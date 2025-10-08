---
layout:     post
title:      Vala 数值计算实践：高精度太阳位置算法
subtitle:   以 Meeus 算法为例的 Vala 数值计算探讨
date:       2025-10-08
author:     wszqkzqk
header-img: img/GTK-logo.webp
catalog:    true
tags:       开源软件 GTK Vala 数值计算
---

## 前言

Vala 语言以其将高级语言的便利性与C语言的原始性能相结合的特点，在桌面应用开发领域（尤其是 GNOME 生态）备受青睐。然而，它的能力远不止于构建用户界面。Vala 编译到C的本质，使其在需要高性能的数值与科学计算场景中，同样是一个值得考虑的强大选项。

本文旨在探讨 Vala 在科学计算领域的应用潜力。我们将以一个经典的天文学问题——**精确计算太阳在天空中的位置**——作为核心案例，从零开始，分步详解如何用 Vala 实现国际上广受认可的 **Meeus 算法**。

我们将看到，Vala 不仅能胜任复杂的数学运算，其现代化的语言特性、清晰的面向对象结构以及与 GLib 等底层库的无缝集成，都能让我们的科学计算代码变得既高效又易于维护。

这篇文章的算法实现，被用于笔者在[上一篇教程](https://wszqkzqk.github.io/2025/08/07/GTK-Vala-Tutorial-3)中介绍的 [GTK4 太阳高度角计算器](https://github.com/wszqkzqk/FunValaGtkExamples/blob/master/solarangleadw.vala) 中，但本文的重点并非 GUI 应用本身，而是**算法的理论、实现细节及其在 Vala 语言中的最佳实践**。

## 算法背景：为何选择 Meeus 算法？

计算太阳位置存在不同层次的解法，复杂度与精度各不相同：

*  **经验公式**：例如一些基于傅里叶级数拟合的简化模型（如 Spencer 的算法）。这类公式易于实现，对于一般性应用（如常规的日照模拟）精度足够，但它们是观测数据的近似，缺乏坚实的物理基础。
*  **高精度天文历**：由专业天文机构（如 NASA JPL）发布的星历表，如 DE430、DE440 等。它们提供了最精确的行星位置数据，但通常体积庞大，使用和解析也相对复杂。
*  **解析理论（Analytical Theory）**：介于两者之间，基于天体力学模型，但通过一系列数学简化，得到一组可以直接计算的解析公式。**Meeus 算法**正是此类方法的杰出代表，它由比利时气象学家兼天文学家 [Jean Meeus](https://en.wikipedia.org/wiki/Jean_Meeus) 在其著作《天文算法》（*Astronomical Algorithms*）中推广，能在不依赖大型星历表的情况下，达到非常高的精度（通常优于 1 角分），是业余天文学和许多科学应用中的“黄金标准”。

本文选择 Meeus 算法，旨在展示如何在 Vala 中处理一个兼具理论深度和实现复杂度的真实科学计算问题。

## Meeus 算法的 Vala 实现：分步详解

本文后续展示的算法实现，主要参考了 Paul Schlyter 先生和 J. Giesen 先生总结的[高精度算法页面](http://www.jgiesen.de/elevaz/basics/meeus.htm)。值得一提的是，为了便于在代码中直接使用以“天”为单位的儒略日，笔者对原始公式进行了一定的恒等变形。

原始公式通常基于**儒略世纪数**（Julian Centuries, `T`）作为时间变量，其形式为 `C₀ + C₁T + C₂T² + ...`。而本文的实现则统一使用**儒略天数**（Julian Days, `d`）作为变量。由于 1 儒略世纪 = 36525 天，笔者通过将原始公式中的 n 阶项系数 $C_n$ 除以 $36525^n$，将其转化为了适用于天数 `d` 的等价形式。后续的时角等计算也做了类似的等价转换。

这种转换不影响计算的精度，但使得代码逻辑与以“天”为单位的 `GLib.Date` 时间体系更为统一。

我们将按照 Meeus 算法的流程，将天文学概念逐一转化为 Vala 代码。

### 时间基准：儒略日与 J2000.0 历元

天文学计算需要一个连续、无歧义的时间标尺。**儒略日 (Julian Date, JD)** 就是为此而生。我们通过 GLib 的 `GLib.Date` 可以轻松获取：

```vala
var date = new GLib.Date ();
date.set_dmy (day, month, year);
var julian_date = (double) date.get_julian ();
```

为了简化公式，天文学家选择了一个标准参考时刻，即 **J2000.0 历元**，对应于 2000 年 1 月 1 日国际原子时 12:00。我们的计算将以从这个历元开始的天数 `d` 为基础。

这里减去 `730120.5` 即可将当天 00:00 UTC 转换为从 J2000.0 历元起算的天数。

```vala
// 从 J2000.0 历元起算的天数
double base_days_from_epoch = julian_date - 730120.5;
```

### 黄赤交角 (Obliquity of the Ecliptic, ε)

地球自转轴相对于其公转轨道（黄道）的倾角。它随时间微小变化，Meeus 给出了一个拟合的多项式：

$$ 
\epsilon (\text{deg}) = 23.439291111 - 0.0000003560347 d - 1.2285 \times 10^{-16} d^2 + 1.0335 \times 10^{-20} d^3 
$$ 

其中 `d` 是从 J2000.0 起算的天数。在 Vala 中实现为：

```vala
double base_days_sq = base_days_from_epoch * base_days_from_epoch;
double base_days_cb = base_days_sq * base_days_from_epoch;
double obliquity_deg = 23.439291111 - 3.560347e-7 * base_days_from_epoch - 1.2285e-16 * base_days_sq + 1.0335e-20 * base_days_cb;
double obliquity_sin = Math.sin (obliquity_deg * DEG2RAD);
double obliquity_cos = Math.cos (obliquity_deg * DEG2RAD);
```

### 轨道参数

**平黄经 (Mean Longitude, L)** 和 **平近点角 (Mean Anomaly, M)** 是两个重要的轨道参数。在深入公式之前，有必要先理解这两个核心概念的物理意义。

**平黄经 (Mean Longitude, L)** 是想象一个“平均太阳”——它在一个完美的圆形轨道上，以恒定的速度运动，其周期与地球绕太阳的真实周期相同。平黄经就是这个“平均太阳”在黄道（地球公转轨道平面）上的角度位置。它的起点是春分点，因此平黄经为 0° 意味着“平均太阳”正处于春分点。

**平近点角 (Mean Anomaly, M)** 则描述了这个“平均太阳”在其理想化圆形轨道上，从“近地点”（轨道上离地球最近的点）出发所转过的角度。它是一个从 0° 到 360° 均匀增加的角度，反映了时间的流逝。当 M 为 0° 时，意味着“平均太阳”在近地点；当 M 为 180° 时，它在远地点。

简而言之，L 告诉我们“平均太阳”在天空背景（黄道）上的位置，而 M 则告诉我们它在其自身轨道路径上的进展。这两个“平”的、理想化的角度，是计算真实太阳位置（“真黄经”和“真近点角”）的起点。真实的太阳因为轨道是椭圆的（开普勒第一定律）且速度是变化的（开普勒第二定律），其位置会围绕着这个“平均太阳”前后摆动。

这些值描述了在一个理想化的匀速圆周轨道上太阳的位置。

$$ 
L (\text{deg}) = 280.46645 + 0.98564736 d + 2.2727 \times 10^{-13} d^2 
$$ 

$$ 
M (\text{deg}) = 357.52910 + 0.985600282 d - 1.1686 \times 10^{-13} d^2 - 9.85 \times 10^{-21} d^3 
$$ 

Vala 实现（注意 `fmod` 用于将角度归一化到 0-360 度）：

```vala
double days_from_epoch_sq = days_from_epoch * days_from_epoch;
double days_from_epoch_cb = days_from_epoch_sq * days_from_epoch;

double mean_anomaly_deg = 357.52910 + 0.985600282 * days_from_epoch - 1.1686e-13 * days_from_epoch_sq - 9.85e-21 * days_from_epoch_cb;
mean_anomaly_deg = Math.fmod (mean_anomaly_deg, 360.0);
if (mean_anomaly_deg < 0) { mean_anomaly_deg += 360.0; }

double mean_longitude_deg = 280.46645 + 0.98564736 * days_from_epoch + 2.2727e-13 * days_from_epoch_sq;
mean_longitude_deg = Math.fmod (mean_longitude_deg, 360.0);
if (mean_longitude_deg < 0) { mean_longitude_deg += 360.0; }
```

### 中心差与真黄经 (Equation of Center and True Longitude, λ)

为了从“平”位置得到“真”位置，需要加上由地球轨道椭圆形引起的修正，即**中心差**。Meeus 算法给出了一个包含三项正弦修正的简化形式：

$$ 
C (\text{deg}) = (1.914600 - 0.00000013188 d - 1.049 \times 10^{-14} d^2) \sin(M) + (0.019993 - 0.0000000027652 d) \sin(2M) + 0.000290 \sin(3M) 
$$ 

**真黄经 (True Longitude, λ)** 就是平黄经加上中心差：

$$ 
\lambda = L + C 
$$ 

Vala 实现：

```vala
double ecliptic_c1 = 1.914600 - 1.3188e-7 * base_days_from_epoch - 1.049e-14 * base_days_sq;
double ecliptic_c2 = 0.019993 - 2.7652e-9 * base_days_from_epoch;
double ecliptic_c3 = 0.000290;

double mean_anomaly_rad = mean_anomaly_deg * DEG2RAD;
double ecliptic_longitude_deg = mean_longitude_deg + ecliptic_c1 * Math.sin (mean_anomaly_rad) + ecliptic_c2 * Math.sin (2.0 * mean_anomaly_rad) + ecliptic_c3 * Math.sin (3.0 * mean_anomaly_rad);
```

### 坐标转换：从黄道到赤道

有了真黄经 `λ` 和黄赤交角 `ε`，我们便可将太阳位置转换到赤道坐标系，得到**赤纬 (Declination, δ)** 和**赤经 (Right Ascension, RA)**。

$$ 
\sin(\delta) = \sin(\epsilon) \sin(\lambda) 
$$ 

$$ 
\tan(RA) = \frac{\cos(\epsilon) \sin(\lambda)}{\cos(\lambda)} \implies RA = \text{atan2}(\cos(\epsilon) \sin(\lambda), \cos(\lambda)) 
$$ 

Vala 实现：

```vala
double ecliptic_longitude_rad = ecliptic_longitude_deg * DEG2RAD;
double ecliptic_longitude_sin = Math.sin (ecliptic_longitude_rad);
double ecliptic_longitude_cos = Math.cos (ecliptic_longitude_rad);

// 计算赤纬
double declination_sin = (obliquity_sin * ecliptic_longitude_sin).clamp (-1.0, 1.0);
double declination_rad = Math.asin (declination_sin);

// 计算赤经
double right_ascension_rad = Math.atan2 (obliquity_cos * ecliptic_longitude_sin, ecliptic_longitude_cos);
```

## 应用一：计算太阳高度角

有了太阳的赤纬 `δ`，我们距离计算出它的高度角只有一步之遥。最后一步是计算出在给定的地方、给定的时刻，太阳相对于观测者的方位，这由**时角 (Hour Angle, HA)** 来描述。

### 真太阳时 (True Solar Time, TST)

我们日常使用的钟表时间是**地方标准时 (Local Standard Time)**，它基于一个时区（如 UTC+8）的中央经线，并非我们所在地的真实太阳位置。要计算时角，我们必须首先将钟表时间转换为**真太阳时 (TST)**，即由日晷测得的时间。

转换过程考虑了两个主要修正：

*   **方程时 (Equation of Time, EoT)**：我们之前计算出的、因地球轨道偏心率和黄赤交角引起的修正。
*   **经度修正**：我们的钟表时间基于时区中央经线，但太阳过中天（正午）的时刻取决于我们真实的经度。经度每向东 1°，正午就提早 4 分钟。

因此，真太阳时的计算公式为：

$$ 
TST_\text{minutes} = T_\text{local, minutes} + EoT_\text{minutes} + 4 \times \lambda_\text{lon, deg} - 60 \times TZ_\text{offset, hr} 
$$ 

其中：
*   $T_\text{local, minutes}$ 是午夜起算的本地钟表时间（分钟）。
*   $EoT_\text{minutes}$ 是我们计算出的方程时（分钟）。
*   $\lambda_\text{lon, deg}$ 是观测地的地理经度（东经为正）。
*   $TZ_\text{offset, hr}$ 是时区偏移量（例如 UTC+8 时区为 8）。

在我们的 Vala 代码中，`tst_offset` 预先计算了经度和时区带来的固定偏移，而 `eqtime_minutes` 则是动态计算的方程时。

```vala
// 方程时 (分钟)
double eot_hours = mean_time - right_ascension_hours;
double eqtime_minutes = eot_hours * 60.0;

// 固定的经度与时区偏移 (分钟)
double tst_offset = 4.0 * longitude_deg - 60.0 * timezone_offset_hrs;

// i 是午夜起算的本地时间（分钟）
double tst_minutes = i + eqtime_minutes + tst_offset;
```

### 时角 (Hour Angle, HA)

时角定义为天体距离本地子午线（正南或正北的天空弧线）的角度。天文学上通常定义正午时为 0°，下午为正，上午为负。地球每小时自转 15°，每 4 分钟自转 1°。

从以分钟计量的真太阳时到以度计量的时角，转换公式为：

$$ 
HA_\text{deg} = \frac{TST_\text{minutes}}{4} - 180 
$$ 

这里除以 4 是因为 1 分钟时间对应 0.25° 的旋转。减去 180° 是为了将计时起点从午夜（0 分钟）校正到正午（720 分钟），使得正午时 `720 / 4 - 180 = 0`。

```vala
// 将真太阳时转换为时角 (度)
double hour_angle_deg = tst_minutes / 4.0 - 180.0;
double hour_angle_rad = hour_angle_deg * DEG2RAD;
```

### 太阳高度角 (Altitude, α)

最后，我们将观测地纬度 `φ`、太阳赤纬 `δ` 和刚刚得到的时角 `HA` 代入球面三角学的基本公式，即可求得太阳高度角 `α`。

$$ 
\sin(\alpha) = \sin(\phi)\sin(\delta) + \cos(\phi)\cos(\delta)\cos(HA) 
$$ 

```vala
// 计算太阳高度角的正弦值
double elevation_sine = sin_lat * declination_sin + cos_lat * declination_cos * Math.cos (hour_angle_rad);
// 反正弦后转换为度
sun_angles[i] = Math.asin (elevation_sine.clamp (-1.0, 1.0)) * RAD2DEG;
```

至此，我们就完成了从一个日期和时间点，到其精确太阳高度角的完整计算链条。

## 应用二：计算白昼时长

计算白昼时长是这些天文参数的另一个直接应用。其核心是计算出太阳升起和落下的时刻，即太阳高度角为某个特定值（通常是-0.83°而不是0，考虑大气折射）时的时角。

### 计算方法

*  **计算高精度太阳赤纬 (δ)**：与应用一完全相同，我们首先需要得到当天精确的太阳赤纬。

*  **求解日出/日落时角 (ω₀)**：将太阳高度角公式反解，求解时角 `HA`。设 `α` 为大气折射导致的观测的地平线的修正角（一般取-0.83°，也可以按特殊需要调整），`φ` 为本地纬度，`δ` 为太阳赤纬，则日落时的时角 `ω₀` 满足：

    $$ 
    \cos(\omega_0) = \frac{\sin(\alpha) - \sin(\phi)\sin(\delta)}{\cos(\phi)\cos(\delta)} 
    $$ 

*  **处理边界情况（极昼与极夜）**：
    *   若 `cos(ω₀) ≥ 1`，意味着太阳永远在地平线以下，发生**极夜**，昼长为 0。
    *   若 `cos(ω₀) ≤ -1`，意味着太阳永远在地平线以上，发生**极昼**，昼长为 24 小时。

*  **计算总昼长**：日落时角 `ω₀` 代表了从正午到日落的时间跨度。总昼长则是日出到日落的总时长，即 `2 * ω₀`。将其从弧度转换为小时即可。

    $$ 
    t_\text{daylight} (\text{hours}) = \frac{2 \cdot \omega_0}{2\pi} \times 24 = \frac{24 \cdot \omega_0}{\pi} 
    $$ 

## Vala 在数值计算中的优势

通过这个实践，我们可以总结出 Vala 在处理此类问题时的几个优点：

*   **卓越性能**：Vala 直接编译为C代码，几乎没有额外开销。对于包含大量循环和浮点运算的数值计算任务，其性能表现与手写C代码相当，远超各类解释型语言。
*   **代码可读性与组织性**：相比C，Vala 提供了类、方法、属性等现代面向对象特性，使得我们可以将复杂的计算逻辑封装在独立的、职责清晰的函数或类中，代码结构更优，可维护性更强。
*   **类型安全**：Vala 强类型系统能在编译期捕获大量潜在错误，这对于处理多步骤、易出错的复杂科学计算流程至关重要。
*   **底层库的便捷访问**：能够零成本地调用 GLib/GObject 库是 Vala 的一大杀手锏。如本文中直接使用 `GLib.Date.get_julian()`，极大地简化了时间处理的复杂度。

## 总结

本文通过一个完整的天文算法实践，展示了 Vala 作为一门通用语言，在图形界面开发之外，同样是执行高性能数值计算的有力工具。它在提供接近C的性能的同时，赋予了我们更现代化、更安全的编程范式。

希望这次从理论到代码的深度实践，能为你提供一个在 Vala 中进行科学计算的优秀范例，并激发你使用 Vala 探索更多可能性的兴趣。

## 效果及计算代码

### 效果

笔者将上述算法应用于 GUI 程序中，结合 GTK4/Libadwaita/JSON-GLib等技术栈，制作了一个[太阳高度角计算器](https://github.com/wszqkzqk/FunValaGtkExamples/blob/master/solarangleadw.vala)和一个[白昼时长计算器](https://github.com/wszqkzqk/FunValaGtkExamples/blob/master/daylengthadw.vala)，将计算结果可视化展示。两个程序均支持浅色和深色主题，并能自动从 IP 获取地理位置，自动识别时区，还支持导出 PNG、SVG、PDF 等格式的图表，以及 CSV 数据。

| [![#~/img/GTK-examples/pku-light-solar-angle-250814.webp](/img/GTK-examples/pku-light-solar-angle-250814.webp)](/img/GTK-examples/pku-light-solar-angle-250814.webp) | [![#~/img/GTK-examples/pku-dark-solar-angle-250814.webp](/img/GTK-examples/pku-dark-solar-angle-250814.webp)](/img/GTK-examples/pku-dark-solar-angle-250814.webp) |
| :--: | :--: |
| 太阳高度角计算器（浅色模式）| 太阳高度角计算器（深色模式）|
| [![#~/img/GTK-examples/fetching-location-solarangle.webp](/img/GTK-examples/fetching-location-solarangle.webp)](/img/GTK-examples/fetching-location-solarangle.webp) | [![#~/img/GTK-examples/timezone-mismatch-solarangle.webp](/img/GTK-examples/timezone-mismatch-solarangle.webp)](/img/GTK-examples/timezone-mismatch-solarangle.webp) |
| 获取地理位置时的加载动画 | 提示与选择 |

|[![#~/img/GTK-examples/day-length-pku-light.webp](/img/GTK-examples/day-length-pku-light.webp)](/img/GTK-examples/day-length-pku-light.webp)|[![#~/img/GTK-examples/day-length-chongqing-dark.webp](/img/GTK-examples/day-length-chongqing-dark.webp)](/img/GTK-examples/day-length-chongqing-dark.webp)|
|:----:|:----:|
|白昼时长计算器（浅色模式）|白昼时长计算器（深色模式）|

### 太阳高度角计算

该函数可以用于计算一天中每分钟的太阳高度角，完整程序见 [GitHub](https://github.com/wszqkzqk/FunValaGtkExamples/blob/master/solarangleadw.vala)：

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

### 白昼时长计算

该函数用于计算某一天的白昼时长，完整程序见 [GitHub](https://github.com/wszqkzqk/FunValaGtkExamples/blob/master/daylengthadw.vala)：

```vala
    /**
     * Calculates day length using high-precision astronomical formula.
     * Based on http://www.jgiesen.de/elevaz/basics/meeus.htm
     * 
     * @param latitude_rad Latitude in radians.
     * @param julian_date GLib's Julian Date for the day (from 0001-01-01).
     * @param horizon_angle_deg Horizon angle correction in degrees (default -0.83° for atmospheric refraction).
     * @return Day length in hours.
     */
    private double calculate_day_length (double latitude_rad, double julian_date, double horizon_angle_deg = -0.83) {
        double sin_lat = Math.sin (latitude_rad);
        double cos_lat = Math.cos (latitude_rad);
        // Base days from J2000.0 epoch (GLib's Julian Date is days since 0001-01-01 12:00 UTC)
        double base_days_from_epoch = julian_date - 730120.5; // julian_date's 00:00 UTC to 2000-01-01 12:00 UTC
        // Pre-compute obliquity with higher-order terms (changes very slowly)
        double base_days_sq = base_days_from_epoch * base_days_from_epoch;
        double base_days_cb = base_days_sq * base_days_from_epoch;
        double obliquity_deg = 23.439291111 - 3.560347e-7 * base_days_from_epoch - 1.2285e-16 * base_days_sq + 1.0335e-20 * base_days_cb;
        double obliquity_sin = Math.sin (obliquity_deg * DEG2RAD);
        // Mean anomaly of the sun (degrees) with higher-order terms
        double days_from_epoch_sq = base_days_from_epoch * base_days_from_epoch;
        double days_from_epoch_cb = days_from_epoch_sq * base_days_from_epoch;
        double mean_anomaly_deg = 357.52910 + 0.985600282 * base_days_from_epoch - 1.1686e-13 * days_from_epoch_sq - 9.85e-21 * days_from_epoch_cb;
        mean_anomaly_deg = Math.fmod (mean_anomaly_deg, 360.0);
        if (mean_anomaly_deg < 0) {
            mean_anomaly_deg += 360.0;
        }
        // Mean longitude of the sun (degrees) with higher-order terms
        double mean_longitude_deg = 280.46645 + 0.98564736 * base_days_from_epoch + 2.2727e-13 * days_from_epoch_sq;
        mean_longitude_deg = Math.fmod (mean_longitude_deg, 360.0);
        if (mean_longitude_deg < 0) {
            mean_longitude_deg += 360.0;
        }
        // Ecliptic longitude corrections
        double ecliptic_c1 = 1.914600 - 1.3188e-7 * base_days_from_epoch - 1.049e-14 * base_days_sq;
        double ecliptic_c2 = 0.019993 - 2.7652e-9 * base_days_from_epoch;
        double ecliptic_c3 = 0.000290;
        // Ecliptic longitude of the sun (degrees) with higher-order corrections
        double mean_anomaly_rad = mean_anomaly_deg * DEG2RAD;
        double ecliptic_longitude_deg = mean_longitude_deg + ecliptic_c1 * Math.sin (mean_anomaly_rad) + ecliptic_c2 * Math.sin (2.0 * mean_anomaly_rad) + ecliptic_c3 * Math.sin (3.0 * mean_anomaly_rad);
        ecliptic_longitude_deg = Math.fmod (ecliptic_longitude_deg, 360.0);
        if (ecliptic_longitude_deg < 0) {
            ecliptic_longitude_deg += 360.0;
        }
        // Solar declination (radians)
        double ecliptic_longitude_rad = ecliptic_longitude_deg * DEG2RAD;
        double ecliptic_longitude_sin = Math.sin (ecliptic_longitude_rad);
        double declination_sin = (obliquity_sin * ecliptic_longitude_sin).clamp (-1.0, 1.0);
        double declination_rad = Math.asin (declination_sin.clamp (-1.0, 1.0));
        // Convert horizon angle to radians
        double horizon_angle_rad = horizon_angle_deg * DEG2RAD; 
        // Calculate hour angle at sunrise/sunset with horizon correction
        double cos_hour_angle = (Math.sin (horizon_angle_rad) - sin_lat * declination_sin) 
            / (cos_lat * Math.cos (declination_rad));
        if (cos_hour_angle.is_nan ()) {
            // Invalid value, return 12.0 hours
            return 12.0;
        } else if (cos_hour_angle >= 1.0) {
            // Polar night (sun never rises)
            return 0.0;
        } else if (cos_hour_angle <= -1.0) {
            // Polar day (sun never sets)
            return 24.0;
        }
        // Hour angle in radians
        double hour_angle_rad = Math.acos (cos_hour_angle);
        // Day length in hours (hour angle is in radians, convert to hours)
        return (2.0 * hour_angle_rad * 24.0) / (2.0 * Math.PI);
    }

    /**
     * Updates plot data for all days in the selected year.
     */
    private void update_plot_data () {
        int total_days = days_in_year (selected_year);
        day_lengths = new double[total_days];
        
        double latitude_rad = latitude * DEG2RAD;

        // Get Julian Date for January 1st of the selected year
        var date = Date ();
        date.set_dmy (1, 1, (DateYear) selected_year);
        uint base_julian_date = date.get_julian ();

        for (int day = 0; day < total_days; day += 1) {
            day_lengths[day] = calculate_day_length (
                latitude_rad, (double) (base_julian_date + day), horizon_angle
            );
        }

        // Clear click point when data updates
        has_click_point = false;
        click_info_label.label = "Click on chart to view data\n";
    }
```

## 附录：算法精度对比验证

为了全面评估本文所采用的 Meeus 算法的精度，并将其与其他常见算法进行横向对比，笔者编写了一个 Python 验证脚本。该脚本将以下三种算法的计算结果与业界公认的高精度方法——`astropy` 库的计算结果进行逐小时比较：

1.  **Meeus 算法 (本文实现)**：即 `generate_sun_angles_meeus`，是本文 Vala 代码的 Python 复现版。
2.  **傅里叶级数近似算法 (旧版实现)**：即 `generate_sun_angles_fourier`，这是笔者早期使用的一种基于傅里叶级数拟合的简化算法。
3.  **维基百科简化公式**：即 `generate_sun_angles_wikipedia`，实现了维基百科上提供的简化版太阳赤纬和方程时公式。

通过计算每种算法结果与 `astropy` 基准值之间的均方根误差 (Root Mean Square Deviation, RMSD)，我们可以量化它们的精度差异。

### 旧版傅里叶级数近似算法

这是笔者早期使用的 Vala 函数，它基于一个傅里叶级数来近似太阳赤纬和方程时。这种方法实现相对简单，但精度有限，尤其是在长期时间跨度上。

```vala
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
            // -1 to avoid discontinuity at year start (Dec 31 to Jan 1)
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
            cos_phi = cos_phi.clamp (-1.0, 1.0);
            // Zenith angle phi (rad)
            double phi_rad = Math.acos (cos_phi);

            // Solar elevation alpha = 90° - phi, convert to degrees
            double solar_elevation_rad = Math.PI / 2.0 - phi_rad;
            sun_angles[i] = solar_elevation_rad * RAD2DEG;
        }
    }
```

### 维基百科简化公式

维基百科提供了一组更为简化的公式，用于计算太阳赤纬 (δ) 和方程时 (EoT)。

**赤纬 (δ):**
$$
\delta_\odot = \arcsin \left [ \sin \left ( -23.44^\circ \right ) \cdot \cos \left ( \frac{360^\circ}{365.24} \left (N + 10 \right ) + \frac{360^\circ}{\pi} \cdot 0.0167 \sin \left ( \frac{360^\circ}{365.24} \left ( N - 2 \right ) \right ) \right ) \right ]
$$

带入数据，简化可得：

$$
\delta_\odot = - \arcsin \left [ 0.39779 \cos \left ( 0.98565^\circ \left (N + 10 \right ) + 1.914^\circ \sin \left ( 0.98565^\circ \left ( N - 2 \right ) \right ) \right ) \right ]
$$

其中，N是天数，从1月1日的午夜（0点）开始计算（即序数日期的天数部分减1），可以包含小数以调整当天的具体时间。

**方程时 (EoT):**
$$
\Delta t_{ey} =  -7.659\sin(D) + 9.863\sin \left(2D + 3.5932 \right) \quad [\text{minutes}]
$$

其中：

$$
D = 6.24004077 + 0.01720197(365.25(y-2000) + d)
$$

其中，d是从当年1月1日开始计算的天数，y是当前年份。

### Python 验证脚本

以下是用于生成对比数据的完整 Python 脚本。它依赖 `numpy` 和 `astropy` 库。

```python
#!/usr/bin/env python3

import numpy as np
from astropy.coordinates import EarthLocation, AltAz, get_sun
from astropy.time import Time
import datetime
import calendar

DEG2RAD = np.pi / 180.0
RAD2DEG = 180.0 / np.pi

LOCATIONS = {
    "Beijing":      {"lat": 39.9075, "lon": 116.3972, "tz": 8.0},
    "Chongqing":    {"lat": 29.5628, "lon": 106.5528, "tz": 8.0},
    "Singapore":    {"lat": 1.3521,  "lon": 103.8198, "tz": 8.0},
    "Sydney":       {"lat": -33.8688, "lon": 151.2093, "tz": 10.0},
    "Stockholm":    {"lat": 59.3293, "lon": 18.0686,  "tz": 1.0},
    "South Pole":   {"lat": -90.0,   "lon": 0.0,      "tz": 0.0}
}

def astropy_sun_elevations(year, month, day, latitude_deg, longitude_deg, timezone_offset_hrs):
    """
    Calculates the ground truth solar elevation angles using Astropy (the gold standard).
    """
    location = EarthLocation(lat=latitude_deg, lon=longitude_deg)
    angles = []
    for local_hour in range(24):
        local_dt = datetime.datetime(year, month, day, local_hour, 0, 0)
        utc_dt = local_dt - datetime.timedelta(hours=timezone_offset_hrs)
        time_astropy = Time(utc_dt)
        altaz_frame = AltAz(obstime=time_astropy, location=location)
        sun_altaz = get_sun(time_astropy).transform_to(altaz_frame)
        angles.append(sun_altaz.alt.degree)
    return np.array(angles)

def generate_sun_angles_meeus(latitude_deg, longitude_deg, timezone_offset_hrs, year, month, day):
    """
    Method 1: The high-precision algorithm from your new Vala program (based on Jean Meeus' method).
    """
    julian_date = float(datetime.date(year, month, day).toordinal())
    
    latitude_rad = latitude_deg * DEG2RAD
    sin_lat = np.sin(latitude_rad)
    cos_lat = np.cos(latitude_rad)
    
    base_days_from_epoch = julian_date - 730120.5
    
    base_days_sq = base_days_from_epoch ** 2
    base_days_cb = base_days_sq * base_days_from_epoch
    obliquity_deg = 23.439291111 - 3.560347e-7 * base_days_from_epoch - 1.2285e-16 * base_days_sq + 1.0335e-20 * base_days_cb
    obliquity_sin = np.sin(obliquity_deg * DEG2RAD)
    obliquity_cos = np.cos(obliquity_deg * DEG2RAD)
    
    ecliptic_c1 = 1.914600 - 1.3188e-7 * base_days_from_epoch - 1.049e-14 * base_days_sq
    ecliptic_c2 = 0.019993 - 2.7652e-9 * base_days_from_epoch
    ecliptic_c3 = 0.000290
    
    tst_offset = 4.0 * longitude_deg - 60.0 * timezone_offset_hrs
    
    angles = []
    for local_hour in range(24):
        i = local_hour * 60
        time_offset_days = (i / 60.0 - timezone_offset_hrs) / 24.0
        days_from_epoch = base_days_from_epoch + time_offset_days
        days_from_epoch_sq = days_from_epoch ** 2
        days_from_epoch_cb = days_from_epoch_sq * days_from_epoch
        
        mean_anomaly_deg = 357.52910 + 0.985600282 * days_from_epoch - 1.1686e-13 * days_from_epoch_sq - 9.85e-21 * days_from_epoch_cb
        mean_anomaly_deg = np.fmod(mean_anomaly_deg, 360.0)
        
        mean_longitude_deg = 280.46645 + 0.98564736 * days_from_epoch + 2.2727e-13 * days_from_epoch_sq
        mean_longitude_deg = np.fmod(mean_longitude_deg, 360.0)
        
        mean_anomaly_rad = mean_anomaly_deg * DEG2RAD
        ecliptic_longitude_deg = (mean_longitude_deg +
                                  ecliptic_c1 * np.sin(mean_anomaly_rad) +
                                  ecliptic_c2 * np.sin(2 * mean_anomaly_rad) +
                                  ecliptic_c3 * np.sin(3 * mean_anomaly_rad))
        
        ecliptic_longitude_rad = ecliptic_longitude_deg * DEG2RAD
        declination_sin = np.clip(obliquity_sin * np.sin(ecliptic_longitude_rad), -1.0, 1.0)
        declination_cos = np.sqrt(1.0 - declination_sin ** 2)
        
        right_ascension_rad = np.arctan2(obliquity_cos * np.sin(ecliptic_longitude_rad), np.cos(ecliptic_longitude_rad))
        right_ascension_hours = (right_ascension_rad * RAD2DEG) / 15.0
        
        mean_time = np.fmod(mean_longitude_deg / 15.0, 24.0)
        delta_ra = right_ascension_hours - mean_time
        if delta_ra > 12.0: right_ascension_hours -= 24.0
        elif delta_ra < -12.0: right_ascension_hours += 24.0
        
        eqtime_minutes = (mean_time - right_ascension_hours) * 60.0
        
        tst_minutes = i + eqtime_minutes + tst_offset
        hour_angle_rad = (tst_minutes / 4.0 - 180.0) * DEG2RAD
        
        elevation_sine = sin_lat * declination_sin + cos_lat * declination_cos * np.cos(hour_angle_rad)
        elevation = np.arcsin(np.clip(elevation_sine, -1.0, 1.0)) * RAD2DEG
        angles.append(elevation)
    
    return np.array(angles)

def generate_sun_angles_fourier(latitude_deg, longitude_deg, timezone_offset_hrs, year, month, day):
    """
    Method 2: The algorithm from your old Vala program (based on a Fourier series approximation).
    """
    latitude_rad = latitude_deg * DEG2RAD
    sin_lat = np.sin(latitude_rad)
    cos_lat = np.cos(latitude_rad)

    dt = datetime.date(year, month, day)
    day_of_year = dt.timetuple().tm_yday
    days_in_year = 366.0 if calendar.isleap(year) else 365.0
    
    angles = []
    for local_hour in range(24):
        i = local_hour * 60
        
        fractional_day_component = day_of_year - 1 + (i / 1440.0)
        gamma_rad = (2.0 * np.pi / days_in_year) * fractional_day_component

        decl_rad = 0.006918 \
            - 0.399912 * np.cos(gamma_rad) \
            + 0.070257 * np.sin(gamma_rad) \
            - 0.006758 * np.cos(2.0 * gamma_rad) \
            + 0.000907 * np.sin(2.0 * gamma_rad) \
            - 0.002697 * np.cos(3.0 * gamma_rad) \
            + 0.001480 * np.sin(3.0 * gamma_rad)

        eqtime_minutes = 229.18 * (0.000075 \
            + 0.001868 * np.cos(gamma_rad) \
            - 0.032077 * np.sin(gamma_rad) \
            - 0.014615 * np.cos(2.0 * gamma_rad) \
            - 0.040849 * np.sin(2.0 * gamma_rad))

        tst_minutes = i + eqtime_minutes + 4.0 * longitude_deg - 60.0 * timezone_offset_hrs
        ha_rad = (tst_minutes / 4.0 - 180.0) * DEG2RAD

        elevation_sine = sin_lat * np.sin(decl_rad) + cos_lat * np.cos(decl_rad) * np.cos(ha_rad)
        elevation = np.arcsin(np.clip(elevation_sine, -1.0, 1.0)) * RAD2DEG
        angles.append(elevation)
        
    return np.array(angles)

def generate_sun_angles_wikipedia(latitude_deg, longitude_deg, timezone_offset_hrs, year, month, day):
    """
    Method 3: The simplified formula provided by Wikipedia.
    """
    latitude_rad = latitude_deg * DEG2RAD
    sin_lat = np.sin(latitude_rad)
    cos_lat = np.cos(latitude_rad)

    dt = datetime.date(year, month, day)
    day_of_year = dt.timetuple().tm_yday
    
    angles = []
    for local_hour in range(24):
        utc_hour = local_hour - timezone_offset_hrs
        N = day_of_year - 1 + utc_hour / 24.0

        arg1_deg = 0.98565 * (N + 10)
        arg2_deg = 0.98565 * (N - 2)
        cos_arg_deg = arg1_deg + 1.914 * np.sin(arg2_deg * DEG2RAD)
        decl_rad = -np.arcsin(0.39779 * np.cos(cos_arg_deg * DEG2RAD))

        d_eot = day_of_year - 1
        D_rad = 6.24004077 + 0.01720197 * (365.25 * (year - 2000) + d_eot)
        eqtime_minutes = -7.659 * np.sin(D_rad) + 9.863 * np.sin(2 * D_rad + 3.5932)
        
        i = local_hour * 60
        tst_minutes = i + eqtime_minutes + 4.0 * longitude_deg - 60.0 * timezone_offset_hrs
        ha_rad = (tst_minutes / 4.0 - 180.0) * DEG2RAD
        
        elevation_sine = sin_lat * np.sin(decl_rad) + cos_lat * np.cos(decl_rad) * np.cos(ha_rad)
        elevation = np.arcsin(np.clip(elevation_sine, -1.0, 1.0)) * RAD2DEG
        angles.append(elevation)
        
    return np.array(angles)

def main():
    """
    Runs the validation test for all configured locations and years,
    and prints a detailed monthly and average RMSD report.
    """
    years = [1949, 1976, 1989, 2003, 2008, 2020, 2025, 2035, 2050]
    
    for location_name, params in LOCATIONS.items():
        lat, lon, tz = params["lat"], params["lon"], params["tz"]
        
        print(f"\n={'='*70}")
        print(f"Validation Results for: {location_name}")
        print(f"(Lat: {lat}, Lon: {lon}, TZ: UTC{tz:+.1f})")
        print(f"={'='*70}")
        
        for year in years:
            print(f"\n--- Year: {year} ---")
            print(f"| {'Month':<7} | {'Meeus RMSD':<15} | {'Fourier RMSD':<15} | {'Wikipedia RMSD':<15} |")
            print(f"|{'-'*9}|{'-'*17}|{'-'*17}|{'-'*17}|")
            
            monthly_rmsd_meeus = []
            monthly_rmsd_fourier = []
            monthly_rmsd_wikipedia = []
            
            for month in range(1, 13):
                day = 15
                
                astro_angles = astropy_sun_elevations(year, month, day, lat, lon, tz)
                meeus_angles = generate_sun_angles_meeus(lat, lon, tz, year, month, day)
                fourier_angles = generate_sun_angles_fourier(lat, lon, tz, year, month, day)
                wikipedia_angles = generate_sun_angles_wikipedia(lat, lon, tz, year, month, day)
                
                rmsd_meeus = np.sqrt(np.mean((meeus_angles - astro_angles) ** 2))
                rmsd_fourier = np.sqrt(np.mean((fourier_angles - astro_angles) ** 2))
                rmsd_wikipedia = np.sqrt(np.mean((wikipedia_angles - astro_angles) ** 2))
                
                monthly_rmsd_meeus.append(rmsd_meeus)
                monthly_rmsd_fourier.append(rmsd_fourier)
                monthly_rmsd_wikipedia.append(rmsd_wikipedia)
                
                month_name = datetime.date(year, month, 1).strftime('%b')
                print(f"| {month_name:<7} | {rmsd_meeus:<15.4f} | {rmsd_fourier:<15.4f} | {rmsd_wikipedia:<15.4f} |")
            
            annual_avg_rmsd_meeus = np.mean(monthly_rmsd_meeus)
            annual_avg_rmsd_fourier = np.mean(monthly_rmsd_fourier)
            annual_avg_rmsd_wikipedia = np.mean(monthly_rmsd_wikipedia)
            
            print(f"|{'-'*9}|{'-'*17}|{'-'*17}|{'-'*17}|")
            print(f"| {'Average':<7} | {annual_avg_rmsd_meeus:<15.4f} | {annual_avg_rmsd_fourier:<15.4f} | {annual_avg_rmsd_wikipedia:<15.4f} |")

if __name__ == "__main__":
    main()
```

### 验证结果与分析

#### 综合对比

首先从海量数据中提炼出核心指标。

| 性能指标 (单位: 度)    | Meeus 算法 | 傅里叶级数算法 | 维基百科算法 |
|------------------------|----------------|---------------------|-------------------|
| 最佳表现 (最小 RMSD) | **0.0001**        | 0.0010             | 0.0001           |
| 最差表现 (最大 RMSD) | **0.0083**        | 0.3326             | 0.4171           |
| 全场景平均 RMSD    | **0.0034**        | 0.0829             | 0.1448           |
| 误差数量级         | **10⁻³**          | 10⁻¹ ~ 10⁻²        | 10⁻¹ ~ 10⁻²     |
| 相对平均误差       | **1x**            | 24x                | 43x              |

* Meeus 算法的精度与其他两个算法之间存在**数量级**的差距。其平均误差比傅里叶算法小 **24 倍**，比维基百科算法小 **43 倍**。
* Meeus 算法的最差表现 (`0.0083°`) 依然比另外两个算法的**平均表现**好得多。傅里叶和维基百科算法的误差波动范围极大，最差情况下的误差高达 0.3-0.4 度，这几乎是太阳的视直径大小。

#### 地理位置对比

| 地点       | Meeus平均RMSD | Fourier平均RMSD | Wikipedia平均RMSD |
|------------|-----------|-------------|---------------|
| Beijing   | 0.0034   | 0.0741     | 0.1273       |
| Chongqing | 0.0034   | 0.0701     | 0.1196       |
| Singapore | 0.0034   | 0.0670     | 0.1022       |
| Sydney    | 0.0034   | 0.0693     | 0.1130       |
| Stockholm | 0.0030   | 0.0959     | 0.1343       |
| South Pole| 0.0029   | 0.1192     | 0.1414       |
| **总体平均**| **0.0033** | **0.0823** | **0.1230**  |

Meeus 算法具有完美的地理普适性，从赤道到极点都保持极高精度。而傅里叶和维基百科算法是“中低纬度特化”的粗略模型，纬度越高，其模型缺陷暴露得越彻底。

#### 年份对比

通过对比1949年和2050年的数据，我们可以评估算法是否考虑了地球轨道参数的长期变化。

| 方法         | 1949年平均RMSD (°) | 2050年平均RMSD (°) | 误差变化趋势与结论                             |
|--------------|---------------------|---------------------|------------------------------------------------|
| Meeus        | 0.0051              | 0.0036              | 精度在百年尺度上保持稳定。                     |
| 傅里叶级数   | 0.0443              | 0.1080              | 误差在百年间增长超过一倍（增长144%）。         |
| 维基百科     | 0.1109              | 0.2146              | 误差在百年间几乎翻倍（增长94%）。              |

Meeus 算法包含了对地球轨道参数长期变化的修正项，因此其精度在很长的时间跨度内都是可靠的。而傅里叶和维基百科算法是基于特定历元的经验公式，其参数是固定的，因此离它们被拟合的年代越远，误差就越大。它们不具备长期预测能力。

#### 月份/季节维度分析

观察任意一年内12个月的数据波动：

* Meeus: 月度RMSD波动非常小。
* Fourier/Wikipedia: 月度RMSD波动极大。例如北京2025年，傅里叶算法的误差从0.0412°（12月）剧增到0.1674°（3月），相差4倍。这表明它们的模型未能精确模拟地球在椭圆轨道上运动速度的变化，导致均时差和太阳赤纬的季节性变化计算不准。

Meeus 算法精确地模拟了地球公转的真实物理过程，而简化模型只是拟合了大致的年度周期，忽略了重要的季节性非线性变化。

#### 结论

Meeus 算法是一个基于天体力学的物理模型。它从儒略日出发，计算地球在J2000.0历元下的轨道根数，并加入长期修正项，然后求解太阳的平近点角、真近点角、黄经等，最后通过坐标变换得到地平坐标。每一步都有物理意义，是在基本参数基础上加入了多项修正以提高精度。

而是 Spencer 的傅里叶级数算法是一个基于信号处理的数学拟合模型。它将太阳赤纬和时差这两个年度周期性变化的数据，用傅里叶级数（一系列正弦和余弦函数的和）来进行近似。它不关心背后的物理原因，只求在当时的结果上“长得像”。这种方法拟合的精度有限，且不具备更远时间的外推能力。

维基百科介绍的算法则是从高度简化的物理模型导出的公式。它将复杂的物理模型简化为几个关键项和一组简单的参数。这种公式通常是为了在特定条件下（如现代、中纬度）提供一个快速估算，但牺牲了普适性和精度。
