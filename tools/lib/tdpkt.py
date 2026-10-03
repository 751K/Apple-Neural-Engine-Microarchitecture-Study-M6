"""按包头解析 HWX 指令流中的 TD（2026-10-03 解出的格式，见 hwx_h18g.md §11）。

用法：python3 tdpkt.py <model.hwx> [流名过滤] [TD 数=1]
格式：每个 TD 开头 12 个字是任务头（不解析），之后是一串包：
  包头低 15 位 = 起始寄存器的字地址；
  bit 31 = 0：连续写，bits 15–30 = 个数 − 1，其后跟"个数"个值；
  bit 31 = 1：按掩码写，bits 15–30 = 16 位掩码，写基址本身以及基址 + 1 + i（掩码第 i 位为 1），其后跟 1 + popcount(掩码) 个值。
  TD 结束的判断是近似的：遇到 0、下一个任务头（1 后跟 3 个 0），或 bit 31 = 0 且 bits 26–30 非零的字（如 0x23009346，含义未知）。
"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import struct
import sys
sys.path.insert(0, __import__("os").path.dirname(__file__) or ".")
import hwx_bonded as hb


def words(path, flt=None):
    b, sub, segs, syms = hb.load(path)
    s = segs["__TEXT"]
    d = hb.vm_bytes(b, segs, s[0], s[3])
    return [struct.unpack_from("<I", d, k)[0] for k in range(0, len(d) - 3, 4)]


def parse(w, start=0):
    """从 start 起解析一个 TD，返回 ([(地址, 值)], 下一个 TD 的起点)。"""
    regs = []
    i = start + 12
    while i < len(w):
        h = w[i]
        if h == 0 or (h == 1 and w[i + 1:i + 4] == [0, 0, 0]) or (not h >> 31 and (h >> 26) & 31):
            break  # 连续写的个数不会超过 2048；bits 26–30 非零的字（如 0x23009346）不是包头，暂视为 TD 结束
        addr = h & 0x7fff
        f = (h >> 15) & 0xffff
        if h >> 31:
            addrs = [addr] + [addr + 1 + k for k in range(16) if f >> k & 1]
        else:
            addrs = [addr + k for k in range(f + 1)]
        vals = w[i + 1:i + 1 + len(addrs)]
        regs += list(zip(addrs, vals))
        i += 1 + len(addrs)
    while i < len(w) and w[i] == 0:
        i += 1
    return regs, i


if __name__ == "__main__":
    w = words(sys.argv[1])
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    p = 0
    for t in range(n):
        regs, p2 = parse(w, p)
        print(f"TD {t} @ {4 * p:#x}：{len(regs)} 个寄存器")
        for a, v in regs:
            print(f"  {a:#06x}  {v:08x}")
        p = p2
