# Core ML 的算子分派：哪些算子会退回 CPU，分段器怎么决定

- 日期：2026-10-05
- 环境：M4（Mac16,12，h16g，16 GB），macOS 27.0.1（26A434）；coremltools 9.0，ML Program，最低部署目标 macOS 15，FP16，
  `MLComputeUnits.cpuAndNeuralEngine`。只测了 M4。M6 的 ANE 支持面与代价常数可能不同，待测。
- 工具：`tools/03_compile/opd_arch.sh`（h16g / h18g 直接编译对比）、`topk_ctx.py` 与 `tools/common/predict.swift`（topk 计时）、
  `tools/03_compile/opdispatch_gen.py`（单算子模型；`--ctx` 前后各包两层卷积）、`tools/common/computeplan.swift`
  （公开 API `MLComputePlan`：每个运算的支持设备、首选设备）、`tools/03_compile/opdispatch_run.sh`（逐模型串行跑，带内存看门狗）、
  `opd_all.sh` / `opd_ana.sh` / `opd_sw2.sh`（流水线；每个模型独立 `CFFIXED_USER_HOME`，收集分段器写出的 `analytics.mil`）、
  `tools/03_compile/opdispatch_fit.py`（解析 `analytics.mil`，用最短路径模型复现分段）。
- 数据：`data/03_compile/opdispatch/`：`plan_*.tsv`（MLComputePlan 输出）、`ana/{iso,ctx}/<模型>.mil`（分段器分析文件，
  每个运算的后端支持、各后端估计耗时、选中后端）、`sw2_mem.tsv`（边界扫描的编译时间与 ANECompilerService 峰值内存）。
  Espresso 的字符串表在 `private/data/03_compile/opdispatch/`（Apple 内部内容，不入库）。
- 注意：`plan_iso_cpune.tsv` 里 `sw_conv_k16*` 等几行标着 OOM，是看门狗把 ANECompilerService 的内存算进去后杀掉了 computeplan，
  这些模型的结论以 `ana/iso/sw_*.mil` 为准（§3.3）。

## 0. 结论（报告用）

1. **决定"上不上 ANE"的是 Espresso 里 E5 编译器的分段器，不是 ANE 编译器本身。** ANECompiler 导出 56 个 `ANECValidate*Layer`，
   Espresso 用到其中 24 个做逐层校验；在此之上，分段器按代价模型给每个运算选后端（ane / bnns / classic_cpu），再按最短路径把图切成段。【编译器】
2. **分段器的规则可以用一个很简单的模型完全复现。** 每个运算取分段器自己给出的各后端估计耗时；**一段 ANE 固定加 0.125 ms 启动，
   相邻两段后端不同再加 0.125 ms 切换，图的输出落在 ANE 上再加 0.125 ms**。按这个模型求最短路径，482 个模型中 440 个与实际选择完全一致，
   41 个是代价相同的平局，只有 1 个不一致（§2.3）。这些常数在所有模型里都一样（0x1p-3 ms）。【编译器】
3. **所以小模型、小段几乎都会被放到 CPU。** 整个图放 ANE 要付约 0.25 ms，图中间夹一段 ANE 要付 0.375 ms；ANE 只有在省下的估计耗时超过这些常数时才会被选。
   例：1×64×32×32 的 3×3 卷积 ANE 估计 4.7 µs、CPU 100 µs，单独一层（运算本身只省 0.095 ms）放 CPU，四层（省约 0.38 ms，超过 0.25 ms）才上 ANE；两层卷积夹一个归约，
   整个图都放到 CPU。【编译器】
4. **ANE 不支持的东西主要是四类（§3）：** ① 任何 int32 张量（int32 的加乘、matmul、cast 到/自 int32、argmax/argsort 的 int32 输出、
   动态索引 gather/scatter 的整套索引预处理）；② 部分数学函数（asin、acos、tan、sinh、cosh、atanh、mod、reduce_prod、cumsum）；
   ③ 序列和结构类运算（lstm / gru / rnn、band_part、one_hot、non_zero、range_1d、random_normal、sliding_windows、crop_resize、动态起点的 slice）；
   ④ 尺寸上限：任一维 > 65536，matmul 内积维 > 32768，卷积核宽 > 15（高可到 31，方核到 16×16），max_pool 核宽 > 8。【编译器】
