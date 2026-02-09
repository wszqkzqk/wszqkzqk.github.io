---
layout:       post
title:        PvZ-Portable：修复《Zombies On Your Lawn》MV 的随机背景贴图错误
subtitle:     从资源加载策略到 OpenGL 纹理重建：一个跨越三层逻辑的蝴蝶效应 Debug 实录
date:         2026-02-09
author:       wszqkzqk
header-img:   img/games/bg-pvz-portable.webp
catalog:      true
tags:         C++ OpenGL 跨平台 游戏移植 开源软件 开源游戏
---

## 引言

在 [PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable) 项目中，曾经存在一个令人摸不着头脑的 Bug：

当玩家播放《Zombies On Your Lawn》MV（即主题曲/通关字幕/制作人员表）时，画面的背景图即开始出现混乱与错位——屋顶的背景变成了草地，白天的变成了黑夜，甚至出现花屏。更诡异的是，一旦播放过这个 MV，即使退回到主菜单重新开始正常游戏，游戏里的关卡背景也会全部错乱。如果不播放 MV，一切正常。

这个 Bug 表现出极强的随机性，背景图似乎在这个过程中被随机交换了内存。

经过漫长的排查，笔者终于在近日根治了这个问题（Commit [f83ad81](https://github.com/wszqkzqk/PvZ-Portable/commit/f83ad81e5637921eb24c714230b7cf25fb28d4c0)）。这远远比看上去的更复杂，是一个跨越了资源管理、渲染状态机和底层 OpenGL 接口实现的连锁反应。

## 抽丝剥茧：排查之路

### 第一步：确认怀疑对象——SharedImageRef

首先，最可疑的线索是：**为什么 MV 出错会污染到正常游戏？**

PvZ 的 Credits MV 实际上是一个名为 `Credits_Main` 的 Reanim（骨骼动画）序列。通过研读 `CreditScreen.cpp`，笔者发现它加载背景图的方式与常规游戏不同。

在常规游戏中，背景图通过 `IMAGE_BACKGROUND1` 等 ID 直接加载。而在 Credits 动画定义中，背景引用的是名为 `IMAGE_REANIM_BACKGROUND1` 的资源。

在 `SexyAppFramework` 的资源管理器中，存在一个 `SharedImageMap` 机制。它会将文件路径标准化为大写作为 Key。笔者追踪发现，尽管 ID 不同，但 `IMAGE_REANIM_BACKGROUND1` 和 `IMAGE_BACKGROUND1` 指向的路径完全一致。

这意味着：**两者在内存中共享同一个 `GLImage` 对象。**

这就是污染的源头：Credits 动画逻辑修改了这个共享的 Image 对象，导致后续所有复用该对象的场景全都中毒。

### 第二步：寻找触发器——神秘的标志位

既然对象是共享的，为什么只有 Credits MV 会导致它出问题？

笔者进一步深入 `Definition.cpp`，这是处理 Reanim 定义加载的地方。原版引擎有一个回退机制：当 Reanim 定义引用一张图片时，它会尝试在多个子目录下寻找。

当通过这个 fallback 路径加载图片时，代码多做了一件事：

```cpp
// Definition.cpp
if (DefinitionLoadImage(...)) {
    // ...
    TodMarkImageForSanding(aImage); // <--- 关键点！
}
```

`TodMarkImageForSanding` 会给图片加上一个标志位：`RENDERIMAGEFLAG_SANDING` (0x1000)。这是原版用于处理纹理边缘半透明像素混合的一个特殊标记。

**真相逐渐浮出水面**：
1.  正常进入游戏时，背景图是作为普通资源加载的，**没有** Sanding 标志。
2.  进入 Credits 时，动画系统重新获取这个共享图片对象，并通过 fallback 路径给它**强行加上了** Sanding 标志。

### 第三步：连锁反应——不必要的纹理重建

有了标志位又如何？为何会导致贴图变花？

视角转到底层渲染器 `GLInterface.cpp`。每次绘制图片前，引擎都会调用 `CheckCreateTextures` 检查纹理状态。

```cpp
// GLInterface.cpp
void TextureData::CheckCreateTextures(MemoryImage *theImage)
{
    // 检查每一项属性是否改变，如果改变则重建纹理
    if (mPixelFormat == PixelFormat_Unknown || 
        theImage->mWidth != mWidth || 
        // ...
        theImage->mRenderFlags != mImageFlags) // <--- 灾难发生的地方
    {
        CreateTextures(theImage);
    }
}
```

在播放 Credits 时，动画每一帧都会调用 `TodSandImageIfNeeded`，这个函数会做完图像处理后**清除** `mRenderFlags` 中的 Sanding 标志。

于是出现了：
1.  图片原本被打上了 Sanding 标 (Flags = 0x1000)。
2.  底层纹理创建时记录了 `mImageFlags = 0x1000`。
3.  绘制代码清除了图片对象上的 Sanding 标 (mRenderFlags 变为 0)。
4.  `CheckCreateTextures` 发现 `theImage->mRenderFlags (0) != mImageFlags (0x1000)`。
5.  **判定纹理需要重建！**

引擎误以为图片属性变了，于是销毁现有的 GPU 纹理，试图从内存中重新读取数据并上传。

### 第四步：致命一击——破碎的 RecoverBits

纹理重建本应只是性能损耗，不该导致画面错误。除非……重建过程本身就是坏的。

当纹理重建发生时，如果原始的内存数据（mBits）已经被释放（为了节省内存，上传 GPU 后通常会释放 CPU 端的 mBits），引擎会调用 `RecoverBits` 从 GPU 显存中把像素读回来。

笔者检查了 `RecoverBits` 的实现，瞬间倒吸一口凉气。

PvZ 的背景图很大（通常是 1400x600），会被切割成多个 64x64 的小块纹理（Texture Piece）存储。`RecoverBits` 的逻辑是遍历这些小块，用 `glGetTexImage` 读回数据。

但这部分的实现存在在一个低级失误：

```cpp
// 修复前的代码
for (int aPieceRow = 0; ... ) {
    for (int aPieceCol = ... ) {
        // ... 绑定当前块的纹理 ...
        
        // 灾难现场：直接写入到 GetBits() 起始位置，没有加偏移量！
        glGetTexImage(GL_TEXTURE_2D, 0, GL_BGRA, ..., theImage->GetBits());
    }
}
```

**它每次读取纹理块时，都写入到了缓冲区的开头！**

这意味着，对于那一千多个纹理小块，每一个块的数据都会覆盖掉前一个块。最终，整个 1400x600 的背景图缓冲区里，只有最后那 64x64 像素的数据是对的（但也仅仅是位置在内存开头），而缓冲区其余绝大部分空间，都是**未初始化的堆内存垃圾**。

这些堆内存垃圾里有什么？恰好可能有之前释放掉的其他背景图的残留数据、或是完全随机的字节。这就是为什么我们能在白天看到黑夜的残影，在屋顶看到草地的碎片——我们实际上是在看内存碎片的万花筒。

## 修复

整个 Bug 的链条现在已经清晰：

1.  **触发**：Credits 动画通过特殊路径加载背景，给共享图片加上了 `Sanding` 标志。
2.  **传导**：绘制逻辑清除了标志，导致底层 `GLInterface` 判定标志位不一致，触发**纹理重建**。
3.  **爆发**：纹理重建调用了有 Bug 的 `RecoverBits`，导致从 GPU 读回的数据互相覆盖，大部分沦为随机内存垃圾。
4.  **持久化**：这份损坏的数据被重新上传到 GPU，并永久替换了那个共享的 Image 对象。

修复工作分两步进行（[查看 Commit](https://github.com/wszqkzqk/PvZ-Portable/commit/f83ad81e5637921eb24c714230b7cf25fb28d4c0)）：

1.  **修复 `RecoverBits`**：
    这是根本性的修复。笔者重写了读取逻辑，为每个纹理块分配临时缓冲，读取后使用 `memcpy` 将其逐行拷贝到大图缓冲区正确的 `(offx, offy)` 坐标处。不管是什么平台处理上下文丢失，正确的显存回读都是必须的。

2.  **修复标志位检测**：
    在 `CheckCreateTextures` 中引入掩码机制。`Sanding` 这种只影响一次性预处理的瞬态标志，不应作为判断纹理是否需要重建的依据。我们忽略这些无关标志的变动，从而彻底避免了不必要的纹理重建开销。

```cpp
// GLInterface.h
// 排除瞬态标志，只检查影响纹理格式的位
RenderImageFlag_TextureMask = 0x000F 

// GLInterface.cpp
if ((theImage->mRenderFlags & RenderImageFlag_TextureMask) != mImageFlags)
    CreateTextures(theImage);
```

至此，这个困扰笔者已久的幽灵 Bug 终于被彻底消灭。这也再次提醒了我们：在实现复杂的代码时，对于每一行看似冗余的标志位操作和每一个底层的数据搬运函数，都必须保持十分的警惕。

## 结语

事实上，笔者本人之前一直被困在 MV 逻辑和资源加载的表象中，始终无法突破。直到笔者将相关的详细描述、表现和怀疑点传递给 **GitHub Copilot** 中的 **Claude Opus 4.6** 模型，在 **Agent 连续运行了两个小时**之后，才终于得以拨云见日。

此前，笔者也尝试过使用 Gemini 3.0 Pro, GPT 5.2 Codex, Claude Opus 4.5 等模型，但均未能成功定位问题。唯有 Claude Opus 4.6 通过调用大量的 Subagent，发掘了相当完整的上下文，逐步理清了思路，最终才找到了问题的根源。
