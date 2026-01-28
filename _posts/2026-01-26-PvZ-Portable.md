---
layout:       post
title:        PvZ-Portable：跨平台植物大战僵尸重实现
subtitle:     近乎100%复现植物大战僵尸年度版体验的开源引擎，支持Linux、Windows、macOS等多平台
date:         2026-01-26
author:       wszqkzqk
header-img:   img/bg-pvz.webp
catalog:      true
tags:         C++ SDL2 OpenGL 开源软件 游戏移植
---

# [PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable)

笔者在大一时曾经尝试写过 [Python 版植物大战僵尸](https://wszqkzqk.github.io/2022/04/05/pypvz/)。那时候笔者还在起步阶段，用 Python 和 Pygame 做了一个简单的练习，主要目的是学习 Python 和面向对象编程。那个项目虽然能玩，但在还原度上和功能完成度上存在不少局限。

时隔几年，随着技术栈的深入，在开源社区前人大量代码[^1] [^2]的基础上，笔者带来了一个强大得多的新项目 —— [**PvZ-Portable**](https://github.com/wszqkzqk/PvZ-Portable)。

[^1]: [Patoke 的 re-plants-vs-zombies](https://github.com/Patoke/re-plants-vs-zombies)
[^2]: [Headshotnoby 的 re-plants-vs-zombies fork](https://github.com/headshot2017/re-plants-vs-zombies)

这是一个**跨平台**的社区驱动项目，是对《植物大战僵尸：年度版》（GOTY Edition）的完整重实现。与之前的玩具项目不同，PvZ-Portable 的目标是**100% 还原原版游戏体验**，同时让它能在现代硬件和各种非官方支持的平台上流畅运行。项目开源开发，用于交流学习**跨平台移植技术**、**引擎现代化**以及研究如何将经典游戏逻辑适配到各种不同的硬件架构（如 ARM, RISC-V, LoongArch）上。

| 🌿 原汁原味 | 🎮 可移植/跨平台 | 🛠️ 开源开放 |
| :---: | :---: | :---: |
| 几乎 100% 复刻原版所有特性 | 支持 Linux, Windows, macOS, Switch... | 基于 OpenGL & SDL |

## 为什么要重写？

原版《植物大战僵尸》虽然经典，但毕竟是十几年前的游戏。原版使用了 DirectX 7 等过时技术，且只提供了 32 位可执行文件，在现代操作系统上运行可能会遇到兼容性问题，而且它从未官方支持过 Linux，也没有适配过 LoongArch 等新兴指令集架构。

在开源社区，已经有前人基于逆向工程得到的文档和社区研究，[^3]重写了游戏引擎。PvZ-Portable 在此基础上进一步开发，是一个专注于跨平台移植技术的研究项目，主要目标包括：

[^3]: 互联网上存在大量关于植物大战僵尸游戏机制的研究文档，部分基于逆向分析，例如在 [植物大战僵尸吧](https://tieba.baidu.com/f?ie=utf-8&kw=%E6%A4%8D%E7%89%A9%E5%A4%A7%E6%88%98%E5%83%B5%E5%B0%B8), [PVZ Wiki](https://wiki.pvz1.com/doku.php?id=home) 和 [PvZ Tools](https://pvz.tools/memory/) 等平台上都有丰富详尽的游戏机制细节资料。但**笔者从未对游戏进行过任何逆向工程分析**。

1.  **现代化渲染**：使用 SDL2 和 OpenGL 替代了古老的 DirectX[^4]，支持硬件加速，并且终于**支持调整窗口大小**了！
    *   由于游戏分辨率仅有 800x600，在高分辨率屏幕上运行原版时窗口会非常小，只有开启全屏模式才能放大。
    *   PvZ-Portable **支持任意缩放比例**，也支持**窗口最大化**和全屏。
2.  **真正、全面跨平台**：
    *   **OS**: Linux, Windows, macOS
    *   **ISA**: x86_64, aarc64, riscv64, loongarch64, ...
    *   **主机**: Nintendo Switch
    *   **其他**: Haiku OS 等小众系统
3.  **音频升级**：基于 [Headshotnoby](https://github.com/headshot2017/) 的适配工作，使用 [SDL Mixer X](https://github.com/WohlSoft/SDL-Mixer-X) 和 libopenmpt，支持 MO3 音乐格式。
4.  **修复原版 Bug**：在保持原汁原味的同时，本项目还可选修复一些原版游戏中存在的逻辑错误（例如有关特殊的魅惑僵尸的某些行为等）。当然，如果你喜欢那些“特性”，也可以选择不开启修复。（默认不启用额外修复，保证体验与原版一致）

[^4]: 原版植物大战僵尸使用 DirectX 7 进行渲染，无法跨平台且性能较差。目前为止，移植到 OpenGL 的主要工作由 [Patoke](https://github.com/Patoke/re-plants-vs-zombies) 和 [Headshotnoby](https://github.com/headshot2017/re-plants-vs-zombies) 完成。

## ⚠️ 版权与使用说明

**重要：本项目仅包含代码引擎，不包含任何游戏素材！**

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

要游玩此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中：

*   `main.pak`
*   `properties/` 目录

本项目仅提供引擎代码，用于技术学习，**不包含**上述任何游戏资源文件，任何游戏资源均需要用户自行提供正版游戏文件。

## 使用指南

### 数据存储

PvZ-Portable 会自动在各操作系统的标准应用数据目录下存储存档和配置：

*   **Linux**: `~/.local/share/io.github.wszqkzqk/PlantsVsZombies/`
*   **Windows**: `%APPDATA%\io.github.wszqkzqk\PlantsVsZombies\`
*   **macOS**: `~/Library/Application Support/io.github.wszqkzqk/PlantsVsZombies/`
*   **Nintendo Switch**: `sdmc:/switch/PlantsvsZombies`

你可以手动将原版的**用户进度**文件复制到上述路径的 `userdata` 子目录下，以继续你的游戏进度（例如复制 `users.dat`, `user1.dat` 等）。但是请注意，由于**关卡内进度**（例如 `game1_13.dat`）的保存涉及到内存数据，无法兼容原版。

## 构建与测试

作为开源项目，你可以自由地编译它。本项目使用了现代化的 CMake 构建系统。

### 构建

这部分仅涉及引擎的编译，适用于开发者或希望手动管理游戏文件的用户。确保安装了 CMake, Ninja, SDL2, OpenGL, libopenmpt 等依赖。这里列出了部分平台的依赖安装命令：

*   **Arch Linux**:
    ```bash
    sudo pacman -S --needed base-devel cmake glew libjpeg-turbo libogg libopenmpt libpng libvorbis mpg123 ninja sdl2-compat
    ```
*   **Windows (MSYS2 UCRT64)**:
    ```bash
    pacman -S --needed base-devel mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-glew mingw-w64-ucrt-x86_64-libjpeg-turbo mingw-w64-ucrt-x86_64-libopenmpt mingw-w64-ucrt-x86_64-libogg mingw-w64-ucrt-x86_64-libpng mingw-w64-ucrt-x86_64-libvorbis mingw-w64-ucrt-x86_64-mpg123 mingw-w64-ucrt-x86_64-ninja mingw-w64-ucrt-x86_64-SDL2
    ```
*   **macOS (Homebrew)**:
    ```bash
    brew install cmake dylibbundler glew jpeg-turbo libogg libopenmpt libpng libvorbis mpg123 ninja sdl2
    ```

**配置项目 (Release 模式)**:

```bash
cmake -G Ninja -B build -DCMAKE_BUILD_TYPE=Release
```

如果需要使用**作弊键** `-tod` 等功能，可以启用 `PVZ_DEBUG` 选项：

```bash
cmake -G Ninja -B build -DCMAKE_BUILD_TYPE=Release -DPVZ_DEBUG=ON
```

这样如果在运行时向程序添加 `-tod` 参数，就可以启用作弊功能。[^5]

[^5]: 以下为作弊键清单（仅在编译时启用 `PVZ_DEBUG` 且运行参数带 `-tod` 时有效，且不少只在特定界面/模式生效）：
    * **标题/主菜单**：
        * 按键记录“快速进入”目标：
            * `End` → 直接加载禅境花园。
            * `M` → 正常进入主菜单。
            * `S` → 直接进入生存模式选择页。
            * `C` → 直接进入小游戏选择页。
            * `P` → 直接进入解谜模式选择页。
            * `U` → 直接进入试玩/引导关。
            * `I` → 直接进入序章关。
            * `R` → 直接进入片尾。
            * `T` → 直接加载冒险模式。
    * **选卡界面**：`Esc` 随机选卡。
    * **模式选择界面**：
        * `u`：解锁冒险进度、模式、奖杯记录并加金币（用于开发测试）。
        * `c` / `C`：临时解锁小游戏/解谜/生存入口。
    * **关卡内快捷键**：
        * 通用：
            * `l` 打开关卡跳转对话框
            * `<` 打开选项。
            * `8` 自由种植开关（无需冷却、阳光、位置检测）。
            * `7` 放慢游戏速度。
            * `6` 加快游戏速度。
            * `z` 切换调试文字。
            * `?`/`/` 触发下一波倒计时。
            * `0` +100 阳光；`9` +999999 阳光；`-` -100 阳光。
            * `$` +100*10 金钱并显示钱袋。
            * `%` 切换渲染模式（窗口/3D）。
            * `M` 调整音乐 Burst Override。
            * `#` 生存模式快速推进 5 轮（10面旗帜）。
            * `!`/`+` 快速过关（随模式做收尾逻辑）。
            * `q` 一键布阵/补波/开罐（随模式变化）。
            * `O` 前三列自动补花盆。
            * `B` 吹散迷雾。
            * `t` 召唤雪橇小队并铺冰道。
            * `r` 从墓碑刷怪。
            * `1` 杀死 (0,0) 处植物并计入被吃。
            * `Ctrl + C` 触发崩溃测试并强制下一波倒计时。
        * 僵王博士：`b/u/s/r/h/d` 分别触发蹦极/召唤/踩踏/扔车/吐球/对僵王造成10000伤害。
        * 直接刷僵尸：
            * `b` 蹦极、`o` 橄榄球、`s` 铁门、`L` 扶梯、`y` 雪人、`a` 旗帜、`w` 读报、`F` 气球、`n` 潜水（泳池）、`c` 路障、`m` 舞王、`h` 铁桶、`D` 矿工、`p` 撑杆、`P` 蹦极杖、`R` 海豚（泳池）、`j` 小丑、`g` 巨人、`G` 红眼巨人、`i` 冰车、`C` 投石。
          * 植物僵尸相关关卡：`w/t/j/g/s` 分别刷出坚果/高坚果/辣椒/机枪/倭瓜僵尸。
        * **禅境花园**：
            * `m` 加一盆金盏花（随机颜色）；`+` 加随机植物；`a` 加完全长大的随机植物。
            * `f` 自动照料当前需要的植物；`r` 重置所有植物计时。
            * `s` 蜗牛唤醒/重置计时；`c` 加巧克力次数。
            * `]` 循环修改手推车中植物的类型。
        * **智慧树**：
            * `f` 施肥；`g` 快速生长；`b` 重置阶段计数。
            * `0`~`8` 设置智慧树高度为`0/9/19/29/39/49/98/498/998`，并触发生长。
    * **片尾字幕**：
        * `1`~`7`、`q`~`t`、`a`~`g` 跳转到不同字幕段。
        * `n` 切换字幕与音乐同步。

**编译**:

```bash
cmake --build build
```

编译完成后，你需要手动将正版游戏的 `main.pak` 和 `properties/` 复制到生成的可执行文件所在目录才能运行。

### Arch Linux 打包与环境测试

为了方便在 Arch Linux 环境下进行测试，仓库中提供了 `PKGBUILD` 脚本；笔者创建这个文件的原因主要是为了**研究引擎在不同显示服务器（Wayland vs. X11）下的行为差异**。

由于法律原因，我们无法在软件包中分发游戏资源。在打包前，你需要**自行提供**正版游戏资源：
1.  找到你购买的正版游戏安装目录，常见路径包括：
    *   **Steam (Linux/Proton)**:
        `~/.steam/steam/steamapps/common/PlantsVsZombies/`
    *   **Steam (Windows)**:
        `C:\Program Files (x86)\Steam\steamapps\common\PlantsVsZombies\`
    *   **PopCap (Windows)**:
        `C:\Program Files (x86)\PopCap Games\PlantsVsZombies\` 或
        `C:\Program Files\PopCap Games\PlantsVsZombies\`
2.  将 `main.pak` 和 `properties/` 目录打包为 `Plants_vs._Zombies_1.2.0.1073_EN.zip`。
    *   确保 `main.pak` 位于 ZIP 文件的根目录，而不是子目录内。例如，可以使用以下命令（假设你在游戏目录下）：
        ```bash
        7z a Plants_vs._Zombies_1.2.0.1073_EN.zip main.pak properties/
        ```
3.  将该 ZIP 文件放置在 `archlinux/` 目录下。

然后执行打包命令：

```bash
cd archlinux
makepkg -si
```

#### 关于 Wayland 的测试

在 Linux 平台上，我们特别关注 SDL2 后端在 Wayland 和 X11 环境下的表现差异（例如全屏下的黑边闪烁问题）。为此，Arch Linux 包中引入了一个特殊的启动脚本，用于自动检测环境并在必要时调整 SDL 视频驱动：

```
#!/usr/bin/env sh

# Default to Wayland SDL video driver if running in a Wayland session and $SDL_VIDEODRIVER is not set
if [ -n "$WAYLAND_DISPLAY" ] && [ -z "$SDL_VIDEODRIVER" ]; then
    export SDL_VIDEODRIVER="wayland,x11"
fi

exec /usr/share/pvz-portable/pvz-portable "$@"
```

在运行的时候，这个脚本会检查当前是否在 Wayland 会话中运行，如果是且没有设置 `SDL_VIDEODRIVER` 环境变量，则会将其设置为 `wayland,x11`，以优先使用 Wayland 后端。在需要测试 Xwayland 的情况下，可以在启动时手动设置 `SDL_VIDEODRIVER=x11`。

## [DeepWiki](https://deepwiki.com/wszqkzqk/PvZ-Portable) AI 助手

如果你在测试、学习或开发 PvZ-Portable 过程中遇到问题，可以询问项目的 [DeepWiki AI 助手](https://deepwiki.com/wszqkzqk/PvZ-Portable)。

由于本项目高度精准地实现了原版的游戏逻辑，你也可以通过 DeepWiki AI 助手来**查询原版游戏的详细内部机制和规则**。

## 致谢

这个项目站在了巨人的肩膀上。

* 特别感谢 [Patoke](https://github.com/Patoke/) 和 [Headshotnoby](https://github.com/headshot2017/) 对引擎的跨平台移植的杰出贡献！
*  感谢 SDL 开发团队提供的强大跨平台库！
*  感谢所有为游戏研究做出贡献的社区成员！
*  感谢宝开创造了这个经典游戏！

如果你对游戏引擎开发或者跨平台移植感兴趣，欢迎访问项目仓库给个 Star，或者参与贡献！

👉 **项目地址**: [https://github.com/wszqkzqk/PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable)
