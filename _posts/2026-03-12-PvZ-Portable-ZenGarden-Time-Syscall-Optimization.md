---
layout:       post
title:        PvZ-Portable：禅境花园性能优化——一次系统调用优化如何揭开 Wine 的性能回归
subtitle:     time(0) 与 localtime() 热路径分析、逐帧缓存优化与 Wine 11.4 性能回归的意外发现
date:         2026-03-12
author:       wszqkzqk
header-img:   img/games/bg-pvz-portable.webp
catalog:      true
tags:         C++ 性能优化 Wine 系统调用 跨平台 开源软件 开源游戏 PvZ-Portable
---

## 引言

在 [PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable) 的开发过程中，笔者遇到了一个诡异的性能问题：将 Wine 从 11.3 升级到 11.4 后，禅境花园的主画面帧率从正常的 100+ FPS 骤降至约 **5 FPS**。而其他所有场景——冒险模式、迷你游戏、商店界面——均流畅如常。

更耐人寻味的是，**笔者最终没有通过 bisect Wine 的代码来找到回归的 commit**，而是通过对程序自身的性能分析与优化，直接揭示了 Wine 的性能回归所在——这或许是一种更有说服力的回归排查方式：当你从程序层面就能消除整类系统调用的热路径开销时，回归的根因自然就呼之欲出了。

本文将完整记录这次从发现问题到彻底解决的全过程，包括性能分析方法论、根因定位、优化实现细节，以及它对 Wine 性能回归理解的意义。

## 问题现象

### 症状

在 Wine 11.4 下打开禅境花园：

- **主花园场景（约 30 株植物）**：帧率约 5 FPS，明显卡顿
- **蘑菇花园 / 水族花园（仅数株植物）**：流畅，未触发瓶颈
- **智慧之树**：正常
- **购买界面 / 设置 / 其他弹窗**：正常
- **冒险模式等一切非禅境花园场景**：正常

回退到 Wine 11.3，所有场景全部正常。

初看之下，似乎只有主花园出了问题，蘑菇花园和水族花园没事。但后续分析表明，三者的逻辑其实没有本质不同，只是**植物数量的差异**——主花园满载约 30 株盆栽，蘑菇花园和水族花园各只有数株。每帧系统调用次数与植物数量成正比，只有当植物数量足够多、累积开销超过单帧的时间预算时，卡顿才会显现。换句话说，蘑菇花园和水族花园只是还没达到单核 CPU 的瓶颈，而非不受影响。

与此同时，笔者也在 Windows 原生环境下做了对照测试，并未观察到对应的异常卡顿；再结合对相关代码路径的检查，可以初步排除这是 PvZ-Portable 自身近期引入的通用性能回归。

### 关键线索

综合以上观察，关键线索逐步浮现：

1. **卡顿程度与植物数量正相关**——30 株满花园严重卡顿，数株植物的子花园流畅，说明瓶颈在逐植物的循环逻辑中
2. **非禅境花园场景完全不受影响**——说明问题不在渲染、音频或框架层面，而在禅境花园特有的时间检查逻辑中
3. **Wine 11.3 → 11.4 引入**——某种系统调用的开销在新版本中显著增长
4. **Windows 原生环境未复现，代码检查也未发现足以解释该退化的近期改动**——说明问题更像是兼容层放大了既有热路径，而不是程序本身突然变慢

## 性能剖析

### 第一轮：定位到 `ZenGardenUpdate()`

首先，笔者在 `Board::Update()` 中插入了基于 `SDL_GetTicks()` 的计时代码，将主循环分段测量：

```cpp
// Board.cpp - 临时性能分析代码
Uint32 tStart = SDL_GetTicks();

// ... Board 常规更新 ...

Uint32 tBeforeZen = SDL_GetTicks();

if (IsZenGardenMode())
    mApp->mZenGarden->ZenGardenUpdate();

Uint32 tAfterZen = SDL_GetTicks();

// 每 50 帧输出一次累积耗时
mProfileFrameCount++;
mProfileAccBoard += (tBeforeZen - tStart);
mProfileAccZen += (tAfterZen - tBeforeZen);
if (mProfileFrameCount >= 50) {
    printf("board=%ums  zen=%ums\n", mProfileAccBoard, mProfileAccZen);
    mProfileFrameCount = mProfileAccBoard = mProfileAccZen = 0;
}
```

