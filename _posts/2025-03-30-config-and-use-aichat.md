---
layout:     post
title:      配置并使用AIChat
subtitle:   利用AIChat与LLM API高效交互
date:       2025-03-30
author:     wszqkzqk
header-img: img/llm/ai-bg-lossless.webp
catalog:    true
tags:       LLM
---

## 前言

**AIChat** 是一款开源命令行大语言模型工具，主要用于高效集成和调用各类AI模型。它以Rust编写，支持跨平台安装，并通过多种包管理器或预编译二进制快速部署。它统一接入了20+主流AI服务（如OpenAI、Claude、Gemini等），提供多样化交互方式：直接生成Shell命令的CMD模式、支持自动补全的交互式REPL聊天、结合外部文件的RAG增强问答，以及通过函数调用扩展的自动化工具链。特色功能包括角色预设管理、会话持久化、宏命令批处理，并内置轻量HTTP服务，可本地部署API接口和Web交互界面（Playground/Arena）。用户可定制主题和提示模板，适应不同开发场景。项目采用MIT/Apache 2.0双协议，兼顾开发灵活性与生产环境需求，显著提升AI模型在命令行环境下的实用性和效率。

## 安装

Arch Linux与Windows的MSYS2均已经官方收录了AIChat，用户可以直接使用包管理器进行安装。

### Arch Linux

```bash
sudo pacman -S aichat
```

### Windows

```bash
pacman -S mingw-w64-ucrt-x86_64-aichat
```

## API配置

我们可以在Google的[AI Studio](https://aistudio.google.com/app/apikey)中免费申请API密钥。请注意，API密钥是非常重要的凭证，请不要泄露。

首次运行AIChat时，系统会提示我们配置，包括选择模型服务商、输入API密钥等。我们可以选择Google Gemini作为模型服务商，并输入申请到的API密钥。对于复杂任务，笔者推荐使用强大且免费开放的Gemini 2.5 Pro模型。配置完成后，AIChat会自动保存设置。

如果我们想要添加多个模型服务商，可以在配置文件中手动添加。配置文件位于`~/.config/aichat/config.yaml`，我们可以使用文本编辑器打开并编辑。

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

而如果我们需要使用文件，可以使用`.file`命令：

```bash
.file /path/to/file
```

这时AIChat会将文件内容作为上下文信息发送给模型，并返回结果。如果已经在会话中，我们还可以后续对文件的内容进行询问。

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
