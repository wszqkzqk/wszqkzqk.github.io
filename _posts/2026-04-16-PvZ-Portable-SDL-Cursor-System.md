---
layout:       post
title:        PvZ-Portable：跨平台光标系统的 SDL 实现与自定义光标缓存
subtitle:     从 Windows API 到 SDL 的完整迁移，以及 MemoryImage 动态创建自定义光标的链路设计
date:         2026-04-16
author:       wszqkzqk
header-img:   img/games/bg-pvz-portable.webp
catalog:      true
tags:         C++ SDL2 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

在将 PvZ-Portable 从 Windows 原生引擎改造为跨平台项目的过程中，渲染、音频、输入等核心子系统都经历了大规模重构。但有一个看似不起眼的模块长期被搁置——**光标系统**。旧代码里，`LawnApp::EnforceCursor()` 中躺着一大段被注释掉的 `::SetCursor` / `LoadCursor` Win32 API 调用，事实上，游戏此前一直并没有实现跨平台光标处理。

光标系统虽小，却是玩家与游戏交互的第一触点。当玩家悬停在可点击的按钮上时需要手型光标，在文本输入框中需要 I 形光标，在战斗场景中还需要隐藏光标以避免干扰沉浸感。本文将记录笔者如何**彻底移除 Windows 专属的光标代码**，在 `SexyAppBase` 中基于 SDL 实现一套完整的跨平台光标系统，并解决自定义光标创建与运行时缓存的技术细节。

## 被遗留的 Windows 光标实现

