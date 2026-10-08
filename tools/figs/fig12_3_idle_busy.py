#!/usr/bin/env python3
# 图 12-3（第 12.4 节）：每次空闲的长度与 ANE 忙碌比例，以及作业结束时采样的指数平均模型。
#   数据为后两轮实验（gov_tg2、gov_tg3）中每个模型、每个睡眠时间的稳态；颜色按满频任务时长，实心为单 ANE，空心为双 ANE。
#   参与拟合的点：主机调用线程没有停顿，且档位众数不在上限 2580 MHz 或下限 852 MHz；档位到头的点画为灰色。
#   满频任务约 1.4 ms 的双 ANE 模型在空闲超过约 2.5 ms 时跳到接近满频（约 2540 MHz），单独标出，不参与拟合。
#   模型：CLPC 以时间常数 τ 对忙碌状态作指数平均，在作业结束时读取 r = (1 − e^(−d/τ)) / (1 − e^(−(d+g)/τ))，
#   并使 r 等于目标 T。联合拟合 τ 与 T（T 取 r 的均值，τ 按 0.1 ms 网格），得 τ ≈ 6.5 ms、T ≈ 80%。
#   上图曲线为该模型给出的稳态忙碌比例 d / (d + g)（对每个 g 解 r(d, g) = T）；下图为各点的 r − T。
# 数据：data/10_clpc/gov_tg2/fit.txt、data/10_clpc/gov_tg3/fit.txt（tools/10_clpc/gov_target2_fit.py 的输出）。
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figplot import Chart, COLORS, FG2, AXIS  # noqa: E402

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


jump = [p for p in pts if p['model'] == 'k1_c512_h1w256_L384' and p['f'] > 2400 and p['G'] > 0]
used = [p for p in pts if p['stall'] == 0 and p['mode'] not in (2580, 852) and p not in jump]
bound = [p for p in pts if p['stall'] == 0 and p['mode'] in (2580, 852) and p['G'] > 0 and p not in jump]
best = None
for t10 in range(20, 200):
    tau = t10 / 10
    rs = [r(p['d'], p['g'], tau) for p in used]
    T = sum(rs) / len(rs)
    e = math.sqrt(sum((v - T) ** 2 for v in rs) / len(rs))
    if best is None or e < best[0]:
        best = (e, tau, T)
RMS, TAU, TGT = best
print(f'{len(used)} 点：τ = {TAU:.1f} ms，T = {TGT * 100:.1f}%，均方根 {RMS * 100:.1f}%')


def pred_busy(g):
    lo, hi = 1e-3, 200.0                       # 解 r(d, g) = T，r 随 d 单调增加
    for _ in range(80):
        mid = (lo + hi) / 2
        if r(mid, g, TAU) < TGT:
            lo = mid
        else:
            hi = mid
    return lo / (lo + g) * 100


def colour(p):
    return COLORS[0] if p['d0'] < 2 else (COLORS[1] if p['d0'] < 4 else COLORS[2])


GREY = ('#b8b8bd', '#ffffff')
JUMP = COLORS[4]
c = Chart(1000, 820)
X0, AW, XMAX = 100, 760, 15


def mark(a, x, y, col, hollow, shape='o'):
    X, Y = a.X(x), a.Y(y)
    if shape == 'x':
        c.a(f'<path d="M{X - 5:.1f} {Y - 5:.1f} L{X + 5:.1f} {Y + 5:.1f} M{X - 5:.1f} {Y + 5:.1f} L{X + 5:.1f} {Y - 5:.1f}" stroke="{col[0]}" stroke-width="2"/>')
    elif shape == 's':
        c.a(f'<rect x="{X - 5:.1f}" y="{Y - 5:.1f}" width="10" height="10" fill="{"#ffffff" if hollow else col[0]}" stroke="{col[0]}" stroke-width="1.8"/>')
    else:
        c.a(f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="5.2" fill="{"#ffffff" if hollow else col[0]}" stroke="{col[0]}" stroke-width="1.8"/>')


# ---------- 上：忙碌比例 ----------
ax = c.axes(x=X0, y=50, w=AW, h=400, xr=(0, XMAX), yr=(30, 90), xticks=list(range(0, 16, 1)),
            yticks=[30, 40, 50, 60, 70, 80, 90], ylabel='ANE 忙碌比例（%）',
            title='(a) 每次空闲的长度与忙碌比例')
ax.hline(77, '77%（第 12.2 节，空闲不超过约 1 ms）', anchor='end')
gs = [0.2 + k * 0.05 for k in range(int((XMAX - 0.2) / 0.05))]
ax.line(gs, [pred_busy(g) for g in gs], color=(FG2, '#ffffff'), marker=False, width=2.0)
c.t(ax.X(12), ax.Y(pred_busy(12)) + 30, f'模型：τ = {TAU:.1f} ms，目标 {TGT * 100:.0f}%', 's', 'middle')
for p in bound:
    mark(ax, p['g'], p['busy'], GREY, True)
for p in used:
    mark(ax, p['g'], p['busy'], colour(p), p['dual'], 's' if p['dual'] else 'o')
for p in jump:
    mark(ax, p['g'], p['busy'], JUMP, False, 'x')
jx = sum(p['g'] for p in jump) / len(jump)
c.t(ax.X(jx) + 14, ax.Y(34.5) + 4, '双 ANE、满频约 1.4 ms 的模型：跳到约 2540 MHz', 's', 'start', JUMP[0])

# ---------- 下：残差 ----------
YB = 50 + 400 + 70
bx = c.axes(x=X0, y=YB, w=AW, h=150, xr=(0, XMAX), yr=(-8, 10), xticks=list(range(0, 16, 1)),
            yticks=[-5, 0, 5, 10], yticklabels=['−5', '0', '+5', '+10'], ylabel='r − 目标（百分点）',
            xlabel='每次空闲（ms，含主机开销）', title=f'(b) 模型残差（均方根 {RMS * 100:.1f}%）')
bx.hline(0, color=AXIS, dash=False)
for p in used:
    mark(bx, p['g'], (r(p['d'], p['g'], TAU) - TGT) * 100, colour(p), p['dual'], 's' if p['dual'] else 'o')

# ---------- 图例 ----------
ly = YB + 150 + 78
items = [(COLORS[0], False, 'o', '单 ANE，满频约 1.3 ms'), (COLORS[1], False, 'o', '单 ANE，约 2.7 ms'),
         (COLORS[2], False, 'o', '单 ANE，约 5.3 ms'), (GREY, True, 'o', '档位已到上下限，不参与拟合'),
         (COLORS[0], True, 's', '双 ANE，约 1.4 ms'), (COLORS[1], True, 's', '双 ANE，约 2.6 ms'),
         (COLORS[2], True, 's', '双 ANE，约 5.2 ms'), (JUMP, False, 'x', '双 ANE，约 1.4 ms，跳变')]
pos = [(X0, 0), (X0 + 220, 0), (X0 + 400, 0), (X0 + 580, 0), (X0, 26), (X0 + 220, 26), (X0 + 400, 26), (X0 + 580, 26)]
for (col, hol, shape, lab), (lx, dy) in zip(items, pos):
    class _A:
        X = staticmethod(lambda v: v)
        Y = staticmethod(lambda v: v)
    mark(_A, lx + 8, ly + dy - 4, col, hol, shape)
    c.t(lx + 22, ly + dy + 1, lab, 's')
c.save('fig12-3_idle_busy')
