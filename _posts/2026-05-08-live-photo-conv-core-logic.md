---
layout:     post
title:      GTK/Vala 开发教程：双后端架构与 XMP 元数据处理
subtitle:   解析 Live Photo Converter 的后端设计
date:       2026-05-08
author:     wszqkzqk
header-img: img/GTK-logo.webp
catalog:    true
tags:       开源软件 Vala GStreamer FFmpeg XMP 算法 GExiv2
---

## 前言

[前两篇](https://wszqkzqk.github.io/2026/05/06/live-photo-conv-build-system/) 分别拆解了 Meson 构建系统与 GTK4 图形界面，它们解决了怎么编译与界面怎么做的问题。这一篇进入最底层——`liblivephototools` 共享库的核心处理逻辑。

动态照片的处理链条大致是这样的：打开一个文件 → 判断它是不是动态照片 → 如果是，找到嵌入视频的位置 → 把静态图和视频各自导出，或者反过来从图片和视频合成一张新的动态照片。每一步都有可替换的实现方案，这就引出了整个库的架构主线——抽象基类加双后端的模板方法模式。

项目仓库：[github.com/wszqkzqk/live-photo-conv](https://github.com/wszqkzqk/live-photo-conv)

## 整体架构

库的核心是两组抽象基类，分别对应两个方向的操作：

```
LivePhoto (抽象)          LiveMaker (抽象)
  ├─ LivePhotoGst           ├─ LiveMakerGst
  └─ LivePhotoFFmpeg        └─ LiveMakerFFmpeg
```

`LivePhoto` 负责"拆"——从动态照片中提取图像和视频、导出帧、生成长曝光。`LiveMaker` 负责"合"——将图片和视频拼成动态照片，写入正确的 XMP 元数据。每个基类定义了一套抽象方法（比如 `split_images_from_video`、`generate_long_exposure`、`export_main_image`），两个子类分别用 GStreamer 和 FFmpeg 来实现。

选择哪个后端由编译期决定——Meson 构建时如果检测到 GStreamer，就注入 `-D ENABLE_GST` 宏，整个代码库通过 `#if ENABLE_GST` 来切换。运行时不需要判断，编译的时候就已经定好了。用户在安装时如果两个后端都可用，默认用 GStreamer；如果在 CLI 加 `--use-ffmpeg` 参数，也可以在 GStreamer 构建下强制走 FFmpeg 路径。

要理解这个架构为什么这样设计，得先看一个更基本的问题：一段嵌在 JPEG 文件末尾的 MP4 视频，程序是怎么找到它的。

## GExiv2 与 XMP 元数据

Android 动态照片在两个关键地方定义了"视频从哪里开始"——一是 XMP 元数据中标注的视频大小，二是文件末尾那段数据的物理位置。前者是标准途径，后者是后备方案。

### 命名空间注册

Google 的动态照片元数据使用了自定义的 XMP 命名空间，这些命名空间不是 XMP 标准内置的，必须在读写之前手动注册：

```vala
GExiv2.Metadata.try_register_xmp_namespace (
    "http://ns.google.com/photos/1.0/camera/", "GCamera");
GExiv2.Metadata.try_register_xmp_namespace (
    "http://ns.google.com/photos/1.0/container/", "Container");
GExiv2.Metadata.try_register_xmp_namespace (
    "http://ns.google.com/photos/1.0/container/item/", "Item");
```

三个命名空间分别对应 Google 的 Camera（相机信息）、Container（容器结构）和 Item（容器条目）。`try_register_xmp_namespace` 的"try"意味着如果之前已经注册过也不会报错——同一个进程里多次打开动态照片，重复注册是安全的。

### 两套标准

Google 对动态照片定义过两套标准。旧标准把标记写在一个叫 `GCamera.MicroVideo` 的标签族里，靠 `MicroVideoOffset` 标注视频大小（从文件末尾往前算的偏移）。新标准改用 `GCamera.MotionPhoto` 系列标签，加上 `Container.Directory` 的序列结构来描述文件内部的布局——第 1 个条目是主图（`Semantic=Primary`），第 2 个条目是视频（`Semantic=MotionPhoto`），`Item:Length` 告诉程序视频有多大。

读取时先试新标准，读不到再试旧标准：

```vala
var video_size_str = metadata.try_get_tag_string (
    "Xmp.Container.Directory[2]/Container:Item/Item:Length");
if (video_size_str == null)
    video_size_str = metadata.try_get_tag_string (
        "Xmp.GCamera.MicroVideoOffset");
```

两个标准得到的都是视频大小，不是视频的起始位置。用文件总大小减去这个值，才是真正的视频偏移。

写的时候，`LiveMaker` 和 `LivePhoto` 的 `repair_live_metadata()` 会同时写入新旧两套标签——这样无论是老款 Pixel 还是最新的 HyperOS 3 设备，都能正确识别。

### 元数据的保留与清理

打开一个动态照片后，构造函数做的第一件事是把所有 XMP 标签复制到一棵 `Tree<string?, string?>` 里：

```vala
var all_tags = metadata.get_xmp_tags ();
foreach (unowned string tag in all_tags) {
    xmp_map[tag] = metadata.try_get_tag_string (tag);
}
metadata.clear_xmp ();
```

为什么要先复制再清空？因为这个 `metadata` 对象后续会被用来给导出的普通图片附加元数据——如果不清空 XMP，导出的静态图就会带着 `MicroVideoOffset` 之类的标签，接收方可能会误以为它是动态照片。但原始标签又不能丢——修复功能需要原封不动地把它们写回去。所以方案是：把标签存到 `xmp_map` 里，GExiv2 对象本身保持"干净"，修复时再从 `xmp_map` 里逐一恢复。

## 视频偏移检测：从 XMP 到 KMP

上面说到先读 XMP 元数据，但 XMP 不总是可靠的。用户在社交媒体上发了一张动态照片，平台可能会剥离元数据；换机迁移时文件的 metadata 可能被其他的工具改写。碰到这种情况，就得直接从文件内容里找。

### XMP 路径

最优先的方案是读 XMP，这是最快的——GExiv2 在文件打开时已经解析好了元数据，一个 `try_get_tag_string` 调用只是查哈希表。从 `MicroVideoOffset` 或 `Item:Length` 中拿到视频大小，用文件总大小减一下，就有了偏移量。

读完之后加一个验证步骤：跳转到 `video_offset + 4` 的位置读 4 个字节，看看是不是 `ftyp`。这能防止 metadata 里的数字是错的——比如文件被截断过、或者写过不正确的 XMP。

### KMP 后备

如果 XMP 里找不到偏移，或者验证不通过，就降到 KMP 搜索。思路是在整个文件中搜索 `{'f','t','y','p'}` 这四个字节——MP4 文件的头总是以这四个字符开头。

这里用的 KMP 算法分了两个阶段。首先是构建 LPS 表（最长相同前后缀）：

```vala
lps[0] = 0;
int len = 0;
for (int i = 1; i < PATTERN_LENGTH; i += 1) {
    while (len > 0 && MP4_VIDEO_HEADER[i] != MP4_VIDEO_HEADER[len])
        len = lps[len - 1];
    if (MP4_VIDEO_HEADER[i] == MP4_VIDEO_HEADER[len])
        len += 1;
    lps[i] = len;
}
```

然后是流式搜索——以 64 KiB 为一块读文件，模式指针 `j` 跨块保持状态：

```vala
while ((bytes_read = stream.read (buffer)) > 0) {
    for (int i = 0; i < bytes_read; i += 1) {
        while (j > 0 && buffer[i] != (uint8) pattern[j])
            j = lps[j - 1];
        if (buffer[i] == (uint8) pattern[j])
            j += 1;
        if (j == PATTERN_LENGTH) {
            offset = global_pos + i - PATTERN_LENGTH + 1;
            break;
        }
    }
    global_pos += bytes_read;
}
```

找到 `ftyp` 之后还要往回退 4 个字节——MP4 文件头的结构是 4 字节大端整数（整个头的大小）后面紧跟 `ftyp`，视频真正开始的位置在那 4 字节之前。

坦诚讲，对于 `ftyp` 这种只 4 字节的固定模式，KMP 确实是大材小用了——把 4 个字节拼成一个 `uint32` 去比较，代码更短跑得也更快。但视频偏移检测不在热路径上，一个文件只跑一次，4 字节的 KMP 和 int 比较在实际使用中完全感觉不到区别。KMP 的价值在于跨块搜索时模式指针不会丢，而这个场景下 `ftyp` 刚好跨越块边界的概率微乎其微。所以选择 KMP 纯粹是因为实现简单、逻辑正确、没理由换掉它——反正不是性能瓶颈，能用就行。

## GStreamer 后端

GStreamer 后端的核心是一条 pipeline 字符串：

```
appsrc name=src ! decodebin ! videoflip method=automatic !
  queue ! videoconvert ! video/x-raw,format=RGB,depth=8 ! appsink name=sink
```

每个元素的选择都有具体原因。`appsrc` 而不是 `filesrc` 或 `giostreamsrc`：因为视频数据嵌在 JPEG 文件体内，不是独立的 `.mp4`。`filesrc` 不能从文件中间开始读，`giostreamsrc` 不支持 `seek`。所以用 `appsrc`，另外开一个线程手动 seek 到 `video_offset` 后把数据一段段 `push_buffer` 进去。

`decodebin` 做自动解复用和解码——手机拍出来的视频编码格式各异（H.264、H.265 都有），让 GStreamer 自己去识别比硬编码解码器灵活得多。`videoflip method=automatic` 根据视频的旋转元数据来翻转画面——很多手机竖拍时并不会真正旋转像素，只是在 metadata 里写了旋转角度，不处理的话导出来的是侧躺的画面。`queue` 在线程边界处做缓冲，解耦解码线程和下游的处理速度。

最后 `videoconvert` 加 `video/x-raw,format=RGB,depth=8` 的 caps filter，强制所有帧转换为 8 位 RGB。这个格式直接对得上 `Gdk.Pixbuf.from_data()` 的要求——色彩空间 RGB、无 alpha、8 位深度、行跨度 `width × 3`。这个强制转换是有代价的：每次拿到帧都做一次色彩空间转换，而很多视频本身就是 YUV 编码，转换开销不小。笔者的实现里没有优化这一部分——一个更高效的方案是在解码后直接拿 YUV 数据自己做 RGB 转换，但那样会丢掉 GStreamer 的通用性。

### 逐帧导出：双线程 + 线程池

逐帧导出的整体流程是一个"推—拉—并行写"的三段模型。

推送线程负责把视频的原始字节塞进 `appsrc`：

```vala
new Thread<ExportError?> ("push-video", () => {
    var stream = file.read ();
    stream.seek (video_offset, SeekType.SET);
    // 分块读取并 push_buffer
    appsrc.push_buffer (new Gst.Buffer.wrapped (chunk));
    appsrc.end_of_stream ();
});
```

主线程则不断从 `appsink` 中 `pull_sample()`，每拿到一帧就包装成 `Sample2Img` 对象扔进线程池：

```vala
int index = 0;
while (true) {
    var sample = appsink.pull_sample ();
    if (sample == null) break;
    var img = new Sample2Img (sample, output_format, dest_path, index, metadata);
    thread_pool.add (img);
    index += 1;
}
```

`ThreadPool` 的大小等于 `get_num_processors()`——多帧并行编码写入，在多核机器上能明显加速。不过线程池不保证顺序，帧是以 `index` 命名的，哪个先编完就先落地，最终文件名不会乱。

最后等推送线程结束、`pull_sample` 返回 null（说明 apprc 发送了 EOS 且 pipeline 已排空），再释放线程池。

### 长曝光：逐像素时间平均

长曝光合成的思路很直觉——把视频所有帧的每个像素值累加起来，除以总帧数取平均。运动的部分会被"抹匀"，静止的部分保持不变，效果类似慢速快门。

累加数组用 `uint64` 而不是 `uint8`——视频哪怕只有 3 秒（约 90 帧），单个像素的累加值也能轻松超过 255。用 64 位无符号整数保证不会溢出：

```vala
uint64[] accumulator = new uint64[width * height * 3];
// ... 从 appsink 逐帧 pull_sample ...
for (uint64 i = 0; i < len; i += 1)
    accumulator[i] += data[i];
frames += 1;
```

全部帧处理完后做平均，`+ frames / 2` 是四舍五入：

```vala
pixel_data[i] = (uint8) ((accumulator[i] + frames / 2) / frames);
```

然后用 `Gdk.Pixbuf.from_data()` 把结果 RGB 数组包装成 pixbuf 写出。需要注意 `pixel_data` 的生命周期——`from_data()` 只是借用了这份内存（不会复制），所以 `pixel_data` 必须在 pixbuf 使用期间保持存活。

## FFmpeg 后端

FFmpeg 后端不走库调用（没有链 `libav*`），而是通过子进程的方式——在代码里拼命令行、创建 `Subprocess`、把数据写到 stdin、从 stdout 读结果。

### 子进程模式

`Subprocess.newv()` 接受一个以 `null` 结尾的字符串数组作为命令。以逐帧导出为例：

```vala
const string[] ffmpeg_cmd = {
    "ffmpeg",
    "-progress", "-",
    "-loglevel", "error",
    "-hwaccel", "auto",
    "-i", "pipe:0",
    "-f", "image2",
    "-y", dest_pattern,
    null
};
var subprcs = new Subprocess.newv (ffmpeg_cmd,
    SubprocessFlags.STDIN_PIPE | SubprocessFlags.STDOUT_PIPE | SubprocessFlags.STDERR_PIPE);
```

`-progress -` 让 FFmpeg 把编码进度以 `key=value` 的格式输出到 stdout，方便代码用正则 `/^frame=\s*(\d+)/` 去解析当前编到第几帧了。`pipe:0` 表示从 stdin 读输入——视频数据由推送线程塞进管道。

推送线程和 GStreamer 后端很像，但有一个必须手动处理的细节：

```vala
var pipe = subprcs.get_stdin_pipe ();
Utils.write_stream (video_stream, pipe);
pipe.close ();
```

`get_stdin_pipe()` 返回的是 unowned 引用——GLib 不会自动帮你关。不关的话 FFmpeg 会一直在 stdin 上阻塞等待，永远不会退出。这是最容易踩的坑：子进程没有 exit，`subprcs.wait()` 永远等不到，整个程序卡死。

进度解析用的是 FFmpeg 的 `-progress` 输出：

```vala
while ((line = stdout_stream.read_line ()) != null) {
    MatchInfo match;
    if (/^frame=\s*(\d+)/.match (line, 0, out match)) {
        int64 frame = int64.parse (match.fetch (1));
        // 从上一次进度推进到当前帧，报告给 Reporter
    }
}
```

FFmpeg 已经负责了实际的编码和写文件，代码这边只是在追踪进度和附加元数据。

### 长曝光：tmix 滤镜

GStreamer 后端要手写几十行累加代码的长曝光效果，FFmpeg 用一行滤镜就解决了：

```
ffmpeg -i pipe:0 -vf tmix=frames=N -f image2 -update 1 -y dest.jpg
```

`tmix=frames=N` 做的是逐帧时间混合，`N` 是总帧数——需要提前用 `ffprobe` 拿到。

```vala
string[] ffprobe_cmd = {
    "ffprobe",
    "-v", "error",
    "-select_streams", "v:0",
    "-count_packets",
    "-show_entries", "stream=nb_read_packets",
    "-of", "csv=p=0",
    "pipe:0",
    null
};
```

`-update 1` 让 `image2` muxer 只写一个文件而不是帧序列。整个长曝光就是一次 ffmpeg 调用——不需要逐帧解码、不需要内存累加、不用操心溢出。

### WebP 的特殊处理

当输出格式是 WebP 时，代码会额外加 `-c:v libwebp` 参数。不加的话 FFmpeg 会默认选 `libwebp_anim` 编码器，产出一个动画 WebP 而不是一系列静态 WebP 图片——效果完全不符合预期。

## 合成方向：LiveMaker

与 `LivePhoto` 的"拆"相反，`LiveMaker` 负责把一个图片和一个视频拼成动态照片。

### 自动命名

构造函数在没有指定输出路径时，会根据输入自动生成：

- 有主图：在主图文件名前加 `MVIMG_` 前缀（Google 的命名惯例），强制用 `.jpg` 后缀
- 只有视频：从 `VID_*` 变 `MVIMG_*`，同样强制 `.jpg`

强制 `.jpg` 不是因为不想支持其他格式，而是因为 GExiv2 目前不支持在 HEIC 或 AVIF 文件上写 XMP 元数据。这是一个上游限制，只能等 GExiv2 更新。

### 合成流程

`export()` 方法走两条路径：如果用户提供了主图，就先写主图数据再追视频；如果只有视频，就提取第一帧做封面。写完文件主体之后，统一写入 XMP 标签——同时写新旧两套标准的 `MicroVideo` 系列和 `MotionPhoto` 系列，以及 `Container.Directory` 的结构描述。

从原素材中保留时间戳的逻辑也值得一提：如果主图原本就是动态照片导出的，它可能带有 `MotionPhotoPresentationTimestampUs` 标签（表示视频播放的起始时间戳）。合成时会尝试把这个值继承到新的动态照片中，保证"提取→编辑→重新合成"这个流程不丢时间信息。

GStreamer 版的 `LiveMakerGst` 在只有视频时用 `giostreamsrc` 读取视频（因为视频是独立文件，可以直接从头播放，不需要 `appsrc` 的 seek 能力）。`Sample2Img.save_to_stream()` 直接把第一帧写成 JPEG，然后视频原始数据追加到同一个输出流后面。

FFmpeg 版的 `LiveMakerFFmpeg` 则走管道——把视频喂给 `ffmpeg -vf select=eq(n\,0) -f image2pipe -vcodec mjpeg pipe:1`，从 stdout 读出第一帧的 JPEG 数据写到输出文件头部，再补上视频原始数据。这种"FFmpeg 当转换器用"的模式在跨平台场景下很实用——不用关心系统有没有特定解码库，只要装了 FFmpeg 就能跑。

## Sample2Img：从 Gst.Sample 到 Gdk.Pixbuf

`Sample2Img` 的定位是一个轻量转换器，把 GStreamer pipeline 吐出的 `Gst.Sample` 变成可以存盘的 `Gdk.Pixbuf`。它被声明为 `[Compact (opaque = true)]`——不是 GObject，没有引用计数，没有属性系统，用完后由 `ThreadPool` 负责释放。每帧都建这么一个对象，省掉 GObject 的开销是值得的。

构造时直接从 `Gst.Sample` 中解出 buffer 和 caps：

```vala
var buffer = sample.get_buffer ();
var caps = sample.get_caps ();
caps.get_structure (0).get_int ("width", out width);
caps.get_structure (0).get_int ("height", out height);

Gst.MapInfo info;
buffer.map (out info, Gst.MapFlags.READ);
pixbuf = new Gdk.Pixbuf.from_data (info.data, Gdk.Colorspace.RGB,
    false, 8, width, height, width * 3);
buffer.unmap (info);
```

这里有一项隐含约定：pipeline 的 caps filter 已经保证了数据是 8 位 RGB，所以 `from_data` 的参数（`Colorspace.RGB`、`false` 无 alpha、`8` 位深度、`width*3` 行跨度）不需要做任何运行时检查——如果 pipeline 配置错了，这里会直接产生花屏图片，但不会崩溃。

## 编译与运行

依赖和构建命令与前两篇一致。如果不想装 GStreamer 全家桶，可以走纯 FFmpeg 模式：

```bash
meson setup builddir --buildtype=release -D gst=disabled
meson compile -C builddir
meson install -C builddir
```

FFmpeg 模式下逐帧导出、长曝光、视频首帧提取都能正常工作，只是少了一个后端选项。

## 关于后续

本文覆盖了 `liblivephototools` 的核心逻辑——抽象基类与双后端的架构选择、GExiv2 对 Google XMP 命名空间的操作、视频偏移检测的两级后备策略、GStreamer pipeline 与 FFmpeg 子进程的各自实现、以及合成功能的完整流程。加上前两篇的构建系统和图形界面，Live Photo Converter 作为完整 Vala 项目的三个主要维度就都拆解完了。

后续如果有需要，可以追加一篇覆盖 Flatpak 打包、GitHub Actions CI 流水线和 Hosted Weblate 翻译管理的文章，三篇核心教程已经足够支撑项目的全貌。
