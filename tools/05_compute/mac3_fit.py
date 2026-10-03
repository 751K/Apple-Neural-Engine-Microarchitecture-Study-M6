"""mac3_run.txt 的分析：每种形状 FP16 / W8A8 的每层耗时（L4→L16 斜率，p10 取两轮中位数）、有效吞吐、每引擎每 NE 每周期乘加数。

用法：python3 mac3_fit.py <mac3_run.txt>
行格式（runall.sh）：名字 中位数 p10 ANE0中断/调用 ANE1中断/调用 计算时钟开启
每 NE 每周期乘加 = 乘加/层 ÷ 斜率 ÷ (引擎数 × 16 NE × 2.58 GHz)。
"""
import re
import sys
from collections import defaultdict

import numpy as np

PAT = re.compile(r"d(\d+)_k(\d+)_c(\d+)_h(\d+)w(\d+)_L(\d+)_(f16|q8)")
t, eng = defaultdict(list), {}
for line in open(sys.argv[1]):
    p = line.split()
    if len(p) >= 5 and PAT.fullmatch(p[0]):
        t[p[0]].append(float(p[2]))
        eng[p[0]] = 2 if float(p[4]) > 0.5 else 1
print(f"{'形状':24s} {'精度':4s} 引擎 {'每层 µs':>8} {'T 乘加/s':>9} {'乘加/NE/周期':>12}   q8÷f16")
for d, k, c, h, w in sorted({PAT.fullmatch(n).groups()[:5] for n in t}):
    base = f"d{d}_k{k}_c{c}_h{h}w{w}"
    mac = int(c) ** 2 * int(k) ** 2 * int(h) * int(w)
    r = {}
    for mode in ("f16", "q8"):
        a, b = f"{base}_L4_{mode}", f"{base}_L16_{mode}"
        if a not in t or b not in t:
            continue
        s = (np.median(t[b]) - np.median(t[a])) / 12
        e = eng[b]
        r[mode] = s
        print(f"{base:24s} {mode:4s} {'双' if e == 2 else '单':2s}  {s:8.2f} {mac / s / 1e6:9.2f} {mac / s / 1e-6 / (e * 16 * 2.58e9):12.0f}"
              + (f"   {r['f16'] / s:5.2f}" if mode == "q8" and "f16" in r else ""))
