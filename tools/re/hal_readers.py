#!/usr/bin/env python3
"""从反汇编中找出各函数读取 ZinIrHalParameters 的偏移。

输入：funcs.idx（序号 + mangled 名）、funcs.dis（llvm-objdump 输出）
输出：hal_readers.json  {偏移: [[宽度, 函数名], ...]}

做法：按签名确定参数表是第几个参数（成员函数多一个 this），
线性扫描跟踪持有"表基址 + 常量"的寄存器，记录 [reg, #imm] 形式的读取。
不跟踪分支和内存中转，结果是近似的。
"""
import json
import re
import subprocess
import sys
from collections import defaultdict

CXXFILT = "/Library/Developer/CommandLineTools/usr/bin/c++filt"

idx = {}
for line in open("funcs.idx"):
    k, name = line.rstrip("\n").split(" ", 1)
    idx[int(k)] = name
mangled = [idx[k] for k in sorted(idx)]
demangled = subprocess.run([CXXFILT], input="\n".join(m[1:] for m in mangled),
                           capture_output=True, text=True).stdout.split("\n")

# 有构造函数或虚表的作用域视为类
allsyms = open("allsyms.txt").read()


def top_params(sig):
    """返回最外层括号内的参数列表。"""
    start = None
    depth = 0
    for i, ch in enumerate(sig):
        if ch == "(" and start is None and depth == 0:
            start = i
            break
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
    if start is None:
        return []
    params, cur, d = [], "", 0
    for ch in sig[start + 1:]:
        if ch in "(<[":
            d += 1
        elif ch in ")>]":
            if d == 0:
                break
            d -= 1
        if ch == "," and d == 0:
            params.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        params.append(cur.strip())
    return params


def is_member(m, dem):
    if m.startswith("__ZNK"):
        return True
    if not m.startswith("__ZN"):
        return False
    scope = dem.split("(")[0].rsplit("::", 1)[0]
    scope = re.sub(r"<.*", "", scope)
    if not scope or " " in scope:
        return False
    enc = f"{len(scope)}{scope}" if "::" not in scope else None
    if enc and (f"__ZTV{enc}" in allsyms or f"__ZN{enc}C2" in allsyms or f"__ZN{enc}C1" in allsyms):
        return True
    return False


def hal_arg_regs(m, dem):
    params = top_params(dem)
    regs = []
    gp = 1 if is_member(m, dem) else 0
    for p in params:
        if p in ("float", "double"):
            continue
        if "ZinIrHalParameters" in p and ("&" in p or "*" in p):
            regs.append(gp)
        gp += 1
    return [r for r in regs if r < 8]


LOAD = re.compile(r"^\s*[0-9a-f]+:\s+(ld\w*)\s+(.*)$")
INS = re.compile(r"^\s*[0-9a-f]+:\s+(\S+)\s*(.*)$")
WIDTH = {"ldrb": 1, "ldrsb": 1, "ldurb": 1, "ldursb": 1, "ldrh": 2, "ldrsh": 2, "ldurh": 2, "ldursh": 2,
         "ldrsw": 4, "ldursw": 4}


def regname(r):
    r = r.strip()
    if r.startswith("w"):
        return "x" + r[1:]
    return r


func_lines = defaultdict(list)
cur = None
for line in open("funcs.dis"):
    m = re.match(r"^[0-9a-f]+ <(\w+)>:", line)
    if m:
        lab = m.group(1)
        cur = 0 if lab == "ltmp0" else (int(lab[1:]) if re.fullmatch(r"f\d+", lab) else None)
        continue
    if cur is not None:
        func_lines[cur].append(line)

readers = defaultdict(set)
for k in sorted(idx):
    m, dem = mangled[k], demangled[k] if k < len(demangled) else ""
    regs = hal_arg_regs(m, dem)
    if not regs:
        continue
    track = {f"x{r}": 0 for r in regs}
    short = re.sub(r"\(.*", "", dem)
    for line in func_lines.get(k, []):
        mi = INS.match(line)
        if not mi:
            continue
        op, args = mi.group(1), mi.group(2).split("//")[0].strip()
        ops = [a.strip() for a in re.split(r",(?![^\[]*\])", args)]
        if op.startswith("ld") and "[" in args:
            mm = re.search(r"\[(x\d+|sp)(?:,\s*#(-?0x[0-9a-f]+|-?\d+))?\]", args)
            if mm and mm.group(1) in track:
                imm = int(mm.group(2), 0) if mm.group(2) else 0
                off = track[mm.group(1)] + imm
                if op in WIDTH:
                    w = WIDTH[op]
                else:
                    d = ops[0]
                    w = 8 if d.startswith("x") or d.startswith("d") else 4 if d.startswith(("w", "s")) else 16 if d.startswith("q") else 8
                if op.startswith("ldp"):
                    readers[off].add((w, short))
                    readers[off + w].add((w, short))
                else:
                    readers[off].add((w, short))
            # 目标寄存器被覆盖
            for d in ops[:2 if op.startswith("ldp") else 1]:
                track.pop(regname(d), None)
            continue
        if op == "mov" and len(ops) == 2 and regname(ops[1]) in track and ops[0].startswith("x"):
            track[regname(ops[0])] = track[regname(ops[1])]
            continue
        if op == "add" and len(ops) == 3 and regname(ops[1]) in track and ops[2].startswith("#"):
            track[regname(ops[0])] = track[regname(ops[1])] + int(ops[2][1:], 0)
            continue
        if op in ("bl", "blr", "blraa", "blraaz", "blrab", "blrabz"):
            for r in range(19):
                track.pop(f"x{r}", None)
            continue
        if ops and re.fullmatch(r"[xw]\d+", ops[0]) and not op.startswith(("st", "cmp", "cmn", "tst", "cb", "tb", "b.", "ccmp")):
            track.pop(regname(ops[0]), None)

out = {hex(o): sorted(v, key=lambda t: t[1]) for o, v in sorted(readers.items()) if 0 <= o < 0xa10}
json.dump(out, open("hal_readers.json", "w"), indent=1, ensure_ascii=False)
print(len(out), "offsets with readers")
