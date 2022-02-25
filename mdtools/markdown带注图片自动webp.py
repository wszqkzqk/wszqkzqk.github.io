#!/usr/bin/env python

import os
import sys

def unixpath(path):
    return path.replace('\\', '/')

print('本程序将在插入带注图片的同时，可以按需将jpg、png、bmp、gif、ico、icon、 raw图片转化为webp格式以节省空间与网页流量，并将自动对使用webp进行有损压缩还是无损压缩给出建议\n')
localimg = os.path.dirname(unixpath(sys.path[0])) + '/img'

def autowebp(imgfile):  # 仅对本地图片使用
    
    # 检查该本地文件是否存在
    if not os.path.exists("{0}/{1}".format(localimg, imgfile)):
        print('该文件既不是网络文件，又不是./img目录下的文件！请检查输入！')
        return

    appendname = imgfile.split('.')[-1].lower()

    if appendname in {'png', 'bmp', 'gif', 'ico', 'icon', 'jpg', 'jpeg', 'raw'}:
        llwebpimg = os.path.splitext(imgfile)[0] + '-lossless.webp'
        webpimg = os.path.splitext(imgfile)[0] + '.webp'

        if os.path.exists("{0}/{1}".format(localimg, llwebpimg)):
            lltodo = input('检测到目标文件"{}"已存在！\n若需要直接使用已存在文件请输入"0"，覆盖请输入"1"，需要重命名请输入"2"（默认"0"）:\n'.format(llwebpimg))
            if lltodo == '2':
                llwebpimg = input('请输入用于无损压缩webp的文件名（默认为originalname-new.webp）：\n')
            elif lltodo == '0':
                return '/img/' + llwebpimg

        if os.path.exists("{0}/{1}".format(localimg, webpimg)):
            lossytodo = input('检测到目标文件"{}"已存在！\n若需要直接使用已存在文件请输入"0"，覆盖请输入"1"，需要重命名请输入"2"（默认"0"）:\n'.format(webpimg))
            if lossytodo == '2':
                webpimg = input('请输入用于有损压缩webp的文件名（默认为originalname-new.webp）：\n')
            elif lossytodo == '0':
                return '/img/' + webpimg

        # 调用ffmpeg转化
        os.system('echo y|ffmpeg -i "{0}/{1}" "{0}/{2}"'.format(localimg, imgfile, webpimg))
        os.system('echo y|ffmpeg -i "{0}/{1}" -lossless 1 "{0}/{2}"'.format(localimg, imgfile, llwebpimg))
        
        originsize = os.path.getsize("{0}/{1}".format(localimg, imgfile))
        lossysize = os.path.getsize("{0}/{1}".format(localimg, webpimg))
        llsize = os.path.getsize("{0}/{1}".format(localimg, llwebpimg))

        # 判断无损压缩相比于原图有无压缩效果
        if originsize / llsize > 1:
            llok = 1
        else:
            llok = 0
        # 判断有损压缩是否比无损压缩更省体积
        if llsize > lossysize:
            if (originsize / lossysize) >= 1.15:
                lossyok = 1
            else:
                lossyok = 0
        else:
            lossyok = 0

        if llok and lossyok:
            preference = (llsize - lossysize)*100 / llsize
            print('\n完成！检测到无损压缩与有损压缩均能有效减小图片大小！')
            choice = input('其中有损压缩文件比无损压缩文件体积小{}%\n若保留无损压缩请输入"1"，保留有损压缩请输入"0"（默认"1"）：\n'.format(round(preference, 2)))
            if choice == '0':
                os.remove("{0}/{1}".format(localimg, llwebpimg))
                flag = input('若需要删除源文件请输入"1"，否则请输入"0"（默认"0"）：\n')
                if flag == '1':
                    os.remove("{0}/{1}".format(localimg, imgfile))
                print('完成！所选的新图片相比原图节省了{}%的空间'.format(round((originsize - lossysize)*100 / originsize, 2)))
                return '/img/' + webpimg
            else:
                os.remove("{0}/{1}".format(localimg, webpimg))
                flag = input('若需要删除源文件请输入"1"，否则请输入"0"（默认"0"）：\n')
                if flag == '1':
                    os.remove("{0}/{1}".format(localimg, imgfile))
                print('完成！所选的新图片相比原图节省了{}%的空间'.format(round((originsize - llsize)*100 / originsize, 2)))
                return '/img/' + llwebpimg
        elif llok:
            print('检测到无损压缩能有效减小图片大小，采用无损压缩！')
            os.remove("{0}/{1}".format(localimg, webpimg))
            flag = input('若需要删除源文件请输入"1"，否则请输入"0"（默认"0"）：\n')
            if flag == '1':
                os.remove("{0}/{1}".format(localimg, imgfile))
            print('完成！所选的新图片相比原图节省了{}%的空间'.format(round((originsize - llsize)*100 / originsize, 2)))
            return '/img/' + llwebpimg
        elif lossyok:
            print('检测到有损压缩能有效减小图片大小，采用有损压缩！')
            os.remove("{0}/{1}".format(localimg, llwebpimg))
            flag = input('若需要删除源文件请输入"1"，否则请输入"0"（默认"0"）：\n')
            if flag == '1':
                os.remove("{0}/{1}".format(localimg, imgfile))
            print('完成！所选的新图片相比原图节省了{}%的空间'.format(round((originsize - lossysize)*100 / originsize, 2)))
            return '/img/' + webpimg
        else:
            print('webp并不能很好地优化文件大小，保留原图！')
            os.remove("{0}/{1}".format(localimg, webpimg))
            os.remove("{0}/{1}".format(localimg, llwebpimg))
            return '/img/' + imgfile
    else:
        return '/img/' + imgfile

