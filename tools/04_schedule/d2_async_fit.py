"""d2_async.sh 的结果：每种提交方式的合计吞吐（相对同一模型同一轮的同步调用）、读权重带宽，以及每个引擎的忙碌情况。

用法：python3 d2_async_fit.py <d2_as 目录> [每层读权重字节数 MB = 2.53]
列：
  吞吐     各进程每秒推理次数之和
  倍数     ÷ 同一模型、同一轮的单进程同步吞吐
  按权重   每层读权重字节数 × 层数 × 吞吐（GB/s，只对 1×9 模型；对照模型权重常驻片上）
  中断     ANE0 / ANE1 每次推理的中断数（IOReport 全系统计数，两个进程时取第一个进程看到的值）
  忙碌     kdebug：该段内 ANE0、ANE1 各自有任务在执行的时间比例（任务按先进先出配对，见下），以及两个引擎同时忙的比例；每段丢弃前 1.5 s（含 1 s 预热）
  任务     两个引擎固件任务时长的中位数（µs）
"""
import os
import re
import sys
from statistics import median

d = sys.argv[1]
MB = float(sys.argv[2]) if len(sys.argv) > 2 else 2.53

blocks, cur = [], None
for l in open(os.path.join(d, "run.txt")):
    if l.startswith("== "):
        model, case, rnd = l[3:].split()
        cur = {"model": model, "case": case, "round": rnd, "rate": [], "irq": {}}
        blocks.append(cur)
        continue
    if cur is None:
        continue
    m = re.search(r"= ([\d.]+) 次/s", l)
    if m:
        cur["rate"].append(float(m[1]))
    m = re.search(r"ANE(\d): 中断\s+\d+（([\d.]+) 次/推理）", l)
    if m and int(m[1]) not in cur["irq"]:
        cur["irq"][int(m[1])] = float(m[2])

busy = {}
tp = os.path.join(d, "trace.txt")
if os.path.exists(tp):
    marks = [l.split() for l in open(os.path.join(d, "marks.txt")) if l.strip()]
    ev = {"ANE0": [], "ANE1": []}
    for l in open(tp):
        p = l.split()
        if len(p) == 3:
            ev["ANE1" if "ANE1" in p[2] else "ANE0"].append((int(p[0]) / 24.0, p[1]))
    # 配对：请求在引擎上排队时，前一个任务的结束和下一个任务的开始常是同一时刻，所以同一时刻先处理结束；
    # 开始按先进先出与结束配对；缺开始事件的结束（固件会省略部分开始事件），以前一个任务的结束为开始。
    iv = {}
    for e, lst in ev.items():
        lst.sort(key=lambda x: (x[0], x[1] == "61b0125"))
        out, q, last_end = [], [], None
        for t, i in lst:
            if i == "61b0125":
                q.append(t)
            else:
                if q:
                    s0 = q.pop(0)
                elif last_end is not None and t - last_end < 1e5:
                    s0 = last_end
                else:
                    s0 = None
                if s0 is not None:
                    out.append((max(s0, last_end) if last_end else s0, t))
                last_end = t
        iv[e] = out
    allt = sorted(s for e in iv for s, _ in iv[e])
    starts = [allt[0]] + [allt[k] for k in range(1, len(allt)) if allt[k] - allt[k - 1] > 2e6] if allt else []
    bounds = starts + [float("inf")]
    for r in range(min(len(starts), len(marks))):
        lo, hi = bounds[r] + 1.5e6, bounds[r + 1]
        seg = {e: [(s, t) for s, t in iv[e] if lo <= s < hi] for e in iv}
        span0 = min(s for e in seg for s, _ in seg[e]) if any(seg.values()) else 0
        span1 = max(t for e in seg for _, t in seg[e]) if any(seg.values()) else 1
        span = span1 - span0
        frac = {e: sum(t - s for s, t in seg[e]) / span for e in seg}
        # 两个引擎同时忙：按时间点扫描
        pts = sorted([(s, 1) for e in seg for s, _ in seg[e]] + [(t, -1) for e in seg for _, t in seg[e]])
        both, depth, last = 0.0, 0, span0
        for t, dlt in pts:
            if depth >= 2:
                both += t - last
            depth += dlt
            last = t
        med = {e: median(t - s for s, t in seg[e]) if seg[e] else float("nan") for e in seg}
        busy[(marks[r][0], marks[r][1], marks[r][2])] = (frac["ANE0"], frac["ANE1"], both / span, med["ANE0"], med["ANE1"])

base = {}
print(f"{'模型':>22} {'方式':>14} {'轮':>2} {'吞吐 次/s':>9} {'倍数':>5} {'按权重 GB/s':>10} {'中断 ANE0/1':>12} "
      f"{'忙 ANE0':>7} {'忙 ANE1':>7} {'同时忙':>6} {'任务 µs ANE0/1':>16}")
for b in blocks:
    if not b["rate"]:
        continue
    rate = sum(b["rate"])
    key = (b["model"], b["round"])
    if b["case"] == "sync":
        base[key] = rate
    L = int(re.search(r"_L(\d+)", b["model"])[1])
    wbw = f"{MB * L * rate / 1e3:10.0f}" if b["model"].startswith("k1x9") else f"{'—':>10}"
    bz = busy.get((b["model"], b["case"], b["round"]))
    bs = (f"{bz[0]:7.0%} {bz[1]:7.0%} {bz[2]:6.0%} {bz[3]:7.0f}/{bz[4]:<7.0f}" if bz else "")
    print(f"{b['model']:>22} {b['case']:>14} {b['round']:>2} {rate:9.1f} {rate / base.get(key, float('nan')):5.2f} {wbw} "
          f"{b['irq'].get(0, 0):5.2f}/{b['irq'].get(1, 0):<5.2f}  {bs}")
