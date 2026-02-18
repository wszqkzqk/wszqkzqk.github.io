---
layout:       post
title:        PvZ-Portable 渲染后端迁移：统一的 OpenGL ES 2.0
subtitle:     用最小公共子集实现最大兼容性和良好性能
date:         2026-02-16
author:       wszqkzqk
header-img:   img/games/bg-pvz-portable.webp
catalog:      true
tags:         C++ OpenGL 开源软件 游戏移植 开源游戏 PvZ-Portable
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
uniform vec4 u_uvBounds;
V2F vec4 v_color;
V2F vec2 v_uv;
void main() {
    if (u_useTexture == 1)
        FRAG_OUT = TEX2D(u_texture, clamp(v_uv, u_uvBounds.xy, u_uvBounds.zw)) * v_color;
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

在旧的分立代码中，这个问题被一些特定的平台代码路径掩盖了。但统一渲染器后，问题立即浮现——最明显的症状是冰冻的僵尸部分渲染块从蓝色变成了红色，因为 R 和 B 通道被交换了两次。

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

### 第九步：修复纹理过滤状态管理

统一渲染后端后，笔者注意到部分缩放或旋转渲染的图像存在**锯齿状阶梯纹**——例如舞王僵尸脚下的聚光灯光圈、水族馆和禅境花园的背景图等。这些图像在游戏中需要经过缩放或旋转绘制，理应使用双线性过滤（`GL_LINEAR`）来获得平滑的采样效果，但实际渲染却表现为最近邻采样（`GL_NEAREST`）的粗糙像素边缘。

#### 根本原因：过滤参数被设置到了错误的纹理上

调查后发现，问题的根源在于 **OpenGL 的纹理过滤状态是绑定在纹理对象（texture object）上的，而非全局状态**。

旧代码中，`SetLinearFilter()` 在每次绘制前通过 `glTexParameteri` 设置过滤模式：

```cpp
void GLInterface::SetLinearFilter(bool linearFilter)
{
    GLenum filter = linearFilter ? GL_LINEAR : GL_NEAREST;
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, filter);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, filter);
}
```

然而，`glTexParameteri` 作用的对象是**当前绑定的纹理**——即上一次 `glBindTexture` 所绑定的那个。在实际绘制路径中，调用顺序是：

1. `SetLinearFilter(true)` → 将过滤参数设到**上一次绘制残留的旧纹理**
2. `glBindTexture(GL_TEXTURE_2D, newTexture)` → 绑定**本次实际要绘制的纹理**
3. `glDrawArrays(...)` → 绘制，使用的是 `newTexture` 自身已有的过滤参数

也就是说，`SetLinearFilter` 的调用效果总是作用在**错误的纹理**上，实际要绘制的纹理从未收到过滤参数的更新。

#### 修复方案：引入 GfxBindTexture

修复思路很直接：**将纹理绑定和过滤参数设置合并为一个原子操作**。笔者引入了 `GfxBindTexture()` 函数（它同时承担了后文第十一步中 UV bounds 上传的职责——这里展示的是最终版本）：

```cpp
static bool gLinearFilter = true;

void GLInterface::SetLinearFilter(bool linearFilter)
{
    gLinearFilter = linearFilter;
}

static constexpr float kDefaultUvBounds[4] = { 0.f, 0.f, 1.f, 1.f };

static void GfxBindTexture(GLuint tex, const float *uvBounds = kDefaultUvBounds)
{
    glBindTexture(GL_TEXTURE_2D, tex);
    int f = gLinearFilter ? GL_LINEAR : GL_NEAREST;
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, f);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, f);
    glUniform4fv(gUfUvBounds, 1, uvBounds);
}
```

`SetLinearFilter()` 不再直接调用 GL API，只是设置一个标志位。真正的 `glTexParameteri` 调用被移到 `GfxBindTexture()` 中——在 `glBindTexture()` **之后**立即执行，确保过滤参数一定作用在正确的纹理对象上。所有原先直接调用 `glBindTexture` 的地方都替换为 `GfxBindTexture`。函数同时通过 `glUniform4fv` 上传 UV bounds uniform（详见第十一步），默认参数 `kDefaultUvBounds = {0, 0, 1, 1}` 表示不限制 UV 范围——不需要钳位的调用点无需任何代码变更。

#### 默认使用双线性过滤

既然过滤功能修复了，笔者将默认过滤模式从 `GL_NEAREST` 改为 `GL_LINEAR`：

- `Graphics` 构造函数中的 `mLinearBlend` 默认值：`false` → `true`
- `Blt()` / `BltMirror()` 的 `linearFilter` 默认参数：`false` → `true`

这一改动不仅仅是"顺便"——它直接解决了从 DirectX 7 迁移以来一直存在的**纹理缩放品质退化**问题。原版游戏的 DirectX 7 渲染器对缩放和旋转的纹理默认使用双线性过滤，而 OpenGL 移植版之前一直使用 `GL_NEAREST`（最近邻采样），导致多处视觉效果明显劣于原版：

- **舞王僵尸的聚光灯光圈**：原版中聚光灯是一个平滑的圆形渐变光幕，而 `GL_NEAREST` 下呈现明显的像素方块和网格状锯齿，严重破坏了舞台效果。
- **水族馆关卡的背景图**：背景纹理被缩放绘制以填满屏幕，`GL_NEAREST` 下呈现粗糙的像素化背景，而原版中是平滑过渡的。
- **禅境花园的背景图**：同样因为纹理缩放，`GL_NEAREST` 下呈现出马赛克状。

切换为 `GL_LINEAR` 后，这些场景的渲染效果恢复到了与原版游戏一致的品质。

这一改动的安全性在于：**当纹理以 1:1 像素对齐方式绘制时，`GL_LINEAR` 和 `GL_NEAREST` 的采样结果完全一致**——因为采样点恰好落在纹素中心，双线性插值的四个权重退化为 $(1, 0, 0, 0)$。只有在纹理被缩放或旋转时，`GL_LINEAR` 才会产生平滑的插值效果，而这正是我们所期望的行为。在现代 GPU 上，双线性过滤是硬件原生支持的操作，与最近邻采样相比没有可测量的性能差异。

然而，切换到 `GL_LINEAR` 也引入了一个新的回归问题——字体渲染出现异常。这一问题及其修复将在下文"第十一步"中详细讨论。

#### 清理死代码

修复后，`PreDraw()` 中原本在每次绘制前重置 `gLinearFilter = false` 的代码变成了无效逻辑——因为每条绘制路径都会通过 `SetLinearFilter()` 重新设置这个标志。笔者移除了这三行死代码，使 `PreDraw()` 只保留混合模式的重置。同理，`CopyImageToTexture()` 中在纹理上传时设置过滤参数的代码也是冗余的——后续 `GfxBindTexture()` 绑定该纹理时会重新设置过滤参数——一并移除。

### 第十步：禁用 sRGB 帧缓冲

迁移完成后，笔者在 Windows 上测试时发现画面整体**偏亮**，颜色像被漂白了一样。经调查，这是一个由上下文类型变更引发的 **sRGB gamma 双重校正**问题。

#### 根本原因：ES 上下文改变了帧缓冲的 sRGB 属性

迁移前，PC 平台请求的是**桌面 OpenGL 兼容性上下文**（`SDL_GL_CONTEXT_PROFILE_COMPATIBILITY`）。在这种上下文下，Windows 驱动通常选择**不带 sRGB 标记**的像素格式，`GL_FRAMEBUFFER_SRGB` 默认禁用——这符合 OpenGL 规范的默认行为。

迁移后，PC 平台改为优先请求 **OpenGL ES 2.0 上下文**（`SDL_GL_CONTEXT_PROFILE_ES`）。在 Windows 上，SDL 创建 ES 上下文通常走以下两条路径之一：

1. **驱动原生 ES 模拟**：NVIDIA/AMD 的桌面驱动提供 ES 兼容性时，WGL 的像素格式选择路径与桌面 GL 不同，可能倾向选择带 `WGL_FRAMEBUFFER_SRGB_CAPABLE_ARB` 标记的像素格式。
2. **ANGLE 后端**：ANGLE 将 GLES 调用翻译为 Direct3D。其 D3D11 后端默认使用 `DXGI_FORMAT_R8G8B8A8_UNORM_SRGB` 格式创建交换链（swap chain），使默认帧缓冲天然具有 sRGB 属性。

无论哪种情况，结果都是默认帧缓冲变成了 **sRGB-capable**。此时某些驱动会自动启用 `GL_FRAMEBUFFER_SRGB`，使 GPU 在写入帧缓冲时执行**线性 → sRGB** 的 gamma 转换（约 $\gamma = 1/2.2$）。

然而，PvZ-Portable 的整个渲染管线都在 **sRGB 空间**中直接工作——纹理采样后不做线性化，fragment shader 直接输出 sRGB 值。如果帧缓冲端又额外做一次 sRGB 编码，相当于 **gamma 校正被重复应用**，导致画面发白。

#### 修复方案

修复非常直接——在 GL 初始化时无条件禁用 `GL_FRAMEBUFFER_SRGB`：

```cpp
// Windows GL implementations may auto-enable sRGB on the default framebuffer.
glDisable(GL_FRAMEBUFFER_SRGB);
glGetError(); // clear error if unsupported
```

由于 `GL_FRAMEBUFFER_SRGB`（`0x8DB9`）是桌面 OpenGL 3.0+（`GL_ARB_framebuffer_sRGB`）的枚举，GLES 2.0 头文件中没有定义，因此还需要一个兼容性宏：

```cpp
#ifndef GL_FRAMEBUFFER_SRGB
#define GL_FRAMEBUFFER_SRGB 0x8DB9
#endif
```

#### 跨平台安全性

这个修复对所有平台都是安全的：

| 平台 | 行为 |
| :--- | :--- |
| **Windows（ES 上下文或桌面 GL 回退）** | 关键修复。驱动可能自动启用 sRGB，`glDisable` 将其关闭。 |
| **Linux / Mesa** | 桌面 GL 兼容模式通常不自动启用 sRGB，`glDisable` 无害。 |
| **macOS** | 同 Linux，默认不启用。 |
| **原生 GLES 2.0 设备** | 此枚举不被识别，`glDisable` 产生 `GL_INVALID_ENUM`，紧随的 `glGetError()` 将其清除，不影响后续逻辑。 |

`glGetError()` 的调用是关键的安全网——它确保即使在不支持此枚举的 GLES 实现上，错误标志也不会残留，不会干扰后续的 GL 错误检查逻辑。

### 第十一步：修复纹理渗透——基于 Uniform 的 UV 钳位

切换到 `GL_LINEAR` 后，大部分渲染效果有了显著提升，但同时也引入了一个**纹理渗透**问题。最明显的症状是位图字体文字下方出现了一条不应存在的细横线，此外部分被拆分到多个纹理 piece 中的图片在 piece 边界处也会出现可见的接缝。

#### 根本原因：双线性采样越界

PvZ 的渲染引擎会将大图拆分成固定大小的纹理 piece（以适应 GPU 的最大纹理尺寸限制）。字体系统也类似——所有字形紧密排列在一张图集纹理中，中间没有间隙。

当使用 `GL_NEAREST` 时，每个像素只采样最近的一个纹素，不会越界。但 `GL_LINEAR` 在纹素边界处会采样相邻的 $2 \times 2$ 个纹素并加权插值。如果采样点落在纹理 piece 或字形的边缘，插值器会看到相邻 piece 或字形的像素，以很小的权重混入当前渲染结果——这就是渗色的来源。

#### 修复方案：片段着色器中的 UV 钳位

修复思路是在片段着色器中，将 UV 坐标 clamp 到当前纹理 piece 的有效范围内，使采样器永远不会越界。

具体来说，对每个纹理 piece 计算一个**半纹素内缩边界**：如果 piece 的宽度是 $W$ 纹素，那么有效 UV 范围从 $[u_1, u_2]$ 收缩为 $[u_1 + 0.5/W, \; u_2 - 0.5/W]$。这样，即使 `GL_LINEAR` 在边界处向外扩展半个纹素的采样范围，也不会触及相邻 piece 的数据。

关键的设计决策是**如何将这个边界传递给着色器**。有两种选择：

| 方式 | 实现 | 开销 |
| :--- | :--- | :--- |
| **per-vertex attribute** | 在 `GLVertex` 中添加 `float uvBounds[4]`，作为顶点属性传入 | 顶点结构 +16 字节（+67%），需要额外的 varying 插值 |
| **uniform** | 通过 `glUniform4fv` 在每次 draw call 前设置 | 每次 draw call 一次 GL 调用，顶点结构不变 |

笔者选择了 **uniform** 方案。原因很简单：在同一个 draw call 中，所有顶点都来自同一个纹理 piece，它们的 uvBounds **完全相同**——把相同的值塞进每个顶点是纯粹的带宽浪费。uniform 天然就是为每次 draw call 一个值设计的。

修改后的片段着色器：

```glsl
uniform sampler2D u_texture;
uniform int u_useTexture;
uniform vec4 u_uvBounds;   // {uMin, vMin, uMax, vMax}
void main() {
    if (u_useTexture == 1)
        FRAG_OUT = TEX2D(u_texture, clamp(v_uv, u_uvBounds.xy, u_uvBounds.zw)) * v_color;
    else
        FRAG_OUT = v_color;
}
```

顶点着色器和 `GLVertex` 结构**完全不变**——不需要额外的顶点属性，不需要额外的 varying。

> **性能**：`clamp` 在 GPU 上编译为 1-2 条 ALU 指令（`MAX` + `MIN`），与加法/乘法同级，单周期完成。相比于同一行 `texture2D()` 涉及的纹理单元寻址、缓存查找和硬件双线性插值，一条 clamp 的开销完全可以忽略。对于 PvZ 这种纹理带宽受限的 2D 游戏，ALU 侧有大量空闲周期，clamp 不构成任何瓶颈。

#### C++ 侧的边界计算

在 `GetTexture()` / `GetTextureF()` 中计算半纹素内缩边界，通过输出参数 `uvBounds` 返回给调用者：

```cpp
float halfU = 0.5f / p.mWidth, halfV = 0.5f / p.mHeight;
float midU  = (u1 + u2) * 0.5f, midV = (v1 + v2) * 0.5f;
uvBounds[0] = std::min(u1 + halfU, midU);
uvBounds[1] = std::min(v1 + halfV, midV);
uvBounds[2] = std::max(u2 - halfU, midU);
uvBounds[3] = std::max(v2 - halfV, midV);
```

`midU`/`midV` 的回退确保在极端情况下（piece 只有 1 纹素宽时 $u_1 + 0.5/W > u_2 - 0.5/W$）边界不会反转。

#### 原子化绑定：将 UV bounds 合并进 GfxBindTexture

最初的实现使用了一个全局数组 `gUvBounds[4]` 和辅助函数 `GfxSetUvBounds()` 来传递边界，在 `GfxEnd()` 的 `glDrawArrays()` 之前上传 uniform 并在之后重置。然而这种设计存在三个问题：

1. **可遗忘的全局可变状态**：`BltTriangles()` 等路径如果忘记调用 `GfxSetUvBounds()`，就会**继承上一次绘制残留的边界**，导致纹理渲染错乱（实际测试中确实因此出现过 Zomboss 机甲的贴图错误）。
2. **冗余重置**：需要在 `GfxEnd()` 和 `PreDraw()` 中都做安全重置，增加维护负担。
3. **非纹理绘制的无用开销**：`FillRect` 等不使用纹理的路径也会在 `GfxEnd()` 中触发 `glUniform4fv`。

重构后的方案是将 UV bounds 上传**合并进 `GfxBindTexture()` 的调用签名中**，即第九步中展示的最终版本：

```cpp
static void GfxBindTexture(GLuint tex, const float *uvBounds = kDefaultUvBounds)
{
    glBindTexture(GL_TEXTURE_2D, tex);
    int f = gLinearFilter ? GL_LINEAR : GL_NEAREST;
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, f);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, f);
    glUniform4fv(gUfUvBounds, 1, uvBounds);
}
```

这一设计的关键优势：

- **不可能遗漏**：纹理绑定和 UV bounds 上传是同一次函数调用的原子操作——只要绑定了纹理，边界就一定被正确设置。
- **零性能退化**：默认参数 `kDefaultUvBounds = {0, 0, 1, 1}` 使得不需要钳位的路径无需任何代码变更。
- **非纹理绘制零开销**：`FillRect` 等路径不调用 `GfxBindTexture()`，完全不触发 `glUniform4fv`。`GfxEnd()` 中也不再有任何 uniform 上传或重置逻辑——它只负责提交顶点数据并调用 `glDrawArrays()`。

绘制流程变为：

1. `GetTexture()` 返回纹理 ID、UV 坐标和 `uvBounds`
2. `GfxBindTexture(tex, uvb)` **一次性完成**纹理绑定、过滤参数设置和 UV bounds 上传
3. `GfxBegin()` → `GfxAddVertices()` → `GfxEnd()` 提交并绘制

对于 `BltTriangles()`（Reanimation 系统的三角形批量渲染），也需要计算 UV bounds——单纹理快速路径根据 piece 尺寸和实际 UV 范围计算半纹素 inset，多纹理路径在内层循环中为每个 piece 分别计算。所有路径都通过 `GfxBindTexture(piece.mTexture, uvb)` 原子化传递。

#### 附带修复：缩放字体路径的键值错误

在排查字体渲染问题的过程中，笔者还发现并修复了 `ImageFont.cpp` 中一个长期潜伏的 bug。在缩放字体路径中，`mScaledCharImageRects` 的存储键使用了自增计数器 `aCharNum`（值为 1, 2, 3, ...），但渲染时查找使用的键是实际的字符值（如 `'A'` = 0x41）。键完全不匹配——缩放后的字形位置查找会全部失败，使得缩放字体实际上从未正确工作过。由于游戏中绝大多数字体在 `mScale == 1.0` 时使用无缩放路径，不受此 bug 影响，因此这个问题一直没有被注意到。修复后统一使用实际字符值作为键，彻底消除了这个隐患。

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
- 修复了纹理过滤状态管理的 bug，消除了缩放/旋转图像的锯齿伪影，并将默认过滤模式切换为更合理的双线性过滤。
- 修复了 Windows 上因 ES 上下文导致 sRGB 帧缓冲自动启用引起的画面发白问题。
- 解决了 XWayland 下黑边区域可能出现的闪烁问题（旧版固定管线代码在某些 Wayland 合成器上通过 XWayland 运行时表现不稳定）。
- 支持通过 ANGLE 对接 DirectX/Metal/Vulkan，在 OpenGL 驱动不佳的平台上提供额外的兼容性保障。
  - 在 macOS 上，如果存在 ANGLE，程序会**默认使用 ANGLE** 的 Metal 后端。
  - 在 Windows 上，程序会**默认使用原生 OpenGL ES 上下文**，如果要使用 ANGLE 映射到 DirectX 11，需要设置环境变量 `ANGLE_PLATFORM=windows`，不过一般**仍然建议使用原生驱动**。
  - 在 Linux 等其他操作系统，**不建议使用 ANGLE**，因为原生 OpenGL 驱动通常更稳定，程序默认也不会使用 ANGLE。
- 通过片段着色器中基于 uniform 的 UV 钳位，从渲染层面根治了双线性过滤带来的纹理 piece 边界和字形图集渗透问题，且不增加顶点结构体积。
- 使渲染 bug 修复只需改一处，所有平台同时受益。

## ⚠️ 版权与说明

**重要：本项目仅包含代码引擎，不包含任何游戏素材！**

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中：

*   `main.pak`
*   `properties/` 目录

本项目仅提供引擎代码，用于技术学习，**不包含**上述任何游戏资源文件，任何游戏资源均需要用户自行提供正版游戏文件。

本项目的源代码以 [**LGPL-3.0-or-later**](https://www.gnu.org/licenses/lgpl-3.0.html) 许可证开源，欢迎学习和贡献。