结果（30 株植物，50 帧累积）：

| 阶段 | 耗时 |
| :--- | :---: |
| Board 常规更新 | ~2 ms |
| **ZenGardenUpdate()** | **~1050 ms** |

几乎所有时间都消耗在 `ZenGardenUpdate()` 中。

### 第二轮：定位到需求检查与盆栽更新

在 `ZenGardenUpdate()` 内部，逐段添加计时点后，发现两个热点：

```
needs=245ms  potted=775ms  (每 50 帧)
```

| 函数区域 | 50 帧累积耗时 |
| :--- | :---: |
| `UpdatePlantNeeds()`（需求检查循环） | ~245 ms |
| **`PottedPlantUpdate()` 循环** | **~775 ms** |
| 其他（动画、CrazyDave 等） | ~30 ms |

至此，笔者已经知道：**每帧对 30 株植物的遍历循环**是整个瓶颈所在。

### 第三轮：根因——`time(0)` 和 `localtime()` 的灾难性调用

进一步审查这两个热点循环中的代码逻辑后，发现**每株植物每帧**都要调用大量的 `time(0)` 和 `localtime()`：

- `PottedPlantUpdate()` 中直接调用 `time(0)` 获取当前时间，用于检查植物是否需要浇水、施肥、状态是否过期等
- `WasPlantNeedFulfilledToday()` 和 `PlantShouldRefreshNeed()` 同时调用 `time(0)` 和 `localtime()`，用于比较日期
- `WasPlantFertilizedInLastHour()`、`GetPlantsNeed()`、`PlantGetMinutesSinceHappy()`、`IsStinkyHighOnChocolate()`、`PlantHighOnChocolate()`、`ShouldStinkyBeAwake()` 等函数中也各自调用 `time(0)`

经过仔细计数：

> **每帧每株植物约产生 6 次 `time(0)` 调用和 4 次 `localtime()` 调用**

30 株植物意味着每帧约 **180 次 `time(0)` + 120 次 `localtime()`** 系统调用。

在原生 Linux 环境下，这些调用通过 vDSO 机制极为廉价（纳秒级），因此这段代码在 Linux 原生运行时完全不成问题。但在 Wine 环境中，这些调用需要经过 Wine 的 NT → Unix 翻译层。**Wine 11.4 中该翻译层的开销显著增加**，导致每帧约 300 次系统调用的累积开销从可忽略飙升到了约 20 ms——对于 60 FPS 的目标来说，这直接导致了严重的帧率下降。

## 优化方案：逐帧时间缓存

### 核心思路

`time(0)` 返回的是 `time_t`（秒精度）。在同一帧中，无论调用多少次，返回值几乎不会变化（一帧的时间远小于一秒）。因此，完全可以**在每帧入口处缓存一次**，后续所有读取直接使用缓存值。

### 实现

在 `ZenGarden` 类中增加两个成员变量：

```cpp
// ZenGarden.h
class ZenGarden
{
    // ...
    time_t  mNowTime;  // 逐帧缓存的当前时间
    tm      mNowTM;    // 逐帧缓存的当前本地时间结构
};
```

在构造函数、关卡初始化和商店返回时初始化：

```cpp
// ZenGarden.cpp - 构造函数
ZenGarden::ZenGarden()
{
    // ...
    mNowTime = time(0);
    mNowTM = *localtime(&mNowTime);
}
```

在 `ZenGardenUpdate()` 入口处每帧刷新缓存：

```cpp
void ZenGarden::ZenGardenUpdate()
{
    if (mApp->GetDialog(Dialogs::DIALOG_STORE))
        return;

    // 每帧缓存一次 time(0) 和 localtime()，避免重复系统调用
    mNowTime = time(0);
    mNowTM = *localtime(&mNowTime);

    // ... 后续逻辑 ...
}
```

然后，将所有函数中的 `time(0)` 替换为 `mNowTime`，将 `localtime()` 对当前时间的调用替换为 `mNowTM`：

