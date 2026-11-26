#!/usr/bin/env python3
# 图 13-2（第 13.4 节，表 13-3）：每次推理的 ANE 能耗与调用耗时随睡眠时间的变化（统一样式见 plotfig.py）。
# 数据：data/11_power/power_parts*。
import os
from plotfig import Plot, K, AXIS, C_BLUE, C_GREEN, C_ORANGE, C_RED

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '11_power')
NK = 7


def measure(d, tag):
    path = os.path.join(ROOT, d, tag)
    rows = [list(map(float, l.split())) for l in open(path + '.trace') if l.strip()]
    ts, te = map(float, open(path + '.marks').read().split()[:2])
    med = float(open(path + '.bondrun.txt').read().split('中位数')[1].split()[0])

    def avg(a, b):
        sel = [r for r in rows if a <= r[0] <= b]
        if len(sel[0]) == NK + 2:
            return sum(r[2] - r[1] for r in sel) / len(sel)
        return sum(r[1] for r in sel) / len(sel)

    st = avg(ts + 4, te - 0.3)
    if len(rows[0]) == NK + 2:
        st -= avg(te + 7, te + 99)
    return st, med


pts = []
a, b = measure('power_parts2', 'f16_single'), measure('power_parts2', 'f16_single_r2')
pts.append((0, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
for sl, d, tag in [
    (100, 'power_parts2', 'f16_sl100'),
    (300, 'power_parts2', 'f16_sl300'),
    (800, 'power_parts2', 'f16_sl800'),
    (1600, 'power_parts', 'f16_duty50'),
    (3200, 'power_parts2', 'f16_sl3200'),
    (6400, 'power_parts', 'f16_duty20'),
]:
    w, t = measure(d, tag)
    pts.append((sl, w, t))

re_w, re_t = measure('power_parts4', 'f16_sl3200')
E = [w * (t + s) * 1e-3 for s, w, t in pts]
re_e = re_w * (re_t + 3200) * 1e-3
gain = [E[0] / e for e in E[2:]]

N = len(pts)
labels = [str(s) for s, _, _ in pts]
X0, AW = 86, 686

p = Plot(800, 588)
p.panel(4, 8, 792, 272)
p.panel(4, 290, 792, 256)

# (a) 每次推理的 ANE 能耗
ax = p.axes(x=X0, y=46, w=AW, h=198, xr=(-0.6, N - 0.4), yr=(0, 12),
            xticks=list(range(N)), xticklabels=labels,
            yticks=[0, 3, 6, 9, 12], ylabel='每次推理能耗 (mJ)',
            title='(a) 每次推理的 ANE 能耗', title_x=18)

for i, ((s, w, t), e) in enumerate(zip(pts, E)):
    col = C_BLUE if s <= 100 else C_GREEN
    ax.bars([i], [e], color=col, width=48)
    ax.text(i, e, f'{e:.1f}', 13.5, col[0], 'middle', 700, dy=-7)

# 第 4 轮扣除 CPU 簇复测点（空心橙菱形）
i3200 = [s for s, _, _ in pts].index(3200)
ax.point(i3200 + 0.42, re_e, color=C_ORANGE, marker='d', r=5.2)

ax.text(N - 0.55, 10.6, f'能耗降至 1/{min(gain):.1f}–1/{max(gain):.1f}', 14, C_RED[0], 'end', 600)

# (b) 每次调用的耗时与时钟档位
Y2 = 328
bx = p.axes(x=X0, y=Y2, w=AW, h=156, xr=(-0.6, N - 0.4), yr=(0, 6200),
            xlabel='调用前睡眠时间 (µs)', ylabel='调用耗时 (µs)',
            xticks=list(range(N)), xticklabels=labels,
            yticks=[0, 2000, 4000, 6000],
            title='(b) 每次调用耗时与时钟档位', title_x=18)

# 顶部时钟档位色带（字号 13 px）
for i0, i1, txt, col in [
    (-0.5, 1.5, '2580 MHz', C_BLUE),
    (1.5, 2.5, '≈ 1032 MHz', C_GREEN),
    (2.5, N - 0.5, '852 MHz', C_GREEN),
]:
    x_l, x_r = bx.X(i0) + 3, bx.X(i1) - 3
    p.raw(f'<rect x="{x_l:.1f}" y="{Y2 + 4}" width="{x_r - x_l:.1f}" height="24" rx="4" fill="{col[1]}"/>')
    p.text((x_l + x_r) / 2, Y2 + 20.5, txt, 13, K, 'middle', 600)

bx.line(list(range(N)), [t for _, _, t in pts], color=C_BLUE, marker='o', width=2.4, r=4.4)
bx.text(4.5, 3650, '耗时 ≈ 2.8×', 14, C_RED[0], 'middle', 600)

# 底部白底居中图例
ly = 568
items = [
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="14" viewBox="0 0 16 14"><rect x="1" y="2" width="14" height="10" rx="1.5" fill="{C_BLUE[1]}" stroke="{AXIS}" stroke-width="1"/></svg>', '最高档 (2580 MHz)'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="14" viewBox="0 0 16 14"><rect x="1" y="2" width="14" height="10" rx="1.5" fill="{C_GREEN[1]}" stroke="{AXIS}" stroke-width="1"/></svg>', '低频档 (≤ 1032 MHz)'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><path d="M8 2 L14 8 L8 14 L2 8 Z" fill="#ffffff" stroke="{C_ORANGE[0]}" stroke-width="1.9"/></svg>', f'第 4 轮复测 ({re_e:.1f} mJ)'),
]
parts = [f'<span style="display:flex;align-items:center;gap:7px">{ic}<span>{lb}</span></span>' for ic, lb in items]
p.raw(f'<foreignObject x="0" y="{ly - 14}" width="800" height="28"><div xmlns="http://www.w3.org/1999/xhtml" '
      f'style="display:flex;justify-content:center;gap:34px;align-items:center;height:28px;'
      f'font-family:Arial,\'Helvetica Neue\',\'PingFang SC\',sans-serif;font-size:13px;color:{K}">'
      + ''.join(parts) + '</div></foreignObject>')

print(p.save('fig13-2_energy_vs_level'))
