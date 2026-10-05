# M6（h18g）编译产物 HWX 分析

- 日期：2026-10-02
- 编译器：zin_ane_compiler v10.26.6（macOS 27.0.1）
- 测试模型：3 层 1×1 卷积 + relu，64 通道，输入 [1, 64, 64, 64]，fp16。由 `data/03_compile/hwx/mk.py` 生成，MIL 源码在 `data/03_compile/hwx/model.mil`。
- 编译方式：在自己的进程里直接调用 `ANECCompile`（`tools/common/anecc.m`），不经过 aned。
- 解析工具：`tools/lib/hwx_parse.py`
- 产物：`data/03_compile/hwx/<目标>/model.hwx`

## 1. 各目标的格式

| 目标 | subtype | 文件大小 | load command 数 | 格式 | 有无 bonded |
|---|---|---|---|---|---|
| h16g（M4） | 7 | 96 KB | 14 | 传统格式（书里描述的那种） | 无 |
| h17s（M5） | 9 | 96 KB | 14 | 传统格式 | 无 |
| h18 | 10 | 96 KB | 14 | 传统格式 | 无 |
| **h18g（M6）** | **11** | 128 KB | 8 | **新格式：有 `__RUNTIME` 段（RTGraph）** | **有** |
| h19 | 11 | 128 KB | 8 | 新格式 | 有 |

- M6 的 ioreg 报 `ANECPUSubType = 11`，和 h18g 一致，所以 **M6 实际运行的是 h18g 格式**。
- h18（subtype 10）和 h18g 是两个不同的目标：h18 是同一代 ANE 的单引擎版本（用户指出：H18 这一代对应的手机芯片是 A20，其 ANE 与 M6 相同）。

## 2. h18g 的文件结构

```
__PAGEZERO
__RUNTIME  0x30000000  __runtime（0x102c B）   运行时操作图（RTGraph）
__TEXT     0x30004000  __text（0x84b8 B）      三段任务描述符（TD）流：
             0x30004000  nonbonded（只用 ANE0）
             0x30008000  bonded，在 ANE0 上跑的部分
             0x3000c000  bonded，在 ANE1 上跑的部分
           __const
__KERN_0   0x30014000  __kern_0（0x6c00 B）    权重，两个 ANE 共用同一份
LC_IDENT   编译器版本、编译参数（-t h18g --fno-fold-scale=true ...）
LC_NOTE    src model info / rt.version
LC_SYMTAB  111 个符号
```

### 运行时操作图（`__RUNTIME`）里的符号

| 过程 | 包含的操作 |
|---|---|
| `main` | 入口 |
| `main__nonbonded` | 映射权重 → 映射输入 / 输出 → 映射 ane0 的 text → `rt_op_ane_kick_..._ane_0`（启动一次） |
| `main__bonded` | 把同一份权重分别映射给 ane0 和 ane1 → 输入 / 输出分别映射给两个 ANE → 两段 text 各自映射 → `rt_op_ane_kick_..._ane_1` 和 `rt_op_ane_kick_..._ane_0`（**两个 ANE 各启动一次**） |

由此可见，同一个编译产物里同时装着单 ANE 和双 ANE 两种执行方案，由运行时选择用哪一个。

## 3. 权重布局：证实每个 ANE 有 16 个 NE

- 每层的权重都切成 16 份：`K<sha256>_ne_0` 到 `_ne_15`，每份 0x240 字节。
  - 64 个输出通道 ÷ 16 = 每个 NE 负责 4 个输出通道；
  - 4 × 64（输入通道）× 2 B = 512 B，加上 bias 和对齐，正好 0x240 = 576 B。
- 和书里的说法一致：**按输出通道分给各个 NE**。
- 每个 TD 里有 16 个连续的配置字（`00000021`、`00010021` 等），推测是这 16 个 NE 各自的权重 DMA 配置。

## 4. bonded 怎么分工：按空间高度切成两半

对比 nonbonded、bonded ane0、bonded ane1 三段 TD 流（每层一个 TD，共 3 个，每段约 0x4ac 字节）：

| 位置 | nonbonded | bonded ane0 | bonded ane1 | 含义（推测） |
|---|---|---|---|---|
| 每个 TD 的 +0x108 / +0x118 / +0x120 | 0x40（64） | 0x20（32） | 0x20（32） | **高度 64 → 32** |
| 0x158 / 0x2e8 / 0x438 | 0x82000 | 0x41000 | 0x41000 | 数据量减半 |
| 0x44c | 0x104000 | 0x82000 | 0x82000 | 同上 |
| 0x014 / 0x1b4 / 0x314 | 4 / 2 / 6 | 2 / 1 / 3 | 2 / 1 / 3 | 计数减半（分块数？） |
| ane1 在输入 DMA 处多一个字（0x14c） | — | — | **0x20 = 32** | **从第 32 行开始读** |
| ane1 在输出 DMA 处多一个字（0x478） | — | — | **0x20 = 32** | **从第 32 行开始写** |
| 0x198 / 0x49c | 0x2380… / 0x2300… | 0x2580… / 0x2500… | 同 ane0 | 同步或标志位不同 |

结论：
- 对于这种逐点卷积链，**bonded 模式把图按高度（H）切成上下两半**：ANE0 算第 0–31 行，ANE1 算第 32–63 行。两边用同一份权重，每个 ANE 都用满自己的 16 个 NE。
- 1×1 卷积不需要两个 ANE 之间交换数据，所以 TD 里没有出现跨 ANE 的等待。
- 3×3 卷积、矩阵乘、attention 这类需要交换数据或拆不开的运算，编译器会怎么切，还要另外实验（编译器里有 GenericDAG 拆分、ForceTMWaitForInterAneDependencies 等）。

## 5. 后续

1. 编 3×3 卷积、matmul、注意力、LLM 一层，看 bonded 的切法，以及有没有跨 ANE 的等待。
2. 实测：同一个模型分别强制走 nonbonded 和 bonded，比较速度。
3. 看 Core ML 编译的模型在运行时到底选了哪一个（用 anemon 看两个 ANE 的忙碌度）。
4. 逐字段解码 TD（结合 `ZinAneTdHw_v*` 的寄存器名）。

## 6. 不同运算在 bonded 模式下的切法（2026-10-02，只编译不运行）

- 用例由 `tools/lib/bonded_cases.py` 生成，用 `tools/lib/hwx_bonded.py` 汇总。
- 产物在 M6 的 `~/anehal/hwx/cases_out/`。

| 用例 | bonded 时用几个 ANE | 共享暂存内存（shared_bss） | 说明 |
|---|---|---|---|
| 1×1 卷积，64 通道，64×64，3 层 | 2 | 无 | 按高度对半切，两边各 32 行 |
| 1×1 卷积，512 通道，32×32，8 层 | 2 | 无（各自有私有 bss） | 两个 ANE 的 TD 流长度接近（0xbdc / 0xbf4） |
| 3×3 卷积，64 通道，64×64，3 层 | 2 | **有** | 每个 ANE 输出 32 行，但输入要读 **33 行**（多 1 行 halo）。TD 里多出一组配置字，疑似通过共享内存交换边界行并做同步 |
| 1×1 卷积，1024 通道，1×64（只有一行） | **1**（只有 ane0） | — | 没法按高度切，编译器也不按通道切 |
| 1×1 卷积，1024 通道，1×1 | **1** | — | 同上 |
| 矩阵乘，常量权重，M=1，K=N=2048 | **1** | — | 和 LLM decode 的形状一样，不切 |
| 矩阵乘，常量权重，M=64，K=N=1024 | **1** | — | 不切 |
| 矩阵乘，两个动态输入，8 批 128×64×128 | 2 | **有** | ane0 的流（0x2d8）比 ane1（0x1fc）长，分工不对称 |
| softmax 沿宽度，64×64×256 | 2 | **有** | 两边 TD 流长度相同（0x448），比 nonbonded（0x6f8）短 |
| reduce_sum 沿高度，64×64×64 | 2 | **有** | 分工不对称：ane0 0x2e4，ane1 0x110。推测 ane1 算一半的部分和，经共享内存交给 ane0 做最终合并 |

