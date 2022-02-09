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
    print(info)
    print('\n操作系统不受支持，无法自动将输出内容复制到剪贴板！请自行复制！')

while 1:
    print('请输入化学式（上标需要用"<>"框出）：')
    fml = input()
    temp = ''
    j = 0
    while j < len(fml):
        word = fml[j]
        if '0' <= word <= '9':
            temp += '<sub>' + word + '</sub>'
            j += 1
        elif word == '<':
            temp += '<sup>'
            j += 1
            while fml[j] != '>':
                temp += fml[j]
                j += 1
            else:
                temp += '</sup>'
                j += 1
        else:
            temp += word
            j += 1
    clip(temp)
    print()
