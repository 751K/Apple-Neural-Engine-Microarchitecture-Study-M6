# Bryngelson《Apple Neural Engine: Architecture, Programming, and Performance》硬件部分整理

- 出处：arXiv:2606.22283，2026 年 6 月，302 页。
- 覆盖范围：A11–A18、M1–M5。
- **只有 M1/H13 和 M5/H17s 两个实测点**（M2 有少量实测），中间各代都是反编译结果或预测，**完全没有 M6 的数据**。
- 每条结论在书中都标为三类之一：实测 / 反编译 / 预测。下文分别记作【实测】【反编译】【预测】。
- 附带一篇 ANEForge（arXiv:2606.17090）：Python 直连 ANE 的工具，github.com/sbryngelson/ANEForge，MIT 许可。

---

## 1. 整体结构

```
CoreML / Espresso(e5rt) → AppleNeuralEngine.framework + aned（编译、签名、缓存）
  → 内核：AppleH11ANEInterface（设备、doorbell）
          AppleANELoadBalancer（多 die 仲裁，最多 4 个 die）
          AppleT81xxANEHAL（时钟、电源）
  → 固件：CHINOOK 控制核（ARM，11 个硬件线程，RTKit）
  → 硅片：NE（MAC 阵列）+ PE（平面引擎）+ L2 scratchpad + DMA（3 个 tile + 1 个 kernel）+ DART
```

- **ANE 是一个由控制核驱动的自主协处理器**。主机只写 mailbox、按 doorbell，不碰计算寄存器。
- **程序不是指令流，是一张静态的任务描述符（TD）图**，由控制器逐段配置 DMA 和 MAC 阵列。没有 PC、没有微码，也不支持数据相关的分支。【反编译】
- 驱动同一时刻只有一个命令在执行（single pending queue）。两个线程同时提交只快 1.04 倍。【实测 M1】ANEForge 在 M5 Pro 上也说"只暴露一条硬件通道"。

## 2. 数据通路（流水线相关）

### 2.1 计算阵列

- 核数有两种口径：
  - **营销口径 / ioreg 的 "number of cores"**：M1 是 16。
  - **架构口径 num_nes（HAL+0x238）**：后缀决定，base=4，g=8，s=16，c=32，d=64。M1 是 4，M5（H17s）是 16。
  - maderix 在 M4 上读到 8（h16g）。书中预测 M4 base 是 4，两者不矛盾：maderix 的 M4 报告的是 h16g，不是 base。
- **每核每周期出 4 个输出通道（fp16），int8 打包时出 8 个**；窄模式出 2 或 1 个。【反编译】
- **归约树**【实测 M1】：
  - 第一级是 radix-4：每 4 个 lane 先在 fp16 下求和；
  - 第二级是一个 fp32 级的宽累加器，只在输出端口舍入到 fp16。
- 累加器文件深 8：单缓冲要求需求 ≤ 8，双缓冲要求需求 ≤ 4。
- OCG（每轮能算多少个输出通道）= min(floor_pow2(8/(kW·kH·kD)), 字节上限 32/16/8)。超出一轮就要再把输入完整读一遍。
  - 实测（M1，1×1 卷积，32²）：输出通道从 192 增到 256 时，耗时从 20 µs 跳到 61 µs。
- **核分配**：输出通道组按 c mod N 轮流分给各核；实际使用的核数 = min(num_nes, next_pow2(ceil(Cout/OCG)))，写在 TD 的 ActiveNE 字段（3 bit）。
  - M1 实测：1/2/3/4 个核的吞吐成线性，每多一核功耗只多约 10 mW，常开的底座约 800 mW。
- **每层固定开销 44 个周期**。这是从编译器成本模型里实时抓到的值。
- **co-issue 只发生在 MAC 与 PE 之间**，例如 softmax 和 V 的 matmul 并发。chaining 和 co-issue 互斥。【反编译】
- Winograd：只有 F(2×2,3×3) 和 F(4×4,3×3) 两种，变换矩阵固化在硬件里，由 HAL[0x680] bit0 使能。
- int8：MAC 有双 int8 打包模式。在 M1 上，只把权重编成 int8 的程序仍然走 fp16。和 maderix 说的"W8A8 是整条链的属性"一致。

