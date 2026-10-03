# maderix《Inside the M4 ANE》四篇内容整理

- 测试平台：M4 Mac mini（16 核 ANE，代号 H16G），macOS 15.x
- 代码：github.com/maderix/ANE（MIT 许可），只包含 Part 1–3 的代码
- Part 4 用到的工具没有公开：读硬件参数表（HAT）、解析和生成 HWX

## Part 1：软件栈和接口（逆向入门）

| 章节 | 内容 |
|---|---|
| ANE 是什么 | ANE 是整图执行引擎，不是 CPU，也不是 GPU。A11 上 2 核，M4 上 16 核。任务队列深度 127。有独立的调频调压（DVFS），空闲时彻底断电 |
| 前人工作 | hollance/neural-engine（社区文档）、mdaiter/ane、eiln/ane（Asahi Linux 驱动）、apple/ml-ane-transformers |
| 方法 | 用 `dyld_info -objc` 找私有类；方法替换（swizzling）截获 Core ML 对私有接口的调用；分析 E5 二进制；做规模扫描 |
| 软件栈 | Core ML 在上层，往下是 AppleNeuralEngine.framework 里的 `_ANEClient`，负责编译、加载、执行 |
| `_ANEClient` 调用流程 | 1. sharedConnection<br>2. `_ANEModel`<br>3. 编译<br>4. 加载（返回 programHandle，queueDepth=127）<br>5. 创建 IOSurface<br>6. 创建 `_ANERequest`<br>7. evaluate<br>8. 读取输出 |
| MIL | 带类型的 SSA；张量布局 NCDHW；1024×1024 矩阵写成 [1,1024,1,1024] |
| E5 二进制 | 1024² matmul 编出来 2688 字节，128² 编出来 2680 字节，大小几乎一样。说明 E5 存的是参数配置，不是指令 |
| 内存中编译 | `_ANEInMemoryModelDescriptor`（Apple 源码里拼错成 Desctiptor）。有三个坑：<br>1. milText 要传 NSData<br>2. weights 是一个字典，不是一整块 buffer<br>3. 内部仍会写临时目录 |
| 硬件 | DVFS 触发源有 ANE_ADCLK_TRIG、ANE_DITHR_TRIG、ANE_PPT_* 等 |
| IOSurface | 所有输入输出都走 IOSurface，理论上可以和 GPU 零拷贝互通 |
| 编译缓存 | `~/Library/Caches/<app>/com.apple.e5rt.e5bundlecache/`。首次编译 20–40 ms，命中缓存几乎不花时间 |
| 未探索 | `_ANEChainingRequest`、`_ANESharedEvents` 和 Signal/Wait 事件、`_ANEPerformanceStats`（可能是性能计数器）、`_ANEVirtualClient` |

## Part 2：性能测试

| 章节 | 内容 |
|---|---|
| 测试设置 | 直接调 `_ANEClient`；用 mach_absolute_time 计时，跑 100 次以上取中位数；计算用 FP16，输入输出用 FP32 |
| matmul 规模扫描 | 256²：总耗时 0.101 ms，其中调度开销约 0.095 ms<br>2048²：5.7 TFLOPS<br>4096²：4.0 TFLOPS |
| SRAM 断崖 | 2048² 时三个矩阵共 24 MB，放得下；4096² 共 96 MB，性能掉 30%。推断 SRAM 约 32 MB |
| 卷积优于 matmul | 写成 1×1 卷积约快 3 倍 |
| 深图填满流水线 | 单个 matmul 只用到峰值的约 30%；16–64 层深链能接近峰值 |
| Core ML 开销 | 小算子上 Core ML 慢 2–4 倍 |
| INT8 = FP16 | 结论是"没有 2 倍加速"，真实峰值 19 TFLOPS，32 层以上利用率 94%。**这条被 Part 4 修正了** |
| 能效 | 空闲 0 mW；6.6 TFLOPS/W（按 2.8 W 计算）。对比 A100 约 0.08、H100 约 0.13 |
| ANE vs SME | ANE 适合 prefill，CPU 上的 SME 适合单 token 的 decode |

## Part 3：在 ANE 上训练（偏应用）

| 章节 | 内容 |
|---|---|
| 分工 | ANE 不支持分支、按运行时值索引、原地修改。SDPA 会忽略因果 mask，所以 attention 拆成三步：Q@Kᵀ 在 ANE 上，mask+softmax 在 CPU 上，乘 V 在 ANE 上。权重梯度和 Adam 在 CPU 上 |
| 方案 1：权重写死 | 每个 batch 要编译 72 次，每步 106.7 ms，约 1.6 TFLOPS。**一个进程编译约 119 次后资源泄漏**，只能定期重启进程 |
| 方案 2：更多运算放到 ANE | 每步降到 91.8 ms，但编译次数增加到 86 次，总时间反而变长 |
| 方案 3：动态权重 | 权重作为 IOSurface 输入传进去，启动时只编译一次（约 0.4 s），每步 96 ms |
| 问题 | FP16 梯度下溢，需要把 loss 乘 256；权重转置放错；残差需要按 1/√(2N) 缩放 |
| 结果 | Stories110M 训练 50K 步，loss 从 9.11 降到 1.02。Qwen3-0.6B 每步约 416 ms。功耗 2.8 W，CPU 训练要 15–20 W |
| 后续 | 每次 XPC 调度约 160 µs。12 层合成一个大 kernel 耗时 5081 µs，拆成 24 次调用耗时 15227 µs。4 层融合是最佳平衡点（7.7 倍） |

## Part 4：硬件本身（最深的一篇）

