---
layout:     post
title:      GTK/Vala 开发教程：图形界面架构与异步线程模型
subtitle:   自定义控件、ViewStack 布局、异步工作线程与错误处理
date:       2026-05-07
author:     wszqkzqk
header-img: img/GTK-logo.webp
catalog:    true
tags:       开源软件 Vala GTK LibAdwaita GUI
---

## 前言

[上一篇](https://wszqkzqk.github.io/2026/05/06/live-photo-conv-build-system/) 拆解了 Live Photo Converter 的 Meson 构建体系，从依赖管理、共享库输出到跨平台分发逐层展开。构建系统解决的是怎么编译的问题，这一篇则进入界面怎么做——`src/gui.vala` 的完整实现。

本教程涉及自定义控件封装、异步工作线程与 UI 的协作、表单构建器模式、跨平台图标策略等一系列实际工程中可能会遇到的问题。笔者将逐一拆解这些设计背后的原因与实现细节。

项目仓库：[github.com/wszqkzqk/live-photo-conv](https://github.com/wszqkzqk/live-photo-conv)

## Application 骨架

GTK4 应用的生命周期由一个 `Gtk.Application`（或其 LibAdwaita 版本 `Adw.Application`）管理。它负责处理 D-Bus 单实例注册、命令行参数解析、窗口创建和销毁。Live Photo Converter 的 GUI 入口就是这样一个子类：

```vala
public class LivePhotoConv.Application : Adw.Application {
```

### construct 块

`construct` 在 GObject 构造链的最后执行，此时通过构造参数传入的属性值都已经就位。`application_id` 必须在此时设定——它是一个构造时属性，之后不能再改：

```vala
construct {
    application_id = "com.github.wszqkzqk.live-photo-conv";
    flags = ApplicationFlags.DEFAULT_FLAGS;
}
```

`application_id` 采用反向域名格式，这不单是惯例——Flatpak 用它做沙盒标识，D-Bus 用它做服务名，`Gtk.IconTheme` 也用它查找应用图标。

`DEFAULT_FLAGS` 等价于 `HANDLES_OPEN | HANDLES_COMMAND_LINE`，意味着这个应用会接管文件打开和命令行激活的 D-Bus 请求——用户从文件管理器双击一个动态照片时，系统会通过 D-Bus 通知这个应用，不会另起一个进程。

### startup()：GAction 与主题切换

`startup()` 在整个进程生命周期中只执行一次，用来设置全局状态。这里做了两件事：配色方案切换和关于对话框。

配色方案的实现用到了 `GAction` 的状态模式：

```vala
var style_manager = Adw.StyleManager.get_default ();
string init_scheme;
switch (style_manager.color_scheme) {
    case FORCE_LIGHT: init_scheme = "force-light"; break;
    case FORCE_DARK:  init_scheme = "force-dark";  break;
    default:          init_scheme = "default";      break;
}

var scheme_action = new SimpleAction.stateful ("color-scheme", VariantType.STRING,
    new Variant.string (init_scheme));
scheme_action.notify["state"].connect (() => {
    style_manager.color_scheme = scheme_action.state.get_string () switch {
        "force-light" => Adw.ColorScheme.FORCE_LIGHT,
        "force-dark"  => Adw.ColorScheme.FORCE_DARK,
        default       => Adw.ColorScheme.DEFAULT,
    };
});
add_action (scheme_action);
```

`SimpleAction.stateful()` 创建的是一个带状态的 action。它内部持有一个 `GVariant` 状态值，当菜单项通过 `app.color-scheme::force-dark` 这样的详细 action 名称触发时，状态自动切换为新值，然后 `notify["state"]` 信号被触发。回调里读取新状态并写给 `Adw.StyleManager.color_scheme`，整个窗口的配色就即时更新。

`add_action()` 将这个 action 注册到应用的 `GActionMap` 中，后续菜单栏里写 `"app.color-scheme::default"` 就能直接引用。`::` 是 GAction 的参数分隔符——左侧是 action 名，右侧是目标值。

关于对话框的实现更简单——不需要状态，只是一个触发：

```vala
var about_action = new SimpleAction ("about", null);
about_action.activate.connect (show_about);
add_action (about_action);
```

`show_about()` 里使用 `Adw.AboutDialog`（不是旧的 `Gtk.AboutDialog`）：

```vala
var about = new Adw.AboutDialog () {
    application_name = "Live Photo Converter",
    application_icon = "com.github.wszqkzqk.live-photo-conv",
    developer_name = "Zhou Qiankang",
    developers = { "Zhou Qiankang <wszqkzqk@qq.com>" },
    copyright = COPYRIGHT,
    license_type = Gtk.License.LGPL_2_1,
    version = VERSION,
    website = WEBSITE,
    issue_url = ISSUES_URL,
};
about.present (active_window);
```

`active_window` 是 `Gtk.Application` 的内置属性，始终指向当前拥有焦点的窗口。用这个而不是存一个窗口引用，是因为理论上可能有多个窗口同时存在（虽然这个应用目前只有一个）。

### activate()：创建窗口

`activate()` 在每次应用被激活时调用——首次启动、D-Bus 激活、以及点击桌面启动器图标都会触发。这里组装了整个窗口结构：

```
ApplicationWindow
  └─ Adw.ToastOverlay
       └─ Adw.ToolbarView
            ├─ HeaderBar (顶部)
            │    ├─ Adw.ViewSwitcher (标签页切换)
            │    └─ MenuButton (汉堡菜单)
            └─ Adw.ViewStack (内容区)
                 ├─ "extract" 页面
                 ├─ "make" 页面
                 └─ "repair" 页面
```

`Adw.ToolbarView` 是 LibAdwaita 提供的顶级布局容器，原生支持顶部栏和底部栏。`Adw.ToastOverlay` 是最外层的包装——它的作用是让 `Adw.Toast`（操作反馈气泡）能覆盖在整个窗口之上。这些组件在 [Series 3 的基础教程](https://wszqkzqk.github.io/2025/08/07/GTK-Vala-Tutorial-3/) 中已经详细讲过，本文不再展开，重点放在这个项目特有的设计上：自定义控件、异步线程和错误处理。

## 自定义控件：FileDropArea

图形界面里每个标签页都包含两到三个文件放置区——用户把文件拖上去，或者点击浏览选择文件。GTK4 内置的 `Gtk.FileChooserButton` 和 `Gtk.DropTarget` 各管一半，但不能方便地组合成一个"既能拖又能点"的独立组件。于是有了 `FileDropArea`——一个继承自 `Adw.Bin` 的自定义控件。

```vala
private class LivePhotoConv.FileDropArea : Adw.Bin {
    public signal void changed ();
```

`Adw.Bin` 是最简单的单子容器。选择它而不是 `Gtk.Box` 的原因在于：`FileDropArea` 内部有一套完整的图标、标签、拖放和点击逻辑，但对外它只是一个"能装文件"的控件。设置 `this.child = main_box` 之后，父级只需要把它当普通 widget 使用即可。

### 构造阶段属性

```vala
public string hint { get; construct; }
public string icon_name { get; construct; default = "document-open-symbolic"; }
public string[] mime_types { get; construct; default = new string[0]; }
```

`get; construct;` 意味着这些属性只能在构造时设定。为什么不让外部在运行时改 `hint`？因为这个控件的视觉身份——提示文字、图标、文件类型过滤器——在它被创建的那一刻就固定了。允许运行时修改会迫使内部重新构建 widget 树，复杂度远超过收益。

构造函数的实现用到了 Vala 的默认参数和空合并运算符：

```vala
public FileDropArea (string hint, string? icon_name = null, string[]? mime_types = null) {
    Object (hint: hint, icon_name: icon_name ?? "document-open-symbolic",
            mime_types: mime_types ?? new string[0]);
}
```

`Object(...)` 是 GLib 基类的构造调用，Vala 要求所有构造参数通过它传递。`??` 确保即使调用者显式传了 `null`，属性仍然拿到合理的默认值。

### 属性驱动 UI 更新

这个控件最核心的设计在于 `files` 属性的 setter：

```vala
public GenericArray<File> files {
    get { return _files; }
    set {
        _files = value;
        if (value.length == 0) {
            label_stack.visible_child = hint_label;
            icon_image.icon_name = _orig_icon;
            icon_image.opacity = 0.5;
        } else if (value.length == 1) {
            file_label.label = value[0].get_basename ();
            label_stack.visible_child = file_label;
            icon_image.icon_name = "emblem-documents-symbolic";
            icon_image.opacity = 1.0;
        } else {
            file_label.label = ngettext ("%u file selected", "%u files selected", value.length).printf (value.length);
            label_stack.visible_child = file_label;
            icon_image.icon_name = "emblem-documents-symbolic";
            icon_image.opacity = 1.0;
        }
        changed ();
    }
}
```

无论文件是通过拖放还是浏览对话框进来的，最终都落到这个 setter 里。setter 根据文件数量做出三种响应：空状态（半透明占位图标 + 提示文字）、单选（显示文件名，图标变为文档图标）、多选（用 `ngettext` 处理复数字符串的翻译）。`changed()` 信号在状态切换后发出，外部监听者据此决定是否启用操作按钮。

`ngettext` 不是可选的装饰——英语里 "1 file selected" 和 "2 files selected" 只是后缀不同，但俄语、阿拉伯语等语言对复数的处理远比英语复杂。`ngettext(msgid, msgid_plural, n)` 根据当前 locale 的复数规则返回正确的形式，这是 gettext 体系的标准做法。

### 拖放接收

文件拖放的接收端通过 `Gtk.DropTarget` 实现。这里传 `Type.INVALID` 关闭自动类型检查，改用 `set_gtypes()` 手动声明可接受的类型：

```vala
var drop_target = new Gtk.DropTarget (Type.INVALID, Gdk.DragAction.COPY);
drop_target.set_gtypes ({typeof (Gdk.FileList), typeof (File)});
drop_target.drop.connect (on_drop);
this.add_controller (drop_target);
```

两种类型各有来源——`Gdk.FileList` 是文件管理器的多文件拖拽，`File` 是某些应用的单文件拖拽。处理器中用 `Value.holds()` 分派：

```vala
private bool on_drop (Value value, double x, double y) {
    var collected = new GenericArray<File> ();
    if (value.holds (typeof (Gdk.FileList))) {
        foreach (var file in ((Gdk.FileList) value.get_object ()).get_files ())
            collected.add (file);
    } else if (value.holds (typeof (File))) {
        collected.add (value.get_object () as File);
    }
    load_files (collected);
    return true;
}
```

`load_files()` 是内部的把关函数——它检查 `max_files` 的约束，截断多余的文件后再写入 `files` 属性。这样单文件和多文件模式的拖放逻辑完全统一。

### 点击浏览

拖放之外还有一条输入路径——点击控件打开文件对话框。GTK4 用 `Gtk.GestureClick` 捕获点击，这里连 `pressed` 信号（而非 `released`），因为点击后直接弹对话框没有"按住取消"的场景：

```vala
var click = new Gtk.GestureClick ();
click.pressed.connect (on_clicked);
this.add_controller (click);
```

`Gtk.GestureClick` 的 `pressed` 信号在鼠标按下时立即触发（而非 `released` 在松开时触发）。对于一个"点击就弹对话框"的场景，没有按住后取消的需求，`pressed` 的即时响应体验更好。

`on_clicked()` 中打开 `Gtk.FileDialog`，根据 `max_files` 选择调用 `dialog.open.begin()` 或 `dialog.open_multiple.begin()`。文件过滤器由 `build_filter()` 从 `mime_types` 构造。异步回调中静默忽略 `IOError.CANCELLED`（用户点了取消），这是标准的 GTK4 对话框处理方式。

## ViewStack 三标签页布局

三个操作模式（提取、制作、修复）通过 `Adw.ViewStack` + `Adw.ViewSwitcher` 组织：

```vala
var header = new Adw.HeaderBar ();
var view_switcher = new Adw.ViewSwitcher ();
var stack = new Adw.ViewStack ();
view_switcher.stack = stack;

stack.add_titled_with_icon (page_with_action_button (build_extract_page (), extract_button), 
    "extract", _("Extract"), "document-send-symbolic");
stack.add_titled_with_icon (page_with_action_button (build_make_page (), make_button), 
    "make", _("Make"), "list-add-symbolic");
stack.add_titled_with_icon (page_with_action_button (build_repair_page (), repair_button), 
    "repair", _("Repair"), "applications-utilities-symbolic");

header.title_widget = view_switcher;
```

`Adw.ViewSwitcher` 和 `Adw.ViewStack` 是一对绑定组件——只需设置 `view_switcher.stack`，切换器就会自动从栈中读取页面标题和图标，生成标签页按钮。`add_titled_with_icon()` 把标题和图标的元数据写入栈，切换器同步读取。

`header.title_widget = view_switcher` 把 HeaderBar 的中间区域替换为标签页切换栏。这是 LibAdwaita 的推荐做法——标签页导航取代传统的居中标题。

默认选中提取页面，因为从动态照片里导出内容是最高频的操作。

### 页面包装与底部按钮

每个页面的结构是"可滚动内容 + 底部固定按钮"：

```vala
private Gtk.Widget page_with_action_button (Gtk.Widget content, Gtk.Button button) {
    var scroll = new Gtk.ScrolledWindow () {
        child = content,
        vexpand = true, hexpand = true,
    };
    var box = new Gtk.Box (Gtk.Orientation.VERTICAL, 0);
    box.append (scroll);
    box.append (button);
    return box;
}
```

`ScrolledWindow` 设置了 `vexpand = true`，会在垂直方向上尽可能扩展，从而把按钮推向底部。按钮本身用 `make_action_button()` 创建，带 `"pill"` 和 `"suggested-action"` CSS 类——前者产生完全圆角，后者应用蓝色强调色，符合 GNOME 人机界面指南中的主要操作样式。

### 表单构建器模式

三个页面的内容区是不同组合的选项控件，由几个工厂函数构造：

```vala
private Adw.PreferencesGroup make_group (string title, string? description = null);

private Adw.ActionRow make_check_row (string title, out Gtk.CheckButton out_check,
                                        bool active = true, string? tooltip = null);

private Adw.ActionRow make_entry_row (string title, out Gtk.Entry out_entry,
                                        string? placeholder = null);
```

`Adw.PreferencesGroup` 虽然设计上属于 `Adw.PreferencesWindow` 体系，但它本质上就是一个带标题和可选描述文字的卡片容器，用在普通内容区里效果同样干净。比起自己写 CSS 搞分组，直接用这个现有组件更省事，也能保持 GNOME 应用间的视觉一致性。

`make_check_row()` 的 `out` 参数值得展开：

```vala
private Adw.ActionRow make_check_row (string title, out Gtk.CheckButton out_check, ...) {
    var check = new Gtk.CheckButton () { ... };
    out_check = check;
    var row = new Adw.ActionRow () { title = title, activatable = false, ... };
    row.add_suffix (check);
    return row;
}
```

调用方这样用：

```vala
options_group.add (make_check_row (_("Export main image"), out extract_main_image_check, true));
```

函数返回了 `Adw.ActionRow` 用于布局，同时通过 `out` 参数把内部的 `Gtk.CheckButton` 引用"泄露"出来。后续提取操作触发时，代码需要读取 `extract_main_image_check.active` 来判断用户勾了哪些导出选项。`out` 机制让工厂函数既能封装构造细节，又不丢失对内部控件的访问——如果返回的是一个复合 widget 再让调用方 `get_child()` 去翻找，代码会丑陋得多。

`activatable = false` 禁用了行本身的点击反馈，只让后缀的复选框响应交互。

## 异步操作与线程模型

这是整篇文章最核心的部分。GUI 程序的铁律是"不能阻塞主线程"——如果处理一张动态照片需要 5 秒，而代码在主线程里同步执行这 5 秒，整个窗口就会冻结，用户什么都点不了。解决方案是把耗时逻辑扔到后台线程，主线程只负责更新进度和展示结果。Vala 的 `async`/`yield` 机制正是为此设计的。

### 核心模式

以 `extract_batch_async` 为例，完整的异步线程模式分为五个步骤：

```vala
private async void extract_batch_async (File[] files, File dest_dir, ..., Gtk.Button button)
                                       throws ExportError, NotLivePhotosError {
    // 第一步：捕获回调
    SourceFunc callback = extract_batch_async.callback;

    // 第二步：启动工作线程
    bool success;
    int error_count;
    StringBuilder error_sb;
    new Thread<void> ("extract-batch", () => {
        // 在后台线程中逐个处理文件
        for (int i = 0; i < files.length; i++) {
            // ... 处理逻辑 ...
            // 第三步：通过 Idle 向主线程报告进度
            Idle.add (() => {
                report_progress (button, _("Extracting"), processed, total);
                return false;
            });
        }
        // 第四步：工作完成，唤醒主线程
        Idle.add ((owned) callback);
    });

    // 第五步：挂起协程，等待工作线程完成
    yield;

    // 回到主线程，处理结果
    if (error_count > 0)
        throw new ExportError.FILE_PUSH_ERROR (...);
}
```

这个模式的关键在于理解每一步的线程归属。

`SourceFunc callback = extract_batch_async.callback` 这一行是整个机制的入口。`async` 方法在 Vala 编译后会自动生成一个 `callback` 属性，类型是 `SourceFunc`（无参无返回值委托）。它就是"恢复执行"的句柄——在哪个线程调用它，协程就在哪个线程的主循环中恢复。

`new Thread<void>()` 创建分离线程，lambda 内的代码全部在后台执行，可以随意调用阻塞 I/O 和耗时的处理函数。

`Idle.add(() => { ... return false; })` 是跨线程通信的桥梁，向 GLib 主循环投递回调、在主线程空闲时执行。`return false` 告诉主循环"只跑一次就移除"——如果返回 `true`，这个回调就会变成不断重复的定时器。这里用于更新按钮上的进度文字；GTK4 的属性设置支持从任意线程调用，GObject 的属性系统内部有线程安全通知机制。

所有文件处理完后，`Idle.add((owned) callback)` 把 callback 投递到主线程。`owned` 转移所有权，防止 callback 被后面的代码复用。

`yield` 是 Vala 的关键字。执行到这一行，协程暂停、控制权归还主循环——用户在此期间可以继续操作界面。当 callback 被主循环调度执行后，协程从 `yield` 的下一行恢复，此时已经回到主线程，可以安全地访问 UI。

### 批量错误聚合

后台线程中每个文件的处理结果被记录到 `StringBuilder` 里：

```vala
var sb = new StringBuilder ();
// ... 处理失败时:
sb.append_printf ("%s: %s\n", file.get_basename (), e.message);
error_count++;
```

回到主线程后，根据错误数量构造不同的提示：

```vala
if (error_count > 0) {
    if (error_count != total)
        throw new ExportError.FILE_PUSH_ERROR (
            "%u of %u files failed:\n%s".printf ((uint) error_count, (uint) total, sb.str));
    else
        throw new ExportError.FILE_PUSH_ERROR (sb.str);
}
```

全部失败和部分失败的提示格式不同——后者会加上 "3 of 10 files failed" 的前缀，让用户一眼就能判断严重程度。`sb.str` 返回的是内部缓冲区的弱引用，这里的写法中 `sb` 是栈变量、尚未离开作用域，所以用 `unowned` 读取是安全的。

### 入口与收尾

每个操作按钮的点击处理遵循同一个模式。以提取为例：判断是否有文件选中，没有则弹出 toast 提示并返回；打开 `Gtk.FileDialog` 选择输出目录；在对话框的异步回调中，从 UI 控件读取用户选项到局部变量（作为快照，防止后续 UI 状态变化干扰）；调用 `start_work(button, ...)` 禁用按钮防止重复点击；调用 `extract_batch_async.begin(...)` 启动后台处理；在完成回调中调用 `end_work(button, ...)` 恢复按钮、根据结果显示 toast 或错误对话框。

`start_work` / `end_work` 是操作状态的看门：

```vala
private void start_work (Gtk.Button button, string label) {
    working = true;
    button.sensitive = false;
    button.label = label;
}

private void end_work (Gtk.Button button, string label, bool sensitive) {
    working = false;
    button.label = label;
    button.sensitive = sensitive;
}
```

`working` 这个标志除了控制按钮，还被文件放置区的 `changed` 信号回调检查——处理过程中如果用户拖入了新文件，回调会跳过按钮状态的更新，避免干扰正在进行的工作。

### 进度报告

后台线程通过 `Idle.add` 向主线程报告进度，这个函数负责把翻译动词和数字拼到按钮上：

```vala
private static void report_progress (Gtk.Button button, string verb,
                                      int current, int total) {
    button.label = @"$(verb) $(current)/$(total)…";
}
```

Vala 的字符串插值 `@"..."` 在这里很自然——动词在调用处传入（已经过 `_()` 翻译），数字是变化的计数器。末尾的 `…` 是 Unicode 省略号（U+2026），告诉用户"还在跑"。

## 错误处理：AlertDialog 与 Toast

这个项目用了两个层级的用户反馈：`Adw.AlertDialog` 用于操作失败需要用户确认的场景，`Adw.Toast` 用于非阻塞的状态提示。

```vala
private void show_error_dialog (string title, string detail) {
    var dialog = new Adw.AlertDialog (title, detail);
    dialog.add_response ("ok", "OK");
    dialog.present (active_window);
}

private void show_toast (string msg) {
    toast_overlay.add_toast (new Adw.Toast (msg) { timeout = 3 });
}
```

两者的选择标准不是技术性的，而是用户体验层面的：如果信息需要用户停下来看一眼并确认（"3 个文件处理失败"），用对话框；如果只是告知操作已经完成（"已导出 5 个文件"），用 toast。Toast 3 秒后自动消失，不会打断用户的后续操作。

`Adw.ToastOverlay` 必须包裹整个窗口内容才能让 toast 正确浮动在界面上方。如果把它放在某个子容器里，toast 就会被裁剪在那个容器的范围内。

## 编译与运行

GUI 的编译依赖于 GTK4 和 LibAdwaita。以下是各平台的依赖安装命令：

**Arch Linux：**

```bash
sudo pacman -S --needed glib2 libgexiv2 meson vala gtk4 libadwaita \
    gstreamer gst-plugins-base-libs gdk-pixbuf2 gobject-introspection \
    gst-plugins-good gst-plugins-bad gst-plugin-va
```

**Debian/Ubuntu：**

```bash
sudo apt install build-essential meson valac libgexiv2-dev libglib2.0-dev \
    libgtk-4-dev libadwaita-1-dev libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev libgdk-pixbuf-2.0-dev \
    gobject-introspection libgirepository1.0-dev \
    gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-vaapi
```

**Windows（MSYS2 UCRT64）：**

```bash
pacman -S --needed mingw-w64-ucrt-x86_64-glib2 mingw-w64-ucrt-x86_64-cc \
    mingw-w64-ucrt-x86_64-gexiv2 mingw-w64-ucrt-x86_64-meson \
    mingw-w64-ucrt-x86_64-vala mingw-w64-ucrt-x86_64-gtk4 \
    mingw-w64-ucrt-x86_64-libadwaita mingw-w64-ucrt-x86_64-gstreamer \
    mingw-w64-ucrt-x86_64-gst-plugins-base mingw-w64-ucrt-x86_64-gdk-pixbuf2 \
    mingw-w64-ucrt-x86_64-gobject-introspection \
    mingw-w64-ucrt-x86_64-gst-plugins-good \
    mingw-w64-ucrt-x86_64-gst-plugins-bad
```

构建命令：

```bash
git clone https://github.com/wszqkzqk/live-photo-conv.git
cd live-photo-conv
meson setup builddir --buildtype=release
meson compile -C builddir
meson install -C builddir
```

## 关于后续

这篇文章聚焦于图形界面的架构——`Adw.Application` 的生命周期、`FileDropArea` 自定义控件的封装、`ViewStack` 的三页布局、异步线程与 UI 的协作模式、以及错误处理的分层体系。这些是任何 GTK4 桌面应用都会遇到的通用问题。

下一篇将深入 `liblivephototools` 共享库，拆解 GStreamer / FFmpeg 双后端架构、GExiv2 对 XMP 元数据的操作、以及 KMP 算法做视频偏移检测的实现——也就是底层到底怎么算。
