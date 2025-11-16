---
layout:     post
title:      利用Android手机硬件进行高效灵活的编解码
subtitle:   在Termux中启用硬件加速视频编解码
date:       2025-10-26
author:     wszqkzqk
header-img: img/media/bg-hardware-acceleration-darken.webp
catalog:    true
tags:       Termux Android FFmpeg 开源软件 媒体编解码
---

## 前言

> 本文介绍了如何在Termux中启用MediaCodec硬件加速，以充分利用Android手机的硬件资源进行媒体编解码。

随着移动设备性能的提升，手机已经能够胜任越来越多的计算密集型任务。在短视频行业的驱动下，手机的视频解码能力得到了显著提升；同时，用户对高清摄影的要求也促使硬件厂商不断优化其视频编解码性能。如今，手机的硬件编解码越来越强大，能够越来越省电、高效地处理高清视频内容。

Termux作为Android平台上的一个强大终端模拟器和Linux环境，允许用户在手机上运行各种开源软件。然而，默认情况下，Termux中的软件通常只能使用CPU进行计算，无法充分利用手机的专用视频编解码硬件加速单元，使得某些任务的速率大打折扣。本文将介绍如何在Termux中启用硬件加速，以提升媒体处理的效率。

## 背景

FFmpeg是一个广泛使用的开源多媒体处理工具，支持多种音视频格式的编解码，其基础的使用方法可以参见[笔者之前的博客](https://wszqkzqk.github.io/2023/01/01/FFmpeg%E7%9A%84%E5%9F%BA%E7%A1%80%E4%BD%BF%E7%94%A8/)。FFmpeg支持多种硬件加速技术，包括跨平台的Vulkan和Android平台上的MediaCodec等。

笔者首先计划尝试在Termux中使用Vulkan进行硬件加速编解码，然而，**各Android硬件厂商的Vulkan实现并不支持视频编解码**功能，因此这里FFmpeg无法使用Vulkan进行硬件加速。在使用Vulkan解码时也有如下报错：

```log
Device creation failed: -12.
[vist#0:0/vp9 @ 0xb400007697414d50] [dec:vp9 @ 0xb4000077b7410b10] No device available for decoder: device type vulkan needed for codec vp9.
[vist#0:0/vp9 @ 0xb400007697414d50] [dec:vp9 @ 0xb4000077b7410b10] Hardware device setup failed for decoder: Out of memory
```

后来，笔者尝试在Termux中使用MediaCodec进行硬件加速编解码。MediaCodec是Android平台提供的一个用于视频编解码的硬件加速API，能够充分利用手机的硬件资源。通过在FFmpeg中启用MediaCodec支持，笔者成功实现了在Termux中使用硬件加速进行视频编解码。

## 安装与配置

自FFmpeg 6开始，FFmpeg即引入了不依赖于JVM的MediaCodec支持。在Termux中，FFmpeg 7以来的MediaCodec支持是**开箱即用**的：

```bash
pkg install ffmpeg
```

不过，Termux中如果需要访问手机存储目录下的文件，需要先授予存储权限：

```bash
termux-setup-storage
```

运行并完成授权后，即可自由访问`/sdcard`（即手机文件管理器顶级目录）下的文件。

## 基础使用

使用`-hwaccel mediacodec`参数可以启用MediaCodec硬件加速解码，而使用`<encoder>_mediacodec`（例如`h264_mediacodec`、`hevc_mediacodec`等）可以启用MediaCodec硬件加速编码。

一般来说，我们可以使用形如这样的命令，利用MediaCodec进行硬件加速编解码：

```bash
ffmpeg -hwaccel mediacodec \
    -i <input_file> \
    -pix_fmt yuv420p \
    -c:v <encoder>_mediacodec <output_file>
```

部分编码器可能不支持`yuv420p`像素格式，可以改为使用`nv12`等格式，下同。

此外，对于较罕见的奇数分辨率视频，还需要额外处理：

```bash
ffmpeg -hwaccel mediacodec \
    -i <input_file> \
    -vf "crop=trunc(iw/2)*2:trunc(ih/2)*2" \
    -pix_fmt yuv420p \
    -c:v <encoder>_mediacodec <output_file>
```

这里值得注意的是`-vf "crop=trunc(iw/2)*2:trunc(ih/2)*2"`参数，因为MediaCodec编码器**通常要求输入视频的宽高必须是偶数**，如果没有这个参数，在宽高为奇数时可能会导致编码失败。

> ### FFmpeg 7.1.1中MediaCodec的严重Bug（已修复）
>
> **截至2024年10月27日，该问题已经在FFmpeg 7.1.2中修复。**
>
> 然而，FFmpeg 7.1.1的NDK dMediaCodec支持存在**严重Bug**，导致**输出分辨率存在错误**，只会给出相当小的视频分辨率，并且似乎仅截取了视频的部分。[^1] [^2]
>
> [^1]: [termux/termux-packages#22899 — FFMPEG transcoding with mediacodec first keyframe missing or damaged after ffmpeg update](https://github.com/termux/termux-packages/issues/22899)
> [^2]: [termux/termux-packages#23014 — ffmpeg mediacodec decoder outputs wrong dimensions](https://github.com/termux/termux-packages/issues/23014)
>
> 对此，可以暂时使用软件解码来避免这个问题：
>
> ```bash
> ffmpeg -i <input_file> \
>     -vf "crop=trunc(iw/2)*2:trunc(ih/2)*2" \
>     -pix_fmt yuv420p \
>     -c:v <encoder>_mediacodec <output_file>
> ```
>
> FFmpeg 7.1.2及更高版本已经修复了该问题，可以正常使用`-hwaccel mediacodec`进行硬件加速解码。

## 硬件编解码支持情况查看

有时候，我们可能希望了解硬件编解码器的功能支持情况，我们当然可以通过尝试来确定，但其实也有更加方便的方法。

在Google Play或者其他应用商店中安装Device Info HW应用，打开后选择“编解码器”选项卡，可以查看设备的编解码器支持情况。其中，以`c2.<vendor>`或者`OMX.<vendor>`开头的条目**一般**为对应的硬件编解码器（`<vendor>`代表芯片制造商，例如`c2.mtk.hevc.decoder`为联发科的HEVC硬件解码器），而形如`OMX.google`或者`c2.android`的条目则为软件编解码器。具体是否为硬件编解码器，可以点击查看详情页中的`Hardware acceleration`字段，若显示为`yes`则为硬件编解码器。

|[![#~/img/android/device-info-hw/device-info-hw-decoder.webp](/img/android/device-info-hw/device-info-hw-decoder.webp)](/img/android/device-info-hw/device-info-hw-decoder.webp)|[![#~/img/android/device-info-hw/device-info-hw-encoder.webp](/img/android/device-info-hw/device-info-hw-encoder.webp)](/img/android/device-info-hw/device-info-hw-encoder.webp)|
|:----:|:----:|
|视频解码器支持|视频编码器支持|

例如，从这里可以看出，笔者搭载天玑7200 Ultra的Redmi Note 13 Pro+支持H.264、HEVC、VP8和VP9的等多种格式的硬件解码，但是只支持H.264和HEVC的硬件编码；此外，该设备不支持AV1硬件解码，也不支持AV1硬件编码。

点击详情页，还可以查看该编解码器支持的最大分辨率、帧率等：

|[![#~/img/android/device-info-hw/device-info-hw-vp9-decoder.webp](/img/android/device-info-hw/device-info-hw-vp9-decoder.webp)](/img/android/device-info-hw/device-info-hw-vp9-decoder.webp)|[![#~/img/android/device-info-hw/device-info-hw-hevc-decoder.webp](/img/android/device-info-hw/device-info-hw-hevc-decoder.webp)](/img/android/device-info-hw/device-info-hw-hevc-decoder.webp)|[![#~/img/android/device-info-hw/device-info-hw-hevc-encoder.webp](/img/android/device-info-hw/device-info-hw-hevc-encoder.webp)](/img/android/device-info-hw/device-info-hw-hevc-encoder.webp)|
|:----:|:----:|:----:|
|VP9硬解解码支持详情|HEVC硬件解码支持详情|HEVC硬件编码支持详情|

例如，从这里可以看出，笔者的设备VP9和HEVC硬件解码器均是最高支持4096x2176分辨率，HEVC硬件编码器则最高支持3840x2176分辨率。~~MTK几乎是比着4K的最低标准在做硬件编解码支持，十分抠门~~。

对于设定了`-hwaccel mediacodec`但解码器不支持的格式，FFmpeg会**自动回退**到软件解码，因此不会报错。（目前应该只有指定为Vulkan硬解时在这种情况下会报错）但是对于编码，如果指定了不支持的硬件编码器，则会报错。

## 质量控制

MediaCodec编码器支持的质量控制方法与常规编码器有所不同。MediaCodec支持以下几种质量控制模式，通过`-bitrate_mode`参数进行指定：

- `0`：恒定质量（CQ，Constant Quality）
- `1`：可变码率（VBR，Variable Bitrate）
- `2`：恒定码率（CBR，Constant Bitrate）
- `3`：允许丢帧的恒定码率（CBR with frame dropping）

对于不需要即时传输的本地转码任务，建议使用恒定质量（CQ）模式，以获得稳定、一致的输出质量。MediaCodec的CQ模式通过`-global_quality:v`参数进行质量控制，范围为`1`（最低质量）到`100`（最高质量）。例如，如果想获得较高质量的视频，可以设置为`80`（想要极小的体积则可以尝试`40-50`，当然，具体需要依设备和场景而定）：

```bash
ffmpeg -hwaccel mediacodec \
    -i <input_file> \
    -pix_fmt yuv420p \
    -c:v <encoder>_mediacodec \
    -bitrate_mode 0 \
    -global_quality:v 80 \
    <output_file>
```

设置`-global_quality:v`可以间接控制质量因子（QP）的大小，从而影响输出视频的质量和文件大小。较高的质量值通常会导致更好的视觉质量，但也会增加文件大小。

不过笔者发现，码率限制设定在当前设备HEVC的MediaCodec中控制力并不太有效，输出视频的实际码率可能会比设定值大不少。（即有些视频存在**码率“压不下来”**的情况）此外，对于某些设备的某些编码器，可能不支持某些质量控制模式：

|[![#~/img/android/device-info-hw/device-info-hw-hevc-encoder.webp](/img/android/device-info-hw/device-info-hw-hevc-encoder.webp)](/img/android/device-info-hw/device-info-hw-hevc-encoder.webp)|[![#~/img/android/device-info-hw/device-info-hw-avc-encoder.webp](/img/android/device-info-hw/device-info-hw-avc-encoder.webp)](/img/android/device-info-hw/device-info-hw-avc-encoder.webp)|
|:----:|:----:|
|HEVC硬件编码支持详情|AVC硬件编码支持详情|

由图，笔者的设备HEVC的硬件编码器完整支持了CBR、VBR和CQ三种质量控制模式，而AVC的硬件编码器则只支持VBR这一种质量控制模式，且不能通过`-global_quality:v`参数进行质量控制。

这可能是因为针对移动端高度优化的编码器在设计的时候为了在该场景下更重要的因素——极高的能效比和不错的速率，牺牲了编码的灵活性和可控性，~~降本增效了~~。

### 精细控制：FFmpeg 8.0及更高版本

自FFmpeg 8.0开始，FFmpeg引入了对I帧、P帧和B帧的单独质量控制支持，可以分别设置其质量因子上限和下限，从而实现更加精细的质量控制，这使得利用MediaCodec进行编码时可以更好地控制视频质量，功能更加强大。可以使用以下参数进行设置：

```
  -qp_i_min          <int>        E..V....... minimum quantization parameter for I frame (from -1 to INT_MAX) (default -1)
  -qp_p_min          <int>        E..V....... minimum quantization parameter for P frame (from -1 to INT_MAX) (default -1)
  -qp_b_min          <int>        E..V....... minimum quantization parameter for B frame (from -1 to INT_MAX) (default -1)
  -qp_i_max          <int>        E..V....... maximum quantization parameter for I frame (from -1 to INT_MAX) (default -1)
  -qp_p_max          <int>        E..V....... maximum quantization parameter for P frame (from -1 to INT_MAX) (default -1)
  -qp_b_max          <int>        E..V....... maximum quantization parameter for B frame (from -1 to INT_MAX) (default -1)
```

不过事实上大多数Android设备在默认情况下并不支持B帧编码，因此`-qp_b_min`和`-qp_b_max`通常不会起作用。此外，必须要保证`-bitrate_mode`设置为`0`（CQ模式），否则这些参数也不会起作用。

## 实际表现

笔者发现，使用MediaCodec进行硬件加速编解码在Termux中效果显著，能够大幅提升视频处理的能效。通过合理配置质量控制参数，可以在保证视频质量的同时，充分利用手机的硬件资源。

笔者使用MediaCodec硬件解码与编码，将VP9编码的4K（3840x2160）视频转编码成了HEVC。下图展示了MediaCodec硬件编解码的速率与功耗表现：

|[![#~/img/android/termux/ffmpeg-hardware-mediacodec-power.webp](/img/android/termux/ffmpeg-hardware-mediacodec-power.webp)](/img/android/termux/ffmpeg-hardware-mediacodec-power.webp)|
|:----:|
|速率与功耗展示|

笔者使用了搭载天玑7200 Ultra的Redmi Note 13 Pro+进行测试。如图，此时电流为531 mA，整体电流大概在500-700 mA间，按照手机电池在4 V左右来计算，**整机功耗仅为2-3 W**。考虑到笔者的手机还有200-300 mA的空载基础功耗，实际用于视频编解码的功耗大约在**1-2 W，甚至更低**，而处理4K视频的速率则达到了**约45 FPS**，表现相当出色。

如果使用笔者笔记本电脑搭载的AMD Ryzen 5800H的**硬件编码**，在相同的任务下即使使用新的Vulkan API，封装功耗达到5 W（已经很不错了，远低于VAAPI；空载3 W左右）,整机更是接近15 W（空载9-10 W）。

当然，手机跟电脑比功耗是“不讲武德”的，但就算**不管功耗**，**5800H在输出速度（38 FPS）、质量上还没有任何优势**。可见，手机在视频编解码能效和性能上的优化是十分显著的。~~(也可以看出AMD对编解码是多么不上心)~~

可见，在对视频没有精细的码率控制的需求下，使用Android手机，在Termux下利用FFmpeg的MediaCodec API硬件加速编解码，是一个十分高效的解决方案。~~（5800H还是只用来SVT-AV1软件编码吧）~~

## 结语

利用MediaCodec和FFmpeg在Termux中进行全面硬件加速的视频编解码实测表现出色，实现了极高的视频处理的效率和能效。在手机消费者对短视频和高清摄影日益增长的需求推动下，现代手机的硬件编解码无论在能效、质量还是速度上，都有着非常优秀的表现，只是在编码的可控性和灵活性上有所欠缺（FFmpeg 8.0的更新部分弥补了这一点）。在能够接受这些限制的场景下，使用手机进行硬件加速编解码是一个非常值得推荐的方案。

此外，利用手机的闲置时段进行视频转码任务可谓是非常环保。笔者成功使用手机将若干保存的AVC编码的高清电影转码为HEVC编码，通过控制质量因子，**节省了大量存储空间**；同时，仅利用了手机闲置待机时间完成了转码任务，电量开销也不大，全硬件编解码场景中手机**完全没有可感知发热**，**质量**观感也比5800H的硬件编码**更优**。这可以作为高效利用闲置资源的一个范例。
