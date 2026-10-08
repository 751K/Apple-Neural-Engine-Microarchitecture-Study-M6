#!/usr/bin/env python3
# 把报告生成为单页网页：final_report/zh.md → site/index.html，final_report/en.md → site/en/index.html（另复制所需的图）。
#   - 左侧章节目录，滚动时高亮当前章节；深浅色跟随系统，也可手动切换；
#   - 图按主题在 figs/zh/light 与 figs/zh/dark 之间切换；
#   - 正文中的 ../tools/…、../data/… 链接改写为 GitHub 上的地址；
#   - "第 N.M 节""表 N-M""图 N-M""[n]"（英文版为 Section、Table、Figure 等）自动链接到对应的锚点；
#   - 顶栏有中英文切换链接（中文版在 site/，英文版在 site/en/）。
# 用法：python3 tools/site/build.py [--lang zh|en] [--repo URL] [--out DIR]
# 依赖：markdown-it-py（pip install markdown-it-py）
import argparse
import html
import os
import re
import shutil
import struct

from markdown_it import MarkdownIt

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
REPO = 'https://github.com/751K/Apple-Neural-Engine-Microarchitecture-Study-M6'

ap = argparse.ArgumentParser()
ap.add_argument('--repo', default=REPO)
ap.add_argument('--out')
ap.add_argument('--lang', default='zh', choices=('zh', 'en'))
args = ap.parse_args()
EN = args.lang == 'en'
if not args.out:
    args.out = os.path.join(ROOT, 'site', 'en') if EN else os.path.join(ROOT, 'site')
UI = {
    'zh': dict(menu='目录', theme_dark='深色', theme_light='浅色', theme_label='切换深浅色', code='代码与数据：',
               other='English', other_href='en/',
               desc='Apple M6 神经网络引擎的微体系结构研究：编译产物、执行追踪与功耗测量。'),
    'en': dict(menu='Contents', theme_dark='Dark', theme_light='Light', theme_label='Toggle dark mode', code='Code and data: ',
               other='中文', other_href='../',
               desc='A microarchitecture study of the Apple M6 Neural Engine based on compiled artifacts, execution traces, and power measurements.'),
}[args.lang]
FIG = 'Figure' if EN else '图'
TAB = 'Table' if EN else '表'

src = open(os.path.join(ROOT, 'final_report', f'{args.lang}.md')).read()
md = MarkdownIt('commonmark', {'html': True}).enable('table')
body = md.render(src)


# ---------- 标题：编号锚点与目录 ----------
def heading_id(text):
    t = html.unescape(re.sub(r'<[^>]+>', '', text)).strip()
    m = re.match(r'(\d+(?:\.\d+)*)\.?\s', t)
    if m:
        return 's' + m.group(1).replace('.', '-')
    m = re.match(r'(?:附录\s*|Appendix\s+)([A-E])\b', t)
    if m:
        return 'app' + m.group(1)
    m = re.match(r'([A-E])\.(\d+)', t)
    if m:
        return m.group(1).lower() + '-' + m.group(2)
    return {'摘要': 'abstract', '致谢': 'ack', '参考文献': 'refs',
            'Abstract': 'abstract', 'Acknowledgments': 'ack', 'References': 'refs'}.get(t, None)


toc = []
used = set()


def on_heading(m):
    lvl, inner = int(m.group(1)), m.group(2)
    hid = heading_id(inner)
    if lvl == 1:
        return m.group(0)
    if not hid or hid in used:
        hid = f'h{len(used)}'
    used.add(hid)
    if lvl in (2, 3):
        toc.append((lvl, hid, re.sub(r'<[^>]+>', '', inner)))
    return f'<h{lvl} id="{hid}"><a class="anchor" href="#{hid}">#</a>{inner}</h{lvl}>'


body = re.sub(r'<h([1-4])>(.*?)</h\1>', on_heading, body)
title = re.search(r'<h1>(.*?)</h1>', body).group(1)
body = re.sub(r'<h1>.*?</h1>', '', body, count=1)


