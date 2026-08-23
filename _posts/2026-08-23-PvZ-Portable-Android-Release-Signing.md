---
layout:       post
title:        PvZ-Portable：Android APK 现在可以直接覆盖安装升级
subtitle:     使用固定发布证书为 GitHub Releases 中的 APK 签名
date:         2026-08-23
author:       wszqkzqk
header-img:   img/games/pvz-portable/bg-pvz-portable.webp
catalog:      true
tags:         Android CI 开源软件 游戏移植 开源游戏 PvZ-Portable
---

## Android 版本的覆盖安装支持

此前发布的 Android APK 使用 debug 签名，而且每次 CI 构建生成的签名证书都不同。Android 无法把这些 APK 识别为同一应用的连续版本，升级时只能先导出存档，再卸载旧版本。卸载还会删除应用目录中已经导入的游戏资源，重新安装后需要再次导入。

从 [v0.2.0](https://github.com/wszqkzqk/PvZ-Portable/releases/tag/0.2.0) 开始，PvZ-Portable 的 CI 使用固定的发布证书为 APK 签名。之后发布的版本可以直接覆盖安装，应用中的游戏资源和存档也会保留。相关改动见 [#384](https://github.com/wszqkzqk/PvZ-Portable/pull/384)。

下面先说明新旧版本的升级方法，再介绍 GitHub Actions 和 Gradle 中的签名配置。

## 用户指南

### 从 v0.2.0 或更高版本升级

从 [GitHub Releases](https://github.com/wszqkzqk/PvZ-Portable/releases) 下载新版 APK 并直接安装即可。Android 会将其识别为已有应用的更新，原来的游戏资源和存档都会保留。

### 从 v0.1.27 或更早版本迁移

旧版本使用另一份签名证书，无法直接覆盖安装 v0.2.0 或更新版本。迁移时需要执行以下步骤：

1. 长按桌面图标，通过 `Manage Data` 打开数据管理界面，使用 `Export Save Data` 导出存档。
2. 确认正版游戏资源仍有可用副本，包括 `main.pak` 和 `properties/`，或包含这两项内容的 ZIP 文件。
3. 卸载旧版本，再安装新版 APK。
4. 首次打开新版时重新导入游戏资源。
5. 再次进入 `Manage Data`，通过 `Import Save ZIP` 或 `Import Save Folder` 导入存档。

应用清单声明了 `hasFragileUserData`。部分 Android 10 及以上的系统会在卸载时询问是否保留应用数据，选择保留后可能不需要重新导入。但并非所有系统都会显示这个选项，例如笔者测试发现小米 HyperOS 就没有提供。因此迁移前仍应主动导出存档，并准备好重新导入游戏资源。

迁移到 v0.2.0 或更高版本后，后续升级可以直接覆盖安装。

### 自行构建的注意事项

官方 Release 使用项目的发布证书，本地构建默认使用开发者机器上的 debug 证书。两者签名不同，不能互相覆盖安装。在官方版本和自行构建版本之间切换时，也需要先导出存档并准备好游戏资源，再卸载原版本。

## 为什么之前 debug 签名不能覆盖安装

Android 使用签名证书确认 APK 的发布者。安装更新时，系统需要确认新旧 APK 具有相同的签名身份，否则会拒绝安装，常见错误为 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`。这项检查可以防止其他发布者使用相同的应用 ID 覆盖现有应用并读取其私有数据。

使用 debug 证书并不妨碍覆盖安装，只要每次构建使用同一份 debug keystore 即可。本地开发时，`~/.android/debug.keystore` 通常会一直保留，所以连续构建的 APK 具有相同签名。GitHub Actions 使用临时运行器，每次任务开始时都没有这份文件，Android Gradle 插件会重新生成 debug keystore。此前各个 Release APK 因此使用了不同的证书。

现在，CI 会在构建时载入同一份发布密钥库，Gradle 再用其中的证书为 Release APK 签名。

## 实现：CI 注入的固定发布证书

发布密钥库经过 Base64 编码后保存在 GitHub Actions Secrets 中。构建时，工作流将其还原为临时文件；Gradle 检测到相应环境变量后使用发布签名，否则继续使用 debug 签名。

### 生成密钥库并配置 Secrets

用 JDK 自带的 `keytool` 生成一份有效期足够长的 RSA 密钥库：

```bash
keytool -genkeypair -v \
  -keystore pvzp-release.keystore \
  -alias pvzp \
  -keyalg RSA -keysize 2048 \
  -validity 36525
```

这里将证书有效期设为 100 年，避免短期内处理证书到期问题。`-alias` 的值需要与后面配置的 `PVZP_KEY_ALIAS` 一致。发布私钥和密码还应另行离线备份；如果私钥丢失，后续版本将无法继续使用相同的签名身份。

然后将密钥库文件做 base64 编码，存入仓库的 Actions Secrets：

```bash
base64 -w 0 pvzp-release.keystore > pvzp-release.keystore.b64
```

GNU coreutils 的 `base64` 默认会换行，`-w 0` 用于输出单行文本。macOS 自带的 `base64` 默认不换行，可以直接使用。仓库需要配置四个 Secret：

| Secret | 内容 |
| :--- | :--- |
| `PVZP_KEYSTORE_BASE64` | 密钥库文件的 base64 编码 |
| `PVZP_KEYSTORE_PASSWORD` | 密钥库密码 |
| `PVZP_KEY_ALIAS` | 密钥别名（如 `pvzp`） |
| `PVZP_KEY_PASSWORD` | 密钥密码 |

### CI 中的解码与注入

在构建 APK 之前新增一个步骤，把 base64 编码的密钥库解码为临时文件，并将其路径写入 `GITHUB_ENV`：

```yaml
- name: Decode release keystore
  env:
    PVZP_KEYSTORE_BASE64: ${{ secrets.PVZP_KEYSTORE_BASE64 }}
    PVZP_KEYSTORE_PASSWORD: ${{ secrets.PVZP_KEYSTORE_PASSWORD }}
    PVZP_KEY_ALIAS: ${{ secrets.PVZP_KEY_ALIAS }}
    PVZP_KEY_PASSWORD: ${{ secrets.PVZP_KEY_PASSWORD }}
  run: |
    # Secrets are empty on fork PRs; the build then falls back to debug signing.
    if [ -n "$PVZP_KEYSTORE_BASE64" ] && [ -n "$PVZP_KEYSTORE_PASSWORD" ] && [ -n "$PVZP_KEY_ALIAS" ] && [ -n "$PVZP_KEY_PASSWORD" ]; then
      echo "$PVZP_KEYSTORE_BASE64" | base64 -d > "$RUNNER_TEMP/pvzp-release.keystore"
      echo "PVZP_KEYSTORE_FILE=$RUNNER_TEMP/pvzp-release.keystore" >> "$GITHUB_ENV"
    fi

- name: Build APK with Gradle
  env:
    PVZP_KEYSTORE_PASSWORD: ${{ secrets.PVZP_KEYSTORE_PASSWORD }}
    PVZP_KEY_ALIAS: ${{ secrets.PVZP_KEY_ALIAS }}
    PVZP_KEY_PASSWORD: ${{ secrets.PVZP_KEY_PASSWORD }}
  run: |
    cd android
    echo "sdk.dir=$ANDROID_HOME" > local.properties

    # Use gradle wrapper; package pre-built native libraries into a release APK
    gradle wrapper
    ./gradlew assembleRelease -PusePrebuiltLibs=true --no-daemon
```

密钥库被解码到 `$RUNNER_TEMP`，不放进检出的源码目录。后续 artifact 步骤只上传 `dist/`，不会包含这个文件。四个 Secret 全部存在时，工作流才会设置 `PVZP_KEYSTORE_FILE`；本地构建和来自 fork 的 Pull Request 无法读取仓库 Secrets，因此会继续使用 debug 签名。

当前工作流在任意 Secret 缺失时都会回退到 debug 签名，tag 构建也不例外。发布前必须确认 Secrets 配置完整，并检查 APK 的签名证书。更严格的做法是在 tag 构建中加入检查，只要发布签名不可用就直接终止任务，避免把 debug 签名的 APK 上传到 Release。

### Gradle 中的条件签名配置

`android/app/build.gradle` 中新增一个 `release` 签名配置，仅当环境变量存在时才填入密钥库信息；`release` 构建类型则按环境变量在两套签名配置之间选择：

```groovy
signingConfigs {
    release {
        // Keystore is injected via env vars by CI; absent (e.g. local builds) falls back to debug signing.
        def storeFilePath = System.getenv('PVZP_KEYSTORE_FILE')
        if (storeFilePath) {
            storeFile file(storeFilePath)
            storePassword System.getenv('PVZP_KEYSTORE_PASSWORD')
            keyAlias System.getenv('PVZP_KEY_ALIAS')
            keyPassword System.getenv('PVZP_KEY_PASSWORD')
        }
    }
}

buildTypes {
    release {
        minifyEnabled false
        signingConfig System.getenv('PVZP_KEYSTORE_FILE') ? signingConfigs.release : signingConfigs.debug
    }
}
```

密钥库路径、密码和别名都从环境变量读取，仓库不保存私钥或密码。`android/.gitignore` 也加入了 `*.keystore`，降低本地密钥库被误提交的可能。

### versionCode 的自动递增

Android 的升级检查不只看签名，还会比较 `versionCode`：新安装包的值低于已安装版本时，系统会拒绝降级安装（`INSTALL_FAILED_VERSION_DOWNGRADE`）。因此固定证书只是覆盖安装的一半条件，另一半是每个新版本的 `versionCode` 都必须单调递增。手工维护这个数值难免遗忘，PvZ-Portable 选择直接从 Git 历史推导（[#385](https://github.com/wszqkzqk/PvZ-Portable/pull/385)）：

```groovy
// Version from git, mirroring archlinux/PKGBUILD's pkgver(); fall back to 0.1/1 without git or tags.
def gitVersionName = {
    try {
        // providers.exec: plain exec is rejected at configuration time by Gradle 9's configuration cache.
        def text = providers.exec {
            commandLine 'git', 'describe', '--tags', '--abbrev=12'
        }.standardOutput.asText.get().trim()
        return text.replaceFirst(/^v/, '').replace('-', '.')
    } catch (Exception ignored) {
        return '0.1'
    }
}()

def gitVersionCode = {
    try {
        def text = providers.exec {
            commandLine 'git', 'rev-list', '--count', 'HEAD'
        }.standardOutput.asText.get().trim()
        return text.toInteger()
    } catch (Exception ignored) {
        return 1
    }
}()
```

`versionName` 来自 `git describe --tags`，与 Arch Linux 打包中 `pkgver()` 的规则一致；`versionCode` 使用 `git rev-list --count HEAD`，即当前提交在历史上的提交总数。主分支的历史只增不改，发布新版本时 HEAD 必然包含旧版本的全部提交，提交数随之严格增加，`versionCode` 不需要任何手工维护就能满足 Android 的递增要求。无法访问 Git 信息时（例如直接下载源码压缩包构建），两者分别回退为 `0.1` 和 `1`。

这个提交数同时用作 iOS 的 `CFBundleVersion`，并作为 Build Num 显示在游戏内。每个提交对应的版本信息完全确定，构建也因此保持可复现。

这里还有一段插曲。最初的实现使用 Groovy 的 `exec` 在配置阶段调用 git，而 CI 会用运行器预装的 Gradle 9 重新生成 wrapper——Gradle 9 默认启用 configuration cache，禁止在配置阶段直接执行外部进程，异常被 `catch` 吞掉后，CI 构建全部静默回退到了 `0.1`/`1`。改用与 configuration cache 兼容的 `providers.exec` 后才恢复正常（[#387](https://github.com/wszqkzqk/PvZ-Portable/pull/387)）。如果带着这个问题发布，所有 Release 的 `versionCode` 都同为 1，版本间的先后关系完全丢失，系统也无法再识别和拒绝降级安装。这个例子也说明，发布前检查 APK 实际的版本号和签名证书是必要的。

### 密钥的保存与使用

Base64 只是一种文本编码，不提供加密。密钥库的保密依赖 GitHub Actions Secrets、密钥库自身的密码，以及对工作流修改权限的管理。当前配置采取了以下措施：

- 仓库 Secrets 不会提供给来自 fork 的 Pull Request，相关构建自动使用 debug 签名；
- 工作流不会输出密钥库内容或密码，GitHub 也会屏蔽日志中与 Secret 值完全匹配的内容；
- 解码后的密钥库位于临时目录，不进入源码和发布产物；
- 仓库只保存签名配置和环境变量名称，不保存密钥库与密码。

能够修改工作流并触发受信任分支构建的人，仍有机会读取或使用这些 Secrets。因此涉及签名步骤的工作流变更需要单独审查，发布私钥也应保留一份安全的离线备份。

这份证书由项目维护者自行生成，不经过应用商店的签名服务。用户从 GitHub Releases 安装 APK 时，仍需允许浏览器或文件管理器安装未知来源的应用。

## 总结

从 v0.2.0 开始，PvZ-Portable 的官方 Android 版本使用固定证书签名。已经安装 v0.2.0 或更新版本的用户，可以直接安装新版 APK，原有资源和存档会随应用更新保留。

对于通过 GitHub Releases 分发 APK 的项目，签名证书也属于需要长期保存的发布材料。CI 发布前可以使用 `apksigner verify --print-certs` 比较相邻版本的证书，并确认 `versionCode` 按预期增加。

项目地址：[github.com/wszqkzqk/PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable)。源代码采用 [LGPL-3.0-or-later](https://www.gnu.org/licenses/lgpl-3.0.html) 许可证发布。

## ⚠️ 版权与说明

《植物大战僵尸》的 IP 归 PopCap/EA 所有。

本项目只包含开源重实现的引擎代码，不包含游戏美术、音效、关卡等受版权保护的资源文件。使用本项目时需要拥有正版游戏；如尚未购买，可前往 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 购买。请从正版游戏中提取以下内容，并放入 PvZ-Portable 程序所在的目录：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 LGPL-3.0-or-later 许可证发布。
