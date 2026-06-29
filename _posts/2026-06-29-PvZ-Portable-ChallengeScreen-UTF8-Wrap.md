---
layout:       post
title:        PvZ-Portable：挑战页的中文标题为什么往上跑——把字节数当成字符数的换行误判
subtitle:     一个 6 字的中文挑战名有 18 个字节，size() 让它被误判成长标题，画到了不该在的位置
header-img:   img/games/bg-pvz-portable.webp
date:         2026-06-29
author:       wszqkzqk
catalog:      true
tags:         UTF-8 国际化 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

上一篇聊了智慧树身高只报数字不报单位的问题，根因是 `TodDrawStringMatrix` 按字节遍历 UTF-8 字符串。其实就在差不多的时间，笔者还在 [PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable) 中因为同一个字节假设发现了另一个坑。

社区用户在 Issue [#328](https://github.com/wszqkzqk/PvZ-Portable/issues/328) 里报告：装上中文年度增强版（1.1.0.1056）的资源包后，打开“小游戏 / 生存 / 谜题”这几个挑战页面，会发现有些按钮标题在格子里往上飘，没有垂直居中：

> `src\Lawn\Widget\ChallengeScreen.cpp` 465 行，`string size` 不会返回字符数，这导致返回的数字通常大于自动换行的数字，然后就会在不该换行时换行。

能在报 bug 的时候顺手把出错的文件、行号和原因一起写出来，这种 Issue 对维护者来说十分友好。笔者顺着这个线索看了一下，确实如此，而且同一份代码里还藏着第二个相关的隐患。修复合并在 PR [#330](https://github.com/wszqkzqk/PvZ-Portable/pull/330)，核心提交是 [906530c](https://github.com/wszqkzqk/PvZ-Portable/commit/906530c2f819f103c41ef50656acf9b79fc54cdf)。这篇就单讲挑战按钮标题换行这一件事。

## 挑战按钮的标题是怎么排版的

挑战选择界面（`ChallengeScreen`）上每个模式都是一个按钮，按钮上要画这个模式的名字。名字有长有短，引擎的处理方式是分两档：

- 短名字就单行画在按钮中央；
- 长名字就在中间找个空格切成两行，分别画在偏上和偏下的位置。

判断“长还是短”的阈值从属性文件里读，键名叫 `CHALLENGE_SCREEN_BUTTON_AUTO_WRAP_NUM`，默认是 13。也就是说，名字“长度”小于 13 就单行居中，大于等于 13 就走两行切分。这个阈值之所以做成可配置，是因为不同语言的文本长度差异很大，三月做[多语言支持](https://wszqkzqk.github.io/2026/03/01/PvZ-Portable-Multilingual-Support/)的时候就把它放进了 `Layout.xml`，方便各语言版本自己调。

问题出在“长度”这两个字上。来看看修复前 `ChallengeScreen::DrawButton` 里相关的代码：

```cpp
int aNameLen = aName.size();
int aAutoWrapNum = mApp->GetInteger("CHALLENGE_SCREEN_BUTTON_AUTO_WRAP_NUM", 13);
if (aNameLen < aAutoWrapNum)
{
    TodDrawString(g, aName, aPosX + 52, aPosY + 96, Sexy::FONT_BRIANNETOD12, aTextColor, DS_ALIGN_CENTER);
}
else
{
    int aHalfPos = (mPageIndex == CHALLENGE_PAGE_SURVIVAL && !aChallengeButton->mDisabled) ? 7 : (aNameLen / 2 - 1);
    const char* aSpacedChar = strchr(aName.c_str() + aHalfPos, ' ');
    if (aSpacedChar == nullptr)
    {
        aSpacedChar = strchr(aName.c_str(), ' ');
    }

    int aLine1Len = aNameLen;
    int aLine2Len = 0;
    if (aSpacedChar != nullptr)
    {
        aLine1Len = aSpacedChar - aName.c_str();
        aLine2Len = aNameLen - aLine1Len - 1;
    }

    TodDrawString(g, aName.substr(0, aLine1Len), aPosX + 52, aPosY + 88, Sexy::FONT_BRIANNETOD12, aTextColor, DS_ALIGN_CENTER);
    if (aLine2Len > 0)
    {
        TodDrawString(g, aName.substr(aLine1Len + 1, aLine2Len), aPosX + 52, aPosY + 102, Sexy::FONT_BRIANNETOD12, aTextColor, DS_ALIGN_CENTER);
    }
}
```

注意两处 y 坐标：单行居中时画在 `aPosY + 96`，两行布局时第一行画在 `aPosY + 88`、第二行画在 `aPosY + 102`。也就是说，单行和两行这两种情况，文字出现的位置本来就不一样——单行的基准线比两行布局的第一行要低 8 个像素。这个细节后面很关键。

## 一个 6 字的中文名为什么被当成长标题

`aName.size()` 返回的是字节数，不是字符数。这一点和上一篇智慧树那个 bug 如出一辙，只不过这次的受害者是换行判断。

拿一个典型的中文挑战名来说，假设它叫“植物僵尸”——4 个汉字。在 UTF-8 里每个汉字占 3 个字节，所以这个名字实际占 12 个字节。再长一点的，比如 6 个汉字的名字，就是 18 个字节。

按字符数算，4 个字、6 个字都远小于 13 的阈值，本该走单行居中分支。但 `size()` 看到的是 12、18 这些字节数——6 个汉字的名字直接超过 13，被一刀切进了“长标题”分支。

进了两行分支之后，代码试图在名字后半段找一个空格来切分。可中文名字里哪有空格？`strchr` 从 `aHalfPos` 开始找，找不到；再从头找一遍，还是找不到。于是 `aSpacedChar` 是空指针，`aLine1Len` 保持为整个 `aNameLen`，`aLine2Len` 是 0。

最后的结果就是：这个本该单行居中的短名字，被完整地画在了 `aPosY + 88` 的位置——也就是两行布局里**第一行**的位置。它比真正居中时高了 8 个像素，而且第二行什么都没有。

这就是 Vector-Syobon-812 看到的“标题在格子里向上对齐”。文字没有真的“向上对齐”任何东西，它只是被错误地画到了一个本不属于它的、偏上的基线位置。看起来像是排版对齐出了问题，实际上是长度判断把字节数当成了字符数，导致一个短名字被错误地送进了两行布局。

报告里那句“返回的数字通常大于自动换行的数字，然后就会在不该换行时换行”，说的就是这个过程，一语中的。

## 顺手修掉的第二个隐患

光是“该不该换行”这一处用字节数还不够。在确实需要切分成两行的那条路径上，代码还有第二个按字节干活的地方。

`aHalfPos` 是“从名字中间往后找空格”的起点，旧代码这么算：

```cpp
int aHalfPos = (mPageIndex == CHALLENGE_PAGE_SURVIVAL && !aChallengeButton->mDisabled) ? 7 : (aNameLen / 2 - 1);
const char* aSpacedChar = strchr(aName.c_str() + aHalfPos, ' ');
```

`aNameLen / 2` 是字节长度的一半。对于一个中英文混杂或者纯中文的名字，这个“一半”很可能落在某个汉字的三字节编码中间。然后 `strchr(aName.c_str() + aHalfPos, ' ')` 就会从这个字节位置开始往后扫描空格。

从多字节字符的中间开始扫描，本身不一定会出错——毕竟空格是 ASCII，扫描逻辑只是在找 `0x20`。但问题在于，`aHalfPos` 这个“中间点”的语义已经歪了：你以为你在“字符串中点”附近找切分，实际上这个中点是按字节算的，和真正的字符中点相差甚远。对于某些长度接近阈值、又恰好带空格的混合名字，这个偏差会让切分点落在一个很别扭的位置。

这也是 commit 信息里“find the line split at a space by code-point index, so multi-byte names no longer wrap or split mid-character”对应的那一半——既不要在不该换行时换行，也不要把多字节字符从中间劈开。

## 修复：判断按字符数，切片按字节

修复后的代码把“字符数”和“字节位置”分得很清楚。先单独数一遍字符数，专门用来判断该不该换行：

```cpp
int aNameCharLen = 0;
for (size_t aOffset = 0; ; )
{
    char32_t aChar = 0;
    if (!UTF8DecodeNext(aName, aOffset, aChar))
        break;
    aNameCharLen++;
}

const int aAutoWrapNum = mApp->GetInteger("CHALLENGE_SCREEN_BUTTON_AUTO_WRAP_NUM", 13);
if (aNameCharLen < aAutoWrapNum)
{
    TodDrawString(g, aName, aPosX + 52, aPosY + 96, Sexy::FONT_BRIANNETOD12, aTextColor, DS_ALIGN_CENTER);
}
```

这里用 `UTF8DecodeNext` 把整个字符串扫一遍，每完整解出一个字符就把计数器加一，最后得到的 `aNameCharLen` 是真正的字符数。拿它和阈值 13 比较，6 个汉字就是 6，不会再被当成 18。

如果确实需要切分成两行，切分逻辑也改成按字符索引走：

```cpp
const int aHalfPosChar = (mPageIndex == CHALLENGE_PAGE_SURVIVAL && !aChallengeButton->mDisabled) ? 7 : (aNameCharLen / 2 - 1);
size_t aSplitBytePos = std::string::npos;
size_t aFallbackSpacePos = std::string::npos;
{
    size_t aOffset = 0;
    char32_t aChar = 0;
    int aCharIdx = 0;
    while (true)
    {
        const size_t aCharStart = aOffset;
        if (!UTF8DecodeNext(aName, aOffset, aChar))
            break;
        if (aChar == U' ')
        {
            if (aCharIdx >= aHalfPosChar)
            {
                aSplitBytePos = aCharStart;
                break;
            }
            if (aFallbackSpacePos == std::string::npos)
                aFallbackSpacePos = aCharStart;
        }
        aCharIdx++;
    }
    if (aSplitBytePos == std::string::npos)
        aSplitBytePos = aFallbackSpacePos;
}
```

这一段是这次修复里最有意思的部分，值得多说两句。

切分点的“中点”现在按字符算，`aHalfPosChar = aNameCharLen / 2 - 1`，是第几个字符，不再是第几个字节。扫描也是逐字符进行的，遇到空格时，用当前字符的序号 `aCharIdx` 和中点比较——这就保证了“找后半段的空格”是按字符位置来理解“后半段”的。

但 `std::string::substr` 吃的是字节位置，不是字符序号。所以光知道“第 N 个字符后面有个空格”还不够，还得知道这个空格在原字符串里是第几个字节。这就是 `aCharStart` 的用处：每次进入循环、在 `UTF8DecodeNext` 推进偏移量之前，先把当前字符的起始字节位置记下来。一旦找到合适的空格，记下来的就是这个空格字符的字节位置 `aSplitBytePos`。

最后切字符串的时候，用的还是字节位置：

```cpp
int aLine1Len;
int aLine2Len;
if (aSplitBytePos != std::string::npos)
{
    aLine1Len = aSplitBytePos;
    aLine2Len = aName.size() - aSplitBytePos;
    if (aName[aSplitBytePos] == ' ')
        aLine2Len--;
}
else
{
    aLine1Len = aName.size();
    aLine2Len = 0;
}

TodDrawString(g, aName.substr(0, aLine1Len), aPosX + 52, aPosY + 88, ...);
if (aLine2Len > 0)
{
    const int aLine2Offset = (aName[aSplitBytePos] == ' ') ? aSplitBytePos + 1 : aSplitBytePos;
    TodDrawString(g, aName.substr(aLine2Offset, aLine2Len), aPosY + 52, aPosY + 102, ...);
}
```

`aLine1Len` 是第一行的字节长度，`aLine2Len` 是第二行的字节长度，`substr` 用这两个字节数把原串切成两段。如果切分点本身是个空格，就把这个空格从第二行开头剔掉，免得第二行以一个空格起头。

这套写法的核心思路可以概括成一句话：**逻辑判断用字符数，字符串切片用字节位置，中间靠“记录每个字符的起始字节”来搭桥。** 这正是处理 UTF-8 文本时最容易绕晕、也最容易写对的地方——你不能指望字符序号和字节下标是同一套东西，必须显式地在两者之间转换。

顺带一提，“生存模式”那一页有个特例：`aHalfPosChar` 直接固定成 7。这是因为生存模式的挑战名都带一个公共前缀（英文版是 `Survival: ...`），切成两行时希望第一行刚好是这个前缀，所以把切分起点钉在前缀末尾。这个“7”本身也是按字符算的，对中文版同样成立——只要前缀的字符数对得上就行。

`906530c` 这个提交其实一并改了两个文件，除了 `ChallengeScreen`，还有 `MessageWidget`。后者管的是游戏里那种“一大波僵尸正在接近”的逐字飞入字幕——每个字是一个独立的小动画，按顺序错开时间飞进来。

旧实现同样是按字节遍历字幕字符串：每读一个字节就创建一个动画、按字节序号错开时间、最后再把单个字节喂给字体去画。对纯英文没问题，对中文就会把一个字拆成好几个“动画”，各自乱飞。根因和挑战按钮这个 bug 同出一源，都是把字符串下标当成了字符序号。

## 结语

这个 bug 的修复本身不算复杂，但踩出来的几个点挺值得记下来。

`std::string::size()` 返回的是字节数，这句话每个写 C++ 的人都背得出来。可只要字符串里可能混进 UTF-8 多字节字符，那些“拿 `size()` 当长度、拿 `str[i]` 当下标”的写法就都是定时炸弹——不会立刻炸，而是一直安静地正常工作，直到某一天有人装上中文资源包、打开某个特定页面，才发现标题全往上跑了。

更深一点的收获，是“字符逻辑”和“字节存储”要分开。这次修复最干净的地方，就是把“该不该换行”“在哪换行”这些判断全部搬到字符层面来做，只有到最后真正调用 `substr` 切字符串的时候，才落到字节位置上；两层之间靠“记下每个字符的起始字节”来衔接。处理 UTF-8 文本时这套模式几乎处处用得上，值得形成肌肉记忆。

最后还想夸一下报 bug 的人。Vector-Syobon-812 的报告不但描述了现象、给了复现步骤，还直接定位到了文件、行号和根因，把一个本来可能要来回沟通好几轮才能复现的问题，变成了“看一眼就懂、顺手就修”的小事。一份好的 bug 报告本身就是对项目很实在的贡献。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
