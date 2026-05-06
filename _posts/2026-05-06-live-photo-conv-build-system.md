---
layout:     post
title:      GTK/Vala 开发教程：Meson 构建系统与跨平台项目架构
subtitle:   共享库、多二进制分发、GObject Introspection 与国际化
date:       2026-05-06
author:     wszqkzqk
header-img: img/GTK-logo.webp
catalog:    true
tags:       开源软件 Vala GTK 构建系统 Meson
---

## 前言

笔者此前的几篇 [GTK/Vala 教程](https://wszqkzqk.github.io/2025/08/07/GTK-Vala-Tutorial-3/) 侧重于语言特性、控件用法和算法实现，为了聚焦核心内容，一直采用单文件 `#!/usr/bin/env -S vala` 的方式编译。但一个真正能分发、能跨平台的项目，背后还需要一套完整的构建体系——共享库与可执行程序的拆分、条件编译、安装路径与资源管理、国际化、打包支持等等。这些内容与之前的教程互为补充，本文就以 [**Live Photo Converter**](https://github.com/wszqkzqk/live-photo-conv) 为样本，拆解 **Meson 构建体系**与**跨平台项目架构**。

项目仓库地址：[github.com/wszqkzqk/live-photo-conv](https://github.com/wszqkzqk/live-photo-conv)，建议克隆下来对照阅读。

## 项目概览

先看一下目录结构：

```
live-photo-conv/
├── meson.build          # 顶层构建定义
├── meson.options        # 构建选项
├── src/
│   ├── meson.build      # 源文件构建定义
│   ├── constants.vala.in
│   ├── *.vala           # Vala 源文件（约 15 个）
│   ├── platformbindings.c
│   ├── icons.gresource.xml
│   └── *.deps
├── po/                  # 国际化翻译
├── assets/              # 图标、.desktop 等资源
├── scripts/             # 构建辅助脚本
└── distros/             # 发行版打包
```

构建产物的组织方式是理解整个架构的钥匙。这个项目最终会产出以下内容：

*   **`liblivephototools.so`**：共享库，封装了动态照片处理的核心逻辑。附带 GObject Introspection 的 GIR 与 typelib，以及 Vala 的 VAPI 绑定文件，支持 Python、Rust 等任何 GI 语言直接调用。
*   **`live-photo-conv`**：功能最全的 CLI 工具，通过 `--make`、`--extract`、`--repair` 子命令覆盖所有操作。
*   **`live-photo-make`、`live-photo-extract`、`live-photo-repair`**：三个精简 CLI，实际是 `live-photo-conv` 的符号链接（Windows 下为副本），程序通过检测 `argv[0]` 自动切换模式。
*   **`copy-img-meta`**：独立的图片元数据迁移工具。
*   **`live-photo-conv-gtk`**：GTK4/LibAdwaita 图形界面程序。

一个共享库 + 多个前端程序的布局，很好地分离了 UI 与逻辑——无论是 CLI 还是 GUI，底层调用的都是同一份 `liblivephototools`。下面从构建系统的角度，逐步拆解这个项目是如何组织起来的。

## Meson 顶层配置

Meson 构建系统是 Vala 项目和 GNOME 生态的事实标准，对 GIR 生成、i18n 集成、Flatpak 构建都有原生支持。我们先从最顶层的 `meson.build` 看起。

### 项目声明

```meson
project('live-photo-conv', ['c', 'vala'],
          version: '0.40.3',
    meson_version: '>= 1.4',
)
```

`['c', 'vala']` 指定项目同时使用两种语言。Vala 编译器实际上是把 Vala 源码翻译成 C 再交给 C 编译器，但从 Meson 的角度，需要声明两种语言都存在——比如项目里有一个 `platformbindings.c` 是直接手写的 C 代码，而 Vala 也需要通过 C 编译器来完成最终的二进制链接。

### 版本号与 SO 版本分离

```meson
lib_api_version = '0.4'  # GIR 版本号 / API 版本号
lib_soversion = '0'      # SONAME / ABI 版本号
```

这两个变量服务不同的用途。`lib_api_version` 用在 GIR 标识符、pkg-config 文件和安装路径中，遵循语义化版本的主次版本号。下游通过 `gi.require_version('LivePhotoTools', '0.4')` 引入时，用的就是这个值。`lib_soversion` 则是 Linux 动态链接器的 `SONAME`——仅在 ABI 发生不兼容变化时才需要递增，编译器链接时写入 ELF 的 `NEEDED` 条目靠的就是它。把两者分开管理，可以在不破坏 API 兼容性的前提下安全地升级 SO 版本。

### 平台检测与条件编译

```meson
is_windows = target_machine.system() == 'windows'
is_darwin = target_machine.system() == 'darwin'
is_freedesktop = not is_windows and not is_darwin
if is_windows
  add_project_arguments('-D', 'WINDOWS', language: 'vala')
endif
```

`target_machine.system()` 返回 `'windows'`、`'darwin'` 或 `'linux'` 等字符串。这里的处理方式很直接：凡是既不是 Windows 也不是 macOS 的平台（Linux、FreeBSD 等），都归入 `is_freedesktop`。这个布尔值随后会在图标安装策略、桌面文件安装和 post-install hook 中反复出现。

关键的一步是 `add_project_arguments('-D', 'WINDOWS', language: 'vala')`——它在 Vala 编译器命令行中注入 `-D WINDOWS`，等效于 C 的 `#define WINDOWS`。于是整个 Vala 代码库都可以用 `#if WINDOWS` 来做条件编译，比如 `reporter.vala` 里的终端颜色检测和 `main.vala` 里 Windows 命令行参数的 UTF-8 转换。

## Feature 选项与条件依赖

这个项目有两个"不一定有"的后端——GStreamer 和 FFmpeg，还有一个"不一定需要"的 GUI。如果把这些都写成硬依赖，用户只是想用 CLI 处理几张照片，却必须先装全套 GTK 和 GStreamer，这显然不合理。反过来，如果什么都不依赖，功能又太弱。Meson 的 feature 选项正是为解决这种"有则用、无则免"的场景设计的。

### 选项定义

项目的构建选项集中放在 `meson.options` 中，而不是散落在 `meson.build` 顶部：

```meson
option('gst', type: 'feature', value: 'auto',
    description: 'GStreamer support')
option('gui', type: 'feature', value: 'auto',
    description: 'Build GTK4/LibAdwaita GUI')
option('gir', type: 'feature', value: 'auto',
    description: 'Enable GObject introspection')
option('manpages', type: 'feature', value: 'auto',
    description: 'Build manpages')
option('docs', type: 'feature', value: 'auto',
    description: 'Build documentation')
```

这里 `type: 'feature'` 是关键。Meson 的 feature 类型有三种状态：`enabled`（强制要求）、`disabled`（强制禁用）、`auto`（有则启用，无则跳过）。`value: 'auto'` 作为默认值意味着用户什么都不传时，Meson 会自动探测环境中是否有对应的依赖。

### 依赖解析

有了选项定义后，接下来是用这些选项去控制依赖的查找。`basic_deps` 是无论如何都要的（GLib 栈 + GExiv2），而 GStreamer 的三个依赖全部绑定到同一个 `require_gst` 上——要么全有，要么全无：

```meson
basic_deps = [
  dependency('glib-2.0'),
  dependency('gobject-2.0'),
  dependency('gio-2.0'),
  dependency('gmodule-2.0'),
  dependency('gexiv2'),
]
lib_deps = basic_deps

require_gst = get_option('gst')
gst = dependency('gstreamer-1.0', required: require_gst)
gst_app = dependency('gstreamer-app-1.0', required: require_gst)
gdk_pixbuf = dependency('gdk-pixbuf-2.0', required: require_gst)

with_gst = gst.found() and gst_app.found() and gdk_pixbuf.found()
if with_gst
  add_project_arguments('-D', 'ENABLE_GST', language: 'vala')
  lib_deps += [gst, gst_app, gdk_pixbuf]
endif
```

这里的设计思路是：`basic_deps` 列出无论如何都需要的依赖（GLib 栈 + GExiv2），而 GStreamer 相关的三个依赖全部绑定到同一个 `require_gst` 选项上——要么全有，要么全无。`with_gst` 通过 `.found()` 方法做最终判断，只有当三个依赖都找到时才为真。

当 GStreamer 可用时，除了把依赖追加到 `lib_deps` 之外，还会注入 `ENABLE_GST` 预处理器定义。整个项目中所有涉及后端选择的地方——GUI 里的 maker 实例化、CLI 里的 `--use-ffmpeg` 选项、以及 `src/meson.build` 中是否编译 GStreamer 版本的源文件——全由这一个宏控制。一处定义，处处生效。

GUI 的依赖解析采用了相同的模式：

```meson
require_gui = get_option('gui')
gtk4_dep = dependency('gtk4', required: require_gui)
libadwaita_dep = dependency('libadwaita-1', required: require_gui)
with_gui = gtk4_dep.found() and libadwaita_dep.found()
```

## 版本号注入与编译期常量

`meson.build` 里写的 `version: '0.40.3'` 只在发版时更新，日常开发中改了十几行代码跑出来的程序和打 tag 的正式版共享同一个版本号，出了问题根本没法追溯。所以需要一个更精确的版本戳，在每次构建时自动生成，并注入到代码中让 `--version` 能打印出来。

### Git 描述作为精确版本号

```meson
vcs_version = meson.project_version()
git = find_program('git', required: false)
if git.found()
  git_desc = run_command('git', 'describe', '--tags', '--abbrev=12', '--dirty', check: false)
  if git_desc.returncode() == 0
    raw = git_desc.stdout().strip()
    if raw.startswith('v')
      raw = raw.substring(1)
    endif
    vcs_version = raw.replace('-', '.')
  endif
endif
```

这段逻辑的产出比手动维护的 `meson.project_version()` 精确得多。假设最近一次 tag 是 `v0.40.3`，之后又提交了 5 个 commit，最新 commit 的缩写 hash 是 `gabcdef123456`，那么 `git describe` 会输出类似 `v0.40.3-5-gabcdef123456` 的字符串。经过去掉前缀 `v` 和替换 `-` 为 `.` 后，最终注入到程序里的版本号就变成了 `0.40.3.5.gabcdef123456`。即便没有打 tag 的中间版本，用户跑 `live-photo-conv --version` 也能知道具体是哪一次 commit 构建的。最后的 `--dirty` 标记还会在有未提交修改时追加 `.dirty` 后缀。

### configure_file 生成常量文件

```meson
localedir = join_paths(get_option('prefix'), get_option('localedir'))
constants_data = configuration_data()
constants_data.set_quoted('VERSION', vcs_version)
constants_data.set_quoted('GETTEXT_PACKAGE', meson.project_name())
constants_data.set_quoted('LOCALEDIR', localedir)
constants_file = configure_file(
    input: 'constants.vala.in',
    output: 'constants.vala',
    configuration: constants_data,
)
```

模板文件 `constants.vala.in` 长这样：

```vala
namespace LivePhotoConv {
    public const string VERSION = @VERSION@;
    public const string GETTEXT_PACKAGE = @GETTEXT_PACKAGE@;
    public const string LOCALEDIR = @LOCALEDIR@;

    public const string COPYRIGHT = "Copyright (C) 2024-2026 Zhou Qiankang <wszqkzqk@qq.com>";
    public const string SPDX_LICENSE_ID = "LGPL-2.1-or-later";
    public const string WEBSITE = "https://github.com/wszqkzqk/live-photo-conv";
    public const string ISSUES_URL = "https://github.com/wszqkzqk/live-photo-conv/issues";

    private const string LICENSE_TEXT = """ ... """;

    public string get_license () {
        return LICENSE_TEXT;
    }
}
```

Meson 用 `@VARIABLE@` 语法做替换。`set_quoted()` 与 `set()` 的区别在于前者会在值两侧加上双引号并转义内部引号——对于字符串常量这正是我们需要的行为。生成的文件放在构建目录下（不会污染源码树），然后作为 `lib_sources` 的最后一个元素参与编译，对整个项目可见。

`LOCALEDIR` 的计算也很讲究：`join_paths(get_option('prefix'), get_option('localedir'))`——在默认 `prefix=/usr/local`、`localedir=share/locale` 的情况下就是 `/usr/local/share/locale`；而当打包者通过 `-Dprefix=/usr` 覆盖时（AUR PKGBUILD 就是这样做的），它会自动变成 `/usr/share/locale`。gettext 运行时就是靠这个路径找到翻译文件的。

## 共享库构建与 GObject Introspection

如果说前面几节在定义"怎么编译"，那这一节开始进入"编译出来的是什么"。`liblivephototools` 是这个项目最核心的产出——它不仅要给自家的 CLI 和 GUI 用，还要能供 Python、Rust 等外部语言调用。要让一个 Vala 写的库做到这一点，需要同时产出 `.so`（共享库本体）、`.gir`（GObject Introspection 的 XML 描述）、`.typelib`（GI 的二进制运行时格式）、`.vapi`（Vala 绑定）和 `.pc`（pkg-config），五条输出一条都不能少。

### 条件源文件

```meson
lib_common_sources = [
  'errordomains.vala',
  'livemaker.vala',
  'livemakerffmpeg.vala',
  'livephoto.vala',
  'livephotoffmpeg.vala',
  'platformbindings.c',
  'reporter.vala',
  'utils.vala',
]

if with_gst
  lib_common_sources += [
    'livemakergst.vala',
    'livephotogst.vala',
    'sample2img.vala'
  ]
endif

lib_sources = lib_common_sources + [constants_file]
```

注意 GStreamer 相关的三个源文件只在使用 GStreamer 时才加入编译列表。`constants_file`（即生成的 `constants.vala`）总是在最后，因为它引用了前面源文件可能定义的符号。

### 共享库与 GIR

源文件就位之后，用 `shared_library()` 把它们编译成 `.so`。Meson 的 `vala_gir:` 参数让 Vala 编译器在编译的同时直接产出 GIR，一步完成：

```meson
lib_gi_name = 'LivePhotoTools'
lib_gi_version = lib_api_version
lib_gi = 'LivePhotoTools-' + lib_gi_version
lib_gir = lib_gi + '.gir'
lib_typelib = lib_gi + '.typelib'

if g_ir_compiler.found() and not valadoc.found()
  liblivephototools = shared_library(
    'livephototools', lib_sources,
    vala_gir: lib_gir,
    vala_args: ['--vapi-comments'],
    dependencies: lib_deps,
    version: meson.project_version(),
    soversion: lib_soversion,
    install: true,
    install_dir: [true, 'include/livephototools', true, true]
  )
else
  liblivephototools = shared_library(
    'livephototools', lib_sources,
    vala_args: ['--vapi-comments'],
    dependencies: lib_deps,
    version: meson.project_version(),
    soversion: lib_soversion,
    install: true,
    install_dir: [true, 'include/livephototools', true]
  )
endif
```

这里有两条分支。当 `g-ir-compiler` 可用且不需要 valadoc 生成带文档的 GIR 时，Meson 直接通过 `vala_gir:` 参数让 Vala 编译器同时产出 GIR 文件。`install_dir` 是一个数组，按照 Meson 的约定依次控制共享库 `.so`、C 头文件、VAPI 绑定、GIR 文件的安装路径；`true` 表示使用默认路径，索引 1 的 `'include/livephototools'` 则覆盖了头文件的安装子目录。

当 valadoc 被启用时（将在本篇 [Manpage 生成与 API 文档](#manpage-生成与-api-文档)一节简介），GIR 的生成改为由 valadoc 完成（因为 valadoc 可以在 GIR 中嵌入 API 文档），共享库的构建就不带 `vala_gir:` 参数了。

### GIR → typelib 编译

GIR 是 XML 格式的接口描述文件，运行时需要编译成二进制 typelib（`.typelib`）才能被 GObject Introspection 高效加载。这个步骤由 `g-ir-compiler` 完成：

```meson
if g_ir_compiler.found()
  custom_target(lib_typelib,
    input: liblivephototools,
    output: lib_typelib,
    depends: valadoc.found() ? gir_with_doc : liblivephototools,
    command: [
      g_ir_compiler,
      '--shared-library', '@PLAINNAME@',
      '--output', '@OUTPUT@',
      meson.current_build_dir() / lib_gir,
    ],
    install: true,
    install_dir: get_option('libdir') / 'girepository-1.0',
  )
endif
```

`g-ir-compiler` 把 XML 格式的 GIR 文件编译成二进制的 typelib（后缀 `.typelib`），这是运行时 GObject Introspection 实际加载的格式。`@PLAINNAME@` 是 Meson 的占位符，展开为不带路径的输入文件名（即 `liblivephototools.so`）。`depends:` 子句确保在 typelib 编译之前，生成 GIR 的上游步骤已经完成。

### pkg-config 与 .deps 文件

GI 体系解决了运行时跨语言调用的问题，而编译时的依赖传递则靠 pkg-config 和 Vala 的 `.deps` 文件——前者给 C 项目用，后者给 Vala 编译器用：

```meson
pkg.generate(
  name: 'LivePhotoTools',
  filebase: 'livephototools',
  description: 'A library for live photo conversion',
  url: 'https://github.com/wszqkzqk/live-photo-conv',
  libraries: liblivephototools,
  version: meson.project_version(),
  subdirs: 'livephototools',
  requires: lib_deps,
)
```

pkg-config 的 `.pc` 文件让下游 C 项目能通过 `pkg-config --cflags --libs livephototools` 获取编译和链接参数。

Vala 编译器还需要 `.deps` 文件——当用户写 `--pkg livephototools` 时，valac 会读取这个文件来确定需要自动链接哪些包。由于 Vala 还不支持 `.deps` 的条件生成，这里采用了一个简单务实的方案：准备两个版本的 `.deps` 文件，安装时根据构建配置选择正确的那个：

```meson
if with_gst
  install_data('livephototools.deps',
    install_dir: get_option('datadir') / 'vala' / 'vapi'
  )
else
  install_data('livephototools-no-gst.deps',
    rename: 'livephototools.deps',
    install_dir: get_option('datadir') / 'vala' / 'vapi'
  )
endif
```

含 GStreamer 的版本列出了 8 个包：

```
glib-2.0
gobject-2.0
gio-2.0
gmodule-2.0
gexiv2
gstreamer-1.0
gstreamer-app-1.0
gdk-pixbuf-2.0
```

不含 GStreamer 的版本只有前 5 个基础包。这样一来，下游项目无论用的哪种构建配置，只需 `--pkg livephototools` 就能自动拉入正确的依赖。

## 多二进制与符号链接分发

共享库编译好了，接下来是调用它的可执行程序。这里有一个有意思的设计决策：项目提供了五个 CLI 命令名，但只编译了两个二进制。`copy-img-meta` 功能独立，单独编译；而 `live-photo-make`、`live-photo-extract`、`live-photo-repair` 三个，都是 `live-photo-conv` 的别名。

### 单一入口，多重身份

具体做法很直接——同一个二进制根据 `argv[0]` 来切换模式：

```vala
string program_name = Path.get_basename (args[0]).ascii_down ();
if (program_name.has_prefix ("live-photo-make")) {
    // 只注册合成相关的选项
} else if (program_name.has_prefix ("live-photo-extract")) {
    // 只注册提取相关的选项
} else if (program_name.has_prefix ("live-photo-repair")) {
    // 只注册修复相关的选项
} else {
    // 通用模式：注册全部选项，通过 --make/--extract/--repair 子命令切换
}
```

运行 `live-photo-make --help` 时只看到合成相关的选项，而 `live-photo-conv --help` 则列出全部能力。对普通用户来说前三个更清晰，对高级用户来说通用命令更灵活。

### 跨平台的"符号链接"

Linux 上创建符号链接只需要 `ln -s`，但 Windows 上普通用户没有创建符号链接的权限。所以同一个"给二进制起别名"的需求，在跨平台时要分两条路径处理——Unix 平台创建真正的符号链接，Windows 平台用文件副本：

```meson
sub_exe_names = ['live-photo-make', 'live-photo-extract', 'live-photo-repair']

foreach exe_name : sub_exe_names
  linked_exe = custom_target('link-' + exe_name,
    output: exe_name + (is_windows ? '.exe' : ''),
    command: [
      python,
      symlink_script,
      main_exe_bin.full_path(),
      '@OUTPUT@',
    ],
    depends: main_exe_bin,
    build_by_default: true,
    install: is_windows,
    install_dir: get_option('bindir'),
  )
  if not is_windows
    install_symlink(
      exe_name,
      pointing_to: main_exe_name,
      install_dir: get_option('bindir')
    )
  endif
endforeach
```

这段是全文中最需要仔细看的跨平台处理。思路是：

*   **构建目录中**：始终通过一个 Python 脚本 `create-binary-symlinks.py` 创建链接。在 Unix 上它做 `symlink_to()`，在 Windows 上它做 `shutil.copy2()`。
*   **安装时**：在 Unix 平台上，Meson 的 `install_symlink()` 在安装目录中创建真正的符号链接——这样无论用户把程序装在哪个目录，链接关系都能保持。Windows 上则直接安装构建阶段生成的副本文件。

Python 脚本本身不到 60 行，核心逻辑也易懂：

```python
if platform.system() == 'Windows':
    shutil.copy2(source_path, target_path)
else:
    target_path.symlink_to(source_name)
```

注意这里有一个细节：symlink 使用的是相对路径 `source_name`（即 `live-photo-conv`），而不是源文件的绝对路径。这样安装后的符号链接不管被复制到哪个前缀下，只要和主二进制在同一个目录，就能正确解析。

### copy-img-meta：独立构建

`copy-img-meta` 虽然也链接同一个共享库，但因为它的源文件列表不同（只有一个 `copyimgmeta.vala`），所以单独构建：

```meson
copy_img_meta_bin = executable('copy-img-meta',
  ['copyimgmeta.vala'],
  install: true,
  link_with: liblivephototools,
  dependencies: lib_deps,
)
```

一个容易被忽略的要点是它并不依赖 `lib_common_sources`——它直接链接编译好的 `liblivephototools.so`，只把自己独有的 `copyimgmeta.vala` 编译成目标文件。这意味着即使将来修改了核心库的实现，只要 API 没变，`copy-img-meta` 就不需要重新编译自己的源文件。

## 跨平台资源策略

GUI 程序要能被系统识别为一个"正常应用"，需要做三件事：有一个桌面入口文件（`.desktop`）、有一个图标、在 Windows 上还要有一个嵌入式资源文件以便任务栏显示。这三件事在不同平台上的实现方式完全不同，而这个项目用了一套清晰的策略来管理。

### Linux：遵循 freedesktop 规范

在 freedesktop 兼容的桌面环境（Linux、BSD 等）上，应用图标和桌面入口文件直接安装到约定的系统路径即可，不需要编译进二进制：

```meson
if is_freedesktop
  install_data('../assets/com.github.wszqkzqk.live-photo-conv.desktop',
    install_dir: get_option('datadir') / 'applications',
  )
  install_data('../assets/icon.png',
    install_dir: get_option('datadir') / 'icons' / 'hicolor' / '256x256' / 'apps',
    rename: 'com.github.wszqkzqk.live-photo-conv.png',
  )
endif
```

`.desktop` 文件放到 `/usr/share/applications/`，图标放到 hicolor 主题的标准路径下，使用反向域名重命名——这是 GNOME/Flatpak 生态中定位图标的惯例。运行时程序通过 `Gtk.IconTheme` 按名称查找，主题引擎会自动在 hicolor 路径中匹配。

### 非 Linux（含 Flatpak）：GResource 嵌入

在 Flatpak 沙盒或非 freedesktop 平台上，文件系统路径约定不可靠——应用图标必须直接编译进可执行文件。GResource 是 GLib 提供的资源打包机制，能将任意文件编译为 C 代码后链接进二进制，并提供虚拟文件系统供运行时访问：

```meson
if not is_freedesktop
  gui_sources += gnome.compile_resources('live-photo-conv-gtk-resources',
    'icons.gresource.xml',
    source_dir: '..',
  )
endif
```

`icons.gresource.xml` 描述了打包内容：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<gresources>
  <gresource prefix="/com/github/wszqkzqk/live-photo-conv/icons">
    <file alias="256x256/apps/com.github.wszqkzqk.live-photo-conv.png">../assets/icon.png</file>
  </gresource>
</gresources>
```

`alias` 属性让文件在 GResource 内部的虚拟路径沿用 hicolor 的目录结构——这样运行时无论是从文件系统还是从 GResource 查找图标，路径一致。

### Windows：.rc 资源文件

Windows 有一套完全不同的资源管理机制，可执行文件的图标在链接阶段通过 `.rc` 资源脚本嵌入，格式也必须是 `.ico` 而非 `.png`：

```meson
if is_windows
  win_rc = configure_file(
    input: files('../assets/live-photo-conv-gtk.rc'),
    output: 'live-photo-conv-gtk.rc',
    copy: true,
  )
  configure_file(
    input: files('../assets/icon.ico'),
    output: 'icon.ico',
    copy: true,
  )
  gui_sources += import('windows').compile_resources(win_rc)
endif
```

`import('windows').compile_resources()` 是 Meson 的 Windows 模块，负责把 `.rc` 编译成 `.o` 目标文件链接进可执行文件。GUI 二进制还额外设置了 `win_subsystem: 'windows'`，这让它在启动时不弹出控制台窗口。

### 安装后处理

安装完文件和图标之后，还需要通知桌面环境刷新缓存，否则应用启动器可能不会立刻显示新装的应用。`gnome.post_install()` 正是为此而生：

```meson
if with_gui and is_freedesktop
  gnome.post_install (
    gtk_update_icon_cache: true,
    update_desktop_database: true,
  )
endif
```

它会依次调用 `gtk-update-icon-cache` 和 `update-desktop-database`。只在 `is_freedesktop` 且构建了 GUI 时才执行——其他平台上这些命令不存在，也不需要。

## 国际化的构建侧配置

GUI 界面上的按钮文字、提示信息都需要支持多语言。在 Vala 里做翻译靠的是 GLib 的 gettext 绑定——代码里写 `_("Make")`，运行时从翻译文件里找对应语言的版本。而要让这个机制跑起来，构建系统需要做三件事：告诉编译器翻译文件的查找路径、管理 .po 翻译文件的编译、以及把翻译集成到安装流程中。

### gettext 集成

```meson
# 顶层 meson.build
add_project_arguments('-DGETTEXT_PACKAGE="@0@"'.format(meson.project_name()), language: 'c')
```

这一行把 `-DGETTEXT_PACKAGE="live-photo-conv"` 注入到 C 编译器的命令行。注意 `language: 'c'`——虽然最终目标是 Vala 程序，但 Vala 编译器生成的是 C 代码，所以这里要作为 C 编译参数传递。Vala 代码中引用 `GETTEXT_PACKAGE` 时，编译器会把它当作一个来自 C 预处理器的宏常量。

然后 `LOCALEDIR` 和 `GETTEXT_PACKAGE` 通过 `configure_file` 注入到 `constants.vala`（见前文"[版本号注入与编译期常量](#版本号注入与编译期常量)"一节）。运行时在 `main.vala` 和 `gui.vala` 的入口处执行标准的 gettext 初始化：

```vala
Intl.setlocale (LocaleCategory.ALL, "");
Intl.bindtextdomain (GETTEXT_PACKAGE, LOCALEDIR);
Intl.bind_textdomain_codeset (GETTEXT_PACKAGE, "UTF-8");
Intl.textdomain (GETTEXT_PACKAGE);
```

之后代码中所有 `_("string")` 调用便会自动查找对应语言的翻译。

### po/ 子目录

`po/meson.build` 只有一行：

```meson
i18n.gettext(meson.project_name(),
    args: '--directory=' + meson.project_source_root(),
    preset: 'glib'
)
```

`preset: 'glib'` 告诉 Meson 按照 GLib 的惯例来组织翻译文件——`.mo` 文件安装到 `$LOCALEDIR/语言代码/LC_MESSAGES/项目名.mo`。`--directory` 参数让 `xgettext` 在扫描 `POTFILES` 中列出的源文件时，从项目根目录解析相对路径。

`POTFILES` 列出了包含可翻译字符串的源文件：

```
src/gui.vala
```

目前只有 GUI 做了国际化——CLI 的输出走的是 `Reporter` 模块直接输出英文，暂未纳入翻译范围。这是有意为之：跨平台的命令行 locale 处理有各种边界情况（Windows 控制台编码、SSH 会话的 locale 传播、CI 环境），权衡之后只对 GUI 做国际化。

`LINGUAS` 列出当前支持的 8 种语言：

```
de es fr ja ko pt_BR ru zh_CN
```

翻译通过 [Hosted Weblate](https://hosted.weblate.org/projects/live-photo-conv/) 平台管理，贡献者不需了解 `.po` 文件格式就能直接参与。

### .desktop 文件的多语言化

桌面入口文件也做了国际化，`Comment` 字段按语言分别提供翻译：

```ini
[Desktop Entry]
Name=Live Photo Converter
Comment=Convert, extract and repair Android Live Photos
Comment[de]=Android Live Photos konvertieren, extrahieren und reparieren
Comment[es]=Convierte, extrae y repara Live Photos de Android
Comment[fr]=Convertissez, extrayez et réparez des Live Photos Android
Comment[ja]=Android Live Photo の変換、抽出、修復
Comment[ko]=Android Live Photo 변환, 추출 및 복구
Comment[pt_BR]=Converta, extraia e repare Live Photos do Android
Comment[ru]=Конвертируйте, извлекайте и восстанавливайте Android Live Photos
Comment[zh_CN]=转换、提取和修复 Android 动态照片
```

当用户在桌面环境的语言设置中切换时，应用启动器会自动显示对应语言的描述。

## Manpage 生成与 API 文档

这属于"锦上添花"的构建目标——有则更好，没有也不影响程序正常运行。CLI 工具的 manpage 让用户能通过 `man live-photo-conv` 查看帮助，不需要每次跑 `--help`；API 文档则让下游开发者能在 IDE 里直接看到库的接口说明。

### help2man 自动生成 manpage

`help2man` 是一个省心省力的工具——它直接运行目标程序的 `--help`，把选项列表和描述自动转成 troff 格式的 manpage，省去了手写 groff 的繁琐。`-N` 参数告诉它即使 `--help` 的输出格式不完全符合 GNU 标准也不要报错（因为 GOption 生成的格式跟 getopt 略有差异），`--no-discard-stderr` 确保帮助信息即使输出到 stderr 也不会丢失：

```meson
if help2man_prog.found()
  custom_target('manpage-' + main_exe_name,
    output : main_exe_name + '.1',
    command : [
      help2man_prog,
      '-N',
      '-o', '@OUTPUT@',
      main_exe_bin,
      '--no-discard-stderr',
    ],
    install : true,
    install_dir : get_option('mandir') / 'man1',
  )
  # ... 对子命令和 copy-img-meta 也生成 manpage
endif
```

子命令的 manpage 也一并生成，关键在于 `depends:` 子句：

```meson
custom_target('manpage-' + sub_exe_names[index],
  ...
  depends : sub_exe_bins[index],
)
```

如果一个可执行文件在构建时被创建（比如 `custom_target` 生成的副本或硬链接），help2man 必须在它存在之后才能运行。`depends:` 保证了正确的构建顺序。

### Valadoc 与带文档的 GIR

当 `valadoc` 可用且 `-Ddocs=enabled` 时，项目可以生成带嵌入式 API 文档的 GIR 文件：

```meson
if valadoc.found()
  # ... 收集所有源文件，组装 valadoc 命令行
  gir_with_doc = custom_target(
    'livephototools gir with doc',
    command: [
        valadoc,
        '--force', '--verbose',
        '--package-name', 'liblivephototools',
        '--package-version', meson.project_version(),
        deps_command,
        '--vapidir', join_paths(meson.project_build_root(), 'src'),
        '--vapidir', join_paths(meson.global_source_root(), 'vapi'),
        '--doclet=devhelp',
        '-o', 'docs',
        constants_file.full_path(),
        '--gir', '@OUTPUT@',
        '@INPUT@'
    ],
    ...
  )
endif
```

关键参数是 `--gir @OUTPUT@` 和 `--doclet=devhelp`——前者让 valadoc 在生成文档的同时输出 GIR，后者生成 Devhelp 格式的文档（可被 GNOME Builder 等 IDE 直接浏览）。后续 typelib 编译的 `depends:` 指向 `gir_with_doc`，保证了完整的依赖链条。

这部分将在后续文章中详述，目前只需要了解构建体系中预留了这个入口。

## 编译与运行

### 依赖安装

**Arch Linux：**

```bash
sudo pacman -S --needed glib2 libgexiv2 meson vala gtk4 libadwaita \
    gstreamer gst-plugins-base-libs gdk-pixbuf2 gobject-introspection \
    gst-plugins-good gst-plugins-bad gst-plugin-va
```

**Debian/Ubuntu：**

```bash
sudo apt install build-essential meson valac libgexiv2-dev libglib2.0-dev \
    libgtk-4-dev libadwaita-1-dev libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev libgdk-pixbuf-2.0-dev \
    gobject-introspection libgirepository1.0-dev \
    gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-vaapi
```

**Windows（MSYS2 UCRT64）：**

```bash
pacman -S --needed mingw-w64-ucrt-x86_64-glib2 mingw-w64-ucrt-x86_64-cc \
    mingw-w64-ucrt-x86_64-gexiv2 mingw-w64-ucrt-x86_64-meson \
    mingw-w64-ucrt-x86_64-vala mingw-w64-ucrt-x86_64-gtk4 \
    mingw-w64-ucrt-x86_64-libadwaita mingw-w64-ucrt-x86_64-gstreamer \
    mingw-w64-ucrt-x86_64-gst-plugins-base mingw-w64-ucrt-x86_64-gdk-pixbuf2 \
    mingw-w64-ucrt-x86_64-gobject-introspection \
    mingw-w64-ucrt-x86_64-gst-plugins-good \
    mingw-w64-ucrt-x86_64-gst-plugins-bad
```

### 构建命令

```bash
git clone https://github.com/wszqkzqk/live-photo-conv.git
cd live-photo-conv
```

默认配置（自动检测所有可选依赖）：

```bash
meson setup builddir --buildtype=release
meson compile -C builddir
meson install -C builddir
```

按需禁用某些功能：

```bash
# 不构建 GUI，只保留 CLI 和共享库
meson setup builddir --buildtype=release -D gui=disabled

# 禁用 GStreamer，只用 FFmpeg 后端
meson setup builddir --buildtype=release -D gst=disabled

# 只构建 CLI，不要 GUI 和 GIR
meson setup builddir --buildtype=release -D gui=disabled -D gir=disabled
```

所有 option 的组合都可以自由搭配，Meson 会自动处理依赖链上的缺失。

## 关于后续

本文把整个项目的骨架完整梳理了一遍——从 Meson 的顶层配置、feature 选项、依赖解析，到共享库的 GObject Introspection 输出体系，再到多二进制的符号链接分发、跨平台资源策略和国际化构建配置。这些都是单文件教程难以覆盖的工程实践。

下一篇文章将进入 `src/gui.vala`，以同一个项目为例，详细拆解 GTK4 / LibAdwaita 图形界面的实现——自定义控件、异步线程模型、ViewStack 的页面组织、错误处理体系和主题切换等内容都会一一展开。
