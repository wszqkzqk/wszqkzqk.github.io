---
layout:     post
title:      PDF/SVG格式转化工具
subtitle:   基于Cairo/Poppler/Rsvg开发强大高效的多线程PDF/SVG转换工具
date:       2025-02-15
author:     wszqkzqk
header-img: img/media/bg-modern-img-comp.webp
catalog:    true
tags:       开源软件 Vala Meson 媒体文件 PDF
---

* 项目 GitHub 地址：[**PDF/SVG Converter**](https://github.com/wszqkzqk/pdf-svg-conv)
* 本文涉及的代码采用 [**LGPL v2.1+**](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html) 协议公开发布。

# 前言

笔者最近发现 Cairo 在 Vala 语言中的集成非常方便，于是用 Vala 写了一个 PDF/SVG 格式转化工具，基于 Cairo/Poppler/Rsvg 开发，并实现了高效率转化。

* 写这个项目的一大原因是现有的 ImageMagick 等工具虽然可以用于转化，但是由于**光栅化**的原因，会将矢量描述的 PDF 或者 SVG 文件转化为位图，导致信息丢失。
  * 而且 ImageMagick 似乎不支持生成 SVG。
* 还有一大原因是现有的 `pdf2svg` 工具实在过于简单，功能实现较少。
* 这些工具也都不支持多线程转化包含多页的 PDF 文件，转化速度较慢。
* 当然最主要的原因还是笔者想尝试一下 Cairo。😉😉😉 而且这个项目本身工作量很小。
* **本项目无论是结构设计还是代码实现都非常非常简单，也适合想要学习 Vala/Cairo 的开发者参考**。

# 内容

该项目主要提供两大功能命令行工具：

* Neo PDF to SVG (`neopdf2svg`)： 将 PDF 文件转化为 SVG 文件。支持多线程处理、加密 PDF 解密、指定页码转化以及格式化输出文件名。
* Neo SVG to PDF (`neosvg2pdf`)： 将一组 SVG 文件合并生成单个 PDF 文件。

项目采用 Vala 编程语言和 Meson 构建系统进行开发，依赖于 GLib、Cairo、Poppler、Pango、Rsvg 等第三方库。其设计思路注重并行化、模块化与跨平台兼容。由于 GLib 自带的日志系统不太适合命令行工具，因此项目中还实现了一个日志输出模块与彩色进度条显示。

# 基本原理

* PDF 转 SVG：  
  * 利用 Poppler 库解析 PDF 文件，获取每一页的内容。
  * 将内容渲染到 Cairo 的 `SvgSurface` 上，生成 SVG 文件。
  * 通过 Cairo 的 `Context` 对象绘制 PDF 页面内容到 SVG 中。
* SVG 转 PDF：  
  * 利用 Rsvg 库解析 SVG 文件，获取每个文件的内容。
  * 将内容绘制到 Cairo 的 `PdfSurface` 上，生成 PDF 文件。
  * 通过 Cairo 的 `Context` 对象绘制 SVG 文件内容到 PDF 中。

# 组成结构

## PDF 转 SVG 模块

* `pdf2svg.vala`  
  该模块解析将 PDF 文件转换为 SVG 文件的命令行参数，并调用 `SvgMakerMT` 类完成转换操作。
  * 设置日志颜色启用信息、线程数、PDF 密码以及页码转换规则。
  * 通过 `OptionContext` 解析命令行参数。
  * 调用 `SvgMakerMT` 类完成 PDF 转 SVG 的操作。
  * 通过 `Reporter` 模块输出日志信息。

* `svgmakermt.vala`  
  作为多线程转换的核心类，负责分配任务到线程池。  
  * 如果启用多线程，则为每个页面**新建**一个 **PDF 实例**（而不是简单传递 `Poppler.Page`），并将转换任务封装为 `Task2Svg` 对象加入线程池中。
    * `Poppler.Document` 的渲染操作并**不支持**多线程。
    * 从同一个打开的 `Poppler.Document` 对象获取 `Poppler.Page` 并传递给多个线程渲染时，可能会导致**线程竞争**并引发 `SIGSEGV` 错误。
    * 为了避免这个问题，每个线程都会**重新打开** PDF 文档，建立独立的 `Poppler.Document` 对象，确保线程安全。
  * 当处于单线程模式或转化内容只有一页时，会直接调用转换代码完成渲染，并更新进度条，减小不必要的开销。
  * 接受 PDF 密码，支持加密的 PDF 文件。
  * 接受 PDF 页码或页码范围指定。
  * 转化多页 PDF 时，支持使用 `printf` 风格的32位有符号整数格式化标识符，生成带有序号的输出文件名。
    * 例如 `output-%03d.svg` 将会生成 `output-001.svg`、`output-002.svg` 等文件。
    * 其他不受支持的格式化标识符将被忽略。
    * 在转化单页 PDF 时，也不会进行文件名格式化。
  * 由 `Reporter.ProgressBar` 负责显示转换进度。

* `task2svg.vala`  
  此类封装了单个页面转换任务，用于在线程池中执行。主要包括：
  * 读取指定页面，获取页面大小。
  * 创建 Cairo 的 `SvgSurface` 及 `Context`。
  * 通过 `page.render_for_printing` 将 PDF 页面渲染到 SVG 文件中。

这种设计既保证了多线程转换的性能，又避免了 `Poppler.Page` 的线程安全问题。

## SVG 转 PDF 模块

* `svg2pdf.vala`  
  此模块负责将多个 SVG 文件合并为一个 PDF 文件。
  * 解析命令行参数，设置日志颜色和帮助信息；
  * 获取所有输入 SVG 文件和输出 PDF 文件路径；
  * 调用 `convert_svgs` 方法完成对 SVG 文件的逐个处理，在一个 `Cairo.PdfSurface` 上依次绘制每个 SVG。

这种实现方式使得用户可以灵活指定多个 SVG 文件，按照顺序合并为单一 PDF 输出。

## 通用工具与辅助模块

* `reporter.vala`  
  该模块封装了日志输出与错误提示功能，支持彩色日志输出以及进度条显示。  
  * 定义了日志的颜色设置，用于根据命令行参数控制输出效果；
  * 提供统一的错误、警告和普通信息输出接口，方便在全项目中调用。
  * 通过 `ProgressBar` 类提供了简单的进度条显示功能。
    * 支持显示成功及失败的任务统计信息。
    * 支持清晰醒目的进度条显示，方便用户了解转换进度。
    * 显示转化进度百分比，更加直观。

* `platformbindings.c`  
  提供了跨平台的接口，用于获取终端宽度、判断文件描述符是否为终端等，为 `Reporter` 模块中的彩色输出与进度条显示提供支持。

## 构建与版本控制

* `meson.build`  
  项目的构建脚本定义了各个模块之间的依赖关系以及编译选项。  
  * 利用 Meson 的 `vcs_tag` 指定版本信息，并生成 `version.vala` 文件；
  * 为不同的可执行文件（`neopdf2svg` 和 `neosvg2pdf`）分别指定源文件与依赖库；
  * 同时配置了可选的 `manpage` 生成逻辑，当系统中存在 `help2man` 时会自动生成对应的手册页文件。
    * 也可以通过向 `meson` 命令传递 `-D manpage=true` 或者 `-D manpage=false` 来手动控制是否生成手册页。

# 特点

1. **多线程转换与线程安全：**  
   * PDF 转 SVG 部分针对 `Poppler` 的线程安全问题，通过为每个线程重新打开 PDF 文档，确保并发执行时不发生竞争问题。

2. **命令行参数与用户友好性：**  
  * 使用 Vala 提供的 `OptionContext` 对命令行参数做详细解析，不仅支持显示帮助与版本信息，同时可以根据参数动态调整日志颜色以及线程数等运行时设置。

3. **跨平台设计：**  
  * 使用的 Cairo/Poppler/Rsvg 等库以及 Vala 均支持多平台，通过跨平台特性，确保了项目在不同操作系统下的正常运行。
  * 通过 `platformbindings` 模块，确保终端相关功能（如获取控制台宽度）在不同平台下均能正常工作。

4. **模块化设计：**  
  * 将日志、转换任务、渲染逻辑、构建配置等分离成独立的模块，增加了代码的可维护性与扩展性。

# 结语

PDF/SVG Converter 实现了高效的 PDF 与 SVG 格式互转功能。利用多线程优化渲染效率，并通过跨平台的设计保证了在不同操作系统下的良好体验。这样的设计既满足了命令行工具的快速响应需求，也为后续功能扩展提供了良好基础。希望这个项目能够为更多社区 Vala 开发者提供参考与启发。

# 构建与运行

* 参见项目 [**README.md**](https://github.com/wszqkzqk/pdf-svg-conv) 或 [**README-zh.md**](https://github.com/wszqkzqk/pdf-svg-conv/blob/main/README-zh.md)
* 已上传到 [Arch Linux AUR](https://aur.archlinux.org/packages/pdf-svg-conv)，同时也适配了 Windows (MSYS2) 环境的 [`PKGBUILD` 构建脚本](https://gist.github.com/wszqkzqk/5ece53f3cda6213c62c5f77a9da26af4)。
