# ANE 编译器参数表（ZinIrHalParameters）分析

- 来源：M6 上 macOS 27.0.1 的 ANECompiler，各代 `ZinIrHal*::GetParams()` 返回的静态表，每张 0xa10 字节。
- 原始数据：`hal_*.bin`（不公开，只留本地 private/；可用 `tools/re/dump2.c`、`tools/re/hal_readers.py` 重新生成）
- 字段总表：`hal_fields_raw.txt`（偏移、宽度、各代数值、读取它的函数）（不公开，只留本地 private/；可用 `tools/re/dump2.c`、`tools/re/hal_readers.py` 重新生成）
- 读取者索引：`hal_readers.json`（不公开，只留本地 private/；可用 `tools/re/dump2.c`、`tools/re/hal_readers.py` 重新生成）

## 方法

1. 在进程内调用各代的 `GetParams()`，导出参数表（`tools/re/dump2.c`）。
2. 取出所有参数里带 `ZinIrHalParameters const&` 的函数（3233 个）的机器码，用 clang 汇编、llvm-objdump 反汇编（`tools/re/fnbytes.c`）。
3. 根据签名定位参数表是第几个参数，跟踪对应寄存器上 `[reg, #imm]` 形式的读取，得到"偏移 → 读取函数"（`tools/re/hal_readers.py`）。共有 293 个偏移找到了读取者。
4. 用函数名推断字段含义，再拿各代的数值变化去核对。

**局限**：
- 只做线性扫描，不跟分支，也不跟经过内存中转的读取，所以会漏掉一些读取者。
- 字段含义是由函数名推出来的，没有上机验证。

## 结论 1：同一代的各个变体，参数表完全一样

- H16、H16g、H16s、H16c 的数值字节级相同，H17 各变体也是。只有表开头的名字指针和几个 vector 的地址不同，vector 里的内容也一样。
- **这一版编译器里，按变体区分的东西（例如核数、die 数）已经不在这张表里**。书里说 HAL+0x238 存 num_nes（base=4、g=8、s=16），这个说法不适用于这一版。
- 0x00c 是"每个 ANE 的 NE 核数"：M9 为 2，H11/H12 为 8，**H13 及以后都是 16**。读它的函数有 `DetermineNumNesToUse`、`ComputeOcgSize`、`ComputeNumActiveCoeffDMA`。这和 M6 上 ioreg 报的每个 ANE 16 核（NumANECores = 16）一致。

## 结论 2：和 Bryngelson 书中布局的对应关系

这一版编译器在表里插入了新字段，所以书里的偏移在不同区段要加上不同的位移：

| 书中偏移 | 含义 | 本版偏移 | 位移 | 数值验证 |
|---|---|---|---|---|
| 0x0c | 每核累加器预算 | 0x014 | +0x8 | 8（`ComputeMaxOcgSize`、`HasAccDoubleBuffering` 读取） |
| 0x70 | 大卷积核 z 维上限 | 0x078 | +0x8 | H11/H12 为 1，H13 起为 16 |
| 0x138 | 张量最大宽度 | 0x158 | +0x20 | H13–H15 为 16384，H16 起为 65536 |
| 0x158 | 张量最大深度 | 0x178 | +0x20 | 同上 |
| 0x1b8 | 单个操作数上限 | 0x1d8 | +0x20 | 2 MiB（M9 为 1 MiB） |
| 0x1c0 | DRAM 对齐 | 0x1e0 | +0x20 | 16 |
| 0x1c8 | L2 bank 数 | 0x1e8 | +0x20 | 64（`ZinMirBankConflictOptimizer` 读取） |
| 0x1f0 | L2 驻留阈值 | 0x210 | +0x20 | H15 为 32 KiB，H16 起为 256 KiB |
| 0x200 | 常驻权重上限 | 0x220 | +0x20 | 64 KiB |
| 0x210 | 流式权重上限 | 0x230 | +0x20 | 16 MiB（`OptimizeCoutBatchtoFitInKBuf` 读取） |
| 0x218 | 指令/段对齐 | 0x240 | +0x28 | H13 为 256，H14 起为 16 |
| 0x228 | 成本模型周期除数 | 0x250 | +0x28 | M9 16，H11 32，H12 起 64 |
| 0x3f0 | 归约转 transpose 的阈值 | 0x470 | +0x80 | 192，H15 起为 384 |
| 0x668 | 交换格式数 | 0x720 | +0xb8 | 3 / 13 / 16 / 14 |

