---
layout:     post
title:      优化 Wikipedia 太阳位置简化公式
subtitle:   接着上一篇继续整活
date:       2025-10-08
author:     wszqkzqk
header-img: img/Vala_Logo.webp
catalog:    true
tags:       开源软件 GTK Vala 数值计算
---

## 前言

在上篇博客[《Vala 数值计算实践：高精度太阳位置算法》](https://wszqkzqk.github.io/2025/10/08/Vala-Numerical-Computation-Practice-High-Precision-Solar-Position-Algorithm)中，我们深入探讨了 Jean Meeus 算法在 Vala 中的实现。这是一个基于天体力学解析模型的"黄金标准"，精度极高（平均误差仅 0.003°）且计算也很高效，但其输入依赖儒略日（Julian Date），还需要理解平近点角、真黄经等专业概念，这对不熟悉天文学历元的读者来说，可能门槛较高。

今天，我们转向另一个方向：**优化 Wikipedia 上提供的太阳位置简化公式**。这个公式简单、直观，只需年份和年积日（Day of Year）即可计算太阳高度角，非常适合日常应用和教学目的。然而，原公式精度较低（平均误差 0.12°），且忽略了轨道参数随年份的缓慢变化（如近日点偏移、轴倾角衰减）。本文将完整介绍我对其的优化过程：从模型改进，到数据拟合，再到结果验证。我们将看到，如何在保持易用性的前提下，将其精度显著提升（平均误差降至 0.076° 左右），并探讨这种优化的物理意义与计算效率。

这篇博客的优化代码，已集成到我的 [GTK4 太阳高度角计算器](https://github.com/wszqkzqk/FunValaGtkExamples/blob/master/solarangleadw.vala) 中，作为 Meeus 算法的"轻量备选"。如果你对高精度计算感兴趣，这是一个平衡易懂与精度的实用方案。

## Wikipedia 简化公式的背景与不足

Wikipedia 的太阳位置公式（详见 [Position of the Sun](https://en.wikipedia.org/wiki/Position_of_the_Sun#Approximation)）是一个经典的简化解析模型。它源于天体力学的基本原理，但通过一系列近似，得到易于手算的表达式。核心目标是：在不依赖复杂星历表的情况下，提供一个"够用"的太阳赤纬（Declination, $\delta$）和均时差（Equation of Time, EoT）计算方法。

### 赤纬公式

$$
\delta_\odot = \arcsin \left [ \sin \left ( -23.44^\circ \right ) \cdot \cos \left ( \frac{360^\circ}{365.2422} \left (N + 10 \right ) + \frac{360^\circ}{\pi} \cdot 0.0167 \sin \left ( \frac{360^\circ}{365.2422} \left ( N - 2 \right ) \right ) \right ) \right ]
$$

- **物理基础**：太阳赤纬反映了地球自转轴倾角（Obliquity, $\epsilon \approx 23.44^\circ$）与公转位置的交互。公式假设一个理想圆轨道（角速度 $\Omega = 360^\circ / 365.2422$），然后加入中心差（Equation of Center，由偏心率 $e \approx 0.0167$ 引起）。
- **参数含义**：
  - $N$：年积日（从 1 月 1 日起算）。
  - $N + 10$：近似冬至偏移（冬至约在 12 月 21 日，距 1 月 1 日前 10 天）。
  - $N - 2$：近似近日点偏移（近日点约在 1 月 3 日，距 1 月 1 日后 2 天）。
- **为什么这样设计**：这是一个"一阶修正"模型。先计算近似黄经 $\lambda \approx \Omega (N + 10) + (360^\circ / \pi) e \sin(\Omega (N - 2))$，再通过 $\sin \delta = -\sin \epsilon \cos \lambda$ 得到赤纬。简单，却捕捉了轨道椭圆的主要影响。

### 均时差公式

$$
\Delta t = -7.659 \sin D + 9.863 \sin(2D + 3.5932^\circ)
$$

其中 $D = 6.24004077^\circ + 0.01720197^\circ \times (365.25 (y - 2000) + d_e)$，$y$ 为年份，$d_e$ 为年积日减 1。

- **物理基础**：EoT 修正了钟表时间与真太阳时的偏差，包括偏心率项（周期 1 年）和轴倾角项（周期 0.5 年）。
- **为什么这样设计**：这是一个双正弦拟合，捕捉了 EoT 的主要周期性变化。$D$ 的增长率对应地球的平均角速度。

### 不足之处

尽管优雅，这个公式有明显局限：
1. **精度低**：平均 RMSD 达 0.124°，最差时超 0.4°（相当于太阳视直径）。这是因为它忽略了高阶修正（如轨道摄动）和参数的长期变化。
2. **粗糙近似**：冬至/近日点偏移用固定整数（10 和 -2），忽略了这些点随年份的缓慢漂移（预进和岁差导致）。
3. **无年份依赖**：参数如 $\epsilon = 23.44^\circ$、$e = 0.0167$ 是 2000 年左右的快照值。实际中，$\epsilon$ 每世纪衰减 0.47°，近日点每世纪前进 11°，导致百年尺度误差累积。
4. **闰年不平滑**：$N$ 在闰年 2 月 29 日"跳跃"，但公式未处理，导致平/闰年误差不均。

这些不足使它适合手算或低精度 App，但不宜用于长期模拟或高纬度场景（如极地日出日落）。

## 优化动机：易用性与精度的平衡

为什么不直接用 Meeus 算法？Meeus 虽优越（RMSD 0.0038°），但：
- 输入需儒略日，用户需额外转换（虽 Vala 的 `GLib.Date.get_julian()` 简化了，但对初学者仍不直观）。
- 概念门槛高（平黄经、中心差高阶项），不易初学者理解。

Wikipedia 公式则只需"年份 + 年积日"，更易懂。但其精度不足以匹敌 Meeus。优化目标：
- **保持易用**：输入不变，输出 Vala 函数直接用年/日。
- **提升精度**：引入年份线性变化，拟合 1900-2099 数据，使 RMSD 降至 0.076°。
- **物理意义**：参数对应真实轨道变化（如轴倾、近日点偏移），便于理解和调试。
- **效率相当**：详见后文分析。

这种"半物理半拟合"方法，适合教育/移动 App：精度够用，代码简洁。

## 优化方法：模型改进与数据拟合

### 模型改进

我将原公式参数化为年份线性函数：$P(y) = P_0 + k_y (y - 2000)$，其中 $P$ 为物理量，$P_0$ 为 2000 年基准，$k_y$ 为年系数。

- **赤纬部分**：
  - Obliquity: $\epsilon(y) = \epsilon_0 + k_{\epsilon} (y - 2000)$（对应轴倾衰减）。
  - Solstice offset: $S(y) = S_0 + k_S (y - 2000)$（冬至漂移）。
  - Perihelion offset: $P(y) = P_0 + k_P (y - 2000)$（近日点前进）。
  - Eccentricity: $e(y) = e_0 + k_e (y - 2000)$（偏心率微变）。
  - 公式变为：$\delta = \arcsin[ \sin(-\epsilon(y)) \cos( \Omega (N + S(y)) + (360/\pi) e(y) \sin( \Omega (N + P(y)) ) ) ]$。

- **EoT 部分**：
  - Amp1 (偏心项幅度): $A_1(y) = A_{10} + k_{A1} (y - 2000)$。
  - Amp2 (倾角项幅度): $A_2(y) = A_{20} + k_{A2} (y - 2000)$。
  - Phase (倾角项相位): $\phi(y) = \phi_0 + k_\phi (y - 2000)$。
  - D const: $D_0(y) = D_{00} + k_D (y - 2000)$。
  - 公式：$\Delta t = A_1(y) \sin D(y) + A_2(y) \sin(2D(y) + \phi(y))$，$D(y) = D_0(y) + \omega (365.25 (y-2000) + N)$。

总参数 16 个（8 常数 + 8 年系数），拟合自高精度数据。

### 数据生成与拟合

使用 Astropy（金标准）生成"真值"：1900-2099 年偶数年（--year-step 2，确保 ~50% 闰年/平年），每 2 天（--day-step 2），每 2 小时整点，3 个位置（重庆、新加坡、斯德哥尔摩）。总样本 ~65 万，覆盖全球纬度。

**早期困难：数据选取不均**  
初始方案：每 5 年采样，导致平年远多于闰年（闰年仅 20%）。结果：平年 RMSD 低（0.05°），闰年高（0.15°），因 $N$ 在 2/29 "跳跃"未平滑。  
**解决**：改用偶数年（1900-2099），闰年比例 ~48%，数据更平衡。脚本用 `least_squares`（SciPy）最小化残差，初始猜值为 Wikipedia 常数 + 0 年系数。

Vala 输出函数预计算年参数，循环内仅基本三角函数，高效。

## 拟合结果与物理解释

拟合收敛快（4 迭代，成本从 6400 降至 1877）。中心化系数（$y_c = y - 2000$）：

| 参数组 | 常数项 ($P_0$) | 年系数 ($k_y$) |
|--------|----------------|---------------|
| Obliquity (°) | 23.4352 | -0.000127 |
| Solstice offset (day) | 10.216 | 0.00758 |
| Perihelion offset (day) | -2.955 | -0.00993 |
| Eccentricity | 0.01664 | -4.27e-7 |
| EoT Amp1 (min) | -7.342 | 9.32e-5 |
| EoT Amp2 (min) | 9.909 | -0.000133 |
| EoT Phase (rad) | 3.629 | 0.000643 |
| EoT D const (°) | 6.211 | -2.76e-5 |

展开为 $P(y) = (P_0 - 2000 k_y) + k_y y$（便于 Vala 代码）：

- Obliquity const: 23.690°，年率 -0.000127°/yr（匹配公认值：2000 年 23.439°，世纪衰减 0.47°）。
- Solstice offset const: -4.954 day，年率 0.00758 day/yr（冬至后移，匹配岁差）。
- Perihelion offset const: 16.908 day，年率 -0.00993 day/yr（近日点前进 ~11°/世纪）。
- Eccentricity const: 0.01749，年率 -4.27e-7/yr（微小衰减）。
- EoT 参数：幅度/相位随倾角/偏心变化，D const 微调起始相位。

这些系数直接对应物理量：轴倾衰减由潮汐摩擦引起，近日点前进由引力摄动。2000 年值与 NASA 星历吻合（e.g., $\epsilon=23.4393^\circ$，误差 <0.001°）。

### 线性参数的完整公式表达

为便于后续实现和复现，以下给出在日历年份 $y$、年积日 $N$（自 1 月 1 日起，含闰日）以及从本地午夜起算的分钟数 $t$ 下的完整解析式。角度制转换采用 $\deg2rad(x) = x \pi / 180$。

**赤纬**

线性化的轨道参数为：

$$
\begin{aligned}
\epsilon(y) &= (23.68961512 - 0.00012720\, y)^\circ,\\
S(y) &= -4.95365451 + 0.00758474\, y,\\
P(y) &= 16.90763877 - 0.00993146\, y,\\
e(y) &= 0.01749432 - 4.3\times 10^{-7} y,\\
\Omega &= \frac{360^\circ}{365.2422}.
\end{aligned}
$$

则经过拟合优化后的赤纬表达式为：

$$
\delta(y,N,t) = \arcsin\Bigg[ \sin\big(-\deg2rad(\epsilon(y))\big) \cos\Big(\deg2rad\Big(\Omega (N-1+\tfrac{t}{1440} + S(y)) + \frac{360^\circ}{\pi} e(y) \sin\big(\deg2rad(\Omega (N-1+\tfrac{t}{1440} + P(y))\big)\Big)\Big)\Bigg].
$$

**均时差**

同样地，时间方程相关参数为：

$$
\begin{aligned}
A_e(y) &= -7.52810424 + 0.00009320\, y,\\
A_o(y) &= 10.17530545 - 0.00013295\, y,\\
\phi(y) &= 2.34399278 + 0.00064267\, y,\\
D_0(y) &= \deg2rad\big(6.26628811 - 0.00002763\, y\big),\\
\omega &= 0.01720197,\\
T(y) &= 365.25\, (y-2000).
\end{aligned}
$$

设 $f = N-1 + t/1440$，则 EoT 为：

$$
\Delta t(y,N,t) = A_e(y) \sin D(y,f) + A_o(y) \sin\big(2 D(y,f) + \phi(y)\big),
$$

其中

$$
D(y,f) = D_0(y) + \omega \big(T(y) + f\big).
$$

**最终太阳高度角**

给定地理纬度 $\varphi$、经度 $\lambda$（向东为正）以及时区偏移 $\Delta_{\mathrm{tz}}$（东八区取 $+8$），本地真太阳时对应的小时角 $H$ 为：

$$
\begin{aligned}
\mathrm{TST}(y,N,t) &= t + \Delta t(y,N,t) + 4\lambda - 60\Delta_{\mathrm{tz}},\\
H(y,N,t) &= \deg2rad\Big(\frac{\mathrm{TST}(y,N,t)}{4} - 180\Big).
\end{aligned}
$$

最终可得到太阳高度角：

$$
\alpha(y,N,t) = \arcsin\big(\sin\varphi \sin\delta(y,N,t) + \cos\varphi \cos\delta(y,N,t) \cos H(y,N,t)\big).
$$

该套表达式与上节给出的 Vala 实现一一对应，方便在其他语言中复现或进行进一步分析。

## 验证与对比

### 与公认数值对比

| 物理量 | 优化 (2000 年) | 公认值 (NASA/Meeus) | 误差 |
|--------|----------------|---------------------|------|
| Obliquity (°) | 23.4352 | 23.4393 | -0.0041 |
| Eccentricity | 0.01664 | 0.01671 | -0.00007 |
| Perihelion offset (day) | -2.955 | - | - |
| Solstice offset (day) | 10.216 | - | - |

可见我们的拟合结果与公认基准吻合，所得到的参数是有实际物理意义的。此外，拟合得到的冬至日和近日点偏移项则更好地平衡了平年和闰年的数据，使得公式在不同年份下的表现更加均衡稳定。

### 精度对比（RMSD, °）

扩展上篇验证，新增"优化 Wikipedia"列。测试年 1949-2050，6 地点，每月 15 日 24 小时。

| 方法 | 整体 RMSD | 整月最差 RMSD | 最大绝对误差 |
|------|-----------|-----------|-----------|
| Meeus | 0.0038 | 0.0083 | 0.0122 |
| Fourier | 0.1040 | 0.333 | 0.3372 |
| 原 Wikipedia | 0.1533 | 0.417 | 0.4844 |
| 优化 Wikipedia | 0.0919 | 0.27 | 0.2812 |

|[![#~/img/astronomy/solar-meeus_error_histogram.svg](/img/astronomy/solar-meeus_error_histogram.svg)](/img/astronomy/solar-meeus_error_histogram.svg)|
|:----:|
| Meeus 算法误差分布直方图 |
|[![#~/img/astronomy/solar-fourier_error_histogram.svg](/img/astronomy/solar-fourier_error_histogram.svg)](/img/astronomy/solar-fourier_error_histogram.svg)|
| 傅里叶级数算法误差分布直方图 |
|[![#~/img/astronomy/solar-wikipedia_error_histogram.svg](/img/astronomy/solar-wikipedia_error_histogram.svg)](/img/astronomy/solar-wikipedia_error_histogram.svg)|
| 维基百科算法误差分布直方图 |
|[![#~/img/astronomy/solar-wikiimp_error_histogram.svg](/img/astronomy/solar-wikiimp_error_histogram.svg)](/img/astronomy/solar-wikiimp_error_histogram.svg)|
| 优化 Wikipedia 算法误差分布直方图 |

- **年份稳定性**：优化版在 1949 年 RMSD 0.097°，2050 年 0.061°（稳定）；原版 1949 年 0.109°，2050 年 0.209°。
- **地理普适性**：高纬（Stockholm）优化版 0.082°，原版 0.136°（改善 40%）；新加坡优化版 0.063°，原版 0.101°（改善 38%）。
- **季节稳定性**：优化版月波动小（0.019-0.112°），原版剧烈（0.034-0.197°）。

精度虽显著不及 Meeus，但也明显超原版，百年内可靠。

## 总结

通过引入年线性参数和平衡数据拟合，我们将 Wikipedia 公式从"粗糙近似"升级为"实用高精"模型：精度提升 1.6 倍，在一百年的长时间尺度上稳定性更好，并保持易懂。虽不及 Meeus 的物理深度，但其简单性与物理参数，使之成为日常和教育用途的一个选择。

## 附录：Vala 函数实现

```vala
    /**
     * Calculates solar elevation angles for each minute of the day.
     * Originally based on https://en.wikipedia.org/wiki/Position_of_the_Sun
     * and https://en.wikipedia.org/wiki/Equation_of_time
     * Added year correction and refined parameters by wszqkzqk
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

        // Precompute year-dependent parameters outside loop
        const double OMEGA_DEG_PER_DAY = 360.0 / 365.2422;
        const double OMEGA_D_RAD_PER_DAY = 0.01720197;
        const double TROPICAL_YEAR_DAYS = 365.25;
        double ecc_factor = 360.0 / Math.PI * (0.01749432 + -0.00000043 * year);
        double solstice_offset = -4.95365451 + 0.00758474 * year;
        double perihelion_offset = 16.90763877 + -0.00993146 * year;
        double sin_obliquity_neg = Math.sin ( - (23.68961512 + -0.00012720 * year) * DEG2RAD );
        double tropical_offset = TROPICAL_YEAR_DAYS * (year - 2000.0);
        double eot_dconst = 6.26628811 + -0.00002763 * year;
        double eot_ecc_amp = -7.52810424 + 0.00009320 * year;
        double eot_obli_amp = 10.17530545 + -0.00013295 * year;
        double eot_obli_phase = 2.34399278 + 0.00064267 * year;
        double tst_offset = 4.0 * longitude_deg - 60.0 * timezone_offset_hrs;

        for (int i = 0; i < RESOLUTION_PER_MIN; i += 1) {
            double fractional_day_component = day_of_year - 1 + ((double) i) / RESOLUTION_PER_MIN;
            
            // Declination: sin(δ) = sin(-ε) * cos(λ_approx)
            // where λ_approx = Ω * (N + solstice_offset) + (360/π * e) * sin(Ω * (N + perihelion_offset))
            // Ω = 360 / 365.2422
            double sin_decl = sin_obliquity_neg * Math.cos (
                (OMEGA_DEG_PER_DAY * (fractional_day_component + solstice_offset)
                + ecc_factor * Math.sin (OMEGA_DEG_PER_DAY * (fractional_day_component + perihelion_offset) * DEG2RAD))
                * DEG2RAD
            );
            sin_decl = sin_decl.clamp (-1.0, 1.0);
            double cos_decl = Math.sqrt (1.0 - sin_decl * sin_decl);
            
            // Equation of Time: Δt = A1 * sin(D) + A2 * sin(2D + φ)
            // where D = dconst + ω * (T * (year - 2000) + N), ω = 0.01720197
            double d_rad = eot_dconst + OMEGA_D_RAD_PER_DAY * (tropical_offset + fractional_day_component);
            double eqtime_minutes = eot_ecc_amp * Math.sin (d_rad)
                + eot_obli_amp * Math.sin (2.0 * d_rad + eot_obli_phase);
            
            // True Solar Time and Hour Angle
            double tst_minutes = i + eqtime_minutes + tst_offset;
            double ha_deg = tst_minutes / 4.0 - 180.0;
            double ha_rad = ha_deg * DEG2RAD;
            
            // Zenith distance cosine: cos(φ) = sin(φ_lat) * sin(δ) + cos(φ_lat) * cos(δ) * cos(HA)
            double cos_phi = sin_lat * sin_decl + cos_lat * cos_decl * Math.cos (ha_rad);
            cos_phi = cos_phi.clamp (-1.0, 1.0);
            double phi_rad = Math.acos (cos_phi);
            
            // Solar elevation: α = 90° - φ
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
```
