---
layout:       post
title:        PvZ-Portable：渲染路径上的坐标与寻址陷阱
subtitle:     D3DX7 半像素偏移与 BltRotated 行步长——两个潜伏多年的小修复
header-img:   img/games/pvz-portable/bg-pvz-portable.webp
date:         2026-06-15
author:       wszqkzqk
catalog:      true
tags:         OpenGL 游戏移植 图形渲染 开源软件 开源游戏 PvZ-Portable
---

## 引言

移植旧引擎的渲染栈时，最费神的往往不是大重构，而是旧框架关于像素位置的假设。这些假设有两层：一是逻辑坐标如何映射到屏幕像素，二是像素在内存中如何排列。它们写死在代码里多年，平时不会出错，只在特定路径上露出马脚。

PvZ-Portable 的渲染路径上就有两个这样的 bug。一个是 D3DX7 时代遗留的半像素偏移，在主菜单草丛的接缝处制造了一道 1 像素的亮线；另一个是软件光栅化旋转绘制里的行步长错误，从框架代码最初导入仓库时就存在。两个修复都只有一两行，但定位它们都要先回答同一个问题：这段代码对位置的理解，和当前的渲染管线还一致吗？

## 主菜单左下角的缝隙：被遗漏的 D3DX7 半像素偏移

### 现象：一张差点搞反顺序的对比图

