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



由于现在电脑CPU的单核性能提升已经遇到瓶颈，最近AMD与Intel的处理器核心数也远比以前多，因此，合理利用好多核性能对程序运行速度的提升非常重要。最近我打算尝试一下Python的`multiprocessing`库中的多进程