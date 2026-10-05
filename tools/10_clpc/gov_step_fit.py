"""gov_step.sh 的结果（H54 §7）：CLPC 阶跃响应。

用法：python3 gov_step_fit.py <目录>
tasks.txt：tick id（61b0125 开始、61b0126 结束）；phases_<A|B|C>.txt：切换时刻 tick、新间隔 us。
每个任务按 C / f + D 换算成设备树档位（同 gov_fit.py）。对每次切换，给出切换后各时刻（ms）的档位轨迹，
以及：升档——到达稳态档位（该段末 30% 任务的中位档）所需时间；降档——同上。C 组：每次长空闲后第一个任务的档位与恢复满频的时间。
"""
import os
import sys

import numpy as np

DT = [804, 828, 852, 960, 996, 1032, 1092, 1128, 1188, 1248, 1308, 1368, 1404, 1476, 1548, 1632,
      1716, 1788, 1872, 1908, 1968, 2052, 2112, 2196, 2280, 2352, 2364, 2436, 2448, 2484, 2508, 2580]
C, D = 1267.5 - 8.0, 8.0
d = sys.argv[1]


def mhz(dur):
    f = C * 2580 / (dur - D)
    return min(DT, key=lambda x: abs(x - f))


st, en = [], []
cur = None
for l in open(os.path.join(d, "tasks.txt")):
    t, i = l.split()
    t = int(t)
    if i == "61b0125":
        cur = t
    elif i == "61b0126" and cur is not None:
        st.append(cur); en.append(t); cur = None
st, en = np.array(st, dtype=float), np.array(en, dtype=float)
lv = np.array([mhz((e - s) / 24.0) for s, e in zip(st, en)])


# 若没有 phases 文件（gov_step.sh 首次运行时输出目录属 root，bondrun 写不进去），按调用次数反推切换时刻：
# 每次调用恰好对应一个任务；相隔 > 2 s 分为 A、B、C 三次运行，每次运行的任务数 = 预热次数 + gov_step.sh 中
# BONDRUN_SLEEP_SEQ 的总次数，因此预热次数 = 任务数 − 总次数，此后按序列中的次数逐段切分。
# （早先按"任务间隙 − 384 µs"逐个分类的做法在 G = 0 段会因主机空闲波动而把升频段切碎，已弃用。）
SEQ = {"A": [(1000, 270), (0, 900)] * 6, "B": [(200, 440), (0, 900)] * 5,
       "C": [(0, 300), (20000, 1), (0, 300), (50000, 1), (0, 300), (100000, 1), (0, 300), (200000, 1), (0, 300), (500000, 1)]}


def infer_phases():
    gaps = np.r_[np.inf, (st[1:] - en[:-1]) / 24.0]
    runs = [k for k in range(len(st)) if gaps[k] > 2e6] + [len(st)]
    res = {}
    for name, (a, b) in zip("ABC", zip(runs[:-1], runs[1:])):
        k = b - sum(n for _, n in SEQ[name])          # 预热结束处
        ph = [(int(st[a]), 0)]
        for g, n in SEQ[name]:
            if k < b:
                ph.append((int(st[k]), g))
            k += n
        res[name] = ph
    return res


INF = None


def load_phases(name):
    global INF
    f = os.path.join(d, f"phases_{name}.txt")
    if os.path.exists(f):
        return [tuple(map(int, l.split())) for l in open(f)]
    if INF is None:
        INF = infer_phases()
    return INF[name]


def traj(t0, t1):
    k = (st >= t0) & (st < t1)
    return (st[k] - t0) / 24e3, lv[k]  # ms, MHz


for name in "AB":
    ph = load_phases(name)
    print(f"== {name} 组")
    for j in range(1, len(ph)):
        t0, g = ph[j]
        t1 = ph[j + 1][0] if j + 1 < len(ph) else st[st >= t0][-1] + 1
        ms, f = traj(t0, t1)
        if len(f) < 10:
            continue
        ss = int(np.median(f[int(len(f) * 0.7):]))

        def first(cond, n=3):
            return next((ms[k] for k in range(len(f) - n) if all(cond(x) for x in f[k:k + n])), float("nan"))
        if g == 0:   # 升频：到达 ≥ 2448 MHz 与 2580 MHz（连续 3 个任务）
            gp = np.median((st[(st >= t0) & (st < t1)][1:] - en[(st >= t0) & (st < t1)][:-1]) / 24.0)
            extra = f"到达 ≥2448 {first(lambda x: x >= 2448):6.1f} ms，2580 {first(lambda x: x >= 2580):6.1f} ms，主机空闲中位数 {gp:.0f} us"
        else:        # 降频：在 ≥ 2448 MHz 保持的时间，降到 852 MHz 的时间
            extra = f"保持 ≥2448 {first(lambda x: x < 2448):6.1f} ms，降到 852 {first(lambda x: x <= 852):6.1f} ms"
        marks = [0, 5, 10, 20, 30, 50, 75, 100, 150, 200, 300, 500, 800, 1200]
        pts = []
        for m in marks:
            k = np.searchsorted(ms, m)
            if k < len(f):
                pts.append(f"{m}:{f[k]}")
        print(f"  → 间隔 {g:4d} us：起点 {f[0]} MHz，稳态 {ss} MHz，{extra}；轨迹(ms:MHz) {' '.join(pts)}")

ph = load_phases("C")
print("== C 组（长空闲后恢复）")
for j in range(len(ph) - 1):
    t0, g = ph[j]
    if g < 10000:
        continue
    t1 = ph[j + 2][0] if j + 2 < len(ph) else st.max() + 1
    ms, f = traj(t0, t1)
    if len(f) == 0:
        continue
    full = next((ms[k] - ms[0] for k in range(len(f) - 3) if all(x >= 2448 for x in f[k:k + 3])), float("nan"))
    print(f"  空闲 {g / 1000:5.0f} ms（设定值；实测间隙约多 10 ms）后：第 1 个任务 {f[0]} MHz，前 8 个 {' '.join(map(str, f[:8]))}，回到 ≥2448 MHz 用时 {full:6.1f} ms")
