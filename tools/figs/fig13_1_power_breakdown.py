#!/usr/bin/env python3
# 图 13-1（第 13.2–13.3 节）：ANE 功耗的分解与每次运算能耗（统一样式见 plotfig.py）。
# 数据：data/11_power/power_parts4/、data/11_power/power_zero/。
import os
from plotfig import Plot, K, AXIS, C_BLUE, C_GREEN, C_GREY

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '11_power')
NK = 7


def measure(d, tag, base_from=None):
    path = os.path.join(ROOT, d, tag)
    rows = [list(map(float, l.split())) for l in open(path + '.trace') if l.strip()]
    ts, te = map(float, open(path + '.marks').read().split()[:2])
    br = open(path + '.bondrun.txt').read()
    med = float(br.split('中位数')[1].split()[0])

    def avg(a, b):
        sel = [r for r in rows if a <= r[0] <= b and len(r) == NK + 2]
        n = len(sel)
        diff = sum(r[2] - r[1] for r in sel) / n
        mem = sum(r[3] + r[4] for r in sel) / n
        return diff, mem

    st, mem = avg(ts + 4, te - 0.3)
    on, _ = avg(te + 1.2, te + 4.8)
    off, _ = avg(te + 7, te + 99)
    if base_from:
        off = measure(d, base_from)['off']
    return dict(st=st - off, on=on - off, off=off, mem=mem, med=med)


def mean2(d, tag):
    a, b = measure(d, tag), measure(d, tag + '_r2')
    return {k: (a[k] + b[k]) / 2 for k in a}


P4 = 'power_parts4'
f1, f2 = measure(P4, 'f16_single'), measure(P4, 'f16_dual')
q8, wb = measure(P4, 'q8_single'), measure(P4, 'weightbw')
pa = measure(P4, 'pe_add', base_from='pe_add_zero')
paz, pm = measure(P4, 'pe_add_zero'), measure(P4, 'pe_mul')
zr, zz = mean2('power_zero', 'b0_rand'), mean2('power_zero', 'b0_zero')

MAC384 = 512 * 512 * 128 * 384
r_f1 = MAC384 / f1['med'] * 1e6
r_f2 = 2 * MAC384 / f2['med'] * 1e6
r_q8 = MAC384 / q8['med'] * 1e6
r_wb = 512 * 512 * 2 * 192 / wb['med'] * 1e6
r_pa = 256 * 64 * 64 * 96 / pa['med'] * 1e6
r_pm = 256 * 64 * 64 * 64 / pm['med'] * 1e6
r_z = 512 * 512 * 128 * 128 / zr['med'] * 1e6

shared = 2 * f1['st'] - f2['st']
per_eng = f1['st'] - shared
q8_rest = q8['st'] - wb['st']
pj = lambda w, r: w / r * 1e12 + 1e-9
E = dict(
    f16=pj(f1['st'], r_f1), f16n=pj(per_eng, r_f1), f16d=pj(f2['st'], r_f2),
    q8=pj(q8['st'], r_q8), q8n=pj(q8_rest, r_q8),
    zr=pj(zr['st'], r_z), zz=pj(zz['st'], r_z),
    pa=pj(pa['st'] - pa['on'], r_pa), pm=pj(pm['st'] - pm['on'], r_pm),
    dram=pj(wb['st'] + wb['mem'], r_wb), dram_mem=pj(wb['mem'], r_wb), dram_ane=pj(wb['st'], r_wb))

MEM = ('#999999', '#f2f2f5')

p = Plot(800, 722)
p.panel(4, 8, 792, 388)
p.panel(4, 434, 792, 246)

X0, AW = 196, 580

# ---------- (a) 各类负载的 ANE 净功耗（收敛为 2 彩色 + 灰） ----------
RH, BH = 32, 18
rows = [
    ('单 ANE · FP16 卷积', [(0, shared, C_GREY), (shared, f1['st'], C_BLUE)], f1['mem'], f"{f1['st']:.2f} W"),
    ('双 ANE · FP16 卷积', [(0, shared, C_GREY), (shared, shared + per_eng, C_BLUE), (shared + per_eng, f2['st'], C_BLUE)], f2['mem'], f"{f2['st']:.2f} W"),
    ('单 ANE · W8A8 卷积', [(0, wb['st'], C_GREEN), (wb['st'], q8['st'], C_BLUE)], q8['mem'], f"{q8['st']:.2f} W"),
    ('单 ANE · 读权重受限', [(0, wb['st'], C_GREEN)], wb['mem'], f"{wb['st']:.2f} W"),
    ('双 ANE · PE 加（随机）', [(0, pa['st'], C_BLUE)], pa['mem'], f"{pa['st']:.2f} W"),
    ('双 ANE · PE 加（全 0）', [(0, paz['st'], C_BLUE)], paz['mem'], f"{paz['st']:.2f} W (−{(1 - paz['st'] / pa['st']) * 100:.0f}%)"),
    ('双 ANE · PE 乘', [(0, pm['st'], C_BLUE)], pm['mem'], f"{pm['st']:.2f} W"),
    ('单 ANE · 卷积（随机）', [(0, zr['st'], C_BLUE)], zr['mem'], f"{zr['st']:.2f} W"),
    ('单 ANE · 卷积（全 0）', [(0, zz['st'], C_BLUE)], zz['mem'], f"{zz['st']:.2f} W (−{(1 - zz['st'] / zr['st']) * 100:.0f}%)"),
]
ax = p.axes(x=X0, y=46, w=AW, h=len(rows) * RH, xr=(0, 14), yr=(0, 1),
            xticks=list(range(0, 15, 2)), yticks=[], xgrid=True, ygrid=False,
            xlabel='功耗 (W)', title='(a) 各类负载的 ANE 净功耗', title_x=18)

