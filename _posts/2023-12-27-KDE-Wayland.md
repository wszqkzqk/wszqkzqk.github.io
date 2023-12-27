---
layout:     post
title:      KDE Plasma的Wayland现状
subtitle:   在KDE Plasma 5.27中使用Wayland
date:       2023-12-27
author:     wszqkzqk
header-img: img/KDE-bg.webp
catalog:    true
tags:       开源软件 系统配置 KDE 系统维护
---

## 前言

近几年来，Wayland作为X11的替代方案，已经逐渐成为Linux桌面环境的主流选择。RedHat、SUSE、Canonical等主流Linux操作系统厂商目前都一致力挺Wayland，而X11的维护力量也在逐渐减弱。GNOME桌面环境率先默认启用Wayland，而像Fedora这样比较激进的发行版甚至在积极准备移除X11。

然而，目前大多数主流桌面环境仍然默认使用X11。KDE Plasma的Wayland支持早已可用，但直到KDE Plasma 6时才会推荐发行版默认使用Wayland。

笔者在最近的一两年中有过多次尝试使用Wayland的经历，但是每次都因种种原因回到X11。笔者本来打算在KDE Plasma 6时再正式切换到Wayland，但最近，随着Firefox 121默认启用Wayland，Wine的Wayland支持日渐完善，由KDE社区开发的xwaylandvideobridge也于今天（2023.12.27）加入Arch Linux的`extra`仓库，笔者认为现在已完全可以切换到Wayland了。

## 切换

由于系统实际上已经安装了KDE Wayland所需的所有依赖，因此，切换到Wayland非常简单，只需要在`SDDM`登录界面选择`Plasma (Wayland)`即可。

## 系统缩放与桌面布局

KDE Plasma在Wayland下和X11下用的是两套不同的缩放设置方案，因此切换到Wayland后，需要重新设置系统缩放。更改缩放后，在系统桌面上的某些插件可能会出现错位的情况，这时，只需要重新将插件拖动到正确的位置即可。

[![#~/img/KDE/desktop-wayland.webp](/img/KDE/desktop-wayland.webp)](/img/KDE/desktop-wayland.webp)

## `XWayland`程序的缩放策略与影响

KDE Plasma对于`XWayland`程序的缩放有2个方案，一个是`由应用程序进行缩放`，一个是`由系统进行缩放`。

该设置可以到`系统设置`-`显示与监视器`-`显示配置`-`缩放`中进行设置。

|[![#~/img/KDE/plasma-settings-scale.webp](/img/KDE/plasma-settings-scale.webp)](/img/KDE/plasma-settings-scale.webp)|
|:----:|
|`系统设置`-`显示与监视器`-`显示配置`-`缩放`的界面|

两者在设置中的描述为：

* `由应用程序进行缩放`：支持缩放的旧式应用程序将使用内建的缩放功能得到清晰的显示效果，但是不支持缩放的应用程序将不会进行缩放。
* `由系统进行缩放`：所有旧式应用程序将由系统缩放到正确的大小，但它们将总是略显模糊。

由于`由系统进行缩放`连不受支持的应用程序都会进行缩放，因此，笔者选择了`由系统进行缩放`。但笔者在使用一段时间后，发现这样除了会导致Xwayland应用的字体显示模糊外，还会有其他意想不到的副作用：使用`由系统进行缩放`的方式，会导致**OBS Studio录屏时出现模糊**的情况，而使用`由应用程序进行缩放`的方式则不会出现这个问题。

因此，笔者最终选择了`由应用程序进行缩放`的方式。

## `xwaylandvideobridge`的现状

`xwaylandvideobridge`是KDE社区开发的用于解决X11应用程序无法访问Wayland客户端的窗口或屏幕内容的问题的一个工具，目前还在`0.4.0`，尚未发布正式版。正好今天（2023.12.27）`xwaylandvideobridge`正式加入了Arch Linux的`extra`仓库，因此，笔者也尝试了一下`xwaylandvideobridge`。

`xwaylandvideobridge`的安装非常简单，只需要安装`xwaylandvideobridge`即可，例如：

```bash
sudo pacman -S xwaylandvideobridge
```

`xwaylandvideobridge`理论上开箱即用，安装后重新登录即可在系统底栏的隐藏图标中找到`Wayland to X11 Video bridge`的图标。然而，笔者发现，使用XWayland程序调用截图或者屏幕捕捉等功能时，仍然只能看到黑屏和光标，似乎并没有起到作用。

## 程序快捷键的设置

与X11不同，出于安全考虑，Wayland不允许非激活窗口直接捕捉键盘输入。因此，程序自身如果需要使用快捷键，应当在KDE的`系统设置`-`应用程序`-`旧式X11应用程序支持`中进行额外的设置。

|[![#~/img/KDE/plasma-settings-x11-hotkeys.webp](/img/KDE/plasma-settings-x11-hotkeys.webp)](/img/KDE/plasma-settings-x11-hotkeys.webp)|
|:----:|
|`系统设置`-`应用程序`-`旧式X11应用程序支持`|

默认情况下，Wayland会禁止X11程序在非激活窗口状态下直接捕捉键盘输入，即这里的`永不`选项。我们可以按需要允许X11程序在非激活窗口状态下直接捕捉键盘输入，共有3种不同程序的允许的策略。

* `仅Meta、Ctrl、Alt、Shift键`
* `所有键，但仅在按下了Meta、Ctrl、Alt、Shift键时`
* `总是`

笔者选择了`所有键，但仅在按下了Meta、Ctrl、Alt、Shift键时`，因为一般的快捷键都是包含`Meta`、`Ctrl`、`Alt`、`Shift`的组合键，该设置基本可以做到安全性与便利性的平衡。

## `virt-manager`的问题

笔者在使用`virt-manager`时发现虚拟机窗口的缩放存在问题，虚拟机的实际窗口很小，周围全是固定比例的黑边。这一问题笔者暂时没有找到解决方案，目前是在使用的时候开全屏。

## 便利

当然，除了以上的问题外，笔者在使用KDE Plasma的Wayland时，还发现了一些便利之处。Firefox在Wayland下的表现非常好，可以直接使用触摸板手势进行放大、移动等操作（触摸屏理论上同理），这是X11下所不具备的。不过Edge等其他浏览器仍然不支持手势操作。