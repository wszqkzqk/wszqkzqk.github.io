---
layout:     post
title:      龙芯Arch Linux移植技巧
subtitle:   参与移植工作的注意事项及FAQ
date:       2024-08-22
author:     wszqkzqk
header-img: img/bg-mountain-darken.webp
catalog:    true
tags:       系统配置 系统维护 开源软件 Linux archlinux 国产硬件 虚拟化 龙芯 LoongArchLinux 容器
---

# 需要重新构建的软件

## soname变更

多数时候，如果遇到上游软件包的soname变更，**必须**要重新构建链接到这些库的软件包。

当开发者使用`devtools`/`devtools-loong64`构建软件包时（例如`extra-loong64-build`），会自动运行`checkpkg`来检查soname变化，例如，我们将`llvm`（pkgbase）从`16.0.6-2`升级到`18.1.8-4`，`checkpkg`会输出如下信息：

```bash
......
==> No soname differences for llvm.
usr/lib/libLLVM-16.0.6.so                                     | usr/lib/libLLVM-18.so
usr/lib/libLLVM-16.so                                         <
                                                              > usr/lib/libLLVM.so.18.1
usr/lib/libLTO.so.16                                          | usr/lib/libLTO.so.18.1
usr/lib/libRemarks.so.16                                      | usr/lib/libRemarks.so.18.1
==> Sonames differ in llvm-libs!
libLLVM-16.so=libLLVM-16.so-64                                | libLLVM.so=18.1-64
libLTO.so=16-64                                               | libLTO.so=18.1-64
libRemarks.so=16-64                                           | libRemarks.so=18.1-64
```

* 关注**`==> Sonames differ in <package>!`**之后列出的内容！
* `extra-*-build`默认并不会保存输出到`stderr`的输出，因此日志中**默认不会包含**`checkpkg`的输出。
  * 可以结合`script`命令来保存**全部**的输出，例如：
    ```bash
    script -c "extra-loong64-build -- -- -A" build-log-all.log
    ```

其中给出了发生soname变化的软件包名`llvm-libs`，以及变化的soname：`libLLVM.so`、`libLTO.so`、`libRemarks.so`。

我们可以在获得了变化的soname后，通过`sogrep-loong64`来查找链接到这些库的软件包：

* Bash/Zsh

```bash
for lib in libLLVM.so libLTO.so libRemarks.so
do
    sogrep-loong64 -r all $lib
done | sort | uniq
```

* Fish

```fish
for lib in libLLVM.so libLTO.so libRemarks.so
    sogrep-loong64 -r all $lib
end | sort | uniq
```

这样我们就可以找到需要重新构建的软件包列表。

考虑到一般情况下，同一软件的多个`.so`文件的soname变化是同时发生的，我们有时候也可以通过对软件包查找来获取所有需要重新构建的软件包：

* Bash/Zsh

```bash
for lib in $(find-libprovides <path-to-your-pkg> | sed 's/=.*//g')
do
    sogrep-loong64 -r all $lib
done | sort | uniq
```

* Fish

```fish
for lib in $(find-libprovides <path-to-your-pkg> | sed 's/=.*//g')
    sogrep-loong64 -r all $lib
end | sort | uniq
```

* `find-libprovides`给出的是软件包提供的**所有**soname，包含了没有变化的soname，可能会包含很多不必要的重构
* 很多时候还是需要手动找出需要重构的软件包：
  * 手动找到发生soname变化的`.so`文件
  * 使用`sogrep-loong64`找到链接到这些`.so`文件的软件包
  * 少数情况下还有其他需要重构的软件包

## 构建顺序

### 一般情况

