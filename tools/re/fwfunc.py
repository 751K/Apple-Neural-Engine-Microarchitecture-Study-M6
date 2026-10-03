"""打印 ANE 固件某个函数的反汇编（来自 otool 的 ane0.dis），把 adrp + add 指向的字符串注释出来。只读分析。

用法：python3 fwfunc.py <ane0.dis> <固件.bin> <起始 vmaddr 十六进制> [最多指令数=200]
固件为 RTKit Mach-O：__TEXT vmaddr 0 对应文件偏移 0x4000。
"""
import re
import sys

dis, fw, start = sys.argv[1], open(sys.argv[2], "rb").read(), int(sys.argv[3], 16)
n = int(sys.argv[4]) if len(sys.argv) > 4 else 200


def cstr(va):
    off = va + 0x4000
    if not (0 <= off < len(fw)):
        return None
    e = fw.find(b"\0", off, off + 200)
    s = fw[off:e]
    return s.decode("latin1") if e > off and all(32 <= c < 127 or c in (9, 10) for c in s) else None


page, out, on = {}, 0, False
for l in open(dis):
    m = re.match(r"^([0-9a-f]{16})\t(.*)", l.rstrip("\n"))
    if not m:
        continue
    a = int(m.group(1), 16)
    if a < start:
        continue
    ins = m.group(2).replace("\t", " ")
    note = ""
    mm = re.match(r"adrp\s+(x\d+), .*?; 0x([0-9a-f]+)", ins)
    if mm:
        page[mm.group(1)] = int(mm.group(2), 16)
    mm = re.match(r"add\s+(x\d+), (x\d+), #0x([0-9a-f]+)", ins)
    if mm and mm.group(2) in page:
        t = page[mm.group(2)] + int(mm.group(3), 16)
        s = cstr(t)
        note = f"  ; {t:#x}" + (f' "{s[:90]}"' if s else "")
    print(f"{a:#7x}  {ins}{note}")
    out += 1
    if out >= n or (out > 3 and ins.startswith("ret")):
        break
