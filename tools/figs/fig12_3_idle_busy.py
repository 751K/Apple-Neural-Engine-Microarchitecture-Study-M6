#!/usr/bin/env python3
# 图 12-3（第 12.4 节）：每次空闲的长度与 ANE 忙碌比例，以及指数平均模型与残差（统一样式见 plotfig.py）。
# 数据：data/10_clpc/gov_tg2/fit.txt、data/10_clpc/gov_tg3/fit.txt。
import math
import os
from plotfig import Plot, K, AXIS, SUB, C_BLUE, C_GREEN, C_ORANGE, C_RED

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '10_clpc')
pts = []
for rnd in ('gov_tg2', 'gov_tg3'):
    for l in open(os.path.join(D, rnd, 'fit.txt')):
        f = l.split()
        if not f or not f[0].startswith('k1'):
            continue
        mode = int([x for x in f if ':' in x and '%' in x][0].split(':')[0])
        pts.append(dict(model=f[0], G=float(f[1]), d=float(f[3]) / 1000, d0=float(f[4]) / 1000,
                        f=float(f[6]), g=float(f[-7]) / 1000, busy=float(f[-5].rstrip('%')),
                        stall=float(f[-1].rstrip('%')), mode=mode, dual='h1w' in f[0] and 'c512_h1w' in f[0]))


def r(d, g, tau):
    return (1 - math.exp(-d / tau)) / (1 - math.exp(-(d + g) / tau))


jump = [pt for pt in pts if pt['model'] == 'k1_c512_h1w256_L384' and pt['f'] > 2400 and pt['G'] > 0]
used = [pt for pt in pts if pt['stall'] == 0 and pt['mode'] not in (2580, 852) and pt not in jump]
bound = [pt for pt in pts if pt['stall'] == 0 and pt['mode'] in (2580, 852) and pt['G'] > 0 and pt not in jump]

best = None
for t10 in range(20, 200):
    tau = t10 / 10
    rs = [r(pt['d'], pt['g'], tau) for pt in used]
    T = sum(rs) / len(rs)
    e = math.sqrt(sum((v - T) ** 2 for v in rs) / len(rs))
    if best is None or e < best[0]:
        best = (e, tau, T)
RMS, TAU, TGT = best


def pred_busy(g):
    lo, hi = 1e-3, 200.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if r(mid, g, TAU) < TGT:
            lo = mid
        else:
            hi = mid
    return lo / (lo + g) * 100


def colour(pt):
    return C_BLUE if pt['d0'] < 2 else (C_GREEN if pt['d0'] < 4 else C_ORANGE)


GREY = ('#888888', '#ffffff')
X0, AW, XMAX = 86, 686, 15
XT = [0, 3, 6, 9, 12, 15]

p = Plot(800, 616)
p.panel(4, 8, 792, 314)
p.panel(4, 332, 792, 212)


def mark(ax, x, y, col, hollow, shape='o'):
    X, Y = ax.X(x), ax.Y(y)
    if shape == 'x':
        p.raw(f'<path d="M{X - 4.6:.1f} {Y - 4.6:.1f} L{X + 4.6:.1f} {Y + 4.6:.1f} '
              f'M{X - 4.6:.1f} {Y + 4.6:.1f} L{X + 4.6:.1f} {Y - 4.6:.1f}" '
              f'stroke="{col[0]}" stroke-width="2"/>')
    elif shape == 's':
        p.raw(f'<rect x="{X - 4.6:.1f}" y="{Y - 4.6:.1f}" width="9.2" height="9.2" '
              f'fill="{"#ffffff" if hollow else col[0]}" stroke="{col[0]}" stroke-width="1.9"/>')
    else:
        p.raw(f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="4.8" '
              f'fill="{"#ffffff" if hollow else col[0]}" stroke="{col[0]}" stroke-width="1.9"/>')


