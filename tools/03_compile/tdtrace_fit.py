"""汇总 tdtrace.sh 的跟踪记录：每个 ZinAneTd<24u> 方法改了哪些寄存器的哪些位、各模型里收到的参数、调用者。

用法：python3 tdtrace_fit.py <tdtrace 目录> [输出目录，默认同目录]
输出：
  setters.txt   每个方法：调用次数、改动的寄存器位（各次调用前后快照的异或之并；值没变的写入看不到）、
                参数第 1 个（x1，按 32 位）在各模型的取值、直接调用者
  regmap.txt    每个寄存器：各方法改动过的位
  matrix.txt    方法 × 模型：该模型里出现过的 x1 取值（看调用条件）
只统计"叶子"调用对自身写入的归属：Handle* 等会调用其他方法的函数，其异或里减去子调用改动的位。
"""
import collections
import glob
import json
import os
import re
import sys

d = sys.argv[1]
od = sys.argv[2] if len(sys.argv) > 2 else d
short = lambda n: re.sub(r"^ZinAneTd<24u>::", "", n.split("(")[0])

calls = collections.Counter()
bits = collections.defaultdict(lambda: collections.defaultdict(int))
argv = collections.defaultdict(lambda: collections.defaultdict(set))
callers = collections.defaultdict(collections.Counter)
models = []
for f in sorted(glob.glob(os.path.join(d, "*.jsonl"))):
    m = os.path.basename(f)[:-6]
    models.append(m)
    recs = [json.loads(l) for l in open(f)]
    # 退出顺序记录：子调用先于父调用写出。按对象、层级把子调用的改动从父调用里扣掉
    child = collections.defaultdict(lambda: collections.defaultdict(int))   # (对象, 层级) -> 寄存器 -> 子调用改动位
    for r in recs:
        n = short(r["fn"])
        calls[n] += 1
        x1 = r["args"][0] & 0xffffffff
        argv[n][m].add(x1)
        c = r["caller"].split("+")[0]
        callers[n][short(c) if c.startswith("ZinAneTd<24u>::") else re.sub(r"\(.*", "", c)[:60]] += 1
        key, own = (r["obj"], r["depth"]), {}
        for reg, a, b in r.get("diff", []):
            own[reg] = (a ^ b) & ~child[key].get(reg, 0)
        for reg, v in own.items():
            if v:
                bits[n][reg] |= v
        up = child[(r["obj"], r["depth"] - 1)]
        for reg, a, b in r.get("diff", []):
            up[reg] |= a ^ b
        child.pop(key, None)


def fmt_args(n):
    vals = collections.defaultdict(list)
    for m in models:
        if m in argv[n]:
            vals[tuple(sorted(argv[n][m]))].append(m)
    out = []
    for v, ms in sorted(vals.items(), key=lambda kv: -len(kv[1])):
        vs = ",".join(f"{x:#x}" if x > 9 else str(x) for x in v[:6]) + ("…" if len(v) > 6 else "")
        out.append(f"{vs} [{len(ms)} 个模型{'' if len(ms) > 4 else '：' + ' '.join(ms)}]")
    return "；".join(out)


with open(os.path.join(od, "setters.txt"), "w") as fo:
    fo.write(f"# {len(models)} 个模型：{' '.join(models)}\n")
    for n in sorted(calls):
        regs = ", ".join(f"{reg:#06x}:{v:#x}" for reg, v in sorted(bits[n].items()))
        top = ", ".join(f"{c}×{k}" for c, k in callers[n].most_common(3))
        fo.write(f"{n}\n    调用 {calls[n]}  改动 {regs or '—'}\n    x1 {fmt_args(n)}\n    调用者 {top}\n")

regmap = collections.defaultdict(lambda: collections.defaultdict(int))
for n, rv in bits.items():
    for reg, v in rv.items():
        regmap[reg][n] |= v
with open(os.path.join(od, "regmap.txt"), "w") as fo:
    for reg in sorted(regmap):
        fo.write(f"{reg:#06x}\n")
        for n, v in sorted(regmap[reg].items(), key=lambda kv: (kv[1] & -kv[1], kv[0])):
            lo = (v & -v).bit_length() - 1
            hi = v.bit_length() - 1
            fo.write(f"    位 {lo:2d}-{hi:2d}  {v:#010x}  {n}\n")

with open(os.path.join(od, "matrix.txt"), "w") as fo:
    fo.write("方法\t" + "\t".join(models) + "\n")
    for n in sorted(calls):
        row = []
        for m in models:
            v = sorted(argv[n].get(m, []))
            row.append("" if not v else ",".join(str(x) if x < 1 << 16 else "*" for x in v[:3]) + ("…" if len(v) > 3 else ""))
        fo.write(n + "\t" + "\t".join(row) + "\n")
print(f"{len(models)} 个模型，{len(calls)} 个方法，{sum(calls.values())} 次调用；输出 setters.txt、regmap.txt、matrix.txt")
