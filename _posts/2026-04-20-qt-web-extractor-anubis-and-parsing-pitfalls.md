---
layout:       post
title:        Qt Web Extractor：适配 Anubis 并与 Qt HTML 解析斗智斗勇
subtitle:     扩展 Qt Web Extractor 的适用范围并增加支持提取的网页类型
date:         2026-04-20
author:       wszqkzqk
header-img:   img/llm/ai-bg-lossless.webp
catalog:      true
tags:         Python Qt PySide 开源软件 网页提取
---

## 背景

[Qt Web Extractor](https://github.com/wszqkzqk/qt-web-extractor) 最近遇到了两个比较复杂的问题：一个是 Anubis 反爬虫的 PoW 挑战页，另一个是 Qt `QTextDocument` 解析大页面 HTML 时的内存失控。排查下来发现，前者的修复其实非常简洁；后者虽然还没彻底解决，但恰好被前者的修复方式给自然缓解了。

## Anubis：其实适配很简单

### 现象

笔者在测试提取 [gitlab.winehq.org/wine/wine](https://gitlab.winehq.org/wine/wine) 时，发现返回的总是这段内容：

> Making sure you're not a bot!
>
> Loading...
>
> You are seeing this because the administrator of this website has set up Anubis to protect the server...

拿不到后面的真实 GitLab 内容。

### 分析

Anubis 是一种基于 PoW（Proof-of-Work）的反爬虫中间件。服务器向浏览器下发一个 SHA-256 计算挑战，客户端需要在本地通过 JavaScript brute-force 找出一个满足难度要求的 nonce，完成后通过 cookie 才能访问真实页面。

跟 Cloudflare 那种复杂的指纹识别和行为分析不同，Anubis 的核心逻辑其实非常直白：**它就是要求你付出算力**。对于真正的浏览器来说，这意味着在本地执行几秒的 JavaScript 计算。对于爬虫来说，这意味着大规模抓取的成本会急剧上升。

而 Qt Web Extractor 本身就是一个完整的 Chromium headless 环境，有完整的 JavaScript 引擎，执行 PoW 计算完全不在话下。实际上笔者观察过，Anubis 的 `main.mjs` 在 Qt WebEngine 中可以正常执行，PoW 计算和后续重定向都没有问题。

真正的问题在于**提取器和 Anubis 的工作流没有对齐**。

Qt Web Extractor 的流程是：

1. `page.load(url)` 加载页面
2. 等 `loadFinished` 信号
3. `loadFinished` 后启动一个 2 秒的单发定时器
4. 定时器触发后，注入 JavaScript 递归遍历 DOM，序列化成 HTML
5. `_finish()` 设置 `settled = True`，提取结束

Anubis 挑战页的初始 HTML 很小（约 4KB），`loadFinished` 在几百毫秒内就会触发。但此时页面上的 `main.mjs` 才刚刚开始执行 PoW 计算，整个计算过程需要几秒到十几秒。计算完成后 JavaScript 调用 `window.location.replace()` 重定向到真实页面，这会触发新的 `loadStarted` → `loadFinished` 周期。

但原来的代码只连接了 `loadFinished`，没有连接 `loadStarted`。所以 2 秒定时器触发后，提取器拿到当时的 DOM（挑战页），调用 `_finish()`，`settled = True`。这时候 Anubis 的 PoW 可能还在进行，甚至可能尚未启动。等几秒后 PoW 计算完成、页面重定向到真实内容、新的 `loadFinished` 触发——但 `settled` 已经是 True，所有后续处理都被跳过。真实页面就这样被忽略了。

也就是说，PoW 能够正常计算完成，重定向也会正常执行，但提取器在重定向触发之前就已经 settled，后续的真实内容完全没有机会进入提取流程。

### 修复

修复的思路是：既然提取器本身就能正常执行 PoW，那我们只需要**等待计算完成**即可。

`window.location.replace()` 会触发 `loadStarted`，这是感知自刷新的最直接方式。笔者在 `_WebPage` 中加了对 `loadStarted` 的连接：

```python
self.loadFinished.connect(self._on_load_finished)
self.loadStarted.connect(self._on_load_started)
```

```python
def _on_load_started(self):
    self._stability_timer.stop()
```

Anubis 完成 PoW 触发重定向时，旧的 stability timer 会被停止。随后真实页面加载完成触发新的 `loadFinished`，重新启动 2 秒倒计时，在真实页面稳定后才提取。

看 commit 记录就知道了——`e993fec` 这个 commit 只改了 5 行代码：加了一个 `_on_load_started` 方法、连接了 `loadStarted` 信号、修正了一个空白字符。Anubis 这种看似强力的反爬虫，对于一个本身就有完整 Chromium 内核的提取器来说，适配成本相当低。它不像 Cloudflare 那样需要绕过复杂的指纹识别，其核心只是要求客户端执行一段 JavaScript 计算。

修复后的行为是**概率性**的，取决于 PoW 计算时间和网络延迟的相对关系：

- 如果 PoW 在 2 秒定时器触发前完成，重定向发生时 timer 会被 `loadStarted` 重置，最终能成功提取真实页面。对于 winehq.org 这种难度较低的配置（PoW 约 2-3 秒），这种情况出现的概率很高，所以"大多数 Anubis 已经能够正常处理"。
- 如果 PoW 超过 2 秒，定时器先触发，提取器 settled，后续真实页面被忽略。kernel.org 的部分配置难度为 5，PoW 可能需要 5-8 秒，这种情况下会提取到挑战页。

笔者也尝试过延长 stability delay 到 5 秒或更长，让 PoW 有更充分的时间完成。但这个方向很快就被放弃了，原因跟下面要说的内存问题直接相关。

## Qt HTML 解析的内存失控

### 现象

在测试提取 [Linux 内核的一个大型 merge commit](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=cdd4dc3aebeab43a72ce0bc2b5bab6f0a80b97a5) 时，Python 进程在提取阶段被系统 OOM killer 杀掉。同一个页面在 Chrome 和 Firefox 中打开完全正常，内存占用也就几百 MB。但通过 Qt Web Extractor 提取时，内存占用一路飙升到 30GB 以上，直到耗尽。

### 定位

问题出在 `QTextDocument.setHtml()`。

Qt Web Extractor 的提取管线中，HTML 到 Markdown 的转换依赖 `QTextDocument`：

```python
doc = QTextDocument()
doc.setHtml(html)
md = doc.toMarkdown()
```

这个 commit 页面的 diff 内容非常大，cgit 用 `<table>` 展示 diff，每行一个 `<tr>`。浏览器渲染这种页面没有问题，因为浏览器的光栅化和布局是流式的。但 `QTextDocument` 是富文本处理类，内部会把 HTML 转换成块结构、表格结构和格式对象。对于包含数万行表格的代码 diff 页面，`setHtml()` 内部需要为每个单元格分配格式对象和布局元数据，内存膨胀非常严重。

笔者通过诊断脚本确认了规模：

```
body.innerHTML.length = 2057483
outer_html_len = 2058590
inner_text_len = 1171958
```

2MB 的原始 HTML 在 `QTextDocument` 中膨胀到 30GB 以上，这是 Qt 解析器的问题。`QTextDocument` 的设计目标是处理编辑器量级的富文本，不是作为通用的任意大小 HTML 解析器。

### 尝试与回退

笔者一度在 `_text_from_html` 中加入了大小阈值判断，对大页面降级为 `innerText` 提取，绕过 `QTextDocument`。但这样做其实是在掩盖问题，而不是解决它。而且 `innerText` 丢失了 Markdown 的超链接和表格结构，输出质量明显下降。

经过考虑，笔者回退了这个降级修改。2MB 的 HTML 不应该让任何解析器吃掉 30GB 内存，这是 Qt 的问题。在找到更根本的解决方案之前，不应该用降级来掩盖。

### 与大页面内存问题的交叉影响

这里有一个需要说明的情况。kernel commit 这种大页面，真实内容本身就很大（约 2MB HTML），一旦进入 Qt 解析路径就会 OOM。笔者测试过，如果延长 stability delay 到 5 秒或更长，给 Anubis 更充分的时间完成重定向，真实页面被提取后内存会直接爆掉。

保持 2 秒的 delay 反而避免了这个问题。这个巨大的页面在 2 秒内通常无法完成到真实页面的重定向。2 秒定时器触发后，提取器拿到 Anubis 挑战页（只有 4KB，安全），然后 settled。后续即使网络恢复、重定向到真实页面，由于 `settled` 已经是 True，真实大页面永远不会被提取——所以 Qt 解析大页面的 OOM 也永远不会触发。

换句话说，大页面的真实内容因为 Anubis 未完成而被跳过，但这也恰好绕过了 Qt 解析器的内存失控。这不是特意设计的保护机制，而是当前网络环境和 2 秒 delay 共同产生的实际效果。

目前的状态是小页面（如 gitlab.winehq.org/wine/wine）的 Anubis 流程顺畅，大概率能在 2 秒内完成重定向，能正常提取；大页面 Anubis 运算后在 2 秒内通常无法完成页面内容加载，提取到的是挑战页，真实内容拿不到，但至少不会 OOM。

## 内容丢失问题

在排查过程中，笔者还遇到了两个内容提取不完整的问题，修复方式各不相同。

### checkVisibility 的误判

之前的 Shadow DOM flatten JS 中加入了这行：

```javascript
if (node.checkVisibility && !node.checkVisibility()) return '';
```

意图是过滤掉不可见元素。但在某些现代网页中，`checkVisibility()` 会因为计算时机、CSS 动画状态或元素尚未进入 viewport 而返回 `false`，导致可见内容被错误过滤。笔者在测试 [SemiAnalysis Newsletter](https://newsletter.semianalysis.com/p/nvidia-tensor-core-evolution-from-volta-to-blackwell) 的一篇文章时，提取结果大量缺失——正文被全部过滤掉了。

修复是直接移除了这行（commit `948ed7a`）。不可见元素的过滤应该属于内容处理的后续阶段，不应该在 DOM 序列化时做硬拦截。

### DOM 遍历范围的遗漏

另一个问题出在 DOM 序列化的入口点上。原来的代码从 `document.body` 开始遍历：

```javascript
return '<html><body>' + walk(document.body) + '</body></html>';
```

这导致某些页面的 head 内容无法被正确捕获，提取结果异常。笔者在测试 [Google Open Source Blog](https://opensource.googleblog.com/2024/04/introducing-jpegli-new-jpeg-coding-library.html) 的一篇文章时，提取结果几乎只剩一个 `1`——正文结构完全丢失。

修复是将遍历入口改为 `document.documentElement`，并扩展 SKIP 集合以显式排除 `meta`、`link`、`base`、`title` 等标签（commit `8ca4503`）：

```javascript
const SKIP = new Set(['script','style','svg','noscript','template','meta','link','base','title']);
// ...
return walk(document.documentElement);
```

## 总结

目前代码中已提交的修复包括：

- `loadStarted` 信号连接，在导航时重置 stability timer
- 移除了 `checkVisibility` 过滤
- DOM 遍历入口从 `document.body` 改为 `document.documentElement`，并扩展 SKIP 标签集合

stability delay 保持 2 秒不变。Anubis 这种基于 PoW 的反爬虫系统，对于一个本身就有完整 Chromium 内核的 headless 提取器来说，适配成本非常低——它不需要绕过任何复杂检测，只需要等待 PoW 计算完成即可。整个核心修复只有几行代码。

Qt 的 `QTextDocument` 在处理大表格 HTML 时的内存失控，笔者已经确认是 Qt 侧的问题，需要进一步研究是 Qt 版本相关的已知问题，还是特定 HTML 结构触发的边缘情况。在找到可靠的修复或替代方案之前，这是项目的一个已知限制。而当前 2 秒的 delay 配置恰好避免了实际触发这个问题，算是一个意外的平衡。

项目仓库地址：[GitHub · Qt Web Extractor](https://github.com/wszqkzqk/qt-web-extractor)

项目协议：[GPL-3.0-or-later](https://www.gnu.org/licenses/gpl-3.0.html)
