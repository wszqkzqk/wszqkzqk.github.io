---
layout:       post
title:        PvZ-Portable：longjmp 错误路径上的内存清理
subtitle:     图像解码器中的泄漏、双重释放与 volatile 指针
header-img:   img/games/pvz-portable/bg-pvz-portable.webp
date:         2026-09-14
author:       wszqkzqk
catalog:      true
tags:         C++ 内存管理 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

PvZ-Portable 的图像解码集中在 ImageLib：资源包里的图片（PNG、JPEG、GIF）由它读成位图，再交给渲染器。其中 PNG 和 JPEG 的解码依赖两个经典 C 库——libpng 和 libjpeg。这两个库报告致命错误的方式不是返回值，也不是异常，而是 `longjmp`：解码器遇到损坏的数据，直接跳回调用方预先设置的恢复点。

这套错误模型和 C++ 的内存管理天生冲突。`longjmp` 不做栈展开，跳过的 C++ 对象不会执行析构，RAII 在它面前帮不上忙。PR [#439](https://github.com/wszqkzqk/PvZ-Portable/pull/439) 修了一组资源管理问题，[之前的文章](https://wszqkzqk.github.io/2026/09/06/PvZ-Portable-Music-Map-Data-Race/)提过其中加载线程共享变量的部分。本文聚焦另一条线：图像解码器错误路径上的内存问题。

旧代码在解码中途出错时会泄漏像素缓冲区。把缺失的释放补上并不复杂，真正有意思的是随之而来的两个坑：一个来自 C++ 标准里一条关于 `volatile` 的冷门条款，另一个则是所有权转移之后形成的双重释放窗口。

## 旧的错误路径漏掉了什么

以 JPEG 解码为例。libjpeg 的错误处理需要调用方提供一个自定义错误函数，由它执行 `longjmp`。解码前用 `setjmp` 登记恢复点。修复前的错误路径是这样的（`src/SexyAppFramework/imagelib/ImageLib.cpp`）：

```cpp
	if (setjmp(jerr.setjmp_buffer))
	{
		/* If we get here, the JPEG code has signaled an error.
		 * We need to clean up the JPEG object, close the input file, and return.
		 */
		jpeg_destroy_decompress(&cinfo);
		p_fclose(fp);
		return 0;
	}
```

错误路径清理了 libjpeg 对象、关闭了文件，看起来滴水不漏。问题在于像素缓冲区的分配发生在 `setjmp` **之后**：

```cpp
	aBits = new uint32_t[cinfo.output_width*cinfo.output_height];
	uint32_t* q = aBits;

	if (cinfo.output_components==1)
	{
		while (cinfo.output_scanline < cinfo.output_height)
		{
			jpeg_read_scanlines(&cinfo, buffer, 1);   // 损坏数据在这里触发 longjmp
			...
```

`jpeg_read_scanlines` 读行时遇到损坏数据，`longjmp` 直接跳回 `setjmp` 处。刚分配的 `aBits` 既不在错误路径的清理清单里，也没有 RAII 对象接管——每次解码失败就泄漏一份。PNG 解码器是同一种结构，`row_pointers` 和 `aBits` 两块缓冲区面临同样的问题。

这条路径平时完全走不到：只有资源文件损坏、下载不完整，或者用户自制资源包格式有误时才会进入。也正因为如此，泄漏可以潜伏很多年而不被察觉。

## 加上 `delete[]` 还不够

直观做法是在错误路径里加上 `delete[]`。但这件事有两个不那么直观的约束，缺了任何一个，修复本身就是错的。

### longjmp 之后，普通局部变量的值是未确定的

C++ 标准对 `setjmp`/`longjmp` 有一条专门规定（[csetjmp]）：在 `setjmp` 与 `longjmp` 之间被修改过的自动变量，如果没有 `volatile` 限定，`longjmp` 之后读到的值是未确定的。原因很实际：`setjmp` 保存的是当时的寄存器状态，`longjmp` 恢复现场后，编译器完全有权让变量继续使用寄存器里的旧值，而不是内存里被修改过的新值。

所以，凡是在 `setjmp` 之后赋值、又要在错误路径里读取的指针，都必须声明为 `volatile`，强迫编译器每次从内存读取。修复后的声明：

```cpp
	// must be volatile: assigned after setjmp, read in the error path after longjmp
	uint32_t* volatile aBits = nullptr;
	Image* volatile anImage = nullptr;

	if (setjmp(jerr.setjmp_buffer))
	{
		jpeg_destroy_decompress(&cinfo);
		delete[] (uint32_t*)aBits;
		delete anImage;
		p_fclose(fp);
		return 0;
	}
```

两个细节值得一看。指针初始化为 `nullptr`：如果 `longjmp` 发生在分配之前，错误路径 `delete[] nullptr` 是无害的空操作，清理逻辑不需要分支判断。另外，`volatile` 指针不能直接 `delete`，需要显式 cast 去除限定——这就是 `(uint32_t*)aBits` 这层转换的由来。

### 所有权转移后的双重释放

只补 `delete[] aBits` 还不够，因为正常路径的末尾是这样的：

```cpp
	anImage = new Image();
	anImage->mWidth = cinfo.output_width;
	anImage->mHeight = cinfo.output_height;
	anImage->mBits.reset(aBits);
	aBits = nullptr; // anImage owns it now; avoid double delete in the error path

	jpeg_finish_decompress(&cinfo);
	jpeg_destroy_decompress(&cinfo);
```

`ImageLib::Image` 的 `mBits` 是 `std::unique_ptr`，`reset(aBits)` 之后，像素缓冲区的所有权就归图像对象了。但注意，所有权转移**之后**还有两个 libjpeg 调用：`jpeg_finish_decompress` 和 `jpeg_destroy_decompress`，它们同样可能 `longjmp`。

如果此时出错，错误路径会执行 `delete[] aBits` 和 `delete anImage`：前者释放像素缓冲区，后者析构图像对象、连带释放 `mBits`——同一块内存被释放两次。所以转移所有权的下一行必须立刻 `aBits = nullptr`，让错误路径里的 `delete[]` 退化成空操作，只剩下 `delete anImage` 一个有效的清理动作。

PNG 解码器没有这一步置空，原因也很说明问题：它的正常路径里，所有 libpng 调用都在创建图像对象**之前**完成。`png_destroy_read_struct` 之后不再调用 libpng，`longjmp` 也就不可能再发生，自然不存在这个窗口。需不需要置空，取决于所有权转移之后还会不会回到可能 `longjmp` 的库调用里——这正是审查这类代码时要逐行确认的地方。

## 为什么 GIF 可以直接用 RAII

同一次修改里，GIF 解码器的待遇完全不同：文件句柄、调色板、LZW 解码表全部包进了 `std::unique_ptr`：

```cpp
	std::unique_ptr<PFILE, decltype(&p_fclose)> fp(p_fopen(theFileName.c_str(), "rb"), &p_fclose);
	...
	std::unique_ptr<unsigned char[]> global_colormap;
```

差别不在于两个解码器谁更新，而在于错误模型。GIF 解码器是项目自己的代码，出错走正常的 `return`，控制流按原路返回，局部对象的析构函数都会执行，RAII 自然有效。PNG 和 JPEG 的错误路径由 `longjmp` 进入，不经过析构，只能手工设计清理逻辑。

也有另一条路：libpng 允许注册自定义错误函数，理论上可以在里面抛 C++ 异常，把错误模型整个换掉。但异常要穿过 C 库的栈帧才能回到调用方，而这些帧可能没有展开信息，可移植性没有保证。相比之下，`volatile` 指针加幂等清理完全留在 C 的规则内，不依赖任何库的额外支持，是更保守的选择。

把这次的模式总结成三条，对所有使用 `setjmp`/`longjmp` 错误模型的 C 库都适用：

1. 需要在错误路径清理的指针，初始化为 `nullptr` 并声明为 `volatile`；
2. 所有权一旦转移给别的对象，立即把原指针置空；
3. 错误路径无条件执行清理，靠释放空指针是空操作这一事实保证幂等，而不是靠状态判断。

顺带一提，JPEG 编码（`WriteJPEGImage`）也有 `setjmp` 保护区，这次按同一模式处理了它的临时缓冲区。

## 结语

C 库与 C++ 的交界处是存量代码里很容易藏问题的地方：两边各自看起来都对，拼在一起就出事。`longjmp` 不执行析构、非 `volatile` 变量的值在跳转后不确定，这两条规则单独看都不算生僻，但只有真正在错误路径上栽过跟头，才会意识到它们的分量。

这类 bug 还有一层隐蔽性：错误路径本身就是冷路径，内存错误又让它冷上加冷。功能测试用的是完好的资源文件，永远走不到这里。只有损坏、截断或手工构造的输入才能触发。审查 `setjmp` 保护区时，我的做法是把区内的资源逐个列出来，标注每个资源在错误路径上由谁释放、会不会释放两次——清单列完，问题通常自己浮出来。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。研究或使用此项目时，**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies)购买）。你需要从正版游戏中提取以下文件，放到 PvZ-Portable 的程序所在目录：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
