---
layout:     post
title:      在Linux下使用Wine构建与测试Windows应用
subtitle:   在Wine环境中使用Meson/Vala构建GTK应用并进行测试
date:       2025-06-03
author:     wszqkzqk
header-img: img/GTK-logo.webp
catalog:    true
tags:       开源软件 MSYS2 Wine Meson Vala GTK
---

## 前言

许多开发者倾向于使用Linux作为主力开发环境，但在开发需要支持Windows平台的应用程序时，为了验证程序的跨平台兼容性，通常还需要切换到Windows下进行编译和测试，**反复重启切换系统会非常不便**。本文将介绍一种通用方法，通过配置**Wine**环境，在Linux下实现针对Windows平台的各类应用的**构建**与**测试**。本文方法实际上不仅仅局限于特定的工具链与语言，也可以用于其他需要在Windows平台上构建的应用程序。通过这种方式，开发者可以在Linux环境下高效地完成Windows平台的构建与初步验证，甚至可以将Linux和Windows的构建集成到同一个工作流。

相比于开销较大的虚拟机等方式，Wine通过**API转换层**（Windows Syscall → Linux Syscall）直接执行原生x86指令，不涉及虚拟化或指令集模拟。Wine具有更短的系统调用路径、更低的上下文切换开销，还可以通过宿主调度器及文件系统直接管理资源，CPU、内存、硬盘IO的开销也明显更小。

通过Wine运行的纯CPU、无硬件加速的程序的性能大致与在Windows下运行的性能相当，甚至有时会更好（Wine对某些系统调用及内置函数的优化可能更好）。因此，Wine是一个非常适合在Linux下进行Windows平台应用开发和测试的工具。

为了具体说明这一流程，本文将以Windows下的GTK/Vala应用构建为例，讲解如何配置Wine环境来在Linux下实现其构建与测试。通过这种方式，开发者可以在Linux环境下高效地完成Windows平台的**构建、分发与初步验证**。

## 安装Windows下的GTK/Vala开发环境

首先需要获取Windows下的开发环境，这个环节可能要处理很多依赖，在Windows下进行比较方便，可以在Windows下下载好后将环境复制或者挂载到Linux下使用。另外，在Windows下保有开发环境也是有必要的，因此本文先从Windows下的GTK/Vala开发环境安装讲起，再介绍如何在Linux下使用Wine来构建和测试。

**如果读者有更好的获取方式，可以使用自己的方式获取并跳过这一部分。**

### MSYS2简介

在Windows下，GTK和Vala的开发环境可以通过MSYS2来安装。MSYS2是一个轻量级包管理系统，提供了类似于Arch Linux的包管理体验。MSYS2继承了Arch Linux的哲学设计，提供了大量的开源软件包，无论是日用的GIMP、VLC、Inkscape，还是开发用的GCC、Clang、Python等，都可以通过MSYS2轻松安装。

MSYS2的核心优势在于其对**原生Windows应用**的支持。不同于在Windows平台上提供Linux环境的WSL（Windows Subsystem for Linux），以及侧重于在Windows上模拟Unix环境的Cygwin，MSYS2的`ucrt64`/`mingw64`/`clang64`等mingw-w64环境构建的软件包是**完全原生的Windows二进制文件**。

这意味着通过MSYS2安装的GTK、GCC/Vala编译器、Meson等工具链，这些工具本身以及编译出的应用程序都是真正的Windows本地应用，不依赖于MSYS2环境本身（除了`msys`环境中的基础Unix兼容工具依赖于`msys-2.0.dll`进行syscall映射）。这使其成为在Windows上进行原生开源软件开发（如GTK/Vala应用）的理想选择。许多知名的开源项目，例如Git for Windows、Inkscape、GTKWave、KeePassXC、Xournal++、Neovim和darktable等，都利用MSYS2来构建其Windows版本。[^1]

