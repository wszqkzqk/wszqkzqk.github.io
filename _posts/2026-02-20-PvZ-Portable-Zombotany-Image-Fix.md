---
layout:       post
title:        PvZ-Portable：修复僵尸植物存档恢复后的贴图错误
subtitle:     修复资源 ID 反查映射中一个指针与值的混淆以及 64 位平台的未定义行为
date:         2026-02-20
author:       wszqkzqk
header-img:   img/games/bg-pvz-portable.webp
catalog:      true
tags:         C++ 跨平台 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

在 [PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable) 中，有一个只在特定条件下才会出现的 Bug：当场上存在**植物僵尸**时进行存档，**读档恢复**后，这些僵尸会多出一个重叠的普通僵尸头部——本该被隐藏的默认头部贴图重新显示了出来，与植物头部叠在一起，看上去非常怪异。

|[![#~/img/games/pvz-portable-bug-zombotany-image.webp](/img/games/pvz-portable-bug-zombotany-image.webp)](/img/games/pvz-portable-bug-zombotany-image.webp)|
|:----:|
|植物僵尸在存档后读档恢复时的贴图错误<br>在植物头后还错误地渲染了一个普通僵尸的头|

而在没有僵尸植物的普通关卡中，存档和读档一切正常，完全不会触发这个问题。

经过排查，笔者发现这个 Bug 的根源深藏在资源管理系统的 ID 反查函数 `GetIdByVariable` 中，并且在修复这个核心问题的同时，还发现了与之相关的 64 位平台未定义行为和边界检查缺失等一系列问题，一并进行了修复（PR [#63](https://github.com/wszqkzqk/PvZ-Portable/pull/63)，Commit [3252690](https://github.com/wszqkzqk/PvZ-Portable/commit/3252690e14c9b17e713fa432ed27bab08469aa34)）。

## 问题分析

### 资源管理系统的架构

PvZ-Portable 的资源管理系统使用了一个核心数组 `gResources`，它是一个 `void*` 类型的全局数组，按照 `ResourceId` 枚举的顺序，存储着所有全局资源变量的**地址**：

```cpp
void* gResources[static_cast<int>(Sexy::ResourceId::RESOURCE_ID_MAX)] =
{
    &Sexy::IMAGE_BLANK,         // ResourceId 0
    &Sexy::IMAGE_POPCAP_LOGO,   // ResourceId 1
    &Sexy::IMAGE_PARTNER_LOGO,  // ResourceId 2
    // ...
    &Sexy::SOUND_BUTTONCLICK,   // 某个 ResourceId
    &Sexy::SOUND_LOADINGBAR_FLOWER,
    // ...
};
```

这里需要注意的是，`gResources[i]` 存储的是**变量的地址**（如 `&IMAGE_BLANK`），而不是变量的值。例如 `IMAGE_BLANK` 本身是一个 `Image*` 指针，`gResources` 中存储的是指向这个指针变量的地址（即 `Image**`）。

引擎提供了两个方向的查询函数：

- **正向查询**：`GetImageById(ResourceId)` —— 根据枚举 ID 获取资源值，实现方式是 `*reinterpret_cast<Image**>(gResources[id])`，即从 `gResources` 中取出变量地址，再解引用得到变量的值。
- **反向查询**：`GetIdByVariable(void*)` —— 根据资源的值反查枚举 ID。这个函数在存档序列化中非常关键。

### 核心 Bug：`GetIdByVariable` 中地址与值的混淆

`GetIdByVariable` 的功能是给定一个资源的值，找到它对应的 `ResourceId`。修复前的代码如下：

```cpp
Sexy::ResourceId Sexy::GetIdByVariable(void* theVariable)
{
    static std::map<void*, int> aMap;

    if (gNeedRecalcVariableToIdMap)
    {
        gNeedRecalcVariableToIdMap = false;
        aMap.clear();
        for (int i = 0; i < static_cast<int>(ResourceId::RESOURCE_ID_MAX); i++)
            aMap[gResources[i]] = i;  // BUG: 存入的是变量地址，而非变量值！
    }

    auto anIter = aMap.find(theVariable);
    return anIter == aMap.end() ? ResourceId::RESOURCE_ID_MAX : (ResourceId)anIter->second;
}
```

这里的问题在于构建反向映射时使用了 `gResources[i]` 作为 Key。正如前文所述，`gResources[i]` 存储的是**变量的地址**，而不是变量的值。

然而，调用端传入的参数 `theVariable` 却是资源的**值**。以 `GetIdByImage` 为例：

```cpp
Sexy::ResourceId Sexy::GetIdByImage(Image* theImage)
{
    return GetIdByVariable(theImage);
}
```

这导致反向映射表的 Key（变量地址）和查询的 Key（变量值）永远无法匹配，`aMap.find(theVariable)` 几乎必定返回 `aMap.end()`，函数始终返回 `RESOURCE_ID_MAX`——表示未找到。

### 为什么只有僵尸植物会触发？

这个 Bug 从原理上讲应该影响所有需要通过 `SyncImagePortable` 序列化 `Image*` 的场景。然而实际上，只有僵尸植物的存档恢复会出问题。笔者追踪了存档序列化代码，找到了原因。

`SyncImagePortable` 函数用于在存档中保存和恢复 `Image*` 类型的字段：

```cpp
static void SyncImagePortable(PortableSaveContext& theContext, Image*& theImage)
{
    if (theContext.mReading) {
        // 读档：从存档读取 ResourceId，然后反查 Image*
        ResourceId aResID;
        theContext.SyncInt32(reinterpret_cast<int&>(aResID));
        if (aResID == Sexy::ResourceId::RESOURCE_ID_MAX)
            theImage = nullptr;
        else
            theImage = GetImageById(aResID);
    } else {
        // 存档：将 Image* 转换为 ResourceId 写入
        ResourceId aResID;
        if (theImage != nullptr)
            aResID = GetIdByImage(theImage);  // 这里会调用到有 Bug 的 GetIdByVariable
        else
            aResID = Sexy::ResourceId::RESOURCE_ID_MAX;
        theContext.SyncInt32(reinterpret_cast<int&>(aResID));
    }
}
```

关键的短路逻辑在于：如果 `theImage` 为 `nullptr`，函数直接写入 `RESOURCE_ID_MAX`，根本不会调用有 Bug 的 `GetIdByImage`。

在游戏中，`mImageOverride` 字段（被 `SyncImagePortable` 序列化）默认为 `nullptr`，绝大多数实体都不会修改它。只有**僵尸植物**才会设置这个字段：

```cpp
// Zombie.cpp — 豌豆射手僵尸初始化
ReanimatorTrackInstance* aTrackInstance = aBodyReanim->GetTrackInstanceByName("anim_head1");
aTrackInstance->mImageOverride = IMAGE_BLANK;  // 设置为非 nullptr！
```

僵尸植物用 `IMAGE_BLANK`（一张透明贴图）覆盖了默认的僵尸头部贴图，以此隐藏普通头部，然后附加一个植物头部的骨骼动画。这是唯一会让 `mImageOverride` 变为非 `nullptr` 的路径。

因此 Bug 的完整触发链条为：

1. 僵尸植物的 `mImageOverride` 被设为 `IMAGE_BLANK`（非 `nullptr`）。
2. 存档时，`SyncImagePortable` 调用 `GetIdByImage(IMAGE_BLANK)`。
3. `GetIdByVariable` 在映射表中查不到对应项（因为地址与值的混淆），返回 `RESOURCE_ID_MAX`。
4. `RESOURCE_ID_MAX` 被写入存档。
5. 读档时，`SyncImagePortable` 读到 `RESOURCE_ID_MAX`，将 `mImageOverride` 设为 `nullptr`。
6. 僵尸头部的覆盖贴图丢失，默认的普通僵尸头部重新显示，与植物头部叠加在一起。

### 64 位平台的未定义行为：`int` 与 `intptr_t`

在排查过程中，笔者还发现了一个与此相关的 64 位平台安全隐患。

在修复前，所有 `SOUND_*` 全局变量的类型为 `int`（4 字节）：

```cpp
extern int SOUND_BUTTONCLICK;
extern int SOUND_LOADINGBAR_FLOWER;
// ...
```

这些变量的地址通过 `&SOUND_BUTTONCLICK` 存入 `gResources` 数组（`void*` 类型）。正向查询函数 `GetSoundById` 的实现为：

```cpp
int Sexy::GetSoundById(Sexy::ResourceId theId)
{
    return *reinterpret_cast<int*>(gResources[static_cast<int>(theId)]);
}
```

这本身没问题。但修复 `GetIdByVariable` 后，新代码使用 `memcpy` 从 `gResources[i]` 指向的地址读取 `sizeof(void*)` 字节：

```cpp
void* value;
std::memcpy(&value, gResources[i], sizeof(void*));
aMap[value] = i;
```

在 64 位平台上，`sizeof(void*)` 为 8 字节，但 `SOUND_*` 变量是 `int` 类型，仅占 4 字节。这意味着 `memcpy` 会从一个 4 字节的对象中读取 8 字节的数据，**越界读取了相邻内存**，这是未定义行为。

实际上，`gResources` 数组在各个地方的使用都隐含了一个前提：数组中每个指针指向的对象大小至少为 `sizeof(void*)`。`Image*` 和 `_Font*` 天然满足（指针本身就是 `sizeof(void*)` 大小），但 `int` 在 64 位平台上只有 4 字节，不满足这个要求。

因此，修复方案是将所有 `SOUND_*` 变量从 `int` 改为 `intptr_t`。`intptr_t` 保证与指针大小一致，在 32 位平台上是 4 字节，在 64 位平台上是 8 字节，彻底消除了这个隐患。这个改动涉及全部 168 个 `SOUND_*` 变量声明，以及从 `Resources.h/cpp` 到 `SoundManager.h`、`SDLSoundManager.h/cpp`、`ResourceManager.h/cpp`、`SexyAppBase.h/cpp`、`LawnApp.h/cpp`、`TodFoley.h/cpp` 等所有使用声音 ID 的接口，共 14 个文件。

### 附带修复：边界检查与 `LoadSound` 返回值

在审查声音相关代码时，笔者还发现了两处额外的问题：

**1. `GetSoundInstance` 的边界检查**

```cpp
// 修复前
SoundInstance* SDLSoundManager::GetSoundInstance(unsigned int theSfxID)
{
    if (theSfxID > MAX_SOURCE_SOUNDS) return NULL;
    // ...
}
```

这里 `> MAX_SOURCE_SOUNDS` 应该是 `>= MAX_SOURCE_SOUNDS`，因为有效索引范围是 `0` 到 `MAX_SOURCE_SOUNDS - 1`。并且修改类型为 `intptr_t` 后，该参数为有符号类型，还需要增加负数检查：

```cpp
// 修复后
SoundInstance* SDLSoundManager::GetSoundInstance(intptr_t theSfxID)
{
    if (theSfxID < 0 || theSfxID >= MAX_SOURCE_SOUNDS) return NULL;
    // ...
}
```

**2. `ReleaseSound` 缺少边界检查**

`ReleaseSound` 函数在修复前完全没有边界检查就直接用 `theSfxID` 作为数组索引访问 `mSourceSounds`，存在越界访问风险。修复后增加了与 `GetSoundInstance` 一致的边界检查。

**3. `TitleScreen.cpp` 中的 `LoadSound` 返回值误用**

```cpp
// 修复前
SOUND_LOADINGBAR_FLOWER = LoadSound(GetFreeSoundId(), path);
```

`LoadSound` 返回的是 `bool`（表示加载成功与否），而不是声音 ID。此处实际行为是将 `bool` 值（0 或 1）赋给了 `SOUND_LOADINGBAR_FLOWER`，而真正分配的 ID 被丢弃了。修复后拆分为两步：

```cpp
// 修复后
SOUND_LOADINGBAR_FLOWER = GetFreeSoundId();
LoadSound(SOUND_LOADINGBAR_FLOWER, path);
```

## 修复方案

核心修复仅涉及 `GetIdByVariable` 一个函数，修改后的代码为：

```cpp
Sexy::ResourceId Sexy::GetIdByVariable(void* theVariable)
{
    static std::map<void*, int> aMap;

    if (gNeedRecalcVariableToIdMap)
    {
        gNeedRecalcVariableToIdMap = false;
        aMap.clear();
        for (int i = 0; i < static_cast<int>(ResourceId::RESOURCE_ID_MAX); i++)
        {
            void* value;
            std::memcpy(&value, gResources[i], sizeof(void*));
            aMap[value] = i;  // 用变量的值作为 Key，而非变量的地址
        }
    }

    auto anIter = aMap.find(theVariable);
    return anIter == aMap.end() ? ResourceId::RESOURCE_ID_MAX : (ResourceId)anIter->second;
}
```

关键改动：用 `memcpy` 从 `gResources[i]` 所指向的地址处读取 `sizeof(void*)` 字节的**值**，并以这个值作为映射表的 Key。这样调用端传入的资源值就能正确匹配到映射表中的条目了。

配合 `SOUND_*` 类型从 `int` 到 `intptr_t` 的全链路改动，确保 `memcpy` 读取 `sizeof(void*)` 字节时不会越界。

## 结语

这个 Bug 的有趣之处在于它的**高度选择性**：只有僵尸植物的 `mImageOverride` 会从非 `nullptr` 变成 `nullptr`，从而导致可见的贴图错误。其他所有使用 `SyncImagePortable` 的字段要么始终为 `nullptr`（跳过了有 Bug 的反查路径），要么即使查找失败也不会在视觉上产生明显影响。正是这种藏在角落里的特性使得这个问题长期未被发现。

同时，这次修复也暴露了当初将不同大小的类型（`Image*`、`_Font*` 和 `int`）统一存入 `void*` 数组时留下的类型安全隐患。将 `SOUND_*` 改为 `intptr_t` 不仅修复了当前的未定义行为，也为将来代码统一以指针大小为单位操作资源变量奠定了基础。
