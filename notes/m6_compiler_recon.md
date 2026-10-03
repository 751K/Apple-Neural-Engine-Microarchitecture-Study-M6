# M6 ANE 编译器摸底（2026-10-02，macOS 27.0.1，只读）

工具在 `report/tools/`：
- syms.c：在进程内解析 ANECompiler 的符号表，找未导出的函数。
- dump2.c：调用各代 `ZinIrHal*::GetParams()` 导出参数表。
- peek.c：读内存。
- cstr.c：搜 `__cstring` 段里的字符串。

原始数据在 `report/data/hal/`。

## 1. 硬件参数表（HAL）

- 编译器里有这些目标：
  - H11, H12, H13, H13g, H14, H14g, H14c, H15, H15g, H15c, H16, H16g, H16s, H16c, H17, H17a, H17g, H17s, H17c, H17d, **H18**, **H19**, **2026BaseLine**
  - 另有 M9, M11, M12, T0, T1, U1–U4
- **H18 只有一个，没有 g/s/c 变体**。而 ioreg 里两个 ANE 报的都是 h18g，所以运行时的 h18g 对应编译器的 H18。
- 每张表 0xa10 字节，是函数内的静态变量。调用时可以传一个假的 `this`，直接返回表的地址。
- **和书（Bryngelson）的布局不同**：书里的标量字段整体往后挪了 0x20。例如 2 MiB 门槛在 0x1d8（书上是 0x1b8），256 KiB 在 0x210（书上 0x1f0），16 MiB 在 0x230（书上 0x210）。能力字节的位置也变了，书里的偏移不能直接用。
- **同一代的各个变体（例如 H16 / H16g / H16s / H16c），表的内容完全一样**，只有开头的名字指针和几个 vector 的地址不同，vector 里的内容也一样。所以核数不在这张表里。
- 0x8 处的 u32：H16 = 7，H17 = 9，**H18 = 10**，H19 和 2026BaseLine = 11。疑似代际或 TD 版本序号。
- H17s 和 H18 之间有 49 处不同（偏移 0x528–0x8a0）。vector 0x6a8 多了一个元素 6；vector 0x8a0 从 13 项变成 21 项。这些字段的含义待查。

## 2. Bonded（双 ANE 绑定）——编译器已完整支持

- 编译器参数（`ZinIrCompilerParameters`）：
  - EnableBondedNetworks / DisableBondedNetworks
  - GenerateBondedProcedures / GenerateNonbondedProcedures
  - ForceAllToANE0OnBondedProcedure
  - EnableWorkStealingForBondedNetworks
  - EnableForcedMaximalBondedSplit
  - EnableInterAneSameKernelReadAnalysis
  - ForceTMWaitForInterAneDependencies
  - DisablePerDmaRdtidForBondedNetworks
  - BondedNetworksTestAssignment（disabled / random / random_non_parallel）
- 拆图相关的类：
  - BondedSplitSubgraphIdentification：按维度拆子图，考虑 L2 压力
  - ZinBondedAne::ZinMirFindInherentParallelism：找图中天然可并行的分支，支持 work stealing
  - LatencyInfo::ComputeSplitLatencyBonded
  - CodegenAsyncGroupsForBonded
  - kBondedSharedBSSKey
- 字符串中的关键信息：
  - "Multi-flavor macho"：**同一个编译产物里同时有 `__bonded`（并发 2）和 `__nonbonded`（并发 1）两套过程**，运行时任选其一。
  - "Unsupported concurrency … only supports concurrency values of 1 (non-bonded) or 2 (bonded)"：**bonded 就是两个 ANE 一起跑**。
  - "Network count for all ANEs must be equal when bonded."
  - "Bonded networks require GenericDAG spatial split mode"
  - 编译选项：`--fdisable-bonded-networks=true`、`--enable-nonbonded-networks=false`、`--use-extended-macho-format`
  - McacheHiBondedKernelReadDSID：两个 ANE 共享读同一份权重时用的系统缓存（SLC）标签。
- 运行时框架 AppleNeuralEngine 里有 **`kANEFDisableBondedNetworksKey`**，是一个可以从外部传入的编译选项。
- 多 die 的一套（DeviceMesh、SPMD、CollectiveCommunication、CCDMA）也在。并区分 InterDie 和 IntraDie；M6 的两个 ANE 在同一块 die 上（ioreg 里 die-id 都是 0）。

## 3. TD 版本

- 编译器里有 ZinAneTdHw_v4…v20，以及 **v24、v26、v28、v31、v36**（书里最多到 v20）。M6（h18g）用 v24，h18 用 v20；v26 = M12，v28 / v31 / v36 暂无对外目标（hwx_h18g.md §11.3）。
- H18 用哪个版本待查。

## 4. 推论（待实测验证）

1. Core ML 在 M6 上编译出的模型，很可能默认就包含 bonded 过程，**单个模型就能同时用两个 ANE**。
   - 这能解释为什么 M6 的 INT8 实测有 85–91 TOPS，约为 M4（约 38）的 2.3 倍。
2. 我们的 fast3（LLM decode）可能也在跑 bonded。
   - 验证方法：用 `kANEFDisableBondedNetworksKey` 关掉 bonded 再编译，比较速度；同时用 anemon 看两个 ANE 是否都在忙。
