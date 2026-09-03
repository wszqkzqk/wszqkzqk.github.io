---
layout:       post
title:        PvZ-Portable：消除渲染路径上的每帧冗余工作
subtitle:     CPU 侧 GL 状态缓存、逐帧不变量提升与确定性回放基准
header-img:   img/games/pvz-portable/bg-pvz-portable.webp
date:         2026-09-03
author:       wszqkzqk
catalog:      true
tags:         性能优化 OpenGL 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

PvZ-Portable 的渲染走的是一条很典型的 2D 精灵路径：所有图像最终都汇成三角形批次，通过同一条 GLES2 管线画到屏幕上。这样的路径看起来没什么可优化的——没有复杂的场景图，没有光照计算，顶点量也不大。但“看起来没问题”和“测出来没问题”是两回事。

此前笔者构建了[确定性回放系统](https://wszqkzqk.github.io/2026/07/22/PvZ-Portable-Demo-Deterministic-Replay/)，同一份对局录像可以在任何构建上逐 tick 复现。它本来是回归测试工具，但同时提供了一种难得的能力：**给性能优化做可证伪的对照实验**。两个构建回放同一份录像，逻辑负载严格一致，绘制耗时的差异就只能来自代码差异。

带着这个工具重新审视渲染路径，笔者发现的问题不是某个昂贵的算法，而是大量的**重复**：重复设置相同的 GL 状态，重复计算同一帧内不会变化的值，重复分配立刻就丢弃的字符串。每一处单独看都微不足道，但它们全部位于每帧都要执行的路径上。这次优化（PR [#462](https://github.com/wszqkzqk/PvZ-Portable/pull/462)）把这类重复系统地消掉，原生构建的每帧绘制耗时降低了 14%，Wasm 构建的总绘制耗时降低了 31%，回放断言同时确认行为没有任何变化。本文记录其中几个有代表性的点。

## 冗余的 GL 状态调用

### 每次 Blt 都重设一遍纹理状态

OpenGL 是一台状态机：纹理绑定、过滤参数、混合方程都是持久状态，设置一次就一直有效。但引擎的纹理绑定函数原来是这样写的（`src/SexyAppFramework/graphics/GLInterface.cpp`，修改前）：

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

也就是说，**每一次** Blt 都无条件发出 5 个 GL 调用。而实际场景中，大量精灵共享同一纹理图集，雾效这类绘制更是连续几十次 Blt 使用同一张纹理、同一组参数。混合模式也一样：`SetDrawMode` 在正常混合和叠加混合之间切换时，每次都直接调用 `glBlendFunc`，不管目标值和当前值是否相同。

驱动程序无法假设“这次设置和上次一样”。每次调用都要走完整的参数校验，并可能向命令流写入一条状态变更。在桌面 GL 上这未必显眼，但在 GLES2 驱动和 Wasm 的 GL 桩上，每次调用的固定开销都真实存在。

### CPU 侧的影子状态

修改的方向很直接：在 CPU 侧保存一份影子状态，目标状态与影子一致时直接跳过（修改后）：

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

混合模式也加了同样的缓存：

```cpp
static void SetBlendFunc(GLenum theSrc, GLenum theDst)
{
	if (gBlendSrc == theSrc && gBlendDst == theDst) return;
	glBlendFunc(theSrc, theDst);
	gBlendSrc = theSrc;
	gBlendDst = theDst;
}
```

影子状态缓存是 GL 程序的经典手法，思路本身并不新鲜。真正需要小心的是它的正确性条件，这也是这次改动里最容易踩坑的地方。

### 缓存失效：纹理名会被复用

影子状态成立的前提，是“同名纹理对象的参数没有被别人改过”。这个前提在一个容易被忽略的地方会失效：`glDeleteTextures` 删除纹理后，**纹理名可以被后续的 `glGenTextures` 复用**。

假设缓存里记录着“纹理 42，LINEAR 过滤”。某张纹理被释放后，一张**新**纹理通过 `glGenTextures` 又拿到了 42 这个名字。此时如果调用方以相同参数绑定 42，缓存命中，所有 `glTexParameteri` 都被跳过——但新纹理对象是全新创建的，它的过滤参数还是 GL 默认值（`GL_NEAREST_MIPMAP_LINEAR`）。一张没有 mipmap 链的纹理按 mipmap 过滤采样，在 GLES2 上属于不完整纹理，采样结果是黑色。也就是说，**缓存不失效不是性能问题，而是渲染错误**。

因此这次改动在三个位置显式失效缓存：删除纹理的 `TextureData::ReleaseTextures`、创建纹理的 `TextureData::CreateTextures`，以及从内存位图恢复纹理的 `GLInterface::RecoverBits`：

```cpp
void TextureData::ReleaseTextures()
{
	GfxInvalidateTextureCache();
	for (auto &piece : mTextures)
		glDeleteTextures(1, &piece.mTexture);
	mTextures.clear();
}
```

凡是纹理对象生死发生变化的地方，影子状态都必须作废。做这类优化时，把失效路径一条条列出来核对，比缓存本身更重要。

## 只设一次的顶点格式

旧代码在每次批次冲刷（`GfxEnd`）上传顶点数据前，都要重新设置一遍顶点属性：

```cpp
// 修改前：每次 flush 都执行
glVertexAttribPointer(0, 3, GL_FLOAT,         GL_FALSE, sizeof(GLVertex), (const void*)0);
glEnableVertexAttribArray(0);
glVertexAttribPointer(1, 4, GL_UNSIGNED_BYTE, GL_TRUE,  sizeof(GLVertex), (const void*)(sizeof(float)*3));
glEnableVertexAttribArray(1);
glVertexAttribPointer(2, 2, GL_FLOAT,         GL_FALSE, sizeof(GLVertex), (const void*)(sizeof(float)*3 + sizeof(uint32_t)));
glEnableVertexAttribArray(2);
```

而整个渲染器生命周期里只有一个 VBO、一种顶点布局。`glVertexAttribPointer` 记录的是“当前绑定的 `GL_ARRAY_BUFFER` + 布局”，只要这两样不变，设置就是持久的——GLES2 没有 VAO，但顶点属性状态同样是上下文级的持久状态。于是这 6 个调用移到了 `GLInterface::Init` 中创建 VBO 之后，之后每次冲刷只剩 `glBufferData` 和 `glDrawArrays`。

冲刷逻辑本身也有一处修正。旧代码是“先添加顶点，发现超过 `MAX_VERTICES`（16384）再 flush”：

```cpp
// 修改前
const int oldCount = gNumVertices;
gNumVertices += arrCount;
gVertices.resize(gNumVertices);              // 可能超过 MAX_VERTICES
memcpy(gVertices.data() + oldCount, arr, sizeof(GLVertex) * arrCount);
GfxFlushIfOverBudget();                      // 超限后整批上传
```

问题在于 VBO 是按 `MAX_VERTICES` 预分配的。一旦某批顶点使总数超限，`glBufferData` 就会用更大的尺寸**重新分配**缓冲存储——这是一次隐式的 GPU 侧重分配。新代码改成“先确保空间，再写入”：

```cpp
static void GfxEnsureSpace(int theAdditional)
{
	if (gVertexMode == (GLenum)-1 || gNumVertices + theAdditional <= MAX_VERTICES) return;
	GLenum oldMode = gVertexMode;
	GfxEnd();
	GfxBegin(oldMode);
}
```

上传量因此始终不超过预分配大小，VBO 尺寸保持稳定。顺带地，顶点数组 `gVertices` 不再每次 flush 后 `clear()`，而是初始化时一次性 `resize(MAX_VERTICES)`，之后的批次添加退化为纯粹的 `memcpy` 和计数器累加。

## 逻辑侧的逐帧不变量

GL 调用之外，游戏逻辑侧也存在同样模式的问题：一些值在同一帧（或同一 tick）内是不变量，却被反复计算。这些改动单看都不起眼，但它们全都在每帧执行的路径上。

**鼠标命中测试从最多 5 遍合并到 1 遍。** `Board::Update` 每个逻辑 tick 都会调用 `UpdateMousePosition`，而旧代码中 `UpdateCursor`、`UpdateToolTip`、`HighlightPlantsForMouse` 各自独立做一遍 `MouseHitTest`，砸罐子关卡和禅境花园还会额外再做一两遍。`MouseHitTest` 本身并不便宜：要遍历种子栏、所有金币、植物等实体逐个做矩形判定。现在 `UpdateMousePosition` 入口做一遍，把 `HitResult` 传给下游：

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

各下游函数保留了默认参数兜底，被独立调用时行为不变。

**骨骼动画的帧时间从每个轨道一次合并到每次绘制一次。** 绘制一个 reanimation 时，原来每个动画轨道都调一次 `GetFrameTime`，计算当前帧位置和插值系数——对同一次绘制，这些值显然是同一个。现在 `DrawRenderGroup` 入口算一次，传给所有轨道：

```cpp
PvzpTriangleGroup aTriangleGroup;
ReanimatorFrameTime aFrameTime;
GetFrameTime(&aFrameTime);
for (int aTrackIndex = 0; aTrackIndex < mDefinition->mTracks.count; aTrackIndex++)
{
	...
	bool aTrackDrawn = DrawTrack(g, aTrackIndex, theRenderGroup, &aTriangleGroup, &aFrameTime);
```

**删掉三角形组构造里的 768 次清零。** 粒子系统和骨骼动画的绘制都会在栈上创建一个 `PvzpTriangleGroup`，它的构造函数原来要把 256 个三角形 × 3 个顶点的颜色全部清零——而这些颜色在添加三角形时必然被显式写入，清零是纯浪费。

**其余琐碎但同类的问题**也一并处理：雾效绘制把 `SetColorizeImages` 和只依赖帧计数的时间量提出双重循环；`PlantDrawHeightOffset` 中同一格的 `GetFlowerPotAt` 查找从 2 次并为 1 次；调试文本为空时跳过 5 次 `DrawStringWordWrapped`；`ImageFont` 绘制时对同一字符的 `GetCharData`（一次 `std::map` 查找）从每个字符最多 5 次并为 1 次；提示框每帧按行切分文本从 `std::string` 的 `substr`（逐行堆分配）改为 `std::string_view`；粒子和骨骼求值中最热的 `PvzpCurveEvaluate`、`FloatTrackEvaluate` 则内联进了头文件。

## 用确定性回放做基准

性能优化最怕“感觉快了”。这次的所有数字都来自同一负载下的严格对照。

**负载**：一份真实对局录像 `pvzp-20260822-011238.dmo`（52750 个逻辑更新，约 8.8 分钟），用 `-play` 回放。录像录制于两个对比构建的共同祖先，因此两边回放的是逐字节相同的输入流。

**方法**：原生和 Wasm 各自将基线构建（merge-base `ab2fbde`）与优化构建**交错运行 3 次**（base → head → base → …），抵消系统漂移；结果取平均，置信区间用 Welch t 检验计算。

**原生**（Ryzen 7 5800H + Renoir iGPU，Mesa 26.2.1，RelWithDebInfo）：

| 指标 | 基线 | 优化后 | 变化 | p 值 | 95% CI |
|---|---:|---:|---:|---:|---:|
| 每帧绘制耗时 | 2.890 ms | 2.485 ms | **-14.0%** | 7.9e-04 | [11.2%, 16.8%] |
| 总绘制耗时 | 91.3 s | 78.5 s | **-14.0%** | 8.1e-04 | [11.2%, 16.8%] |
| 进程 CPU 时间 | 233.7 s | 216.4 s | **-7.4%** | 2.6e-03 | [4.8%, 10.0%] |

退出时记录的平均 FPS 从 343 升到约 400，与每帧绘制耗时的降幅一致。需要说明，回放按真实时间定速（100 updates/s），墙钟时长两边相同，收益体现为**每帧 CPU 占用降低**——对桌面平台是余量，对 Android、iOS、Switch 这类移动平台则直接是发热和续航。另外，这些指标主要反映 CPU 侧成本（含 GL 驱动调用）；GPU 受限场景的有效收益会小一些。

**Wasm**（Node.js 测试桩）：

| 指标 | 基线 | 优化后 | 变化 | p 值 | 95% CI |
|---|---:|---:|---:|---:|---:|
| 总绘制耗时 | 118.4 s | 81.4 s | **-31.2%** | 6.0e-07 | [29.7%, 32.7%] |
| 进程 CPU 时间 | 146.9 s | 109.9 s | **-25.2%** | 4.6e-05 | [24.1%, 26.3%] |

Wasm 侧的降幅明显更大，原因也直接：桩环境里每次 GL 调用都要跨越 wasm→JS 边界，固定开销比原生高；真实浏览器里还要加上 WebGL 的参数校验，只会更贵。减少 GL 调用次数在这类环境里的收益被进一步放大。需要注意的是，Wasm 下两个构建的绘制次数并不相同（更快的构建每帧打包的更新更少、绘制帧数更多），所以 Wasm 表比较的是总耗时而非每帧耗时；另外测试桩并不真实渲染，绝对数字不代表浏览器表现，只有相对比较有意义。

**行为不变的验证**：原生构建每次回放的更新数都精确等于 52750，绘制次数在约 31600 次中仅有 ±6 的浮动（回放按真实时间定速，帧边界对齐略有差异）；录像内嵌的回放断言全程无一触发。逻辑负载和渲染负载在统计意义上完全一致，性能差异只能来自优化本身。

## 结语

这次改动没有引入任何新算法，主题只有一个：**每帧重复做的事情，让它只做一次**。有三点经验值得记录。

**对状态机 API，CPU 侧影子状态几乎总是值得的。** 但缓存的正确性取决于失效路径是否找全——纹理名复用这类隐蔽渠道，会让“性能优化”悄悄变成“渲染错误”。把所有对象生死变化的点列出来逐一核对，是这类改动不能省的一步。

**不变量提升是最安全的优化。** 命中测试、帧时间、顶点格式——这些值在同一帧内本来就不会变，合并计算不改变任何行为，风险极低，收益却可以直接测量。排查的方向不是“哪里慢”，而是“哪里在重复”。

**确定性负载让性能工作可证伪。** 同一份输入、交错运行、统计检验——有了这套基准，“优化”不再是印象，而是带有置信区间的测量结果。确定性回放系统此前为回归测试而建，如今成了性能工作的基础设施。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。研究或使用此项目时，**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies)购买）。你需要从正版游戏中提取以下文件，放到 PvZ-Portable 的程序所在目录：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
