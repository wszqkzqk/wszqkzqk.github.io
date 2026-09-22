---
layout:       post
title:        排查 Tailscale 与其他 TUN 服务的开机冲突
subtitle:     fake-ip DNS 劫持与一条绕过 TUN 的拨号路径
header-img:   img/bg-sunrise.webp
date:         2026-09-22
author:       wszqkzqk
catalog:      true
tags:         Linux 网络 DNS systemd Tailscale
---

## 引言

笔者本机长期同时运行两个网络组件：一个是 Tailscale，负责把几台设备组成虚拟内网；另一个是以 TUN 模式工作的分流服务，把系统的出站流量统一接管过来，按规则分流（下文就称它"分流服务"）。两者共存了很长时间，一直相安无事。问题出现在把分流服务注册为 systemd 服务、设置开机自启之后——每次重启，Tailscale 都起不来：

```text
$ tailscale status
# Health check:
#     - You are logged out. The last login error was: fetch control key: Get "https://controlplane.tailscale.com/key?v=142": failed to resolve "controlplane.tailscale.com": no DNS fallback candidates remain for "controlplane.tailscale.com"

unexpected state: NoState
```

临时解法并不复杂：停掉分流服务，`sudo tailscale login` 重新登录，再把它拉起来，之后一切正常。但每次开机都要手动来一遍，显然不是办法。整个排查过程绕了两个弯，最后确认的原因和最初的判断完全不同，值得记录下来。

报错里的几个概念先交代一下。`fetch control key` 是 tailscaled 与协调服务器（coordination server）握手的第一步；`no DNS fallback candidates remain` 表示它内置的 DNS 回退机制已经用尽；`NoState` 则是 ipn 状态机的内存状态——state 文件里的登录凭据其实还在，并不是账号真的被登出了。

## 第一个假设：启动顺序竞争

最直接的怀疑是开机竞态。查看故障发生时的 journal：

```text
tailscaled[810]: control: bootstrapDNS("derp1i.tailscale.com", "199.38.181.103") for "controlplane.tailscale.com" error: ... connect: network is unreachable
```

这里涉及 tailscaled 的一套容错设计：系统 DNS 解析失败时，它会用一批硬编码的 DERP 服务器 IP 直接发起 HTTPS 请求来解析协调服务器的域名，不依赖任何 DNS 服务器，本是最后的兜底。而日志显示，tailscaled 启动时系统里唯一的默认路由是分流服务刚建好的 TUN 设备，物理网卡 wlan0 几秒之后才拿到地址——bootstrap 的直连全部撞上 `network is unreachable`。

时序上看证据是完整的：分流服务的 TUN 开了 `auto-route`，启动即接管路由；tailscaled 只排在 `network-pre.target` 之后，比网络就绪还要早。于是笔者给分流服务加了一个 systemd drop-in，让它等网络就绪：

```ini
[Unit]
Wants=network-online.target
After=network-online.target
```

改完重启，分流服务确实等到网络可用之后才启动了。但这个改动并没有修好 Tailscale，只是让故障换了一种形式出现。这是后话。

## 插曲：两分钟启动延迟从何而来

加了 drop-in 之后还冒出一个谜之现象：分流服务看似"不自启"了，每次都要手动拉一把。实际上它是被 `network-online.target` 挡住了，而这个 target 又被另一个系统服务拖住：

```text
systemd-networkd-wait-online[17670]: Timeout occurred while waiting for network connectivity.
systemd[1]: systemd-networkd-wait-online.service: Failed with result 'exit-code'.
```

`systemd-networkd-wait-online` 的职责是等待 systemd-networkd 管理的接口就绪。用 `networkctl list` 一看，本机所有接口对 networkd 全是 `unmanaged`：网络完全由 NetworkManager 管理，networkd 一个接口都没管。于是这个等待永远等不到结果，每次开机空转约 120 秒后超时失败，把所有排在 `network-online.target` 之后的服务都拖慢两分钟。

解决办法是禁用它，只保留 networkd 本体：

```bash
sudo systemctl disable systemd-networkd-wait-online.service
```

networkd 本体要留着，因为本机以后还要跑 nspawn 容器，容器的 `ve-*` 虚拟网卡由 networkd 在运行时配置，这与 wait-online 无关。这是本次排查中一个真正有价值的附带发现：此后 `network-online.target` 只需等 NetworkManager 的三四秒，不再有两分钟空窗。

## 第二次失败：注册请求持续超时

排序修好、延迟消除之后再次重启，分流服务开机自启正常了，但 Tailscale 依然失败，而且失败模式变了。不再是开机瞬间的 `network is unreachable`，而是持续不断的超时：

```text
tailscaled[39574]: control: doLogin(regen=false, hasUrl=false)
tailscaled[39574]: Received error: register request: Post "https://controlplane.tailscale.com/machine/register": connection attempts aborted by context: context deadline exceeded
```

tailscaled 每 25~30 秒重试一次，十几分钟过去全部超时。此时 wlan0 早已上线，tailscale0 接口存在，tailscaled 自己的策略路由规则（fwmark `0x80000` 走 main 表）也都就位。网络明明是通的，协调服务器却怎么也连不上。到这一步，"启动顺序"假设基本破产。

## 流量根本没有进 TUN

配置里其实早就给 Tailscale 加过直连规则：

```text
- PROCESS-NAME,tailscaled,DIRECT
- PROCESS-NAME,tailscale,DIRECT
- DOMAIN-SUFFIX,tailscale.com,DIRECT
- DOMAIN-SUFFIX,tailscale.io,DIRECT
```

