---
layout:       post
title:        PvZ-Portable：多语言资源包支持
subtitle:     BOM 处理、字体 Unicode 化到 CJK 自动换行与禁则处理……一个完整的国际化踩坑记录
date:         2026-03-01
author:       wszqkzqk
header-img:   img/games/bg-pvz-portable.webp
catalog:      true
tags:         C++ SDL2 国际化 开源软件 游戏移植 开源游戏 PvZ-Portable
---

## 引言

在之前的[文章](https://wszqkzqk.github.io/2026/01/26/PvZ-Portable/)中，笔者介绍了 [PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable) 项目——一个跨平台的《植物大战僵尸：年度版》开源重实现。项目一直以来以英语版 1.2.0.1073 为标准资源包进行开发和测试。然而，宝开官方实际上发布过多种语言的 GOTY 版本——德语、西班牙语、法语、意大利语，以及至今仍有争议的中文版。这些版本的资源文件在编码方式、文本格式和 UI 布局上都与英语版存在不同程度的差异。

社区开发者 [chirsz-ever](https://github.com/chirsz-ever) 首先注意到了这个问题，并先后提交了 Issue [#72](https://github.com/wszqkzqk/PvZ-Portable/issues/72) 和 PR [#73](https://github.com/wszqkzqk/PvZ-Portable/pull/73)、[#78](https://github.com/wszqkzqk/PvZ-Portable/pull/78)，指出了引擎在加载非英语资源包时遇到的 BOM 编码问题和 Unicode 字体渲染问题，并提供了初步的修复方案。感谢 chirsz-ever 的发现和贡献！

笔者在 chirsz-ever 的初始工作基础上，重新整理代码，对编码处理和渲染逻辑进行了规范化和性能优化，同时解决了 CJK 文本自动换行、禁则处理、`\n` 回归等一系列复杂问题，最终汇总为 PR [#79](https://github.com/wszqkzqk/PvZ-Portable/pull/79)。

本文将按照开发和踩坑的时间顺序，详细记录整个多语言支持的实现过程。

## 背景：非英语资源包的差异

原版植物大战僵尸的多语言版本由宝开官方发布，各语言版本的资源文件在编码和内容上存在以下差异：

| 差异项 | 英语版 1.2.0.1073 | 非英语版（DE/ES/FR/IT/ZH 等） |
| :--- | :--- | :--- |
| **文本编码** | ASCII / 无 BOM 的 UTF-8 | UTF-8 with BOM 或 UTF-16 LE with BOM |
| **`properties/default.xml`** | 不存在 | 存在，包含本地化字符串 |
| **`properties/Layout.xml`** | 不存在 | 存在，包含 UI 布局参数 |
| **字符覆盖范围** | 仅 ASCII 字形 | 含重音字母、CJK 字符等 |
| **商店控制标志** | 不使用 `STORE_USE_*_IMAGE_LABEL` | 部分版本设置了这些 bool 标志 |

引擎在此之前完全按 ASCII 或不带 BOM 的 UTF-8 处理文本文件，也没有在启动时加载 `default.xml` 和 `Layout.xml`，因此非英语资源文件要么无法加载，要么会显示乱码。

## 第一步：Unicode 文本渲染与 UTF-8 文件加载

**对应 Commit**: [`03b0925`](https://github.com/wszqkzqk/PvZ-Portable/commit/03b092527df0fadc7d32e4eda13cdde16b9b6845)（Co-authored-by: chirsz-ever）

这是整个多语言支持的基础工程。核心改动包括：

### BOM 检测与编码转换

原先 `Buffer::UTF8ToString()` 直接将 Buffer 中的原始字节当作 UTF-8 返回。这对英语版没有问题，但非英语版的文件往往带有 BOM，甚至使用 UTF-16 LE 编码。

笔者将该方法重构为 `Buffer::ToUTF8String()`，加入了 BOM 检测逻辑：

```cpp
bool Buffer::ToUTF8String(std::string* theString) const
{
    const char* aData = (const char*)GetDataPtr();
    int aLen = GetDataLen();
    if (aLen >= 3 && memcmp(aData, "\xEF\xBB\xBF", 3) == 0) {
        // UTF-8 BOM: strip it
        *theString = std::string(aData + 3, aLen - 3);
        return true;
    }
    char* aStringBuffer = nullptr;
    if (aLen >= 2 && memcmp(aData, "\xFF\xFE", 2) == 0) {
        // UTF-16 LE BOM
        aStringBuffer = SDL_iconv_string("UTF-8", "UTF-16LE", aData + 2, aLen - 2);
    } else if (aLen >= 2 && memcmp(aData, "\xFE\xFF", 2) == 0) {
        // UTF-16 BE BOM
        aStringBuffer = SDL_iconv_string("UTF-8", "UTF-16BE", aData + 2, aLen - 2);
    } else {
        // No BOM: treat as UTF-8,  covers ASCII as well
        *theString = std::string(aData, aLen);
        return true;
    }
    // ...
}
```

这里使用了 SDL 自带的 `SDL_iconv_string` 进行 UTF-16 到 UTF-8 的转码，避免引入额外的依赖。同时新增了 `ReadUTF8StringFromFile` 方法，将文件读取和 BOM 处理封装在一起，`DescParser`、`PropertiesParser` 和 `TodStringFile` 中所有的文本文件加载都统一改为调用这个方法。

### 字体渲染的 `char32_t` 改造

原有的 `ImageFont` 字体引擎完全按单字节 `char` 处理字符。对于 ASCII 字符来说这没有问题，但遇到多字节 UTF-8 编码的非 ASCII 字符（如重音字母、CJK 字符）时，引擎会将一个字符的多个字节拆开处理，导致乱码或无法渲染。

核心改造是将 `CharData` 的查找键、字符宽度计算和渲染循环全部从 `char` 升级到 `char32_t`：

```cpp
// Before
CharData* FontLayer::GetCharData(char theChar);
int ImageFont::CharWidthKern(char theChar, char thePrevChar);
int ImageFont::CharWidth(char theChar);
char ImageFont::GetMappedChar(char theChar);

// After
CharData* FontLayer::GetCharData(char32_t theChar);
int ImageFont::CharWidthKern(char32_t theChar, char32_t thePrevChar);
int ImageFont::CharWidth(char32_t theChar);
char32_t ImageFont::GetMappedChar(char32_t theChar);
```

`ImageFont::DrawStringEx` 中原先按字节遍历字符串的循环，被重写为使用共享的 `UTF8DecodeNext()` 函数逐码点（codepoint）遍历：

```cpp
size_t aDecodeOffset = 0;
char32_t aCurRawChar = 0;
char32_t aNextRawChar = 0;

bool aHasCur = UTF8DecodeNext(theString, aDecodeOffset, aCurRawChar);
while (aHasCur)
{
    bool aHasNext = UTF8DecodeNext(theString, aDecodeOffset, aNextRawChar);
    char32_t aChar = GetMappedChar(aCurRawChar);
    char32_t aNextChar = aHasNext ? GetMappedChar(aNextRawChar) : 0;
    // ... 渲染逻辑 ...
    aCurRawChar = aNextRawChar;
    aHasCur = aHasNext;
}
```

`UTF8DecodeNext()` 被提取到 `Common.h` 中作为公共内联函数，消除了之前在 `ImageFont.cpp` 里的重复实现。

## 第二步：XML 解析器的 UTF-8 修复

**对应 Commit**: [`602dc9b`](https://github.com/wszqkzqk/PvZ-Portable/commit/602dc9b71d8d927b04a67c4518579b309f6a7a3d)（Co-authored-by: chirsz-ever）

这是一个小而关键的修复。`XMLParser` 的 `NextElement` 在跳过空白字符时，使用了 `char` 与数字 `32`（即空格）的比较：

```cpp
if (c <= 32)  // 意图：跳过空格和控制字符
```

问题是 C++ 中 `char` 默认是 **有符号的**（至少在大多数平台上是）。UTF-8 的后续字节（continuation bytes）的值在 `0x80` 以上，作为 `signed char` 解释时变成**负数**，因此 `c <= 32` 的条件恒为真，导致 UTF-8 多字节序列被错误地当作空白跳过，非 ASCII 内容的 XML 元素会被截断或丢失。

修复方式很简单——在比较前将 `char` 转换为 `unsigned char`：

```cpp
if (static_cast<unsigned char>(c) <= 32)
```

另外，`GetUTF8Char` 在遇到文件末尾（EOF）时不再设置编码错误标志，因为 EOF 并不是一个编码错误。

## 第三步：CJK 和 Emoji 的自动换行

**对应 Commit**: [`74e627a`](https://github.com/wszqkzqk/PvZ-Portable/commit/74e627a581b9453023b44a2c92a6e143169d7f86)

### 问题：中文文本不换行

在完成前两步之后，用中文资源包测试时发现了一个严重的显示问题：**所有中文文本在文本框中不会自动换行**，整段话挤成一长串溢出显示框。

原因在于，英文的自动换行逻辑完全依赖**空格**作为断行点——遇到空格时记录断行位置，当行宽超出限制时回退到上一个空格处换行。但中文、日文、韩文等 CJK 文字之间没有空格分隔，引擎找不到任何断行点，自然无法换行。

### 解决方案：`IsAutoBreakChar` 与 UTF-8 断行

笔者在 `Common.h` 中添加了 `IsAutoBreakChar()` 函数，覆盖所有可以在字符前后自动断行的 Unicode 范围：

```cpp
inline bool IsAutoBreakChar(char32_t theChar)
{
    if (theChar < 0x80) return false;
    return (theChar >= 0x2018 && theChar <= 0x201D) ||  // Curly quotes
        (theChar >= 0x2600 && theChar <= 0x27BF) ||  // Misc Symbols, Dingbats
        (theChar >= 0x3000 && theChar <= 0x303F) ||  // CJK Symbols and Punctuation
        (theChar >= 0x3040 && theChar <= 0x309F) ||  // Hiragana
        (theChar >= 0x30A0 && theChar <= 0x30FF) ||  // Katakana
        (theChar >= 0x3400 && theChar <= 0x4DBF) ||  // CJK Extension A
        (theChar >= 0x4E00 && theChar <= 0x9FFF) ||  // CJK Unified Ideographs
        (theChar >= 0xAC00 && theChar <= 0xD7AF) ||  // Hangul Syllables
        (theChar >= 0xF900 && theChar <= 0xFAFF) ||  // CJK Compatibility Ideographs
        (theChar >= 0xFE30 && theChar <= 0xFE4F) ||  // CJK Compatibility Forms
        (theChar >= 0xFF01 && theChar <= 0xFF60) ||  // Fullwidth Forms
        (theChar >= 0x1F300 && theChar <= 0x1FAFF) || // Emoji
        (theChar >= 0x20000 && theChar <= 0x2FA1F);  // CJK Extension B-F
}
```

然后重写了三个地方的换行逻辑：

1. **`TodDrawStringWrappedHelper`**（`TodStringFile.cpp`）——游戏内大部分文本显示使用
2. **`Graphics::WriteWordWrapped`**（`Graphics.cpp`）——框架层通用文本换行
3. **`ToolTipWidget::GetLines`**（`ToolTipWidget.cpp`）——工具提示换行

三个函数都从原来的按字节遍历改为用 `UTF8DecodeNext()` 逐码点遍历，并在遇到 `IsAutoBreakChar` 返回 `true` 的字符时记录断行点。

### 踩坑：`\n` 的语义回归

这一步完成后，笔者使用标准英语版 1.2.0.1073 资源包测试时发现了**回归问题**：部分文本的显示出现异常——原本应该连续显示的描述文本被错误地硬换行了。

追查后发现，`LawnStrings.txt` 中某些字符串（比如植物和僵尸的 FLAVOR 描述文本）的 `\n` **并不是硬换行符**，而只是在显示时起到空格的作用，真正的换行由引擎根据文本框宽度自动计算。原版引擎通过 `TOD_FORMAT_IGNORE_NEWLINES` 格式标志来控制这一行为——当该标志被设置时，`\n` 应该被当作空格而不是强制换行。

但在重写换行逻辑时，笔者将 `\n` 统一处理为硬换行，忽略了这个标志。这对中文版没有影响（中文版的文本格式不同），但对标准英语版造成了**回归**，因为1.2.0.1073 EN 的 FLAVOR 文本依赖 `TOD_FORMAT_IGNORE_NEWLINES` 来正确排版。

## 第四步：加载本地化属性文件

**对应 Commit**: [`ed97925`](https://github.com/wszqkzqk/PvZ-Portable/commit/ed97925603ca6cc50f3dd580695548c1b56360af)

这一步是为了响应 Issue [#72](https://github.com/wszqkzqk/PvZ-Portable/issues/72) 中 chirsz-ever 提出的需求：非英语版本的设置界面和成就界面仍然显示英文。

### `default.xml` 与 `Layout.xml` 的加载

非英语版本的资源包中通常包含 `properties/default.xml` 和 `properties/Layout.xml`，分别存储本地化的字符串和 UI 布局参数。这两个文件的加载时机至关重要——它们必须**在 `LawnStrings.txt` 之后**加载，才能覆盖 `LawnStrings.txt` 中同名键的值。笔者将加载逻辑放在 `LawnApp::LoadingThreadProc` 中 `TodStringListLoad` 之后：

```cpp
void LawnApp::LoadingThreadProc()
{
    // ...
    TodStringListLoad("Properties/LawnStrings.txt");

    // Load localized properties AFTER LawnStrings so they can override string values
    LoadProperties("properties/default.xml", false, false);
    LoadProperties("properties/Layout.xml", false, false);
    // ...
}
```

两个文件都以 `required=false` 加载——不存在时静默忽略，存在时覆盖 `LawnStrings.txt` 中的同名值。这一设计的好处是：除了让非英语版本的属性生效，用户还可以**自己编写 `default.xml`**，在其中添加需要的字符串键值对或其他参数来手动覆盖 `LawnStrings.txt` 中的内容，从而解决特定版本的不兼容显示问题——例如使用 1.2.0.1096 资源包的用户可以在 `default.xml` 中补上缺失的键来修复已知的显示差异。

### 成就界面的本地化

成就名称和描述原先是直接引用硬编码的英文字符串。改为通过 `GetString()` 查询，有本地化字符串时用本地化版本，否则回退到英文：

```cpp
std::string aName = mApp->GetString(gAchievementList[i].name,
                                     gAchievementList[i].name);
std::string aDesc = mApp->GetString(gAchievementList[i].description,
                                     gAchievementList[i].description);
```

### 踩坑：`STORE_USE_*_IMAGE_LABEL` 布尔标志

在实现 `default.xml` 加载后，笔者发现**德语等版本的商店界面出现了新的显示问题**：本来应该显示 "SOLD OUT"（已售出）或 "COMING SOON"（即将推出）的文字标签不见了。

追踪后发现，`default.xml` 中定义了一些布尔控制值，如 `STORE_USE_SOLD_OUT_IMAGE_LABEL`，原版引擎会根据这些标志来决定是使用**本地化的图片标签**还是绘制文本。但 PvZ-Portable 并不没有编码这些本地化图片资源路径——项目始终直接绘制文本。一旦属性文件中的布尔标志被加载并为 `true`，引擎就会走使用图片的分支，而图片又不存在，结果就是什么都不显示。

解决方案是在 `StoreScreen.cpp` 中跳过对这些布尔标志的判断，始终使用文本绘制路径，由于 PvZ-Portable 项目对 Unicode 支持完全，文本绘制路径兼容所有语言：

```cpp
// STORE_USE_*_IMAGE_LABEL not checked: no localized image, always draw text.
TodDrawStringWrapped(g, "[SOLD_OUT]", aRect, ...);
```

同时，部分从 `Layout.xml` 中读取 **UI 布局偏移量**的逻辑也被添加到 `NewOptionsDialog`（音量滑块标签位置、复选框标签位置、字体缩放）和 `ChallengeScreen`（按钮文本自动换行阈值）等界面中，使 UI 布局能够适应**不同语言文本的长度差异**。

### 版本间不兼容的菜单字符串键

另一个发现是，宝开的多语言版本实际上基于的是 1.2.0.1093 而非 1.2.0.1073。两者之间存在**字符串键名的不兼容变更**，例如菜单设置中的某些键在 1.2.0.1093 中被重命名了。这意味着引擎不可能在保持与 1.2.0.1073 行为一致的同时"干净地"兼容所有版本的菜单字符串。因此，菜单设置项的文本仍然使用英文硬编码作为最终回退。

## 第五步：修复换行回归与禁则处理

**对应 Commit**: [`03623e0`](https://github.com/wszqkzqk/PvZ-Portable/commit/03623e003940608752d5823b00a8f83858a0102f)

这是整个 PR 中最后一个 commit，也是前面遗留的问题清理。

### 修复 `\n` 回归

如前所述，第三步中将 `\n` 统一当作硬换行导致了英语版 FLAVOR 文本的显示回归。修复方案是在判断换行时检查 `TOD_FORMAT_IGNORE_NEWLINES` 标志：

```cpp
bool aIsNewline = (aCurChar == U'\n') &&
    !TestBit(aCurrentFormat.mFormatFlags,
             TodStringFormatFlag::TOD_FORMAT_IGNORE_NEWLINES);
```

当该标志被设置时，`\n` 不被视为硬换行，而是像普通字符一样参与宽度计算——在显示效果上等同于空格。标准英语版 1.2.0.1073 的 `LawnStrings.txt` 中的 FLAVOR 文本正是依赖这个机制来正确排版的。

同时，所有三个换行函数中都加入了对 `\r`（CR）的跳过处理，确保 CRLF 和 LF 行尾都能正常工作，确保稳健性。

### 禁则处理（Kinsoku Shori）

简单地在每个 CJK 字符前后都允许断行虽然解决了换行问题，但会产生排版上的瑕疵——例如句号被挤到下一行开头、左括号留在上一行末尾等。这在日文排版中有一个专门的术语叫**禁则处理**（禁則処理，kinsoku shori）。

笔者添加了两个辅助函数来区分开闭标点：

```cpp
// 行首禁则：这些字符不能出现在行首
inline bool IsClosingPunctuation(char32_t theChar)
{
    switch (theChar)
    {
    case U'〉': case U'》': case U'」': case U'』':
    case U'】': case U'〕': case U'〗': case U'〙': case U'〛':
    case U'）': case U'］': case U'｝':
    case U'\u2019': case U'\u201D':  // 右单引号、右双引号
    case U'、': case U'。': case U'，': case U'．':
    case U'！': case U'？': case U'：': case U'；':
        return true;
    default: return false;
    }
}

// 行尾禁则：这些字符不能出现在行尾
inline bool IsOpeningPunctuation(char32_t theChar)
{
    switch (theChar)
    {
    case U'〈': case U'《': case U'「': case U'『':
    case U'【': case U'〔': case U'〖': case U'〘': case U'〚':
    case U'（': case U'［': case U'｛':
    case U'\u2018': case U'\u201A': case U'\u201B': case U'\u201C':  // 左引号
        return true;
    default: return false;
    }
}
```

断行逻辑被更新为：

- **闭标点**（如句号、逗号、右括号）后面不能是断行点——闭标点应该紧跟在前一个字的后面
- **开标点**（如左括号、左引号）前面不能是断行点——开标点应该跟随下一个字

对应的断行条件变为：

```cpp
if (!aIsSpace && !aIsNewline && Sexy::IsAutoBreakChar(aCurChar) &&
    !Sexy::IsClosingPunctuation(aCurChar) &&
    aCharStart > aLineFeedPos &&
    !Sexy::IsOpeningPunctuation(aPrevChar))
{
    aBreakDrawLen = aCharStart - aLineFeedPos;
    aBreakResumePos = aCharStart;
    aBreakSkipSpaces = false;
}
```

注意这里记录的断行位置是 `aCharStart`（当前字符之前），而不是 `aCharEnd`（当前字符之后），确保断行发生在字符边界的正确一侧。同时 `aPrevChar` 的更新被移到了断行判断之后，避免因顺序问题在本次迭代中检查到的是已经更新过的 `aPrevChar`。

## 总结：踩坑回顾

整个多语言支持的实现可以用一张时间线来概括：

| 阶段 | 做了什么 | 踩了什么坑 |
| :--- | :--- | :--- |
| ① UTF-8 / BOM / Unicode 字体化 | 编码检测、UTF-16 转码、`char32_t` 字体改造 | — |
| ② XML 解析器修复 | `signed char` vs `unsigned char` 的比较 | UTF-8 continuation bytes 被当作负数 |
| ③ CJK 自动换行 | `IsAutoBreakChar` + UTF-8 码点遍历 | 中文文本不换行（全挤一行）；改完后英语版 FLAVOR 文本出现回归（`\n` 被硬换行） |
| ④ 本地化属性加载 | 加载 `default.xml` / `Layout.xml`、成就翻译 | `STORE_USE_*_IMAGE_LABEL` 导致德语版商店标签消失 |
| ⑤ 换行回归修复 + 禁则处理 | `TOD_FORMAT_IGNORE_NEWLINES`、`\r` 跳过、开闭标点禁则 | 必须区分"软换行 `\n`"和硬换行 |

几个关键教训：

1. **`\n` 不一定是换行**——至少在这个项目中，`\n` 在启用了 `TOD_FORMAT_IGNORE_NEWLINES` 标志的文本（如 FLAVOR 描述）中只相当于空格。忽略这一点会导致标准英语版的文本显示回归。
2. **属性文件中的 bool 标志不能简单采用**——`default.xml` 中定义的某些布尔控制值对应的是原版引擎中使用本地化图片资源的逻辑，但重实现的引擎并不包含这些图片，直接采用反而会导致显示内容丢失。
3. **`signed char` 是 C/C++ 中的经典陷阱**——UTF-8 continuation bytes 的高位为 1，在有符号 `char` 下变成负数，各种数值比较都可能出错。
4. **CJK 排版不只是"能断行"**——还需要考虑禁则处理，否则标点符号会出现在不合适的位置。
5. **不同版本之间的字符串键不兼容**——宝开在 1.2.0.1073 到 1.2.0.1093/1096 之间修改了不少键名，因此完全跨版本兼容几乎不可能，只能在标准版本上保证正确行为，其他版本尽力适配。

## 支持的版本

经过这些改动，PvZ-Portable 现在支持 **GOTY 1.2.0.1073** EN（宝开独立发行版）以外的多种语言版本。**其他语言 GOTY 版本**（1.2.0.1093 DE/ES/FR/IT 及基于 1.2.0.1073 的 1.1.0.1056 ZH）和 **Steam GOTY 1.2.0.1096** 也受支持——游戏玩法均完全正常——但由于不同版本间字符串键名存在差异，部分界面文本可能缺失或回退为英文默认值。

**建议尽量使用 1.2.0.1073 EN 的资源包。**

以下问题**已在 1.2.0.1096（Steam 版）中确认**，也可能影响其他非 1.2.0.1073 EN 的版本。使用 1.2.0.1073 EN 资源包时这些问题**均不会出现**。

| 问题（非 1.2.0.1073 EN 版本） | 原因 |
| :--- | :--- |
| **图鉴蓝色介绍文字不显示** | 1.2.0.1096 将描述开头的纯文本段落从 `[XXX_DESCRIPTION]` 拆分到了新的 `[XXX_DESCRIPTION_HEADER]` 键中，而引擎只读取 `[XXX_DESCRIPTION]`，因此不会显示头部文本。 |
| **"重新开始"按钮文字缺失** | 按钮文本的键名从 `[RESTART_LEVEL]` 被改为了 `[RESTART_LEVEL_BUTTON]`。 |
| **未遭遇的僵尸显示 `???`** 而非 `(not encountered yet)` | `[NOT_ENCOUNTERED_YET]` 的值在 1.2.0.1096 中被改为了 `???`，原文本移到了新键 `[NOT_ENCOUNTERED_YET_DESCRIPTION]`。 |
| **戴夫卖植物价格显示为正确值的 1/10** | 1.2.0.1073 的 `[CRAZY_DAVE_1700]` 字符串模板中 `{SELL_PRICE}` 后有一个尾随的 `0`（即 `${SELL_PRICE}0`），因为引擎传入的是价格除以 10 的值。1.2.0.1096 去掉了这个 `0`，导致显示的卖价变为实际值的 1/10。 |

不过，由于 `default.xml` 的加载优先级高于 `LawnStrings.txt`，用户可以**自行创建或编辑 `properties/default.xml`**，在其中添加或覆盖所需的字符串键值对，从而手动修复特定版本的显示不兼容问题。例如，使用 1.2.0.1096 资源包的用户可以在 `default.xml` 中补上 `RESTART_LEVEL` 等缺失的键，使界面恢复正常显示。用户借此可以在不修改引擎代码的情况下灵活调整游戏文本。
