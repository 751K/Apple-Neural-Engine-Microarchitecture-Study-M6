# 结论索引

每一行是一条结论，按报告章节排列，列出证据、数据、工具和笔记出处。写报告时按此取材；改结论时同步改这里。

- **证据**：【计时】Core ML 公开接口计时 ·【kdebug】固件任务时间戳（需 root）·【IOReport】·【SMC】·【HWX】编译产物 ·【编译器】ANECompiler 参数表 / 逆向 / 性能模型 ·【固件】【内核】只读分析 ·【ioreg】·【数值】·【推断】
- **root**：● 需要用户在 M6 上 `sudo` 运行（只记录事件，不改系统）；空白 = 不需要。
- **运行位置**：采集脚本都在 M6 的 `~/anehal/hwx/` 运行（`tools/deploy_m6.sh` 同步），结果拷回本仓库 `data/`；分析脚本在本机或 M6 均可。
- 路径相对仓库根目录；`data/xx/*` 表示该目录下多个文件。

## 02 全景

| 结论 | 证据 | 数据 | 工具 | root | 笔记 |
|---|---|---|---|---|---|
| 2 个 ANE（`ane` / `ane1`），同一个 die，各自电源门控，`clock-ids` 相同，`BondedModeSupported = 1` | 【ioreg】 | `data/02_overview/m6_ioreg_ane_20261002.md` | `ioreg` | | `m6_report/zh.md` §2.3 |
| 每个 ANE 16 个 NE（ioreg `NumANECores`、HAL 0x00c、权重切 16 份） | 【ioreg】【HAL】【HWX】 | 同上；`data/03_compile/hwx/`；HAL 原始导出不公开（`tools/re/dump2.c` 重新生成） | `tools/re/dump2.c`、`tools/lib/hwx_parse.py` | | hal_analysis 结论 1、hwx_h18g §3 |
| 代号层次：M6 / T8152 / h18g / H18（Soc2026BaseLine）/ H11ANE（AppleH16ANEInterface）/ TD v24 | 【ioreg】【编译器】 | 编译器反汇编不公开（`tools/re/xref.c`、`tools/re/fnbytes.c` 重新生成） | `tools/re/xref.c` | | hwx_h18g §11.3、power §6.1 |

## 03 从模型到程序（编译）