```cpp
// 修改前
bool ZenGarden::WasPlantFertilizedInLastHour(PottedPlant* thePottedPlant)
{
    return static_cast<int64_t>(time(0)) - thePottedPlant->mLastFertilizedTime < 3600;
}

// 修改后
bool ZenGarden::WasPlantFertilizedInLastHour(PottedPlant* thePottedPlant)
{
    return static_cast<int64_t>(mNowTime) - thePottedPlant->mLastFertilizedTime < 3600;
}
```

```cpp
// 修改前
bool ZenGarden::WasPlantNeedFulfilledToday(PottedPlant* thePottedPlant)
{
    time_t aNowTime = time(0);
    int64_t aNow = static_cast<int64_t>(aNowTime);
    if (aNow - thePottedPlant->mLastNeedFulfilledTime < 3600)
        return true;

    time_t aLastNeedFulfilledTime = (time_t)thePottedPlant->mLastNeedFulfilledTime;
    tm aNowTM = *localtime(&aNowTime);
    tm aLastNeedFulfilledTM = *localtime(&aLastNeedFulfilledTime);
    return aNowTM.tm_year <= aLastNeedFulfilledTM.tm_year && aNowTM.tm_yday <= aLastNeedFulfilledTM.tm_yday;
}

// 修改后
bool ZenGarden::WasPlantNeedFulfilledToday(PottedPlant* thePottedPlant)
{
    int64_t aNow = static_cast<int64_t>(mNowTime);
    if (aNow - thePottedPlant->mLastNeedFulfilledTime < 3600)
        return true;

    time_t aLastNeedFulfilledTime = (time_t)thePottedPlant->mLastNeedFulfilledTime;
    tm aLastNeedFulfilledTM = *localtime(&aLastNeedFulfilledTime);
    return mNowTM.tm_year <= aLastNeedFulfilledTM.tm_year && mNowTM.tm_yday <= aLastNeedFulfilledTM.tm_yday;
}
```

注意，对于 **历史时间戳的 `localtime()` 调用**（比如将植物的 `mLastNeedFulfilledTime` 或 `mLastWateredTime` 转换为 `tm` 结构体），由于每株植物的时间戳不同，无法统一缓存，但经性能分析验证这些调用的开销已可忽略不计。

### 用户交互函数的同步优化

除了逐帧更新的热路径，我们还将所有在用户交互时调用的函数（如 `PlantFertilized()`、`PlantWatered()`、`FeedChocolateToPlant()`、`WakeStinky()` 等）中的 `time(0)` 也替换为 `mNowTime`。理由如下：

1. `time(0)` 的精度是**秒级**，在同一帧内无论调用 `time(0)` 还是使用帧开头缓存的 `mNowTime`，结果本质上是一致的
2. 所有交互操作都发生在 `ZenGardenUpdate()` 之后的同一帧中，缓存值与实时值之间的偏差严格小于 1 秒——不可能对秒级精度的时间戳产生任何影响
3. 保持一致的时间源有利于代码可维护性，并避免帧内时间不一致导致的边界情况

### 时间缓存额外刷新点

除了帧循环之外，还有两个场景需要额外刷新时间缓存：

1. **关卡初始化（`ZenGardenInitLevel()`）**：在进入禅境花园时，需要立即有正确的缓存时间来判断植物状态
2. **从商店返回（`OpenStore()` 结束后）**：用户可能在商店中花费了较长时间，返回花园后需要刷新缓存时间

```cpp
void ZenGarden::ZenGardenInitLevel()
{
    mBoard = mApp->mBoard;
    mNowTime = time(0);
    mNowTM = *localtime(&mNowTime);
    // ...
}
```

## 优化效果

应用缓存后，再次运行性能分析：

| 阶段 | 优化前（50 帧） | 优化后（50 帧总计） | 提升 |
| :--- | :---: | :---: | :---: |
| `UpdatePlantNeeds()` | ~245 ms | ~0 ms | **>99%** |
| `PottedPlantUpdate()` 循环 | ~775 ms | ~12 ms | **>98%** |
| **ZenGardenUpdate() 总计** | **~1050 ms** | **~12 ms** | **~90x** |

系统调用从每帧约 **300 次**降至每帧 **2 次**（`time(0)` + `localtime()`），缓存命中率接近 100%。

最终变更仅涉及 **2 个文件、34 行新增、23 行删减**，是一个非常小而精确的补丁。

