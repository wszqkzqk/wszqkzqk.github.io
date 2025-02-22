---
layout:     post
title:      GTK/Vala开发基础教程
subtitle:   基础教程
date:       2023-01-19
author:     wszqkzqk
header-img: img/GTK-logo.webp
catalog:    true
tags:       开源软件 GTK Vala
---

本文采用[**CC-BY-SA-3.0**](https://creativecommons.org/licenses/by-sa/3.0/)协议发布，但本文代码采用[**LGPL v2.1+**](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html)协议公开

# 前言

本文假设读者已经掌握Vala语言的基本语法。如果对Vala的基本语法仍然不熟悉，推荐首先阅读[Vala语言官方教程](https://wiki.gnome.org/Projects/Vala/Tutorial)；如果在学习Vala语言前有C#、Java、C、C++等其他语言的开发经验，也可以阅读[面向C#程序员的Vala教程](https://wiki.gnome.org/Projects/Vala/ValaForCSharpProgrammers)或者[面向Java程序员的Vala教程](https://wiki.gnome.org/Projects/Vala/ValaForJavaProgrammers)，阅读笔者的[相关介绍性博客](https://wszqkzqk.github.io/2022/10/17/探索Vala语言/)对快速了解Vala语言的部分特点也有帮助。

本教程不对开发环境安装作介绍。

# GTK概述

GTK是一个用于创建图形用户界面的库。它可以在多种类UNIX平台、Windows和macOS上使用。GTK根据[GNU Library General Public License](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html)条款发布，较为灵活，允许闭源的动态链接。GTK库本身由C语言编写，采用了面向对象的设计，拥有很大的灵活性和可移植性。

GTK可以在多种语言中使用，例如C、Vala、C++、Objective-C、Guile/Scheme、Perl、 Python、JavaScript、Rust、Go、 TOM 、Ada95、Free Pascal和Eiffel。其中，Vala语言专门面向GTK所采用的GObject设计，并且没有使用C语言以外的ABI，与GTK集成良好；同时，Vala又具有大量现代语言的特征，能够大大简化代码结构。使用GTK/Vala技术栈开发GUI程序，是一个高效的选择。

GTK依赖于以下库：

* [GLib](https://developer.gnome.org/glib/stable/)：通用的实用程序库，不局限于图形用户界面。GLib提供了许多有用的数据类型、宏、类型转换、字符串实用程序、文件实用程序、主循环抽象等。
* [GObeject](https://developer.gnome.org/gobject/stable/)：提供类型系统的库，一个含有包括对象类型和信号系统等基本类型结构的集合。
* [GIO](https://developer.gnome.org/gio/stable/)：现代的、易于使用的VFS API，包括文件、驱动器、卷、流的IO的抽象，也包括网络编程IPC和总线。
* [Cairo](https://www.cairographics.org/manual/)：二维图形库，支持多设备输出。
* [OpenGL](https://www.opengl.org/about/)：用于开发可移植、交互式的2D和3D图形应用程序的库。
* [Pango](https://pango.gnome.org/)：用于国际化文本处理的库。
* [gdk-pixbuf](https://developer.gnome.org/gdk-pixbuf/stable/)：小型可移植库，用于由图像数据或图像文件创建`Gdk.Pixbuf`对象。
* [graphene](https://ebassi.github.io/graphene/)：提供向量和矩阵数据类型和操作的小型库。graphene提供使用各种SIMD指令集优化实现。

GTK 分为三个部分：

* GDK：支持多个视窗系统的抽象层。GDK在Wayland、X11、微软Windows和苹果macOS上可用。
* GSK：用于通过绘图操作创建场景图的API，并使用不同的后端渲染它。GSK使用OpenGL、Vulkan和Cairo的渲染器。
* GTK：GUI工具包，包含UI元素、布局管理器、数据等在应用程序中可高效使用的存储类型，用于直接编写GUI。

# 教程

## 基本

我们从一个非常简单的程序开始：创建一个400 × 200像素的空窗口：

[![#~/img/GTK-examples/window-default.webp](/img/GTK-examples/window-default.webp)](/img/GTK-examples/window-default.webp)

创建一个包含以下内容的新文件，命名为`example-0.vala`：

```vala
int main (string[] args) {
    var app = new Gtk.Application (
        "org.gtk.example",
        ApplicationFlags.DEFAULT_FLAGS
    );

    app.activate.connect (() => {
        var win = new Gtk.ApplicationWindow (app) {
            title = "Window",
            default_width = 400,
            default_height = 200
        };
        win.present ();
    });
    return app.run (args);
}
```

使用`valac`命令编译以上程序：

```bash
valac --pkg gtk4 example-0.vala
```

在GTK/Vala应用程序中，主函数`main ()`功能是创建一个`Gtk.Application`对象并运行它。在这个例子中，我们通过`new`关键字创建了一个`Gtk.Application`对象并完成了初始化，命名为`app`。

创建`Gtk.Application`时，您需要选择一个应用程序标识符名称并将其传递给`Gtk.Application ()`的创建函数作为参数。在这个例子中，我们使用了`org.gtk.example`这个名称。应用程序标识符名称的选择问题可以参阅[相关指南](https://developer.gnome.org/documentation/tutorials/application-id.html)。最后，`Gtk.Application ()`创建函数需要传递`Gtk.ApplicationFlags`枚举值作为参数，如果您的应用程序有特殊需要，可以更改默认行为。

接下来，我们将应用程序的激活信号连接到了一个匿名函数中，这也是Vala语言中非常常见的信号连接方式。在本教程中，我们先看完程序的整体结构，再来说明此处的匿名函数中的内容。激活信号将在程序运行`Gtk.Application`对象的`run ()`函数（这个例子中是`app.run ()`）时发出。`Gtk.Application`对象的`run ()`函数也会处理命令行参数（即通过`main ()`函数传递的`args`）。GTK应用程序可以覆盖命令行处理，例如打开通过命令行传递的文件。

然后，`app.run ()`发送激活信号，程序进入之前连接的匿名函数。这是我们构建GTK窗口的地方。用`new`关键字新建一个`Gtk.ApplicationWindow`窗口。这个窗口将含有框架、标题栏和平台依赖的窗口控件。

在创建窗口时，我们使用大括号对`Gtk.ApplicationWindow`对象的属性进行初始化。`title = "Window"`指定了窗口的标题为`Window`，`default_width = 400`与`default_height = 200`则分别指定了窗口的宽和高。最后，调用`win.present ()`函数显示窗口。

触发关闭窗口时（例如按下`X`按钮），`app.run ()`函数将返回表示程序的运行状态的整数，并退出程序。

当程序运行时，GTK会等待接收*事件（events）*。*事件*通常是用户与程序交互产生的输入事件，但也可能是窗口管理器或者其他应用程序发出的信息。当GTK接收到这些事件时，GTK部件可能会发出*信号（signals）*。一般来说，我们通过将这些信号与*信号处理函数（handlers）*相*连接（connect）*让程序按照一定的方式相应用户的输入。

接下来的示例稍微复杂一些，并尝试展示GTK的一些功能。 

## Hello, World

*Hello, World*是编程语言与库中的经典示例程序。

[![#~/img/GTK-examples/hello-world.webp](/img/GTK-examples/hello-world.webp)](/img/GTK-examples/hello-world.webp)

创建一个包含以下内容的新文件，命名为`example-1.vala`：

```vala
int main (string[] args) {
    var app = new Gtk.Application (
        "org.gtk.example",
        ApplicationFlags.DEFAULT_FLAGS
    );

    app.activate.connect (() => {
        var win = new Gtk.ApplicationWindow (app) {
            title = "Hello",
            default_width = 300,
            default_height = 100
        };
        
        var box = new Gtk.Box (Gtk.Orientation.VERTICAL, 0) {
            halign = Gtk.Align.CENTER,
            valign = Gtk.Align.CENTER
        };
        win.child = box;
        
        var button = new Gtk.Button.with_label ("Hello World");
        button.clicked.connect (() => print ("Hello World\n"));
        button.clicked.connect_after (win.destroy);
        box.append (button);
        
        win.present ();
    });
    return app.run (args);
}
```

使用`valac`命令编译以上程序：

```bash
valac --pkg gtk4 example-1.vala
```

如上所示，`example-1.vala`建立在`example-0.vala`的基础上，添加了一个标签为*Hello World*的按钮。我们使用`Gtk.Box`与`Gtk.Button`实现添加，以便控制按钮的大小和布局。

`Gtk.Box`部件在创建时需要传递一个`Gtk.Orientation`枚举值作为参数指定容器的布局方式。`Gtk.Box`可以水平或者竖直布置，但因为我们只有一个按钮，所以在这个例子中，水平与竖直并不重要。`halign = Gtk.Align.CENTER`与`valign = Gtk.Align.CENTER`两个属性设置表示令其中的子部件居中，不填充整个空间。创建完成后，使用`win.child = box`语句指定我们新创建的`Gtk.Box`对象为窗口的子部件。

接下来新建一个`Gtk.Button`变量并初始化，`Gtk.Button.with_label ()`将返回一个指定了标签内容的按钮。

然后，我们指定了`button`被点击时的响应函数，其中一个是用于在终端中打印`Hello World\n`的匿名函数，另一个是关闭窗口的响应函数。这里推荐使用`connect_after ()`而不是`connect ()`连接用于关闭窗口的`win.destroy`函数，这样可以保证`win.destroy`在其他所有连接的函数都调用完成后再调用，无关于在代码中连接的顺序，更加安全。随后，将按钮添加到`box`中。

可以在[GTK](https://wiki.gnome.org/HowDoI/Buttons)与[Vala](https://valadoc.org/gtk4/Gtk.Button.html)的相关文档中查看更多关于按钮创建的信息。

其余在`example-1.vala`中的代码均在`example-0.vala`中有所说明。下一个部分将进一步说明如何添加多个GTK部件到GTK应用程序。 

## 包装

创建程序时，我们可能需要在一个窗口中放多个部件。此时，控制每个部件的位置与大小的方式尤其重要——而这就是包装的用武之地。

GTK包含了多种布局容器，可以用于控制子部件的布局，例如：

* `Gtk.Box`
* `Gtk.Grid`
* `Gtk.Revealer`
* `Gtk.Stack`
* `Gtk.Overlay`
* `Gtk.Paned`
* `Gtk.Expander`
* `Gtk.Fixed`

以下实例展示了用`Gtk.Grid`包装多个按钮：

[![#~/img/GTK-examples/grid-packing.webp](/img/GTK-examples/grid-packing.webp)](/img/GTK-examples/grid-packing.webp)

创建一个包含以下内容的新文件，命名为`example-2.vala`：

```vala
void print_hello () {
    print ("Hello World\n");
}

int main (string[] args) {
    var app = new Gtk.Application (
        "org.gtk.example",
        ApplicationFlags.DEFAULT_FLAGS
    );

    app.activate.connect (() => {
        // 创建新窗口
        var win = new Gtk.ApplicationWindow (app) {
            title = "Grid",
        };

        // 创建包装按钮的网格容器
        var grid = new Gtk.Grid ();
        // 将`grid`设定为`win`的子部件
        win.child = grid;

        var button = new Gtk.Button.with_label ("Button 1");
        button.clicked.connect (print_hello);
        // 将第1个按钮放在网格的(0, 0)位置，并占据(1 × 1)的大小
        grid.attach (button, 0, 0, 1, 1);
        
        button = new Gtk.Button.with_label ("Button 2");
        button.clicked.connect (print_hello);
        // 将第2个按钮放在网格的(1, 0)位置，并占据(1 × 1)的大小
        grid.attach (button, 1, 0, 1, 1);

        button = new Gtk.Button.with_label ("Quit");
        button.clicked.connect (win.destroy);
        // 将第3个按钮放在网格的(0, 1)位置，并占据(2 * 1)的大小
        grid.attach (button, 0, 1, 2, 1);

        win.present ();
    });
    return app.run (args);
}
```

使用`valac`命令编译以上程序：

```bash
valac --pkg gtk4 example-2.vala
```

这段代码中，信号的连接没有采用Vala中常用的定义匿名函数的方式，而是直接定义了一个另外的函数，这是因为本示例中向终端打印`Hello World`的函数被调用了2次，如果用匿名函数，将会重复定义，较为繁琐，不便于阅读，也不便于维护。

## 自定义绘图

许多小部件，如按钮，会自动绘制所有内容。在代码中只需要传递我们所需要的标签即可，部件会自动按照默认方案设置所需的字体、绘制部件轮廓、焦点矩形等。但是在另一些应用场景下，我们可能仍然需要自定义绘图。此时，我们可能需要使用`Gtk.DrawingArea`部件。该部件提供了一个画布，可以设置其绘制函数来进行绘制。

部件的内容也经常需要部分或全部重绘，例如：当另一个窗口移动，露出一部分部件时，或者当包含部件的窗口被调整大小时，往往需要重绘部件。GTK中也可以调用`Gtk.Widget.queue_draw ()`显式地重绘部件。

以下示例展示了如何使用`Gtk.DrawingArea`绘图。这个示例比前面的例子稍微复杂一点，因为它也展示了使用事件控制器处理输入事件。 

[![#~/img/GTK-examples/drawing.webp](/img/GTK-examples/drawing.webp)](/img/GTK-examples/drawing.webp)

创建一个包含以下内容的新文件，命名为`example-3.vala`：

```vala
static Cairo.Surface surface = null;
static double start_x;
static double start_y;

static void clear_surface () {
    var cr = new Cairo.Context (surface);
    cr.set_source_rgb (1, 1, 1);
    cr.paint ();
}

static void draw_brush (Gtk.Widget widget, double x, double y) {
    var cr = new Cairo.Context (surface);
    cr.rectangle (x - 3, y - 3, 6, 6);
    cr.fill ();
    widget.queue_draw ();
}

static int main (string[] args) {
    var app = new Gtk.Application (
        "org.gtk.example",
        ApplicationFlags.DEFAULT_FLAGS
    );

    app.activate.connect (() => {
        var win = new Gtk.ApplicationWindow (app) {
            title = "Drawing Area"
        };

        var frame = new Gtk.Frame (null);
        win.child = frame;

        var drawing_area = new Gtk.DrawingArea () {
            width_request = 400,
            height_request = 300
        };
        frame.child = drawing_area;
        
        drawing_area.set_draw_func ((area, context, width, height) => {
            context.set_source_surface (surface, 0, 0);
            context.paint ();
        });
        drawing_area.resize.connect_after ((widget, width, height) => {
            if (surface != null) {
                surface = null;
            }
            var next_surface = (widget.get_native ()).get_surface ();
            if (next_surface != null) {
                surface = next_surface.create_similar_surface (
                    Cairo.Content.COLOR,
                    width,
                    height
                );
                clear_surface ();
            }
        });
        
        var drag = new Gtk.GestureDrag ();
        drag.set_button (Gdk.BUTTON_PRIMARY);
        drawing_area.add_controller (drag);
        drag.drag_begin.connect ((drag, x, y) => {
            start_x = x;
            start_y = y;
            draw_brush (drawing_area, x, y);
        });
        drag.drag_update.connect ((drag, x, y) => draw_brush (drawing_area, start_x + x, start_y + y));
        drag.drag_end.connect ((drag, x, y) => draw_brush (drawing_area, start_x + x, start_y + y));
        
        var press = new Gtk.GestureClick ();
        press.set_button (Gdk.BUTTON_SECONDARY);
        drawing_area.add_controller (press);
        press.pressed.connect (() => {
            clear_surface ();
            drawing_area.queue_draw ();
        });

        win.present ();
    });
    return app.run (args);
}
```

使用`valac`命令编译以上程序：

```bash
valac --pkg gtk4 example-3.vala
```

## 构建用户界面

有时，我们需要构建的界面较为复杂，或者我们需要分离应用程序的前端界面与后端逻辑。在这样的场景下，我们可能需要使用`GtkBuilder`的xml格式的UI描述功能。

### 使用`Gtk.Builder`打包按钮

创建一个包含以下内容的新文件，命名为`example-4.vala`：

```vala
static void print_hello () {
    print ("Hello World\n");
}

static int main (string[] args) {
    var app = new Gtk.Application (
        "org.gtk.example",
        ApplicationFlags.DEFAULT_FLAGS
    );

    app.activate.connect (() => {
        var builder = new Gtk.Builder ();
        builder.add_from_file ("builder.ui");
        
        var win = builder.get_object ("window") as Gtk.Window;
        win.application = app;
        
        var button = builder.get_object ("button1") as Gtk.Button;
        button.clicked.connect (print_hello);
        
        button = builder.get_object ("button2") as Gtk.Button;
        button.clicked.connect (print_hello);
        
        button = builder.get_object ("quit") as Gtk.Button;
        button.clicked.connect (win.close);
        
        win.present ();
    });
    return app.run (args);
}
```

使用`valac`命令编译以上程序：

```bash
valac --pkg gtk4 example-4.vala
```

在所得的二进制文件所在目录下创建一个包含以下内容的新文件，命名为`builder.ui`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <object id="window" class="GtkWindow">
    <property name="title">Grid</property>
    <child>
      <object id="grid" class="GtkGrid">
        <child>
          <object id="button1" class="GtkButton">
            <property name="label">Button 1</property>
            <layout>
              <property name="column">0</property>
              <property name="row">0</property>
            </layout>
          </object>
        </child>
        <child>
          <object id="button2" class="GtkButton">
            <property name="label">Button 2</property>
            <layout>
              <property name="column">1</property>
              <property name="row">0</property>
            </layout>
          </object>
        </child>
        <child>
          <object id="quit" class="GtkButton">
            <property name="label">Quit</property>
            <layout>
              <property name="column">0</property>
              <property name="row">1</property>
              <property name="column-span">2</property>
            </layout>
          </object>
        </child>
      </object>
    </child>
  </object>
</interface>
```

[![#~/img/GTK-examples/grid-packing.webp](/img/GTK-examples/grid-packing.webp)](/img/GTK-examples/grid-packing.webp)

这个例子呈现效果与[本教程第三个示例](#包装)一样，但本例子中可以将前端界面与后端逻辑分开。这对小型项目意义或许不大，但是对于大型项目可以提高开发效率。此外，xml格式的ui描述文件可以用[Glade（不再积极开发）](https://glade.gnome.org/)或[Cambalache](https://gitlab.gnome.org/jpu/cambalache)等工具由“所见即所得”的方式自动生成，也可以快速查看界面预览，进一步提高开发的效率。

`Gtk.Builder`也可以构造非Gtk部件的对象，例如树模型与调校等。`Gtk.Builder.get_object ()`函数实际上返回的是一个`GLib.Object`对象。

一般来说，我们可以将UI文件的完整参数传递到`Gtk.Builder.add_from_file ()`函数中，导入非当前目录下的UI文件。在Linux平台下，安装UI文件的目录通常是`/usr/share/[应用程序名称]`。也可以将UI文件嵌入源代码，作为字符串，传递到`Gtk.Builder.add_from_string ()`函数加载。但单独将UI描述保存为单独文件还具有以下优点：

* 对UI进行微调时往往不需要重新编译程序
* UI描述与后端逻辑分离更彻底
* 使用复合部件模板将界面重组为单独的类时更加方便

使用`GResource`可能是一个更加折衷的办法：在源代码中，UI文件与代码能够分离，但编译后的程序中则已经嵌入了UI文件，无需另外分发或指定，也不用担心平台相关的路径问题。
