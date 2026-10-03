"""pefreq_ktrace3.sh 的结果：卷积 / PE L32 / PE L96 交错执行，逐档比较 PE 的 L96 − L32 之差与 NE、L2 频率的关系。

用法：python3 pefreq_fit3.py <pefreq_kt3 目录>
1. 每个 ANE 的任务按 0125 → 0126 配对；按时长分类：卷积 ≥ 1250 µs，L96 450–1250，L32 150–450（只用 ANE0）。
2. 卷积任务时长 → NE 频率：T = C / f + D，C、D 由最长台阶（852 MHz）与满载台阶（2580 MHz）两点确定，再取设备树最近档。
3. 每个 PE 任务取时间上最近（≤ 3 ms）的卷积任务的档位；每档取 L96、L32 的中位数，Δ = L96 − L32（64 个 PE 运算，不含固定部分）。
4. 若 PE 用 NE 时钟，Δ × f_NE 为常数；若用 L2 时钟，Δ × f_L2(f_NE) 为常数（编译器 GetMapNEToL2Frequencies）。
"""
import bisect
import os
import sys
from collections import defaultdict

import numpy as np

DT = [804, 828, 852, 960, 996, 1032, 1092, 1128, 1188, 1248, 1308, 1368, 1404, 1476, 1548, 1632,
      1716, 1788, 1872, 1908, 1968, 2052, 2112, 2196, 2280, 2352, 2364, 2436, 2448, 2484, 2508, 2580]
NE2L2 = dict(zip([804, 828, 852, 960, 996, 1032, 1092, 1128, 1188, 1248, 1308, 1368, 1404, 1476, 1548, 1632, 1716, 1788,
                  1872, 1908, 1968, 2052, 2112, 2196, 2244, 2280, 2316, 2364, 2400, 2448, 2484, 2508],
                 [684, 696, 720, 804, 828, 852, 900, 924, 972, 1008, 1056, 1104, 1128, 1188, 1236, 1296, 1356, 1404,
                  1452, 1476, 1512, 1548, 1584, 1620, 1644, 1668, 1680, 1716, 1728, 1764, 1788, 1812]))

st, tasks = defaultdict(list), []
for l in open(os.path.join(sys.argv[1], "trace.txt")):
    t, i, c = l.split()
    e = "ANE1" if "ANE1" in c else "ANE0"
    t = int(t) / 24.0
    if i == "61b0125":
        st[e].append(t)
    elif st[e]:  # 多个进程同时提交时同一引擎上有排队的任务：按先进先出配对
        a = st[e].pop(0)
        tasks.append((a, t - a, e))
tasks = [x for x in sorted(tasks) if x[2] == "ANE0"]
conv = [(a, d) for a, d, _ in tasks if d >= 1250]
p96 = [(a, d) for a, d, _ in tasks if 450 <= d < 1250]
p32 = [(a, d) for a, d, _ in tasks if 150 <= d < 450]
print(f"ANE0 任务：卷积 {len(conv)}，L96 {len(p96)}，L32 {len(p32)}")
cd = np.array([d for _, d in conv])
Tlow, Tfull = np.median(cd[cd > 3700]), np.median(cd[(cd > 1255) & (cd < 1280)])
C = (Tlow - Tfull) / (1 / 852 - 1 / 2580)
D = Tfull - C / 2580
print(f"卷积：最长台阶 {Tlow:.1f} µs，满载 {Tfull:.1f} µs → C = {C:.0f} MHz·µs，D = {D:.1f} µs")
ct = [a for a, _ in conv]
lev = []
for a, d in conv:
    f = C / (d - D)
    g = min(DT, key=lambda x: abs(x - f))
    lev.append(g if abs(f / g - 1) < 0.006 else None)  # 偏离档位 > 0.6% 的（可能跨档或受干扰）不用


def level_at(t):
    k = bisect.bisect_left(ct, t)
    best = None
    for j in (k - 1, k):
        if 0 <= j < len(ct) and abs(ct[j] - t) < 3000:
            if best is None or abs(ct[j] - t) < abs(ct[best] - t):
                best = j
    return lev[best] if best is not None else None


by = defaultdict(lambda: ([], []))
for a, d in p96:
    g = level_at(a)
    if g:
        by[g][0].append(d)
for a, d in p32:
    g = level_at(a)
    if g:
        by[g][1].append(d)
print(f"\n{'NE 档':>6} {'L2':>6} {'n96':>4} {'n32':>4} {'L96 µs':>8} {'L32 µs':>8} {'Δ µs':>7} {'Δ×f_NE':>9} {'Δ×f_L2':>9}")
rows = []
for g in sorted(by):
    a, b = by[g]
    if len(a) < 3 or len(b) < 3:
        continue
    dlt = np.median(a) - np.median(b)
    l2 = NE2L2.get(g)
    rows.append((g, l2, dlt))
    print(f"{g:6d} {l2 if l2 else '-':>6} {len(a):4d} {len(b):4d} {np.median(a):8.1f} {np.median(b):8.1f} {dlt:7.1f} {dlt * g / 1e3:9.1f} {dlt * l2 / 1e3 if l2 else float('nan'):9.1f}")
ne = np.array([r[2] * r[0] for r in rows if r[1]])
l2 = np.array([r[2] * r[1] for r in rows if r[1]])
print(f"\n只用编译器映射里有的档（{len(ne)} 档）：Δ×f_NE 变异系数 {100 * ne.std() / ne.mean():.2f}%（{ne.min() / 1e3:.1f}–{ne.max() / 1e3:.1f}），"
      f"Δ×f_L2 变异系数 {100 * l2.std() / l2.mean():.2f}%（{l2.min() / 1e3:.1f}–{l2.max() / 1e3:.1f}）")
full = [r for r in rows if r[0] == 2580]
if full and len(l2):
    print(f"满载档（2580）Δ = {full[0][2]:.1f} µs → 若 Δ×f_L2 守恒，满载 L2 = {np.median(l2) / full[0][2]:.0f} MHz")
