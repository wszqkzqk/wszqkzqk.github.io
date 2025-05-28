---
layout:     post
title:      GTK/Vala开发基础教程 2
subtitle:   使用GTK/Vala构建简单应用
date:       2025-02-05
author:     wszqkzqk
header-img: img/GTK-logo.webp
catalog:    true
tags:       开源软件 GTK Vala
---

本文采用[**CC-BY-SA-4.0**](https://creativecommons.org/licenses/by-sa/4.0/)协议发布，但本文代码采用[**LGPL v2.1+**](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html)协议公开

# 前言

* 在之前的[GTK/Vala开发基础教程](https://wszqkzqk.github.io/2023/01/19/GTK-Vala-Tutorial/)发布后🕊了2年终于写了一篇后续。🥲🥲🥲

本文假设读者已经阅读了笔者的上一篇[GTK/Vala开发基础教程](https://wszqkzqk.github.io/2023/01/19/GTK-Vala-Tutorial/)，已经对GTK/Vala的基本概念有所了解。本文将通过简单的例子，展示如何使用GTK4和Vala构建一个简单的应用程序。本文的例子均与太阳☀️☀️☀️有关。

# 构建应用：白昼时长计算与绘制工具

笔者在这里用一个有趣的例子来展示如何构建一个简单的应用程序。该程序用到了GTK4的许多组件（有意识地在用GTK4下新增的，推荐的，或者行为发生改变的组件），以及Cairo的绘图功能。

这个应用程序可用于计算在不同纬度下，全年的每一天的白昼时长。为了方便，程序做了这些简化：

* 不考虑大气折射
* 不考虑进动（岁差）
* 假设地球公转与自转的角速度恒定且完全与格里高利历对齐
* 假设自转倾角恒定为23.44°

## 运行效果

|||
|:----:|:----:|
|[![#~/img/GTK-examples/beijing-day-length.webp](/img/GTK-examples/beijing-day-length.webp)](/img/GTK-examples/beijing-day-length.webp)|[![#~/img/GTK-examples/chongqing-day-length.webp](/img/GTK-examples/chongqing-day-length.webp)](/img/GTK-examples/chongqing-day-length.webp)|
|北京|重庆|
|[![#~/img/GTK-examples/berlin-day-length.webp](/img/GTK-examples/berlin-day-length.webp)](/img/GTK-examples/berlin-day-length.webp)|[![#~/img/GTK-examples/sydney-day-length.webp](/img/GTK-examples/sydney-day-length.webp)](/img/GTK-examples/sydney-day-length.webp)|
|柏林|悉尼|
|[![#~/img/GTK-examples/singapore-day-length.webp](/img/GTK-examples/singapore-day-length.webp)](/img/GTK-examples/singapore-day-length.webp)|[![#~/img/GTK-examples/murmansk-day-length.webp](/img/GTK-examples/murmansk-day-length.webp)](/img/GTK-examples/murmansk-day-length.webp)|
|新加坡|摩尔曼斯克|
|[![#~/img/GTK-examples/n-polar-day-length.webp](/img/GTK-examples/n-polar-day-length.webp)](/img/GTK-examples/n-polar-day-length.webp)|[![#~/img/GTK-examples/s-polar-day-length.webp](/img/GTK-examples/s-polar-day-length.webp)](/img/GTK-examples/s-polar-day-length.webp)|
|北极点|南极点|

## 程序架构

### 辅助函数
- `days_in_year (int year)`  
  判断给定年份是否为闰年，返回一年中的天数。  
  判断规则：能被 400 整除，或者能被 4 整除但不能被 100 整除的为闰年。

- `solar_declination (int n)`  
  利用近似公式计算第 n 天的太阳赤纬角（弧度），公式为：  
  $\delta = 23.44 \times \frac{\pi}{180} \times \sin\left(\frac{2\pi}{365} \times (n - 81)\right)$。
  其中81为春分日的天数偏移量（1月1日为第1天）。一般春分日的偏移量其实是79，但是由于地球的轨道是椭圆形的，春分-秋分时长与秋分-春分时长并不完全相等，完全对齐春分日的偏移量会导致秋季误差较大，因此这里使用了能够相对平衡春秋两季的偏移量81。

- `compute_day_length (double latitude_rad, int n)`   
  根据输入的纬度（弧度）和天数，计算当天的日照时长（单位：小时）。  
  使用公式 $X = -\tan(\phi)\tan(\delta)$ 计算 X 值，其中 $\phi$ 为纬度（弧度）、$\delta$ 为太阳赤纬角（弧度）。  
  此处 X 表示太阳在地平面上升降时刻对应的余弦值，即 $\cos(\omega_0)$，通过 X 的取值判断：  
  - 若 $X$ 在 $[-1, 1]$ 内，则通过 $\omega_0 = \arccos(X)$ 计算出太阳的小时角，再利用该角度计算日照时长；  
  - 若 $X < -1$，则表示处于极昼状态（日照 24 小时）；  
  - 若 $X > 1$，则表示处于极夜状态（日照 0 小时）。

- `generate_day_lengths (double latitude_rad, int year)`  
  遍历一年中的每一天，调用 `compute_day_length` 计算各天日照时长，返回包含所有白昼时长数据的数组。

### 主窗口类 `DayLengthWindow`
此类继承自 `Gtk.ApplicationWindow`，用于构建图形界面和显示绘图内容：
- **界面组件**  
  - 使用 `Gtk.Box` 布局，包含输入区域和绘图区域。
  - `Gtk.Entry` 控件允许用户输入纬度和年份，并通过 `Gtk.Button` 触发绘图更新。
- **事件处理**  
  - “Plot” 按钮点击时调用 `update_plot_data ()` 读取输入并更新数据，再通过 `drawing_area.queue_draw ()` 重绘图表。
  - “Export” 按钮点击时弹出文件保存对话框，用户选择保存路径后调用 `export_plot ()` 导出图表为 PNG, SVG 或 PDF 文件。
    - 通过 `Gtk.FileDialog` 选择保存路径，设置默认文件名和过滤器（仅显示 PNG, SVG 和 PDF 文件）。
    - 通过 `Cairo.ImageSurface`、`Cairo.SvgSurface` 或 `Cairo.PdfSurface` 创建绘图表面，再调用 `draw_plot ()` 绘制图表。
- **绘图操作**  
  - `drawing_area` 使用 `Gtk.DrawingArea`，并注册了绘图回调 `draw_plot ()`。  
  - `draw_plot ()` 中利用 `Cairo` 库完成以下工作：  
    1. 清空背景并设置为白色。  
    2. 定义绘图区域的边距、X/Y 轴范围。  
    3. 绘制横向和纵向的网格线、刻度及文字标签（包括月份和小时刻度）。  
    4. 绘制坐标轴，其中 X/Y 轴均加粗显示。  
    5. 利用计算得到的 `day_lengths` 数据绘制红色的日照时长曲线。  
    6. 额外绘制坐标轴标题，其中 Y 轴文字通过旋转操作实现垂直显示。

### 应用管理类 `DayLengthApp` 及 `main` 函数
- **`DayLengthApp` 类**  
  继承自 `Gtk.Application`，主要用于管理应用的生命周期和窗口创建。
- **`activate ()` 回调函数**  
  当应用激活时，创建 `DayLengthWindow` 并显示窗口。
- **`main ()` 函数**  
  程序的入口，创建 `DayLengthApp` 对象并启动事件循环，处理命令行参数。

## 实现代码

实现这个应用程序的代码如下：

```vala
#!/usr/bin/env -S vala --pkg=gtk4 -X -lm -X -pipe -X -O2 -X -march=native

// Helper functions to compute day-of-year, solar declination and day length

/**
 * Returns the number of days in a given year.
 *
 * @param year The year to calculate the number of days.
 * @return Total number of days in the year.
 */
private inline int days_in_year (int year) {
    // Leap year: divisible by 400 or divisible by 4 but not by 100.
    if ((year % 4 == 0) && ((year % 100 != 0) || (year % 400 == 0))) {
        return 366;
    }
    return 365;
}

/**
 * Computes solar declination in radians using an approximate formula.
 *
 * Formula: δ (rad) = (23.44 * π/180) * sin(2π/365 * (n - 81))
 *
 * @param n The day number in the year.
 * @return Solar declination in radians.
 */
private inline double solar_declination (int n) {
    return (23.44 * Math.PI / 180.0) * Math.sin (2 * Math.PI / 365.0 * (n - 81));
}

/**
 * Calculates the day length (in hours) for a given latitude (in radians) and day number.
 *
 * Using formula: T = (24/π) * arccos( -tan(φ) * tan(δ) )
 *
 * φ: observer's latitude, δ: solar declination
 *
 * When |tan φ * tan δ| > 1, returns polar day (24 hours) or polar night (0 hours)
 *
 * @param latitude_rad Latitude in radians.
 * @param n The day number in the year.
 * @return Day length in hours.
 */
private inline double compute_day_length (double latitude_rad, int n) {
    double phi = latitude_rad;
    double delta = solar_declination (n);
    double X = -Math.tan (phi) * Math.tan (delta);
    if (X < -1) {
        return 24.0; // Polar day
    } else if (X > 1) {
        return 0.0;  // Polar night
    } else {
        // 'omega0' is the half-angle (in radians) corresponding to the time from sunrise to solar noon.
        // Since 2π radians represent 24 hours, 1 radian equals 24/(2π) hours.
        // Multiplying omega0 by (24/Math.PI) converts this angle to the total day length in hours.
        double omega0 = Math.acos (X); // computed in radians
        double T = (24.0 / Math.PI) * omega0; // convert to hours
        return T;
    }
}

/**
 * Generates an array of day lengths for all days at the given latitude (in radians) and year.
 *
 * @param latitude_rad Latitude in radians.
 * @param year The year for which to generate day lengths.
 * @return Array of day lengths in hours.
 */
private inline double[] generate_day_lengths (double latitude_rad, int year) {
    int total_days = days_in_year (year);
    double[] lengths = new double[total_days];
    for (int i = 0; i < total_days; i += 1) {
        lengths[i] = compute_day_length (latitude_rad, i + 1);
    }
    return lengths;
}

/**
 * Window for displaying the day length plot.
 */
public class DayLengthWindow : Gtk.ApplicationWindow {
    private Gtk.Entry latitude_entry;
    private Gtk.Entry year_entry;
    private Gtk.DrawingArea drawing_area;
    private double[] day_lengths;
    private int current_year;
    private double latitude_deg;
    private Gtk.Button export_button;

    /**
     * Constructs a new DayLengthWindow.
     *
     * @param app The Gtk.Application instance.
     */
    public DayLengthWindow (Gtk.Application app) {
        Object (
            application: app,
            title: "Day Length Plotter",
            default_width: 800,
            default_height: 600
        );

        // Initialize current_year first
        DateTime now = new DateTime.now_local ();
        current_year = now.get_year ();

        // Use vertical box as the main container
        var vbox_main = new Gtk.Box (Gtk.Orientation.VERTICAL, 10) {
            // Add top margin but do not add other margins since drawing area expands
            margin_top = 10
        };
        this.child = vbox_main;

        // Input area (using horizontal Box layout)
        var hbox_controls = new Gtk.Box (Gtk.Orientation.HORIZONTAL, 10) {
            margin_start = 10,
            margin_end = 10
        };
        vbox_main.append (hbox_controls);

        var lat_label = new Gtk.Label ("<b>Latitude (degrees):</b>") {
            halign = Gtk.Align.START,
            use_markup = true
        };
        hbox_controls.append (lat_label);

        latitude_entry = new Gtk.Entry () {
            width_chars = 10,
            input_purpose = Gtk.InputPurpose.NUMBER
        };
        hbox_controls.append (latitude_entry);

        var year_label = new Gtk.Label ("<b>Year:</b>") {
            halign = Gtk.Align.START,
            use_markup = true
        };
        hbox_controls.append (year_label);

        year_entry = new Gtk.Entry () {
            width_chars = 10,
            input_purpose = Gtk.InputPurpose.DIGITS,
            // Set year entry text using current_year
            text = current_year.to_string ()
        };
        hbox_controls.append (year_entry);

        var plot_button = new Gtk.Button.with_label ("Plot");
        hbox_controls.append (plot_button);
        plot_button.clicked.connect (() => {
            update_plot_data ();
            drawing_area.queue_draw ();
        });

        // Export image button
        export_button = new Gtk.Button.with_label ("Export");
        hbox_controls.append (export_button);
        export_button.clicked.connect (() => {
            var png_filter = new Gtk.FileFilter ();
            png_filter.name = "PNG Images";
            png_filter.add_mime_type ("image/png");
            
            var svg_filter = new Gtk.FileFilter ();
            svg_filter.name = "SVG Images";
            svg_filter.add_mime_type ("image/svg+xml");

            var pdf_filter = new Gtk.FileFilter ();
            pdf_filter.name = "PDF Documents";
            pdf_filter.add_mime_type ("application/pdf");

            // FileDialog.filters are required to contain default filter and others
            var filter_list = new ListStore (typeof (Gtk.FileFilter));
            filter_list.append (png_filter);
            filter_list.append (svg_filter);
            filter_list.append (pdf_filter);

            var file_dialog = new Gtk.FileDialog () {
                modal = true,
                initial_name = "daylength_plot.png",
                filters = filter_list
            };

            file_dialog.save.begin (this, null, (obj, res) => {
                try {
                    var file = file_dialog.save.end (res);
                    if (file != null) {
                        string filepath = file.get_path ();
                        export_plot (filepath);
                    }
                } catch (Error e) {
                    // Usually due to the user canceling the dialog
                    message ("File has not been saved: %s", e.message);
                }
            });
        });

        // Drawing area: using Gtk.DrawingArea and Cairo for plotting
        drawing_area = new Gtk.DrawingArea () {
            hexpand = true,
            vexpand = true
        };
        drawing_area.set_size_request (400, 400);
        drawing_area.set_draw_func (this.draw_plot);
        vbox_main.append (drawing_area);
    }

    /**
     * Updates plot data based on input values.
     */
    private void update_plot_data () {
        latitude_deg = double.parse (latitude_entry.text);
        current_year = int.parse (year_entry.text);
        // Convert input latitude (in degrees) to radians
        double latitude_rad = latitude_deg * Math.PI / 180.0;
        day_lengths = generate_day_lengths (latitude_rad, current_year);
    }

    /**
     * Drawing callback to render the day length plot.
     *
     * @param area The drawing area widget.
     * @param cr The Cairo context.
     * @param width The width of the drawing area.
     * @param height The height of the drawing area.
     */
    private void draw_plot (Gtk.DrawingArea area, Cairo.Context cr, int width, int height) {
        // Clear background to white
        cr.set_source_rgb (1, 1, 1);
        cr.paint ();

        // Set margins
        int margin_left = 75;
        int margin_right = 20;
        int margin_top = 50;
        int margin_bottom = 70;
        int plot_width = width - margin_left - margin_right;
        int plot_height = height - margin_top - margin_bottom;

        // Fixed Y axis range: -0.5 to 24.5
        double y_min = -0.5, y_max = 24.5;
        // X axis range: 1 to total_days
        int total_days = (day_lengths != null) ? day_lengths.length : 365;

        // Draw grid lines (gray)
        cr.set_source_rgba (0.5, 0.5, 0.5, 0.5);
        cr.set_line_width (1.0);
        // Horizontal grid lines (every 3 hours)
        for (int tick = 0; tick <= 24; tick += 3) {
            double y_val = margin_top + (plot_height * (1 - (tick - y_min) / (y_max - y_min)));
            cr.move_to (margin_left, y_val);
            cr.line_to (width - margin_right, y_val);
            cr.stroke ();
        }
        // Vertical grid lines (start of each month)
        for (int month = 1; month <= 12; month += 1) {
            DateTime month_start = new DateTime (new TimeZone.local (), current_year, month, 1, 0, 0, 0);
            int day_num = month_start.get_day_of_year ();
            double x_pos = margin_left + (plot_width * ((double) (day_num - 1) / (total_days - 1)));
            cr.move_to (x_pos, margin_top);
            cr.line_to (x_pos, height - margin_bottom);
            cr.stroke ();
        }

        // Draw axes (black, bold)
        cr.set_source_rgb (0, 0, 0);
        cr.set_line_width (2.0);
        // X axis
        cr.move_to (margin_left, height - margin_bottom);
        cr.line_to (width - margin_right, height - margin_bottom);
        cr.stroke ();
        // Y axis
        cr.move_to (margin_left, margin_top);
        cr.line_to (margin_left, height - margin_bottom);
        cr.stroke ();

        // Draw Y axis ticks
        cr.set_line_width (1.0);
        for (int tick = 0; tick <= 24; tick += 3) {
            double y_val = margin_top + (plot_height * (1 - (tick - y_min) / (y_max - y_min)));
            cr.move_to (margin_left - 5, y_val);
            cr.line_to (margin_left, y_val);
            cr.stroke ();
            // Draw tick labels
            cr.set_font_size (22);
            Cairo.TextExtents ext;
            cr.text_extents (tick.to_string (), out ext);
            cr.move_to (margin_left - 10 - ext.width, y_val + ext.height / 2);
            cr.show_text (tick.to_string ());
        }

        // Draw X axis ticks (start of each month)
        for (int month = 1; month <= 12; month += 1) {
            // Use GLib.DateTime to construct the 1st of each month
            DateTime month_start = new DateTime (new TimeZone.local (), current_year, month, 1, 0, 0, 0);
            int day_num = month_start.get_day_of_year ();
            double x_pos = margin_left + (plot_width * ((double) (day_num - 1) / (total_days - 1)));
            cr.move_to (x_pos, height - margin_bottom);
            cr.line_to (x_pos, height - margin_bottom + 5);
            cr.stroke ();
            // Draw month labels
            string label = month.to_string ();
            cr.set_font_size (22);
            Cairo.TextExtents ext;
            cr.text_extents (label, out ext);
            cr.move_to (x_pos - ext.width / 2, height - margin_bottom + 20);
            cr.show_text (label);
        }

        // Draw X and Y axis titles
        cr.set_source_rgb (0, 0, 0);
        cr.set_font_size (22);

        // X axis title
        string x_title = "Date (Month)";
        Cairo.TextExtents x_ext;
        cr.text_extents (x_title, out x_ext);
        cr.move_to ((double) width / 2 - x_ext.width / 2, height - margin_bottom + 50);
        cr.show_text (x_title);

        // Y axis title
        string y_title = "Day Length (hours)";
        Cairo.TextExtents y_ext;
        cr.text_extents (y_title, out y_ext);
        cr.save ();
        // Position 45 pixels to the left of Y axis, vertically centered
        cr.translate (margin_left - 45, (double) height / 2);
        // Rotate -90 degrees (π/2) for vertical text
        cr.rotate (-Math.PI / 2);
        // Adjust text position for vertical centering
        cr.move_to (-y_ext.width / 2, 0);
        cr.show_text (y_title);
        cr.restore ();

        // Add caption below the X axis title for clarity and aesthetics
        string caption;
        if (day_lengths == null) {
            caption = "Day Length";
        } else {
            caption = "Day Length - Latitude: %.2f°, Year: %d".printf (latitude_deg, current_year);
        }
        cr.set_font_size (22);
        Cairo.TextExtents cap_ext;
        cr.text_extents (caption, out cap_ext);
        cr.move_to ((width - cap_ext.width) / 2, (double) margin_top / 2);
        cr.show_text (caption);

        // Return if no data
        if (day_lengths == null) {
            return;
        }

        // Draw data curve (red, bold)
        cr.set_source_rgb (1, 0, 0);
        cr.set_line_width (2.5);
        for (int i = 0; i < total_days; i += 1) {
            double x = margin_left + (plot_width * ((double) i / (total_days - 1)));
            double y = margin_top + (plot_height * (1 - (day_lengths[i] - y_min) / (y_max - y_min)));
            if (i == 0) {
                cr.move_to (x, y);
            } else {
                cr.line_to (x, y);
            }
        }
        cr.stroke ();
    }

    /**
     * Exports the current day length plot to an image file (PNG or SVG).
     *
     * This function gets the current width and height of the drawing area.
     * If invalid, it defaults to 800x600.
     * It then creates a Cairo surface (SVG or PNG) and draws the plot onto it.
     *
     * @param filepath The destination file path.
     */
    private void export_plot (string filepath) {
        int width = drawing_area.get_width ();
        int height = drawing_area.get_height ();

        if (width <= 0 || height <= 0) {
            width = 800;
            height = 600;
        }

        string? extension = null;
        var last_dot = filepath.last_index_of_char ('.');
        if (last_dot != -1) {
            extension = filepath[last_dot:].down ();
        }

        if (extension == ".svg") {
            Cairo.SvgSurface surface = new Cairo.SvgSurface (filepath, width, height);
            Cairo.Context cr = new Cairo.Context (surface);
            draw_plot (drawing_area, cr, width, height);
        } else if (extension == ".pdf") {
            Cairo.PdfSurface surface = new Cairo.PdfSurface (filepath, width, height);
            Cairo.Context cr = new Cairo.Context (surface);
            draw_plot (drawing_area, cr, width, height);
        } else {
            Cairo.ImageSurface surface = new Cairo.ImageSurface (Cairo.Format.RGB24, width, height);
            Cairo.Context cr = new Cairo.Context (surface);
            draw_plot (drawing_area, cr, width, height);
            surface.write_to_png (filepath);
        }
    }
}

/**
 * Main application class for Day Length Plotter.
 */
public class DayLengthApp : Gtk.Application {

    /**
     * Constructs a new DayLengthApp.
     */
    public DayLengthApp () {
        Object (
            application_id: "com.github.wszqkzqk.DayLengthApp",
            flags: ApplicationFlags.DEFAULT_FLAGS
        );
    }

    /**
     * Activates the application.
     */
    protected override void activate () {
        var win = new DayLengthWindow (this);
        win.present ();
    }
}

/**
 * Main entry point.
 *
 * @param args Command line arguments.
 * @return Exit status code.
 */
public static int main (string[] args) {
    var app = new DayLengthApp ();
    return app.run (args);
}
```

## 编译与运行说明
- 文件最上方的 shebang 指定了编译命令，其包含了：
  - 指定 Vala 编译器（`#!/usr/bin/env -S vala`）。
  - 添加 gtk4 包（`--pkg=gtk4`）。
  - 链接数学库 (`-lm`)。
  - 各种编译优化参数（如 `-O2`、`-march=native` 等）。
- 运行前请确保系统已安装 Vala、GTK4 以及相关编译工具（如 `gcc`）。
- 可以直接执行该脚本，也可以在命令行中使用如下命令进行编译：
  ```bash
  valac --pkg gtk4 -X -lm -X -pipe -X -O2 daylengthgtk.vala
  ```

# 构建应用：太阳高度角计算与绘制工具

在了解了白昼时长计算程序后，我们再来看一个与天文计算相关的 GTK4 应用程序。这个程序用于计算并绘制地球上任意纬度、任意日期的太阳高度角随时间变化的曲线。它将进一步展示 GTK4 中 `Gtk.SpinButton` 和 `Gtk.Calendar` 等新组件的使用，以及 Cairo 绘图更精细的控制，例如绘制阴影区域。

为了达到更高的精度，笔者在这里不再使用之前的固定的春分日期以及基于匀速圆周运动假设的赤纬计算，而是使用 [NOAA 赤纬公式](https://gml.noaa.gov/grad/solcalc/solareqns.PDF)来计算太阳赤纬角。该公式通过保留更多傅里叶级数项来提高精度，能更准确地反映太阳在天空中的位置。

该程序同样做了一些简化：

*   不考虑大气折射
*   假设中午12点太阳高度角最大
*   假设太阳时角严格线性变化
*   傅里叶级数的计算展开到 3 阶
    *   相比于之前的简单、理想的几何模型的 1 阶正弦函数包含了更多复杂的周期性变化
    *   但仍无法考虑长期的岁差等效应

## 运行效果

|[![#~/img/GTK-examples/chongqing-solar-angle-spring.webp](/img/GTK-examples/chongqing-solar-angle-spring.webp)](/img/GTK-examples/chongqing-solar-angle-spring.webp)|[![#~/img/GTK-examples/beijing-solar-angle-summer.webp](/img/GTK-examples/beijing-solar-angle-summer.webp)](/img/GTK-examples/beijing-solar-angle-summer.webp)|
|:----:|:----:|
|重庆(北半球春分)|北京(北半球夏至)|
|[![#~/img/GTK-examples/singapore-solar-angle-autumn.webp](/img/GTK-examples/singapore-solar-angle-autumn.webp)](/img/GTK-examples/singapore-solar-angle-autumn.webp)|[![#~/img/GTK-examples/n-polar-solar-angle-winter.webp](/img/GTK-examples/n-polar-solar-angle-winter.webp)](/img/GTK-examples/n-polar-solar-angle-winter.webp)|
|新加坡(北半球秋分)|北极点(北半球冬至)|

## 程序架构

## 核心计算函数

- `generate_sun_angles (double latitude_rad, int day_of_year, int year)`  
    - 使用 NOAA 赤纬公式计算 `δ`：  
      非闰年时 $\gamma = \frac{2\pi\,(n - 1)}{365}$ ，闰年时 $\gamma = \frac{2\pi\,(n - 1)}{366}$ 。
      代入经验公式得到赤纬：

      $$
      \begin{aligned}
      \delta &= 0.006918 - 0.399912 \cos\gamma
              + 0.070257 \sin\gamma \\
          &\quad - 0.006758 \cos(2\gamma)
              + 0.000907 \sin(2\gamma) \\
          &\quad - 0.002697 \cos(3\gamma)
              + 0.001480 \sin(3\gamma)
      \end{aligned}
      $$

      公式含义：
      - n：当年第 n 天
      - γ：太阳周年角（弧度），表示地球在轨道上的位置
      - δ：太阳赤纬（弧度），表示太阳在天球赤道平面的投影高度
    - 每分钟计算时间点，填充 `sun_angles` 数组（单位：°）

- `update_plot_data ()`  
  - 从 `latitude_spin` 和 `calendar` 读取参数  
  - 调用 `generate_sun_angles` 更新数据

## 界面与事件处理

- `Gtk.SpinButton`：范围 [-90, 90]，步长 0.1，信号 `value_changed`  
- `Gtk.Calendar`：信号 `day_selected`  
- 信号触发时调用 `update_plot_data ()` 并 `drawing_area.queue_draw ()` 重绘  
- “Export Image”按钮：打开 `Gtk.FileDialog`，调用 `export_chart (filepath)`

## 绘图函数

- `draw_sun_angle_chart (Gtk.DrawingArea, Cairo.Context, int width, int height)`：  
  1. 白色背景  
  2. 阴影矩形表示地平线以下区域（半透明灰）  
  3. 网格：每 15° 水平线、每 2 小时垂直线  
  4. 坐标轴、刻度与标签  
  5. 红色曲线绘制高度角  
  6. 标题显示纬度和日期

## 实现代码

实现这个应用程序的代码如下：

```vala
#!/usr/bin/env -S vala --pkg=gtk4 -X -lm -X -O2 -X -march=native -X -pipe

public class SolarAngleApp : Gtk.Application {
    private const double DEG2RAD = Math.PI / 180.0;
    private const double RAD2DEG = 180.0 / Math.PI;
    private const int RESOLUTION = 1440; // samples per day, 1 sample per minute

    private Gtk.ApplicationWindow window;
    private Gtk.DrawingArea drawing_area;
    private Gtk.SpinButton latitude_spin;
    private Gtk.Calendar calendar;
    private Gtk.Button export_button;
    private double latitude = 0.0;
    private DateTime selected_date;
    private double sun_angles[RESOLUTION]; // Fixed size array for solar angles

    public SolarAngleApp () {
        Object (application_id: "com.github.wszqkzqk.SolarAngleApp");
        selected_date = new DateTime.now_local ();
    }

    protected override void activate () {
        window = new Gtk.ApplicationWindow (this);
        window.title = "Solar Angle Calculator";
        window.default_width = 1000;
        window.default_height = 700;

        var main_box = new Gtk.Box (Gtk.Orientation.HORIZONTAL, 0) {
            margin_start = 10,
            margin_end = 10,
            margin_top = 10,
            margin_bottom = 10,
        };

        var left_panel = new Gtk.Box (Gtk.Orientation.VERTICAL, 15) {
            width_request = 320,
            hexpand = false,
            margin_start = 10,
            margin_end = 10,
            margin_top = 10,
            margin_bottom = 10,
        };

        var latitude_group = new Gtk.Box (Gtk.Orientation.VERTICAL, 8);
        var latitude_label = new Gtk.Label ("<b>Latitude Settings</b>") {
            use_markup = true,
            halign = Gtk.Align.START,
        };

        var latitude_box = new Gtk.Box (Gtk.Orientation.HORIZONTAL, 10);
        var latitude_input_label = new Gtk.Label ("Latitude (deg):");
        latitude_input_label.halign = Gtk.Align.START;
        latitude_spin = new Gtk.SpinButton.with_range (-90, 90, 0.1) {
            value = latitude,
            digits = 2,
            width_request = 100,
        };
        latitude_spin.value_changed.connect (() => {
            latitude = latitude_spin.value;
            update_plot_data ();
            drawing_area.queue_draw ();
        });

        latitude_box.append (latitude_input_label);
        latitude_box.append (latitude_spin);
        latitude_group.append (latitude_label);
        latitude_group.append (latitude_box);

        var date_group = new Gtk.Box (Gtk.Orientation.VERTICAL, 8);
        var date_label = new Gtk.Label ("<b>Date Selection</b>") {
            use_markup = true,
            halign = Gtk.Align.START,
        };
        calendar = new Gtk.Calendar ();
        calendar.day_selected.connect (() => {
            selected_date = calendar.get_date ();
            update_plot_data ();
            drawing_area.queue_draw ();
        });

        date_group.append (date_label);
        date_group.append (calendar);

        var export_group = new Gtk.Box (Gtk.Orientation.VERTICAL, 8);
        var export_label = new Gtk.Label ("<b>Export Chart</b>") {
            use_markup = true,
            halign = Gtk.Align.START,
        };

        export_button = new Gtk.Button.with_label ("Export Image");
        export_button.clicked.connect (on_export_clicked);

        export_group.append (export_label);
        export_group.append (export_button);

        left_panel.append (latitude_group);
        left_panel.append (date_group);
        left_panel.append (export_group);

        drawing_area = new Gtk.DrawingArea () {
            hexpand = true,
            vexpand = true,
            width_request = 600,
            height_request = 500,
        };
        drawing_area.set_draw_func (draw_sun_angle_chart);

        main_box.append (left_panel);
        main_box.append (drawing_area);

        update_plot_data ();

        window.child = main_box;
        window.present ();
    }

    private void generate_sun_angles (double latitude_rad, int day_of_year, int year) {
        double sin_lat = Math.sin (latitude_rad);
        double cos_lat = Math.cos (latitude_rad);

        // Use the equation of NOAA for solar declination
        double days_in_year = ((year % 4 == 0) && ((year % 100 != 0) || (year % 400 == 0))) ? 366.0 : 365.0;
        double gamma = 2.0 * Math.PI * day_of_year / days_in_year;
        double delta = 0.006918
            - 0.399912 * Math.cos (gamma)
            + 0.070257 * Math.sin (gamma)
            - 0.006758 * Math.cos (2 * gamma)
            + 0.000907 * Math.sin (2 * gamma)
            - 0.002697 * Math.cos (3 * gamma)
            + 0.00148 * Math.sin (3 * gamma);

        for (int i = 0; i < RESOLUTION; i += 1) {
            // map index to hour of day, then to hour angle around solar noon
            double t = 24.0 / (RESOLUTION - 1) * i;
            double hour_angle = (2.0 * Math.PI / 24.0) * (t - 12.0);
            // spherical formula for elevation angle
            double sin_a = sin_lat * Math.sin (delta) + cos_lat * Math.cos (delta) * Math.cos (hour_angle);
            sun_angles[i] = Math.asin (sin_a) * RAD2DEG;
        }
    }

    private void update_plot_data () {
        int day_of_year = selected_date.get_day_of_year ();
        double latitude_rad = latitude * DEG2RAD;
        int year = selected_date.get_year ();
        generate_sun_angles (latitude_rad, day_of_year, year);
    }

    private void draw_sun_angle_chart (Gtk.DrawingArea area, Cairo.Context cr, int width, int height) {
        // fill white background
        cr.set_source_rgb (1, 1, 1);
        cr.paint ();

        int ml = 70, mr = 20, mt = 50, mb = 70;
        int pw = width - ml - mr, ph = height - mt - mb;

        double y_min = -90, y_max = 90;

        double horizon_y = mt + ph * (1 - (0 - y_min) / (y_max - y_min));
        
        cr.set_source_rgba (0.7, 0.7, 0.7, 0.3);
        cr.rectangle (ml, horizon_y, pw, height - mb - horizon_y);
        cr.fill ();

        // draw horizontal grid every 15° elevation
        cr.set_source_rgba (0.5, 0.5, 0.5, 0.5);
        cr.set_line_width (1);
        for (int a = -90; a <= 90; a += 15) {
            double yv = mt + ph * (1 - (a - y_min) / (y_max - y_min));
            cr.move_to (ml, yv);
            cr.line_to (width - mr, yv);
            cr.stroke ();
        }
        // draw vertical grid every 2 hours
        for (int h = 0; h <= 24; h += 2) {
            double xv = ml + pw * (h / 24.0);
            cr.move_to (xv, mt);
            cr.line_to (xv, height - mb);
            cr.stroke ();
        }

        // draw axes and horizon line
        cr.set_source_rgb (0, 0, 0);
        cr.set_line_width (2);
        cr.move_to (ml, height - mb);
        cr.line_to (width - mr, height - mb);
        cr.stroke ();
        cr.move_to (ml, mt);
        cr.line_to (ml, height - mb);
        cr.stroke ();
        // Draw horizon line
        cr.move_to (ml, horizon_y);
        cr.line_to (width - mr, horizon_y);
        cr.stroke ();

        cr.set_line_width (1);
        cr.set_font_size (20);
        for (int a = -90; a <= 90; a += 15) {
            double yv = mt + ph * (1 - (a - y_min) / (y_max - y_min));
            cr.move_to (ml - 5, yv);
            cr.line_to (ml, yv);
            cr.stroke ();
            var te = Cairo.TextExtents ();
            var txt = a.to_string ();
            cr.text_extents (txt, out te);
            cr.move_to (ml - 10 - te.width, yv + te.height / 2);
            cr.show_text (txt);
        }
        for (int h = 0; h <= 24; h += 2) {
            double xv = ml + pw * (h / 24.0);
            cr.move_to (xv, height - mb);
            cr.line_to (xv, height - mb + 5);
            cr.stroke ();
            var te = Cairo.TextExtents ();
            var txt = h.to_string ();
            cr.text_extents (txt, out te);
            cr.move_to (xv - te.width / 2, height - mb + 25);
            cr.show_text (txt);
        }

        // plot solar elevation curve in red
        cr.set_source_rgb (1, 0, 0);
        cr.set_line_width (2);
        for (int i = 0; i < RESOLUTION; i += 1) {
            double x = ml + pw * (i / (double)(RESOLUTION - 1));
            double y = mt + ph * (1 - (sun_angles[i] - y_min) / (y_max - y_min));
            if (i == 0) {
                cr.move_to (x, y);
            } else {
                cr.line_to (x, y);
            }
        }
        cr.stroke ();

        cr.set_source_rgb (0, 0, 0);
        cr.set_font_size (20);
        string x_title = "Time (Hour)";
        Cairo.TextExtents x_ext;
        cr.text_extents (x_title, out x_ext);
        cr.move_to ((double)width / 2 - x_ext.width / 2, height - mb + 55);
        cr.show_text (x_title);
        string y_title = "Solar Elevation (°)";
        Cairo.TextExtents y_ext;
        cr.text_extents (y_title, out y_ext);
        cr.save ();
        cr.translate (ml - 45, (double)height / 2);
        cr.rotate (-Math.PI / 2);
        cr.move_to (-y_ext.width / 2, 0);
        cr.show_text (y_title);
        cr.restore ();

        string caption = "Solar Elevation Angle - Latitude: %.2f°, Date: %s".printf (
            latitude, selected_date.format ("%Y-%m-%d"));
        cr.set_font_size (22);
        Cairo.TextExtents cap_ext;
        cr.text_extents (caption, out cap_ext);
        cr.move_to ((width - cap_ext.width) / 2, (double)mt / 2);
        cr.show_text (caption);
    }

    private void on_export_clicked () {
        // Open save dialog with PNG, SVG & PDF filters
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
            filters = filter_list
        };

        file_dialog.save.begin (window, null, (obj, res) => {
            try {
                var file = file_dialog.save.end (res);
                if (file != null) {
                    string filepath = file.get_path ();
                    export_chart (filepath);
                }
            } catch (Error e) {
                message ("File has not been saved: %s", e.message);
            }
        });
    }

    private void export_chart (string filepath) {
        // Export current chart to chosen format by extension
        int width = drawing_area.get_width ();
        int height = drawing_area.get_height ();

        if (width <= 0 || height <= 0) {
            width = 800;
            height = 600;
        }

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

    public static int main (string[] args) {
        var app = new SolarAngleApp ();
        return app.run (args);
    }
}
```

## 编译与运行说明
- 文件最上方的 shebang 指定了编译命令，其包含了：
  - 指定 Vala 编译器（`#!/usr/bin/env -S vala`）。
  - 添加 gtk4 包（`--pkg=gtk4`）。
  - 链接数学库 (`-lm`)。
  - 各种编译优化参数（如 `-O2`、`-march=native` 等）。
- 运行前请确保系统已安装 Vala、GTK4 以及相关编译工具（如 `gcc`）。
- 可以直接执行该脚本，也可以在命令行中使用如下命令进行编译：
  ```bash
  valac --pkg gtk4 -X -lm -X -pipe -X -O2 solaranglegtk.vala
  ```
  编译后将生成 `solaranglegtk` 可执行文件，直接运行即可。
