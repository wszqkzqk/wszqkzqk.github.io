---
layout:     post
title:      龙芯的Arch Linux移植工作流程
subtitle:   Loong Arch Linux软件包开发者维护工具设计
date:       2024-08-12
author:     wszqkzqk
header-img: img/bg-mountain-darken.webp
catalog:    true
tags:       系统配置 系统维护 开源软件 Linux archlinux 国产硬件 虚拟化
---

本文将介绍目前LoongArch的Arch Linux移植的**最小**维护架构（**不包括**CI工具）和参与[北京大学Linux俱乐部](https://github.com/lcpu-club)的Arch Linux龙芯移植工作的可能方式。

# 前言

Loong Arch Linux是Arch Linux的龙芯移植版本，目前龙芯Linux社区较普遍地认为，为龙芯Linux生态圈维护一个滚动更新的Arch Linux发行版具有重要意义，目前[北京大学Linux俱乐部](https://github.com/lcpu-club)计划接手维护。

由于社区维护力量较为有限，Loong Arch Linux将会尽可能地实现**上游化**，来减少维护工作量。

# 预备工作

## 基本条件

本文默认读者至少已经满足以下**条件中的一个**（建议读者预先大致阅读笔者的另一篇博客[在x86设备上跨架构构建LoongArch的Arch Linux软件包](https://wszqkzqk.github.io/2024/08/08/devtools-loong64/)）：

1. 拥有x86_64设备且可以在设备上运行x86_64的Arch Linux操作系统或者容器
2. 拥有原生的龙芯编译机器，或者可以运行LoongArch的QEMU System虚拟机

如果对本文中涉及的某些基本概念不熟悉，可以参考[ArchWiki](https://wiki.archlinux.org/)。

## 环境准备

### 文件系统

使用`devtools`构建软件包在每次构建时都会创建一个干净的chroot环境，该工具对Btrfs的快照进行了适配，创建新的chroot环境时会使用Btrfs的快照功能快速根据存放基本chroot环境的子卷创建新的chroot环境。因此，**建议使用Btrfs文件系统**。

### 导入PGP Key

Loong Arch Linux移植签名所用的PGP密钥并不在Arch Linux的`archlinux-keyring`密钥环中，因此需要导入签名密钥。

目前笔者打包了[北京大学Linux俱乐部](https://github.com/lcpu-club)Arch Linux用户组的密钥环[`archlinux-lcpu-keyring`](https://github.com/lcpu-club/archlinux-lcpu-keyring)。但这一软件包尚未上传到AUR，可以通过以下方式安装：

```bash
git clone https://github.com/lcpu-club/archlinux-lcpu-keyring.git
cd archlinux-lcpu-keyring
makepkg -si
```

### 安装[`devtools-loong64`](https://github.com/lcpu-club/devtools-loong)

笔者已经打包了`devtools-loong64`工具，并上传到了AUR，可以直接从AUR中安装：

```bash
paru -S devtools-loong64
```

对于在容器中运行x86_64 Arch Linux的用户，还需要参考笔者在另一篇博客中的[`binfmt_misc` FLAGS说明](https://wszqkzqk.github.io/2024/08/08/devtools-loong64/#binfmt_misc-flags说明仅针对在容器中运行x86-arch-linux的用户)一节进行设置。其他用户可以忽略。

# 维护仓库

* **TODO:** 补丁维护仓库结构仍可能会有微调

我们的补丁维护仓库位于[GitHub lcpu-club/loongarch-packages](https://github.com/lcpu-club/loongarch-packages)下，每个需要额外patch的软件包都有一个对应于包名的目录。该目录仅用于存放patch或龙芯特有的配置文件,**不直接存放`PKGBUILD`或上游软件源代码文件**。

* `loong.patch`是主要针对`PKGBUILD`的patch文件
  * 也可能包含其他Arch Linux**官方**软件包仓库**git跟踪**的文件
    * 具体是否可以包含Arch Linux**官方**软件包仓库中**git跟踪**的文件由移植包维护者自行决定
      * 有的维护者可能要求使用独立的patch并在makepkg中应用
      * 有的维护者可能允许直接编辑并一并导出到`loong.patch`
    * 但是**不能**包括新的补丁文件
  * 使用`git diff`导出
* 其他文件则可能是针对软件包的其他patch文件或者特别适用于龙芯的的配置文件

此外，仓库下还有`update_config`文件，用于存放需要更新`config.guess`和`config.sub`且不需要其他patch的软件包名。详见[后文](#特殊情况)。

# 工作流程

## 不需要patch的软件包构建及测试流程示例

这是最简单的情况，我们以`erofs-utils`软件包为例，展示如何构建和测试软件包。

### 获取软件包

由于Loong Arch Linux的构建需要遵循尽可能上游化的原则，我们的构建与移植需要先获取Arch Linux官方构建仓库。以`erofs-utils`软件包为例，我们可以通过以下命令获取：

```bash
pkgctl repo clone erofs-utils
```

如果报错`Please make sure you have the correct access rights and the repository exists.`，则需要指明使用`https`协议：

```bash
pkgctl repo clone --protocol=https erofs-utils
```

### 构建尝试

切换到克隆下来的示例软件包目录：

```bash
cd erofs-utils
```

一般来说，软件包的构建命令是`extra-loong64-build`。由于原软件包`PKGBUILD`是针对x86_64的，其`arch`数组并不包含`loong64`，未经修改并不能够直接用无参数的`extra-loong64-build`构建。虽然说修改`arch`数组也可以算是需要针对`PKGBUILD`的patch，但是我们默认在我们的移植中，所有`arch`字段不为`any`的软件包的`arch`字段都应该包含`loong64`，因此对`arch`的修改**不应当**出现在维护的patch中。

对此，我们可以有两种选择，一种是先修改`PKGBUILD`，将`loong64`添加到`arch`数组中，然后再使用`extra-loong64-build`构建（如果需要导出补丁则需要改回来）。

为了避免麻烦，我们还可以向`extra-loong64-build`传递参数来解决问题：

* `extra-loong64-build`参数组中在`--`后的参数会传递给`makechrootpkg`，而`makechrootpkg`参数组中在`--`后的参数会传递给`makepkg`
* `makepkg`的`-A`参数表示忽略`arch`字段不兼容的情况以便继续构建

因此，我们可以使用以下命令构建：

```bash
extra-loong64-build -- -- -A
```

* 如果需要`core-testing`和`extra-testing`中的包，请使用`extra-testing-loong64-build`。

#### 首次构建可能问题

首次运行时，程序会在`/var/lib/archbuild/`下创建目录`extra-loong64`，如果是Btrfs文件系统，会在`extra-loong64`下创建一个名为`root`的子卷，用于存放LoongArch Linux的基本chroot环境，在后续每次运行构建时，将会对这一子卷中的环境进行升级同步，并创建一个新的快照子卷进行构建。（其他文件系统则是创建普通目录、复制目录）

此时如果在同步数据库阶段就提示PGP签名错误，可能是因为没有导入PGP密钥，请自行检查软件包`archlinux-lcpu-keyring`是否[正常安装](#导入pgp-key)。如果仅有下载的部分软件包提示签名校验失败，可能是网络问题，重试即可。首次运行无论是否失败，均会在`/var/lib/archbuild/extra-loong64`下创建一个名为`root`的子卷，如果创建并没有成功，在重试时会提示该路径并非Arch Linux的chroot环境，此时请运行`extra-loong64-build -c`清理环境，或者手动删除`/var/lib/archbuild/extra-loong64`下的所有子卷以及`/var/lib/archbuild/extra-loong64`目录本身，然后再次运行。

#### 构建成功

构建成功后，在原构建仓库目录下会生成`*.pkg.tar.zst`软件包文件，即为构建成功的软件包；`*.log`为各项构建过程的日志。更详细的编译日志则是在`/var/lib/archbuild/extra-loong64/$USER/build/`下。

由于这种最简单的情况并不需要patch，这里不需要patch导出流程。

如果读者是北京大学Linux俱乐部Arch Linux用户组的成员且在`archlinux-lcpu-keyring`中有签名密钥，可以手动对软件包进行签名：

```bash
for file in *.pkg.tar.zst
do
  gpg --detach-sign --use-agent "$file"
done
```

软件包的测试可以使用龙芯物理机、`qemu-system-loongarch64`虚拟机、使用QEMU User Mode Emulation的龙芯容器等方式进行，具体方法不再赘述。

## 需要patch的软件包

本项目始终以上游化为目标，因此我们的软件包构建过程中，**尽量**不对软件包进行patch；对于共性问题，应当视具体情况提交到软件上游或者Arch Linux上游。但是，由于龙芯平台的特殊性，有些软件包可能不可避免地需要patch才能在龙芯平台上正常运行,而上游可能并不能够及时接收这些修复，此时我们不得不在我们的[补丁维护仓库](https://github.com/lcpu-club/loongarch-packages)中**暂时**维护patch。

### 构建测试流程

有额外patch的软件包仍然需要从上游拉取Arch Linux官方仓库，然后从我们的补丁维护仓库中获取patch。大致流程如下：

1. 将补丁维护仓库对应目录下所有文件复制到软件包目录下
2. 对`PKGBUILD`应用`loong.patch`

#### 特殊情况

* 本部分是为了简化维护而特别设计的，如果初学者不理解这部分内容，可以跳过，几篇文档都看完以后会理解的（）

部分软件包由于补丁内容非常一致、简单，而且有大量的软件包系统性地需要这些补丁，在这种时候，我们为了简洁与维护方便，并没有创建这些软件包的补丁维护目录。目前的这样特殊情况主要分为两种：

* 特殊情况1：`config.sub`和`config.guess`
  * 开发不活跃的软件`config.sub`和`config.guess`过旧，需要更新才能在龙芯平台上正常构建
  * **仅**需要更新`config.sub`和`config.guess`而**不用其他任何修改**就能成功构建
* 特殊情况2：使用`cargo fetch`的软件包的架构指定问题
  * `cargo fetch`在`PKGBUILD`中使用了硬编码的`x86_64`，需要替换为`uname -m`（`loongarch64`）
  * `cargo fetch`在`PKGBUILD`中使用了`$CARCH`（在本发行版是`loong64`），需要替换为`uname -m`（`loongarch64`）

因此对这两种特殊情况：

* 特殊情况1：如果没有对应的补丁，但软件包名在`update_config`文件中，需要对`PKGBUILD`进行修改
  * 需要对`config.sub`和`config.guess`进行更新
* 特殊情况2：如果没有对应的补丁，但软件包使用`cargo fetch`，需要将`$CARCH`替换为`uname -m`，并且将
  * 硬编码的`x86_64`也要替换为`uname -m`

这些过程可以手动使用命令完成，也可以封装一些脚本来实现：

```
#!/bin/bash

PATCH_GIT="https://github.com/lcpu-club/loongarch-packages.git"

if [ -z "$1" ]; then
  echo "Usage: get-loong64-pkg <package-name>"
  exit 1
fi

PACKAGE_NAME=$1
PATCH_REPO=${PATCH_REPO:-~/projects/loongarch-packages}

if [ -d "$PATCH_REPO" ]; then
  echo "Updating existing $PATCH_REPO..."
  git -C "$PATCH_REPO" fetch --all
  git -C "$PATCH_REPO" reset --hard origin/$(git -C "$PATCH_REPO" rev-parse --abbrev-ref HEAD)
else
  echo "Cloning PATCH_REPO to $PATCH_REPO..."
  mkdir -p "$(dirname "$PATCH_REPO")"
  git clone "$PATCH_GIT" "$PATCH_REPO"
fi

echo "Cloning official package repository..."
pkgctl repo clone --protocol=https "$PACKAGE_NAME"

PATCH_DIR="$PATCH_REPO/$PACKAGE_NAME"
if [ -d "$PATCH_DIR" ]; then
  echo "Copying patches..."
  cp "$PATCH_DIR"/* "$PACKAGE_NAME"
  cd "$PACKAGE_NAME"
  PATCH_FILE="loong.patch"
  if [ -f "$PATCH_FILE" ]; then
    echo "Applying patch $PATCH_FILE..."
    patch -p1 < "$PATCH_FILE"
  else
    echo "No 'loong.patch' found."
    exit 1
  fi

  echo "Done."
else
  echo "No patch of $PACKAGE_NAME found."
  if grep -Fxq "$PACKAGE_NAME" "$PATCH_REPO/update_config"; then
    sed -i '/^build()/,/configure/ {/^[[:space:]]*cd[[:space:]]\+/ { s/$/\n  for c_s in $(find -type f -name config.sub -o -name configure.sub); do cp -f \/usr\/share\/automake-1.1?\/config.sub "$c_s"; done\n  for c_g in $(find -type f -name config.guess -o -name configure.guess); do cp -f \/usr\/share\/automake-1.1?\/config.guess "$c_g"; done/; t;};}' "$PACKAGE_NAME/PKGBUILD"
    echo "Added config.sub and config.guess update to PKGBUILD."
  fi

  if grep -Eq 'cargo fetch.*(x86_64|\$CARCH)' "$PACKAGE_NAME/PKGBUILD"; then
    sed -i '/cargo fetch/s/\$CARCH/`uname -m`/' PKGBUILD
    sed -i '/cargo fetch/s/\x86_64/`uname -m`/' PKGBUILD
    echo "Automatically changed 'cargo fetch' to use `uname -m`."
  fi
  exit 1
fi
```

这个脚本可以将软件包的测试构建过程简化为：

```bash
./get-loong64-pkg <package-name>
cd <package-name>
extra-loong64-build -- -- -A
```

构建成功后的测试流程与不需要patch的软件包相同，这里不再赘述。

### patch导出流程

patch导出是应用patch流程的逆过程。对于需要patch适配的软件包，开发者在适配完成后，需要将适配的patch导出，并添加到我们的[补丁维护仓库](https://github.com/lcpu-club/loongarch-packages)中。

导出的内容包括针对`PKGBUILD`的patch和软件包的其他patch或特别适用于龙芯的配置文件。除了`loong.patch`外，其他需要用到的patch文件或者其他配置应当注意添加到`PKGBUILD`中的`source`数组中，并且更新好`PKGBUILD`中的哈希值，具体操作可以参考ArchWiki的[PKGBUILD条目](https://wiki.archlinux.org/title/PKGBUILD)。

此外其他文件应当尽可能地命名得更具体，以便于其他开发者理解。

如果开发者觉得手动的patch导出流程过于繁琐，可以尝试自己开发脚本来简化这个过程，并且欢迎分享给[北京大学Linux俱乐部](https://github.com/lcpu-club)。如果不想自己开发，可以使用笔者提供的简单脚本：

```
#!/bin/bash

if [[ "$1" == "--help" || "$1" == "-h" ]]; then
  echo "Usage: export-loong64-patches [package-path] [destination-directory]"
  exit 0
fi

if [[ $# -gt 2 ]]; then
  echo "Error: Too many arguments."
  exit 1
fi

PATCH_DIR="loong64-patches"
if [[ $# -eq 2 ]]; then
  cd "$1" || exit
  PATCH_DIR="$2"
elif [[ $# -eq 1 ]]; then
  PATCH_DIR="$1"
fi

mkdir -p "$PATCH_DIR"

echo "Exporting: loong.patch..."
git diff > "$PATCH_DIR/loong.patch"

sources=$(. PKGBUILD && echo "${source[@]}")

untracked_files=$(git ls-files --others --exclude-standard)

for file in $sources; do
  if [ -f "$file" ]; then
    for untracked_file in $untracked_files; do
      if [ "$file" == "$untracked_file" ]; then
        echo "Copying: $file..."
        cp "$file" "$PATCH_DIR"
        break
      fi
    done
  fi
done
```

这个脚本的逻辑是：

1. 将软件包目录下`git diff`的结果写入`loong.patch`
   * 对原有仓库git跟踪的内容只能修改`PKGBUILD`，因此`loong.patch`即为`PKGBUILD`的patch
2. 查找需要复制的其他文件
   * 需要复制的文件一定在`PKGUILD`的`source`数组中
   * 需要复制的文件一定在本地存在
   * 需要复制的文件一定不在Arch Linux官方软件包git仓库的跟踪文件中
   * 同时满足以上三个条件的文件一定需要复制，为充要条件

这个脚本可以将软件包的patch导出过程简化为：

```bash
./export-loong64-patches <package-path> <destination-directory>
```

软件包的patch提交流程与要求详见[补丁维护仓库自述文件](https://github.com/lcpu-club/loongarch-packages)。

注意：
* 如果patch文件**仅包含**对`config.sub`和`config.guess`的更新，不需要额外维护`loong.patch`，而是将包名添加到`update_config`文件中

### patch维护建议及示例

原则上，本项目的软件包应当尽可能地减少patch的使用，而是应当尽可能地将patch提交到软件上游或者Arch Linux上游。因此，我们的patch应当尽可能地少，保持简单、易于理解、易于维护。笔者将给出针对部分情况下减少patch维护的建议示例。

#### Bootstrap情况：构建失败但并不需要维护patch（新手如果觉得困难可以跳过这个部分）

某些时候，尤其是一些需要自举完成编译的软件包，在某些版本上可能会因为上游原因导致构建失败，可能暂时需要patch才能构建，但是当修复的软件包上传到软件源后，我们并**不需要长期维护**这个patch。笔者将以`vala`软件包为例，展示这种情况。

首先，我们需要获取软件包：

```bash
pkgctl repo clone --protocol=https vala
```

然后，我们可以尝试使用`extra-loong64-build`构建：

```bash
cd vala
extra-loong64-build -- -- -A
```

Vala是一个需要自举编译的软件包，目前（2024.08.14）在Loong Arch Linux软件源中的版本为`0.56.14`。如果我们尝试直接构建新版的`vala`软件包，可能会出现构建失败的情况，查看终端日志或者包目录下的`vala-*-loong64-build.log`文件可以发现类似如下的错误：

```log
valacodecontext.c: In function 'vala_code_context_get_gir_path':
valacodecontext.c:2538:27: error: assignment to 'gchar **' {aka 'char **'} from incompatible pointer type 'const gchar * const*' {aka 'const char * const*'} [-Wincompatible-pointer-types]
```

笔者同时也是Vala项目的贡献者，可以直接告诉大家，这个问题在`vala < 0.56.15`且`gcc >= 14`（如果用Clang编译则是`clang >= 16`）时会出现，这是因为Vala编译器生成的C代码中存在不兼容的指针赋值。在`gcc < 14`时，这一问题仅是一个警告，不会导致构建失败；但是在`gcc >= 14`时，GCC默认对这个问题使用了`-Werror`，因此会导致构建失败。

目前，Vala上游已经修复了（其实是Workaround）这个问题，在`0.56.15`版本及以后的Vala在编译代码时并不会因这一问题而失败，我们并**不需要维护**这个patch。然而，现存于仓库的`vala`软件包是`0.56.14`版本，在`gcc`升级到`14`之前完全可以正常使用，但是现在升级到`gcc 14`后`vala 0.56.14`产生的C代码则无法通过编译，也就**无法完成自举**，即使上游早已修复并发版，我们也仍然需要处理这个问题。

对于这种情况，我们可以在打包时在`PKGBUILD`的`build()`函数中添加一个`CFLAGS+=" -Wno-incompatible-pointer-types"`，这样可以在构建时忽略这个警告，再正常构建即可。

```bash
extra-loong64-build -- -- -A
```

更新到我们新构建的软件包后，以后的Vala软件构建就不会再出现这个问题，也就不需要维护这个patch。

Bootstrap问题相对而言比较特殊，而且就一般的“构建失败优先修改代码而非编译参数”的原则来说，这种情况的解决方式可能也并不是那么直观。这可能要求包维护者需要对上游情况有一定的了解，如果遇到问题，可以从上游的issues等内容中找到解决方案。

# 软件包的手动上传

参见[龙芯Arch Linux移植技巧 #软件包的手动上传](https://wszqkzqk.github.io/2024/08/22/loongarchlinux-port-tips/#软件包的手动上传)一节

# 更多阅读材料

* [ArchWiki](https://wiki.archlinux.org/)
* [Arch Linux Packaging Standards](https://wiki.archlinux.org/title/Arch_packaging_standards)
* [Arch RISC-V Port Wiki](https://github.com/felixonmars/archriscv-packages/wiki)
* [在x86设备上跨架构构建LoongArch的Arch Linux软件包](https://wszqkzqk.github.io/2024/08/08/devtools-loong64/)
* [Arch RISC-V Port Wiki - 我们的工作习惯](https://github.com/felixonmars/archriscv-packages/wiki/%E6%88%91%E4%BB%AC%E7%9A%84%E5%B7%A5%E4%BD%9C%E4%B9%A0%E6%83%AF)
* [Arch RISC-V Port Wiki - 完全新人指南](https://github.com/felixonmars/archriscv-packages/wiki/%E5%AE%8C%E5%85%A8%E6%96%B0%E4%BA%BA%E6%8C%87%E5%8D%97)
* [北京大学Linux俱乐部Arch Linux for Loongarch64项目维护网页](https://loongarchlinux.lcpu.dev/)
* [北京大学Linux俱乐部Arch Linux for Loongarch64项目 - 构建状态列表](https://loongarchlinux.lcpu.dev/status)
* [原Loong Arch Linux项目](https://github.com/loongarchlinux)
* 可能的补丁参考源：[AOSC Code Tracking Project](https://github.com/AOSC-Tracking)
* 可能的补丁参考源：[Gentoo/Loongson Support Overlay](https://github.com/xen0n/loongson-overlay)
* [龙芯Arch Linux移植技巧 by wszqkzqk](https://wszqkzqk.github.io/2024/08/22/loongarchlinux-port-tips/)