5. **常见的 Transformer / CNN 算子都能上 ANE：** conv（含 1D/3D、分组、空洞、转置、动态权重）、matmul（含批量、广播、动态）、
   scaled_dot_product_attention、layer_norm、instance_norm、softmax、gelu 三种、topk、静态索引 gather、reduce（除 prod）、
   各种 resize / upsample、pad（含 reflect / replicate）、pixel shuffle、transpose、concat。FP32 输入会被插入 cast 后上 ANE。【编译器】
6. **单是查分派也会触发完整的 ANE 编译，可能非常重。** 对一层 16×16 卷积（64 通道、32×32）调用 `MLComputePlan.load`，
   ANECompilerService 用了 212–229 s，峰值 11.7 GB；13×13 只要 2–23 s、0.1–0.3 GB（§3.3）。【计时】

7. **尺寸上限在 M4 和 M6 上相同。** 在 M4 上用 anecc 直接调用 ANECCompile，分别以 h16g（M4）和 h18g（M6）为目标编译 67 个边界/对照模型，
   两个目标的成败逐个相同（只有 topk 例外，见下条）；h16g 的成败又与 Core ML 在 M4 上的判断一致，说明 Core ML 的上限就来自 ANE 编译器（§3.4）。
   int32、lstm、cumsum、asin、动态 gather、sliding_windows 在两个目标上也都编不过。M6 的估计耗时和分段结果仍需在 M6 上测。【编译器】
8. **topk 在 M4 上被放进 ANE，但很慢，分段器把它低估了约 200 倍。** 前后各 4 层 256 通道卷积、中间一个 topk 的模型，Core ML 在 M4 上整图放 ANE，
   比同形状对照多 6.0 ms（沿宽，k=4）和 10.1 ms（沿通道，k=256），而分段器的估计只有 0.03 和 0.06 ms；结果整图放 ANE 比只用 CPU 还慢
   （8.00 对 6.23 ms，12.59 对 11.08 ms）。直接编译单个 topk 时，h16g 报 "Validation for RCAS failed / Invalid TD"，h18g 能编过（§3.5）。【计时】【编译器】

## 1. 方法

- 每个被测算子生成两个模型：**单独**（只有这一个运算，看"支持设备"）和**上下文**（FP16 的 3/4 维输入、输出前后各包两层
  3×3 卷积 + ReLU 或 linear + ReLU，看放进网络后的"首选设备"）。另有 46+22 个边界扫描模型（`sw_*`）。
- 读设备分配用公开 API `MLComputePlan`；后来发现分段器把完整决策写在 E5 缓存的 `analytics.mil` 里，
  于是每个模型用独立的 `CFFIXED_USER_HOME` 跑一次，避免命中缓存，再把 `analytics.mil` 拷出来。以 `analytics.mil` 为主要数据。
- 全部在第二台 M4 上串行跑（一次一个模型）。

## 2. 分段器

### 2.1 代码位置（静态）

- Espresso 导入 ANECompiler 的 `ANECValidate{Conv,MatrixMult,Pool,Softmax,Reduction,Reshape,Transpose,Gather,TopK,Sort,NMS,Resize,
  Resample,Pad,PixelShuffle,PixelUnshuffle,Concat,Tile,CropResize,AffineTransform,CrossCorrelation,DynamicSlice,GlobalArgMinMax}Layer`
  和 `ANECUnitValidatorCreate`、`ANECValidateNetworkCreate`。没导入的有 SDPA、LayerNorm、InstanceNorm、ElementWise、Neuron 等，
  这些运算仍然能上 ANE，判断走别的路径（未查）。
- 字符串表里有大量逐算子的拒绝原因，例如 "Only Channelwise or Spatial ArgMax/Min is supported on ANE"、
  "Constnt Pad fill mode with non-zero values is not supported on ANE"、"NonMaximumSuppression kernel cannot currently run on ANE
  with more than 2048 input boxes"、"Inner product with H/W > 1 not allowed on ANE"、"3d space_to_batch is not supported on ANE"、
  "The network bounces between the ANE and GPU/CPU ... too often"。
