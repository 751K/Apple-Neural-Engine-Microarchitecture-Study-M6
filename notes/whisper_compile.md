# Whisper 编码器在 M6 上编译失控：双 ANE 空间拆分的全局细化每层写约 2.4 GB 交换文件

- 日期：2026-10-04
- 环境：M6（Mac18,5，T8152 / h18g，16 GB 内存），M4（Mac16,10，h16g，16 GB 内存），两台都是 macOS 27.0.1（26A434），
  ANECompiler 10.26.6（`zin_ane_compiler v10.26.6`，源码版本 10026006000000），AppleNeuralEngine 382.15.1。
- 模型：WhisperKit 的 Core ML 包 `openai_whisper-large-v3-v20240930_turbo`（argmaxinc/whisperkit-coreml）。
- 工具：`tools/03_compile/whisper_load.sh`、`whisper_tmp.sh`、`whisper_capture.sh`、`whisper_anecc.sh`、`whisper_trunc.py`；
  `tools/common/cmload.m`、`tools/common/anecc.m`、`tools/05_compute/hwx_kern.py`、`tools/lib/hwx_bonded.py`。
- 数据：`data/03_compile/whisper_compile/`（README 有逐项数字）；调用栈采样和抓出的 `model.mil` 含 Apple 内部内容，在 `private/whisper_ane_mil/`（不入库）。
- 相关：defects.md A1、A2、B1、B2，新增 A3、A4；compile_cost.md §1–4。

## 0. 结论（报告用）

1. **M6 上 Whisper large-v3-turbo 的音频编码器无法实际用上 ANE。** 首次加载时 ANE 编译器要写约 78 GB 的临时文件，经 Core ML 还要 20 分钟以上；
   同一个模型在 M4（同样 16 GB 内存、同一系统）上 80 s、1.3 GB 就编完。解码器等其余三个子模型在 M6 上都在 2.3 s 内编完。【计时】
2. **只有双 ANE 目标 h18g 出问题。** 不经 Core ML、用 anecc 直接编译 Core ML 转换后的同一份模型：h16g、h18（M6 单引擎目标）都是 41 s、磁盘 3.8 GB；
   h18g 每个编码器层多写约 2.4 GB、多花约 11 s，与层数成正比。只有一层也能复现（12 s、2.7 GB，对比 h18 的 5 s、0）。【计时】
3. **出问题的阶段是双 ANE 空间拆分里的"全局细化"。** h18g 编译时 97% 的调用栈采样在
   `ZinMirSplitSpatially → … → ZinMirSpatialSplitter::TileWithGlobalRefinement → MirOpt::MergeConvolutions → MirOpt::CreateMergedNEConvLayer`，
   其下是读取、复制权重和计算权重的 SHA-256。数据写在编译输出目录里的 `anecompiler.swap.*` 文件中，进程内存只有约 6 GB。【编译器】
4. **这一步是拆到两个 ANE 的必要步骤，不能简单关掉。** 编译器选项 `GlobalRefinementInSpatialSplit = false`（顶层 flags）让 h18g 编译回到 8 s、磁盘 0，
   但编出的"双 ANE"程序只剩 ANE0，编译器放弃了拆分。【HWX】
5. **周边的两个问题把它放大成"机器不可用"：** 客户端退出后编译服务继续编、继续写；编译器不检查剩余磁盘空间，会把磁盘写满，系统随之清掉 ANE 编译缓存，
   之后每次加载都从头编译。【计时】【推断】
6. 默认 h18g 拆出的双 ANE 程序也很不均衡：ANE1 的 TD 流约是 ANE0 的 13 倍（L4）。即使编完，双 ANE 对这个编码器的加速也有限。【HWX】

## 1. 现象：B7 测评中的 M6 全 ANE 组合

- 2026-10-02 用 WhisperKit（`whisperkit-cli` 1.1.0）测评时，M6 上每启动一个新进程、选全 ANE（编码器和解码器都 `cpuAndNeuralEngine`），
  加载都要 20–24 分钟（1,428 s），期间 `ANECompilerService` 攒了约 60 GB 临时文件，把磁盘写满到只剩 121 MB；之后系统清掉了 ANE 编译缓存，
  每次加载都要重新编译。客户端被结束后，编译服务仍在后台满负荷运行，只能 `sudo killall -9 ANECompilerService`。
- 同一模型在 M4 上加载不到 1 s（已有缓存），首次编译 80 s。
- 当时的推断是"新进程不复用编译缓存"，以及"M6 每次调用 ANE 的开销大"。下面逐项核实。

## 2. 排查过程

