---
layout:     post
title:      Arch Linux字体配置
subtitle:   Arch Linux中文默认字体行为变更后的配置
date:       2024-07-29
author:     wszqkzqk
header-img: img/bg-mountain-darken.webp
catalog:    true
tags:       开源软件 系统配置 Linux archlinux 字体
---

## 前言

在以前，Arch Linux的软件包`noto-fonts-cjk`存在打包阶段的配置，安装该软件包后默认的中文字体即是`Noto Sans CJK`，适合一般的显示，笔者也一直没有对字体进行配置。由于将字体配置写死在打包阶段并不合理，因此目前的这一软件包已经移除了相关配置文件，在笔者的环境下，默认的字体变成了衬线字体`Noto Serif CJK`，这并不符合系统UI字体的一般惯例，也不利于阅读，因此需要对字体进行配置。

## 字体配置

一般来说，我们不需要对全局的字体进行配置，只需要对当前用户进行配置即可。在Arch Linux中，我们可以通过`~/.config/fontconfig/fonts.conf`文件进行配置，以下是笔者的配置文件：

```xml
<?xml version='1.0'?>
<!DOCTYPE fontconfig SYSTEM 'fonts.dtd'>
<fontconfig>
 <!-- English - Sans: Noto Sans; Serif: Noto Serif; Mono: Hack -->
 <match target="pattern">
  <test name="family" qual="any">
   <string>serif</string>
  </test>
  <edit binding="strong" mode="prepend" name="family">
   <string>Noto Serif</string>
  </edit>
 </match>
 <match target="pattern">
  <test name="family" qual="any">
   <string>sans-serif</string>
  </test>
  <edit binding="strong" mode="prepend" name="family">
   <string>Noto Sans</string>
  </edit>
 </match>
 <match target="pattern">
  <test name="family" qual="any">
   <string>monospace</string>
  </test>
  <edit binding="strong" mode="prepend" name="family">
   <string>Hack</string>
  </edit>
 </match>
 <!-- CJK - Sans: Noto Sans CJK; Serif: Noto Serif CJK; Mono: Noto Sans CJK -->
 <match target="pattern">
  <test name="lang">
   <string>ja</string>
  </test>
  <test name="family">
   <string>serif</string>
  </test>
  <edit mode="prepend" name="family">
   <string>Noto Serif CJK JP</string>
  </edit>
 </match>
 <match target="pattern">
  <test name="lang">
   <string>ko</string>
  </test>
  <test name="family">
   <string>serif</string>
  </test>
  <edit mode="prepend" name="family">
   <string>Noto Serif CJK KR</string>
  </edit>
 </match>
 <match target="pattern">
  <test name="lang">
   <string>zh-cn</string>
  </test>
  <test name="family">
   <string>serif</string>
  </test>
  <edit binding="strong" mode="prepend" name="family">
   <string>Noto Serif CJK SC</string>
  </edit>
 </match>
 <match target="pattern">
  <test name="lang">
   <string>zh-tw</string>
  </test>
  <test name="family">
   <string>serif</string>
  </test>
  <edit binding="strong" mode="prepend" name="family">
   <string>Noto Serif CJK TC</string>
  </edit>
 </match>
 <match target="pattern">
  <test name="lang">
   <string>zh-hk</string>
  </test>
  <test name="family">
   <string>serif</string>
  </test>
  <edit binding="strong" mode="prepend" name="family">
   <string>Noto Serif CJK HK</string>
  </edit>
 </match>
 <match target="pattern">
  <test name="lang">
   <string>ja</string>
  </test>
  <test name="family">
   <string>sans-serif</string>
  </test>
  <edit mode="prepend" name="family">
   <string>Noto Sans CJK JP</string>
  </edit>
 </match>
 <match target="pattern">
  <test name="lang">
   <string>ko</string>
  </test>
  <test name="family">
   <string>sans-serif</string>
  </test>
  <edit mode="prepend" name="family">
   <string>Noto Sans CJK KR</string>
  </edit>
 </match>
 <match target="pattern">
  <test name="lang">
   <string>zh-cn</string>
  </test>
  <test name="family">
   <string>sans-serif</string>
  </test>
  <edit binding="strong" mode="prepend" name="family">
   <string>Noto Sans CJK SC</string>
  </edit>
 </match>
 <match target="pattern">
  <test name="lang">
   <string>zh-tw</string>
  </test>
  <test name="family">
   <string>sans-serif</string>
  </test>
  <edit binding="strong" mode="prepend" name="family">
   <string>Noto Sans CJK TC</string>
  </edit>
 </match>
 <match target="pattern">
  <test name="lang">
   <string>zh-hk</string>
  </test>
  <test name="family">
   <string>sans-serif</string>
  </test>
  <edit binding="strong" mode="prepend" name="family">
   <string>Noto Sans CJK HK</string>
  </edit>
 </match>
 <match target="pattern">
  <test name="lang">
   <string>ja</string>
  </test>
  <test name="family">
   <string>monospace</string>
  </test>
  <edit mode="prepend" name="family">
   <string>Noto Sans Mono CJK JP</string>
  </edit>
 </match>
 <match target="pattern">
  <test name="lang">
   <string>ko</string>
  </test>
  <test name="family">
   <string>monospace</string>
  </test>
  <edit mode="prepend" name="family">
   <string>Noto Sans Mono CJK KR</string>
  </edit>
 </match>
 <match target="pattern">
  <test name="lang">
   <string>zh-cn</string>
  </test>
  <test name="family">
   <string>monospace</string>
  </test>
  <edit binding="strong" mode="prepend" name="family">
   <string>Noto Sans Mono CJK SC</string>
  </edit>
 </match>
 <match target="pattern">
  <test name="lang">
   <string>zh-tw</string>
  </test>
  <test name="family">
   <string>monospace</string>
  </test>
  <edit binding="strong" mode="prepend" name="family">
   <string>Noto Sans Mono CJK TC</string>
  </edit>
 </match>
 <match target="pattern">
  <test name="lang">
   <string>zh-hk</string>
  </test>
  <test name="family">
   <string>monospace</string>
  </test>
  <edit binding="strong" mode="prepend" name="family">
   <string>Noto Sans Mono CJK HK</string>
  </edit>
 </match>
</fontconfig>
```

