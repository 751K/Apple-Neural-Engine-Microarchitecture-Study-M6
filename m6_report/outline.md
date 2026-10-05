# 技术报告大纲（v3，2026-10-03）

- 标题（暂定）：**Apple M6 神经网络引擎的微体系结构：基于编译产物、执行追踪与功耗测量的实证研究**
  - 英文：*Inside the Apple M6 Neural Engine: An Empirical Study of Its Microarchitecture via Compiled Programs, Execution Traces, and Power Measurements*
- 体例：完整的技术报告（摘要、引言、相关工作、方法、分章结果、讨论、局限、结论、致谢、参考文献、附录），单篇发布。内容的深度与范围参照 maderix《Inside the M4 ANE》Part 4，但文体采用学术写法。
- 中文版先写（`m6_report/zh.md`），英文版随后（`en.md`），最后通过 GitHub Pages 发布为网页；本仓库作为报告的源码与数据公开。
- v2 大纲（博客体例）见 git 历史；更早的 v1 保留为 `outline_v1.md`。

## 一、文体要求

1. **句子完整**：每句话主语、谓语、宾语齐全，不以名词短语或冒号片段代替句子。表格和图注以外，不使用电报式的省略写法。
2. **学术、干练**：陈述事实与推理，不使用口语和修饰性说法（如"卡了很久""更麻烦的是""令人惊讶"）。叙述主体用"本文"或"我们"，全文保持一致（定为"本文"指文章，"我们"指作者所做的实验）。
3. **段落为主，列表为辅**：论证用段落展开；只有并列的条目（如工具清单、缺陷编号）才使用列表。每个结论应在同一段落内交代依据。
4. **术语统一**：首次出现时给出中文名、英文名和缩写（例如"任务描述符（task descriptor，TD）"），之后只用缩写。术语表放在附录。
5. **编号**：章节用"第 N 章 / N.M 节"；图表按章编号（图 5-1、表 5-2），每张图表都有标题，并在正文中被引用。
6. **证据标注**：每条结论注明证据类别，写在句末的方括号中，例如"……为 64 KiB〔HWX，HAL〕"。证据类别在第 3 章定义（表 3-3）。由证据推出而未直接测量的结论标"推断"，并在正文中说明推理过程。
7. **数据与源码引用**：正文以括注形式引用仓库中的数据和工具，写成相对链接，例如"（数据：[bsdecide.txt](../data/08_bonded/bsdecide.txt)）"。网页构建时改写为仓库链接。每章不再单设"复现"小节，复现方法统一列在附录 A。
8. **文献引用**：用方括号编号，例如"maderix [1]"，文末列参考文献。
9. **更正记录**：正文只陈述最终结论；被推翻的早期结论统一记入附录 C，正文不保留删除线。
10. **章节结构**：每章以一段导言开始，说明本章研究的问题、方法和主要结论；正文分节论述；以"小结"结束（第 2、3 章介绍背景与方法，不设小结），必要时在小结前设"与 M4 的比较"一节。

## 二、全文结构

