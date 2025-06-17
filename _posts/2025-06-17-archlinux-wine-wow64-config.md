---
layout:     post
title:      Wine WoW64下的渲染库配置
subtitle:   解决Arch Linux的Wine切换到WoW64后部分Windows应用的渲染问题
date:       2025-06-17
author:     wszqkzqk
header-img: img/wine/wine-bg.webp
catalog:    true
tags:       开源软件 Wine archlinux 系统配置
---

## 前言

Arch Linux近期（2025.06.16，`extra/wine 10.9-1`）将Wine切换到了WoW64（Windows 32-bit on Windows 64-bit）模式，以移除对**Linux系统下32位库**（`lib32-*`）的依赖。这一变更虽然简化了系统的维护，但也导致了一些Windows应用在渲染方面出现问题。部分应用无法显示渲染内容而黑屏，另外还有一些应用渲染十分缓慢，速度不可接受。

## 解决

**WineD3D**目前在**WoW64**模式下的渲染支持仍然**不完善**，尤其是对于某些依赖于特定渲染库的应用。为了解决这些问题，我们手动配置Wine的渲染库**替代WineD3D**即可。[^1]

[^1]: Arch Linux官方的[更新公告](https://archlinux.org/news/transition-to-the-new-wow64-wine-and-wine-staging/)提到现存的32位Wine环境需要重置，以便在WoW64模式下正常工作。（注意自行备份）**64位**Wine环境可以**直接使用**，不受影响。

### 安装

首先，安装`winetricks`，这是一个用于管理Wine环境的工具，可以帮助我们安装和配置所需的Windows组件。

```bash
sudo pacman -S winetricks
```

### 配置渲染库

为了有齐全的Direct3D支持，我们需要安装额外的渲染库。DXVK是DirectX 8-11的Vulkan实现，而VKD3D是DirectX 12的Vulkan实现。我们可以通过`winetricks`来安装这些库。

```bash
winetricks dxvk vkd3d
```

### 验证

安装完成后，可以通过运行一些依赖于Direct3D的Windows应用来验证渲染是否正常。例如，可以尝试运行一些游戏或图形密集型应用，检查它们的渲染效果是否正常。

经过笔者的测试，安装`dxvk`和`vkd3d`后，64位Windows应用的渲染问题基本得到了解决。大多数应用可以正常显示渲染内容，且渲染速度也有了明显提升。然而，虽然部分32位在安装`dxvk`和`vkd3d`后也能正常渲染，但仍有一些32位应用的渲染仍然存在问题。（比如Plants vs. Zombies及其改版；用Unity完全重写的融合版是64位，不受此影响；笔者写的[pypvz](https://github.com/wszqkzqk/pypvz)可原生运行，也不受此影响）
