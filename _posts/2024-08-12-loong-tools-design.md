---
layout:     post
title:      龙芯的Arch Linux移植工作流程
subtitle:   Loong Arch Linux软件包开发者维护工具设计
date:       2024-08-12
author:     wszqkzqk
header-img: img/bg-mountain-darken.webp
catalog:    true
tags:       系统配置 系统维护 开源软件 Linux archlinux 国产硬件 虚拟化 龙芯 LoongArchLinux 容器
---

本文将介绍目前LoongArch的Arch Linux移植的**最小**维护架构（**不包括**CI工具）和参与[北京大学Linux俱乐部](https://github.com/lcpu-club)的Arch Linux龙芯移植工作的方式。

# 前言

Loong Arch Linux是Arch Linux的龙芯移植版本，目前龙芯Linux社区较普遍地认为，为龙芯Linux生态圈维护一个滚动更新的Arch Linux发行版具有重要意义，目前[北京大学Linux俱乐部](https://github.com/lcpu-club)已经接手维护。

由于社区维护力量较为有限，Loong Arch Linux将会尽可能地实现**上游化**，来减少维护工作量。

# 预备工作

## 基本条件

本文默认读者至少已经满足以下**条件中的一个**（建议读者预先大致阅读笔者的另一篇博客[在x86设备上跨架构构建LoongArch的Arch Linux软件包](https://wszqkzqk.github.io/2024/08/08/devtools-loong64/)）：

1. 拥有**原生**的**龙芯编译机器**，或者**可以运行LoongArch的QEMU System虚拟机**
2. 拥有**任意**架构的64位设备且可以在设备上运行对应架构支持的**Arch Linux操作系统或者容器**
  * 例如x86_64的官方Arch Linux、x86_64的其他Linux发行版中的Arch Linux容器、WSL2中的Arch Linux等
  * 例如aarch64的Arch Linux ARM、aarch64的其他Linux发行版中的Arch Linux ARM容器等

如果对本文中涉及的某些基本概念不熟悉，可以参考[ArchWiki](https://wiki.archlinux.org/)。

## 环境准备

### 文件系统

使用`devtools`构建软件包在每次构建时都会创建一个干净的chroot环境，该工具对Btrfs的快照进行了适配，创建新的chroot环境时会使用Btrfs的快照功能快速根据存放基本chroot环境的子卷创建新的chroot环境。因此，**建议使用Btrfs文件系统**。

### 导入PGP Key

Loong Arch Linux移植签名所用的PGP密钥并不在Arch Linux的`archlinux-keyring`密钥环中，因此需要导入签名密钥。

目前笔者打包了[北京大学Linux俱乐部](https://github.com/lcpu-club)Arch Linux用户组的密钥环[`archlinux-lcpu-keyring`](https://github.com/lcpu-club/archlinux-lcpu-keyring)。但这一软件包尚未上传到AUR，可以通过以下方式安装：

```bash
git clone https://github.com/lcpu-club/archlinux-lcpu-keyring.git
cd archlinux-lcpu-keyring
makepkg -si
```

### 安装[`devtools-loong64`](https://github.com/lcpu-club/devtools-loong)

笔者已经打包了`devtools-loong64`工具，并上传到了AUR，可以直接从AUR中安装：

```bash
paru -S devtools-loong64
```

对于在容器中运行x86_64 Arch Linux的用户，还需要参考笔者在另一篇博客中的[`binfmt_misc` FLAGS说明](https://wszqkzqk.github.io/2024/08/08/devtools-loong64/#binfmt_misc-flags说明仅针对在容器中运行x86-arch-linux的用户)一节进行设置。其他用户可以忽略。

# 维护仓库

我们的补丁维护仓库位于[GitHub lcpu-club/loongarch-packages](https://github.com/lcpu-club/loongarch-packages)下，每个需要额外patch的软件包都有一个对应于包名的目录。该目录仅用于存放patch或龙芯特有的配置文件,**不直接存放`PKGBUILD`或上游软件源代码文件**。

* `loong.patch`是主要针对`PKGBUILD`的patch文件
  * 也可能包含其他Arch Linux**官方**软件包仓库**git跟踪**的文件
    * **不推荐**
    * 如果直接修改非`PKGBUILD`的git跟踪文件将必然需要修改`PKGBUILD`的checksum数组
      * 上游更新后容易在`loong.patch`应用时带来冲突
    * 建议额外维护一个对应的`.diff`文件，在`PKGBUILD`中应用
* 其他文件则可能是针对软件包的其他patch文件或者特别适用于龙芯的的配置文件，须添加在`PKGBUILD`的`source`数组中
* 目前（自2024.12.17）`devtools-loong64 >= 1.3.0.patch3-1`已集成补丁导出工具`export-loong64-patches`。以上内容，包括`loong.patch`和其他补丁，均应当由`export-loong64-patches`自动导出。

## 特殊情况

* 本部分是为了简化维护而特别设计的，如果初学者不理解这部分内容，可以跳过，几篇文档都看完以后会理解的（）

部分软件包由于补丁内容非常一致、简单，而且有大量的软件包系统性地需要这些补丁，在这种时候，我们为了简洁与维护方便，并没有创建这些软件包的补丁维护目录。目前的这样特殊情况主要分为两种：

* 特殊情况1：`config.sub`和`config.guess`
  * 开发不活跃的软件`config.sub`和`config.guess`过旧，需要更新才能在龙芯平台上正常构建
  * **仅**需要更新`config.sub`和`config.guess`而**不用其他任何修改**就能成功构建
* 特殊情况2：使用`cargo fetch`的软件包的架构指定问题
  * `cargo fetch`在`PKGBUILD`中使用了硬编码的`x86_64`，需要替换为`uname -m`（`loongarch64`）
  * `cargo fetch`在`PKGBUILD`中使用了`$CARCH`（在本发行版是`loong64`），需要替换为`uname -m`（`loongarch64`）
* 对于这些特殊情况，我们的包拉取工具`get-loong64-pkg`（`devtools-loong64 >= 1.3.0.patch3-1`）会自动处理，因此不需要单独维护补丁

## 补丁维护原则

本项目始终以上游化为目标，因此我们的软件包构建过程中，**尽量**不对软件包进行patch；对于共性问题，应当视具体情况提交到**软件上游**或者**Arch Linux上游**。但是，由于龙芯平台的特殊性，有些软件包可能不可避免地需要patch才能在龙芯平台上正常运行,而上游可能并不能够及时接收这些修复，此时我们不得不在我们的[补丁维护仓库](https://github.com/lcpu-club/loongarch-packages)中**暂时**维护patch。

因此对这两种特殊情况：

* 特殊情况1：如果没有对应的补丁，但软件包名在`update_config`文件中，需要对`PKGBUILD`进行修改
  * 需要对`config.sub`和`config.guess`进行更新
* 特殊情况2：如果没有对应的补丁，但软件包使用`cargo fetch`，需要将`$CARCH`替换为`uname -m`，并且将
  * 硬编码的`x86_64`也要替换为`uname -m`

# 工作流程

## 构建及测试流程示例

我们以`erofs-utils`软件包为例，展示如何构建和测试软件包。

### 获取软件包

目前（自2024.12.17）`devtools-loong64 >= 1.3.0.patch3-1`已集成获取软件包的工具`get-loong64-pkg`，可以直接使用，详细使用方法可以运行`get-loong64-pkg -h`查看。该工具可以自动从Arch Linux官方仓库**拉取**构建文件，**自动同步更新**，**切换**到相应的版本，并**自动应用**我们的补丁集中维护的**补丁**。需要注意的是，传递的参数是`pkgbase`，而不是`pkgname`。

```bash
get-loong64-pkg erofs-utils
```

### 构建尝试

切换到克隆下来的示例软件包目录：

```bash
cd erofs-utils
```

一般来说，软件包的构建命令是`extra-loong64-build`。由于原软件包`PKGBUILD`是针对x86_64的，其`arch`数组并不包含`loong64`，未经修改并不能够直接用无参数的`extra-loong64-build`构建。虽然说修改`arch`数组也可以算是需要针对`PKGBUILD`的patch，但是我们默认在我们的移植中，所有`arch`字段不为`any`的软件包的`arch`字段都应该包含`loong64`，因此对`arch`的修改**不应当**出现在维护的patch中。

对此，我们可以有两种选择，一种是先修改`PKGBUILD`，将`loong64`添加到`arch`数组中，然后再使用`extra-loong64-build`构建（如果需要导出补丁则需要改回来，不推荐）。

为了避免麻烦，我们推荐向`extra-loong64-build`传递参数来解决问题：

* `extra-loong64-build`参数组中在`--`后的参数会传递给`makechrootpkg`，而`makechrootpkg`参数组中在`--`后的参数会传递给`makepkg`
* `makepkg`的`-A`参数表示忽略`arch`字段不兼容的情况以便继续构建

因此，我们推荐使用以下命令构建：

```bash
extra-loong64-build -- -- -A
```

* 如果需要`core-testing`和`extra-testing`中的包，请使用`extra-testing-loong64-build`。
* 如果需要`core-staging`和`extra-staging`中的包，请使用`extra-staging-loong64-build`。
  * ~~目前（2024.09.05）我们的工作进度**仍存放于`testing`与`staging`中**~~
  * ~~如果要针对最新的维护状况构建，请使用**`extra-testing-loong64-build`**或者`extra-staging-loong64-build`~~
  * 目前我们只跟进Arch Linux官方的`core`和`extra`仓库，因此**一般只使用`extra-loong64-build`**

#### 首次构建可能问题

首次运行时，程序会在`/var/lib/archbuild/`下创建目录`extra-loong64`，如果是Btrfs文件系统，会在`extra-loong64`下创建一个名为`root`的子卷，用于存放LoongArch Linux的基本chroot环境，在后续每次运行构建时，将会对这一子卷中的环境进行升级同步，并创建一个新的快照子卷进行构建。（其他文件系统则是创建普通目录、复制目录）

此时如果在同步数据库阶段就提示PGP签名错误，可能是因为没有导入PGP密钥，请自行检查软件包`archlinux-lcpu-keyring`是否[正常安装](#导入pgp-key)。如果仅有下载的部分软件包提示签名校验失败，可能是网络问题，重试即可。首次运行无论是否失败，均会在`/var/lib/archbuild/extra-loong64`下创建一个名为`root`的子卷，如果创建并没有成功，在重试时会提示该路径并非Arch Linux的chroot环境，此时请运行`extra-loong64-build -c`清理环境，然后再次运行。

#### 构建成功后

构建成功后，在原构建仓库目录下会生成`*.pkg.tar.zst`软件包文件，即为构建成功的软件包；`*.log`为各项构建过程的日志。更详细的编译日志则是在`/var/lib/archbuild/extra-loong64/$USER/build/`下。

如果读者是北京大学Linux俱乐部Arch Linux用户组的成员且在`archlinux-lcpu-keyring`中有签名密钥，可以手动对软件包进行签名：

```bash
for file in *.pkg.tar.zst
do
  gpg --detach-sign --use-agent "$file"
done
```

软件包的测试可以使用龙芯物理机、`qemu-system-loongarch64`虚拟机、使用QEMU User Mode Emulation的龙芯容器等方式进行，具体方法不再赘述。

### patch导出流程

之前列出的软件包`erofs-utils`较为简单，不需要额外修复就能直接构建，然而仍然存在大量的软件包需要开发者进行一些修复适配（修复遇到困难可以查看笔者提供的[软件包修复构建的相关指引](https://wszqkzqk.github.io/2024/08/22/loongarchlinux-port-tips/)）。

对于需要patch适配的软件包，开发者在适配完成并进行构建和验证后，需要将适配的patch导出，添加到我们的[补丁维护仓库](https://github.com/lcpu-club/loongarch-packages)中。

导出的内容包括针对`PKGBUILD`的patch和软件包的其他patch或特别适用于龙芯的配置文件。除了`loong.patch`外，其他需要用到的patch文件或者其他配置应当注意添加到`PKGBUILD`中的`source`数组中，并且更新好`PKGBUILD`中的哈希值，具体操作可以参考ArchWiki的[PKGBUILD条目](https://wiki.archlinux.org/title/PKGBUILD)。

此外其他文件应当尽可能地**命名得更具体**，以便于其他开发者理解。

目前（自2024.12.17）`devtools-loong64 >= 1.3.0.patch3-1`已集成补丁导出工具`export-loong64-patches`，可以直接使用，详细使用方法可以运行`export-loong64-patches -h`查看。该工具可以自动导出软件包的patch，**不需要**手动导出。运行以下命令，可以将补丁导出到`loong64-patches`目录下：

```bash
export-loong64-patches
```

> 这个脚本的逻辑是：
>
> 1. 将软件包目录下`git diff`的结果写入`loong.patch`
>   * 即对上游git仓库已跟踪文件的修改，一般为`PKGBUILD`的修改
> 2. 查找需要复制的其他文件
>   * 需要复制的文件一定在`PKGUILD`的`source`数组中
>   * 需要复制的文件一定在本地存在
>   * 需要复制的文件一定不在Arch Linux官方软件包git仓库的跟踪文件中
>   * 同时满足以上三个条件的文件一定需要复制，为充要条件
> 3. 对`PKGBUILD`的`pkgrel`字段的小版本号进行忽略
>   * `pkgrel`字段的小版本号是我们在维护时用于版本控制的，不应当导出到patch中
>   * patch中不能包含对`pkgver`和`pkgrel`的修改

对于导出的补丁，需要注意[补丁维护原则](#补丁维护原则)中列出的特殊情况：
* 如果patch文件**仅包含**对`config.sub`和`config.guess`的更新，不需要额外维护`loong.patch`，而是将包名添加到`update_config`文件中
  * 有关添加到`update_config`文件后的自动处理流程是否能够解决问题，可以预先使用以下命令验证：
    ```bash
    sed -i '/^build()/,/configure/ {/^[[:space:]]*cd[[:space:]]\+/ { s/$/\n  for c_s in $(find -type f -name config.sub -o -name configure.sub); do cp -f \/usr\/share\/automake-1.1?\/config.sub "$c_s"; done\n  for c_g in $(find -type f -name config.guess -o -name configure.guess); do cp -f \/usr\/share\/automake-1.1?\/config.guess "$c_g"; done/; t;};}' "PKGBUILD"
    ```
    * 如果能够解决问题，就不要单独维护`loong.patch`

# 软件包的手动上传

参见[龙芯Arch Linux移植技巧 #软件包的手动上传](https://wszqkzqk.github.io/2024/08/22/loongarchlinux-port-tips/#软件包的手动上传)一节

# 更多阅读材料

* [ArchWiki](https://wiki.archlinux.org/)
* [Arch Linux Packaging Standards](https://wiki.archlinux.org/title/Arch_packaging_standards)
* [Arch RISC-V Port Wiki](https://github.com/felixonmars/archriscv-packages/wiki)
* [在x86设备上跨架构构建LoongArch的Arch Linux软件包](https://wszqkzqk.github.io/2024/08/08/devtools-loong64/)
* [Arch RISC-V Port Wiki - 我们的工作习惯](https://github.com/felixonmars/archriscv-packages/wiki/%E6%88%91%E4%BB%AC%E7%9A%84%E5%B7%A5%E4%BD%9C%E4%B9%A0%E6%83%AF)
* [Arch RISC-V Port Wiki - 完全新人指南](https://github.com/felixonmars/archriscv-packages/wiki/%E5%AE%8C%E5%85%A8%E6%96%B0%E4%BA%BA%E6%8C%87%E5%8D%97)
* [北京大学Linux俱乐部Arch Linux for Loongarch64项目维护网页](https://loongarchlinux.lcpu.dev/)
* [北京大学Linux俱乐部Arch Linux for Loongarch64项目 - 构建状态列表](https://loongarchlinux.lcpu.dev/status)
* [原Loong Arch Linux项目](https://github.com/loongarchlinux)
* 可能的补丁参考源：[AOSC Code Tracking Project](https://github.com/AOSC-Tracking)
* 可能的补丁参考源：[Gentoo/Loongson Support Overlay](https://github.com/xen0n/loongson-overlay)
* [龙芯Arch Linux移植技巧 by wszqkzqk](https://wszqkzqk.github.io/2024/08/22/loongarchlinux-port-tips/)
* [利用本地仓库实现有依赖关系的软件包的顺序构建 by wszqkzqk](https://wszqkzqk.github.io/2024/09/19/build-order-local-repo/)
* [Loong Arch Linux维护中可能用到Bootstrap构建方法 by wszqkzqk](https://wszqkzqk.github.io/2024/11/20/Loong-Arch-Linux-Bootstrap-Packages/)
* [LoongArch介绍 — The Linux Kernel documentation](https://www.kernel.org/doc/html/latest/translations/zh_CN/arch/loongarch/introduction.html)
* [LoongArch 指令集架构的文档](https://github.com/loongson/LoongArch-Documentation/releases/latest/download/LoongArch-Vol1-v1.10-CN.pdf)
