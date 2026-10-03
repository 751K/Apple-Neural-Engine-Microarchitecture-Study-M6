"""pe_ktrace.sh 的结果：每次调用的 ANE 忙碌时间（中位数），以及 L16 → L64 的每层斜率和 PE 吞吐。

用法：python3 pe_kt.py <pe_kt 目录>
双 ANE（有 61b0125）：每个引擎任务时长之和，取两个引擎中较大者；单 ANE：提交（01a9）→ 最后一个 0126。
sc 模型 16 个单输入运算编成 8 个任务（相邻两个合并），add 模型每层一个任务；斜率按"任务数"归一。
"""
import glob
import os
import re
import statistics as S
import sys
from collections import defaultdict

res = {}
for f in sorted(glob.glob(os.path.join(sys.argv[1], "pe_*.txt"))):
    n = os.path.basename(f)[:-4]
    if n.endswith(".bondrun"):
        continue
    ev = sorted((int(p[0]) / 24.0, p[1], "ANE1" if "ANE1" in p[2] else "ANE0") for p in (l.split() for l in open(f)) if len(p) >= 3)
    if not ev:
        continue
    subs = [t for t, i, _ in ev if i == "61b01a9"]
    dual = any(i == "61b0125" for _, i, _ in ev)
    rows = []
    for a, b in zip(subs[:-1], subs[1:]):
        seg = [x for x in ev if a <= x[0] < b]
        if dual:
            st, busy = defaultdict(list), defaultdict(float)
            for t, i, e in seg:
                if i == "61b0125":
                    st[e].append(t)
                elif i == "61b0126" and st[e]:
                    busy[e] += t - st[e].pop(0)
            if len(busy) == 2:
                rows.append(max(busy.values()))
        else:
            ends = [t for t, i, _ in seg if i == "61b0126"]
            if ends:
                rows.append(max(ends) - a)
    if len(rows) > 20:
        res[n] = (S.median(rows), dual)
for n, (t, d) in res.items():
    print(f"{n:26s} {'双' if d else '单'}  每次调用 ANE 忙碌 {t:8.1f} µs")
print()
pat = re.compile(r"pe_(\w+)_c(\d+)_h(\d+)w(\d+)_L(\d+)")
slopes = defaultdict(list)  # (op, Ls) -> [(每引擎元素数, 每层 µs)]
groups = defaultdict(dict)
for k, v in res.items():
    op, C, H, W, L = pat.fullmatch(k).groups()
    groups[(op, C, H, W)][int(L)] = v
for (op, C, H, W), d in sorted(groups.items(), key=lambda x: (x[0][0], int(x[0][1]), int(x[0][2]))):
    for lo, hi in ((16, 64), (32, 96)):
        if lo not in d or hi not in d or d[lo][1] != d[hi][1]:
            continue
        # 每层：add 每层一个任务；sc 每两层（两个单输入运算）一个任务，这里按"每个运算"计
        s_ = (d[hi][0] - d[lo][0]) / (hi - lo)
        e = int(C) * int(H) * int(W) / (2 if d[hi][1] else 1)
        slopes[(op, f"L{lo}/L{hi}")].append((e, s_))
        print(f"{op:4s} c{C} {H}×{W}  L{lo}→L{hi}  {'双' if d[hi][1] else '单'}  每个运算 {s_:6.2f} µs  每引擎 {e:7.0f} 元素")
print()
import numpy as np
for (op, ls), pts in sorted(slopes.items()):
    if len(pts) < 3:
        continue
    x = np.array([p[0] for p in pts]); y = np.array([p[1] for p in pts])
    A = np.vstack([x, np.ones_like(x)]).T
    (k, b), res_, _, _ = np.linalg.lstsq(A, y, rcond=None)
    n = len(x); r = y - (k * x + b)
    se_k = np.sqrt((r @ r) / (n - 2) / ((x - x.mean()) @ (x - x.mean())))
    rate = 1 / k  # 元素 / µs
    lo_, hi_ = 1 / (k + 2 * se_k), (1 / (k - 2 * se_k) if k > 2 * se_k else float("inf"))
    print(f"{op:4s} {ls}  {n} 点  固定 {b:5.2f} µs / 运算  斜率 {k * 1e3:6.3f} ns / 千元素 → 每引擎 {rate / 1e3:6.1f} G元素/s = {rate * 1e6 / 2.58e9:6.1f} 元素/周期"
          f"（±2σ：{lo_ * 1e6 / 2.58e9:5.1f}–{hi_ * 1e6 / 2.58e9:5.1f}）  残差 {np.abs(r).max():.2f} µs")
