---
layout:     post
title:      Live Photo Converter：处理动态照片从未如此简单
subtitle:   便捷且强大的动态照片处理工具，GTK4 + LibAdwaita 图形界面、多种语言、全平台一键安装
date:       2026-05-05
author:     wszqkzqk
header-img: img/bg-sunrise.webp
catalog:    true
tags:       开源软件 Vala GTK4 LibAdwaita 媒体文件 Flatpak 动态照片
---

## 动态照片，能做的事比你想象的更多

很多人拍完动态照片就停在手机相册里，没有再进一步——其实动态照片里藏着的那些素材，完全值得充分利用。把嵌入的视频单独导出保存、将视频逐帧拆成照片挑选最佳瞬间、把短暂视频合成一张有慢速快门效果的长曝光图、甚至把一段自己拍的短视频加上一张精修封面图包装成标准的动态照片——这些都是可以做到的事。

笔者开发的 [Live Photo Converter](https://github.com/wszqkzqk/live-photo-conv) 就是专为这些场景打造的工具。它的核心能力覆盖四件事：**合成**——将视频与图片合成为动态照片；**提取**——从动态照片中分离静态图、嵌入视频、逐帧导出或生成长曝光；**修复**——重建损坏或缺失的 XMP 元数据，让无法播放的动态照片恢复正常；以及**元数据迁移**——解决不同品牌手机之间的兼容性问题。

工具目前全方位覆盖 Linux、Windows 和 macOS，既有美观直观的图形界面，也为进阶用户保留了命令行和可编程的共享库。

<div align="center">
  <a href="/img/media/live-photo-conv-logo.png"><img src="/img/media/live-photo-conv-logo.png" alt="Live Photo Converter" style="width: 500px; max-width: 100%;" /></a>
</div>

## 图形界面

Live Photo Converter 基于 GTK4 / LibAdwaita 构建了现代化的图形界面，遵循平台设计规范。界面布局简洁，操作直观，用户无需任何技术背景就能上手。

<div align="center">
  <a href="/img/media/live-photo-conv/ui-overview-cn.webp"><img src="/img/media/live-photo-conv/ui-overview-cn.webp" alt="Live Photo Converter UI" style="width: 500px; max-width: 100%;" /></a>
</div>

图形界面围绕三个核心操作模式组织，以标签页的形式切换。操作方式非常简单——把文件拖进窗口，勾选需要的内容，点击按钮——不需要终端，不需要命令行，没有任何技术门槛。

| [![提取](/img/media/live-photo-conv/extract-ui-cn.webp)](/img/media/live-photo-conv/extract-ui-cn.webp) | [![制作](/img/media/live-photo-conv/make-ui-cn.webp)](/img/media/live-photo-conv/make-ui-cn.webp) | [![修复](/img/media/live-photo-conv/repair-ui-cn.webp)](/img/media/live-photo-conv/repair-ui-cn.webp) |
|:---:|:---:|:---:|
| 提取模式界面 | 制作模式界面 | 修复模式界面 |

* **提取模式**从动态照片里分离内容。勾选"导出**主图片**""导出**视频**""生成**长曝光照片**""**逐帧导出**"中的任意几项，指定输出目录即可。值得一提，这里支持**批量处理**——拖入多张动态照片，工具会逐个处理并统一汇报结果。
  * **逐帧导出**这个功能尤其实用，支持 JPEG、PNG、WebP、AVIF、HEIF、JXL 等多种图片格式，可以提取出动态照片中记录的每一个瞬间。
  * 长曝光合成则通过对所有帧做时间平均，生成一张**类似慢速快门效果的静态照片**——拍夜景或车流时非常有表现力。
  * 导出的主图片是手机拍摄时用正常照片算法生成的原始静态图，**清晰度远高于视频帧**。以笔者的谁被为例，主图 4080×3060，而每一个视频帧都仅 1440×1080：

  | [![主图元数据](/img/media/live-photo-conv/metadata-of-main-img.webp)](/img/media/live-photo-conv/metadata-of-main-img.webp) | [![视频帧元数据](/img/media/live-photo-conv/metadata-of-frame-img.webp)](/img/media/live-photo-conv/metadata-of-frame-img.webp) |
  |:---:|:---:|
  | 主图片：4080×3060 | 视频帧：1440×1080 |

  主图和视频都可以单独导出，方便后续编辑或使用。
* **制作模式**负责把视频和图片合成为动态照片。用户把主图和视频分别拖进两个文件放置区，点一下按钮选择保存路径，就完成了。如果只传视频不选主图，工具会自动提取视频第一帧作为封面。
  * 也就是说，有一张图加一段视频，想拼起来也行；手里只有一段视频，想直接转也行。
  * 与提取模式相结合，可以**轻松编辑动态照片**。用户可以**先提取**出静态照片和视频素材，进行**编辑后再合成**回动态照片，这样既能够保留修改，又能得到能够直接被手机相册识别的动态照片。
* **修复模式**解决动态照片因**社交媒体抹除元数据而无法识别**的问题。这个模式下，程序能自动检测并重建正确的元数据结构，同时兼容新旧两套 Google 标准。用户只需要把损坏的动态照片拖进窗口，点击修复按钮，即可原位修复，恢复照片的动态效果。该功能同样**支持批量处理**，能一次修复多张照片。

美观易用的界面之下，处理引擎同样强大：GStreamer / FFmpeg 双后端自动切换、新旧两套 Google XMP 标准兼容、KMP 算法搜索视频偏移——这些能力在图形界面下全部可用，用户无需了解背后发生了什么。

## 安装

Live Photo Converter 在全平台的安装都做到了极简。所有包由 CI 在打 tag 时自动构建并发布。

**Windows** 用户安装 MSYS2 后，软件已进入 MSYS2 官方仓库：

```bash
pacman -S mingw-w64-ucrt-x86_64-live-photo-conv
```

**Arch Linux** 用户从 AUR 一键安装：

```bash
paru -S live-photo-conv
```

**其他 Linux 发行版**（Ubuntu、Fedora、Debian、openSUSE 等）通过 Flatpak 安装，从 [GitHub Releases](https://github.com/wszqkzqk/live-photo-conv/releases) 下载 `.flatpak` 包：

```bash
flatpak install --user live-photo-conv*.flatpak
```

Flatpak 的 GNOME Platform 运行时自带全部依赖，无需额外配置。安装完成后，桌面启动器里会出现 Live Photo Converter 图标，点击即用。

macOS 和需要自行编译的用户可参照项目 README 构建。对绝大多数用户而言，上面三条路任选一条即可。

## 不止界面——命令行和程序库同样强大

图形界面解决了易用性的问题，但对于有脚本化、与 Agent 集成需求的场景，命令行工具才是王牌。`live-photo-make`、`live-photo-extract`、`live-photo-repair`、`live-photo-conv` 和 `copy-img-meta` 五个命令各司其职，选项丰富，支持管道和脚本串联。自动化的内容工作流和照片管理系统中，这些 CLI 工具的价值无可替代。

同时，项目还将核心逻辑封装为 `liblivephototools` 共享库，通过 GObject Introspection 提供了跨语言 API，能在 Python、Rust、C、Vala 等任何支持 GI 绑定的语言中直接调用。如果开发者想在自己的应用里集成动态照片处理能力，不需要重新实现解析逻辑，链接这个库即可。

## 多语言

本项目的 GUI 内容经过了国际化处理。目前已支持 9 种语言：英语、简体中文、德语、西班牙语、法语、日语、韩语、葡萄牙语（巴西）和俄语。翻译在 [Hosted Weblate](https://hosted.weblate.org/projects/live-photo-conv/) 平台上管理，任何用户都可以直接参与贡献，无需技术背景。

## 解决厂商兼容性

Android 厂商在动态照片的元数据标准上并不统一。有些品牌要求照片里包含自家的私有 EXIF 或 XMP 字段才能正确识别动态照片，直接用本工具生成的动态照片可能在某些设备上无法被相册识别。

Live Photo Converter 为这个问题准备了专门的解法：`copy-img-meta` 工具。先用目标品牌的手机拍一张普通照片，再将这张照片的元数据（排除 XMP 部分）复制到动态照片上：

```bash
copy-img-meta --exclude-xmp /path/to/source.jpg /path/to/dest.jpg
```

然后在制作动态照片时以处理后的图片为主图，就能生成在该品牌手机上可正常识别和播放的动态照片。笔者实测小米 HyperOS 3 其实已经不需要这一步了——只要 XMP 元数据规范，系统相册就能直接识别——但这项能力仍然是对其他品牌机型的有效兜底方案。

## 结语

如果你有 Android 动态照片不知道怎么在电脑上处理，或者想把一段短视频包装成动态照片传到手机上，或者只是想给受损的动态照片做一次修复——不妨试试这个工具。下载安装不超过一分钟，然后你会发现，处理动态照片原来可以这么简单。

项目地址：[GitHub · wszqkzqk/live-photo-conv](https://github.com/wszqkzqk/live-photo-conv)，欢迎体验、Star、和参与贡献！
