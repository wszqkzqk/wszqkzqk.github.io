---
layout:       post
title:        PvZ-Portable：构建可复现的游戏录制与回放系统
subtitle:     从时区、音频时钟与 RNG 流入手，让录制内容在任何机器上都能逐 tick 复现
header-img:   img/games/pvz-portable/bg-pvz-portable.webp
date:         2026-07-22
author:       wszqkzqk
catalog:      true
tags:         确定性回放 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

PvZ-Portable 沿用的 SexyAppFramework 引擎中，保留着 PopCap 当年设计的一套 demo 录制/回放机制：将一局游戏录成 `.dmo` 文件，之后再完整回放。它原本是一种**调试和回归测试工具**：先录下一段会话，之后复现当时的过程，再配合 `DEMO_ASSERT_INT_EQUAL` 之类的断言命令和 marker 检查点来捕捉崩溃、验证修复。

但是，原版框架的录制**从来没有做到真正可复现**。它只粗略记录输入和时间戳，却无法保证回放时随机数的消耗顺序与录制时一致——简单场景或许还能大致吻合，到了无尽模式这类对象众多、随机数调用频繁的对局，往往很快就会出现偏差。只要多消耗或少消耗一次 RNG，之后的所有随机决策都会错位，可谓失之毫厘，谬以千里。因此，用它来做严格复现并不可靠。

此外，原版 SexyAppFramework 的录制系统是针对 Windows 实现的，并不基于 SDL。到了 PvZ-Portable 的 SDL 移植版本中，这套机制只剩下尚未补完的骨架：输入根本没有被录制，回放时也不会屏蔽真实输入，demo buffer 的加载时机甚至还是错的——把录好的文件拿来回放，游戏只会停在主菜单，毫无动静。

