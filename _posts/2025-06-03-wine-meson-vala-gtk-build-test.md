---
layout:     post
title:      在Linux下跨平台构建与测试适用于Windows平台的GTK/Vala应用
subtitle:   在Wine环境中使用Meson/Vala构建GTK应用并进行测试
date:       2025-06-03
author:     wszqkzqk
header-img: img/GTK-logo.webp
catalog:    true
tags:       开源软件 MSYS2 Wine Meson Vala GTK
---

## 前言

大多数习惯写GTK或者Vala程序的人一般都倾向于使用Linux作为开发环境，但是为了验证程序的跨平台兼容性，我们通常还需要切换到Windows下进行编译和测试，反复重启切换系统会非常不便。因此，笔者探索了能够在Linux下通过Wine来构建与测试GTK/Vala应用的方法。

本文将从Windows下的GTK/Vala应用构建出发，讲解如何方便地安装Windows下GTK/Vala开发的相关环境，并通过配置Wine环境来在Linux下实现针对Windows平台的GTK/Vala应用的构建与测试。

## 安装Windows下的GTK/Vala开发环境

首先需要获取Windows下的开发环境，这个环节可能要处理很多依赖，在Windows下进行比较方便，可以在Windows下下载好后将环境复制或者挂载到Linux下使用。另外，在Windows下保有开发环境也是有必要的，因此本文先从Windows下的GTK/Vala开发环境安装讲起，再介绍如何在Linux下使用Wine来构建和测试。

**如果读者有更好的获取方式，可以使用自己的方式获取并跳过这一部分。**

### MSYS2简介

在Windows下，GTK和Vala的开发环境可以通过MSYS2来安装。MSYS2是一个轻量级包管理系统，提供了类似于Arch Linux的包管理体验。MSYS2继承了Arch Linux的哲学设计，提供了大量的开源软件包，无论是日用的GIMP、VLC、Inkscape，还是开发用的GCC、Clang、Python等，都可以通过MSYS2轻松安装。

MSYS2的核心优势在于其对**原生Windows应用**的支持。不同于在Windows平台上提供Linux环境的WSL（Windows Subsystem for Linux），以及侧重于在Windows上模拟Unix环境的Cygwin，MSYS2的`ucrt64`/`mingw64`/`clang64`等mingw-w64环境构建的软件包是**完全原生的Windows二进制文件**。这意味着通过MSYS2安装的GTK、GCC/Vala编译器、Meson等工具链，这些工具本身以及编译出的应用程序都是真正的Windows本地应用，不依赖于MSYS2环境本身（除了`libmsys-2.0.dll`对于`msys`环境中的Unix工具）。这使其成为在Windows上进行原生开源软件开发（如GTK/Vala应用）的理想选择。许多知名的开源项目，例如Git for Windows、Inkscape、GTKWave、KeePassXC、Xournal++、Neovim和darktable等，都利用MSYS2来构建其Windows版本。[^1]

