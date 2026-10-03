"""gov_target.sh 的结果：各模型、各睡眠时间 G 下的稳态档位，以及按三种口径算的 ANE 忙碌比例。

用法：python3 gov_target_fit.py <gov_tg 目录> [每段丢弃的前 N 秒 = 4]
trace.txt 每行：mach 时间（24 MHz tick） debug-id。相邻任务相隔 > 2 s 视为新的一段，按顺序对应 marks.txt。
口径：
  固件  61b0125 → 61b0126（固件记录的任务开始、结束）
  驱动  61b01a9（驱动收到提交）→ 任务结束后第一个 61b00a0（驱动收到完成）
  调用  61b0071（调用线程提交）→ 同上
忙碌比例 = 各任务区间之和 / 该段时长。档位：f = 2580 MHz × (d0 − D) / (d − D)，d0 为该模型 G = 0 时的任务时长中位数
（连续调用时三个模型都跑在 2580 MHz），D ≈ 8 µs，取设备树 32 档中最接近者。
"""
import os
import sys

import numpy as np

DT = [804, 828, 852, 960, 996, 1032, 1092, 1128, 1188, 1248, 1308, 1368, 1404, 1476, 1548, 1632,
      1716, 1788, 1872, 1908, 1968, 2052, 2112, 2196, 2280, 2352, 2364, 2436, 2448, 2484, 2508, 2580]
D = 8.0
d = sys.argv[1]
SKIP = float(sys.argv[2]) if len(sys.argv) > 2 else 4.0

marks = [l.split() for l in open(os.path.join(d, "marks.txt")) if l.strip()]
ev = {}
for l in open(os.path.join(d, "trace.txt")):
    p = l.split()
    if len(p) == 2:
        ev.setdefault(p[1], []).append(int(p[0]) / 24.0)
ev = {k: np.array(v) for k, v in ev.items()}

st, en = [], []
cur = None
for t, i in sorted([(t, "s") for t in ev["61b0125"]] + [(t, "e") for t in ev["61b0126"]]):
    if i == "s":
        cur = t
    elif cur is not None:
        st.append(cur); en.append(t); cur = None
st, en = np.array(st), np.array(en)
cuts = [0] + [k for k in range(1, len(st)) if st[k] - en[k - 1] > 2e6] + [len(st)]
print(f"任务 {len(st)}，{len(cuts) - 1} 段，marks {len(marks)} 行")


def last_before(ids, t):
    v = ev[ids]
    k = np.searchsorted(v, t) - 1
    return np.where(k >= 0, v[np.clip(k, 0, len(v) - 1)], np.nan)


def first_after(ids, t):
    v = ev[ids]
    k = np.searchsorted(v, t, side="right")
    return np.where(k < len(v), v[np.clip(k, 0, len(v) - 1)], np.nan)


d0 = {}
print(f"{'模型':>24} {'G µs':>6} {'任务':>5} {'任务中位 µs':>11} {'周期中位 µs':>11} {'档位中位':>8} "
      f"{'档位分布(前 3)':>28} {'固件':>6} {'驱动':>6} {'调用':>6} {'驱动多出 µs':>10} {'调用多出 µs':>10}")
for r in range(len(cuts) - 1):
    a, b = cuts[r], cuts[r + 1]
    s, e = st[a:b], en[a:b]
    keep = s >= s[0] + SKIP * 1e6
    if keep.sum() < 20 or r >= len(marks):
        continue
    s, e = s[keep], e[keep]
    model, G = os.path.basename(marks[r][0]).replace(".mlmodelc", ""), int(marks[r][1])
    dur = e - s
    if G == 0:
        d0[model] = np.median(dur)
    span = e[-1] - s[0]
    drv0 = last_before("61b01a9", s)          # 驱动收到提交
    call0 = last_before("61b0071", s)         # 调用线程提交
    done = first_after("61b00a0", e)          # 驱动收到完成
    ok = (s - drv0 < 1000) & (s - call0 < 1000) & (done - e < 1000)
    busy_fw = dur.sum() / span
    busy_drv = (done - drv0)[ok].sum() / span * len(s) / ok.sum()
    busy_call = (done - call0)[ok].sum() / span * len(s) / ok.sum()
    extra_drv = np.median((done - drv0 - dur)[ok])
    extra_call = np.median((done - call0 - dur)[ok])
    per = np.median(np.diff(s))
    if model in d0:
        f = 2580 * (d0[model] - D) / (dur - D)
        lv = np.array([min(DT, key=lambda x: abs(x - v)) for v in f])
        vals, cnt = np.unique(lv, return_counts=True)
        top = sorted(zip(cnt, vals), reverse=True)[:3]
        lvs = " ".join(f"{v}:{c * 100 // len(lv)}%" for c, v in top)
        lvm = f"{np.median(lv):.0f}"
    else:
        lvs, lvm = "?", "?"
    print(f"{model:>24} {G:6d} {len(s):5d} {np.median(dur):11.1f} {per:11.1f} {lvm:>8} {lvs:>28} "
          f"{busy_fw:6.1%} {busy_drv:6.1%} {busy_call:6.1%} {extra_drv:10.1f} {extra_call:10.1f}")
