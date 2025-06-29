---
layout:     post
title:      在Linux下使用Wine运行ChemDraw/Chem3D
subtitle:   在Linux下无缝使用ChemOffice化学组件的复杂功能
date:       2025-06-29
author:     wszqkzqk
header-img: img/wine/wine-bg.webp
catalog:    true
tags:       Wine archlinux 系统配置 化学 有机化学
---

## 前言

ChemOffice是一个广泛使用的化学绘图和分子建模软件套件，包含ChemDraw和Chem3D等组件。然而，ChemOffice官方并不提供Linux版本，这使得Linux用户在使用这些工具时面临挑战。幸运的是，**Wine**可以帮助我们在Linux上运行ChemOffice组件，且**效果优良**，不仅可以使用ChemDraw进行化学结构绘制，还可以使用Chem3D进行分子建模、MM2力场优化与动态模拟计算等复杂功能。

## Linux环境准备

首先确保系统已安装Wine和Winetricks，此外，还需要安装解压所需的`7zip`，以Arch Linux为例：

```bash
sudo pacman -S --needed wine winetricks 7zip
```

笔者测试的Wine版本为10.9和10.11，Arch Linux的`extra/wine`包已经切换到WoW64模式，不再依赖任何32位库，但截至目前（2025.06.29），`winetricks`仍然在`multilib`仓库中（虽然它并不是32位程序，也并不依赖32位库），因此需要启用`multilib`仓库。

## 在Wine中安装ChemOffice

### 下载ChemOffice安装包

从ChemOffice官方网站或其他可信来源下载ChemOffice安装包。北京大学的同学可以从[北京大学正版软件平台](https://software.pku.edu.cn)下载[ChemDraw22.0 for Windows](https://software.pku.edu.cn/product.html?id=553)，对应的文件名应该是`cos22.2.0.exe`。

然而，这一安装程序实际上并不能直接在Wine中成功运行，我们需要使用别的方法来安装ChemOffice。

### 解压ChemOffice安装包

由于ChemOffice的安装程序无法直接在Wine中运行，我们需要先解压安装包。可以使用`7zip`来解压：

```bash
7z x cos22.2.0.exe -oChemOffice
```

这将会在当前目录下创建一个名为`ChemOffice`的目录，里面包含了ChemOffice的安装文件。观察解压后的目录结构：

```
ChemOffice/
├── _images
│   └── progress.gif
├── Install.exe
├── Install.ini
├── MSCOMCTL.OCX
├── PerkinElmer
│   ├── Activation
│   │   ├── Activate.exe
│   │   ├── activationhelp.html
│   │   ├── concrt140.dll
│   │   ├── FlxComm.dll
│   │   ├── FlxCore.dll
│   │   ├── FNEactivationhelp.html
│   │   ├── msvcp140_1.dll
│   │   ├── msvcp140_2.dll
│   │   ├── msvcp140_atomic_wait.dll
│   │   ├── msvcp140_codecvt_ids.dll
│   │   ├── msvcp140.dll
│   │   ├── registerproductemail.html
│   │   ├── registerproductfax.html
│   │   ├── registerproduct.html
│   │   ├── vccorlib140.dll
│   │   └── vcruntime140.dll
│   ├── ChemOffice
│   │   ├── PerkinElmer_ChemOffice_Suite_22.2.0.msi
│   │   └── PerkinElmer_ChemOffice_Suite_22.2.0_x64.msi
│   └── ChemOfficePlus
│       └── ChemOfficePlus.exe
├── QProGIF.ocx
├── RICHTX32.OCX
└── ThirdParty
    ├── Microsoft
    │   └── VCRedist
    │       ├── vcredist_x64.exe
    │       └── vcredist_x86.exe
    ├── NETInstaller
    │   └── ndp48-x86-x64-allos-enu.exe
    ├── Python
    │   ├── python-3.9.10-amd64.exe
    │   └── python-3.9.10.exe
    └── PythonExt
        ├── pywin32-303.win32-py3.9.exe
        └── pywin32-303.win-amd64-py3.9.exe

12 directories, 32 files
```

`PerkinElmer_ChemOffice_Suite_22.2.0.msi`和`PerkinElmer_ChemOffice_Suite_22.2.0_x64.msi`分别是ChemOffice的32位和64位安装包。由于Windows本身并没有Linux这样的软件包依赖管理系统，因此ChemOffice在自己的安装程序中集成了了所需的第三方组件和库，包括VC++运行时、.NET运行时等。

### 安装

由于官方的安装程序无法运行，我们需要**手动安装**这些依赖组件。我们可以选择使用`winetricks`一键安装，也可以手动从解压后的目录中安装。笔者在这里推荐使用`winetricks`来安装这些组件，因为它更加方便，能够避免手动安装的繁琐。运行命令：

```bash
winetricks vcrun2013 dotnet48 mfc140
```

其中前两个依赖是通用所需，`mfc140`是Chem3D所需的MFC库。运行之后，程序会弹出不同GUI安装程序的窗口，按照提示完成安装即可。[^1]

[^1]: 笔者在[之前的博客](https://wszqkzqk.github.io/2025/06/17/archlinux-wine-wow64-config/)中提到，Wine WoW64模式下一般需要安装`dxvk`和`vkd3d`来解决渲染性能问题，但似乎ChemOffice的组件并不需要，`dxvk`和`vkd3d`主要用于游戏和图形密集型应用，当然在这里安装也无妨。

随后，再运行ChemOffice的安装程序：

```bash
wine ChemOffice/PerkinElmer/ChemOffice/PerkinElmer_ChemOffice_Suite_22.2.0_x64.msi
```

如果你需要安装32位版本，可以运行：

```bash
wine ChemOffice/PerkinElmer/ChemOffice/PerkinElmer_ChemOffice_Suite_22.2.0.msi
```

一般按照默认的安装选项即可。安装完成后，ChemOffice的组件将被安装到Wine的虚拟C盘中，通常位于`~/.wine/drive_c/Program Files/PerkinElmer`（64位）或`~/.wine/drive_c/Program Files (x86)/PerkinElmer`（32位）。程序也会创建Linux的`.desktop`快捷方式，方便在应用菜单中找到。

### 使用ChemOffice

首次使用时会弹出激活窗口，北京大学的同学可以使用[学校提供的激活码](https://software.pku.edu.cn/product.html?id=553)进行激活。其他用户可以选择试用或联系PerkinElmer获取激活码。

激活完成后，你就可以在Linux上无缝使用ChemOffice的各个组件了。ChemDraw可以用于化学结构绘制，Chem3D可以用于分子建模和计算等。经过笔者的测试，无论是ChemDraw的结构绘制，还是Chem3D的分子建模、MM2力场优化与动态模拟计算等功能，都能在Wine中流畅运行，且效果良好。

笔者还在目前较新的Wine WoW64及实验性支持的原生Wayland下测试了ChemDraw和Chem3D，均能正常运行，且效果良好。

|[![#~/img/wine/chem/chemdraw.webp](/img/wine/chem/chemdraw.webp)](/img/wine/chem/chemdraw.webp)|
|:----:|
|ChemDraw运行效果展示（原生Wayland）|
|[![#~/img/wine/chem/chem3d-02.webp](/img/wine/chem/chem3d-02.webp)](/img/wine/chem/chem3d-02.webp)|
|Chem3D运行效果展示（原生Wayland）|
|[![#~/img/wine/chem/chem3d-03.webp](/img/wine/chem/chem3d-03.webp)](/img/wine/chem/chem3d-03.webp)|
|Chem3D运行效果展示（原生Wayland）|