### 2.1 四个子模型分别加载（Core ML，`whisper_load.sh`）

每个子模型复制 `cmload` 为新进程名后加载（Core ML 与 aned 的缓存按进程名区分，新名字强制重新编译），再用同一名字加载一次：

| 子模型（mlmodelc 大小） | 首次加载 | 临时空间峰值 | 同名再加载 |
|---|---:|---:|---:|
| MelSpectrogram（392 KB） | 0.39 s | 0 | 0.07 s |
| TextDecoderContextPrefill（12 MB） | 0.04 s | 0 | 0.01 s |
| TextDecoder（328 MB） | 2.29 s | 0.5 GB | 0.08 s |
| AudioEncoder（1.2 GB） | 438 s 时可用空间低于 15 GB，中止 | 44.1 GB | — |

- 编译代价几乎全在编码器上。【计时】
- **编译结果是能复用的**：同名进程再加载只要 0.01–0.08 s。10-02 "每次都重编"是磁盘写满后缓存被清掉的结果，不是"新进程不复用缓存"。【计时】

### 2.2 临时空间写到了哪里（`whisper_tmp.sh`，需 root）

编码器首次加载 240 s 内，每秒记录可用空间，每 30 s 用 `lsof` 看编译服务打开的文件：

| | M6 | M4 |
|---|---|---|
| 结果 | 240 s 时限到，未完成 | **80 s 加载成功** |
| 临时空间峰值 | 17.7 GB（仍在增长） | 1.3 GB |
| 编译服务 CPU | 约 200% | — |
| 大文件 | `/Library/Caches/com.apple.aned/26A434/ModelAssetsCache/<进程名>_unsigned/<哈希>/<哈希>/anecompiler.swap.*`，240 s 时 18.0 GB；另有 e5rt 缓存里 1.24 GB 的 `weights1.bin`（编码器权重副本，开始时写好后不变） | 没有交换文件 |

M6 的可用空间：前约 70 s 不变，之后约 3.5 GB/min 线性下降。【计时】
经 `whisperkit-cli` 加载时增长更快（8.6 min 内 63 → 7 GB，最后一分钟约 9 GB），被中止两次。【计时】

### 2.3 抓出编译器的输入（`whisper_capture.sh`，需 root）

编译开始 17 s 后，e5rt 缓存里出现 `H18G.bundle/main/main_ane/ane_mil_model/`，即 Core ML 转换后交给 ANE 编译器的模型：

- `model.mil`：3.9 MB，15,854 行、15,849 个运算：einsum 5,120、slice_by_index 4,480、softmax 2,560、mul 2,560、concat 672、conv 194、
  layer_norm 65、batch_norm 65、add 65、gelu 34。WhisperKit 为 ANE 改写了注意力：按头、按块拆成大量小 einsum。
  构建信息：coremltools 8.0（TorchScript 来源）、coremlc 3304.6.2。
- `weights1.bin`：1,273,974,400 字节。
- `options.plist`：只有 `h18g.EnableLowEffortCPAllocation = true`。

### 2.4 不经 Core ML 复现（`whisper_anecc.sh`）

anecc 在本进程里调用 `ANECCompile` 编译这份 `model.mil`：

| 目标 | 结果 | 用时 | 内存峰值 | 磁盘峰值 | HWX |
|---|---|---:|---:|---:|---:|
| h16g（M4） | 成功 | 41 s | 2.4 GB | 3.8 GB | 1.29 GB |
| h18（M6 单引擎，不生成双 ANE 程序） | 成功 | 41 s | 2.5 GB | 3.8 GB | 1.29 GB |
| h18g + `EnableLowEffortCPAllocation` | 可用空间低于 15 GB，中止 | 219 s | 5.9 GB | 44.2 GB | — |
| h18g | 同上 | 225 s | 6.1 GB | 44.3 GB | — |

- h18g 时 anecc 在**输出目录**里写 `anecompiler.swap.*`（约 15 GB/min；用 Core ML 时输出目录是 aned 的 ModelAssetsCache，所以交换文件出现在那里）；
  进程结束后交换文件被删除。【计时】
- Core ML 传的选项没有影响。【计时】
- anecc 比 Core ML 快 3–4 倍（推算约 6 min 对 10-02 实测的 24 min）：Core ML 下编译服务跑在 E 核上（defects B2）。

### 2.5 最小复现：截成前 N 层（`whisper_trunc.py`）

在第 N 层开头的 layer_norm 处截断，把它的输入接到原来的输出转换上（权重文件不变）：

