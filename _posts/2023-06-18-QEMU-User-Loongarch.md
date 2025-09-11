---
layout:     post
title:      在QEMU User模式下测试龙芯新世界软件
subtitle:   轻量级龙芯新世界测试环境
date:       2023-06-18
author:     wszqkzqk
header-img: img/loongarch/loongson-mother-board.webp
catalog:    true
tags:       开源软件 国产硬件 系统配置 虚拟化 容器 QEMU
---

## 前言

> 本文主要讨论使用 QEMU User 模式下测试龙芯新世界软件的方法

笔者之前写过一篇[使用QEMU配置龙芯新世界环境](https://wszqkzqk.github.io/2023/05/01/使用QEMU配置龙芯新世界环境/)，那篇文章主要介绍了如何在完整的 QEMU 虚拟机中运行龙芯新世界的环境，但是这种方法的缺点是只能利用宿主机的 4 个核心，因此性能较低；而且，完整模拟的方法环境较重，不够简洁。

本文在此提供一种更加轻量、更能利用宿主机性能的方法。

## 环境配置

本方法的轻量级测试环境主要依赖于 QEMU User 模式，依靠 `systemd-nspawn` 或 `arch-chroot` 的方法，结合 QEMU 提供的 `binfmt`，可以在 x86_64 主机上运行龙芯新世界的环境。

以 Arch Linux 为例，首先需要安装 QEMU User 的相关文件：

```bash
sudo pacman -S qemu-user-static-binfmt qemu-user-static-binfmt
```

下载有关的 rootfs，推荐到[北京大学开源镜像站](https://mirrors.pku.edu.cn/loongarch/archlinux/iso/latest/archlinux-bootstrap-loong64.tar.gz)下载。

下载完成后，解压到一个目录，例如 `~/loongarch`，然后执行：

```bash
sudo systemd-nspawn -aD ~/loongarch --machine archloong64 -U
```

这样就可以进入一个龙芯新世界环境的容器了。

## 存在问题

在 `systemd-nspawn` 下使用 `sudo` 会出现一些问题，例如 `sudo pacman -S` 会出现 `sudo: effective uid is not 0, is sudo installed setuid root?` 的错误，这是因为 `systemd-nspawn` 会将 `sudo` 的权限降低，因此在需要 `root` 权限时，应当直接登录 `root` 用户。

如果需要使用 `sudo`，可以使用 `arch-chroot` 的方法，首先需要安装 `arch-install-scripts`：

```bash
sudo pacman -S arch-install-scripts
```

然后执行：

```bash
sudo arch-chroot ~/loongarch
```

