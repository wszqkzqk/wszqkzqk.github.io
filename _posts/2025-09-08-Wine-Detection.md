---
layout:     post
title:      程序检测自身是否在Wine中运行的方法
subtitle:   Wine环境下程序自我检测
date:       2025-09-08
author:     wszqkzqk
header-img: img/wine/wine-bg.webp
catalog:    true
tags:       Wine archlinux 系统配置 开源软件 Vala
---

## 前言

某些时候，我们可能希望程序能够检测自身是否在**Wine**环境下运行。部分开发者可能需要据此做一个环境的统计，分析通过Wine运行程序的用户比例。

然而，对于功能适配，Wine官方建议我们仅**检测功能支持情况**，而[**不应当**检测**是否在Wine中运行**](https://gitlab.winehq.org/wine/wine/-/wikis/Developer-FAQ#how-can-i-detect-wine)。本文介绍的方法仅为暂时可行的技术手段，但**任何**检测程序在Wine下运行的方法都**不受Wine官方推荐**，并且将来可能会在没有任何警告的情况下失效。

本文介绍了几种在不同编程语言中检测程序是否在Wine环境下运行的方法，可供有需要的开发者参考。

## 原理

可以用较为直接的方法检测Wine的存在性，只需要读取`ntdll`中是否存在`wine_get_version`函数即可。该函数在Wine中存在，而在Windows中并不存在。

## 示例代码

### C语言

在C语言中，可以使用以下代码进行检测：

```c
#include <stdio.h>

#include <windows.h>

BOOL is_running_under_wine() {
    HMODULE h_ntdll = GetModuleHandleW(L"ntdll.dll");
    if (!h_ntdll) {
        return FALSE;
    }
    return (GetProcAddress(h_ntdll, "wine_get_version") != NULL);
}

int main() {
    if (is_running_under_wine()) {
        printf("Running under Wine\n");
    } else {
        printf("Not running under Wine\n");
    }
    return 0;
}
```

程序使用了Windows API来获取`ntdll.dll`的模块句柄，并检查`wine_get_version`函数是否存在。如果存在，则说明程序在Wine环境中运行。需要注意的是，相关代码依赖于Windows API，对于跨平台程序，可能需要使用条件编译等方式来处理。

### Python

在Python中，可以使用`ctypes`库来实现类似的功能：

```python
import ctypes

def is_running_under_wine() -> bool:
    try:
        ntdll = ctypes.WinDLL('ntdll.dll')
        return hasattr(ntdll, 'wine_get_version')
    except Exception:
        return False

if __name__ == "__main__":
    if is_running_under_wine():
        print("Running under Wine")
    else:
        print("Not running under Wine")
```

这段代码尝试加载`ntdll.dll`，并检查是否存在`wine_get_version`属性。如果存在，则说明程序在Wine环境中运行。

### Vala

Vala中如果要直接使用Windows API，一般需要自己写VAPI或者声明`extern`函数，可能不那么方便，因此笔者不推荐这种方式。笔者建议直接使用GLib中**GModule**实现的**动态库加载**功能来检测：

```vala
private static bool is_running_under_wine () {
    void* symbol;
    Module? module = Module.open ("ntdll.dll", ModuleFlags.LAZY);
    if (module == null) {
        return false;
    }
    return module.symbol ("wine_get_version", out symbol);
}

void main () {
    if (is_running_under_wine ()) {
        print ("Running under Wine\n");
    } else {
        print ("Not running under Wine\n");
    }
}
```

程序使用GModule中统一实现的跨平台`Module.open`方法加载`ntdll.dll`模块，然后检查是否存在`wine_get_version`符号，更符合GLib/Vala程序的风格，也更加简洁。

下面的代码还进一步展示了如何获取Wine的版本号：

```vala
private static bool is_running_under_wine () {
    void* symbol;
    Module? module = Module.open ("ntdll.dll", ModuleFlags.LAZY);
    if (module == null) {
        return false;
    }
    return module.symbol ("wine_get_version", out symbol);
}

[CCode (has_target = false)]
private delegate string? WineVersionFunc ();

private static string? get_wine_version () {
    void* symbol;
    Module? module = Module.open ("ntdll.dll", ModuleFlags.LAZY);
    if (module == null) {
        return null;
    }
    if (!module.symbol ("wine_get_version", out symbol)) {
        return null;
    }
    WineVersionFunc? func = (WineVersionFunc) symbol;
    if (func == null) {
        return null;
    }
    return func ();
}

void main () {
    if (is_running_under_wine ()) {
        print ("Running under Wine\n");
        string? version = get_wine_version ();
        if (version != null) {
            print ("Wine version: %s\n", version);
        }
    } else {
        print ("Not running under Wine\n");
    }
}
```

这段Vala代码定义了两个函数：`is_running_under_wine`用于检测是否在Wine中运行，`get_wine_version`用于获取Wine的版本号。对于`get_wine_version`函数，笔者在这里还声明了一个`WineVersionFunc`的委托类型，以便将获取到的符号转换为函数指针并调用。

## 背后的故事

笔者写这一篇文章的初衷，实际上并非是想统计Wine使用情况，而是因为在使用Vala编写的命令行程序中遇到了一个问题：**在Wine环境下输出ANSI转义序列会导致输出混乱**。

Windows自Windows 10 1511开始已经支持了ANSI转义序列（ANSI Escape Code Sequence），可以在命令行中使用颜色等功能。然而，在Wine中运行的程序如果直接用标准库的输出函数（如`printf`、`puts`等）输出ANSI转义序列时，无法正确显示颜色等效果，只会显示原始的转义序列，造成输出混乱。

而另一方面，GLib虽然具有跨平台检测是否支持ANSI转义序列的函数`g_log_writer_supports_color`（`Log.writer_supports_color`），但这一方法在Wine下的返回值仍然为真，并不体现标准库函数的行为。

因此，笔者一度计划使用上述的检测方法来判断程序是否在Wine中运行，从而在决定是否输出ANSI转义序列时进行特殊处理，避免在Wine下输出ANSI转义序列导致的输出混乱问题。

然而，考虑到Wine官方[对于检测Wine的态度](https://gitlab.winehq.org/wine/wine/-/wikis/Developer-FAQ#how-can-i-detect-wine)，笔者**一直没有实施**这一计划。

> #### How can I detect Wine?
> This is a bad idea. The goal of Wine is to be compatible enough that an
application should see no difference in behavior, and therefore should
not apply any workarounds, different paths, etc. So any method to detect
running under Wine is unsupported and may break without warning in the
future.

幸运的是，笔者遇到的这一问题在现在已能够得到妥善解决。目前，GLib已经发布了2.86.0版本，修复了`g_print`（`print`）等函数在Windows下的字符集编码问题，补充了正确的**编码转化**过程。现在，虽然在Wine下标准的输出函数仍然无法正确处理ANSI转义序列，但**GLib提供的输出函数已经可以在Windows下正确处理ANSI转义序列**，可以正确显示颜色等效果。因此，笔者最终是将程序的输出函数从标准库的函数改为GLib的实现，从而解决了在Wine下输出ANSI转义序列的问题，实际上从未引入是否在Wine中运行的检测。