### 初步规律

1. **只沿空间维度切**（这几个用例里都是 H；后来发现 H=1 且 W≥256 时会沿 W 切，见 `bonded_measure.md`）。空间很小的张量（例如 1×64、1×1，以及 LLM decode）和 M 很小的 matmul，在 bonded 模式下也只用 ANE0。也就是说，**单个小 batch 的 matmul 不会因为有两个 ANE 而变快**。
2. 每一层都只依赖自己那一半的运算（逐点卷积链），两个 ANE 之间不需要通信，也没有共享内存。
3. 需要跨半边数据的运算（3×3 卷积的 halo、沿 H 归约、softmax、动态 matmul）会分配**两个 ANE 共享的 bss**（`rt_op_alloc_bss_for_ane16383`、`map_shared_bss__ane0/ane1`），TD 里多出疑似同步的记录。
4. bonded 时每个 TD 头部的 0x30 字从 `00050001` 变为 `00050041`（多了 bit 6），疑似"bonded / 需要同步"的标志。

### 和实测数据的关系（待验证）

- M6 上 INT8 峰值的测试用的是大空间尺寸的卷积链，会被切到两个 ANE 上。这能解释为什么测到 85–91 TOPS，约为 M4 的 2.3 倍。
- 按这个规律，LLM decode（M=1）在 bonded 模式下也只跑在一个 ANE 上，所以 decode 速度主要靠单个 ANE 的权重读带宽。

### 实测（2026-10-02）

见 `notes/bonded_measure.md`：
- Core ML 运行时只要有分到两个 ANE 的 bonded 版本就会用它。
- 单个 ANE 的 fp16 边际吞吐约 20.6 TFLOPS，两个 ANE 约 39.5 TFLOPS（1.92×）。
- 权重要从 DRAM 读时，两个 ANE 各读一份权重，收益降到约 1.4×。

## 7. 双引擎的共享内存和同步记录（A5，2026-10-02）

材料：`data/03_compile/hwx_cases/`（c1x1、c3x3、reduce_h、softmax_w 四个用例的 h18g 编译产物）。

### 7.1 运行时操作图

需要两个 ANE 交换数据的用例（3×3 卷积、沿高度归约、softmax），bonded 过程多出：

| 运行时操作 | 推断 |
|---|---|
| `rt_op_alloc_bss_for_ane16383_P_main__bonded` | 16383 = 0x3FFF，像是"所有 ANE"的掩码：分配一块两个 ANE 共享的暂存区 |
| `rt_op_map_shared_bss__ane0/1_P_main__bonded` | 把这块共享区分别映射给两个 ANE |
| `rt_param_main__bonded_ane_{0,1}_hi_replaceable_dsid_usage_dsid_relocation` | 每个 ANE 一个 DSID（SoC 系统级缓存给数据流打的标签）重定位参数。编译器里还有 `McacheHiBondedKernelReadDSID`。推测**两个 ANE 交换数据经过 SoC 的系统级缓存（SLC），而不是两者之间的专用通道** |

沿高度归约时，**输入 x 和输出只映射给 ANE0**，ANE1 只有共享区和自己的程序：ANE1 算一半的部分和写进共享区，由 ANE0 汇总并负责输入输出。

### 7.2 TD 流里的变化（bonded 相对 nonbonded）

| 位置 | nonbonded | bonded | 推断 |
|---|---|---|---|
| 每个 TD 的头部字（流内 0x10） | 0x0068xxxx | ANE0 0x0070…、ANE1 0x0075…，逐个 TD 加 1 | TD 编号，两个 ANE 不重叠，像是全局唯一的任务 ID |
| 0x30 | 0x00050001 | 0x00050041 | 第 6 位 = bonded 标志 |
| 0x3c–0x7c（16 个 NE 配置字） | 0x00000021 | 0x00010021 | 第 16 位在 bonded 时全部置 1 |
| 0x14 | 0xe | 0x7 | 计数减半（按高度切半） |

### 7.3 同步记录

在所有 TD 流里找最高 4 位为 f 的字：

| 字 | 出现位置 | 推断 |
|---|---|---|
| `ffc01540` | 每个卷积 TD 内的固定偏移 0x34 | TD 头的一部分 |
| `f0003211` | 每条流的末尾各一个（单 / 双 ANE 都有）；归约、softmax 的流里会出现多次 | 阶段结束 / 通知 |
| **`f0003281`** | **只出现在需要交换数据的 bonded 流里** | **跨 ANE 同步（屏障）** |

数量和需要交换数据的次数一致：

| 用例 | 每个 ANE 的 `f0003281` 个数 | 说明 |
|---|---|---|
| 1×1 卷积 ×3（bonded） | 0 | 两半互不依赖 |
| 3×3 卷积 ×3（bonded） | **2** | 第 2、3 层开始前都要拿到对方算的边界行；第 1 层直接从 DRAM 读带 halo 的输入 |
| softmax 沿宽度（bonded） | 1 | |
| 沿高度归约（bonded） | 0；ANE0 有 3 个 `f0003211`，ANE1 有 1 个 | 用分阶段的方式等待，而不是屏障 |

记录格式（前后的字）：

```
c0301440  010N00e1  00000400  00010000  f0003281  ...    跨 ANE 同步，N = 同步点序号（1、2…）
c0301440  010N0021  00000080  00002000  f0003211  ...    结束记录，低字节 0x21
ANE1 的这两类记录后面都多两个字：00001457 00000020（ANE0 没有）
```

- 第二个字的第 2 字节是递增序号；低字节 0xe1 表示跨 ANE 同步，0x21 表示普通结束。
- ANE1 多出的 `00001457 00000020` 推测是 ANE1 通知 ANE0（或主机）用的信号量编号和计数。
- 这和 maderix 说的"HWX 里只有 DMA、计算、同步、终止四类记录"、以及论文的 WAIT / WAIT_EXT 对应：`f0003281` 应该就是双引擎版本的 WAIT_EXT。
- 局限：没有执行修改后的程序，字段含义只是根据"出现在哪里、出现几次"推断出来的。

## 8. 逐元素运算的操作码（A6，2026-10-02）

"1×1 卷积 → 双输入逐元素运算"的融合层，5 种运算的 TD 流长度相同（0x294），只有流内 0x240 这个字有实质差别（另有两个字是输入缓冲区地址的交换）：

| 运算 | 0x240 | 第 2–3 位 | 第 18 位 |
|---|---|---|---|
| add | 0x00080000 | 0 | 0 |
| sub | 0x000c0000 | 0 | **1** |
| mul | 0x00080004 | 1 | 0 |
| maximum | 0x00080008 | 2 | 0 |
| minimum | 0x0008000c | 3 | 0 |

- 操作码是一个 2 位字段：0 加、1 乘、2 取大、3 取小。
- 减法 = 加法 + 第二个输入取反（第 18 位）。
- real_div 的流更长（0x338），推测拆成"倒数（查表 + 区间归约）+ 乘法"。
- maderix 说"一个操作码字节、256 种 ALU 运算"。在这种融合层里只看到 4 种基本运算加一个取反位，其他层类型可能用到更多编码，未覆盖。

## 9. TD 字段布局与流水线各级（A4，2026-10-02）

### 9.1 方法