## 结论 3：流水线和性能模型相关的常数（H13 起各代基本不变）

| 偏移 | 值 | 读取者 | 推断 |
|---|---|---|---|
| 0x00c | 16 | DetermineNumNesToUse | 每个 ANE 有 16 个 NE 核 |
| 0x014 | 8 | ComputeMaxOcgSize, HasAccDoubleBuffering | 累加器深度 8 |
| 0x010 | 8 MiB | HandleNEConfig, CalculateCoutBatchSize | NE 配置上限（待查） |
| 0x1d8 | 2 MiB | HandleL2Config, LowerNEMatMulToNEConv | 单个操作数上限，超过就分块 |
| 0x1e0 | 16 | L2 fetch/WB request, GetL2Alignment | L2 访问粒度 16 B |
| 0x1e8 | 64 | BankConflictOptimizer | L2 bank 数 64 |
| 0x1f0 | 128 | ComputeL2FetchRequest, 性能模型 | 每次 L2 取数 128 B（推测） |
| 0x298 | 256 | L2FetchRequest, PE chain buffer, 性能模型 | 256 B 粒度 |
| 0x2a0 | 64 | PERasterization::GetWorkunitSize | PE 工作单元 64 |
| 0x330 | 16 | SetChainBufferNEWorkUnit, 性能模型 | NE 工作单元 16 |
| 0x408 / 0x410 | 16 / 8 | ComputeMaxOcgSize | OCG 相关上限 |
| 0x890 | 50（与相邻的 10 成对，高低互换后拷入 PerfHwParams +0xf0 / +0xf8） | 性能模型 | ~~疑似"50 GB/s 带宽常数"~~ → **2026-10-03 更正：内存访问能耗系数**，10 pJ/B（落在系统缓存）/ 50 pJ/B（DRAM），用于 perf CSV 的 `power(W)` 列（见 power.md §7.1） |
| 0x8c0 | 4 | 性能模型 | H14 为 6，H15 起为 4 |
| 0x9d0 | 3 | 性能模型 | H16 起 |

## 结论 4：H17 → H18（M5 → M6）的变化

| 偏移 | H17 | H18 | 读取者 | 推断 |
|---|---|---|---|---|
| 0x55a | 0 | 1 | CanUseTinySourceMode | 支持新的小输入模式 |
| 0x55c | 0 | 1 | **CanUseHalfWorkUnitMode** | 新增"半工作单元"模式，小张量能更细地切分 |
| 0x5a0 / 0x5a8 | 0 | 16 / 20 | **EnumerateWorkUnitCandidateForNonPowerOf2** | 工作单元可以不是 2 的幂（候选值 16、20） |
| 0x5fb–0x5fd | 1 | 0 | CanUseFillLowerNEFirst, SetMirInfoForMultiPaletteLut / VectorPalettization | 取消"先填满低编号 NE"的策略；调色板 LUT 的处理方式变了 |
| 0x5ff / 0x600 | 0 | 1 | ValidateFormat, ValidateKernelFormat, CheckLiveIOTensor | **新增输入输出 / 权重格式**（可能是 fp8 或 MX 格式） |
| 0x60a | 0 | 1 | IsFusableBasedOnFormatOCGSizeAndActiveNE | NE 输出 transpose 可以融合 |
| 0x64b | 0 | 1 | HasUnalignedOutputCropX, HandleL2Config | 支持输出 X 方向不对齐的裁剪 |
| 0x658 | 14 | 12 | GetDSIDFromPriorityHalAndSecureMode | 系统缓存（SLC）的 DSID 分配变了 |
| ~~0x72a~~ | ~~1~~ | ~~0~~ | CreateRasterKernelHALConfig | **更正（2026-10-04）：这一项在 H16 → H17 时就已变化（H16g 1、H17 / H17s 0），不属于 H17 → H18** |
| ~~0x72f / 0x730~~ | ~~0~~ | ~~1 / 4~~ | ValidatePaletteVectorSize | **更正（2026-10-04）：向量调色板在 H17 就已存在（H17 / H17s 均为 1 / 4，H16g 为 0），不是 H18 新增** |
| 0x738 | — | 变化 | — | — |
| 0x73a | 0 | 1 | 性能模型 | — |
| ~~0x73b~~ | ~~0~~ | ~~1~~ | EventFlagsV6/V7 | **更正（2026-10-04）：H17 / H17s 已为 1，H16 → H17 的变化** |
| 0x818 | 0 | 4 | 仅构造函数 | — |
| 0x838 | 0 | 15 | ValidateReflectivePaddingMode | 支持反射填充，范围 15 |
| 0x6a8 vector | 5 项 | 6 项（多了 6） | HandleL2Config, IsFusableToDequant | 可与反量化融合的权重类型多了一种 |
| 0x8a0 vector | 13 项 | 21 项 | NeedsUpcastingFrom3bitPaletteTo4bitPalette | **原生支持的权重格式从 13 种增加到 21 种**（例如 3-bit 调色板不再需要升成 4-bit） |