## 回归分析：为什么没有风险？

将 `time(0)` 替换为缓存值时，一个自然的疑问是：**这是否会改变游戏行为？**

答案是**不会**，原因如下：

### 精度分析

- `time(0)` 返回 `time_t`，精度为**秒**
- 游戏帧率为 100 FPS（逻辑帧率，不是渲染帧率），即每帧 10 ms
- 缓存值与实际值的最大偏差 < 10 ms，远低于 1 秒
- 所有使用 `time(0)` 的地方都是**秒级比较**（如 `< 3600` 表示一小时内、`< 180` 表示三分钟内）

### 时间戳存储

存档中存储的时间戳类型为 `int64_t` 或 `uint32_t`，写入的值同样是秒级的 UNIX 时间戳。使用缓存值写入的结果与直接调用 `time(0)` 完全一致。

### 帧内一致性改善

事实上，使用缓存反而**改善**了行为：在优化前，同一帧内的多次 `time(0)` 调用可能跨越整秒边界，导致帧内不同函数看到不同的时间（对一株植物判断为"今天"，对另一株判断为"明天"）。统一使用缓存值彻底消除了这种帧内时间不一致的边界情况。

## 从程序优化到 Wine 回归发现

这个案例有一个独特之处：**笔者没有通过 bisect Wine 的大量 commit 来定位回归**。

传统的回归排查方式是在 Wine 代码仓库中进行二分查找，最终定位到某个引入性能退化的 commit。这种方式在 Wine 这种庞大的代码库中非常耗时，而且对于细微的性能回归可能难以稳定复现。

笔者采用了一种不同的路径：

1. **从程序表现入手**——精确定位到只有禅境花园主画面受影响
2. **从热路径分析入手**——逐层缩小范围，从 `Board::Update()` → `ZenGardenUpdate()` → 需求检查/盆栽更新循环
3. **从系统调用模式入手**——发现每帧约 300 次的 `time(0)` / `localtime()` 调用
4. **从优化效果反推**——在缓存了系统调用后，即使在 Wine 11.4 下，禅境花园也恢复了满帧运行

这个优化的结果**直接证明了 Wine 11.4 中 `time(0)` 和 `localtime()` 相关系统调用的翻译开销显著增加**。我们基本可以推断：**Wine 11.4 在时间相关系统调用的 NT → Unix 翻译层中存在性能回归**。

而 Windows 原生环境的对照测试，以及对相关代码路径的静态检查，则补上了另一半证据链：这并不是 PvZ-Portable 最近引入了一个会在所有平台普遍触发的性能问题，而是 Wine 11.4 将原本就存在、但在其他环境里成本较低的一段热路径放大成了可见卡顿。

这种从应用层面直接定位底层回归的方法有其独特优势：

- **即时可行**——不需要编译数十个 Wine 版本进行二分测试
- **附带修复**——排查过程的副产品就是一个有效的优化补丁，无论 Wine 何时修复这个回归，程序都已受益

不过对于在 Wine 中的干净修复，还是免不了需要 bisect 定位回归 commit，或者等待 Wine 社区的修复。

## 全平台受益

虽然这个优化是由 Wine 的性能回归触发的，但它对**所有平台**都有积极意义：

| 平台 | 原状 | 优化后 |
| :--- | :--- | :--- |
| **Linux 原生** | vDSO 很快，无感知 | 减少 ~300 次/帧的无意义系统调用 |
| **Windows 原生** | 开销较低 | 减少系统调用带来的内核态切换 |
| **Wine** | 11.4 回归导致严重卡顿 | 从 ~5 FPS 恢复到满帧 |
| **macOS** | 开销中等 | 减少 mach_absolute_time 转换开销 |
| **Android / iOS** | 移动设备功耗敏感 | 减少每帧不必要的 CPU 唤醒 |
| **WebAssembly** | Emscripten 中系统调用有模拟开销 | 减少 JS 胶水代码调用次数 |

这里的一个核心结论是：**正确的做法本身就是性能优化**。不应该在热路径中反复调用一个返回值几乎不变的系统级函数，无论它在当前平台上碰巧足够快。

## 代码审计：是否存在类似问题？

