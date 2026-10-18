---
layout:       post
title:        在 systemd-nspawn 容器中运行 Waydroid
subtitle:     在 Arch Linux 中通过 systemd-nspawn 与 LXC 嵌套运行 Android
header-img:   img/android/lineage/lineage-bg.webp
date:         2026-10-17
author:       wszqkzqk
catalog:      true
tags:         Linux Android Waydroid systemd-nspawn LXC 容器
---

## 引言

笔者有一块移动固态硬盘，其中的 Btrfs 分区上安装了一套完整的 Arch Linux。这套系统有三种使用方式：直接在物理机上启动、作为虚拟机启动，或在宿主系统运行时通过 `systemd-nspawn` 将其作为容器启动。

前两种方式下，Waydroid 都能正常工作。但在 nspawn 容器中，Waydroid 会话刚启动，Android 容器便会在不到一秒内退出，而且不留下任何日志。经过排查，笔者最终用一条启动命令解决了这个问题，无需修改宿主配置或 Android 镜像，也不影响物理启动和虚拟机启动。

[![#~/img/android/waydroid/waydroid-in-systemd-nspawn-container.webp](/img/android/waydroid/waydroid-in-systemd-nspawn-container.webp)](/img/android/waydroid/waydroid-in-systemd-nspawn-container.webp)

图中的 Android 桌面由 nspawn 容器内的 Waydroid 提供。Konsole 窗口运行在宿主上，其中显示的是容器内的 Shell。两者都直接渲染在宿主的 Wayland 桌面上。

Waydroid 本身采用 LXC 容器方案，其 Android 镜像基于 LineageOS。因此，在 nspawn 中运行 Waydroid 会形成两层嵌套容器：外层是 nspawn，内层是 LXC。排查的难点在于，两层容器的安全机制会叠加生效：设备访问控制（cgroup eBPF）、seccomp 系统调用过滤和 capability 边界集都分别受到内外两层限制。最终权限相当于取交集，任何一层缺少必要权限，都可能导致 Android 进程异常退出。本文按排查过程展开，并在最后给出完整命令。

## 网络配置

首先需要配置网络，不过这部分并不复杂。Waydroid 的 `waydroid-net.sh` 需要在容器内创建网桥、启动 dnsmasq 并配置 NAT，因此容器必须保留 `CAP_NET_ADMIN`。

最终采用 `--network-bridge=virbr0`。nspawn 的私有网络模式默认保留 `CAP_NET_ADMIN`。将容器桥接到 libvirt 的 `virbr0` 后，即可直接使用 libvirt 提供的 DHCP、DNS 和 NAT。容器内的 NetworkManager 能自动获取地址，Waydroid 的网桥脚本也能正常运行。

选择这个方案还有另一个原因。笔者曾让宿主上的 systemd-networkd 管理相关接口，但 networkd 重新加载时会清理它认为多余的策略路由规则，而笔者的 TUN 代理恰好依赖这些规则，结果导致宿主网络中断。因此，让 networkd 不参与相关接口的管理更为稳妥。

容器镜像中的 `/etc/resolv.conf` 是指向 systemd-resolved stub 的软链接，因此只需在容器内执行一次 `systemctl enable --now systemd-resolved`。该设置会持久保存在硬盘上，物理启动和虚拟机启动时同样有效。此外，启动命令中不应添加任何 `--resolv-conf` 参数。

## loop 设备与镜像挂载

Waydroid 启动时，需要通过 loop 设备以只读方式挂载 `system.img` 和 `vendor.img`，然后再叠加 overlay。最初遇到的报错如下：

```
mount: failed to set up loop device for /usr/share/waydroid-extra/images/system.img
```

排查发现，nspawn 内置了基于 cgroup v2 eBPF 设备控制器的设备过滤器。实测行为如下：

- 允许通过 `mknod` 创建字符设备节点（实测 `mknod /tmp/tnull c 1 3` 成功）。
- 拒绝通过 `mknod` 创建块设备节点（`mknod /tmp/tloop b 7 0` 返回 EPERM）。
- 对于已经存在的设备节点，能否通过 `open()` 打开由 `DeviceAllow` 控制。

这意味着无法在容器内通过 `losetup` 动态分配 loop 设备，因为自动分配的前提是能够使用 `mknod` 创建新节点。解决方法是改由宿主在容器启动前预先创建设备节点：先用 `modprobe loop max_loop=8` 让内核创建 8 个 loop 节点（这是内核模块的标准行为，不会留下额外配置），再将这些节点全部绑定到容器中：

```
--bind=/dev/loop-control --bind=/dev/loop0 ... --bind=/dev/loop7
--property=DeviceAllow="block-loop rwm"
--property=DeviceAllow="/dev/loop-control rwm"
```

还需要注意加载顺序：`DeviceAllow="block-loop rwm"` 会按设备组名解析，因此必须在容器启动前加载 loop 模块。否则，系统将无法解析该设备组，这条规则也会被静默忽略。所以应在命令开头先执行 `modprobe`。先运行 `modprobe -r` 再重新加载，则是为了确保 `max_loop=8` 生效。

## Binder：容器内自建 binderfs

Binder 的配置比预期简单。排查发现，Waydroid 会在内层容器启动前自行创建 `/dev/binderfs` 并挂载一个新的 binderfs 实例，再通过 `binder-control` 创建 `anbox-binder`、`anbox-vndbinder`、`anbox-hwbinder` 三个节点。因此，无需从宿主绑定任何 Binder 设备，只需允许访问相应设备。

笔者使用的宿主内核采用 Rust 重写的 Binder 驱动，在 `/proc/devices` 中的设备组名为 `rust_binder`：

```
--property=DeviceAllow="char-rust_binder rwm"
--property=DeviceAllow="char-binder rwm"
```

第二条用于兼容采用传统 C 版 Binder 驱动的内核。两条规则同时保留，即可适应不同的内核版本和构建配置。

排查过程中还出现过一次误判。验证 `DeviceAllow` 是否生效时，笔者最初检查了 `machine-*.scope`，发现其中没有这些属性，便以为配置未生效。实际上，直接通过 `systemd-nspawn` 命令启动的容器，其 scope 名为 `nv1-arch.scope`。此前检查错了单元，自然看不到相关配置。进一步实测发现，删除属性后无法打开 `binder-control`，重新添加后则恢复正常，说明这些属性其实一直有效。

## 通过 kmsg 获取 Android init 日志

解决挂载和 Binder 的问题后，LXC 容器可以进入 RUNNING 状态，但仍会在约一秒后退出。`waydroid.log` 中仅记录了以下两行 LXC 输出：

```
lxc-start: waydroid: cgroup2_devices.c: bpf_program_load_kernel: Operation not permitted
lxc-start: waydroid: utils.c: run_buffer: Script exited with status 126
```

第一行表示 LXC 加载 cgroup 设备 BPF 程序失败。当时 `bpf` 系统调用仍被 seccomp 拦截，详见后文。第二行则是 `lxc.hook.post-stop = /dev/null` 导致 hook 尝试执行 `/dev/null`，因而返回 126。这两条日志都没有直接说明容器为何退出，容易干扰排查。

要继续排查，必须先获取 Android init 的日志。笔者先尝试了 LXC 的 `lxc.console.logfile`，但没有得到任何输出，因为 Waydroid 的配置中写着 `lxc.console.path = none`，不会分配控制台。即使分配控制台也无济于事：Android init 只向 kmsg 写入日志，启动时还会将 stdout/stderr 重定向到 `/dev/kmsg`。

接下来需要让 Android init 能够访问 kmsg。第一次尝试是在 LXC 的 `config_nodes` 中将 `/dev/kmsg` 绑定到 Android 容器，同时为 nspawn 添加 `--bind=/dev/kmsg` 和 `DeviceAllow="/dev/kmsg rwm"`。这样设置后，宿主的 `journalctl -k` 中立刻出现了 init 日志，但也暴露出另一个导致启动失败的问题：

```
init: mknod("/dev/kmsg", S_IFCHR | 0600, makedev(1, 11)) failed File exists
init: Init encountered errors starting first stage, aborting
init: InitFatalReboot: signal 6
```

Android init 在第一阶段会自行执行 `mknod /dev/kmsg`，并通过 `CHECK` 宏检查结果。如果节点已经存在，init 就会将其判定为致命错误并触发重启。因此，预先绑定进来的设备节点反而导致了启动失败。

不过，这条日志也提示了正确的做法：无需提前绑定 `/dev/kmsg`，只要让 init 在 LXC 容器内自行创建 `1:11` 字符设备节点即可。打开这个节点，访问的就是宿主内核的 kmsg。此时，只需让外层 nspawn 的设备过滤器允许这一 `open()` 操作，即保留 `DeviceAllow="/dev/kmsg rwm"`，无需再进行绑定。删除 `config_nodes` 中的绑定配置后，`journalctl -k` 依然能看到 Android init 的完整日志。

至此，后续每次失败的具体原因都能直接从日志中确认。

## 补齐缺失的 capability

有了日志，导致容器退出的直接原因很快显现出来。init 完成第一阶段并开始启动系统服务后，出现了以下日志：

```
init: cap_set_proc(18253611008) failed: Operation not permitted
init: failed to apply initial capset
init: cannot set capabilities for logd
init: Service 'logd' (pid 268) exited with status 6
...
init: critical process 'lmkd' exited 4 times before boot completed
init: InitFatalReboot: signal 6
```

logd、audioserver 和 lmkd 都因 `cap_set_proc()` 返回 EPERM 而退出。其中，lmkd 是 critical 服务。它在系统启动完成前退出 4 次后，init 按规则将其视为致命错误并重启，整个 LXC 容器也随之退出。

`cap_set_proc` 的参数是能力位掩码，可以直接换算。例如，另一条日志中的 `68719476736` 对应：

```
68719476736 = 2^36 → capability 36 = CAP_BLOCK_SUSPEND
```

收集 Android 镜像中所有 rc 文件声明的能力（可执行 `grep -rh "^    capabilities" /system/etc/init/*.rc | sort -u`），再与 nspawn 默认保留的能力集对照，可以发现缺少以下五项：`SYSLOG`、`AUDIT_CONTROL`、`BLOCK_SUSPEND`、`IPC_LOCK`、`WAKE_ALARM`。

其背后的机制并不复杂。容器进程的 capability 边界集（bounding set）决定了它能够为子进程设置哪些能力。如果试图设置该集合之外的能力，操作就会返回 EPERM。在嵌套容器中，最终可用的能力集合相当于内外两层限制的交集：外层 nspawn 使用自己的默认保留集，内层 LXC 再通过 `lxc.cap.keep` 进行裁剪。Waydroid 的 `cap.keep` 列表虽然包含 syslog、block_suspend 等能力，但如果外层 nspawn 没有授予这些能力，内层同样无法获得。

因此，只需精确补充这五项能力，无需使用 `--capability=all`：

```
--capability=CAP_SYSLOG,CAP_AUDIT_CONTROL,CAP_WAKE_ALARM,CAP_BLOCK_SUSPEND,CAP_IPC_LOCK
```

## 放行 bpf 系统调用

此外，还有一个问题在补齐上述能力之前就已经发现，可以一并处理。nspawn 的 seccomp 过滤器采用白名单机制，默认允许的系统调用中不包括 `bpf`。实测结果如下：

```python
libc.syscall(321, 0, 0, 0, 0, 0)  # SYS_bpf，返回 -1，errno 1 (EPERM)
```

Android 镜像中的 `bpfloader.rc` 将 bpfloader 声明为 critical 服务。该服务负责加载系统的 eBPF 程序，网络统计和流量控制等功能都依赖这些程序。如果 `bpf` 不可用，就会再次触发致命重启。前文 LXC 加载 BPF 程序失败的警告也由此产生。

解决方法是将 `bpf` 加入白名单：

```
--system-call-filter=bpf
```

同时保留容器中的 `CAP_SYS_ADMIN`（内核的 `bpf_capable()` 也接受 `CAP_SYS_ADMIN`），bpfloader 即可正常工作。

判断是否被 seccomp 拦截，有一个简单的方法：如果放行后 errno 从 1（EPERM）变为 22（EINVAL），就说明系统调用已经通过过滤器，只是传入的参数无效。

## 最终命令

综合以上结论，可以得到以下启动命令。宿主上不需要额外的配置文件，也不需要手动预建设备。容器关闭后，没有额外配置需要清理：

```bash
sudo sh -c 'modprobe -r loop 2>/dev/null; modprobe loop max_loop=8; exec systemd-nspawn -bD /tmp/nv1-arch --hostname=nv1-arch --network-bridge=virbr0 --capability=CAP_SYSLOG,CAP_AUDIT_CONTROL,CAP_WAKE_ALARM,CAP_BLOCK_SUSPEND,CAP_IPC_LOCK --bind=/dev/dri --bind=/dev/loop-control --bind=/dev/loop0 --bind=/dev/loop1 --bind=/dev/loop2 --bind=/dev/loop3 --bind=/dev/loop4 --bind=/dev/loop5 --bind=/dev/loop6 --bind=/dev/loop7 --bind=/dev/kmsg --bind-ro="$1/$2:/run/xdg/wayland-0" --bind-ro="$1/pulse:/run/xdg/pulse" --bind-ro="$3/.config/pulse/cookie:/root/.config/pulse/cookie" --property=DeviceAllow="char-drm rwm" --property=DeviceAllow="char-rust_binder rwm" --property=DeviceAllow="char-binder rwm" --property=DeviceAllow="block-loop rwm" --property=DeviceAllow="/dev/loop-control rwm" --property=DeviceAllow="/dev/kmsg rwm" --system-call-filter=bpf' _ "$XDG_RUNTIME_DIR" "$WAYLAND_DISPLAY" "$HOME"
```

各段的作用如下：

| 部分 | 作用 |
| --- | --- |
| `modprobe loop max_loop=8` | 预先创建 loop 节点（容器内无权通过 `mknod` 创建块设备节点） |
| `--network-bridge=virbr0` | 创建私有网络命名空间，保留 `CAP_NET_ADMIN`，并使用 libvirt 提供的 DHCP/DNS/NAT |
| `--capability=CAP_SYSLOG,...` | 补充 Android 服务需要、但 nspawn 默认未授予的五项能力 |
| `--bind=/dev/dri` + `char-drm` | GPU 渲染 |
| `--bind=/dev/loop*` + `block-loop` | 挂载 system/vendor 镜像 |
| `--bind=/dev/kmsg` + `DeviceAllow` | 将 Android init 日志写入宿主内核日志，可通过 `journalctl -k` 直接查看 |
| `char-rust_binder` / `char-binder` | 允许访问容器内自行创建的 binderfs 设备 |
| `--system-call-filter=bpf` | 放行 `bpf` 系统调用，供 bpfloader 使用 |
| 三个 `--bind-ro` 参数 | 传入 Wayland socket、Pulse socket 和认证 cookie，使 GUI 和音频直接接入宿主会话 |

容器启动后，在其中运行 `waydroid show-full-ui`（或先 `waydroid session start`），即可完整启动 Android。

## dconf 运行目录的权限

以普通用户身份在容器内运行 GUI 程序时，可能遇到以下警告：

```
dconf-CRITICAL **: unable to create directory '/run/xdg/dconf': Permission denied.
```

dconf 是 GTK 程序使用的设置后端，需要在 `$XDG_RUNTIME_DIR` 下创建 `dconf` 目录存放运行时文件。容器中的 `/run/xdg` 是为接入宿主 Wayland 和 Pulse 而创建的目录，属主是 root，普通用户进程无法在其中新建目录。这个警告不影响程序运行，但设置的读取与变更通知会失效。

处理方法是预先创建该目录，并将属主指定给普通用户：

```
install -d -o wszqkzqk -g wszqkzqk -m 700 /run/xdg/dconf
```

不过 `/run` 是 tmpfs，重启后就会丢失，因此还需要在容器内写入 `/etc/tmpfiles.d/xdg-dconf.conf`，让 systemd-tmpfiles 在每次启动的早期重建：

```
d /run/xdg 0755 root root -
d /run/xdg/dconf 0700 wszqkzqk wszqkzqk -
```

这条规则在物理启动和虚拟机启动时只会创建两个空目录，没有其他影响。

还需要注意的是，普通用户会话在容器内有自己的 `/run/user/1000`，但不宜把 GUI 程序的 `XDG_RUNTIME_DIR` 切换过去。容器内运行的 pipewire 已经占用 `/run/user/1000/pulse`，而容器中没有声卡，走这条路径的音频不会有声音。继续使用 `/run/xdg` 直接接入宿主的 Wayland 和 Pulse 即可。

## 残留会话的清理

清理残留的 Waydroid 会话进程时，笔者曾在 `sh -c '...'` 中执行 `pkill -f "waydroid session"`，结果后续命令都没有执行。原因是 `pkill -f` 会匹配完整命令行，而当前 `sh` 进程的 cmdline 也包含该模式，于是父进程被一并终止。将匹配模式写成 `[w]aydroid session`，就能避免匹配到当前命令行。

Waydroid 的容器服务还会在内存中保留会话跟踪状态。Android 异常退出后，该状态不会自动清除。如果再次启动会话，就会遇到 `Already tracking a session` 错误，需要执行 `systemctl restart waydroid-container` 重置状态。笔者一度以为已经重启过该服务，后来才发现，前面的 `pkill` 问题中断了整个命令序列，重启操作实际上并未执行。

## 总结

回顾整个排查过程，嵌套容器的问题主要来自三类安全机制的叠加：设备访问（外层 cgroup eBPF 过滤器与内层 LXC 设备控制）、系统调用（外层 seccomp 白名单与内层 LXC seccomp profile）以及能力（外层边界集与内层 `lxc.cap.keep`）。每一类权限都受内外两层共同限制。任何一层缺少必要权限，都可能导致内层进程异常退出。

[![#~/img/android/waydroid/waydroid-nested-layers.webp](/img/android/waydroid/waydroid-nested-layers.webp)](/img/android/waydroid/waydroid-nested-layers.webp)

将 Android init 的 kmsg 日志接入宿主的 `journalctl -k` 后，每次失败的原因都能直接确认，后续排查无需再靠猜测。

除在容器系统中启用 `systemd-resolved`、添加 dconf 目录的 tmpfiles 规则这两处一次性设置外，其余适配都通过 nspawn 的运行时参数完成，无需修改宿主配置或 Android 镜像。这块移动硬盘仍可直接在物理机上启动，或作为虚拟机启动，三种使用方式互不干扰。
