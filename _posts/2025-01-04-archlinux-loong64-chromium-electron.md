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

此外，Arch Linux对于Chromium构建中的compiler-rt的路径也有修改，以适配`clang > 16`。而我们也需要在同样的构建文件中的相同位置进行修改，增加对龙架构的支持。我们可以再增加一个补丁`compiler-rt-adjust-paths-loong64.patch`，并在应用时选择我们的补丁替换Arch Linux的`compiler-rt-adjust-paths.patch`：

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

* 自`devtools-loong64` `1.3.1.patch2-1`起（2025.1.21），我们已经在默认的`makepkg.conf`中向`CFLAGS`和`CXXFLAGS`添加了`-mcmodel=medium`，因此**理论上一般不需要再额外设置**Code Model。

以下内容**已失效，**仅存档供查看：

> 对于Chromium这样巨大的二进制软件包，还需要在`prepare()`函数中设定`code model`为`medium`。（参见[移植修复指引中的相关内容](https://wszqkzqk.github.io/2024/08/22/loongarchlinux-port-tips/#relocation-r_larch_b26-out-of-rangerelocation-r_larch_b26-overflow%E9%94%99%E8%AF%AF)）
>
> ```bash
>   # Add ` -mcmodel=medium` to CFLAGS etc.
>   # to avoid `relocation R_LARCH_B26 overflow`
>   export CFLAGS="${CFLAGS} -mcmodel=medium"
>   export CXXFLAGS="${CXXFLAGS} -mcmodel=medium"
> ```
>
> * 自Rust 1.83起，Rust的Code Model默认为`medium`，因此不需要再额外设置`export RUSTFLAGS="${RUSTFLAGS} -C code-model=medium"`

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

此外，有时候我们所使用的Chromium版本可能与darkyzhou的补丁中指定的版本不同，导致补丁在应用的时候可能会出现冲突。这时，我们应当先在Chromium中解决这些冲突，再导出我们的Chromium补丁以替换darkyzhou的Chromium补丁`patches/chromium/loong64_support.patch`。其他子模块如果出现冲突，也应当类似处理。

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

#### 路径适配的修改

与Chromium类似，我们也需要用`compiler-rt-adjust-paths-loong64.patch`替换Arch Linux的`compiler-rt-adjust-paths.patch`（参见Chromium的[相关部分](#额外的修改)）。

然后，参考Chromium的[应用补丁环节](#应用补丁)，将所有补丁文件放置在`PKGBUILD`文件所在目录，修改`PKGBUILD`文件，补充添加、应用补丁的步骤即可。

#### 评价

darkyzhou的Electron修复补丁是“patch了Electron的patch过程”，更类似“自己维护一个上游”，但是却和Arch Linux中的Electron本地补丁的应用方式有较大不同。虽然看起来基于darkyzhou的补丁清理会比较方便，但是实际上，这种维护模式下维护的补丁很容易出现冲突，甚至**小版本升级都可能需要重新适配**。因此，笔者更推荐下文基于Chromium的补丁进行适配的方式。

### 对于没有维护补丁的版本

#### 使用Chromium的补丁（推荐）

如果darkyzhou的仓库中没有适用于我们所需版本的修复补丁，我们可以尝试自行找到该electron版本对应的Chromium版本，然后移植[Chen Jiajie的Chromium补丁](https://github.com/AOSC-Dev/chromium-loongarch64)进行修复。（注意：即使darkyzhou维护了补丁集，也可能是未验证的，不一定能保证成功构建或者构建后可以使用）其实这种方式的工作量并不比修改darkyzhou的补丁大，某种程度上讲，这种方式更加简洁，而且更符合**Arch Linux上游的补丁应用方式**。

需要注意的是，Chen Jiajie的补丁是基于完整的Chromium源码的，如果要直接应用，需要等Arch Linux的`makepkg-source-roller.py`脚本整合Chromium的源码后再进行操作（应当放在Arch Linux上游跑完`src/electron/script/apply_all_patches.py`后的`echo "Applying local patches..."`段中，和上游的其他local patch一起应用，实践上**建议放在所有Arch Linux上游的local patch之后应用**）。

我们需要事先按照之前介绍的方法对补丁进行[**清理**](#清理)。这里应用的Chromium补丁还需要预先**解决好冲突**，尤其是当Chen Jiajie的补丁针对的Chromium版本与我们的不完全对应的时候。

除了Chromium的补丁，我们还需要对`electron_runtime_api_delegate.cc`文件进行适配，增加对`loong64`的支持，例如（对`electron`目录应用）：

```
--- a/shell/browser/extensions/api/runtime/electron_runtime_api_delegate.cc
+++ b/shell/browser/extensions/api/runtime/electron_runtime_api_delegate.cc
@@ -67,6 +67,8 @@ bool ElectronRuntimeAPIDelegate::GetPlatformInfo(PlatformInfo* info) {
     info->arch = extensions::api::runtime::PlatformArch::kX86_32;
   } else if (strcmp(arch, "x64") == 0) {
     info->arch = extensions::api::runtime::PlatformArch::kX86_64;
+  } else if (strcmp(arch, "loong64") == 0) {
+    info->arch = extensions::api::runtime::PlatformArch::kLoong64;
   } else {
     NOTREACHED();
   }
@@ -78,6 +80,8 @@ bool ElectronRuntimeAPIDelegate::GetPlatformInfo(PlatformInfo* info) {
     info->nacl_arch = extensions::api::runtime::PlatformNaclArch::kX86_32;
   } else if (strcmp(nacl_arch, "x86-64") == 0) {
     info->nacl_arch = extensions::api::runtime::PlatformNaclArch::kX86_64;
+  } else if (strcmp(nacl_arch, "loong64") == 0) {
+    info->nacl_arch = extensions::api::runtime::PlatformNaclArch::kLoong64;
   } else {
     NOTREACHED();
   }
```

此外，我们**至少**还需要完成上一节提到的[适配`depot_tools`](#适配depot_tools)、[获取`esbuild`的二进制文件](#获取esbuild的二进制文件)、[路径适配的修改](#路径适配的修改)这些工作并应用才能完成适配。

## 结语

当然，**很可能单纯按照本文的内容来修复是不够的**，我们仍然可能**不可避免地遇到各种各样的其他问题**（Chen Jiajie和darkyzhou的补丁可能有没有覆盖的代码），这时候我们需要根据错误信息，充分检索，具体问题具体分析，逐一解决。（注意在**上游有相关修复**的时候应该优先**移植**上游的修复到我们的版本，如果没有，我们才使用自己的修复，尤其是潜在的可能因为**工具链变化等原因出现的架构无关问题**）

通过共用/参考补丁内容的方式，我们可以利用社区力量，维护龙架构的Arch Linux软件生态。这样的方式不仅可以让我们更好地适配Arch Linux的构建方式，也可以让我们更好地利用社区资源，减少重复劳动，提高效率。

最后，感谢Chen Jiajie和darkyzhou的工作，感谢其他开源社区的支持，让我们一起维护龙架构的软件生态，让我们的龙架构更好地发展！

## 参考链接

* [Chromium 131的适配补丁集](https://github.com/lcpu-club/loongarch-packages/tree/13e278dc0dbb10f593af6b40871e8a3cd8166f47/chromium)
* [Electron 32的适配补丁集（早期，基于darkyzhou的Electron补丁）](https://github.com/lcpu-club/loongarch-packages/tree/d7e71d63b8cfd5d4cf00e07693a59ccf583d9bc1/electron32)
* [Electron 32的适配补丁集（后期，基于Chromium的补丁）](https://github.com/lcpu-club/loongarch-packages/tree/07923d160122f37c42dd776b50cdbd30dbf03ae7/electron32)
* [Electron 30的适配：PR #401 (Merged)](https://github.com/lcpu-club/loongarch-packages/pull/401)，可以参考这个PR的内容和曲折的修复过程（包括PR的diff和comment）
* [Electron 33的适配：PR #400 (Merged)](https://github.com/lcpu-club/loongarch-packages/pull/400)，可以参考这个PR的内容和曲折的修复过程（包括PR的diff和comment）
