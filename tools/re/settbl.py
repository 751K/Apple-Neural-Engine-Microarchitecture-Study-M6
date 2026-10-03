"""从 otool 反汇编（fnbytes 导出的 ZinAneTd<31> 函数）中提取：函数名 → (对象偏移, 起始位, 位宽, 指令)。"""
import re, sys
names = {}
for line in open(sys.argv[1]):
    m = re.match(r"; FUNC (\d+) (\S+)", line)
    if m: names[f"f{m.group(1)}"] = m.group(2)
cur = None; rows = []; off = None
for line in open(sys.argv[2]):
    m = re.match(r"^(f\d+):", line)
    if m: cur = names.get(m.group(1)); off = None; continue
    m = re.search(r"ldr\s+w\d+, \[x\d+, #(0x[0-9a-f]+)\]", line)
    if m: off = int(m.group(1), 16)
    m = re.search(r"\b(bfi|bfxil)\s+w\d+, w\d+, #(\d+), #(\d+)", line)
    if m and cur and off is not None:
        rows.append((off, int(m.group(2)), int(m.group(3)), m.group(1), cur))
import itertools
dem = lambda n: re.sub(r"^__ZN8ZinAneTdILj31EE\d+", "", n).split("E")[0]
for off, lsb, w, ins, n in sorted(set(rows)):
    if 0x240 <= off <= 0x2c0:
        print(f"{off:#06x}  位 {lsb:2d}-{lsb + w - 1:2d}  {dem(n)}")
