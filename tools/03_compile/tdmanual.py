"""把三份数据合成 TD 寄存器手册（M6 / h18g，ZinAneTd<24u>）：
  静态位掩码（tools/re/tdstatic.py 的输出）、动态跟踪（tdtrace.sh 的 *.jsonl：参数、调用者）、
  各模型 HWX 中的实际寄存器值（tdtrace.sh 存的 *.hwx）。

用法：python3 tdmanual.py <static.tsv> <tdtrace 目录> > manual.md
每个寄存器一节；每个位段一行：位、负责的方法（静态写这些位的方法）、各模型 HWX 中该位段的取值（取值: 模型…）、
跟踪到的 x1 参数、调用者。HWX 里出现但没有任何方法静态写入的寄存器单列（由 TD 生成之外的代码写，如地址 / 重定位）。
"""
import collections
import glob
import json
import os
import re
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib")]
import td_widths as tw  # noqa: E402
import tdwalk  # noqa: E402

static = collections.defaultdict(list)          # 寄存器 -> [(掩码, 方法)]
for l in open(sys.argv[1]):
    fn, reg, mask, _ = l.rstrip("\n").split("\t")
    static[int(reg, 16)].append((int(mask, 16), fn))
d = sys.argv[2]
short = lambda n: re.sub(r"^ZinAneTd<24u>::", "", n.split("(")[0])

hw = collections.defaultdict(lambda: collections.defaultdict(set))   # 寄存器 -> 模型 -> 取值集合
args = collections.defaultdict(lambda: collections.defaultdict(set))
callers = collections.defaultdict(collections.Counter)
models = []
for f in sorted(glob.glob(os.path.join(d, "*.jsonl"))):
    m = os.path.basename(f)[:-6]
    models.append(m)
    for l in open(f):
        r = json.loads(l)
        n = short(r["fn"])
        args[n][m].add(r["args"][0] & 0xffffffff)
        c = r["caller"].split("+")[0]
        callers[n][short(c) if c.startswith("ZinAneTd<24u>::") else re.sub(r"\(.*", "", c)[:50]] += 1
    h = os.path.join(d, m + ".hwx")
    if os.path.exists(h):
        for k, w in tw.streams(h).items():
            st = {}
            for _, hd, regs, _ in tdwalk.walk(w):
                st.update(regs)
                for reg, v in st.items():
                    hw[reg][m].add(v)


def runs(mask):
    """掩码拆成连续位段 [(lsb, msb)]。"""
    out, b = [], 0
    while mask >> b:
        if mask >> b & 1:
            e = b
            while mask >> (e + 1) & 1:
                e += 1
            out.append((b, e)); b = e + 1
        else:
            b += 1
    return out


def vals(reg, lsb, msb):
    by = collections.defaultdict(list)
    for m in models:
        if m in hw[reg]:
            vs = tuple(sorted({(v >> lsb) & ((1 << (msb - lsb + 1)) - 1) for v in hw[reg][m]}))
            by[vs].append(m)
    parts = []
    for vs, ms in sorted(by.items(), key=lambda kv: -len(kv[1])):
        s = "/".join(f"{x:#x}" if x > 9 else str(x) for x in vs[:4]) + ("…" if len(vs) > 4 else "")
        parts.append(f"{s}（{len(ms)}" + ("" if len(ms) > 5 else "：" + " ".join(ms)) + "）")
    return "；".join(parts) or "—"


def argstr(fn):
    by = collections.defaultdict(list)
    for m in models:
        if m in args[fn]:
            by[tuple(sorted(args[fn][m]))].append(m)
    if not by:
        return "未调用"
    parts = []
    for vs, ms in sorted(by.items(), key=lambda kv: -len(kv[1]))[:4]:
        s = "/".join(f"{x:#x}" if x > 9 else str(x) for x in vs[:3]) + ("…" if len(vs) > 3 else "")
        parts.append(f"{s}（{len(ms)}" + ("" if len(ms) > 4 else "：" + " ".join(ms)) + "）")
    return "；".join(parts)


print(f"# M6（h18g）TD 寄存器手册：静态位掩码 + 动态跟踪 + {len(models)} 个模型的 HWX 取值\n")
for reg in sorted(set(static) | set(hw)):
    if reg not in static:
        continue
    print(f"## {reg:#06x}\n")
    print("| 位 | 方法 | HWX 取值（模型数：模型） | 跟踪到的参数 x1 | 调用者 |")
    print("|---|---|---|---|---|")
    seg = collections.defaultdict(list)
    for mask, fn in static[reg]:
        for lsb, msb in runs(mask):
            seg[(lsb, msb)].append(fn)
    for (lsb, msb), fns in sorted(seg.items()):
        fns = sorted(set(fns), key=lambda n: (not n.startswith("Set"), n))
        main = fns[0]
        cl = ", ".join(f"{c}×{k}" for c, k in callers[main].most_common(2)) or "—"
        print(f"| {lsb}–{msb} | {' / '.join(fns[:3])}{'…' if len(fns) > 3 else ''} | {vals(reg, lsb, msb)} | {argstr(main)} | {cl} |")
    print()
others = sorted(r for r in hw if r not in static)
print("## 没有方法静态写入的寄存器（TD 生成之外写入）\n")
print(", ".join(f"{r:#06x}" for r in others))