- 编译器里每一版 TD 布局有一个类 `ZinAneTdHw_vN`（v4–v36），字段读取函数是 `ZinGetRegisterProgramming<N>::GetXxx(const ZinAneTdHw_vN&)`。各版本的方法数：v8–v20 约 53 个，v24–v31 约 58–61 个，v36 有 67 个。
- 用 `tools/re/fnbytes.c` 导出 v31、v36 全部读取函数的机器码并反汇编（`td31.dis`、`td36.dis`；编译器反汇编，不公开，只留本地 private/；可用 `tools/re/fnbytes.c` 重新生成）。每个函数基本就是"从 TD 对象的某个偏移读一个字，再取若干位"，由此得到每个字段的偏移和位宽。
- 汇总：`data/03_compile/td_field_offsets.txt`。偏移是编译器内存对象里的偏移，不一定等于硬件寄存器地址，但字段的先后顺序和分组可以参考。

### 9.2 v36 的字段布局（按偏移排序）

| 偏移 | 字段（位） | 推断的硬件单元 |
|---|---|---|
| 0x6 | TaskSize（[10:0]） | 任务头 |
| 0x8–0x9 | Tsr（bit0）、Tde（bit1）、Xtde（0x9 bit3）、PublishBit（0x9 bit4） | 任务头 |
| 0x2ec | MxInFmt [3:0]、MxSrc2InFmt [7:4]、MxOutFmt [11:8] | 数据格式（v36 新增） |
| 0x2f0–0x30c | Win、Hin、Cin、Din、Wout、Hout、Cout、Dout（各 17 位） | 公共：张量形状 |
| 0x310 | NumGroups（17 位） | 公共 |
| 0x334–0x335 | Src1/Src2 的 C/H/W/D 广播、转置；输出转置 | 公共 |
| 0x338 | CommonTaskType [3:0] | 公共：任务类型 |
| 0x354 / 0x358 | TileDma Src1 / Src2：Enabled（bit0）、DoubleRate（bit31） | 输入 Tile DMA |
| 0x404 / 0x408 | Src1 / Src2：FormatMode [1:0]、Interleave [7:4] | 输入 Tile DMA |
| 0x414 / 0x424 | Src1 / Src2 Compressed | 输入 Tile DMA |
| 0x420 / 0x430 | CropOffsetSrc1Y / Src2Y（16 位） | 输入 Tile DMA |
| 0x45c | TextureMode [2:0]（TexModeEnabled） | 纹理单元 |
| 0x460 | Gather 索引维度：W [2:0]、H [5:3]、Plane [8:6]、Depth [11:9]、Group [14:12] | 纹理 / gather |
| 0x46c–0x47c | 纹理源尺寸 | 纹理单元 |
| 0x54c / 0x550 | L2 Src1 / Src2：Ephemeral [1:0]、L2 DMA DoubleRate（bit31） | L2 源 |
| 0x590 | ResultEphemeral | L2 结果 |
| 0x5c0 | CircularBuffer Src1 [2:0]、Src2 [6:4]、Result [10:8] | L2 环形缓冲 |
| 0x5ea | PEIndexingEnabled | 平面引擎 |
| **0x660** | **NEAccBiasShift（bit11 起）、NEPostRightShift [23:19]（5 位）** | **NE（MAC 阵列）** |
| 0x69c | TileDmaDst Enabled | 输出 Tile DMA |
| 0x700 | Dst FormatMode [1:0]、OutputInterleave [7:4] | 输出 Tile DMA |
| 0x708 | Dst Compressed | 输出 Tile DMA |
| 0x71c | CropOffsetDstY | 输出 Tile DMA |

v31 的布局相同，只是 0x274（Win）起整体比 v36 前移 0x7c，之后各段前移 0xbc–0xf8：v36 在形状字段之前插入了 31 个字，后面又有几处插入。v36 新增的只有 MX 格式和三个 TileDma Enabled 位。

### 9.3 结论

1. 按偏移排列的字段顺序就是一条流水线：**任务头 → 公共（形状、任务类型） → 输入 Tile DMA → 纹理 / gather → L2 源 / 环形缓冲 / PE → NE → 输出 Tile DMA**。和论文从 M1（v10）寄存器分组得到的数据流（DRAM → L2 → NE → L2 → PE → DRAM）一致。
2. **NE 有"累加器偏置移位"和 5 位"输出右移"字段**，正好是定点累加器（`numerics.md`：Q15.16、溢出 ±32768）需要的配置：累加在定点里做，输出时右移、转 fp16。
3. 双倍速率（DoubleRate）字段在 v24 就已出现（Tile DMA 和 L2 DMA 各有），v26 起一直保留。H19 参数表里的 `CanEnableDoubleRateMode` 是打开它的开关。
4. **MX 格式（v36 新增）**：输入、第二输入、输出各 4 位格式码，对应 OCP Microscaling（MXFP8 / MXFP6 / MXFP4 / MXINT8 之类）。
5. ~~版本与架构的对应没有直接证据。推测 H18（M6）= v31、H19 = v36~~ → **已查明（§11.3）：M6（h18g）和 h19 用 v24，h18 用 v20**；v31、v36 对应 subtype 12、14，是编译器里已实现、但还没有对外目标名的架构。本节的 v31 / v36 字段表仍可参考：形状块、卷积配置字、任务信息字在 v19–v31 中位置和位定义完全相同。


## 10. 卷积配置字（2026-10-03；从 v31 的函数解出，M6 实际用的 v24 与之相同，见 §11.3）

- 来源：反汇编编译器 `ZinAneTd<31>::SetCommonConvCfg*`（`tools/re/fnbytes.c` 导出机器码，`as` + `otool` 反汇编）。每个函数把参数写进 TD 对象偏移 0x2a0 或 0x2a4 的若干位（`bfi` / `bfxil`）。
- 0x2a0（"ConvCfg"）：

| 位 | 0–5 | 6–11 | 12 | 13–14 | 15–16 | 17–21 | 22–26 | 27 | 28–29 | 30–31 |
|---|---|---|---|---|---|---|---|---|---|---|
| 字段 | Kw | Kh | 保留 | Sx | Sy | PadLeft | PadTop | 保留 | Ox | Oy |

- 0x2a4（3D）：Kd 0–4、Sz 6–7、Pz 8–11、Oz 13–14。
- 在 HWX 指令流中，每个卷积 TD 有一个按此布局编码的字，例如 1×3 为 `0x5002a043`（Kw 3、Kh 1、Sx 1、Sy 1、PadLeft 1、Ox 1、Oy 1），3×3 为 `0x5042a0c3`。
- 核宽字段有 6 位，但硬件以步长 1 原生执行时核宽上限为 8；核宽 9–15 被编译器改写为 Sx = 2、Ox = 2 的形式（见 compute_array.md B4c 第 6 条）。
- Ox / Oy：每个输入步长产生的输出像素数（x / y 方向输出倍数）。核宽 9–15 时编译器设 Sx = 2、Ox = 2，TD 的输出宽度字段为实际输出宽度的一半，权重存成两套错开一位的核（见 compute_array.md B4c 第 7 条）。
- 卷积 TD 中配置字之前的字段依次为：格式字（对象 0x278：InFmt 0–2、Src2InFmt 3–5、OutFmt 6–8）、输入宽度、行数、输入通道、**未知字 X**（如 `0x93498005`）、输出宽度、输出行数、本 TD 的输出通道数；配置字之后是 TileHeight（0x2ac）、TileOverlap（0x2b0）、任务信息（0x2b4：SmallSourceMode 2–3、TaskType 4–7、Trace 22、L2Barrier 23、1DWinograd 27、OutputTranspose 28、FillLowerN 29、L2ForwardBarrier 30）。指令流基本按编译器对象的顺序写出，省略未用字段（Din、Dout、NumGroups、3D 配置）。
- 每层 TD 数 = ⌈每个 NE 需要的权重 ÷ 64 KiB⌉，推断每个 NE 的权重缓冲区为 64 KiB；与 HAL 0x220"常驻权重上限" = 64 KiB 一致（compute_array.md B4c 第 7 点）。

