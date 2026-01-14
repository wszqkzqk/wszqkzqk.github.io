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

笔者测试的Wine版本为10.9和10.11，Arch Linux的`extra/wine`包已经切换到WoW64模式，不再依赖任何32位库，~~但截至目前（2025.06.29），`winetricks`仍然在`multilib`仓库中（虽然它并不是32位程序，也并不依赖32位库），因此需要启用`multilib`仓库~~。目前（2026.01.14），Arch Linux的`winetricks`已经移动到了`extra`仓库中，不再需要启用`multilib`仓库。

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

其中前两个依赖是通用所需，`mfc140`是Chem3D所需的MFC库。运行之后，程序会弹出不同GUI安装程序的窗口，按照提示完成安装即可。[^1]注意这里的`dotnet48`不可以用`wine-mono`替代。

[^1]: 笔者在[之前的博客](https://wszqkzqk.github.io/2025/06/17/archlinux-wine-wow64-config/)中提到，在较早期的Wine中，Wine WoW64模式下一般需要安装`dxvk`和`vkd3d`来解决渲染性能问题，但似乎ChemOffice的组件并不需要，`dxvk`和`vkd3d`主要用于游戏和图形密集型应用，当然在这里安装也无妨。

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

## 已知问题

ChemDraw的Templates（模板）功能在Wine中无法使用，点击后程序会崩溃退出。其他功能未发现明显问题。

如果在ChemDraw中点击Main Toolbar中的Templates按钮，会因形如这样的错误而崩溃退出：

```
Unhandled exception: page fault on read access to 0x0000000000000038 in 64-bit code (0x000001804fba91).
Register dump:
 rip:00000001804fba91 rsp:000000000051ef10 rbp:000000000051f010 eflags:00010206 (  R- --  I   - -P- )
 rax:0000000000000037 rbx:000000000000ffce rcx:0000000000000000 rdx:0000000000000000
 rsi:0000000022d05200 rdi:0000000022d05540  r8:0000000000000000  r9:0000000000000000 r10:0000000000000000
 r11:0000000000000202 r12:00000000225b97f0 r13:0000000000000443 r14:0000000022d05200 r15:000000002263b5d0
Stack dump:
0x0000000051ef10:  0000000022d05540 000000000051f010
0x0000000051ef20:  0000000022d05200 0000000000000001
0x0000000051ef30:  0000000000370037 0000000000000000
0x0000000051ef40:  0000000000000000 0000000000000000
0x0000000051ef50:  0000000000000000 0000014a000001b8
0x0000000051ef60:  0000000180875bf8 01dc852ba28008a0
0x0000000051ef70:  0000000000000000 0000000000000000
0x0000000051ef80:  0000000180866628 0000000000000000
0x0000000051ef90:  0000000000000000 0000100000000012
0x0000000051efa0:  000b1f7200000012 0000000000000000
0x0000000051efb0:  0000000000000000 000000002313f390
0x0000000051efc0:  00000000225b97f0 0000000000000014
Backtrace:
=>0 0x000001804fba91 in chemdrawbase (+0x4fba91) (0x0000000051f010)
  1 0x0000018047c62c in chemdrawbase (+0x47c62c) (0x0000000051f1d9)
  2 0x0000018061113e in chemdrawbase (+0x61113e) (0x0000000051f1d9)
  3 0x0000018042afaa in chemdrawbase (+0x42afaa) (0x0000000051f340)
  4 0x0000018051d787 in chemdrawbase (+0x51d787) (0x000000231022d0)
  5 0x00000180520e6c in chemdrawbase (+0x520e6c) (0x00000000010284)
  6 0x006ffffdaabd7e in user32 (+0x5bd7e) (0x00000000000201)
  7 0x006ffffdab1ca4 in user32 (+0x61ca4) (0x0000000051fa90)
  8 0x006ffffdab1ac1 in user32 (+0x61ac1) (0x0000000051fa90)
  9 0x006ffffda6ef8c in user32 (+0x1ef8c) (0x0000000051fa90)
  10 0x000001806240d6 in chemdrawbase (+0x6240d6) (0x0000000051fa90)
  11 0x006ffff7d20922 in chemdrawui (+0x220922) (0x0000000051fa90)
  12 0x006ffff7d1d96f in chemdrawui (+0x21d96f) (0000000000000000)
  13 0x00000140008041 in chemdraw (+0x8041) (0000000000000000)
  14 0x000001400098a2 in chemdraw (+0x98a2) (0000000000000000)
  15 0x006fffffa11469 in kernel32 (+0x11469) (0000000000000000)
  16 0x006fffffbf0d2b in ntdll (+0x10d2b) (0000000000000000)
0x000001804fba91 chemdrawbase+0x4fba91: movl 0x38(%rcx), %eax
Modules:
Module  Address                                 Debug info      Name (149 modules, 1 for wow64 not listed)
PE             100000000-       100fde000       Deferred        chemdrawbase
PE             140000000-       140436000       --none--        chemdraw
PE             180000000-       180fde000       --none--        chemdrawbase
PE           644406e0000-     64440813000       Deferred        system.configuration.ni
PE           64443400000-     64443e75000       Deferred        system.core.ni
PE           644442c0000-     64444b6b000       Deferred        system.xml.ni
PE           64474a80000-     644756f0000       Deferred        system.ni
PE           64475d40000-     64475f34000       Deferred        system.drawing.ni
PE           644760a0000-     64477145000       Deferred        system.windows.forms.ni
PE           64478000000-     644795e5000       Deferred        mscorlib.ni
PE-Wine     6ffff5270000-    6ffff530f000       Deferred        mlang
PE          6ffff5320000-    6ffff58ec000       Deferred        mfc140
PE-Wine     6ffff5900000-    6ffff5937000       Deferred        compstui
PE-Wine     6ffff5950000-    6ffff5a1c000       Deferred        winspool
PE-Wine     6ffff5a30000-    6ffff5a4b000       Deferred        atlthunk
PE-Wine     6ffff5a60000-    6ffff5a86000       Deferred        schannel
PE-Wine     6ffff5aa0000-    6ffff5ac1000       Deferred        netutils
PE-Wine     6ffff5ae0000-    6ffff5b81000       Deferred        netapi32
PE-Wine     6ffff5ba0000-    6ffff5bf1000       Deferred        msv1_0
PE-Wine     6ffff5c10000-    6ffff5c47000       Deferred        kerberos
PE-Wine     6ffff5c60000-    6ffff5d1c000       Deferred        secur32
PE-Wine     6ffff5d30000-    6ffff5d82000       Deferred        cryptnet
PE-Wine     6ffff5da0000-    6ffff5f09000       Deferred        rsaenh
PE-Wine     6ffff5f20000-    6ffff5f67000       Deferred        imagehlp
PE-Wine     6ffff5f80000-    6ffff5f93000       Deferred        psapi
PE-Wine     6ffff5fb0000-    6ffff6382000       Deferred        crypt32
PE-Wine     6ffff63a0000-    6ffff646d000       Deferred        wintrust
PE          6ffff6480000-    6ffff6ea2000       Deferred        flxcore64
PE          6ffff6ec0000-    6ffff700e000       Deferred        clrjit
PE          6ffff7020000-    6ffff7ae7000       Deferred        clr
PE          6ffff7b00000-    6ffff7f77000       --none--        chemdrawui
PE-Wine     6ffff7f90000-    6ffff878b000       Deferred        windowscodecs
PE-Wine     6ffff87a0000-    6ffff8a8a000       Deferred        gdiplus
PE-Wine     6ffff8aa0000-    6ffff9052000       Deferred        comctl32
PE-Wine     6ffff9070000-    6ffff9455000       Deferred        msvcp140
PE          6ffff9470000-    6ffffa1f1000       Deferred        pkicorechemistry
PE-Wine     6ffffa210000-    6ffffa231000       Deferred        winewayland
PE-Wine     6ffffa270000-    6ffffa315000       Deferred        concrt140
PE-Wine     6ffffa330000-    6ffffa39b000       Deferred        oledlg
PE-Wine     6ffffa3b0000-    6ffffa3ec000       Deferred        vcruntime140_1
PE-Wine     6ffffa400000-    6ffffa41c000       Deferred        vcruntime140
PE-Wine     6ffffa650000-    6ffffa677000       Deferred        nsi
PE-Wine     6ffffa690000-    6ffffa6e2000       Deferred        dnsapi
PE-Wine     6ffffa700000-    6ffffa7a7000       Deferred        iphlpapi
PE-Wine     6ffffa840000-    6ffffa910000       Deferred        actxprxy
PE-Wine     6ffffa920000-    6ffffa9f1000       Deferred        uxtheme
PE-Wine     6ffffad30000-    6ffffad53000       Deferred        version
PE          6ffffad70000-    6ffffad86000       Deferred        boost_thread-vc142-mt-x64-1_75
PE          6ffffada0000-    6ffffae49000       Deferred        mscoreei
PE-Wine     6ffffb220000-    6ffffb2aa000       Deferred        bcrypt
PE-Wine     6ffffb3d0000-    6ffffb455000       Deferred        imm32
PE          6ffffb470000-    6ffffb4df000       Deferred        mscoree
PE          6ffffb4f0000-    6ffffb5ad000       Deferred        ucrtbase_clr0400
PE          6ffffb5c0000-    6ffffb5d6000       Deferred        vcruntime140_clr0400
PE-Wine     6ffffb6a0000-    6ffffb73c000       Deferred        propsys
PE-Wine     6ffffb8b0000-    6ffffbc2f000       Deferred        oleaut32
PE-Wine     6ffffbc60000-    6ffffbc84000       Deferred        dhcpcsvc
PE-Wine     6ffffbca0000-    6ffffbcba000       Deferred        msimg32
PE          6ffffbcd0000-    6ffffbea4000       Deferred        lib3mf
PE          6ffffbec0000-    6ffffbefc000       Deferred        pki3dformats
PE-Wine     6ffffbf10000-    6ffffbf7a000       Deferred        mpr
PE-Wine     6ffffbf90000-    6ffffc1cb000       Deferred        wininet
PE-Wine     6ffffc1e0000-    6ffffc434000       Deferred        comdlg32
PE-Wine     6ffffc450000-    6ffffc4a5000       Deferred        shcore
PE-Wine     6ffffc4c0000-    6ffffc5e1000       Deferred        shlwapi
PE-Wine     6ffffc600000-    6ffffd3d8000       Deferred        shell32
PE-Wine     6ffffd3f0000-    6ffffd44d000       Deferred        coml2
PE-Wine     6ffffd4b0000-    6ffffd4fe000       Deferred        win32u
PE-Wine     6ffffd740000-    6ffffd768000       Deferred        cryptbase
PE-Wine     6ffffd780000-    6ffffda34000       Deferred        rpcrt4
PE-Wine     6ffffda50000-    6ffffe05b000       COFF            user32
PE-Wine     6ffffe070000-    6ffffe31d000       Deferred        gdi32
PE-Wine     6ffffe330000-    6ffffe4e0000       Deferred        combase
PE-Wine     6ffffe4f0000-    6ffffe8d6000       Deferred        ole32
PE-Wine     6ffffe8f0000-    6ffffe9a4000       Deferred        ws2_32
PE-Wine     6ffffe9c0000-    6ffffedf8000       Deferred        ucrtbase
PE-Wine     6ffffee10000-    6ffffee9f000       Deferred        sechost
PE-Wine     6ffffeeb0000-    6fffff248000       Deferred        msvcrt
PE-Wine     6fffff260000-    6fffff382000       Deferred        advapi32
PE-Wine     6fffff3a0000-    6fffff9e2000       Deferred        kernelbase
PE-Wine     6fffffa00000-    6fffffbcd000       COFF            kernel32
PE-Wine     6fffffbe0000-    6ffffffe5000       COFF            ntdll
ELF         7f72fe026000-    7f72fe14d000       Deferred        libsystemd.so.0
ELF         7f72fe14d000-    7f72fe1a0000       Deferred        libdbus-1.so.3
ELF         7f72fe1a0000-    7f72fe231000       Deferred        libcups.so.2
ELF         7f72ff4ba000-    7f72ff50d000       Deferred        libgssapi_krb5.so.2
ELF         7f72ff50d000-    7f72ff53a000       Deferred        libk5crypto.so.3
ELF         7f72ff53a000-    7f72ff600000       Deferred        libkrb5.so.3
ELF         7f72ff600000-    7f7301595000       Deferred        libicudata.so.78
ELF         7f730159b000-    7f73015cb000       Deferred        libnss_myhostname.so.2
ELF         7f73015cb000-    7f7301600000       Deferred        libnss_resolve.so.2
ELF         7f7301600000-    7f730180e000       Deferred        libicuuc.so.78
ELF         7f7301812000-    7f7301825000       Deferred        libavahi-client.so.3
ELF         7f7301825000-    7f730182c000       Deferred        libkeyutils.so.1
ELF         7f730182c000-    7f7301889000       Deferred        libnss_mymachines.so.2
ELF         7f7301896000-    7f73018a5000       Deferred        libavahi-common.so.3
ELF         7f73018a5000-    7f73018ab000       Deferred        winspool.so
ELF         7f73018ab000-    7f73018b0000       Deferred        msv1_0.so
ELF         7f73018b0000-    7f73018b7000       Deferred        netapi32.so
ELF         7f73019b7000-    7f7301aec000       Deferred        libxml2.so.16
ELF         7f7301aec000-    7f7301b49000       Deferred        libxkbcommon.so.0
ELF         7f7301b4a000-    7f7301b58000       Deferred        libkrb5support.so.0
ELF         7f7301b58000-    7f7301b5e000       Deferred        libcom_err.so.2
ELF         7f7301b5e000-    7f7301b67000       Deferred        kerberos.so
ELF         7f7301b67000-    7f7301b71000       Deferred        secur32.so
ELF         7f7301b71000-    7f7301b77000       Deferred        crypt32.so
ELF         7f7301b77000-    7f7301c1d000       Deferred        libgmp.so.10
ELF         7f7301c1d000-    7f7301e00000       Deferred        libunistring.so.5
ELF         7f7301e00000-    7f730204c000       Deferred        libleancrypto.so.1
ELF         7f7302074000-    7f730209a000       Deferred        winewayland.so
ELF         7f730209a000-    7f7302200000       Deferred        libp11-kit.so.0
ELF         7f7302200000-    7f730240c000       Deferred        libgnutls.so.30
ELF         7f730241f000-    7f730242a000       Deferred        libxkbregistry.so.0
ELF         7f730242a000-    7f7302436000       Deferred        libffi.so.8
ELF         7f7302436000-    7f7302490000       Deferred        libnettle.so.8
ELF         7f7302490000-    7f73024db000       Deferred        libhogweed.so.6
ELF         7f73024db000-    7f73024f1000       Deferred        libtasn1.so.6
ELF         7f73024f1000-    7f7302513000       Deferred        libidn2.so.0
ELF         7f7302513000-    7f7302518000       Deferred        libwayland-egl.so.1
ELF         7f7302518000-    7f7302528000       Deferred        libwayland-client.so.0
ELF         7f7302528000-    7f730253b000       Deferred        libresolv.so.2
ELF         7f730253b000-    7f7302541000       Deferred        ws2_32.so
ELF         7f7302541000-    7f730254e000       Deferred        bcrypt.so
ELF         7f73026ab000-    7f73026d6000       Deferred        libexpat.so.1
ELF         7f73026d6000-    7f7302727000       Deferred        libfontconfig.so.1
ELF         7f7302727000-    7f73027d5000       Deferred        libpcre2-8.so.0
ELF         7f73027d5000-    7f73027f8000       Deferred        libgraphite2.so.3
ELF         7f73027f8000-    7f7302950000       Deferred        libglib-2.0.so.0
ELF         7f7302950000-    7f7302a85000       Deferred        libharfbuzz.so.0
ELF         7f7302a85000-    7f7302aa8000       Deferred        libbrotlicommon.so.1
ELF         7f7302aa8000-    7f7302ab7000       Deferred        libbrotlidec.so.1
ELF         7f7302ab7000-    7f7302af2000       Deferred        libpng16.so.16
ELF         7f7302af2000-    7f7302c00000       Deferred        libm.so.6
ELF         7f7302c00000-    7f7302e1d000       Deferred        win32u.so
ELF         7f7302e1d000-    7f7302e30000       Deferred        libbz2.so.1.0
ELF         7f7302e30000-    7f7302f00000       Deferred        libfreetype.so.6
ELF         7f73037f5000-    7f730380e000       Deferred        libz.so.1
ELF         7f730380e000-    7f730383b000       Deferred        libgcc_s.so.1
ELF         7f730393b000-    7f7303a00000       Export          ntdll.so
ELF         7f7303a00000-    7f7303c12000       Deferred        libc.so.6
ELF         7f7303c12000-    7f7303c17000       Deferred        dnsapi.so
ELF         7f7303c1d000-    7f7303c52000       Deferred        liblzma.so.5
ELF         7f7303c52000-    7f7303c6d000       Deferred        libunwind.so.8
ELF         7f7303ca0000-    7f7303cdd000       Deferred        ld-linux-x86-64.so.2
ELF         7f7303cdd000-    7f7303ce2000       Deferred        <wine-loader>
PE          7ffffe300000-    7ffffe37a000       Deferred        chemdrawmanaged
PE          7ffffe600000-    7ffffe67a000       Deferred        chemdrawmanaged
PE          7ffffeb80000-    7ffffed4e000       Deferred        online
PE          7fffff020000-    7fffff1ee000       Deferred        online
Threads:
process  tid      prio    name (all IDs are in hex)
00000020 (D) C:\Program Files\PerkinElmerInformatics\ChemOffice\ChemDraw\ChemDraw.exe
	00000024    0 <== 
	0000017c    0     
	00000180    0     
	00000184    0     
	00000188    2     
	000001b0    0     wine_rpcrt4_server
	000001c0    0     
	000001c8    0     wine_wininet_collect_connections
	000001e4    0     
00000038 services.exe
	0000003c    0     
	00000040    0     wine_rpcrt4_server
	0000004c    0     wine_rpcrt4_io
	00000070    0     wine_rpcrt4_io
	0000008c    0     wine_rpcrt4_io
	000000b4    0     wine_rpcrt4_io
	000000e0    0     wine_rpcrt4_io
	000000f0    0     wine_rpcrt4_io
	00000114    0     wine_rpcrt4_io
	00000148    0     
	00000154    0     wine_rpcrt4_io
	000001ac    0     wine_rpcrt4_io
00000044 winedevice.exe
	00000048    0     
	00000054    0     
	00000058    0     wine_sechost_service
	0000005c    0     
	00000060    0     
	00000064    0     
	00000108    0     wine_nsi_notification
00000068 svchost.exe
	0000006c    0     
	00000074    0     
	00000078    0     wine_sechost_service
0000007c mscorsvw.exe
	00000080    0     
	00000090    0     
	00000094    0     wine_sechost_service
	00000098    0     
00000084 explorer.exe
	00000088    0     
	000000a4    0     
	000000a8    0     
	000000d8    0     wine_explorer_display_settings_restorer
	000000dc    0     wine_rpcrt4_server
0000009c plugplay.exe
	000000a0    0     
	000000b8    0     
	000000bc    0     wine_sechost_service
	000000c0    0     wine_rpcrt4_server
	00000130    0     wine_rpcrt4_io
000000c4 mscorsvw.exe
	000000c8    0     
	000000f8    0     
	000000fc    0     wine_sechost_service
	00000100    0     
0000010c winedevice.exe
	00000110    0     
	00000118    0     
	0000011c    0     wine_sechost_service
	00000120    0     
	00000124    0     
	00000128    0     
	0000012c    0     
	00000138    0     
	00000140    0     
0000014c rpcss.exe
	00000150    0     
	00000158    0     
	0000015c    0     wine_sechost_service
	00000160    0     wine_rpcrt4_server
	00000164    0     wine_rpcrt4_server
	00000168    0     wine_rpcrt4_io
	000001b4    0     wine_rpcrt4_io
	000001b8    0     wine_rpcrt4_io
000001d4 conhost.exe
	000001d8    0     
	000001dc    0     
	000001e0    0     
System information:
    Wine build: wine-11.0
    Platform: x86_64 (guest: i386)
    Version: Windows 10
    Host system: Linux
    Host version: 6.18.5-zen1-1-zen
```