| 结论 | 证据 | 数据 | 工具 | root | 笔记 |
|---|---|---|---|---|---|
| HAL 参数表：同代各变体完全相同；与 Bryngelson 偏移对照（+0x8 / +0x20）；L2 bank 64、常驻权重上限 64 KiB、单操作数 2 MiB | 【HAL】 | 原始导出与字段总表不公开（`tools/re/dump2.c`、`tools/re/hal_readers.py` 重新生成）；关键字段见笔记 | `tools/re/dump2.c`、`tools/re/fnbytes.c`、`tools/re/hal_readers.py` | | hal_analysis |
| HWX：每个模型有 nonbonded / bonded 两套程序；`__RUNTIME` 运行时操作图；50 种层、33 种激活 | 【HWX】 | `data/03_compile/hwx/`、`data/03_compile/hwx_cases/` | `tools/common/anecc.m`、`tools/lib/hwx_parse.py`、`tools/lib/hwx_bonded.py` | | hwx_h18g §1–2、§6 |
| TD 指令流打包：包头低 15 位为寄存器字地址，bit 31 掩码写，bit 29 地址包（BAR：4 权重、20 DSID、24 起先输出后输入） | 【HWX】【编译器】 | `data/03_compile/xword_samples.txt`、`data/03_compile/td_*` | `tools/lib/tdpkt.py`、`tools/03_compile/xword.py`、`tools/03_compile/hwxreloc.py` | | hwx_h18g §11.1、§11.4 |
| TD 布局版本：M6 = h19 = v24，h18 = v20；19 个编译目标按布局分 4 组 | 【编译器】【HWX】 | `data/03_compile/tdv/`（反汇编 `tdver/` 不公开） | `tools/re/xref.c`、`tools/re/jtab.c`、`tools/lib/td_widths.py` | | hwx_h18g §11.2–11.3 |
| 卷积配置字位定义（Kw / Kh / Sx / Sy / Pad / Ox / Oy） | 【HWX】【编译器】 | `data/03_compile/convcfg_scan.txt`、`data/03_compile/ox_tddump.txt`（反汇编 `td31.*` 不公开） | `tools/03_compile/convcfg.py`、`tools/03_compile/tddump.py` | | hwx_h18g §10 |
| 编译耗时：双 ANE 版本对逐元素层超线性（约 3.5–3.8 次方）；Core ML 首次加载时编译只在 E 核上跑（慢 2.7 倍） | 【计时】 | `data/03_compile/h7_compile_time.txt`、`data/03_compile/cm_load_vs_compile.txt` | `tools/common/anecc.m`、`tools/common/cmload.m` | | compile_cost |
| 图深度上限 386 层：双 ANE 编译路径栈溢出，之后退回 CPU 或加载卡死 | 【计时】【编译器】 | `data/03_compile/h9_depth_compile.txt`、`data/04_schedule/d5_depth_run.txt` | `tools/common/chain.py`、`tools/common/anecc.m` | | compile_cost §4、defects A1 |
| Whisper 编码器编译为 h18g：空间拆分的全局细化每层写约 2.4 GB 交换文件（32 层约 78 GB），h18 / h16g 41 s、3.8 GB；一层即可复现；关掉 `GlobalRefinementInSpatialSplit` 则退回只用 ANE0 | 【计时】【编译器】【HWX】 | `data/03_compile/whisper_compile/`（调用栈、`model.mil` 不公开：`private/whisper_ane_mil/`） | `tools/03_compile/whisper_load.sh`、`whisper_tmp.sh`、`whisper_capture.sh`、`whisper_anecc.sh`、`whisper_trunc.py` | ●（抓取、看交换文件） | whisper_compile、compile_cost §5、defects A3 / A4 |

## 04 调度

| 结论 | 证据 | 数据 | 工具 | root | 笔记 |
|---|---|---|---|---|---|
| 每次调用：提交约 30 µs；任务结束后 130–325 µs（随任务时长增加，不按层数增长）；2–3 次中断 | 【kdebug】 | `data/04_schedule/d1b_kt/`、`data/04_schedule/d1b_stages.txt` | `tools/04_schedule/d1b_ktrace.sh`、`tools/04_schedule/d1b_stages.py` | ● | scheduling D1、D1c |
| 任务结束后的增长全在主机侧（驱动完成处理、用户线程唤醒），原因是 CPU 进入深度空闲 | 【kdebug】 | `data/07_memory/sw_*`、`data/04_schedule/d1b_warm.txt` | `tools/07_memory/sw_ktrace.sh` | ● | memory C2j、defects B5 |
| 同步调用时两次调用之间 ANE 空闲约 384 µs | 【kdebug】 | `data/10_clpc/gov_kt/` | `tools/10_clpc/gov_fit.py` | ● | scheduling H54 §6 |
| 每层固定开销 ≤ 13 ns | 【计时】 | `data/04_schedule/d6_tiny.txt`、`data/04_schedule/d5d6_run2.txt` | `tools/common/chain.py`、`tools/common/bondrun.m` | | scheduling D6b |
| 独立支路串行；MAC 与 PE、DMA 与 PE 不重叠 | 【计时】 | `data/04_schedule/d3_overlap_run*.txt` | `tools/04_schedule/overlap.py` | | scheduling D3 / D4 |
| 同一程序在一个进程内严格串行；不同程序或进程可分到两个 ANE（约 1.8×） | 【计时】【IOReport】 | `data/04_schedule/d2_concurrency.txt`、`data/04_schedule/h15_mt*.txt` | `tools/common/mtrun.m`、`tools/common/bondrun.m` | | scheduling D2、H15、defects B3 |
| 驱动：优先级映射（固件 6 级）、选引擎评分（WRK / HOL / CLPC / THROT / clientPref / PWR）、变体选择、fence、防饿死 | 【内核】 | M6：`~/anehal/kc/kc_strings_off.txt`（不入库） | `tools/re/kcdis.py` | | scheduling H54 §2 |
| 固件：作业队列 8 + 1（AFPP），硬件 TQ 每个两槽，可切换 / 降优先级，动态电源门控；固件不选时钟档位 | 【固件】 | M6：`~/anehal/fw/`（不入库） | `tools/re/fwref.py`、`tools/re/fwfunc.py`、`tools/re/im4p_extract.py` | | scheduling H54 §3 |

