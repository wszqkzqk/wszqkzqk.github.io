---
layout:     post
title:      Arch Linux安全启动的终极方案
subtitle:   共享分区下Ubuntu引导的Arch Linux系统
date:       2023-04-25
author:     wszqkzqk
header-img: img/Linux-distro-logo/archlinux.webp
catalog:    true
tags:       开源软件 系统引导 系统配置 系统安装
---

## 前言

Arch Linux是一个非常优秀的Linux发行版，但是它并不支持安全启动。虽然笔者的笔记本的安全启动长期处于关闭状态，但是笔者还是想把自己的移动硬盘打造成随处可用的移动系统，这就需要支持不依赖于特定设备注册是安全启动。因此，笔者就想到了一个办法，就是在Arch Linux上安装Ubuntu，然后**使用Ubuntu的grub引导来引导Arch Linux**。这样，Arch Linux就可以支持安全启动了😜😜😜。

此外，割区安装另一个系统总需要预留不少空闲，而如果以后不常使用Ubuntu,往往会造成浪费，而如果分配过小，在以后要用时又不方便扩容，较为麻烦。为了最大化利用空间，也简化安装流程，笔者充分利用了Btrfs的**子卷**功能，将Arch Linux和Ubuntu安装在**同一个Btrfs文件系统的不同子卷下**，实现了共享分区容量、简化分区布局的效果。

## 理想方案

