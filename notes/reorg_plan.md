# data/ 按章节重组的移动清单（已于 2026-10-03 执行，提交见 git log）

各目录数量：02_overview 1，03_compile 25，04_schedule 14，05_compute 38，06_numerics 10，07_memory 36，08_bonded 11，09_clock 9，10_clpc 12，11_power 5，_obsolete 2

| 原路径 | 新路径 | 备注 |
|---|---|---|
| data/align_hwx.txt | data/07_memory/align_hwx.txt |  |
| data/align_timing.txt | data/07_memory/align_timing.txt |  |
| data/asym_kt | data/08_bonded/asym_kt |  |
| data/asym_kt2 | data/08_bonded/asym_kt2 |  |
| data/asym_timing.txt | data/08_bonded/asym_timing.txt |  |
| data/b2b_run.txt | data/05_compute/b2b_run.txt |  |
| data/b6_kt | data/05_compute/b6_kt |  |
| data/b6_pcpu.txt | data/05_compute/b6_pcpu.txt |  |
| data/b6_q8_run.txt | data/05_compute/b6_q8_run.txt |  |
| data/b6_sample_top.txt | data/05_compute/b6_sample_top.txt |  |
| data/b6_w8_recheck.txt | data/05_compute/b6_w8_recheck.txt |  |
| data/b6x_hwx.txt | data/05_compute/b6x_hwx.txt |  |
| data/b6x_sweep.txt | data/05_compute/b6x_sweep.txt |  |
| data/b8_s2d_run.txt | data/05_compute/b8_s2d_run.txt |  |
| data/bond_calib_run.txt | data/08_bonded/bond_calib_run.txt |  |
| data/bond_dsweep_run.txt | data/08_bonded/bond_dsweep_run.txt |  |
| data/bond_ksweep_run.txt | data/08_bonded/bond_ksweep_run.txt |  |
| data/bond_sweep_run1.txt | data/08_bonded/bond_sweep_run1.txt |  |
| data/bond_wsweep_run.txt | data/08_bonded/bond_wsweep_run.txt |  |
| data/bsdecide.txt | data/08_bonded/bsdecide.txt |  |
| data/bsplit_even.txt | data/08_bonded/bsplit_even.txt |  |
| data/bsplit_flags.txt | data/08_bonded/bsplit_flags.txt |  |
| data/bw_48_60_run.txt | data/07_memory/bw_48_60_run.txt |  |
| data/bw_blocksize_run.txt | data/07_memory/bw_blocksize_run.txt |  |
| data/bw_kshape_run.txt | data/07_memory/bw_kshape_run.txt |  |
| data/bw_kshape_run2.txt | data/07_memory/bw_kshape_run2.txt |  |
| data/bw_mlp_run.txt | data/07_memory/bw_mlp_run.txt |  |
| data/bwco_kt | data/07_memory/bwco_kt |  |
| data/c12_run.txt | data/07_memory/c12_run.txt |  |
| data/c1_hwx | data/03_compile/c1_hwx |  |
| data/c2b_run.txt | data/07_memory/c2b_run.txt |  |
| data/c2c_run.txt | data/07_memory/c2c_run.txt |  |
| data/c3c4_run.txt | data/07_memory/c3c4_run.txt | C3/C4 含主机开销，结论已由 C3b 更正（数据本身保留） |
| data/c4_run.txt | data/07_memory/c4_run.txt | 同上 |
| data/chains_run1.txt | data/05_compute/chains_run1.txt |  |
| data/chains_run2.txt | data/05_compute/chains_run2.txt |  |
| data/cm_load_vs_compile.txt | data/03_compile/cm_load_vs_compile.txt |  |
| data/compiler_enums_m6.txt | data/03_compile/compiler_enums_m6.txt |  |
| data/compiler_layers_neurons_m6.txt | data/03_compile/compiler_layers_neurons_m6.txt |  |
| data/convcfg_scan.txt | data/03_compile/convcfg_scan.txt |  |
| data/d1_out | data/04_schedule/d1_out |  |
| data/d1b_kt | data/04_schedule/d1b_kt |  |
| data/d1b_stages.txt | data/04_schedule/d1b_stages.txt |  |
| data/d1b_warm.txt | data/04_schedule/d1b_warm.txt |  |
| data/d2_concurrency.txt | data/04_schedule/d2_concurrency.txt |  |
| data/d3_overlap_run.txt | data/04_schedule/d3_overlap_run.txt |  |
| data/d3_overlap_run2.txt | data/04_schedule/d3_overlap_run2.txt |  |
| data/d5_depth_m4.txt | data/04_schedule/d5_depth_m4.txt |  |
| data/d5_depth_run.txt | data/04_schedule/d5_depth_run.txt |  |
| data/d5d6_run2.txt | data/04_schedule/d5d6_run2.txt |  |
| data/d6_tiny.txt | data/04_schedule/d6_tiny.txt |  |
| data/dramco | data/07_memory/dramco |  |
| data/e2_coldwake.txt | data/10_clpc/e2_coldwake.txt |  |
| data/e2_coldwake_states.txt | data/10_clpc/e2_coldwake_states.txt |  |
| data/e4_sustained_ioreport.txt | data/10_clpc/e4_sustained_ioreport.txt |  |
| data/e4_sustained_series.txt | data/10_clpc/e4_sustained_series.txt |  |
| data/effA_kt | data/05_compute/effA_kt |  |
| data/effA_pcpu.txt | data/05_compute/effA_pcpu.txt |  |
| data/effA_sample.txt | data/05_compute/effA_sample.txt |  |
| data/effA_spinner.txt | data/05_compute/effA_spinner.txt |  |
| data/f3_lut_m6.txt | data/06_numerics/f3_lut_m6.txt |  |
| data/freq_kt | data/09_clock/freq_kt |  |
| data/gov | data/10_clpc/gov |  |
| data/gov_kt | data/10_clpc/gov_kt |  |
| data/gov_step | data/10_clpc/gov_step |  |
| data/group1_run.txt | data/04_schedule/group1_run.txt |  |
| data/h10_dilation.txt | data/05_compute/h10_dilation.txt |  |
| data/h10_w8a8_k3.txt | data/05_compute/h10_w8a8_k3.txt |  |
| data/h10_w8a8_slope.txt | data/05_compute/h10_w8a8_slope.txt |  |
| data/h14_rerun.txt | data/07_memory/h14_rerun.txt |  |
| data/h14_segments.txt | data/07_memory/h14_segments.txt |  |
| data/h15_mt.txt | data/04_schedule/h15_mt.txt |  |
| data/h15_mt2.txt | data/04_schedule/h15_mt2.txt |  |
| data/h16_idle_sweep.txt | data/10_clpc/h16_idle_sweep.txt |  |
| data/h16_iop_trace.txt | data/10_clpc/h16_iop_trace.txt |  |
| data/h16_iop_trace40.txt | data/10_clpc/h16_iop_trace40.txt |  |
| data/h16_log.txt | data/10_clpc/h16_log.txt |  |
| data/h16_stream_raw.txt | data/10_clpc/h16_stream_raw.txt |  |
| data/h7_compile_time.txt | data/03_compile/h7_compile_time.txt |  |
| data/h8 | data/03_compile/h8 |  |
| data/h9_depth_compile.txt | data/03_compile/h9_depth_compile.txt |  |
| data/hal | data/03_compile/hal |  |
| data/hi2_kt | data/05_compute/hi2_kt |  |
| data/hi_kt | data/05_compute/hi_kt |  |
| data/hwx | data/03_compile/hwx |  |
| data/hwx_cases | data/03_compile/hwx_cases |  |
| data/ior104.txt | data/07_memory/ior104.txt |  |
| data/ior96.txt | data/07_memory/ior96.txt |  |
| data/ks4_engines.txt | data/05_compute/ks4_engines.txt |  |
| data/ks4_fit.txt | data/05_compute/ks4_fit.txt |  |
| data/ks4_hwx | data/05_compute/ks4_hwx |  |
| data/ks4_kt | data/05_compute/ks4_kt |  |
| data/ks4_list.txt | data/05_compute/ks4_list.txt |  |
| data/ks4_warm.txt | data/05_compute/ks4_warm.txt |  |
| data/ks4b_warm.txt | data/05_compute/ks4b_warm.txt |  |
| data/kshape2_run.txt | data/05_compute/kshape2_run.txt |  |
| data/kshape_run.txt | data/05_compute/kshape_run.txt |  |
| data/kshape_td.txt | data/05_compute/kshape_td.txt |  |
| data/l2bank_table.txt | data/07_memory/l2bank_table.txt |  |
| data/l2hwx | data/03_compile/l2hwx |  |
| data/l2sz | data/07_memory/l2sz |  |
| data/lut_m6 | data/06_numerics/lut_m6 |  |
| data/m6_ioreg_ane_20261002.md | data/02_overview/m6_ioreg_ane_20261002.md |  |
| data/mac3_run.txt | data/05_compute/mac3_run.txt |  |
| data/macw_td.txt | data/05_compute/macw_td.txt |  |
| data/membw64_alone.txt | data/07_memory/membw64_alone.txt |  |
| data/membw64_co.txt | data/07_memory/membw64_co.txt |  |
| data/numerics2_m4.txt | data/06_numerics/numerics2_m4.txt |  |
| data/numerics2_m6.txt | data/06_numerics/numerics2_m6.txt |  |
| data/numerics3_m6.txt | data/06_numerics/numerics3_m6.txt |  |
| data/numerics4_m6.txt | data/06_numerics/numerics4_m6.txt |  |
| data/numerics5_m6.txt | data/06_numerics/numerics5_m6.txt |  |
| data/numerics6_m6.txt | data/06_numerics/numerics6_m6.txt |  |
| data/numerics_i8 | data/06_numerics/numerics_i8 |  |
| data/ocg_table.txt | data/05_compute/ocg_table.txt |  |
| data/opv_hwx | data/06_numerics/opv_hwx |  |
| data/ox_tddump.txt | data/03_compile/ox_tddump.txt |  |
| data/pe_kt | data/05_compute/pe_kt |  |
| data/pe_kt_fit.txt | data/05_compute/pe_kt_fit.txt |  |
| data/pe_run.txt | data/05_compute/pe_run.txt |  |
| data/pefreq_kt | data/09_clock/pefreq_kt |  |
| data/pefreq_kt2 | data/09_clock/pefreq_kt2 |  |
| data/pefreq_kt3 | data/09_clock/pefreq_kt3 |  |
| data/pefreq_kt3_v1 | data/_obsolete/pefreq_kt3_v1 | PE 频率第 3 轮第一版，被重跑取代 |
| data/perfcsv | data/05_compute/perfcsv |  |
| data/pmp_L100.txt | data/07_memory/pmp_L100.txt |  |
| data/pmp_L96.txt | data/07_memory/pmp_L96.txt |  |
| data/power_out | data/_obsolete/power_out | powermetrics 在 M6 上估不出 ANE 功耗，已作废（power.md §5.1） |
| data/power_parts | data/11_power/power_parts | 第 1 轮：PP0b 未扣除 P 核，大模型行仍可用（power.md §7.0） |
| data/power_parts2 | data/11_power/power_parts2 | 第 2 轮：同上 |
| data/power_parts3 | data/11_power/power_parts3 | 第 3 轮：同上；小模型行无效 |
| data/power_parts4 | data/11_power/power_parts4 |  |
| data/power_smc.txt | data/11_power/power_smc.txt | E3：PP0b 未扣除 P 核，小模型一行无效 |
| data/slc_flush_run.txt | data/07_memory/slc_flush_run.txt |  |
| data/socfreq.txt | data/09_clock/socfreq.txt |  |
| data/socfreq_2026baseline.txt | data/09_clock/socfreq_2026baseline.txt |  |
| data/socfreq_mem.txt | data/09_clock/socfreq_mem.txt |  |
| data/socfreq_ne2l2.txt | data/09_clock/socfreq_ne2l2.txt |  |
| data/socpe_kt | data/09_clock/socpe_kt |  |
| data/sw_L100.txt | data/07_memory/sw_L100.txt |  |
| data/sw_L96.txt | data/07_memory/sw_L96.txt |  |
| data/sw_cpufreq.txt | data/07_memory/sw_cpufreq.txt |  |
| data/sw_duration.txt | data/07_memory/sw_duration.txt |  |
| data/sw_ktrace_sum.txt | data/07_memory/sw_ktrace_sum.txt |  |
| data/sw_spinner.txt | data/07_memory/sw_spinner.txt |  |
| data/sw_workstats.txt | data/07_memory/sw_workstats.txt |  |
| data/switch_coldwake.txt | data/07_memory/switch_coldwake.txt |  |
| data/switch_scope_run.txt | data/07_memory/switch_scope_run.txt |  |
| data/td31.dis | data/03_compile/td31.dis |  |
| data/td31.s | data/03_compile/td31.s |  |
| data/td31_setters_0x240.txt | data/03_compile/td31_setters_0x240.txt |  |
| data/td36.dis | data/03_compile/td36.dis |  |
| data/td36.s | data/03_compile/td36.s |  |
| data/td_1x8_full.txt | data/03_compile/td_1x8_full.txt |  |
| data/td_field_offsets.txt | data/03_compile/td_field_offsets.txt |  |
| data/td_hw_syms.txt | data/03_compile/td_hw_syms.txt |  |
| data/td_reg_methods.txt | data/03_compile/td_reg_methods.txt |  |
| data/tdma_kt | data/07_memory/tdma_kt |  |
| data/tdma_run.txt | data/07_memory/tdma_run.txt |  |
| data/tdv | data/03_compile/tdv |  |
| data/tdver | data/03_compile/tdver |  |
| data/val_run.txt | data/05_compute/val_run.txt |  |
| data/xword_samples.txt | data/03_compile/xword_samples.txt |  |

