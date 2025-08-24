---
layout:     post
title:      在使用Meson为构建系统的项目中处理多调用CLI
subtitle:   保证跨平台且与Meson集成的前提下妥善管理多调用CLI的复杂构建
date:       2025-08-24
author:     wszqkzqk
header-img: img/media/bg-modern-img-comp.webp
catalog:    true
tags:       开源软件 构建工具 Meson Vala
---

## 前言

> Meson是一个功能强大的构建系统，旨在简化软件项目的构建过程。然而，Meson本身并没有内置对**多调用二进制**的直接支持。

> 多调用二进制指的是一个可执行文件可以响应多个不同的命令。程序在运行时检查它被调用时使用的名称（即`argv[0]`），然后根据这个名称决定执行哪个功能。典型例子就是BusyBox，它将大量常用的Unix工具（如`ls`, `cp`, `grep`, `ps`等）集成在一个可执行文件中。当你创建指向BusyBox的符号链接，比如`ln -s /bin/busybox /bin/ls`，那么当你运行`ls`时，实际上运行的是BusyBox，当BusyBox检查到`argv[0]`是`ls`时，它就会执行`ls`的功能。

> 这种方法在嵌入式领域上有广泛应用，除此之外，在某些时候也可以用于简化CLI的编写。

笔者开发了一个用于综合处理Android动态照片的工具[live-photo-conv](https://github.com/wszqkzqk/live-photo-conv)。该工具原本设计有一个强大但复杂的CLI——`live-photo-conv`，基本集成了所有有关动态照片解包、逐帧提取、生成，和元数据修复的功能。然而，这样复杂的集成虽然在功能上很强大，但在使用上却显得较为繁琐，有些时候可能会要求用户传递比较多的参数；另外，`--help`中琳琅满目的选项也可能让用户眼花缭乱。

为了在大多数情况下简化用户体验，笔者觉得在全集成式的`live-photo-conv`这一CLI之外，额外提供专门用于解包与帧提取的`live-photo-extract`、专门用于生成的`live-photo-make`、以及专门用于元数据修复的`live-photo-repair`等子命令是一个不错的选择。

然而，如果这些额外的子命令需要再额外独立维护若干份新的CLI源码，那么在项目结构和构建系统上就会变得更加复杂。事实上，这些子命令处理与主命令处理的逻辑是高度相似的，绝大部分代码可以共用，若每一个子命令都单独维护CLI处理和程序入口源码将会导致代码重复和维护成本增加，很不经济。

因此，笔者认为多调用二进制的设计理念在此尤为合适：在同样一个CLI文件中实现`live-photo-conv`及其子命令`live-photo-extract`、`live-photo-make`、`live-photo-repair`的处理功能，这样可以最大限度地复用程序的逻辑。

然而，Meson本身并没有直接集成一个完备的、跨平台的多调用二进制支持方案。用Meson管理多调用二进制的构建，尤其是同时兼容类Unix和Windows平台时，存在诸多困难。

## 探索尝试

### Meson下的软链接与复制

Meson内置了`install_symlink()`函数，可以方便地在安装阶段创建符号链接，但这仅适用于类Unix系统。在Windows上，一方面是需要处理二进制文件额外的`.exe`**拓展名**，否则会直接失败，更重要的是，由于平台对软链接创建要求管理员权限，Meson会直接**跳过软链接的创建**，造成不一致的行为。故即使处理好拓展名也不行。

处理的一个方法是将软链接改为复制，利用`install_data()`等方法来复制文件；然而，`install_data()`只支持在源码仓库中存在的文件的安装，而不支持构建生成的文件。

利用Meson提供的`custom_target()`函数来在Windows上复制主可执行文件并重命名为子命令的名称也存在困难：Windows并不支持`cp`命令，而`cmd`所支持的`copy`命令不支持用`/`作为路径的分隔符，导致Meson传递的路径可能失效；`powershell`/`pwsh`等工具虽然可以用于复制，但并不能保证所有Windows系统都预装了它们。

而且，笔者在构建中还使用了`help2man`来创建手册页，以便为每个命令生成相应的文档。但这也就要求在项目的**构建阶段**内即需要**存在各个子命令的可执行文件**，否则`help2man`无法为它们生成文档。这也就导致无论是创建链接还是复制，都需要在构建阶段内完成，不可拖延到安装阶段。

### 多次构建

对CLI对应的`main.vala`文件运行多次构建，生成不同名称的可执行文件完全保证在构建阶段内生成所需的子命令文件，也完全可以跨平台。然而，这将在一定程度上延长项目的构建时间，并增大分发体积，并不优雅。笔者更希望在不同平台下都使用**最优实践**，并保证**一致的体验**。

## 设计方案

### 主可执行文件与别名列表

首先，在 `src/meson.build` 中，我们正常定义主可执行文件，并创建一个列表来存储所有别名的名称。

```
# 构建主程序
main_exe_name = 'live-photo-conv'
main_exe_bin = executable(main_exe_name,
  ['main.vala'],
  install: true,
  link_with: liblivephototools,
  dependencies: lib_deps,
)

# 定义所有子命令（别名）
sub_exe_names = ['live-photo-make', 'live-photo-extract', 'live-photo-repair']
```

### 跨平台处理方式

笔者希望在类Unix平台下使用软链接创建子命令文件，而在Windows平台下则采用复制的方式，均在构建阶段内完成，尽可能保持一致的体验。

在这样的要求下，由于各个支持平台的系统命令并不兼容，尤其是Windows平台情况复杂，适配较为困难。然而，我们考虑到，Meson构建系统本身是依赖Python的，因此在我们支持的环境中**一定具有可用的Python解释器**。因此，笔者设计了**调用Python脚本**的`custom_target()`实现来处理。由于Python集成了强大的跨平台能力，我们不难在Python脚本中处理所有平台的差异。

```
# scripts/create-binary-symlinks.py
import sys
import shutil
import platform
from pathlib import Path

def create_binary_symlink(source_binary, target_name):
    source_path = Path(source_binary)
    target_path = Path(target_name)
    
    if target_path.exists():
        target_path.unlink()
    
    try:
        if platform.system() == 'Windows':
            # 在 Windows 上，创建副本
            shutil.copy2(source_path, target_path)
            print(f"Created copy: {target_path}")
        else:
            # 在类 Unix 系统上，创建相对路径的符号链接
            source_name = source_path.name
            target_path.symlink_to(source_name)
            print(f"Created symlink: {target_path} -> {source_name}")
        return True
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return False

# ... main function ...
```

这个脚本接收源文件和目标文件名作为参数，在 Windows 上执行复制，在其他系统上执行符号链接创建。

### 使用 `custom_target` 在构建时生成别名

接下来，我们使用 Meson 的 `custom_target` 在构建时调用上述 Python 脚本，为每一个别名生成对应的文件。

```
# meson.build
...
# 获取 Python 解释器
python = import('python').find_installation()
```

```
# src/meson.build

symlink_script = meson.project_source_root() / 'scripts' / 'create-binary-symlinks.py'
sub_exe_bins = []

foreach exe_name : sub_exe_names
  # 在构建目录中创建链接/副本
  linked_exe = custom_target('link-' + exe_name,
    # Windows 上需要 .exe 后缀
    output: exe_name + (is_windows ? '.exe' : ''),
    command: [
      python,
      symlink_script,
      main_exe_bin.full_path(), # 主程序路径
      '@OUTPUT@',              # 产物路径
    ],
    depends: main_exe_bin,
    build_by_default: true,
    # ... 安装部分见下文（有坑） ...
  )
  sub_exe_bins += [linked_exe]
endforeach
```

通过这个循环，Meson 会为 `sub_exe_names` 中的每个名称都执行一次我们的 Python 脚本，从而在构建目录中生成了所有别名文件。`@OUTPUT@` 是 Meson 的魔法变量，代表了 `output:` 字段定义的文件名。

### 解决安装阶段的陷阱

最棘手的部分在于安装。Meson 的 `custom_target` 在处理符号链接的安装时存在一些问题。如果直接在 `custom_target` 中设置 `install: true`，Meson 在目前的默认行为下（`follow_symlinks: true`）会将符号链接解引用，安装其指向的源文件，而不是链接本身；由于Meson以后的默认行为会改为`follow_symlinks: false`，我们还会收到一个警告：

```log
Warning: trying to copy a symlink that points to a file. This currently copies
the file by default, but will be changed in a future version of Meson to copy
the link instead.  Set follow_symlinks to true to preserve current behavior, or
false to copy the link.
```

而Meson目前又**不支持在`custom_target`中设定`follow_symlinks`参数**。这就破坏了我们的设计，没有达到在类Unix平台上使用软链接的目的。（参见 [Meson issue #12710](https://github.com/mesonbuild/meson/issues/12710)）

为了绕过这个坑，笔者在`meson.build`中仍采用了分平台处理的策略：

```
# src/meson.build (在 foreach 循环内部)

  linked_exe = custom_target('link-' + exe_name,
    # ... 前述 command 等配置 ...
    
    # 仅在 Windows 上通过 custom_target 安装副本
    install: is_windows, 
    install_dir: get_option('bindir'),
  )
  
  # 在非 Windows 平台上，使用 meson.install_symlink() 单独安装符号链接
  if not is_windows
    install_symlink(
      exe_name,
      pointing_to: main_exe_name, # 指向主程序名
      install_dir: get_option('bindir')
    )
  endif
```

* 在Windows上，`custom_target` 生成的是一个独立的 `.exe` 副本，所以直接通过 `install: true` 来安装它是完全正确的。
* 在类Unix上，我们将 `custom_target` 的 `install` 属性设为 `false`，使得Python脚本创建的子命令文件仅用于`help2man`的文档生成。随后，显式调用 `install_symlink()` 函数用于安装。这个函数能确保被安装的是一个指向 `main_exe_name` 的符号链接，完美符合我们的需求。

这样，我们既能保证在运行`help2man`文档生成的时候，能够调用到创建的子命令，又能在支持时在安装中使用符号链接，减小安装体积。

### 集成 Man Page 生成

既然我们在安装阶段有了多个“可执行文件”，通过 `help2man` 和 `custom_target`，我们便很容易为所有主程序和别名生成文档。

```
# meson.build
...
# 获取 help2man 程序
help2man_prog = find_program('help2man', required: get_option('manpages'))
```

```
# src/meson.build

# 为主程序生成 man page
custom_target('manpage-' + main_exe_name,
  # ...
)

# 为所有别名生成 man page
foreach index : range(sub_exe_names.length())
  custom_target('manpage-' + sub_exe_names[index],
    output : sub_exe_names[index] + '.1',
    command : [
      help2man_prog,
      # ...
      sub_exe_bins[index].full_path(),
      # ...
    ],
    install : true,
    install_dir : get_option('mandir') / 'man1',
    depends : sub_exe_bins[index], # 依赖于别名文件的创建
  )
endforeach
```

这样就可以正确地从主命令与每个子命令提取帮助信息，生成 man page。

## 实现

以上讨论中，笔者已经进行了充分的分析，并提出了相应的解决方案。接下来，笔者将展示正式的实现代码。

### Python脚本实现

```
#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""
Cross-platform script to create symlinks/copies of the main binary with different names.
On Windows: creates copies
On Unix-like systems: creates symbolic links

Copyright 2024-2025 Zhou Qiankang <wszqkzqk@qq.com>
"""

import sys
import shutil
import platform
from pathlib import Path


def create_binary_symlink(source_binary, target_name):
    """Create a symlink or copy of the source binary with the target name."""
    source_path = Path(source_binary)
    target_path = Path(target_name)
    
    # Remove target if it already exists
    if target_path.exists():
        target_path.unlink()
    
    try:
        if platform.system() == 'Windows':
            # On Windows, create a copy
            shutil.copy2(source_path, target_path)
            print(f"Created copy: {target_path}")
        else:
            # On Unix-like systems, create a symbolic link
            # Use relative path for the symlink to make it portable
            source_name = source_path.name
            target_path.symlink_to(source_name)
            print(f"Created symlink: {target_path} -> {source_name}")
        
        return True
    except Exception as e:
        print(f"Error creating link/copy {target_path}: {e}", file=sys.stderr)
        return False


def main():
    if len(sys.argv) < 3:
        print("Usage: create_binary_links.py <source_binary> <target1> [target2] ...", file=sys.stderr)
        sys.exit(1)
    
    source_binary = sys.argv[1]
    target_names = sys.argv[2:]

    success = True
    for target_name in target_names:
        if not create_binary_symlink(source_binary, target_name):
            success = False
    
    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
```

### `custom_target`设计与改进

```
# Create symlinks/copies in build directory and install them
symlink_script = meson.project_source_root() / 'scripts' / 'create-binary-symlinks.py'
sub_exe_bins = []
foreach exe_name : sub_exe_names
  # Create link/copy in build directory and install it
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
    install: is_windows, # Workaround for https://github.com/mesonbuild/meson/issues/12710
    install_dir: get_option('bindir'),
  )
  # Workaround for https://github.com/mesonbuild/meson/issues/12710
  if not is_windows
    install_symlink(
      exe_name,
      pointing_to: main_exe_name,
      install_dir: get_option('bindir')
    )
  endif

  sub_exe_bins += [linked_exe]
endforeach
```

## 结论

通过 **`custom_target` + 外部脚本** 的组合，并利用 **分平台处理安装逻辑** 的技巧，我成功地在 `live-photo-conv` 项目中实现了一套健壮、跨平台的多调用 CLI 构建方案。

这套方案的优点在于：
* **逻辑清晰**：构建逻辑（Meson）与平台差异化操作（Python）分离。
* **跨平台**：无需修改 meson.build 即可在 Windows 和 Linux 上获得符合各自平台习惯的产物。
* **完全集成**：无论是构建、测试还是安装，别名文件的行为都与普通可执行文件无异，并且能够集成 man page 生成等下游任务。

对于同样在使用 Meson 并希望实现多调用二进制模式的开发者，本文提供了一种可行的解决方案，希望能为你们的项目带来帮助。