## 05 计算阵列

| 结论 | 证据 | 数据 | 工具 | root | 笔记 |
|---|---|---|---|---|---|
| 每 NE 每周期 256 次 FP16 乘加；单 / 双 ANE 实测 20.6 / 39.5 TFLOPS（1.92×），理论 21.1 / 42.3 | 【计时】【kdebug】 | `data/08_bonded/bond_*`、`data/09_clock/freq_kt/` | `tools/08_bonded/bond_sweep.py`、`tools/common/bondrun.m` | | bonded_measure §3、power §6.5 |
| INT8 每 NE 每周期 512 次乘加（每个累加器同时算 2 个输出通道）；单引擎 1×1 实测 428 | 【编译器】【kdebug】 | `data/05_compute/mac3_run.txt`、`data/05_compute/macw_td.txt` | `tools/05_compute/mac3.py`、`tools/05_compute/mac3_fit.py`、`tools/05_compute/macw.py`、`tools/05_compute/macw_td.py` | ● | compute_array H51 |
| W8A8：3×3 上为 FP16 的 2.0×（单 ANE 有效 62 TOPS）；1×1 链受激活带宽限制，双 ANE 时与 FP16 持平；只量化权重不加速 | 【计时】 | `data/05_compute/h10_*`、`data/05_compute/b6_q8_run.txt`、`data/05_compute/b6_w8_recheck.txt` | `tools/05_compute/w8a8.py` | | compute_array H10、B6 / B7、defects B4 |
| 硬件 Winograd，按形状启用（3×3 单 ANE 有效 31 TFLOPS）；膨胀卷积不用 | 【计时】【HWX】 | `data/05_compute/h10_dilation.txt` | `tools/05_compute/dilconv.py` | | compute_array B5、H10 |
| 每 NE 权重缓冲 64 KiB；FP16 一次最多 16 个输出通道（OCG），256 → 272 通道 +32% 台阶 | 【计时】【HWX】【HAL】 | `data/05_compute/ocg_table.txt` | `tools/05_compute/ocg.py` | | compute_array B2 / B3、H53 |
| 编译器高档位（FP16 512 / INT8 1024）只出现在单 ANE 大工作单元程序，Core ML 执行的 bonded 程序用不到 | 【编译器】【kdebug】 | `data/05_compute/perfcsv/`、`data/05_compute/hi_kt/`、`data/05_compute/hi2_kt/`、`data/05_compute/val_run.txt` | `tools/05_compute/perfcsv.py`、`tools/common/anevariant.c`、`tools/05_compute/hi_fit.py`、`tools/05_compute/hi2_fit.py` | ● | compute_array H53 §3b |
| 编译器性能模型（perf CSV）：NE 按 2.508 GHz、PE 按 1.812 GHz；对激活 DMA 偏乐观；膨胀卷积按展开核计 | 【编译器】 | `data/05_compute/perfcsv/` | `tools/05_compute/perfcsv.py`、`tools/05_compute/perfcsv_lldb.txt` | | compute_array H53 |
| 卷积核形状：核宽 ≤ 8 原生（单 ANE 90–96%）；9–15 改写为步长 2，受读权重带宽限制；≥ 16 编译失败退回 CPU | 【计时】【HWX】【kdebug】 | `data/05_compute/ks4_*`、`data/05_compute/kshape*` | `tools/05_compute/ks4_*`、`tools/05_compute/kshape_fit.py` | ● | compute_array B4b / B4c、defects |
| 按深度的吞吐（对照 M4）；32 层"反常地慢"= 主机唤醒 + relu 放到 CPU | 【计时】【kdebug】 | `data/05_compute/b6_*`、`data/05_compute/chains_run*.txt` | `tools/05_compute/b6_ktrace.sh`、`tools/05_compute/b6_split.py`、`tools/common/runall.sh` | ● | compute_array B6 / B6b、defects B7 |
| space_to_depth：9.5 → 31.7 TFLOPS，没有 block = 2 陷阱 | 【计时】 | `data/05_compute/b8_s2d_run.txt` | `tools/05_compute/s2d.py` | | compute_array B8 |
| PE 逐元素：单个运算约 121.5 G 元素 / s，融合后每 ANE 约 61 G；与 MAC 串行 | 【kdebug】 | `data/05_compute/pe_kt/`、`data/05_compute/pe_kt_fit.txt`、`data/05_compute/pe_run.txt` | `tools/05_compute/pe.py`、`tools/05_compute/pe_ktrace.sh`、`tools/05_compute/pe_kt.py` | ● | compute_array（PE 节） |

