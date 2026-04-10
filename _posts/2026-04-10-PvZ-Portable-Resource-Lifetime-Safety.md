---
layout:       post
title:        PvZ-Portable 资源释放时序安全：动画附件生命周期与 SDL 音频回调的硬防护
subtitle:     修复对象析构阶段外部异步访问导致的崩溃
date:         2026-04-10
author:       wszqkzqk
header-img:   img/games/bg-pvz-portable.webp
catalog:      true
tags:         C++ SDL2 游戏移植 开源软件 开源游戏 PvZ-Portable
---

## 引言

在 PvZ-Portable 的开发和测试过程中，笔者遇到一类非常棘手的崩溃：它们不发生在游戏逻辑最繁忙的更新阶段，而是在某个对象被销毁、资源被释放的**瞬间**触发。这类崩溃的共同特征是——对象已经开始析构，但外部系统仍在通过指针或回调异步访问它。

本文将记录两个典型的修复：一是 **Reanimator 动画附件系统的生命周期治理**，解决特定僵尸动画在加载和卸载时的指针混乱与悬空引用；二是 **SDL_mixer 音频实例的析构时序加固**，防止音效回调在声音对象已释放后继续触碰悬垂内存。这两个子系统截然不同，但指向同一个底层问题：**手动管理内存的 C++ 对象与外部 C 风格 API 之间的生命周期耦合**。

## Reanimator 动画附件的生命周期治理

### 崩溃现象与排查方向

最早触发问题的是投石车僵尸（Catapult Zombie）。在特定状态下切换贴图时，或者当包含该僵尸的关卡结束、动画资源被回收时，引擎会概率性崩溃。堆栈指向 Reanimator 的绘制路径或附件销毁路径，很容易让人误以为是图片资源本身的损坏或释放过早。

深入排查后，笔者发现问题的根源并不在资源加载器，而在 **Reanimator 的 Atlas 语义与附件的释放约定** 上。这两个层面的设计彼此交织，错误的假设一路传导，最终在高负载或对象销毁时被放大成崩溃。

### Atlas 语义修正：区分编码句柄与真实指针

PvZ-Portable 的重实现支持 Reanim Atlas，这是一种将多张贴图合并到一张大图集上的优化机制。在 Atlas 模式下，动画帧数据中的 `mImage` 字段存储的并不是可以直接绘制的 `Image*` 指针，而是一个**编码后的 Atlas 句柄**。绘制时需要通过 `GetEncodedReanimAtlas` 解码，才能得到真正的贴图信息和子图坐标。

旧代码在 `Reanimation::DrawTrack` 中对这流程的处理存在逻辑漏洞：

```cpp
// 旧代码（简化后）
Image* aImage = aTransform.mImage;
if (mDefinition->mReanimAtlas != nullptr && aImage != nullptr)
{
    ReanimAtlasImage* aAtlasImage = mDefinition->mReanimAtlas->GetEncodedReanimAtlas(aImage);
    if (aAtlasImage != nullptr)
        aImage = aAtlasImage->mOriginalImage;
    if (aTrackInstance->mImageOverride != nullptr)
        aAtlasImage = nullptr;
}
```

这段代码有两大问题：

第一，**解码顺序错误**。当某个 track 存在 `mImageOverride`（显示覆盖贴图）时，旧代码会先尝试将 `aImage` 当作 Atlas 句柄解码，然后再发现存在 override 并丢弃 Atlas 结果。这个顺序本身不致命，但它意味着 `aImage` 在没有 override 且不是合法 Atlas 句柄时，会被当作 raw `Image*` 使用——而实际上，如果 Atlas 存在，`aImage` 可能只是编码值，根本不是一个稳定可用的指针。

第二，**对非 Atlas 图片的误判**。旧代码的判定是：Atlas 存在且 `aImage != nullptr`，就进入 Atlas 解码分支。但逻辑上应该区分轨道变换自带的 frame image（可能是编码句柄）和显式指定的非 Atlas 覆盖图。如果开发者或游戏逻辑为某个 track 设置了一张普通的非 Atlas 图片作为 override，旧代码仍可能在 `aImage` 上执行 Atlas 解码，得到 `nullptr` 后又错误地把它当成空贴图处理。

修复后的逻辑彻底重写了分支结构：

```cpp
// 修复后
Image* aImage = aTransform.mImage;
ReanimAtlasImage* aAtlasImage = nullptr;
if (mDefinition->mReanimAtlas != nullptr && aImage != nullptr)
{
    aAtlasImage = mDefinition->mReanimAtlas->GetEncodedReanimAtlas(aImage);
    if (aTrackInstance->mImageOverride != nullptr)
    {
        aImage = aTrackInstance->mImageOverride;
        aAtlasImage = nullptr;
    }
    else if (aAtlasImage == nullptr)
    {
        aImage = nullptr;  // 不合法的编码句柄，不能当作 raw Image* 使用
    }
}
else if (aTrackInstance->mImageOverride != nullptr)
{
    aImage = aTrackInstance->mImageOverride;
}
```

