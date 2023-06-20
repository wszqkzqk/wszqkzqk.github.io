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
> $\Gamma$、$\iota$、$\sigma$、$\phi$、$\upsilon$、$\Pi$、$\Bbbk$、$\heartsuit$、$\int$、$\oint$

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
