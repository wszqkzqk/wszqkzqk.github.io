---
layout:       post
title:        PvZ-Portable：构建可复现的游戏录制与回放系统
subtitle:     从时区、音频时钟与 RNG 流等多个角度，保证录制和回放在任何机器上都能逐 tick 复现
header-img:   img/games/bg-pvz-portable.webp
date:         2026-07-22
author:       wszqkzqk
catalog:      true
tags:         确定性回放 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

PvZ-Portable 沿用的 SexyAppFramework 引擎里，留着 PopCap 当年设计的一套 demo 录制/回放机制：把一局游戏录成 `.dmo` 文件，之后原样放出来。它原本的定位是**调试和回归工具**：录下一段会话，之后复现出来，配合 `DEMO_ASSERT_INT_EQUAL` 这类断言命令和 marker 检查点，用来抓崩溃、验证修复。

但是，原版框架的录制**从来都不是真正可复现的**。它只把输入和时间戳大致记下来，回放时的随机数消耗序列并没有任何保障——简单场景还能大致对上，到了无尽模式这种对象密集、随机数消耗密集的对局，跑不了多久就会跑偏。差一次 RNG 消耗，之后所有随机决策全部错位，失之毫厘谬以千里，拿它做严格复现根本不可靠。

此外，原来的 SexyAppFramework 的录制系统 Windows 时代的实现，并非 SDL 这套机制。而到了 PvZ-Portable 的 SDL 移植里，这套机制剩下的骨架尚未实现完成：输入根本没被录制，回放时真实输入也没人拦，demo buffer 的加载时机还是错的——录出来的文件放回去，游戏停在主菜单一动不动。

