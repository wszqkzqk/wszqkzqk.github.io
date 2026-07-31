---
layout:       post
title:        PvZ-Portable：打通 UTF-8 文本输入链路
subtitle:     彻底码点化 EditWidget，解决软键盘遮挡、快捷键、多字符提交
header-img:   img/games/bg-pvz-portable.webp
date:         2026-07-31
author:       wszqkzqk
catalog:      true
tags:         文本输入 UTF-8 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

PvZ-Portable 的 UTF-8 改造，之前几篇博客讲的都是**显示**侧：文本渲染支持 Unicode、字符串资源按 UTF-8 加载、自动换行按码点断行。但游戏里有几处需要玩家自己打字的地方——比如改玩家名字的输入框——这一侧一直是字节语义的：光标按字节移动、退格按字节删除。一个汉字三个字节，按一次退格只删掉一个字节，剩下的就是一段损坏的 UTF-8 序列。移动端更直接：软键盘弹出来把输入框整个挡住，打没打上字全凭信仰。

最近笔者用三个递进的 PR 把输入侧彻底打通了：[#363](https://github.com/wszqkzqk/PvZ-Portable/pull/363) 解决软键盘遮挡和唤醒，[#367](https://github.com/wszqkzqk/PvZ-Portable/pull/367) 解决快捷键和输入法整串提交，[#371](https://github.com/wszqkzqk/PvZ-Portable/pull/371) 把 `EditWidget` 整体码点化并接入 demo 录制。这条链路正好可以概括成能用 → 好使 → 正确三步，这篇博客按这个顺序讲。

## 第一步：让软键盘不挡输入框（#363）

Android 上点输入框，软键盘弹出来直接把输入框盖住——根因是程序从来没告诉过系统**输入框在屏幕上什么位置**。SDL 提供了 `SDL_SetTextInputRect` 这个接口，它有两个作用：给系统的"键盘避让"机制一个锚点（键盘弹出时把内容平移到输入框可见的位置），以及在桌面平台上给输入法的候选词窗口定位。PvZ-Portable 一直没设置它，键盘避让自然无从谈起。

修复是加一个 `SexyAppBase::SetTextInputRect`，把游戏逻辑坐标系下的光标矩形换算成窗口像素再喂给 SDL（`Input.cpp`）：

```cpp
void SexyAppBase::SetTextInputRect(const Rect& theRect)
{
	const Rect& aLogical = mWidgetManager->mMouseDestRect;
	const Rect& aPresent = mWidgetManager->mMouseSourceRect; // presentation/window pixels, inverse of RemapMouse
	if (aLogical.mWidth <= 0 || aLogical.mHeight <= 0)
		return;

	SDL_Rect aRect;
	aRect.x = (theRect.mX - aLogical.mX) * aPresent.mWidth / aLogical.mWidth + aPresent.mX;
	aRect.y = (theRect.mY - aLogical.mY) * aPresent.mHeight / aLogical.mHeight + aPresent.mY;
	aRect.w = theRect.mWidth * aPresent.mWidth / aLogical.mWidth;
	aRect.h = theRect.mHeight * aPresent.mHeight / aLogical.mHeight;
	SDL_SetTextInputRect(&aRect);
}
```

游戏画面是逻辑分辨率渲染再缩放到窗口的，所以这里要做一次和鼠标坐标映射互逆的换算。`EditWidget` 在获得焦点和光标移动时，把光标处 1 像素宽的矩形报上去。

还有两个平台层的坑一并处理。一是 Android 11 之后，在边到边布局下系统旧的 `adjustPan` 机制失效，得由 `PvZPortableActivity` 自己监听 `WindowInsets.Type.ime()` 算出键盘高度、平移内容视图，旧系统则回退到 `adjustPan`。二是已聚焦的输入框被再次点击时焦点不会重新触发，被用户划走的软键盘就叫不回来了——解法是在按下时快照焦点状态，重复点击已聚焦输入框就重启一次文本输入会话，键盘重新弹出。

## 第二步：快捷键和整串提交（#367）

键盘能用了，接下来是两个 SDL 文本输入模型的坑。

第一个：**`SDL_TEXTINPUT` 不保证携带 Ctrl 组合键**。文本输入激活时，Ctrl+C、Ctrl+V 这些组合在很多平台上不会产生 `SDL_TEXTINPUT` 事件，输入框里的复制粘贴快捷键直接失灵。修复是在 keydown 路径上，文本输入激活时不再整体丢弃事件，而是单独把 Ctrl+字母合成为控制码放行：

```cpp
	const bool aTextInputActive = SDL_IsTextInputActive(); // printable chars arrive via SDL_TEXTINPUT then
...
		if (aHasCtrl)
		{
			theChar = static_cast<char>(aSym - SDLK_a + 1); // Ctrl+letter -> control code; SDL_TEXTINPUT is not guaranteed for Ctrl combos
			return true;
		}

		if (aTextInputActive)
			return false;
```

可打印字符照旧走 `SDL_TEXTINPUT`，控制码走 keydown 合成，两条路径职责分开，同一次输入不会触发两遍。

第二个：**输入法可能在一个 `SDL_TEXTINPUT` 事件里提交一整串字符**——Android Gboard 的整词提交、自动纠错替换、输入法内粘贴都是这个行为。而旧代码只取第一个字节：

```cpp
-				mWidgetManager->KeyChar((char)event.text.text[0]);
+				for (const char* aTextPtr = event.text.text; *aTextPtr != 0; aTextPtr++) // IMEs may commit a whole string in one event
+				{
+					const unsigned char aChar = static_cast<unsigned char>(*aTextPtr);
+					if (aChar >= 32 && aChar < 128) // control codes arrive via keydown; non-ASCII has no legacy byte representation
+						mWidgetManager->KeyChar(*aTextPtr);
+				}
```

一次提交一个词，只进第一个字母，其余全部丢弃——这个改动先把 ASCII 部分救回来。注意注释里那句 "non-ASCII has no legacy byte representation"：逐字节转发天然表达不了多字节字符，要真正支持中文输入，靠 `KeyChar(char)` 这条路是走不通的。这就是第三个 PR 要解决的问题。

## 第三步：整条链路码点化（#371）

### 新虚函数 KeyText，ASCII 默认转发

核心改动是在 Widget 体系里加了一个多字节文本输入的虚函数（`Widget.h`）：

```cpp
virtual void KeyChar(char theChar);
virtual void KeyText(std::string_view theText);
```

`SDL_TEXTINPUT` 事件不再拆字节，而是整串交给它（`Input.cpp`）：

```cpp
			case SDL_TEXTINPUT:
				mLastUserInputTick = mLastTimerTime;
				mWidgetManager->KeyText(std::string_view(event.text.text));
				break;
```

关键设计在 `Widget::KeyText` 的**默认实现**（`Widget.cpp`）：

```cpp
void Widget::KeyText(std::string_view theText)
{
	for (const char aChar : theText) // legacy widgets get ASCII via KeyChar; non-ASCII needs an override
		if (static_cast<unsigned char>(aChar) >= 32 && static_cast<unsigned char>(aChar) < 128)
			KeyChar(aChar);
}
```

游戏里有一大批老的 `KeyChar` 消费者——作弊键、菜单热键——它们只认 ASCII。默认实现把可打印 ASCII 逐字转发给 `KeyChar`，这些老消费者在新链路上原样工作，一行都不用改；只有真正需要多字节文本的 `EditWidget` 重写 `KeyText`。新链路不破旧契约，这是这次改造能控制在三百多行的关键。

### 边界助手：输入侧需要的 UTF-8 原语

显示侧早就有了 `UTF8DecodeNext`（解码下一个码点），但输入侧要回答的是另一组问题：光标向左移动该退几个字节？退格该删几个字节？第 N 个字符在第几个字节？这次在 `Common.h` 里补了一组边界助手：

```cpp
// Step one code point backward to its lead byte. Returns 0 if at the start.
inline size_t UTF8PrevBoundary(std::string_view theString, size_t theOffset)
{
	if (theOffset == 0 || theString.empty())
		return 0;
	size_t aPos = std::min(theOffset, theString.size()) - 1;
	while (aPos > 0 && (static_cast<unsigned char>(theString[aPos]) & 0xC0) == 0x80)
		aPos--;
	return aPos;
}

// Number of UTF-8 code points in theString.
inline size_t UTF8CodePointCount(std::string_view theString)
{
	size_t aCount = 0;
	size_t aOffset = 0;
	char32_t aChar = 0;
	while (UTF8DecodeNext(theString, aOffset, aChar))
		aCount++;
	return aCount;
}
```

后退边界利用 UTF-8 的结构性质：延续字节的特征是 `(b & 0xC0) == 0x80`，往回跳过所有延续字节就落在首字节上——不需要解码，一次扫描到位。同批还有 `UTF8NextBoundary`、`UTF8ByteOffsetForCodePoint`、`UTF8CodePointAt`。

### EditWidget：光标、退格、选词、字数限制

`EditWidget` 的全部编辑操作从字节语义改成码点语义。退格不再是 `length - 1`，而是删到上一个码点边界（`EditWidget.cpp`）：

```cpp
				// Delete char behind cursor
				if (mCursorPos > 0)
				{
					size_t aPrev = UTF8PrevBoundary(mString, mCursorPos);
					...
					mString = mString.substr(0, aPrev) + mString.substr(mCursorPos);
					mCursorPos = aPrev;
				}
```

Ctrl+左右的方向键选词，`IsPartOfWord` 从 `char` 改成 `char32_t`，非 ASCII 一律视为词内字符——中文连续成词，不会被当成标点切开。字数限制同理，限制的是字符个数而不是字节数：

```cpp
void EditWidget::EnforceMaxChars()
{
	if ((mMaxChars != -1) && (UTF8CodePointCount(mString) > (size_t)mMaxChars))
		mString = mString.substr(0, UTF8ByteOffsetForCodePoint(mString, (size_t)mMaxChars));
}
```

文本插入收敛到一个 `InsertTextAtCursor`，并且做了一层**字体可渲染性过滤**：游戏字体不是全覆盖的 Unicode 字体，输入法提交进来的码点如果字体画不出来（`CharWidth` 为零），就直接丢掉，避免玩家名字里混进一堆显示成方框的字符。损坏的 UTF-8 序列也有明确的容错：跳过坏字节，保住其余部分。

WebAssembly 平台的软键盘走另一条路：JS 侧比对输入框前后值做差分。原来的差分按 UTF-16 码元做，一个代理对（部分emoji）算两个码元，退格删除和实际字符数对不上；这次改成 `Array.from` 按码点差分，非 ASCII 再经 `TextEncoder` 编成 UTF-8 字节送进引擎。

### demo 录制同步跟进

输入链路变了，确定性回放也要跟上：demo 格式升到 `DEMO_VERSION = 6`，新增 `DEMO_KEY_TEXT` 命令，录制时把整串 UTF-8 文本写进流，回放时原样回注 `KeyText`——上一篇博客讲的那套逐 tick 复现机制，覆盖范围跟着扩大到了文本输入。

### 顺手清理

码点化之后，密码掩码功能成了纯死代码——全项目没有任何地方设置 `mPasswordChar`，而且它和多字节文本天然冲突（掩码长度按字节还是按字符算？）。整套 `mPasswordChar`、`mPasswordDisplayString`、`GetDisplayString()` 间接层一并删除。另外修了两处经典的 ctype UB：`toupper`/`isdigit` 传入负的 `char` 值是未定义行为，参数一律先转 `unsigned char`。

## 结语

三个 PR 递进的顺序其实值得说说：先修平台层的遮挡和唤醒，再修输入模型层的快捷键和整串提交（不修这个，编辑体验是残缺的），最后才动核心——码点化。倒过来做不是不行，但每前一步都让后一步的问题暴露得更清楚。

**字节和码点之分，别拖到输入侧才补。** 显示侧的 UTF-8 支持做完之后，很容易产生"国际化已经搞定"的错觉。但显示只需要解码，输入需要的是一整套边界运算——光标、删除、选词、计数，每一样都得按码点重新定义。这两侧的工作量完全不对等，规划时容易漏掉输入这一半。

**新通路配默认转发，老消费者一行不动。** `KeyText` 默认把 ASCII 转发给 `KeyChar`，作弊键和热键在新链路上无感存活。做多语言改造时，真正的成本往往不在新功能本身，而在不吵醒那批只认 ASCII 的老代码——一个设计好的默认值能把这笔成本降到零。

**平台输入的坑都在边界上。** Ctrl 组合键不走 `SDL_TEXTINPUT`、输入法一次提交一整串、UTF-16 码元和码点不等价、键盘避让要自己报位置——这些没有一条能从 SDL 的 API 签名里读出来，每一条都是真机实测撞出来的。文本输入这种人人都要用的基础设施，文档和现实的差距只能靠各平台轮着测来弥补。

至此，PvZ-Portable 的文本链路——加载、渲染、换行、输入——全部支持 UTF-8 了。玩家名写中文，删字不再删出乱码，软键盘也不再挡视线，这是早就该有的样子。（不过中文版资源包支持的中文字体其实非常有限，很多汉字没有字形，游戏对于缺乏字形的字体会都会把宽度设为 0，不会显示出来）

## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
