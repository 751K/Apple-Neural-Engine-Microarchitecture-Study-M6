# 英文版术语表与格式约定

英文版 `final_report/en.md` 以中文定稿 `final_report/zh.md`（提交 309228a）为准逐段翻译，不增删内容，不重新编号。本文件供翻译与校对使用，定稿后可保留在仓库中。

## 一、格式约定

| 中文 | 英文 | 说明 |
| --- | --- | --- |
| 第 5.8.3 节；（第 5.8.3 节） | Section 5.8.3；(Section 5.8.3) | 多节：Sections 5.7–5.8；Sections 5.7 and 10.4 |
| 第 5 章 | Chapter 5 | |
| 图 5-4 / 表 10-7 / 表 E-1 | Figure 5-4 / Table 10-7 / Table E-1 | 编号与中文版完全相同 |
| 附录 A | Appendix A | |
| `## 1. 引言` | `## 1. Introduction` | 章节号保持不变 |
| `## 附录 A　工具与复现` | `## Appendix A. Tools and Reproduction` | |
| `*表 5-1　标题*` | `*Table 5-1. Title*` | 图注同理：`Figure 5-4. ...` |
| 〔HWX，推断〕 | 〔HWX, inferred〕 | 保留六角括号，与参考文献 [4] 区分；见第三节标签译法 |
| 约 30 µs | about 30 µs（正文）；≈30 µs（表格、括号内） | |
| 2.2 倍 | 2.2× | 正文中也可用 "2.2 times"，同一段内统一 |
| 下降 17% | 17% lower / drops by 17% | 百分点写作 percentage points（表格中 pp） |
| 本文 | this report | 不用 "this paper" |
| 我们 | we | 中文原文用"我们"处照译；"本文"处用 this report |
| 引号"……" | "..." | 直角引号「」不出现 |
| 全角括号、冒号、分号 | 半角，后接空格 | |

- 表注与图注用句首大写（sentence case）：`*Table 2-1. Conclusions corrected in the maderix series*`；章节标题用标题大写（title case）。
- 证据标签前留一个空格：`... the M6 〔inferred〕.`
- CLPC 前加定冠词：the CLPC。芯片名作名词时加定冠词（on the M6、compared with the M4），作修饰语时不加（the M6 ANE、M4 control experiments）。
- maderix 作为作者署名始终小写，句首亦然；以 "the author" 指代，不用 "it"。
- "第 N 章" 一律译为 Chapter N，不可译为 Section N。
- 拼写用美式英语；数字与单位之间留空格（30 µs、150 GB/s、2 MiB），百分号不留空格（77%）。
- 范围用 en dash：130–325 µs、Sections 6.5.2–6.5.3。
- 代码标识符、路径、寄存器名、命令保持原样并保留反引号；插图路径 `figs/zh/` 改为 `figs/en/`。
- 参考文献条目本为英文，原样保留。
- 标题：*Microarchitecture of the Apple M6 Neural Engine: An Empirical Study Based on Compiled Artifacts, Execution Traces, and Power Measurements*。

## 二、已确定的几处译法

1. **忙碌比例**：busy fraction。插图中原有的 "busy ratio" 已随之修改。
2. **档位**：DVFS state。最高档 / 最低档为 top state / lowest state；"NE 时钟档位" 为 NE DVFS state；插图中原有的 "clock level" 已随之修改。
3. **证据标签**：保留六角括号〔〕，内部用英文逗号，如〔HWX, inferred〕。
4. **第 14 章"实际应用测试"**：Application Benchmarks；"整机测评" 也译为 application benchmarks。

## 三、证据类别标签

| 中文 | 英文 |
| --- | --- |
| 计时 | timing |
| 推断 | inferred |
| 内核 | kernel |
| 固件 | firmware |
| 编译器 | compiler |
| 数值 | numerical |
| HWX、HAL、kdebug、IOReport、ioreg、SMC | 原样 |

例：〔计时，kdebug，推断〕→〔timing, kdebug, inferred〕。

## 四、章节标题

| 中文 | 英文 |
| --- | --- |
| 摘要 | Abstract |
| 1. 引言 | 1. Introduction |
| 2. 相关工作 | 2. Related Work |
| 3. 实验平台与方法 | 3. Platform and Methodology |
| 4. 体系结构概览 | 4. Architecture Overview |
| 5. 编译器与程序格式 | 5. Compiler and Program Format |
| 6. 调度与执行 | 6. Scheduling and Execution |
| 7. 计算阵列 | 7. Compute Array |
| 8. 数值行为 | 8. Numerical Behavior |
| 9. 存储层次与数据搬运 | 9. Memory Hierarchy and Data Movement |
| 10. 双引擎协同 | 10. Dual-Engine Cooperation |
| 11. 时钟域 | 11. Clock Domains |
| 12. 动态调频 | 12. Dynamic Frequency Scaling |
| 13. 功耗与能效 | 13. Power and Energy Efficiency |
| 14. 实际应用测试 | 14. Application Benchmarks |
| 15. 讨论 | 15. Discussion |
| 16. 局限与未解决问题 | 16. Limitations and Open Questions |
| 17. 结论 | 17. Conclusion |
| 致谢 / 参考文献 | Acknowledgments / References |
| 附录 A　工具与复现 | Appendix A. Tools and Reproduction |
| 附录 B　数据索引 | Appendix B. Data Index |
| 附录 C　更正记录 | Appendix C. Corrections Log |
| 附录 D　缺陷清单 | Appendix D. Defect List |
| 附录 E　术语表 | Appendix E. Glossary |