所以笔者最近**重新构建了一整套基于 SDL 的可复现录制/回放系统**，一共三个 PR：[#369](https://github.com/wszqkzqk/PvZ-Portable/pull/369) 重建输入的录制与回放通路，[#375](https://github.com/wszqkzqk/PvZ-Portable/pull/375) 把墙钟时间变成确定性的，[#379](https://github.com/wszqkzqk/PvZ-Portable/pull/379) 消除剩余的不确定性来源，同一份 `.dmo` 在任何平台、任何时区回放，都能**逐 tick 复现录制时的状态**——包括无尽模式这种原版录制从来不指望能对上的场景。

现在，这套系统的能力其实已经超出了调试工具的定位：`.dmo` 里只有输入事件、随机种子和时间信息，不含任何画面数据，体积天然**比视频录屏小不知道多少个数量级**，而确定性保证让任何人拿到文件都能放出分毫不差的同一局。也就是说，它完全可以当作**游戏录像**来用——录一局精彩的无尽发给朋友，对方 `-play` 一下就能看到原汁原味、没有任何转码压缩的完整对局。

## Demo 系统的基本结构

先交代一下这套系统长什么样。其中文件格式和命令流的骨架沿用了原框架的设计，输入通路和全部确定性保障则是这次新建的。demo 文件是一个全小端的二进制流，开头依次是文件 ID、`DEMO_VERSION`、随机种子 `mRandSeed`（回放时用它 `SRand` 恢复全局 RNG）、会话开始时间、时区偏移、产品版本字符串、marker 列表，最后是一段 **bit 级的命令流**。

命令流里的每条命令带一个 4 bit 的 tick 增量时间戳，然后是命令本体：鼠标微移用 6 bit 增量压缩，鼠标按键、键盘、注册表读写、文件读写各有命令号。回放时主循环在消息处理前调 `ProcessDemo()`，按 tick 把流里的输入事件逐条回注给 `WidgetManager`，跟真人操作走同一条路径。

最关键的设计是 **IO 同步**：`RegistryRead`、`WriteBytesToFile` 这些调用在录制时会把结果写进流，回放时调用点不认真实注册表和文件系统，而是从流里读回录制时的结果。这样回放就不依赖宿主机器上的存档状态——哪怕换一台没玩过这游戏的电脑，回放看到的"存档"也和录制时一模一样。

整个系统确定性的根基只有一条：**游戏全局只有一个 Mersenne Twister 实例，而回放用同一个种子**。只要每次运行消耗的随机数个数和顺序完全一致，整局游戏就是逐 tick 确定的。

反过来，MT 是顺序流，任何一个地方多消耗或少消耗一个值，之后所有的随机决策——僵尸出怪、植物行为、掉落物——全部错位。后面要讲的每一处问题，本质都是某个决策点依赖了非确定因素，导致 RNG 消耗次数不稳定。

## 重建输入的录制与回放通路

[#369](https://github.com/wszqkzqk/PvZ-Portable/pull/369) 解决的是能否工作这一层，问题有四个：

之前的 SDL 输入层里没有任何 demo 相关代码——移植时只保住了 IO 同步命令，鼠标键盘事件从不写入流。修复是在输入层加 `RecordDemoEvent`，把 SDL 事件翻译成 demo 命令，格式与 `ProcessDemo` 的读取严格镜像：

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

之前的事件循环在回放时照常在分发用户的鼠标键盘事件，动一下鼠标就往游戏里注入了流外输入，确定性当场报废。修复后回放模式下只放行窗口管理事件，其余全部丢弃：

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

之前 `Init()` 在 `ReadFromRegistry()` **之后**才调 `ReadDemoBuffer()`，而回放模式下注册表读取是 demo-synced 的——它从一个还没加载的空 buffer 里读命令，流一开始就错位了。修复后 buffer 在任何 demo-synced 操作之前加载。

此外，资源加载线程也会走注册表和文件 IO 路径，这些线程上 demo 命令的读写顺序相对主线程是不确定的。修复是把所有 demo-synced IO 用 `IsOnPrimaryThread()` 门控，非主线程走真实 IO、不进流。

到这里，录制和回放能跑通一个简单会话了。但只要会话稍微长一点、跨一点场景，回放就会在中段悄悄跑偏——剩下的问题全都出在时间上。

## 把墙钟变成 tick 的函数

游戏里依赖真实时间的地方比想象中多：商店的金盏花每天限购、禅境花园按日历日刷新浇水施肥需求、购买记录的时间戳、`Board::mGameID` 的生成……这些在录制时是一个值，回放时换成另一个时刻再跑一遍，得到的必然是另一个游戏。

[#375](https://github.com/wszqkzqk/PvZ-Portable/pull/375) 的解法是把所有 demo 可见的时间查询收敛到同一个出口（`SexyAppBase.h`）：

```cpp
// Demo-synced wall clock: real time normally; session start time advanced by update ticks during demo record/playback
inline time_t			GetNowTime() const
{
    if (IsInDemoMode())
        return static_cast<time_t>(mDemoStartTime) + mUpdateCount / 100;
    return time(nullptr);
}
```

`mDemoStartTime` 在录制时取真实时刻并写进 demo 头（v4），回放时从头里恢复。于是 demo 会话里的现在实际上是录制时刻 + 已流逝的 tick 数（引擎 100 tick/秒），完全确定，还跟游戏节奏严格同步。正常游戏不受影响，照样读真实时间。

同一批要处理的还有依赖**渲染帧时序**的检查。引擎的 update（逻辑）和 draw（渲染）是解耦的，draw 的节奏**随机器性能漂移**，凡是拿 `mDrawCount` 当条件的地方都可能会造成无法确定的结果。比如关卡 intro 的预加载门，原来写的是 `mDrawCount == 0`，改成按一个独立于场景的 `mBoardUpdateCounter` 判断（`CutScene.cpp`）：

```cpp
if (mApp->mGameScene != GameScenes::SCENE_LEVEL_INTRO || mBoard->mBoardUpdateCounter <= 1) // the first frame is drawn after the first update tick, so defer one tick deterministically
	return;
```

原来的写法是同样的位置判断 `mBoard->mDrawCount == 0`。

首帧绘制确定性地落在首个 update 之后，推迟一拍，回放时不再受渲染调度影响。泳池闪光粒子、limbo 页面连点解锁的毫秒间隔（从 `SDL_GetTicks()` 改成 20 个 update tick 计 200ms）也一并改挂到 tick 上。

## 清扫剩余导致回放不一致的因素

到这一步回放已经能稳定跑完常规对局了，但 [#379](https://github.com/wszqkzqk/PvZ-Portable/pull/379) 又揪出了一批更隐蔽的不一致来源。

### 时区：日历日逻辑跨时区不一致

`GetNowTime` 只解决了"时刻"的确定性，没解决"日历日"的。商店限购和禅境花园的需求刷新比较的是 `tm_year` / `tm_yday`，这要求把时刻换算成本地日期——而 `localtime` 按**回放宿主的时区**换算。在另一个时区的机器上回放，同一时刻可能落在不同的日历日，商店补货状态、植物需求状态随之不同，代码路径不同，RNG 消耗次数不同，流就错位了。

修复是录制时把`本地时间 − UTC`的秒数写进 demo 头，回放时用 `gmtime(clock + 偏移)` 重建录制者的本地日历日（`SexyAppBase.h`）：

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

偏移量的计算没有用任何时区数据库，就是录制瞬间 `localtime` 的分解字段与 UTC 秒数做差，仅包含确定的算术运算；`gmtime` 前置 0 的钳制是为了照顾 MSVC 对公元前时间的拒绝。禅境花园和商店里所有 `localtime` 调用点全部改走这个出口，回放从此与宿主时区彻底解耦。

### 音频时钟：最典型的一条 RNG 错位链

这是整轮修复里笔者觉得最有意思的一处不确定性来源。音效的触发是消耗 RNG 的——`TodFoley::PlayFoley` 里音高、播放音效的变体选择都要取随机数。

游戏逻辑在决定是否触发一个音效之前，首先检测：**这个音效还在播吗？**也就是说，下一条音效是否播放，会取决于 `SoundInstance::IsPlaying()` 的返回值。

旧的 `IsPlaying()` 读的是 `Mix_Playing(mChannel)`，也就是**真实音频硬件的播放进度**。这在正常游戏里天经地义，但对回放是个问题：真实世界的播放进度是不确定的——音频线程怎么调度、机器跑多快，两次回放不可能完全一样。于是在同一个 tick 上，每一次运行都可能处于不同的播放状态，得到不同答案，**后面的 RNG 消耗次数便会跟着不同**，随机数产生便不再与录制时一致了。

笔者的修复则是**把还在不在播这个逻辑判定，从真实时钟对齐到确定的 tick 时间轴上。**

`Play()` 是游戏逻辑调用的，它发生的 tick 本身就是确定的；音效的时长也是已知的，通过音频 chunk 长度除以 pitch 就能计算。所以 `Play()` 时就能算出这个音效**理论上应该在哪个 tick 结束**，存进 `mDemoEndUpdateCount`；之后 `IsPlaying()` 不再问音频硬件，只拿 `mUpdateCount` 跟这个结束 tick 比较：

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

注意，在这里真实的声音该怎么播还怎么播，用户体验没有任何变化——音频实际结束得比折算的 tick 早几毫秒或晚几毫秒根本不要紧，游戏逻辑不关心，它只认 tick 时间轴上的答案。同一个 tick 在复现中结果永远相同，RNG 消耗序列就稳定了。

### 排队命令与分歧检测：让回放在出错时停在原地

还有一类结构性问题。文件/注册表命令是游戏逻辑私有的：`ProcessDemo` 在命令记录的 tick 读到命令头，但配对的 `WriteBytesToFile` / `RegistryRead` 调用可能发生在同一 tick 更晚的调用栈里——比如商店购买经模态对话框确认，`WaitForResult` 退栈之后才写盘，这个写盘不在输入注入的调用栈内。

旧代码里这种命令头掉进 `default` 分支，payload 没人消费，后续所有命令从 payload 中段开始解码成垃圾，游戏拿着垃圾输入乱点菜单，直到撞上某个被误解码出来的 `DEMO_CLOSE` 才把进程杀掉——出错了也不告诉你错在哪。

修复是把这类命令**排队**：`ProcessDemo` 遇到它们时回退 bit 位置和流时钟，自己不消费，把命令留给游戏逻辑的调用点来处理：

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

精确复现的回放里，排队命令一定在同一个 tick 内被它的调用点处理掉；如果它**跨过一个完整的 tick 还没被处理**，就说明那次调用根本不会来了——游戏状态已经真实偏离了录制。这时直接 `Shutdown()`，回放停在确切出问题的命令处，而不是带着垃圾数据继续演。配套的改动是把命令处理的 tick 比较从 `==` 放宽到 `>=`，游戏时钟超过流时钟时不死锁；Emscripten 下 `Dialog::WaitForResult` 拿到结果后停止抽取嵌套 update，保证对话框之后的 IO 能在同一 tick 处理掉自己的命令。

同一个排队机制，同 tick 内重复遇到是正常流程（放行等待），跨 tick 仍未被处理就是分歧（立即终止）——一这样的设计既实现了宽容正常时序，又做到了尽早暴露错误。

### MTRand 序列化补全

同一 PR 里还把 `MTRand` 的状态序列化修完整了：状态向量改为 `uint32_t`、逐字小端编码（原来是 `memcpy`，字节序相关），并且**把 `mti` 索引也纳入序列化**。旧实现恢复状态时不恢复 `mti`，下次取随机数会强制重新 twist 整块状态——任何发生在"块中间"的保存/恢复都会错位。目前树内还没有调用点，算是为以后的 RNG 检查点/恢复能力提前做的准备。

## 结语

现在，PvZ-Portable 有了一套真正可复现的录制/回放系统：跨平台、跨时区逐 tick 确定，包括无尽模式这种原版框架的录制从来没法保证播放一致性的场景。

**确定性是一种全局性质，不能漏一个点。** RNG 种子固定只能保证"消耗序列一致时结果一致"，而消耗序列会被任何非确定因素扰动：真实墙钟、宿主时区、渲染帧节奏、音频线程进度、对话框的调用栈时序……每一处都得揪出来锚定到 tick 上。这类工作没有捷径，只能一个一个来源地排查——好在 demo 系统自带断言命令和 marker，验证手段就在工具本身里。

**逻辑可见的状态和真实设备的状态要分开。** 音频那处的修法很说明问题：不需要让音频线程变得确定，那既不现实也没必要，只需要让游戏逻辑**查询**到的播放状态从确定性时钟推导。设备性能肯定是不确定的，但逻辑可以照常确定，只需要中间夹一层换算。

**谨慎看待容错设计，尽早暴露问题。** 调试工具的价值一半在于能复现，另一半就在于复现失败时告诉你断在哪——后者经常被忽视，但真到排查分歧的时候，这就是几小时和几分钟的差别。

从原版框架里一个不可靠的遗留功能，到跨平台逐 tick 确定的录制系统，再到一个可以直接拿来分享对局的录像格式——这套机制现在的样子，大概是当年设计它的人也没想到过的。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
