---
layout:       post
title:        PvZ-Portable 渲染后端迁移：统一的 OpenGL ES 2.0
subtitle:     用最小公共子集实现最大兼容性和良好性能
date:         2026-02-16
author:       wszqkzqk
header-img:   img/games/bg-pvz-portable.webp
catalog:      true
tags:         C++ OpenGL 开源软件 游戏移植 开源游戏
---

## 引言

在之前的[文章](https://wszqkzqk.github.io/2026/01/26/PvZ-Portable/)中，笔者介绍了 [PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable) 项目——一个将《植物大战僵尸：年度版》带向所有平台的开源重实现。项目使用 SDL2 和 OpenGL 替代了原版的 DirectX 7 渲染，实现了跨平台支持。

然而，原有的 OpenGL 渲染后端存在一个架构问题：**PC 平台和 Switch 平台各自维护一套独立的渲染代码**，逻辑高度重复却又各有差异，维护成本较高且容易引入不一致的 bug。

本文将详细介绍笔者最近完成的一次渲染后端重构——将整个图形管线统一迁移到 **OpenGL ES 2.0**，并使用 **glad**（header-only）作为函数加载器，从而消除平台分裂、移除外部依赖，用最小公共子集实现最大兼容性。

## 迁移前的状况：两套渲染代码并存

在迁移之前，PvZ-Portable 的渲染代码按平台分裂成两份独立实现：

### PC 平台（Linux/Windows/macOS）

PC 平台使用一套渲染器：

- `platform/pc/graphics/GLInterface.cpp`（约 1757 行）：基于 OpenGL 固定管线（Fixed-Function Pipeline）的渲染器，使用 `glBegin`/`glEnd`、`glVertex`、`glColor` 等已废弃的 API。

该文件依赖 **GLEW**（OpenGL Extension Wrangler Library）来加载 OpenGL 函数指针，并且使用了桌面 OpenGL 的头文件（`<GL/gl.h>`、`<GL/glext.h>`）。在 macOS 上则是 `<OpenGL/gl.h>`，需要额外的条件编译。

此外还需要 **glm**（OpenGL Mathematics Library）来做矩阵运算。

> 注：仓库中存在 `GLInterfaceModern.cpp`（约 1859 行）文件，这是一套基于着色器的现代渲染器实现。然而，由于各种原因，该文件**从未被实际构建和使用**——PC 平台一直使用的是固定管线版本。这次迁移实际上达成了该文件原本的目标——移除固定管线，并以跨平台统一的方式实现，最终将这个未使用的文件一并移除。

### Switch 平台

Switch 平台有自己完全独立的一套：

- `platform/switch/graphics/GLInterface.cpp`（约 1844 行）：基于 OpenGL 4.3 Core Profile 的渲染器，使用 devkitPro 的 `glad` 全功能加载器和 `glm`。
- `platform/switch/graphics/GLInterface.h`（约 239 行）
- Switch 通过 EGL 创建上下文，绑定的是 `EGL_OPENGL_API`（桌面 OpenGL），请求 OpenGL 4.3 Core Profile。

### 问题总结

| 问题 | 具体表现 |
| :--- | :--- |
| **平台分裂** | PC 和 Switch 各约 1800 行渲染代码，逻辑几乎相同，却独立维护。PC 使用固定管线，Switch 使用现代着色器。 |
| **外部依赖多** | PC 需要 GLEW 和 glm；Switch 需要 glad（devkitPro 版）和 glm。GLEW 是一个需要单独安装的系统库。 |
| **API 层级不统一** | PC 使用固定管线（OpenGL 1.x 风格），Switch 使用 OpenGL 4.3 Core。两套代码使用完全不同的 GL API 子集。 |
| **头文件混乱** | PC 上 `<GL/gl.h>` 和 `<GL/glext.h>` 在不同平台路径不同，macOS 需要 `<OpenGL/gl.h>`，需要 `#ifdef __APPLE__` 特判。|
| **维护困难** | 修一个渲染 bug 需要同时改两个平台的文件，而且容易遗漏某个平台。 |

## 为什么选择 OpenGL ES 2.0

既然要统一，就要选一个所有目标平台都支持的 API 层级。笔者最终选择了 **OpenGL ES 2.0**，原因如下：

### 真正的最小公共子集

OpenGL ES 2.0 是几乎所有现代 GPU 都支持的最低标准：

- **桌面 GPU**：所有支持 OpenGL 2.1+ 的桌面驱动都内含 ES 2.0 的函数集。自 OpenGL 4.1 起，标准更是通过 `GL_ARB_ES2_compatibility` 扩展明确保证了对 ES 2.0 着色器的兼容（包括 `#version 100` 和 `precision` 限定符）。实际上，即便是不支持该扩展的 OpenGL 2.1 兼容模式驱动（如 macOS）也能正常编译 `#version 100` 着色器。
- **移动 GPU**：Android、iOS 设备的标配，在 ARM 开发板上支持非常完善。
- **游戏主机**：Nintendo Switch 的 GPU 原生支持 ES 2.0（它支持到 OpenGL 4.3，ES 2.0 自然包含在内）。
- **软件渲染**：即便 Mesa 的 llvmpipe（软件渲染器）也支持 ES 2.0。

对于 PvZ 这样一个十几年前的 2D 游戏，ES 2.0 的功能绰绰有余——我们只需要基本的纹理映射、Alpha 混合和一个简单的顶点/片段着色器。

### 可编程管线，但够简单

ES 2.0 移除了所有固定管线 IP（`glBegin`/`glEnd`、`glMatrixMode`、内置光照等），强制使用着色器。这意味着：

- 代码更简洁：不需要维护一套固定管线路径和一套着色器路径。
- 可移植性更好：所有平台走同一套着色器代码。
- 更容易理解：一个顶点着色器 + 一个片段着色器就完成了所有渲染。

### 消除 GLEW 依赖

GLEW 是 PC 平台上用来加载 OpenGL 函数指针的库。虽然各大包管理器都有它，但它：

- 是一个额外的编译时和运行时依赖。
- 在 macOS 上有时会出现兼容性问题（比如在 Core Profile 上下文中初始化失败）。
- 不支持 OpenGL ES，所以 Switch 已经在用别的加载器了。

统一到 ES 2.0 后，笔者使用 **glad**（header-only 模式）替代了 GLEW。glad 是一个在构建前预生成的单头文件，根据所需的 API 版本精确生成对应的函数指针声明和加载代码，无需安装任何系统库。

### 对接 ANGLE 的可能性

[ANGLE](https://chromium.googlesource.com/angle/angle)（Almost Native Graphics Layer Engine）是 Google 开发的 OpenGL ES 到其他图形 API（DirectX、Metal、Vulkan）的转译层，Chrome 浏览器用它在 Windows 上提供 WebGL 支持。如果未来某个平台的 OpenGL 驱动实在有问题，用户可以直接加载 ANGLE 的 `libGLESv2.so`/`libGLESv2.dll` 来将 ES 调用转译到 DirectX 或 Metal，而代码层面不需要任何修改。

## 迁移过程

### 第一步：统一 GLInterface

迁移的核心是将 PC 和 Switch 两份平台特异的渲染代码合并为一份共享实现。

笔者将 `platform/pc/graphics/GLInterface.cpp`（固定管线版）和 `platform/switch/graphics/GLInterface.cpp` 两个文件合并为一个：

```
src/SexyAppFramework/graphics/GLInterface.cpp   （约 1506 行）
```

这个统一的文件只使用 ES 2.0 的 API 子集，不依赖任何桌面 OpenGL 特有的函数。与合并前的约 3600 行相比，代码量减少了超过 58%，而且所有平台共享同一份渲染逻辑——一次修复，处处生效。

同样地，`GLInterface.h` 也从两个平台特异版本合并为一份共享头文件。

### 第二步：引入 glad（header-only）

过去 PC 用 GLEW 加载 GL 函数，Switch 用 devkitPro 提供的 glad 全功能版本（包含 OpenGL 4.3 Core 的所有函数和全部扩展）。

现在笔者使用 glad 的在线/命令行生成器，精确生成仅包含 **ES 2.0 核心**函数的 header-only 加载器：

```bash
glad --api 'gles2=2.0' --extensions '' c --header-only
```

关键参数：
- `--api 'gles2=2.0'`：只生成 ES 2.0 核心函数（约 142 个函数）。
- `--extensions ''`：不包含任何扩展。项目不使用任何 GL 扩展，去掉它们可以避免不必要的膨胀。
- `--header-only`：生成单个头文件，不需要额外的 `.c` 源文件。

生成的 `gles2.h` 只有约 1784 行。作为对比，如果包含所有 326 个 GLES2 扩展，文件会膨胀到近 7935 行——多出来的全是项目用不到的函数指针声明。

header-only 的使用方式很简单：在**恰好一个** `.cpp` 文件（`GLInterface.cpp`）的顶部 `#define GLAD_GLES2_IMPLEMENTATION`，然后 `#include <glad/gles2.h>` 即可。其他文件只需普通的 `#include`。

### 第三步：统一着色器语言版本

GLSL 也需要统一。ES 2.0 对应的着色器语言是 **GLSL ES 1.00**（`#version 100`），而桌面 OpenGL 2.1 对应 **GLSL 1.20**（`#version 120`）。

两者的语法几乎完全一致。主要差异在于：

| 特性 | GLSL ES 1.00 (`#version 100`) | GLSL 1.20 (`#version 120`) |
| :--- | :--- | :--- |
| `precision` 限定符 | 必须声明 | 不认识（但兼容模式通常接受） |
| `attribute`/`varying` | 使用 | 使用 |
| `gl_FragColor` | 使用 | 使用 |

笔者通过一组宏来抽象平台差异，在 `GLPlatform.h` 中定义：

```cpp
#define GLSL_VERT_MACROS \
    "#define VERT_IN attribute\n" \
    "#define V2F varying\n"

#define GLSL_FRAG_MACROS \
    "#define V2F varying\n" \
    "#define FRAG_OUT gl_FragColor\n" \
    "#define TEX2D texture2D\n"
```

着色器代码本身使用这些宏而非原始关键字，这样当未来需要从 ES 2.0 升级到 ES 3.0（将 `attribute`/`varying` 改为 `in`/`out`）时，只需修改宏定义即可。

实际的着色器非常简洁——毕竟这只是一个 2D 游戏：

```glsl
// 顶点着色器
uniform mat4 u_viewProj;
VERT_IN vec3 a_position;
VERT_IN vec4 a_color;
VERT_IN vec2 a_uv;
V2F vec4 v_color;
V2F vec2 v_uv;
void main() {
    v_color = a_color;
    v_uv = a_uv;
    gl_Position = u_viewProj * vec4(a_position, 1.0);
}

// 片段着色器
uniform sampler2D u_texture;
uniform int u_useTexture;
V2F vec4 v_color;
V2F vec2 v_uv;
void main() {
    if (u_useTexture == 1)
        FRAG_OUT = TEX2D(u_texture, v_uv) * v_color;
    else
        FRAG_OUT = v_color;
}
```

游戏的所有渲染就靠这一对着色器完成。

在运行时，shader 编译函数会根据当前上下文类型动态选择版本头：

```cpp
const char *versionLine = gDesktopGLFallback
    ? "#version 120\n"
    : "#version 100\nprecision mediump float;\n";
```

这里的 `gDesktopGLFallback` 标记在极少数无法创建 ES 上下文的平台（如某些 macOS 配置）上为 `true`，此时退为桌面 GL 2.1 的 `#version 120`。这两种着色器语言的核心语法完全一致，只是版本声明和精度限定符不同。

### 第四步：统一平台初始化

渲染初始化抽象为 `GLPlatform.h` 中的一个内联函数：

```cpp
#ifdef NINTENDO_SWITCH
#include <switch.h>
#include <EGL/egl.h>
#include <EGL/eglext.h>

inline void PlatformGLInit()
{
    gladLoadGLES2((GLADloadfunc)eglGetProcAddress);
}
#else
#include <SDL.h>

inline void PlatformGLInit()
{
    gladLoadGLES2((GLADloadfunc)SDL_GL_GetProcAddress);
}
#endif
```

整个平台抽象层就这么多——唯一的差异是函数指针的来源：Switch 从 EGL 获取，PC 从 SDL 获取。glad 拿到函数指针后加载所有 ES 2.0 核心函数，供渲染代码统一调用。

### 第五步：简化窗口创建

Switch 的 `Window.cpp` 将 EGL 上下文类型从 `EGL_OPENGL_API` + OpenGL 4.3 Core 改为 `EGL_OPENGL_ES_API` + ES 2.0：

```cpp
// 旧：请求桌面 OpenGL 4.3 Core
eglBindAPI(EGL_OPENGL_API);
static const EGLint contextAttributeList[] = {
    EGL_CONTEXT_OPENGL_PROFILE_MASK_KHR, EGL_CONTEXT_OPENGL_CORE_PROFILE_BIT_KHR,
    EGL_CONTEXT_MAJOR_VERSION_KHR, 4,
    EGL_CONTEXT_MINOR_VERSION_KHR, 3,
    EGL_NONE
};

// 新：请求 OpenGL ES 2.0
eglBindAPI(EGL_OPENGL_ES_API);
static const EGLint contextAttributeList[] = {
    EGL_CONTEXT_CLIENT_VERSION, 2,
    EGL_NONE
};
```

PC 的 `Window.cpp` 首先尝试创建 ES 2.0 上下文，如果失败（某些不支持 ES 的驱动或 macOS），则退回桌面 GL 2.1 兼容模式：

```cpp
// 第一选择: OpenGL ES 2.0
SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_ES);
SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 2);
SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 0);
// ... 创建窗口和上下文 ...

// 退路: 桌面 GL 2.1 兼容模式
if (!mContext)
{
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_COMPATIBILITY);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 2);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 1);
    // ... 重新创建 ...
    gDesktopGLFallback = true;
}
```

无论最终创建的是哪种上下文，glad 都可以从中加载到我们需要的那百余个 ES 2.0 函数——因为桌面 GL 的函数集严格包含 ES 2.0 的函数集。

### 第六步：扁平化目录结构

合并后，每个平台的 `graphics/` 子目录通常只剩一个 `Window.cpp`。笔者将它们提升到上一级目录：

```
# 迁移前
platform/pc/graphics/GLInterface.cpp       (1757 行)
platform/pc/graphics/GLInterfaceModern.cpp  (1859 行)
platform/pc/graphics/GLInterface.h          (243 行)
platform/pc/graphics/Window.cpp
platform/pc/Input.cpp
platform/switch/graphics/GLInterface.cpp    (1844 行)
platform/switch/graphics/GLInterface.h      (239 行)
platform/switch/graphics/GLPlatform.h
platform/switch/graphics/Window.cpp
platform/switch/Input.cpp

# 迁移后
graphics/GLInterface.cpp   (1506 行, 共享)
graphics/GLInterface.h     (229 行, 共享)
graphics/GLPlatform.h      (51 行, 共享)
glad/gles2.h               (1784 行, 生成，无维护负担)
platform/pc/Window.cpp
platform/pc/Input.cpp
platform/switch/Window.cpp
platform/switch/Input.cpp
```

3DS 平台由于使用了完全不同的图形 API（PICA200，非 OpenGL），其 `graphics/` 目录保持不动。这是硬件层面的根本限制——3DS 的 GPU 不支持任何形式的 OpenGL，只能通过其专有的 PICA200 API 进行渲染，因此无法纳入这次统一。统一渲染后端的前提是目标平台至少支持某个共同的图形 API 子集，而 3DS 不具备这个条件。

### 第七步：修复 Color::ToInt() 引入的颜色 bug

迁移过程中暴露了一个潜伏的颜色处理 bug。在之前的一次字节序清理中，`Color::ToInt()` 被错误地修改为返回 ABGR 格式（`0xAABBGGRR`），而游戏内部的 `TriVertex.color` 等数据结构始终期望标准的 ARGB 格式（`0xAARRGGBB`）。

在旧的分立代码中，这个问题被一些特定的平台代码路径掩盖了。但统一渲染器后，问题立即浮现——最明显的症状是冰冻的巨人僵尸（Gargantuar）从蓝色变成了红色，因为 R 和 B 通道被交换了两次。

修复方案分两步：

1. **恢复 `Color::ToInt()`** 为标准 ARGB 格式：

```cpp
// 修复后：标准 ARGB (0xAARRGGBB)
uint32_t Color::ToInt() const
{
    return (static_cast<uint32_t>(mAlpha) << 24) |
           (static_cast<uint32_t>(mRed) << 16) |
           (static_cast<uint32_t>(mGreen) << 8) |
           static_cast<uint32_t>(mBlue);
}
```

2. **在 GL 顶点颜色赋值处统一转换**：OpenGL 期望顶点颜色以 `GL_UNSIGNED_BYTE` 的 RGBA 字节序传入。笔者在 `GLInterface.cpp` 中定义了转换函数，所有需要把 `Color::ToInt()` 的返回值之处使用 `ArgbToRgba()` 进行恰当的转换：

```cpp
static inline uint32_t ArgbToRgba(uint32_t argb) noexcept
{
    // ARGB → ABGR (swap R↔B), then force little-endian for GL byte order
    uint32_t abgr = (argb & 0xFF00FF00u)
                  | ((argb >> 16) & 0x000000FFu)
                  | ((argb << 16) & 0x00FF0000u);
    return ToLE32(abgr);
}
```

这里的 `ToLE32()` 确保在大端架构上也能得到正确的字节序——OpenGL 按字节读取顶点颜色时，期望的内存布局是 `[R, G, B, A]`，而在小端机器上 `0xAABBGGRR` 的内存布局恰好就是 `[RR, GG, BB, AA]`。

### 第八步：移除外部依赖

迁移完成后，从构建系统中移除了以下依赖：

- **GLEW**：从 `CMakeLists.txt`（`find_package(GLEW)`）、vcpkg.json、CI 脚本、各平台的包管理器依赖列表中全部移除。
- **glm**：不再需要。矩阵运算直接在 shader 中用 `mat4` 完成，投影矩阵在 C++ 侧手动构造（正交投影矩阵非常简单，完全不需要一个数学库）。
- **OpenGL 系统库**：不再需要 `find_package(OpenGL)` 或链接 `OpenGL::GL`。glad 通过 `GetProcAddress` 在运行时加载所有函数，不需要编译时链接 GL 库。
- **Switch 上的 glad（devkitPro 版）**：替换为项目内置的精简 glad header-only 版本，不再链接 `glad` 库。

## 迁移成效

### 代码量对比

| 项目 | 迁移前 | 迁移后 | 变化 |
| :--- | :--- | :--- | :--- |
| PC GLInterface.cpp | 1757 行 | — | 删除 |
| PC GLInterfaceModern.cpp | 1859 行 | — | 删除 |
| PC GLInterface.h | 243 行 | — | 删除 |
| Switch GLInterface.cpp | 1844 行 | — | 删除 |
| Switch GLInterface.h | 239 行 | — | 删除 |
| 共享 GLInterface.cpp | — | 1506 行 | 新增 |
| 共享 GLInterface.h | — | 229 行 | 新增 |
| 共享 GLPlatform.h | — | 51 行 | 新增 |
| glad/gles2.h | — | 1784 行 | 新增（生成） |
| **渲染代码净变化** | **5942 行** | **1786 行** | **-70%** |

> 注：PC 平台的 `GLInterfaceModern.cpp`（1859 行）虽然从未被构建使用，但它代表了一个"将 PC 渲染从固定管线迁移到着色器"的尝试。这次迁移以跨平台统一的方式实现了这个目标——新代码既是着色器驱动的，又在 PC 和 Switch 之间共享，避免了平台分裂。因此，该文件的目标达成了，文件本身也随之移除。

整个 PR 的总体统计：**+3412 行 / -5778 行**（净减少约 2366 行），其中新增内容中还有 1784 行是自动生成的 glad 头文件，不增加维护负担。

### 外部依赖对比

| 依赖 | 迁移前 | 迁移后 |
| :--- | :--- | :--- |
| GLEW | 需要（系统库） | 不需要 |
| glm | 需要（系统库） | 不需要 |
| OpenGL 系统库 | 需要链接 | 不需要链接 |
| glad | Switch 链接 devkitPro 版 | 内置 header-only，全平台共享 |

### 兼容性

| 维度 | 支持情况 |
| :--- | :--- |
| **操作系统** | Linux、Windows、macOS、Haiku、Nintendo Switch |
| **CPU 架构** | x86、ARM、RISC-V、LoongArch 等 |
| **字节序** | 小端、大端均支持（`ToLE32`/`FromLE32` 保证 GL 数据正确） |
| **GL 上下文** | 原生 ES 2.0 优先，桌面 GL 2.1 兼容模式自动回退 |
| **软件渲染** | Mesa llvmpipe 等支持 ES 2.0 的软件渲染器可用 |
| **ANGLE** | 如有需要可直接通过 ANGLE 转译到 DirectX/Metal/Vulkan |

## 技术细节补充

### glad 的 header-only 模式原理

glad 生成的 header-only 文件本质上是将所有函数指针的声明和加载逻辑放在一个头文件中。通过条件编译，确保：

- **声明**：所有包含 `gles2.h` 的编译单元都能看到函数指针的 `extern` 声明。
- **定义**：只有定义了 `GLAD_GLES2_IMPLEMENTATION` 的那一个编译单元会生成函数指针的实际存储和加载函数的实现。

这种方式在 stb 系列库中非常常见，优势是不需要往构建系统中添加额外的源文件。

### 关于精简扩展

笔者最初使用 glad 生成时，默认包含了全部 326 个 GLES2 扩展，生成了约 7935 行的头文件。后来检查发现项目代码中没有使用任何扩展函数（`GLAD_GL_*` 零引用），于是用 `--extensions ''` 重新生成，文件从 7935 行缩减到 1784 行，减少了约 78%。

扩展声明虽然不影响运行时性能（它们只是函数指针定义），但 `gladLoadGLES2()` 初始化时会逐个查询每个扩展是否可用。去掉不需要的扩展可以略微加快初始化速度，更重要的是减少了编译时间。

### Framebuffer 完整性检查

在迁移过程中，笔者还发现 `RecoverBits()`（用于从 GPU 纹理读回像素数据到内存）缺少 framebuffer 完整性检查。如果纹理格式不被当前驱动支持为 framebuffer 附件，`glReadPixels` 会产生未定义行为。笔者补充了检查：

```cpp
if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE)
{
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    glDeleteFramebuffers(1, &fbo);
    return false;
}
```

这在 ES 2.0 上尤为重要，因为 ES 2.0 对 framebuffer 可附加的纹理格式有更严格的限制。

### 为什么不直接去掉桌面 GL 回退

读者可能会问：既然用了 glad 加载 ES 2.0 函数，是否可以完全不要桌面 GL 回退？

理论上可以——glad 的 `gladLoadGLES2((GLADloadfunc)SDL_GL_GetProcAddress)` 可以从任何类型的 GL 上下文中加载 ES 2.0 的函数指针，因为这些函数在桌面 GL 中名称完全相同。然而保留回退有实际意义：

- **macOS**：macOS 的 SDL2 不支持创建 ES 上下文（Apple 的 OpenGL 实现只提供桌面 GL，最高 4.1）。即使 Shader 内容是 ES 2.0 级别的，也需要一个桌面 GL 上下文来承载它们，此时着色器版本头需要改为 `#version 120`。
- **部分 Windows 驱动**：可能存在部分 Windows 驱动不支持通过 SDL 创建 ES 上下文。（虽然极难遇到）

保留回退的成本很低——只是 `Window.cpp` 中多几行上下文创建逻辑和 `GLInterface.cpp` 中一个三元表达式的差异。

## 总结

这次迁移的核心思路可以概括为一句话：**用最小公共子集实现最大兼容性**。OpenGL ES 2.0 现代渲染引擎的最小公共子集——作为 WebGL 等技术的基础，它足够强大以满足游戏的渲染需求，又足够基础以被所有目标平台支持。

这次重构：

- 消除了三套渲染代码的平台分裂，统一为一份约 1500 行的共享实现。
- 移除了 GLEW、glm 等外部依赖，降低了构建和部署门槛。
- 修复了潜伏的颜色处理 bug。
- 解决了 XWayland 下黑边区域可能出现的闪烁问题（旧版固定管线代码在某些 Wayland 合成器上通过 XWayland 运行时表现不稳定）。
- 支持通过 ANGLE 对接 DirectX/Metal/Vulkan），在 OpenGL 驱动不佳的平台上提供额外的兼容性保障。
- 使渲染 bug 修复只需改一处，所有平台同时受益。

## ⚠️ 版权与说明

**重要：本项目仅包含代码引擎，不包含任何游戏素材！**

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中：

*   `main.pak`
*   `properties/` 目录

本项目仅提供引擎代码，用于技术学习，**不包含**上述任何游戏资源文件，任何游戏资源均需要用户自行提供正版游戏文件。

本项目的源代码以 [**LGPL-3.0-or-later**](https://www.gnu.org/licenses/lgpl-3.0.html) 许可证开源，欢迎学习和贡献。
