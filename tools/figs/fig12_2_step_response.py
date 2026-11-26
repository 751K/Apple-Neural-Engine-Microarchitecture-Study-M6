#!/usr/bin/env python3
# 图 12-2：CLPC 升频与降频的阶跃响应（第 12.3 节，统一样式见 plotfig.py）。
# 数据：data/10_clpc/gov_step/tasks.txt。
import bisect
import math
import os
import statistics
from plotfig import Plot, K, C_BLUE, C_GREEN, C_ORANGE

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
DT = [804, 828, 852, 960, 996, 1032, 1092, 1128, 1188, 1248, 1308, 1368, 1404, 1476, 1548, 1632,
      1716, 1788, 1872, 1908, 1968, 2052, 2112, 2196, 2280, 2352, 2364, 2436, 2448, 2484, 2508, 2580]
C, D = 1267.5 - 8.0, 8.0

st, en, cur = [], [], None
for l in open(os.path.join(ROOT, 'data/10_clpc/gov_step/tasks.txt')):
    t_s, code = l.split()
    t = int(t_s) / 24.0
    if code == '61b0125':
        cur = t
    elif code == '61b0126' and cur is not None:
        st.append(cur)
        en.append(t)
        cur = None


def nearest_dt(dur):
    f = C * 2580 / (dur - D)
    return min(DT, key=lambda x: abs(x - f))


lv = [nearest_dt(e - s) for s, e in zip(st, en)]
gap = [math.inf] + [st[k] - en[k - 1] for k in range(1, len(st))]
runs = [k for k in range(len(st)) if gap[k] > 2e6] + [len(st)]


def medfilt(x, n=9):
    h = n // 2
    xp = [x[0]] * h + list(x) + [x[-1]] * h
    return [statistics.median(xp[k:k + n]) for k in range(len(x))]


def switches(a, b, thr, t_skip=0.2e6):
    g = [0.0] + gap[a + 1:b]
    hi = [v > thr for v in medfilt(g)]
    sw = [k for k in range(1, len(hi)) if hi[k] != hi[k - 1] and st[a + k] - st[a] > t_skip]
    out = []
    for j, k in enumerate(sw):
        e = sw[j + 1] if j + 1 < len(sw) else b - a
        out.append((bool(hi[k]), a + k, a + e))
    return out


TG = [float(i) for i in range(1201)]


def trace(k0, k1):
    t0 = st[k0]
    return [(s - t0) / 1e3 for s in st[k0:k1]], lv[k0:k1]


def on_grid(t, L):
    out = []
    tmax = t[-1]
    for tv in TG:
        if tv > tmax:
            out.append(None)
        else:
            idx = bisect.bisect_right(t, tv) - 1
            out.append(float(L[max(0, idx)]))
    return out


A = switches(runs[0], runs[1], 884)
B = switches(runs[1], runs[2], 484)
groups = {
    'Aup': [s for s in A if not s[0]],
    'Adn': [s for s in A if s[0]],
    'Bdn': [s for s in B if s[0]],
    'Bup': [s for s in B if not s[0]],
}

p = Plot(800, 640)
# 2×2 独立浅灰圆角底板
p.panel(4, 8, 390, 276)
p.panel(406, 8, 390, 276)
p.panel(4, 294, 390, 302)
p.panel(406, 294, 390, 302)

panels = [
    ('Aup', 82, 46, 18, 300, C_BLUE, '(a) 升频：G 1000 → 0 µs', True, False),
    ('Adn', 482, 46, 420, 300, C_GREEN, '(b) 降频：G 0 → 1000 µs', False, False),
    ('Bup', 82, 332, 18, 300, C_BLUE, '(c) 升频：G 200 → 0 µs', True, True),
    ('Bdn', 482, 332, 420, 1200, C_GREEN, '(d) 降频：G 0 → 200 µs', False, True),
]
YT = [852, 1188, 1548, 1872, 2196, 2580]

