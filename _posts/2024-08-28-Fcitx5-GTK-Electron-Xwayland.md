---
layout:     post
title:      在Wayland下解决Electron应用的Fcitx5输入法问题
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
