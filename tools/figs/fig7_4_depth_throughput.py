#!/usr/bin/env python3
# 图 7-4（第 7.7 节，表 7-12）：M6 与 M4 的整体吞吐（含每次调用固定开销）随链深度的变化（统一样式见 plotfig.py）。
# 数据：data/05_compute/chains_run2.txt、b6_q8_run.txt、b6x_sweep.txt；M4 取自 maderix [4]。
import os
import re
from plotfig import Plot, K, C_BLUE, C_GREEN, C_RED

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '05_compute')
FLOP = 2 * 512 * 512 * 32 * 32


def parse(fn, pat):
    out = {}
    for ln in open(os.path.join(D, fn)):
        m = re.match(pat + r'\s+([\d.]+)\s+([\d.]+)', ln)
        if m:
            out[int(m.group(1))] = float(m.group(2))
    return out


fp = parse('chains_run2.txt', r'k1_c512_h32w32_L(\d+)_u')
q8 = parse('b6_q8_run.txt', r'k1_c512_h32w32_L(\d+)_u_q8')
sw = {}
for ln in open(os.path.join(D, 'b6x_sweep.txt')):
    m = re.match(r'k1_c512_h32w32_L(\d+)_u\s+([\d.]+)', ln)
    if m:
        L, t = int(m.group(1)), float(m.group(2))
        sw[L] = min(sw.get(L, 1e9), t)

fx = [L for L in sw if L >= 36]
n = len(fx)
mx = sum(fx) / n
my = sum(sw[L] for L in fx) / n
b = sum((L - mx) * (sw[L] - my) for L in fx) / sum((L - mx) ** 2 for L in fx)
a = my - b * mx

M4_FP16 = {1: 5.4, 4: 9.8, 8: 12.3, 16: 11.7, 32: 16.1, 48: 18.5}
M4_W8A8 = {1: 5.9, 4: 12.4, 8: 18.6, 16: 22.4, 32: 27.4, 48: 36.0}


def thr(d):
    Ls = sorted(d)
    return Ls, [L * FLOP / d[L] / 1e6 for L in Ls]


p = Plot(800, 412)
p.panel(4, 8, 390, 360)
p.panel(406, 8, 390, 360)

XT = [1, 2, 4, 8, 16, 32, 64]
panels = [
    (74, 18, '(a) FP16', '吞吐 (TFLOPS)', fp, M4_FP16),
    (478, 420, '(b) W8A8', '吞吐 (TOPS)', q8, M4_W8A8),
]

for i, (ax_x, tx, title, yl, m6, m4) in enumerate(panels):
    ax = p.axes(x=ax_x, y=50, w=304, h=256, xr=(0.8, 82), yr=(0, 44),
                xlog=True, xticks=XT, yticks=[0, 10, 20, 30, 40],
                xlabel='层数', ylabel=yl, title=title, title_x=tx)
    if i == 0:
        Ls_fit = [16 + k * 0.5 for k in range(0, 97)]
        ax.line(Ls_fit, [L * FLOP / (a + b * L) / 1e6 for L in Ls_fit],
                color=C_BLUE, marker=None, dash='5 4', width=1.4)
        sx, sy = thr(sw)
        ax.scatter(sx, sy, color=C_BLUE, r=2.8, op=0.45)

    m4L = sorted(m4)
    ax.line(m4L[:-1], [m4[L] for L in m4L[:-1]], color=C_GREEN, marker='o', width=2.2, r=4.2)
    ax.line([32, 48], [m4[32], m4[48]], color=C_GREEN, marker=None, dash='3 3', width=1.6)
    ax.point(48, m4[48], color=C_GREEN, marker='s', r=4.6)

    Ls, ys = thr(m6)
    ax.line(Ls, ys, color=C_BLUE, marker='o', width=2.2, r=4.2)

    if i == 0:
        # 仅标 L32 反常下凹（relu → CPU）与 48 层端点
        ax.arrow((17, 31.5), (30.5, 20.4), color=C_RED, sw=1.5, pad0=2, pad1=6)
        ax.text(16, 33.0, 'relu → CPU', 12.5, C_RED[0], 'middle', 600)
        ax.text(48, ys[-1], f'{ys[-1]:.1f}', 12.5, C_BLUE[0], 'end', 600, dx=-8, dy=-8)
        ax.text(48, m4[48], f'{m4[48]:.1f}', 12.5, C_GREEN[0], 'start', 600, dx=8, dy=4)
    else:
        ax.text(32, ys[-2], f'{ys[-2]:.1f}', 12.5, C_BLUE[0], 'middle', 600, dy=-11)
        ax.text(48, m4[48], f'{m4[48]:.1f}', 12.5, C_GREEN[0], 'start', 600, dx=8, dy=-2)

ly = 392
items = [
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="26" height="14" viewBox="0 0 26 14"><line x1="0" y1="7" x2="26" y2="7" stroke="{C_BLUE[0]}" stroke-width="2.2"/><circle cx="13" cy="7" r="4" fill="#ffffff" stroke="{C_BLUE[0]}" stroke-width="2"/></svg>', 'M6'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="26" height="14" viewBox="0 0 26 14"><line x1="0" y1="7" x2="26" y2="7" stroke="{C_GREEN[0]}" stroke-width="2.2"/><circle cx="13" cy="7" r="4" fill="#ffffff" stroke="{C_GREEN[0]}" stroke-width="2"/></svg>', 'M4'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="26" height="14" viewBox="0 0 26 14"><line x1="0" y1="7" x2="26" y2="7" stroke="{C_BLUE[0]}" stroke-width="1.4" stroke-dasharray="4 3"/><circle cx="13" cy="7" r="3" fill="{C_BLUE[0]}" opacity="0.5"/></svg>', 'M6 细扫与拟合'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><rect x="2.5" y="2.5" width="9" height="9" fill="#ffffff" stroke="{C_GREEN[0]}" stroke-width="1.8"/></svg>', 'M4 48 层（异形）'),
]
parts = [f'<span style="display:flex;align-items:center;gap:7px">{ic}<span>{lb}</span></span>' for ic, lb in items]
p.raw(f'<foreignObject x="0" y="{ly - 14}" width="800" height="28"><div xmlns="http://www.w3.org/1999/xhtml" '
      f'style="display:flex;justify-content:center;gap:34px;align-items:center;height:28px;'
      f'font-family:Arial,\'Helvetica Neue\',\'PingFang SC\',sans-serif;font-size:13.5px;color:{K}">'
      + ''.join(parts) + '</div></foreignObject>')

print(p.save('fig7-4_depth_throughput'))