### 2.2 时钟（书中仅有的频率数据）

| 芯片 | 时钟 | 来源 |
|---|---|---|
| M1 | 约 1.14 GHz | 实测 |
| M5（H17s） | 约 1.89 GHz | 实测 |

其他补充：
- ANE 节点自身没有 DVFS 表，频率由 SoC 的 PMGR/CLPC 管理。
- 持续负载下一直停在同一个时钟档位：M1 跑 210 s 没有降频。
- IOReport 里 `SOC0_ANE_F1/F2` 是各频点的驻留时间。

### 2.3 存储层次

| 项目 | 值 | HAL 偏移 |
|---|---|---|
| 单个操作数上限（L2 / MemCache） | 2 MB（各代相同） | 0x1b8 |
| 实测阈值 | M1 为 2.28–2.34 MB；**M5 为 4.72 MB** | — |
| L2 bank | 64 个，16 B 交错，没有二级分组 | 0x1c8 / 0x1c0 |
| 常驻权重 | 64 KB | 0x200 |
| 流式权重 | 16 MB | 0x210 |
| L2 驻留阈值 | M1 为 0；A15 为 32 KB；**M4/M5 为 256 KB** | 0x1f0 |
| 编译器默认 memcache | 4 MB（编译参数 `--memcache-size=4194304`） | — |

- 这块存储是编译器管理的 scratchpad，不是 cache。
- 编译器分配缓冲区时有 9 种类型：resident、streamed、L2 双缓冲、L2 原地、ring-buffer、DRAM 原地等。

### 2.4 从 TD 寄存器分组看流水线各级（M1 v10）【反编译】

| 寄存器组 | 寄存器基址 | 数量 | 对应硬件 |
|---|---|---|---|
| Kernel & common | 0x5500 | 34 | kernel DMA（权重）、任务类型 |
| Tile DMA ×3 | 0x4d00 | 69 | 输入数据 DMA |
| EW / PE / padding | 0x4100 | 30 | 平面引擎 |
| L2 & texture | 0x4500 | 14 | L2 源、纹理采样 |
| Kernel format / op mode | 0x4900 | 11 | MAC 模式、palette/稀疏 |
| L2 result | 0x5100 | 21 | 结果写回 L2 |

**从 per-TD 性能计数器的名字推出的数据流**（共 24 个，用户态读不到）：

```
DRAM ─(AF)─→ L2 ─→ NE ─→ L2 ─→ PE ─→ … ─→ DRAM
        └─→ KM（权重存储）─→ NE
```

计数器名：AF_TO_L2、AF_TO_KM、L2_TO_NE、NE_TO_L2、L2_TO_AF，以及 NE 的 COMPUTE / INPUT_STALL / OUTPUT_STALL / KERNEL_STALL、L2 的 READ / WRITE_STALL、FP16 / INT8_CYCLES、DPE_ENERGY。

> 这些计数器名基本就是流水线框图：AF（fabric）→ L2 / KM → NE → L2 → PE。

### 2.5 带宽

| 项目 | 值 |
|---|---|
| M1 DRAM 上限 | 85 GB/s |
| M1 权重流 | 51 GB/s（编译器内部常数 50） |
| M1 独立激活流 | 24 GB/s |
| **M5 权重流** | **约 145 GB/s，走两条 DRAM 读通道** |
| M5 激活路径 | 约 24 GB/s |

我们在 M6 上测到的权重读带宽是 148 GB/s（FP16），和 M5 几乎一样。

## 3. 调度开销分解（M1，约 190 µs/次）【实测】

