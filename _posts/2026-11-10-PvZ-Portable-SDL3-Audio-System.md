---
layout:       post
title:        PvZ-Portable：基于 SDL3_mixer 与 SDL_AudioStream 重构音频系统
subtitle:     告别 14 万行 SDL-Mixer-X，用 190 行代码桥接 libopenmpt 动态 MOD 音乐流
header-img:   img/games/pvz-portable/bg-pvz-portable.webp
date:         2026-11-10
author:       wszqkzqk
catalog:      true
tags:         SDL 音频 开源软件 游戏移植 开源游戏 PvZ-Portable
---

## 引言

在[上一篇文章](https://wszqkzqk.github.io/2026/11/09/PvZ-Portable-SDL3-Migration/)中，笔者介绍了 [PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable) 从 SDL2 迁移至 SDL3 的整体脉络。在整个迁移工程（PR [#523](https://github.com/wszqkzqk/PvZ-Portable/pull/523)）中，改动幅度最大、收益也最明显的部分是音频系统。

为了还原《植物大战僵尸》原版基于 `.mo3` 格式的动态关卡音乐与音效变调，项目此前不仅在源码树中内嵌了逾 14.3 万行的 `SDL-Mixer-X`，还在音效管理层维护了手写的 `.au` 解码器与软件重采样变调回调，游戏逻辑层也直接穿透抽象接口去操作底层混音器结构。

本文将记录笔者如何利用 `SDL3_mixer` 的轨道（`MIX_Track`）模型与 SDL3 的音频流（`SDL_AudioStream`）拉取回调机制，用不到 200 行代码实现对 `libopenmpt` 的直连桥接，在保留动态打击乐切换与无残留跳转的前提下，移除内嵌的 `SDL-Mixer-X` 并理顺音频层的接口边界。

## 迁移前的历史包袱

要理解为什么音频层需要重写，可以先看看迁移前代码中存在的三处结构问题。

### 为三个扩展函数内嵌 14 万行 SDL-Mixer-X

在之前的[单流音乐系统博客](https://wszqkzqk.github.io/2026/03/02/PvZ-Portable-Music-System/)中介绍过，游戏的主音乐文件 `mainmusic.mo3` 包含 30 个 tracker 通道，所有关卡的旋律、鼓组与镲片都打包在同一个文件内。引擎在运行时需要三项特殊能力：

- **跳转到指定 Order**：切换关卡曲目，或在黑夜关卡同步鼓组流。
- **读取当前播放的 Order 与 Row**：在双流模式下检查播放进度。
- **逐通道实时调节音量**：在僵尸数量达到阈值触发 Burst 时，对指定的鼓组通道和镲片通道以不同速率独立执行淡入淡出。

标准 `SDL2_mixer` 的 `Mix_Music` 接口将模块解码完全封装在内部，不提供逐通道音量控制（`Mix_ModMusicStreamSetChannelVolume`）与 Order 读写（`Mix_ModMusicStreamJumpToOrder` / `Mix_ModMusicStreamGetOrder`）。为了拿到这三个扩展函数，项目早期将整棵 `SDL-Mixer-X` 源码树直接放进了 `src/SexyAppFramework/sound/SDL-Mixer-X/`。

这棵内嵌源码树体量达 14.3 万行，里面除了项目真正用到的 OpenMPT 后端和 Ogg/MP3/WAV 解码封装外，还包含 ADLMIDI、OPNMIDI、FluidLite、Timidity、PxTone 等十余种合成器源码、大体积的音色表头文件（仅 `gm_opn_bank.h` 单文件就有 1.55 万行）以及测试数据。而且，此前在[单流音乐系统](https://wszqkzqk.github.io/2026/03/02/PvZ-Portable-Music-System/)中为了消除切歌音符残留而设置 `seek.sync_samples = 0` 时，还不得不直接修改这棵第三方源码树里的 `music_openmpt.c`。

### 游戏层穿透 MusicInterface 抽象

在框架设计上，`SexyAppBase` 定义了平台无关的纯虚基类 `MusicInterface`，理应由子类 `SDLMusicInterface` 隐藏所有 SDL 相关的实现细节。但在旧代码中，游戏逻辑层的 `src/Lawn/System/Music.cpp` 却直接包含了 `<SDL_mixer_ext/SDL_mixer_ext.h>`，并在多处将 `mApp->mMusicInterface.get()` 向下强转为 `SDLMusicInterface*`，直接读写子类内部的 `mMusicMap` 和 `mMusicMapMutex`：

```cpp
// 旧代码：src/Lawn/System/Music.cpp 直接穿透抽象层操作 Mix_Music 与 mMusicMap
bool Music::PvzpLoadMusic(MusicFile theMusicFile, std::string_view theFileName)
{
	Mix_Music* aHMusic = 0;
	SDLMusicInterface* anSDL = (SDLMusicInterface*)mApp->mMusicInterface.get();
	// ... 读取文件到 new[] 分配的裸缓冲区 aData ...
	aHMusic = Mix_LoadMUS_RW(SDL_RWFromMem(aData, aSize), 1);
	if (theMusicFile == MusicFile::MUSIC_FILE_CREDITS_ZOMBIES_ON_YOUR_LAWN)
	{
		gMusicFileData[theMusicFile].mFileData = (unsigned int*)aData;
	}
	else
	{
		delete[] (char *)aData;
	}
	// ...
	std::scoped_lock anAutoCrit(anSDL->mMusicMapMutex);
	anSDL->mMusicMap.insert(SDLMusicMap::value_type(theMusicFile, aMusicInfo));
	return true;
}
```

这段代码里还留着一个全局数组 `gMusicFileData`：因为 `.mo3` 由 OpenMPT 在加载时一次性拷入内部内存，加载完即可 `delete[] aData`；而片尾曲 `ZombiesOnYourLawn.ogg` 是流式解码的，`Mix_LoadMUS_RW` 在播放期间仍需读取 `aData` 指向的内存（见[片尾曲崩溃修复博客](https://wszqkzqk.github.io/2026/02/09/PvZ-Portable-Zombies-on-Your-Lawn-Bug-Fix/)），旧代码于是用全局裸指针把这块内存挂起来，直到进程退出都未释放。

### 音效层的手写 `.au` 解码与软件变调回调

在音效（SFX）一侧，旧版 `SDLSoundManager` 和 `SDLSoundInstance` 也背负着两段补偿代码：

- **手写 `.au` 解码器（`SDLSoundManager::LoadAUSound`，约 120 行）**：游戏中有部分音效采用 Sun/NeXT 的 `.au`（`.snd`）格式，包含 8-bit $\mu$-law 编码。旧代码专门手写了大端序文件头解析、$\mu$-law 到 16-bit 线性 PCM 的分段折线解码循环，再调用 `SDL_BuildAudioCVT` 和 `SDL_ConvertAudio` 将 8000 Hz 单声道样本重采样到混音器格式，最后手动 `SDL_malloc` 拼装出一个 `Mix_Chunk` 结构体。
- **手写软件变调效果器（`SDLSoundInstance::PitchHandlerFuncCallback`，约 100 行）**：游戏中大量音效（如种植、打击、收集阳光）在播放时会通过 `AdjustPitch` 随机微调音高。由于 `SDL2_mixer` 的 `Mix_Chunk` 不支持变调，旧代码通过 `Mix_RegisterEffect` 在每个播放通道上挂载了一个自定义后处理回调，在音频线程中直接把缓冲区当作 `int16_t*`，用浮点步长做手动线性插值重采样；当加速播放提前耗尽样本时，甚至要在音频回调内部调用注释里标着 `// XXX unsafe call, since it locks audio` 的 `Mix_HaltChannel`。

## 转向 SDL3_mixer 的对象模型

`SDL3_mixer` 重新设计了混音 API，核心抽象收敛为三个类型：

- **`MIX_Mixer`**：混音器实例，绑定到具体的音频输出设备（`MIX_CreateMixerDevice`），不再是隐式的全局单例。
- **`MIX_Audio`**：不可变的音频源资产（取代了旧版分立的 `Mix_Chunk` 与 `Mix_Music`），支持从 `SDL_IOStream` 加载，并允许通过 `predecode` 参数指定是预先解码为内存 PCM 还是在播放时流式解码。
- **`MIX_Track`**：独立的播放轨道（取代了旧版用整数下标索引的固定通道池）。一条 `MIX_Track` 既可以绑定静态的 `MIX_Audio`（`MIX_SetTrackAudio`），也可以直接绑定动态生产数据的 `SDL_AudioStream`（`MIX_SetTrackAudioStream`），并且原生支持轨道级浮点增益（`MIX_SetTrackGain`）与底层重采样变调（`MIX_SetTrackFrequencyRatio`）。

### 原生 `.au` 支持与一行代码变调

迁移到 `SDL3_mixer` 后，`SDLSoundManager` 的音效加载逻辑首先得到了简化。因为 `SDL3_mixer` 原生内置了对 `.au` 格式的解码支持，原先 120 行的 `LoadAUSound`（含 $\mu$-law 解码表与 `SDL_AudioCVT`）被整体删除，`.au` 直接并入常规音效扩展名列表，统一走 `MIX_LoadAudio_IO`（`src/SexyAppFramework/sound/SDLSoundManager.cpp`）：

```cpp
bool SDLSoundManager::DecodeSound(intptr_t theSfxID, const std::string& theFilename)
{
	static constexpr const char* aFormats[] = { ".wav", ".mp3", ".ogg", ".au" };

	for (const char* aFormat : aFormats)
	{
		std::string aFilename = theFilename + aFormat;
		PFILE* fp = p_fopen(aFilename.c_str(), "rb");
		if (fp == nullptr)
			continue;

		p_fseek(fp, 0, SEEK_END);
		const size_t aFileSize = p_ftell(fp);
		p_fseek(fp, 0, SEEK_SET);
		std::vector<uint8_t> aData(aFileSize);
		const size_t aReadSize = p_fread(aData.data(), 1, aFileSize, fp);
		p_fclose(fp);
		if (aReadSize != aFileSize)
			continue;

#ifdef LOW_MEMORY
		constexpr bool aPredecode = false;
#else
		constexpr bool aPredecode = true;
#endif
		MIX_Audio* aAudio = MIX_LoadAudio_IO(
			mMixer, SDL_IOFromConstMem(aData.data(), aData.size()), aPredecode, true);
		if (aAudio == nullptr)
			continue;

		mSourceSounds[theSfxID] = aAudio;
		const Sint64 aDurationMs = MIX_AudioFramesToMS(aAudio, MIX_GetAudioDuration(aAudio));
		mSourceDurationMs[theSfxID] = aDurationMs > 0 ? static_cast<int>(aDurationMs) : 0;
		return true;
	}

	return false;
}
```

这里有两处细节值得留意：

- **`LOW_MEMORY` 与 `aPredecode` 的对应**：常规构建下 `aPredecode = true`，音效在加载时即解码为 PCM 驻留内存，播放时没有解码开销；而在面向内存受限设备的 `LOW_MEMORY` 构建下，`aPredecode = false` 让 `SDL3_mixer` 按需流式解码。同时，`SDL_IOFromConstMem` 配合 `closeio = true` 会在 `MIX_LoadAudio_IO` 内部拷贝所需数据后自动关闭临时 `SDL_IOStream`，无需调用方延长 `aData` 的生命周期。
- **用 `MIX_GetAudioDuration` 支撑确定性回放**：在录制或回放 `.dmo` 演示文件时，音效是否播放完毕不能依赖真实的音频时钟，而必须根据逻辑帧计数（`mUpdateCount`）确定性推算。过去需要手动根据 `Mix_Chunk::alen` 除以采样位深与声道数来计算毫秒数；现在加载时直接通过 `MIX_AudioFramesToMS(aAudio, MIX_GetAudioDuration(aAudio))` 算出时长并存入 `mSourceDurationMs`，无论底层是预解码还是流式格式都能准确获取。

而在 `SDLSoundInstance.cpp` 中，原本近百行的 `SDLSoundPitchHandler` 结构体、线性插值循环和 `Mix_RegisterEffect` 回调被全部移除。每个 `SDLSoundInstance` 持有一条专属的 `MIX_Track*`，变调与音量控制直接交给 `SDL3_mixer` 原生接口：

```cpp
void SDLSoundInstance::RehupVolume()
{
	if (mTrack != nullptr)
		MIX_SetTrackGain(mTrack, static_cast<float>(mBaseVolume * mVolume * mSoundManagerP->mMasterVolume));
}

void SDLSoundInstance::AdjustPitch(double theNumSteps)
{
	mPitch = powf(1.0594630943592952645618252949463, theNumSteps);
	if (mTrack != nullptr)
		MIX_SetTrackFrequencyRatio(mTrack, mPitch);
}
```

以十二平均律半音比 $2^{1/12} \approx 1.059463$ 计算出频率倍率后，一行 `MIX_SetTrackFrequencyRatio(mTrack, mPitch)` 就利用 SDL3 内部的音频重采样管线完成了变调，既消除了手写 `int16_t` 线性插值的音质损失，也去掉了在音频回调里调用 `Mix_HaltChannel` 的重入隐患。

## 用 OpenMptMusic 与 SDL_AudioStream 驱动动态 MOD

解决了音效与常规音频流（如 `ZombiesOnYourLawn.ogg`）之后，剩下的核心问题是 `mainmusic.mo3`。官方 `SDL3_mixer` 依然不暴露 MOD 音乐的内部通道控制接口，我们也不希望为了三个函数再去维护一份自定义的 `SDL3_mixer` 分支。

### 绕开内置解码器，直连 SDL_AudioStream

换个角度看，我们对混音器的诉求其实只是把这路音乐与其他轨道混音、控制总增益并输出到声卡；至于 `.mo3` 内部如何解码、如何跳转 Order、如何调节 30 个通道各自的音量，本来就是 `libopenmpt` 自己的职责。

SDL3 提供的 `SDL_AudioStream` 和 `SDL3_mixer` 的 `MIX_SetTrackAudioStream` 打通了这条路径：

```text
[libopenmpt (mModuleExt)]
       │  openmpt_module_read_interleaved_float_stereo()
       ▼
[OpenMptMusic::RenderCallback]
       │  SDL_PutAudioStreamData()
       ▼
[SDL_AudioStream (SDL_AUDIO_F32, stereo)]
       │  MIX_SetTrackAudioStream()
       ▼
[MIX_Track ("music")] ──► [MIX_Mixer] ──► 音频设备输出
```

当 `MIX_Track` 处于播放状态时，混音器会从绑定的 `SDL_AudioStream` 中拉取数据；一旦流中数据不足，SDL3 自动触发注册在流上的 `SDL_AudioStreamCallback`（即 `OpenMptMusic::RenderCallback`），由回调当场调用 `libopenmpt` 渲染出所需字节数的双声道 32 位浮点 PCM 样本并推入流中。

### 190 行实现 OpenMptMusic

基于这一思路，笔者编写了 `OpenMptMusic` 类（`src/SexyAppFramework/sound/OpenMptMusic.h` 与 `OpenMptMusic.cpp`，合计 190 行）。其核心加载与初始化逻辑如下：

```cpp
bool OpenMptMusic::Load(const void* theData, size_t theSize, int theSampleRate)
{
	if (theData == nullptr || theSize == 0)
		return false;

	int aError = 0;
	const char* aErrorMessage = nullptr;
	mModuleExt = openmpt_module_ext_create_from_memory(
		theData, theSize, nullptr, nullptr, nullptr, nullptr, &aError, &aErrorMessage, nullptr);
	if (mModuleExt == nullptr)
	{
		LogInfoLn("Failed to load MOD music: {}", aErrorMessage != nullptr ? aErrorMessage : "unknown error");
		return false;
	}

	mModule = openmpt_module_ext_get_module(mModuleExt);
	if (mModule == nullptr || !openmpt_module_ext_get_interface(
		mModuleExt, LIBOPENMPT_EXT_C_INTERFACE_INTERACTIVE, &mInteractive, sizeof(mInteractive)))
	{
		return false;
	}

	mSampleRate = theSampleRate;
	openmpt_module_set_repeat_count(mModule, -1);
	openmpt_module_ctl_set_boolean(mModule, "seek.sync_samples", 0);

	SDL_AudioSpec aSpec = { SDL_AUDIO_F32, 2, mSampleRate };
	mStream = SDL_CreateAudioStream(&aSpec, &aSpec);
	if (mStream == nullptr)
		return false;

	return SDL_SetAudioStreamGetCallback(mStream, &OpenMptMusic::RenderCallback, this);
}
```

这段代码把原本散落在 `SDL-Mixer-X` 内部的配置集中到了同一处：

- **直接获取 `LIBOPENMPT_EXT_C_INTERFACE_INTERACTIVE` 扩展接口**：通过 `openmpt_module_ext_get_interface` 拿到 `mInteractive` 函数表，后续调节通道音量只需调用 `mInteractive.set_channel_volume(mModuleExt, theChannel, theVolume)`，且音量参数直接接收 `[0.0, 1.0]` 浮点数，不再需要像旧版那样先量化成 `0~128` 的整数再传进 `SDL-Mixer-X` 除回浮点数。
- **保留 `seek.sync_samples = 0`**：这行等价于原版 BASS 库 `BASS_MUSIC_POSRESET` 标志的配置，此前需要给内嵌的 `SDL-Mixer-X` 打补丁才能加上；现在直接写在项目自己的 `OpenMptMusic::Load` 中，跨曲目跳转 Order 时会自动停止上一首曲目的残留音符。
- **采样率对齐与零格式转换**：创建 `OpenMptMusic` 时，`SDLMusicInterface` 先通过 `MIX_GetMixerFormat(mMixer, &aSpec)` 查询混音器当前的工作采样率并传给 `Load()`。`SDL_AudioStream` 的输入端与输出端使用相同的 `SDL_AudioSpec{ SDL_AUDIO_F32, 2, mSampleRate }`，由 `libopenmpt` 直接以目标采样率渲染双声道 `float` 样本，省去了二次重采样与格式转换。

对应的拉取回调与控制方法如下：

```cpp
void OpenMptMusic::Rewind(int thePackedOrder)
{
	SDL_ClearAudioStream(mStream);
	openmpt_module_set_position_seconds(mModule, 0.0);
	if (thePackedOrder > 0)
		JumpToOrder(thePackedOrder);
}

void OpenMptMusic::JumpToOrder(int thePackedOrder)
{
	const auto aValue = static_cast<uint32_t>(thePackedOrder);
	openmpt_module_set_position_order_row(
		mModule,
		static_cast<int32_t>(aValue & 0xFFFF),
		static_cast<int32_t>((aValue >> 16) & 0xFFFF));
}

int OpenMptMusic::GetOrder() const
{
	const uint32_t aOrder = static_cast<uint32_t>(openmpt_module_get_current_order(mModule));
	const uint32_t aRow = static_cast<uint32_t>(openmpt_module_get_current_row(mModule));
	return static_cast<int>((aRow << 16) | (aOrder & 0xFFFF));
}

void OpenMptMusic::SetChannelVolume(int theChannel, double theVolume)
{
	mInteractive.set_channel_volume(mModuleExt, theChannel, theVolume);
}

void OpenMptMusic::Render(int theByteCount)
{
	while (theByteCount > 0)
	{
		const int aFrames = std::min(theByteCount / static_cast<int>(sizeof(float) * 2), 2048);
		if (aFrames <= 0)
			return;

		const size_t aRendered = openmpt_module_read_interleaved_float_stereo(
			mModule, mSampleRate, static_cast<size_t>(aFrames), mBuffer.data());
		if (aRendered == 0)
			return;

		const int aBytes = static_cast<int>(aRendered * sizeof(float) * 2);
		if (!SDL_PutAudioStreamData(mStream, mBuffer.data(), aBytes))
			return;
		theByteCount -= aBytes;
	}
}
```

注意 `Rewind()` 第一行的 `SDL_ClearAudioStream(mStream)`：重新开始播放或切换曲目时，`SDL_AudioStream` 内部缓冲区里可能还留有停止前预渲染出的若干帧旧样本；先清空流缓冲区再执行 `openmpt_module_set_position_order_row`，才能确保新曲目从第一帧起不夹带旧数据。

### 在 SDLMusicInterface 中统一挂载双路径

在 `SDLMusicInterface` 中，每个音乐条目 `SDLMusicInfo` 根据文件扩展名走两条路径之一：`.mo3` 创建 `OpenMptMusic` 并通过 `MIX_SetTrackAudioStream` 绑定到 `MIX_Track`；`.ogg` 等常规流式音频则调用 `MIX_LoadAudio_IO`（同样设置 `predecode = false` 以流式解码，避免一次性展开整首片尾曲）并通过 `MIX_SetTrackAudio` 绑定到 `MIX_Track`：

```cpp
static bool InsertMusic(MIX_Mixer* theMixer, int theSongId, SDLMusicInfo&& theMusic, SDLMusicMap& theMap, float theGlobalVolume)
{
	theMusic.mTrack.reset(MIX_CreateTrack(theMixer));
	if (theMusic.mTrack == nullptr)
		return false;

	const bool aHasInput = theMusic.mOpenMpt != nullptr
		? MIX_SetTrackAudioStream(theMusic.mTrack.get(), theMusic.mOpenMpt->GetStream())
		: MIX_SetTrackAudio(theMusic.mTrack.get(), theMusic.mAudio.get());
	if (!aHasInput || !MIX_TagTrack(theMusic.mTrack.get(), "music"))
		return false;

	theMap.emplace(theSongId, std::move(theMusic));
	ApplyMusicGain(theMap.at(theSongId), theGlobalVolume);
	return true;
}
```

绑定完成后，后续的暂停（`MIX_PauseTrack`）、恢复（`MIX_ResumeTrack`）、停止（`MIX_StopTrack`）、状态查询（`MIX_TrackPlaying`）和淡入淡出音量控制（`MIX_SetTrackGain`）就完全统一在 `MIX_Track` 层面，不再关心底层输入来自 `OpenMptMusic` 还是 `MIX_Audio`。

### 收拢接口边界与双层锁同步

有了 `OpenMptMusic` 后，基类 `MusicInterface`（`src/SexyAppFramework/sound/MusicInterface.h`）补齐了四个带默认空实现的虚方法：

```cpp
virtual bool LoadMusicFromMemory(int, const void*, size_t, std::string_view) { return false; }
virtual int  GetMusicOrder(int) { return -1; }
virtual bool JumpToOrder(int, int) { return false; }
virtual bool SetChannelVolume(int, int, double) { return false; }
```

游戏层的 `Music.cpp` 由此移除了对 `SDLMusicInterface.h` 和 `SDL_mixer` 的头文件依赖。原先带有裸指针分配和 `gMusicFileData` 特殊分支的 `Music::PvzpLoadMusic`，现在简化为读取字节数组并调用虚接口：

```cpp
bool Music::PvzpLoadMusic(MusicFile theMusicFile, std::string_view theFileName)
{
	// ... 解析扩展名 anExt 并打开 pFile ...
	p_fseek(pFile, 0, SEEK_END);
	const size_t aSize = p_ftell(pFile);
	p_fseek(pFile, 0, SEEK_SET);
	std::vector<uint8_t> aData(aSize);
	const size_t aReadSize = p_fread(aData.data(), 1, aSize, pFile);
	p_fclose(pFile);
	if (aReadSize != aSize)
		return false;

	return mMusicInterface->LoadMusicFromMemory(theMusicFile, aData.data(), aData.size(), anExt);
}
```

在线程同步上，`SDLMusicInterface` 区分了两把锁的职责：

- **`mMusicMapMutex`（`std::recursive_mutex`）**：保护 `mMusicMap` 容器本身，防止后台加载线程插入音乐条目与主线程 `Update()` 遍历音乐表产生数据竞争（见[音乐表数据竞争修复博客](https://wszqkzqk.github.io/2026/09/06/PvZ-Portable-Music-Map-Data-Race/)）。
- **`MIX_LockMixer(mMixer)` / `MIX_UnlockMixer(mMixer)`**：保护 `OpenMptMusic` 内部的 `openmpt_module*` 状态。因为 `OpenMptMusic::RenderCallback` 运行在 SDL 音频设备线程（由 `MIX_Mixer` 调起），而主线程会调用 `GetMusicOrder`、`JumpToOrder`、`SetChannelVolume` 和 `StartMusic`（内含 `Rewind`），在访问 `mOpenMpt` 前后锁住 `mMixer`，即可保证主线程的控制调用不会与音频线程的 `openmpt_module_read_interleaved_float_stereo` 并发重入。

## 迁移过程中的三处细节排错

在 `refactor/sdl3-migration` 分支的演进过程中，新音频系统在试听与边界测试中暴露出三处问题。

### MIX_SetTagGain 与 MIX_SetTrackGain 的覆盖冲突

`SDL3_mixer` 支持给轨道打字符串标签（如 `MIX_TagTrack(track, "music")`），并提供 `MIX_SetTagGain(mixer, "music", gain)`。在初版实现（`68de7dc2`）中，笔者用 `MIX_SetTagGain` 控制设置菜单里的全局音乐音量（`mGlobalVolume`），再用 `MIX_SetTrackGain` 控制每首音乐自己的曲目音量与淡入淡出（`aMusicInfo.mVolume`），以为两者会在混音器内部自动相乘。

实际测试却发现，每当曲目执行淡入淡出（每帧调用 `MIX_SetTrackGain`）时，用户在设置里调低的全局音乐音量就会失效；反过来，拖动全局音乐音量滑块时，正在淡出的曲目音量又会被重置。

查阅 `SDL3_mixer` 的实现可知，Tag 在 `SDL3_mixer` 中只是一个批量操作轨道集合的分组机制，并不构成独立的子混音总线（Submix Bus）——调用 `MIX_SetTagGain(mixer, "music", gain)` 实际上只是遍历所有带有 `"music"` 标签的 `MIX_Track`，把每条轨道的 track gain 直接改写为 `gain`。

定位原因后，提交 `c69ae501`（`Fix: compose music gain per track`）移除了 `MIX_SetTagGain` 调用，改为在 `SDLMusicInterface` 内部通过 `ApplyMusicGain` 显式计算单曲音量与全局音量的乘积：

```cpp
static void ApplyMusicGain(const SDLMusicInfo& theMusic, float theGlobalVolume)
{
	MIX_SetTrackGain(theMusic.mTrack.get(), theMusic.mVolume * theGlobalVolume);
}
```

无论是单曲淡入淡出（`Update`）、设置单曲音量（`SetSongVolume` / `SetSongMaxVolume`），还是调节全局音乐音量（`SetVolume`），都统一调用 `ApplyMusicGain` 更新轨道的合成增益，两者不再互相覆盖。

### 对齐原版 BASS 的音量标度

在排查音乐音量的过程中，笔者还注意到旧版 `SDLMusicInterface` 里一处反常的系数：

```cpp
// 旧代码
void SDLMusicInterface::SetVolume(double theVolume)
{
	mGlobalVolume = (int)(theVolume*80);
}
```

在旧版 `SDL_mixer` 中，满音量常量 `MIX_MAX_VOLUME` 是 `128`，而 `SetVolume` 却把 `[0.0, 1.0]` 的输入乘以 `80`，相当于给背景音乐打了个 `80 / 128 = 0.625` 的折扣（初版迁移时曾写成 `theVolume * 0.8`）。对比音效管理器 `SDLSoundManager` 中直接按 `theVolume * 128`（即 `1.0` 满量程）映射的做法，以及原版 BASS 音频库的线性增益语义，这个额外的缩放系数会导致音乐相对于音效偏小。提交 `fb44b85d`（`Fix: match BASS music volume scaling`）将其修正为 1:1 的满量程映射：

```cpp
void SDLMusicInterface::SetVolume(double theVolume)
{
	std::scoped_lock anAutoCrit(mMusicMapMutex);
	mGlobalVolume = static_cast<float>(theVolume);
	for (auto& [aId, aMusicInfo] : mMusicMap)
		ApplyMusicGain(aMusicInfo, mGlobalVolume);
}
```

### 无音频设备时的音效文件名注册

在 CI 无头环境或未连接音频设备的系统上，`MIX_CreateMixerDevice` 可能失败，`SDLSoundManager::Initialized()` 返回 `false`。初版迁移重构 `SDLSoundManager::LoadSound` 时，把 `!Initialized()` 的早退判断写在了记录 `mSourceFileNames[theSfxID]` 之前：

```cpp
// 初版写法：当音频未初始化时，mSourceFileNames 未被写入
ReleaseSound(theSfxID);
if (!Initialized())
	return true;
mSourceFileNames[theSfxID] = theFilename;
```

这引发了一个副作用：`SDLSoundManager` 的另一个重载 `LoadSound(const std::string& theFilename)` 会先遍历 `mSourceFileNames` 数组，若发现同名音效已注册则直接复用已有 ID；否则从槽位末尾向前分配新槽位。如果 `!Initialized()` 时跳过记录 `mSourceFileNames`，上层每次按文件名请求加载同一音效都会消耗一个新槽位。提交 `91c99943`（`Fix: preserve sound file registration when audio is unavailable`）将 `mSourceFileNames[theSfxID] = theFilename;` 移到了 `!Initialized()` 检查之前，保证了无音频环境下槽位去重逻辑的一致。

## 结语

回顾这次音频系统的重构，代码量的变化很直观：

- 删除内嵌 `SDL-Mixer-X`：约 -143,800 行
- 删除手写 `.au` 解码器与软件变调回调：约 -220 行
- 新增 `OpenMptMusic` 桥接类：+190 行

过去之所以要在仓库里维护十几万行的 `SDL-Mixer-X`，是因为把“混音输出”和“特定格式的交互式解码”绑在了同一个库里。SDL3 的 `SDL_AudioStream` 加上 `SDL3_mixer` 的 `MIX_SetTrackAudioStream`，提供了一套流式组合机制：通用格式（WAV、MP3、Ogg、AU）交给 `SDL3_mixer` 内置解码，而需要细粒度通道控制的 tracker 模块（`.mo3`）则由应用层直接调用 `libopenmpt` 渲染成 `SDL_AudioStream` 接入轨道。职责拆开之后，不仅省去了庞大的第三方源码树，抽象接口与线程边界也一并理顺。

下一篇文章《[SDL3 窗口、高分屏双坐标系与输入事件迁移](https://wszqkzqk.github.io/2026/11/11/PvZ-Portable-SDL3-Window-HiDPI-Input/)》将继续介绍窗口系统、HiDPI 视口映射以及键盘输入事件在迁移至 SDL3 时的改造与排错。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。研究或使用此项目时，**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies)购买）。你需要从正版游戏中提取以下文件，放到 PvZ-Portable 的程序所在目录：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
