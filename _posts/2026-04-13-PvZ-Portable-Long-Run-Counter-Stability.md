---
layout:       post
title:        PvZ-Portable：长期运行稳定性修复——从计数器溢出到浮点精度悬崖
subtitle:     无尽模式数十小时后动画抖动、闪烁异常的根因与系统重构
date:         2026-04-13
author:       wszqkzqk
header-img:   img/games/bg-pvz-portable.webp
catalog:      true
tags:         C++ 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

在调试 PvZ-Portable 的过程中，笔者注意到一类只在**长时间运行**后才会显现的异常：当无尽模式推进到数十小时后，某些周期性动画开始出现肉眼可见的抖动——浓雾的波动不再平滑，水生植物的漂浮动画变得不连续，就连 UI 元素的闪烁节奏也会偶发错乱。

这些问题看似分布在不同子系统，其实根因只有一个：**游戏计数器在不断累加后，首先会触碰到 IEEE 754 `float` 的精度问题；而 `int32_t` 的 signed overflow 则是另一个隐患**。本文将记录笔者如何系统性地重构 PvZ-Portable 中的主计数器与动画相位计算，改进超长期运行的稳定性。

## 浮点精度

PvZ-Portable 的动画系统大量使用 `float` 来计算浓雾波动、弹坑水波、漂浮植物的正弦运动等周期性相位。这些计算的典型模式是：

```cpp
float aTime = mMainCounter * 2.0f * PI / 200.0f;
float aWave = sin(aPos + aTime) * 2.0f;
```

`mMainCounter` 是每帧递增的整数计数器。问题在于，当这个大整数被转成 `float` 并乘以一个系数后，IEEE 754 单精度浮点有限的 **24 位有效尾数** 会让相位的增量逐渐丧失精度。

以漂浮植物为例，每帧增量约为 `2π/200 ≈ 0.0314`。当 `mMainCounter` 增长到约 **1670 万** 时，`float` 在该数量级下的相邻可表示值间距（ULP）会超过这个增量。这意味着相邻两帧的相位输入不再有区别，正弦函数的参数被卡住在更粗粒的近似值上，原本平滑的正弦波会退化为阶梯状抖动。按逻辑帧率 100 FPS 计算，这个临界点出现在运行约 **46 小时** 之后。

还有个更隐蔽的问题：不同动画的缩放系数不同，触达的具体帧数略有差异，但都集中在 **40～50 小时** 这个区间。对于不停使用同一局存档的无尽模式玩家来说，这完全可能在正常游戏中触发。

### 精度衰减时间表

我们可以把漂浮植物当作典型案例，算一算它会如何随时间逐步坏掉。它的相位增量是 `2π/200 ≈ 0.0314`。`float` 的相邻可表示值间距（ULP）在不同数量级下如下：

| 运行时长 | `mMainCounter` | `float` 的 ULP | 等价效果 |
| :--- | :--- | :--- | :--- |
| **~46 小时** | 1.67×10⁷ | 0.0625 | 约 **2 帧** 相位才更新一次，开始出现轻微顿挫 |
| **~93 小时** | 3.34×10⁷ | 0.125 | 约 **4 帧** 一跳，肉眼可见的抽搐 |
| **~7.7 天** | 1.34×10⁸ | 1.0 | 约 **32 帧**（0.3 秒）一跳，已经完全不像平滑动画 |
| **~62 天** | 5.34×10⁸ | 4.0 | 约 **128 帧**（1.3 秒）一跳，像幻灯片 |
| **~248 天**（`int32` 溢出前） | 2.15×10⁹ | 8.0 | 约 **255 帧**（2.5 秒）才抽搐一下 |

也就是说，如果一个玩家真的把游戏挂到 `int32_t` 溢出前夕，荷叶每隔两秒半才会晃动一下。更糟糕的是，第 249 天溢出发生时，有符号 `int` 的 UB 会让相位瞬间跳变成一个完全不可预测的值——即使它此前勉强还能运行，此时也可能行为错乱。

