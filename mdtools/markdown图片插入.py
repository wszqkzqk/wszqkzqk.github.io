#!/usr/bin/env python
import os
from platform import system
if system() == 'Linux':    # 需要先安装xclip软件包
    def clip(info):
        print(info)
        if os.system('echo "' + info + '" |xclip -selection  c '):
            print('无法调用xclip进行自动复制，请手动复制输出内容；若需要使用自动复制功能，请安装"xclip"软件包！')
        else:
            print('已复制到剪贴板！\n')
elif system() == 'Windows':
    def clip(info):
        print(info)
        os.system('echo "' + info + '" | clip')
        print('已复制到剪贴板！（可能需要手动去除多余的引号）\n')
    
    def unixpath(path):
        return path.replace('\\', '/')
else:
    print(info)
    print('\n操作系统不受支持，无法自动将输出内容复制到剪贴板！请自行复制！')

while 1:
    print('请输入图片地址（默认在./img下，也可输入绝对网址）：')
    url = input()
    imgname = url
    if '://' not in url:
        url = '/img/' + url
    print('请输入点击图片的链接指向（默认为本身）')
    goto = input()
    if not goto:
        goto = url
    clip('[![#~{2}]({0})]({1})'.format(url, goto, imgname))
    print()