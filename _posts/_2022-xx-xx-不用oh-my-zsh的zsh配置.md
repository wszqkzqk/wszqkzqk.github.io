---
layout:       post
title:        不借助oh-my-zsh进行Zsh配置
subtitle:     Zsh配置日志：解决Zsh启动缓慢的问题
date:         2022-xx-xx
author:       星外之神
header-img:   img/
catalog:      true
tags:         Linux Windows MSYS2 Zsh 开源软件 Pacman 系统配置
---

## 前言

Linux下最常用的Bash发布于1989年，在此后的发展中并没有引入太多么革命性的功能，已经是一个十分古老的Unix Shell了。虽然它仍然是众Linux发行版预装最多的Shell，但是它的扩展性也早已不如其他的Shell。

Zsh、Fish甚至从Windows下发展而来的PowerShell相比于Bash而言，都极具扩展性。其中，只有Zsh能够很好地兼容Bash的语法，所以，将Zsh作为Bash的替代品非常合适。

然而，Zsh虽然可扩展性高，功能强大，但是它的配置并不容易。一般来说，要方便地配置Zsh需要借助oh-my-zsh这个强大的工具。但oh-my-zsh这个工具主要用Shell脚本写成，性能并不出色，往往需要较长的启动时间。

由于Linux下有十分成熟的内存缓存机制，因此当oh-my-zsh在系统启动后完成过一次加载，之后便可以直接从内存中读取已经缓存的内容，能够做到瞬间启动。然而，Windows下的内存缓冲机制则没有这么友好，如果使用oh-my-zsh，Zsh的加载时间将会特别长。此外，由于Windows下的Unix Shell环境均是移植而来，利用了Cygwin或衍生库将Unix API Calls转化为Windows API Calls，有显著的性能损失，对于Unix的`fork()`API转化效率尤其低下，再加上无论是Cygwin还是MSYS2都将Unix Shell内置的`echo`、`[`等功能拆分成了独立`.exe`文件，增加了调用性能开销（不过WSL的原生实现可能要好一点）。因此，在Windows下使用本来就比较吃资源的oh-my-zsh十分卡顿，体验并不好。

### 准备

考虑到有的读者可能对Windows下的终端配置不熟悉，在这里我简单列出一下Windows下安装Zsh的方法。

由于WSL对Windows本身的交互并不是很方便，里面的工具链也不能用来构建Windows本地应用，我在这里推荐使用MSYS2。MSYS2相当于Windows版的Pacman包管理器，不仅与Archlinux系发行版的包管理命令完美兼容，而且包构建方便（只需要写一份`PKGBUILD`）、官方源中软件丰富，包含了gcc、clang等编译器与众多库，还有ffmpeg等基础软件和VLC等方便的用户端GUI软件，功能十分强大。

MSYS2已经包含在了winget的软件库中，可以直接通过命令安装：

```powershell
winget install msys2.msys2
```

安装完成后，需要在系统环境变量（现在的Windows系统应该只需要在开始菜单的搜索框中输入`path`就能弹出）中添加如下变量：

|       变量名               |   变量值   |
|       ----                |    ---    |
|   MSYS2_PATH_TYPE[^1]     | inherit   |

其实也可以把MSYS2的相关路径（使用的MinGW-w64工具链路径`{MSYS2安装路径}/{使用的MinGW类型}/bin`以及MSYS2路径`{MSYS2安装路径}/usr/bin`）添加到`Path`变量中，方便直接在Windows的cmd或者PowerShell中调用MSYS2命令，但是据说可能会出现一些冲突，然而笔者添加了以后并没有发现什么问题，因此这也可以作为一个可选项。

添加完成后，在MinTTY中运行MSYS2终端，安装Zsh：

```bash
pacman -S zsh
```

为了方便，可以将MSYS2集成到Windows终端，在Windows终端中选择`添加新配置文件`-`新建空配置文件`，在`命令行`中填入：