# (a) 每次空闲与忙碌比例
ax = p.axes(x=X0, y=46, w=AW, h=242, xr=(0, XMAX), yr=(30, 90),
            xticks=XT, yticks=[30, 40, 50, 60, 70, 80, 90],
            ylabel='忙碌比例 (%)', title='(a) 每次空闲与忙碌比例', title_x=18)
ax.hline(77, color='#888888', dash='4 3', sw=1.1)
ax.text(14.8, 77, '77%', 13, SUB, 'end', 600, dy=-7)

gs = [0.2 + k * 0.05 for k in range(int((XMAX - 0.2) / 0.05))]
ax.line(gs, [pred_busy(g) for g in gs], color=('#333333', '#ffffff'), marker=None, width=2.0)
ax.text(11.6, pred_busy(11.6), f'τ = {TAU:.1f} ms, T = {TGT * 100:.0f}%', 13, '#333333', 'middle', 600, dy=26)

for pt in bound:
    mark(ax, pt['g'], pt['busy'], GREY, True)
for pt in used:
    mark(ax, pt['g'], pt['busy'], colour(pt), pt['dual'], 's' if pt['dual'] else 'o')
for pt in jump:
    mark(ax, pt['g'], pt['busy'], C_RED, False, 'x')

jx = max(pt['g'] for pt in jump)
ax.text(jx, 34.8, '跳至 2540 MHz', 13, C_RED[0], 'start', 600, dx=12, dy=4)

# (b) 模型残差
bx = p.axes(x=X0, y=370, w=AW, h=114, xr=(0, XMAX), yr=(-8, 10),
            xticks=XT, yticks=[-5, 0, 5, 10], yticklabels=['−5', '0', '+5', '+10'],
            xlabel='每次空闲 (ms)', ylabel='残差 (百分点)',
            title=f'(b) 模型残差（RMS {RMS * 100:.1f}%）', title_x=18)
bx.hline(0, color=AXIS, dash=None, sw=1.0)
for pt in used:
    mark(bx, pt['g'], (r(pt['d'], pt['g'], TAU) - TGT) * 100, colour(pt), pt['dual'], 's' if pt['dual'] else 'o')

# 底部两行白底居中图例（颜色表时长，形状表单/双引擎与特殊点）
row1 = [
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="4.5" fill="{C_BLUE[0]}"/></svg>', '满频 ≈ 1.3 ms'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="4.5" fill="{C_GREEN[0]}"/></svg>', '满频 ≈ 2.7 ms'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="4.5" fill="{C_ORANGE[0]}"/></svg>', '满频 ≈ 5.3 ms'),
    ('<svg xmlns="http://www.w3.org/2000/svg" width="22" height="14" viewBox="0 0 22 14"><line x1="0" y1="7" x2="22" y2="7" stroke="#333333" stroke-width="2"/></svg>', '拟合模型'),
]
row2 = [
    ('<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="4.5" fill="#444444"/></svg>', '单 ANE'),
    ('<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><rect x="2.5" y="2.5" width="9" height="9" fill="#ffffff" stroke="#444444" stroke-width="1.8"/></svg>', '双 ANE'),
    ('<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="4.5" fill="#ffffff" stroke="#888888" stroke-width="1.8"/></svg>', '档位到限'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><path d="M3 3 L11 11 M3 11 L11 3" stroke="{C_RED[0]}" stroke-width="2"/></svg>', '跳变（不拟合）'),
]

for ry, row in ((566, row1), (594, row2)):
    parts = [f'<span style="display:flex;align-items:center;gap:6px">{ic}<span>{lb}</span></span>' for ic, lb in row]
    p.raw(f'<foreignObject x="0" y="{ry - 14}" width="800" height="26"><div xmlns="http://www.w3.org/1999/xhtml" '
          f'style="display:flex;justify-content:center;gap:34px;align-items:center;height:26px;'
          f'font-family:Arial,\'Helvetica Neue\',\'PingFang SC\',sans-serif;font-size:13px;color:{K}">'
          + ''.join(parts) + '</div></foreignObject>')

print(p.save('fig12-3_idle_busy'))
