"""ANE 功耗分部件实验（E5），SMC 电源轨，不需要 root。

用法（M6）：cd ~/anehal/hwx && python3 power_parts.py power_parts > power_parts_run.txt
每种负载：
  1. 先用 300 次调用校准每次耗时（bondrun 中位数），按目标时长算调用次数；
  2. 正式运行（bondrun 自带约 1 s 预热）期间，smcpower trace 每 100 ms 记录一次各电源轨，
     负载结束后再记 TAIL 秒（ANE 已上电、没有任务；IOP 约 5.7 s 后断电）；
  3. 输出 <目录>/<标签>.trace（相对时间 s + 各键瓦数）、<标签>.bondrun.txt，以及时间标记 <标签>.marks（负载开始 / 结束的相对时间）。
SMC 读数约每 1 s 才刷新一次，所以取负载中段（开始后 3 s 到结束前 0.5 s）的平均。
电源轨：PP0b = ANE 加 P 核（2026-10-03 发现与 P 核共用，见 power.md §7.0；设 PP_PCLUS=1 同时记 P 核簇功耗）；PP2b、PP4b、PZD1 = 读 DRAM 时上涨的三路（推测内存控制器 / DRAM）；PSTR = 整机；PPSR、PHPC 参考。
"""
import os
import subprocess
import sys
import time

OUT = sys.argv[1] if len(sys.argv) > 1 else "power_parts"
TARGET_S = float(os.environ.get("PP_SECONDS", 12))
TAIL = float(os.environ.get("PP_TAIL", 8))
GAP = float(os.environ.get("PP_GAP", 0))      # 每段之间额外冷却的秒数（无风扇机器用）
KEYS = ["PP0b", "PP2b", "PP4b", "PZD1", "PSTR", "PPSR", "PHPC"]
os.makedirs(OUT, exist_ok=True)

# (标签, 模型, 额外环境变量)
W = [
    ("f16_single", "sweep/k1x1_512_h1w128_L384.mlmodelc", {}),
    ("f16_single_zero", "sweep/k1x1_512_h1w128_L384.mlmodelc", {"BONDRUN_FILL": "zero"}),
    ("f16_dual", "sweep/k1x1_512_h1w256_L384.mlmodelc", {}),
    ("q8_single", "q8/k1_c512_h1w128_L384_q8.mlmodelc", {}),
    ("f16_small", "sweep/k1x1_512_h1w128_L16.mlmodelc", {}),
    ("weightbw", "chains/k1_c512_h1w16_L192_u.mlmodelc", {}),
    ("pe_add", "pem/pe_add_c256_h64w64_L96.mlmodelc", {}),
    ("pe_add_zero", "pem/pe_add_c256_h64w64_L96.mlmodelc", {"BONDRUN_FILL": "zero"}),
    ("pe_mul", "pem/pe_mul_c256_h64w64_L64.mlmodelc", {}),
    ("tdma_add2", "tdma/add2_s256.mlmodelc", {}),
    ("f16_duty50", "sweep/k1x1_512_h1w128_L384.mlmodelc", {"BONDRUN_SLEEP_US": "1600"}),
    ("f16_duty20", "sweep/k1x1_512_h1w128_L384.mlmodelc", {"BONDRUN_SLEEP_US": "6400"}),
    ("f16_L48", "sweep/k1x1_512_h1w128_L48.mlmodelc", {}),
    ("f16_L128", "sweep/k1x1_512_h1w128_L128.mlmodelc", {}),
    ("f16_L256", "sweep/k1x1_512_h1w128_L256.mlmodelc", {}),
    ("f16_sl100", "sweep/k1x1_512_h1w128_L384.mlmodelc", {"BONDRUN_SLEEP_US": "100"}),
    ("f16_sl300", "sweep/k1x1_512_h1w128_L384.mlmodelc", {"BONDRUN_SLEEP_US": "300"}),
    ("f16_sl800", "sweep/k1x1_512_h1w128_L384.mlmodelc", {"BONDRUN_SLEEP_US": "800"}),
    ("f16_sl3200", "sweep/k1x1_512_h1w128_L384.mlmodelc", {"BONDRUN_SLEEP_US": "3200"}),
    # 13.3 节"全 0 输入功耗 +7.5%"的复核（2026-10-04）：上面 f16_single 的模型偏置为随机值、层间 ReLU，全 0 输入只让
    # 第 1 层为 0，之后每层是"每通道一个常数"。sparse/c1x1_fp16_L128（sparse_gen.py）偏置为 0，全 0 输入每层都是 0。
    ("f16_single_chconst", "sweep/k1x1_512_h1w128_L384.mlmodelc", {"BONDRUN_FILL": "chconst"}),
    ("b0_rand", "sparse/c1x1_fp16_L128.mlmodelc", {}),
    ("b0_zero", "sparse/c1x1_fp16_L128.mlmodelc", {"BONDRUN_FILL": "zero"}),
    ("b0_chconst", "sparse/c1x1_fp16_L128.mlmodelc", {"BONDRUN_FILL": "chconst"}),
    ("b0_negzero", "sparse/c1x1_fp16_L128.mlmodelc", {"BONDRUN_FILL": "negzero"}),
    # 零值省电是门控还是"不翻转"：每层输入 0 的比例 0 / 50 / 75 / 90%（随机位置）与一半通道整体为 0（sparse_gen.py 的掩码模型）
    ("z00", "sparse/c1x1_z00_L128.mlmodelc", {}),
    ("z50", "sparse/c1x1_z50_L128.mlmodelc", {}),
    ("z75", "sparse/c1x1_z75_L128.mlmodelc", {}),
    ("z90", "sparse/c1x1_z90_L128.mlmodelc", {}),
    ("zch", "sparse/c1x1_zch_L128.mlmodelc", {}),
    # 成对的 0：对齐与错开一位（2026-10-05）
    ("zpc", "sparse/c1x1_zpc_L128.mlmodelc", {}),
    ("zpco", "sparse/c1x1_zpco_L128.mlmodelc", {}),
    ("zpw", "sparse/c1x1_zpw_L128.mlmodelc", {}),
    ("zpwo", "sparse/c1x1_zpwo_L128.mlmodelc", {}),
]
# PP_ONLY=标签1,标签2,...：按给定顺序运行（可重复；重复的标签输出名加 _r2、_r3…）
only = os.environ.get("PP_ONLY")
if only:
    by, seen, sel = {w[0]: w for w in W}, {}, []
    for t in only.split(","):
        seen[t] = seen.get(t, 0) + 1
        sel.append((t if seen[t] == 1 else f"{t}_r{seen[t]}",) + by[t][1:])
    W = sel


