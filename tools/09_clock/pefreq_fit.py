"""pefreq_ktrace.sh 的结果：卷积 / PE 两种任务在升频过程中的台阶，并检验 PE 跑在 NE 时钟还是 L2 时钟。

用法：python3 pefreq_fit.py <pefreq_kt 目录>
trace.txt 每行：mach 时间（24 MHz） debug-id cpu（33 = ANE1，36 = ANE0）；order.txt 每行：轮次 模型。
每个 ANE 的任务按 0125 → 0126 配对；相邻任务开始相隔 > 1 s 视为新的一段，段的顺序与 order.txt 对应。
"""
import os
import sys
from collections import Counter, defaultdict

import numpy as np

d = sys.argv[1]
order = [l.split()[1] for l in open(os.path.join(d, "order.txt")) if l.strip()]
st, tasks = {}, []
for l in open(os.path.join(d, "trace.txt")):
    t, i, c = l.split()
    e = "ANE1" if "ANE1" in c else "ANE0"
    t = int(t) / 24.0
    if i == "61b0125":
        st[e] = t
    elif e in st:
        tasks.append((st.pop(e), t - st.get(e, 0) if False else t, e))
tasks = [(a, b - a, e) for a, b, e in sorted(tasks)]
segs, cur = [], []
for x in tasks:
    if cur and x[0] - cur[-1][0] > 1e6:
        segs.append(cur); cur = []
    cur.append(x)
segs.append(cur)
print(f"段数 {len(segs)}，order {len(order)} 条")
plate = defaultdict(list)
for k, sg in enumerate(segs):
    m = "PE" if "pe_" in order[k] else "卷积"
    du = [x[1] for x in sg if x[2] == "ANE0"]
    print(f"第 {k + 1} 段 {m}：ANE0 任务 {len(du)}，前 40 个：{' '.join(f'{v:.0f}' for v in du[:40])}  末 50 中位数 {np.median(du[-50:]):.1f}")
    plate[m] += du
for m, du in plate.items():
    lo = np.round(np.log(np.array(du)) / 0.004).astype(int)
    cnt = Counter(lo)
    pk = sorted(((np.exp(b * 0.004), n) for b, n in cnt.items() if n >= 6), reverse=True)
    print(m, "台阶（时长 µs，次数）：", " ".join(f"{v:.0f}×{n}" for v, n in pk))

# ---- 拟合：PE 台阶按"NE 档位"与"L2 档位"两种假设 ----
DT = [804, 828, 852, 960, 996, 1032, 1092, 1128, 1188, 1248, 1308, 1368, 1404, 1476, 1548, 1632,
      1716, 1788, 1872, 1908, 1968, 2052, 2112, 2196, 2280, 2352, 2364, 2436, 2448, 2484, 2508, 2580]
L2 = [684, 696, 720, 804, 828, 852, 900, 924, 972, 1008, 1056, 1104, 1128, 1188, 1236, 1296, 1356, 1404, 1452,
      1476, 1512, 1548, 1584, 1620, 1644, 1668, 1680, 1716, 1728, 1764, 1788, 1812]  # 编译器 NE→L2 映射的值域
du = np.array(plate["PE"])
lo = np.round(np.log(du) / 0.004).astype(int)
cnt = Counter(lo)
pk = sorted((np.exp(b * 0.004) for b, n in cnt.items() if n >= 9), reverse=True)
# 合并相邻箱（相差 < 1%）
steps = []
for v in pk:
    if steps and steps[-1][-1] / v < 1.01:
        steps[-1].append(v)
    else:
        steps.append([v])
steps = [float(np.mean(s)) for s in steps]
full = min(steps)
low = [s for s in steps if s > full * 1.03]
print("\nPE 台阶（合并后）：", " ".join(f"{s:.0f}" for s in steps), f"；满载 {full:.1f}")


def fit(table, name):
    best = None
    for D in np.arange(0, 20.1, 0.5):
        # 以最长台阶对应表中第 3 档（852 MHz 或其 L2 值），扫 C 让其余台阶最近邻匹配
        for f0 in table[:6]:
            C = (max(steps) - D) * f0
            err = []
            for s in low:
                f = C / (s - D)
                g = min(table, key=lambda x: abs(np.log(x / f)))
                err.append(np.log(g / f))
            r = float(np.sqrt(np.mean(np.square(err))))
            if best is None or r < best[0]:
                best = (r, D, f0, C)
    r, D, f0, C = best
    print(f"{name}：最优 RMS {100 * r:.2f}%  D = {D:.1f} µs  最长台阶对应 {f0} MHz  → 满载台阶对应 {C / (full - D):.0f} MHz")
    return best


fit(DT, "假设 A：PE 用 NE 时钟（设备树 32 档）")
fit(L2, "假设 B：PE 用 L2 时钟（编译器映射）")
