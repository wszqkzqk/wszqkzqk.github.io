#!/usr/bin/env python3

import os

def unixpath(path):
    return path.replace('\\', '/')

print('本程序将在插入图片的同时，将jpg、png、bmp、gif图片转化为webp格式\n')
localimg = unixpath(os.path.dirname(os.path.dirname(__file__))) + '/img'

def autowebp(imgfile):  # 仅对本地图片使用
    if imgfile.split('.')[-1].lower() in {jpg, png, jpeg, bmp, gif}:
        webpimg = imgfile.split('.')[0] + '.webp'
        os.system('ffmpeg -i "{0}/{1}" "{0}/{2}"'.format(localimg, imgfile, webpimg))
        if os.path.getsize(imgfile) / os.path.getsize(webpimg) >= 1.15: # 如果转码前后的图片体积比大于1.15则取webp,否则仍然取之前的图片
            print('webp格式可以显著减少图片体积，采用webp格式！')
            flag = input('若需要删除源文件请输入"1"，否则请输入"0"（默认"0"）')
            if flag == '1':
                os.remove("{0}/{1}".format(localimg, imgfile))
            return '/img/' + webpimg
        else:
            print('webp格式没有显著减少图片体积，保留原有格式！')
            os.remove("{0}/{1}".format(localimg, webpimg))
            return '/img/' + imgfile

print('请输入该行的图片分栏数：')
n = int(input())
picline = '|'
neckline = '|' + ':----:|'*n
tailline = '|'
for i in range(n):
    print('请输入第{}张图片的地址（默认在/img下，也可输入绝对网址）：'.format(i+1))
    url = input()
    if '://' not in url:
        if '/img/' not in url:
            if url:
                url = autowebp(url)
        else:
            url = autowebp(os.path.basename(url))
    print('请输入点击图片的链接指向（默认为本身）')
    goto = input()
    if not goto:
        goto = url
    if url:
        picline += '[![#~{0}]({0})]({1})|'.format(url, goto)
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
    print('\n已输出到"otherfiles/tmp.md"')
except FileNotFoundError:
    print()
    print(picline)
    print(neckline)
    print(tailline)
