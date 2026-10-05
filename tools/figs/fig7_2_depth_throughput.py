#!/usr/bin/env python3
# 图 7-2（第 7.7 节，表 7-12）：M6 与 M4 的整体吞吐（含每次调用的固定开销）随链深度的变化，左 FP16、右 W8A8。
# 形状：1×1 卷积链，512 通道，32×32，各层权重不同（模型名后缀 _u）；每层 2 × 512 × 512 × 32 × 32 FLOP。
# 数据：
#   M6 FP16  data/05_compute/chains_run2.txt  中的 k1_c512_h32w32_L{1,4,8,16,32,48}_u（调用耗时取第 1 个数值列，与表 7-12 相同）
#   M6 W8A8  data/05_compute/b6_q8_run.txt    中的 k1_c512_h32w32_L*_u_q8（同一模型出现多次时取文件中最后一次的有效值；48 层在补测行中）
#   M6 FP16 细扫  data/05_compute/b6x_sweep.txt 中的 _u 模型（16–64 层，两轮；每个层数取两轮中较小的调用耗时，
#            以剔除第 1 轮 34 层的一次 2969 µs 离群值），并对 36 层及以上作最小二乘直线拟合，画出拟合直线对应的吞吐曲线。
#   M4 FP16 / W8A8  手工录入自 maderix [4]（即表 7-12 的 M4 两列）；M4 的 48 层一点为 1024 通道、64×64，形状不同，用空心方块区分。
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figplot import Chart, COLORS, AXIS, FG3

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
D = os.path.join(ROOT, 'data', '05_compute')
FLOP = 2 * 512 * 512 * 32 * 32  # 每层


def parse(fn, pat):
    out = {}
    for ln in open(os.path.join(D, fn)):
        m = re.match(pat + r'\s+([\d.]+)\s+([\d.]+)', ln)
        if m:
            out[int(m.group(1))] = float(m.group(2))  # 后出现的覆盖先出现的
    return out


fp = parse('chains_run2.txt', r'k1_c512_h32w32_L(\d+)_u')
q8 = parse('b6_q8_run.txt', r'k1_c512_h32w32_L(\d+)_u_q8')
sw = {}
for ln in open(os.path.join(D, 'b6x_sweep.txt')):
    m = re.match(r'k1_c512_h32w32_L(\d+)_u\s+([\d.]+)', ln)
    if m:
        L, t = int(m.group(1)), float(m.group(2))
        sw[L] = min(sw.get(L, 1e9), t)
# 36 层及以上的直线拟合 t = a + b·L
fx = [L for L in sw if L >= 36]
n = len(fx); mx = sum(fx) / n; my = sum(sw[L] for L in fx) / n
b = sum((L - mx) * (sw[L] - my) for L in fx) / sum((L - mx) ** 2 for L in fx)
a = my - b * mx

M4_FP16 = {1: 5.4, 4: 9.8, 8: 12.3, 16: 11.7, 32: 16.1, 48: 18.5}   # maderix [4]
M4_W8A8 = {1: 5.9, 4: 12.4, 8: 18.6, 16: 22.4, 32: 27.4, 48: 36.0}  # maderix [4]


def thr(d):
    Ls = sorted(d)
    return Ls, [L * FLOP / d[L] / 1e6 for L in Ls]  # FLOP/µs → TFLOPS


