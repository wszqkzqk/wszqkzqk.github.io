---
layout:       post
title:        记录从Manjaro直接切换到Archlinux的过程
subtitle:     折腾日志
date:         2022-06-25
author:       星外之神
header-img:   img/
catalog:      true
tags:         Linux Manjaro Archlinux Pacman 开源软件
---

## 说明

本文写于该切换完整完成后，并非实时更新，内容可能不能精确反映当时操作情况

## 更改镜像源

首先需要把`/ect/pacman.d/mirrorlist`改成Archlinux的源，在中国可以直接改成：

```
Server = https://mirrors.tuna.tsinghua.edu.cn/archlinux/$repo/os/$arch
Server = http://mirrors.aliyun.com/archlinux/$repo/os/$arch
```

感觉北大访问隔壁的镜像源比本地的快QwQ（

为了切换到Archlinux,还需要编辑`/etc/pacman.conf`，在`HoldPkg = pacman glibc manjaro-system`中删除`manjaro-system`，同时，注释掉`SyncFirst = manjaro-system archlinux-keyring manjaro-keyring`一行，与Archlinux保持一致

## 添加Archlinuxcn源并安装yay

编辑`/etc/pacman.conf`，在文本后添加：

```
[archlinuxcn]
SigLevel = Optional TrustedOnly
Server = https://mirrors.ustc.edu.cn/archlinuxcn/$arch
```

然后进行软件仓库同步并安装新的keyring：

```shell
sudo pacman -Syy archlinux-keyring
```

再从Archlinuxcn源中直接安装AUR助手yay：
```shell
sudo pacman -S yay
```

## 切换软件

由于Manjaro和Archlinux的软件包并非一一对应，想要更改了镜像源就直接切换升级是不可能的，还需要进行一些操作

### bash

首先，Manjaro和Archlinux的`bash`封装不同，Manjaro将bash本身与bash的配置文件`.bashrc`封装成了`bash`和`bashrc-manjaro`两个软件包，并且`bash`依赖于`bashrc-manjaro`，所以需要对现有Manjaro系统的文件进行编辑

可以将`bashrc-manjaro`的文件先转移备份到其他地方，再覆盖安装Archlinux的`bash`：

```shell
sudo mv /etc/bash.bashrc /etc/bash.bashrc.bak
sudo mv /etc/skel/.bashrc /etc/skel/.bashrc.bak
sudo pacman -S bash
```
安装成功后，再卸载`bashrc-manjaro`软件包：

```shell
sudo pacman -R bashrc-manjaro
```

这样就不会有依赖错误和文件冲突了，但是这样的卸载操作可能会将Archlinux的bash软件包的`/etc/skel/.bashrc`保存为`/etc/skel/.bashrc.pacsave`，所以还需要执行：

```shell
sudo mv /etc/skel/.bashrc.pacsave /etc/skel/.bashrc
```

如果不喜欢刚才带来的文件冗余，也可以删除之前生成的`.bak`文件：

```shell
sudo rm /etc/bash.bashrc.bak /etc/skel/.bashrc.bak
```

### Linux内核

Manjaro与Archlinux的内核打包机制也不一样，Manjaro是按版本打包发布，升级内核版本一般需要手动切换，包名一般为`linux5xx`、`linux5xx-header`这样的形式，而Archlinux的内核仍才采用滚动更新机制，最新稳定版内核包名为`linux`、`linux-headers`，LTS内核包名为`linux-lts`、`linux-lts-header`，因此切换后需要卸载掉Manjaro的内核再安装Archlinux的内核：

```shell
# 以安装了linux515与inux518内核的Manjaro系统为例
sudo pacman -S linux linux-headers linux-zen linux-zen-headers
sudo pacman -R linux515 linux515-headers linux518 linux518-headers
```

## Manjaro特色软件

Archlinux的软件源里面显然也不会有Manjaro的特色软件，因此这些软件也需要进行替换或者删除

利用`pacman -Qqm`可以列出现在源中没有的本地软件包，有一些可能是AUR的或自己构建的，而其余的则是Manjaro的“前朝余孽”

首先，需要将Manjaro的`pacman-mirrors`替换成Archlinux的`pacman-mirrorlist`，然而，直接采用`sudo pacman -S pacman-mirrorlist`并不可行，因为我们现在还没有移除Manjaro自身的包管理相关软件，这些软件依赖于Manjaro的`pacman-mirrors`，需要先行卸载：

```shell
sudo pacman -Rc libpamac python-manjaro-sdk
```

这个时候被卸载的可能不只是Manjaro的程序，如果有其他的可以在卸载之后再安装回来

然后，在对Manjaro的`pacman-mirrors`进行替换：

```shell
sudo pacman -S pacman-mirrorlist
```

现在即可以成功安装

这个步骤完成后，就可以删除其他在`pacman -Qqm`中列出的Manjaro特色软件了

一般来说，除了`manjaro-*`需要删除以外，因为Archlinux与Manjaro的硬件配置机制不同，`mhwd*`也需要删除，这一步建议手动排查，但是也可以进行直接删除：

```shell
sudo pacman -R $(pacman -Qqm|grep manjaro)
sudo pacman -R $(pacman -Qqm|grep mhwd)
```

其他残余软件也可以按需删除

## 软件包切换

很多Manjaro软件包的包名和版本号都与Archlinux一样，但是内容未必一样（最简单的例子：发行版信息`lsb-release`），所以建议切换后进行软件包的重新安装，执行完前几节的步骤后依赖问题已基本解决，可以继续执行：

```shell
sudo pacman -Syu $(pacman -Qqn)
```

## grub

Manjaro默认使用了自己的主题，而Manjaro的主题文件已经在之前被我们删除，所以grub主题文件需要重新指定

这里我不想折腾，直接使用了grub自带的starfield主题：
- 打开`/etc/default/grub`
- 找到`GRUB_THEME=`一行
- 把`=`后的内容改成`"/usr/share/grub/themes/starfield/theme.txt"`
- 完成后，执行`sudo grub-mkconfig -o /boot/grub/grub.cfg`重新生成`grub.cfg`

## zsh

Manjaro默认配置好了zsh

## fcitx5

Manjaro通过依赖的方式在安装fcitx5的时候通过向`/etc/xdg`添加`fcitx5`文件夹及配置文件自动启用了fcitx5在软件中的输入功能