| 阶段 | 耗时 |
|---|---|
| 用户态和运行时，含 fp16 拷贝 | 约 25 µs |
| 构建固件请求 | 约 16 µs |
| 按 doorbell | 2–3 µs |
| **固件往返** | **约 130 µs** |
| 内核完成处理 | 约 10 µs |

- 每次调用约 2 次中断。
- ANEForge 在 M5 Pro 上测到的调度下限约 70 µs；我们在 M6 上测到 0.1–0.25 ms。

## 4. 电源

- 空闲时整块断电（0 mW），没有"上电但时钟门控"的空闲态。
- 电源域：1 个常开 base 域加 N 个计算簇（M1 是 4 个），由任务触发懒上电。
- 冷唤醒代价：
  - 5 s 空闲后首次调用约 260 ms（M1）；
  - 另一处写约 100 ms 空闲后多 0.5 ms。
- M1 的寄存器初始化表里有 **32 个可单独门控的 MAC tile**。
- 固件里没有温度或降频逻辑，这些都由 SoC 电源管理负责。

## 5. 数值

| 项目 | 结论 |
|---|---|
| 累加器 | fp32 级，各代相同 |
| 舍入 | 输出 round-half-to-even |
| NaN | 输入端的 NaN 变成 +inf |
| 非规格化数 | M1 的 MAC 累加阶段 flush 成 0，M5 保留 |
| 饱和 | M1/A14 上 MAC 输出在 32768 饱和，M5 不饱和 |
| 激活 | 33 点分段线性 LUT（与 maderix 一致） |

## 6. 编译产物格式

- HWX 是 Mach-O：magic 0xbeefface，cputype 0x80，subtype 随代际变化（H13 是 4，H16G 是 7）。
  - 把 magic 改成 0xfeedfacf 后，可以用 `otool` 解析。
- 段：`__TEXT`（TD 流）、`__KERN_0`（权重和 LUT，符号名 `K<sha256>_ne_<i>`）、`__FVMLIB`（输入输出声明）。另有 3 个 `LC_THREAD`，分别是 `main_ane`、`t0_ane`、`t5_ane@output`。
- TD 是链表：头部 +0x1c 是指向下一个 TD 的偏移。
- **共 14 个 TD 版本**（`ZinAneTd<N>`），各版本的偏移和位宽都不同。M5 是 v20。
- build banner 里有完整的编译参数，例如 `-t h13g --memcache-size=4194304 ...`。

## 7. HAL 表 ZinIrHalParameters

- 大小：0x938 B（另一处写 0x348 B，书中不一致）。
- **方法**：编译器为每个架构都有一个构造函数，在任何一台机器上都能取到任意代的 HAL。书里就是这样取了 28 个目标逐字节比较的。
- 关键字段：

| 偏移 | 含义 | M1 | M4（A16） | M5（16 核 profile） |
|---|---|---|---|---|
| 0x0 | 代际标记 | 0x0d | 0x10 | 0x11（H18 = 0x12） |
| 0x0c | 每核累加器预算 | 8 | | |
| 0x138 | 张量最大宽度 | 16384 | 65536 | 65536 |
| 0x1b8 | 单个操作数上限 | 2 MB | 2 MB | 2 MB |
| 0x1f0 | L2 驻留阈值 | 0 | 256 KB | 256 KB |
| 0x228 | 成本模型周期除数 | 64 | | |
| 0x238 | num_nes | 4 | 4（base） | 16 |
| 0x388 / 0x390 / 0x398 | OCG 字节上限 | 32 / 16 / 8 | | |
| 0x3a8 / 0x3b0 / 0x3b8 / 0x3c0 | 每累加器通道数 | 8 / 4 / 2 / 1 | | |
| 0x7a8 | 频率-效率曲线 | | | |

- 字段命名的方法：找签名里带 `ZinIrHalParameters const&` 的 reader 函数，看其中的 ldr/ldrb 偏移。

## 8. 多 die / 多引擎（对 M6 最关键）

