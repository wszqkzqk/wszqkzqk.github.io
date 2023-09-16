---
layout:     post
title:      使用Stellarium观月
subtitle:   LCPU中秋游园会活动
date:       2023-09-16
author:     wszqkzqk
header-img: img/stellarium/stellarium-bg.webp
catalog:    true
tags:       开源软件 社团活动
---

## 前言

Stellarium是一款开源的天文模拟软件，目前基于Qt6与OpenGL技术，采用GNU GPLv2许可证分发，可以模拟天空中的恒星、行星、卫星、星系等天体的运行，还可以模拟日食、月食、流星雨等天文现象。Stellarium的模拟效果非常逼真，广受天文爱好者赞誉。

北京大学Linux俱乐部将在中秋游园会暨社团招新活动中使用Stellarium演示虚拟天空，欢迎大家参加。本文将面向小白简单介绍使用Stellarium观月、观星的方法，以及Stellarium的一些高级功能。

## 安装

Stellarium可以在Windows、macOS和Linux上运行，可以在[Stellarium官网](https://stellarium.org/)下载安装包，也可以在Linux发行版的软件仓库中安装。

Ubuntu等发行版的官方源中自带了Stellarium，可以使用以下命令安装：

```bash
sudo apt install stellarium
```

Arch Linux则需要添加archlinuxcn源，在`/etc/pacman.conf`中添加以下内容：

```bash
[archlinuxcn]
Server = https://mirrors.pku.edu.cn/archlinuxcn/$arch
```

然后使用以下命令安装：

```bash
sudo pacman -Syu stellarium
```

## 使用

### 基本界面

打开Stellarium后，鼠标划往左侧，会出现一个菜单栏：

![Stellarium菜单栏](/img/stellarium/basic-left-end.webp)

该菜单栏由上至下分别是`所在地点`、`日期/时间`、`搜索`、`设置`、`天文计算`和`说明`。

鼠标移动到下方，会出现一个工具栏。

<!-- 工具栏最左侧的3个开关是有关星座的：

|![](/img/stellarium/basic-bottom1.webp)|
|:-:|
|有关星座的3个开关：`星座连线`、`星座标签`、`星座图绘`|

接下来是赤经网络和地平网络的开关：

|![](/img/stellarium/basic-bottom2.webp)|
|:-:|
|从左到右：`赤经网络`、`地平网络`|

然后是有关场景的开关：
-->

对于初次使用的用户，可以首先关注下图圈出的这组开关：

|![](/img/stellarium/basic-bottom3.webp)|
|:-:|
|从左到右：`地面`、`大气层`、`方位基点`|

以及最右侧的这组用于控制时间流逝速度的开关：

|![](/img/stellarium/basic-bottom4.webp)|
|:-:|
|从左到右：`减缓时间流逝`、`正常时间流逝速度`、`切换至当前时间`、`加快时间流逝`|

### 观月

常规的观月方法自然不必过多介绍，只需要找到月球，然后放大视野即可，但这显然需要对应的时间、地点在空中真的能看到月球才能适用，而Stellarium的功能可远远不止如此。笔者在这里再介绍一些看不见月亮也能观月的方法。

#### 白天不容易看到月球怎么办？

由于地球大气存在瑞利散射，白天的时候月光会被大气层散射的阳光掩盖。那么，我们怎么才能看见月球呢？

回到刚刚的界面介绍部分，找到下方工具栏的`大气层`开关，将其关闭，然后你会发现一个新的世界：

|![](/img/stellarium/atm-off.webp)|
|:-:|
|关闭大气层后的天空|

太阳仍然耀眼，但是月球和繁星已经可以看见了。此时，你可以放大视野，观察月球的表面细节。

|![](/img/stellarium/atm-off2.webp)|
|:-:|
|白天关闭大气显示后观测到的娥眉月|

#### 月球还在地平线下怎么办？

即使我们关闭了大气层，但是月球仍然会被地平线遮挡。此时，我们可以使用`地面`开关，将地面隐藏，这样就可以看见地平线下的月球了！

|![](/img/stellarium/ground-on.webp)|![](/img/stellarium/ground-off.webp)|
|:-:|:-:|
|地面开关打开|地面开关关闭|

#### 我想看见满月/新月/上弦月/下弦月怎么办？

Stellarium提供了一个`日期/时间`的菜单，可以用于调整时间。在这个菜单中，你可以调整年、月、日、时、分、秒。所以，我们只要切换到满月、新月、上弦月、下弦月的日期，就可以在Stellarium中观测到这些月相了。

|![](/img/stellarium/time.webp)|
|:-:|
|日期/时间菜单|

#### 我想看见月食/日食怎么办？

月食和日食是非常有趣的天文现象，但是由于月食和日食的发生频率较低，所以我们不能经常现实中观测到月食和日食。但是，Stellarium可以帮助我们随时观测月食和日食。

那么，我们需要自己查询月食/日食的时间吗？当然不需要！Stellarium提供了一个`天文计算`的菜单，可以用于计算天文现象的时间。在这个菜单中，你可以选择`月食`或`日食`，设置好计算的时间范围，然后选择`计算食`，Stellarium就会自动计算出给定时间段内月食/日食的时间。

更方便的是，计算完成后，双击你想观看的月食/日食，Stellarium就会自动跳转到该月食/日食的时间。

|![](/img/stellarium/lunar-eclipse.webp)|
|:-:|
|月全食|

|![](/img/stellarium/solar-eclipse.webp)
|:-:|
|日环食|

|![](/img/stellarium/solar-eclipse-full.webp)|
|:-:|
|日全食|

### 从月球望地球

既然我们可以从地球上观测月球，那么我们是不是也能在月球上观测地球呢？答案是肯定的！Stellarium的地点切换不仅可以帮你将观测地点切换到地球上的其他地方，还能直接切换到月球！

在`所在地点`菜单中，将`行星`这一项切换到`月球`（虽然月球并不是行星），然后你就可以在月球上观测地球了！

|![](/img/stellarium/location-moon.webp)|
|:-:|
|将地点切换到月球|

或许你会觉得切换之后月球的地面不太逼真，我们也可以进行设置：从左侧菜单栏中选择`星空及显示`，选择`地景`-`月`，这样就可以将地景切换为月球了。

|![](/img/stellarium/landscape-moon.webp)|
|:-:|
|将地景切换为月球|

然而，身处北京的我们可能会发现，这样直接切换后，无论怎么调整时间，都无法从月球上看到地球。这是因为月球已经被地球潮汐锁定，所以月球的一面永远朝向地球，而另一面永远背向地球。而直接切换到月球的操作保留了原始位置（即北京）的经纬度，月球的这一位置恰好永远背对地球，如果我们想在月球上看地球，还需要切换我们在月球上的具体地点：

|![](/img/stellarium/see-earth-from-moon.webp)|
|:-:|
|选择月球正面的地点就能看见地球了|

### 其他高级使用

这里笔者就先不写了😝😝😝，欢迎来参加北京大学Linux俱乐部中秋游园会暨社团招新活动，我们将在活动中介绍更多Stellarium的高级使用方法😜😜😜。
