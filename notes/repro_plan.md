# 复现清单：maderix Part 1–4 + Bryngelson 论文，在 M6 上逐项做

- 目标：两份资料里做过的硬件实验，在 M6 上全部做一遍，并补上两个 ANE 的部分。
- 最终产出：技术报告，见 `final_report/zh.md`。
- 最后更新：2026-10-03 17:20

## 方法约定

- **确认在 ANE 上执行**：看 IOReport 中断计数，并区分 ANE0 / ANE1（`tools/common/bondrun.m`、`tools/common/anewho.c`）。Core ML 会把小模型、单独的 softmax / relu、部分采样类运算悄悄放到 CPU 上，所以每个实验都要检查中断。
- **计时**：
  - 一律用"改层数取斜率"，扣掉每次调用约 150–170 µs 的固定开销（kdebug 验证：斜率等于 ANE 实际执行时间，见 D1）；
  - 先空闲基线、再连续调用 ≥1 s 预热（ANE 从空闲到满速约 0.3 s，慢 2.8 倍），预热和测量之间不能有空闲；
  - 每个点至少两轮，看 p10 和中位数是否一致。
- **生成模型**：
  - `ct.convert(..., skip_model_load=True)`。否则生成时会多编译一次 ANE 程序，而且和之后加载用的不是同一份缓存；
  - 每个模型一个进程（同一进程连续生成多个时，coremltools 偶尔报 KeyError）；
  - 多个输入时，每个输入用独立的 `TensorSpec` 对象。
- **数值实验**：后接"陪跑"卷积支路，保证测试算子放到 ANE 上；同时跑 CPU_ONLY 对照。
- **功耗**：用 SMC 的 `PP0b`（ANE 电源轨）和 `PSTR`（整机），`tools/common/smcpower.c`，不需要 root。`powermetrics` 在这台 M6 上估不出 CPU / ANE 功耗，不能用。
- **读编译器内部参数**：在自己的进程里加载 ANECompiler，按符号表调用只读函数（工厂函数、Get 方法），再用 vm_read 读内存：`tools/re/dump2.c`（HAL 参数表）、`tools/re/socfreq.c`（SoC 频率与内存参数）、`tools/re/xref.c`（找调用关系）。不执行任何 ANE 程序。
- **需要 root 的只有三处**：kdebug 跟踪（D1，anemon）、`log stream` 抓内核日志、结束卡住的系统进程（aned、ANECompilerService）。

不做的一项：maderix 的"修改 HWX 后执行"（例如把 sigmoid 的采样点换成 x³、改 W8A8 的模式字）。这需要绕过 Core ML / aned 直接加载自己的程序，不在本项目范围内。替代办法是**只编译、比对 HWX**（不执行）。

状态：✅ 完成 · 🔄 部分完成 · ⏳ 待做 · ⛔ 没有数据源，测不了

## 进度

| 组 | 共 | ✅ | 🔄 | ⏳ | ⛔ |
|---|---|---|---|---|---|
| A 静态结构 | 6 | 6 | | | |
| B 计算阵列 | 9 | 9 | | | |
| C 存储与带宽 | 4 | 4 | | | |
| D 调度 | 6 | 6 | | | |
| E 电源 | 4 | 4 | | | |
| F 数值 | 3 | 3 | | | |
| G 汇总 | 2 | 2 | | | |
| **合计** | **34** | **34** | **0** | **0** | **0** |
| H 计划外补充 | 50 | 50 | | | |

## A. 设备与静态结构

| # | 来源 | 实验 | 状态 | 位置 |
|---|---|---|---|---|
| A1 | 论文 §9.1–2、Part 4 §4.1 | ioreg：设备、核数、时钟 / 电源域 | ✅ 两个 16 核 ANE，各自电源门控、共用时钟；设备树 voltage-states8 / 29 为两个 ANE 的 32 档频率表（804 MHz – 2.58 GHz） | data/02_overview/m6_ioreg_ane_20261002.md、power.md §6.3 |
| A2 | 论文 §7、Part 4 §4.2 | HAL 参数表 dump、跨代对比 | ✅ 含 H17→H18、H18→H19 的差异 | hal_analysis.md |
| A3 | 论文 §6、Part 4 §2 | HWX 格式、TD 流、权重按 NE 切分 | ✅ h18g 新格式，nonbonded / bonded 两套程序 | hwx_h18g.md §1–5 |
| A4 | 论文 §2.4 | TD 寄存器分组 → 流水线各级 | ✅ v31 / v36 完整字段布局；顺序为任务头 → 形状 → 输入 DMA → 纹理 → L2/PE → NE（含右移、偏置移位）→ 输出 DMA；**M6 实际用 v24**（形状 / 卷积 / 任务信息字段与 v31 相同；见 hwx_h18g.md §11.3） | hwx_h18g.md §9 |
| A5 | 论文 §8 | 多引擎：编译器的切法、共享 bss、同步记录 | ✅ 共享区经 SLC（DSID）；跨 ANE 屏障 `f0003281`，个数与数据交换次数一致；TD 编号全局唯一 | hwx_h18g.md §6–7 |
| A6 | Part 4 §4.6 | 硬件层清单、ALU 操作码、激活函数 LUT 的位置（只编译比对） | ✅ 50 种层、33 种激活；逐元素操作码是 2 位字段（加 / 乘 / 大 / 小）+ 取反位；LUT 33 点，用对称和区间归约，gelu / silu 是拟合值 | hwx_h18g.md §8、numerics.md F3b、data/03_compile/compiler_layers_neurons_m6.txt |