原版引擎的光标管理集中在 `LawnApp` 层，`EnforceCursor()` 是整个游戏的唯一光标控制入口。旧代码的典型模式如下(（被注释掉，没有实际生效）：

```cpp
void LawnApp::EnforceCursor()
{
    if (mSEHOccured || !mMouseIn)
    {
        ::SetCursor(LoadCursor(nullptr, IDC_ARROW));
        return;
    }

    if (mOverrideCursor)
    {
        ::SetCursor(mOverrideCursor);
        return;
    }

    switch (mCursorNum)
    {
    case CURSOR_POINTER:
        ::SetCursor(LoadCursor(GetModuleHandle(nullptr), MAKEINTRESOURCE(IDC_CURSOR1)));
        return;
    case CURSOR_HAND:
        ::SetCursor(mHandCursor);
        return;
    // ... 更多 Windows 专属分支 ...
    }
}
```

这段代码有两大问题：

1. **平台耦合过重**：`HCURSOR`、`LoadCursor`、`SetCursor`、`GetModuleHandle` 全部是 Win32 API，无法在其他平台上编译或运行。
2. **架构位置过高**：光标作为通用窗口系统能力，本应由应用框架层（`SexyAppBase`）负责，而不应该由游戏逻辑层（`LawnApp`）持有。将光标控制放在 `LawnApp` 意味着每个基于该框架的新项目都要重复实现一遍。

在 PvZ-Portable 此前的版本中，这段代码一直处于被完全注释掉的状态，导致跨平台构建时虽然能编译通过，但光标行为是缺失的。

## 跨平台重构：下沉到 SexyAppBase

修复的第一步是**把光标逻辑从 `LawnApp` 完全移除**，转而在 `SexyAppBase` 中以 SDL API 重新实现 `EnforceCursor()`。这样，所有基于该框架的应用都能自动获得跨平台光标支持。

新的 `EnforceCursor()` 核心逻辑如下：

```cpp
void SexyAppBase::EnforceCursor()
{
    int aCursorNum = mSEHOccured ? CURSOR_POINTER : mCursorNum;
    if (aCursorNum < 0 || aCursorNum >= NUM_CURSORS)
        aCursorNum = CURSOR_POINTER;

    if (aCursorNum == CURSOR_NONE)
    {
        SDL_ShowCursor(SDL_DISABLE);
        return;
    }

    SDL_Cursor* aCursor = nullptr;

    // 1. 优先使用自定义光标（如果启用且已设置图片）
    if (mCustomCursorsEnabled && mCursorImages[aCursorNum] != nullptr)
    {
        // ... 从 MemoryImage 创建或命中缓存 ...
    }

    // 2. 回退到系统光标
    if (aCursor == nullptr)
    {
        SDL_Cursor*& aCachedCursor = mSysCursors[aCursorNum];
        if (aCachedCursor == nullptr)
            aCachedCursor = SDL_CreateSystemCursor(CursorNumToSystemCursor(aCursorNum));
        aCursor = aCachedCursor;
        if (aCursor == nullptr)
            aCursor = SDL_GetDefaultCursor();
    }

    if (aCursor != nullptr)
        SDL_SetCursor(aCursor);

    SDL_ShowCursor(SDL_ENABLE);
}
```

这个结构清晰地划分了三个层级：**自定义光标 → 系统光标 → 默认光标**。`CURSOR_NONE` 则单独走隐藏分支，确保在任何平台下都能可靠地隐藏鼠标指针。

## 系统光标映射

SDL2 提供了一套与操作系统无关的系统光标枚举 `SDL_SystemCursor`。笔者编写了一个静态映射函数，将引擎内部使用的 `CURSOR_xxx` 枚举转换为对应的 SDL 枚举：

```cpp
static SDL_SystemCursor CursorNumToSystemCursor(int theCursorNum)
{
    switch (theCursorNum)
    {
        case CURSOR_HAND:        return SDL_SYSTEM_CURSOR_HAND;
        case CURSOR_TEXT:        return SDL_SYSTEM_CURSOR_IBEAM;
        case CURSOR_CIRCLE_SLASH:return SDL_SYSTEM_CURSOR_NO;
        case CURSOR_SIZEALL:     return SDL_SYSTEM_CURSOR_SIZEALL;
        case CURSOR_SIZENESW:    return SDL_SYSTEM_CURSOR_SIZENESW;
        case CURSOR_SIZENS:      return SDL_SYSTEM_CURSOR_SIZENS;
        case CURSOR_SIZENWSE:    return SDL_SYSTEM_CURSOR_SIZENWSE;
        case CURSOR_SIZEWE:      return SDL_SYSTEM_CURSOR_SIZEWE;
        case CURSOR_WAIT:        return SDL_SYSTEM_CURSOR_WAIT;
        case CURSOR_DRAGGING:
        case CURSOR_POINTER:
        case CURSOR_NONE:
        case CURSOR_CUSTOM:
        default:
            return SDL_SYSTEM_CURSOR_ARROW;
    }
}
```

这里有几个值得注意的设计选择：

- **`CURSOR_DRAGGING` 映射到箭头**：SDL 并没有专门的"拖动中"系统光标，因此回退到标准箭头是合理的。
- **`CURSOR_CUSTOM` 也映射到箭头**：`CURSOR_CUSTOM` 的语义是"使用开发者通过 `SetCursorImage` 设置的自定义图片"。如果自定义图片未设置或未启用，回退到箭头光标能避免光标突然消失。
- **懒加载（Lazy Initialization）**：系统光标只在第一次需要时通过 `SDL_CreateSystemCursor` 创建，并缓存到 `mSysCursors` 数组中。这避免了在应用启动时就为所有平台创建大量可能永远用不到的光标句柄。

## 从 MemoryImage 到 SDL_Cursor

相比系统光标，自定义光标的实现要复杂得多。PvZ-Portable 的图像系统使用 `MemoryImage` 作为内存位图的抽象，其像素数据以 BGRA32 格式存储在 `mBits` 指针中。而 SDL 创建自定义光标需要 `SDL_Surface`。因此，关键问题是如何**在不复制像素数据的前提下，将 `MemoryImage` 包装为 SDL 表面**。

笔者选择了 `SDL_CreateRGBSurfaceWithFormatFrom`，它允许直接从现有的像素缓冲区创建表面，而无需额外拷贝：

```cpp
static SDL_Cursor* CreateCursorFromMemoryImage(MemoryImage* theImage)
{
    if (theImage == nullptr || theImage->mBits == nullptr)
        return nullptr;

    const int aWidth = theImage->GetWidth();
    const int aHeight = theImage->GetHeight();
    if (aWidth <= 0 || aHeight <= 0)
        return nullptr;

    SDL_Surface* aSurface = SDL_CreateRGBSurfaceWithFormatFrom(
        theImage->mBits,
        aWidth,
        aHeight,
        32,
        aWidth * static_cast<int>(sizeof(uint32_t)),
        SDL_PIXELFORMAT_BGRA32);
    if (aSurface == nullptr)
        return nullptr;

    SDL_Cursor* aCursor = SDL_CreateColorCursor(aSurface, 0, 0);
    SDL_FreeSurface(aSurface);
    return aCursor;
}
```

这段代码的技术细节包括：

- **零拷贝创建 Surface**：`SDL_CreateRGBSurfaceWithFormatFrom` 直接使用 `theImage->mBits` 作为像素源，`SDL_FreeSurface` 时不会释放这个外部缓冲区，因此 `MemoryImage` 的生命周期不受影响。
- **像素格式对齐**：`MemoryImage` 内部使用 32 位 BGRA，pitch 为 `width * sizeof(uint32_t)`，与 `SDL_PIXELFORMAT_BGRA32` 完全匹配。
- **热点坐标**：`SDL_CreateColorCursor` 的 `(0, 0)` 热点对于 PvZ-Portable 的自定义光标资源来说是适用的。如果未来需要更精细的热点控制，可以在 `MemoryImage` 或 `Image` 接口中扩展元数据。

## 缓存策略与性能优化

自定义光标有一个显著的运行时开销：**每次调用 `SDL_CreateColorCursor` 都会分配新的操作系统光标资源**。如果在每一帧都重新创建，不仅会造成内存分配压力，还可能导致光标闪烁。因此，缓存机制必不可少。

笔者设计了一个双层缓存策略：

### 系统光标缓存

```cpp
// SexyAppBase.h
SDL_Cursor* mSysCursors[NUM_CURSORS];
```

`mSysCursors` 是一个固定大小的指针数组。`EnforceCursor()` 在首次需要某个系统光标时调用 `SDL_CreateSystemCursor`，并将结果缓存到对应槽位。后续再切换到同一光标时直接命中，无需与操作系统交互。这些缓存在 `SexyAppBase` 析构时统一 `SDL_FreeCursor` 释放。

### 自定义光标缓存

```cpp
// SexyAppBase.h
SDL_Cursor*  mCustomCursor;
Image*       mCustomCursorImage;
int          mCustomCursorImageNum;
```

自定义光标采用**单例缓存**模式（而非数组），原因如下：

1. **资源开销更高**：自定义光标的创建需要遍历像素数据、生成表面、再生成系统光标对象，成本远高于系统光标。
2. **使用频率更低**：游戏中大部分光标都是系统光标（箭头、手型、等待等），自定义光标只在特定场景出现，通常一次只会使用一张自定义图片。

缓存命中判定逻辑：

```cpp
if (mCustomCursor != nullptr
    && mCustomCursorImage == aCursorImage
    && mCustomCursorImageNum == aCursorNum)
{
    aCursor = mCustomCursor;  // 命中缓存
}
else
{
    SDL_Cursor* aNewCursor = CreateCursorFromMemoryImage(aMemoryImage);
    if (aNewCursor != nullptr)
    {
        ResetCustomCursorCache();  // 释放旧缓存
        mCustomCursor = aNewCursor;
        mCustomCursorImage = aCursorImage;
        mCustomCursorImageNum = aCursorNum;
        aCursor = mCustomCursor;
    }
}
```

此外，如果上层逻辑通过 `SetCursorImage()` 替换了某光标编号对应的图片，且该编号正好是当前缓存的自定义光标，则必须立即失效缓存，否则新图片不会生效：

```cpp
void SexyAppBase::SetCursorImage(int theCursorNum, Image* theImage)
{
    if ((theCursorNum >= 0) && (theCursorNum < NUM_CURSORS))
    {
        if (mCustomCursorImageNum == theCursorNum
            && mCursorImages[theCursorNum] != theImage)
            ResetCustomCursorCache();

        mCursorImages[theCursorNum] = theImage;
        EnforceCursor();
    }
}
```

`EnableCustomCursors` 同样会在关闭自定义光标时清空缓存，避免在禁用状态下仍持有不必要的系统资源。

## 隐藏光标与状态管理

除了"显示什么光标"之外，"是否显示光标"同样重要。原版引擎使用 `CURSOR_NONE` 和 `CURSOR_CUSTOM` 两个枚举值来表达"不显示系统光标"。在新的 SDL 实现中，笔者对 `CURSOR_NONE` 做了明确处理：

```cpp
if (aCursorNum == CURSOR_NONE)
{
    SDL_ShowCursor(SDL_DISABLE);
    return;
}
```

当光标编号为 `CURSOR_NONE` 时，直接调用 `SDL_ShowCursor(SDL_DISABLE)` 隐藏鼠标指针，不再尝试创建或设置任何光标对象。这对于战斗场景、过场动画或全屏模式非常有用——玩家不希望一个巨大的箭头遮挡画面中心。

与此同时，从 `CURSOR_NONE` 切换回其他任何光标时，`EnforceCursor()` 的正常流程会在设置新光标后调用 `SDL_ShowCursor(SDL_ENABLE)`，确保指针重新出现。状态转换是可靠且可逆的。

## 结语

光标系统在游戏引擎中往往被视为"边缘功能"，但在跨平台移植的语境下，它其实是一个完整的子系统：从操作系统抽象、像素格式转换、资源生命周期管理到运行时缓存策略，每一个环节都需要仔细设计。

通过这次重构，PvZ-Portable 彻底摆脱了 Win32 光标的遗留包袱，获得了真正意义上的跨平台光标支持。无论是桌面平台（Windows、Linux、macOS）、移动平台（通过外接鼠标），还是 WebAssembly 浏览器环境，玩家都能获得一致且完整的光标交互体验。

## ⚠️ 版权与说明

**重要：本项目仅包含代码引擎，不包含任何游戏素材！**

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中。

*   `main.pak`
*   `properties/` 目录

本项目的源代码以 [**LGPL-3.0-or-later**](https://www.gnu.org/licenses/lgpl-3.0.html) 许可证开源，欢迎学习和贡献。
