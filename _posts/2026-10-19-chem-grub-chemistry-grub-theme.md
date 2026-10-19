---
layout:     post
title:      Chem Grub：给启动菜单加一点化学
subtitle:   护目镜、烧瓶与启动菜单：安装、设计与发布
date:       2026-10-19
author:     wszqkzqk
header-img: img/chem-grub/preview.png
header-mask: 0.53
catalog:    true
tags:       GRUB Arch Linux 化学 SVG 字体 构建系统 AUR
---

## 前言

GRUB 的画面通常在几秒内闪过，很多人甚至不会特意停下来看它一眼。最近，笔者把这段短暂的启动过程做成了一套叫 **Chemistry GRUB** 的主题，并给里面的吉祥物取名 **Chem Grub（化蛆）**：一只薄荷绿的蛆，戴着护目镜、穿着实验服，一手拿着冒泡的锥形瓶，一手翻着化学笔记。启动项放在左侧，右侧则是一间小小的实验室。

![Chem Grub 主界面](/img/chem-grub/preview.png)

这个项目已经公开在 [GitHub](https://github.com/wszqkzqk/chem-grub)，Arch Linux 用户也可以通过 [AUR 的 `chem-grub`](https://aur.archlinux.org/packages/chem-grub) 安装。我希望它看起来有趣，实际使用也顺手：启动项要容易读，中文和英文要排得整齐，Arch 的多内核和 grub-btrfs 快照要自然展开，构建和发布则交给自动化流程。

文章分成两部分：先用起来，再拆开看实现。

## 先把 Chem Grub 用起来

### 从 AUR 安装

Arch Linux 上最直接的安装方式是使用 AUR helper：

```bash
paru -S chem-grub
# 也可以使用 yay -S chem-grub
```

软件包会把主题资源放到 `/boot/grub/themes/chem-grub`，包括背景、图标、字体和主题配置。安装文件和启用主题是两个步骤，因此还需要告诉 GRUB 使用哪一份主题。编辑 `/etc/default/grub`，加入：

```sh
GRUB_THEME="/boot/grub/themes/chem-grub/theme.txt"
```

然后重新生成配置：

```bash
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

重启后就能看到新的启动画面。这里的 `grub-mkconfig` 会根据当前系统和已有的脚本重新生成启动项，Arch 的多内核高级选项和 grub-btrfs 快照结构都会继续保留。

如果希望安装器帮忙备份并设置 `GRUB_THEME`，也可以运行：

```bash
sudo /boot/grub/themes/chem-grub/install.sh
```

在 pacman 已安装好的目录里，这个脚本会跳过文件复制，只负责备份配置并启用主题，启动项仍然由系统原有的生成逻辑负责。

### 从 Release 安装

不想使用 AUR，或者正在使用其他发行版，可以从 [Releases](https://github.com/wszqkzqk/chem-grub/releases) 下载最新的 `chem-grub.zip`：

```bash
curl -fLO https://github.com/wszqkzqk/chem-grub/releases/latest/download/chem-grub.zip
unzip chem-grub.zip
sudo ./chem-grub/install.sh
```

安装器会寻找 `/boot/grub` 或 `/boot/grub2`，备份 `/etc/default/grub` 和已有的 `grub.cfg`，设置主题并重新生成配置。想先查看计划执行的内容，可以使用 `--dry-run`。只想复制文件，可以使用 `--copy-only`。

### 启动之后能看到什么

左侧的启动项仍然是可操作的 GRUB 菜单。Arch 的高级选项和 grub-btrfs 快照目录按 Enter 展开，按 Esc 返回。快照或内核条目较多时，右侧会出现滚动条。1280×720 下可以同时看到 7 项，1920×1080 下可以看到 11 项，较长的条目会继续在列表中滚动显示。

主题也接入了 GRUB 自带的翻译机制。菜单标题、底部键位提示和倒计时文字会随 GRUB 的语言环境变化。启动项名称则仍然由操作系统、os-prober 或 grub-btrfs 决定。某种语言缺少对应翻译时，GRUB 会回退到英文。

这里有一个容易混淆的地方：**图形主题和文本终端是两条显示路径**。`GRUB_TERMINAL_OUTPUT=console` 时，看到的是 GRUB 原生文本菜单，没有 mascot 和背景。`gfxterm` 才会加载主题。若配置为 `gfxterm serial`，图形输出显示主题，串口输出显示文本菜单，两种输出可以同时存在。

无 GUI 的 QEMU 环境建议显式配置串口：

```sh
GRUB_TERMINAL="serial"
GRUB_SERIAL_COMMAND="serial --unit=0 --speed=115200"
```

按当前配置移除冲突的 `console` 设置并重新生成 `grub.cfg` 后，可以这样启动测试盘：

```bash
qemu-system-x86_64 -display none -serial stdio -cdrom /tmp/chem-grub.iso
```

这时看到的是可操作的文本菜单。QEMU 的 `-nographic` 或 `-display none` 本身不会改变 GRUB 的终端选择，串口配置需要单独完成。

---

## 把实验室装进启动菜单

### 先画出 Chem Grub

Chem Grub 的形象从一只 grub 开始：薄荷绿的分节身体、圆圆的眼睛、实验服和锥形瓶。护目镜让它有研究人员的感觉，笔记本则把“研究化学”这个动作说清楚。角色的脸部中心线也经过了调整，镜框桥接、双眼中点和嘴巴中心放在同一条轴线上，`NOTES` 则放在右侧书页顶部的空白处。

![Chem Grub 吉祥物](/img/chem-grub/mascot.png)

角色原稿保存在 [`artwork/chem-grub.svg`](https://github.com/wszqkzqk/chem-grub/blob/main/artwork/chem-grub.svg)，使用 SVG 路径绘制，后续修改颜色和形状都比较方便。背景同样从 SVG 开始，在 [`src/background.svg`](https://github.com/wszqkzqk/chem-grub/blob/main/src/background.svg) 中定义 1920×1080 的深青色实验室、分子结构线和原子轨道。左侧留给菜单，右侧留给角色和实验台。

制作时先渲染角色，再把角色合并到背景中，最后用 `rsvg-convert` 输出 GRUB 可以加载的 PNG。背景只保留 `CHEMISTRY`、`GRUB` 和 `CHEM GRUB` 等品牌文字，动态提示和本地化文字都交给 GRUB 的组件处理，这样同一张背景就能配合不同语言使用。

### GRUB 主题由哪些组件组成

一张背景图无法提供启动菜单所需的选中框、图标、滚动条和终端窗口。主题的 `theme.txt` 负责把这些资源组织起来，下面这段是菜单的主体配置：

```grub
title-font: "Noto Sans Mono CJK SC 20"
desktop-image: "background.png"
terminal-font: "Noto Sans Mono CJK SC 20"

+ boot_menu {
  left = 5%
  top = 32%
  width = 59%
  height = 52%
  item_height = 38
  item_padding = 10
  item_spacing = 6
  icon_width = 28
  icon_height = 28
  item_icon_space = 14
  item_font = "Noto Sans Mono CJK SC 20"
  selected_item_font = "Noto Sans Mono CJK SC 20"
  item_color = "#c6d9cf"
  selected_item_color = "#103a32"
  menu_pixmap_style = "menu_*.png"
  selected_item_pixmap_style = "select_*.png"
  scrollbar = true
  scrollbar_width = 6
  scrollbar_frame = "scrollbar_frame_*.png"
  scrollbar_thumb = "scrollbar_thumb_*.png"
}
```

`left`、`top`、`width` 和 `height` 使用百分比，是为了让 1280×720 和 1920×1080 共用一套布局。`item_height`、`item_padding` 和 `item_spacing` 则根据字体的上升高度、下降高度和想要的行距来调整，不能凭感觉随手填写，否则中文会比英文更容易顶到相邻行。

`menu_*.png` 和 `select_*.png` 采用九宫格切图。GRUB 会分别读取 `_nw`、`_n`、`_ne`、`_w`、`_c`、`_e`、`_sw`、`_s`、`_se` 这些片段，在菜单尺寸变化时保持边框和圆角的形状。`terminal_*.png` 则为按 `e` 编辑启动项或按 `c` 进入命令行时的终端窗口提供背景。

图标按启动项的 `--class` 放置，例如 `arch`、`snapshots`、`windows` 和 `uefi`。如果系统给出了发行版或快照类名，GRUB 就能在 `icons/` 中找到对应图像。启动项本身不需要为主题另写一份清单。

### 中英文字体要一起考虑宽度

主题字体使用的是 **Noto Sans Mono CJK SC**。它同时覆盖拉丁字符、中文、日文、韩文等字符，并且拉丁半宽字符与 CJK 全宽字符保持 1∶2 的宽度关系。中英文混排时，字符串的节奏比较一致，Arch 条目中的内核名称、设备路径和中文说明也能在同一行里对齐。

GRUB 的字体需要整理成自己的 **PF2 位图格式**。构建脚本 [`scripts/build.py`](https://github.com/wszqkzqk/chem-grub/blob/main/scripts/build.py) 用 fontTools 读取字符映射，用 Pillow 光栅化字形，再写出 20 px 和 18 px 两种 PF2 文件。每种尺寸包含 44,810 个字形。每个字形都记录位图、宽高、偏移和前进宽度，位图按 1 bpp 连续打包。

字体文件放在主题根目录：

```text
NotoSansMonoCJKsc-Regular-20.pf2
NotoSansMonoCJKsc-Regular-18.pf2
```

这样 GRUB 的标准 `00_header` 就能在加载主题时找到它们。构建检查还会比较拉丁字符和 CJK 字符的宽度，并拿真实长度的 Arch 条目检查菜单视口，避免出现“字能显示，但排版已经散开”的情况。

### 多语言交给 GRUB 自己处理

如果把 `BOOT ENTRIES / 启动项` 直接写进主题，英文和中文就会永远并排出现，跟系统语言没有关系。制作时，我把这类固定文案从背景和组件中移开，改用 GRUB 已有的翻译入口。

菜单标题没有额外覆盖 `title-text`，因此使用 GRUB 内置并翻译过的 `GRUB Boot Menu`。底部帮助使用 `@KEYMAP_SHORT@`，倒计时使用 `@TIMEOUT_NOTIFICATION_MIDDLE@`：

```grub
+ label {
  left = 6%
  top = 94%
  width = 88%
  height = 28
  font = "Noto Sans Mono CJK SC 18"
  text = "@KEYMAP_SHORT@"
}

+ progress_bar {
  id = "__timeout__"
  left = 6%
  top = 89%
  width = 54%
  height = 32
  font = "Noto Sans Mono CJK SC 18"
  text = "@TIMEOUT_NOTIFICATION_MIDDLE@"
}
```

GRUB 会根据 `$lang` 和已有的语言文件选择翻译。这样一来，字体负责显示字符，GRUB 负责选择语言，主题负责安排位置，三件事各自清楚。启动项的文本仍然来自系统生成的 `grub.cfg`，主题不会替它们翻译。

### 子菜单和长列表沿用同一套逻辑

Arch 的 `10_linux` 会把其他内核和 fallback initramfs 放进 `Advanced options for Arch Linux`，grub-btrfs 则生成自己的 snapshots 子菜单。它们最终都是 `grub.cfg` 中的 `submenu` 结构，进入 `boot_menu` 后使用相同的布局、选中框和滚动条。

因此，主题的制作重点落在列表的可用高度、文字视口和滚动行为上，Arch 和 grub-btrfs 沿用各自的生成逻辑。构建时会检查 `linux-hardened (fallback initramfs)` 这类长名称，也会检查中英文混合的快照条目。列表超出可视区域后，GRUB 自己负责滚动，主题只负责让滚动条和文本保持清晰的边界。

### 打包时分开“安装文件”和“启用主题”

`make` 会生成 `dist/chem-grub/` 和 `dist/chem-grub.zip`，`make check` 则检查资源引用、PF2 数据、字体宽度、多语言占位符和代表性长条目。`make docs` 可以重新生成文档中的预览图。

在 Arch 打包中，安装目标是一个临时的 `$pkgdir`，而真正的启用动作发生在用户的系统上。为此，Makefile 提供了 `make install DESTDIR=...` 的暂存安装方式，`PKGBUILD` 直接复用它：

```bash
package() {
    cd "${pkgname}"
    make install DESTDIR="${pkgdir}"
}
```

这个分支只复制主题、许可证和文档，不修改主机的 `/etc/default/grub`，也不调用 `grub-mkconfig`。`DESTDIR` 为空时，才走主机上的安装和启用脚本。这样，`makepkg` 只负责把文件装好，是否启用由用户决定，启动配置也不会在 pacman 安装过程中被悄悄改写。

### 让版本号跟随 commit

主题更适合滚动构建，版本号由提交数量、提交日期和短 hash 组成，和 `qt-web-extractor` 的做法一致：

```bash
printf "r%s.%s.%s" \
    "$(git rev-list --count HEAD)" \
    "$(git log -1 --format=%cd --date=format:%Y%m%d)" \
    "$(git rev-parse --short HEAD)"
```

CI 先在 Ubuntu 上运行 `make check`，再在 Arch Linux 容器中执行 `makepkg`。随后，[`softprops/action-gh-release`](https://github.com/softprops/action-gh-release) 为当前 commit 创建独立的 tag 和正式 Release，并生成 Release Notes。附件只包含 `chem-grub.zip` 和对应的 Arch 软件包，每个提交都有自己的版本，不会把旧文件覆盖到同一个 Release 页面里。

AUR 的发布排在这些检查之后。CI 使用 `PKGBUILD-AUR` 构建并生成 `.SRCINFO`，再通过 AUR 的 SSH Git 远程推送 `master`。`AUR_SSH_PRIVATE_KEY`、`AUR_USERNAME` 和 `AUR_EMAIL` 只保存在 GitHub Actions 的 secrets 中，私钥不会进入仓库。AUR 的历史使用普通 `git push`，不做强制覆盖。

### 最后还要验证两条显示路径

`make check` 能检查文件和构建逻辑，但 GRUB 是否真正接受主题，还需要在虚拟机里加载。在安装了 `grub-mkrescue` 和 `xorriso` 的 Linux 测试机上，可以准备一张不启动操作系统的测试盘。先复制主题，再按文档中的示例准备 `$work/boot/grub/grub.cfg`：

```bash
work=$(mktemp -d)
mkdir -p "$work/boot/grub/themes"
cp -a dist/chem-grub "$work/boot/grub/themes/"
# 将 docs/VALIDATION.md 中的测试 grub.cfg 放到 $work/boot/grub/grub.cfg
grub-mkrescue -o /tmp/chem-grub.iso "$work"
qemu-system-x86_64 -m 512 -cdrom /tmp/chem-grub.iso -boot d -vga std
```

在 QEMU 中检查背景、菜单、子菜单、滚动条、倒计时以及 `e` 编辑和 `c` 命令行，再用串口配置检查无 GUI 时的文本菜单。`grub-script-check` 只负责检查 `grub.cfg` 的语法，主题是否显示正确仍然要看实际渲染。完整的测试配置和检查清单放在 [`docs/VALIDATION.md`](https://github.com/wszqkzqk/chem-grub/blob/main/docs/VALIDATION.md)。

## 写在最后

Chem Grub 看起来是一只拿烧瓶的蛆，背后却涉及 SVG 原稿、九宫格图片、PF2 字体、GRUB 原生翻译、暂存安装、Arch 打包和持续发布。把这些部分拆开之后，最终呈现的是一套可以维护、可以复现、也方便别人修改的小项目。

如果你使用 Arch Linux，可以从 `paru -S chem-grub` 开始。如果你对实现细节感兴趣，欢迎直接阅读 [源码](https://github.com/wszqkzqk/chem-grub)。反馈时最好带上发行版、GRUB 版本、分辨率和语言环境，这些信息能帮助定位显示差异。也欢迎你给这只小蛆提出新的实验点子。
