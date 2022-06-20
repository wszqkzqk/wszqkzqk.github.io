---
layout:       post
title:        不借助oh-my-zsh进行Zsh配置
subtitle:     折腾日志
date:         2022-xx-xx
author:       星外之神
header-img:   img/
catalog:      true
tags:         Linux Windows Msys2 Zsh 开源软件
---

## 前言

Linux下最常用的Bash发布于1989年，在此后的发展中并没有引入太多么革命性的功能，已经是一个十分古老的Unix Shell了。虽然它仍然是众Linux发行版预装最多的Shell，但是它的扩展性也早已不如其他的Shell。

Zsh、Fish甚至从Windows下发展而来的PowerShell相比于Bash而言，都极具扩展性。其中，只有Zsh能够很好地兼容Bash的语法，所以，将Zsh作为Bash的替代品非常合适。

然而，Zsh虽然可扩展性高，功能强大，但是它的配置并不容易。一般来说，要方便地配置Zsh需要借助oh-my-zsh这个强大的工具。但是，由于Windows下的Unix Shell环境均是移植而来，利用了Cygwin或衍生库将Unix API Calls转化为Windows API Calls，有显著的性能损失，对于`fork()`等API效率尤其低下，再加上无论是Cygwin还是Msys2都将Unix Shell内置的`echo`、`[`等功能拆分成了独立`.exe`文件，增加了调用性能开销。因此，在Windows下使用本来就比较吃资源的oh-my-zsh十分卡顿，体验并不好。

