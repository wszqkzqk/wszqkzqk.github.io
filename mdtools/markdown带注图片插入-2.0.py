#!/usr/bin/env python3
print('请输入该行的图片分栏数：')
n = int(input())
picline = '|'
neckline = '|' + ':----:|'*n
tailline = '|'
for i in range(n):
    print('请输入第{}张图片的地址（默认在/img下，也可输入绝对网址）：'.format(i+1))
    url = input()
    imgname = url
    if ('://' not in url) and ('/img/' not in url) and url:
        url = '/img/' + url
    print('请输入点击图片的链接指向（默认为本身）')
    goto = input()
    if not goto:
        goto = url
    if url:
        picline += '[![#~{2}]({0})]({1})|'.format(url, goto, imgname)
    else:
        picline += '    |'
    print('请输入图注：')
    note = input()
    if note:
        tailline += '{}|'.format(note)
    else:
        tailline += '    |'
try:
    print()
    with open("otherfiles/tmp.md", "a", encoding="utf-8") as echo:
        echo.write(picline + '\n')
        print(picline)
        echo.write(neckline + '\n')
        print(neckline)
        echo.write(tailline + '\n')
        print(tailline)
    print('\n已输出到"其他联系/tmp.md"')
except FileNotFoundError:
    print()
    print(picline)
    print(neckline)
    print(tailline)