# ---------- 图：浅色与深色两份，按主题显示 ----------
def figure(m):
    img, cap = m.group(1), m.group(2)
    srcp = re.search(r'src="([^"]+)"', img).group(1)
    alt = re.search(r'alt="([^"]*)"', img)
    alt = alt.group(1) if alt else ''
    name = os.path.basename(srcp)
    fid = re.match(FIG + r' (\d+-\d+)', cap)
    fid = f' id="f{fid.group(1)}"' if fid else ''
    light = f'figs/{args.lang}/light/{name}'
    dark = f'figs/{args.lang}/dark/{name}'
    with open(os.path.join(ROOT, light), 'rb') as fh:   # PNG 头中的宽高，用于预留版面
        w, h = struct.unpack('>II', fh.read(24)[16:24])
    img_attr = f'width="{w}" height="{h}" loading="lazy"'
    return (f'<figure{fid}><a href="{light}" class="light-only" target="_blank"><img src="{light}" alt="{alt}" {img_attr}></a>'
            f'<a href="{dark}" class="dark-only" target="_blank"><img src="{dark}" alt="{alt}" {img_attr}></a>'
            f'<figcaption>{cap}</figcaption></figure>')


body = re.sub(r'<p>(<img [^>]+>)</p>\s*<p><em>(' + FIG + r' .*?)</em></p>', figure, body, flags=re.S)


# ---------- 表：标题锚点，横向滚动 ----------
def table_cap(m):
    cap = m.group(1)
    tid = re.match(TAB + r' ([0-9A-Z]+-\d+)', cap)
    tid = f' id="t{tid.group(1)}"' if tid else ''
    return f'<p class="tcap"{tid}>{cap}</p>'


body = re.sub(r'<p><em>(' + TAB + r' [0-9A-Z]+-\d+.*?)</em></p>', table_cap, body)
body = body.replace('<table>', '<div class="table-wrap"><table>').replace('</table>', '</table></div>')


# ---------- 参考文献：条目锚点，网址变链接 ----------
def refs_block(m):
    block = m.group(0)
    block = re.sub(r'<p>\[(\d+)\]\s*', r'<p class="ref" id="ref-\1"><span class="refno">[\1]</span>', block)
    block = re.sub(r'arXiv:(\d{4}\.\d{4,5})', r'<a href="https://arxiv.org/abs/\1">arXiv:\1</a>', block)
    block = re.sub(r'(?<!["=>])(https?://[^\s<，,）)]+?)(?=[.,，]?\s|[.,，]?</p>|,\s)',
                   lambda u: f'<a href="{u.group(1)}">{u.group(1)}</a>', block)
    return block


body = re.sub(r'<h2 id="refs">.*?(?=<h2 )', refs_block, body, flags=re.S)


# ---------- 仓库内的相对链接 ----------
def repo_link(m):
    path = m.group(1)
    full = os.path.join(ROOT, path)
    kind = 'tree' if path.endswith('/') or os.path.isdir(full) else 'blob'
    return f'href="{args.repo}/{kind}/main/{path.rstrip("/")}"'


body = re.sub(r'href="\.\./([^"]+)"', repo_link, body)
body = re.sub(r'<a href="http', '<a target="_blank" rel="noopener" href="http', body)


# ---------- 正文中的交叉引用与证据标签 ----------
ids = set(re.findall(r'id="([^"]+)"', body))


def link_text(t):
    def sec(m):
        nums = m.group(1)
        hid = 's' + nums.replace('.', '-')
        return f'<a class="xref" href="#{hid}">{m.group(0)}</a>' if hid in ids else m.group(0)
    t = re.sub(r'第 (\d+(?:\.\d+)*) (?:节|章)', sec, t)

    def tf(m):
        kind, num = m.group(1), m.group(2)
        hid = ('t' if kind == '表' else 'f') + num
        return f'<a class="xref" href="#{hid}">{m.group(0)}</a>' if hid in ids else m.group(0)
    t = re.sub(r'(表|图) ([0-9A-Z]+-\d+)', tf, t)

    def app(m):
        letter, num = m.group(1), m.group(2)
        hid = f'{letter.lower()}-{num}' if num else f'app{letter}'
        return f'<a class="xref" href="#{hid}">{m.group(0)}</a>' if hid in ids else m.group(0)
    t = re.sub(r'附录 ([A-E])(?:\.(\d+))?', app, t)
    if EN:
        t = link_en(t)

    def cite(m):
        inner = m.group(1)
        out = re.sub(r'\d+', lambda d: f'<a class="cite" href="#ref-{d.group(0)}">{d.group(0)}</a>'
                     if f'ref-{d.group(0)}' in ids else d.group(0), inner)
        return f'[{out}]'
    t = re.sub(r'\[(\d+(?:\s*[,，–-]\s*\d+)*)\]', cite, t)
    t = re.sub(r'〔([^〔〕]{1,40})〕', r'<span class="ev">〔\1〕</span>', t)
    return t