- 分段：`Segmenter.mil`、"Segmenter to use in E5 compiler (linear,graph,coarse)"、"Segmenter failed: invalid shortest path generated"。
  代价：`Espresso::AOT::EstimatorMILDecisionTree::EstimateCost`，特征为 gFlopCnt、totalMB、mbKernel、opsPerByte、输入输出尺寸、
  通道、核尺寸、空洞、workUnitEfficiency16、isL2Resident、is3DConv（"per MIL operator decision trees"）。
- 打开代价日志：`EstimateCost` 用 `E5Common::Utils::IsDefaultsWritePresent` 查全局 defaults（NSGlobalDomain）的
  `espresso.e5compiler.log_cost_model`。`defaults write -g espresso.e5compiler.log_cost_model -bool YES` 后，
  os_log（子系统 com.apple.espresso）每个运算打一行 `[CostModelFeature]`，含 GFLOP/s、GBP/s、Runtime、UsedDTree、Bound:Compute/Memory；
  运算名是 `<private>`，要开私有数据才能看到。`analytics.mil` 已含同样的估计，所以没再深入。用完已删除这个 defaults。

### 2.2 analytics.mil

位置：`~/Library/Caches/<进程名>/com.apple.e5rt.e5bundlecache/<系统版本>/<哈希>/<哈希>.bundle/H16G.bundle/analytics.mil`。
内容是分段前的 MIL 程序，每个运算附 `BackendSupport`、`EstimatedRuntime`（ms）、`SelectedBackend`；函数头附图级常数：
`Launch_ane_ms = 0.125`，其余后端 `Launch_*_ms = 0`；所有 `Src_<a>_Dest_<b>_ms = 0.125`。同目录还有分段后的 `main/main_ane`、
`main/main_classic_cpu` 等。

代表性估计（M4，单算子，µs）：

| 运算 | ANE | BNNS (CPU) |
|---|---|---|
| conv 3×3，64→64，32×32 | 4.67 | 100.06 |
| conv 1×1，同上 | 1.17 | 21.62 |
| matmul 1×128×256 · 256×128 | 2.24 | 11.12 |
| upsample_bilinear ×2 | 3.31 | 499.64 |
| concat（通道） | 2.62 | 22.79 |
| sdpa 1×8×128×64 | 7.18 | 8.62 |
| softmax / layer_norm（64×32×32） | 3.59 | 4.31 |
| relu | 2.62 | 2.62 |
| transpose（交换 H、W） | 3.81 | 3.00 |

访存为主的运算两边只差约 17%（ANE / CPU = 0.83），切换代价 0.125 ms 相当于几十个这样的运算，所以这类运算单独出现时总是留在 CPU 段。

### 2.3 复现

模型：每个运算按文件顺序，状态为后端；进入 ANE 段加 0.125 ms，换后端加 0.125 ms，最后一段在 ANE 再加 0.125 ms，输入不计；求最小总代价。
`opdispatch_fit.py fit` 的结果：完全一致 440，平局 41（多为最后一个 ReLU 在 ANE、CPU 估计相同，实际随机落在一边），不一致 1
（`ctx/band_part`：band_part 只能在 CPU，实际在它两侧各开一段 ANE，代价 0.658 ms，比模型的最优解 0.640 ms 高；可能是多输入图的链式近似不准）。

推论：
- 一段 ANE 在图首或图尾要省 ≥ 0.25 ms，在图中间要省 ≥ 0.375 ms 才会被开出来。
- 夹在 ANE 段中间的一个 CPU 运算（如 int32 的 argmax）会让分段器在"切两次（+0.25 ms）"和"整段放 CPU"之间二选一；网络不大时会整段放 CPU。
- 上下文实验里很多"全图放 CPU"的结果正是这个原因：前后各两层 64 通道卷积在 CPU 上估计约 0.2 ms，不够付 ANE 的固定代价。
  这不说明那个算子本身不能上 ANE。

## 3. 支持面（单算子，`analytics.mil` 的 BackendSupport）

