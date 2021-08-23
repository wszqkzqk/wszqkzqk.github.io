---
layout:       post
title:        在Manjaro下使用VESTA查看或编辑晶体结构
subtitle:     软件推荐
date:         2021-08-17
author:       星外之神
header-img:   img/crystal-bg.png
catalog:      true
tags:         Linux Manjaro 系统配置 化学 结构化学 无机化学
--- 

<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="330" height="86" src="//music.163.com/outchain/player?type=2&id=28302231&auto=1&height=66"></iframe>

## 简介
![](/img/vesta.png)
VESTA是一款3D可视化程序，可用于查看或编辑结构模型、体积数据（如电子/核密度）和晶体结构。可以替代Crystal Maker使用。VESTA是一款免费的闭源软件。

与Crystal Maker不同的是，VESTA是一款跨平台软件，除了Windows外，还支持Mac与Linux:
![](/img/vesta-os-support.png)

## 在Manjaro上安装

### 背景
官方只给出了.bz2格式的压缩包和.rpm安装包，并没有适配Arch系的发行版。

于是，为了能够在Manjaro下更好地使用，我创建了VESTA的PKGBUILD文件，将VESTA从RPM系移植到了Arch系
![](/img/vesta-pkgbuild.png)

### 准备
准备安装的时候，我突然发现AUR上已经有了[vesta](https://aur.archlinux.org/packages/vesta/)软件包  
然而，这个软件包有依赖错误，而且是从官方的.bz2软件包移植的，与我的来源并不相同

于是我将我写的PKGBUILD推送到了AUR（已得到原作者官方认可）：[vesta-rpm](https://aur.archlinux.org/packages/vesta-rpm/)，与原有的[vesta](https://aur.archlinux.org/packages/vesta/)软件包共存
![](/img/vesta-rpm-aur.png)

### 安装
因为已经推送到了AUR，其他用户的安装过程得以大大简化

Manjaro用户可以直接在Pamac软件管理器打开AUR并在AUR中搜索"vesta-rpm",选择安装即可
![](/img/vesta-rpm-pamac.png)

Arch Linux用户或不想用GUI安装界面的Manjaro用户可以在终端中执行：
``` shell
git clone https://aur.archlinux.org/vesta-rpm.git
cd vesta-rpm
makepkg -si
```
![](/img/vesta-rpm-install.png)

### 使用
#### 运行软件
直接运行VESTA的.desktop快捷方式或终端运行`VESTA`即可打开软件
![](/img/vesta-application.png)
#### 打开文件
##### 手动选择
VESTA在安装时并没有绑定文件后缀名默认打开方式，打开相关文件时，可以手动选择：

可以在软件内操作：  
`File`-`Open`-选择所需文件即可

也可在文件打开时的打开方式中选择VESTA：
![](/img/vesta-打开方式.png)
##### 添加MIME
如果认为每次都手动选择很麻烦，可以添加MIME，以后对应格式的文件即可用VESTA直接打开

以KDE为例，找到`设置-应用程序-文件关联`，点击“添加”：
![](/img/vesta-mime.png)
设置对应的类型名后点击确定
![](/img/vesta-mime-2.png)
然后找到刚才添加的新文件类型，分别添加“文件名模式”（即对应的后缀名）并设置“程序优先顺序”（添加VESTA并设置在首位）
![](/img/vesta-mime-3.png)

完成设置后即可在双击文件时自动采用VESTA打开

打开晶体文件后的示例：
![](/img/vesta-YInMnBlue.png)

以后即可使用VESTA愉快地看晶体结构了！

## 转载授权声明
本文采用[署名-非商业性使用-相同方式共享 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh)协议发布
