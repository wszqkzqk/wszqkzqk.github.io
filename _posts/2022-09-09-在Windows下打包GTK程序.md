---
layout:     post
title:      在Windows下打包GTK程序
subtitle:   一个简单的程序打包脚本
date:       2022-09-09
author:     星外之神
header-img: img/GTK-logo.webp
catalog:    true
tags:       GTK Python vala Windows 程序打包
---

***未经特殊说明，本文中包括的所有代码均采用LGPL v2.1协议公开***

## 背景

GTK是一个强大的部件工具库，可以用于开发图形用户界面程序。相比Qt、wxWidget等与C++语言深度绑定的部件工具库，GTK采用了纯C语言进行开发。而且，为了减轻开发的工作量，GNOME社区还为GObject对象特别开发了一种语法类似C#的语言——Vala，Vala背靠强大的Glib与GTK库，又拥有较为现代化的高级语言特性，开发效率高；此外，Vala的编译过程是将Vala代码先编译为C语言中间代码，再调用C语言编译器将中间代码编译为二进制程序，所以Vala并不依赖额外的运行时或虚拟机，拥有与用C语言直接开发的程序相近的性能，也拥有与C语言所开发的程序的原生ABI兼容性。

GTK是一个跨平台的部件工具库，然而，由于GTK的主要开发由Linux下的桌面环境开发团队——GNOME社区进行，实际上GTK在Linux下的开发者数目远远多于在Windows下的开发者数目。因此，GTK在Windows下的表现无论是从性能来看，还是从便利性来看，都远远不如在Linux下的表现。

就打包与发布的体验而言，GTK在Windows下也表现不佳。几乎所有Linux发行版均可以从官方源中获取GTK的依赖，但是Windows并没有基于软件源的依赖体系，GTK的诸多依赖与配置还需要手动打包。

## 打包实现

注：本文的方案均需要MSYS2环境提供GTK及`ntldd`。本文的打包器由Python实现，但是由于Python打包器中不存在对C语言编译的二进制库的依赖关系，不存在ABI兼容问题，因此无论是用官方的Python（由MSVC编译）还是MSYS2中的Python（根据选择的环境不同由GCC或者Clang编译）均可以进行打包操作。

### 基本思路

`ntldd`是一个在Windows下解析二进制文件动态链接关系的工具，可以用其解析GTK程序在Windows下的`dll`依赖，再读取`ntldd`的输出结果，将程序和依赖复制到同一个文件夹中，完成打包。

### 具体实现

仅仅依赖`Glib`的CLI程序一般仅需复制其`dll`依赖到同一文件夹即可完成打包，但是对于完整依赖GTK的GUI程序，除了需要动态链接的`dll`文件外，还需要同时打包GTK所需要的图标、主题等资源文件，以及额外的库文件。

而仅依赖于`Glib`的CLI程序并不需要这些额外的文件，因此，还需要判断程序的具体依赖。比如，GTK3程序应当有对`libgtk-3-0.dll`的依赖

这样就可以用Python简单实现一个GTK程序打包器：

```python
from sys import argv
from fnmatch import fnmatch
import os

MINGW_ARCH = "ucrt64"
MSYS2_PATH = "D:\\msys64\\"

if len(argv) == 3:
    path = argv[1]
    outdir = argv[2]
elif len(argv) == 2:
    outdir = input('请输入需要将目标文件复制到的文件夹地址:\n')
elif len(argv) == 1:
    path = input('请输入文件地址:\n')
    outdir = input('请输入需要将目标文件复制到的文件夹地址:\n')

def pathed(path):
    if ((path[0] == "'") or (path[0] == '"')) and ((path[-1] == "'") or (path[-1] == '"')):
        return path[1:-1]
    else:
        return path

info = [i.split() for i in os.popen(f'ntldd -R "{pathed(path)}"')]
dependencies = set()
if not os.path.exists(os.path.join(outdir, "bin")):
    os.makedirs(os.path.join(outdir, "bin"))
for item in info:
    if (fnmatch(item[2], '/usr/*') or fnmatch(item[2], f'/{MINGW_ARCH}/*')
    or fnmatch(item[2], '*\\usr\\*')) or fnmatch(item[2], f'*\\{MINGW_ARCH}\\*'):
        if item[0] not in dependencies:
            os.system(f'cp "{item[2]}" "{os.path.join(outdir, "bin", item[0])}"')
            dependencies.add(item[0])
os.system(f'cp "{pathed(path)}" "{os.path.join(outdir, "bin", os.path.basename(path))}"')

if ("libgtk-3-0.dll" in dependencies):
    copy_share_file_dic = {
        os.path.join(MSYS2_PATH, MINGW_ARCH, "share", "themes", "default", "gtk-3.0"): os.path.join(outdir, "share", "themes", "default"),
        os.path.join(MSYS2_PATH, MINGW_ARCH, "share", "themes", "emacs", "gtk-3.0"): os.path.join(outdir, "share", "themes", "emacs"),
        os.path.join(MSYS2_PATH, MINGW_ARCH, "share", "glib-2.0", "schemas"): os.path.join(outdir, "share", "glib-2.0"),
        os.path.join(MSYS2_PATH, MINGW_ARCH, "share", "icons"): os.path.join(outdir, "share"),
        os.path.join(MSYS2_PATH, MINGW_ARCH, "lib", "gdk-pixbuf-2.0"): os.path.join(outdir, "lib"),
    }
    for source, target in copy_share_file_dic.items():
        if not os.path.exists(os.path.join(outdir, target)):
            os.makedirs(os.path.join(outdir, target))
        os.system(f'cp -r "{source}" "{target}"')
```

