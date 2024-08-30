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

其中给出了发生soname变化的软件包名`llvm-libs`，以及变化的soname：`libLLVM.so`、`libLTO.so`、`libRemarks.so`。

我们可以在获得了变化的soname后，通过`sogrep`来查找链接到这些库的软件包：

* Bash/Zsh

```bash
for lib in libLLVM.so libLTO.so libRemarks.so
do
    sogrep -r all $lib
done | sort | uniq
```

* Fish

```fish
for lib in libLLVM.so libLTO.so libRemarks.so
    sogrep -r all $lib
end | sort | uniq
```

这样我们就可以找到需要重新构建的软件包列表。

考虑到一般情况下，同一软件的多个`.so`文件的soname变化是同时发生的，我们有时候也可以通过对软件包查找来获取所有需要重新构建的软件包：

* Bash/Zsh

```bash
for lib in $(find-libprovides <path-to-your-pkg> | sed 's/=.*//g')
do
    sogrep -r all $lib
done | sort | uniq
```

* Fish

```fish
for lib in $(find-libprovides <path-to-your-pkg> | sed 's/=.*//g')
    sogrep -r all $lib
end | sort | uniq
```

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

```bash
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

if [[ ! -e $PKG_PATH.sig ]]; then
    gpg --detach-sign --use-agent $PKG_PATH
    if [[ ! -e $PKG_PATH.sig ]]; then
        echo "$PKG_PATH.sig not found! Exiting..."
        exit 1
    fi
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
    -smp 8 \
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
* `-smp 8`：使用8个CPU核心
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
        # 直接使用mount命令挂载
        sudo mount /dev/nbd0p2 <mount-point>
        # 或者使用udisksctl挂载
        udisksctl mount -b /dev/nbd0p2
        ```
* 然后可以在挂载的目录下进行修复，例如：
    ```bash
    sudo systemd-nspawn -aD <mount-point> --bind <path-to-your-sharing-directory>:<mount-point>
    ```

修复完成后，卸载分区和nbd设备：

```bash
sudo umount <mount-point>
# 或者，如果用的是udisksctl
udisksctl unmount -b /dev/nbd0p2
```

```bash
sudo qemu-nbd --disconnect /dev/nbd0
sudo rmmod nbd
```

然后即可重新启动QEMU System虚拟机进行测试。

# TODO

# 更多阅读材料

* [龙芯的Arch Linux移植工作流程 by wszqkzqk](https://wszqkzqk.github.io/2024/08/22/loongarchlinux-port-tips/)
* [ArchWiki](https://wiki.archlinux.org/)
* [Arch Linux Packaging Standards](https://wiki.archlinux.org/title/Arch_packaging_standards)
* [Arch RISC-V Port Wiki](https://github.com/felixonmars/archriscv-packages/wiki)
* [在x86设备上跨架构构建LoongArch的Arch Linux软件包](https://wszqkzqk.github.io/2024/08/08/devtools-loong64/)
* [Arch RISC-V Port Wiki - 我们的工作习惯](https://github.com/felixonmars/archriscv-packages/wiki/%E6%88%91%E4%BB%AC%E7%9A%84%E5%B7%A5%E4%BD%9C%E4%B9%A0%E6%83%AF)
* [Arch RISC-V Port Wiki - 完全新人指南](https://github.com/felixonmars/archriscv-packages/wiki/%E5%AE%8C%E5%85%A8%E6%96%B0%E4%BA%BA%E6%8C%87%E5%8D%97)
