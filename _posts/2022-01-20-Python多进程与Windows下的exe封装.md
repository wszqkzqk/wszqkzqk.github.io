---
layout:     post
title:      Python多进程与Windows下的exe封装的踩坑实践
subtitle:   multiprocessing、pyinstaller、nuitka的尝试
date:       2022-01-20
author:     星外之神
header-img: img/nuitka-pyinstaller.webp
catalog:    true
tags:       python
--- 



## 前言

由于现在电脑CPU的单核性能提升已经遇到瓶颈，最近AMD与Intel的处理器也通过堆核来大幅提高性能，主流处理器早已达到了达到了8核16线程。因此，合理利用好多核性能对程序运行速度的提升非常重要。最近我打算简单体验一下Python的`multiprocessing`库中的多进程功能～～～

在摸鱼过程中，顺便学习了一下两个打包工具——`nuitka`和`pyinstaller`的使用（当然，我尝试打包了Windows版本，由于Linux的大多数发行版均已经预装Python，并没有什么打包的必要）

## 多进程踩坑经历

### 应用场景选择

在尝试`multiprocessing`库之前首先应当选择一个合适的应用场景，要求计算处理的对象可以分成若干块并行计算。我选择的是

