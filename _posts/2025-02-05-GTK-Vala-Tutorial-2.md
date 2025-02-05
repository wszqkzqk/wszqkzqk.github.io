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

本文假设读者已经阅读了笔者的上一篇[GTK/Vala开发基础教程](https://wszqkzqk.github.io/2023/01/19/GTK-Vala-Tutorial/)，已经对GTK/Vala的基本概念有所了解。本文将通过一个简单的例子，展示如何使用GTK4和Vala构建一个简单的应用程序。

# 构建应用：白昼时长计算与绘制工具

笔者在这里用一个有趣的例子来展示如何构建一个简单的应用程序。该程序用到了GTK4的许多组件，以及Cairo的绘图功能。

这个应用程序可用于计算在不同纬度下，全年的每一天的白昼时长。为了方便，程序做了这些简化：

* 不考虑大气折射
* 不考虑进动（岁差）
* 假设地球公转与自转的角速度恒定
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
  利用近似公式计算第 n 天的太阳赤纬角（单位：角度），公式为：  
  $\delta = 23.44 \times \sin\left(\frac{2\pi}{365} \times (n - 81)\right)$

- `compute_day_length (double latitude, int n)`  
  根据输入的纬度（单位：度）和天数，计算当天的日照时长（单位：小时）。  
  先将纬度转换为弧度，然后使用公式 $X = -\tan(\phi)\tan(\delta)$ 计算 X 值，其中 $\phi$ 为纬度（弧度）、$\delta$ 为太阳赤纬角（弧度）。  
  此处 X 表示太阳在地平面上升降时刻对应的余弦值，即 $\cos(\omega_0)$，通过 X 的取值判断：  
  - 若 $X$ 在 $[-1, 1]$ 内，则通过 $\omega_0 = \arccos(X)$ 计算出太阳的小时角，再利用该角度计算日照时长；  
  - 若 $X < -1$，则表示处于极昼状态（日照 24 小时）；  
  - 若 $X > 1$，则表示处于极夜状态（日照 0 小时）。

- `generate_day_lengths (double latitude, int year)`  
  遍历一年中的每一天，调用 `compute_day_length` 计算各天日照时长，返回包含所有白昼时长数据的数组。

### 主窗口类 `DayLengthWindow`
此类继承自 `Gtk.ApplicationWindow`，用于构建图形界面和显示绘图内容：
- **界面组件**  
  - 使用 `Gtk.Box` 和 `Gtk.Grid` 布局管理窗口组件。  
  - `Gtk.Entry` 控件允许用户输入纬度和年份，并通过 `Gtk.Button` 触发绘图更新。
- **事件处理**  
  - “Plot Day Length” 按钮点击时调用 `update_plot_data ()` 读取输入并更新数据，再通过 `drawing_area.queue_draw ()` 重绘图表。
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
 * Computes solar declination in degrees using an approximate formula.
 *
 * Formula: δ (deg) = 23.44 * sin(2π/365 * (n - 81))
 *
 * @param n The day number in the year.
 * @return Solar declination in degrees.
 */
private inline double solar_declination (int n) {
    return 23.44 * Math.sin (2 * Math.PI / 365.0 * (n - 81));
}

/**
 * Calculates the day length (in hours) for a given latitude and day number.
 *
 * Using formula: T = (2/15) * arccos( -tan(φ) * tan(δ) )
 *
 * φ: observer's latitude, δ: solar declination
 *
 * When |tan φ * tan δ| > 1, returns polar day (24 hours) or polar night (0 hours)
 *
 * @param latitude Latitude in degrees.
 * @param n The day number in the year.
 * @return Day length in hours.
 */
private inline double compute_day_length (double latitude, int n) {
    double phi = latitude * Math.PI / 180.0; // Convert to radians
    double delta_deg = solar_declination (n);
    double delta = delta_deg * Math.PI / 180.0; // Convert to radians
    double X = -Math.tan (phi) * Math.tan (delta);
    if (X < -1) {
        return 24.0; // Polar day
    } else if (X > 1) {
        return 0.0;  // Polar night
    } else {
        double omega0 = Math.acos (X); // in radians
        double omega0_deg = omega0 * 180.0 / Math.PI;
        double T = 2 * (omega0_deg / 15.0); // 15° per hour
        return T;
    }
}

/**
 * Generates an array of day lengths for all days at the given latitude and year.
 *
 * @param latitude Latitude in degrees.
 * @param year The year for which to generate day lengths.
 * @return Array of day lengths in hours.
 */
private inline double[] generate_day_lengths (double latitude, int year) {
    int total_days = days_in_year (year);
    double[] lengths = new double[total_days];
    for (int i = 0; i < total_days; i += 1) {
        lengths[i] = compute_day_length (latitude, i + 1);
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
    private double current_latitude;

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
        var vbox = new Gtk.Box (Gtk.Orientation.VERTICAL, 10);
        set_child (vbox);

        // Input area (using Grid layout)
        var grid = new Gtk.Grid ();
        grid.column_spacing = 10;
        grid.row_spacing = 10;
        vbox.append (grid);

        var lat_label = new Gtk.Label ("Latitude (degrees, positive for N, negative for S):");
        lat_label.set_margin_start (5);
        lat_label.set_margin_top (5);
        lat_label.set_halign (Gtk.Align.START);
        lat_label.set_markup ("<b>Latitude (degrees):</b>");
        grid.attach (lat_label, 0, 0, 1, 1);

        latitude_entry = new Gtk.Entry ();
        latitude_entry.set_width_chars (10);
        grid.attach (latitude_entry, 1, 0, 1, 1);

        var year_label = new Gtk.Label ("Year:");
        year_label.set_margin_start (5);
        year_label.set_margin_top (5);
        year_label.set_halign (Gtk.Align.START);
        year_label.set_markup ("<b>Year:</b>");
        grid.attach (year_label, 2, 0, 1, 1);

        year_entry = new Gtk.Entry ();
        year_entry.set_width_chars (10);
        grid.attach (year_entry, 3, 0, 1, 1);
        // Set year entry text using current_year
        year_entry.text = current_year.to_string ();

        var plot_button = new Gtk.Button.with_label ("Plot Day Length");
        grid.attach (plot_button, 4, 0, 1, 1);
        plot_button.clicked.connect (() => {
            update_plot_data ();
            drawing_area.queue_draw ();
        });

        // Drawing area: using Gtk.DrawingArea and Cairo for plotting
        drawing_area = new Gtk.DrawingArea ();
        // Make the drawing area expandable
        drawing_area.hexpand = true;
        drawing_area.vexpand = true;
        // Register drawing callback
        drawing_area.set_draw_func (this.draw_plot);
        vbox.append (drawing_area);
    }

    /**
     * Updates plot data based on input values.
     */
    private void update_plot_data () {
        current_latitude = double.parse (latitude_entry.text);
        current_year = int.parse (year_entry.text);
        day_lengths = generate_day_lengths (current_latitude, current_year);
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
        int margin_top = 40;
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