[^1]: 参考 MSYS2 Wiki 中的[“Who is using MSYS2?”](https://www.msys2.org/docs/who-is-using-msys2/)一文。

### 安装MSYS2

MSYS2的安装非常简单，从[官网](https://www.msys2.org/)下载即可一键安装。如果需要在Windows下对MSYS2进行更好的集成，可参考我之前的[博客文章](https://wszqkzqk.github.io/2022/06/24/在不借助oh-my-zsh的前提下进行Zsh配置/)。当然，如果只是用于下载和安装GTK/Vala开发环境，默认安装完成后直接使用亦可。（推荐使用`ucrt64`环境）

### 安装软件包

在MSYS2中，GTK4/Libadwaita/Vala/Meson的开发环境可以通过以下命令安装：

```bash
pacman -S mingw-w64-ucrt-x86_64-gtk4 mingw-w64-ucrt-x86_64-libadwaita mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-vala mingw-w64-ucrt-x86_64-meson
```

如果希望使用其他工具链（如`clang`、`rust`）、其他基础库（如`Qt`）、其他构建系统（如`CMake`）等，也可以通过类似的方式安装相应的包。

## Linux下Wine环境的配置

在Linux下，我们可以通过Wine来提供Windows兼容环境，从而在Linux上构建和测试Windows平台的GTK/Vala应用。Wine是一个开源的兼容层，可以让Linux用户运行Windows应用程序。

### 安装Wine

在大多数Linux发行版中，Wine可以通过包管理器直接安装。在Arch Linux中，可以使用以下命令安装Wine：

```bash
sudo pacman -S wine
```

### 在Wine中配置路径

将Windows下的GTK/Vala开发环境（如MSYS2下的`ucrt64`目录）复制或者挂载到Linux下，并在Wine中配置相应的路径。

在Linux的终端中运行`wine regedit`命令打开Wine的注册表编辑器，找到：

```
HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Session Manager\Environment
```

找到`Path`变量，如果有，则双击它并将MSYS2的`ucrt64/bin`路径添加到最后：

```
C:\windows\system32;C:\windows;<MSYS2路径>\ucrt64\bin
```

其中，具体路径可以使用`winepath`**从Linux路径转换为Wine路径**，例如：

```bash
winepath -w /mnt/msys64/ucrt64/bin

# 输出为：'Z:\mnt\msys64\ucrt64\bin\'
```

如果没有，则右键点击右侧窗格的空白区域
- 选择 `新建` → `字符串值`
- 将新值命名为 **`Path`**，添加默认路径和MSYS2的`ucrt64/bin`路径：
  ```
  C:\windows\system32;C:\windows;<MSYS2路径>\ucrt64\bin
  ```

需要注意的是，由于Wine目前尚**不能**兼容**依赖`msys-2.0.dll`**的**非Windows原生**的工具，因此**不应该**添加MSYS2的`usr/bin`路径到Wine的`Path`中。

### 防止环境变量干扰

很多时候（例如安装了flatpak的情况下），Linux下会设置`$XDG_DATA_DIRS`等XDG相关的环境变量，这些变量在Linux下与Windows下**均会被GLib读取**，但是Linux使用`:`分隔符，而Windows使用`;`分隔符。在Linux下运行Wine时，如果Wine**继承**了`$XDG_DATA_DIRS`等变量，GLib等库中的实现会按照Windows的规则来处理，但实际上接受到的却是Linux的风格，程序将无法按照正确的分隔符拆分，导致程序无法正确解析系统数据路径。

因此，我们需要确保Wine不会继承Linux下的`$XDG_DATA_DIRS`等变量。如果没有必要使用这些环境变量，可以清除这些变量设置；如果需要使用，可以**在Wine中覆盖该变量**。同样使用`wine regedit`命令打开Wine的注册表编辑器，找到：

```
HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Session Manager\Environment
```

右键点击右侧窗格的空白区域：
- 选择 `新建` → `字符串值`
- 将新值命名为 **`XDG_DATA_DIRS`**，添加默认路径和MSYS2的`ucrt64/share`路径：
  ```
  C:\ProgramData;C:\users\Public\Documents;<MSYS2路径>\ucrt64\share
  ```

对于其他的环境变量（如`XDG_CONFIG_DIRS`、`XDG_CACHE_HOME`等），可以使用类似的方式进行配置。

## 在Wine中构建

经过上述配置后，我们就可以在Linux下使用Wine来构建Windows平台的GTK/Vala应用了。由于相关路径已经添加到了Wine的环境变量中，我们可以直接在Linux终端中使用`wine <命令>`的方式来运行构建命令。这几乎只是在Linux的对应命令前加上一个`wine`，十分方便。

例如，配置Meson构建目录：

```bash
wine meson setup release --buildtype=release
```

使用Meson构建项目：

```bash
wine meson compile -C release
```

由于Wine对Python、Meson、Vala、GCC等工具的兼容性较好，在大多数情况下，使用这些命令可以直接在Wine环境中完成构建。

### `msys`环境的依赖解决

#### 禁用文档生成（推荐）

很多构建失败往往是文档等内容依赖了`msys`环境下的工具（如`help2man`）等。因为Wine目前无法运行依赖`msys-2.0.dll`的程序，我们并没有将`msys`环境的路径添加到Wine中，因此会找不到对应的程序而报错。此时可以通过关闭相关文档生成选项来解决。

```bash
wine meson setup release --buildtype=release -Dmanpages=disabled -Ddocumentation=disabled
```

具体选项视待构建的上游项目而定。

#### 使用Linux原生工具代替（有风险）

由于`msys`中的工具都是POSIX下常用工具的移植版本，因此在Linux下也可以找到类似的工具来代替。比如`help2man`可以使用Linux下的`help2man`命令来代替，或者直接使用`pandoc`等工具来生成文档。可以在构建的时候临时将Linux的`/usr/bin`路径添加到Wine的`Path`的末尾。

不过这样做可能存在潜在风险，可能会导致某些工具的行为与预期不符，因此需要谨慎使用。

## 在Wine中测试

由于我们已经将相关路径添加到Wine的环境变量中，因此可以直接在Wine环境中运行测试程序，无论是GUI应用还是命令行工具。对于受支持的DE，如果配置了XDG打开方式，也可以直接双击`.exe`文件来运行应用。

笔者编写的[GTK4/Vala示例应用](https://wszqkzqk.github.io/2025/02/05/GTK-Vala-Tutorial-2/)，无论是否基于Libadwaita，在Wine下构建均较为顺利。但在测试运行的时候，显示与渲染上效果相对欠佳，基于Libadwaita的应用存在较大的黑边，纯GTK4应用也有较小的黑边，两者在某些时候偶尔有闪烁现象，但整体上仍然可以正常运行和操作。

|[![#~/img/wine/wine-solarangleadw.webp](/img/wine/wine-solarangleadw.webp)](/img/wine/wine-solarangleadw.webp)|[![#~/img/wine/wine-solarangleadw-black.webp](/img/wine/wine-solarangleadw-black.webp)](/img/wine/wine-solarangleadw-black.webp)|
|:----:|:----:|
|基于Libadwaita的GTK4程序|基于Libadwaita的GTK4程序(深色模式)|

|[![#~/img/wine/wine-daylengthgtk.webp](/img/wine/wine-daylengthgtk.webp)](/img/wine/wine-daylengthgtk.webp)|[![#~/img/wine/wine-solaranglegtk.webp](/img/wine/wine-solaranglegtk.webp)](/img/wine/wine-solaranglegtk.webp)|
|:----:|:----:|
|纯GTK4程序(1)|纯GTK4程序(2)|

同样，非GUI的程序也可以这样构建与运行。笔者也测试了在Wine中构建出的这些程序在Windows下的运行情况，普遍较GUI的好，但是同样可能存在一些问题。以下是一些典型问题：

* 在Linux下和较新Windows下可以通过**ANSI转义序列**直接控制终端输出颜色的程序，目前Wine则会将ANSI转义序列直接输出到终端，这是Wine中存在已久的已知问题。

  |[![#~/img/wine/wine-live-photo-conv.webp](/img/wine/wine-live-photo-conv.webp)](/img/wine/wine-live-photo-conv.webp)|
  |:----:|
  |默认情况下控制序列直接被输出（上），关闭颜色输出后则不再显示（下）|

* 非ASCII字符在GLib的`-h`/`--help`等帮助信息中无法正常输出，从第一个非ASCII字符开始输出被截断。其他输出一般正常。（甚至在其他地方打印的与`--help`一样的帮助信息也正常）但是同样都有可能因为**非ASCII字符**而导致输出被**截断**，在测试过程中应当尽量**避免使用非ASCII字符**。

  |[![#~/img/wine/wine-live-photo-conv-help.webp](/img/wine/wine-live-photo-conv-help.webp)](/img/wine/wine-live-photo-conv-help.webp)|
  |:----:|
  |`-h`输出分别因为中文（上）和非ASCII的`…`（中）而被截断，而非`-h`情况即使包含同样内容（下）也能正常输出|

* **GStreamer的硬件加速解码**不可用（但依赖CPU运算的基础功能在Wine下都能正常运行）。

  |[![#~/img/wine/wine-live-photo-conv-gst.webp](/img/wine/wine-live-photo-conv-gst.webp)](/img/wine/wine-live-photo-conv-gst.webp)|
  |:----:|
  |在Wine下运行的[Live Photo转换程序](https://github.com/wszqkzqk/live-photo-conv)，纯CPU完成的图片视频导出及元数据修改完全正常，但D3D硬件加速的逐帧导出解码在Gstreamer中卡住|

  这一问题可以**使用FFmpeg代替**来解决。笔者的[Live Photo转换程序](https://github.com/wszqkzqk/live-photo-conv)也提供了FFmpeg后端，可以直接通过`--use-ffmpeg`使用，运行**完全正常**。

  |[![#~/img/wine/wine-live-photo-conv-ffmpeg.webp](/img/wine/wine-live-photo-conv-ffmpeg.webp)](/img/wine/wine-live-photo-conv-ffmpeg.webp)|
  |:----:|
  |使用FFmpeg后端的Live Photo转换程序，能够正常逐帧导出|

一般来说，Wine对GCC、Meson等**基础构建工具**的支持**相当好**，对非GUI的程序的支持一般也很不错。但是Wine对非常复杂的Win32 API调用（甚至像`msys-2.0.dll`这样的Hack）的支持可能并不理想。

由于基于GLib的程序一般都有原生Linux版本且往往表现比Windows版更好，因此Wine下GLib程序的某些**高度依赖于平台**的行为适配可能不太合适，需要开发者自行处理相关环境。

另外，由于图形界面渲染适配难度较大，**复杂GUI程序**的**兼容性风险**往往相对更大。在笔者的示例中，几个**GTK4**/Vala应用（包括纯GTK4与基于Libadwaita的GTK4应用）在Wine下的运行效果都**尚可接受**，虽然有些小问题，但基本上可以使用。

## 总结

本文详细介绍了一种在Linux环境下通过Wine实现跨平台构建与测试Windows平台应用的通用方法，并以GTK/Vala应用为例展示了其具体实现。这种方法使开发者能够在仅使用Linux开发环境的情况下，高效验证各类应用在Windows平台的兼容性。

该方法能够显著简化需要支持Windows平台的应用的开发流程，使开发者能够在Linux环境下高效完成Windows平台的构建与初步验证，甚至可以将Linux和Windows的构建集成到同一个工作流。随着Wine和MSYS2等工具的持续改进，该工作流将更加完善，为各类应用的跨平台开发提供有力支持。
