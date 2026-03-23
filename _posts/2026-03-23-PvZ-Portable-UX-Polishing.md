---
layout:       post
title:        PvZ-Portable 输入系统与主循环优化：原生字符合成与 Web 端延迟修复
subtitle:     解决跨平台开发中的输入响应与事件派发问题
date:         2026-03-23
author:       wszqkzqk
header-img:   img/games/bg-pvz-portable.webp
catalog:      true
tags:         C++ SDL2 开源软件 游戏移植 开源游戏 PvZ-Portable WebAssembly
---

## 引言

在之前完成[基于 Emscripten 的浏览器端适配](https://wszqkzqk.github.io/2026/03/10/PvZ-Portable-WebAssembly-Adaptation/)后，PvZ-Portable 终于填补了跨平台版图的最后一块。引擎此时已经能在 PC、移动端乃至纯 Web 环境中跑通基础流程。但对于游戏移植而言，完成编译只是第一步，真正的考验在于如何抹平不同宿主环境对底层设施的入侵感。

在不同平台的细微体验打磨中，应用的输入处理和事件调度常常是重灾区。近期，笔者主要对 PvZ-Portable 的底层事件分发以及 Web 端主循环做了一次针对性的重构修复，进一步解决了跨系统开发中输入响应迟滞和事件派发错位等问题。本文将重点介这两项底层基础设施的优化细节。

## Emscripten 主循环事件漏帧与鼠标拖动卡顿修复

在通过 Emscripten 编译到 Web 平台时，受限于浏览器的执行模型，传统的无限阻塞式游戏主循环必须被转换为异步的回调机制，通常挂载到浏览器的 `requestAnimationFrame`（rAF）中。

为了适配这一机制，PvZ-Portable 将原有的进程阻塞转编为一套状态机机制，通过 `UpdateAppStep` 函数逐步推进应用状态。然而，在之前的代码实现中，主循环的回调存在一个导致输入延迟和偶发掉帧的判定问题，其最典型的症状是：**在 Web 端游戏内拖动鼠标时，画面会出现明显的卡顿甚至完全冻结。**

```cpp
// 旧版轮询逻辑
while (updated || app->mUpdateAppState == UPDATESTATE_PROCESS_2 || app->mHasPendingDraw)
{
    if (!app->UpdateAppStep(&updated))
        break;

    if (!updated && app->mUpdateAppState == UPDATESTATE_PROCESS_DONE && !app->mHasPendingDraw)
        break;
}
```

这段代码的问题在于对其状态穷举不足。在特定的中间状态下，如果在当前迭代中没有产生明显的逻辑更新（`updated` 为 false），循环会提前 `break`，将剩余的事件处理或帧渲染推迟到下一个 rAF 回调。

当玩家快速移动或拖动鼠标时，底层会产生大量的 `SDL_MOUSEMOTION` 事件，而这种提前 `break` 的机制导致引擎无法在一个单独的浏览器刷新帧内将堆积的鼠标事件完全消化。未处理的事件导致事件队列拥塞，状态机因为事件迟滞而无法推进，反映在游戏体验上便是严重的拖放卡顿感。

优化方案是将终止条件改为显式校对最终完成状态，强制事件泵在单次浏览器帧回调内彻底排空所有挂起阶段和积压事件：

```cpp
// 优化后的 Emscripten 轮询逻辑
while (app->mUpdateAppState != UPDATESTATE_PROCESS_DONE || app->mHasPendingDraw)
{
    if (!app->UpdateAppStep(&updated))
        break;
}
```

通过这一改动，只要引擎没有抵达 `UPDATESTATE_PROCESS_DONE`，状态机就会在其所在的这一个 rAF 内部不间断推进。所有的用户输入堆栈（包括高频次触发的鼠标移动操作）和挂起的绘制指令都能在一个物理周期内高效率地提取并结算。更新此逻辑后，Web 端鼠标拖放的卡顿问题得到了彻底解决。

## SDL2 原生字符合成与作弊快捷键修复

原版游戏及引擎中存在许多依赖于 `KeyChar` 键盘事件直接触发的动作交互，其中就包含了游戏内丰富的作弊快捷键（`-DPVZ_DEBUG`且启动时传递`-tod`参数时开启）。

在现代的跨平台 SDL2 开发范式中，上层若想获取标准的对应字符级事件，常规的做法是调用 `SDL_StartTextInput()`。但这在许多非传统桌面系统平台中会引发不符合预期的副作用：无论是在移动设备上还是包含虚拟键盘的现代桌面环境，拉起标准的 Text Input 上下文会不可避免地强制唤起输入法辅助面板，甚至直接拉长屏幕占用遮挡半个游戏视野。

然而我们仅仅是想让玩家在游戏正常流程下顺畅使用那些老式的单键快捷组合。引擎需要一种能在不触发系统输入法弹窗的前提下，静默且准确地提取字符事件的方案。

由于这部分快捷键纯粹属于字符组合与映射操作，笔者在 SDL 事件泵处理 `SDL_KEYDOWN` 的逻辑中建立了一个底层的 ASCII 字符合成器，从物理按键及其修饰符直接向游戏应用派发所需的 `KeyChar` 信息：

```cpp
static bool SDLSynthesizeAsciiCharFromKeyDown(const SDL_KeyboardEvent& theEvent, char& theChar)
{
    theChar = 0;

    // 当游戏真正需要文本输入（如存档命名）时，让位给系统的系统输入法
    if (SDL_IsTextInputActive())
        return false;

    SDL_Keycode aSym = theEvent.keysym.sym;
    SDL_Keymod aMods = static_cast<SDL_Keymod>(theEvent.keysym.mod);
    const bool aHasCtrl = (aMods & KMOD_CTRL) != 0;
    const bool aHasAlt = (aMods & KMOD_ALT) != 0;
    const bool aHasGui = (aMods & KMOD_GUI) != 0;
    const bool aHasShift = (aMods & KMOD_SHIFT) != 0;

    // 过滤掉包含 Alt 或 Gui 中继键的操作
    if (aHasAlt || aHasGui)
        return false;

    // 映射字母并处理 Shift 组合
    if (aSym >= SDLK_a && aSym <= SDLK_z)
    {
        theChar = aHasCtrl
            ? static_cast<char>(aSym - SDLK_a + 1)
            : static_cast<char>(aHasShift ? aSym - SDLK_a + 'A' : aSym);
        return true;
    }

    if (aHasCtrl)
        return false;

    // 映射数字区域与其他标点符号
    switch (aSym)
    {
        case SDLK_1: theChar = aHasShift ? '!' : '1'; return true;
        // ... (其他字符映射省略)
        case SDLK_SPACE: theChar = ' '; return true;
        default: return false;
    }
}
```

随后在事件循环处理 `SDL_KEYDOWN` 的分支处增加对合成器的调用：

```cpp
case SDL_KEYDOWN:
{
    mLastUserInputTick = mLastTimerTime;
    mWidgetManager->KeyDown(SDLKeyToKeyCode(event.key.keysym.sym));

    char aSynthesizedChar = 0;
    if (SDLSynthesizeAsciiCharFromKeyDown(event.key, aSynthesizedChar))
        mWidgetManager->KeyChar(aSynthesizedChar);

    break;
}
```

在此流程下，当玩家敲击键盘时，普通的字符映射被自动合成为 `KeyChar` 信息传递给 WidgetManager 控制层。游戏内部对于键盘流的监听与原版无缝衔接，同时通过判断 `SDL_IsTextInputActive()`，保留了玩家建立新存档需要输入账号名称时的正常虚拟键盘唤起通道，互不冲突。

## 结语

不同运行环境的差异往往体现在 API 缝隙以及系统调用习惯上。通过修正 Emscripten 帧回调中的提前退出机制，以及解耦字符获取机制与 OS 输入法组件之间的强绑定，PvZ-Portable 进一步消除了不同平台的体验差异。游戏引擎的基础设施改进仍在继续进行中。

## ⚠️ 版权与说明

**重要：本项目仅包含代码引擎，不包含任何游戏素材！**

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中。

*   `main.pak`
*   `properties/` 目录

本项目的源代码以 [**LGPL-3.0-or-later**](https://www.gnu.org/licenses/lgpl-3.0.html) 许可证开源，欢迎学习和贡献。