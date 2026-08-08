---
layout:       post
title:        Qt Web Extractor：轻量级的跨平台多模态网页内容提取工具
subtitle:     专为LLM和自动化工具打造，基于系统Qt WebEngine，告别臃肿的独立浏览器依赖，支持多模态输出与PDF解析
date:         2026-03-20
author:       wszqkzqk
header-img:   img/llm/ai-bg-lossless.webp
catalog:      true
tags:         Python Qt PySide 开源软件 LLM
---

## 网页内容提取的痛点

目前给 LLM 平台提供网页提取或者搜索功能的 API 一般依赖于 Playwright 或 Puppeteer 等技术。这些技术十分强大，能够完美处理动态网页，但也带来了一个显著的问题：过于笨重。

它们通常要求在使用时下载体积庞大的独立完整浏览器二进制文件，在运行时也需要启动完整的浏览器进程。对于一套仅仅用来抓取文本的后端服务来说，这不仅占用了较多的磁盘存储和执行内存，在不同环境部署时也显得有些麻烦。

更为棘手的问题在于跨架构的支持。笔者同时担任着 Arch Linux for Loong64 的维护者，在适配 LoongArch 架构时深有体会。这其实是双重的挑战：首先，像 Playwright 这样的工具本身在 LoongArch 下从源码构建就困难重重，笔者至今也没有成功构建出其稳定可用的版本；其次，它们在运行时强依赖于上游官方预编译发布的 Chromium 等独立浏览器二进制文件，而官方并没有提供针对 LoongArch 等非主流架构的打包分支，这让常规的方法很困难。

