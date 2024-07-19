---
layout:     post
title:      修复libvirt虚拟机网络连接问题
subtitle:   一个防火墙设置导致的错误
date:       2024-07-19
author:     wszqkzqk
header-img: img/bg-sunrise.webp
catalog:    true
tags:       
---

## 问题

不知道哪次升级以后，笔者的`libvirt`虚拟机突然无法连接到外网。在检查了`libvirt`的网络设置、虚拟机的网络设置、`dnsmasq`的设置等等之后，发现问题出在了防火墙上。

可能是升级后`ufw`的默认策略发生了变化（或者启用状态发生了变化，之前基本没管过防火墙），导致了`libvirt`的虚拟网桥无法正常工作。

## 解决

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

这样，`libvirt`的虚拟机就可以正常连接到外网了。
