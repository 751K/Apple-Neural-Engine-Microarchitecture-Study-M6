#!/usr/bin/env python3
# 图 11-1：从空闲开始连续调用时，每个 ANE 任务的时长随时间的变化（第 11.2.2 节，统一样式见 plotfig.py）。
# 数据：data/09_clock/freq_kt/trace.txt。
import math
import os
from plotfig import Plot, K, AXIS, TICK, SUB, C_BLUE, C_ORANGE

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
t0, dur, st = None, [], []
for line in open(os.path.join(ROOT, 'data/09_clock/freq_kt/trace.txt')):
    parts = line.split()
    if len(parts) != 2:
        continue
    t = int(parts[0])
    if parts[1] == '61b0125':
        t0 = t
    elif parts[1] == '61b0126' and t0 is not None:
        dur.append((t - t0) / 24.0)
        st.append(t0 / 24.0)
        t0 = None
cuts = [0] + [k for k in range(1, len(st)) if st[k] - st[k - 1] > 1e6] + [len(st)]
rounds = [(cuts[r], cuts[r + 1]) for r in range(len(cuts) - 1)]

pauses = [((st[a + 19] - st[a] + dur[a + 19]) / 1000, (st[a + 20] - st[a]) / 1000) for a, b in rounds]
p0 = sum(x for x, _ in pauses) / len(pauses)
p1 = sum(y for _, y in pauses) / len(pauses)

# T = C / f + D
D = 12.0
LOW = [(3809.1, 852), (2382.1, 1368), (2108.3, 1548), (1904.7, 1716), (1748.9, 1872)]
C = math.exp(sum(math.log(f * (T - D)) for T, f in LOW) / len(LOW))
# 选取右侧刻度间距充足、无需引线折线的 8 个代表档位
PATH = [852, 1188, 1368, 1548, 1716, 1872, 2196, 2580]

p = Plot(800, 436)
p.panel(4, 8, 504, 384)
p.panel(520, 8, 276, 384)

# (a) 前 330 ms 升频过程
YR = (1150, 4000)
A = p.axes(x=84, y=50, w=324, h=284, xr=(0, 330), yr=YR,
           xlabel='时间 (ms)', ylabel='任务时长 (µs)',
           xticks=[0, 100, 200, 300], yticks=[1500, 2000, 2500, 3000, 3500, 4000],
           title='(a) 升频过程（0–330 ms）', title_x=18)

# 预热后 28 ms 暂停带（柔和浅灰蓝，浅深两色均克制自然）
p.raw(f'<rect x="{A.X(p0):.1f}" y="{A.y}" width="{A.X(p1) - A.X(p0):.1f}" height="{A.h}" fill="#eef0f4"/>')

# 档位水平虚线 + 右侧直出刻度（无折线、字号 13 px）
xr_a = A.x + A.w
p.raw(f'<line x1="{xr_a}" y1="{A.y}" x2="{xr_a}" y2="{A.y + A.h}" stroke="{AXIS}" stroke-width="1.1"/>')
for f in PATH:
    yy = A.Y(C / f + D)
    p.raw(f'<line x1="{A.x}" y1="{yy:.1f}" x2="{xr_a}" y2="{yy:.1f}" stroke="#d5d5dc" stroke-width="0.85" stroke-dasharray="3 3"/>')
    p.raw(f'<line x1="{xr_a}" y1="{yy:.1f}" x2="{xr_a + 5}" y2="{yy:.1f}" stroke="{AXIS}" stroke-width="1.1"/>')
    p.text(xr_a + 9, yy + 4.5, f'{f}', 13, TICK, 'start', 400)
p.raw(f'<text x="{xr_a + 66}" y="{A.y + A.h / 2:.1f}" text-anchor="middle" '
      f'transform="rotate(90 {xr_a + 66} {A.y + A.h / 2:.1f})" '
      f'style="font-size:14.5px;fill:{K};font-weight:600">NE 时钟 (MHz)</text>')

# (b) 330 ms 以后稳定段（纵轴放大）
YR2 = (1255, 1345)
B = p.axes(x=588, y=50, w=192, h=284, xr=(330, 1450), yr=YR2,
           xlabel='时间 (ms)', xticks=[400, 800, 1200],
           yticks=[1260, 1280, 1300, 1320, 1340],
           title='(b) 稳定段（330 ms 后）', title_x=534)

# B 中 2448 / 2580 MHz 两条参考虚线
B.hline(1326.5, color='#c6c6ce', dash='3 3', sw=0.9)
B.hline(1267.5, color='#c6c6ce', dash='3 3', sw=0.9)

# 6 轮散点
for a, b in rounds:
    xs = [(st[k] - st[a]) / 1000 for k in range(a, b)]
    ys = dur[a:b]
    pa = [(x, y) for x, y in zip(xs, ys) if x <= 330]
    pb = [(x, y) for x, y in zip(xs, ys) if x > 330 and YR2[0] < y < YR2[1]]
    A.scatter([x for x, _ in pa], [y for _, y in pa], color=C_BLUE, r=2.0, op=0.45)
    B.scatter([x for x, _ in pb], [y for _, y in pb], color=C_BLUE, r=1.7, op=0.38)

# 第 1 轮路径（暖橙细线）
a, b = rounds[0]
xs1 = [(st[k] - st[a]) / 1000 for k in range(a, b) if (st[k] - st[a]) / 1000 <= 330]
A.line(xs1[:20], dur[a:a + 20], color=C_ORANGE, marker=None, width=1.4)
A.line(xs1[20:], dur[a + 20:a + len(xs1)], color=C_ORANGE, marker=None, width=1.4)

# 极简清晰标注（全部 ≥ 13 px，无说明句）
A.text((p0 + p1) / 2, 1450, f'暂停 {p1 - p0:.0f} ms', 13, SUB, 'middle', 600)
B.text(900, 1337, '2448 MHz', 13, SUB, 'middle', 600)
B.text(900, 1259, '2580 MHz', 13, C_BLUE[0], 'middle', 600)

# 底部白底居中图例
ly = 416
items = [
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="3.5" fill="{C_BLUE[0]}" opacity="0.65"/></svg>', '全部 6 轮'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="26" height="14" viewBox="0 0 26 14"><line x1="0" y1="7" x2="26" y2="7" stroke="{C_ORANGE[0]}" stroke-width="1.8"/></svg>', '第 1 轮路径'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="26" height="14" viewBox="0 0 26 14"><line x1="0" y1="7" x2="26" y2="7" stroke="#888888" stroke-width="1.2" stroke-dasharray="3 3"/></svg>', '时钟档位'),
]
parts = [f'<span style="display:flex;align-items:center;gap:7px">{ic}<span>{lb}</span></span>' for ic, lb in items]
p.raw(f'<foreignObject x="0" y="{ly - 14}" width="800" height="28"><div xmlns="http://www.w3.org/1999/xhtml" '
      f'style="display:flex;justify-content:center;gap:42px;align-items:center;height:28px;'
      f'font-family:Arial,\'Helvetica Neue\',\'PingFang SC\',sans-serif;font-size:13.5px;color:{K}">'
      + ''.join(parts) + '</div></foreignObject>')

print(p.save('fig11-1_ramp_steps'))
