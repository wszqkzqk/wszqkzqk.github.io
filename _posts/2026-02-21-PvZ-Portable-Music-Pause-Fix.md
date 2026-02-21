---
layout:       post
title:        PvZ-Portable：修复 MOD 音乐暂停恢复倒退与鼓点泄露
subtitle:     从 Stop+Replay 到 PauseMusic/ResumeMusic，以及 Order/Row 精度与通道数边界的修复
date:         2026-02-21
author:       wszqkzqk
header-img:   img/games/bg-pvz-portable.webp
catalog:      true
tags:         C++ 跨平台 媒体文件 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

PvZ-Portable 使用通过 SDL Mixer X 集成 libopenmpt 来播放原版《植物大战僵尸》中的 MOD 格式背景音乐（`.mo3` 文件）。MOD 音乐不同于常规的流式音频（如 OGG、MP3），它采用的是**音序器格式**（Tracker format）：将乐曲划分为若干个 **Order**（乐曲段号），每个 Order 对应一个 **Pattern**（乐谱），Pattern 内部由逐行（**Row**）的音符事件组成。

PvZ 的音乐系统利用 MOD 格式的这一特性来实现动态配乐：将旋律和鼓点/镲片分别放在同一个 MOD 文件的不同**通道**中，在游戏进行时根据战斗强度实时切换通道的静音/取消静音，让鼓点在激烈战斗时渐入、战斗结束后渐出。

