---
layout:     post
title:      GTK4/Vala 教程：使用 LibAdwaita 构建现代桌面应用
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

许多入门教程止步于“Hello, World!”或简单控件演示，这样一方面各部分间缺乏组织逻辑，不便进行复杂演示，另一方面也难以指导你如何开发一个真正实用、现代、体验良好的桌面应用。本教程将以“太阳高度角计算器”这一完整项目为例，带你从需求分析、界面设计、核心算法、异步网络、数据导出等多个维度，系统梳理 Vala/GTK4/LibAdwaita 的开发流程。

本教程适合有一定编程基础、希望深入学习 Vala 语言和 GTK4 框架、并渴望开发高质量应用的开发者。

本教程将以“太阳高度角计算器”的完整应用为例，深入剖析其从概念设计到功能实现的每一个环节。这个应用不仅能进行科学计算，还拥有一个使用 LibAdwaita 构建的、支持深色模式的现代化用户界面，并具备异步网络请求、JSON 解析、自定义绘图和文件导出等高级功能。

| [![#~/img/GTK-examples/pku-light-solar-angle-250807.webp](/img/GTK-examples/pku-light-solar-angle-250807.webp)](/img/GTK-examples/pku-light-solar-angle-250807.webp) | [![#~/img/GTK-examples/pku-dark-solar-angle-250807.webp](/img/GTK-examples/pku-dark-solar-angle-250807.webp)](/img/GTK-examples/pku-dark-solar-angle-250807.webp)
| :--: | :--: |
| 太阳高度角计算器（浅色模式）| 太阳高度角计算器（深色模式）|

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

### UI/UX 设计哲学

为了让应用看起来现代化且用户友好，我们选择使用 **LibAdwaita**。它是 GTK4 的一个辅助库，旨在帮助开发者构建遵循 [GNOME 人机界面指南 (HIG)](https://developer.gnome.org/hig/) 的应用。

我们的界面布局采用常见的**双栏结构**：
* **左侧面板**：作为控制中心，包含所有输入控件（经纬度、时区、日期选择器）和操作按钮（导出、自动定位）。我们使用 `Adw.PreferencesGroup` 来组织这些设置，使其清晰明了。
* **右侧主区域**：用于展示核心内容——太阳高度角图表。这部分将使用 `Gtk.DrawingArea` 进行完全的自定义绘制。

这种设计不仅结构清晰，也为未来可能的响应式布局（例如在小屏幕上将左侧面板收起到侧边栏）打下了基础。

现代桌面应用越来越重视**主题一致性**和**深色模式支持**。LibAdwaita 天生支持系统主题切换，能够自动适配浅色/深色模式，为用户带来舒适的视觉体验。在本项目中，我们不仅让应用自动响应系统主题，还在标题栏右上角提供了**深色模式切换按钮**，用户可以随时手动切换浅色/深色界面。

主题切换的实现思路如下：

* 通过 `Adw.StyleManager` 检测当前系统主题（`dark` 属性）。
* 在 `HeaderBar` 添加一个 `Gtk.ToggleButton`，点击时切换 `color_scheme` 属性，实现强制浅色或深色。
* 所有自定义绘图（如 Cairo 绘制图表）都根据当前主题动态选择配色方案，确保视觉风格统一。
* 主题切换时，主动触发重绘，保证界面即时更新。

这种做法不仅让应用外观与系统保持一致，也为自定义控件和绘图区域带来了良好的主题适配体验。

## 第二部分：项目设置与编译

Vala 代码需要被编译成 C 代码，然后再编译成可执行文件。Vala 编译器 `valac` 会为我们处理好这一切。

读者不妨先**编译并试用**该应用，再继续阅读。这样可以更好地理解每个功能的意义。

### 依赖项

完成本教程涉及的代码编译需要确保系统已安装 Vala、GTK4、LibAdwaita，以及用于 JSON 解析的 `json-glib` 库，以及 C 编译工具（如 `gcc`）。笔者在此列举了在 Arch Linux 和 Windows MSYS2 环境下的安装命令：

* Arch Linux：
  ```bash
  sudo pacman -S --needed vala gtk4 libadwaita json-glib
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
* `-X -O2 -X -march=native -X -pipe`: 这些是传递给 C 编译器的参数。在脚本中应用编译优化存在一些独特考量：`-O2` 提供了良好的优化级别，既明显提升运行时性能，又避免激进优化可能导致的编译时间显著延长 —— 这点尤为重要，**因为每次执行脚本都会重新编译**，编译耗时直接影响用户体验；`-march=native` 利用当前 CPU 的全部指令集特性进行优化。由于编译产物**仅在当前机器上运行且不被保留**，不存在跨设备兼容性风险，这有望带来本地性能提升。

### 编译与运行

读者可以将[教程最后的完整代码](#附：完整源代码)保存为 `solarangle.vala`。你可以直接运行这个脚本文件（如果它有执行权限 `chmod +x solarangle.vala`），或者使用以下命令手动编译：

```bash
valac --pkg=gtk4 --pkg=libadwaita-1 --pkg=json-glib-1.0 -X -lm -X -O2 -X -march=native -X -pipe solarangle.vala
```

需要注意的是，与“执行”用的 `vala` 不同，编译需要使用 `valac` 命令。

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

我们使用 `Adw.ToolbarView` 作为顶级布局容器。它天生支持顶部栏（`HeaderBar`）和主内容区域，是构建现代 LibAdwaita 应用的理想选择。

```vala
var header_bar = new Adw.HeaderBar ();
var toolbar_view = new Adw.ToolbarView ();
toolbar_view.add_top_bar (header_bar);

// ... main content ...

window.content = toolbar_view;
```

### 左侧输入面板

左侧面板是一个垂直的 `Gtk.Box`，里面包含了几个 `Adw.PreferencesGroup`，用于对设置项进行逻辑分组。这些控件负责收集用户输入，并提供操作入口。

#### 处理加载状态：Gtk.Stack 与 Gtk.Spinner

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

`generate_sun_angles` 函数是应用计算的核心函数。它基于 [NOAA 赤纬公式](https://gml.noaa.gov/grad/solcalc/solareqns.PDF)来计算太阳高度角。这个公式保留了较多了傅里叶级数项，计算精度较高。

- **日行轨迹组分与年角计算**：
  - `fractional_day_component = day_of_year - 1 + ((double) i) / RESOLUTION_PER_MIN`：计算一年中的具体时刻（以天为单位，包含小数部分）。
  - `gamma_rad = (2.0 * Math.PI / days_in_year) * fractional_day_component`：计算年角（弧度），表示地球在轨道上的精确位置。
- **太阳赤纬 `δ` 计算**（使用 NOAA 傅里叶级数近似公式）：
  将上述 `gamma_rad` 代入经验公式：

  $$
  \begin{aligned}
  \delta &= 0.006918 - 0.399912 \cos(\gamma)
          + 0.070257 \sin(\gamma) \\
      &\quad - 0.006758 \cos(2 \times \gamma)
          + 0.000907 \sin(2 \times \gamma) \\
      &\quad - 0.002697 \cos(3 \times \gamma)
          + 0.001480 \sin(3 \times \gamma)
  \end{aligned}
  $$

- **均时差 (Equation of Time, EoT) 计算**：
  `eqtime_minutes = 229.18 * (0.000075 + 0.001868 * cos(gamma_rad) ...)`：计算均时差（分钟），真太阳时（True Solar Time，基于太阳真实位置）与均太阳时（Mean Solar Time，假设太阳匀速运行）之差，主要由地球轨道偏心率和黄赤交角引起，反映钟表时间和日晷时间的偏差。将本地平时（分钟 `i`）修正为真太阳时（分钟），以保证后续时角、太阳高度角计算的天文精度。
    - 真太阳时：基于太阳在天空中的实际位置计算。
    - 平太阳时：虚构一个匀速运动的“平太阳”作为参考，将一天固定为24小时（86,400秒），消除季节性波动。这是日常钟表时间的基准。
    - 真太阳日的长度（太阳连续两次过中天的时间间隔）会因地球轨道离心率和黄赤交角的影响而变化，可达±30秒。
    - 这些微小日变化会逐日累积，导致真太阳时与平太阳时的偏差可达 **-14分15秒至+16分25秒** （公元2000年），因此有必要均时差修正。
- **真太阳时 (True Solar Time, TST) 计算**：  
  `tst_minutes = i + eqtime_minutes + 4.0 * longitude_deg - 60.0 * timezone_offset_hrs`  
  将本地钟表时间（分钟 `i`）先加上均时差修正（`eqtime_minutes`），再加上因经度（每向东 1 度 +4 分钟）带来的分钟偏移，最后减去因时区带来的分钟差，得到真太阳时（分钟）。  
  - `longitude_deg`：经度（度），正值为东经、负值为西经；  
  - `timezone_offset_hrs`：时区偏移（小时），正值为东区、负值为西区；  
  - `4.0 * longitude_deg`：将经度转换为分钟偏移；  
  - `60.0 * timezone_offset_hrs`：将时区小时数转换为分钟偏移；
  - **时角 (Hour Angle, HA) 计算**：
  `ha_deg = (tst_minutes / 4.0) - 180.0`：根据真太阳时计算时角（度），表示太阳相对于本地子午线的角距离。
- **太阳高度角计算**：
  使用球面三角公式，结合纬度 `latitude_rad`、太阳赤纬 `decl_rad` 和时角 `ha_rad` 计算太阳天顶角 `phi_rad`，进而得到太阳高度角 `(90° - phi_rad)`。
  - 结果填充到 `sun_angles` 数组（单位：°），每分钟一个采样点。

### 自定义绘图与 Cairo

`draw_sun_angle_chart` 函数是应用的绘制核心。它接收一个 `Cairo.Context` 对象（通常简写为 `cr`），你可以把它想象成一支画笔，拥有颜色、粗细、字体等属性。

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

* **Vala 的 `async` / `yield`**
  Vala 借鉴了 C# 的 `async/await` 语法，使得异步编程像写同步代码一样直观。
  1. 我们将网络请求逻辑放在一个 `async` 方法 `get_location_async` 中。
  2. 当遇到耗时操作时（如 `file.read_async`），我们使用 `yield` 关键字。这会“暂停”当前方法的执行，将控制权交还给主事件循环（让 UI 保持响应），当 I/O 操作完成后，方法会自动从 `yield` 的地方继续执行。
  ```vala
  private async void get_location_async () throws IOError {
      var file = File.new_for_uri ("https://ipapi.co/json/");
      // 'yield' 在这里暂停，等待数据下载，但 UI 不会卡住
      var stream = yield file.read_async (Priority.DEFAULT, null);
      // 下载完成后，代码从这里继续
      // ...
  }
  ```

* **JSON-GLib 解析**
  JSON-GLib 提供了一套健壮的 API 来遍历和提取 JSON 结构中的数据，并能很好地处理潜在的错误。获取到 JSON 字符串后，我们使用 `Json.Parser` 来解析它。
  ```vala
  var parser = new Json.Parser ();
  parser.load_from_data (json_text);
  var root_object = parser.get_root ().get_object ();
  
  // 安全地获取数据
  if (root_object.has_member ("latitude")) {
      parsed_lat = root_object.get_double_member ("latitude");
  }
  ```

* **UI 更新**
  所有 GTK 控件的更新都必须在主线程中进行。由于异步方法的回调可能在其他线程中执行，我们使用 `Idle.add()` 来安全地将 UI 更新操作（如设置 `SpinRow` 的值）调度回主线程执行。

### 错误处理的用户交互：`Adw.AlertDialog`

在涉及网络请求等可能失败的操作时，提供明确的错误反馈至关重要。我们使用 `Adw.AlertDialog` 来创建符合 GNOME HIG 规范的现代化错误对话框：

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
```

`Adw.AlertDialog` 自动适应深浅色模式，符合 GNOME 人机界面指南。而且无需复杂布局，标题+描述+交互按钮三步完成创建，十分方便。

### 文件导出

* **`Gtk.FileDialog`**
  为了提供现代化的文件保存体验，我们使用 `Gtk.FileDialog`。它取代了旧的 `Gtk.FileChooserDialog`，通过异步回调函数处理用户的选择。
  ```vala
  var file_dialog = new Gtk.FileDialog () { /* ... */ };
  file_dialog.save.begin (window, null, (obj, res) => {
      var file = file_dialog.save.end (res);
      if (file != null) {
          export_chart (file);
      }
  });
  ```
* **导出为图片**:
  Cairo 的一个强大之处在于其“设备无关性”。我们的 `draw_sun_angle_chart` 函数不仅可以向屏幕绘图，也可以向不同的**表面 (Surface)** 绘图。通过创建 `Cairo.SvgSurface`、`Cairo.PdfSurface` 或 `Cairo.ImageSurface`，我们可以将完全相同的绘图代码重定向到文件，从而轻松实现 SVG、PDF 和 PNG 格式的导出。
* **导出为 CSV**:
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

## 附：完整源代码

```vala
#!/usr/bin/env -S vala --pkg=gtk4 --pkg=libadwaita-1 --pkg=json-glib-1.0 -X -lm -X -O2 -X -march=native -X -pipe
/* SPDX-License-Identifier: LGPL-2.1-or-later */

/**
 * Solar Angle Calculator Application.
 *
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
    // Constants for margins in the drawing area
    private const int MARGIN_LEFT = 70;
    private const int MARGIN_RIGHT = 20;
    private const int MARGIN_TOP = 50;
    private const int MARGIN_BOTTOM = 70;

    private Adw.ApplicationWindow window;
    private Gtk.DrawingArea drawing_area;
    private Gtk.Label click_info_label;
    private DateTime selected_date;
    private double sun_angles[RESOLUTION_PER_MIN];
    private double latitude = 0.0;
    private double longitude = 0.0;
    private double timezone_offset_hours = 0.0;
    private double clicked_time_hours = 0.0;
    private double corresponding_angle = 0.0;
    private bool has_click_point = false;

    // Location detection widgets
    private Gtk.Stack location_stack;
    private Gtk.Spinner location_spinner;
    private Gtk.Button location_button;
    private Adw.SpinRow latitude_row;
    private Adw.SpinRow longitude_row;
    private Adw.SpinRow timezone_row;

    // Color theme struct for chart drawing
    private struct ThemeColors {
        // Background colors
        double bg_r; double bg_g; double bg_b;
        // Grid colors with alpha
        double grid_r; double grid_g; double grid_b; double grid_a;
        // Axis colors
        double axis_r; double axis_g; double axis_b;
        // Text colors
        double text_r; double text_g; double text_b;
        // Curve colors
        double curve_r; double curve_g; double curve_b;
        // Shaded area colors with alpha
        double shade_r; double shade_g; double shade_b; double shade_a;
        // Click point colors
        double point_r; double point_g; double point_b;
        // Guide line colors with alpha
        double line_r; double line_g; double line_b; double line_a;
    }

    // Light theme color constants
    private ThemeColors LIGHT_THEME = {
        bg_r: 1.0, bg_g: 1.0, bg_b: 1.0,                    // White background
        grid_r: 0.5, grid_g: 0.5, grid_b: 0.5, grid_a: 0.5, // Gray grid
        axis_r: 0.0, axis_g: 0.0, axis_b: 0.0,              // Black axes
        text_r: 0.0, text_g: 0.0, text_b: 0.0,              // Black text
        curve_r: 1.0, curve_g: 0.0, curve_b: 0.0,           // Red curve
        shade_r: 0.7, shade_g: 0.7, shade_b: 0.7, shade_a: 0.3, // Light gray shade
        point_r: 0.0, point_g: 0.0, point_b: 1.0,           // Blue point
        line_r: 0.0, line_g: 0.0, line_b: 1.0, line_a: 0.5  // Blue guide lines
    };

    // Dark theme color constants
    private ThemeColors DARK_THEME = {
        bg_r: 0.0, bg_g: 0.0, bg_b: 0.0,                    // Black background
        grid_r: 0.5, grid_g: 0.5, grid_b: 0.5, grid_a: 0.5, // Light gray grid
        axis_r: 1.0, axis_g: 1.0, axis_b: 1.0,              // White axes
        text_r: 1.0, text_g: 1.0, text_b: 1.0,              // White text
        curve_r: 1.0, curve_g: 0.0, curve_b: 0.0,           // Bright red curve
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
            if (dark_mode_button.active) {
                style_manager.color_scheme = Adw.ColorScheme.FORCE_DARK;
            } else {
                style_manager.color_scheme = Adw.ColorScheme.FORCE_LIGHT;
            }
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
     * Asynchronously gets current location using IP geolocation service.
     */
    private async void get_location_async () throws IOError {
        // Use ipapi.co which provides free IP geolocation
        var file = File.new_for_uri ("https://ipapi.co/json/");

        try {
            var stream = yield file.read_async (Priority.DEFAULT, null);
            var data_stream = new DataInputStream (stream);

            // Read the entire response
            var response_text = new StringBuilder ();
            string? line = null;

            while ((line = yield data_stream.read_line_async (Priority.DEFAULT, null)) != null) {
                response_text.append (line);
            }

            stream.close ();
            data_stream.close ();

            if (response_text.len == 0) {
                throw new IOError.FAILED ("Empty response from location service");
            }

            parse_location_response (response_text.str);
            
        } catch (Error e) {
            throw new IOError.FAILED ("Failed to get location: %s".printf (e.message));
        }
    }

    /**
     * Parses the JSON response from the location service.
     * 
     * @param json_text The JSON response as string.
     */
    private void parse_location_response (string json_text) throws IOError {
        try {
            var parser = new Json.Parser ();
            parser.load_from_data (json_text);

            var root_object = parser.get_root ().get_object ();

            // Check if the response contains an error
            if (root_object.has_member ("error") && root_object.get_boolean_member ("error")) {
                var reason = root_object.has_member ("reason") ? 
                    root_object.get_string_member ("reason") : "Unknown error";
                throw new IOError.FAILED ("Location service error: %s".printf (reason));
            }

            // Extract location data
            double parsed_lat = 0.0;
            double parsed_lon = 0.0;

            if (root_object.has_member ("latitude")) {
                parsed_lat = root_object.get_double_member ("latitude");
            } else {
                throw new IOError.FAILED ("No latitude found in response");
            }

            if (root_object.has_member ("longitude")) {
                parsed_lon = root_object.get_double_member ("longitude");
            } else {
                throw new IOError.FAILED ("No longitude found in response");
            }

            var timezone = new TimeZone.local ();
            var time_interval = timezone.find_interval (GLib.TimeType.UNIVERSAL, selected_date.to_unix ());
            timezone_offset_hours = timezone.get_offset (time_interval) / 3600.0;

            // Update UI in main thread
            Idle.add (() => {
                latitude = parsed_lat;
                longitude = parsed_lon;

                // Update the spin rows
                latitude_row.value = latitude;
                longitude_row.value = longitude;
                timezone_row.value = timezone_offset_hours;

                // Update plot
                update_plot_data ();
                drawing_area.queue_draw ();

                return false;
            });

        } catch (Error e) {
            throw new IOError.FAILED ("Failed to parse location data: %s".printf (e.message));
        }
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
     *
     * @param latitude_rad Latitude in radians.
     * @param day_of_year Day of the year (1-365/366).
     * @param year The year.
     * @param longitude_deg Longitude in degrees.
     * @param timezone_offset_hrs Timezone offset from UTC in hours.
     */
    private void generate_sun_angles (double latitude_rad, int day_of_year, int year, double longitude_deg, double timezone_offset_hrs) {
        double sin_lat = Math.sin (latitude_rad);
        double cos_lat = Math.cos (latitude_rad);

        double days_in_year = ((year % 4 == 0) && ((year % 100 != 0) || (year % 400 == 0))) ? 366.0 : 365.0;

        for (int i = 0; i < RESOLUTION_PER_MIN; i += 1) {
            // fractional_day_component: day of year plus fraction of the day
            double fractional_day_component = day_of_year - 1 + ((double) i) / RESOLUTION_PER_MIN;
            // gamma: fractional year angle in radians
            double gamma_rad = (2.0 * Math.PI / days_in_year) * fractional_day_component;

            // Solar declination delta (rad) via Fourier series approximation
            double decl_rad = 0.006918
                - 0.399912 * Math.cos (gamma_rad)
                + 0.070257 * Math.sin (gamma_rad)
                - 0.006758 * Math.cos (2.0 * gamma_rad)
                + 0.000907 * Math.sin (2.0 * gamma_rad)
                - 0.002697 * Math.cos (3.0 * gamma_rad)
                + 0.001480 * Math.sin (3.0 * gamma_rad);

            // Equation of Time (EoT) in minutes
            double eqtime_minutes = 229.18 * (0.000075
                + 0.001868 * Math.cos (gamma_rad)
                - 0.032077 * Math.sin (gamma_rad)
                - 0.014615 * Math.cos (2.0 * gamma_rad)
                - 0.040849 * Math.sin (2.0 * gamma_rad));

            // True Solar Time (TST) in minutes, correcting local clock by EoT and longitude
            double tst_minutes = i + eqtime_minutes + 4.0 * longitude_deg - 60.0 * timezone_offset_hrs;

            // Hour angle H (°) relative to solar noon
            double ha_deg = tst_minutes / 4.0 - 180.0;
            double ha_rad = ha_deg * DEG2RAD;

            // cos(phi): cosine of zenith angle via spherical trig
            double cos_phi = sin_lat * Math.sin (decl_rad) + cos_lat * Math.cos (decl_rad) * Math.cos (ha_rad);
            // clamp to valid range
            if (cos_phi > 1.0) cos_phi = 1.0;
            if (cos_phi < -1.0) cos_phi = -1.0;
            // Zenith angle phi (rad)
            double phi_rad = Math.acos (cos_phi);

            // Solar elevation alpha = 90° - phi, convert to degrees
            double solar_elevation_rad = Math.PI / 2.0 - phi_rad;
            sun_angles[i] = solar_elevation_rad * RAD2DEG;
        }
    }

    /**
     * Updates solar angle data for current settings.
     */
    private void update_plot_data () {
        int day_of_year = selected_date.get_day_of_year ();
        double latitude_rad = latitude * DEG2RAD;
        int year = selected_date.get_year ();
        generate_sun_angles (latitude_rad, day_of_year, year, longitude, timezone_offset_hours);
        
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