P, B = COLORS[0][0], COLORS[1][0]
W, H = 1160, 560
c = Chart(W, H)
XT = [1, 2, 4, 8, 16, 32, 48, 64]
panels = [(80, 'FP16', '吞吐（TFLOPS）', fp, M4_FP16), (650, 'W8A8', '吞吐（TOPS）', q8, M4_W8A8)]
for i, (x0, name, yl, m6, m4) in enumerate(panels):
    ax = c.axes(x=x0, y=40, w=470, h=400, xr=(0.8, 80), yr=(0, 45), xlog=True, xlabel='链深度（层数，对数坐标）', ylabel=yl,
                xticks=XT, yticks=[0, 10, 20, 30, 40], title=f'（{"ab"[i]}）{name}')
    if i == 0:
        # 直线拟合对应的吞吐曲线
        Ls = [16 + k * 0.25 for k in range(0, 193)]  # 只画 16–64 层（细扫覆盖的范围）
        xy = [(ax.X(L), ax.Y(L * FLOP / (a + b * L) / 1e6)) for L in Ls]
        c.a('<path d="M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in xy) + f'" fill="none" stroke="{P}" stroke-width="1.3" stroke-dasharray="5 4" opacity="0.7"/>')
        sx, sy = thr(sw)
        ax.scatter(sx, sy, color=0, r=3, op=0.45)
    m4L = sorted(m4)
    ax.line(m4L[:-1], [m4[L] for L in m4L[:-1]], color=1)
    xa, ya = ax.X(32), ax.Y(m4[32])
    xb, yb = ax.X(48), ax.Y(m4[48])
    c.a(f'<path d="M{xa:.1f} {ya:.1f} L{xb:.1f} {yb:.1f}" stroke="{B}" stroke-width="1.6" stroke-dasharray="3 3" fill="none"/>')
    c.a(f'<rect x="{xb - 4.5:.1f}" y="{yb - 4.5:.1f}" width="9" height="9" fill="#ffffff" stroke="{B}" stroke-width="1.8"/>')
    Ls, ys = thr(m6)
    ax.line(Ls, ys, color=0, r=4.2)
    # 数值标签：同一层数上较高者标在上方，较低者标在下方
    for L, y in zip(Ls, ys):
        up = y >= m4[L]
        if i == 0 and L == 32:      # 避开细扫散点与箭头
            ax.text(L, y, f'{y:.1f}', 'c', 'end', dx=-8, dy=16, col=P)
        elif i == 1 and L == 16:    # 两点几乎重合
            ax.text(L, y, f'{y:.1f}', 'c', 'end', dx=-10, dy=-4, col=P)
        else:
            ax.text(L, y, f'{y:.1f}', 'c', 'middle', dy=-12 if up else 21, col=P)
        ax.text(L, m4[L], f'{m4[L]:.1f}', 'c', 'middle', dy=21 if up else -12, col=B)
    if i == 0:
        ax.text(22, 35.5, 'Core ML 把最后一个 relu', 'c', 'middle')
        ax.text(22, 35.5, '放到 CPU 上（第 7.7 节）', 'c', 'middle', dy=17)
        ax.arrow((24, 32.2), (31, 20.6))
        c.t(ax.X(1), ax.Y(43), f'虚线：36–64 层调用耗时的直线拟合（{a:.0f} µs + 每层 {b:.2f} µs）', 'c')
        c.t(ax.X(1), ax.Y(43) + 18, '在 16–64 层对应的吞吐', 'c')

# 图例
ly = 518
c.leg = []
c.leg.append(('M6（本文）', P, 'line', False))
c.leg.append(('M4（maderix [4]）', B, 'line', False))
c.legend(90, ly, dx=170, cols=2)
c.a(f'<circle cx="{445}" cy="{ly - 4}" r="3" fill="{P}" opacity="0.45"/>')
c.t(456, ly + 1, 'M6 FP16 细扫（16–64 层）', 's')
c.a(f'<rect x="{680}" y="{ly - 8.5}" width="9" height="9" fill="#ffffff" stroke="{B}" stroke-width="1.8"/>')
c.t(698, ly + 1, 'M4 48 层：1024 通道、64×64（形状不同）', 's')
c.t(90, ly + 26, 'M6：512 通道、32×32、各层权重不同，切分到两个 ANE；吞吐含每次调用的固定开销', 'c')
c.save('fig7-2_depth_throughput')
print(f'fit: {a:.1f} + {b:.3f} L  -> {FLOP / b / 1e6:.1f} TFLOPS', file=sys.stderr)
