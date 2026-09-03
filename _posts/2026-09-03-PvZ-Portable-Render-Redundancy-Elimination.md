---
layout:       post
title:        PvZ-Portable：减少渲染路径上的重复工作
subtitle:     GL 状态缓存、逐帧不变量与确定性回放基准
header-img:   img/games/pvz-portable/bg-pvz-portable.webp
date:         2026-09-03
author:       wszqkzqk
catalog:      true
tags:         性能优化 OpenGL 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

PvZ-Portable 的渲染器走的是一条很典型的 2D 精灵路线：图像最后都会被整理成三角形批次，再交给同一套 GLES2 管线绘制。它没有复杂的场景图，顶点数量也不算多，乍看之下似乎没有多少优化空间。不过，渲染器简单，并不代表每一帧做的事情都已经足够少。

我之前做过[确定性回放系统](https://wszqkzqk.github.io/2026/07/22/PvZ-Portable-Demo-Deterministic-Replay/)。同一份对局录像可以在不同构建中逐 tick 重现，这原本是为了回归测试，后来也成了性能优化的好工具：让两个构建回放同一份输入，再比较它们的绘制耗时，差异就有了清晰的参照。

重新检查这条路径后，发现的问题并不在某个特别昂贵的算法，在许多已经做过、这一帧却又做了一遍的小操作上：反复设置相同的 GL 状态，重复计算同一帧里不会变化的值，以及分配马上就会丢掉的字符串。单看每一项都不起眼，但它们都处在高频路径上，累加起来就值得处理了。

这次改动集中解决了这些重复工作（PR [#462](https://github.com/wszqkzqk/PvZ-Portable/pull/462)）。在这份回放上，原生构建的每帧绘制耗时下降了 14%，Wasm 构建的总绘制耗时下降了 31%；回放断言也确认游戏行为没有改变。下面挑几处比较有代表性的改动记录下来。

## 减少 GL 状态调用

### 每次 Blt 都重设纹理状态

OpenGL 是状态机。纹理绑定、过滤方式、混合方程等状态会一直保留，直到下一次被修改。可是在旧实现里，纹理绑定函数每调用一次，都会完整地设置一遍这些状态（`src/SexyAppFramework/graphics/GLInterface.cpp`）：

```cpp
static void GfxBindTexture(GLuint tex, const float *uvBounds = kDefaultUvBounds, bool clampUv = true)
{
	glBindTexture(GL_TEXTURE_2D, tex);
	int f = gLinearFilter ? GL_LINEAR : GL_NEAREST;
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, f);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, f);
	glUniform1i(gUfClampUvEnabled, clampUv ? 1 : 0);
	glUniform4fv(gUfUvBounds, 1, uvBounds);
}
```

这意味着每次 Blt 都会发出 5 个 GL 调用。实际绘制中，大量精灵来自同一张纹理图集；例如浓雾效果，连续几十次 Blt 可能使用完全相同的纹理和参数。混合模式也有类似问题：`SetDrawMode` 每次都直接调用 `glBlendFunc`，即使目标模式和当前模式根本没变。

驱动不能替调用方假定这次设置和上次一样，所以每个调用仍要经过参数检查，有时还会向命令流写入状态变更。在桌面 OpenGL 上，这个开销未必容易注意到，但是在 GLES2 驱动和 Wasm 的 GL 桩环境里，调用本身的固定成本就明显更高。

### 在 CPU 侧存储状态

解决办法很朴素：在 CPU 侧保存一份最近提交给 GL 的状态，只有目标状态发生变化时才真正调用 GL。纹理状态缓存大致如下：

```cpp
struct GfxTextureCache
{
	GLuint tex = 0;
	int filter = 0;
	int clampUv = -1;
	float uvBounds[4] = {};
	bool valid = false;
};
static GfxTextureCache gTextureCache;

static void GfxBindTexture(GLuint tex, const float *uvBounds = kDefaultUvBounds, bool clampUv = true)
{
	int f = gLinearFilter ? GL_LINEAR : GL_NEAREST;
	int c = clampUv ? 1 : 0;
	if (gTextureCache.valid
		&& gTextureCache.tex == tex
		&& gTextureCache.filter == f
		&& gTextureCache.clampUv == c
		&& memcmp(gTextureCache.uvBounds, uvBounds, sizeof(gTextureCache.uvBounds)) == 0)
		return;

	glBindTexture(GL_TEXTURE_2D, tex);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, f);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, f);
	glUniform1i(gUfClampUvEnabled, c);
	glUniform4fv(gUfUvBounds, 1, uvBounds);

	gTextureCache.tex = tex;
	gTextureCache.filter = f;
	gTextureCache.clampUv = c;
	memcpy(gTextureCache.uvBounds, uvBounds, sizeof(gTextureCache.uvBounds));
	gTextureCache.valid = true;
}
```

混合模式也采用了同样的做法：`SetBlendFunc` 先比较缓存的源、目标因子，相同就直接返回。

```cpp
static void SetBlendFunc(GLenum theSrc, GLenum theDst)
{
	if (gBlendSrc == theSrc && gBlendDst == theDst) return;
	glBlendFunc(theSrc, theDst);
	gBlendSrc = theSrc;
	gBlendDst = theDst;
}
```

这种影子状态缓存并不新鲜，难点在于什么时候必须把它作废。缓存只有在这个纹理对象的参数没有被外部改动时才可靠，而纹理对象的生命周期会带来一个很隐蔽的例外。

### 纹理名复用时要失效缓存

调用 `glDeleteTextures` 删除纹理后，纹理名并不会永久占用，后续 `glGenTextures` 可能把同一个名字重新分配给一个全新的纹理对象。

假设缓存记录的是“纹理 42，使用 LINEAR 过滤”。原纹理释放后，新纹理恰好又拿到 42。调用方再次以相同参数绑定 42 时，缓存会命中，`glTexParameteri` 就被跳过了。但新对象的过滤参数还是 OpenGL 默认值（`GL_NEAREST_MIPMAP_LINEAR`）。对于没有 mipmap 链的纹理，这在 GLES2 中会导致纹理不完整，最终采样出黑色。

所以，缓存不失效不只是少几次调用的问题，也可能直接造成渲染错误。此次改动在三个地方主动清除缓存：释放纹理的 `TextureData::ReleaseTextures`、创建纹理的 `TextureData::CreateTextures`，以及从内存位图恢复纹理的 `GLInterface::RecoverBits`：

```cpp
void TextureData::ReleaseTextures()
{
	GfxInvalidateTextureCache();
	for (auto &piece : mTextures)
		glDeleteTextures(1, &piece.mTexture);
	mTextures.clear();
}
```

凡是纹理对象可能被销毁、替换或重新上传的地方，都需要检查是否应该让影子状态失效。实际做这类优化时，逐一列出对象生命周期的所有入口，往往比写缓存本身更费心，也更不能省略。

## 顶点格式只需要设置一次

旧代码在每次批次冲刷（`GfxEnd`）上传顶点数据前，都会重新设置顶点属性：

```cpp
// 修改前：每次 flush 都执行
glVertexAttribPointer(0, 3, GL_FLOAT,         GL_FALSE, sizeof(GLVertex), (const void*)0);
glEnableVertexAttribArray(0);
glVertexAttribPointer(1, 4, GL_UNSIGNED_BYTE, GL_TRUE,  sizeof(GLVertex), (const void*)(sizeof(float)*3));
glEnableVertexAttribArray(1);
glVertexAttribPointer(2, 2, GL_FLOAT,         GL_FALSE, sizeof(GLVertex), (const void*)(sizeof(float)*3 + sizeof(uint32_t)));
glEnableVertexAttribArray(2);
```

但整个渲染器生命周期里只有一个 VBO，也只有这一种顶点布局。`glVertexAttribPointer` 记录的是当前绑定的 `GL_ARRAY_BUFFER` 及其布局；只要两者都不变，这些设置就会一直有效。GLES2 虽然没有 VAO，顶点属性状态仍然是上下文级的持久状态。

因此，这 6 个调用被移到了 `GLInterface::Init`，紧跟在 VBO 创建之后。后续每次冲刷只需上传数据并执行 `glDrawArrays`。

批次冲刷的时机也顺手调整了。旧代码会先把顶点追加到数组，发现超过 `MAX_VERTICES`（16384）后才 flush：

```cpp
// 修改前
const int oldCount = gNumVertices;
gNumVertices += arrCount;
gVertices.resize(gNumVertices);              // 可能超过 MAX_VERTICES
memcpy(gVertices.data() + oldCount, arr, sizeof(GLVertex) * arrCount);
GfxFlushIfOverBudget();                      // 超限后整批上传
```

这样一来，VBO 明明按 `MAX_VERTICES` 预分配，却可能因为某一批顶点超限而重新分配更大的缓冲存储。现在改为写入前先确认空间：

```cpp
static void GfxEnsureSpace(int theAdditional)
{
	if (gVertexMode == (GLenum)-1 || gNumVertices + theAdditional <= MAX_VERTICES) return;
	GLenum oldMode = gVertexMode;
	GfxEnd();
	GfxBegin(oldMode);
}
```

这样上传的数据不会超过预分配容量，VBO 大小也能保持稳定。顶点数组 `gVertices` 同样在初始化时一次性 `resize(MAX_VERTICES)`，flush 后不再 `clear()`；之后添加一个批次，基本就是 `memcpy` 加上计数器更新。

## 把逐帧不变量提出来

重复计算不只发生在 GL 调用里，游戏逻辑也有不少同样的例子：有些值在一帧（或一个 tick）内根本不会变化，却被多个函数各算一遍。这次改动把几处这样的计算合并了。

鼠标命中测试就是其中最明显的一处。`Board::Update` 每个逻辑 tick 都会调用 `UpdateMousePosition`；旧实现中，`UpdateCursor`、`UpdateToolTip` 和 `HighlightPlantsForMouse` 各自做一次 `MouseHitTest`，砸罐子关卡、禅境花园还会再做一两次。命中测试需要遍历种子栏、金币和植物等对象，最多一帧会重复 5 遍。

现在在 `UpdateMousePosition` 入口处只做一次，再把 `HitResult` 传给下游：

```cpp
void Board::UpdateMousePosition()
{
	SeedType aCursorSeedType = GetSeedTypeInCursor();
	int aMouseX = mApp->mWidgetManager->mLastMouseX - mX;
	int aMouseY = mApp->mWidgetManager->mLastMouseY - mY;
	HitResult aHitResult;
	MouseHitTest(aMouseX, aMouseY, &aHitResult);

	UpdateCursor(&aHitResult);
	UpdateToolTip(&aHitResult);
	...
}
```

下游函数仍保留了默认参数；如果未来有代码单独调用它们，原来的行为不会改变。

骨骼动画也有一个类似的重复。绘制一个 reanimation 时，旧实现会让每条动画轨道都调用一次 `GetFrameTime`，重复计算当前帧位置和插值系数。对同一次绘制来说，这些值当然相同，所以现在改在 `DrawRenderGroup` 入口计算一次，再传给所有轨道：

```cpp
PvzpTriangleGroup aTriangleGroup;
ReanimatorFrameTime aFrameTime;
GetFrameTime(&aFrameTime);
for (int aTrackIndex = 0; aTrackIndex < mDefinition->mTracks.count; aTrackIndex++)
{
	...
	bool aTrackDrawn = DrawTrack(g, aTrackIndex, theRenderGroup, &aTriangleGroup, &aFrameTime);
```

另外，`PvzpTriangleGroup` 的构造函数原来会把 256 个三角形、共 768 个顶点的颜色清零。粒子和骨骼动画在添加三角形时都会明确写入颜色，这次就不再为这些必然会被覆盖的字段做初始化了。

其他改动比较零散，但思路相同：雾效绘制把 `SetColorizeImages` 和只依赖帧计数的时间量移到循环外；`PlantDrawHeightOffset` 对同一格的 `GetFlowerPotAt` 查找从两次合并为一次；调试文本为空时不再调用 5 次 `DrawStringWordWrapped`；`ImageFont` 绘制同一字符时，把最多 5 次 `GetCharData`（一次 `std::map` 查找）合并为一次；提示框按行切分文本时改用 `std::string_view`，避免 `std::string::substr` 带来的逐行堆分配。粒子和骨骼求值中最热的 `PvzpCurveEvaluate`、`FloatTrackEvaluate` 也移入头文件并标为内联，让编译器有机会直接展开。

## 用确定性回放做基准

性能优化不能靠“感觉应该快了”。这次的数字都来自同一份输入、同一套回放流程。

测试负载是一份真实对局录像 `pvzp-20260822-011238.dmo`：共 52750 次逻辑更新，时长约 8.8 分钟，用 `-play` 参数回放。录像是在两个对比构建的共同祖先上录制的，因此两边收到的是逐字节相同的输入流。

原生和 Wasm 分别比较基线构建（merge-base `ab2fbde`）与优化构建，并交错运行 3 次（base → head → base → …），尽量抵消机器状态随时间变化带来的影响。表中是这几次运行的平均值，置信区间用 Welch t 检验计算。

**原生环境**：Ryzen 7 5800H、Renoir 集成显卡、Mesa 26.2.1，`RelWithDebInfo`。

| 指标 | 基线 | 优化后 | 变化 | p 值 | 95% CI |
|---|---:|---:|---:|---:|---:|
| 每帧绘制耗时 | 2.890 ms | 2.485 ms | **-14.0%** | 7.9e-04 | [11.2%, 16.8%] |
| 总绘制耗时 | 91.3 s | 78.5 s | **-14.0%** | 8.1e-04 | [11.2%, 16.8%] |
| 进程 CPU 时间 | 233.7 s | 216.4 s | **-7.4%** | 2.6e-03 | [4.8%, 10.0%] |

退出时记录的平均 FPS 从 343 上升到约 400，与每帧绘制耗时下降约 14% 基本吻合。回放按真实时间定速（100 updates/s），所以两边墙钟时间相同；收益体现为每帧占用的 CPU 更少。对桌面平台来说，这是额外余量；对 Android、iOS、Switch 等平台，则可能转化为更低的发热和更长的续航。这里测到的主要是 CPU 侧成本（包括 GL 驱动调用），如果场景本身受 GPU 限制，实际收益会小一些。

**Wasm（Node.js 离屏测试）**：

| 指标 | 基线 | 优化后 | 变化 | p 值 | 95% CI |
|---|---:|---:|---:|---:|---:|
| 总绘制耗时 | 118.4 s | 81.4 s | **-31.2%** | 6.0e-07 | [29.7%, 32.7%] |
| 进程 CPU 时间 | 146.9 s | 109.9 s | **-25.2%** | 4.6e-05 | [24.1%, 26.3%] |

Wasm 的降幅更大，原因很直接：测试中的每次 GL 调用都要跨过 wasm-JavaScript 边界，固定成本比原生高；真实浏览器还会进行 WebGL 参数校验，因此减少调用通常更划算。不过，测试并没有真的渲染画面，绝对时间不能直接当作浏览器成绩，适合参考的只有相对变化。

还要注意，Wasm 两个构建的绘制次数并不相同：更快的构建会把更少的更新合并到一帧里，于是实际绘制帧数反而更多。因此 Wasm 这里比较的是总耗时，而不是每帧耗时。

**行为验证**：原生构建每次回放的更新数都准确为 52750，约 31600 次绘制只有 ±6 的波动（回放按真实时间定速，帧边界会有轻微差异）；录像内置的回放断言全程没有触发。两边处理的逻辑负载和渲染内容可以视为一致，性能差异来自这次优化。

## 结语

这次改动没有引入新的算法，做的事情可以概括为一句话：同一帧里不会变化的东西，不要反复计算，已经提交过、且没有变化的状态，不要重复提交。

状态缓存值得用，但必须把失效路径当成正确性的一部分来设计。纹理名复用就是一个很容易漏掉的角落，缓存没有及时作废，结果可能不是没省下多少时间，而是直接画出黑纹理。

逐帧不变量则是相对稳妥的优化方向。命中结果、帧时间、顶点格式本来就在同一帧内保持不变，把计算移到更高一层通常不会改变行为，收益也能用基准直接验证。排查时，与其只盯着某个“最慢”的函数，不如顺着每帧路径问一句：这里是不是已经算过了？

最后，确定性回放让这类工作有了可以复现、也可以被推翻的依据。同一输入、交错运行和统计检验，把“应该变快了”变成了带有置信区间的测量结果。最初为回归测试搭建的回放系统，现在也成了性能优化的基础设施。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。研究或使用此项目时，**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies)购买）。你需要从正版游戏中提取以下文件，放到 PvZ-Portable 的程序所在目录：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
