---
layout:       post
title:        PvZ-Portable：修复音乐表的数据竞争
subtitle:     后台加载与主线程更新之间的同步
header-img:   img/games/pvz-portable/bg-pvz-portable.webp
date:         2026-09-06
author:       wszqkzqk
catalog:      true
tags:         多线程 C++ 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

PvZ-Portable 会在后台线程中加载资源。游戏启动后，主线程继续更新并绘制加载界面，加载线程则负责读取资源包、解码图片和音频。这套机制在之前的文章里出现过几次。[WebAssembly 适配](https://wszqkzqk.github.io/2026/03/10/PvZ-Portable-WebAssembly-Adaptation/)需要为浏览器的单线程环境改用同步加载，[确定性回放](https://wszqkzqk.github.io/2026/07/22/PvZ-Portable-Demo-Deterministic-Replay/)则通过 `IsOnPrimaryThread()` 将 demo 命令流的读写限制在主线程。

只要两个线程同时运行，就要留意它们访问的共享状态。此前，加载线程已经改为在退出前 `join`（[#359](https://github.com/wszqkzqk/PvZ-Portable/pull/359)），进度计数和完成标志等跨线程变量也改成了 `std::atomic`（[#439](https://github.com/wszqkzqk/PvZ-Portable/pull/439)）。最近检查其余共享数据时，我又发现了音乐接口中的一张 `std::map`：加载线程会向其中插入音乐，主线程则在每次更新时遍历它，二者之间没有同步。

PR [#468](https://github.com/wszqkzqk/PvZ-Portable/pull/468) 为这张表的所有访问加上了互斥锁。本文记录这个数据竞争是怎样产生的，以及修复时为什么选择了递归互斥锁。

## 两个线程在同时访问音乐表

音乐接口 `SDLMusicInterface` 用一张公开的 `std::map` 保存已经加载的音乐（`src/SexyAppFramework/sound/SDLMusicInterface.h`）：

```cpp
class SDLMusicInfo
{
public:
	Mix_Music*             mHMusic;
	double                 mVolume;
	double                 mVolumeAdd;
	double                 mVolumeCap;
	bool                   mStopOnFade;
	...
};

typedef std::map<int, SDLMusicInfo> SDLMusicMap;
```

主线程每次进入 `SexyAppBase::UpdateFrames()`，都会调用 `mMusicInterface->Update()`。音乐的淡入和淡出在这里逐次调整音量，所以 `Update()` 需要遍历整张表：

```cpp
void SDLMusicInterface::Update()
{
	Mix_VolumeMusic(mGlobalVolume);
	Mix_VolumeMusicGeneral(mGlobalVolume);

	SDLMusicMap::iterator anItr = mMusicMap.begin();
	while (anItr != mMusicMap.end())
	{
		SDLMusicInfo* aMusicInfo = &anItr->second;

		if (aMusicInfo->mVolumeAdd != 0.0)
		{
			aMusicInfo->mVolume += aMusicInfo->mVolumeAdd;
			...
			Mix_VolumeMusicStream(aMusicInfo->mHMusic, (int)(aMusicInfo->mVolume*128));
		}

		++anItr;
	}
}
```

资源尚未加载完时，主线程依然会调用 `UpdateFrames()`，否则加载界面的动画和音乐状态都无法继续更新。

与此同时，加载线程会在 `LawnApp::LoadingThreadProc()` 的末尾执行 `mMusic->MusicInit()`，预先加载 `mainmusic.mo3` 和 `ZombiesOnYourLawn.ogg`。文件读取和解码完成后，`Music::PvzpLoadMusic` 会向同一张表插入条目。修复前的代码如下：

```cpp
	aHMusic = Mix_LoadMUS_RW(SDL_RWFromMem(aData, aSize), 1);
	...
	SDLMusicInfo aMusicInfo;
	aMusicInfo.mHMusic = aHMusic;
	anSDL->mMusicMap.insert(SDLMusicMap::value_type(theMusicFile, aMusicInfo));
	return true;
```

这样，加载线程可能正在执行 `insert`，主线程却同时从 `begin()` 遍历到 `end()`。原来的代码没有互斥锁，也没有其他同步手段。

## `insert` 不使迭代器失效，为什么仍然有问题

`std::map::insert` 不会使已有迭代器失效，但这个保证不能用来说明并发访问安全。它描述的是同一线程中前后发生的容器操作。一个线程修改容器、另一个线程同时读取容器，仍然构成数据竞争，程序行为未定义。

从常见实现来看，`std::map` 通常是一棵红黑树。插入节点时可能需要调整树结构，迭代器自增也要沿着节点之间的链接移动。如果两项操作刚好交叠，遍历可能看到尚未调整完的结构。至于具体表现是漏掉条目、访问异常还是看起来一切正常，C++ 标准都不作保证。

这个问题平时很难复现。整个加载过程只向表中插入两个条目，而且文件读取与 `Mix_LoadMUS` 解码都发生在 `insert` 之前。真正发生无同步读写的时间很短，桌面环境中的线程调度往往恰好让两项操作错开。即使偶尔崩溃，调用栈也更可能停在 `Update()` 的遍历中，很难立刻联想到另一个线程的音乐加载。

但无法稳定复现并不代表代码安全。Android、Switch 等设备的性能和线程调度与桌面环境不同，同一个竞争可能表现出不同的结果。ThreadSanitizer 也适合检查这类问题，因为它关注的是访问之间是否建立了正确的同步关系，而不是等待某次运行恰好崩溃。

## 用一把锁保护所有访问

修复方式很直接：为 `mMusicMap` 增加一把互斥锁，访问这张表前先持有锁（`src/SexyAppFramework/sound/SDLMusicInterface.h`）：

```cpp
class SDLMusicInterface : public MusicInterface
{
public:
	SDLMusicMap             mMusicMap;
	std::recursive_mutex    mMusicMapMutex;
	...
```

框架层中会访问音乐表的 18 个方法都增加了 `std::scoped_lock`，包括 `LoadMusic`、`PlayMusic`、`StopMusic`、`UnloadMusic`、`Update` 和 `GetMusicOrder` 等。锁的位置以实际访问范围为准，例如需要读取文件的 `LoadMusic` 只在最后插入条目时持锁。

游戏层还有 4 处代码直接访问公开的 `mMusicMap`，分别是 `PvzpLoadMusic`、`GetMusicHandle`、`PlayFromOffset` 和 `MusicCreditScreenInit`，这些地方也使用同一把锁。由于 `mMusicMap` 原本就是公开成员，互斥锁目前也只能随它一起公开。更理想的设计是把所有访问封装在 `SDLMusicInterface` 内部，不过这会牵涉更大范围的接口调整，这次没有继续展开。

当前真正形成跨线程冲突的是加载线程中的 `insert` 和主线程中的 `Update()`。其余方法大多只在主线程调用，但仍然统一加锁。这样可以把同步要求落实在每个访问点上，今后新增调用时也不必依赖调用者记住某些隐含的线程约定。

### 缩短插入操作的持锁时间

修复后的 `PvzpLoadMusic` 没有一进入函数就加锁，而是等音频解码完成后再锁住音乐表：

```cpp
	aHMusic = Mix_LoadMUS_RW(SDL_RWFromMem(aData, aSize), 1);
	...
	SDLMusicInfo aMusicInfo;
	aMusicInfo.mHMusic = aHMusic;

	std::scoped_lock anAutoCrit(anSDL->mMusicMapMutex);
	anSDL->mMusicMap.insert(SDLMusicMap::value_type(theMusicFile, aMusicInfo));
	return true;
}
```

文件读取和 `Mix_LoadMUS` 解码仍在锁外，加载线程只在插入条目时持锁。因此，音频解码不会长时间阻塞主线程的 `Update()`。音乐表本身很小，两个线程实际互相等待的时间也很有限。

### 为什么使用 `recursive_mutex`

这里不能直接换成普通的 `std::mutex`。`UnloadMusic` 会在持锁期间调用 `StopMusic`，`UnloadAllMusic` 也会调用 `StopAllMusic`，而这些被调用的方法同样需要取得 `mMusicMapMutex`。同一线程第二次锁定普通互斥锁时会造成死锁。

```cpp
void SDLMusicInterface::UnloadMusic(int theSongId)
{
	std::scoped_lock anAutoCrit(mMusicMapMutex);

	StopMusic(theSongId);   // StopMusic 会再次取得 mMusicMapMutex
	...
```

另一种做法是把相关方法拆成两层：公开方法负责加锁，内部的辅助方法假定调用方已经持锁。这样可以继续使用普通互斥锁，但需要重新整理现有方法之间的调用关系。考虑到音乐表很小，访问频率和竞争程度也不高，使用 `std::recursive_mutex` 对现有代码的改动更少。

## 继续整理加载线程的共享状态

音乐表并不是加载线程遇到的第一个同步问题。此前不再 `detach` 加载线程，改为在退出前等待它结束，既解决了 Switch 上 `detach()` 抛出异常的问题，也保证了程序退出时资源管理器不会先于加载线程销毁。之后，进度计数和加载完成标志等变量又改成了 `std::atomic`。确定性回放加入后，demo 命令流的 I/O 也被限制在主线程。

这几次修改处理的是同一类问题：后台线程和主线程之间有哪些共享数据，以及每份数据通过什么方式同步。排查时，我会先找出两个线程都能到达的对象，再列出所有读写位置并标明所在线程。音乐表中的 `insert` 和遍历，就是这样对照出来的。

## 结语

后台线程加载资源、主线程读取资源状态，是游戏和 GUI 程序中很常见的结构。这里容易混淆的是容器对迭代器的保证与容器的线程安全。`std::map::insert` 不使已有迭代器失效，不代表它可以与另一个线程的遍历同时执行。只要同一对象存在并发读写，就需要由调用方建立同步关系。

这处竞争存在了很久，实际触发窗口却很短，所以靠普通测试很难发现。修复代码并不多，主要工作反而是确认所有访问点，并为它们统一一条规则：读写 `mMusicMap` 时必须持有 `mMusicMapMutex`。相比依赖线程调度碰巧错开，这样的约束更容易检查，也更便于以后维护。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。研究或使用此项目时，**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies)购买）。你需要从正版游戏中提取以下文件，放到 PvZ-Portable 的程序所在目录：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