for i, (lab, segs, mem, note) in enumerate(rows):
    yc = 46 + i * RH + RH / 2
    p.text(X0 - 12, yc + 4.5, lab, 13, K, 'end', 400)
    end = 0
    for a0, a1, (s, f) in segs:
        p.raw(f'<rect x="{ax.X(a0):.1f}" y="{yc - BH / 2:.1f}" width="{ax.X(a1) - ax.X(a0):.1f}" height="{BH}" '
              f'fill="{f}" stroke="{AXIS}" stroke-width="0.9"/>')
        end = a1
    p.raw(f'<rect x="{ax.X(end):.1f}" y="{yc - BH / 2 + 3:.1f}" width="{ax.X(end + mem) - ax.X(end):.1f}" height="{BH - 6}" '
          f'fill="{MEM[1]}" stroke="{MEM[0]}" stroke-width="1" stroke-dasharray="3 2"/>')
    p.text(ax.X(end + mem) + 8, yc + 4.5, note, 13, K, 'start', 600)

# (a) 精简 4 项白底居中图例
leg_a = [
    (C_GREY, False, '共用开销'),
    (C_BLUE, False, '计算（NE / PE）'),
    (C_GREEN, False, '读权重（含共用）'),
    (MEM, True, '内存电源轨'),
]
parts_a = []
for (s, f), dash, lb in leg_a:
    da = ' stroke-dasharray="3 2"' if dash else ''
    st_col = s if dash else AXIS
    ic = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="14" viewBox="0 0 16 14"><rect x="1" y="2" width="14" height="10" rx="1.5" fill="{f}" stroke="{st_col}" stroke-width="1"{da}/></svg>'
    parts_a.append(f'<span style="display:flex;align-items:center;gap:6px">{ic}<span>{lb}</span></span>')
p.raw(f'<foreignObject x="0" y="401" width="800" height="28"><div xmlns="http://www.w3.org/1999/xhtml" '
      f'style="display:flex;justify-content:center;gap:32px;align-items:center;height:28px;'
      f'font-family:Arial,\'Helvetica Neue\',\'PingFang SC\',sans-serif;font-size:13px;color:{K}">'
      + ''.join(parts_a) + '</div></foreignObject>')

# ---------- (b) 每次运算能耗（同样收敛为钢蓝计算 + 橄榄绿访存） ----------
RH2 = 29
erows = [
    ('FP16 乘加', E['f16'], E['f16n'], C_BLUE, f"{E['f16n']:.2f} / {E['f16']:.2f}"),
    ('INT8 乘加（W8A8）', E['q8'], E['q8n'], C_BLUE, f"{E['q8n']:.2f} / {E['q8']:.2f}"),
    ('FP16 乘加（全 0 / 随机）', E['zr'], E['zz'], C_BLUE, f"{E['zz']:.2f} / {E['zr']:.2f}"),
    ('读取 DRAM（每字节）', E['dram'], E['dram_ane'], C_GREEN, f"{E['dram_ane']:.0f} / {E['dram']:.0f}"),
    ('PE 逐元素加 / 乘', E['pa'], E['pm'], C_BLUE, f"{E['pa']:.0f} / {E['pm']:.0f}"),
]
bx = p.axes(x=X0, y=472, w=AW, h=len(erows) * RH2, xr=(0.1, 300), yr=(0, 1), xlog=True,
            xticks=[0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200], yticks=[],
            xgrid=True, ygrid=False, xlabel='每次运算能耗 (pJ)',
            title='(b) 每次运算能耗', title_x=18)

for i, (lab, v0, v1, (s, _), note) in enumerate(erows):
    yc = 472 + i * RH2 + RH2 / 2
    p.text(X0 - 12, yc + 4.5, lab, 13, K, 'end', 400)
    xa, xb = bx.X(v0), bx.X(v1)
    p.raw(f'<line x1="{min(xa, xb):.1f}" y1="{yc:.1f}" x2="{max(xa, xb):.1f}" y2="{yc:.1f}" stroke="{s}" stroke-width="2"/>')
    if i == 4:
        for xx in (xa, xb):
            p.raw(f'<circle cx="{xx:.1f}" cy="{yc:.1f}" r="4.8" fill="{s}"/>')
    else:
        p.raw(f'<circle cx="{xb:.1f}" cy="{yc:.1f}" r="4.8" fill="#ffffff" stroke="{s}" stroke-width="2"/>')
        p.raw(f'<circle cx="{xa:.1f}" cy="{yc:.1f}" r="4.8" fill="{s}"/>')
    p.text(max(xa, xb) + 10, yc + 4.5, note, 13, s, 'start', 600)

# (b) 居中图例（白底）
parts_b = [
    '<span style="display:flex;align-items:center;gap:6px"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="4.5" fill="#444444"/></svg><span>实测总能耗 / 速率</span></span>',
    '<span style="display:flex;align-items:center;gap:6px"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="4.5" fill="#ffffff" stroke="#444444" stroke-width="2"/></svg><span>扣除共用 / 全 0 / ANE 部分</span></span>',
]
p.raw(f'<foreignObject x="0" y="688" width="800" height="28"><div xmlns="http://www.w3.org/1999/xhtml" '
      f'style="display:flex;justify-content:center;gap:36px;align-items:center;height:28px;'
      f'font-family:Arial,\'Helvetica Neue\',\'PingFang SC\',sans-serif;font-size:13px;color:{K}">'
      + ''.join(parts_b) + '</div></foreignObject>')

print(p.save('fig13-1_power_breakdown'))