## `int32_t` 溢出的未定义行为

原版引擎使用 `int32_t`（即 `int`）存储 `mMainCounter` 和 `mAppCounter`。`int32_t` 的上限约为 21.47 亿，按 100 FPS 计算约 **248 天** 会触及溢出边界。在 C++ 中，**有符号整数溢出是未定义行为**，编译器可以据此做出任何假设，导致行为不可靠。

`abs(INT_MIN)` 在 C++ 中同样是 UB。旧代码里 `mMainCounter / 8 % 22 - 11` 的实际范围不可能触及 `INT_MIN`，但计数器类型一旦向无符号迁移，类似表达式的语义就会变得更危险：无符号减法下溢会得到一个巨大的正数，此时再套一层 `abs()` 就存在 UB 风险。

## 计数器类型重构

明确了这两个根因后，修复路径就很清晰了：先把所有计数器统一为 `uint32_t`，再在送入 `float` 之前对大周期取模。

### 将主计数器切换为 `uint32_t`

修复的第一步是将 `mMainCounter`（`Board` 类）和 `mAppCounter`（`LawnApp` 类）从 `int32_t` 改为 `uint32_t`。

旧代码：

```cpp
// Board.h
int32_t mMainCounter;

// LawnApp.h
int mAppCounter;
```

修复后：

```cpp
// Board.h
uint32_t mMainCounter;

// LawnApp.h
uint32_t mAppCounter;
```

无符号整数的溢出在 C++ 中是**定义良好的模 2^32 回绕行为**。这不仅彻底消除了 UB 风险，还顺带解决了一些工程上的麻烦：存档同步、跨平台联机、以及时间比较逻辑都因此获得了稳定的行为基线。数值周期性运行，配合前面提到的动画相位取模，回绕到 0 不会产生任何错误——计数器进入了任意时间尺度都**定义正确**的运行状态。

### 统一派生计数器

`Board` 中还存在着 `mEffectCounter`、`mDrawCount`、`mIntervalDrawCountStart`，以及 `PoolEffect` 中的 `mPoolCounter`。这些计数器同样参与周期性动画或时间间隔计算，必须保持一致的类型语义。笔者将它们全部统一为无符号类型：

```cpp
// Board.h
uint32_t mEffectCounter;
uint32_t mDrawCount;
uint32_t mIntervalDrawCountStart;

// PoolEffect.h
unsigned int mPoolCounter;
```

### 存档同步路径的适配

PvZ-Portable 使用自定义的 Portable v4 存档格式。计数器类型变更后，序列化路径必须同步切换为无符号读写。

修改前：

```cpp
c.SyncInt32(theBoard->mMainCounter);
c.SyncInt32(theBoard->mEffectCounter);
```

修改后：

```cpp
c.SyncUInt32(theBoard->mMainCounter);
c.SyncUInt32(theBoard->mEffectCounter);
```

这确保了旧存档的兼容性不会被破坏（位模式不变，只是解释方式明确为无符号），同时消除了读档时可能的符号扩展歧义。

## 动画相位的周期性取模

计数器类型改对了，但这只消除了溢出层面的风险。但无论计数器怎么改，把它直接喂给 `float` 做周期运算，还是因精度问题而出现抖动。真正的办法是，**在向 `float` 转换之前先对大周期取模**，确保输入三角函数的数值始终处于安全精度范围内。

### 浓雾动画（Fog）

浓雾波动由两个周期参数共同决定（900 帧与 500 帧），其最小公倍数为 4500 帧。修复后的代码在转换前先对 4500 取模：

```cpp
constexpr uint32_t FOG_ANIM_PERIOD = 4500;
float aTime = static_cast<float>(mMainCounter % FOG_ANIM_PERIOD) * PI * 2;
```

这保证无论游戏运行多久，`aTime` 的绝对值都不会超过 4500 × 2π ≈ 28274，在 `float` 的精度范围内游刃有余。

