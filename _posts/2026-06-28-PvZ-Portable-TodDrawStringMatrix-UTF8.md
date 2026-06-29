---
layout:       post
title:        PvZ-Portable：智慧树只报身高不报单位——TodDrawStringMatrix 里按字节数的 UTF-8 漏洞
subtitle:     字体早就 Unicode 化了，可这条带矩阵变换的绘制路径还在把每个 UTF-8 字节当成一个字符去查字图
header-img:   img/games/bg-pvz-portable.webp
date:         2026-06-28
author:       wszqkzqk
catalog:      true
tags:         UTF-8 国际化 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

三月份那篇[《多语言资源包支持》](https://wszqkzqk.github.io/2026/03/01/PvZ-Portable-Multilingual-Support/)发出去之后，笔者一度以为 [PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable) 的 UTF-8 改造基本收尾了：字体渲染换成了 `char32_t`，文本文件加载能识别 BOM 和各种编码，CJK 自动换行和禁则处理也都加上了。英语、德语、中文几套资源包跑下来，界面上的字都能正常显示。

结果前阵子用中文资源包养智慧树的时候，又被现实教育了一次。

智慧树是禅境花园里的一个彩蛋玩法，给它施肥它会不断长高，并在屏幕上方报告自己的身高。树比较矮的时候它只会和你聊天，等长到 50 英尺以上，才会在头顶显示一行类似“XX 英尺高”的身高文字。笔者那棵树养得足够高，于是看到了这一幕：

> 屏幕上只有一个孤零零的数字“50”，后面的“英尺高”三个字凭空消失了。

数字是对的，单位没了。这种“一半对一半错”的现象往往比全错更烦人，因为它说明渲染管线本身没崩，只是某一段文本被悄悄吞掉了。顺着这条线索查下去，最后定位到的是一处早就该改、却一直没人踩到的代码：`TodDrawStringMatrix` 里还在按字节数遍历 UTF-8 字符串。对应的修复是 PR [#327](https://github.com/wszqkzqk/PvZ-Portable/pull/327)，提交 [0d6b2a9](https://github.com/wszqkzqk/PvZ-Portable/commit/0d6b2a91cfa00d6da56e71aa2a6e103dd4a1d841)。

## 为什么偏偏是智慧树

PvZ-Portable 里绝大部分文本走的是 `TodDrawString`、`TodDrawStringWrapped` 这两条路径，它们在三月那次改造里就已经换成逐码点解码了，所以菜单、对话框、图鉴这些中文都显示正常。智慧树身高之所以单独出问题，是因为它压根不走那两条路。

身高文字在树长高的瞬间会有一个弹跳缩放的动画，需要挂一个变换矩阵来绘制，所以它用的是带矩阵参数的 `TodDrawStringMatrix`。相关代码在 `src/Lawn/Challenge.cpp` 的 `Challenge::TreeOfWisdomDraw` 里：

```cpp
if (aCurSize >= 50)
{
    std::string aSizeStr = TodReplaceNumberString("[TREE_OF_WISDOM_HIEGHT]", "{HEIGHT}", aCurSize);
    float aStrWidth = Sexy::FONT_HOUSEOFTERROR16->StringWidth(aSizeStr) * aScale;
    float aStrHeight = Sexy::FONT_HOUSEOFTERROR16->mAscent * aScale;

    SexyTransform2D aMatrix;
    TodScaleTransformMatrix(aMatrix, 400.0f - aStrWidth * 0.5f, 20.0f + aStrHeight * 0.5f, aScale, aScale);
    TodDrawStringMatrix(g, Sexy::FONT_HOUSEOFTERROR16, aMatrix, aSizeStr, Color(255, 255, 255));
}
```

（`TREE_OF_WISDOM_HIEGHT` 这个键名本身就是原版资源里遗留的拼写错误，把“HEIGHT”写成了“HIEGHT”，引擎为了兼容资源包只能将错就错。）

`TodReplaceNumberString` 把 `{HEIGHT}` 替换成实际数字。英语资源包里这个模板是纯 ASCII，比如 `50 feet tall`；中文资源包里则是 `50英尺高` 这种“数字夹中文”的 UTF-8 字符串。问题就出在 `TodDrawStringMatrix` 拿到这个混合字符串之后的处理方式上。

也正因为这个 bug 的触发条件比较苛刻——既要装非英语资源包，又要把智慧树养到 50 英尺以上——它才在代码里安安静静地藏了这么久。用英语资源包的玩家永远不会遇到，用中文资源包但没怎么养树的玩家也遇不到。

## 根因：把字节数当成了字符数

来看修复前 `TodDrawStringMatrix` 的核心循环（在 `src/Sexy.TodLib/TodCommon.cpp`）：

```cpp
for (int aCharNum = 0; aCharNum < static_cast<int>(aFinalString.size()); aCharNum++)
{
    char aChar = aFont->GetMappedChar(aFinalString[aCharNum]);
    char aNextChar = '\0';
    if (aCharNum < static_cast<int>(aFinalString.size()) - 1)
    {
        aNextChar = aFont->GetMappedChar(aFinalString[aCharNum + 1]);
    }
    // ...
    CharData* aCharData = aLayer->GetCharData(aChar);
    // ...
    aRenderCommand->mSrc[0] = aKernItr->mScaledCharImageRects.find(aChar)->second.mX;
    // ...
}
```

问题全在第一行。`aFinalString` 是 `std::string`，它的 `size()` 返回的是**字节数**，不是字符数。循环用 `aFinalString[aCharNum]` 每次取一个 `char`，再交给 `GetMappedChar` 去查字形。对纯 ASCII 文本来说，一个字节就是一个字符，这套写法完全没问题——这也是它能“正常工作”这么多年的原因。

可一旦字符串里混进 UTF-8 多字节序列，事情就变了味。`50英尺高` 这个字符串在内存里其实是 11 个字节：

```
'5'   '0'   英          尺          高
0x35  0x30  E8 8B B1    E5 B0 BA    E9 AB 98
```

旧循环会老老实实地跑 11 次，把 `E8`、`8B`、`B1`、`E5`、`B0`、`BA`、`E9`、`AB`、`98` 这 9 个字节**各自当成一个独立的字符**去查字图。前两次迭代取到的是 `0x35` 和 `0x30`，也就是数字 `5` 和 `0`，这两个是合法 ASCII，能正常查到字形。后面 9 次迭代取到的，全是某个汉字的 UTF-8 编码片段——它们单独拿出来根本不是一个合法的字符。

这就是“数字能显示、单位消失”的第一层原因：循环从头到尾就没有把 `英`、`尺`、`高` 当作三个完整的字来处理过，而是把它们拆成了 9 个谁也不认识的碎片。

## 为什么是“只剩数字”，而不是崩溃或者乱码

光说“按字节拆开了”还不够解释现象。如果真按一个非法字符去查字图，按理说可能画出一个豆腐块、一个问号，或者干脆崩掉。为什么实际看到的是干干净净地“只剩数字”，中文部分像被橡皮擦掉了一样？

要回答这个问题，得看 `GetCharData` 在拿到一个它不认识的字符时会干什么。它的实现在 `ImageFont.cpp` 里：

```cpp
CharData* FontLayer::GetCharData(char32_t theChar)
{
    auto anItr = mCharDataMap.find(theChar);
    if (anItr == mCharDataMap.end())
    {
        anItr = mCharDataMap.insert(CharDataMap::value_type(theChar, CharData())).first;
    }
    return &anItr->second;
}
```

它**永远不会返回空指针**。如果请求的字符不在字形表里，它会就地插入一个默认构造的 `CharData`，然后把这个默认值返回给你。而一个默认的 `CharData`，`mWidth` 是 0、`mOffset` 是 `(0, 0)`、`mOrder` 也是 0——全是零。

于是那 9 个 UTF-8 碎片各自触发了这条路径：每来一个碎片，`GetCharData` 就给它造一个宽度为 0 的默认字形。宽度是 0，意味着光标的水平位置 `aCurXPos` 基本不往前走；偏移是 0，意味着绘制位置也算不出什么有意义的结果。换句话说，这些碎片对应的“字形”在逻辑上是存在的，但它们既占不了位置、也画不出东西。

更要命的是后面那一行源矩形的查找：

```cpp
aRenderCommand->mSrc[0] = aKernItr->mScaledCharImageRects.find(aChar)->second.mX;
```

这里直接对 `find(aChar)` 的结果取 `->second`，**完全没有判断迭代器是不是 `end()`**。对于那些碎片字节 `aChar`，`mScaledCharImageRects` 里当然找不到对应的项，`find` 返回的就是 `end()`。对一个 `end()` 迭代器解引用取 `->second`，这是标准的未定义行为。实际跑出来，这条渲染命令携带的源矩形就是一堆垃圾值——要么指向字体贴图里某个莫名其妙的角落，要么干脆是一个空矩形。无论哪种，都不会在屏幕上画出 `英`、`尺`、`高`。

所以整条链路串起来是这样的：

- 数字 `5`、`0` 是合法 ASCII，能查到真实字形和真实源矩形，正常绘制，光标正常前进；
- 后面 9 个中文编码碎片各自被当成独立字符，拿到的是宽度为 0 的默认字形，光标不前进，全部堆在“50”后面同一个位置；
- 这些碎片又触发了不安全的 `find()->second` 解引用，渲染命令带的是垃圾源矩形，画不出任何有意义的内容。

最终呈现在玩家眼前的，就是一个孤单的“50”，单位部分悄无声息地消失了。没有崩溃，没有乱码，恰恰是这种“安静”让这个 bug 特别难察觉——如果不是正好在智慧树这种“数字+单位”混排的场景下，光靠肉眼扫一遍界面，很可能就漏过去了。

这也解释了为什么修复必须是**两处改动一起上**，只改一处都不够。

## 修复：逐码点解码，再加一道防线

修复后的循环换成了逐码点解码：

```cpp
size_t aDecodeOffset = 0;
char32_t aCurRawChar = 0;
char32_t aNextRawChar = 0;
bool aHasCur = UTF8DecodeNext(aFinalString, aDecodeOffset, aCurRawChar);
while (aHasCur)
{
    const bool aHasNext = UTF8DecodeNext(aFinalString, aDecodeOffset, aNextRawChar);
    const char32_t aChar = aFont->GetMappedChar(aCurRawChar);
    const char32_t aNextChar = aHasNext ? aFont->GetMappedChar(aNextRawChar) : 0;
    // ...
    CharData* aCharData = aLayer->GetCharData(aChar);
    auto aRectItr = aKernItr->mScaledCharImageRects.find(aChar);
    if (aRectItr == aKernItr->mScaledCharImageRects.end())
        continue;
    // ...
    aRenderCommand->mSrc[0] = aRectItr->second.mX;
    // ...
    aCurRawChar = aNextRawChar;
    aHasCur = aHasNext;
}
```

第一处改动是把“按字节取下标”换成“用 `UTF8DecodeNext` 逐码点解码”。`UTF8DecodeNext` 是三月那次改造里就抽出来的公共函数，每次调用会吃下一个完整的 UTF-8 码点（无论它是 1 字节还是 3 字节），推进偏移量，并把解码出的 `char32_t` 写回来。这样一来，`英` 就是完整的 `U+82F1`、`尺` 就是完整的 `U+5C3A`、`高` 就是完整的 `U+9AD8`，作为完整的 `char32_t` 交给 `GetMappedChar` 和 `GetCharData`，自然能查到中文字形表里真实存在的那个字。循环的迭代次数也从“字节数”变成了真正的“字符数”。

第二处改动是给源矩形查找加一道 `end()` 判断：

```cpp
auto aRectItr = aKernItr->mScaledCharImageRects.find(aChar);
if (aRectItr == aKernItr->mScaledCharImageRects.end())
    continue;
```

这一改初看好像只是顺手加的防御性代码，但其实它和第一处改动是互补的。第一处改动保证“正常的字符一定能查到正确的字图”；第二处改动保证“万一字体里真的缺了某个字形，也不会再去解引用 `end()`”。即便解码完全正确，字体文件本身也可能没有收录某个生僻字或某个 emoji——这种情况下 `find` 依然会返回 `end()`。没有这道判断，那个缺失的字形就会再次触发未定义行为。有了这道判断，缺失的字形会被安静地跳过，而不是带着一堆垃圾源矩形坐标闯进渲染队列。

两处改动合在一起，才同时解决了“中文单位显示不出来”和“缺字时可能 UB”这两个问题。PR 标题里写的“support UTF-8 decoding **and** safe rect lookup”，说的正是这两件事，缺一不可。

修完之后再用中文资源包看智慧树，`50英尺高` 完整地显示在头顶，弹跳动画也正常。数字和单位一起出现，终于和原版一致了。

## 同样的坑不止这一处

按字节索引字符串这个毛病，并不只藏在 `TodDrawStringMatrix` 里。在排查这个问题的同一天，笔者顺手把另外两处类似的遗漏也一起修了：一处是 `MessageWidget` 里“一大波僵尸”那种逐字飞入的字幕动画，它原本按字节给每个“字符”创建动画；另一处是 `ChallengeScreen` 的挑战按钮文字换行，原本用 `size()` 判断是否该换行、用字节位置去找切分的空格。它们的根因和智慧树这个 bug 同出一源——都是把 `std::string` 的下标当成了字符下标。

这里就不展开讲了，否则这篇文章会变成一份更新日志。想说明的是：字体层 `char32_t` 化只是 Unicode 支持的第一步。真正容易藏污纳垢的，是那些**直接拿字符串下标干活**的上层代码——测宽、换行、切片、逐字动画，每一处都可能暗自假设“一个字节等于一个字符”。这个假设在纯 ASCII 时代成立，一旦文本里出现多字节字符，就会在某个角落悄悄爆掉。

## 结语

这个 bug 本身不大，修复也就改了几十行代码，但它把几个值得记住的点浓缩在了一起。

`std::string::size()` 返回的是字节数，不是字符数。只要字符串里可能有 UTF-8 多字节序列，任何用下标遍历字符串的代码都值得重新审视一遍——尤其是那些写成 `for (i < str.size())` 然后 `str[i]` 的循环。这类写法不会立刻出错，会一直安静地正常工作，直到某天撞上一段非 ASCII 文本。

更隐蔽的是“静默失败”这一类。`GetCharData` 那种“找不到就插个默认值”的设计，配合上不判 `end()` 的 `find()->second`，把一个本该暴露出来的错误变成了“安静地少画几个字”。没有崩溃、没有报错，单靠测试用例很难抓到，往往要等到某个特定语言、某个特定界面、某个特定进度下才会露出马脚。智慧树身高偏偏就是这样一个“非英语 + 后期进度”的小众组合。

再往外一层看，国际化始终是个长尾工程。把字体渲染改成 `char32_t` 只是开了个头，真正的工作量在于把散落在代码库各处的“字节假设”逐一找出来、改干净。每一次以为“应该都改完了吧”的时候，多半还有一两处漏网之鱼，安静地等在某个不常走的代码路径上。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
