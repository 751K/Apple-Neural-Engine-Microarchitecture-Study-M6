#!/usr/bin/env python3
# 图 12-2：CLPC 升频与降频的阶跃响应（第 12.3 节）。
# 数据：data/10_clpc/gov_step/tasks.txt（kdebug：61b0125 任务开始、61b0126 任务结束，mach tick 24 MHz）。
# 该次运行没有写出切换时刻文件 phases_*.txt（见 notes/scheduling.md H54 §7），切换时刻由任务间空闲反推：
#   相邻任务相隔 > 2 s 分成 A、B、C 三次运行（C 为长空闲后恢复，本图不用，见表 12-3）；
#   对任务间空闲取 9 点滑动中位数，A 组以 884 µs（≈ 384 µs + 500 µs）、B 组以 484 µs（≈ 384 µs + 100 µs）
#   为阈值区分"调用前睡眠"与"不睡眠"两段；越过阈值的第一个任务即切换时刻。B 组开头 0.2 s 内的几次误判（预热期抖动）丢弃。
#   结果：A 组 6 次 0→1000 µs（降频）、6 次 1000→0 µs（升频）；B 组 5 次 0→200 µs、5 次 200→0 µs，各段任务数与
#   gov_step.sh 中 BONDRUN_SLEEP_SEQ 的设定（A：270 / 900 次，B：440 / 900 次）一致。
# 档位按 T = C / f + D 换算（同 gov_fit.py）。细线为每次切换的档位轨迹，粗线为同一时刻各次轨迹的中位数（1 ms 网格）。
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figplot import Chart, COLORS  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
DT = [804, 828, 852, 960, 996, 1032, 1092, 1128, 1188, 1248, 1308, 1368, 1404, 1476, 1548, 1632,
      1716, 1788, 1872, 1908, 1968, 2052, 2112, 2196, 2280, 2352, 2364, 2436, 2448, 2484, 2508, 2580]
C, D = 1267.5 - 8.0, 8.0

st, en, cur = [], [], None
for l in open(os.path.join(ROOT, 'data/10_clpc/gov_step/tasks.txt')):
    t, i = l.split()
    t = int(t) / 24.0
    if i == '61b0125':
        cur = t
    elif i == '61b0126' and cur is not None:
        st.append(cur); en.append(t); cur = None
st, en = np.array(st), np.array(en)
DTa = np.array(DT)
f = C * 2580 / (en - st - D)
lv = DTa[np.abs(f[:, None] - DTa[None, :]).argmin(1)]
gap = np.r_[np.inf, st[1:] - en[:-1]]
runs = [k for k in range(len(st)) if gap[k] > 2e6] + [len(st)]


def medfilt(x, n=9):
    h = n // 2
    xp = np.r_[np.full(h, x[0]), x, np.full(h, x[-1])]
    return np.array([np.median(xp[k:k + n]) for k in range(len(x))])


def switches(a, b, thr, t_skip=0.2e6):
    g = gap[a:b].copy(); g[0] = 0
    hi = medfilt(g) > thr
    sw = [k for k in range(1, len(hi)) if hi[k] != hi[k - 1] and st[a + k] - st[a] > t_skip]
    out = []
    for j, k in enumerate(sw):
        e = sw[j + 1] if j + 1 < len(sw) else b - a
        out.append((bool(hi[k]), a + k, a + e))
    return out


TG = np.arange(0, 1201, 1.0)


def trace(k0, k1):
    t = (st[k0:k1] - st[k0]) / 1e3
    return t, lv[k0:k1]


def on_grid(t, L):
    idx = np.searchsorted(t, TG, side='right') - 1
    v = L[np.clip(idx, 0, None)].astype(float)
    v[TG > t[-1]] = np.nan
    return v


A = switches(runs[0], runs[1], 884)
B = switches(runs[1], runs[2], 484)
groups = {
    'Aup': [s for s in A if not s[0]], 'Adn': [s for s in A if s[0]],
    'Bdn': [s for s in B if s[0]], 'Bup': [s for s in B if not s[0]],
}
for k, v in groups.items():
    print(k, len(v), [k1 - k0 for _, k0, k1 in v])


