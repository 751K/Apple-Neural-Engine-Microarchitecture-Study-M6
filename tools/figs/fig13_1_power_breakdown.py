#!/usr/bin/env python3
# 图 13-1（第 13.2–13.3 节）：ANE 功耗的分解。
#   (a) 各类负载的 ANE 净功耗（PP0b − PACC0 簇 − 断电时的同一差值），右侧浅灰为同时段内存电源轨（PP2b + PP4b）；
#       FP16 卷积一行按"双 ANE 比单 ANE 两倍少出的部分 = 共用开销"拆成共用开销与每个 ANE 的计算部分；
#       W8A8 一行拆成同速读权重负载的功耗（其中已含共用开销）与其余部分（第 13.3 节的扣除方法）。
#   (b) 由差值推算的每次运算能耗（对数坐标）：实心点为 ANE 净功耗 / 有效速率，空心点为再扣除共用开销后的值。
# 数据：data/11_power/power_parts4/（第 4 轮，扣除 CPU 簇），data/11_power/power_zero/（偏置为 0 的 1×1 卷积链，两轮平均）。
# 处理：时间窗与功耗算法同 tools/11_power/power_parts_fit.py（稳态 = 开始后 4 s 至结束前 0.3 s；上电空闲 = 结束后
#   1.2–4.8 s；断电 = 结束后 7 s 以后）。power_parts4/pe_add 的断电基线异常（−1.71 W），按紧邻的 pe_add_zero 运行的
#   正常基线修正（第 13.3 节，修正后约 2.46 W）；每元素能耗用"稳态 − 上电空闲"，两者共用基线，不受影响。
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figplot import Chart, COLORS, FG2, FG3, AXIS  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '11_power')
NK = 7  # PP0b PP2b PP4b PZD1 PSTR PPSR PHPC


def measure(d, tag, base_from=None):
    """返回 dict(st, on, off, mem, med)：st/on 为 ANE 净功耗（W），mem 为内存电源轨，med 为中位耗时（µs）。"""
    p = os.path.join(ROOT, d, tag)
    rows = [list(map(float, l.split())) for l in open(p + '.trace') if l.strip()]
    ts, te = map(float, open(p + '.marks').read().split()[:2])
    br = open(p + '.bondrun.txt').read()
    med = float(br.split('中位数')[1].split()[0])

    def avg(a, b):
        sel = [r for r in rows if a <= r[0] <= b and len(r) == NK + 2]
        n = len(sel)
        diff = sum(r[2] - r[1] for r in sel) / n          # PP0b − PACC0 簇
        mem = sum(r[3] + r[4] for r in sel) / n           # PP2b + PP4b
        return diff, mem
    st, mem = avg(ts + 4, te - 0.3)
    on, _ = avg(te + 1.2, te + 4.8)
    off, _ = avg(te + 7, te + 99)
    if base_from:  # 用另一次运行的断电基线
        off = measure(d, base_from)['off']
    return dict(st=st - off, on=on - off, off=off, mem=mem, med=med)


def mean2(d, tag):
    a, b = measure(d, tag), measure(d, tag + '_r2')
    return {k: (a[k] + b[k]) / 2 for k in a}


P4 = 'power_parts4'
f1, f2 = measure(P4, 'f16_single'), measure(P4, 'f16_dual')
q8, wb = measure(P4, 'q8_single'), measure(P4, 'weightbw')
pa_raw = measure(P4, 'pe_add')
pa = measure(P4, 'pe_add', base_from='pe_add_zero')
paz, pm = measure(P4, 'pe_add_zero'), measure(P4, 'pe_mul')
zr, zz = mean2('power_zero', 'b0_rand'), mean2('power_zero', 'b0_zero')

# 每次调用的工作量（同 power_parts_fit.py 的 WORK 表；b0_* 为 512 通道、1×128、128 层的 1×1 卷积链）
MAC384 = 512 * 512 * 128 * 384
r_f1 = MAC384 / f1['med'] * 1e6
r_f2 = 2 * MAC384 / f2['med'] * 1e6
r_q8 = MAC384 / q8['med'] * 1e6
r_wb = 512 * 512 * 2 * 192 / wb['med'] * 1e6          # 字节/s
r_pa = 256 * 64 * 64 * 96 / pa['med'] * 1e6
r_pm = 256 * 64 * 64 * 64 / pm['med'] * 1e6
r_z = 512 * 512 * 128 * 128 / zr['med'] * 1e6

