"""d1b_ktrace.sh 的结果：每次调用拆成"提交 → 任务结束"和"任务结束 → 下次提交"（再细分），比较两组层数不同、任务时长重叠的模型。

用法：python3 d1b_stages.py <d1b_kt 目录>
  单 ANE 时固件不发任务开始事件（61b0125），所以"提交 → 任务结束"包含提交延迟 + 任务本身。
  任务结束之后的阶段同 memory.md C2j：结束(0126) → 固件消息(00b8) → 中断(0020) → 完成标记(00a0, arg1=1) → 驱动完成(0170) → 用户返回(0024) → 下次提交(01a9)。
  计算量：A = k1_c512（每层 2·512²·128 = 67.1 MFLOP），B = k1_c1024（每层 268.4 MFLOP）。
"""
import glob
import os
import re
import sys

import numpy as np

rows = []
for f in glob.glob(os.path.join(sys.argv[1], "k1_*.txt")):
    name = os.path.basename(f)[:-4]
    if name.endswith(".bondrun"):
        continue
    m = re.match(r"k1_c(\d+)_h1w(\d+)_L(\d+)(_spin)?$", name)
    C, W, L, spin = int(m.group(1)), int(m.group(2)), int(m.group(3)), bool(m.group(4))
    ev = []
    for l in open(f):
        p = l.split()
        if len(p) >= 4:
            ev.append((int(p[0]) / 24.0, p[1], p[2], p[3]))
    ev.sort()
    subs = [k for k, e in enumerate(ev) if e[1] == "61b01a9"]
    st = []
    for a, b in zip(subs[:-1], subs[1:]):
        seg = ev[a:b + 1]
        t0 = seg[0][0]
        ends = [t for t, i, _, _ in seg if i == "61b0126"]
        if len(ends) != 1:
            continue
        te = ends[0]

        def first(idd, t_from, cond=lambda x: True):
            for t, i, x, _ in seg:
                if i == idd and t >= t_from and cond(x):
                    return t
            return None
        t1 = first("61b00b8", te)
        t2 = first("61b0020", t1 or te)
        t3 = first("61b00a0", t2 or te, lambda x: x == "1")
        t4 = first("61b0170", t3 or te)
        t5 = first("61b0024", t4 or te)
        t6 = seg[-1][0]
        if None in (t1, t2, t3, t4, t5):
            continue
        st.append([t6 - t0, te - t0, t6 - te, t1 - te, t2 - t1, t3 - t2, t4 - t3, t5 - t4, t6 - t5])
    if not st:
        continue
    s = np.array(st)
    rows.append((C, L, spin, len(st), np.median(s, axis=0), np.percentile(s[:, 2], 10)))
gf = lambda C, L: 2 * C * C * 128 * L / 1e9
print(f"{'模型':>16} {'n':>5} {'GFLOP':>6} {'调用':>7} {'提交→结束':>9} {'结束→下次提交':>12} {'(p10)':>6} │ {'→消息':>6} {'→中断':>6} {'→完成':>6} {'驱动完成':>7} {'用户返回':>7} {'→提交':>6}")
for C, L, spin, n, m, p10 in sorted(rows, key=lambda r: (r[2], r[0], r[1])):
    tag = f"c{C} L{L}" + (" 空转" if spin else "")
    print(f"{tag:>16} {n:5d} {gf(C, L):6.2f} {m[0]:7.1f} {m[1]:9.1f} {m[2]:12.1f} {p10:6.1f} │ " + " ".join(f"{x:6.1f}" for x in m[3:6]) + f" {m[6]:7.1f} {m[7]:7.1f} {m[8]:6.1f}")
for C in (512, 1024):
    r = [x for x in rows if x[0] == C and not x[2]]
    g = np.array([gf(C, x[1]) for x in r]); y = np.array([x[4][1] for x in r]); Ls = np.array([x[1] for x in r])
    k, b = np.polyfit(g, y, 1)
    print(f"c{C}：提交→结束 = {b:.1f} µs + {k:.1f} µs/GFLOP（{1000 / k:.1f} TFLOPS）；残差 " + " ".join(f"L{L}:{v - (b + k * gg):+.1f}" for L, gg, v in zip(Ls, g, y)))
