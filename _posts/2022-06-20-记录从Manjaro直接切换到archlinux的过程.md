---
layout:       post
title:        记录从Manjaro直接切换到Arch Linux的过程
subtitle:     折腾日志
date:         2022-06-20
author:       wszqkzqk
header-img:   img/switch-manjaro-to-archlinux-bg.webp
catalog:      true
tags:         Linux Manjaro archlinux Pacman 开源软件 系统配置 系统安装
---

<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="330" height="86" src="//music.163.com/outchain/player?type=2&id=444356916&auto=1&height=66"></iframe>

## 说明

本文写于该切换完整完成后，并非实时更新，内容可能不能精确反映当时操作情况

## 更改镜像源

首先需要把`/ect/pacman.d/mirrorlist`改成Arch Linux的源，在中国可以直接改成：

```
Server = https://mirrors.tuna.tsinghua.edu.cn/archlinux/$repo/os/$arch
Server = https://mirrors.aliyun.com/archlinux/$repo/os/$arch
```

感觉北大访问隔壁的镜像源比校内的快QwQ（

为了切换到Arch Linux,还需要编辑`/etc/pacman.conf`，在`HoldPkg = pacman glibc manjaro-system`中删除`manjaro-system`，同时，注释掉`SyncFirst = manjaro-system archlinux-keyring manjaro-keyring`一行，与Arch Linux保持一致

## 添加archlinuxcn源并安装yay

编辑`/etc/pacman.conf`，在文本后添加：

```
[archlinuxcn]
SigLevel = Optional TrustedOnly
Server = https://mirrors.tuna.tsinghua.edu.cn/archlinuxcn/$arch
```

然后进行软件仓库同步并安装新的keyring：

```shell
sudo pacman -Syy archlinuxcn-keyring
```

再从archlinuxcn源中直接安装AUR助手yay：

```shell
sudo pacman -S yay
```

## 切换软件依赖

由于Manjaro和Arch Linux的软件包并非一一对应，想要更改了镜像源就直接切换升级是不可能的，还需要进行一些操作

### Bash

首先，Manjaro和Arch Linux的`bash`封装不同，Manjaro将bash本身与bash的配置文件`.bashrc`封装成了`bash`和`bashrc-manjaro`两个软件包，并且`bash`依赖于`bashrc-manjaro`，所以需要对现有Manjaro系统的文件进行编辑

可以将`bashrc-manjaro`的文件先转移备份到其他地方，再覆盖安装Arch Linux的`bash`：

```shell
sudo mv /etc/bash.bashrc /etc/bash.bashrc.bak
sudo mv /etc/skel/.bashrc /etc/skel/.bashrc.bak
sudo pacman -S bash
```
安装成功后，再卸载`bashrc-manjaro`软件包：

```shell
sudo pacman -R bashrc-manjaro
```

这样就不会有依赖错误和文件冲突了，但是这样的卸载操作可能会将Arch Linux的bash软件包的`/etc/skel/.bashrc`保存为`/etc/skel/.bashrc.pacsave`，所以还需要执行：

```shell
sudo mv /etc/skel/.bashrc.pacsave /etc/skel/.bashrc
```

如果不喜欢刚才带来的文件冗余，也可以删除之前生成的`.bak`文件：

```shell
sudo rm /etc/bash.bashrc.bak /etc/skel/.bashrc.bak
```

### Linux内核

Manjaro与Arch Linux的内核打包机制也不一样，Manjaro是按版本打包发布，升级内核版本一般需要手动切换，包名一般为`linux5xx`、`linux5xx-header`这样的形式，而Arch Linux的内核仍才采用滚动更新机制，最新稳定版内核包名为`linux`、`linux-headers`，LTS内核包名为`linux-lts`、`linux-lts-header`，因此切换后需要卸载掉Manjaro的内核再安装Arch Linux的内核：

```shell
# 以安装了linux515与inux518内核的Manjaro系统为例
sudo pacman -S linux linux-headers linux-zen linux-zen-headers
sudo pacman -R linux515 linux515-headers linux518 linux518-headers
```

### Manjaro特色软件

Arch Linux的软件源里面显然也不会有Manjaro的特色软件，因此这些软件也需要进行替换或者删除

利用`pacman -Qqm`可以列出现在源中没有的本地软件包，有一些可能是AUR的或自己构建的，而其余的则是Manjaro的“前朝余孽”

首先，需要将Manjaro的`pacman-mirrors`替换成Arch Linux的`pacman-mirrorlist`，然而，直接采用`sudo pacman -S pacman-mirrorlist`并不可行，因为我们现在还没有移除Manjaro自身的包管理相关软件，这些软件依赖于Manjaro的`pacman-mirrors`，需要先行卸载：

```shell
sudo pacman -Rc libpamac python-manjaro-sdk
```

这个时候被卸载的可能不只是Manjaro的程序，如果有其他的可以在卸载之后再安装回来（我的`python-systemd`与`pyside6`需要重新安装）

然后，在对Manjaro的`pacman-mirrors`进行替换：

```shell
sudo pacman -S pacman-mirrorlist
```

现在即可以成功安装

这个步骤完成后，就可以删除其他在`pacman -Qqm`中列出的Manjaro特色软件了

一般来说，除了`manjaro-*`需要删除以外，因为Arch Linux与Manjaro的硬件配置机制不同，`mhwd*`也需要删除，这一步建议手动排查，但是也可以进行直接删除：

