---
layout:     post
title:      在virt-manager中配置VirGL GPU加速以启动Waydroid
subtitle:   在虚拟机中启用GPU虚拟化并套娃使用Waydroid
date:       2025-06-12
author:     wszqkzqk
header-img: img/qemu/vm-bg.webp
catalog:    true
tags:       开源软件 系统配置 虚拟化 QEMU Android 容器
---

## 前言

Waydroid是一个在Linux上运行Android容器的项目，在Arch Linux下可以很方便得通过AUR或者`archlinuxcn`软件源安装。（Arch Linux的官方内核均已启用`binder`模块，因此Waydroid开箱即用）笔者并不经常使用Waydroid，而且也不喜欢Waydroid将大量启动文件放到KDE Plasma的起动器中，因此笔者选择将Waydroid运行在virt-manager管理的QEMU虚拟机中，虚拟机事实上是[直通笔者的移动硬盘块设备作为存储](https://wszqkzqk.github.io/2023/05/06/%E5%B0%86%E6%9C%AC%E5%9C%B0%E5%AE%89%E8%A3%85%E7%9A%84%E6%93%8D%E4%BD%9C%E7%B3%BB%E7%BB%9F%E4%BD%9C%E4%B8%BA%E8%99%9A%E6%8B%9F%E6%9C%BA%E5%90%AF%E5%8A%A8/)，没有使用虚拟机镜像文件。

然而，笔者发现直接在QEMU虚拟机中运行Waydroid时，只有底栏图标显示，却没有任何界面显示；而直接在裸机上运行完全相同的系统环境时Waydroid则可以正常显示界面。因此，笔者推断是Waydroid需要依赖OpenGL等GPU加速。

笔者之前的虚拟机配置中并没有启用GPU虚拟化，这也导致即使是在虚拟机中运行KDE Plasma桌面环境时，桌面环境的性能也不够好，Konsole的日志输出甚至肉眼可见一行一行地刷新。可见，虚拟机的GPU虚拟化配置是有必要的。

## 宿主机配置

### 安装

在Arch Linux下，安装virt-manager和QEMU的相关软件包：

```bash
sudo pacman -S --needed qemu-full virt-manager
```

如果不需要`qemu-full`的所有功能，可以只安装`qemu-desktop`。

### 配置

安装完成后，启动`virt-manager`程序。可以参考笔者[之前的博客](https://wszqkzqk.github.io/2023/05/06/%E5%B0%86%E6%9C%AC%E5%9C%B0%E5%AE%89%E8%A3%85%E7%9A%84%E6%93%8D%E4%BD%9C%E7%B3%BB%E7%BB%9F%E4%BD%9C%E4%B8%BA%E8%99%9A%E6%8B%9F%E6%9C%BA%E5%90%AF%E5%8A%A8/)中的方法完成基本配置。

这样按照默认方式配置完成后，还需要额外配置GPU虚拟化。

在`virt-manager`中，选择要配置的虚拟机，点击右键，选择`打开`，然后在虚拟机窗口中点击右上角的`显示`按钮，选择`显卡`，型号选择`virtio`，并勾选下方的`3D加速`选项，点击`应用`。

|[![#~/img/qemu/gpu-3d-virtio.webp](/img/qemu/gpu-3d-virtio.webp)](/img/qemu/gpu-3d-virtio.webp)|
|:----:|
|在显卡配置中启用3D加速|

随后，配置`显示协议`。类型选择为`Spice 服务器`，监听类型选择为`无`，并勾选下方的`OpenGL`选项，选择对应的宿主显卡设备。

|[![#~/img/qemu/spice-opengl.webp](/img/qemu/spice-opengl.webp)](/img/qemu/spice-opengl.webp)|
|:----:|
|在显示协议中启用OpenGL|

完成上述配置后，点击`应用`保存配置。

## 虚拟机配置

进入虚拟机。在Arch Linux下，可以通过AUR或者`archlinuxcn`软件源安装Waydroid：

```bash
paru -S --needed waydroid waydroid-image
```

如果需要使用GApps，可以使用`waydroid-image-gapps`镜像：

```bash
paru -S --needed waydroid waydroid-image-gapps
```

启用Waydroid服务：

```bash
sudo systemctl enable --now waydroid-container.service
```

随后，初始化Waydroid：

```bash
sudo waydroid init
```

如果需要使用GApps，可以使用`sudo waydroid init -s GAPPS`命令。

现在，Waydroid已经可以在虚拟机中运行了。首次启动Waydroid时，会运行Android系统的开机动画，随后会进入Android系统的桌面界面，而这些过程需要依赖GPU虚拟化。

可以使用命令启动GUI：

```bash
waydroid show-full-ui
```

|[![#~/img/qemu/waydroid-in-linux-in-virt-manager.webp](/img/qemu/waydroid-in-linux-in-virt-manager.webp)](/img/qemu/waydroid-in-linux-in-virt-manager.webp)|
|:----:|
|在virt-manager的虚拟机Linux中“套娃”运行的Waydroid|

也可以从起动器中选择Android应用。