| 编码器层数 | 1 | 2 | 4 | 8 | 16 | 32（推算） |
|---|---:|---:|---:|---:|---:|---:|
| 运算数 | 502 | 997 | 1,987 | 3,967 | 7,927 | 15,849 |
| h18g 用时 | 12 s | 21 s | 47 s | 88 s | 182 s | 约 6 min |
| h18g 磁盘峰值 | 2.7 GB | 4.7 GB | 10.0 GB | 19.4 GB | 39.0 GB | 约 78 GB |
| h18g 内存峰值 | 2.6 GB | 3.9 GB | 5.1 GB | 5.5 GB | 5.7 GB | — |
| h18 用时（磁盘均为 0） | 5 s | 6 s | 8 s | 13 s | 23 s | 41 s（实测） |

- h18g 的磁盘占用与层数成正比，每层约 2.4 GB；每层权重约 39 MB，约 60 倍。【计时】
- 编译最终能完成（L16 产出 673 MB 的 HWX），所以这是与层数成正比的资源缺陷，不是死循环。【计时】
- 内存在 5–6 GB 封顶，磁盘却一直增长：编译器有意把这部分数据放在文件上，不是内存不足时由系统换出。【推断】

## 3. 定位：调用栈与编译器选项

### 3.1 调用栈（`sample`，L4，h18g，5 s）

ANECompiler 的 C++ 符号没有剥掉，`sample` 能直接解析（只采自己的进程，SIP 开着也可以）。编译线程 1,456 个样本：

```
ANECProcedureCompiler::Compile                          （由 ZinTfExecutor::ProcedureLoop 并行调度各过程）
 └ ZinCompilerCoreClassic::CompileProcedure → RunMirBuilder → ZinMirBuilder
   └ ZinMirSplitSpatially                                       1420
     └ ZinMirSpatialSplitUtils::ExecuteGenericDAGMode           1359
       └ ZinMirSpatialSplitter::Tile                            1359
         └ ZinMirSpatialSplitter::TileWithGlobalRefinement      1289
           └ MirOpt::MergeConvolutions                          1289
             └ MirOpt::CreateMergedNEConvLayer                   521
```

栈顶（自身耗时）较多的函数：`ZinIrKernel::AddWeightsToSHA()` 146、`ZinIrWeight::GetWeightValueAsFloat` 123、`ConstWeightData::GetAt<half>` 67、
`_platform_memmove` 290、`ccdigest_process` / `CC_SHA256_Update` / `AccelerateCrypto_SHA256_compress` 合计约 180、
`perfmodel::NERasterization::RasterizeWorkUnit` 26、`details::ZinIrMappedDataBase_Impl::backing_` 14。【编译器】

解读：
- `ZinMirSplitSpatially` 是把每层的计算按空间切开、分给两个 ANE 的阶段。编译器的报错字符串 "Bonded networks require GenericDAG spatial split mode"
  说明双 ANE 程序必须走这一步；h18 单引擎不走，所以 41 s 就编完。
- 全局细化（`TileWithGlobalRefinement`）反复调用"合并卷积"（`MergeConvolutions`），每次合并生成新的 NE 卷积层（`CreateMergedNEConvLayer`），
  读出并复制参与合并的权重，再对新权重算 SHA-256（`AddWeightsToSHA`，推测用于权重去重或缓存键）。
- 新权重的存储是映射数据（`ZinIrMappedDataBase_Impl::backing_`），背后很可能就是 `anecompiler.swap.*`。【推断】
- WhisperKit 编码器每层有 160 个 einsum（5,120 / 32），在编译器里按卷积处理，所以每层的合并候选和权重副本都很多。【推断】

### 3.2 编译器选项

ANECompiler 的字符串里与这一步有关的有：`GlobalRefinementInSpatialSplit`（命令行写法 `global-refinement-in-spatial-split`）、
`SpatialSplitMode`（`GenericDAG`、`GenericDAGExperimental`、`GenericDAGMemory`）、`EnableAdvancedKernelRefinement`、
`EnableSpatialSplitInX`、`EnableCircularBufferInSpatialSplit`，以及 `anecompiler.swap.XXXXXXXXX`、`refine.json`、
"Weight size sanity checking failure in MergeConvolutions"、"Error: GlobalRefinement does not allow reset layers in the identified subgraphs"。【编译器】

L4，h18g，关掉全局细化（`tools/03_compile/whisper_anecc.sh` 的 `h18g_norefine` / `h18g_norefine_t`）：

