---
layout:       post
title:        PvZ-Portable 优化实录：从 6 秒到 1.5 秒的启动速度提升
subtitle:     记一次针对类 Unix 平台下的文件大小写不敏感 I/O 性能优化
date:         2026-02-06
author:       wszqkzqk
header-img:   img/games/bg-pvz-portable.webp
catalog:      true
tags:         C++ 性能优化 Linux 文件系统 开源游戏 开源软件
---

## 背景：大小写敏感的历史包袱

在[之前的文章](https://wszqkzqk.github.io/2026/01/26/PvZ-Portable/)中，我介绍了 [PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable) 项目。作为一个以“100% 还原原版体验”为目标的项目，我们必须面对大量历史遗留问题。其中最让人头疼的一个，就是**资源文件名的大小写混乱**。

原版游戏是为 Windows 开发的。众所周知，Windows 默认是**大小写不敏感**的。这意味着代码里写 `LoadImage("Reanim/Zombie.png")`，而在硬盘上文件名叫 `reanim/zombie.PNG`，Windows 也能照常读取。

然而，当我们要将游戏移植到 Linux 或 macOS 时，问题就来了。这些操作系统默认通常是**大小写敏感**的。直接移植的代码会因为 `File Not Found` 而崩溃。

由于版权原因，我们不能分发修改文件名后的游戏资源包（`main.pak` 等），必须要求用户提供原版正版资源，也无法修正原版资源中的错误。因此，兼容这些混乱的文件名成为了引擎层的责任。

## 初始方案：`fcaseopen`

为了解决这个问题，笔者最初引入了一个通用的跨平台解决方案 —— `fcaseopen`。

它的原理非常简单直接：如果直接 `fopen` 失败，就假设是因为大小写问题，然后对路径进行分解，逐级遍历目录（opendir/readdir），进行不区分大小写的比对（strcasecmp），找到正确的文件名后拼凑出真实路径再打开。

```c
// 伪代码：fcaseopen 的“暴力”逻辑
FILE* fcaseopen(path) {
    if (f = fopen(path)) return f; // 尝试直接打开 (Fast Path)
    
    // 失败了，开始逐级查找
    full_path = "";
    parts = split(path, "/");
    for (part : parts) {
        found = false;
        dir = opendir(full_path);
        while (entry = readdir(dir)) {
            if (strcasecmp(entry.name, part) == 0) {
                full_path += "/" + entry.name;
                found = true;
                break;
            }
        }
        if (!found) return NULL; // 真的不存在
    }
    return fopen(full_path);
}
```

这个方案虽然能工作，但性能开销是巨大的。每一次失败的打开操作都会触发多次系统调用（System Call）和目录遍历。

在早期的未提交测试中，笔者在一台 AMD Ryzen 5800H 的笔记本上（运行 Arch Linux），游戏的资源加载时间（即启动黑屏时间）竟然高达 **6 秒**！这对于一个 2D 游戏来说是不可接受的。

## 阶段一：抛弃 `chdir`，引入 `fcaseopenat`

在最早的版本中，为了省事，游戏启动时会直接 `chdir`（改变工作目录）到资源所在目录。这虽然方便了相对路径的编写，并且避免了处理大小写不敏感路径的开销，但在现代软件工程中是个坏习惯，不仅影响了后续功能的扩展，还带来了潜在的线程安全风险。

因此，笔者决定重构这部分逻辑。引入了命令行参数 `-resdir`，允许手动指定资源路径，废弃了全局 `chdir`。

为了配合这个改动，笔者实现了一套基于 `fcaseopenat` 的机制。利用 `GetResourceFolder()` 获取已知的资源根目录（Base Directory），然后在进行文件查找时，只对**相对路径**部分进行大小写修正。

```cpp
// 优化后的逻辑
FILE* fcaseopenat(base, relative_path) {
    // 1. 尝试直接打开 base + relative_path
    // ...
    // 2. 如果失败，且 base 是确定存在的，则只对 relative_path 进行 casepath
    // 避免了对 /usr, /home 等上层目录的无效扫描
}
```

**效果**：
这一改动将启动时间从 **6 秒** 降低到了 **2 秒** 左右。这是因为我们避免了对系统根路径的大量冗余扫描，仅仅在确定的游戏资源目录内进行查找。

## 阶段二：确认 CPU 瓶颈

将启动时间优化到 2 秒后，笔者发现了一个有趣的现象：
*   使用 `-O3` 编译的版本启动耗时约 **1.9s - 2.0s**。
*   使用 `-O2` 编译的版本启动耗时约 **2.0s - 2.2s**。
*   更关键的是，当拔掉笔记本电源（CPU 降频）时，启动时间会大幅增加到 **4~6 秒**！

这强烈的暗示：**瓶颈不再主要在于磁盘 I/O，而在于 CPU 计算**。

经过分析，瓶颈主要集中在大量的**字符串操作**和**负面查找（Negative Lookup）**上。

### 资源架构与 Alpha 通道探测的冲突

要理解为什么会有性能瓶颈，首先需要明确 PvZ 的资源加载架构，它主要由两部分组成：

1.  **PAK 资源包 (`main.pak`)**：
    *   这是宝开（PopCap）官方分发游戏资源的方式。
    *   它是一个巨大的压缩包，包含了游戏中 99.9% 的图片、音效和数据。
    *   **特点**：作为官方只读数据，其内部文件名是规范的，且已被我们读入内存红黑树（`std::map`），查找速度极快（O(log n)），不存在 IO 性能问题。

2.  **松散文件 (Loose Files)**：
    *   这是指直接散落在游戏目录下的文件。
    *   **作用**：主要用于或**热更新**或者**贴图替换**。
    *   引擎设计的逻辑是：如果磁盘上存在某个文件（如 `images/Zombie.png`），它会优先于 `main.pak` 中的同名文件被加载。这允许玩家通过简单的复制粘贴来修改游戏图片。

**性能杀手：Alpha 遮罩探测**

PvZ 的旧版引擎有一个遗留特性：在加载每一张图片（比如 `Zombie.png`）时，都会自动尝试寻找是否存在独立的**透明度遮罩文件**（通常命名为 `_Zombie.png` 或 `Zombie_.png`），用于合成最终图像。

这个逻辑对于通过 `main.pak` 加载的官方图片来说是灾难性的：
1.  引擎加载了 `main.pak` 中的 `Zombie.png`。
2.  引擎为了确认有没有“针对这张图片的松散 Alpha 遮罩 Mod”，会去磁盘上查找 `_Zombie.png`。
3.  **99% 的情况下，这种文件是不存在的**。
4.  在 `fcaseopen` 的逻辑里，查找不存在的文件的代价是最高的 —— 为了确认它“真的不存在”（而不是仅仅大小写没对上），它必须遍历整个目录。

这意味着加载 1000 张 PAK 内的图片，就会产生 2000 次**针对磁盘的、必然失败的、高成本的**文件查找。

## 阶段三：极致优化

为了榨干最后的性能，笔者引入了更深度的优化方案。

### 引入 `FastFileExists` 与 PAK 优先策略

既然 90% 的 Alpha 遮罩查找都是失败的，我们需要让失败来得更快一点。笔者引入了 `FastFileExists` 函数：

```cpp
static bool CheckSinglePath(std::string_view thePath)
{
    // 1. 优先查 PAK 索引 (红黑树查找，极快)
    // 预先将路径规范化并大写，直接在内存 Map 中查询
    // PAK 内的资源因为 NormalizePakPath 的存在，始终能够大小写不敏感地命中
    if (gPakInterface && gPakInterface->Contains(NormalizePakPath(thePath)))
        return true;

    // 2. 只有 PAK 里没有，才去查文件系统
    // 这里使用了普通的 exists (stat)，对于不存在的文件，它能利用 OS 缓存极快返回 false
    // ⚠️ 注意：这里进行了一个有意的权衡 (Trade-off)
    // 这里的 FileExists 是大小写敏感的 (在 Linux 上)。这意味着如果 Alpha 遮罩作为一个松散文件
    // 存在于磁盘上，但大小写与代码中不匹配，它虽然存在但会被这里判断为 false (不存在)。
    // 
    // 为什么这么做？
    // 因为这主要用于探测 "大概率不存在" 的 Alpha 辅助文件。
    // 为了兼容少数 "文件名大小写写错的松散 Alpha 文件" 而对 90% 的不存在情况调用昂贵的 fcaseopen 是极不划算的。
    // 对于这类松散文件，我们要求用户/开发者保证文件名大小写正确；而对于主资源文件，我们依然有 fcaseopen 兜底。
    return Sexy::FileExists(thePath); 
}
```

通过优先查询内存中的 PAK 索引表，大量的无效文件探测瞬间完成，完全规避了磁盘 I/O 和目录遍历。同时，对于磁盘文件查找，我们采取了**“主资源保兼容，辅助资源保性能”**的策略，这背后的逻辑是：

1.  **历史遗留 vs 用户行为**： `main.pak` 是宝开官方打包的，其中的内容受到版权保护，不可自行分发，里面的大小写混乱是真正的历史债务，我们**必须**兼容。
2.  **松散文件无包袱**： 松散文件（如修改的贴图或者 Alpha 通道图）是由现在的玩家或开发者手动放入游戏目录的，并不存在历史遗留问题。作为新加入的资源，完全有理由要求创作者遵循目标平台的文件命名规范（即大小写正确）。
3.  **性能权衡**： 为了兼容极少数用户自己犯下的命名错误，而去惩罚 99% 的正常玩家的启动速率，显然是不划算的。

因此，最终的实现方案为：
*   **主资源加载 (Main Image)**：经过 `TryLoadByExt` 尝试加载，最终会调用底层的 `fcaseopen`，虽然慢但保证了全兼容，即使磁盘文件名大小写错了也能找到。
*   **辅助资源探测 (Alpha Mask)**：使用 `FastFileExists` 预检。如果 PAK 里没有，且磁盘文件名严格大小写不匹配，直接放弃加载。这避免了对海量不存在文件进行递归目录扫描。

### 优化 `NormalizePakPath`

对于路径规范化这一热点函数，笔者进行了针对性优化：
*   **减少分配**：接口改为接收 `std::string_view`，减少入参时的临时字符串构造。
*   **按需转换**：仅在必要时才调用 `std::filesystem` 的重型操作。

### 数据驱动的格式探测

原先的代码在加载图片时，是硬编码的一连串 `if-else`：

```cpp
// 旧代码
if (Load("foo.png")) ...
else if (Load("foo.jpg")) ...
else if (Load("foo.gif")) ...
```

每一次 `Load` 调用（即使失败）都可能触发复杂的路径处理。新代码将其重构为数据驱动的查找表结构，配合 `std::string_view`，使得逻辑更加紧凑且易于分支预测。

## 最终成果

经过这一系列优化，PvZ-Portable 在 Arch Linux (Ryzen 5800H) 上的平均启动时间最终稳定在 **1.5s - 1.6s**。第二阶段的优化甚至将龙芯 3C5000L 上的启动时间在第一阶段的基础上减半，从 **4.8s** 降到了 **2.4s**。

更令人欣慰的是，`-O2` 和 `-O3` 构建之间的性能差距被缩小到了 **50ms** 以内。这表明我们成功消除了大部分低效的冗余计算代码，性能不再呈现出明显的 CPU 瓶颈和编译器优化依赖。

## 总结

这次优化经历再次印证了那个经典道理：**最快的 I/O 是没有 I/O**。

1.  **Stage 1**: 通过 `fcaseopenat` 缩小搜索范围，减少了目录遍历的深度。
2.  **Stage 2**: 通过内存索引（PAK Map）拦截请求，直接消除了绝大多数无效的 I/O 操作。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中：

*   `main.pak`
*   `properties/` 目录

本项目仅提供引擎代码，用于技术学习，**不包含**上述任何游戏资源文件，任何游戏资源均需要用户自行提供正版游戏文件。

本项目的源代码以 [**LGPL-3.0-or-later**](https://www.gnu.org/licenses/lgpl-3.0.html) 许可证开源，欢迎学习和贡献。
