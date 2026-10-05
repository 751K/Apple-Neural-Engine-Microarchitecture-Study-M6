# 示意图共用的配色与绘图辅助（浅色为默认，深色另出一份）。
THEMES = {
    'light': dict(bg=None, fg='#1d1d1f', fg2='#48484a', fg3='#6e6e73', mono='#3a3a3c',
                  ctl=('#ececee', '#6e6e73'), hdr=('#f5f5f7', '#8e8e93'), mem=('#fbe3df', '#e64b35'),
                  buf=('#e3f4f0', '#00a087'), cmp=('#e7eaf3', '#3c5488'), dma=('#e1f3f8', '#2f9ab5'),
                  adr=('#efe8e1', '#7e6148'), clk=('#efe8e1', '#7e6148'), val=('#ffffff', '#b8bcc6'),
                  ph=('#e5e5ea', '#636366'), host=('#eef2f8', '#5b6b8c'),
                  line='#8e8e93', arrow='#48484a', accent='#7e6148'),
    'dark': dict(bg='#151517', fg='#f2f2f2', fg2='#b8b8b8', fg3='#9a9a9a', mono='#d0d0d0',
                 ctl=('#4a4a4c', '#e6e6e6'), hdr=('#2e2e30', '#8a8a8a'), mem=('#5a1414', '#e04848'),
                 buf=('#12394a', '#3cb4dc'), cmp=('#3a1550', '#b050e0'), dma=('#3c4a10', '#c8d830'),
                 adr=('#4a3410', '#f0a830'), clk=('#4a3410', '#f0a830'), val=('#26272b', '#5a5f6a'),
                 ph=('#3a3b40', '#c8c8c8'), host=('#1e2633', '#7f93b8'),
                 line='#8a93a8', arrow='#e6e6e6', accent='#f0a830'),
}


class Fig:
    def __init__(self, t, W, H):
        self.t, self.W, self.H, self.o = t, W, H, []
        a = self.o.append
        a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="PingFang SC, Helvetica Neue, Arial, sans-serif">')
        a('<style>'
          f'text{{fill:{t["fg"]}}} .t{{font-size:24px;font-weight:600}} .h{{font-size:20px;font-weight:600}} .n{{font-size:18px}} '
          f'.m{{font-size:17px;font-family:Menlo,SF Mono,monospace}} .ms{{font-size:14px;font-family:Menlo,SF Mono,monospace;fill:{t["mono"]}}} '
          f'.s{{font-size:15px;fill:{t["fg2"]}}} .xs{{font-size:13px;fill:{t["fg3"]}}}'
          '</style>')
        a('<defs>'
          f'<marker id="a" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,1 L9,5 L0,9" fill="none" stroke="{t["arrow"]}" stroke-width="1.6"/></marker>'
          f'<marker id="b" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,1 L9,5 L0,9" fill="none" stroke="{t["accent"]}" stroke-width="1.6"/></marker>'
          '</defs>')
        if t['bg']:
            a(f'<rect width="{W}" height="{H}" fill="{t["bg"]}"/>')

    def raw(self, s):
        self.o.append(s)

    def box(self, cls, x, y, w, h, op=1.0, rx=0, dash=False):
        f, s = self.t[cls]
        self.o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{f}" stroke="{s}" stroke-width="1.6"'
                      + (f' opacity="{op}"' if op != 1.0 else '') + (' stroke-dasharray="6 4"' if dash else '') + '/>')

    def frame(self, x, y, w, h, rx=14, dash=False, col=None, sw=1.3):
        c = col or self.t['line']
        self.o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="none" stroke="{c}" stroke-width="{sw}"'
                      + (' stroke-dasharray="7 5"' if dash else '') + '/>')

    def txt(self, x, y, s, cls='n', anchor='start', col=None):
        self.o.append(f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}"' + (f' fill="{col}"' if col else '') + f'>{s}</text>')

    def lines(self, x, y, items, dy=20, anchor='start'):
        for i, (s, cls) in enumerate(items):
            self.txt(x, y + i * dy, s, cls, anchor)

    def arrow(self, pts, accent=False, dash=False, w=2):
        d = 'M' + ' L'.join(f'{x} {y}' for x, y in pts)
        c = self.t['accent'] if accent else self.t['arrow']
        m = 'b' if accent else 'a'
        self.o.append(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{w}"' + (' stroke-dasharray="6 4"' if dash else '')
                      + f' marker-end="url(#{m})"/>')

    def svg(self):
        return '\n'.join(self.o + ['</svg>'])