def link_en(t):
    """英文版：Section(s) / Chapter(s) / Table(s) / Figure(s) / Appendix(-ces) 后的编号逐个链接，含 "5.7 and 10.4"、"5–6" 等列举。"""
    def one(hid, text):
        return f'<a class="xref" href="#{hid}">{text}</a>' if hid in ids else text

    def secs(m):
        word, lst = m.group(1), m.group(2)
        return word + ' ' + re.sub(r'\d+(?:\.\d+)*', lambda d: one('s' + d.group(0).replace('.', '-'), d.group(0)), lst)
    t = re.sub(r'\b(Sections?|Chapters?) (\d+(?:\.\d+)*(?:(?:–|, | and |, and | to )\d+(?:\.\d+)*)*)', secs, t)

    def tfs(m):
        word, lst = m.group(1), m.group(2)
        k = 't' if word.startswith('T') else 'f'
        pre = [None]

        def num(d):
            n = d.group(0)
            if '-' in n:
                pre[0] = n.split('-')[0]
                return one(k + n, n)
            return one(f'{k}{pre[0]}-{n}', n) if pre[0] else n
        return word + ' ' + re.sub(r'(?:[0-9A-Z]+-)?\d+', num, lst)
    t = re.sub(r'\b(Tables?|Figures?) ([0-9A-Z]+-\d+(?:(?:–|, | and |, and | to )(?:[0-9A-Z]+-)?\d+)*)', tfs, t)

    def apps(m):
        word, lst = m.group(1), m.group(2)
        return word + ' ' + re.sub(r'\b([A-E])(?:\.(\d+))?\b',
                                   lambda d: one(f'{d.group(1).lower()}-{d.group(2)}' if d.group(2) else f'app{d.group(1)}', d.group(0)), lst)
    t = re.sub(r'\b(Appendix|Appendices) ([A-E](?:\.\d+)?(?:(?:, | and |, and )[A-E](?:\.\d+)?)*)\b', apps, t)
    return t


# 只处理标签之外的文字，并跳过 a、code、pre 与标题中的内容
out, skip = [], 0
for part in re.split(r'(<[^>]+>)', body):
    if part.startswith('<'):
        tag = re.match(r'</?([a-zA-Z0-9]+)', part)
        name = tag.group(1).lower() if tag else ''
        if name in ('a', 'code', 'pre', 'h2', 'h3', 'h4'):
            skip += -1 if part.startswith('</') else 1
        out.append(part)
    else:
        out.append(part if skip > 0 else link_text(part))
body = ''.join(out)
# 参考文献条目自身不再链接
body = re.sub(r'<span class="refno">\[<a class="cite" href="#ref-\d+">(\d+)</a>\]</span>', r'<span class="refno">[\1]</span>', body)


# ---------- 目录 ----------
def toc_html():
    items, open_sub = [], False
    for lvl, hid, text in toc:
        text = html.escape(html.unescape(text))
        if lvl == 2:
            if open_sub:
                items.append('</ol></li>')
                open_sub = False
            items.append(f'<li class="c"><a href="#{hid}">{text}</a>')
            items.append('<ol>')
            open_sub = True
        else:
            items.append(f'<li><a href="#{hid}">{text}</a></li>')
    if open_sub:
        items.append('</ol></li>')
    s = ''.join(items).replace('<ol></ol>', '')
    return f'<ol>{s}</ol>'


