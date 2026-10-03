# 编译代价：双 ANE 版本让编译变慢（H7）

- 日期：2026-10-02
- 方法：用 `tools/common/anecc.m` 在 M6 上直接调用 `ANECCompile`（只编译、不执行），同一个 MIL 分别按 h16g（M4）、h17s（M5）、h18、h18g（M6）、h19 编译，记录墙钟时间。
  - h18 是和 h18g 同一代的单引擎目标，产物里没有 bonded 版本，所以 **h18 和 h18g 的差就是生成双 ANE 版本的代价**，不需要任何开关。
- 原始数据：`data/03_compile/h7_compile_time.txt`

## 1. 五个目标的对比

| 模型 | h16g | h17s | h18 | **h18g** | h19 | 产物大小（h18 → h18g） |
|---|---|---|---|---|---|---|
| 1×1 卷积链，64 通道，宽 1024，256 层 | 0.67 s | 0.68 s | 0.68 s | **1.19 s**（1.75×） | 1.19 s | 160 KB → 352 KB |
| 逐元素链 64 步（128 个逐元素层） | 0.09 s | 0.09 s | 0.09 s | **1.10 s**（12×） | 1.10 s | 80 KB → 144 KB |
| 两层 1×1 卷积，16 MB 中间张量 | 0.03 s | 0.03 s | 0.03 s | 0.05 s | 0.05 s | 176 KB → 224 KB |

- h16g、h17s、h18 三个单引擎目标的编译时间完全相同，h18g 和 h19 完全相同。
- **慢只来自双 ANE 版本**，和代际无关。

## 2. 逐元素链：编译时间随层数的增长

`y = y·u + u` 重复 n 步（每步一个乘法、一个加法）：

| 步数 | 逐元素层数 | h18 | h18g | 倍数 |
|---|---|---|---|---|
| 32 | 64 | 0.06 s | 0.18 s | 3× |
| 64 | 128 | 0.10 s | 1.13 s | 11× |
| 96 | 192 | 0.14 s | 4.57 s | 33× |
| 128 | 256 | 0.18 s | 13.1 s | 73× |
| 192 | 384 | 0.28 s | 61.3 s | 219× |
| 256 | 512 | 0.39 s | **178.6 s** | **458×** |

- **单引擎版本线性增长**（每步约 1.5 ms）。
- **双 ANE 版本约按步数的 3.5–3.8 次方增长**：64→128 步涨 11.6 倍，128→256 步涨 13.6 倍。
- 编译器里和双 ANE 相关的步骤有：
  - `BondedSplitSubgraphIdentification`（按维度拆子图，考虑 L2 压力）；
  - `ZinMirFindInherentParallelism`（找可并行的分支，支持 work stealing）；
  - `LatencyInfo::ComputeSplitLatencyBonded`；
  - `CodegenAsyncGroupsForBonded`。

  推测是其中某个对所有层或层对做搜索，复杂度超线性。卷积链的增长慢得多（256 层只多 0.5 s），说明主要是逐元素层（PE）触发的。

## 3. 和 Core ML 加载时间的关系

| 模型 | 直接编译（h18g） | 通过 Core ML 首次加载 |
|---|---|---|
| ovl_B256 | 179 s | 约 510 s（计时程序加载用时） |
| ovl_AB128_256（128 层卷积 + 256 步逐元素） | 未测 | 约 650 s |

- Core ML 路径比直接编译还慢约 3 倍。原因见下面 §3.1：**编译服务跑在 E 核上**。
- 另外，coremltools 生成模型时默认会加载一次，那次编译的缓存不会被之后加载 .mlmodelc 时复用，所以以前的大模型都被编译了两次。现已在所有生成脚本里加了 `skip_model_load=True`。
- M6 上曾有一个 ANE 编译服务进程单核满载约 2 小时（14:45–16:50，被手动结束）。按上面的增长率，几百层逐元素运算的图编译几十分钟到几小时都有可能，这很可能就是原因。

### 3.1 为什么 Core ML 首次加载慢约 3 倍（2026-10-02）

