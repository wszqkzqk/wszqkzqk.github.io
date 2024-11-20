---
layout:     post
title:      Loong Arch Linux维护中可能用到Bootstrap构建方法
subtitle:   面向新人的Bootstrap构建基础教程
date:       2024-11-20
author:     wszqkzqk
header-img: img/bg-sunrise.webp
catalog:    true
tags:       系统配置 系统维护 开源软件 Linux archlinux 国产硬件 虚拟化
---

## 前言

有时候某些软件的构建往往会依赖自身进行编译，这时候就需要使用Bootstrap构建方法。这种方法在Arch Linux维护中可能会用到，因此我在这里写了一个面向新人的Bootstrap构建基础教程。

本教程仅简单列举一些新人相对容易理解的、常见的Bootstrap构建方法，对于复杂的问题，可能需要具体研究。

## 注意事项

首次通过“不干净”的方法生成的软件包**请勿上传**，请将这一文件[添加到本地仓库](https://wszqkzqk.github.io/2024/09/19/build-order-local-repo/)，再使用**官方的构建文件**（或者基于官方构建文件应用了我们**补丁集中的补丁**的），进行**正式的打包**，然后上传，保证构建的可复现性。

## 上游给出Bootstrap构建方法的情况

某些软件包官方会给出Bootstrap构建方法，因此我们需要注意查看**官方文档**中是否有相关说明。

### 例子：`vala`

Vala是一种编程语言，Vala编译器会将Vala代码编译成C代码，然后再编译成二进制文件。Vala编译器本身也是用Vala语言编写的，因此在编译Vala编译器时，我们需要使用Bootstrap构建方法。Vala官方给出了Bootstrap构建方法：Vala官方会直接发布由Vala代码生成的中间C代码的tarball，我们只需要解压这个tarball，然后再用C编译器编译即可。

因此，我们只需要对Arch Linux官方的`vala`软件包的PKGBUILD文件进行修改得到`vala-bootstrap`软件包的PKGBUILD文件即可。

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

这样的`vala-bootstrap`软件包构建完成后，我们可以将其添加到本地仓库，然后使用`vala-bootstrap`软件包构建`vala`软件包。最后，我们再将最后得到的`vala`软件包上传。

## 利用其他发行版的二进制包构建

如果某个软件包在Loong Arch Linux上还没有，但是其他支持LoongArch的发行版上已经构建好了二进制包，我们可以尝试使用其他发行版的二进制包构建。我们同样可以构建一个`-bootstrap`软件包，然后在`build()`或者`package()`函数中，使用`bsdtar`解压其他发行版的二进制包，直接安装到`$pkgdir`中。

这一方法容易遇到一些问题：

* 不同发行版的路径结构可能不同，有时候可能需要手动调整
  * 比如`/usr/lib`和`/usr/lib64`的区别
  * 比如`/usr/bin`和`/usr/local/bin`的区别
* 不同发行版的二进制包可能有不同的依赖，需要手动调整或者导入依赖包

## 利用有“功能替代”作用的其他软件包构建

某些软件包一般是需要自身构建的，但是有时候我们可以利用有“功能替代”作用的其他软件包构建。

一个非常常见的例子就是gcc系列的编译器与llvm系列的编译器往往有**相互对应**或者**近似相互对应**的关系。

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

PS: 对于新手来说，**这个知识可能不是那么关键**，因为它已经被记录在我的教程里面了，很容易查阅到。但是笔者是怎么知道的呢？**在遇到相关问题是知道怎么查/怎么做可能才更关键**。笔者此前也对D语言编译器相关的一切完全不了解，遇到这个问题时，笔者首先去**AUR**查找了`gdmd`，找到了[`gdmd-git`这个包](https://aur.archlinux.org/packages/gdmd-git)，包的描述是`DMD-like wrapper for GDC`，即`gdmd`是`GDC`的`DMD`的包装器。再去专门查找一下相关知识，即可知道想要构建`ldc`，仅仅有`gcc-d`是不够的，还需要`gdmd`，因此笔者打包了AUR的`gdmd-git`并添加到本地仓库，然后在`ldc`的PKGBUILD文件中添加了`gdmd`到`makedepends`中。

从AUR获取`gdmd-git`并构建、添加到本地仓库，且在修改的`ldc`的PKGBUILD文件中额外添加`gdmd`到`makedepends`后，即可尝试构建`ldc`。

然而，这样直接构建时又会遇到问题，Arch Linux的`ldc`软件包的PKGBUILD文件中指定了一些编译参数：

```bash
    ...
    -DD_COMPILER_FLAGS="-link-defaultlib-shared=false -linker=lld --flto=thin" \
    -DADDITIONAL_DEFAULT_LDC_SWITCHES="\"-link-defaultlib-shared\"," \
    ...
```

而`gdmd`并不能接受这些参数，进而报错，我们可以在`build()`函数中，临时禁用这些参数再次构建。

构建完成后，我们可以将`ldc`软件包添加到本地仓库，然后使用这一用`gcc-d`构建的不干净的`ldc`软件包构建干净的`ldc`软件包。

不幸的是，我们又会遇到一个与架构有关的问题，即`ldc`这一**软件包本身需要Patch**。如果直接按照官方的PKGBUILD文件构建，在**check**阶段会报错：

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