## B. 计算阵列

| # | 来源 | 实验 | 状态 | 位置 |
|---|---|---|---|---|
| B1 | 本项目 | 单 / 双 ANE 的边际吞吐 | ✅ FP16 20.6 / 39.5 TFLOPS（1.92×）；单引擎为理论峰值（16 NE × 256 MAC × 2 × 2.58 GHz = 21.1）的 97.5%，双引擎约 93% | bonded_measure.md、power.md §6 |
| B2 | 论文 §2.1 | 扫 Cout 找 OCG 跳变 | ✅ 只有 256→272 一个明显台阶（+32%），之后平滑 | compute_array.md B2 |
| B3 | 论文 §2.1 | 扫 Cout 看实际使用的 NE 数 | ✅ Cout ≥ 16 时 16 个 NE 全部启用（16 通道时每 NE 1 个通道）；通道少时效率低是因为每 NE 工作少 | compute_array.md B3 |
| B4 | 论文 §2.1 | 卷积核尺寸与形状 | ✅ 3×3 15.3、5×5 16.9、7×7 19.4 TFLOPS；长条形核（1×9、9×1）比 3×3 慢 70–85% | compute_array.md B4、B4b |
| B5 | 论文 §2.1 | Winograd 是否启用 | ✅ **有，硬件实现，按形状启用**：256 通道 8×16 没有用；512 通道 16×16 的 3×3 单引擎有效 31 TFLOPS（直接峰值 21.1，按 2.58 GHz），膨胀 3×3 只有每引擎 14.6；权重存原始 3×3 | compute_array.md B5、H10 |
| B6 | Part 4 §4.8 | 按链深度的 FP16 / W8A8 吞吐表（1–48 层） | ✅ 双 ANE；W8A8 在 32 层时 37.5 TOPS（FP16 的 2 倍），边际约 1.7× | compute_array.md B6 |
| B7 | Part 4 §4.8 | int8 权重 + fp16 激活是否加速 | ✅ 基本不加速 | compute_array.md |
| B8 | Part 4 §4.9 | S2D 形状变换、block=2 陷阱 | ✅ 9.5 → 31.7 TFLOPS（3.3×）；M6 没有 block=2 陷阱 | compute_array.md B8 |
| B9 | 论文 §2.2 | 时钟频率 | ✅ **硬件读数：满载约 2.58 GHz**（设备树 voltage-states8/29 最高档；由固件任务时间戳在升频台阶上反推，低档台阶拟合 RMS 0.2%，见 H34）。编译器 `Soc2026BaseLine` 表最高 2.508 GHz，只用于性能模型。升频从 852 MHz 起 | power.md §6、§6.5 |

## C. 存储与带宽

| # | 来源 | 实验 | 状态 | 位置 |
|---|---|---|---|---|
| C1 | 论文 §2.3、Part 4 §4.2 | 单个操作数阈值（M5 是 4.72 MB） | ✅ 编译产物：片上中间张量每块必须 < 2 MiB，块数 = ⌊大小 / 2 MiB⌋ + 1；计时看不到拐点（层融合） | memory.md C1、C1b |
| C2 | 论文 §2.3 | 权重工作集阈值 | ✅ 8 MB 已放不进片上；每层 4.5 MB 时即使共用一份权重也要每层重读 | memory.md C2、C2d |
| C3 | 论文 §2.5 | 权重流带宽、激活流带宽；单 / 双 ANE 的上限 | ✅ 读权重：约 150 GB/s（固件任务时长；早先"≤48 MiB 130 / ≥50 MiB 150 GB/s 两种状态"是主机 CPU 空闲深度的假象，见 H33）；与每层大小、卷积核形状无关；双 ANE 合计约 140 GB/s（共享 DRAM）。转置约 60 GB/s；逐元素读写激活约 40 GB/s | memory.md C2b–C2j、C3 |
| C4 | Part 4 §4.5 | 独立输入数量 2→8 | ✅ 每多一个 2 MB 输入多约 52 µs（约 40 GB/s），线性 | memory.md C4 |

## D. 调度、开销与重叠

