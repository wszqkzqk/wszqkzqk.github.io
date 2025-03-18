---
layout:     post
title:      Arch Linux for Loong64 项目 Debuginfod 调试符号服务正式上线！
subtitle:   Loong Arch Linux 的 Debuginfod 服务上线公告与使用说明
date:       2025-03-18
author:     wszqkzqk
header-img: img/bg-mountain-darken.webp
catalog:    true
tags:       系统配置 系统维护 开源软件 Linux archlinux 国产硬件 龙芯 LoongArchLinux
---

我们很高兴地宣布，经过**北京大学学生 Linux 俱乐部**维护团队的持续努力，Arch Linux for Loong64 (新 Loong Arch Linux) 项目的 **Debuginfod 调试符号服务**已全面部署并稳定运行。即日起，所有用户均可通过简单的升级，在 `gdb` 等调试工具中**无缝、自动地获取调试符号包**，大幅提升开发与调试体验！  

## 什么是 Debuginfod？
Debuginfod 是由 `elfutils` 项目提供的**调试符号分发服务**，它允许调试工具（如 `gdb`）**自动从远程服务器下载所需调试符号**，无需手动安装调试包。对于 Arch Linux 用户，这意味着：  
- **开箱即用**：调试时无需手动下载或配置调试符号。  
- **高效轻量**：仅按需获取必要符号，节省存储空间。  
- **无缝集成**：与现有工具链（如 `gdb`）高效集成。  

## 关键改进 
1. 调试符号自动下载  
   只需将 `libelf` 升级至 **0.192-4.1** 或更高版本，系统将自动配置 `DEBUGINFOD_URLS`，指向我们的 Loong64 调试符号包分发服务器。  
   - **升级命令**：  
     ```bash
     sudo pacman -Syu libelf
     ```

2. 无缝兼容性保障
   - Debuginfod 服务适用于大量用于调试的核心组件。  
   - 支持 `gdb`、`delve`、`valgrind`、KDE Crash Report 等主流工具的符号自动获取。  

## 如何验证服务是否生效
1. **检查环境变量**：  
   升级 `libelf` 后，重新登录终端，系统会自动设置 `$DEBUGINFOD_URLS` 环境变量：  
   ```bash
   echo $DEBUGINFOD_URLS
   # 应输出我们的 Debuginfod 服务地址 (https://loongarchlinux.lcpu.dev/debuginfod)
   ```

2. **实际调试测试**：  
   使用 `gdb` 调试任意程序，观察是否自动下载符号，例如：  
   ```bash
   gdb /usr/bin/zstd
   ```
   若看到与以下内容类似的提示，说明服务已生效：
   ```log
   This GDB supports auto-downloading debuginfo from the following URLs:
     <https://loongarchlinux.lcpu.dev/debuginfod>
   Enable debuginfod for this session? (y or [n])
   ```
