"""从 run_time.sh 的输出求每层耗时：同一形状两种层数的调用耗时中位数之差 ÷ 层数差（正序、倒序分别算，再平均）。
同时列出每次调用的中断数（判断主机唤醒状态是否一致）和用到的引擎。用法：python3 fit.py <time.txt> [MAC 公式用的 C]"""
import re, sys, collections
txt = open(sys.argv[1]).read()
rec = collections.defaultdict(dict)
for blk in txt.split("== ")[1:]:
    head, body = blk.split("\n", 1)
    r, name = head.split()
    m = re.search(r"中位数 ([\d.]+)", body)
    a0 = re.search(r"ANE0: 中断\s+\d+（([\d.]+)", body); a1 = re.search(r"ANE1: 中断\s+\d+（([\d.]+)", body)
    rec[name][r] = (float(m.group(1)) if m else None, float(a0.group(1)) if a0 else -1, float(a1.group(1)) if a1 else -1)
shapes = collections.defaultdict(dict)
for n, v in rec.items():
    s, L = n.rsplit("_L", 1); shapes[s][int(L)] = v
print(f"{'形状':22s} {'每层 µs(正)':>11s} {'(倒)':>7s} {'平均':>7s}  中断/调用 ANE0,ANE1（各层数，正序）")
for s in sorted(shapes, key=lambda x: [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', x)]):
    Ls = sorted(shapes[s]); lo, hi = Ls[0], Ls[-1]
    sl = [(shapes[s][hi][r][0] - shapes[s][lo][r][0]) / (hi - lo) for r in ("fwd", "rev")]
    ir = "  ".join(f"L{L}:{shapes[s][L]['fwd'][1]:.2f},{shapes[s][L]['fwd'][2]:.2f}" for L in Ls)
    print(f"{s:22s} {sl[0]:11.3f} {sl[1]:7.3f} {sum(sl)/2:7.3f}  {ir}")
