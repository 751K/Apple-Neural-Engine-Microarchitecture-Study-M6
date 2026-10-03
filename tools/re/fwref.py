"""在 ANE 固件的 otool 反汇编（ane0.dis）里找引用某些地址（字符串等）的指令，按 adrp + add/ldr 配对计算目标地址。只读分析。

用法：python3 fwref.py <ane0.dis> <十六进制 vmaddr> [...]
输出：引用处地址、所在函数的起始地址（向前找 pacibsp / stp x29,x30 序言）。
"""
import re
import sys

dis, targets = sys.argv[1], {int(a, 16) for a in sys.argv[2:]}
lines = [l.rstrip("\n").split("\t") for l in open(dis) if re.match(r"^[0-9a-f]{16}\t", l)]
addr = [int(l[0], 16) for l in lines]
page = {}
starts = []
for i, l in enumerate(lines):
    ins = " ".join(l[1:])
    if ins.startswith("pacibsp") or (ins.startswith("stp") and "x29, x30" in ins and "pre" not in ins and "]!" in ins):
        if not starts or addr[i] - starts[-1] > 8:
            starts.append(addr[i])
    m = re.match(r"adrp\s+(x\d+), .*?; 0x([0-9a-f]+)", ins)
    if m:
        page[m.group(1)] = int(m.group(2), 16)
        continue
    m = re.match(r"add\s+(x\d+), (x\d+), #0x([0-9a-f]+)", ins)
    if m and m.group(2) in page:
        t = page[m.group(2)] + int(m.group(3), 16)
        if t in targets:
            fs = max([s for s in starts if s <= addr[i]], default=0)
            print(f"{t:#x} 被 {addr[i]:#x} 引用（函数约始于 {fs:#x}）")
