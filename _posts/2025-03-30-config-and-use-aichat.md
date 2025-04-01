---
layout:     post
title:      配置并使用AIChat
subtitle:   利用AIChat与LLM API高效交互
date:       2025-03-30
author:     wszqkzqk
header-img: img/llm/ai-bg-lossless.webp
catalog:    true
tags:       AI LLM
---

## 前言

**AIChat**是一款开源命令行大语言模型工具，主要用于高效集成和调用各类AI模型。它以Rust编写，支持跨平台安装，并通过多种包管理器或预编译二进制快速部署。它统一接入了20+主流AI服务（如OpenAI、Claude、Gemini等），提供多样化交互方式：直接生成Shell命令的CMD模式、支持自动补全的交互式REPL聊天、结合外部文件的RAG增强问答，以及通过函数调用扩展的自动化工具链。特色功能包括角色预设管理、会话持久化、宏命令批处理，并内置轻量HTTP服务，可本地部署API接口和Web交互界面（Playground/Arena）。用户可定制主题和提示模板，适应不同开发场景。项目采用MIT/Apache 2.0双协议，兼顾开发灵活性与生产环境需求，显著提升AI模型在命令行环境下的实用性和效率。

## 安装

Arch Linux与Windows的MSYS2均已经官方收录了AIChat，用户可以直接使用包管理器进行安装。

### Arch Linux

```bash
sudo pacman -S aichat
```

### Windows

安装MSYS2后，打开MSYS2终端，执行以下命令：

```bash
pacman -S mingw-w64-ucrt-x86_64-aichat
```

## API配置

