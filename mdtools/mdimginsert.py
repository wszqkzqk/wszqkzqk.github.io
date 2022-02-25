#!/usr/bin/env python
from sys import argv
from fnmatch import fnmatch
def pathed(path):
    while len(path) > 1 and ((path[0] == "'" and path[-1] == "'") or (path[0] == '"' and path[-1] == '"')):
        path = path[1:-1]
    else:
        return path.replace('\\', '/')
imgchara = ('.png', '.jpg', '.jpeg', '.svg', '.gif', '.ico', '.icon', '.heif', '.avif', '.webp')
supported = ' '.join(imgchara)
if len(argv) == 2:
    if (argv[1] == '--help') or (argv[1] == '-h'):
        print('''\
用法：
1. mdimginsert.py [待处理的.md文件的路径]
        -- 将目标文件中所有以"#~"开头且以所支持的图片后缀名结尾的行表达为markdown图片格式（注意图片末不能有空格）
2. mdimginsert.py
        -- 输入目标文件路径，将其中以"#~"开头"#~"且以所支持的图片后缀名结尾的行表达为markdown图片格式（注意图片末不能有空格）
3. mdimginsert.py --help
        -- 查看帮助
4. mdimginsert.py -h
        -- 查看帮助
目前支持的图片后缀名（不区分大小写）：{}'''.format(supported))
        exit()
    else:
        path = pathed(argv[1])
elif len(argv) == 1:
    print('请输入所需要操作的.md文件地址：')
    path = pathed(input())
else:
    print('参数过多：一次只支持处理一个文件！')
with open(path, "r", encoding="utf-8") as load:
    content = load.readlines()
output = []
for i in range(len(content)):
    if fnmatch(content[i], '#~*'):
        checkitem = content[i].lower()
        for imgfmt in imgchara:
            if fnmatch(checkitem, '*{}\n'.format(imgfmt)):
                flag = 1
                break
        else:
            flag = 0
    else:
        flag = 0
    if flag:
        imgname = content[i][2:-1]
        if '://' in imgname:
            content[i] = '[![#~{0}]({0})]({0})\n'.format(imgname)
        elif fnmatch(imgname, '/img/*'):
            content[i] = '[![#~{0}]({0})]({0})\n'.format(imgname)
        else:
            content[i] = '[![#~{0}](/img/{0})](/img/{0})\n'.format(imgname)
with open(path, "w", encoding="utf-8") as init:
    init.write('')
with open(path, "a", encoding="utf-8") as echo:
    for line in content:
        echo.write(line)
print('完成！')