此前，社区用户在 [Issue #284](https://github.com/wszqkzqk/PvZ-Portable/issues/284) 里报告了一个非常奇怪的 Bug：

> 主菜单左下角的草有细小的视觉问题。与原版不一致（有细小的缝隙）。

配图里的缝隙细到不认真看几乎会忽略。但既然被提出来了，就得查清楚。排查过程不算复杂，最后定位到的根因却很有代表性：一个从 D3DX7 时代遗留下来的 `-0.5f` 平移偏移，在年初的坐标系统一清理中被漏掉了。

这件事本身不大，但它说明了这类像素级视觉回归的一个特点：**连报告者自己都很难一眼分清哪个是对的**。毕竟草丛边缘的 1 像素缝隙，在截图压缩、显示器差异、甚至观看角度不同的情况下，都可能被误判。

### 背景：D3DX7 的半像素偏移是从哪来的

要理解这个 `-0.5f`，得先回到今年初的一次坐标系清理。

PvZ-Portable 的图形栈是从 SexyAppFramework 继承而来，原版基于 D3DX7/Direct3D。Direct3D 9 及更早版本里，屏幕像素中心位于整数坐标的 `(0.5, 0.5)` 处，而纹理采样通常按 texel 中心对齐。很多旧引擎为了把逻辑坐标（整数像素左上角）映射到 D3D 的像素中心，会在顶点或变换矩阵里手动减去 `0.5f`。

今年初，笔者在把渲染管线统一迁移到 OpenGL ES 2.0 时，提交了 [eb6526a](https://github.com/wszqkzqk/PvZ-Portable/commit/eb6526a3625985205cb982632cc68a5532492d40)“Fix: normalize coordinate mapping and remove D3DX7 legacy offsets”。那次改动做了三件事：

1. 正交投影矩阵的范围从 `(width - 1, height - 1)` 改为 `(width, height)`，让逻辑视口覆盖完整像素范围；
2. 在 `TextureData::Blt`、`TextureData::BltTransformed`、`GLInterface::FillRect` 里移除了手动 `-0.5f` 的顶点偏移；
3. 简化了 `BltTransformed` 里为了兼容旧坐标系而引入的 `pixelcorrect` 变量。

那次提交之后，大部分由半像素偏移引起的错位都消失了。但显然，清理并不彻底。

### 根因：Reanimator 矩阵里的漏网之鱼

主菜单的背景草皮不是一张静态贴图，而是由 Reanimator 骨骼动画驱动的组合画面。草丛、地面、标题文字等元素被拆成多个动画轨道，每帧根据关键帧插值计算出变换矩阵，再批量绘制。

出问题的那段代码在 `src/Sexy.TodLib/Reanimator.cpp` 的 `Reanimation::DrawTrack` 中。该函数负责把单个轨道的图像或图集加入三角带批次。在把轨道局部变换、动画变换、覆盖矩阵以及 Graphics 的平移叠加起来之后，旧代码会再加一个 `-0.5f` 的平移：

```cpp
SexyMatrix3Translation(
    aMatrix,
    aTrackInstance->mShakeX + g->mTransX - 0.5f,
    aTrackInstance->mShakeY + g->mTransY - 0.5f
);
```

注释写着“轨道震动及 g 的影响”，但 `-0.5f` 显然不是震动，而是当年为了适配 D3D 像素中心而塞进去的修正项。在 OpenGL ES 2.0 的管线里，逻辑坐标 `(x, y)` 直接对应片元的左下角/左上角（取决于投影矩阵方向），再去手动偏移半个像素，反而会把贴图推离正确位置。

更关键的是，这个偏移只在**未使用图集**的动画路径上生效。PvZ-Portable 支持 Reanim Atlas 优化，图集路径下的绘制流程在 `AddTriangle` 时走的是另一套坐标映射。而主菜单的草皮恰好没有进图集，于是这个漏网的 `-0.5f` 就在屏幕左下角制造了一道缝隙。

为什么偏偏是左下角？因为草皮贴图在该位置由多个动画轨道拼接而成，每个轨道都被平移了同样的半个像素，接缝处就被拉开了一条线。在单个独立精灵上，半个像素的偏移可能只是轻微模糊；但在需要拼接的连续图案上，它会变成可见的裂缝。

### 修复与验证

修复本身只有一行：

```diff
- SexyMatrix3Translation(aMatrix, aTrackInstance->mShakeX + g->mTransX - 0.5f, aTrackInstance->mShakeY + g->mTransY - 0.5f);
+ SexyMatrix3Translation(aMatrix, aTrackInstance->mShakeX + g->mTransX, aTrackInstance->mShakeY + g->mTransY);
```

对应的提交是 [4f80f04](https://github.com/wszqkzqk/PvZ-Portable/commit/4f80f0469ef800a42b618dc5efaec927243e71cf)。

验证阶段，笔者在本地重新截图对比：修复前左下角草丛有明显亮缝，修复后缝隙消失，与原版一致。peashooter2 重新确认后也表示问题解决。那场截图顺序乌龙反而让笔者更确信：对于这种像素级差异，必须建立明确的“修复前 / 修复后 / 原版”三组对照，否则连当事人都会看混。

### 还有另一个 -0.5f

在排查过程中，笔者注意到 `Reanimator.cpp` 里还有一处 `-0.5f` 没有动：

```cpp
// GetTrackMatrix
SexyMatrix3Translation(theMatrix, aTrackInstance->mShakeX - 0.5f, aTrackInstance->mShakeY - 0.5f);
```

这个函数用于获取动画轨道的当前变换矩阵，主要供游戏逻辑查询（例如判断某个动画部件的屏幕位置，用于点击检测或特效挂载）。它并不直接参与绘制，因此没有引发可见的视觉问题。是否需要同步移除，取决于后续逻辑层是否也按照 OpenGL 坐标系来理解矩阵结果。目前笔者选择保持原样，因为贸然改动可能会影响点击判定；如果未来发现逻辑层坐标也有偏差，再统一处理会更安全。

## 旋转绘制里的行步长错误

半像素偏移是坐标约定的问题。另一处问题则出在更底层的地方——像素在内存中的排列方式。

PvZ-Portable 的屏幕绘制早已迁移到 GLES2（此前的文章介绍过[迁移过程](https://wszqkzqk.github.io/2026/02/16/PvZ-Portable-GLES2-Migration/)），但框架里还完整保留着软件光栅化路径：当绘制目标是 `MemoryImage` 而不是屏幕时，所有图元都改由 CPU 逐像素写入。`ReanimatorCache` 为种子选择界面、图鉴等处预渲染的植物和僵尸图像，就是先画进内存图像再使用的；`FilterEffect` 的滤镜处理也在内存图像上完成；在未启用硬件加速的环境中，它还是整个渲染器的回退方案。检查这条路径时，笔者发现旋转绘制的源图寻址里有一个行步长错误（PR [#466](https://github.com/wszqkzqk/PvZ-Portable/pull/466)），它从框架代码最初导入仓库时就存在。

### 子矩形的行步长

位图在内存中是一维数组。对于紧密排列的 32 位图像，第 `y` 行第 `x` 个像素的地址是：

```
bits + y * 图像宽度 + x
```

这里的图像宽度就是行步长（stride，也叫 pitch）：从当前行移动到下一行，指针需要前进的像素数。

绘制时经常只取源图的一部分，也就是用一个源矩形 `theSrcRect` 指定要画的区域。需要注意，源矩形并不拥有自己的存储，它只是整图上的一个视图。从源矩形第 0 行的末尾跳到第 1 行的开头，指针要越过源矩形右边界到整图右边界、以及下一行左边界到源矩形左边界这两段像素，合起来恰好是整图宽度。所以，**子矩形的行步长仍然是整图宽度，而不是子矩形自己的宽度**。

图集（atlas）是最典型的场景。框架自带的 `ReanimAtlas` 会把一个骨骼动画的全部帧打包进一张大图，绘制某一帧时，源矩形就是这一帧在大图中的位置：纵坐标通常不为 0，宽度也小于整图。对这种源矩形做逐行读取，行步长一旦用错，读到的就是别的帧。

### 基准指针与循环步长的失配

软件路径的旋转绘制由 `MemoryImage::BltRotated` 实现。它先把源指针定位到源矩形的左上角，再包含进 `BltRotatedHelper.inc` 执行逐像素采样。修复前，定位基准指针的代码是这样的（`src/SexyAppFramework/graphics/MemoryImage.cpp`）：

```cpp
uint32_t* aSrcBits = aMemoryImage->GetBits() + theSrcRect.mX + theSrcRect.mY*theSrcRect.mWidth;
```

问题出在最后一项：`theSrcRect.mY*theSrcRect.mWidth` 把源矩形的宽度当成了行步长。按照前面的分析，第 `mY` 行的起始位置应该是 `mY * 整图宽度`。

再看循环体内部（`src/SexyAppFramework/graphics/inc_routines/BltRotatedHelper.inc`）。采样坐标 `aU`、`aV` 是相对源矩形左上角的，循环按整图宽度把采样坐标换算成地址：

```cpp
int aWidth = theImage->mWidth;
...
SRC_TYPE* srcptr = aSrcBits + (aVInt * aWidth) + aUInt;
```

双线性插值读取下方两个相邻像素时，同样加的是整图宽度：

```cpp
uint32_t src3 = READ_COLOR(srcptr+theImage->mWidth);
uint32_t src4 = READ_COLOR(srcptr+1+theImage->mWidth);
```

也就是说，循环体假定 `aSrcBits` 已经按整图宽度定位到了源矩形左上角。基准指针用源矩形宽度，循环步长用整图宽度——同一个算法里出现了两个不一致的宽度，读取位置必然有偏差。偏差量是：

```
theSrcRect.mY * (整图宽度 - 源矩形宽度)
```

源矩形越靠下、越窄，偏得越远。在图集上取一帧靠下的图，再旋转绘制，读到的就是图集中其他位置的内容，画面上表现为图像错乱。

### 为什么一直没有暴露

这个 bug 从最初导入就存在，却一直没人踩到，原因是触发它需要几个条件同时成立，而常见用法恰好都落在安全区里：

- **整图绘制**：`mX`、`mY` 都是 0，偏移项整个为 0，两种算法等价。
- **横向条带**：多帧动画常用一排帧拼成的长条图（cel strip），源矩形 `mY` 为 0，误差同样为 0。
- **满宽竖向条带**：源矩形宽度等于整图宽度时，两个宽度相等，也不会出错。

除此之外，游戏的主渲染路径走的是 GL。GL 侧的纹理上传按 `offy * img->GetWidth() + offx` 定位子区域，绘制时再用纹理坐标选取源矩形，两处都是对的。只要硬件加速可用，屏幕上就永远看不到这个错误。游戏内真正的旋转绘制大多又经过 `BltMatrix` 的三角形路径，按 UV 采样，同样不受影响。

`BltRotated` 实际服务的场景本来就不多：`Graphics::DrawImageRotatedF`、`DrawImageTransform` 的软件实现，以及 `MemoryImage::BltF`——浮点坐标绘制会以旋转角 0 转交给它，所以它实际上是软件路径上带裁剪的通用位块传输。这些调用再叠加目标是内存图像、源矩形纵坐标非零、源矩形比整图窄三个条件，日常运行中几乎没有机会同时满足。

同一个文件里就有正确的对照。普通位块传输 `NormalBlt` 的定位写法是：

```cpp
uint32_t* aSrcPixelsRow = ((uint32_t*) aSrcMemoryImage->GetBits()) + (theSrcRect.mY * theImage->mWidth) + theSrcRect.mX;
```

相邻的两个函数，一个用整图宽度，一个用源矩形宽度。放在一起看，错误一目了然；分开看，两处各自都像是正确的写法。

### 修复

修复就是把基准指针的行步长改回整图宽度。真彩色路径和 256 色调色板路径各有一处，调色板路径读取的是颜色索引 `mColorIndices`，错误形式完全一样：

```diff
-			uint32_t* aSrcBits = aMemoryImage->GetBits() + theSrcRect.mX + theSrcRect.mY*theSrcRect.mWidth;
+			uint32_t* aSrcBits = aMemoryImage->GetBits() + theSrcRect.mX + theSrcRect.mY*aMemoryImage->mWidth;
```

```diff
-			uchar* aSrcBits = aMemoryImage->mColorIndices.get() + theSrcRect.mX + theSrcRect.mY*theSrcRect.mWidth;
+			uchar* aSrcBits = aMemoryImage->mColorIndices.get() + theSrcRect.mX + theSrcRect.mY*aMemoryImage->mWidth;
```

两处错误一模一样，说明当初实现调色板分支时，把真彩色分支的寻址表达式整个复制了过去，错误的约定也一起被复制了。修复后，基准指针与循环体的行步长一致，两条分支的寻址约定也与 `NormalBlt`、GL 路径对齐。

## 结语

两个 bug 的修复都只有一两行，但它们踩中的是同一类陷阱：**旧框架关于像素位置的约定，在新管线里不再自动成立**。

半像素偏移是坐标约定：D3DX7 时代的手动 `0.5f` 修正在当年是正确的，换成 OpenGL ES 2.0 后就成了错误。年初的大规模清理没有覆盖到 Reanimator 的非图集绘制路径，于是它在草丛接缝处又藏了三个月。行步长错误是寻址约定：源矩形只是一个视图，它的行步长永远属于底图，而 `BltRotated` 的基准指针却拿视图的宽度当步长，与循环体的约定失配——只是整图绘制、横向条带、满宽竖条带这些常见用法恰好都不会触发，GL 主路径又掩盖了它，于是一藏就是好几年。

对笔者来说，这类修复最大的收获不是那一行改动，而是再次验证了**必须靠语义根治，不能靠肉眼碰运气**。肉眼对比截图可以作为触发点，但如果讲不清楚这个偏移、这个宽度在目标平台上意味着什么，修复就永远是凑出来的。审查这类问题的办法也很朴素：把代码里每一处关于坐标和寻址的约定逐条列出来，对照当前管线逐一验证——同函数、同文件、不同后端的相邻实现，都是现成的参照。约定一旦失配，几乎总有一个是错的。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