由于我们需要Ubuntu作引导，因此在理想情况下，我们应该安装Ubuntu，然后再在已经安装好Ubuntu的分区中创建新子卷安装Arch Linux。Arch Linux安装的灵活性使得这样不仅能够方便引导及子卷的配置，还可以将Arch Linux的安装直接搬到[已经安装好的Ubuntu系统下进行](https://wiki.archlinuxcn.org/wiki/%E4%BB%8E%E7%8E%B0%E6%9C%89_Linux_%E5%8F%91%E8%A1%8C%E7%89%88%E5%AE%89%E8%A3%85_Arch_Linux)，甚至可以省略Arch Linux镜像的下载步骤😋😋😋。

### Ubuntu安装

Ubuntu安装较为简单，只需要注意使用Btrfs格式的分区即可，此处不再赘述。

### Arch Linux安装

在已经安装有Ubuntu的分区中创建新子卷，可以放在一个目录下，例如：`/subsystems/@arch`、`/subsystems/@arch-home`、`/subsystems/@arch-tmp`等，安装Arch Linux，需要注意挂载要按照这里设定的子卷布局：

```bash
sudo mount /dev/sdXn -o subvol=subsystems/@arch /mnt
sudo mount /dev/sdXn -o subvol=subsystems/@arch-home /mnt/home
sudo mount /dev/sdXn -o subvol=subsystems/@arch-tmp /mnt/var/tmp
...（挂载其他所需子卷）...
```

然后正常在`/mnt`挂载点处执行`pacstrap`等[Arch Linux的一般安装过程](https://wiki.archlinuxcn.org/wiki/%E5%AE%89%E8%A3%85%E6%8C%87%E5%8D%97)，完成Arch Linux的基本安装。

### 引导配置

在Arch Linux安装完成后，我们需要配置Ubuntu的grub引导来引导Arch Linux。我们需要在Ubuntu下编辑`/etc/grub.d/40_custom`文件，在末尾添加如下内容：

```bash
menuentry "Arch Linux" {
    insmod part_gpt
    insmod btrfs
    set root='(hd0,gpt3)' # 这里的gpt3是Arch Linux所在的分区
    search --no-floppy --fs-uuid --set=root 0f0f0f0f-0f0f-0f0f-0f0f-0f0f0f0f0f0f # 这里的UUID是Arch Linux所在分区的UUID
    linux /subsystems/@arch/boot/vmlinuz-linux root=UUID=0f0f0f0f-0f0f-0f0f-0f0f-0f0f0f0f0f0f rw rootflags=subvol=subsystems/@arch # vmlinuz-linux应当替换为实际内核文件名
    initrd /subsystems/@arch/boot/initramfs-linux.img # initramfs-linux.img应当替换为实际initramfs镜像文件名
}
```

然后执行`sudo update-grub`，重启即可。

## 先安装Arch Linux再安装Ubuntu

如果在之前已经安装了Arch Linux，后续再安装Ubuntu也可以实现引导，但是由于Ubuntu安装一般不方便自定义子卷，因此需要先改变Btrfs子卷布局。

### 改变Btrfs子卷布局

在另一个Linux系统或者Linux Live CD中，挂载Arch Linux所在分区，然后在顶级子卷下创建新的`subsystems`子卷，然后将原来的子卷移动到`subsystems`子卷下，例如：

```bash
sudo mount /dev/sdXn /mnt
sudo btrfs subvolume create /mnt/subsystems
sudo mv /mnt/@ /mnt/subsystems/@arch
sudo mv /mnt/@home /mnt/subsystems/@arch-home
sudo mv /mnt/@tmp /mnt/subsystems/@arch-tmp
...（移动其他所需子卷）...
```

### 编辑Arch Linux的`fstab`文件

编辑Arch Linux的`fstab`文件，将原来的子卷挂载点改为`/subsystems/@arch`等，此外，由于我们将改用Ubuntu引导，需要删除`efi`分区在Arch Linux下的挂载项：

```bash
UUID=0f0f0f0f-0f0f-0f0f-0f0f-0f0f0f0f0f0f / btrfs rw,noatime,subvol=/subsystems/@arch 0 0
UUID=0f0f0f0f-0f0f-0f0f-0f0f-0f0f0f0f0f0f /home btrfs rw,noatime,subvol=/subsystems/@arch-home 0 0
UUID=0f0f0f0f-0f0f-0f0f-0f0f-0f0f0f0f0f0f /var/tmp btrfs rw,noatime,subvol=/subsystems/@arch-tmp 0 0
...（挂载其他所需子卷）...
```

### 安装Ubuntu

Ubuntu安装较为简单，此处只需要注意安装时不要格式化原来的分区，而是安装到原有分区的新子卷中。

### 引导配置

在Ubuntu安装完成后，我们需要配置Ubuntu的grub引导来引导Arch Linux。我们需要在Ubuntu下编辑`/etc/grub.d/40_custom`文件，添加如下内容：

```bash
menuentry "Arch Linux" {
    insmod part_gpt
    insmod btrfs
    set root='(hd0,gpt3)' # 这里的gpt3是Arch Linux所在的分区
    search --no-floppy --fs-uuid --set=root 0f0f0f0f-0f0f-0f0f-0f0f-0f0f0f0f0f0f # 这里的UUID是Arch Linux所在分区的UUID
    linux /subsystems/@arch/boot/vmlinuz-linux root=UUID=0f0f0f0f-0f0f-0f0f-0f0f-0f0f0f0f0f0f rw rootflags=subvol=subsystems/@arch
    initrd /subsystems/@arch/boot/initramfs-linux.img
}
```

然后执行`sudo update-grub`，重启即可。

## 后续整理

如果我们~~不怕折腾~~想要干净统一的子卷布局，也可以用类似的方法，将Ubuntu的子卷移动到`subsystems`子卷下。

首先当然是移动Ubuntu子卷，这个过程可以在已经安装好的Arch Linux下进行，也可以在其他Linux系统或者Live CD中进行。

```bash
sudo mount /dev/sdXn /mnt
sudo mv /mnt/@ /mnt/subsystems/@ubuntu
sudo mv /mnt/@home /mnt/subsystems/@ubuntu-home
...（（移动其他所需子卷）...
```

然后编辑Ubuntu的`fstab`文件，将子卷改为新的位置：

```bash
UUID=0F0F-0F0F /boot/efi vfat rw,noatime,umask=0077 0 0 # 这里的efi分区不需要改变
UUID=0f0f0f0f-0f0f-0f0f-0f0f-0f0f0f0f0f0f / btrfs rw,noatime,subvol=/subsystems/@ubuntu 0 0
UUID=0f0f0f0f-0f0f-0f0f-0f0f-0f0f0f0f0f0f /home btrfs rw,noatime,subvol=/subsystems/@ubuntu-home 0 0
...（挂载其他所需子卷）...
```

卸载`/mnt`下的分区，并重新挂载为Ubuntu所在的子卷：
    
```bash
sudo umount /mnt
sudo mount /dev/sdXn -o subvol=subsystems/@ubuntu /mnt
sudo mount /dev/sdXn -o subvol=subsystems/@ubuntu-home /mnt/home
...（挂载其他所需子卷）...
```

然后使用Arch Linux自带的`arch-install-scripts`工具`chroot`到Ubuntu子卷中，重新构建Ubuntu的grub引导，如果没有安装`arch-install-scripts`，可以使用`sudo pacman -S arch-install-scripts`安装。

```bash
sudo arch-chroot /mnt
```

在`chroot`环境中执行：

```bash
/sbin/update-grub
```

以更新Ubuntu的引导信息，最后重启即可。

## 捐赠

|  **支付宝**  |  **微信支付**  |
|  :----:  |  :----:  |
|  [![](/img/donate-alipay.webp)](/img/donate-alipay.webp)  |  [![](/img/donate-wechatpay.webp)](/img/donate-wechatpay.webp)  |