### 10.1 未知字 X（卷积 TD 中 Cin 之后的字）——已解出：是按掩码写的包头，见 §11.1

- 样本（`data/03_compile/xword_samples.txt`、`data/03_compile/td_1x8_full.txt`，工具 `tools/03_compile/xword.py`、`tools/03_compile/tddump.py`）：

| 模型 / TD | X |
|---|---|
| 1×1、1×3、1×9、1×15（各 TD）；3×3 的 224 通道 TD；3×3（512 通道，FP16）的 96 通道 TD | `0x91498005` |
| 1×8；9×1（各 TD）；3×3 的 32 通道 TD；膨胀 3×3（各 TD） | `0x93498005` |
| 3×3（512 通道，W8A8，各 TD） | `0xb3498005` |
| 2 层模型（`data/03_compile/c1_hwx/`） | `0x93491005` / `0x91491005` |

- 已能确定的位：
  - **第 29 位与数据类型有关**：同一 3×3 模型的 W8A8 版本比 FP16 版本多这一位；
  - **第 25 位按 TD 变化**：同一层被按输出通道拆成两个 TD 时可以一个为 1、一个为 0（3×3：32 通道 TD 为 1，224 通道 TD 为 0）；9×1 两个 TD 都为 1；横向核（含改写的）都为 0。规律未找到；
  - **第 12–15 位**：2 层模型为 1，8 层及以上的模型为 8。
- 未能定位来源：按指令流顺序它落在编译器对象的 Din（0x288）位置，但 v31 的 509 个 `ZinAneTd<31>` 函数中只有 `SetOrReturnDin` 写 0x288，且只写低 17 位（X 的低 17 位为 0x18005，不可能是 Din）；编译器代码中也没有直接装入 0x9349 / 0x9149 等常量的指令（`tools/re/immscan.c`）。推测 X 是序列化时拼出的硬件寄存器，或对应对象中没有一一映射的寄存器。要彻底解码，需要先解析指令流的打包格式（包头如何编码寄存器地址和数量，例如 `000f1559` 后跟 16 个 NE 的权重偏移），再找到序列化函数。

## 11. 指令流的打包格式与 TD 布局版本（2026-10-03）

### 11.1 包头格式（已解出）

- 每个 TD 开头 12 个字是任务头（未逐位解析），之后是一串"包头 + 值"的寄存器写入包：
  - 包头低 15 位 = 起始寄存器的字地址；
  - **bit 31 = 0：连续写**，bits 15–30 = 个数 − 1，后跟"个数"个值。例如 `00031551`：从 0x1551 起写 7 个；`000f1559`：从 0x1559 起写 31 个（16 个 NE 的权重偏移等）；`00010001`：从 1 起写 3 个（Win、Hin、Cin）。
  - **bit 31 = 1：按掩码写**，bits 15–30 是 16 位掩码，写基址本身以及"基址 + 1 + i"（掩码第 i 位为 1），后跟 1 + popcount(掩码) 个值。例如 `80c11340`：基址 0x1340，掩码 0x182，写 0x1340、0x1342、0x1348、0x1349 共 4 个。
  - bit 31 = 0 且 bits 26–30 非零的字（如 `0x23009346`、`0x22801344`）不是包头，出现在 TD 末尾，含义未知（可能是另一种命令）。
- **§10.1 的"未知字 X"就是按掩码写的包头**：`0x91498005` = 基址 5（Wout），掩码 0x2293 → 写寄存器 5、6、7、10、13、15、19 共 7 个值：Wout、Hout、Cout、卷积配置字、TileHeight、任务信息、寄存器 19。
  - 所谓"bit 29 与 W8A8 有关"，就是 W8A8 时多写一个寄存器（基址 + 15 = 20）；"bit 25 逐个 TD 变化"，就是寄存器 16 写或不写；
  - 2 层模型的 `0x93491005`：基址 0x1005（另一块地址），掩码最低位为 0。
  - 这也解释了为什么在编译器对象里找不到 X：它不是寄存器值，是序列化时根据哪些字段非零拼出来的包头。"省略未用字段"靠的就是掩码。
- 形状块的寄存器号 n 与 v31 编译器对象偏移的关系：setter 偏移 = 0x278 + 4n（ConvCfg 0x2a0 = 寄存器 10，TileHeight 0x2ac = 13，任务信息 0x2b4 = 15）。
- 工具：`tools/lib/tdpkt.py`（按包头解析一个 TD，输出"寄存器地址 → 值"）。

### 11.2 各编译目标的寄存器布局（同一模型 k1x9_c256_h8w32_L4，`data/03_compile/tdv/<目标>/model.hwx`）

| 组 | 目标（HWX subtype） | L2 块写入地址 | NE 块写入地址 | DMA 块 |
|---|---|---|---|---|
| ① | h15、h15g（6），m11（8） | 1342 1346 1347 135a | 1240 1241 1244 | 1041–1047、104d、104f、1050 |
| ② | h16、h16c、h16g、h16s（7），h17、h17a/c/d/g/s（9） | 同 ① | 同 ① | 1041 1042 1044–1048 1052 1054 1055 |
| ③ | **h18**（10） | **1340 1342 1348 1349 135c** | 1240 1241 1244 | 同 ② |
| ④ | **h18g（M6）、h19**（11） | 同 ③ | **1240 1242 1245** | 同 ② |

- h13、h14、m12、u1–u4 的格式与此不同（解析器未覆盖）；m9、t0 编译失败；t1 的输出为空。
- **h18g 与 h19 的指令流几乎逐字相同**（17948 字节，差异只在任务头的一个字段和一处 TD 末尾命令字）；**h18（单引擎）与 h18g 的 NE 块不同**（第一个寄存器之后多一个寄存器），L2 块相同；h17 → h18 的变化在 L2 块（插入两个寄存器）。
- 卷积核改写规则也随代际变化：h16g / h17 把 1×9 写成 Kw = 9（`0x6008c049`），h18 起写成 Kw = 10（`0x6008c04a`，核宽 + 1 再补成偶数）。

### 11.3 与编译器 TD 版本（ZinAneTd&lt;N&gt;）的对应——已查明

- 查找路径（工具 `tools/re/adrref.c`、`tools/re/jtab.c`、`tools/re/tblread.c`、`tools/re/xref.c`，均在 M6 上对已加载的 ANECompiler 只读扫描）：
  1. `ZinAneTd<N>` 的构造函数被内联，用 `adrref`（找 ADRP + ADD / LDR 计算出的地址）查 vtable `__ZTV8ZinAneTdILj<N>EE` 的引用，得到创建 TD 对象的函数 `CodegenCreateInstructions<N>`。
  2. 它们的唯一调用者是 `arch_dispatch<CodegenCreateInstructionsDispatcher>(AneArchEnum, …)`：按 `AneArchEnum − 1` 查 36 项跳转表，`jtab` 解析得：编号 1、4、5、6、7、8、10、11、17、19、20、24、26、28、31、36 各跳到 `CodegenCreateInstructions<同一编号>`，其余编号断言失败。**模板参数 N 就是 `AneArchEnum` 的值**。
  3. `AneArchEnum` 由 `ZinCpuSubtypeToArchValue(int)` 从 HWX CPU subtype 换算而来（21 项查表，编译器里有 5 份相同的副本），subtype 存在 HAL 参数表偏移 0x8（`hal_*.bin`：H13 = 4、H16 = 7、H17 = 9、H18 = 10、2026BaseLine（即 h18g 用的 HAL）= 11、H19 = 11、M12 = 17、U1–U4 = 15、18、19、20）。
  4. 目标名 → 类：`ZinIrTargetCreator::CreateTargetFromString` 按字符串构造 `TargetH18g` 等；`TargetH18g` 的 HAL 是 `ZinIrHal2026BaseLine`（参数表即 `hal_2026BaseLine.bin`），`TargetH18`、`TargetH19` 分别用 `ZinIrHalH18`、`ZinIrHalH19`。

