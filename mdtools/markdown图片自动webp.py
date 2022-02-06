#!/usr/bin/env python
import os
from platform import system

if system() == 'Linux':    # 需要先安装xclip软件包
    def clip(info):
        print(info)
        os.system('echo "' + info + '" |xclip -selection  c ')
        print('已复制到剪贴板！\n')
    
    localimg = os.path.dirname(os.path.dirname(__file__)) + '/img'
elif system() == 'Windows':
    def clip(info):
        print(info)
        os.system('echo "' + info + '" | clip')
        print('已复制到剪贴板！（可能需要手动去除多余的引号）\n')
    
    def unixpath(path):
        return path.replace('\\', '/')
    
    localimg = unixpath(os.path.dirname(os.path.dirname(__file__))) + '/img'
else:
    print('操作系统不受支持！')
    exit()

print('本程序将在插入图片的同时，将jpg、png、bmp、gif图片转化为webp格式\n')

def autowebp(imgfile):  # 仅对本地图片使用
    if imgfile.split('.')[-1].lower() in {'jpg', 'png', 'jpeg', 'bmp', 'gif'}:
        webpimg = imgfile.split('.')[0] + '.webp'
        if not os.path.exists("{0}/{1}".format(localimg, webpimg)):
            os.system('ffmpeg -i "{0}/{1}" "{0}/{2}"'.format(localimg, imgfile, webpimg))
            if os.path.getsize("{0}/{1}".format(localimg, imgfile)) / os.path.getsize("{0}/{1}".format(localimg, webpimg)) >= 1.15: # 如果转码前后的图片体积比大于1.15则取webp,否则仍然取之前的图片
                print('webp格式可以显著减少图片体积，采用webp格式！')
                flag = input('若需要删除源文件请输入"1"，否则请输入"0"（默认"0"）：\n')
                if flag == '1':
                    os.remove("{0}/{1}".format(localimg, imgfile))
                return '/img/' + webpimg
            else:
                print('webp格式没有显著减少图片体积，保留原有格式！')
                os.remove("{0}/{1}".format(localimg, webpimg))
                return '/img/' + imgfile
        else:
            todo = input('检测到已有对应文件名的webp文件存在，若需要直接使用已存在文件请输入"0"，覆盖请输入"1"，需要重命名请输入"2"（默认"0"）:\n')
            if todo == '1':
                os.system('ffmpeg -i "{0}/{1}" "{0}/{2}"'.format(localimg, imgfile, webpimg))
                if os.path.getsize("{0}/{1}".format(localimg, imgfile)) / os.path.getsize("{0}/{1}".format(localimg, webpimg)) >= 1.15: # 如果转码前后的图片体积比大于1.15则取webp,否则仍然取之前的图片
                    print('webp格式可以显著减少图片体积，采用webp格式！')
                    flag = input('若需要删除源文件请输入"1"，否则请输入"0"（默认"0"）：\n')
                    if flag == '1':
                        os.remove("{0}/{1}".format(localimg, imgfile))
                    return '/img/' + webpimg
                else:
                    print('webp格式没有显著减少图片体积，保留原有格式！')
                    os.remove("{0}/{1}".format(localimg, webpimg))
                    return '/img/' + imgfile
            elif todo == '2':
                webpimg = input('请输入目标webp文件名（默认为originalname-new.webp）：\n')
                os.system('ffmpeg -i "{0}/{1}" "{0}/{2}"'.format(localimg, imgfile, webpimg))
                if os.path.getsize("{0}/{1}".format(localimg, imgfile)) / os.path.getsize("{0}/{1}".format(localimg, webpimg)) >= 1.15: # 如果转码前后的图片体积比大于1.15则取webp,否则仍然取之前的图片
                    print('\nwebp格式可以显著减少图片体积，采用webp格式！')
                    flag = input('若需要删除源文件请输入"1"，否则请输入"0"（默认"0"）：\n')
                    if flag == '1':
                        os.remove("{0}/{1}".format(localimg, imgfile))
                    return '/img/' + webpimg
                else:
                    print('\nwebp格式没有显著减少图片体积，保留原有格式！')
                    os.remove("{0}/{1}".format(localimg, webpimg))
                    return '/img/' + imgfile
            else:
                return '/img/' + webpimg

while 1:
    print('请输入图片地址（默认在/img下，也可输入绝对网址）：')
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
    clip('[![#~{0}]({0})]({1})'.format(url, goto))
    print()