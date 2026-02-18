---
layout:       post
title:        PvZ-Portable v4 存档格式：实现跨架构关卡内无损存档
subtitle:     实现跨架构/跨平台且完美保存关卡内状态的游戏存档系统
date:         2026-01-30
author:       wszqkzqk
header-img:   img/games/bg-pvz-portable.webp
catalog:      true
tags:         C++ 游戏移植 序列化 游戏存档 开源软件 开源游戏 PvZ-Portable
---

## 引言

在之前的[文章](https://wszqkzqk.github.io/2026/01/26/PvZ-Portable/)中，笔者介绍了 [PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable) 项目。这是一个致力于将《植物大战僵尸：年度版》带向所有平台的开源重实现研究项目。

实现跨平台不仅仅意味着让代码在 Linux、Windows、macOS 上编译通过，更意味着**用户体验的一致性**。而这其中最关键的一环，就是**存档的互通性**。

试想一下，你在 Linux 上玩了一半的无尽生存模式，出门时希望能把存档转到 Switch 上继续玩，或者在 Windows 上回顾。然而，原版游戏的存档格式完全不支持这种操作。为了解决这个问题，笔者最近开发了全新的 **v4 可移植存档格式**。

本文将深入技术细节，剖析原版存档的缺陷，并详细介绍 v4 格式的设计原理与结构。

## 原版存档实现：裸内存快照

《植物大战僵尸》原版的存档机制设计非常简单粗暴。当你点击保存并退出时，游戏基本上是直接把内存中的对象 `memcpy` 到了硬盘上。

例如，保存关卡状态（`game1_13.dat`）时，大概逻辑如下：

```cpp
// 伪代码：原版存档逻辑
void SaveGame(Board* board) {
    File* f = OpenFile("game1_13.dat", "wb");
    Write(f, board, sizeof(Board)); // 直接写入整个 Board 对象
    for (int i = 0; i < board->mZombies.Count(); i++) {
        Write(f, &board->mZombies[i], sizeof(Zombie)); // 直接写入 Zombie 对象
    }
    // ... 对植物、子弹等做同样操作 ...
}
```

### 问题在哪？

这种内存转储的方式对于单一平台的闭源商业游戏来说，开发效率极高，运行速度也快（无需序列化开销）。但对于一个跨平台移植项目来说，这是灾难性的：

1.  **32位与64位的鸿沟**：
    原版是 32 位程序。游戏对象中包含大量的**指针**（例如僵尸指向它正在吃的植物）。
    *   在 32 位系统上，指针占 4 字节。
    *   在 64 位系统上，指针占 8 字节。
    导致 `sizeof(Zombie)` 在不同架构上完全不同，结构体内的字段偏移量（Offset）也会发生错位。
2.  **内存对齐（Alignment）与填充（Padding）**：
    不同的编译器（MSVC vs GCC）或不同的 CPU 架构（x86 vs ARM vs LoongArch）对于结构体成员的内存对齐规则不同。编译器可能会在 `bool` 和 `int` 之间插入填充字节。直接 Dump 内存会将这些不可移植的填充字节也写入文件。
3.  **字节序（Endianness）**：
    虽然目前主流桌面设备（PC, Mac, Android, Switch）几乎都是小端序（Little-Endian），但直接 Dump 内存意味着不仅失去了对大端架构（如 Wii U, PS3）的潜在支持，也缺乏明确的格式规范。
4.  **指针失效**：
    原版存档中保存的指针其实是运行时的内存地址。重新加载时，游戏必须小心翼翼地把这些无效的地址修复为新分配的内存地址。如果对象布局稍有变化，这个修复过程就会出错崩溃。

因此，**原版存档无法在不同架构之间互通**。你无法把 Linux 版的存档直接放到 32 位的 MSVC 构建的 Windrows 上运行。

## 解决方案：全新 v4 可移植存档格式

为了彻底解决这个问题，笔者设计并实现了 **v4 可移植存档格式**（内部代号 `PVZP_SAVE4`）。

### 设计原则

1.  **显式序列化**：
    不再 Dump 内存。每个字段（坐标、血量、状态）都必须通过代码明确地读写。
    *   `mX` (float) -> 写入 4 字节浮点。
    *   `mZombieType` (enum) -> 写入 4 字节整数。
    *   `mIsEating` (bool) -> 写入 1 字节布尔值。
    *   ……
2.  **消除指针，使用 ID**：
    不保存内存地址。所有引用关系通过 ID 或索引来重建。
    *   原版：`Zombie* mTargetPlant = 0x12345678;`
    *   v4版：`int mTargetPlantIndex = 5;` （指向第 5 个植物）。
3.  **固定字节序**：
    所有多字节整数强制使用 **小端序（Little-Endian）** 写入，确保在任何架构上读取一致。
4.  **块结构（Chunk-based）与 TLV**：
    文件被组织成不同的块（Chunk），每个块负责一类数据（如僵尸列表、植物列表）。这提高了格式的扩展性和容错性。

### 文件结构详解

v4 存档文件由**文件头（Header）**和一系列**数据块（Chunks）**组成。

#### 文件头 (Header)

文件最开始是 24 字节的固定头：

| 字段 | 大小 | 值/说明 |
| :--- | :--- | :--- |
| **Magic** | 12 Bytes | `"PVZP_SAVE4\0\0"` (确保识别格式) |
| **Version** | 4 Bytes | `1` (当前 v4 格式的版本号) |
| **PayloadSize** | 4 Bytes | 后续所有 Chunk 数据的总大小 |
| **CRC32** | 4 Bytes | 校验和，防止存档损坏 |

#### 数据块 (Chunk)

Header 之后是紧凑排列的 Chunk。每个 Chunk 的结构如下：

| 字段 | 大小 | 说明 |
| :--- | :--- | :--- |
| **ChunkID** | 4 Bytes | 块类型标识（见下表） |
| **Size** | 4 Bytes | 该块数据区的大小（N 字节） |
| **Data** | N Bytes | 具体的序列化数据 |

支持的 Chunk 类型 (`SaveChunkTypeV4`) **完整列表**如下（编号与代码一致）：

1.  `SAVE4_CHUNK_BOARD_BASE (1)`：关卡主状态（Board 基础字段）
2.  `SAVE4_CHUNK_ZOMBIES (2)`：僵尸列表
3.  `SAVE4_CHUNK_PLANTS (3)`：植物列表
4.  `SAVE4_CHUNK_PROJECTILES (4)`：子弹/投射物列表
5.  `SAVE4_CHUNK_COINS (5)`：金币与掉落物列表
6.  `SAVE4_CHUNK_MOWERS (6)`：小推车/割草机列表
7.  `SAVE4_CHUNK_GRIDITEMS (7)`：格子道具（墓碑、梯子等）
8.  `SAVE4_CHUNK_PARTICLE_EMITTERS (8)`：粒子发射器
9.  `SAVE4_CHUNK_PARTICLE_PARTICLES (9)`：粒子对象（具体粒子）
10. `SAVE4_CHUNK_PARTICLE_SYSTEMS (10)`：粒子系统
11. `SAVE4_CHUNK_REANIMATIONS (11)`：Reanimation 动画实例
12. `SAVE4_CHUNK_TRAILS (12)`：Trail 轨迹效果
13. `SAVE4_CHUNK_ATTACHMENTS (13)`：附着物（Attachment）
14. `SAVE4_CHUNK_CURSOR (14)`：光标/手持对象
15. `SAVE4_CHUNK_CURSOR_PREVIEW (15)`：光标预览态
16. `SAVE4_CHUNK_ADVICE (16)`：提示系统状态
17. `SAVE4_CHUNK_SEEDBANK (17)`：种子卡槽整体
18. `SAVE4_CHUNK_SEEDPACKETS (18)`：单张卡片（冷却、数量等）
19. `SAVE4_CHUNK_CHALLENGE (19)`：挑战/特殊模式状态
20. `SAVE4_CHUNK_MUSIC (20)`：音乐状态

#### 对象序列化 (TLV within Chunks)

在每个 Chunk 内部，笔者采用 **Type-Length-Value (TLV)** 的变体思想来组织对象属性。

为了应对未来游戏更新可能增减字段的情况，不能只是简单将属性按顺序写入（这样如果中间加一个字段旧存档就废了），更好的方式是给每个关键属性分配一个 **Tag ID**。

以 **僵尸（Zombie）** 对象为例，它的序列化流看起来是这样的：

```text
[Tag: 1] [Size] [Value: mZombieType]
[Tag: 2] [Size] [Value: mZombiePhase]
[Tag: 3] [Size] [Value: mPosX]
...
[Tag: PORTABLE_FIELD_TAIL] [Size] [Value: 结构体剩余的简单数据]
```

在代码实现中，笔者需要兼顾原本内存 Dump 的兼容性（为了读取旧存档）和新格式的可移植性。因此，笔者在 `SaveGame.cpp` 中定义了一套 `PortableSaveContext` 系统：

```cpp
// 核心序列化类
class PortableSaveContext
{
    // ...
    void SyncBool(bool& theBool);   // 读/写 1 byte
    void SyncInt32(int& theValue);  // 读/写 4 bytes (LE)
    void SyncFloat(float& theValue);// 读/写 4 bytes (LE)
    // ...
};

// 僵尸对象的序列化实现
static void SyncZombieTailPortable(PortableSaveContext& theContext, Zombie& theZombie)
{
    SyncEnum32(theContext, theZombie.mZombieType);
    SyncEnum32(theContext, theZombie.mZombiePhase);
    theContext.SyncFloat(theZombie.mPosX);
    theContext.SyncFloat(theZombie.mPosY);
    // ...以此类推，显式同步每一个字段
}
```

### 遇到的挑战：音频状态带来的崩溃

在实现过程中，笔者遇到过一个奇怪的问题。

笔者在远程的 LoongArch64 机器上加载从 x86_64 的 Linux 下拷贝过来的存档时，游戏直接触发了断言崩溃。但其实完全不是内存布局的问题，而是**音频子系统的支持状态不匹配**。

**原因分析**：
`Board` 对象中保存了 `mMusicDisabled` 状态。
1.  PC 玩家开启了音乐 (`mMusicDisabled = false`)，保存并生成存档。
2.  LoongArch 机器因为没有安装对应的音频库，启动时检测并设置了 `mMusicDisabled = true`。
3.  **读档时**，旧的逻辑无脑读取了存档中的 `false`，覆盖了本地的 `true`。
4.  游戏误以为音乐系统可用，尝试调用 `PlayMusic`，结果在底层触发了断言失败。

**修复方案**：
笔者在序列化层引入了**运行时状态隔离**。对于 `mMusicDisabled` 这种反映硬件/驱动状态的字段，笔者在读档时**只读取不操作** —— 读取存档中的字节仅仅是为了维持文件流的对齐，读取后直接丢弃，不修改内存中的真实状态。

```cpp
// src/Lawn/System/SaveGame.cpp 中的修复片段
if (theContext.mReading)
{
    bool aSavedMusicDisabled = false;
    theContext.SyncBool(aSavedMusicDisabled);
    // 忽略读取到的值。mMusicDisabled 是运行时能力标志，
    // 不应从存档中恢复，而应保持本机硬件检测的结果。
}
else
{
    theContext.SyncBool(theMusic.mMusicDisabled); // 写入占位，保持格式对齐
}
```

这样，无论存档来自哪个平台，是否有音乐支持，游戏都能正确地根据当前硬件状态决定是否启用音乐，避免了崩溃。

## 兼容性与共存策略

为了保证现有用户的平滑过渡以及对旧版游戏的兼容性，PvZ-Portable 目前采用了**双格式共存**的保存策略。

当游戏保存进度时，会同时生成两个文件：
1.  **`.dat` 文件**（例如 `game1_13.dat`）：这是原版格式的内存转储存档。它保留了特定于当前运行平台的内存布局，仅供本机快速读取，**不具有跨平台移植性**。
2.  **`.v4` 文件**（例如 `game1_13.v4`）：这是新的可移植存档。它可以在任何支持 v4 格式的设备上加载。

**注意**：如果你需要在不同设备间转移存档，请**复制 `.v4` 文件**，只有`.v4`文件能保证跨平台兼容。目标设备上的游戏在读取存档时，会优先寻找并加载 `.v4` 文件（如果存在）；只有在找不到 `.v4` 文件时，才会尝试加载旧版的 `.dat` 文件（但这通常会导致跨架构崩溃）。

## 特别说明：游戏存档清理机制

在开发过程中，我们对游戏的存档清理机制进行了一项微小的调整。原版游戏在**加载**关卡那一刻便会**删除存档**，可能是想以此防止玩家通过强行杀死游戏进程来反复重试，或者只是因为这样的设定正常可用。但这样也会引入一个严重的问题：如果游戏**意外崩溃**，玩家将***失去所有进度***，包括此前保存过的内容。

现在的逻辑是仅在**关卡明确结束时**才删除存档，这意味着：
1.  **正常退出**：当你点击主退出按钮、关闭窗口甚至在终端按下 `Ctrl + C` 时，游戏都能捕获退出信号，自动执行保存操作。这点与原版体验一致。
2.  **异常终止**：如果游戏因 Bug 崩溃、被系统强制杀死（`kill -9`）或发生了突然的断电，游戏无法执行保存。在**原版**中，这会导致本关进度**全部丢失**（因为开始时存档已被删）；而在 **PvZ-Portable** 中，由于我们保留了关卡起始存档，你重新打开游戏后可以**从上次保存的状态继续游戏**。
3.  **再次保存**：当你在关卡中途再次保存时，新的存档会覆盖旧存档，确保你的最新进度被保存。

虽然这在理论上允许了玩家通过操作系统强行结束任务来重试关卡，但考虑到玩家本就可以通过更简单的复制/粘贴存档文件来回档，我们认为**保护正常玩家不因崩溃而坏档**的优先级远远更高。

## 存档查看与修改工具

为了方便调试、修改存档，笔者还编写了一个配套的 Python 脚本工具：`scripts/pvzp-v4-converter.py`。

### 功能亮点

这个工具不仅仅可以一个查看存档信息，还实现了 **无损的双向转换**：

1.  **v4 转 YAML (Export)**：
    将二进制的 `.v4` 存档转换为人类可读的 YAML 文本格式。
    *   **可玩性数据可视化**：你可以直接看到并修改阳光数、金币数、当前波数、植物位置等。
    *   **复杂数据保留**：对于粒子效果、动画状态等极其复杂且难以手动编辑的数据，脚本会自动将其保留为 Base64 编码的二进制块，确保在转换回 v4 时数据**完全无损**。
    *   **关卡编辑支持**：
        *   **场上植物/僵尸**：你可以直接编辑 `plants` 和 `zombies` 列表，添加、删除或修改它们的属性（类型、位置、状态等）。
        *   **状态数据**：例如阳光、卡槽的冷却状态、当前波数等都可以直接修改。
        *   **自定义出怪**：脚本支持解析并编辑 `zombies_in_wave` 数组，你可以手动定制每一波出现的僵尸类型。
        *   **砸罐子编辑**：完整支持解析 `GridItem` 中的罐子内容（`ScaryPotType`），你可以修改每个罐子里是植物、僵尸还是阳光。

2.  **YAML 转 v4 (Import)**：
    将修改后的 YAML 文件重新打包成合法的 `.v4` 存档。
    *   脚本会自动处理 CRC32 校验和与文件头，生成的存档可以**直接在游戏中加载**。

### 使用方法

首先确保安装了 PyYAML 依赖，随后即可使用：

```bash
# 进入脚本目录
cd scripts

# 查看存档基本信息
python pvzp-v4-converter.py info game1_13.v4

# 导出为 YAML (默认模式，wave 数据保持紧凑)
python pvzp-v4-converter.py export game1_13.v4 game1_13.yaml

# 导出为 YAML (展开模式，可编辑每一波僵尸)
python pvzp-v4-converter.py export --expand-waves game1_13.v4 game1_13.yaml

# 修改 YAML 后，导入回 v4 格式
python pvzp-v4-converter.py import game1_13.yaml game1_13_mod.v4
```

通过这个工具，即使不了解二进制格式细节，玩家也可以轻松实现存档修改器的功能，也可以用于制作特殊的测试关卡。

## 结语

通过 v4 存档格式，PvZ-Portable 终于打破了硬件架构的壁垒。现在：
*   ✅ **32位 <-> 64位**：兼容。
*   ✅ **x86_64 <-> i686 <-> ARM <-> RISC-V <-> LoongArch**：兼容。
*   ✅ **Windows <-> Linux <-> macOS <-> Switch**：兼容。

笔者开发这样的新游戏存档，不仅是为了让玩家间的数据共享成为可能，更是为了让优秀的游戏不再受限于它诞生的时代和平台，真正属于每一个玩家。

## ⚠️ 版权与说明

**重要：本项目仅包含代码引擎，不包含任何游戏素材！**

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中：

*   `main.pak`
*   `properties/` 目录

本项目仅提供引擎代码，用于技术学习，**不包含**上述任何游戏资源文件，任何游戏资源均需要用户自行提供正版游戏文件。

本项目的源代码以 [**LGPL-3.0-or-later**](https://www.gnu.org/licenses/lgpl-3.0.html) 许可证开源，欢迎学习和贡献。

## 附录：v4 存档结构文档

本节给出 v4 存档的结构文档，便于第三方实现读写器。

### 文件整体布局

```
SaveFileV4 := Header + Payload
Header := Magic[12] + Version[u32] + PayloadSize[u32] + PayloadCrc32[u32]
Payload := Chunk*
```

*   `Magic` 固定为 ASCII 字符串 `PVZP_SAVE4`，不足 12 字节用 `\0` 填充。
*   `Version` 当前为 `1`。
*   `PayloadSize` 为所有 Chunk 序列化后字节数总和。
*   `PayloadCrc32` 为 `Payload` 的 CRC32（与 `zlib` 的 `crc32` 一致）。

### Chunk 结构

```
Chunk := ChunkID[u32] + ChunkSize[u32] + ChunkData[ChunkSize]
```

*   `ChunkID` 对应上文完整列表（1..20）。
*   `ChunkSize` 为 `ChunkData` 的字节数。
*   `ChunkData` 内部仍为 TLV/字段序列化流。

### ChunkData 的通用 TLV 结构

Chunk 内部使用可扩展字段布局：

```
Field := FieldID[u32] + FieldSize[u32] + FieldData[FieldSize]
ChunkData := Field*
```

*   未识别的 `FieldID` 必须跳过（根据 `FieldSize` 移动游标），以保证前向/后向兼容。
*   常用字段以 `FieldID` 固定编号写入；复杂对象的尾部字段使用 `PORTABLE_FIELD_TAIL` 记录。

### 基本类型编码规则

*   `u32`/`i32`/`float`：统一 **小端序**。
*   `bool`：1 字节（`0`/`1`）。
*   数组：按元素顺序线性写入。

### Chunk 级别语义说明（简述）

*   **Board Base (1)**：关卡全局状态（关卡类型、波次、计时器、模式标志等）。
*   **Zombies/Plants/Projectiles (2/3/4)**：关卡中所有实体对象列表。
*   **Coins/Mowers/GridItems (5/6/7)**：掉落物、割草机、墓碑/梯子等格子道具。
*   **Particles/Reanimations/Trails/Attachments (8..13)**：粒子、动画实例、轨迹及其附着物。
*   **Cursor/CursorPreview (14/15)**：鼠标/手持物及预览状态。
*   **Advice/SeedBank/SeedPackets (16/17/18)**：提示系统与卡槽/卡片状态。
*   **Challenge/Music (19/20)**：挑战模式及音乐播放状态。

### 兼容性要求

*   读档时必须允许缺失字段：缺失字段使用默认值。
*   读取到未知字段必须跳过，保持后续字段可解析。
*   运行时能力标志 `mMusicDisabled` **不得**从存档恢复，只允许读出字节以保持流对齐。

以上结构可以确保 v4 存档能在不同 ISA、不同编译器、不同位宽之间稳定互通。
