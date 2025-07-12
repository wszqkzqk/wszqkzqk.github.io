---
layout:     post
title:      利用LLM辅助总结Arch Linux for Loong64开发进展报告
subtitle:   使用LLM轻松总结开发进度
date:       2025-07-07
author:     wszqkzqk
header-img: img/llm/ai-bg-lossless.webp
catalog:    true
tags:       AI LLM 开源软件 archlinux LoongArchLinux
---

## 前言

目前Arch Linux for Loong64一般会在龙架构双周会上向开发者交流开发进展，并且在龙芯社区合作部的“龙芯爱好者社区”官方的BiliBili账号及微信公众号上公开。但是笔者考虑到这样的形式下每一期的内容较为分散，不变集中对比查证，因此笔者也计划在[LoongBBS](https://www.loongbbs.cn/)中发布帖子，集中记录每一期的开发进展。

由于BBS不仅面向开发者，也面向普通用户，因此信息侧重有所区别。同时，BBS没有篇幅和时间限制，可以更详细地记录的开发进展。

## 环境

其实只需要将有关信息提取出来并传递给LLM处理即可，并不一定需要专门的工具。但为了方便，笔者在这里推荐一套简洁有效的方法和参考提示词。

### 安装与准备

#### 软件包升级情况获取准备

现在推荐使用笔者编写的脚本来获取软件包升级情况（环境要求与[devtools-loong64](https://aur.archlinux.org/packages/devtools-loong64)完全相同，不要求架构）：

```python
#!/usr/bin/env python3

import argparse
import pyalpm
import urllib.request
import shutil
from typing import Optional
import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib # type: ignore
import os
import sys
from datetime import datetime, timedelta

CACHE_DIR: str = os.path.join(GLib.get_user_cache_dir(), "devtools-loong64")
LOONG64_REPOS: tuple = ("core", "extra")
LOONG64_DB_PATH: str = os.path.join(CACHE_DIR, "repo-db", "loong64")
DEFAULT_MIRROR: str = "https://loongarchlinux.lcpu.dev/loongarch/archlinux"

def download_file(source: str, dest: str) -> None:
    """
    Download a file from a given URL to a local destination.

    Args:
        source (str): The URL of the file to download
        dest (str): The local path where the file should be saved

    Raises:
        Exception: If the download fails for any reason
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    repo_path = os.path.dirname(dest)
    os.makedirs(repo_path, exist_ok=True)

    try:
        print(f"Downloading {source} to {dest}")
        req = urllib.request.Request(source, headers=headers)
        with urllib.request.urlopen(req) as response, open(dest, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
    except Exception as e:
        print(f"Error downloading file: {e}", file=sys.stderr)
        raise

def update_loong64_repos(mirror_loong64: str) -> None:
    """
    Update the local loong64 repository databases from a specified mirror.

    Args:
        mirror_loong64 (str): The base URL of the loong64 package mirror
    """
    print("Updating loong64 repositories...")
    for repo in LOONG64_REPOS:
        db_url = f"{mirror_loong64}/{repo}/os/loong64/{repo}.db"
        db_path = os.path.join(LOONG64_DB_PATH, "sync", f"{repo}.db")
        try:
            download_file(db_url, db_path)
        except Exception:
            print(f"Failed to download {repo}.db, skipping.", file=sys.stderr)
            continue
    print("Loong64 repositories updated.")

def load_repo(dir_path: str, repo: str) -> Optional[pyalpm.DB]:
    """
    Load a package repository database.

    Args:
        dir_path (str): The directory path where the repository database is located
        repo (str): The name of the repository to load

    Returns:
        Optional[pyalpm.DB]: The loaded repository database, or None if loading fails
    """
    handle = pyalpm.Handle("/", dir_path)
    try:
        db = handle.register_syncdb(repo, 0)
        return db
    except pyalpm.error as e:
        print(f"Failed to load repo {dir_path}/{repo}: {e}", file=sys.stderr)
        return None

def main() -> None:
    """
    Main function to query package information.
    """
    parser = argparse.ArgumentParser(
        description="Query package information from LoongArch repositories.",
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument(
        '-S', '--sync',
        action='store_true',
        help='Download and update the loong64 repository databases.'
    )
    parser.add_argument(
        '-d', '--days',
        type=int,
        default=7,
        help='List packages updated in the last n days (default: %(default)s).'
    )
    parser.add_argument(
        '-m', '--mirror',
        default=DEFAULT_MIRROR,
        help='Mirror URL for LoongArch repository database (default: %(default)s)',
        metavar='URL'
    )

    args = parser.parse_args()

    if args.sync:
        update_loong64_repos(args.mirror)

    repos_to_load = LOONG64_REPOS
    databases = []
    for repo_name in repos_to_load:
        db_path = os.path.join(LOONG64_DB_PATH, "sync", f"{repo_name}.db")
        if not os.path.exists(db_path):
            print(f"Database for '{repo_name}' not found. Please run with -S to download.", file=sys.stderr)
            continue
        db = load_repo(LOONG64_DB_PATH, repo_name)
        if db:
            databases.append(db)

    if not databases:
        print("No databases loaded. Exiting.", file=sys.stderr)
        sys.exit(1)

    print(f"\nPackages updated in the last {args.days} days:")
    print("-" * 75)
    print(f"{'Package':<30} {'Version':<25} {'Build Date':<20}")
    print("-" * 75)

    cutoff_date = datetime.now() - timedelta(days=args.days)
    
    updated_packages = []

    for db in databases:
        for pkg in db.pkgcache:
            build_date = datetime.fromtimestamp(pkg.builddate)
            if build_date > cutoff_date:
                updated_packages.append(pkg)

    updated_packages.sort(key=lambda p: p.builddate)

    for pkg in updated_packages:
        build_date_str = datetime.fromtimestamp(pkg.builddate).strftime('%Y-%m-%d %H:%M')
        print(f"{pkg.name:<30} {pkg.version:<25} {build_date_str:<20}")

if __name__ == "__main__":
    main()
```

也可以通过`wget`直接下载：

```bash
wget https://raw.githubusercontent.com/wszqkzqk/loongarchlinux-scriptlet/refs/heads/master/query-pkgs.py
chmod +x query-pkgs.py
```

这个脚本可以直接运行，获取最近一段时间内的软件包升级情况。你可以通过以下命令运行：

```bash
python3 query-pkgs.py -S -d 14
```

当然，在**Arch Linux for Loong64环境或者基于QEMU User的systemd-nspawn等透明容器环境**中，软件包升级情况可以直接利用`expac`工具来获取。`expac`是一个用于格式化Arch Linux软件包数据库的工具，可以通过以下命令安装：

```bash
sudo pacman -S expac
```

#### 软件包修复变动获取准备

软件包修复变动可以从[Arch Linux for Loong64的补丁集仓库](https://github.com/lcpu-club/loongarch-packages)获取。如果是使用过`devtools-loong64`的环境，在`$XDG_CACHE_HOME/devtools-loong64`（一般是`~/.cache/devtools-loong64`）目录下即有`loongarch-packages`补丁集仓库。如果没有使用过`devtools-loong64`，也可以自己克隆到其他目录下：

```bash
git clone https://github.com/lcpu-club/loongarch-packages.git
```

如果已经存在`loongarch-packages`仓库，记得**更新到最新**！记得**更新到最新**！记得**更新到最新**！

此外，笔者建议安装`aichat`，这是一个用Rust编写的命令行AI聊天工具，支持多种LLM模型。无论是x86_64的官方的Arch Linux还是Arch Linux for Loong64，都可以直接使用`pacman`安装：

```bash
sudo pacman -S aichat
```

### 获取信息

我们至少需要将这一周期内的补丁集的变动情况信息和软件包升级信息提供给LLM。对于补丁集的变动情况，可以通过以下命令获取：

```bash
git -C ~/.cache/devtools-loong64/loongarch-packages log --since="2 weeks ago" --stat
```

对于这段时间内的软件包版本升级信息，可以通过以下命令获取。使用笔者的脚本：

```bash
python3 ~/query-pkgs.py -S -d 14
```

使用`expac`：

```bash
expac -S "%b %-30n %v" --timefmt=%s | sort | awk -v cutoff=$(date -d '2 weeks ago' +%s) '$1 > cutoff'
```

可以自行将这些信息整理并提交给LLM。如果按照笔者的建议安装了`aichat`，则可以大大简化，直接运行`aichat`并在其中一步操作即可将上下文和提示词一次性便捷地传递给LLM。

* 使用笔者的脚本获取软件包升级信息
  ```
  .file `git -C ~/.cache/devtools-loong64/loongarch-packages/ log --since="2 weeks ago" --stat` `python3 ~/query-pkgs.py -S -d 14` -- 假如你是Arch Linux for Loong64社区（由北京大学学生Linux俱乐部维护，仓库地址为https://github.com/lcpu-club/loongarch-packages）的维护者，你需要向其他龙架构的开发者以及Arch Linux for Loong64的用户汇报最近两周的Loong Arch Linux发行版的开发信息。请你从git仓库的提交记录中分析，筛选并详细总结出对其他开发者和我们的用户有参考意义，包括对其他发行版和上游开发者（指参与龙架构相关开发的上游开发者）的维护有潜在帮助的内容。切勿遗漏重要、有价值的信息；请用括号标注出修复的贡献者，例如(by wszqkzqk)这种形式；请尽量附上相关提交的链接（如果有对应PR，优先放PR链接而不是冗长的commit链接）和向上游贡献内容的链接供参考。另外，根据近期软件包的更新汇总，请你指出值得用户关注的重要升级
  ```
* 使用`expac`
  ```
  .file `git -C ~/.cache/devtools-loong64/loongarch-packages/ log --since="2 weeks ago" --stat` `expac -S "%b %-30n %v" --timefmt=%s | sort | awk -v cutoff=$(date -d '2 weeks ago' +%s) '$1 > cutoff'` -- 假如你是Arch Linux for Loong64社区（由北京大学学生Linux俱乐部维护，仓库地址为https://github.com/lcpu-club/loongarch-packages）的维护者，你需要向其他龙架构的开发者以及Arch Linux for Loong64的用户汇报最近两周的Loong Arch Linux发行版的开发信息。请你从git仓库的提交记录中分析，筛选并详细总结出对其他开发者和我们的用户有参考意义，包括对其他发行版和上游开发者（指参与龙架构相关开发的上游开发者）的维护有潜在帮助的内容。切勿遗漏重要、有价值的信息；请用括号标注出修复的贡献者，例如(by wszqkzqk)这种形式；请尽量附上相关提交的链接（如果有对应PR，优先放PR链接而不是冗长的commit链接）和向上游贡献内容的链接供参考。另外，根据近期软件包的更新汇总，请你指出值得用户关注的重要升级
  ```

LLM会根据提供的信息和提示词，生成一份详细的开发进展报告。

## 结果

以下是LLM生成的报告示例，使用的模型是DeepSeek R1 0528，基于2025.07.06的状态：

```markdown
### Arch Linux for Loong64 社区开发动态（最近两周总结）  
**仓库地址：** [lcpu-club/loongarch-packages](https://github.com/lcpu-club/loongarch-packages)  

---

### 一、重要补丁更新与修复  
#### 1. **OCaml 生态支持优化**  
- **OCaml 5.3.0 机器码支持**：通过反向移植上游 PR [#11974](https://github.com/ocaml/ocaml/pull/11974)，为 LoongArch 启用机器码编译支持，修复了依赖 OCaml 的多个软件包（如 `libnbd`, `brltty`）的功能问题。  
  - 相关包更新：`ocaml`、`ocaml-findlib`、`libnbd`、`brltty`。  
  - 贡献者：**wszqkzqk** ([#627](https://github.com/lcpu-club/loongarch-packages/pull/627), [#628](https://github.com/lcpu-club/loongarch-packages/pull/628), [#629](https://github.com/lcpu-club/loongarch-packages/pull/629), [#632](https://github.com/lcpu-club/loongarch-packages/pull/632))。  
  > **对其他发行版的帮助**：此补丁解决了 OCaml 在 LoongArch 上的长期兼容性问题，可被其他发行版参考。

#### 2. **内核驱动配置更新**  
- 所有内核分支（`linux`、`linux-lts`、`linux-zen`、`linux-hardened`）均启用 **Intel Xe 显卡驱动**：通过 `CONFIG_DRM_XE_FORCE_PROBE="*"` 默认启用 Intel 新显卡驱动，改善显卡兼容性。  
  - 贡献者：**wszqkzqk** ([#623](https://github.com/lcpu-club/loongarch-packages/pull/623), [#624](https://github.com/lcpu-club/loongarch-packages/pull/624), [#625](https://github.com/lcpu-club/loongarch-packages/pull/625), [#626](https://github.com/lcpu-club/loongarch-packages/pull/626))。  

#### 3. **Firefox 临时修复**  
- **Firefox Developer Edition**：添加针对 `Assembler-loong64.h` 的临时补丁，解决汇编代码兼容性问题。  
  - 贡献者：**wszqkzqk** ([#634](https://github.com/lcpu-club/loongarch-packages/pull/634))。  

#### 4. **测试套件适应性调整**  
- **Meson**：优化测试流程，允许测试失败时继续执行，并过滤不支持依赖（如 CUDA、Mono）。  
  - 贡献者：**wszqkzqk** ([#621](https://github.com/lcpu-club/loongarch-packages/pull/621))。  
- **Xwayland-satellite**：跳过 `wayland_then_x11_clipboard_owner` 测试（在 systemd-nspawn 容器中失败）。  
  - 贡献者：**wszqkzqk** ([#633](https://github.com/lcpu-club/loongarch-packages/pull/633))。  

#### 5. **QEMU 构建修复**  
- 移除 `rutabaga-gfx` 相关组件（因缺少 `rutabaga-ffi` 依赖），解决构建失败问题。  
  - 贡献者：**wszqkzqk** ([#622](https://github.com/lcpu-club/loongarch-packages/pull/622))。  

---

### 二、上游修复同步（补丁移除）  
以下软件包因上游修复问题，移除了 LoongArch 专用补丁：  
1. `autotiling-rs`：上游更新 `Cargo.lock`（[#635](https://github.com/lcpu-club/loongarch-packages/pull/635), **wszqkzqk**）。  
2. `termusic`、`aarch64-linux-gnu-binutils`、`loki`：上游修复核心问题（**Pluto Yang**）。  
> **对上游的反馈**：此类修复可提交至上游，帮助减少架构特定补丁。  

---

### 三、用户重点关注升级  
#### 关键软件包更新：  
| 软件包               | 新版本       | 说明                          |
|----------------------|-------------|------------------------------|
| **Firefox**          | `140.0.2-1` | 重要安全更新                  |
| **Firefox Dev Ed**   | `141.0b4-1` | 开发者频道更新                |
| **Mesa**             | `25.1.5-1.2`| 图形驱动优化（含 Vulkan 组件）|
| **OCaml**            | `5.3.0-1.1` | 支持机器码编译                |
| **QEMU**             | `10.0.0-7`  | 修复虚拟化功能                |
| **Systemd**          | `257.7-1`   | 核心服务管理更新              |
| **Rust**             | `1.88.0-1`  | 编译器工具链升级              |
| **Python**           | `3.13.5-1`  | 最新 Python 稳定版            |

#### 桌面环境更新：  
- **KDE Plasma 6.4.2**：全系列组件更新（`kwin`、`plasma-desktop` 等）。  
- **GNOME 48.3**：`gnome-shell`、`mutter`、`nautilus` 等升级。  

---

### 四、完整提交记录  
- 所有提交详见仓库 [Commit History](https://github.com/lcpu-club/loongarch-packages/commits/main)。  
- 软件包更新列表可通过 `expac` 命令查询（见原始数据）。  

---

### 五、后续计划  
1. 推进 OCaml 补丁向上游合并。  
2. 优化 Firefox 的 LoongArch 汇编代码支持。  
3. 简化内核补丁管理，减少向下游移植需求。  

**感谢所有贡献者！**  
维护者团队：@wszqkzqk, @Pluto Yang 等。
```

我们可以看到，LLM生成的报告内容详细且结构清晰，涵盖了补丁更新、上游修复、用户关注的升级等多个方面。这样的报告不仅便于开发者了解当前的开发进展，也能帮助用户掌握最新的软件包更新情况。我们只需要稍微检查和调整一下格式和内容，就可以直接发布到LoongBBS上。

## 总结

使用LLM来辅助总结Arch Linux for Loong64的开发进展报告，可以大大简化信息整理和报告撰写的工作。通过提供必要的信息和清晰的提示词，LLM能够生成结构化且易于理解的报告内容。这种方法不仅提高了工作效率，也确保了信息的准确性和完整性。
