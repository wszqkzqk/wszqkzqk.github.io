---
layout:     post
title:      Python多进程与Windows下exe封装的踩坑实践
subtitle:   multiprocessing、pyinstaller、nuitka的尝试
date:       2022-01-20
author:     星外之神
header-img: img/nuitka-pyinstaller.webp
catalog:    true
tags:       python
--- 



## 前言

由于现在电脑CPU的单核性能提升已经遇到瓶颈，最近AMD与Intel的处理器也通过堆核来大幅提高性能，主流处理器早已达到了达到了8核16线程。因此，合理利用好多核性能对程序运行速度的提升非常重要。最近我打算简单体验一下Python的`multiprocessing`库中的多进程功能～～～

在摸鱼过程中，顺便学习了一下两个打包工具——`nuitka`和`pyinstaller`的使用（当然，我尝试打包了Windows版本，由于Linux的大多数发行版均已经预装Python，并没有什么打包的必要）

## 多进程踩坑经历

### 应用场景选择

在尝试`multiprocessing`库之前首先应当选择一个合适的应用场景，要求计算处理的对象可以分成若干块并行计算。我选择的是数值积分，因为数值积分是将积分区间分割成很多小段，求出每个小段的面积之后再相加。求面积的过程是相互独立的，不依赖之前的结果，计算任务也基本上是重复算小段面积和累加，所以可以将大的积分区间分成若干个小区间，分别求出每个区间的值，最后再相加即可。这种计算任务写成多进程比较方便

### 代码

#### 单进程的代码

其实选择数值积分器这个应用还有一个原因，那就是单进程积分器的代码我以前写过🤪🤪🤪🤪🤪🤪

为了提高精度，我这里没有采用矩形法（常函数）或梯形法（一次函数）进行拟合，而是使用了辛普森法（二次函数）拟合

``` python
#!/usr/bin/env python3

from time import time
from math import *
#   按照习惯名称对部分函数定义别名

def ln(x):
    return log(x)
def lg(x):
    return log(x, 10)
def arcsin(x):
    return asin(x)
def arccos(x):
    return acos(x)
def arctan(x):
    return atan(x)
def arcsinh(x):
    return asinh(x)
def arccosh(x):
    return acosh(x)
def arctanh(x):
    return atanh(x)
print('''       积分器 <一个简单的数值积分工具>
    Copyright (C) 2021-2022 星外之神 <wszqkzqk@qq.com>

注意：三角函数请先化成正弦、余弦、正切及相应的反三角函数（现已支持双曲三角函数及对应的反三角函数）
     请务必使用半角符号；圆周率请用"pi"表示；自然对数的底数请用"e"表示
     请用"*""/"表示乘除，"**"表示乘方，"abs"表示绝对值，"ln"或"log"表示自然对数，"lg"表示常用对数，"log(m, n)"表示m对于底数n的对数
请输入被积函数（用x表示自变量）：''')   # 预备信息

fx = input()
print('请输入积分的下限：')
start = eval(input())   # 使用eval函数，支持输入表达式
print('请输入积分的上限：')
end = eval(input())
print('请输入分割数（由于浮点数值运算具有不精确性，分割数过大反而可能增大误差）')
block = int(input())
calcstart = time()
length = (end - start) / block
halflength = length / 2
out = 0
x = start
temp2 = eval(fx)    # 初始化x与temp2，以便后续让temp0调用上一次的temp2的值，可以减小运算量

for i in range(1, block + 1):   # 积分运算

    temp0 = temp2
    x += halflength
    temp1 = eval(fx)
    x = start + i*length    # 浮点运算中，乘积误差比累加小，此处用乘法虽然降低了速度但是提高了准确度

    temp2 = eval(fx)
    temp = (temp0 + 4*temp1 + temp2) / 6
    out += temp*length
print('\n完成！计算耗时：{}s'.format(time() - calcstart))
print('数值积分运算结果为：')
print(out)

input('\n请按回车键退出')
```
### 改成多线程

我这里选择了的是`multiprocessing`中的`Pool`进行多进程运算，`Pool`能为我的程序提供很多便利：
- 