| 章节 | 内容 |
|---|---|
| 方法 | 两条路径：<br>1. MIL → 编译器 → ANE：看算子支持和整图性能<br>2. 自己写 HWX → loader → ANE：看任务描述符、DMA 记录、分块、模式<br>具体手段：逐字节比较二进制、改字段后上机执行、用 LLDB 读出 2360 字节的 HAT、从零生成和编译器逐字节一致的程序 |
| 端到端流程 | MIL → ANECompiler → SSA → 合法化和分块 → 调度任务描述符 → aned 加载 → 调度（约 90 µs）→ 硬件执行 → IOSurface 输出 |
| 总体规格 | 16 核，H16G 版本号 192；峰值 19 TFLOPS；4.6 W；内存带宽 120 GB/s，CPU、GPU、ANE 三者共享 |
| **2 MiB 规则** | 编译器拿每个操作数和 HAT[0x1b8]（2 MiB）比较：不超过就整块驻留在片上，超过就分块、双缓冲，下一块的 DMA 和当前块的计算重叠 |
| **SRAM** | 64 个 bank，交错粒度 16 字节，bank = ⌊addr/16⌋ mod 64。权重：64 KiB 常驻，最多 16 MiB 分 16 块流式读入 |
| **计算** | 8 个计算组 × 8 个累加器。默认 FP16 19 TFLOPS；W8A8 打包模式 38 TOPS |
| **DMA** | 独立输入平面从 2 个增加到 8 个，每多一个慢约 995 µs。DMA_INTER 把融合的中间结果留在 SRAM 里，matmul+bias+relu 融合后快 5.7 倍 |
| 支持的运算 | 矩阵：matmul、1×1/3×3/5×5 卷积、depthwise、SDPA<br>逐元素：256 个 ALU 操作码<br>激活：sigmoid、tanh、gelu、silu、exp 等，用 33 个采样点的分段线性 LUT 实现，sigmoid 在 −8 到 8 上最大误差 2.4e-4<br>归约：sum、mean、max。softmax 和 layer_norm 拆成 6–7 个融合的基础操作<br>不支持：acos、asin、tan、log、cumsum、mod、布尔逻辑 |
| 程序格式 | Mach-O，magic 0xBEEFFACE，CPU type 0x80，subtype 0x07（H16G） |
| 性能 | 单个 1024² matmul：5.2 TFLOPS（27%）<br>64 层 1×1 卷积，512 通道，128²：18.77 TFLOPS（98.8%）<br>48 层，1024 通道，64²：W8A8 36.01 TOPS |
| **W8A8** | W8A8 是整条链的属性：中间块的模式字是 0xb1418005，单字节边的 DMA 字是 0x80049240，两者缺一不可。只有权重是 INT8 时加速 1.00 倍。只改模式字会变慢一倍、结果出错 |
| 功耗 | 空闲 0 mW；FP16 4.57 W（4.1 TFLOPS/W）；W8A8 12.25 W（2.9 TOPS/W） |
| 形状 | 硬件按输出通道并行。64 通道的链经 SpaceToDepth(4) 变换后，从 3.92 提升到 16.37 TFLOPS（4.18 倍） |
| ANE vs GPU vs CPU | 峰值：ANE 19 TFLOPS，GPU 约 3.6，SME 3.9 TOPS<br>交叉点约在 23 µs 的计算量<br>两个请求同时提交只省 16% |
| M6 推测 | 两个 16 核引擎；内存带宽 170 GB/s。推测 38 TFLOPS / 76 TOPS（未实测）。是否共享 SRAM、调度一次还是两次、一张图能否跨两个引擎，都未知 |
| 硬限制 | 383 个块能编译，384 个就失败；只支持 FP16 和 W8A8（FP8 E4M3 的能力位是 0）；HWX 里没有分支记录 |
| **仍未知** | 程序最大长度；MAC、PE、DMA 之间的重叠（实测只省 1.1%）；DMA 引擎数量和队列深度；乘加阵列的通道数和时钟频率；WAIT/WAIT_EXT 的同步范围 |

## 各篇之间的矛盾（引用时注意）

| 项目 | 早期说法 | Part 4 |
|---|---|---|
| INT8 | 没有加速（Part 2） | W8A8 打包后约 1.95 倍；只有权重是 INT8 时才不加速 |
| 功耗 | 2.8 W（Part 2、3） | FP16 4.57 W，W8A8 12.25 W |
| 能效 | 6.6 TFLOPS/W | 4.1 TFLOPS/W |
| 调度开销 | 95 µs（Part 2），160 µs（Part 3） | 约 90 µs |
| SRAM | 约 32 MB，由断崖推断 | 改用 2 MiB 单操作数门槛加 bank 结构来描述，没有再给总容量 |

## 和硬件设计（流水线）直接相关的内容

- 有哪几级（Part 4）：
  - DMA 读入：分 tile DMA 和 kernel DMA 两路
  - SRAM
  - 计算：8 组 × 8 累加器
  - 逐元素 ALU 和 LUT
  - DMA 写出
- 重叠：
  - 分块之间有双缓冲，DMA 和计算能重叠；
  - MAC 和 PE 之间几乎不重叠，只省 1.1%；
  - 两个请求并发只省 16%。
- 尺寸：
  - 2 MiB 操作数门槛；
  - 64 个 bank × 16 字节；
  - 64 KiB 常驻权重，16 块流式读入。
- **他没测出来、可以做的**：
  - 时钟频率；
  - 乘加阵列的通道数；
  - DMA 引擎数量；
  - 各级之间的重叠关系；
  - M6 双引擎怎么协作。
