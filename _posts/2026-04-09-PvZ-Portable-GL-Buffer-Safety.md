---
layout:       post
title:        PvZ-Portable：渲染层缓冲区的安全重构与边界保护
subtitle:     修复 OpenGL 顶点缓冲中的越界风险、内存泄漏与未定义行为
date:         2026-04-09
author:       wszqkzqk
header-img:   img/games/bg-pvz-portable.webp
catalog:      true
tags:         C++ OpenGL SDL2 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

此前，笔者集中修复了渲染子系统中一类隐藏很深的底层缺陷：OpenGL 顶点缓冲中的越界风险、不匹配的内存释放，以及缺失的边界防护。这些问题与游戏逻辑无关，却在复杂特效或高负载场景下有直接触发崩溃的风险。

本文将详细记录这次对 PvZ-Portable 渲染层的安全重构过程，包括裸数组的 RAII 化、顶点追加时序的修正、粒子特效裁剪阶段的溢出保护，以及一个长期潜伏的 `delete/delete[]` 不匹配问题。

## 旧顶点缓冲区的隐患

PvZ-Portable 的 OpenGL 渲染后端采用批量提交（batching）策略：将尽可能多的几何体合并到同一个 draw call 中，再统一调用 `glDrawArrays`。为了暂存这些顶点数据，引擎维护了一个全局的静态缓冲区 `gVertices`。在重构之前，它的实现非常直接——一块通过 `new[]` 分配的固定大小裸数组：

```cpp
static GLVertex* gVertices;

// 初始化
gVertices = new GLVertex[MAX_VERTICES]();
```

所有向 GPU 提交顶点的操作都围绕这个数组进行。`GfxAddVertices` 负责将新的顶点 `memcpy` 到 `gVertices + gNumVertices` 的位置，然后累加计数器。旧代码的逻辑看起来大致是这样：

```cpp
static void GfxAddVertices(const GLVertex *arr, int arrCount)
{
    if (gVertexMode == (GLenum)-1) return;

    memcpy(gVertices + gNumVertices, arr, sizeof(GLVertex) * arrCount);
    gNumVertices += arrCount;

    if (gNumVertices >= MAX_VERTICES)
    {
        GLenum oldMode = gVertexMode;
        GfxEnd();      // 提交当前批次
        GfxBegin(oldMode); // 开始新批次
    }
}
```

这段代码的问题在于**边界检查的时序**。`memcpy` 发生在容量判定之前，这意味着如果某一次调用传入的顶点数量直接超过了数组剩余容量，数据会在边界检查触发 flush 之前就写到了数组末尾之外。这是明确的未定义行为，可能导致直接崩溃。

此外，`gVertices` 作为全局裸指针，其生命周期完全依赖 `GLInterface` 的构造函数和析构函数手动管理。`new[]` 与 `delete[]` 虽然配对正确，但整个设计没有任何自动边界保护或异常安全保证。

## 向 `std::vector` 重构与追加前 flush

修复的第一步是彻底改造顶点缓冲的内存模型。笔者将 `gVertices` 从裸指针替换为 `std::vector<GLVertex>`，利用 C++ 标准容器的自动扩容和 RAII 语义来消除手动分配风险：

```cpp
static std::vector<GLVertex> gVertices;
```

如果只是简单地把 `memcpy` 改成 `push_back`，时序问题依然存在。真正的关键是**把边界检查从追加后移到追加前**。为此，笔者引入了一个独立的辅助函数 `GfxFlushIfOverBudget()`：

```cpp
static void GfxFlushIfOverBudget()
{
    if (gVertexMode == (GLenum)-1 || gNumVertices < MAX_VERTICES)
        return;

    GLenum oldMode = gVertexMode;
    GfxEnd();
    GfxBegin(oldMode);
}
```

这个函数在每次追加操作完成后被调用，用于判断当前累积的顶点数是否已经达到了单批次提交的上限。如果 `gNumVertices` 已经触及 `MAX_VERTICES`，它会立即强制提交当前批次，清空缓冲区，然后开始新的批次。结合 `std::vector` 的使用，新的 `GfxAddVertices` 变成了下面这样：

```cpp
static void GfxAddVertices(const GLVertex *arr, int arrCount)
{
    if (gVertexMode == (GLenum)-1) return;
    if (arrCount <= 0) return;

    const int oldCount = gNumVertices;
    gNumVertices += arrCount;
    gVertices.resize(gNumVertices);
    memcpy(gVertices.data() + oldCount, arr, sizeof(GLVertex) * arrCount);

    GfxFlushIfOverBudget();
}
```

`resize(gNumVertices)` 会在 `std::vector` 需要扩容时自动重新分配内存，并安全地迁移已有数据，这意味着 `memcpy` 的目标地址 `gVertices.data() + oldCount` 始终是合法的——无论 `gNumVertices` 增长到多大，都不会再出现裸数组时代的写越界。

随之而来的是 `MAX_VERTICES` 的语义转变：在裸数组时代，它是防止缓冲区溢出的硬边界；而在使用 `std::vector` 之后，它变成了**单批次向 GPU 提交顶点的上限**。`GfxFlushIfOverBudget` 保障的是渲染性能与驱动兼容性，而不是防止内存损坏。也就是说，即使某次追加后 `gNumVertices` 暂时超过了 `MAX_VERTICES`，数据本身仍然是安全地存放在已扩容的 `std::vector` 中的，唯一的后果是 `GfxEnd()` 被触发时，这次向 GPU 提交的 draw call 可能会略微大于 `MAX_VERTICES` 的设定值。

`GfxEnd()` 本身也得到了加固：

