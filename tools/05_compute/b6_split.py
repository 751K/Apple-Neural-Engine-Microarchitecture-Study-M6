"""b6_ktrace.sh 的结果：每次调用拆成 ANE 任务时长和其余部分。

用法：python3 b6_split.py <b6_kt 目录>
事件文件每行：mach 时间（24 MHz） debug-id cpu
  61b01a9 = 用户提交（每次调用一次），61b0125 / 61b0126 = 任务开始 / 结束（双 ANE 时每个引擎各一对）
"""
import glob
import os
import sys

import numpy as np

d = sys.argv[1]
print(f"{'层数':>4} {'调用 µs':>9} {'任务数/调用':>10} {'任务时长 µs':>12} {'提交→首个任务开始':>16} {'最后任务结束→下次提交':>20} {'每层任务 µs':>10}")
rows = []
for f in sorted(glob.glob(os.path.join(d, "*.txt")), key=lambda p: int(os.path.basename(p).split(".")[0]) if os.path.basename(p).split(".")[0].isdigit() else 0):
    name = os.path.basename(f)[:-4]
    if not name.isdigit():
        continue
    L = int(name)
    ev = [l.split() for l in open(f) if l.strip()]
    subs, tasks, open_t = [], [], []
    for t, i, *_ in ev:
        t = int(t) / 24.0
        if i == "61b01a9":
            subs.append(t)
        elif i == "61b0125":
            open_t.append(t)
        elif i == "61b0126" and open_t:
            tasks.append((open_t.pop(0), t))
    subs = np.array(subs)
    if len(subs) < 10 or not tasks:
        continue
    period = np.median(np.diff(subs))
    # 每次调用：提交时刻之后、下一次提交之前的所有任务
    tk = np.array(tasks)
    durs, pre, post = [], [], []
    for a, b in zip(subs[:-1], subs[1:]):
        sel = tk[(tk[:, 0] >= a) & (tk[:, 0] < b)]
        if len(sel) == 0:
            continue
        durs.append(sel[:, 1].max() - sel[:, 0].min())
        pre.append(sel[:, 0].min() - a)
        post.append(b - sel[:, 1].max())
    n_per = len(tk) / len(subs)
    rows.append((L, period, n_per, np.median(durs), np.median(pre), np.median(post)))
    print(f"{L:>4} {period:9.1f} {n_per:10.2f} {np.median(durs):12.1f} {np.median(pre):16.1f} {np.median(post):20.1f} {np.median(durs) / L:10.2f}")

if len(rows) >= 3:
    r = np.array(rows)
    big = r[r[:, 0] >= 36]
    k, b = np.polyfit(big[:, 0], big[:, 3], 1)
    print(f"\n任务时长对层数（≥36 层）拟合：{b:.1f} + {k:.2f}·L µs；各点偏差：")
    for L, _, _, du, _, _ in rows:
        print(f"  L{int(L)}: {du - (b + k * L):+.1f} µs")