我们可以在Google的[AI Studio](https://aistudio.google.com/app/apikey)中免费申请API密钥。请注意，API密钥是非常重要的凭证，请不要泄露。

首次运行AIChat时，系统会提示我们配置，包括选择模型服务商、输入API密钥等。我们可以选择Google Gemini作为模型服务商，并输入申请到的API密钥。对于复杂任务，笔者推荐使用强大且免费开放的Gemini 2.5 Pro模型。配置完成后，AIChat会自动保存设置。

如果我们想要添加多个模型服务商，可以在配置文件中手动添加。配置文件位于用户数据目录下的`aichat/config.yaml`（在Linux上默认为`~/.config/aichat/config.yaml`，在Windows上默认为`%APPDATA%\aichat\config.yaml`）。

此外，AIChat默认的上下文压缩阈值较小，为`4000`，现在比较强大的大模型普遍支持128 K的上下文，我们将阈值设定为`100000`一般是合理的。以下是一个示例配置文件：

```yaml
compress_threshold: 100000

model: gemini:gemini-2.5-pro-exp-03-25
clients:
- type: gemini
  api_key: xxxxxx
- type: openai-compatible
  name: openrouter
  api_base: https://openrouter.ai/api/v1
  api_key: xxxxxx
  models:
    # Deepseek
    - name: deepseek/deepseek-r1:free
      max_input_tokens: 163840
      max_output_tokens: 163840
    - name: deepseek/deepseek-chat-v3-0324:free
      max_input_tokens: 131072
      max_input_tokens: 131072
    # Google Gemini
    - name: google/gemini-2.5-pro-exp-03-25:free
      max_input_tokens: 1000000
      max_output_tokens: 65536
      supports_vision: true
    # Qwen
    - name: qwen/qwq-32b:free
      max_input_tokens: 40000
      max_output_tokens: 40000
    - name: qwen/qwen2.5-vl-32b-instruct:free
      max_input_tokens: 8192
      max_output_tokens: 8192
      supports_vision: true
```

## 使用

简单运行AIChat：

```bash
aichat
```

进入AIChat后，我们还可以使用很多命令，可以输入`.help`查看：

```
.help                    Show this help guide
.info                    Show system info
.edit config             Modify configuration file
.model                   Switch LLM model
.prompt                  Set a temporary role using a prompt
.role                    Create or switch to a role
.info role               Show role info
.edit role               Modify current role
.save role               Save current role to file
.exit role               Exit active role
.session                 Start or switch to a session
.empty session           Clear session messages
.compress session        Compress session messages
.info session            Show session info
.edit session            Modify current session
.save session            Save current session to file
.exit session            Exit active session
.agent                   Use an agent
.starter                 Use a conversation starter
.edit agent-config       Modify agent configuration file
.info agent              Show agent info
.exit agent              Leave agent
.rag                     Initialize or access RAG
.edit rag-docs           Add or remove documents from an existing RAG
.rebuild rag             Rebuild RAG for document changes
.sources rag             Show citation sources used in last query
.info rag                Show RAG info
.exit rag                Leave RAG
.macro                   Execute a macro
.file                    Include files, directories, URLs or commands
.continue                Continue previous response
.regenerate              Regenerate last response
.copy                    Copy last response
.set                     Modify runtime settings
.delete                  Delete roles, sessions, RAGs, or agents
.exit                    Exit REPL

Type ::: to start multi-line editing, type ::: to finish it.
Press Ctrl+O to open an editor for editing the input buffer.
Press Ctrl+C to cancel the response, Ctrl+D to exit the REPL.
```

## 基础会话使用

例如，如果我们需要保留上下文信息，可以使用`.session`命令创建一个会话：

```bash
.session
```

如果需要指定会话名称，可以使用`.session <name>`命令：

```bash
.session my_session
```

这时我们可以输入问题，AIChat会自动将问题发送给模型并返回结果。我们也可以使用`.exit session`命令退出会话。

### 核心功能：Chat-REPL
AIChat 的核心是 Chat-REPL（交互式聊天环境），提供以下特性：
1. **Tab 自动补全**：
   - 输入 `.` 后按 Tab 可补全 REPL 命令。
   - 输入 `.model` 后按 Tab 可补全聊天模型。
   - 输入 `.set <key>` 后按 Tab 可补全配置值。

2. **多行输入支持**：
   - 按 `Ctrl+O` 用外部编辑器编辑多行文本（推荐）。
   - 直接粘贴多行文本（需终端支持）。
   - 输入 `:::` 开始多行编辑，再输入 `:::` 结束。
   - 使用快捷键 `Ctrl/Shift/Alt + Enter` 直接换行。

3. **历史记录搜索**：
   - 按 `Ctrl+R` 搜索历史记录，用 `↑↓` 键导航。

4. **可配置键绑定**：
   - 支持 Emacs 和 VI 风格的键绑定。

5. **自定义提示符**：
   - 可在提示符中显示当前上下文信息。

## 文件操作

AIChat支持文本、图片、PDF文档等多种文件类型，还支持传入URL和目录等。如果我们需要使用文件操作，可以使用`.file`命令：

```bash
.file /path/to/file
```

`.file`命令还可以指定多个文件或目录，使用空格分隔。例如：

```bash
.file /path/to/file1 /path/to/file2
```

在指定完文件后，如果我们还想要指定提交文件的这轮对话的提示词，可以在命令后面加上`--`，然后在后面输入提示词即可：

```bash
.file /path/to/file -- 请帮我总结一下这个文件的内容
```

提示词中还可以包含对于多个文件的高级操作，例如：

```bash
.file a.txt b.txt -- 找出不同之处
.file img1.png img2.png -- 分析图片差异
```

如果已经在会话中，我们还可以后续对文件的内容进行进一步询问。很多时候网页版或者客户端的LLM可能对文件上传大小有限制，而AIChat直接指定本地文件时，文件会在本地处理而无需上传到远程服务器，因此**不受网页版大模型通常存在的文件上传大小限制**。

### 引用上一个回复的内容到文件：`%%`

`%%`是`.file`命令的一个特殊参数，在`.file`命令中使用`%%`时，系统会自动将上一次AI的回复内容作为输入。例如：

```bash
.file %% -- 将上次回复翻译成英文
```

这相当于将 AI 的上一条回复传递给后续指令处理。

利用`%%`，我们可以实现多步处理的链式流程（如生成代码后迭代优化等）。

### 读取命令输出：``` `command` ```

我们还可以使用反引号 `` `command` `` 来读取命令的输出。例如：

```bash
.file `git diff` -- 生成 Git 提交信息
```

这里会先执行`git diff`，将其差异内容发送给LLM进行处理。以上示例可以用于生成Git提交信息，对很多强迫症很有用。

考虑到Git提交信息还往往需要符合项目的历史风格，笔者更推荐使用：

```bash
.file `git diff` `git log` -- 根据历史Git提交信息的风格，为本次修改生成Git提交信息
```

这里的`git diff`会将当前工作区的差异内容传递给LLM，而`git log`会将项目历史提交信息传递给LLM。这样，LLM就可以根据历史提交信息的风格来生成符合项目风格的提交信息。

## RAG增强问答

RAG（Retrieval-Augmented Generation）是一种增强问答的技术，它结合了检索和生成模型的优势。AIChat支持RAG功能，我们可以使用`.rag`命令来初始化或访问RAG。例如，如果我们想要基于AIChat的Wiki文档进行增强问答，可以使用以下命令：

```bash
.rag aichat-wiki
```

在运行`.rag`命令后，AIChat会要求我们指定Embedding模型并设置相关参数（可以保留默认值）。假设我们之前添加了Google Gemini的API密钥，我们就可以使用Google的Embedding模型来进行RAG增强问答。

设置完模型以后，AIChat还是要求我们设置RAG的内容源，对于AIChat的Wiki文档，我们可以使用`https://github.com/sigoden/aichat/wiki/**`作为内容源，其中`**`表示递归匹配该目录下的所有文件和子目录，将AIChat Wiki的所有页面添加到RAG中。另外，如果需要同时指定多个独立的URL，可以用分号 `;` 分隔它们。

如果使用上述设定，我们即可配置得到一个RAG增强问答的环境：

```log
> .rag aichat-wiki
⚙ Initializing RAG...
> Select embedding model: gemini:text-embedding-004 (max-tokens:2048;max-batch:100;price:0)
> Set chunk size: 1500
> Set chunk overlay: 75
> Add documents: https://github.com/sigoden/aichat/wiki/**
Load https://github.com/sigoden/aichat/wiki/** [1/1]
Start crawling url=https://github.com/sigoden/aichat/wiki/ exclude=_history extract=#wiki-body
Crawled https://github.com/sigoden/aichat/wiki/
Crawled https://github.com/sigoden/aichat/wiki/Environment-Variables
Crawled https://github.com/sigoden/aichat/wiki/Macro-Guide
Crawled https://github.com/sigoden/aichat/wiki/Role-Guide
Crawled https://github.com/sigoden/aichat/wiki/Command-Line-Guide
Crawled https://github.com/sigoden/aichat/wiki/Custom-Theme
Crawled https://github.com/sigoden/aichat/wiki/Custom-REPL-Prompt
Crawled https://github.com/sigoden/aichat/wiki/FAQ
Crawled https://github.com/sigoden/aichat/wiki/Chat-REPL-Guide
Crawled https://github.com/sigoden/aichat/wiki/Configuration-Guide
Crawled https://github.com/sigoden/aichat/wiki/RAG-Guide
```

完成以后，我们即可在此RAG环境中进行增强问答。

在RAG环境中，我们还可以叠加使用`.session`命令来创建会话，以便模型能够记住对话内容。

## 内置 HTTP 服务器

启动本地服务：

```
aichat --serve
```

默认地址为 `http://127.0.0.1:8000`，提供以下端点：
- 聊天补全 API：`/v1/chat/completions`
- 嵌入 API：`/v1/embeddings`
- LLM  playground 和竞技场。

支持自定义监听地址和端口：

```
aichat --serve 127.0.0.1:1234
```

## Shell集成

在运行`aichat`命令时加上`-e`参数可以让AI生成并执行命令（需确认）。例如：

```bash
aichat -e "安装docker"  # 生成适合当前系统的安装命令
```

生成命令后，系统会询问接下来的操作：

```log
> aichat -e '不递归地找到/tmp下所有的png文件并转化为无损的webp'
find /tmp -maxdepth 1 -name "*.png" -exec bash -c 'for f; do cwebp -lossless "$f" -o "${f%.*}.webp"; done' _ {} +
> execute | revise | describe | copy | quit:
```

我们可以选择执行、修正、描述、复制或退出。选择执行后，AIChat会自动执行生成的命令。
