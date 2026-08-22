---
layout:       post
title:        Live Photo Converter：首个登陆 Android 的完整 Vala 应用，把动态照片处理带到 Android
subtitle:     在手机上制作、提取和修复动态照片
date:         2026-08-22
author:       wszqkzqk
header-img:   img/bg-sunrise.webp
catalog:      true
tags:         开源软件 Vala GTK4 LibAdwaita Android 媒体文件 动态照片
---

## Android 版本

[Live Photo Converter](https://github.com/wszqkzqk/live-photo-conv) 0.50.0 已经发布。这个版本第一次提供了 Android APK，动态照片可以直接在手机上制作、提取和修复，不必先把文件传到电脑。

Android 版保留了桌面版的三个主要功能：

- **制作**：把视频和静态图片合成为动态照片；只有视频时，也可以用视频的第一帧生成封面。
- **提取**：导出主图片、嵌入视频、视频帧和长曝光照片。
- **修复**：重新写入被社交平台删除或破坏的 XMP 元数据。

Android 版目前只提供图形界面，桌面端的命令行工具和原有安装方式不受影响。对动态照片格式和桌面版界面不熟悉的读者，可以先看之前的[介绍文章](https://wszqkzqk.github.io/2026/05/05/live-photo-conv-gtk4-gui/)；本文只介绍 0.50 的变化。

据目前所知，这也是第一个登陆 Android 的完整 Vala 应用。此前通过 pixiewood 构建的 Vala 工程主要是演示性质的模板。

<div align="center">
  <a href="/img/media/live-photo-conv/live-photo-conv-logo.svg"><img src="/img/media/live-photo-conv/live-photo-conv-logo.svg" alt="Live Photo Converter" style="width: 500px; max-width: 100%;" /></a>
</div>

## 手机上的操作方式

Android 版和桌面版使用同一套 GTK4 / LibAdwaita 界面，仍然分为制作、提取、修复三个标签页。桌面端可以拖放文件，手机上则通过系统文件选择器选择文件和输出目录。

| [![提取](/img/media/live-photo-conv/extract-ui-cn.webp)](/img/media/live-photo-conv/extract-ui-cn.webp) | [![制作](/img/media/live-photo-conv/make-ui-cn.webp)](/img/media/live-photo-conv/make-ui-cn.webp) | [![修复](/img/media/live-photo-conv/repair-ui-cn.webp)](/img/media/live-photo-conv/repair-ui-cn.webp) |
|:---:|:---:|:---:|
| 提取 | 制作 | 修复 |

从相册或文件管理器中选好文件和输出位置后，应用会完成处理并保存结果。整个过程不需要用户填写文件路径，也不需要额外申请整个存储空间的访问权限。

视频处理所需的 GStreamer 组件已经随 APK 一起打包，安装应用后不需要另外安装 FFmpeg、GStreamer 或其他媒体组件。

## 安装

从 [GitHub Releases](https://github.com/wszqkzqk/live-photo-conv/releases) 下载对应设备架构的 APK：

- `*-android-arm64-v8a.apk`：适用于绝大多数现代手机和平板；
- `*-android-x86_64.apk`：适用于 x86 设备和模拟器；
- `*-android-universal.apk`：通用包，体积更大。

系统要求 Android 12 或更高版本。安装时，系统可能会要求允许当前浏览器或文件管理器安装未知来源的应用。

Android 版目前仍标记为实验性版本。它只包含图形界面。桌面端的命令行工具、共享库和原有安装方式不受影响。

## 这个版本还修了什么

除了 Android 支持，0.50 还包含了一批与日常使用直接相关的修复。

处理长视频、批量任务和 4K 视频时，内存占用比以前更低。视频处理过程中如果出现解码错误，程序现在会及时报告；逐帧导出失败也会反映到最终结果，不会再出现终端报错但程序返回成功的情况。

动态照片修复功能也更加稳妥。遇到无效的元数据时，程序会尝试寻找正确的视频位置再进行修复；新旧两套 Google 动态照片标准都可以处理。

此外，输出文件与输入文件相同时现在会直接拒绝，避免误覆盖原始照片。这个版本还新增了捷克语和葡萄牙语翻译，目前界面共支持 11 种语言；各平台图标也统一使用同一套 SVG 资源。

## 结语

0.50 让动态照片的基本处理流程可以直接在 Android 手机上完成：从视频和图片制作动态照片，提取其中的内容，或者修复无法正常播放的文件，都不必再借助电脑。

Android 版本仍需要更多真实设备上的测试。如果你在不同品牌的手机或平板上使用时遇到问题，欢迎在 [GitHub Issues](https://github.com/wszqkzqk/live-photo-conv/issues) 反馈。

项目地址：[GitHub · wszqkzqk/live-photo-conv](https://github.com/wszqkzqk/live-photo-conv)。
