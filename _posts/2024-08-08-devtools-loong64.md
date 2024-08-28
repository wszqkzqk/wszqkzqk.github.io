---
layout:     post
title:      在x86设备上跨架构构建龙芯的Arch Linux软件包
subtitle:   devtools-loong64的应用
date:       2024-08-08
author:     wszqkzqk
header-img: img/bg-sunrise.webp
catalog:    true
tags:       系统配置 系统维护 开源软件 Linux archlinux 国产硬件 虚拟化
---

# 前言

Arch Linux主要使用devtools来构建软件包。为了方便拥有x86_64设备的开发者构建LoongArch的软件包，笔者制作了一个[`devtools-loong64`](https://github.com/lcpu-club/devtools-loong)的[AUR软件包](https://aur.archlinux.org/packages/devtools-loong64)，可以在龙芯或者x86_64设备上构建LoongArch的软件包。

# 特点

相比于原来的`devtools`龙芯移植，`devtools-loong64`保留了Arch Linux官方原版的`devtools`作为依赖，通过patch的方式增加了部分LoongArch专属的文件，简化了维护的潜在工作量。

在x86_64平台上，`devtools-loong64`还依赖`qemu-user-static`软件包，以便在x86_64平台上使用QEMU用户模式模拟LoongArch的环境。通过在binfmt_misc的注册中额外添加`C`标志，`devtools-loong64`可以在x86_64平台上构建LoongArch的软件包，[并避免了QEMU binfmt下的提权问题](https://wszqkzqk.github.io/2024/03/28/qemu-user-binfmt-flag/)。

# 准备工作

## 文件系统

使用devtools构建软件包在每次构建时都会创建一个干净的chroot环境，该工具对Btrfs的快照进行了适配，创建新的chroot环境时会使用Btrfs的快照功能快速根据存放基本chroot环境的子卷创建新的chroot环境。因此，建议使用Btrfs文件系统。

## PGP Key的导入

由于目前的LoongArchLinux移植主要由龙芯的武老师维护，签名所用的PGP密钥并不在Arch Linux的`archlinux-keyring`密钥环中，因此需要导入签名密钥。以下导入方法**二选一**即可。

### 安装[`archlinux-lcpu-keyring`](https://github.com/lcpu-club/archlinux-lcpu-keyring)

目前笔者打包了[北京大学Linux俱乐部](https://github.com/lcpu-club)Arch Linux用户组的密钥环[`archlinux-lcpu-keyring`](https://github.com/lcpu-club/archlinux-lcpu-keyring)，其中包含了武老师的PGP密钥。但这一软件包尚未上传到AUR，可以通过以下方式安装：

```bash
git clone https://github.com/lcpu-club/archlinux-lcpu-keyring.git
cd archlinux-lcpu-keyring
makepkg -si
```

### 直接导入

也可以直接导入武老师的PGP密钥：

```bash
sudo pacman-key --recv-keys 65D4986C7904C6DBF2C4DD9A4E4E02B70BA5C468
sudo pacman-key --lsign-key 65D4986C7904C6DBF2C4DD9A4E4E02B70BA5C468
```

## 安装`devtools-loong64`

从AUR中安装`devtools-loong64`软件包：

```bash
paru -S devtools-loong64
```

### `binfmt_misc` FLAGS说明（仅针对在容器中运行x86 Arch Linux的用户）

* 只要**不是**在容器中运行x86 Arch Linux的用户，`devtools-loong64`完全**开箱即用**，可以**忽略**这一部分，请**继续阅读[测试打包](#测试打包)**一节
* 更多知识介绍见笔者的另一篇博客：[`binfmt_misc` flags与QEMU用户模式下的跨架构构建环境](https://wszqkzqk.github.io/2024/03/28/qemu-user-binfmt-flag/)
* 无论如何**宿主**都需要安装**`qemu-user-static`**软件包

笔者打包的`devtools-loong64`软件包在x86平台上使用QEMU用户模式模拟LoongArch的环境，笔者附加了`z-qemu-loong64-static-for-archpkg.conf`这一文件，该文件在`/usr/lib/binfmt.d/`下，特意以`z`开头以便最后注册`qemu-loong64-static`的binfmt_misc规则，附加了`C`标志，以避免QEMU binfmt下的提权问题。

需要注意的是，该软件包添加这一文件是假设用户的宿主环境是直接运行于x86（物理机或完整的虚拟机）上的Arch Linux系统，必须要有独立的内核。因为`z-qemu-loong64-static-for-archpkg.conf`这一文件涉及对内核的`binfmt_misc`的注册。

因此对于将打包所用到的x86的Arch Linux环境运行在`systemd-nspawn`等**容器**中的用户（其他发行版用户想进行测试时可能有这一需求），如果将`devtools-loong64`安装在了容器内而非宿主上，这一注册并不能够自动进行。在这种情况下，用户可以在以下方法中选择一种执行。

#### 在宿主系统QEMU的binfmt注册文件中添加`C`标志

* 注册文件一般在`/usr/lib/binfmt.d/`下，binfmt的注册一般由`systemd-binfmt.service`负责
* 注册文件一般为`/usr/lib/binfmt.d/qemu-loongarch64-static.conf`，不同发行版可能有所不同

例如，原本的注册文件内容为：

```conf
:qemu-loongarch64:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x02\x01:\xff\xff\xff\xff\xff\xff\xff\xfc\x00\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/usr/bin/qemu-loongarch64-static:FP
```

添加`C`标志到末尾后为：

```conf
:qemu-loongarch64:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x02\x01:\xff\xff\xff\xff\xff\xff\xff\xfc\x00\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/usr/bin/qemu-loongarch64-static:FPC
```

#### 临时手动在**宿主**环境下注册binfmt规则

手动注册binfmt规则的方法可以仅在需要时启用binfmt的调用者的凭证，不需要时默认禁用，运行完成后也可以手动禁用，理论上可能会更加安全。

假设宿主存在注册文件，为`/usr/lib/binfmt.d/qemu-loongarch64-static.conf`，执行命令：

```bash
echo -1 | sudo tee /proc/sys/fs/binfmt_misc/qemu-loongarch64 && echo "$(cat /usr/lib/binfmt.d/qemu-loongarch64-static.conf)C" | sudo tee /proc/sys/fs/binfmt_misc/register
```

以便重新注册`qemu-loongarch64`的binfmt规则，并添加`C`标志。

同理，如果想恢复原状，禁用`C`标志，可以执行：

```bash
echo -1 | sudo tee /proc/sys/fs/binfmt_misc/qemu-loongarch64 && cat "/usr/lib/binfmt.d/qemu-loongarch64-static.conf" | sudo tee /proc/sys/fs/binfmt_misc/register
```

如果宿主仅安装了`qemu-user-static`软件包，却没有安装`qemu-user-static-binfmt`软件包，可能不存在`/usr/lib/binfmt.d/qemu-loongarch64-static.conf`这一文件，此时需要指定完整的注册规则，例如：

```bash
echo -1 | sudo tee /proc/sys/fs/binfmt_misc/qemu-loongarch64 && echo ":qemu-loongarch64:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x02\x01:\xff\xff\xff\xff\xff\xff\xff\xfc\x00\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/usr/bin/qemu-loongarch64-static:FPC" | sudo tee /proc/sys/fs/binfmt_misc/register
```

* 为了方便，可以自行编写脚本，以便实现在启动容器时自动注册binfmt规则

#### 测试`binfmt_misc`注册结果

执行以下命令，观察输出中`flags`的内容是否含有`C`标志：

```bash
cat /proc/sys/fs/binfmt_misc/qemu-loongarch64
```

如果输出中含有`flags: POCF`，则表明目前已经启用了`C`标志；如果仅含有`flags: PF`，则表明目前没有启用`C`标志，后续的构建过程将会出现提权问题：

```log
sudo: effective uid is not 0, is /usr/bin/sudo on a file system with the 'nosuid' option set or an NFS file system without root privileges?
==> ERROR: 'pacman' failed to install missing dependencies.
```

这一报错极具迷惑性，实际上如果`binfmt_misc`的标志没有设置正确，无论文件系统、挂载参数如何都会提示这一错误。如果在实际构建过程中出现了如上问题，可以通过[本节内容](#binfmt_misc-flags说明仅针对在容器中运行x86-arch-linux的用户)中的方法解决。

# 测试打包

## PKGBUILD的获取

准备工作完成后，可以准备一个包含PKGBUILD的软件包进行测试，PKGBUILD可以自己通过`pkgctl repo clone xxx`下载并自行移植，也可以从目前武老师维护的[LoongArch Linux仓库](https://github.com/loongarchlinux/)中获取。如果是新手第一次测试，不熟悉PKGBUILD的编写，建议从LoongArch Linux仓库的[core](https://github.com/loongarchlinux/core)或者[extra](https://github.com/loongarchlinux/extra)中选择一个简单的软件包进行测试。

## 首次运行

首先，进入软件包的目录，然后进行构建：

```bash
extra-loong64-build
```

首次运行时，程序会在`/var/lib/archbuild/`下创建目录`extra-loong64`，如果是Btrfs文件系统，会在`extra-loong64`下创建一个名为`root`的子卷，用于存放LoongArch Linux的基本chroot环境，在后续每次运行构建时，将会对这一子卷中的环境进行升级同步，并创建一个新的快照子卷进行构建。（其他文件系统则是创建普通目录、复制目录）

此时如果在同步数据库阶段就提示PGP签名错误，可能是因为没有导入PGP密钥，请自行按照上文[PGP签名的导入](#PGP签名的导入)一节进行检查。如果仅有下载的部分软件包提示签名校验失败，可能是网络问题，重试即可。首次运行无论是否失败，均会在`/var/lib/archbuild/extra-loong64`下创建一个名为`root`的子卷，如果创建并没有成功，在重试时会提示该路径并非Arch Linux的chroot环境，此时请运行`extra-loong64-build -c`清理环境，或者手动删除`/var/lib/archbuild/extra-loong64`下的所有子卷以及`/var/lib/archbuild/extra-loong64`目录本身，然后再次运行。

当基本的chroot环境创建成功后，后续的构建均无需从头创建环境，应该能够顺利进行。

# 其他注意事项

## 构建期间的PGP签名问题

许多软件包在PKGBUILD中会指明需要验证PGP签名，如果在构建时没有导入相应的PGP密钥，会导致构建失败。这一问题较为复杂，目前有以下几种解决方案：

1. 在**宿主机**的`~/.gnupg/gpg.conf`中添加`auto-key-retrieve`选项，这样在构建时会自动从密钥服务器下载PGP密钥。
   * 缺点是某一特定的PGP服务器上可能没有相应的密钥
   * 可以考虑多添加几个PGP服务器
2. 一般来说，软件包的PGP密钥会在软件包`keys`子目录下提供，可以在构建前从`keys`中导入密钥
   * 缺点是`keys`下的密钥一般是`devtools`的`export-pkgbuild-keys`自动导出的，可能会有一些问题
3. 考虑到Arch Linux官方上游会对软件包的PGP密钥进行验证，而在我们的构建环境中使用hash验证已经可以基本保证源的完整性与可靠性，因此我们可以考虑在构建流程中**跳过**PGP验证
   * `extra-loong64-build`参数组中在`--`后的参数会传递给`makechrootpkg`，而`makechrootpkg`参数组中在`--`后的参数会传递给`makepkg`
   * 因此使用`extra-loong64-build -- -- --skippgpcheck`可以跳过PGP验证

## QEMU的性能问题

在QEMU适配龙芯的LSX指令集后，QEMU的性能似乎出现了严重下降（适配了LSX指令集的QEMU 9.0似乎性能比没有适配LSX的QEMU 8.0差）：

| 运行环境[^1] | 7z Compression/MIPS | 7z Decompression/MIPS |
| ----        | ----                | ----                  |
| x86原生     | 47307 (100%)         | 57979 (100%)         |
| QEMU 8.0.0, 2023.05 | 16295 (34%)  | 21927 (38%)          |
| QEMU 9.0.2, 2024.08 | **10699 (23%)** | **12492 (22%)**   |
| Longsoon 3A6000 | 19295 (41%)      | 19295 (33%)          |

考虑到当前QEMU下16线程的多核性能都明显不如龙芯3A6000，单线程性能更是远远落后，因此在构建时可能会出现性能瓶颈，导致打包耗时较长。

[^1]: x86原生及QEMU测试所用的CPU为AMD Ryzen 7 5800H (16) @ 4.46 GHz，所用的软件为`p7zip`，测试命令为`7z b`，表中列出的是多线程性能。

## 维护参与

欢迎大家参与北京大学Linux俱乐部的[LoongArch Linux移植工作](https://github.com/lcpu-club/loongarch-packages)！
