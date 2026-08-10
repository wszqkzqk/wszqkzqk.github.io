---
layout:       post
title:        SVT-AV1-HWY：用 Google Highway 为 SVT-AV1 添加可移植 SIMD
subtitle:     面向 LoongArch、RISC-V 等缺少手写 SIMD 的架构的高效优化方案
header-img:   img/bg-sunrise.webp
date:         2026-08-10
author:       wszqkzqk
catalog:      true
tags:         SIMD 国产硬件 龙芯 RISC-V 媒体编解码 开源软件
---

## 背景

SVT-AV1 是目前速度最快的 AV1 软件编码器之一，不过它在不同 CPU 架构上的优化程度相差很大。x86 有从 SSE2 到 AVX-512 的多级实现，AArch64 也有 NEON、SVE 和 SVE2；到了 RISC-V、LoongArch、ppc64le 等架构，编码器就只能使用 C 实现。

这些 C 实现经过编译器优化后，有些循环也会生成向量指令，但效果很难与专门编写的 SIMD kernel 相比。在一台双路龙芯 3C5000L 上，我用 FFmpeg 8.1.2 和默认参数编码一段 4K 视频，上游版本只能达到 0.151 倍实时，也就是约 3.6 fps。

为每种架构分别重写一遍热点 kernel，维护成本会很高。我希望只写一套向量代码，再由编译器将它映射到各平台的 SIMD 指令。Google Highway 为此提供了一组统一的向量操作：构建时为当前架构的不同指令集目标分别生成实现，运行时再选择 CPU 支持的最佳版本。相同的 kernel 因而可以落到 LoongArch 的 LSX/LASX、RISC-V 的 RVV，也可以落到 x86 的 AVX2/AVX-512。

