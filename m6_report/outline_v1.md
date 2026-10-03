# 技术报告大纲：Inside the M6 ANE — Two Engines, One Program

- 形式：参照 maderix Part 4（https://maderix.github.io/articles/inside-the-m4-ane-part-4/）。
- 产出：
  - 中文版和英文版各一份；
  - 源稿是 Markdown：`m6_report/zh.md`、`m6_report/en.md`；
  - 发布版是网页（单页长文，含框图、图表、表格）。
- 写法：每条结论都标出证据来源，标签沿用 Part 4，并加上本项目自己的几种：

| 标签 | 证据来源 |
|---|---|
| 【HAL】 | 编译器硬件参数表（在自己的进程里调用 `ZinIrHal*::GetParams`） |
| 【HWX】 | 编译产物对比（直接调用 `ANECCompile`，只编译、不执行） |
| 【计时】 | Core ML 公开接口计时，用改层数取斜率的方法 |
| 【IOReport】 | 无 root 的 IOReport 计数（每个 ANE 的中断、电源状态、时钟开启时间、链路带宽） |
| 【数值】 | 构造输入，比较 ANE 和 CPU 的输出 |
| 【ioreg】 | 设备树 |
| 【引用】 | maderix、Bryngelson 的数据 |

## 章节

| # | 章节 | 内容 | 主要材料 | 状态 |
|---|---|---|---|---|
| 0 | 摘要 | 一张"关键数字"表：2×16 NE、fp16 单 / 双 ANE 20.6 / 39.5 TFLOPS、Q15.16 定点累加器、0.3 s 爬升、1.92× 双引擎扩展 | 各节 | 待写 |
| 1 | 方法 | 不用私有执行接口：编译用 ANECCompile，执行只用 Core ML，观测用 IOReport；中断计数怎么校准；斜率法；两个计时坑 | bonded_measure §1、compute_array §0 | 材料齐 |
| 2 | 设备身份 | 两个 H11ANE 设备、h18g、各自的电源门控、共用时钟、同一个 die；命名层次（M6 / T8152 / H18 / h18g / H16 kext） | m6_ioreg、hal_analysis | 材料齐 |
| 3 | 从 MIL 到两个 ANE | 改编自 Part 4 的 9 步图：多出 bonded / nonbonded 两种版本，RTGraph（`__RUNTIME`），两个 kick；Core ML 怎么在两种版本里选 | hwx_h18g §1–2、bonded_measure §1 | 材料齐 |
| 4 | 硬件框图 | 两个引擎 × 16 NE、L2、tile / kernel DMA、每个引擎两条 DRAM 链路（L0/L1）、PE；和 M4 的图对比 | ioreg + IOReport 通道名 + HAL | 待画 |
| 5 | HAL：H16g → H17s → H18 → H19 | 字段对照，H18 新增的能力 | hal_analysis | 材料齐 |
| 6 | 双引擎 | 按空间切（H 或 W）、阈值、共享 bss 和同步、权重各读一份；1.92× 扩展，权重受限时 1.4× | hwx_h18g §6、bonded_measure | 材料齐 |
| 7 | 计算阵列 | OCG 跳变、NE 数、核尺寸、没有 Winograd、按深度的吞吐表（FP16 / W8A8，对照 M4） | compute_array | 进行中 |
| 8 | 存储与带宽 | 操作数阈值、权重工作集、单 / 双 ANE 的 DRAM 带宽 | C 组 | 待测 |
| 9 | 调度与重叠 | 固定开销、中断次数、两个模型并发能否分到两个 ANE、内部重叠、图深度上限 | D 组 | 待测 |
| 10 | 电源与时钟 | 空闲断电、0.3 s 爬升（2.8 倍）、冷唤醒、降频事件；功耗（需要你跑 sudo powermetrics） | E 组 | 部分 |
| 11 | 数值 | Q15.16 定点累加器、远离零舍入、exp=31 的解码、PE 是浮点；M4 结果相同 | numerics | 材料齐 |
| 12 | 限制与未解决问题 | 不能强制单 / 双 ANE；没有 per-TD 计数器；没有修改 HWX 后执行的验证 | — | 待写 |
| 13 | 附录 | 工具清单、复现命令、原始数据 | tools/、data/ | 待写 |

## 图表计划

1. 双引擎执行流程图（第 3 节）
2. M6 ANE 框图（第 4 节）
3. 单 / 双 ANE 的耗时与层数关系（两条直线，斜率之比 1.92）
4. 宽度阈值：单 ANE 与双 ANE 的分界（第 6 节）
5. OCG 阶梯：每层耗时与通道数的关系（第 7 节）
6. 按深度的吞吐：M6 与 M4（第 7 节）
7. 时钟爬升：每次调用耗时的时间序列（第 10 节）
8. 定点累加器的示意图：位宽、溢出、舍入（第 11 节）
