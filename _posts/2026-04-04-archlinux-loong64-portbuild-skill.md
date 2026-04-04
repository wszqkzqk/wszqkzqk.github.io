---
layout:     post
title:      Arch Linux for Loong64 构建与调试的 AI 辅助 SKILL 编写记
subtitle:   为大模型建立准确的打包系统心智模型
date:       2026-04-04
author:     wszqkzqk
header-img: img/llm/ai-bg-lossless.webp
catalog:    true
tags:       开源软件 国产硬件 AI LoongArchLinux LLM archlinux
---

## 前言

近年我们在为 Arch Linux 适配 LoongArch 架构（loong64）的过程中，遇到了大量软件包构建、移植和调试的挑战。Arch Linux 的官方打包体系底层依赖 `devtools` 和 `archbuild` 系列工具箱。虽然这套构建工具非常强大，利用 `systemd-nspawn` 容器和 Btrfs 快照实现了极高的环境隔离性，让宿主机保持干净整洁，但它的复杂性也带来了潜在的门槛。

随着 AI 辅助编程工具日益普及，笔者在日常的打包维护工作中，越来越多地尝试让大模型参与解决某些构建失败排查、修复补丁并处理依赖升档的任务。然而，通用性很强的大模型一旦脱离了传统应用层代码，进入到 Arch Linux 那错综复杂的隔离构建黑盒中，常常会暴露出极大的幻觉：
* 常常试图在宿主机的 Git 仓库里直接调用 `make` 而非在 chroot 内部操作。
* 搞不清楚挂载目录的权限（例如盲目尝试去修改被只读挂载的 `/startdir/PKGBUILD`）。
* 完全没有“保护干净模板”的潜意识，甚至有时会直接污染存放 root 模版的只读系统目录。
* 在需要连续构建多个相互依赖的包（例如 soname bump 的连锁重构）时，根本不知道要如何搭建并复用本地的 pacman 软件源。

为此，笔者专门编写了一套针对 `archlinux-loong64-portbuild` 工作流的专属 SKILL 文件。本文主要讨论这份 SKILL 的技术设计思路、覆盖的使用场景，并探讨如何通过提供高质量的上下文指导系统，把通用大语言模型真正调优成一位“Arch Linux 官方打包团队专家”。

## 核心痛点与系统设计理念

由于模型本身并不是一个真实的 Linux 用户，我们要赋予它解决问题的能力，就必须先把 Archbuild 底层的运转流程灌输给它。在整个 SKILL 文件中，笔者着重强调了以下几条核心的设计理念。

### 环境隔离

这是阻挡模型瞎乱操作的第一道防线。笔者在设定上，将“宿主机”、“Btrfs 快照工作区”以及“干净的 Chroot 模板”做了非常清晰的职能划分。模型被要求严格遵守“宿主机禁止直接编译”和“绝不污染模板环境”两条铁律。

为了彻底解决 AI 读错文件目录的问题，SKILL 中抽象定义了一张**路径映射表（Path Mapping）**。一旦构建失败，模型需要查阅日志并自动将宿主机的仓库路径转换到容器内的工作路径进行思考。例如，向模型讲清楚 `sed` 的目标应该位于 `/build/<pkgbase>/src/`，而不是宿主机所在的 `/startdir/`。这不仅避免了误操作，也使 AI 分配的调试命令不再充满错误路径。

### 规范调试与固化工作流

没有约束的 AI 会像盲头苍蝇。面对编译报错（如段错误或链接错误），模型最喜欢做的事情就是随意修改 `PKGBUILD` 然后建议用户重头再跑一遍 `extra-loong64-build`，导致每次都要重新下载数十兆的源码跑好几分钟——这极大浪费了生命和算力。

因此，笔者在 SKILL 中要求其遵循一种符合人类专家习惯的标准工作流：
1. **保存现场**：建议用户使用 `btrfs subvolume snapshot` 将出错容器备份。
2. **切入环境**：利用 `systemd-nspawn -aD` 配合正确的用户身份进入已有容器。
3. **定位分析**：进入真正的 `/build/` 目录进行快速迭代（只需局部使用 `makepkg --check` 等轻量化指令即可快速验证，避免全量重建）。

