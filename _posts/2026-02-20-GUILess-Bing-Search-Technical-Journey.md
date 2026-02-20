---
layout:       post
title:        从 urllib 到 Qt WebEngine：在无头环境中获取正确 Bing 搜索结果
subtitle:     GUI-Less Bing Search 开发中解决搜索结果异常问题的技术历程
date:         2026-02-20
author:       wszqkzqk
header-img:   img/llm/ai-bg-lossless.webp
catalog:      true
tags:         Python PySide Qt 开源软件 搜索引擎 LLM
---

## 前言

在[上一篇文章](https://wszqkzqk.github.io/2026/02/20/GUILess-Bing-Search-Introduction/)中，笔者介绍了 [GUI-Less Bing Search](https://github.com/wszqkzqk/GUILessBingSearch) 项目——一个在无头环境中通过 HTTP API 搜索 Bing 的工具。

在开发这个项目的初期，为了保持轻量，笔者最初尝试使用 Python 的 `urllib` 直接请求 Bing 搜索页面。然而，在实际测试中，笔者遇到了一个奇怪的现象：Bing 返回的搜索结果与搜索词完全无关。经过一系列排查，最终笔者切换到了 Qt WebEngine 才得以解决这一问题。

本文将详细展开这段技术历程：为什么朴素的 HTTP 请求方案行不通、问题的根因究竟在哪里，以及如何在完全无头的 offscreen 环境中适配浏览器引擎以获取正确的搜索结果。

## 第一版：urllib + HTMLParser

笔者最初的实现很简洁——只使用 Python 标准库，零外部依赖：

```python
from urllib.request import Request, urlopen
from html.parser import HTMLParser

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 ... Chrome/131.0.0.0 ...",
    "Accept": "text/html,...",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

req = Request(url, headers=headers, method="GET")
with urlopen(req, timeout=15) as resp:
    html = resp.read().decode("utf-8")
```

解析端使用了一个自定义的 `HTMLParser` 子类，通过跟踪 `li.b_algo` → `h2` → `a` 的标签嵌套状态来提取标题、链接和摘要，最终实现一个完整的基于 HTML 解析的搜索服务。

这个方案代码不过两三百行，无需任何外部依赖，看上去非常理想。初期测试用的是一些常见查询词（"Python tutorial" 之类），结果都是正确的，一切看似正常。

## 令人困惑的异常现象

问题在笔者扩大测试范围后出现了。当使用更加具体或小众的查询词时，Bing 返回的 HTML **结构完全正确**（`li.b_algo`、`h2 a` 等 DOM 元素一应俱全），但**内容与搜索词毫无关系**——笔者搜索某个技术名词，拿到的却是美食推荐或娱乐新闻。

更令人摸不着头脑的是，这种行为具有**随机性**和**选择性**：

- 同一个查询词，有时返回正确结果，但更多时候返回无关内容
- 越是小众、越是特定的查询，错误率越高
- 很常见、很通用的热门搜索词反而总是正确的
- 在 `cn.bing.com` 上问题尤为突出

由于假结果的 HTML 结构与真结果完全一致，仅从解析层面根本无法区分。笔者最初怀疑是解析代码的 bug，反复检查了 `HTMLParser` 的状态机逻辑后排除了这个可能。直接将返回的完整 HTML 保存下来用浏览器打开，确认了 HTML 中的搜索结果内容本身就是错误的——问题出在 Bing 返回的**内容**上，而不是笔者的**解析**。

## 排除假设

笔者在接下来的排查中逐步排除了多个假设。

### User-Agent

第一个想法是 User-Agent 可能与浏览器不同，导致 Bing 认为该环境无法加载正常结果。笔者尝试了：

- 完整的 Edge UA 字符串（包含 `Edg/131.0.0.0` 标识）
- 添加 `Sec-CH-UA`、`Sec-CH-UA-Mobile`、`Sec-CH-UA-Platform` 等客户端提示头
- 添加 `DNT: 1`、`Upgrade-Insecure-Requests: 1` 等常见头部

**结果全部无效。** 无论 HTTP 头部怎么构造，垃圾结果的问题依然存在。

### Cookie 问题？

然后笔者怀疑是 Cookie 相关的问题——也许 Bing 需要某些特定的 Cookie 才能返回正确结果。尝试了：

- 手动从浏览器中提取 `_U` Cookie 并注入
- 使用 `MUID` 等额外 Cookie
- 完全不带任何 Cookie

**结果：Cookie 对结果正确性没有影响。** 注入 Cookie 可以解决某些中国大陆网络环境下的重定向问题，但并不能解决搜索结果本身为垃圾内容的问题。

### 缺少 `form=QBLH` 参数？

在排查过程中，笔者注意到通过浏览器在 Bing 首页提交搜索时，URL 中会附带一个 `form=QBLH` 参数。笔者一度怀疑这个参数是服务端用来区分正常搜索和直接 URL 访问的标志。

**这一猜想后来同样被证伪了。** 当其他所有问题解决后，不带 `form=QBLH` 的直接 URL 访问一样能够获取正确结果。之前失败是因为更根本的原因尚未解决。

## TLS 指纹：真正的决定因素

在排除了以上所有 HTTP 层面的因素后，笔者将疑点转向了更底层——**TLS 握手**。

现代的 HTTPS 连接在建立时，客户端会在 TLS Client Hello 消息中发送一系列参数：支持的密码套件列表、TLS 扩展、椭圆曲线列表、签名算法等。这些参数的组合构成了一个"TLS 指纹"（业界常用 JA3/JA4 等哈希方法来标识）。

关键在于：**不同的 TLS 实现产生的指纹差异显著。** Python 标准库使用的 `ssl` 模块（基于 OpenSSL）产生的 TLS 指纹与 Chrome/Chromium 使用的 BoringSSL 有着本质的不同。服务端可以在 TLS 握手阶段——甚至在读取到第一个 HTTP 字节之前——就判断出这个连接来自什么样的客户端。

换句话说，**Python 的 `urllib`/`requests` 从 TLS 层就已经被标记为非浏览器客户端了**。后续无论在 HTTP 层怎么模拟都无济于事。

## 迁移到 Qt WebEngine

定位到根因后，解决方案就很明确了：使用一个**真正的浏览器引擎**，让 TLS 握手、HTTP 交互和 JavaScript 执行都使用与 Chrome 一致的实现。

笔者选择了 **Qt WebEngine**（通过 PySide6 使用），原因如下：

- **内嵌完整的 Chromium 引擎**：TLS 行为与 Chrome 完全一致
- **支持 offscreen 模式**：Qt 提供了 `QT_QPA_PLATFORM=offscreen` 参数，无需 X11/Wayland 即可运行
- **PySide6 可通过 pip 安装**：部署相对方便
- **完善的 JavaScript 执行环境**：可以直接在页面上下文中运行 JS 提取 DOM

切换到 Qt WebEngine 后，**之前无论怎么调整都无法正确获取的搜索结果，立刻全部恢复正常了**。这验证了 TLS 指纹确实是 Bing 对不正确的结果的唯一决定性因素。

## Offscreen 环境的适配

使用真实的浏览器引擎解决了 TLS 层面的问题，但在 Qt 的 offscreen 模式下运行 Chromium 还需要处理一系列环境细节。这些细节在有桌面环境的情况下不会出现，但在 offscreen 模式下可能影响页面的正常渲染或导致搜索结果异常。

### 屏幕尺寸为零

在 offscreen 模式下，所有与屏幕相关的 JavaScript 属性都返回 0：

```javascript
screen.width       // 0
screen.height      // 0
window.outerWidth  // 0
window.innerWidth  // 0
// ... 全部为 0
```

零尺寸的屏幕对于正常运行的浏览器来说不合理。工具通过在 `DocumentCreation` 阶段注入 JavaScript，将这些属性覆盖为常见的值（如 1920×1080）：

```javascript
var _W = 1920, _H = 1080;
['width','availWidth'].forEach(function(k){
    Object.defineProperty(screen, k, {get: () => _W});
});
// ... 对 screen.height, window.outerWidth 等属性做相同处理
```

### `navigator.webdriver` 属性

在 Qt WebEngine 的无头模式下，浏览器的 `navigator.webdriver` 属性默认会返回 `true`，这容易让服务端误以为这是一个非交互式的脚本环境。工具在 `DocumentCreation` 阶段将其覆盖：

```javascript
Object.defineProperty(navigator, 'webdriver', {get: () => false});
```

### `window.chrome` 对象缺失

真正的 Chrome/Chromium 浏览器会暴露一个 `window.chrome` 对象，包含 `chrome.runtime`、`chrome.app` 等属性。在 Qt WebEngine 的 offscreen 模式下，这个对象可能不存在。工具为其创建了一个最小化的存根：

```javascript
if (!window.chrome) window.chrome = {};
if (!window.chrome.runtime) {
    window.chrome.runtime = {connect: function(){}, sendMessage: function(){}};
}
if (!window.chrome.app) window.chrome.app = {isInstalled: false};
```

### User-Agent 清理

Qt WebEngine 的默认 User-Agent 中包含一个 `QtWebEngine/x.y.z` 标记，例如：

```
Mozilla/5.0 (X11; Linux x86_64) ... QtWebEngine/6.10.2 Chrome/134.0.0.0 ...
```

这个标记会立刻暴露客户端是一个嵌入式浏览器而非独立的 Chrome。工具通过正则替换将其移除：

```python
clean_ua = re.sub(r"\s*QtWebEngine/\S+", "", profile.httpUserAgent())
```

需要注意的是，除了移除 `QtWebEngine` 标记外，UA 中的其他部分（平台、Chrome 版本号等）**保持不变**。这是因为 UA 需要与 TLS 指纹保持一致——如果 TLS 指纹表明客户端是 Linux 上的 Chromium，但 UA 却声称自己是 Windows 上的 Edge，这种不一致反而可能产生更多问题。

**保持环境信息的真实性和一致性，比全面模拟更重要。**

### 参数冲突

在排查过程中，笔者发现了一个有趣的参数冲突。当同时传入 `ensearch=1`（请求国际搜索结果）和 `setmkt=zh-CN` / `setlang=zh-CN`（强制中文区域）时，`cn.bing.com` 会返回垃圾结果。单独使用任何一个参数都正常，但两者的组合是矛盾的——"我要国际搜索结果"和"我在中国区"是相互冲突的信号。

正常的浏览器不会同时发送这些冲突的参数。这个发现本身虽然不是核心问题，但帮助笔者理解到：**服务端对请求的"合理性"有着细致的判断**，任何不一致的信号都可能触发异常的响应。

## 不需要做的事情

在排查过程中，笔者也测试了很多最终证实**不需要**的措施：

| 不需要的措施 | 说明 |
| :---: | :---: |
| 先访问 Bing 首页"预热" | 直接通过 URL 访问搜索页面即可 |
| Cookie 存在与否 | 全新的空 Profile 就能获取正确结果 |
| `form=QBLH` 参数 | 直接 URL 访问不需要此参数 |
| 模拟 Edge 浏览器 | 干净的 Chromium UA 就足够了 |
| 模拟 Windows 系统 | Linux 平台信息完全没有问题 |
| 注入 `navigator.plugins` | 空的 plugins 列表不影响结果 |
| 注入 `navigator.languages` | 默认的语言列表就可以 |
| WebGL 渲染信息 | offscreen 环境下 WebGL 不可用不影响结果 |

这个清单说明了问题的边界在哪里，也避免了在代码中引入不必要的复杂度。

## 最终方案的最小有效集合

经过反复测试和对照实验，笔者总结出在 offscreen 环境中正确获取 Bing 搜索结果所需的**最小改动集合**：

1. **使用真实的 Chromium 引擎**（Qt WebEngine）——解决 TLS 指纹问题，这是最核心的一步
2. **覆盖 `navigator.webdriver`**——避免被误判为非交互式环境
3. **覆盖屏幕尺寸相关属性**——使 offscreen 环境的屏幕参数合理化
4. **提供 `window.chrome` 存根**——补充 Chromium 浏览器预期存在的对象
5. **清理 User-Agent**——移除 `QtWebEngine` 标记，保持其余信息真实

五项改动，每一项都有明确的技术原因，且缺一不可。其中第 1 项是根本性的（解决了 95% 的问题），第 2~5 项是环境适配层面的细节完善。

## 请求频率控制

除了上述的客户端环境适配之外，合理的请求频率控制也是正确使用工具的重要组成部分。工具内置了可配置的 `SEARCH_INTERVAL`（默认 1 秒）参数，每次搜索之间会等待至少这么长的时间。此外，还在基础间隔之上叠加了 0~50% 的**随机抖动**，使得请求的时间分布更加自然，避免以固定间隔访问对服务器造成集中的访问压力。

```python
if SEARCH_INTERVAL > 0:
    elapsed = time.monotonic() - self._last_search_time
    jitter = random.uniform(0, SEARCH_INTERVAL * 0.5)
    required = SEARCH_INTERVAL + jitter
    if elapsed < required:
        delay_ms = int((required - elapsed) * 1000)
        QTimer.singleShot(delay_ms, self._start_search)
        return
```

## 小结

回顾整个开发历程，从最初几百行的 `urllib` + `HTMLParser` 方案，到最终基于 Qt WebEngine 的完整实现，看似简单的问题其实并不简单。

- **TLS 指纹是 HTTPS 通信中比 HTTP 头部更底层、也更难模拟的身份标识**。使用 Python 的 `urllib`/`requests` 库——无论怎样精心构造 HTTP 头部——都无法产生与真实浏览器一致的 TLS 特征。唯一可靠的解决方案是使用真正的浏览器引擎。
- **offscreen 环境有其特殊性**。即使使用了真实的浏览器引擎，在无头模式下运行时，一些通常在桌面环境中理所当然的细节（屏幕尺寸、浏览器对象）需要显式地适配。
- **一致性比刻意模拟更重要**。与其试图将 Linux 上的 Chromium 模拟成 Windows 上的 Edge，不如保持所有信息的真实性和一致性——真实的平台信息、真实的 Chrome 版本号、只移除不应该出现的 `QtWebEngine` 标记。
- **排除法同样有价值**。知道什么是不需要做的（首页预热、Cookie 依赖、特定参数、模拟平台等），与知道什么是必要的同样重要。它简化了最终方案，也避免了无意义的复杂度。

项目仓库：[**GitHub - wszqkzqk/GUILessBingSearch**](https://github.com/wszqkzqk/GUILessBingSearch)
