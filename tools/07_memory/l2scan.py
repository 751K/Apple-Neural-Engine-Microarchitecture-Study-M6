"""【注意：本工具的寄存器映射有误——0x134x 是 Tile DMA 源（DRAM）寄存器，不是 L2 块，见 hwx_h18g.md §11.4；保留作记录】
在 h18g HWX 的 nonbonded 流中找写 L2 块（0x1340–0x1367）的包，收集 L2 源 / 结果的基址与跨步（v24 映射，见 memory.md C1d）。

用法：python3 l2scan.py <model.hwx> [流名过滤，默认 nonbonded]
寄存器（v24，硬件地址）：0x1348 源基址、0x1349 源通道跨步、0x134a 源行跨步、0x134d 第二源基址、0x134e 第二源通道跨步、
  0x1357 结果基址、0x1358 结果通道跨步、0x1359 结果行跨步、0x135c 结果配置。地址 / 跨步为字节（bit 4 起 17 位）。
方法：扫描流中所有字，凡是包头（低 15 位地址在 0x1340–0x1367；连续写个数 ≤ 40；bits 26–30 为 0 或 bit 31 = 1）就解码。
"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import sys
sys.path.insert(0, __import__("os").path.dirname(__file__) or ".")
import td_widths as tw

NAMES = {0x1348: "源基址", 0x1349: "源通道跨步", 0x134a: "源行跨步", 0x134d: "源2基址", 0x134e: "源2通道跨步",
         0x1357: "结果基址", 0x1358: "结果通道跨步", 0x1359: "结果行跨步", 0x135c: "结果配置"}


def scan(w):
    out = []
    for i, h in enumerate(w):
        a = h & 0x7fff
        if not (0x1340 <= a <= 0x1367):
            continue
        f = (h >> 15) & 0xffff
        if h >> 31:
            addrs = [a] + [a + 1 + k for k in range(16) if f >> k & 1]
        elif (h >> 26) & 31 or f > 40:
            continue
        else:
            addrs = [a + k for k in range(f + 1)]
        vals = w[i + 1:i + 1 + len(addrs)]
        out.append((4 * i, dict(zip(addrs, vals))))
    return out


if __name__ == "__main__":
    st = tw.streams(sys.argv[1])
    flt = sys.argv[2] if len(sys.argv) > 2 else "nonbonded"
    for name, w in st.items():
        if flt not in name:
            continue
        print(f"== {name}")
        for off, r in scan(w):
            print(f"  @{off:#06x} " + "  ".join(f"{NAMES.get(a, hex(a))}={v:#x}" for a, v in sorted(r.items())))
