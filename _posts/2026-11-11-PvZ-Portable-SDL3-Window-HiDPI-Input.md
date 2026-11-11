---
layout:       post
title:        PvZ-Portable：SDL3 窗口、高分屏双坐标系与输入事件迁移
subtitle:     分离物理像素与窗口逻辑坐标，排查 SDLK_A 命名变更引发的按键失灵
header-img:   img/games/pvz-portable/bg-pvz-portable.webp
date:         2026-11-11
author:       wszqkzqk
catalog:      true
tags:         SDL 输入事件 高分屏 开源软件 游戏移植 PvZ-Portable
---

## 引言

在[上一篇文章](https://wszqkzqk.github.io/2026/11/10/PvZ-Portable-SDL3-Audio-System/)中，笔者拆解了 [PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable) 迁移至 SDL3 时的音频架构重写。除了音频，游戏与操作系统打交道的另一半基础设施——窗口管理、视口缩放、鼠标光标、键盘与文本输入——也在这次迁移（PR [#523](https://github.com/wszqkzqk/PvZ-Portable/pull/523)）中全面切到了 SDL3。

从表面上看，这部分改动不少是枚举和函数签名的更替；但真正落地到高分屏（HiDPI）环境、确定性回放（Demo）录制以及键盘输入分发时，SDL3 在坐标体系、事件结构和键码命名上的几处语义变化都需要仔细对齐。本文将记录这些改动的技术细节，以及迁移中途踩到的一个典型键码陷阱。

## 高分屏下的两套坐标系

《植物大战僵尸》原版的逻辑分辨率固定为 $800 \times 600$（$4:3$）。PvZ-Portable 支持自由调整窗口大小与全屏显示，画面通过黑边（letterbox / pillarbox）保持 $4:3$ 比例居中呈现。

在窗口缩放时，引擎需要同时做对两件事：

- **渲染侧**：告诉 OpenGL 当前 $4:3$ 画面落在帧缓冲区的哪个像素矩形内（`glViewport`）。
- **交互侧**：将操作系统上报的鼠标坐标（以及输入法候选框锚点）与这片 $4:3$ 画面区域对齐（`mPresentationRect`），供 `WidgetManager::RemapMouse` 换算回 $800 \times 600$ 的游戏逻辑坐标。

### 启用高像素密度后，像素尺寸与窗口尺寸不再相等

迁移到 SDL3 时，我们在创建窗口的标志位中加入了 `SDL_WINDOW_HIGH_PIXEL_DENSITY`（`src/SexyAppFramework/platform/default/Window.cpp`）：

```cpp
SDL_WindowFlags winFlags = SDL_WINDOW_OPENGL | SDL_WINDOW_RESIZABLE
	| SDL_WINDOW_HIGH_PIXEL_DENSITY | (!mIsWindowed ? SDL_WINDOW_FULLSCREEN : 0);

SDLWindowPtr window(SDL_CreateWindow(mTitle.c_str(), mWidth, mHeight, winFlags), &SDL_DestroyWindow);
```

顺带一提，SDL3 的 `SDL_CreateWindow` 移除了 SDL2 中鸡肋的 `x, y` 初始位置参数（窗口默认居中创建），全屏标志也从 `SDL_WINDOW_FULLSCREEN_DESKTOP` 统一为 `SDL_WINDOW_FULLSCREEN`，`SDL_SetWindowFullscreen(window, bool)` 直接接收布尔值。

一旦开启 `SDL_WINDOW_HIGH_PIXEL_DENSITY`，在 macOS Retina 显示器或开启了 150%、200% 缩放的 Linux Wayland 桌面上，窗口便同时拥有两套尺寸：

- **物理像素尺寸**（由 `SDL_GetWindowSizeInPixels` 获取，取代了 SDL2 的 `SDL_GL_GetDrawableSize`）：例如一个 $800 \times 600$ 逻辑大小的窗口，在 $2\times$ 缩放屏幕上的帧缓冲像素尺寸是 $1600 \times 1200$。OpenGL 的 `glViewport` 工作在这个坐标系下。
- **窗口逻辑尺寸**（由 `SDL_GetWindowSize` 获取）：依然是 $800 \times 600$。**SDL3 的鼠标事件坐标（`event.motion.x`、`event.button.x`）以及文本输入区域（`SDL_SetTextInputArea`）全部工作在这个窗口逻辑坐标系下。**

### 分离 glViewport 与 mPresentationRect

在迁移前的旧代码中，`GLInterface::UpdateViewport()` 只查询了像素尺寸，算出的视口矩形 `(vx, vy, vw, vh)` 既直接传给 `glViewport`，又原封不动地存进 `mPresentationRect`：

```cpp
// 旧代码：将像素坐标直接存入 mPresentationRect
int width, height;
SDL_GL_GetDrawableSize(mApp->mWindow.get(), &width, &height);
// ... 按 4:3 计算 vx, vy, vw, vh ...
glViewport(vx, vy, vw, vh);
mPresentationRect = Rect(vx, vy, vw, vh);
```

如果窗口未开启高像素密度（像素与逻辑尺寸 $1:1$），这样做不会暴露问题。但开启 `SDL_WINDOW_HIGH_PIXEL_DENSITY` 后，若继续把物理像素算出的 `mPresentationRect`（例如 $1600 \times 1200$）交给 `WidgetManager`，而鼠标事件上报的 `x, y` 却是 $0 \sim 800$ 的窗口逻辑坐标，`RemapMouse` 就会以为鼠标永远只在屏幕左上角四分之一的区域里活动。

修复后的 `GLInterface::UpdateViewport()` 明确区分了这两个坐标系（`src/SexyAppFramework/graphics/GLInterface.cpp`）：

```cpp
void GLInterface::UpdateViewport()
{
	int vx = 0, vy = 0, vw, vh;
#ifdef __SWITCH__
	int width = 1280, height = 720;
#else
	int width, height;
	SDL_GetWindowSizeInPixels(mApp->mWindow.get(), &width, &height);
#endif
	if (width <= 0 || height <= 0)
		return;

	int windowWidth = width, windowHeight = height;
#ifndef __SWITCH__
	SDL_GetWindowSize(mApp->mWindow.get(), &windowWidth, &windowHeight);
#endif
	if (windowWidth <= 0 || windowHeight <= 0)
		return;

	vw = width; vh = height;

	if (vw * 3 > vh * 4)
	{
		vw = vh * 4 / 3;
		vx = (width - vw) / 2;
	}
	else
	{
		vh = vw * 3 / 4;
		vy = (height - vh) / 2;
	}

	glViewport(vx, vy, vw, vh);
	mPresentationRect = Rect(
		windowWidth * vx / width,
		windowHeight * vy / height,
		windowWidth * vw / width,
		windowHeight * vh / height);
}
```

`glViewport` 继续使用物理像素 `(vx, vy, vw, vh)`，让高分屏下的纹理和字体边缘获得完整物理分辨率的采样精度；存入 `mPresentationRect` 前，则按 `windowWidth / width` 与 `windowHeight / height` 换算回窗口逻辑坐标。

与此同时，在事件分发（`Input.cpp`）中，除了响应 `SDL_EVENT_WINDOW_RESIZED`，还一并监听了 `SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED`：

```cpp
case SDL_EVENT_WINDOW_RESIZED:
case SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED:
	mGLInterface->UpdateViewport();
	mWidgetManager->Resize(mScreenBounds, mGLInterface->mPresentationRect);
	mWidgetManager->MarkAllDirty();
	break;
```

当用户把窗口从普通显示器拖到高分屏显示器（窗口逻辑大小未变、像素密度改变），或直接拉伸窗口边框时，视口与鼠标映射矩形都能及时同步。

## 键码命名变更背后的陷阱：SDLK_A 的值依然是小写 `'a'`

这次迁移中最隐蔽的一个 bug 出现在键盘输入上，对应 `refactor/sdl3-migration` 分支的提交 `ede66cf3`（`Fix: restore letter key input on SDL3`）。

### 初次迁移后，所有字母键突然失灵

在 SDL2 中，字母键的 `SDL_Keycode` 常量以小写命名：`SDLK_a` 到 `SDLK_z`，其底层枚举值就是小写 ASCII 字符 `'a'`（`0x61`）到 `'z'`（`0x7A`）。游戏内部使用的 `KeyCode` 枚举则与 Windows 虚拟键码（VK）兼容，字母键统一映射到 `'A'` $\sim$ `'Z'`。因此，SDL2 时代的键码转换函数是这样写的（`src/SexyAppFramework/platform/default/Input.cpp`）：

```cpp
// SDL2 旧代码
static KeyCode SDLKeyToKeyCode(SDL_Keycode theSDLKey)
{
	if (theSDLKey >= SDLK_a && theSDLKey <= SDLK_z)
		return static_cast<KeyCode>(theSDLKey - SDLK_a + 'A');
	// ...
}
```

到了 SDL3，官方将所有字母键常量的宏名从 `SDLK_a` $\sim$ `SDLK_z` 改成了大写形式的 **`SDLK_A` $\sim$ `SDLK_Z`**。

在初次迁移（`68de7dc2`）时，看到常量名变成了大写的 `SDLK_A`，很容易产生一个直觉误判：以为 SDL3 把字母键的枚举值也一并改成了大写 ASCII `'A'` $\sim$ `'Z'`。于是初版代码被写成了：

```cpp
// 初版迁移的错误写法：误以为 SDL3 字母键码的值变成了 'A' ~ 'Z'
static KeyCode SDLKeyToKeyCode(SDL_Keycode theSDLKey)
{
	if (theSDLKey >= 'A' && theSDLKey <= 'Z')
		return static_cast<KeyCode>(theSDLKey);
	// ...
}
```

同样地，用于在非 IME 状态下从 `keydown` 合成控制码（如 Ctrl+C/V）和 ASCII 字符的 `SDLSynthesizeAsciiCharFromKeyDown`，初版也写成了 `if (aSym >= 'A' && aSym <= 'Z')`。

运行游戏后发现：关卡内的字母快捷键（例如调试模式下的刷怪键、快进键）、主菜单热键以及输入框里的 Ctrl+A/C/V 快捷键全部失灵了。

### 命名大写化，但码点值保持小写

查阅 SDL3 的 `<SDL3/SDL_keycode.h>` 定义，真相水落石出：

```c
#define SDLK_A 0x00000061u /* 'a' */
...
#define SDLK_Z 0x0000007au /* 'z' */
```

SDL3 的规则是：**代表可打印字符的 `SDL_Keycode`，其数值定义为按下该键且不带修饰键时产生的 Unicode 小写码点（即 `'a'` = `0x61`）**；而将宏名从 `SDLK_a` 改为 `SDLK_A`，纯粹是为了让标识符命名风格与 `SDL_SCANCODE_A` 及其他全大写宏名保持一致。

换句话说，**名字从 `SDLK_a` 改成了 `SDLK_A`，但它的值仍然是 `'a'`**。用 `theSDLKey >= 'A' && theSDLKey <= 'Z'`（`0x41` $\sim$ `0x5A`）去拦截 `event.key.key`，自然永远不会命中。

提交 `ede66cf3` 将两处判断全部改为使用 `SDLK_A` 和 `SDLK_Z` 宏，并恢复 `SDLK_A` 到 `'A'` 的偏移换算：

```cpp
static KeyCode SDLKeyToKeyCode(SDL_Keycode theSDLKey)
{
	if (theSDLKey >= SDLK_A && theSDLKey <= SDLK_Z)
		return static_cast<KeyCode>(theSDLKey - SDLK_A + 'A');
	// ...
}
```

以及字符合成路径：

```cpp
	if (aSym >= SDLK_A && aSym <= SDLK_Z)
	{
		if (aHasCtrl)
		{
			theChar = static_cast<char>(aSym - SDLK_A + 1); // Ctrl+letter -> control code; SDL_EVENT_TEXT_INPUT is not guaranteed for Ctrl combos
			return true;
		}

		if (aTextInputActive)
			return false;

		theChar = static_cast<char>(aHasShift ? aSym - SDLK_A + 'A' : aSym);
		return true;
	}
```

由于 `SDLK_A` 等于 `'a'`，未按住 Shift 时直接取 `aSym` 就是小写字母，按住 Shift 时 `aSym - SDLK_A + 'A'` 则得到大写字母。其他从 SDL2 迁移到 SDL3 的项目如果此前直接用字符字面量 `'a'`/`'z'` 或误改成了 `'A'`/`'Z'`，也很容易在这里踩坑——始终使用 `SDLK_A` $\sim$ `SDLK_Z` 符号并显式加减偏移，才不会受字面量假设的误导。

## 事件结构扁平化与精度调整

在事件循环（`Input.cpp`）中，SDL3 对 `SDL_Event` 做了几项结构性整理。

### 窗口事件提升为顶层枚举

SDL2 将所有与窗口状态相关的事件都塞进 `SDL_WINDOWEVENT` 一个顶层类型里，处理时必须先 `case SDL_WINDOWEVENT:`，再嵌套一层 `switch (event.window.event)` 去区分 `SDL_WINDOWEVENT_CLOSE`、`SDL_WINDOWEVENT_MINIMIZED`、`SDL_WINDOWEVENT_ENTER` 等子事件。

SDL3 取消了这层二级分发，将所有窗口事件直接提升为 `SDL_EventType` 的顶层枚举（如 `SDL_EVENT_WINDOW_CLOSE_REQUESTED`、`SDL_EVENT_WINDOW_MINIMIZED`、`SDL_EVENT_WINDOW_RESTORED`、`SDL_EVENT_WINDOW_FOCUS_GAINED`、`SDL_EVENT_WINDOW_MOUSE_ENTER`、`SDL_EVENT_WINDOW_MOUSE_LEAVE`）。`ProcessDeferredMessages` 和 `RecordDemoEvent` 中的两层嵌套 `switch` 由此压平为单层，窗口关闭请求也可以直接与 `SDL_EVENT_QUIT` 合并处理：

```cpp
case SDL_EVENT_QUIT:
case SDL_EVENT_WINDOW_CLOSE_REQUESTED:
	CloseRequestAsync();
	break;
```

### 鼠标浮点坐标与滚轮 `integer_y`

为了支持高精度触控板和数位板，SDL3 将鼠标移动（`event.motion.x/y`）、鼠标按键（`event.button.x/y`）以及 `SDL_GetMouseState(&x, &y)` 的坐标类型全部从 `int` 改为了 `float`。由于游戏内部 UI 树（`WidgetManager`）工作在 $800 \times 600$ 的整数像素网格上，接收这些事件时先查询浮点坐标，再转换为 `int` 传入 `RemapMouse`：

```cpp
case SDL_EVENT_WINDOW_MOUSE_ENTER:
	if (!mMouseIn)
	{
		float x, y;
		SDL_GetMouseState(&x, &y);
		int aX = static_cast<int>(x), aY = static_cast<int>(y);
		mWidgetManager->RemapMouse(aX, aY);
		mMouseIn = true;
		mWidgetManager->MouseMove(aX, aY);
		EnforceCursor();
	}
	break;
```

鼠标滚轮事件 `SDL_EVENT_MOUSE_WHEEL` 的变化则需要格外小心。在 SDL3 中，`event.wheel.y` 同样变成了 `float`，在高精度触控板或无极滚轮上可能上报小于 `1.0` 的小数增量。然而，PvZ-Portable 的 `WidgetManager::MouseWheel(int)` 和确定性回放录制（将滚轮增量 clamp 到 `[-128, 127]` 后写入 8 位比特流）都需要整数刻度：

```cpp
case SDL_EVENT_MOUSE_WHEEL:
	theApp->WriteDemoTimingBlock();
	theApp->mDemoBuffer.WriteNumBits(0, 1);
	theApp->mDemoBuffer.WriteNumBits(DEMO_MOUSE_WHEEL, 5);
	theApp->mDemoBuffer.WriteNumBits(std::clamp(theEvent.wheel.integer_y, -128, 127), 8);
	break;
```

这里没有简单地对 `event.wheel.y` 做 `static_cast<int>`（否则每次小于 `1.0` 的平滑滚动都会被截断为 `0`，导致触控板滚轮彻底失效），而是使用了 SDL3 在 `SDL_MouseWheelEvent` 中提供的 `integer_y` 字段——SDL3 内部会替应用累积平滑滚动的小数余量，每凑够一个完整刻度就通过 `integer_y` 输出整数步数。

需要注意的是，`integer_y` 是在 **SDL 3.2.12** 中才加入 `SDL_MouseWheelEvent` 的字段。为了防止用户在安装了更早的 SDL 3.2.x 头文件的系统上编译时报出字段不存在的编译错误，提交 `69dad699`（`Fix: declare minimum SDL3 version`）在 `CMakeLists.txt` 中明确声明了最低版本约束：

```cmake
find_package(SDL3 3.2.12 CONFIG REQUIRED)
```

这样既允许使用后续的 3.2.x / 3.4.x 新版本，又能在 CMake 配置阶段直接拦截过旧的头文件。

### 键盘事件字段与窗口级文本输入

键盘事件 `SDL_KeyboardEvent` 在 SDL3 中去掉了冗余的 `keysym` 嵌套层：

- `event.key.keysym.sym` 简化为 `event.key.key`
- `event.key.keysym.mod` 简化为 `event.key.mod`，修饰键常量统一加上 `SDL_` 前缀（如 `KMOD_CTRL` $\rightarrow$ `SDL_KMOD_CTRL`）
- `event.key.repeat` 从 `Uint8` 改为 `bool`
- 撇号与反引号键码从 `SDLK_QUOTE`、`SDLK_BACKQUOTE` 更名为更准确的 `SDLK_APOSTROPHE`、`SDLK_GRAVE`

文本输入 API（见[打通 UTF-8 文本输入链路博客](https://wszqkzqk.github.io/2026/07/31/PvZ-Portable-UTF8-Text-Input/)）在 SDL3 中全部改为绑定具体窗口句柄，以便在多窗口环境下明确输入焦点归属：

- `SDL_StartTextInput()` $\rightarrow$ `SDL_StartTextInput(mWindow.get())`
- `SDL_StopTextInput()` $\rightarrow$ `SDL_StopTextInput(mWindow.get())`
- `SDL_IsTextInputActive()` $\rightarrow$ `SDL_TextInputActive(mWindow.get())`
- `SDL_SetTextInputRect(&aRect)` $\rightarrow$ `SDL_SetTextInputArea(mWindow.get(), &aRect, 0)`（第三个参数为候选词光标在矩形内的水平偏移）

## 光标、Surface 与平台基础接口清理

除了窗口和输入，[跨平台光标系统](https://wszqkzqk.github.io/2026/04/16/PvZ-Portable-SDL-Cursor-System/)与系统级辅助函数也在这次迁移中同步更新到了 SDL3 规范。

### 光标枚举与零拷贝 Surface 创建

SDL3 将系统光标枚举 `SDL_SystemCursor` 的命名对齐到了 CSS 标准光标名称：

```cpp
static SDL_SystemCursor CursorNumToSystemCursor(int theCursorNum)
{
	switch (theCursorNum)
	{
		case CURSOR_HAND:         return SDL_SYSTEM_CURSOR_POINTER;
		case CURSOR_TEXT:         return SDL_SYSTEM_CURSOR_TEXT;
		case CURSOR_CIRCLE_SLASH: return SDL_SYSTEM_CURSOR_NOT_ALLOWED;
		case CURSOR_SIZEALL:      return SDL_SYSTEM_CURSOR_MOVE;
		case CURSOR_SIZENESW:     return SDL_SYSTEM_CURSOR_NESW_RESIZE;
		case CURSOR_SIZENS:       return SDL_SYSTEM_CURSOR_NS_RESIZE;
		case CURSOR_SIZENWSE:     return SDL_SYSTEM_CURSOR_NWSE_RESIZE;
		case CURSOR_SIZEWE:       return SDL_SYSTEM_CURSOR_EW_RESIZE;
		case CURSOR_WAIT:         return SDL_SYSTEM_CURSOR_WAIT;
		default:                  return SDL_SYSTEM_CURSOR_DEFAULT;
	}
}
```

光标显隐控制从原先复用同一个函数的 `SDL_ShowCursor(SDL_ENABLE)` / `SDL_ShowCursor(SDL_DISABLE)` 拆分为语义直接的 `SDL_ShowCursor()` 和 `SDL_HideCursor()`。

从 `MemoryImage` 零拷贝包装 `SDL_Surface` 以创建自定义彩色光标的代码，也用 `SDL_CreateSurfaceFrom` 替代了旧版的 `SDL_CreateRGBSurfaceWithFormatFrom`（不再需要单独传入冗余的 `depth = 32` 参数），销毁函数则统一为 `SDL_DestroySurface` 与 `SDL_DestroyCursor`：

```cpp
SDL_Surface* aSurface = SDL_CreateSurfaceFrom(
	aWidth,
	aHeight,
	SDL_PIXELFORMAT_BGRA32,
	theImage->mBits.get(),
	aWidth * static_cast<int>(sizeof(uint32_t)));
if (aSurface == nullptr)
	return nullptr;

SDL_Cursor* aCursor = SDL_CreateColorCursor(aSurface, 0, 0);
SDL_DestroySurface(aSurface);
```

### 用 SDL3 原生能力替换三段平台特判代码

在迁移过程中，笔者还顺手利用 SDL3 的新特性删掉了三段过去不得不自己维护的平台补偿代码：

1. **移除 Windows 下的 `BuildUtf8ArgsFromWin32`（`src/main.cpp`）**：
   在 Windows 上，标准 C/C++ 的 `main(int argc, char** argv)` 传入的参数编码取决于系统活动代码页（ACP），遇到含非 ASCII 字符的路径参数就会乱码。过去我们在 `main.cpp` 顶部专门写了 45 行 Win32 代码，调用 `GetCommandLineW()`、`CommandLineToArgvW()` 和 `WideCharToMultiByte(CP_UTF8, ...)` 手动构造 UTF-8 `argv`。
   SDL3 重构了入口头 `<SDL3/SDL_main.h>`：在 Windows 上包含该头文件后，SDL3 的入口包装层会自动从宽字符命令行提取参数并转换为 UTF-8 再传给应用层的 `main`。因此，`main.cpp` 中的 `<windows.h>`、`<shellapi.h>` 和整段 `BuildUtf8ArgsFromWin32` 被全部删除。
2. **移除 Windows 下的 `nanosleep` 模拟函数（`src/SexyAppFramework/Common.h`）**：
   为了在桌面帧率控制和加载线程让出 CPU 时进行毫秒/微秒级休眠，旧代码在 POSIX 平台调用 `nanosleep`，并在 `Common.h` 中专门为 `_WIN32` 写了 30 行基于 `CreateWaitableTimer` + `SetWaitableTimer` + `WaitForSingleObject` 的同名 `nanosleep` 包装函数。
   SDL3 提供了跨平台的纳秒级延迟函数 `SDL_DelayNS(Uint64 ns)`，内部在各操作系统上自动选用最高精度的睡眠原语。我们将 `SexyAppBase.cpp` 中的三处 `nanosleep` 全部替换为 `SDL_DelayNS(static_cast<Uint64>(ms) * 1000000ULL)`，随之删去了 `Common.h` 里的 Win32 定时器代码，连带省去了启动时无意义的 `SDL_Init(SDL_INIT_TIMER)` 调用。
3. **统一 iOS `Documents` 与桌面 `BasePath` 的获取（`src/SexyAppFramework/SexyAppBase.cpp`）**：
   iOS 端此前通过读取环境变量 `std::getenv("HOME")` 再拼接 `"Documents"` 来定位用户文档目录；迁移后直接改用 SDL3 新增的 `SDL_GetUserFolder(SDL_FOLDER_DOCUMENTS)`。此外，SDL3 将 `SDL_GetBasePath()` 的返回值改为了由 SDL 内部缓存管理的 `const char*`，调用方不再需要每次接手 `char*` 后手动调用 `SDL_free`。

## 结语

窗口与输入层的迁移印证了一件事：跨大版本升级底层库时，编译器能报错的签名变更反而是最好改的部分；真正需要留心的是**同名或近名概念在语义上的迁移**。

开启 `SDL_WINDOW_HIGH_PIXEL_DENSITY` 后，渲染帧缓冲与鼠标事件分属物理像素和窗口逻辑两套坐标系，`UpdateViewport` 必须在出口处把视口矩形换算回窗口坐标；`SDLK_a` 改名为 `SDLK_A`，只是统一了宏名大小写，枚举值却仍是 `'a'`；`event.wheel.y` 变成浮点数后，确定性回放必须改读 `event.wheel.integer_y` 才能在触控板上保持整数刻度，而这又反过来决定了 `find_package(SDL3 3.2.12)` 的最低版本要求。把这几处隐含契约核对清楚，窗口和输入系统才能在所有平台上跑得稳当。

在系列最后一篇文章《[SDL3 迁移中的跨平台构建与静态链接](https://wszqkzqk.github.io/2026/11/12/PvZ-Portable-SDL3-Cross-Platform-Build/)》中，笔者将复盘这次迁移在七个目标平台的构建体系与 CI 上遇到的工程问题。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。研究或使用此项目时，**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies)购买）。你需要从正版游戏中提取以下文件，放到 PvZ-Portable 的程序所在目录：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
