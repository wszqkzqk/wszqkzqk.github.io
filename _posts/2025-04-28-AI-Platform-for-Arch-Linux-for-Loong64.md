---
layout:     post
title:      为Arch Linux for Loong64设计的AI平台
subtitle:   利用Open WebUI与RAG技术构建基于开源大模型的AI助手
date:       2025-04-28
author:     wszqkzqk
header-img: img/llm/ai-bg-lossless.webp
catalog:    true
tags:       AI LLM 开源软件 archlinux LoongArchLinux
---

## 前言

随着Arch Linux for Loong64项目的不断发展，我们积累了越来越多的开发文档，并形成了一套相对完整的开发流程和社区习惯。为了更好地服务于Arch Linux for Loong64的开发者与用户，笔者搭建了一个AI平台，旨在为Arch Linux for Loong64的开发者与用户提供帮助。

该平台目前**仅**向可访问**北京大学校园网**的**Arch Linux for Loong64**开发者与用户公开。

## 技术实现过程

笔者选择了[Open WebUI](https://docs.openwebui.com/)作为前端平台。

### 模型选择

该平台LLM均使用**开源大模型**，其中单模态模型使用[DeepSeek V3 0324](https://api-docs.deepseek.com/zh-cn/news/news250325)，多模态模型使用[Llama 4 Maverick](https://www.llama.com/models/llama-4/)。这两个模型基本上是目前（2025.04.28）开源的单模态和多模态模型（尤其是文字识别应用）中性能最好的。（不过LLama 4 Maverick的日常处理和代码能力确实不敢恭维……）

笔者主要希望通过增强问答（RAG，Retrieval-Augmented Generation）来赋予模型帮助Arch Linux for Loong64开发者和用户的能力。

#### 2024.04.29更新：引入Qwen 3 235B A22B作为推理模型

2024.04.29，[Qwen 3发布](https://qwenlm.github.io/zh/blog/qwen3/)，Qwen 3 235B A22B的**性能**似乎更强：

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

Qwen 3 235B A22B原生仅支持32 K的上下文窗口，扩展到131 K的上下文窗口需要借助YaRN-based scaling，在**大量文档的RAG场景**以及冗长的构建日志分析中可能会超出上下文窗口的限制而报错。（不过在**不超过其窗口范围**时上下文理解表现尚可）因此笔者仅将其作为可选项。（由于DeepSeek V3 0324是非推理模型，而Qwen 3 235B A22B是推理模型，用户也正好可以按照实际需要选择使用）

除了性能外，幻觉率也是一个很重要的考虑因素，以下是笔者于2025.04.30在[vectara](https://vectara-leaderboard.hf.space/?__theme=system)上摘录的结果：

| Model                     | Hallucination Rate | Factual Consistency Rate | Answer Rate | Summary Length (Words) |
|---------------------------|--------------------:|--------------------------:|------------:|------------------------:|
| OpenAI o3-mini-high       | 0.8 %              | 99.2 %                   | 100.0 %     | 79.5                   |
| Gemini-2.5-Pro-Exp-0325   | 1.1 %              | 98.9 %                   | 95.1 %      | 72.9                   |
| Gemini-2.5-Flash-Preview  | 1.3 %              | 98.7 %                   | 91.2 %      | 71.1                   |
| Grok-3-Beta               | 2.1 %              | 97.8 %                   | 100.0 %     | 97.7                   |
| Qwen3-14B                 | 2.2 %              | 97.8 %                   | 100.0 %     | 82.4                   |
| Qwen3-4B                  | 2.7 %              | 97.3 %                   | 100.0 %     | 87.7                   |
| Qwen3-32B                 | 2.8 %              | 97.2 %                   | 100.0 %     | 82.4                   |
| Qwen3-8B                  | 3.0 %              | 97.0 %                   | 100.0 %     | 78.2                   |
| Grok-3-Mini-Beta          | 3.3 %              | 96.7 %                   | 100.0 %     | 90.2                   |
| DeepSeek-V3               | 3.9 %              | 96.1 %                   | 100.0 %     | 88.2                   |
| Claude-3.7-Sonnet         | 4.4 %              | 95.6 %                   | 100.0 %     | 97.8                   |
| Claude-3.7-Sonnet-Think   | 4.5 %              | 95.5 %                   | 99.8 %      | 99.9                   |
| Meta Llama-4-Maverick     | 4.6 %              | 95.4 %                   | 100.0 %     | 84.8                   |
| OpenAI o4-mini            | 4.6 %              | 95.4 %                   | 100.0 %     | 82.0                   |
| Qwen3-30b-a3b             | 7.6 %              | 92.4 %                   | 99.9 %      | 69.9                   |
| DeepSeek-V3-0324          | 8.0 %              | 92.0 %                   | 100.0 %     | 78.9                   |
| Qwen3-235b-a22b           | 13.0 %             | 87.0 %                   | 99.2 %      | 86.6                   |
| DeepSeek-R1               | 14.3 %             | 85.7 %                   | 100.0 %     | 77.1                   |

可见其实Qwen 3 235B A22B的**幻觉率相当高**，所以默认还是使用DeepSeek V3 0324作为RAG相对合理。

#### 2025.05.29更新：使用DeepSeek R1 0528作为新的推理模型

2025.05.28，DeepSeek R1模型进行了小版本更新，升级后的DeepSeek R1 0528模型性能提升十分明显，夺回了开源大模型的单模态性能王座。

以下信息来自DeepSeek官方的[模型卡片](https://huggingface.co/deepseek-ai/DeepSeek-R1-0528)：

| Category | Benchmark (Metric)               | DeepSeek R1     | DeepSeek R1 0528
|----------|----------------------------------|-----------------|---|
| General  |
|          | MMLU-Redux (EM)                   | 92.9            | 93.4
|          | MMLU-Pro (EM)                     | 84.0            | 85.0
|          | GPQA-Diamond (Pass@1)             | 71.5            | 81.0
|          | SimpleQA (Correct)                | 30.1            | 27.8
|          | FRAMES (Acc.)                     | 82.5            | 83.0
|          | Humanity's Last Exam (Pass@1)                     | 8.5            | 17.7
| Code |
|          | LiveCodeBench (2408-2505) (Pass@1)        | 63.5          | 73.3
|          | Codeforces-Div1 (Rating)          | 1530            | 1930
|          | SWE Verified (Resolved)           | 49.2            | 57.6
|          | Aider-Polyglot (Acc.)             | 53.3            | 71.6
| Math |
|          | AIME 2024 (Pass@1)                | 79.8            | 91.4
|          | AIME 2025 (Pass@1)                     | 70.0           | 87.5
|          | HMMT 2025 (Pass@1)            | 41.7 | 79.4 |
|          | CNMO 2024 (Pass@1)                | 78.8            | 86.9
| Tools |
|          | BFCL_v3_MultiTurn (Acc)     | -            | 37.0 |
|          | Tau-Bench   (Pass@1)       | -            | 53.5(Airline)/63.9(Retail)

| Benchmarks                        | DeepSeek-R1-0528 | OpenAI-o3 | Gemini-2.5-Pro-0506 | Qwen3-235B | DeepSeek-R1 |
|-----------------------------------|------------------|-----------|---------------------|------------|--------------|
| AIME 2024                         | 91.4             | 91.6      | 90.8                | 85.7       | 79.8         |
| AIME 2025                         | 87.5             | 88.9      | 83.0                | 81.5       | 70.0         |
| GPQA Diamond                      | 81.0             | 83.3      | 83.0                | 71.1       | 71.5         |
| LiveCodeBench                     | 73.3             | 77.3      | 71.8                | 66.5       | 63.5         |
| Aider                             | 71.6             | 79.6      | 76.9                | 65.0       | 57.0         |
| Humanity's Last Exam              | 17.7             | 20.6      | 18.4                | 11.75      | 8.5          |

以下表格摘自[Fiction.liveBench](https://fiction.live/stories/Fiction-liveBench-May-22-2025/oQdzQvKHw8JyXbN87)：

| Model | 0 | 400 | 1k | 2k | 4k | 8k | 16k | 32k | 60k | 120k | 192k |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| o3 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 88.9 | 100.0 | 83.3 | 100.0 | 58.1 |
| o4-mini | 100.0 | 100.0 | 100.0 | 100.0 | 77.8 | 66.7 | 77.8 | 55.6 | 66.7 | 62.5 | 43.8 |
| o1 | 100.0 | 97.2 | 100.0 | 94.4 | 94.4 | 86.1 | 83.3 | 83.3 | 72.2 | 53.1 |  |
| o3-mini | 100.0 | 63.9 | 58.3 | 47.2 | 47.2 | 50.0 | 50.0 | 55.6 | 44.4 | 43.8 |  |
| claude-3-7-sonnet-20250219-thinking | 100.0 | 100.0 | 100.0 | 97.2 | 91.7 | 97.2 | 83.3 | 75.0 | 69.4 | 53.1 |  |
| deepseek-r1 | 100.0 | 82.2 | 80.6 | 76.7 | 77.8 | 83.3 | 69.4 | 63.9 | 66.7 | 33.3 |  |
| deepseek-r1-0528:free | 100.0 | 91.7 | 83.3 | 82.9 | 88.9 | 86.1 | 75.0 | 69.4 | 58.3 | - | - |
| gemini-2.5-pro-preview-06-05 | 100.0 | 100.0 | 100.0 | 97.2 | 94.4 | 80.6 | 91.7 | 91.7 | 83.3 | 87.5 | 90.6 |
| gemini-2.5-pro-preview-05-06 | 100.0 | 97.2 | 86.1 | 83.3 | 75.0 | 69.4 | 66.7 | 72.2 | 61.1 | 71.9 | 72.2 |
| gemini-2.5-pro-exp-03-25:free | 100.0 | 100.0 | 100.0 | 100.0 | 97.2 | 91.7 | 66.7 | 86.1 | 83.3 | 90.6 |  |
| gemini-2.5-flash-preview-05-20 | 100.0 | 97.2 | 94.4 | 75.0 | 91.7 | 72.2 | 77.8 | 55.6 | 69.4 | 68.8 | 65.6 |
| qwq-32b:free | 100.0 | 91.7 | 94.4 | 88.9 | 94.4 | 86.1 | 83.3 | 80.6 | 61.1 | - |  |
| qwen3-235b-a222b:free | 100.0 | 90.0 | 89.3 | 80.0 | 69.0 | 66.7 | 67.7 | - | - | - |  |
| qwen3-32b:free | 80.0 | 90.9 | 93.8 | 76.7 | 86.7 | 80.0 | 74.2 | - | - | - |  |
| qwen3-30b-a3b:free | 85.7 | 58.1 | 54.8 | 51.5 | 53.3 | 50.0 | 40.6 | - | - | - |  |
| qwen3-14b:free | 83.3 | 64.5 | 61.8 | 59.4 | 64.7 | 51.6 | 62.5 | - | - | - |  |
| qwen3-8b:free | 100.0 | 77.4 | 63.3 | 66.7 | 74.2 | 61.3 | 62.1 | - | - | - |  |
| grok-3-mini-beta | 87.5 | 77.8 | 77.8 | 80.6 | 77.8 | 72.2 | 66.7 | 75.0 | 72.2 | 65.6 |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-4.1 | 100.0 | 91.7 | 75.0 | 69.4 | 63.9 | 55.6 | 63.9 | 58.3 | 52.8 | 62.5 | 56.3 |
| gpt-4.1-mini | 75.0 | 66.7 | 55.6 | 41.7 | 44.4 | 41.7 | 44.4 | 38.9 | 38.9 | 46.9 |  |
| gpt-4.1-nano | 62.5 | 50.0 | 41.7 | 36.1 | 33.3 | 38.9 | 25.0 | 33.3 | 36.1 | 18.8 |  |
| chatgpt-4o-latest | 87.5 | 83.3 | 66.7 | 63.9 | 63.9 | 66.7 | 66.7 | 63.9 | 55.6 | 65.6 |  |
| gpt-4.5-preview | 100.0 | 94.4 | 83.3 | 83.3 | 83.3 | 72.2 | 63.9 | 63.9 | 66.7 | 63.9 |  |
| claude-opus-4 | 100.0 | 77.8 | 77.8 | 66.7 | 66.7 | 66.7 | 61.1 | 63.9 | 55.6 | 37.5 | - |
| claude-sonnet-4 | 100.0 | 77.8 | 62.5 | 66.7 | 55.6 | 55.6 | 46.9 | 44.4 | 37.5 | 36.4 | - |
| claude-3-7-sonnet-20250219 | 100.0 | 77.8 | 80.6 | 72.2 | 61.1 | 52.8 | 50.0 | 52.8 | 44.4 | 34.4 |  |
| deepseek-chat-v3-0324:free | 87.5 | 61.1 | 69.4 | 52.8 | 52.8 | 52.8 | 50.0 | 55.6 | 55.6 | - |  |
| gemma-3-27b-it:free | 87.5 | 44.4 | 50.0 | 41.7 | 33.3 | 38.9 | 33.3 | 25.0 | 30.6 | - |  |
| gemini-2.5-flash-preview | 62.5 | 63.9 | 69.4 | 61.1 | 47.2 | 44.4 | 47.2 | 44.4 | 58.3 | 53.1 |  |
| gemini-2.0-pro-exp-02-05:free | 87.5 | 91.7 | 80.6 | 72.2 | 61.1 | 52.8 | 41.7 | 47.2 | 41.7 | 37.5 |  |
| llama-4-maverick:free | 100.0 | 56.0 | 50.0 | 52.0 | 48.0 | 48.0 | 46.2 | 44.0 | 32.0 | 36.4 |  |
| llama-4-scout:free | 62.5 | 52.0 | 50.0 | 36.0 | 32.0 | 40.0 | 36.0 | 16.0 | 24.0 | 27.3 |  |
| grok-3-beta | 75.0 | 72.2 | 63.9 | 55.6 | 55.6 | 52.8 | 58.3 | 55.6 | 63.9 | 58.3 |  |

DeepSeek R1 0528优势明显：
  * 目前性能几乎**全面优于**Qwen 3 235B A22B等其他开源模型
  * 支持**128k上下文长度**
  * 幻觉得到了有效控制：根据DeepSeek官方的[发布公告](https://api-docs.deepseek.com/zh-cn/news/news250528)，更新后的模型在改写润色、总结摘要、阅读理解等场景中，幻觉率降低了 45～50% 左右

因此，笔者将Arch Linux for Loong64 Dev Helper (Reasoning)的后端模型更改为DeepSeek R1 0528。

由于更新后的DeepSeek R1 0528模型性能十分强大，笔者现在**推荐在遇到复杂问题时使用Arch Linux for Loong64 Dev Helper (Reasoning)模型**。

### Open WebUI基本配置

笔者在16核16 GB内存的AMD Zen 3虚拟机（CLab）上部署了Open WebUI，笔者并没有使用Docker，而是直接通过`pacman`从`archlinuxcn`安装了Open WebUI。

```bash
sudo pacman -S open-webui
```

安装完成后，还需要启用Open WebUI的服务：

```bash
sudo systemctl enable open-webui.service --now
```

Open WebUI默认使用`0.0.0.0:8080`作为地址，因此直接可以通过`http://<IP>:8080`在其他设备上访问。

首次访问时会提示注册管理员账号并设置密码。随后，可以点击头像，进入管理员设置界面（或者直接访问`http://<IP>:8080/admin/settings`），通过`设置 -> 管理OpenAI API连接 -> +`添加API连接，输入API Key和API URL并添加所需要的模型列表（也可以不添加，使用自动获取的模型列表），完成之后点击`保存`，即可完成API连接的设置。

在`界面`选项中，可以设置用于总结对话标题、生成检索查询、生成联网搜索关键词等工作的任务模型。任务模型不适合用推理模型，因此笔者选择了`DeepSeek V3 0324`。

### RAG配置

找到`文档`进行设置。由于笔者的机器没有GPU，性能受限，只能在效果和速度之间进行权衡。笔者发现嵌入模型如果选择更准确、更受欢迎的`BGE-m3`，在面对**大量文档**的检索时会**慢**到不可接受，因此笔者最后还是回退到了默认的`sentence-transformers/all-MiniLM-L6-v2`模型，这一模型的参数量仅有**22 M**（0.022 B），速度快，效果尚可。

而有关检索的设置，笔者启用了混合检索模式，使用小模型`BAAI/bge-reranker-base`作为**重排序**模型（同样是因为效果更好的`BAAI/bge-reranker-v2-m3`性能开销不可接受），设置`块大小 (Chunk Size)`为`1024`，`块重叠 (Chunk Overlap)`为`128`，`Top K`为`50`，`Top K Reranker`为`20`，并设置`Relevance Threshold`为`0.1`，这样的设置虽然有所妥协，效果基本上也能接受。

这样的设置含义是：
* `块大小 (Chunk Size)`：每个文档块大小，设置为`1024`，即每个块有1024个Token
* `块重叠 (Chunk Overlap)`：每个文档块重叠的大小，设置为`100`，即每个块与前一个块的重叠大小为100
* `Top K`：检索时返回的文档数量，设置为`50`，即检索选择50个（嵌入向量余弦相似度最大的）文档
* `Top K Reranker`：重排序时返回的文档数量，设置为`20`，即重排序检索返回的文档，将前20个文档传递给LLM作为上下文
  * 虽然重排序模型是可选的，即使没有重排序模型，嵌入模型也会对检索的文档按照匹配度进行排序
  * 但是这一匹配度只是基于文本**嵌入向量**的**余弦值**简单得出，在真实场景中往往**不够准确**
  * 重排序可以将更准确的文档排在前面并排除劣质的检索结果
  * `Relevance Threshold`：检索时的相关性阈值，设置为`0.1`，即检索到的文档的相关性余弦值大于0.1才会被返回

经过测试，即使是添加了这样简单的重排序模型，也可对检索的准确率带来显著提升。（似乎收益比使用更强大的`BGE-m3`作为嵌入模型但不添加重排序模型的效果要好）对于块大小似乎不宜设置得更大，否则检索速度会严重降低。

### 添加文档

点击UI左侧的`工作空间`，点击上方的`知识库`（或者直接访问`http://<IP>:8080/workspace/knowledge`），点击右上角的`+`，按照要求补充信息，并上传文档即可。笔者建立了两个相关知识库：

* Arch Linux for Loong64
  * 笔者亲自撰写的数万字的Arch Linux for Loong64开发文档，包括自己的相关博客和GitHub上的Wiki文档
  * 龙芯公开的手册：[龙芯架构参考手册 - 卷一](https://github.com/loongson/LoongArch-Documentation/releases/latest/download/LoongArch-Vol1-v1.10-CN.pdf)
* ArchWiki
  * Arch Linux上游的ArchWiki的全部内容（获取自`arch-wiki-docs`包）
  * 已弃用，建议使用联网搜索功能替代

### 创建模型

点击UI左侧的`工作空间`，随后点击上方的`模型`（或者直接访问`http://<IP>:8080/workspace/models`），点击右上角的`+`，补充信息并创建用于Arch Linux for Loong64助手的模型。笔者创建了4个模型：

* Arch Linux for Loong64 Dev Helper
  * 简称`Dev Helper`
  * 回答有关Arch Linux for Loong64维护的问题
  * 使用`DeepSeek V3 0324`作为LLM
  * 可访问`Arch Linux for Loong64`知识库
  * 系统提示词为：
    ```
    你是一个帮助Arch Linux for Loong64维护者工作的助手，在Arch Linux for Loong64知识库中有答案时优先根据知识库回答，如果知识库中没有答案但是有检索得到的上下文参考时可以参考可信较高的检索内容（不要参考劣质****博客），否则结合自身知识（给出结合自身知识的说明），并按照你认为最合理的方式回答
    ```
* Arch Linux for Loong64 Dev Helper (Reasoning)
  * 简称`Dev Helper (Reasoning)`
  * 回答有关Arch Linux for Loong64维护的问题
  * 使用`DeepSeek R1 0528`作为LLM
  * 可访问`Arch Linux for Loong64`知识库
  * 系统提示词为：
    ```
    你是一个帮助Arch Linux for Loong64维护者工作的助手，在Arch Linux for Loong64知识库中有答案时优先根据知识库回答，如果知识库中没有答案但是有检索得到的上下文参考时可以参考可信较高的检索内容（不要参考劣质****博客），否则结合自身知识（给出结合自身知识的说明），并按照你认为最合理的方式回答
    ```
* Arch Linux for Loong64 Dev Helper VL
  * 简称`Dev Helper VL`
  * 多模态模型，可用于拍屏/截图日志分析，也可以辅助分析异常显示的界面等，回答有关Arch Linux for Loong64维护的问题（仅建议用于多模态用途）
  * 使用`Llama 4 Maverick`作为LLM
  * 可访问`Arch Linux for Loong64`知识库
  * 系统提示词为：
    ```
    你是一个帮助Arch Linux for Loong64维护者工作的助手，在Arch Linux for Loong64知识库中有答案时优先根据知识库回答，如果知识库中没有答案但是有检索得到的上下文参考时可以参考可信较高的检索内容（不要参考劣质****博客），否则结合自身知识（给出结合自身知识的说明），并按照你认为最合理的方式回答。作为一个多模态模型，你需要准确识别用户可能发送的截图、拍屏，并精准完整地提炼信息。
    ```
* ~~Arch Linux for Loong64 Generic Helper (Beta)~~（已下架）
  * 简称`Generic Helper`
  * 更通用的Arch Linux for Loong64助手（Beta），除Arch Linux for Loong64外还拥有ArchWiki的知识（但检索较慢且效果可能不如启用网页搜索后的开发助手）
  * 使用`DeepSeek V3 0324`作为LLM
  * 可访问`Arch Linux for Loong64`和`ArchWiki`知识库
  * 系统提示词为：
    ```
    你是一个帮助Arch Linux或者Arch Linux for Loong64维护者及用户的助手（没有特殊说明架构的时候假定架构为Loong64）。在知识库中有答案时优先根据知识库回答，注意有关Loong64架构的问题应当优先按照Arch Linux for Loong64的文档说明和社区习惯回答；如果知识库中没有答案但是有检索得到的上下文参考时可以参考可信较高的检索内容（不要参考劣质****博客）；否则结合自身知识（给出结合自身知识的说明），并按照你认为最合理的方式回答
    ```

创建完成后，将这些模型设置为`公开`，或者对Arch Linux for Loong64的用户组开放。

## 使用方法

* 如果主要目标是知识的检索与查询，不涉及太复杂的推理，可以使用`Dev Helper`模型，避免深度的推理耗费大量时间。
* 如果遇到需要**深度推理**的问题，比如代码的辅助编写、报错原因的排查、工具设计架构的规划等，可以使用`Dev Helper (Reasoning)`模型进行分析。
* 如果遇到不便于分析日志的**拍屏、截图**等信息形式，可以使用`Dev Helper VL`模型进行分析。
  * 在输入框中输入`@`即可在对话中切换模型，也可以通过左上角模型栏UI切换模型。
  * 由于`Llama 4 Maverick`逻辑能力与代码能力均较差，建议仅使用该模型提取多模态信息，分析工作仍然交给`Dev Helper`与`Dev Helper (Reasoning)`模型来完成。
* `Generic Helper (Beta)`模型的效果并不理想，检索速度较慢，且准确性一般，已**不再开放使用**。
  * 建议使用`Dev Helper`与`Dev Helper (Reasoning)`模型并开启**网页搜索**功能替代。
    * 网页搜索功能目前更强大：基于Google或者DuckDuckGo的搜索引擎并使用大模型生成搜索关键词。
    * 启用网页搜索时，首先会将上下文传递给DeepSeek V3 0324模型处理，**生成搜索的关键词**，然后使用这些关键词在Google或者DuckDuckGo上进行搜索。
      * 这样可以更准确地找到相关内容，也增加了搜索的灵活性。
      * 可以通过在提示词中加入对搜索内容的要求备注来引导模型生成更准确的搜索关键词。
      * 例如：`Mold适合在哪些场景下使用？（参考英文文档）`，这里通过括号备注`参考英文文档`来引导模型生成更准确的搜索关键词，要求搜索关键词生成模型指定更合适的搜索范围。
    * 网页检索完成后，模型会将搜索结果与知识库作相同的RAG处理，提取出相关的内容，并将其作为上下文传递给模型进行回答。
  * **ArchWiki非常著名**，很容易被搜索引擎收录。（相比之下Arch Linux for Loong64的文档则很难直接通过搜索引擎找到）
  * 现代搜索引擎使用的检索模型远远比笔者本地部署的要强大，再加上搜索关键词生成模型的优化，更容易找到正确的内容，在合适的提示词下可能给出比笔者特意建立的ArchWiki检索系统更准确的答案。

建议一般情况下按需使用`Dev Helper`与`Dev Helper (Reasoning)`（可按照实际需要开启网页搜索功能），需要多模态分析拍屏或者截图时使用`@`在对话中切换暂时切换到`Dev Helper VL`模型提取日志等信息，但后续分析仍然使用推荐的`Dev Helper`与`Dev Helper (Reasoning)`模型。

需要注意，即使有了RAG加持，**模型的回答仍然可能不准确**，建议用户对模型的回答进行事实验证。由于输出内容中会包含检索引文，用户可以自行检索引文（或访问相应的文档网页）来验证模型的回答。

## 效果展示

|[![#~/img/llm/arch-linux-for-loong64-helper.webp](/img/llm/arch-linux-for-loong64-helper.webp)](/img/llm/arch-linux-for-loong64-helper.webp)|
|:----:|
|Arch Linux for Loong64 Dev Helper|

|[![#~/img/llm/arch-linux-for-loong64-helper-reasoning.webp](/img/llm/arch-linux-for-loong64-helper-reasoning.webp)](/img/llm/arch-linux-for-loong64-helper-reasoning.webp)|
|:----:|
|Arch Linux for Loong64 Dev Helper (Reasoning)|

|[![#~/img/llm/arch-linux-for-loong64-helper-vl.webp](/img/llm/arch-linux-for-loong64-helper-vl.webp)](/img/llm/arch-linux-for-loong64-helper-vl.webp)|
|:----:|
|Arch Linux for Loong64 Dev Helper VL|

|[![#~/img/llm/arch-linux-for-loong64-helper-generic.webp](/img/llm/arch-linux-for-loong64-helper-generic.webp)](/img/llm/arch-linux-for-loong64-helper-generic.webp)|
|:----:|
| ~~Arch Linux for Loong64 Generic Helper (Beta)~~ （已下架）|

|[![#~/img/llm/answer1-arch-linux-for-loong64-helper-lossless.webp](/img/llm/answer1-arch-linux-for-loong64-helper-lossless.webp)](/img/llm/answer1-arch-linux-for-loong64-helper-lossless.webp)|
|:----:|
|回答效果示例|

|[![#~/img/llm/answer2-arch-linux-for-loong64-helper-lossless.webp](/img/llm/answer2-arch-linux-for-loong64-helper-lossless.webp)](/img/llm/answer2-arch-linux-for-loong64-helper-lossless.webp)|
|:----:|
|回答效果示例|

|[![#~/img/llm/answer3-arch-linux-for-loong64-helper-lossless.webp](/img/llm/answer3-arch-linux-for-loong64-helper-lossless.webp)](/img/llm/answer3-arch-linux-for-loong64-helper-lossless.webp)|
|:----:|
|回答效果示例|