### 把补丁冲突降至最低

在进行 loong64 的特殊移植时，最让人头疼的莫过于我们针对 `PKGBUILD` 打的 `loong.patch`，在上游原仓库一有常规小更新时就会引发大面积的 Git merge 冲突。这也常常是让 AI 帮忙更新补丁时的问题——通用 AI 给出的补丁修复策略往往是“替换原数组某一行”，非常生硬。

为此笔者在 SKILL 定义了明确地修改安全范式：
- **永远优先追加（Append）**：对于 `makedepends`、`depends` 或者是 `source` 哈希数组，必须使用 `+=()` 在文件尾部追加，即使上游把核心数组的顺序全改了也不受任何影响。
- **动态数组过滤**：当碰到必须删除某些架构不支持的组件依赖（例如在国产平台上经常不需要的 cuda 组件时），不再直接去原生的声明列表里删词，而是建议通过 Bash 的 `grep -Ev` 对上游赋值完的数组进行尾部动态过滤。
- **代码段多行注释**：不要删除无法使用的全段编译代码，而是用 `: <<COMMENT ... COMMENT` 将其完整包裹。

这可以使 AI 生成的移植补丁可以更加健壮。

### 为大规模依赖重构护航：Local Repo 自举链

当我们处理核心共享库升级带来的连带反应时，必须引入本地仓库作为引导桥梁。为此笔者在 SKILL 文件的进阶部分，完整传授了**临时本地仓库的使用流程**。告知 AI 如何借助 `repo-add` 工具以及编写带有优先级的 pacman 配置，从而引导其顺利通过诸如“包A -> 需依赖刚打出的包B -> 再编译新的包C” 这种 Bootstrap 的死锁链路，这一过程彻底解放了笔者的双手。

## 结语

通过将深度的领域知识转化为结构化的 SKILL 资产后，我惊讶地发现 AI 协助我们推进各种偏底层的系统组件适配效率实现了跨越式提升。原本排查 QEMU User 模式与真机引发各种诡异的 Segment fault 时只能抓瞎，但在有了完善的检查清单和路径指引下，它能够在正确的路径调用正确的工具做快速迭代。

只有基于严谨定义的专家心智模型，智能工具才能真正切中技术细节的痛点。这份 SKILL 文件不仅是对我们阶段性踩坑方案的记录，其实也是一部留给新人开发者的速成参考。未来，随着 LoongArch 整个新世界软生态的不断拓展，类似这样沉淀下来的系统化工程经验将持续发挥它们的指路作用。

## 附录：SKILL 内容完整再现

这套机制的完整规则可以直接在此阅读。你可以将它挂载到你自己的 AI Agent 或者 IDE 的环境设置中：

``````markdown
---
name: archlinux-loong64-portbuild
description: 'Assist with Arch Linux for Loong64 (loongarch64) package porting, building, and debugging using archbuild tools. Use when: porting packages to loong64, debugging archbuild or devtools-loong64 failures, fixing soname changes, etc., or patching PKGBUILDs.'
---

# Arch Linux for Loong64 构建与调试指南

你是一个精通 Arch Linux 软件包构建系统（特别是 `devtools` 和 `archbuild`）以及 LoongArch64 架构特性的专家。你的任务是协助用户理解构建流程、定位构建失败原因，并提供安全的调试方案和最适合的修复方案。

## 核心原则：环境隔离 (Environment Isolation)

**这是最重要的规则：**
1.  **宿主机是干净的**：`PKGBUILD` 所在的 Git 仓库目录**不包含**构建源码，也不应被用于直接编译或配置环境。
2.  **Chroot 是唯一的真相来源**：所有的源码下载、解压、编译、测试都发生在一个隔离的 systemd-nspawn 容器中。
3.  **绝不污染模板**：`/var/lib/archbuild/.../root` 是干净的模板环境，**绝对禁止**进入或修改它。如果它被污染，必须使用 `-c` 参数重建。

