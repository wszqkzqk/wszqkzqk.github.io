---
layout:       post
title:        Qt Web Extractor 多模态 MCP：让 AI 助手看见网页图片
subtitle:     让视觉模型直接看到网页插图
date:         2026-07-23
author:       wszqkzqk
header-img:   img/llm/ai-bg-lossless.webp
catalog:      true
tags:         Python Qt PySide 开源软件 LLM MCP
---

## 背景

之前笔者介绍过 [Qt Web Extractor](https://github.com/wszqkzqk/qt-web-extractor) 的 MCP 支持：`fetch_url` 工具把网页完整渲染后转成干净的 Markdown，交给 Claude Code、OpenCode 这类终端 AI 助手阅读。这套流程用来看文字内容已经很顺，但有一个明显的短板——**模型看不见图片**。

Markdown 里的图片只会以 `![描述](https://xxx/img.png)` 这样的链接形式存在。对纯文本模型来说这不是问题，但现在的主流模型大多具备视觉能力，而技术文章里的架构图、性能曲线、截图往往承载着关键信息。如果 AI 助手只能读到一句 alt text，这些信息实际上就丢了。

所以这次更新，笔者给项目加了一个 `fetch_image` 工具：把图片 URL 通过同一个完整浏览器引擎加载、栅格化，再以 MCP 原生的 image content 返回给模型。AI 助手阅读 `fetch_url` 返回的 Markdown 时，遇到想看的图片链接，直接调用 `fetch_image` 就能看到图。

## 为什么不能直接 HTTP 下载

最朴素的思路是让 AI 助手自己用 HTTP 把图片数据拉下来。这条路在实际场景中走不通，原因和当初做网页提取要用完整浏览器引擎是一样的：

- **会话门槛**。图片资源经常和页面共用同一套防护——Anubis / Cloudflare 人机验证、登录态 Cookie。裸 HTTP GET 拿到的往往是 403 或者一个验证页，而不是图片本身。
- **格式不受控**。服务端返回的可能是 AVIF、SVG、ICO 等格式，而各家视觉模型客户端对输入格式的支持参差不齐，SVG 这种矢量格式更是普遍不被支持。
- **尺寸不受控**。一张 8000px 的原始大图直接喂给模型，既浪费 token 又可能超出客户端的大小限制。

既然项目本身就是一个 headless Chromium，最自然的做法是让浏览器加载图片，再用 canvas 把解码后的位图栅格化成统一的 WebP——浏览器能显示什么，模型就能看到什么，会话、防盗链、格式问题一并解决。并且经过 WebP 压缩和尺寸控制，返回给模型的图片体积也更小、更可控。

## 实现

### 独立的渲染 Profile 与 Cookie 桥接

主提取流程为了速度禁用了图片加载：

```python
s.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, False)
```

所以 `fetch_image` 不能用主 profile，需要单独建一个不禁图的 `QWebEngineProfile`。但完全隔离又会丢掉主会话里已经拿到的 Cookie——比如 Anubis 验证通过后写入的凭证，或者站点的登录态。解决办法是把主 profile 的新 Cookie 实时同步过去：

```python
self._render_profile = QWebEngineProfile()
# fetch_image shares cookies set during extraction.
self._profile.cookieStore().cookieAdded.connect(
    self._render_profile.cookieStore().setCookie
)
```

这样 `fetch_url` 先通过验证拿到 Cookie，`fetch_image` 再取同站的图片时就能直接取到。两个 profile 各自独立、互不干扰，但会话凭证是共享的。

### Canvas 栅格化与尺寸控制

注入的 JavaScript 核心逻辑很直接：拿到解码后的图片，按长边上限 2576px 等比缩放，画到 canvas 上，导出为 data URL：

```javascript
function mount(im) {
  const w = im.naturalWidth, h = im.naturalHeight;
  if (!w || !h) { throw new Error('no intrinsic size'); }
  const scale = Math.min(1, EDGE / Math.max(w, h));
  const c = document.createElementNS('http://www.w3.org/1999/xhtml', 'canvas');
  c.width = Math.max(1, Math.round(w * scale));
  c.height = Math.max(1, Math.round(h * scale));
  c.getContext('2d').drawImage(im, 0, 0, c.width, c.height);
  let data = c.toDataURL('image/webp', 0.8);
  if (data.indexOf('data:image/webp') !== 0) data = c.toDataURL('image/jpeg', 0.8);
  finish(JSON.stringify({data: data, w: c.width, h: c.height}));
}
```

2576px 这个上限取自当前主流模型 API 的高分辨率档位——超过这个尺寸对模型识别没有额外收益，纯属浪费。WebP 质量 0.8 在体积和清晰度之间是个不错的平衡；按规范，`toDataURL` 遇到不支持的格式时会静默回退成 PNG，代码会检查返回的 data URL 头部，不是 WebP 就改用 JPEG。SVG 在这里也被顺带处理了：`drawImage` 会把它栅格化成点阵图，无论原始格式是 SVG、AVIF 还是 ICO，模型收到的都是可以直接查看的图片。Python 侧再对解码后的字节数设一道 16MB 的防御性上限，防止异常输出撑爆内存。

返回给 MCP 客户端的结果遵循协议规范，image content 和一段文字说明一起返回：

```json
{
    "content": [
        {"type": "image", "data": "<base64>", "mimeType": "image/webp"},
        {"type": "text", "text": "Image fetched: https://xxx/img.png\nFormat: image/webp, 1280x720, 84321 bytes"}
    ],
    "isError": false
}
```

### 三个比较绕的坑

这部分是真正花了时间的地方，记录一下。

**隔离的 JS world。** 注入脚本把结果暂存在 `window.__qr` 里，Python 侧轮询读取。如果脚本跑在页面主 world，页面自身的脚本就能看见甚至伪造这个变量——理论上一个恶意页面可以提前写好假结果骗过提取器。Qt WebEngine 提供了 world 隔离机制，注入脚本统一跑在 `ApplicationWorld`：

```python
_JS_WORLD = QWebEngineScript.ScriptWorldId.ApplicationWorld
```

页面脚本和注入脚本各自拥有独立的全局环境，互不可见。

**隐藏页面的 JS 定时器钳制。** 最初笔者想用 `setInterval` 在页面里自己轮询，等图片解码完成再写入结果。但 Chromium 对后台、隐藏页面的 JS 定时器有激进的钳制策略，offscreen 模式下轮询可能根本不走。解决办法是把驱动权拿回 Qt 侧：JS 只暴露一个单次执行的 `window.__att` 函数，由 Qt 的 500ms 轮询定时器反复调用它并读回结果：

```python
poll_timer.timeout.connect(
    lambda: page.runJavaScript(
        "window.__qr || (window.__att && window.__att(), window.__qr)",
        _JS_WORLD,
        on_probe,
    )
)
```

Qt 定时器不受页面可见性影响，行为完全可控。

**跨重定向的重试。** 图片 URL 也可能被 Anubis 这类验证拦住：第一次加载拿到的是验证页，JS 执行完 PoW 后才自刷新到真实图片。处理方式和之前的网页提取一致——每次 `loadFinished` 都重新注入脚本，让它在新页面上继续尝试；JS 侧的尝试次数预算刻意比 Qt 总超时少 5 秒，这样预算耗尽时，JS 生成的具体错误信息能赶在总超时之前返回。这条错误信息也值得一看：

```
The URL did not return an image (Content-Type: text/html). Page title: "Making sure
you're not a bot!". Page content: ... (If this is a temporary interstitial such as a
bot check, call fetch_image again: the browser session persists across calls and the
check may have completed during this attempt.)
```

它不仅报告了页面标题和正文开头，方便调用方排查，还明确提示模型"会话是持久的，再调一次试试"——往往第二次调用时验证恰好完成，图片就直接出来了。错误信息本身就是写给模型看的，值得认真措辞。

另外还有一个快速失败的判断：Chromium 自带的网络错误页 body 会带 `neterror` 类名，检测到就立刻报错返回，不必干等整个超时时间。

## URL 类型探测

`fetch_image` 引入后，URL 分流从"是不是 PDF"变成了"PDF / 图片 / 网页"三类，`detect_pdf_url` 相应重构成了 `detect_url_kind`。最初的实现是后缀快速路径加 HEAD 请求兜底，但很快发现顺序上有问题。

原来的逻辑是**先看后缀**：URL 以 `.png` 结尾就直接判定为图片，路由进 `fetch_image` 的完整渲染流程。然而后缀是会撒谎的——不少站点看似指向图片的路径，实际返回的是 HTML（比如需要登录跳转的图片页，或者图床那种点进去是展示页而不是图片本身的链接）。这种 URL 被误判进 `fetch_image` 后，会走完整个渲染预算才报错，既慢又浪费。

修复是把优先级反过来（commit `fd3474b`）：**HEAD 请求拿到的 Content-Type 是权威判定**，只有 HEAD 不可用时（405、请求出错、非 http(s) scheme、响应没有 Content-Type 头）才回退到根据后缀猜测：

```python
def detect_url_kind(self, url: str, timeout: int = 10) -> str:
    ct = self._head_content_type(url, timeout)
    if "application/pdf" in ct:
        return "pdf"
    if ct.startswith("image/"):
        return "image"
    # octet-stream means "no idea", let the suffix decide below.
    if ct and ct != "application/octet-stream":
        return "page"

    path = urllib.parse.urlparse(url).path.rstrip("/").lower()
    if path.endswith(".pdf"):
        return "pdf"
    if path.endswith(_IMAGE_URL_SUFFIXES):
        return "image"
    return "page"
```

这里还有一个细节：`application/octet-stream` 不算有效判定。不少服务器对静态资源一律返回 octet-stream，这等于"我也不知道是什么"，此时照样让后缀来决定。

顺带把后缀表补全到了 `.avif`、`.svg`、`.bmp`、`.ico`（commit `9e5d222`）。这里没有直接用 Python 的 `mimetypes` 数据库，因为平台 MIME 库对新格式支持不全——`.avif` 在原生 macOS 和 Python 3.13 之前的版本里都查不到——所以维护了一份手写的后缀到 MIME 映射表，只有表外格式才回退到 `mimetypes`。

有了三类分流之后，`fetch_url` 也能自动处理图片 URL 了：调用方把一个图片链接喂给 `fetch_url` 时，服务端会识别出来并改走图片路径返回 image content，而不是渲染出一个只有一张图的页面再转成 Markdown。

### 让模型会用：工具描述也得下功夫

MCP 工具的描述文本直接决定了模型能不能正确使用它。`fetch_image` 的描述里除了说明用途，还专门写了一段相对链接的处理方法：

> Resolve site-relative links against the page URL first: e.g. after fetching `https://xxx.yyy/foo/bar.html`, view `![baz](/baz/img.png)` by calling this tool with `https://xxx.yyy/baz/img.png`. Only absolute http(s) URLs.

Markdown 里的图片链接大量是站点相对路径，而工具只接受绝对 URL。不把这个转换规则写进描述里，模型遇到 `/baz/img.png` 这类链接时很容易把相对路径原样传进来，导致调用失败。写清楚之后，模型基本上都能正确拼出绝对 URL 再调用。

## 总结

这次更新的核心是 `fetch_image`：图片走完整浏览器引擎加载，canvas 栅格化成 WebP，以 MCP 原生 image content 返回。关键点包括独立的渲染 profile 与 Cookie 桥接、隔离 JS world 防伪造、Qt 定时器驱动规避后台页面定时器钳制、跨重定向的重试与会话持久化提示。配套的 URL 分流改为 HEAD Content-Type 权威判定，避免后缀撒谎导致的错误路由。

对使用者来说，这些细节都是透明的——AI 助手读到 Markdown 里的图片链接，想看就调一下 `fetch_image`，架构图和截图从此不再是信息黑洞。

项目仓库地址：[GitHub · Qt Web Extractor](https://github.com/wszqkzqk/qt-web-extractor)

项目协议：[GPL-3.0-or-later](https://www.gnu.org/licenses/gpl-3.0.html)
