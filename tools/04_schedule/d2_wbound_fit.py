"""d2_wbound.sh 的结果：每个模型、每种情况的每次调用耗时、合计吞吐（相对单个进程）、读权重带宽，以及每个引擎的固件任务时长。

用法：python3 d2_wbound_fit.py <d2_wb 目录> [每层读权重字节数 MB = 2.53]
读带宽两种算法：
  按权重  每层读权重字节数 × 层数 × 合计每秒调用次数（只对 1×9 模型；对照模型权重常驻片上，不算）
  直方图  IOReport 链路直方图：平均档位 × 活跃采样数 ÷ 4444 次/秒 ÷ 总时长，各引擎相加。M6 每条链路在 32 GB/s 截断，
          每个引擎两条链路最多显示 64 GB/s，读权重受限时只是下限。两个进程同时运行时，每个进程各自读一遍全系统计数，
          取其中较大者。
固件任务时长：kdebug 61b0125 → 61b0126，按 cpu 列分 ANE0 / ANE1，每段丢弃前 1.5 s（含 bondrun 的 1 s 预热）。
"""
import os
import re
import sys
from statistics import median

d = sys.argv[1]
MB = float(sys.argv[2]) if len(sys.argv) > 2 else 2.53
RATE = 24e6 / 5400

blocks, cur = [], None
for l in open(os.path.join(d, "run.txt")):
    if l.startswith("== "):
        model, case = l[3:].split()
        cur = {"model": model, "case": case, "procs": []}
        blocks.append(cur)
    elif cur is not None:
        m = re.search(r"耗时 中位数 ([\d.]+) us\s+p10 ([\d.]+)\s+p90 ([\d.]+)", l)
        if m:
            cur["procs"].append({"med": float(m[1]), "p10": float(m[2]), "p90": float(m[3]), "irq": {}, "bw": {}})
        m = re.search(r"ANE(\d): 中断\s+(\d+)（([\d.]+) 次/调用）\s+读 活跃采样\s+(\d+) 平均\s+([\d.]+) GB/s", l)
        if m and cur["procs"]:
            cur["procs"][-1]["irq"][int(m[1])] = float(m[3])
            cur["procs"][-1]["bw"][int(m[1])] = (int(m[4]), float(m[5]))
        m = re.search(r"总时长 ([\d.]+) s", l)
        if m and cur["procs"]:
            cur["procs"][-1]["wall"] = float(m[1])

tasks = {}
tp = os.path.join(d, "trace.txt")
if os.path.exists(tp):
    marks = [l.split() for l in open(os.path.join(d, "marks.txt")) if l.strip()]
    ev = {"ANE0": [], "ANE1": []}
    for l in open(tp):
        p = l.split()
        if len(p) == 3:
            ev["ANE1" if "ANE1" in p[2] else "ANE0"].append((int(p[0]) / 24.0, p[1]))
    seg_tasks = {}
    for eng, lst in ev.items():
        lst.sort()
        st, cur_s = [], None
        for t, i in lst:
            if i == "61b0125":
                cur_s = t
            elif cur_s is not None:
                st.append((cur_s, t - cur_s)); cur_s = None
        seg_tasks[eng] = st
    # 段：任意引擎上相邻任务相隔 > 2 s 处切开（段之间空闲 3 s）
    allt = sorted([s for s, _ in seg_tasks["ANE0"]] + [s for s, _ in seg_tasks["ANE1"]])
    starts = [allt[0]] + [allt[k] for k in range(1, len(allt)) if allt[k] - allt[k - 1] > 2e6] if allt else []
    bounds = starts + [float("inf")]
    for r in range(min(len(starts), len(marks))):
        key = (marks[r][0], marks[r][1])
        lo, hi = bounds[r] + 1.5e6, bounds[r + 1]
        tasks[key] = {e: [x for s, x in seg_tasks[e] if lo <= s < hi] for e in ("ANE0", "ANE1")}

single = {}
print(f"{'模型':>22} {'情况':>7} {'每次调用中位 µs（各进程）':>26} {'p10–p90':>20} {'合计吞吐':>7} "
      f"{'ANE0/ANE1 中断/调用':>18} {'按权重 GB/s':>10} {'直方图下限 GB/s':>14} {'任务时长 ANE0 / ANE1 µs（任务数）':>32}")