修复完禅境花园后，笔者对整个代码库进行了全面审计，检查是否存在其他热路径中的类似问题：

- `time(0)` / `localtime()` / `strftime()` 等时间函数：其余调用均在初始化、存档加载、商店界面（低频触发）中
- 文件 I/O（`fopen` / `fread` 等）：全部在加载和存档路径中，无帧循环调用
- 字符串格式化（`snprintf` / `StrFormat` 等）：主要在 UI 渲染和调试代码中
- 阻塞调用（`sleep` / `SDL_Delay` 等）：全部在框架层和音频线程中

结论：**禅境花园是唯一存在这类热路径系统调用堆积问题的模块**。这与原版游戏的设计吻合——禅境花园是整个游戏中唯一需要对大量实体进行实时时间判断的场景（每株盆栽的浇水、施肥、需求、巧克力等状态都基于真实世界时间）。

## 后续：最小复现程序与 Wine Bug 提交

### 编写最小复现程序

为了向 Wine 社区精确地报告这一性能回归，笔者编写了一个完全独立于 PvZ-Portable 的最小复现程序。该程序的目标是：**用最少的代码，最直观地展示 `time()` 和 `localtime()` 在 Wine 11.4 中的性能退化**。

```c
/*
 * Minimal reproducer: time() / localtime() performance regression in Wine.
 *
 * Measures the wall-clock cost of calling time() and localtime() in a
 * tight loop.  Compare the output between Wine 11.3 and Wine 11.4 (or
 * whichever versions bracket the regression).
 *
 * Build:  gcc -O2 -o time_bench.exe time_bench.c
 * Run:    time_bench.exe            (uses default N = 10000)
*/

#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#ifdef _WIN32
#include <windows.h>
#endif

/* Prevent the compiler from optimising calls away. */
static volatile long long g_sink = 0;

static double monotonic_seconds(void)
{
#ifdef _WIN32
    LARGE_INTEGER c, f;
    QueryPerformanceCounter(&c);
    QueryPerformanceFrequency(&f);
    return (double)c.QuadPart / (double)f.QuadPart;
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec / 1e9;
#endif
}

int main(int argc, char **argv)
{
    long n = 10000;
    long i;
    double t0, t1, t2;

    if (argc > 1)
        n = atol(argv[1]);
    if (n <= 0)
        n = 10000;

    printf("iterations: %ld\n\n", n);

    /* --- Benchmark time() --- */
    t0 = monotonic_seconds();
    for (i = 0; i < n; i++)
    {
        g_sink += (long long)time(NULL);
    }
    t1 = monotonic_seconds();
    printf("time()      : %.6f s  (%.0f ns/call)\n",
           t1 - t0, (t1 - t0) / n * 1e9);

    /* --- Benchmark localtime() --- */
    t1 = monotonic_seconds();
    for (i = 0; i < n; i++)
    {
        time_t now = time(NULL);
        struct tm *tm = localtime(&now);
        g_sink += tm->tm_sec;
    }
    t2 = monotonic_seconds();
    printf("localtime() : %.6f s  (%.0f ns/call)\n",
           t2 - t1, (t2 - t1) / n * 1e9);

    printf("\nsink=%lld\n", g_sink);
    return 0;
}
```

程序设计非常简洁：分别循环调用 `time()` 和 `localtime()` 各 N 次（默认 10000 次），使用高精度计时器测量总耗时后输出每次调用的总耗时和平均纳秒开销。`volatile` 防止编译器优化掉调用，末尾打印 `sink` 值进一步确保不被优化。在 Windows 下使用 `QueryPerformanceCounter`，在 Linux 下使用 `clock_gettime(CLOCK_MONOTONIC)`。

### 基准测试结果

使用同一复现程序，在三种环境下运行，结果对比如下：

**Wine 11.3**（N=10000）：

```
iterations: 10000

time()      : 0.128437 s  (12844 ns/call)
localtime() : 0.129727 s  (12973 ns/call)

sink=17732949360000
```

**Wine 11.4**（N=10000）：

```
iterations: 10000

time()      : 3.196547 s  (319655 ns/call)
localtime() : 3.184343 s  (318434 ns/call)

sink=17732948683316
```

**Linux 原生**（N=10000）：