如果流量进了分流服务的 TUN 却被错误分流，这些规则本该兜住。排查时翻了分流服务的运行日志，结果非常关键：日志里没有任何一条与 tailscaled 相关的连接记录。也就是说，tailscaled 的流量压根没有进入 TUN，"分流规则配错了"这条线索整个不成立。

顺带说明这两条规则为什么在 TUN 模式下本来就靠不住。`PROCESS-NAME` 依赖连接的进程信息，而 TUN 是三层设备，数据包从协议栈上来时已经脱离了原始进程上下文，这类规则只对 mixed-port 的 SOCKS/HTTP 入站有效。`DOMAIN-SUFFIX` 需要域名信息，来源只有两种：经过分流服务自身 DNS 的查询记录，或者 sniffer 嗅探 TLS SNI。本机没有开 sniffer，tailscaled 又大量走"硬编码 IP 加裸 IP 直连"的路径，域名规则同样无从命中。

## 根本原因：fake-ip 遇上绕过 TUN 的拨号

流量没进 TUN，又连不上协调服务器，包到底发到哪去了？先看系统把协调服务器的域名解析成了什么：

```text
$ getent ahosts controlplane.tailscale.com
198.18.0.6      STREAM controlplane.tailscale.com
```

`198.18.0.6`，这是分流服务返回的 fake-ip。相关配置如下：

```yaml
tun:
  stack: gvisor
  device: tun0
  auto-route: true
  dns-hijack:
    - any:53
  enable: true
dns:
  enable: true
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
```

`dns-hijack: any:53` 劫持发往任意地址 53 端口的 DNS 查询；fake-ip 模式不返回真实地址，而是返回 `198.18.0.0/16` 段内的一个假地址，同时记录假地址到域名的映射。普通应用拿到假地址后照常发起连接，由于 socket 没有绑定源地址，做路由决策时源还是 `0.0.0.0`，命中分流服务的策略路由规则（`from 0.0.0.0 iif lo lookup 2022`）进入 TUN；分流服务收到后按映射还原出域名，再交给分流规则处理。整个闭环对应用是透明的。

tailscaled 的行为不同。它的出站连接绑定出接口，并带有自己的 fwmark，命中优先级更高的策略路由（`fwmark 0x80000 lookup main`），直接走物理网卡。于是 `198.18.0.6` 这个假地址被原样发向真实网络——而 `198.18.0.0/15` 是 RFC 2544 保留的基准测试网段，公网上没有路由，包发出去就是黑洞，最终表现为 register request 的 `context deadline exceeded`。

为确认这个推断，做了三组对照实验：

```text
# 普通进程：流量进 TUN，fake-ip 被映射回域名
$ curl -m 15 -o /dev/null -w "%{http_code}\n" "https://controlplane.tailscale.com/key?v=142"
200            # 0.94 秒

# 绑定物理网卡，使用系统解析结果：模拟 tailscaled 的路径
$ curl -m 8 --interface wlan0 -o /dev/null -w "%{http_code}\n" "https://controlplane.tailscale.com/key?v=142"
curl: (28) Connection timed out    # 与故障现象一致

# 绑定物理网卡，但指定真实 IP
$ curl -m 8 --interface wlan0 --resolve controlplane.tailscale.com:443:192.200.0.105 \
    -o /dev/null -w "%{http_code}\n" "https://controlplane.tailscale.com/key?v=142"
200            # 0.56 秒
```

直连协调服务器本身完全畅通，唯一的问题就是 tailscaled 拿到的是 fake-ip。之前"停分流服务再 login"的土办法之所以有效，也是因为劫持消失后，tailscaled 改走 bootstrapDNS（硬编码 IP 的 HTTPS 查询）拿到真实地址，直连成功。至于这台机器以前为什么没事：以前分流服务启动得晚，tailscaled 早已完成登录并把真实地址缓存在进程内；改成开机服务后两者几乎同时启动，时序变化把问题暴露了出来。

## 修复

既然病根是特定域名不该返回 fake-ip，分流服务正好有对应的配置项。在 `dns` 段加入 `fake-ip-filter`：

```yaml
dns:
  enable: true
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  fake-ip-filter:
    - +.tailscale.com
    - +.tailscale.io
    - +.ts.net
```

列表中的域名会跳过 fake-ip，直接返回真实解析结果。改完配置后，重启分流服务和 tailscaled。注意 tailscaled 必须重启：它进程内的 DNS 缓存还留着之前解析到的假地址，光改配置清不掉。重启后状态机顺利走到 `Running`，`tailscale status` 恢复正常。此后无论怎样重启，Tailscale 都能在无人干预的情况下自行登录。

## 复盘

这次排查有几次判断事后看是无效的，值得清点：

- **systemd 排序 drop-in**：针对的是"开机瞬间网络未就绪"这个表象。根因修复后，笔者用 `systemctl revert` 撤掉了它。tailscaled 本身有 25~30 秒的登录重试，即使开机首轮失败也能自愈，排序不再是必需品。
- **`PROCESS-NAME` 与 `DOMAIN-SUFFIX` 直连规则**：方向就是错的。前者在 TUN 模式下原理上无法命中，后者依赖本不存在的域名信息。
- **"停分流服务再 login"**：绕开问题而非修复问题，还掩盖了真正的故障点。
- **真正有价值的附带修复**：禁用 `systemd-networkd-wait-online.service`，消除了一个与本故障无关、但确实存在的两分钟启动延迟。

方法论上也有两点收获。排查 TUN 模式的流量接管问题，第一步应该看接管方的日志里有没有这条流量——没进 TUN这一条证据，直接否决了整排关于分流规则的假设。另外，当"只有某一个进程异常、其他应用都正常"时，可以用 `curl --interface` 绑定接口、`--resolve` 指定地址来模拟那个进程的网络路径。把差异精确复现出来，根因往往就藏在这个差异里。
