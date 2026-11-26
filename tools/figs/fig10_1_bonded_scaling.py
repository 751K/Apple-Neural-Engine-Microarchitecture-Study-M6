#!/usr/bin/env python3
# 图 10-1：单 ANE（宽 128）与双 ANE（宽 256）程序的耗时随层数的变化与边际吞吐对比（第 10.3 节，表 10-1，统一样式见 plotfig.py）。
# 数据：data/08_bonded/bond_ksweep_run.txt。
import os
import re
from collections import defaultdict
from plotfig import Plot, K, C_BLUE, C_GREEN, C_RED

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
pat = re.compile(r'k1x1_512_h1w(\d+)_L(\d+)\.mlmodelc\s+耗时 中位数 ([\d.]+) us')
runs = defaultdict(list)
for line in open(os.path.join(ROOT, 'data/08_bonded/bond_ksweep_run.txt')):
    m = pat.search(line)
    if m:
        runs[(int(m[1]), int(m[2]))].append(float(m[3]))
med = {k: sum(v) / len(v) for k, v in runs.items()}
LS = sorted({L for _, L in med})


def slope(w):
    return (med[(w, 384)] - med[(w, 256)]) / 128


s1, s2 = slope(128), slope(256)
tf1 = 2 * 512 * 512 * 128 / (s1 * 1e-6) / 1e12
tf2 = 2 * 512 * 512 * 256 / (s2 * 1e-6) / 1e12
sp = tf2 / tf1

p = Plot(800, 412)
p.panel(4, 8, 478, 360)
p.panel(494, 8, 302, 360)

# (a) 调用耗时随层数变化
ax1 = p.axes(x=86, y=50, w=380, h=256, xr=(0, 405), yr=(0, 2000),
             xlabel='层数', ylabel='调用耗时 (µs)',
             xticks=[0, 48, 128, 256, 384], yticks=[0, 400, 800, 1200, 1600, 2000],
             title='(a) 调用耗时', title_x=18)

ax1.line(LS, [med[(256, L)] for L in LS], color=C_BLUE, marker='o', width=2.4, r=4.4)
ax1.line(LS, [med[(128, L)] for L in LS], color=C_GREEN, marker='o', width=2.4, r=4.4)

# (b) 边际吞吐对比（256–384 层）
ax2 = p.axes(x=568, y=50, w=210, h=256, xr=(0.25, 2.75), yr=(0, 50),
             xticks=[1, 2], xticklabels=['单 ANE', '双 ANE'],
             yticks=[0, 10, 20, 30, 40, 50],
             ylabel='边际吞吐 (TFLOPS)', title='(b) 边际吞吐', title_x=508)

ax2.bars([1], [tf1], color=C_GREEN, width=54)
ax2.bars([2], [tf2], color=C_BLUE, width=54)

ax2.text(1, tf1, f'{tf1:.1f}', 14, C_GREEN[0], 'middle', 700, dy=-8)
ax2.text(2, tf2, f'{tf2:.1f}', 14, C_BLUE[0], 'middle', 700, dy=-8)

# 仅保留核心加速比数字 + 箭头
ax2.text(1.05, 41.0, f'{sp:.2f}×', 16.5, C_RED[0], 'middle', 700)
ax2.arrow((1.16, 26.8), (1.64, 38.8), color=C_RED, sw=1.6, pad0=2, pad1=4)

# 底部白底居中图例
ly = 392
items = [
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="26" height="14" viewBox="0 0 26 14"><line x1="0" y1="7" x2="26" y2="7" stroke="{C_BLUE[0]}" stroke-width="2.4"/><circle cx="13" cy="7" r="4" fill="#ffffff" stroke="{C_BLUE[0]}" stroke-width="2"/></svg>', '双 ANE（2× 计算量）'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="26" height="14" viewBox="0 0 26 14"><line x1="0" y1="7" x2="26" y2="7" stroke="{C_GREEN[0]}" stroke-width="2.4"/><circle cx="13" cy="7" r="4" fill="#ffffff" stroke="{C_GREEN[0]}" stroke-width="2"/></svg>', '单 ANE'),
]
parts = [f'<span style="display:flex;align-items:center;gap:7px">{ic}<span>{lb}</span></span>' for ic, lb in items]
p.raw(f'<foreignObject x="0" y="{ly - 14}" width="800" height="28"><div xmlns="http://www.w3.org/1999/xhtml" '
      f'style="display:flex;justify-content:center;gap:40px;align-items:center;height:28px;'
      f'font-family:Arial,\'Helvetica Neue\',\'PingFang SC\',sans-serif;font-size:13.5px;color:{K}">'
      + ''.join(parts) + '</div></foreignObject>')

print(p.save('fig10-1_bonded_scaling'))
