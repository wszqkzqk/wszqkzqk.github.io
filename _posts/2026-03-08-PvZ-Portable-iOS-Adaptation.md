---
layout:       post
title:        PvZ-Portable：100% 复原的植物大战僵尸正式支持 iOS/iPadOS
subtitle:     在 iPhone 和 iPad 上运行完整的 PvZ 引擎——纯 C++ 的跨平台移植实践
date:         2026-03-08
author:       wszqkzqk
header-img:   img/games/bg-pvz-portable.webp
catalog:      true
tags:         C++ SDL2 OpenGL iOS 开源软件 游戏移植 开源游戏 PvZ-Portable
---

## 引言

在完成 [Android 适配](https://wszqkzqk.github.io/2026/03/04/PvZ-Portable-Android-Adaptation/)后，PvZ-Portable 已经在 Linux、Windows、macOS、Android、Nintendo Switch 和 Nintendo 3DS 上运行。现在，iOS/iPadOS 也加入了这个大家庭——你可以在 iPhone 和 iPad 上运行 100% 复原的开源版植物大战僵尸了。

与 Android 适配不同，iOS 适配**不需要任何 Objective-C 或 Swift 代码**，整个适配在纯 C++ 层面完成。不过，代码量小并不意味着过程轻松——没有 Mac 的情况下，iOS 的调试测试远比 Android 困难，笔者在整个过程中完全依赖 CI 编译，并在北京大学学生 Linux 俱乐部中召集游戏爱好者协助完成真机测试。本文将记录适配中遇到的问题和解决方案。

## ⚠️ 重要说明

**本项目仅包含代码引擎，不包含任何游戏素材！**

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。本项目的 iOS 适配**纯粹是跨平台移植技术的研究**——研究如何将一个使用 SDL2 和 OpenGL ES 的 C++ 引擎适配到 iOS 平台，仅用于技术学习。本项目与 EA/PopCap 没有任何商业合作或授权关系，也不包含任何受版权保护的游戏资源。

要研究或使用此项目，你**必须**拥有正版 PC 版《植物大战僵尸：年度版》（GOTY Edition）的资源文件（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies)上购买）。

