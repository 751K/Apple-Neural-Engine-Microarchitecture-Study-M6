#!/usr/bin/env python3
# 图 12-1：不同睡眠时间 G 下 ANE 的档位与忙碌比例（第 12.2 节，表 12-2）。
# 数据：data/10_clpc/gov_kt/tasks.txt（kdebug：61b0125 任务开始、61b0126 任务结束，mach tick 24 MHz）。
# 处理与 tools/10_clpc/gov_fit.py 相同：相邻任务相隔 > 2 s 分段，每段对应一个 G（顺序同 gov_ktrace.sh：
# 0 100 150 200 300 400 1000 3000；3000 一段未被追踪记录），每段丢弃前 2 s；任务时长按 T = C / f + D
# （满频 2580 MHz 时 1267.5 µs，D = 8 µs）换算成设备树 32 档中最接近的一档；忙碌比例 = 任务时长之和 / 段总时长。
# 上图：每个 G 下各档位所占比例（圆面积）与档位中位数；下图：ANE 忙碌比例。
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figplot import Chart, COLORS, FG3  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
DT = [804, 828, 852, 960, 996, 1032, 1092, 1128, 1188, 1248, 1308, 1368, 1404, 1476, 1548, 1632,
      1716, 1788, 1872, 1908, 1968, 2052, 2112, 2196, 2280, 2352, 2364, 2436, 2448, 2484, 2508, 2580]
C, D = 1267.5 - 8.0, 8.0
GS = [0, 100, 150, 200, 300, 400, 1000, 3000]
SKIP = 2.0

st, en, cur = [], [], None
for l in open(os.path.join(ROOT, 'data/10_clpc/gov_kt/tasks.txt')):
    p = l.split()
    if len(p) < 2:
        continue
    t, i = int(p[0]) / 24.0, p[1]
    if i == '61b0125':
        cur = t
    elif i == '61b0126' and cur is not None:
        st.append(cur); en.append(t); cur = None
st, en = np.array(st), np.array(en)
cuts = [0] + [k for k in range(1, len(st)) if st[k] - en[k - 1] > 2e6] + [len(st)]


def mhz(dur):
    f = C * 2580 / (dur - D)
    return min(DT, key=lambda x: abs(x - f))


rows = []
for r in range(len(cuts) - 1):
    s, e = st[cuts[r]:cuts[r + 1]], en[cuts[r]:cuts[r + 1]]
    keep = s >= s[0] + SKIP * 1e6
    if keep.sum() < 20:
        continue
    s, e = s[keep], e[keep]
    lv = np.array([mhz(x) for x in e - s])
    vals, cnt = np.unique(lv, return_counts=True)
    rows.append(dict(G=GS[r], med=float(np.median(lv)), dist=dict(zip(vals.tolist(), (cnt / len(lv)).tolist())),
                     busy=(e - s).sum() / (e[-1] - s[0]), gap=float(np.median(s[1:] - e[:-1]))))
for q in rows:
    print(f"G={q['G']:5d}  档位中位 {q['med']:.0f} MHz  忙碌 {q['busy']:.1%}  空闲中位 {q['gap']:.0f} µs")

n = len(rows)
c = Chart(W=1000, H=740)
X0, W0 = 110, 760
xt = list(range(n))
xl = [str(q['G']) for q in rows]
# 上图：档位
ax = c.axes(X0, 40, W0, 380, (-0.5, n - 0.5), (700, 2700), ylabel='NE 时钟档位（MHz）',
            yticks=[852, 1200, 1548, 1872, 2196, 2580], xticks=xt, xticklabels=xl, title=None)
c.t(X0, 28, '（a）各睡眠时间下的档位分布', 'h2')
ax.hline(2580, '上限 2580 MHz', anchor='end')
ax.hline(852, '下限 852 MHz', anchor='start')
for k, q in enumerate(rows):
    for f, p in q['dist'].items():
        if p < 0.01:
            continue
        r = 2 + 22 * p ** 0.5
        c.a(f'<circle cx="{ax.X(k):.1f}" cy="{ax.Y(f):.1f}" r="{r:.1f}" fill="{COLORS[0][1]}" stroke="{COLORS[0][0]}" '
            f'stroke-width="1.1" opacity="0.85"/>')
ax.line(xt, [q['med'] for q in rows], color=1, marker=True, label='档位中位数')
for k, q in enumerate(rows):
    if k < 2 or q["med"] <= 852:
        continue  # 上限、下限处的中位数由两条水平线标出
    x, y = ax.X(k) + 34, ax.Y(q['med']) - 8
    c.t(x, y, f"{q['med']:.0f}", 'tk', 'start', COLORS[1][0])
# 圆面积图例
lx = X0 + W0 + 22
c.t(lx, 70, '圆面积：该档位', 'c')
c.t(lx, 88, '所占任务比例', 'c')
for j, p in enumerate([0.1, 0.4, 0.9]):
    r = 2 + 22 * p ** 0.5
    yy = 118 + j * 52
    c.a(f'<circle cx="{lx + 26}" cy="{yy}" r="{r:.1f}" fill="{COLORS[0][1]}" stroke="{COLORS[0][0]}" stroke-width="1.1"/>')
    c.t(lx + 58, yy + 5, f'{int(p * 100)}%', 's')
c.legend(lx - 6, 290)

# 下图：忙碌比例
ax2 = c.axes(X0, 500, W0, 180, (-0.5, n - 0.5), (50, 90), xlabel='调用前睡眠时间 G（µs）', ylabel='ANE 忙碌比例（%）',
             yticks=[50, 60, 70, 80, 90], xticks=xt, xticklabels=xl)
c.t(X0, 488, '（b）ANE 忙碌比例', 'h2')
lo, hi = ax2.Y(78), ax2.Y(76)
c.a(f'<rect x="{X0}" y="{lo:.1f}" width="{W0}" height="{hi - lo:.1f}" fill="{COLORS[2][1]}"/>')
ax2.hline(77, '约 77%', color=COLORS[2][0], anchor='end')
ax2.line(xt, [q['busy'] * 100 for q in rows], color=0, marker=True)
for k, q in enumerate(rows):
    ax2.text(k, q['busy'] * 100, f"{q['busy'] * 100:.0f}", 'tk', 'middle', dy=(18 if k in (1, 6) else -10))
# 区域注释
c.t(ax2.X(0.5), ax2.Y(87), '档位已到上限', 'c', 'middle', COLORS[1][0])
c.t(ax2.X(3.5), ax2.Y(87), '档位随 G 下降，忙碌比例保持约 77%', 'c', 'middle', COLORS[0][0])
c.t(ax2.X(6), ax2.Y(87), '档位已到下限', 'c', 'middle', COLORS[1][0])
for xv in (1.5, 5.5):
    for a_ in (ax, ax2):
        a_.vline(xv)
c.save('fig12-1_utilization_target')
