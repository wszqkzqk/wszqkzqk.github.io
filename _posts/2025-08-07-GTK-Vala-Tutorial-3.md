---
layout:     post
title:      GTK4/Vala 教程：构建现代桌面应用
subtitle:   GTK/Vala 开发基础教程 3
date:       2025-08-07
author:     wszqkzqk
header-img: img/GTK-logo.webp
catalog:    true
tags:       开源软件 GTK Vala
---

## 前言

欢迎来到这篇 Vala 和 GTK4 的实战教程！[^1]

[^1]: 本文采用[**CC-BY-SA-4.0**](https://creativecommons.org/licenses/by-sa/4.0/)协议发布，但本文代码采用[**LGPL v2.1+**](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html)协议公开

许多入门教程止步于“Hello, World!”或简单控件演示，这样一方面各部分间缺乏组织逻辑，不便进行复杂演示，另一方面也难以指导读者开发一个真正实用、现代、体验良好的应用。本教程将通过一个**完整的项目案例**，带你从需求分析、界面设计、核心算法、异步网络、数据导出等多个维度，系统梳理依托 GLib/GObject 世界生态的 Vala 开发流程。

本教程适合有一定编程基础，希望深入学习 Vala 语言和最新的 GTK4、LibAdwaita 等开发框架，并渴望开发高质量应用的开发者。如果你还不熟悉 Vala 语言，可以阅读 [Vala 官方文档](https://docs.vala.dev/)，如果想查阅基础库的使用方法，可以参考 [Valadoc.org 提供的 API 参考](https://valadoc.org/)，也欢迎阅读笔者先前写的 [GTK/Vala 开发基础教程](https://wszqkzqk.github.io/2023/01/19/GTK-Vala-Tutorial/)与 [GTK/Vala 开发基础教程 2](https://wszqkzqk.github.io/2025/02/05/GTK-Vala-Tutorial-2/)。

本教程将以笔者实现的[“太阳高度角计算器”](https://github.com/wszqkzqk/FunValaGtkExamples/blob/master/solarangleadw.vala)的完整应用为例，深入剖析其从概念设计到功能实现的每一个环节。这个应用不仅能进行科学计算，还拥有一个使用 LibAdwaita 构建的、支持深色模式的现代化用户界面，并具备异步网络请求、JSON 解析、自定义绘图和文件导出等高级功能。

| [![#~/img/GTK-examples/pku-light-solar-angle-250814.webp](/img/GTK-examples/pku-light-solar-angle-250814.webp)](/img/GTK-examples/pku-light-solar-angle-250814.webp) | [![#~/img/GTK-examples/pku-dark-solar-angle-250814.webp](/img/GTK-examples/pku-dark-solar-angle-250814.webp)](/img/GTK-examples/pku-dark-solar-angle-250814.webp) |
| :--: | :--: |
| 太阳高度角计算器（浅色模式）| 太阳高度角计算器（深色模式）|
| [![#~/img/GTK-examples/fetching-location-solarangle.webp](/img/GTK-examples/fetching-location-solarangle.webp)](/img/GTK-examples/fetching-location-solarangle.webp) | [![#~/img/GTK-examples/timezone-mismatch-solarangle.webp](/img/GTK-examples/timezone-mismatch-solarangle.webp)](/img/GTK-examples/timezone-mismatch-solarangle.webp) |
| 获取地理位置时的加载动画 | 提示与选择 |

通过本教程，你将学到：

* **Vala 语言的核心特性**：面向对象、信号与槽、异步编程等。
* **GTK4 和 LibAdwaita**：如何构建响应式、符合现代 GNOME 设计规范的 UI。
* **Cairo 图形库**：如何在 `Gtk.DrawingArea` 上绘制自定义图表。
* **异步网络编程**：如何在 Vala 中使用 `async` 和 `yield` 从网络 API 获取数据而不会冻结 UI。
* **JSON-GLib**：如何轻松解析网络返回的 JSON 数据。
* **文件 I/O**：如何使用 `Gtk.FileDialog` 和 Cairo 将图表导出为图片（PNG/SVG/PDF），以及如何将数据保存为 CSV 文件。

让我们开始这段激动人心的旅程吧！

## 第一部分：应用概念与设计

在编写任何代码之前，清晰地构思应用的功能和设计是至关重要的。

### 应用目标

我们的目标是创建一个工具，能够：
* 接收用户输入的**地理位置（经纬度）**、**时区**和**日期**。
* 计算出该地点在指定日期内，一天中每一分钟的**太阳高度角**。
* 将计算结果以**直观的图表**形式可视化展示出来。
* 提供**交互功能**，用户可以点击图表上的任意点，查看具体时间的太阳高度角。
* 支持**自动定位**功能，通过网络服务获取用户当前位置。
* 允许用户将**图表导出为图片**，或将**原始数据导出为 CSV 文件**。
* 对于特殊情况，应当为用户提供**友好的提示**。

### UI/UX 设计哲学

为了让应用看起来现代化且用户友好，我们选择使用 **LibAdwaita**。它是 GTK4 的一个辅助库，旨在帮助开发者构建遵循 [GNOME 人机界面指南 (HIG)](https://developer.gnome.org/hig/) 的应用。

我们的界面布局采用常见的**双栏结构**：
* **左侧面板**：作为控制中心，包含所有输入控件（经纬度、时区、日期选择器）和操作按钮（导出、自动定位）。我们使用 `Adw.PreferencesGroup` 来组织这些设置，使其清晰明了。
* **右侧主区域**：用于展示核心内容——太阳高度角图表。这部分将使用 `Gtk.DrawingArea` 进行完全的自定义绘制。

这种设计不仅结构清晰，也为未来可能的响应式布局（例如在小屏幕上将左侧面板收起到侧边栏）打下了基础。

现代桌面应用越来越重视**主题一致性**和**深色模式支持**。LibAdwaita 天生支持系统主题切换，能够自动适配浅色/深色模式，为用户带来舒适的视觉体验。在本项目中，我们不仅让应用自动响应系统主题，还在标题栏右上角提供了**深色模式切换按钮**，用户可以随时手动切换浅色/深色界面。

主题切换的实现思路如下：

* 通过 `Adw.StyleManager` 检测当前系统主题（`dark` 属性）。
  * 如果用户没有手动切换深浅色主题，本应用的深浅色将跟随系统主题，并随系统主题改变而改变。
* 在 `HeaderBar` 添加一个 `Gtk.ToggleButton`，点击时切换 `color_scheme` 属性，实现强制浅色或深色。
  * 用户手动指定主题后，程序深浅色主题将不再跟随系统变化。
* 所有 Cairo 自定义绘图都根据当前主题动态选择配色方案，确保视觉风格统一。
* 主题切换时，主动触发重绘，保证界面即时更新。

这种做法不仅让应用外观与系统保持一致，也为自定义控件和绘图区域带来了良好的主题适配体验。

## 第二部分：项目设置与编译

Vala 代码需要被编译成 C 代码，然后再编译成可执行文件。Vala 编译器 `valac` 会为我们处理好这一切。

读者不妨先**编译并试用**该应用，再继续阅读。这样可以更好地理解每个功能的意义。

### 依赖项

完成本教程涉及的代码编译需要确保系统已安装 Vala、GTK4、LibAdwaita，用于 JSON 解析的 `json-glib` 库，以及 C 编译工具（如 `gcc`）；在 Linux 下，还需要额外安装在 GLib/GIO 中实现网络访问的 `gvfs` 库（Windows则不需要）。笔者在此列举了在 Arch Linux 和 Windows MSYS2 环境下的安装命令：

* Arch Linux：
  ```bash
  sudo pacman -S --needed vala gtk4 libadwaita json-glib gvfs
  ```
* Windows MSYS2：
  在 MSYS2 UCRT64 环境中：
  ```bash
  pacman -S --needed mingw-w64-ucrt-x86_64-vala mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-gtk4 mingw-w64-ucrt-x86_64-libadwaita mingw-w64-ucrt-x86_64-json-glib
  ```

我们的应用的编译参数还可以指定到文件的 Shebang 中，这样在 Linux 操作系统上授予可执行权限后直接执行源代码时，Vala 编译器会自动帮你**编译并运行**程序，一条龙完成。（Windows不支持 Shebang）

对于不熟悉 Shebang 的读者：Shebang 是 Unix/Linux 系统中脚本文件的第一行，用于指定可执行文件的解释器。例如，`#!/usr/bin/env -S vala` 表示使用 `vala` 编译器来执行该脚本。需要注意的是，虽然看起来像是直接运行 Vala 代码，但实际上它会在后台调用 `valac` 编译器来处理代码，并不涉及解释执行。

```vala
#!/usr/bin/env -S vala --pkg=gtk4 --pkg=libadwaita-1 --pkg=json-glib-1.0 -X -lm -X -O2 -X -march=native -X -pipe
```

* `--pkg=gtk4`: GTK4 核心库，用于构建 UI。
* `--pkg=libadwaita-1`: LibAdwaita 库，用于现代化窗口和控件。
* `--pkg=json-glib-1.0`: GLib 的 JSON 支持库，用于解析 JSON 数据。
* `-X -lm`: 传递 `-lm` 链接选项给 C 编译器，因为我们的计算代码使用了数学库 (`math.h`)。
* `-X -O2 -X -march=native -X -pipe`: 这些是传递给 C 编译器的参数。在脚本中应用编译优化存在一些独特考量：`-O2` 提供了良好的优化级别，既明显提升运行时性能，又避免激进优化可能导致的编译时间显著延长 —— 这点尤为重要，因为每次通过 Shebang **直接执行**脚本都会**重新编译**，编译耗时直接影响用户体验；`-march=native` 利用当前 CPU 的全部指令集特性进行优化。由于编译产物**仅在当前机器上运行且不被保留**，不存在跨设备兼容性风险，这有望带来本地性能提升。

### 编译与运行

读者可以将[教程最后的完整代码](#完整源代码)保存为 `solarangleadw.vala`，或者使用`wget`命令直接下载：

```bash
wget https://raw.githubusercontent.com/wszqkzqk/FunValaGtkExamples/master/solarangleadw.vala
```

你可以直接运行这个脚本文件（如果它有执行权限 `chmod +x solarangleadw.vala`），或者使用以下命令手动编译，避免每次运行前都自动编译带来的启动延迟：

```bash
valac --pkg=gtk4 --pkg=libadwaita-1 --pkg=json-glib-1.0 -X -lm -X -O2 -X -pipe solarangleadw.vala
```

需要注意的是，与“执行”用的 `vala` 不同，编译需要使用 `valac` 命令。对于 Windows 用户，如果不希望程序运行的时候总是额外带着一个命令行窗口，可以额外添加 `-X -mwindows` 参数。

## 第三部分：构建用户界面

现在，让我们深入 `activate` 方法，看看 UI 是如何一步步构建起来的。

### 应用与主窗口

基于 LibAdwaita/GTK4 的应用的入口点是一个继承自 `Adw.Application` 的类。在 `activate` 方法中，我们创建了主窗口 `Adw.ApplicationWindow`。

```vala
public class SolarAngleApp : Adw.Application {
    private Adw.ApplicationWindow window;

    // ...

    protected override void activate () {
        window = new Adw.ApplicationWindow (this) {
            title = "Solar Angle Calculator",
        };
        // ...
        window.present ();
    }
}
```

### 布局结构：`Adw.ToolbarView`

我们使用 `Adw.ToolbarView` 作为顶级布局容器。它天生支持顶部栏（`HeaderBar`）和主内容区域，是构建现代 LibAdwaita 应用的理想选择。`Adw.HeaderBar`作为应用的顶部栏，不仅承载了窗口标题，还提供了放置按钮等交互元素的区域。在本应用中，我们利用 `Adw.HeaderBar` 来显示应用标题，并在其右侧集成了深色模式切换按钮，为用户提供便捷的主题控制。

```vala
var header_bar = new Adw.HeaderBar ();
// Add dark mode toggle button
var dark_mode_button = new Gtk.ToggleButton () {
    icon_name = "weather-clear-night-symbolic",
    tooltip_text = "Toggle dark mode",
    active = style_manager.dark,
};
// ...
header_bar.pack_end (dark_mode_button);

var toolbar_view = new Adw.ToolbarView ();
toolbar_view.add_top_bar (header_bar);

// ... main content ...

window.content = toolbar_view;
```

### 左侧输入面板

左侧面板是一个垂直的 `Gtk.Box`，里面包含了几个 `Adw.PreferencesGroup`，用于对设置项进行逻辑分组。这些控件负责收集用户输入，并提供操作入口。

#### 处理加载状态：`Gtk.Stack` 与 `Gtk.Spinner`

在现代应用中，为耗时操作（如网络请求）提供即时反馈至关重要。当用户点击“自动获取位置”时，我们不希望界面冻结无响应，也不希望界面无反应。一个常见的模式是在操作期间用一个**加载指示器（如提供旋转加载动画的 `Gtk.Spinner`）**替换原始控件（如 `Gtk.Button`）。

然而，一个朴素的实现——简单地移除按钮并添加 `Gtk.Spinner`——可能会导致界面布局发生变化，因为两个控件的大小可能不同。这会造成视觉上的“抖动”，影响用户体验。

为了解决这个问题，我们采用了一种更优雅的方案：`Gtk.Stack`。`Gtk.Stack` 是一个容器，它一次只显示其众多子控件中的一个，就像一叠卡片。将按钮和 `Gtk.Spinner` 都放入同一个 `Gtk.Stack` 中，并设置其 `hhomogeneous` 和 `vhomogeneous` 属性为 `true` 时，`Gtk.Stack` 会确保其分配的空间足以容纳其最大的子控件，并让所有子控件都占用同样大小的空间。此外，设置 `transition_type` 为 `Gtk.StackTransitionType.CROSSFADE` 可以实现平滑的淡入淡出过渡效果。

```vala
// Use a stack to keep consistent allocation and avoid layout jitter
location_stack = new Gtk.Stack () {
    hhomogeneous = true,
    vhomogeneous = true,
    transition_type = Gtk.StackTransitionType.CROSSFADE,
};
location_spinner = new Gtk.Spinner ();
location_button = new Gtk.Button () { /* ... */ };

location_stack.add_child (location_button);
location_stack.add_child (location_spinner);
location_stack.visible_child = location_button;
```

这样，当我们通过 `location_stack.visible_child = location_spinner;` 在按钮和加载器之间切换时，容器的尺寸保持不变，从而彻底消除了界面抖动。再配合 `transition_type` 设置一个淡入淡出的过渡效果，用户体验就非常平滑了。

#### 输入与交互控件

* **输入控件 `Adw.SpinRow`**：对于经纬度和时区这类数值输入，`Adw.SpinRow` 是一个非常合适的控件。它将一个标签、一个描述和一个数值调节器组合在一起，美观且便于使用。
    ```vala
    latitude_row = new Adw.SpinRow.with_range (-90, 90, 0.1) {
        title = "Latitude",
        subtitle = "Degrees",
        value = latitude,
        digits = 2,
    };
    ```
    我们通过监听其 `notify::value` 信号来响应用户的输入变化。当值改变时，我们更新内部变量并重绘图表。Vala 语言支持信号与槽机制，这使得响应用户交互变得非常简单。此外，Vala 还可以很方便地使用 lambda 匿名函数来简化代码。
    ```vala
    latitude_row.notify["value"].connect (() => {
        latitude = latitude_row.value;
        update_plot_data ();
        drawing_area.queue_draw ();
    });
    ```

* **日期选择 `Gtk.Calendar`**：`Gtk.Calendar` 控件提供了直观的日期选择功能，用户可以直接在日历界面中选择所需要的日期。我们将其放入一个 `Adw.ActionRow` 中，以保持与其他设置项风格的统一。

### 右侧绘图区域

右侧区域的核心是 `Gtk.DrawingArea`。它本质上是一块空白画布，我们可以通过 `set_draw_func` 注册一个绘图函数，来控制其显示内容。

```vala
drawing_area = new Gtk.DrawingArea () { /* ... */ };
drawing_area.set_draw_func (draw_sun_angle_chart);
```

每当需要重绘时（例如窗口大小改变、数据更新），这个函数就会被调用。此外，在需要的时候，我们也可以通过 `drawing_area.queue_draw()` 主动发起一次重绘。

## 第四部分：核心功能实现

现在，我们来实现应用的核心功能：计算与表达。

### 太阳高度角计算

> **【2025年10月更新】**
>
> 本程序的完整代码已更新为基于 [**Meeus 算法**](http://www.jgiesen.de/elevaz/basics/meeus.htm)的高精度实现。Meeus 算法是国际上广受认可的天文算法，能在不依赖大型星历表的情况下，达到非常高的精度（笔者进行了实测：分散选取南北半球低中高纬度不同位置，在 1949-2050 年间分散选取 9 年，测试其中每个整时刻的高度角计算值与公认高精度的专业天文库 [Astropy](https://github.com/astropy/astropy) 的结果的误差，测试发现整体 **RMSD 仅 0.0038°**，如此多的数据中最大误差绝对值也仅为 0.0122°）。
> 如果你对算法的理论背景、实现细节及其在 Vala 语言中的最佳实践感兴趣，请移步阅读笔者的续篇教程：**[Vala 数值计算实践：高精度太阳位置算法](https://wszqkzqk.github.io/2025/10/08/GTK-Vala-Tutorial-Advanced-Solar-Calculation/)**。

`generate_sun_angles` 函数是应用计算的核心。笔者在此实现了 Meeus 算法的等价变体，通过精确的天体力学模型计算太阳位置。算法的主要参考来源是 [Paul Schlyter 和 J. Giesen 总结的高精度算法页面](http://www.jgiesen.de/elevaz/basics/meeus.htm)。

#### 时间基准：从 J2000.0 历元起算的天数

天文计算需要统一的时间标尺。我们使用 **J2000.0 历元**（2000 年 1 月 1 日 12:00 UTC）作为参考点，由于 GLib 的 `DateTime.get_julian ()` 方法返回的儒略日是从公元1年1月1日开始计算的（注意不是常见的公元前4713年），我们需要将其转换为相对于 J2000.0 的天数：

```vala
var date = new GLib.Date ();
date.set_dmy (day, month, year);
var julian_date = (double) date.get_julian ();
double base_days_from_epoch = julian_date - 730120.5; // 当天 00:00 UTC 到 J2000.0 的天数
```

#### 黄赤交角 (Obliquity of the Ecliptic, $\epsilon$)

地球自转轴相对黄道的倾角，随时间微小变化：

$$
\epsilon_\text{degrees} = 23.439291111 - 0.0000003560347 d - 1.2285 \times 10^{-16} d^2 + 1.0335 \times 10^{-20} d^3
$$

#### 轨道参数：平黄经 ($L$) 和平近点角 ($M$)

*   **平黄经**：描述理想化匀速圆周运动下的“平均太阳”在黄道上的位置，从**春分点**开始计算

$$
L_\text{degrees} = 280.46645 + 0.98564736 d + 2.2727 \times 10^{-13} d^2
$$

*   **平近点角**：描述理想化匀速圆周运动下的“平均太阳”在轨道上从**近地点**出发的角度

$$
M_\text{degrees} = 357.52910 + 0.985600282 d - 1.1686 \times 10^{-13} d^2 - 9.85 \times 10^{-21} d^3
$$

#### 中心差修正与真黄经 ($\lambda$)

考虑地球椭圆轨道的影响，通过中心差 $C$ 将平黄经修正为真黄经 $\lambda$：

$$
C_\text{degrees} = (1.914600 - 0.00000013188 d - 1.049 \times 10^{-14} d^2) \sin(M) + (0.019993 - 0.0000000027652 d) \sin(2M) + 0.000290 \sin(3M)
$$

$$
\lambda = L + C
$$

#### 坐标转换：赤纬 ($\delta$) 和赤经 (RA)

从黄道坐标系转换到赤道坐标系：

$$
\sin(\delta) = \sin(\epsilon) \sin(\lambda)
$$

$$
RA = \text{atan2}(\cos(\epsilon) \sin(\lambda), \cos(\lambda))
$$

#### 真太阳时 (True Solar Time, $TST$)

考虑均时差和经度修正，将本地钟表时间转换为真太阳时：

$$
TST_\text{minutes} = T_\text{local,minutes} + EoT_\text{minutes} + 4 \times \lambda_\text{longitude,degrees} - 60 \times TZ_\text{hours}
$$

#### 时角 (Hour Angle, $HA$) 与太阳高度角 ($\alpha$)

*   时角描述太阳相对本地子午线的角距离：$HA_\text{degrees} = TST_\text{minutes} / 4 - 180$
*   结合观测地纬度 $\phi$、太阳赤纬 $\delta$ 和时角 $HA$，使用球面三角公式计算高度角：

$$
\sin(\alpha) = \sin(\phi)\sin(\delta) + \cos(\phi)\cos(\delta)\cos(HA)
$$

算法对一天中每一分钟都进行采样计算，将结果存储在 `sun_angles` 数组中，为后续的可视化和交互提供数据支持。

### 自定义绘图与 Cairo

`draw_sun_angle_chart` 函数是应用的绘制核心。它接收一个 `Cairo.Context` 对象（通常简写为 `cr`），你可以把它想象成 Cairo 的画笔，拥有颜色、粗细、字体等属性。

绘图过程遵循一个清晰的层次结构：
1. **主题颜色**：我们定义了一个 `ThemeColors` 结构体，并准备了 `LIGHT_THEME` 和 `DARK_THEME` 两套颜色。在绘图开始时，根据 `style_manager.dark` 的状态选择合适的颜色方案，实现了对系统深色/浅色模式的自适应。
2. **绘制背景和坐标系**：首先填充背景色，然后绘制网格线、坐标轴和标签。这里大量使用了 `cr.move_to()`, `cr.line_to()`, `cr.stroke()` 等基本绘图命令。对于文本，`cr.show_text()` 用于绘制，`cr.text_extents()` 用于测量文本尺寸以实现精确定位。
3. **绘制数据曲线**：这是最关键的一步。我们遍历 `sun_angles` 数组，将每个数据点（时间 -> x, 角度 -> y）转换为画布上的像素坐标，然后用 `cr.line_to()` 将这些点连接起来，形成平滑的曲线。
4. **绘制交互点**：如果用户点击了图表 (`has_click_point` 为 `true`)，我们会在对应位置绘制一个圆点和十字参考线，为用户提供即时反馈。
5. **绘制标题**：在图表顶部添加动态标题，显示当前的日期和位置信息。

### 交互式图表：`Gtk.GestureClick`

为了响应用户的点击，我们给 `drawing_area` 添加了一个 `Gtk.GestureClick` 控制器。

```vala
var click_controller = new Gtk.GestureClick ();
click_controller.pressed.connect (on_chart_clicked);
drawing_area.add_controller (click_controller);
```

在 `on_chart_clicked` 回调函数中：
1. 获取点击的 `x`, `y` 坐标。
2. 将 `x` 坐标从像素值转换回一天中的时间（小时）。
3. 根据时间从 `sun_angles` 数组中查找到对应的太阳高度角。
4. 更新 `click_info_label` 的文本，显示选定点的信息。
5. 设置 `has_click_point = true` 并调用 `drawing_area.queue_draw()`，请求重绘以显示点击标记。

### 异步网络请求与 JSON 解析

自动定位功能是本应用的一个亮点，它完美地展示了 Vala 强大的**异步处理**能力：网络请求是耗时的 I/O 操作，如果我们在主线程中**直接请求**，在收到网络响应前整个应用的 **UI 会被冻结**，这会带来极差的用户体验；因此，我们使用 Vala 的异步编程特性来处理这一问题。

*   **Vala 的 `async` / `yield`**：
    Vala 借鉴了 C# 的 `async/await` 语法，使得异步编程像写同步代码一样直观。
    * 我们将网络请求逻辑放在一个 `async` 方法 `get_location_async` 中。
    * 当遇到耗时操作时（如 `file.read_async`），我们使用 `yield` 关键字。这会“暂停”当前方法的执行，将控制权交还给主事件循环（让 UI 保持响应），当 I/O 操作完成后，方法会自动从 `yield` 的地方继续执行。
    * 为了避免网络请求长时间无响应，我们还引入了**超时机制**。通过 `GLib.Cancellable` 和 `GLib.Timeout.add_seconds`，我们可以在指定时间（例如 5 秒）后取消网络请求，并向用户显示错误信息，提升应用的健壮性。
      ```vala
      private async void get_location_async () throws IOError {
          var file = File.new_for_uri ("https://ipapi.co/json/");
          var parser = new Json.Parser ();

          // 设置 5 秒超时
          var cancellable = new Cancellable ();
          var timeout_id = Timeout.add_seconds_once (5, () => {
              cancellable.cancel ();
          });

          try {
              var stream = yield file.read_async (Priority.DEFAULT, cancellable);
              // ...
          } catch (Error e) {
              // ...
          } finally {
              // 取消超时回调
              if (!cancellable.is_cancelled ()) {
                  Source.remove (timeout_id);
              }
          }
      }
      ```
*   **JSON-GLib 解析**：
    JSON-GLib 提供了一套健壮的 API 来遍历和提取 JSON 结构中的数据，并能很好地处理潜在的错误。获取到网络响应后，我们使用 `Json.Parser` 来解析它。得益于 JSON-GLib 与 GLib/GObject/GIO 生态的强大集成，我们可以直接方便地使用 `parser.load_from_stream_async` 从网络流中异步加载和解析 JSON 数据，无需手动处理字节流。
    ```vala
    var parser = new Json.Parser ();
    yield parser.load_from_stream_async (stream, cancellable);
    var root_object = parser.get_root ().get_object ();
    
    if (root_object.has_member ("latitude") && root_object.has_member ("longitude")) {
        latitude = root_object.get_double_member ("latitude");
        longitude = root_object.get_double_member ("longitude");
    } else {
        throw new IOError.FAILED ("No coordinates found in the response");
    }
    // ...
    ```
*   **时区冲突处理**：
    在自动定位时，网络服务返回的时区信息可能与用户系统当前设置的时区不同。为了提供更好的用户体验，应用会检测这种差异。如果发现网络时区与系统时区不一致，应用会弹出一个 `Adw.AlertDialog` （详见后文）对话框，询问用户希望使用哪个时区。用户选择后，应用会根据用户的决定更新时区设置。这种交互通过 `yield dialog.choose(window, null)` 实现，它会异步等待用户的选择，并在用户做出选择后继续执行代码。

### 错误处理与用户交互：`Adw.AlertDialog`

在涉及网络请求等可能失败的操作时，提供明确的错误反馈至关重要。我们使用 `Adw.AlertDialog` 来创建符合 GNOME HIG 规范的现代化错误对话框。此外，`Adw.AlertDialog` 不仅可以用于显示简单的错误信息，还可以通过 `add_response` 和 `choose` 方法实现更复杂的异步用户选择，在本示例中是本地与 IP 时区冲突时让用户选择使用哪个时区：

```vala
private void show_error_dialog (string title, string error_message) {
    var dialog = new Adw.AlertDialog (
        title,  // 主标题
        error_message  // 详细描述
    );

    // 添加确认按钮（自动遵循当前主题）
    dialog.add_response ("ok", "OK");
    // 显示对话框并关联到主窗口
    dialog.present (window); 
    // 同时输出到终端
    message ("%s: %s", title, error_message); 
}

// 利用 Adw.AlertDialog 给用户提供选择
private async void handle_timezone_mismatch (double network_tz_offset, double local_tz_offset) {
    var dialog = new Adw.AlertDialog (
        "Timezone Mismatch",
        "The timezone from the network (UTC%+.2f) differs from your system's timezone (UTC%+.2f).\n\nWhich one would you like to use?".printf (
            network_tz_offset,
            local_tz_offset
        )
    );
    dialog.add_response ("network", "Use Network Timezone");
    dialog.add_response ("local", "Use System Timezone");
    dialog.default_response = "network"; // 默认选择网络时区

    // 异步等待用户的选择
    string choice = yield dialog.choose (window, null);

    if (choice == "network") {
        timezone_offset_hours = network_tz_offset;
    } else {
        timezone_offset_hours = local_tz_offset;
    }
    // ... 更新 UI ...
}
```

`Adw.AlertDialog` 自动适应深浅色模式，符合 GNOME 人机界面指南。而且无需复杂布局，标题+描述+交互按钮三步完成创建，十分方便。对于文件保存对话框，当用户取消操作时，我们现在会更优雅地处理，避免弹出不必要的错误提示框，只在终端输出日志。

### 文件导出

*   **`Gtk.FileDialog`**
    为了提供现代化的文件保存体验，我们使用 `Gtk.FileDialog`。它取代了旧的 `Gtk.FileChooserDialog`，通过异步回调函数处理用户的选择。
    ```vala
    var file_dialog = new Gtk.FileDialog () { /* ... */ };
    file_dialog.save.begin (window, null, (obj, res) => {
        try {
            var file = file_dialog.save.end (res);
            if (file != null) {
                export_chart (file);
            }
        } catch (Error e) {
            // 用户取消操作时，不显示警告对话框，仅在终端输出日志
            message ("Image file has not been saved: %s", e.message);
        }
    });
    ```
*   **导出为图片**:
    Cairo 的一个强大之处在于其“设备无关性”。我们的 `draw_sun_angle_chart` 函数不仅可以向屏幕绘图，也可以向不同的**表面 (Surface)** 绘图。通过创建 `Cairo.SvgSurface`、`Cairo.PdfSurface` 或 `Cairo.ImageSurface`，我们可以将完全相同的绘图代码重定向到文件，从而轻松实现 SVG、PDF 和 PNG 格式的导出。
*   **导出为 CSV**:
    CSV 导出则是一个标准的文本文件写入过程。我们使用 `DataOutputStream` 来高效地将格式化的字符串写入文件。在数据之前，我们还写入了以 `#` 开头的注释行，作为元数据，这是一种良好的实践。

## 使用

* **启动应用**：运行编译后的程序。
* **设置位置**：
    * **自动**：点击“Auto-detect Location”按钮。应用会尝试通过网络获取你当前的位置和时区，自动填充这些值并更新图表。
    * **手动**：在左侧面板中，拖动或输入你的纬度（Latitude）、经度（Longitude）和时区（Timezone）。图表会实时更新。
* **选择日期**：点击左侧的日历，选择你感兴趣的任何日期。
* **分析图表**：
    * 右侧的图表显示了从 0 点到 24 点的太阳高度角变化。
    * 水平的黑线代表地平线（0°）。曲线在地平线上方表示白天，下方表示夜晚。
    * 点击图表上的任意位置，左下角的“Selected Point”区域会显示该精确时间的太阳高度角，同时图表上会出现一个蓝色的标记点和参考线。
* **导出结果**：
    * **图片**：点击“Export Image”，在弹出的对话框中选择保存位置、文件名和格式（PNG, SVG, PDF）。
    * **数据**：点击“Export CSV”，可以将当天每分钟的太阳高度角数据保存为 CSV 文件，以便在电子表格软件（如 LibreOffice Calc, Excel）中进行进一步分析。

## 总结

这个太阳高度角计算器功能集中，“麻雀虽小，五脏俱全”。它综合运用了 Vala 语言的现代特性、GTK4/LibAdwaita 的 UI 构建能力、Cairo 的强大绘图功能，以及 GLib 提供的异步处理和数据解析工具。

在这个实例中，读者不仅可以学会如何使用这些独立的工具，更重要的是，读者还可以了看到如何将它们有机地结合起来，构建一个功能完整、体验良好、代码结构清晰的现代桌面应用程序。希望这个教程能为你未来的 Vala/GTK 开发之旅提供坚实的垫脚石。

## 完整源代码

```vala
#!/usr/bin/env -S vala --pkg=gtk4 --pkg=libadwaita-1 --pkg=json-glib-1.0 -X -lm -X -O2 -X -march=native -X -pipe
/* SPDX-License-Identifier: LGPL-2.1-or-later */

/**
 * Solar Angle Calculator Application.
 * Copyright (C) 2025 wszqkzqk <wszqkzqk@qq.com>
 * A libadwaita application that calculates and visualizes solar elevation angles
 * throughout the day for a given location and date. The application provides
 * an interactive interface for setting latitude, longitude, timezone, and date,
 * and displays a real-time chart of solar elevation angles with export capabilities.
 */
public class SolarAngleApp : Adw.Application {
    // Constants for solar angle calculations
    private const double DEG2RAD = Math.PI / 180.0;
    private const double RAD2DEG = 180.0 / Math.PI;
    private const int RESOLUTION_PER_MIN = 1440; // 1 sample per minute
    // Constants for drawing area
    private const int MARGIN_LEFT = 70;
    private const int MARGIN_RIGHT = 20;
    private const int MARGIN_TOP = 50;
    private const int MARGIN_BOTTOM = 70;

    // Model / persistent state
    private DateTime selected_date;
    private double sun_angles[RESOLUTION_PER_MIN];
    private double latitude = 0.0;
    private double longitude = 0.0;
    private double timezone_offset_hours = 0.0;
    // Interaction / transient UI state
    private double clicked_time_hours = 0.0;
    private double corresponding_angle = 0.0;
    private bool has_click_point = false;

    // UI widgets
    private Adw.ApplicationWindow window;
    private Gtk.DrawingArea drawing_area;
    private Gtk.Label click_info_label;
    private Gtk.Stack location_stack;
    private Gtk.Spinner location_spinner;
    private Gtk.Button location_button;
    private Adw.SpinRow latitude_row;
    private Adw.SpinRow longitude_row;
    private Adw.SpinRow timezone_row;

    // Color theme struct for chart drawing
    private struct ThemeColors {
        double bg_r; double bg_g; double bg_b; // Background
        double grid_r; double grid_g; double grid_b; double grid_a; // Grid with alpha
        double axis_r; double axis_g; double axis_b; // Axes
        double text_r; double text_g; double text_b; // Text
        double curve_r; double curve_g; double curve_b; // Curve
        double shade_r; double shade_g; double shade_b; double shade_a; // Shaded area with alpha
        double point_r; double point_g; double point_b; // Click point
        double line_r; double line_g; double line_b; double line_a; // Guide line with alpha
    }

    // Light theme
    private static ThemeColors LIGHT_THEME = {
        bg_r: 1.0, bg_g: 1.0, bg_b: 1.0,                    // White background
        grid_r: 0.5, grid_g: 0.5, grid_b: 0.5, grid_a: 0.5, // Gray grid
        axis_r: 0.0, axis_g: 0.0, axis_b: 0.0,              // Black axes
        text_r: 0.0, text_g: 0.0, text_b: 0.0,              // Black text
        curve_r: 1.0, curve_g: 0.5, curve_b: 0.0,           // Orange curve
        shade_r: 0.7, shade_g: 0.7, shade_b: 0.7, shade_a: 0.3, // Light gray shade
        point_r: 0.0, point_g: 0.0, point_b: 1.0,           // Blue point
        line_r: 0.0, line_g: 0.0, line_b: 1.0, line_a: 0.5  // Blue guide lines
    };

    // Dark theme
    private static ThemeColors DARK_THEME = {
        bg_r: 0.0, bg_g: 0.0, bg_b: 0.0,                    // Black background
        grid_r: 0.5, grid_g: 0.5, grid_b: 0.5, grid_a: 0.5, // Gray grid
        axis_r: 1.0, axis_g: 1.0, axis_b: 1.0,              // White axes
        text_r: 1.0, text_g: 1.0, text_b: 1.0,              // White text
        curve_r: 1.0, curve_g: 0.5, curve_b: 0.0,           // Orange curve
        shade_r: 0.3, shade_g: 0.3, shade_b: 0.3, shade_a: 0.7, // Dark gray shade
        point_r: 0.3, point_g: 0.7, point_b: 1.0,           // Light blue point
        line_r: 0.3, line_g: 0.7, line_b: 1.0, line_a: 0.7  // Light blue guide lines
    };

    /**
     * Creates a new SolarAngleApp instance.
     *
     * Initializes the application with a unique application ID and sets
     * the selected date to the current local date.
     */
    public SolarAngleApp () {
        Object (application_id: "com.github.wszqkzqk.SolarAngleAdw");
        selected_date = new DateTime.now_local ();
    }

    /**
     * Activates the application and creates the main window.
     *
     * Sets up the user interface including input controls, drawing area,
     * and initializes the plot data with current settings.
     */
    protected override void activate () {
        window = new Adw.ApplicationWindow (this) {
            title = "Solar Angle Calculator",
        };

        // Create header bar
        var header_bar = new Adw.HeaderBar () {
            title_widget = new Adw.WindowTitle ("Solar Angle Calculator", ""),
        };

        // Add dark mode toggle button
        var dark_mode_button = new Gtk.ToggleButton () {
            icon_name = "weather-clear-night-symbolic",
            tooltip_text = "Toggle dark mode",
            active = style_manager.dark,
        };
        dark_mode_button.toggled.connect (() => {
            style_manager.color_scheme = (dark_mode_button.active) ? Adw.ColorScheme.FORCE_DARK : Adw.ColorScheme.FORCE_LIGHT;
            drawing_area.queue_draw ();
        });

        // Listen for system theme changes
        style_manager.notify["dark"].connect (() => {
            drawing_area.queue_draw ();
        });

        header_bar.pack_end (dark_mode_button);

        // Create toolbar view to hold header bar and content
        var toolbar_view = new Adw.ToolbarView ();
        toolbar_view.add_top_bar (header_bar);

        var main_box = new Gtk.Box (Gtk.Orientation.HORIZONTAL, 0);

        var left_panel = new Gtk.Box (Gtk.Orientation.VERTICAL, 12) {
            hexpand = false,
            vexpand = true,
            width_request = 320,
            margin_start = 12,
            margin_end = 12,
            margin_top = 12,
            margin_bottom = 12,
        };

        // Location and Time Settings Group
        var location_time_group = new Adw.PreferencesGroup () {
            title = "Location and Time Settings",
        };

        // Auto-detect location button
        var location_detect_row = new Adw.ActionRow () {
            title = "Auto-detect Location",
            subtitle = "Get current location and timezone",
            activatable = true,
        };

        var location_box = new Gtk.Box (Gtk.Orientation.HORIZONTAL, 6);
        // Use a stack to keep consistent allocation and avoid layout jitter
        location_stack = new Gtk.Stack () {
            hhomogeneous = true,
            vhomogeneous = true,
            transition_type = Gtk.StackTransitionType.CROSSFADE,
        };
        location_spinner = new Gtk.Spinner ();
        location_button = new Gtk.Button () {
            icon_name = "find-location-symbolic",
            valign = Gtk.Align.CENTER,
            css_classes = { "flat" },
            tooltip_text = "Auto-detect current location",
        };
        location_button.clicked.connect (on_auto_detect_location);
        // Add to stack as separate pages
        location_stack.add_child (location_button);
        location_stack.add_child (location_spinner);
        location_stack.visible_child = location_button;
        // Place stack into the suffix box
        location_box.append (location_stack);
        location_detect_row.add_suffix (location_box);
        location_detect_row.activated.connect (on_auto_detect_location);

        latitude_row = new Adw.SpinRow.with_range (-90, 90, 0.1) {
            title = "Latitude",
            subtitle = "Degrees",
            value = latitude,
            digits = 2,
        };
        latitude_row.notify["value"].connect (() => {
            latitude = latitude_row.value;
            update_plot_data ();
            drawing_area.queue_draw ();
        });

        longitude_row = new Adw.SpinRow.with_range (-180.0, 180.0, 0.1) {
            title = "Longitude",
            subtitle = "Degrees",
            value = longitude,
            digits = 2,
        };
        longitude_row.notify["value"].connect (() => {
            longitude = longitude_row.value;
            update_plot_data ();
            drawing_area.queue_draw ();
        });

        timezone_row = new Adw.SpinRow.with_range (-12.0, 14.0, 0.5) {
            title = "Timezone",
            subtitle = "Hours from UTC",
            value = timezone_offset_hours,
            digits = 2,
        };
        timezone_row.notify["value"].connect (() => {
            timezone_offset_hours = timezone_row.value;
            update_plot_data ();
            drawing_area.queue_draw ();
        });

        location_time_group.add (location_detect_row);
        location_time_group.add (latitude_row);
        location_time_group.add (longitude_row);
        location_time_group.add (timezone_row);

        // Date Selection Group
        var date_group = new Adw.PreferencesGroup () {
            title = "Date Selection",
        };

        var calendar = new Gtk.Calendar () {
            margin_start = 12,
            margin_end = 12,
            margin_top = 6,
            margin_bottom = 6,
        };
        calendar.day_selected.connect (() => {
            selected_date = calendar.get_date ();
            update_plot_data ();
            drawing_area.queue_draw ();
        });

        var calendar_row = new Adw.ActionRow ();
        calendar_row.child = calendar;
        date_group.add (calendar_row);

        // Export Group
        var export_group = new Adw.PreferencesGroup () {
            title = "Export",
        };

        var export_image_row = new Adw.ActionRow () {
            title = "Export Image",
            subtitle = "Save chart as PNG, SVG, or PDF",
            activatable = true,
        };
        var export_image_button = new Gtk.Button () {
            icon_name = "document-save-symbolic",
            valign = Gtk.Align.CENTER,
            css_classes = { "flat" },
        };
        export_image_button.clicked.connect (on_export_clicked);
        export_image_row.add_suffix (export_image_button);
        export_image_row.activated.connect (on_export_clicked);

        var export_csv_row = new Adw.ActionRow () {
            title = "Export CSV",
            subtitle = "Save data as CSV file",
            activatable = true,
        };
        var export_csv_button = new Gtk.Button () {
            icon_name = "x-office-spreadsheet-symbolic",
            valign = Gtk.Align.CENTER,
            css_classes = { "flat" },
        };
        export_csv_button.clicked.connect (on_export_csv_clicked);
        export_csv_row.add_suffix (export_csv_button);
        export_csv_row.activated.connect (on_export_csv_clicked);

        export_group.add (export_image_row);
        export_group.add (export_csv_row);

        // Click Info Group
        var click_info_group = new Adw.PreferencesGroup () {
            title = "Selected Point",
        };

        click_info_label = new Gtk.Label ("Click on chart to view data\n") {
            halign = Gtk.Align.START,
            margin_start = 12,
            margin_end = 12,
            margin_top = 6,
            margin_bottom = 6,
            wrap = true,
        };

        var click_info_row = new Adw.ActionRow ();
        click_info_row.child = click_info_label;
        click_info_group.add (click_info_row);

        left_panel.append (location_time_group);
        left_panel.append (date_group);
        left_panel.append (export_group);
        left_panel.append (click_info_group);

        drawing_area = new Gtk.DrawingArea () {
            hexpand = true,
            vexpand = true,
            width_request = 600,
            height_request = 500,
        };
        drawing_area.set_draw_func (draw_sun_angle_chart);

        // Add click event controller
        var click_controller = new Gtk.GestureClick ();
        click_controller.pressed.connect (on_chart_clicked);
        drawing_area.add_controller (click_controller);

        main_box.append (left_panel);
        main_box.append (drawing_area);

        toolbar_view.content = main_box;

        update_plot_data ();

        window.content = toolbar_view;
        window.present ();
    }

    /**
     * Handles auto-detect location button click.
     * 
     * Uses a free IP geolocation service to get current location and timezone.
     */
    private void on_auto_detect_location () {
        location_button.sensitive = false;
        // Switch to spinner page without changing allocation size
        location_stack.visible_child = location_spinner;
        location_spinner.start ();

         // Run async to avoid blocking the UI
         get_location_async.begin ((obj, res) => {
            try {
                get_location_async.end (res);
            } catch (Error e) {
                show_error_dialog ("Location Detection Failed", e.message);
            }

            location_button.sensitive = true;
            location_spinner.stop ();
            // Switch back to button page
            location_stack.visible_child = location_button;
         });
     }

    /**
     * Asynchronously gets current location using IP geolocation service with timeout.
     */
    private async void get_location_async () throws IOError {
        var file = File.new_for_uri ("https://ipapi.co/json/");
        var parser = new Json.Parser ();

        var cancellable = new Cancellable ();
        var timeout_id = Timeout.add_seconds_once (5, () => {
            cancellable.cancel ();
        });

        try {
            var stream = yield file.read_async (Priority.DEFAULT, cancellable);
            yield parser.load_from_stream_async (stream, cancellable);
        } catch (Error e) {
            throw new IOError.FAILED ("Failed to get location: %s", e.message);
        } finally {
            // MUST free the timeout here (local variable `cancellable` is NOT owned by Timeout)
            if (!cancellable.is_cancelled ()) {
                Source.remove (timeout_id);
            }
        }

        var root_object = parser.get_root ().get_object ();
        if (root_object.get_boolean_member_with_default ("error", false)) {
            throw new IOError.FAILED ("Location service error: %s", root_object.get_string_member_with_default ("reason", "Unknown error"));
        }

        if (root_object.has_member ("latitude") && root_object.has_member ("longitude")) {
            latitude = root_object.get_double_member ("latitude");
            longitude = root_object.get_double_member ("longitude");
        } else {
            throw new IOError.FAILED ("No coordinates found in the response");
        }

        double network_tz_offset = 0.0;
        bool has_network_tz = false;

        if (root_object.has_member ("utc_offset")) {
            var offset_str = root_object.get_string_member ("utc_offset");
            network_tz_offset = double.parse (offset_str) / 100.0;
            has_network_tz = true;
        }

        // Get local system's current timezone offset
        var timezone = new TimeZone.local ();
        var time_interval = timezone.find_interval (GLib.TimeType.UNIVERSAL, selected_date.to_unix ());
        var local_tz_offset = timezone.get_offset (time_interval) / 3600.0;

        const double TZ_EPSILON = 0.01; // Epsilon for floating point comparison
        if (has_network_tz && (!(-TZ_EPSILON < (network_tz_offset - local_tz_offset) < TZ_EPSILON))) {
            const string RESPONSE_NETWORK = "network"; // ID for network timezone
            const string RESPONSE_LOCAL = "local"; // ID for local timezone

            // Timezones differ, prompt user for a choice
            var dialog = new Adw.AlertDialog (
                "Timezone Mismatch",
                "The timezone from the network (UTC%+.2f) differs from your system's timezone (UTC%+.2f).\n\nWhich one would you like to use?".printf (
                    network_tz_offset,
                    local_tz_offset
                )
            );
            dialog.add_response (RESPONSE_NETWORK, "Use Network Timezone");
            dialog.add_response (RESPONSE_LOCAL, "Use System Timezone");
            dialog.default_response = RESPONSE_NETWORK;

            // Asynchronously wait for the user's choice
            unowned var choice = yield dialog.choose (window, null);
            timezone_offset_hours = (choice == RESPONSE_NETWORK) ? network_tz_offset : local_tz_offset;
        } else {
            // Network's timezone is the same as local's or unavailable
            timezone_offset_hours = local_tz_offset;
        }

        latitude_row.value = latitude;
        longitude_row.value = longitude;
        timezone_row.value = timezone_offset_hours;
        update_plot_data ();
        drawing_area.queue_draw ();
    }

    /**
     * Shows a generic error dialog and logs the error message.
     *
     * @param title The title of the error dialog.
     * @param error_message The error message to display.
     */
    private void show_error_dialog (string title, string error_message) {
        var dialog = new Adw.AlertDialog (title, error_message);
        dialog.add_response ("ok", "OK");
        dialog.present (window);
        message ("%s: %s", title, error_message);
    }

    /**
     * Calculates solar elevation angles for each minute of the day.
     * Based on http://www.jgiesen.de/elevaz/basics/meeus.htm
     *
     * @param latitude_rad Latitude in radians.
     * @param longitude_deg Longitude in degrees.
     * @param timezone_offset_hrs Timezone offset from UTC in hours.
     * @param julian_date GLib's Julian Date for the day (from 0001-01-01).
     */
    private void generate_sun_angles (double latitude_rad, double longitude_deg, double timezone_offset_hrs, double julian_date) {
        double sin_lat = Math.sin (latitude_rad);
        double cos_lat = Math.cos (latitude_rad);
        // Base days from J2000.0 epoch (GLib's Julian Date is days since 0001-01-01 12:00 UTC)
        double base_days_from_epoch = julian_date - 730120.5; // julian_date's 00:00 UTC to 2000-01-01 12:00 UTC
        // Pre-compute obliquity with higher-order terms (changes very slowly)
        double base_days_sq = base_days_from_epoch * base_days_from_epoch;
        double base_days_cb = base_days_sq * base_days_from_epoch;
        double obliquity_deg = 23.439291111 - 3.560347e-7 * base_days_from_epoch - 1.2285e-16 * base_days_sq + 1.0335e-20 * base_days_cb;
        double obliquity_sin = Math.sin (obliquity_deg * DEG2RAD);
        double obliquity_cos = Math.cos (obliquity_deg * DEG2RAD);
        double ecliptic_c1 = 1.914600 - 1.3188e-7 * base_days_from_epoch - 1.049e-14 * base_days_sq;
        double ecliptic_c2 = 0.019993 - 2.7652e-9 * base_days_from_epoch;
        const double ecliptic_c3 = 0.000290;
        double tst_offset = 4.0 * longitude_deg - 60.0 * timezone_offset_hrs;
        for (int i = 0; i < RESOLUTION_PER_MIN; i += 1) {
            double days_from_epoch = base_days_from_epoch + (i / 60.0 - timezone_offset_hrs) / 24.0;
            double days_from_epoch_sq = days_from_epoch * days_from_epoch;
            double days_from_epoch_cb = days_from_epoch_sq * days_from_epoch;
            double mean_anomaly_deg = 357.52910 + 0.985600282 * days_from_epoch - 1.1686e-13 * days_from_epoch_sq - 9.85e-21 * days_from_epoch_cb;
            mean_anomaly_deg = Math.fmod (mean_anomaly_deg, 360.0);
            if (mean_anomaly_deg < 0) {
                mean_anomaly_deg += 360.0;
            }
            double mean_longitude_deg = 280.46645 + 0.98564736 * days_from_epoch + 2.2727e-13 * days_from_epoch_sq;
            mean_longitude_deg = Math.fmod (mean_longitude_deg, 360.0);
            if (mean_longitude_deg < 0) {
                mean_longitude_deg += 360.0;
            }
            double mean_anomaly_rad = mean_anomaly_deg * DEG2RAD;
            double ecliptic_longitude_deg = mean_longitude_deg
                + ecliptic_c1 * Math.sin (mean_anomaly_rad)
                + ecliptic_c2 * Math.sin (2.0 * mean_anomaly_rad)
                + ecliptic_c3 * Math.sin (3.0 * mean_anomaly_rad);
            ecliptic_longitude_deg = Math.fmod (ecliptic_longitude_deg, 360.0);
            if (ecliptic_longitude_deg < 0) {
                ecliptic_longitude_deg += 360.0;
            }
            double ecliptic_longitude_rad = ecliptic_longitude_deg * DEG2RAD;
            double ecliptic_longitude_sin = Math.sin (ecliptic_longitude_rad);
            double ecliptic_longitude_cos = Math.cos (ecliptic_longitude_rad);
            double declination_sin = (obliquity_sin * ecliptic_longitude_sin).clamp (-1.0, 1.0);
            double declination_cos = Math.sqrt (1.0 - declination_sin * declination_sin);
            double mean_time_hours = mean_longitude_deg / 15.0;
            double right_ascension_hours = Math.atan2 (obliquity_cos * ecliptic_longitude_sin, ecliptic_longitude_cos) * RAD2DEG / 15.0;
            if (right_ascension_hours < 0) {
                right_ascension_hours += 24.0;
            }
            double delta_ra = right_ascension_hours - mean_time_hours;
            if (delta_ra > 12.0) {
                right_ascension_hours -= 24.0;
            } else if (delta_ra < -12.0) {
                right_ascension_hours += 24.0;
            }
            double eqtime_minutes = (mean_time_hours - right_ascension_hours) * 60.0;
            double hour_angle_rad = ((i + eqtime_minutes + tst_offset) / 4.0 - 180.0) * DEG2RAD;
            double elevation_sine = sin_lat * declination_sin + cos_lat * declination_cos * Math.cos (hour_angle_rad);
            sun_angles[i] = Math.asin (elevation_sine.clamp (-1.0, 1.0)) * RAD2DEG;
        }
    }

    /**
     * Updates solar angle data for current settings.
     */
    private void update_plot_data () {
        double latitude_rad = latitude * DEG2RAD;
        // Convert DateTime to Date and get Julian Day Number
        var date = Date ();
        date.set_dmy ((DateDay) selected_date.get_day_of_month (),
                      selected_date.get_month (),
                      (DateYear) selected_date.get_year ());
        var julian_date = (double) date.get_julian ();
        generate_sun_angles (latitude_rad, longitude, timezone_offset_hours, julian_date);

        // Clear click point when data updates
        has_click_point = false;
        click_info_label.label = "Click on chart to view data\n";
    }

    /**
     * Handles mouse click events on the chart.
     *
     * @param n_press Number of button presses.
     * @param x X coordinate of the click.
     * @param y Y coordinate of the click.
     */
    private void on_chart_clicked (int n_press, double x, double y) {
        int width = drawing_area.get_width ();
        int height = drawing_area.get_height ();

        int chart_width = width - MARGIN_LEFT - MARGIN_RIGHT;

        // Check if click is within plot area and single click
        if (x >= MARGIN_LEFT && x <= width - MARGIN_RIGHT && y >= MARGIN_TOP && y <= height - MARGIN_BOTTOM && n_press == 1) {
            // Convert coordinates to time and get corresponding angle
            clicked_time_hours = (x - MARGIN_LEFT) / chart_width * 24.0;
            int time_minutes = (int) (clicked_time_hours * 60) % RESOLUTION_PER_MIN;
            corresponding_angle = sun_angles[time_minutes];
            has_click_point = true;

            // Format time display
            int hours = (int) clicked_time_hours;
            int minutes = (int) ((clicked_time_hours - hours) * 60);

            // Update info label
            string info_text = "Time: %02d:%02d\nSolar Elevation: %.1f°".printf (
                hours, minutes, corresponding_angle
            );

            click_info_label.label = info_text;
            drawing_area.queue_draw ();
        } else {
            // Double click or outside plot area - clear point
            has_click_point = false;
            click_info_label.label = "Click on chart to view data\n";
            drawing_area.queue_draw ();
        }
    }

    /**
     * Draws the solar elevation chart.
     *
     * @param area The drawing area widget.
     * @param cr The Cairo context for drawing.
     * @param width The width of the drawing area.
     * @param height The height of the drawing area.
     */
    private void draw_sun_angle_chart (Gtk.DrawingArea area, Cairo.Context cr, int width, int height) {
        ThemeColors colors = style_manager.dark ? DARK_THEME : LIGHT_THEME;

        // Fill background
        cr.set_source_rgb (colors.bg_r, colors.bg_g, colors.bg_b);
        cr.paint ();

        int chart_width = width - MARGIN_LEFT - MARGIN_RIGHT;
        int chart_height = height - MARGIN_TOP - MARGIN_BOTTOM;

        double horizon_y = MARGIN_TOP + chart_height * 0.5; // 0° is at middle of -90° to +90° range
        
        // Shade area below horizon
        cr.set_source_rgba (colors.shade_r, colors.shade_g, colors.shade_b, colors.shade_a);
        cr.rectangle (MARGIN_LEFT, horizon_y, chart_width, height - MARGIN_BOTTOM - horizon_y);
        cr.fill ();

        // Draw horizontal grid every 15°
        cr.set_source_rgba (colors.grid_r, colors.grid_g, colors.grid_b, colors.grid_a);
        cr.set_line_width (1);
        for (int angle = -90; angle <= 90; angle += 15) {
            double tick_y = MARGIN_TOP + chart_height * (90 - angle) / 180.0;
            cr.move_to (MARGIN_LEFT, tick_y);
            cr.line_to (width - MARGIN_RIGHT, tick_y);
            cr.stroke ();
        }
        // Draw vertical grid every 2 hours
        for (int h = 0; h <= 24; h += 2) {
            double tick_x = MARGIN_LEFT + chart_width * (h / 24.0);
            cr.move_to (tick_x, MARGIN_TOP);
            cr.line_to (tick_x, height - MARGIN_BOTTOM);
            cr.stroke ();
        }

        // Draw axes and horizon
        cr.set_source_rgb (colors.axis_r, colors.axis_g, colors.axis_b);
        cr.set_line_width (2);
        cr.move_to (MARGIN_LEFT, height - MARGIN_BOTTOM);
        cr.line_to (width - MARGIN_RIGHT, height - MARGIN_BOTTOM);
        cr.stroke ();
        cr.move_to (MARGIN_LEFT, MARGIN_TOP);
        cr.line_to (MARGIN_LEFT, height - MARGIN_BOTTOM);
        cr.stroke ();
        // Horizon line
        cr.move_to (MARGIN_LEFT, horizon_y);
        cr.line_to (width - MARGIN_RIGHT, horizon_y);
        cr.stroke ();

        // Draw axis ticks and labels
        cr.set_source_rgb (colors.text_r, colors.text_g, colors.text_b);
        cr.set_line_width (1);
        cr.set_font_size (20);
        for (int angle = -90; angle <= 90; angle += 15) {
            double tick_y = MARGIN_TOP + chart_height * (90 - angle) / 180.0;
            cr.move_to (MARGIN_LEFT - 5, tick_y);
            cr.line_to (MARGIN_LEFT, tick_y);
            cr.stroke ();
            var te = Cairo.TextExtents ();
            var txt = angle.to_string ();
            cr.text_extents (txt, out te);
            cr.move_to (MARGIN_LEFT - 10 - te.width, tick_y + te.height / 2);
            cr.show_text (txt);
        }
        for (int h = 0; h <= 24; h += 2) {
            double tick_x = MARGIN_LEFT + chart_width * (h / 24.0);
            cr.move_to (tick_x, height - MARGIN_BOTTOM);
            cr.line_to (tick_x, height - MARGIN_BOTTOM + 5);
            cr.stroke ();
            var te = Cairo.TextExtents ();
            var txt = h.to_string ();
            cr.text_extents (txt, out te);
            cr.move_to (tick_x - te.width / 2, height - MARGIN_BOTTOM + 25);
            cr.show_text (txt);
        }

        // Plot solar elevation curve
        cr.set_source_rgb (colors.curve_r, colors.curve_g, colors.curve_b);
        cr.set_line_width (2);
        for (int i = 0; i < RESOLUTION_PER_MIN; i += 1) {
            double x = MARGIN_LEFT + chart_width * (i / (double) (RESOLUTION_PER_MIN - 1));
            double y = MARGIN_TOP + chart_height * (90.0 - sun_angles[i]) / 180.0;
            if (i == 0) {
                cr.move_to (x, y);
            } else {
                cr.line_to (x, y);
            }
        }
        cr.stroke ();

        // Draw click point if exists
        if (has_click_point) {
            // Calculate current coordinates from stored time and angle
            double clicked_x = MARGIN_LEFT + chart_width * (clicked_time_hours / 24.0);
            double corresponding_y = MARGIN_TOP + chart_height * (90.0 - corresponding_angle) / 180.0;

            cr.set_source_rgba (colors.point_r, colors.point_g, colors.point_b, 0.8);
            cr.arc (clicked_x, corresponding_y, 5, 0, 2 * Math.PI);
            cr.fill ();
            
            // Draw vertical line to show time
            cr.set_source_rgba (colors.line_r, colors.line_g, colors.line_b, colors.line_a);
            cr.set_line_width (1);
            cr.move_to (clicked_x, MARGIN_TOP);
            cr.line_to (clicked_x, height - MARGIN_BOTTOM);
            cr.stroke ();
            
            // Draw horizontal line to show angle
            cr.move_to (MARGIN_LEFT, corresponding_y);
            cr.line_to (width - MARGIN_RIGHT, corresponding_y);
            cr.stroke ();
        }

        // Draw axis titles
        cr.set_source_rgb (colors.text_r, colors.text_g, colors.text_b);
        cr.set_font_size (20);
        string x_title = "Time (hours)";
        Cairo.TextExtents x_ext;
        cr.text_extents (x_title, out x_ext);
        cr.move_to ((double) width / 2 - x_ext.width / 2, height - MARGIN_BOTTOM + 55);
        cr.show_text (x_title);
        string y_title = "Solar Elevation (°)";
        Cairo.TextExtents y_ext;
        cr.text_extents (y_title, out y_ext);
        cr.save ();
        cr.translate (MARGIN_LEFT - 45, (double)height / 2);
        cr.rotate (-Math.PI / 2);
        cr.move_to (-y_ext.width / 2, 0);
        cr.show_text (y_title);
        cr.restore ();

        // Draw chart captions
        string caption_line1 = "Solar Elevation Angle - Date: %s".printf (selected_date.format ("%Y-%m-%d"));
        string caption_line2 = "Lat: %.2f°, Lon: %.2f°, TZ: UTC%+.2f".printf (latitude, longitude, timezone_offset_hours);
        
        cr.set_font_size (18);
        Cairo.TextExtents cap_ext1, cap_ext2;
        cr.text_extents (caption_line1, out cap_ext1);
        cr.text_extents (caption_line2, out cap_ext2);

        double total_caption_height = cap_ext1.height + cap_ext2.height + 5;

        cr.move_to ((width - cap_ext1.width) / 2, (MARGIN_TOP - total_caption_height) / 2 + cap_ext1.height);
        cr.show_text (caption_line1);
        cr.move_to ((width - cap_ext2.width) / 2, (MARGIN_TOP - total_caption_height) / 2 + cap_ext1.height + 5 + cap_ext2.height);
        cr.show_text (caption_line2);
    }

    /**
     * Handles export button click event.
     *
     * Shows a file save dialog with filters for PNG, SVG, and PDF formats.
     */
    private void on_export_clicked () {
        // Show save dialog with PNG, SVG, PDF filters
        var png_filter = new Gtk.FileFilter ();
        png_filter.name = "PNG Images";
        png_filter.add_mime_type ("image/png");
        
        var svg_filter = new Gtk.FileFilter ();
        svg_filter.name = "SVG Images";
        svg_filter.add_mime_type ("image/svg+xml");

        var pdf_filter = new Gtk.FileFilter ();
        pdf_filter.name = "PDF Documents";
        pdf_filter.add_mime_type ("application/pdf");

        var filter_list = new ListStore (typeof (Gtk.FileFilter));
        filter_list.append (png_filter);
        filter_list.append (svg_filter);
        filter_list.append (pdf_filter);

        var file_dialog = new Gtk.FileDialog () {
            modal = true,
            initial_name = "solar_elevation_chart.png",
            filters = filter_list,
        };

        file_dialog.save.begin (window, null, (obj, res) => {
            try {
                var file = file_dialog.save.end (res);
                if (file != null) {
                    export_chart (file);
                }
            } catch (Error e) {
                // Dismissed by user, so do not show alert dialog
                message ("Image file has not been saved: %s", e.message);
            }
        });
    }

    /**
     * Exports the current chart to a file.
     *
     * Supports PNG, SVG, and PDF formats based on file extension.
     * Defaults to PNG if extension is not recognized.
     *
     * @param file The file to export the chart to.
     */
    private void export_chart (File file) {
        int width = drawing_area.get_width ();
        int height = drawing_area.get_height ();

        if (width <= 0 || height <= 0) {
            width = 800;
            height = 600;
        }

        string filepath = file.get_path ();
        string? extension = null;
        var last_dot = filepath.last_index_of_char ('.');
        if (last_dot != -1) {
            extension = filepath[last_dot:].down ();
        }

        if (extension == ".svg") {
            Cairo.SvgSurface surface = new Cairo.SvgSurface (filepath, width, height);
            Cairo.Context cr = new Cairo.Context (surface);
            draw_sun_angle_chart (drawing_area, cr, width, height);
        } else if (extension == ".pdf") {
            Cairo.PdfSurface surface = new Cairo.PdfSurface (filepath, width, height);
            Cairo.Context cr = new Cairo.Context (surface);
            draw_sun_angle_chart (drawing_area, cr, width, height);
        } else {
            Cairo.ImageSurface surface = new Cairo.ImageSurface (Cairo.Format.RGB24, width, height);
            Cairo.Context cr = new Cairo.Context (surface);
            draw_sun_angle_chart (drawing_area, cr, width, height);
            surface.write_to_png (filepath);
        }
    }

    /**
     * Handles CSV export button click event.
     *
     * Shows a file save dialog for CSV format.
     */
    private void on_export_csv_clicked () {
        var csv_filter = new Gtk.FileFilter ();
        csv_filter.name = "CSV Files";
        csv_filter.add_mime_type ("text/csv");

        var filter_list = new ListStore (typeof (Gtk.FileFilter));
        filter_list.append (csv_filter);

        var file_dialog = new Gtk.FileDialog () {
            modal = true,
            initial_name = "solar_elevation_data.csv",
            filters = filter_list,
        };

        file_dialog.save.begin (window, null, (obj, res) => {
            try {
                var file = file_dialog.save.end (res);
                if (file != null) {
                    export_csv_data (file);
                }
            } catch (Error e) {
                // Dismissed by user, so do not show alert dialog
                message ("CSV file has not been saved: %s", e.message);
            }
        });
    }

    /**
     * Exports the solar elevation data to a CSV file.
     *
     * @param file The file to export the data to.
     */
    private void export_csv_data (File file) {
        try {
            var stream = file.replace (null, false, FileCreateFlags.REPLACE_DESTINATION);
            var data_stream = new DataOutputStream (stream);

            // Write CSV metadata as comments
            data_stream.put_string ("# Solar Elevation Data\n");
            data_stream.put_string ("# Date: %s\n".printf (selected_date.format ("%Y-%m-%d")));
            data_stream.put_string ("# Latitude: %.2f degrees\n".printf (latitude));
            data_stream.put_string ("# Longitude: %.2f degrees\n".printf (longitude));
            data_stream.put_string ("# Timezone: UTC%+.2f\n".printf (timezone_offset_hours));
            data_stream.put_string ("#\n");


            // Write CSV header
            data_stream.put_string ("Time,Solar Elevation (degrees)\n");

            // Write data points
            for (int i = 0; i < RESOLUTION_PER_MIN; i += 1) {
                int hours = i / 60;
                int minutes = i % 60;
                data_stream.put_string (
                    "%02d:%02d,%.3f\n".printf (hours, minutes, sun_angles[i])
                );
            }

            data_stream.close ();
        } catch (Error e) {
            show_error_dialog ("CSV export failed", e.message);
        }
    }

    /**
     * Application entry point.
     *
     * Creates and runs the SolarAngleApp instance.
     *
     * @param args Command line arguments.
     * @return Exit code.
     */
    public static int main (string[] args) {
        var app = new SolarAngleApp ();
        return app.run (args);
    }
}
```

## 番外

除了[太阳高度角计算器](https://github.com/wszqkzqk/FunValaGtkExamples/blob/master/solarangleadw.vala)外，笔者还使用几乎相同的设计写了一个[白昼时长及日出日落时间计算器](https://github.com/wszqkzqk/FunValaGtkExamples/blob/master/daylengthadw.vala)。该程序的架构设计与前文接好的基本相同，具体算法实现同样参见笔者的另一篇博客：[Vala 数值计算实践：高精度太阳位置算法](https://wszqkzqk.github.io/2025/10/08/GTK-Vala-Tutorial-Advanced-Solar-Calculation/)。

可以通过类似的方式下载并编译该程序：

```bash
wget https://raw.githubusercontent.com/wszqkzqk/FunValaGtkExamples/master/daylengthadw.vala
valac --pkg=gtk4 --pkg=libadwaita-1 --pkg=json-glib-1.0 -X -lm -X -O2 -X -pipe daylengthadw.vala
```

以下是效果展示：

|[![#~/img/GTK-examples/day-length-pku-light.webp](/img/GTK-examples/day-length-pku-light.webp)](/img/GTK-examples/day-length-pku-light.webp)|[![#~/img/GTK-examples/day-length-pku-dark.webp](/img/GTK-examples/day-length-pku-dark.webp)](/img/GTK-examples/day-length-pku-dark.webp)|
|:----:|:----:|
|白昼时长计算器（浅色模式）|白昼时长计算器（深色模式）|