| 章 | 标题 | 内容 | 主要材料 | 图表 |
|---|---|---|---|---|
| — | 摘要 | 研究对象、方法、主要发现（约 400 字） | 全文 | — |
| 1 | 引言 | 研究背景（M6 首次采用双 ANE）；既有工作的空白；研究问题；本文贡献（5–6 条）；全文组织 | maderix_summary、part4_deep | — |
| 2 | 相关工作 | maderix 系列 [1–4]；Bryngelson 的综述与 ANEForge [5, 6]；Orion [7]；社区文档与 Asahi 驱动 [8, 9]；GPU 逆向的方法参考 [10] | bryngelson_summary、maderix_summary | — |
| 3 | 实验平台与方法 | 平台与软件版本；工具链（只编译的 ANECCompile、Core ML 执行、IOReport / SMC / kdebug 观测、只读逆向）；证据类别（表 3-3）；测量规范（预热、斜率法、中断计数校验、P 核功耗扣除）；研究约束 | experiments §1、bonded_measure §1、compute_array §0、power §7.0、README 约定 | 表 3-1 证据类别 |
| 4 | 体系结构概览 | 两个 ANE × 16 NE；命名层次；电源与时钟域；结构图导读；与 M4 的比较 | zh.md 原第 2 章、hal_analysis | 图 4-1 结构图（已有） |
| 5 | 编译器与程序格式 | HWX 格式与两套程序；权重切分；TD 的寄存器包格式与版本；bonded 切分的成本模型；编译代价与深度上限 | hwx_h18g、bonded_measure §2、compile_cost | 图 5-1 权重切分；图 5-2 TD 格式；图 5-3 双 ANE 切分 |
| 6 | 调度与执行 | 驱动（优先级、选引擎、变体选择）；固件（队列、优先级、抢占）；单次调用的时间分解；并发 | scheduling D1 / D2 / H15 / H54 §1–4 | 图 6-1 调用时间线 |
| 7 | 计算阵列 | 每 NE 每周期乘加数；权重缓冲与 OCG；卷积核形状与 Winograd；PE；吞吐与深度 | compute_array | 图 7-1 OCG 台阶；图 7-2 吞吐与深度 |
| 8 | 数值行为 | Q15.16 累加器；INT8 累加；PE 浮点；LUT 插值误差 | numerics | 图 8-1 累加器；图 8-2 LUT 误差；图 8-3 LUT 误差近景 |
| 9 | 存储层次与数据搬运 | L2 与 bank；Tile DMA；Kernel DMA 与读权重带宽；SLC；DRAM | memory | 图 9-1 中间张量的切块 |
| 10 | 双引擎协同 | 切分方式、同步与共享暂存区；扩展效率；共享带宽；进程内串行 | bonded_measure、hwx_h18g §4 / §7 | 图 10-1 单 / 双 ANE 耗时；图 10-2 切块分配 |
| 11 | 时钟域 | NE 时钟档位与实测频率；共享簇；互连；DRAM | power §6、compute_array、memory C2k | 图 11-1 升频台阶 |
| 12 | 动态调频 | CLPC 的利用率目标、阶跃响应、节流；冷唤醒与断电 | scheduling H54 §5–7、power §2–4 | 图 12-1 利用率目标；图 12-2 阶跃响应 |
| 13 | 功耗与能效 | 测量方法（PP0b 扣除 P 核簇）；功耗分解；每次乘加与每字节能耗；档位与能耗 | power §5、§7 | 图 13-1 功耗分解；图 13-2 能耗与档位 |
| 14 | 实际应用测试 | M4 与 M6 两台 Mac mini（16 GB）上的整机测评：大语言模型、图像分类、文字识别、语音转文字；以 M4 的 ANE 为参照，用前面各章的结论解释现象；GPU 只在功耗部分作参照 | 测评记录（9.22-测评/数据记录.md） | 表 14-1 至 14-6 |
| 15 | 讨论 | 设计特点；对模型部署的建议；与 M1 / M4 / M5 的比较及 HAL 参数表的代际变化；已发现的缺陷与未文档化行为 | comparison、defects、hal_analysis、各章 | 表 15-1 至 15-5 |
| 16 | 局限与未解决问题 | 方法的局限；尚未确定的硬件参数；后续工作 | experiments §5 | 表 16-1 |
| 17 | 结论 | 主要发现的归纳 | 全文 | — |
| — | 参考文献 | | | |
| 附录 A | 工具与复现 | 按章列出工具、数据目录、是否需要 root；复现命令 | tools/、repro_plan、INDEX | |
| 附录 B | 数据索引 | data/ 目录说明；Release 附件清单 | data/ | |
| 附录 C | 更正记录 | 早期结论及其更正原因 | experiments §3、各 notes | |
| 附录 D | 缺陷清单 | A1–A4、B1–B10、C1–C10 | defects | |
| 附录 E | 术语表 | 中英文术语与缩写 | 全文 | |

## 三、写作顺序

1. 第 4、5 章已按 v3 文体重写，作为全文样板。
2. 按章节号顺序写第 6–13 章，每章同时绘制对应的图。
3. 写第 14–16 章与附录。
4. 最后写第 1–3 章和摘要，因为它们要引用全文定稿后的数字。
5. 中文定稿后翻译英文版，再构建网页。

## 四、图表

图统一采用浅色配色，每张图同时输出 SVG 和 PNG，文件名为 `figs/fig<章>-<序号>_<名称>.svg`。

