---
layout:       post
title:        PvZ-Portable：从 SDL2 迁移至 SDL3
subtitle:     移除 14 万行内嵌音频库，更新跨平台多媒体与构建底座
header-img:   img/games/pvz-portable/bg-pvz-portable.webp
date:         2026-11-09
author:       wszqkzqk
catalog:      true
tags:         SDL 开源软件 游戏移植 开源游戏 PvZ-Portable
---

## 引言

在 [PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable) 的跨平台演进中，[渲染后端统一至 OpenGL ES 2.0](https://wszqkzqk.github.io/2026/02/16/PvZ-Portable-GLES2-Migration/) 解决了图形层的平台分裂。而在窗口管理、输入分发、音频输出与系统路径抽象上，项目自诞生起一直建立在 SDL2 与仓库内嵌的 SDL-Mixer-X 之上。

随着 SDL3 及配套生态（`SDL3_mixer`、Emscripten `sdl3` port、vcpkg 与各 Linux 发行版软件源）趋于成熟，笔者在 PR [#523](https://github.com/wszqkzqk/PvZ-Portable/pull/523) 中将项目从 SDL2 全面迁移到了 SDL3。整个提交涉及 478 个文件，新增 1,275 行代码，删除 144,016 行代码——完成底层多媒体框架换代的同时，彻底移除了随仓库携带多年的 `SDL-Mixer-X` 源码树。

这次改造涉及音频引擎重写、高分屏（HiDPI）坐标系分离、输入事件扁平化以及七个目标平台构建链路的调整。作为系列的第一篇，本文先说明迁移的原因以及对玩家、编译者和打包维护者的实际影响，再从整体上梳理各子系统的改动脉络。具体技术细节在同系列其余三篇文章中展开：

- [基于 SDL3_mixer 与 SDL_AudioStream 重构音频系统](https://wszqkzqk.github.io/2026/11/10/PvZ-Portable-SDL3-Audio-System/)
- [SDL3 窗口、高分屏双坐标系与输入事件迁移](https://wszqkzqk.github.io/2026/11/11/PvZ-Portable-SDL3-Window-HiDPI-Input/)
- [SDL3 迁移中的跨平台构建与静态链接](https://wszqkzqk.github.io/2026/11/12/PvZ-Portable-SDL3-Cross-Platform-Build/)

## 为什么要迁移到 SDL3

项目此前已经在 Linux、Windows、macOS、Android、iOS、WebAssembly 和 Nintendo Switch 上稳定运行。决定在此时跨大版本迁移到 SDL3，主要出于以下几处现实问题。

### 摆脱内嵌的 14 万行 SDL-Mixer-X

《植物大战僵尸》的关卡音乐存放在单个 `mainmusic.mo3` 文件中，包含 30 个 tracker 通道，运行时需要通过跳转 Order 切换曲目，并在战斗进入 Burst 状态时逐通道实时调整鼓组与镲片的音量（见[单流音乐系统博客](https://wszqkzqk.github.io/2026/03/02/PvZ-Portable-Music-System/)）。标准 `SDL2_mixer` 没有暴露 MOD 音乐的逐通道音量接口，因此项目早期直接在 `src/SexyAppFramework/sound/SDL-Mixer-X/` 下内嵌了整棵 SDL-Mixer-X 源码树。

这棵源码树有 14.3 万余行代码，包含了大量项目根本用不到的 MIDI 合成器、音色库、Qt 播放器示例乃至 VB6 绑定。每次全新编译时，相当一部分时间都花在编译这套庞大的第三方源码上；而在静态构建、交叉编译或 WebAssembly 移植时，它自带的旧版 CMake 脚本又经常与外部工具链产生摩擦。

SDL3 引入了支持拉取回调的 `SDL_AudioStream`，配合 `SDL3_mixer` 的轨道（`MIX_Track`）接口，可以直接把 `libopenmpt` 渲染出的浮点音频流挂接到混音器轨道上。原本需要内嵌 14 万行源码才能拿到的 MOD 通道控制能力，现在用不到 200 行桥接代码就能实现。

### 跨过 sdl2-compat 过渡层

在 Arch Linux、macOS Homebrew 等更新较快的软件源中，`sdl2` 包实际上已经被替换为基于 SDL3 实现的兼容层 `sdl2-compat`。这意味着程序编译时面向 SDL2 头文件，运行时却要先加载 `libSDL2`，再由 `sdl2-compat` 在内部通过 `dlopen` 动态加载 `libSDL3`。

这种双层结构给打包带来过不少麻烦。例如在 macOS CI 构建中，`dylibbundler` 通过分析 Mach-O 头部依赖来收集动态库，无法发现 `sdl2-compat` 在运行时 `dlopen` 的 `libSDL3.dylib`，过去只能在打包脚本里专门写一条命令把 `libSDL3.dylib` 手动拷进发布目录：

```bash
# 旧版 macOS CI 中针对 sdl2-compat 的特殊处理
install -m 755 "$(brew --prefix sdl3)/lib/libSDL3.dylib" dist/libs/libSDL3.dylib
```

既然主流环境的底层已经是 SDL3，直接迁移到原生 SDL3 接口，既省去了中间兼容层的转发，也让二进制依赖关系恢复直接。

### 原生 Wayland 策略与高分屏支持

在 SDL2 下，即便运行在 Linux Wayland 会话中，默认仍会优先选择 X11 后端（走 XWayland），只有显式设置环境变量 `SDL_VIDEODRIVER=wayland` 才会启用原生 Wayland。为此，项目在 Arch Linux 软件包中专门配了一个启动脚本 `archlinux/pvz-portable.sh` 来检测 `WAYLAND_DISPLAY`。

SDL3 在桌面 Linux 上将 Wayland 作为默认优先后端，并在窗口系统中原生区分了窗口逻辑尺寸与物理像素尺寸（`SDL_WINDOW_HIGH_PIXEL_DENSITY`）。迁移后，不再需要外部启动脚本干预视频驱动选择，高分屏环境下的渲染分辨率与鼠标坐标映射也能通过原生接口分离。

### 收敛 Android 构建链路

在 SDL2 架构下，Android 端的 `SDLActivity` 默认通过 `System.loadLibrary("SDL2")` 动态加载 SDL2，迫使我们在 vcpkg 静态依赖之外单独从源码编译一份 `libSDL2.so`。迁移到 SDL3 并调整 `PvZPortableActivity` 的库加载列表后，SDL3 与 `SDL3_mixer` 可以同其他依赖一样由 vcpkg 静态编译并直接链入单个 `libmain.so`，显著简化了 Android 的构建与打包过程。

## 对用户与打包维护者的影响

### 普通玩家：存档、资源与回放保持兼容

对直接下载预编译版本或使用在线 Web 版的玩家而言，这次迁移不需要做任何额外操作：

- **游戏资源不变**：依然只需准备正版《植物大战僵尸：年度版》的 `main.pak` 与 `properties/` 目录。
- **存档完全兼容**：各平台的数据存储路径（由 `SDL_GetPrefPath`、Android 外部文件目录、iOS `Documents` 目录及浏览器 IndexedDB 管理）保持原样，`userdata/` 下的用户存档与关卡进度存档可以直接读取。
- **确定性回放兼容**：`.dmo` 演示文件的录制与回放格式没有破坏性变更，原有的回放文件仍可正常加载。
- **桌面体验改进**：Linux Wayland 用户无需设置环境变量即可默认以原生 Wayland 窗口运行；macOS Retina 与桌面分数缩放屏幕下的窗口缩放、全屏切换更加稳定。

### 源码编译与打包维护：依赖变更说明

从源码自行编译 PvZ-Portable，或维护各 Linux 发行版、BSD 等平台软件包时，需要注意构建依赖的变化：

- **移除 `SDL2`，新增 `SDL3` 与 `SDL3_mixer`**：
  - `SDL3` 最低版本要求为 **3.2.12**。滚轮事件处理使用了 SDL 3.2.12 引入的 `event.wheel.integer_y` 字段，CMake 配置阶段会通过 `find_package(SDL3 3.2.12 CONFIG REQUIRED)` 检查版本。
  - 由于移除了仓库内嵌的 `SDL-Mixer-X`，现在需要系统或工具链提供官方的 `SDL3_mixer`。
- **保留 `libopenmpt`**：`.mo3` 音乐解码不再经过混音器内置插件，而是由引擎直接调用 `libopenmpt` 解码后送入 `SDL_AudioStream`，因此 `libopenmpt` 依然是必需的直接依赖。
- **常规动态构建不再显式查找二级音频依赖**：在系统提供动态库的桌面构建中，顶层项目只需查找 `SDL3`、`SDL3_mixer`、`libopenmpt`、`libpng`、`libjpeg-turbo` 和 `zlib`；仅当静态链接 `libopenmpt` 且该静态归档未自包含解码依赖时，CMake 才会按需探测 `mpg123`、`vorbisfile`、`vorbis` 和 `ogg`。

各主流平台更新后的依赖安装命令如下：

- **Arch Linux**：
  ```bash
  sudo pacman -S --needed base-devel cmake libjpeg-turbo libopenmpt libpng ninja sdl3 sdl3_mixer
  ```
- **Debian / Ubuntu**：
  ```bash
  sudo apt install cmake ninja-build libjpeg-dev libopenmpt-dev libpng-dev libsdl3-dev libsdl3-mixer-dev
  ```
- **Windows (MSYS2 UCRT64)**：
  ```bash
  pacman -S --needed base-devel mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-libjpeg-turbo mingw-w64-ucrt-x86_64-libopenmpt mingw-w64-ucrt-x86_64-libpng mingw-w64-ucrt-x86_64-ninja mingw-w64-ucrt-x86_64-sdl3 mingw-w64-ucrt-x86_64-sdl3-mixer
  ```
- **macOS (Homebrew)**：
  ```bash
  brew install cmake dylibbundler jpeg-turbo libopenmpt libpng ninja sdl3 sdl3_mixer
  ```

Arch Linux 的打包脚本（`archlinux/PKGBUILD` 与 `PKGBUILD-AUR`）已同步将 `depends` 中的 `sdl2-compat` 替换为 `sdl3` 和 `sdl3_mixer`，并删去了 `pvz-portable.sh` 中手动设置 `SDL_VIDEODRIVER` 的代码。

## 迁移内容概览

从代码上看，除了把 `#include <SDL.h>` 替换为 `#include <SDL3/SDL.h>` 以及常规函数重命名外，实质性的改动集中在四个部分。

### 重构音频子系统

`SDL3_mixer` 放弃了沿用多年的“全局单混音器 + 固定整数通道号 + `Mix_Chunk`/`Mix_Music` 二元划分”设计，转向基于对象的 `MIX_Mixer` / `MIX_Audio` / `MIX_Track` 架构。借此机会，项目的音频层做了三项清理：

- **用 `OpenMptMusic` + `SDL_AudioStream` 替代 `SDL-Mixer-X`**：新建了 190 行的 `OpenMptMusic` 类（`src/SexyAppFramework/sound/OpenMptMusic.cpp`），直接调用 `libopenmpt` C API 渲染双声道浮点音频，通过 `SDL_SetAudioStreamGetCallback` 按需向 `SDL_AudioStream` 喂入数据，再由 `MIX_SetTrackAudioStream` 将流挂载到 `MIX_Track` 上。曲目跳转（Order seek）和 30 通道独立音量控制全部收敛在 `OpenMptMusic` 内部，主线程与音频线程之间通过 `MIX_LockMixer` 同步。
- **消除 `Music` 与 `MusicInterface` 的抽象泄漏**：旧代码中，游戏层的 `Music.cpp` 直接包含了 `SDL_mixer_ext.h`，甚至将 `mMusicInterface` 强转为 `SDLMusicInterface*` 去直接读写内部的 `mMusicMap` 和互斥锁。迁移后，`LoadMusicFromMemory`、`GetMusicOrder`、`JumpToOrder` 和 `SetChannelVolume` 正式进入 `MusicInterface` 虚接口，`Music.cpp` 不再感知任何底层音频库类型，此前为防止内存提前释放而保留的全局数组 `gMusicFileData` 也被清除。
- **移除手写的软件变调回调与 `.au` 解码器**：`SDL3_mixer` 原生支持 `.au`（Sun/NeXT $\mu$-law/PCM）格式，且 `MIX_Track` 原生提供 `MIX_SetTrackFrequencyRatio` 变调接口。因此，`SDLSoundManager.cpp` 中 120 多行手写的 `.au` 解析与 `SDL_AudioCVT` 转换代码，以及 `SDLSoundInstance.cpp` 中近百行手动对 `int16_t` 样本做线性插值的 `SDLSoundPitchHandler` 回调全部删除，音效变调简化为一行函数调用。

这部分的设计与排错过程见《[基于 SDL3_mixer 与 SDL_AudioStream 重构音频系统](https://wszqkzqk.github.io/2026/11/10/PvZ-Portable-SDL3-Audio-System/)》。

### 窗口、高分屏双坐标系与输入事件更新

在窗口与输入层（`Window.cpp`、`GLInterface.cpp`、`Input.cpp`），改动主要围绕坐标精度与事件结构展开：

- **高分屏下的像素与窗口坐标分离**：窗口创建启用了 `SDL_WINDOW_HIGH_PIXEL_DENSITY`。在 Retina 或分数缩放的 Wayland 桌面上，`GLInterface::UpdateViewport()` 使用 `SDL_GetWindowSizeInPixels()` 获取物理像素尺寸来设置 `glViewport`，同时使用 `SDL_GetWindowSize()` 获取窗口逻辑坐标，按比例换算出逻辑坐标系下的 `mPresentationRect`。这保证了 OpenGL 以原生像素分辨率绘制，而升级为 `float` 类型的 SDL3 鼠标事件与输入法候选框位置（`SDL_SetTextInputArea`）仍在窗口逻辑坐标系下映射。
- **事件循环扁平化与滚轮整数刻度**：原本嵌套在 `SDL_WINDOWEVENT` 下的二级 `switch` 全部提升为顶层 `SDL_EVENT_WINDOW_*` 事件；鼠标滚轮改用 SDL 3.2.12 的 `event.wheel.integer_y`，确保确定性回放（Demo）录制的 8 位滚轮增量在不同高精度滚动设备上行为一致。
- **`SDLK_A` 命名变更背后的键码陷阱**：SDL3 将字母键宏名从 `SDLK_a` 改为大写 `SDLK_A`，但其底层枚举值依然是小写 ASCII `'a'`（`0x61`）。初次迁移时若误以为其值变成了 `'A'`，会导致所有字母快捷键与非 IME 字符输入失效。

这部分细节见《[SDL3 窗口、高分屏双坐标系与输入事件迁移](https://wszqkzqk.github.io/2026/11/11/PvZ-Portable-SDL3-Window-HiDPI-Input/)》。

### 清理平台遗留胶水代码

SDL3 将许多原本需要应用层自行编写平台分支的基础设施纳入了标准 API，使我们得以删去多处平台特判代码：

| 平台特判逻辑 | 迁移前（SDL2 + 平台 API） | 迁移后（SDL3 统一 API） |
| :--- | :--- | :--- |
| **Windows 命令行 UTF-8 转换** | `main.cpp` 中 45 行 `GetCommandLineW` + `CommandLineToArgvW` + `WideCharToMultiByte` | 引入 `<SDL3/SDL_main.h>`，由 SDL3 入口统一提供 UTF-8 `argv` |
| **Windows 纳秒休眠模拟** | `Common.h` 中 30 行 `CreateWaitableTimer` + `WaitForSingleObject` 实现的 `nanosleep` | 全平台统一调用 `SDL_DelayNS()` |
| **iOS Documents 目录获取** | `std::getenv("HOME")` 拼接 `"Documents"` | `SDL_GetUserFolder(SDL_FOLDER_DOCUMENTS)` |
| **可执行文件目录获取** | `char* p = SDL_GetBasePath()` 后需手动 `SDL_free(p)` | `const char* p = SDL_GetBasePath()`（SDL3 内部缓存，无需释放） |

### 重整七大平台构建与静态链接体系

代码层面的 API 迁移只占了整个 PR 的第一个提交（`68de7dc2`）。在 `refactor/sdl3-migration` 分支随后的 30 个提交中，大部分工作都围绕着 Linux（动态与 manylinux 静态）、Windows（MinGW 与 MSVC）、macOS、Android、iOS、WebAssembly 和 Nintendo Switch 七个平台的构建链路展开：

- 放弃在主项目 `CMakeLists.txt` 中通过 `FetchContent` 隐式拉取构建依赖的尝试，回归标准 `find_package(SDL3 3.2.12 CONFIG REQUIRED)` 与 `find_package(SDL3_mixer CONFIG REQUIRED)`，保持构建入口单纯。
- Android 端通过 vcpkg 统一静态编译 `sdl3` 与 `sdl3-mixer`，全部链接进单个 `libmain.so`，并在 Gradle 中编写 `downloadSdl3Java` 任务，自动解析 `vcpkg-configuration.json` 的 baseline 提交以拉取版本严格对齐的 SDL3 Java 层源码，同时兼顾 CI 与本地 Android Studio 构建。
- WebAssembly 端编写 14 行的 `CMake/EmscriptenSDL3.cmake` 桥接 Emscripten 内置的 `-sUSE_SDL=3` 端口与源码编译的 `SDL3_mixer`。
- 解决 Linux 全静态构建中 `libopenmpt` 与 `SDL3_mixer` 内置 `stb_vorbis` 的符号冲突，以及 MinGW 静态目标的选择。

这些跨平台构建经验汇总在《[SDL3 迁移中的跨平台构建与静态链接](https://wszqkzqk.github.io/2026/11/12/PvZ-Portable-SDL3-Cross-Platform-Build/)》中。

## 结语

从最终合并的结果来看，这次 SDL3 迁移更像是一次借框架换代完成的减法：

| 指标 | 迁移结果 |
| :--- | :--- |
| **仓库代码净变化** | **+1,275 行 / -144,016 行**（净减少逾 14.2 万行） |
| **内嵌第三方音频库** | 完全移除 `SDL-Mixer-X` 目录，改用 `SDL3_mixer` + 190 行 `OpenMptMusic` |
| **手写音频底层样板** | 移除 120 行 `.au` 解码器与 100 行软件重采样变调回调 |
| **平台特判胶水代码** | 移除 Win32 UTF-8 `argv` 转换、Win32 `nanosleep`、Wayland 启动脚本与 macOS `libSDL3.dylib` 补丁 |
| **Android 原生库产物** | 从多个独立动态库收敛为单个静态集成的 `libmain.so` |

同系列的后续三篇文章将按子系统逐一拆解这次迁移中的技术细节与排错过程。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。研究或使用此项目时，**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies)购买）。你需要从正版游戏中提取以下文件，放到 PvZ-Portable 的程序所在目录：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
