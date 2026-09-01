---
layout:     post
title:      Live Photo Converter 的 Android 文件访问：适配 SAF 与 content URI
subtitle:   从 GTK content file 补丁到跨平台暂存
date:       2026-08-25
author:     wszqkzqk
header-img: img/GTK-logo.webp
catalog:    true
tags:       开源软件 Vala GTK LibAdwaita Android GIO
---

## 前言

[上一篇](https://wszqkzqk.github.io/2026/08/24/live-photo-conv-android-build/)讲了 [Live Photo Converter](https://github.com/wszqkzqk/live-photo-conv) 的 Android 构建：pixiewood 怎么组织依赖、GStreamer 为什么要静态链接，以及 APK 如何发布。程序真正跑起来后，首先遇到的却是一个更基础的问题：Android 文件选择器给我的不是文件路径。

SAF（Storage Access Framework）把用户选中的文件交给应用时，使用的是 `content://` URI。这种 URI 没有对应的本地路径，应用只能通过 SAF 提供的接口读写。可是 Live Photo Converter 的核心库和 gexiv2 都是按路径工作的，`LivePhoto.create (path, dest_dir)` 接收的就是路径。最后采用的方案分成两步：先修 GTK Android 后端对 content file 的处理，再在应用里增加一层暂存，把文件复制到本地临时路径，交给原有代码处理，完成后再复制回去。

项目地址仍是 [github.com/wszqkzqk/live-photo-conv](https://github.com/wszqkzqk/live-photo-conv)。本文主要涉及 `src/gui.vala` 和 `src/sample2img.vala`。

## 问题：content:// 没有路径

在桌面上，`Gtk.FileDialog` 选完文件后调用 `file.get_path ()` 就能得到路径。Android 上，同一个 API 返回的是 GTK Android 后端实现的 **content file**，也就是 SAF 文档的 GIO 封装。它的 `get_path ()` 返回 `null`，`get_uri ()` 返回以 `content://` 开头的 URI。

这会影响三个地方：

* **核心库无法直接处理**：`LivePhoto`、`LiveMaker` 和 gexiv2 都需要真实路径；
* **输出不能直接写入**：用户选择的目录也可能是 content URI，结果要再复制进去；
* **修复模式还要覆盖原文件**：修复完成后，暂存副本必须写回原来的 content file。

Linux 桌面上的 GVfs 远程位置（例如 smb://、sftp://）也有同样的问题。从 NAS 拖进来的文件不一定有本地路径。暂存层用 `File.is_native ()` 判断是否需要复制，所以不必把逻辑写死在 Android 分支里。

## 修复 GTK Android 后端

移植时我在 GTK Android 后端碰到了两个问题。

第一个问题和文件选择器有关。HyperOS 返回的是普通的 MediaStore content URI，而不是 DocumentsContract 定义的 document URI。旧版 GTK 的 `from_uri()` 不接受这类 URI，选择文件后可能直接崩溃。[`gtk!10178`](https://gitlab.gnome.org/GNOME/gtk/-/merge_requests/10178) 扩大了可接受的 URI 范围。这个修复已经合并，所以仓库里对应的补丁已经删掉。

第二个问题出现在写回结果时。把本地暂存文件复制到 content URI，GTK 也可能崩溃。我给上游提交的修复是 [`gtk!10190`](https://gitlab.gnome.org/GNOME/gtk/-/merge_requests/10190)：

```diff
@@ gdk/android/gdkandroidcontentfile.c
 {
-  g_return_val_if_fail (GDK_IS_ANDROID_CONTENT_FILE (file), FALSE);
+  if (!GDK_IS_ANDROID_CONTENT_FILE (file))
+    {
+      g_set_error (error, G_IO_ERROR, G_IO_ERROR_NOT_SUPPORTED, "Cannot copy %s into a content file", G_OBJECT_TYPE_NAME (file));
+      return FALSE;
+    }
   if (!GDK_IS_ANDROID_CONTENT_FILE (destination))
     {
       g_set_error (error, G_IO_ERROR, G_IO_ERROR_NOT_SUPPORTED, "Cannot copy content file into %s", G_OBJECT_TYPE_NAME(destination));
```

`g_file_copy()` 会先调用目标文件提供的 copy vfunc。把本地暂存文件复制到 content URI 时，`gdk_android_content_file_copy()` 收到的源文件当然是普通的本地 `GFile`。旧代码用 `g_return_val_if_fail` 直接拒绝它，只返回 `FALSE`，却没有设置 `GError`；调用方随后按“错误已经设置”来处理，结果解引用了空指针。

补丁把这种情况改成返回 `G_IO_ERROR_NOT_SUPPORTED`。GIO 收到这个错误后会退回到流式复制：先读取本地源文件，再通过 content file 创建目标文件。此前的 [`gtk!9403`](https://gitlab.gnome.org/GNOME/gtk/-/merge_requests/9403) 已经解决 [#7703](https://gitlab.gnome.org/GNOME/gtk/-/issues/7703) 中相反方向的复制；`gtk!10190` 补的正是本地文件写入 content file 这一侧。应用把结果写回 SAF 目录时会走这条路径。

现在这个修复已经合并进 GTK main，以后的程序都不再需要单独携带这个补丁。

## 将文件暂存到本地路径

GTK 修好后，content file 的 `read`、`write`、`copy` 都能正常工作，但它还是没有本地路径。于是我在 `gui.vala` 里加了 staging：**先复制一份本地临时文件，让按路径工作的库处理这份副本，完成后再把结果复制回用户选中的位置**。这部分代码主要由几个小函数组成。

### 检测与选址

```vala
/** TRUE for files without a filesystem path (content://, GVfs remotes). */
private static bool needs_staging (File file) {
    return !file.is_native ();
}
```

判断只看 `File.is_native ()`，不关心 URI scheme，所以 content://、smb://、sftp:// 都能覆盖。这套 staging 代码在所有平台都会编译；0.50 开发期间专门把它改成了平台无关的实现，只有目录位置等少数细节留在 `#if ANDROID` 中。

暂存目录的位置则因平台而异：

```vala
private static string staging_root () {
#if ANDROID
    // Relies on the runtime pointing glib's data dirs at <filesDir>/share
    unowned var dirs = Environment.get_system_data_dirs ();
    var parent = dirs.length > 0 ? Path.get_dirname (dirs[0])
                                 : Environment.get_user_cache_dir ();
    return Path.build_filename (parent, "staging");
#else
    return Path.build_filename (Environment.get_user_cache_dir (),
                                "live-photo-conv", "staging");
#endif
}
```

Android 分支有一个容易忽略的细节。早期代码直接读取 `XDG_DATA_DIRS`，后来改成调用 glib 的 `Environment.get_system_data_dirs ()`。pixiewood 运行时会把 glib 的数据目录指向应用私有目录中的 `<filesDir>/share`，所以程序取它的父目录并在下面创建 `staging/`。暂存文件始终在应用沙盒里，不需要申请存储权限。桌面端则放在用户缓存目录中。

### 暂存与回收

```vala
/**
 * Returns a filesystem path for the file, staging it if needed.
 *
 * content:// files have no filesystem path; a local copy is staged
 * for the path-based library and gexiv2. SAF access must stay on the
 * main thread: GTK's content file vfuncs segfault on other threads.
 */
private static string path_for (File file) throws Error {
    if (!needs_staging (file)) {
        return file.get_path ();
    }

    var staging_dir = staging_root ();
    if (DirUtils.create_with_parents (staging_dir, 0700) != 0) {
        throw new FileError.FAILED ("Failed to create staging directory: %s", staging_dir);
    }
    var local = Path.build_filename (staging_dir, "%s-%s".printf (
        Uuid.string_random (), file.get_basename () ?? "unnamed"));
    file.copy (File.new_for_path (local), FileCopyFlags.OVERWRITE, null, null);
    return local;
}
```

`path_for ()` 是入口。本地文件直接返回路径，不产生额外开销；content file 则复制到暂存目录，并返回这个副本的路径。文件名前加 UUID，避免同一批次里出现同名文件。输出文件使用 `staging_output_path ()` 生成暂存路径，处理结束后由 `cleanup_staged ()` 删除。

## SAF 访问必须在主线程完成

GTK Android 后端的 content file vfunc 最终要通过 JNI 调用 Android 框架。**在非主线程调用它会直接段错误。**所以暂存复制和结果回写都在主线程完成，后台线程只接触已经转换成本地路径的文件。

这个限制决定了 GUI 的调用顺序。三个操作的入口都在按钮点击处理器或对话框回调中调用 `path_for ()`，而且发生在启动工作线程之前：

```vala
private void on_repair_clicked () {
    // ……
    var paths = new GenericArray<string> ();
    try {
        foreach (unowned var file in files)
            paths.add (path_for (file));   // 主线程：SAF 暂存
    } catch (Error e) {
        show_error_dialog (_("Error"), e.message);
        return;
    }

    start_work (repair_button, _("Repairing…"));
    repair_batch_async.begin (files, paths, force, video_size, repair_button, ...);
}
```

批处理协程启动后，传给工作线程的已经是**纯本地路径**数组，线程里不会再碰 content file。处理结束回到主线程，再执行回写。可以把这条边界记成一句话：**主线程负责 SAF，工作线程负责本地路径。**

## 三种模式的回写路径

三个操作都会暂存输入，但输出的处理方式不同：

### 制作：成功后复制到目标位置

制作模式的输出由保存对话框决定。如果目标是 content file，先写入暂存路径，制作成功后再复制到用户选择的位置：

```vala
bool output_staged = needs_staging (output_file);
video_path = path_for (video_file);
image_path = image_file != null ? path_for (image_file) : null;
// A staged output is copied back to the picked destination on success
output_path = output_staged
    ? staging_output_path (output_file.get_basename () ?? "live-photo.jpg")
    : output_file.get_path ();
maker = LiveMaker.create (video_path, image_path, output_path);
// ……异步制作完成后：
if (output_staged) {
    File.new_for_path (output_path).copy (
        output_file, FileCopyFlags.OVERWRITE, null, null);
}
```

无论成功还是失败，回调都会清理视频、主图和输出的暂存文件。

### 提取：暂存整个目录，再逐个复制

提取支持批量处理，输出目标是一个**目录**。SAF 选中的目录同样没有路径，因此先把整个批次输出到 UUID 命名的暂存目录，完成后再逐个复制到 SAF 目录：

```vala
// SAF-picked folders have no path: extract into a staging dir,
// then copy the results into the picked folder
string? dest_dir = dest_folder.get_path ();
File? copy_out_folder = null;
if (needs_staging (dest_folder)) {
    dest_dir = Path.build_filename (staging_root (), Uuid.string_random ());
    // ……
    copy_out_folder = dest_folder;
}
```

回写时每个文件单独处理复制错误。即使其中一个文件失败，也继续复制剩余文件，最后以 `%u of %u files failed` 汇总结果：

```vala
foreach (unowned var name in names.data) {
    // One failed copy must not strand the rest of the batch
    var child = staging.get_child (name);
    try {
        child.copy (copy_out_folder.get_child (name),
                    FileCopyFlags.OVERWRITE, null, null);
        child.delete ();
    } catch (Error e) {
        // 记入错误汇总，继续下一个
    }
}
```

### 修复：覆盖原文件与非原子写回

修复模式是原位操作，回写时要把修好的暂存副本**覆盖回原始的 content:// 文件**：

```vala
// Repair works in place: write the staging copies back over the
// original content:// files (not atomic: a crash mid-copy can
// corrupt the original)
for (int i = 0; i < files.length; i += 1) {
    if (succeeded[i] && needs_staging (files[i])) {
        try {
            File.new_for_path (paths[i]).copy (
                files[i], FileCopyFlags.OVERWRITE, null, null);
        } catch (Error e) {
            // 记入错误汇总
        }
    }
    if (needs_staging (files[i]))
        cleanup_staged (paths[i]);
}
```

只有**修复成功**（`succeeded[i]`）的文件才会写回，失败的原文件不会动。这次复制也不是原子操作：如果中途崩溃，原文件可能只写了一部分。SAF 没有可用的 rename 语义，暂时无法用“写临时文件再替换”的方式规避这个问题。

## 崩溃恢复：启动时清理残留

正常流程结束时会清理暂存文件，但应用可能在处理中途被系统杀掉，留下没有机会清理的文件。为此，程序每次启动时都会再清理一次：

```vala
public override void startup () {
    base.startup ();
    clear_staging ();
    // ……
}

/** Wipes leftover staging files from a previous run. */
private static void clear_staging () {
    delete_recursively (File.new_for_path (staging_root ()));
}
```

`clear_staging ()` 会递归删除整个暂存根目录。它在 `startup ()` 中调用，早于窗口创建和文件操作，所以上次运行留下的内容会在新任务开始前消失。暂存区位于应用沙盒中，用户看不到。

## gdk-pixbuf 的 Android saver

除了 staging，Android 的图像保存也踩到过一个坑。gdk-pixbuf 的 Android saver 会把像素缓冲区按 RGBA_8888 交给 `AndroidBitmap_compress()`，所以**没有 alpha 通道的 pixbuf 保存必定失败**，返回 `ANDROID_BITMAP_RESULT_BAD_PARAMETER`。视频采样得到的帧通常没有 alpha，早期版本提取视频帧时会因此悄悄失败：界面显示成功，磁盘上却没有文件。

修复集中在一个小函数里（`src/sample2img.vala`）：

```vala
internal Gdk.Pixbuf pixbuf_with_opaque_alpha (Gdk.Pixbuf pixbuf) {
#if ANDROID
    return pixbuf.has_alpha ? pixbuf : pixbuf.add_alpha (false, 0, 0, 0);
#else
    return pixbuf;
#endif
}
```

在 Android 上，无 alpha 的 pixbuf 会补上一条不透明 alpha 通道。Android loader 解码出来的结果本来就是 RGBA，其他平台的 saver 也接受 RGB，因此非 Android 分支不需要做任何处理。运行时代码中的 `#if ANDROID` 目前只有两处：`staging_root ()` 的目录选择，以及这个 alpha 修复。

## 结语

这次 SAF 适配最后落在三个点上：修好 GTK 的 content file 复制、用 staging 把没有路径的文件转换成本地副本，以及把所有 SAF 操作限制在主线程。核心库不需要知道 Android 的 `content://`，它始终只接收本地路径。

构建和运行时的 Android 适配就先写到这里。0.40 到 0.50 期间还做了并发背压、内存泄漏、修复算法和边界检查等与平台无关的改动，之后再单独整理。
