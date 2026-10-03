"""freq_ktrace.sh 的结果分析：每个 ANE 任务的时长 → 台阶 → 与频率表匹配。

用法：python3 freq_fit.py <trace.txt>
trace.txt 每行：mach 绝对时间（24 MHz tick） debug-id（61b0125 开始 / 61b0126 结束）
"""
import sys
from collections import Counter

import numpy as np

# 编译器 Soc2026BaseLine 的 NE 频率表（MHz，32 档）与设备树 voltage-states8（32 档）
DT = [804, 828, 852, 960, 996, 1032, 1092, 1128, 1188, 1248, 1308, 1368, 1404, 1476, 1548, 1632,
      1716, 1788, 1872, 1908, 1968, 2052, 2112, 2196, 2280, 2352, 2364, 2436, 2448, 2484, 2508, 2580]

ev = [l.split() for l in open(sys.argv[1]) if l.strip()]
t0 = None
durs, starts = [], []
for t, i in ev:
    t = int(t)
    if i == "61b0125":
        t0 = t
    elif i == "61b0126" and t0 is not None:
        durs.append((t - t0) / 24.0)
        starts.append(t0 / 24.0)
        t0 = None
d = np.array(durs)
s = np.array(starts)
print(f"任务数 {len(d)}，时长 中位数 {np.median(d):.1f} us，最小 {d.min():.1f}，最大 {d.max():.1f}")

# 按轮次切分（相邻任务开始时间相差 > 1 s 视为新的一轮）
cuts = [0] + [k for k in range(1, len(s)) if s[k] - s[k - 1] > 1e6] + [len(s)]
for r in range(len(cuts) - 1):
    seg = d[cuts[r]:cuts[r + 1]]
    print(f"第 {r + 1} 轮 {len(seg)} 个任务：前 12 个 {' '.join(f'{x:.0f}' for x in seg[:12])} … 末 5 个中位数 {np.median(seg[-5:]):.1f}")

# 台阶：时长按 0.2% 宽的箱聚类，取出现 ≥ 3 次的峰
lo = np.log(d)
bins = np.round(lo / 0.002).astype(int)
cnt = Counter(bins)
peaks = []
for b, c in sorted(cnt.items()):
    if c >= 3 and c >= cnt.get(b - 1, 0) and c >= cnt.get(b + 1, 0):
        sel = d[np.abs(bins - b) <= 1]
        peaks.append((np.median(sel), len(sel)))
peaks.sort()
print("\n台阶（时长 us，次数）：")
for p, c in peaks:
    print(f"  {p:9.2f}  {c:5d}")

# 用最短台阶当最高频，比值 → 频率；与表比较
if peaks:
    dmin = peaks[0][0]
    for top in (2508, 2580):
        print(f"\n假设最短台阶 = {top} MHz：")
        for p, c in peaks:
            f = top * dmin / p
            j = int(np.argmin([abs(f - x) for x in DT]))
            print(f"  {p:9.2f} us → {f:7.1f} MHz，最近的表项 {DT[j]}（偏差 {100 * (f - DT[j]) / DT[j]:+.2f}%），次数 {c}")

# ---- 模型 d = C/f + D：对两张表、各种 D 做最优拟合（只用出现 ≥ 20 次的台阶，最短台阶必须是 1 档）
COMP = [804, 828, 852, 960, 996, 1032, 1092, 1128, 1188, 1248, 1308, 1368, 1404, 1476, 1548, 1632,
        1716, 1788, 1872, 1908, 1968, 2052, 2112, 2196, 2244, 2280, 2316, 2364, 2400, 2448, 2484, 2508]
major = np.array([p for p, c in peaks if c >= 20])
print(f"\n用于拟合的台阶（≥ 20 次）：{' '.join(f'{x:.1f}' for x in major)}")
for name, table in (("设备树表", DT), ("编译器表", COMP)):
    tab = np.array(table, float)
    best = None
    for top in tab[-6:]:                     # 最短台阶对应的档位
        for D in np.arange(-60, 60.01, 0.5):     # 不随频率变化的固定时长（us）
            C = (major[0] - D) * top
            f = C / (major - D)
            j = np.abs(f[:, None] - tab[None, :]).argmin(1)
            res = (f - tab[j]) / tab[j]
            rms = float(np.sqrt(np.mean(res ** 2)))
            if best is None or rms < best[0]:
                best = (rms, top, D, C, j, res)
    rms, top, D, C, j, res = best
    print(f"\n{name}：最优 最短台阶 = {top:.0f} MHz，D = {D:+.1f} us，RMS 偏差 {100 * rms:.2f}%")
    for x, jj, r in zip(major, j, res):
        print(f"  {x:9.2f} us → {tab[jj]:.0f} MHz（{100 * r:+.2f}%）")
    for top2 in (2508, 2580):
        if top2 in table:
            for D in (0.0,):
                C = (major[0] - D) * top2
                f = C / (major - D)
                jj = np.abs(f[:, None] - tab[None, :]).argmin(1)
                r = (f - tab[jj]) / tab[jj]
                print(f"  （对照：最短台阶 = {top2}，D = 0 时 RMS {100 * np.sqrt(np.mean(r ** 2)):.2f}%）")
