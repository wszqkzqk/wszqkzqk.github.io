---
layout:     post
title:      配置并使用AIChat
subtitle:   利用AIChat与LLM API高效交互
date:       2025-03-30
author:     wszqkzqk
header-img: img/llm/ai-bg-lossless.webp
catalog:    true
tags:       AI LLM 开源软件
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

笔者在2025.03.30为Windows的MSYS2环境增加了`mingw-w64-aichat`包，并在同日[被MSYS2项目接受](https://github.com/msys2/MINGW-packages/commit/2272a99a9c1175695017d8591c05d4e217613cc3)，现已支持直接从MSYS2的官方软件源安装。在确保Windows系统安装MSYS2后，打开MSYS2终端（以UCRT64环境为例），执行以下命令：

```bash
pacman -S mingw-w64-ucrt-x86_64-aichat
```

## API配置

我们可以在Google的[AI Studio](https://aistudio.google.com/app/apikey)中免费申请API密钥。请注意，API密钥是非常重要的凭证，请不要泄露。

首次运行AIChat时，系统会提示我们配置，包括选择模型服务商、输入API密钥等。我们可以选择Google Gemini作为模型服务商，并输入申请到的API密钥，然后则需要选择我们想要使用的模型。配置完成后，AIChat会自动保存设置。默认的配置过程十分简单，**一路完成之后就可以直接运行AIChat**，无需再次配置。

如果我们还想要添加多个模型服务商，可以在配置文件中手动添加。配置文件位于用户数据目录下的`aichat/config.yaml`（在Linux上默认为`~/.config/aichat/config.yaml`，在Windows上默认为`%APPDATA%\aichat\config.yaml`）。

此外，AIChat默认的上下文压缩阈值较小，为`4000`，现在比较强大的大模型普遍支持128 K及以上的上下文，我们将阈值设定为`100000`一般是合理的。笔者在一般聊天中更喜欢使用DeepSeek v3 0324模型（近期Google Gemini 2.5 Pro有时候容易无响应），以下是笔者的示例配置文件：

```yaml
compress_threshold: 100000

model: chutes.ai:deepseek-ai/DeepSeek-V3-0324
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
      max_output_tokens: 131072
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
- type: openai-compatible
  name: chutes.ai
  api_base: https://llm.chutes.ai/v1
  api_key: xxxxxx
  models:
    - name: deepseek-ai/DeepSeek-V3-0324
      max_input_tokens: 131072
      max_output_tokens: 131072
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
   - 直接粘贴多行文本（需终端支持，笔者在Linux下用Konsole测试发现直接支持，Windows下用Windows Terminal则发现不支持）。
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

此外，我们在RAG中对于模型的需求往往与普通会话不同，RAG中我们往往需要要求模型的幻觉率尽可能地低，可以参考附录的[榜单](#模型幻觉率榜单)来选择合适的模型。

## 内置HTTP服务器

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

如果想要在AIChat提供的HTTP服务中直接与LLM交互，可以打开运行`aichat --serve`所输出的`LLM Playground`的链接（例如`http://127.0.0.1:8000/playground`），在这里我们可以直接与LLM进行交互。

|[![#~/img/llm/aichat-http-serve.webp](/img/llm/aichat-http-serve.webp)](/img/llm/aichat-http-serve.webp)|
|:----:|
|在浏览器中打开AIChat简洁的HTTP服务界面|

AIChat的网页版默认会运行在一个不保存的会话中，点击左上角的`+`图标可以创建一个新的会话。不过笔者没有找到在网页中保存会话的功能，网页版中的所有会话似乎会在停止服务后丢失。

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

## 附录

### 模型幻觉率榜单

以下内容摘自[Hugging Face](https://huggingface.co/spaces/vectara/leaderboard)的[榜单](https://vectara-leaderboard.hf.space/?__theme=system)，使用[Hallucination](https://github.com/vectara/hallucination-leaderboard)评估，列出了当前主流模型的幻觉率、事实一致性率、回答率等指标。我们可以根据这些指标来选择合适的模型。[^1]

| T | Model                                             | Hallucination Rate (%) | Factual Consistency Rate (%) | Answer Rate (%) | Average Summary Length | Type            |
|----|---------------------------------------------------|-------------------------|------------------------------|-----------------|-----------------------|-----------------|
| ?  | google/gemini-2.0-flash-001                       | 0.7                     | 99.3                         | 100.0           | 65.2                  |                 |
| ?  | google/gemini-2.0-pro-exp-02-05                   | 0.8                     | 99.2                         | 99.7             | 61.5                  |                 |
| ?  | openai/o3-mini-high-reasoning                     | 0.8                     | 99.2                         | 100.0            | 79.5                  |                 |
| ?  | google/gemini-2.5-pro-exp-03-25                   | 1.1                     | 98.9                         | 95.1             | 72.9                  |                 |
| ?  | google/gemini-2.0-flash-lite-preview-02-05       | 1.2                     | 98.8                         | 99.5             | 60.9                  |                 |
| ?  | openai/gpt-4.5-preview                             | 1.2                     | 98.8                         | 100.0            | 77.0                  |                 |
| ?  | gemini-2.0-flash-exp                               | 1.3                     | 98.7                         | 99.9             | 60.0                  |                 |
| ?  | THUDM/glm-4-9b-chat                                | 1.3                     | 98.7                         | 100.0            | 58.1                  |                 |
| ?  | openai/o1-mini                                     | 1.4                     | 98.6                         | 100.0            | 78.3                  |                 |
| ?  | openai/GPT-4o                                      | 1.5                     | 98.5                         | 100.0            | 77.8                  |                 |
| ?  | amazon/nova-micro-v1                              | 1.6                     | 98.4                         | 100.0            | 90.0                  |                 |
| 🟢 | openai/GPT-4-Turbo                                 | 1.7                     | 98.3                         | 100.0            | 86.2                  | pretrained       |
| ?  | openai/GPT-4o-mini                                 | 1.7                     | 98.3                         | 100.0            | 76.3                  |                 |
| ?  | google/gemini-2.0-flash-thinking-exp              | 1.8                     | 98.2                         | 99.3             | 73.2                  |                 |
| ?  | amazon/nova-pro-v1                                 | 1.8                     | 98.2                         | 100.0            | 85.5                  |                 |
| ?  | amazon/nova-lite-v1                                | 1.8                     | 98.2                         | 99.9             | 80.7                  |                 |
| 🟢 | openai/GPT-4                                       | 1.8                     | 98.2                         | 100.0            | 81.1                  | pretrained       |
| ?  | x-ai/grok-2-1212                                   | 1.9                     | 98.1                         | 100.0            | 86.5                  |                 |
| 🟢 | openai/GPT-3.5-Turbo                               | 1.9                     | 98.1                         | 99.6             | 84.1                  | pretrained       |
| ?  | ai21/jamba-1.6-large                               | 2.3                     | 97.7                         | 99.9             | 85.6                  |                 |
| ?  | deepseek/deepseek-chat                             | 2.4                     | 97.6                         | 100.0            | 83.2                  |                 |
| ?  | openai/o1                                          | 2.4                     | 97.6                         | 99.9             | 73.0                  |                 |
| ?  | openai/o1-pro                                      | 2.4                     | 97.6                         | 100.0            | 81.0                  |                 |
| ?  | microsoft/Orca-2-13b                               | 2.5                     | 97.5                         | 100.0            | 66.2                  |                 |
| ?  | microsoft/Phi-3.5-MoE-instruct                     | 2.5                     | 97.5                         | 96.3             | 69.7                  |                 |
| 🟦 | Intel/neural-chat-7b-v3-3                          | 2.6                     | 97.4                         | 100.0            | 60.7                  | RL-tuned         |
| ?  | Qwen/Qwen2.5-7B-Instruct                           | 2.8                     | 97.2                         | 100.0            | 71.0                  |                 |
| ?  | google/gemma-3-12b-it                              | 2.8                     | 97.2                         | 100.0            | 69.6                  |                 |
| ?  | x-ai/grok-2-vision-1212                            | 2.9                     | 97.1                         | 100.0            | 79.8                  |                 |
| ?  | ai21labs/AI21-Jamba-1.5-Mini                      | 2.9                     | 97.1                         | 95.6             | 74.5                  |                 |
| ?  | qwen/qwen-max                                      | 2.9                     | 97.1                         | 88.4             | 90.4                  |                 |
| ?  | Qwen/Qwen2.5-32B-Instruct                          | 3.0                     | 97.0                         | 100.0            | 67.9                  |                 |
| ?  | snowflake/snowflake-arctic-instruct                | 3.0                     | 97.0                         | 100.0            | 68.7                  |                 |
| ?  | google/gemma-3-27b-it                              | 3.0                     | 97.0                         | 100.0            | 62.5                  |                 |
| ?  | microsoft/Phi-3-mini-128k-instruct                 | 3.1                     | 96.9                         | 100.0            | 60.1                  |                 |
| ?  | mistralai/Mistral-Small-24B-Instruct-2501         | 3.1                     | 96.9                         | 100.0            | 74.9                  |                 |
| ?  | openai/o1-preview                                  | 3.3                     | 96.7                         | 100.0            | 119.3                 |                 |
| ?  | google/gemini-1.5-flash-002                       | 3.4                     | 96.6                         | 99.9             | 59.4                  |                 |
| ?  | microsoft/Phi-4-mini-instruct                      | 3.4                     | 96.6                         | 100.0            | 69.7                  |                 |
| ?  | openai/chatgpt-4o-latest                           | 3.5                     | 96.5                         | 100.0            | 63.5                  |                 |
| ?  | 01-ai/Yi-1.5-34B-Chat                             | 3.7                     | 96.3                         | 100.0            | 83.7                  |                 |
| ?  | google/gemma-3-4b-it                               | 3.7                     | 96.3                         | 100.0            | 63.7                  |                 |
| ?  | meta-llama/Meta-Llama-3.1-405B-Instruct            | 3.9                     | 96.1                         | 99.6             | 85.7                  |                 |
| ?  | deepseek/deepseek-v3                               | 3.9                     | 96.1                         | 100.0            | 88.2                  |                 |
| ?  | meta-llama/Llama-3.3-70B-Instruct                  | 4.0                     | 96.0                         | 100.0            | 85.3                  |                 |
| ?  | microsoft/Phi-3-mini-4k-instruct                   | 4.0                     | 96.0                         | 100.0            | 86.8                  |                 |
| ?  | internlm/internlm3-8b-instruct                     | 4.0                     | 96.0                         | 100.0            | 97.5                  |                 |
| ?  | mistralai/Mistral-Large2                           | 4.1                     | 95.9                         | 100.0            | 77.4                  |                 |
| ?  | meta-llama/Llama-3-70B-chat-hf                     | 4.1                     | 95.9                         | 99.2             | 68.5                  |                 |
| ?  | microsoft/Phi-3.5-mini-instruct                    | 4.1                     | 95.9                         | 100.0            | 75.0                  |                 |
| ?  | Qwen/Qwen2.5-14B-Instruct                          | 4.2                     | 95.8                         | 100.0            | 74.8                  |                 |
| ?  | Qwen/Qwen2-VL-7B-Instruct                          | 4.2                     | 95.8                         | 100.0            | 73.9                  |                 |
| ?  | Qwen/Qwen2.5-72B-Instruct                          | 4.3                     | 95.7                         | 100.0            | 80.8                  |                 |
| ?  | meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo    | 4.3                     | 95.7                         | 100.0            | 79.8                  |                 |
| ?  | anthropic/claude-3-7-sonnet-latest                 | 4.4                     | 95.6                         | 100.0            | 97.8                  |                 |
| ?  | anthropic/claude-3-7-sonnet-latest-think           | 4.5                     | 95.5                         | 99.8             | 99.9                  |                 |
| ?  | cohere/command-a-03-2025                           | 4.5                     | 95.5                         | 100.0            | 77.3                  |                 |
| ?  | meta-llama/llama-4-maverick                        | 4.6                     | 95.4                         | 100.0            | 84.8                  |                 |
| ?  | xai/grok-beta                                      | 4.6                     | 95.4                         | 100.0            | 91.0                  |                 |
| ?  | ai21/jamba-1.6-mini                                | 4.6                     | 95.4                         | 100.0            | 82.3                  |                 |
| ?  | anthropic/Claude-3-5-sonnet                        | 4.6                     | 95.4                         | 100.0            | 95.9                  |                 |
| ?  | Qwen/Qwen2-72B-Instruct                            | 4.7                     | 95.3                         | 100.0            | 100.1                 |                 |
| ?  | mistralai/Mixtral-8x22B-Instruct-v0.1              | 4.7                     | 95.3                         | 99.9             | 92.0                  |                 |
| ?  | microsoft/phi-4                                    | 4.7                     | 95.3                         | 100.0            | 100.3                 |                 |
| ?  | meta-llama/llama-4-scout                           | 4.7                     | 95.3                         | 100.0            | 80.7                  |                 |
| ?  | anthropic/claude-3-5-haiku-20241022                | 4.9                     | 95.1                         | 100.0            | 92.2                  |                 |
| ?  | 01-ai/Yi-1.5-9B-Chat                              | 4.9                     | 95.1                         | 100.0            | 85.7                  |                 |
| ?  | allenai/olmo-2-0325-32b-instruct                  | 4.9                     | 95.1                         | 99.9             | 100.0                 |                 |
| ?  | cohere/command-r-08-2024                           | 4.9                     | 95.1                         | 100.0            | 68.7                  |                 |
| ?  | meta-llama/Meta-Llama-3.1-70B-Instruct             | 5.0                     | 95.0                         | 100.0            | 79.6                  |                 |
| ?  | google/gemma-3-1b-it                               | 5.3                     | 94.7                         | 99.9             | 57.9                  |                 |
| ?  | cohere/command-r-plus-08-2024                      | 5.4                     | 94.6                         | 100.0            | 68.4                  |                 |
| ?  | meta-llama/Meta-Llama-3.1-8B-Instruct              | 5.4                     | 94.6                         | 100.0            | 71.0                  |                 |
| ?  | meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo    | 5.5                     | 94.5                         | 100.0            | 67.3                  |                 |
| ?  | mistralai/mistral-small-3.1-24b-instruct           | 5.6                     | 94.4                         | 100.0            | 73.1                  |                 |
| ?  | mistralai/mistral-large-latest                     | 5.864811133200803      | 94.1351888667992             | 100.0            | 79.55367793240556     |                 |
| 🟢 | meta-llama/Llama-2-70b-chat-hf                     | 5.9                     | 94.1                         | 99.9             | 84.9                  | pretrained       |
| ?  | ibm-granite/granite-3.0-8b-instruct                | 6.5                     | 93.5                         | 100.0            | 74.2                  |                 |
| ?  | google/gemini-1.5-pro-002                          | 6.6                     | 93.4                         | 99.9             | 62.0                  |                 |
| ?  | google/gemini-1.5-flash-001                       | 6.6                     | 93.4                         | 99.9             | 63.3                  |                 |
| ?  | mistralai/pixtral-large-latest                     | 6.6                     | 93.4                         | 100.0            | 76.4                  |                 |
| 🟢 | microsoft/phi-2                                    | 6.7                     | 93.3                         | 91.5             | 80.8                  | pretrained       |
| ?  | Qwen/Qwen2.5-3B-Instruct                           | 7.0                     | 93.0                         | 100.0            | 70.4                  |                 |
| ?  | google/gemma-2-2b-it                               | 7.0                     | 93.0                         | 100.0            | 62.2                  |                 |
| ?  | meta-llama/Llama-3-8B-chat-hf                     | 7.4                     | 92.6                         | 99.8             | 79.7                  |                 |
| ?  | mistralai/ministral-8b-latest                      | 7.5                     | 92.5                         | 100.0            | 62.7                  |                 |
| 🟢 | google/Gemini-Pro                                  | 7.7                     | 92.3                         | 98.4             | 89.5                  | pretrained       |
| ?  | 01-ai/Yi-1.5-6B-Chat                               | 7.9                     | 92.1                         | 100.0            | 98.9                  |                 |
| ?  | meta-llama/Llama-3.2-3B-Instruct-Turbo            | 7.9                     | 92.1                         | 100.0            | 72.2                  |                 |
| ?  | deepseek/deepseek-v3-0324                          | 8.0                     | 92.0                         | 100.0            | 78.9                  |                 |
| ?  | databricks/dbrx-instruct                           | 8.3                     | 91.7                         | 100.0            | 85.9                  |                 |
| ?  | mistralai/ministral-3b-latest                      | 8.3                     | 91.7                         | 100.0            | 73.2                  |                 |
| ?  | Qwen/Qwen2-VL-2B-Instruct                          | 8.3                     | 91.7                         | 100.0            | 81.8                  |                 |
| ?  | cohere/c4ai-aya-expanse-32b                       | 8.5                     | 91.5                         | 99.9             | 81.9                  |                 |
| ?  | anthropic/Claude-3-5-Sonnet                        | 8.6                     | 91.4                         | 100.0            | 103.0                 |                 |
| ?  | mistralai/mistral-small-latest                     | 8.6                     | 91.4                         | 100.0            | 74.2                  |                 |
| ?  | ibm-granite/granite-3.1-8b-instruct                | 8.6                     | 91.4                         | 100.0            | 107.4                 |                 |
| ?  | ibm-granite/granite-3.2-8b-instruct                | 8.7                     | 91.3                         | 100.0            | 120.1                 |                 |
| ?  | ibm-granite/granite-3.0-2b-instruct                | 8.8                     | 91.2                         | 100.0            | 81.6                  |                 |
| ?  | google/gemini-1.5-pro-001                          | 9.1                     | 90.9                         | 99.8             | 61.6                  |                 |
| ?  | mistralai/Mistral-7B-Instruct-v0.3                 | 9.5                     | 90.5                         | 100.0            | 98.4                  |                 |
| 🟢 | anthropic/Claude-3-opus                            | 10.1                    | 89.9                         | 95.5             | 92.1                  | pretrained       |
| ?  | google/gemma-2-9b-it                               | 10.1                    | 89.9                         | 100.0            | 70.2                  |                 |
| 🟢 | meta-llama/Llama-2-13b-chat-hf                     | 10.5                    | 89.5                         | 99.8             | 82.1                  | pretrained       |
| ?  | allenai/OLMo-2-1124-13B-Instruct                   | 10.8                    | 89.2                         | 100.0            | 82.0                  |                 |
| ?  | allenai/OLMo-2-1124-7B-Instruct                   | 11.1                    | 88.9                         | 100.0            | 112.6                 |                 |
| ?  | mistralai/Mistral-Nemo-Instruct-2407               | 11.2                    | 88.8                         | 100.0            | 69.9                  |                 |
| 🟢 | meta-llama/Llama-2-7b-chat-hf                     | 11.3                    | 88.7                         | 99.6             | 119.9                 | pretrained       |
| ?  | microsoft/WizardLM-2-8x22B                        | 11.7                    | 88.3                         | 99.9             | 140.8                 |                 |
| ?  | cohere/c4ai-aya-expanse-8b                        | 12.2                    | 87.8                         | 99.9             | 83.9                  |                 |
| ?  | Qwen/QwQ-32B-Preview                               | 12.9                    | 87.1                         | 100.0            | 140.2                 |                 |
| 🟢 | amazon/Titan-Express                               | 13.5                    | 86.5                         | 99.5             | 98.4                  | pretrained       |
| 🟢 | google/PaLM-2                                      | 14.1                    | 85.9                         | 99.8             | 86.6                  | pretrained       |
| ?  | deepseek/deepseek-r1                               | 14.3                    | 85.7                         | 100.0            | 77.1                  |                 |
| ⭕ | google/gemma-7b-it                                 | 14.8                    | 85.2                         | 100.0            | 113.0                 | instruction-tuned |
| ?  | ibm-granite/granite-3.1-2b-instruct                | 15.7                    | 84.3                         | 100.0            | 107.7                 |                 |
| ?  | Qwen/Qwen2.5-1.5B-Instruct                         | 15.8                    | 84.2                         | 100.0            | 70.7                  |                 |
| 🟢 | anthropic/Claude-3-sonnet                          | 16.3                    | 83.7                         | 100.0            | 108.5                 | pretrained       |
| ?  | ibm-granite/granite-3.2-2b-instruct                | 16.5                    | 83.5                         | 100.0            | 117.3                 |                 |
| ?  | google/gemma-1.1-7b-it                             | 17.0                    | 83.0                         | 100.0            | 64.3                  |                 |
| 🟢 | anthropic/Claude-2                                 | 17.4                    | 82.6                         | 99.3             | 87.5                  | pretrained       |
| ?  | google/flan-t5-large                               | 18.3                    | 81.7                         | 99.3             | 20.9                  |                 |
| ⭕ | mistralai/Mixtral-8x7B-Instruct-v0.1               | 20.1                    | 79.9                         | 99.9             | 90.7                  | instruction-tuned |
| ?  | meta-llama/Llama-3.2-1B-Instruct                   | 20.7                    | 79.3                         | 100.0            | 71.5                  |                 |
| ?  | apple/OpenELM-3B-Instruct                          | 24.8                    | 75.2                         | 99.3             | 47.2                  |                 |
| ?  | Qwen/Qwen2.5-0.5B-Instruct                         | 25.2                    | 74.8                         | 100.0            | 72.6                  |                 |
| ?  | google/gemma-1.1-2b-it                             | 27.8                    | 72.2                         | 100.0            | 66.8                  |                 |
| ⭕ | tiiuae/falcon-7b-instruct                          | 29.9                    | 70.1                         | 90.0             | 75.5                  | instruction-tuned |

[^1]: **S. Hughes, M. Bae**, "Vectara Hallucination Leaderboard", Vectara, Inc., 2023. [Online]. Available: [https://github.com/vectara/hallucination-leaderboard](https://github.com/vectara/hallucination-leaderboard).
