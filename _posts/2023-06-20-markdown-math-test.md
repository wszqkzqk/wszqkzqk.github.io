---
layout:     post
title:      Markdown Math 及 mhchem 测试
subtitle:   在 Markdown 中使用数学公式及化学式
date:       2023-06-20
author:     wszqkzqk
header-img: img/bg-mountain-darken.webp
catalog:    true
tags:       开源软件 化学
---

## 前言

> 本文主要讨论在 Markdown 中使用数学公式及化学式的方法

## MathJax

在 Markdown 中使用 MathJax 的方法是在 Markdown 文件的头部添加以下内容：

```markdown
<script src="https://cdn.mathjax.org/mathjax/latest/MathJax.js?config=TeX-AMS-MML_HTMLorMML" type="text/javascript"></script>
<script type="text/x-mathjax-config">
    MathJax.Hub.Config({
        tex2jax: {
        skipTags: ['script', 'noscript', 'style', 'textarea', 'pre'],
        inlineMath: [['$','$']]
        }
    });
</script>
```

然后就可以在 Markdown 中使用 MathJax 了，例如：

```markdown
$$
\begin{aligned}
\frac{\partial \mathcal{L}}{\partial \mathbf{w}} &= \frac{\partial}{\partial \mathbf{w}} \left( \frac{1}{2} \mathbf{w}^T \mathbf{w} + C \sum_{i=1}^n \xi_i - \sum_{i=1}^n \alpha_i \left( y_i \mathbf{w}^T \mathbf{x}_i - 1 + \xi_i \right) - \sum_{i=1}^n \mu_i \xi_i \right) \\
&= \mathbf{w} - \sum_{i=1}^n \alpha_i y_i \mathbf{x}_i = 0
\end{aligned}
$$
```

效果如下：

$$
\begin{aligned}
\frac{\partial \mathcal{L}}{\partial \mathbf{w}} &= \frac{\partial}{\partial \mathbf{w}} \left( \frac{1}{2} \mathbf{w}^T \mathbf{w} + C \sum_{i=1}^n \xi_i - \sum_{i=1}^n \alpha_i \left( y_i \mathbf{w}^T \mathbf{x}_i - 1 + \xi_i \right) - \sum_{i=1}^n \mu_i \xi_i \right) \\
&= \mathbf{w} - \sum_{i=1}^n \alpha_i y_i \mathbf{x}_i = 0
\end{aligned}
$$

## 默认化配置

如果不想在每篇博客中都添加 MathJax 的配置，可以在`_include/head.html`的`<head>`与`</head>`之间插入以下内容：

```html
<script src="https://cdn.mathjax.org/mathjax/latest/MathJax.js?config=TeX-AMS-MML_HTMLorMML" type="text/javascript"></script>
<script type="text/x-mathjax-config">
    MathJax.Hub.Config({
        tex2jax: {
        skipTags: ['script', 'noscript', 'style', 'textarea', 'pre'],
        inlineMath: [['$','$']]
        }
    });
</script>
```

## 部分符号及其含义

* 指数：`^`
  * 例如：`x^2`
    * 效果：$x^2$
* 下标：`_`
  * 例如：`x_1`
    * 效果：$x_1$
* 分数：`\frac{分子}{分母}`
  * 例如：`\frac{1}{2}`
    * 效果：$\frac{1}{2}$
* 开方：`\sqrt{被开方数}`
  * 例如：`\sqrt{2}`
    * 效果：$\sqrt{2}$
* 累加：`\sum_{下标}^{上标}`
  * 例如：`\sum_{i=1}^n`
    * 效果：$\sum_{i=1}^n$
* 累乘：`\prod_{下标}^{上标}`
  * 例如：`\prod_{i=1}^n`
    * 效果：$\prod_{i=1}^n$
* 积分：`\int_{下标}^{上标}`
  * 例如：`\int_{0}^1`
    * 效果：$\int_{0}^1$
* 矩阵：`\begin{aligned}...\end{aligned}`
  * 例如：`\begin{aligned}...\end{aligned}`
    * 效果：$\begin{aligned}...\end{aligned}$
* 函数等符号：`\sin`、`\cos`、`\tan`、`\cot`、`\sec`、`\csc`、`\arcsin`、`\arccos`、`\arctan`、`\sinh`、`\cosh`、`\tanh`、`\coth`、`\log`、`\ln`、`\lg`、`\arg`、`\min`、`\max`、`\lim`、`\liminf`、`\limsup`、`\exp`、`\det`、`\dim`、`\mod`、`\gcd`、`\deg`、`\hom`、`\ker`、`\Pr`、`\sup`、`\inf`
  * 效果：$\sin$、$\cos$、$\tan$、$\cot$、$\sec$、$\csc$、$\arcsin$、$\arccos$、$\arctan$、$\sinh$、$\cosh$、$\tanh$、$\coth$、$\log$、$\ln$、$\lg$、$\arg$、$\min$、$\max$、$\lim$、$\liminf$、$\limsup$、$\exp$、$\det$、$\dim$、$\gcd$、$\deg$、$\hom$、$\ker$、$\Pr$、$\sup$、$\inf$
* n次方根：`\sqrt[n]{被开方数}`
  * 例如：`\sqrt[3]{2}`
    * 效果：$\sqrt[3]{2}$

## 化学式支持

使用拓展的 MathJax，可以方便地支持化学式的显示，只需要将插入内容换成：

```html
<script>
  window.MathJax = {
    tex: {
      inlineMath: [['$', '$']],
      packages: {'[+]': ['mhchem']}
    },
    loader: {load: ['[tex]/mhchem']},
    svg: {
      fontCache: 'global'
    }
  };
</script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
```

其中`svg:{...}`的内容是指定 svg 字体缓存为全局模式，减少开销。

