# 疑似缺陷与不合理的行为（M6）

- 日期：2026-10-02
- 环境：M6（T8152 / h18g），macOS 27.0.1（构建 26A434），ANE 编译器 `zin_ane_compiler v10.26.6`，Core ML 公开接口。
- 分三类：
  - **A 疑似 bug**：崩溃、卡死、静默出错，显然不是设计意图；
  - **B 性能问题 / 有争议的策略**：功能正常，但代价大，或者调用方无法控制；
  - **C 未写进文档的行为**：不算缺陷，但开发者很可能踩到。
- 每条都给出复现方式和出处，可以直接整理成 Feedback Assistant 报告。

## A 疑似 bug

### A1 双 ANE（h18g）编译路径在 387 层起栈溢出崩溃

- **现象**：64 通道、宽 1024 的 1×1 卷积链（共享权重），用 `ANECCompile` 编译为 h18g 时，387、388、400、512 层都崩溃，返回码 138（SIGBUS）；同一个模型编为 h16g（M4）、h18（单引擎）到 512 层都正常。
- **原因**：崩溃报告显示是线程栈的保护页被访问，也就是栈溢出。调用栈是 `ZinIrOpLayerGraphScheduler::Schedule` 的逐层递归（每层网络一层递归），在只有 h18g 才执行的 `ZinIrParallelExecutionOpportunityFinder::FindIntraANEParallelism` → `FindAllAttentionBranchesInRegion` → `ZinIrNgraph::TopologicalSortImpl` 里耗尽栈。
- **影响**：M6 上可用的图深度只有 386 层（M4 同一系统、同一模型至少 448 层）。这是编译器的递归实现问题，不是硬件限制。
- **复现**：`tools/common/chain.py` 生成 `k1_c64_h1w1024_L387`，`tools/common/anecc.m` 以 h18g 编译。
- **出处**：scheduling.md D5、compile_cost.md §4；数据 `data/03_compile/h9_depth_compile.txt`。

### A2 编译服务崩溃后，Core ML 加载的结果不确定，可能永久卡住

- **现象**（与 A1 同一组模型，经 Core ML 加载）：
  - 388、400–1024 层：**静默退回 CPU**，不报错，慢 100 倍以上（26.9–70 ms，对比 ANE 约 0.3 ms）；
  - 387、392 层：**加载永久卡住**，调用进程等了 11 分钟以上，CPU 为 0，编译服务空闲，既不报错也不退回 CPU。
- **连带问题**：编译服务崩溃或被结束后，aned 一直等待它的回复，**之后所有进程的 ANE 加载都被堵住**，只有 `sudo killall aned` 才能恢复。实验中出现过两次（一次编译服务单核满载约 2 小时，见 B1）。
- **期望**：编译失败时返回错误，或者确定性地退回 CPU 并给出提示；aned 应该对编译服务设超时。
- **出处**：scheduling.md D5；repro_plan.md H24。

### A3 双 ANE（h18g）空间拆分的全局细化把权重副本写成交换文件，用量与层数成正比（Whisper 编码器约 78 GB）

- **现象**：WhisperKit 的 Whisper large-v3-turbo 编码器（Core ML 转换后 15,849 个运算，其中 5,120 个 einsum）编译为 h18g 时，
  编译器在输出目录写 `anecompiler.swap.*`，每个编码器层约 2.4 GB（约为该层权重的 60 倍），32 层约 78 GB；用时为单引擎 h18 的 8–9 倍。
  h18、h16g 同一模型 41 s、磁盘 3.8 GB。截到一层即可复现（h18g 12 s、2.7 GB；h18 5 s、0）。经 Core ML 加载时要 20 分钟以上，并写满磁盘。
- **位置**：调用栈 97% 在 `ZinMirSplitSpatially → ZinMirSpatialSplitter::TileWithGlobalRefinement → MirOpt::MergeConvolutions →
  MirOpt::CreateMergedNEConvLayer`（复制权重、`ZinIrKernel::AddWeightsToSHA`）。顶层选项 `GlobalRefinementInSpatialSplit=false`
  让编译回到 8 s、磁盘 0，但双 ANE 程序退化为只用 ANE0。
- **期望**：细化不应把每个合并候选的权重副本都落盘，或应及时回收；超出预算时放弃细化、退回单引擎程序；编译前检查可用空间。
- **复现**：`tools/03_compile/whisper_capture.sh` 抓出 Core ML 交给编译器的模型，`whisper_trunc.py` 截层，`whisper_anecc.sh` 以 h18g 编译。
- **出处**：whisper_compile.md；数据 `data/03_compile/whisper_compile/`。