- 工具：`tools/common/cmload.m`（只计时 `MLModel` 加载；每次复制成新的进程名，Core ML 和 aned 的缓存按进程名区分，确保每次都重新编译；可选指定发起加载的线程 QoS）。同时用 `log stream` 抓 aned 和 ANECompilerService 的日志，用 IOReport `CPU Core Performance States` 统计各核的忙碌时间。原始数据：`data/03_compile/cm_load_vs_compile.txt`。
- 模型 `ovl_B128`（128 步逐元素运算），h18g：

| 方式 | 用时 | 运行在 |
|---|---|---|
| 直接编译（`anecc`，本进程，默认优先级） | **12.65 s** | P 核 |
| 直接编译，`taskpolicy -c utility` | 12.66 s | P 核 |
| 直接编译，`taskpolicy -b`（后台） | 83.9 s | E 核（低频） |
| **Core ML 首次加载**（客户端 QoS 为 default / utility / user-initiated / user-interactive） | **33.7–34.3 s**，其中编译 34.05 s | **E 核**：25 s 窗口里 6 个 E 核合计忙约 30 s，P 核 0.2 s |
| Core ML 首次加载，客户端 QoS = background | 98.8 s | E 核（低频） |

- **只编译了一次**：编译服务日志里 "Start of compilation" 到 "End of compilation" 正好 34.05 s，加载过程的其余步骤合计不到 0.3 s。编译选项也不是原因：同一个编译器、同一个目标，耗时比 34.05 / 12.65 = 2.7，正好是 E 核与 P 核单线程性能之比。
- **为什么在 E 核**：
  - aned 的 launchd 配置是 `ProcessType = Adaptive`，空闲时处于后台优先级（`ps` 显示 pri 4）；
  - 编译服务（`ANECompilerService.xpc`，`_MultipleInstances`）由 aned 拉起，继承这个角色：空闲时 pri 4，编译时被客户端请求提升到 pri 31（默认 QoS，日志 `clientQos=21 threadQos=21`），但线程仍被调度到 E 核；
  - 编译服务的可执行文件里没有绑定 CPU 簇或主动降优先级的代码，只有 CPU 用量监控（`proc_set_cpumon_params`）。所以这是系统对"守护进程派生的 XPC 服务"的调度策略，客户端 QoS 只能把它变得更慢（background），不能把它提到 P 核。
- aned 有 4 种编译服务实例：`Regular`（本次）、`Background`、`LongerDuration`，以及单独的 `ANELargeModelCompilerService.xpc`，按请求的 QoS / 模型大小选择。
- M6 的 CPU：2 个 P 核（PCPU0–1）、4 个 M 核（MCPU2–5）、6 个 E 核（ECPU0–5），见 IOReport `PACC0_PCPU*` / `PACC0_MCPU*` / `EACC_ECPU*`。
- 对使用者的含义：在 M6 上，大模型的首次加载慢主要有两个原因：一是双 ANE 版本的编译开销随逐元素层数超线性增长，二是编译跑在 E 核上，又慢 2.7 倍。之后的加载走缓存，不受影响。

## 4. 双 ANE 编译路径的深度上限（H9）

同一种 64 通道卷积链，h18g 在 **387 层起编译崩溃**（栈溢出，SIGBUS），h16g / h18 到 512 层都正常。崩溃发生在只有 h18g 才执行的 `ZinIrParallelExecutionOpportunityFinder::FindIntraANEParallelism`（经由递归的 `ZinIrOpLayerGraphScheduler::Schedule`）。详见 `scheduling.md` D5。

## 结论（报告用）

1. **在 M6 上，编译一个模型要同时生成单 ANE 和双 ANE 两套程序**。双 ANE 版本的编译时间对逐元素层很敏感，约按层数的 3.5–3.8 次方增长：512 个逐元素层要 3 分钟（单引擎只要 0.4 s），通过 Core ML 首次加载则要 8 分钟以上。
2. 这是 M6 上"Core ML 首次加载特别慢"的主要原因。编译结果有缓存，之后再加载就快了。
3. h19 的编译行为和 h18g 相同。
4. 双 ANE 编译路径还有一个深度上限：约 386 层后递归调度栈溢出、编译器崩溃，这就是 M6 上图深度上限的来源。

## 待做

- Core ML 路径比直接编译慢 3 倍的原因：对比编译服务实际用的选项。
- 哪一步编译耗时最多：在 `anecc` 进程里采样（例如 `sample`），看热点函数。