```cpp
static void GfxEnd()
{
    if (gVertexMode == (GLenum)-1) return;

    if (gNumVertices > 0)
    {
        glBindBuffer(GL_ARRAY_BUFFER, gVbo);
        glBufferData(GL_ARRAY_BUFFER, sizeof(GLVertex) * gNumVertices,
                     gVertices.data(), GL_DYNAMIC_DRAW);

        // 设置 vertex attributes ...
        glDrawArrays(gVertexMode, 0, gNumVertices);
    }

    gVertexMode = (GLenum)-1;
    gNumVertices = 0;
    gVertices.clear();
}
```

绘制命令现在只在 `gNumVertices > 0` 时才执行，避免了对空缓冲区发起无意义的 `glDrawArrays`。批次结束后 `gVertices.clear()` 会保留已分配的容量（因为 `clear()` 不释放内存），这样下一帧的追加通常不需要重新进行堆分配。

在 `GLInterface` 的析构函数中，旧代码需要显式 `delete[] gVertices`，现在这一步也被 `std::vector` 的自动析构所取代，彻底消除了手动内存管理中的泄漏风险。

## 裁剪阶段的溢出保护

顶点缓冲区的主路径安全了，但还有一个侧路径同样危险——`EffectSystem` 中的三角形裁剪与追加逻辑。

`TodTriangleGroup::AddTriangle` 负责接收一个三角形，根据当前的裁剪矩形将其切分为多个子三角形，然后把结果写入 `mVertArray` 数组。这个数组的大小由 `MAX_TRIANGLES` 定义。旧代码在循环内直接写入：

```cpp
int vCount = Tod_clipShape(clipped, aTriRef[i], clipX0, clipX1, clipY0, clipY1);
for (int j = 0; j < vCount - 2; j++)
{
    TriVertex* pVert = mVertArray[mTriangleCount];
    pVert[0].x = clipped[0]->x;
    // ... 填充顶点数据 ...
    mTriangleCount++;
}
```

问题在于，当一个复杂的粒子特效触发裁剪时，单个输入三角形可能被切分成数十个子三角形。如果此时 `mTriangleCount` 已经接近 `MAX_TRIANGLES`，循环内没有任何容量检查，最终一定会写穿 `mVertArray` 的边界。

这一问题只有在 `mVertArray` 接近其容量上限时才会显现，因此之前长期未被发现。修复非常直接：在每次增量前检查容量，若已满则先 `DrawGroup(g)` 提交当前积攒的三角形：

```cpp
for (int j = 0; j < vCount - 2; j++)
{
    if (mTriangleCount == MAX_TRIANGLES)
        DrawGroup(g);

    TriVertex* pVert = mVertArray[mTriangleCount];
    // ... 填充顶点数据 ...
    mTriangleCount++;
}
```

由于这种极端裁剪场景触发概率不高，再加上不同平台内存分配器对越界写入的容忍度不同，这个缺陷在此前并未引起足够注意。但在更严格的运行环境（如特定的 GPU 驱动）下，以及某些无尽模式情形的高压力下，能稳定复现崩溃。

## 隐藏已久的 `delete`/`delete[]` 不匹配

在审查顶点缓冲相关代码时，笔者还注意到了一个与 OpenGL 无关但同样危险的内存管理错误，它藏在 `VertexList` 结构体中。

`VertexList` 是一个小型的动态数组实现，用于临时存放一组 `GLVertex`。它的内部分配逻辑是这样的：

```cpp
void reserve(int theCapacity)
{
    if (theCapacity > mCapacity)
    {
        GLVertex* aNewList = new GLVertex[theCapacity];
        memcpy(aNewList, mVerts, mSize * sizeof(mVerts[0]));
        if (mVerts != mStackVerts)
            delete mVerts;

        mVerts = aNewList;
    }
}
```

以及析构函数：

```cpp
~VertexList()
{
    if (mVerts != mStackVerts)
        delete mVerts;
}
```

这里的问题非常经典：**使用了 `new[]` 分配数组，却用 `delete`（标量删除）来释放**。根据 C++ 标准，这是未定义行为。虽然标准的 `delete` 和 `delete[]` 在简单类型如 `GLVertex` 上可能不会立刻崩溃，但它们在底层可能调用不同的释放逻辑：

- `new[]` 通常会在返回的指针前面额外存储数组元素个数；
- `delete` 不会读取这个前缀，只会释放单个对象大小的内存；
- 这会导致分配的内存和释放的内存大小不一致，逐渐腐蚀堆的元数据。

在短生命周期对象上，这个错误可能数年都不被察觉。但当引擎运行时间变长、对象分配变得非常频繁时，堆元数据的损坏会在完全无关的代码位置引发难以解释的崩溃。修复只需要把两处 `delete mVerts;` 改成 `delete[] mVerts;`。**未定义行为不会因为当前平台暂未崩溃而变得安全**。不同的内存分配器实现对这种不匹配的敏感程度各不相同，在一种环境下稳定的程序，换到另一种环境下就可能出现难以追踪的崩溃。

## 结语

这次对渲染层缓冲区安全的集中修复，本质上是对底层代码中遗漏边界和生命周期管理的系统补齐。这些缺陷在过去可能因为触发概率低、触发场景少而没有立刻暴露，但它们始终是潜在的风险点。

PvZ-Portable 的跨平台工作还在持续，这类底层基础设施的健壮化也将是后续的重点方向。

## ⚠️ 版权与说明

**重要：本项目仅包含代码引擎，不包含任何游戏素材！**

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中。

*   `main.pak`
*   `properties/` 目录

本项目的源代码以 [**LGPL-3.0-or-later**](https://www.gnu.org/licenses/lgpl-3.0.html) 许可证开源，欢迎学习和贡献。
