# M6 ANE 硬件研究

研究 Apple M6（T8152，ANE 架构 h18g）神经网络引擎的硬件：结构、计算、存储、调度、时钟、功耗、数值。参照 maderix《Inside the M4 ANE》Part 1–4 与 Bryngelson 的论文，最终产出中英文技术报告（Markdown + 网页）。

- 机器：M6（16 GB），macOS 27.0.1（26A434），ANE 编译器 `zin_ane_compiler v10.26.6`；对照机为 M4（h16g）。
- 当前状态（2026-10-03）：实验基本完成；报告大纲 v2 已定，第 2 章全景有初稿。

## 从哪里开始看

| 想看 | 去哪里 |
|---|---|
| 全部结论，以及每条对应的数据、工具 | [`INDEX.md`](INDEX.md) |
| 报告大纲、图表清单、写作顺序 | [`m6_report/outline.md`](m6_report/outline.md) |
| 报告正文（中文） | [`m6_report/zh.md`](m6_report/zh.md) |
| 结构图 | [`figs/m6_ane_dark.png`](figs/m6_ane_dark.png) |
| 某个主题的详细实验记录 | `notes/` 下的分册（见下） |
| 被推翻、更正过的结论 | `notes/experiments.md` §3，以及各分册中的删除线 |

## 目录

```
INDEX.md          结论索引（按报告章节）
README.md         本文件
REORG_PLAN.md     2026-10-03 目录重组的记录（data/、tools/ 的移动清单与注意事项）
m6_report/        报告：outline.md（大纲 v2）、outline_v1.md（旧大纲）、zh.md（正文）
figs/             图（SVG + PNG）
notes/            实验记录分册
data/             原始数据，按报告章节分目录
tools/            工具，按用途和章节分目录
```

### notes/ 分册

| 文件 | 内容 |
|---|---|
| `experiments.md` | 实验总览：测量手段、按主题的结论、纠错记录、局限 |
| `compute_array.md` | 计算阵列：MAC 宽度、INT8、OCG、核形状、Winograd、PE、性能模型、时钟 |
| `memory.md` | 存储与带宽：L2、读权重、Tile DMA、DRAM、主机空闲深度 |
| `scheduling.md` | 调度与开销、并发、固件与驱动的调度、CLPC 调频（H54） |
| `bonded_measure.md` | 双 ANE 的切分条件与扩展 |
| `power.md` | 电源状态、冷唤醒、频率、功耗与能效（§7） |
| `numerics.md` | 累加器、舍入、查找表、INT8 路径 |
| `hwx_h18g.md` | 编译产物格式、TD 打包、卷积配置字 |
| `hal_analysis.md` | 编译器硬件参数表 |
| `compile_cost.md` | 编译耗时 |
| `defects.md` | 疑似缺陷与未写进文档的行为 |
| `comparison.md` | 与 M1 / M4 / M5 对照 |
| `repro_plan.md` | 实验计划与编号（A–H 组） |
| `maderix_summary.md`、`part4_deep.md`、`bryngelson_summary.md` | 参考文献整理 |
| `m6_compiler_recon.md` | 早期对编译器的探查 |

### data/ 与 tools/ 的章节目录

两者按报告章节一一对应：`02_overview`、`03_compile`、`04_schedule`、`05_compute`、`06_numerics`、`07_memory`、`08_bonded`、`09_clock`、`10_clpc`、`11_power`。另外：

- `data/_obsolete/`：已作废的数据（保留备查）。
- `tools/common/`：通用运行器与采样器（`bondrun.m`、`anecc.m`、`anewho.c`、`smcpower.c`、`pclus.c`、`chain.py`、`runall.sh`、模型清单 `*.list` 等）。
- `tools/lib/`：公共 Python 模块（`td_widths`、`tdwalk`、`tdpkt`、`hwx_bonded` 等）。
- `tools/re/`：只读逆向工具（符号、字符串、交叉引用、反汇编、固件分析）。
- `tools/deploy_m6.sh`：把工具平铺同步到 M6。

## 两台机器的分工

| | 本机（M4，本仓库） | M6（下文记作 `$M6_HOST`，形如 `user@m6-host.local`） |
|---|---|---|
| 作用 | 整理、分析、写报告、版本管理 | 生成模型、编译、运行实验 |
| 目录 | 本仓库 | `~/anehal/hwx/`（工具平铺，模型、编译产物、结果都在这里）；`~/anehal/fw/`、`~/anehal/kc/`（固件与 kernelcache，只读） |
| Python | `/opt/miniconda3/bin/python3`（numpy） | 生成模型：`/opt/miniconda3/envs/mps/bin/python`（torch 2.7、coremltools 9.0）；其余脚本用系统 `python3` |

### 工作流程

1. 在本仓库修改或新增工具，然后同步到 M6：
   ```bash
   export M6_HOST=user@m6-host.local   # M6 的 ssh 地址
   tools/deploy_m6.sh -n     # 预演，列出要传的文件
   tools/deploy_m6.sh        # 同步（只传有变化的文件，不删除 M6 上的任何东西）
   ```
2. 在 M6 上按需编译改动过的 C / Objective-C 工具（编译命令写在各文件开头），例如：
   ```bash
   ssh $M6_HOST 'cd ~/anehal/hwx && clang -fobjc-arc -O2 bondrun.m -framework Foundation -framework CoreML -o bondrun'
   ```
3. 运行实验。不需要 root 的直接用 ssh 运行；需要 root 的 kdebug 脚本（`*_ktrace.sh`、`gov_step.sh` 等）由用户自己在终端运行（脚本内部用 `$SUDO_USER` 降权运行负载、改回结果文件的属主）：
   ```bash
   ssh -t $M6_HOST 'cd ~/anehal/hwx && sudo ./gov_ktrace.sh'
   ```
4. 把结果拷回本仓库对应章节的 `data/` 目录，分析后更新 `notes/` 和 `INDEX.md`，提交。

## 约定

- **只用公开路径执行**：模型由 Core ML 执行；编译用 `ANECCompile` 只编译、不执行；不直接加载或执行修改过的 HWX，不使用私有执行客户端。
- **观测只读**：IOReport、SMC、ioreg、kdebug（只记录事件）。需要 `sudo` 的步骤由用户本人运行。
- **固件和 kernelcache 只做只读分析，不分发**；它们和编译器的反汇编都只留在 M6 上，不入库。
- **不修改系统安全设置**。唯一的例外是经用户同意、只作用于本项目 `anecc` 进程的 DYLD 插桩（`tools/common/anevariant.c`），用于导出编译器的性能模型 CSV。
- **测量习惯**：
  - 每个实验检查 IOReport 中断数，确认确实在 ANE 上执行；
  - 先连续预热 ≥ 1 s，中间不插入空闲（CLPC 会降频）；
  - 每点至少两轮；
  - 测功耗时 PP0b 必须扣除 P 核簇功耗（`tools/common/pclus.c`）。
- 16 GB 内存，不要并行跑大计算；M6 保持 ≥ 20 GB 可用空间。

## 历史

- 2026-09-29：在 `ANE/report/` 开始；早期结论（如"片上约 32 MB""FP16 约 50 TOPS""INT8 功耗 14–16 W"）后来都被更正或重新解读（例如片上容量见 `notes/memory.md` C1d、C2b，功耗见 `notes/power.md` §7）。
- 2026-10-03：拷贝到本仓库并建 git；`data/`、`tools/` 按章节重组（见 `REORG_PLAN.md`）；建立 `INDEX.md`。原目录 `ANE/report/` 保留作备份、不再修改。
