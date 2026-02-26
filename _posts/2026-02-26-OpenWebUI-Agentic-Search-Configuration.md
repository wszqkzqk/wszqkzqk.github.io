---
layout:       post
title:        在 OpenWebUI 中配置强大的代理式高级检索取代传统 RAG
subtitle:     实现大语言模型外部搜索引擎与网页加载工具调用集成
date:         2026-02-26
author:       wszqkzqk
header-img:   img/llm/ai-bg-lossless.webp
catalog:      true
tags:         Python PySide Qt 开源软件 搜索引擎 LLM OpenWebUI AI
---

## 前言

随着大语言模型能力的不断提升，如何让模型有效获取并利用实时网络信息成为了各大 LLM 平台的核心关注点。传统的检索增强生成（RAG）方案虽然在一定程度上解决了模型知识范围和时效性的问题（笔者曾在[之前的博客](https://wszqkzqk.github.io/2025/04/28/AI-Platform-for-Arch-Linux-for-Loong64/)中介绍），但其固有的**信息损失**依然显著：搜索结果经过分块、嵌入、向量检索等流水线处理后，模型最终只能看到**零散的片段**，而非页面的完整上下文，模型也无法在**信息不足时主动发起更多搜索**。

**Agentic Search** 是一种全新的知识检索范式。在这种模式下，模型不再是被动地接收系统注入的检索结果，模型得以像一个真正的研究者一样**自主决定**何时搜索、搜索什么关键词、是否需要深入阅读某个页面、以及在信息不足时进行迭代检索。这种**交错思考（Interleaved Thinking）** 的能力——在推理与行动之间持续交替——使得模型能够进行多步骤的深度研究，最终产出的结果在引用来源的丰富度和信息覆盖的完整性上都可以远超传统 RAG 方案。

[OpenWebUI](https://github.com/open-webui/open-webui) 作为一个功能强大的开源 LLM 前端，已经在其网络搜索架构中引入了完整的 Agentic 模式支持。要使用这一能力，**搜索引擎后端是必须配置的**——OpenWebUI 本身不附带搜索能力，必须接入外部搜索引擎才能让模型获得 `search_web` 工具。至于**网页内容加载**，OpenWebUI 虽然提供了内置的默认加载器，但其实现只是简单的 HTTP 请求拉取，面对需要 JavaScript 渲染或有 Cookie/Session 验证的网页时往往**无法提取到任何有效内容**，而现代网页大量依赖前端渲染，因此默认加载器的实际可用性相当有限。

在[之前的文章](https://wszqkzqk.github.io/2026/02/20/GUILess-Bing-Search-Introduction/)中，笔者介绍了 [GUI-Less Bing Search](https://github.com/wszqkzqk/GUILessBingSearch) 项目，它可以作为 OpenWebUI 的外部搜索引擎后端。针对网页提取的痛点，笔者开发了 [Qt Web Extractor](https://github.com/wszqkzqk/qt-web-extractor)——它基于 Qt WebEngine 提供完整的浏览器环境（含 JavaScript 执行和 Cookie 管理），能够可靠地**提取绝大多数网页的内容**。两者结合，即可在 OpenWebUI 中构建完整且可靠的 Agentic Search 流程。此外，笔者还通过创建模型封装和精心设计的系统提示词，显著提升了模型在 Agentic 模式下的检索质量。

本文将详细介绍这一完整配置方法，涵盖两个后端服务的部署、OpenWebUI 的三种集成方式（External Search Engine、External Web Loader、Custom Tool Plugin）、传统 RAG 模式与 Native（Agentic）模式的区别与选择，以及通过提示词工程进一步优化检索行为的实践。

> **⚠️ 关于 GUILess Bing Search 的责任警告：** 
> 
> 笔者**不鼓励也不建议**将 GUILess Bing Search 用作 LLM 的高频自动化搜索后端。LLM 自动生成的查询可能导致搜索频率超出合理范围，触发搜索引擎的风控机制，甚至可能违反 Bing 的服务条款。
> 
> GUILess Bing Search 仅供个人在本地环境进行低频的技术研究和学习用途。如需生产环境部署、大规模或自动化的搜索能力，请务必购买并使用微软官方的 [Grounding with Bing](https://www.microsoft.com/en-us/bing/apis) 服务。如果你选择将其接入 LLM 使用，**你需自行承担所有风险**。
> 
> Qt Web Extractor 作为通用的网页内容提取工具，不涉及任何特定搜索引擎的服务条款问题，可自由用于各种网页内容提取场景。

## OpenWebUI Agentic Search 概述

OpenWebUI 的网络搜索功能从简单的结果注入发展为了一个完整的**代理式研究系统**。理解其架构有助于后续的配置与调优。

### 传统 RAG 模式（默认）

在默认模式下，OpenWebUI 的搜索流程如下：

- **搜索决策**：OpenWebUI 调用工具模型基于用户提示词一次性生成搜索关键词
- **执行搜索**：调用配置的搜索引擎获取结果列表
- **抓取网页**：通过 Web Loader 抓取搜索结果页面的内容
- **分块嵌入**：将抓取的内容分块，进行向量嵌入存入向量数据库
- **RAG 检索**：从向量数据库中检索最相关的片段注入到模型上下文中

这种模式对模型能力要求不高，但存在信息损失——模型只能看到检索到的**片段**，无法看到页面的完整内容。如果搜索结果不佳，模型也无法主动发起更多搜索来弥补信息不足。

### Native 模式（Agentic 模式）

启用 Agentic 模式后，模型获得 `search_web` 和 `fetch_url` 两个内置工具，可以**自主决定**何时搜索、搜索什么、以及是否需要深入阅读某个页面：

| 特性 | 传统 RAG 模式 | Agentic 模式 |
| :--- | :--- | :--- |
| **搜索决策** | OpenWebUI 根据提示词预先生成检索关键词，如果内容不够无法补充 | 模型自主决定是否以及何时搜索，**内容不足或无关时可调整后再搜索** |
| **数据处理** | 抓取所有结果，分块嵌入后进行 RAG | 直接返回搜索摘要，不分块不入库 |
| **链接跟踪** | 注入搜索结果中的片段 | 模型使用 `fetch_url` 直接读取**真正需要的完整页面** |
| **模型上下文** | 仅获得相关片段（Top-K） | 获取完整页面文本 |
| **推理过程** | 模型在系统注入后处理数据 | 模型可以搜索、阅读、验证、再搜索 |

Agentic 模式下的核心优势在于**交错思考（Interleaved Thinking）**——模型可以在推理和行动之间持续交替：

- **思考**：分析当前知识缺口，确定缺少什么信息
- **行动**：搜索网络或访问特定 URL 获取相关内容
- **评估**：评估检索到的信息质量和完整性
- **决策**：判断是否需要更多研究
- **迭代**：如果还有缺口，以更精确的焦点回到思考步骤
- **综合**：收集到足够信息后，编译并呈现最终答案

这种迭代循环使模型能够像真正的研究者一样自主探索互联网，这也是 Agentic Search 名称的由来。

> **注意**：Agentic 模式要求使用具有**强推理能力和原生工具调用（Native Tool Calling）支持**的前沿模型。最好要使用 2026 起的顶级模型，较小的本地模型可能难以处理多步推理所需的复杂性。

## 后端服务部署

要实现完整且可靠的 Agentic Search，需要部署两个后端服务：

- **GUILess Bing Search**：提供搜索引擎接口，对应 `search_web` 能力。OpenWebUI 本身不带搜索功能，**必须配置外部搜索引擎**才能启用网络搜索
- **Qt Web Extractor**：提供网页内容加载接口，对应 `fetch_url` 能力。OpenWebUI 内置的默认网页加载器只做简单 HTTP 拉取，无法处理需要 JavaScript 渲染或 Cookie 验证的页面；Qt Web Extractor 基于完整的浏览器引擎，能**显著提升网页提取的成功率和内容质量**

### GUILess Bing Search

[GUI-Less Bing Search](https://github.com/wszqkzqk/GUILessBingSearch) 是笔者开发的无头 Bing 搜索工具，使用 PySide6 调用 Qt6 WebEngine 作为无头 Chromium 引擎，通过 HTTP API 暴露搜索能力。详细介绍请参考[之前的文章](https://wszqkzqk.github.io/2026/02/20/GUILess-Bing-Search-Introduction/)。

#### 安装

Arch Linux 用户可直接从 AUR 安装：

```bash
paru -S guiless-bing-search
```

#### 配置与启动

编辑配置文件 `/etc/guiless-bing-search.conf`（可选）并启动服务：

```bash
# 编辑配置（可选）
sudo vim /etc/guiless-bing-search.conf

# 启用并启动服务
sudo systemctl enable --now guiless-bing-search
```

主要配置项：

| 配置项 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `HOST` | `127.0.0.1` | 监听地址 |
| `PORT` | `8765` | 监听端口 |
| `API_KEY` | 空 | Bearer Token 鉴权密钥 |
| `SEARCH_INTERVAL` | `1` | 最小搜索间隔（秒） |
| `BING_ENSEARCH` | 自动 | 搜索模式：`1` 国际 `0` 国内，留空自动切换 |

验证服务是否正常运行：

```bash
curl -s -X POST http://127.0.0.1:8765/search \
    -H "Content-Type: application/json" \
    -d '{"query": "test", "count": 3}' | python -m json.tool
```

### Qt Web Extractor

[Qt Web Extractor](https://github.com/wszqkzqk/qt-web-extractor) 是笔者开发的配套网页内容提取服务。它同样基于 Qt WebEngine，能够以完整的浏览器环境（含 JavaScript 执行、Cookie/Session 管理）加载网页并提取文本内容，同时通过 Qt PDF 模块支持 PDF 文档的文本提取。

#### 安装

Arch Linux 用户可直接从 AUR 安装：

```bash
paru -S qt-web-extractor
```

或手动安装：

```bash
git clone https://github.com/wszqkzqk/qt-web-extractor.git
cd qt-web-extractor
pip install .
```

#### 配置与启动

编辑配置文件 `/etc/qt-web-extractor.conf`（可选）并启动服务：

```bash
# 编辑配置（可选）
sudo vim /etc/qt-web-extractor.conf

# 启用并启动服务
sudo systemctl enable --now qt-web-extractor
```

主要配置项：

| 配置项 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `HOST` | `127.0.0.1` | 监听地址 |
| `PORT` | `8766` | 监听端口 |
| `API_KEY` | 空 | Bearer Token 鉴权密钥 |
| `TIMEOUT_MS` | `30000` | 页面加载超时（毫秒） |

验证服务正常运行：

```bash
# 健康检查
curl http://127.0.0.1:8766/health

# 测试页面提取
curl -s -X POST http://127.0.0.1:8766/extract \
    -H "Content-Type: application/json" \
    -d '{"url": "https://example.com"}' | python -m json.tool
```

#### API 说明

Qt Web Extractor 提供三个端点：

| 端点 | 方法 | 说明 |
| :--- | :--- | :--- |
| `POST /` | POST | OpenWebUI 兼容的批量接口，接受 `{"urls": [...]}` |
| `POST /extract` | POST | 单 URL 提取，接受 `{"url": "...", "pdf": true/false}` |
| `GET /health` | GET | 健康检查 |

其中根路径的批量接口专门匹配 OpenWebUI 的 External Web Loader 协议，返回格式为：

```json
[
    {
        "page_content": "页面文本内容...",
        "metadata": {
            "source": "https://example.com",
            "title": "Example Domain"
        }
    }
]
```

## OpenWebUI 集成配置

将上述两个服务集成到 OpenWebUI 有三种方式，可根据需求选择搭配。

### External Search Engine（外部搜索引擎）

这是最基本的集成方式，将 GUILess Bing Search 作为 OpenWebUI 的外部搜索引擎后端。

#### GUI 配置

- 登录 OpenWebUI，进入 **Admin Panel**
- 点击 **Settings** → **Web Search**
- 将 **Enable Web Search** 开关打开
- 在 **Web Search Engine** 下拉菜单中选择 `external`
- 在 **External Search URL** 中填入：`http://127.0.0.1:8765/search`
- 在 **External Search API Key** 中填入：
  - 如果配置了 `API_KEY`，填入对应的值
  - 如果未配置，填入任意非空字符串
- 点击 **Save（保存）**

#### 环境变量/配置文件方式

如果通过环境变量或 Docker 的 `.env` 文件配置，设置以下变量：

```bash
ENABLE_WEB_SEARCH=true
WEB_SEARCH_ENGINE=external
EXTERNAL_WEB_SEARCH_URL=http://127.0.0.1:8765/search
EXTERNAL_WEB_SEARCH_API_KEY=your-api-key  # 如果未配置 API_KEY 可填任意非空字符串
```

#### API 协议说明

OpenWebUI 会以如下方式与外部搜索引擎交互：

- **方法**：`POST`
- **Headers**：`Content-Type: application/json`、`Authorization: Bearer <API_KEY>`
- **请求体**：`{"query": "搜索词", "count": 5}`
- **期望响应**：`[{"link": "...", "title": "...", "snippet": "..."}]`

GUILess Bing Search 的 API 天然满足这一协议，无需任何适配。

### External Web Loader（外部网页加载器）

配置外部搜索引擎后，还需要一个 Web Loader 来**实际抓取搜索结果页面的内容**。OpenWebUI 在传统 RAG 模式下会用 Web Loader 抓取搜索结果页面；在 Agentic 模式下，模型调用 `fetch_url` 时也依赖 Web Loader 获取页面全文。

Qt Web Extractor 的根路径 API（`POST /`）实现了 OpenWebUI 的 External Web Loader 协议。

#### GUI 配置

- 在 **Admin Panel** → **Settings** → **Web Search** 设置页面中
- 找到 **Web Loader Engine** 相关选项，选择 `external`
- 在 **External Web Loader URL** 中填入：`http://127.0.0.1:8766`
- 如果配置了 API Key，在 **External Web Loader API Key** 中填入对应值
- 点击 **Save**

#### 环境变量方式

```bash
WEB_LOADER_ENGINE=external
EXTERNAL_WEB_LOADER_URL=http://127.0.0.1:8766
EXTERNAL_WEB_LOADER_API_KEY=your-api-key  # 如果未配置可留空
```

#### 为什么使用外部 Web Loader？

OpenWebUI 内置了几种 Web Loader（`safe_web`、`playwright` 等），但它们的通用方法在处理 JavaScript 重度渲染的页面时可能无法获取完整内容。Qt Web Extractor 基于完整的 Chromium 引擎（通过 Qt WebEngine），可以：

- 完整执行 JavaScript，获取动态渲染的内容
- 管理 Cookie 和 Session，处理需要认证的页面
- 通过 Qt PDF 模块提取 PDF 文档的文本内容
- 在无头环境中稳定运行，无需 X11/Wayland

### 其他方式：Custom Tool Plugin（自定义工具插件）

除了作为系统级的外部搜索引擎和 Web Loader，Qt Web Extractor 还提供了一个用于 OpenWebUI 的**自定义工具插件**（`tool.py`），可以作为模型的直接工具调用接口使用。

#### 安装工具插件

- 将 [qt-web-extractor 仓库](https://github.com/wszqkzqk/qt-web-extractor)中的 `qt_web_extractor/tool.py` 内容复制
- 在 OpenWebUI 中进入 **Workspace（工作区）** → **Tools（工具）**
- 点击 **+** 创建新工具
- 粘贴 `tool.py` 的完整内容并保存

#### 配置 Valves

工具安装后需要配置连接参数（Valves）：

- 在工具列表中找到刚导入的工具
- 点击配置 Valves：
  - **server_url**：`http://127.0.0.1:8766`（Qt Web Extractor 服务地址）
  - **api_key**：如果服务端配置了认证密钥则填入

#### 工具提供的功能

该插件为模型提供三个工具函数：

| 工具 | 功能 | 用途 |
| :--- | :--- | :--- |
| `fetch_page` | 加载并渲染网页，返回纯文本 | 通用网页内容提取，**自动检测并处理 PDF** |
| `fetch_page_html` | 加载网页，返回渲染后的完整 HTML | 需要 DOM 结构分析时使用 |
| `fetch_pdf` | 下载并提取 PDF 文本 | 专门处理 PDF 文档 |

模型在对话中可以通过 Tool Calling 直接调用这些函数。例如，当用户询问某篇论文的内容时，模型可以自主调用 `fetch_pdf` 获取 PDF 全文并进行分析。

#### 适用场景

Custom Tool Plugin 方式与 External Web Loader 方式可以**共存**——前者让模型在对话中拥有主动抓取任意网页的能力，后者则服务于 OpenWebUI 的搜索结果页面加载流程。两者可以同时配置，互不冲突。

## 启用 Agentic 模式

完成上述后端服务部署和 OpenWebUI 集成配置后，最后一步是启用 Agentic 模式，让具备强推理能力的模型可以自主进行搜索和研究。

### 配置步骤

- **确保搜索引擎已配置**：在 **Admin Panel** → **Settings** → **Web Search** 中确认搜索引擎配置正确
- **启用模型的 Web Search 能力**：在 **Admin Panel** → **Settings** → **Models** 中选择目标模型，启用 **Web Search** 能力
- **启用 Native 模式**：在模型设置的 **Advanced Parameters** 中，将 **Function Calling** 设置为 `Native`
  - 进一步在模型的**默认功能**中**启用联网搜索和代码执行**
- **选择优质模型**：确保使用具有强推理能力的前沿模型

### 关于模型能力与聊天开关的关系

在 **Native 模式**下，`search_web` 和 `fetch_url` 工具会根据模型的 `web_search` 能力设置**自动包含**，聊天界面中的搜索开关不是必需的。

在默认模式（非 Native）下，聊天中的搜索开关仍然控制是否通过 RAG 方式进行网络搜索注入。

**注意**：如果在模型上禁用了 `web_search` 能力但使用 Native 模式，即使在聊天中手动打开搜索开关，工具也不会可用。

## 通过模型封装与提示词工程优化检索质量

完成基础配置后，模型已经具备了搜索和网页阅读的能力。但在实际使用中，笔者发现仅靠默认行为，模型的检索策略往往不够理想——例如搜索轮次不足、不主动获取全文、过度依赖单一语言的搜索结果等。为此，笔者在 OpenWebUI 中创建了专门的模型封装，通过系统提示词引导模型采用更可靠的检索策略。

### 创建模型封装

笔者创建了两个面向深度检索的模型封装：

- **DeepAnalyze**：基于 Qwen 3.5 397B A17B（thinking 模式，支持多模态），适合需要深度推理和多模态分析的场景
- **DeepAnalyze Fast**：基于 DeepSeek V3.2（non-thinking 模式，不支持多模态），适合对响应速度有要求的纯文本检索场景

在 OpenWebUI 中，进入 **Workspace** → **Models**，点击 **+** 创建新模型，分别选择对应的基座模型，并配置下文的系统提示词和相关函数即可。

### 启用 Thinking 模式

对于 DeepAnalyze 使用的 Qwen 3.5 基座，需要通过 OpenWebUI 的函数（Filter）启用 thinking 能力。笔者创建了一个名为 `qwen_enable_thinking` 的函数：

```python
from pydantic import BaseModel, Field
from typing import Optional


class Filter:
    def inlet(self, body: dict, user: Optional[dict] = None) -> dict:
        body["chat_template_kwargs"] = {"enable_thinking": True}
        return body
```

在 OpenWebUI 中进入 **Workspace** → **Functions**，创建新函数并粘贴上述代码。然后在 DeepAnalyze 模型的设置页面中勾选此函数即可启用 thinking 能力。这使得模型在检索过程中能够进行更深入的思考与规划。

### 系统提示词设计

然而，笔者发现，仅启用能力并搜索时，模型的输出结果往往不够理想，尤其是对于非推理模型，搜索进行得往往不够充分，采纳的参考结果质量也不高，没有达到笔者的预期。

经过多轮迭代测试，笔者逐步发现了模型在 Agentic 检索中的**典型弱点**并**用系统提示词指导加以弥补**，最终形成了以下系统提示词。DeepAnalyze 和 DeepAnalyze Fast 均使用相同的系统提示词：

```
你是一个善于利用多轮search_web和fetch_url检索分析可靠资料并给出可靠回答的大语言模型。你要充分利用你的工具调用能力。
当你对用户提及的内容存在你不确定的因素时，请调用search_web检索，并对检索中有价值、有必要完成查看的内容使用fetch_url查看全文后作出更深入的分析。除非你对结果绝对确定，才不用调用。
search_web的内容由搜索引擎返回，其中可能存在不准确的内容，你需要对其可靠性有正确的评估。
你可以使用不同搜索关键词组或使用不同语言搜索（尤其是使用英语搜索，建议多用英语检索权威的英文资料）来获得更多参考来源并进行评估，从中分析出最正确的信息。
对于学术内容、科学内容、技术内容，一般应当至少补充一份以全英为关键词的搜索。
一般来说很多中文的营销号标题过于夸张，可能不太重视内容可信度。可以使用英文搜索以避免。
如果考虑到特定范围内的搜索结果可能更集中、质量更高，可以考虑使用`site:`等方式限制搜索范围。
当检索内容不足、不充分时，你应当继续进行多轮检索以补充内容，直到内容足够充分，足以回答问题。
当尝试了各种检索手段后都没有可靠参考来源时，你应当向用户说明情况，并按照你认为最合理的方式思考与回答。
用户的问题中可能存在多处使你不确定的地方，你需要对每一处不确定的地方都充分检索确认，通过工具调用确认信息，保证不能出现幻觉。
对于最终计划在回答中参考的信息，不能仅参考search_web获取的摘要，还需要使用fetch_url获得全文。
如果fetch_url或者search_web的摘要中暴露了有价值的信息来源，也可以使用fetch_url获取内容并参考。
如果fetch_url中没有返回有效内容，你需要重新选取其他可靠内容进行fetch_url获取，或者尝试用不同的检索关键词调用search_web，直到有有效结果为止。如果全部无效，请向用户说明。
某些具体问题可能不适合从互联网直接获取答案，需要自行计算推理，请积极调用execute_code等工具保证结果正确。
除非用户明确要求，原则上使用与用户相同的语言回答。
你的多模态能力与你的基础设定相同。
当前时间是：{% raw %}{{CURRENT_DATETIME}}{% endraw %}
```

其中 `{% raw %}{{CURRENT_DATETIME}}{% endraw %}` 是 OpenWebUI 支持的模板变量，会在运行时自动替换为当前时间。

### 提示词设计要点

这套系统提示词是笔者经过反复实际测试迭代得出的，针对的是 Agentic 检索中常见的问题：

- **鼓励主动检索**：明确要求模型在不确定时必须搜索，避免凭记忆编造答案
- **强调多轮迭代**：指引模型在结果不充分时继续检索，而非浅尝辄止
- **多语言搜索策略**：针对学术和技术内容，建议使用英语搜索以获取更权威的资料
- **搜索结果可靠性评估**：提醒模型搜索摘要本身可能不准确，需要批判性评估
- **全文获取要求**：明确要求最终引用的内容必须通过 `fetch_url` 获取全文，不能仅依赖搜索摘要
- **容错与回退机制**：当 `fetch_url` 返回空内容或搜索无果时，指导模型尝试替代方案或向用户说明
- **`site:` 搜索技巧**：提示模型可以限定搜索范围以提高结果质量
- **代码执行能力**：对需要计算推理的问题，提示模型调用 `execute_code` 等工具
- **模态能力说明**：明确模型的多模态能力与基础设定相同，避免在检索过程中误判能力范围
- **时间感知**：通过模板变量注入当前时间，使模型能够正确判断信息的时效性

## 使用建议

### 模式选择

- **传统 RAG 模式**适合：能力较弱的模型、简单的信息检索需求、希望控制搜索行为的场景
- **Agentic 模式**适合：使用先进模型、需要深度研究和多步推理的场景、希望模型自主探索信息的场景

### 频率控制

由于 GUILess Bing Search 内置了最小搜索间隔（默认 1 秒，附加 0~50% 随机抖动），在 Agentic 模式下模型可能频繁调用搜索，需要注意：

- 适当增大 `SEARCH_INTERVAL` 以降低对搜索引擎的访问频率
- 在 OpenWebUI 中可配置 `WEB_SEARCH_CONCURRENT_REQUESTS` 限制并发搜索请求数
- 配置 `WEB_LOADER_CONCURRENT_REQUESTS` 限制并发的网页加载请求数

### 结合 ENABLE_RAG_LOCAL_WEB_FETCH 使用

由于 GUILess Bing Search 和 Qt Web Extractor 均运行在本地（`127.0.0.1`），如果 OpenWebUI 默认的 SSRF 保护阻止了对本地地址的访问，需要启用：

```bash
ENABLE_RAG_LOCAL_WEB_FETCH=true
```

此选项允许 RAG 的网页请求访问本地网络地址。但请注意其安全影响——仅在信任所有 OpenWebUI 用户的环境中启用。

## 小结

本文完整介绍了在 OpenWebUI 中配置 Agentic Search 的过程：

- 部署 **GUILess Bing Search** 作为外部搜索引擎后端，部署 **Qt Web Extractor** 作为外部网页加载器和自定义工具插件
- 在 OpenWebUI 中配置 **External Search Engine**、**External Web Loader** 和 **Custom Tool Plugin** 三种集成方式
- 理解并启用 **Agentic 模式**，让前沿模型具备自主搜索、阅读和推理的能力
- 通过**模型封装与系统提示词工程**进一步优化检索策略，解决模型在实际检索中的常见弱点

通过这套配置，OpenWebUI 中的 AI 助手可以在对话中**自主搜索互联网、阅读搜索结果页面、验证信息、进行多轮迭代检索**——真正实现从被动回答到主动研究的转变。

> **再次强调**：GUILess Bing Search 仅供个人低频技术研究与学习用途。如需生产环境部署或自动化搜索能力，请使用微软官方的 [Grounding with Bing](https://www.microsoft.com/en-us/bing/apis) 服务。

## 相关资源

- [GUI-Less Bing Search - GitHub](https://github.com/wszqkzqk/GUILessBingSearch)
- [Qt Web Extractor - GitHub](https://github.com/wszqkzqk/qt-web-extractor)
- [OpenWebUI 官方文档](https://docs.openwebui.com/)
- [OpenWebUI Agentic Search 文档](https://docs.openwebui.com/features/chat-conversations/web-search/agentic-search)