### 弹坑水波（Crater）

弹坑在泳池场景下的水波摆动周期为 200 帧：

```cpp
constexpr uint32_t CRATER_ANIM_PERIOD = 200;
float aTime = static_cast<float>(mMainCounter % CRATER_ANIM_PERIOD)
              * (PI * 2.0f / static_cast<float>(CRATER_ANIM_PERIOD));
```

### 宝石迷阵旋转效果

宝石迷阵模式中的扭转动画每 1000 帧旋转一周：

```cpp
constexpr uint32_t BEGHOULED_TWIST_ROTATION_PERIOD = 1000;
float aRotation = -static_cast<float>(mBoard->mMainCounter % BEGHOULED_TWIST_ROTATION_PERIOD)
                  * (2 * PI * 0.001f);
```

### 漂浮植物与咖啡豆

水生植物的漂浮效果，以及咖啡豆的上下波动，也都采用了类似的取模策略。

旧代码直接将整数计数器乘以系数 `aCounter * 0.03f`。修复后改用 `fmod` 在 `double` 精度下先对 `2π` 取模，再降级为 `float`：

```cpp
float aTime = static_cast<float>(
    fmod((mRow * 97.0 + mPlantCol * 61.0 + static_cast<double>(aCounter)) * 0.03,
         2.0 * PI)
);
```

这里要特别小心，因为咖啡豆的相位计算不仅依赖计数器，还叠加了行和列的固定偏移，数值增长更快。

### 泳池波动（PoolEffect）

泳池的水面波纹由多组不同周期的正弦波叠加而成，涉及的周期包括 1600、300、1800、220、3200/3、200、720、640、88 帧等。笔者计算出这些周期的共同周期边界：**316800 帧**，作为主周期取模边界：

```cpp
constexpr unsigned int POOL_PHASE_PERIOD = 316800u;
float aPoolPhase = (mPoolCounter % POOL_PHASE_PERIOD) * PI;
```

同时，PoolEffect 中负责计算焦散纹理的固定点代码里，原先使用 `int` 存储的位移量也被明确为 `unsigned int`，避免了左移运算在 signed 类型上的 UB 风险：

```cpp
// 旧代码
int timeU = x << 17;
int timePool0 = mPoolCounter << 16;

// 修复后
unsigned int timeU = x << 17;
unsigned int timePool0 = mPoolCounter << 16;
```

## 闪烁颜色与 `abs` 的安全性

动画相位的问题解决了，计数器类型变更还牵出了一处接口层面的细枝末节。

`GetFlashingColor` 是游戏中广泛使用的闪烁/高亮颜色插值函数，原先接收 `int theCounter`。当参数改为 `uint32_t` 后，`theCounter % theFlashTime` 变为无符号取模，随后与有符号的中间值相减可能引发符号混乱。

修改前：

```cpp
Color GetFlashingColor(int theCounter, int theFlashTime)
{
    int aTimeAge = theCounter % theFlashTime;
    // ... abs(aTimeInf - aTimeAge) ...
}
```

修改后：

```cpp
Color GetFlashingColor(uint32_t theCounter, int theFlashTime)
{
    int aTimeAge = static_cast<int>(theCounter % static_cast<uint32_t>(theFlashTime));
    // ...
}
```

另一处风险在 `Board::DrawUIBottom` 中。旧代码：

```cpp
int aWaveTime = abs(mMainCounter / 8 % 22 - 11);
```

迁移到 `uint32_t` 后，如果不做显式 `static_cast<int>`，`mMainCounter / 8 % 22 - 11` 会先进行无符号运算，结果小于 11 时会发生下溢，变成一个巨大的正数。修复后：

```cpp
int aWaveTime = std::abs(static_cast<int>((mMainCounter / 8) % 22) - 11);
```

这样不但避免了无符号下溢，也彻底消除了 `abs(INT_MIN)` 的 UB 隐患。

