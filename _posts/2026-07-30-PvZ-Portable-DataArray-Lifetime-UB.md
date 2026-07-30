---
layout:       post
title:        PvZ-Portable：治理 DataArray 的对象生命周期 UB
subtitle:     重写管理所有游戏实体的对象池以消除UB
header-img:   img/games/bg-pvz-portable.webp
date:         2026-07-26
author:       wszqkzqk
catalog:      true
tags:         未定义行为 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

PvZ 里每一只僵尸、每一株植物、每一颗子弹、每一个粒子，生命周期都归同一个容器管：`DataArray<T>`。这是 PopCap 当年引擎框架里的对象池，游戏里所有短生命周期的实体对象都在它的池子里分配和回收。它是一套专门为游戏对象设计的 ID 句柄系统——外部拿到的不是指针，只能使用一个 `unsigned int` 的 ID，高位是递增的 key，低位是池内下标；对象释放后槽位复用、key 递增，旧 ID 随之失效，查询时能识别出这类悬空句柄。

这个设计本身相当扎实，当年的工程直觉到今天也不过时。但它的**实现**，用现代 C++ 的眼光看，几乎每一步都是未定义行为：在从未构造过的对象上读写成员、靠 `reinterpret_cast` 在两个类型之间来回强转、对已析构的对象继续写字段……这些 UB 在当年的编译器上跑得起来，就这么一路跑到了今天。

