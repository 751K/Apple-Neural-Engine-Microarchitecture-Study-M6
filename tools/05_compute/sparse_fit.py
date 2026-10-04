"""sparse.sh 的结果：每个稀疏版本的 HWX 权重段大小、每层耗时（两种层数的斜率）和相对稠密 FP16 的比值。

用法：python3 sparse_fit.py <sparse_out 目录> [kdebug 记录，默认 <目录>/trace.txt，可为 .gz]
第一张表（每次运行，运行名 = <模型>@<输入>）：
  KERN MB   HWX 所有 __KERN_<n> 段大小之和（kern_all.txt，hwx_kern.py）
  调用      bondrun 每次调用耗时中位数（含主机开销）
  任务/调用  计时窗口内固件任务数 ÷ 驱动提交数
  引擎      任务落在哪个引擎；窗口内没有任务即 CPU（整个模型在 CPU 上执行）
  任务µs   计时窗口内两个引擎的任务区间（61b0125 → 61b0126）取并集后的总长 ÷ 提交数。计时窗口是 bondrun 打印的
            mach 时间，与 kdebug 同一时基，不含预热
  提交→完成  每个任务结束（61b0126）与它之前最近一次驱动提交（61b01a9）之差的中位数（µs）。比任务时长多一段固定的
            提交延迟（M6 约 22 µs），斜率中抵消。部分运行里 61b0125 大量缺失（如 c1x1 小剪枝模型，结束事件齐全、
            开始事件只有 0–40%，原因未查明），任务时长不可用，这一列仍然可用
  开始/结束  窗口内 61b0125 与 61b0126 的个数之比（< 0.95 时任务µs 不用）
  M4 的 kdebug 没有固件任务事件（61b0125/126 只在 M6 上有），引擎记为 ANE（窗口内有驱动提交），改用调用耗时中位数
  SOC-NI / DCS  iorlist 采样 1 s 的读带宽直方图（GB/s；M6 上每端口 64、每链路 32 GB/s 截断，是下限）
第二张表（每个 形状_版本@输入#轮，最少与最多两种层数之间的斜率）：
  KERN/层   m2048：两种层数的 KERN 之差 ÷ 层数之差；c1x1 / c3x3 各层共享一份权重，列出整份权重的大小
  每层      两种层数的每次调用 ANE 时间之差 ÷ 层数之差（µs）。M6 用 提交→完成；M4 用调用耗时中位数
  每层(任务) M6 上按任务时长算的同一斜率（开始事件不全时为空）
  相对      ÷ 同形状 fp16@rand 的每层耗时
  有效算力  按稠密乘加数算的 TFLOPS（2 × 乘加 ÷ 每层）：m2048 1.34 亿、c1x1 3355 万、c3x3 6.04 亿次乘加 / 层
  等效读    m2048：KERN/层 ÷ 每层（GB/s），读权重受限时约 150 GB/s
"""
import bisect
import glob
import gzip
import os
import re
import sys
from statistics import median

d = sys.argv[1]
nan = float("nan")
RATE = 24e6 / 5400
MAC = {"m2048": 2048 * 2048 * 32, "c1x1": 512 * 512 * 128, "c3x3": 512 * 512 * 9 * 256}

kern = {}
for l in open(os.path.join(d, "kern_all.txt")):
    p = l.split()
    if len(p) >= 2 and not l.startswith("#"):
        kern[p[0]] = int(p[1]) if p[1].isdigit() else None

call = {}
cur = None
for l in open(os.path.join(d, "run.txt")):
    if l.startswith("== "):
        cur = l[3:].strip()
    m = re.search(r"耗时 中位数 ([\d.]+) us", l)
    if m and cur:
        call[cur] = float(m[1])


def hist_gbs(path, pat):
    tot = 0.0
    for l in open(path):
        m = re.match(r"\[(.*?)\] / \[(.*?)\] / \[(.*?)\] fmt=2", l)
        if not m or not re.search(pat, f"{m[2]} / {m[3]}"):
            continue
        lower = 0.0
        for st, c in re.findall(r"([\d.]+)GB/s=(\d+)", l):
            up = float(st)
            tot += (up + lower) / 2 * int(c) if up != lower else up * int(c)
            lower = up
    return tot / RATE


ior = {}
for f in glob.glob(os.path.join(d, "ior_*.txt")):
    n = os.path.basename(f)[4:-4]
    ior[n] = (hist_gbs(f, r"SOC-NI Util BW / SOC-NI\d+ ANE"), hist_gbs(f, r"DCS BW / ANE\d L\d RD$"))

