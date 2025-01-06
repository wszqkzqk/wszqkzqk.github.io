---
layout:     post
title:      为龙架构的Arch Linux构建Chromium与Electron
subtitle:   借助社区力量维护龙架构的Arch Linux软件生态
date:       2025-01-04
author:     wszqkzqk
header-img: img/bg-mountain-darken.webp
catalog:    true
tags:       开源软件 Linux archlinux 国产硬件 龙芯 LoongArchLinux Chromium Electron
---

## 前言

Chromium是一款开源的网页浏览器，是Google Chrome的开源版本。Electron是一个基于Chromium和Node.js的开源框架，用于构建跨平台的桌面应用程序。这两个软件包在Linux用户中非常受欢迎，但是在龙芯架构上的构建并不容易。

目前，清华的[Chen Jiajie](https://github.com/jiegec)维护了适用于龙架构的[Chromium补丁集](https://github.com/AOSC-Dev/chromium-loongarch64)。字节跳动的[darkyzhou](https://github.com/darkyzhou)则基于Chen Jiajie的工作，维护了适用于龙架构的[Electron修复](https://github.com/darkyzhou/electron-loong64)。

然而，这些内容主要考虑的是针对AOSC发行版或者单独发行的Electron软件包，可能有特定的路径配置，或者复杂的构建环境要求，不能够直接适用于Arch Linux的构建流程。本文将介绍如何利用好这些社区力量，为龙架构的Arch Linux修复并构建Chromium与Electron。

## Chromium

我们可以到[Chen Jiajie的Chromium补丁集](https://github.com/AOSC-Dev/chromium-loongarch64)仓库中找到所需的Chromium版本的`tag`，在`chromium`目录中获取`chromium-<version>.diff`文件。

### 清理

为了在Arch Linux上构建Chromium，我们需要对这个`diff`文件进行适当的修改。这一补丁可能会对某些上游指定的路径修改为AOSC的风格，我们应当将相关的修改全部移除。对于这些文件，我们应当移除修改：

```
build/config/clang/BUILD.gn
build/nocompile.gni
build/rust/rust_bindgen.gni
build/rust/rust_target.gni
```

### 额外的修改

此外，Arch Linux对于Chromium构建中的compiler-rt的路径也有修改，以适配比`clang >= 18`。而我们也需要在同样的构建文件中的相同位置进行修改，增加对龙架构的支持。我们可以再增加一个补丁`compiler-rt-adjust-paths-loong64.patch`，并在应用时选择我们的补丁替换Arch Linux的`compiler-rt-adjust-paths.patch`：

```
diff --git a/build/config/clang/BUILD.gn b/build/config/clang/BUILD.gn
index 890bf91c43e40..888804b675c7d 100644
--- a/build/config/clang/BUILD.gn
+++ b/build/config/clang/BUILD.gn
@@ -164,16 +164,17 @@ template("clang_lib") {
         _dir = "darwin"
       } else if (is_linux || is_chromeos) {
         if (current_cpu == "x64") {
-          _dir = "x86_64-unknown-linux-gnu"
+          _suffix = "-x86_64"
         } else if (current_cpu == "x86") {
-          _dir = "i386-unknown-linux-gnu"
-        } else if (current_cpu == "arm") {
-          _dir = "armv7-unknown-linux-gnueabihf"
+          _suffix = "-i386"
         } else if (current_cpu == "arm64") {
-          _dir = "aarch64-unknown-linux-gnu"
+          _suffix = "-aarch64"
+        } else if (current_cpu == "loong64") {
+          _suffix = "-loongarch64"
         } else {
           assert(false)  # Unhandled cpu type
         }
+        _dir = "linux"
       } else if (is_fuchsia) {
         if (current_cpu == "x64") {
           _dir = "x86_64-unknown-fuchsia"
```

### 应用补丁

随后，将这些补丁文件放置在`PKGBUILD`文件所在目录，修改`PKGBUILD`文件，并使用`+=`的方式添加到`source`和checksums数组中。例如：

```bash
source+=("chromium-loong64-support.patch"
         "compiler-rt-adjust-paths-loong64.patch")
sha256sums+=('xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
             'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
```

然后别忘了在`prepare()`函数中应用这些补丁。例如，将Arch Linux的`compiler-rt-adjust-paths.patch`替换为我们的`compiler-rt-adjust-paths-loong64.patch`：

```bash
  patch -Np1 -i "${srcdir}/compiler-rt-adjust-paths-loong64.patch"
```

应用龙架构的修复补丁：

```bash
  patch -Np1 -i "${srcdir}/chromium-loong64-support.patch"
```

对于Chromium这样巨大的二进制软件包，还需要在`prepare()`函数中设定`code model`为`medium`。（参见[移植修复指引中的相关内容](https://wszqkzqk.github.io/2024/08/22/loongarchlinux-port-tips/#relocation-r_larch_b26-out-of-rangerelocation-r_larch_b26-overflow%E9%94%99%E8%AF%AF)）

```bash
  # Add ` -mcmodel=medium` to CFLAGS etc.
  # to avoid `relocation R_LARCH_B26 overflow`
  export CFLAGS="${CFLAGS} -mcmodel=medium"
  export CXXFLAGS="${CXXFLAGS} -mcmodel=medium"
```

* 自Rust 1.83起，Rust的Code Model默认为`medium`，因此不需要再额外设置`export RUSTFLAGS="${RUSTFLAGS} -C code-model=medium"`

一切就绪后，我们可以使用`devtools-loong64`构建Chromium了。

## Electron

### 对于社区已有维护补丁的版本

首先在[darkyzhou的Electron修复仓库](https://github.com/darkyzhou/electron-loong64)中检查是否有适用于我们所需版本的修复补丁。如果有，我们尽可能基于这些补丁进行修改。

#### 清理并修改darkyzhou的补丁

我们需要先通过`git`获取Electron的源码，并`checkout`到我们所需的版本：

```bash
git clone https://github.com/electron/electron.git
cd electron
git checkout <version>
```

然后，从darkyzhou的仓库中找到对应版本的`tag`，获取修复补丁并应用：

```bash
patch -Np1 -i /path/to/electron.patch
```

应用后，使用`git status`可以查看情况：

```log
HEAD detached at v32.2.7
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
        modified:   DEPS
        modified:   build/args/ffmpeg.gn
        modified:   build/args/release.gn
        modified:   js2c_toolchain.gni
        modified:   patches/boringssl/.patches
        modified:   patches/chromium/.patches
        modified:   patches/config.json
        modified:   patches/devtools_frontend/.patches
        modified:   patches/ffmpeg/.patches
        modified:   patches/skia/.patches
        modified:   shell/browser/extensions/api/runtime/electron_runtime_api_delegate.cc

Untracked files:
  (use "git add <file>..." to include in what will be committed)
        patches/boringssl/loong64_support.patch
        patches/breakpad/
        patches/chromium/loong64_support.patch
        patches/devtools_frontend/loong64_support.patch
        patches/devtools_frontend/patch_esbuild_version_for_loong64.patch
        patches/ffmpeg/loong64_support.patch
        patches/skia/loong64_support.patch
        patches/swiftshader/
```

也可以使用`git diff`更详细地查看修改的具体内容。我们可以注意到，darkyzhou的补丁中包含了对`DEPS`中Chromium版本依赖的修改，以及对`build`目录下构建工具信息的指定。此外，由于Arch Linux的PKGBUILD仅适用于host构建，在`js2c_toolchain.gni`中的`toolchain`指定也没有必要。我们需要将这些修改全部移除，以便适配Arch Linux的构建环境。使用`git restore`命令：

```bash
git restore DEPS build js2c_toolchain.gni
```

由于darkyzhou的补丁中同样在Chromium构建中修改并使用了AOSC风格的路径，我们需要将这些修改全部移除。与Chromium修复的[清理](#清理)环节类似，我们需要编辑`patches/chromium/loong64_support.patch`文件，移除对这些文件的修改：

```
build/config/clang/BUILD.gn
build/nocompile.gni
build/rust/rust_bindgen.gni
build/rust/rust_target.gni
```

#### 导出补丁

由于我们向Electron的git仓库新增了未跟踪的文件，我们还需要`git add`这些文件，并使用`git diff`导出我们的补丁：

```bash
git add .
git diff HEAD > /path/to/electron-add-loong64-support.patch
```

#### 适配`depot_tools`

除此之外，我们还需要对`depot_tools`进行适配，在`cipd`文件中添加对`loong64`的支持：

```
diff --git a/cipd b/cipd
index 7f9cca27..3acbe4ad 100755
--- a/cipd
+++ b/cipd
@@ -80,6 +80,9 @@ if [ -z $ARCH ]; then
     riscv64)
       ARCH=riscv64
       ;;
+    loongarch64)
+      ARCH=loong64
+      ;;
     *)
       >&2 echo "UNKNOWN Machine architecture: ${UNAME}"
       exit 1
```

这一补丁需要在合并子模块源码前就**预先应用**，否则在合并时就会报错。需要注意的是，对**Electron本体**的修改也应当在合并子模块源码前就**预先应用**。

```bash
  # Apply in advance to so that makepkg-source-roller.py will not throw error
  patch -p1 -d chromium-mirror_third_party_depot_tools -i "${srcdir}/depot_tools-loong64-support.patch"
  patch -p1 -d electron -i "${srcdir}/electron-add-loong64-support.patch"
```

#### 获取`esbuild`的二进制文件

由于Google的fork中并没有发布`esbuild`的二进制文件，我们无法用Arch Linux上游使用的`makepkg-source-roller.py`脚本来获取`esbuild`的二进制文件。而系统的`esbuild`版本过新，也不适合用于构建Electron。我们可以通过`npm`下载版本最接近的`esbuild`二进制文件，然后将其复制到对应的位置。

首先，修改Arch Linux上游的`makepkg-source-roller.py`脚本，根据[项目的约定原则](https://wszqkzqk.github.io/2024/08/12/loong-tools-design/#%E7%BB%B4%E6%8A%A4%E4%BB%93%E5%BA%93)，对于Arch Linux构建文件仓库中跟踪的PKGBUILD以外的文件，我们一般不建议直接修改以免引发checksum变动，使补丁出现冲突。我们可以使用`+=`向`source`数组及checksum数组中添加我们对`makepkg-source-roller.py`的补丁`makepkg-source-roller.py.diff`，禁止使用Arch Linux的方式直接获取`esbuild`二进制文件：

```
@@ -400,7 +400,9 @@ if __name__ == "__main__":
                     True,
                 ),  # only for new electron versions (probably >= 29)
                 # The esbuild version 0.14.13 is not compatible with the system one
-                ("src/third_party/devtools-frontend/src/third_party/esbuild", False),
+                # Not suitable for loong64 since the package is missing
+                # Need another workaround
+                #("src/third_party/devtools-frontend/src/third_party/esbuild", False),
             ],
         )
         # gcs dependencies are usually binary blobs. They are not handled yet.
```

对`source`数组中的文件应用补丁，由于Arch Linux的`source`中的文件将会以软链接的形式存在于`src`目录下，这里的补丁应用相对麻烦一点，需要先复制，再应用，最后替换：

```bash
  # Patching makepkg-source-roller.py
  cp "${srcdir}/makepkg-source-roller.py" "makepkg-source-roller-new.py"
  patch "makepkg-source-roller-new.py" -i "${srcdir}/makepkg-source-roller.py.diff"
  mv -f "makepkg-source-roller-new.py" "makepkg-source-roller.py"
```

然后，我们可以使用`npm`下载`esbuild`版本最接近的二进制文件：

```bash
npm install @esbuild/linux-loong64@0.14.54
```

最后，在子模块源代码**合并完成后**，将`esbuild`二进制文件复制到对应的位置：

```bash
  # Add esbuild binary manually
  mkdir -p src/third_party/devtools-frontend/src/third_party/esbuild
  cp node_modules/@esbuild/linux-loong64/bin/esbuild src/third_party/devtools-frontend/src/third_party/esbuild/esbuild
```

由于之前darkyzhou的补丁中已经包含了对`esbuild`以来版本的修改（指定为了0.14.54），我们无需再对`devtools_frontend`中指定的版本进行修改。

#### 路径适配的修改

与Chromium类似，我们也需要用`compiler-rt-adjust-paths-loong64.patch`替换Arch Linux的`compiler-rt-adjust-paths.patch`（参见Chromium的[相关部分](#额外的修改)）。

然后，参考Chromium的[应用补丁环节](#应用补丁)，将所有补丁文件放置在`PKGBUILD`文件所在目录，修改`PKGBUILD`文件，补充添加、应用补丁的步骤即可。

### 对于没有维护补丁的版本

如果darkyzhou的仓库中没有适用于我们所需版本的修复补丁，我们可以尝试自行找到该electron版本对应的Chromium版本，然后移植[Chen Jiajie的Chromium补丁](https://github.com/AOSC-Dev/chromium-loongarch64)进行修复。

由于Chen Jiajie所维护的补丁是针对Chromium的tarball的，将对Chromium主仓库以及子模块的修改都包含在一个`diff`文件中。我们除了需要对这个`diff`文件进行适当的清理、修改外，还需要将这个`diff`文件根据子模块拆分成多个文件。我们在获取子模块的源码后，首先应当使用`git checkout`命令切换到对应的版本，再将我们拆分好的补丁文件应用于相应的子模块，并逐一解决冲突。完成后，再使用`git diff`导出我们的补丁。

接下来，我们再将最终的补丁文件放到Electron的`patches/<submodule-name>`目录下，并在`patches/<submodule-name>/.patches`文件中添加这一额外指定的补丁文件的文件名。

以上适配工作完成后，参考[前一节](#对于社区已有维护补丁的版本)的步骤，应用这些补丁，构建Electron。

## 结语

通过这样的方式，我们可以利用社区力量，维护龙架构的Arch Linux软件生态。这样的方式不仅可以让我们更好地适配Arch Linux的构建方式，也可以让我们更好地利用社区资源，减少重复劳动，提高效率。

最后，感谢Chen Jiajie和darkyzhou的工作，感谢其他开源社区的支持，让我们一起维护龙架构的软件生态，让我们的龙架构更好地发展！
