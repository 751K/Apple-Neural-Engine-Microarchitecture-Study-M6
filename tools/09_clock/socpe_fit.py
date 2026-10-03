"""socpe_ktrace.sh 的结果：每轮冷启动后 ANE0 任务时长与同一时刻 SOC 档位（实际档位、PMP 汇总下限）的对齐。

用法：python3 socpe_fit.py <socpe_kt 目录> [每轮显示的任务数=60]
SOC 档位取所在采样窗口里驻留最多的一档（窗口约 25 ms）；无驻留记为 "-"。
"""
import bisect
import os
import sys
from collections import Counter, defaultdict

d = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 60
NAMES = ["VMIN", "VNOM", "VMAX", "VOVD", "VOVD2"]
marks = [(int(a), b) for a, b in (l.split() for l in open(os.path.join(d, "marks.txt")))]
soc = []
for l in open(os.path.join(d, "soc.txt")):
    p = l.replace("|", " ").split()
    t, w = int(p[0]), int(p[1])
    s, f = list(map(int, p[2:7])), list(map(int, p[7:12]))
    soc.append((t - w, t, NAMES[s.index(max(s))] if max(s) > 0 else "-", NAMES[f.index(max(f))] if max(f) > 0 else "-"))
ends = [x[1] for x in soc]


def soc_at(t):
    k = bisect.bisect_left(ends, t)
    return soc[k][2:] if k < len(soc) and soc[k][0] <= t else ("?", "?")


st, tasks = defaultdict(list), []
for l in open(os.path.join(d, "trace.txt")):
    t, i, c = l.split()
    e = "ANE1" if "ANE1" in c else "ANE0"
    if i == "61b0125":
        st[e].append(int(t))
    elif st[e]:
        a = st[e].pop(0)
        tasks.append((a, int(t) - a, e))
tasks = sorted(x for x in tasks if x[2] == "ANE0")
summary = defaultdict(Counter)
for k, (m, kind) in enumerate(marks):
    nxt = marks[k + 1][0] if k + 1 < len(marks) else 1 << 62
    sel = [(a, du) for a, du, _ in tasks if m <= a < nxt]
    print(f"\n== 第 {k + 1} 轮 {kind}：任务 {len(sel)}")
    out = []
    for a, du in sel[:N]:
        s, f = soc_at(a + du // 2)
        out.append(f"{(a - m) / 24e3:6.1f}ms:{du / 24:6.0f}µs[{s}/{f}]")
        summary[kind][(round(du / 24, -1), s)] += 1
    for j in range(0, len(out), 6):
        print("   " + "  ".join(out[j:j + 6]))
