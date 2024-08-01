---
layout:     post
title:      systemd-nspawn容器网络配置
subtitle:   Arch Linux宿主下的非Arch Linux发行版容器网络配置
date:       2024-07-21
author:     wszqkzqk
header-img: img/bg-sunrise.webp
catalog:    true
tags:       系统配置 虚拟化 网络 Linux
---

## 前言

`systemd-nspawn`是`systemd`提供的一个轻量容器管理工具，可以用来启动容器。在`Arch Linux`宿主下，使用`systemd-nspawn`启动一个`Arch Linux`容器是直接可以使用网络的，但是如果启动一个非`Arch Linux`发行版`systemd-nspawn`容器，可能会遇到网络配置问题。

## 配置

对于非`Arch Linux`发行版的`systemd-nspawn`容器，可以使用网桥来实现网络连接。

### 创建网桥

由于笔者平时也需要使用`libvirt`，所以这里使用`libvirt`的网桥`virbr0`来配置`systemd-nspawn`容器的网络。

首先，安装`libvirt`：

```bash
sudo pacman -S libvirt
```

然后，启用`libvirtd`服务：

```bash
sudo systemctl enable --now libvirtd
```

有可能需要手动启用`virbr0`网桥：

```bash
sudo virsh net-start default
```

### 容器配置

在使用`systemd-nspawn`启动容器时，可以使用`--network-bridge=virbr0`参数来指定网桥：

```bash
sudo systemd-nspawn --network-bridge=virbr0 -D /path/to/container/root
```

这样，容器就可以使用网桥来连接网络了。