CSS = r'''
:root{--bg:#ffffff;--fg:#1d1d1f;--muted:#6b6b70;--line:#e3e3e6;--soft:#f5f5f7;--accent:#3C5488;--link:#2f5fa7;
--ev:#8a6d3b;--side:#fafafb;--code:#f3f3f5}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161618;--fg:#e6e6e9;--muted:#9a9aa1;--line:#2e2e33;
--soft:#1f1f23;--accent:#8fa6d8;--link:#8db4f0;--ev:#c9a86a;--side:#1a1a1d;--code:#232328}}
:root[data-theme="dark"]{--bg:#161618;--fg:#e6e6e9;--muted:#9a9aa1;--line:#2e2e33;--soft:#1f1f23;--accent:#8fa6d8;
--link:#8db4f0;--ev:#c9a86a;--side:#1a1a1d;--code:#232328}
*{box-sizing:border-box}
html{scroll-padding-top:64px;-webkit-text-size-adjust:100%}
:root{--serif:"Source Serif 4","Noto Serif SC","Source Han Serif SC","Songti SC",serif;--sans:"Noto Sans SC",-apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
body{margin:0;background:var(--bg);color:var(--fg);font:16.5px/1.9 var(--serif)}
h1,h2,h3,h4,header.top,nav.toc,.tcap,figcaption,table,.meta,button{font-family:var(--sans)}
a{color:var(--link);text-decoration:none;overflow-wrap:anywhere}a:hover{text-decoration:underline}
header.top{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:12px;height:52px;padding:0 16px;
background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
header.top .t{font-weight:600;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1}
header.top button,header.top a.btn{font:inherit;font-size:13px;color:var(--fg);background:var(--soft);border:1px solid var(--line);
border-radius:8px;padding:4px 10px;cursor:pointer;white-space:nowrap}
#menu{display:none}
.layout{display:grid;grid-template-columns:290px minmax(0,1fr);max-width:1800px;margin:0 auto}
nav.toc{position:sticky;top:52px;height:calc(100vh - 52px);overflow-y:auto;padding:20px 12px 40px 16px;
border-right:1px solid var(--line);background:var(--side);font-size:13.5px;line-height:1.5}
nav.toc ol{list-style:none;margin:0;padding:0}
nav.toc li.c>a{display:block;font-weight:600;padding:5px 8px;border-radius:6px;color:var(--fg)}
nav.toc li.c>ol{display:none;margin:2px 0 6px 10px;border-left:1px solid var(--line)}
nav.toc li.c.open>ol{display:block}
nav.toc li li a{display:block;padding:3px 8px 3px 12px;color:var(--muted)}
nav.toc a.active{color:var(--accent)!important;background:color-mix(in srgb,var(--accent) 10%,transparent)}
main{min-width:0;padding:32px 48px 120px}
article{max-width:72em;margin:0 auto}
h1.title{font-size:30px;line-height:1.35;margin:8px 0 6px;letter-spacing:.01em}
.meta{color:var(--muted);font-size:14px;margin-bottom:36px}
h2{font-size:24px;margin:64px 0 16px;padding-bottom:8px;border-bottom:1px solid var(--line);line-height:1.4}
h3{font-size:19px;margin:40px 0 12px;line-height:1.45}
h4{font-size:16.5px;margin:28px 0 10px}
h2,h3,h4{position:relative}
.anchor{position:absolute;left:-1.1em;color:var(--muted);opacity:0;font-weight:400}
h2:hover .anchor,h3:hover .anchor,h4:hover .anchor{opacity:.6}
p{margin:0 0 1em;text-align:left}
.ev{color:var(--ev);font-size:.82em;white-space:nowrap}
a.xref{color:inherit;border-bottom:1px dotted var(--muted)}a.xref:hover{color:var(--link);text-decoration:none}
a.cite{color:var(--link)}
code{font:.86em/1.5 "IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace;background:var(--code);padding:.1em .35em;border-radius:4px;word-break:break-word}
pre{background:var(--code);padding:14px 16px;border-radius:8px;overflow-x:auto;font-size:13px;line-height:1.55}
pre code{background:none;padding:0}
.table-wrap{overflow-x:auto;margin:6px 0 28px;border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:13.5px;line-height:1.55}
th,td{padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}
th{background:var(--soft);font-weight:600;white-space:nowrap}
tr:last-child td{border-bottom:none}
td{min-width:4em}
.tcap{text-align:center;font-size:14px;font-weight:600;margin:28px 0 4px;color:var(--fg)}
figure{margin:28px 0 32px;text-align:center}
figure img{max-width:100%;height:auto;border-radius:6px}
figcaption{font-size:14px;color:var(--muted);text-align:justify;margin-top:10px;line-height:1.7}
.dark-only{display:none}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .light-only{display:none}:root:not([data-theme="light"]) .dark-only{display:inline}}
:root[data-theme="dark"] .light-only{display:none}:root[data-theme="dark"] .dark-only{display:inline}
p.ref{padding-left:3em;text-indent:-3em;font-size:14.5px;text-align:left;overflow-wrap:anywhere}p.ref a{word-break:break-all}
.refno{display:inline-block;width:3em;text-indent:0;color:var(--muted)}
:target{animation:hl 1.6s ease}
@keyframes hl{from{background:color-mix(in srgb,var(--accent) 18%,transparent)}to{background:transparent}}
@media (max-width:1000px){
 #menu{display:inline-block}
 .layout{display:block}
 nav.toc{position:fixed;left:0;top:52px;width:min(320px,86vw);z-index:15;transform:translateX(-102%);transition:transform .2s;box-shadow:0 0 24px rgba(0,0,0,.18)}
 body.nav-open nav.toc{transform:none}
 main{padding:20px 16px 80px}
 h1.title{font-size:24px}
 h2{font-size:21px}h3{font-size:18px}
 .anchor{display:none}
 p{text-align:left}
}
'''

