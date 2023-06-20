---
layout:     post
title:      Markdown Math 测试
subtitle:   在Markdown中使用数学公式
date:       2023-06-20
author:     wszqkzqk
header-img: img/bg-mountain-darken.webp
catalog:    true
tags:       开源软件
---

## 前言

> 本文主要讨论在Markdown中使用数学公式的方法

## 方法

Markdown中使用数学公式的方法有很多，这里主要介绍两种方法。

### 使用MathJax

在Markdown中使用MathJax的方法是在Markdown文件的头部添加以下内容：

```markdown
<script type="text/javascript" src="https://cdn.bootcss.com/mathjax/2.7.5/latest.js?config=TeX-AMS-MML_HTMLorMML"></script>
```

然后就可以在Markdown中使用MathJax了，例如：

```markdown
$$
\begin{aligned}
\frac{\partial \mathcal{L}}{\partial \mathbf{w}} &= \frac{\partial}{\partial \mathbf{w}} \left( \frac{1}{2} \mathbf{w}^T \mathbf{w} + C \sum_{i=1}^n \xi_i - \sum_{i=1}^n \alpha_i \left( y_i \mathbf{w}^T \mathbf{x}_i - 1 + \xi_i \right) - \sum_{i=1}^n \mu_i \xi_i \right) \\
&= \mathbf{w} - \sum_{i=1}^n \alpha_i y_i \mathbf{x}_i = 0
\end{aligned}
$$
```

效果如下：

<script type="text/javascript" src="https://cdn.bootcss.com/mathjax/2.7.5/latest.js?config=TeX-AMS-MML_HTMLorMML"></script>

$$
\begin{aligned}
\frac{\partial \mathcal{L}}{\partial \mathbf{w}} &= \frac{\partial}{\partial \mathbf{w}} \left( \frac{1}{2} \mathbf{w}^T \mathbf{w} + C \sum_{i=1}^n \xi_i - \sum_{i=1}^n \alpha_i \left( y_i \mathbf{w}^T \mathbf{x}_i - 1 + \xi_i \right) - \sum_{i=1}^n \mu_i \xi_i \right) \\
&= \mathbf{w} - \sum_{i=1}^n \alpha_i y_i \mathbf{x}_i = 0
\end{aligned}
$$


### 使用KaTeX

在Markdown中使用KaTeX的方法是在Markdown文件的头部添加以下内容：

```markdown
<link rel="stylesheet" href="https://cdn.bootcss.com/KaTeX/0.10.0/katex.min.css">
<script src="https://cdn.bootcss.com/KaTeX/0.10.0/katex.min.js"></script>
```

然后就可以在Markdown中使用KaTeX了，例如：

```markdown
$$
\begin{aligned}
\frac{\partial \mathcal{L}}{\partial \mathbf{w}} &= \frac{\partial}{\partial \mathbf{w}} \left( \frac{1}{2} \mathbf{w}^T \mathbf{w} + C \sum_{i=1}^n \xi_i - \sum_{i=1}^n \alpha_i \left( y_i \mathbf{w}^T \mathbf{x}_i - 1 + \xi_i \right) - \sum_{i=1}^n \mu_i \xi_i \right) \\
&= \mathbf{w} - \sum_{i=1}^n \alpha_i y_i \mathbf{x}_i = 0
\end{aligned}
$$
```

效果如下：

<link rel="stylesheet" href="https://cdn.bootcss.com/KaTeX/0.10.0/katex.min.css">
<script src="https://cdn.bootcss.com/KaTeX/0.10.0/katex.min.js"></script>

$$
\begin{aligned}
\frac{\partial \mathcal{L}}{\partial \mathbf{w}} &= \frac{\partial}{\partial \mathbf{w}} \left( \frac{1}{2} \mathbf{w}^T \mathbf{w} + C \sum_{i=1}^n \xi_i - \sum_{i=1}^n \alpha_i \left( y_i \mathbf{w}^T \mathbf{x}_i - 1 + \xi_i \right) - \sum_{i=1}^n \mu_i \xi_i \right) \\
&= \mathbf{w} - \sum_{i=1}^n \alpha_i y_i \mathbf{x}_i = 0
\end{aligned}
$$

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
* 累积：`\int_{下标}^{上标}`
  * 例如：`\int_{0}^1`
  * 效果：$\int_{0}^1$
* 矩阵：`\begin{aligned}...\end{aligned}`
  * 例如：`\begin{aligned}...\end{aligned}`
  * 效果：$\begin{aligned}...\end{aligned}$
* 函数：`\sin`、`\cos`、`\tan`、`\cot`、`\sec`、`\csc`、`\arcsin`、`\arccos`、`\arctan`、`\sinh`、`\cosh`、`\tanh`、`\coth`、`\log`、`\ln`、`\lg`、`\arg`、`\min`、`\max`、`\lim`、`\liminf`、`\limsup`、`\exp`、`\det`、`\dim`、`\mod`、`\gcd`、`\deg`、`\hom`、`\ker`、`\Pr`、`\sup`、`\inf`
  * 例如：`\sin`
  * 效果：$\sin$
* n次方根：`\sqrt[n]{被开方数}`
  * 例如：`\sqrt[3]{2}`
  * 效果：$\sqrt[3]{2}$
