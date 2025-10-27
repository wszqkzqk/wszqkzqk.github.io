---
layout:     post
title:      在Termux中启用硬件加速
subtitle:   充分利用Android手机硬件进行编解码
date:       2025-10-26
author:     wszqkzqk
header-img: img/media/bg-hardware-acceleration-darken.webp
catalog:    true
tags:       Termux Android FFmpeg 开源软件 媒体编解码
---

## 前言

> 本文介绍了如何在Termux中启用MediaCodec硬件加速，以充分利用Android手机的硬件资源进行媒体编解码。

随着移动设备性能的提升，手机已经能够胜任越来越多的计算密集型任务。在短视频行业的驱动下，手机的视频编解码能力得到了显著提升，手机的硬件编解码越来越强大，能够越来越省电、高效地处理高清视频内容。

Termux作为Android平台上的一个强大终端模拟器和Linux环境，允许用户在手机上运行各种开源软件。然而，默认情况下，Termux中的软件通常只能使用CPU进行计算，无法充分利用手机的专用视频编解码硬件加速单元，使得某些任务的性能大打折扣。本文将介绍如何在Termux中启用硬件加速，以提升媒体处理和AI推理的效率。

## 背景

FFmpeg是一个广泛使用的开源多媒体处理工具，支持多种音视频格式的编解码，其基础的使用方法可以参见[笔者之前的博客](https://wszqkzqk.github.io/2023/01/01/FFmpeg%E7%9A%84%E5%9F%BA%E7%A1%80%E4%BD%BF%E7%94%A8/)。FFmpeg支持多种硬件加速技术，包括跨平台的Vulkan和Android平台上的MediaCodec。

笔者首先计划尝试在Termux中使用Vulkan进行硬件加速编解码，然而，**各Android硬件厂商的Vulkan实现并不支持视频编解码**功能，因此这里FFmpeg无法使用Vulkan进行硬件加速。在使用Vulkan解码时也有如下报错：

```log
Device creation failed: -12.
[vist#0:0/vp9 @ 0xb400007697414d50] [dec:vp9 @ 0xb4000077b7410b10] No device available for decoder: device type vulkan needed for codec vp9.
[vist#0:0/vp9 @ 0xb400007697414d50] [dec:vp9 @ 0xb4000077b7410b10] Hardware device setup failed for decoder: Out of memory
```

后来，笔者尝试在Termux中使用MediaCodec进行硬件加速编解码。MediaCodec是Android平台提供的一个用于视频编解码的硬件加速API，能够充分利用手机的硬件资源。通过在FFmpeg中启用MediaCodec支持，笔者成功实现了在Termux中使用硬件加速进行视频编解码。

## 安装

自FFmpeg 6开始，FFmpeg即引入了不依赖于JVM的MediaCodec支持。在Termux中，FFmpeg 7以来的MediaCodec支持是**开箱即用**的：

```bash
pkg install ffmpeg
```

## 使用MediaCodec进行硬件加速编解码

使用`-hwaccel mediacodec`参数可以启用MediaCodec硬件加速解码，而使用`<encoder>_mediacodec`（例如`h264_mediacodec`、`hevc_mediacodec`等）可以启用MediaCodec硬件加速编码。

一般来说，我们可以使用形如这样的命令，利用MediaCodec进行硬件加速编解码：

```bash
ffmpeg -hwaccel mediacodec \
    -i <input_file> \
    -vf "crop=trunc(iw/2)*2:trunc(ih/2)*2" \
    -pix_fmt yuv420p \
    -c:v <encoder>_mediacodec <output_file>
```

部分编码器可能不支持`yuv420p`像素格式，可以改为使用`nv12`等格式。

这里值得注意的是`-vf "crop=trunc(iw/2)*2:trunc(ih/2)*2"`参数，因为MediaCodec编码器**通常要求输入视频的宽高必须是偶数**，如果没有这个参数，在宽高为奇数时可能会导致编码失败。

然而，目前NDK的MediaCodec支持存在**严重Bug**，导致**输出分辨率存在错误**，只会给出相当小的视频分辨率，并且似乎仅截取了视频的部分。[^1] [^2]

[^1]: [termux/termux-packages#22899 — FFMPEG transcoding with mediacodec first keyframe missing or damaged after ffmpeg update](https://github.com/termux/termux-packages/issues/22899)
[^2]: [termux/termux-packages#23014 — ffmpeg mediacodec decoder outputs wrong dimensions](https://github.com/termux/termux-packages/issues/23014)

对此，可以暂时使用软件解码或者`-hwaccel auto`来避免这个问题：

```bash
ffmpeg -hwaccel auto \
    -i <input_file> \
    -vf "crop=trunc(iw/2)*2:trunc(ih/2)*2" \
    -pix_fmt yuv420p \
    -c:v <encoder>_mediacodec <output_file>
```

## 质量控制

MediaCodec编码器支持的质量控制方法与常规编码器有所不同。MediaCodec支持以下几种质量控制模式，通过`-bitrate_mode`参数进行指定：

- `0`：恒定质量（CQ，Constant Quality）
- `1`：可变码率（VBR，Variable Bitrate）
- `2`：恒定码率（CBR，Constant Bitrate）
- `3`：允许丢帧的恒定码率（CBR with frame dropping）

对于不需要即时传输的本地转码任务，建议使用恒定质量（CQ）模式，以获得稳定、一致的输出质量。MediaCodec的CQ模式通过`-global_quality:v`参数进行质量控制，范围为`1`（最低质量）到`100`（最高质量）。例如，如果想获得较高质量的视频，可以设置为`80`：

```bash
ffmpeg -hwaccel auto \
    -i <input_file> \
    -pix_fmt yuv420p \
    -c:v <encoder>_mediacodec \
    -bitrate_mode 0 \
    -global_quality:v 80 \
    <output_file>
```

设置`-global_quality:v`可以间接控制质量因子（QP）的大小，从而影响输出视频的质量和文件大小。较高的质量值通常会导致更好的视觉质量，但也会增加文件大小。

不过笔者发现，其他质量设置模式，例如码率限制，在MediaCodec中的控制力并不太有效，输出视频的实际码率可能会比设定值大不少，这可能是因为针对移动端高度优化的编码器为了在该场景下更重要的极高的能效比和不错的速率，牺牲了编码的灵活性和可控性。
