"""hi2_ktrace.sh 的结果：两个进程并发时每个 ANE 上的任务时长分布，以及 L4 → L12 的单 ANE 每层耗时与每 NE 每周期乘加。

用法：python3 hi2_fit.py <hi2_kt 目录>
任务按 ANE 分别以 0125 → 0126 先进先出配对；取各 ANE 任务时长的中位数（并发时每个任务应是完整的单 ANE 程序）。
同时统计两个 ANE 的任务在时间上重叠的比例：bonded 程序两边同时开始、同时结束；单 ANE 程序两边各跑各的。
"""
import glob
import os
import re
import statistics as S
import sys
from collections import defaultdict

PAT = re.compile(r"d(\d+)_k(\d+)_c(\d+)_h(\d+)w(\d+)_L(\d+)_(f16|q8)")
med = {}
for f in sorted(glob.glob(os.path.join(sys.argv[1], "d*_L*_*.txt"))):
    n = os.path.basename(f)[:-4]
    st, tasks = defaultdict(list), defaultdict(list)
    for l in open(f):
        p = l.split()
        if len(p) < 3:
            continue
        t, i, e = int(p[0]) / 24.0, p[1], ("ANE1" if "ANE1" in p[2] else "ANE0")
        if i == "61b0125":
            st[e].append(t)
        elif i == "61b0126" and st[e]:
            a = st[e].pop(0)
            tasks[e].append((a, t))
    if not tasks:
        continue
    starts1 = sorted(a for a, _ in tasks.get("ANE1", []))
    sync = 0
    for a, _ in tasks.get("ANE0", []):
        j = min(range(len(starts1)), key=lambda k: abs(starts1[k] - a)) if starts1 else None
        if j is not None and abs(starts1[j] - a) < 5:
            sync += 1
    d0 = [b - a for a, b in tasks.get("ANE0", [])]
    d1 = [b - a for a, b in tasks.get("ANE1", [])]
    allm = S.median(d0 + d1)
    med[n] = allm
    print(f"{n:28s} ANE0 任务 {len(d0):5d} 中位 {S.median(d0) if d0 else 0:7.1f} µs | ANE1 任务 {len(d1):5d} 中位 {S.median(d1) if d1 else 0:7.1f} µs"
          f" | 两边同时开始 {100 * sync / max(1, len(d0)):4.0f}%")
print()
for base in sorted({re.sub(r"_L\d+_", "_L_", n) for n in med}):
    a, b = base.replace("_L_", "_L4_"), base.replace("_L_", "_L12_")
    if a in med and b in med:
        dd, k, C, H, W, _, m = PAT.fullmatch(b).groups()
        s = (med[b] - med[a]) / 8
        mac = int(C) ** 2 * int(k) ** 2 * int(H) * int(W)
        print(f"{base:28s} 单 ANE 每层 {s:7.2f} µs  每 NE 每周期乘加 {mac / s / 1e-6 / (16 * 2.58e9):6.0f}")
