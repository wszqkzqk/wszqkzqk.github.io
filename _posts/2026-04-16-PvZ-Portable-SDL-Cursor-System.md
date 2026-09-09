---
layout:       post
title:        PvZ-Portable：跨平台光标系统的 SDL 实现与自定义光标缓存
subtitle:     从 Windows API 到 SDL 的完整迁移、自定义光标缓存与三处状态缺陷的修复
date:         2026-04-16
author:       wszqkzqk
header-img:   img/games/pvz-portable/bg-pvz-portable.webp
catalog:      true
tags:         C++ SDL2 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

在将 PvZ-Portable 从 Windows 原生引擎改造为跨平台项目的过程中，渲染、音频、输入等核心子系统都经历了大规模重构。但有一个看似不起眼的模块长期被搁置——**光标系统**。旧代码里，`LawnApp::EnforceCursor()` 中躺着一大段被注释掉的 `::SetCursor` / `LoadCursor` Win32 API 调用，事实上，游戏此前一直并没有实现跨平台光标处理。

光标系统虽小，却是玩家与游戏交互的第一触点。当玩家悬停在可点击的按钮上时需要手型光标，在文本输入框中需要 I 形光标，在战斗场景中还需要隐藏光标以避免干扰沉浸感。本文将记录笔者如何**彻底移除 Windows 专属的光标代码**，在 `SexyAppBase` 中基于 SDL 实现一套完整的跨平台光标系统，并解决自定义光标创建与运行时缓存的技术细节。系统投入使用后暴露出的几处状态缺陷，以及它们的修复过程，也一并整理在文末。

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

## 三处状态缺陷的修复

结构搭好之后，问题才在日常使用中陆续浮现。接下来的几个月里，光标和鼠标相关的三处状态先后暴露出缺陷：一处缺了事件来源，一处生命周期没有复位，一处把缓存当成了判定依据。三处修复都不大，但各自指向状态管理的一个侧面。

### 鼠标进出窗口：`mMouseIn` 没有事件来源

`EnforceCursor()` 和 WidgetManager 的悬停处理都依赖 `mMouseIn` 这个状态：鼠标在窗口内才更新位置和悬停，离开窗口后光标恢复默认、悬停状态清除。原版 Win32 代码里，这个状态由窗口消息驱动。SDL 移植后，`SDL_WINDOWEVENT_ENTER` 和 `SDL_WINDOWEVENT_LEAVE` 两个事件却一直没有被处理——`mMouseIn` 在应用里没有任何更新来源。

于是就有了两个平时能碰到的现象。鼠标移进窗口、恰好停在一个按钮上时，按钮没有悬停高亮，光标也不切换，直到动一下鼠标才恢复正常——因为状态更新一直依赖鼠标移动事件，而进入这一时刻本身没有事件驱动它。鼠标移出窗口时则相反：按钮的高亮残留在原地，因为没有任何代码通知 WidgetManager 鼠标已经离开。

修复就是把这两个事件接上（`src/SexyAppFramework/platform/default/Input.cpp`）：

```cpp
					case SDL_WINDOWEVENT_ENTER:
						if (!mMouseIn)
						{
							int x, y;
							SDL_GetMouseState(&x, &y);
							mWidgetManager->RemapMouse(x, y);
							mMouseIn = true;
							mWidgetManager->MouseMove(x, y);
							EnforceCursor();
						}
						break;

					case SDL_WINDOWEVENT_LEAVE:
						if (mMouseIn)
						{
							mWidgetManager->MouseExit(mWidgetManager->mLastMouseX, mWidgetManager->mLastMouseY);
							mMouseIn = false;
							EnforceCursor();
						}
						break;
```

进入时主动取一次实时鼠标位置（`SDL_GetMouseState`），而不是等下一个移动事件——否则进入瞬间悬停判定用的还是旧坐标。离开时先 `MouseExit` 清除悬停，再复位 `mMouseIn` 并刷新光标。

值得一提的是，这两个事件也同步接进了 demo 命令流：录制时写入 `DEMO_MOUSE_ENTER`/`DEMO_MOUSE_EXIT`，回放时按同样的顺序驱动 `mMouseIn` 和 `EnforceCursor()`。光标状态由此也成为回放确定性的一部分——新输入事件类型接入游戏时，回放格式必须同步扩展，否则回放和实时运行在窗口焦点变化时就会产生分歧。

### 锤子光标的加载时机与生命周期

游戏里唯一的真实自定义光标，是锤击僵尸（Whack-a-Zombie）关卡中跟随鼠标的锤子动画。修复前，它的初始化写在 `CursorObject` 的构造函数里，用一个 `IsWhackAZombieLevel()` 判断把守：

