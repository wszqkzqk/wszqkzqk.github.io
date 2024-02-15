---
layout:     post
title:      使用Btrfs Balance调整分配过多的元数据空间
subtitle:   减小Btrfs元数据空间分配大小的方法
date:       2024-02-15
author:     wszqkzqk
header-img: img/storage-device/various-media.webp
catalog:    true
tags:       开源软件 系统配置 文件系统
---

## 前言

笔者只有单一设备，并没有组RAID，一直以来，笔者本以为自己用不上Btrfs的数据平衡功能。

然而，笔者最近却发现，笔者使用的Btrfs文件系统`Metadata`不知为什么，分配空间达到了`96 GB`（加上默认的`DUP`就是`192 GB`），而实际却仅使用了不到`7 GB`。而分配给`Metadata`的空间是无法给`Data`使用的，导致文件系统实际可用空间浪费严重。

```bash
Overall:
    Device size:                 953.67GiB
    Device allocated:            638.07GiB
    Device unallocated:          315.60GiB
    Device missing:                  0.00B
    Device slack:                    0.00B
    Used:                        422.44GiB
    Free (estimated):            346.09GiB      (min: 188.29GiB)
    Free (statfs, df):           346.09GiB
    Data ratio:                       1.00
    Metadata ratio:                   2.00
    Global reserve:              512.00MiB      (used: 0.00B)
    Multiple profiles:                  no

Data,single: Size:446.01GiB, Used:415.52GiB (93.16%)
   /dev/nvme0n1p2        446.01GiB

Metadata,DUP: Size:96.00GiB, Used:3.46GiB (3.61%)
   /dev/nvme0n1p2        192.00GiB

System,DUP: Size:32.00MiB, Used:80.00KiB (0.24%)
   /dev/nvme0n1p2         64.00MiB

Unallocated:
   /dev/nvme0n1p2        315.60GiB
```

因此，笔者决定使用Btrfs的数据平衡功能，将`Metadata`的空间分配调整到合适的大小。

## Btrfs Balance的使用

Btrfs的数据平衡功能是通过`btrfs balance`命令实现的。`btrfs balance`命令可以将文件系统中的数据重新分配，可以有效减小占用率过低的数据块大量占用未分配空间。

对所有数据进行平衡往往需要耗费很多的时间，由于我们主要针对的内容是`Metadata`，我们可以使用`filter`进行指定。例如，如果我们需要对`/`文件系统中占用在50%以下的`Metadata`进行平衡，我们可以使用：

```bash
sudo btrfs balance start -v -musage=50 /
```

这样，我们就可以只对`Metadata`占用在50%以下的数据进行平衡，而不用对整个文件系统进行平衡。有时候，一次的平衡可能并不能完全解决问题，我们还可以反复运行这一命令，往往可以得到更好的效果。

笔者2次运行后，结果如下：

```bash
wszqkzqk@wszqkzqk-pc ~> sudo btrfs balance start -v -musage=50 /
Dumping filters: flags 0x6, state 0x0, force is off
  METADATA (flags 0x2): balancing, usage=50
  SYSTEM (flags 0x2): balancing, usage=50
Done, had to relocate 25 out of 477 chunks
```

平衡以后，`Metadata`的分配空间更加合理，从`96 GB`减小到了`5 GB`。

```bash
wszqkzqk@wszqkzqk-pc ~/p/wszqkzqk.github.io (master)> sudo btrfs filesystem usage /
Overall:
    Device size:                 953.67GiB
    Device allocated:            504.07GiB
    Device unallocated:          449.60GiB
    Device missing:                  0.00B
    Device slack:                    0.00B
    Used:                        422.44GiB
    Free (estimated):            480.09GiB      (min: 255.29GiB)
    Free (statfs, df):           480.09GiB
    Data ratio:                       1.00
    Metadata ratio:                   2.00
    Global reserve:              512.00MiB      (used: 0.00B)
    Multiple profiles:                  no

Data,single: Size:446.01GiB, Used:415.52GiB (93.16%)
   /dev/nvme0n1p2        446.01GiB

Metadata,DUP: Size:29.00GiB, Used:3.46GiB (11.94%)
   /dev/nvme0n1p2         58.00GiB

System,DUP: Size:32.00MiB, Used:80.00KiB (0.24%)
   /dev/nvme0n1p2         64.00MiB

Unallocated:
   /dev/nvme0n1p2        449.60GiB
wszqkzqk@wszqkzqk-pc ~/p/wszqkzqk.github.io (master)> sudo btrfs filesystem usage /
Overall:
    Device size:                 953.67GiB
    Device allocated:            456.07GiB
    Device unallocated:          497.60GiB
    Device missing:                  0.00B
    Device slack:                    0.00B
    Used:                        422.44GiB
    Free (estimated):            528.09GiB      (min: 279.29GiB)
    Free (statfs, df):           528.09GiB
    Data ratio:                       1.00
    Metadata ratio:                   2.00
    Global reserve:              512.00MiB      (used: 0.00B)
    Multiple profiles:                  no

Data,single: Size:446.01GiB, Used:415.52GiB (93.16%)
   /dev/nvme0n1p2        446.01GiB

Metadata,DUP: Size:5.00GiB, Used:3.46GiB (69.25%)
   /dev/nvme0n1p2         10.00GiB

System,DUP: Size:32.00MiB, Used:80.00KiB (0.24%)
   /dev/nvme0n1p2         64.00MiB

Unallocated:
   /dev/nvme0n1p2        497.60GiB
```