修改后的关键变化是：

- **ImageOverride 优先级最高**。如果存在覆盖贴图，直接跳过 Atlas 路径，不再对 `aImage` 做任何假设性的解码。
- **严格区分 Atlas 编码句柄与 raw 指针**。如果 Atlas 存在但解码失败，`aImage` 会被显式置为 `nullptr`，杜绝将非法编码值当作普通指针解引用的风险。
- **绘制时的矩阵计算也分层处理**。如果 `aAtlasImage` 有效，使用 Atlas 的元数据计算 pivot；否则使用 `aImage` 自身的尺寸信息。

同一修复还同步应用于 `GetCurrentTrackImage` 和 `GetTrackMatrix`，确保查询和绘制两条路径的语义一致。

### 附件系统的释放

解决了 Atlas 语义问题后，另一类崩溃出现在 `Attachment` 系统的释放路径中。

在 PvZ-Portable 中，Attachment 是一种挂载在骨骼动画轨道上的特效容器。一个 Attachment 可以包含粒子系统（ParticleSystem）、拖尾（Trail）、子动画（Reanimation）甚至嵌套 Attachment。这些子资源的生命周期由 `EffectSystem` 统一管理，而 Attachment 本身则由 `AttachmentHolder` 通过一个 `DataArray` 分配和回收。

旧代码中存在两个互相加剧的问题：

**问题一：Detach 后没有清理条目。**

`AttachmentDetachCrossFadeParticleType` 用于在取消挂载某种粒子特效时，通知粒子系统进入 cross-fade 或死亡状态。旧代码的逻辑大概是：

```cpp
for (int i = 0; i < aAttachment->mNumEffects; i++)
{
    if ( ... 找到匹配的粒子 ... )
    {
        if (theCrossFadeName)
            aParticleSystem->CrossFade(theCrossFadeName);
        else
            aParticleSystem->ParticleSystemDie();
    }
}
```

这段代码**只通知了粒子系统死亡**，却没有将对应的 `AttachEffect` 条目从 Attachment 的 `mEffectArray` 中移除。结果是：粒子系统消亡后，Attachment 仍然保留着一个指向已死粒子系统的 ID。当后续代码遍历该 Attachment 的效果数组时，会拿到一个无效 ID，进而解引用一个已释放或已标记为 `mDead` 的对象。

修复后的逻辑在通知粒子死亡的同时，**立即将条目从数组中移除**：

```cpp
for (int i = 0; i < aAttachment->mNumEffects;)
{
    AttachEffect* aAttachEffect = &aAttachment->mEffectArray[i];
    // ... 匹配粒子逻辑 ...
    if (匹配成功)
    {
        if (theCrossFadeName)
            aParticleSystem->CrossFade(theCrossFadeName);
        else
            aParticleSystem->ParticleSystemDie();

        // 立即从数组中移除该条目
        int aNumEffectsRemaining = aAttachment->mNumEffects - i - 1;
        if (aNumEffectsRemaining > 0)
            memmove(aAttachEffect, aAttachEffect + 1, aNumEffectsRemaining * sizeof(AttachEffect));
        aAttachment->mNumEffects--;
        continue;
    }
    i++;
}

if (aAttachment->mNumEffects == 0)
{
    aAttachment->mDead = true;
    theAttachmentID = AttachmentID::ATTACHMENTID_NULL;
}
```

这样，Attachment 的所有权状态与底层粒子系统的实际生命周期始终保持一致。当最后一个 effect 被移除时，Attachment 自身也会立即被标记为死亡，不再被误用。

**问题二：没有主动回收死附件。**

`AttachmentHolder::AllocAttachment` 负责从 `DataArray` 中分配新的 Attachment。旧代码直接调用 `DataArrayAlloc`，没有任何容量满时的回收机制。如果 DataArray 接近容量上限，分配会失败，或者更糟糕的是——分配器可能复用一个尚未正确清理的槽位，导致新对象带着旧附件的残留数据。

修复方案是在 `AllocAttachment` 中引入预分配时的垃圾回收：当数组快要满时，先遍历所有现有 Attachment，调用新增的 `PruneDeadEffects` 函数清理已死亡的 effects，然后释放掉所有已经完全死亡的 Attachment。

