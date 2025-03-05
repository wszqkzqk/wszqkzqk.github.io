---
layout:     post
title:      在Wayland下解决Electron应用的Fcitx5输入法漏字等问题
subtitle:   解决运行在Xwayland下依赖旧式GTK的应用的Fcitx5输入法问题
date:       2024-08-28
author:     wszqkzqk
header-img: img/input-method/abstract-bg.webp
catalog:    true
tags:       Fcitx5 开源软件 GTK Electron Xwayland
---

## 前言

笔者曾经在博客[修复WPS Office的Fcitx5输入法问题](/2024/03/09/WPS-Fcitx5/)中介绍了如何解决WPS Office这样的**跑在Xwayland下的闭源旧式Qt5程序**在Wayland环境中的Fcitx5输入法问题，如果按照官方推荐的方式，仅启用Wayland输入协议，并添加`XMODIFIERS=@im=fcitx`这一个环境变量，这样的程序将**完全无法使用输入法**。按照那篇博客的方法，我们可以通过给这些程序单独添加环境变量的方式来解决这个问题。

而对于**跑在Xwayland下的闭源旧式GTK程序**，例如Electron应用，虽然按照官方推荐的配置方式，这些程序可以使用Fcitx5输入法，但是在某些情况下，这些程序可能会出现**输入漏字**的问题。这一问题可以按照[老方法](/2024/03/09/WPS-Fcitx5/)单独为每一个程序添加环境变量来解决，但是考虑到现在的用户可以普遍安装有较多的Electron应用，这样的方法显然比较麻烦。

本文将介绍一种更加简单的解决方法，通过修改GTK的配置文件来避免单独为每一个程序添加环境变量，同时不会影响运行在Wayland下的GTK应用。

## 解决方法

对于GTK3应用，在`~/.config/gtk-3.0/settings.ini`中添加以下内容：

```ini
gtk-im-module=fcitx
```

这样配置可以使得运行在Xwayland下的GTK3应用使用为X11指定的输入法，同时不会影响运行在Wayland下的GTK应用。

GTK2虽然早已不再维护，但是GIMP等应用仍然在使用GTK2，我们可能仍然需要处理。对于GTK2应用，在`~/.gtkrc-2.0`中添加以下内容：

```ini
gtk-im-module="fcitx"
```

这样配置可以使得运行在Xwayland下的GTK2应用使用为X11指定的输入法，同时不会影响运行在Wayland下的GTK应用。

* 说明：这一方法不仅适用于Electron应用，也适用于其他运行在Xwayland下且依赖旧式GTK的应用。

## 其他

笔者发现Fcitx5在Wayland部分程序中的拼音输入体验也有一些问题，比如说在Firefox中，按左右键在输入框中移动光标时，光标并不显示在预编辑文本中。这可以通过将输入文本显示在从应用程序中改为显示在输入法中来解决，即将输入法的单行模式改为双行模式。这一设置可以在Fcitx5的配置中找到。

目前Fcitx5的设置选项发生了一些变化，在`拼音`-`设置`-`预编辑模式`中，有以下选项：

* `不显示`：不显示预编辑文本
* `拼音串`（默认）：显示拼音串
* `提交预览`：显示第一个选词的提交预览

其中，`拼音串`为单行模式，输出的原始内容将显示在应用程序中，而另外两种模式均为双行模式，输出的原始内容将显示在输入法中。用户可以根据自己的喜好选择适合自己的模式。
