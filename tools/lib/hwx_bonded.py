#!/usr/bin/env python3
"""总结 h18g HWX 中 nonbonded / bonded 两套过程：运行时操作序列、各 ANE 的 TD 流长度和差异。

用法：hwx_bonded.py model.hwx [--diff]
"""
import re
import struct
import sys


def load(path):
    b = open(path, "rb").read()
    _, _, sub, _, ncmds, _, _, _ = struct.unpack_from("<8I", b, 0)
    segs, syms = {}, []
    o = 32
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<2I", b, o)
        if cmd == 0x19:
            name = b[o + 8:o + 24].split(b"\0")[0].decode()
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from("<4Q", b, o + 24)
            segs[name] = (vmaddr, vmsize, fileoff, filesize)
        elif cmd == 0x2:
            symoff, nsyms, stroff, _ = struct.unpack_from("<4I", b, o + 8)
            for k in range(nsyms):
                strx, ntype, nsect, _, val = struct.unpack_from("<IBBHQ", b, symoff + 16 * k)
                e = b.index(b"\0", stroff + strx)
                syms.append((val, ntype, nsect, b[stroff + strx:e].decode("latin1")))
        o += size
    return b, sub, segs, syms


def vm_bytes(b, segs, addr, n):
    for vmaddr, vmsize, fileoff, filesize in segs.values():
        if vmaddr <= addr < vmaddr + filesize:
            o = fileoff + addr - vmaddr
            return b[o:o + n]
    return b""


def main(path, show_diff):
    b, sub, segs, syms = load(path)
    print(f"{path}: subtype {sub}, segments {list(segs)}")
    if "__RUNTIME" not in segs:
        print("  传统格式，没有 bonded")
        return
    rv = segs["__RUNTIME"]
    rt = sorted((v, n) for v, t, s, n in syms if rv[0] <= v < rv[0] + rv[1] and t & 0x0e == 0x0e)
    procs = [n for v, n in rt if re.fullmatch(r"main(__\w+)?", n)]
    print("  过程:", procs)
    for flavor in ("nonbonded", "bonded"):
        ops = [n for v, n in rt if n.endswith(flavor) or f"_{flavor}_" in n or f"_{flavor}__" in n]
        kicks = [n for n in ops if "ane_kick" in n]
        other = sorted({re.sub(r"_(main__\w+?)(_|$).*", "", n) for n in ops})
        print(f"  [{flavor}] 运行时操作 {len(ops)} 个，kick {len(kicks)} 个: {kicks}")
        print(f"      操作类型: {other}")
    starts = sorted((v, n) for v, t, s, n in syms if n.startswith("text_section_start_for_"))
    text_end = segs["__TEXT"][0] + segs["__TEXT"][3]
    streams = {}
    for i, (v, n) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else text_end
        d = vm_bytes(b, segs, v, end - v)
        used = len(d.rstrip(b"\0"))
        key = n.replace("text_section_start_for_", "")
        streams[key] = d[:used + (-used % 4)]
        print(f"  TD 流 {key:32s} @ {v:#x}  {used:#x} 字节")
    if show_diff and len(streams) >= 3:
        keys = list(streams)
        nb = next(k for k in keys if "nonbonded" in k)
        a0 = next(k for k in keys if "ane0" in k and "nonbonded" not in k)
        a1 = next(k for k in keys if "ane1" in k)
        x, y, z = streams[nb], streams[a0], streams[a1]
        n = max(len(x), len(y), len(z))
        word = lambda d, i: struct.unpack_from("<I", d, i)[0] if i + 4 <= len(d) else None
        cnt = 0
        for i in range(0, n, 4):
            p, q, r = word(x, i), word(y, i), word(z, i)
            if not (p == q == r):
                f = lambda v: "--------" if v is None else f"{v:08x}"
                print(f"    {i:#06x}  nb {f(p)}  a0 {f(q)}  a1 {f(r)}")
                cnt += 1
                if cnt > 80:
                    print("    ...")
                    break


if __name__ == "__main__":
    main(sys.argv[1], "--diff" in sys.argv)
