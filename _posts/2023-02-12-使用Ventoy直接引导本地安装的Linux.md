---
layout:     post
title:      使用Ventoy直接引导本地安装的Linux
subtitle:   高级Linux安装及引导方式
date:       2023-02-12
author:     星外之神
header-img: img/ventoy/ventoy_bg.webp
catalog:    true
tags:       Ventoy 开源软件 系统引导 系统配置 系统安装
---

## 前言

Ventoy是一个多系统启动U盘解决方案。笔者首次接触Ventoy是软件开发初期Ventoy的作者在deepin论坛宣传，当时即感受到了这款软件的诸多强大之处：

* 不用像Rufus、Unetbootin等工具一样需要在更换U盘中的镜像时格式化，只需要重新拷贝镜像文件
* 支持在U盘中存放多个镜像，在启动时可自行选择
* 支持更多用于存放镜像的文件系统，如exfat、ntfs、xfs等，传统工具往往仅支持fat32与ext4
  * 支持4 GB以上大小的镜像
* 对传统BIOS引导与目前较通用的UEFI引导均有较好的兼容
* 可定制性强，使用、扩展较为灵活
* 除Linux外还支持其他操作系统，如Windows、BSD等

在此之后，笔者就在也没有使用过其他的U盘镜像写入工具。

Ventoy的发展也十分迅速，作者会积极响应社区的反馈，不断为Ventoy增加新的功能。笔者在Ventoy刚刚推出时强烈需要的数据持久化功能也于后期更新中加上。数据持久化功能可以把Linux的Live USB中原本应该保存在内存的数据保存在本地存储分区或者文件中，在重启之后不会丢失，相当于把Live USB当成了一个本地化安装的Linux操作系统。

然而，数据持久化方法存在着以下缺点：

* 共性缺点
  * 启动部分由镜像文件写死，**不支持更改内核**
* 持久化文件方案
  * 创建大的持久化文件时U盘**写入时间**很长，不方便
  * 整个内容作为单文件存储在无日志也非写时复制的exfat文件系统中，数据安全性不足
* 持久化分区方案
  * 不支持UEFI启动

因此，如果要充分利用U盘空间，在里面安装系统的话，基于Live USB的持久化数据存储不见得是一个好的方案。

Ventoy还支持将`.vhd`虚拟机磁盘作为本地系统启动，但是这种方法仅支持固定大小的虚拟机文件，创建文件时仍然需要长时间写入。

所以，仍有必要在U盘内部的单独分区真正安装Linux操作系统。

## 准备

笔者以主流发行版中安装流程较复杂的Arch Linux为例，在此梳理在U盘中安装Linux并由Ventoy引导的过程。笔者在本地安装的另一个Arch Linux中运行Ventoy与Arch Linux的安装过程，不需要另外下载Arch Linux的ISO。虽然还是在Ventoy的数据分区下存储了一个，以备以后不时之需。（（（

## Ventoy启动盘制作

### Ventoy软件安装

在本地系统上安装Ventoy，对于Arch Linux，可以添加archlinuxcn等第三方源，也可以直接从AUR安装，Manjaro等基于Arch Linux的发行版则可能直接在官方源中继承了Ventoy，可以直接安装。总之，可以运行安装命令：

```bash
yay -S ventoy-bin
```

