---
layout:     post
title:      新 Loong Arch Linux 项目发布公告
subtitle:   北京大学学生 Linux 俱乐部接手并重建的 Loong Arch Linux 项目全面对外发布
date:       2025-01-01
author:     wszqkzqk
header-img: img/bg-mountain-darken.webp
catalog:    true
tags:       开源软件 Linux archlinux 国产硬件 虚拟化 龙芯 LoongArchLinux 容器
---

自 2025 年 1 月 1 日起，北京大学学生 Linux 俱乐部（LCPU）接手并重建的 Loong Arch Linux 项目全面对外发布。

## 新的维护团队与结构

LCPU 接手项目后，重新设计了维护结构，并借鉴 [archriscv 社区](https://github.com/felixonmars/archriscv-packages) 的经验，从头构建了更易于维护的[补丁集式维护仓库](https://github.com/lcpu-club/loongarch-packages)与更强大易用的 [devtools-loong64](https://aur.archlinux.org/packages/devtools-loong64) 开发工具。经过两个季度的试运行，目前维护工作已步入正轨。

LCPU 维护团队完成了以下关键工作：

- 修复并构建了 KDE 6、Firefox、Chromium、Code - OSS 等广受欢迎的日用应用，新增了大量原项目中缺失的软件包。
- 积极推动多个重要项目的龙架构修复上游化。
- 整理并发布了丰富详尽的[维护文档](https://github.com/lcpu-club/loongarch-packages/wiki)，使社区参与更加广泛和可行。

这些成果展现了团队强大的开发、维护、教育与组织能力，为项目注入了新的活力。

## 项目信息

* [补丁集仓库](https://github.com/lcpu-club/loongarch-packages)
* [项目页面](https://loongarchlinux.lcpu.dev/)
* [项目文档/贡献指南](https://github.com/lcpu-club/loongarch-packages/wiki)
* [镜像下载](https://github.com/lcpu-club/loongarch-packages/releases)

## 未来目标

新的社区团队致力于：

1. **及时跟随 Arch Linux 官方的更新进度，持续维护 Loong Arch Linux 发行版**
   - 最终借助 [Arch Linux Ports](https://rfc.archlinux.page/0032-arch-linux-ports/) 平台，推动 Arch Linux 官方增加对龙架构的支持，并同步发行龙架构版本。
2. **修复上游软件在龙架构上的构建问题，并尽可能将修复上游化**
   - 最终推动各软件包上游提高龙架构的维护等级。
3. **培养更多能够为龙架构、Arch Linux 及上游社区生态作出贡献的人才，建设更加开放健康的开源社区**

我们欢迎有意愿的同学[加入社区](https://github.com/lcpu-club/loongarch-packages)团队（可联系社区负责人 wszqkzqk@qq.com），共同建设龙架构的软件生态，共同维护 Loong Arch Linux 发行版！

## 原 Loong Arch Linux 用户换源升级指南

对于使用武老师维护的原 Loong Arch Linux 发行版的用户，一般可以先尝试通过换源升级到 LCPU 维护的版本。

1. 编辑文件 `/etc/pacman.d/mirrorlist` ，将内容修改为：
```
Server = https://mirrors.pku.edu.cn/loongarch-lcpu/archlinux/$repo/os/$arch
Server = https://loongarchlinux.lcpu.dev/loongarch/archlinux/$repo/os/$arch
```
2. 更新系统，运行命令：
```bash
sudo rm -f /var/lib/pacman/sync/*
sudo pacman -Syuu
```
3. LCPU 维护的新 Loong Arch Linux 项目建议使用 `pacman-mirrorlist-loong64` 作为镜像列表文件以避免和 Arch Linux 上游的冲突，可在**换源与更新完成后**编辑 `/etc/pacman.conf`，将所有的 `Include = /etc/pacman.d/mirrorlist` 替换为 `Include = /etc/pacman.d/mirrorlist-loong64`：
```bash
sudo sed -i 's/^\s*Include\s*=\s*\/etc\/pacman\.d\/mirrorlist\s*$/Include = /etc/pacman.d/mirrorlist-loong64/' /etc/pacman.conf
```
后续使用中可按需编辑 `/etc/pacman.d/mirrorlist-loong64` 中的镜像配置列表。
