"""wfmt.sh 的结果：每种权重格式的 HWX 权重段大小、每层耗时（两种层数的斜率）、等效读权重带宽和 DRAM 读带宽下限。

用法：python3 wfmt_fit.py <wfmt_out 目录>
列：
  KERN/层   HWX 所有 __KERN_<n> 段大小之和（kern_all.txt，hwx_kern.py；超过 128 MB 时拆成多个段），
            两种层数之差 ÷ 层数之差（MB），即每层实际存放的权重和调色板字节
  调用      bondrun 每次调用耗时中位数（含主机开销）
  任务/调用  固件任务数 ÷ 驱动提交数（1 表示整个模型一个任务；> 1 表示被拆成多段）
  引擎      任务落在哪个引擎
  ANE/调用  每次调用的 ANE 时间（µs）：两个引擎的任务区间取并集后的总长 ÷ 提交数，每段丢弃前 1.5 s。
            拆到两个引擎的模型（任务/调用 = 2）两段同时执行，按并集算，不重复计入
  CPU 上执行的模型（SOC-NI、DCS 直方图都为 0，HWX 编译失败）没有 ANE 任务，分段时跳过
  每层      两种层数的 ANE/调用 之差 ÷ 层数之差（µs）
  等效读    KERN/层 ÷ 每层（GB/s）：若权重按压缩格式读入，读权重受限时应接近约 150 GB/s
  150 预测  KERN/层 ÷ 150 GB/s（µs）；m2048 的纯计算约 12.7 µs/层（2048² × 32 MAC ÷ 10.6 TMAC/s），二者取大
  SOC-NI / DCS  iorlist 采样 1 s 的读带宽直方图（各端口 / 链路之和，GB/s，每端口每秒约 4444 个采样）。
          SOC-NI 每端口到 64 GB/s、DCS BW 每链路到 32 GB/s 截断，是下限。
"""
import glob
import os
import re
import sys
from statistics import median

d = sys.argv[1]
RATE = 24e6 / 5400

kern = {}
for l in open(os.path.join(d, "kern_all.txt")):
    p = l.split()
    if len(p) >= 2:
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

# kdebug
seg = {}
tp = os.path.join(d, "trace.txt")
if os.path.exists(tp):
    marks = [l.split() for l in open(os.path.join(d, "marks.txt")) if l.strip()]
    marks = [m for m in marks if sum(ior.get(m[0], (99, 99))) > 5]      # CPU 上执行的模型没有 ANE 任务（直方图 < 5 GB/s）
    fw, sub = {"ANE0": [], "ANE1": []}, []
    for l in open(tp):
        p = l.split()
        if len(p) < 3:
            continue
        t = int(p[0]) / 24.0
        if p[1] == "61b01a9":
            sub.append(t)
        else:
            fw["ANE1" if "ANE1" in p[2] else "ANE0"].append((t, p[1]))
    tasks = []
    for eng, lst in fw.items():
        lst.sort()
        s0 = None
        for t, i in lst:
            if i == "61b0125":
                s0 = t
            elif s0 is not None:
                tasks.append((s0, t - s0, eng)); s0 = None
    tasks.sort()
    sub.sort()
    starts = [tasks[0][0]] + [tasks[k][0] for k in range(1, len(tasks)) if tasks[k][0] - tasks[k - 1][0] > 2e6]
    bounds = starts + [float("inf")]
    for r in range(min(len(starts), len(marks))):
        lo, hi = bounds[r] + 1.5e6, bounds[r + 1]
        tk = [x for x in tasks if lo <= x[0] < hi]
        ns = sum(1 for t in sub if lo <= t < hi)
        if not tk or not ns:
            continue
        engs = sorted({e for _, _, e in tk})
        union, end = 0.0, -1.0                                       # 两个引擎的任务区间取并集
        for s0, dur, _ in sorted(tk):
            if s0 >= end:
                union += dur; end = s0 + dur
            elif s0 + dur > end:
                union += s0 + dur - end; end = s0 + dur
        seg[marks[r][0]] = dict(per_call=union / ns, tpc=len(tk) / ns, eng="+".join(engs),
                                med=median(x for _, x, _ in tk))

names = sorted(set(kern) | set(call), key=lambda n: (n.split("_")[0], n.split("_")[1], int(n.split("_L")[1])))
print(f"{'模型':>18} {'KERN MB':>8} {'调用 µs':>8} {'任务/调用':>8} {'引擎':>9} {'ANE/调用 µs':>10} {'SOC-NI':>7} {'DCS':>6}")
for n in names:
    s = seg.get(n, {})
    k = kern.get(n)
    so, dc = ior.get(n, (float("nan"), float("nan")))
    if so + dc <= 5:
        s = dict(eng="CPU")
    print(f"{n:>18} {k / 1e6 if k else float('nan'):8.2f} {call.get(n, float('nan')):8.1f} {s.get('tpc', float('nan')):8.2f} "
          f"{s.get('eng', '—'):>9} {s.get('per_call', float('nan')):10.1f} {so:7.0f} {dc:6.0f}")

print()
print(f"{'形状_格式':>12} {'KERN/层 MB':>10} {'每层 µs':>8} {'等效读 GB/s':>10} {'150 预测 µs':>10} {'相对 FP16':>9}")
pairs = {}
for n in names:
    shape, fmt, L = n.split("_")
    pairs.setdefault((shape, fmt), {})[int(L[1:])] = n
fp = {}
for (shape, fmt), byL in pairs.items():
    if len(byL) < 2:
        continue
    (La, a), (Lb, b) = sorted(byL.items())
    if a not in seg or b not in seg or not kern.get(a) or not kern.get(b):
        print(f"{shape + '_' + fmt:>12} 缺数据")
        continue
    kpl = (kern[b] - kern[a]) / (Lb - La) / 1e6
    if shape == "k1x9":                      # 共享权重：每层都从 DRAM 重读同一份，按整份权重算
        kpl = kern[b] / 1e6
    per = (seg[b]["per_call"] - seg[a]["per_call"]) / (Lb - La)
    pred = kpl * 1e6 / 150e3
    if shape == "m2048":
        pred = max(pred, 12.7)
    if fmt == "fp16":
        fp[shape] = per
    rel = per / fp[shape] if shape in fp else float("nan")
    print(f"{shape + '_' + fmt:>12} {kpl:10.3f} {per:8.1f} {kpl * 1e3 / per:10.0f} {pred:10.1f} {rel:9.2f}")
