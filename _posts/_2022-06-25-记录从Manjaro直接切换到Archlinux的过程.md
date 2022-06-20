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

利用`pacman -Qqm`可以列出现在源中没有的本地软件包，有一些可能是AUR的
