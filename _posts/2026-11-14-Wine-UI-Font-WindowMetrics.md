---
layout:     post
title:      配置Wine的标准UI字体：注册表方案与升级后的持久性
subtitle:   FontSubstitutes、WindowMetrics与FontLink的分工、适用场景和回滚方法
date:       2026-11-14
author:     wszqkzqk
header-img: img/wine/wine-bg.webp
catalog:    true
tags:       Wine archlinux 系统配置 开源软件
---

## 前言

之前的 [FontSubstitutes 方案](https://wszqkzqk.github.io/2026/01/15/Wine-UI-Font-Without-Replacement/)和 [FontLink 方案](https://wszqkzqk.github.io/2026/06/14/Wine-UI-FontLink-Without-SimSun/)分别介绍了虚拟 UI 字体和中文回退链的配置。本文继续沿用这套思路，**以 Microsoft YaHei UI 为例**设置标准 UI 字体。示例中的字体名称和字体文件都可以替换，明确请求 `SimSun` 的程序仍使用真实宋体。

可以按程序使用的字体路径选择配置：

| 配置位置 | 适用场景 |
| --- | --- |
| `FontSubstitutes` | `winecfg` 和使用 `MS Shell Dlg` 的对话框 |
| `WindowMetrics` | 标题栏、菜单、消息框、状态栏和 GTK 默认 UI |
| `FontLink\SystemLink` | 直接请求 `Tahoma` 等字体时的中文回退 |

三项配置可以单独使用，也可以组合使用。

## 确认目标字体可用

以微软雅黑为例，字体文件通常位于：

```text
/usr/share/fonts/TTF/msyh.ttc
/usr/share/fonts/TTF/msyhbd.ttc
```

Wine 的用户字体目录为：

```text
C:\users\<用户名>\AppData\Local\Microsoft\Windows\Fonts
```

需要安装时，将字体文件放入该目录即可。

## FontSubstitutes：设置对话框字体

`winecfg` 的资源文件使用 `FONT 8, "MS Shell Dlg"`，可以直接将两个虚拟 UI 字体设为目标字体。

保存为 `wine-ui-font-fontsubstitutes.reg`：

```reg
Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion\FontSubstitutes]
"MS Shell Dlg"="Microsoft YaHei UI"
"MS Shell Dlg 2"="Microsoft YaHei UI"
```

导入：

```bash
wine reg import wine-ui-font-fontsubstitutes.reg
```

恢复为默认值：

```reg
Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion\FontSubstitutes]
"MS Shell Dlg"="SimSun"
"MS Shell Dlg 2"="Tahoma"
```

## WindowMetrics：设置标准 UI 和 GTK 默认字体

`HKEY_CURRENT_USER\Control Panel\Desktop\WindowMetrics` 中的各项分别控制：

- `CaptionFont`：标题栏；
- `SmCaptionFont`：小标题栏；
- `MenuFont`：菜单；
- `MessageFont`：标准消息框和对话框；
- `StatusFont`：状态栏、部分工具提示；
- `IconFont`：图标标题。

GTK 在 Windows 上通过 `NONCLIENTMETRICSW.lfMessageFont` 构造默认的 `gtk-font-name`，因此这组配置也适用于 GTK3/GTK4 的默认 UI。

这些值是 92 字节的 `LOGFONT` 数据。以下示例保留原有字号和字重，只将字体名称改为 `Microsoft YaHei UI`。

<details>
<summary>展开 wine-ui-font-windowmetrics.reg</summary>

```reg
Windows Registry Editor Version 5.00

[HKEY_CURRENT_USER\Control Panel\Desktop\WindowMetrics]
"CaptionFont"=hex:f3,ff,ff,ff,00,00,00,00,00,00,00,00,00,00,00,00,90,01,00,00,00,00,00,01,00,00,00,00,4d,00,69,00,63,00,72,00,6f,00,73,00,6f,00,66,00,74,00,20,00,59,00,61,00,48,00,65,00,69,00,20,00,55,00,49,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00
"IconFont"=hex:08,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,90,01,00,00,00,00,00,01,00,00,00,00,4d,00,69,00,63,00,72,00,6f,00,73,00,6f,00,66,00,74,00,20,00,59,00,61,00,48,00,65,00,69,00,20,00,55,00,49,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00
"MenuFont"=hex:f5,ff,ff,ff,00,00,00,00,00,00,00,00,00,00,00,00,90,01,00,00,00,00,00,01,00,00,00,00,4d,00,69,00,63,00,72,00,6f,00,73,00,6f,00,66,00,74,00,20,00,59,00,61,00,48,00,65,00,69,00,20,00,55,00,49,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00
"MessageFont"=hex:f5,ff,ff,ff,00,00,00,00,00,00,00,00,00,00,00,00,90,01,00,00,00,00,00,01,00,00,00,00,4d,00,69,00,63,00,72,00,6f,00,73,00,6f,00,66,00,74,00,20,00,59,00,61,00,48,00,65,00,69,00,20,00,55,00,49,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00
"SmCaptionFont"=hex:f5,ff,ff,ff,00,00,00,00,00,00,00,00,00,00,00,00,90,01,00,00,00,00,00,01,00,00,00,00,4d,00,69,00,63,00,72,00,6f,00,73,00,6f,00,66,00,74,00,20,00,59,00,61,00,48,00,65,00,69,00,20,00,55,00,49,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00
"StatusFont"=hex:f5,ff,ff,ff,00,00,00,00,00,00,00,00,00,00,00,00,90,01,00,00,00,00,00,01,00,00,00,00,4d,00,69,00,63,00,72,00,6f,00,73,00,6f,00,66,00,74,00,20,00,59,00,61,00,48,00,65,00,69,00,20,00,55,00,49,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00
```

</details>

导入：

```bash
wine reg import wine-ui-font-windowmetrics.reg
```

示例使用 96 DPI 下的字号。使用其他 DPI 或主题字号时，可以先导出当前值，再只修改第 29 字节开始的 UTF-16LE 字体名称：

```bash
wine reg export 'HKCU\Control Panel\Desktop\WindowMetrics' windowmetrics-original.reg /y
```

<details>
<summary>展开恢复用 windowmetrics-tahoma.reg</summary>

```reg
Windows Registry Editor Version 5.00

[HKEY_CURRENT_USER\Control Panel\Desktop\WindowMetrics]
"CaptionFont"=hex:f3,ff,ff,ff,00,00,00,00,00,00,00,00,00,00,00,00,90,01,00,00,00,00,00,01,00,00,00,00,54,00,61,00,68,00,6f,00,6d,00,61,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00
"IconFont"=hex:08,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,90,01,00,00,00,00,00,01,00,00,00,00,54,00,61,00,68,00,6f,00,6d,00,61,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00
"MenuFont"=hex:f5,ff,ff,ff,00,00,00,00,00,00,00,00,00,00,00,00,90,01,00,00,00,00,00,01,00,00,00,00,54,00,61,00,68,00,6f,00,6d,00,61,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00
"MessageFont"=hex:f5,ff,ff,ff,00,00,00,00,00,00,00,00,00,00,00,00,90,01,00,00,00,00,00,01,00,00,00,00,54,00,61,00,68,00,6f,00,6d,00,61,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00
"SmCaptionFont"=hex:f5,ff,ff,ff,00,00,00,00,00,00,00,00,00,00,00,00,90,01,00,00,00,00,00,01,00,00,00,00,54,00,61,00,68,00,6f,00,6d,00,61,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00
"StatusFont"=hex:f5,ff,ff,ff,00,00,00,00,00,00,00,00,00,00,00,00,90,01,00,00,00,00,00,01,00,00,00,00,54,00,61,00,68,00,6f,00,6d,00,61,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00,00
```

</details>

## FontLink：设置中文回退字体

直接请求 `Tahoma`、`Microsoft Sans Serif` 或 `Lucida Sans Unicode` 的程序，可以使用下面的回退配置，让中文优先显示为目标字体。`SimSun` 仍保留在后续回退链中。

<details>
<summary>展开 wine-ui-font-fontlink.reg</summary>

```reg
Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion\FontLink\SystemLink]
"Tahoma"=str(7):"MSYH.TTC,Microsoft YaHei UI\0SIMSUN.TTC,SimSun\0MINGLIU.TTC,PMingLiu\0MSGOTHIC.TTC,MS UI Gothic\0BATANG.TTC,Batang\0MSJH.TTC,Microsoft JhengHei UI\0YUGOTHM.TTC,Yu Gothic UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"
"Microsoft Sans Serif"=str(7):"MSYH.TTC,Microsoft YaHei UI\0SIMSUN.TTC,SimSun\0MINGLIU.TTC,PMingLiu\0MSGOTHIC.TTC,MS UI Gothic\0BATANG.TTC,Batang\0MSJH.TTC,Microsoft JhengHei UI\0YUGOTHM.TTC,Yu Gothic UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"
"Lucida Sans Unicode"=str(7):"MSYH.TTC,Microsoft YaHei UI\0SIMSUN.TTC,SimSun\0MINGLIU.TTC,PMingLiu\0MSGOTHIC.TTC,MS UI Gothic\0BATANG.TTC,Batang\0MSJH.TTC,Microsoft JhengHei UI\0YUGOTHM.TTC,Yu Gothic UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"
```

</details>

导入：

```bash
wine reg import wine-ui-font-fontlink.reg
```

<details>
<summary>展开恢复用 wine-ui-fontlink-default.reg</summary>

```reg
Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion\FontLink\SystemLink]
"Tahoma"=str(7):"SIMSUN.TTC,SimSun\0MINGLIU.TTC,PMingLiu\0MSGOTHIC.TTC,MS UI Gothic\0BATANG.TTC,Batang\0MSYH.TTC,Microsoft YaHei UI\0MSJH.TTC,Microsoft JhengHei UI\0YUGOTHM.TTC,Yu Gothic UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"
"Microsoft Sans Serif"=str(7):"SIMSUN.TTC,SimSun\0MINGLIU.TTC,PMingLiu\0MSGOTHIC.TTC,MS UI Gothic\0BATANG.TTC,Batang\0MSYH.TTC,Microsoft YaHei UI\0MSJH.TTC,Microsoft JhengHei UI\0YUGOTHM.TTC,Yu Gothic UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"
"Lucida Sans Unicode"=str(7):"SIMSUN.TTC,SimSun\0MINGLIU.TTC,PMingLiu\0MSGOTHIC.TTC,MS UI Gothic\0BATANG.TTC,Batang\0MSYH.TTC,Microsoft YaHei UI\0MSJH.TTC,Microsoft JhengHei UI\0YUGOTHM.TTC,Yu Gothic UI\0MALGUN.TTF,Malgun Gothic\0SEGUISYM.TTF,Segoe UI Symbol"
```

</details>

## wineboot --update 后的表现

在 Wine 11.22 中实测，执行 `wineboot --update` 后，各项表现如下：

| 配置项 | 更新后的值 |
| --- | --- |
| `WindowMetrics` 中的六项字体 | 保留自定义值 |
| `MS Shell Dlg` | 保留自定义值 |
| `MS Shell Dlg 2` | 恢复为 `Tahoma` |
| 自定义 `FontLink\SystemLink` | 保留自定义值 |

区域代码页变化时，`MS Shell Dlg` 和 `SystemLink` 会重新生成。统一各启动器的 locale，例如始终使用 `zh_CN.UTF-8`，可以让配置保持稳定。

`MS Shell Dlg 2` 恢复为 `Tahoma` 后，可以单独设回目标字体：

```bash
wine reg add 'HKLM\Software\Microsoft\Windows NT\CurrentVersion\FontSubstitutes' \
  /v 'MS Shell Dlg 2' /t REG_SZ /d 'Microsoft YaHei UI' /f
```

新建 Wine 前缀时，重新导入需要的 `.reg` 即可。

## GTK 默认配置

GTK 会从 `WindowMetrics.MessageFont` 读取默认 UI 字体。保持 Pango 默认的 `win32` 后端即可，通常直接运行：

```bash
wine live-photo-conv-gtk
```

`GSK_RENDERER` 用于选择 GTK 的场景绘制器，字体设置使用前面的注册表配置即可。

## 小结

- 对话框使用 `FontSubstitutes`。
- 标准 UI 和 GTK 默认字体使用 `WindowMetrics`。
- `Tahoma` 等字体的中文回退使用 `FontLink\SystemLink`。

按实际场景导入相应文件即可，需要还原时，导入各节附带的恢复用 `.reg`。
