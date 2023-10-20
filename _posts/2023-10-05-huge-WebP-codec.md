---
layout:     post
title:      使用WebP编码超高像素图像
subtitle:   将2亿像素的图像编码为WebP格式
date:       2023-10-05
author:     wszqkzqk
header-img: img/media/webp/WebPLogo.svg
catalog:    true
tags:       媒体文件 开源软件 媒体编解码
---

## 前言

WebP是一种由Google开发的图像编码格式，同时支持**无损压缩和有损压缩**，其在**压缩率与视觉质量**上均优于JPEG或PNG，同时还支持透明度与动画。

而相比较新、压缩率更高的AVIF格式，WebP目前的**支持要广泛得多**：Google Chrome、Mozilla Firefox、Microsoft Edge、Opera、Safari、Android、iOS、各搭载了FFmpeg的Linux发行版等平台均已支持WebP格式，Windows 11的图片查看器也已经支持WebP格式；Wiki Commons目前支持WebP图片，但是仍然不支持AVIF图片。

因此，目前将图片存储为WebP格式是一种非常好的选择。笔者的博客中现在使用的**所有点阵图**，包括有损压缩图片与无损压缩图片，均使用的是**WebP**格式。

## 编码问题

笔者以前将图片转码为WebP格式通常使用的是[FFmpeg](https://ffmpeg.org/)或者ImageMagick，其中FFmpeg默认输出的WebP图片大小更小，而ImageMagick默认输出的WebP图片质量更高。然而，笔者最近换了支持直出2亿像素照片的Redmi Note 13 Pro+，在尝试将2亿像素的照片转码为WebP格式时，发现FFmpeg和ImageMagick均会报`failed with error: 6`的错误，就像这样：

```
[libwebp @ 0x5580403317c0] WebPEncode() failed with error: 6
[vost#0:0/libwebp @ 0x5580403314c0] Error submitting video frame to the encoder
Conversion failed!
```

这里的报错信息非常简单，只有`failed with error: 6`，其中输出的`Error submitting video frame to the encoder`还是非常有误导性。

## 尝试

笔者之后又尝试使用更加直接的`cwebp`进行转码，但是`cwebp`的输出结果与FFmpeg的输出结果相同，均会报`failed with error: 6`的错误：

```
Saving file '/tmp/test.webp'
Error! Cannot encode picture as WebP
Error code: 6 (PARTITION0_OVERFLOW: Partition #0 is too big to fit 512k.
To reduce the size of this partition, try using less segments with the -segments option, and eventually reduce the number of header bits using -partition_limit. More details are available in the manual (`man cwebp`))
```

但是`cwebp`的错误信息更加详细，指出了报错的具体原因：

* `PARTITION0_OVERFLOW: Partition #0 is too big to fit 512k.`：第0个分区太大，无法放入512k中。
* `To reduce the size of this partition, try using less segments with the -segments option, and eventually reduce the number of header bits using -partition_limit.`：为了减小分区的大小，尝试使用`-segments`选项减少分区数量，或者使用`-partition_limit`选项减少头部位数。

因此可以尝试使用`-segments`和`-partition_limit`这两个转码参数尝试调整。

## 解决

笔者首先使用`-segments`选项尝试调整分区数量，减小在sns算法分割期间更改要使用的分区数，使得控制分区能够满足512 k的限制。`-segments`选项的默认值为4，接受的范围是1-4，笔者发现，只有将`-segments`选项的值调整为1时，才能够成功将2亿像素的照片转码为WebP格式，例如：

```
cwebp -q 80 [...] -segments 1 -o [...]
```

笔者又尝试了单独调整`-partition_limit`选项，发现如果不将`-segments`选项的值调整为1，将`-partition_limit`选项的值调整为多少都无法成功将2亿像素的照片转码为WebP格式。

在将`-segments`选项的值调整为1后，笔者又尝试调整`-partition_limit`选项的值，发现将`-partition_limit`调整为100时（即宏块位数完全降级，默认值为0，不降级），编码速度由55453 ms大幅降低到7837 ms：

```bash
$ cwebp -preset photo -q 80 '/run/media/wszqkzqk/D/OneDrive - 北京大学/Pictures/Camera Roll/2023/10/IMG_20231001_163030.jpg' -segments 1 -o /tmp/test2.webp
Saving file '/tmp/test2.webp'
File:      /run/media/wszqkzqk/D/OneDrive - 北京大学/Pictures/Camera Roll/2023/10/IMG_20231001_163030.jpg
Dimension: 16320 x 12240
Output:    19675582 bytes Y-U-V-All-PSNR 42.60 46.61 48.75   43.72 dB
           (0.79 bpp)
block count:  intra4:      42638  (5.46%)
              intra16:    737662  (94.54%)
              skipped:      1637  (0.21%)
bytes used:  header:            865  (0.0%)
             mode-partition: 474423  (2.4%)
 Residuals bytes  |segment 1|segment 2|segment 3|segment 4|  total
    macroblocks:  |     100%|       0%|       0%|       0%|  780300
      quantizer:  |      19 |      19 |      19 |      19 |
   filter level:  |      61 |       3 |       3 |       3 |
$ echo $CMD_DURATION
55453
$ cwebp -preset photo -q 80 '/run/media/wszqkzqk/D/OneDrive - 北京大学/Pictures/Camera Roll/2023/10/IMG_20231001_163030.jpg' -partition_limit 100 -segments 1 -o /tmp/test.webp
Saving file '/tmp/test.webp'
File:      /run/media/wszqkzqk/D/OneDrive - 北京大学/Pictures/Camera Roll/2023/10/IMG_20231001_163030.jpg
Dimension: 16320 x 12240
Output:    19799116 bytes Y-U-V-All-PSNR 42.60 46.62 48.76   43.72 dB
           (0.79 bpp)
block count:  intra4:          0  (0.00%)
              intra16:    780300  (100.00%)
              skipped:      1508  (0.19%)
bytes used:  header:            786  (0.0%)
             mode-partition: 442598  (2.2%)
 Residuals bytes  |segment 1|segment 2|segment 3|segment 4|  total
    macroblocks:  |     100%|       0%|       0%|       0%|  780300
      quantizer:  |      19 |      19 |      19 |      19 |
   filter level:  |      61 |       2 |       2 |       2 |
$ echo $CMD_DURATION
7837
```

而对于2亿像素的大图片，两者体积差别却非常小，分别为`19675582`和`19799116`，差别仅为`0.12`MB，占原图体积的`0.6%`，而两者的PSNR值也几乎没有区别。可见，编码较大的图片时，将`-partition_limit`选项的值调整为100可以大幅提升编码速度，而对于编码后的图片体积影响不大。

## 保留元数据

在默认的转码中，`cwebp`并不会保留原图的元数据，例如拍摄时间、拍摄设备等信息。如果需要保留原图的元数据，可以使用`-metadata`选项，例如：

```bash
cwebp [...] -metadata all -segments 1 -o [...]
```

不过，目前Windows版的`cwebp`仅支持保留ICC元数据，不支持保留EXIF元数据，因此在Windows下使用`cwebp`转码时，无法保留原图的拍摄时间、拍摄设备等信息；Linux版的`cwebp`则可以保留原图的所有元数据。

## 多线程编码

`cwebp`默认使用单线程编码，可以使用`-mt`选项开启多线程编码，例如：

```bash
cwebp [...] -mt -metadata all -segments 1 -o [...]
```

## 总结

在转码2亿像素的大图片时，`cwebp`需要将`-segments`选项的值调整为1才能够成功转码；对于大图片，将`-partition_limit`选项的值调整为100可以大幅提升编码速度，而对于编码后的图片体积影响不大；如果需要保留原图的元数据，可以使用`-metadata all`选项。