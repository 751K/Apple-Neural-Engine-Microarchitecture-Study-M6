"""ks4_ktrace.sh 的结果：双 ANE 模型每次调用里两个 ANE 各自的忙碌时间、任务数和重叠程度。

用法：python3 ks4_engines.py <ks4_kt 目录> [名字过滤正则]
  双 ANE 时固件发任务开始 / 结束（61b0125 / 61b0126），按引擎配对。每次调用（两次提交之间）统计：
  ANE0 / ANE1 忙碌 µs（各自任务时长之和）、任务数、跨度（最早开始 → 最晚结束）、重叠 = (忙0 + 忙1 − 跨度) / min(忙0, 忙1)。
  重叠接近 1：两边并行；接近 0：两边串行（先后执行）。
"""
import glob
import os
import re
import sys
from collections import defaultdict

import numpy as np

flt = re.compile(sys.argv[2]) if len(sys.argv) > 2 else None
print(f"{'模型':28s} {'忙0 µs':>8} {'忙1 µs':>8} {'任务0':>5} {'任务1':>5} {'跨度 µs':>8} {'重叠':>5} {'ANE1 先开始':>10}")
for f in sorted(glob.glob(os.path.join(sys.argv[1], os.environ.get("KGLOB", "k*_L*.txt")))):
    name = os.path.basename(f)[:-4]
    if name.endswith(".bondrun") or (flt and not flt.search(name)):
        continue
    ev = []
    for l in open(f):
        p = l.split()
        if len(p) >= 3:
            ev.append((int(p[0]) / 24.0, p[1], "ANE1" if "ANE1" in p[2] else "ANE0"))
    ev.sort()
    if not any(i == "61b0125" for _, i, _ in ev):
        continue  # 单 ANE
    subs = [t for t, i, _ in ev if i == "61b01a9"]
    st = defaultdict(list)
    tasks = []
    for t, i, e in ev:
        if i == "61b0125":
            st[e].append(t)
        elif i == "61b0126" and st[e]:
            tasks.append((st[e].pop(0), t, e))
    tasks.sort()
    rows = []
    for a, b in zip(subs[:-1], subs[1:]):
        sel = [x for x in tasks if a <= x[0] < b]
        b0 = sum(x[1] - x[0] for x in sel if x[2] == "ANE0")
        b1 = sum(x[1] - x[0] for x in sel if x[2] == "ANE1")
        n0 = sum(x[2] == "ANE0" for x in sel)
        n1 = sum(x[2] == "ANE1" for x in sel)
        if not n0 or not n1:
            continue
        span = max(x[1] for x in sel) - min(x[0] for x in sel)
        ov = (b0 + b1 - span) / min(b0, b1)
        first1 = min(x[0] for x in sel if x[2] == "ANE1") < min(x[0] for x in sel if x[2] == "ANE0")
        rows.append((b0, b1, n0, n1, span, ov, first1))
    if not rows:
        continue
    r = np.array(rows, dtype=float)
    m = np.median(r, axis=0)
    print(f"{name:28s} {m[0]:8.1f} {m[1]:8.1f} {m[2]:5.0f} {m[3]:5.0f} {m[4]:8.1f} {m[5]:5.2f} {100 * r[:, 6].mean():9.0f}%")