| # | 来源 | 实验 | 状态 | 位置 |
|---|---|---|---|---|
| D1 | 论文 §3、Part 4 §4.7 | 每次调用的固定开销、中断次数 | ✅ kdebug：任务以外的开销 = 提交侧约 30 µs + 结束侧 130–325 µs（随任务时长饱和，不按层数增长，见 D1c；原"每层 0.48 µs"已更正）；任务时长斜率 3.29 µs / 层，与计时一致；每次调用 2–3 次中断 | scheduling.md D1 |
| D2 | Part 4 §4.7 | 两个单 ANE 模型同时跑 | ✅ 会分到 ANE0 和 ANE1，合计 1.78× | scheduling.md D2 |
| D3 | Part 4 §5.2 | 内部重叠：matmul + 独立 relu；8 个独立 add 与串联 add | ✅ 独立支路一律串行；层内流水线重叠；8 个串联逐元素几乎不花时间 | scheduling.md D3 |
| D4 | 论文 §2.1 | MAC 与 PE 的 co-issue | ✅ softmax + 卷积并列与串行耗时完全相同；MAC+PE、MAC+重采样、DMA+PE、DMA+MAC 都不重叠 | scheduling.md D3 / D4 |
| D5 | Part 4 §4.10 | 图深度上限 | ✅ M6 为 386 层（双 ANE 编译路径栈溢出），超过后悄悄退回 CPU，387 / 392 层加载会卡住；M4 至少 448 层 | scheduling.md D5 |
| D6 | 论文 §2.1 | 每层固定开销（论文 44 个周期） | ✅ 几乎无计算的 32 通道小层：每层边际 ≈ 13 ns，按 2.58 GHz ≤ 约 34 个周期（若时钟在低档则更少）；D1 的"任务以外每层 0.48 µs"已证实是主机唤醒随任务时长变化造成的假象（D1c、H42） | scheduling.md D6b |

## E. 电源

| # | 来源 | 实验 | 状态 | 位置 |
|---|---|---|---|---|
| E1 | 论文 §4 | 空闲时是否整块断电 | ✅ ANE 电源轨空闲 0 W；IOP 约 6 s 后断电；Device States 通道不可用 | power.md §1、§3 |
| E2 | 论文 §4 | 冷唤醒代价 | ✅ 三档：< 30 ms 几乎无代价 / 0.1–3 s 多约 4 ms / > 6 s 多约 50 ms | power.md §3 |
| E3 | Part 2–4、论文 §4 | 功率：FP16 / W8A8、单 / 双 ANE、每 TFLOP 能耗 | ✅ SMC PP0b：单 ANE FP16 6.5 W，双 ANE 11.3 W（2.7 TFLOPS/W），W8A8 3.4 TOPS/W；读权重受限时 ANE 仅 2.5 W；开销为主的小模型反而 9.1 W | power.md §5 |
| E4 | 论文 §2.2 | 持续负载下是否降频 | ✅ 5 分钟满载不降频，降频事件全为 0 | power.md §4 |

## F. 数值

| # | 来源 | 实验 | 状态 | 位置 |
|---|---|---|---|---|
| F1 | 论文 §2.1 | 归约树、累加器位宽 | ✅ 32 位定点累加器（16 位小数，范围 ±32768），没有 fp16 部分和；M4 相同 | numerics.md |
| F2 | 论文 §5 | 舍入、NaN、非规格化数、饱和 | ✅ 舍入远离零；exp = 31 当普通数解码；PE 是浮点路径；M4 相同 | numerics.md |
| F3 | Part 4 §4.6 | LUT 激活的误差曲线 | ✅ sigmoid 33 点（[−8, 8]，间距 0.5）；gelu 两种模式在 ANE 上逐位相同；sqrt / rsqrt ≤ 1.5 ulp | numerics.md F3、figs/lut_error_*.png |

## G. 汇总

| # | 内容 | 状态 | 位置 |
|---|---|---|---|
| G1 | M6 与 M1 / M4 / M5（论文和 maderix 的数据）的对照表 | ✅ | comparison.md |
| G2 | M6 ANE 硬件框图 | ✅ | figs/legacy/m6_ane_block.svg（.png） |

## H. 计划外的补充项

### 已完成（53 项）

