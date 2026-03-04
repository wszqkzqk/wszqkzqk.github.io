---
layout:       post
title:        PvZ-Portable：进军 Android——将 100% 还原的植物大战僵尸年度版带到手机上
subtitle:     一个桌面游戏引擎的 Android 适配全纪录
date:         2026-03-04
author:       wszqkzqk
header-img:   img/games/bg-pvz-portable.webp
catalog:      true
tags:         C++ SDL2 OpenGL Android 开源软件 游戏移植 开源游戏 PvZ-Portable
---

## 引言

在之前的[项目总览](https://wszqkzqk.github.io/2026/01/26/PvZ-Portable/)和 [GLES2 渲染后端迁移](https://wszqkzqk.github.io/2026/02/16/PvZ-Portable-GLES2-Migration/)中，笔者介绍了 [PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable) 如何将《植物大战僵尸：年度版》的引擎带向各大平台。其中，GLES2 迁移尤其关键——将渲染后端统一到 OpenGL ES 2.0 这一最小公共子集，使得 Android 适配在图形层面成为可能。

然而，GPU 能渲染只是万里长征的起点。一个桌面 C++ 游戏引擎要在 Android 上跑起来，还需要解决一长串平台特异的问题：SDL2 的动态链接需求与 vcpkg 静态构建的冲突、Android FUSE 存储对游戏资源导入的限制、`SDLActivity` 的生命周期陷阱、屏幕方向控制的权责归属……

本文将从使用指南、设计决策和技术实现三个维度，完整记录 PvZ-Portable 的 Android 适配过程。

## ⚠️ 重要说明

**本项目仅包含代码引擎，不包含任何游戏素材！**

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。本项目的 Android 适配**纯粹是跨平台移植技术的研究**——研究如何将一个使用 SDL2 和 OpenGL 的 C++ 桌面引擎适配到 Android 平台，仅用于技术学习。

要研究或使用此项目，你**必须**拥有正版 PC 版《植物大战僵尸：年度版》（GOTY Edition）的资源文件（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies)上购买）。你需要从正版游戏中复制出 `main.pak` 和 `properties/` 目录，通过应用内的导入功能导入到 PvZ-Portable 中。