| 图 | 内容 | 数据 | 文件 |
|---|---|---|---|
| 4-1 | 硬件结构 | — | `figs/fig4-1_hardware.svg` |
| 4-2 | 从软件调用到硬件执行 | — | `figs/fig4-2_software.svg` |
| 5-1 | 权重的切分 | hwx_h18g、compute_array | `figs/fig5-1_weight_split.svg`（tools/figs/fig5_1_weight_split.py） |
| 5-2 | TD 格式 | hwx_h18g §9–11 | `figs/fig5-2_td_format.svg`（tools/figs/fig5_2_td_format.py） |
| 5-3 | 双 ANE 程序的切分与同步 | bonded_measure | `figs/fig5-3_bonded.svg`（tools/figs/fig5_3_bonded.py） |
| 6-1 | 单次调用时间线 | d1b_stages | `figs/fig6-1_call_timeline.svg`（tools/figs/fig6_1_timeline.py） |
| 7-1 | 输出通道数的台阶 | data/05_compute/b2b_run.txt | `figs/fig7-1_ocg_step.svg`（tools/figs/fig7_1_ocg_step.py） |
| 7-2 | 吞吐与深度（FP16 / W8A8，M6 / M4） | chains_run2、b6_q8_run、b6x_sweep | `figs/fig7-2_depth_throughput.svg`（tools/figs/fig7_2_depth_throughput.py） |
| 8-1 | Q15.16 累加器 | numerics | `figs/fig8-1_accumulator.svg`（tools/figs/fig8_1_accumulator.py） |
| 8-2 | LUT 误差 | opv 测量 | `figs/fig8-2_lut_error.png`（tools/06_numerics/lut_plot.py） |
| 8-3 | LUT 误差近景 | opv 测量 | `figs/fig8-3_lut_error_zoom.png`（tools/06_numerics/lut_plot.py） |
| 9-1 | 中间张量的切块 | memory | `figs/fig9-1_tiling.svg`（tools/figs/fig9_1_tiling.py） |
| 10-1 | 单 / 双 ANE 耗时与层数 | data/08_bonded/bond_ksweep_run.txt | `figs/fig10-1_bonded_scaling.svg`（tools/figs/fig10_1_bonded_scaling.py） |
| 10-2 | 双 ANE 程序的切块分配 | 表 10-3、10-4 | `figs/fig10-2_split.svg`（tools/figs/fig10_2_split.py） |
| 11-1 | 升频台阶 | data/09_clock/freq_kt | `figs/fig11-1_ramp_steps.svg`（tools/figs/fig11_1_ramp_steps.py） |
| 12-1 | CLPC 利用率目标 | data/10_clpc/gov_kt | `figs/fig12-1_utilization_target.svg`（tools/figs/fig12_1_utilization_target.py） |
| 12-2 | CLPC 阶跃响应 | data/10_clpc/gov_step | `figs/fig12-2_step_response.svg`（tools/figs/fig12_2_step_response.py） |
| 13-1 | 功耗分解 | power_parts4、power_zero | `figs/fig13-1_power_breakdown.svg`（tools/figs/fig13_1_power_breakdown.py） |
| 13-2 | 每次推理能耗与调用间隔 | power_parts、power_parts2、power_parts4 | `figs/fig13-2_energy_vs_level.svg`（tools/figs/fig13_2_energy_vs_level.py） |

全部 18 张图均已完成。数据图共用 `tools/figs/figplot.py`，示意图共用 `tools/figs/figlib.py`；SVG 用 `tools/figs/render.sh` 导出 2 倍分辨率的 PNG。

## 五、发布方式（2026-10-03 定）

- 单篇发布；中文先写，英文版随后。
- 本仓库公开，作为报告的源码；报告通过 GitHub Pages 发布为网页。
- 公开范围：`tools/` 全部公开（含 `tools/re/` 脚本）；固件、kernelcache、编译器反汇编仍只保存在 `private/` 和 M6 上。`data/` 中体积较大的原始文件（HWX 产物、kdebug 原始追踪等）打包为 GitHub Release 附件，仓库保留汇总表和小样本，并在 README 中说明下载方式。
- 发布前的工作：英文 README；大文件拆分与 Release 清单；Pages 构建（Markdown 转网页、链接改写）；检查仓库中不含个人信息和苹果二进制。

## 六、篇幅

正文约 3–3.5 万字（中文），18 张图、30 余张表。第 4–13 章每章 2000–3500 字，第 7、9、12、13 章可至 4000 字。