在这样的背景下，笔者开发了 [qt-web-extractor](https://github.com/wszqkzqk/qt-web-extractor) 项目。项目的核心目标是打造一个**简单、易用、轻量且真正跨平台**的通用网页内容提取工具。在 Linux、Windows、macOS 在内的各平台上都能轻松部署运行，不再受限于强绑定的独立浏览器二进制文件；同时，它也顺带完美解决了前文所述的跨指令集架构难题——可以直接使用发行版提供的 Qt WebEngine 库。

## 为什么选择 Qt WebEngine

既然需要一个能解析 JavaScript、执行客户端动态渲染并且高度跨平台的轻量级替代方案，Qt WebEngine 成为了极佳的选择。

Qt WebEngine 本质上是 Chromium 的封装，前端渲染和 JS 执行能力与现代浏览器完全一致。它本身就是一个极其成熟及通用的跨平台基础构件，只需引入对应的 Python 绑定包 PySide6，即可直接作为轻量的提取引擎工作，免去了繁琐的额外配置。

而在 Linux 平台下，它还额外带来了得天独厚的优势：作为非常通用的基础 GUI 依赖，从 x86 到 LoongArch、RISC-V 等各种指令集的分支，几乎所有的主流发行版都已经把它在软件仓库中打包集成好了。如果在 Linux 下使用，它可以直接复用系统的动态库，无需再去第三方服务器下载动辄好几百兆的 Chromium 内核。只要用常规的包管理器备齐环境，部署本项目几乎不会带来任何额外的存储占用开销。

## [Qt Web Extractor](https://github.com/wszqkzqk/qt-web-extractor) 简介

[Qt Web Extractor](https://github.com/wszqkzqk/qt-web-extractor) 是一个基于 Qt WebEngine 和 Qt PDF 实现的通用**多模态**网页内容提取工具。它通过 Qt 的 offscreen 模式实现无头运行，不需要显示器或显卡参与渲染，专门用于解决提取那些依赖 JavaScript、由客户端动态加载渲染的现代网页内容，弥补普通 HTTP 请求无法执行 JS 的短板。它不仅能将渲染后的页面转换为干净的 Markdown 文本，还能把网页中的图片、PDF 页面直接作为图像内容返回，让具备视觉能力的模型真正"看到"网页。

项目仅依赖于 PySide6 与 Qt6 WebEngine 模块，方便部署。

### 核心特性

* 全面的 JavaScript 渲染支持：对于常见的单页应用或客户端渲染构建的页面，普通的 requests 纯 HTTP 请求只能获取基础的 HTML 代码。本项目会等待页面渲染完毕，返回包含实际完整内容的 Markdown 文本或 DOM 代码。
* 智能 **Markdown** 输出：默认输出是干净的 Markdown。转换直接基于 Qt 自带的 `QTextDocument` 完成，没有引入任何第三方依赖；标题、链接、列表、表格等结构都能保留下来，还顺带剔除了 `<script>`、`<style>` 和 data URI 等噪声。对于使用了 Shadow DOM 的现代 Web Components 页面，也会在转换前自动将其拍平成普通 HTML，避免内容丢失。这样的输出对 LLM 非常友好：既节省了 Token，又让模型能利用其中的链接信息进一步追溯来源。
* **多模态**支持：工具可以通过同一个完整的浏览器引擎抓取网页中的图片，并将其转换为 WebP 图像内容直接返回，任何浏览器可渲染的格式（PNG、JPEG、GIF、SVG、AVIF 等）都受支持。具备视觉能力的 Agent 因此可以直接看图——阅读论文中的插图、查看网页截图、辨认图表数据都不在话下。而对于不具备视觉能力的模型也无需担心兼容性问题：每个图片结果都会附带一段包含 URL、格式、尺寸、大小的文本摘要，纯文本 Agent 直接忽略图像内容即可，不会引发任何错误。
* 原生 **PDF 解析**：这个扩展特性针对的是一个非常影响现实体验的痛点。之前笔者发现在 Open WebUI 中，如果 LLM 使用 Open WebUI 自带的**默认提取器**去调取一个 PDF 类型的链接，会把 PDF 的二进制格式文件直接拉下来，然后当成文本直接塞到对话的上下文中。这可以说是一场灾难，模型不仅难以获取其中的有效信息，还会浪费巨量 Token。而在本机提取中，遇到 PDF 文件时，可以直接利用与 Qt WebEngine 搭配的 **Qt PDF** 库将文件中的真正**可读文本层解析、提取**并返回，完美解决了这个十分影响用户体验的痛点。
  * 在此基础之上，现在还支持将 PDF 页面**渲染为图像**返回——对于以图表、公式、扫描件为主的 PDF，视觉模型可以直接读图，效果远好于残缺不全的文本层。配合按 URL 缓存下载结果、限制单次渲染页数与总大小等机制，反复翻阅同一个 PDF 时也不会重复下载。
* **MCP** 服务端：内置了标准的 MCP（Model Context Protocol）端点，AI Agent 可以通过 `fetch_url`、`fetch_image`、`fetch_pdf` 三个工具直接调用，各类 Harness 加一行配置即可接入，无需额外的适配层。
* 多种使用接口：提供命令行工具、Python 模块 API、内置的 HTTP REST API 服务，以及上文提到的 MCP 端点。
* 通用的 HTTP API：服务端常驻后台后，能为各类 AI 平台、监控脚本等提供统一的页面与文本获取服务。同时，它还开箱即用支持被配置为 [Open WebUI](https://github.com/open-webui/open-webui) 的外部网页加载器，源码目录中也包含了作为对话自定义工具引用的脚本。
* 部署极简：**依赖简洁且不需要独立下载浏览器**，提供 **systemd 服务**文件和基于 [AUR](https://aur.archlinux.org/packages/qt-web-extractor) 的部署方式，安装和后台启停都非常方便。

### 使用方式展示

#### 常驻 HTTP 服务

工具最常见的使用方式是作为后端的公共常驻服务。项目内置了 HTTP 服务器：

```bash
qt-web-extractor serve --host 127.0.0.1 --port 8766 --api-key mysecretkey
```

启动以后，它就可以作为一个通用的 REST API 供其他程序调用。例如在 Open WebUI 的管理后台中，将 Web Loader Engine 设置为 external，填写这个地址和配置好的 API Key。此后环境中所有的网页阅读、数据拉取都会交由它进行渲染分析。因为能执行 JS 的缘故，它自然也可以顺利加载更多的网页（比如通过简单 HTTP 访问不能获取的知乎、Hugging Face 等等），并且能在应对含有弹窗或单页路由的页面时获取到渲染后的实际 DOM 文本。

除了 Open WebUI 兼容的 `POST /` 接口之外，服务端还提供了单条 URL 提取的 `POST /extract` 接口和健康检查接口。代理方面默认遵循 `HTTPS_PROXY` 等标准环境变量，也可以用 `--proxy` 参数显式指定；出于安全考虑，服务端默认拒绝 `file://` 等本地文件访问，确有需要的场景可以通过 `--allow-local-files` 显式放行。

#### MCP 服务

服务进程同时还内置了 MCP 端点（`http://127.0.0.1:8766/mcp`），与 REST API 复用同一个运行中的浏览器实例和同一套鉴权配置，不需要启动任何额外的进程。主流的 MCP 客户端都可以用一段简单的配置接入：

```json
{
  "mcpServers": {
    "web-extractor": {
      "url": "http://127.0.0.1:8766/mcp",
      "headers": {
        "Authorization": "Bearer mysecretkey"
      }
    }
  }
}
```

以 Claude Code 为例，一条命令即可添加：

```bash
claude mcp add --transport http web-extractor http://127.0.0.1:8766/mcp \
  --header "Authorization: Bearer mysecretkey"
```

接入后 Agent 可以使用三个工具：`fetch_url` 抓取网页并返回渲染后的 Markdown（若 URL 实际指向图片或 PDF 会自动按对应方式处理）；`fetch_image` 将图片作为视觉模型可直接查看的图像内容返回；`fetch_pdf` 提取 PDF 文本，或以 `image` 模式把指定页渲染成图片。配合抓取结果中保留的 Markdown 图片链接，Agent 在阅读网页时看到感兴趣的插图，可以自己再调用 `fetch_image` 把图取回来查看，整个信息获取链路相比纯文本时代完整了许多。

#### 命令行工具

通过命令行可以直接快速提取目标源并将结果输出到终端：

```bash
# Markdown 文本提取（默认输出，保留链接与结构）
python -m qt_web_extractor https://example.com

# 输出 JSON 格式
python -m qt_web_extractor --json https://example.com

# 提取渲染后的 HTML 代码
python -m qt_web_extractor --html https://example.com

# 解析 PDF 文本（按 .pdf 扩展名自动识别）
python -m qt_web_extractor https://example.com/document.pdf

# 一次提取多个 URL
python -m qt_web_extractor https://example.com https://example.org

# 自定义超时、User-Agent 或临时代理
python -m qt_web_extractor --timeout 60000 --user-agent "MyApp/1.0" https://example.com
python -m qt_web_extractor --proxy http://127.0.0.1:7890 https://example.com
```

#### Python 代码调用

项目本身也是一个标准的 Python 包：

```python
from qt_web_extractor import QtWebExtractor

extractor = QtWebExtractor(timeout_ms=30000)
result = extractor.extract("https://example.com")

print(result.title)  # 页面标题
print(result.text)   # 提取经过渲染的网页 Markdown 文本
print(result.html)   # 提取渲染后的 HTML

# 解析 PDF 文本
result = extractor.extract_pdf("https://example.com/document.pdf")
print(result.text)
```

工具引擎在主线程运行 Qt 的事件循环，通过后台线程处理 HTTP 接口。面对每次请求，会在网页完成加载后再给出一定的缓冲时间保证 JS 执行完毕，确保提取的是最终视图数据。

## 总结

[Qt Web Extractor](https://github.com/wszqkzqk/qt-web-extractor) 通过系统自带的 Qt WebEngine 来进行加载和提取，既保留了执行现代前端框架必备的 Chromium 核心能力，又规避了平台架构支持的局限和额外的存储烦恼。而随着 Markdown 结构化输出、PDF 分页渲染与多模态图片支持的加入，它给 LLM 提供的信息不再局限于平铺的文本——模型既能读到结构清晰的文字，也能看到网页和文档中的图像，信息获取的完整度和准确度都有了实实在在的提升。

如果你也面临特殊指令集的部署难题或者厌倦了总是要下载臃肿的浏览器环境，可以尝试一下这个极简的方案。在 Arch Linux 上可以通过 [AUR](https://aur.archlinux.org/packages/qt-web-extractor) 直接安装包。

项目仓库地址：[GitHub · Qt Web Extractor](https://github.com/wszqkzqk/qt-web-extractor)

项目协议：[GPL-3.0-or-later](https://www.gnu.org/licenses/gpl-3.0.html)
