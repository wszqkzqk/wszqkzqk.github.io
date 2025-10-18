---
layout:     post
title:      Arch Linux for Loong64维护中可能用到Bootstrap构建方法
subtitle:   面向新人的Bootstrap构建基础指引
date:       2024-11-20
author:     wszqkzqk
header-img: img/bg-sunrise.webp
catalog:    true
tags:       系统配置 系统维护 开源软件 Linux archlinux 国产硬件 虚拟化 龙芯 LoongArchLinux
---

## 前言

有时候某些软件的构建往往会依赖自身进行编译，这时候就需要使用Bootstrap构建方法。

本教程仅简单列举一些新人相对容易理解的、常见的Bootstrap构建方法，对于复杂的问题，可能需要额外的具体研究。

## 注意事项

首次通过“不干净”的方法生成的软件包**请勿上传**，请将这一文件[添加到本地仓库](https://wszqkzqk.github.io/2024/09/19/build-order-local-repo/)，再使用**官方的构建文件**（或者基于官方构建文件应用了我们**补丁集中的补丁**的），进行**正式的打包**，然后上传，保证构建的可复现性。

## 上游给出Bootstrap构建方法的情况

某些软件包官方会给出Bootstrap构建方法，因此我们需要注意查看**官方文档**中是否有相关说明。

### 例子：`vala`

Vala是一种为GObject设计的高级编程语言，Vala编译器会将Vala代码编译成C代码，然后再编译成二进制文件。Vala编译器本身也是用Vala语言编写的，因此在编译Vala编译器时，我们需要使用Bootstrap构建方法。Vala官方给出了Bootstrap构建方法：Vala官方会直接发布包含Vala代码及其生成的中间C代码的tarball，我们只需要解压这个tarball，然后再禁用Vala编译，指定使用C编译器编译即可。

因此，我们只需要对Arch Linux官方的`vala`软件包的PKGBUILD文件进行修改，得到`vala-bootstrap`软件包的PKGBUILD文件即可。

* 修改包名并增加`provides`字段
* 修改`source`字段，使用Vala官方发布的tarball替代git源码
* 去掉对`vala`的依赖
* 根据Vala的Bootstrap文档，在构建时指定`VALAC=/no-valac`

```bash
_pkgname=vala
pkgname="$_pkgname-bootstrap"
pkgver=0.56.17
pkgrel=1
pkgdesc='Compiler for the GObject type system'
url='https://wiki.gnome.org/Projects/Vala'
arch=(x86_64)
license=(LGPL-2.1-or-later)
depends=(
  gcc
  glib2
  glibc
  graphviz
  gtk-doc
  pkg-config
  ttf-font
)
makedepends=(
  autoconf-archive
  git
  help2man
  libxslt
)
checkdepends=(
  dbus
  gobject-introspection
  libx11
)
provides=(
  libvala{,doc}-${pkgver%.*}.so
  valadoc
  $_pkgname
)
conflicts=(valadoc)
replaces=(valadoc)
source=("http://download.gnome.org/sources/vala/${pkgver%.*}/vala-$pkgver.tar.xz")
b2sums=('c4b8d5b7c810893728f82d2cbbf2f0dd70ad17bd4eeb323ab5d31d99f37b5a5508b7d2447f0249f3a925013d7110bb6f145b32c833b990b15f18d9949035293f')

build() {
  cd "vala-$pkgver"
  VALAC=/no-valac ./configure --prefix=/usr
  sed -i -e 's/ -shared / -Wl,-O1,--as-needed\0/g' libtool
  make
}

check() {
  cd "vala-$pkgver"
  make check
}

package() {
  cd "vala-$pkgver"
  make DESTDIR="$pkgdir" install
}
```

这样的`vala-bootstrap`软件包构建完成后，我们可以将其添加到本地仓库，然后使用`vala-bootstrap`软件包构建`vala`软件包。最后，我们再将得到的干净的`vala`软件包上传。

## 利用其他发行版的二进制包构建

如果某个软件包在Loong Arch Linux上还没有，但是**其他支持LoongArch的发行版**上已经构建好了**二进制包**，我们可以尝试使用其他发行版的二进制包构建。我们同样可以构建一个`-bootstrap`软件包，然后在`build()`或者`package()`函数中，使用`bsdtar`解压其他发行版的二进制包，直接安装到`$pkgdir`中。（同样需要注意添加`provides`字段）

这一方法容易遇到一些问题：

* 不同发行版的路径结构可能不同，有时候可能需要手动调整
  * 比如`/usr/lib`和`/usr/lib64`的区别
  * 比如`/usr/bin`和`/usr/local/bin`的区别
* 不同发行版的二进制包可能有不同的依赖
  * 可能会遇到链接到不存在的库的问题
    * 包括依赖缺失或者soname不同
  * 需要手动调整或者导入依赖包

### 例子：`ghc`

* 2025年10月更新

GHC是Haskell语言的主要编译器，它的自举是出了名的复杂。此前，Arch Linux官方出于种种原因，此前GHC的版本一直被锁定在了9.4.4，而GHC直到9.6才开始支持LoongArch，因此我们一直没有构建。直到最近，Arch Linux官方才将GHC升级到了9.6.6版本，Arch Linux for Loong64也终于可以构建GHC了。

好在，也正是因为Arch Linux的GHC升级较慢，在我们移植之时，Debian就早已构建好了GHC 9.6.6的二进制包，因此我们可以将Debian的GHC二进制包作为基础，构建一个`ghc-bootstrap`软件包，然后再使用这个软件包构建干净的`ghc`软件包。

#### 基础自举依赖包

编写`-botstrap`系列软件包的`PKGBUILD`文件，用于将`.deb`文件解包并重新打包成Arch Linux的软件包。由于自举可以认为是一次性的，我们并不用太在乎这几个`PKGBUILD`文件的规范性和可维护性。

我们需要集成`ghc`的构建依赖，从Debian中获取，构建包括`ghc-bootstrap`、`alex-bootstrap`、`happy-bootstrap`、`haskell-hscolour-bootstrap`、`haskell-hadrian-bootstrap`这几个软件包。

* `ghc-bootstrap`的PKGBUILD文件。注意Debian的GHC依赖了LLVM18。此外，Debian的GHC并没有拆包，都放到了一个`.deb`文件中，因此我们只需要解压这个`.deb`文件即可，并在`provides`中按照Arch Linux的情况列出所有GHC提供的组件。

```bash
shopt -s extglob

pkgbase=ghc-bootstrap
pkgname=(ghc-bootstrap)
pkgver=9.6.6
pkgrel=1
pkgdesc='The Glasgow Haskell Compiler'
arch=('x86_64')
url='https://www.haskell.org/ghc/'
license=('custom')
source=("https://snapshot.debian.org/archive/debian-ports/20250217T194911Z/pool-loong64/main/g/ghc/ghc_9.6.6-4_loong64.deb"
        ghc-rebuild-doc-index.hook ghc-register.hook ghc-unregister.hook)
sha512sums=('a92d46ac343718d36e9ce59db549e236c51423bb2835f103045a3cfbb02be0def75f3e38176c41baba9fb8be00d34a45a7795f0ba7b321cebde4521b66585df6'
            'd69e5222d1169c4224a2b69a13e57fdd574cb1b5932b15f4bc6c7d269a9658dd87acb1be81f52fbcf3cb64f96978b9943d10cee2c21bff0565aaa93a5d35fcae'
            '5f659651d8e562a4dcaae0f821d272d6e9c648b645b1d6ab1af61e4dd690dc5a4b9c6846753b7f935963f001bb1ae1f40cd77731b71ef5a8dbc079a360aa3f8f'
            '3bdbd05c4a2c4fce4adf6802ff99b1088bdfad63da9ebfc470af9e271c3dd796f86fba1cf319d8f4078054d85c6d9e6a01f79994559f24cc77ee1a25724af2e6')
depends=('gcc' 'gmp' 'libffi' 'numactl' 'perl' 'llvm18')
provides=(
  'haskell-array=0.5.4.0'
  'haskell-base=4.17.2.1'
  'haskell-binary=0.8.9.1'
  'haskell-bytestring=0.11.5.3'
  'haskell-cabal=3.8.1.0'
  'haskell-cabal-syntax=3.8.1.0'
  'haskell-containers=0.6.7'
  'haskell-deepseq=1.4.8.0'
  'haskell-directory=1.3.7.1'
  'haskell-exceptions=0.10.5'
  'haskell-filepath=1.4.2.2'
  'haskell-ghc-bignum=1.3'
  'haskell-ghc-boot=9.4.8'
  'haskell-ghc-boot-th=9.4.8'
  'haskell-ghc-compact=0.1.0.0'
  'haskell-ghc-heap=9.4.8'
  'haskell-ghc-prim=0.9.1'
  'haskell-haddock=2.27.0'
  'haskell-haskeline=0.8.2'
  'haskell-hpc=0.6.1.0'
  'haskell-hp2ps=0.1'
  'haskell-hpc-bin=0.68'
  'haskell-hsc2hs=0.68.8'
  'haskell-integer-gmp=1.1'
  'haskell-libiserv=9.4.8'
  'haskell-mtl=2.2.2'
  'haskell-parsec=3.1.16.1'
  'haskell-pretty=1.1.3.6'
  'haskell-process=1.6.18.0'
  'haskell-stm=2.5.1.0'
  'haskell-template-haskell=2.19.0.0'
  'haskell-terminfo=0.4.1.5'
  'haskell-text=2.0.2'
  'haskell-time=1.12.2'
  'haskell-transformers=0.5.6.2'
  'haskell-unix=2.7.3'
  'haskell-xhtml=3000.2.2.1'
  'haskell-ghc-pkg=9.4.8'
  "haskell-ghc=$pkgver"
  "haskell-ghci=$pkgver"
  ghc
  ghc-libs
  ghc-static
)
replaces=(
  'haskell-array'
  'haskell-base'
  'haskell-binary'
  'haskell-bytestring'
  'haskell-cabal'
  'haskell-cabal-syntax'
  'haskell-containers'
  'haskell-deepseq'
  'haskell-directory'
  'haskell-exceptions'
  'haskell-filepath'
  'haskell-ghc-bignum'
  'haskell-ghc-boot'
  'haskell-ghc-boot-th'
  'haskell-ghc-compact'
  'haskell-ghc-heap'
  'haskell-ghci'
  'haskell-ghc-prim'
  'haskell-haddock'
  'haskell-haskeline'
  'haskell-hpc'
  'haskell-hp2ps'
  'haskell-hpc-bin'
  'haskell-hsc2hs'
  'haskell-integer-gmp'
  'haskell-libiserv'
  'haskell-mtl'
  'haskell-parsec'
  'haskell-pretty'
  'haskell-process'
  'haskell-stm'
  'haskell-template-haskell'
  'haskell-terminfo'
  'haskell-text'
  'haskell-time'
  'haskell-transformers'
  'haskell-unix'
  'haskell-xhtml'
  'haskell-ghc-pkg'
  "haskell-ghc"
)
conflicts=('haskell-ghci')
backup=('usr/share/libalpm/hooks/ghc-rebuild-doc-index.hook'
        'usr/share/libalpm/hooks/ghc-register.hook'
        'usr/share/libalpm/hooks/ghc-unregister.hook')

package() {
  tar -xf "$srcdir/data.tar.xz" -C "${pkgdir}"

  install -Dm644 "$srcdir/ghc-rebuild-doc-index.hook" -t \
    "$pkgdir/usr/share/libalpm/hooks/"
  install -Dm644 "$srcdir/ghc-register.hook" -t \
    "$pkgdir/usr/share/libalpm/hooks/"
  install -Dm644 "$srcdir/ghc-unregister.hook" -t \
    "$pkgdir/usr/share/libalpm/hooks/"
}
```

* `alex-bootstrap`的PKGBUILD文件

```bash
pkgname=alex-bootstrap
provides=(alex)
pkgver=3.4.0.0
pkgrel=1
pkgdesc='Lexical analyser generator for Haskell'
arch=(x86_64)
url='https://hackage.haskell.org/package/alex'
license=(BSD-3-Clause)
depends=(ghc-libs)
source=("https://snapshot.debian.org/archive/debian-ports/20240919T192048Z/pool-loong64/main/a/alex/alex_3.4.0.1-1_loong64.deb")
sha512sums=('825efb12b9b10c725c1f76a8228e7e6da22c5cad2f8b213bc3b0b05f7da8565bc3afaee27cf70c0264199cc938011b6258779b392030a3608f1763ba73816523')

package() {
  tar -xf "$srcdir/data.tar.xz" -C "${pkgdir}"
}
```

* `happy-bootstrap`的PKGBUILD文件

```bash
pkgname=happy-bootstrap
provides=(happy haskell-happy-lib)
pkgver=2.1.5
pkgrel=1
pkgdesc="The Parser Generator for Haskell"
url="https://hackage.haskell.org/package/happy"
arch=('x86_64')
license=("BSD-2-Clause")
depends=('ghc-libs')
source=("https://snapshot.debian.org/archive/debian-ports/20240531T134713Z/pool-loong64/main/h/happy/happy_1.20.1.1-1%2Bb1_loong64.deb")
sha512sums=('d2096ac5020966a664affe9d8c5547adc1ced53978225779a2c3c8e0e7235e2ab016bb3e2a4bab6ea42ec5e8ea527195e4a546b13e8f9c12ee4bea58d89b4996')

package() {
  tar -xf "$srcdir/data.tar.xz" -C "${pkgdir}"
}
```

* `haskell-hscolour-bootstrap`的PKGBUILD文件

```bash
_hkgname=hscolour
pkgname=haskell-hscolour-bootstrap
provides=(haskell-hscolour)
pkgver=1.25
pkgrel=3
pkgdesc="Colourise Haskell code."
url="http://code.haskell.org/~malcolm/hscolour/"
license=("LGPL")
arch=('x86_64')
depends=('ghc-libs')
makedepends=('ghc')
source=("https://snapshot.debian.org/archive/debian-ports/20240917T132308Z/pool-loong64/main/h/hscolour/libghc-hscolour-dev_1.25-1_loong64.deb")
sha512sums=('c7daf013cc8ed230a4f75201f2add0ffb4c4a1380f7f303e3611107da0330f2dd0f3d0e2172e306c9b3f52817997e1e0aa0201d5edf6f268d5575e273defebab')

package() {
    tar -xf "$srcdir/data.tar.xz" -C "${pkgdir}"
}
```

* `haskell-hadrian-bootstrap`的PKGBUILD文件

```bash
_hkgname=hadrian
pkgname=haskell-hadrian-bootstrap
provides=(haskell-hadrian)
_ghcver=9.4.8
pkgver=0.1.0.0+$_ghcver
pkgrel=121
pkgdesc="GHC build system"
url="https://gitlab.haskell.org/ghc/ghc"
license=("BSD")
arch=('x86_64')
depends=('ghc-libs')
source=("https://snapshot.debian.org/archive/debian-ports/20241008T013019Z/pool-loong64/main/h/haskell-hadrian/hadrian_9.6.6-2_loong64.deb")
sha256sums=('b7a0193fa299e46a757b9f5a4bc5e3bc4aad0ecca5058d87a8ff41429bf86ead')

package() {
  tar -xf "$srcdir/data.tar.xz" -C "${pkgdir}"
}
```

#### GHC的后端

GHC支持NCG和LLVM后端，其中Arch Linux官方使用的是NCG后端，但可能需要等到GHC 9.12才会有NCG的龙架构支持。因此，我们目前只能使用LLVM后端。

从Arch Linux官方获取GHC的PKGBUILD文件，在`package_ghc`函数下的`depends`字段添加`llvm18`，保证安装GHC时也安装LLVM18。

然而，GHC对于LLVM版本存在要求。事实上，GHC 9.6.6只支持LLVM 11-15，并**不支持LLVM 18**。但LLVM直到17才开始支持龙架构，而我们的维护仓库中最低也只有LLVM18，因此我们只能想办法**强制使用LLVM18**。

首先，在`prepare`函数中更改GHC构建时检测LLVM的版本要求，以允许使用LLVM18：

```bash
sed -i 's/LlvmMaxVersion=[0-9]\+ \(# not inclusive\)/LlvmMaxVersion=19 \1/' configure.ac
autoreconf -fiv
```

当然，就这样掩耳盗铃地简单修改肯定是不行的，我们还需要实际解决LLVM版本间的兼容问题。GHC会调用LLVM的CLI进行编译和优化，通过测试可以发现其使用了LLVM18中不再支持的某些选项，需要对此调整适配。

这里我们还有一些小技巧，可以充分利用已有的资源：之前在使用Debian的二进制包自举的时候已经发现，Debian的GHC 9.6.6二进制包**依赖了LLVM18**，因此我们可以**推断**：**Debian必然有什么办法让GHC 9.6.6能够正常使用LLVM18**。

在[Debian的源码仓库](https://sources.debian.org)中查找，我们不难找到[GHC 9.9.6](https://sources.debian.org/src/ghc/9.6.6-4/debian/patches)的补丁集，查看其中看起来高度相关的补丁[llvm-new-pass-manager](https://sources.debian.org/src/ghc/9.6.6-4/debian/patches/llvm-new-pass-manager)，发现正是我们想要的。

现在，在Debian的工作基础上，我们只需要导入并应用这一补丁即可。

#### 跨发行版的安装后事务问题

Debian和Arch Linux的安装后事务处理机制不同，Debian使用`dpkg`的`postinst`和`prerm`脚本，而Arch Linux使用`libalpm`的hook机制。这导致了直接从二进制包解压出来的GHC安装后实际上还需要手动在root下运行`ghc-pkg recache`才能够正常使用。

对此，我们可以先不使用Arch Linux的干净nspawn容器的构建流程，暂时先手动进入nspawn构建容器环境中（可以直接从标准构建流程的容器快照得到，参见[笔者之前的博客](https://wszqkzqk.github.io/2024/08/22/loongarchlinux-port-tips/#%E6%88%91%E6%83%B3%E4%BF%9D%E5%AD%98%E6%9F%A5%E7%9C%8B%E6%9F%90%E4%B8%80%E6%AC%A1%E7%9A%84%E6%9E%84%E5%BB%BA%E7%8E%AF%E5%A2%83%E6%80%8E%E4%B9%88%E5%8A%9E)），以root身份运行：

```bash
ghc-pkg recache
```

然后切换到普通用户，这里是archbuild的`builduser`用户：

```bash
sudo -u builduser bash
```

复制相关构建文件到容器中，手动使用`makepkg -A`进行构建。在这一步，反正我们由Debian的二进制首次构建的软件包无论如何是不能直接上传的，因此即使这里引入了不干净的因素也无妨，后续使用本次构建出来的软件包进行干净构建即可。

#### 跨发行版的工具链名称问题

使用来自Debian的GHC二进制包自举时，还会遇到因为工具链名称导致的问题：GHC尝试运行`loongarch64-linux-gnu-ar`作为`ar`工具，`loongarch64-linux-gnu-ld`作为`ld`工具，但在Arch Linux中，这些工具名称为`ar`/`loongarch64-linux-gnu-gcc-ar`和`ld.bfd`。笔者经过若干尝试，发现无论是设置`AR`、`LD`环境变量，还是运行`autoreconf`重新生成配置文件，都无法解决这个问题。

最终，笔者选择了在`build`函数中**创建符号链接**的方式解决这个问题：

```bash
mkdir -p "${srcdir}/bin"
ln -sf "$(which loongarch64-linux-gnu-gcc-ar)" "${srcdir}/bin/loongarch64-linux-gnu-ar"
ln -sf "$(which ld.bfd)" "${srcdir}/bin/loongarch64-linux-gnu-ld"
export PATH="$PATH:${srcdir}/bin"
```

这样在Arch Linux环境下完成一次GHC的构建后，我们得到的新的GHC软件包将使用正确的工具链名称，在后续补丁中也就**无需集成**这个Hack。

#### 构建后的问题：功能缺失

经过上述步骤，我们终于成功构建出了GHC 9.6.6软件包。然而，在构建第一个Haskell包时，笔者即发现，GHC的功能并不完整，缺乏GHCi的支持，导致报错：

```log
ghc: panic! (the 'impossible' happened)
  GHC version 9.6.6
      link: GHC not built to link this way: LinkInMemory
  CallStack (from HasCallStack):
    panic, called at compiler/GHC/Driver/Pipeline.hs:390:22 in ghc:GHC.Driver.Pipeline
```

笔者再次注意到，Debian事实上已经构建了不少的Haskell包，可能有值得参考的经验。再次浏览Debian的[GHC 9.9.6](https://sources.debian.org/src/ghc/9.6.6-4/debian/patches)的补丁集，笔者注意到Debian应用了[hadrian-enable-interpreter](https://sources.debian.org/src/ghc/9.6.6-4/debian/patches/hadrian-enable-interpreter)这一简单补丁，禁用了Hadrian中的对启用平台的检测，从而强制在所有平台上启用了GHCi的支持。笔者便应用了这一补丁，重新构建GHC，终于得到了功能完整的GHC 9.6.6软件包。

## 利用有“功能替代”作用的其他软件包构建

某些软件包一般是需要自身构建的，但是有时候我们可以利用有“功能替代”作用的其他软件包构建。

一个非常常见的例子就是gcc系列的编译器与llvm系列的编译器功能上往往有**相互对应**或者**近似相互对应**的关系。

当然，有时候直接代替构建可能会出现问题，还需要根据具体情况调整编译参数、引入组件、临时禁用功能等。

### 例子：`ldc`

LDC编译器是基于LLVM的D语言编译器。Loong Arch Linux在还没有LDC时就已经有了GDC（GDC是基于GCC的D语言编译器）。因此我们可以利用GDC构建LDC。

然而，如果我们直接将`makedepends`中的`ldc`替换为`gcc-d`就构建，会出现以下问题：

```log
CMake Error at cmake/Modules/FindDCompiler.cmake:80 (message):
  No supported D compiler (ldmd2, dmd, gdmd) found! Try setting the
  'D_COMPILER' variable or 'DMD' environment variable.
```

这是因为LDC的CMake脚本在检测D编译器时，只支持`ldmd2`、`dmd`和`gdmd`这些接受D语言参考实现`dmd`参数风格的编译器，而实际上`gcc-d`并没有提供`gdmd`（不同的是`ldc`是提供`ldmd2`的）。

PS: 对于新手来说，上面这条知识本身可能不是那么关键，因为它已经被记录在我的教程里面了，很容易查阅到。但是笔者是怎么知道的呢？**在遇到相关问题时知道怎么查/怎么做可能才更关键**。笔者此前也对D语言编译器相关的一切完全不了解，遇到这个问题时，笔者首先去**AUR**查找了`gdmd`，找到了[`gdmd-git`这个包](https://aur.archlinux.org/packages/gdmd-git)，包的描述是`DMD-like wrapper for GDC`，即`gdmd`是`GDC`的`DMD`的包装器。再去专门查找一下相关知识，即可知道想要构建`ldc`，仅仅有`gcc-d`是不够的，还需要`gdmd`，因此笔者打包了AUR的`gdmd-git`并添加到本地仓库，然后在`ldc`的PKGBUILD文件中添加了`gdmd`到`makedepends`中。

从AUR获取`gdmd-git`并构建、添加到本地仓库，且在修改的`ldc`的PKGBUILD文件中额外添加`gdmd`到`makedepends`后，即可尝试构建`ldc`。

然而，这样直接构建时又会遇到问题。Arch Linux的`ldc`软件包的PKGBUILD文件中指定了一些编译参数：

```bash
    ...
    -DD_COMPILER_FLAGS="-link-defaultlib-shared=false -linker=lld --flto=thin" \
    -DADDITIONAL_DEFAULT_LDC_SWITCHES="\"-link-defaultlib-shared\"," \
    ...
```

经过尝试，我们可以发现，`gdmd`并不能接受这些参数，进而报错。我们可以在`build()`函数中，临时禁用这些参数再次构建。

构建完成后，我们可以将`ldc`软件包添加到本地仓库，然后使用这一用`gcc-d`构建的`ldc`软件包，利用Arch Linux官方的`ldc`的PKGBUILD文件，构建干净的`ldc`软件包。

不幸的是，我们又会遇到一个与架构及发行版环境有关的问题，即`ldc`这一**软件包本身需要Patch**。如果直接按照官方的PKGBUILD文件构建，在**check**阶段会报错：

```log
/usr/bin/ld: /build/ldc/src/ldc/build/lib/libdruntime-ldc-unittest-shared.so: undefined reference to `__atomic_compare_exchange_16'
/usr/bin/ld: /build/ldc/src/ldc/build/lib/libdruntime-ldc-unittest-shared.so: undefined reference to `__atomic_load_16'
/usr/bin/ld: /build/ldc/src/ldc/build/lib/libdruntime-ldc-unittest-shared.so: undefined reference to__atomic_store_16'
collect2: error: ld returned 1 exit status
```

可见，`libatomic`库的链接问题导致了这一测试用例的构建失败。此时需要在CMake配置时显式指定链接到`libatomic`库：

```bash
    ...
    -DLD_FLAGS="-Wl,--no-as-needed -latomic -Wl,--as-needed" \
    ...
```

然后再次构建，即得到了干净且测试全部通过的`ldc`软件包。上传补丁和`ldc`软件包即可。

附注：这一链接问题是ldc的一个bug，ldc的测试用到的druntime中使用了16字节的原子操作，这一操作在某些架构下（比如x86_64）可以内联为一条指令，但是在某些架构下（比如loon64和riscv64）则需要调用`libatomic`库中的函数。因此，这一问题在loon64上会暴露出来。经过讨论，ldc的维护者已经在开发分支中修复了这一问题，对于loong64与riscv64架构会默认链接`libatomic`库。因此，这一问题在未来的版本中将不再出现。参见[这一PR](https://github.com/ldc-developers/ldc/pull/4864)。
