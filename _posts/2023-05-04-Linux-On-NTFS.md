---
layout:     post
title:      在NTFS分区上安装Linux
subtitle:   使用Ventoy和ntfs3实现的对Windows系统全透明的Linux文件系统布局
date:       2023-05-04
author:     wszqkzqk
header-img: img/ventoy/ventoy_bg.webp
catalog:    true
tags:       开源软件 系统安装 系统配置 系统引导
---

## 前言

> 本文主要讨论在NTFS分区上安装Linux的方法
> 笔者实现了完全在Windows可以直接访问的分区上安装完整的Arch Linux操作系统
> 仅使用FAT与NTFS文件系统实现Linux的文件系统布局

笔者在Linux下使用NTFS时无意中发现现在的ntfs3似乎已经支持了较为完整的Linux权限，也支持软链接等特性：

[![#~/img/ventoy/ntfs-usermod.webp](/img/ventoy/ntfs-usermod.webp)](/img/ventoy/ntfs-usermod.webp)

因此意识到：现在在NTFS分区上是不是已经可以直接安装Linux了🤔🤔🤔。笔者尝试了一下，发现确实可以😋😋😋。

* **警告：本文的方法混乱邪恶，仅供学习交流，不建议用于生产环境**
* Linux中有许多文件系统（例如Btrfs、XFS等）**性能、功能都毫不逊色甚至远远强于NTFS**，完全没有必要将Linux安装到NTFS中
* 本文纯粹在笔者好奇心驱使下写出，不一定具有应用上的意义

## 准备

**以Arch Linux环境为例。**

首先需要制作一个Ventoy启动盘，可以参考[使用Ventoy直接引导本地安装的Linux的启动盘制作部分](https://wszqkzqk.github.io/2023/02/12/%E4%BD%BF%E7%94%A8Ventoy%E7%9B%B4%E6%8E%A5%E5%BC%95%E5%AF%BC%E6%9C%AC%E5%9C%B0%E5%AE%89%E8%A3%85%E7%9A%84Linux/#ventoy%E5%90%AF%E5%8A%A8%E7%9B%98%E5%88%B6%E4%BD%9C)。

Ventoy启动盘默认会分为两个分区，第一个是我们的数据分区，第二个为约16 MB的FAT引导分区，**不要对引导分区进行任何操作**。数据分区的默认格式为exfat，我们需要手动将其格式化为NTFS，可以使用`sudo mkfs.ntfs /dev/sdXn`命令，其中`/dev/sdXn`是分区设备名。（需要安装`ntfs-3g`）

## 安装

指定以`ntfs3`为挂载类型，挂载数据分区：

```bash
sudo mount -t ntfs3 /dev/sdXn /mnt
```

参考Arch Linux官方的[安装指南](https://wiki.archlinuxcn.org/wiki/%E5%AE%89%E8%A3%85%E6%8C%87%E5%8D%97)进行安装。

先安装较基本的软件包，这里需要用到`pacstrap`命令，如果提示找不到该命令，可能是相关软件包没有安装，需要先在主系统中安装`arch-install-scripts`：

```bash
sudo pacman -S --needed arch-install-scripts
```

然后执行

```bash
sudo pacstrap -c -K /mnt --needed \
        base base-devel linux linux-firmware \
        amd-ucode intel-ucode \
        btrfs-progs xfsprogs f2fs-tools nilfs-utils dosfstools exfatprogs ntfs-3g lvm2 \
        sof-firmware networkmanager network-manager-applet nm-connection-editor \
        nano vim man-db man-pages texinfo \
        noto-fonts-cjk noto-fonts-emoji
```

然后再选择一个DM安装，以在不同桌面环境间较通用LightDM为例：

```bash
sudo pacstrap -c -K /mnt --needed lightdm lightdm-gtk-greeter lightdm-gtk-greeter-settings
```

再选择一个桌面环境，以Xfce为例：

```bash
sudo pacstrap -c -K /mnt --needed xfce4 xfce4-goodies
```

安装完成后，使用`genfstab`生成`fstab`文件：

```bash
sudo su
genfstab -U /mnt >> /mnt/etc/fstab
```

`fstab`在自动生成后可能还需要手动编辑，例如可以加入`noatiome`挂载选项等。


使用`arch-chroot`进入新系统：

```bash
sudo arch-chroot /mnt
```

设置时区：

```bash
ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
hwclock --systohc
```

设置本地化：

```bash
sed -i 's/#en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/g' /etc/locale.gen
sed -i 's/#zh_CN.UTF-8 UTF-8/zh_CN.UTF-8 UTF-8/g' /etc/locale.gen
locale-gen
echo 'LANG=en_US.UTF-8' > /etc/locale.conf
```

设置主机名：

```bash
echo 主机名 > /etc/hostname
```

设置root密码：

```bash
passwd
```

启用lightdm与网络管理器：

```bash
systemctl enable lightdm.service
systemctl enable NetworkManager.service
```

创建非root账户：

```bash
useradd -m 用户名
```

设定用户密码：

```bash
passwd 用户名
```

将用户加入`wheel`用户组，以便支持`sudo`权限：

```bash
usermod -aG wheel 用户名
```

编辑`sudo`配置，为`wheel`组加入`sudo`使用权限：

```bash
EDITOR=nano visudo
```

在编辑时取消`%wheel      ALL=(ALL): ALL`一行的注释即可。

这里安装其实已经完成，但是由于Linux下没有NTFS的fsck支持，我们还需要编辑`/etc/mkinitcpio.conf`，在`HOOKS`中去掉`fsck`。

如果需要更混乱邪恶地将**这个设备整体放到QEMU下作为虚拟机启动**，还需要在`/etc/mkinitcpio.conf`中添加几个内核模块：

```
MODULES=(ntfs3 virtio virtio_blk virtio_pci virtio_net)
```

然后再执行`mkinitcpio -P`，以生成新的initramfs。

## Ventoy引导配置

Ventoy引导配置文件位于`ventoy/grub.cfg`。我们需要在其中添加一个新的菜单项，以引导我们的新系统。

首先在数据分区的根目录下创建好`ventoy`文件夹和`ventoy/grub.cfg`配置文件，然后在`ventoy/grub.cfg`中添加以下内容：

```
menuentry 'Arch Linux on NTFS' --class arch --class gnu-linux --class gnu --class os $menuentry_id_option 'gnulinux-simple-XXXXXXXXXXXXXXXX' {
        set gfxpayload=keep
        insmod gzio
        insmod part_gpt
        insmod ntfs
        search --no-floppy --fs-uuid --set=root XXXXXXXXXXXXXXXX
        echo    'Loading Linux kernel...'
        linux   /boot/vmlinuz-linux rootfstype=ntfs3 root=UUID=XXXXXXXXXXXXXXXX rw
        echo    'Loading initramfs...'
        initrd  /boot/intel-ucode.img /boot/amd-ucode.img /boot/initramfs-linux.img
} 

menuentry '<-- Return to previous menu [Esc]' --class=vtoyret VTOY_RET {
    echo 'Return ...'
}
```

注意将`$vtoydev,gptX`中的`X`替换为实际的编号，将`XXXXXXXXXXXXXXXX`替换为实际的NTFS分区UUID。该配置的关键在于：

* 使用`insmod ntfs`加载`ntfs`模块
  * 使得gurb能够进入NTFS分区访问`vmlinuz`与`initramfs`镜像
* 指定`rootfstype=ntfs3`
  * 否则在启动时会出现根分区的挂载错误

## Ventoy镜像搜索配置

将完整的操作系统安装进Ventoy的数据分区以后，Ventoy仍然会将分区下的每个文件扫描一遍，以确定是不是镜像，这会导致启动时的镜像搜索时间过长。为了解决这个问题，我们可以在Ventoy的配置文件中指定需要扫描文件夹。

例如，如果我们仅需要搜索`ISOs`目录下的文件，可以创建`ventoy/ventoy.json`并添加以下内容：

```json
{
    "control":[
        { "VTOY_DEFAULT_SEARCH_ROOT": "/ISOs" }
    ]
}
```

这样，Ventoy就只会搜索`ISOs`目录下的文件，而不会搜索其他文件，加快启动速率。

## 测试及效果

安装完成后，重启进入Ventoy，按`F6`，选择新添加的菜单项，即可进入新系统。

目前看来系统功能均可以正常使用，未发现明显问题。

[![#~/img/ventoy/linux-on-ntfs.webp](/img/ventoy/linux-on-ntfs.webp)](/img/ventoy/linux-on-ntfs.webp)

## 捐赠

|  **支付宝**  |  **微信支付**  |
|  :----:  |  :----:  |
|  [![](/img/donate-alipay.webp)](/img/donate-alipay.webp)  |  [![](/img/donate-wechatpay.webp)](/img/donate-wechatpay.webp)  |
