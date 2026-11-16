---
layout:       post
title:        PvZ-Portable：跨平台植物大战僵尸重实现
subtitle:     《植物大战僵尸：年度版》的开源重实现，支持桌面、移动设备、Switch 与浏览器
date:         2026-01-26
author:       wszqkzqk
header-img:   img/games/pvz-portable/bg-pvz-portable.webp
catalog:      true
pinned:       true
pinned_order: 2
tags:         C++ SDL OpenGL 开源软件 游戏移植 开源游戏 PvZ-Portable
---

# [PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable)

笔者在大一时曾经写过 [Python 版植物大战僵尸](https://wszqkzqk.github.io/2022/04/05/pypvz/)，那个项目以学习 Python 和面向对象编程为主，虽然能玩，但还原度和完成度都相当有限。PvZ-Portable 则把目标放在《植物大战僵尸：年度版》的完整重实现与跨平台运行上，希望为现代桌面、移动设备、主机和浏览器带来忠实的原版体验。

目前，Windows、Linux、macOS、Android、iOS/iPadOS 和 Nintendo Switch 的预构建版本都可以从 [GitHub Releases](https://github.com/wszqkzqk/PvZ-Portable/releases) 下载，其他平台可以自行编译，也可以直接打开[浏览器版](https://wszqkzqk.github.io/PvZ-Portable/pvz-portable.html)体验。预构建二进制由 GitHub Actions 编译，主要用于测试，有条件的话更推荐自行编译——例如 macOS 用户可以借此避开应用签名问题。

> **游戏资源说明**：仓库和预构建包只包含引擎。游玩时，请从你合法拥有的《植物大战僵尸：年度版》中准备 `main.pak` 和 `properties/` 目录（正版可在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 购买）。

## 为什么要重写？

原版《植物大战僵尸》虽然经典，但毕竟是十几年前的游戏。原版使用了 DirectX 7 等过时技术，且只提供 32 位可执行文件，在现代操作系统上难免遇到兼容性问题；分辨率只有 800×600，在高分辨率屏幕上窗口小得可怜，想放大只能开全屏；而且它从未官方支持过 Linux，更没有适配 LoongArch 等新兴指令集架构。

在开源社区，已经有前人基于逆向工程得到的文档和社区研究，重写出了最初的游戏引擎。[^1] [^2] [^3] PvZ-Portable 在此基础上进一步开发，是一个专注于跨平台移植技术的研究项目。

## 项目特点

### 图形、音频与游戏

- **SDL3 与 OpenGL ES 2.0**：渲染统一使用 OpenGL ES 2.0，并可回退到桌面 OpenGL 2.1+。这套接口可以覆盖桌面 GPU、移动芯片、WebGL 和主机平台。[^4]
- **窗口与高分屏**：支持自由调整窗口、最大化、全屏缩放和 Alt+Enter 切换全屏，并根据高分屏的物理像素尺寸进行渲染。
- **原版音乐与音效**：通过 SDL3_mixer 和 libopenmpt 播放原版 MO3 音乐，支持曲目跳转与逐通道音量控制。
- **原版内容**：支持隐藏小游戏页面 Limbo 和僵尸头像工具 Zombatar。在小游戏、解谜或生存模式选择界面快速点击空白处 5 次，即可解锁 Limbo 页面。
- **可选修复**：`DO_FIX_BUGS` 提供一组社区修复，默认关闭，由构建者选择是否启用。[^6]
- **确定性回放**：可以把游戏过程录制为 `.dmo` 文件，用于问题复现和回归测试。

### 可移植性

- **32 位与 64 位架构**：支持 i686、x86_64、aarch64、riscv64、loongarch64 等架构。
- **字节序无关设计**：支持小端和大端系统，可移植存档能够跨字节序使用。大端支持已经实现，尚未在实体硬件上验证。
- **现代化 C++20**：使用 `std::thread`、`std::filesystem` 和统一的 UTF-8 字符串处理，支持各平台的 Unicode 路径与多语言文本输入。
- **低内存模式**：`LOW_MEMORY` 构建选项会减少资源预缓存，面向内存受限的主机设备。

### 存档与资源兼容

- **原版用户进度**：可以直接读写原版 PC GOTY 的 `users.dat`、`user*.dat`，涵盖冒险进度、金币、禅境花园和成就等内容，并以向后兼容的方式修复 2038 年时间戳溢出问题。
- **跨平台关卡存档**：关卡中途进度默认保存为 `.v4`，采用逐字段序列化的 TLV 结构，可以跨操作系统、编译器和 CPU 架构转移。仓库还提供 YAML 导出、编辑与导入工具。
- **旧版关卡存档**：保留 `.dat` 后备读取与自动迁移支持。旧格式与程序内存布局有关，跨平台使用仍以 `.v4` 为准。
- **多语言资源**：支持英语、汉语、德语、法语、西班牙语和意大利语等官方 GOTY 资源包。

## 开始使用

### 游戏资源与版本

游玩时需要 `main.pak` 和 `properties/` 目录，也可以使用解包后的资源文件替代 `main.pak`。

项目主要针对 **GOTY 1.2.0.1073 EN** 设计和测试，推荐使用这一版本获得最佳开箱体验。Steam GOTY 1.2.0.1096、其他官方语言 GOTY 版本以及 1.1.0.1056 ZH 也可以正常游玩。不同版本的少量字符串键名存在差异，可能表现为图鉴介绍或按钮文字缺失。

遇到这种情况，可以在仓库根目录运行以下命令生成兼容覆盖文件：

```bash
python3 scripts/make-compat-overrides.py "/path/to/main.pak"
```

脚本会在 `main.pak` 同级的 `properties/` 目录中生成 `pvz-portable.xml`，一次覆盖所有已知的键名差异。可以通过 `-o` 指定输出路径，通过 `--force` 覆盖已有文件。多语言支持的实现过程见[专题博客](https://wszqkzqk.github.io/2026/03/01/PvZ-Portable-Multilingual-Support/)。

这些差异全部源于后续版本对字符串键名的调整，目前已知的有：

| 现象（仅非 1.2.0.1073 EN 资源） | 原因 |
| :--- | :--- |
| **图鉴蓝色介绍文字缺失** | 1.2.0.1096 将介绍段落从 `[XXX_DESCRIPTION]` 拆分到新的 `[XXX_DESCRIPTION_HEADER]` 键，旧引擎只读取前者。 |
| **“重新开始”按钮文字缺失** | 键名由 `[RESTART_LEVEL]` 改为 `[RESTART_LEVEL_BUTTON]`。 |
| **未遭遇的僵尸显示 `???`** | `[NOT_ENCOUNTERED_YET]` 的值被改为 `???`，原文本移至 `[NOT_ENCOUNTERED_YET_DESCRIPTION]`。 |
| **戴夫收购物品的价格显示为实际值的 1/10** | 1.2.0.1073 的 `[CRAZY_DAVE_1700]` 模板在 `{SELL_PRICE}` 后有一个字面量 `0`（因为引擎传入的是价格÷10），1.2.0.1096 把这个 `0` 删掉了。 |

### Windows、Linux、macOS 与 BSD

将 `main.pak` 和 `properties/` 放在 `pvz-portable` 可执行文件所在目录，然后启动程序。资源路径以可执行文件为基准，因此可以从任意工作目录启动。

存档、设置与缓存保存在系统的用户数据目录：

- **Linux**：`~/.local/share/io.github.wszqkzqk/PvZPortable/`
- **Windows**：`%APPDATA%\io.github.wszqkzqk\PvZPortable\`
- **macOS**：`~/Library/Application Support/io.github.wszqkzqk/PvZPortable/`

原版的 `users.dat`、`user1.dat` 等文件可以复制到其中的 `userdata/` 子目录继续使用。

### Android

Android 版需要 Android 7.0 或更高版本。Releases 提供 `arm64-v8a` APK，其他 ABI 可以从源码构建。

1. 安装并打开 APK，首次启动时会进入资源导入界面。
2. 选择包含 `main.pak` 和 `properties/` 的 ZIP 文件或文件夹。
3. 导入完成后点击 **Start Game**。
4. 之后可以长按应用图标，通过 **Manage Data** 重新导入资源或导入、导出存档。

资源导入与存档管理使用 Android Storage Access Framework，无需广泛存储权限。更多实现细节见 [Android 适配博客](https://wszqkzqk.github.io/2026/03/04/PvZ-Portable-Android-Adaptation/)。

### iOS/iPadOS

iOS/iPadOS 版需要 iOS/iPadOS 16.4 或更高版本，支持 arm64 设备。

1. 从 Releases 下载未签名 IPA，通过 AltStore、TrollStore 或 Xcode 侧载。免费 Apple ID 的签名有效期为 7 天。
2. 打开 iOS Files 应用，或通过 Finder/iTunes 文件共享，将 `main.pak` 和 `properties/` 复制到 **PvZ Portable** 的 Documents 目录。

存档位于同一目录下的 `userdata/` 中，可以通过 Files 或 Finder 导出。更多实现细节见 [iOS 适配博客](https://wszqkzqk.github.io/2026/03/08/PvZ-Portable-iOS-Adaptation/)。

### 浏览器

1. 打开[浏览器版页面](https://wszqkzqk.github.io/PvZ-Portable/pvz-portable.html)。
2. 选择包含 `main.pak` 和 `properties/` 的 ZIP 文件或文件夹，点击 **Start Game**。

资源处理全部在浏览器本地完成。存档保存在 IndexedDB 中，可以通过页面控件导出或导入 ZIP 文件。更多实现细节见 [WebAssembly 适配博客](https://wszqkzqk.github.io/2026/03/10/PvZ-Portable-WebAssembly-Adaptation/)。

## 从源码构建

构建需要 C++20 编译器、CMake（≥ 3.12）、Ninja、SDL3（≥ 3.2.12）、SDL3_mixer、libopenmpt、libpng、libjpeg-turbo 和 zlib。各平台的依赖安装命令见 [README](https://github.com/wszqkzqk/PvZ-Portable#building-from-source)。

```bash
git clone https://github.com/wszqkzqk/PvZ-Portable.git
cd PvZ-Portable
cmake -G Ninja -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

编译完成后，将游戏资源放到可执行文件所在目录，也可以通过 `-resdir` 指定资源目录，通过 `-savedir` 指定可写数据目录。

常用构建选项如下：

| 选项 | 默认值 | 作用 |
| :--- | :--- | :--- |
| `PVZ_DEBUG` | `OFF`（Debug 构建为 `ON`） | 启用作弊键、调试显示和诊断功能。[^5] |
| `DO_FIX_BUGS` | `OFF` | 启用可选的原版逻辑修复。[^6] |
| `LOW_MEMORY` | `OFF` | 减少资源预缓存与内存占用。 |
| `CONSOLE` | `OFF`（Debug 构建为 `ON`） | 在 Windows 上显示控制台窗口。 |
| `BUILD_STATIC` | `OFF` | 在 Windows（MinGW）和使用 glibc 的 Linux 上静态链接依赖。 |

例如，以下命令会构建启用作弊键的 Release 版本，运行时添加 `-cheat` 即可使用：[^5]

```bash
cmake -G Ninja -B build -DCMAKE_BUILD_TYPE=Release -DPVZ_DEBUG=ON
```

关于渲染、音频、存档与回放的实现，可以继续阅读 [SDL3 迁移](https://wszqkzqk.github.io/2026/11/09/PvZ-Portable-SDL3-Migration/)、[OpenGL ES 2.0 迁移](https://wszqkzqk.github.io/2026/02/16/PvZ-Portable-GLES2-Migration/)、[存档格式 v4](https://wszqkzqk.github.io/2026/01/30/PvZ-Portable-Save-Format-v4/) 和[确定性回放](https://wszqkzqk.github.io/2026/07/22/PvZ-Portable-Demo-Deterministic-Replay/)等专题文章。

## 开源协议与致谢

PvZ-Portable 的源代码以 [LGPL-3.0-or-later](https://www.gnu.org/licenses/lgpl-3.0.html) 发布。项目以非商业的教育与研究为目的，游戏 IP 和原始素材属于 PopCap/EA，与 PopCap/EA 没有授权、合作或隶属关系。

感谢 Patoke 和 Headshotnoby 的早期移植工作，感谢 SDL、OpenMPT 等项目提供的跨平台基础，也感谢所有整理游戏机制、报告问题和参与贡献的社区成员。

项目地址：[https://github.com/wszqkzqk/PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable)

## 备注

[^1]: [Patoke 的 re-plants-vs-zombies](https://github.com/Patoke/re-plants-vs-zombies)

[^2]: [Headshotnoby 的 re-plants-vs-zombies fork](https://github.com/headshot2017/re-plants-vs-zombies)

[^3]: 互联网上存在大量关于植物大战僵尸游戏机制的研究文档，部分基于逆向分析，例如在 [植物大战僵尸吧](https://tieba.baidu.com/f?ie=utf-8&kw=%E6%A4%8D%E7%89%A9%E5%A4%A7%E6%88%98%E5%83%B5%E5%B0%B8), [PVZ Wiki](https://wiki.pvz1.com/doku.php?id=home) 和 [PvZ Tools](https://pvz.tools/memory/) 等平台上都有丰富详尽的游戏机制细节资料。但**笔者从未对游戏进行过任何逆向工程分析**。笔者仅通过**公开的社区研究资料**和**实际游戏测试**来理解游戏机制，并在此基础上进行重实现。

[^4]: 原版植物大战僵尸使用 DirectX 7 进行渲染，无法跨平台且性能较差。将游戏移植到 OpenGL 的大量工作离不开 [Patoke](https://github.com/Patoke/re-plants-vs-zombies) 和 [Headshotnoby](https://github.com/headshot2017/re-plants-vs-zombies) 的贡献。

[^5]: 以下为作弊键清单（仅在编译时启用 `PVZ_DEBUG` 且运行参数带 `-cheat` 时有效，且不少只在特定界面/模式生效）：
    * **标题/主菜单**：
        * 按键记录“快速进入”目标：
            * `Z` → 直接加载禅境花园。
            * `M` → 正常进入主菜单。
            * `S` → 直接进入生存模式选择页。
            * `C` → 直接进入小游戏选择页。
            * `P` → 直接进入解谜模式选择页。
            * `U` → 直接进入试玩/引导关。
            * `I` → 直接进入序章关。
            * `R` → 直接进入片尾。
            * `T` → 直接加载冒险模式。
    * **选卡界面**：`(Debug Play)` （鼠标点击触发）随机选卡并立刻开始游戏。
    * **模式选择界面**：
        * `u`：解锁冒险进度、模式、奖杯记录并加 50000×10 金币（上限 99999×10），同时重置冒险关卡进度存档（用于开发测试）。
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
            * `0` +100 阳光；`9` 阳光直接拉满（内部上限 9990）；`-` -100 阳光。
            * `$` +100×10 金钱并显示钱袋。
            * `%` 切换渲染模式（窗口/3D）。
            * `M` 调整音乐 Burst Override。
            * `#` 生存模式快速推进 5 轮（10面旗帜）。
            * `!` 快速完成当前关/当前生存阶段（随模式做收尾逻辑）。
            * `+` 快速过关，非无尽生存模式下直接整段结束（推进 5 个阶段）。
            * `q` 一键布阵/补波/开罐（随模式变化）。
            * `O` 前三列自动补花盆。
            * `B` 吹散迷雾。
            * `t` 召唤雪橇小队并铺冰道。
            * `r` 从墓碑刷怪。
            * `1` 杀死 (0,0) 处植物并计入被吃。
            * `Ctrl + C` 触发崩溃测试并强制下一波倒计时。
        * 僵王博士：`b/u/s/r/h/d` 分别触发蹦极/召唤/踩踏/扔车/吐球/对僵王造成10000伤害。
        * 直接刷僵尸：
            * `b` 蹦极、`o` 橄榄球、`s` 铁门、`L` 扶梯、`y` 雪人、`a` 旗帜、`w` 读报、`F` 气球、`n` 潜水（泳池）、`c` 路障、`m` 舞王、`h` 铁桶、`D` 矿工、`p` 撑杆、`P` 跳跳、`R` 海豚（泳池）、`j` 小丑、`g` 巨人、`G` 红眼巨人、`i` 冰车、`C` 投石。
          * 植物僵尸相关关卡：`w/t/j/g/s` 分别刷出坚果/高坚果/辣椒/机枪/倭瓜僵尸。
        * **禅境花园**：
            * `m` 加一盆金盏花（随机颜色）；`+` 加随机植物；`a` 加完全长大的随机植物。
            * `f` 自动照料第一株有需求的植物（每次按键只处理一株）；`r` 重置所有植物计时。
            * `s` 蜗牛唤醒/重置计时；`c` 加巧克力次数。
            * `]` 循环修改手推车中植物的类型。
        * **智慧树**：
            * `f` 施肥；`g` 快速生长；`b` 推进到下一说话阶段。
            * `0`~`8` 设置智慧树高度为`0/9/19/29/39/49/98/498/998`，并触发生长。
    * **片尾字幕**：
        * `1`~`7`、`q`~`t`、`a`~`g` 跳转到不同字幕段。
        * `n` 切换字幕与音乐同步。
    * **其他**：
        * 开场/过场动画中，`空格`/`回车`/`Esc` 跳过开场；试玩模式中 `Esc` 快进戴夫演讲。
        * 破罐模式中按住 `Shift` 可让罐子半透明（透视内容）。

[^6]: 目前 `DO_FIX_BUGS` 包含以下修复：
    * 修复我是僵尸关卡中蹦极僵尸重复掉落阳光或物品的问题。
    * 使魅惑的巨人僵尸攻击敌方僵尸，而非植物。
    * 使魅惑的巨人僵尸投掷魅惑小鬼（修正比例、生命值和方向）。
    * 使魅惑的巨人僵尸在解谜模式中可以砸碎花瓶。
    * 使魅惑的豌豆/机枪头僵尸向前射击而非向后。
    * 使魅惑的辣椒/窝瓜僵尸伤害敌方僵尸而非植物。
    * 修正魅惑窝瓜僵尸追踪和砸碎敌方僵尸的坐标问题。
    * 使魅惑的辣椒僵尸正确清除僵王博士的技能（冰球/火球）和梯子。
    * 同步伴舞僵尸与舞王僵尸的动画（修复“女仆秘籍”位移问题）。
    * 修复扶梯僵尸手臂恢复的视觉故障。