for b in blocks:
    ps = b["procs"]
    if not ps:
        continue
    if b["case"] == "single":
        single[b["model"]] = ps[0]["med"]
    base = single.get(b["model"])
    rate = sum(1e6 / p["med"] for p in ps)
    speed = rate / (1e6 / base) if base else float("nan")
    L = int(re.search(r"_L(\d+)", b["model"])[1])
    wbw = f"{MB * L * rate / 1e3:10.0f}" if b["model"].startswith("k1x9") else f"{'—':>10}"
    hist = max(sum(n * avg / RATE / p["wall"] for n, avg in p["bw"].values()) for p in ps if "wall" in p)
    meds = " / ".join(f"{p['med']:.0f}" for p in ps)
    rng = " / ".join(f"{p['p10']:.0f}–{p['p90']:.0f}" for p in ps)
    irq = f"{ps[0]['irq'].get(0, 0):.2f} / {ps[0]['irq'].get(1, 0):.2f}"
    tk = tasks.get((b["model"], b["case"]))
    tstr = " / ".join(f"{median(v):.0f}（{len(v)}）" if v else "—" for v in tk.values()) if tk else ""
    print(f"{b['model']:>22} {b['case']:>7} {meds:>26} {rng:>20} {speed:6.2f}× {irq:>18} {wbw} {hist:14.0f} {tstr:>32}")

# ---- 两个引擎的重叠：同时忙 / 只有一个忙 / 都空闲的时间比例，以及重叠时每个引擎分到的读带宽 ----
# 独占时的读带宽取单个进程那一段（每层字节数 × 层数 ÷ 独占时间）；两个进程时，ANE0 每个任务按"被 ANE1 覆盖的部分"
# 和"独占的部分"拆开，用独占带宽扣掉独占部分读的字节，剩下的除以重叠时间，得到重叠时每个引擎的读带宽（取中位数）。
if tasks:
    import numpy as np
    print()
    print(f"{'模型':>22} {'情况':>7} {'同时忙':>6} {'只一个':>6} {'都空闲':>6} {'任务中位 µs':>10} {'被重叠比例':>8} "
          f"{'独占 GB/s':>9} {'重叠时每个引擎 GB/s':>16}")
    alone_bw = {}
    for r in range(min(len(starts), len(marks))):
        m, c = marks[r][0], marks[r][1]
        lo, hi = bounds[r] + 1.5e6, bounds[r + 1]
        a = np.array([(s, s + x) for s, x in seg_tasks["ANE0"] if lo <= s < hi])
        b = np.array([(s, s + x) for s, x in seg_tasks["ANE1"] if lo <= s < hi]) if c != "single" else np.zeros((0, 2))
        if len(a) < 20:
            continue
        t0, t1 = a[0, 0], a[-1, 1]
        ga, gb = np.zeros(int(t1 - t0) + 2, bool), np.zeros(int(t1 - t0) + 2, bool)
        for s, e in a:
            ga[int(s - t0):int(e - t0)] = True
        for s, e in b:
            if s < t1:
                gb[max(0, int(s - t0)):int(min(e, t1) - t0)] = True
        dur = a[:, 1] - a[:, 0]
        ov = np.array([gb[int(s - t0):int(e - t0)].mean() if int(e - t0) > int(s - t0) else 0.0 for s, e in a])
        bw1, bw2 = "", ""
        if m.startswith("k1x9"):
            nbytes = MB * int(re.search(r"_L(\d+)", m)[1]) * 1e6
            ta, to = dur * (1 - ov) / 1e6, dur * ov / 1e6
            if c == "single":
                alone_bw[m] = float(np.median(nbytes / 1e9 / ta))
                bw1 = f"{alone_bw[m]:.0f}"
            elif m in alone_bw:
                k = to > 0.2 * dur / 1e6
                bw1 = f"{alone_bw[m]:.0f}"
                bw2 = f"{np.median((nbytes / 1e9 - alone_bw[m] * ta[k]) / to[k]):.0f}"
        print(f"{m:>22} {c:>7} {(ga & gb).mean():6.0%} {(ga ^ gb).mean():6.0%} {(~(ga | gb)).mean():6.0%} "
              f"{np.median(dur):10.0f} {np.median(ov):8.0%} {bw1:>9} {bw2:>16}")
