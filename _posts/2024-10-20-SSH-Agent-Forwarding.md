---
layout:     post
title:      配置SSH Agent Forwarding
subtitle:   使用SSH Agent Forwarding在远程服务器上安全访问仓库
date:       2024-10-20
author:     wszqkzqk
header-img: img/bg-sunrise.webp
catalog:    true
tags:       系统配置 系统维护 开源软件 Linux
---

## 前言

在远程服务器上访问仓库时，我们通常会使用SSH密钥来进行认证。但是，如果我们直接将私钥拷贝到远程服务器上，就会存在私钥泄露的风险。SSH Agent Forwarding是一种解决这一问题的方法，它可以让我们在远程服务器上使用本地的SSH密钥，而不需要将私钥拷贝到远程服务器上。

## 配置SSH Agent Forwarding

在ssh访问时启用SSH Agent Forwarding所需的参数是`-A`，例如：

```bash
ssh -A user@remote
```

对于SSH客户端，可以在`~/.ssh/config`中添加以下配置：

```bash
Host remote
    HostName remote
    User user
    ForwardAgent yes
```

其中，`ForwardAgent yes`表示启用SSH Agent Forwarding。

然而，仅仅加上这一参数是不够的，我们还需要配置SSH Agent。

### Linux

在Linux系统上，我们可以使用systemd的用户单元`ssh-agent.service`来启动SSH Agent，首先我们需要在`~/.profile`中设置环境变量：

```
echo 'export SSH_AUTH_SOCK="$XDG_RUNTIME_DIR/ssh-agent.socket"' >> ~/.profile
```

然后启用`ssh-agent.service`：

```bash
systemctl --user enable ssh-agent.service
```

重新登录用户，SSH Agent就会自动启动。

如果想在SSH Agent中添加私钥，可以使用`ssh-add`命令，例如：

```bash
ssh-add ~/.ssh/id_rsa
```

如果希望在每次登录时自动添加私钥，在`~/.ssh/config`中添加：

```
AddKeysToAgent yes
```

### Windows

在Windows系统上，我们可以使用`SetService`来启动SSH Agent，在`pwsh`中以管理员身份运行：

```pwsh
Set-Service ssh-agent -StartupType Automatic
Start-Service ssh-agent
```

然后使用`ssh-add`命令添加私钥：

```pwsh
ssh-add ~/.ssh/id_rsa
```
