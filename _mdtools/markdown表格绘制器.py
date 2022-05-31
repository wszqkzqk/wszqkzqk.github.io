#!/usr/bin/env python
from fnmatch import fnmatch
def pic(x):    #图片格式转化
    if '://' in x:
        return '[![#~{1}]({0})]({0})'.format(x)
    else:
        return '[![#~{1}]({0}{1})]({0}{1})'.format('/img/', x)
def scientificnum(s):    #读取科学计数法含义
    s = s.replace('×10', 'e', 1)
    s = s.replace('*10', 'e', 1)
    return eval(s)
print('请输入表格的标题栏内容:')
title = input().split()
tit = '|  '
neck = '|  '
for i in range(len(title)):
    tit += title[i] + '  |  '
    neck += '----  |  '
print('考虑到博客的表格中有很多化学式，请指出表格的哪些栏需要将数字下标化与电荷上标化?（没有请回车）')
down = {int(i)-1 for i in input().split()}
print('请指出哪些栏需要按照科学计数法进行格式转化（没有请回车）')
scien = {int(i)-1 for i in input().split()}
print('请逐行输入表格内容：\n-    内容结束后请直接回车\n-    上标前后请用<>标出\n-    插图请用"#~"+文件名或地址（由于插图量大不方便每张询问webp化，若需要转化为webp格式请事先进行）:')
content = []
i = input().split()
while i:
    content.append(i)
    i = input().split()
print('若需要排序请输入根据表格哪一栏排序（否则直接回车）')
request = input()
if request:
    if int(request)-1 in scien:
        try:
            content = sorted(content, key = lambda x: scientificnum(x[int(request)-1]))
        except (TypeError, NameError, SyntaxError):
            content = sorted(content, key = lambda x: x[int(request)-1])
    else:
        try:
            content = sorted(content, key = lambda x: eval(x[int(request)-1]))
        except (TypeError, NameError, SyntaxError):
            content = sorted(content, key = lambda x: x[int(request)-1])
tab = []
for info in content:    #输入与基本格式处理
    out = '|  '
    for i in range(len(info)):
        if fnmatch(info[i], '#~*'):
            info[i] = pic(info[i][2:])
            out += info[i] + '  |  '
            continue
        if i in scien:
            if '×10' in info[i]:
                info[i] = info[i].replace('×10', '×10<sup>', 1)
                info[i] += '</sup>'
            elif '*10' in info[i]:
                info[i] = info[i].replace('*10', '×10<sup>', 1)
                info[i] += '</sup>'
            elif 'e' in info[i]:
                info[i] = info[i].replace('e', '×10<sup>', 1)
                info[i] += '</sup>'
        if i in down:
            temp = ''
            j = 0
            while j < len(info[i]):
                word = info[i][j]
                if '0' <= word <= '9':
                    temp += '<sub>' + word + '</sub>'
                    j += 1
                elif word == '<':
                    temp += '<sup>'
                    j += 1
                    while info[i][j] != '>':
                        temp += info[i][j]
                        j += 1
                    else:
                        temp += '</sup>'
                        j += 1
                else:
                    temp += word
                    j += 1
            else:
                info[i] = temp
        out += info[i] + '  |  '
    tab.append(out)
#显示及输出到文件
try:
    with open("otherfiles/tmp.md", "a", encoding="utf-8") as echo:
        echo.write(tit + '\n')
        print(tit)
        echo.write(neck + '\n')
        print(neck)
        for i in tab:
            echo.write(i + '\n')
            print(i)
    print('完成！输出表格见"otherfiles/tmp.md"')
except FileNotFoundError:
    print('\n')
    print(tit)
    print(neck)
    for i in tab:
        print(i)