```cpp
Attachment* AttachmentHolder::AllocAttachment()
{
    if (mAttachments.mSize + 1 >= mAttachments.mMaxSize)
    {
        // ... 遍历所有 attachment，执行 PruneDeadEffects ...
        // ... 将 mDead 的 attachment ID 收集到数组 ...
        // ... 逐个调用 DataArrayFree 释放死附件 ...
    }
    return mAttachments.DataArrayAlloc();
}
```

`PruneDeadEffects` 是一个集中式的状态清理器。它会检查 Attachment 上的每一个 effect，若对应的底层对象（粒子、Trail、Reanim、子 Attachment）已经死亡或无效，就通过 `memmove` 将其从紧凑数组中移除。这个函数既在分配压力的垃圾回收时被调用，也可以在未来需要时作为维护接口使用。

### 投石车僵尸的调用侧修正

在 Atlas 语义修正的同时，笔者还修复了 `Zombie::UpdateReanim` 中投石车僵尸对 `GetCurrentTrackImage` 的调用：

```cpp
// 旧代码
Image* aPoleImage = aReanim->GetCurrentTrackImage("Zombie_catapult_pole");
if (aPoleImage == IMAGE_REANIM_ZOMBIE_CATAPULT_POLE_WITHBALL && mSummonCounter != 0)
{
    aReanim->SetImageOverride(...);
}
```

这段代码试图通过查询当前轨道的贴图来判断投石车是否还载着篮球。但 `GetCurrentTrackImage` 在 Atlas 模式下返回的是不稳定的气候编码句柄，用它和特定的常量 `Image*` 做等值比较本身就是不可靠的。正确的逻辑应当直接依赖 `mSummonCounter` 这个已被计算好的状态变量：

```cpp
// 修复后
if (mSummonCounter != 0)
{
    aReanim->SetImageOverride("Zombie_catapult_pole", IMAGE_REANIM_ZOMBIE_CATAPULT_POLE_DAMAGE_WITHBALL);
}
```

不仅消除了 Atlas 句柄与 raw 指针比较带来的未定义行为，也让状态转换意图更加清晰。

---

这里插入一个关于 `ResourceManager` 的附带修复。在审查资源加载代码时，笔者为 `ParseImageResource` 中 sprite sheet 的 `rows` 和 `cols` 属性增加了 `TOD_ASSERT` 正向边界检查。这是一个防御性措施：如果资源配置文件因为格式错误或版本不一致而写入非正数，引擎可以在加载阶段就断言失败，而不是将零或负数带入后续的纹理切分计算中导致更隐蔽的崩溃。

## SDL 音频回调与对象析构的时序博弈

另一类崩溃出现在音效密集播放的场景：当僵尸数量很多、豌豆射手和西瓜投手同时开火时，游戏概率性 segfault，堆栈往往指向 SDL_mixer 的某个 effect callback 内部。

这个问题与动画附件系统的崩溃在表面上毫无关联，但究其本质，仍然是**对象已经释放，外部回调还在继续访问它**。

### 通道所有权的缺失

PvZ-Portable 使用 SDL_mixer 作为音频后端。音效播放的流程大致是：

- `SDLSoundManager` 维护一个 `Mix_Chunk` 数组（`mSourceSounds`）和一个固定大小的通道池（`mPlayingSounds`）。
- 当需要播放某个音效时，`SDLSoundManager` 找到一个空闲通道，创建一个 `SDLSoundInstance` 对象，然后调用 `Mix_PlayChannel` 开始播放。
- 为了支持音高变化（pitch），代码在 `Mix_PlayChannel` 之后通过 `Mix_RegisterEffect` 注册了一个回调函数 `PitchHandlerFuncCallback`，该回调会在 SDL_mixer 的混音线程中定期被调用。

旧代码中的 `SDLSoundInstance` 构造如下：

```cpp
SDLSoundInstance::SDLSoundInstance(SDLSoundManager* theSoundManager, Mix_Chunk* theSourceSound)
{
    // ...
    mChannel = -1;
}
```

播放时调用 `Mix_PlayChannel(-1, ...)` 让 SDL_mixer 自动分配通道。`mChannel` 只是被动记录 SDL_mixer 返回的通道号。这里的关键问题是：**SDLSoundInstance 并不知道自己被绑定到了哪个通道**。虽然 `SDLSoundManager` 在 `mPlayingSounds` 数组中以通道号为索引存放了实例指针，但实例对象本身并没有保留这个绑定关系。

### 析构时序的竞争

更致命的是，`SDLSoundInstance` 的析构函数在旧代码中是**完全空的**：

```cpp
SDLSoundInstance::~SDLSoundInstance()
{
    // 什么都不做
}
```

这意味着，如果某个音效实例因为以下原因被销毁：

