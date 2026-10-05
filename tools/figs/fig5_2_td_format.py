#!/usr/bin/env python3
# 图 5-2：TD 的结构（v24 布局）。生成浅色 SVG（深色版见 darken.py）；PNG 用 Chrome 无头模式导出（见 tools/figs/render.sh）。
# 示例字取自 data/03_compile/tdv/h18g/model.hwx（256 通道、8×32 输入、4 层的 1×9 卷积）。
import os

W, H = 1600, 1290

THEMES = {
    'light': dict(bg=None, fg='#1d1d1f', fg2='#48484a', fg3='#6e6e73', mono='#3a3a3c', panel='#f5f5f7',
                  ctl=('#ececee', '#6e6e73'), hdr=('#f5f5f7', '#8e8e93'), mem=('#fbe3df', '#e64b35'),
                  buf=('#e3f4f0', '#00a087'), cmp=('#e7eaf3', '#3c5488'), dma=('#e1f3f8', '#2f9ab5'),
                  adr=('#efe8e1', '#7e6148'), val=('#ffffff', '#b8bcc6'), ph=('#e5e5ea', '#636366'),
                  line='#8e8e93', arrow='#48484a'),
    'dark': dict(bg='#151517', fg='#f2f2f2', fg2='#b8b8b8', fg3='#9a9a9a', mono='#d0d0d0', panel='#232428',
                 ctl=('#4a4a4c', '#e6e6e6'), hdr=('#2e2e30', '#8a8a8a'), mem=('#5a1414', '#e04848'),
                 buf=('#12394a', '#3cb4dc'), cmp=('#3a1550', '#b050e0'), dma=('#3c4a10', '#c8d830'),
                 adr=('#4a3410', '#f0a830'), val=('#26272b', '#5a5f6a'), ph=('#3a3b40', '#c8c8c8'),
                 line='#8a93a8', arrow='#e6e6e6'),
}


