---
layout:     post
title:      Live Photo Converter 的 Android 构建实践
subtitle:   pixiewood、Meson、静态 GStreamer 与 CI 签名
date:       2026-08-24
author:     wszqkzqk
header-img: img/GTK-logo.webp
catalog:    true
tags:       开源软件 Vala GTK LibAdwaita Android Meson 构建系统 GStreamer
---

## 前言

[Live Photo Converter](https://github.com/wszqkzqk/live-photo-conv) 从 0.50.0 开始提供 Android 版本。这个版本继续使用桌面端的 GTK4 / LibAdwaita 界面，同时把 GStreamer、FFmpeg、exiv2 等依赖一起放进 APK。GUI 和桌面版共用 `gui.vala`，平台差异只保留在少数 `#if ANDROID` 分支里。

GTK 在 Android 上的资料并不多。这次移植主要依赖 GTK 主线的 **Android GDK 后端**，以及 GTK 社区维护的 [**pixiewood**](https://github.com/sp1ritCS/gtk-android-builder)（gtk-android-builder）。GTK 和 libadwaita 自己的 CI 也用它来生成演示 APK。下面按实际遇到的问题，记录 pixiewood 清单、Meson 适配、静态 GStreamer，以及 CI 签名和发布的做法。运行时的 SAF 文件访问（`content://` URI 和 staging）放在[下一篇](https://wszqkzqk.github.io/2026/08/25/live-photo-conv-android-saf/)介绍。

项目源码在 [github.com/wszqkzqk/live-photo-conv](https://github.com/wszqkzqk/live-photo-conv)，文中的片段都可以在仓库里找到。

## pixiewood 与 GTK 的 Android 运行时

### 应用模型：可执行文件变成共享库

Android 应用的 native 代码会以共享库的形式由 Java 运行时加载。GTK 的 Android 运行时也是这样：加载应用的库，然后调用其中导出的 `main()`。因此 pixiewood 对应用有两个要求：

* 有一个**暴露的 `main(int, char**, char**)` 入口**，且返回前最终会调用 `g_application_run`；
* Meson 构建脚本中，应用目标设置了 `android_exe_type: 'application'` 关键字——这个参数是 **Meson 1.9 才引入的**，它让 `executable()` 在 Android 上实际产出共享库而非可执行文件。

Vala 的 `public static int main (string[] args)` 编译后会导出 C 符号 `main`，第一条不需要额外处理。第二条在 `src/meson.build` 中为 Android 单独设置即可：

```meson
if is_android
  # Loaded as a shared library by the GTK Android runtime, which calls
  # the exported main().
  executable(gui_name,
    gui_sources,
    android_exe_type: 'application',
    install: true,
    link_with: liblivephototools,
    dependencies: gui_deps,
    vala_args: android_gui_vala_args,
  )
else
  executable(gui_name,
    gui_sources,
    install: true,
    link_with: liblivephototools,
    dependencies: gui_deps,
    win_subsystem: 'windows',
  )
endif
```

CLI 也不参与 Android 构建。手机应用没有终端环境，命令行工具在这里没有用：

```meson
# CLI tools are meaningless on Android
if not is_android
  # live-photo-conv、copy-img-meta 及子命令链接……
endif
```

因为 `android_exe_type` 是 Meson 1.9 才加入的，`meson.build` 开头会检查版本：

```meson
if is_android
  if not meson.version().version_compare('>= 1.9')
    error('Android builds require meson >= 1.9, found ' + meson.version())
  endif
  add_project_arguments('-D', 'ANDROID', language: 'vala')
  # ……
endif
```

`ANDROID` 宏的作用和桌面端的 `WINDOWS` 宏一样，供 Vala 代码使用 `#if ANDROID`。

### pixiewood 的工作流程

pixiewood 是一个 Perl 脚本，负责把 Meson 生成的共享库组装成 APK。运行它需要四样东西：

* 一份描述应用的 **pixiewood.xml 清单**（下一节详述）；
* **Android SDK 与 NDK**；
* [**mini-studio**](https://github.com/sp1ritCS/mini-studio)——Android Studio 项目的一个最小子集，充当 APK 的 Gradle 骨架；
* 应用自己的源码树。

CI 中的构建分三步：

```bash
./pixiewood-tool/pixiewood prepare --release \
  -s "${ANDROID_HOME}" \
  -t "${ANDROID_HOME}/ndk/${ANDROID_NDKVER}" \
  -a ./mini-studio \
  pixiewood.xml
./pixiewood-tool/pixiewood generate
./pixiewood-tool/pixiewood build
```

`prepare` 解析清单，按需把依赖的 wrap 写入 `subprojects/`，并准备各架构的 Meson 交叉构建；`generate` 生成 Gradle 工程和 Java 胶水代码；`build` 负责交叉编译、打包，最后得到未签名 APK。SDK 组件由 `build-aux/android-sdk.sh` 安装。这个脚本改自 GTK 主线的 `.gitlab-ci/android-sdk.sh`，通过 `sdkmanager` 安装 build-tools、NDK 和 platform，并自动接受许可协议。

## pixiewood.xml 清单

`pixiewood.xml` 是整个构建的入口，里面主要是元信息、主题、依赖和构建选项。

### metainfo：版本号进 APK

```xml
<metainfo vercalc="sem121010">
  <xi:include href="build://aarch64/app.metainfo.xml" parse="xml"/>
</metainfo>
```

pixiewood 从 AppStream metainfo 读取应用 ID、名称和版本。`build://` 前缀指向**构建目录**。这个 metainfo 文件由 Meson 在配置阶段通过 `configure_file` 生成，版本号来自 `git describe`：

```meson
# Consumed by pixiewood.xml via a build:// include
configure_file(
  input: 'android/app.metainfo.xml.in',
  output: 'app.metainfo.xml',
  configuration: {'VERSION': vcs_version},
)
```

`vercalc="sem121010"` 指定了转换 Android `versionCode` 的算法：`(major << 20) + (minor << 10) + patch`。它要求版本号符合语义化版本格式。这样 APK 的版本直接来自 git 历史，不需要另写一份版本号。

### style：主题与图标生成

```xml
<style>
  <theme name="adw"/>
  <icon type="generate">
    <drawable target="foreground" scale=".5" type="svg"
              path="src://assets/icon.svg"/>
    <color target="background">#FFFFFF</color>
  </icon>
</style>
```

`theme` 选择应用主题（`adw` 就是 LibAdwaita 风格）。`icon type="generate"` 会让 pixiewood 根据 SVG 生成 Android 自适应图标的各个尺寸；`src://` 指向源码树，前景使用应用图标，背景设为纯色。项目把各平台图标统一成一份 master SVG 后，这里可以直接复用。

### dependencies：两套 wrap 如何分工

```xml
<dependencies>
  <glib>
    <patch>hack</patch>
  </glib>
  <cairo/>
  <fontconfig/>
  <harfbuzz/>
  <gdk-pixbuf/>
  <libadwaita revision="2d3f160a3514934ac9e3eaf02399734dc005020a"/>
</dependencies>
```

这一段列出的是 **pixiewood 自带 wrap 集中的依赖**，`prepare` 会把它们写进 `subprojects/`。其中有两点和普通 Meson 构建不太一样：

* `<glib><patch>hack</patch></glib>` 应用了 pixiewood 为 glib 准备的 hack 补丁；
* `libadwaita` 用 `revision` 属性**锁定到了一个 main 分支的 commit**。上游 main 引入了 `G_GNUC_FLAG_ENUM`，要求宿主机的 `glib-mkenums` 认识这个宏，而构建环境中的 glib 版本还不够新；另一方面，pixiewood 针对 AppStream 的补丁只适用于 main。因此这里固定了一个同时满足这两个条件的提交。

GTK、gexiv2/exiv2 和 GStreamer 没有写在这份清单里，而是由仓库 `subprojects/` 中的 wrap 提供。原因是 `prepare` 会覆盖清单中声明的依赖对应的 wrap；需要自带补丁或固定版本的依赖，必须避开这一步：

```ini
# GTK main (pinned; bump manually). Declaring <gtk/> in pixiewood.xml
# would overwrite this wrap. A pinned commit cannot be shallow-cloned.
[wrap-git]
directory = gtk
url = https://gitlab.gnome.org/GNOME/gtk.git
revision = d1872a0b1f4da7fe132d41722fa7f1bf692beb92

[provide]
dependency_names = gtk4
```

GTK 固定在 main 的一个 commit。移植时提交的两个上游修复——[`gtk!10178`](https://gitlab.gnome.org/GNOME/gtk/-/merge_requests/10178) 和 [`gtk!10190`](https://gitlab.gnome.org/GNOME/gtk/-/merge_requests/10190) 目前已经全部合并。content file 写回问题的来龙去脉会在下一篇展开说明。

`gexiv2android.wrap` 也有意使用了不同的名字：它**不叫 `gexiv2`**，并且没有 `[provide]`：

```ini
# gexiv2 for Android builds, pinned release; bump manually. Deliberately
# not named "gexiv2" and without [provide], so desktop builds never fall
# back to it silently.
[wrap-git]
url = https://gitlab.gnome.org/GNOME/gexiv2.git
revision = 0.16.2
depth = 1
```

如果它也叫 `gexiv2` 并声明 provide，那么桌面系统没有安装 gexiv2 时，Meson 可能**静默回退**到这个 Android 专用子项目，构建结果就会变得不可预期。改名后，Android 构建需要显式指定 fallback：

```meson
if is_android
  # Not in pixiewood's wrap set; built from subprojects/gexiv2android.wrap.
  basic_deps += dependency('gexiv2', fallback: ['gexiv2android', 'libgexiv2'])
else
  basic_deps += dependency('gexiv2-0.16', 'gexiv2')
endif
```

gexiv2 和 exiv2 的构建也做了裁剪。清单的 configure-options 关闭了 gexiv2 的 introspection、vapi、gtk_doc、python3、tools 和 tests；exiv2 只打开项目真正用到的功能：

```xml
<option>-Dexiv2:xmp=enabled</option>
<option>-Dexiv2:png=enabled</option>
<option>-Dexiv2:bmff=true</option>
<option>-Dexiv2:iconv=disabled</option>
<option>-Dexiv2:inih=disabled</option>
<option>-Dexiv2:brotli=disabled</option>
<option>-Dexiv2:curl=disabled</option>
<option>-Dexiv2:nls=disabled</option>
```

XMP 是修复功能的基础，必须显式启用；`bmff=true` 保留 BMFF（MP4/MOV 容器）的元数据支持。iconv、inih、brotli、curl、nls 等功能则全部关闭，避免引入不必要的嵌套依赖。

## Meson 侧的 Android 适配

### 交叉构建没有 GIR：把 VAPI 放进仓库

Vala 项目需要各个库的 `.vapi` 绑定。GTK 栈通常在构建时通过 GObject Introspection 扫描生成这些文件，但**交叉构建无法运行目标架构的 GIR 工具**，因此不能现场生成。项目把需要的 VAPI 直接提交进仓库：

```
android/vapi/
├── README.md
├── gexiv2.deps
├── gexiv2.vapi            # 317 行
├── libadwaita-1.deps
└── libadwaita-1.vapi      # 2855 行
```

`android/vapi/README.md` 记录了维护约定：只有 `host_machine.system() == 'android'` 时才使用这些文件；`gexiv2.vapi` 要和 `gexiv2android.wrap` 的版本对应；如果代码开始使用更新的 API，就从相应 release 重新提取。Meson 侧只需加入 VAPI 搜索路径：

```meson
# No GObject-Introspection in Android cross builds; use vendored VAPIs
add_project_arguments('--vapidir', meson.project_source_root() / 'android' / 'vapi', language: 'vala')
```

### 子项目依赖无法推断 `--pkg`

另一个问题是 `--pkg` 参数。桌面构建中，`dependency('gtk4')` 返回 pkg-config 依赖，Meson 会自动把 `--pkg gtk4` 传给 valac；依赖改由**子项目**提供后，Meson 推断不出 Vala 包名，编译时就会报找不到命名空间。Android 构建因此要手动补上这些参数：

```meson
android_vala_args = []
android_gui_vala_args = []
if is_android
  foreach pkg : ['gio-2.0', 'gmodule-2.0', 'gexiv2',
                 'gstreamer-1.0', 'gstreamer-app-1.0', 'gdk-pixbuf-2.0']
    android_vala_args += ['--pkg', pkg]
  endforeach
  android_gui_vala_args = android_vala_args + ['--pkg', 'gtk4', '--pkg', 'libadwaita-1']
endif
```

两个数组分别追加到共享库和 GUI 目标的 `vala_args`。桌面构建中它们为空，不会改变原有逻辑。

### C++ 运行时与符号可见性

exiv2 和 gexiv2 是 C++ 库。Android 不会替应用提供要用的 C++ 运行时，所以必须把 NDK 中的 `libc++_shared.so` 一起放进 APK：

```meson
# exiv2/gexiv2 need the C++ runtime; ship it in the APK
libcpp = meson.get_external_property('sys_root') / 'usr' / 'lib' / (
  target_machine.cpu_family() + '-linux-android') / 'libc++_shared.so'
install_data(libcpp, install_dir: get_option('libdir'), install_tag: 'runtime')
```

`meson.get_external_property('sys_root')` 从交叉文件取得 NDK sysroot，再按 ABI 拼出对应的 `libc++_shared.so` 路径。文件安装到 libdir 后，pixiewood 打包时会把它一起收进 APK。

链接阶段还遇到过静态 FFmpeg 的 NEON 汇编符号问题。Android 构建统一加上：

```meson
# Make statically linked FFmpeg NEON asm linkable into shared objects
add_project_link_arguments('-Wl,-Bsymbolic', language: ['c', 'cpp'])
```

`-Wl,-Bsymbolic` 会让共享库内部的符号引用优先绑定到库内定义，避免静态链接进来的汇编符号在后续动态链接时无法解析。

### 图标资源：没有系统图标主题

Android 没有 freedesktop 的 hicolor 图标主题，GUI 使用的 symbolic 图标必须随应用放进 GResource：

```meson
# No system icon theme on Android; bundle the symbolic icons we use
if is_android
  gui_sources += gnome.compile_resources('live-photo-conv-gtk-android-icons',
    '../android/icons.gresource.xml',
    c_name: 'icons_android',
    source_dir: '../android',
  )
endif
```

这和 Windows、macOS 等非 freedesktop 平台的做法相同，只是 Android 也需要走一次 GResource 打包。

## 全静态 GStreamer：gst-full

### 为什么必须是静态链接

桌面版有 GStreamer 和 FFmpeg 两个后端，FFmpeg 后端会通过 spawn 启动 `ffmpeg`/`ffprobe`。Android 应用不能依赖这些外部进程，必须使用进程内的 GStreamer；而系统又没有现成的 GStreamer，所以只能把它**静态链接**进应用。

GStreamer monorepo 提供了 `gst-full` 目标，可以把核心库和选中的插件合成一个静态库。Meson 侧只在 Android 分支切换依赖：

```meson
require_gst = get_option('gst')
if is_android
  # Spawning external ffmpeg is not viable on Android; the in-process
  # GStreamer backend is mandatory, statically linked via gst-full.
  # gdk-pixbuf comes from pixiewood's <gdk-pixbuf/> dependency.
  require_gst = true
  gst = dependency('gstreamer-full-1.0', fallback: ['gstreamer-full', 'gst_full_dep'])
  gst_app = gst
  gdk_pixbuf = dependency('gdk-pixbuf-2.0')
else
  gst = dependency('gstreamer-1.0', required: require_gst)
  gst_app = dependency('gstreamer-app-1.0', required: require_gst)
  gdk_pixbuf = dependency('gdk-pixbuf-2.0', required: require_gst)
endif
```

`gst-full` 把 `gstreamer` 和 `gstreamer-app` 合并成一个 `gst_full_dep`，因此这里直接令 `gst_app = gst`。上层的 `with_gst` 判断和 `ENABLE_GST` 宏都不用改，应用代码看不出后端换过。

wrap 文件锁定 release 并携带一个补丁：

```ini
[wrap-git]
directory = gstreamer-full
url = https://gitlab.freedesktop.org/gstreamer/gstreamer.git
revision = 1.28.6
depth = 1
diff_files = gstreamer-full/shared-glib.patch

[provide]
dependency_names = gstreamer-full-1.0
```

`[provide]` 只提供 `gstreamer-full-1.0` 这个名字。桌面构建不会查询它，所以这个 wrap 不会影响桌面依赖解析。

### 插件选择：绕过 gst-full-plugins 的上游 bug

通常可以通过 `gst-full-plugins` 列出要打包的插件，但上游这个选项的插件名校验有问题（`pixiewood.xml` 的注释里也记着这件事）。因此项目没有使用插件清单，而是**对每个子项目分别设置 build option**：

```xml
<!-- Static gst-full. Do NOT use gst-full-plugins with an explicit
     list (name check broken upstream); select plugins via build
     options. default_library does not cascade to nested
     subprojects. -->
<option>-Dgstreamer-full:default_library=static</option>
<option>-Dgstreamer:default_library=static</option>
<option>-Dgst-plugins-base:default_library=static</option>
<option>-Dgst-plugins-good:default_library=static</option>
<option>-Dgst-plugins-bad:default_library=static</option>
<option>-Dgst-libav:default_library=static</option>
<option>-DFFmpeg:default_library=static</option>
<option>-Dgstreamer-full:gst-full=enabled</option>
<option>-Dgstreamer-full:gst-full-target-type=static_library</option>
<option>-Dgstreamer-full:gst-full-libraries=gstreamer-app-1.0</option>
```

这里有两个容易踩坑的 Meson 行为：

* **`default_library` 不会传给嵌套子项目**。gst-plugins-base/good/bad、gst-libav 和 FFmpeg 都在 gstreamer-full monorepo 内部，必须逐个设为 `static`；
* `gst-full-target-type=static_library` 和 `gst-full-libraries=gstreamer-app-1.0` 决定最终产物是静态库，并且只暴露 app 库接口。

插件功能也要逐项打开或关闭。对每个子项目设置全局 `auto_features` 并不会自动传递，所以选项仍然要逐项写出来：

```xml
<option>-Dgstreamer-full:ugly=disabled</option>
<option>-Dgstreamer-full:devtools=disabled</option>
<!-- ……webrtc、libnice、python、orc、tools、tests、introspection、nls、tls 全关 -->
<option>-Dgstreamer-full:libav=enabled</option>
<option>-Dgst-plugins-base:playback=enabled</option>
<option>-Dgst-plugins-base:app=enabled</option>
<option>-Dgst-plugins-base:videoconvertscale=enabled</option>
<option>-Dgst-plugins-base:audioconvert=enabled</option>
<option>-Dgst-plugins-base:audioresample=enabled</option>
<option>-Dgst-plugins-base:typefind=enabled</option>
<option>-Dgst-plugins-base:gio=enabled</option>
<option>-Dgst-plugins-base:gl=disabled</option>
<option>-Dgst-plugins-good:isomp4=enabled</option>
<option>-Dgst-plugins-good:audioparsers=enabled</option>
<option>-Dgst-plugins-bad:videoparsers=enabled</option>
<option>-Dgst-plugins-bad:gl=disabled</option>
<option>-Dgst-plugins-bad:androidmedia=disabled</option>
<option>-Dgst-plugins-bad:fdkaac=disabled</option>
<option>-Dgst-plugins-bad:openh264=disabled</option>
```

最终保留下来的功能并不多：解码交给 **gst-libav（静态 FFmpeg）**，`isomp4` 负责 MP4 解封装，`playback` 提供 playbin/decodebin，再加上必要的 convert 和 parser 插件。`fdkaac`、`openh264` 与 FFmpeg 的能力重复，前者还有许可证方面的顾虑，因此都关闭。GL 相关插件不需要（GTK Android 后端不走这套 GL 栈），`androidmedia` 也关闭，所有解码都在进程内由 FFmpeg 完成。

### shared glib 补丁

`gst-full` 原本用 `link_whole` 把 glib 整体嵌进静态库，这要求 glib 也是**静态**构建。但 pixiewood 会把 glib 构建成**共享库**，两者不能直接搭配。`shared-glib.patch` 检测到这种情况后改用普通链接：

```diff
 if building_full
   gobject_dep = dependency('gobject-2.0')
   if gobject_dep.type_name() == 'internal'
     glib_subproject = subproject('glib')
-    exposed_libs += glib_subproject.get_variable('libglib')
-    exposed_libs += glib_subproject.get_variable('libgobject')
+    # link_whole requires static libraries, but the glib subproject may be
+    # built shared (e.g. pixiewood Android builds). Link against it
+    # normally instead of embedding it; its symbols are resolved when the
+    # final application/shared library is linked.
+    glib_deps = [glib_dep, gobject_dep]
```

这样符号会在最终应用共享库链接时解析，功能不变。

### 子项目解析顺序

依赖解析还有一个顺序问题。`meson.build` 必须先解析 GTK，再处理 GStreamer：

```meson
# NOTE: must be resolved before gstreamer-full: the monorepo also calls
# subproject('gtk'), which would poison the global subproject cache.
require_gui = get_option('gui')
if is_android
  # On Android the GUI *is* the application
  require_gui = true
endif
gtk4_dep = dependency('gtk4', required: require_gui)
libadwaita_dep = dependency('libadwaita-1', required: require_gui)
```

gstreamer-full monorepo 内部也会调用 `subproject('gtk')`。如果 GStreamer 先解析，Meson 的全局子项目缓存可能被 monorepo 自己的 GTK 占用，仓库 wrap 中锁定的版本和补丁就会被绕开。先得到 `gtk4_dep` 后，后面的调用会复用同一个 GTK 子项目。

## CI：APK 构建、签名与发布

完整流程在 `.github/workflows/ci.yml` 的 `build-android` job 中。除了前面那三条 pixiewood 命令，CI 还要处理签名、ABI 分包和构建环境。

### 签名策略：release 与 debug 的严格分离

APK 必须签名后才能安装。CI 使用四个仓库 secret，keystore 以 base64 保存，构建时再解码：

```yaml
- name: Prepare signing keystore
  run: |
    # Fall back to a debug key when the release secrets are not set
    if [ -n "$LPC_KEYSTORE_BASE64" ] && [ -n "$LPC_KEYSTORE_PASSWORD" ] && ...; then
      echo "$LPC_KEYSTORE_BASE64" | base64 -d > "$RUNNER_TEMP/ks"
      # ……写入 GITHUB_ENV
    else
      keytool -genkeypair -keystore "$RUNNER_TEMP/ks" -alias androiddebugkey \
        -keyalg RSA -keysize 2048 -validity 365 \
        -storepass android -keypass android -dname "CN=Android Debug"
      # ……使用 debug 签名参数
    fi
```

普通分支可以回退到临时生成的 debug key，产物作为 CI artifact 用于测试。**tag 构建必须使用 release key**；只要四个 secret 有一个缺失，就直接失败，避免把 debug 签名的 APK 发布出去：

```yaml
# Releases must not ship debug-signed APKs
- name: Require signing secrets on tag builds
  if: github.ref_type == 'tag'
  run: |
    if [ -z "$LPC_KEYSTORE_BASE64" ] || [ -z "$LPC_KEYSTORE_PASSWORD" ] || [ -z "$LPC_KEY_ALIAS" ] || [ -z "$LPC_KEY_PASSWORD" ]; then
      echo "Tag builds must be signed with the release keystore, but the signing secrets are not set."
      exit 1
    fi
```

这项检查是在 0.50 开发期间补上的，tag 构建会逐一检查四个 secret。

### 三种 ABI 的 APK

签名和重命名在同一个步骤完成。版本字符串由 `git describe` 生成，脚本再循环处理三种 ABI：

```yaml
- name: Sign and rename APKs
  run: |
    set -euo pipefail
    VERSION="$(git describe --tags --abbrev=12 | sed 's/^v//;s/-/./g')"
    for ABI in arm64-v8a x86_64 universal; do
      APK_IN="$(find .pixiewood/android/app/build/outputs/apk -path "*${ABI}*" -name '*.apk' | head -1)"
      "${ANDROID_HOME}/build-tools/${ANDROID_SDKVER}/apksigner" sign \
        --ks "$KS" --ks-pass "pass:$KS_PASS" \
        --ks-key-alias "$KS_ALIAS" --key-pass "pass:$KS_ALIAS_PASS" \
        --out "live-photo-conv-${VERSION}-android-${ABI}.apk" \
        "$APK_IN"
    done
```

`arm64-v8a` 和 `x86_64` 是 pixiewood 清单中声明的两个架构，单架构包只带对应的 native 库；`universal` 包包含全部 ABI，体积更大，但不必区分设备。用户按设备选择其中一个即可。

### 构建加速与环境

这个 job 的超时设置为 180 分钟，因为 GTK 栈、GStreamer 和 FFmpeg 要针对两个架构交叉编译。编译缓存使用 `hendrikmuhs/ccache-action`（缓存键为 `android`，上限 2G），重复构建会快一些。pixiewood 还依赖一些 **Perl 模块**（如 `libglib-perl`、`libxml-libxml-perl`）；`gir1.2-appstream-1.0` 和 Java 17 用于解析 metainfo 及转换 SVG 图标。

## 固定依赖版本，保证可复现

为了让构建结果可复现，外部依赖都固定了版本：GTK、libadwaita 固定到具体 commit，gstreamer-full、gexiv2 固定到 release tag，pixiewood 工具链固定在 `android36` 分支，SDK 和 NDK 版本写进 CI 环境变量。以后重跑 CI 会使用同一套依赖，出现问题时也容易定位是哪次升级造成的。

其中两个嵌套依赖的原因比较特殊。`exiv2.wrap` 固定到 main 上**删除 CMake config 生成**的那个 commit，因为 pixiewood 的构建环境没有 cmake；它只作为 gexiv2android 的嵌套依赖使用，桌面构建仍然使用系统 exiv2。`expat.wrap` 则是因为上游没有 Meson 构建，仓库在 `subprojects/packagefiles/expat/` 放了一份手写的 meson.build，并明确列出源文件。为了避免源文件变动导致构建悄悄失效，这里固定 release tarball（2.7.5），升级时手动处理。

应用自身的版本号则完全自动生成：`git describe` 的结果经过 `configure_file` 写入 AppStream metainfo，再由 pixiewood 的 `sem121010` 算法转换成 `versionCode`；APK 文件名中的版本串也来自同一条命令。整条链路没有需要手工同步的数字。

## 运行时文件访问

上面这些是 Android 构建中最容易影响结果的部分：pixiewood 清单、交叉构建时的 VAPI 和 `--pkg`、C++ 运行时、`-Bsymbolic`、gst-full 的静态链接、子项目解析顺序，以及 CI 的签名和 ABI 分包。

APK 能构建出来只是第一步。运行时还要面对 SAF（Storage Access Framework）：系统文件选择器返回的 `content://` URI 没有本地路径，而核心库和 gexiv2 都需要路径。这个问题以及 staging 的实现放在[下一篇：SAF 文件访问](https://wszqkzqk.github.io/2026/08/25/live-photo-conv-android-saf/)。