| # | 内容 | 结论 | 位置 |
|---|---|---|---|
| H1 | IOReport 无 root 通道普查 | 有每个 ANE 的中断、IOP 状态、时钟开启、链路带宽、降频事件；没有 ANE 频率和能耗 | power.md §1 |
| H2 | ANE 时钟爬升 | 从空闲开始约 0.3 s 内慢 2.8 倍 | power.md §2 |
| H3 | 编译器在两个 ANE 之间切分的阈值 | H = 1 时宽 128 → 256 之间开始切；逐元素链在宽 128 时也会切 | bonded_measure.md §2 |
| H4 | bonded 时两个 ANE 各读一份权重 | 权重受限时双 ANE 收益从 1.9× 降到约 1.4× | bonded_measure.md §3.3 |
| H5 | 重复编译问题 | coremltools 生成时加载会多编译一次，且缓存不共享；已改用 `skip_model_load` | 本文"方法约定" |
| H6 | 哪些运算会退回 CPU | 单独的 softmax / relu 链、resize_bilinear、最近邻上采样、gather、小模型 | scheduling.md |
| H7 | 编译耗时 | 只有双 ANE 版本慢：逐元素层约按层数的 3.5–3.8 次方增长（512 层 179 s，单引擎 0.4 s） | compile_cost.md |
| H8 | H19 的新功能 | 编译产物：FP16 / W8 / W8A8 只差缓冲计数和 L2 地址，双倍速率、MX 格式未被触发；SoC 参数：MCache 36 MiB、DRAM 最高 5.3 GHz、NE 29 档 591 MHz – 2.13 GHz | hal_analysis.md 结论 6、power.md §6.2 |
| H9 | 层数上限 386 的原因 | 双 ANE 编译路径递归调度栈溢出（SIGBUS）；h16g / h18 目标到 512 层正常 | scheduling.md D5、compile_cost.md §4 |
| H10 | W8A8 峰值、硬件 Winograd | 1×1 链的 W8A8 受激活带宽限制（单 27.5 TOPS，双 38.6，与 FP16 持平）；3×3 上 W8A8 = 2.0× FP16（单引擎有效 62 TOPS）；普通 3×3 单引擎有效 31 TFLOPS > 直接峰值 21.1（2.58 GHz），膨胀 3×3 只有每引擎 14.6 → **硬件 Winograd**；int8 累加器为 32 位有符号整数（见 H50） | compute_array.md H10 |
| H11 | bias 在哪里加 | **定点累加器的初值**（先舍入到 2⁻¹⁶），同样受 ±32768 限制；负的大 bias 可让中间值不溢出 | numerics.md H11 |
| H12 | 小于 1 LSB 的乘积何时被丢掉 | **按指数判断**：x、w 指数和（非规格化按 −14）≥ −16 时远离零舍入到 2⁻¹⁶，≤ −17 时整个丢掉（实际值近 2 LSB 也丢） | numerics.md H12 |
| H13 | silu / erf / sin / tanh 的采样点 | 从 `__KERN_0` 直接读出 | numerics.md F3b |
| H14 | 权重 48–64 MB 处的"带宽下降" | 两种状态，48–50 MiB 处突变；不是带宽下降（机制见 H33：主机侧唤醒变慢） | memory.md C2b、C2f |
| H15 | 同一进程内的并发 | 同一个程序在一个进程里严格串行（多线程、多个 MLModel 对象都没有加速，全在 ANE0）；不同程序可分到两个 ANE（1249 次/s，对比 616 + 843）；两个进程跑同一个模型 1.81×；bonded + 单 ANE 混跑约 +25–30% | scheduling.md H15 |
| H16 | IOP 断电阈值和维护计时器 | 内核两个计时器：最后一次推理后 5.68 s 断电；10.2 s 时维护计时器重新上电、撤下空闲程序，约 15.3 s 再断电。第一次调用：< 5.7 s 为 6.8 ms，5.7–10.2 s 为 47–60 ms，10.2–15.3 s 为 9.5 ms，之后 53–58 ms | power.md §3.1 |
| H17 | 读权重带宽与每层大小的关系（用户提出） | 每层 128 KB–8 MB 都是 127–133 GB/s，无关 | memory.md C2c |
| H18 | 卷积核形状的影响（用户提出） | 读权重带宽与形状无关；长条形核影响的是计算效率 | memory.md C2d、compute_array.md B4b |
| H19 | 与之前 ane_bw 148 GB/s 的对照（用户提出） | 重测 152 GB/s，属于 ≥ 50 MiB 的状态 | memory.md C2e |
| H20 | 48 MiB 切换的范围 | （已被 H33 更正：按单次调用的 ANE 任务时长约 350 µs 判断）原记录：按单个模型、单次提交所有 ANE 要读的总量判断；两个模型同时跑不会合并计算 | memory.md C2h |
| H21 | 48 MiB 切换的机制排查 | 排除编译分段、权重外置、换链路；SLC、aned 缓存两条路走不通（之后由 H33 查明） | memory.md C2g、C2i |
| H22 | 片上切块阈值的编译产物证据 | 每块 < 2 MiB；bonded 时两边块数不完全对称 | memory.md C1b |
| H23 | 功耗数据源 | powermetrics 在 M6 上不可用；SMC PP0b 可用且无需 root | power.md §5.1 |
| H24 | 系统服务卡死 | aned 在编译服务崩溃后会一直等待，堵住后续加载；需 `sudo killall aned` | 本文"方法约定"、scheduling.md D5 |
| H25 | 两种张量操作的带宽差别 | 转置约 60 GB/s、逐元素约 40 GB/s，都远低于读权重 | memory.md C3 |
| H26 | 满载时偶尔更快的调用 | 约 1.8% 的调用快约 12%，成串出现，推测是 CPU / 内存频率档位变化 | power.md §4 |
| H27 | 编译器内置的 SoC 参数（`ZinIrSocVariantParams`） | 每代一组：NE / DRAM / DMA 频率表、DRAM 通道数、MCache 大小、DRAM 池上限；可用只读调用读出 | power.md §6.1–6.2、data/09_clock/socfreq*.txt |
| H28 | 哪个编译目标用哪组 SoC 参数 | 扫描 BL 指令：**TargetH18g（M6）用 `Soc2026BaseLine`**，TargetH18（单引擎，对应芯片未知；A20 是 TargetH19，2026-10-07 更正）用 `H18`；编译器里没有 `H18g()` | power.md §6.1 |
| H29 | M6 的 SoC 参数 | NE 32 档 804 MHz – 2.508 GHz；DRAM 8 通道、最高 5.328 GHz（×2 ≈ 10656 MT/s，理论约 170 GB/s，实测读权重 152 GB/s ≈ 89%）；MCache 16 MiB；DMA / L2 最高 1.308 GHz | power.md §6.2 |
| H30 | 每个 NE 的乘加宽度 | 每 NE 每周期 256 次 FP16 乘加（每引擎 4096）；按实测 2.58 GHz 与固件任务周期数算，1×1 链为 256 的 96.7%；3×3 超过此值是硬件 Winograd，不矛盾（H10） | power.md §6.0 |
| H31 | 时钟机制 | 每个 ANE 两个 PLL；爬升期 PLL 已开、在频率表内逐档升频；ANE 没有自己的调压域，通过 SOC Floor（5 档）请求电压；固件有 `System Clock`、`pstate` 处理 | power.md §6.4 |
| H32 | 内核日志里的编译参数 | `--ne-frequency=-1`、`--pstate-soc=-1`、`--pstate-dcs=-1`、`--cost-model-cluster-threshold=85`、`--e4m3-overflow-setting=Saturate`、`--enable-l2-cached-buffer=true` 等；驱动加载过程（RTGraph、DART 页 16 KiB、上电） | power.md §6.1 |
| H33 | 48 MiB 切换的机制（逆向） | 不是 ANE 换读法：固件时间戳显示 ANE 读权重一直约 152 GB/s，台阶全在任务结束后的主机侧（驱动完成处理和用户线程唤醒都慢 1.5 倍）；原因是任务超过约 350 µs 后 CPU 进入更深的空闲状态；空转占满 CPU 后台阶消失；共享权重模型在同样的任务时长出现同样的台阶。"两种带宽"的说法作废 | memory.md C2j |
| H34 | ANE 实际运行频率（硬件读数） | IOReport / ioreg 无直接读数（档位由 CLPC 决定）；用 kdebug 固件任务起止时间，纯计算模型在升频过程中的台阶时长与频率表匹配：低档 852/1368/1548/1716/1872 MHz 拟合 RMS 0.2%，**满载 2578–2584 MHz = 设备树最高档 2.58 GHz**，不是编译器表的 2.508 GHz；每 NE 每周期约 247.5 次乘加（256 的 96.7%） | power.md §6.5 |
| H35 | Core ML 首次加载比直接编译慢约 3 倍的原因 | 只编译一次、选项相同；编译服务由 Adaptive 守护进程 aned 派生，编译时虽被提升到默认 QoS，但只在 E 核上运行（ovl_B128：直接 12.65 s，Core ML 34.05 s，E 核忙约 30 s / P 核 0.2 s）；客户端 QoS 改不了，设为 background 更慢（98.8 s） | compile_cost.md §3.1 |
| H36 | FP16 在 32 层时反常地慢 | 与权重无关；两个效应：A 层数少时主机侧开销小（166 → 355 µs；阶段拆分显示增长几乎全在驱动完成处理和用户线程唤醒两段，占满 CPU 后消失，是 CPU 空闲电源管理）；B **只有 32、34 层的执行计划把最后一个 relu 放到 CPU**（`main_classic_cpu` 段，cast → relu → cast），每次调用多约 100 µs。ANE 编译产物在 16–40 层结构一致；W8 的 32 层计划是纯 ANE、耗时在直线上，不受影响 | compute_array.md B6b、defects.md B7 |
| H37 | bonded 两边块数不对称 | **双 ANE 划分沿用不分引擎时的切块网格，只在块边界上分成两组，块数为奇数时多出的一块给 ANE1**（8 层模型两边块宽分布之和 = 不分引擎时的分布）；ANE1 / ANE0 时间比与块数比一致（1.29、1.46）；比均分慢 12.5–19%。预测验证：块数为偶数的 W14336 比 W12288 多 17% 计算量，耗时反而少 2% | memory.md C1c、defects.md B8 |
| H38 | 长条形卷积核效率低的原因 | ① **硬件步长 1 原生核宽上限 8**；核宽 9–15 被改写为横向步长 2、每步出 2 个像素（Ox = 2，权重存两套错开一位的核，每对翻倍），按每 NE 64 KiB 的权重缓冲切成更多趟（每层 TD 数 = ⌈每 NE 权重 ÷ 64 KiB⌉，所有核形状都吻合），核宽 ≥ 16 无法改写、编译失败、整个模型退回 CPU；核高到 15 都原生；② 宽度 ≤ 约 32 时按行计时（1×9 宽 8 效率 18%、宽 32 为 78%）；③ 原对比的 3×3 用了硬件 Winograd。TD 卷积配置字布局已从编译器 `SetCommonConvCfg*` 反汇编得到 | compute_array.md B4c、hwx_h18g.md §10 |
| H39 | 核形状效率重测（不切换单 / 双 ANE 的形状，固件时间戳） | 原生核（核宽 ≤ 8、竖向到 15×1）单 ANE 90–96%；**改写核（1×9–1×15）受读权重带宽限制**：每层耗时 = 权重量 ÷ 约 150 GB/s，与行数无关（反推抽头数与编译产物一致）；改写 Kw = 核宽 + 1 补偶数；双 ANE 下 16×32 的 1×9/10/11/15 按行切分、两边各读一份权重，没有加速（defects.md B9）；单 ANE 时固件不发任务开始事件 | compute_array.md B4c 第 8 点 |
| H40 | HWX 指令流打包格式；未知字 X | 包头低 15 位 = 寄存器字地址；bit 31 = 0 连续写（bits 15–30 = 个数 − 1），bit 31 = 1 按 16 位掩码写。**未知字 X 就是按掩码写的包头**（`0x91498005` = 基址 Wout，写 7 个寄存器）。19 个编译目标按寄存器布局分 4 组，h18g 与 h19 相同 | hwx_h18g.md §11 |
| H41 | TD 布局版本对应哪个芯片（逆向分发代码） | `ZinAneTd<N>` 的 N = `AneArchEnum`；`arch_dispatch` 按它查跳转表；`ZinCpuSubtypeToArchValue` 把 HWX subtype 换算成它。**h18g（M6）、h19 = subtype 11 = v24；h18 = v20**；v26 / v28 / v31 / v36 是更新的架构（v26 = M12，其余暂无目标名）。原推测 M6 = v31 作废，但形状 / 卷积 / 任务信息字段在 v19–v31 相同，已有解码仍有效 | hwx_h18g.md §11.3 |
| H42 | 任务以外"每层约 0.48 µs"的来源 | 两组层数相差 4 倍、任务时长重叠的模型：提交 → 任务结束对计算量是直线（截距约 30 µs，残差 ±5 µs），**没有每层开销**；任务结束后的开销只随任务时长变化（≤ 350 µs 时约 130–150 µs，≥ 660 µs 时饱和在约 320 µs），增长全在驱动完成处理和用户线程唤醒两段，CPU 空转时降到约 215 µs。"每层 0.48 µs"是 D1 两点连线跨过 CPU 深度空闲台阶造成的假象 | scheduling.md D1c |
| H43 | M6 的内存结构（"三通道"？）与总带宽 | 设备树：1 个 AMCC（4 个 plane）× 8 个 DCS 通道、全部启用，每通道一颗美光 die（16 GB，单 rank），有 ECC；**不是三通道**。带宽：ANE 单独约 153 GB/s，GPU 单独约 145 GB/s，两者同时合计约 160–168 GB/s（理论 170.5 的约 97%）。用户指出 32 GB 版本才能到 170 GB/s（可能与双 rank 有关，未验证） | memory.md C2k |
| H44 | H17s 数据块 +0xb0 起的第二组表 | 不是 H17s 的参数：SoC 参数块每个 0xa0 字节、按目标相邻排列，H17s 块 + 0xa0 正好是 H18 块，+0xb0 / +0xc8 / +0xe0 = H18 的 NE / DRAM / DMA 频率表。是 `socfreq` 读越界造成的 | power.md §6.2 |
| H45 | L2 的大小 | **每个 ANE 2 MiB**：编译选项 `L2Size`（kB）默认正好 2048——≥ 2048 时 TD 流与默认逐字相同，2047 就不同，更大不再变化；默认编译把 0.5 MiB 缓冲放在 [1.5 MiB, 2 MiB)，少 1 kB 就放不下。TD 中 L2 地址 / 跨步字段（bit 4 起 17 位，字节）上限也是 2 MiB；HAL 单操作数上限 2 MiB、64 bank、16 B 粒度。物理 SRAM 无直接读数 | memory.md C1d |
| H46 | 控制字段：卷积配置字 bit 12 / 27、TD 末尾命令字、任务头 | bit 12、27 是保留位（v24 无函数写入，产物中恒为 0）；TD 末尾 `0x2xxxxxxx` 是"地址包"（bit 29 标记，bits 23–28 标签），只写 0x1544 / 0x1346 / 0x1444 / 0x1344 / 0x1442；**0x1544 = 权重 DMA 64 位基址**，`__text` 全部重定位项都指向它（目标 `__kern_0`），其余由运行时绑定输入 / 输出；TD 头第 0 字 = 编号 + 长度（字），+0x20 为 Tsr / Tde / Xtde / PublishBit 标志字 | hwx_h18g.md §11.4 |
| H47 | TD 头三个字；输入 / 输出地址包与 BAR 编号 | TD+0x4 = `exe_cycles`（`CalculateExeCycles`：性能模型估计值，上限 0xffff，链式读入的层为 0）；+0x8 / +0x10 / +0x18 = `log_events` / `debug_log_events` / `dram_log_events`（`SetEventFlags`），+0xc / +0x14 = exception / debug_exception。地址包 bits 21–28 = BAR 编号：4 权重（`KernelSrcBaseAddr`）、20 DSID、24 起先输出后输入、每个张量 4 槽；0x1346 = Src1BaseAddr、0x134c = Src2BaseAddr、0x1444 = DstBaseAddr（Tile DMA）。顺带更正：0x134x 是 Tile DMA 源寄存器，不是 L2 块（C1d 证据 3 作废，2 MiB 结论不变） | hwx_h18g.md §11.4、memory.md C1d |
| H48 | 编译器怎么决定用一个还是两个 ANE | 编译期决定：HWX 同时有 nonbonded / bonded 两套程序，bonded 程序里由空间切分步骤（`BondedSplitSubgraphIdentification`、`ClusterSplitCostModel`、`ComputeSplitLatencyBonded`）按估计延迟选切法，不划算就全留在 ANE0。两种切法：按行（融合切块，竖向核带 halo）、按输出通道（把权重分趟平均分给两个 ANE，各趟大小相同时才行）。8×32 的 1×2–1×8 门槛：nonbonded `exe_cycles` 之和 ≤ 44 不切、≥ 48 切；4×32 从不切；1×9–1×15、3×3、9×1、11×1、3×1–7×1 在 8×32 不切；16×32 起几乎都切。成本模型不考虑共享读权重带宽 | bonded_measure.md §2.1 |
| H49 | 双 ANE 成本模型的具体公式与根因 | 切 ⇔ Σ切分前 > ½（Σ切分后各块 + Σ拷贝 / 合并）且不劣于进一步细分；**× 0.5 = 假设两 ANE 完全并行、不争带宽**，这是 B9 的根因。用 `exe_cycles`（同一性能模型）+ 强制切分反推：按行切的拷贝 / 合并开销 ≈ 45（44 < x ≤ 46，各核一致），**只在切后每块 ≤ 128 像素时出现**（8×32 → 4×32、4×64 → 2×64），约与张量字节数成正比；每块 > 128 像素（4×33、5×32、4×64）时几乎为 0；按通道切 ≈ 0。已排除：MCache 命中阈值（16 MiB）、输入 + 输出 ≤ 256 KiB、激活 ≤ 128 KiB、每 NE 64 KiB 权重缓冲 × 2、small source mode。128 像素条件的代码位置未定位 | bonded_measure.md §2.2 |
| H50 | int8（W8A8）累加器位宽 | 手写 quantize / dequantize 控制缩放：整数累加和 2^30 准确，2^31 溢出成 inf（缩放改为让输出只有 8192 时仍溢出）→ **32 位有符号整数**；输出可到 64512，没有 fp16 路径的 ±32768 上限，缩放在累加之后 | numerics.md H50 |
| H51 | INT8 MAC 宽度 | 编译器性能模型：W8A8 卷积 TD 每单位 exe_cycles 20.8 M 乘加，FP16 / W8 为 10.3 M，正好 2 倍；`perfmodel::GetNumOutputChannelsPerAccumulator` 在 int8 时返回 2（HAL 0x430 高半），FP16 返回 1（HAL 0x440）→ **每累加器同时算 2 个输出通道，等价每 NE 512 次 int8 乘加 / 周期**，H16–H19 相同。实测：1×1、2048 通道、16² 的 W8A8 单引擎跑出每 NE 每周期 428 次乘加（> FP16 上限 256，1×1 无 Winograd）；双引擎两组为 FP16 的 1.76–1.87 倍 → **INT8 = 512 / NE / 周期**，单引擎直接卷积峰值 42.3 TOPS。附带：`exe_cycles` 单位 ≈ 1 µs；性能模型不计 Winograd | compute_array.md H51 |
| H52 | Tile DMA 输入 / 输出路数 | 编译：每个 TD 最多读 2 个 DRAM 张量（Src1、Src2）、写 1 个（Dst）；3 / 4 个输入拆成 2 / 3 个 TD 经 L2 接力，两路输出各起一个 TD。实测（kdebug，ANE 任务时长）：一路与两路输入每个 ANE 的读写总吞吐相同（18 → 32 MB 斜率 34–36 GB/s），`a + a` 也读两次 → **两路源共用一份带宽，Tile DMA 每 ANE 约 35–40 GB/s**。更正 C3 / C4：原数字含主机开销 | memory.md C3b |
| H53 | NE / PE 内部结构（编译器视角 + PE 实测） | TD 寄存器 0x10 = NE 配置（OcgSize log2 [2:0]、HalfWU [6]）。**FP16 每 NE 每轮最多 16 个输出通道**，再由 64 KiB 权重缓冲限制（2×2、512 通道正好 64 KiB）；INT8 同样受 64 KiB 限制（1 B / 权重）；Winograd 的 OCG 只有 1–2。16 × 16 NE = 256 解释了 B2 的 256→272 台阶。性能模型输出项显示 L2 有独立时钟域、读写分别计 bank 冲突。PE（kdebug，5 点回归）：单输入每 ANE 约 61 G 元素 / s；PE 在单独调度的时钟域（与 NE、SOC 档位都无关；冷启动约 0.5 s 才升频，GPU 同时工作时会被反复压回慢档），慢档到满载 2.63 倍，绝对频率读不到（设备树、编译器、驱动、固件均无该域频率表），固定 0.34 µs / 任务；双输入非线性、每元素成本高得多（单 DMA 引擎，HAL 0x5f6）。L2 bank：关掉优化时步长为 1024 B 整数倍，默认补 512 / 768 B → 64 bank × 16 B。输入行缓冲测不出。性能 CSV：`DebugMask` bit 11 只在 `os_variant_has_internal_content("com.apple.ane")` 为真时生效；经用户同意在自己的 anecc 进程里替换该函数（`tools/common/anevariant.c`）后拿到逐 TD CSV（`tools/05_compute/perfcsv.py`）：编译器把 PE 放在 L2 时钟（1.812 GHz）、NE 2.508 GHz；每 NE 每周期乘加 FP16 256（Cin 64 时 512）、INT8 512 / 1024；工作单元 128–512 像素 | compute_array.md H53 |

