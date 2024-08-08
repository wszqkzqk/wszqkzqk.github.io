---
layout:     post
title:      在x86设备上跨架构构建LoongArch的Arch Linux软件包
subtitle:   devtools-loong64的应用
date:       2024-08-08
author:     wszqkzqk
header-img: img/bg-sunrise.webp
catalog:    true
tags:       系统配置 系统维护 开源软件 Linux archlinux 国产硬件 虚拟化
---

## 前言

Arch Linux主要使用devtools来构建软件包。为了方便拥有x86设备的开发者构建LoongArch的软件包，笔者制作了一个[`devtools-loong64`](https://github.com/lcpu-club/devtools-loong)的[AUR软件包](https://aur.archlinux.org/packages/devtools-loong64)，可以在龙芯或者x86设备上构建LoongArch的软件包。

## 特点

相比于原来的`devtools`龙芯移植，`devtools-loong64`保留了Arch Linux官方原版的`devtools`作为依赖，通过patch的方式增加了部分LoongArch专属的文件，简化了维护的潜在工作量。

在x86平台上，`devtools-loong64`还依赖`qemu-user-static`软件包，以便在x86平台上使用QEMU用户模式模拟LoongArch的环境。通过在binfmt_misc的注册中额外添加`C`标志，`devtools-loong64`可以在x86平台上构建LoongArch的软件包，并避免了binfmt下的提权问题。

## 准备工作

### 文件系统

使用devtools构建软件包在每次构建时都会创建一个干净的chroot环境，该工具对Btrfs的快照进行了适配，创建新的chroot环境时会使用Btrfs的快照功能快速根据存放基本chroot环境的子卷创建新的chroot环境。因此，建议使用Btrfs文件系统。

### PGP签名的导入

由于目前的LoongArchLinux移植主要由龙芯的武老师维护，签名所用的PGP密钥并不在Arch Linux的`archlinux-keyring`密钥环中，因此需要导入武老师的PGP密钥：

```bash
sudo pacman-key --recv-keys 65D4986C7904C6DBF2C4DD9A4E4E02B70BA5C468
sudo pacman-key --lsign-key 65D4986C7904C6DBF2C4DD9A4E4E02B70BA5C468
```

目前[北京大学Linux俱乐部](https://github.com/lcpu-club)计划在未来的LoongArch Linux移植中使用独立的`archlinux-lcpu-keyring`密钥环，因此在未来可能可以直接通过安装`archlinux-lcpu-keyring`密钥环来导入密钥。

### 安装`devtools-loong64`

从AUR中安装`devtools-loong64`软件包：

```bash
paru -S devtools-loong64
```

## 测试打包

### PKGBUILD的获取

准备工作完成后，可以准备一个包含PKGBUILD的软件包进行测试，PKGBUILD可以自己通过`pkgctl repo clone xxx`下载并自行移植，也可以从目前武老师维护的[LoongArch Linux仓库](https://github.com/loongarchlinux/)中获取。如果是新手第一次测试，不熟悉PKGBUILD的编写，建议从LoongArch Linux仓库的[core](https://github.com/loongarchlinux/core)或者[extra](https://github.com/loongarchlinux/extra)中选择一个简单的软件包进行测试。

### 首次运行

首先，进入软件包的目录，然后进行测试构建：

```bash
extra-loong64-build
```

首次运行时，程序会在`/var/lib/archbuild/`下创建目录`extra-loong64`，如果是Btrfs文件系统，会在`extra-loong64`下创建一个名为`root`的子卷，用于存放LoongArch Linux的基本chroot环境，在后续每次运行构建时，将会对这一子卷中的环境进行升级同步，并创建一个新的快照子卷进行构建。（其他文件系统则是创建普通目录、复制目录）

此时如果在同步数据库阶段就提示PGP签名错误，可能是因为没有导入PGP密钥，请自行按照上文[PGP签名的导入](#PGP签名的导入)一节进行检查。如果仅有下载的部分软件包提示签名校验失败，可能是网络问题，重试即可。首次运行无论是否失败，均会在`/var/lib/archbuild/extra-loong64`下创建一个名为`root`的子卷，如果创建并没有成功，在重试时会提示该路径并非Arch Linux的chroot环境，此时请手动删除`/var/lib/archbuild/extra-loong64`下的所有子卷以及`/var/lib/archbuild/extra-loong64`目录本身，然后再次运行。

当基本的chroot环境创建成功后，后续的构建均无需从头创建环境，应该能够顺利进行。

## 其他注意事项

### 构建期间的PGP签名问题

许多软件包在PKGBUILD中会指明需要验证PGP签名，如果在构建时没有导入相应的PGP密钥，会导致构建失败。这一问题较为复杂，目前有以下几种解决方案：

1. 在**宿主机**的`~/.gnupg/gpg.conf`中添加`auto-key-retrieve`选项，这样在构建时会自动从密钥服务器下载PGP密钥。
   * 缺点是某一特定的PGP服务器上可能没有相应的密钥
   * 可以考虑多添加几个PGP服务器
2. 一般来说，软件包的PGP密钥会在软件包`keys`子目录下提供，可以在构建前从`keys`中导入密钥
   * 缺点是`keys`下的密钥一般是`devtools`的`export-pkgbuild-keys`自动导出的，可能会有一些问题
3. 考虑到Arch Linux官方上游会对软件包的PGP密钥进行验证，而在我们的构建环境中使用hash验证已经可以基本保证源的完整性与可靠性，因此我们可以考虑在构建流程中**跳过**PGP验证
   * `extra-loong64-build`参数组中在`--`后的参数会传递给`makechrootpkg`，而`makechrootpkg`参数组中在`--`后的参数会传递给`makepkg`
   * 因此使用`extra-loong64-build -- --skippgpcheck`可以跳过PGP验证

### QEMU的性能问题

在QEMU适配龙芯的LSX指令集后，QEMU的性能似乎出现了严重下降（适配了LSX指令集的QEMU 9.0似乎性能比没有适配LSX的QEMU 8.0差），可能会导致目前打包耗时较长。