## 数据一览

下表汇总了这次修复涉及的关键计数器及其长期运行特性：

| 计数器 | 旧类型 | 新类型 | 100 FPS 下的环绕/溢出周期 |
| :--- | :--- | :--- | :--- |
| `mMainCounter` | `int32_t` | `uint32_t` | 约 **497 天**（定义良好） |
| `mAppCounter` | `int` | `uint32_t` | 约 **497 天** |
| `mPoolCounter` | `int` | `unsigned int` | 约 **497 天** |
| `mEffectCounter` | `int32_t` | `uint32_t` | 约 **497 天** |
| `mDrawCount` | `int32_t` | `uint32_t` | 约 **497 天** |

而浮点精度问题在取模修复前的表现为：

| 动画效果 | 缩放系数 | 出现可见抖动的预估时长（100 FPS） |
| :--- | :--- | :--- |
| 漂浮植物 | `2π/200` | 约 **46 小时** |
| 浓雾波动 | `2π` | 约 **46～47 小时** |
| 咖啡豆浮动 | `0.03` | 约 **48 小时** |
| 泳池波纹 | `π` | 约 **46 小时** |

现在，所有计数器都改为无符号类型，即使无限递增也不会触发 UB；同时，所有动画的相位输入都被限制在一个安全的周期范围内，避免了长期运行的精度问题。

### 回绕对齐的缺陷

然而，`uint32_t` 的自然回绕周期 `2^32 = 4294967296` 与各动画的取模周期**并不保证对齐**。这意味着在约 497 天后的回绕瞬间，理论上会出现一次相位跳变。

举个例子，漂浮植物的周期是 200 帧。`4294967296 % 200 = 96`，所以回绕时 `% 200` 的结果会从 95 直接跳到 0，而不是正常地走完 96→199。这相当于半个周期的瞬时跳变——严格来说，水生植物上下浮动位置会在那一帧突然跳变。

同理，浓雾的 4500 帧周期也不整除 `2^32`（余数为 796），回绕时同样存在一次跳变。

要彻底消除这个跳变，理论上需要让计数器在所有动画周期的**公倍数**处回绕（比如 {4500, 200, 1000, 316800} 的最小公倍数是 792000 帧），或者让所有动画周期都整除 `2^32`——前者会破坏计数器用于非动画逻辑时的单调性，后者对含有因数 3、5 的周期（如 4500）根本不可能。

所幸，这个跳变只发生在**连续运行 497 天后的一帧**，且不会造成额外的任何破坏。与其引入复杂的全局同步机制，不如坦然接受这个理论上存在、实践中几乎不可见的瑕疵。

## 结语

这次修复的核心启示非常直观，却又极易被忽视：**不要在热路径中将单调递增的大整数直接塞给 `float` 做周期性运算**。对于以帧为单位计时的游戏引擎，24 位浮点尾数是一座真实存在的悬崖——运行约 46 小时后，它就会把平滑的动画变成一顿一顿的抖动。

与此同时，`int32_t` 的 signed overflow 在 C++ 中不是什么回绕到负数那么简单，它是实实在在的未定义行为。将计数器家族统一迁移到 `uint32_t`，不仅修复了 UB，还顺带获得了可预期的环绕语义和跨平台一致性。

PvZ-Portable 作为开源重实现，在处理这类长期运行假设时尤其需要谨慎。原版游戏很多设计可能并不精细，但现代平台上的开源重实现没有理由继承这种隐式的寿命限制。把计数器类型做对、把相位取模做对，才能确保玩家在任何时长下都能获得稳定体验。

## ⚠️ 版权与说明

**重要：本项目仅包含代码引擎，不包含任何游戏素材！**

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中。

*   `main.pak`
*   `properties/` 目录

本项目的源代码以 [**LGPL-3.0-or-later**](https://www.gnu.org/licenses/lgpl-3.0.html) 许可证开源，欢迎学习和贡献。
