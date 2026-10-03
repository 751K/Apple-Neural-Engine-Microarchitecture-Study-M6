"""asym_ktrace.sh 的结果：每次调用中 ANE0、ANE1 各自的任务时长和起止时刻差（中位数，µs）。

用法：python3 asym_split.py <asym_kt 目录>
事件：61b01a9 = 提交；61b0125 / 61b0126 = 任务开始 / 结束，cpu 列 "36(ANE0)" 或 "33(ANE1)"。
"""
import glob
import os
import sys

import numpy as np

d = sys.argv[1]
print(f"{'模型':>22} {'调用':>8} {'ANE0 任务':>10} {'ANE1 任务':>10} {'ANE1/ANE0':>10} {'开始差(1-0)':>12} {'结束差(1-0)':>12}   n")
def key(p):
    n = os.path.basename(p)[:-4]
    w, _, l = n.rpartition("_L") if n.startswith("k1_") else n.partition("_L")
    return (w, int(l) if l.isdigit() else 40)


for f in sorted(glob.glob(os.path.join(d, "*.txt")), key=key):
    name = os.path.basename(f)[:-4]
    if name.endswith(".bondrun") or not (name.split("_L")[0].isdigit() or name.startswith("k1_")):
        continue
    ev = []
    for l in open(f):
        p = l.split()
        if len(p) >= 3:
            ev.append((int(p[0]) / 24.0, p[1], "ANE1" if "ANE1" in p[2] else ("ANE0" if "ANE0" in p[2] else p[2])))
    ev.sort()
    subs = [k for k, e in enumerate(ev) if e[1] == "61b01a9"]
    rows = []
    for a, b in zip(subs[:-1], subs[1:]):
        seg = ev[a:b]
        st = {e: [t for t, i, c in seg if i == "61b0125" and c == e] for e in ("ANE0", "ANE1")}
        en = {e: [t for t, i, c in seg if i == "61b0126" and c == e] for e in ("ANE0", "ANE1")}
        if all(st[e] and en[e] for e in ("ANE0", "ANE1")):
            d0 = en["ANE0"][-1] - st["ANE0"][0]
            d1 = en["ANE1"][-1] - st["ANE1"][0]
            rows.append((d0, d1, st["ANE1"][0] - st["ANE0"][0], en["ANE1"][-1] - en["ANE0"][-1], ev[b][0] - ev[a][0]))
    if not rows:
        print(f"{name:>22} 没有成对的任务事件")
        continue
    r = np.median(np.array(rows), axis=0)
    print(f"{name if '_L' in name else name + '_L40':>22} {r[4]:8.1f} {r[0]:10.1f} {r[1]:10.1f} {r[1] / r[0]:10.2f} {r[2]:12.1f} {r[3]:12.1f}   {len(rows)}")
