---
layout:       post
title:        PvZ-Portable：100% 复原的植物大战僵尸登陆浏览器——零安装即点即玩
subtitle:     将经典游戏全功能完美适配浏览器免安装运行（WebAssembly + Emscripten 技术详解）
date:         2026-03-10
author:       wszqkzqk
header-img:   img/games/bg-pvz-portable.webp
catalog:      true
tags:         C++ SDL2 OpenGL WebAssembly Emscripten 开源软件 游戏移植 开源游戏 PvZ-Portable
---

## 现在，打开浏览器就能玩

经过 [Linux/Windows/macOS](https://wszqkzqk.github.io/2026/01/26/PvZ-Portable/)、[Android](https://wszqkzqk.github.io/2026/03/04/PvZ-Portable-Android-Adaptation/)、[iOS/iPadOS](https://wszqkzqk.github.io/2026/03/08/PvZ-Portable-iOS-Adaptation/) 的一轮轮适配，PvZ-Portable 已经可以在几乎所有主流平台上运行。但此前仍留下了一个终极平台——**浏览器**。

现在，PvZ-Portable 终于完成了 WebAssembly 适配，这一跨平台开源游戏引擎可以**直接在 Chrome、Firefox、Edge、Safari 等现代浏览器中运行**了。

**无需下载任何安装包、无需配置任何运行环境**——只要你有一个现代浏览器（Chrome、Firefox、Edge、Safari...），就可以直接游玩 100% 复原的开源版植物大战僵尸年度版。整个 C++ 引擎被编译为 WebAssembly，在浏览器沙箱中以接近原生的速度运行，存档自动保存到浏览器本地存储中。一切数据完全在用户设备上处理，**没有任何数据上传到服务器**，安全隐私无忧。

**👉 [点击这里立即体验](https://wszqkzqk.github.io/pvz-portable-wasm/pvz-portable.html)**

打开页面后，上传你**合法拥有的正版** PC 版《植物大战僵尸：年度版》的 `main.pak` 和 `properties/` 目录，点击 **Start Game**，即可开始游戏。存档数据会自动保存在浏览器的 IndexedDB 中，关闭页面后再次打开需要重新上传资源包，但是存档会自动保存，可以直接继续游戏。

|[![#~/img/games/pvz-portable-wasm-upload-screen.webp](/img/games/pvz-portable-wasm-upload-screen.webp)](/img/games/pvz-portable-wasm-upload-screen.webp)|[![#~/img/games/pvz-portable-wasm-gameplay.webp](/img/games/pvz-portable-wasm-gameplay.webp)](/img/games/pvz-portable-wasm-gameplay.webp)|
|:----:|:----:|
| 上传资源界面 | 浏览器中的游戏画面 |

这是 PvZ-Portable 目前为止**最复杂的一次平台适配**。Android 需要编写 Java Activity 和 JNI 桥接，iOS 需要处理路径和侧载，但它们本质上都是把同一个 SDL2 程序交叉编译到另一个操作系统。而 WebAssembly 面临的是一个完全不同的执行模型——**浏览器没有线程（主线程不能阻塞）、没有本地文件系统、没有 `nanosleep`、没有传统的主循环**。几乎每一个底层假设都需要重新审视。

本文将首先介绍使用方法，然后详细记录适配过程中遇到的每个技术挑战及其解决方案。

## ⚠️ 重要说明

**本项目仅包含代码引擎，不包含任何游戏素材！**

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。本项目的 WebAssembly 适配**纯粹是跨平台移植技术的研究**——研究如何将一个使用 SDL2 和 OpenGL ES 的 C++ 引擎适配到浏览器环境中运行，仅用于技术学习。本项目与 EA/PopCap 没有任何商业合作或授权关系，也不包含任何受版权保护的游戏资源。

要研究或使用此项目，你**必须**拥有正版 PC 版《植物大战僵尸：年度版》（GOTY Edition）的资源文件（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies)上购买）。

本项目的源代码以 [**LGPL-3.0-or-later**](https://www.gnu.org/licenses/lgpl-3.0.html) 许可证开源，欢迎学习和贡献。

## 使用指南

### 在线体验

直接访问 **[https://wszqkzqk.github.io/pvz-portable-wasm/pvz-portable.html](https://wszqkzqk.github.io/pvz-portable-wasm/pvz-portable.html)** 即可。

1. 拖放或点击上传你的 `main.pak` 文件和 `properties/` 目录。
2. 可选地点击 **Import Saves** 导入之前导出的存档 ZIP。
3. 点击 **▶ Start Game** 开始游戏。
4. 游戏过程中存档会**每 5 秒自动同步**到 IndexedDB。切换标签页、关闭页面时也会触发同步。
5. 页面右上角的 **💾 Export Saves** 按钮可以将存档导出为 ZIP 文件，方便迁移到其他平台或备份。

所有文件**完全在本地处理**，不会上传到任何服务器。没有任何隐私风险。

### 本地部署

如果你想在本地部署，从 [GitHub Releases](https://github.com/wszqkzqk/PvZ-Portable/releases) 下载 WASM 构建包（包含 `pvz-portable.html`、`pvz-portable.js`、`pvz-portable.wasm` 三个文件），放在同一目录下，用任意 HTTP 服务器托管即可：

```bash
cd <包含三个文件的目录>
python3 -m http.server 8080 --bind 127.0.0.1
```

然后访问 `http://localhost:8080/pvz-portable.html`。

> ⚠️ **不能直接双击打开 HTML 文件**——浏览器的安全策略禁止 `file://` 协议加载 WebAssembly 模块和使用 IndexedDB。必须通过 HTTP 服务。

### 自行构建

项目提供了 `wasm/build-wasm.sh` 构建脚本。需要先安装 [Emscripten SDK](https://emscripten.org/docs/getting_started/downloads.html)，然后：

```bash
source /path/to/emsdk/emsdk_env.sh
./wasm/build-wasm.sh --deps  # --deps 会自动构建 libopenmpt
```

构建产物位于 `build-wasm/` 目录。

## 技术适配详解

WebAssembly 适配涉及 13 个文件、约 960 行新增代码。下面按问题类别逐一展开。

### 构建系统：Emscripten 与 CMake 集成

Emscripten 将 C/C++ 编译为 WebAssembly，同时提供了 SDL2、zlib、libpng、libjpeg、libogg、libvorbis、mpg123 等常用库的 Emscripten Port（预编译版本），通过 `-sUSE_SDL=2` 等标志即可自动获取。但 **libopenmpt 没有 Emscripten Port**——这是游戏音乐系统依赖的 MOD/tracker 音频解码库，需要手动用 `emmake make` 从源码编译。

CMakeLists.txt 为 Emscripten 添加了独立的工具链分支：

```cmake
elseif(EMSCRIPTEN)
    find_library(OPENMPT_LIBRARY NAMES openmpt libopenmpt REQUIRED)
    set(OPENMPT_LIB ${OPENMPT_LIBRARY})
    list(APPEND SOURCES
        ${CMAKE_CURRENT_SOURCE_DIR}/src/SexyAppFramework/platform/emscripten/Window.cpp
        ${CMAKE_CURRENT_SOURCE_DIR}/src/SexyAppFramework/platform/default/Input.cpp
    )
```

链接阶段需要传递大量 Emscripten 特有的标志：

```cmake
target_link_options(pvz-portable PRIVATE
    "SHELL:-sUSE_SDL=2"
    "SHELL:-sASYNCIFY"             # 关键：启用 Asyncify 协程支持
    "SHELL:-sALLOW_MEMORY_GROWTH=1"
    "SHELL:-sMAXIMUM_MEMORY=1073741824"  # 1 GB
    "SHELL:-sFORCE_FILESYSTEM=1"
    "SHELL:-sEXPORTED_RUNTIME_METHODS=[\"FS\",\"callMain\"]"
    "SHELL:-sINVOKE_RUN=0"        # 不自动运行 main()
    "SHELL:-lidbfs.js"            # IndexedDB 文件系统
    "SHELL:--shell-file ${CMAKE_CURRENT_SOURCE_DIR}/wasm/shell.html"
)
```

其中几个关键标志后文会详细解释。`-sINVOKE_RUN=0` 配合 `--shell-file` 使得可以在 JavaScript 侧先完成资源上传，再手动调用 `Module.callMain([])` 启动游戏。

为了确保修改 `shell.html` 后 CMake 能自动触发重新链接，还需要显式声明依赖：

```cmake
set_property(TARGET pvz-portable APPEND PROPERTY LINK_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/wasm/shell.html"
)
```

否则修改模板后 `ninja` 不知道需要重新生成输出文件。

此外，由于 Emscripten 的 SDL2 Port 并不通过 `find_package(SDL2)` 暴露 CMake 目标，项目提供了一个 `CMake/FindSDL2.cmake` 封装模块，仅在 Emscripten 环境下使用，为 `SDL2::SDL2` 目标设置正确的编译和链接选项，使得上游 CMake 代码中对 `SDL2::SDL2` 的引用能正确工作。

### 黑屏问题：`glClear` 与浏览器合成

适配初期遇到的第一个视觉问题是**游戏画面完全黑屏**。

在桌面平台上，`GLInterface::Flush()` 在 `SDL_GL_SwapWindow()` 之后会立即调用 `glClear(GL_COLOR_BUFFER_BIT)` 清除后缓冲区——这是标准做法，因为 `SwapBuffers` 后后缓冲区的内容是未定义的（undefined behavior），不清除可能导致残影。

但在 Emscripten 中，渲染流程不同。浏览器使用 `requestAnimationFrame` 调度渲染，合成器（compositor）在 rAF 回调返回**之后**才会将 WebGL canvas 的内容合成到页面上。如果在 `SwapBuffers` 后立即 `glClear`，浏览器合成时看到的就是一个被清空的 canvas——于是黑屏。

修复方法很简单：在 Emscripten 下跳过 swap 后的 `glClear`：

```cpp
void GLInterface::Flush()
{
    SDL_GL_SwapWindow((SDL_Window*)mApp->mWindow);
#ifndef __EMSCRIPTEN__
    glClear(GL_COLOR_BUFFER_BIT);
#endif
}
```

### Canvas 缩放与鼠标坐标

游戏原始分辨率为 800×600，但用户的浏览器窗口大小各异。如何在不破坏鼠标坐标映射的前提下实现自适应缩放？

关键区分是 HTML Canvas 的两种大小属性：

- **内在尺寸**（`width`/`height` 属性）：决定了绘图坐标系，SDL 和 WebGL 以此为基准
- **CSS 尺寸**（`style.width`/`style.height`）：决定了在页面上的显示大小

最终的方案是保持 canvas 内在尺寸为 800×600 不变，仅通过 CSS 缩放来适配屏幕：

```javascript
function resizeCanvas() {
    var canvas = document.getElementById('canvas');
    var container = document.getElementById('canvas-container');
    var vw = container.clientWidth;
    var vh = container.clientHeight;
    var scale = Math.min(vw / canvas.width, vh / canvas.height);
    canvas.style.width  = Math.floor(canvas.width  * scale) + 'px';
    canvas.style.height = Math.floor(canvas.height * scale) + 'px';
}
```

这样 SDL 始终在 800×600 的坐标空间中处理鼠标事件，浏览器自动将 CSS 缩放后的用户点击坐标映射回 canvas 内在坐标。如果错误地修改 canvas 的 `width`/`height` 属性来适配窗口大小，会导致 SDL 的坐标系与实际游戏逻辑不匹配——典型表现是关卡内鼠标点击位置偏移，无法正确操作。

`canvas-container` 设置为 `100vw × 100vh` 并居中，结合 4:3 比例的 letterbox 适配，在任何屏幕比例下都能正确显示。

### 卡顿修复：主循环与帧完成

这是整个适配过程中调试最久的问题。

#### 背景：桌面平台的主循环

在桌面平台上，游戏主循环是一个简单的 `while` 死循环：

```cpp
void SexyAppBase::DoMainLoop()
{
    while (!mShutdown)
    {
        if (mExitToTop)
            mExitToTop = false;
        UpdateApp();
    }
}
```

`UpdateApp()` 内部通过 `UpdateAppStep()` 推进一个状态机，状态依次为：

1. `UPDATESTATE_MESSAGES` — 处理输入事件
2. `UPDATESTATE_PROCESS_1` — 逻辑更新
3. `UPDATESTATE_PROCESS_2` — 继续逻辑更新
4. `UPDATESTATE_PROCESS_DONE` — 执行绘制

桌面上每次 `UpdateApp()` 调用会在一个 `while` 循环中把所有状态走完，一帧的全部工作在一次调用中完成。

#### 问题：requestAnimationFrame 的单步执行

Emscripten 不允许死循环（会冻结浏览器），改用 `emscripten_set_main_loop` 注册回调，由浏览器的 `requestAnimationFrame`（rAF）每帧调用一次。

最初的实现在每次 rAF 回调中只调用了一次 `UpdateAppStep()`——但这意味着完成一帧需要 4-5 个 rAF 周期（屏幕刷新周期）。在 60Hz 的显示器上，实际帧率只有 12-15 FPS，严重卡顿。

#### 解决方案：在单次 rAF 中完成完整帧

修复方法是在 rAF 回调中添加循环，确保所有未完成的更新步骤在一次 rAF 回调中全部执行完毕：

```cpp
void SexyAppBase::EmscriptenMainLoopCallback()
{
    SexyAppBase* app = Sexy::gSexyAppBase;
    if (app->mShutdown)
    {
        emscripten_cancel_main_loop();
        // ... 清理 & 同步存档 ...
        return;
    }
    if (app->mExitToTop)
        app->mExitToTop = false;

    bool updated = false;
    if (!app->UpdateAppStep(&updated))
        return;

    // 关键：在一个 rAF 中完成所有剩余状态
    while (updated
        || app->mUpdateAppState == UPDATESTATE_PROCESS_2
        || app->mHasPendingDraw)
    {
        if (!app->UpdateAppStep(&updated))
            break;
        if (!updated
            && app->mUpdateAppState == UPDATESTATE_PROCESS_DONE
            && !app->mHasPendingDraw)
            break;
    }
}
```

循环条件检查了三个维度：是否有更新被执行（`updated`）、状态机是否还在中间态（`UPDATESTATE_PROCESS_2`）、是否有待处理的绘制（`mHasPendingDraw`）。任何一个条件不满足都说明这一帧已完成。

`DoMainLoop()` 用 `emscripten_set_main_loop` 注册此回调：

```cpp
void SexyAppBase::DoMainLoop()
{
#ifdef __EMSCRIPTEN__
    emscripten_set_main_loop(EmscriptenMainLoopCallback, 0, 1);
#else
    while (!mShutdown) { /* ... */ }
#endif
}
```

`fps=0` 意味着使用 `requestAnimationFrame`（自动匹配显示器刷新率），`simulate_infinite_loop=1` 意味着 `DoMainLoop()` 不会返回——这正是在 Web 端需要的行为，因为 `Start()` 函数在 `DoMainLoop()` 之后有清理代码，如果 `DoMainLoop()` 返回会导致提前清理。

### 阻塞式等待的消除

#### nanosleep

桌面平台的帧率控制使用 `nanosleep` 实现精确等待。在浏览器中，主线程上任何阻塞调用都会冻结整个页面——不仅游戏画面卡住，连页面的响应性也丧失了。

由于项目已经使用了 `requestAnimationFrame`（`fps=0`）来驱动主循环，浏览器本身就会在每次 rAF 回调之间自动等待到下一个垂直同步信号，因此不需要额外的帧率限制 sleep。简单地用 `#ifndef __EMSCRIPTEN__` 跳过所有 `nanosleep` 调用即可：

```cpp
#ifndef __EMSCRIPTEN__
    timespec ts;
    ts.tv_sec = aTimeToNextFrame / 1000;
    ts.tv_nsec = (aTimeToNextFrame % 1000) * 1000000;
    nanosleep(&ts, &ts);
#endif
```

#### 加载线程

原版引擎使用 `std::thread` 在后台线程中加载资源，主线程通过 `WaitForLoadingThread()` 中的 `nanosleep` 轮询等待。在浏览器的单线程模型中，这会死锁——后台线程无法执行，而主线程在 sleep 中等待后台线程完成。

解决方案是在 Emscripten 下**直接在主线程中同步执行加载**，不创建线程：

```cpp
void SexyAppBase::StartLoadingThread()
{
    if (mLoadingThreadStarted)
        return;
    mYieldMainThread = true; 
    mLoadingThreadStarted = true;
#ifdef __EMSCRIPTEN__
    LoadingThreadProcStub(this);  // 直接调用，不创建线程
#else
    std::thread(LoadingThreadProcStub, this).detach();
#endif
}
```

`WaitForLoadingThread()` 在 Emscripten 下直接 `return`，因为加载已经在调用 `StartLoadingThread()` 时同步完成了。

### 商店与图鉴的冻结：Asyncify 协程化

解决完主循环卡顿后，打开疯狂戴夫的商店或植物图鉴时游戏再次冻结——画面完全静止，但音乐继续播放。

#### 原因：Dialog::WaitForResult 的同步阻塞

商店和图鉴通过模态对话框（Modal Dialog）实现，核心是 `Dialog::WaitForResult()`：

```cpp
// 桌面平台的原始实现：同步等待
while ((gSexyAppBase->UpdateAppStep(nullptr))
    && (mWidgetManager != nullptr)
    && (mResult == 0x7FFFFFFF));
```

这是一个典型的**同步轮询**——在 `while` 循环中不断推进游戏状态机，直到对话框被关闭（`mResult` 被设置）。在桌面平台上这没有任何问题——循环在推进游戏逻辑的同时也在推进渲染，屏幕正常更新。

但在浏览器中，这个 `while` 循环**永远不会返回控制权给浏览器**。浏览器无法执行 rAF 回调（被这个循环阻塞了），屏幕无法重绘，用户无法点击任何按钮关闭对话框——死锁。而音乐之所以继续播放，是因为 Web Audio API 使用独立的音频线程，不受主线程阻塞的影响。

#### 解决方案：Emscripten Asyncify

[Asyncify](https://emscripten.org/docs/porting/asyncify.html) 是 Emscripten 提供的一种**将同步 C/C++ 代码转换为异步执行**的机制。它通过在编译时对所有可能暂停的调用路径插入栈保存/恢复代码，使得 `emscripten_sleep()` 能够：

1. **保存**当前 C++ 调用栈（所有局部变量、程序计数器）
2. **返回**控制权给浏览器事件循环
3. 在浏览器完成一次 rAF 后**恢复** C++ 执行，从 `emscripten_sleep()` 的下一条语句继续

对于游戏引擎来说，这相当于一次**透明的协程 yield**——C++ 代码认为自己只是做了一次很短的 sleep，但实际上浏览器在这期间完成了一次完整的帧渲染和事件处理。

启用 Asyncify 只需添加链接标志 `-sASYNCIFY`。然后修改 `WaitForResult`：

```cpp
#ifdef __EMSCRIPTEN__
while ((mWidgetManager != nullptr) && (mResult == 0x7FFFFFFF))
{
    // 1. 推进游戏状态机
    bool updated = false;
    if (!gSexyAppBase->UpdateAppStep(&updated))
        break;

    // 2. 完成当前帧的所有剩余状态（与主循环相同的逻辑）
    while (updated
        || gSexyAppBase->mUpdateAppState == UPDATESTATE_PROCESS_2
        || gSexyAppBase->mHasPendingDraw)
    {
        if (!gSexyAppBase->UpdateAppStep(&updated))
            break;
        if (!updated
            && gSexyAppBase->mUpdateAppState == UPDATESTATE_PROCESS_DONE
            && !gSexyAppBase->mHasPendingDraw)
            break;
    }

    // 3. 让出控制权给浏览器
    emscripten_sleep(0);
}
#else
while ((gSexyAppBase->UpdateAppStep(nullptr))
    && (mWidgetManager != nullptr)
    && (mResult == 0x7FFFFFFF));
#endif
```

这里的 `emscripten_sleep(0)` 不是sleep 0 毫秒然后继续——它是一个**完整的协程 yield**。执行到这里时，Asyncify 保存整个 C++ 调用栈，控制权返回浏览器，浏览器处理完当前帧后在下一个 rAF 中恢复执行。

注意步骤 2 的完成当前帧循环是**必要的**——没有它的话，每次 yield 只执行了一个 `UpdateAppStep`，需要 4-5 个浏览器帧才能完成一个游戏帧，结果虽然不再冻结但帧率极低。加上完整帧循环后，商店和图鉴的帧率与正常关卡一致。

值得一提的是，Asyncify 会增加约 10-20% 的 wasm 二进制大小，因为它需要为每个可能经过 sleep 路径的函数生成栈保存/恢复代码。这是一个合理的权衡——代替方案是重构整个引擎的对话框系统为事件驱动，工作量和代码侵入性要大得多。

### 存档持久化：IDBFS 与生命周期管理

WebAssembly 模块的内存文件系统在页面关闭后就会丢失。为了持久化存档数据，可以利用 Emscripten 提供的 **IDBFS**（IndexedDB File System）——它将虚拟文件系统的内容镜像到浏览器的 IndexedDB 中。

#### 挂载与初始化

IDBFS 需要在游戏启动前挂载并同步：

```javascript
async function ensureSaveFsReady() {
    await window.moduleReadyPromise;
    try { Module.FS.mkdir('/saves'); } catch (e) {}
    try { Module.FS.mount(Module.FS.filesystems.IDBFS, {}, '/saves'); } catch (e) {}
    savesMounted = true;

    // 从 IndexedDB 加载已有存档到内存文件系统
    await new Promise(r => Module.FS.syncfs(true, err => {
        if (err) console.warn('IDBFS initial sync error:', err);
        r();
    }));
}
```

C++ 侧将存档目录设置为 `/saves/`：

```cpp
#elif defined(__EMSCRIPTEN__)
    SetAppDataFolder("/saves/");
```

#### 自动同步策略

`FS.syncfs(false, callback)` 将内存中的变更**持久化**到 IndexedDB。目前的自动同步策略有三层：

1. **定时同步**：每 5 秒自动执行一次 `syncfs`
2. **生命周期事件**：`visibilitychange`（切标签页）、`pagehide`（导航离开）、`beforeunload`（关闭窗口）时立即触发同步
3. **关闭保护**：如果距上次成功同步超过 7 秒，`beforeunload` 会弹出确认框提示用户等待

```javascript
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') void syncSaves();
});
window.addEventListener('pagehide', () => void syncSaves());
window.addEventListener('beforeunload', e => {
    if (!gameStarted) return;
    void syncSaves();
    if (Date.now() - lastSaveSyncAt >= SAVE_CLOSE_WARNING_MS) {
        e.preventDefault();
        e.returnValue = 'Recent save data may still be syncing.';
    }
});
```

`syncSaves()` 内部实现了**去重与队列化**——如果一次 `syncfs` 还在进行中，新的请求不会创建并发操作，而是设置一个 `queued` 标志，等当前操作完成后自动重做一次。这避免了 IndexedDB 的并发写入问题。

#### 游戏关闭时同步

在 C++ 侧，`SexyAppBase::Shutdown()` 中也会触发一次最终同步：

```cpp
#ifdef __EMSCRIPTEN__
EM_ASM(
    if (typeof FS !== 'undefined' && FS.syncfs) {
        FS.syncfs(false, function(err) {
            if (err) console.warn('IDBFS sync error on shutdown:', err);
        });
    }
);
#endif
```

### 资源上传与游戏启动流程

由于游戏不包含资源文件，浏览器版本需要用户在游戏启动前上传资源。这通过 `shell.html` 中的自定义上传界面实现。

使用 `-sINVOKE_RUN=0` 禁止 Emscripten 自动调用 `main()`，而是在 JavaScript 侧完成以下步骤后手动调用 `Module.callMain([])`：

1. 通过 drag-and-drop 或文件选择器收集 `main.pak` 和 `properties/` 文件
2. 使用 `Module.FS.writeFile()` 将文件写入 Emscripten 的内存文件系统
3. 挂载 IDBFS 并从 IndexedDB 恢复已有存档
4. 显示 canvas、隐藏上传界面
5. 调用 `Module.callMain([])` 启动游戏

文件遍历使用 `webkitGetAsEntry()` API 递归处理目录结构，确保 `properties/` 目录中的所有子文件都正确写入文件系统。

### 移动端文本输入：为软键盘提供真实焦点目标

WebAssembly 版本上线后，又暴露出一个只在移动浏览器上出现的问题：创建用户时，名字输入框虽然在游戏里已经获得焦点，但 **Android 和 iOS 下的浏览器不会仅因为 canvas 获得焦点就弹出软键盘**。桌面端有物理键盘，因此看起来一切正常；Android APK 则运行在原生 SDL 窗口中，也不受这个限制。

根本原因是浏览器的软键盘策略要求页面中必须存在一个**真实的、可聚焦的原生文本输入元素**。游戏内部的 `EditWidget` 走的是 SDL 文本输入事件链路，本身没有问题；缺的是浏览器这一侧的焦点桥接。

最小且不破坏架构的修复方式，是继续保留现有的 `EditWidget` 和 SDL 输入分发逻辑，只在 wasm 平台增加一个隐藏的文本输入代理，并在 JavaScript 与 C++ 之间做一层很薄的桥接：

* 在 `wasm/shell.html` 中添加一个不可见但真实存在的 `textarea`
* 在 `src/SexyAppFramework/platform/default/Input.cpp` 的 `StartTextInput()` / `StopTextInput()` 中，仅在 `__EMSCRIPTEN__` 下对该元素执行 `focus()` / `blur()`
* 在同一个 `Input.cpp` 中，通过 `EM_JS` 维护一个轻量的浏览器侧输入队列，把 `textarea` 的 `input` / `keydown` 事件转换成现有 `WidgetManager->KeyChar()` / `KeyDown()` 能消费的字符和编辑键

这样修复后：

- 桌面浏览器仍然可以直接用物理键盘输入，不受影响
- 移动浏览器在创建用户、重命名用户等文本输入场景下可以正常弹出软键盘
- 原生端完全不需要改动，因为这条桥接逻辑只存在于 wasm shell 和 Emscripten 分支中

这个方案的关键优点是：**没有改动任何游戏对话框、编辑框或输入法过滤逻辑，只是把浏览器原生文本输入可靠地桥接回现有的游戏输入通道**。相比直接把 SDL 的键盘目标强行绑定到隐藏元素，这种做法对桌面物理键盘和移动软键盘的兼容性更稳定，也更容易控制编辑键行为。

### 窗口与渲染：Emscripten 平台 Window.cpp

为 Emscripten 新增了专门的 `Window.cpp`（`src/SexyAppFramework/platform/emscripten/Window.cpp`），负责创建 WebGL 上下文。与桌面平台的主要区别：

- 使用 **OpenGL ES 2.0** Profile（`SDL_GL_CONTEXT_PROFILE_ES`），因为浏览器的 WebGL 对应 GLES2
- 关闭 alpha/depth/stencil buffer 以节省显存：`SDL_GL_SetAttribute(SDL_GL_ALPHA_SIZE, 0)` 等
- Swap interval 设为 0：帧率由 rAF 控制，不需要 SDL 层面的垂直同步

#### 全屏实现的重构与坐标修复

在适配浏览器的全屏功能时遇到了一个核心问题：如果直接调用桌面上常用的 `SDL_SetWindowFullscreen` 尝试进入全屏，SDL 会去强行修改 `<canvas>` 元素的实际像素大小以适应屏幕。这在浏览器沙箱下带来了毁灭性的后果——改变了 Canvas 内在分辨率后，它不再是游戏原生预期的 `800x600` 像素网格，导致 SDL 内保留的鼠标坐标映射发生严重偏移，根本无法准确定位并点击游戏内按钮。

为了解决这个问题，PvZ-Portable 选择剥离 SDL2 在 Web 上的默认全屏封装，转而直接请求浏览器原生的 Web Fullscreen API：

```cpp
// 在 SexyAppBase::SwitchScreenMode 中
#ifdef __EMSCRIPTEN__
    // Web API 全屏外部容器
    EmscriptenFullscreenStrategy strategy;
    strategy.scaleMode = EMSCRIPTEN_FULLSCREEN_SCALE_DEFAULT;
    strategy.canvasResolutionScaleMode = EMSCRIPTEN_FULLSCREEN_CANVAS_SCALE_NONE; // 严禁修改 canvas 分辨率
    strategy.filteringMode = EMSCRIPTEN_FULLSCREEN_FILTERING_DEFAULT;
    emscripten_request_fullscreen_strategy("#canvas-container", EM_FALSE, &strategy);
#else
    SDL_SetWindowFullscreen(mWindow, mIsWindowed ? 0 : SDL_WINDOW_FULLSCREEN_DESKTOP);
#endif
```

通过指定 `EMSCRIPTEN_FULLSCREEN_CANVAS_SCALE_NONE` 并通过 `#canvas-container` 发起全屏，这就将画面渲染环境与呈现环境隔离开来：底层 C++ 引擎始终在绝对准成的 `800x600` 内核里收发坐标，而外围浏览器承担将画面自适应填充到任何屏幕的工作，从而彻底解决了全屏模式下光标点击发生偏移的痛点。

### 安全退出与事件循环的死锁避免

在浏览器环境中，当用户通过界面退出游戏，或因为资源加载异常导致引擎调用 `SexyAppBase::DoExit()` 时，往往会导致游戏假死或画面冻结。根本原因在于：

如果直接同步调用引擎的析构操作 `Shutdown()`，此时执行环境可能仍在 UI 按钮的事件回调嵌套栈中。由于所有逻辑都在单个 JavaScript 线程执行，强行析构正在运行的调用链会导致栈崩溃。此外，仅仅停止引擎运行并不足以还原浏览器 DOM 环境，WebAssembly 内存的残留状态容易导致二次游玩不可用。

这里的解决方案是：在 JavaScript 侧利用 `window.onGameExit` 粗放而绝对安全地通过 `window.location.reload()` 彻底刷新环境；同时在 C++ 侧，使用 `emscripten_async_call` 进行**异步延迟退出**：

```cpp
#ifdef __EMSCRIPTEN__
void EmscriptenDeferredDoExit(void* arg) {
    SexyAppBase* app = static_cast<SexyAppBase*>(arg);
    app->Shutdown();
    EM_ASM( if (window.onGameExit) window.onGameExit(); );
}
#endif

void SexyAppBase::DoExit(int theCode)
{
    mExitReturnCode = theCode;
#ifdef __EMSCRIPTEN__
    if (mRunning) {
        // 利用 emscripten_async_call 将关闭操作推迟到当前调用栈结算之后
        emscripten_async_call(EmscriptenDeferredDoExit, this, 0);
        return;
    }
    Shutdown();
    EM_ASM( if (window.onGameExit) window.onGameExit(); );
#else
    // 桌面端使用原有的同步退出方式或发送 Quit 消息
#endif
}
```

这样一旦触发 `DoExit`，C++ 会安全弹出并结算所有当前回调栈，让出控制权后在事件循环末尾触发清理和页面重载，实现了一个无泄漏、不卡死的健壮退出流程。

### 其他平台守卫

所有修改都使用 `#ifdef __EMSCRIPTEN__` 或 `#ifndef __EMSCRIPTEN__` 守卫，确保对其他平台（Linux、Windows、macOS、Android、iOS、Switch、3DS）**零影响**：

| 文件 | 修改内容 | 守卫方式 |
| :--- | :--- | :--- |
| `SexyAppBase.cpp` | 主循环改造、sleep 消除、加载线程同步化、IDBFS 同步 | `#ifdef`/`#ifndef __EMSCRIPTEN__` |
| `Dialog.cpp` | Asyncify 协程等待 | `#ifdef __EMSCRIPTEN__` |
| `GLInterface.cpp` | 跳过 swap 后 `glClear` | `#ifndef __EMSCRIPTEN__` |
| `platform/default/Input.cpp` | wasm 文本输入开始/结束时切换隐藏输入元素焦点，并桥接浏览器输入事件到 `WidgetManager` | `#ifdef __EMSCRIPTEN__` |
| `main.cpp` | 跳过 `Shutdown`/`delete`（Start 不返回） | `#ifndef __EMSCRIPTEN__` |
| `ImageLib.cpp` | `optimize_coding = TRUE`（C 布尔类型修正） | 无条件（所有平台受益） |

`ImageLib.cpp` 的变更值得单独提一下：将 `cinfo.optimize_coding = 1` 改为 `= TRUE`，`jpeg_start_compress(&cinfo, true)` 改为 `TRUE`。这不是 Emscripten 特有的修复——libjpeg 的 API 使用 C 的 `boolean` 类型（即 `int`），用 C++ 的 `true`/`false` 可能在某些编译器上产生警告。这个修正对所有平台都有益。

### CI 与发布

GitHub Actions 添加了 `build-wasm` job，在 Ubuntu runner 上使用 `mymindstorm/setup-emsdk@v14` 配置 Emscripten，构建流程与本地 `build-wasm.sh` 基本一致。构建产物（`.html`、`.js`、`.wasm`）作为 artifact 上传，在 release job 中打包为 `pvz-portable-wasm.zip` 发布。

## 技术挑战回顾

| 问题类别 | 具体问题 | 根本原因 | 解决方案 |
| :--- | :--- | :--- | :--- |
| **渲染** | 画面完全黑屏 | swap 后 `glClear` 在 rAF 合成前清空了 canvas | Emscripten 下跳过 `glClear` |
| **交互** | 鼠标点击位置偏移 | Canvas 内在尺寸与显示尺寸不匹配 | 仅通过 CSS 缩放，保持内在尺寸 800×600 |
| **交互** | 全屏后光标失效 | SDL 全屏会强行修改 canvas 实际分辨率 | 弃用 SDL 全屏，直接调 Web Fullscreen API 并约束 CSS |
| **退出** | 退出游戏时画面挂起死锁 | 同步调用 `Shutdown` 破坏调用栈，且内存未清干净 | `emscripten_async_call` 异步延迟退出，JS 侧自动重载刷新 |
| **性能** | 主循环帧率仅 12-15 FPS | 每次 rAF 只执行一个 UpdateAppStep | 在 rAF 回调中循环完成完整帧 |
| **阻塞** | 商店/图鉴打开后冻结 | `WaitForResult` 同步循环阻塞浏览器 | Asyncify + `emscripten_sleep(0)` 协程 yield |
| **性能** | 商店/图鉴帧率低 | Asyncify yield 后只执行单步更新 | yield 前添加完整帧循环 |
| **阻塞** | 加载线程 sleep 死锁 | 单线程中 `nanosleep` + 线程等待 = 死锁 | 同步加载 + 跳过所有 sleep |
| **持久化** | 存档关闭后丢失 | 内存文件系统页面关闭即清空 | IDBFS + 5 秒自动同步 + 生命周期事件 |
| **输入** | 移动浏览器创建用户时无法弹出软键盘 | canvas 焦点不满足浏览器软键盘唤起条件 | 隐藏 `textarea` + 文本输入时 focus/blur + `EM_JS` 输入桥接 |
| **构建** | libopenmpt 无 Emscripten Port | 第三方库未提供 wasm 预编译 | `emmake make` 从源码构建 |
| **构建** | shell.html 修改后不重新链接 | CMake 不感知模板文件变化 | `LINK_DEPENDS` 显式依赖 |

## WebAssembly vs. Android vs. iOS 适配对比

| 维度 | Android | iOS | WebAssembly |
| :--- | :--- | :--- | :--- |
| **平台 UI 代码** | ~470 行 Java | 0 行 ObjC/Swift | ~300 行 JavaScript（shell.html） |
| **C++ 修改量** | ~100 行 | ~60 行 | ~130 行 |
| **主要挑战** | JNI 桥接、Scoped Storage、Activity 生命周期 | 路径、侧载、无 Mac 调试 | 单线程执行模型、同步到异步的改造 |
| **资源导入** | App 内 ZIP/文件夹导入 UI | Files app 手动拷贝 | 浏览器拖放/文件选择上传 |
| **存档方案** | 内部存储 | Documents 目录 | IndexedDB (IDBFS) |
| **线程模型** | 正常多线程 | 正常多线程 | 单线程 + Asyncify 协程 |
| **构建工具** | Gradle + NDK + CMake | CMake + Xcode | emcmake + CMake + Ninja |
| **安装方式** | `adb install` / APK 直装 | 签名侧载（AltStore 等） | **零安装**，打开网页即可 |

从用户体验角度看，WebAssembly 版本提供了**最低的使用门槛**——不需要下载安装包、不需要处理签名、不需要配置环境，一个链接即可使用。代价是每次进入游戏都需要导入游戏资源（约 40-70 MB，不过过程全在本地运行，没有网络传输，速度很快），以及浏览器环境下的性能略低于原生平台。

从开发角度看，WebAssembly 适配是三者中**技术复杂度最高的**——需要理解浏览器的事件循环模型、Asyncify 的栈保存机制、IDBFS 的同步语义、Emscripten 的 Port 系统和 CMake 集成。Android 的挑战在于 Java/JNI 对接和存储框架，iOS 的挑战在于编码之外的签名与调试门槛，而 WebAssembly 的挑战则集中在**重新思考 C++ 代码中隐含的同步执行假设**。

## 总结

WebAssembly 适配让 PvZ-Portable 实现了**零安装**的跨平台目标——Linux、Windows、macOS、Android、iOS/iPadOS，以及现在的任何拥有现代浏览器的设备。代码改动涉及 13 个文件、约 960 行，核心改动集中在主循环改造（`EmscriptenMainLoopCallback`）、阻塞式等待的协程化（`Dialog::WaitForResult` + Asyncify）、和持久化存储（IDBFS）三个层面。

这次适配最有趣的一点可能是：同一个 `UpdateAppStep` 状态机在桌面上被 `while` 循环驱动，在 Emscripten 上被 `requestAnimationFrame` 驱动，在模态对话框中被 Asyncify 协程驱动——三种完全不同的调度方式，但底层的状态转移逻辑完全一致。良好的架构分层使得这种换引擎不换内核的适配成为可能。

👉 **立即体验**: [https://wszqkzqk.github.io/pvz-portable-wasm/pvz-portable.html](https://wszqkzqk.github.io/pvz-portable-wasm/pvz-portable.html)

👉 **项目地址**: [https://github.com/wszqkzqk/PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable)

## ⚠️ 版权与说明

**再次强调：本项目仅包含代码引擎，不包含任何游戏素材！**

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件，通过网页上传界面导入：

*   `main.pak`
*   `properties/` 目录

本项目仅提供引擎代码，用于技术学习，**不包含**上述任何游戏资源文件，任何游戏资源均需要用户自行提供正版游戏文件。

本项目的源代码以 [**LGPL-3.0-or-later**](https://www.gnu.org/licenses/lgpl-3.0.html) 许可证开源，欢迎学习和贡献。
