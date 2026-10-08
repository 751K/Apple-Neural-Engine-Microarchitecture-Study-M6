#!/usr/bin/env python3
# 图 11-2（第 11.3.2 节）：共享簇（PE）的调频行为。
#   (a) 冷启动后的提速：速度 = 首个任务时长 ÷ 当前任务时长。NE 为卷积模型（第 5–7 轮），PE 为只含逐元素运算的模型
#       （第 1–4 轮）；粗线为代表轮，细线为其余各轮。
#   (b) PE 任务时长：单独运行（第 1 轮）与 GPU 先读内存 1.5 s 后再启动（第 8、9 轮）。
#   (c) 与 (b) 对齐的 SoC 电压域实际档位（约 25 ms 一次采样，取窗口内驻留最多的一档；无驻留的窗口不画）。
# 数据：data/09_clock/socpe_kt/（kdebug ANE0 任务、socsamp 采样、各轮起点 marks.txt）。
import bisect
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figplot import Chart, COLORS, FG2, FG3, GRID  # noqa: E402

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '09_clock', 'socpe_kt')
NAMES = ['VMIN', 'VNOM', 'VMAX', 'VOVD', 'VOVD2']
TB = 24e3                                   # 系统时基：每毫秒 24000 个刻度

marks = [(int(a), b) for a, b in (l.split() for l in open(os.path.join(D, 'marks.txt')))]
soc = []
for l in open(os.path.join(D, 'soc.txt')):
    p = l.replace('|', ' ').split()
    t, w = int(p[0]), int(p[1])
    s = list(map(int, p[2:7]))
    soc.append((t - w, t, s.index(max(s)) if max(s) > 0 else None))
st, tasks = defaultdict(list), []
for l in open(os.path.join(D, 'trace.txt')):
    t, i, cpu = l.split()
    e = 'ANE1' if 'ANE1' in cpu else 'ANE0'
    if i == '61b0125':
        st[e].append(int(t))
    elif st[e]:
        a = st[e].pop(0)
        tasks.append((a, int(t) - a, e))
tasks = sorted(x for x in tasks if x[2] == 'ANE0')


def round_(k, smooth=True):
    """第 k 轮（从 1 起）：返回 (起点刻度, [(相对毫秒, 任务 µs)])，时间从该轮第一个任务开始计。"""
    m = marks[k - 1][0]
    nxt = marks[k][0] if k < len(marks) else 1 << 62
    sel = [(a, du) for a, du, _ in tasks if m <= a < nxt]
    t0 = sel[0][0]
    raw = [((a - t0) / TB, du / 24) for a, du in sel]
    if not smooth:
        return t0, raw
    out = []                                  # 5 个任务的滑动中位数，去掉单个任务的抖动
    for k in range(len(raw)):
        w = sorted(d for _, d in raw[max(0, k - 2):k + 3])
        out.append((raw[k][0], w[len(w) // 2]))
    return t0, out


NE_R, PE_R, GPU_R = (5, 6, 7), (1, 2, 3, 4), (8, 9)
NE, PE, GPU = COLORS[1], COLORS[0], COLORS[4]
XMAX = 1100
c = Chart(1000, 1030)
X0, AW = 110, 760

# ---------- (a) 冷启动后的提速 ----------
ax = c.axes(x=X0, y=50, w=AW, h=250, xr=(0, XMAX), yr=(0.8, 3.2), xticks=list(range(0, 1101, 100)),
            yticks=[1, 1.5, 2, 2.5, 3], yticklabels=['1×', '1.5×', '2×', '2.5×', '3×'],
            ylabel='相对最低档的速度', title='(a) 冷启动后的提速：NE（卷积）与 PE（逐元素运算）')
for rounds, col in ((NE_R, NE), (PE_R, PE)):
    for j, k in enumerate(rounds):
        _, ser = round_(k)
        base = round_(k, smooth=False)[1][0][1]   # 首个任务（最低档）的时长
        xs = [t for t, _ in ser if t <= XMAX]
        ys = [min(3.15, max(0.85, base / du)) for t, du in ser if t <= XMAX]
        if j == 0:
            ax.line(xs, ys, color=col, marker=False, width=2.0, label=None)
        else:
            c.a('<path d="M' + ' L'.join(f'{ax.X(x):.1f} {ax.Y(y):.1f}' for x, y in zip(xs, ys))
                + f'" fill="none" stroke="{col[0]}" stroke-width="1" opacity="0.35"/>')

# ---------- (b) PE 任务时长：单独运行与 GPU 同时运行 ----------
YB = 400
bx = c.axes(x=X0, y=YB, w=AW, h=300, xr=(0, XMAX), yr=(300, 1300), xticks=list(range(0, 1101, 100)),
            yticks=[400, 600, 800, 1000, 1200], ylabel='PE 任务时长（µs）',
            title='(b) PE 任务时长：单独运行与 GPU 同时工作')
_, ser1 = round_(PE_R[0])
for k, col in ((PE_R[0], PE), (GPU_R[0], GPU)):
    _, ser = round_(k)
    bx.line([t for t, _ in ser if t <= XMAX], [min(1290, d) for t, d in ser if t <= XMAX], color=col, marker=False, width=1.8)
bx.hline(466, '满载约 466 µs', anchor='start')

# ---------- (c) SoC 电压档位（与 (b) 对齐） ----------
YC = YB + 300 + 90
cx = c.axes(x=X0, y=YC, w=AW, h=110, xr=(0, XMAX), yr=(-0.5, 4.5), xticks=list(range(0, 1101, 100)),
            yticks=[0, 2, 4], yticklabels=['VMIN', 'VMAX', 'VOVD2'], xlabel='时间（ms，自该轮第一个任务开始）',
            title='(c) SoC 电压域的实际档位')
ends = [x[1] for x in soc]
for k, col, dy in ((PE_R[0], PE, -0.12), (GPU_R[0], GPU, 0.12)):
    t0, ser = round_(k)
    t1 = t0 + XMAX * TB
    pts = [((a - t0) / TB, (b - t0) / TB, lv) for a, b, lv in soc if b > t0 and a < t1 and lv is not None]
    for a, b, lv in pts:
        c.a(f'<line x1="{cx.X(max(a, 0)):.1f}" y1="{cx.Y(lv + dy):.1f}" x2="{cx.X(min(b, XMAX)):.1f}" y2="{cx.Y(lv + dy):.1f}" stroke="{col[0]}" stroke-width="3"/>')

# 图例
ly = YC + 110 + 74
items = [(NE, 'NE（卷积模型）'), (PE, 'PE 单独运行'), (GPU, 'PE，GPU 先读内存 1.5 s 后启动')]
for (col, lab), lx in zip(items, (X0, X0 + 200, X0 + 400)):
    c.a(f'<line x1="{lx}" y1="{ly - 4}" x2="{lx + 26}" y2="{ly - 4}" stroke="{col[0]}" stroke-width="2.4"/>')
    c.t(lx + 34, ly + 1, lab, 's')
c.save('fig11-2_pe_ramp')
