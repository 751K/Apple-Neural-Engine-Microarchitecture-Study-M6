"""HWX 中所有 __KERN_<n> 段（权重和调色板）的文件大小之和，以及段数。单个段超过 128 MB 时编译器拆成多个段。

用法：python3 hwx_kern.py <model.hwx>    输出：<字节数> <段数>
"""
import struct
import sys

b = open(sys.argv[1], "rb").read()
ncmds = struct.unpack_from("<8I", b, 0)[4]
o, total, n = 32, 0, 0
for _ in range(ncmds):
    cmd, size = struct.unpack_from("<2I", b, o)
    if cmd == 0x19 and b[o + 8:o + 24].rstrip(b"\0").startswith(b"__KERN_"):
        total += struct.unpack_from("<4Q", b, o + 24)[3]   # filesize
        n += 1
    o += size
print(total, n)