- **subtype → TD 版本**（`ZinCpuSubtypeToArchValue`）及已知目标：

| subtype | 0 / 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | **10** | **11** | 12 | 14 | 16 | 17 | 13、15、18–20 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TD 版本 | v5 | v4 | v6 | v7 | v11 | v8 | v17 | v10 | v19 | **v20** | **v24** | v31 | v36 | v28 | v26 | 1（无） |
| 目标 | H11（1） | T0 | H12 | H13、T1 | H14 | H15 | H16（M4 = h16g） | M11 | H17 全系 | **h18** | **h18g（M6）、h19** | — | — | — | M12 | U1–U4 等 |

- 代际先后（`ArchCompareValue`，越大越新）：v5 = 2、v6 = 3、v7 = 4、v11 = 5、v8 / v10 = 6、v17 = 7、v19 = 8、v20 = 9、**v24 / v26 = 10**、v28 = 11、v31 = 12、v36 = 14。
- 结论：
  1. **M6（h18g）用 v24**；h19 也用 v24（同一 subtype 11），所以两者的指令流几乎相同（§11.2）。h18（单引擎）用 v20。原先"M6 = v31、H19 = v36"的推测**不成立**。
  2. **v26、v28、v31、v36 是比 M6 更新、但在这版编译器里还没有对外目标名的架构**（v26 对应 subtype 17 = M12；v31、v36、v28 对应 subtype 12、14、16，目前没有 HAL）。v36 新增的 MX 格式属于其中最新的一代。
  3. 寄存器布局变化与版本对应：h15（v8）→ h16 / h17（v17 / v19）是 DMA 块，v19 → v20（h17 → h18）是 L2 块，v20 → v24（h18 → h18g）是 NE 块，与 §11.2 的观测一致。
  4. 形状块、卷积配置字（Kw / Kh / Sx / Sy / Pad / Ox / Oy、3D）、TileHeight、TileOverlap、任务信息字的偏移和位定义在 v19、v20、v24、v31 中完全相同（`tdver/t19|t20|t24|t31.dis`；编译器反汇编，不公开，只留本地 private/；可用 `tools/re/fnbytes.c` 重新生成），所以 §10 的解码对 M6 有效。
  5. 与 Bryngelson 书中"M5 是 v20"不一致：按此表 H17（M5 一代）是 v19、H18 是 v20。可能是编译器版本不同导致编号变化，或书中的对应有误，未核实。

### 11.4 任务头、"地址包"与重定位（2026-10-03）

- **卷积配置字 bit 12、27 是保留位**：v24 中写这个字的 13 个函数（Kw、Kh、Sx、Sy、PadLeft、PadTop、Ox、Oy，加上复用 PadLeft / PadTop 位的 `HandleCommonArgMinMax`、清 bits 17–26 的 `HandleCommonMACBypassMode`）都不碰 bit 12、27；所有编译产物中这两位都是 0。
- **任务头**（v24 getter `ZinGetRegisterProgramming<24>`）：
  - 指令流开头 4 个字（`1, 0, 0, 0`）是流头；每个 TD 的第 0 个字 = TD 编号（低 16 位）| `TaskSize`（bits 16–26，单位：字）。例：TD0 `0x006d0000` → 109 字，下一个 TD 在 0x1d0；TD1 `0x00710001` → 编号 1、113 字。
  - TD + 0x20 是标志字：`Tsr` bit 0、`Tde` bit 1、`Xtde` bit 5、`PublishBit` bit 6（TD0 为 `0x00050001`，TD1 为 `0x00050009`）。
  - **TD 头各字（2026-10-03 补）**：编译器断言字符串把头部称为 `td_header0`–`td_header11`（一个字一个编号，字段名随版本有出入）。v24：
    | 字 | 名称 | 来源 | 观测 |
    |---|---|---|---|
    | +0x0 | `tid`（低 16 位）、`TaskSize`（bits 16–26，字） | `SetField` | TD 编号、长度 |
    | +0x4 | **`exe_cycles`**（低 16 位） | `HandleTdHeader` → `CalculateExeCycles(layer)`：层对象 +0x1e0 处性能模型估计值取整，上限 0xffff；若该层从 L2 链式读入（`HasChainRead`）则为 0 | 4–0xb；1×9 每层三个 TD 为 7 / 11 / 11，与输出通道 64 / 96 / 96 成正比；单位 ≈ 1 µs（compute_array.md H51：1×1 FP16 TD 的值与按 20.6 TFLOPS 折算的时间一致；模型不计 Winograd，3×3 实测比估计快 1.49 倍） |
    | +0x8 | `log_events` | `SetEventFlags` 第 1 个参数 | 第一个 TD 0x68，最后一个 TD 0x04000000，其余 0 |
    | +0xc | `exception` | | 0 |
    | +0x10 | `debug_log_events` | `SetEventFlags` 第 2 个参数 | 0x00fff800，第一个 TD 低位加 0x68、最后一个加 0x60 |
    | +0x14 | `debug_exception` | | 0 |
    | +0x18 | `dram_log_events` | `SetEventFlags` 第 3 个参数 | 0 |
    | +0x1c | `dram_log_events`（第二个字） | `SetField` | 0x1ff、0x1ff0、0x01ff01ff 等分段变化的掩码 |
    | +0x20 | 标志字 | `SetField`、`SetLdtid`、`SetRdtidOnHeader`、`SetPublishBit`、`SetTdHeaderPerfTraceEn` | bit 0 Tsr、bit 1 Tde、bit 3（只在最后一个 TD）、bit 4 性能追踪、bit 5 Xtde / ldtid、bit 6 PublishBit、bits 16–18 卷积 TD 为 5、逐元素 TD 为 0 |
    - 这三组"事件掩码"决定固件在每个 TD 的哪些时刻记录哪些事件（与 kdebug 里看到的固件任务事件对应）；事件位的具体含义、`ZinLogEventFlags` 的 V1–V7 哪一版用于 v24 未查。
