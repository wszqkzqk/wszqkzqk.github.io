---
layout:       post
title:        PvZ-Portable：用顶点上传队列降低渲染开销
subtitle:     将交错的小块上传改为整组一次提交
header-img:   img/games/pvz-portable/bg-pvz-portable.webp
date:         2026-10-26
author:       wszqkzqk
catalog:      true
tags:         性能优化 OpenGL 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

PvZ-Portable 最近完成了一项渲染提交优化：将许多次小规模顶点上传合并成整组上传，同时保留原有的 draw call、图元顺序和画面输出。它适合处理这样一种负载：每个图元的顶点很少，绘制十分频繁，所有图元又共用同一块 VBO。

方案部分来自社区贡献者 [mindorigin150](https://github.com/mindorigin150) 的 PR [#510](https://github.com/wszqkzqk/PvZ-Portable/pull/510)。笔者在 PR [#511](https://github.com/wszqkzqk/PvZ-Portable/pull/511) 中将其与 GL 状态去重整合进现有渲染路径，并用真实对局回放做了验证。

这项改造中有三个值得展开的问题：频繁重写 VBO 为什么会增加开销，合并上传后怎样用原来的方式执行每一条 draw，以及延迟绘制以后如何保证状态和资源顺序仍然正确。

## 旧路径：上传与绘制反复交替

PvZ-Portable 的 GLES2 后端共用一个 VBO。旧代码每收集完一个图元，都会在 `GfxEnd()` 中立即上传并绘制（`src/SexyAppFramework/graphics/GLInterface.cpp`）：

```cpp
glBindBuffer(GL_ARRAY_BUFFER, gVbo);
glBufferData(GL_ARRAY_BUFFER,
	sizeof(GLVertex) * gNumVertices, gVertices.data(), GL_DYNAMIC_DRAW);
glDrawArrays(gVertexMode, 0, gNumVertices);

gNumVertices = 0;
```

于是，一帧中的提交过程是：

```text
上传 A → 绘制 A → 上传 B → 绘制 B → 上传 C → 绘制 C → ……
```

`glBufferData` 会重新指定缓冲区的数据存储。每次调用的数据量虽然不大，API 与驱动处理的固定成本却会随着图元数量累积。

这里还有一层资源依赖。绘制 A 时，GPU 可能仍在读取 VBO 中 A 的顶点；紧接着上传 B，又要改写同一块缓冲区。驱动必须同时保证 A 读到旧数据、B 得到新数据，可能等待已有工作完成，也可能为缓冲区更换底层存储。具体策略取决于驱动，但这段依赖管理会出现在每一次上传与绘制的交界处。

如果能先上传 A、B、C 共用的数据，再连续执行三次 draw，上传之间就不再夹着 draw，draw 之间也不再有 VBO 重写。这正是上传队列要改变的提交顺序。

#510 的隔离探针为这一判断提供了直接证据。在每帧 120 次 draw 的匹配对照中，上传顶点均为 11,520 字节，上传调用从 120 次降为 1 次。对照组保留交错上传并执行相同的额外场景遍历，只有整组上传获得明显收益，确认提交顺序是关键变量。

## 合并上传，保留每一条 draw

假设 A、B、C 分别有 4、4、6 个顶点。旧路径每次只把一个图元放到 VBO 开头：

```text
上传 4 个顶点 → glDrawArrays(modeA, 0, 4)
上传 4 个顶点 → glDrawArrays(modeB, 0, 4)
上传 6 个顶点 → glDrawArrays(modeC, 0, 6)
```

新路径先在 CPU 侧连续排列这些顶点：

```text
[A 的 4 个顶点 | B 的 4 个顶点 | C 的 6 个顶点]
```

整组上传一次后，仍然执行三条 draw，只是起点换成了各自在共享缓冲区中的偏移：

```cpp
glDrawArrays(modeA, 0, 4);
glDrawArrays(modeB, 4, 4);
glDrawArrays(modeC, 8, 6);
```

draw 仍然是 3 次，顶点总数仍然是 14 个，顺序仍然是 A、B、C。减少的是 `glBufferData` 调用和 VBO 重写次数。

### 用命令记录顶点范围

实现时，`GfxBegin()` 在图元开始前记录当前顶点数量，`GfxEnd()` 将图元模式、起点、数量和绘制状态保存为一条命令：

```cpp
struct GfxDrawCommand
{
	GLenum mode;
	GLint first;
	GLsizei count;
	GfxDrawState state;
};
```

入队的核心操作如下：

```cpp
gDrawCommands.push_back({
	gVertexMode,
	gPrimitiveStart,
	gNumVertices - gPrimitiveStart,
	gDrawState
});
```

`gNumVertices` 不再随每个图元清零，而要等到整组提交之后。这样，队列中的 `first` 和 `count` 才能一直对应同一份顶点数据。

`GfxSubmit()` 负责真正访问 GL：先上传整组顶点，再逐条取出命令，恢复状态并绘制。

```cpp
static void GfxSubmit()
{
	if (gDrawCommands.empty()) return;

	glBindBuffer(GL_ARRAY_BUFFER, gVbo);
	glBufferData(GL_ARRAY_BUFFER,
		sizeof(GLVertex) * gNumVertices, gVertices.data(), GL_DYNAMIC_DRAW);
	glActiveTexture(GL_TEXTURE0);
	for (const auto& command : gDrawCommands)
	{
		GfxApplyState(command.state);
		glDrawArrays(command.mode, command.first, command.count);
	}
	gDrawCommands.clear();
	gNumVertices = 0;
}
```

上层仍然按原顺序调用 `GfxBegin`、`GfxAddVertices` 和 `GfxEnd`，场景只需遍历一次。变化集中在渲染后端的记录与提交边界上。

## 延迟绘制必须保存状态

旧路径中，A 绘制完成后，B 才能修改纹理、混合因子和 uniform。新路径会先记录 A、B、C，再统一绘制；如果执行 A 时直接读取当前全局状态，看到的可能已经是 C 的设置。

因此，每条命令都携带一份 `GfxDrawState` 快照，包含纹理、混合因子、过滤方式、UV 范围等着色状态。记录阶段的 `SetBlendFunc`、`GfxBindTexture` 只更新这份 CPU 侧状态；执行阶段的 `GfxApplyState(command.state)` 再将它应用到 GL。

此前的混合模式合批可以作为快照内容的一个例子。若源 RGB 和 Alpha 分别为 $C_s$、$A_s$，普通透明将着色器输出改为 $(A_sC_s,A_s)$，加法混合则输出 $(A_sC_s,0)$，两者便可共用 `(GL_ONE, GL_ONE_MINUS_SRC_ALPHA)`，并保持原来的 RGB 混合结果。`mixedBlend` 决定是否启用这套着色器逻辑，也必须随命令保存，否则后续批次会改变已排队图元的混合方式。

当前实现还维护了另一份 `gAppliedState`，记录上次真正应用到 GL 的状态。`gDrawState` 服务于命令录制，`gAppliedState` 用于提交时跳过没有变化的状态设置，两者承担不同的职责。

## 在这些边界前必须提交队列

命令入队以后，上层代码仍可能修改队列所依赖的资源。以下操作发生前，需要调用 `GfxFlush()`，先完成已经排队的绘制。

| 边界 | 需要提前提交的原因 |
|---|---|
| 顶点缓冲区容量不足 | 后续顶点会覆盖旧命令引用的区间。 |
| 创建、更新或删除纹理 | 已排队的命令需要读取记录时所对应的纹理内容与对象。 |
| `RecoverBits` 回读纹理 | 回读过程会绑定临时 FBO；挂起的屏幕绘制要先完成。 |
| 更新 viewport 或重新初始化 | 旧命令依赖变更前的绘制区域、投影和 uniform。 |
| 交换窗口缓冲区 | 当前帧的所有命令都要在交换前发出。 |

以容量边界为例，`GfxEnsureSpace()` 在发现空间不足时依次执行 `GfxEnd()`、`GfxSubmit()` 和 `GfxBegin()`。这里的 `GfxSubmit()` 将旧顶点送入 VBO 并执行对应命令，随后才能安全地复用 CPU 侧数组。

这些边界可以统一成一条审查规则：**后续操作只要会改变旧命令依赖的顶点、纹理、帧缓冲区或全局状态，就先用 `GfxFlush()` 结束当前组。** 对延迟渲染而言，这条规则与命令结构本身同样重要。

## 真实对局中的验证

笔者在 #511 中使用项目的确定性回放评估了最终整合版本。基线为主分支 `3838ec21`，整合版为 `a46a1e88`，两边都使用 O2 `RelWithDebInfo`，运行于 Ryzen 7 5800H、Mesa/Gallium、Linux Wayland 环境。测试负载为同一份无尽模式回放 `pvzp-20261002-141740.dmo`，前后版本交替运行 3 次，每次只运行一个游戏进程。

| 指标 | 基线均值 | 整合版均值 | 平均配对降幅 | 95% 配对 t 置信区间 |
|---|---:|---:|---:|---:|
| 进程 CPU 时间 | 181.130 s | 122.123 s | **32.576%** | [28.451%, 36.700%] |
| 绘制/提交耗时 | 64.381 s | 44.751 s | **30.486%** | [26.290%, 34.682%] |

每次性能回放都完成了 38,456 次逻辑更新，前后每轮 draw count 只差约 1 次。普通回放还比较了最终 RGB hash，结果一致；ASan/UBSan 和 LOW_MEMORY 回放也通过了。

这组数据对应“上传队列 + GL 状态去重”的最终整合版本，用来评价实际合入代码在真实游戏负载中的整体表现。在垂直同步或帧率上限生效时，进程 CPU 与绘制/提交耗时比 FPS 更能反映渲染余量。#510 的普通客户端前后均约 100 FPS，GPU 绘制到交换的间隔却显著缩短，正体现了这一点。

### 低端设备上的高压场景

实际设备体验进一步体现了这些渲染余量的价值。一台搭载骁龙 450（Cortex-A53，1.8 GHz）的低端设备，在优化之前，运行普通关卡和一般场景时原本就比较流畅，无尽模式进入高密度、饱和出怪阶段后，大量僵尸、动画和粒子效果会显著增加提交压力，变得卡顿。**在包含这项优化的版本中，该设备在这样的极限场景下也能流畅运行**。

无尽高压阶段的小图元提交更加密集，上传队列有更多机会合并相邻图元，优化收益也更容易在这类原本吃紧的场景中体现出来。

## 结语

这套方法适用于顶点量小、绘制频繁、共享 VBO 被反复改写的 2D 渲染器。它的核心步骤很直接：连续收集顶点，用 `first`、`count` 保留每条 draw 的读取范围，整组上传后按原顺序绘制。

将这套思路用于其他渲染器时，还需要同步补上两项设计：命令级状态快照，以及资源和上下文变更前的冲刷边界。它们决定了提交顺序改变之后，画面能否保持原样。

每个冲刷边界之间能累积的图元数量会直接影响实际收益，频繁的资源或上下文变更会缩短批次。评估这类改造时，应结合实际场景统计有效批量，并检查画面等价性。

## 版权与说明

PvZ-Portable 严格遵守版权协议。游戏 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。研究或使用此项目时，**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies)购买）。你需要从正版游戏中提取以下文件，放到 PvZ-Portable 的程序所在目录：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
