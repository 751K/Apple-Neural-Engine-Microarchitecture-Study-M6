"""ks4_ktrace.sh 的结果：每个模型每次调用的 ANE 任务时长（固件时间戳）和所用引擎，按核形状求每层耗时与效率。

用法：python3 ks4_fit.py <ks4_kt 目录> [--points]
  每次调用 = 两次提交（61b01a9）之间的所有任务结束事件（61b0126）；耗时 = 最后一个任务结束 − 提交。
  单 ANE 时固件不发任务开始事件（61b0125），所以统一用"提交 → 最后一个任务结束"：含一段近似固定的提交延迟，
  不含任务结束后的主机唤醒开销（defects.md B5）；求斜率时固定延迟抵消。
  引擎：调用里任务结束事件的 cpu 列（ANE0 / ANE1）。一个模型的模式取多数调用的模式（"单0"、"单1"、"双"）。
  每层耗时：同一核形状、同一空间形状，只用模式相同的层数点做最小二乘直线拟合；不同模式分开拟合，各自至少 2 个点。
  效率：相对直接卷积峰值，单 ANE 21.1 TFLOPS，双 ANE 42.3 TFLOPS（256 MAC × 16 NE × 2 × 2.58 GHz）。
"""
import glob
import os
import re
import sys
from collections import defaultdict

import numpy as np

PAT = re.compile(r"k(\d+)x(\d+)_c(\d+)_h(\d+)w(\d+)_L(\d+)")
PEAK = {"单": 21.1, "双": 42.3}


def model_stats(path):
    ev = []
    for l in open(path):
        p = l.split()
        if len(p) >= 3:
            ev.append((int(p[0]) / 24.0, p[1], p[2]))
    ev.sort()
    subs = [t for t, i, _ in ev if i == "61b01a9"]
    ends = [(t, "ANE1" if "ANE1" in c else "ANE0") for t, i, c in ev if i == "61b0126"]
    if len(subs) < 5 or not ends:
        return None
    durs, modes = [], []
    j = 0
    for a, b in zip(subs[:-1], subs[1:]):
        while j < len(ends) and ends[j][0] < a:
            j += 1
        sel = []
        while j < len(ends) and ends[j][0] < b:
            sel.append(ends[j])
            j += 1
        if not sel:
            continue
        durs.append(max(x[0] for x in sel) - a)
        engs = {x[1] for x in sel}
        modes.append("双" if len(engs) == 2 else ("单0" if "ANE0" in engs else "单1"))
    if not durs:
        return None
    mode = max(set(modes), key=modes.count)
    d = np.array([x for x, m in zip(durs, modes) if m == mode])
    return mode, np.median(d), np.percentile(d, 10), modes.count(mode) / len(modes), len(durs)


pts = defaultdict(dict)  # (核, 空间) -> {L: (模式, 中位数, p10, 一致率, n)}
for f in glob.glob(os.path.join(sys.argv[1], "*.txt")):
    name = os.path.basename(f)[:-4]
    m = PAT.fullmatch(name)
    if not m:
        continue
    s = model_stats(f)
    if s is None:
        continue
    kh, kw, c, h, w, L = map(int, m.groups())
    pts[(kh, kw, c, h, w)][L] = s

if "--points" in sys.argv:
    for key in sorted(pts):
        kh, kw, c, h, w = key
        print(f"k{kh}x{kw} c{c} {h}×{w}: " + "  ".join(f"L{L} {s[0]} {s[1]:.1f}µs({100 * s[3]:.0f}%)" for L, s in sorted(pts[key].items())))
    print()

print(f"{'核':>6} {'空间':>6} {'模式':>3} {'层数点':>12} {'每层 µs':>8} {'截距 µs':>8} {'TFLOPS':>7} {'效率':>5} {'每行 µs':>7}")
for key in sorted(pts, key=lambda k: (k[3], k[4], k[0] > 1 and k[1] > 1, k[0], k[1])):
    kh, kw, c, h, w = key
    bymode = defaultdict(list)
    for L, s in pts[key].items():
        bymode[s[0][0]].append((L, s[1]))  # 单0 / 单1 合并为"单"
    for mode, xs in sorted(bymode.items()):
        if len(xs) < 2:
            continue
        xs.sort()
        Ls, ts = np.array([x[0] for x in xs]), np.array([x[1] for x in xs])
        k, b = np.polyfit(Ls, ts, 1)
        tf = 2 * c * c * kh * kw * h * w / k / 1e6
        print(f"{f'{kh}x{kw}':>6} {f'{h}x{w}':>6} {mode:>3} {','.join(map(str, Ls)):>12} {k:8.2f} {b:8.1f} {tf:7.2f} {100 * tf / PEAK[mode]:4.0f}% {k / h:7.3f}")
