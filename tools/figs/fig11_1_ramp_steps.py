#!/usr/bin/env python3
# 图 11-1：从空闲开始连续调用时，每个 ANE 任务的时长随时间的变化（第 11.2.2 节）。
# 数据：data/09_clock/freq_kt/trace.txt（freq_ktrace.sh 记录的 kdebug 61b0125 / 61b0126 任务开始 / 结束事件，
#       24 MHz 计时；模型 k1x1_512_h1w128_L384，单 ANE，共享权重；6 轮，每轮先空闲 2.5 s，再由 bondrun
#       预热 20 次、计时 800 次，共 4920 个任务）。
# 处理：与 tools/09_clock/freq_fit.py 相同地配对开始 / 结束事件、按 > 1 s 的间隔切分轮次；横轴为距本轮第一个
#       任务开始的时间。右侧频率刻度按 T = C / f + D 换算：D 取 12 µs（第 11.2.2 节所给 5–12 µs 的上端，
#       该值下 5 个低档台阶的拟合偏差与表 11-2 逐项相同），C 由表 11-2 的 5 个台阶（852、1368、1548、1716、
#       1872 MHz）按对数最小二乘求得；所标频率为第 11.2.3 节所列典型升频路径上的 10 个档位（表 11-1 设备树频率）。
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figplot import Chart, COLORS, AXIS, FG3  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
t0, dur, st = None, [], []
for line in open(os.path.join(ROOT, 'data/09_clock/freq_kt/trace.txt')):
    p = line.split()
    if len(p) != 2:
        continue
    t = int(p[0])
    if p[1] == '61b0125':
        t0 = t
    elif p[1] == '61b0126' and t0 is not None:
        dur.append((t - t0) / 24.0)
        st.append(t0 / 24.0)
        t0 = None
cuts = [0] + [k for k in range(1, len(st)) if st[k] - st[k - 1] > 1e6] + [len(st)]
rounds = [(cuts[r], cuts[r + 1]) for r in range(len(cuts) - 1)]
print(f'{len(dur)} 个任务，{len(rounds)} 轮')

# 预热 20 次与计时段之间的暂停（每轮第 20 个任务结束到第 21 个任务开始）
pauses = [((st[a + 19] - st[a] + dur[a + 19]) / 1000, (st[a + 20] - st[a]) / 1000) for a, b in rounds]
p0 = sum(x for x, _ in pauses) / len(pauses)
p1 = sum(y for _, y in pauses) / len(pauses)
print('暂停 ms：', [f'{x:.1f}–{y:.1f}' for x, y in pauses])

