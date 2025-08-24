---
layout:     post
title:      Arch Linux设置默认内核启动项
subtitle:   在GRUB中为Arch Linux设置默认启动项
date:       2025-08-25
author:     wszqkzqk
header-img: img/qemu/vm-bg.webp
catalog:    true
tags:       开源软件 系统安装 系统配置 系统引导 archlinux GRUB
---

## 前言

不少Arch Linux用户可能都会安装多个内核，比如同时安装`linux`、`linux-lts`和`linux-zen`等。然而，GRUB的默认配置中`GRUB_DEFAULT=0`，会选择按照一定规则排序的第一个，排序规则在Arch Linux下一般由`/etc/grub.d/10_linux`指定，默认如下：

```bash
reverse_sorted_list=$(echo $list | tr ' ' '\n' | sed -e 's/\.old$/ 1/; / 1$/! s/$/ 2/' | version_sort -r | sed -e 's/ 1$/.old/; s/ 2$//')
```

这段代码做了以下几件事：

1. 构建一个包含所有 `/boot/vmlinuz-*` 文件的列表。
2. 把带有 `.old` 后缀的内核（通常是旧版本）临时替换为 `1`，其他文件补上 `2`，保证 `.old` 版本比没有 `.old` 后缀的版本更小。
3. 使用 `version_sort -r` 进行降序版本排序，保证高版本号在前。
4. 最后恢复原文件名。

因此，默认情况下，GRUB会选择`version_sort`排名最高的内核作为启动项。在`linux`、`linux-lts`和`linux-zen`同时存在时，`linux-zen`会成为排名最高的内核（逆序时`z`会在更前面），即`GRUB_DEFAULT=0`时的默认启动项。需要说明的是，`version_sort`排名最高的并不一定是版本最高的内核，因为`vmlinuz`文件的命名形如`vmlinuz-<name>-<version>`，**内核名称**在版本的前面，会**优先决定排序**。

然而，可能在某些时候我们并**不希望**按照这样的**名称排序规则**来选择默认的启动项，此时，我们需要用额外的方式来**明确指定**。

## 保存上次启动项

这种方法适用于 **`/boot`不在Btrfs分区上** 的情况。**保存**上一次的启动项可以使得我们的后续启动在没有更改的时候都按照我们上次的行为执行，**事实上**可以很方便地起到设置默认启动项的作用。

这一方法十分简单，只需要编辑`/etc/default/grub`，找到并更改`GRUB_DEFAULT`的值为`saved`：

```bash
GRUB_DEFAULT=saved
```

此外，还需要在`/etc/default/grub`中添加以下内容，以便在每次启动时保存上次的选择：

```bash
GRUB_SAVEDEFAULT=true
```

然而，对于`/boot`分区在Btrfs上的情况，由于GRUB至今仍只有对Btrfs的只读支持，这一方法**并不适用**。（其他文件系统要么根本不支持，要么有读写支持，仅Btrfs一个特例）

### 手动指定默认启动项

不巧的是，笔者的`/boot`分区就在Btrfs上，因此无法使用上述方法。此时，我们不得不手动指定默认启动项。

#### 数字

最简单的方法是将`GRUB_DEFAULT`的值从`0`改为所需要的**序号**，然而这样的方法可能**不够稳定**，在安装新的内核后可能会导致启动项的顺序发生变化，从而影响默认启动项的选择。

#### 启动项的完整标题

还有一种方法是使用启动项的完整**标题**来指定。例如，如果我们希望将`linux`设置为默认启动项，可以将`GRUB_DEFAULT`的值设置为`"Advanced options for Arch Linux>Arch Linux, with Linux linux"`（如果没有二级菜单，则是`"Arch Linux, with Linux linux"`）。这样的方法虽然可以保证GRUB始终选择指定条目作为默认启动项，但考虑到**语言设置为非英文**的情况，尤其是语言设置可能发生变化的情况，启动项的标题可能会随之变化，从而导致GRUB无法正确识别。

#### 启动项的标识符

使用启动项的标识符是一种可行的方法。对于`/etc/grub.d/10-linux`配置的Linux内核标识符，一般形如`gnulinux-<name>-advanced-<UUID>`，其中`<name>`是内核的名称，`<UUID>`是`/boot`**所在分区的UUID**。

此外，我们可以在`/boot/grub/grub.cfg`中找到每个启动项的完整配置，包括其标识符，只需要找到相应的`menuentry`行，例如：

```bash
$ sudo cat /boot/grub/grub.cfg

...
menuentry 'Arch Linux，使用 Linux linux-zen' --class arch --class gnu-linux --class gnu --class os $menuentry_id_option 'gnulinux-linux-zen-advanced-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' {
...
```

其中，`gnulinux-linux-zen-advanced-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa`就是该启动项的标识符。我们可以将其用作`GRUB_DEFAULT`的值。

这样，GRUB就会始终选择该启动项作为默认启动项。由于`/boot`所在分区的UUID一般不会变化，因此这种方法相对稳定。

### 综合方法

此外，对于`/boot`分区在Btrfs上的情况，还可以将两种方法结合起来使用。GRUB不支持对Btrfs写入，但不代表不能设定`GRUB_DEFAULT=saved`。

由于GRUB可以**读取**Btrfs的内容，`GRUB_DEFAULT=saved`仍然会生效，只是我们**无法**通过`GRUB_SAVEDEFAULT=true`来**保存**上次的选择。（故此时**不应**添加`GRUB_SAVEDEFAULT=true`这一参数）

然而，我们仍然可以手动运行`grub-set-default`命令来设置默认启动项，支持设置的参数与[手动指定默认启动项](#手动指定默认启动项)这一小节完全相同，支持数字、启动项标题，和启动项的标识符三种形式。例如：

```bash
sudo grub-set-default 'gnulinux-linux-zen-advanced-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
```

手动在支持Btrfs读写的Linux操作系统中设置后，在重启时，GRUB会读取Btrfs上的配置，遵守用户对默认启动项的设置。

## 提醒与总结

本文介绍的默认启动项设置方法不仅仅局限于Linux内核启动项，也可以用于外部启动项，例如可以设置**默认启动Windows**。

不管用什么方法设置后，都需要更新GRUB的配置：

```bash
sudo grub-mkconfig -o /boot/grub/grub.cfg
```

无论是保存上次启动项、手动指定启动项，还是结合使用这些方法，读者都可以根据自己的需求灵活配置GRUB，以实现更便捷的系统启动体验。