**小结**：
- 从 H17 到 H18，参数表里**乘加阵列、L2、带宽这些常数都没有变**，变化集中在两方面：
  - 工作单元切分更灵活：半工作单元、非 2 的幂；
  - 权重 / 张量格式更多：向量调色板、新格式、3-bit 调色板。
- 双 ANE（bonded）在这张表里看不到，它由编译器参数（EnableBondedNetworks 等）控制。

## 结论 5：H19（下一代）相对 H18 的变化（预告）

| 偏移 | H18 | H19 | 读取者 | 推断 |
|---|---|---|---|---|
| 0x5f7 | 0 | 1 | **CanEnableDoubleRateMode** | 新增"双倍速率"模式 |
| 0x5c7 / 0x5c8 | 0 | 1 / 16 | CanUseMultiPaletteMode | 多调色板，最多 16 个 |
| 0x888 / 0x88c | 1 MiB / 1 | 2 MiB / 2 | FifoMode::GetFifoModeUtil, 性能模型 | FIFO 模式的缓冲加倍 |
| 0x678 / 0x690 / 0x698 | 64 / 8 / 0 | 32 / 16 / 1 | DartThrashingOptimizer | 地址翻译（DART）抖动优化 |
| 0x1a8–0x1c8, 0x800, 0x810 | 65536 | 0xffffffff | gather / texture 维度 | 维度上限取消 |
| 0x563, 0x73c, 0x73f | 0 | 1 | 性能模型, ValidateFormat | 更多新格式 |

另外，`2026BaseLine` 的表和 H19 在这些字段上一致，可能是 H19 的基线。

**2026-10-04 逐字节核对**：`hal_2026BaseLine.bin` 与 `hal_H19.bin` 除表头名字指针和各 vector 的 begin / end / cap 指针外完全相同，各 vector 内容（`vec_*.txt`）也完全相同。h18g（M6）用的是 2026BaseLine，所以**编译器眼中 M6 的硬件参数 = H19 的参数**，与同代单引擎 H18 不同（多调色板、双倍速率、FIFO 2 MiB、DART 抖动参数、gather / 纹理维度上限、0x563 / 0x73c / 0x73f 等）。两者在编译器中的区别只在 SoC 参数（`Soc2026BaseLine` 与 `H19`）。核对时还发现上面 H17 → H18 表中 0x72a、0x72f / 0x730、0x73b 三项实为 H16 → H17 的变化，已更正。

## 待做

1. 反汇编 `ToPerfHwParams`，结合 perfmodel 里的成员名，给性能模型字段命名（0x250、0x3e0、0x448、0x458、0x578、0x588、0x598、0x890、0x8c0、0x9d0 等）。
2. 查 0x8a0 vector 里 21 项对应的权重格式编号，确认 H18 新增了哪 8 种。
3. 编一个小卷积，从 HWX 的 build banner 看 H18 实际用的 TD 版本和编译参数。这一步要用 ANE 编译服务，需要等 M6 空闲。

## 结论 6：H19 在编译产物里的体现（H8，2026-10-02）

