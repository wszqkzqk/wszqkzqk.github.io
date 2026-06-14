---
layout:     post
title:      通过注册表覆盖Wine的系统字体链接以规避宋体作为UI默认字体
subtitle:   另一种不影响显式字体请求的Wine UI字体优化方案
date:       2026-06-14
author:     wszqkzqk
header-img: img/wine/wine-bg.webp
catalog:    true
tags:       Wine archlinux 系统配置 开源软件
---

## 前言

[之前](https://wszqkzqk.github.io/2026/01/15/Wine-UI-Font-Without-Replacement/) 介绍过通过 `FontSubstitutes` 修改 `MS Shell Dlg` 和 `MS Shell Dlg 2` 的方法，让 Wine 的 UI 字体在不替换字体文件的前提下变得更顺眼。那套方案简单直接，但本质是改动 Windows 的虚拟逻辑字体映射，对个别坚持自己指定字体的程序未必生效。

这里再补充一条思路：直接覆盖 `FontLink\SystemLink` 下的系统字体链接表，把常见 UI 字体回退链里的 `simsun`（宋体）去掉。

Wine 在中文区域设置下，经常把宋体塞进各种字体的 fallback 链里。一旦 Linux 系统安装了宋体，这些程序在显示中文时就会优先回退到宋体，界面瞬间回到二十年前的风格。更麻烦的是，如果直接把宋体重映射成别的字体，那些真正需要宋体的软件反而会出现显示错误。

通过覆盖 `SystemLink`，我们只是调整"某个字体缺字时该找谁替补"的顺序，并不改变字体文件本身的映射关系。换句话说，程序显式请求宋体时仍然能得到宋体；但 UI 字体在需要中文字形时，会优先走我们指定的那几条更现代的 fallback 路径。

## FontLink\SystemLink 是什么

Windows 的 `FontLink`（字体链接）机制解决的是单一字体无法覆盖全部字符的问题。注册表路径

```
HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion\FontLink\SystemLink
```

下存放的是"系统链接"，也就是各字体在缺字时应该依次尝试的备用字体列表。比如 `Tahoma` 不含 CJK 字形，系统遇到中文时就会按这个列表去找能显示的字体。

Wine 会根据当前区域设置填充这些值。在中文环境下，很多条目的 fallback 链头部会被填上宋体相关条目，于是宋体就成了事实上的中文 UI 字体。

## 覆盖注册表

下面的注册表片段把常见 UI 字体（Segoe UI、Tahoma、Meiryo、Microsoft JhengHei、Yu Gothic UI 等）的 fallback 链里的宋体移除，同时保留其他东亚字体作为替补。这样即使系统里存在 `simsun.ttc`，Wine 也不会优先把它挑出来当 UI 字体。

把以下内容保存为 `wine-ui-fontlink.reg`：

```reg
Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion\FontLink\SystemLink]

"Lucida Sans Unicode"=str(7):"MINGLIU.TTC,PMingLiu\0MSGOTHIC.TTC,MS UI Gothic\0BATANG.TTC,Batang\0MSYH.TTC,Microsoft YaHei UI\0MSJH.TTC,Microsoft JhengHei UI\0YUGOTHM.TTC,Yu Gothic UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"

"Meiryo"=str(7):"SEGOEUI.TTF,Segoe UI\0YUGOTHM.TTC,Yu Gothic UI\0MSGOTHIC.TTC,MS UI Gothic\0MSJH.TTC,Microsoft JhengHei\0MSYH.TTC,Microsoft YaHei\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"

"Meiryo Bold"=str(7):"SEGOEUIB.TTF,Segoe UI Bold\0YUGOTHB.TTC,Yu Gothic UI Bold\0MSGOTHIC.TTC,MS UI Gothic\0MSJHBD.TTC,Microsoft Jhenghei Bold\0MSYHBD.TTC,Microsoft YaHei Bold\0MALGUNBD.TTF,Malgun Gothic Bold\0SEGUISYM.TTF,Segoe UI Symbol"

"Meiryo UI"=str(7):"SEGOEUI.TTF,Segoe UI\0YUGOTHM.TTC,Yu Gothic UI\0MSGOTHIC.TTC,MS UI Gothic\0MSJH.TTC,Microsoft Jhenghei UI\0MSYH.TTC,Microsoft YaHei UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"

"Meiryo UI Bold"=str(7):"SEGOEUIB.TTF,Segoe UI Bold\0YUGOTHB.TTC,Yu Gothic UI Bold\0MSGOTHIC.TTC,MS UI Gothic\0MSJHBD.TTC,Microsoft Jhenghei UI Bold\0MSYHBD.TTC,Microsoft YaHei UI Bold\0MALGUNBD.TTF,Malgun Gothic Bold\0SEGUISYM.TTF,Segoe UI Symbol"

"Microsoft JhengHei"=str(7):"SEGOEUI.TTF,Segoe UI\0MINGLIU.TTC,MingLiU\0MSYH.TTC,Microsoft YaHei\0MEIRYO.TTC,Meiryo\0MALGUN.TTF,Malgun Gothic\0YUGOTHM.TTC,Yu Gothic UI\0SEGUISYM.TTF,Segoe UI Symbol"

"Microsoft JhengHei Bold"=str(7):"SEGOEUIB.TTF,Segoe UI Bold\0MINGLIU.TTC,MingLiU\0MSYHBD.TTC,Microsoft YaHei Bold\0MEIRYOB.TTC,Meiryo Bold\0MALGUNBD.TTF,Malgun Gothic Bold\0YUGOTHB.TTC,Yu Gothic UI Bold\0SEGUISYM.TTF,Segoe UI Symbol"

"Microsoft JhengHei UI"=str(7):"SEGOEUI.TTF,Segoe UI\0MINGLIU.TTC,MingLiU\0MSYH.TTC,Microsoft YaHei UI\0MEIRYO.TTC,Meiryo UI\0MALGUN.TTF,Malgun Gothic\0YUGOTHM.TTC,Yu Gothic UI\0SEGUISYM.TTF,Segoe UI Symbol"

"Microsoft JhengHei UI Bold"=str(7):"SEGOEUIB.TTF,Segoe UI Bold\0MINGLIU.TTC,MingLiU\0MSYHBD.TTC,Microsoft YaHei UI Bold\0MEIRYOB.TTC,Meiryo UI Bold\0MALGUNBD.TTF,Malgun Gothic Bold\0YUGOTHB.TTC,Yu Gothic UI Bold\0SEGUISYM.TTF,Segoe UI Symbol"

"Microsoft JhengHei UI Light"=str(7):"SEGOEUIL.TTF,Segoe UI Light\0MINGLIU.TTC,MingLiU\0MSYHL.TTC,Microsoft YaHei UI Light\0MEIRYO.TTC,Meiryo UI\0MALGUNSL.TTF,Malgun Gothic Semilight\0YUGOTHL.TTC,Yu Gothic UI Light\0SEGUISYM.TTF,Segoe UI Symbol"

"Microsoft Sans Serif"=str(7):"MINGLIU.TTC,PMingLiu\0MSGOTHIC.TTC,MS UI Gothic\0BATANG.TTC,Batang\0MSYH.TTC,Microsoft YaHei UI\0MSJH.TTC,Microsoft JhengHei UI\0YUGOTHM.TTC,Yu Gothic UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"

"MingLiU"=str(7):"MICROSS.TTF,Microsoft Sans Serif\0MSMINCHO.TTC,MS Mincho\0BATANG.TTC,BatangChe\0MSJH.TTC,Microsoft JhengHei UI\0MSYH.TTC,Microsoft YaHei UI\0YUGOTHM.TTC,Yu Gothic UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"

"MingLiU-ExtB"=str(7):"MICROSS.TTF,Microsoft Sans Serif\0MINGLIU.TTC,MingLiU\0MSMINCHO.TTC,MS Mincho\0BATANG.TTC,BatangChe\0MSJH.TTC,Microsoft JhengHei UI\0MSYH.TTC,Microsoft YaHei UI\0YUGOTHM.TTC,Yu Gothic UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"

"MingLiU_HKSCS"=str(7):"MICROSS.TTF,Microsoft Sans Serif\0MINGLIU.TTC,MingLiU\0MSMINCHO.TTC,MS Mincho\0BATANG.TTC,BatangChe\0MSJH.TTC,Microsoft JhengHei UI\0MSYH.TTC,Microsoft YaHei UI\0YUGOTHM.TTC,Yu Gothic UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"

"MingLiU_HKSCS-ExtB"=str(7):"MICROSS.TTF,Microsoft Sans Serif\0MINGLIU.TTC,MingLiU_HKSCS\0MINGLIU.TTC,MingLiU\0MSMINCHO.TTC,MS Mincho\0BATANG.TTC,BatangChe\0MSJH.TTC,Microsoft JhengHei UI\0MSYH.TTC,Microsoft YaHei UI\0YUGOTHM.TTC,Yu Gothic UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"

"MS Gothic"=str(7):"MINGLIU.TTC,MingLiU\0GULIM.TTC,GulimChe\0YUGOTHM.TTC,Yu Gothic UI\0MSJH.TTC,Microsoft JhengHei UI\0MSYH.TTC,Microsoft YaHei UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"

"MS Mincho"=str(7):"MINGLIU.TTC,MingLiU\0BATANG.TTC,Batang\0YUGOTHM.TTC,Yu Gothic UI\0MSJH.TTC,Microsoft JhengHei UI\0MSYH.TTC,Microsoft YaHei UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"

"MS PGothic"=str(7):"MINGLIU.TTC,PMingLiU\0GULIM.TTC,Gulim\0YUGOTHM.TTC,Yu Gothic UI\0MSJH.TTC,Microsoft JhengHei UI\0MSYH.TTC,Microsoft YaHei UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"

"MS PMincho"=str(7):"MINGLIU.TTC,PMingLiU\0BATANG.TTC,Batang\0YUGOTHM.TTC,Yu Gothic UI\0MSJH.TTC,Microsoft JhengHei UI\0MSYH.TTC,Microsoft YaHei UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"

"MS UI Gothic"=str(7):"MICROSS.TTF,Microsoft Sans Serif\0MINGLIU.TTC,PMingLiU\0GULIM.TTC,Gulim\0YUGOTHM.TTC,Yu Gothic UI\0MSJH.TTC,Microsoft JhengHei UI\0MSYH.TTC,Microsoft YaHei UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"

"PMingLiU"=str(7):"MICROSS.TTF,Microsoft Sans Serif\0MSMINCHO.TTC,MS PMincho\0BATANG.TTC,Batang\0MSJH.TTC,Microsoft JhengHei UI\0MSYH.TTC,Microsoft YaHei UI\0YUGOTHM.TTC,Yu Gothic UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"

"PMingLiU-ExtB"=str(7):"MICROSS.TTF,Microsoft Sans Serif\0MINGLIU.TTC,PMingLiU\0MSMINCHO.TTC,MS PMincho\0BATANG.TTC,Batang\0MSJH.TTC,Microsoft JhengHei UI\0MSYH.TTC,Microsoft YaHei UI\0YUGOTHM.TTC,Yu Gothic UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"

"Segoe UI"=str(7):"TAHOMA.TTF,Tahoma\0MSYH.TTC,Microsoft YaHei UI\0MEIRYO.TTC,Meiryo UI\0MSGOTHIC.TTC,MS UI Gothic\0MSJH.TTC,Microsoft JhengHei UI\0MALGUN.TTF,Malgun Gothic\0MINGLIU.TTC,PMingLiU\0GULIM.TTC,Gulim\0YUGOTHM.TTC,Yu Gothic UI\0SEGUISYM.TTF,Segoe UI Symbol"

"Tahoma"=str(7):"MINGLIU.TTC,PMingLiu\0MSGOTHIC.TTC,MS UI Gothic\0BATANG.TTC,Batang\0MSYH.TTC,Microsoft YaHei UI\0MSJH.TTC,Microsoft JhengHei UI\0YUGOTHM.TTC,Yu Gothic UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"

"Yu Gothic UI"=str(7):"SEGOEUI.TTF,Segoe UI\0MSJH.TTC,Microsoft JhengHei\0MSYH.TTC,Microsoft YaHei\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"

"Yu Gothic UI Bold"=str(7):"SEGOEUIB.TTF,Segoe UI Bold\0MSJHBD.TTC,Microsoft Jhenghei UI Bold\0MSYHBD.TTC,Microsoft YaHei Bold\0MALGUNBD.TTF,Malgun Gothic Bold\0SEGUISYM.TTF,Segoe UI Symbol"

"Yu Gothic UI Light"=str(7):"SEGOEUIL.TTF,Segoe UI Light\0MSJHL.TTC,Microsoft Jhenghei UI Light\0MSYHL.TTC,Microsoft YaHei Light\0MALGUNSL.TTF,Malgun Gothic Semilight\0SEGUISYM.TTF,Segoe UI Symbol"

"Yu Gothic UI Semibold"=str(7):"SEGUISB.TTF,Segoe UI Semibold\0MSJH.TTC,Microsoft Jhenghei UI\0MSYH.TTC,Microsoft YaHei\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"

"Yu Gothic UI Semilight"=str(7):"SEGOEUISL.TTF,Segoe UI Semilight\0MSJH.TTC,Microsoft Jhenghei UI\0MSYH.TTC,Microsoft YaHei\0MALGUNSL.TTF,Malgun Gothic Semilight\0SEGUISYM.TTF,Segoe UI Symbol"
```

然后导入：

```bash
wine regedit wine-ui-fontlink.reg
```

如果希望作用于特定 Wine prefix，先导出 `WINEPREFIX`：

```bash
WINEPREFIX=/path/to/prefix wine regedit wine-ui-fontlink.reg
```

## 需要注意的几点

* 这个方案和 `FontSubstitutes` 改 `MS Shell Dlg` 的思路是互补的。可以单独用，也可以同时用。如果只改 `FontLink`，那么程序自己硬编码 `"Tahoma"` 或 `"Segoe UI"` 时仍然走这里定义的 fallback 链；如果还改了 `FontSubstitutes`，则虚拟逻辑字体会先解析成指定字体，再进入各自的 fallback。
* *Wine 升级后这些注册表项可能会被重置，和上一篇文章一样，需要重新导入。
* 列表里保留了 `MingLiU`（细明体）等字体条目，是因为它们在某些场景下确实是合理的 fallback，而且比宋体更适合搭配现代 UI。如果你的系统里完全没有安装这些字体，Wine 会按顺序继续往下找，最终落到 `Microsoft YaHei` 或 `Malgun Gothic` 等更常见的字体上。
* 某些程序内部会读取注册表里的 `SystemLink` 来决定自己的字体回退，因此这个改动对它们的 UI 也有效；但反过来说，如果某个应用显式把宋体写死在资源文件里，这个方案不会把它强制替换掉——这正是我们想要的行为。

## 小结

通过覆盖 `HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion\FontLink\SystemLink`，可以在不替换、不重映射宋体文件的前提下，让 Wine 的常用 UI 字体在需要中文字形时绕过宋体。这样既保留了宋体本身供真正需要它的程序使用，又能让大部分现代 Windows 应用在 Wine 下的中文界面看起来更协调。