## 06 数值

| 结论 | 证据 | 数据 | 工具 | root | 笔记 |
|---|---|---|---|---|---|
| FP16 累加器为 32 位定点 Q15.16：\|和\| ≥ 32768 → inf 并粘住；bias 为初值；M4 结果相同 | 【数值】 | `data/06_numerics/numerics*_m6.txt`、`data/06_numerics/numerics2_m4.txt` | `tools/06_numerics/numerics*.py`、`tools/common/anewho.c` | | numerics、H11 |
| 小于 1 LSB 的乘积（x、w 指数和 ≤ −17）整个丢掉 | 【数值】 | `data/06_numerics/numerics5_m6.txt`、`data/06_numerics/numerics6_m6.txt` | `tools/06_numerics/numerics5.py`、`tools/06_numerics/numerics6.py` | | numerics H12 |
| INT8 累加器为 32 位有符号整数，缩放在累加之后 | 【数值】 | `data/06_numerics/numerics_i8/` | `tools/06_numerics/numerics_i8.py` | | numerics H50 |
| 输出远离零舍入；NaN 当作普通大数；PE 走浮点 | 【数值】 | `data/06_numerics/numerics2_m6.txt`–`numerics4_m6.txt` | `tools/06_numerics/numerics2.py`–`numerics4.py` | | numerics F2 |
| 激活函数：33 点查找表（[−8, 8]，间距 0.5）+ 线性插值；可从编译产物直接读出 | 【数值】【HWX】 | `data/06_numerics/f3_lut_m6.txt`、`data/06_numerics/lut_m6/`、`data/06_numerics/opv_hwx/`；图 `figs/lut_error_*.png` | `tools/06_numerics/lut_err.py`、`tools/06_numerics/lut_plot.py`、`tools/06_numerics/opvariants.py` | | numerics F3 / F3b |

## 07 存储与搬运

