---
layout:     post
title:      修复libvirt虚拟机网络连接问题
subtitle:   一个防火墙设置与dnsmasq导致的错误
date:       2024-07-19
author:     wszqkzqk
header-img: img/bg-sunrise.webp
catalog:    true
tags:       系统配置 虚拟化 网络
---

## 问题

不知道哪次升级以后，笔者的`libvirt`虚拟机突然无法连接到外网。在检查了`libvirt`的网络设置、虚拟机的网络设置、`dnsmasq`的设置等等之后，发现问题出在了防火墙上。

## 解决

### 防火墙规则

首先，查看`ufw`的状态：

```bash
sudo ufw status
```

如果`ufw`是启用的，可以看到类似如下的输出：

```bash
Status: active

To                         Action      From
--                         ------      ----
xxxx                       ALLOW       Anywhere
```

首先允许`virbr0`的访问：

```bash
sudo ufw allow in on virbr0
sudo ufw allow out on virbr0
```

然后，编辑`ufw`的默认配置文件`/etc/default/ufw`，将`DEFAULT_FORWARD_POLICY`设置为`ACCEPT`：

```bash
DEFAULT_FORWARD_POLICY="ACCEPT"
```

可以直接运行`sed`命令：

```bash
sudo sed -i 's/DEFAULT_FORWARD_POLICY="DROP"/DEFAULT_FORWARD_POLICY="ACCEPT"/' /etc/default/ufw
```

最后，重启`ufw`：

```bash
sudo ufw disable
sudo ufw enable
```

### 监听接口占用[^1]

在使用`virsh net-start default`启用网桥的时候，可能会遇到类似如下的错误：

```bash
internal error: Child process (VIR_BRIDGE_NAME=virbr0 /usr/bin/dnsmasq --conf-file=/var/lib/libvirt/dnsmasq/default.conf --leasefile-ro --dhcp-script=/usr/lib/libvirt/libvirt_leaseshelper) unexpected exit status 2: 
dnsmasq: failed to create listening socket for 192.168.122.1: Address already in use
```

这是因为`dnsmasq`的监听接口被占用了。可以通过`netstat`查看：

```bash
sudo lsof -i :53 | grep LISTE
```

可以看到类似如下的输出：

```bash
dnsmasq 75746 dnsmasq 5u  IPv4 912512      0t0  TCP *:domain (LISTEN)
dnsmasq 75746 dnsmasq 7u  IPv6 912514      0t0  TCP *:domain (LISTEN)
```

可以看到`dnsmasq`占用了`53`端口。一般可以通过`systemctl`停止`dnsmasq`：

```bash
sudo systemctl stop dnsmasq
sudo systemctl disable dnsmasq
```

如果确实需要`dnsmasq`，可以编辑`/etc/dnsmasq.conf`，将`bind-interfaces`和`listen-address`注释掉：

```
bind-interfaces
interface=[some physical interface name, e.g. eth0]
listen-address=[ip address of the interface you want, e.g. 192.168.1.1]
```

然后重启`dnsmasq`：

```bash
sudo systemctl restart dnsmasq
```

这样，`libvirt`的虚拟机就可以正常连接到外网了。

[^1]: [libvirt: Virtual network 'default' has not been started](https://wiki.libvirt.org/Virtual_network_default_has_not_been_started.html)
