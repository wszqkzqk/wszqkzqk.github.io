---
layout:     post
title:      将远程Wayland应用窗口转发到本地
subtitle:   利用Waypipe实现远程无桌面环境的单个Wayland GUI应用的本地显示
date:       2025-10-13
author:     wszqkzqk
header-img: img/wayland/wayland-bg.webp
catalog:    true
tags:       开源软件 Wayland Linux
---

## 前言

> 本文介绍了在远程的Linux机器上**只有Wayland相关依赖**但没**有运行桌面环境**的情况下，如何将远程的Wayland GUI应用程序**窗口转发**到**本地Wayland**显示出来。

笔者是[Arch Linux for Loong64](https://github.com/lcpu-club/loongarch-packages)的维护者，但是事实上笔者手边并没有属于自己的龙芯物理机。笔者一直通过SSH远程连接龙芯武汉提供的编译机和同学手里的龙芯机器进行工作。对于非GUI的测试，笔者一般也用SSH来进行，而对于GUI程序的测试则比较麻烦，一般要么自己启动QEMU虚拟机，要么@同学让同学帮忙测试，或者招募社区用户来测试。

而QEMU虚拟机的性能并不理想，会让笔者的笔记本温度飙升🥵🥵🥵，在离电的时候更是续航杀手；让同学或者招募的用户测试则可能需要等待较长的时间，而且向他们传递测试包有时候也不方便。

对此，最方便的情况就是直接在打包出来以后原位测试，这就需要在远程的机器上运行GUI程序，并且将图形界面传输到本地显示出来。对于X11来说，这并不难，只需要在SSH连接时加上`-X`或者`-Y`参数即可（前提是远程机器上有X11服务器），然而对于Wayland来说，这就比较麻烦了。

远程的机器事实上不会运行DE，因此是**不能**够用KRDP等**远程桌面软件**的，而且笔者更想要的是将某个单独的GUI程序在本地像**正常的程序窗口**一样显示出来，而不是转发整个桌面。

因此，笔者在此引入了一种Wayland的远程转发方案——[Waypipe](https://gitlab.freedesktop.org/mstoeckl/waypipe)。Waypipe与X11 Forwarding类似，可以将远程的Wayland应用程序的图形界面通过SSH隧道传输到本地显示出来，并且支持单个应用程序的转发，而不是整个桌面。（当然也有办法转发整个桌面合成器）

## 依赖安装

确保**本地在使用Wayland**，并在本地安装`waypipe`：

```bash
sudo pacman -S waypipe
```

在远程机器上也需要安装`waypipe`和`wayland`，如果想要转发完整合成器，还可以安装`weston`：

```bash
sudo pacman -S waypipe wayland weston
```

## 基本使用

Waypipe的使用方法非常简单，只需要在SSH连接时使用`waypipe`命令即可。假设远程机器的地址为`remote_host`，要运行的程序为`your_program`，则可以使用以下命令：

```bash
waypipe ssh user@remote_host your_program
```

## 添加SSH参数

需要注意的是，**ssh的参数**必须要放在**机器地址之前**，例如：

```bash
waypipe ssh -p 2222 user@remote_host your_program
```

## 获得具有Wayland程序启动能力的远程终端

如果暂时不需要运行某个特定的程序，也可以不加上程序名，直接连接到远程机器的Wayland会话：

```bash
waypipe ssh user@remote_host
```

这样会正常连接到远程机器的终端，但暂时不会启动任何GUI程序。当你在**终端中运行某个Wayland GUI程序**时，它的图形界面就会被**转发到本地**显示出来。

## 转发Wayland合成器

如果想要转发整个Wayland合成器，可以在远程机器上运行`weston`，然后在本地连接：

```bash
waypipe ssh user@remote_host weston
```

## 指定压缩算法

Waypipe支持lz4和zstd两种压缩算法，默认使用lz4，可以手动使用`-c`参数指定压缩算法：

```bash
waypipe -c zstd ssh user@remote_host your_program
```

在对应的算法后面加上`=N`可以指定压缩级别，例如：

```bash
waypipe -c zstd=10 ssh user@remote_host your_program
```

## 指定视频流编码

Waypipe支持H264、VP9和AV1视频流编码（也可以无编码传输），可以通过`--video`参数指定编码方式。例如，使用AV1编码：

```bash
waypipe --video av1 ssh user@remote_host your_program
```

还可以对硬件/软件编解码进行指定：

* `hw` - 编码和解码都使用硬件加速
* `sw` - 编码和解码都使用软件
* `hwenc` - 仅编码使用硬件
* `swenc` - 仅编码使用软件
* `hwdec` - 仅解码使用硬件
* `swdec` - 仅解码使用软件

例如，使用硬件编解码的AV1：

```bash
waypipe --video av1,hw ssh user@remote_host your_program
```

## 效果

|[![#~/img/wayland/waypipe-demo.webp](/img/wayland/waypipe-demo.webp)](/img/wayland/waypipe-demo.webp)|
|:----:|
|运行远程服务器上的GTK4程序并转发到本地显示|

如图，显示的IP属地是武汉的龙芯服务器，运行的程序是远程服务器上编译好的太阳高度角查看器，可以看到程序在本地显示正常。

|[![#~/img/wayland/waypipe-demo-chromium.webp](/img/wayland/waypipe-demo-chromium.webp)](/img/wayland/waypipe-demo-chromium.webp)|
|:----:|
|在远程服务器上运行Chromium并在本地显示|

如图，远程在Arch Linux for Loong64上运行的Chromium浏览器，成功转发到本地显示，功能一切正常。

## 常见问题

### 在没有GPU的远程机器上运行GUI程序时报错

在没有GPU的机器上直接通过Waypipe运行GUI程序时，可能会遇到问题，首先是Waypipe的错误：

```log
[58.090527 ERR waypipe-server(437190) mainloop.rs:5773] Sending error: src/dmabuf.rs:967: Failed to create Vulkan instance: Unable to find a Vulkan driver
```

随后，GUI程序则会报错，例如GTK程序一般会显示这样的错误：

```log
(solarangleadw:437185): Gtk-WARNING **: 07:59:18.091: Failed to open display
```

这是因为Waypipe默认启用了GPU，如果远程机器没有GPU或者没有正确配置GPU驱动，就会导致无法创建Vulkan实例，从而无法运行GUI程序。此时，可以加入`--no-gpu`参数来禁用GPU：

```bash
waypipe --no-gpu ssh user@remote_host your_program
```

不过需要注意的是，禁用GPU的同时也会禁用视频流编码，即前面的`--video`参数将不再生效。这样的模式对于网络带宽要求较高，建议启用较高的压缩级别，例如：

```bash
waypipe -c zstd=10 --no-gpu ssh user@remote_host your_program
```

这样的选项可能会导致性能较低（当然这个示例中远程的网络条件确实也很差）：

|[![#~/img/wayland/waypipe-gtk-demo-performance-1.webp](/img/wayland/waypipe-gtk-demo-performance-1.webp)](/img/wayland/waypipe-gtk-demo-performance-1.webp)|[![#~/img/wayland/waypipe-gtk-demo-performance-2.webp](/img/wayland/waypipe-gtk-demo-performance-2.webp)](/img/wayland/waypipe-gtk-demo-performance-2.webp)|
|:----:|:----:|
|GTK4 Demo Benchmark Scrolling，不到10 FPS|GTK4 Demo Benchmark Fishbowl，在仅1个图标时也才不到30 FPS|

### 默认环境下无法运行Chromium

Chromium在不设置相关环境变量时无法依靠Waypipe运行，即使指定了Wayland模式与GTK4模式也无效，报错如下：

```log
[442257:442257:1013/103637.352992:ERROR:ui/ozone/platform/x11/ozone_platform_x11.cc:249] Missing X server or $DISPLAY
[442257:442257:1013/103637.353091:ERROR:ui/aura/env.cc:257] The platform failed to initialize.  Exiting.
```

运行以下命令后我们不难知道原因：

```bash
echo $XDG_SESSION_TYPE # 输出值为 tty
```

这时候我们发现在Waypipe中输出的值是`tty`，而不是`wayland`，这就导致Chromium无法正确识别当前的显示服务器类型，从而无法启动。

我们只需要在运行Chromium前**设置`XDG_SESSION_TYPE`环境变量为`wayland`**即可，如果在Waypipe的终端中运行Chromium，可以这样：

```bash
export XDG_SESSION_TYPE=wayland
chromium --ozone-platform=auto
```

也可以不导出变量，直接在命令前加上：

```bash
XDG_SESSION_TYPE=wayland chromium --ozone-platform=auto
```

如果需要在一条Waypipe命令中完成远程Chromium的启动，可以使用`env`来设置环境变量：

```bash
waypipe ssh user@remote_host env XDG_SESSION_TYPE=wayland chromium --ozone-platform=auto
```

自Chromium 140开始，Chromium默认自动在Wayland平台下启用Wayland支持，因此不需要再加上`--ozone-platform=auto`参数：

```bash
waypipe ssh user@remote_host 'env XDG_SESSION_TYPE=wayland chromium'
```

除Chromium外，其他的程序如果遇到相关问题，也可以尝试设置`XDG_SESSION_TYPE=wayland`来解决。
