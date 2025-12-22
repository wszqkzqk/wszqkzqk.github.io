---
layout:       post
title:        在不借助oh-my-zsh的前提下进行Zsh配置
subtitle:     Windows(MSYS2)或Arch Linux平台下Zsh的配置
date:         2022-06-24
author:       wszqkzqk
header-img:   img/shell-config-bg.webp
catalog:      true
tags:         Linux Windows MSYS2 Zsh 开源软件 Pacman 系统配置
---

<iframe frameborder="no" border="0" marginwidth="0" marginheight="0" width="330" height="86" src="//music.163.com/outchain/player?type=2&id=1825023368&auto=1&height=66"></iframe>

## 前言

Linux下最常用的Bash发布于1989年，在此后的发展中并没有引入太多么革命性的功能，已经是一款十分古老的Unix Shell了。虽然它仍然是众Linux发行版预装最多的Shell，但是它的扩展性也早已不如其他的Shell。

Zsh、Fish甚至从Windows下发展而来的PowerShell相较Bash而言都极具扩展性。其中，只有Zsh能够很好地兼容Bash的语法，所以，将Zsh作为Bash的替代品非常合适。

然而，Zsh虽然可扩展性高，功能强大，但是它的配置并不容易。一般来说，要方便地配置Zsh需要借助oh-my-zsh这个强大的工具。但oh-my-zsh这个工具主要用Shell脚本写成，性能并不出色，往往需要较长的启动时间。

由于Linux下有十分成熟的内存缓存机制，因此当oh-my-zsh在系统启动后完成过一次加载，之后便可以直接从内存中读取已经缓存的内容，能够做到瞬间启动。然而，Windows下的内存缓冲机制则没有这么友好，如果使用oh-my-zsh，Zsh的加载时间将会特别长。此外，由于Windows下的Unix Shell环境均是移植而来，利用了Cygwin或衍生库将Unix API Calls转化为Windows API Calls，有显著的性能损失，对于Unix的`fork()`API转化效率尤其低下（不过WSL的原生实现可能要好一点）。因此，在Windows下使用本来就比较吃资源的oh-my-zsh十分卡顿，体验并不好。

### Windows下MSYS2环境的准备

#### MSYS2的安装

考虑到有的读者可能对Windows下的终端配置不熟悉，在这里我简单列出一下Windows下安装Zsh的方法。

由于WSL对Windows本身的交互并不是很方便，里面的工具链也不能用来构建Windows本地应用，我在这里推荐使用MSYS2。MSYS2相当于Windows版的Pacman包管理器，不仅与Arch Linux系发行版的包管理命令完美兼容，而且包构建方便（只需要写一份`PKGBUILD`）、官方源中软件丰富，包含了gcc、clang等编译器与众多库，还有ffmpeg等基础软件和VLC等方便的用户端GUI软件，功能十分强大。

MSYS2已经包含在了winget的软件库中，可以直接通过命令安装：

```powershell
winget install msys2.msys2
```

#### 环境变量的配置

安装完成后，需要在系统环境变量（现在的Windows系统应该只需要在开始菜单的搜索框中输入`path`就能弹出）中添加如下变量，其中设定`MSYS2_PATH_TYPE`为`inherit`是让MSYS2的环境变量继承Windows系统的环境变量所必须的，其余的是笔者的习惯，可选：

|       变量名               |   变量值   |
|       ----                |    ---    |
|   MSYS2_PATH_TYPE[^1]     | inherit   |
|   MSYS[^4]                | winsymlinks:native |
|   MINGW_ARCH[^5]          | ucrt64    |