* 化学符号：`\ce{化学式}`
  * 例如：`\ce{H2O}`
    * 效果：$\ce{H2O}$
  * 例如： `\ce{^{227}_{90}Th}`
    * 手动上下标
    * 效果：$\ce{^{227}_{90}Th}$
  * 例如：`\ce{2 Cr^2+ + 4 CH3COO^− + 2 H2O -> Cr2(CH3COO)4·2H2O↓}`
    * `->`表示反应箭头
    * 效果：$\ce{2 Cr^2+ + 4 CH3COO^− + 2 H2O -> Cr2(CH3COO)4·2H2O↓}$
  * 例如：`\ce{3 [Re(CN)8]^2- + 2 [Co(NH3)6]^3+ -> [Co(NH3)6]2[Re(CN)8]3 v}`
    * 可以用` v`表示沉淀
    * 效果：$\ce{3 [Re(CN)8]^2- + 2 [Co(NH3)6]^3+ -> [Co(NH3)6]2[Re(CN)8]3 v}$
  * 例如：`\ce{2 Co(CO)4− + 2 NO + 2 H2O -> 2 Co(NO)(CO)3 + 2 Co + 2 OH− + H2}`
    * 效果：$\ce{2 Co(CO)4− + 2 NO + 2 H2O -> 2 Co(NO)(CO)3 + 2 Co + 2 OH− + H2}$
  * 例如：`\ce{C2B7H11^2- + Re(CO)5Br ->[\ce{THF}] [(π-C2B7H11)Re(CO)3]− + Br− + 2 CO}`
    * 在`->`后面加上`\ce{}`可以表示反应条件
    * 效果：$\ce{C2B7H11^2- + Re(CO)5Br ->[\ce{THF}] [(π-C2B7H11)Re(CO)3]− + Br− + 2 CO}$
  * 例如：`\ce{MnO4− + OH− → MnO4^2− + 1/2O2 ^ + H2O}`
    * 可以用` ^`表示气体
    * 效果：$\ce{MnO4− + OH− → MnO4^2− + 1/2O2 ^ + H2O}$

其他有趣的例子：
* 热化学：
  * `C_p[\ce{H2O(l)}] = \pu{75.3 J // mol K}`
  * $C_p[\ce{H2O(l)}] = \pu{75.3 J // mol K}$
  * `\ce{$K = \frac{[\ce{Hg^2+}][\ce{Hg}]}{[\ce{Hg2^2+}]}$}`
  * $\ce{$K = \frac{[\ce{Hg^2+}][\ce{Hg}]}{[\ce{Hg2^2+}]}$}$
* 各种箭头：
  * `\ce{A -> B}` $\ce{A -> B}$
  * `\ce{A <- B}` $\ce{A <- B}$
  * `\ce{A <=> B}` $\ce{A <=> B}$
  * `\ce{A <--> B}` $\ce{A <--> B}$
  * `\ce{A <<=> B}` $\ce{A <<=> B}$
  * `\ce{A <=>> B}` $\ce{A <=>> B}$
  * `\ce{A ->[{text above}][{text below}] B}` $\ce{A ->[{text above}][{text below}] B}$
  * `\ce{A ->[$x$][$x_i$] B}` $\ce{A ->[$x$][$x_i$] B}$
* 相态标注：
  * `\ce{NaOH_{(aq,$\infty$)}}` $\ce{NaOH_{(aq,$\infty$)}}$
* 配位化学：
  * `\ce{[Pt(\eta^2-C2H4)Cl3]-}` $\ce{[Pt(\eta^2-C2H4)Cl3]-}$
  * `\ce{$cis${-}[PtCl2(NH3)2]}` $\ce{$cis${-}[PtCl2(NH3)2]}$
* 核化学：
  * `\ce{^40_18Ar + \gamma{} + \nu_e}` $\ce{^40_18Ar + \gamma{} + \nu_e}$
* 键合：
  * `\ce{A-B=C#D}` $\ce{A-B=C#D}$
  * `\ce{A\bond{~}B\bond{~-}C}` $\ce{A\bond{~}B\bond{~-}C}$
  * `\ce{A\bond{~--}B\bond{~=}C\bond{-~-}D}` $\ce{A\bond{~--}B\bond{~=}C\bond{-~-}D}$
  * `\ce{A\bond{...}B\bond{....}C}` $\ce{A\bond{...}B\bond{....}C}$
  * `\ce{A\bond{->}B\bond{<-}C}` $\ce{A\bond{->}B\bond{<-}C}$
* 氧化态
  * `\ce{Fe^{II}Fe^{III}2O4}` $\ce{Fe^{II}Fe^{III}2O4}$
* 自由基等
  * `\ce{NO^{(2.)-}}` $\ce{NO^{(2.)-}}$
* 复杂组成
  * `\ce{Li^x_{Li,1-2x}Mg^._{Li,x}$V$'_{Li,x}Cl^x_{Cl}}` $\ce{Li^x_{Li,1-2x}Mg^._{Li,x}$V$'_{Li,x}Cl^x_{Cl}}$
* 有机基团
  * `\ce{n-Pr}` $\ce{n-Pr}$
* 科学记数法
  * `\pu{6.02e23}` $\pu{6.02e23}$
  * `\pu{6.02E23}` $\pu{6.02E23}$
* 性质描述
  * `\ce{Hg^2+ ->[I-]  $\underset{\mathrm{red}}{\ce{HgI2}}$  ->[I-]  $\underset{\mathrm{red}}{\ce{[Hg^{II}I4]^2-}}$}`
  * $\ce{Hg^2+ ->[I-]  $\underset{\mathrm{red}}{\ce{HgI2}}$  ->[I-]  $\underset{\mathrm{red}}{\ce{[Hg^{II}I4]^2-}}$}$