然而，笔者在日常测试中逐步发现并修复了三个相互关联的音乐播放问题（PR [#61](https://github.com/wszqkzqk/PvZ-Portable/pull/61)，Merge commit [9d6fec8](https://github.com/wszqkzqk/PvZ-Portable/commit/9d6fec842aa36fbed764485500bd55b20457b769)）：

1. **暂停/恢复时音乐倒退**：打开游戏菜单暂停后恢复，音乐会倒退几秒——这是最先被注意到的问题，也是整个修复的起点。
2. **存档恢复音乐位置不精确**：在修复暂停/恢复逻辑的过程中，笔者发现 save/load 路径仍依赖旧的 Order 定位机制，Row 精度缺失会导致读档后音乐同样倒退，因此一并改进了 Order/Row 打包精度。
3. **鼓点/镲片泄露**：在提交前两项修复后的回归测试中，笔者注意到泳池关卡一进入就能听到镲片声，与预期的"超过 10 个僵尸后才渐入鼓点"行为不符。追查后发现这是一个**长期存在于主分支上的旧 bug**——通道数差一错误。

## 问题一：暂停/恢复导致音乐位置倒退

### 现象

当玩家在关卡中按 Esc 打开菜单（触发 `GameMusicPause(true)`），然后关闭菜单恢复游戏（触发 `GameMusicPause(false)`）时，背景音乐会明显倒退几秒，跳到当前这段旋律的开头。

### 旧实现：Stop + Replay

修复前，`GameMusicPause` 对 MOD 音乐的处理方式是**停止 + 重播**：暂停时先记录当前 Order 号，然后停止音乐；恢复时从记录的 Order 号开始重新播放。

```cpp
// 修复前的 GameMusicPause
void Music::GameMusicPause(bool thePause)
{
    if (thePause) {
        if (!mPaused && mCurMusicTune != MusicTune::MUSIC_TUNE_NONE) {
            if (mCurMusicTune == MusicTune::MUSIC_TUNE_CREDITS_ZOMBIES_ON_YOUR_LAWN) {
                // OGG 格式的 Credits 使用 SDL 的真暂停
                mMusicInterface->PauseMusic(mCurMusicFileMain);
            } else {
                // MOD 格式：记录 Order 后停止播放
                mPauseOffset = GetMusicOrder(mCurMusicFileMain);
                mMusicInterface->StopMusic(mCurMusicFileMain);
                // 停止鼓点和镲片音轨...
                mMusicInterface->StopMusic(mCurMusicFileDrums);
                mMusicInterface->StopMusic(mCurMusicFileHihats);
            }
            mPaused = true;
        }
    }
    else if (mPaused) {
        if (mCurMusicTune == MusicTune::MUSIC_TUNE_CREDITS_ZOMBIES_ON_YOUR_LAWN) {
            mMusicInterface->ResumeMusic(mCurMusicFileMain);
        } else {
            // 从保存的 Order 位置重新开始播放
            PlayMusic(mCurMusicTune, mPauseOffset, mPauseOffsetDrums);
        }
        mPaused = false;
    }
}
```

### 根因：Stop + Replay 不适用于 SDL Mixer X

这套 Stop + Replay 方案存在两个层面的问题：

**第一层（根本原因）：Stop 本身会破坏播放状态。** SDL Mixer X 的 `StopMusic` 会销毁 libopenmpt 内部的播放上下文，包括通道音量状态、混音器状态等。即使位置信息完全精确，重新 `PlayFromOffset` 后还需要重新设置所有通道的静音/取消静音（`SetupMusicFileForTune`），而多个音轨（旋律/鼓点/镲片各自是独立的 MOD 文件实例）之间的同步也无法保证完全一致——Stop 和 Replay 之间存在不可避免的时间差。

**第二层（加剧因素）：`GetMusicOrder` 只返回 Order，丢失了 Row。** 一个 Order 对应一个完整的 Pattern，通常包含 64 行或更多。以 4/4 拍、125 BPM、Speed 6 的典型设置为例，一个 64 行的 Pattern 大约持续 **7.68 秒**。如果玩家在某个 Pattern 播放到第 48 行（约 5.76 秒处）时暂停，`GetMusicOrder` 记录下的只是这个 Pattern 的 Order 号，Row 信息丢失了。恢复播放时，`PlayFromOffset` 从该 Order 的第 0 行开始播放，音乐于是倒退了约 5.76 秒。

旧的 `OPENMPT_GetOrder` 实现确实只返回了 Order：

```c
// 旧 OPENMPT_GetOrder 实现
static int OPENMPT_GetOrder(void *context, int *outOrder)
{
    OPENMPT_Music *music = (OPENMPT_Music *)context;
    *outOrder = openmpt.openmpt_module_get_current_order(music->file);
    return 0;
}
```

相应地，旧的 `OPENMPT_Jump` 也只接受 Order，始终从第 0 行开始播放：

```c
// 旧 OPENMPT_Jump 实现
static int OPENMPT_Jump(void *context, int order)
{
    OPENMPT_Music *music = (OPENMPT_Music *)context;
    openmpt.openmpt_module_set_position_order_row(music->file, order, 0);
    return 0;
}
```

不过在这个情况下，即使 `OPENMPT_GetOrder` 返回了完整的 Order + Row 信息，暂停/恢复仍然会有问题：`StopMusic` 会销毁 libopenmpt 内部的播放上下文，Replay 后需要重新初始化所有通道状态，多音轨之间也无法保证精确同步。因此，真正的修复应当从根本上避免 Stop + Replay。

### 修复方案：统一使用原生 Pause/Resume

最直接的修复是：**对所有 MOD 音乐也使用 SDL Mixer X 的原生 `PauseMusic`/`ResumeMusic`，替代 Stop + Replay。**

旧代码只对 OGG 格式的 Credits 音乐使用了真暂停，对 MOD 格式则因历史原因（最初从 BASS 音频库迁移过来），沿用了 Stop + Replay 的笨办法。

修复后的 `GameMusicPause`：

```cpp
// 修复后的 GameMusicPause
void Music::GameMusicPause(bool thePause)
{
    if (thePause) {
        if (!mPaused && mCurMusicTune != MusicTune::MUSIC_TUNE_NONE) {
            // 保留 offset 信息（用于存档兼容）
            if (mCurMusicFileMain != MusicFile::MUSIC_FILE_NONE &&
                mCurMusicTune != MusicTune::MUSIC_TUNE_CREDITS_ZOMBIES_ON_YOUR_LAWN)
            {
                mPauseOffset = GetMusicOrder(mCurMusicFileMain);
            }
            if (mCurMusicTune == MusicTune::MUSIC_TUNE_NIGHT_MOONGRAINS &&
                mCurMusicFileDrums != MusicFile::MUSIC_FILE_NONE)
            {
                mPauseOffsetDrums = GetMusicOrder(mCurMusicFileDrums);
            }

            // 统一对所有音轨使用真暂停
            if (mCurMusicFileMain != MusicFile::MUSIC_FILE_NONE)
                mMusicInterface->PauseMusic(mCurMusicFileMain);
            if (mCurMusicFileDrums != MusicFile::MUSIC_FILE_NONE)
                mMusicInterface->PauseMusic(mCurMusicFileDrums);
            if (mCurMusicFileHihats != MusicFile::MUSIC_FILE_NONE)
                mMusicInterface->PauseMusic(mCurMusicFileHihats);

            mPaused = true;
        }
    }
    else if (mPaused) {
        // 恢复播放
        Mix_Music* aHandle = (mCurMusicFileMain != MusicFile::MUSIC_FILE_NONE) ?
                              GetMusicHandle(mCurMusicFileMain) : nullptr;
        if (mCurMusicTune == MusicTune::MUSIC_TUNE_CREDITS_ZOMBIES_ON_YOUR_LAWN ||
            (aHandle && Mix_PlayingMusicStream(aHandle)))
        {
            // 音乐仍处于暂停/播放状态，直接恢复
            if (mCurMusicFileMain != MusicFile::MUSIC_FILE_NONE)
                mMusicInterface->ResumeMusic(mCurMusicFileMain);
            if (mCurMusicFileDrums != MusicFile::MUSIC_FILE_NONE)
                mMusicInterface->ResumeMusic(mCurMusicFileDrums);
            if (mCurMusicFileHihats != MusicFile::MUSIC_FILE_NONE)
                mMusicInterface->ResumeMusic(mCurMusicFileHihats);
        }
        else {
            // Save-load 恢复路径：音乐已被销毁，需要重新播放
            PlayMusic(mCurMusicTune, mPauseOffset, mPauseOffsetDrums);
        }
        mPaused = false;
    }
}
```

改动要点：

1. **暂停时**不再 Stop 任何音轨，对所有活跃的音轨统一调用 `PauseMusic`。同时仍然记录 `mPauseOffset`，以便存档中保存位置信息。
2. **恢复时**通过 `Mix_PlayingMusicStream` 检查音乐是否仍然存在于 SDL Mixer X 的播放队列中。如果是（正常的暂停/恢复流程），直接 `ResumeMusic`；如果不是（说明是从存档加载后的恢复，音乐对象已被销毁），走旧的 `PlayMusic` 路径，从保存的 Order 位置重新播放。

## 问题二：Order/Row 打包精度

### 动机

在完成暂停/恢复的统一修复后，笔者注意到虽然正常的暂停/恢复现在使用了原生 Pause/Resume，不再丢失位置信息，但 save/load 路径仍然需要将音乐位置信息序列化到存档中——存档保存时调用 `GameMusicPause(true)` 记录 `mPauseOffset`，读档后通过 `PlayMusic` 从保存的 offset 恢复播放。如果 offset 只包含 Order 而丢失 Row，读档后音乐依然会倒退。

此外，游戏中的 `MusicResyncChannel` 函数需要比较不同音轨之间的 **Row 差值**来微调同步（这是原版 BASS 音频库的设计约定：返回值的高 16 位是 Row，低 16 位是 Order）。在旧的 `OPENMPT_GetOrder` 只返回 Order 的实现下，Row 差值始终为 0，使得 resync 逻辑形同虚设。

### 修复方案：将 Row 打包进返回值

修改 `OPENMPT_GetOrder` 和 `OPENMPT_Jump`，采用高低位打包格式：**低 16 位存储 Order，高 16 位存储 Row**。

```c
// 修复后的 OPENMPT_GetOrder（packed: LOWORD=order, HIWORD=row）
static int OPENMPT_GetOrder(void *context, int *outOrder)
{
    OPENMPT_Music *music = (OPENMPT_Music *)context;
    int32_t order = openmpt.openmpt_module_get_current_order(music->file);
    int32_t row = openmpt.openmpt_module_get_current_row(music->file);
    *outOrder = (int)((((uint32_t)row & 0xFFFF) << 16) | ((uint32_t)order & 0xFFFF));
    return 0;
}

// 修复后的 OPENMPT_Jump
static int OPENMPT_Jump(void *context, int order)
{
    OPENMPT_Music *music = (OPENMPT_Music *)context;
    int32_t ord = (int32_t)((uint32_t)order & 0xFFFF);
    int32_t row = (int32_t)(((uint32_t)order >> 16) & 0xFFFF);
    openmpt.openmpt_module_set_position_order_row(music->file, ord, row);
    return 0;
}
```

这样，当 save/load 路径通过 `PlayFromOffset` 恢复音乐时，`Mix_ModMusicStreamJumpToOrder` 会把打包值传给 `OPENMPT_Jump`，后者解包出 Order 和 Row，即可把播放位置精确定位到断点处，不会产生倒退。

与此配合，`MusicUpdate` 中比较 Order 时需要加上 `& 0xFFFF` 掩码来提取纯 Order 值（只使用低 16 位），避免 Row 信息干扰 Order 比较：

```cpp
// 修复前：直接比较（未区分打包格式）
aOrderMain = aPackedOrderMain;
aOrderDrum = mQueuedDrumTrackPackedOrder;

// 修复后：提取低16位作为 Order
aOrderMain = aPackedOrderMain & 0xFFFF;
aOrderDrum = mQueuedDrumTrackPackedOrder & 0xFFFF;
```

## 问题三：通道数边界错误导致鼓点泄露

### 现象

在提交了暂停/恢复统一修复和 Order/Row 精度改进后，笔者对各关卡进行回归测试。进入泳池关卡（Pool）时，发现**一进入关卡就能听到镲片声**，而此时屏幕上还没有任何僵尸——按照设计，鼓点和镲片应当在场上僵尸超过 10 个时才由 `UpdateMusicBurst` 渐入。

### 根因：`aTrackCount` 差一错误

使用 `openmpt123 --info` 查看 MOD 文件的元信息，确认 `mainmusic.mo3` 和 `mainmusic_hihats.mo3` 各有 **30 个通道**（编号 0–29）：

```
$ openmpt123 --info sounds/mainmusic.mo3
Type.......: mo3 (Un4seen MO3 v1)
Orig. Type.: xm (FastTracker 2)
Channels...: 30
Orders.....: 236
Patterns...: 200
```

然而 `SetupMusicFileForTune` 函数负责在播放开始时设置每个通道的音量——需要发声的通道设为满音量，其余通道设为静音——其中所有 `switch-case` 分支中的 `aTrackCount` 都被设为了 `29`：

```cpp
// 修复前
case MusicTune::MUSIC_TUNE_DAY_GRASSWALK:
    switch (theMusicFile) {
    case MusicFile::MUSIC_FILE_MAIN_MUSIC:
        aTrackCount = 29; aTrackStart1 = 0; aTrackEnd1 = 23; break;
    case MusicFile::MUSIC_FILE_HIHATS:
        aTrackCount = 29; aTrackStart1 = 27; aTrackEnd1 = 27; break;
    case MusicFile::MUSIC_FILE_DRUMS:
        aTrackCount = 29; aTrackStart1 = 24; aTrackEnd1 = 26; break;
    } break;
```

设置音量的循环为 `for (int aTrack = 0; aTrack < aTrackCount; aTrack++)`，`aTrackCount = 29` 意味着循环只处理通道 0–28，**跳过了通道 29**。

通道 29 从未被设置为静音，因此无论当前播放的是哪首曲子的哪个文件实例，通道 29 始终保持 libopenmpt 的默认音量（满音量）。在泳池关卡中，HIHATS 配置明确将通道 29 分配给镲片（`aTrackStart2 = 29, aTrackEnd2 = 29`），但由于循环到不了这个通道，该赋值形同虚设——通道 29 在**所有三个文件实例**（MAIN_MUSIC、DRUMS、HIHATS）中都以满音量播放，导致原本只有 HIHATS 实例该播的内容通过 MAIN_MUSIC 也被播了出来。其他关卡虽然通道 29 上也可能有数据，但泳池关卡的影响最为明显。

这是一个经典的**差一错误（off-by-one error）**。在原版游戏的 BASS 音频库实现中，虽然使用了同样的 `aTrackCount = 29`，但 BASS 的 `BASS_ATTRIB_MUSIC_VOL_CHAN + aTrack` 属性设置的行为可能有所不同（例如可能全部通道默认静音，或通道编号从 1 开始）。迁移到 SDL Mixer X + libopenmpt 后，libopenmpt 的通道默认音量为满音量、编号从 0 开始，`aTrackCount` 必须覆盖全部 30 个通道才能正确静音未使用的通道。

### 修复

将所有 `aTrackCount = 29` 改为 `aTrackCount = 30`（共涉及 20 处 `switch-case` 赋值和 1 处 `default` 分支），确保循环覆盖全部 30 个通道（0–29）：

```cpp
// 修复后
case MusicTune::MUSIC_TUNE_DAY_GRASSWALK:
    switch (theMusicFile) {
    case MusicFile::MUSIC_FILE_MAIN_MUSIC:
        aTrackCount = 30; aTrackStart1 = 0; aTrackEnd1 = 23; break;
    case MusicFile::MUSIC_FILE_HIHATS:
        aTrackCount = 30; aTrackStart1 = 27; aTrackEnd1 = 27; break;
    case MusicFile::MUSIC_FILE_DRUMS:
        aTrackCount = 30; aTrackStart1 = 24; aTrackEnd1 = 26; break;
    } break;
```

## 三个修复的关系

这三个问题虽然表现不同，但根源上都指向同一个主题：**从 BASS 音频库迁移到 SDL Mixer X + libopenmpt 后，MOD 音乐控制逻辑未被充分适配。**

从开发时间线上看，它们是逐步被发现和修复的：

| 阶段 | 问题 | 根因 | 修复 |
| :--- | :--- | :--- | :--- |
| 起点 | 暂停/恢复倒退 | 沿用 BASS 时代 Stop+Replay 方式，不适用于 SDL Mixer X | 统一使用 `PauseMusic`/`ResumeMusic` |
| 重构中发现 | 位置精度丢失 | `OPENMPT_GetOrder` 只返回 Order，丢失 Row | 打包 Order+Row 进同一个 `int`，匹配原版 BASS 的 `MAKELONG(order, row)` 格式 |
| 回归测试中发现 | 鼓点泄露 | `aTrackCount=29` 遗漏通道 29 | 修正为 `aTrackCount=30` |

## 结语

MOD 音乐的动态配乐系统是 PvZ-Portable 中十分精妙的设计之一。将它从 Windows 专属的 BASS 音频库迁移到跨平台的 SDL Mixer X + libopenmpt 组合后，虽然核心的音序器回放和通道控制能力得到了保留，但上层的暂停/定位/静音控制逻辑需要针对新后端的接口契约逐一适配。

这次修复的过程本身也很有代表性：从一个明显的暂停倒退 bug 出发，在重构过程中发现了 Order/Row 精度的缺失，最后在回归测试中又牵出了一个长期潜伏的通道数边界错误。三个问题环环相扣、逐步浮现，体现了音频迁移工作中常见的"冰山效应"——表面上的一个小问题下面，往往藏着更多需要适配的细节。