- **TD 末尾的 `0x2xxxxxxx` 字是"地址包"**：
  - 格式与连续写包相同（低 15 位寄存器地址，bits 15–20 = 个数 − 1，后跟相应个数的值），另有 **bit 29 = 1** 作标记，bits 23–28 是标签。
  - 只写 5 个寄存器（`tools/03_compile/hwxreloc.py`、统计 1600 多个包）：0x1544（2 个字，标签恒为 1）、0x1346（2 个字）、0x1444（2 个字）、0x1344（1 个字）、0x1442（1 个字）。值是缓冲区内的偏移（0、0x20000、0x9a400、0x18000、0x40000 等）。
  - **0x1544/0x1545 = 权重 DMA 的 64 位基址**：`__text` 的重定位项（k1x9 16×32 模型 24 项、残差块模型 32 项）全部是 8 字节、目标为 `__kern_0` 节（权重），地址正好是这些包的值字；值是该 TD 的权重块在权重节中的偏移（1×9 每层三个 TD：0、0x9a400、0x181800）。加载时加上权重节的实际地址。
  - **地址包 = 基址寄存器 + BAR 编号**：包头 bits 21–28 整体是 BAR 编号（运行时基址表的槽位；编译器字符串"64-bit relocation, BarIdx must be even"——所有 64 位地址包的编号都是偶数）。两输入两输出模型 `io2`（o1 = relu(conv(x) + y)，o2 = relu(conv(y))，`tools/03_compile/io2.py`、`data/03_compile/l2hwx/io2/`）：

    | 寄存器 | 字段（编译器名称） | BAR | 说明 |
    |---|---|---|---|
    | 0x1544 / 0x1545 | `KernelSrcBaseAddrLo / Hi` | 4 | 权重节（`__text` 中有对 `__kern_0` 的静态重定位） |
    | 0x1346 / 0x1347 | Tile DMA `Src1BaseAddrLo / Hi` | 输入张量 | x → 32 |
    | 0x134c / 0x134d | Tile DMA `Src2BaseAddrLo / Hi` | 输入张量 | y → 36（作为 add 的第二个源） |
    | 0x1444 / 0x1445 | Tile DMA `DstBaseAddrLo / Hi` | 输出张量 | o1 → 24，o2 → 28 |
    | 0x1344、0x1345、0x1442 | Src1 / Src2 / Dst 的 DSID（缓存标签，32 位） | 20 | 对应符号 `…_hi_non_replaceable_dsid_usage_dsid_relocation` |

    - **BAR 编号规则**：4 = 权重，20 = DSID 参数；从 24 起**先输出、后输入**，每个张量占 4 个槽（单输入单输出的模型：输出 24、输入 28；`io2`：o1 24、o2 28、x 32、y 36）。值字里是张量内的偏移（例如 bonded 时 ANE1 从第 32 行开始）。
    - 输入 / 输出地址在 `__text` 中没有重定位，由运行时按 BAR 槽位在每次调用时填入（`__runtime` 节里有 `x`、`o1@output` 等映射项）。
    - 注意：h18（v20）产物里同一寄存器的编号不同（如 0x1544 为 28），BAR 布局随版本变化。
  - **对 §11.2 和 memory.md C1d 的更正**：0x134x 块是 Tile DMA 源（读 DRAM）的寄存器，不是 L2 块；0x1349 很可能是 Tile DMA 源的通道跨步，而不是 L2 通道跨步。
  - 这些包放在每个 TD 的末尾，大概是为了方便加载时集中修补。

## 12. 权重配置字 0x1240（2026-10-05）

**来源**：在 M4 上对同版本 ANECompiler（10.26.6）导出 `ZinAneTd<24>` 全部 518 个函数（`tools/re/fnbytes.c`），反汇编后提取每个 setter 对对象偏移的读改写（不只 bfi / bfxil，也看 orr / and 常量）。字段表 `private/data/03_compile/td24_setters_all.txt`（编译器派生，不公开）。

**寄存器与对象偏移的对应**：v24 的 NE 块按掩码写 0x1240、0x1242、0x1245（§11.2），对应对象 0x4fc、0x504、0x510（每个寄存器 4 字节）：0x1242 = 0x504 是 NE 配置字（`SetOpMode` 0–2、`SetKernelMode` 3、`SetNEBias` 4、`SetPassthroughEnable` 5、`SetNEMatrixVectorBias` 6、`SetNEBinaryPoint` 8–13、`SetNEPostScale` 14、`SetNENonLinearMode` 16–17、`SetMaxPoolMode` 19、`SetArgOutputSelect` 20–23、`SetDoubleInt8Enable` 26、`SetNESmallSourceMode` 27）；0x1245 = 0x510 是 NE 后缩放值。**0x1240 = 对象 0x4fc，是权重（kernel）配置字**：

| 位 | setter | 稠密 FP16 | 剪枝（稀疏格式） | W8 | 4 位调色板 |
|---|---|---|---|---|---|
| 0–1 | `SetKernelFmt`（权重数据类型） | 2 | 2 | 1 | 2 |
| 2 | `SetKernelPalettizedEn` | 0 | 0 | 0 | 1 |
| 4–7 | `SetKernelPalettizedBits`（1 / 2 / 3 / 4 / 6 / 8） | 8 | 8 | 8 | 4 |
| **8** | **`SetKernelSparseFmt`** | 0 | **1** | 0 | 0 |
| 10 | `SetGroupKernelReuse` | 0 | 0 | 0 | 0 |
| 15 | `SetKernelSparseBinary` | 0 | 0 | 0 | 0 |
| 16 | `SetKernelAlignmentFormat` | 0 | 0 | 0 | 0 |
| 17–18 | `SetAlignedKernelBias` | 0 | 0 | 0 | 0 |
| 19–20 | `SetAlignedKernelPostScale` | 0 | 0 | 0 | 0 |
| 21–23 | `SetKernelSparseBlockSize` | 0 | 0 | 0 | 0 |
| 24 | `SetKernelAsymQuantEn` | 0 | 0 | 0 | 0 |
| 25–27 | `SetPaletteBlockSize` | 0 | 0 | 0 | 0 |
| **28** | **`SetKernelDetectZeros`** | **1** | **0** | 1 | 1 |

（实测值：稠密 0x10000082，稀疏 0x182，W8 0x10000081，4 位调色板 0x10000046；c1x1、512 通道，`tools/05_compute/kfmt_gen.py`，h18g。）

- `SetKernelSparseFmt` 同时置对象 0x3c 第 5 位；实测权重 DMA 配置寄存器 0x1540 由 0x10040 变为 0x10060，所以 **0x1540 = 对象 0x3c（`KernelDmaSrc` 配置）**，第 5 位 = 稀疏格式，第 11–13 位 `SetPaletteBlockSize`、第 4 位 `SetGroupKernelReuse` 也在这里各有一份。
- `SetKernelDetectZeros` 对应编译器 MLIR 方言 `polylang::anehlo` 里的 `DetectZerosOp`（`NEOp` 的修饰操作），是正式的硬件功能。**稠密格式（含 W8、调色板）一律打开，稀疏格式关闭**。
- **稠密存放的零权重不会被编译器改成稀疏格式**：同一模型权重 50% / 75% / 90% / 100% 为 0（MIL 里是普通常量），权重段、0x1240、exe_cycles 与随机权重完全相同。
- **DetectZeros 不带来明显加速**（M4，c1x1，32 → 128 层调用耗时斜率，最干净的一遍）：随机 4.07 µs / 层，50% / 75% / 90% / 100% 为 0 时 3.91 / 3.74 / 3.73 / 3.75（至多 −8%）；同比例的稀疏格式（剪 75%）2.02。另两遍里 dz 版本的 128 层有 1.5–2 倍的跳变（随机、调色板、稀疏版本没有），原因未查，可能与零权重降低功耗后时钟策略的变化有关。推测 DetectZeros 用于省电（与 power.md §7.3 零激活省电不省时一致），未测功耗。
- 由此，14.4 节的 55.6 TFLOPS 也不能用"稠密权重里有大量 0"解释：要靠零权重加速，权重必须以稀疏格式（constexpr_sparse_to_dense）交给编译器。原因仍未查明。
- 一个 constexpr_sparse_to_dense 但一个 0 都没有的模型，编译器按稠密处理（权重段为稠密大小），且不写 0x1240。

## 13. TD 字段的动态跟踪（2026-10-05）