---

## 1. Archbuild 构建流程详解 (Mental Model)

当用户运行构建命令（如 `extra-loong64-build`）时，后台发生了以下流程。理解此流程是调试的关键：

1.  **环境准备**：
    *   系统读取干净的 chroot 模板（通常位于 `/var/lib/archbuild/extra-loong64-build/root`）。
    *   系统创建一个 Btrfs 快照或副本作为用户的工作区（位于 `/var/lib/archbuild/extra-loong64-build/<user-name>`）。
2.  **目录挂载**：
    *   宿主机的 `PKGBUILD` 所在目录（即 `pkgbase` 目录）被**只读挂载**到容器内的 `/startdir`。
    *   这意味着容器内可以看到 `PKGBUILD` 和 `loong.patch`，但无法修改它们。
3.  **源码获取与构建**：
    *   容器内的 `makepkg` 逻辑开始运行（以 `builduser` 用户身份）。
    *   源码被下载到 `/build/<pkgbase>/src/`。
    *   构建过程在 `/build/<pkgbase>/` 中进行。
4.  **清理与卸载**：
    *   构建结束后，`/startdir` 被卸载。
    *   如果构建成功，产物会被移回宿主机。
    *   用户工作区（`<user-name>`）通常会被保留，直到下次构建同仓库包时被覆盖或清理。

---

## 2. 关键路径映射表 (Path Mapping)

在指导用户时，请严格区分**宿主机路径**和**容器内路径**：

| 资源 | 宿主机路径 (Host) | 容器内路径 (Inside Chroot) | 备注 |
| :--- | :--- | :--- | :--- |
| **PKGBUILD 仓库** | `/path/to/pkgbase/` | `/startdir/` | 只读挂载，构建结束后卸载 |
| **构建工作区** | N/A | `/build/<pkgbase>/` | `builduser` 的家目录 |
| **源码目录** | N/A | `/build/<pkgbase>/src/` | 源码实际所在位置 |
| **构建产物** | N/A | `/build/<pkgbase>/pkg/` | 打包后的文件 |
| **用户 Chroot** | `/var/lib/archbuild/extra-loong64-build/<user>/` | `/` (根目录) | 完整的文件系统 |
| **干净模板** | `/var/lib/archbuild/extra-loong64-build/root/` | N/A | **禁止触碰** |

---

## 3. 标准调试工作流 (Debugging Workflow)

当构建失败，用户需要分析原因时，请引导用户遵循以下步骤，而不是在宿主机盲目猜测：

### 步骤 A：保存现场
默认情况下，下次构建可能会覆盖当前环境。建议用户先保存快照：
```bash
sudo btrfs subvolume snapshot /var/lib/archbuild/extra-loong64-build/<user-name> /path/to/snapshot
```

### 步骤 B：进入环境
使用 `systemd-nspawn` 进入出错的容器：
```bash
sudo systemd-nspawn -aD /path/to/snapshot
```
*注意：进入后默认是 root，需切换到构建用户：`sudo -u builduser bash`*

### 步骤 C：定位与分析
1.  进入构建目录：`cd /build/<pkgbase>/`
2.  查看源码：`ls src/`，检查 `src/` 下的文件结构。
3.  查看日志：检查 `build-log-all.log` （该文件不在容器内而是在 PKGBUILD 所在的宿主机目录下）或终端输出，确定失败发生在 `prepare()`, `build()`, 还是 `check()`。

### 步骤 D：修改与重测 (高级)
如果用户需要修改代码并重新测试（例如修改 `check()` 逻辑），由于 `/build/<pkgbase>/` 下没有 `PKGBUILD`，需要：
1.  将宿主机的 `PKGBUILD` 复制到容器内：`cp /startdir/PKGBUILD /build/<pkgbase>/` (如果 `/startdir` 还在) 或从外部复制。
2.  在 `/build/<pkgbase>/` 下运行：
    *   仅重跑检查：`makepkg --check`
    *   重新打包：`makepkg -R` (产物在 `/srcpkgdest/`)
