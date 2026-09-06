---
layout:       post
title:        PvZ-Portable：消除音乐表的数据竞争
subtitle:     加载线程、逐帧遍历与递归互斥锁
header-img:   img/games/pvz-portable/bg-pvz-portable.webp
date:         2026-09-06
author:       wszqkzqk
catalog:      true
tags:         多线程 C++ 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

PvZ-Portable 的资源加载在后台线程进行：启动后主线程继续跑更新循环、绘制加载界面和进度条，加载线程则读取资源包、解码图片和音频。这套架构在之前的博客里出现过几次——[WebAssembly 适配](https://wszqkzqk.github.io/2026/03/10/PvZ-Portable-WebAssembly-Adaptation/)时曾因为浏览器的单线程模型把它同步化，[确定性回放](https://wszqkzqk.github.io/2026/07/22/PvZ-Portable-Demo-Deterministic-Replay/)则用 `IsOnPrimaryThread()` 把 demo 命令流的读写限制在主线程。

两个线程同时存活，就有共享状态的同步问题。这条线上的问题已经修过几轮：加载线程从 detach 改成 join（[#359](https://github.com/wszqkzqk/PvZ-Portable/pull/359)），进度计数、完成标志等跨线程读写的变量改成了 `std::atomic`（[#439](https://github.com/wszqkzqk/PvZ-Portable/pull/439)）。剩下的共享数据里，最扎眼的是音乐接口里的一张 `std::map`：加载线程会往里插入条目，主线程每次更新都在遍历它，全程没有任何同步。笔者最近把这张表的所有访问点用一把互斥锁串了起来（[#468](https://github.com/wszqkzqk/PvZ-Portable/pull/468)），这篇记录一下这个竞争的具体形态，以及修复时的几个取舍。

## 两个线程各自在碰这张表

音乐接口 `SDLMusicInterface` 用一个公开的 `std::map` 保存所有已加载的音乐（`src/SexyAppFramework/sound/SDLMusicInterface.h`）：

```cpp
class SDLMusicInfo
{
public:
	Mix_Music*				mHMusic;
	double					mVolume;
	double					mVolumeAdd;
	double					mVolumeCap;
	bool					mStopOnFade;
	...
};

typedef std::map<int, SDLMusicInfo> SDLMusicMap;
```

主线程这边，`SexyAppBase::UpdateFrames()` 每次更新都会调用 `mMusicInterface->Update()`。`Update()` 遍历整张表，推进每首音乐的音量渐变——淡入淡出不是一次性调用，而是靠这个逐帧的 tick 完成的：

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

注意这个调用在加载期间不会停：`DoUpdateFrames()` 不管加载是否完成，每帧都会走到 `UpdateFrames()`，加载界面的动画和音乐接口的 tick 都靠它驱动。

加载线程这边，`LawnApp::LoadingThreadProc()` 在加载末尾调用 `mMusic->MusicInit()`，预加载主音乐模块 `mainmusic.mo3` 和片尾曲 `ZombiesOnYourLawn.ogg`，把解码的开销放在加载阶段完成。每个文件最终都走进 `Music::PvzpLoadMusic`，在表里插入一个条目（`src/Lawn/System/Music.cpp`，修复前）：

```cpp
	aHMusic = Mix_LoadMUS_RW(SDL_RWFromMem(aData, aSize), 1);
	...
	SDLMusicInfo aMusicInfo;
	aMusicInfo.mHMusic = aHMusic;
	anSDL->mMusicMap.insert(SDLMusicMap::value_type(theMusicFile, aMusicInfo));  // 加载线程执行
	return true;
```

于是，一个线程在 `insert`，另一个线程同时在 `begin()` 到 `end()` 之间迭代，中间没有任何同步设施。

## 竞争到底错在哪

熟悉 `std::map` 的读者可能会说：`insert` 不会让已有迭代器失效，遍历应该是安全的。这个保证确实存在，但它的前提是**没有并发修改**。C++ 标准对容器线程安全的承诺只有两条：并发的只读访问是安全的，以及不同对象上的操作互不影响。对同一个对象，一个线程写、另一个线程读，就是数据竞争，行为未定义——迭代器失不失效的问题根本轮不到讨论。

落到实现上，`std::map` 是红黑树。`insert` 可能触发旋转，重写若干节点的父子指针；而另一个线程的迭代器自增，走的正是这些指针。两边重叠时，迭代器可能顺着改到一半的链接走进错误的子树，重复访问、跳过条目，或者解引用一个指针正在被改写的节点。即使侥幸遍历完了，`Update()` 还会读写节点里的 `mVolume`、拿 `mHMusic` 去调 SDL_mixer，而此时加载线程可能正把同一个 `SDLMusicInfo` 拷贝进节点。

这种 bug 最麻烦的地方在于它几乎不出现。整个加载过程只插入两个条目，每次 `insert` 本身是纳秒级操作；真正耗时的文件读取和 `Mix_LoadMUS` 解码都在插入之前完成，不在竞争窗口里。桌面平台上加载一闪而过，两个线程的访问大概率永远不会重叠。就算真的重叠，崩溃栈也会停在 `Update()` 的遍历循环里，看上去和音乐加载毫无关系，排查时很难把两者联系起来。

但窗口小不等于安全。在加载更慢的 Android、Switch 设备上，加载阶段更长，主线程的更新次数更多，重叠概率随之上升；这些平台的 ARM 内存序也比桌面 x86 弱，x86 上被强内存模型掩盖的竞争，在 ARM 上更容易表现为可见的错误。而且这类问题用 ThreadSanitizer 检查时不依赖时序窗口：它报告的是两次访问之间缺少 happens-before 关系，只要执行到这两条路径就必然报警。

## 修复：所有访问点共享一把锁

修复本身不复杂：在 `SDLMusicInterface` 里给这张表配一把互斥锁，每个访问点进入前先拿锁（`src/SexyAppFramework/sound/SDLMusicInterface.h`）：

```cpp
class SDLMusicInterface : public MusicInterface
{
public:
	SDLMusicMap				mMusicMap;
	std::recursive_mutex	mMusicMapMutex;
	...
```

框架层的 18 个方法——`LoadMusic`、`PlayMusic`、`StopMusic`、`PauseMusic`、`ResumeMusic`、`StopAllMusic`、`UnloadMusic`、`UnloadAllMusic`、`PauseAllMusic`、`ResumeAllMusic`、`FadeIn`、`FadeOut`、`FadeOutAll`、`SetSongVolume`、`SetSongMaxVolume`、`IsPlaying`、`Update`、`GetMusicOrder`——全部在入口处加 `std::scoped_lock`。

游戏层也躲不开。`mMusicMap` 是公开成员，`Music` 类有 4 处绕过接口直接访问它：`PvzpLoadMusic`、`GetMusicHandle`、`PlayFromOffset` 和 `MusicCreditScreenInit`。锁因此只能和 map 一样公开，两个层共用同一把。直接暴露成员是这套框架的老设计，它让锁也不得不成为公共设施；更彻底的做法是把访问收敛进接口内部，但那要改动的调用面大得多，这次先把正确性补上。

真正存在跨线程竞争的，其实只有一对访问：加载线程的 `insert` 和主线程 `Update()` 的遍历，其余入口大多只会在主线程被调用。给它们也加上锁，不是为了修当前的 bug，而是把“哪些访问需要同步”从一条需要逐点论证的隐式约定，变成“访问这张表就必须持锁”的机械规则。以后新增调用点时，不用再重新论证一次它跑在哪个线程。

### 锁只包住必要的一段

值得注意的是 `PvzpLoadMusic` 里锁的位置（修复后）：

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

文件读取和 `Mix_LoadMUS` 解码都在锁外完成，临界区只有 `insert` 一行。加载线程解码音频文件时，主线程的 `Update()` 不会被堵住；两边真正会互相等待的，只有遍历一张最多几个条目的表和一次插入这种微秒级操作。这张表的竞争本来就接近于零，锁的代价可以忽略。

### 为什么是 recursive_mutex

普通互斥锁在这里会自己咬到自己：`UnloadMusic` 持锁后内部调用 `StopMusic`，`UnloadAllMusic` 持锁后调用 `StopAllMusic`，而被调用的函数也要拿同一把锁。非递归互斥锁下，这就是确定性的自死锁。

```cpp
void SDLMusicInterface::UnloadMusic(int theSongId)
{
	std::scoped_lock anAutoCrit(mMusicMapMutex);

	StopMusic(theSongId);   // 内部再次 scoped_lock 同一把锁
	...
```

更教科书式的解法是把每个函数拆成公有的加锁包装和私有的无锁实现两层，内部调用只走无锁版本。但对一张竞争几乎为零的表，这种拆法要给每个相关函数都多出一层，换来的只是省掉递归锁在无竞争时那一次额外的原子计数。`std::recursive_mutex` 在这里是成本和侵入性都更合理的选择。

## 同一架构下的一轮收紧

这次修复不是孤立的。加载线程这套“后台加载、前台渲染”的架构保留至今，围绕它的共享数据访问规则在一轮轮收紧：先把 detach 的加载线程改成 joinable，既修掉了 Switch 上 `detach()` 抛异常导致的崩溃，也保证加载线程不会比它访问的资源管理器活得更久；再把进度计数、完成标志等跨线程变量改成 `std::atomic`；确定性回放又进一步规定，凡是进 demo 命令流的 I/O 只允许发生在主线程。音乐表是这条线上最后一块没有同步的共享数据。

这类问题没有银弹，排查方法却很固定：找出两个线程都能到达的数据，枚举它的全部访问点，挨个标注访问发生在哪个线程。标注做完，问题通常会自己浮出来——这次的 `insert` 和遍历，就是在这张清单上碰面的。

## 结语

后台线程加载、主线程遍历共享容器，是 GUI 程序和游戏里最常见的并发模式之一，也是数据竞争最高发的形状。容器文档里“此操作不使迭代器失效”一类的保证，从来不覆盖并发修改；只要两个线程能同时碰到同一个对象，同步就是调用方的责任。

这个 bug 从移植第一天起就存在，但它几乎不可能被玩家触发并报告：窗口太小，崩溃栈又指向不相干的地方。数据竞争的危险程度和出现概率从来不成比例——越难复现的竞争，越只能靠枚举访问点这种笨办法挖出来；而挖出来之后，修复往往只是一把锁，加上一条“所有访问都在锁内”的纪律。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。研究或使用此项目时，**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies)购买）。你需要从正版游戏中提取以下文件，放到 PvZ-Portable 的程序所在目录：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