**内核层**
- LoadBalancer 最多支持 4 个 die。
- 以**整个提交**为单位派给最空闲的 die，**die 之间不交换张量**。【反编译】
- ioreg 和握手结构里有 "number of engines"，M1 上是 1。

**固件层**
- 先尝试 `ANE1Endpoint1`，失败再回退到 `ANEEndpoint1`。
- 统计 buffer 最多循环 32 个 engine；DMA bar 的 engine 步长是 0x148。

**编译器层**
- 有 `mlir::silc` 集合通信方言：all_reduce、all_gather、all_slice、mesh；跨 die 搬运走 CCDMA。
- 但 collective-enable（0x48b）在所有 28 个目标上都是 0，CCDMA 的 setter 全部是 assert。**功能存在但没有打开**。

**书中关于 H18 的描述**（与 M6 不符）

| 字段 | 含义 | 书中 H18 的值 |
|---|---|---|
| 0x238 | num_nes | 4（"A18 base"，单 die） |
| 0x52d | fp8 E4M3 | 1（只有 H18 是 1） |
| 0x563 | FIFO-mode DMA | 1 |
| 0x564 | 多 die hazard 跟踪 | **0**（A14–H17s 是 1） |
| 0x687 | 远程依赖 | **0** |

**我们 M6 的情况**：2 个 16 核引擎，编译器里有 `ZinIrHalH18`（只看到 H18 一个名字，没有 g/s 后缀）。
- 书里的 H18 是 iPhone A18 的 4 核版本。（注：用户指出 H18 这一代对应的手机芯片是 A20，ANE 与 M6 相同；书中的对应关系可能有误，以本机实测为准。）M6 用的 H18 参数是否不同、有没有新的 profile，需要在本机读 HAL 确认。

## 9. 可在 M6 上直接复用的方法

| # | 方法 | 看什么 | 风险 |
|---|---|---|---|
| 1 | `ioreg -l` 查 H11ANEIn | 架构串、version、number of cores、**number of engines**；是否有 ane0 和 ane1、两个 dart-ane | 无 |
| 2 | `ioreg -p IODeviceTree` 查 ane0/ane1 节点 | clock-ids（每个簇一个）、power-gates、reg | 无 |
| 3 | IOReport（anemon 已有） | 是否有 ANE1 系列通道；`SOC0_ANE_F1/F2` 频点驻留；`ANE0_ADCLK_TRIG`、`ANE_THROTTLE_*` | 无 |
| 4 | 在自己的进程里调用 `ZinIrHalH18::GetParams()` 和 H16g、H17s 的同名函数 | dump HAL 后逐字节比较，读 0x0、0x238、0x1b8、0x1f0、0x48b、0x52d、0x55c、0x564、0x687 | 低 |
| 5 | 编一个小卷积，取出 HWX | 看 build banner 里的 `-t h18?` 和 memcache-size；看 TD 版本号；看 LC_THREAD 数量（每个引擎一个？） | 低 |
| 6 | 微基准 | 扫 Cout 找 OCG 跳变；扫权重 1.25–6 MB 找工作集阈值；用 [+B, −B, +1] 测归约树 | 无 |

**不可行**：per-TD 计数器、统计 buffer、固件时间戳，用户态都拿不到。

## 10. 书中的矛盾和疑点

1. M1 的 12 TFLOP/s 斜率，高于"4 核 × 4 通道/周期 × 1.14 GHz"能解释的量级。所以"输出通道"应该是向量单位，书中没有展开。
2. MAC 饱和问题到哪一代修复：§3.7 说 A15，§12.4 说 M5。
3. fp16 kernel 宽度上限：一处说 A14 起是 16，另一处说 A16 起是 15。
4. HAL 大小：0x938 和 0x348 两种说法。
5. M5 的 base 型号是 H17s 还是 T605x（Pro/Max）是 h17s，书中前后不一。
6. `ANEFamilyToMLIR` 把 HW version 10 映射为 "A17（h18）"，疑似错误。