| 结论 | 证据 | 数据 | 工具 | root | 笔记 |
|---|---|---|---|---|---|
| L2 每个 ANE 2 MiB（编译选项 `L2Size` 默认 2048 kB、TD 地址上限 2 MiB）；物理 SRAM 无直接读数 | 【编译器】【HWX】 | `data/07_memory/l2sz/`、`data/03_compile/l2hwx/` | `tools/07_memory/l2scan.py`、`tools/07_memory/l2res.py` | | memory C1d |
| L2 64 个 bank × 16 B（1 KiB 一周期）；编译器补 512 / 768 B 步长避冲突，关闭后冲突重现 | 【HAL】【计时】【HWX】 | `data/07_memory/l2bank_table.txt` | `tools/07_memory/l2bank.py` | | compute_array H53（L2 bank） |
| 片上中间张量每块 < 2 MiB，块数 = ⌊大小 / 2 MiB⌋ + 1；计时看不到拐点（层融合） | 【HWX】 | `data/03_compile/c1_hwx/`、`data/07_memory/c12_run.txt` | `tools/lib/td_widths.py` | | memory C1 / C1b |
| 读权重约 150–153 GB/s，与每层大小、核形状无关；"两种带宽"其实是主机 CPU 空闲深度造成的 | 【计时】【kdebug】 | `data/07_memory/bw_*`、`data/07_memory/sw_*`、`data/07_memory/switch_*`、`data/07_memory/h14_*` | `tools/07_memory/sw_ktrace.sh`、`tools/07_memory/sw_ktrace_sum.sh`、`tools/07_memory/ane_bw.py` | ● | memory C2–C2j |
| Tile DMA：每个 TD 最多读 2、写 1 个 DRAM 张量，两路输入共用，每个 ANE 约 35–40 GB/s（更正 C3 / C4） | 【kdebug】 | `data/07_memory/tdma_kt/`、`data/07_memory/tdma_run.txt`；旧 `c3c4_run.txt`、`c4_run.txt` | `tools/07_memory/tdma.py`、`tools/07_memory/tdma_ktrace.sh` | ● | memory C3b |
| DRAM：1 控制器 × 8 通道，16 GB，满载在最高档 F9 = 10656 MT/s，理论 170.5 GB/s；ANE 单独约 153、与 GPU 合计约 160–168 | 【ioreg】【IOReport】【计时】 | `data/07_memory/dramco/`、`data/07_memory/membw64_*.txt`、`data/07_memory/pmp_L*.txt` | `tools/07_memory/dramco.sh`、`tools/common/membw.swift`、`tools/07_memory/bwco_ktrace.sh` | ● | memory C2k |
| 系统级缓存（SLC / MCache 16 MiB）：权重不经过（编译选项已关闭预取） | 【编译器】【计时】 | `data/07_memory/slc_flush_run.txt` | `tools/common/bondrun.m`（`BONDRUN_GAP=flush`） | | memory C2i、C2 |

## 08 双引擎

| 结论 | 证据 | 数据 | 工具 | root | 笔记 |
|---|---|---|---|---|---|
| 切分条件：Σ单 > 0.5 × (Σ切块 + Σ拷贝)；按行或按输出通道切 | 【编译器】【HWX】 | `data/08_bonded/bsdecide.txt`、`data/08_bonded/bsplit_flags.txt` | `tools/08_bonded/bsdecide.py`、`tools/08_bonded/bs_split*.py` | | bonded_measure §2.1–2.2 |
| 扩展 1.92×；读权重受限时约 1.4×；按行切分的读权重受限层没有加速 | 【计时】 | `data/08_bonded/bond_*_run*.txt` | `tools/08_bonded/bond_sweep.py`、`tools/lib/bonded_cases.py` | | bonded_measure §3、defects B9 |
| 切块不均：奇数块时多出的一块给 ANE1，慢 12.5–19%；偶数块时均衡 | 【HWX】【kdebug】 | `data/08_bonded/asym_*`、`data/08_bonded/bsplit_even.txt` | `tools/08_bonded/asym_ktrace*.sh`、`tools/08_bonded/asym_split.py` | ● | memory C1c、defects B8 |
| 同步：跨 ANE 屏障 `f0003281`，个数等于数据交换次数；共享区经 SLC | 【HWX】 | `data/03_compile/hwx/` | `tools/lib/hwx_bonded.py` | | hwx_h18g §7 |

## 09 时钟域