### A4 客户端退出后编译服务继续运行，并把系统盘写满，随后 ANE 编译缓存被清除

- **现象**：经 Core ML 加载 A3 的模型时，结束加载进程（或 `whisperkit-cli`）后，`ANECompilerService` 仍满负荷运行、继续写
  `/Library/Caches/com.apple.aned/<build>/ModelAssetsCache/<进程名>_unsigned/…/anecompiler.swap.*`；2026-10-02 写到系统盘只剩 121 MB，
  系统随之清除 ANE 编译缓存，所有模型下次加载都要重新编译。只能 `sudo killall -9 ANECompilerService`，交换文件随之释放。
- **期望**：客户端取消或退出时停止编译；aned 对编译的磁盘用量设上限。与 A2（aned 一直等编译服务）同属"编译服务没有超时和预算"。
- **出处**：whisper_compile.md §1、§2.2。

## B 性能问题 / 有争议的策略

### B1 双 ANE 版本的编译时间随逐元素层数超线性增长

- **现象**：`y = y·u + u` 重复 n 步，h18 单引擎版本线性增长（256 步 0.39 s），h18g 双 ANE 版本约按步数的 3.5–3.8 次方增长：256 步（512 个逐元素层）要 178.6 s，是单引擎的 458 倍。经 Core ML 首次加载（叠加 B2）要 8 分钟以上。实验中出现过编译服务单核满载约 2 小时的情况。
- **推测**：双 ANE 专属的步骤（`BondedSplitSubgraphIdentification`、`ZinMirFindInherentParallelism`、`ComputeSplitLatencyBonded` 等）中有对层或层对的超线性搜索，主要由逐元素（PE）层触发；卷积链几乎不受影响。
- **出处**：compile_cost.md §1–3。

### B2 Core ML 首次加载时，编译只在能效核（E 核）上运行，慢 2.7 倍

- **现象**：同一模型，进程内直接编译 12.65 s（单线程，各核忙碌时间未记录，推断在 S 核上）；经 Core ML 首次加载，编译用时 34.05 s，期间 6 个 E 核合计忙约 30 s，2 个 S 核合计 0.2 s，4 个 P 核为 0。
- **机制**：编译服务由 `ProcessType = Adaptive` 的守护进程 aned 派生；客户端 QoS 会被传递（user-interactive 33 → aned 收到 33 → 编译线程用 25），但线程仍只上 E 核。客户端设为 background 时更慢（98.8 s）。
- **争议点**：不是实现错误，是调度策略，可能出于功耗和发热考虑。但 QoS 25 在普通 App 里通常会上 S 核或 P 核，这里客户端无法加速；在 M6 上又和 B1 叠加，大模型首次加载要多等几分钟。
- **出处**：compile_cost.md §3.1；repro_plan.md H35。

### B3 同一个编译后的程序，在一个进程里严格串行

- **现象**：同一个模型在一个进程里开 2 或 4 个线程（无论共用还是各自加载 MLModel 对象），吞吐都和单线程相同，全部排在 ANE0 上，ANE1 闲置。换成两个不同的模型，或者放到两个进程里，就能分到两个 ANE（1.8 倍左右）。
- **影响**：M6 有两个 ANE，但"一个服务进程 + 多线程跑同一个模型"这种常见用法只能用到一个。
- **出处**：scheduling.md H15。

### B4 1×1 卷积链的 W8A8：激活每层都经过 DRAM，双引擎下与 FP16 持平

- **现象**：共享权重的 1×1 卷积链，FP16 版本的 DRAM 读接近 0（激活留在片上），W8A8 版本每个 ANE 持续读 22–28 GB/s，正好是每层激活的大小。单引擎 W8A8 是 FP16 的 1.34 倍，双引擎时只有 0.97 倍；计算更密的 3×3 卷积上则正好 2 倍。
- **推测**：编译器为 W8A8 链中每层的量化 / 反量化安排了经过 DRAM 的路径，没有像 FP16 那样把激活留在片上。属于编译器的优化缺口（待确认是否为硬件限制）。
- **出处**：compute_array.md H10。

### B5 ANE 任务变长时，主机侧唤醒开销逐步增加（最多约 +195 µs）