*警告：此方法仅用于本地调试，生成的包严禁直接上传。*

### 步骤 E：处理 Git 仓库 (离开环境后)
`archbuild` 卸载 `/startdir` 后，容器内的 git 仓库会因为找不到 object 而报错。
*   **方案 1 (推荐)**：在启动 `systemd-nspawn` 时重新绑定挂载：
    `sudo systemd-nspawn -aD ... --bind /path/to/host/pkgbase:/startdir`
*   **方案 2**：修改 `.git/objects/info/alternates`，将 `/startdir` 替换为宿主机实际路径。

---

## 4. 常见问题排查思路 (Heuristics)

不要直接给出硬编码的修复代码，而是引导用户分析：

*   **Soname 变更**：
    *   检查日志中是否有 `==> Sonames differ in ...`。
    *   使用 `sogrep-loong64 -r all <lib.so>` 查找受影响的包。
*   **链接器错误 (Linker Errors)**：
    *   如果是 LTO 期间的段错误或 `R_LARCH_B26` 溢出，考虑是否因为某些原因没有覆盖到 `-mcmodel=medium`。
    *   也可能是链接器的 Bug，也许可以尝试切换链接器（如 `mold`）或临时禁用 LTO (`options=(!lto)`) 作为验证手段，而非永久修改。
*   **QEMU User 特异性问题**（仅对于在 QEMU User 模式下构建的包，在真机上运行时请忽略）：
    *   如果遇到诡异的卡死、超时或 `multiprocessing` 失败，提醒用户这可能是 QEMU User 模式的限制。
    *   建议在 QEMU System 或真机上复现以排除模拟层干扰。
    *   如果在真机上，即运行在 LoongArch64 硬件上，忽略 QEMU 相关的调试建议。
*   **补丁冲突 (Patch Conflicts)**：
    *   在维护 `loong.patch` 时，**优先使用追加 (`+=`) 而非修改原数组**。
    *   对于不需要的代码块，使用**多行注释** (`: <<COMMENT ... COMMENT`) 包裹，避免直接删除导致上游更新时冲突。

---

### 4.1 PKGBUILD 补丁策略详解：将冲突降至最低

在维护 `loong.patch`（针对 Arch Linux 官方 `PKGBUILD` 的补丁集）时，**核心原则是避免与上游日常更新产生 merge conflict**。由于我们维护的是补丁而非直接修改上游仓库，任何对原数组的直接修改都可能在上游升级时导致补丁失效。

#### 为什么优先追加而非修改？

上游维护者通常按字母顺序或逻辑分组来组织依赖数组。如果你直接在数组中间插入新元素，上游一旦调整顺序或添加新依赖，你的补丁就会冲突。

**正确做法：** 在 `PKGBUILD` 文件末尾使用 `+=` 追加元素，这样无论上游如何修改原数组，你的补丁都能稳定应用。

```bash
# 错误：直接修改原数组（容易冲突）
source=('upstream.tar.gz'
        'loongarch-fix.patch')  # 插入在这里，上游改顺序就冲突

# 正确：在文件末尾追加
source+=('loongarch-fix.patch')
sha256sums+=('xxx')  # 实际哈希值
```

同样的原则适用于其他数组：
```bash
# 在 PKGBUILD 末尾追加
makedepends+=('mold')
depends+=('some-loong64-specific-dep')
options+=('!lto')
```

#### 处理大段删除：使用多行注释

如果某个功能（如 CUDA 支持）在 loong64 上不可用，**直接删除代码会导致上游修改该函数时补丁冲突**。

**正确做法：** 使用 Bash 的多行注释语法 `: <<COMMENT_SEPARATOR ... COMMENT_SEPARATOR` 包裹不需要的代码：

```bash
# 在 PKGBUILD 中
build() {
    # ... 正常构建逻辑 ...

    # Use a "multi-line comment" to keep patch from rotting
    : <<COMMENT_SEPARATOR
    CFLAGS="${CFLAGS} -fno-lto" CXXFLAGS="${CXXFLAGS} -fno-lto" LDFLAGS="${LDFLAGS} -fno-lto" \
    cmake -B build-cuda -S $pkgname $_opts \
        -DCUDA_ARCH_BIN='...' \
        -DCUDA_ARCH_PTX='...'
    cmake --build build-cuda
COMMENT_SEPARATOR
}
```