本项目的源代码以 [**LGPL-3.0-or-later**](https://www.gnu.org/licenses/lgpl-3.0.html) 许可证开源，欢迎学习和贡献。

## 使用指南

### APK 安装

从 [GitHub Releases](https://github.com/wszqkzqk/PvZ-Portable/releases) 下载 Android APK（目前仅提供 `arm64-v8a` 架构），或从源代码自行构建。APK 使用 GitHub Actions 的 debug 签名构建，安装时可能需要启用"允许安装未知来源的应用"。

### 首次启动

* 安装并启动应用。由于尚无游戏资源，应用会自动跳转到**资源导入界面**。
* 选择你**合法购买的正版** PC GOTY 版游戏的资源文件：
   * 点击 **Select ZIP File**，选择一个包含 `main.pak` 和 `properties/` 的 ZIP 压缩包（文件可以位于 ZIP 根目录或一层子目录内，例如 `PvZ/main.pak`）。
   * 或者点击 **Select Resource Folder**，选择直接包含 `main.pak` 和 `properties/` 的文件夹（或其直接父目录）。
* 导入成功后界面状态更新为 "Ready"，点击 **Start Game** 即可开始游戏。
* `Import Game Resources` 是必须的第一步，**不导入资源无法进入游戏**。如果用户之前在其他平台还有存档数据，还可以可选地通过下方的 `Import/Export Save Data (Optional)` 功能区迁移存档。

|[![#~/img/games/pvz-portable-android-manage-data-first-lossless.webp](/img/games/pvz-portable-android-manage-data-first-lossless.webp)](/img/games/pvz-portable-android-manage-data-first-lossless.webp)|[![#~/img/games/pvz-portable-android-import-resources-dir-lossless.webp](/img/games/pvz-portable-android-import-resources-dir-lossless.webp)](/img/games/pvz-portable-android-import-resources-dir-lossless.webp)|
|:----:|:----:|
| 首次打开时需按提示导入资源数据 | 选择需要导入的资源数据目录 |

### App Shortcut 数据管理

导入资源后，如果需要**重新导入资源或管理存档**，可以通过 **App Shortcut** 快速访问。长按桌面上的应用图标，选择 **Manage Data**，即可打开资源管理界面，与首次启动时的导入界面相同——包含所有的导入/导出按钮。

|[![#~/img/games/pvz-portable-android-how-to-enter-manage-data-ui.webp](/img/games/pvz-portable-android-how-to-enter-manage-data-ui.webp)](/img/games/pvz-portable-android-how-to-enter-manage-data-ui.webp)|[![#~/img/games/pvz-portable-android-manage-data-ui-lossless.webp](/img/games/pvz-portable-android-manage-data-ui-lossless.webp)](/img/games/pvz-portable-android-manage-data-ui-lossless.webp)|
|:----:|:----:|
| 在桌面长按图标可弹出数据管理按钮 | 数据管理界面可导入资源或管理存档 |

这种设计比为每个功能分别提供一个 shortcut 更合理：多个 shortcut 直接触发系统文件选择器，用户看到的只是一个突然弹出的文件管理器界面，没有任何上下文说明；而单个 shortcut 打开完整的管理界面，用户可以看到所有可用操作的按钮和当前状态（资源是否已导入、存档是否存在），再自行选择需要的操作。

### 关于操作体验

PvZ-Portable 的 Android 移植保留了原版游戏的 4:3 宽高比和鼠标交互模型——**没有做任何触屏特化的 UI 优化**。SDL2 会自动将触摸事件映射为鼠标输入，因此游戏完全可玩，但并未针对移动端手势操作进行优化。这是因为本项目的定位是**跨平台移植技术研究**，而非开发一款移动端游戏产品。

PvZ-Portable 目标特性即是在**任何平台**上都 **100% 还原**原版游戏的玩法和体验。因此，Android 版本一切游戏机制都与桌面版保持一致，**实现了在 Android 平台上的智慧树、生存困难模式等完整体验**。

|[![#~/img/games/pvz-portable-android-game-showcase1.webp](/img/games/pvz-portable-android-game-showcase1.webp)](/img/games/pvz-portable-android-game-showcase1.webp)|[![#~/img/games/pvz-portable-android-game-showcase2.webp](/img/games/pvz-portable-android-game-showcase2.webp)](/img/games/pvz-portable-android-game-showcase2.webp)|[![#~/img/games/pvz-portable-android-game-showcase3.webp](/img/games/pvz-portable-android-game-showcase3.webp)](/img/games/pvz-portable-android-game-showcase3.webp)|
|:----:|:----:|:----:|
|智慧树|禅境花园|戴夫商店|
|[![#~/img/games/pvz-portable-android-game-showcase4.webp](/img/games/pvz-portable-android-game-showcase4.webp)](/img/games/pvz-portable-android-game-showcase4.webp)|[![#~/img/games/pvz-portable-android-game-showcase5.webp](/img/games/pvz-portable-android-game-showcase5.webp)](/img/games/pvz-portable-android-game-showcase5.webp)|[![#~/img/games/pvz-portable-android-game-showcase6.webp](/img/games/pvz-portable-android-game-showcase6.webp)](/img/games/pvz-portable-android-game-showcase6.webp)|
|生存·浓雾（无尽）|生存·泳池（无尽）|生存模式关卡选择|

### 数据存储与存档兼容

所有游戏数据存储在 `Android/data/io.github.wszqkzqk.pvzportable/files/` 目录下，无需任何额外存储权限。存档数据（`userdata/` 目录）与桌面版**完全兼容**——你可以通过 Export/Import Saves 在 Android 和 Linux/Windows/macOS 之间迁移存档。关于存档格式的详细信息，请参阅[存档格式 v4](https://wszqkzqk.github.io/2026/01/30/PvZ-Portable-Save-Format-v4/) 的介绍。

需要注意的是，由于本项目目标是供研究学习，因此只对 APK 提供了 debug 签名。这意味着用户**不能直接升级覆盖安装新的 APK 版本**，而需要**先卸载旧版本，再安装新版本**。由于卸载时会删除 `Android/data/io.github.wszqkzqk.pvzportable/` 目录下的所有数据，因此如果需要保留存档数据，**请务必先使用 Export Save Data 功能将存档导出到外部目录**，完成 APK 卸载与重新安装后，再通过 Import Save Data 导入回应用目录。

## 设计决策

### 为什么用 SAF 而非存储权限

Android 平台上，让用户导入游戏资源文件的方式大致有以下几种：

| 方式 | 需要权限 | Android 适用版本 | 用户体验 |
| :--- | :--- | :--- | :--- |
| `READ_EXTERNAL_STORAGE` | 运行时危险权限 | Android 10 以下（10+ 被限制） | 需要弹出权限授予对话框，用户可能感到不安 |
| `MANAGE_EXTERNAL_STORAGE` | 特殊权限 | Android 11+ | 需要跳转系统设置页面，体验极差，且 Google Play 对此审查严格 |
| **Storage Access Framework (SAF)** | **无需任何权限** | Android 4.4+ | 调用系统文件选择器，用户主动选择文件，无需授权 |

SAF 是 Android 官方推荐的现代文件访问方式。它基于一个简单的原则：**用户通过系统文件选择器主动选择文件或目录，应用获得对所选内容的临时访问权**。这意味着：

- **零权限声明**：`AndroidManifest.xml` 中不需要声明 `READ_EXTERNAL_STORAGE` 或 `WRITE_EXTERNAL_STORAGE`，也不需要 `requestLegacyExternalStorage` 等过时的兼容标记。
- **面向未来**：不受 Android 版本演进中存储权限收紧的影响。
- **安全**：应用只能访问用户明确选择的文件，不会获得整个外部存储的访问权。

PvZ-Portable 的资源导入界面（`ResourceImportActivity`）完全基于 SAF 实现，使用 `ActivityResultContracts.OpenDocument`（选择 ZIP 文件）、`ActivityResultContracts.OpenDocumentTree`（选择文件夹）和 `ActivityResultContracts.CreateDocument`（导出 ZIP）三种契约，覆盖了所有的文件导入导出需求。

### 为什么用单个 App Shortcut

资源导入界面在首次启动时会自动展示。但后续启动时，如果游戏资源已存在，应用会直接进入游戏——用户没有入口再次打开导入界面。

Android 的 **App Shortcuts**（长按图标弹出的快捷方式）可以解决这个问题。最初的设计为每个功能（导入资源、导出存档、导入存档）各提供一个 shortcut，每个 shortcut 通过自定义 Intent action 直接触发对应的系统文件选择器。但这种方式的用户体验很差——用户长按图标后选择一个 shortcut，看到的是突然弹出的系统文件管理器，没有任何说明界面，也无法在操作前确认当前状态。

正确的做法是提供**单个** shortcut（"Manage Data"），打开与首次启动相同的完整资源管理界面。用户可以看到所有按钮和状态信息，自行选择需要的操作：

- **不侵入主流程**：正常使用时直接启动游戏，不增加额外步骤。
- **按需使用**：需要管理资源或存档时，长按图标即可快速进入管理界面。
- **零代码运行时开销**：静态快捷方式通过 `res/xml/shortcuts.xml` 声明，Android 系统直接解析 XML 并展示，应用代码中不需要处理自定义 action 或动态注册。

### SDLActivity 与自定义 Activity 的分工

SDL2 的 Android 支持基于 `SDLActivity`——一个由 SDL 项目提供的 Java Activity，负责创建 `SurfaceView`、管理 OpenGL 上下文、处理输入事件并将其转发给 C++ 端。PvZ-Portable 的 `PvZPortableActivity` 继承自 `SDLActivity`，是实际运行游戏的 Activity。

资源管理则完全交给独立的 `ResourceImportActivity`（继承 `AppCompatActivity`）。这种分离有几个好处：

- **职责清晰**：`SDLActivity` 启动时会初始化 SDL 运行时并创建 GL Surface。如果把资源导入 UI 也放在其中，SDL 初始化和资源导入会相互干扰。
- **可独立进入**：通过 App Shortcuts 直接启动 `ResourceImportActivity`，不触碰 SDL 的初始化流程。
- **生命周期简单**：`ResourceImportActivity` 作为普通的 `AppCompatActivity`，不需要处理 SDL 的线程模型和 Surface 回调。

`PvZPortableActivity` 在 `onCreate` 中检测游戏资源是否存在：如果不存在，通过 `Intent` 跳转到 `ResourceImportActivity`；如果存在，调用 `super.onCreate()` 走正常的 SDL 初始化流程。

## 技术实现

### Android 对 SDL2 动态库的要求

PvZ-Portable 在部分桌面平台（如 MSVC 构建）和 Android 都上使用 [vcpkg](https://vcpkg.io/) 管理 C/C++ 依赖（libjpeg-turbo、libpng、libvorbis、mpg123、libopenmpt 等）。对于 Android，vcpkg 提供了 `arm64-android` triplet，默认构建**静态库**。

然而，SDL2 在 Android 上**必须是动态库**。这是 SDL 的 Android 适配架构决定的：`SDLActivity.java` 通过 `System.loadLibrary("SDL2")` 在运行时动态加载 `libSDL2.so`，对应的 JNI 入口函数（如 `Java_org_libsdl_app_SDLActivity_nativeInit`）也只能通过动态链接来解析。如果 SDL2 被静态链接进 `libmain.so`，`System.loadLibrary("SDL2")` 将因找不到 `libSDL2.so` 文件而直接抛出 `UnsatisfiedLinkError`：

```
java.lang.UnsatisfiedLinkError: dlopen failed: library "libSDL2.so" not found
```

解决方案是**在 CI 中将 SDL2 单独从源码构建为动态库**，并在 vcpkg 的依赖声明中排除 Android 上的 SDL2：

```json
{
  "dependencies": [
    {
      "name": "sdl2",
      "platform": "!android"
    },
    "libjpeg-turbo",
    "libpng",
    ...
  ]
}
```

CI 中的 Android 构建步骤分为三个阶段：

* **下载 SDL2 源码**，从 GitHub Release 获取最新的 SDL2 2.x 版本。
* **使用 NDK 工具链编译 SDL2 动态库**：

```bash
cmake -B build-sdl2 \
  -DCMAKE_TOOLCHAIN_FILE=$ANDROID_NDK/build/cmake/android.toolchain.cmake \
  -DANDROID_ABI=arm64-v8a \
  -DANDROID_PLATFORM=android-28 \
  -DSDL_SHARED=ON \
  -DSDL_STATIC=OFF \
  -DCMAKE_INSTALL_PREFIX=$GITHUB_WORKSPACE/sdl2-android \
  -DCMAKE_BUILD_TYPE=Release \
  sdl2-src
cmake --build build-sdl2 -j$(nproc)
cmake --install build-sdl2
```

* **使用 vcpkg + NDK 构建游戏本体**，通过 `-DSDL2_DIR` 指向预构建的 SDL2：

```bash
cmake -B build-android-arm64-v8a \
  -DCMAKE_TOOLCHAIN_FILE=$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake \
  -DVCPKG_TARGET_TRIPLET=arm64-android \
  -DVCPKG_CHAINLOAD_TOOLCHAIN_FILE=$ANDROID_NDK/build/cmake/android.toolchain.cmake \
  -DANDROID_ABI=arm64-v8a \
  -DANDROID_PLATFORM=android-28 \
  -DSDL2_DIR=$GITHUB_WORKSPACE/sdl2-android/lib/cmake/SDL2 \
  -DCMAKE_BUILD_TYPE=Release
```

最终将 `libmain.so`、`libSDL2.so` 和 vcpkg 构建的所有 `.so` 依赖一起复制到 `jniLibs/arm64-v8a/` 目录下，由 Gradle 打包进 APK。

### SDLActivity Java 源码的集成

SDL2 的 Android 适配还需要一系列 Java 文件（`SDLActivity.java`、`SDLSurface.java`、`SDLAudioManager.java` 等），它们提供了 Activity 生命周期管理、Surface 回调和 JNI 桥接。这些文件位于 SDL2 源码树的 `android-project/app/src/main/java/` 目录下。

在 Gradle 构建中，笔者通过 `sourceSets` 将 SDL2 源码目录添加为额外的 Java 源码路径：

```groovy
sourceSets {
    main {
        java.srcDirs = [
            'src/main/java',
            "${project.rootDir}/../sdl2-src/android-project/app/src/main/java"
        ]
    }
}
```

这样 SDL 的 Java 文件和项目自己的 Java 文件一起编译，避免了在项目仓库中硬拷贝 SDL 的 Java 源码。CI 中下载的 SDL2 源码目录（`sdl2-src`）同时服务于 C++ 编译和 Java 编译两个阶段。

### SuperNotCalledException：SDLActivity 生命周期的陷阱

`PvZPortableActivity` 继承 `SDLActivity`，后者继承 `Activity`。Android 要求每个 Activity 的 `onCreate()` **必须调用** `super.onCreate()`，否则系统会抛出 `SuperNotCalledException` 并强制结束应用。

最初的代码在检测到游戏资源不存在时，直接调用 `finish()` 跳转到导入界面：

```java
@Override
protected void onCreate(Bundle savedInstanceState) {
    if (!hasGameResources(extDir)) {
        // BUG: super.onCreate() 从未被调用！
        startActivity(new Intent(this, ResourceImportActivity.class));
        finish();
        return;
    }
    super.onCreate(savedInstanceState);
    // ...
}
```

这段代码在大多数运行时恰巧能工作——因为 `finish()` 后 Activity 很快被销毁，系统的合规检查可能来不及触发。但在某些设备或 Android 版本上，系统会在 `onPause()`/`onStop()` 时检查 `super.onCreate()` 是否被调用，导致崩溃。

修复很简单：在 `finish()` 之前先调用 `super.onCreate(savedInstanceState)`：

```java
@Override
protected void onCreate(Bundle savedInstanceState) {
    File extDir = getExternalFilesDir(null);
    if (extDir != null && !extDir.exists()) extDir.mkdirs();

    if (!hasGameResources(extDir)) {
        super.onCreate(savedInstanceState);
        startActivity(new Intent(this, ResourceImportActivity.class));
        finish();
        return;
    }

    super.onCreate(savedInstanceState);
    hideSystemUI();
}
```

虽然在即将 `finish()` 的 Activity 上调用 `super.onCreate()` 会触发 `SDLActivity` 的部分初始化逻辑（包括短暂创建 SDL 的 Surface），但这些资源会在 `finish()` 后的 `onDestroy()` 中被正常回收，不会造成泄漏或副作用。相比之下，不调用 `super.onCreate()` 会导致确定性的崩溃。

### 屏幕方向：SDL_HINT_ORIENTATIONS 的正确运用

植物大战僵尸是一个横屏游戏。在 `AndroidManifest.xml` 中声明 `android:screenOrientation="landscape"` 似乎就够了——对于普通 Activity 确实如此。但 `SDLActivity` 有一个鲜为人知的行为：**它会在运行时读取 `SDL_HINT_ORIENTATIONS` hint 并调用 `setRequestedOrientation()` 覆盖 Manifest 的声明**。

如果 `SDL_HINT_ORIENTATIONS` 没有被设置，`SDLActivity` 在某些代码路径中可能使用默认值（取决于 SDL 版本），导致屏幕方向行为不可预测。为了确保横屏锁定行为的可靠性，笔者在 C++ 侧的窗口创建代码中，**在 `SDL_Init(SDL_INIT_VIDEO)` 之前**设置了这个 hint：

```cpp
#ifdef __ANDROID__
    // Lock to landscape on Android; SDL's Java layer reads this hint
    SDL_SetHint(SDL_HINT_ORIENTATIONS, "LandscapeLeft LandscapeRight");
#endif

    SDL_Init(SDL_INIT_VIDEO);
```

`"LandscapeLeft LandscapeRight"` 允许左右两个横屏方向，即用户转动手机 180° 时画面会自动翻转，但不允许竖屏。这个 hint 的设置时机很关键——必须在 `SDL_Init(SDL_INIT_VIDEO)` 之前，因为 SDL 在初始化视频子系统时就会读取它并调用 `setRequestedOrientation()`。

值得注意的是，`ResourceImportActivity`（资源导入界面）**不设置固定方向**——它跟随系统默认的自动旋转行为。这是因为导入界面是一个竖向滚动列表，在竖屏和横屏下都能正常使用。

### 沉浸式全屏

游戏运行时应该隐藏系统的状态栏和导航栏以获得沉浸式的全屏体验。Android 的全屏 API 在不同版本间有显著变化：

- **Android 11 (API 30) 及以上**：使用 `WindowInsetsController` API，这是现代的推荐方式。
- **Android 10 及以下**：使用已废弃的 `SYSTEM_UI_FLAG_IMMERSIVE_STICKY` 标志组合。

`PvZPortableActivity` 实现了跨版本兼容的 `hideSystemUI()` 方法：

```java
private void hideSystemUI() {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
        Window window = getWindow();
        WindowInsetsController controller = window.getInsetsController();
        if (controller != null) {
            controller.hide(WindowInsets.Type.statusBars()
                          | WindowInsets.Type.navigationBars());
            controller.setSystemBarsBehavior(
                WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
        }
    } else {
        getWindow().getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
            | View.SYSTEM_UI_FLAG_FULLSCREEN
            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
    }
}
```

此外，`PvZPortableActivity` 还在 `onWindowFocusChanged(hasFocus)` 中重新调用 `hideSystemUI()`——这是因为当用户从通知栏或多任务切回游戏时，系统栏可能会被重新显示。配合 Manifest 中 `android:theme="@android:style/Theme.NoTitleBar.Fullscreen"` 的声明（隐藏 Action Bar 上的标题栏和默认的状态栏），游戏在运行时实现了完整的无边框沉浸式体验。

### Android 上概率性 GL 上下文创建失败与重试机制

在 Android 上测试时发现一个概率性的原生崩溃：

```
GLImage::GLImage(GLInterface*)+16
GetImage → GetSharedImage → DoLoadImage
TodLoadNextResource → TodLoadResources → LawnApp::Init → SDL_main
```

崩溃位于 `GLImage` 构造函数，原因是 `mGLInterface` 为 `nullptr` 时直接解引用。

**根因分析**：Android 上 OpenGL ES 2.0 是原生图形 API，`SDL_GL_CreateContext` 在理论上不应该失败——SDL2 保证在 `surfaceChanged` 回调之后才启动 native 线程。但实际上，Android 的 Activity 生命周期事件（例如启动过程中的通知弹出、快速切换应用、系统资源压力等）可以在极短的时间窗口内导致 EGL surface 被临时回收，使 `SDL_GL_CreateContext` 返回 `NULL`。这种竞态解释了崩溃的**概率性**——大多数情况下启动足够快、surface 持续可用，偶尔才会触发。

原始代码的问题在于：ES 2.0 上下文创建失败后，会继续尝试桌面 GL 2.1 回退（这在 Android 上永远不可能成功），两次都失败后 `MakeWindow()` 直接 `return`，`mGLInterface` 留空。随后 `LawnApp::Init()` 继续执行资源加载，在 `GetSharedImage → GetImage → new GLImage(mGLInterface)` 处解引用空指针。

**修复方案**由三层组成：

**第一层——根因修复：Android 上下文创建重试**。在 `MakeWindow()` 中，如果首次 `SDL_GL_CreateContext` 失败，通过 `SDL_PumpEvents()` 驱动事件循环让 surface 回调有机会到达，然后重试，最多等待 2 秒（20 × 100ms）：

```cpp
#ifdef __ANDROID__
    for (int retry = 0; !mContext && retry < 20; ++retry)
    {
        SDL_Delay(100);
        SDL_PumpEvents();
        if (!mWindow)
            mWindow = (void*)SDL_CreateWindow(/* ... */);
        if (mWindow)
            mContext = (void*)SDL_GL_CreateContext((SDL_Window*)mWindow);
    }
    if (!mContext) { /* 清理并 return */ }
#else
    // 非 Android 平台：回退到桌面 GL 2.1
#endif
```

同时，`#ifdef __ANDROID__` / `#else` 条件编译跳过了 Android 上无意义的桌面 GL 2.1 回退路径。

**第二层——失败传播**。在 `SexyAppBase::Init()` 中，`MakeWindow()` 返回后检查 `mGLInterface`，若为空则标记 `mShutdown = true` 并立即返回。`LawnApp::Init()` 在 `SexyApp::Init()` 之后检查 `mShutdown`，若已标记则跳过后续资源加载直接退出。这保证了即便所有重试都失败，应用也能优雅退出而非崩溃：

```cpp
// SexyAppBase::Init()
MakeWindow();
if (mGLInterface == nullptr)
{
    fprintf(stderr, "FATAL: Failed to create OpenGL interface.\n");
    mShutdown = true;
    return;
}

// LawnApp::Init()
SexyApp::Init();
if (mShutdown)
    return;
```

**第三层——GLImage 构造函数防御**。`GLImage(GLInterface*)` 的初始化列表改为三元表达式 `theGLInterface ? theGLInterface->mApp : gSexyAppBase`，`AddGLImage` / `RemoveGLImage` 调用前加空指针检查。这是零开销的防御性编程，确保即使有未预见的代码路径传入 `nullptr`，也不会立即崩溃。

### 动画图集（ReanimAtlas）缓冲区溢出

在 Android 上打开僵尸图鉴时发现一个必现的原生崩溃：

```
Reanimation::DrawTrack(Sexy::Graphics*, int, int, TodTriangleGroup*)+496
DrawRenderGroup → MakeCachedZombieFrame → DrawCachedZombie → AlmanacDialog::DrawZombies
```

**根因分析**：PvZ-Portable 的动画系统使用 `ReanimAtlas`（动画图集）来优化渲染——将同一动画的多张小贴图合并到一张大纹理上，减少 draw call。创建图集时，每张贴图的原始 `Image*` 指针会被替换为一个编码后的小整数索引（`(Image*)(index + 1)`，值域 1~64），渲染时通过 `GetEncodedReanimAtlas()` 反查回真正的贴图数据。

问题出在图集的容量限制上。`ReanimAtlas::mImageArray` 是一个固定大小为 `MAX_REANIM_IMAGES = 64` 的数组，但 `AddImage()` 的越界保护使用的是 `TOD_ASSERT`——在 Release 构建中被编译为空语句。GOTY 版游戏中 `zombatar_zombie_head.reanim` 引用了 **171 张**独立贴图，远超 64 的上限。在桌面平台上，这种越界写入恰好覆盖到 `mImageCount` 和 `mMemoryImage` 字段但未触发段错误；而 Android 的 Scudo 内存分配器对堆布局更严格，越界访问直接导致 SIGSEGV。

修复集中在 `ReanimAtlas.cpp` 的四个根因点：

**1. `AddImage` 溢出保护**。将 debug-only 的 `TOD_ASSERT(mImageCount < MAX_REANIM_IMAGES)` 替换为运行时检查，超限时直接跳过：

```cpp
if (mImageCount >= MAX_REANIM_IMAGES)  // Prevent array overflow
    return;
```

**2. 编码阶段条件修正**。`ReanimAtlasCreate` 的编码阶段（将 `Image*` 替换为整数索引）中，原代码对 `FindImage` 返回 -1（图片未加入图集）的情况使用 `TOD_ASSERT`，Release 下会编码为 `(Image*)(0)`（即 `nullptr`）。修正为 `continue` 跳过：

```cpp
intptr_t aImageIndex = FindImage(aImage);
if (aImageIndex < 0)  // Image not in atlas (e.g. mNumCols>1 or atlas full)
    continue;
aImage = (Image*)(aImageIndex + 1);  // Encode atlas index as Image*
```

**3. `GetEncodedReanimAtlas` 运行时边界检查**。原代码的越界保护同样是 debug-only 的 `TOD_ASSERT`，在 Release 中可能返回越界指针。替换为运行时检查，并将指针比较从 `intptr_t` 改为语义更正确的 `uintptr_t`：

```cpp
if (theImage == nullptr || reinterpret_cast<uintptr_t>(theImage) > 1000)
    return nullptr;
intptr_t aAtlasIndex = reinterpret_cast<intptr_t>(theImage) - 1;
if (aAtlasIndex < 0 || aAtlasIndex >= mImageCount)  // Runtime bounds check
    return nullptr;
```

**4. 排序比较器修正**。`sSortByNonIncreasingHeight` 在高度和宽度都相同时，使用 `&image1` vs `&image2`（元素地址）作为 tiebreaker。但 `std::sort` 在排序过程中会交换元素，元素的地址不是稳定标识符，导致比较函数违反**严格弱序**要求（同一对逻辑元素在交换前后可能返回不同的比较结果），属于未定义行为。修正为使用 `mOriginalImage` 指针（排序过程中不变的元素属性）：

```cpp
return reinterpret_cast<uintptr_t>(image1.mOriginalImage)
     > reinterpret_cast<uintptr_t>(image2.mOriginalImage);
```

这四处修复全部集中在 `ReanimAtlas.cpp`（+10/-7 行），是纯粹的根因层修复。由于修复后编码阶段只编码确实存在于图集中的图片、`GetEncodedReanimAtlas` 对所有合法编码值都能正确解码，**不需要**在 `DrawTrack` 等消费端做额外的防御性空指针检查——任何此类检查都是死代码。

### 资源导入的实现细节

`ResourceImportActivity` 是一个约 390 行的 Java 文件，实现了完整的资源和存档管理功能。

#### ZIP 导入与路径前缀剥离

用户选择的 ZIP 文件内部结构可能不统一——有些 ZIP 的根目录直接就是 `main.pak` 和 `properties/`，有些则包裹在一层子目录中（如 `PvZ/main.pak`）。为了兼容这两种情况，`importFromZip()` 使用 `stripCommonPrefix()` 方法进行智能路径处理：

```java
private String stripCommonPrefix(String name) {
    name = name.replace('\\', '/').replaceAll("^/+", "");
    if (isKnownTopLevel(name)) return name;

    // Strip one leading directory component
    int slash = name.indexOf('/');
    if (slash > 0 && slash < name.length() - 1) {
        return name.substring(slash + 1);
    }
    return name;
}
```

逻辑很直白：如果条目路径以已知的顶级文件/目录名开头（`main.pak`、`properties/`、`data/`、`images/` 等），说明 ZIP 根目录即为游戏资源根目录，直接使用原始路径；否则剥离第一层目录前缀。这种做法覆盖了绝大多数用户打包 ZIP 的习惯。

#### 文件夹导入与 DocumentFile

文件夹导入使用 `DocumentFile` API 递归遍历目录树。由于 SAF 返回的 `Uri` 不是传统文件路径，不能直接使用 `java.io.File` 操作——必须通过 `DocumentFile.fromTreeUri()` 创建 `DocumentFile` 实例，逐级使用 `listFiles()` 遍历和 `getContentResolver().openInputStream()` 读取。

同样地，`importFromDirectory()` 也处理了嵌套目录的情况：如果用户选择的目录本身不含 `main.pak`，则向下一层搜索包含 `main.pak` 的子目录作为实际的源目录。

#### 存档导入导出

存档数据存储在 `userdata/` 子目录下。导出功能使用 `ZipOutputStream` 将整个 `userdata/` 递归压缩为 ZIP 文件，通过 SAF 的 `CreateDocument` 契约让用户选择保存位置。

导入功能同时支持 ZIP 文件和文件夹两种形式。ZIP 导入时，如果条目路径不以 `userdata/` 开头，会自动补上这个前缀——这使得用户无论是导出的标准 ZIP 还是手动创建的 ZIP 都能被正确识别。文件夹导入则会智能检测所选目录是 `userdata/` 本身还是包含 `userdata/` 的父目录。

所有的文件操作都在后台线程中执行，通过 `runOnUiThread()` 更新 UI 状态，避免阻塞主线程。

### Gradle 构建系统

Android 构建使用标准的 Gradle 项目结构。`build.gradle` 中有一个关键的 `usePrebuiltLibs` 属性开关：

- **CI 模式**（`-PusePrebuiltLibs=true`）：跳过 Gradle 的 `externalNativeBuild`（CMake），直接使用已预编译好的 `.so` 文件。这与前述 CI 的三阶段构建相配合——CMake 编译在 Gradle 之前完成，产出的 `.so` 已被复制到 `jniLibs/` 目录下。
- **本地开发模式**（默认）：Gradle 自动调用 CMake 编译 native 代码，方便开发者直接在 Android Studio 中构建。

依赖方面，项目使用了三个 AndroidX 库：

```groovy
dependencies {
    implementation 'androidx.appcompat:appcompat:1.7.0'
    implementation 'androidx.activity:activity:1.10.1'
    implementation 'androidx.documentfile:documentfile:1.0.1'
}
```

其中 `appcompat` 提供 `AppCompatActivity`（`ResourceImportActivity` 的基类），`activity` 提供 `ActivityResultContracts`（SAF 文件选择器的现代 API），`documentfile` 提供 `DocumentFile`（SAF 目录遍历）。

### 零权限设计

最终的 `AndroidManifest.xml` **不声明任何存储权限**：

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-feature
        android:glEsVersion="0x00020000"
        android:required="true" />
    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:hasFragileUserData="true"
        android:supportsRtl="true">
        <!-- ... Activities ... -->
    </application>
</manifest>
```

唯一的 `<uses-feature>` 声明是 OpenGL ES 2.0——这是游戏渲染的硬性需求。`hasFragileUserData="true"` 告诉 Android 在用户卸载应用时提示是否保留数据，避免存档意外丢失。除此之外，没有 `READ_EXTERNAL_STORAGE`、没有 `WRITE_EXTERNAL_STORAGE`、没有 `MANAGE_EXTERNAL_STORAGE`、没有 `FileProvider`——所有文件访问都通过 SAF 完成。

## 技术挑战回顾

Android 适配过程中遇到的主要技术挑战可以归纳为以下几类：

| 问题类别 | 具体问题 | 根本原因 | 解决方案 |
| :--- | :--- | :--- | :--- |
| **构建** | `dlopen failed: library "libSDL2.so" not found` | vcpkg 在 Android 上默认构建静态库，而 SDLActivity 通过 JNI 动态加载 SDL2 | 从源码单独构建 SDL2 共享库，vcpkg 中排除 Android 的 SDL2 |
| **生命周期** | `SuperNotCalledException` 崩溃 | 检测到无资源时直接 `finish()`，跳过了 `super.onCreate()` | 在 `finish()` 之前先调用 `super.onCreate()` |
| **屏幕方向** | Manifest 中声明的 `screenOrientation` 无效 | `SDLActivity` 在运行时通过 `setRequestedOrientation()` 覆盖 Manifest 声明 | 在 C++ 侧 `SDL_Init` 之前设置 `SDL_HINT_ORIENTATIONS` |
| **竞态** | `GLImage::GLImage(GLInterface*)+16` 概率性崩溃 | Activity 生命周期事件导致 EGL surface 短暂不可用，`SDL_GL_CreateContext` 返回 `NULL` | Android 端重试上下文创建 + `Init()` 失败传播 + `GLImage` 构造函数防御 |
| **内存安全** | `Reanimation::DrawTrack` 僵尸图鉴必现崩溃 | `ReanimAtlas` 固定 64 元素数组被 171 张图片越界写入，Release 中 `TOD_ASSERT` 为空 | `AddImage` 运行时溢出保护 + 编码/解码阶段边界检查 + 排序比较器严格弱序修正 |
| **文件访问** | Android Scoped Storage 限制直接文件访问 | Android 10+ 逐步禁用传统存储权限 | 全面采用 SAF，零权限设计 |

## 总结

PvZ-Portable 的 Android 适配是一次典型的"桌面引擎移动化"实践。GLES2 迁移解决了图形 API 的兼容性问题，但 Android 平台还带来了一系列图形之外的挑战——从最基础的构建链路（SDL2 必须动态链接）到 Android 特有的存储模型（SAF）、Activity 生命周期约束和 SDL 运行时行为的隐含覆盖（屏幕方向）。

这些问题的解决方案遵循一个共同的原则：**尊重平台的规则，而不是试图绕过它**。使用 SAF 而非申请危险权限、通过 SDL hint 而非强行 override 来控制方向、在 `finish()` 前确保 `super.onCreate()` 被调用——每一项都是在 Android 平台的框架内找到正确的做法。

整个 Android 适配的代码量并不大——约 390 行 Java（`ResourceImportActivity`）、约 80 行 Java（`PvZPortableActivity`）、几十行 XML（Manifest、layout、shortcuts、strings）、几十行 C++ 补丁（SDL hint、GL 上下文重试、GLImage 防御和 ReanimAtlas 越界修复），以及 CI 配置的调整。真正的工作量在于理解 Android 平台的各层抽象——从 Gradle/NDK/vcpkg 的构建体系到 SDLActivity 的运行时行为——并找到每个问题的正确解法。

👉 **项目地址**: [https://github.com/wszqkzqk/PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable)

## ⚠️ 版权与说明

**再次强调：本项目仅包含代码引擎，不包含任何游戏素材！**

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件，通过应用内的导入功能导入：

*   `main.pak`
*   `properties/` 目录

本项目仅提供引擎代码，用于技术学习，**不包含**上述任何游戏资源文件，任何游戏资源均需要用户自行提供正版游戏文件。

本项目的源代码以 [**LGPL-3.0-or-later**](https://www.gnu.org/licenses/lgpl-3.0.html) 许可证开源，欢迎学习和贡献。
