---
layout:       post
title:        PvZ-Portable：打通 UTF-8 文本输入链路
subtitle:     让 EditWidget 全面改用码点语义，解决软键盘遮挡、快捷键失效与多字符提交问题
header-img:   img/games/bg-pvz-portable.webp
date:         2026-07-31
author:       wszqkzqk
catalog:      true
tags:         文本输入 UTF-8 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

此前几篇介绍 PvZ-Portable UTF-8 改造的博客，讨论的都是**显示侧**：让文本渲染支持 Unicode、按 UTF-8 加载字符串资源、按码点自动换行。但游戏中还有几处需要玩家输入文字的地方，例如修改玩家名的输入框。这部分却一直采用字节语义：光标按字节移动，退格也按字节删除。一个常用汉字通常占三个 UTF-8 字节，按一次退格却只会删掉一个字节，留下损坏的 UTF-8 序列。移动端的问题更直观：软键盘弹出后会把整个输入框挡住，玩家连文字是否成功输入都看不到。

最近，笔者通过三个层层递进的 PR 彻底打通了输入侧：[#363](https://github.com/wszqkzqk/PvZ-Portable/pull/363) 解决软键盘遮挡和重新唤起的问题，[#367](https://github.com/wszqkzqk/PvZ-Portable/pull/367) 解决快捷键失效和输入法整串提交的问题，[#371](https://github.com/wszqkzqk/PvZ-Portable/pull/371) 则让 `EditWidget` 全面改用码点语义，并接入 demo 录制。这条改造路线正好可以概括为“能用 → 好用 → 正确”三步，本文也将按照这个顺序展开。

## 第一步：让软键盘不挡输入框（#363）

在 Android 上点击输入框后，弹出的软键盘会直接将它遮住。根本原因是程序从未告诉系统：**输入框位于屏幕上的什么位置**。SDL 提供的 `SDL_SetTextInputRect` 接口有两个作用：一是为系统的“键盘避让”机制提供锚点，让系统在键盘弹出时将内容平移到输入框可见的位置；二是在桌面平台上帮助输入法定位候选词窗口。PvZ-Portable 一直没有设置这个矩形，键盘避让自然无从实现。

为此，笔者新增了 `SexyAppBase::SetTextInputRect`，将游戏逻辑坐标系中的光标矩形换算为窗口像素坐标，再传给 SDL（`Input.cpp`）：

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

游戏画面先按逻辑分辨率渲染，再缩放到窗口中，因此这里需要进行一次与鼠标坐标映射互逆的换算。`EditWidget` 获得焦点或移动光标时，会向系统报告光标所在位置的 1 像素宽矩形。

这次还一并处理了两个平台层的问题。其一，从 Android 11 开始，旧有的 `adjustPan` 机制在边到边布局下不再生效。因此，需要由 `PvZPortableActivity` 监听 `WindowInsets.Type.ime()`，计算键盘高度并平移内容视图；在旧版系统上则仍回退到 `adjustPan`。其二，再次点击已经获得焦点的输入框不会重新触发焦点事件，因此被用户收起的软键盘无法再次唤出。解决办法是在按下时记录焦点状态；如果用户重复点击已聚焦的输入框，就重新启动一次文本输入会话，让键盘再次弹出。

## 第二步：快捷键和整串提交（#367）

软键盘可以正常使用后，接下来还要解决 SDL 文本输入模型中的两个问题。

第一个问题是：**`SDL_TEXTINPUT` 不保证携带 Ctrl 组合键**。启用文本输入后，Ctrl+C、Ctrl+V 等组合键在许多平台上不会产生 `SDL_TEXTINPUT` 事件，导致输入框中的复制、粘贴快捷键直接失效。修复后，keydown 路径不再在文本输入启用时丢弃所有事件，而是单独将 Ctrl+字母组合转换为控制码并继续传递：

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

可打印字符仍由 `SDL_TEXTINPUT` 传递，控制码则在 keydown 路径中合成。两条路径各司其职，同一次输入也不会被重复处理。

第二个问题是：**输入法可能通过一个 `SDL_TEXTINPUT` 事件提交一整串字符**。Android Gboard 的整词提交、自动纠错替换和输入法内粘贴都会产生这种事件，而旧代码只读取其中的第一个字节：

```cpp
-				mWidgetManager->KeyChar((char)event.text.text[0]);
+				for (const char* aTextPtr = event.text.text; *aTextPtr != 0; aTextPtr++) // IMEs may commit a whole string in one event
+				{
+					const unsigned char aChar = static_cast<unsigned char>(*aTextPtr);
+					if (aChar >= 32 && aChar < 128) // control codes arrive via keydown; non-ASCII has no legacy byte representation
+						mWidgetManager->KeyChar(*aTextPtr);
+				}
```

因此，输入法一次提交一个单词时，游戏只能收到首字母，其余内容都会丢失。上述改动先修复了 ASCII 文本的整串提交。值得注意的是注释中的一句话：`non-ASCII has no legacy byte representation`。逐字节转发无法表达多字节字符；要真正支持中文输入，`KeyChar(char)` 这条路径显然行不通。这正是第三个 PR 要解决的问题。

## 第三步：整条链路码点化（#371）

### 新增 KeyText 虚函数，默认转发 ASCII

核心改动是在 Widget 体系中新增一个用于多字节文本输入的虚函数（`Widget.h`）：

```cpp
virtual void KeyChar(char theChar);
virtual void KeyText(std::string_view theText);
```

`SDL_TEXTINPUT` 事件不再被拆成单个字节，而是将整串文本交给这个函数处理（`Input.cpp`）：

```cpp
			case SDL_TEXTINPUT:
				mLastUserInputTick = mLastTimerTime;
				mWidgetManager->KeyText(std::string_view(event.text.text));
				break;
```

关键在于 `Widget::KeyText` 的**默认实现**（`Widget.cpp`）：

```cpp
void Widget::KeyText(std::string_view theText)
{
	for (const char aChar : theText) // legacy widgets get ASCII via KeyChar; non-ASCII needs an override
		if (static_cast<unsigned char>(aChar) >= 32 && static_cast<unsigned char>(aChar) < 128)
			KeyChar(aChar);
}
```

游戏中有许多旧的 `KeyChar` 消费者，例如作弊键和菜单热键，它们只识别 ASCII。默认实现将可打印的 ASCII 字符逐个转发给 `KeyChar`，因此这些旧代码无需修改，仍能通过新的输入链路正常工作；只有真正需要处理多字节文本的 `EditWidget` 才需要重写 `KeyText`。新链路没有破坏原有接口约定，这是整项改造得以控制在三百多行代码内的关键。

### 边界助手：输入侧需要的 UTF-8 原语

显示侧早已有 `UTF8DecodeNext`，可以解码下一个码点；但输入侧需要解决的是另一组问题：光标向左移动时应后退几个字节？按下退格键时应删除几个字节？第 N 个字符从哪个字节开始？为此，笔者在 `Common.h` 中补充了一组边界辅助函数：

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

向后查找边界利用了 UTF-8 的结构特征：延续字节满足 `(b & 0xC0) == 0x80`，因此只需向后跳过所有延续字节，就能停在该码点的首字节上。这个过程无须解码，一次扫描即可完成。同一批加入的辅助函数还有 `UTF8NextBoundary`、`UTF8ByteOffsetForCodePoint` 和 `UTF8CodePointAt`。

### EditWidget：光标、退格、选词、字数限制

`EditWidget` 的所有编辑操作都从字节语义改为码点语义。按下退格键时，不再简单删除光标前的一个字节，而是删除光标之前的完整码点（`EditWidget.cpp`）：

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

对于 Ctrl+左右方向键的按词移动，`IsPartOfWord` 的参数从 `char` 改为 `char32_t`，并将所有非 ASCII 字符视为词内字符。这样，连续的中文会被视为同一个词，不会像标点一样被切开。字数限制也采用相同的原则，限制的是码点数量，而不是字节数：

```cpp
void EditWidget::EnforceMaxChars()
{
	if ((mMaxChars != -1) && (UTF8CodePointCount(mString) > (size_t)mMaxChars))
		mString = mString.substr(0, UTF8ByteOffsetForCodePoint(mString, (size_t)mMaxChars));
}
```

所有文本插入操作都统一由 `InsertTextAtCursor` 处理，并增加了一层**字体可渲染性过滤**。游戏字体无法覆盖全部 Unicode 字符；如果输入法提交的码点无法由当前字体绘制（`CharWidth` 为零），程序就会将其丢弃，避免玩家名中混入大量只能显示为方框的字符。对于损坏的 UTF-8 序列，处理方式也很明确：跳过无效字节，保留其余有效内容。

WebAssembly 平台的软键盘采用另一套路径：JavaScript 端会比较输入框修改前后的内容，并计算差异。原有实现按 UTF-16 码元进行比较，一个代理对（例如部分 emoji）会被算作两个码元，导致退格删除的数量与实际字符数不符。这次改用 `Array.from` 按码点计算差异，再通过 `TextEncoder` 将非 ASCII 字符编码为 UTF-8 字节并送入引擎。

### demo 录制同步跟进

输入链路发生变化后，确定性回放也需要同步适配：demo 格式升级到 `DEMO_VERSION = 6`，并新增 `DEMO_KEY_TEXT` 命令。录制时，程序会将整串 UTF-8 文本写入命令流；回放时，再将其原样注入 `KeyText`。上一篇博客介绍的逐 tick 复现机制，由此也覆盖到了文本输入。

### 顺手清理

改用码点语义后，密码掩码功能成了彻底的死代码：整个项目中没有任何地方设置 `mPasswordChar`，而它原有的实现也无法正确处理多字节文本，例如掩码长度究竟应按字节还是按字符计算。因此，`mPasswordChar`、`mPasswordDisplayString` 和 `GetDisplayString()` 这一整层间接实现都被删除。此外，这次还修复了两处经典的 ctype 未定义行为：如果向 `toupper` / `isdigit` 传入值为负数的 `char`，行为将未定义，所以现在会先将参数统一转换为 `unsigned char`。

## 结语

三个 PR 的递进顺序其实值得一提：先修复平台层的遮挡和唤醒，再修复输入模型层的快捷键和整串提交问题（否则编辑体验仍然是不完整的），最后才处理核心的码点化。倒过来做也不是不行，但按这个顺序推进，每一步都能让下一步的问题暴露得更清楚。

**不要等到输入侧，才补上字节和码点的区别。** 显示侧完成 UTF-8 支持后，很容易产生“国际化已经搞定”的错觉。但显示只需要解码，输入却需要一整套边界运算——光标移动、删除、选词、计数，每一项都必须按码点重新定义。两侧的工作量并不对等，规划时很容易漏掉输入这一半。

**新通路配合默认转发，让旧消费者一行不动。** `KeyText` 默认将 ASCII 转发给 `KeyChar`，作弊键和热键无需感知变化，就能继续在新链路上工作。做多语言改造时，真正的成本往往不在新功能本身，而在于不能惊动那批只识别 ASCII 的旧代码。一个设计合理的默认实现，就能把这部分成本降到最低。

**平台输入的问题往往都藏在边界上。** Ctrl 组合键不经过 `SDL_TEXTINPUT`，输入法可能一次提交一整串文本，UTF-16 码元与码点并不等价，键盘避让还需要主动上报输入框位置——这些问题没有一条能从 SDL 的 API 签名中直接看出来，每一条都是在真机测试中碰到的。文本输入是所有用户都会接触的基础设施，文档与现实之间的差距，只能靠在各个平台上轮流测试来弥补。

至此，PvZ-Portable 的文本链路——加载、渲染、换行和输入——已经全部支持 UTF-8。玩家名可以使用中文，删除文字不再产生乱码，软键盘也不会再遮挡输入框，这才是文本输入本来应该有的样子。不过，中文版资源包提供的中文字体覆盖范围仍然非常有限，许多汉字没有对应字形；对于缺少字形的字符，游戏会将其宽度设为 0，因此不会显示出来。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守相关版权规定。《植物大战僵尸》的 IP 归 PopCap/EA 所有。

本项目仅包含开源重实现的引擎代码，**不含任何受版权保护的游戏美术、音效、关卡等资源文件**。研究或使用本项目时，你**必须**拥有正版游戏；如尚未购买，可前往 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 购买。你需要从正版游戏中提取以下文件，并将它们放入 PvZ-Portable 程序所在的目录：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