for key, ax_x, ax_y, tx, xmax, col, title, show_yl, show_xl in panels:
    xt = [0, 100, 200, 300] if xmax == 300 else [0, 400, 800, 1200]
    ax = p.axes(x=ax_x, y=ax_y, w=298, h=202, xr=(0, xmax), yr=(700, 2700),
                xticks=xt, yticks=YT,
                xlabel='切换后时间 (ms)' if show_xl else None,
                ylabel='NE 时钟 (MHz)' if show_yl else None,
                title=title, title_x=tx)
    ax.hline(2448, color='#888888', dash='4 3', sw=1.1)

    grid = []
    for _, k0, k1 in groups[key]:
        t, L = trace(k0, k1)
        pts = [(tv, lv_) for tv, lv_ in zip(t, L) if tv <= xmax]
        ax.line([a for a, _ in pts], [b for _, b in pts],
                color=('#c0c0c6', '#ffffff'), marker=None, width=1.0, step=True)
        grid.append(on_grid(t, L))

    med = []
    for i in range(len(TG)):
        vals = [g[i] for g in grid if g[i] is not None]
        med.append(statistics.median(vals) if vals else None)
    # 仅在有效区间内做 15 ms 平滑（xmax > 300）
    valid_i = [i for i, v in enumerate(med) if v is not None and TG[i] <= xmax]
    m_xs = [TG[i] for i in valid_i]
    m_ys = [med[i] for i in valid_i]
    if xmax > 300:
        m_ys = medfilt(m_ys, 15)
    ax.line(m_xs, m_ys, color=col, marker=None, width=2.4, step=True)

    if key == 'Aup':
        _, k0, k1 = groups[key][0]
        t, L = trace(k0, k1)
        pts = [(tv, lv_) for tv, lv_ in zip(t, L) if tv <= xmax]
        ax.line([a for a, _ in pts], [b for _, b in pts],
                color=C_ORANGE, marker=None, width=1.8, step=True, dash='5 4')

# 底部白底居中图例
ly = 620
items = [
    ('<svg xmlns="http://www.w3.org/2000/svg" width="22" height="14" viewBox="0 0 22 14"><line x1="0" y1="7" x2="22" y2="7" stroke="#b5b5bc" stroke-width="1.2"/></svg>', '各次切换'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="22" height="14" viewBox="0 0 22 14"><line x1="0" y1="7" x2="22" y2="7" stroke="{C_BLUE[0]}" stroke-width="2.4"/></svg>', '中位数（升频）'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="22" height="14" viewBox="0 0 22 14"><line x1="0" y1="7" x2="22" y2="7" stroke="{C_GREEN[0]}" stroke-width="2.4"/></svg>', '中位数（降频）'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="22" height="14" viewBox="0 0 22 14"><line x1="0" y1="7" x2="22" y2="7" stroke="{C_ORANGE[0]}" stroke-width="1.8" stroke-dasharray="4 3"/></svg>', '(a) 首次切换'),
    ('<svg xmlns="http://www.w3.org/2000/svg" width="22" height="14" viewBox="0 0 22 14"><line x1="0" y1="7" x2="22" y2="7" stroke="#888888" stroke-width="1.2" stroke-dasharray="4 3"/></svg>', '2448 MHz'),
]
parts = [f'<span style="display:flex;align-items:center;gap:6px">{ic}<span>{lb}</span></span>' for ic, lb in items]
p.raw(f'<foreignObject x="0" y="{ly - 14}" width="800" height="28"><div xmlns="http://www.w3.org/1999/xhtml" '
      f'style="display:flex;justify-content:center;gap:24px;align-items:center;height:28px;'
      f'font-family:Arial,\'Helvetica Neue\',\'PingFang SC\',sans-serif;font-size:13px;color:{K}">'
      + ''.join(parts) + '</div></foreignObject>')

print(p.save('fig12-2_step_response'))
