---
layout:     post
title:      在本地Linux环境使用Gaussian
subtitle:   计算化学软件使用
date:       2023-04-08
author:     wszqkzqk
header-img: img/bg-mountain-darken.webp
catalog:    true
tags:       化学 计算化学 有机化学
---

在计算化学中，Gaussian是一款十分常用的软件，然而，笔者之前在本地Linux下使用它时，却一直出现段错误的报错提示，无法使用。

[![#~/img/gaussian/segfault.webp](/img/gaussian/segfault.webp)](/img/gaussian/segfault.webp)

由于段错误一般是程序设计缺陷导致的，笔者之前一直以为Gaussian的Linux版程序有问题。

Gaussian的文件架构设计很容易让人联想到这点：Gaussian在Linux下的二进制文件具有`.exe`的后缀名，但是却真的是elf格式；都2023年了Gaussian的Linux版的shell脚本居然仍然基于csh；Linux版软件的文件命名居然叫`bsd`；这个软件整体就给人一种很不靠谱的感觉。因此，笔者长期以来均没有在本地的Linux下运行过Gaussian。然而，在一次社团聚会中，学长告诉笔者Gaussian的段错误是自己raise的，实际上很有可能是环境没有配置正确，或者输入文件有问题。笔者这才开始重新在本地的Linux下配置Gaussian。

## 配置

Gaussian的配置教程在网上并不少，但是大多都是面向不懂Linux的小白的，而且也大多运行在超算上，重点在于能用，而并没有在乎本地配置的整洁性。

而笔者长期使用Linux系统，不能简单地像一般的教程那样写`.bashrc`，以免影响正常使用。

笔者选择了在Gaussian软件目录下创建一个配置文件，命名为`1-gaussian.profile`：

```bash
export g16root=/home/wszqkzqk/Downloads # 按需替换为Gaussian文件夹实际所在位置
export GAUSS_SCRDIR=/var/tmp # 存放临时文件的位置
source $g16root/g16/bsd/g16.profile # 加载Gaussian自己的环境配置文件
```

由于笔者使用的fish不兼容POSIX的shell脚本风格，在每次Gaussian相关的软件时，需要先运行`zsh`或者`bash`，再加载`1-gaussian.profile`，然后再运行Gaussian的二进制文件：

```bash
source /home/wszqkzqk/Downloads/g16/1-gaussian.profile
/home/wszqkzqk/Downloads/g16/g16 <input.com> output.log
```

## 报错原因

笔者的Gaussian在此前报错的原因让人哭笑不得😂。笔者之前曾在Windows下使用Gaussian，在其中指定的`chk`文件的输出路径是Windows下的路径，而在Linux下，这个路径是不存在的，因此Gaussian在读取这个文件时，就会报错。

为了跨平台的兼容性，笔者直接将`chk`文件的输出指定在当前目录下，这样就不会出现路径问题了。

## `chk`文件的坑

Gaussian的`chk`文件是一个平台相关的二进制文件。很多人可能知道在超算（运行Linux）上输出的`chk`文件在Windows下无法查看，同理，在Windows下输出的`chk`文件在Linux下也无法查看。同时，Linux下的Gaussian也并没有包含能够转化Windows下生成的`chk`文件的工具，因此如果有在Linux下查看Windows输出`chk`文件的需求，需要预先在Windows下将文件转化为`fchk`。

不过，由于都是Linux系统，本地Linux下的Gaussian也可以直接读取超算生成的`chk`文件，而不需要转化为`fchk`。

## 评价

虽然大多数需要用Gaussian计算的人都不会在本地Linux下使用Gaussian，但笔者认为这还是有很多优势：

* 北京大学正版软件平台仅提供Linux版下载
  * 显然是为了方便超算的使用
  * 但本地Linux也可以直接使用
* 有时候本地使用Gaussian较超算方便灵活
* 北京大学正版软件平台提供的Linux版Gaussian是最新的且有AVX2指令集支持
  * 一般的Windows泄漏版没有支持AVX2指令集
  * Linux版显著更快
* 主要使用Linux的用户不用重启到Windows下使用Gaussian

## 捐赠

|  **支付宝**  |  **微信支付**  |
|  :----:  |  :----:  |
|  [![](/img/donate-alipay.webp)](/img/donate-alipay.webp)  |  [![](/img/donate-wechatpay.webp)](/img/donate-wechatpay.webp)  |