def first(t, L, cond, n=3):
    return next((t[j] for j in range(len(L) - n) if all(cond(x) for x in L[j:j + n])), float('nan'))


for _, k0, k1 in groups['Aup']:
    t, L = trace(k0, k1)
    print(f"A 升频：≥2448 用时 {first(t, L, lambda x: x >= 2448):.0f} ms，2580 用时 {first(t, L, lambda x: x >= 2580):.0f} ms，"
          f"前 30 个任务空闲中位 {np.median(gap[k0 + 1:k0 + 30]):.0f} µs")
for _, k0, k1 in groups['Adn']:
    t, L = trace(k0, k1)
    print(f"A 降频：保持 ≥2448 {first(t, L, lambda x: x < 2448, 1):.0f} ms，到 852 用时 {first(t, L, lambda x: x <= 852, 1):.0f} ms")
for _, k0, k1 in groups['Bdn']:
    t, L = trace(k0, k1)
    print(f"B 降频：保持 ≥2448 {first(t, L, lambda x: x < 2448, 1):.0f} ms，段末一半中位 {np.median(L[len(L) // 2:]):.0f} MHz")
for _, k0, k1 in groups['Bup']:
    t, L = trace(k0, k1)
    print(f"B 升频：起点 {L[0]} MHz，≥2448 用时 {first(t, L, lambda x: x >= 2448):.0f} ms")

c = Chart(W=1100, H=800)
PW, PH = 440, 250
panels = [
    ('Aup', 90, 50, 300, 0, '（a）升频：G 由 1000 µs 切换为 0（6 次）'),
    ('Adn', 620, 50, 300, 1, '（b）降频：G 由 0 切换为 1000 µs（6 次）'),
    ('Bup', 90, 430, 300, 0, '（c）升频：G 由 200 µs 切换为 0（5 次）'),
    ('Bdn', 620, 430, 1200, 1, '（d）降频：G 由 0 切换为 200 µs（5 次）'),
]
yt = [852, 1188, 1548, 1872, 2196, 2580]
for key, x, y, xmax, col, title in panels:
    xt = [0, 50, 100, 150, 200, 250, 300] if xmax == 300 else [0, 200, 400, 600, 800, 1000, 1200]
    ax = c.axes(x, y + 20, PW, PH, (0, xmax), (700, 2700), xlabel='切换后的时间（ms）', ylabel='NE 时钟档位（MHz）',
                xticks=xt, yticks=yt)
    c.t(x, y, title, 'h2')
    ax.hline(2448)
    grid = []
    for j, (_, k0, k1) in enumerate(groups[key]):
        t, L = trace(k0, k1)
        m = t <= xmax
        light = ('#b9b9be', '#ffffff')
        ax.line(t[m], L[m], color=light, marker=False, width=1.0, step=True)
        grid.append(on_grid(t, L))
    med = np.nanmedian(np.array(grid), axis=0)
    if xmax > 300:  # 长时间轴上逐毫秒中位数抖动过密，再取 15 ms 滑动中位数
        med = medfilt(med, 15)
    m = TG <= xmax
    ax.line(TG[m], med[m], color=col, marker=False, width=2.6, step=True)
    if key == 'Aup':  # 第 1 次升频单独标出
        _, k0, k1 = groups[key][0]
        t, L = trace(k0, k1)
        mm = t <= xmax
        ax.line(t[mm], L[mm], color=2, marker=False, width=1.8, step=True, dash=True)

# 图例
lg = [('各次切换', '#b9b9be', 1.0, False), ('中位数（升频）', COLORS[0][0], 2.6, False),
      ('中位数（降频）', COLORS[1][0], 2.6, False), ('（a）中的第 1 次切换', COLORS[2][0], 1.8, True),
      ('2448 MHz', '#8e8e93', 1.2, True)]
lx = 70
for lab, s, w, dash in lg:
    c.a(f'<line x1="{lx}" y1="{772}" x2="{lx + 28}" y2="{772}" stroke="{s}" stroke-width="{w}"'
        + (' stroke-dasharray="6 4"' if dash else '') + '/>')
    c.t(lx + 36, 777, lab, 's')
    lx += 190
c.save('fig12-2_step_response')