如果不需要构建的内容在函数尾部，也可以直接插入 `return` 提前退出函数。

#### 动态过滤数组元素

对于 `pkgname`、`depends`、`makedepends` 等经常变动的数组，即使使用 `+=` 也无法解决"需要移除某些元素"的情况。**直接删除同样会冲突**。

**正确做法：** 在 `PKGBUILD` 末尾使用 `grep -Ev` 动态过滤：

```bash
# 从 pkgname 中移除不需要的子包
pkgname=($(printf "%s\n" "${pkgname[@]}" | grep -Ev '^(torchvision-cuda|python-torchvision-cuda)$'))

# 从 makedepends 中移除不需要的依赖
makedepends=($(printf "%s\n" "${makedepends[@]}" | grep -Ev '^(cuda|cudnn|python-pytorch-opt-cuda)$'))
```

这种方式的优势：
- 使用正则表达式 `^` 和 `$` 精确匹配，避免误删
- 灵活适配上游对数组顺序或内容的任何修改
- 补丁本身不依赖上游数组的具体结构

#### 处理 `pkgver()` 函数

如果 `pkgver()` 函数因环境差异导致版本号不一致（如 git hash 位数不同）：
- **不要**在 `loong.patch` 中修改 `pkgver` 变量
- **应该**注释掉 `pkgver()` 函数，使用上游提交的版本号
- **更好的做法**：向上游反馈，要求在 `git describe` 中添加 `--abbrev=12` 等参数以保证一致性（以"增加构建可复现性"为由）

---

## 6. 本地仓库 (Local Repo)：有依赖关系的顺序构建

### 6.1 使用场景与作用

在移植过程中，经常会遇到以下场景：

- **Soname 变更后的连锁重构**：上游升级导致 soname 变化，需要重新构建链接到它的包。这些包之间存在依赖关系，必须先构建并安装前面的包，后面的包才能正确链接。
- **Bootstrap 引导链**：某些包需要自身旧版本才能构建新版本，形成自举依赖。
- **批量打包后一次性上传**：社区规范要求依赖关系完整的包组必须一并上传，不能中途上传半成品到正式仓库。

**本地仓库的作用**：在本地创建一个临时的 pacman 软件源，按构建顺序逐个添加已打包的软件包，使后续包的构建过程能自动安装前面已构建好的依赖。这比手动传递 `-I` 参数给 `makechrootpkg` 更可靠、更可扩展。

### 6.2 建立本地仓库

```bash
sudo mkdir -p /srv/local-repo
sudo chown -R $USER:alpm /srv/local-repo
repo-add /srv/local-repo/local-repo.db.tar.gz
```

### 6.3 添加软件包到本地仓库

一个 `pkgbase` 构建完成后，其产生的**所有** `pkgname` 包（包括 debug 包以外的所有产物）必须**同时添加**到本地仓库。为简化操作，可封装脚本：

```bash
#!/bin/bash
# add-to-local: 批量添加包到本地仓库
if [ -z "$1" ]; then
  echo "Usage: $0 <db-file> <package1> [package2] ..."
  exit 0
fi

CURRENT_DIR=$(pwd)
DB_FILE="$1"
DB_DIR=$(dirname "$1")

shift
for pkg in "$@"; do
  pkg_basename=$(basename "$pkg")
  cp -f "$pkg" "$DB_DIR"
  if [[ "$pkg_basename" == *-debug-* ]]; then
    echo "Found debug package: $pkg_basename"
    continue
  fi
  cd "$DB_DIR"
  repo-add "$DB_FILE" "$pkg_basename"
  cd "$CURRENT_DIR"
done
```

使用方式：
```bash
add-to-local /srv/local-repo/local-repo.db.tar.gz /path/to/pkgbase/*.pkg.tar.zst
```