shared = 2 * f1['st'] - f2['st']                      # 两个 ANE 共用的开销
per_eng = f1['st'] - shared
q8_rest = q8['st'] - wb['st']
pj = lambda w, r: w / r * 1e12 + 1e-9  # +1e-9：0.795 等按四舍五入显示
E = dict(
    f16=pj(f1['st'], r_f1), f16n=pj(per_eng, r_f1), f16d=pj(f2['st'], r_f2),
    q8=pj(q8['st'], r_q8), q8n=pj(q8_rest, r_q8),   # 读权重负载中已含共用开销，相减后不再扣
    zr=pj(zr['st'], r_z), zz=pj(zz['st'], r_z),
    pa=pj(pa['st'] - pa['on'], r_pa), pm=pj(pm['st'] - pm['on'], r_pm),
    dram=pj(wb['st'] + wb['mem'], r_wb), dram_mem=pj(wb['mem'], r_wb), dram_ane=pj(wb['st'], r_wb))
print(f"shared {shared:.2f} W, per engine {per_eng:.2f} W, pe_add {pa_raw['st']:.2f} -> {pa['st']:.2f} W")
print({k: round(v, 3) for k, v in E.items()})

PUR, BLU, ORA, GRN, RED, GRY = COLORS
SHARED = ('#6e6e73', '#e2e2e6')
MEM = ('#b8b8bd', '#f4f4f6')

W, H = 1100, 1060
c = Chart(W, H)

# ---------- (a) 各负载的 ANE 净功耗 ----------
X0, AW = 330, 600
ax = c.axes(x=X0, y=58, w=AW, h=520, xr=(0, 14), yr=(0, 1), xlabel='功耗（W）',
            xticks=list(range(0, 15, 2)), yticks=[], grid=False, title='(a) 各类负载的 ANE 净功耗')
for v in range(2, 15, 2):
    c.a(f'<line x1="{ax.X(v):.1f}" y1="58" x2="{ax.X(v):.1f}" y2="578" stroke="#e5e5ea" stroke-width="1"/>')

rows = [  # (标签, 副标签, [(起, 止, 颜色, 段内文字)], 内存电源轨, 右侧注)
    ('单 ANE，FP16 卷积', '384 层，共享权重', [(0, shared, SHARED, '共用'), (shared, f1['st'], PUR, 'ANE0 计算')], f1['mem'],
     f"{f1['st']:.2f} W"),
    ('双 ANE，FP16 卷积', '384 层，共享权重', [(0, shared, SHARED, '共用'), (shared, shared + per_eng, PUR, 'ANE0 计算'),
                                     (shared + per_eng, f2['st'], BLU, 'ANE1 计算')], f2['mem'], f"{f2['st']:.2f} W"),
    ('单 ANE，W8A8 卷积', '每次读 100 MB 权重', [(0, wb['st'], ORA, '读权重＋共用'), (wb['st'], q8['st'], GRN, 'INT8 计算')],
     q8['mem'], f"{q8['st']:.2f} W"),
    ('单 ANE，读权重受限', '每次 100 MB，96.6 GB/s', [(0, wb['st'], ORA, '')], wb['mem'], f"{wb['st']:.2f} W"),
    ('双 ANE，PE 逐元素加', '数据在 L2 内，随机输入', [(0, pa['st'], RED, '')], pa['mem'], f"{pa['st']:.2f} W"),
    ('　同上，输入全为 0', '', [(0, paz['st'], RED, '')], paz['mem'], f"{paz['st']:.2f} W（−{(1 - paz['st'] / pa['st']) * 100:.0f}%）"),
    ('双 ANE，PE 逐元素乘', '', [(0, pm['st'], RED, '')], pm['mem'], f"{pm['st']:.2f} W"),
    ('单 ANE，1×1 卷积链', '偏置为 0，128 层，随机输入', [(0, zr['st'], PUR, '')], zr['mem'], f"{zr['st']:.2f} W"),
    ('　同上，输入全为 0', '每一层的输入都为 0', [(0, zz['st'], PUR, '')], zz['mem'],
     f"{zz['st']:.2f} W（−{(1 - zz['st'] / zr['st']) * 100:.0f}%）"),
]
RH, BH = 56, 26
for i, (lab, sub, segs, mem, note) in enumerate(rows):
    yc = 58 + 22 + i * RH + BH / 2
    c.t(X0 - 14, yc + (-2 if sub else 5), lab, 'b', 'end')
    if sub:
        c.t(X0 - 14, yc + 15, sub, 'c', 'end')
    end = 0
    for a0, a1, (s, f), txt in segs:
        c.a(f'<rect x="{ax.X(a0):.1f}" y="{yc - BH / 2:.1f}" width="{ax.X(a1) - ax.X(a0):.1f}" height="{BH}" fill="{f}" stroke="{s}" stroke-width="1.3"/>')
        if txt:
            c.t((ax.X(a0) + ax.X(a1)) / 2, yc + 4.5, txt, 's', 'middle')
        end = a1
    # 内存电源轨：接在 ANE 净功耗之后的浅色段（另一条电源轨，不属于 ANE 净功耗）
    c.a(f'<rect x="{ax.X(end):.1f}" y="{yc - BH / 2 + 4:.1f}" width="{ax.X(end + mem) - ax.X(end):.1f}" height="{BH - 8}" fill="{MEM[1]}" stroke="{MEM[0]}" stroke-width="1" stroke-dasharray="3 2"/>')
    c.t(ax.X(end + mem) + 8, yc + 4.5, note, 's')