本项目的源代码以 [**LGPL-3.0-or-later**](https://www.gnu.org/licenses/lgpl-3.0.html) 许可证开源，欢迎学习和贡献。

## 使用指南

### IPA 安装

从 [GitHub Releases](https://github.com/wszqkzqk/PvZ-Portable/releases) 下载未签名的 iOS IPA（`pvz-portable-ios-arm64.ipa`），或使用 `ios/build-ios.sh` 脚本从源码构建。

由于 Apple 的签名机制，IPA **不能像 APK 一样直接安装**。Android 上一个 `adb install xxx.apk` 就能完成的事情，在 iOS 上需要经过签名和侧载（sideload）的曲折流程。目前常见的侧载方案包括：

- **[AltStore](https://altstore.io/)**：最流行的免费侧载方案，使用个人 Apple ID 签名，有效期 7 天，到期需续签。**需要 Mac 或 Windows 上的 AltServer 配合**。
- **[TrollStore](https://github.com/opa334/TrollStore)**（iOS 14.0–16.6.1）：利用系统漏洞实现的永久安装方案，无需签名续期。但仅支持特定 iOS 版本。
- **Xcode 直接部署**：使用免费 Apple ID 在 Xcode 中直接构建部署到设备。**需要 Mac**。

无论哪种方案，都不如 Android 的 `adb install` 来得直接。笔者在适配过程中没有 Mac，通过在北京大学学生 Linux 俱乐部召集游戏爱好者协助完成侧载和真机测试。

### 导入游戏资源

iOS 版**没有 ZIP 导入功能和资源管理 UI**，需要用户手动拷贝文件。Android 版之所以能提供完整的 `ResourceImportActivity`（支持 ZIP 一键导入），是因为 Android 适配本身就需要编写 Java Activity 代码，顺便实现导入 UI 的成本很低。而 iOS 适配的整体思路是零平台 UI 代码（不引入 ObjC/Swift），在这个前提下实现类似的导入界面成本较高，因此采用了更朴素的方案。

Info.plist 中声明了 `UIFileSharingEnabled` 和 `LSSupportsOpeningDocumentsInPlace`，这使得 app 的 Documents 目录暴露在两个位置：

- **iOS Files 应用**：打开 Files → 浏览 → 我的 iPhone/iPad → PvZ Portable
- **Finder/iTunes 文件共享**：连接设备到 Mac/PC，在 Finder 侧边栏（或 iTunes 的"文件共享"）中选择 PvZ Portable

将正版游戏的 `main.pak` 和 `properties/` 目录直接拷贝到此处即可。启动 app 时会自动检测这些文件——如果缺失，会弹出提示对话框说明操作步骤并退出。

Finder/iTunes 文件共享方式需要用数据线连接设备和电脑，Files app 方式需要先通过某种途径将文件传到设备上（AirDrop、iCloud Drive 等）。操作步骤比 Android 版的"在 app 内选择 ZIP 文件"要繁琐一些，这是保持零平台 UI 代码的取舍。

### 存档兼容

存档文件与桌面版和 Android 版**完全兼容**。存档数据同样保存在 Documents 目录下的 `userdata/` 子目录中，可以通过 Files app 或 Finder 直接拷贝进出设备。

### 关于操作体验

与 Android 版一致，iOS 版保留了原版游戏的 4:3 宽高比和鼠标交互模型。SDL2 自动将触摸事件映射为鼠标输入，游戏完全可玩，但未针对触屏操作进行特化优化。

## 技术实现

### 构建体系：CMake + vcpkg + Xcode Generator

iOS 构建使用 CMake 的 Xcode generator，通过 vcpkg 管理 C/C++ 依赖。与 Android 的构建体系对比：

| 维度 | Android | iOS |
| :--- | :--- | :--- |
| 构建系统 | Gradle + CMake + NDK | CMake + Xcode Generator |
| 包管理 | vcpkg (arm64-android) + 单独构建 SDL2 共享库 | vcpkg (arm64-ios) |
| SDL2 形式 | **必须动态库**（`SDLActivity` 通过 JNI 加载） | **静态库**（vcpkg 默认） |
| 输出格式 | APK（Gradle 打包） | .app bundle → unsigned IPA |
| 签名 | debug keystore（自动） | ad-hoc（`-`，无需证书） |

Android 必须将 SDL2 单独构建为共享库（`.so`），因为 `SDLActivity.java` 在运行时通过 `System.loadLibrary("SDL2")` 动态加载。而 iOS 上 SDL2 可以静态链接——SDL2 的 iOS 支持完全通过 Objective-C 源码编译到应用内部，不需要动态加载。因此 vcpkg 的默认静态构建在 iOS 上开箱即用，无需像 Android 那样从 vcpkg 中排除 SDL2 再单独构建。

CMake 配置的核心参数：

```bash
cmake -B build-ios \
  -DCMAKE_TOOLCHAIN_FILE=$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake \
  -DVCPKG_TARGET_TRIPLET=arm64-ios \
  -DVCPKG_OVERLAY_PORTS=ios/ports \
  -DCMAKE_SYSTEM_NAME=iOS \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=15.0 \
  -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -G Xcode
```

其中 `arm64-ios` 是 vcpkg 的社区（community）triplet，无需额外配置。`-G Xcode` 生成 Xcode 项目文件，后续通过 `cmake --build` 调用 `xcodebuild` 完成编译。

构建命令传入 ad-hoc 签名参数：

```bash
cmake --build build-ios --config Release -- \
  -sdk iphoneos \
  CODE_SIGN_IDENTITY="-" \
  CODE_SIGNING_ALLOWED=NO
```

### libvorbis 并行配置问题与 Overlay Port

iOS 构建中遇到的第一个问题来自 vcpkg 的 libvorbis port，也是适配过程中**调试成本最高的问题**。libvorbis 在 `arm64-ios` triplet 下使用 CMake 配置时，**并行配置会导致竞态失败**——多个 CMake 配置进程同时写入同一个构建目录中的中间文件，产生随机的配置错误。

这个问题的棘手之处在于它的随机性：不是每次都失败，CI 有时能过有时不能，且错误信息不固定。在没有 Mac 本地复现环境的情况下，需要反复触发 CI 构建、对比日志差异，才能最终定位到是并行配置的竞态。

这个问题在桌面平台上不容易触发（配置速度快，窗口期短），但在交叉编译到 iOS 时，CMake 需要额外的工具链探测步骤，配置时间更长，竞态窗口显著增大。

解决方案是在 `ios/ports/` 中创建一个 vcpkg [overlay port](https://learn.microsoft.com/en-us/vcpkg/concepts/overlay-ports)，基于上游 libvorbis port 的 `portfile.cmake` 添加 `DISABLE_PARALLEL_CONFIGURE` 选项：

```cmake
vcpkg_cmake_configure(
    SOURCE_PATH "${SOURCE_PATH}"
    DISABLE_PARALLEL_CONFIGURE
    OPTIONS
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5
)
```

同时，上游 port 中的四个 patch 文件里有两个是仅适用于 Windows 的（修复 MSVC 路径和 def 文件），在 iOS 交叉编译时反而会因为目标文件不存在而失败。因此该 overlay port 仅保留了跨平台通用的两个 patch（`0002-Fixup-pkgconfig-libs.patch` 和 `0004-ogg-find-dependency.patch`）。

CI 和本地构建脚本通过 `-DVCPKG_OVERLAY_PORTS=ios/ports` 指定 overlay，仅在 iOS 构建时生效，不影响其他平台。

### SDL-Mixer-X：macOS 专有框架在 iOS 上的编译错误

PvZ-Portable 使用 [SDL-Mixer-X](https://github.com/WohlSoft/SDL-Mixer-X)（SDL_mixer 的扩展 fork）作为音频库。它的 CMakeLists.txt 中有一个 `if(APPLE)` 条件块，链接了多个 Apple 框架：

```cmake
if(APPLE)
    find_library(APPLE_COCOA Cocoa)
    find_library(APPLE_CARBON Carbon)
    find_library(APPLE_FORCE_FEEDBACK ForceFeedback)
    # ...
endif()
```

问题在于 `APPLE` 宏在 macOS **和** iOS 上都为 `TRUE`。但 Cocoa、Carbon 和 ForceFeedback 是 **macOS 独有**的框架——iOS 上不存在这些框架，`find_library` 会失败（返回 `NOTFOUND`），后续链接时报错。

修复方式是将这三个 macOS 专有框架包裹在 `if(NOT IOS)` 条件中：

```cmake
if(APPLE)
    find_library(APPLE_CORE_AUDIO CoreAudio)
    find_library(APPLE_IOKIT IOKit)
    find_library(APPLE_AUDIOTOOLBOX AudioToolbox)
    # ... 其他 Apple 通用框架 ...
    if(NOT IOS)
        find_library(APPLE_COCOA Cocoa)
        find_library(APPLE_CARBON Carbon)
        find_library(APPLE_FORCE_FEEDBACK ForceFeedback)
    endif()
endif()
```

由于 SDL-Mixer-X 是以 fork 形式维护在项目仓库内的（而非 git submodule），直接修改其 CMakeLists.txt 是合理的做法。CoreAudio、IOKit、AudioToolbox 等框架在 macOS 和 iOS 上都可用，不需要额外的 `if(NOT IOS)` 守卫。

### 资源路径：Documents 目录 vs. Application Support

这是 iOS 适配中最关键的设计决策，也是与 Android 适配差异最大的部分。

Android 上游戏资源存储在 `Android/data/<package>/files/`，通过 `SDL_AndroidGetExternalStoragePath()` 获取——这是 SDL2 为 Android 提供的专用 API，直接返回 app-specific 外部存储路径。而 iOS 上 SDL2 没有提供等价的 API。如果使用 SDL2 通用的 `SDL_GetPrefPath()`，它返回的路径是 `Library/Application Support/io.github.wszqkzqk/PvZPortable/`——这个路径**对用户不可见**，用户无法通过 Files app 或 Finder 向其中放入文件。

iOS 上用户可见的目录是 **Documents**。当 Info.plist 中声明 `UIFileSharingEnabled = true` 时，Documents 目录会暴露在 Files app 和 Finder 文件共享中。因此，iOS 版需要将资源目录和存档目录都指向 Documents。

获取 Documents 目录路径的方式有两种：

1. **Objective-C API**：`NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES)` —— Apple 官方推荐的 iOS 路径解析方式
2. **纯 C++ 方式**：`std::getenv("HOME")` + `std::filesystem::path` 拼接 —— 利用 iOS sandbox 中 HOME 环境变量指向 app 沙箱根目录的事实

最终选择了**方案 2**（纯 C++）：

```cpp
#elif defined(__IPHONEOS__)
    {
        const char* aHome = std::getenv("HOME");
        if (aHome != nullptr && aHome[0] != '\0')
        {
            mResourceDir = (std::filesystem::path(aHome) / "Documents").generic_string() + "/";
        }
        else
        {
            mResourceDir = "";
        }
    }
```

选择纯 C++ 方案的理由：

- **零 Objective-C 依赖**：不需要引入 `.mm` 文件、不需要链接 Foundation 以外的框架（Foundation 已因 SDL2 链接）、不需要在 CMakeLists.txt 中配置 Objective-C 编译规则。
- **与项目约定一致**：项目中其他平台（Android、Switch、3DS）的路径获取都是内联在 `SexyAppBase.cpp` 中的简短代码块，没有独立的平台辅助文件。
- **HOME 环境变量在 iOS sandbox 中可靠**：Apple 文档虽然不显式保证 HOME 的存在，但 iOS 的 POSIX 兼容层确会设置此变量。且代码已对 HOME 为 `nullptr` 的极端情况做了防御（回退到空路径，后续会走资源缺失的错误提示路径）。

同样的逻辑也用于 `SexyAppBase::Init()` 中设置 `AppDataFolder`（存档数据目录），使资源和存档都统一指向 Documents。

### 启动时资源检测

Android 版有完整的 Java 资源导入界面（`ResourceImportActivity`），在 C++ 层面不需要做资源检测。而 iOS 版没有 UI 层，需要在 C++ 中直接检测：

```cpp
#ifdef __IPHONEOS__
    bool aHasGameResources = false;
    const char* aHome = std::getenv("HOME");
    if (aHome != nullptr && aHome[0] != '\0')
    {
        const std::filesystem::path aDocsPath =
            std::filesystem::path(aHome) / "Documents";
        aHasGameResources =
            std::filesystem::is_regular_file(aDocsPath / "main.pak") &&
            std::filesystem::is_directory(aDocsPath / "properties");
    }

    if (!aHasGameResources)
    {
        SDL_Init(SDL_INIT_VIDEO);
        SDL_ShowSimpleMessageBox(
            SDL_MESSAGEBOX_ERROR,
            "Resources Not Found",
            "Please place main.pak and the properties/ folder into the "
            "PvZ Portable folder using the Files app or "
            "Finder/iTunes file sharing.\n\n"
            "The app will now exit.",
            NULL
        );
        SDL_Quit();
        return 1;
    }
#endif
```

这段代码放置在 `main()` 函数中、游戏引擎初始化之前。如果资源不存在，通过 `SDL_ShowSimpleMessageBox` 弹出系统原生对话框提示用户操作步骤，然后干净地退出。不需要初始化完整的渲染管线。

### 移动平台全屏模式锁定

iOS（和 Android）上不存在"窗口模式"的概念——app 始终全屏运行。但 PvZ 的选项对话框中有一个 Full Screen 复选框，如果用户取消勾选，引擎会调用 `SDL_SetWindowFullscreen(window, 0)` 尝试退出全屏。在 iOS 上，这个调用会导致 EAGL 渲染上下文异常，表现为**黑屏**。

更微妙的是，即使用户不碰全屏复选框，只是打开选项菜单再关闭，也可能触发黑屏。这是因为关闭对话框的 `KillNewOptionsDialog()` 会无条件读取复选框状态并调用 `SwitchScreenMode`——如果 `mIsWindowed` 的值与复选框状态不一致（例如引擎默认 `mIsWindowed = true` 但实际全屏运行），就会触发不必要的模式切换。

修复分四层，各自解决不同层面的问题：

**第一层——初始状态正确**：在构造函数中将 `mIsWindowed` 设为 `false`：

```cpp
#if defined(__IPHONEOS__) || (defined(__ANDROID__) && !defined(__TERMUX__)) \
    || defined(__SWITCH__) || defined(__3DS__)
    mIsWindowed = false;
#else
    mIsWindowed = true;
#endif
```

这确保选项对话框中全屏复选框**初始就是勾选状态**（复选框通过 `!theApp->mIsWindowed` 决定是否勾选），与实际运行状态一致。

**第二层——配置读取守卫**：阻止配置和存档覆写 `mIsWindowed`：

引擎在初始化过程中会从配置文件和注册表/存档中读取窗口模式设置，这些读取可能将 `mIsWindowed` 从 `false` 改回 `true`，导致复选框显示为未勾选。在移动平台上跳过这些读取：

```cpp
// SexyApp.cpp — 跳过配置文件中的 DefaultWindowed 属性
#if !defined(__IPHONEOS__) && (!defined(__ANDROID__) || defined(__TERMUX__)) \
    && !defined(__SWITCH__) && !defined(__3DS__)
    mIsWindowed = GetBoolean("DefaultWindowed", mIsWindowed);
#endif

// SexyAppBase.cpp — 跳过注册表/存档中的 ScreenMode 读取
#if !defined(__IPHONEOS__) && (!defined(__ANDROID__) || defined(__TERMUX__)) \
    && !defined(__SWITCH__) && !defined(__3DS__)
    if (RegistryReadInteger("ScreenMode", &anInt))
        mIsWindowed = anInt == 0;
#endif
```

这确保 `mIsWindowed` 在移动平台上始终保持构造函数中设置的 `false`，不会被任何外部配置覆写。

**第三层——UI 锁定**：同样在构造函数中将 `mForceFullscreen` 设为 `true`：

```cpp
#if defined(__IPHONEOS__) || (defined(__ANDROID__) && !defined(__TERMUX__)) \
    || defined(__SWITCH__) || defined(__3DS__)
    mForceFullscreen = true;
#else
    mForceFullscreen = false;
#endif
```

这利用了引擎已有的 `mForceFullscreen` 机制——当它为 `true` 时，选项对话框中取消全屏复选框会弹出"不支持窗口模式"的提示并自动恢复为勾选状态。

**第四层——彻底阻断模式切换**：在 `SwitchScreenMode()` 入口处直接 early return：

```cpp
void SexyAppBase::SwitchScreenMode(bool wantWindowed, bool is3d, bool force)
{
#if defined(__IPHONEOS__) || (defined(__ANDROID__) && !defined(__TERMUX__)) \
    || defined(__SWITCH__) || defined(__3DS__)
    Set3DAcclerated(is3d);
    return;
#endif
    // ... 原有逻辑 ...
}
```

这是最后的安全网。`SwitchScreenMode` 是触发 `MakeWindow()` 和 `SDL_SetWindowFullscreen` 的唯一入口。在移动平台上直接跳过所有逻辑（仅保留 3D 加速设置），确保无论 `mIsWindowed` 的值如何、无论调用来源（用户操作、配置读取、存档恢复），都不会执行任何窗口模式变更。

这四层各有明确职责且互不冗余：第一层管初始 UI 显示正确性，第二层防止配置/存档覆写破坏第一层的状态，第三层管用户交互体验（提供友好的提示反馈），第四层管代码路径安全性（兜底所有可能的触发路径）。

### EAGL 上下文创建重试

此前在 Android 适配中，笔者已经解决了一个 EGL surface 短暂不可用导致 `SDL_GL_CreateContext` 返回 `NULL` 的概率性崩溃问题（详见 [Android 适配博客](https://wszqkzqk.github.io/2026/03/04/PvZ-Portable-Android-Adaptation/)）。iOS 上存在完全相同的问题——EAGL（Apple 的 EGL 等价物）surface 在 Activity 启动过程中也可能短暂不可用。

修复方案直接复用了 Android 的代码路径。将原有的 `#ifdef __ANDROID__` 扩展为同时覆盖 iOS：

```cpp
#if defined(__ANDROID__) || defined(__IPHONEOS__)
    // EGL/EAGL surface may be transiently unavailable on mobile
    for (int retry = 0; !mContext && mWindow && retry < 20; retry++)
    {
        SDL_Delay(100);
        SDL_PumpEvents();
        mContext = (void*)SDL_GL_CreateContext((SDL_Window*)mWindow);
    }
```

同时，iOS 编译时也正确跳过了"回退到桌面 GL 2.1"的代码路径——iOS 不支持桌面 OpenGL，只有 OpenGL ES。

### 横屏方向控制

PvZ 是横屏游戏。在 Android 上，横屏控制需要三层配合（Manifest 声明 + SDL hint + Java 层拦截 `SENSOR_LANDSCAPE` 替换为 `USER_LANDSCAPE`），详见 Android 适配博客。

iOS 上简单得多：

1. **Info.plist 声明**：`UISupportedInterfaceOrientations` 仅列出 `LandscapeLeft` 和 `LandscapeRight`，系统保证 app 只能在两个横屏方向之间切换。
2. **SDL hint**：窗口创建前设置 `SDL_SetHint(SDL_HINT_ORIENTATIONS, "LandscapeLeft LandscapeRight")`，这也覆盖了 iOS。

不需要像 Android 那样拦截 SDL 的 `setRequestedOrientation` 调用——iOS 的方向控制完全由 Info.plist 决定，SDL 不会在运行时覆盖它。

### Info.plist 配置

iOS 应用的行为主要由 `Info.plist` 控制。PvZ-Portable 使用 CMake 的模板机制（`MACOSX_BUNDLE_INFO_PLIST` 指向 `ios/Info.plist.in`），Xcode 在构建时自动替换 `$(EXECUTABLE_NAME)` 和 `$(PRODUCT_BUNDLE_IDENTIFIER)` 等变量。

关键配置项：

| 键 | 值 | 目的 |
| :--- | :--- | :--- |
| `UIFileSharingEnabled` | `true` | 在 Files app 和 Finder 中暴露 Documents 目录 |
| `LSSupportsOpeningDocumentsInPlace` | `true` | 允许其他 app 就地打开 Documents 中的文件 |
| `UIApplicationSupportsIndirectInputEvents` | `true` | 声明支持间接输入（Apple Pencil hover、触控板等） |
| `UIRequiresFullScreen` | `true` | 禁用 iPad 分屏，确保独占全屏 |
| `UIStatusBarHidden` | `true` | 隐藏状态栏 |
| `UIRequiredDeviceCapabilities` | `opengles-2`, `arm64` | 限制安装到支持 GLES2 的 64 位设备 |
| `CFBundleDocumentTypes` | ZIP Archive | 允许从"共享"菜单接收 ZIP 文件 |

### CMake iOS 配置

CMakeLists.txt 中 iOS 专属部分包括：

- **`add_executable(pvz-portable MACOSX_BUNDLE ${SOURCES})`**：生成 .app bundle 而非裸二进制
- **iOS 系统框架链接**：Foundation、UIKit、OpenGLES、QuartzCore、CoreGraphics、CoreMotion、GameController、AVFoundation、AudioToolbox、Metal
- **Bundle 属性**：GUI identifier、显示名称、Info.plist 模板路径、deployment target 15.0、支持 iPhone 和 iPad
- **LaunchScreen.storyboard**：启动屏幕（深绿色背景 + "PvZ Portable" 标题），通过 `MACOSX_PACKAGE_LOCATION Resources` 加入 bundle
- **Assets.xcassets**：App 图标 asset catalog，同样通过 `MACOSX_PACKAGE_LOCATION Resources` 加入 bundle

Asset catalog 需要通过 `set_source_files_properties` 设置 `MACOSX_PACKAGE_LOCATION Resources`，以确保 Xcode 的 `actool`（Asset Catalog Compiler）正确编译图标资源。如果仅通过 `target_sources` 添加而不设置此属性，CMake 的 Xcode generator 不会将 asset catalog 纳入资源构建阶段，导致 app icon 不显示。

### App 图标

iOS app 图标需要满足以下要求：

- **尺寸**：1024×1024 像素（现代 Xcode 14+ 使用单尺寸方案，系统自动缩放生成各种尺寸）
- **格式**：PNG，sRGB 色彩空间
- **无 alpha 通道**：Apple 明确要求 app icon **不能包含透明区域**。带 alpha 通道的 PNG 会导致图标在设备上显示为空白占位符

项目的 `icon.png` 是一个 512×512 的 RGBA 图片（带透明背景），需要两步处理：

```bash
magick icon.png -background white -alpha remove -alpha off \
    -resize 1024x1024 ios/Assets.xcassets/AppIcon.appiconset/AppIcon.png
```

1. `-background white -alpha remove -alpha off`：将透明区域填充为白色，然后去除 alpha 通道
2. `-resize 1024x1024`：从 512×512 放大到 1024×1024

生成的 PNG 必须是 `TrueColor`（RGB，3 通道）而非 `TrueColorAlpha`（RGBA，4 通道）。可通过 `file` 命令验证：

```
PNG image data, 1024 x 1024, 8-bit/color RGB, non-interlaced
```

### LaunchScreen.storyboard

iOS 要求所有 app 提供一个 LaunchScreen storyboard——系统在 app 启动时显示此界面，直到 app 准备好渲染第一帧。如果缺少 LaunchScreen storyboard，app 会以 iPhone 4 尺寸（320×480）的兼容模式运行。

PvZ-Portable 的启动屏幕是一个简单的深绿色背景（`rgb(0, 0.2, 0)`）加居中的 "PvZ Portable" 白色标题，横屏布局。使用 Interface Builder XML 格式（`.storyboard`），`targetRuntime` 设置为 `iOS.CocoaTouch`。

需要注意的是，`targetRuntime` 的值必须是 `iOS.CocoaTouch` 而非 `AppleSDK`——后者是较新版本 Xcode 创建 storyboard 时可能使用的值，但在 CI 环境中的 Xcode 版本可能不支持该值，导致 "Unknown target runtime" 编译错误。

### CI 配置

GitHub Actions 的 iOS 构建 job 运行在 `macos-latest` runner 上，使用 `lukka/run-vcpkg@v11` 管理 vcpkg。构建步骤与 `ios/build-ios.sh` 脚本一致：CMake configure + build + 打包 unsigned IPA。

IPA 打包方式与 `build-ios.sh` 相同：找到 `.app` bundle，创建 `Payload/` 目录结构，zip 压缩为 `.ipa`。IPA 作为 artifact 上传，在 release job 中与其他平台的构建产物一起发布。

## iOS vs. Android 适配对比

| 维度 | Android | iOS |
| :--- | :--- | :--- |
| **平台 UI 代码** | ~470 行 Java（ResourceImportActivity + PvZPortableActivity） | **0 行**（无 ObjC/Swift） |
| **C++ 修改量** | ~100 行（SDL hint、GL 重试、GLImage 防御、ReanimAtlas 重构） | ~60 行（路径、资源检测、全屏锁定） |
| **SDL2 链接方式** | 必须动态库（JNI 要求） | 静态库（vcpkg 默认） |
| **资源导入** | SAF + ZIP 解压 + 文件夹递归复制（app 内 UI） | 用户手动通过 Files/Finder 拷贝（无 app 内 UI） |
| **构建工具** | Gradle + NDK + CMake | CMake + Xcode Generator |
| **签名与安装** | debug keystore（自动），`adb install` 即可 | ad-hoc / sideload，**需要 Mac 或特殊工具** |
| **本地调试效率** | 高（编译→adb install→即时测试） | **极低**（无 Mac 则依赖 CI + 远程协助） |
| **全屏处理** | Edge-to-Edge + WindowInsetsController | 四层锁定：`mIsWindowed = false` + 配置读取守卫 + `mForceFullscreen` + `SwitchScreenMode` early return |
| **方向控制** | Manifest + SDL hint + Java 拦截 `SENSOR_LANDSCAPE` | Info.plist + SDL hint |

从代码量看，iOS 适配远比 Android "轻量"——零平台 UI 代码，C++ 改动量也更少。但从实际开发体验看，两者的难点截然不同：Android 的挑战在于编码——需要理解 Java/JNI 桥接、SAF 存储框架、Activity 生命周期，工具链本身是友好的；iOS 的挑战则在于编码之外——侧载安装门槛高、没有 Mac 时本地测试困难、vcpkg 交叉编译偶发构建失败。Android 的导入 UI 是在编写 Java Activity 时顺便实现的，成本很低；而 iOS 要实现类似功能则需要额外引入 ObjC/Swift，与整体零平台 UI 代码的设计不符。

## 技术挑战回顾

| 问题类别 | 具体问题 | 根本原因 | 解决方案 |
| :--- | :--- | :--- | :--- |
| **构建** | libvorbis 并行配置竞态失败 | iOS 交叉编译工具链探测耗时长，并行配置窗口增大 | Overlay port 添加 `DISABLE_PARALLEL_CONFIGURE` |
| **构建** | SDL-Mixer-X 链接 Cocoa/Carbon/ForceFeedback 失败 | `if(APPLE)` 不区分 macOS 和 iOS | 用 `if(NOT IOS)` 守卫 macOS 专有框架 |
| **构建** | LaunchScreen.storyboard "Unknown target runtime" | `targetRuntime="AppleSDK"` 在部分 Xcode 版本不支持 | 改为 `targetRuntime="iOS.CocoaTouch"` |
| **运行时** | 资源文件找不到（崩溃） | `SDL_GetPrefPath()` 返回 `Library/Application Support/`，用户不可见 | 改用 `getenv("HOME")/Documents` |
| **运行时** | Full Screen 选项导致黑屏 | `SDL_SetWindowFullscreen(window, 0)` 在 iOS 上破坏渲染上下文 | 四层锁定：`mIsWindowed = false` + 配置读取守卫 + `mForceFullscreen = true` + `SwitchScreenMode` early return |
| **资源** | App 图标显示为空白占位符 | PNG 带 alpha 通道，且 asset catalog 缺少 `MACOSX_PACKAGE_LOCATION` | 去除 alpha + 设置 `MACOSX_PACKAGE_LOCATION Resources` |

## 总结

iOS/iPadOS 适配是一次有趣的平台移植——代码改动量是所有平台中最小的，但开发过程中遇到的非编码层面的阻力却不少。

从技术角度看，iOS 的 SDL2 集成比 Android 优雅得多——不需要 Java 层代码，不需要处理 SDLActivity 的复杂生命周期，Info.plist 声明替代了大量运行时逻辑。整个适配用 18 个文件、不到 60 行 C++ 逻辑修改就完成了。

但在编码之外，iOS 生态带来了不同维度的挑战。没有 Mac 意味着无法本地测试，整个调试流程变成"CI 编译 → 远程协助测试 → 修复"的循环，反馈效率远低于 Android 的 `adb install`。libvorbis 的并行配置竞态问题由于只在 CI 上偶发出现，定位起来尤其费时。资源导入方面，Android 版在编写 Java Activity 时顺便实现了 ZIP 导入 UI，成本很低；而 iOS 版要做类似功能需要额外引入 ObjC/Swift，与整体设计不符，因此采用了更朴素的文件拷贝方案。

这或许反映了两个生态的不同特点：Android 的开放性让开发者能以低成本获取即时反馈，代价是需要编写更多平台适配代码；iOS 的 SDK 集成度高，平台适配代码少，但签名机制和 Mac 绑定在编码之外设置了额外的门槛。

👉 **项目地址**: [https://github.com/wszqkzqk/PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable)

## ⚠️ 版权与说明

**再次强调：本项目仅包含代码引擎，不包含任何游戏素材！**

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件，通过 Files app 或 Finder 文件共享导入：

*   `main.pak`
*   `properties/` 目录

本项目仅提供引擎代码，用于技术学习，**不包含**上述任何游戏资源文件，任何游戏资源均需要用户自行提供正版游戏文件。

本项目的源代码以 [**LGPL-3.0-or-later**](https://www.gnu.org/licenses/lgpl-3.0.html) 许可证开源，欢迎学习和贡献。
