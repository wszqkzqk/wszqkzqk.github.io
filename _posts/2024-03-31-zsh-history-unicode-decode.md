---
layout:     post
title:      解码含有Unicode的zsh历史记录
subtitle:   Zsh历史记录编码解析
date:       2024-03-31
author:     wszqkzqk
header-img: img/media/bg-modern-img-comp.webp
catalog:    true
tags:       系统配置 系统维护 开源软件 Zsh
---

## 前言

虽然笔者自去年年初就已经从`zsh`切换到了`fish`，但是在Windows平台下，由于`fish`的路径兼容性问题，笔者在需要使用类Unix Shell时仍然使用`zsh`。

相比与`fish`开箱即用的功能，`zsh`支持的很多特征往往都需要手动配置，不过如果配置得当，`zsh`的功能也是非常强大的。

然而，有一个问题困扰笔者很久，那就是`zsh`的历史记录编码问题：如果使用一般的文本编辑器打开`~/.zsh_history`，会发现其中的Unicode字符都是乱码，这将导致无法手动编辑历史记录，也难以将历史记录导出。

## 原因

`zsh`的历史记录并非直接使用UTF-8编码，而是使用了一种[特殊的元格式编码](https://www.zsh.org/mla/users/2011/msg00154.html)。这种编码的格式如下：

* Unicode字节前加上了元字节`0x83`开头
* 后续的内容需要与`32`进行异或运算才能得到原始值

因此，如果要解码`zsh`的历史记录，需要先找到`0x83`开头的字节，将其后面的内容转化为与`32`进行异或运算的值，才能得到结果。

## 解码实现

笔者使用Vala语言编写了一个简单的解码工具，代码如下：

```vala
// In place unmetafy
public unowned string unmetafy_in_place (string s) {
    const char META = 0x83;
    for (var p = (char*) s, t = p; *t != '\0'; t += 1, p += 1) {
        if (*p == META) {
            p += 1;
            *t = *p ^ 32;
        } else {
            *t = *p;
        }
    }
    return s;
}

// Unmetafy with StringBuilder
public string unmetafy (string s) {
    const char META = 0x83;
    var builder = new StringBuilder ();
    for (var t = (char*) s; *t != '\0'; t += 1) {
        if (*t == META) {
            *(t + 1) ^= 32;
        } else {
            builder.append_c (*t);
        }
    }
    return builder.free_and_steal ();
}

void main () {
    Intl.setlocale ();
    string line;
    while ((line = stdin.read_line ()) != null) {
        unmetafy_in_place (line);
        print ("%s\n", line);
    }
}
```

编译并使用该工具，即可解码`zsh`的历史记录：

```bash
$ valac unmetafy.vala
$ cat ~/.zsh_history | ./unmetafy
```
