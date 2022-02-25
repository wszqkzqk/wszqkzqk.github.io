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

elif system() == 'Windows': # 增加Msys2或Cygwin判断，如果可以执行Unix命令就直接执行更方便的Unix命令
    def unixpath(path):
        return path.replace('\\', '/')
    
    def cleanpath(path):
        path = path.replace('\\', '/')
        if path[-1] == '/':
            return path[0:-1]
        else:
            return path
    
    from fnmatch import fnmatch
    for i in os.getenv('path').split(';'):
        if i:
            targetFile = cleanpath(i) + '/echo.exe'
            if fnmatch(targetFile, '*/bin/echo.exe') or fnmatch(targetFile, '*MSYS2*echo.exe'):
                if os.path.exists(targetFile):
                    def clip(info):
                        print(info)
                        os.system('{} "'.format(targetFile) + info + '"| clip')
                        print('已复制到剪贴板！\n')
                    break
    else:
        def clip(info):
            print(info)
            os.system('echo "' + info + '"| clip')
            print('已复制到剪贴板！（可能需要手动去除多余的引号）\n')

else:
    print(info)
    print('\n操作系统不受支持，无法自动将输出内容复制到剪贴板！请自行复制！')

while 1:
    print('请输入图片地址（默认在./img下，也可输入绝对网址或带有/img的完整地址）：')
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