[^1]: 指定MSYS2程序读取的环境变量类型，`inherit`表示将系统变量合并到MSYS2环境变量
[^4]: 指定MSYS2的软链接方式为`winsymlinks:native`，即使用Windows的软链接方式。如果设置了这个变量以后，记得在`MSYS2安装路径/etc/makepkg.conf`与`MSYS2安装路径/etc/makepkg_mingw.conf`末尾添加`export MSYS='winsymlinks:deepcopy'`，保证在打包中的软链接仍然通过`deepcopy`方式复制，而不是直接创建软链接文件，否则打包安装后路径发生变化可能会导致软链接失效。
[^5]: 指定MSYS2使用的MINGW环境类型，`ucrt64`表示使用UCRT64环境

其实也可以把MSYS2的相关路径（使用的MinGW-w64工具链路径`MSYS2安装路径/使用的MinGW类型/bin`以及MSYS2路径`MSYS2安装路径/usr/bin`）添加到`Path`变量中，方便直接在Windows的cmd或者PowerShell中调用MSYS2命令，但是据说可能会出现一些冲突，然而笔者添加了以后并没有发现什么问题，因此这也可以作为一个可选项。

- 将MSYS2的相关可执行文件路径添加到系统环境变量的一个示例：

|在`Path`变量中添加的内容[^3]|
|           ----          |
|D:\msys64\ucrt64\bin[^2] |
|D:\msys64\usr\bin[^2]    |

[^2]: 注意应当写成本地MSYS2可执行文件目录所在路径或本地使用的MSYS2的MINGW环境的所在路径，且应当保证MINGW环境的所在路径排在前面
[^3]: 注意不要删除`Path`变量中的原有内容

#### MSYS2的用户主目录配置

如果想要让MSYS2将Windows的用户主目录作为`$HOME`而不是MSYS2下的`/home/用户名`，可以编辑`MSYS2安装路径/etc/nsswitch.conf`文件，将`db_home`一行改为`db_home: windows`。

#### 建议：选择UCRT64环境

* 本建议与Zsh本身无关，但对于使用MSYS2管理开发环境的用户来说非常重要。

MSYS2不仅提供了Zsh，还提供了多种原生的（`mingw-w64`环境）编译器和工具链，以及广受欢迎的GIMP、Inkscape、VLC等日用应用。

MSYS2提供了多种构建环境，每种环境都有其特定的编译器、C/C++运行时库和默认的工具链。对于现代Windows开发，官方**强烈推荐并已将UCRT64作为默认环境**。

*   **UCRT64 (Universal C Runtime)** 环境使用最新的Universal C Runtime库，与Microsoft Visual Studio默认使用的运行时库保持一致，提供了更好的C99兼容性和与MSVC的互操作性。
*   相比之下，传统的MINGW64环境使用的是MSVCRT (Microsoft Visual C++ Runtime)，这是一个较旧的C运行时库，在某些方面存在兼容性问题且不完全支持C99。

对不需要使用的环境，可以到`MSYS2安装路径/etc/pacman.conf`中将其注释掉，减少`pacman`同步时拉取`.db`文件的时间。例如：

```unix-config
# [clangarm64]
# Include = /etc/pacman.d/mirrorlist.mingw
# 
# [mingw32]
# Include = /etc/pacman.d/mirrorlist.mingw
# 
# [mingw64]
# Include = /etc/pacman.d/mirrorlist.mingw

[ucrt64]
Include = /etc/pacman.d/mirrorlist.mingw

# [clang64]
# Include = /etc/pacman.d/mirrorlist.mingw

[msys]
Include = /etc/pacman.d/mirrorlist.msys
```

注意千万不要注释掉`[msys]`环境，因为Zsh等Shell工具需要使用`msys`环境提供的工具。

#### 提醒：避免包冲突

* 本提醒与Zsh本身无关，但对于使用MSYS2管理开发环境的用户来说非常重要。

在使用MSYS2时，理解其环境区分对于避免工具链冲突至关重要。MSYS2拥有一个`msys`环境（通常对应`/usr/bin`路径），其中包含了许多Unix风格的工具（如`grep`, `diff`, `git`, `make`, `file`, `coreutils`等）。这些`msys`环境下的工具是基于Cygwin运行时库的，能够正确识别和处理MSYS2风格的路径（例如`/usr/bin`、`/ucrt64/bin`等）。

