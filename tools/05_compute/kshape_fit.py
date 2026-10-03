"""kshape_run.txt 的分析：每种卷积核 / 空间形状的每层耗时（L4→L12 斜率）、有效吞吐、相对直接卷积峰值的效率。

用法：python3 kshape_fit.py <kshape_run.txt>（自动取文件中最小、最大两个层数求斜率）
行格式：<轮> <模型名> <中位数 µs> <p10 µs> [ANE1 中断/调用]
直接卷积峰值：单引擎 21.1 TFLOPS（256 MAC × 16 NE × 2 × 2.58 GHz），双引擎 42.3。
"""
import re
import sys
from collections import defaultdict

import numpy as np

PAT = re.compile(r"k(\d+)x(\d+)_c(\d+)_h(\d+)w(\d+)_L(\d+)")
t = defaultdict(list)
dual = {}
for line in open(sys.argv[1]):
    p = line.split()
    if len(p) < 4 or not PAT.fullmatch(p[1]):
        continue
    t[p[1]].append(float(p[3]))  # p10
    if len(p) >= 5:
        dual[p[1]] = float(p[4]) > 0.5
rows = []
Ls = sorted({int(n.rsplit("_L", 1)[1]) for n in t})
lo, hi = Ls[0], Ls[-1]
for name in sorted({re.sub(r"_L\d+$", "", n) for n in t}):
    a, b = f"{name}_L{lo}", f"{name}_L{hi}"
    if a not in t or b not in t:
        continue
    kh, kw, c, h, w, _ = map(int, PAT.fullmatch(a).groups())
    slope = (np.median(t[b]) - np.median(t[a])) / (hi - lo)
    flop = 2 * c * c * kh * kw * h * w
    tf = flop / slope / 1e6
    peak = 42.3 if dual.get(b) else 21.1
    rows.append((name, kh, kw, h, w, slope, tf, tf / peak, dual.get(b)))
print(f"{'模型':26s} {'每层 µs':>8} {'TFLOPS':>7} {'效率':>6}  引擎  {'每输出行 µs':>10} {'每像素 ns':>9}")
for name, kh, kw, h, w, s, tf, eff, du in rows:
    print(f"{name:26s} {s:8.2f} {tf:7.2f} {100 * eff:5.0f}%  {'双' if du else '单'}   {s / h:10.3f} {1000 * s / (h * w):9.2f}")
