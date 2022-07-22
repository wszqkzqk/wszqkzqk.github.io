#!/usr/bin/env python
from sys import argv
def pathed(path):
    while len(path) > 1 and ((path[0] == "'" and path[-1] == "'") or (path[0] == '"' and path[-1] == '"')):
        path = path[1:-1]
    else:
        return path.replace('\\', '/')
loadtarget = 0
loadref = 0
loadinner = 0
if len(argv) == 1:
    loadtarget = 1
    loadref = 1
    loadinner = 1
elif len(argv) == 2:
    if (argv[1] == '-h') or (argv[1] == '--help'):
        print('''\
用法:
1. mdrefadd.py 0 [待处理的.md文件的路径] [引注内容纯文本路径]
        -- 仅将引注内容按markdown语法添加到目标文件中
2. mdrefadd.py 1 [待处理的.md文件的路径] [引注内容纯文本路径]
        -- 将引注内容按markdown语法添加到目标文件中，并将目标文件中的"[num]"改为makdown引注"[^num]"
3. mdrefadd.py [待处理的.md文件的路径] [引注内容纯文本路径]
        -- 将引注内容按markdown语法添加到目标文件中，并将目标文件中的"[num]"改为makdown引注"[^num]"
4. mdrefadd.py [待处理的.md文件的路径]
        -- 处理目标文件，可在后续过程中自选处理内容（手动输入引注内容）
5. mdrefadd.py
        -- 在后续过程中自选目标文件和处理内容（手动输入引注内容）
6. mdrefadd.py --help
        -- 查看帮助
7. mdrefadd.py -h
        -- 查看帮助
注意：Windows操作系统需要按"python mdrefadd.py [参数]"运行''')
        exit()
    else:
        path = pathed(argv[1])
        loadref = 1
        loadinner = 1
elif len(argv) == 3:
    inner = '1'
    path = pathed(argv[1])
    refpath = pathed(argv[2])
elif len(argv) == 4:
    inner = argv[1]
    path = pathed(argv[2])
    refpath = pathed(argv[3])
else:
    print('错误！参数过多！')
    exit()
if loadtarget:
    print('请输入所操作的文件的路径：')
    path = pathed(input())
if loadref:
    print('请输入总引注数（即原文最后的引注数）：')
    num = int(input())
    print('请依次输入各个引注的内容（应保证每个引注占一行，注意复制时首行不要留空）：')
    with open(path, "a", encoding="utf-8") as echo:
        echo.write('\n')
        for i in range(num):
            ref = '[^{}]: '.format(i + 1) + input() + '\n\n'
            echo.write(ref)
else:
    with open(refpath, "r", encoding="utf-8") as load:
        refs = load.readlines()
    with open(path, "a", encoding="utf-8") as echo:
        echo.write('\n')
        i = 1
        for info in refs:
            if info and (not info.isspace()):
                ref = '[^{0}]: {1}\n'.format(i, info)
                i += 1
                echo.write(ref)
        num = i
if loadinner:
    print('若需要替换文中的"[num]"为markdown引注形式"[^num]"请输入"1"，否则请输入"0"（默认"1"）,注意：如果文中有其他地方出现了"[num]"（如以数字为图片名显示的图片）请不要使用这个功能：')
    inner = input()
if inner != '0':
    with open(path, "r", encoding="utf-8") as load:
        content = load.read()
    for i in range(1, num + 1):
        content = content.replace('[{}]'.format(i), '[^{}]'.format(i))
    with open(path, "w", encoding="utf-8") as rewt:
        rewt.write(content)
print('完成！')