然而，如果你在MSYS2的**UCRT64（或其他MINGW）环境**中，安装了这些**同样名称的`mingw-w64-ucrt-x86_64-*`版本**的工具（例如 `mingw-w64-ucrt-x86_64-grep`, `mingw-w64-ucrt-x86_64-diffutils`，`mingw-w64-ucrt-x86_64-file`，`mingw-w64-ucrt-x86_64-uutils-coreutils`等），则极有可能导致包管理系统（Pacman）或构建过程出现问题。这是因为这些`mingw-w64-ucrt-x86_64-*`版本是为构建原生Windows应用而设计的，它们通常不理解MSYS2的Unix风格路径，在执行需要处理这些路径的操作时会报错。

对于开发所需的库和编译器（如GTK、Vala、GCC、Clang），你当然需要安装其`mingw-w64-ucrt-x86_64-`版本，例如`mingw-w64-ucrt-x86_64-gtk4`，因为这些是用来构建原生Windows应用程序的。但对于作为Shell环境核心功能的工具，应使用`msys`环境提供的版本。

### Windows下安装Zsh

完成后，在MinTTY中运行MSYS2终端（如果添加了MSYS2可执行文件路径到`Path`环境变量，也可以在Windows终端的PowerShell或cmd环境中执行），安装Zsh：

```bash
pacman -S zsh
```

为了方便，可以将MSYS2集成到Windows终端，在Windows终端中选择`添加新配置文件`-`新建空配置文件`，在`命令行`中填入：

```cmd
cmd.exe /c set MSYSTEM=你使用的MinGW环境名称 && set CHERE_INVOKING=enabled_from_arguments && MSYS2安装位置/usr/bin/
zsh.exe --login
```

例如：

```cmd
cmd.exe /c set MSYSTEM=UCRT64 && set CHERE_INVOKING=enabled_from_arguments && D:/msys64/usr/bin/
zsh.exe --login
```

以上命令依靠在cmd中配置MSYS2所需的特殊环境变量，再启动Zsh，如果不想这样手动写出要加载的环境变量，也可以直接调用MSYS2的cmd，只需要在Windows终端中选择`添加新配置文件`-`新建空配置文件`，在`命令行`中填入：

```cmd
你的MSYS2安装路径\msys2_shell.cmd -对应使用的MinGW环境(如-mingw64) -here -no-start -full-path -defterm -shell zsh
```

例如：

```cmd
D:\msys64\msys2_shell.cmd -ucrt64 -here -no-start -full-path -defterm -shell zsh
```

## oh-my-zsh的替代实现

oh-my-zsh提供的便利主要是主题支持和插件支持，当然还有其他的操作绑定。这些我们都可以想办法去进行性能更优的替代实现。

### 主题支持及状态提示