笔者最近在修复分支 [`fix/dataarray-ub-init`](https://github.com/wszqkzqk/PvZ-Portable/tree/fix/dataarray-ub-init) 上把这个容器彻底重写了一遍（共 8 个 commit），把所有生命周期 UB 清理干净，同时守住两条硬约束：**存档字节布局一个字节都不能变，游戏 RNG 流一个值都不能变**。过程中最能说明问题的一次验证是：笔者手工构造了一份带野指针的存档，实测出未修复的代码会在读档后对**写档进程留下的野指针**执行析构，当场段错误。

这篇博客就讲这一个容器的故事。

## 旧实现：每一步都是 UB

先看池子是怎么分配的（`src/Sexy.TodLib/DataArray.h`，修复前）：

```cpp
class DataArrayItem
{
public:
	T					mItem;
	unsigned int		mID;
};

void DataArrayInitialize(unsigned int theMaxSize, const char* theName)
{
	mBlock = static_cast<DataArrayItem*>(operator new(sizeof(DataArrayItem) * theMaxSize));
	...
}
```

`operator new` 分配的是一块**原始内存**，上面没有任何对象。但从这一行返回开始，代码就把它当成 `DataArrayItem*` 数组来用——下标、取成员、指针算术，全在一群从未开始生命周期的对象上进行。

再看分配一个槽位时发生了什么：

```cpp
DataArray<T>::DataArrayItem* aNewItem = &mBlock[aNext];
memset(aNewItem, 0, sizeof(DataArrayItem));
aNewItem->mID = (mNextKey++ << DATA_ARRAY_KEY_SHIFT) | aNext;
...
new (aNewItem)T();
return reinterpret_cast<T*>(aNewItem);
```

`memset` 清零之后，只有 `T` 被 placement-new 了出来——**`DataArrayItem` 本身从头到尾没有被构造过**，可它的 `mID` 成员却照样被写入。释放时更甚：

```cpp
void DataArrayFree(T* theItem)
{
	DataArrayItem* aItem = reinterpret_cast<DataArrayItem*>(theItem);
	...
	theItem->~T();
	unsigned int anId = aItem->mID & DATA_ARRAY_INDEX_MASK;
	aItem->mID = mFreeListHead;   // 在已析构的对象上写空闲链表指针
	mFreeListHead = anId;
	mSize--;
}
```

`theItem->~T()` 之后，槽位里的对象已经析构，紧接着却又往它的 `mID` 里写空闲链表链接。整个池子的空闲槽位链表，是靠读写一群已析构对象的成员来维持的。

类型层面同样不合法。`DataArrayItem` 比 `T` 多一个尾部成员，代码却在 `T*` 和 `DataArrayItem*` 之间直接 `reinterpret_cast` 来回转——转回去的那次，指针指向的地址上根本不存在一个 `DataArrayItem` 对象；迭代器也是靠 `reinterpret_cast` 之后做指针递增来扫描池子。另外 `DataArrayGet` 里还藏着一个更朴素的坑：

```cpp
return &mBlock[static_cast<short>(theId)].mItem;
```

`theId` 是 `unsigned int`，这里直接截断成 `short` 再取下标。池子容量没超过 32767 的时候不会出问题，但这个 cast 的存在本身就说明写这段代码时没人认真考虑过边界。

简单说：这个容器能正常工作，靠的不是它的实现合法，而是它非法得足够稳定。

## 修复：先让槽位成为真正的对象

修复的思路一句话就能说完：**让数组里的每一个槽位，在任何时候都有一个生命周期内的、值初始化的对象**。存储改成两个 RAII 数组成员：

```cpp
// Value-initialization zeroes T's members only while this constructor stays implicit.
struct DataArrayItem : T {};

std::unique_ptr<DataArrayItem[]>	mItems;
std::unique_ptr<unsigned int[]>		mItemIds;
```

`DataArrayItem` 从包裹 `T` 改成继承 `T`，这是保住内存布局的关键——继承后 `T` 的地址就是 `DataArrayItem` 的地址，`DataArrayFree` 里从 `T*` 找回槽位只需要一次 `static_cast` 加指针算术，不再需要 `reinterpret_cast`。`mID` 则干脆拆出去，放进独立的 `mItemIds` 数组，对象和元数据各归各的。

所有槽位的状态变更都收敛到同一个辅助函数：

```cpp
T& DataArrayResetItemAt(unsigned int theIndex)
{
	DataArrayItem* aItem = &mItems[theIndex];
	std::destroy_at(aItem);
	return *std::construct_at(aItem);
}
```

`destroy_at` 之后立刻 `construct_at` **值初始化**——语义上等价于旧代码的 `memset` 清零加 placement new（零初始化加 `T` 的构造函数，同一时刻、同样的效果），但全程作用于真实存在的对象。注意这里重置的是整个 `DataArrayItem` 而不只是 `T`：对有用户自定义构造函数的 `T`，单值初始化 `T` 并不会清零它的成员，重置外层的 `DataArrayItem` 才能保证所有类型下都拿到零。`DataArrayAlloc` 就是 `DataArrayResetItemAt` 之后写入新 ID，`DataArrayFree` 就是 `DataArrayResetItemAt` 之后恢复空闲链表链接——分配和释放成了同一件事的两种包装，槽位上**永远**有存活的对象，`unique_ptr` 析构时对整块数组 `delete[]` 也就完全安全了。

迭代器里那个 `reinterpret_cast`，在 C++17 里有了正式的替代方案：

```cpp
DataArrayItem* aItem = static_cast<DataArrayItem*>(std::launder(theItem));
anIndex = static_cast<unsigned int>(aItem - mItems.get()) + 1U;
```

原地重建对象之后，旧指针指向的还是已销毁对象的存储位置，要拿到指向新对象的指针，标准做法就是 `std::launder`。原来靠 `reinterpret_cast` 强制转换的地方，现在有了语义准确的写法。顺带地，`DataArrayGet` 里那个截断 cast 也消失了，直接 `mItems[theId & DATA_ARRAY_INDEX_MASK]`。

到这里，容器自身的 UB 清完了。但真正花掉最多时间的，是它和历史遗留存档格式的接口。

## 最麻烦的一环：对写档进程留下的野指针执行析构

PvZ-Portable 现在只写结构化的 V4 存档，但代码里还留着一条旧格式（代码里称之为 legacy 格式）的读取路径，用来读 ABI 一致的旧构建写下的存档。这个格式正是这个容器最难对付的地方：它是池子内存的直接镜像——把**原始字节整体序列化**，不是只存活跃对象，而是连空闲槽位里的垃圾数据一起原样写进文件。这种格式只有在读写双方 ABI 完全一致时才可能工作，可移植性为零——这也正是当初要另起 V4 格式的原因。修复前的同步代码就是这么直白：

```cpp
theContext.SyncBytes(theDataArray.mBlock, theDataArray.mMaxUsedCount * sizeof(*theDataArray.mBlock));
```

空闲槽位里有什么？上次释放的对象析构后留下的残留字节。如果那个对象持有指针——比如舞王僵尸槽位里的 `mBoard`——那么存进文件的就是**写档那一刻进程里的一个真实地址**。

现在把新旧实现放在一起想。新实现保证了槽位上永远有存活的对象，销毁池子时会老老实实对每个槽位跑析构。那么读一份这样的存档会发生什么：文件里的原始字节被写回槽位，空闲槽位里的野指针字节成了对象的成员，等 board 拆除、池子销毁时，析构函数顺着这个**来自另一个进程的指针**访问过去——段错误。

这不是理论推演。笔者手工构造了一份存档来实证：把舞王僵尸所在空闲槽位的 `mBoard` 改成一个野指针，未修复的构建在 board 拆除时稳定复现段错误，修复后的构建正常地加载和销毁。

修法是读档时**只信任活跃槽位的字节，非活跃槽位全部重建**。存档文件的字节布局用一个只描述格式的字节结构体来表达，它本身不产生任何对象语义：

```cpp
template <typename T>
struct LegacyDataArrayItem
{
	alignas(T) unsigned char mItem[sizeof(T)];
	unsigned int mID;
};

template <typename T> inline static void SyncDataArray(SaveGameContext& theContext, DataArray<T>& theDataArray)
{
	theContext.SyncUInt32(theDataArray.mFreeListHead);
	theContext.SyncUInt32(theDataArray.mMaxUsedCount);
	theContext.SyncUInt32(theDataArray.mSize);
	auto aBlock = std::make_unique<LegacyDataArrayItem<T>[]>(theDataArray.mMaxUsedCount);
	// （写方向的分支仅作对称保留，此处省略：PvZ-Portable 只写 V4，legacy 没有写的调用点）
	theContext.SyncBytes(aBlock.get(), theDataArray.mMaxUsedCount * sizeof(aBlock[0]));
	if (!theContext.mReading)
		return;

	for (uint32_t i = 0; i < theDataArray.mMaxUsedCount; i++)
	{
		auto& aSlot = aBlock[i];
		theDataArray.DataArrayGetIDAt(i) = aSlot.mID;
		if (aSlot.mID & DATA_ARRAY_KEY_MASK)   // 只有活跃槽位的字节才进真实对象
			std::copy_n(aSlot.mItem, sizeof(T), reinterpret_cast<unsigned char*>(&theDataArray.DataArrayGetItemAt(i)));
	}
}
```

要点在最后一个循环：读档时 `mID` 恢复到独立的 ID 数组，只有 key 位有效（活跃）的槽位才把字节拷进对应的真实对象；空闲槽位的字节被**直接丢弃**，槽位本身保持池子初始化时的零初始化状态，空闲链表靠 ID 数组重新生效。这只是读档一侧的变化，对外没有任何可见影响：ABI 一致的旧构建写下的存档照样能读，只是空闲槽位的垃圾数据不再被读进对象。V4 格式那边本来就只序列化活跃项的字段，不受影响。

## 不能动的隐性约束：RNG 流

还有一类问题不会崩溃、不会被 sanitizer 报出来，但对 PvZ-Portable 来说同样致命：污染随机数流。

上一篇博客讲过，PvZ-Portable 有一套逐 tick 确定的录制/回放系统，它的根基是**全局只有一个 Mersenne Twister，每次运行消耗的随机数个数和顺序完全一致**。新实现有一个隐蔽的隐患：池子初始化从一块原始内存变成了值初始化 N 个槽位，也就是要跑 N 次 `T` 的构造函数——**如果某个 `T` 的构造函数有副作用，池子初始化就会凭空多出一串 RNG 消耗**。

真有这样一个 `T`：`Trail`（火炬树桩火焰之类的拖尾特效）的构造函数里原本带着随机化：

```cpp
Trail::Trail()
{
	...
	for (int i = 0; i < 4; i++)
	{
		mTrailInterp[i] = RandRangeFloat(0.0f, 1.0f);
	}
}
```

留着它，池子初始化就抽 4×N 次随机数，legacy 读档重建槽位时再抽一遍，RNG 流当场错位，之前整套确定性回放的工作前功尽弃。但简单粗暴地删掉也不行——分配 Trail 时少抽 4 个值，流同样错位。

修法是把这 4 次抽取从构造函数移动到 `AllocTrailFromDef` 里，插在原有的 `aDurationInterp` 抽取之前：

```cpp
aTrail->mTrailHolder = this;
aTrail->mDefinition = theDefinition;

for (int i = 0; i < 4; i++)
{
	aTrail->mTrailInterp[i] = RandRangeFloat(0.0f, 1.0f);
}
float aDurationInterp = RandRangeFloat(0.0f, 1.0f);
```

旧实现里，这 4 次抽取本来就发生在 placement new 构造 `Trail` 的时刻，也就是 `DataArrayAlloc` 之后、`AllocTrailFromDef` 取 `aDurationInterp` 之前——挪过去之后，抽取的次数、顺序、相对位置与旧实现**完全一致**，分配路径上的 RNG 序列分毫不动；而池子初始化和读档重建这两个新引入构造调用的场景，走的是不消耗任何随机数的纯值初始化，不再有任何副作用。构造无副作用、随机化集中到分配点，两件事一次做完。

配套的小调整还有几处：`TrailDefinition` 改用默认成员初始化器变成可值初始化（`mMaxPoints = 2`、`mMinPointDistance = 1.0f` 这些默认值从 `memset` 加手写字段的定义构造器里挪进了声明），`ReanimationDie` 加了一个 `mDefinition == nullptr` 的提前返回，保证零初始化实例（没用过或读档重建出来的槽位）被析构时不会解引用空指针。

## 验证

这类行为不该有丝毫变化的重构，验证手段和行为本身一样重要。这次的验证有四层：

- **容器单元测试**：分配、释放、ID 复用、迭代、失效 ID 识别，逐一覆盖。
- **ASan/UBSan 无告警**：旧代码在 UBSan 下的生命周期诊断全部消除。
- **带野指针的存档**：上面讲过的野指针 `mBoard` 实验，修复前必触发段错误、修复后正常。
- **确定性回归**：用之前那套回放系统跑两段完整 demo（一段 18.2 分钟、一段 20.7 分钟，都跑到自然 `DEMO_CLOSE`），对每一帧做 V4 存档状态比对，与基线构建**所有游戏数据块逐字节一致**——包括读报僵尸这类 RNG 敏感的帧，以及回放中途的存档/读档。

最后一层是最有力的证据：它不仅证明 RNG 流没变，还顺带证明了整个对象生命周期改造对游戏逻辑是完全透明的。

## 结语

这次改造改了 7 个文件、净增不过十来行。

**能跑不等于合法。** 旧 `DataArray` 的 UB 稳定地跑了这么多年，但是它挡掉了 sanitizer 的价值（满屏误报里谁还找得到真问题），给每一次编译器升级埋下隐患，还逼得后续代码（比如存档系统）围绕这些非法假设越堆越多。这次真正费劲的是把围绕非法假设长出来的 legacy 存档加载安全地拆开。

**序列化格式是字节协议，不是内存镜像。** Legacy 读档崩溃的本质，是把文件字节和进程内对象画了等号：文件里的指针字节被当成了可用的指针。修复后的 `LegacyDataArrayItem` 把这层关系摆正了——它只负责描述文件格式，要不要把字节变成对象状态，由读档逻辑逐槽位判断。凡是存档里可能混着垃圾数据的格式，这条原则都适用。

**重构的边界由隐性约束划定。** 这个容器连着两条不能碰的约束：存档字节布局和 RNG 消耗序列。它们不会出现在任何类型签名里，只能靠对系统的理解提前想到、再用验证手段兜底。改核心基础设施时，先问"什么东西绝不能变"，往往比问"怎么改更好"更重要。

从一块靠非法手段稳定运行的原始内存，到一个每个槽位都真实存在、销毁安全的容器，存档兼容、行为不变、回放逐字节一致——这次改动对外没有任何可见变化，但它清除的是一个陈年隐患。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
