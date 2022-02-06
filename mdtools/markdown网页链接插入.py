#!/usr/bin/env python
import os
from platform import system
if system() == 'Linux':    # 需要先安装xclip软件包
    def clip(info):
        print(info)
        os.system('echo "' + info + '" |xclip -selection  c ')
        print('已复制到剪贴板！')
elif system() == 'Windows':
    def clip(info):
        print(info)
        os.system('echo "' + info + '" | clip')
        print('已复制到剪贴板！（可能需要手动去除多余的引号）')
else:
    print('操作系统不受支持！')
    exit()
while 1:
    print('请输入链接网址：')
    url = input()
    print('请输入显示文字（默认为网址本身）：')
    words = input()
    if not words:
        words = url
    clip('[{0}]({1})'.format(words, url))
    print()
 
