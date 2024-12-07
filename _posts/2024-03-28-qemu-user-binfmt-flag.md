---
layout:     post
title:      binfmt_misc flags与QEMU用户模式下的跨架构构建环境
subtitle:   Acrh Linux龙架构移植踩坑
date:       2024-03-28
author:     wszqkzqk
header-img: img/media/bg-modern-img-comp.webp
catalog:    true
tags:       系统配置 系统维护 开源软件 龙芯 LoongArchLinux
---

## 前言

对于部分架构，出于设备较不常见或者设备性能较低等原因，很多时候开发者并不会选择在该架构下进行打包与分发，而是选择使用QEMU等模拟器进行跨架构构建。

QEMU主要有两种模式，一种是全系统模拟，另一种是用户模式模拟。全系统模拟是指QEMU模拟整个系统，包括CPU、内存、外设等，而用户模式模拟则是只模拟用户空间，不模拟内核空间。笔者在之前的测试中，发现对龙架构使用QEMU全系统模拟时，`-smp`只能指定为1-4，无法充分利用多核性能；在最近的版本中`-smp`似乎已经可以指定为更多核心，但是据社团的其他同学称，即使指定了更多的核心数，实际上多核性能利用也并不充分。

因此，笔者决定尝试使用QEMU用户模式模拟，以充分利用多核性能。

## `binfmt_misc`带来的权限问题

在笔者的测试中，如果在用户模式下使用QEMU，在容器中从root切换到普通用户再提权时，会出现如下错误：

```log
sudo: effective uid is not 0, is /usr/sbin/sudo on a file system with the 'nosuid' option set or an NFS file system without root privileges?
```

这一报错极具迷惑性，实际上提权失败的原因与文件系统、挂载参数等完全无关。笔者后续也去排查了`systemd-nspawn`、`sudo`等工具，并没有解决问题。后来，笔者阅读了Arch Linux维护者[Felix Yan](https://github.com/felixonmars)的[Arch Ports RFC](https://gitlab.archlinux.org/archlinux/rfcs/-/merge_requests/32)，发现了问题的所在：

> Requires unsafe "C" flag for binfmt to correctly invoke suid binaries for our toolchain to work.

这一问题的根源在于`binfmt_misc`的flags参数。`binfmt_misc`是Linux内核的一个功能，可以在内核中注册一个二进制格式解释器，当内核遇到一个二进制文件时，会调用这个解释器来解释这个文件。

对于龙架构的QEMU用户模式模拟，`binfmt_misc`的默认注册内容为：

```bash
~> cat /usr/lib/binfmt.d/qemu-loongarch64-static.conf
:qemu-loongarch64:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x02\x01:\xff\xff\xff\xff\xff\xff\xff\xfc\x00\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/usr/bin/qemu-loongarch64-static:FP
```

根据`binfmt_misc`的[文档](https://www.kernel.org/doc/html/latest/admin-guide/binfmt-misc.htm)，注册的二进制类型的基本格式为：

```conf
:name:type:offset:magic:mask:interpreter:flags
```

其中，`flags`参数可以指定为：

* `P` - 保留原始`argv[0]`
  * 默认情况下，`binfmt_misc`会用二进制文件的完整路径覆盖原始的`argv[0]`（命令名称）。
  * 使用此标志后，`binfmt_misc`会在参数列表中添加一个额外的参数来保存原始的`argv[0]`。
    * 例如，如果将解释器设置为`/bin/foo`，并且运行`blah`（位于`/usr/bin`），则内核会用以下参数执行`/bin/foo`：
      * `["/bin/foo", "/usr/bin/blah", "blah"]`
    * 解释器需要理解这种格式，并用以下参数执行`/usr/bin/blah`：
      * `["blah"]`
* `O` - 打开可执行文件
  * 默认情况下，`binfmt_misc`会将二进制文件的完整路径作为参数传递给解释器。
  * 使用此标志后，`binfmt_misc`会打开该文件并传递文件描述符作为参数，而不是完整路径。
  * 这允许解释器执行不可读的二进制文件，但需谨慎使用，因为解释器可能泄露不可读文件的內容。
* `C` - 凭据
  * 当前，`binfmt_misc`根据解释器计算新进程的凭据和安全令牌。
  * 使用此标志后，这些属性会根据二进制文件本身来计算。
  * 此标志隐含了`O`标志。
  * 谨慎使用，因为使用`binfmt_misc`运行由`root`用户拥有的`suid`二进制文件时，解释器将以`root`权限运行。
* `F` - 固定二进制文件
  * `binfmt_misc`的默认行为是在调用`misc`格式文件时延迟启动二进制文件。
    * 然而，这种方式在挂载命名空间和`chroot`环境下可能无法正常工作。
  * `F`模式会在安装模拟器时立即打开二进制文件，并使用打开的镜像启动模拟器。
  * 这意味着只要安装了模拟器，无论环境如何变化，它都始终可用。

因此，为了解决`sudo`提权失败的问题，需要在`binfmt_misc`的注册中添加`C`标志。即，编辑`/usr/lib/binfmt.d/qemu-loongarch64-static.conf`，在末尾添加`C`：

``conf
:qemu-loongarch64:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x02\x01:\xff\xff\xff\xff\xff\xff\xff\xfc\x00\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/usr/bin/qemu-loongarch64-static:FPC
```

需要注意的是，`C`标志有一定的安全风险，需要确保环境安全。
