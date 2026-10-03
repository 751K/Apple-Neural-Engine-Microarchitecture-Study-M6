"""gov_target2.sh / gov_target3.sh 的结果：每个模型、每个睡眠时间 G 下 ANE0 的稳态任务时长、空闲间隙和忙碌比例。

用法：python3 gov_target2_fit.py <gov_tg2 目录> [每段丢弃的前 N 秒 = 4]
trace.txt 每行：mach 时间（24 MHz tick） debug-id cpu 列（如 36(ANE0)）。固件任务按引擎配对开始 / 结束。
相邻任务相隔 > 2 s 视为新的一段，按顺序对应 marks.txt。
列：
  d0     该模型 G = 0 时的任务时长中位数（满频或接近满频）
  s      任务时长 / d0。只算 NE 的模型（S、B 组）s = 2580 / f；读 DRAM 的模型（M 组）任务不完全随频率变长，
         2580 / s 只是频率的上限，但纯计算部分不长于任务，频率也有下限，见报告。
  间隙   相邻两个任务之间 ANE0 的空闲中位数（含主机开销）
  x      间隙 / d0
  固件   ANE0 忙碌比例（任务时间之和 / 段长）
  驱动   61b01a9（驱动收到提交）→ 任务结束后第一个 61b00a0（驱动收到完成），按 ANE0 的任务算
  剔停顿 把该段切成 0.5 s 的窗口，任务数不到窗口中位数一半的窗口（主机调用线程停住了）不计，
         其余窗口内的固件忙碌比例；停顿 = 被剔除的窗口数 / 总窗口数
"""
import os
import sys

import numpy as np

DT = [804, 828, 852, 960, 996, 1032, 1092, 1128, 1188, 1248, 1308, 1368, 1404, 1476, 1548, 1632,
      1716, 1788, 1872, 1908, 1968, 2052, 2112, 2196, 2280, 2352, 2364, 2436, 2448, 2484, 2508, 2580]
d = sys.argv[1]
SKIP = float(sys.argv[2]) if len(sys.argv) > 2 else 4.0

marks = [l.split() for l in open(os.path.join(d, "marks.txt")) if l.strip()]
ev, fw = {}, {}
for l in open(os.path.join(d, "trace.txt")):
    p = l.split()
    if len(p) < 2:
        continue
    t = int(p[0]) / 24.0
    if p[1] in ("61b0125", "61b0126"):
        eng = "ANE1" if len(p) > 2 and "ANE1" in p[2] else "ANE0"
        fw.setdefault(eng, []).append((t, p[1]))
    else:
        ev.setdefault(p[1], []).append(t)
ev = {k: np.array(sorted(v)) for k, v in ev.items()}


def pairs(lst):
    st, en, cur = [], [], None
    for t, i in sorted(lst):
        if i == "61b0125":
            cur = t
        elif cur is not None:
            st.append(cur); en.append(t); cur = None
    return np.array(st), np.array(en)


st, en = pairs(fw["ANE0"])
st1, en1 = pairs(fw.get("ANE1", []))
cuts = [0] + [k for k in range(1, len(st)) if st[k] - en[k - 1] > 2e6] + [len(st)]
print(f"ANE0 任务 {len(st)}，ANE1 任务 {len(st1)}，{len(cuts) - 1} 段，marks {len(marks)} 行")


def last_before(ids, t):
    v = ev[ids]
    k = np.searchsorted(v, t) - 1
    return np.where(k >= 0, v[np.clip(k, 0, len(v) - 1)], np.nan)


def first_after(ids, t):
    v = ev[ids]
    k = np.searchsorted(v, t, side="right")
    return np.where(k < len(v), v[np.clip(k, 0, len(v) - 1)], np.nan)


d0 = {}
print(f"{'模型':>22} {'G':>5} {'任务':>5} {'d µs':>8} {'d0 µs':>8} {'s':>5} {'2580/s':>6} {'档位分布(前 3)':>26} "
      f"{'间隙 µs':>8} {'x':>5} {'固件':>6} {'ANE1':>6} {'驱动':>6} {'剔停顿':>6} {'停顿':>5}")
for r in range(len(cuts) - 1):
    a, b = cuts[r], cuts[r + 1]
    s, e = st[a:b], en[a:b]
    keep = s >= s[0] + SKIP * 1e6
    if keep.sum() < 20 or r >= len(marks):
        continue
    s, e = s[keep], e[keep]
    model, G = os.path.basename(marks[r][0]).replace(".mlmodelc", ""), int(marks[r][1])
    dur = e - s
    md = np.median(dur)
    if G == 0:
        d0[model] = md
    base = d0.get(model, np.nan)
    span = e[-1] - s[0]
    gap = np.median(s[1:] - e[:-1])
    busy = dur.sum() / span
    m1 = (st1 >= s[0]) & (en1 <= e[-1])
    busy1 = (en1[m1] - st1[m1]).sum() / span if m1.any() else np.nan
    drv0, done = last_before("61b01a9", s), first_after("61b00a0", e)
    ok = (s - drv0 < 1000) & (done - e < 1000)
    busy_drv = (done - drv0)[ok].sum() / span * len(s) / max(ok.sum(), 1)
    win = ((s - s[0]) // 5e5).astype(int)
    cnt = np.bincount(win)[:-1]                     # 最后一个窗口不完整，不计
    good = np.flatnonzero(cnt >= 0.5 * np.median(cnt))
    kw = np.isin(win, good)
    busy_ns = dur[kw].sum() / (len(good) * 5e5) if len(good) else np.nan
    stall = 1 - len(good) / max(len(cnt), 1)
    f = 2580 * base / dur
    lv = np.array([min(DT, key=lambda x: abs(x - v)) for v in f])
    vals, cnt = np.unique(lv, return_counts=True)
    top = " ".join(f"{v}:{c * 100 // len(lv)}%" for c, v in sorted(zip(cnt, vals), reverse=True)[:3])
    print(f"{model:>22} {G:5d} {len(s):5d} {md:8.1f} {base:8.1f} {md / base:5.2f} {2580 * base / md:6.0f} {top:>26} "
          f"{gap:8.1f} {gap / base:5.2f} {busy:6.1%} {busy1:6.1%} {busy_drv:6.1%} {busy_ns:6.1%} {stall:5.0%}")