- **现象**：固件时间戳显示 ANE 本身没有变慢，多出来的时间全在任务结束后的主机侧（驱动完成处理和用户线程唤醒都慢约 1.5 倍）。原因是等待期间 CPU 进入了更深的空闲状态。占满 CPU 后台阶消失。曾被误读为"48 MiB 权重切换"。
- **范围**：逐步加深，不只是一个台阶。ANE 任务从约 230 µs 增加到约 400 µs 时，任务结束后的主机侧开销从约 160 µs 增加到约 355 µs（驱动完成处理 3.1 倍、用户线程唤醒 2.5 倍），之后不再增加（compute_array.md B6b）。
- **性质**：是操作系统电源管理与 ANE 驱动交互的结果，不是 ANE 本身的问题。对调用时长 0.4–1 ms 的模型，主机侧开销占调用时间的 20–40%。
- **出处**：memory.md C2j。

### B6 编译器性能模型的最高 NE 频率与实际不符

- **现象**：编译器为 h18g 使用的 `Soc2026BaseLine` 频率表最高 2.508 GHz，而硬件满载实测约 2.58 GHz（设备树 `voltage-states8/29` 的最高档）。两张表的后 8 档都不同。
- **影响**：编译器的性能模型（切分、调度决策）用的频率比实际低约 3%。影响多大不清楚，可能只是性能模型的保守取值。
- **出处**：power.md §6.5。

### B7 Core ML 在某些深度把最后一个运算悄悄放到 CPU 上

- **现象**：1×1 卷积 + relu 链（512 通道，32×32），只有 32 层和 34 层的执行计划被拆成 `AneInference → Cast → CpuInference(relu) → Cast`，最后一个 relu 在 CPU 上算，前后各做一次 1–2 MB 的 fp16 / fp32 转换。每次调用慢约 100 µs（约 12%），P 核的 CPU 占用翻倍；30 层和 36 层都完全在 ANE 上。
- **问题**：整个图用 ANE 编译器直接编译没有问题，拆分没有收益，而且是静默发生的，只能从缓存里的执行计划（`main_classic_cpu` 段）或者采样中发现。划分理由在系统日志中不可见。
- **出处**：compute_array.md B6b。

### B8 切块时双 ANE 的工作划分不均（ANE1 拿 56–59%，耗时比均分长 12.5–19%，吞吐降 11–16%）

- **现象**：中间张量需要切块时，编译器把更多的块分给 ANE1（W12288：44% / 56%；W8192：41% / 59%）。双 ANE 调用的耗时由 ANE1 决定，比均分慢约 12.5–19%。不切块时两边均衡。
- **证据**：编译产物里 ANE1 的 TD 数和列数都更多（8 层模型 56 对 42 个 TD）；固件时间戳测得的 ANE1 / ANE0 时间比（1.29、1.47）与列数比（1.29、1.46）一致；不同宽度的总耗时比例也与预测一致。
- **原因**：双 ANE 划分沿用不分引擎时的切块网格，只在块边界上把块列表分成两组；块数为奇数时多出的一块给 ANE1。块数为偶数时完全均衡：W14336（8 块）比 W12288（7 块）多 17% 的计算量，耗时反而少 2%。
- **建议**：编译器应在双 ANE 模式下按每个引擎重新切块，或者在块数为奇数时把最后一块再对半分。
- **更极端的一例（2026-10-03）**：1×1、2048 通道、32² 的 W8A8 链（每层 3 块 TD 组），bonded 程序 ANE0 / ANE1 的 exe_cycles 之和为 434 / 880，即 1 : 2；W8A8 只比 FP16 快 1.21 倍，而均衡的形状快 1.76–1.87 倍（compute_array.md H51 第 3 步）。
- **出处**：memory.md C1c。

### B9 双 ANE 下读权重受限的层被按行切分，第二个 ANE 不带来加速

- **现象**：16×32、256 通道的 1×9 / 1×10 / 1×11 / 1×15 卷积链（核宽 9–15 被改写为步长 2，权重约翻倍，每层要从共享带宽读入）在双 ANE 下的每层耗时，等于单 ANE 处理同样行数时的 2 倍。两个 ANE 完全并行，但整体吞吐与单 ANE 相同（效率 42–43%）；同一形状的 1×12–1×14 为 73–77%。
- **原因**：编译器对前者按行切分，每个 ANE 8 行、全部输出通道，**两个 ANE 各读一份完整权重**；而读权重带宽约 150 GB/s，由两个 ANE 共享（memory.md C2）。对 1×12–1×14 则按输出通道切分，各读一半权重。实测与"总权重读取量 ÷ 150 GB/s"的预测一致（1×9：33.0 对 33.7 µs；1×12：24.9 对 22.5 µs）。
- **建议**：对受读权重限制的层，双 ANE 应按输出通道切分；或者这种情况下干脆只用一个 ANE（可省一半功耗）。
- **根本原因（逆向确认）**：双 ANE 的成本模型（`LatencyInfo::ComputeSplitLatencyBonded`）把切分后的总延迟直接乘 0.5，即假设两个 ANE 完全并行、各有完整带宽，没有任何一项考虑共享的读权重带宽（bonded_measure.md §2.2）。
- **出处**：compute_array.md B4c 第 8 点；数据 `data/05_compute/ks4_fit.txt`、`data/05_compute/ks4_hwx/`。

