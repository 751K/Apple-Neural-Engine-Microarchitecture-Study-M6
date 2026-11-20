#!/usr/bin/env python3
# 结构图的公共画法（图 4-1 定下的样式，供第 4–10 章的结构图共用）：
#   填色只分三类：计算 = 浅绿，存储 = 浅蓝，搬运、控制与软件 = 白；方框加深灰细描边；
#   灰色只作分区底色，不描边；连线颜色区分数据：激活 = 橙，权重 = 深红，控制与软件调用 = 黑。
#   字号不小于 15 px（图宽 800 时，印到 A4 版心约 180 mm 仍可读）；图中只写部件名，数值放在图注。
# 用法：from archfig import Fig, GREEN, BLUE, ...；f = Fig(800, 560)；...；f.save('fig4-2_software')
import os

K = '#111111'                     # 文字、黑色连线
SK, SW = '#2b2b2b', 0.8           # 描边
GREEN, BLUE, WHITE = '#d5e3b8', '#b6c9e6', '#ffffff'
PANEL = '#efefef'                 # 分区底色
GREY = '#8c8c8c'                  # 投影线、次要连线
ACT, WT = '#e07b22', '#a5302e'
FONT = 'text{font-family:Arial,"Helvetica Neue","PingFang SC",sans-serif}'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'figs', 'zh', 'light')



def legend_html(items, y, W, h=28):
    # 图例：用 foreignObject 中的 flex 排版，各项之间的间距自动相等（中英文译文长度不同也一样）。
    # items: ('line', 颜色, 虚线样式或 None, 文字) 或 ('swatch', 填色, 文字)；y 为图例中线。
    parts = []
    for it in items:
        if it[0] == 'line':
            _, col, dash, lab = it
            da = f' stroke-dasharray="{dash}"' if dash else ''
            icon = (f'<svg xmlns="http://www.w3.org/2000/svg" width="36" height="12" viewBox="0 0 36 12"><line x1="0" y1="6" x2="27" y2="6" stroke="{col}" '
                    f'stroke-width="{1.8 if dash else 2.4}"{da}/><path d="M26,1.5 L35,6 L26,10.5 z" fill="{col}"/></svg>')
        else:
            _, fill, lab = it
            icon = (f'<span style="display:inline-block;width:26px;height:18px;box-sizing:border-box;'
                    f'background:{fill};border:{SW}px solid {SK}"></span>')
        parts.append(f'<span style="display:flex;align-items:center;gap:10px">{icon}<span>{lab}</span></span>')
    # 项数少时居中并用固定间距，避免三四项被拉到整幅宽度的两端
    jc, gap = ('space-between', '0') if len(items) >= 5 else ('center', '56px')
    return (f'<foreignObject x="0" y="{y - h / 2}" width="{W}" height="{h}"><div xmlns="http://www.w3.org/1999/xhtml" '
            f'style="display:flex;justify-content:{jc};gap:{gap};align-items:center;height:{h}px;padding:0 6px;'
            f'font-family:Arial,\'Helvetica Neue\',\'PingFang SC\',sans-serif;font-size:16px;color:{K}">'
            + ''.join(parts) + '</div></foreignObject>')


class Fig:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.o = []
        self.marks = {}

    def raw(self, s):
        self.o.append(s)

    def text(self, x, y, s, size=17, col=K, anchor='middle', w=600):
        self.raw(f'<text x="{x}" y="{y}" text-anchor="{anchor}" style="font-size:{size}px;fill:{col};font-weight:{w}">{s}</text>')

    def rect(self, x, y, w, h, fill=WHITE, stroke=True, rx=0, sw=SW, extra=''):
        st = f' stroke="{SK}" stroke-width="{sw}"' if stroke else ''
        self.raw(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{st}{extra}/>')

    def box(self, x, y, w, h, title='', fill=WHITE, size=17, w8=600):
        self.rect(x, y, w, h, fill)
        if title:
            self.text(x + w / 2, y + h / 2 + size * 0.35, title, size, K, 'middle', w8)

    def panel(self, x, y, w, h):
        self.rect(x, y, w, h, PANEL, stroke=False, rx=10)

    def _mark(self, col):
        if col not in self.marks:
            self.marks[col] = f'm{len(self.marks)}'
        return self.marks[col]

    def line(self, pts, col=K, sw=2.2, dash=None, head=True, both=False):
        d = ' '.join(f'{x},{y}' for x, y in pts)
        m = self._mark(col)
        self.raw(f'<polyline points="{d}" fill="none" stroke="{col}" stroke-width="{sw}" stroke-linejoin="miter"'
                 + (f' stroke-dasharray="{dash}"' if dash else '')
                 + (f' marker-end="url(#{m})"' if head else '')
                 + (f' marker-start="url(#{m})"' if both else '') + '/>')

    def legend(self, items, y, **_):
        self.raw(legend_html(items, y, self.W))

    def save(self, name):
        defs = ''.join(
            f'<marker id="{m}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4.5" markerHeight="4.5" '
            f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
            for c, m in self.marks.items())
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.W} {self.H}" width="{self.W}" height="{self.H}">'
               f'<style>{FONT}</style><defs>{defs}</defs>'
               f'<rect width="{self.W}" height="{self.H}" fill="#ffffff"/>\n' + '\n'.join(self.o) + '\n</svg>')
        path = os.path.join(OUT, name + '.svg')
        open(path, 'w').write(svg)
        return path
