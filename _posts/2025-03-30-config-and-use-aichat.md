---
layout:     post
title:      配置并使用AIChat
subtitle:   利用安装便捷且功能强大的命令行工具与LLM API高效交互
date:       2025-03-30
author:     wszqkzqk
header-img: img/llm/ai-bg-lossless.webp
catalog:    true
tags:       AI LLM 开源软件
---

## 前言

[**AIChat**](https://github.com/sigoden/aichat)是一款开源命令行大语言模型工具，主要用于高效集成和调用各类AI模型。它以Rust编写，支持跨平台安装，并通过多种包管理器或预编译二进制快速部署。它统一接入了20+主流AI服务（如OpenAI、Claude、Gemini等），提供多样化交互方式：直接生成Shell命令的CMD模式、支持自动补全的交互式REPL聊天、结合外部文件的RAG增强问答，以及通过函数调用扩展的自动化工具链。特色功能包括角色预设管理、会话持久化、宏命令批处理，并内置轻量HTTP服务，可本地部署API接口和Web交互界面（Playground/Arena）。用户可定制主题和提示模板，适应不同开发场景。项目采用MIT/Apache 2.0双协议，兼顾开发灵活性与生产环境需求，显著提升AI模型在命令行环境下的实用性和效率。

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

我们可以在各大LLM API提供商处申请API密钥。请注意，API密钥是非常重要的凭证，请不要泄露。

首次运行AIChat时，系统会提示我们配置，包括选择模型服务商、输入API密钥等。我们可以选择Google Gemini作为模型服务商，并输入申请到的API密钥，然后则需要选择我们想要使用的模型。配置完成后，AIChat会自动保存设置。默认的配置过程十分简单，**一路完成之后就可以直接运行AIChat**，无需再次配置。

如果我们还想要添加多个模型服务商，可以在配置文件中手动添加。配置文件位于用户数据目录下的`aichat/config.yaml`（在Linux上默认为`~/.config/aichat/config.yaml`，在Windows上默认为`%APPDATA%\aichat\config.yaml`）。

此外，AIChat默认的上下文压缩阈值较小，为`4000`，现在比较强大的大模型普遍支持128 K及以上的上下文，我们将阈值设定为`100000`一般是合理的。笔者在一般聊天中更喜欢使用DeepSeek v3 0324模型（Google Gemini 2.5 Pro非常强大但是近期OpenRouter提供的Google Gemini 2.5 Pro有时候容易无响应），以下是笔者的示例配置文件：

```yaml
compress_threshold: 100000

model: chutes:deepseek-ai/DeepSeek-V3-0324
clients:
- type: gemini
  api_key: xxxxxx
- type: openai-compatible
  name: openrouter
  api_base: https://openrouter.ai/api/v1
  api_key: xxxxxx
  models:
    # Deepseek
    - name: deepseek/deepseek-chat-v3-0324:free
      max_input_tokens: 131072
      max_output_tokens: 131072
      supports_function_calling: true
    - name: deepseek/deepseek-r1:free
      max_input_tokens: 163840
      max_output_tokens: 163840
    # Google Gemini
    - name: google/gemini-2.5-pro-exp-03-25:free
      max_input_tokens: 1000000
      max_output_tokens: 65536
      supports_vision: true
      supports_function_calling: true
- type: openai-compatible
  name: chutes
  api_base: https://llm.chutes.ai/v1
  api_key: xxxxxx
  models:
    # DeepSeek
    - name: deepseek-ai/DeepSeek-V3-0324
      max_input_tokens: 131072
      max_output_tokens: 131072
      supports_function_calling: true
    - name: deepseek-ai/DeepSeek-R1
      max_input_tokens: 163840
      max_output_tokens: 163840
    # Meta
    - name: chutesai/Llama-4-Maverick-17B-128E-Instruct-FP8
      max_input_tokens: 1000000
      max_output_tokens: 256000
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
.file `git diff HEAD` -- 生成 Git 提交信息
```

这里会先执行`git diff HEAD`，将其差异内容发送给LLM进行处理。以上示例可以用于生成Git提交信息，对很多强迫症很有用。

考虑到Git提交信息还往往需要符合项目的历史风格，笔者更推荐使用：

```bash
.file `git diff HEAD` `git log -n 30` -- 根据历史Git提交信息的风格，为本次修改生成Git提交信息
```

这里的`git diff HEAD`会将当前工作区和暂存的差异内容传递给LLM，而`git log -n 30`会将近30条项目历史提交信息传递给LLM作为范例。这样，LLM就可以根据历史提交信息的风格来生成符合项目风格的提交信息。

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

AIChat的网页版默认会运行在一个不保存的会话中，点击左上角的`+`图标可以创建一个新的会话。不过笔者没有找到在网页中保存会话的功能，网页版中的所有会话似乎会在**停止服务**后丢失。

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

## 应用案例

笔者是Arch Linux for Loong64（Loong Arch Linux）发行版的维护者，常常需要在开发者社区的日常会议上向其他开发者介绍Loong Arch Linux的最新进展。为了提高会议效率，可以很方便地使用AIChat来生成进度信息汇总。我们可以利用之前介绍的``` `command` ```的方式，通过`git`命令，将近2周内的仓库提交信息传递给LLM,并让LLM从**这一个角度**来帮助撰写我们所需要的汇报内容。在AIChat的Chat-REPL CLI界面中输入：

```bash
.file `git -C ~/projects/loongarch-packages/ log --since="2 weeks ago" --stat` -- 假如你是Arch Linux for Loong64社区（由北京大学学生Linux俱乐部维护，仓库地址为https://github.com/lcpu-club/loongarch-packages）的维护者，你需要向其他龙架构的开发者汇报最近两周的Loong Arch Linux发行版的开发信息。请你先从git仓库的提交记录中分析，筛选并详细总结出对其他开发者和我们的用户有参考意义，尤其是对其他发行版和上游开发者（指参与龙架构相关开发的上游开发者）的维护有潜在帮助的内容。请有选择地介绍，但是切勿遗漏重要、有价值的信息；请用括号标注出修复的贡献者，例如(by wszqkzqk)这种形式；请尽量附上相关提交的链接（如果有对应PR，优先放PR链接而不是冗长的commit链接）和向上游贡献内容的链接供参考
```

这里的`git -C ~/projects/loongarch-packages/ log --since="2 weeks ago" --stat`会将最近两周的提交记录直接传递给LLM进行处理。LLM会自动分析提交记录，并生成一份详细的进度信息汇总，例如笔者在2025.04.10时的运行结果：

```markdown
以下是从最近两周的提交记录中筛选出的对LoongArch Linux发行版开发有重要参考价值的内容总结，特别关注对其他发行版和上游开发者有帮助的信息：

---

### 1. **AMDVLK驱动支持**
- **提交**: [a0d186c](https://github.com/lcpu-club/loongarch-packages/commit/a0d186ca279b47434b2a1c902a3247dbe379e73b)  
  - 移植了上游stb库的LoongArch支持补丁（[stb#1610](https://github.com/nothings/stb/pull/1610)）(by wszqkzqk)  
  - 临时添加`-DCMAKE_POLICY_VERSION_MINIMUM=3.5`以解决构建问题（[AMDVLK#402](https://github.com/GPUOpen-Drivers/AMDVLK/issues/402)）。  
  - **意义**: 为LoongArch提供了AMD GPU的开源Vulkan驱动支持，对其他发行版集成AMDVLK有参考价值。

---

### 2. **Rust生态适配**
- **提交**: [4a56a27](https://github.com/lcpu-club/loongarch-packages/commit/4a56a27961b0aa4b85e3f75c4ac8813f8f55cd09)  
  - 修复`aichat`的依赖`hnsw_rs`，替换`mmap-rs`为`memmap2`以解决构建问题 (by wszqkzqk)。  
  - 上游PR: [hnswlib-rs#23](https://github.com/jean-pierreBoth/hnswlib-rs/pull/23)。  
- **提交**: [3d9a05e](https://github.com/lcpu-club/loongarch-packages/commit/3d9a05e1cf89598b581106c6b0329ee32b836aae)  
  - 修复`arti`（Tor客户端）的`aws-lc-sys`构建问题，需添加`cmake`和`clang`依赖 (by wszqkzqk)。  
  - 使用`mold`链接器绕过`bfd`的分段错误问题。  
  - **意义**: 展示了Rust工具链在LoongArch上的常见问题及解决方案，对上游Rust库维护者有参考价值。

---

### 3. **QEMU虚拟化改进**
- **提交**: [4e2b778](https://github.com/lcpu-club/loongarch-packages/commit/4e2b77892556eaa06dead178b570ab17fb09bc73)  
  - 为`qemu-system-loongarch64`添加`edk2-loongarch64`依赖（类似x86/aarch64）(by wszqkzqk)。  
  - **意义**: 完善了LoongArch虚拟化支持，为其他发行版提供标准化依赖配置参考。

---

### 4. **Chromium/Electron重大更新**
- **提交**: [ce1141a](https://github.com/lcpu-club/loongarch-packages/commit/ce1141a710fd571cf05c75913474ceb6b3bdc79f)  
  - 升级至Electron 35/Chromium 134，修复Swiftshader的LLVM16兼容性问题 (by wszqkzqk)。  
  - 包含大量LoongArch支持补丁（如seccomp修复、depot_tools适配等）。  
- **提交**: [2b0c6c4](https://github.com/lcpu-club/loongarch-packages/commit/2b0c6c499d26e220c15ab050389106ea4ac59251)  
  - Chromium 135升级，不再需要Swiftshader的额外补丁 (by wszqkzqk)。  
  - **意义**: 为浏览器生态的LoongArch支持提供持续维护范例，补丁可反馈至上游Chromium。

---

### 5. **Qt6 WebEngine适配**
- **提交**: [f75364e](https://github.com/lcpu-club/loongarch-packages/commit/f75364e1cef6295b0b75df70134b661835eda9de)  
  - 升级至Qt 6.9，移除已合并的`libyuv`补丁（上游已修复）(by wszqkzqk)。  
  - **意义**: 展示了如何与上游协作逐步减少下游补丁，推动代码合并。

---

### 6. **LuaJIT关键修复**
- **提交**: [00fd5f7](https://github.com/lcpu-club/loongarch-packages/commit/00fd5f75bbebdc807594ccdc364756da36073dbf)  
  - 修复LuaJIT的JIT编译问题，确保LazyVim等工具链兼容性 (by Wu Xiaotian)。  
- **提交**: [b7dca15](https://github.com/lcpu-club/loongarch-packages/commit/b7dca1539e9c3f6ab39ab04bf9b6e105863ef804)  
  - 合并龙芯社区的LuaJIT更新，支持NeoVim构建 (by Pluto Yang)。  
  - **意义**: 解决了动态语言运行时的重要兼容性问题，补丁可反馈至LuaJIT上游。

---

### 7. **工具链优化**
- **提交**: [659066f](https://github.com/lcpu-club/loongarch-packages/commit/659066f434f0d81b9c95ba23a7e13bef6b95733c)  
  - 修复`pkgfile`的LoongArch64架构识别问题 (by wszqkzqk)。  
  - **意义**: 改进包管理工具对LoongArch的支持，建议提交至Arch Linux上游。

---

### 8. **上游贡献建议**
- **已合并上游的补丁**:  
  - `libyuv`（Qt6依赖）的LoongArch SIMD支持已合并，可移除本地补丁。  
  - `stb`库的LoongArch补丁（[stb#1610](https://github.com/nothings/stb/pull/1610)）已合并。  
- **待推动的补丁**:  
  - `hnsw_rs`的`memmap2`替换（[hnswlib-rs#23](https://github.com/jean-pierreBoth/hnswlib-rs/pull/23)）需上游审核。  
  - `pkgfile`的架构识别补丁可提交至Arch Linux。

---

### 完整提交列表
- [所有相关提交记录](https://github.com/lcpu-club/loongarch-packages/commits/main)  
- **重点包**: AMDVLK、QEMU、Chromium/Electron、Qt6、LuaJIT、Rust生态工具。

---

以上内容可供其他LoongArch发行版维护者和上游开发者参考，欢迎进一步协作优化生态支持！
```

LLM生成的信息未必直接可用，可能会有**错误、遗漏或者不正确的解读**（这在上面的示例中即存在），但是确实可以帮助我们快速生成一份大致的进度信息。我们可以在此基础上进行修改和补充，最终形成一份完整的进度信息。

另外，需要注意的是，社区的信息不仅仅是代码的提交信息，很多时候我们还需要关注社区的其他动态，例如社区成员的讨论，以及核心成员在上游的提交等。我们不能寄希望使用AIChat的一条命令就能完成所有的工作，AIChat只是一个工具，它可以帮助我们更高效地完成工作，无法做到完全自动化。

## 附录

### 常见高性能模型性能对比

摘自[Google Gemini 2.5 Pro](https://blog.google/technology/google-deepmind/gemini-model-thinking-updates-march-2025/)与[Google Gemini 2.5 Flash](https://developers.googleblog.com/en/start-building-with-gemini-25-flash/)的发布页面。（由于是Google发布的，可能结果中立性存疑）

| 指标名称 | Gemini 2.5 Pro | Grok 3 Beta | OpenAI o4-mini | Gemini 2.5 Flash | OpenAI o3-mini | Claude 3.7 Sonnet | DeepSeek R1 | OpenAI GPT-4.5 | Gemini 2.0 Flash |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Humanity's Last Exam (no tools) | 18.8% | - | 14.3% | 12.1% | 14.0% | 8.9% | 8.6% | 6.4% | 5.1% |
| GPQA diamond (single attempt) | 84.0% | 80.2% | 81.4% | 78.3% | 79.7% | 78.2% | 71.5% | 71.4% | 60.1% |
| GPQA diamond (multiple attempts) | - | 84.6% | - | - | - | 84.8% | - | - | - |
| AIME 2025 (single attempt) | 86.7% | 77.3% | 92.7% | 78.0% | 86.5% | 49.5% | 70.0% | - | 27.5% |
| AIME 2024 (single attempt) | 92.0% | 83.9% | 93.4% | 88.0% | 87.3% | 61.3% | 79.8% | 36.7% | 32.0% |
| AIME 2024 (multiple attempts) | - | 93.3% | - | - | - | 80.0% | - | - | - |
| LiveCodeBench v5 (single attempt) | 70.4% | 70.6% | - | 63.5% | 74.1% | - | 64.3% | - | 34.5% |
| LiveCodeBench v5 (multiple attempts) | - | 79.4% | - | - | - | - | - | - | - |
| Aider Polyglot (whole / diff) | 74.0% / 68.6% | - | 68.9% / 58.2% | 51.1% / 44.2% | 60.4% (diff) | 64.9% (diff) | 56.9% (diff) | 44.9% (diff) | 22.2% (whole) |
| SimpleQA | 52.9% | 43.6% | - | 29.7% | 13.8% | - | 30.1% | 62.5% | 29.9% |
| MMMU (single attempt) | 81.7% | 76.0% | 81.6% | 76.7% | - | 75.0% | - | 74.4% | 71.7% |
| MMMU (multiple attempts) | - | 78.0% | - | - | - | - | - | - | - |
| Vibe-Eval (Reka) | 69.4% | - | - | 62.0% | - | - | - | - | 56.4% |
| MRCR (128k average) | 94.5% | - | - | 84.6% | 61.4% | - | - | 64.0% | 74.2% |
| MRCR (1M pointwise) | 83.1% | - | - | 66.3% | - | - | - | - | 48.2% |
| Global MMLU (Lite) | 89.8% | - | - | 88.4% | - | - | - | - | 83.4% |

### 长上下文深度理解性能

以下内容摘自[Fiction.LiveBench](https://fiction.live/stories/Fiction-liveBench-April-17-2025/oQdzQvKHw8JyXbN87)。（2025年4月17日发布）

| Model | 0 | 400 | 1k | 2k | 4k | 8k | 16k | 32k | 60k | 120k |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| o3 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 88.9 | 100.0 | 83.3 | 100.0 |
| o4-mini | 100.0 | 100.0 | 100.0 | 100.0 | 77.8 | 66.7 | 77.8 | 55.6 | 66.7 | 62.5 |
| o1 | 100.0 | 97.2 | 100.0 | 94.4 | 94.4 | 86.1 | 83.3 | 83.3 | 72.2 | 53.1 |
| o3-mini | 100.0 | 63.9 | 58.3 | 47.2 | 47.2 | 50.0 | 50.0 | 55.6 | 44.4 | 43.8 |
| claude-3-7-sonnet-20250219-thinking | 100.0 | 100.0 | 100.0 | 97.2 | 91.7 | 97.2 | 83.3 | 75.0 | 69.4 | 53.1 |
| deepseek-r1 | 100.0 | 82.2 | 80.6 | 76.7 | 77.8 | 83.3 | 69.4 | 63.9 | 66.7 | 33.3 |
| gemini-2.5-pro-exp-03-25:free | 100.0 | 100.0 | 100.0 | 100.0 | 97.2 | 91.7 | 66.7 | 86.1 | 83.3 | 90.6 |
| gemini-2.5-flash-preview:thinking | 100.0 | 97.2 | 86.1 | 75.0 | 75.0 | 61.1 | 63.9 | 55.6 | 58.3 | 75.0 |
| gemini-2.0-flash-thinking-exp:free | 100.0 | 83.3 | 66.7 | 75.0 | 77.8 | 52.8 | 52.8 | 36.1 | 36.1 | 37.5 |
| qwq-32b:free | 100.0 | 91.7 | 94.4 | 88.9 | 94.4 | 86.1 | 83.3 | 80.6 | 61.1 | - |
| grok-3-mini-beta | 87.5 | 77.8 | 77.8 | 80.6 | 77.8 | 72.2 | 66.7 | 75.0 | 72.2 | 65.6 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| quasar-alpha | 100.0 | 97.2 | 86.1 | 66.7 | 66.7 | 69.4 | 69.4 | 63.9 | 63.9 | 59.4 |
| optimus-alpha | 100.0 | 91.7 | 77.8 | 72.2 | 61.1 | 55.6 | 61.1 | 55.6 | 58.3 | 59.4 |
| gpt-4.1 | 100.0 | 91.7 | 75.0 | 69.4 | 63.9 | 55.6 | 63.9 | 58.3 | 52.8 | 62.5 |
| gpt-4.1-mini | 75.0 | 66.7 | 55.6 | 41.7 | 44.4 | 41.7 | 44.4 | 38.9 | 38.9 | 46.9 |
| gpt-4.1-nano | 62.5 | 50.0 | 41.7 | 36.1 | 33.3 | 38.9 | 25.0 | 33.3 | 36.1 | 18.8 |
| chatgpt-4o-latest | 87.5 | 83.3 | 66.7 | 63.9 | 63.9 | 66.7 | 66.7 | 63.9 | 55.6 | 65.6 |
| gpt-4.5-preview | 100.0 | 94.4 | 83.3 | 83.3 | 83.3 | 72.2 | 63.9 | 63.9 | 66.7 | 63.9 |
| claude-3-7-sonnet-20250219 | 100.0 | 77.8 | 80.6 | 72.2 | 61.1 | 52.8 | 50.0 | 52.8 | 44.4 | 34.4 |
| claude-3-5-sonnet-20241022 | 100.0 | 77.8 | 69.4 | 55.6 | 50.0 | 38.9 | 38.9 | 36.1 | - | - |
| deepseek-chat-v3-0324:free | 87.5 | 61.1 | 69.4 | 52.8 | 52.8 | 52.8 | 50.0 | 55.6 | 55.6 | - |
| deepseek-chat:free | 87.5 | 61.1 | 61.1 | 55.6 | 55.6 | 50.0 | 61.1 | 16.7 | 19.4 | - |
| qwen-max | 75.0 | 69.4 | 69.4 | 63.9 | 72.2 | 63.9 | 66.7 | - | - | - |
| jamba-1-5-large | 75.0 | 50.0 | 47.2 | 58.3 | 50.0 | 52.8 | 52.8 | 36.1 | 44.4 | 46.9 |
| gemma-3-27b-it:free | 87.5 | 44.4 | 50.0 | 41.7 | 33.3 | 38.9 | 33.3 | 25.0 | 30.6 | - |
| gemini-2.5-flash-preview | 62.5 | 63.9 | 69.4 | 61.1 | 47.2 | 44.4 | 47.2 | 44.4 | 58.3 | 53.1 |
| gemini-2.0-pro-exp-02-05:free | 87.5 | 91.7 | 80.6 | 72.2 | 61.1 | 52.8 | 41.7 | 47.2 | 41.7 | 37.5 |
| gemini-2.0-flash-001 | 100.0 | 63.9 | 58.3 | 55.6 | 47.2 | 50.0 | 61.1 | 50.0 | 47.2 | 62.5 |
| llama-4-maverick:free | 100.0 | 56.0 | 50.0 | 52.0 | 48.0 | 48.0 | 46.2 | 44.0 | 32.0 | 36.4 |
| llama-4-scout:free | 62.5 | 52.0 | 50.0 | 36.0 | 32.0 | 40.0 | 36.0 | 16.0 | 24.0 | 27.3 |
| llama-3.3-70b-instruct | 75.0 | 66.7 | 69.4 | 55.6 | 41.7 | 36.1 | 33.3 | 33.3 | 33.3 | - |
| grok-3-beta | 75.0 | 72.2 | 63.9 | 55.6 | 55.6 | 52.8 | 58.3 | 55.6 | 63.9 | 58.3 |

### 模型幻觉率榜单

以下内容摘自[Hugging Face](https://huggingface.co/spaces/vectara/leaderboard)的[榜单](https://vectara-leaderboard.hf.space/?__theme=system)，使用[Hallucination](https://github.com/vectara/hallucination-leaderboard)评估，列出了当前主流模型的幻觉率、事实一致性率、回答率等指标。我们可以根据这些指标来选择合适的模型。[^1]摘录时间为2025.04.08。

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

### 模型智能榜单

以下是对模型的智能方面的评估，选择性摘录自[Artificial Analysis](https://artificialanalysis.ai/leaderboards/models)。摘录时间为2025.04.13。

| 模型名称                          | Context Window | Artificial Analysis Intelligence Index | MMLU-Pro (Reasoning & Knowledge) | GPQA Diamond (Scientific Reasoning) | Humanity's Last Exam (Reasoning & Knowledge) | LiveCodeBench (Coding) | SciCode (Coding) | HumanEval (Coding) | Math-500 (Quantitative Reasoning) | AIME 2024 (Competition Math) | Multilingual Index (Artificial Analysis) | Chatbot Arena |
|-----------------------------------|----------------|----------------------------------------|----------------------------------|-------------------------------------|-----------------------------------------------|------------------------|------------------|--------------------|-----------------------------------|-----------------------------|------------------------------------------|---------------|
| Gemini 2.5 Pro Experimental       | 1m             | 68                                     | 86%                              | 84%                                 | 17%                                           | 70%                    | 39%              | 99%                | 98%                              | 87%                        | -                                        | -             |
| o3-mini (high)                    | 200k           | 66                                     | 80%                              | 77%                                 | 12%                                           | 73%                    | 40%              | -                  | 99%                              | 86%                        | -                                        | -             |
| o3-mini                           | 200k           | 63                                     | 79%                              | 75%                                 | 9%                                            | 72%                    | 40%              | 97%                | 97%                              | 77%                        | -                                        | -             |
| o1                                | 200k           | 62                                     | 84%                              | 75%                                 | 8%                                            | 68%                    | 36%              | 97%                | 97%                              | 72%                        | 88%                                      | -             |
| DeepSeek R1                       | 128k           | 60                                     | 84%                              | 71%                                 | 9%                                            | 62%                    | 36%              | 98%                | 97%                              | 68%                        | -                                        | -             |
| QwQ-32B                           | 131k           | 58                                     | 76%                              | 59%                                 | 8%                                            | 63%                    | 36%              | 98%                | 96%                              | 78%                        | -                                        | -             |
| Claude 3.7 Sonnet Thinking        | 200k           | 57                                     | 84%                              | 77%                                 | 10%                                           | 47%                    | 40%              | 98%                | 95%                              | 49%                        | -                                        | -             |
| o1-mini                           | 128k           | 54                                     | 74%                              | 60%                                 | 5%                                            | 58%                    | 32%              | 97%                | 94%                              | 60%                        | 83%                                      | 1308          |
| DeepSeek V3 (Mar' 25)             | 128k           | 53                                     | 82%                              | 66%                                 | 5%                                            | 41%                    | 36%              | 92%                | 94%                              | 52%                        | -                                        | -             |
| Gemini 2.0 Flash Thinking exp. (Jan '25) | 1m             | 52                                     | 80%                              | 70%                                 | 7%                                            | 32%                    | 33%              | -                  | 94%                              | 50%                        | -                                        | -             |
| DeepSeek R1 Distill Qwen 32B      | 128k           | 52                                     | 74%                              | 62%                                 | 6%                                            | 27%                    | 38%              | 95%                | 94%                              | 69%                        | -                                        | -             |
| Llama 4 Maverick                  | 1m             | 51                                     | 81%                              | 67%                                 | 5%                                            | 40%                    | 33%              | 88%                | 89%                              | 39%                        | -                                        | -             |
| GPT-4o (March 2025)               | 128k           | 50                                     | 80%                              | 66%                                 | 5%                                            | 43%                    | 37%              | 96%                | 89%                              | 33%                        | -                                        | -             |
| Grok 3                            | 1m             | 50                                     | 80%                              | 67%                                 | 5%                                            | 42%                    | 37%              | 91%                | 87%                              | 30%                        | -                                        | -             |
| Gemini 2.0 Pro Experimental       | 2m             | 49                                     | 81%                              | 62%                                 | 7%                                            | 35%                    | 31%              | 95%                | 92%                              | 36%                        | -                                        | -             |
| DeepSeek R1 Distill Qwen 14B      | 128k           | 49                                     | 74%                              | 48%                                 | 4%                                            | 38%                    | 24%              | 93%                | 95%                              | 67%                        | -                                        | -             |
| DeepSeek R1 Distill Llama 70B     | 128k           | 48                                     | 80%                              | 40%                                 | 6%                                            | 27%                    | 31%              | 97%                | 94%                              | 67%                        | -                                        | -             |
| Claude 3.7 Sonnet                 | 200k           | 48                                     | 80%                              | 66%                                 | 5%                                            | 39%                    | 38%              | 95%                | 85%                              | 22%                        | -                                        | -             |
| Gemini 2.0 Flash                  | 1m             | 48                                     | 78%                              | 62%                                 | 5%                                            | 33%                    | 31%              | 90%                | 93%                              | 33%                        | -                                        | -             |
| Reka Flash 3                      | 128k           | 47                                     | 67%                              | 53%                                 | 5%                                            | 44%                    | 27%              | 95%                | 89%                              | 51%                        | -                                        | -             |
| Gemini 2.0 Flash (exp)            | 1m             | 46                                     | 78%                              | 64%                                 | 5%                                            | 21%                    | 34%              | 91%                | 91%                              | 30%                        | 84%                                      | -             |
| DeepSeek V3 (Dec '24)             | 128k           | 46                                     | 75%                              | 56%                                 | 4%                                            | 36%                    | 35%              | 91%                | 89%                              | 25%                        | 86%                                      | -             |
| Qwen2.5 Max                       | 32k             | 45                                     | 76%                              | 59%                                 | 5%                                            | 36%                    | 34%              | 93%                | 84%                              | 23%                        | -                                        | -             |
| Gemini 1.5 Pro (Sep)              | 2m             | 45                                     | 75%                              | 59%                                 | 5%                                            | 32%                    | 30%              | 90%                | 88%                              | 23%                        | 85%                                      | 1301          |
| Claude 3.5 Sonnet (Oct)           | 200k           | 44                                     | 77%                              | 60%                                 | 4%                                            | 38%                    | 37%              | 93%                | 77%                              | 16%                        | 88%                                      | 1282          |
| Sonar                             | 127k           | 43                                     | 69%                              | 47%                                 | 7%                                            | 30%                    | 23%              | 82%                | 82%                              | 49%                        | -                                        | -             |
| Llama 4 Scout                     | 10m            | 43                                     | 75%                              | 59%                                 | 4%                                            | 30%                    | 17%              | 83%                | 84%                              | 28%                        | -                                        | -             |
| Sonar Pro                         | 200k           | 43                                     | 76%                              | 58%                                 | 8%                                            | 28%                    | 23%              | 85%                | 75%                              | 29%                        | -                                        | -             |
| QwQ 32B-Preview                   | 33k             | 43                                     | 65%                              | 56%                                 | 5%                                            | 34%                    | 4%               | 87%                | 91%                              | 45%                        | -                                        | -             |
| GPT-4o (Nov '24)                  | 128k           | 41                                     | 75%                              | 54%                                 | 3%                                            | 31%                    | 33%              | 93%                | 76%                              | 15%                        | 84%                                      | 1361          |
| Gemini 2.0 Flash-Lite (Feb '25)   | 1m             | 41                                     | 72%                              | 54%                                 | 4%                                            | 19%                    | 25%              | 88%                | 87%                              | 28%                        | -                                        | -             |
| Llama 3.3 70B                     | 128k           | 41                                     | 71%                              | 50%                                 | 4%                                            | 29%                    | 26%              | 86%                | 77%                              | 30%                        | 84%                                      | -             |
| GPT-4o (May '24)                  | 128k           | 41                                     | 74%                              | 53%                                 | 3%                                            | 33%                    | 31%              | 94%                | 79%                              | 11%                        | -                                        | 1285          |
| Llama 3.1 405B                    | 128k           | 40                                     | 73%                              | 52%                                 | 4%                                            | 31%                    | 30%              | 85%                | 70%                              | 21%                        | 77%                                      | 1266          |
| Qwen2.5 72B                       | 131k           | 40                                     | 72%                              | 49%                                 | 4%                                            | 28%                    | 27%              | 88%                | 86%                              | 16%                        | 83%                                      | 1259          |
| MiniMax-Text-01                   | 4m             | 40                                     | 76%                              | 58%                                 | 4%                                            | 25%                    | 25%              | 86%                | 75%                              | 13%                        | -                                        | -             |
| Phi-4                             | 16k             | 40                                     | 71%                              | 57%                                 | 4%                                            | 23%                    | 26%              | 87%                | 81%                              | 14%                        | -                                        | -             |
| Command A                         | 256k           | 40                                     | 71%                              | 53%                                 | 5%                                            | 29%                    | 28%              | 82%                | 82%                              | 10%                        | -                                        | -             |
| Tulu3 405B                        | 128k           | 40                                     | 72%                              | 52%                                 | 4%                                            | 29%                    | 30%              | 89%                | 78%                              | 13%                        | -                                        | -             |
| Llama 3.3 Nemotron Super 49B v1   | 128k           | 39                                     | 70%                              | 52%                                 | 4%                                            | 28%                    | 23%              | 83%                | 78%                              | 19%                        | -                                        | -             |
| Grok 2                            | 131k           | 39                                     | 71%                              | 51%                                 | 4%                                            | 27%                    | 28%              | 86%                | 78%                              | 13%                        | -                                        | -             |
| Gemini 1.5 Flash (Sep)            | 1m             | 39                                     | 68%                              | 46%                                 | 4%                                            | 27%                    | 27%              | 84%                | 83%                              | 18%                        | 81%                                      | 1271          |
| Mistral Large 2 (Nov '24)         | 128k           | 38                                     | 70%                              | 49%                                 | 4%                                            | 29%                    | 29%              | 90%                | 74%                              | 11%                        | 83%                                      | -             |
| Gemma 3 27B                       | 128k           | 38                                     | 67%                              | 43%                                 | 5%                                            | 14%                    | 21%              | 89%                | 88%                              | 25%                        | -                                        | -             |
| Grok Beta                         | 128k           | 38                                     | 70%                              | 47%                                 | 5%                                            | 24%                    | 30%              | 87%                | 74%                              | 10%                        | -                                        | 1289          |
| Pixtral Large                     | 128k           | 37                                     | 70%                              | 51%                                 | 4%                                            | 26%                    | 29%              | 85%                | 71%                              | 7%                         | -                                        | -             |
| Qwen2.5 Instruct 32B              | 128k           | 37                                     | 70%                              | 47%                                 | 4%                                            | 25%                    | 23%              | 90%                | 81%                              | 11%                        | -                                        | -             |
| Llama 3.1 Nemotron 70B            | 128k           | 37                                     | 69%                              | 47%                                 | 5%                                            | 17%                    | 23%              | 82%                | 73%                              | 25%                        | -                                        | 1269          |
| Nova Pro                          | 300k           | 37                                     | 69%                              | 50%                                 | 3%                                            | 23%                    | 21%              | 83%                | 79%                              | 11%                        | 83%                                      | -             |
| Mistral Large 2 (Jul '24)         | 128k           | 37                                     | 68%                              | 47%                                 | 3%                                            | 27%                    | 27%              | 89%                | 71%                              | 9%                         | -                                        | 1251          |
| Qwen2.5 Coder 32B                 | 131k           | 36                                     | 64%                              | 42%                                 | 4%                                            | 30%                    | 27%              | 90%                | 77%                              | 12%                        | -                                        | 1220          |
| GPT-4o mini                       | 128k           | 36                                     | 65%                              | 43%                                 | 4%                                            | 23%                    | 23%              | 88%                | 79%                              | 12%                        | 80%                                      | 1273          |
| Llama 3.1 70B                     | 128k           | 35                                     | 68%                              | 41%                                 | 5%                                            | 23%                    | 27%              | 81%                | 65%                              | 17%                        | -                                        | 1249          |
| Mistral Small 3.1                 | 128k           | 35                                     | 66%                              | 45%                                 | 5%                                            | 21%                    | 27%              | 86%                | 71%                              | 9%                         | -                                        | -             |
| Mistral Small 3                   | 32k             | 35                                     | 65%                              | 46%                                 | 4%                                            | 25%                    | 24%              | 85%                | 72%                              | 8%                         | -                                        | -             |
| Claude 3 Opus                     | 200k           | 35                                     | 70%                              | 49%                                 | 3%                                            | 28%                    | 23%              | 85%                | 64%                              | 3%                         | -                                        | 1248          |
| Claude 3.5 Haiku                  | 200k           | 35                                     | 63%                              | 41%                                 | 4%                                            | 31%                    | 27%              | 86%                | 72%                              | 3%                         | 78%                                      | -             |
| DeepSeek R1 Distill Llama 8B      | 128k           | 34                                     | 54%                              | 30%                                 | 4%                                            | 23%                    | 12%              | 84%                | 85%                              | 33%                        | -                                        | -             |
| Gemma 3 12B                       | 128k           | 34                                     | 60%                              | 35%                                 | 5%                                            | 14%                    | 17%              | 83%                | 85%                              | 22%                        | -                                        | -             |
| Gemini 1.5 Pro (May)              | 2m             | 34                                     | 66%                              | 37%                                 | 4%                                            | 24%                    | 27%              | 83%                | 67%                              | 8%                         | -                                        | 1260          |
| Qwen Turbo                        | 1m             | 34                                     | 63%                              | 41%                                 | 4%                                            | 16%                    | 15%              | 85%                | 81%                              | 12%                        | -                                        | -             |
| Llama 3.2 90B (Vision)            | 128k           | 33                                     | 67%                              | 43%                                 | 5%                                            | 21%                    | 24%              | 82%                | 63%                              | 5%                         | -                                        | -             |
| Qwen2 72B                         | 131k           | 33                                     | 62%                              | 37%                                 | 4%                                            | 16%                    | 23%              | 83%                | 70%                              | 15%                        | -                                        | 1187          |
| Nova Lite                         | 300k           | 33                                     | 59%                              | 43%                                 | 5%                                            | 17%                    | 14%              | 84%                | 77%                              | 11%                        | 76%                                      | -             |
| Gemini 1.5 Flash-8B               | 1m             | 31                                     | 57%                              | 36%                                 | 5%                                            | 22%                    | 23%              | 12%                | 69%                              | 3%                         | 74%                                      | 1211          |
| Jamba 1.5 Large                   | 256k           | 29                                     | 57%                              | 43%                                 | 4%                                            | 14%                    | 16%              | 24%                | 61%                              | 5%                         | -                                        | 1221          |
| Jamba 1.6 Large                   | 256k           | 29                                     | 56%                              | 39%                                 | 4%                                            | 17%                    | 18%              | 70%                | 58%                              | 5%                         | -                                        | -             |
| Gemini 1.5 Flash (May)            | 1m             | 28                                     | 57%                              | 32%                                 | 4%                                            | 20%                    | 18%              | 72%                | 55%                              | 9%                         | -                                        | 1227          |
| Nova Micro                        | 130k           | 28                                     | 53%                              | 36%                                 | 5%                                            | 14%                    | 9%               | 80%                | 70%                              | 8%                         | 71%                                      | -             |
| Yi-Large                          | 32k             | 28                                     | 59%                              | 36%                                 | 3%                                            | 11%                    | 19%              | 74%                | 56%                              | 7%                         | -                                        | 1213          |
| Claude 3 Sonnet                   | 200k           | 28                                     | 58%                              | 40%                                 | 4%                                            | 18%                    | 23%              | 71%                | 41%                              | 5%                         | -                                        | 1201          |
| Codestral (Jan '25)               | 256k           | 28                                     | 45%                              | 31%                                 | 5%                                            | 24%                    | 25%              | 85%                | 61%                              | 4%                         | -                                        | -             |
| Llama 3 70B                       | 8k              | 27                                     | 57%                              | 38%                                 | 4%                                            | 20%                    | 19%              | 79%                | 48%                              | 0%                         | -                                        | 1206          |
| Mistral Small (Sep '24)           | 33k             | 27                                     | 53%                              | 38%                                 | 4%                                            | 14%                    | 16%              | 81%                | 56%                              | 6%                         | -                                        | -             |
| Phi-4 Multimodal                  | 128k           | 27                                     | 49%                              | 32%                                 | 4%                                            | 13%                    | 11%              | 73%                | 69%                              | 9%                         | -                                        | -             |
| Qwen2.5 Coder 7B                  | 131k           | 27                                     | 47%                              | 34%                                 | 5%                                            | 13%                    | 15%              | 90%                | 66%                              | 5%                         | -                                        | -             |
| Mistral Large (Feb '24)           | 33k             | 26                                     | 52%                              | 35%                                 | 3%                                            | 18%                    | 21%              | 71%                | 53%                              | 0%                         | -                                        | 1157          |
| Mixtral 8x22B                     | 65k             | 26                                     | 54%                              | 33%                                 | 4%                                            | 15%                    | 19%              | 72%                | 55%                              | 0%                         | -                                        | 1148          |
| Phi-4 Mini                        | 128k           | 26                                     | 47%                              | 33%                                 | 4%                                            | 13%                    | 11%              | 74%                | 70%                              | 3%                         | -                                        | -             |
| Phi-3 Medium 14B                  | 128k           | 25                                     | 54%                              | 33%                                 | 5%                                            | 15%                    | 12%              | 0%                 | 46%                              | 1%                         | -                                        | 1123          |
| Gemma 3 4B                        | 128k           | 24                                     | 42%                              | 29%                                 | 5%                                            | 7%                     | 6%               | 72%                | 77%                              | 5%                         | -                                        | -             |
| Claude 2.1                        | 200k           | 24                                     | 50%                              | 32%                                 | 4%                                            | 20%                    | 18%              | 16%                | 37%                              | 3%                         | -                                        | 1118          |
| Llama 3.1 8B                      | 128k           | 24                                     | 48%                              | 26%                                 | 5%                                            | 12%                    | 13%              | 67%                | 52%                              | 8%                         | 61%                                      | 1172          |
| Pixtral 12B                       | 128k           | 23                                     | 47%                              | 34%                                 | 5%                                            | 12%                    | 14%              | 78%                | 46%                              | 0%                         | -                                        | -             |
| Mistral Small (Feb '24)           | 33k             | 23                                     | 42%                              | 30%                                 | 4%                                            | 11%                    | 13%              | 79%                | 56%                              | 1%                         | -                                        | -             |
| Mistral Medium                    | 33k             | 23                                     | 49%                              | 35%                                 | 3%                                            | 10%                    | 12%              | -                  | 41%                              | 4%                         | -                                        | 1148          |
| Ministral 8B                      | 128k           | 22                                     | 39%                              | 28%                                 | 5%                                            | 11%                    | 12%              | 77%                | 57%                              | 4%                         | -                                        | 1183          |
| Gemma 2 9B                        | 8k              | 22                                     | 50%                              | 31%                                 | 4%                                            | 13%                    | 1%               | 65%                | 52%                              | 0%                         | -                                        | 1190          |
| Phi-3 Mini                        | 4k              | 22                                     | 44%                              | 32%                                 | 4%                                            | 12%                    | 9%               | 25%                | 46%                              | 4%                         | -                                        | 1037          |
| LFM 40B                           | 32k             | 22                                     | 43%                              | 33%                                 | 5%                                            | 10%                    | 7%               | 51%                | 48%                              | 2%                         | -                                        | -             |
| Command-R+                        | 128k           | 21                                     | 43%                              | 34%                                 | 5%                                            | 11%                    | 12%              | 63%                | 40%                              | 0%                         | -                                        | 1215          |
| Llama 3 8B                        | 8k              | 21                                     | 41%                              | 30%                                 | 5%                                            | 10%                    | 12%              | 71%                | 50%                              | 0%                         | -                                        | 1152          |
| Gemini 1.0 Pro                    | 33k             | 21                                     | 43%                              | 28%                                 | 5%                                            | 12%                    | 12%              | 2%                 | 40%                              | 1%                         | -                                        | 1111          |
| Codestral (May '24)               | 33k             | 20                                     | 33%                              | 26%                                 | 5%                                            | 21%                    | 22%              | 80%                | 35%                              | 0%                         | -                                        | -             |
| Aya Expanse 32B                   | 128k           | 20                                     | 38%                              | 23%                                 | 5%                                            | 14%                    | 15%              | 68%                | 45%                              | 0%                         | 65%                                      | 1207          |
| Llama 2 Chat 13B                  | 4k              | 20                                     | 41%                              | 32%                                 | 5%                                            | 10%                    | 12%              | -                  | 33%                              | 2%                         | -                                        | 1063          |
| Command-R+ (Apr '24)              | 128k           | 20                                     | 43%                              | 32%                                 | 5%                                            | 12%                    | 12%              | 64%                | 28%                              | 1%                         | -                                        | 1190          |
| DBRX                              | 33k             | 20                                     | 40%                              | 33%                                 | 7%                                            | 9%                     | 12%              | 67%                | 28%                              | 3%                         | -                                        | 1103          |
| Ministral 3B                      | 128k           | 20                                     | 34%                              | 26%                                 | 6%                                            | 7%                     | 9%               | 74%                | 54%                              | 0%                         | -                                        | -             |
| Mistral NeMo                      | 128k           | 20                                     | 40%                              | 31%                                 | 4%                                            | 6%                     | 10%              | 65%                | 40%                              | 0%                         | -                                        | -             |
| Llama 3.2 3B                      | 128k           | 20                                     | 35%                              | 26%                                 | 5%                                            | 8%                     | 5%               | 56%                | 49%                              | 7%                         | -                                        | 1103          |
| DeepSeek R1 Distill Qwen 1.5B     | 128k           | 19                                     | 27%                              | 10%                                 | 3%                                            | 7%                     | 7%               | 45%                | 69%                              | 18%                        | -                                        | -             |
| Jamba 1.5 Mini                    | 256k           | 18                                     | 37%                              | 30%                                 | 5%                                            | 6%                     | 8%               | 63%                | 36%                              | 1%                         | -                                        | 1176          |
| Jamba 1.6 Mini                    | 256k           | 18                                     | 37%                              | 30%                                 | 5%                                            | 7%                     | 10%              | 43%                | 26%                              | 3%                         | -                                        | -             |
| Mixtral 8x7B                      | 33k             | 17                                     | 39%                              | 29%                                 | 5%                                            | 7%                     | 3%               | 1%                 | 30%                              | 0%                         | -                                        | 1114          |
| Aya Expanse 8B                    | 8k              | 16                                     | 31%                              | 25%                                 | 5%                                            | 7%                     | 8%               | 44%                | 32%                              | 0%                         | 49%                                      | -             |
| Command-R                         | 128k           | 15                                     | 34%                              | 29%                                 | 5%                                            | 4%                     | 9%               | 42%                | 15%                              | 0%                         | -                                        | 1179          |
| Command-R (Mar '24)               | 128k           | 15                                     | 34%                              | 28%                                 | 5%                                            | 5%                     | 6%               | 40%                | 16%                              | 1%                         | -                                        | 1149          |
| Codestral-Mamba                   | 256k           | 14                                     | 21%                              | 21%                                 | 5%                                            | 13%                    | 11%              | 80%                | 24%                              | 0%                         | -                                        | -             |
| Mistral 7B                        | 8k              | 10                                     | 25%                              | 18%                                 | 4%                                            | 5%                     | 2%               | 40%                | 12%                              | 0%                         | -                                        | 1008          |
| Llama 3.2 1B                      | 128k           | 10                                     | 20%                              | 20%                                 | 5%                                            | 2%                     | 2%               | 40%                | 14%                              | 0%                         | -                                        | 1054          |
| Llama 2 Chat 7B                   | 4k              | 8                                      | 16%                              | 23%                                 | 6%                                            | 0%                     | 0%               | -                  | 6%                               | 0%                         | -                                        | 1037          |