| | 用时 | 磁盘峰值 | 内存峰值 | 权重段 | bonded 程序 | ANE0 TD 流 | ANE1 TD 流 |
|---|---:|---:|---:|---:|---|---:|---:|
| h18g 默认 | 47 s | 10.0 GB | 5.1 GB | 182.6 MB | ANE0、ANE1 各一次 kick | 0xa2480 | 0x80a400 |
| **顶层 `GlobalRefinementInSpatialSplit=false`** | **8 s** | **0** | 1.5 GB | 170.3 MB（= h18） | **只有 ANE0 一次 kick** | 0x80e400 | 无 |
| 同一选项放在 h18g 子字典 | 45 s | 10.0 GB | 5.1 GB | 182.6 MB | 同默认 | | |
| h18 | 8 s | 0 | 1.3 GB | 170.3 MB | 无 bonded 程序 | | |

- 选项只在顶层 flags 生效。【计时】
- 关掉后编译器找不到可行的拆分，"bonded"程序退化为只在 ANE0 上运行：全局细化是这个模型能拆到两个 ANE 的必要步骤，关掉它不是修复。【HWX】
- 默认 h18g 的拆分本身很不均衡：ANE1 的 TD 流是 ANE0 的约 13 倍（与 defects B8 的"ANE1 拿 56–59%"同方向，但程度大得多）。【HWX】

## 4. 问题的完整描述

| | 内容 |
|---|---|
| **缺陷 1（A3）** | 为 h18g 生成双 ANE 程序时，空间拆分的全局细化在反复合并卷积的过程中，把权重副本写入编译输出目录下的交换文件，用量与网络层数成正比（WhisperKit 编码器每层约 2.4 GB，约为该层权重的 60 倍），对 32 层编码器约 78 GB；用时约为单引擎目标的 8–9 倍（经 Core ML 再慢 3–4 倍）。编译器不检查剩余空间。 |
| **缺陷 2（A4）** | 经 Core ML 加载时，交换文件位于系统盘的 aned 缓存；客户端被结束后编译服务不停止，继续写到磁盘几乎写满；随后系统清除 ANE 编译缓存，所有模型下次加载都要重新编译。 |
| 触发条件 | 目标 h18g（M6 / H18G）；网络含大量可合并的卷积类运算（这里是被拆开的注意力 einsum）；一层编码器即可复现 |
| 不触发 | h18（单引擎）、h16g（M4）；关掉 `GlobalRefinementInSpatialSplit`（但随之失去双 ANE） |
| 影响 | WhisperKit 默认的编码器在 M6 上不能实际跑在 ANE 上；按"全 ANE"配置的应用首次启动会卡 20 分钟以上、写满小容量机型的磁盘 |
| 期望 | 全局细化不应把每个合并候选的权重副本都落盘（或应及时回收）；超过预算时放弃细化、退回单引擎程序并给出提示；编译前检查可用空间；客户端退出时停止编译 |

## 5. 对 B7 测评结论的修正

- "M6 每次调用 ANE 的开销大、被解码阶段约 3,200 次调用放大"：没有证据。同日 B1 的"M6 一次 1 张比 M4 慢"在正常状态下复现不出来
  （现在 M6 每次调用约 1.2 ms，M4 约 1.7 ms，见 B1 评测方法的复核）。M6 全 ANE 的 205 s 测于编译服务失控、磁盘写满的时段，不能代表 ANE 的速度。
- "新进程不复用编译缓存"：不成立，见 §2.1。
- "M6 的 ANE 编码器编译 20 多分钟、约 60 GB"：属实，原因是缺陷 1；视频里可说明为 macOS 27.0.1 的 ANE 编译器缺陷，不是硬件。
- 解码器在 M6 上 2.3 s 编完，"GPU 编码器 + ANE 解码器"组合可以正常测。

## 6. 未查明

- 交换文件里具体是什么（合并候选的权重副本、细化的中间图，还是两者都有），旧的副本是否被回收。可以在编译中读交换文件，或在
  `CreateMergedNEConvLayer` / `ZinIrMappedDataBase_Impl` 上设断点（lldb 附加到自己的 anecc 进程）。
- 是否只有"大量小 einsum"的网络触发：可用 `tools/common/chain.py` 构造只含 einsum、只含 1×1 卷积的链对照。
- 完整的 h18g 编码器能否编完（需要约 80 GB 可用空间），编完后在 M6 上的实际速度，以及拆分不均对速度的影响。
- 新版本 macOS / ANECompiler 是否已修复。
- 10-02 同日 B1 一次 1 张调用变慢（每次多约 3.3 ms），是否与失控的编译服务（满负荷、写磁盘）有关：时间上重合，未验证。