## tools/ 的重组（2026-10-03 执行）

- 分为 `common/`（运行器、采样器、模型生成与清单）、`lib/`（公共 Python 模块）、`re/`（只读逆向工具）和 `03_compile/` … `11_power/`（各章实验的采集与分析脚本），与 `data/` 的章节目录对应。
- 有本地 import 的 27 个 Python 脚本在开头加了路径查找（本目录 → `../lib` → `../common`），所以在仓库里分目录和在 M6 上平铺两种布局都能运行；原有的 `sys.path.insert` 保留。
- M6 上仍平铺在 `~/anehal/hwx/`。同步一律用 `tools/deploy_m6.sh`：先按 shasum 比对，只用 scp 传有变化的文件，不删除任何东西；`-n` 为预演。
  - macOS 自带的 openrsync 在这种用法下只列清单、不实际传输，所以没用 rsync。
  - zsh 里 `"$M6:anehal"` 的 `:a` 会被当成路径修饰符，必须写成 `"${M6}:anehal"`。
- 验证：77 个 .py 语法检查通过；两种布局下所有本地 import 都能找到；M6 平铺目录 import `td_widths / tdwalk / tdpkt / hwx_bonded` 正常；本机分目录下 `lib/tdpkt.py` 处理编译产物正常。`chain.py`、`bonded_cases.py` 需要装有 torch 的 Python 环境，与路径无关。
- notes、大纲中的 `tools/xxx` 引用已改为新路径（12 个文件）。
