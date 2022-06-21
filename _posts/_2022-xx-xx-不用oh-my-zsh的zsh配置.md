---
layout:       post
title:        不借助oh-my-zsh进行Zsh配置
subtitle:     Zsh配置日志
date:         2022-xx-xx
author:       星外之神
header-img:   img/
catalog:      true
tags:         Linux Windows Msys2 Zsh 开源软件
---

## 前言

Linux下最常用的Bash发布于1989年，在此后的发展中并没有引入太多么革命性的功能，已经是一个十分古老的Unix Shell了。虽然它仍然是众Linux发行版预装最多的Shell，但是它的扩展性也早已不如其他的Shell。

Zsh、Fish甚至从Windows下发展而来的PowerShell相比于Bash而言，都极具扩展性。其中，只有Zsh能够很好地兼容Bash的语法，所以，将Zsh作为Bash的替代品非常合适。

然而，Zsh虽然可扩展性高，功能强大，但是它的配置并不容易。一般来说，要方便地配置Zsh需要借助oh-my-zsh这个强大的工具。但oh-my-zsh这个工具主要用Shell脚本写成，性能并不出色，往往需要较长的启动时间。

由于Linux下有十分成熟的内存缓存机制，因此当oh-my-zsh在系统启动后完成过一次加载，之后便可以直接从内存中读取已经缓存的内容，能够做到瞬间启动。然而，Windows下的内存缓冲机制则没有这么友好，如果使用oh-my-zsh，Zsh的加载时间将会特别长。此外，由于Windows下的Unix Shell环境均是移植而来，利用了Cygwin或衍生库将Unix API Calls转化为Windows API Calls，有显著的性能损失，对于Unix的`fork()`API转化效率尤其低下，再加上无论是Cygwin还是Msys2都将Unix Shell内置的`echo`、`[`等功能拆分成了独立`.exe`文件，增加了调用性能开销。因此，在Windows下使用本来就比较吃资源的oh-my-zsh十分卡顿，体验并不好。

## 替代实现

oh-my-zsh提供的便利主要是主题支持和插件支持，当然还有其他的操作绑定。这些我们都可以想办法去进行性能更优的替代实现。

### 主题支持及状态提示

在oh-my-zsh的启发下，[Jan De Dobbeleer](https://github.com/JanDeDobbeleer)开发了一个功能较为接近的[oh-my-posh](https://github.com/JanDeDobbeleer/oh-my-posh)。与oh-my-zsh不同，oh-my-posh采用Go语言开发，虽然运行效率仍然较C/C++低不少，但是其性能仍然显著高于直接用Sell写成的oh-my-zsh。

虽然oh-my-posh看似是为微软的PowerShell设计，但是由于它并没有用绑定在Shell上的语言实现，故实际上oh-my-posh支持多种Shell环境，当然也包括Zsh。


