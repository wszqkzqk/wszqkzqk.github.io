---
layout:     post
title:      Vala 数值计算实践：高精度月球位置算法
subtitle:   探索月球运动的复杂性——计算月球位置与相位的 Vala 实现
date:       2025-11-21
author:     wszqkzqk
header-img: img/Vala_Logo.webp
catalog:    true
tags:       开源软件 GTK Vala 数值计算
---

## 前言

在[之前的文章](https://wszqkzqk.github.io/2025/10/08/GTK-Vala-Tutorial-Advanced-Solar-Calculation/)中，我们探讨了如何使用 Vala 语言结合 Meeus 算法来计算太阳的位置。太阳的视运动相对规律，将其视为遵循开普勒定律的二体问题（地球绕太阳公转）并辅以少量长期摄动修正项，即可获得相当高的精度。

然而，当我们把目光转向夜空中的月亮时，情况就变得复杂得多。月球的运动是著名的“三体问题”的一个实例。月球不仅受到地球引力的主导，还受到太阳引力的强烈摄动。这导致月球的轨道不是一个简单的椭圆，而是一个不断变形、进动、摆动的复杂轨迹。

本文将继续我们的 Vala 数值计算之旅，以**月球位置计算**为例，展示如何处理比太阳算法更复杂的数学模型，并实现一个包含视差修正和月相计算的完整月球计算器。

本文的代码实现可在 [GitHub 对应仓库](https://github.com/wszqkzqk/FunValaGtkExamples/blob/master/lunarcalc.vala)中获取也可以在[文末](#完整代码实现)查看。

## 界面设计与效果展示

本应用的界面设计延续了[之前的教程（GTK4/Vala 教程：构建现代桌面应用）](https://wszqkzqk.github.io/2025/08/07/GTK-Vala-Tutorial-3/)中“太阳计算器”的风格，采用了现代化的 LibAdwaita 库构建。

界面依然保持了清晰的双栏布局：左侧为参数设置与控制面板，右侧为自定义绘制的图表区域。我们同样支持了深色模式的自动适配与手动切换，以及平滑的加载动画。关于界面构建的具体细节（如 `Adw.ToolbarView`、`Adw.PreferencesGroup` 的使用，以及 Cairo 绘图的实现），请读者参考笔者[之前的博客](https://wszqkzqk.github.io/2025/08/07/GTK-Vala-Tutorial-3/)，本文不再赘述，仅在此简单展示效果截图：

|[![#~/img/GTK-examples/lunar-pku-light.webp](/img/GTK-examples/lunar-pku-light.webp)](/img/GTK-examples/lunar-pku-light.webp)|[![#~/img/GTK-examples/lunar-pku-dark.webp](/img/GTK-examples/lunar-pku-dark.webp)](/img/GTK-examples/lunar-pku-dark.webp)|
|:----:|:----:|
|浅色模式效果|深色模式效果|

## 算法背景：月球运动的复杂性

与太阳（实际上是地球轨道）相比，月球位置的计算难度要高很多。为了提高精度，我们需要考虑更多的周期项。

月球运动本质上是一个**限制性三体问题（Restricted Three-Body Problem）**。在这个模型中，地球和太阳是两个主要的引力源（尽管太阳距离远，但质量巨大），而月球是一个质量相对可忽略的第三体。月球不仅受到地球引力的主导（使其绕地球公转），还受到太阳引力的强烈摄动。这些复杂的引力相互作用，可以分为两类主要效应：

*   **短周期摄动**：这些摄动项与日、地、月三者的瞬时相对位置紧密相关，周期通常在一个月或一年左右。主要包括：
    *   **出差 (Evection)**：太阳引力通过摄动月球轨道近地点位置，引起偏心率与近点角周期性变化。朔望时，太阳与地月共线，引力耦合最强，向轨道注入能量使偏心率增大；上下弦时，太阳引力垂直于地月连线，耦合效应反转并从轨道提取能量，使偏心率减小。这种双向拉锯导致近地点在椭圆轨道内进动，周期约31.8天（近点月与朔望月的拍频周期，即两者相位滑移一周所需时间），振幅可达1.274°，是太阳摄动中最大的短周期项。
    *   **二均差 (Variation)**：由太阳对月球的直接引力梯度效应引起。在朔（新月）时，太阳与月球同向，拉月球远离地球，使其角速度增加；在望（满月）时，太阳拉月球向地球，使减速；在上下弦月时，太阳垂直于地月连线，效应最小。周期约为朔望月的二分之一（约14.8天）。
    *   **周年差 (Annual Equation)**：由地球绕太阳公转轨道偏心率引起的月球运动周期性变化，地月系在椭圆轨道上绕日运行，与太阳的距离在近日点和远日点之间变化，导致太阳对月球轨道的潮汐摄动发生周期性变化，周期为一个近点年。

*   **轨道自身的周期性演化**：除了短周期项，月球轨道自身的几何形态也在发生着周期性的、影响更为深远的变化。这些变化描述了月球轨道的平均状态是如何“漂移”的：
    *   **轨道倾角 (Orbital Inclination)**：月球的公转轨道平面（白道面）与地球的公转轨道平面（黄道面）并不重合，而是存在一个约 **5.145°** 的夹角。这个倾角是月球能够出现在黄道南北两侧的原因，是计算**月球黄纬**的首要参数。若无此倾角，月球将永远在黄道上运行，每个朔望月都会发生日食和月食。
    *   **交点退行 (Regression of the Nodes)**：月球轨道与黄道的两个交点——升交点和降交点——并非固定不动。在太阳引力的作用下，这两个交点会沿着黄道向西（与月球公转方向相反）缓慢移动，每 **18.6 年**完成一周的退行。这一现象深刻影响着月球黄纬的计算（通过纬度参数 $F$ 体现），并且是预测日食和月食发生的关键周期，也是“沙罗周期”等概念的根本原因。
    *   **近地点进动 (Apsidal Precession)**：月球轨道的近地点和远地点连成的线（拱线）也非固定。它会沿着月球的公转方向向东缓慢旋转，每 **8.85 年**完成一周的进动。这意味着月球从一个近地点出发，再次回到近地点所需的时间（近点月）比它完成 360° 公转的时间（恒星月）要长。这一效应是修正月球**平近点角 ($M'$)** 和计算真实距离所必需的。

综合上述各类效应，月球的真实运动变得异常复杂。

在太阳算法中，我们主要关注平黄经 $L$ 和平近点角 $M$。而在月球算法中，我们需要引入五个基本参数来描述月球和太阳的相对位置及轨道状态，并通过叠加一系列三角级数项（即上述摄动效应的数学表达）来修正月球的平位置。

此外，由于月球距离地球非常近（平均约 38 万公里），**地心视差（Geocentric Parallax）** 的影响变得极大。对于太阳，视差仅约 8.8 角秒，通常可以忽略；而对于月球，视差可达 1 度左右（即两个满月的直径），如果不进行视差修正，计算出的地平高度将出现巨大误差。

本文采用的算法基于 Jean Meeus 的《天文算法》中的简化模型，它本质上是 ELP-2000/82 理论的一个截断版本，保留了对精度影响最大的项。

## 实现详解

### 时间基准与基本参数

首先，与太阳计算一样，我们需要计算从 J2000.0 历元（2000年1月1日 12:00 TT）起算的儒略世纪数 $T$。在 Vala 中，我们利用 GLib 提供的 `GLib.Date` 类来方便地处理日期，并将其转换为儒略日。

```vala
// 将 GLib.Date 转换为儒略日
var date = Date ();
date.set_dmy ((DateDay) selected_date.get_day_of_month (),
              selected_date.get_month (),
              (DateYear) selected_date.get_year ());
var julian_date = (double) date.get_julian ();

// 计算从 J2000.0 历元起算的天数和世纪数
double base_days_since_j2000 = julian_date - 730120.5;
double local_days_since_j2000 = base_days_since_j2000 + (i / 60.0 - timezone_offset_hrs) / 24.0;
double centuries_since_j2000 = local_days_since_j2000 / 36525.0;
```

接下来，我们需要计算月球运动的五个基本要素。这些公式是基于长期观测拟合的多项式，它们描述了月球和太阳在黄道上的平均位置及其轨道特征。在限制性三体问题中，这些参数是计算摄动项的基础变量：

*  **月球平黄经 ($L'$)**：月球在黄道上的平均位置。

$$
L' = 218.3164477 + 481267.88123421 T - 0.0015786 T^2 + T^3 / 538841.0 - T^4 / 65194000.0
$$

*  **月球平距角 ($D$)**：月球与太阳的平均角距离（决定了平均月相）。$D$ 决定了月球相对于“日-地”连线的位置。由于太阳的引力摄动主要取决于月球相对于太阳的方向（例如在朔望时摄动最大，上下弦时最小），$D$ 是计算**出差 (Evection)** 和 **二均差 (Variation)** 等主要摄动项的关键参数。

$$
D = 297.8501921 + 445267.1114034 T - 0.0018819 T^2 + T^3 / 545868.0 - T^4 / 113065000.0
$$

*  **太阳平近点角 ($M$)**：同太阳算法，描述太阳在地球轨道上的位置。$M$ 反映了地球到太阳距离的变化。由于引力与距离的平方成反比，当地球（月球系统）靠近近日点时，太阳的摄动会增强。这主要影响**周年差 (Annual Equation)**。

$$
M = 357.5291092 + 35999.0502909 T - 0.0001536 T^2 + T^3 / 24490000.0
$$

*  **月球平近点角 ($M'$)**：月球在轨道上离近地点的角距离。$M'$ 描述了月球在其椭圆轨道上的位置。这是计算开普勒运动（中心天体引力主导）的主要参数，同时也与 $D$ 耦合产生复杂的摄动项。其计算公式中一次项的巨大系数，已经包含了月球自身的平均运动和**近地点进动**（每 8.85 年一周）的叠加效应。

$$
M' = 134.9633964 + 477198.8675055 T + 0.0087414 T^2 + T^3 / 69699.0 - T^4 / 14712000.0
$$

*  **月球纬度参数 ($F$)**：月球离升交点的角距离（决定了月球的黄纬）。$F$ 描述了月球相对于黄道平面的位置。太阳引力倾向于将月球拉向黄道面，导致月球轨道面的进动（交点退行）。$F$ 是计算黄纬摄动项的核心。同样，其公式体现了月球平均运动与**交点退行**（每 18.6 年一周）的共同影响。

$$
F = 93.2720950 + 483202.0175233 T - 0.0036539 T^2 - T^3 / 3526000.0 + T^4 / 863310000.0
$$

```vala
double moon_mean_longitude_deg = 218.3164477 + 481267.88123421 * centuries_since_j2000 - 0.0015786 * centuries_since_j2000_sq + centuries_since_j2000_cu / 538841.0 - centuries_since_j2000_q / 65194000.0;
double mean_elongation_deg = 297.8501921 + 445267.1114034 * centuries_since_j2000 - 0.0018819 * centuries_since_j2000_sq + centuries_since_j2000_cu / 545868.0 - centuries_since_j2000_q / 113065000.0;
// ... (其他参数类似)
```

### 黄道坐标的周期项修正

这是月球算法中最繁琐的部分。月球的**地心黄经 ($\lambda$)** 和 **地心黄纬 ($\beta$)** 是通过在平均位置上叠加一系列周期性摄动项得到的。这些项反映了太阳引力对月球轨道的各种拉扯效应（如出差、二均差等）。

我们的代码实现选取了影响最大的几项：

**黄经修正 ($\Sigma_l$)**：

$$
\begin{aligned}
\Sigma_l = &+ 6.2888 \sin(M') \quad (\text{中心方程：椭圆轨道修正}) \\
&+ 1.2740 \sin(2D - M') \quad (\text{出差：偏心率摄动}) \\
&+ 0.6583 \sin(2D) \quad (\text{二均差：切向力摄动}) \\
&- 0.1856 \sin(M) \quad (\text{周年差：日地距离变化}) \\
&- 0.1143 \sin(2F) \quad (\text{黄道差：轨道倾角投影}) \\
&+ 0.2136 \sin(2D - M) \quad (\text{混合摄动项}) \\
&- 0.0588 \sin(2D - 2M') \quad (\text{出差二阶项}) \\
&- 0.0572 \sin(2D - M - M') \quad (\text{混合摄动项}) \\
&+ 0.0533 \sin(2D + M') \quad (\text{出差变体})
\end{aligned}
$$

**黄纬修正 ($\Sigma_b$)**：

这里不仅包含了摄动项，还直接体现了月球轨道的几何特征。第一项系数 $5.1282^\circ$ 即对应了月球轨道相对于黄道的平均**倾角 (Inclination)**（约为 $5.145^\circ$）。由于 $F$ 包含了**交点退行 (Regression of nodes)** 的影响（即升交点在黄道上向西移动，周期约 18.6 年），这一项描述了月球在黄道面上下摆动的基本运动。

$$
\begin{aligned}
\Sigma_b = &+ 5.1282 \sin(F) \\
&+ 0.2806 \sin(M' + F) \\
&+ 0.2777 \sin(M' - F) \\
&+ 0.1732 \sin(2D - F)
\end{aligned}
$$

最终的地心黄道坐标为：

$$
\lambda = L' + \Sigma_l
$$

$$
\beta = \Sigma_b
$$

```vala
double geocentric_ecliptic_longitude_deg = moon_mean_longitude_deg
    + 6.2888 * Math.sin (moon_mean_anomaly_rad)
    + 1.2740 * Math.sin (2 * mean_elongation_rad - moon_mean_anomaly_rad)
    // ... 更多项
```

### 地心视差与距离

为了将地心坐标转换为观测者所在的**站心坐标（Topocentric Coordinates）**，我们需要知道月球的距离。通常我们计算**赤道地平视差 ($\pi$)**，即地球赤道半径在月球中心的张角。视差 $\pi$ 与地月距离 $r$ 成反比关系（$\sin \pi = R_\oplus / r$）。

$$
\pi (\text{deg}) = 0.95072 + 0.05182 \cos(M') + 0.00953 \cos(2D - M') + 0.00784 \cos(2D) + 0.00282 \cos(2M)
$$

这个公式清晰地展示了地月距离的变化规律：
*   **常数项 $0.95072^\circ$**：对应月球的平均距离（约 384,400 km）。
*   **$\cos(M')$ 项**：反映了月球在自身椭圆轨道上运动引起的距离变化（在近地点时距离近、视差大；在远地点时距离远、视差小），而近地点本身的位置因**近地点进动**而不断变化。
*   **其他项**：反映了太阳引力摄动对月球距离的周期性影响。

这个值大约在 $0.9^\circ$ 到 $1^\circ$ 之间变化。

有了地平视差 $\pi$ 后，我们就可以计算**地心距离 (Geocentric Distance)** $r_{geo}$。根据定义，视差是地球赤道半径 $R_\oplus$ 在月球处的张角，因此：

$$
\sin \pi = \frac{R_\oplus}{r_{geo}}
$$

由此可得地月**地心距离**（单位：千米）：

$$
r_{geo} = \frac{R_\oplus}{\sin \pi} \approx \frac{6378.137}{\sin \pi}
$$

值得注意的是，本程序在侧栏显示及在 CSV 中导出的距离并不是地心距离，而是站心距离（即观测者与月球之间的直线距离），这两者可能存在显著差异，这一点将在后续的视差修正部分详细说明。

### 坐标转换：从黄道到赤道

利用黄赤交角 $\epsilon$，我们将地心黄道坐标 $(\lambda, \beta)$ 转换为地心赤道坐标——赤经 ($\alpha$) 和赤纬 ($\delta$)。

$$
\tan \alpha = \frac{\sin \lambda \cos \epsilon - \tan \beta \sin \epsilon}{\cos \lambda}
$$

$$
\sin \delta = \sin \beta \cos \epsilon + \cos \beta \sin \epsilon \sin \lambda
$$

### 视差修正

这是月球计算中至关重要的一步。之前的计算都是假设观测者位于地心，但实际上观测者位于地球表面。对于月球这样近的天体，这种位置差异会导致视位置的显著改变。

我们需要计算观测者的**地方恒星时 (LST)**，然后得到**时角 (H)**。

$$
H = \text{LST} - \alpha
$$

接着，利用视差 $\pi$ 和观测者的地理纬度 $\phi$，我们将地心坐标 $(\alpha, \delta)$ 转换为站心坐标 $(\alpha', \delta')$。这里我们使用严密的矢量公式（或其分量形式）：

$$
\begin{aligned}
A &= \cos \delta \sin H \\
B &= \cos \delta \cos H - \rho \cos \phi' \sin \pi \\
C &= \sin \delta - \rho \sin \phi' \sin \pi
\end{aligned}
$$

其中 $\rho \sin \phi'$ 和 $\rho \cos \phi'$ 是考虑了地球扁率后的地心纬度函数。

于是，站心时角 $H'$ 和站心赤纬 $\delta'$ 可由下式求得：

$$
\tan H' = \frac{A}{B}
$$

$$
\tan \delta' = \frac{C}{\sqrt{A^2 + B^2}}
$$

A, B, C 实际上构成了从观测者指向月球的矢量的三个分量（以地月地心距离为单位长度）。因此，从观测者到月球的真正距离——**站心距离 ($r_{topo}$)** ——也可以通过计算这个矢量的模长得到：

$$
r_{topo} = r_{geo} \times \sqrt{A^2 + B^2 + C^2}
$$

其中，$r_{geo}$ 是我们之前算出的地心距离。这正是代码中计算 `moon_distances` 的方法。最终程序界面上显示的，便是这个经过完整视差修正后的站心距离。由于站心距是观测者与月球的“直线距离”，它叠加了观测者在地球上的**位置**及**地球大小**的影响，因此这个值完全可以**大于远地点或者小于近地点距离**，这完全是合理的。

最后，利用站心赤纬 $\delta'$ 和站心时角 $H'$，通过标准的球面三角公式计算出月球的**地平高度角 (Elevation)**：

$$
\sin(\text{El}) = \sin \phi \sin \delta' + \cos \phi \cos \delta' \cos H'
$$

```vala
double elevation_sin = sin_lat * Math.sin (topocentric_declination_rad)
                 + cos_lat * Math.cos (topocentric_declination_rad) * Math.cos (topocentric_hour_angle_rad);
moon_angles[i] = Math.asin (elevation_sin.clamp (-1.0, 1.0)) * RAD2DEG;
```

### 月相与亮面比例

除了位置，我们还计算了月相。月球的被照亮比例 $k$ 取决于**日月距角 (Elongation, $\psi$)**：

$$
\cos \psi = \cos \beta \cos (\lambda_{moon} - \lambda_{sun})
$$

$$
k = \frac{1 + \cos \psi}{2}
$$

这里 $\lambda_{sun}$ 是太阳的视黄经。

## 编译与运行

确保你的系统已安装 Vala、GTK4、LibAdwaita、JSON-GLib 以及 C 编译器。在 Linux 下，还需要额外安装在 GLib/GIO 中实现网络访问的 `gvfs` 库（Windows则不需要）。笔者在此列举了在 Arch Linux 和 Windows MSYS2 环境下的安装命令：

* Arch Linux：
  ```bash
  sudo pacman -S --needed vala gtk4 libadwaita json-glib gvfs
  ```
* Windows MSYS2：
  在 MSYS2 UCRT64 环境中：
  ```bash
  pacman -S --needed mingw-w64-ucrt-x86_64-vala mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-gtk4 mingw-w64-ucrt-x86_64-libadwaita mingw-w64-ucrt-x86_64-json-glib
  ```

你可以将[完整代码](https://github.com/wszqkzqk/FunValaGtkExamples/blob/master/lunarcalc.vala)保存为 `lunarcalc.vala`，可以手动保存，也可以使用以下命令下载：

```bash
wget https://raw.githubusercontent.com/wszqkzqk/FunValaGtkExamples/master/lunarcalc.vala
```

然后使用以下命令进行编译：

```bash
valac --pkg=gtk4 --pkg=libadwaita-1 --pkg=json-glib-1.0 -X -lm -X -O2 -X -pipe lunarcalc.vala
```

或者，如果你在 Linux 环境下，可以直接赋予脚本执行权限并运行（脚本头部已包含 Shebang）：

```bash
chmod +x lunarcalc.vala
./lunarcalc.vala
```

## 总结

通过上述步骤，我们用 Vala 实现了一个精度相当可观的月球位置计算器。虽然为了代码简洁性，我们省略了 ELP-2000 理论中数以千计的微小摄动项，但保留的主项足以满足一般天文观测和摄影的需求。

这个案例再次证明，Vala 凭借其 C 语言级别的性能和现代化的语法，非常适合处理此类包含大量三角函数运算和迭代的科学计算任务，再加上 GTK4 和 LibAdwaita 的生态加持，我们可以轻松地将这些后台计算与流畅的 UI 交互结合起来，实时展现天体的奥秘。

## 完整代码实现

```vala
#!/usr/bin/env -S vala --pkg=gtk4 --pkg=libadwaita-1 --pkg=json-glib-1.0 -X -lm -X -O2 -X -march=native -X -pipe
/* SPDX-License-Identifier: LGPL-2.1-or-later */

/**
 * Lunar Calculator.
 * Copyright (C) 2025 wszqkzqk <wszqkzqk@qq.com>
 * A libadwaita application that calculates and visualizes lunar data including
 * elevation angles, distance, phase information, and other lunar parameters
 * throughout the day for a given location and date, with parallax correction.
 */
public class LunarCalc : Adw.Application {
    // Constants for math
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
    private double moon_angles[RESOLUTION_PER_MIN]; // Store moon elevation angles in degrees (-90 to +90)
    private double moon_phases[RESOLUTION_PER_MIN]; // Store illumination fraction (0.0 - 1.0)
    private double moon_elongations[RESOLUTION_PER_MIN];   // Store moon elongations in degrees (0 - 360)
    private double moon_distances[RESOLUTION_PER_MIN]; // Store moon distance in km
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
        double grid_r; double grid_g; double grid_b; double grid_a; // Grid
        double axis_r; double axis_g; double axis_b; // Axes
        double text_r; double text_g; double text_b; // Text
        double curve_r; double curve_g; double curve_b; // Curve
        double shade_r; double shade_g; double shade_b; double shade_a; // Shaded area
        double point_r; double point_g; double point_b; // Click point
        double line_r; double line_g; double line_b; double line_a; // Guide line
    }

    // Light theme
    private static ThemeColors LIGHT_THEME = {
        bg_r: 1.0, bg_g: 1.0, bg_b: 1.0,                    // White background
        grid_r: 0.5, grid_g: 0.5, grid_b: 0.5, grid_a: 0.5, // Gray grid
        axis_r: 0.0, axis_g: 0.0, axis_b: 0.0,              // Black axes
        text_r: 0.0, text_g: 0.0, text_b: 0.0,              // Black text
        curve_r: 0.1, curve_g: 0.1, curve_b: 0.8,           // Blue curve
        shade_r: 0.7, shade_g: 0.7, shade_b: 0.7, shade_a: 0.3, // Light gray shade
        point_r: 0.8, point_g: 0.3, point_b: 0.0,           // Orange point
        line_r: 0.8, line_g: 0.3, line_b: 0.0, line_a: 0.5  // Orange guide lines
    };

    // Dark theme
    private static ThemeColors DARK_THEME = {
        bg_r: 0.0, bg_g: 0.0, bg_b: 0.0,                    // Black background
        grid_r: 0.5, grid_g: 0.5, grid_b: 0.5, grid_a: 0.5, // Gray grid
        axis_r: 1.0, axis_g: 1.0, axis_b: 1.0,              // White axes
        text_r: 1.0, text_g: 1.0, text_b: 1.0,              // White text
        curve_r: 0.3, curve_g: 0.7, curve_b: 1.0,           // Light blue curve
        shade_r: 0.3, shade_g: 0.3, shade_b: 0.3, shade_a: 0.7, // Dark gray shade
        point_r: 1.0, point_g: 0.5, point_b: 0.0,           // Orange point
        line_r: 1.0, line_g: 0.5, line_b: 0.0, line_a: 0.7  // Orange guide lines
    };

    /**
     * Creates a new LunarCalc instance.
     *
     * Initializes the application with a unique application ID and sets
     * the selected date to the current local date.
     */
    public LunarCalc () {
        Object (application_id: "com.github.wszqkzqk.LunarCalc");
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
            title = "Lunar Calculator",
        };

        // Create header bar
        var header_bar = new Adw.HeaderBar () {
            title_widget = new Adw.WindowTitle ("Lunar Calculator", ""),
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
        style_manager.notify["dark"].connect (() => {
            drawing_area.queue_draw ();
        });
        header_bar.pack_end (dark_mode_button);

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

        var location_detect_row = new Adw.ActionRow () {
            title = "Auto-detect Location",
            subtitle = "Get current location and timezone",
            activatable = true,
        };

        var location_box = new Gtk.Box (Gtk.Orientation.HORIZONTAL, 6);
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
        location_stack.add_child (location_button);
        location_stack.add_child (location_spinner);
        location_stack.visible_child = location_button;
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

        // Click Info Group (Enhanced for Lunar)
        var click_info_group = new Adw.PreferencesGroup () {
            title = "Lunar Info",
        };
        click_info_label = new Gtk.Label ("Click on chart for details.\n\n\n") {
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
        drawing_area.set_draw_func (draw_lunar_angle_chart);

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
        location_stack.visible_child = location_spinner;
        location_spinner.start ();

         get_location_async.begin ((obj, res) => {
            try {
                get_location_async.end (res);
            } catch (Error e) {
                show_error_dialog ("Location Detection Failed", e.message);
            }
            location_button.sensitive = true;
            location_spinner.stop ();
            location_stack.visible_child = location_button;
         });
    }

    /**
     * Asynchronously gets current location using IP geolocation service with timeout.
     *
     * @throws IOError If location detection fails.
     */
    private async void get_location_async () throws IOError {
        var file = File.new_for_uri ("https://ipapi.co/json/");
        var parser = new Json.Parser ();
        var cancellable = new Cancellable ();
        var timeout_id = Timeout.add_seconds_once (5, () => { cancellable.cancel (); });

        try {
            var stream = yield file.read_async (Priority.DEFAULT, cancellable);
            yield parser.load_from_stream_async (stream, cancellable);
        } catch (Error e) {
            throw new IOError.FAILED ("Failed to get location: %s", e.message);
        } finally {
            if (!cancellable.is_cancelled ()) Source.remove (timeout_id);
        }

        var root_object = parser.get_root ().get_object ();
        if (root_object.get_boolean_member_with_default ("error", false)) {
            throw new IOError.FAILED ("Location service error: %s", root_object.get_string_member_with_default ("reason", "Unknown error"));
        }

        if (root_object.has_member ("latitude") && root_object.has_member ("longitude")) {
            latitude = root_object.get_double_member ("latitude");
            longitude = root_object.get_double_member ("longitude");
        } else {
            throw new IOError.FAILED ("No coordinates found");
        }

        double network_tz_offset = 0.0;
        bool has_network_tz = false;
        if (root_object.has_member ("utc_offset")) {
            var offset_str = root_object.get_string_member ("utc_offset");
            network_tz_offset = double.parse (offset_str) / 100.0;
            has_network_tz = true;
        }

        var timezone = new TimeZone.local ();
        var time_interval = timezone.find_interval (GLib.TimeType.UNIVERSAL, selected_date.to_unix ());
        var local_tz_offset = timezone.get_offset (time_interval) / 3600.0;

        const double TZ_EPSILON = 0.01;
        const string NETWORK_CHOICE = "network";
        const string LOCAL_CHOICE = "local";
        if (has_network_tz && (!(-TZ_EPSILON < (network_tz_offset - local_tz_offset) < TZ_EPSILON))) {
            var dialog = new Adw.AlertDialog (
                "Timezone Mismatch",
                "The timezone from the network (UTC%+.2f) differs from your system's timezone (UTC%+.2f).\n\nWhich one would you like to use?".printf (network_tz_offset, local_tz_offset)
            );
            dialog.add_response (NETWORK_CHOICE, "Use Network Timezone");
            dialog.add_response (LOCAL_CHOICE, "Use System Timezone");
            dialog.default_response = NETWORK_CHOICE;
            unowned var choice = yield dialog.choose (window, null);
            timezone_offset_hours = (choice == NETWORK_CHOICE) ? network_tz_offset : local_tz_offset;
        } else {
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
     * Gets the phase description string based on elongation angle.
     *
     * @param phase_fraction Illuminated fraction (0.0-1.0).
     * @param elongation_deg Elongation angle in degrees.
     * @return Phase description string.
     */
    private string get_phase_description (double phase_fraction, double elongation_deg) {
        while (elongation_deg < 0) elongation_deg += 360.0;
        while (elongation_deg >= 360.0) elongation_deg -= 360.0;

        string desc;
        if (elongation_deg < 5 || elongation_deg > 355) desc = "New Moon";
        else if (elongation_deg < 85) desc = "Waxing Crescent";
        else if (elongation_deg < 95) desc = "First Quarter";
        else if (elongation_deg < 175) desc = "Waxing Gibbous";
        else if (elongation_deg < 185) desc = "Full Moon";
        else if (elongation_deg < 265) desc = "Waning Gibbous";
        else if (elongation_deg < 275) desc = "Last Quarter";
        else desc = "Waning Crescent";

        return "%s (%.1f%%)".printf(desc, phase_fraction * 100.0);
    }

    /**
     * Updates the info label with default lunar phase at 00:00.
     */
    private void update_info_label_default() {
        click_info_label.label = "Click on chart for details.\nReference Data (00:00):\nDistance: %.0f km\n%s".printf (
            moon_distances[0],
            get_phase_description (moon_phases[0], moon_elongations[0])
        );
    }

    /**
     * Calculates Moon elevation angles and phases for each minute of the day.
     * Includes parallax correction. No atmospheric refraction.
     *
     * @param latitude_rad Latitude in radians.
     * @param longitude_deg Longitude in degrees.
     * @param timezone_offset_hrs Timezone offset from UTC in hours.
     * @param julian_date GLib's Julian Date for the day (from 0001-01-01).
     */
    private void generate_moon_angles (double latitude_rad, double longitude_deg, double timezone_offset_hrs, double julian_date) {
        double earth_flattening = 1.0 / 298.257223563;
        double phi_prime = Math.atan ((1 - earth_flattening) * Math.tan (latitude_rad));
        double rho_sin_phi_prime = (1 - earth_flattening) * Math.sin (phi_prime);
        double rho_cos_phi_prime = Math.cos (phi_prime);

        double sin_lat = Math.sin (latitude_rad);
        double cos_lat = Math.cos (latitude_rad);

        // Base days from J2000.0 epoch (GLib's Julian Date is days since 0001-01-01 12:00 UTC)
        double base_days_since_j2000 = julian_date - 730120.5;

        // Pre-compute obliquity that changes very slowly
        double base_centuries_since_j2000 = base_days_since_j2000 / 36525.0;
        double base_centuries_since_j2000_sq = base_centuries_since_j2000 * base_centuries_since_j2000;
        double base_centuries_since_j2000_cu = base_centuries_since_j2000_sq * base_centuries_since_j2000;
        double obliquity_deg = 23.439291111 - 0.013004167 * base_centuries_since_j2000 - 1.63889e-7 * base_centuries_since_j2000_sq + 5.0361e-7 * base_centuries_since_j2000_cu;
        double obliquity_rad = obliquity_deg * DEG2RAD;
        double obliquity_sin = Math.sin (obliquity_rad);
        double obliquity_cos = Math.cos (obliquity_rad);
        double sun_eq_c1 = 1.914602 - 0.004817 * base_centuries_since_j2000 - 0.000014 * base_centuries_since_j2000_sq;
        double sun_eq_c2 = 0.019993 - 0.000101 * base_centuries_since_j2000;

        for (int i = 0; i < RESOLUTION_PER_MIN; i += 1) {
            double local_days_since_j2000 = base_days_since_j2000 + (i / 60.0 - timezone_offset_hrs) / 24.0;
            double centuries_since_j2000 = local_days_since_j2000 / 36525.0;
            double centuries_since_j2000_sq = centuries_since_j2000 * centuries_since_j2000;
            double centuries_since_j2000_cu = centuries_since_j2000_sq * centuries_since_j2000;
            double centuries_since_j2000_q = centuries_since_j2000_cu * centuries_since_j2000;

            double moon_mean_longitude_deg = 218.3164477 + 481267.88123421 * centuries_since_j2000 - 0.0015786 * centuries_since_j2000_sq + centuries_since_j2000_cu / 538841.0 - centuries_since_j2000_q / 65194000.0;
            double mean_elongation_deg = 297.8501921 + 445267.1114034 * centuries_since_j2000 - 0.0018819 * centuries_since_j2000_sq + centuries_since_j2000_cu / 545868.0 - centuries_since_j2000_q / 113065000.0;
            double sun_mean_anomaly_deg = 357.5291092 + 35999.0502909 * centuries_since_j2000 - 0.0001536 * centuries_since_j2000_sq + centuries_since_j2000_cu / 24490000.0;
            double moon_mean_anomaly_deg = 134.9633964 + 477198.8675055 * centuries_since_j2000 + 0.0087414 * centuries_since_j2000_sq + centuries_since_j2000_cu / 69699.0 - centuries_since_j2000_q / 14712000.0;
            double moon_argument_of_latitude_deg = 93.2720950 + 483202.0175233 * centuries_since_j2000 - 0.0036539 * centuries_since_j2000_sq - centuries_since_j2000_cu / 3526000.0 + centuries_since_j2000_q / 863310000.0;

            double mean_elongation_rad = mean_elongation_deg * DEG2RAD;
            double sun_mean_anomaly_rad = sun_mean_anomaly_deg * DEG2RAD;
            double moon_mean_anomaly_rad = moon_mean_anomaly_deg * DEG2RAD;
            double moon_argument_of_latitude_rad = moon_argument_of_latitude_deg * DEG2RAD;

            double geocentric_ecliptic_longitude_deg = moon_mean_longitude_deg
                + 6.2888 * Math.sin (moon_mean_anomaly_rad)
                + 1.2740 * Math.sin (2 * mean_elongation_rad - moon_mean_anomaly_rad)
                + 0.6583 * Math.sin (2 * mean_elongation_rad)
                - 0.1856 * Math.sin (sun_mean_anomaly_rad)
                - 0.1143 * Math.sin (2 * moon_argument_of_latitude_rad)
                + 0.2136 * Math.sin (2 * mean_elongation_rad - sun_mean_anomaly_rad)
                - 0.0588 * Math.sin (2 * mean_elongation_rad - 2 * moon_mean_anomaly_rad)
                - 0.0572 * Math.sin (2 * mean_elongation_rad - sun_mean_anomaly_rad - moon_mean_anomaly_rad)
                + 0.0533 * Math.sin (2 * mean_elongation_rad + moon_mean_anomaly_rad);

            double geocentric_ecliptic_latitude_deg = 5.1282 * Math.sin (moon_argument_of_latitude_rad)
                + 0.2806 * Math.sin (moon_mean_anomaly_rad + moon_argument_of_latitude_rad)
                + 0.2777 * Math.sin (moon_mean_anomaly_rad - moon_argument_of_latitude_rad)
                + 0.1732 * Math.sin (2 * mean_elongation_rad - moon_argument_of_latitude_rad);

            double horizontal_parallax_deg = 0.95072
                + 0.05182 * Math.cos (moon_mean_anomaly_rad)
                + 0.00953 * Math.cos (2 * mean_elongation_rad - moon_mean_anomaly_rad)
                + 0.00784 * Math.cos (2 * mean_elongation_rad)
                + 0.00282 * Math.cos (2 * sun_mean_anomaly_rad);

            double horizontal_parallax_rad = horizontal_parallax_deg * DEG2RAD;

            double sun_mean_longitude = 280.46646 + 36000.76983 * centuries_since_j2000 + 0.0003032 * centuries_since_j2000_sq;
            sun_mean_longitude = Math.fmod (sun_mean_longitude, 360.0);
            if (sun_mean_longitude < 0) sun_mean_longitude += 360.0;

            double sun_eq_center = sun_eq_c1 * Math.sin (sun_mean_anomaly_rad)
                                 + sun_eq_c2 * Math.sin (2 * sun_mean_anomaly_rad)
                                 + 0.000289 * Math.sin (3 * sun_mean_anomaly_rad);

            double sun_true_longitude = sun_mean_longitude + sun_eq_center;

            double omega = moon_mean_longitude_deg - moon_argument_of_latitude_deg;
            double sun_apparent_longitude = sun_true_longitude - 0.00569 - 0.00478 * Math.sin (omega * DEG2RAD);

            double lambda_moon_rad = geocentric_ecliptic_longitude_deg * DEG2RAD;
            double beta_moon_rad = geocentric_ecliptic_latitude_deg * DEG2RAD;
            double lambda_sun_rad = sun_apparent_longitude * DEG2RAD;

            double cos_elongation = Math.cos (beta_moon_rad) * Math.cos (lambda_moon_rad - lambda_sun_rad);

            double illuminated_fraction = (1.0 - cos_elongation) / 2.0;

            double diff_long = geocentric_ecliptic_longitude_deg - sun_apparent_longitude;
            diff_long = Math.fmod (diff_long, 360.0);
            if (diff_long < 0) diff_long += 360.0;

            moon_phases[i] = illuminated_fraction;
            moon_elongations[i] = diff_long;

            double geocentric_ecliptic_longitude_rad = geocentric_ecliptic_longitude_deg * DEG2RAD;
            double geocentric_ecliptic_latitude_rad = geocentric_ecliptic_latitude_deg * DEG2RAD;

            double sin_ecl_lon = Math.sin (geocentric_ecliptic_longitude_rad);
            double cos_ecl_lon = Math.cos (geocentric_ecliptic_longitude_rad);
            double sin_ecl_lat = Math.sin (geocentric_ecliptic_latitude_rad);
            double cos_ecl_lat = Math.cos (geocentric_ecliptic_latitude_rad);

            double ra_sin_component = sin_ecl_lon * obliquity_cos - Math.tan (geocentric_ecliptic_latitude_rad) * obliquity_sin;
            double ra_cos_component = cos_ecl_lon;
            double geocentric_ra_rad = Math.atan2 (ra_sin_component, ra_cos_component);

            double geocentric_dec_sin = sin_ecl_lat * obliquity_cos + cos_ecl_lat * obliquity_sin * sin_ecl_lon;
            double geocentric_dec_rad = Math.asin (geocentric_dec_sin);

            double greenwich_mean_sidereal_time_deg = 280.46061837 + 360.98564736629 * local_days_since_j2000;
            greenwich_mean_sidereal_time_deg = Math.fmod (greenwich_mean_sidereal_time_deg, 360.0);
            if (greenwich_mean_sidereal_time_deg < 0) greenwich_mean_sidereal_time_deg += 360.0;

            double local_mean_sidereal_time_deg = greenwich_mean_sidereal_time_deg + longitude_deg;
            double local_mean_sidereal_time_rad = local_mean_sidereal_time_deg * DEG2RAD;

            double hour_angle_rad = local_mean_sidereal_time_rad - geocentric_ra_rad;

            double declination_cos = Math.cos (geocentric_dec_rad);
            double parallax_sin = Math.sin (horizontal_parallax_rad);

            double sin_hour_angle = Math.sin (hour_angle_rad);
            double cos_hour_angle = Math.cos (hour_angle_rad);

            double a_component = declination_cos * sin_hour_angle;
            double a_sq = a_component * a_component;
            double b_component = declination_cos * cos_hour_angle - rho_cos_phi_prime * parallax_sin;
            double b_sq = b_component * b_component;
            double c_component = geocentric_dec_sin - rho_sin_phi_prime * parallax_sin;
            double c_sq = c_component * c_component;

            double topocentric_hour_angle_rad = Math.atan2 (a_component, b_component);
            double topocentric_horizontal_distance = Math.sqrt (a_sq + b_sq);
            double topocentric_declination_rad = Math.atan2 (c_component, topocentric_horizontal_distance);

            double elevation_sin = sin_lat * Math.sin (topocentric_declination_rad)
                             + cos_lat * Math.cos (topocentric_declination_rad) * Math.cos (topocentric_hour_angle_rad);

            moon_angles[i] = Math.asin (elevation_sin.clamp (-1.0, 1.0)) * RAD2DEG;

            double dist_ratio = Math.sqrt (a_sq + b_sq + c_sq);
            moon_distances[i] = dist_ratio * (6378.137 / parallax_sin);
        }
    }

    /**
     * Updates lunar angle data for current settings.
     */
    private void update_plot_data () {
        double latitude_rad = latitude * DEG2RAD;
        // Convert DateTime to Date and get Julian Day Number
        var date = Date ();
        date.set_dmy ((DateDay) selected_date.get_day_of_month (),
                      selected_date.get_month (),
                      (DateYear) selected_date.get_year ());
        var julian_date = (double) date.get_julian ();
        generate_moon_angles (latitude_rad, longitude, timezone_offset_hours, julian_date);
        has_click_point = false;
        update_info_label_default ();
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

        if (x >= MARGIN_LEFT && x <= width - MARGIN_RIGHT && y >= MARGIN_TOP && y <= height - MARGIN_BOTTOM && n_press == 1) {
            clicked_time_hours = (x - MARGIN_LEFT) / chart_width * 24.0;
            int time_minutes = (int) (clicked_time_hours * 60);
            corresponding_angle = moon_angles[time_minutes];
            double phase = moon_phases[time_minutes];
            double elongation = moon_elongations[time_minutes];
            has_click_point = true;

            int hours = (int) clicked_time_hours;
            int minutes = (int) ((clicked_time_hours - hours) * 60);

            string info_text = "Time: %02d:%02d\nElevation: %.1f°\nDistance: %.0f km\n%s".printf (
                hours, minutes, corresponding_angle, moon_distances[time_minutes], get_phase_description(phase, elongation)
            );
            click_info_label.label = info_text;
            drawing_area.queue_draw ();
        } else {
            has_click_point = false;
            update_info_label_default();
            drawing_area.queue_draw ();
        }
    }

    /**
     * Draws the lunar elevation chart.
     *
     * @param area The drawing area widget.
     * @param cr The Cairo context for drawing.
     * @param width The width of the drawing area.
     * @param height The height of the drawing area.
     */
    private void draw_lunar_angle_chart (Gtk.DrawingArea area, Cairo.Context cr, int width, int height) {
        ThemeColors colors = style_manager.dark ? DARK_THEME : LIGHT_THEME;

        cr.set_source_rgb (colors.bg_r, colors.bg_g, colors.bg_b);
        cr.paint ();

        int chart_width = width - MARGIN_LEFT - MARGIN_RIGHT;
        int chart_height = height - MARGIN_TOP - MARGIN_BOTTOM;
        double horizon_y = MARGIN_TOP + chart_height * 0.5;

        // Shade area below horizon
        cr.set_source_rgba (colors.shade_r, colors.shade_g, colors.shade_b, colors.shade_a);
        cr.rectangle (MARGIN_LEFT, horizon_y, chart_width, height - MARGIN_BOTTOM - horizon_y);
        cr.fill ();

        // Grid
        cr.set_source_rgba (colors.grid_r, colors.grid_g, colors.grid_b, colors.grid_a);
        cr.set_line_width (1);
        for (int angle = -90; angle <= 90; angle += 15) {
            double tick_y = MARGIN_TOP + chart_height * (90 - angle) / 180.0;
            cr.move_to (MARGIN_LEFT, tick_y);
            cr.line_to (width - MARGIN_RIGHT, tick_y);
            cr.stroke ();
        }
        for (int h = 0; h <= 24; h += 2) {
            double tick_x = MARGIN_LEFT + chart_width * (h / 24.0);
            cr.move_to (tick_x, MARGIN_TOP);
            cr.line_to (tick_x, height - MARGIN_BOTTOM);
            cr.stroke ();
        }

        // Axes
        cr.set_source_rgb (colors.axis_r, colors.axis_g, colors.axis_b);
        cr.set_line_width (2);
        cr.move_to (MARGIN_LEFT, height - MARGIN_BOTTOM);
        cr.line_to (width - MARGIN_RIGHT, height - MARGIN_BOTTOM);
        cr.stroke ();
        cr.move_to (MARGIN_LEFT, MARGIN_TOP);
        cr.line_to (MARGIN_LEFT, height - MARGIN_BOTTOM);
        cr.stroke ();
        cr.move_to (MARGIN_LEFT, horizon_y);
        cr.line_to (width - MARGIN_RIGHT, horizon_y);
        cr.stroke ();

        // Labels
        cr.set_source_rgb (colors.text_r, colors.text_g, colors.text_b);
        cr.set_line_width (1);
        cr.set_font_size (20);
        for (int angle = -90; angle <= 90; angle += 15) {
            double tick_y = MARGIN_TOP + chart_height * (90 - angle) / 180.0;
            cr.move_to (MARGIN_LEFT - 5, tick_y);
            cr.line_to (MARGIN_LEFT, tick_y);
            cr.stroke ();
            var txt = angle.to_string ();
            Cairo.TextExtents te;
            cr.text_extents (txt, out te);
            cr.move_to (MARGIN_LEFT - 10 - te.width, tick_y + te.height / 2);
            cr.show_text (txt);
        }
        for (int h = 0; h <= 24; h += 2) {
            double tick_x = MARGIN_LEFT + chart_width * (h / 24.0);
            cr.move_to (tick_x, height - MARGIN_BOTTOM);
            cr.line_to (tick_x, height - MARGIN_BOTTOM + 5);
            cr.stroke ();
            var txt = h.to_string ();
            Cairo.TextExtents te;
            cr.text_extents (txt, out te);
            cr.move_to (tick_x - te.width / 2, height - MARGIN_BOTTOM + 25);
            cr.show_text (txt);
        }

        // Curve
        cr.set_source_rgb (colors.curve_r, colors.curve_g, colors.curve_b);
        cr.set_line_width (2);
        for (int i = 0; i < RESOLUTION_PER_MIN; i += 1) {
            double x = MARGIN_LEFT + chart_width * (i / (double) (RESOLUTION_PER_MIN - 1));
            double y = MARGIN_TOP + chart_height * (90.0 - moon_angles[i]) / 180.0;
            if (i == 0) cr.move_to (x, y);
            else cr.line_to (x, y);
        }
        cr.stroke ();

        // Click point
        if (has_click_point) {
            double clicked_x = MARGIN_LEFT + chart_width * (clicked_time_hours / 24.0);
            double corresponding_y = MARGIN_TOP + chart_height * (90.0 - corresponding_angle) / 180.0;

            cr.set_source_rgba (colors.point_r, colors.point_g, colors.point_b, 0.8);
            cr.arc (clicked_x, corresponding_y, 5, 0, 2 * Math.PI);
            cr.fill ();

            cr.set_source_rgba (colors.line_r, colors.line_g, colors.line_b, colors.line_a);
            cr.set_line_width (1);
            cr.move_to (clicked_x, MARGIN_TOP);
            cr.line_to (clicked_x, height - MARGIN_BOTTOM);
            cr.stroke ();
            cr.move_to (MARGIN_LEFT, corresponding_y);
            cr.line_to (width - MARGIN_RIGHT, corresponding_y);
            cr.stroke ();
        }

        // Titles
        cr.set_source_rgb (colors.text_r, colors.text_g, colors.text_b);
        cr.set_font_size (20);
        string x_title = "Time (hours)";
        Cairo.TextExtents x_ext;
        cr.text_extents (x_title, out x_ext);
        cr.move_to ((double) width / 2 - x_ext.width / 2, height - MARGIN_BOTTOM + 55);
        cr.show_text (x_title);

        string y_title = "Lunar Elevation (°)";
        Cairo.TextExtents y_ext;
        cr.text_extents (y_title, out y_ext);
        cr.save ();
        cr.translate (MARGIN_LEFT - 45, (double)height / 2);
        cr.rotate (-Math.PI / 2);
        cr.move_to (-y_ext.width / 2, 0);
        cr.show_text (y_title);
        cr.restore ();

        // Captions
        string caption_line1 = "Lunar Elevation Angle - Date: %s".printf (selected_date.format ("%Y-%m-%d"));
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
        var png_filter = new Gtk.FileFilter (); png_filter.name = "PNG Images"; png_filter.add_mime_type ("image/png");
        var svg_filter = new Gtk.FileFilter (); svg_filter.name = "SVG Images"; svg_filter.add_mime_type ("image/svg+xml");
        var pdf_filter = new Gtk.FileFilter (); pdf_filter.name = "PDF Documents"; pdf_filter.add_mime_type ("application/pdf");

        var filter_list = new ListStore (typeof (Gtk.FileFilter));
        filter_list.append (png_filter); filter_list.append (svg_filter); filter_list.append (pdf_filter);

        var file_dialog = new Gtk.FileDialog () {
            modal = true,
            initial_name = "lunar_elevation_chart.png",
            filters = filter_list,
        };
        file_dialog.save.begin (window, null, (obj, res) => {
            try {
                var file = file_dialog.save.end (res);
                if (file != null) export_chart (file);
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
        if (width <= 0) { width = 800; height = 600; }

        string filepath = file.get_path ();
        string? extension = null;
        var last_dot = filepath.last_index_of_char ('.');
        if (last_dot != -1) extension = filepath[last_dot:].down ();

        if (extension == ".svg") {
            var surface = new Cairo.SvgSurface (filepath, width, height);
            var cr = new Cairo.Context (surface);
            draw_lunar_angle_chart (drawing_area, cr, width, height);
        } else if (extension == ".pdf") {
            var surface = new Cairo.PdfSurface (filepath, width, height);
            var cr = new Cairo.Context (surface);
            draw_lunar_angle_chart (drawing_area, cr, width, height);
        } else {
            var surface = new Cairo.ImageSurface (Cairo.Format.RGB24, width, height);
            var cr = new Cairo.Context (surface);
            draw_lunar_angle_chart (drawing_area, cr, width, height);
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
            initial_name = "lunar_elevation_data.csv",
            filters = filter_list,
        };
        file_dialog.save.begin (window, null, (obj, res) => {
            try {
                var file = file_dialog.save.end (res);
                if (file != null) export_csv_data (file);
            } catch (Error e) {
                message ("CSV file has not been saved: %s", e.message);
            }
        });
    }

    /**
     * Exports the lunar data to a CSV file.
     *
     * @param file The file to export the data to.
     */
    private void export_csv_data (File file) {
        try {
            var stream = file.replace (null, false, FileCreateFlags.REPLACE_DESTINATION);
            var data_stream = new DataOutputStream (stream);

            data_stream.put_string ("# Lunar Data\n");
            data_stream.put_string ("# Date: %s\n".printf (selected_date.format ("%Y-%m-%d")));
            data_stream.put_string ("# Latitude: %.2f, Longitude: %.2f\n".printf (latitude, longitude));
            data_stream.put_string ("# Timezone: UTC%+.2f\n".printf (timezone_offset_hours));
            data_stream.put_string ("#\n");
            data_stream.put_string ("Time,Elevation(deg),Illumination,Distance(km)\n");

            for (int i = 0; i < RESOLUTION_PER_MIN; i += 1) {
                int hours = i / 60;
                int minutes = i % 60;
                data_stream.put_string (
                    "%02d:%02d,%.3f,%.2f%%,%.0f\n".printf (hours, minutes, moon_angles[i], moon_phases[i] * 100.0, moon_distances[i])
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
     * Creates and runs the LunarCalc instance.
     *
     * @param args Command line arguments.
     * @return Exit code.
     */
    public static int main (string[] args) {
        var app = new LunarCalc ();
        return app.run (args);
    }
}
```