其余发行版可以自行查找对应的安装方法，也可以下载[Ventoy的源码](https://www.ventoy.net/cn/download.html)编译，Windows也可以直接[下载Ventoy的安装程序以安装](https://www.ventoy.net/cn/download.html)，此处不再赘述。

### 启动盘写入

启动Ventoy的GUI程序，点击`配置选项`->`分区设置`，勾选`在磁盘最后保留一段空间`，输入并确认你想为系统安装保留的大小。笔者在这里保留了32 GB：

[![#~/img/ventoy/ventoy-reservation.webp](/img/ventoy/ventoy-reservation.webp)](/img/ventoy/ventoy-reservation.webp)

然后检查目标硬件是否是想要制作Ventoy启动盘的硬件，确认后点击`安装`。此时Ventoy会格式化整个U盘，注意数据备份。一般来说Ventoy启动盘制作较快，几秒到几十秒不等即可制作完成。

## 分区处理及挂载

制作完成的Ventoy启动盘分为3个部分：第一部分是Ventoy的数据空间，可以用来保存日常数据以及为Ventoy提供的启动镜像；第二部分是Ventoy的引导分区，大小较小，仅32 MB；第三部分即为我们的保留空间。制作完成以后，Ventoy的保留空间尚未分区或格式化，我们需要手动分区。由于我们现在在GUI的环境下，可以直接用GParted或者KDE分区管理器进行分区。

由于安装在U盘中，为了减少对U盘闪存的磨损，我们可以采用对闪存特别优化的文件系统。除了经典的ext4和XFS文件系统之外，我们还有F2FS和Btrfs这两个主流选择。虽然F2FS被部分手机厂商宣传得神乎其神，但在笔者的测试中性能并不突出，而且功能性、可扩展性和稳定性均较其他现代主流Linux文件系统差，笔者首先将其排除。Btrfs则具有写时复制、快照、配额、**可释放空间的**透明压缩等大量高级功能[^1]。近几年来，Btrfs主要功能稳定性已经得到保证，在大型企业级服务器上的应用表现也较为优秀，在近两年的Linux内核更新中，Btrfs性能提升巨大，笔者一直在NVMe固态硬盘与机械硬盘中使用Btrfs，其性能在简单测试下可与XFS比肩，较显著地超过ext4（使用Linux 6.1内核），[高级测试方法也有类似的结论](https://openbenchmarking.org/result/2107263-IB-2107261IB78)，因此笔者使用了Btrfs文件系统。

U盘中的操作系统可能并没有必要使用快照等功能，笔者在这里没有建立子卷，直接在Btrfs的默认子卷下安装。由于U盘上的IO瓶颈较为显著，笔者建议在U盘上启用较为激进的透明压缩。挂载时，推荐启用压缩参数，假设创建的分区在`/dev/sdb3`：

```bash
sudo mount /dev/sdb3 -o compress-force=zstd:6 /mnt
```

以上命令将会强制对写入的所有文件进行压缩尝试，压缩算法为Zstandard，压缩等级为6（而默认压缩等级为3），能提供较大的压缩比。

然后，为了在任意挂载情况都启用压缩，我们还可以人为指定压缩算法：

```bash
sudo btrfs property set /mnt compression zstd
```

以上命令表示在`/mnt`下创建的文件将默认尝试用zstd算法压缩（即使在无挂载参数时仍会尝试，但没有`compress-force`选项时不会对“不可压缩文件”[^2]尝试压缩）。

## Arch Linux系统安装

本部分遵照[Arch Wiki: 安装指南](https://wiki.archlinuxcn.org/wiki/%E5%AE%89%E8%A3%85%E6%8C%87%E5%8D%97)的方法进行操作即可。

由于前一部分已经完成了分区、格式化与挂载到`/mnt`目录的操作，我们可以直接用`pacstrap`命令进行安装；由于U盘空间较小，且主系统往往存在大量可利用的软件包缓存，我们还可以传递`-c`参数以利用主系统的缓存安装包

先安装较基本的软件包，这里需要用到`pacstrap`命令，如果提示找不到该命令，可能是相关软件包没有安装，需要先在主系统中安装`arch-install-scripts`：

```bash
sudo pacman -S --needed arch-install-scripts
```

然后执行

```bash
sudo pacstrap -c -K /mnt --needed \
        base base-devel linux linux-firmware \
        amd-ucode intel-ucode \
        btrfs-progs xfsprogs f2fs-tools nilfs-utils dosfstools exfatprogs ntfs-3g lvm2 \
        sof-firmware networkmanager \
        nano vim man-db man-pages texinfo \
        noto-fonts-cjk noto-fonts-emoji
```

然后再选择一个DM安装，以在不同桌面环境间较通用LightDM为例：

```bash
sudo pacstrap -c -K /mnt --needed lightdm
```

再选择一个桌面环境。由于笔者主系统用了KDE，备用盘用了Cinnamon，虚拟机用了Xfce，这里仅仅是个U盘，不需要太追求稳定性，也不太想用配置较繁琐的桌面环境，笔者就直接选择了自己初中时首次真正入坑Linux用的桌面环境——deepin开发的DDE：

```bash
sudo pacstrap -c -K /mnt --needed deepin deepin-extra deepin-kwin
```

安装完成后，配置U盘中操作系统的`fstab`：

```bash
sudo su
genfstab -U /mnt >> /mnt/etc/fstab
```

注意，`genfstab`命令必须直接在root账户下运行，`sudo genfstab -U /mnt >> /mnt/etc/fstab`会提示权限错误。生成完后，需要手动编辑，移除本地的swap分区，因为本地的swap分区并不保证在U盘系统中可用。此外，还建议给Btrfs分区加上`noatime`和`compress-force=zstd:6`两个挂载参数，分别用于减小读写量与强制启用等级为6的zstd压缩。

接下来，使用`arch-chroot`命令切换到U盘系统的目录下：

```bash
sudo arch-chroot /mnt
```

在U盘系统下设置中国时区：

```bash
ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
hwclock --systohc
```

使用U盘系统的`vi`、`nano`等命令或直接在主系统中编辑本地化设置，将主系统下的`/mnt/etc/locale.gen`（即U盘系统下的`/etc/locale.gen`）的`en_US.UTF-8 UTF-8`与`zh_CN.UTF-8 UTF-8`取消注释，然后在`arch-chroot`的环境中运行：

```bash
locale-gen
```

创建主系统下的`/mnt/etc/locale.conf`（即U盘系统下的`/etc/locale.conf`），内容可以设定为`LANG=zh_CN.UTF-8`

创建主系统下的`/mnt/etc/hostname`（即U盘系统下的`/etc/hostname`），其中的内容为设定的主机名称。

为U盘中的系统启用DM和网络管理器，以LightDM为例：

```bash
systemctl enable lightdm.service
systemctl enable NetworkManager.service
```

设定root密码：

```bash
passwd
```

创建非root账户：

```bash
useradd -m 用户名
```

设定用户密码：

```bash
passwd 用户名
```

将用户加入`wheel`用户组，以便支持`sudo`权限：

```bash
usermod -aG wheel 用户名
```

编辑`sudo`配置，为`wheel`组加入`sudo`使用权限：

```bash
EDITOR=nano visudo
```

在编辑时取消`%wheel      ALL=(ALL): ALL`一行的注释即可。

## 引导配置

Ventoy启动盘中的引导应当由Ventoy统一管理，不必在U盘的Linux系统中安装`grub`等引导软件，也不必另外放置`efi`文件。

Ventoy支持使用自定义的grub配置，可由此引导本地安装的操作系统。

在Ventoy启动盘的**数据与镜像分区**新建一个`ventoy`目录，在其中创建一个`ventoy_grub.cfg`文件，内容为：

```
menuentry "Linux On USB Flash" --class=custom {
    set root=($vtoydev,gpt3)
    linux /boot/vmlinuz-linux root=UUID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    initrd /boot/initramfs-linux.img
    boot
}
menuentry '<-- Return to previous menu [Esc]' --class=vtoyret VTOY_RET {
    echo 'Return ...'
}
```

`set root=($vtoydev,gpt3)`语句用来设定U盘内安装的系统的位置，`$vtoydev`表示Ventoy所在存储设备，而由于Ventoy固定前面了两个分区的内容，故安装位置多为`gpt3`。此外，需要将`root=UUID=`后面的内容**替换**为安装分区的实际UUID。

引导配置完成后，重启进入Ventoy启动盘引导，按`F6`即可进入自定义的grub设定菜单，按下`Enter`启动系统，使用方法与经典的引导、安装方式基本一致，此处不再赘述。

## 捐赠

|  **支付宝**  |  **微信支付**  |
|  :----:  |  :----:  |
|  [![](/img/donate-alipay.webp)](/img/donate-alipay.webp)  |  [![](/img/donate-wechatpay.webp)](/img/donate-wechatpay.webp)  |


[^1]: Btrfs等文件系统的透明压缩可以用于节约空间与减小写入量，但F2FS的透明压缩节省的空间并不可利用，仅能用来减小写入量。

[^2]: 参见[Btrfs Wiki对不可压缩文件处理方式的介绍](https://btrfs.wiki.kernel.org/index.php/Compression#What_happens_to_incompressible_files.3F)
