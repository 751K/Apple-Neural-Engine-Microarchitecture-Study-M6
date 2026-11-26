#!/usr/bin/env python3
# 图 12-1：不同睡眠时间 G 下 ANE 的档位分布与忙碌比例（第 12.2 节，表 12-2，统一样式见 plotfig.py）。
# 数据：data/10_clpc/gov_kt/tasks.txt。
import os
import statistics
from collections import Counter
from plotfig import Plot, K, C_BLUE, C_GREEN, C_ORANGE

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
DT = [804, 828, 852, 960, 996, 1032, 1092, 1128, 1188, 1248, 1308, 1368, 1404, 1476, 1548, 1632,
      1716, 1788, 1872, 1908, 1968, 2052, 2112, 2196, 2280, 2352, 2364, 2436, 2448, 2484, 2508, 2580]
C, D = 1267.5 - 8.0, 8.0
GS = [0, 100, 150, 200, 300, 400, 1000, 3000]
SKIP = 2.0

st, en, cur = [], [], None
for l in open(os.path.join(ROOT, 'data/10_clpc/gov_kt/tasks.txt')):
    parts = l.split()
    if len(parts) < 2:
        continue
    t, code = int(parts[0]) / 24.0, parts[1]
    if code == '61b0125':
        cur = t
    elif code == '61b0126' and cur is not None:
        st.append(cur)
        en.append(t)
        cur = None

cuts = [0] + [k for k in range(1, len(st)) if st[k] - en[k - 1] > 2e6] + [len(st)]


def mhz(dur):
    f = C * 2580 / (dur - D)
    return min(DT, key=lambda x: abs(x - f))


rows = []
for r in range(len(cuts) - 1):
    s_seg = st[cuts[r]:cuts[r + 1]]
    e_seg = en[cuts[r]:cuts[r + 1]]
    t_cut = s_seg[0] + SKIP * 1e6
    kept = [(s, e) for s, e in zip(s_seg, e_seg) if s >= t_cut]
    if len(kept) < 20:
        continue
    lv = [mhz(e - s) for s, e in kept]
    cnt = Counter(lv)
    tot = len(lv)
    busy = sum(e - s for s, e in kept) / (kept[-1][1] - kept[0][0])
    rows.append(dict(G=GS[r], med=float(statistics.median(lv)),
                     dist={k: v / tot for k, v in cnt.items()}, busy=busy))

n = len(rows)
xt = list(range(n))
xl = [str(q['G']) for q in rows]

p = Plot(800, 570)
p.panel(4, 8, 792, 286)
p.panel(4, 304, 792, 224)

X0, W0 = 92, 680

# (a) 各睡眠时间下的档位分布
ax = p.axes(x=X0, y=48, w=W0, h=212, xr=(-0.5, n - 0.5), yr=(660, 2780),
            ylabel='NE 时钟 (MHz)', yticks=[852, 1200, 1548, 1872, 2196, 2580],
            xticks=xt, xticklabels=xl,
            title='(a) NE 时钟档位分布', title_x=18)
ax.hline(2580, color='#b8b8c0', dash='4 3', sw=1.0)
ax.hline(852, color='#b8b8c0', dash='4 3', sw=1.0)
for xv in (1.5, 5.5):
    ax.vline(xv, color='#b8b8c0', dash='4 3', sw=1.0)

for k, q in enumerate(rows):
    for f, frac in q['dist'].items():
        if frac < 0.01:
            continue
        rad = 2.0 + 16.5 * (frac ** 0.5)
        p.raw(f'<circle cx="{ax.X(k):.1f}" cy="{ax.Y(f):.1f}" r="{rad:.1f}" '
              f'fill="{C_BLUE[1]}" stroke="{C_BLUE[0]}" stroke-width="1.1" opacity="0.82"/>')

ax.line(xt, [q['med'] for q in rows], color=C_GREEN, marker='o', width=2.4, r=4.2)

# (b) ANE 忙碌比例
ax2 = p.axes(x=X0, y=344, w=W0, h=124, xr=(-0.5, n - 0.5), yr=(50, 90),
             xlabel='调用前睡眠时间 G (µs)', ylabel='忙碌比例 (%)',
             yticks=[50, 60, 70, 80, 90], xticks=xt, xticklabels=xl,
             title='(b) ANE 忙碌比例', title_x=18)
for xv in (1.5, 5.5):
    ax2.vline(xv, color='#b8b8c0', dash='4 3', sw=1.0)

lo, hi = ax2.Y(78), ax2.Y(76)
p.raw(f'<rect x="{X0}" y="{lo:.1f}" width="{W0}" height="{hi - lo:.1f}" fill="{C_ORANGE[1]}" opacity="0.7"/>')
ax2.hline(77, color=C_ORANGE[0], dash='4 3', sw=1.2)
ax2.text(6.0, 82.5, '≈ 77%', 13.5, C_ORANGE[0], 'middle', 600)
ax2.line(xt, [q['busy'] * 100 for q in rows], color=C_BLUE, marker='o', width=2.4, r=4.2)

# 底部白底居中图例
ly = 550
items = [
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="42" height="20" viewBox="0 0 42 20">'
     f'<circle cx="5" cy="10" r="3" fill="{C_BLUE[1]}" stroke="{C_BLUE[0]}" stroke-width="1.1"/>'
     f'<circle cx="16" cy="10" r="5" fill="{C_BLUE[1]}" stroke="{C_BLUE[0]}" stroke-width="1.1"/>'
     f'<circle cx="31" cy="10" r="7.5" fill="{C_BLUE[1]}" stroke="{C_BLUE[0]}" stroke-width="1.1"/></svg>', '圆面积：档位占比'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="26" height="14" viewBox="0 0 26 14"><line x1="0" y1="7" x2="26" y2="7" stroke="{C_GREEN[0]}" stroke-width="2.4"/><circle cx="13" cy="7" r="4" fill="#ffffff" stroke="{C_GREEN[0]}" stroke-width="2"/></svg>', '档位中位数'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="26" height="14" viewBox="0 0 26 14"><line x1="0" y1="7" x2="26" y2="7" stroke="{C_BLUE[0]}" stroke-width="2.4"/><circle cx="13" cy="7" r="4" fill="#ffffff" stroke="{C_BLUE[0]}" stroke-width="2"/></svg>', '忙碌比例'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="26" height="14" viewBox="0 0 26 14"><line x1="0" y1="7" x2="26" y2="7" stroke="{C_ORANGE[0]}" stroke-width="1.6" stroke-dasharray="4 3"/></svg>', '目标区间'),
]
parts = [f'<span style="display:flex;align-items:center;gap:7px">{ic}<span>{lb}</span></span>' for ic, lb in items]
p.raw(f'<foreignObject x="0" y="{ly - 14}" width="800" height="28"><div xmlns="http://www.w3.org/1999/xhtml" '
      f'style="display:flex;justify-content:center;gap:30px;align-items:center;height:28px;'
      f'font-family:Arial,\'Helvetica Neue\',\'PingFang SC\',sans-serif;font-size:13.5px;color:{K}">'
      + ''.join(parts) + '</div></foreignObject>')

print(p.save('fig12-1_utilization_target'))
