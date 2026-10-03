"""hi_ktrace.sh 的结果：每次调用的 ANE 忙碌时间（双 ANE 取两个引擎中较大者；单 ANE 为提交 → 最后一个 0126），
L4 → L12 斜率得每层耗时，再按 2.58 GHz、实际引擎数折算每 NE 每周期乘加。

用法：python3 hi_fit.py <hi_kt 目录>
"""
import glob
import os
import re
import statistics as S
import sys
from collections import defaultdict

PAT = re.compile(r"d(\d+)_k(\d+)_c(\d+)_h(\d+)w(\d+)_L(\d+)_(f16|q8)")
res = {}
for f in sorted(glob.glob(os.path.join(sys.argv[1], "d*_L*_*.txt"))):
    n = os.path.basename(f)[:-4]
    ev = sorted((int(p[0]) / 24.0, p[1], "ANE1" if "ANE1" in p[2] else "ANE0") for p in (l.split() for l in open(f)) if len(p) >= 3)
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
            if busy:
                rows.append(max(busy.values()))
        else:
            ends = [t for t, i, _ in seg if i == "61b0126"]
            if ends:
                rows.append(max(ends) - a)
    if len(rows) > 20:
        res[n] = (S.median(rows), dual)
for n, (t, d) in sorted(res.items()):
    print(f"{n:30s} {'双' if d else '单'} 每次调用 ANE 忙碌 {t:8.1f} µs")
print()
for base in sorted({re.sub(r"_L\d+_", "_L_", n) for n in res}):
    a, b = base.replace("_L_", "_L4_"), base.replace("_L_", "_L12_")
    if a not in res or b not in res:
        continue
    dd, k, C, H, W, _, m = PAT.fullmatch(b).groups()
    s = (res[b][0] - res[a][0]) / 8
    e = 2 if res[b][1] else 1
    mac = int(C) ** 2 * int(k) ** 2 * int(H) * int(W)
    print(f"{base:30s} {'双' if e == 2 else '单'}  每层 {s:7.2f} µs  每 NE 每周期乘加 {mac / s / 1e-6 / (e * 16 * 2.58e9):6.0f}")