这一份配置文件中，笔者将英文的衬线字体设为`Noto Serif`，无衬线字体设为`Noto Sans`，等宽字体设为`Hack`，而对于CJK字符，笔者将衬线字体设为`Noto Serif CJK`，无衬线字体设为`Noto Sans CJK`，等宽字体设为`Noto Sans Mono CJK`，并根据语言区域进行了区分。这一配置文件可以保证在不同的语言环境下，字体的显示效果都是一致的。

字体配置文件的编写有一定的规则，可以参考[Fontconfig User Guide](https://www.freedesktop.org/software/fontconfig/fontconfig-user.html)。具体来说：

* `<match>`元素用于匹配字体，可以通过`<test>`元素进行条件判断，通过`<edit>`元素进行修改。
* `<test>`元素用于条件判断，可以通过`name`属性指定判断的属性，通过`qual`属性指定判断的方式，通过`compare`属性指定判断的方式，通过`lang`属性指定判断的语言。
* `<edit>`元素用于修改字体，可以通过`name`属性指定修改的属性，通过`mode`属性指定修改的方式，通过`binding`属性指定修改的强度。
  * `mode`属性可以取值`prepend`、`append`、`replace`，分别表示在前面添加、在后面添加、替换。
  * `binding`属性可以取值`strong`、`weak`，分别表示强制修改、弱修改。
    * 强制修改会覆盖原有的字体配置，而弱修改则不会。
* `<string>`元素用于指定字符串。
* `<family>`元素用于指定字体系列。
  * `<family>`元素可以嵌套，表示多个字体系列。
  * `<family>`元素一般可以包括以下值，当系统匹配到这些值时，会使用对应的字体。
    * `serif`表示衬线字体
    * `sans-serif`表示无衬线字体
    * `monospace`表示等宽字体

## 结语

本来一路用默认字体的笔者当时其实一直不明白是什么地方出了问题，导致系统的字体突然变成了衬线字体，直到运行`cat /var/log/pacman.log | grep "\[ALPM\] upgraded"`命令排查到`noto-fonts-cjk`软件包的变更，才意识到原来是软件包的配置变更导致的。字体配置文件的编写其实并不复杂，只要了解了规则，就可以根据自己的需求进行配置。