print('请输入该行的图片分栏数：')
n = input()
while 1:
    try:
        n = int(n)
        break
    except ValueError:
        print('错误！请输入一个数字作为分栏数！')
        n = input()

picline = '|'
neckline = '|' + ':----:|'*n
tailline = '|'

for i in range(n):
    print('请输入第{}张图片的地址（默认在./img下，也可输入绝对网址或带有/img的完整地址）：'.format(i+1))
    url = input()
    if '://' not in url:
        url = url.replace('\\', '/')
        if '/img/' not in url:
            if url:
                url = autowebp(url)
            else:
                print('无输入内容！若需要将此位置留空请输入"1"，不需要则请输入"0"（默认"0"）')
                if input() == '1':
                    picline += '    |'
                    tailline += '    |'
                    continue
        else:
            if os.path.dirname(url) == os.path.dirname(unixpath(sys.path[0])) + '/img':
                url = autowebp(os.path.basename(url))
    # 重试机制
    while not url:
        print('请重新输入第{}张图片的地址（默认在./img下，也可输入绝对网址或带有/img的完整地址）：'.format(i+1))
        url = input()
        if '://' not in url:
            url = url.replace('\\', '/')
            if '/img/' not in url:
                if url:
                    url = autowebp(url)
                else:
                    print('无输入内容！若需要将此位置留空请输入"1"，不需要则请输入"0"（默认"0"）')
                    if input() == '1':
                        picline += '    |'
                        tailline += '    |'
                        break
            else:
                if os.path.dirname(url) == os.path.dirname(unixpath(sys.path[0])) + '/img':
                    url = autowebp(os.path.basename(url))
    else:
        print('请输入点击图片的链接指向（默认为本身）')
        goto = input()
        if not goto:
            goto = url
        picline += '[![#~{0}]({0})]({1})|'.format(url, goto)
        print('请输入图注：')
        note = input()
        tailline += '{}|'.format(note)

print('正在生成符合markdown语法的输出内容……\n', picline, neckline, tailline, '\n完成！请自行将以上内容复制到所需要的markdown文件内', sep='\n')
input('\n请按回车键退出……')