---
layout:     post
title:      龙芯Arch Linux移植技巧
subtitle:   Loong Arch Linux移植要点
date:       2024-08-22
author:     wszqkzqk
header-img: img/bg-mountain-darken.webp
catalog:    true
tags:       系统配置 系统维护 开源软件 Linux archlinux 国产硬件 虚拟化
---

# 需要重新构建的软件查找

多数时候，如果遇到上游软件包的soname变更，往往需要重新构建链接到这些库的软件包。

软件包所包含的`.so`文件可以通过以下命令列出：

```bash
pkgfile -l <package> | grep -F .so
```

在得知发生了soname变更的文件之后，可以通过以下命令列出链接到这些库的软件包：

```bash
sogrep <repo-name> <soname>
```

注意这里的`<soname>`是文件名而非完整路径。列出的软件包因为链接到了soname发生变更的库，所以需要重新构建。

# 一般的Bootstrap方法

在Bootsrap的过程中，往往需要在构建环境中添加一些源中没有的软件包，这可以通过`makechrootpkg`的`-I`参数来实现，而在运行`extra-testing-loong64-build`或者`extra-staging-loong64-build`的时候，可以通过`--`参数来添加传递到`makechrootpkg`的参数。

```bash
cd <package>
extra-testing-loong64-build -- -I
```

# TODO
