"""列出 HWX 中 __text 的重定位项，并对照指令流里"bit 29 包"（地址类寄存器写入）。

用法：python3 hwxreloc.py <model.hwx>
背景（hwx_h18g.md §11.4）：bit 31 = 0 且 bit 29 = 1 的包头是"地址包"：低 15 位寄存器地址，bits 15–20 个数 − 1，bits 23–28 标签。
权重 DMA 基址（0x1544/0x1545，64 位）在 __text 中有对 __kern_0 节的 8 字节重定位；输入 / 输出张量的地址包由 __runtime 在运行时绑定。
"""
import struct
import sys

b = open(sys.argv[1], "rb").read()
ncmds = struct.unpack_from("<I", b, 16)[0]
off, secs, symtab, names = 32, {}, None, []
for _ in range(ncmds):
    cmd, sz = struct.unpack_from("<II", b, off)
    if cmd == 0x19:
        for j in range(struct.unpack_from("<I", b, off + 64)[0]):
            so = off + 72 + 80 * j
            sn = b[so:so + 16].rstrip(b"\0").decode()
            names.append(sn)
            secs[sn] = struct.unpack_from("<QQI", b, so + 32) + struct.unpack_from("<II", b, so + 56)
    if cmd == 0x2:
        symtab = struct.unpack_from("<IIII", b, off + 8)
    off += sz
addr, size, fo, reloff, nrel = secs["__text"]
W = lambda o: struct.unpack_from("<I", b, fo + o)[0]
print(f"__text：{nrel} 个重定位（节号从 1 起：{', '.join(f'{i + 1}={n}' for i, n in enumerate(names))}）")
for k in range(nrel):
    ra, ri = struct.unpack_from("<iI", b, reloff + 8 * k)
    tgt = ri & 0xffffff
    h = W(ra - 4)
    pk = f"包头 {h:08x} 寄存器 {h & 0x7fff:#06x} 标签 {((h >> 21) & 0xff) >> 2}" if (h >> 29) & 1 and not h >> 31 else "前一字不是地址包"
    print(f"  @{ra:#07x} {1 << ((ri >> 25) & 3)} 字节 → {'符号' if (ri >> 27) & 1 else '节'} {tgt}  值 {W(ra):#x}  | {pk}")