### B10 PE（平面引擎）时钟升频慢，且 GPU 同时工作时被反复压回慢档

- **现象**：
  1. 只跑 PE 类运算（逐元素链，数据留在 L2）时，冷启动后 PE 在慢档停约 0.4–0.5 s 才开始升频，升频中来回摆动，约 0.8 s 后才稳定在满速；同条件下 NE（卷积）约 50 ms 升满。慢档到满速为 2.63 倍（256 × 64²、96 个运算：每次调用 ANE 任务 1193 µs → 466 µs）。
  2. GPU 同时读内存时，PE 提速后又被压回慢档，反复多次，整轮（约 1 s）未稳定在满速；此时 SOC 调压域一直在最高档 VOVD2，说明不是 SOC 电压不够。
- **证据**：kdebug 任务时长与 IOReport SOC 档位按 mach 时基对齐（compute_array.md H53"PE 的时钟"，数据 `data/09_clock/socpe_kt/`）；三进程交错实验中 NE 已满载时 PE 仍在慢档（`data/09_clock/pefreq_kt3/`）。
- **推测原因**：PE / L2 在单独调度的"共享 ANE 簇"时钟域，由 CLPC 管理，调度反应慢，并受互连功耗限制（`fabric_power_limiter`、`FabricComputePowerRatio`）约束；该域没有公开的频率表或档位统计。
- **影响**：短于约 0.5 s 的推理，PE 部分（逐元素、激活、归一化等）基本跑在慢档；ANE 与 GPU 并发的应用里，PE 部分可能长期慢至约 2.6 倍。NE（卷积 / 矩阵乘）不受影响。
- **建议**：CLPC 对 ANE 共享簇的升频应与 NE 同步（NE 已满载说明负载明确）；GPU 并发时的功耗分配应考虑 ANE 共享簇的吞吐需求。

## C 未写进文档的行为（开发者容易踩到）

| # | 行为 | 出处 |
|---|---|---|
| C1 | 小模型、单独的 softmax / relu、部分采样类运算会被 Core ML 悄悄放到 CPU，没有任何提示 | repro_plan.md 方法约定 |
| C2 | 卷积 / 矩阵乘的累加器是 Q15.16 定点数：中间值绝对值 ≥ 32768 即变成 inf 并"粘住"（之后减回来也还是 inf）；bias 计入同一个范围 | numerics.md、H11 |
| C3 | NaN 输入被当作普通大数（2¹⁶ 量级）解码，导致累加器溢出成 +inf | numerics.md |
| C4 | 小乘积是否被丢掉按指数和判断：x、w 指数和 ≤ −17 时整个乘积丢掉，即使实际值接近 2 LSB（约 3·10⁻⁵） | numerics.md H12 |
| C5 | 输出舍入是"远离零的四舍五入"，不是 IEEE 的四舍六入五成双 | numerics.md |
| C6 | gelu 选 EXACT 或 TANH 近似，在 ANE 上是同一张查找表 | numerics.md F3 |
| C7 | 空闲 5.68 s 后 ANE 断电，下次调用多约 50 ms；空闲 10.2 s 时还会被维护计时器重新上电一次、撤下模型 | power.md §3.1 |
| C8 | coremltools 生成模型时默认加载一次，那次的编译缓存不会被之后加载 .mlmodelc 复用，大模型会被编两次（用 `skip_model_load=True` 避免） | compile_cost.md §3 |
| C9 | 卷积核宽度 ≥ 16 时 ANE 编译失败，Core ML 不报错，整个模型退回 CPU（慢 4–7 倍）；核高没有这个限制 | compute_array.md B4c |
| C10 | int8（W8A8）卷积的累加器是 32 位有符号整数，整数和达到 2^31 时输出 inf（不饱和）；fp16 路径则在实际值 ±32768 处溢出，两条路径的上限不同 | numerics.md H50 |
