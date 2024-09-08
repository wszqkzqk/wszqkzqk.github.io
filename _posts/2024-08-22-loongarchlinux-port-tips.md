---
layout:     post
title:      龙芯Arch Linux移植技巧
subtitle:   Loong Arch Linux移植要点
date:       2024-08-22
author:     wszqkzqk
header-img: img/bg-mountain-darken.webp
catalog:    true
tags:       系统配置 系统维护 开源软件 Linux archlinux 国产硬件 虚拟化
---

# 需要重新构建的软件

## soname变更

多数时候，如果遇到上游软件包的soname变更，**必须**要重新构建链接到这些库的软件包。

当开发者使用`devtools`/`devtools-loong`构建软件包时（例如`extra-loong64-build`），会自动运行`checkpkg`来检查soname变化，例如，我们将`llvm`（pkgbase）从`16.0.6-2`升级到`18.1.8-4`，`checkpkg`会输出如下信息：

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
* `extra-*-build`默认并不会保存`checkpkg`的输出，可以考虑事先在命令中加入`| tee all.log`来保存所有输出。

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

获得了需要重新构建的软件包列表后，我们需要按照依赖关系的顺序来构建这些软件包。目前，肥猫的[`genrebuild`脚本](https://github.com/felixonmars/archlinux-futils/blob/master/genrebuild)可以帮助我们生成构建顺序。

```bash
genrebuild <package1> <package2> ...
```

# 一般的Bootstrap方法

在Bootsrap的过程中，往往需要在构建环境中添加一些源中没有的软件包，这可以通过`makechrootpkg`的`-I`参数来实现，而在运行`extra-testing-loong64-build`或者`extra-staging-loong64-build`的时候，可以通过`--`参数来添加传递到`makechrootpkg`的参数。

```bash
cd <package>
extra-testing-loong64-build -- -I <package1> -I <package2> ...
```

# 软件包的手动上传

在打包完成后，如果具有上传权限，开发者可以将软件包上传。一般来说，没有处理好依赖或者没有重新构建完所有需要重新构建的软件包时**只能**上传到`extra-staging`或者`core-staging`。（一般能够使用本文介绍的[**Bootstrap方法**](#一般的Bootstrap方法)来解决问题时**不用上传**到`staging`）当软件包没有依赖和重构建问题时，可以上传到`extra-testing`或者`core-testing`。如果软件包很简单稳定，完全不需要测试，才可以上传到`extra`或者`core`。

需要注意的是，如果软件包存在需要一并上传的依赖或者需要重新构建的软件包，应当**一并上传，不要遗漏**。

上传可以使用一些脚本来简化，例如：

```
#!/bin/bash

if [[ $# -lt 2 ]]; then
    echo "Usage: ${0##*/} <repo-name> <pkg-file> [option]"
    echo "Option:"
    echo "  --sign Sign the database file."
    exit 1
fi

# Set the server information "username@hostname"
TIER0SERVER=""
# Set the port of the server
PORT=""
_remote_path=/srv/http/loongarch/archlinux/

REPO=$1
PKG_PATH=$2
PKG=$(basename $2)
shift
shift

# get pkgname and version infor from $PKG
TEMP=${PKG%-*}
REL=${TEMP##*-}
TEMP2=${TEMP%-*}
VER=${TEMP2##*-}
NAME=${TEMP2%-*}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --sign)
            SIGN=-s
            shift
            ;;
        *)
            shift
            ;;
    esac
done

gpg --detach-sign --use-agent $PKG_PATH
if [[ ! -e $PKG_PATH.sig ]]; then
    echo "$PKG_PATH.sig not found! Exiting..."
    exit 1
fi

rsync -e "ssh -p ${PORT}" -p '--chmod=ug=rw,o=r' -c -h -L --progress --partial -y $PKG_PATH{,.sig} $TIER0SERVER:$_remote_path/$REPO/os/loong64/
ssh -tt $TIER0SERVER -p $PORT "cd $_remote_path/$REPO/os/loong64/; flock /tmp/loong-repo-$REPO.lck repo-add $SIGN -R $REPO.db.tar.gz $PKG; curl -X POST http://127.0.0.1/op/uploong/$NAME --data-urlencode 'ver=$VER-$REL'"
```

然后对脚本进行修改，填入服务器信息，就可以使用这个脚本来上传软件包了：

* Bash/Zsh

```bash
for pkg in <pkg1> <pkg2> ...
do
    loong-repo-add <repo> $pkg
done
```

* Fish

```fish
for pkg in <pkg1> <pkg2> ...
    loong-repo-add <repo> $pkg
end
```

# 使用QEMU System测试

QEMU User模式下的容器没有自己的内核，显然无法用于内核测试。因此，我们需要在龙芯实体机或者QEMU System模式下进行内核测试。在实体机下的测试相对比较好理解，这里主要介绍QEMU System模式下的内核测试。

在获取或者自己构建了Loong Arch Linux的qcow2镜像后，我们可以使用`qemu-system-loongarch64`来启动虚拟机，例如：

```bash
qemu-system-loongarch64 \
    -m 6G \
    -cpu la464-loongarch-cpu \
    -machine virt \
    -smp 16 \
    -bios ./QEMU_EFI_9.0.fd \
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
* `-bios ./QEMU_EFI_9.0.fd`：指定QEMU使用的EFI固件
* `-hda <path-to-your-image>`：指定虚拟机使用的qcow2镜像
* `-virtfs local,path=<path-to-your-sharing-directory>,mount_tag=host0,security_model=passthrough,id=host0`：将宿主机的目录目录共享给虚拟机

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

有时候，由于某个功能整体不支持loong64，需要删除`PKGBUILD`中的大段代码；然而，如果这些被删除的代码在Arch Linux官方的维护中存在频繁更改，那么在以后应用`loong.patch`时就很可能会出现冲突。

为了避免这样的情况，我们可以将直接删除改为写成多行注释，例如，如果我们想要删除掉opencv的PKGBUILD中的`package_opencv-cuda()`函数，我们可以在其前面插入`: <<'COMMENT_SEPARATOR'`，在其后面插入`COMMENT_SEPARATOR`，这样就可以在一定程度上避免上游对这个函数的修改导致的冲突。

```PKGBUILD
  # Use a "multi-line comment" to keep patch from rotting
  : <<'COMMENT_SEPARATOR'
  CFLAGS="${CFLAGS} -fno-lto" CXXFLAGS="${CXXFLAGS} -fno-lto" LDFLAGS="${LDFLAGS} -fno-lto" \
  cmake -B build-cuda -S $pkgname $_opts \
      -DBUILD_WITH_DEBUG_INFO=OFF \
      -DCUDA_ARCH_BIN='52-real;53-real;60-real;61-real;62-real;70-real;72-real;75-real;80-real;86-real;87-real;89-real;90-real;90-virtual' \
      -DCUDA_ARCH_PTX='90-virtual'
  cmake --build build-cuda
COMMENT_SEPARATOR
```

此外，由于“主要矛盾”不同，语句插入的原则也发生了变化。比如，一般按照字母顺序来插入新的依赖或者新的选项，但是在这种情况下，我们可以将新的依赖或者新的选项插入到**上下文最不容易被上游修改的地方**，这样可以减少冲突的发生。

由于`PKGBUILD`本质上是一个bash文件，对于新加入的`source`和哈希值等数组的内容，如果要最大程度地避免上游修改带来的冲突，我们可以使用`+=`来添加新的元素，而不是直接修改数组的内容。

```PKGBUILD
source+=(...)
sha256sums+=(...)
```

# Patch的获取

不一定所有需要Patch的软件包都需要自己手动编写Patch，有时候可以从其他地方获取Patch，例如：

* 其他支持loongarch发行版
  * [Gentoo/Loongson Support Overlay](https://github.com/xen0n/loongson-overlay)
  * [ABBS/ACBS tree for AOSC OS package metadata, build configuration, scripts, and patches](https://github.com/AOSC-Dev/aosc-os-abbs)
  * [AOSC Code Tracking Project](https://github.com/AOSC-Tracking)
  * [原Loong Arch Linux项目](https://github.com/loongarchlinux)
* 上游软件包
  * 如果上游已经修复但是没有发布，可以从上游的Git仓库中获取Patch

此外，其他Arch Linux移植项目的Patch也可以参考，例如：

* [Modified Arch Linux packages for archriscv ](https://github.com/felixonmars/archriscv-packages)
  * 其中不针对于RISC-V架构的Patch可能可以直接参考使用，例如：
    * 禁用了仅适用于x86的功能
    * 禁用了仅x86下存在的依赖
    * 禁用了仅x86下存在的编译选项
  * 对于RISC-V架构的Patch，可以参考其Patch的内容，参照维护自己的Patch

# FAQ

## `relocation R_LARCH_B26 out of range`/`relocation R_LARCH_B26 overflow`错误

这个错误信息一般来自链接器，它表示在处理文件时，发生了`R_LARCH_B26`重定位溢出错误。`R_LARCH_B26`是LoongArch架构的一种重定位类型，通常用于跳转指令。它要求目标地址必须在跳转指令可达的范围内（±128 MB），即它只允许一定范围内的偏移量。

这个错误通常发生在编译Chromium、Firefox等大型软件包时，链接器无法找到合适的位置来放置跳转指令。

解决这个问题的方法一般为在编译参数中加入`-mcmodel=medium`来扩大地址空间，使得链接器可以找到合适的位置来放置跳转指令。[^1]

[^1]: [GitHub/Rust PR#120661](https://github.com/rust-lang/rust/pull/120661)

例如，可以在`PKGBUILD`中的`prepare()`或者`build()`函数中加入以下内容：

```bash
prapre() {
    ......

    # Add ` -mcmodel=medium` to CFLAGS etc.
    # to avoid `relocation R_LARCH_B26 overflow`
    export CFLAGS="${CFLAGS} -mcmodel=medium"
    export CXXFLAGS="${CXXFLAGS} -mcmodel=medium"
    export RUSTFLAGS="${RUSTFLAGS} -C code-model=medium"

    ......
}
```

## QEMU User特异性问题

由于QEMU User的实现问题，使用QEMU User模式构建软件包时可能会遇到一些特异性问题，目前已知的问题有：

* 运行过于缓慢导致某些`check`超时报错
* 调用`python`的`multiprocessing`模块的程序**大概率**会**卡死**
  * 也有**可能**发生**内存泄漏**
* `go`语言程序编译有一定概率卡死
* `rustc`在**编译并行线程非常多时**且**项目本身非常大**时可能会卡死
  * 模式触发条件：
    * 48核，磁盘IOPS仅1000，QEMU User编译Firefox
    * 似乎16核就不会触发（至少不太容易触发）
  * 卡死时一般会发现进程中剩下一个`rustc`进程，吃满单核性能，且内存占用较一般的`rustc`进程高（约7GB）
* `gn`在部分场景下有概率卡死并报错
  ```log
  -- GN Done. Made ... targets from ... files in ...ms

  ......

  -- GN FAILED

  Process terminated due to timeout
  ```
  * 状态为`Sleeping`，CPU占用为0%
  * 不太能总结出触发条件
  * 不过需要注意的是，如果修改`gn`配置的patch有误也可能会导致这个问题

（待补充）

### QEMU User典型失败内容列举

* `opus`构建
  * `check`严重超时（>50倍）
* `gimp-help`构建（似乎用到了python的`multiprocessing`模块）
  * 内存泄漏
* 部分测试仅在QEMU User下失败
  * `wayland`的`check`阶段
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

（待补充）

## `pkgctl`从官方`clone`软件包时要求输入用户名和密码

如果使用`pkgctl`从官方克隆软件包时要求输入用户名和密码：

```log
==> Cloning <package-name> ...
Cloning into '<package-name>'...
Username for 'https://gitlab.archlinux.org': 
```

这个时候说明Arch Linux官方**并不存在**这一软件包仓库，一般有以下几种情况：

* 这个软件是仅相关于Loong Arch Linux的软件包，没有由Arch Linux维护
  * 例如`archlinux-lcpu-keyring`，`devtools-loong64`
* 未以`pkgbase`来克隆软件包仓库
  * 注意上游的软件包仓库名是`pkgbase`，而**不一定**是`pkgname`
  * 同一`pkgbase`可能会包括多个`pkgname`的软件包
    * 例如`rust`提供了`rust`、`rust-musl`、`rust-src`、`rust-wasm`等软件包，这些软件包都在`rust`这一仓库中
* 单纯把软件包名敲错了

# TODO

# 更多阅读材料

* [龙芯的Arch Linux移植工作流程 by wszqkzqk](https://wszqkzqk.github.io/2024/08/22/loongarchlinux-port-tips/)
* [ArchWiki](https://wiki.archlinux.org/)
* [Arch Linux Packaging Standards](https://wiki.archlinux.org/title/Arch_packaging_standards)
* [Arch RISC-V Port Wiki](https://github.com/felixonmars/archriscv-packages/wiki)
* [在x86设备上跨架构构建LoongArch的Arch Linux软件包](https://wszqkzqk.github.io/2024/08/08/devtools-loong64/)
* [Arch RISC-V Port Wiki - 我们的工作习惯](https://github.com/felixonmars/archriscv-packages/wiki/%E6%88%91%E4%BB%AC%E7%9A%84%E5%B7%A5%E4%BD%9C%E4%B9%A0%E6%83%AF)
* [Arch RISC-V Port Wiki - 完全新人指南](https://github.com/felixonmars/archriscv-packages/wiki/%E5%AE%8C%E5%85%A8%E6%96%B0%E4%BA%BA%E6%8C%87%E5%8D%97)
