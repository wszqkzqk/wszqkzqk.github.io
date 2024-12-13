---
layout:     post
title:      在systemd-nspawn容器中使用硬件加速视频编解码
subtitle:   nspawn容器中使用VA-API硬件加速
date:       2024-12-13
author:     wszqkzqk
header-img: img/FFmpeg_Logo_new.webp
catalog:    true
tags:       FFmpeg 媒体文件 开源软件 媒体编解码
---

## 前言

某些情况下，我们存在在容器中使用硬件加速编解码视频的需求。本文将介绍如何在systemd-nspawn容器中使用硬件加速视频编解码。

## 原理

systemd-nspawn容器是一个轻量级的容器，它可以在不使用虚拟机的情况下提供隔离的环境。在容器中使用硬件加速视频编解码，需要将硬件加速设备映射到容器中。

## 方法

一般来说，硬件加速设备的设备节点位于`/dev/dri`目录下，例如`/dev/dri/renderD128`。我们可以将`/dev/dri`目录映射到容器中，使容器可以访问硬件加速设备。

然而，如果单纯只是使用`--bind`选项将`/dev/dri`目录映射到容器中而没有其他操作，容器中的应用仍不能使用硬件加速设备，例如打开容器：

```bash
sudo systemd-nspawn --bind /dev/dri -bD /path/to/container/root
```

这时如果在容器中运行`vainfo`，会发现无法打开硬件加速设备：

```log
Trying display: wayland
VA error: wayland: failed to open /dev/dri/renderD128
VA error: wayland: failed to open /dev/dri/renderD128: Operation not permitted (errno 1)
VA error: wayland: did not get DRM device
```

这是systemd-nspawn的默认权限设置导致的。我们还需要额外传递`--property=DeviceAllow='char-drm rw'`选项，使容器中的应用可以访问硬件加速设备：

```bash
sudo systemd-nspawn --bind /dev/dri --property=DeviceAllow='char-drm rw' -bD /path/to/container/root
```

这时在容器中运行`vainfo`，就可以正常打开硬件加速设备了：

```log
Trying display: wayland
vainfo: VA-API version: 1.22 (libva 2.22.0)
vainfo: Driver version: Mesa Gallium driver 24.3.1-arch1.4 for AMD Radeon Graphics (radeonsi, renoir, LLVM 18.1.8, DRM 3.59, 6.12.4-zen1-1-zen)
vainfo: Supported profile and entrypoints
      VAProfileMPEG2Simple            : VAEntrypointVLD
      VAProfileMPEG2Main              : VAEntrypointVLD
      VAProfileVC1Simple              : VAEntrypointVLD
      VAProfileVC1Main                : VAEntrypointVLD
      VAProfileVC1Advanced            : VAEntrypointVLD
      VAProfileH264ConstrainedBaseline: VAEntrypointVLD
      VAProfileH264ConstrainedBaseline: VAEntrypointEncSlice
      VAProfileH264Main               : VAEntrypointVLD
      VAProfileH264Main               : VAEntrypointEncSlice
      VAProfileH264High               : VAEntrypointVLD
      VAProfileH264High               : VAEntrypointEncSlice
      VAProfileHEVCMain               : VAEntrypointVLD
      VAProfileHEVCMain               : VAEntrypointEncSlice
      VAProfileHEVCMain10             : VAEntrypointVLD
      VAProfileHEVCMain10             : VAEntrypointEncSlice
      VAProfileJPEGBaseline           : VAEntrypointVLD
      VAProfileVP9Profile0            : VAEntrypointVLD
      VAProfileVP9Profile2            : VAEntrypointVLD
      VAProfileNone                   : VAEntrypointVideoProc
```

此时，可以尝试使用FFmpeg等工具进行硬件加速视频编解码：

```bash
ffmpeg -hwaccel auto -i /path/to/your-video.mp4 -c:v hevc_vaapi -vf hwupload -c:a copy output.mp4
```

其中`-hwaccel auto`表示自动选择硬件加速器，如果选中了VA-API硬件加速器，在日志中会有这样的输出：

```log
AVHWDeviceContext @ 0x5a1a52ebfc40] Cannot load libcuda.so.1
[AVHWDeviceContext @ 0x5a1a52ebfc40] Could not dynamically load CUDA
Device creation failed: -1.
[vist#0:0/hevc @ 0x5a1a52eac580] [dec:hevc @ 0x5a1a52eadd40] Using auto hwaccel type vaapi with new default device.
```

当然，VA-API硬件加速器并不是`-hwaccel auto`的最优先选择，如果有cuda可用，FFmpeg会优先选择cuda硬件加速器。这在日志中也有体现。

而`-c:v hevc_vaapi`表示使用VA-API硬件加速器进行HEVC编码，`-vf hwupload`表示使用硬件上传（如果颜色空间不支持一般可以使用`-vf 'hwupload,scale_vaapi=format=nv12'`转化，有关FFmpeg硬件加速的使用方法，可以参见笔者的[另一篇博客](https://wszqkzqk.github.io/2023/01/01/FFmpeg%E7%9A%84%E5%9F%BA%E7%A1%80%E4%BD%BF%E7%94%A8/)）。如果硬件本身支持示例中的HEVC编码，且容器的硬件加速配置成功，这一命令应当能够正常运行。
