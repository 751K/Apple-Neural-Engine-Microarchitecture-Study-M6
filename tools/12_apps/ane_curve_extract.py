#!/usr/bin/env python3
# 从整机测评的 ANE 资源曲线记录中提取忙碌比例与读内存速率（第 14.3 节、图 14-1）。
# 输入：测评记录中的采集目录（anemon.jsonl：anemon 约 0.25–0.31 s 一次的采样；phases.txt：各阶段的起止时刻）。
# 输出：data/12_apps/ane_curve/<名>.csv，每行一个采样：
#   t_s（相对预填充开始的秒数）、phase（idle_before / prefill / decode / idle_after）、
#   busy_pct（各 ANE 忙碌比例的平均；M4 只有一个 ANE）、busy_ane0、busy_ane1、
#   dram_read_gbs、dram_clipped_pct（M6 的读带宽来自直方图，落在最高档的采样比例，非 0 时读数只是下限）。
# 用法：python3 tools/12_apps/ane_curve_extract.py <采集目录> <名> [<采集目录> <名> ...]
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
OUT = os.path.join(ROOT, 'data', '12_apps', 'ane_curve')


def extract(d, name):
    ph = {}
    for line in open(os.path.join(d, 'phases.txt')):
        if line.startswith('PHASE'):
            f = line.split()
            ph[f[1]] = (float(f[2]), float(f[3]))
    t0 = ph['prefill'][0]
    lo, hi = ph['idle_before'][0] - 1, ph['idle_after'][1] + 1
    rows = []
    for line in open(os.path.join(d, 'anemon.jsonl')):
        if ' {' not in line:
            continue
        t, js = line.split(' ', 1)
        t = float(t)
        if not lo <= t <= hi:
            continue
        x = json.loads(js)
        busy = [b or 0 for b in x['ane_busy_pct']]
        phase = next((k for k, (a, b) in ph.items() if a <= t <= b), '')
        clip = x.get('dram_clipped_pct')
        rows.append((t - t0, phase, sum(busy) / len(busy), busy[0], busy[1] if len(busy) > 1 else '',
                     x['dram_read_gbs'] or 0, '' if clip is None else clip))
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name + '.csv')
    with open(p, 'w') as fh:
        fh.write('# 来源：%s；预填充 %.2f s，解码 %.2f s\n' % (os.path.basename(os.path.normpath(d)),
                 ph['prefill'][1] - ph['prefill'][0], ph['decode'][1] - ph['decode'][0]))
        fh.write('t_s,phase,busy_pct,busy_ane0,busy_ane1,dram_read_gbs,dram_clipped_pct\n')
        for r in rows:
            fh.write(','.join(f'{v:.3f}' if isinstance(v, float) else str(v) for v in r) + '\n')
    print(p, len(rows))


args = sys.argv[1:]
for i in range(0, len(args), 2):
    extract(args[i], args[i + 1])
