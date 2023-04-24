---
layout:     post
title:      Arch Linux安全启动的终极方案
subtitle:   共享分区下Ubuntu引导的Arch Linux系统
date:       2023-04-25
author:     wszqkzqk
header-img: img/bg-sunrise.webp
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

然后正常在`/mnt`挂载点处执行`pacstrap`等[Arch Linux的一般安装过程](https://wiki.archlinuxcn.org/wiki/%E5%AE%89%E8%A3%85%E6%8C%87%E5%8D%97)。


