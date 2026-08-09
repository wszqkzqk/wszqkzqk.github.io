---
layout:       post
title:        PvZ-Portable：构建跨发行版的 Linux 二进制
subtitle:     使用 manylinux 控制 glibc 基线，并静态链接第三方依赖
header-img:   img/games/pvz-portable/bg-pvz-portable.webp
date:         2026-08-09
author:       wszqkzqk
catalog:      true
tags:         静态链接 Linux 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

Linux 是 PvZ-Portable 最早支持的平台之一，不过目前 GitHub Releases 中的 Linux 二进制只有 Arch Linux 版本。Linux 上的软件本来就常以源码形式分发，再由各发行版维护者制作软件包，或者由用户按照自己的环境编译。因此，项目此前也没有专门提供一份面向各个发行版的通用二进制。

源码编译对 Linux 用户并不陌生，但如果只是想运行游戏，还要先准备工具链、安装依赖，对部分用户多少有些麻烦。发布一份能在多种发行版上运行的预编译程序，可以让用户在准备好正版游戏资源后直接运行引擎，不必再搭建编译环境。

PvZ-Portable 本身是一个用于研究与教育的项目。除了提供现成的构建产物，这次工作的另一项主要目的，就是为 PvZ-Portable 找到一套合适的跨发行版 Linux 二进制分发方案。为此需要厘清哪些依赖应当静态链接进程序，哪些接口必须留给宿主系统，以及怎样同时使用较旧的 glibc 基线和较新的编译器。

