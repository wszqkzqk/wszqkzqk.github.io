---
layout:     post
title:      解决宿主使用Tailscale出口节点后Libvirt虚拟机无法联网的问题
subtitle:   虚拟网卡冲突与MTU问题
date:       2025-06-14
author:     wszqkzqk
header-img: img/qemu/vm-bg.webp
catalog:    true
tags:       开源软件 系统配置 虚拟化 QEMU
---

## 前言

在使用Tailscale的出口节点功能时，可能会遇到Libvirt虚拟机无法联网的问题。这通常是由于Tailscale与Libvirt的虚拟网卡配置冲突所导致的。本文将介绍如何解决这一问题。

## 问题描述

Tailscale在使用出口节点时，会将所有流量通过Tailscale网络转发。Libvirt虚拟机通常使用`virbr0`网桥作为默认网络接口，当`virbr0`网桥（一般是`192.168.122.1/24`）的流量也被Tailscale接管并转发时，就会导致虚拟机无法联网。

## 解决方案

### 允许LAN访问

我们可以在Tailscale中允许LAN访问来避免Libvirt虚拟机的流量被Tailscale接管：

```bash
sudo tailscale set --exit-node-allow-lan-access
```

这条命令会允许Tailscale出口节点访问本地网络，从而使Libvirt虚拟机能够正常联网。

### 解决MTU带来的网络问题

设置允许LAN访问后，笔者发现Linux虚拟机可以正常联网，但Windows虚拟机只能访问个别网站。这通常是由于MTU（最大传输单元）设置不当导致的。可以通过以下命令查看当前的MTU设置：

```bash
ip a
```

默认情况下，Windows的虚拟网卡MTU是1500字节，数据包可以顺利通过MTU同样为1500字节的Libvirt虚拟网桥。但是`tailscale0`接口的MTU是1280字节。这是因为Tailscale使用WireGuard隧道，本身需要一些额外的头部空间来封装数据，所以它会将MTU减小。

1500字节的数据包太大了，无法通过。此时，宿主机应该向发送方（Windows VM）发送一个ICMP "Fragmentation Needed"（需要分片）的消息，但由于某种原因（可能是防火墙、NAT的复杂性），这个 ICMP 消息没能成功返回到 Windows VM。导致了MTU黑洞：

* Windows VM 发送了一个大包，但它被`tailscale0`接口静默地丢弃了。
* Windows VM 没有收到任何错误反馈，它不知道包被丢了，只是傻傻地等待服务器的响应。
* 等待超时后，连接失败，看到的就是网站无法访问。

进入受影响的Windows虚拟机，以管理员权限打开命令提示符，设置MTU为更小的值（不超过1280）：

```cmd
netsh interface ipv4 set subinterface "以太网实例 0" mtu=1200 store=persistent
```

其中，`"以太网实例 0"`是虚拟机中网络接口的名称，可以通过`ipconfig`命令查看。重启Windows虚拟机，让设置完全生效。之后再尝试访问之前无法访问的网站，应该就没问题了。
