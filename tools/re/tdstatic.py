"""静态提取 ZinAneTd<N> 每个方法写的寄存器位：跟踪"ldr 对象字 -> and / orr / bfi / bfxil -> str 回同一偏移"，
把清零与置位用到的位并起来作为该方法管的位掩码，并按寄存器地址 -> 对象偏移表换算成寄存器地址。

用法：python3 tdstatic.py <fnbytes 导出的 .s> <otool -tv 反汇编> > static.tsv
输出列：方法  寄存器  掩码（十六进制）  来源指令种类
对象偏移表（v24，setter 所见偏移；来自 ZinAneTdHw_v24::GetRegisterValueFromAddress，+8）。
"""
import re
import subprocess
import sys

BLOCKS = [(0x0000, 0x0016, 0x238), (0x1040, 0x106a, 0x400), (0x1140, 0x114f, 0x4b4), (0x1240, 0x124d, 0x4fc),
          (0x1340, 0x1396, 0x29c), (0x1440, 0x145c, 0x53c), (0x1540, 0x1594, 0x3c), (0x1640, 0x164d, 0x5b8)]


def off2reg(o):
    for lo, hi, base in BLOCKS:
        if base <= o <= base + 4 * (hi - lo) and (o - base) % 4 == 0:
            return lo + (o - base) // 4
    return None


names = {}
for l in open(sys.argv[1]):
    m = re.match(r"; FUNC (\d+) (\S+)", l)
    if m:
        names[f"f{m.group(1)}"] = m.group(2)
dem = dict(zip(names, subprocess.run(["c++filt", "-_"], input="\n".join(names.values()), capture_output=True,
                                     text=True).stdout.split("\n")))
M32 = 0xffffffff
out = {}
cur = None
for line in open(sys.argv[2]):
    m = re.match(r"^(f\d+):", line)
    if m:
        cur = m.group(1); tie = {}; acc = {}; this = {"x0"}; kinds = {}
        continue
    if cur is None:
        continue
    ins = line.split("\t", 1)[-1].strip()
    op = ins.split("\t")[0].split()[0] if ins else ""
    args = ins[len(op):].strip()
    mm = re.match(r"mov\s+(x\d+), x0$", ins)
    if mm:
        this.add(mm.group(1)); continue
    mm = re.match(r"ldr\s+(w\d+), \[(x\d+), #(0x[0-9a-f]+)\]$", ins)
    if mm and mm.group(2) in this:
        tie[mm.group(1)] = int(mm.group(3), 16); acc[mm.group(1)] = 0; continue
    mm = re.match(r"(and|orr|eor)\s+(w\d+), (w\d+), #(0x[0-9a-f]+|\d+)$", ins)
    if mm and mm.group(3) in tie:
        d, s, imm = mm.group(2), mm.group(3), int(mm.group(4), 0)
        mask = (~imm & M32) if mm.group(1) == "and" else imm
        tie[d] = tie[s]; acc[d] = acc.get(s, 0) | mask; kinds[d] = kinds.get(s, "") + mm.group(1)[0]
        continue
    mm = re.match(r"orr\s+(w\d+), (w\d+), (w\d+)$", ins)
    if mm and (mm.group(2) in tie or mm.group(3) in tie):
        s = mm.group(2) if mm.group(2) in tie else mm.group(3)
        tie[mm.group(1)] = tie[s]; acc[mm.group(1)] = acc.get(s, 0); kinds[mm.group(1)] = kinds.get(s, "") + "o"
        continue
    mm = re.match(r"(bfi|bfxil)\s+(w\d+), (w\d+|wzr), #(\d+), #(\d+)$", ins)
    if mm and mm.group(2) in tie:
        lsb, w = int(mm.group(4)), int(mm.group(5))
        mask = ((1 << w) - 1) << (lsb if mm.group(1) == "bfi" else 0)
        acc[mm.group(2)] = acc.get(mm.group(2), 0) | mask; kinds[mm.group(2)] = kinds.get(mm.group(2), "") + "b"
        continue
    mm = re.match(r"str\s+(w\d+|wzr), \[(x\d+), #(0x[0-9a-f]+)\]$", ins)
    if mm and mm.group(2) in this:
        o = int(mm.group(3), 16); r = mm.group(1)
        mask = acc.get(r, 0) if r in tie and tie[r] == o else M32     # 直接写整字（常量或别处算好的值）
        k = kinds.get(r, "") if r in tie and tie[r] == o else "w"
        reg = off2reg(o)
        if reg is not None:
            key = (dem[cur], reg)
            pm, pk = out.get(key, (0, ""))
            out[key] = (pm | mask, pk + k)
for (fn, reg), (mask, k) in sorted(out.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    if mask:
        print(f"{re.sub(r'^ZinAneTd<24u>::', '', fn.split('(')[0])}\t{reg:#06x}\t{mask:#010x}\t{''.join(sorted(set(k)))}")