- 自动释放逻辑（`mAutoRelease`）在播放结束后触发；
- 上层逻辑主动调用 `Release()`；
- `SDLSoundManager` 在清理时覆盖该通道；

那么 SDL_mixer 的混音线程仍可能在下一个 audio callback 中调用 `PitchHandlerFuncCallback(mChannel, ...)`，而这个回调需要读取 `SDLSoundInstance` 的成员 `mPitchHandler`。一旦实例已被 `delete`，这就是典型的 use-after-free。

### 修复：斩断回调先于停止播放

修复的核心时序非常明确：**在对象死亡之前，必须先切断外部系统对它的访问路径**。具体到 SDL_mixer，就是先 `Mix_UnregisterAllEffects` 注销 effect 回调，再 `Mix_HaltChannel` 停止播放。

修改后的 `Stop()` 实现：

```cpp
void SDLSoundInstance::Stop()
{
    if (mChannel >= 0 && mChannel < MAX_CHANNELS)
    {
        Mix_UnregisterAllEffects(mChannel);
        Mix_HaltChannel(mChannel);
        mChannel = -1;
    }
    mAutoRelease = false;
}
```

析构函数现在改为：

```cpp
SDLSoundInstance::~SDLSoundInstance()
{
    Stop();
}
```

这样，当 `SDLSoundInstance` 被销毁时，它会主动停止自己绑定的通道，并且在停止之前彻底注销 pitch effect。即使 `Mix_HaltChannel` 的执行存在异步延迟，由于回调已经被取消，混音线程不会再触碰这个垂死对象的任何成员。

### 通道保留与稳健边界

除了时序修复，笔者还为 `SDLSoundInstance` 增加了**通道保留机制**。`SDLSoundManager` 的空闲通道查找和实例创建逻辑天然确保了每个实例都有一个确定的通道，但旧代码没有把这个信息传递给实例。修复后：

```cpp
// 构造时传入预留的通道号
SDLSoundInstance::SDLSoundInstance(SDLSoundManager* theSoundManager,
                                   Mix_Chunk* theSourceSound,
                                   int theReservedChannel);

// SDLSoundManager 中
mPlayingSounds[aFreeChannel] = new SDLSoundInstance(
    this, mSourceSounds[theSfxID], aFreeChannel);
```

播放时优先请求该保留通道：

```cpp
const int aTargetChannel =
    (mReservedChannel >= 0 && mReservedChannel < MAX_CHANNELS) ? mReservedChannel : -1;
mChannel = Mix_PlayChannel(aTargetChannel, mMixChunk, (looping) ? -1 : 0);
```

如果 `Mix_PlayChannel` 返回 -1（例如该通道被其他高优先级声音抢占），`mChannel` 会被显式设为 -1，避免残留旧值导致后续操作越界。

同时，所有涉及 `mChannel` 的边界判断都收紧为 `mChannel >= 0 && mChannel < MAX_CHANNELS`，杜绝负数索引或越界数组访问的风险。

## 结语

动画附件系统的崩溃和 SDL 音频回调的崩溃，表面上分属两个毫不相干的子系统，但它们共享同一个底层模式：**手动管理内存的 C++ 对象在析构阶段，外部 C 风格的异步系统仍在通过指针或回调访问它**。

对 Reanimator 的修复思路是**建立显式的所有权清理和垃圾回收**：确保 Attachment 的 effect 数组与底层粒子/动画/Trail 的实际生命周期同步，并在分配压力下主动回收死对象。对 SDL 音频的修复思路则是**在对象死亡之前，按正确顺序切断外部回调**：先 UnregisterEffects，再 HaltChannel，析构函数绝不空手而归。

这两种思路——清理引用链和切断访问路径——是处理 C++ 与底层 C API 混用时生命周期问题的基本工具。PvZ-Portable 作为对 legacy 引擎的重实现，在处理这类历史遗留假设时仍需持续投入精力。

## ⚠️ 版权与说明

**重要：本项目仅包含代码引擎，不包含任何游戏素材！**

PvZ-Portable 严格遵守版权协议。游戏的 IP（植物大战僵尸）属于 PopCap/EA。

要研究或使用此项目，你**必须**拥有正版游戏（如果没有，请在 [Steam](https://store.steampowered.com/app/3590/Plants_vs_Zombies_GOTY_Edition/) 或 [EA 官网](https://www.ea.com/games/plants-vs-zombies/plants-vs-zombies) 上购买）。你需要从正版游戏中提取以下文件放到 PvZ-Portable 的程序所在目录中。

*   `main.pak`
*   `properties/` 目录

本项目的源代码以 [**LGPL-3.0-or-later**](https://www.gnu.org/licenses/lgpl-3.0.html) 许可证开源，欢迎学习和贡献。
