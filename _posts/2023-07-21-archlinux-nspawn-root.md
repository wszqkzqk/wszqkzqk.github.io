---
layout:     post
title:      在systemd-nspawn容器中root登录Arch Linux
subtitle:   容器使用
date:       2023-07-21
author:     wszqkzqk
header-img: img/Linux-distro-logo/archlinux.webp
catalog:    true
tags:       开源软件 系统管理 Linux archlinux
---

## 前言

在systemd-nspawn容器中使用root登录Arch Linux时，会发现即使输入正确的密码，也会提示密码错误。这是因为Arch Linux的安全策略仅允许root用户在`console`、`tty1`、`tty2`、`tty3`、`tty4`、`tty5`、`tty6`、`ttyS0`、`hvc0`这些终端登录，而容器中的终端并不在这些终端列表中。

## 解决方法

解决方法很简单，只需要在容器中的`/etc/securetty`文件中添加容器的终端即可，例如：

```bash
echo "pts/0" >> /etc/securetty
```
