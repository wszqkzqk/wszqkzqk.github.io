---
layout:       post
title:        将 Android 手机打造为全功能的 ARM Linux 服务器
subtitle:     利用 Termux 释放手机的计算、存储与图形能力
date:         2026-10-18
author:       wszqkzqk
header-img:   img/android/termux/weston-in-android-showing-with-kde.webp
header-mask:  0.5
catalog:      true
tags:         Termux Android Linux ARM SSH sshfs Wayland
---

## 前言

ARM Linux 服务器的用途很多：编译和测试 aarch64 程序、运行脚本和定时任务、同步文件、处理媒体，甚至提供远程图形界面。不过，专门准备一台这样的机器并不总是方便：开发板需要购买和配置，云服务器需要持续付费，一些低配实例的性能也比较有限。

而 Android 手机几乎人人都有，它的硬件潜力却经常被忽略。现在手机 SoC 的单核、多核性能，完全可能超过一些租来的低配服务器，存储、网络和电池也都是现成的。借助 Termux，手机可以运行 OpenSSH、Clang、FFmpeg 等 Linux 软件，覆盖个人服务器的大部分常见用途。

启动 `sshd` 后，手机便具备了服务器最基本的远程控制能力：电脑可以登录终端、执行命令和传输文件，也可以通过 sshfs 挂载手机目录。利用 Termux 丰富的软件包，编译、转码和后台服务等任务都可以交给手机完成。再结合 Waypipe 和 `x11-repo` 提供的 GUI 应用，手机还能成为一台具备 GUI 能力的 ARM Linux 服务器。在手机 GPU 的支持下，它在这类任务上甚至可能比没有 GPU 的 Linux 服务器更有优势。把这些能力组合起来，Android 手机作为 ARM Linux 服务器的表现确实超乎想象：个人使用中的常见任务几乎都能交给它完成。

## Termux 与 SSH 基本配置

