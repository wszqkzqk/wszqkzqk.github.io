---
layout:       post
title:        Qt Web Extractor 新增 MCP 支持：为 AI 编程助手提供高级网页提取
subtitle:     完整渲染复杂页面并输出干净 Markdown，为 Claude Code、OpenCode 等终端 AI 工具提供开箱即用的网页内容提取能力
date:         2026-04-04
author:       wszqkzqk
header-img:   img/llm/ai-bg-lossless.webp
catalog:      true
tags:         Python Qt PySide 开源软件 LLM MCP
---

## 背景

之前笔者写过一篇介绍 [Qt Web Extractor](https://github.com/wszqkzqk/qt-web-extractor) 的文章，讲了这个项目是怎么用系统 Qt WebEngine 来做轻量级网页内容提取的。项目一直提供了 HTTP REST API 和 Open WebUI 的集成方式，给 AI 平台调用本来就不是问题——在 Open WebUI 里配置一下外部网页加载器，或者直接用 `tool.py` 作为自定义工具，都能很方便地让 LLM 获取网页内容，几乎是一键式集成。

不过对于 Claude Code、OpenCode 这类 AI 编程助手，[Qt Web Extractor](https://github.com/wszqkzqk/qt-web-extractor) 此前事实上还不能开箱即用，需要手动配置。这些工具本身支持 MCP 协议来扩展能力，如果网页提取服务也能以 MCP 的方式暴露出来，那在终端对话中需要查阅在线文档、阅读 API 参考的时候，AI 助手就能直接调用，不需要任何额外的脚本或配置。

与简单的 HTTP 抓取服务不同，本工具有能力处理目前占据主流的复杂动态渲染页面，不仅能**提取出其他基础工具获取不到的动态内容**，基于完整渲染页面转换得到的 Markdown 还保留了**超链接、表格结构、代码块**等丰富结构信息。这意味着模型在阅读内容后，可以顺着超链接继续获取相关的参考文档，形成信息获取的良性循环。

所以这次更新，项目在原有的 HTTP 服务基础上内建了 [MCP（Model Context Protocol）](https://modelcontextprotocol.io/) 支持。这算是锦上添花——几乎没有引入任何额外的代码负担和运行开销，只是 `server.py` 里多处理了一个 `/mcp` 端点，但大大方便了终端 AI 工具的使用体验。Claude Code、OpenCode 这类工具在对话中遇到需要读取网页内容的场景时，会调用这个 MCP 工具，整个过程非常顺畅。

## 什么是 MCP

MCP 是 Anthropic 提出的一种开放协议，用来标准化 AI 模型与外部工具之间的交互方式。服务端按照协议暴露一组工具（tools），客户端通过标准的 JSON-RPC 调用来请求执行，服务端返回结构化的结果。

对于 Qt Web Extractor 来说，MCP 的价值不在于让 AI 能调用——这一点原来的 REST API 和 Open WebUI 集成已经做得很好了——而在于让 Claude Code、OpenCode 这类终端 AI 工具能**原生地发现和使用**这个能力。AI 助手启动时会读取可用的 MCP 工具列表，在对话中遇到需要读取网页的场景时，会自动选择调用，整个过程不需要用户手动干预。

另外，笔者在工具描述中特别写了 `Always prioritize this tool when you need to read, fetch, or analyze content from any URL or web link`，这样 AI 模型在多个可用工具中会**优先选择本工具**来处理网页内容，避免使用自带的简单 HTTP 请求工具导致无法获取动态渲染内容或者格式不佳的情况。

## 实现方式

Qt Web Extractor 的 MCP 支持是直接内建在已有的 HTTP 服务里的，不需要额外启动任何进程。服务启动后，除了原有的 REST API 端点，还会在 `/mcp` 路径上响应 MCP 协议的 JSON-RPC 请求。

### 协议处理

MCP 基于 JSON-RPC 2.0，服务端需要处理几个标准方法：

* `initialize`：客户端初始化握手，返回协议版本和服务端信息
* `ping`：心跳检测
* `tools/list`：返回可用的工具列表
* `tools/call`：执行具体的工具调用

这些都在 `server.py` 的 `_Handler` 类中实现。以 `tools/list` 为例，它会返回一个 `extract_url` 工具的定义：

```python
{
    "name": "extract_url",
    "description": (
        "Advanced web content extractor. Fully evaluates JavaScript "
        "to render modern web pages and converts the result into clean "
        "Markdown. Always prioritize this tool when you need to read, "
        "fetch, or analyze content from any URL or web link."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to extract content from.",
            }
        },
        "required": ["url"],
        "additionalProperties": False,
    },
    "_meta": {
        "anthropic/maxResultSizeChars": 500000,
    },
}
```

工具描述里明确告诉 AI 模型这是一个高级网页提取器，能完整执行 JavaScript 并返回干净的 Markdown 格式内容。`_meta` 中的 `anthropic/maxResultSizeChars` 是 Anthropic 的扩展字段，用来告知客户端单次返回的最大字符数。

### 提取流程

当 AI 助手调用 `extract_url` 工具时，服务端会走和 REST API 相同的提取管线：

1. 解析请求参数，获取目标 URL
2. 自动检测是否为 PDF 链接（先检查 `.pdf` 后缀作为快速路径，否则发送 HEAD 请求检查 Content-Type）
3. 将提取请求放入队列，由 Qt 主线程的 WebEngine 执行渲染
4. 等待页面加载完成，提取 Markdown 文本
5. 返回结构化结果，包含 URL、标题、Markdown 内容和可能的错误信息

返回格式遵循 MCP 的工具调用规范：

```json
{
    "content": [{"type": "text", "text": "页面 Markdown 内容..."}],
    "structuredContent": {
        "url": "https://example.com",
        "title": "Example Domain",
        "markdown": "页面 Markdown 内容...",
        "error": ""
    },
    "isError": false
}
```

`content` 字段是 AI 模型直接阅读的文本，`structuredContent` 则保留了完整的结构化数据，方便客户端做进一步处理。

### 架构设计

Qt WebEngine 的页面加载必须在 Qt 主线程的事件循环中运行，而 HTTP 服务是在后台线程处理的。两者之间的通信通过一个线程安全的队列来实现：

```python
class _ExtractRequest:
    __slots__ = ("url", "pdf", "result", "done")

    def __init__(self, url: str, pdf: bool = False):
        self.url = url
        self.pdf = pdf
        self.result: _ExtractionResult | None = None
        self.done = threading.Event()
```

HTTP 处理线程创建一个 `_ExtractRequest` 放入队列，Qt 主线程从队列中取出请求、执行提取、设置结果并触发 `done` 事件。HTTP 线程等待 `done` 信号后读取结果返回给客户端。这个设计和原有的 REST API 共享同一套机制，MCP 只是多了一个协议解析层。

## 使用方式

### 启动服务

首先启动 Qt Web Extractor 的 HTTP 服务：

```bash
qt-web-extractor serve --host 127.0.0.1 --port 8766
```

如果需要 API Key 认证：

```bash
qt-web-extractor serve --host 127.0.0.1 --port 8766 --api-key mysecretkey
```

### Claude Code

Claude Code 提供了命令行方式来添加 MCP 服务端：

```bash
# 无认证
claude mcp add --transport http qt-web-extractor http://127.0.0.1:8766/mcp

# 如果服务端设置了 --api-key
claude mcp add --transport http qt-web-extractor http://127.0.0.1:8766/mcp \
  --header "Authorization: Bearer mysecretkey"
```

也可以通过配置文件来管理。项目根目录的 `.mcp.json` 作用于当前项目，`~/.claude.json` 中的 `mcpServers` 则是全局配置：

```json
{
  "mcpServers": {
    "qt-web-extractor": {
      "type": "http",
      "url": "http://127.0.0.1:8766/mcp",
      "headers": {
        "Authorization": "Bearer mysecretkey"
      }
    }
  }
}
```

### OpenCode

OpenCode 的配置写在 `opencode.json`（项目根目录）或 `~/.config/opencode/opencode.json`（全局）中：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "qt_web_extractor": {
      "type": "remote",
      "url": "http://127.0.0.1:8766/mcp",
      "enabled": true,
      "headers": {
        "Authorization": "Bearer mysecretkey"
      }
    }
  }
}
```

### 关于认证

MCP 端点和 REST API 共用同一个认证机制。手动启动服务时通过 `--api-key` 设置密钥，而使用 systemd 服务时则是在 `/etc/qt-web-extractor.conf` 中取消 `API_KEY=` 的注释并填入密钥。无论哪种方式，客户端在请求头中带上 `Authorization: Bearer <key>` 即可通过验证。如果不设置 API Key，所有端点都无需认证即可访问。

### 实际使用场景

配置好以后，用起来就很自然了。比如在 OpenCode 里问一句：

```
> 帮我看看 https://github.com/wszqkzqk/qt-web-extractor 是怎么设计的
```

模型会自动调用 `extract_url` 工具把页面内容拉下来，然后基于渲染后的完整页面转化得到的干净整洁的 Markdown 来回答。对于查阅在线文档、对比 API 设计、看某个项目的使用说明这些场景，这个流程都颇为顺畅。

## 与原有功能的配合

MCP 支持只是多了一个接口，不影响原有的任何使用方式。项目目前提供了四种使用方式：

* **命令行工具**：快速提取，适合脚本和一次性使用
* **Python API**：作为库集成到自己的项目中
* **HTTP REST API**：为 Open WebUI 等平台提供网页加载服务
* **MCP 协议**：为 Claude Code、OpenCode 等终端 AI 工具提供原生调用

它们共享同一个提取引擎，底层都是 Qt WebEngine 在执行渲染。后台服务可以同时响应 REST API 和 MCP 请求，互不干扰。

## 总结

这次 MCP 支持的加入，对于日常使用 Claude Code、OpenCode 等终端 AI 助手的开发者来说，查阅在线文档、分析网页内容已经变得和读写本地文件一样自然。

项目依然保持了轻量、简洁的特点——没有引入任何额外的依赖，MCP 协议处理只是 `server.py` 中新增的几百行代码，几乎不存在额外开销。服务启动后，REST API 和 MCP 端点同时可用，按需取用。

项目仓库地址：[GitHub · Qt Web Extractor](https://github.com/wszqkzqk/qt-web-extractor)

项目协议：[GPL-3.0-or-later](https://www.gnu.org/licenses/gpl-3.0.html)