JS = r'''
(function(){
 var root=document.documentElement,btn=document.getElementById('theme');
 function cur(){return root.getAttribute('data-theme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light')}
 function label(){btn.textContent=cur()==='dark'?'__LIGHT__':'__DARK__'}
 btn.onclick=function(){var t=cur()==='dark'?'light':'dark';root.setAttribute('data-theme',t);
  try{localStorage.setItem('theme',t)}catch(e){}label()};
 label();
 document.getElementById('menu').onclick=function(){document.body.classList.toggle('nav-open')};
 var links=[].slice.call(document.querySelectorAll('nav.toc a')),map={};
 links.forEach(function(a){map[a.getAttribute('href').slice(1)]=a;a.addEventListener('click',function(){document.body.classList.remove('nav-open')})});
 var heads=[].slice.call(document.querySelectorAll('article h2[id],article h3[id]')).filter(function(h){return map[h.id]});
 var active=null;
 function update(){
  var y=window.scrollY+90,h=null;
  for(var i=0;i<heads.length;i++){if(heads[i].offsetTop<=y)h=heads[i];else break}
  if(!h||h===active)return;active=h;
  links.forEach(function(a){a.classList.remove('active')});
  [].forEach.call(document.querySelectorAll('nav.toc li.c'),function(li){li.classList.remove('open')});
  var a=map[h.id];a.classList.add('active');
  var li=a.closest('li.c');if(li){li.classList.add('open');var top=li.querySelector('a');if(top!==a)top.classList.add('active')}
  var r=a.getBoundingClientRect(),nav=document.querySelector('nav.toc'),nr=nav.getBoundingClientRect();
  if(r.top<nr.top+40||r.bottom>nr.bottom-40)nav.scrollTop+=r.top-nr.top-nr.height/3;
 }
 var tick=false;window.addEventListener('scroll',function(){if(!tick){tick=true;requestAnimationFrame(function(){tick=false;update()})}});
 update();
})();
'''

page = f'''<!doctype html>
<html lang="{args.lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.unescape(re.sub(r'<[^>]+>', '', title))}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&family=Noto+Serif+SC:wght@400;600&family=Noto+Sans+SC:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<meta name="description" content="{UI['desc']}">
<script>try{{var t=localStorage.getItem('theme');if(t)document.documentElement.setAttribute('data-theme',t)}}catch(e){{}}</script>
<style>{CSS}</style>
</head>
<body>
<header class="top">
<button id="menu" aria-label="{UI['menu']}">{UI['menu']}</button>
<div class="t">{title}</div>
<button id="theme" aria-label="{UI['theme_label']}">{UI['theme_dark']}</button>
<a class="btn" href="{UI['other_href']}" hreflang="{'zh' if EN else 'en'}">{UI['other']}</a>
<a class="btn" href="{args.repo}" target="_blank" rel="noopener">GitHub</a>
</header>
<div class="layout">
<nav class="toc" aria-label="{UI['menu']}">{toc_html()}</nav>
<main><article>
<h1 class="title">{title}</h1>
<div class="meta">{UI['code']}<a href="{args.repo}" target="_blank" rel="noopener">{args.repo.replace("https://", "")}</a></div>
{body}
</article>
</main>
</div>
<script>{JS.replace('__LIGHT__', UI['theme_light']).replace('__DARK__', UI['theme_dark'])}</script>
</body>
</html>
'''

os.makedirs(args.out, exist_ok=True)
open(os.path.join(args.out, 'index.html'), 'w').write(page)
for theme in ('light', 'dark'):
    d = os.path.join(args.out, 'figs', args.lang, theme)
    if os.path.isdir(d):
        shutil.rmtree(d)
    shutil.copytree(os.path.join(ROOT, 'figs', args.lang, theme), d,
                    ignore=shutil.ignore_patterns('*.svg'))
n_fig = page.count('<figure')
n_xref = page.count('class="xref"')
print(f'{os.path.relpath(args.out, ROOT)}/index.html：{len(toc)} 个目录项，{n_fig} 张图，{n_xref} 处交叉引用')