Termux 可以从其[官方网站](https://termux.dev/)列出的渠道安装。Termux 及其附加应用应保持相同的安装来源和签名，否则可能因签名不一致而无法安装或升级。

安装后先更新软件包，并安装 OpenSSH：

```bash
pkg update
pkg upgrade
pkg install openssh
```

临时启动 SSH 服务可以运行：

```bash
sshd
```

服务以 Termux 应用用户运行，默认监听 **8022** 端口。登录用户名可以通过以下命令查看：

```bash
whoami
```

它通常是 `u0_aXXX` 形式的 Android 应用用户名。

### 添加公钥

在 Termux 中创建 SSH 配置目录，并将电脑上的公钥追加到 `authorized_keys`：

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo '<公钥内容>' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

公钥内容通常是电脑上 `~/.ssh/id_ed25519.pub` 等文件中的一整行，私钥则保留在电脑上。完成后即可使用密钥登录：

```bash
ssh -p 8022 <Termux用户名>@<手机地址>
```

手机地址可以来自局域网，也可以来自自己使用的加密组网。直接暴露到公网时，还需要认真考虑访问控制和服务安全。

登录后可以确认设备的架构：

```bash
uname -m
```

在常见的 64 位 ARM 手机上，输出为：

```text
aarch64
```

### 使用 runit 管理 sshd

直接运行 `sshd` 适合临时使用。需要服务状态管理和自动启动时，可以使用 `termux-services`：

```bash
pkg install termux-services
```

安装后重新打开一次 Termux 会话，让 service-daemon 启动，然后启用 SSH 服务：

```bash
sv-enable sshd
sv status sshd
```

常用的服务控制命令包括：

```bash
sv up sshd
sv down sshd
sv-disable sshd
```

`sv up` 和 `sv down` 用于启动和停止服务。`sv-disable` 会同时停止服务并关闭自动启动，之后可以用 `sv-enable` 重新启用。

### 本地交互使用 fish

默认 shell 可以保持 Bash，只在 Termux 本地交互会话中使用 fish。先安装 fish：

```bash
pkg install fish
```

Termux 的 `$PREFIX/bin/login` 会在启动 shell 前加载 `$PREFIX/etc/termux-login.sh`。将以下内容写入该文件：

```bash
if [ -z "$SSH_CONNECTION" ] && [ -z "$SSH_CLIENT" ] && [ -x "$PREFIX/bin/fish" ]; then
    SHELL="$PREFIX/bin/fish"
fi
```

`login` 默认会从 `~/.termux/shell` 取得 Bash。这段配置只在本地 Termux 会话中将其改为 fish。检测到 SSH 连接时仍使用 Bash，远程命令和脚本的默认环境因此保持一致。重新打开 Termux 会话后生效。

## 文件传输与 sshfs 挂载

### scp、sftp 与 rsync

安装 `openssh` 后，`scp` 和 `sftp` 就可以直接通过 SSH 服务传输文件。例如，在电脑上执行：

```bash
scp -P 8022 ./input.bin <Termux用户名>@<手机地址>:
```

对于需要反复同步的源码目录，`rsync` 更方便。手机端可以安装：

```bash
pkg install rsync
```

电脑端也需要有 `rsync`。之后可以增量同步整个目录：

```bash
ssh -p 8022 <Termux用户名>@<手机地址> mkdir -p projects
rsync -av -e 'ssh -p 8022' ./example/ <Termux用户名>@<手机地址>:projects/example/
```

### 将手机目录挂载到 Linux

前面介绍的 `scp` 和 `rsync` 已经能让电脑访问手机中的文件，不过每次都需要手动复制或同步。使用 sshfs 将手机目录挂载到 Linux 后，就可以像访问本地文件一样打开和修改手机文件。无论文件管理器、编辑器还是其他本地程序，都可以直接操作这些文件，方便很多。

在 Linux 电脑上安装 sshfs。以 Arch Linux 为例：

```bash
sudo pacman -S sshfs
```

建立一个临时挂载点，并将手机的 Termux 家目录挂载过去：

```bash
mkdir -p /tmp/phone-sshfs
sshfs -o idmap=user,follow_symlinks -p 8022 <Termux用户名>@<手机地址>: /tmp/phone-sshfs
```

其中：

- 远程地址末尾的冒号后没有指定路径，因此挂载的是 Termux 用户的家目录。
- `idmap=user` 用于处理本地用户和远程 Termux 用户之间的身份映射。
- `follow_symlinks` 让 sshfs 跟随远程符号链接，后面访问 Termux 的 `storage` 链接时会用到。

挂载完成后，Termux 家目录就对应到 `/tmp/phone-sshfs`。可以直接在本地编辑器中打开其中的源码，也可以用文件管理器查看手机文件。在编辑器中所做的修改会直接写回手机。

使用完毕后可以卸载：

```bash
fusermount3 -u /tmp/phone-sshfs
```

较早的系统中，对应的命令可能是 `fusermount -u`。

涉及大量小文件读写、锁和元数据操作的构建任务，适合通过 SSH 在手机本地目录中执行，以获得更稳定的性能和文件系统语义。

## 访问手机共享存储

前面的挂载对应的是 Termux 家目录。手机中已有的照片、视频和下载文件位于共享存储，完成 Android 存储授权后，也能通过同一个挂载访问。授权命令需要在 **Termux 中**运行：

```bash
termux-setup-storage
```

按照 Android 的提示完成授权后，Termux 会在家目录下建立 `storage` 目录及若干符号链接。例如，`~/storage/shared` 指向手机的共享存储，常见的 `DCIM`、`Download`、`Movies` 等目录就在其中。

此前建立的 sshfs 挂载可以直接访问这些链接：

```bash
ls /tmp/phone-sshfs/storage/shared/
ls /tmp/phone-sshfs/storage/shared/DCIM/
```

同一个挂载点由此也能用于处理手机中已有的媒体文件。处理后的结果可以放回共享存储，供其他 Android 应用继续使用。

两类目录适合承担不同的任务：

- **Termux 私有目录**：源码、构建目录、Git 工作区、运行时文件和 Unix socket。
- **手机共享存储**：照片、视频、下载文件，以及需要与其他 Android 应用交换的结果。

共享存储的执行权限、符号链接及其他 POSIX 语义受到 Android 实现方式影响，源码和构建目录放在 Termux 私有目录中更稳妥。

## 在手机上编译项目

手机也可以直接承担源码获取和构建任务。Termux 提供了完整的原生编译工具链，按常见 C/C++ 项目的需要，可以安装：

```bash
pkg install clang cmake ninja make pkg-config git
```

工具链就绪后，可以直接在手机上克隆并构建项目。以使用 CMake 的项目为例：

```bash
mkdir -p ~/projects
git clone <项目仓库地址> ~/projects/example
cd ~/projects/example
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel "$(nproc)"
```

如果项目带有测试，还可以继续运行：

```bash
ctest --test-dir build --output-on-failure
```

`--parallel "$(nproc)"` 按设备的可用核心数设置并行度，也可以结合手机内存和温度手动调整。

如果需要修改源码，可以在电脑上通过 sshfs 编辑，再通过 SSH 在手机上执行构建。这样既保留了电脑的编辑环境，也让编译、依赖检查和测试实际发生在手机的 ARM 环境中。

通过 `clang -v` 可以看到，Termux 编译器的目标通常是 `aarch64-unknown-linux-android` 及对应的 Android API 级别。程序直接在 Termux 的 Android/Bionic 用户空间中构建和运行，产物也面向这一环境。

C/C++ 项目可以利用 `__ANDROID__` 和 `__TERMUX__` 区分 Android 与 Termux 的代码路径。笔者在 PvZ-Portable 的适配中遇到过这类差异，具体例子见[社区开源引擎实现的 Android 适配全纪录](https://wszqkzqk.github.io/2026/03/04/PvZ-Portable-Android-Adaptation/)中的“Termux 兼容性”部分。

## 使用 FFmpeg 处理手机中的视频

编译属于通用计算，视频处理则能进一步利用手机 SoC 中专门的编解码硬件。近年来，短视频和手机摄影的发展促使厂商不断优化这些硬件，使手机在视频编解码速度和能效上很有优势。Termux 中的 FFmpeg 可以通过 Android 的 MediaCodec 接口使用这些能力：

```bash
pkg install ffmpeg
```

完成前文所述的存储授权后，就能直接处理共享存储中的文件。以支持 HEVC MediaCodec 编码的设备为例：

```bash
ffmpeg -hwaccel mediacodec \
    -i /sdcard/Movies/input.mp4 \
    -pix_fmt yuv420p \
    -c:v hevc_mediacodec \
    -c:a copy \
    /sdcard/Movies/output-hevc.mp4
```

处理完成后，在已经挂载的 Linux 目录中打开 `storage/shared/Movies/`，就能直接使用输出文件。

不同设备支持的硬件编解码器、像素格式和质量控制方式有所差异。MediaCodec 的详细用法、硬件能力查看方法和实际功耗表现，可以参见笔者此前的[利用 Android 手机硬件进行高效灵活的编解码](https://wszqkzqk.github.io/2025/10/26/Termux-Hardware-Acceleration/)。将这套能力与 SSH、共享存储和 sshfs 配合起来，手机中的素材和转码结果就能直接进入电脑上的工作流。

## 后台任务与 SSH 断线

编译和转码都可能持续较长时间，适合放在手机端的 tmux 中运行：

```bash
pkg install tmux
```

新建一个用于转码的会话：

```bash
tmux new -s transcode
```

在其中启动任务后，按 `Ctrl+b`，再按 `d`，即可脱离会话。SSH 连接断开后，tmux 中的进程仍会继续运行。重新登录手机后，可以恢复查看：

```bash
tmux attach -t transcode
```

tmux 负责保存终端会话。需要让手机在执行任务期间保持唤醒时，可以配合使用：

```bash
termux-wake-lock
```

任务结束后释放：

```bash
termux-wake-unlock
```

同时可以在系统设置中允许 Termux 后台运行，并按需调整它的电池优化策略。各家 Android 系统的后台管理有所不同，可以结合任务时长和实际运行情况选择设置。

## 在电脑上显示手机中的 GUI 应用

SSH、文件访问和后台任务已经覆盖了服务器的常见命令行用途。Waypipe 则把手机上的 Wayland 窗口显示到电脑的 Wayland 桌面上，让 GUI 程序和手机的图形硬件也能加入这套使用方式。

### 安装与 Termux 配置

Waypipe 可以直接从 Termux 主仓库安装：

```bash
pkg install waypipe
```

`x11-repo` 则提供 Weston 和其他 GUI 软件。本文使用 Weston 进行演示，因此还需要：

```bash
pkg install x11-repo
pkg install weston
```

Linux 电脑安装 Waypipe 的命令如下，以 Arch Linux 为例：

```bash
sudo pacman -S waypipe
```

Termux 下的 SSH 会话默认可能没有 `XDG_RUNTIME_DIR`，而 Waypipe 需要用这个目录放置 Wayland display socket。可以在手机的 `$PREFIX/etc/ssh/sshd_config` 中加入：

```sshconfig
SetEnv XDG_RUNTIME_DIR=/data/data/com.termux/files/usr/tmp
```

这里写入与 `$PREFIX/tmp` 对应的绝对路径。修改后先检查配置：

```bash
sshd -t
```

然后重启 sshd，并建立新的 SSH 连接。

另一个 Termux 特有的问题是远端转发 socket 的位置。Waypipe 默认使用 `/tmp` 下的路径，而 Android 的 `/tmp` 通常不允许 Termux 用户写入。连接时应通过 `--remote-socket` 将路径前缀指定到 Termux 的可写目录：

```bash
waypipe \
    --remote-socket /data/data/com.termux/files/usr/tmp/waypipe \
    ssh -p 8022 <Termux用户名>@<手机地址> weston
```

`XDG_RUNTIME_DIR` 用于放置 Wayland display socket，`--remote-socket` 则指定 Waypipe 转发 socket 的路径前缀。

运行上述命令后，手机上启动的 Weston 会作为一个窗口显示在本地 Wayland 桌面上：

|[![#~/img/android/termux/weston-in-android-showing-with-kde.webp](/img/android/termux/weston-in-android-showing-with-kde.webp)](/img/android/termux/weston-in-android-showing-with-kde.webp)|
|:----:|
|手机 Termux 中运行的 Weston，通过 Waypipe 显示在 Linux KDE 桌面上|

在 Weston 中启动终端，可以看到其中运行的是手机上的 Termux 环境：

|[![#~/img/android/termux/weston-in-android.webp](/img/android/termux/weston-in-android.webp)](/img/android/termux/weston-in-android.webp)|
|:----:|
|Weston 终端中显示的 Termux、Clang 与设备信息|

Waypipe 的压缩、`--no-gpu` 等通用选项，可以参见笔者此前的[将远程 Wayland 应用窗口转发到本地](https://wszqkzqk.github.io/2025/10/13/GUI-With-Remote-Headless-Wayland-Linux/)。当前 Termux 版 Waypipe 的构建未包含 DMABUF、VAAPI 和视频流转码支持，本文使用的是它提供的常规 Wayland 转发能力。

### macOS 客户端

macOS 也可以通过 Waypipe 查看这些窗口。先运行 cocoa-way，由其提供本地 Wayland socket，再设置本地 `XDG_RUNTIME_DIR` 和 `WAYLAND_DISPLAY` 即可。笔者在 fish 中使用的命令如下：

```fish
set -l runtime "$TMPDIR/cocoa-way"
set -l display (basename (find "$runtime" -maxdepth 1 -type s -name 'wayland-*' -print | sort | head -n 1))
env XDG_RUNTIME_DIR="$runtime" WAYLAND_DISPLAY="$display" \
    waypipe --remote-socket /data/data/com.termux/files/usr/tmp/waypipe \
    ssh -p 8022 <Termux用户名>@<手机地址>
```

这里的两个环境变量服务于 **macOS 本地**的 Waypipe，前文 `sshd_config` 中的 `SetEnv` 则服务于手机端。

## 结语

Android 手机本身已经具备计算、存储、网络和图形硬件。Termux 将这些硬件接入 Linux 软件生态，SSH、sshfs 和 Waypipe 则让电脑能够方便地调用这些能力。这样，远程控制、文件访问、编译、转码、后台服务和 GUI 等任务都可以由同一台手机承担。

这套方案的吸引力在于，功能相当完整，成本和门槛却很低。对于已经有 Android 手机的人来说，只需完成这些配置，就能把它变成一台全功能的 ARM Linux 服务器。
