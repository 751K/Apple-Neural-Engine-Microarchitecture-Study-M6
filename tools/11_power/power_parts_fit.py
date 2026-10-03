"""分析 power_parts.py 的输出（E5）。

用法：python3 power_parts_fit.py <目录>
每种负载取三个时间窗的平均：
  稳态：负载开始后 4 s（模型加载 + 0.5 s 空闲基线 + 1 s 预热之后）到结束前 0.3 s；
  上电空闲：负载结束后 1.2–4.8 s（IOP 仍在 Running、没有任务；SMC 约 1 s 刷新，前 1 s 可能还是负载读数）；
  断电：结束后 7 s 以后（IOP 约 5.7 s 断电）。
每次调用的工作量（乘加 / 逐元素运算 / DRAM 字节）按模型形状给出，用 bondrun 正式运行的中位耗时折算成速率。
"""
import glob
import os
import re
import sys

D = sys.argv[1]
KEYS = ["PP0b", "PP2b", "PP4b", "PZD1", "PSTR", "PPSR", "PHPC"]
# 每次调用：乘加数、PE 逐元素运算数、DRAM 读字节（权重 / 激活，粗估）
MAC384 = 512 * 512 * 128 * 384
WORK = {
    "f16_single": dict(mac=MAC384),
    "f16_single_zero": dict(mac=MAC384),
    "f16_dual": dict(mac=2 * MAC384),
    "q8_single": dict(mac8=MAC384),
    "f16_small": dict(mac=512 * 512 * 128 * 16),
    "f16_L48": dict(mac=512 * 512 * 128 * 48),
    "f16_L128": dict(mac=512 * 512 * 128 * 128),
    "f16_L256": dict(mac=512 * 512 * 128 * 256),
    "weightbw": dict(mac=512 * 512 * 16 * 192, dram=512 * 512 * 2 * 192),
    "pe_add": dict(pe=256 * 64 * 64 * 96),
    "pe_add_zero": dict(pe=256 * 64 * 64 * 96),
    "pe_mul": dict(pe=256 * 64 * 64 * 64),
    "tdma_add2": dict(),
    "f16_duty50": dict(mac=MAC384),
    "f16_duty20": dict(mac=MAC384),
}


def load(tag):
    rows = [list(map(float, l.split())) for l in open(f"{D}/{tag}.trace") if l.strip()]
    ts, te, iters, _ = open(f"{D}/{tag}.marks").read().split()
    br = open(f"{D}/{tag}.bondrun.txt").read()
    med = float(br.split("中位数")[1].split()[0]) if "中位数" in br else None
    return rows, float(ts), float(te), int(iters), med


def avg(rows, a, b):
    """返回 [PP0b 或 ANE 净功耗, 其余键...]。pclus 格式（第 2 列为 P 核簇瓦数）时第 0 项为 PP0b − P 核簇。"""
    sel = [r for r in rows if a <= r[0] <= b]
    if not sel:
        return [float("nan")] * len(KEYS)
    pc = len(sel[0]) == len(KEYS) + 2
    off = 2 if pc else 1
    v = [sum(r[off + j] for r in sel) / len(sel) for j in range(len(KEYS))]
    if pc:
        v[0] -= sum(r[1] for r in sel) / len(sel)
    return v


def pclus(rows, a, b):
    sel = [r for r in rows if a <= r[0] <= b and len(r) == len(KEYS) + 2]
    return sum(r[1] for r in sel) / len(sel) if sel else float("nan")


print(f"{'负载':16s} {'耗时us':>7s} {'ANE稳态':>7s} {'ANE上电空闲':>10s} {'ANE断电':>7s} {'DRAM2b+4b':>9s} {'PZD1':>6s} "
      f"{'整机':>6s} {'整机断电':>7s} {'速率':>16s} {'(ANE−上电空闲)/速率':>18s}")
tags = sorted((os.path.basename(f)[:-6] for f in glob.glob(f"{D}/*.marks")), key=lambda t: os.path.getmtime(f"{D}/{t}.marks"))
for tag in tags:
    base = re.sub(r"_r\d+$", "", tag)
    sl = re.match(r"f16_sl(\d+)$", base)
    rows, ts, te, iters, med = load(tag)
    st = avg(rows, ts + 4, te - 0.3)
    on = avg(rows, te + 1.2, te + 4.8)
    off = avg(rows, te + 7, te + 99)
    if len(rows[0]) == len(KEYS) + 2:  # ANE 净功耗 = (PP0b − P 核簇) − 断电时的同一差值
        st[0] -= off[0]; on[0] -= off[0]
        extra_pc = f" P核簇 {pclus(rows, ts + 4, te - 0.3):5.2f} W，断电差值 {off[0]:+.2f}"
    else:
        extra_pc = ""
    w = WORK.get(base, dict(mac=MAC384) if sl else {})
    sleep = int(sl.group(1)) if sl else {"f16_duty50": 1600, "f16_duty20": 6400}.get(base, 0)
    period = (med + sleep) * 1e-6 if med else None  # 每次调用（含间隔）的秒数
    rate, unit, e = "", "", ""
    for k, u, scale in (("mac", "TMAC/s", 1e12), ("mac8", "T int8 MAC/s", 1e12), ("pe", "G 元素/s", 1e9),
                        ("dram", "GB/s", 1e9)):
        if k in w and period:
            r = w[k] / period
            rate = f"{r / scale:7.2f} {u}"
            pj = (st[0] - on[0]) / r * 1e12
            e = f"{pj:7.3f} pJ/{'MAC' if 'mac' in k else ('元素' if k == 'pe' else 'B')}"
            break
    print(f"{tag:16s} {med or 0:7.1f} {st[0]:7.2f} {on[0]:10.2f} {off[0]:7.2f} {st[1] + st[2]:9.2f} {st[3]:6.2f} "
          f"{st[4]:6.2f} {off[4]:7.2f} {rate:>16s} {e:>18s}{extra_pc}")
