---
layout:       post
title:        LinSYS2再进化：在Linux上直接构建MSYS2软件包
subtitle:     从Wine执行到bubblewrap路径视图，linsys2-makepkg如何打通混合构建环境
header-img:   img/wine/wine-bg.webp
date:         2026-11-01
author:       wszqkzqk
catalog:      true
tags:         开源软件 Wine MSYS2 跨平台开发 archlinux
---

## 前言

在[上一篇介绍LinSYS2的文章](https://wszqkzqk.github.io/2026/04/27/LinSYS2/)中，笔者展示了如何在Linux上安装MSYS2官方仓库中的Windows工具链，再通过Wine完成编译、调试和运行。那时，LinSYS2已经能够让开发者方便地使用MSYS2提供的软件包。

现在，项目又向前跨了一步：新增的[`linsys2-makepkg`](https://github.com/wszqkzqk/LinSYS2)可以直接读取[MINGW-packages](https://github.com/msys2/MINGW-packages)中的PKGBUILD，在Linux上完成依赖安装、源码构建和软件打包，生成可由MSYS2自带的pacman直接安装的`.pkg.tar.zst`软件包。

```bash
cd MINGW-packages/mingw-w64-zlib
linsys2-makepkg -s
```

这意味着，修改一个MSYS2软件包、验证MINGW-packages的PR、维护私有软件包，甚至在Linux CI中构建Windows软件包，都可以沿用MSYS2现有的PKGBUILD和官方工具链。LinSYS2也由“Windows工具链的安装与运行工具”扩展成了完整的软件包构建环境。

这条命令看上去与MSYS2中的`makepkg-mingw`十分相似，背后的工作却要多得多。PKGBUILD期待POSIX shell和MSYS2路径，MinGW编译器是Windows程序，配置脚本还会不断生成并执行新的Windows二进制。让这些环节在Linux上协同工作，才是`linsys2-makepkg`真正有趣的地方。

## 从PKGBUILD构建可安装的软件包

Arch Linux用户可以从AUR安装LinSYS2，其他发行版的安装方式见[项目README](https://github.com/wszqkzqk/LinSYS2#installation)。构建功能还需要Wine、`bubblewrap`和后文介绍的`binfmt_misc`。

先初始化目标环境，然后就可以直接读取MINGW-packages中的PKGBUILD：

```bash
linsys2-pacman init

git clone https://github.com/msys2/MINGW-packages.git
cd MINGW-packages/mingw-w64-zlib

# 解析并安装MinGW构建依赖，然后构建软件包
linsys2-makepkg -s
```

生成的软件包位于当前PKGBUILD目录，可以安装回对应环境：

```bash
linsys2-pacman -U mingw-w64-ucrt-x86_64-zlib-*-any.pkg.tar.zst
```

同一个软件包也可以复制到Windows上的MSYS2环境中，直接用MSYS2自带的`pacman -U`安装。Linux侧的构建产物由此可以进入MSYS2原有的安装与验证流程。

也可以为多个环境连续构建。每个环境拥有自己的包数据库、安装前缀、编译参数和Wine前缀：

```bash
linsys2-pacman init --env clang64
MINGW_ARCH="ucrt64 clang64" linsys2-makepkg -s
```

目前已支持`ucrt64`、`clang64`和`clangarm64`。`linsys2-makepkg`仍标记为实验性功能，但从获取依赖到生成、安装软件包的链路已经完整贯通。

## Linux原生makepkg与Windows工具链协同

`linsys2-makepkg`沿用MSYS2的PKGBUILD和makepkg实现，采用分工明确的混合模型：让Linux原生工具负责组织构建，让Wine中的Windows工具负责目标平台的编译与运行。

<div class="mermaid">
flowchart TD
    PKGBUILD["PKGBUILD"] --> Makepkg["Linux原生makepkg与bash"]
    Bwrap["bubblewrap：统一MSYS2规范路径"] --> Makepkg
    Makepkg --> Host["Linux宿主构建工具"]
    Makepkg --> Wrapper["build-bin：命令与平台语义适配"]
    Wrapper --> Wine["Wine中的Windows编译器与工具"]
    Makepkg --> PE["构建过程中生成的PE程序"]
    PE --> Binfmt["binfmt_misc"]
    Binfmt --> Wine
    Makepkg --> Package["MSYS2 pacman可直接安装的软件包"]
</div>

保留Linux原生makepkg是一个关键选择。PKGBUILD的函数、变量展开、源码下载、依赖处理和归档逻辑都由成熟的makepkg实现，LinSYS2只需提供适合各目标环境的`makepkg_linsys2.conf`，设置`MINGW_PREFIX`、`MINGW_CHOST`、`CC`、`CXX`和编译参数。Windows GCC、Clang、CMake等工具则继续来自MSYS2官方仓库，通过Wine运行。

这种分工保留了PKGBUILD的原始形态和Linux的轻量执行环境，核心工作集中在两种工具链之间的语义连接。

## bubblewrap的挂载命名空间与MSYS2路径适配

MSYS2构建系统大量依赖固定前缀。`ucrt64`环境中的编译器、头文件和库通常位于`/ucrt64`，而LinSYS2为了维持用户级安装，把实际文件放在：

```text
~/.local/share/linsys2/ucrt64/ucrt64/
```

如果逐个修改PKGBUILD和上游构建脚本，路径适配会变成永无止境的补丁工作；在宿主根目录创建符号链接又会引入全局状态和权限要求。复制整个环境同样不理想，因为包数据库、构建依赖和Wine前缀都需要继续共享同一份状态。

`linsys2-makepkg`最终选择用`bubblewrap`创建私有挂载命名空间，在每次构建中把真实目录绑定到`/ucrt64`、`/clang64`或`/clangarm64`。这样，规范路径只在当前构建视图中生效，宿主机目录结构保持不变，构建过程仍然直接访问用户目录中的文件。

这个选择也恰好与Wine的路径模型衔接。Wine默认通过`Z:`盘映射Linux根目录，因此同一份文件在两类进程中分别呈现为：

```text
Linux原生bash与构建脚本：/ucrt64
Wine中的Windows工具：    Z:\ucrt64
```

路径视图统一以后，Windows编译器输出的路径与Linux脚本使用的路径才有了稳定的转换基础。Wine进程也需要看到这个挂载视图，因此构建会在命名空间中重启wineserver，并在退出时清理。

`bubblewrap`在这里提供轻量的路径适配层，构建直接使用宿主现有文件和工具。在部分拒绝新建procfs挂载的容器中，实现还会回退为绑定现有的`/proc`，让同一套路径方案继续工作。

## 包装脚本与binfmt_misc的执行分工

路径问题解决以后，下一个问题来自命令解析。Linux构建脚本通常调用`gcc`，MSYS2提供的却是`gcc.exe`。

最直觉的做法是创建`gcc -> gcc.exe`符号链接，项目在初期也采用过这种思路。但Windows工具不仅需要一个能被执行的入口，还依赖真实安装位置完成自我定位。Wine会根据模块路径处理DLL搜索，GCC的specs、CMake的模块等资源也与实际目录相关。符号链接可能让工具把链接所在目录误当作模块路径，使命令虽然启动，后续资源查找却偏离预期。

因此，实现后来改为在独立目录中生成包装脚本：

```text
~/.local/share/linsys2/ucrt64/build-bin/
```

`gcc`包装脚本的核心逻辑相当于：

```bash
export WINEPREFIX="$HOME/.local/share/linsys2/ucrt64/wine"
export WINEDEBUG=-all
exec wine "/实际安装路径/ucrt64/bin/gcc.exe" "$@"
```

`build-bin`被放到PATH前端，包装脚本则始终调用真实`.exe`的绝对路径。裸命令名、Wine前缀和模块定位由此同时得到保留，生成文件集中留在这个私有目录，pacman管理的安装目录保持原状。对于`.bat`和`.cmd`，实现保留显式扩展名，并通过`wine cmd /c`执行。

不过，包装脚本只能覆盖从PATH按名称启动的工具。Autoconf经常会生成一个小型测试程序，然后直接按路径执行：

```bash
./conftest.exe
```

这类文件只有在构建过程中才会出现，因此需要一种按路径直接执行PE程序的通用机制。配置过程中的大量能力探测又依赖这种“编译后立即运行”的行为，一旦无法执行，构建系统就无法判断目标平台特性。

这里引入了第二层执行机制：通过Linux内核的`binfmt_misc`，把带有`MZ`头的PE程序自动交给Wine。多**数配置好Wine的发行版已经注册了相应规则**，如果有少数环境没有自带的规则，可以执行以下命令手动配置：

```bash
echo ':DOSWin:M::MZ::/usr/bin/wine:F' | \
    sudo tee /etc/binfmt.d/linsys2-wine.conf
sudo systemctl restart systemd-binfmt
```

这是一次性的系统准备。末尾的`F`标志会让内核在注册时打开解释器，使规则在其他挂载命名空间中也能使用；在容器内构建时，应在宿主机注册。

包装脚本与`binfmt_misc`因此形成互补：前者处理已知工具的命令名、环境和模块路径，后者接管构建过程中不断出现的未知PE文件。只有两者同时存在，执行链才能从编译器延伸到配置探测和生成的程序。

## uname、arch与cygpath的平台语义适配

编译器能够运行以后，构建系统还需要获得正确的平台身份，才能选择正确的代码路径。大量configure和Makefile逻辑会先查询系统身份，再决定源文件、链接参数和生成规则。如果`uname`仍然回答`Linux`，或者`arch`返回宿主CPU，后续判断就会错误地面向Linux宿主。

为此，`build-bin`中还包含一组特殊的原生脚本。`uname`返回`MINGW64_NT-...`形式的系统名，Windows版本通过所选Wine前缀中的`wine cmd /c ver`获取；`uname -m`与`arch`则报告目标环境的机器类型。这样，在x86_64宿主上构建ARM64软件包，或者在ARM64宿主上构建x86_64软件包时，系统探测仍然面向目标环境。

这些脚本也需要足够认真地模拟命令行为。项目迭代中曾出现组合选项未被覆盖的情况：简单的`uname -s`能够返回预期结果，`uname -sm`却可能落回宿主命令，把宿主身份重新带入配置过程。现在的实现会解析组合短选项和GNU长选项，按固定顺序输出字段，覆盖构建脚本实际使用的调用形式。

`cygpath`承担另一类平台语义：在Unix路径、Windows路径和PATH式路径列表之间转换。这里的边界同样很具体。Windows盘符后的冒号不是路径列表分隔符，`Z:`开头的路径需要映射到Wine看到的Linux根目录，其他盘符则对应各自的`drive_*`目录。

项目历史中还记录过一个很能说明问题的故障：`cygpath`最初使用`#!/usr/bin/env python3`，而PATH前端的Windows Python包装可能被优先选中，令输出带上CRLF。libtool把这段输出嵌入C包装源码后，多余的回车会破坏字符串字面量；更隐蔽的是，libtool仍然返回成功，最终导致程序漏装和安装钩子中的悬空链接。修复方式是把兼容脚本的解释器固定为构建时的Linux Python绝对路径，同时完善盘符与路径列表处理。

这些脚本向构建系统提供了关于平台身份和路径形式的稳定答案，是整个兼容层的一部分。

## 适配Windows路径与Linux构建工具的接口差异

即使`/ucrt64`与`Z:\ucrt64`已经能够对应，Windows工具输出的路径也未必能直接交给Linux工具使用。这个问题在libtool和Automake项目中尤其明显。

Windows GCC执行`gcc -print-prog-name=ld`时可能给出`Z:/...`路径，原生bash无法把它当作可执行文件启动。`linsys2-makepkg`因此默认设置`LD=ld`，让链接器重新通过PATH解析，也使libtool进入GNU ld处理分支。

libtool还会用`test -d`验证GCC报告的库搜索目录，`Z:/...`形式在原生shell中自然无法通过检查。实现通过预置`lt_cv_sys_lib_search_path_spec`，直接提供命名空间内真实的`/ucrt64`路径，避免每次配置都沿着错误前提继续探测。

Automake的依赖文件又是另一种情况：其中如果包含盘符和反斜杠，未启用DOS路径支持的GNU make无法正确解析。对于一次性的软件包构建，实现默认关闭编译器头文件依赖跟踪，将`am_cv_CC_dependencies_compiler_type`和对应的CXX变量设为`none`。

这些值都通过`setdefault`写入，用户显式提供的环境变量仍然优先。它们负责衔接Windows工具输出与Linux构建工具的输入。

## 依赖安装与工具入口的动态同步

`makepkg -s`会在构建过程中安装依赖，构建环境因此需要在makepkg启动后持续更新。这里的依赖还分成两类：bash、awk等宿主工具由Linux发行版提供，`mingw-w64-*`编译器和库则由目标环境的pacman数据库管理。

LinSYS2在pacman依赖处理中体现了这种分工：非MinGW依赖视为宿主提供，MinGW依赖继续通过MSYS2仓库解析和安装。对应的`makepkg_linsys2.conf`则使用专用的`PACMAN_AUTH`钩子，让依赖事务直接发生在当前用户拥有的环境中：

```bash
PACMAN_AUTH=(linsys2-makepkg --pacman-auth)
```

这个钩子还解决了一个动态一致性问题。包装脚本最初是构建开始前根据`bin`目录生成的快照；如果`makepkg -s`随后安装了新的`gcc.exe`或`cmake.exe`，新工具就会暂时缺少裸命令入口。后续构建可能报错，也可能悄悄落到PATH中的宿主工具链，把宿主对象混入软件包。

`PACMAN_AUTH`正好只包装修改软件包状态的事务，不包裹查询操作，因此成为合适的刷新时机。每次成功的pacman事务后，钩子都会重新扫描目标环境并更新`build-bin`：新安装的工具立即获得包装脚本，已经删除的工具则移除过期入口。

这里也能看出技术选型之间的相互影响。ALPM hook依赖的scriptlet执行路径已被LinSYS2在Linux端跳过，makepkg现有的`PACMAN_AUTH`因而成为干净、可靠的扩展位置。配合fakeroot要求的调整，整个依赖安装与构建过程都保持在用户权限之内。

## 构建状态管理与自动化测试

Wine前缀既是执行环境，也是共享状态。`linsys2-makepkg`会在构建前后重启所选前缀的wineserver，因此两个共享同一环境的并发构建可能相互终止进程。为此，实现加入了环境级非阻塞锁：同一环境同一时间只允许一个构建，`MINGW_ARCH`指定的多个环境则按顺序处理。

默认情况下，各环境使用自己独立的Wine前缀；也可以通过`--prefix`指定已有前缀。无论选择哪一个，都需要把构建前后会终止其中Windows进程这一行为纳入使用方式，最好让构建与日常运行Windows程序使用不同前缀。

测试策略也随着这些兼容层建立起来。包装脚本的生成与清理、带空格或引号的路径、`.bat`处理、`cygpath`转换、`uname`选项、环境锁和pacman初始化都有对应的单元测试。项目原有的shell入口同时重组为Python包，Meson统一管理构建与安装，为这些行为提供持续验证。

目前`check()`默认关闭，因为测试套件经常依赖MSYS2对无`.exe`后缀程序的执行语义；需要运行时可以传入`--check`。对于包含特殊Windows构建步骤的软件包，仍可能需要针对性的调整。

## 结语

`linsys2-makepkg`带来的新能力很直观：在Linux上读取MSYS2现有的PKGBUILD，自动安装依赖，使用官方Windows工具链完成构建，再生成可由MSYS2自带的pacman直接安装的软件包。

更有价值的是实现这项能力时形成的技术结构。Linux原生makepkg保留成熟的打包流程，Wine提供Windows程序执行能力，包装脚本保留命令入口与模块定位，`binfmt_misc`接通新生成的PE程序，`bubblewrap`统一规范路径，特殊命令脚本提供目标平台语义，pacman与`PACMAN_AUTH`则让依赖和包装入口在构建过程中持续同步。

这些机制在逐一解决混合构建中的路径、执行、平台身份和状态一致性问题后，组合成一套完整方案。LinSYS2也由此完成了从“使用MSYS2软件包”到“参与MSYS2软件包生产”的转变。

* **项目地址**：[https://github.com/wszqkzqk/LinSYS2](https://github.com/wszqkzqk/LinSYS2)
* **AUR地址**：[linsys2](https://aur.archlinux.org/packages/linsys2/)
* **上一篇介绍**：[LinSYS2：无需虚拟机与容器，在Linux上完整管理、构建、调试与运行Windows程序](https://wszqkzqk.github.io/2026/04/27/LinSYS2/)
* **开源协议**：[GPL v2 or later](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html)
