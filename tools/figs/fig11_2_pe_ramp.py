#!/usr/bin/env python3
# 图 11-2（第 11.3.2 节）：共享簇（PE）的调频行为（统一样式见 plotfig.py）。
# 数据：data/09_clock/socpe_kt/。
import os
from collections import defaultdict
from plotfig import Plot, K, SUB, C_BLUE, C_GREEN, C_ORANGE

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '09_clock', 'socpe_kt')
TB = 24e3

marks = [(int(a), b) for a, b in (l.split() for l in open(os.path.join(D, 'marks.txt')))]
soc = []
for l in open(os.path.join(D, 'soc.txt')):
    parts = l.replace('|', ' ').split()
    t, w = int(parts[0]), int(parts[1])
    s = list(map(int, parts[2:7]))
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
    m = marks[k - 1][0]
    nxt = marks[k][0] if k < len(marks) else 1 << 62
    sel = [(a, du) for a, du, _ in tasks if m <= a < nxt]
    t0 = sel[0][0]
    raw = [((a - t0) / TB, du / 24) for a, du in sel]
    if not smooth:
        return t0, raw
    out = []
    for idx in range(len(raw)):
        w = sorted(d for _, d in raw[max(0, idx - 2):idx + 3])
        out.append((raw[idx][0], w[len(w) // 2]))
    return t0, out


NE_R, PE_R, GPU_R = (5, 6, 7), (1, 2, 3, 4), (8, 9)
NE, PE, GPU = C_GREEN, C_BLUE, C_ORANGE
XMAX = 1100
XT = [0, 200, 400, 600, 800, 1000]

p = Plot(800, 676)
p.panel(4, 8, 792, 208)
p.panel(4, 226, 792, 208)
p.panel(4, 444, 792, 190)

X0, AW = 92, 680

# (a) 冷启动后的提速
ax = p.axes(x=X0, y=46, w=AW, h=136, xr=(0, XMAX), yr=(0.8, 3.2),
            xticks=XT, yticks=[1, 2, 3], yticklabels=['1×', '2×', '3×'],
            ylabel='相对速度', title='(a) 冷启动提速', title_x=18)
for rounds, col in ((NE_R, NE), (PE_R, PE)):
    for j, k in enumerate(rounds):
        _, ser = round_(k)
        base = round_(k, smooth=False)[1][0][1]
        xs = [t for t, _ in ser if t <= XMAX]
        ys = [min(3.15, max(0.85, base / du)) for t, du in ser if t <= XMAX]
        if j == 0:
            ax.line(xs, ys, color=col, marker=None, width=2.2)
        else:
            p.raw('<path d="M' + ' L'.join(f'{ax.X(x):.1f} {ax.Y(y):.1f}' for x, y in zip(xs, ys))
                  + f'" fill="none" stroke="{col[0]}" stroke-width="1.0" opacity="0.32"/>')

# (b) PE 任务时长
bx = p.axes(x=X0, y=264, w=AW, h=136, xr=(0, XMAX), yr=(300, 1300),
            xticks=XT, yticks=[400, 600, 800, 1000, 1200],
            ylabel='任务时长 (µs)', title='(b) PE 任务时长', title_x=18)
bx.hline(466, color='#888888', dash='4 3', sw=1.1)
bx.text(14, 466, '466 µs', 13, SUB, 'start', 600, dy=-6)
for k, col in ((PE_R[0], PE), (GPU_R[0], GPU)):
    _, ser = round_(k)
    bx.line([t for t, _ in ser if t <= XMAX], [min(1290, d) for t, d in ser if t <= XMAX],
            color=col, marker=None, width=2.0)

# (c) SoC 电压档位
cx = p.axes(x=X0, y=482, w=AW, h=92, xr=(0, XMAX), yr=(-0.5, 4.5),
            xticks=XT, yticks=[0, 2, 4], yticklabels=['VMIN', 'VMAX', 'VOVD2'],
            xlabel='时间 (ms)', title='(c) SoC 电压档位', title_x=18)
for k, col, dy in ((PE_R[0], PE, -0.14), (GPU_R[0], GPU, 0.14)):
    t0, _ = round_(k)
    t1 = t0 + XMAX * TB
    pts = [((a - t0) / TB, (b - t0) / TB, lv) for a, b, lv in soc if b > t0 and a < t1 and lv is not None]
    for a, b, lv in pts:
        p.raw(f'<line x1="{cx.X(max(a, 0)):.1f}" y1="{cx.Y(lv + dy):.1f}" '
              f'x2="{cx.X(min(b, XMAX)):.1f}" y2="{cx.Y(lv + dy):.1f}" '
              f'stroke="{col[0]}" stroke-width="3.2"/>')

# 底部白底居中图例
ly = 656
items = [
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="26" height="14" viewBox="0 0 26 14"><line x1="0" y1="7" x2="26" y2="7" stroke="{NE[0]}" stroke-width="2.4"/></svg>', 'NE（卷积）'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="26" height="14" viewBox="0 0 26 14"><line x1="0" y1="7" x2="26" y2="7" stroke="{PE[0]}" stroke-width="2.4"/></svg>', 'PE 单独'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="26" height="14" viewBox="0 0 26 14"><line x1="0" y1="7" x2="26" y2="7" stroke="{GPU[0]}" stroke-width="2.4"/></svg>', 'PE + GPU 读内存'),
]
parts = [f'<span style="display:flex;align-items:center;gap:7px">{ic}<span>{lb}</span></span>' for ic, lb in items]
p.raw(f'<foreignObject x="0" y="{ly - 14}" width="800" height="28"><div xmlns="http://www.w3.org/1999/xhtml" '
      f'style="display:flex;justify-content:center;gap:42px;align-items:center;height:28px;'
      f'font-family:Arial,\'Helvetica Neue\',\'PingFang SC\',sans-serif;font-size:13.5px;color:{K}">'
      + ''.join(parts) + '</div></foreignObject>')

print(p.save('fig11-2_pe_ramp'))