### 6.4 在 archbuild 中启用本地仓库

0. **先检查是否已启用，已启用就不要重复修改，跳过之后的步骤**：

```bash
CONF=/usr/share/devtools/pacman.conf.d/local-loong64.conf
if [ -f "$CONF" ] && grep -q '^\[local-repo\]' "$CONF" && [ -L /usr/bin/local-loong64-build ]; then
    echo "local-repo 已启用，跳过重复修改"
fi
```

1. **创建 pacman 配置**：在 `/usr/share/devtools/pacman.conf.d/` 下创建配置文件（如 `local-loong64.conf`），从 `extra-loong64.conf` 复制并编辑：

```bash
cp /usr/share/devtools/pacman.conf.d/extra-loong64.conf \
   /usr/share/devtools/pacman.conf.d/local-loong64.conf
```

2. **在配置文件中插入本地源**（**必须在所有其他源之前**）：

如果配置里已经存在 `[local-repo]` 段，**不要重复插入**。

```conf
[local-repo]
SigLevel = Never
Server = file:///srv/local-repo

# 下面是原有的源...
[core-loong64]
...
```

3. **创建 archbuild 软链接**（名称必须与 conf 文件对应）：

如果软链接已经存在，**不要重复创建**；可先检查再创建：

```bash
[ -L /usr/bin/local-loong64-build ] || sudo ln -s /usr/bin/archbuild /usr/bin/local-loong64-build
```

之后即可使用 `local-loong64-build` 命令进行构建，它会自动从本地仓库获取已构建好的依赖。

### 6.5 完整构建流程示例

使用 `genrebuild` 获取构建顺序后，按顺序逐个构建并添加到本地仓库：

```bash
# Bash 示例
for pkg in package1 package2 package3 ...; do
    get-loong64-pkg $pkg --skip-update
    cd $pkg
    gpg --import keys/pgp/*
    while ! updpkgsums; do :; done
    rm *.pkg.tar.zst*
    cd ..
    get-loong64-pkg $pkg --skip-update
    script -c "time local-loong64-build -- -- -A" build-log-all.log && \
        ../add-to-local /srv/local-repo/local-repo.db.tar.gz *.pkg.tar.zst
    if [ $? -ne 0 ]; then
        break
    fi
done
```

**全部构建成功后**，再将所有软件包一次性上传到正式仓库。完成后清空本地仓库：

```bash
rm -rf /srv/local-repo/*
repo-add /srv/local-repo/local-repo.db.tar.gz
```

### 6.6 注意事项

- **版本锁定问题**：如果本地仓库中有更新的包，但某个依赖锁定了旧版本，可能导致构建无效。可用 `pactree` 排查依赖关系。
- **上游 conf 更新后**：当 `devtools-loong64` 的 conf 文件更新后，需重新编辑 `local-loong64.conf` 同步上游变化。
- **`pkgrel` 批量修改**：按规范自动将 `pkgrel` 小数部分加 1：
  ```bash
  perl -i -pe 's{(^[^#]*?\bpkgrel\s*=\s*)(\d+)(?:\.(\d+))?}{$1 . $2 . "." . (defined($3) ? $3 + 1 : 1)}e' PKGBUILD
  ```

---

## 7. 标准构建命令

推荐用户使用 `script` 记录完整日志（包含 stderr 中的 `checkpkg` 输出）：

```bash
script -c 'time extra-loong64-build $(bash -c "source PKGBUILD; [[ \" \${arch[*]} \" =~ \" loong64 \" ]] || echo -- -- -A")' build-log-all.log
```

*   如果是本地仓库构建，将 `extra-loong64-build` 替换为 `local-loong64-build`。
*   参数 `-- -- -A` 用于在非 loong64 架构宿主机上强制构建 loong64 包（通过 QEMU User）。

---

## License

本 Skill 文件（`SKILL.md`）采用 **Creative Commons Attribution-ShareAlike 4.0 International (CC-BY-SA-4.0)** 发布。

完整许可证文本见 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)。
``````