获得了需要重新构建的软件包列表后，我们需要按照依赖关系的顺序来构建这些软件包。目前，肥猫的[`genrebuild`脚本](https://github.com/felixonmars/archlinux-futils/blob/master/genrebuild)可以帮助我们生成构建顺序。

```bash
genrebuild <package1> <package2> ...
```

肥猫的脚本要求传入的参数是软件包名`pkgname`，而不是`pkgbase`，这与我们目前的流程不符。因此，北京大学学生Linux俱乐部的指导老师[Pluto](https://github.com/setarcos/)在[LCPU loongshot](https://github.com/lcpu-club/loongshot)仓库中提供了一个[修改版的`genrebuild`脚本](https://github.com/lcpu-club/loongshot/blob/main/scripts/genrebuild)，接受`pkgbase`作为参数。目前，我们更推荐使用这个修改版的`genrebuild`脚本。

```bash
genrebuild <pkgbase1> <pkgbase2> ...
```

### KDE及Qt软件包

Arch Linux官方维护有专门用于构建KDE及Qt软件包的工具[kde-build](https://gitlab.archlinux.org/archlinux/kde-build)，其中[记录了构建这些软件包的顺序](https://gitlab.archlinux.org/archlinux/kde-build/-/tree/master/package-list)。我们需要按照这一手动维护的顺序来构建这些软件包。

# 一般的Bootstrap方法

## 向`makechrootpkg`传递`-I`参数

在Bootsrap的过程中，往往需要在构建环境中添加一些源中没有的软件包，这可以通过`makechrootpkg`的`-I`参数来实现，而在运行`extra-loong64-build`或者`extra-loong64-build`的时候，可以通过`--`参数来添加传递到`makechrootpkg`的参数。

```bash
cd <package>
extra-loong64-build -- -I <package1> -I <package2> ...
```

## 本地仓库

手动传递`-I`参数往往比较麻烦，推荐参考笔者介绍的[**本地仓库**](https://wszqkzqk.github.io/2024/09/19/build-order-local-repo/)的方法。

# 软件包的上传

在打包完成后，如果具有上传权限，开发者可以将软件包上传。没有处理好依赖或者没有重新构建完所有需要重新构建的软件包时**不应当上传软件包**，或**只能**上传到`extra-staging`或者`core-staging`。（一般来说没有构建完所有需要构建的包时最好**什么源都不要上传**，只有在问题十分复杂，需要多个开发者协作解决时才上传`staging`，否则请参见本文介绍的[**Bootstrap方法**](#一般的Bootstrap方法)或者[**本地仓库**](https://wszqkzqk.github.io/2024/09/19/build-order-local-repo/)的使用，先在本地解决好，再一次性上传~~，当软件包没有依赖和重构建问题时，可以上传到`extra-testing`或者`core-testing`。如果软件包很简单稳定，完全不需要测试，才可以上传到`extra`或者`core`~~。由于我们目前只跟进Arch Linux官方的`extra`和`core`仓库，因此一般也不上传testing仓库。

需要注意的是：

* 如果软件包存在需要一并上传的依赖或者需要重新构建的软件包，应当**一并上传，不要遗漏**
* 不管什么情况，同一个`pkgbase`下（即同一个构建仓库下）的软件包（各个`pkgname`）应当**一并上传，不要遗漏**；哪怕是重新修改PKGBUILD的时候看起来只影响了其中的部分软件包，也应当将**所有**软件包一并上传

我们在[loongshot](https://github.com/lcpu-club/loongshot)中维护了一个上传软件包的工具[loong-repo-add](https://github.com/lcpu-club/loongshot/blob/main/scripts/loong-repo-add)，可以方便地上传软件包。

由于技术限制和安全规定，目前仅在北京大学的校园网环境下才能上传软件包。如果在校外，可以通过北京大学VPN连接校园网后上传软件包。如果无法连接校园网，可以通过其他方式将软件包传给有上传权限的同学，由他们上传（不推荐）；或在仓库中通过PR提交好补丁（尽量附上完整信息），告知校内维护者重新打包（推荐）。

对于有上传权限的开发者，可以**向项目维护者索要服务器的地址和端口**，并添加到`~/.ssh/config`中，默认需要将服务器命名为`loongarchlinux-tier0`。

```config
Host loongarchlinux-tier0
  HostName <server-ip>
  User <username>
  Port <port>
```

使用脚本上传软件包时会自动PGP签名，注意**设置好PGP密钥**，签名所用的密钥应当与在[archlinux-lcpu-keyring](https://github.com/lcpu-club/archlinux-lcpu-keyring)中提交的**一致**。

如果还没有下载软件包上传工具，可以使用以下命令下载：

```bash
curl -O https://raw.githubusercontent.com/lcpu-club/loongshot/main/scripts/loong-repo-add
chmod +x ./loong-repo-add
```

之后即可使用`loong-repo-add`来上传软件包。目前的上传脚本在绝大部分情况下会自动处理好`debug`包的上传，因此务必保证上传的软件包列表**完整无遗漏**（需要包括`debug`包），建议使用通配符`*`来匹配上传软件包，例如：

```bash
./loong-repo-add <repo> /path/to/package/*.pkg.tar.zst
```

其中`<repo>`一般为`extra`或者`core`，如果确实需要上传到`testing`或者`staging`，可以使用`extra-testing`、`core-testing`、`extra-staging`或者`core-staging`。

开发者需要注意检查`core`和`extra`仓库的软件包上传不要混淆。

# 使用QEMU System测试

QEMU User模式下的容器没有自己的内核，显然无法用于内核测试。因此，我们需要在龙芯实体机或者QEMU System模式下进行内核测试（事实上包括但不限于内核）。在实体机下的测试相对比较好理解，这里主要介绍在没有龙芯实体机时使用QEMU System模式测试内核。

在获取或者自己构建了Loong Arch Linux的qcow2镜像后，我们可以使用`qemu-system-loongarch64`来启动虚拟机，例如：

```bash
qemu-system-loongarch64 \
    -m 6G \
    -cpu la464-loongarch-cpu \
    -machine virt \
    -smp 16 \
    -bios ./QEMU_EFI.fd \
    -serial stdio \
    -device virtio-gpu-pci \
    -net nic -net user \
    -device nec-usb-xhci,id=xhci,addr=0x1b \
    -device usb-tablet,id=tablet,bus=xhci.0,port=1 \
    -device usb-kbd,id=keyboard,bus=xhci.0,port=2 \
    -hda <path-to-your-image> \
    -virtfs local,path=<path-to-your-sharing-directory>,mount_tag=host0,security_model=passthrough,id=host0
```

其中：

* `-m 6G`：分配6 GB内存
* `-smp 16`：使用16个CPU核心
* `-bios ./QEMU_EFI.fd`：指定QEMU使用的EFI固件
  * 该固件可以在本项目的`edk2-loongarch64`软件包中获取
  * 在镜像站中下载该软件包，解压后可以在解压后目录下的`usr/share/edk2/loongarch64/QEMU_EFI.fd`找到
  * 此外，由于`edk2-loongarch64`是`any`包，也可以直接在非`loong64`架构的机器上安装该软件包
* `-hda <path-to-your-image>`：指定虚拟机使用的qcow2镜像
* `-virtfs local,path=<path-to-your-sharing-directory>,mount_tag=host0,security_model=passthrough,id=host0`：将宿主机的目录目录共享给虚拟机

如果不需要启动GUI，**只在终端中操作**,可以去掉`-serial stdio`,并**加入`-nographic`参数**。

对于需要传递给虚拟机的软件包，可以复制或者`bind mount`到共享目录下，供虚拟机使用。

在虚拟机中，可以使用以下命令挂载共享目录：

```bash
sudo mount -t 9p host0 <mount-point>
```

然后即可访问共享目录中的内容，可以使用`pacman -U`来安装软件包。

## 修复无法启动的QEMU System虚拟机

如果内核存在问题，可能会使得QEMU System虚拟机无法启动，这时候可以通过以下方法来修复：

* 在宿主机中挂载qcow2镜像：
    * 加载nbd模块，挂载qcow2镜像：
        ```bash
        sudo modprobe nbd max_part=8
        sudo qemu-nbd --connect=/dev/nbd0 <path-to-your-image>
        ```
    * 挂载分区：
        ```bash
        sudo mount /dev/nbd0p2 <mount-point>
        ```
* 然后可以在挂载的目录下进行修复，例如：
    ```bash
    sudo systemd-nspawn -aD <mount-point> --bind <path-to-your-sharing-directory>:<mount-point>
    ```

修复完成后，卸载分区和nbd设备：

```bash
sudo umount <mount-point>
```

```bash
sudo qemu-nbd --disconnect /dev/nbd0
sudo rmmod nbd
```

然后即可重新启动QEMU System虚拟机进行测试。

* 需要注意的是，如果虚拟机的`/etc/mkinitcpio.conf`中的`HOOKS`中包含`autodetect`，则默认镜像如果在与虚拟机硬件环境不同的宿主机下生成，可能会导致缺少必要的模块而无法启动。这时候可以先使用`linux-*fallback`镜像启动虚拟机，然后在虚拟机中重新生成镜像。

# 对于需要更新`config.guess`和`config.sub`的软件包

在构建软件包时，有时候会遇到`config.guess`和`config.sub`过旧的问题，这时候可以给上游反馈，要求上游更新。当然，对于这样的软件包，可能是因为上游已经不再维护，或者上游不愿意更新，这时候我们需要更新`config.guess`和`config.sub`。

如果软件包的修复补丁**仅包含**`config.guess`和`config.sub`的更新，**不要**在[Patch仓库](https://github.com/lcpu-club/loongarch-packages)中单独维护其补丁，而是在仓库的[`update_conifg`文件](https://github.com/lcpu-club/loongarch-packages/blob/master/update_config)中添加对应的软件包名。

# Patch维护技巧：避免冲突

## 内容插入的原则（`source`、哈希数组等）

由于“主要矛盾”不同，在本项目的维护中，语句插入的原则也可能与Arch Linux上游有所不同。我们维护的是针对Arch Linux官方构建文件的补丁集，因此我们需要尽量避免与上游日常升级的修改产生冲突。

上游可能一般按照字母顺序来插入新的依赖或者新的选项，但是在我们的项目中，我们可以将新的依赖或者新的选项插入到**上下文最不容易被上游修改的地方**，以便减少冲突的发生。

由于`PKGBUILD`本质上是一个Bash脚本文件，对于新加入的`source`和哈希值等数组的内容，如果要最大程度地避免上游修改带来的冲突，我们可以**使用`+=`来添加新的元素**，而不是直接修改数组的内容。

```bash
source+=(...)
sha256sums+=(...)
```

## 对`PKGBUILD`大段删除的处理

有时候，由于某个功能整体不支持loong64，需要删除`PKGBUILD`中的大段代码；然而，如果这些被删除的代码在Arch Linux官方的维护中存在频繁更改，那么在以后应用`loong.patch`时就很可能会出现冲突。

为了避免这样的情况，我们可以将直接删除改为写成多行注释，例如，如果我们想要删除掉opencv的PKGBUILD中有关cuda的构建，我们可以在其前面插入`: <<COMMENT_SEPARATOR`，在其后面插入`COMMENT_SEPARATOR`，这样就可以在一定程度上避免上游对这个函数部分的修改导致的冲突。

```
  # Use a "multi-line comment" to keep patch from rotting
  : <<COMMENT_SEPARATOR
  CFLAGS="${CFLAGS} -fno-lto" CXXFLAGS="${CXXFLAGS} -fno-lto" LDFLAGS="${LDFLAGS} -fno-lto" \
  cmake -B build-cuda -S $pkgname $_opts \
      -DBUILD_WITH_DEBUG_INFO=OFF \
      -DCUDA_ARCH_BIN='52-real;53-real;60-real;61-real;62-real;70-real;72-real;75-real;80-real;86-real;87-real;89-real;90-real;90-virtual' \
      -DCUDA_ARCH_PTX='90-virtual'
  cmake --build build-cuda
COMMENT_SEPARATOR
```

此外，如果某段我们不希望构建的内容在函数的尾部，我们可以在前面插入`return`，以直接避免函数的后续内容被执行。

值得注意的是，如果我们不需要某个包的`package()`函数，我们应当直接将这个包**从`pkgname`数组中移除**，此时对应的`package()`函数会被忽略，因此不用删除或者注释掉。

如果仍然担心直接删除会导致冲突，也可以不在原处改动，而是在`PKGBUILD`末尾追加从Bash数组中删除对应的元素的操作，例如：

```bash
pkgname=($(printf "%s\n" "${pkgname[@]}" | grep -Ev '^(torchvision-cuda|python-torchvision-cuda)$'))
makedepends=($(printf "%s\n" "${makedepends[@]}" | grep -Ev '^(cuda|cudnn|python-pytorch-opt-cuda)$'))
```

这里使用`printf "%s\n"`来将数组元素逐行输出，然后使用`grep -Ev`来过滤掉不需要的元素，最后再将结果赋值回数组。这里`grep`使用了正则表达式的`^`和`$`来匹配行首和行尾，确保只删除完全匹配的元素。这一方式也更加灵活，可以使用任何合法的正则表达式来匹配需要删除的元素。对某些`pkgname`、`depends`和`makedepends`等**数组**常常发生**变动**的软件包，我们可以使用这种删除方式来**避免补丁冲突**。

## 应用了额外Patch的包含`pkgver()`函数的软件包

`pkgver()`函数一般通过`git`等工具来获取软件包的版本号，然而由于环境不同，可能会导致`pkgver()`函数获取到的版本号（尤其是hash的位数）不同。（此时可能会存在导出的`loong.patch`中包含对`pkgver`变量的修改，这是**不允许**的）

为了避免这种情况，我们应当删除或者注释掉`pkgver()`函数，保证软件包使用的是上游的版本号。当然，更好的办法是向上游反馈，要求在`pkgver()`函数的`git`命令中添加`--abbrev=12`等参数，以保证版本号的一致性。向上游反馈这个问题时，一般附加以“增加构建的可复现性”等理由，或者援引先例来说明这个问题的重要性。（一般不宜直接、单独以本项目的需要为理由）有关此问题的Arch Linux上游修改先例：

* [gcc #14](https://gitlab.archlinux.org/archlinux/packaging/packages/gcc/-/issues/14)
* [gcc commit 9dc7297f](https://gitlab.archlinux.org/archlinux/packaging/packages/gcc/-/commit/9dc7297f6752c8592b603c9949613f56fe018453)
* [gcc commit 158c088f](https://gitlab.archlinux.org/archlinux/packaging/packages/gcc/-/commit/158c088f6220da200e1a5986857b1fb8ce15e303)

# Patch的获取

**不一定**所有需要Patch的软件包都需要自己手动编写Patch，有时候可以从其他地方获取Patch，例如：

* 上游软件仓库
  * 如果上游已经修复但是没有发布，可以从**上游的Git仓库**中获取Patch
    * 未合并的PR也可以作为我们临时修复的Patch
  * 善用GitHub的检索功能，关键字一般可以选择`loongarch`、`loong`、`loongson`、`loongarch64`、`loong64`等
  * 注意：如果上游有相关修复，一定要**优先使用上游的修复**
* 其他支持loongarch发行版
  * [Gentoo/Loongson Support Overlay](https://github.com/xen0n/loongson-overlay)
  * [ABBS/ACBS tree for AOSC OS package metadata, build configuration, scripts, and patches](https://github.com/AOSC-Dev/aosc-os-abbs)
  * [AOSC Code Tracking Project](https://github.com/AOSC-Tracking)
  * [原Loong Arch Linux项目](https://github.com/loongarchlinux)

此外，其他Arch Linux移植项目的Patch也可以参考，例如：

* [Modified Arch Linux packages for archriscv ](https://github.com/felixonmars/archriscv-packages)
  * 其中不针对于RISC-V架构的Patch可能可以直接参考使用，例如：
    * 禁用了仅适用于x86的功能
    * 禁用了仅x86下存在的依赖
    * 禁用了仅x86下存在的编译选项
  * 对于RISC-V架构的Patch，可以参考其Patch的内容，参照维护自己的Patch

某些时候，某个软件所需要的Patch可能已经出现在了**某个大型软件包的子模块**中，反之亦然。此时，我们也可以尝试去复用这些Patch或者作为参考。

# 与上游交流的注意事项

这部分内容可以参考[archriscv社区的建议](https://github.com/felixonmars/archriscv-packages/wiki/%E5%BC%80%E5%A7%8B%E9%A1%B9%E7%9B%AE%E8%B4%A1%E7%8C%AE%E5%92%8C%E7%A4%BE%E5%8C%BA%E4%BA%A4%E6%B5%81%E5%89%8D%E5%BF%85%E8%A6%81%E5%AD%A6%E4%B9%A0%E7%9A%84%E6%A6%82%E5%BF%B5)：

> 首先在给社区做贡献之前，一定要优先看上游的 Code of conduct/How to contribute 等指引，尽可能的按照上游的习惯去合作。 其次和社区沟通时，尽量**减少提 “某某错误是在给 loongarch-packages 做修复时出现的”**，也**不要用 loongarch-packages 这边的习惯做法去和上游对峙**。在和上游沟通时，只需要提软件错误相关的**必要信息**即可。更不要不知所谓的丢个 loongarch-package 的修复链接给上游，敷衍了事的报个 bug，**这样会损害整个项目的社区声誉**。

此外，笔者还有若干补充：

* 某些问题并不一定与架构相关，比如上游的`config.guess`、`config.sub`或者`Cargo.lock`等文件过旧，这时候提出“可能影响`loong64`架构的构建时”，也最好一并附上**安全性考虑**等理由，因为一般而言维护者更可能更关注通用的安全、性能、修复等问题，而不是一个自己不太了解的架构上的构建情况
* 向本不支持`loong64`的软件的构建/配置文件中添加`loong64`支持时，考虑到上游可能根本不知道这个架构，可以附上相关介绍
  * [内核文档中的LoongArch介绍](https://docs.kernel.org/arch/loongarch/introduction.html)
  * [Phoronix上有关LoongArch的资讯与评测](https://www.phoronix.com/search/LoongArch)
  * 在PR中简单介绍这个架构
  * 总之，尽量简洁地让上游了解这个架构，并体现出**架构的重要性**和**修复的必要性**

PR参考示例：[GitHub Google/libultrahdr PR#303](https://github.com/google/libultrahdr/pull/303)

# 开发分支的管理要求

为了避免给`loongarch-packages`引入冲突，我们一般需要遵循以下原则：

* 使用**自己的fork**来进行开发
* 主分支（`master`）只用于同步上游的`loongarch-packages`的`master`分支
  * 仅用于同步，不用于开发
* 为要修复的包**单独建立**以包名命名的分支
  * 派生自`master`分支（派生前先同步`master`分支）
  * 命令示例：`git checkout -b <package-name>`
  * 开发分支仅用于对应包的补丁提交，不用于同步

# 有关LoongArch64的编译器预定义宏

以下指导原则来自[xen0n](https://github.com/xen0n/)：

> 关注gpr宽度是否为64，用`__loongarch_grlen == 64`，
> 关注调用约定是否为LP64系，用`__loongarch_lp64`

一般来说，我们关注的是调用约定，因此建议使用`__loongarch_lp64`。

# FAQ

## `relocation R_LARCH_B26 out of range`/`relocation R_LARCH_B26 overflow`错误

这个错误信息一般来自链接器，它表示在处理文件时，发生了`R_LARCH_B26`重定位溢出错误。`R_LARCH_B26`是LoongArch架构的一种重定位类型，通常用于跳转指令。它要求目标地址必须在跳转指令可达的范围内（128 MB），即它只允许一定范围内的偏移量。

这个错误通常发生在编译Chromium、Firefox等大型软件包时，链接器无法找到合适的位置来放置跳转指令。

自`devtools-loong64`的`1.3.1.patch2-1`起（2025.1.21），我们已经在默认的`makepkg.conf`中向`CFLAGS`和`CXXFLAGS`添加了`-mcmodel=medium`，因此**理论上一般不需要再额外设置**Code Model，理论上也不应该出现这个问题。

如果仍然出现这个问题，可能是以下原因：

* 程序**静态链接**到了2025.1.21**之前**`devtools-loong64 < 1.3.1.patch2-1`构建的且没有手动指定`-mcmodel=medium`的**系统库或者对象文件**
  * 此时应该**重新构建**这些包含没有覆盖的系统库或者对象文件的依赖包
* 软件包的构建系统因为各种原因，**没有使用全局的`CFLAGS`和`CXXFLAGS`**
  * 此时可能可以在构建文件等地方手动添加指定Code Model的参数

以下方法仅在`devtools-loong64 < 1.3.1.patch2-1`时使用，目前**已失效**，仅供存档：

> 解决这个问题的方法一般为在编译参数中加入`-mcmodel=medium`来扩大地址空间，使得链接器可以找到合适的位置来放置跳转指令。[^1] [^2]
>
> [^1]: [GitHub/Rust PR#120661](https://github.com/rust-lang/rust/pull/120661)
> [^2]: [GCC Doc: LoongArch Options](https://gcc.gnu.org/onlinedocs/gcc/gcc-command-options/machine-dependent-options/loongarch-options.html#cmdoption-LoongArch-mcmodel)
>
> 例如，可以在`PKGBUILD`中的`prepare()`或者`build()`函数中加入以下内容：
>
> ```bash
> prepare() {
>     ......
>
>     # Add ` -mcmodel=medium` to CFLAGS etc.
>     # to avoid `relocation R_LARCH_B26 overflow`
>     export CFLAGS="${CFLAGS} -mcmodel=medium"
>     export CXXFLAGS="${CXXFLAGS} -mcmodel=medium"
>
>     ......
> }
> ```
>
> `-mcmodel=medium`会使得编译器使用`medium`模型，这样可以扩大地址空间，允许更大的跳转范围（2 GiB）。
>
> * 自Rust 1.83起，Rust的Code Model默认为`medium`，因此不需要再额外设置`export RUSTFLAGS="${RUSTFLAGS} -C code-model=medium"`

### LTO出错：换链接器还是禁用LTO？

#### 因链接器Bug导致的LTO失败

目前的`binutils`版本存在一些Bug，可能会在链接时出现段错误等情况，尤其是在LTO时，这时候我们一般有两种选择：

* 改用`mold`链接器
  * 在`PKGBUILD`的`prepare()`函数中加入以下内容：
    ```bash
    export LDFLAGS="${LDFLAGS} -fuse-ld=mold"
    ```
  * 在`PKGBUILD`的`makedepends`数组中加入`mold`
    * 为了避免补丁应用时的冲突风险，不建议直接在原来的`makedepends`数组中直接添加`mold`
    * 建议在`PKGBUILD`末尾添加`makedepends+=('mold')`
* 禁用LTO
  * 在`PKGBUILD`中加入`options=(!lto)`

一般来说，这两种方法都可以解决这一问题，但是目前推荐优先尝试不禁用LTO，仅改用`mold`链接器的方法：

* 目前据笔者的观察，`mold`在LoongArch下稳定性更好
* `mold`的性能显著更好，且对`binutils`的`bfd`的兼容性出色
* 保留LTO可以提高软件包的性能

总结选择如下：

1. 如果上游设置直接可行，不要作更改，直接使用上游设置
2. 如果上游设置不可行，优先尝试`mold`链接器
3. 如果`mold`链接器也无法解决问题，可以尝试禁用LTO

#### 其他原因导致的LTO失败

注意，以上指引是针对**链接器自身Bug**的情况，如果不是这个原因，例如，存在无法访问的其他架构的内联汇编导致LTO失败，那么应当直接禁用LTO：

```log
error: impossible constraint in ‘asm’
# Or
Error: no match insn: xxx xxx xxx
```

这个时候换用其他链接器是无法解决问题的。

### `binutils`的Bug：设置`-mcmodel=medium`后仍然链接失败

* `bintuils`自`2.43_1+r171+g01da089627be-1`已经修复了`relax`的问题，参见[Commit bb9a0a3](https://github.com/bminor/binutils-gdb/commit/bb9a0a36e78aa564021b377a4a7fab4851b2c22b)，不应该再出现这个问题
* 以下内容**已失效**，理论上应该没有必要使用，仅供存档

> * 与上一小节类似，目前**建议直接改用`mold`链接器**（`export LDFLAGS="${LDFLAGS} -fuse-ld=mold"`）
> * 如果`mold`链接器会引入新的问题，必须使用`bfd`时，可以尝试以下方法
> 
> 目前的`binutils`版本（`2.43+r4+g7999dae6961-1`）存在问题，`relax`时对指令进行了错误的优化，导致即使设置了`-mcmodel=medium`也会出现`relocation R_LARCH_B26 out of range`问题。这一问题即将修复，但是尚未发布。
> 
> 如果不改用其他链接器，可以通过在`LDFLAGS`中加入`-Wl,--no-relax`来避免这一问题。
> 
> ```bash
> prapre() {
>     ......
> 
>     # Add ` -mcmodel=medium` to CFLAGS etc.
>     # to avoid `relocation R_LARCH_B26 overflow`
>     export CFLAGS="${CFLAGS} -mcmodel=medium"
>     export CXXFLAGS="${CXXFLAGS} -mcmodel=medium"
>     export LDFLAGS="${LDFLAGS} -Wl,--no-relax"
> 
>     ......
> }
> ```
> 
> 待`binutils`修复后，应当将这一修改去除。

## QEMU User特异性问题

* **省流：在QEMU USER模式如果遇到奇怪/难以解释的问题，请尝试在QEMU System模式或者实体机上进行测试**
  * 当然，QEMU System模式模拟性能很差，请自行衡量

由于QEMU User的实现问题，使用QEMU User模式构建软件包时可能会遇到一些特异性问题，目前已知的问题有：

* 运行过于缓慢导致某些`check`超时报错
* 调用`python`的`multiprocessing`模块的程序**大概率**会**卡死**
  * 也有**可能**发生**内存泄漏**
* `go`语言程序编译有一定概率卡死
* `gn`在部分场景下有概率卡死并报错
  ```log
  -- GN Done. Made ... targets from ... files in ...ms

  ......

  -- GN FAILED

  Process terminated due to timeout
  ```
  * 不太能总结出触发条件
  * 不过需要注意的是，如果修改`gn`配置的patch有误也可能会导致这个问题

（待补充）

### QEMU User典型失败内容列举

* `opus`构建
  * `check`严重超时（>50倍）
* `gimp-help`构建（似乎用到了python的`multiprocessing`模块）
  * 内存泄漏
* `pyside6`构建
  ```log
  ImportError: /build/pyside6/src/build/sources/shiboken6/Shiboken.cpython-312-loongarch64-linux-gnu.so: file too short
  ```
* 部分测试仅在QEMU User下失败
  * `wayland`
    ```log
    sanity-test: ../wayland-1.23.0/tests/sanity-test.c:92: sanity_fd_leak: Assertion `fd_leak_check_enabled' failed.
    qemu: uncaught target signal 6 (Aborted) - core dumped
    Client 'sanity_fd_leak' was killed by signal 6
    Client 'sanity_fd_leak' failed
    1 child(ren) failed
    qemu: uncaught target signal 6 (Aborted) - core dumped
    test "tc_client_fd_leaks":	signal 6, pass.
  ```
  * `vim`
  * `gdk-pixbuf2`
  * `glib2`中`GSubprocess`的测试
  * `mold`
    ```
    211 - loongarch64-section-order (Failed)
    ```
* 部分包在QEMU下的测试构建一切正常，但仍**不能**用QEMU打包
  * `rust`在QEMU下可以正常打包并运行，但是打包出来的文件在**真机下**会因为**页大小错误**而**无法运行**

（待补充）

## `pkgctl`从官方`clone`软件包时要求输入用户名和密码

如果使用`pkgctl`从官方克隆软件包时（包括用`get-loong64-pkg`获取软件包时）要求输入用户名和密码：

```log
==> Cloning <package-name> ...
Cloning into '<package-name>'...
Username for 'https://gitlab.archlinux.org': 
```

这个时候说明Arch Linux官方**并不存在**这一软件包仓库，一般有以下几种情况：

* 这个软件是仅相关于Loong Arch Linux的软件包，没有由Arch Linux维护
  * 例如`archlinux-lcpu-keyring`，`devtools-loong64`
  * 这些软件包不能用上游的`pkgctl repo clone`，但是可以**正常用`get-loong64-pkg`获取**
* 未以`pkgbase`来克隆软件包仓库
  * 注意上游的软件包仓库名是`pkgbase`，而**不一定**是`pkgname`
  * 同一`pkgbase`可能会包括多个`pkgname`的软件包
    * 例如`rust`提供了`rust`、`rust-musl`、`rust-src`、`rust-wasm`等软件包，这些软件包都在`rust`这一仓库中
  * 无论是`pkgctl`还是`get-loong64-pkg`，都需要使用`pkgbase`来克隆软件包仓库
* 单纯把软件包名敲错了

## 我想保存/查看某一次的构建环境怎么办？

### 保存

默认情况下，每次运行针对相同仓库的构建命令时，`devtools`会自动清理上一次的构建环境。如果需要保存某一次的构建环境，可以对上一次构建环境的子卷进行快照，例如：

```bash
sudo btrfs subvolume snapshot /var/lib/archbuild/extra-loong64-build/<user-name> <path-to-your-snapshot>
```

如果不再需要这个快照，可以通过以下命令删除：

```bash
sudo btrfs subvolume delete <path-to-your-snapshot>
```

### 进入环境查看

可以使用`systemd-nspawn`进入构建环境，例如：

```bash
sudo systemd-nspawn -aD /var/lib/archbuild/extra-loong64-build/<user-name>
```

* 注意：**切勿**进入`/var/lib/archbuild/<repo-name>-loong64-build/root`环境中，这是保留的**干净环境**，不要在这个环境中进行任何操作。如果对这个环境进行了修改，下次运行`<repo-name>-loong64-build`时请添加`-c`参数以清理环境。

这样进入环境以后的用户是`root`，一般我们需要切换到构建用户。Arch Linux构建环境中的构建用户统一都是`builduser`，可以用以下命令切换：

```bash
sudo -u builduser bash
```

`builduser`的家目录是`/build`，这同时也是构建环境的工作目录。其中的`<pkgbase>`目录就是软件包的构建目录。一般编译的中间文件都在`/build/<pkgbase>/src`的子目录中。

#### 在构建环境中进行`makepkg`操作（不推荐）

`/build/<pkgbase>/`目录下并不存在`PKGBUILD`文件，而且原`PKGBUILD`中直接指定的`source`在这里也只有**不可直接访问的**软链接。因此，我们并不能够直接在这里进行`makepkg`的相关操作。

如果必须要在这里进行操作，可以将`PKGBUILD`文件复制到这里。因为一般在这个环境中进行的`makepkg`操作可能已经完成了编译（例如：因为直接构建时`check`没有通过，修改了`check`的逻辑，但是又不想重新构建，所以尝试在构建环境中先测试修改后的`check`能否通过），一般需要执行的只有`check`或者`package`部分。如果要跑`check`函数，可以执行：

```bash
makepkg --check
```

如果要打包，可以执行：

```bash
makepkg -R
```

这样打包生成的文件会存放在**构建环境容器**的**`/srcpkgdest`**目录下。

然而，**笔者并不推荐这种做法**，笔者仍然建议按照官方的流程来运行构建命令。此外，校内具有上传权限的开发者请注意，由这样的方式得到的软件包**一律禁止上传**，只能用于本地的Bootstrap用途。

### 在保存的环境中操作git源代码仓库

`archbuild`会将存储构建源码的整个`PKGBUILD`所在目录`pkgbase`挂载到构建环境的`/startdir`目录下，当我们离开构建环境后，这个目录会被卸载。此时，如果我们再尝试对git源代码仓库进行操作，会因为找不到`/startdir`下的object而报错。

如果需要用`systemd-nspawn`进入保存的环境中操作git源代码仓库，可以将宿主的`PKGBUILD`和构建源码的所在的`pkgbase`目录挂载到构建环境的`/startdir`目录下，例如：

```bash
sudo systemd-nspawn -aD /var/lib/archbuild/extra-loong64-build/<user-name> --bind /path/to/your/pkgbase:/startdir
```

如果我们是希望直接在宿主的环境中操作git源代码仓库，则需要修改git仓库设定的`.git/objects/info/alternates`，将其指向宿主的实际`objects`目录，例如：

```bash
find /path/to/the/git/repo -type f -path '*/.git/objects/info/alternates' -exec sed -i -e 's|^/startdir|/path/to/your/pkgbase|g' {} +^C
```

## 网络环境不稳定导致下载失败

有时候我们的网络环境不稳定，导致构建所需的源代码下载失败，而如果反复运行构建命令，又存在重新创建环境等资源开销，较为缓慢。

此时，我们可以安装`pacman-contrib`包，使用`updpkgsums`来下载源代码：

* Bash/Zsh
  ```bash
  while ! updpkgsums
  done
  ```
* Fish
  ```fish
  while not updpkgsums
  end
  ```

在下载完成之后，再手动检查一下`PKGBUILD`中的哈希是否变动，如果没有变动，再运行构建命令即可。

## 我为什么经常遇到`(invalid or corrupted package (checksum))`错误？

对于这样的错误：

```log
:: File /var/cache/pacman/pkg/<package> is corrupted (invalid or corrupted package (checksum)).                                                                                                                              
Do you want to delete it? [Y/n]
```

这表示的是软件包的校验和不匹配，一般来说**重新运行命令**，尝试**重新下载**软件包即可解决。

对于架构为`any`的包， 用户自行在**x86下载的更新包**与**龙芯的包**可能**同名**但是构建环境与签名者不同，很可能会出现这个错误。

如果不愿意被重试困扰，可以在运行的构建命令中向`makechrootpkg`传递`-d`参数，为构建环境指定不同的缓存目录，例如：

```bash
mkdir ~/loong64-cache
extra-loong64-build -- -d ~/loong64-cache:/var/cache/pacman/pkg/ -- -A
```

* 这一方法可以避免在**构建子环境**中可能遇到的冲突问题，却不能避免**干净chroot模板环境**在构建前的升级过程中可能遇到的冲突问题
  * 因为`-d`参数只会传递给从模板环境（`root`子卷）新建的构建子环境，而不会传递给模板环境本身
* 不过干净chroot模板环境中仅存在`base-devel`及其依赖包，其中的包升级不那么频繁，因此这一问题的发生概率较低

## 如何指定`sogrep-loong64`的镜像站

自`devtools-loong64`的`1.2.1.patch9-1`版本开始，`archbuild`默认使用`/etc/pacman.d/mirrorlist-loong64`这一镜像列表。在`loong64`上，由发行版的默认镜像列表软件包`pacman-mirrorlist-loong64`提供，在其他架构上，由`devtools-loong64`本身提供。

然而，`sogrep-loong64`工具本身不会读取`mirrorlist-loong64`文件，而是读取环境变量`SOLINKS_MIRROR`来获取镜像站。如果需要指定镜像站，可以在运行命令时指定环境变量，例如：

```bash
SOLINKS_MIRROR=https://loongarchlinux.lcpu.dev/loongarch/archlinux sogrep-loong64 <repo> <lib>
```

## 如何指定构建环境的镜像站

构建环境会自动读取宿主的镜像站配置并写入到构建环境的`/etc/pacman.d/mirrorlist`中。然而，我们真正使用的`mirrorlist`是`/etc/pacman.d/mirrorlist-loong64`，这一文件不会从宿主环境中读取。如果我们想要修改，可以在模板环境中修改`/etc/pacman.d/mirrorlist-loong64`。（但是注意不应该对模板环境进行任何污染，确保模板环境是干净的）

有时候，如果**嫌镜像站同步过慢影响开发**，可以将其设置为`CacheServer`：

```bash
CacheServer = https://mirrors.pku.edu.cn/loongarch-lcpu/archlinux/$repo/os/$arch
Server = https://loongarchlinux.lcpu.dev/loongarch/archlinux/$repo/os/$arch
Server = https://mirrors.pku.edu.cn/loongarch-lcpu/archlinux/$repo/os/$arch
```

这样会优先从第一个`Server`条目，也就是原始的Tier0镜像站获取仓库元数据，并优先从`CacheServer`获取软件包，保证了下载速度和软件包的新鲜度。

## LTO提示磁盘空间不足：`lto: fatal error: write: No space left on device`

这一错误很有可能不是真的吃满了硬盘空间。`archbuild`使用的systemd-nspawn环境中`/tmp`目录是挂载的`tmpfs`，Arch Linux上游设定的`tmpfs`大小是内存（**不包括swap**）的50%，如果`/tmp`被写满了，就会出现这个问题。

如果确实有用小内存机器构建这样大型的软件包的需求，可以在构建命令中向`makechrootpkg`传递`-t /tmp:size=<size-you-want>`参数**覆盖**Arch Linux上游的设定，指定`tmpfs`的大小（可以用绝对大小或者物理内存的百分比表示，此外也可以指定更多参数，参见[Linux内核文档](https://www.kernel.org/doc/html/v6.12/filesystems/tmpfs.html)），例如：

```bash
extra-loong64-build -- -t /tmp:size=32G -- -A
```

需要注意的是，如果要用以上方法，应当保证`tmpfs`的大小根据内存和swap的总大小合理设置。以下是来自Linux内核文档的警告：

> If you **oversize** your tmpfs instances the machine will **deadlock** since the OOM handler will **not be able to free** that memory.

对于小内存机器，如果要使用这样的方法来构建大型软件包，应当务必确保启用了**足够大的swap分区**。

## 如何从GitHub的PR/Commit中获取Patch

GitHub的PR/Commit页面提供了`diff`和`patch`的下载功能，在对应的PR/Commit页面下，只需要在PR或者Commit号后面加上`.patch`或者`.diff`即可跳转到对应的Patch页面，该Patch可以直接放到`PKGBUILD`的`source`中，但是建议用`::`分隔来指定Patch的名字。（要求Patch文件名需要有实际意义）

由于从GitHub获取的`.patch`文件中包含了时间、commit hash等容易变化的信息，尤其是commit hash的位数可能出现不一致，导致文件的**checksum出现变化**，因此笔者**更建议使用`.diff`文件**，`.diff`文件中只包含了文件的相对路径和变动内容，不包含commit hash等信息，更加稳定。

## 上游已合并但未发布的Commit/未合并的PR导出的Patch在`source`中优先写链接还是写本地Patch文件

很多时候我们使用的Patch可能是已经合并但未发布的Commit，或者是未合并的PR导出的Patch。这些Patch已经可以从上游的链接中获取。为了**简化我们的补丁集内容**，并且**增加Patch的可查验性**，便于**追踪**上游及PR提出者的**更新**，我们一般按照以下原则来指定Patch的来源：

1. 如果上游已经存在相关Commit，且软件本身使用git仓库进行构建，**优先使用`git cherry-pick -n <commit-hash>`**应用补丁
   * 如果**一个PR**有**多个Commit**且上游合并的时候**没有squash**，可以直接**应用merge commit**，但是需要加上`-m 1`参数
2. 上游尚未存在相关Commit，或者本身使用tarball构建，并非git仓库，**优先在`source`中添加[指向上游Patch的链接](#如何从GitHub的PR/Commit中获取Patch)**
3. 相关PR变动过于频繁，以上两种情况均不可行时，才考虑将Patch文件**拉到本地并放入`source`中**

## 某git仓库太大，我是否可以从国内的镜像源克隆再给`makepkg`使用

由于国内网络环境的原因，有时候我们直接从`PKGBUILD`指定的git地址克隆一个完整且巨大的仓库可能会非常困难，如果这一仓库在国内有可以高速访问的镜像，我们确实也可以先从镜像源克隆一份，然后再经过一些处理后给`makepkg`使用。

首先我们先从国内的某个镜像源（比如Gitee、GitCode或者某些国内的GitHub镜像站等）克隆一份，这里需要注意的是，我们推荐将这一用于存储的仓库克隆为bare仓库，遵从上游`makepkg`的习惯：

```bash
git clone --bare <mirror-repo-url> <path-to-bare-repo>
```

然后，根据`PKGBUILD`的`source`数组中的地址，重新指定我们从镜像源克隆的仓库的远程地址：

```bash
cd <path-to-bare-repo>
git remote set-url origin <upstream-repo-url>
```

此外，由于`makepkg`通常会使用`git tag`来切换到指定的版本，我们必须要保证在每次`makepkg`自动`git fetch`时一并获取`tag`（`makepkg`克隆的仓库自动设定了这项设置，手动克隆的则默认没有开启，需要自行设定），避免没有拉取到上游的`tag`导致找不到对应的版本。我们可以通过以下命令开启这一设置：

```bash
git config fetch.pruneTags true
```

最后，将该仓库移动到`PKGBUILD`所在目录的指定名称，即可给`makepkg`使用。

## `makepkg`克隆下来的git仓库是bare仓库，如何测试、应用Patch

Arch Linux的`makepkg`会把仓库克隆成bare仓库，其中没有工作目录的，因此无法直接在这个仓库中进行修改。如果需要在本地测试、应用Patch，可以将这个bare仓库克隆一份非bare仓库，例如：

```bash
git clone <path-to-bare-repo> <path-to-non-bare-repo>
```

这一克隆过程仅涉及在本地的复制和处理，不会涉及网络传输，因此速度很快。后续，我们可能还需要将这个非bare仓库的`origin`指向上游仓库，例如：

```bash
cd <path-to-non-bare-repo>
git remote set-url origin <upstream-repo-url>
```

然后就可以在这个非bare仓库中进行修改、测试、应用Patch了。

## 大规模重构建中升级的包因为soname被某依赖锁定版本，导致安装老版本包使得重构建无效怎么办？

在大规模重构建中，由于依赖关系复杂，可能会存在我们的local repo中有更新的包，但是由于某个依赖锁定了版本，导致重构建的时候安装了老版本的包（或者中途降级为老版本的包），导致重构建无效。这一问题本质上是构建顺序不合理导致的。如果我们遇到了这样的问题，可以利用Arch Linux的`pactree`等工具方便地**排查到底是哪个依赖锁定了版本**。

`pactree`是Arch Linux的一个命令行工具，可以用来查看软件包的依赖关系树。我们可以使用以下命令来查看某个软件包的依赖关系：

```bash
pactree -s <package-name>
```

锁定了soname版本的依赖在`pactree`的输出中会呈现出一定的特征。一般情况下，如果没有在依赖中显式指定soname，那么`pactree`的输出中会显示为：

```log
├─xz
├─zlib
├─zstd
```

如果在依赖中显式指定了soname，那么`pactree`的输出中则类似：

```log
├─xz provides liblzma.so=5-64
├─zlib provides libz.so=1-64
├─zstd provides libzstd.so=1-64
```

我们只需要用`grep`找出这样的特征即可。

### 安装`depends`时即锁定了旧的依赖

对于这种情况，一般体现为构建过程中直接安装了老版本的依赖包。我们可以使用`pactree`来查看我们待构建的这个包的依赖关系树，找出锁定了旧版本的依赖包：

```bash
pactree -s <package-name>
```

在其中找到`<soname发生变化的依赖> provides <soname>=<old-version>`的行，表示这个依赖包锁定了旧版本的依赖，向上一级即为导致版本锁定的依赖包。

例如，如果我们需要对`libxml2`升级进行重构建，并且在构建`cmake`的时候发现了版本锁定，需要排查其依赖关系，运行：

```bash
pactree -s cmake
```

输出如下：

```log
cmake
├─ ……（省略）
├─libarchive
│ ├─ ……（省略）
│ ├─libxml2 provides libxml2.so=16-64
│ ├─ ……（省略）
```

找到`libxml2 provides ……`这一行，并向上追溯一个层级，发现是`libarchive`锁定了旧版本的依赖。这表明我们蓄意先将`libarchive`来针对新版本的`libxml2`进行重构建，然后才能重构建`cmake`。

### 安装`makedepends`/`checkdepends`时锁定了旧的依赖

对于这种情况，可能体现为构建过程中先安装了新版本的依赖包，然后在安装`makedepends`/`checkdepends`的时候又降级为了老版本。这种情况我们需要对`makedepends`/`checkdepends`进行排查，找出锁定了旧版本的依赖包。首先在Bash（或者其他兼容POSIX的Shell，**不能用Fish**）中从`PKGBUILD`导出`makedepends`/`checkdepends`数组，并遍历初筛造成影响的直接依赖：

```
makedepends=$(source PKGBUILD && echo "${makedepends[@]}")
checkdepends=$(source PKGBUILD && echo "${checkdepends[@]}")

for dep in $makedepends; do
    if pactree -s $dep | grep -q "<soname发生变化的依赖> provides"; then
        echo "$dep"
    fi
done

for dep in $checkdepends; do
    if pactree -s $dep | grep -q "<soname发生变化的依赖> provides"; then
        echo "$dep"
    fi
done
```

这样即得到了造成版本锁定的直接依赖包，接下来，按照[**安装depends时即锁定了旧的依赖**的方法](#安装depends时即锁定了旧的依赖)来排查这些依赖包的依赖关系树，找出应该首先重构建的包。

## `check()`阶段实在无法通过怎么办？

一般来说：

* 如果打包过程在`check()`阶段无法通过，应该尽可能**向上游反馈**，并**尽量修复**问题
* 如果无法做到（比如上游尚未接受LoongArch的支持，或者失败原因复杂，牵涉很多依赖体系），优先**禁用已知的、影响有限的极个别的**失败的测试用例，以保证`check()`阶段可以通过
* 如果不支持单独禁用测试用例，则优先**在运行的测试命令后面**加上`|| echo "Watch out for failed tests!"`，使得`check()`阶段不会因为测试失败而导致整个打包过程失败，同时也保证了测试失败的**日志可以查看**。例如：
  ```bash
  check() {
    cd "$pkgname-$pkgver"
 
    meson test -C build --print-errorlogs || echo "Watch out for failed tests!"
  }
  ```
* 如果是测试阶段会卡死或者内存泄漏，根本无法运行`check()`函数，可以在`PKGBUILD`最后加上：
  ```bash
  check() {
    echo "Skipping check() phase due to……"
  }
  ```
  这样可以覆盖原`check()`函数以便跳过`check()`阶段，并且输出了跳过`check()`阶段的详细原因，方便其他开发者了解。

# 更多阅读材料

* [龙芯的Arch Linux移植工作流程 by wszqkzqk](https://wszqkzqk.github.io/2024/08/22/loongarchlinux-port-tips/)
* [ArchWiki](https://wiki.archlinux.org/)
* [Arch Linux Packaging Standards](https://wiki.archlinux.org/title/Arch_packaging_standards)
* [Arch RISC-V Port Wiki](https://github.com/felixonmars/archriscv-packages/wiki)
* [在x86设备上跨架构构建LoongArch的Arch Linux软件包 by wszqkzqk](https://wszqkzqk.github.io/2024/08/08/devtools-loong64/)
* [Arch RISC-V Port Wiki - 我们的工作习惯](https://github.com/felixonmars/archriscv-packages/wiki/%E6%88%91%E4%BB%AC%E7%9A%84%E5%B7%A5%E4%BD%9C%E4%B9%A0%E6%83%AF)
* [Arch RISC-V Port Wiki - 完全新人指南](https://github.com/felixonmars/archriscv-packages/wiki/%E5%AE%8C%E5%85%A8%E6%96%B0%E4%BA%BA%E6%8C%87%E5%8D%97)
* [利用本地仓库实现有依赖关系的软件包的顺序构建 by wszqkzqk](https://wszqkzqk.github.io/2024/09/19/build-order-local-repo/)
* [Loong Arch Linux维护中可能用到Bootstrap构建方法 by wszqkzqk](https://wszqkzqk.github.io/2024/11/20/Loong-Arch-Linux-Bootstrap-Packages/)
* [为龙架构的Arch Linux构建Chromium与Electron by wszqkzqk](https://wszqkzqk.github.io/2025/01/04/archlinux-loong64-chromium-electron/)
* [LoongArch介绍 — The Linux Kernel documentation](https://www.kernel.org/doc/html/latest/translations/zh_CN/arch/loongarch/introduction.html)
* [LoongArch 指令集架构的文档](https://github.com/loongson/LoongArch-Documentation/releases/latest/download/LoongArch-Vol1-v1.10-CN.pdf)
