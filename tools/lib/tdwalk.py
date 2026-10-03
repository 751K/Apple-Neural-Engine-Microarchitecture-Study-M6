"""按 TD 头的长度字段逐个遍历 h18g（v24）指令流中的 TD，输出头部各字、标志字和地址包。

用法：python3 tdwalk.py <model.hwx> [流名过滤=nonbonded]
TD 布局（hwx_h18g.md §11.4）：流开头 4 个字是流头；TD 第 0 字 = 编号（低 16 位）| 长度（bits 16–26，字）；
TD + 0x20 为标志字；之后是寄存器包。地址包：bit 31 = 0、bit 29 = 1，bits 23–28 标签。TD 之间以 0 补齐到 16 字节。
"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import sys
sys.path.insert(0, __import__("os").path.dirname(__file__) or ".")
import td_widths as tw


def walk(w):
    p = 4 if w[:4] == [1, 0, 0, 0] else 0
    while p < len(w):
        while p < len(w) and w[p] == 0:
            p += 1
        if p >= len(w):
            break
        size = (w[p] >> 16) & 0x7ff
        if size == 0:
            break
        td = w[p:p + size]
        regs, addrpk = [], []
        i = 9
        while i < len(td):
            h = td[i]
            a, f = h & 0x7fff, (h >> 15) & 0xffff
            if h >> 31:
                addrs = [a] + [a + 1 + k for k in range(16) if f >> k & 1]
            else:
                n = (f & 0x3f) + 1
                addrs = [a + k for k in range(n)]
                if (h >> 29) & 1:
                    addrpk.append((a, ((h >> 21) & 0xff) >> 2, (h >> 21) & 3, td[i + 1:i + 1 + n]))
            regs += list(zip(addrs, td[i + 1:i + 1 + len(addrs)]))
            i += 1 + len(addrs)
        yield p, td[:9], dict(regs), addrpk
        p += size


if __name__ == "__main__":
    flt = sys.argv[2] if len(sys.argv) > 2 else "nonbonded"
    for name, w in tw.streams(sys.argv[1]).items():
        if flt not in name:
            continue
        print(f"== {name}")
        for p, hdr, regs, ap in walk(w):
            print(f"  @{4 * p:#06x} 编号 {hdr[0] & 0xffff:3d} 长 {(hdr[0] >> 16) & 0x7ff:3d} | +4 {hdr[1]:08x} +8 {hdr[2]:08x} +c {hdr[3]:08x} +10 {hdr[4]:08x} +14 {hdr[5]:08x} +18 {hdr[6]:08x} +1c {hdr[7]:08x} 标志 {hdr[8]:08x} | "
                  + " ".join(f"[{a:#x} 标签{t} {'/'.join(hex(x) for x in v)}]" for a, t, _, v in ap))