```shell
sudo pacman -R $(pacman -Qqm|grep manjaro)
sudo pacman -R $(pacman -Qqm|grep mhwd)
```

其他残余软件也可以按需删除

## 重新安装Arch Linux的软件包

很多Manjaro软件包的包名和版本号都与Arch Linux一样，但是内容未必一样（最简单的例子：发行版信息`lsb-release`），所以建议切换后进行软件包的重新安装，执行完前几节的步骤后依赖问题已基本解决，可以继续执行：

```shell
# 首先清除以前下载的Manjaro的软件包
sudo pacman -Scc
# 重新安装所有已安装的库内软件包
sudo pacman -Syu $(pacman -Qqn)
```

## grub

Manjaro默认使用了自己的主题，而Manjaro的主题文件已经在之前被我们删除，所以grub主题文件需要重新指定

这里我不想折腾，直接使用了grub自带的starfield主题：
- 打开`/etc/default/grub`
- 找到`GRUB_THEME=`一行
- 把`=`后的内容改成`"/usr/share/grub/themes/starfield/theme.txt"`
- 完成后，执行`sudo grub-mkconfig -o /boot/grub/grub.cfg`重新生成`grub.cfg`

## Zsh

### 基于oh-my-zsh的配置

Manjaro默认配置好了zsh，然而这些配置在Arch Linux中并没有直接集成，需要自己进行

在Arch Linux源及Archlinuxcn源中可以直接安装配置zsh所需要用到的`oh-my-zsh-git`、`oh-my-zsh-powerline-theme`

```shell
sudo pacman -S oh-my-zsh-powerline-theme-git oh-my-zsh-git zsh-syntax-highlighting zsh-autosuggestions
```

安装完成后，还需要复制`.zshrc`文件：

```shell
mv ~/.zshrc ~/.zshrc.bak    # 将原来Manjaro的默认配置文件备份保存
cp /usr/share/oh-my-zsh/zshrc ~/.zshrc
```

打开`~/.zshrc`进行编辑，找到`plugins=`，在括号中添加`zsh-syntax-highlighting zsh-autosuggestions`，此外，还推荐将`ZSH_THEME`设置为`"powerline"`，切换到更好看到主题

为了真正启用语法高亮和自动补全功能，还需要将插件链接到oh my zsh的目录下：

```shell
sudo ln -s /usr/share/zsh/plugins/zsh-syntax-highlighting /usr/share/oh-my-zsh/custom/plugins/
sudo ln -s /usr/share/zsh/plugins/zsh-autosuggestions /usr/share/oh-my-zsh/custom/plugins/
```

oh my zsh的历史保存文件地址与Manjaro配置的zsh的保存位置不同，为了继续使用以前的历史记录，可以执行：

```shell
cp ~/.zhistory ~/.zsh_history
```

完成后可以将各个地方的，默认shell切换到zsh：

```shell
chsh -s /bin/zsh
sudo chsh -s /bin/zsh
```

### 不基于oh-my-zsh的配置

Zsh的配置也可以不依赖于oh-my-zsh而直接进行，具体内容见我的另一篇博客：[在不借助oh-my-zsh的前提下进行Zsh配置](https://wszqkzqk.github.io/2022/06/24/在不借助oh-my-zsh的前提下进行Zsh配置)

## Fcitx5

Manjaro通过依赖的方式在安装Fcitx5的时候向`/etc/xdg`添加`fcitx5`文件夹及配置文件自动启用了Fcitx5在软件中的输入功能（软件包`manjaro-asian-input-support-fcitx5`），因此安装了Fcitx5后开箱即用，不需要配置

但是Arch Linux软件源没有这一软件包，应当手动对Fcitx5进行配置，编辑`/etc/environment`，加入：

```shell
GTK_IM_MODULE=fcitx
QT_IM_MODULE=fcitx
XMODIFIERS=@im=fcitx
INPUT_METHOD=fcitx
SDL_IM_MODULE=fcitx
GLFW_IM_MODULE=ibus
```

## 类似Manjaro的GUI包管理器

如果想要在Arch Linux下面使用GUI的包管理器就不推荐pamac了（那还不如直接用Manjaro），这里推荐使用Octopi

```
yay -S octopi
```

如果需要托盘驻留插件，对于KDE，可以执行：

```
yay -S octopi-notifier-framework
```

其他桌面环境执行：

```
yay -S octopi-notifier-qt5
```

不过我个人主要把Octopi当作一个查看是否有更新的工具，一般操作还是用命令实现

## 总结

以上过程完成后，切换即基本完成（部分Manjaro的残留文件可以手动进行清理），我在使用过程中并没有发现由切换造成的bug

最后贴上一张图，切换后`neofetch`与KDE信息中心的系统信息已经变成了Arch Linux：

[![#~switch-manjaro-to-archlinux.webp](/img/switch-manjaro-to-archlinux.webp)](/img/switch-manjaro-to-archlinux.webp)

不过由本文可以看到，由Manjaro切换Arch Linux的过程仍然较为繁琐，仅推荐在需要将使用了很久、不便于迁移的Manjaro系统切换至Arch Linux时使用，不推荐用这个方法通过安装Manjaro来安装Arch Linux，如果需要直接安装Arch Linux又想要避免安装的麻烦可以尝试[EndeavourOS](https://endeavouros.com/)

## 稳定性

感觉由Manjaro切换的Arch Linux的稳定性确实存在不少问题，我现在已经进行了一次全新安装，完全切换到了Arch Linux


