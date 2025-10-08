--- 
layout:     post
title:      GTK4/Vala 教程续：提升太阳高度角计算精度
subtitle:   从经验公式到 Meeus 算法的进阶实践
date:       2025-10-08
author:     wszqkzqk
header-img: img/GTK-logo.webp
catalog:    true
tags:       开源软件 GTK Vala 天文学
---

## 前言

在上一篇[《GTK4/Vala 教程：构建现代桌面应用》](https://wszqkzqk.github.io/2025/08/07/GTK-Vala-Tutorial-3/)中，我们从零到一构建了一个功能完备的太阳高度角计算器。那篇文章的重点在于展示如何将 GTK4、LibAdwaita、Cairo、异步网络和 JSON 解析等技术栈有机地结合起来，打造一个现代化的桌面应用。

然而，原文中为了教学的简洁性和普适性，计算太阳高度角的核心算法采用了一套基于 NOAA 的经验公式。该公式通过傅里叶级数近似，在大多数场景下表现良好，但与真正的天文模型相比，在精度上仍有提升空间。

本文作为续篇，将深入探讨如何将计算核心升级为精度更高的 **Meeus 算法**。这不仅是一次代码上的优化，更是一次从“经验近似”到“物理建模”的思维跃迁。我们将一起探索儒略日、黄赤交角、方程时等更专业的天文概念，并用 Vala 将它们精确地实现出来。

此外，本文还包含一个“番外”章节，其中我们将以“白昼时长计算器”为例，探讨如何应用这些天文计算原理于其他场景，从而将本文打造为一个更具主题性的“Vala 天文计算进阶实践”.

## 第一部分：为何需要更高精度的算法？

你可能会问：既然原来的版本已经能画出看起来很不错的日升日落曲线了，为什么还要费心去升级算法呢？

1.  **追求精确性**：经验公式是对大量观测数据的拟合，它“知其然，而不知其所以然”。而基于天体运行力学的算法（如 Meeus 算法）则是从地球和太阳的运动规律出发，进行第一性原理的推导。后者在理论上更严谨，计算结果也更精确，尤其是在计算长跨度时间或特殊地理位置（如极地）时，优势更为明显。
2.  **扩展性与通用性**：理解了更底层的天文模型，我们不仅能计算太阳高度角，还能轻松地计算出日出日落时间、太阳方位角、黎明/黄昏时长等更多参数，为应用未来的功能扩展打下坚实基础。
3.  **学习的乐趣**：将天文学的理论知识转化为屏幕上精确运行的代码，这个过程本身就充满了探索和创造的乐趣。

## 第二部分：Meeus 算法核心概念

新的 `generate_sun_angles` 函数实现，其背后的理论基础是天文学家 Jean Meeus 在其著作《天文算法》中推广的一系列简化公式。这些公式在保证了极高精度的同时，又避免了使用完整的、极其复杂的轨道摄动理论。

让我们来拆解一下新算法中的关键步骤和概念。

### 1. 儒略日 (Julian Date)

天文学计算中，使用年月日时分秒来表示时间非常繁琐，尤其是在计算两个时刻之间的时间差时。**儒略日 (JD)** 提供了一个解决方案，它是一种不记年、月的长期纪日法，简单来说就是一个从公元前 4713 年 1 月 1 日格林尼治标准时间中午 12:00 开始的连续日计数。这使得时间计算简化为简单的加减法。

对于 Vala 程序，GLib 可以为我们提供可以直接使用的工具。我们可以使用 `GLib.Date` 类型的 `get_julian()` 方法来方便地得到儒略日，但是需要注意的是，`GLib.Date.get_julian()` 返回的是从公元 0001 年 1 月 1 日开始的儒略日数，而非标准的儒略日数，有着不同的偏移。

### 2. J2000.0 历元 (J2000.0 Epoch)

为了简化公式，天文学家选择了一个标准参考时刻，即 **J2000.0 历元**，对应于 2000 年 1 月 1 日国际原子时 12:00。我们的计算将以从这个历元开始的天数 `d` 为基础。

`double base_days_from_epoch = julian_date - 730120.5;`

这里减去 `730120.5` 即可将当天 00:00 UTC 转换为从 J2000.0 历元起算的天数。

### 3. 黄赤交角 (Obliquity of the Ecliptic, ε)

这是地球赤道平面与黄道平面（地球绕太阳公转的轨道平面）之间的夹角，它导致了四季的产生。这个角度并非固定不变，而是在缓慢变化。Meeus 算法给出了一个高次多项式来精确计算它：

$$
\epsilon (\text{deg}) = 23.439291111 - 3.560347 \times 10^{-7} d - \dots
$$

其中 `d` 是从 J2000.0 历元起算的天数。

### 4. 太阳的轨道参数

为了确定太阳在天空中的位置，我们需要计算几个关键的轨道参数，它们同样以 `d` 的多项式形式给出：

*   **平近点角 (Mean Anomaly, M)**：表示地球在其椭圆轨道上相对于近日点的位置。
*   **平黄经 (Mean Longitude, L)**：表示在一个假想的、以太阳为中心的匀速圆周轨道上，地球的位置。

### 5. 太阳的真黄经 (True Ecliptic Longitude, λ)

由于地球轨道是椭圆而非正圆，其公转速度是变化的（开普勒第二定律）。我们需要从“平黄经”计算出“真黄经”，这个修正过程被称为**中心差 (Equation of the Center)**。

$$
\lambda (\text{deg}) = L + C_1 \sin(M) + C_2 \sin(2M) + \dots
$$

其中 $C_1, C_2, \dots$ 是修正系数。真黄经精确地描述了太阳在黄道坐标系中的位置。

### 6. 从黄道坐标到赤道坐标

有了真黄经 `λ` 和黄赤交角 `ε`，我们就可以通过球面三角公式，将太阳的位置从黄道坐标系转换到我们更熟悉的赤道坐标系，得到两个关键参数：

*   **太阳赤纬 (Declination, δ)**：太阳光线与地球赤道平面之间的夹角。
*   **赤经 (Right Ascension, RA)**：太阳在天球赤道上的经度。

### 7. 方程时 (Equation of Time, EoT)

日常使用的钟表时间（平太阳时）与根据太阳真实位置决定的时间（真太阳时）之间存在一个差值，这个差值就是**方程时 (EoT)**。它由地球轨道偏心率和黄赤交角共同导致。我们在旧算法中也计算了它，但新算法基于赤经和平黄经计算，精度更高。

### 8. 时角与太阳高度角

最后一步与旧算法类似：
1.  根据本地时间、经度、时区和方程时计算出**真太阳时 (True Solar Time)**。
2.  将真太阳时转换为**时角 (Hour Angle, HA)**，它表示太阳相对于本地子午线的角距离。
3.  最终，结合本地纬度 `φ`、太阳赤纬 `δ` 和时角 `HA`，使用球面三角公式计算出太阳高度角 `α`：

    $$
    \sin(\alpha) = \sin(\phi)\sin(\delta) + \cos(\phi)\cos(\delta)\cos(HA)
    $$

这个过程虽然比经验公式复杂得多，但每一步都有坚实的物理意义，最终的结果也经得起考验。

## 第三部分：Vala 代码实现

下面是更新后的核心函数。`update_plot_data` 现在传递儒略日，而 `generate_sun_angles` 则完全基于我们上面讨论的 Meeus 算法流程。

```vala
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
        double ecliptic_c3 = 0.000290;
        double tst_offset = 4.0 * longitude_deg - 60.0 * timezone_offset_hrs;
        for (int i = 0; i < RESOLUTION_PER_MIN; i += 1) {
            // Calculate precise time offset for this minute (in days)
            double time_offset_days = (i / 60.0 - timezone_offset_hrs) / 24.0;
            double days_from_epoch = base_days_from_epoch + time_offset_days;
            double days_from_epoch_sq = days_from_epoch * days_from_epoch;
            double days_from_epoch_cb = days_from_epoch_sq * days_from_epoch;
            // Mean anomaly of the sun (degrees) with higher-order terms
            double mean_anomaly_deg = 357.52910 + 0.985600282 * days_from_epoch - 1.1686e-13 * days_from_epoch_sq - 9.85e-21 * days_from_epoch_cb;
            mean_anomaly_deg = Math.fmod (mean_anomaly_deg, 360.0);
            if (mean_anomaly_deg < 0) {
                mean_anomaly_deg += 360.0;
            }
            // Mean longitude of the sun (degrees) with higher-order terms
            double mean_longitude_deg = 280.46645 + 0.98564736 * days_from_epoch + 2.2727e-13 * days_from_epoch_sq;
            mean_longitude_deg = Math.fmod (mean_longitude_deg, 360.0);
            if (mean_longitude_deg < 0) {
                mean_longitude_deg += 360.0;
            }
            // Ecliptic longitude of the sun (degrees) with higher-order corrections
            double mean_anomaly_rad = mean_anomaly_deg * DEG2RAD;
            double ecliptic_longitude_deg = mean_longitude_deg + ecliptic_c1 * Math.sin (mean_anomaly_rad) + ecliptic_c2 * Math.sin (2.0 * mean_anomaly_rad) + ecliptic_c3 * Math.sin (3.0 * mean_anomaly_rad);
            ecliptic_longitude_deg = Math.fmod (ecliptic_longitude_deg, 360.0);
            if (ecliptic_longitude_deg < 0) {
                ecliptic_longitude_deg += 360.0;
            }
            // Solar declination (radians) for this specific time
            double ecliptic_longitude_rad = ecliptic_longitude_deg * DEG2RAD;
            double ecliptic_longitude_sin = Math.sin (ecliptic_longitude_rad);
            double ecliptic_longitude_cos = Math.cos (ecliptic_longitude_rad);
            double declination_sin = (obliquity_sin * ecliptic_longitude_sin).clamp (-1.0, 1.0);
            double declination_cos = Math.sqrt (1.0 - declination_sin * declination_sin);
            // Right Ascension for Equation of Time
            double right_ascension_rad = Math.atan2 (obliquity_cos * ecliptic_longitude_sin, ecliptic_longitude_cos);
            double right_ascension_deg = right_ascension_rad * RAD2DEG;
            if (right_ascension_deg < 0) {
                right_ascension_deg += 360.0;
            }
            double right_ascension_hours = right_ascension_deg / 15.0;
            // Fix quadrant ambiguity for RA
            double mean_time = Math.fmod (mean_longitude_deg / 15.0, 24.0);
            double delta_ra = right_ascension_hours - mean_time;
            if (delta_ra > 12.0) {
                right_ascension_hours -= 24.0;
            } else if (delta_ra < -12.0) {
                right_ascension_hours += 24.0;
            }
            // Equation of Time (minutes)
            double eot_hours = mean_time - right_ascension_hours;
            double eqtime_minutes = eot_hours * 60.0;
            // True Solar Time (TST) in minutes, correcting local clock by EoT and longitude
            double tst_minutes = i + eqtime_minutes + tst_offset;
            double hour_angle_deg = tst_minutes / 4.0 - 180.0;
            double hour_angle_rad = hour_angle_deg * DEG2RAD;
            // Calculate solar elevation angle directly using sin formula
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
```

## 第四部分：番外：白昼时长计算器

在掌握了太阳赤纬 `δ` 的计算方法后，我们就可以实现另一个有趣的功能：计算在给定纬度，一年中每一天的白昼时长。

用几乎一样的思路，笔者实现了一个计算某一纬度处全年中每天的白昼时长的程序，代码也在 [GitHub](https://github.com/wszqkzqk/FunValaGtkExamples/blob/master/daylengthadw.vala) 上，感兴趣的读者可以参考。

### 效果

|[![#~/img/GTK-examples/day-length-pku-light.webp](/img/GTK-examples/day-length-pku-light.webp)](/img/GTK-examples/day-length-pku-light.webp)|[![#~/img/GTK-examples/day-length-chongqing-dark.webp](/img/GTK-examples/day-length-chongqing-dark.webp)](/img/GTK-examples/day-length-chongqing-dark.webp)|
|:----:|:----:|
|浅色模式|深色模式|

### 计算方法

这里笔者同样采用了基于 Meeus 算法的高精度计算方法，其基本思路如下：

*   **计算高精度太阳赤纬 (δ)**：此步骤与本文第二部分介绍的太阳高度角计算过程完全一致。我们通过儒略日计算出从 J2000.0 历元起算的天数，进而求得太阳的真黄经，最终得到当天精确的太阳赤纬。这保证了我们计算昼长的基础数据是精确的。
*   **应用日出/日落时角公式**：太阳高度角、观察者纬度、太阳赤纬和时角（Hour Angle）之间存在一个基本关系，正如前文所述。当太阳处于地平线时（即太阳高度角为地平线修正角，通常取-0.83°以考虑大气折射），我们可以通过该关系反解出此时的太阳时角。公式如下：
  
    $$
    \cos(\omega_0) = \frac{\sin(\alpha) - \sin(\phi)\sin(\delta)}{\cos(\phi)\cos(\delta)}
    $$

    其中：
    *   $\omega_0$ 是日出或日落时的太阳时角。
    *   $\alpha$ 是地平线修正角（Horizon Angle）。
    *   $\phi$ 是观察者所在地的纬度。
    *   $\delta$ 是太阳赤纬。
*   **处理边界情况**：防止因为浮点计算误差导致后续的 `acos` 函数返回 `NaN`。
    *   如果计算出的 $\cos(\omega_0)$ 值大于等于 1，意味着太阳全天都无法升至地平线以上，即出现**极夜**，昼长为 0 小时。
    *   如果计算出的 $\cos(\omega_0)$ 值小于等于 -1，意味着太阳全天都在地平线以上，即出现**极昼**，昼长为 24 小时。
    *   对于无效的计算结果 `NaN`，程序会返回一个默认值以保证稳定性。
*   **计算昼长**：通过反余弦函数 `acos` 得到时角 $\omega_0$（以弧度为单位）。由于时角代表的是从正午到日落（或从日出到正午）的时间，根据“均太阳假设”，相同时角近似对应相同时间，所以总昼长对应 $2\omega_0$ 的弧度。最后，将这个弧度值转换为小时单位，即可得到最终的昼长。

    $$
    t \text{(hours)} = \frac{2 \cdot \omega_0}{2\pi} \times 24 = \frac{24 \cdot \omega_0}{\pi}
    $$

这种方法在一般应用中已经足够精确，避免了逐分钟的迭代求解，计算效率显著更高。由于篇幅关系，这里就不贴代码了，读者可以参考项目在 [GitHub 上的源代码](https://github.com/wszqkzqk/FunValaGtkExamples/blob/master/daylengthadw.vala)，其中包含了详细的注释和完整的逻辑。

## 总结

从一个简单的经验公式出发，我们一步步深入，最终实现了一套基于 Meeus 天文算法的高精度计算模型。这个过程不仅提升了我们应用的专业性，更重要的是，它加深了我们对问题背后物理原理的理解。

希望这篇续集能为你展示如何在软件开发中进行技术深耕，以及如何在“能用”的基础上追求“更好”。编程的乐趣，常常就蕴含在这样不断探索和优化的过程之中。

