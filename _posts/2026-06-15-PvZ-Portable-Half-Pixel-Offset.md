---
layout:       post
title:        PvZ-Portable：主菜单左下角的缝隙——追踪一个被遗漏的 D3DX7 半像素偏移
subtitle:     在坐标系迁移三个月后，Reanimator 矩阵里还藏着一个制造像素级错位的 -0.5f
header-img:   img/games/bg-pvz-portable.webp
date:         2026-06-15
author:       wszqkzqk
catalog:      true
tags:         OpenGL 游戏移植 图形渲染 开源软件 开源游戏 PvZ-Portable
---

## 引言

在 [PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable) 的移植过程中，笔者大部分精力都花在大块头的重构上：渲染后端切到 OpenGL ES 2.0、音频系统重写、跨平台输入适配。这些改动虽然动静大，但好处是错了立刻能发现。真正烦人的是那些只错一个像素、只在特定画面、特定角度才露出马脚的遗留问题。

此前，社区用户在 [Issue #284](https://github.com/wszqkzqk/PvZ-Portable/issues/284) 里报告了一个非常奇怪的 Bug：

> 主菜单左下角的草有细小的视觉问题。与原版不一致（有细小的缝隙）。

配图里的缝隙细到不认真看几乎会忽略。但既然被提出来了，就得查清楚。排查过程不算复杂，最后定位到的根因却很有代表性：一个从 D3DX7 时代遗留下来的 `-0.5f` 平移偏移，在年初的坐标系统一清理中被漏掉了。本文记录这次像素级 bug 的追踪与修复。

## 现象：一张差点搞反顺序的对比图

peashooter2 提交 Issue 时附了两张截图，一张原版、一张 PvZ-Portable。问题出在左下角草丛边缘：原版两片草皮的贴图严丝合缝，而 PvZ-Portable 里出现了一道约 1 像素的亮线。

这件事本身不大，但它说明了这类像素级视觉回归的一个特点：**连报告者自己都很难一眼分清哪个是对的**。毕竟草丛边缘的 1 像素缝隙，在截图压缩、显示器差异、甚至观看角度不同的情况下，都可能被误判。

## 背景：D3DX7 的半像素偏移是从哪来的

要理解这个 `-0.5f`，得先回到今年初的一次坐标系清理。

PvZ-Portable 的图形栈是从 SexyAppFramework 继承而来，原版基于 D3DX7/Direct3D。Direct3D 9 及更早版本里，屏幕像素中心位于整数坐标的 `(0.5, 0.5)` 处，而纹理采样通常按 texel 中心对齐。很多旧引擎为了把逻辑坐标（整数像素左上角）映射到 D3D 的像素中心，会在顶点或变换矩阵里手动减去 `0.5f`。

今年初，笔者在把渲染管线统一迁移到 OpenGL ES 2.0 时，提交了 [eb6526a](https://github.com/wszqkzqk/PvZ-Portable/commit/eb6526a3625985205cb982632cc68a5532492d40)“Fix: normalize coordinate mapping and remove D3DX7 legacy offsets”。那次改动做了三件事：

1. 正交投影矩阵的范围从 `(width - 1, height - 1)` 改为 `(width, height)`，让逻辑视口覆盖完整像素范围；
2. 在 `TextureData::Blt`、`TextureData::BltTransformed`、`GLInterface::FillRect` 里移除了手动 `-0.5f` 的顶点偏移；
3. 简化了 `BltTransformed` 里为了兼容旧坐标系而引入的 `pixelcorrect` 变量。

那次提交之后，大部分由半像素偏移引起的错位都消失了。但显然，清理并不彻底。

## 根因：Reanimator 矩阵里的漏网之鱼

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

## 修复与验证

修复本身只有一行：

```diff
- SexyMatrix3Translation(aMatrix, aTrackInstance->mShakeX + g->mTransX - 0.5f, aTrackInstance->mShakeY + g->mTransY - 0.5f);
+ SexyMatrix3Translation(aMatrix, aTrackInstance->mShakeX + g->mTransX, aTrackInstance->mShakeY + g->mTransY);
```

对应的提交是 [4f80f04](https://github.com/wszqkzqk/PvZ-Portable/commit/4f80f0469ef800a42b618dc5efaec927243e71cf)。

验证阶段，笔者在本地重新截图对比：修复前左下角草丛有明显亮缝，修复后缝隙消失，与原版一致。peashooter2 重新确认后也表示问题解决。那场截图顺序乌龙反而让笔者更确信：对于这种像素级差异，必须建立明确的“修复前 / 修复后 / 原版”三组对照，否则连当事人都会看混。

## 还有另一个 -0.5f

在排查过程中，笔者注意到 `Reanimator.cpp` 里还有一处 `-0.5f` 没有动：

```cpp
// GetTrackMatrix
SexyMatrix3Translation(theMatrix, aTrackInstance->mShakeX - 0.5f, aTrackInstance->mShakeY - 0.5f);
```

这个函数用于获取动画轨道的当前变换矩阵，主要供游戏逻辑查询（例如判断某个动画部件的屏幕位置，用于点击检测或特效挂载）。它并不直接参与绘制，因此没有引发可见的视觉问题。是否需要同步移除，取决于后续逻辑层是否也按照 OpenGL 坐标系来理解矩阵结果。目前笔者选择保持原样，因为贸然改动可能会影响点击判定；如果未来发现逻辑层坐标也有偏差，再统一处理会更安全。

## 结语

这个 Bug 的修复只有一行代码，却集中体现了旧引擎移植到现代图形 API 时常见的一类陷阱：**坐标约定不一致导致的半像素偏移**。

D3DX7 时代的手动 `0.5f` 修正在当年是正确的，因为那是 Direct3D 像素中心的定义方式。但当渲染后端换成 OpenGL ES 2.0 后，同样的偏移就变成了错误。年初的大规模清理没有覆盖到 Reanimator 的绘制路径，原因在于 PvZ-Portable 同时支持 Atlas 和非 Atlas 两种绘制模式，而问题只出现在后者，测试时容易遗漏。

对笔者来说，这次修复的最大收获不是这一行改动，而是再次验证了**视觉回归必须靠坐标语义根治**。肉眼对比截图可以作为触发点，但如果不能讲清楚“这个偏移在目标平台上意味着什么”，修复就永远是碰运气。把 D3DX7 的遗产逐条清理干净，才能让 PvZ-Portable 在不同平台、不同分辨率下都稳定地像素级复刻原版。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