### 待做

无（H 组全部完成）。

### 未解决的问题（报告"限制与未解决问题"一节用）

| 问题 | 已知 | 出处 |
|---|---|---|
| 双 ANE 拷贝开销"每块 ≤ 128 像素"条件的来源 | 公式已逆向，规律已验证（9 种通道数、7 种形状），代码位置未定位 | bonded_measure.md §2.2 |
| 32 GB 版本的带宽 | 用户指出只有 32 GB 能到 170 GB/s；本机 16 GB 单引擎约 145–153、ANE + GPU 合计约 160–168 | memory.md C2k |
| 实际 DRAM 频率 | 设备树 DRAM 档位表的频率字段被隐藏 | memory.md C2k |
| 未解码的字段 | 事件掩码各位的含义；v24 中 L2 块寄存器的硬件地址 | hwx_h18g.md §11.4、memory.md C1d |
| 书中"M5 = v20" | 本机编译器表为 H17 = v19、H18 = v20，原因未核实 | hwx_h18g.md §11.3 |

## 疑似缺陷

单独整理在 `defects.md`：A 类疑似 bug 2 条（h18g 编译栈溢出、编译服务崩溃后加载卡死 / 静默退回 CPU）；B 类性能问题 10 条；C 类未写进文档的行为 10 条。报告里作为"疑似缺陷"一节。

## 下一步

1. **写报告正文**：中文 Markdown 源稿（`final_report/zh.md`），按当时大纲的 14 节（大纲已在报告完成后删除，见 git 历史）；原清单 34 项、H 组 53 项全部完成；按主题的总览见 `experiments.md`，材料齐全。
2. **补图**：
   - 已有：硬件框图（G2）、激活函数误差曲线；
   - 框图要补上"每 NE 每周期 256 次 FP16 乘加、最高 2.5 GHz"；
   - 还要画：双引擎流程图、IOP 两个计时器的时间线（H16）、同进程并发示意（H15）、FP16 / W8A8 / Winograd 吞吐对比（H10）、单 / 双 ANE 耗时随层数变化、宽度阈值、通道数阶梯、按层数的吞吐对比、时钟爬升曲线、定点累加器示意、"48 MiB 切换"的时间线拆解（ANE 任务 vs 主机侧，H33）、各代 NE 频率表对比。
3. **英文版和网页版**：中文定稿后。
4. 未解决问题视时间补做。