**方法**（`tools/03_compile/tdtrace_gen.py`、`tdtrace_lldb.py`、`tdtrace.sh`、`tdtrace_fit.py`）：在 M4 上用同版本 ANECompiler 以 h18g 为目标编译 35 个 2 层小模型（各种卷积核 / 步长 / 膨胀 / 分组 / 深度、转置卷积、激活函数、BN、稀疏、调色板、W8、W8A8、linear、matmul、逐元素、池化、归约、softmax、layernorm、concat、transpose、pad、上采样、bonded），lldb 在 `ZinAneTd<24u>` 的 403 个方法上设断点（另 72 个与其他函数共用地址，禁用），记录每次调用的参数、调用者、层级，以及调用前后 TD 对象按寄存器地址换算的每个字的变化。寄存器地址 → 对象偏移来自 `ZinAneTdHw_v24::GetRegisterValueFromAddress` 的反汇编（8 块：0x0000 → 0x238、0x1040 → 0x400、0x1140 → 0x4b4、0x1240 → 0x4fc、0x1340 → 0x29c、0x1440 → 0x53c、0x1540 → 0x3c、0x1640 → 0x5b8，均为 setter 所见的对象偏移）。
- 要点：anecc 需签 `get-task-allow`（`tdtrace_ent.plist`），不需要开发者模式；编译器多线程，不能依赖 lldb 断点回调（多个线程同时停下时回调偶尔不执行、进程停住），改为脚本循环逐个处理停下的线程。2 层模型每个 10–60 s。
- 结果：35 个模型全部编译成功，226 个方法被调用 47508 次，134 个方法有可见的寄存器改动，覆盖 167 个寄存器。原始记录与函数表（编译器派生）在 `private/data/03_compile/tdtrace/`。
- 校验：由跟踪还原的寄存器取值与 HWX 中的值 89%（2513 / 2832）一致；不一致集中在地址类寄存器（0x1041、0x1042、0x1052、0x1440、0x1642）与 0x1540，它们在 TD 生成之后由地址分配 / 重定位等其他代码改写，不在跟踪范围内。值没变的写入在快照里看不出，字段范围要结合静态 setter 表（§12）。

**解出的字段取值**（参数为传给 setter 的值）：

| 方法 | 寄存器位 | 取值 |
|---|---|---|
| `SetKernelFmt` | 0x1240 [1:0] | FP16 = 2，int8 权重（W8、W8A8）= 1 |
| `SetKernelPalettizedBits` / `En` | 0x1240 [7:4] / [2] | 参数枚举：默认 4，int8 = 1，4 位调色板 = 0x15，2 位 = 0xd |
| `SetKernelSparseFmt` | 0x1240 [8]，0x1540 [5] | 剪枝模型为 1；**1×9 卷积、膨胀 3×3、步长 2 卷积也为 1** |
| `SetKernelDetectZeros` | 0x1240 [28] | 稀疏格式、softmax、layernorm 为 0，其余为 1 |
| `SetOpMode` | 0x1242 [2:0] | 卷积 0；concat、linear、pad、transpose、layernorm 为 6；softmax 中有 3 |
| `SetNENonLinearMode` | 0x1242 [17:16] 等 | 无激活 0、ReLU 1、sigmoid 2、tanh 6、GELU 0x22；softmax 0x12 / 0x15 |
| `SetCommonConvCfgKw` | 0x000a [5:0] | 1 / 3 / 5；1×9 写成 10；池化 2 |

- **稀疏权重格式被编译器内部用来实现带零的改写核**：1×9 改写成核宽 10（§11.2，补零）、膨胀卷积展开成带零的大核、步长 2 的改写，都打开 `KernelSparseFmt`，用跳零硬件省掉补出来的零。这解释了 compute_array 中"改写核的耗时与权重元素数成正比"（wfmt 第 3 点）和"膨胀卷积按展开核计"（H10）。
- `SetKernelDetectZeros` 只由 `HandleNEConfig` 调用；稀疏格式下关闭，与 §12 一致。
- 全部 226 个方法的改动位、各模型参数与调用者见 `private/data/03_compile/tdtrace/setters.txt`、`regmap.txt`、`matrix.txt`；逐个字段的语义解读尚未完成。

### 13.1 寄存器手册（自动合成 + 解读，2026-10-05）

- 静态位掩码改用 `tools/re/tdstatic.py`：跟踪每个方法里"ldr 对象字 → and / orr / bfi / bfxil → str 回同一偏移"，把清零与置位的位都并进去（§12 只取了 bfi / bfxil，漏掉单个标志位）。v24 共 270 个方法、148 个寄存器。
- `tools/03_compile/tdmanual.py` 把静态位掩码、动态跟踪（参数、调用者）和 35 个模型 HWX 的实际取值按"寄存器 → 位段"合并成手册（`private/data/03_compile/td24_manual.md`，编译器派生，不公开）：312 个位段，其中 104 个随模型取值不同、86 个恒定、122 个在这 35 个模型里没出现（纹理、gather、循环缓冲等未用到的功能）。不需要多 agent：多数字段名即含义，只有随模型变化的位段需要解读。
- 随模型变化的位段的解读（括号内为取到该值的模型）：

| 寄存器 位 | 方法 | 解读 |
|---|---|---|
| 0x0000 [2:0] / [5:3] / [8:6] | `SetCommonInFmt` / `Src2InFmt` / `OutFmt` | 数据格式；只在 W8A8（1 = int8、2 = FP16）和双输入 matmul（输出 5）里写出，其余为默认 |
| 0x0001–0x0007 | `SetOrReturnWin/Hin/Cin/Wout/Hout/Cout` | 每个 TD 的输入 / 输出形状（bonded 时 Hin 为一半；转置卷积、pad 前后不同） |
| 0x000a [28:29] / [30:31] | `SetCommonConvCfgOx` / `Oy` | **输出间隔**：转置卷积、上采样为 2（普通卷积 + 结果隔一个写一个）；1×9 为 Ox = 2，配合 Sx = 2（改写成步长 2 后两半交错拼回） |
| 0x000a [17:26] | `PadLeft` / `PadTop` | 1×9 的 PadLeft = 4（改写后核宽 10） |
| 0x000f [4:7] | `SetCommonTaskType` | 任务类型：卷积 0、池化 1、DMA / 拼接类 2、逐元素加乘 3、归约 4–6（layernorm、reduce_mean） |
| 0x000f [27] | `Set1DWinogradMode` | **Winograd 开关**：只有普通 3×3、分组 3×3 为 1；深度卷积、5×5、膨胀、步长 2 都为 0（与 compute_array H10 一致） |
| 0x000f [28] / [29] | `SetOutputTranspose` / `SetFillLowerNEFirst` | layernorm、linear、pad、transpose 的部分 TD |
| 0x000f [3:2]、0x1242 [27] | `SetNESmallSourceMode` | linear、matmul、reduce_mean、步长 2 卷积 |
| 0x0010 [2:0] | `SetNEOcgSize` | log₂(每轮输出通道数)：深度卷积 0、分组卷积 1、bonded 大卷积 4、W8A8 3（与 compute_array OCG 扫描一致） |
| 0x0010 [6] | `SetNEHalfWUMode` | 只在 W8A8 为 1 |
| 0x0011 | `SetPatchWidth` / `Height` | PE 运算的块尺寸（逐元素、池化、layernorm、softmax） |
| 0x0013 [21:28] | `SetNID` | 1；纯 PE 运算（逐元素、池化）为 0，推测为"是否用 NE" |
| 0x0014 [3:0] | `SetDPE` | softmax 1、W8A8 3 |
| 0x1041–0x1057 | `SetL2Src1*` / `Src2*` / `Result*` | L2 源 / 结果的类型、格式、交错、基址和各级跨步；第二源只在逐元素、layernorm、softmax 用；`SetL2ResultType` = 2 出现在 BN、bonded、双输入 matmul；reduce_mean 用 FIFO 模式 |
| 0x1140 | `SetPEOperationMode` / `First/SecondSource` | PE 运算：加 0、乘 1、layernorm 4 |
| 0x1240 | 见 §12 | 另：`SetKernelAlignmentFormat`（[16]）在双输入 matmul 和 softmax 为 1——这时把一个激活张量当作权重 |
| 0x1242 | NE 配置 | OpMode：卷积 0，concat / linear / pad / transpose / layernorm 4，softmax 3；NEBinaryPoint：FP16 −4（0x3c）、int8 0；NEPostScale、DoubleInt8Enable 只在 int8；NonLinearMode：无 0、ReLU 1、sigmoid / tanh / GELU 都为 2（查表，具体函数由查找表决定） |
| 0x1340–0x1363 | Tile DMA 源 | CacheHint 默认 2，bonded 4，reduce_mean 0xc / 0xe；bonded 的 CropOffset = 0x20（ANE1 从第 32 行起读，与 §11.4 地址包一致） |
| 0x1440–0x1457 | Tile DMA 目标 | 同上；转置卷积、上采样的 ChannelStride / CropOffset 加倍 |
| 0x1540 [6] | `SetKernelDmaSrcEnable` | 有权重时为 1；逐元素、池化、layernorm 为 0 |
| 0x1544 | `SetKernalDmaSrcBaseAddr` | 各 TD 的权重块偏移（§11.4） |

