---
layout:       post
title:        PvZ-Portable：在编译期检查格式化字符串
subtitle:     迁移到 std::format
header-img:   img/games/pvz-portable/bg-pvz-portable.webp
date:         2026-09-02
author:       wszqkzqk
catalog:      true
tags:         C++ 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

printf 家族大概是 C 时代留下来、至今仍最常用的一套接口。它灵活，也足够危险：格式串和实参之间没有类型系统的约束，只要两边对不上，程序就进入未定义行为。更麻烦的是，这类问题通常不会立刻暴露。在常见的桌面 ABI 上，把 `size_t` 传给 `%d` 之类的错误，很多时候还能“正常运行”，最多输出一个不容易被发现的错误数字。

[PvZ-Portable](https://github.com/wszqkzqk/PvZ-Portable) 从 SexyAppFramework 继承来的格式化接口，原来就是这种情况。引擎里的 `StrFormat`/`VFormat`、日志接口 `PvzpLogLn`/`PvzpTrace*`，以及断言宏 `PVZP_ASSERT`，在整个项目里有 560 多个调用点。编译器看不到它们的格式串和实参是否匹配，运行时只能按格式串去遍历 `va_list`；一旦传错，结果就是 UB。

我最近把这部分代码重新整理了一遍。先给仍在使用的 printf 风格接口加上 GNU format 属性，让编译器检查所有调用点（[#450](https://github.com/wszqkzqk/PvZ-Portable/pull/450)）；再把字面量格式串迁移到 `std::format`，只为运行时加载的格式串保留一个 printf 入口（[#460](https://github.com/wszqkzqk/PvZ-Portable/pull/460)）。第一轮检查就找出了 4 个真实的类型不匹配，其中一个已经影响了日志内容。下面记录一下这次迁移，以及过程中几个容易忽略的细节。

## 原来的格式化接口

这套格式化设施的核心是 `VFormat`。它先用一次 `vsnprintf` 计算所需长度，再分配恰好足够的 `std::string`，最后写入第二遍（`src/SexyAppFramework/Common.cpp`，迁移前）：

```cpp
std::string Sexy::VFormat(const char* fmt, va_list argPtr)
{
	va_list argsCopy;
	va_copy(argsCopy, argPtr);

#ifdef _WIN32
	int required = _vscprintf(fmt, argsCopy);
#else
	int required = vsnprintf(nullptr, 0, fmt, argsCopy);
#endif
	va_end(argsCopy);

	if (required <= 0)
		return std::string();

	std::string result;
	result.resize((size_t)required + 1);
	// 第二遍：真正写入
	...
}
```

`StrFormat` 只是再包一层，负责调用 `va_start`。它的声明旁边还留着一条很早以前的注释：

```cpp
//overloaded StrFormat: should only be used by the xml strings
```

最初的设计确实是只给 XML 资源字符串做参数替换。但注释并不能阻止接口扩散。到这次迁移开始时，`StrFormat` 的字面量格式串已经有 119 个调用点，日志相关接口又有几百处。封装只是把 `va_list` 藏了起来，并没有消除格式串和实参不匹配的风险。

## 先让编译器发现错误

GCC 和 Clang 支持 `__attribute__((format(printf, m, n)))`。这个属性告诉编译器：第 `m` 个参数是 printf 风格的格式串，从第 `n` 个参数开始是它要消费的实参。标记之后，编译器会像检查 `printf` 一样检查这些函数的调用。

我先在公共头文件里定义一个跨编译器的宏，再把它加到所有格式化入口（`src/SexyAppFramework/Common.h`）：

```cpp
#if defined(__GNUC__) || defined(__clang__)
#define SEXY_FORMAT_ATTRIBUTE(theFormatIndex, theFirstArgIndex) __attribute__((format(printf, theFormatIndex, theFirstArgIndex)))
#else
#define SEXY_FORMAT_ATTRIBUTE(theFormatIndex, theFirstArgIndex)
#endif

void				PrintF(const char *text, ...) SEXY_FORMAT_ATTRIBUTE(1, 2);
void				LogError(const char* theFormat, ...) SEXY_FORMAT_ATTRIBUTE(1, 2);
extern std::string	VFormat(const char* fmt, va_list argPtr) SEXY_FORMAT_ATTRIBUTE(1, 0);
extern std::string	StrFormat(const char* fmt ...) SEXY_FORMAT_ATTRIBUTE(1, 2);
```

这里有两个容易弄错的下标。普通的变参函数用 `(1, 2)`；`VFormat` 把参数打包在 `va_list` 中，因此第三个下标写 `0`，编译器只能检查格式串本身，无法继续检查 `va_list` 里的实参。MSVC 没有对应的属性，宏在那里展开为空，所以 Windows 构建少这一层检查，这是方案本身的限制。

断言接口还遇到了一个 clang 特有的误报。原来的声明带有默认参数：

```cpp
void PvzpAssertFailed(const char* theCondition, const char* theFile, int theLine, const char* theMsg = "", ...);
```

大多数调用点没有传消息，使用的是默认的 `""`。加上属性后，clang 的 `-Wformat-security` 把这些调用都当成了非字面量格式串，于是出现一批误报。处理方式是增加一个“不带消息”的重载，只给真正带格式串的重载加属性；格式参数从第 4 个变成第 5 个，所以属性下标也改为 `(4, 5)`：

```cpp
void PvzpAssertFailed(const char* theCondition, const char* theFile, int theLine);
void PvzpAssertFailed(const char* theCondition, const char* theFile, int theLine, const char* theMsg, ...) SEXY_FORMAT_ATTRIBUTE(4, 5);
```

### 4 个实际找出来的问题

属性加上以后，560 多个调用点里有 4 处格式串和实参确实不匹配。这 4 处都是真问题，不是为了消掉告警而做的形式修复。

**`size_t` 传给了 `%d`**（`ResourceManager::DumpCurResGroup`）：

```diff
- theDestStr = StrFormat("About to dump %d elements from current res group name %s\r\n", rl->size(), mCurResGroup.c_str());
+ theDestStr = StrFormat("About to dump %zu elements from current res group name %s\r\n", rl->size(), mCurResGroup.c_str());
```

`rl->size()` 的类型是 `size_t`，在 64 位构建中为 64 位，而 `%d` 只会按 32 位 `int` 读取。在 x86-64 System V ABI 上，数量较小时通常还能碰巧得到正确的低 32 位，但这仍然是未定义行为，换一个 ABI 就不能指望同样的结果。

**C 字符串传给了 `%d`**（`LawnGetCurrentLevelName`）：

```diff
- return StrFormat("F%d", gLawnApp->GetStageString(gLawnApp->mBoard->mLevel).c_str());
+ return StrFormat("F%s", gLawnApp->GetStageString(gLawnApp->mBoard->mLevel).c_str());
```

`GetStageString` 返回的是类似 `"1-2"` 的文本，这里要生成的结果是 `F1-2`。原来的 `%d` 却把 `const char*` 指针当成整数读取，所以冒险模式回放的加载日志中，关卡名会变成一串乱码数字。这个问题一直存在，只是日志没有经常被逐行检查。

**`intptr_t` 传给了 `%u`**（`LawnApp::Init` 的会话日志）：

```diff
- PvzpLogLn("session id: %u", mSessionID);
+ PvzpLogLn("session id: %lld", static_cast<long long>(mSessionID));
```

**对象指针传给了 `0x%x`**（`DataArrayFree`/`DataArrayGetID` 的断言消息）：

```diff
- PVZP_ASSERT(..., "Failed: DataArrayFree(0x%x) in %s", theItem, mName);
+ PVZP_ASSERT(..., "Failed: DataArrayFree(%p) in %s", (void*)theItem, mName);
```

断言触发时，原写法会在 64 位平台截断指针，只打印低 32 位。这样的地址不仅不完整，还可能把排查方向带偏。

修完这 4 处后，项目重新编译通过。即使暂时不迁移到 `std::format`，给 printf 风格的封装加上这个属性也很值得：改动只有几行宏，却能让整个调用面得到编译期检查。

## 把字面量调用迁到 `std::format`

format 属性能告诉我们“这里传错了”，但 printf 的接口设计本身仍然容易出错。格式串和实参在类型上完全脱钩，`%zu`、`%lld`、`%hhu` 等长度修饰符都要靠人手动对齐。

`std::format` 把这层关系交给类型系统。`{}` 按实参的类型进行格式化；当格式串是字面量时，`std::format_string` 的 `consteval` 构造会在编译期检查占位符和实参是否匹配。这样迁移之后，调用点不再需要记住一套和类型分离的长度修饰符。

这次一共迁移了 119 个字面量格式串。下面是商店金币显示的一处改动：

```cpp
// 旧
return StrFormat("$%d,%03d,%03d", aValue / 1000000, (aValue - aValue / 1000000 * 1000000) / 1000, aValue - aValue / 1000 * 1000);
// 新
return std::format("${},{:03d},{:03d}", aValue / 1000000, (aValue - aValue / 1000000 * 1000000) / 1000, aValue - aValue / 1000 * 1000);
```

`%03d` 对应 `{:03d}`，但新写法的占位符直接和参数绑定，读代码时不必再从格式串反推每个参数的类型。

### 封装接口也要改成 format 模板

不能只把调用点里的 `StrFormat` 替换成 `std::format`。日志和断言这些封装，如果仍然接受 `const char*` 加省略号，编译期检查还是会在封装边界处丢掉。最后留下的是 5 个 format 模板；以 `PvzpLogLn` 为例（`src/PvzpLib/PvzpDebug.h`）：

```cpp
template<typename... Args>
void PvzpLogLn(std::format_string<Args...> theFmt, Args&&... theArgs)
{
	Sexy::DispatchLogLn(Sexy::SexyLogPriority::Info, std::vformat(theFmt.get(), std::make_format_args(theArgs...)));
}
```

这里的参数类型必须是 `std::format_string<Args...>`，不能退回到普通的 `std::string_view`。前者的 `consteval` 构造函数会在编译期验证格式串，后者只是一个字符串视图，检查能力就没有了。

实现中使用 `std::vformat`，而不是直接假设 `format_string` 能转换为 `string_view`。libc++ 的 `format_string` 没有提供这种转换，访问 `.get()` 才是可移植的写法。

## 顺便整理日志路径

迁移格式化接口时，我也把日志入口整理了一遍。此前 `PvzpTrace` 只写 SDL，`PvzpLogLn` 只写文件（而且只在 `PVZ_DEBUG` 构建中生效），`PvzpTraceAndLogLn` 才会两边都写。每个调用点都要自己决定日志去哪儿，写文件也只是每条消息单独打开 `std::ofstream`、追加一行再关闭。

现在日志先进入同一个分发函数，再由它写 SDL；如果调试构建注册了文件 sink，就同时追加到日志文件（`src/SexyAppFramework/Common.cpp`）：

```cpp
void Sexy::DispatchLogLn(SexyLogPriority thePriority, std::string_view theText)
{
	if (theText.empty())
		return;

	SDL_LogMessage(SDL_LOG_CATEGORY_APPLICATION, thePriority == SexyLogPriority::Error ? SDL_LOG_PRIORITY_ERROR : SDL_LOG_PRIORITY_INFO, "%.*s", static_cast<int>(theText.size()), theText.data());

	std::scoped_lock aLock(gLogFileSinkMutex);
	if (gLogFileSink.is_open())
	{
		gLogFileSink << theText << '\n' << std::flush;
		...
	}
}
```

SDL 输出使用 `"%.*s"` 传入 `string_view` 的长度，不需要为了得到 NUL 结尾的字符串再做一次堆分配。文件 sink 只在 `PVZ_DEBUG` 构建的游戏初始化时注册，日志目的地也因此不再由每个调用点单独决定。

`Ln` 后缀现在是接口契约的一部分：一次调用输出一行，换行由函数追加。迁移时发现有 46 个调用点在消息末尾自己写了 `\n`，结果 `log.txt` 里多出了空行。最后逐个修掉这些调用点，而没有在分发函数里统一剥除换行；契约写在名字里，后续调用时更容易注意到。

## 运行时格式串仍然需要 printf

`std::format` 的编译期检查有一个前提：格式串必须在编译期可见。PvZ-Portable 的本地化资源字符串不符合这个条件。游戏文本从 `properties/` 下的字符串表运行时加载，例如删除存档确认框的模板：

```text
This will permanently remove '%s' from the player roster!
```

模板会随语言和资源版本变化，不能把它当成编译期字面量来检查。对这类输入，printf 风格并不是单纯的历史包袱，而是运行时格式化的必要接口。

因此 `VFormat` 没有继续作为公共工具保留，而是在只剩一个调用者后，把两遍 `vsnprintf` 的实现直接移进 `LawnApp::GetFormattedString`。现在 printf 风格格式化只服务运行时资源模板，其他字面量格式串都走 `std::format`。

这个改动还修掉了一处不明显的 UB。C 标准要求 `va_start` 的最后一个命名参数是 trivially copyable 类型；原来的签名使用 `const std::string&`，在常见 ABI 上虽然往往能运行，但标准并不保证这一点。`GetString` 本来就接受 `string_view`，所以这里改成 `string_view` 只是把签名改正确，不改变行为。

## 迁移时几个容易漏掉的细节

**`%X` 和负数：printf 与 `std::format` 并不完全相同。** `Buffer::ToWebString` 要把位串长度写成 8 位十六进制：

```cpp
// 旧
snprintf(aStr, sizeof(aStr), "%08X", aSizeBits);
// 新
aString += std::format("{:08X}", static_cast<unsigned int>(aSizeBits));
```

printf 的 `%X` 会按 `unsigned int` 解释实参，即使传入的是负数也会输出对应的位模式；`std::format` 会保留有符号类型的负号，结果可能变成 `-2A`。因此这里的 `static_cast<unsigned int>` 是保持语义一致所必需的，不是为了让类型看起来更整齐。

**Apple libc++ 对浮点格式化有可用性限制。** 迁移后新增的浮点格式化路径让 iOS 构建直接失败：Apple 的 libc++ 用 availability 宏控制这部分 `std::format`，支持门槛在 iOS 16.4，而项目原来的 deployment target 是 15.0。最后同步修改了 iOS triplet、CMake 的 `XCODE_ATTRIBUTE_IPHONEOS_DEPLOYMENT_TARGET` 和构建脚本，把目标版本提高到 16.4。macOS 在这里没有固定 deployment target，因此不需要改动。

**模板转发的参数包不一定能再转发一层。** 限频日志 `PvzpTraceWithoutSpamming` 最初会在时间检查后，把 `format_string` 和实参原样转给 `PvzpLogLn`。只要实参全是左值，这样通常可以编译；一旦出现右值，两层模板推导出的参数包就可能不同，`basic_format_string` 的转换随之失败。最后的实现不再转发，而是像 `PvzpLogLn` 一样直接调用 `std::vformat`：

```cpp
template<typename... Args>
void PvzpTraceWithoutSpamming(std::format_string<Args...> theFmt, Args&&... theArgs)
{
	static uint64_t gLastTraceTime = 0LL;
	uint64_t aTime = std::time(nullptr);
	if (aTime <= gLastTraceTime) // at most one trace per second
		return;

	gLastTraceTime = aTime;
	Sexy::DispatchLogLn(Sexy::SexyLogPriority::Info, std::vformat(theFmt.get(), std::make_format_args(theArgs...)));
}
```

**简单的整数转换不必使用 format。** `std::format("{}", n)` 能做的事情，`std::to_string(n)` 同样能做，而且没有格式化引擎的额外开销。没有宽度、补零或后缀等要求的调用点都换成了 `std::to_string`，只有确实需要格式说明的地方才保留 `std::format`。

## 收尾与验证

迁移完成后，`StrFormat`、`VFormat`、`PrintF`、`PvzpSnprintf`/`PvzpVsnprintf` 都被删除。第一轮引入的 `SEXY_FORMAT_ATTRIBUTE` 也随着 `VFormat` 移入 `GetFormattedString` 而从 `Common.h` 消失了。

验证时我没有只看“能不能编译”，还逐项比较了输出。内存泄漏的 hex dump、性能报告、资源错误信息、`ToWebString` 生成的 web 字符串、SEH 信息和字体数据等路径，从 `snprintf` 改为 `std::format` 后都保持了逐字节一致。文件日志除了修复 46 处多余换行、恢复正确的 `F1-2` 之外，没有其他变化。

所有目标平台（GCC/Clang/MSVC，以及桌面、Android、iOS、WASM）均编译通过。现在只要是字面量格式串，调用点就会接受编译期检查；运行时格式串则集中在 `GetFormattedString` 这一处。

## 结语

这次改动涉及 50 多个文件，但留下的经验并不复杂，主要有三点。

**封装不会自动带来类型安全。** `StrFormat` 和日志接口把 printf 包了起来，却没有改变它的类型约束。加上几行 format 属性后，560 多个调用点里就暴露出了 4 个真实错误，其中还有一个已经污染了日志输出。只要项目里还存在 printf 风格的变参接口，这一步就值得做。

**编译期检查总有边界。** 本地化模板是在运行时从资源表读出来的，`std::format` 不可能替它完成编译期验证。与其给这类字符串套一层看似安全、实际绕过检查的接口，不如把运行时格式化限制在一个清楚的入口里。

**迁移时要比较语义，而不只是替换语法。** `%X` 对负数的处理、`va_start` 对最后一个命名参数的要求，以及 Apple 平台的标准库可用性，都不会在简单的文本替换中自动解决。对于本来就不应该变化的输出，逐字节比较仍然是最可靠的回归检查。

以前，格式串和实参是否匹配只能靠调用者自己记住；现在，字面量调用不匹配就无法通过编译。运行时的行为基本没有变化，代码里却少了一类不容易察觉、也很难排查的隐患。

## ⚠️ 版权与说明

PvZ-Portable 严格遵守版权协议。游戏 IP（植物大战僵尸）属于 PopCap/EA。

本项目仅包含开源重实现的引擎代码，**不含任何游戏美术、音效、关卡等受版权保护的资源文件**。研究或使用此项目时，**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies)购买）。你需要从正版游戏中提取以下文件，放到 PvZ-Portable 的程序所在目录：

- `main.pak`
- `properties/` 目录下的资源文件

PvZ-Portable 的源代码以 **LGPL-3.0-or-later** 许可证开源。