def median_us(text):
    for line in text.splitlines():
        if "中位数" in line:
            return float(line.split("中位数")[1].split()[0])
    return None


time.sleep(6)  # 让 ANE 先断电
for tag, model, extra in W:
    env = dict(os.environ, **extra)
    cal = subprocess.run(["./bondrun", model, "300"], env=env, capture_output=True, text=True).stdout
    us = median_us(cal)
    if not us:
        print(f"== {tag}：校准失败\n{cal}")
        continue
    per = us + float(extra.get("BONDRUN_SLEEP_US", 0))
    iters = max(300, int(TARGET_S * 1e6 / per))
    time.sleep(7 + GAP)  # 校准后让 ANE 断电，正式运行从冷态开始
    # PP_PCLUS=1：改用 pclus（每 1 s 同时记 P 核簇功耗和 SMC 键；第 2 列为 P 核簇瓦数）
    # 记录时长放宽到预计的 2 倍（正式运行可能比校准慢，如无风扇机器降频），负载结束后录满 TAIL 秒再停止
    dur = str(2 * TARGET_S + TAIL + 30)
    cmd = (["./pclus", dur, "1000", *KEYS] if os.environ.get("PP_PCLUS")
           else ["./smcpower", "trace", dur, "100", *KEYS])
    tr = subprocess.Popen(cmd,
                          stdout=open(f"{OUT}/{tag}.trace", "w"))
    t0 = time.monotonic()
    time.sleep(1.0)
    ts = time.monotonic() - t0
    br = subprocess.run(["./bondrun", model, str(iters)], env=env, capture_output=True, text=True)
    te = time.monotonic() - t0
    open(f"{OUT}/{tag}.bondrun.txt", "w").write(br.stdout + br.stderr)
    open(f"{OUT}/{tag}.marks", "w").write(f"{ts:.3f} {te:.3f} {iters} {us:.1f}\n")
    time.sleep(TAIL + 2)
    tr.terminate()                     # pclus / smcpower 每行 fflush，停止不丢数据
    tr.wait()
    print(f"== {tag} {model} {extra} 次数 {iters} 校准 {us:.1f} us 开始 {ts:.2f} s 结束 {te:.2f} s")
    print(br.stdout.strip())
    sys.stdout.flush()
