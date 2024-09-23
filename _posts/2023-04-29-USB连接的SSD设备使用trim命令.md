---
layout:     post
title:      USB连接的SSD设备使用trim命令
subtitle:   为USB桥接的NVMe设备添加trim支持
date:       2023-04-27
author:     wszqkzqk
header-img: img/storage-device/NVM_Express_logo.webp
catalog:    true
tags:       开源软件 系统配置 系统维护 文件系统
---

## 前言

> 本文主要讨论USB连接的SSD设备使用`trim`命令的方法

`trim`命令是用于清除闪存设备上的无效数据的命令。`trim`可以将文件系统中的删除操作通知给闪存设备，以便闪存设备可以在后台擦除删除的数据。这样可以提高闪存设备的写入性能，也可以减小写放大，延长闪存设备的寿命。

对于USB桥接的NVMe设备，`trim`命令并不可用，然而，很多硬盘盒都支持类似的命令（`unmap`），可以通过UAS（USB Attached SCSI）发送。不过一般情况下，内核并不会自动开启这个功能，需要手动开启。

## 功能支持检查

### `trim`命令支持检查

可以使用`lsblk --discard`检查设备是否支持`trim`命令，如果对应设备的`DISC-GRAN`和`DISC-MAX`字段不为0，则表示支持`trim`命令，反之则不支持，例如：

```
NAME        DISC-ALN DISC-GRAN DISC-MAX DISC-ZERO
sda                0        0B       0B         0
├─sda1             0        0B       0B         0
├─sda2             0        0B       0B         0
├─sda3             0        0B       0B         0
├─sda4             0        0B       0B         0
└─sda5             0        0B       0B         0
nvme0n1            0      512B       2T         0
├─nvme0n1p1        0      512B       2T         0
├─nvme0n1p2        0      512B       2T         0
├─nvme0n1p3        0      512B       2T         0
├─nvme0n1p4        0      512B       2T         0
├─nvme0n1p5        0      512B       2T         0
└─nvme0n1p6        0      512B       2T         0
```

这里可以看到，`nvme0n1`设备支持`trim`命令，而`sda`设备不支持。如果这里就已经显示支持`trim`命令，那么可以跳过后续的步骤，只要设置正确的`discard`挂载选项（或`systemd`的`timer`），文件系统和操作系统就会自动使用`trim`命令。

### `unmap`命令支持检查

如果设备不支持`trim`命令，可以使用以下命令检查设备是否支持`unmap`命令：

```bash
sudo sg_vpd -a /dev/sda | grep "Unmap command supported"
```

如果输出为：

```
Unmap command supported (LBPU): 1
```

则表明设备支持`unmap`命令。

如果设备不支持，可以查询设备的主控是否能够实现`unmap`命令，并找售后更新固件解决问题。

* 补充：后来笔者发现`JMS583`主控的硬盘盒用这一方法查看`unmap`命令支持是不准确的，实际上硬盘盒支持`unmap`命令，但是`sg_vpd`命令并没有输出`Unmap command supported`，然而在后续映射`trim`命令到`unmap`命令后，可以正常使用`trim`命令。

## 映射`trim`命令到`unmap`命令

### 手动映射

如果设备支持`unmap`命令，可以手动映射`trim`命令到`unmap`命令：

```bash
echo unmap | sudo tee /sys/block/sda/device/scsi_disk/*/provisioning_mode
```

### 设置`udev`规则

如果设备支持`unmap`命令但不支持`trim`命令，可以设定udev规则，将`trim`命令映射到`unmap`命令。

首先，应当获取设备的`idVendor`和`idProduct`，可以使用`lsusb`命令获取，可以得到类似的输出（这里的示例是`asm2362`）：

```log
Bus 004 Device 006: ID 174c:2362 ASMedia Technology Inc. wszqkzqk storage by ZQK
```

这里的`idVendor`为`174c`，`idProduct`为`2362`。

同理，对于`jsm583`主控的硬盘盒则是：

```log
Bus 004 Device 004: ID 152d:0583 JMicron Technology Corp. / JMicron USA Technology Corp. JMS583Gen 2 to PCIe Gen3x2 Bridge
```

这里的`idVendor`为`152d`，`idProduct`为`0583`。

然后创建`/etc/udev/rules.d/51-usb-ssd-trim.rules`文件，添加以下内容：

```
ACTION=="add|change", ATTRS{idVendor}=="174c", ATTRS{idProduct}=="2362", SUBSYSTEM=="scsi_disk", ATTR{provisioning_mode}="unmap"

ACTION=="add|change", ATTRS{idVendor}=="152d", ATTRS{idProduct}=="0583", SUBSYSTEM=="scsi_disk", ATTR{provisioning_mode}="unmap"
```

这里的`ATTRS{idVendor}`和`ATTRS{idProduct}`应当替换为实际的`idVendor`和`idProduct`。

最后，重新加载udev规则（重启也可）：

```bash
sudo udevadm control --reload-rules
```

这样USB存储设备就有`trim`支持了。

