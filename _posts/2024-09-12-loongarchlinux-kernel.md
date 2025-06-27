---
layout:     post
title:      龙芯Arch Linux内核维护方法
subtitle:   Loong Arch Linux的linux kernel维护
date:       2024-09-12
author:     wszqkzqk
header-img: img/bg-sunrise.webp
catalog:    true
tags:       系统配置 系统维护 开源软件 Linux archlinux 国产硬件 虚拟化 龙芯 LoongArchLinux
---

## 前言

Linux的kernel config非常复杂，Loong Arch Linux作为Arch Linux的龙芯移植，其kernel config既需要能够**支持龙芯的硬件及相关驱动**，又需要能够及时从Arch Linux的kernel config中**同步新的配置**。

本文介绍了笔者近期探索出的Loong Arch Linux的kernel config维护方法。

## 历程

在此前，笔者曾经尝试过这些维护方法：

1. 单独维护一个Loong Arch Linux的kernel config（`config.loong64`），再从Arch Linux的kernel config中同步新的配置。
  * 但是编辑工作量较大，且在维护者不熟悉kernel config的情况下十分困难。
2. 维护Loong Arch Linux的kernel config与Arch Linux的kernel config的`diff`。
  * 直接生成的`diff`文件几乎每次在上游更新时都会有大量的冲突，导致维护困难。
3. 先使用`make olddefconfig`根据上游的kernel config生成一个新的config，维护维护Loong Arch Linux的kernel config与这一新config的`diff`。
  * 仍然会有大量的冲突，导致维护困难。
4. 先使用`make savedefconfig`根据上游的kernel config生成一个新的config，再添加龙芯架构相关选项与硬件支持，维护Loong Arch Linux的kernel config与这一新config的`diff`。
  * 内容相比之前大大简化，但仍然有冲突风险。

## 新方法

由于适配龙芯的kernel config实际上主要涉及的是功能与驱动支持的开启，笔者想办法对维护进行了进一步的简化。

笔者分别利用Arch Linux上游的kernel config与已知可以良好支持龙芯的AOSC的kernel config，使用`make savedefconfig`生成了两者的简化配置文件`defconfig.arch`与`defconfig.aosc`。

随后，使用`cat defconfig.aoac defconfig.arch > .config`将两者合并，再运行`make savedefconfig`，优先利用Arch Linux的默认配置覆盖AOSC的默认配置。这样处理以后生成了一个新的`defconfig`文件。

这一文件仍然混入了不少来自AOSC的发行版相关配置，笔者进一步对其进行了**系统化**清理。生成`defconfig.arch`与新的`defconfig`的`diff`，并进行提取：

* 仅提取以`+CONFIG_`开头的行
* 不提取以`n`结尾的行
* 去掉开头的`+`

该过程可以用Python脚本实现：

```python
#!/usr/bin/env python3

import sys
import os

def process_patch(patch_path):
    if not os.path.exists(patch_path):
        print(f"Error: File {patch_path} does not exist")
        return

    output_path = os.path.join(os.path.dirname(patch_path), 'loong-addition.config')
    
    with open(patch_path, 'r') as patch_file:
        lines = patch_file.readlines()

    filtered_lines = []
    for line in lines:
        line = line.strip()
        if line.startswith('+CONFIG_') and (line.endswith('=y') or line.endswith('=m')):
            filtered_lines.append(line[1:] + '\n')

    filtered_lines.sort()

    with open(output_path, 'w') as output_file:
        output_file.writelines(filtered_lines)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 cleanpatch.py <patch_file>")
        sys.exit(1)
    
    process_patch(sys.argv[1])
```

将该脚本保存为`cleanpatch.py`，并运行：

```bash
python3 cleanpatch.py defconfig.diff
```

以此便系统性地清理了**部分**AOSC的发行版配置（这样可以用Arch Linux的配置覆盖休眠、zswap压缩算法配置，部分数值设定等发行版相关配置），得到了需要开启的新的**配置项列表**，命名为`loong-addition.config`。

笔者在`PKGBUILD`的`prepare()`函数中，插入了一段逻辑，用于将`loong-addition.config`合并到`config`的末尾：

```
   echo "Setting config..."
   cp ../config .config
+  if [ $CARCH == loong64 ]; then
+    make savedefconfig
+    cat defconfig ../loong-addition.config > .config
+  fi
   make olddefconfig
   diff -u ../config .config || :
```

这样，我们得以完全避免与上游的冲突，同时，也将维护的内容由**整个config文件**或者`diff`文件，变为了**配置项列表**，大大降低了维护的难度。

## 后续维护

后续，我们只需要手动对`loong-addition.config`进行进一步清理，移除不需要的配置项，并实时添加新增的需要额外支持的硬件，即可得到合理的Loong Arch Linux的kernel config。

为了保证追加的配置项的可维护性，我们要求每次对`loong-addition.config`修改后需要进行**整理**：

* 搭建内核构建的环境（可以直接将构建环境[通过`btrfs subvolume snapshot`导出](https://wszqkzqk.github.io/2024/08/22/loongarchlinux-port-tips/#%E4%BF%9D%E5%AD%98)然后[进入环境操作](https://wszqkzqk.github.io/2024/08/22/loongarchlinux-port-tips/#%E8%BF%9B%E5%85%A5%E7%8E%AF%E5%A2%83%E6%9F%A5%E7%9C%8B)）
* 直接使用**Arch Linux上游**的`config`文件，复制到`.config`
* 运行`make savedefconfig`，生成原始的`defconfig`，并复制到`defconfig.orig`
* 运行`make olddefconfig`，生成新的`.config`
* 将`loong-addition.config`的内容加到`.config`中
* 运行`make savedefconfig`，生成新的`defconfig`
* 使用`diff -u defconfig.orig defconfig > defconfig.diff`生成新的`diff`文件
* 使用`cleanpatch.py`清理`defconfig.diff`，得到新的`loong-addition.config`

目前，笔者还没有完全完成不需要的配置项的清理，还需要进一步的维护。但是，这一方法已经大大简化了维护的难度，我们现在可以很容易地同步上游的新配置，同时保持对龙芯硬件的支持。