seg = {}
tp = sys.argv[2] if len(sys.argv) > 2 else os.path.join(d, "trace.txt")
if os.path.exists(tp):
    fw, sub, ends = {"ANE0": [], "ANE1": []}, [], []
    for l in (gzip.open(tp, "rt") if tp.endswith(".gz") else open(tp)):
        p = l.split()
        if len(p) < 3:
            continue
        t = int(p[0])
        if p[1] == "61b01a9":
            sub.append(t)
        else:
            fw["ANE1" if "ANE1" in p[2] else "ANE0"].append((t, p[1]))
            if p[1] == "61b0126":
                ends.append(t)
    tasks, starts = [], []
    for eng, lst in fw.items():
        lst.sort()
        s0 = None
        for t, i in lst:
            if i == "61b0125":
                s0 = t
                starts.append(t)
            elif s0 is not None:
                tasks.append((s0, t - s0, eng)); s0 = None
    tasks.sort(); sub.sort(); ends.sort(); starts.sort()
    for l in open(os.path.join(d, "marks.txt")):
        p = l.split()
        if len(p) < 3:
            continue
        lo, hi = int(p[1]), int(p[2])
        ns = bisect.bisect_left(sub, hi) - bisect.bisect_left(sub, lo)
        if not ns:                                           # 窗口内没有驱动提交：整个模型在 CPU 上执行
            seg[p[0]] = dict(eng="CPU")
            continue
        ne = bisect.bisect_right(ends, hi) - bisect.bisect_left(ends, lo)
        if not ne:                                           # M4：没有固件任务事件，改用调用耗时中位数
            seg[p[0]] = dict(eng="ANE", per_call=call.get(p[0], nan))
            continue
        nst = bisect.bisect_right(starts, hi) - bisect.bisect_left(starts, lo)
        lat = []
        for e in ends[bisect.bisect_left(ends, lo):bisect.bisect_right(ends, hi)]:
            k = bisect.bisect_left(sub, e) - 1
            if k >= 0 and sub[k] >= lo:
                lat.append((e - sub[k]) / 24)
        tk = [x for x in tasks if lo <= x[0] and x[0] + x[1] <= hi]
        union, end = 0, -1                                   # 两个引擎的任务区间取并集
        for s0, dur, _ in tk:
            if s0 >= end:
                union += dur; end = s0 + dur
            elif s0 + dur > end:
                union += s0 + dur - end; end = s0 + dur
        seg[p[0]] = dict(per_call=median(lat), task=union / 24 / ns if nst >= 0.95 * ne else nan,
                         tpc=ne / ns, ratio=nst / ne, eng="+".join(sorted({e for _, _, e in tk})) or "ANE0?")


def parse(r):
    n, rest = r.split("@")
    f, _, rd = rest.partition("#")
    s, v, L = n.split("_")
    return s, v, int(L[1:]), f, rd


def key(r):
    s, v, L, f, rd = parse(r)
    return s, rd, f != "rand", f, v != "fp16", v, L


runs = sorted(set(call) | set(seg), key=key)
print(f"{'运行':>26} {'KERN MB':>8} {'调用 µs':>8} {'任务/调用':>8} {'开始/结束':>8} {'引擎':>9} {'提交→完成':>9} "
      f"{'任务µs':>8} {'SOC-NI':>7} {'DCS':>6}")
for r in runs:
    s = seg.get(r, {})
    k = kern.get(r.split("@")[0])
    so, dc = ior.get(r, (nan, nan))
    print(f"{r:>26} {k / 1e6 if k else nan:8.2f} {call.get(r, nan):8.1f} {s.get('tpc', nan):8.2f} {s.get('ratio', nan):8.2f} "
          f"{s.get('eng', '—'):>9} {s.get('per_call', nan):9.1f} {s.get('task', nan):8.1f} {so:7.0f} {dc:6.0f}")

print()
print(f"{'形状_版本@输入#轮':>22} {'L':>7} {'KERN/层 MB':>10} {'每层 µs':>8} {'每层(任务)':>10} {'相对':>6} "
      f"{'有效 TFLOPS':>11} {'等效读 GB/s':>10}")
pairs = {}
for r in runs:
    s, v, L, f, rd = parse(r)
    pairs.setdefault((s, v, f, rd), {})[L] = r
base = {}
for (s, v, f, rd), byL in pairs.items():
    if len(byL) < 2:
        continue
    La, Lb = min(byL), max(byL)
    a, b = byL[La], byL[Lb]
    tag = f"{s}_{v}@{f}" + (f"#{rd}" if rd else "")
    if seg.get(a, {}).get("eng") == "CPU" or seg.get(b, {}).get("eng") == "CPU":
        print(f"{tag:>22} CPU")
        continue
    if "per_call" not in seg.get(a, {}) or "per_call" not in seg.get(b, {}):
        print(f"{tag:>22} 缺数据")
        continue
    ka, kb = kern.get(a.split("@")[0]), kern.get(b.split("@")[0])
    kpl = ((kb - ka) / (Lb - La) if s == "m2048" else kb) / 1e6 if ka and kb else nan
    per = (seg[b]["per_call"] - seg[a]["per_call"]) / (Lb - La)
    pt = (seg[b].get("task", nan) - seg[a].get("task", nan)) / (Lb - La)
    if v == "fp16" and f == "rand":
        base[(s, rd)] = per
    rel = per / base[(s, rd)] if (s, rd) in base else nan
    rdbw = f"{kpl * 1e3 / per:10.0f}" if s == "m2048" else f"{'':>10}"
    print(f"{tag:>22} {f'{La}→{Lb}':>7} {kpl:10.3f} {per:8.2f} {pt:10.2f} {rel:6.2f} {2 * MAC[s] / per / 1e6:11.1f} {rdbw}")
