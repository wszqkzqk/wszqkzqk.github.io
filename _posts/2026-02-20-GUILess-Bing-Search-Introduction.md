---
layout:       post
title:        GUI-Less Bing Search：在无头环境中搜索 Bing
subtitle:     提供 OpenWebUI 可用的标准 search_web API 的无 GUI 搜索工具
date:         2026-02-20
author:       wszqkzqk
header-img:   img/llm/ai-bg-lossless.webp
catalog:      true
tags:         Python PySide Qt 开源软件 搜索引擎 LLM
---

## 前言

在服务器、容器、嵌入式设备等无图形界面的环境中，用户经常需要查找网上的信息，但没有浏览器可用。虽然可以[通过 SSH 转发 Wayland](https://wszqkzqk.github.io/2025/10/13/GUI-With-Remote-Headless-Wayland-Linux/) 等方式远程使用浏览器，但对于频繁的简单查询场景来说过于笨重。

为了解决这个问题，笔者开发了 [**GUI-Less Bing Search**](https://github.com/wszqkzqk/GUILessBingSearch)——一个在无头环境中通过 HTTP API 搜索 Bing 的个人工具。它使用 PySide6 调用 Qt6 WebEngine 作为无头 Chromium 引擎，让用户可以通过 `curl` 等命令行工具完成搜索，无需显示器和桌面环境。

## 项目简介

GUI-Less Bing Search 的核心思路很简单：启动一个后台服务，内部通过 Qt WebEngine 运行一个无头的 Chromium 浏览器实例，对外暴露一个极简的 HTTP JSON API。用户通过 `curl` 发送搜索请求，工具在内部用浏览器访问 Bing 搜索页面，从 DOM 中提取结果后以 JSON 格式返回。

整个流程对用户来说只需要一条命令：

```bash
curl -s -X POST http://localhost:8765/search \
    -H "Content-Type: application/json" \
    -d '{"query": "Linux kernel", "count": 3}' | python -m json.tool
```

返回格式：

```json
[
    {"link": "https://...", "title": "...", "snippet": "..."},
    ...
]
```

### 主要特性

- **无需 GUI**：基于 Qt WebEngine 的 offscreen 模式运行，无需 X11/Wayland 显示服务器，无需 GPU
- **标准 HTTP API**：提供极简的 JSON 响应，不仅可被 `curl` 或 Shell 脚本调用，**技术上**也可以作为 LLM Agent 的 Tool Calling（函数调用）接口
- **隐私保护**：自动解码 Bing 的 `/ck/a` 跳转链接，直接返回目标 URL，避免用户点击行为被追踪
- **中英文自动适配**：根据查询内容中是否包含 CJK 字符自动切换国际/国内搜索模式
- **请求频率控制**：内置最小搜索间隔和随机抖动（0-50%），避免对服务器造成集中访问压力
- **可选的 Bearer Token 认证**：支持 API Key 鉴权，保护服务端点
- **systemd 集成**：附带 service 文件，支持 `DynamicUser` 安全部署
- **AUR 可用**：Arch Linux 用户可直接从 [AUR](https://aur.archlinux.org/packages/guiless-bing-search) 安装

## 开发背景

### 无头环境下的信息检索需求

笔者日常使用多台远程 Linux 服务器进行开发和维护工作。这些机器通常不安装桌面环境，只通过 SSH 连接操作。在工作过程中，经常需要临时查阅某个命令的用法、某个错误信息的含义、或者某个技术方案的资料。

在有桌面环境的本地机器上，这只是切换到浏览器搜索一下的事；但在纯 CLI 的远程环境中，为了查一个简单的问题，要么切回本机浏览器手动搜索再把结果复制回去，要么用 SSH 转发（X11 或 [Waypipe](https://wszqkzqk.github.io/2025/10/13/GUI-With-Remote-Headless-Wayland-Linux/)）启动远程浏览器——这些方式对于频繁的轻量查询来说都太重了。

笔者希望有一个像 `curl` 一样简单的工具：在终端里一行命令发出搜索请求，几秒后直接拿到结构化的搜索结果。

### 为什么不用现有方案？

市面上当然有现成的方案，但各自存在局限：

- **开源搜索聚合工具（如 SearXNG）**：功能强大，但部署和维护相对复杂，对于纯粹在 CLI 里快速查一下的需求来说过于庞大。
- **直接用 `curl` 请求搜索引擎页面**：笔者最初确实尝试了这个思路——用 Python 的 `urllib` 直接请求 Bing 并解析 HTML。但在实践中发现，对于很多查询词，**Bing 会返回 HTML 结构完全正确但内容与搜索词毫不相关的结果**，这个问题通过调整 HTTP 头部无法解决。经过深入排查，发现根因在于 Python HTTP 库的 TLS 指纹与真实浏览器存在差异，导致服务端在 TLS 握手阶段就将请求识别为非浏览器客户端。具体的技术分析详见[后续的文章](https://wszqkzqk.github.io/2026/02/20/GUILess-Bing-Search-Technical-Journey/)。

### 最终的方案选择

既然问题出在 TLS 层面，最直接的解决思路就是使用一个**真正的浏览器引擎**。笔者选择了 Qt WebEngine、，它内嵌了完整的 Chromium 引擎，配合 Qt 的 `offscreen` 模式可以在完全无 GUI 的环境中运行，同时对外暴露一个极简的 HTTP API 供命令行调用——这正是笔者想要的形态。

此外，这种标准化的 HTTP JSON 接口也天然适合作为本地 LLM 工具（如 OpenWebUI）的搜索后端，为模型提供 `search_web` 工具调用能力（详见[后文](#与本地-llm-工具的集成仅供研究测试)）。

## 技术架构

整个服务由单个 Python 文件（约 550 行）实现，架构非常简洁：

```
[HTTP Client (curl/脚本)]
        │ POST /search {"query": "...", "count": N}
        ▼
[HTTP Server (Python stdlib)]
        │ 将查询放入线程安全队列
        ▼
[Qt Event Loop (主线程)]
        │ 从队列取出查询，触发搜索
        ▼
[QWebEnginePage (offscreen Chromium)]
        │ 导航到 Bing 搜索 URL
        │ 页面加载完成后执行 JavaScript 提取 DOM 结果
        ▼
[JSON 响应返回给客户端]
```

### 几个关键设计决策

#### 线程模型

HTTP Server 运行在独立的守护线程（`threading.Thread(daemon=True)`）中，Qt Event Loop 运行在主线程。搜索请求通过线程安全的 `queue.Queue` 传递，`BingEngine` 在主线程的 Qt 事件循环中以 50ms 间隔轮询队列，取出请求后执行搜索，结果通过 `threading.Event` 同步返回给等待中的 HTTP 处理线程。

之所以这样设计，是因为 **Qt WebEngine 必须在主线程中运行**——这是 Chromium 内核的限制。

#### 搜索结果提取

工具在页面加载完成后，注入一段 JavaScript 来提取搜索结果。这段 JS 会遍历页面中所有 `li.b_algo` 元素，从中提取 `h2 a` 的链接和标题、以及 `.b_caption p` 等元素中的摘要文本，最终以 JSON 字符串的形式返回给 Python 侧。

由于 PySide6 的 `runJavaScript` 回调不能直接传递 JS 对象，所以在 JS 端先用 `JSON.stringify` 序列化，Python 端再用 `json.loads` 反序列化。

#### 跳转链接解码与隐私保护

Bing 搜索结果页中的链接通常不是直接指向目标网站的，而是经过 `/ck/a?u=...` 包装的重定向 URL。用户如果经由这些 URL 访问目标网站，Bing 就能追踪到用户具体点击了哪条结果。

GUI-Less Bing Search 会自动解码这些重定向 URL。`/ck/a` 的 `u` 参数实际上是一个经过 URL-safe Base64 编码的目标地址（前缀 `a1`），工具将其解码后直接返回真实链接。这意味着：

- 用户在终端中看到的就是真正的目标 URL，可以直接复制使用
- 后续访问行为不会回传给 Bing，提供了比普通浏览器更好的隐私保护

#### 中英文搜索自动切换

对于中国大陆用户，实际使用的是 `cn.bing.com`。而 `cn.bing.com` 提供了国内模式（`ensearch=0`）和国际模式（`ensearch=1`）两种搜索体验，前者更适合中文查询，侧重返回国内结果，后者更适合英文查询，侧重返回国际结果。工具默认会自动检测查询字符串中是否包含 CJK 字符，据此决定使用哪种模式，无需用户手动指定。当然也支持通过环境变量强制指定。

## 使用方法

### 快速开始

```bash
# 启动服务
python guiless_bing_search.py
```

服务启动后，在另一个终端中即可通过 `curl` 搜索：

```bash
# 健康检查
curl http://localhost:8765/health

# 搜索
curl -s -X POST http://localhost:8765/search \
    -H "Content-Type: application/json" \
    -d '{"query": "Python tutorial", "count": 5}' | python -m json.tool

# 带认证的搜索（如果配置了 API_KEY）
curl -s -X POST http://localhost:8765/search \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer your-api-key" \
    -d '{"query": "Arch Linux", "count": 3}' | python -m json.tool
```

### Arch Linux 安装

此项目已发布到 [AUR](https://aur.archlinux.org/packages/guiless-bing-search)，Arch Linux 用户可以直接安装：

```bash
paru -S guiless-bing-search
# 或
yay -S guiless-bing-search
```

安装后编辑配置文件（可选），然后启用 systemd 服务即可：

```bash
# 编辑配置（可选）
sudo vim /etc/guiless-bing-search.conf

# 启用并启动服务
sudo systemctl enable --now guiless-bing-search
```

服务默认监听 `127.0.0.1:8765`。

### 配置

工具支持通过环境变量或命令行参数进行配置。在 systemd 部署模式下，配置文件位于 `/etc/guiless-bing-search.conf`：

| 配置项 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `BING_ENSEARCH` | 自动 | 搜索模式：`1` 国际，`0` 国内，留空则根据查询中是否包含 CJK 字符自动切换 |
| `BING_BASE_URL` | `https://www.bing.com` | Bing 搜索的 Base URL |
| `HOST` | `127.0.0.1` | 监听地址 |
| `PORT` | `8765` | 监听端口 |
| `SEARCH_INTERVAL` | `1` | 最小搜索间隔（秒），自动附加 0~50% 的随机抖动 |
| `API_KEY` | 空 | Bearer Token 鉴权密钥，留空则不启用认证 |
| `BING_U_COOKIE` | 空 | 手动注入 Bing `_U` Cookie（[见下方说明](#cookie-相关问题)） |
| `BING_EXTRA_COOKIES` | 空 | 以 JSON 格式注入额外 Cookie，如 `{"MUID":"..."}` |

### Profile 存储

浏览器的持久化数据（Cookie、Local Storage 等）默认存储在用户数据目录下：

| 平台 | 路径 |
| :--- | :--- |
| Linux（用户模式） | `~/.local/share/io.github.wszqkzqk/guiless-bing-search/` |
| Linux（systemd） | `/var/lib/io.github.wszqkzqk/guiless-bing-search/`（通过 `StateDirectory`） |
| macOS | `~/Library/Application Support/io.github.wszqkzqk/guiless-bing-search/` |
| Windows | `%LOCALAPPDATA%\io.github.wszqkzqk\guiless-bing-search\` |

可通过 `--profile-dir` 参数自定义路径。

### Cookie 相关问题

在某些网络环境下（尤其是中国大陆），访问 `bing.com` 可能涉及**复杂的重定向流程**，导致浏览器 Profile 中的 Cookie 状态异常，进而出现搜索失败的情况。如果遇到此类问题，可以：

1. **删除 Profile 目录** 以重置浏览器状态
2. 通过 `BING_U_COOKIE` 或 `BING_EXTRA_COOKIES` **手动注入**已知可用的 Cookie 值

如果网络环境能够正常访问 `bing.com`，则无需设置任何 Cookie 参数。

### systemd 部署

项目附带了 systemd service 文件，使用 `DynamicUser=yes` 以独立的动态用户身份运行，数据存储在 `StateDirectory` 指定的路径下，安全且隔离：

```bash
# 编辑配置
sudo vim /etc/guiless-bing-search.conf

# 启用服务
sudo systemctl enable --now guiless-bing-search

# 查看日志
journalctl -u guiless-bing-search -f
```

## 与本地 LLM 工具的集成（仅供研究测试）

近年来，越来越多的本地部署 LLM 方案（如 [OpenWebUI](https://github.com/open-webui/open-webui)、Dify、LangChain 等）支持为 AI 对话接入外部搜索引擎，以实现检索增强生成（RAG）的联网搜索能力或者原生的 `search_web` 工具调用。

GUI-Less Bing Search 暴露的 HTTP JSON API 是一个非常标准的 RESTful 接口，返回结构清晰的 `[{"title": "...", "link": "...", "snippet": "..."}]` 数组。这种格式天然契合大模型的 Tool Calling（工具调用）需求，这意味着它在**技术上**可以无缝接入各种本地 LLM 工具作为搜索后端。

> **⚠️ 责任警告：** 
> 
> 笔者**不鼓励也不建议**将本工具用作 LLM 的高频自动化搜索后端。LLM 自动生成的查询可能导致搜索频率超出合理范围，触发搜索引擎的风控机制，甚至可能违反服务条款。
> 
> 本工具仅供个人在本地环境进行低频的技术研究和测试 API 返回格式的合法性与兼容性用途。如需生产环境部署、大规模或自动化的搜索能力，请务必购买并使用微软官方的 [Grounding with Bing](https://www.microsoft.com/en-us/bing/apis) 服务。如果你选择配置此集成，**你需自行承担所有风险**。

如果你了解并接受上述风险，仅出于个人低频测试或学习目的，以下是将其接入 **OpenWebUI** 的具体配置步骤：

1. 确保 GUI-Less Bing Search 服务已在后台运行（例如监听在 `http://127.0.0.1:8765`）
2. 登录 OpenWebUI，进入 **管理员面板 (Admin Panel)** -> **设置 (Settings)** -> **网络搜索 (Web Search)**，开启网络搜索功能
1. **Web Search Engine**：选择 `external`
2. **External Search URL**：填入 `http://127.0.0.1:8765/search`
3. **External Search API Key**：如果你在启动服务时配置了 `API_KEY`，请填入对应的值；如果未配置，填入任意非空字符串即可（OpenWebUI 要求此字段不能为空）

配置完成后，你在 OpenWebUI 中与模型对话时，模型就可以通过这个标准的 API 接口自主发起搜索，获取实时的网页摘要来辅助回答了。

## 许可证与免责声明

本项目以 [GPL-3.0-or-later](https://www.gnu.org/licenses/gpl-3.0.html) 许可证开源。

本工具严格定位为**个人手动交互式使用**的 CLI 工具，不设计、不授权、不用于任何自动化抓取或高频批量访问，应当仅用于研究和学习用途。使用者需自行确保其使用方式符合所有适用的法律法规和第三方服务的服务条款。对于生产环境部署、自动化工作流或大规模使用场景，请购买并使用微软官方的 [Grounding with Bing](https://www.microsoft.com/en-us/bing/apis) 服务。

> "Bing" 是微软公司的注册商标。本项目是独立的非官方工具，与微软公司没有任何关联。

## 小结

GUI-Less Bing Search 是笔者为无头环境设计的轻量级 Bing 搜索工具，可用于研究 CLI 下的检索方法参考。它通过内嵌真实的 Chromium 浏览器引擎解决了传统 HTTP 客户端无法正确获取搜索结果的问题，通过极简的 HTTP API 将搜索能力暴露给命令行用户，并通过自动解码跳转链接提供了额外的隐私保护。

项目仓库：[**GitHub - wszqkzqk/GUILessBingSearch**](https://github.com/wszqkzqk/GUILessBingSearch)