| 结论 | 证据 | 数据 | 工具 | root | 笔记 |
|---|---|---|---|---|---|
| NE 32 档（设备树 `voltage-states8/29`），满载 2.58 GHz（固件时间戳在升频台阶上反推）；编译器表 2.508 GHz 只用于性能模型 | 【kdebug】【ioreg】【编译器】 | `data/09_clock/freq_kt/`、`data/09_clock/socfreq*.txt` | `tools/09_clock/freq_ktrace.sh`、`tools/09_clock/freq_fit.py`、`tools/re/socfreq.c` | ● | power §6、defects B6 |
| 各代 SoC 参数（NE / DRAM / DMA 频率表、通道数、MCache）；M6 用 `Soc2026BaseLine` | 【编译器】 | `data/09_clock/socfreq*.txt` | `tools/re/socfreq.c`、`tools/re/socfreq_map.c` | | power §6.2 |
| 编译器 NE → L2 频率映射：L2 = NE × 0.85 … 0.72 | 【编译器】 | `data/09_clock/socfreq_ne2l2.txt` | `tools/re/socfreq_map.c` | | compute_array（时钟节） |
| ANE 共享簇（PE / L2）单独调频：约 0.5 s 才开始升，GPU 忙时被压回慢档，慢档与满载相差 2.63 倍；不跟随 NE、也不跟随 SOC | 【kdebug】【IOReport】 | `data/09_clock/pefreq_kt*/`、`data/09_clock/socpe_kt/` | `tools/09_clock/pefreq_*`、`tools/09_clock/socpe_*`、`tools/common/socsamp.c` | ● | compute_array（PE 时钟）、defects B10 |
| 互连（fabric）5 档 534–1308 MHz = 编译器的"DMA 表"；CLPC 管理"ANE Shared Cluster" | 【内核】【编译器】 | — | `tools/re/kcdis.py`、`tools/re/strref.c` | | compute_array（时钟节） |

## 10 调频器 CLPC 与电源状态

| 结论 | 证据 | 数据 | 工具 | root | 笔记 |
|---|---|---|---|---|---|
| CLPC 按利用率调频，ANE 忙比例目标约 77%；下限 852 MHz；间隔 ≤ 100 µs 保持满频，≥ 400 µs 落到下限 | 【kdebug】【计时】 | `data/10_clpc/gov_kt/`、`data/10_clpc/gov/` | `tools/10_clpc/gov_ktrace.sh`、`tools/10_clpc/gov_fit.py`、`tools/10_clpc/gov_sweep.sh` | ● | scheduling H54 §5–6 |
| 阶跃响应：升满约 50 ms（到最高档 60–120 ms）；降到底约 135–170 ms；降到中间档 380–630 ms 并摆动；空闲约 100 ms 后落到 852 MHz | 【kdebug】 | `data/10_clpc/gov_step/` | `tools/10_clpc/gov_step.sh`、`tools/10_clpc/gov_step_fit.py` | ● | scheduling H54 §7 |
| 驱动向 CLPC 报告工作；节流由 CLPC 给百分比、驱动按占空比执行 | 【内核】 | M6：`~/anehal/kc/`（不入库） | `tools/re/kcdis.py` | | scheduling H54 §4 |
| 空闲 5.68 s 后两个 ANE 同时断电；10.2 s 维护计时器上电撤程序；约 15.3 s 再断电 | 【IOReport】【内核】 | `data/10_clpc/h16_*` | `tools/common/coldwake.m` | | power §3.1 |
| 冷唤醒：< 5.7 s 第一次调用约 6.8 ms；断电后约 50 ms | 【计时】 | `data/10_clpc/e2_coldwake*.txt` | `tools/common/coldwake.m` | | power §3 |
| 持续满载 5 分钟不降频，无降频事件 | 【计时】【IOReport】 | `data/10_clpc/e4_sustained_*.txt` | `tools/common/bondrun.m`、`tools/common/iorlist.c` | | power §4 |

## 11 功耗与能效

