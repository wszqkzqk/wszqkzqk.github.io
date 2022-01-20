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
calcstart = time()  # 输入结束，计算开始，计时

length = (end - start) / block
halflength = length / 2
out = 0
x = start
temp2 = eval(fx)    # 初始化x与temp2，以便后续让temp0调用上一次的temp2的值，可以减小运算量

for i in range(1, block + 1):   # 积分运算，辛普森法

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
### 改为多进程

我这里选择了的是`multiprocessing`中的`Pool`进行多进程运算，`Pool`能为我的程序提供很多便利：
- 方便批量建立进程
- 内置了`Pool(n).map()`（仅支持一个参数）和`Pool(n).starmap()`（支持多个参数）函数，是`map()`函数的进程池版本，可以多进程地对可迭代对象进行目标函数操作，并返回`map`对象
- 返回对象处理方便，只需要套一层`sum()`函数就能得到最终结果

#### 定义积分函数

由于`Pool.starmap()`需要输入函数，所以需要定义每一个进程的积分函数：

``` python
# 用于积分的函数

def integration(blockstart, blockend):
    out = 0
    x = start + blockstart*length
    temp2 = eval(fx)    # 初始化x与temp2，以便后续让temp0调用上一次的temp2的值，可以减小运算量

    for i in range(blockstart + 1, blockend + 1):
        temp0 = temp2
        x += halflength
        temp1 = eval(fx)
        x = start + i*length    # 浮点运算中，乘积误差比累加小，此处用乘法虽然降低了速度但是提高了准确度

        temp2 = eval(fx)
        temp = (temp0 + 4*temp1 + temp2) / 6
        out += temp*length
    return out
```
#### 进程数与区间分段

当然，还需要将积分区间分成若干段，段数应当与进程数匹配。为了充分利用CPU各个虚拟核心算力，可以先调用`from os import cpu_count`再通过`n = cpu_count()`获取CPU的线程数以设置进程数，也可以设定其他合理的进程数（如物理核心数等）

``` python
from os import cpu_count
n = cpu_count() # 默认为设备的逻辑核心数

tile = int(block / n)
# 进行分段，以便分进程计算

tilestart = 0
obj = [0]
for i in range(n):
    tilestart += tile
    obj.append(tilestart)
```

#### 初版整体代码

```python
from time import time
from os import cpu_count
n = cpu_count()    # 默认为设备的逻辑核心数
from multiprocessing import Pool
from math import *
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
print('''注意：三角函数请先化成正弦、余弦、正切及相应的反三角函数（现已支持双曲三角函数及对应的反三角函数）
    请务必使用半角符号；圆周率请用"pi"表示；自然对数的底数请用"e"表示
    请用"*""/"表示乘除，"**"表示乘方，"abs"表示绝对值，"ln"或"log"表示自然对数，"lg"表示常用对数，"log(m, n)"表示m对于底数n的对数
请输入被积函数（用x表示自变量）：''')
fx = input()
print('请输入积分的下限：')
start = eval(input())
print('请输入积分的上限：')
end = eval(input())
print('请输入分割数（建议为CPU逻辑核心数的正整数倍；由于浮点数值运算具有不精确性，分割数过大反而可能增大误差）：')
block = int(input())
calcstart = time()
length = (end - start) / block
halflength = length / 2
tile = int(block / n)

# 用于积分的函数
def integration(blockstart):
    out = 0
    x = start + blockstart*length
    temp2 = eval(fx)    # 初始化x与temp2，以便后续让temp0调用上一次的temp2的值，可以减小运算量
    if blockstart == tilestart:
        blockend = block
    else:
        blockend = blockstart + tile
    for i in range(blockstart + 1, blockend + 1):
        temp0 = temp2
        x += halflength
        temp1 = eval(fx)
        x = start + i*length    # 浮点运算中，乘积误差比累加小，此处用乘法虽然降低了速度但是提高了准确度
        temp2 = eval(fx)
        temp = (temp0 + 4*temp1 + temp2) / 6
        out += temp*length
    return out

# 进行分段，以便分线程计算
tilestart = 0
obj = [0]
for i in range(n):
    tilestart += tile
    obj.append(tilestart)

# 分线程计算
with Pool(n) as pool:
        out = sum(pool.map(integration, obj))

# 显示输出
print('\n完成！计算耗时：{} s'.format(time() - calcstart))
print('数值积分运算结果为：')
print(out)
```

### 初版代码运行结果

以上代码在我的Linux平台上运行毫无问题：

|[![#~Linux-integ-single-multi.webp](/img/Linux-integ-single-multi.webp)](/img/Linux-integ-single-multi.webp)|
|----|
|Linux下单进程与多进程程序效率对比：在100 0000次分割的高计算量下，多进程程序效率是单进程程序的7.5倍|

但是在Windows下会出现以下情况：

|[![#~integrator-windows-bug.webp](/img/integrator-windows-bug.webp)](/img/integrator-windows-bug.webp)|
|----|
|  Windows平台下各个子进程从头执行程序，并非只执行目标函数  |

如上图所示，Windows下