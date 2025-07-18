---
layout:     post
title:      利用本地仓库实现有依赖关系的软件包的顺序构建
subtitle:   Loong Arch Linux下要求同步升级的软件包的构建方法
date:       2024-09-19
author:     wszqkzqk
header-img: img/bg-sunrise.webp
catalog:    true
tags:       系统配置 系统维护 开源软件 Linux archlinux 国产硬件 虚拟化 龙芯 LoongArchLinux
---

# 前言

在软件包的构建过程中，有时候会遇到一些软件包之间有依赖关系的情况，对构建顺序存在要求，并且要求在后一个软件包构建时，能够获取前一个软件包并安装。这一过程固然可以通过手动向`makechrootpkg`传递`-I`参数来实现，但当重构大量包时较为麻烦。

本文介绍了一种利用本地仓库实现有依赖关系的软件包的顺序构建的方法。这样的方法尤其适用于需要先在本地一并打包/重构完并要求一次性上传的软件包。

# 建立本地仓库

首先，建立本地仓库目录并初始化（具体路径可以自行指定）：

```bash
sudo mkdir -p /srv/local-repo
sudo chown -R $USER:alpm /srv/local-repo
repo-add /srv/local-repo/local-repo.db.tar.gz
```

如果成功，会看到类似这样的输出：

```log
==> Creating updated database file '/srv/local-repo/local-repo.db.tar.gz'
==> WARNING: No packages remain, creating empty database.
==> WARNING: No packages remain, creating empty database.
```

# 添加软件包

如果要添加软件包到本地仓库，可以先将软件包复制到本地仓库目录，然后使用`repo-add`命令添加：

```bash
cp /path/to/package.pkg.tar.zst /srv/local-repo
cd /srv/local-repo
repo-add local-repo.db.tar.gz package.pkg.tar.zst
```

当然，为了简化这一过程，可以封装一些脚本来实现：

```
#!/bin/bash

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
  repo-add $DB_FILE "$pkg_basename"
  cd "$CURRENT_DIR"
done
```

将以上内容保存为`add-to-local`，并赋予执行权限：

```bash
chmod +x add-to-local
```

这样，只需要执行`add-to-local /srv/local-repo/local-repo.db.tar.gz /path/to/package1.pkg.tar.zst /path/to/package2.pkg.tar.zst ...`即可。

# 在构建中启用本地仓库

如果想要在devtools的构建过程中使用本地仓库，需要在`/usr/share/devtools/pacman.conf.d/`下添加一个配置文件，比如`local-loong64.conf`、`local-testing-loong64.conf`、`local-staging-loong64.conf`。建议按照一定的规则来命名，比如`local-testing-loong64.conf`的示例`local`表示本地仓库，`testing`表示基于`testing`仓库，`loong64`表示龙芯64位架构。`conf`文件可以从`/usr/share/devtools/pacman.conf.d/extra-loong64.conf`（或`extra-testing-loong64.conf`、`extra-staging-loong64.conf`）复制并编辑。

复制并编辑`local-repo`所基于的`conf`文件，在**所有**软件源的指定**之前**插入本地仓库的指定：
* **务必**保证本地仓库的指定在所有软件源的指定**之前**
* 只有这样`pacman`才会优先使用本地仓库

```conf
[local-repo]
SigLevel = Never
Server = file:///srv/local-repo
```

其中，`SigLevel = Never`表示不验证本地仓库的签名，我们在编译机上构建时对我们自己的本地仓库不便签名，也没有必要验证签名；`Server = file:///srv/local-repo`表示本地仓库的路径。

完成后，我们还需要增加`archbuild`的软链接，以便在构建时使用本地仓库：

```bash
sudo ln -s /usr/bin/archbuild /usr/bin/local-loong64-build
sudo ln -s /usr/bin/archbuild /usr/bin/local-testing-loong64-build
sudo ln -s /usr/bin/archbuild /usr/bin/local-staging-loong64-build
```

确保软链接的名称与`conf`文件的名称保持对应。以后，我们就可以使用`local-testing-loong64-build`命令基于`local-repo`构建软件包了。

# 使用本地仓库构建的流程示例

* 本示例较为简单，实际上在脚本中应该加入更多检查逻辑

假设我们有一整个包组需要构建并同时上传，首先应当获得构建顺序，使用[肥猫的`genrebuild`脚本](https://github.com/felixonmars/archlinux-futils/blob/master/genrebuild)：

```bash
./genrebuild package1 package2 package3 ...
```

然后，按顺序进行打包并添加到本地仓库。不过需要注意的是，如果列表中的包的在上游仓库的版本号在打包期间发生变化，可能会导致本地在此前后打的包版本不对应，因此需要先在构建前更新一下仓库信息，使用`get-loong64-pkg`脚本下载任意一个包即可：

```bash
get-loong64-pkg package1
```

在随后按列表顺序构建的过程中，则需要向`get-loong64-pkg`传递`--skip-update`参数，禁止脚本在按照列表构建期间更新上游仓库信息。假设我们的构建目录下存在[`add-to-local`](#添加软件包)脚本，本地仓库数据库的路径为`/srv/local-repo/local-repo.db.tar.gz`：

* Bash

```
for pkg in package1 package2 package3 ...; do
    get-loong64-pkg $pkg --skip-update
    cd $pkg
    gpg --import keys/pgp/*
    while ! updpkgsums; do
        :
    done
    rm *.pkg.tar.zst*
    cd ..
    get-loong64-pkg $pkg --skip-update
    script -c "time local-loong64-build -- -- -A" build-log-all.log && ../add-to-local /srv/local-repo/local-repo.db.tar.gz *.pkg.tar.zst
    if [ $? -ne 0 ]; then
        break
    fi
    cd ~/loongpack
done
```

* Fish

```fish
for pkg in package1 package2 package3 ...                                                                      
    get-loong64-pkg $pkg --skip-update
    cd $pkg
    gpg --import keys/pgp/*
    while ! updpkgsums
    end
    rm *.pkg.tar.zst*
    cd ..
    get-loong64-pkg $pkg --skip-update
    script -c "time local-loong64-build -- -- -A" build-log-all.log && ../add-to-local /srv/local-repo/local-repo.db.tar.gz *.pkg.tar.zst
    if test $status -ne 0
        break
    end
    cd ~/loongpack                                                                             
end
```

如果**全部**构建都顺利完成，再将**所有**的软件包**一次性**上传。（用脚本处理的注意不要把debug包直接上传了）

建议在一轮构建与上传完成后，清空本地仓库，以免下一轮构建时出现问题：

```bash
rm -rf /srv/local-repo/*
repo-add /srv/local-repo/local-repo.db.tar.gz
```

此外，当`devtools-loong64`的`conf`更新后，需要重新编辑`local-loong64.conf`/`local-testing-loong64.conf`/`local-staging-loong64.conf`文件，**同步上游的变化**。

## `pkgrel`更改命令

在某些时候如果我们需要批量或者自动修改软件包的`pkgrel`，可以参考以下命令：

```bash
perl -i -pe 's{(^[^#]*?\bpkgrel\s*=\s*)(\d+)(?:\.(\d+))?}{$1 . $2 . "." . (defined($3) ? $3 + 1 : 1)}e' PKGBUILD
```

这样可以按照本项目的维护规范，自动将`pkgrel`的小数部分加1，或者如果没有小数部分则将其设置为1。