### 13.2 第二批：补没出现的字段（2026-10-05）

- 第一批 35 个模型有 122 个位段在 HWX 里没出现。按字段名设计第二批 32 个模型（`tdtrace_gen.py ALL2`：3D 卷积、大尺寸 reflect 填充、大激活、gather / gather_along_axis / embedding、奇数位置切片、slice_update、argmax、topk、双线性 resize / 上采样、crop_resize、int8 输出、每通道缩放的 W8A8、6 / 8 位调色板、每 4 通道一组的调色板、leaky ReLU / PReLU / SiLU / clip / ELU、reduce_max / sum、instance norm、广播加、depth_to_space / space_to_depth、reshape、C↔W 转置、稠密存放的 75% 零权重），另加编译选项变体（`tdtrace.sh` 支持 `模型@选项=值`）。共 75 次跟踪，全部编译成功。
- 结果：空白位段 122 → 79；随模型变化的位段 104 → 134。新补上的主要是：

| 字段 | 触发者 | 解读 |
|---|---|---|
| `SetTexture*`（0x1372–0x137a）整组 | gather、gather_along_axis | **ANE 的 gather 借用纹理采样单元**：TextureMode = 1，另写 Permute、ExtMax、BackgroundEn 等 |
| `SetRcas*`（0x1246 [8:20]） | topk | RCAS 只用于 topk：比较位、感知轴 / 位、模式，推测是 NE 内的比较选择（排序）硬件；编译器字符串 `rcas_kernel`、`transpose_rcas`、`ne_supports_rcas` |
| `SetSourceWrap` / `SetL2ResultWrapCfg`（0x1059–0x105a） | 大尺寸 reflect 填充 | 循环（镜像）寻址用于 reflect 填充 |
| `SetOrReturnDin/Dout`、`SetCommonConvCfg3d*` | conv3d | 3D 卷积原生支持（D = 8，Kd = 3）；gather_along_axis 也借用了 Kd 字段 |
| 7 个 `Set*TraceCfg` | `ForcePerfTracerRegisters=true` | L2、PE、NE、Tile DMA 源 / 目标、权重 DMA 的性能跟踪配置（0x101 / 0x202） |
| `SetTileDmaSrc1DependencyOffset` | 每 4 通道一组的调色板 | 依赖偏移 0x40 |

- 附带：`ScanWeightsForCompression=true` 不会把稠密存放的零权重改成稀疏格式（dz75 的 `KernelSparseFmt` 仍为 0）；双线性上采样也打开 `KernelSparseFmt`（实现为固定核的转置卷积，核里带零）。
- 仍为空的 79 个位段：激活压缩（`Compressed*` / `MetaData`，约 30 个；`EnableIntermediateCompression` 写在顶层或 h18g 子字典都没打开，可能 h18g 不支持）、权重系数 DMA（`AlignedKernelBias` / `PostScale` / `PaletteLut` 及其缓存提示，约 12 个）、多调色板（5 个；`EnableKernelSplitForMultiPaletteLUT` 也没触发）、静态循环寻址 / L2 索引源 / PE 索引（约 15 个）、`TileOverlap`、`StochasticRound`、CacheDma 预取限流（`DisableCachePrefetchMask` 不影响）。多半是这版编译器在 h18g 上默认不用的功能。

### 13.3 `HandleNEConfig` 的决策逻辑（2026-10-05）

由子 agent 反汇编 `ZinAneTd<24u>::HandleNEConfig` 并用 lldb 在 27 个模型上核对（全文 `private/data/03_compile/handle_ne_config.md`）。记号：K = 层的权重对象（`ZinIrKernel`，层 +0x70），MAK = K +0x440（`ZinMirAneKernel`）。多数 setter 读的是编译器更早阶段的决定，不是层的原始属性。

- **`SetKernelSparseFmt`** = `ZinMirAneKernelCoeff::compr`，由 `ZinNELayer::CheckKernelCompressed` 决定，两条路：
  1. **必须压缩**：上游已置压缩标志。膨胀 3×3 在 `ZinMirDilatedConv::CreateDilatedConvKernel` 里调用 `SetMustCompressWeight`（展开成 5×5 后 25 个位置只有 9 个非零，比例 0.36）。
  2. **稀疏度检查**：`IsWeightSparse`，零的比例超过 **1/7** 即用稀疏格式。剪枝模型的权重来源本身就是稀疏格式，直接通过；否则由 `CalculateSparsityFromPadding` 按改写核的步长、扩展、填充计算补进去的零：步长 2 卷积 0.4375、1×9 为 0.55（通过），普通 3×3、5×5 为 0。**只看改写补出的零，不扫描权重本身的零**——所以稠密存放的零权重不会走稀疏格式（§12）。
- **`SetKernelDetectZeros`** = `ZinMirAneKernelInfo.detect_zeros_enabled` 且非 DP2Add；只有 `ZinNELayer::EnableOnTheFlySparseEncodingIfPossible` 会打开它，条件：有真实权重、无零点、不是单位权重、权重来源不是预先压缩的。softmax 用无权重的单位核（格式 30）、layernorm 的 NE 层没有权重 → 0；剪枝模型为 0 是因为权重已预先压缩，不是因为稀疏格式；1×9、膨胀、步长 2 两位都是 1。函数名"on-the-fly sparse encoding"提示它在读权重时即时编码零值，作用可能在读权重带宽上（§12 的 c1x1 权重在片上，测不出），待在读权重受限的层上验证。**补充（lldb 看参数）**：M4 的目标 h16g（TD v17）下，c1x1、c3x3 等普通卷积 `SetKernelDetectZeros` 的参数一律为 0，**M4 不启用 DetectZeros**（由 HAL 0x72c 决定，H17 即 M5 一代起为 1，见 hal_analysis.md 结论 7）；h18g 上每层权重不同的 m2048（每层 8 MB、从 DRAM 读）也为 0，共享权重的 c1x1、c3x3 为 1。所以"读权重受限时零值是否省带宽"只能在 M6 上用 c3x3 测（模型：`sparse_gen.py` 的 c3x3_d50 / d75 / d90，对照 fp16、s75、s90）。
- **`SetKernelPalettizedEn` / `Bits`** 的参数就是编译器内部的权重格式编号（K +0xf8）：4 = FP16、1 = int8、13 = 2 位调色板、21 = 4 位调色板；没有权重时硬编码为 4（所以 softmax 也是 4）。`SetKernelFmt` 由同一编号换算成硬件代码（FP16 → 2、int8 → 1）。
- 其他：`SetDoubleInt8Enable` = MirInfo +0x81f；`SetNEBinaryPoint` 的参数是层 +0x304 的 `optional<int>`（跟踪值 8589934588 即 −4）；`SetNENonLinearMode` = 激活对象 +0x80；`SetOpMode` 由 `GetMacCfgOpMode` 按层类型选择；`SetKernelMode` = MAK +0x4（无 MAK 时由 HAL 决定 1 或 2）。
- 未解决：编译器里有一条硬件校验字符串，要求"FP16 输入的稀疏格式权重必须 DetectZeros = 1"，但剪枝模型编出来是稀疏格式且 DetectZeros = 0，没找到这条校验在哪里执行；部分 HAL / MirInfo 字段的含义只是从用法推断。
