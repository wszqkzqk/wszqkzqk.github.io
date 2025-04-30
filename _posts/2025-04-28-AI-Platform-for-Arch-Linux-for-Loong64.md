---
layout:     post
title:      为Arch Linux for Loong64设计的AI平台
subtitle:   能够为Arch Linux for Loong64的开发者与用户提供帮助的AI助手
date:       2025-04-28
author:     wszqkzqk
header-img: img/llm/ai-bg-lossless.webp
catalog:    true
tags:       AI LLM 开源软件 LoongArchLinux
---

## 前言

随着Arch Linux for Loong64项目的不断发展，我们积累了越来越多的开发文档，并形成了一套相对完整的开发流程和社区习惯。为了更好地服务于Arch Linux for Loong64的开发者与用户，笔者搭建了一个AI平台，旨在为Arch Linux for Loong64的开发者与用户提供帮助。

该平台目前**仅**向**可访问北京大学校园网**的**Arch Linux for Loong64的开发者与用户**公开。

## 技术实现过程

笔者选择了[Open WebUI](https://docs.openwebui.com/)作为前端平台，LLM均使用**开源大模型**，其中单模态模型使用[DeepSeek v3 0324](https://api-docs.deepseek.com/zh-cn/news/news250325)，多模态模型使用[Llama 4 Maverick](https://www.llama.com/models/llama-4/)。这两个模型基本上是目前（2025.04.28）开源的单模态和多模态模型（尤其是文字识别应用）中性能最好的。（不过LLama 4 Maverick的日常处理和代码能力确实不敢恭维……）

* 更新：2024.04.29，[Qwen 3发布](https://qwenlm.github.io/zh/blog/qwen3/)，Qwen 3 235B A22B的**性能**似乎更强：

|          | Qwen3-235B-A22B MoE | Qwen3-32B Dense | OpenAI-o1 2024-12-17 | Deepseek-R1 | Grok 3 Beta Think | Gemini2.5-Pro | OpenAI-o3-mini Medium |
|----------|--------------------|-----------------|----------------------|-------------|-------------------|----------------|------------------------|
| ArenaHard | 95.6               | 93.8            | 92.1                 | 93.2        | -                 | 96.4           | 89.0                   |
| AIME'24   | 85.7               | 81.4            | 74.3                 | 79.8        | 83.9              | 92.0           | 79.6                   |
| AIME'25   | 81.5               | 72.9            | 79.2                 | 70.0        | 77.3              | 86.7           | 74.8                   |
| LiveCodeBench v5, 2024.10-2025.02 | 70.7               | 65.7            | 63.9                 | 64.3        | 70.6              | 70.4           | 66.3                   |
| CodeForces Elo Rating | 2056               | 1977            | 1891                 | 2029        | -                 | 2001           | 2036                   |
| Aider Pass@2 | 61.8               | 50.2            | 61.7                 | 56.9        | 53.3              | 72.9           | 53.8                   |
| LiveBench 2024-11-25 | 77.1               | 74.9            | 75.7                 | 71.6        | -                 | 82.4           | 70.0                   |
| BFCL v3    | 70.8               | 70.3            | 67.8                 | 56.9        | -                 | 62.9           | 64.6                   |
| MultilF 8 Languages | 71.9               | 73.0            | 48.8                 | 67.7        | -                 | 77.8           | 48.4                   |

但是**上下文长度**支持似乎是一个短板：

> It natively handles a 32K token context window and extends up to 131K tokens using YaRN-based scaling.

以下表格摘自[Fiction.liveBench](https://fiction.live/stories/Fiction-liveBench-April-14-2025/oQdzQvKHw8JyXbN87)（2025.04.30）：

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
| qwen3-235b-a22b:free | 100.0 | 90.0 | 89.3 | 80.0 | 69.0 | 66.7 | 67.7 | - | - | - |
| qwen3-32b:free | 80.0 | 90.9 | 93.8 | 76.7 | 86.7 | 80.0 | 74.2 | - | - | - |
| qwen3-30b-a3b:free | 85.7 | 58.1 | 54.8 | 51.5 | 53.3 | 50.0 | 40.6 | - | - | - |
| qwen3-14b:free | 83.3 | 64.5 | 61.8 | 59.4 | 64.7 | 51.6 | 62.5 | - | - | - |
| qwen3-8b:free | 100.0 | 77.4 | 63.3 | 66.7 | 74.2 | 61.3 | 62.1 | - | - | - |
| grok-3-mini-beta | 87.5 | 77.8 | 77.8 | 80.6 | 77.8 | 72.2 | 66.7 | 75.0 | 72.2 | 65.6 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-4.1 | 100.0 | 91.7 | 75.0 | 69.4 | 63.9 | 55.6 | 63.9 | 58.3 | 52.8 | 62.5 |
| gpt-4.1-mini | 75.0 | 66.7 | 55.6 | 41.7 | 44.4 | 41.7 | 44.4 | 38.9 | 38.9 | 46.9 |
| gpt-4.1-nano | 62.5 | 50.0 | 41.7 | 36.1 | 33.3 | 38.9 | 25.0 | 33.3 | 36.1 | 18.8 |
| chatgpt-4o-latest | 87.5 | 83.3 | 66.7 | 63.9 | 63.9 | 66.7 | 66.7 | 63.9 | 55.6 | 65.6 |
| gpt-4.5-preview | 100.0 | 94.4 | 83.3 | 83.3 | 83.3 | 72.2 | 63.9 | 63.9 | 66.7 | 63.9 |
| claude-3-7-sonnet-20250219 | 100.0 | 77.8 | 80.6 | 72.2 | 61.1 | 52.8 | 50.0 | 52.8 | 44.4 | 34.4 |
| deepseek-chat-v3-0324:free | 87.5 | 61.1 | 69.4 | 52.8 | 52.8 | 52.8 | 50.0 | 55.6 | 55.6 | - |
| deepseek-chat:free | 87.5 | 61.1 | 61.1 | 55.6 | 55.6 | 50.0 | 61.1 | 16.7 | 19.4 | - |
| qwen-max | 75.0 | 69.4 | 69.4 | 63.9 | 72.2 | 63.9 | 66.7 | - | - | - |
| gemma-3-27b-it:free | 87.5 | 44.4 | 50.0 | 41.7 | 33.3 | 38.9 | 33.3 | 25.0 | 30.6 | - |
| gemini-2.5-flash-preview | 62.5 | 63.9 | 69.4 | 61.1 | 47.2 | 44.4 | 47.2 | 44.4 | 58.3 | 53.1 |
| gemini-2.0-pro-exp-02-05:free | 87.5 | 91.7 | 80.6 | 72.2 | 61.1 | 52.8 | 41.7 | 47.2 | 41.7 | 37.5 |
| gemini-2.0-flash-001 | 100.0 | 63.9 | 58.3 | 55.6 | 47.2 | 50.0 | 61.1 | 50.0 | 47.2 | 62.5 |
| llama-4-maverick:free | 100.0 | 56.0 | 50.0 | 52.0 | 48.0 | 48.0 | 46.2 | 44.0 | 32.0 | 36.4 |
| llama-4-scout:free | 62.5 | 52.0 | 50.0 | 36.0 | 32.0 | 40.0 | 36.0 | 16.0 | 24.0 | 27.3 |
| llama-3.3-70b-instruct | 75.0 | 66.7 | 69.4 | 55.6 | 41.7 | 36.1 | 33.3 | 33.3 | 33.3 | - |
| grok-3-beta | 75.0 | 72.2 | 63.9 | 55.6 | 55.6 | 52.8 | 58.3 | 55.6 | 63.9 | 58.3 |

Qwen 3 235B A22B原生仅支持32 K的上下文窗口，扩展到131 K的上下文窗口需要借助YaRN-based scaling，在**大量文档的RAG场景**以及冗长的构建日志分析中可能会超出上下文窗口的限制而报错。（不过在**不超过其窗口范围**时上下文理解表现尚可）因此笔者仅将其作为可选项，默认模型仍然是DeepSeek v3 0324。（由于DeepSeek v3 0324是非推理模型，而Qwen 3 235B A22B是推理模型，用户也正好可以按照实际需要选择使用）

笔者主要希望通过增强问答（RAG，Retrieval-Augmented Generation）来赋予模型帮助Arch Linux for Loong64开发者和用户的能力。

### Open WebUI配置

#### 基本

笔者在16核16 GB内存的AMD Zen 3虚拟机（CLab）上部署了Open WebUI，笔者并没有使用Docker，而是直接通过`pacman`从`archlinuxcn`安装了Open WebUI。

```bash
sudo pacman -S open-webui
```

安装完成后，还需要启用Open WebUI的服务：

```bash
sudo systemctl enable open-webui.service --now
```

Open WebUI默认使用`0.0.0.0:8080`作为地址，因此直接可以通过`http://<IP>:8080`在其他设备上访问。

首次访问时会提示注册管理员账号并设置密码。随后，可以点击头像，进入管理员设置界面（或者直接访问`http://<IP>:8080/admin/settings`），通过`设置 -> 管理OpenAI API连接 -> +`添加API连接，输入API Key和API URL。完成之后点击`保存`，即可完成API连接的设置。

### RAG配置

找到`文档`进行设置。由于笔者的机器没有GPU，性能受限，笔者只能在效果和速度之间进行权衡。笔者发现嵌入模型如果选择更准确、更受欢迎的`BGE-m3`，在面对**大量文档**的检索时会**慢**到不可接受，因此笔者最后还是回退到了默认的`sentence-transformers/all-MiniLM-L6-v2`模型，这一模型的参数量仅有**22 M**（0.022 B），速度快，效果尚可。

而有关检索的设置，笔者启用了混合检索模式，使用小模型`BAAI/bge-reranker-base`作为**重排序**模型（同样是因为效果更好的`BAAI/bge-reranker-v2-m3`性能开销不可接受），设置`块大小 (Chunk Size)`为`1024`，`块重叠 (Chunk Overlap)`为`100`，`Top K`为`50`，`Top K Reranker`为`20`，并设置`Relevance Threshold`为`0.1`，这样的设置虽然有所妥协，效果基本上也能接受。

这样的设置含义是：
* `块大小 (Chunk Size)`：每个文档块大小，设置为`1024`，即每个块有1024个Token
* `块重叠 (Chunk Overlap)`：每个文档块重叠的大小，设置为`100`，即每个块与前一个块的重叠大小为100
* `Top K`：检索时返回的文档数量，设置为`50`，即检索选择50个（嵌入向量余弦相似度最大的）文档
* `Top K Reranker`：重排序时返回的文档数量，设置为`20`，即重排序检索返回的文档，将前20个文档传递给LLM作为上下文
  * 虽然重排序模型是可选的，即使没有重排序模型，嵌入模型也会对检索的文档按照匹配度进行排序
  * 但是这一匹配度只是基于文本**嵌入向量**的**余弦值**简单得出，在真实场景中往往**不够准确**
  * 重排序可以将更准确的文档排在前面并排除劣质的检索结果
* * `Relevance Threshold`：检索时的相关性阈值，设置为`0.1`，即检索到的文档的相关性余弦值大于0.1才会被返回

经过测试，即使是添加了这样简单的重排序模型，也可对检索的准确率带来显著提升。（似乎收益比使用更强大的`BGE-m3`作为嵌入模型但不添加重排序模型的效果要好）对于块大小似乎不宜设置得更大，否则检索速度会严重降低。

### 添加文档

点击UI左侧的`工作空间`，点击上方的`知识库`（或者直接访问`http://<IP>:8080/workspace/knowledge`），点击右上角的`+`，按照要求补充信息，并上传文档即可。笔者建立了两个相关知识库：

* Arch Linux for Loong64
  * 笔者撰写的Arch Linux for Loong64的开发文档，包括自己的相关博客和GitHub上的Wiki文档
  * 龙芯公开的手册：[龙芯架构参考手册 - 卷一](https://github.com/loongson/LoongArch-Documentation/releases/latest/download/LoongArch-Vol1-v1.10-CN.pdf)
* ArchWiki
  * Arch Linux上游的ArchWiki的全部内容（获取自`arch-wiki-docs`包）

### 创建模型

点击UI左侧的`工作空间`，随后点击上方的`模型`（或者直接访问`http://<IP>:8080/workspace/models`），点击右上角的`+`，补充信息并创建用于Arch Linux for Loong64助手的模型。笔者创建了3个模型：

* Arch Linux for Loong64 Dev Helper
  * 回答有关Arch Linux for Loong64维护的问题
  * 使用`DeepSeek v3 0324`作为LLM
  * 可访问`Arch Linux for Loong64`知识库
  * 系统提示词为：
    ```
    你是一个帮助Arch Linux for Loong64维护者工作的助手，在Arch Linux for Loong64知识库中有答案时优先根据知识库回答，如果知识库中没有答案但是有检索得到的上下文参考时可以参考可信较高的检索内容（不要参考劣质****博客），否则结合自身知识（给出结合自身知识的说明），并按照你认为最合理的方式回答
    ```
* Arch Linux for Loong64 Dev Helper (Reasoning)
  * 回答有关Arch Linux for Loong64维护的问题
  * 使用`Qwen 3 235B A22B`作为LLM
  * 可访问`Arch Linux for Loong64`知识库
  * 系统提示词为：
    ```
    你是一个帮助Arch Linux for Loong64维护者工作的助手，在Arch Linux for Loong64知识库中有答案时优先根据知识库回答，如果知识库中没有答案但是有检索得到的上下文参考时可以参考可信较高的检索内容（不要参考劣质****博客），否则结合自身知识（给出结合自身知识的说明），并按照你认为最合理的方式回答
    ```
* Arch Linux for Loong64 Dev Helper VL
  * 多模态模型，可用于拍屏/截图日志分析，回答有关Arch Linux for Loong64维护的问题（仅建议用于多模态用途）
  * 使用`Llama 4 Maverick`作为LLM
  * 可访问`Arch Linux for Loong64`知识库
  * 系统提示词为：
    ```
    你是一个帮助Arch Linux for Loong64维护者工作的助手，在Arch Linux for Loong64知识库中有答案时优先根据知识库回答，如果知识库中没有答案但是有检索得到的上下文参考时可以参考可信较高的检索内容（不要参考劣质****博客），否则结合自身知识（给出结合自身知识的说明），并按照你认为最合理的方式回答。作为一个多模态模型，你需要准确识别用户可能发送的截图、拍屏，并精准完整地提炼信息。
    ```
* Arch Linux for Loong64 Generic Helper (Beta)
  * 更通用的Arch Linux for Loong64助手（Beta），除Arch Linux for Loong64外还拥有ArchWiki的知识（但检索较慢且效果可能不如启用网页搜索后的开发助手）
  * 使用`DeepSeek v3 0324`作为LLM
  * 可访问`Arch Linux for Loong64`和`ArchWiki`知识库
  * 系统提示词为：
    ```
    你是一个帮助Arch Linux或者Arch Linux for Loong64维护者及用户的助手（没有特殊说明架构的时候假定架构为Loong64）。在知识库中有答案时优先根据知识库回答，注意有关Loong64架构的问题应当优先按照Arch Linux for Loong64的文档说明和社区习惯回答；如果知识库中没有答案但是有检索得到的上下文参考时可以参考可信较高的检索内容（不要参考劣质****博客）；否则结合自身知识（给出结合自身知识的说明），并按照你认为最合理的方式回答
    ```

创建完成后，将这些模型设置为`公开`，或者对Arch Linux for Loong64的用户组开放。在`管理员面板 -> 设置 -> 模型 -> （右上角齿轮图标）`中设置模型，将这些助手模型添加到默认模型列表中。

## 使用方法

* 对于Arch Linux for Loong64用户组，笔者设定了默认模型为`Arch Linux for Loong64 Dev Helper`，理论上注册后激活即**开箱即用**。
* 如果遇到需要**深度推理**的问题且上下文长度不算太大，可以使用`Arch Linux for Loong64 Dev Helper (Reasoning)`模型进行分析。
* 如果遇到不便于分析日志的**拍屏、截图**等问题，可以使用`Arch Linux for Loong64 Dev Helper VL`模型进行分析。
  * 在输入框中输入`@`即可在对话中切换模型。
  * 由于`Llama 4 Maverick`逻辑能力与代码能力均较差，建议仅使用该模型提取多模态信息，分析工作仍然交给`Arch Linux for Loong64 Dev Helper`来完成。
* 目前`Arch Linux for Loong64 Generic Helper (Beta)`模型的效果并不理想，检索速度较慢，且准确性一般。
  * 建议使用`Arch Linux for Loong64 Dev Helper`模型并开启**网页搜索**功能替代。
  * **ArchWiki非常著名**，很容易被搜索引擎收录。（相比之下Arch Linux for Loong64的文档则很难直接通过搜索引擎找到）
  * 现代搜索引擎使用的检索模型远远比笔者本地部署的要强大，更容易找到正确的内容，因此在合适的提示词下可能给出比笔者特意建立的ArchWiki检索系统更准确的答案。

建议一般情况下使用`Arch Linux for Loong64 Dev Helper`或者`Arch Linux for Loong64 Dev Helper (Reasoning)`模型（可按照实际需要开启网页搜索功能），需要多模态分析拍屏或者截图时使用`@`在对话中切换暂时切换到`Arch Linux for Loong64 Dev Helper VL`模型提取日志等信息，但后续分析仍然使用默认的`Arch Linux for Loong64 Dev Helper`模型。

需要注意，即使有了RAG加持，**模型的回答仍然可能不准确**，建议用户对模型的回答进行事实验证。由于输出内容中会包含检索引文，用户可以自行检索引文（或访问相应的文档网页）来验证模型的回答。

## 效果展示

|[![#~/img/llm/arch-linux-for-loong64-helper.webp](/img/llm/arch-linux-for-loong64-helper.webp)](/img/llm/arch-linux-for-loong64-helper.webp)|
|:----:|
|Arch Linux for Loong64 Dev Helper（默认）|

|[![#~/img/llm/arch-linux-for-loong64-helper-vl.webp](/img/llm/arch-linux-for-loong64-helper-vl.webp)](/img/llm/arch-linux-for-loong64-helper-vl.webp)|
|:----:|
|Arch Linux for Loong64 Dev Helper VL|

|[![#~/img/llm/arch-linux-for-loong64-helper-generic.webp](/img/llm/arch-linux-for-loong64-helper-generic.webp)](/img/llm/arch-linux-for-loong64-helper-generic.webp)|
|:----:|
|Arch Linux for Loong64 Generic Helper (Beta)|

|[![#~/img/llm/answer1-arch-linux-for-loong64-helper-lossless.webp](/img/llm/answer1-arch-linux-for-loong64-helper-lossless.webp)](/img/llm/answer1-arch-linux-for-loong64-helper-lossless.webp)|
|:----:|
|回答效果示例|

|[![#~/img/llm/answer2-arch-linux-for-loong64-helper-lossless.webp](/img/llm/answer2-arch-linux-for-loong64-helper-lossless.webp)](/img/llm/answer2-arch-linux-for-loong64-helper-lossless.webp)|
|:----:|
|回答效果示例|

|[![#~/img/llm/answer3-arch-linux-for-loong64-helper-lossless.webp](/img/llm/answer3-arch-linux-for-loong64-helper-lossless.webp)](/img/llm/answer3-arch-linux-for-loong64-helper-lossless.webp)|
|:----:|
|回答效果示例|