### 3.1 不支持 ANE（只有 bnns / classic_cpu）

| 类别 | 运算 |
|---|---|
| int32 | add / mul / matmul（int32）、cast fp16↔int32、cast→int8、reduce_argmax（输出 int32）、argsort、动态索引 gather / gather_nd / embedding 的索引预处理（cast、greater_equal、add、select，gather 本身也跟着上 CPU）、gather_along_axis 的索引 cast |
| 数学函数 | asin、acos、tan、sinh、cosh、atanh、mod、reduce_prod、cumsum |
| 序列 / 结构 | lstm、gru、rnn、band_part、one_hot、non_zero、range_1d、random_normal、sliding_windows、crop_resize、slice_by_size（动态起点）、scatter、scatter_along_axis |
| 尺寸 | 任一维 65537（65536 可以）；matmul 内积维 40000（32768 可以）；conv 核 1×16、32×1、17×17；max_pool 核 9×9、1×9 |

GPU 能跑上表大部分（`plan_iso_all.tsv`），crop_resize、non_zero、range_1d、sliding_windows 只能 CPU。秩：Core ML 本身只支持 ≤ 5 维（coremltools 转换即报错），5 维可上 ANE。

### 3.2 支持 ANE

166 个单算子模型的全部运算都支持 ANE，包括：所有逐元素一元（relu、sigmoid、tanh、silu、gelu×3、softplus、erf、exp、exp2、log、sqrt、rsqrt、
inverse、sin、cos、atan、floor、ceil、round、sign、square、clip、elu、prelu、leaky_relu、hard_sigmoid…）；二元及各种广播（add、sub、mul、
real_div、floor_div、pow、maximum、minimum、比较、select、logical_and）；conv 全家；matmul / linear / sdpa（含 mask）；pool（avg、max、l2、3D）；
softmax（任一轴，含 batch 轴）、layer_norm（各种轴）、instance_norm、batch_norm、l2_norm、lrn；reduce（sum、mean、max、min、l1、l2、log_sum、
log_sum_exp、sum_square）；reshape、transpose（含 5 维）、concat（含 interleave）、split、stack、slice（含步长 2）、reverse、tile、pad（constant、
reflect、replicate、通道维）、space/depth/batch 互换、pixel (un)shuffle；upsample / resize（nearest、bilinear、align_corners、分数倍、缩小）、
affine、resample；静态索引 gather；topk（含 k=40、32000 宽）；quantize→dequantize（int8）。

### 3.3 边界扫描（`sw_*`）

| 项目 | 支持 | 不支持 |
|---|---|---|
| 方形卷积核 K×K（same） | ≤ 16 | 17 |
| 横向卷积核 1×K（same 或 valid） | ≤ 15 | 16 |
| 纵向卷积核 K×1 | ≤ 31 | 32 |
| max_pool K×K | ≤ 8 | 9（valid 也不行） |
| max_pool 1×K / K×1 | 9×1 可以 | 1×9 不行 |
| avg_pool K×K | ≤ 14（已测最大） | — |
| 卷积步长 | 2–8 全可以 | — |
| 分组卷积 | 2–64 全可以 | — |
| matmul 内积维 | ≤ 32768 | 40000、49152、65535、65536 |
| 张量单维 | ≤ 65536 | 65537 |
| batch 维 | 2–64 可以 | — |

方核 16×16 支持而 1×16 不支持，说明宽度上限（15）对方核有特殊处理，可能是先拆分再编译。这正好对应编译代价的突变：

| 模型 | MLComputePlan.load 耗时 | ANECompilerService 峰值 RSS |
|---|---|---|
| conv 13×13 | 2 s / 23 s（两次） | 308 / 92 MB |
| conv 16×16 | 229 s / 212 s | 11.7 GB / 11.7 GB |
| 其他 sw_* | ≤ 1 s | ≤ 14 MB |

（一次跑满 11.7 GB 在 16 GB 机器上已接近上限；查分派本身就会做完整的 ANE 编译。）

### 3.4 h16g 与 h18g 的编译器上限（`arch_h16g_h18g.tsv`）