同一个模型（512 通道、32×32、4 层，每层独立权重）分别做成 FP16、W8（只量化权重）、W8A8 三种，按 h18g 和 h19 编译后逐字对比 TD 流（`data/03_compile/h8/`）：

| 差异 | h18g → h19 | 推断 |
|---|---|---|
| 每个 TD 偏移 0x14 处的计数 | FP16：0x1a → 0x1e；bonded：0xd → 0xf；W8A8：9 → 12、0x16 → 0x19、0xd → 0xf | 这个字段在 bonded 时会减半，推测和分块数或 DMA 缓冲深度有关。H19 的 FIFO 缓冲从 1 MiB 翻倍到 2 MiB（HAL 0x888），可能就体现在这里 |
| bonded 版本的两个 L2 地址字 | 0x2580… → 0x2500…，0x2500… → 0x2480… | 片上存储的分配位置整体下移 0x80 |
| 其他 | TD 流长度、记录结构完全相同 | |

- 这几个模型**没有触发双倍速率或 MX 格式**：coremltools 的 int8 对称量化不会用到它们。
- TD 字段里已有对应的位（`IsTileDmaSrc1DoubleRate`、`IsL2Src1DmaDoubleRate` 自 v24 起；`IsMxInFmt` 等在 v36），见 `hwx_h18g.md` §9。要看到它们被置位，需要能生成 MX 格式或双倍速率路径的模型，coremltools 目前做不到。
- 结论：对现有的 FP16 / int8 模型，H19 的编译结果和 M6 几乎相同，差别只在缓冲深度类的计数和 L2 布局。

## 结论 7：M4（H16g）→ M6（2026BaseLine）的逐项对比，以及给未命名字段找读取者（2026-10-05）

**方法**（在 M4 上运行同版本 ANECompiler，不需要 M6）：
1. 逐字节比较 `hal_H16g.bin` 与 `hal_2026BaseLine.bin`：81 个 8 字节字不同；41 个已知字段（有读取者）不同，另有 24 个纯数值差异此前没有读取者，其余是指针（表名、vector 起止地址）。
2. **改字节实验**（`tools/re/halpatch_lldb.py`）：lldb 以 h18g 编译，在 `ZinIrHal2026BaseLine::GetParams()` 第一次返回后把选定字段改成 M4 表的值（编译器之后会把整张表拷走，所以要在拷贝前改），再在某个 TD setter 处读参数；对差异字段二分，找出决定某个编译决策的字段。不能改指针字段（改了编译器会卡死）。
3. **按偏移扫描读取者**（`tools/re/immscan2.c`）：在整个 `__text` 里找"基址寄存器 + 立即数 = 该偏移"的加载指令并标出函数名。不需要跟踪哪个寄存器装着参数表，能找到 `hal_readers.py` 漏掉的读取者；大偏移处会混入别的结构体的同偏移读取，要看函数名筛。
   - 读观察点（`tools/re/halwatch_lldb.py`）在这里不好用：编译器会把静态表整张拷贝（memmove、拷贝构造），后续读取都发生在堆上的拷贝里，地址每次不同。

**DetectZeros 的开关 = HAL 0x72c**（因果验证）：把 39 个数值差异字段改回 M4 的值后，h18g 编译的 `SetKernelDetectZeros` 参数由 1 变 0；二分到 0x728 这个 8 字节组，再逐字节测，只有 **0x72c** 改回 0 就让 DetectZeros 变 0。读取者是 `ZinNELayer::EnableOnTheFlySparseEncodingIfPossible`（同一函数还读 0x72d）。0x72c 在 H17（M5 一代）起为 1，H16 及以前为 0——所以"读权重时即时编码零值"从 M5 一代起启用，M4 不启用（hwx_h18g.md §13.3 中"M6 才启用"应改为"M4 不启用、M5 起启用"）。

**M4 → M6 的差异，按引入代际**（"读取者"一列中，带 * 的是本次用偏移扫描新找到的）：

