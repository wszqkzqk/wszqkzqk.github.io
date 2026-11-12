---
layout:       post
title:        PvZ-Portable：SDL3 迁移中的跨平台构建与静态链接
subtitle:     Android 单库静态打包、Emscripten 混合构建与 Linux 静态符号冲突处理
header-img:   img/games/pvz-portable/bg-pvz-portable.webp
date:         2026-11-12
author:       wszqkzqk
catalog:      true
tags:         SDL CMake 构建系统 静态链接 Android WebAssembly PvZ-Portable
---

## 引言

在[前两篇](https://wszqkzqk.github.io/2026/11/10/PvZ-Portable-SDL3-Audio-System/)[文章](https://wszqkzqk.github.io/2026/11/11/PvZ-Portable-SDL3-Window-HiDPI-Input/)中，笔者介绍了 [PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable) 迁移到 SDL3 时的音频引擎重写与窗口输入适配。如果翻看 `refactor/sdl3-migration` 分支的原始提交历史就会发现，C++ 源码层面的迁移在第一个提交（`68de7dc2`）中就已经基本成型，而随后的近 30 个提交几乎都在处理同一件事：**让新的 `SDL3 + SDL3_mixer + libopenmpt` 依赖组合在 Linux（常规与 manylinux 静态）、Windows（MinGW 与 MSVC）、macOS、Android、iOS、WebAssembly 和 Nintendo Switch 七类构建目标上全部跑通**。

以前 `SDL-Mixer-X` 源码就躺在仓库里，主项目只需要 `find_package(SDL2)` 再 `add_subdirectory(SDL-Mixer-X)`。移除内嵌源码树并改用外部 `SDL3` 与 `SDL3_mixer` 后，每个平台获取这两个库的方式、动静态链接约束以及二级解码器（如 Vorbis）的符号归属各不相同。本文作为 SDL3 迁移系列的收官篇，将复盘这轮构建体系重整中的关键决策与排错细节。

## 构建边界的取舍：为什么放弃 FetchContent

在最初的迁移提交（`68de7dc2`）中，为了照顾当时部分环境尚未预装 `SDL3` 或 `SDL3_mixer` 的情况，笔者曾编写了一个 `CMake/Dependencies.cmake` 模块：先尝试 `find_package(SDL3 QUIET)` 和 `find_package(SDL3_mixer QUIET)`；如果找不到，就在 CMake 配置阶段通过 `FetchContent` 从 GitHub 下载源码压缩包并内联编译。

这套“找不到就自动拉源码编”的逻辑看似省事，一上多平台 CI 却立刻暴露出弊端：

- **构建选项污染主项目**：为了控制内联编译的 `SDL3` 和 `SDL3_mixer`，主项目的 CMake 脚本不得不塞入几十行 `set(SDLMIXER_FLAC OFF CACHE BOOL "" FORCE)`、`set(SDL_SHARED ...)`、Switch 补丁下载与打补丁命令，乃至针对不同平台的 Vorbis 后端分支。
- **违背打包规范**：Linux 发行版打包（如 Arch `PKGBUILD`）和 vcpkg 构建要求配置阶段严格离线且只消费外部声明的依赖，`FetchContent` 的联网拉取逻辑在这些场景下纯属累赘。
- **缓存粒度失控**：把第三方库的源码编译绑在游戏自身的 build 目录里，每次清理构建目录都要重编一遍 `SDL3` 和 `SDL3_mixer`。

因此在提交 `089c00df`（`Refactor: prepare SDL dependencies outside project builds`）中，笔者果断删掉了整个 `CMake/Dependencies.cmake`，将原则确立为：**依赖准备归外部环境（系统包管理器、vcpkg 或平台预构建脚本），主项目的 `CMakeLists.txt` 只负责声明式地消费依赖**（唯一例外是尚无官方 port 的 Emscripten `SDL3_mixer`，见后文）：

```cmake
if(EMSCRIPTEN AND PVZP_SDL3_MIXER_SOURCE_DIR)
	include(CMake/EmscriptenSDL3.cmake)
	add_subdirectory("${PVZP_SDL3_MIXER_SOURCE_DIR}" "${PROJECT_BINARY_DIR}/SDL3_mixer")
else()
	find_package(SDL3 3.2.12 CONFIG REQUIRED)
	find_package(SDL3_mixer CONFIG REQUIRED)
endif()
```

职责划清之后，主项目的 `CMakeLists.txt` 立刻干净下来，各平台的特殊处理则各自归位到对应的构建脚本与 triplet 中。

## Android 构建收敛：单库静态链接与 Java 源码自动对齐

在所有平台中，Android 构建链路从这次迁移中获益最多。

### 告别单独编译 `libSDL2.so` 的三阶段流程

在之前的 [Android 适配博客](https://wszqkzqk.github.io/2026/03/04/PvZ-Portable-Android-Adaptation/)中曾提到：vcpkg 的 `arm64-android` triplet 默认构建静态库（`.a`），但 `SDLActivity.java` 默认会在运行时调用 `System.loadLibrary("SDL2")`。为了迁就这一点，旧版 Android CI 不得不在 `vcpkg.json` 中写 `"platform": "!android"` 排除 SDL2，再分三步走：先下载 SDL2 源码用 NDK 单独编译出动态库 `libSDL2.so`，再构建游戏生成 `libmain.so`，最后写一段脚本把 `libSDL2.so`、`libmain.so` 等拷贝进 `jniLibs` 并逐个 `llvm-strip`。

迁移到 SDL3 时，我们重新审视了 `SDLActivity` 的加载机制。`SDLActivity` 加载哪些原生库完全由 `getLibraries()` 方法决定，而项目的 `PvZPortableActivity` 本来就是 `SDLActivity` 的子类。只要重写 `getLibraries()` 令其只返回 `"main"`（`android/app/src/main/java/io/github/wszqkzqk/pvzportable/PvZPortableActivity.java`）：

```java
@Override
protected String[] getLibraries() {
    return new String[]{"main"};
}
```

那么 Java 层在启动时就只会加载 `libmain.so`。由于 JNI 入口符号（如 `Java_org_libsdl_app_SDLActivity_nativeInit`）在静态链接时同样导出在 `libmain.so` 的动态符号表中，虚拟机在 `libmain.so` 内就能直接解析到所有 SDL3 JNI 函数，**根本不需要单独存在一个 `libSDL3.so` 动态库**。

这一改动直接打通了全静态集成：

1. `vcpkg.json` 移除了 `"platform": "!android"` 限制，Android 与其他 vcpkg 平台一样，直接声明依赖 `"sdl3"` 和 `"sdl3-mixer"`。
2. vcpkg 在 `arm64-android` 下将 `libSDL3.a`、`libSDL3_mixer.a`、`libopenmpt.a`、`libpng.a`、`libjpeg.a` 和 `libz.a` 全部编译为静态库，并在链接 `pvz-portable`（输出名为 `libmain.so`）时一次性静态链入。
3. CI 中原先单独下载编译 SDL 动态库、手动收集 `.so` 和 `-PusePrebuiltLibs=true` 的大段脚本被全部删除，直接交由 Gradle 的 `externalNativeBuild` 驱动 CMake + vcpkg 完成构建。

### 用 Overlay Triplet 处理 Android API 24 的 iconv 兼容

将 Android 的 SDL3 交给 vcpkg 构建后，遇到了一个编译期小插曲：SDL3 的 CMake 脚本如果在系统头文件中检测到 `<iconv.h>`，会默认尝试启用系统 iconv；但在 Android NDK 目标平台设为 API 24（Android 7.0）时，Bionic libc 尚未完整提供部分 iconv 符号，导致链接失败。

为此，我们在仓库中新增了三行的 overlay triplet `CMake/triplets/arm64-android.cmake`（提交 `b16d975d`、`4996a27f`）：

```cmake
include("${VCPKG_ROOT_DIR}/triplets/arm64-android.cmake")
set(VCPKG_CMAKE_SYSTEM_VERSION 24)
list(APPEND VCPKG_CMAKE_CONFIGURE_OPTIONS -DSDL_SYSTEM_ICONV=OFF)
```

它在继承 vcpkg 官方 `arm64-android.cmake` 的基础上，统一将 API 级别固定为 24，并传入 `-DSDL_SYSTEM_ICONV=OFF` 让 SDL3 使用内置的轻量编码转换实现。同样地，iOS 的 `CMake/triplets/arm64-ios.cmake` 也改为通过 `include("${VCPKG_ROOT_DIR}/triplets/community/arm64-ios.cmake")` 继承上游设置（提交 `e69ea810`），只覆写 `VCPKG_OSX_DEPLOYMENT_TARGET`。

### 在 Gradle 中按 vcpkg baseline 自动拉取匹配的 SDL3 Java 源码

Android 构建还有一个细节：APK 需要将 SDL3 提供的 Java 层文件（`SDLActivity.java`、`SDLAudioManager.java` 等）与项目自己的 Java 代码一起编译。这批 Java 文件必须与 `libmain.so` 中静态链接的 SDL3 C 代码版本严格一致，否则一旦两端 JNI 方法签名发生变动就会在启动时抛出 `UnsatisfiedLinkError`。

过去 SDL2 源码是在 CI workflow 脚本里手动 `wget` 的，如果开发者直接在本地用 Android Studio 打开 `android/` 目录点击构建，就会因为找不到 SDL Java 源码目录而报错。

为了同时满足“版本严格对齐”和“支持本地 Android Studio 直接构建”，提交 `26c48fbb` 与 `c3e01839` 在 `android/app/build.gradle` 中注册了一个 `preBuild` 前置任务 `downloadSdl3Java`：

```groovy
tasks.register('downloadSdl3Java') {
    def config = new JsonSlurper().parseText(file("${rootDir}/../vcpkg-configuration.json").text)
    def version = { ->
        if (!vcpkgRoot) {
            throw new GradleException('Set VCPKG_ROOT before building Android.')
        }
        def output = providers.exec {
            commandLine 'git', '-C', vcpkgRoot, 'show', "${config['default-registry'].baseline}:ports/sdl3/vcpkg.json"
        }.standardOutput.asText.get()
        def versionLine = output.readLines().find { it.trim().startsWith('"version":') }
        if (!versionLine) {
            throw new GradleException('Could not determine SDL3 version from the vcpkg baseline.')
        }
        return versionLine.split(':')[1].trim().replaceAll('[",]', '')
    }()
    inputs.property('sdlVersion', version)
    onlyIf { !sdlJavaDir.exists() || !sdlVersionFile.exists() || sdlVersionFile.text.trim() != version }
    doFirst {
        delete sdlJavaDir
        def archive = new File(temporaryDir, "SDL3-${version}.tar.gz")
        ant.get(src: "https://github.com/libsdl-org/SDL/releases/download/release-${version}/SDL3-${version}.tar.gz", dest: archive)
        ant.untar(src: archive, compression: 'gzip', dest: temporaryDir)
        copy {
            from("${temporaryDir}/SDL3-${version}/android-project/app/src/main/java")
            into sdlJavaDir
        }
        sdlVersionFile.text = version
    }
}
```

需要注意为什么这里用 `git -C $VCPKG_ROOT show <baseline>:ports/sdl3/vcpkg.json` 而不是执行 `vcpkg search sdl3`：因为开发者本机的 `$VCPKG_ROOT` 可能检出在任意分支或较新的提交上，`vcpkg search` 返回的是工作区当前 HEAD 的端口版本；而项目启用了 vcpkg manifest 模式，实际构建安装的版本是由仓库根目录 `vcpkg-configuration.json` 里的 `baseline` commit 锁定的。直接用 `git show` 读取该 baseline 提交下 `ports/sdl3/vcpkg.json` 的版本号，并缓存到 `build/sdl3-src/.../.pvz-version` 中，就能确保无论在 CI 还是本地 IDE 中，Java 源码都与 vcpkg 实际编译出的 `libSDL3.a` 分毫不差。

## WebAssembly (Emscripten) 下的混合构建

WebAssembly 平台面临的是另一种不对称局面：**Emscripten 已经内置了官方的 `sdl3` port（通过 `-sUSE_SDL=3` 启用），但还没有提供 `SDL3_mixer` port**。

这意味着 `SDL3` 来自 Emscripten 的内置端口机制，而 `SDL3_mixer` 必须由 `wasm/build-wasm.sh` 从源码构建。怎样让从源码构建的 `SDL3_mixer` 认识 Emscripten 的 `-sUSE_SDL=3`？

### 从伪造 CMake Package 到 14 行接口目标桥接

在 `refactor/sdl3-migration` 分支的中间几次提交（`a8b7edff`、`bd2f66ba`、`d839ef38`）中，笔者最初走了一条比较曲折的路：先在 `build-wasm.sh` 里解析 Emscripten 的 `tools/ports/sdl3.py` 提取版本号，手动在临时目录生成 `SDL3Config.cmake` 和 `SDL3ConfigVersion.cmake`，再单独调用一次 `emcmake cmake` 编译安装 `SDL3_mixer`，最后再配置主项目。

回头审视这套流程，之所以要生成假的 `SDL3Config.cmake`，仅仅是因为把 `SDL3_mixer` 当成了外部独立工程去调 `find_package(SDL3)`。实际上，如果检查 `SDL3_mixer` 自身的 `CMakeLists.txt`，它在被作为子目录包含时，只要求当前 CMake 作用域内已经存在 `SDL3::Headers` 和 `SDL3::SDL3` 目标即可。

于是提交 `43bf5271`（`Refactor: build SDL3_mixer directly for Emscripten`）将整套伪造包元数据的脚本全部删掉，换成了 14 行的 `CMake/EmscriptenSDL3.cmake`：

```cmake
if(NOT TARGET SDL3::Headers)
	add_library(SDL3::Headers INTERFACE IMPORTED)
	set_target_properties(SDL3::Headers PROPERTIES
		INTERFACE_COMPILE_OPTIONS "-sUSE_SDL=3"
	)
endif()

if(NOT TARGET SDL3::SDL3)
	add_library(SDL3::SDL3 INTERFACE IMPORTED)
	set_target_properties(SDL3::SDL3 PROPERTIES
		INTERFACE_COMPILE_OPTIONS "-sUSE_SDL=3"
		INTERFACE_LINK_LIBRARIES "-sUSE_SDL=3"
	)
endif()
```

在 Emscripten 构建时，`wasm/build-wasm.sh --deps` 只需先执行 `embuilder build sdl3 vorbis` 预热端口并拉取 `SDL3_mixer` 源码目录，随后在一次 CMake 配置中通过 `include(CMake/EmscriptenSDL3.cmake)` + `add_subdirectory("${PVZP_SDL3_MIXER_SOURCE_DIR}" ...)` 将 `SDL3_mixer` 与主项目一同编译。编译与链接选项 `-sUSE_SDL=3` 通过 `SDL3::SDL3` 接口目标自然传递给 `SDL3_mixer` 和 `pvz-portable`，省去了中间安装步骤。

### Emscripten 与 Linux 静态构建中的 Vorbis 后端分工

项目同时使用了 `libopenmpt` 和 `SDL3_mixer`，而这两个库都可能涉及 Ogg Vorbis 解码（`.mo3` 格式内部可以使用 Vorbis 压缩采样，片尾曲和部分音效则是 `.ogg` 文件）。在不同平台上，如何配置两者的 Vorbis 后端很有讲究：

- **Linux 全静态构建（`build-linux-static`）**：
  在 `manylinux_2_34_x86_64` 容器中（见[构建跨发行版的 Linux 二进制](https://wszqkzqk.github.io/2026/08/09/PvZ-Portable-Static-Linux-Build/)），所有第三方库都以 `.a` 静态归档形式链接进同一个可执行文件。`SDL3_mixer` 默认启用内置的 `stb_vorbis`（`SDLMIXER_VORBIS_STB=ON`），但如果系统或另一静态库同时链接了标准 `libvorbis`，静态链接阶段就容易产生符号冲突或重复打包两套 Vorbis 解码器（提交 `4e5cbe51`、`b16d975d`）。
  因此在 Linux 静态构建中，CI 显式从源码静态编译了 `libogg` 与 `libvorbis`，并在构建 `SDL3_mixer` 时指定 `-DSDLMIXER_VORBIS_STB=OFF -DSDLMIXER_VORBIS_VORBISFILE=ON`，让 `SDL3_mixer` 复用同一套静态 `libvorbis`。
- **Emscripten 构建（`build-wasm`）**：
  在 Emscripten 下，`libopenmpt` 通过 `EMSCRIPTEN_PORTS=1` 启用了 Emscripten 官方的 `-sUSE_VORBIS=1 -sUSE_MPG123=1` 端口（提交 `3f677e0c`）。而对于源码编译的 `SDL3_mixer`，如果开启 `VORBISFILE`，CMake 的 `find_package(Vorbis)` 在 Emscripten 交叉编译环境下无法直接识别 `-sUSE_VORBIS=1` 编译器标志形式的端口；反过来，直接为 `SDL3_mixer` 启用其内置的单文件 `-DSDLMIXER_VORBIS_STB=ON -DSDLMIXER_VORBIS_VORBISFILE=OFF`（`stb_vorbis` 内部符号为模块私有，不与 `libvorbis` 导出符号冲突），既不需要额外传递端口查找路径，又能直接编译通过。

## 静态目标选择与 Switch 构建配方更新

最后简要记录其余几个平台在构建配置上的收尾改动。

### MinGW 与静态构建的目标选择

在 SDL2 时代，`SDL2::SDL2main` 和 `SDL-Mixer-X` 的 CMake 目标在接口依赖中硬编码了共享库目标 `SDL2::SDL2`。为了在 `BUILD_STATIC=ON`（如 Linux 静态构建或 MinGW 静态构建）时强制链接静态库，过去的 `CMakeLists.txt` 里不得不写一个 18 行的 `_pvz_patch_sdl2_iface_libs` 函数，去遍历并篡改已有目标的 `INTERFACE_LINK_LIBRARIES` 属性。

迁移到 `SDL3` 与 `SDL3_mixer` 后，上游的 CMake 导出目标规范了许多，而且 `SDL3` 不再需要单独链接 `SDL2main` 静态库（`<SDL3/SDL_main.h>` 已改为 header-only 实现）。因此，那段修改目标属性的 hack 函数被彻底移除，静态构建下的目标选择简化为（提交 `a188c511`）：

```cmake
set(PVZP_SDL3_TARGET SDL3::SDL3)
set(PVZP_SDL3_MIXER_TARGET SDL3_mixer::SDL3_mixer)
if(BUILD_STATIC)
	if(TARGET SDL3::SDL3-static)
		set(PVZP_SDL3_TARGET SDL3::SDL3-static)
	endif()
	if(TARGET SDL3_mixer::SDL3_mixer-static)
		set(PVZP_SDL3_MIXER_TARGET SDL3_mixer::SDL3_mixer-static)
	endif()
endif()
```

### 统一 `libopenmpt` 静态依赖探测

在 `CMakeLists.txt` 中，此前针对 `EMSCRIPTEN` 和常规桌面平台分别写了两套查找 `libopenmpt` 的逻辑。提交 `b210e9e7`（`Refactor: unify libopenmpt discovery`）将它们合并到了平台分支之前：若使用 vcpkg 则直接 `find_package(libopenmpt CONFIG REQUIRED)`；否则通过 `find_library` + `find_path` 查找，且当检测到 `OPENMPT_LIBRARY` 为 `.a` 静态库时（非 Emscripten/Switch），自动用 `check_cxx_source_compiles` 测试其是否能独立链接——若该静态库未内联二级依赖，则自动补齐 `mpg123`、`vorbisfile`、`vorbis` 和 `ogg`。

### Nintendo Switch 的最小化 SDL3 构建

Nintendo Switch 平台的窗口管理（EGL + `libnx`）和手柄/触屏输入在项目中本来就是独立实现的（位于 `src/SexyAppFramework/platform/switch/Window.cpp` 和 `Input.cpp`），实际上只使用了 SDL 的音频与基础计时设施。

在 devkitPro 环境下构建 Switch 版本时（见 `.github/workflows/ci.yml` 中的构建配方，提交 `967d3ff3`、`82ef5d08`、`274da57c`），我们通过 `git sparse-checkout` 拉取社区的 `neomody77/sdl3-switch` 补丁并校验 SHA-256，随后以最小化配置编译静态 `SDL3`：

```bash
aarch64-none-elf-cmake -G "Unix Makefiles" -S "SDL3-${SDL3_TAG}" -B build-sdl3 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$PORTLIBS_PREFIX" \
  -DSDL_SHARED=OFF \
  -DSDL_STATIC=ON \
  -DSDL_VIDEO=OFF \
  -DSDL_JOYSTICK=OFF \
  -DSDL_HAPTIC=OFF \
  -DSDL_TESTS=OFF \
  -DSDL_EXAMPLES=OFF
```

将 `SDL_VIDEO`、`SDL_JOYSTICK` 和 `SDL_HAPTIC` 全部关闭后，不仅缩短了编译时间，也避免了 SDL 的视频/手柄子系统与项目自身的 `libnx` 初始化逻辑发生冲突。

## 结语

纵观整个 SDL3 迁移系列，代码与构建两个层面的改造指向同一个结论：**减少非必要的中间层与特判分支，长期来看总是划算的**。

在代码层面，去掉 14 万行的 `SDL-Mixer-X`，换来的是 190 行职责单一的 `OpenMptMusic` 和干净的 `MusicInterface`；启用 `SDL_WINDOW_HIGH_PIXEL_DENSITY`、`<SDL3/SDL_main.h>` 和 `SDL_DelayNS`，换来的是高分屏坐标系的理顺以及多段 Win32/iOS 平台胶水代码的退场。

在构建层面，放弃 `FetchContent` 的包揽式做法、在 Android 上利用静态链接消掉独立的 `libSDL.so`、在 Emscripten 下用 14 行 `INTERFACE IMPORTED` 目标桥接端口与源码子目录，则让七个平台的构建配置各自收敛到了最简形态。底层的包袱清理干净后，后续的功能演进与跨平台维护也就有了一个更轻便的起点。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。研究或使用此项目时，**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies)购买）。你需要从正版游戏中提取以下文件，放到 PvZ-Portable 的程序所在目录：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
