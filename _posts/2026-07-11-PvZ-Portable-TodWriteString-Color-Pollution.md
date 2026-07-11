---
layout:       post
title:        PvZ-Portable：修复图鉴里提前标红的文字
subtitle:     一次本不该改变任何状态的宽度测量，把行尾的颜色标签渗回了行首
header-img:   img/games/bg-pvz-portable.webp
date:         2026-07-11
author:       wszqkzqk
catalog:      true
tags:         文本渲染 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

有玩家在 issue [#334](https://github.com/wszqkzqk/PvZ-Portable/issues/334) 里报告了一个中文版图鉴的显示问题：用中文版（1.1.0.1056 Chinese GOTY）资源包打开图鉴看豌豆射手，描述文字的着色**提前了一行**——介绍段落的最后一行整行变成了红色，而按原版的表现，红色应该从下面属性部分的数值才开始出现。

这个 bug 的触发条件相当苛刻：必须用中文资源包，而且文本经过自动换行之后，恰好有一个颜色标签落在某一行的行尾。英语、德语资源包跑出来全都正常，所以它一直藏到了现在。顺着这条线索查下去，最后定位到的是文本绘制函数 `TodWriteString` 里一次看似人畜无害的**宽度测量**。

## 内联格式标签及其处理流程

PvZ 的文本资源（`LawnStrings.txt`）支持内联格式标签，用花括号标记，比如图鉴描述里的 `{FLAVOR}`（植物介绍文字）、`{KEYWORD}`（属性名）、`{STAT}`（属性数值）。引擎里有一张格式表（`src/Sexy.TodLib/TodStringFile.cpp`）：

```cpp
TodStringListFormat gLawnStringFormats[12] = {
	{ "NORMAL",           nullptr,    Color(40,   50,     90,     255),       0,      0U },
	{ "FLAVOR",           nullptr,    Color(143,  67,     27,     255),       0,      1U },
	{ "KEYWORD",          nullptr,    Color(143,  67,     27,     255),       0,      0U },
	// ...
	{ "STAT",             nullptr,    Color(204,  36,     29,     255),       0,      0U },
	// ...
};
```

每个格式项携带字体、颜色、行距偏移和一组标志位。绘制时，这些标签的效果全部体现在一个共享的格式状态对象 `TodStringListFormat` 上——`TodWriteStringSetFormat` 按名字查表，然后**就地修改**传入的状态：

```cpp
void TodWriteStringSetFormat(const char* theFormat, TodStringListFormat& theCurrentFormat)
{
	for (int i = 0; i < gTodStringFormatCount; i++)
	{
		const TodStringListFormat& aFormat = gTodStringFormats[i];
		if (strncmp(theFormat, aFormat.mFormatName, strlen(aFormat.mFormatName)) == 0)
		{
			if (aFormat.mNewFont != nullptr)
				theCurrentFormat.mNewFont = aFormat.mNewFont;
			if (aFormat.mNewColor != Color(0, 0, 0, 0))
				theCurrentFormat.mNewColor = aFormat.mNewColor;
			theCurrentFormat.mLineSpacingOffset = aFormat.mLineSpacingOffset;
			theCurrentFormat.mFormatFlags = aFormat.mFormatFlags;
			return;
		}
	}
}
```

也就是说，文本绘制本质上是一个状态机：扫描字符串，普通字符攒进缓冲区，遇到 `{XXX}` 就切换当前颜色/字体，然后把之前攒下的字符用切换前的状态画出去。颜色流向哪里，完全由标签出现的顺序决定。这套机制本身没问题，但它有一个隐含的前提：**谁在什么时候推进这个状态，必须严格受控**。

## 按行绘制机制

带自动换行的文本走的是 `TodDrawStringWrappedHelper`：它逐码点扫描全文、累加宽度，超宽时在最近的断行点把当前行切出来，交给 `TodWriteString` 真正绘制。图鉴里植物描述的调用点在 `AlmanacDialog.cpp`：

```cpp
TodDrawStringWrapped(g, aDescriptionName, Rect(485, 309, 258, 230),
	Sexy::FONT_BRIANNETOD12, Color(40, 50, 90), DS_ALIGN_LEFT);
```

值得注意的是，换行扫描阶段遇到格式标签时，代码会刻意把颜色**还原**回去：

```cpp
Color aExistingColor = aCurrentFormat.mNewColor;
TodWriteStringSetFormat(aFormat, aCurrentFormat);
aCurrentFormat.mNewColor = aExistingColor;   // 换行扫描只关心字体和行距，颜色不留痕迹
```

这样做的结果是：每一行被切出来单独绘制时，都从行首重新应用行内标签，行首到第一个标签之间的文字使用基准色（图鉴里是深蓝 `Color(40, 50, 90)`）。由此可以推出一条很重要的性质：**一个落在行尾、后面已经没有任何字符的标签，对画面应该毫无影响**——它切换的颜色没有文字可用。

而中文版豌豆射手的描述文字，介绍段落恰好以 `…{STAT}\n` 收尾：`{STAT}` 标签就紧挨着换行符。按上面的分析，这个标签本该不起任何作用，可实际表现却是它所在的整一行都红了。

## 根因：测宽的递归调用

问题出在 `TodWriteString` 的开头。为了支持右对齐和居中对齐，函数在真正绘制之前需要先知道这一行画出来有多宽，于是它**递归调用自己**进行测量——`drawString=false` 表示只量宽度、不画字：

```cpp
int TodWriteString(Graphics* g, const std::string& theString, int theX, int theY,
	TodStringListFormat& theCurrentFormat, int theWidth,
	DrawStringJustification theJustification, bool drawString, int theOffset, int theLength)
{
	_Font* aFont = *theCurrentFormat.mNewFont;
	if (drawString)
	{
		int aSpareX = theWidth - TodWriteString(g, theString, theX, theY,
			theCurrentFormat, theWidth, DrawStringJustification::DS_ALIGN_LEFT,
			false, theOffset, theLength);   // ← 测量：同一个 theCurrentFormat，按引用传进去
		switch (theJustification)
		{
		// ... 右对齐/居中：theX += aSpareX 或 aSpareX / 2
		}
	}
	// ... 逐字符扫描，遇标签调用 TodWriteStringSetFormat(theCurrentFormat)
}
```

看参数表：`theCurrentFormat` 是 `TodStringListFormat&`，**按引用传入**。测量那次递归拿到的，和后面真正绘制用的是同一个状态对象。

再看主循环里处理标签的分支（`drawString` 只守护了 `DrawString` 这一步）：

```cpp
if (drawString)
	aFont->DrawString(g, theX + aXOffset, theY, aString, theCurrentFormat.mNewColor, g->mClipRect);
aXOffset += aFont->StringWidth(aString);
aString.assign("");
TodWriteStringSetFormat(aFormatStart + 1, theCurrentFormat);   // ← 测量时照样执行
```

`drawString=false` 只是不调用 `DrawString`，但 `TodWriteStringSetFormat` 照跑不误。于是测量过程会把行内所有标签**全部推进一遍**：等测量返回时，`theCurrentFormat.mNewColor` 已经停在了这一行最后一个标签的颜色上。

现在把豌豆射手那一行代进去走一遍。这一行（换行切分后）的内容是“介绍文字……`{STAT}`”。`TodWriteString` 以 `drawString=true` 被调用时，`mNewColor` 还是基准的深蓝色；但进入 `if (drawString)` 分支后先跑递归测量，测量会扫描完整行、依次应用行内标签，扫到行尾的 `{STAT}` 时，共享的 `mNewColor` 就被推进成了红色 `Color(204, 36, 29)`。测量返回、拿到宽度之后（左对齐下这个宽度其实根本不会被用到），才开始真正的绘制：行首的介绍文字位于第一个标签之前，本应用基准色画出，可此时 `mNewColor` 已经是 `{STAT}` 的红色——于是这一整行都被画成了红色。

红字就这样提前了一行。而英文版之所以没事，是因为英文描述文本在 `{FLAVOR}` 段落之后没有这种落在行尾的行内颜色标签，测量跑完 `mNewColor` 纹丝不动，污染自然无从谈起。再加上英文按空格断行、中文按任意 CJK 字符断行，换行位置完全不同，就算有标签也未必恰好落在行尾——多种条件叠加，这个 bug 成了中文版独有的现象。

顺带一提，这段代码还有一个不算 bug 但同样扎眼的问题：左对齐（`DS_ALIGN_LEFT`）时 `aSpareX` 压根不会被用到，可旧代码对**所有**对齐方式都无条件测量一遍。也就是说图鉴这种纯左对齐的文本，每行都白跑一次完整的扫描，唯一的收获就是把格式状态搞脏。

## 修复：让测量没有副作用

修复后的代码把两件事一起做了：

```cpp
if (drawString)
{
	const auto aMeasureSpareX = [&]() -> int {
		TodStringListFormat aMeasureFormat = theCurrentFormat;   // 测量用本地副本
		return theWidth - TodWriteString(g, theString, theX, theY,
			aMeasureFormat, theWidth, DrawStringJustification::DS_ALIGN_LEFT,
			false, theOffset, theLength);
	};
	switch (theJustification)
	{
	case DrawStringJustification::DS_ALIGN_RIGHT:
	case DrawStringJustification::DS_ALIGN_RIGHT_VERTICAL_MIDDLE:
		theX += aMeasureSpareX();
		break;
	case DrawStringJustification::DS_ALIGN_CENTER:
	case DrawStringJustification::DS_ALIGN_CENTER_VERTICAL_MIDDLE:
		theX += aMeasureSpareX() / 2;
		break;
	default:
		break;   // 左对齐：根本不测量
	}
}
```

第一处改动：测量传入的是 `theCurrentFormat` 的**本地拷贝** `aMeasureFormat`。标签推进随便推，反正改的是副本，函数返回后即销毁，绘制用的状态干干净净。

第二处改动：把测量包进一个 lambda，只在右对齐和居中两个分支里调用。左对齐不再触发测量，既省掉了每行一次的冗余扫描，也从结构上杜绝了测了但没用、只剩副作用这类代码再次出现的土壤。

两处改动合起来，测量的语义从顺带把状态也推一遍，变成了纯粹的问一个宽度、什么都不改变。改完之后用中文资源包看图鉴，豌豆射手的介绍文字恢复了正常的颜色，红色从属性数值那一行才开始出现，与原版一致。

## 结语

这个 bug 不大，修复也就改了十几行，但它踩中的坑可以记录一下。

**测量必须是无副作用的。** 文本排版里先量一遍再画一遍是常见模式，而这里测量和绘制复用了同一段带状态的扫描代码，共享同一个按引用传入的状态对象。`drawString=false` 这个开关只挡住了最显眼的 `DrawString` 调用，却没挡住状态推进——于是本应只读的测量悄悄写改了共享状态。这类问题最阴险的地方在于它不会崩、不会报错，只会安静地画错颜色，而且要等到特定语言、特定文本、特定换行位置三者凑齐才会现身。

**按引用传参掩盖了这种耦合。** 测量那次调用的返回值只是一个宽度，从调用现场完全看不出它顺手把调用方的格式状态也改了——`theCurrentFormat` 以引用形式混在一堆参数中间，修改又是通过递归调用间接发生的，读代码时很容易一晃而过。假如测量函数要么按值传参（修改只落在副本上），要么把推进后的状态作为返回值交出来，这个副作用都会显眼得多。实际上，给这类测量或预览性质的调用一份独立的状态副本，成本几乎为零，却能避免像这次这样跨语言才现身的诡异 bug。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