# 稳定段：时长在 1267.5 µs 的 ±0.2% 内
steady = sorted(dur)[len(dur) // 2]
nst = sum(1 for d in dur if abs(math.log(d / steady)) < 0.002)
print(f'中位数 {steady:.1f} µs，稳定段 {nst} 个（{100 * nst / len(dur):.0f}%）')

# T = C / f + D
D = 12.0
LOW = [(3809.1, 852), (2382.1, 1368), (2108.3, 1548), (1904.7, 1716), (1748.9, 1872)]
C = math.exp(sum(math.log(f * (T - D)) for T, f in LOW) / len(LOW))
print(f'C = {C:.4g} 周期，D = {D} µs；2580 MHz → {C / 2580 + D:.1f} µs')
PATH = [852, 1188, 1368, 1548, 1716, 1872, 2196, 2352, 2448, 2580]

W, H = 1120, 560
c = Chart(W=W, H=H)
YR = (1150, 4000)
YT = [1500, 2000, 2500, 3000, 3500, 4000]
A = c.axes(x=90, y=30, w=560, h=430, xr=(0, 330), yr=YR, xlabel='距本轮第一个任务开始的时间（ms）',
           ylabel='任务时长（µs）', xticks=[0, 50, 100, 150, 200, 250, 300], yticks=YT)
# 右栏：稳定段，纵轴放大
YR2 = (1255, 1345)
YT2 = [1260, 1280, 1300, 1320, 1340]
B = c.axes(x=835, y=30, w=250, h=430, xr=(330, 1450), yr=YR2, xticks=[400, 800, 1200], yticks=YT2,
           xlabel='距本轮第一个任务开始的时间（ms）')
c.t(B.x, 22, '330 ms 以后（纵轴放大）', 's')

# 暂停区间
c.a(f'<rect x="{A.X(p0):.1f}" y="{A.y}" width="{A.X(p1) - A.X(p0):.1f}" height="{A.h}" fill="#f0f0f3"/>')
# 档位参考线
for f in PATH:
    y = C / f + D
    c.a(f'<line x1="{A.x}" y1="{A.Y(y):.1f}" x2="{A.x + A.w}" y2="{A.Y(y):.1f}" stroke="#d8d8de" stroke-width="0.8" stroke-dasharray="3 3"/>')
for a, b in rounds:
    xs = [(st[k] - st[a]) / 1000 for k in range(a, b)]
    ys = dur[a:b]
    pa = [(x, y) for x, y in zip(xs, ys) if x <= 330]
    pb = [(x, y) for x, y in zip(xs, ys) if x > 330 and YR2[0] < y < YR2[1]]
    A.scatter([x for x, _ in pa], [y for _, y in pa], color=0, r=2.0, op=0.45)
    B.scatter([x for x, _ in pb], [y for _, y in pb], color=0, r=1.7, op=0.35)

# 第 1 轮的路径（细线）
a, b = rounds[0]
xs = [(st[k] - st[a]) / 1000 for k in range(a, b) if (st[k] - st[a]) / 1000 <= 330]
A.line(xs[:20], dur[a:a + 20], color=COLORS[2], marker=False, width=1.0)
A.line(xs[20:], dur[a + 20:a + len(xs)], color=COLORS[2], marker=False, width=1.0)

# 标注
A.text((p0 + p1) / 2, 1560, '预热 20 次后', 'c', 'middle')
A.text((p0 + p1) / 2, 1560, f'暂停约 {p1 - p0:.0f} ms', 'c', 'middle', dy=17)
A.text(p1 + 12, C / 852 + D, '时钟回落到 852 MHz，重新升频', 'c', dy=5)
A.text(325, steady, f'稳定段 {steady:.1f} µs，占全部任务的 {100 * nst / len(dur):.0f}%', 's', 'end', dy=-46)
A.arrow((290, steady + 230), (300, steady + 25))
B.text(890, 1336, '1326 µs（约 2448 MHz）：约每 300 个', 'c', 'middle')
B.text(890, 1336, '任务出现一段约 15 个任务的回落', 'c', 'middle', dy=17)
B.text(890, 1258, '稳定段 1267.5 µs（2580 MHz）', 'c', 'middle', dy=-2)

# 左栏右侧的频率刻度（引线避免重叠）
ys = [A.Y(C / f + D) for f in PATH]
lab = sorted(range(len(PATH)), key=lambda i: -ys[i])   # 自下而上
pos = {}
last = None
for i in lab:
    y = ys[i]
    if last is not None and last - y < 15:
        y = last - 15
    pos[i] = y
    last = y
xr = A.x + A.w
for i, f in enumerate(PATH):
    c.a(f'<path d="M{xr} {ys[i]:.1f} L{xr + 8} {ys[i]:.1f} L{xr + 22} {pos[i]:.1f} L{xr + 26} {pos[i]:.1f}" fill="none" stroke="{AXIS}" stroke-width="1"/>')
    c.t(xr + 30, pos[i] + 4.5, f'{f}', 'tk')
c.a(f'<text class="s" x="{xr + 88}" y="{30 + 215}" text-anchor="middle" transform="rotate(90 {xr + 88} {30 + 215})">对应的 NE 时钟档位（MHz）</text>')
c.t(90, H - 14, f'6 轮共 {len(dur)} 个任务（紫点）；橙线为第 1 轮的路径；虚线为 T = C / f + D 换算的档位，C = {C / 1e6:.3f} × 10⁶ 周期，D = {D:.0f} µs', 'c')
c.save('fig11-1_ramp_steps')
