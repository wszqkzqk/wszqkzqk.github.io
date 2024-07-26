---
layout:     post
title:      通用共享的内核模块和initramfs
subtitle:   可跨设备启动与跨发行版内核混搭架构
date:       2024-07-26
author:     wszqkzqk
header-img: img/bg-mountain-darken.webp
catalog:    true
tags:       开源软件 系统配置 Linux archlinux
---

## 前言

笔者的移动固态硬盘上使用了一个Btrfs分区通过多子卷来存放多个Linux发行版。为了在未关闭安全启动的设备上也能正常使用所有发行版，笔者选择使用Ubuntu的GRUB来引导所有的发行版，由于Ubuntu的引导程序有可信签名，可以在未关闭安全启动的设备上正常引导。但是，在开启了安全启动的设备上，使用具有可信签名的GRUB是不能引导未签名的内核的，因此，在这种情况下，笔者需要在所有发行版中使用Ubuntu的内核。

为了实现这一目标，笔者需要在所有发行版中共享内核模块，这样，即使在开启了安全启动的设备上，也可以正常引导所有发行版；同时，笔者也希望至少在关闭了安全启动的设备上，可以使用各自的内核。

## 设计

### 子卷布局

为了方便管理，笔者提出了以下子卷布局：

* `$DISTRO_NAME`：一般文件夹，存放某个发行版专用的子卷
  * `$DISTRO_NAME/@`：子卷，存放发行版的根目录
  * `$DISTRO_NAME/@home`：子卷，存放发行版的用户目录
* `@arch-like-cache`：子卷，存放Arch Linux及其衍生发行版`/var/cache`下的内容
* `@tmp`：子卷，存放临时文件，挂载于Arch Linux及其衍生发行版的`/var/tmp`下
* `@sharingkernelmodules`：子卷，存放共享的内核模块，挂载于所有发行版的`/usr/lib/modules`下

需要在多个发行版之间共用的内容以子卷的形式在不同的发行版上挂载。在这样的架构中，需要保证各个发行版中安装的内核的名称不同，以避免冲突。在不同发行版下，均可获取所有发行版的内核模块，保证了以任何内核启动任意发行版时都能够正常运行。

列出一份`fstab`示例：

```bash
# Static information about the filesystems.
# See fstab(5) for details.

# <file system> <dir> <type> <options> <dump> <pass>
# /dev/sda3 LABEL=MultiLinux
UUID=0f0f0f0f-0f0f-0f0f-0f0f-0f0f0f0f0f0f	/         	btrfs     	lazytime,ssd,discard=async,subvol=/cachy/@	0 0

# /dev/sda3 LABEL=MultiLinux
UUID=0f0f0f0f-0f0f-0f0f-0f0f-0f0f0f0f0f0f	/home     	btrfs     	lazytime,ssd,discard=async,subvol=/cachy/@home	0 0

# /dev/sda3 LABEL=MultiLinux
UUID=0f0f0f0f-0f0f-0f0f-0f0f-0f0f0f0f0f0f	/var/cache	btrfs     	lazytime,ssd,discard=async,subvol=/@arch-like-cache	0 0

# /dev/sda3 LABEL=MultiLinux
UUID=0f0f0f0f-0f0f-0f0f-0f0f-0f0f0f0f0f0f	/var/tmp  	btrfs     	lazytime,ssd,discard=async,subvol=/@tmp	0 0

# Sharing kernel modules
UUID=0f0f0f0f-0f0f-0f0f-0f0f-0f0f0f0f0f0f	/usr/lib/modules	btrfs     	lazytime,ssd,discard=async,subvol=/@sharingkernelmodules	0 0
```

### 引导配置

在用于引导的Ubuntu下编辑`/etc/grub.d/40_custom`文件，添加各个发行版的引导项，例如：

```bash
# 由于各发行版实际上位于同一个Btrfs分区，UUID相同，设置变量以便引用
uuid="0f0f0f0f-0f0f-0f0f-0f0f-0f0f0f0f0f0f"
resume_uuid="0d0d0d0d-0d0d-0d0d-0d0d-0d0d0d0d0d0d"

menuentry 'Cachy OS' --class arch --class gnu-linux --class gnu --class os {
        load_video
        set gfxpayload=keep
        insmod part_gpt
        insmod btrfs
        search --no-floppy --fs-uuid --set=root ${uuid}
        echo    'Loading Linux kernel...'
        linux   /cachy/@/boot/vmlinuz-linux* root=UUID=${uuid} rw rootflags=subvol=cachy/@ nowatchdog nvme_load=YES loglevel=3 resume=UUID=${resume_uuid}
        echo    'Loading initramfs...'
        initrd  /cachy/@/boot/intel-ucode.img /cachy/@/boot/amd-ucode.img /cachy/@/boot/initramfs-linux*.img
}
```

此外，为了在开启了安全启动的设备上也能正常引导，还需要添加一个使用Ubuntu的内核启动的备用引导项：

```bash
menuentry 'Cachy OS with Ubuntu Kernel' --class arch --class gnu-linux --class gnu --class os {
        load_video
        set gfxpayload=keep
        insmod part_gpt
        insmod btrfs
        search --no-floppy --fs-uuid --set=root ${uuid}
        echo    'Loading Linux kernel...'
        linux   /ubuntu/@/boot/vmlinuz root=UUID=${uuid} rw rootflags=subvol=cachy/@ nowatchdog nvme_load=YES loglevel=3 resume=UUID=${resume_uuid}
        echo    'Loading initramfs...'
        initrd  /ubuntu/@/boot/initrd.img
}
```

### Arch Linux的`mkinitcpio`配置

Arch Linux使用的`mkinitcpio`默认会创建两个`initramfs`镜像，一个是默认使用了`autodetect`钩子的`initramfs-linux*.img`，仅包含了当前所需的模块；另一个是默认禁用了`autodetect`钩子的`initramfs-linux-fallback*.img`，包含了所有模块。

由于该设计位于移动固态硬盘上，可能会在多个不同的设备上使用，因此，使用`autodetect`的镜像并没有意义，应当直接创建一个包含所有模块的`initramfs`镜像。只需要在`/etc/mkinitcpio.conf`中编辑`HOOKS`变量，去掉`autodetect`钩子，再执行`mkinitcpio -P`即可。

当然，如果不想修改`HOOKS`变量，也可以直接将GRUB引导项中的`initramfs-linux*.img`替换为`initramfs-linux*-fallback.img`，以便默认使用包含所有模块的`initramfs`镜像。

除了可以在不同设备上工作外，使用完整的`initramfs`镜像还可以在一定程度上避免在Arch Linux内核**滚动升级后出现部分模块无法加载的问题**，可以在更新内核后不立即重启。不过，这样的`initramfs`镜像会比较大，会**增加启动时间**；但是在笔者的设备上，即使是完整的`initramfs`镜像加载也非常快速，因此笔者已经直接在`/etc/mkinitcpio.conf`中去掉了`autodetect`钩子。

Ubuntu等发行版使用的`initramfs-tools`默认`MODULES=most`，即包含了大部分模块，因此不需要额外配置。