## 五、术语

附录 E 中已给出英文的条目（ANE、BAR、CLPC、NE、PE、TD、TQ、Tile DMA、Kernel DMA、SLC 等）照其英文列使用，下表不再重复。

### 5.1 硬件与结构

| 中文 | 英文 | 备注 |
| --- | --- | --- |
| 神经网络引擎 | Neural Engine (ANE) | 首次出现给全称 Apple Neural Engine |
| 引擎；双引擎；单引擎 | engine; dual-engine; single-engine | |
| 神经引擎核 | NE core；简称 NE | |
| 平面引擎 | planar engine (PE) | |
| 计算阵列；乘加阵列 | compute array; MAC array | |
| 乘加 | multiply-accumulate (MAC) | 复数 MACs |
| 乘加单元 | MAC unit | |
| 累加器 | accumulator | |
| 共享簇 | ANE shared cluster；简称 shared cluster | |
| 片上；片上存储 | on-chip; on-chip storage | |
| 系统级缓存 | system-level cache (SLC) | |
| 裸片 | die | |
| 互连 | fabric | 指 Fabric DVFM 相关时；泛指时 interconnect |
| 内存控制器 | memory controller | |
| 通道（DRAM） | channel | 与卷积"通道"同词，必要时写 DRAM channel |
| 电源轨 | power rail | |
| 电压域；调压域 | voltage domain | |
| 电源门控；断电 | power gating; powered off | |
| 设备树 | device tree (IORegistry) | |
| 固件处理器 | firmware processor (IOP) | |
| 地址翻译单元 | address translation unit (DART) | |
| 映射器 | mapper | |
| 缓冲区；环形缓冲 | buffer; ring buffer | |
| 权重缓冲 | weight buffer | |
| bank | bank | |

### 5.2 编译器与程序格式

| 中文 | 英文 | 备注 |
| --- | --- | --- |
| 编译器 | compiler | |
| 编译产物 | compiled artifact；HWX 文件 | |
| 编译服务 | compiler service | |
| 编译目标 | compilation target | |
| 分段器；分段 | segmenter; segmentation | |
| 段（ANE 段） | segment (ANE segment) | |
| 后端 | backend | |
| 单 ANE 程序 / 双 ANE 程序 | single-ANE program / dual-ANE program | 对应 nonbonded / bonded |
| 程序（一套） | program | "两套程序" = two programs |
| 硬件参数表 | hardware parameter table (HAL) | |
| 性能模型；成本模型 | performance model; cost model | |
| 延迟估计 | latency estimate | |
| 任务描述符 | task descriptor (TD) | |
| TD 序列 | TD sequence | |
| 任务头 | task header | |
| 写入包；连续写；掩码写 | write packet; contiguous write; masked write | |
| 地址包 | address packet | |
| 包头字；值字 | header word; value word | |
| 卷积配置字 | convolution configuration word | |
| 寄存器写入 | register write | |
| 布局（TD 布局 v24） | layout (TD layout v24) | |
| 代际比较值 | ArchCompareValue | |
| 静态重定位 | static relocation | |
| 运行时操作图 | runtime operation graph (RTGraph) | |
| 切分；按行切分；按输出通道切分 | split; row split; output-channel split | 动词 split a layer across the two ANEs |
| 切块；块 | tiling; tile | |
| 重叠行 | halo rows | |
| 共享暂存区 | shared scratch buffer | |
| 同步记录 | sync record | |
| 拷贝合并 | copy-and-merge | |
| 趟 | pass | |
| 常驻权重上限 | resident-weight limit | |
| 权重常驻 | weights resident on chip；形容词 weight-resident | |
| 改写核 | rewritten kernel | |
| 原生层 | native layer | |
| 输出通道组 | output channel group (OCG) | |
| 静态单赋值 | static single assignment (SSA) | |
| 反汇编 | disassembly | |

### 5.3 运行时、调度与主机

