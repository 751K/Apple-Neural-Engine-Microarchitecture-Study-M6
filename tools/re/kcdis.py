"""从 kernelcache（Mach-O fileset）里按文件偏移截取一个函数并反汇编（只读）。

用法（M6）：python3 kcdis.py <kc.bin> <文件偏移> <对应 vmaddr> [最多指令数=300]
向前找到最近的 PACIBSP（d503237f）或 BTI c（d503245f）作为函数开头，向后到下一个同类指令或指令数上限为止。
"""
import os
import struct
import subprocess
import sys
import tempfile

kc, fo, vm = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16)
n = int(sys.argv[4]) if len(sys.argv) > 4 else 300
b = open(kc, "rb").read()
if os.environ.get("WIN"):  # 窗口模式：WIN=前,后（字节），不找函数边界
    pre, post = (int(x, 0) for x in os.environ["WIN"].split(","))
    s, e = fo - pre, fo + post
else:
  s = fo
  while struct.unpack_from("<I", b, s)[0] not in (0xd503237f, 0xd503245f):  # PACIBSP 或 BTI c
    s -= 4
  e = s + 4
  while e - s < 4 * n:
    w = struct.unpack_from("<I", b, e)[0]
    if w in (0xd503237f, 0xd503245f) and e > s + 8:
        break
    e += 4
d = tempfile.mkdtemp()
src, obj = os.path.join(d, "f.s"), os.path.join(d, "f.o")
with open(src, "w") as f:
    f.write(".text\n" + "".join(".long %#x\n" % struct.unpack_from("<I", b, k)[0] for k in range(s, e, 4)))
subprocess.run(["clang", "-c", "-arch", "arm64e", src, "-o", obj], check=True)
base = vm - (fo - s)
out = subprocess.run(["objdump", "-d", "--no-show-raw-insn", "--adjust-vma=%#x" % base, obj], capture_output=True, text=True).stdout
print("; 函数 文件 %#x–%#x，vm %#x" % (s, e, base))
print("\n".join(out.splitlines()[6:]))
