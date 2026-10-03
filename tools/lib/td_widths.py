"""从 h18g HWX 的 TD 流中读出每块的列数（片上切块的宽度），以及 ANE0 / ANE1 流的差异。

用法：python3 td_widths.py <model.hwx> [--diff]
方法：每个卷积 TD 中，0x104 型的字 = 本块列数（4 个字之后的 0x114 型字与之相等，紧随其后的 0x10c 型字 = 通道数）。
只适用于 H=1 的 1×1 卷积链这类简单模型（见 memory.md C1c）。
"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import difflib
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import hwx_bonded as hb  # noqa: E402


def streams(path):
    b, sub, segs, syms = hb.load(path)
    starts = sorted((v, n) for v, t, s, n in syms if n.startswith("text_section_start_for_"))
    end = segs["__TEXT"][0] + segs["__TEXT"][3]
    out = {}
    for i, (v, n) in enumerate(starts):
        e = starts[i + 1][0] if i + 1 < len(starts) else end
        d = hb.vm_bytes(b, segs, v, e - v)
        u = len(d.rstrip(b"\0"))
        d = d[:u + (-u % 4)]
        out[n.replace("text_section_start_for_", "")] = [struct.unpack_from("<I", d, k)[0] for k in range(0, len(d), 4)]
    return out


def widths(w):
    return [w[i] for i in range(len(w) - 4) if 64 <= w[i] <= 20000 and w[i] % 16 == 0 and w[i + 4] == w[i]
            and w[i + 2] < w[i] and w[i + 2] >= 16]


if __name__ == "__main__":
    st = streams(sys.argv[1])
    for k in sorted(st, key=lambda s: ("nonbonded" not in s, s)):
        ws = widths(st[k])
        print(f"{k:28s} 流长 {4 * len(st[k]):#06x}  各 TD 列数 {ws}")
    if "--diff" in sys.argv:
        a0 = next(v for k, v in st.items() if "ane0" in k and "nonbonded" not in k)
        a1 = next(v for k, v in st.items() if "ane1" in k)
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a0, a1, autojunk=False).get_opcodes():
            if tag != "equal" and not (tag == "replace" and i2 - i1 == j2 - j1 <= 2):
                print(f"  {tag:7s} ANE0[{4*i1:#06x}] {' '.join(f'{v:08x}' for v in a0[i1:i2][:10])} | ANE1[{4*j1:#06x}] {' '.join(f'{v:08x}' for v in a1[j1:j2][:10])}")
