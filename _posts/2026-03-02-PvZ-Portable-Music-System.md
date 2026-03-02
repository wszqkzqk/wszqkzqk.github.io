---
layout:       post
title:        植物大战僵尸开源实现 PvZ-Portable: 通过通道级音量控制实现单流音乐系统
subtitle:     MOD 音乐的通道级音量控制、动态打击乐切换与音符残留修复
date:         2026-03-02
author:       wszqkzqk
header-img:   img/games/bg-pvz-portable.webp
catalog:      true
tags:         C++ SDL2 开源软件 游戏移植 开源游戏 PvZ-Portable 音频
---

## 引言

在之前的[文章](https://wszqkzqk.github.io/2026/02/16/PvZ-Portable-GLES2-Migration/)中，笔者介绍了 [PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable) 渲染后端统一迁移到 OpenGL ES 2.0 的过程。而除了图形渲染之外，音乐系统同样是游戏体验的核心。《植物大战僵尸》的关卡音乐是一套较复杂的**动态音乐系统**，会根据战场上僵尸的数量实时淡入打击乐轨道（鼓组和镲片），在战斗激烈时制造紧张感。

这套动态音乐机制的正确实现经历了一段曲折的过程：从社区贡献者的首次修复，到因笔者发现回归而回退，再到用户报告音频异常后的重新审视，最终找到了既正确又简洁的解决方案。此外，在迁移到单流方案后，听觉极其灵敏的用户又发现了曲目切换时的音符残留问题——通过对比原版行为和查阅 BASS 音频库的公开文档，最终在 libopenmpt 层面找到了修复方式。本文将详细记录这段历程。

## 背景：MOD 音乐与动态打击乐

### MOD 格式与通道结构

《植物大战僵尸》的关卡音乐使用 [MOD 格式](https://en.wikipedia.org/wiki/Module_file)（具体是 `.mo3` 文件）。与常见的 MP3/OGG 等流式音频不同，MOD 是一种 **tracker 音乐格式**——它将乐曲拆分为多个**通道（channel）**，每个通道独立播放自己的采样序列。游戏的主音乐文件 `mainmusic.mo3`（约 2.2 MB）包含 **30 个通道**，所有关卡的旋律、贝斯、鼓组、镲片等乐器轨道，全部打包在同一个文件中。

MOD 文件还有一个关键概念——**Order 表**。Order 表是一个由 Pattern 编号组成的序列，决定了乐曲的播放顺序。不同关卡的音乐实际上位于同一个 MOD 文件的不同 Order 偏移处，例如白天关卡从 Order `0x00` 开始，黑夜关卡从 `0x30` 开始，泳池关卡从 `0x5E` 开始。播放时，只需跳转到对应的 Order 位置即可切换曲目。

### 两种 Burst 方案

游戏的动态音乐系统通过 **Burst**（爆发）机制来控制打击乐——当屏幕上的僵尸数量 ≥ 10 时触发淡入，<4 时触发淡出。但不同关卡的 Burst 实现方式有所不同，分为两种方案：

**方案一**（白天、泳池、雾夜、屋顶关卡）：所有乐器轨道位于同一个 MOD 文件的**同一段 Order 区间**内，打击乐的通道穿插在旋律通道之间。Burst 触发时，鼓组和镲片通道的音量从 0 淡入到 1；战斗结束时，先用 800 tick 淡出镲片，再用 50 tick 快速淡出鼓组。镲片和鼓组使用不同的淡入/淡出速率，需要对它们进行独立的音量控制。

**方案二**（黑夜关卡）：旋律和鼓组位于同一个 MOD 文件的**不同 Order 区间**——旋律从 `0x30` 开始，鼓组从 `0x5C` 开始。Burst 触发时，旋律流的音量整体淡出到 0，同时鼓组流的音量淡入到 1，形成一种此消彼长的切换效果。

### 通道映射

每个关卡的 30 个通道如何划分为旋律、鼓组、镲片，所用的通道编号都不相同。以下是各关卡的通道映射：

- **白天**（Grasswalk）：旋律 0–23，鼓组 24–26，镲片 27
- **泳池**（Watery Graves）：旋律 0–17，鼓组 18–28，镲片 18–24 和 29
- **雾夜**（Rigor Mormist）：旋律 0–15，鼓组 16–22，镲片 23
- **屋顶**（Graze the Roof）：旋律 0–17，鼓组 18–20，镲片 21

其中泳池关卡的通道映射尤为特殊——鼓组（18–28）和镲片（18–24, 29）在 18–24 号通道上**存在重叠**。这意味着这些通道同时属于鼓组和镲片，音量应取两者中的较大值。

## 三流架构：原始实现及其由来

### BASS 音频库与三流设计

原版游戏使用 [BASS 音频库](https://www.un4seen.com/bass.html)播放 MOD 音乐。BASS 提供了 `BASS_ATTRIB_MUSIC_VOL_CHAN` 属性，可以对单个 MOD 实例内的指定通道设置音量，但同一实例只有一个全局的 `BASS_ATTRIB_VOL`（流级音量）。对于方案一的关卡，鼓组和镲片需要以不同速率独立淡入淡出，仅靠通道级音量就将无法简单区分同一实例中哪些是鼓组、哪些是镲片——除非对每个通道单独计算其在当前 Burst 状态下应有的音量，再逐通道设置。

原版游戏选择了另一种方式：加载**三份 MOD 实例**，分别对应 MAIN（旋律）、DRUMS（鼓组）和 HIHATS（镲片）三个流。每个 MOD 实例播放同一首曲子的同一段 Order，但通过流级音量 `BASS_ATTRIB_VOL` 分别控制三份流的整体音量。其中，`mainmusic.mo3`（2.2 MB）被加载了两次——一次用于 MAIN 流，一次用于 DRUMS 流；而 `mainmusic_hihats.mo3`（47 KB）是一个精简版本，共享相同的 Order 表和 30 通道结构，但只保留了镲片采样数据，作为内存优化的第三流。加载后，各流使用 `BASS_ATTRIB_MUSIC_VOL_CHAN` 设置通道音量来将其他流的通道静音（例如 DRUMS 流中旋律通道音量设为 0），然后用 `BASS_ATTRIB_VOL` 控制整体流音量进行淡入淡出。

这种三流架构巧妙地将鼓组/镲片独立淡入淡出简化为独立控制三个流的音量，代价是需要加载三份 MOD 实例并保持它们的播放进度同步。

### PvZ-Portable 的移植

PvZ-Portable 使用 [SDL-Mixer-X](https://github.com/WohlSoft/SDL-Mixer-X) 替代了 BASS 音频库。SDL-Mixer-X 通过 [OpenMPT](https://openmpt.org/) 后端解码 MOD 音乐，并支持多流（`Mix_PlayMusicStream` / `Mix_VolumeMusicStream`）播放。在最初的移植中，项目忠实地复刻了三流架构——`MusicInit` 中为 DRUMS 流额外加载一份 `mainmusic.mo3`，为 HIHATS 流加载 `mainmusic_hihats.mo3`；播放时启动三个流并在 `MusicResyncChannel` 中通过微调 BPM 来保持同步。

然而，这个看似正确的移植隐藏了一个严重问题：**HIHATS 流始终无声**。

## 折腾的开始：社区 PR 与回退

### Issue #65 与 PR #66

2026 年 2 月，社区贡献者 [chtzs](https://github.com/chtzs) 在 [Issue #65](https://github.com/wszqkzqk/PvZ-Portable/issues/65) 中指出，动态鼓组/镲片切换的逻辑在实现上与原版行为不符，并且 Intro 场景（大量僵尸走过草坪的过场）会因为僵尸数量超过阈值而错误地触发 Burst。

随后，chtzs 提交了 [PR #66](https://github.com/wszqkzqk/PvZ-Portable/pull/66)，核心改动是：对于方案一的四个关卡，**用单流加逐通道音量控制取代三流架构**。这意味着只加载一份 `mainmusic.mo3`，利用 SDL-Mixer-X 的 `Mix_ModMusicStreamSetChannelVolume` API 对 30 个通道分别设置音量——旋律通道始终满音量，鼓组和镲片通道根据 Burst 状态独立淡入淡出。PR 同时修复了 Intro 场景的误触发问题。

笔者在 review 后合并了这个 PR。

### 回退

然而，合并之后笔者产生了疑虑。原版游戏确实附带了一个专门的 `mainmusic_hihats.mo3` 文件——如果原版就是用逐通道音量控制，为什么还需要这个文件？它的存在似乎印证了三流架构才是原版设计。此外，笔者当时认为 BASS 库可能无法在单个 MOD 实例内对不同通道组（鼓组 vs 镲片）设置不同的流级淡入速率，因此三流架构是原版的必选方案。

基于以上判断，笔者在当天（2026-02-23）回退了 PR #66 的合并。不过，其中 Intro 场景误触发的修复确实是正确的。笔者将该修复以不同的方式重新实现——不再在 `StartBurst()` 内部检查 `mGameMode`，而是在 `UpdateMusicBurst()` 函数的最开头加入 guard clause：

```cpp
void Music::UpdateMusicBurst()
{
    if (mApp->mBoard == nullptr)
        return;
    if (mApp->mGameMode == GameMode::GAMEMODE_INTRO)
        return;
    // ...
}
```

这样既保持了 `StartBurst()` 的单一职责，又在检测原点处过滤掉了 Intro 场景。

## Issue #80：用户报告音频异常

回退后不久，有用户在 [Issue #80](https://github.com/wszqkzqk/PvZ-Portable/issues/80) 中报告了关卡音乐的异常：镲片听起来不正常、选卡界面有多余的低音嗡鸣等问题。这促使笔者重新审视三流架构在 SDL-Mixer-X 下的实际表现。

经过测试和排查，笔者发现三流架构在 SDL-Mixer-X + OpenMPT 后端下存在一个根本性问题：**当多个 MOD 实例分别加载自同一个 `.mo3` 文件时，如果它们在通道上有重叠的采样范围，SDL-Mixer-X 无法正确渲染这些实例的音频**。具体表现就是 HIHATS 流虽然在播放，但输出始终为静音。

回顾泳池关卡的通道映射——鼓组和镲片在 18–24 号通道上重叠，这意味着 DRUMS 实例和 HIHATS 实例在这些通道上持有相同的采样数据。在 BASS 库中，每个实例拥有独立的解码器状态，不会互相干扰；但在 SDL-Mixer-X 的 OpenMPT 后端实现中，从同一文件分别加载的多个模块实例在重叠通道上的渲染出了问题，最终导致镲片流的输出被吞掉。

这解释了为什么在三流架构下，方案一的关卡虽然可以听到旋律和鼓组的淡入淡出，但镲片始终缺失。所以，社区 PR 的方向其实是正确的——**在 SDL-Mixer-X 下，单流是更好的选择**。

## 尝试修复三流架构

在完全转向单流方案之前，笔者也尝试过在保留三流的前提下修复问题。在 `multi-stream-mod` 分支上，笔者做了以下工作：

### 实现 Tempo 同步 API

三流架构的一个核心需求是保持三个 MOD 实例的播放进度同步。原版代码通过微调 BPM 来实现——如果某个流比基准流快了几行（row），就略微降低其 BPM，反之则加速。

首先笔者发现了原有同步逻辑中的一个**方向错误**：当 `aDiff < 0`（即从属流落后于主流）时，代码错误地将 BPM 减小（减速），应该是增大（加速）才对。此外，由于 SDL-Mixer-X 原生的 BPM 控制不够灵活，笔者在 OpenMPT codec 层面实现了 **Tempo Factor API**：

```cpp
// music_openmpt.c
static void OPENMPT_SetTempo(void *music_p, double tempo) {
    OPENMPT_Music *music = (OPENMPT_Music *)music_p;
    if (music && music->dl.openmpt_module_get_ctls)
        ext_interactive->set_tempo_factor(music->module, tempo);
}
```

这利用了 OpenMPT 的 `openmpt_ext_interactive` 扩展接口中的 `set_tempo_factor` 方法，可以以乘法比例调整播放速度。对应的 `GetTempo` 和上层的 `Mix_SetMusicTempo` / `Mix_GetMusicTempo` 也一并实现。

### 为什么三流方案仍然失败

虽然 Tempo 同步 API 本身工作正常，三流架构的根本问题——HIHATS 流静音——并没有因此得到解决。这不是同步的问题，而是 SDL-Mixer-X / OpenMPT 后端在处理共享重叠通道范围的多个模块实例时的渲染缺陷。即使同步完美，镲片流的输出仍然为空。

因此，笔者决定放弃三流方案，转向单流方案。

## 最终方案：单流 + 逐通道音量

### 核心思路

最终实现的核心非常简洁：对于方案一的四个关卡（白天、泳池、雾夜、屋顶），只加载一份 `mainmusic.mo3`，利用 `Mix_ModMusicStreamSetChannelVolume` 对 30 个通道逐一设置音量。一个新的 `SetupVolumeForTune` 函数承担了所有通道分配工作：

```cpp
void Music::SetupVolumeForTune(MusicTune theMusicTune,
                               float theDrumsVolume,
                               float theHihatsVolume)
{
    constexpr const int TRACK_COUNT = 30;
    int aMainEnd = 29;
    int aDrumsStart = -1, aDrumsEnd = -1;
    int aHihatsStart1 = -1, aHihatsEnd1 = -1;
    int aHihatsStart2 = -1, aHihatsEnd2 = -1;

    switch (theMusicTune)
    {
    case MusicTune::MUSIC_TUNE_DAY_GRASSWALK:
        aMainEnd = 23;
        aDrumsStart = 24;  aDrumsEnd = 26;
        aHihatsStart1 = 27; aHihatsEnd1 = 27;
        break;
    case MusicTune::MUSIC_TUNE_POOL_WATERYGRAVES:
        aMainEnd = 17;
        aDrumsStart = 18;  aDrumsEnd = 28;
        aHihatsStart1 = 18; aHihatsEnd1 = 24;
        aHihatsStart2 = 29; aHihatsEnd2 = 29;
        break;
    // FOG, ROOF 类似...
    }

    Mix_Music* aHMusic = GetMusicHandle(MusicFile::MUSIC_FILE_MAIN_MUSIC);
    for (int aTrack = 0; aTrack < TRACK_COUNT; aTrack++)
    {
        float aVolume;
        if (aTrack <= aMainEnd)
            aVolume = 1.0f;
        else
        {
            bool isDrums  = (aTrack >= aDrumsStart && aTrack <= aDrumsEnd);
            bool isHihats = (aTrack >= aHihatsStart1 && aTrack <= aHihatsEnd1) ||
                            (aTrack >= aHihatsStart2 && aTrack <= aHihatsEnd2);
            if (isDrums && isHihats)
                aVolume = std::max(theDrumsVolume, theHihatsVolume);
            else if (isDrums)
                aVolume = theDrumsVolume;
            else if (isHihats)
                aVolume = theHihatsVolume;
            else
                aVolume = 0.0f;
        }
        Mix_ModMusicStreamSetChannelVolume(aHMusic, aTrack, (int)(aVolume * 128));
    }
}
```

函数接受当前曲目、鼓组音量和镲片音量三个参数，根据曲目查找通道映射表，然后遍历 30 个通道，按角色设置音量。对于泳池关卡中鼓组和镲片重叠的通道（18–24），取两者音量的较大值——这正确还原了原版行为。

### 方案二（黑夜关卡）保持双流

值得注意的是，黑夜关卡（NIGHT_MOONGRAINS）仍然使用**双流**架构。这是因为方案二的旋律和鼓组位于 MOD 文件的不同 Order 位置（旋律 `0x30`、鼓组 `0x5C`），需要两个独立的播放指针分别从不同位置开始播放——这是逐通道音量控制无法替代的，必须使用两个流。但由于这里只涉及 MAIN 和 DRUMS 两个流（不存在第三个 HIHATS 流），不会触发 SDL-Mixer-X 的重叠通道渲染问题。

### 代码的简化

单流方案带来了显著的代码简化：

- **移除了 HIHATS 流的加载**：不再需要加载 `mainmusic_hihats.mo3`，也不需要第三份 MOD 实例
- **移除了 HIHATS 流的停止、暂停、恢复和同步逻辑**：`StopAllMusic`、`GameMusicPause`、`MusicResync` 等函数中不再需要处理 HIHATS
- **简化了方案一的 Burst 处理**：`UpdateMusicBurst` 中方案一的代码现在只需调用一次 `SetupVolumeForTune`，传入当前鼓组和镲片的目标音量即可
- **减少了加载任务数**：`MusicInit` 中不再加载 HIHATS 文件，`GetNumLoadingTasks` 对应减少

最终，[Music.cpp](https://github.com/wszqkzqk/PvZ-Portable/blob/one-stream-music-sdl-mixer-x/src/Lawn/System/Music.cpp) 从约 730 行减少到约 699 行。行数减少不多，但移除的是分散在多个函数中的同步、暂停恢复等复杂逻辑，新增的 `SetupVolumeForTune` 则是集中且清晰的通道映射。

## 技术总结

### 为什么 BASS 下三流可行，SDL-Mixer-X 下不行

BASS 音频库为每个加载的 MOD 实例维护完全独立的解码器状态。即使两个实例来自同一个 `.mo3` 文件，它们的通道渲染互不干扰。因此，原版游戏可以将 `mainmusic.mo3` 加载三次，每次只让对应角色的通道发声，三个流各自独立输出。

SDL-Mixer-X 使用 OpenMPT 作为 MOD 解码后端。在测试中，通过从相同 `.mo3` 文件分别加载的多个模块实例在共享重叠通道范围时无法正确渲染音频。具体表现为 HIHATS 流始终静音。这是由 SDL-Mixer-X / OpenMPT 在处理多实例模块时的行为差异导致的。

### 单流方案为什么在 SDL-Mixer-X 下可行

SDL-Mixer-X 提供了 `Mix_ModMusicStreamSetChannelVolume(Mix_Music*, int channel, int volume)` API，可以对正在播放的单个 MOD 实例的指定通道设置音量（0–128）。这意味着不需要多个实例来实现不同通道组的独立音量控制——在一个实例内就能完成。这正是 BASS 用 `BASS_ATTRIB_MUSIC_VOL_CHAN` 实现的功能，但 BASS 缺少在单实例内对不同通道组设置不同**流级**音量的能力，所以原版才需要三流。而在单流方案下，流级音量的概念被完全替代为逐通道音量，从而绕过了这一限制。

## 曲目切换时的音符残留

单流方案解决了通道级音量控制的问题，但很快又暴露了另一个一直存在的音频细节缺陷。在 [Issue #84](https://github.com/wszqkzqk/PvZ-Portable/issues/84) 中，有听觉敏锐的用户报告选卡界面（Choose Your Seeds）的音乐开头存在不应出现的多余音符——特别是从泳池等关卡返回选卡界面时，能听到短暂的残留音符混入了选卡旋律。笔者自己反复试听后并未明显感知到这一问题，但用户提供了详细的复现描述，经过代码分析后确认了问题的存在。

### 问题分析

用户描述的复现路径是：先进入泳池关卡（音乐从 Order `0x5E` 开始），战斗一段时间后退出，再进入选卡界面（音乐切换到 Order `0x7A`）。此时选卡音乐的开头会短暂混入前一关卡的残留音符。

所有关卡切换都共享同一条代码路径——`PlayFromOffset`：

```cpp
void Music::PlayFromOffset(MusicFile theMusicFile, int theOffset, double theVolume)
{
    // ...
    Mix_HaltMusicStream(aMusicInfo->mHMusic);         // 1. 停止当前流
    // ...
    Mix_PlayMusicStream(aMusicInfo->mHMusic, -1);     // 2. 重新播放（从头）
    Mix_ModMusicStreamJumpToOrder(aMusicInfo->mHMusic, theOffset);  // 3. 跳转到目标 order
    // ...
}
```

步骤 3 的 `JumpToOrder` 最终调用 libopenmpt 的 `openmpt_module_set_position_order_row`——这是一个 **seek** 操作。问题在于：在默认配置下，libopenmpt 执行 seek 时会尝试**同步采样播放状态**——即保留所有正在发声的音符，使得 seek 后音频听起来"连续"。这种行为对于在同一首曲子内前后拖动播放进度条是合理的，但对于在 MOD 文件中**跨曲目跳转 Order** 来说是有问题的：上一首曲目中尚未衰减完毕的音符会被"带到"新曲目的开头，形成可感知的音频瑕疵。

### 对比原版行为与 BASS 文档

原版游戏在切换曲目时没有这个问题。查阅原版所用的 [BASS 音频库公开文档](https://www.un4seen.com/doc/#bass/BASS_MusicLoad.html)，可以发现 `BASS_MusicLoad` API 提供了一个名为 `BASS_MUSIC_POSRESET` 的标志，其功能描述为：

> Stop all notes when moving position.

即在改变播放位置时，立刻停止所有正在发声的音符。这意味着从 Order A 跳到 Order B 时，A 中残留的音符不会泄漏到 B。可以合理推测，原版游戏在加载 MOD 音乐时启用了这个标志——这正是一个使用 MOD 文件存储多首曲目并通过 Order 跳转来切换曲目的程序应有的配置。

### 在 libopenmpt 中找到等价方案

确认了预期行为后，下一步是在 libopenmpt 中找到对应的机制。查阅 `libopenmpt.h` 头文件中 `openmpt_module_get_ctls` 的文档，可以找到这个控制选项：

> `seek.sync_samples` (boolean): Set to "0" to not sync sample playback when using `openmpt_module_set_position_seconds` or `openmpt_module_set_position_order_row`.

| 值 | 行为 |
|----|------|
| `1`（默认） | seek 时同步采样播放——保留所有正在发声的音符，使音频连续 |
| `0` | seek 时**不同步采样播放**——停止所有音符，等价于 BASS 的 `BASS_MUSIC_POSRESET` |

将 `seek.sync_samples` 设为 `0`，正是 `BASS_MUSIC_POSRESET` 在 libopenmpt 中的等价行为。

### 修复实现

修复只需要在 SDL-Mixer-X 的 OpenMPT codec 层面添加一行设置。在 `music_openmpt.c` 的 `OPENMPT_CreateFromRW` 函数中，模块创建完成后立即设置：

```c
openmpt.openmpt_module_set_repeat_count(music->file, -1);
/* Equivalent to BASS_MUSIC_POSRESET: stop all notes when seeking */
openmpt.openmpt_module_ctl_set_boolean(music->file, "seek.sync_samples", 0);
```

这里使用的是 `openmpt_module_ctl_set_boolean`（自 libopenmpt 0.5.0 起可用），而非已弃用的字符串版本 `openmpt_module_ctl_set`。该设置为模块级别的全局配置，一旦设定，对该模块所有后续的 seek 操作均生效——包括 `openmpt_module_set_position_order_row`（对应 `JumpToOrder`）和 `openmpt_module_set_position_seconds`（对应 `OPENMPT_Seek`），覆盖了游戏中所有的曲目跳转路径。

由于使用了动态加载框架，还需要在 `openmpt_loader` 结构体中注册函数指针，并在 `OPENMPT_Load` 中通过 `FUNCTION_LOADER` 宏加载符号：

```c
// 结构体中
int (*openmpt_module_ctl_set_boolean)(openmpt_module *mod, const char *ctl, int value);

// OPENMPT_Load() 中
FUNCTION_LOADER(openmpt_module_ctl_set_boolean,
    int (*)(openmpt_module *mod, const char *ctl, int value))
```

整个修复仅 +4 行代码。

### 回归风险分析

这个修复虽然简洁，仍需要确认不会引入回归：

- **首次播放是否丢失开头音符？** 不会。`OPENMPT_Play` 调用 `seek(0.0)` 时，模块刚由 `openmpt_module_ext_create_from_memory` 创建，尚未渲染任何音频，没有正在发声的音符可以被停止。
- **循环播放是否受影响？** 正面影响——循环重播时 seek 回起点会停止上一轮遗留的音符，这恰好是 `BASS_MUSIC_POSRESET` 的预期行为。
- **libopenmpt 版本兼容性？** `openmpt_module_ctl_set_boolean` 自 0.5.0（2020 年发布）起可用。项目使用静态链接（`-DOPENMPT_STATIC`），缺少此符号会在编译阶段报链接错误，不会产生运行时隐患。vcpkg 提供的 libopenmpt 0.7.x+ 远超此要求。

## 致谢

感谢社区贡献者 [chtzs](https://github.com/chtzs) 在 Issue #65 和 PR #66 中的分析与修复——虽然当时被笔者回退了，但其核心思路（单流 + 逐通道音量控制）最终被验证为正确方向，为最终方案提供了重要参考。

## ⚠️ 版权与说明

**重要：本项目仅包含代码引擎，不包含任何游戏素材！**

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中：

*   `main.pak`
*   `properties/` 目录

本项目仅提供引擎代码，用于技术学习，**不包含**上述任何游戏资源文件，任何游戏资源均需要用户自行提供正版游戏文件。

本项目的源代码以 [**LGPL-3.0-or-later**](https://www.gnu.org/licenses/lgpl-3.0.html) 许可证开源，欢迎学习和贡献。