其中，需要将`MSYS2_PATH`变量设置为MSYS2的实际安装路径，`MINGW_ARCH`变量设置为实际使用的MINGW环境（MSYS2安装路径下的子文件夹，如mingw64、ucrt64、clang64）。该打包器即可自动打包GTK程序及其相关依赖到所选定的文件夹。

### 测试示例

由于笔者不会C语言，这里列出一个用Vala语言实现的示例程序：

```vala
#!/usr/bin/env -S vala -X -O2 --pkg gtk+-3.0

using Gtk;
void main (string[] args) {
	Gtk.init (ref args);
	var Hello=new MessageDialog (null, Gtk.DialogFlags.MODAL, Gtk.MessageType.INFO, Gtk.ButtonsType.OK, "Hello world!");
	Hello.format_secondary_text ("This is an example dialog.");
	Hello.run ();
}
```

保存为`helloworld.vala`后，使用以下命令编译：

```bash
valac --pkg gtk+3.0 -X -O2 helloworld.vala
```

然后使用打包器，按照提示进行操作即可，得到的文件夹中，程序位于`bin`目录下。可以将整个打包文件夹分发到其他没有GTK环境的电脑使用。

### 面向对象重新实现

由于之前列出的打包器程序较为简单，没有进行封装，也不方便其他的Python程序进行导入。此外，在前面的代码中手动改`MINGW_ARCH`与`MSYS2_PATH`变量也较为麻烦，因此，笔者将这个程序按照面向对象的方式重新实现了一遍。

```python
#!/usr/bin/env python

# MSYS2下的GTK3程序打包器（面向对象实现）
# 依赖ntldd提供动态链接关系

from fnmatch import fnmatch
import os

class GtkPacker():
    def __init__(self, mingw_arch, msys2_path, exe_file_path, outdir):
        self.dependencies = set()
        self.mingw_arch = mingw_arch
        self.mingw_path = os.path.join(msys2_path, mingw_arch)
        self.exe_file_path = self.clean_path(exe_file_path)
        self.outdir = outdir

    def clean_path(self, path):
        if ((path[0] == "'") or (path[0] == '"')) and ((path[-1] == "'") or (path[-1] == '"')):
            return path[1:-1]
        else:
            return path

    def is_msys2_dep(self, dep_path):
        if (fnmatch(dep_path, "/usr/*") or fnmatch(dep_path, f"/{self.mingw_arch}/*")
        or fnmatch(dep_path, "*\\usr\\*")) or fnmatch(dep_path, f"*\\{self.mingw_arch}\\*"):
            return True
        else:
            return False

    def copy_bin_file(self):
        info = (i.split() for i in os.popen(f'ntldd -R "{self.exe_file_path}"'))
        bin_path = os.path.join(self.outdir, "bin")
        if not os.path.exists(bin_path):
            os.makedirs(bin_path)
        for item in info:
            if self.is_msys2_dep(item[2]):
                if item[0] not in self.dependencies:
                    os.system(f'cp "{item[2]}" "{os.path.join(bin_path, item[0])}"')
                    self.dependencies.add(item[0])
        os.system(f'cp "{self.exe_file_path}" "{os.path.join(bin_path, os.path.basename(self.exe_file_path))}"')

    def copy_resource_file(self):
        copy_resource_file_dic = {
            os.path.join(self.mingw_path, "share", "themes", "default", "gtk-3.0"): os.path.join(self.outdir, "share", "themes", "default"),
            os.path.join(self.mingw_path, "share", "themes", "emacs", "gtk-3.0"): os.path.join(self.outdir, "share", "themes", "emacs"),
            os.path.join(self.mingw_path, "share", "glib-2.0", "schemas"): os.path.join(self.outdir, "share", "glib-2.0"),
            os.path.join(self.mingw_path, "share", "icons"): os.path.join(self.outdir, "share"),
            os.path.join(self.mingw_path, "lib", "gdk-pixbuf-2.0"): os.path.join(self.outdir, "lib"),
        }
        for source, target in copy_resource_file_dic.items():
            if not os.path.exists(os.path.join(self.outdir, target)):
                os.makedirs(os.path.join(self.outdir, target))
            os.system(f'cp -r "{source}" "{target}"')

    def run(self):
        self.copy_bin_file()
        if ("libgtk-3-0.dll" in self.dependencies):
            self.copy_resource_file()

if __name__ == "__main__":
    from sys import argv
    if len(argv) == 3:
        path = argv[1]
        outdir = argv[2]
    elif len(argv) == 2:
        if argv[1] in {"--help", "-h"}:
            print(  "帮助：\n"
                    "GtkPacker.py [待打包文件路径] [需打包到的目标路径]\n"
                    "GtkPacker.py -h(--help)    ----查看帮助")
            os._exit(0)
        else:
            outdir = input("请输入需要将目标文件复制到的文件夹地址:\n")
    elif len(argv) == 1:
        path = input("请输入文件地址:\n")
        outdir = input("请输入需要将目标文件复制到的文件夹地址:\n")

    packer = GtkPacker("ucrt64", "D:\\msys64", path, outdir)
    packer.run()
```

使用方式与之前的版本类似，但是可以作为库被其他Python程序调用（比如用于进行编译前预处理及调用编译的程序，或者是调用NSIS的程序，可提供完整的构建方案），并且对路径的改动只需要在`if __name__ == "__main__"`后对`GtkPacker`的传参中进行，维护更加方便。
