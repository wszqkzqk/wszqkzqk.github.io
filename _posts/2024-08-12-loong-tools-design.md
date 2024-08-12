---
layout:     post
title:      LoongArch的Arch Linux移植工作流程
subtitle:   Loong Arch Linux软件包开发者维护工具设计
date:       2024-08-12
author:     wszqkzqk
header-img: img/bg-sunrise.webp
catalog:    true
tags:       系统配置 系统维护 开源软件 Linux archlinux 国产硬件 虚拟化
---

* 注：在近期，本文内容可能会随着北京大学Linux俱乐部的内部讨论而发生变化

本文将介绍目前笔者规划的LoongArch的Arch Linux移植的**最小**维护架构（**不包括**CI工具）和参与[北京大学Linux俱乐部](https://github.com/lcpu-club)的Arch Linux龙芯移植工作的可能方式。但是目前笔者尚未完成完善的开发者维护工具，欢迎大家帮助开发，写出更加方便、易用、完善的工具。

# 前言

Loong Arch Linux是Arch Linux的龙芯移植版本，目前龙芯Linux社区较普遍地认为，为龙芯Linux生态圈维护一个滚动更新的Arch Linux发行版具有重要意义，目前[北京大学Linux俱乐部](https://github.com/lcpu-club)有计划接手维护。

由于社区维护力量较为有限，Loong Arch Linux将会尽可能地实现上游化，来减少维护工作量。

# 预备工作

## 基本条件

本文默认读者至少已经满足以下**两个条件中的一个**：

1. 拥有x86_64设备且可以在设备上运行x86_64的Arch Linux操作系统或者容器
2. 拥有原生的龙芯编译机器

如果对本文中涉及的某些基本概念不熟悉，可以参考[ArchWiki](https://wiki.archlinux.org/)。

## 环境准备

### 文件系统

使用`devtools`构建软件包在每次构建时都会创建一个干净的chroot环境，该工具对Btrfs的快照进行了适配，创建新的chroot环境时会使用Btrfs的快照功能快速根据存放基本chroot环境的子卷创建新的chroot环境。因此，**建议**使用Btrfs文件系统。

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

对于在容器中运行x86_64 Arch Linux的用户，还需要参考笔者在另一篇博客中的[`binfmt_misc` FLAGS说明](/2024/08/08/devtools-loong64/#binfmt_misc-flags说明仅针对在容器中运行x86-arch-linux的用户)一节进行设置。其他用户可以忽略。

# 维护仓库

* **TODO:** 补丁维护仓库结构待议

我们的补丁维护仓库位于[GitHub lcpu-club/loongarch-packages](https://github.com/lcpu-club/loongarch-packages)下，每个需要额外patch的软件包都有一个对应于包名的目录。

* 该目录仅用于存放patch或龙芯特有的配置文件,**不直接存放`PKGBUILD`等直接用于构建的文件**
* 目录下的`loong.patch`存放的是针对`PKGBUILD`的patch
* 子目录`patches`存放的是其他patch和龙芯特定的配置文件

除了目录外，对于每个软件包，还记录了元数据，包含3个信息：

* 包名
* **上游**版本号，即软件包在Arch Linux官方仓库中的**完整**版本号`$pkgver-$pkgrel`，如`1:1.2.3-1`
* 龙芯移植构建版本号，只能为自然数，如`1`、`2`、`3`等
  * 可被工具在构建时合并到`PKGBUILD`中的`pkgrel`中，得到如`1:1.2.3-1.1`的版本号

# 工作流程

## 不需要patch的软件包构建及测试流程示例

这是最简单的情况，我们以`erofs-utils`软件包为例，展示如何构建和测试软件包。

### 获取软件包

由于Loong Arch Linux的构建需要遵循尽可能上游化的原则，我们的构建与移植需要先获取Arch Linux官方构建仓库。以`erofs-utils`软件包为例，我们可以通过以下命令获取：

```bash
pkgctl repo clone erofs-utils
```

如果报错`Please make sure you have the correct access rights and the repository exists.`，则需要指明使用`https`协议：

```bash
pkgctl repo clone --protocol=https erofs-utils
```

### 构建尝试

切换到克隆下来的示例软件包目录：

```bash
cd erofs-utils
```

一般来说，软件包的构建命令是`extra-loong64-build`。由于原软件包`PKGBUILD`是针对x86_64的，其`arch`数组并不包含`loong64`，未经修改并不能够直接用无参数的`extra-loong64-build`构建。虽然说修改`arch`数组也可以算是需要针对`PKGBUILD`的patch，但是我们默认在我们的移植中，所有`arch`字段不为`any`的软件包的`arch`字段都应该包含`loong64`，因此对`arch`的修改**不应当**出现在维护的patch中。

对此，我们可以有两种选择，一种是先修改`PKGBUILD`，将`loong64`添加到`arch`数组中，然后再使用`extra-loong64-build`构建（如果需要导出补丁则需要改回来）。

为了避免麻烦，我们还可以向`extra-loong64-build`传递参数来解决问题：

* `extra-loong64-build`参数组中在`--`后的参数会传递给`makechrootpkg`，而`makechrootpkg`参数组中在`--`后的参数会传递给`makepkg`
* `makepkg`的`-A`参数表示忽略`arch`字段不兼容的情况以便继续构建

因此，我们可以使用以下命令构建：

```bash
extra-loong64-build -- -- -A
```

#### 首次构建可能问题

首次运行时，程序会在`/var/lib/archbuild/`下创建目录`extra-loong64`，如果是Btrfs文件系统，会在`extra-loong64`下创建一个名为`root`的子卷，用于存放LoongArch Linux的基本chroot环境，在后续每次运行构建时，将会对这一子卷中的环境进行升级同步，并创建一个新的快照子卷进行构建。（其他文件系统则是创建普通目录、复制目录）

此时如果在同步数据库阶段就提示PGP签名错误，可能是因为没有导入PGP密钥，请自行检查软件包`archlinux-lcpu-keyring`是否[正常安装](#导入pgp-key)。如果仅有下载的部分软件包提示签名校验失败，可能是网络问题，重试即可。首次运行无论是否失败，均会在`/var/lib/archbuild/extra-loong64`下创建一个名为`root`的子卷，如果创建并没有成功，在重试时会提示该路径并非Arch Linux的chroot环境，此时请手动删除`/var/lib/archbuild/extra-loong64`下的所有子卷以及`/var/lib/archbuild/extra-loong64`目录本身，然后再次运行。

#### 构建成功

构建成功后，在原构建仓库目录下会生成`*.pkg.tar.zst`软件包文件，即为构建成功的软件包；`*.log`为各项构建过程的日志。更详细的编译日志则是在`/var/lib/archbuild/extra-loong64/$USER/build/`下。

由于这种最简单的情况并不需要patch，这里不需要patch导出流程。

如果读者是北京大学Linux俱乐部Arch Linux用户组的成员且在`archlinux-lcpu-keyring`中有签名密钥，可以手动对软件包进行签名：

```bash
gpg --detach-sign --use-agent *.pkg.tar.zst
```

软件包的测试可以使用龙芯物理机、`qemu-system-loongarch64`虚拟机、使用QEMU User Mode Emulation的龙芯容器等方式进行，具体方法不再赘述。

* **TODO:** 软件包手动上传流程待议

## 需要patch的软件包

本项目始终以上游化为目标，因此我们的软件包构建过程中，尽量不对软件包进行patch；对于共性问题，应当视具体情况提交到软件上游或者Arch Linux上游。但是，由于龙芯平台的特殊性，有些软件包可能不可避免地需要patch才能在龙芯平台上正常运行。

### 概述

需要额外patch的软件包仍然需要从上游拉取Arch Linux官方仓库，然后从我们的补丁维护仓库中获取patch。

* 首先需要将克隆的上游仓库切换到补丁维护仓库对应的元数据中记录的上游版本号
* 然后对`PKGBUILD`应用`loong.patch`
* 将元数据中的龙芯移植构建版本号字段合并到`PKGBUILD`中的`pkgrel`字段中
* 最后将补丁维护仓库对应目录下的`patches`子目录复制到软件包目录下

* **TODO:** 确定结构后的自动化工具
* **TODO:** 开发者修改后的patch导出流程