```
iterations: 10000

time()      : 0.000103 s  (10 ns/call)
localtime() : 0.058464 s  (5846 ns/call)

sink=17732948500000
```

整理为表格：

| 环境 | `time()` ns/call | `localtime()` ns/call | 相对 Linux 原生 | 相对 Wine 11.3 |
| :--- | ---: | ---: | :---: | :---: |
| **Linux 原生** | 10 | 5,846 | 1x（基线） | — |
| **Wine 11.3** | 12,844 | 12,973 | ~1,284x / ~2.2x | 1x |
| **Wine 11.4** | 319,655 | 318,434 | ~31,966x / ~54.5x | **~25x** |

几个关键结论：

1. **Wine 11.3 → 11.4 存在约 25 倍的性能回归**：`time()` 从 ~12.8μs 升至 ~319μs，`localtime()` 从 ~13μs 升至 ~318μs。这是一个极为显著的退化。
2. **Linux 原生的 `time()` 几乎零开销**（10ns）：得益于 vDSO 机制，`time()` 在 Linux 内核中通过用户态直接读取共享内存实现，完全无需陷入内核态。这解释了为什么 PvZ-Portable 在 Linux 原生环境下从未触发这个瓶颈。
3. **即使是 Wine 11.3，翻译开销也比原生高 3 个数量级**：`time()` 在 Wine 11.3 中为 ~12.8μs（Linux 原生的约 1284 倍），说明 Wine 的 NT → Unix 翻译层本身就有可观的固定开销。只是在 11.3 中这个开销尚可接受，11.4 中的 25 倍放大才使其从"无感"变为"灾难"。
4. **`time()` 和 `localtime()` 在 Wine 中的开销几乎相同**：在 Linux 原生中 `localtime()` 比 `time()` 慢约 584 倍（涉及时区计算），但在 Wine 中两者的开销几乎一致，说明 Wine 翻译层的固定开销远大于函数本身的计算开销——瓶颈在跨层调用，而非函数逻辑。

### 向 Wine 提交 Bug 报告

基于以上定量证据，笔者向 Wine Bugzilla 提交了正式的 Bug 报告：

> **[Bug 59514 – Significant time()/localtime() Performance Regression in Wine 11.4](https://bugs.winehq.org/show_bug.cgi?id=59514)**

报告中包含了最小复现程序的源码、编译与运行方法（使用 Wine 下的 Windows 原生 gcc 编译 PE 可执行文件，并与 Linux 原生编译的版本做对照）、三组定量对照数据，以及复现步骤。

## 结语

这次优化的完整链条：

1. **发现**：Wine 11.4 下禅境花园主画面帧率骤降至 ~5 FPS
2. **分析**：通过分层计时剖析，逐步将瓶颈锁定为 `time(0)` / `localtime()` 在逐植物逐帧循环中的重复调用
3. **优化**：在 `ZenGarden` 类中增加逐帧时间缓存 `mNowTime` / `mNowTM`，将每帧约 300 次系统调用降至 2 次
4. **验证**：帧率从 ~5 FPS 恢复到满帧，性能提升约 90 倍，无任何行为回归
5. **发现回归**：优化效果间接揭示了 Wine 11.4 在时间系统调用翻译层的性能回归
6. **量化回归**：编写最小复现程序，定量测量出 Wine 11.4 中 `time()` / `localtime()` 的单次调用开销较 11.3 增长约 25 倍
7. **提交报告**：向 Wine Bugzilla 提交了 [Bug 59514](https://bugs.winehq.org/show_bug.cgi?id=59514)，附带最小复现程序与三组对照基准测试数据

整个修复仅修改 2 个文件，增加 34 行、删减 23 行（[PR #132](https://github.com/wszqkzqk/PvZ-Portable/pull/132)）。

这个案例证明了一个有趣的方法论：**有时候，修复你自己的程序就是定位第三方回归最高效的方式**。当你对热路径有足够的理解时，性能剖析数据本身就是最好的证据——它不需要你去编译、bisect 或调试第三方软件的源码。

当然，这也给了我们一个更本质的教训：**不要在热循环中信赖任何应该很快的系统调用**。今天快不代表明天快，这个平台快不代表那个平台快。如果返回值在整个循环中不变，那就缓存它。