其实，libaom 已经在 2025 年开始引入 Highway kernel。这次我把类似的做法接进了编码效率极高的 SVT-AV1，并将重点放在原本没有手写 SIMD 的架构上。代码位于 [SVT-AV1-HWY](https://github.com/wszqkzqk/SVT-AV1-HWY)，相关提案也已提交至上游：[SVT-AV1#2389](https://gitlab.com/AOMediaCodec/SVT-AV1/-/work_items/2389)。

## 接入 SVT-AV1 的 RTCD

SVT-AV1 通过 RTCD（runtime CPU dispatch）函数指针表选择各个 kernel。表项起初指向 C 参考实现，随后按 CPU 能力替换成相应的汇编版本。我把 Highway 的注册放在这个流程的末尾，并规定它只替换仍然指向 C 参考实现的表项：

```c
if (rtcd_ptr == c_reference_fn)
    rtcd_ptr = hwy_getter();
```

这段判断保留了 x86 和 AArch64 上已有的手写优化，这两个平台默认也不编译 Highway。在其他架构上，Highway 默认启用，找不到依赖时则继续使用 C 实现。另有一个 `--asm hwy` 档位，可以在 x86 或 AArch64 机器上单独测试 Highway；`--asm c` 仍然表示纯 C。

Highway 注册时要将函数指针与 C 实现比较，因此 C 实现必须保留在函数表里。AArch64 构建默认定义 `CONFIG_ARM_NEON_IS_GUARANTEED`，通常会省去一部分 C 实现；但在 `--asm c` 或 `--asm hwy` 下，这会留下空函数指针。现在只要启用 Highway，就会保留这些 C 实现，供纯 C 模式和 Highway 注册使用。

每个 `*_hwy.cc` 文件会通过 `hwy/foreach_target.h` 为当前架构的多个目标重复编译。`HWY_DYNAMIC_POINTER` 在初始化时解析出最佳实现，热路径上仍然只是一次普通的函数指针调用，不需要每次重新检测 CPU。

kernel 本身使用 `ScalableTag`，不在源码里写死 128、256 或 512 位向量宽度。每行末尾不足一个完整向量的部分由 `LoadN` 读取。它只访问指定数量的元素，并将向量中的空余通道填零，因此不需要再用标量循环处理剩余元素。

## 覆盖范围与正确性

目前的实现覆盖约 24 组函数，包括 SAD、方差与亚像素方差、卷积、帧内预测、CDEF、去块与环路恢复、时域滤波、正逆变换、量化、compound 混合，以及若干图像和质量评估算子。逐项清单放在仓库的 [Highway 设计文档](https://github.com/wszqkzqk/SVT-AV1-HWY/blob/master/Docs/Appendix-Highway-Portable-SIMD.md) 中，正文不再展开罗列。

所有已实现的 kernel 都接入了相应的 gtest，用随机输入覆盖不同块尺寸，并与 C 实现逐位比较。在端到端测试中，AArch64 和 LoongArch64 上的 `--asm c`、`--asm hwy` 与 `--asm max` 也生成了逐字节相同的码流。

通过正确性测试后，每个 kernel 还要与编译器优化过的 C 实现比较性能。有些小 kernel 的 C 版本已经相当快；如果 Highway 在验证机上没有胜过它，我会保留实现和测试，让 RTCD 表继续使用 C。

## 根据微基准逐项优化

主要 kernel 刚接通时，各个块尺寸已经能够处理，多目标编译也能正常工作，测试结果与 C 参考逐位一致。当时的重点是先保证移植正确，循环结构大多沿用 C 实现，只把其中的运算换成 Highway API。

完成正确性验证后，我在 M4 Pro 上直接调用 RTCD 函数指针，逐项比较 C、Highway 和手写 NEON。每项重复多次取最小值。微基准很快暴露出问题：variance、subpel variance、convolve 和 `nxm_sad` 的 Highway 实现比 NEON 慢 1.9 到 3.7 倍，subpel variance 甚至没有跑过自动向量化的 C。接下来几次改写都从这些数据出发，再对照 Highway 与 NEON 的反汇编定位多出来的指令。

### SAD：换一种累加方式

SAD 做的是绝对差求和。初始实现直接使用 `SumsOf8AbsDiff`，但这个操作在 NEON 后端没有对应的单条指令，会展开成多级配对求和。改写后先用 `AbsDiff` 求绝对差，再用 `SumsOf2` 累加到 16 位通道；在 NEON 上，这正好对应 `UABD` 和 `UADALP`。16 位累加器会按照溢出上限定期折叠进 32 位总和，因此仍然得到精确结果。

`svt_nxm_sad_kernel` 的宽度在运行时才知道。旧实现每处理一行都重新计算完整向量块和剩余像素的处理方式；现在改为每次调用只按宽度分派一次，再进入特化后的行循环。两处调整完成后，64×64 的 `nxm_sad` 从 NEON 的 2.13 倍耗时降到了基本持平。

### variance：让点积指令做归约

方差需要同时计算像素差之和与平方差之和。最初的 `SumsOf8` 和 `WidenMulPairwiseAdd` 会生成较长的配对累加链。现在两部分都使用 `SumOfMulQuadAccumulate`：支持点积的目标可以直接生成 NEON `UDOT` 或 x86 VNNI，没有点积指令的目标则由 Highway 展开成普通乘加。

每个列块还使用独立的累加器，避免所有向量都排在同一条依赖链上。`variance64x64` 的 Highway 耗时由约 239 ns 降到 66 ns，已经与手写 NEON 的 65 ns 无实质差别。

### subpel variance：问题出在循环结构

亚像素方差的初始实现比 C 还慢：818 ns 对 733 ns。反汇编显示，按行处理的 lambda 没有内联，累加器被溢出到栈上；`LoadN` 的读取长度又是运行时值，内层循环不断重复分支和 load/store。

重写后，循环改为一次处理一个向量宽的列块，再从上到下完成滤波。滑动窗口和累加器可以一直留在寄存器里，水平滤波结果用双缓冲复用；偏移为零时，`{128, 0}` 滤波器等价于直接复制，这条路径也通过模板参数在编译期消除。耗时由 818 ns 降到 280 ns，接近手写 NEON 的 260 ns。

优化后的实现仍然保留了几处短小的 lambda，并且能够正常内联。这里应该依据最终生成的代码判断；抽象层本身不会保证内联，也不会替开发者消除内层的动态分支。

### convolve：复用行数据，并利用系数性质

旧版垂直卷积为每个输出行重新加载完整的 8 行窗口。新版先保留 7 行向量，每次再加载 4 行，连续算出 4 个输出行，然后轮换寄存器。随着窗口向下移动，每个源数据行只需加载一次。

AV1 当前使用的滤波器系数都是偶数，因此可以先把系数除以二，在 16 位通道中完成乘加；最大中间值为 23460，不会溢出，最后调整移位量即可保持逐位一致。二维卷积的中间偏置也可以省去：垂直滤波器的系数和恒为 128，这个偏置会在下一阶段精确抵消。

这些改动把 `convolve_y_sr` 从 944 ns 降到 350 ns，把 `convolve_2d_sr` 从 2881 ns 降到 1300 ns。它们仍分别比手写 NEON 慢约 1.27 和 1.62 倍，但差距已经不再来自重复加载和不必要的加宽运算。

### 有些实现就不该注册

优化过程中，我也重新检查了先前因性能不佳而未注册的 13 个 kernel。`build_compound_diffwtd_mask_d16`、`wedge_sse_from_residuals` 和 `upsample_intra_edge` 在调整数据宽度或存储方式后超过了 C，可以正式启用；`cfl_luma_subsampling_420` 等函数虽然有所改善，仍然不够快，RTCD 表继续指向 C 实现。

`noise_tx_filter` 是一个很典型的反例。我原以为保留交织布局、避免解交织会更省指令，实测却慢了约 40%。这个思路在 AVX2 上可能成立，因为 x86 需要多条 shuffle；NEON 的 `LD2/ST2` 一条指令就能完成交织访问，绕开它反而增加了后续计算。最终我撤销了这次改写，也没有注册 Highway 版本。

注册前必须与自动向量化后的 C 实测比较，源码看起来“已经向量化”说明不了性能。同一种改写在不同指令集上的代价也可能相反，作为通用实现，只能保证通常情况下的性能。

## 优化后的性能

完成上述调整后，我重新测试了 Highway 的整体表现。龙芯测试使用双路 3C5000L（LA464），以 Clang 构建。FFmpeg 命令如下，三组数据使用同一个输入文件和默认编码参数：

```bash
ffmpeg -i input.webm -c:a copy -c:v libsvtav1 -f null - -benchmark
```

| 构建 | 编码速度 | 相对上游 |
| --- | --- | --- |
| 上游（C + 自动向量化） | 0.151×（3.6 fps） | 1.0 |
| Highway（LSX） | 0.404×（9.7 fps） | 2.7 倍 |
| Highway（LASX） | 0.440×（11 fps） | 2.9 倍 |

这是包含输入解码开销的端到端结果，因而会低估编码器本身的加速幅度。LSX 一行是限制指令集后的对照；3C5000L 正常运行时会选择 LASX，速度比 LSX 还要快约 9%。

Apple M4 Pro 上的对照测试使用 1080p、300 帧、preset 8，表中为三轮中位数：

| 档位 | 帧率 | 相对纯 C |
| --- | --- | --- |
| `--asm c` | 45.5 fps | 1.0 |
| `--asm hwy` | 124.1 fps | 2.7 倍 |
| `--asm max`（原生 NEON） | 135.0 fps | 3.0 倍 |

Highway 达到了原生 NEON 约 92% 的端到端性能。逐 kernel 的最终微基准如下，单位为 ns/call：

| kernel | C | Highway | 原生 NEON |
| --- | ---: | ---: | ---: |
| sad64x64 | 484 | 45 | 45 |
| nxm_sad64x64 | 488 | 45 | 46 |
| variance64x64 | 338 | 66 | 65 |
| subpel_variance64x64 | 733 | 280 | 260 |
| convolve_y_sr 64x64 | 9813 | 350 | 276 |
| convolve_2d_sr 64x64 | 14605 | 1300 | 803 |
| fwd_txfm2d_32x32 | 2298 | 548 | 360 |

SAD 和方差这类归约操作已经与手写 NEON 基本持平；卷积和变换仍有差距。其中一部分差距来自 NEON 特有的融合指令，Highway 的通用接口不一定能完整表达。

## 工具链与验证范围

LoongArch 上的动态分发目前依赖 Clang。Highway 需要编译器为同一函数分别生成 LSX 和 LASX 版本，而 GCC 的 LoongArch 后端还不支持这种写法。GCC 仍然可以构建项目，但只能使用编译时选定的一个指令集版本，无法在运行时选择 LSX 或 LASX。

目前实际完成构建和运行验证的是 AArch64 与 LoongArch64；RISC-V RVV 和 wasm32 还没有经过编译、测试或性能测量。本文的性能结论只适用于前两个平台。

## 结语

x86 和 AArch64 继续使用成熟且高度优化的手写 SIMD，Highway 则为其他架构提供一套可移植的向量实现。龙芯 3C5000L 正常使用 LASX 时，端到端编码速度提高到上游版本的 2.9 倍，已经弥补了相当一部分性能差距。

Highway 可以让同一份源码复用于多种指令集，底层优化工作仍然少不了。选择哪一种归约操作、循环按行还是按列展开、何时加宽累加器，都会直接影响最后生成的指令。写完可移植 SIMD 后，仍要查看反汇编并逐个测量 kernel。

接下来除了继续跟进上游讨论，我也希望能在真实 RVV 硬件上完成验证。这套实现从一开始就考虑了 RISC-V，但目前还没有实机数据。