def build(t):
    o = []
    a = o.append

    def box(cls, x, y, w, h, op=1.0):
        f, s = t[cls]
        a(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{f}" stroke="{s}" stroke-width="1.6"'
          + (f' opacity="{op}"' if op != 1.0 else '') + '/>')

    def txt(x, y, s, cls='n', anchor='start', col=None):
        a(f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}"' + (f' fill="{col}"' if col else '') + f'>{s}</text>')

    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="PingFang SC, Helvetica Neue, Arial, sans-serif">')
    a('<style>'
      f'text{{fill:{t["fg"]}}} .t{{font-size:24px;font-weight:600}} .n{{font-size:18px}} '
      f'.m{{font-size:17px;font-family:Menlo,SF Mono,monospace}} .ms{{font-size:14px;font-family:Menlo,SF Mono,monospace;fill:{t["mono"]}}} '
      f'.s{{font-size:15px;fill:{t["fg2"]}}} .xs{{font-size:13px;fill:{t["fg3"]}}}'
      '</style>')
    a(f'<defs><marker id="a" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">'
      f'<path d="M0,1 L9,5 L0,9" fill="none" stroke="{t["arrow"]}" stroke-width="1.6"/></marker></defs>')
    if t['bg']:
        a(f'<rect width="{W}" height="{H}" fill="{t["bg"]}"/>')

    # ---- TD 序列（横排） ----
    txt(60, 40, 'TD 序列（每个 ANE 一段）', 't')
    y0, h0 = 60, 62
    box('hdr', 60, y0, 150, h0); txt(135, y0 + 26, '序列头（4 字）', 's', 'middle'); txt(135, y0 + 48, '1 0 0 0', 'ms', 'middle')
    box('mem', 222, y0, 170, h0); txt(307, y0 + 38, 'TD 0（展开见下）', 'n', 'middle')
    x = 404
    for lab in ['TD 1', 'TD 2']:
        box('mem', x, y0, 120, h0, 0.75); txt(x + 60, y0 + 38, lab, 'n', 'middle'); x += 132
    txt(x + 22, y0 + 38, '⋯', 'n', 'middle', t['fg3']); x += 46
    box('mem', x, y0, 130, h0, 0.75); txt(x + 65, y0 + 38, 'TD n − 1', 'n', 'middle')
    nx = x + 160
    txt(nx, y0 + 18, '每层对应一个或多个 TD。单 ANE 程序一段，', 's')
    txt(nx, y0 + 40, '双 ANE 程序中 ANE0、ANE1 各一段（5.7 节）。', 's')
    txt(nx, y0 + 62, 'TD 内没有指令和分支，只有寄存器写入。', 's')

    # 展开连线与面板
    py, ph = 150, 1110
    a(f'<line x1="307" y1="{y0 + h0}" x2="307" y2="{py - 4}" stroke="{t["arrow"]}" stroke-width="1.8" stroke-dasharray="5 4" marker-end="url(#a)"/>')
    a(f'<rect x="40" y="{py}" width="1520" height="{ph}" rx="16" fill="none" stroke="{t["line"]}" stroke-width="1.2"/>')
    txt(70, py + 40, '一个 TD（v24 布局）', 't')

    # 总览：TD 是一串 32 位字
    y = py + 76
    txt(70, y, 'TD 在内存中是一串 32 位字，依次为任务头、若干写入包和若干地址包；每个包由 1 个包头字和随后的 n 个值字组成。', 's')
    sy, sh = y + 14, 40
    box('ctl', 70, sy, 300, sh); txt(220, sy + 26, '任务头（12 字）', 's', 'middle')
    x = 370
    for nv in [3, 5, 3, 6, 4]:
        box('ph', x, sy, 34, sh); txt(x + 17, sy + 26, '头', 'xs', 'middle'); x += 34
        box('val', x, sy, nv * 22, sh); txt(x + nv * 11, sy + 26, f'{nv} 个值', 'xs', 'middle'); x += nv * 22
    box('val', x, sy, 90, sh, 0.6); txt(x + 45, sy + 26, '⋯', 'n', 'middle'); x += 90
    wx0 = 370; wx1 = x
    ax0 = x
    for nv in [2, 1, 2, 2]:
        box('adr', x, sy, 34, sh); txt(x + 17, sy + 26, '头', 'xs', 'middle'); x += 34
        box('val', x, sy, nv * 30, sh); x += nv * 30
    ax1 = x
    for x0_, x1_, lab in [(70, 370, '①'), (wx0, wx1, '② 寄存器写入包'), (ax0, ax1, '③ 地址包')]:
        a(f'<path d="M{x0_ + 2} {sy + sh + 6} v6 H{x1_ - 2} v-6" stroke="{t["line"]}" stroke-width="1.4" fill="none"/>')
        txt((x0_ + x1_) / 2, sy + sh + 32, lab, 's', 'middle')

    # ① 任务头
    y = py + 200
    txt(70, y, '① 任务头：12 个字（td_header0–11）')
    cells = [('+0x0', 'tid · TaskSize', 200), ('+0x4', 'exe_cycles', 160),
             ('+0x8 … +0x1c', '事件掩码：log / exception / debug / dram（6 字）', 560),
             ('+0x20', '标志字：Tsr · Tde · PublishBit', 300), ('+0x24 … +0x2c', '其余 3 字', 240)]
    x = 70
    for off, lab, w in cells:
        box('ctl', x, y + 14, w, 58, 0.6 if lab == '其余 3 字' else 1.0)
        txt(x + w / 2, y + 38, off, 'ms', 'middle'); txt(x + w / 2, y + 62, lab, 's', 'middle'); x += w
    txt(70, y + 96, 'TaskSize 以字为单位给出本 TD 的长度；exe_cycles 是编译器性能模型的延迟估计（约 1 µs / 单位）；各字段见表 5-4。', 'xs')

    # ② 写入包（左）与 ③ 地址包（右）
    y = py + 340
    txt(70, y, '② 寄存器写入包：包头字说明写哪些寄存器，值字依次写入')
    txt(140, y + 26, '包头字', 'xs', 'middle'); txt(336, y + 26, '值字（下方小字为目标寄存器）', 'xs', 'middle')

    def vcell(x, y, w, top, reg):
        box('val', x, y, w, 50); txt(x + w / 2, y + 22, top, 'n' if len(top) < 5 else 'ms', 'middle'); txt(x + w / 2, y + 42, reg, 'xs', 'middle')
    ey = y + 36
    box('ph', 70, ey, 140, 50); txt(140, ey + 31, '00010001', 'm', 'middle')
    for i, v in enumerate(['Win', 'Hin', 'Cin']):
        vcell(210 + i * 84, ey, 84, v, f'寄存器 {i + 1}')
    txt(560, ey + 22, '连续写：从寄存器 1 起', 's'); txt(560, ey + 42, '连续写 3 个值', 's')
    ey += 64
    box('ph', 70, ey, 140, 50); txt(140, ey + 31, '80c11340', 'm', 'middle')
    for i, r in enumerate(['1340', '1342', '1348', '1349']):
        vcell(210 + i * 84, ey, 84, '值', f'寄存器 {r}')
    txt(560, ey + 22, '掩码写：写基址 0x1340，', 's'); txt(560, ey + 42, '以及掩码选中的 3 个寄存器', 's')

    rx = 820
    txt(rx, y, '③ 地址包：值字是缓冲区内的偏移，BAR 编号指明是哪个缓冲区')
    txt(rx + 70, y + 26, '包头字', 'xs', 'middle'); txt(rx + 196, y + 26, '偏移（低 / 高 32 位）', 'xs', 'middle')
    rows = [('20809544', 2, '权重（寄存器 0x1544），BAR 4', '加载时由静态重定位填入'),
            ('22801344', 1, 'DSID 参数（寄存器 0x1344），BAR 20', '系统级缓存的数据流标签'),
            ('23009444', 2, '输出（寄存器 0x1444），BAR 24', '每次调用时由运行时按 BAR 填入'),
            ('23809346', 2, '输入（寄存器 0x1346），BAR 28', '24 起每个张量 4 个槽位，先输出后输入')]
    ey = y + 36
    for hw, n, d1, d2 in rows:
        box('adr', rx, ey, 140, 44); txt(rx + 70, ey + 28, hw, 'm', 'middle')
        for i in range(n):
            box('val', rx + 140 + i * 56, ey, 56, 44); txt(rx + 168 + i * 56, ey + 28, ['Lo', 'Hi'][i] if n == 2 else '值', 'ms', 'middle')
        txt(rx + 270, ey + 19, d1, 's'); txt(rx + 270, ey + 38, d2, 'xs')
        ey += 54

    # 寄存器组色带
    y = py + 640
    txt(70, y, '② 中的写入包按以下寄存器组的顺序排列（字段偏移，表 5-6），这一顺序与硬件中的数据流向一致：', 's')
    groups = [('ctl', '公共', '形状 · 任务类型'), ('dma', '输入', 'Tile DMA'), ('buf', '纹理 / gather', '重采样'),
              ('buf', 'L2 源', '环形缓冲'), ('cmp', 'PE', '逐元素'), ('cmp', 'NE', '卷积配置 · 移位'), ('dma', '输出', 'Tile DMA')]
    gw, gap = 198, 9
    x = 70
    for cls, l1, l2 in groups:
        box(cls, x, y + 14, gw, 64); txt(x + gw / 2, y + 42, l1, 'n', 'middle'); txt(x + gw / 2, y + 64, l2, 'xs', 'middle'); x += gw + gap
    a(f'<line x1="{70 + gw + gap}" y1="{y + 100}" x2="1520" y2="{y + 100}" stroke="{t["arrow"]}" stroke-width="2" marker-end="url(#a)"/>')
    txt(860, y + 124, 'DRAM → 输入 Tile DMA → L2 → NE / PE → 输出 Tile DMA → DRAM', 'xs', 'middle')

    # ④ 包头字逐位解码
    y = py + 810
    txt(70, y, '④ 包头字的逐位解码：以 ②、③ 中的三个包头字为例（32 位，左为 bit 31）')
    bw, x0 = 38, 270

    def bx(b):
        return x0 + (31 - b) * bw
    for b in [31, 30, 29, 28, 21, 20, 15, 14, 0]:
        txt(bx(b) + bw / 2, y + 30, str(b), 'ms', 'middle')
    rowsb = [('连续写', '00010001', [(31, 31, '0', 'ph'), (30, 15, '个数 − 1 = 2', 'val'), (14, 0, '起始寄存器 = 0x0001', 'val')]),
             ('掩码写', '80c11340', [(31, 31, '1', 'ph'), (30, 15, '掩码 = 0x0182（bit 1、7、8）', 'val'), (14, 0, '基址 = 0x1340', 'val')]),
             ('地址包', '23809346', [(31, 31, '0', 'ph'), (30, 30, '0', 'ph'), (29, 29, '1', 'adr'), (28, 21, 'BAR = 28', 'adr'),
                                   (20, 15, '个数 − 1 = 1', 'val'), (14, 0, '寄存器 = 0x1346', 'val')])]
    yy = y + 42
    for name, hx, fs in rowsb:
        txt(150, yy + 30, name, 'n', 'end'); txt(255, yy + 30, hx, 'm', 'end')
        for hi, lo, lab, cls in fs:
            w = (hi - lo + 1) * bw
            box(cls, bx(hi), yy, w, 48); txt(bx(hi) + w / 2, yy + 30, lab, 'n', 'middle')
        yy += 62
    txt(270, yy + 10, 'bit 31 区分连续写（0）与掩码写（1）；掩码第 i 位为 1 时另写寄存器"基址 + 1 + i"；地址包以 bit 29 为标记，所有 64 位地址包的 BAR 编号都是偶数（表 5-5、5.6.6 节）。', 'xs')
    txt(70, py + ph - 16, '示例取自 256 通道、8×32 输入、4 层的 1×9 卷积在 h18g 上的产物（data/03_compile/tdv/h18g）。', 'xs')
    a('</svg>')
    return '\n'.join(o)


if __name__ == '__main__':
    out = os.path.join(os.path.dirname(__file__), '..', '..', 'figs')
    # 深色版由 tools/figs/darken.py 统一从浅色版换算，这里只出浅色版
    with open(os.path.join(out, 'fig5-2_td_format.svg'), 'w') as f:
        f.write(build(THEMES['light']))