因此，笔者最近**重新构建了一整套基于 SDL 的可复现录制/回放系统**，相关工作分为三个 PR：[#369](https://github.com/wszqkzqk/PvZ-Portable/pull/369) 重建输入录制与回放通路，[#375](https://github.com/wszqkzqk/PvZ-Portable/pull/375) 将墙钟时间确定化，[#379](https://github.com/wszqkzqk/PvZ-Portable/pull/379) 消除其余不确定性来源。如今，同一份 `.dmo` 无论在哪个平台、哪个时区回放，都能**逐 tick 复现录制时的状态**——即便是无尽模式这种原版录制系统根本无法保证一致性的场景也不例外。

现在，这套系统的能力其实已经超出了调试工具的范畴，完全可以用作**游戏录像**。与视频录屏相比，`.dmo` 只包含输入事件、随机种子和时间信息，不含任何画面数据，因此体积极小。一段几分钟的游戏，经录屏软件录制后，视频动辄有几百 MB；对应的 `.dmo` 通常却只有几 KB，相差好几个数量级。更重要的是，demo 不需要压缩画面。回放时，引擎会实时重新运行同一局游戏，以原生分辨率渲染，不会产生转码和压缩带来的画质损失；即使更换平台或时区，回放结果也分毫不差。录下一局精彩的无尽模式并发给朋友，对方只需用 `-play` 启动，就能看到原汁原味的完整对局。

## Demo 系统的基本结构

先简要介绍一下这套系统的结构。文件格式和命令流的基本框架沿用了原有设计，输入通路和完整的确定性保障则是在这次工作中重新构建的。demo 文件是一个完全采用小端序的二进制流，开头依次记录文件 ID、`DEMO_VERSION`、随机种子 `mRandSeed`（回放时将它传给 `SRand`，恢复全局 RNG）、会话开始时间、时区偏移、产品版本字符串和 marker 列表，最后则是一段 **bit 级命令流**。

命令流中的每条命令都带有一个 4 bit 的 tick 增量时间戳，后面紧跟命令本体：鼠标小幅移动使用 6 bit 增量编码，鼠标按键、键盘、注册表读写和文件读写则各有相应的命令号。回放时，主循环会在处理消息前调用 `ProcessDemo()`，按 tick 将命令流中的输入事件逐条重新注入 `WidgetManager`，让它们与玩家的真实操作经过同一条处理路径。

其中最关键的设计是 **I/O 同步**：录制时，`RegistryRead`、`WriteBytesToFile` 等调用会将结果写入命令流；回放时，相应的调用点不再访问真实的注册表和文件系统，而是直接读取录制时保存的结果。这样，回放便不再依赖宿主机器上的存档状态——即使换到一台从未运行过这款游戏的电脑上，回放所看到的“存档”也与录制时完全相同。

整个系统的确定性建立在一个前提之上：**游戏全局只有一个 Mersenne Twister 实例，且回放使用与录制时相同的种子**。只要每次运行所消耗的随机数数量和顺序完全一致，整局游戏就能做到逐 tick 确定。

反过来说，MT 生成的是顺序流；任何地方只要多消耗或少消耗一个值，之后所有涉及随机性的决策——僵尸出怪、植物行为、物品掉落——都会错位。后文提到的每一处问题，本质上都是某个决策点受到了非确定性因素的影响，导致 RNG 的消耗次数不稳定。

## 重建输入的录制与回放通路

[#369](https://github.com/wszqkzqk/PvZ-Portable/pull/369) 先解决最基础的问题：让这套系统真正运行起来。相关修复有四项。

此前的 SDL 输入层没有任何与 demo 相关的代码——移植过程中只保留了 I/O 同步命令，鼠标和键盘事件从未写入命令流。为此，笔者在输入层加入 `RecordDemoEvent`，将 SDL 事件转换为 demo 命令，其编码格式与 `ProcessDemo` 中的读取逻辑严格对应：

```cpp
case SDL_KEYDOWN:
{
    ...
    theApp->WriteDemoTimingBlock();
    theApp->mDemoBuffer.WriteNumBits(0, 1);
    theApp->mDemoBuffer.WriteNumBits(DEMO_KEY_DOWN, 5);
    theApp->mDemoBuffer.WriteNumBits(static_cast<int>(SDLKeyToKeyCode(theEvent.key.keysym.sym)), 8);
    ...
}
```

此前，事件循环在回放时仍会照常分发用户的鼠标和键盘事件。哪怕只是移动一下鼠标，也会向游戏注入命令流之外的输入，立即破坏确定性。修复后，回放模式只允许窗口管理事件通过，其余事件全部丢弃：

```cpp
if (mPlayingDemoBuffer)
{
    // Input is replayed from the demo stream; only window-management events are handled
    switch (event.type)
    {
        case SDL_QUIT: CloseRequestAsync(); break;
        case SDL_WINDOWEVENT: ...
    }
    return SDL_HasEvents(SDL_FIRSTEVENT, SDL_LASTEVENT);
}
```

此前，`Init()` 要等到 `ReadFromRegistry()` **之后**才调用 `ReadDemoBuffer()`；然而，回放模式下的注册表读取需要与 demo 同步，这就使程序试图从尚未加载的空 buffer 中读取命令，导致命令流从一开始便发生错位。修复后，buffer 会在执行任何 demo-synced 操作之前加载。

此外，资源加载线程同样会访问注册表和文件 I/O 路径，而这些线程读写 demo 命令的顺序相对于主线程并不确定。解决办法是使用 `IsOnPrimaryThread()` 限制所有 demo-synced I/O：只有主线程参与命令流的读写，其他线程则访问真实 I/O，不进入命令流。

至此，录制和回放已经可以跑通一段简单的会话。但只要会话稍长或切换了场景，回放仍会在中途悄然偏离——剩下的问题都与时间有关。

## 将墙钟时间映射到 tick

游戏中依赖真实时间的地方比想象中更多：商店中的金盏花每日限购、禅境花园按日历日刷新浇水和施肥需求、购买记录的时间戳，以及 `Board::mGameID` 的生成……如果这些逻辑在录制时读取一个值，回放时又在另一个时刻重新计算，得到的游戏状态必然不同。

[#375](https://github.com/wszqkzqk/PvZ-Portable/pull/375) 的解决方案，是让所有会影响 demo 的时间查询统一经过同一个接口（`SexyAppBase.h`）：

```cpp
// Demo-synced wall clock: real time normally; session start time advanced by update ticks during demo record/playback
inline time_t			GetNowTime() const
{
    if (IsInDemoMode())
        return static_cast<time_t>(mDemoStartTime) + mUpdateCount / 100;
    return time(nullptr);
}
```

录制时，程序会读取真实时间并将其存入 `mDemoStartTime`，再写入 v4 版 demo 文件头；回放时则从文件头中恢复该值。因此，demo 会话中的“当前时间”实际等于“录制开始时间 + 已流逝 tick 换算出的秒数”（引擎以 100 tick/秒运行）。这个结果不仅完全确定，也与游戏进度严格同步。正常游戏不受影响，仍然读取真实时间。

同时还要处理那些依赖**渲染帧时序**的检查。引擎中的 update（逻辑更新）与 draw（画面渲染）彼此解耦，而 draw 的节奏会**随机器性能而变化**。因此，凡是以 `mDrawCount` 为条件的逻辑，都可能产生不确定的结果。例如，关卡 intro 的预加载条件原本是 `mDrawCount == 0`，后来改为依据不受场景切换影响的 `mBoardUpdateCounter` 判断（`CutScene.cpp`）：

```cpp
if (mApp->mGameScene != GameScenes::SCENE_LEVEL_INTRO || mBoard->mBoardUpdateCounter <= 1) // the first frame is drawn after the first update tick, so defer one tick deterministically
	return;
```

原来的写法则是在同一位置判断 `mBoard->mDrawCount == 0`。由于首帧绘制必然发生在第一次 update 之后，这里将预加载推迟一个 tick，便可使回放不再受渲染调度影响。泳池闪光粒子以及 limbo 页面连续点击解锁的时间间隔也一并改为基于 tick 计算；后者由 `SDL_GetTicks()` 改成 20 个 update tick，即 200 ms。

## 消除其余导致回放不一致的因素

完成上述工作后，回放已经能够稳定跑完常规对局。不过，[#379](https://github.com/wszqkzqk/PvZ-Portable/pull/379) 又找出了一批更隐蔽的不一致来源。

### 时区：日历日逻辑跨时区不一致

`GetNowTime` 只保证了“时刻”的确定性，却没有解决“日历日”的问题。商店限购和禅境花园的需求刷新会比较 `tm_year` / `tm_yday`，因此需要将时刻换算为本地日期。然而，`localtime` 会按照**回放设备所在的时区**进行换算。在另一时区的机器上回放时，同一时刻可能对应不同的日历日，商店补货和植物需求状态也会随之改变。代码路径一旦不同，RNG 的消耗次数也会不同，最终导致随机数序列错位。

修复方法是：录制时，将“本地时间 − UTC”的秒数写入 demo 文件头；回放时，再通过 `gmtime(clock + 偏移)` 重建录制者所在时区的日历日期（`SexyAppBase.h`）：

```cpp
inline tm				GetLocalTime(time_t theTime) const
{
    if (IsInDemoMode())
    {
        time_t aShifted = theTime + static_cast<time_t>(mDemoTimeZoneOffset);
        if (aShifted < 0) // MSVC/UCRT gmtime rejects pre-epoch times
            aShifted = 0; // clamp to no earlier than 1970-01-01
        return *gmtime(&aShifted);
    }
    return *localtime(&theTime);
}
```

偏移量的计算不依赖任何时区数据库，而是将录制瞬间由 `localtime` 得到的分解字段与 UTC 秒数作差，整个过程只涉及确定性的算术运算。调用 `gmtime` 前将负数钳制为 0，则是为了兼容 MSVC/UCRT 无法处理 Unix 纪元之前时间的问题。禅境花园和商店中的所有 `localtime` 调用也全部改为经过这个接口，从此，回放结果便与宿主时区彻底解耦。

### 音频时钟：最典型的一条 RNG 错位链

这是整轮修复中笔者认为最有意思的一处不确定性来源。触发音效会消耗 RNG——`TodFoley::PlayFoley` 中的音高和音效变体选择都需要随机数。

游戏逻辑在决定是否触发音效之前，会先检查：**这个音效还在播放吗？**也就是说，是否播放下一条音效，取决于 `SoundInstance::IsPlaying()` 的返回值。

旧版 `IsPlaying()` 读取的是 `Mix_Playing(mChannel)`，也就是**音频播放的实际进度**。这在正常游戏中合情合理，却会给回放带来问题：现实中的播放进度并不确定——音频线程如何调度、机器运行多快，都可能让两次回放产生差异。于是在同一个 tick 上，每次回放的播放状态可能不同，进而得到不同的判断结果，**后续 RNG 的消耗次数也会随之变化**，随机数序列便无法再与录制时保持一致。

笔者的解决办法，是**将“音效是否仍在播放”这一逻辑判断从真实时钟转移到确定的 tick 时间轴上。**

`Play()` 由游戏逻辑调用，因此调用发生在哪个 tick 本身就是确定的；音效时长也可以用音频 chunk 的长度除以 pitch 得出。因此，调用 `Play()` 时便能算出该音效**理论上应在哪个 tick 结束**，并将结果存入 `mDemoEndUpdateCount`。之后，`IsPlaying()` 不再查询音频设备，只需比较 `mUpdateCount` 和结束 tick：

```cpp
bool SDLSoundInstance::IsPlaying()
{
    if (gSexyAppBase->IsInDemoMode()) // see Play(): tick-derived playing state in demo sessions
    {
        if (!mMixChunk || !mHasPlayed || mDemoEndUpdateCount == 0)
            return false;
        if (mDemoLooping)
            return true;
        return gSexyAppBase->mUpdateCount < mDemoEndUpdateCount;
    }
    ...
    return Mix_Playing(mChannel);
}
```

需要注意的是，真实声音的播放方式并未改变，因此用户体验不会受到影响。即使音频实际结束的时间比换算出的 tick 早或晚几毫秒也无关紧要：游戏逻辑只采用 tick 时间轴上的结果，而不关心设备的实际播放状态。这样一来，相同 tick 上的判断结果始终一致，RNG 的消耗序列也就稳定了。

### 命令排队与分歧检测：让回放在出错处停止

此外，还有一类结构性问题。文件和注册表命令由游戏逻辑中的特定调用点负责处理：`ProcessDemo` 会在命令所记录的 tick 读到命令头，但与之配对的 `WriteBytesToFile` / `RegistryRead` 调用，可能要到同一 tick 中更晚的调用栈里才会发生。例如，在商店购买物品时，需要先经过模态对话框确认，等 `WaitForResult` 返回后才会写入磁盘；这项写入操作并不位于输入注入的调用栈中。

在旧代码中，这类命令头会落入 `default` 分支，导致 payload 无人读取。后续命令只能从 payload 中段继续解码，得到一连串无意义的数据；游戏则会把这些垃圾数据当成输入，在菜单中胡乱操作，直到某段数据被误解码成 `DEMO_CLOSE`，进程才会退出。此时不仅回放早已出错，也无法看出分歧最初出现在哪里。

解决办法是将这类命令**暂时排队**：`ProcessDemo` 遇到它们时，会恢复读取前的 bit 位置和命令流时钟，不自行消费命令，将其留给游戏逻辑中对应的调用点处理：

```cpp
case DEMO_REGISTRY_GETSUBKEYS:
case DEMO_REGISTRY_READ:
...
case DEMO_SYNC:
case DEMO_ASSERT_STRING_EQUAL:
case DEMO_ASSERT_INT_EQUAL:
    if (mDemoCommandQueued && mUpdateCount != mDemoQueuedSince) // queued across a tick with no claim: the replay has diverged
    {
        Shutdown();
        return;
    }
    mDemoQueuedSince = mUpdateCount;
    mDemoCommandQueued = true;
    mDemoBuffer.mReadBitPos = mDemoCmdBitPos; // leave queued for the game-logic call site to consume
    mLastDemoUpdateCnt = mDemoCmdUpdateCnt;
    mDemoNeedsCommand = true;
    return;
```

在精确复现的回放中，排队的命令一定会在同一个 tick 内由对应调用点处理。如果一条命令**经过一整个 tick 后仍未被处理**，就说明预期的调用不会再出现——游戏状态已经偏离了录制内容。此时直接调用 `Shutdown()`，便能让回放停在发生问题的确切命令处，而不是继续使用垃圾数据运行。与此配套，命令处理时的 tick 比较也从 `==` 放宽到 `>=`，避免游戏时钟超过命令流时钟后陷入死锁；在 Emscripten 环境下，`Dialog::WaitForResult` 得到结果后也会停止执行嵌套的 update，以确保对话框之后的 I/O 能在同一个 tick 内处理自己的命令。

对于同一套排队机制，在一个 tick 内重复遇到同一条命令属于正常流程，只需继续等待；如果命令跨 tick 后仍未被处理，则说明回放已经产生分歧，应当立即终止。这样的设计既能兼容正常的调用时序，又能尽早暴露错误。

### MTRand 序列化补全

同一个 PR 还补全了 `MTRand` 的状态序列化：状态向量改用 `uint32_t`，逐字按小端序编码（原先直接使用 `memcpy`，结果取决于平台字节序），并且**将 `mti` 索引也纳入序列化**。旧实现恢复状态时不会恢复 `mti`，所以下次获取随机数时会强制对整块状态重新执行 twist；只要保存和恢复发生在状态块中间，随机数序列就会错位。目前项目中还没有相应的调用点，这项改动主要是为将来的 RNG 检查点和状态恢复功能做好准备。

## 结语

现在，PvZ-Portable 已经拥有一套真正可复现的录制/回放系统：它能跨平台、跨时区逐 tick 保持确定性，即使在无尽模式这种原版框架从未保证回放一致性的场景中也同样有效。

**确定性是一种全局性质，任何一个环节都不能遗漏。** 固定 RNG 种子只能保证“消耗序列相同时，结果也相同”，而任何非确定性因素都可能扰乱消耗序列：真实墙钟、宿主时区、渲染帧节奏、音频线程进度、对话框的调用栈时序……每一项都必须找出来，再锚定到 tick 时间轴上。这类工作没有捷径，只能逐一排查不确定性的来源。好在 demo 系统自带断言命令和 marker，验证手段就包含在工具本身之中。

**要将逻辑可见的状态与真实设备的状态分开。** 音频问题的修复很好地说明了这一点：没有必要让音频线程本身变得确定——这既不现实，也无必要。真正需要确定的，只是游戏逻辑**查询**到的播放状态；让它从确定性时钟推导即可。设备性能固然不确定，但只要在两者之间增加一层转换，游戏逻辑仍然可以保持确定。

**容错机制要谨慎设计，问题也要尽早暴露。** 调试工具的价值，一半在于能够复现问题，另一半则在于复现失败时指出分歧发生在哪里。后一点经常被忽视，但真正开始排查时，它足以决定这项工作需要几小时，还是只需几分钟。

从原版框架中一项不可靠的遗留功能，到跨平台、逐 tick 确定的录制系统，再到一种可以直接用于分享对局的录像格式——这套机制如今的形态，大概连当年设计它的人也未曾设想过。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守相关版权规定。《植物大战僵尸》的 IP 归 PopCap/EA 所有。

本项目仅包含开源重实现的引擎代码，**不含任何受版权保护的游戏美术、音效、关卡等资源文件**。研究或使用本项目时，你**必须**拥有正版游戏；如尚未购买，可前往 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 购买。你需要从正版游戏中提取以下文件，并将它们放入 PvZ-Portable 程序所在的目录：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
