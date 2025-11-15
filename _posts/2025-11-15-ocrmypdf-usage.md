---
layout:     post
title:      ocrmypdf：从扫描件到可检索文字的PDF/A的方法
subtitle:   对纯图片PDF嵌入文字的软件推荐
date:       2025-11-15
author:     wszqkzqk
header-img: img/bg-leaf-on-the-lake-darken.webp
catalog:    true
tags:       OCR PDF 开源软件 媒体文件
---

## 前言

[ocrmypdf](https://github.com/ocrmypdf/OCRmyPDF) 是一个开源的命令行工具，用于将扫描或其他方式制作的纯图 PDF 文件转换为可搜索和可选中文本的 PDF 文件。它通过集成 Tesseract OCR 引擎，自动识别扫描件中的文字，并将其嵌入到 PDF 中，从而实现全文搜索和复制功能。ocrmypdf 支持多种语言和字符集，适用于各种类型的文档处理需求。

在某些 LLM 的 API 不支持直接处理图片 PDF 的情况下，ocrmypdf 可以作为前置步骤，将扫描件转换为嵌入了文本的 PDF，使得后续处理可以将其当作普通文本来处理，极大提升了工作流的便利性。

之前笔者写过 Ghostscript、ImageMagick 等 PDF/图片处理工具，ocrmypdf 则负责把一堆扫描件或者纯图塞进 Tesseract 再吐出可检索的 PDF/A。它的优势主要是：

* 默认就走 PDF/A-2b 流程，适合归档
* 自带页面旋转、去背景、deskew 等预处理
* 支持 sidecar 文本、插件化流程，方便二次处理

## 安装

Arch Linux 用户可以从 AUR 安装：

```bash
paru -S ocrmypdf
```

如果系统里已经装好了 ocrmypdf，先跑一遍版本确认：

```bash
ocrmypdf --version
```

## 基本命令格式

命令的核心只有两个位置参数：输入文件与输出文件。

```bash
ocrmypdf input.pdf output.pdf
```

常见扫描件往往是纯图片 PDF，这条命令会默认：

1. 逐页 rasterize
2. 交给 Tesseract OCR
3. 输出 PDF/A-2b（`--output-type pdfa`）

如需保留原始压缩方式，可将输出改为普通 PDF：

```bash
ocrmypdf --output-type pdf book.pdf book-searchable.pdf
```

## 语言与多语言 OCR

ocrmypdf 调用 Tesseract 进行 OCR，**正确选择语言**对提升识别率至关重要，在不指定语言时，默认仅能识别英语。Tesseract 的语言包装在 `-l` / `--language` 选项里，用 `+` 连接多语言，例如当前文档包含中英文时：

```bash
ocrmypdf -l chi_sim+eng docs.pdf docs-ocr.pdf
```

建议提前用 `tesseract --list-langs` 确认哪些语言已装好，缺失就 `sudo pacman -S tesseract-data-xxx` 或 `pip install tesseract-ocr` 补齐。

## 控制输出格式与元数据

* `--output-type {pdfa,pdf,pdfa-1,pdfa-2,pdfa-3,none}`：决定是否强制 PDF/A
* `--sidecar`：额外导出纯文本，便于全文索引
* `--title/--author/--subject/--keywords`：重写元数据，默认会沿用输入文件的 metadata

示例：

```bash
ocrmypdf \
	--title "example" \
	--author wszqkzqk \
	--keywords "tag1,tag2" \
	--sidecar example.txt \
	scan.pdf example.pdf
```

若只想要 sidecar 文本，可把 `--output-type none` 并指定 `--sidecar -`，文本会直接输出到 stdout。

## 图像预处理常用组合

ocrmypdf 内置的清理参数可以显著提升识别率：

```bash
ocrmypdf \
	-r --rotate-pages-threshold 10 \
	-d --deskew \
	--remove-background \
	--oversample 400 \
	notebook.pdf notebook-ocr.pdf
```

* `-r/--rotate-pages`：根据文字方向自动旋转，可配 `--rotate-pages-threshold`
* `-d/--deskew`：矫正扫描倾斜
* `--remove-background`：去除彩色底纹
* `--oversample DPI`：低分辨率扫描件可适当放大至 300~400 DPI

对于噪声严重的稿件，可以打开 `--clean` 或 `--clean-final`（后者会把清理后的图像写回 PDF），并用 `--unpaper-args '--layout double'` 这类参数传给 unpaper。

## OCR 行为控制

| 选项 | 适用场景 |
| --- | --- |
| `-s/--skip-text` | PDF 里混有本就可选中文本的页面，避免重复 OCR |
| `-f/--force-ocr` | 强制把所有对象 rasterize，适合“乱七八糟的导出” |
| `--redo-ocr` | 移除旧的隐藏 OCR 层后重新识别 |
| `--skip-big MPixels` | 对超大幅面图纸跳过 OCR 但仍保留页面 |

批量扫描时，通常的流程是：

```bash
ocrmypdf --skip-text input.pdf output.pdf   # 只处理纯图片页
```

如果拿到的是数码导出的 PDF 但希望统一做 OCR，则需要用 `--force-ocr`，但这会重新 光栅化，**体积和画质都会受影响**。

## 性能与优化参数

* `-j/--jobs N`：并行核心数，默认跑满
* `-q/--quiet`、`-v/--verbose N`：日志级别
* `-O/--optimize {0..3}`：控制 Ghostscript 后处理强度，`2`、`3` 会启用有损 JPEG/JBIG2
* `--jpeg-quality` / `--png-quality`：细调图像压缩
* `--jbig2-lossy`：扫描件大量黑白文本时可显著减小体积，但不适合留档合同
* `--fast-web-view`：超过阈值时自动 linearize，便于浏览器边下边看

示例：

```bash
ocrmypdf -j 16 -O 1 --fast-web-view 0 paper.pdf paper-ocr.pdf
```

## 输入是图片而非 PDF 的情况

ocrmypdf 可以直接读取 `jpg/png/tiff`，但更推荐先用 `img2pdf` 控制页面尺寸，再通过管道喂给 OCR：

```bash
img2pdf --pagesize A4 page*.png | ocrmypdf - notebook.pdf
```

当图片自带 DPI 信息时不正确时，还可以手动指定：

```bash
ocrmypdf --image-dpi 300 scan.jpg scan.pdf
```

## Tesseract 进阶参数

当默认配置无法识别表格或版面时，可以尝试：

```bash
ocrmypdf \
	--tesseract-pagesegmode 6 \
	--tesseract-oem 1 \
	--tesseract-thresholding sauvola \
	--user-words custom_words.txt \
	blueprint.pdf blueprint-ocr.pdf
```

* `--tesseract-pagesegmode` (PSM) 用于切换版面分析策略
* `--tesseract-oem` 控制 LSTM/传统引擎
* `--tesseract-thresholding` 在低对比度扫描件上很有用
* `--user-words/--user-patterns` 能帮专业术语拿到更高置信度

记得配合 `--tesseract-timeout` 与 `--tesseract-non-ocr-timeout`，防止异常页面卡死：

```bash
ocrmypdf --tesseract-timeout 120 --tesseract-non-ocr-timeout 30 big.pdf big-ocr.pdf
```

## 故障排查与调试

* `--continue-on-soft-render-error`：遇到字体缺失等渲染警告时继续下一页
* `--max-image-mpixels`：避免“decompression bomb”式的巨大图片
* `-k/--keep-temporary-files`：保留临时目录，方便分析预处理结果

执行失败时，临时目录里会有 `step-XXX` 的中间文件，结合 `-v 1` 的日志通常能定位问题。

## 小结

ocrmypdf 的命令行选项很多，但日常流程基本可以归纳为：确定语言 → 选择输出格式 → 按需打开预处理与优化 → 视情况启用 sidecar 或 Tesseract 进阶配置。想继续深挖可直接阅读[官方文档](https://ocrmypdf.readthedocs.io/en/latest/introduction.html)。