| 结论 | 证据 | 数据 | 工具 | root | 笔记 |
|---|---|---|---|---|---|
| SMC `PP0b` 同时供 ANE 和 P 核（1 个核空转即 7.5 W）；ANE 净功耗 = PP0b − P 核簇 + 1.15 W | 【SMC】【IOReport】 | `data/11_power/power_parts4/` | `tools/common/pclus.c`、`tools/common/smcpower.c` | | power §7.0 |
| 满载：单 ANE 6.2 W，双 ANE 10.8 W，两者共享约 1.6 W；空闲 0 W | 【SMC】【IOReport】 | `data/11_power/power_parts4/`（第 1–3 轮、`power_smc.txt` 未扣 P 核，大模型行仍可用） | `tools/11_power/power_parts.py`、`tools/11_power/power_parts_fit.py` | | power §7.0、§7.3 |
| FP16 0.6–0.8 pJ / 乘加；INT8 约其 55–60%；PE 50–60 pJ / 元素；读 DRAM ≤ 46 pJ / B（内存电源轨约 22 pJ / B） | 【SMC】 | `data/11_power/power_parts*/` | 同上 | | power §7.3、§7.6 |
| 低档（852 MHz）每次推理能耗约为满频的 1/3，延迟约 2.5–2.9 倍 | 【SMC】【kdebug】 | `data/11_power/power_parts2/`、`data/10_clpc/gov_kt/` | 同上 | | power §7.4 |
| 高频小调用的额外功耗主要来自主机 CPU（P 核簇 +6 W，约 1.6 mJ / 次）；ANE 自身每次约 0.15 mJ | 【SMC】【IOReport】 | `data/11_power/power_parts3/`、`data/11_power/power_parts4/` | 同上 | | power §7.5 |
| 输入全 0：PE 功耗低 17%，卷积反而高 7.5%（原因不明） | 【SMC】 | `data/11_power/power_parts2/` | 同上（`BONDRUN_FILL=zero`） | | power §7.3 |
| 编译器 perf CSV 的 `power(W)` 只算 DMA：50 pJ / B（DRAM）、10 pJ / B（≤ 16 MiB 缓存命中），HAL 0x890 | 【编译器】 | `data/05_compute/perfcsv/` | `tools/re/memdump.c`、`tools/re/syms.c` | | power §7.1、hal_analysis（0x890 更正） |
| powermetrics 在 M6 上估不出 ANE / CPU 功耗（已作废） | — | `data/_obsolete/power_out/` | `tools/11_power/power_suite.sh` | ● | power §5.1 |

## 13 缺陷（汇总见 `notes/defects.md`）

| 编号 | 内容 | 数据 |
|---|---|---|
| A1 | 双 ANE 编译路径 387 层起栈溢出崩溃 | `data/03_compile/h9_depth_compile.txt` |
| A2 | 编译服务崩溃后 Core ML 加载不确定，可能永久卡住 | `data/04_schedule/d5_depth_run.txt` |
| B1–B10 | 编译超线性、只在 E 核编译、同程序串行、W8A8 激活走 DRAM、主机唤醒、频率表偏低、relu 放到 CPU、切块不均、按行切分浪费、PE 时钟慢 | 见各章对应行 |

## 只在 M6 上、不入库的内容

| 位置 | 内容 | 原因 |
|---|---|---|
| `~/anehal/hwx/` 下的 `sweep/`、`chains/`、`q8/`、`pem/`、`tdma/`、`mac3/` 等 | 测试模型（`.mlpackage` / `.mlmodelc`）和编译产物，约 9.4 GB | 体积大；可用 `tools/common/chain.py` 等重新生成 |
| `~/anehal/fw/` | ANE / PMP 固件解包与反汇编 | 只读分析、不分发 |
| `~/anehal/kc/` | kernelcache 与字符串表 | 同上 |
| `~/anehal/allsyms.txt`、`funcs.*`、`pm/` | 编译器符号表与反汇编 | 苹果二进制的派生内容；可用 `tools/re/` 重新生成 |
| 本机 `private/`（不入库） | 编译器反汇编（`td31/36.*`、`tdver/`）、HAL 参数表原始导出与字段总表（`hal/`）、符号与方法名列表 | 同上 |