相关改动已经合入 [#432](https://github.com/wszqkzqk/PvZ-Portable/pull/432)。构建产物 `pvz-portable-linux-static-x86_64` 并非完全静态链接：glibc 以及显示、音频和 OpenGL 后端仍由系统提供，其余构建依赖则放进可执行文件。这套链接配置既用于 release CI，在准备好静态库的本地环境中也可以直接使用。

## 为何不用 Flatpak 或 AppImage 等沙箱方案

Flatpak 和 AppImage 都能用来分发跨发行版的 Linux 应用。前者提供统一的运行时和沙箱，后者把程序及其依赖组织成一个可执行镜像。单从解决动态库兼容问题来看，两者都可以考虑。

PvZ-Portable 的情况有所不同。项目只能发布开源重实现的引擎，不能附带《植物大战僵尸》的美术、音效和关卡等资源。用户仍然需要从自己拥有的正版游戏中提取 `main.pak` 和 `properties/`，再交给 PvZ-Portable 读取。即使制作了 Flatpak 或 AppImage，得到的也不是一个资源完整、安装后即可运行的应用包。

技术上当然可以只把引擎放进这些格式，再让用户另外导入资源，但这样会增加资源路径和权限处理。Flatpak 还需要考虑沙箱内外的文件访问；AppImage 则仍要在镜像之外保留游戏资源，无法发挥自包含打包的主要优势。对当前项目而言，这层封装带来的收益有限。

因此，release 仍然只提供不含游戏资源的单独二进制。用户将它与自行提取的资源放在同一目录即可，分发内容也能清楚地限定为开源引擎本身。

## 确定链接边界

跨发行版二进制首先要处理动态库版本。Arch Linux 更新较快，在 Arch 环境中直接构建的程序通常会引用较新的 glibc、libstdc++ 和第三方共享库。换到 Debian stable 或较旧的 Ubuntu 后，目标系统可能没有相应的 SONAME，也可能缺少程序引用的符号版本，此时程序在启动阶段就会报错。

为每个发行版分别提供动态链接构建也不能形成稳定的长期方案。Arch Linux 是滚动发行版，仓库只有持续更新的当前版本，因此 Arch 构建只需跟随最新的稳定软件包。Ubuntu、Debian 和 Fedora 等发行版则同时维护多个版本，不同版本使用的 glibc 和第三方库并不一致。即使为其中一个版本完成构建，后续的发行版升级或依赖 SONAME 变化也可能要求重新编译。笼统地发布一个“Ubuntu 版”或“Fedora 版”，无法说明它究竟兼容哪些系统版本。

静态链接可以消除大部分这类依赖，但不能简单地给链接器传入全局 `-static`。SDL2 仍要使用宿主系统的显示、音频和 OpenGL 实现，因此需要先确定 libc 与这些运行时组件之间的边界。

### 为什么不能静态链接 musl

musl 经常用于构建静态程序，但它的静态可执行文件不支持动态加载共享库。对服务端工具而言，这可能不是问题；但对 SDL2 游戏而言，无法使用 `dlopen` 就意味着无法按需加载显示、音频和 OpenGL 后端。将程序改用 musl，并不能满足这里的运行时要求。

### 为何不可静态链接 glibc

使用 glibc 并传入 `-static` 同样不合适。glibc 的名称解析、NSS 等功能本来就会在完全静态链接时产生限制，链接器也会给出相应警告。更直接的问题仍然是图形驱动：程序需要加载宿主提供的 `libGL` 或 Mesa 驱动，而这些共享对象依赖宿主的动态 glibc。

如果可执行文件已经包含一份静态 glibc，之后又加载依赖动态 glibc 的共享对象，同一进程内就可能出现两套 C 运行时状态。内存分配、线程状态和 locale 等行为都难以保证。即使某个环境下能够启动，也不适合作为发布方案。

### 最终方案

最终采用的是动态 glibc 加静态第三方依赖。glibc 会在二进制中记录所引用符号的版本。使用较旧的构建基线，可以避免引入新版本符号，从而让程序在更多较新的发行版上运行。

这次构建的链接边界如下：

- 目标架构为 x86_64；
- glibc 保持动态链接，并将最低版本控制在 2.34；
- 显示、音频和 OpenGL 实现由目标系统提供，SDL2 在运行时加载；
- SDL2、C++ 运行时及其余第三方库静态链接进可执行文件。

这里所说的“跨发行版”有明确范围：目标系统仍需使用 glibc 2.34 或更新版本，并具备可用的桌面图形与音频环境。它解决的是发行版之间常见的用户态依赖差异，不是制作一个脱离宿主系统的 Linux 程序。

## 使用 manylinux 控制 glibc 基线

笔者最初计划使用 `ubuntu:22.04` 容器，对应 glibc 2.35 和 GCC 11。这个版本的兼容下限尚可，但不适合作为长期使用的发布环境。Ubuntu 22.04 的标准支持将在 2027 年结束，已经处在生命周期后段；仓库中的编译器、构建工具和许多开发库也停留在发行时的版本。若改用更新的 Ubuntu 容器，虽然能获得较新的工具链，却会同时提高 glibc 版本，缩小二进制能够覆盖的系统范围。

最终使用的是 `manylinux_2_34_x86_64`：

```yaml
  build-linux-static:
    name: Build for Linux (x86_64, static)
    runs-on: ubuntu-latest
    container: quay.io/pypa/manylinux_2_34_x86_64 # Old glibc baseline with a recent toolchain
```

manylinux 镜像由 Python 打包社区维护，主要用于构建可移植的 Python wheel，不过镜像提供的系统环境也可以直接用于普通 C/C++ 项目。`manylinux_2_34` 基于 AlmaLinux 9，将 glibc 基线固定在 2.34，同时提供 GCC 14 等较新的构建工具。项目所需的主要第三方库又会从源码构建，因此不必受 Ubuntu 22.04 仓库版本的限制。

glibc 版本决定了程序的主要兼容下限，编译器版本则不必与它同步停留在旧版本。manylinux 将二者分开维护，可以在不改变 glibc 2.34 兼容基线的前提下使用新工具链。由于 libgcc 和 libstdc++ 会静态链接，使用 GCC 14 也不会要求目标系统安装同版本的 C++ 运行时。

## 静态链接第三方依赖

Linux 上启用 `BUILD_STATIC` 时，项目在 `CMakeLists.txt` 中设置：

```cmake
	elseif(CMAKE_SYSTEM_NAME STREQUAL "Linux")
		set(CMAKE_FIND_LIBRARY_SUFFIXES ".a")
		set(BUILD_SHARED_LIBS OFF)
```

`CMAKE_FIND_LIBRARY_SUFFIXES` 让 `find_library` 只搜索 `.a`，因此 Zlib、libpng 和 libjpeg-turbo 等依赖都会解析到静态归档。这里没有使用全局 `-static`，否则链接器也会尝试静态链接 glibc。libgcc 和 libstdc++ 则通过 `-static-libgcc -static-libstdc++` 单独静态链接，避免依赖目标系统中的 C++ 运行时版本。

SDL2 的 CMake 包同时导出 `SDL2::SDL2` 和 `SDL2::SDL2-static`，但 `SDL2::SDL2main` 的接口依赖指向前者，项目内置的 SDL-Mixer-X 也会传递这个依赖。如果不处理，最终链接时仍会引入共享版 SDL2。项目在之前就增加了一个辅助函数，将接口中的目标替换为 `SDL2::SDL2-static`：

```cmake
function(_pvz_patch_sdl2_iface_libs target)
	get_target_property(_libs ${target} INTERFACE_LINK_LIBRARIES)
	if(NOT _libs)
		return()
	endif()
	set(_patched)
	foreach(_lib IN LISTS _libs)
		if(_lib STREQUAL "SDL2::SDL2")
			list(APPEND _patched SDL2::SDL2-static)
		else()
			list(APPEND _patched "${_lib}")
		endif()
	endforeach()
	set_target_properties(${target} PROPERTIES INTERFACE_LINK_LIBRARIES "${_patched}")
endfunction()
```

这个函数分别用于 `SDL2::SDL2main` 和 `SDL2_mixer_ext_Static`。改动只发生在顶层构建配置中，不需要修改 vendored SDL-Mixer-X 的 CMake 文件。

构建 SDL2 时仍然需要安装 X11、Wayland、libxkbcommon、ALSA、PipeWire、PulseAudio 和 OpenGL 对应的 `-devel` 包，以便检测并编译这些后端。SDL2 在运行时通过 `dlopen` 查找实际的共享库，因此它们不会全部成为可执行文件的直接动态依赖。KMSDRM、JACK、SNDIO、DBus、IBus、libudev 和 libsamplerate 等当前不需要的可选组件则在配置时关闭。

## 在 manylinux 中准备静态库

AlmaLinux 9 的仓库并没有提供这次构建所需的全部静态库。Zlib 可以从 CRB 仓库安装 `zlib-static`，libpng、libjpeg-turbo、libogg 和 libvorbis 等依赖则需要自行构建。CI 将它们统一安装到私有前缀 `~/pvz-deps`，随后通过 `CMAKE_PREFIX_PATH` 交给游戏的 CMake 配置查找。

这些依赖使用三套构建系统：

- SDL2、libpng 和 libjpeg-turbo 使用 CMake，分别关闭共享库、测试程序和当前用不到的工具；libjpeg-turbo 另外启用 NASM 优化。
- mpg123、libogg 和 libvorbis 使用 autotools。mpg123 只构建解码库；libvorbis 通过 `PKG_CONFIG_PATH` 查找私有前缀中刚构建的 libogg。
- libopenmpt 使用项目自带的 makefile，以 `CONFIG=gcc STATIC_LIB=1` 构建，并通过 `NO_ZLIB=1`、`NO_MPG123=1`、`NO_OGG=1` 等选项关闭游戏不需要的可选依赖。

libogg 的源码包没有提供 CMake 构建入口，所以这里直接使用 Xiph 发布的 tarball 和 `./configure`。各项目的构建参数虽然不同，但结果都安装到同一个前缀，游戏的链接阶段不需要了解这些差异。

## 在本地使用静态构建配置

上面的静态链接配置并不依赖 GitHub Actions。CI 负责准备统一的 glibc 基线、工具链和依赖，实际的链接策略则由项目自身的 CMake 配置控制。本地环境只要已经准备好各项依赖的 `.a` 静态库，也可以启用 `BUILD_STATIC`。

例如，静态库已经安装到一个独立前缀时，可以这样配置：

```bash
cmake -S . -B build-static \
  -DBUILD_STATIC=ON \
  -DCMAKE_PREFIX_PATH=/path/to/pvz-deps \
  -DCMAKE_EXE_LINKER_FLAGS="-static-libgcc -static-libstdc++"
cmake --build build-static --parallel
```

本地构建会使用本机的 glibc 作为基线。如果需要得到与 release 相同的 glibc 2.34 兼容范围，仍应在 `manylinux_2_34_x86_64` 或具有相同基线的环境中完成链接；`BUILD_STATIC` 本身只负责选择静态依赖，并不会自动降低 glibc 版本要求。

## CI 工作流细节

### Git 仓库与版本号

在 GitHub Actions 中，checkout 目录属于 runner 用户，而容器内的步骤以 root 运行。Git 会将这种属主差异报告为 `dubious ownership`，因此工作流先把仓库加入 safe directory：

```yaml
    - name: Fix Git Safe Directory
      run: git config --global --add safe.directory "$GITHUB_WORKSPACE"
```

这个 job 在配置阶段通过 `git describe` 生成项目版本号，相关实现来自 [#385](https://github.com/wszqkzqk/PvZ-Portable/pull/385)。因此 checkout 使用 `fetch-depth: 0` 获取完整历史；如果容器内的 Git 无法访问仓库，版本号会退回默认值。

### 依赖版本

工作流在每次构建开始时查询依赖的最新稳定版本，同时为每个依赖保留一个已知可用的回退版本。SDL2 的版本解析如下：

```bash
SDL2_TAG=$(git ls-remote --tags https://github.com/libsdl-org/SDL.git 'refs/tags/release-2.*' \
  | sed 's|.*refs/tags/release-||' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1 || true)
if [ -z "$SDL2_TAG" ]; then
  SDL2_TAG="2.32.10" # Fallback to a known stable version if tag retrieval fails
fi
```

查询范围限制在 SDL2 2.x 的 `release-2.*` 标签内。mpg123 没有用于这套流程的 Git 标签，因此改为读取 SourceForge 的 `best_release.json`。查询失败时使用固定版本，避免上游服务短暂不可用导致整个 job 无法运行。

这种策略会自动吸收依赖的新版本，但同一个 Git commit 在不同时间运行时，解析出的依赖版本可能不同。工作流会把最终版本写入环境并纳入缓存键，以便从 CI 日志和缓存名称中确认一次构建实际使用了哪些版本。

### 依赖缓存

七个依赖全部从源码构建耗时较长，因此 `~/pvz-deps` 会整体写入 `actions/cache`。缓存键包含每个依赖解析后的版本：

```yaml
        key: linux-static-deps-v2-${{ env.SDL2_TAG }}-${{ env.OPENMPT_TAG }}-${{ env.MPG123_VERSION }}-${{ env.LIBPNG_VERSION }}-${{ env.JPEG_TURBO_VERSION }}-${{ env.OGG_VERSION }}-${{ env.VORBIS_VERSION }}
```

只要任一依赖升级，就会生成新的缓存键。构建参数或补丁发生变化时，则手动递增键中的 `vN`，使旧构建配方产生的缓存失效。

缓存恢复和保存使用独立步骤。restore 位于依赖构建之前，save 只在全部依赖成功安装后执行。job 中途失败时，未完成的 `~/pvz-deps` 不会进入缓存，下一次运行也就不会复用一份只构建了一半的依赖树。

## 构建结果

CI 最终生成经过 strip 的单文件 `pvz-portable-linux-static-x86_64`。它仍然要求 x86_64、glibc 2.34 以上版本，以及目标系统中可用的显示、音频和 OpenGL 驱动；项目构建所需的其他第三方库则由程序自身携带。

这份构建不会取代源码发布或现有的 Arch Linux 版本。对用户而言，它增加了一种免编译的选择；对项目而言，它验证了一套不依赖特定发行版版本的构建方法。固定 glibc 基线并静态链接其余依赖后，兼容范围由 glibc 版本和必要的系统接口决定，不再依附于某个发行版某次更新时提供的整套动态库。

## ⚠️ 版权与说明

《植物大战僵尸》的 IP 归 PopCap/EA 所有。

本项目只包含开源重实现的引擎代码，不包含游戏美术、音效、关卡等受版权保护的资源文件。使用本项目时需要拥有正版游戏；如尚未购买，可前往 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 购买。请从正版游戏中提取以下内容，并放入 PvZ-Portable 程序所在的目录：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 LGPL-3.0-or-later 许可证发布。