# 共用开销的标注
y2 = 58 + 22 + RH + BH / 2
c.t(ax.X(f2['st'] + f2['mem']) + 8, y2 + 22, f'共用开销 = 2 × {f1["st"]:.2f} − {f2["st"]:.2f} ≈ {shared:.1f} W', 'c')
# 图例
ly = 58 + 520 + 76
for k, (lab, (s, f), dash) in enumerate([('两个 ANE 共用的开销', SHARED, False), ('ANE0', PUR, False), ('ANE1', BLU, False),
                                         ('读取 DRAM 权重', ORA, False), ('PE 逐元素运算', RED, False),
                                         ('内存电源轨（另一路，不计入 ANE）', MEM, True)]):
    lx = X0 - 200 + [0, 160, 230, 300, 430, 570][k]
    c.a(f'<rect x="{lx}" y="{ly - 11}" width="16" height="14" rx="2" fill="{f}" stroke="{s}" stroke-width="1.3"'
        + (' stroke-dasharray="3 2"' if dash else '') + '/>')
    c.t(lx + 22, ly + 1, lab, 's')

# ---------- (b) 每次运算的能耗 ----------
Y1 = 740
bx = c.axes(x=X0, y=Y1, w=AW, h=250, xr=(0.1, 200), yr=(0, 1), xlog=True, xlabel='每次运算的能耗（pJ，对数坐标）',
            xticks=[0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200], yticks=[], grid=False,
            title='(b) 由差值推算的每次运算能耗')
for v in [0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200]:
    c.a(f'<line x1="{bx.X(v):.1f}" y1="{Y1}" x2="{bx.X(v):.1f}" y2="{Y1 + 250}" stroke="#e5e5ea" stroke-width="1"/>')
erows = [  # (标签, 单位, 实心值, 空心值, 颜色, 注)
    ('FP16 乘加（单 ANE / 双 ANE）', '每次乘加', E['f16'], E['f16n'], PUR,
     f"{E['f16']:.2f} / {E['f16d']:.2f}；扣除共用 {E['f16n']:.2f}"),
    ('INT8 乘加（W8A8）', '每次乘加', E['q8'], E['q8n'], GRN, f"{E['q8']:.2f}；扣除读权重负载 {E['q8n']:.2f}"),
    ('FP16 乘加，激活全为 0', '每次乘加（偏置为 0 的卷积链）', E['zr'], E['zz'], PUR,
     f"随机 {E['zr']:.2f} → 全 0 {E['zz']:.2f}"),
    ('读取 DRAM', '每字节', E['dram'], E['dram_ane'], ORA,
     f"{E['dram']:.0f}（内存轨 {E['dram_mem']:.0f} + ANE ≤{E['dram_ane']:.0f}）"),
    ('PE 逐元素加 / 乘', '每个元素', E['pa'], E['pm'], RED, f"{E['pa']:.0f} / {E['pm']:.0f}"),
]
for i, (lab, unit, v0, v1, (s, f), note) in enumerate(erows):
    yc = Y1 + 28 + i * 48
    c.t(X0 - 14, yc - 1, lab, 'b', 'end')
    c.t(X0 - 14, yc + 16, unit, 'c', 'end')
    xa, xb = bx.X(v0), bx.X(v1)
    c.a(f'<line x1="{min(xa, xb):.1f}" y1="{yc:.1f}" x2="{max(xa, xb):.1f}" y2="{yc:.1f}" stroke="{s}" stroke-width="2"/>')
    if i == 4:  # 加、乘两点都是实测总值
        for xx in (xa, xb):
            c.a(f'<circle cx="{xx:.1f}" cy="{yc:.1f}" r="5.5" fill="{s}"/>')
    else:
        c.a(f'<circle cx="{xb:.1f}" cy="{yc:.1f}" r="5.5" fill="#ffffff" stroke="{s}" stroke-width="2"/>')
        c.a(f'<circle cx="{xa:.1f}" cy="{yc:.1f}" r="5.5" fill="{s}"/>')
    c.t(max(xa, xb) + 12, yc + 4.5, note, 's')
ly = Y1 + 250 + 62
c.a(f'<circle cx="{X0 + 8}" cy="{ly - 4}" r="5" fill="{FG2}"/>')
c.t(X0 + 20, ly + 1, 'ANE 净功耗（或总能耗）/ 有效速率', 's')
c.a(f'<circle cx="{X0 + 298}" cy="{ly - 4}" r="5" fill="#ffffff" stroke="{FG2}" stroke-width="2"/>')
c.t(X0 + 310, ly + 1, '扣除共用开销、全 0 激活或仅计 ANE 部分', 's')
c.save('fig13-1_power_breakdown')