```cmd
cmd.exe /c set MSYSTEM={你使用的MinGW环境名称} && set CHERE_INVOKING=enabled_from_arguments && {MSYS2安装位置}/usr/bin/
zsh.exe --login
```

例如：

```cmd
cmd.exe /c set MSYSTEM=UCRT64 && set CHERE_INVOKING=enabled_from_arguments && D:/msys64/usr/bin/
zsh.exe --login
```

## oh-my-zsh的替代实现

oh-my-zsh提供的便利主要是主题支持和插件支持，当然还有其他的操作绑定。这些我们都可以想办法去进行性能更优的替代实现。

### 主题支持及状态提示

在oh-my-zsh的启发下，[Jan De Dobbeleer](https://github.com/JanDeDobbeleer)开发了一个功能较为接近的[oh-my-posh](https://github.com/JanDeDobbeleer/oh-my-posh)。与oh-my-zsh不同，oh-my-posh采用Go语言开发，虽然运行效率仍然较C/C++低不少，但是其性能仍然显著高于直接用Sell写成的oh-my-zsh。

虽然oh-my-posh从名称来看好像是为微软的PowerShell专门设计，但是由于它并没有用绑定在Shell上的语言实现，故实际上oh-my-posh支持多种Shell环境，当然也包括Zsh。

oh-my-posh不仅是跨Shell的，它还是跨平台的，Windows与Acrhlinux系发行版均可以很方便地安装，Windows安装命令如下：

```powershell
winget install JanDeDobbeleer.OhMyPosh
```

Archlinux系发行版则是（使用yay）：

```bash
sudo yay -S oh-my-posh-bin
```

#### 预览

Zsh需要有对应的`.zshrc`文件才能正常启动，在正式配置流程开始之前，我们不妨先让Zsh自动建立一个无功能的初始化`.zshrc`文件：

|[![#~/img/首次运行Zsh.webp](/img/首次运行Zsh.webp)](/img/首次运行Zsh.webp)|
|:----:|
|首次运行Zsh|

如上图所示，在没有配置文件时首次运行Zsh会输出以上提示。为了有一个供后续配置的输入环境，我们可以在这里输入`0`，输入`cat ~/.zshrc`后可以看到，程序在此处生成了一个空的配置文件：

```zsh
$ cat ~/.zshrc
> # Created by newuser for 5.8
```

oh-my-posh在不同平台的文件位置有些区别，在Zsh中预览效果时，Windows下可以执行：

```zsh
# $POSH_THEMES_PATH路径在安装时已经添加到了环境变量中
eval "$(oh-my-posh init zsh --config $POSH_THEMES_PATH/{想要使用的主题文件})"
```

Archlinux下执行：

```zsh
eval "$(oh-my-posh init zsh --config /usr/share/oh-my-posh/themes/{想要使用的主题文件})"
```

oh-my-posh项目推荐使用的是`jandedobbeleer.omp.json`这款主题。

如果配置成功，就会显示界面：

|[![#~/img/预览中的oh-my-posh主题效果.webp](/img/预览中的oh-my-posh主题效果.webp)](/img/预览中的oh-my-posh主题效果.webp)|
|:----:|
|预览中的oh-my-posh主题效果|

这里我们可以发现，系统并没有自带oh-my-posh主题所需要的字体，部分字符被显示成了方块，这一问题我们稍后再解决。

### 下载安装Zsh相关功能插件

Zsh具有许多能够提高生产力的插件，如自动补全插件、语法高亮插件等。

对于Archlinux，这些插件都已经集成到了软件源中，可以直接安装：

```zsh
yay -S zsh-syntax-highlighting zsh-autosuggestions
```

对Windows则较为麻烦，需要手动clone到本地：、

```zsh
mkdir ~/.zshconfig
cd ~/zshconfig
git clone https://github.com/zsh-users/zsh-autosuggestions

```

### 编写`.zshrc`文件

`.zshrc`是Zsh的配置文件，没有了oh-my-zsh，我们需要进行手动编写。



[^1]: 指定MSYS2程序读取的变量类型，`inherit`表示将系统变量合并到MSYS2环境变量