| 引入 | 偏移 | M4 → M6 | 读取者 | 含义 |
|---|---|---|---|---|
| H17 | 0x72c | 0 → 1 | *`EnableOnTheFlySparseEncodingIfPossible` | **DetectZeros（即时稀疏编码）**，已用改字节实验确认 |
| H17 | 0x72b | 0 → 1 | *`ZinNELayer::IsValidMulticastConfiguration` | 多播（推测为同一份数据同时送多个 NE） |
| H17 | 0x902 | 0 → 1 | *`ZinMirPerfTracerSetter::Execute` | 性能跟踪器 |
| H17 | 0x820 | 0 → 2 | *`HandleNEConfig`（各 TD 版本） | NE 配置相关的计数（待定） |
| H17 | 0x5fb–0x5fd、0x653、0x72a、0x72f/0x730、0x73b、0x818、0x884、0x990、0x99a | 见结论 4 | 见结论 4 | 取消"先填满低编号 NE"、向量调色板、事件格式 V6、去掉 TileHeight 勘误与 Radar 103532597 的任务管理器挂起绕行 |
| H18 | 0x55d | 0 → 1 | *`ZinNEConvLayer::CanUseDoubleInt8Mode` | **双 int8 模式**：M6 一代起才有，M4、M5 都没有；对应 compute_array 中 M6 的 W8A8 = FP16 的 2 倍、INT8 每 NE 每周期 512 次乘加 |
| H18 | 0x72d | 0 → 1 | *`EnableOnTheFlySparseEncodingIfPossible` | 即时稀疏编码的第二个条件（单独改它不影响 DetectZeros，作用待查） |
| H18 | 0x998 | 0 → 1 | *`ZinNEConvLayer::GetProgrammedKernelSize` | 写入硬件的权重大小算法 |
| H18 | 0x830 | 0 → 0x1f | — | 待定 |
| H18 | 0x610 | 0x100 → 0x120 | — | 待定 |
| H18 | 0x55a、0x55c、0x5a0/0x5a8、0x5ff/0x600、0x60a、0x64b、0x658、0x73a、0x838、0x8a0 | 见结论 4 | 见结论 4 | 小输入模式、半工作单元、非 2 的幂工作单元、新格式、21 种原生权重格式、反射填充、不对齐的输出裁剪 |
| 2026 | 0x5c7/0x5c8、0x5f7、0x888/0x88c、0x563、0x73c、0x73f | 见结论 5 | 见结论 5 | 多调色板（最多 16）、双倍速率、FIFO 2 MiB、新格式 |
| 2026 | 0x7a0 | 0 → 1 | *`ZinMirEnableAcceleratedTexturing` | 加速纹理采样（gather 走纹理单元，hwx_h18g.md §13.2） |
| 2026 | 0x9d8 | 1 → 0 | *`ZinANELayer::LowerEngineTexture`、`CheckGatherTextureConstraints` | 纹理 / gather 的一条限制取消 |
| 2026 | 0x1a8–0x1c8、0x800、0x810 | 65536 → 0xffffffff | `GetMaxGatherAxisDimensionForTexture` 等 | gather / 纹理维度上限放开 |
| 2026 | 0x668、0x670、0x680、0x688 | 64、64、8、0 → 32、32、32、32 | *`SetCacheDmaPre*`、`HandleDramHazards` | **缓存预取 DMA 参数**（不是 DART；结论 5 的 0x678 / 0x690 / 0x698 仍归 DART 抖动优化） |
| 2026 | 0x740–0x758、0x770–0x788 | 空 → 各 2 项的新列表 | *`HandleCachePrefetchDma` 等 | 缓存预取的配置表（两个新 vector） |

**小结**：
- 从 M4 到 M6，编译器眼中的变化分三步：H17（M5 一代）加入即时稀疏编码（DetectZeros）、多播、新事件格式，并去掉 M4 的几个硬件勘误绕行；H18 加入双 int8、半工作单元、更多格式；2026BaseLine（M6 实际用的表，同 H19）再加多调色板、双倍速率、FIFO 加倍、加速纹理和新的缓存预取参数。
- 乘加阵列、NE 数（16）、L2、累加器等基本常数三代都没有变（结论 3）。M6 相对 M4 的实测差别（W8A8 2 倍、零值省电、DetectZeros、gather 走纹理）在这张表里都能找到对应的能力位。
- 未解：0x72d、0x820、0x830、0x610 的确切含义；多调色板、双倍速率在 M6 的表里是开的，但现有 coremltools 模型都没有触发（hwx_h18g.md §13.2）。