| 中文 | 英文 | 备注 |
| --- | --- | --- |
| 主机；主机侧 | host; host side | |
| 驱动 | driver | |
| 守护进程 | daemon | |
| 运行时 | runtime | |
| 请求；任务；作业 | request; task; job | 三者在文中含义不同，严格对应 |
| 提交 | submit / submission | |
| 同步调用 / 异步调用 | synchronous call / asynchronous call | |
| 在途 | in flight | |
| 批量 | batch | |
| 调用耗时 | per-call time | |
| 任务时长 | task duration | |
| 任务结束 | task end | |
| 固定开销 | fixed overhead | |
| 主机开销 | host overhead | |
| 提交侧开销 / 完成侧开销 | submission-side overhead / completion-side overhead | |
| 空闲；空闲深度 | idle; idle depth | |
| 睡眠 | sleep | |
| 唤醒 | wake-up | |
| 空转进程 | spinner process | |
| 优先级；作业队列 | priority; job queue | |
| 硬件任务队列 | hardware task queue (TQ) | |
| 节流；占空比窗口 | throttling; duty-cycle window | |
| 请求间依赖 | inter-request dependency (fence) | |
| 进程；线程；同一进程 | process; thread; in-process | |
| 客户端 | client | |
| 固件时间戳 | firmware timestamp | |
| 内核事件追踪 | kernel event tracing (kdebug) | |

### 5.4 性能与方法

| 中文 | 英文 | 备注 |
| --- | --- | --- |
| 斜率法 | slope method | |
| 边际吞吐 | marginal throughput | |
| 边际耗时 | marginal time | |
| 吞吐 | throughput | |
| 峰值 | peak | |
| 计算受限 | compute-bound | |
| 读权重受限 | weight-read-bound | 名词：weight-read bound |
| 读权重带宽 | weight-read bandwidth | |
| 计算密集 | compute-dense | 与插图一致 |
| 加速比 | speedup | |
| 扩展效率 | scaling efficiency | |
| 计算量 | amount of compute；FLOPs | |
| 工作量（每次调用） | work per call | |
| 卷积链 | convolution chain；图中 conv chain | |
| 层数 | number of layers；layer count | |
| 基准模型 | baseline model | |
| 满载 | at full load | 指连续忙碌 |
| 满频 | at full clock | |
| 实测；测得 | measured | |
| 预期（第 10、14 章） | expectation | "预期一" = Expectation 1 |
| 证据类别 | evidence category | |
| 拟合；残差；均方根 | fit; residual; RMS | |
| 复现 | reproduce / reproduction | |
| 缺陷（B8） | defect (B8) | |

### 5.5 数值与数据格式

| 中文 | 英文 | 备注 |
| --- | --- | --- |
| 定点 | fixed-point | |
| 舍入 | rounding | |
| 溢出 | overflow | |
| 激活（张量） | activations | |
| 激活函数 | activation function | |
| 中间张量；中间结果 | intermediate tensor; intermediate result | |
| 逐元素运算 | elementwise operation | |
| 查找表 | lookup table (LUT) | |
| 插值 | interpolation | |
| 偏置 | bias | |
| 卷积核；核宽 | kernel; kernel width | |
| 步长 | stride | |
| 稠密 / 稀疏 | dense / sparse | |
| 剪枝；结构化剪枝；非结构化剪枝 | pruning; structured pruning; unstructured pruning | |
| 量化 | quantization | |
| 调色板 | palettization；palettized weights | coremltools 用语 |
| 分组调色板 | grouped-channel palettization | |
| 向量调色板 | vector palettization | |
| 零权重检测 | zero-weight detection (KernelDetectZeros) | |
| 微缩放格式 | microscaling (MX) formats | |

### 5.6 时钟、调频与功耗

| 中文 | 英文 | 备注 |
| --- | --- | --- |
| 时钟域 | clock domain | |
| 档位；时钟档位 | DVFS state；NE DVFS state | |
| 最高档 / 最低档 | top state / lowest state | |
| 档位众数 | modal state | |
| 调频；动态调频 | frequency scaling; dynamic frequency scaling (DVFS) | |
| 升频 / 降频 | ramp up / ramp down | |
| 提速（冷启动后） | ramp-up | |
| 台阶 | step | |
| 忙碌比例 | busy fraction | |
| 利用率；利用率目标 | utilization; utilization target | |
| 指数平均 | exponential moving average (EWMA) | |
| 时间常数 | time constant | |
| 性能域 | performance domain | |
| 闭环性能控制器 | closed-loop performance controller (CLPC) | |
| 功耗；净功耗 | power; net power | |
| 能耗；每次运算能耗 | energy; energy per operation | |
| 能效 | energy efficiency | |
| 功耗直方图 | power histogram | |
| 读数 | reading | |
| 共用开销（功耗） | shared overhead | |
| 热设计功耗 | thermal design power (TDP) | |

### 5.7 实际负载（第 14 章）

| 中文 | 英文 | 备注 |
| --- | --- | --- |
| 大语言模型 | large language model (LLM) | 首次给全称 |
| 词元 | token | |
| 预填充 / 解码 | prefill / decode | |
| 投机解码；多词元预测 | speculative decoding; multi-token prediction (MTP) | |
| 标准模型 / 定制模型 | standard model / custom model | |
| 文字检测 / 文字识别 | text detection / text recognition | |
| 一次 16 张 | batch of 16 | |
| 整机测评 | application benchmark | |
| 部署 | deployment | |