```cpp
CursorObject::CursorObject()
{
    ...
    if (mApp->IsWhackAZombieLevel())
    {
        ReanimatorEnsureDefinitionLoaded(ReanimationType::REANIM_HAMMER, true);
        Reanimation* aHammerReanim = mApp->AddReanimation(-25.0f, 16.0f, 0, ReanimationType::REANIM_HAMMER);
        ...
        mReanimCursorID = mApp->ReanimationGetID(aHammerReanim);
    }
```

`CursorObject` 在 `Board::Board` 中创建（`mLevel` 此刻还是 0），关卡的初始化远未开始。在构造期就加载动画定义、创建动画实例，时机显然过早——真正需要锤子的只有这一个挑战关卡，加载动作却挂在所有关卡共享的对象构造上。更隐蔽的是生命周期上的缺陷：`CursorObject::Die()` 会移除这个动画，却不复位 `mReanimCursorID`，此后任何再读这个 ID 的代码拿到的都是悬空引用。

修复把初始化移到 `Challenge::StartLevel()`——关卡特定逻辑集中在关卡初始化处，构造函数里的条件判断随之删除。`Die()` 里补上复位：

```cpp
void CursorObject::Die()
{
    mApp->RemoveReanimation(mReanimCursorID);
    mReanimCursorID = ReanimationID::REANIMATIONID_NULL;
}
```

这与[资源生命周期治理](https://wszqkzqk.github.io/2026/04/10/PvZ-Portable-Resource-Lifetime-Safety/)里动画附件的处理是同一类问题：持有 ID 的对象必须在自己的生命周期终点解除关联，否则 ID 本身就成了悬空的引用。

### 按钮悬停状态的时效

第三处缺陷在触屏设备上现身（PR [#343](https://github.com/wszqkzqk/PvZ-Portable/pull/343)）：种子选择界面上的模仿者（Imitater）按钮，第一次点按没有反应，第二次才响应。

根子在于 `GameButton` 的身份：它不是 `Widget`，不受 WidgetManager 悬停事件驱动，只能靠自己每帧的 `Update()` 刷新缓存的 `mIsOver`。而主循环的顺序是先处理输入、后执行 `Update()`——触摸点按没有前置的悬停过程，`MouseDown` 里读到的 `mIsOver` 还是上一帧的陈旧值，第一次点按就这样被判定为不在按钮上。桌面鼠标因为移动事件频繁，缓存几乎总是新的，这个问题被掩盖了很久。触摸屏即点即走，缓存的滞后立刻现形。

修复是把判定和缓存拆开（提交 `266224c`）：`IsMouseOver()` 不再读缓存，改用 WidgetManager 的实时鼠标位置当场计算；`Update()` 里的 `mIsOver` 改为从它派生，缓存只继续驱动悬停淡入动画。AwardScreen 里为绕过这个 bug 打的预热补丁（`MouseDown` 里先手动调用三个按钮的 `Update()`）也随之删除——这类预热补丁的存在，本身就说明根因还没修。

## 结语

光标系统在游戏引擎中往往被视为"边缘功能"，但在跨平台移植的语境下，它其实是一个完整的子系统：从操作系统抽象、像素格式转换、资源生命周期管理到运行时缓存策略，每一个环节都需要仔细设计。

通过这次重构，PvZ-Portable 彻底摆脱了 Win32 光标的遗留包袱，获得了真正意义上的跨平台光标支持。无论是桌面平台（Windows、Linux、macOS）、移动平台（通过外接鼠标），还是 WebAssembly 浏览器环境，玩家都能获得一致且完整的光标交互体验。

而后续三处缺陷的修复也说明，光标系统的收尾不在结构搭好的那一刻，而在每个状态来源都接上之后。`mMouseIn` 缺的是驱动它的事件，`mReanimCursorID` 缺的是生命周期终点的复位，`mIsOver` 缺的则是判定与缓存的分离——三个问题互不相干，却都属于同一类：**状态与现实的脱节**。这类系统的正确性不取决于结构多清晰，而取决于每一个驱动状态的事件、每一个状态变更的时点是否都存在。结构图看不出这个状态现在是不是最新的，这只能逐个事件来源去核对。

## ⚠️ 版权与说明

**重要：本项目仅包含代码引擎，不包含任何游戏素材！**

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中。

*   `main.pak`
*   `properties/` 目录

本项目的源代码以 [**LGPL-3.0-or-later**](https://www.gnu.org/licenses/lgpl-3.0.html) 许可证开源，欢迎学习和贡献。
