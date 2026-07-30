---
layout:     post
title:      varallel开发踩坑
subtitle:   一个用于并行执行命令的Vala命令行工具
date:       2024-03-21
author:     wszqkzqk
header-img: img/bg-modern-img-comp.webp
catalog:    true
tags:       Vala 开源软件
---

## 前言

笔者曾经在[批量并行的图片转码](https://wszqkzqk.github.io/2023/10/29/批量并行的图片转码/)一文中介绍了`parallel`这个工具，它可以将多个命令行工具的输出进行并行处理，从而充分利用电脑的性能；也可方便地实现参数组的输入，代替较复杂的shell循环等代码（还可以通过多组参数代替嵌套循环等操作）。然而，`parallel`是一个perl程序，包含多达15000行代码，不支持Windows平台，也较难以维护。为了解决这些问题，笔者决定用Vala语言开发一个跨平台的并行执行命令的命令行工具`varallel`。

## 设计

`varallel`在CLI上基本上与`parallel`一致，但也有一些不同：`parallel`默认会按照shell的规则处理替换字符串中的空白字符，而`varallel`为了实现在各shell间的兼容性，不会额外处理替换字符串中的空白字符，仅作直接的替换，因此在某些情况下需要自行在命令模板中添加引号。

笔者选择用Vala语言开发`varallel`主要是因为Vala语言与GLib库的结合使得开发命令行工具变得十分简单，而且跨平台性也较好。

### 使用方法

* Arch Linux用户可以直接从AUR安装体验：

```bash
paru -S varallel
```

这一部分内容也可见于[`varallel`项目GitHub主页](https://github.com/wszqkzqk/varallel)。

```log
Usage:
  varallel [OPTION?] command [:::|::::] [arguments]

Help Options:
  -h, --help                  Show help options

Application Options:
  -v, --version               Display version number
  -j, --jobs=n                Run n jobs in parallel
  -r, --colsep=EXPRESSION     Regex to split the argument
  -q, --quiet                 Hide subcommands output
  -s, --shell=SHELL           Manually set SHELL to run the command, set 'n' to disable to use any shell
  --hide-bar                  Hide progress bar
  --bar                       Show progress bar (Default behavior)
  --print-only                Only print the command but not run

Replacements in cammand:
  {}                          Input argument
  {.}                         Input argument without extension
  {/}                         Basename of input line
  {//}                        Dirname of input line
  {/.}                        Basename of input line without extension
  {#}                         Job index, starting from 1
  {3} {2.} {4/} {1/.} etc.    Positional replacement strings
  
For more information, or to report bugs, please visit:
    <https://github.com/wszqkzqk/varallel>
```

### 说明

* `{}`
  * Input argument. This replacement will be replaced by a full line read from the input source. The input source may be stdin (standard input), `:::`, or `::::`.
* `{.}`
  * Input argument without extension. This replacement string will be replaced by the input with the extension removed. If the input argument contains `.` after the last `/` the last `.` till the end of the string will be removed and `{.}` will be replaced with the remaining.
    * E.g. `foo.webp` becomes `foo`, `subdir/foo.webp` becomes `subdir/foo`, `sub.dir/foo.webp` becomes `sub.dir/foo`, `sub.dir/bar` remains `sub.dir/bar`. If the input argument does not contain. it will remain unchanged.
* `{/}`
  * Basename of input argument. This replacement string will be replaced by the input with the directory part removed.
* `{//}`
  * Dirname of input argument. This replacement string will be replaced by the dir of the input argument.
* `{/.}`
  * Basename of Input argument without extension. This replacement string will be replaced by the input with the directory and extension part removed. It is a combination of `{/}` and `{.}`. 
* `{#}`
  * Sequence number of the job to run. This replacement string will be replaced by the sequence number of the job being run. Starting from `1`.
* `{3}` `{2.}` `{4/}` `{1/.}` `{5//}` etc.
  * Positional replacement strings. This replacement string will be replaced by the corresponding positional argument group. The first group is `{1}`, the second is `{2}`, and so on. Positional arguments can be combined with other replacement options.
* `:::`
  * Read the argument list from the command line.
* `::::`
  * Read the argument list from the files provided as the argument.
* `-j=n` `--jobs=n`
  * Run n jobs in parallel. The default value is the number of logical CPU cores.
* `-r=EXPRESSION` `--colsep=EXPRESSION`
  * User-defined regex to split the argument.
* `-q` `--quiet`
  * Hide subcommands output.
* `-s=SHELL` `--shell=SHELL`
  * Manually set SHELL to run the command, set it to `n` to disable to use any shell, and the subcommands will be spawned directly.
  * If the `--shell` option is not provided, the program will use the shell specified in the **`SHELL` environment variable** in **Unix-like systems**, and **directly spawn the subcommands** in **Windows**.
  * Note: If you use `cmd.exe`, `powershell.exe` and `pwsh.exe` in Windows, arguments contains unicode characters will not be handled correctly.`
* `--hide-bar`
  * Hide progress bar.
  * If both `--hide-bar` and `--bar` are provided, the program will take the last option.
* `--bar`
  * Show progress bar. (Default behavior)
  * If both `--hide-bar` and `--bar` are provided, the program will take the last option.
* `--print-only`
  * Only print the command but not run.

* If there are more than one `:::` or `::::` in the command line, the replacement strings will be the Cartesian product of the argument lists.
  * Example:
    * `varallel echo ::: 1 2 ::: a b`
    * The command will be run with the following arguments:
      * `echo 1 a`
      * `echo 1 b`
      * `echo 2 a`
      * `echo 2 b`

## 开发

`varallel`程序主要有以下几个模块：

* `src/parallelmanager.vala`：并行管理器，负责转化执行参数、管理进程池、分配任务、等待任务完成、输出任务结果等。
* `src/unit.vala`：任务单元，负责执行单个任务。
* `src/reporter.vala`：报告器，负责输出任务进度、执行情况等。
* `src/main.vala`：主程序，负责解析命令行参数、读取并转化命令输入或文件输入、调用并行管理器等。
* `src/version.vala`：版本信息。
* `include/bindings.h`：C语言绑定头文件，主要用于封装跨平台的一些工具函数。

`varallel`程序目前较为简洁，截至目前，`varallel`程序的有效sloc数约800行。

## 踩坑

### `ThreadPool<T>.with_owned_data`中`ThreadPoolFunc<T> func`访问内容的生命周期

Vala编译器是将Vala代码编译为C代码，然后再由C编译器编译为机器码。本质上，Vala语言中的lambda函数仍然是用C语言实现的。为了实现lambda函数，Vala编译器会生成一个结构体，结构体中包含了lambda函数可访问的本地变量等信息。

`ThreadPool<T>.with_owned_data`所接受的参数是`ThreadPoolFunc<T> func`而非`(owned) ThreadPoolFunc<T> func`，因此新建的进程池对象仅会引用`func`，而不会增加`func`的引用计数；如果`func`中访问了某个对象，当`func`所在的scope结束后，`func`可访问的内容可能已经被释放，从而导致访问错误。

因此，我们需要将lambda函数的定义与调用放到同一个作用域中，以避免访问内容被释放。

* 参见提交[fix: fix the problem that the memory has been cleared when the lambda of ThreadPool accesses the fields of ParallelManager](https://github.com/wszqkzqk/varallel/commit/01855343bb5fb0037bceb428e34f2020f83cef39)

### 跨平台进度条与彩色输出的实现

在`varallel`中，我们需要实现进度条与彩色输出。然而，输出彩色字符与进度条还需要额外的信息。

彩色输出可以通过ANSI转义序列实现，但是如果输出被重定向到文件中，这些转义序列会被输出到文件中，从而导致文件内容混乱。因此，我们需要判断输出是否被重定向到文件中，如果是，我们需要禁用彩色输出。这一功能在Unix-like系统中可以通过`isatty`函数实现，如果没有重定向，`isatty`函数返回`1`，否则返回`0`。然而，Windows系统中则需要使用`_isatty`函数，它的返回值也与`isatty`函数有所不同：如果没有重定向，`_isatty`函数返回非0的32位整数值，否则返回`0`。

因此，在不同的平台上我们需要使用不同头文件的不同函数来实现这一功能，这一功能在`include/bindings.h`中定义了一个跨平台的函数来实现。不仅是彩色输出需要这个函数，在判断是否从管道中读取输入时也需要这个函数。

是否显示进度条及进度条该显示多长这一功能也需要跨平台实现。在Unix-like系统中，我们可以通过`ioctl`函数获取终端的宽度，然后根据终端的宽度来决定进度条的长度。然而，Windows系统中则需要使用`GetConsoleScreenBufferInfo`函数来获取终端的宽度。需要注意的是，`varallel`使用的是`stderr`进行输出，因此应当向这些函数传递`stderr`的文件描述符或者handler。此外，这两个函数的返回值还有所不同：`ioctl`函数返回`0`表示成功，`-1`表示失败，`GetConsoleScreenBufferInfo`函数返回`1`表示成功，`0`表示失败。

### Windows的Unicode参数支持

笔者很大程度上是考虑到与Windows的兼容性才决定开发的`varallel`程序。然而，笔者却在Windows平台下测试时发现在参数中含中文时，会有这样的报错：

```bash
SpawnError: 2 处的参数向量中有无效的字符串：转换输入中有无效的字符序列
```

这是因为在Windows系统中，从`main`函数中是无法直接获取正确的Unicode参数的。根据GLib的相关文档，我们可以在Windows下使用`Win32.get_command_line ()`函数来解决这一问题：

```vala
#if WINDOWS
    var args = Win32.get_command_line ();
#else
    var args = strdupv (original_args);
#endif
```

再将转化参数的函数由`OptionContext.parse`改为`OptionContext.parse_strv`，并且在`meson.build`中根据平台类型添加相关的Vala预处理定义：

```meson
if target_machine.system() == 'windows'
  add_project_arguments('-D', 'WINDOWS', language: 'vala')
endif
```

这样理论上就可以在Windows下正确处理Unicode参数了。

然而，笔者在Windows下指定`cmd.exe`、`powershell.exe`和`pwsh.exe`作为shell时，发现参数中含有Unicode字符时会出现乱码。这是因为这些shell将传入的UTF-8参数额外作了转化，导致了乱码，例如如果执行的命令是`echo 你好`：

```log
[Invalid UTF-8] \xc4\xe3\xba\xc3
```

对此，笔者将Windows下的默认进程执行方式执行由`cmd.exe`改为了直接执行，以避免这一问题，然而这样也导致了一些问题，例如无法使用`&&`、`||`等语法。

实际上，这是Windows的`cmd.exe`、`powershell.exe`和`pwsh.exe`自身的问题，如果在Windows下指定shell为msys2或其他程序提供的`bash.exe`、`zsh.exe`、`fish.exe`等，均可以正确处理UTF-8参数。如果既需要传递Unicode参数，又需要使用shell的语法，可以考虑使用这些shell代替Windows自带的shell。

### Vala语言的Bug：以`ref`传参的数组在有`[CCode (array_length = false, array_null_terminated = true)]`标记的函数中的长度

由于C语言绑定中数组的长度有多种获取形式，有的是单独声明一个变量来存储数组的长度（例如`char** argv`，`int argc`），有的仅通过`null`来标记数组的结束而没有附加的长度信息。因此，为了实现与C语言库的兼容，Vala语言对于`array.length`也有多种C实现形式，一般是通过在生成的C代码中声明`array_length`来保存数组的长度，如果该函数声明时用``[CCode (array_length = false, array_null_terminated = true)]`修饰了数组参数则是遍历数组来获取数组的长度。

Vala在一般情况下能够正确处理数组长度的相关问题，例如在增加或删除数组元素时，Vala会自动更新数组的长度；在以`ref`的方式传递数组时，Vala也会自动将数组的长度传递给函数。然而，当数组以`ref`的形式传递给具有`[CCode (array_length = false, array_null_terminated = true)]`标记的函数时，在C语言层面上该函数事实上并不会接收到`array_length`这一参数，也无法对其进行修改。因此，如果在这样的函数中修改了数组的长度，Vala语言并不会更新数组的长度，从而导致了数组的长度与实际不符。

在`varallel`开发中，笔者是在适配Winsows下的Unicode参数传递方式时遇到了这一问题。直接在`main`函数中获取的参数实际上在C语言层面上是一个`char**`类型的数组外加一个`int`类型的长度，接收这一参数的`OptionContext.parse`函数也会接收这两个参数。当`OptionContext.parse`函数解析参数时，将已解析的选项移除时也会同时修改数组的长度，不会出现任何问题。然而，为了在Windows下正确处理Unicode参数，笔者需要采用一份具有所有权的数组（Windows通过`Win32.get_command_line`获得，Linux则调用`strdupv`复制以便保证一致性），而处理这一数组的函数是一个具有`[CCode (array_length = false, array_null_terminated = true)]`标记的`OptionContext.parse_strv`函数，这一函数在C语言层面上并不会接收到数组的长度，也无法对其进行修改。因此，当`OptionContext.parse_strv`函数解析参数时，将已解析的选项移除时也不会修改数组的长度，从而导致了数组的长度与实际不符。

对于这一问题，有一些Woraround：

* 对于循环遍历数组的情况，可以更改判断条件，例如将`for (var i = 2; i < array.length; i += 1)`改为`for (var i = 2; array[i] != null; i += 1)`
* 对于后续使用的函数，如果需要访问`array.length`，可以同样地为传入的数组参数加上`[CCode (array_length = false, array_null_terminated = true)]`修饰，这样在访问`array.length`时Vala会自动调用函数遍历数组来获取数组的长度。

笔者已经在Vala项目的issue中反馈这一问题（[#1536](https://gitlab.gnome.org/GNOME/vala/-/issues/1536)），Vala项目维护者Rico Tzschichholz目前已经修复了这一问题，这一修复([codegen: Update array length variable passed to null-terminated ref parameter](https://gitlab.gnome.org/GNOME/vala/-/commit/43a348b1eebd57a427275ca58a84cd32d30ebb0d)和[codegen: Properly pass through a null-terminated out argument](https://gitlab.gnome.org/GNOME/vala/-/commit/86984c59734f975c9778251dddf80d247ade28a7))将会在Vala 0.58版本中发布。

## 总结

唉，Windows！🤮🤮🤮
