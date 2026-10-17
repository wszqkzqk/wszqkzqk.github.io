---
layout:       post
title:        在 systemd-nspawn 容器里运行 Waydroid
subtitle:     实现在 Arch Linux 下嵌套 systemd-nspawn 运行 Android 容器
header-img:   img/android/lineage/lineage-bg.webp
date:         2026-10-17
author:       wszqkzqk
catalog:      true
tags:         Linux Android Waydroid systemd-nspawn LXC 容器
---

## 引言

笔者有一块移动固态硬盘，里面的 Btrfs 中装着一个完整的 Arch Linux。这个系统有三种使用方式，分别是直接物理启动、作为虚拟机启动，以及在已经运行的宿主系统上用 `systemd-nspawn` 把它当作容器拉起来。

前两种方式下 Waydroid 都能正常工作，唯独在 nspawn 容器里起不来。会话一开始，里面的 Android 容器不到一秒就退出，而且不留任何日志。这次笔者把它彻底解决了，最终得到一条对宿主零残留的启动命令，镜像本身不做任何改动，物理启动和虚拟机启动都不受影响。

[![#~/img/android/waydroid/waydroid-in-systemd-nspawn-container.webp](/img/android/waydroid/waydroid-in-systemd-nspawn-container.webp)](/img/android/waydroid/waydroid-in-systemd-nspawn-container.webp)

图中 Android 桌面来自 nspawn 容器里运行的 Waydroid，Konsole 窗口本身跑在宿主上，但展示的是容器的 Shell，两者都直接渲染在宿主的 Wayland 桌面上。

Waydroid 本身是 LXC 容器方案（基于 LineageOS 的 Android 镜像），所以在 nspawn 里跑 Waydroid 是一个两层嵌套结构，外层是 nspawn，内层是 LXC。问题的复杂性来自容器安全机制是里外叠加的——设备访问控制（cgroup eBPF）、seccomp 系统调用过滤、capability 边界集各有内外两层，取交集之后任何一处缺失都会表现为 Android 进程莫名死亡。本文按排障顺序记录，最后给出完整命令。

## 网络配置

网络是第一个要解决的问题，虽然它不是本次的难点。Waydroid 的 `waydroid-net.sh` 需要在容器里建网桥、启动 dnsmasq、配置 NAT，这要求容器保留 `CAP_NET_ADMIN`。

最终方案是 `--network-bridge=virbr0`。nspawn 的私有网络模式默认保留 `NET_ADMIN`，桥接到 libvirt 的 `virbr0` 之后，DHCP、DNS、NAT 都由 libvirt 现成的设施提供，容器里的 NetworkManager 自动获取地址，Waydroid 的网桥脚本也能正常运行。

这个方案还有一层原因。笔者最初让宿主上的 systemd-networkd 管理过相关接口，结果 networkd 重新加载时清理了它认为多余的策略路由规则，而笔者的 Mihomo 代理（TUN 模式）正依赖这些规则，宿主网络因此中断。让 networkd 完全不参与是最稳妥的选择。

容器镜像里 `/etc/resolv.conf` 是指向 systemd-resolved stub 的软链接，在容器里执行一次 `systemctl enable --now systemd-resolved` 即可（这个改动持久写在硬盘上，对物理启动和虚拟机同样适用），启动命令不要加任何 `--resolv-conf` 参数。

## loop 设备与镜像挂载

Waydroid 启动时要把 `system.img` 和 `vendor.img` 通过 loop 设备只读挂载，再叠加 overlay。最初的报错是：

```
mount: failed to set up loop device for /usr/share/waydroid-extra/images/system.img
```

排查确认 nspawn 有一个内置的设备过滤器（基于 cgroup v2 的 eBPF 设备控制器），实测的行为如下：

- `mknod` 字符设备节点，允许（实测 `mknod /tmp/tnull c 1 3` 成功）
- `mknod` 块设备节点，拒绝（`mknod /tmp/tloop b 7 0` 返回 EPERM）
- 对已经存在的设备节点，`open()` 是否放行由 `DeviceAllow` 控制

这意味着容器内无法通过 losetup 动态分配 loop 设备——自动分配的前提是能 mknod 新节点。所以改为在启动前由宿主侧预建节点，用 `modprobe loop max_loop=8` 让内核创建 8 个 loop 节点（内核模块的标准行为，不留下任何配置），再把节点全部绑定进容器：

```
--bind=/dev/loop-control --bind=/dev/loop0 ... --bind=/dev/loop7
--property=DeviceAllow="block-loop rwm"
--property=DeviceAllow="/dev/loop-control rwm"
```

还要注意先后顺序：`DeviceAllow="block-loop rwm"` 是按设备组名解析的，loop 模块必须在容器启动之前加载，否则组名解析不到设备，这一条会被静默忽略。所以命令开头先执行 modprobe（先 `modprobe -r` 再加载，是为了确保 `max_loop=8` 生效）。

## Binder：容器内自建 binderfs

Binder 的情况比预期简单。排查中发现，Waydroid 在内层容器启动前会自己创建 `/dev/binderfs` 并挂载一个新的 binderfs 实例，然后通过 `binder-control` 分配出 `anbox-binder`、`anbox-vndbinder`、`anbox-hwbinder` 三个节点。整个 Binder 栈完全自给自足，不需要从宿主绑定任何 Binder 设备。

要做的只是放行设备访问。宿主内核的 Binder 驱动是 Rust 重写版，在 `/proc/devices` 里的组名是 `rust_binder`：

```
--property=DeviceAllow="char-rust_binder rwm"
--property=DeviceAllow="char-binder rwm"
```

第二条是针对传统 C 版 Binder 组名的兜底，解析不到设备时 systemd 会静默忽略该条目，留着无害。

排查中有一次误判值得记录：验证 `DeviceAllow` 是否生效时，笔者最初去查 `machine-*.scope`，发现里面没有这些属性，一度认为属性没有生效。实际上直接由 `systemd-nspawn` 命令拉起的容器，scope 名是 `nv1-arch.scope`，单元名猜错了，看到的自然是空。实测删掉属性后 `binder-control` 打不开、加回后正常，属性一直是生效的。

## 通过 kmsg 获取 Android init 日志

解决了挂载和 Binder 之后，LXC 容器能进入 RUNNING 状态，但大约一秒就退出。`waydroid.log` 里只有两行 LXC 输出：

```
lxc-start: waydroid: cgroup2_devices.c: bpf_program_load_kernel: Operation not permitted
lxc-start: waydroid: utils.c: run_buffer: Script exited with status 126
```

第一行是 LXC 加载 cgroup 设备 BPF 程序失败（当时 bpf 系统调用还被 seccomp 拦截，见后文），第二行是 `lxc.hook.post-stop = /dev/null` 配置导致 hook"执行" `/dev/null` 返回 126。两者都不是死因，属于干扰信息。

继续排障的前提是拿到 Android init 的日志。先试 LXC 的 `lxc.console.logfile`，没有任何输出，因为 Waydroid 的配置里写着 `lxc.console.path = none`，不分配控制台。即使分配了控制台也没有用，因为 Android init 的日志只写 kmsg，它启动时会把 stdout/stderr 重定向到 `/dev/kmsg`。

于是目标变成打通 kmsg。第一次尝试是在 LXC 的 `config_nodes` 里把 `/dev/kmsg` 绑定进 Android 容器，同时给 nspawn 加 `--bind=/dev/kmsg` 和 `DeviceAllow="/dev/kmsg rwm"`。宿主的 `journalctl -k` 里立刻出现了 init 的日志，但内容揭示了一个新的死因：

```
init: mknod("/dev/kmsg", S_IFCHR | 0600, makedev(1, 11)) failed File exists
init: Init encountered errors starting first stage, aborting
init: InitFatalReboot: signal 6
```

Android init 在第一阶段会自己 `mknod /dev/kmsg`，并且用 `CHECK` 宏检查这一步的结果，节点已存在就判定为致命错误并重启。绑定进去的设备节点反而触发了这个检查。

但这条日志同时指出了正确的做法。设备节点不受挂载命名空间隔离，init 在 LXC 容器里自己 mknod 出的 `1:11` 字符设备，打开的就是宿主内核的 kmsg。唯一需要的是外层 nspawn 的设备过滤器放行这个 `open()`，也就是保留 `DeviceAllow="/dev/kmsg rwm"`，绑定是多余的。删掉 `config_nodes` 里那行绑定之后，`journalctl -k` 依然能看到 Android init 的全部日志。

到这一步，后续的每一次失败都能直接看到原因了。

## 补齐缺失的 capability

有了日志之后，真正的死因出现了。init 走完第一阶段，开始拉起系统服务，接下来的日志说明了一切：

```
init: cap_set_proc(18253611008) failed: Operation not permitted
init: failed to apply initial capset
init: cannot set capabilities for logd
init: Service 'logd' (pid 268) exited with status 6
...
init: critical process 'lmkd' exited 4 times before boot completed
init: InitFatalReboot: signal 6
```

logd、audioserver、lmkd 全部死于 `cap_set_proc()` 返回 EPERM。lmkd 是 critical 服务，在启动完成前退出 4 次，init 按规则触发致命重启，整个 LXC 容器随之退出。

`cap_set_proc` 的参数是能力位掩码，可以直接解码，比如另一条日志里的 `68719476736`：

```
68719476736 = 2^36 → capability 36 = CAP_BLOCK_SUSPEND
```

把 Android 镜像里所有 rc 文件声明的能力收集出来（`grep -rh "^    capabilities" /system/etc/init/*.rc | sort -u`），再对照 nspawn 默认保留的能力集，缺口是 `SYSLOG`、`AUDIT_CONTROL`、`BLOCK_SUSPEND`、`IPC_LOCK`、`WAKE_ALARM` 这五个。

背后的机制并不复杂。容器进程的 capability 边界集（bounding set）决定了它能给子进程设置哪些能力，请求集合之外的能力一律 EPERM。在嵌套容器中，这个集合是两层取交集的结果——外层 nspawn 有自己的默认保留集，内层 LXC 再用 `lxc.cap.keep` 裁剪。Waydroid 的 `cap.keep` 列表里包含 syslog、block_suspend 这些能力，裸机上工作正常，但外层 nspawn 不给的话，内层也无法获得。

修复方式是精确补齐这五个能力，不需要 `--capability=all`：

```
--capability=CAP_SYSLOG,CAP_AUDIT_CONTROL,CAP_WAKE_ALARM,CAP_BLOCK_SUSPEND,CAP_IPC_LOCK
```

## 放行 bpf 系统调用

还有一个问题在修复 capabilities 之前就预见到了，一并处理。nspawn 的 seccomp 过滤器是白名单制，默认允许集里没有 `bpf`，实测确认：

```python
libc.syscall(321, 0, 0, 0, 0, 0)  # SYS_bpf，返回 -1，errno 1 (EPERM)
```

而 Android 镜像里 `bpfloader.rc` 声明的是 critical 服务，它负责加载系统的 eBPF 程序（网络统计、流量控制都依赖它），bpf 不可用会再次触发致命重启。前文 LXC 那句 "Failed to load bpf program" 警告也来源于此。

修复方式是把它加入白名单：

```
--system-call-filter=bpf
```

配合容器中保留的 `CAP_SYS_ADMIN`（内核的 `bpf_capable()` 对 `CAP_SYS_ADMIN` 兼容放行），bpfloader 即可正常工作。

判断 seccomp 是否放行有个简单的方法：放行之后 errno 从 1（EPERM）变成 22（EINVAL），说明系统调用已经穿过过滤器，只是参数不合法。

## 最终命令

合并所有结论，得到这条启动命令。宿主上不需要任何配置文件或预建设备，容器关闭后无残留：

```bash
sudo sh -c 'modprobe -r loop 2>/dev/null; modprobe loop max_loop=8; exec systemd-nspawn -bD /tmp/nv1-arch --hostname=nv1-arch --network-bridge=virbr0 --capability=CAP_SYSLOG,CAP_AUDIT_CONTROL,CAP_WAKE_ALARM,CAP_BLOCK_SUSPEND,CAP_IPC_LOCK --bind=/dev/dri --bind=/dev/loop-control --bind=/dev/loop0 --bind=/dev/loop1 --bind=/dev/loop2 --bind=/dev/loop3 --bind=/dev/loop4 --bind=/dev/loop5 --bind=/dev/loop6 --bind=/dev/loop7 --bind=/dev/kmsg --bind-ro="$1/$2:/run/xdg/wayland-0" --bind-ro="$1/pulse:/run/xdg/pulse" --bind-ro="$3/.config/pulse/cookie:/root/.config/pulse/cookie" --property=DeviceAllow="char-drm rwm" --property=DeviceAllow="char-rust_binder rwm" --property=DeviceAllow="char-binder rwm" --property=DeviceAllow="block-loop rwm" --property=DeviceAllow="/dev/loop-control rwm" --property=DeviceAllow="/dev/kmsg rwm" --system-call-filter=bpf' _ "$XDG_RUNTIME_DIR" "$WAYLAND_DISPLAY" "$HOME"
```

各段的作用如下：

| 部分 | 作用 |
| --- | --- |
| `modprobe loop max_loop=8` | 预建 loop 节点（容器内没有 mknod 块设备的权限） |
| `--network-bridge=virbr0` | 私有网络命名空间，保留 NET_ADMIN，使用 libvirt 的 DHCP/DNS/NAT |
| `--capability=CAP_SYSLOG,...` | 补齐 Android 服务需要、nspawn 默认不给的五个能力 |
| `--bind=/dev/dri` + `char-drm` | GPU 渲染 |
| `--bind=/dev/loop*` + `block-loop` | 挂载 system/vendor 镜像 |
| `--bind=/dev/kmsg` + `DeviceAllow` | Android init 日志写入宿主内核日志，`journalctl -k` 可直接查看 |
| `char-rust_binder` / `char-binder` | 放行容器内自建 binderfs 的设备访问 |
| `--system-call-filter=bpf` | 放行 bpf 系统调用，供 bpfloader 使用 |
| `--bind-ro` 三个 | 传入 Wayland socket、Pulse socket 和认证 cookie，GUI 与音频直通宿主会话 |

容器启动后，在里面运行 `waydroid show-full-ui`（或先 `waydroid session start`），Android 即可完整启动。

## 残留会话的清理

**pkill 误杀自身。** 清理残留的 Waydroid 会话进程时，笔者在 `sh -c '...'` 里执行 `pkill -f "waydroid session"`，结果后续命令全部没有执行。原因是 `pkill -f` 匹配完整命令行，而执行这条命令的 `sh` 自身的 cmdline 里就包含这个模式串，pkill 把自己的父进程杀了。解决办法是把模式写成 `[w]aydroid session`，使其无法匹配自身。

**会话状态残留。** Waydroid 的容器服务会在内存中记录"已有一个会话在跟踪"（`Already tracking a session`），Android 崩溃后这个状态不会自动清除，再次启动会话会被拒绝。需要 `systemctl restart waydroid-container` 才能重置。笔者一度以为已经重启过该服务，实际是被上面的 pkill 问题中断，命令根本没有执行到。

## 总结

回顾整个过程，嵌套容器的问题可以归结为三层安全机制的叠加，即设备访问（外层 cgroup eBPF 过滤器与内层 LXC 设备控制）、系统调用（外层 seccomp 白名单与内层 LXC seccomp profile）、能力（外层边界集与内层 `lxc.cap.keep`）。每一层都是内外取交集，任何一处缺失都表现为内层进程莫名死亡。

[![#~/img/android/waydroid/waydroid-nested-layers.webp](/img/android/waydroid/waydroid-nested-layers.webp)](/img/android/waydroid/waydroid-nested-layers.webp)

这次排障的关键转折不是某个参数，而是先建立可观测性。把 Android init 的 kmsg 日志引到宿主的 `journalctl -k` 之后，每个死因都能直接从日志读出来，不再需要猜测。

此外，这里的所有适配都通过 nspawn 的运行时参数完成，没有修改宿主配置，也没有修改容器镜像。这块移动硬盘依然可以拔下来直接物理启动或作为虚拟机启动，三种使用方式互不干扰。