方法：`tools/03_compile/opd_arch.sh`，把单算子模型用 `ct.utils.compile_model` 转成 mlmodelc，再用 `tools/common/anecc.m` 直接调用 ANECCompile，
目标分别为 h16g、h18g；每个模型一个进程、串行，看门狗 8 GB。返回 0 且有 model.hwx 记为成功。

| 项目 | h16g | h18g |
|---|---|---|
| 方核 K×K | ≤ 15 通过；17 失败；16 编译超过 8 GB 被杀 | 同左（16 在 8.4 GB 被杀） |
| 1×K | ≤ 15；16、17、24、32、64 失败 | 同左 |
| K×1 | ≤ 31；32、64 失败 | 同左 |
| max_pool | ≤ 8；9（same / valid）、1×9、13、14、15 失败；9×1 通过 | 同左 |
| avg_pool 13、14 | 通过 | 通过 |
| matmul 内积维 | ≤ 32768；40000 起失败 | 同左 |
| 单维 65536 / 65537 | 通过 / 失败 | 同左 |
| int32 add、argmax、lstm、cumsum、asin、动态 gather、sliding_windows | 失败 | 失败 |
| conv3x3、sdpa、layer_norm | 通过 | 通过 |
| **topk（1×64×32×32，k=4，沿宽）** | **失败（rc=22，RCAS 校验）** | **通过** |

h18g 的 HWX 普遍是 h16g 的约 2 倍大（双 ANE 两份程序）。

### 3.5 topk

- Core ML 在 M4 上把 topk 标为 ANE 可用（BackendSupport 含 ane），前后各接 4 层 256 通道 3×3 卷积（1×256×64×64）时整图一个 ANE 段，编译成功、预测正常。
  单独一个 topk 时直接走 ANECCompile 的 h16g 会失败（日志：`hw.l2_config.ane_l2_config.source1_cfg.alias_conv_rslt`、
  "Validation for RCAS failed"、"Invalid TD exists"），可见 Core ML 的路径与直接编译单个 MIL 不同，或失败只在这种输入直通输出的形状上出现。
- 计时（`topk_timing.txt`，20 次中位数，ms）：

| 模型 | cpuAndNeuralEngine | cpuOnly |
|---|---|---|
| 对照（slice 到宽 4） | 2.01 | 1.72 |
| topk k=4，沿宽 | 8.00 | 6.23 |
| 对照（relu） | 2.48 | 9.91 |
| topk k=256，沿通道 | 12.59 | 11.08 |

  topk 在 ANE 上多花约 6.0 / 10.1 ms，分段器估计 0.0305 / 0.0574 ms（ane）、0.0366 / 0.0689 ms（bnns），即把 topk 当作普通访存型运算。
  （宽 4 的对照在 CPU 上只要 1.72 ms，比 4 层 64×64 卷积的计算量所需少得多，CPU 路径可能裁掉了不影响输出的列；不影响 topk 的结论。）
- TD 跟踪里 h18g 的 topk 走 RCAS（hwx_h18g.md）；M4 上是否也走 RCAS、为什么慢，未查。

## 4. 未完成 / 疑点

- 尺寸上限已用 h18g 目标在 M4 上核对（§3.4）。M6 上的估计耗时、分段结果和 0.125 ms 常数需要在 M6 上复测：带着 `opd_all.sh`、`opd_ana.sh` 跑一遍即可；topk 在 M6 上是否同样慢也要测（`topk_ctx.py`、`predict.swift`）。
- `MLComputePlan` 的首选设备与 `analytics.mil` 的 SelectedBackend 逐运算一致（2187 个运算，0 处不同）；运行时是否严格按这个分配（例如 ANE 编译失败时退回）没测。
- 分段器的 `EstimatedRuntime` 与实测的关系没核对（compute_array.md H53b 是 ANE 编译器内部的另一套估计）。
- 决策树本身（特征 → 耗时）没有导出；`[CostModelFeature]` 日志需要私有数据开关（要 sudo）。
- 16×16 卷积为何编译 200 s、11.7 GB，没拆。
- nms 在这版 coremltools / 部署目标下生成的模型 Core ML 解析失败，未测；shape 运算被折叠成 identity，无分析文件。
