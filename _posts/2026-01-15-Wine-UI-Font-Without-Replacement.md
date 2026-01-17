---
layout:     post
title:      在不替换/重映射字体的情况下配置Wine的UI字体
subtitle:   Wine的字体配置技巧
date:       2026-01-15
author:     wszqkzqk
header-img: img/wine/wine-bg.webp
catalog:    true
tags:       Wine archlinux 系统配置 开源软件
---

## 前言

在使用Wine运行Windows应用程序时，默认的UI字体有时可能不符合用户的审美或阅读习惯，尤其是当Linux系统安装了宋体时，Wine往往会优先使用宋体作为UI字体，这会显得界面十分不协调。

传统上，解决这个问题的方法是通过替换或重映射字体文件来强制Wine使用特定的字体，比如将宋体等字体指定为所需要的字体，例如`Noto Sans CJK SC`。然而，这也会导致所有Wine程序在**任何场景下的宋体都变成了指定的字体**，如果有潜在的文本排版场合，可能并不合适。

本文介绍一种不用替换/重映射字体的方式，通过修改Wine的注册表设置，来指定Wine UI使用特定的字体，而不影响其他场景下的字体显示。

## 方法

Windows实际上有对应的UI虚拟逻辑字体名称，`MS Shell Dlg`和`MS Shell Dlg 2`，这些名称会根据系统的区域设置映射到具体的字体。我们可以利用这一点，通过修改Wine的注册表来指定这些虚拟字体名称对应的实际字体。

```bash
wine reg add "HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion\FontSubstitutes" /v "MS Shell Dlg" /t REG_SZ /d "Noto Sans CJK SC" /f
wine reg add "HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion\FontSubstitutes" /v "MS Shell Dlg 2" /t REG_SZ /d "Noto Sans CJK SC" /f
```

这样，Wine的UI字体就会使用`Noto Sans CJK SC`，而不会影响其他场景下的宋体等字体的显示。运行`winecfg`等程序时，界面字体将变得更加协调。

|[![#~/img/wine/winecfg-ui.webp](/img/wine/winecfg-ui.webp)](/img/wine/winecfg-ui.webp)|
|:----:|
|winecfg的字体显示|

不过，需要注意的是，在Wine升级后，可能需要重新设置这些注册表项，因为升级可能会重置这些配置。
