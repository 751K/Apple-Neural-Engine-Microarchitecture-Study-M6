#!/usr/bin/env python3
"""解析 ANE 编译产物 HWX（magic 0xbeefface 的 Mach-O 变体）。

用法：hwx_parse.py model.hwx
打印头部、各 load command（段、节、线程、note、ident、符号表）。
"""
import struct
import sys

LC = {0x19: "LC_SEGMENT_64", 0x2: "LC_SYMTAB", 0x4: "LC_THREAD", 0x5: "LC_UNIXTHREAD",
      0x8: "LC_IDENT", 0x31: "LC_NOTE", 0x40: "LC_0x40", 0x6: "LC_LOAD_DYLINKER?", 0xb: "LC_DYSYMTAB"}


def cstr(b, o, n=None):
    e = b.find(b"\0", o, o + n if n else len(b))
    return b[o:e if e >= 0 else (o + n if n else len(b))].decode("latin1")


def printable_strings(b, minlen=4):
    out, cur = [], b""
    for ch in b:
        if 32 <= ch < 127:
            cur += bytes([ch])
        else:
            if len(cur) >= minlen:
                out.append(cur.decode())
            cur = b""
    if len(cur) >= minlen:
        out.append(cur.decode())
    return out


def main(path):
    b = open(path, "rb").read()
    magic, cpu, sub, ftype, ncmds, sizeofcmds, flags, _ = struct.unpack_from("<8I", b, 0)
    print(f"file {path} size {len(b)}")
    print(f"magic {magic:#x} cputype {cpu:#x} subtype {sub} filetype {ftype} ncmds {ncmds} sizeofcmds {sizeofcmds:#x} flags {flags:#x}")
    o = 32
    for i in range(ncmds):
        cmd, size = struct.unpack_from("<2I", b, o)
        name = LC.get(cmd, hex(cmd))
        if cmd == 0x19:
            seg = cstr(b, o + 8, 16)
            vmaddr, vmsize, fileoff, filesize, maxp, initp, nsects, fl = struct.unpack_from("<4Q4I", b, o + 24)
            print(f"[{i}] {name} {seg:10s} vm {vmaddr:#x}+{vmsize:#x} file {fileoff:#x}+{filesize:#x} prot {maxp}/{initp} nsects {nsects}")
            so = o + 72
            for _ in range(nsects):
                sect = cstr(b, so, 16)
                addr, ssize, soff, align, reloff, nreloc, sfl = struct.unpack_from("<2Q5I", b, so + 32)
                print(f"      sect {sect:12s} addr {addr:#x} size {ssize:#x} off {soff:#x} align 2^{align} flags {sfl:#x}")
                so += 80
        elif cmd == 0x2:
            symoff, nsyms, stroff, strsize = struct.unpack_from("<4I", b, o + 8)
            print(f"[{i}] {name} nsyms {nsyms} symoff {symoff:#x} stroff {stroff:#x} strsize {strsize:#x}")
            for k in range(nsyms):
                strx, ntype, nsect, ndesc, nval = struct.unpack_from("<IBBHQ", b, symoff + 16 * k)
                print(f"      sym type {ntype:#04x} sect {nsect} desc {ndesc:#06x} value {nval:#x}  {cstr(b, stroff + strx)}")
        else:
            body = b[o + 8:o + size]
            strs = printable_strings(body)
            words = struct.unpack_from(f"<{min(12, (size - 8) // 4)}I", b, o + 8)
            print(f"[{i}] {name} size {size:#x} words {' '.join(f'{w:x}' for w in words)}")
            for s in strs[:12]:
                print(f"      str: {s[:200]}")
        o += size


if __name__ == "__main__":
    main(sys.argv[1])