[^1]: 参考 MSYS2 Wiki 中的[Who is using MSYS2?](https://www.msys2.org/docs/who-is-using-msys2/)一文。

### 安装MSYS2

MSYS2的安装非常简单，关于MSYS2的详细安装步骤、环境变量配置（如`MSYS2_PATH_TYPE=inherit`，`MINGW_ARCH=ucrt64`）以及与Windows终端的集成方法，请参考我之前的[博客文章](https://wszqkzqk.github.io/2022/06/24/在不借助oh-my-zsh的前提下进行Zsh配置/)。

### 安装软件包

在MSYS2中，GTK4/Libadwaita/Vala/Meson的开发环境可以通过以下命令安装：

```bash
pacman -S mingw-w64-ucrt-x86_64-gtk4 mingw-w64-ucrt-x86_64-libadwaita mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-vala mingw-w64-ucrt-x86_64-meson
```

当然，如果希望使用其他工具链（如`clang`）、其他图形库（如`Qt`）、其他构建系统（如`CMake`）等，也可以通过类似的方式安装相应的包。在选择要安装的包时，注意笔者之前的[提醒](https://wszqkzqk.github.io/2022/06/24/%E5%9C%A8%E4%B8%8D%E5%80%9F%E5%8A%A9oh-my-zsh%E7%9A%84%E5%89%8D%E6%8F%90%E4%B8%8B%E8%BF%9B%E8%A1%8CZsh%E9%85%8D%E7%BD%AE/#%E6%8F%90%E9%86%92%E9%81%BF%E5%85%8D%E5%8C%85%E5%86%B2%E7%AA%81)。


## Linux下Wine环境的配置

在Linux下，我们可以通过Wine来模拟Windows环境，从而在Linux上构建和测试Windows平台的GTK/Vala应用。Wine是一个开源的兼容层，可以让Linux用户运行Windows应用程序。

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

找到`Path`变量，如果有，则双击它并将MSYS2的`ucrt64/bin`以及`usr/bin`路径添加到最后：

```
C:\windows\system32;C:\windows;<MSYS2路径>\ucrt64\bin;<MSYS2路径>\usr\bin
```

其中，`<MSYS2路径>`可以使用`winepath`从Linux路径转换为Wine路径，例如：

```bash
winepath -w /mnt/msys64

# 输出为：'Z:\mnt\msys64'，将输出的路径替换到上面的'<MSYS2路径>'中即可
```

如果没有，则：
- 右键点击右侧窗格的空白区域
   - 选择 `新建` → `字符串值`
   - 将新值命名为 **`Path`**，添加默认路径和MSYS2的`ucrt64/bin`以及`usr/bin`路径：
     ```
     C:\windows\system32;C:\windows;<MSYS2路径>\ucrt64\bin;<MSYS2路径>\usr\bin
     ```

### 注意：防止环境变量干扰

很多时候（例如安装了flatpak的情况下），Linux下会设置`$XDG_DATA_DIRS`，这个变量在Linux下与Windows下**均会被GLib读取**，但是Linux使用`:`分隔符，而Windows使用`;`分隔符，因此在Linux下运行Wine时，如果Wine**继承**了`$XDG_DATA_DIRS`变量，可能会导致GLib等优先读取`$XDG_DATA_DIRS`的程序无法正确解析路径。

因此，我们需要确保Wine不会继承Linux下的`$XDG_DATA_DIRS`变量。如果没有必要使用`$XDG_DATA_DIRS`，可以清除该变量；如果需要使用，可以**在Wine中覆盖该变量**。同样使用`wine regedit`命令打开Wine的注册表编辑器，找到：

```
HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Session Manager\Environment
```

右键点击右侧窗格的空白区域
- 选择 `新建` → `字符串值`
- 将新值命名为 **`XDG_DATA_DIRS`**，添加默认路径和MSYS2的`ucrt64/share`路径：
  ```
  C:\ProgramData;C:\Program Files\Common Files;<MSYS2路径>\ucrt64\share
  ```

## 在Wine中构建

经过上述配置后，我们就可以在Linux下使用Wine来构建Windows平台的GTK/Vala应用了。由于相关路径已经添加到了Wine的环境变量中，我们可以直接在Linux终端中使用`wine <命令>`的方式来运行构建命令。

例如，配置Meson构建目录：

```bash
wine meson setup release --buildtype=release
```

使用Meson构建项目：

```bash
wine meson compile -C release
```

由于Wine对Python、Meson、Vala、GCC等工具的兼容性较好，因此在大多数情况下，这些命令可以直接在Wine环境中完成构建。

构建失败往往是文档等内容依赖了`msys`环境下的工具（如`help2man`）等，依赖`libmsys-2.0.dll`的这些非Windows原生工具暂时无法在Wine中运行，此时需要在构建选项中关闭文档等内容的生成，例如：

```bash
wine meson setup release --buildtype=release -Dmanpages=disabled -Ddocumentation=disabled
```

具体选项视待构建的上游项目而定。

## 在Wine中测试

由于我们已经将相关路径添加到Wine的环境变量中，因此可以直接在Wine环境中运行测试程序，无论是GUI应用还是命令行工具。对于受支持的DE，如果配置了XDG打开方式，也可以直接双击`.exe`文件来运行应用。

笔者构建的[GTK4/Vala示例应用](https://wszqkzqk.github.io/2025/02/05/GTK-Vala-Tutorial-2/)，无论是否基于Libadwaita，在Wine下构建、运行均相对顺利。

|[![#~/img/wine/wine-solarangleadw.webp](/img/wine/wine-solarangleadw.webp)](/img/wine/wine-solarangleadw.webp)|[![#~/img/wine/wine-solarangleadw-black.webp](/img/wine/wine-solarangleadw-black.webp)](/img/wine/wine-solarangleadw-black.webp)|
|:----:|:----:|
|基于Libadwaita的GTK4程序|基于Libadwaita的GTK4程序(深色模式)|

|[![#~/img/wine/wine-daylengthgtk.webp](/img/wine/wine-daylengthgtk.webp)](/img/wine/wine-daylengthgtk.webp)|[![#~/img/wine/wine-solaranglegtk.webp](/img/wine/wine-solaranglegtk.webp)](/img/wine/wine-solaranglegtk.webp)|
|:----:|:----:|
|纯GTK4程序(1)|纯GTK4程序(2)|
