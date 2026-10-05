#!/usr/bin/env python3
# 图 13-2（第 13.4 节，表 13-3）：每次推理的 ANE 能耗与调用间隔。
#   (a) 每次推理的 ANE 能耗 = ANE 功耗 × (每次调用耗时 + 睡眠时间)；(b) 每次调用的耗时（中位数），并标出 NE 时钟档位。
# 模型：单 ANE，FP16，1×1、512 通道、1×128、384 层（每次推理 1.29 × 10¹⁰ 次乘加）。
# 数据：早期直接读取 PP0b 的测量（测量期间 CPU 簇空闲，ANE 功耗 = PP0b 稳态平均）：
#   睡眠 0      data/11_power/power_parts2/f16_single 与 f16_single_r2 的平均；
#   100/300/800/3200 µs   data/11_power/power_parts2/f16_sl{100,300,800,3200}；
#   1600/6400 µs          data/11_power/power_parts/f16_duty50、f16_duty20（BONDRUN_SLEEP_US = 1600、6400）。
#   复测点：data/11_power/power_parts4/f16_sl3200（扣除 CPU 簇的第 4 轮，ANE 净功耗）。
# 时间窗同 tools/11_power/power_parts_fit.py（稳态 = 负载开始后 4 s 至结束前 0.3 s）。
# 时钟档位（标注用）取自报告第 12.2 节：睡眠 100 µs 及以下为最高档，300 µs 约 1032 MHz，更长为下限 852 MHz。
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figplot import Chart, COLORS, FG3  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '11_power')
NK = 7  # PP0b PP2b PP4b PZD1 PSTR PPSR PHPC


def measure(d, tag):
    """返回 (ANE 功耗 W, 中位耗时 µs)。PP0b 格式直接取 PP0b；pclus 格式取 (PP0b − PACC0) − 断电时的同一差值。"""
    p = os.path.join(ROOT, d, tag)
    rows = [list(map(float, l.split())) for l in open(p + '.trace') if l.strip()]
    ts, te = map(float, open(p + '.marks').read().split()[:2])
    med = float(open(p + '.bondrun.txt').read().split('中位数')[1].split()[0])

    def avg(a, b):
        sel = [r for r in rows if a <= r[0] <= b]
        if len(sel[0]) == NK + 2:
            return sum(r[2] - r[1] for r in sel) / len(sel)
        return sum(r[1] for r in sel) / len(sel)
    st = avg(ts + 4, te - 0.3)
    if len(rows[0]) == NK + 2:
        st -= avg(te + 7, te + 99)
    return st, med


pts = []  # (睡眠 µs, ANE 功耗, 每次调用 µs)
a, b = measure('power_parts2', 'f16_single'), measure('power_parts2', 'f16_single_r2')
pts.append((0, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
for sl, d, tag in [(100, 'power_parts2', 'f16_sl100'), (300, 'power_parts2', 'f16_sl300'),
                   (800, 'power_parts2', 'f16_sl800'), (1600, 'power_parts', 'f16_duty50'),
                   (3200, 'power_parts2', 'f16_sl3200'), (6400, 'power_parts', 'f16_duty20')]:
    w, t = measure(d, tag)
    pts.append((sl, w, t))
re_w, re_t = measure('power_parts4', 'f16_sl3200')
E = [w * (t + s) * 1e-3 for s, w, t in pts]               # mJ
re_e = re_w * (re_t + 3200) * 1e-3
for (s, w, t), e in zip(pts, E):
    print(f'sleep {s:5d}  {t:7.1f} us  {w:5.2f} W  {e:5.2f} mJ')
print(f'recheck 3200: {re_t:.1f} us {re_w:.2f} W {re_e:.2f} mJ')
slow = [t / pts[0][2] for s, w, t in pts[2:]]
gain = [E[0] / e for e in E[2:]]
print(f'slowdown {min(slow):.2f}-{max(slow):.2f}x, energy 1/{min(gain):.2f}-1/{max(gain):.2f}')

PUR, BLU, ORA = COLORS[0], COLORS[1], COLORS[2]
N = len(pts)
labels = [str(s) for s, _, _ in pts]
W, H = 1000, 760
c = Chart(W, H)
X0, AW = 110, 820

# (a) 每次推理的 ANE 能耗
ax = c.axes(x=X0, y=50, w=AW, h=290, xr=(-0.6, N - 0.4), yr=(0, 12), ylabel='每次推理的 ANE 能耗（mJ）',
            yticks=[0, 2, 4, 6, 8, 10, 12], title='(a) 每次推理的 ANE 能耗')
for i, ((s, w, t), e) in enumerate(zip(pts, E)):
    col = PUR if s <= 100 else BLU
    ax.bars([i], [e], color=col, width=58)
    ax.text(i, e, f'{e:.1f}', 's', 'middle', dy=-8)
    ax.text(i, 0, f'{w:.2f} W', 'c', 'middle', dy=-10)
i3200 = [s for s, _, _ in pts].index(3200)
x, y = ax.X(i3200) + 44, ax.Y(re_e)
c.a(f'<path d="M{x:.1f} {y - 6:.1f} L{x + 6:.1f} {y:.1f} L{x:.1f} {y + 6:.1f} L{x - 6:.1f} {y:.1f} Z" fill="#ffffff" stroke="{ORA[0]}" stroke-width="1.8"/>')
ty = ax.Y(6.6)
c.a(f'<line x1="{x:.1f}" y1="{y - 8:.1f}" x2="{x:.1f}" y2="{ty + 22:.1f}" stroke="{ORA[0]}" stroke-width="1"/>')
c.t(x, ty, f'扣除 CPU 簇的第 4 轮复测', 'c', 'middle')
c.t(x, ty + 16, f'{re_w:.2f} W，{re_e:.1f} mJ', 'c', 'middle')
ax.text(N - 0.5, 11.2, f'睡眠 ≥ 300 µs：能耗降至最高档的 1/{min(gain):.1f} 至 1/{max(gain):.1f}', 'b', 'end')
ax.text(N - 0.5, 10.1, '柱底数字为 ANE 功耗', 'c', 'end')

# (b) 每次调用的耗时
Y2 = 440
bx = c.axes(x=X0, y=Y2, w=AW, h=250, xr=(-0.6, N - 0.4), yr=(0, 6000), xlabel='每次调用前的睡眠时间（µs）',
            ylabel='每次调用的耗时（µs）', xticks=list(range(N)), xticklabels=labels,
            yticks=[0, 1000, 2000, 3000, 4000, 5000, 6000], title='(b) 每次调用的耗时与 NE 时钟档位')
# 档位底色
for i0, i1, txt, col in [(-0.5, 1.5, '最高档（2580 MHz）', PUR), (1.5, 2.5, '约 1032 MHz', BLU),
                         (2.5, N - 0.5, '下限 852 MHz', BLU)]:
    c.a(f'<rect x="{bx.X(i0) + 2:.1f}" y="{Y2 + 2}" width="{bx.X(i1) - bx.X(i0) - 4:.1f}" height="26" rx="3" fill="{col[1]}"/>')
    c.t((bx.X(i0) + bx.X(i1)) / 2, Y2 + 20, txt, 's', 'middle')
bx.line(list(range(N)), [t for _, _, t in pts], color=PUR, r=4)
for i, (s, w, t) in enumerate(pts):
    bx.text(i, t, f'{t:.0f}', 's', 'middle', dy=(16 + 6) if i == 1 else -12)
    if i >= 2:
        bx.text(i, t, f'×{t / pts[0][2]:.1f}', 'c', 'middle', dy=24)
c.save('fig13-2_energy_vs_level')
