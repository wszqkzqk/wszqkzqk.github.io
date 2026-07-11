---
layout:       post
title:        PvZ-Portable：Android 体验优化两则——native 库直载与 edge-to-edge
subtitle:     优化安装后占用体积与资源导入界面显示
header-img:   img/games/bg-pvz-portable.webp
date:         2026-07-10
author:       wszqkzqk
catalog:      true
tags:         Android NDK 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

PvZ-Portable 最近给 Android 端做了一轮体验优化，其中有两件是普通用户能直接感觉到的：

一是**存储和安装**：游戏的安装后占用从约 16MB 降到 12MB，安装过程还变快了；二是**界面**：负责导入游戏资源的页面不再被状态栏压住。

这两笔改动都不大，合起来也就几十行，但改的都是用户每次安装、每次打开游戏都会碰到的东西。前者（PR [#352](https://github.com/wszqkzqk/PvZ-Portable/pull/352)）是把 native 库从“安装时解压到文件系统”改成“留在 APK 里直接加载”；后者是 Android 15 强制 edge-to-edge 之后的一次适配。本文把这两件事的来龙去脉讲清楚；其中第一件还顺带解决了 Google Play 的 16KB 页大小合规问题，这个放到后面说。

## 两种加载方式

先看改动前 `android/app/build.gradle` 里的这段配置：

```gradle
packaging {
    jniLibs {
        useLegacyPackaging true
    }
}
```

这个开关是早年为了兼容旧设备留下的，效果等价于 manifest 里的 `android:extractNativeLibs="true"`。在它的作用下，native 库走的是 Android 传统的**解压模式**：

1. 打包时 so 以压缩形式塞进 APK；
2. 安装时 PackageManager 把 so 解压到应用私有目录（`/data/app/.../lib/arm64/`）；
3. 运行时动态链接器从文件系统加载这些解压出来的文件。

解压模式虽然能够节约压缩后的 APK 大小，但也存在明显的代价。其一是存储双份：PvZ-Portable 的两个 so（`libmain.so` 和 `libSDL2.so`）未压缩合计约 9.4MB，安装后这 9.4MB 会在数据目录里再躺一份。其二是安装耗时：每次安装或更新都要把 native 库完整解压一遍。

而从 Android 6.0（API 23）开始，系统提供了另一种方式——**直载模式**。在 manifest 里声明 `android:extractNativeLibs="false"` 之后打包时 so 以未压缩形式存入 APK，且在 zip 内按页边界对齐；而且安装时不解压这些 so，运行时动态链接器直接从 APK 里 `mmap` 进内存。

直载模式下，so 在设备上只存一份，就在 APK 里，安装时跳过解压，十分迅速。PvZ-Portable 的**安装后占用**因此从约 16MB 降到 12MB——删掉 9.4MB 的解压副本，再扣除包体变大带来的 5.6MB，净省约 4MB。

## 代价：APK变大

这次切换并不是纯收益。解压模式下 so 压缩存放，APK 只有 6.5MB；直载模式要求 so 未压缩，包体涨到了 12.1MB——两个 so 未压缩合计 9.4MB，占了包体的大头。

旧模式是 6.5MB 的包加上安装后 9.4MB 的解压副本，设备上合计约 16MB；新模式安装大小即 APK 大小，仅 12.1MB。笔者的判断是这笔交换值得做：用户为安装包多付的流量是一次性的，而双份存储的浪费在设备上是持续的。

## 改动内容

核心改动只有两处。一是 manifest：

```diff
     <application
         android:allowBackup="true"
+        android:extractNativeLibs="false"
         android:appCategory="game"
```

二是把 `build.gradle` 里那段 `useLegacyPackaging` 整体删除，它和 `extractNativeLibs="false"` 互斥。完整改动见提交 [4cb6359](https://github.com/wszqkzqk/PvZ-Portable/commit/4cb6359a8f02b3ee6025708781cad95cfc5da402)。

直载能力是 API 23 才引入的。PvZ-Portable 恰好在改动前一天把 minSdk 从 28 下调到了 24（PR [#349](https://github.com/wszqkzqk/PvZ-Portable/pull/349)，为了覆盖更多老设备），24 > 23，两者不冲突。但如果项目的 minSdk 卡在 22 或更低，这套方案就不适用。

## 顺带的收获：16KB 页大小合规

这次改动的分支名叫 `android-16k`，因为最初动它的由头确实是 Google Play 的新规则：从 2025 年 11 月起，targetSdk 指向 Android 15（API 35）及以上、且包含 native 库的应用，必须兼容 16KB 页大小的设备。PvZ-Portable 的 targetSdk 是 36，绕不过去。

16KB 页大小是 Android 15 引入的特性：内核内存页从传统的 4KB 变成 16KB，`mmap` 文件时偏移和长度都必须按 16KB 对齐。加载 so 的本质就是把 ELF 的 `LOAD` 段 `mmap` 进内存，因此合规的第一条要求是 **so 的 `LOAD` 段按 16KB 对齐**（程序头里的 `p_align` 字段不小于 `0x4000`）。这一条对 PvZ-Portable 来说**本来就满足**——NDK r28 起 Clang/lld 链接 Android 目标时默认按 16KB 对齐，项目 CI 一直用最新版 NDK 出包，编出来的 so 天然就是对齐的，网上教程里常提的 `-Wl,-z,max-page-size=16384` 在这里并不需要。

Google 要求 **APK 里的 native 库未压缩且按页对齐**。解压模式下 so 是压缩存放的，哪怕解压出来完全对齐、实际运行毫无问题，这条检查也直接判负。而直载模式恰好以未压缩、页对齐的形态存放 so——也就是说，解决存储浪费的那一步改动，同时把合规问题也解决了。

改动合入后，笔者拿 CI 出的 APK 实跑了一遍检查。手头这台机器没有装 Android SDK 的命令行工具，索性直接用 Python 解析 APK，把三件事一次查清：

```python
import struct, zipfile

APK = "pvz-portable-android-arm64-v8a.apk"
z = zipfile.ZipFile(APK)
for info in z.infolist():
    if not info.filename.endswith(".so"):
        continue
    # 1. 存储方式：0 为 Stored（未压缩）
    # 2. so 数据在 zip 内的起始偏移是否按 16KB 对齐
    with open(APK, "rb") as f:
        f.seek(info.header_offset)
        hdr = f.read(30)
        nlen, elen = struct.unpack_from("<HH", hdr, 26)
    data_start = info.header_offset + 30 + nlen + elen
    print(f"{info.filename}: method={info.compress_type}, "
          f"data_start={data_start}, % 16384 = {data_start % 16384}")
    # 3. ELF 程序头中 LOAD 段的 p_align
    so = z.read(info.filename)
    phoff = struct.unpack_from("<Q", so, 32)[0]
    entsize, num = struct.unpack_from("<HH", so, 54)
    for i in range(num):
        base = phoff + i * entsize
        p_type, = struct.unpack_from("<I", so, base)
        if p_type == 1:  # PT_LOAD
            p_align, = struct.unpack_from("<Q", so, base + 48)
            print(f"    LOAD align=0x{p_align:x}")
```

输出：

```
lib/arm64-v8a/libSDL2.so: method=0, data_start=2097152, % 16384 = 0
    LOAD align=0x4000
    LOAD align=0x4000
    LOAD align=0x4000
lib/arm64-v8a/libmain.so: method=0, data_start=3588096, % 16384 = 0
    LOAD align=0x4000
    LOAD align=0x4000
    LOAD align=0x4000
```

三项测试均通过：so 以未压缩方式存放（`method=0` 即 Stored）、zip 内数据偏移都按 16KB 对齐、每个 `LOAD` 段的 `p_align` 都是 `0x4000`。Google 的合规检查看的就是这几项，到这里基本可以算过了。

要说遗憾也有一点：笔者手边没有 16KB 页模式的设备，真机跑一遍这一步做不了。想验证的话可以建一个 16KB 系统镜像的模拟器，等以后有设备了再补。

## 让导入界面躲开状态栏

第二笔改动是 UI 层面的，也在 PR [#352](https://github.com/wszqkzqk/PvZ-Portable/pull/352) 里。先说背景：从 Android 15 开始，targetSdk 35 及以上的应用会被强制按 edge-to-edge（边到边）方式显示——界面内容延伸到整块屏幕，状态栏和导航栏以半透明形式覆盖在内容之上，而不再像过去那样各自占据一块独立区域。PvZ-Portable 的 targetSdk 是 36，自然也跑不掉。

这对游戏主界面没有影响：它是全屏的 SDL Activity，画面本来就是自己绘制的。但 `ResourceImportActivity` 不一样——这是个普通的 AppCompat 界面，用来让玩家从正版游戏里提取 `main.pak` 等资源文件导入游戏。游戏的入口 Activity 启动时会先检查资源在不在，不在就直接跳到这个导入界面，所以对绝大多数新玩家来说，这就是装完游戏后看到的第一个界面。而 edge-to-edge 生效后，界面顶部的标题和提示会直接钻到状态栏底下去。

修法很标准：开启 edge-to-edge，给根布局挂一个 insets 监听器，把系统栏的高度转成 padding：

```java
EdgeToEdge.enable(this);
setContentView(R.layout.activity_resource_import);
ViewCompat.setOnApplyWindowInsetsListener(findViewById(android.R.id.content), (v, insets) -> {
    Insets bars = insets.getInsets(WindowInsetsCompat.Type.systemBars());
    v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
    return insets;
});
```

`EdgeToEdge.enable` 让内容区域延伸到系统栏背后，`WindowInsetsCompat.Type.systemBars()` 拿到的就是状态栏和导航栏各自的高度，把它们设成根布局的 padding，内容就退回了安全区域。总共 10 行，但对所有正在抬 targetSdk 的项目都适用——只要 targetSdk 过了 35，每一个非全屏的界面都得这样检查一遍。

## 结语

这两笔改动有一个共同的由头：targetSdk 抬到 36 之后，平台规则跟着变了——16KB 页大小合规、edge-to-edge 强制，都是冲着 targetSdk 35 及以上的应用来的。但如果只把它们当成“过检查”来做就亏了：16KB 合规引出的 native 库直载，真正的大头收益其实是安装后占用少了约 4MB、安装跳过解压；edge-to-edge 也不只是适配规则，它修的是新用户导入资源时第一眼看到的界面。


## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