在oh-my-zsh的启发下，[Jan De Dobbeleer](https://github.com/JanDeDobbeleer)开发了一个功能较为接近的[oh-my-posh](https://github.com/JanDeDobbeleer/oh-my-posh)。与oh-my-zsh不同，oh-my-posh采用Go语言开发，虽然运行效率仍然较C/C++低不少，但是其性能仍然显著高于直接用Sell写成的oh-my-zsh。

虽然oh-my-posh从名称来看好像是为微软的PowerShell专门设计，但是由于它并没有用绑定在Shell上的语言实现，故实际上oh-my-posh支持多种Shell环境，当然也包括Zsh。

oh-my-posh不仅是跨Shell的，它还是跨平台的，Windows与Acrhlinux系发行版均可以很方便地安装，Windows安装命令如下：

```powershell
winget install JanDeDobbeleer.OhMyPosh
```

Arch Linux系发行版则是（使用paru）：

```bash
paru -S oh-my-posh
```

#### 预览

Zsh需要有对应的`.zshrc`文件才能正常启动，在正式配置流程开始之前，我们不妨先让Zsh自动建立一个无功能的初始化`.zshrc`文件：

|[![#~/img/首次运行Zsh.webp](/img/首次运行Zsh.webp)](/img/首次运行Zsh.webp)|
|:----:|
|首次运行Zsh|

如上图所示，在没有配置文件时首次运行Zsh会输出以上提示。为了有一个供后续配置的输入环境，我们可以在这里输入`0`，输入`cat ~/.zshrc`后可以看到，程序在此处生成了一个空的配置文件：

```zsh
$ cat ~/.zshrc
> # Created by newuser for 5.8
```

oh-my-posh在不同平台的文件位置有些区别，在Zsh中预览效果时，Windows下可以执行：

```zsh
# $POSH_THEMES_PATH路径在安装时已经添加到了环境变量中
eval "$(oh-my-posh init zsh --config $POSH_THEMES_PATH/想要使用的主题文件)"
```

Arch Linux下执行：

```zsh
eval "$(oh-my-posh init zsh --config /usr/share/oh-my-posh/themes/想要使用的主题文件)"
```

具体的主题样式预览参见[oh-my-posh官网](https://ohmyposh.dev/docs/themes)，可以从中选择自己喜欢的主题，oh-my-posh项目推荐使用的是`jandedobbeleer.omp.json`这款主题。

如果配置成功，就会显示界面：

|[![#~/img/预览中的oh-my-posh主题效果.webp](/img/预览中的oh-my-posh主题效果.webp)](/img/预览中的oh-my-posh主题效果.webp)|
|:----:|
|预览中的oh-my-posh主题效果|

这里我们可以发现，系统并没有自带oh-my-posh主题所需要的字体，部分字符被显示成了方块，这一问题我们稍后再解决。

oh-my-posh可不仅仅是一个主题管理器，它还自带了命令运行计时、Git仓库管理提示等功能，因此这些Zsh插件不再需要我们安装了。

### 下载安装Zsh相关功能插件

Zsh具有许多能够提高生产力的插件，如自动补全插件、语法高亮插件等。

对于Arch Linux，这些插件都已经集成到了软件源中，可以直接安装：

```zsh
paru -S zsh-syntax-highlighting zsh-autosuggestions zsh-history-substring-search
```

对Windows则较为麻烦，需要手动clone到本地：

```zsh
mkdir ~/.zsh-config
cd ~/.zsh-config
git clone https://github.com/zsh-users/zsh-autosuggestions
git clone https://github.com/zsh-users/zsh-syntax-highlighting.git
git clone https://github.com/zsh-users/zsh-history-substring-search.git
```

### 编写`.zshrc`文件

`.zshrc`是Zsh的配置文件，没有了oh-my-zsh，我们需要手动进行编写。

- 首先需要在Zsh运行时指定oh-my-posh主题，添加：

```zsh
eval "$(oh-my-posh init zsh --config 主题文件路径)"
```

- 为了自动保存历史，我们还需要指定历史记录文件地址及读取、写入配置：

```zsh
HISTFILE=~/.zsh_history
HISTSIZE=100000000                  # 设置历史记录读取行数
SAVEHIST=100000000                  # 设置历史记录读取行数

setopt BANG_HIST                    # 在展开字符期间对"!"特殊处理
setopt EXTENDED_HISTORY             # 生成详细的历史记录
setopt INC_APPEND_HISTORY           # 立即写入历史文件，而不是退出时写入
setopt SHARE_HISTORY                # 在各个终端窗口中共享历史记录
setopt HIST_EXPIRE_DUPS_FIRST       # 修剪掉过量的历史记录时首先去重复
setopt HIST_IGNORE_DUPS             # 不记录刚刚记录的内容
setopt HIST_IGNORE_ALL_DUPS         # 如果新内容重复，则删除旧内容
setopt HIST_FIND_NO_DUPS            # 不显示先前查找到的历史记录内容
setopt HIST_IGNORE_SPACE            # 不记录以空格开头的内容
setopt HIST_SAVE_NO_DUPS            # 不要在历史文件中写入重复的条目
setopt HIST_REDUCE_BLANKS           # 在记录条目之前删除多余的空白
setopt HIST_VERIFY                  # 在显示历史扩展时不要立即执行
setopt HIST_BEEP                    # 访问不存在的历史记录时发出声音提示
```

- 加载之前下载的插件（这里用的是Windows按照本文方法下载的路径，Arch Linux替换为对应的安装路径即可）：

```zsh
source ~/.zsh-config/zsh-autosuggestions/zsh-autosuggestions.zsh                    # 加载自动补全插件
source ~/.zsh-config/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh            # 加载语法高亮插件
source ~/.zsh-config/zsh-history-substring-search/zsh-history-substring-search.zsh  # 加载历史搜索插件
```

- 最后可以根据习惯指定相关快捷键绑定，比如搜索历史记录、逐词跳过等：

```zsh
bindkey "^[[A" history-substring-search-up      # Up 设置向前查找与此相关
bindkey "^[[B" history-substring-search-down    # Down 设置向后查找与此相关
bindkey ";5A" history-beginning-search-backward # Ctrl-Up 向前查找以此开头
bindkey ";5B" history-beginning-search-forward  # Ctrl-Down 向后查找以此开头
bindkey ";5C" emacs-forward-word                # Ctrl-Right 向前跳过一个单词
bindkey ";5D" emacs-backward-word               # Ctrl-Left 向后跳过一个单词
bindkey "\e[3~" delete-char                     # Del键 删除后面的一个字符
```

编辑`.zshrc`时应当注意`.zshrc`中配置项的逻辑顺序：
- `bindkey`调用了历史记录子字符串查找插件，所以该插件必须在相关`bindkey`之前加载
- 历史记录子字符串查找插件会自动高亮标出正在搜索的字串，这一语法高亮优先级应当高于一般基于命令本身的语法高亮，因此语法高亮插件应当在历史子字符串插件加载前加载

### 字体配置

oh-my-posh工具依赖[Nerd Fonts](https://www.nerdfonts.com/)字体，在Arch Linux下可以直接在Archlinuxcn源中下载`nerd-fonts-noto`字体：

```zsh
sudo pacman -S nerd-fonts-noto
```

Windows下则需要手动下载并安装，官方推荐的字体是[Meslo LGM NF](https://github.com/ryanoasis/nerd-fonts/releases/download/v2.1.0/Meslo.zip)，下载后解压并右键点击，选择`为所有用户安装`（避免Windows终端无法识别字体）。

安装完成后，在终端中切换到对应的`Nerd Front`字体即可，安装成功后，配置了oh-my-posh主题的Zsh便不再乱码。

|[![#~/img/oh-my-posh配置好字体以后的显示情况.webp](/img/oh-my-posh配置好字体以后的显示情况.webp)](/img/oh-my-posh配置好字体以后的显示情况.webp)|
|:----:|
|配置好字体以后的显示情况|

## Arch Linux下的最简方法

我已经将这个简单的`.zshrc`文件打包并[推送到了AUR](https://aur.archlinux.org/packages/easy-zsh-config)，大大简化了安装流程，现在Arch Linux下安装只需要：

```zsh
paru -S easy-zsh-config
```

然后再复制配置文件即可使用：

```zsh
cp /etc/zsh/zshrc ~/.zshrc
```

安装完成后可以使用`chsh /bin/zsh`来切换默认Shell环境。

目前AUR中的`oh-my-posh-bin`存在权限设置bug，可能会导致oh-my-posh的主题设置失败，可以执行以下命令解决这一问题：

```zsh
sudo chmod -R +r /usr/share/oh-my-posh/themes/
```
