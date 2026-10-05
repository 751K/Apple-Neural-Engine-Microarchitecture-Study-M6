"""lldb 脚本：跟踪 ANE 编译器交换文件（anecompiler.swap.*）的创建、删除、扩容、映射和写入，记录参数与调用栈。

用法：lldb --batch -o "command script import swaptrace_lldb.py" -o "sw_run <输出>" -- ./anecc <模型目录> <out> h18g
输出（每行一条 JSON）：系统调用名、参数、返回值、调用栈（前 30 帧的函数名）。交换文件是 ZinIrFileBacking：创建后立即 unlink，
以 ftruncate + mmap 使用（存放转成 float32 的常量 ZinIrConstData<float>），不走 write；所以另按调用者汇总 mmap 字节数。write / pwrite / ftruncate / mmap
只记录目标是交换文件的调用（按文件描述符过滤）。最后汇总：按"调用栈第一个 ANECompiler 帧"分组的写入字节数。
"""
import collections
import json
import lldb

CALLS = ["mkstemp", "mkstemps", "mkostemp", "mkostemps", "unlink", "ftruncate", "mmap", "write", "pwrite", "close"]


def stack(th, n=30):
    out = []
    for i in range(min(n, th.GetNumFrames())):
        f = th.GetFrameAtIndex(i)
        out.append((f.GetFunctionName() or "?").split("(")[0][:90])
    return out


def sw_run(debugger, command, result, internal_dict):
    outp = command.strip()
    fo = open(outp, "w", buffering=1)
    debugger.SetAsync(False)
    target = debugger.GetSelectedTarget()
    bps = {target.BreakpointCreateByName(c, "libsystem_kernel.dylib" if c not in ("mkstemp", "mkstemps", "mkostemp", "mkostemps") else "libsystem_c.dylib").GetID(): c
           for c in CALLS}
    err = lldb.SBError()
    proc = target.Launch(debugger.GetListener(), None, None, None, None, None, None, 0, False, err)
    pending = {}            # 返回断点 id -> (调用名, 记录)
    swap_fds = set()
    bytes_by = collections.Counter()
    nwrite = collections.Counter()
    mm_by = collections.Counter(); mm_n = collections.Counter()
    SKIP = ("ZinIrFileBacking", "ANECCreateFileBacking", "details::ZinIrMappedData", "ZinIrConstData", "std::", "mmap", "__")
    while proc.GetState() == lldb.eStateStopped:
        for th in proc:
            if th.GetStopReason() != lldb.eStopReasonBreakpoint:
                continue
            bid = th.GetStopReasonDataAtIndex(0)
            fr = th.GetFrameAtIndex(0)
            reg = lambda n: fr.FindRegister(n).GetValueAsUnsigned()
            if bid in pending:
                name, rec = pending.pop(bid)
                target.BreakpointDelete(bid)
                rec["ret"] = reg("x0")
                if name.startswith("mk") and rec.get("swap"):
                    swap_fds.add(rec["ret"])
                fo.write(json.dumps(rec) + "\n")
                continue
            name = bps.get(bid)
            if name is None:
                continue
            x0, x1, x2 = reg("x0"), reg("x1"), reg("x2")
            rec = {"call": name}
            want = False
            if name.startswith("mk") or name == "unlink":
                path = proc.ReadCStringFromMemory(x0, 1024, err) if x0 else ""
                rec["path"] = path
                rec["swap"] = "swap" in path
                want = rec["swap"]
            elif name in ("write", "pwrite", "ftruncate", "close"):
                rec.update(fd=x0, size=x2 if name != "ftruncate" else x1)
                want = x0 in swap_fds
                if want and name in ("write", "pwrite"):
                    st = stack(th)
                    key = next((s for s in st if not s.startswith(("write", "pwrite", "__"))), "?")
                    bytes_by[key] += x2; nwrite[key] += 1
                    if sum(nwrite.values()) > 40:      # 前 40 次写入记完整调用栈，之后只计数
                        continue
            elif name == "mmap":
                fd = reg("x4")
                rec.update(len=x1, prot=x2, flags=reg("x3"), fd=fd)
                want = fd in swap_fds
                if want:
                    st = stack(th)
                    key = " < ".join([s for s in st if not s.startswith(SKIP)][:3])
                    mm_by[key] += x1; mm_n[key] += 1
            if want:
                rec["stack"] = stack(th)
                lr = reg("lr") & 0x0000ffffffffffff
                rb = target.BreakpointCreateByAddress(lr)
                rb.SetThreadID(th.GetThreadID())
                pending[rb.GetID()] = (name, rec)
        proc.Continue()
    fo.write(json.dumps({"summary_bytes_by_caller": bytes_by, "writes_by_caller": nwrite, "swap_fds": list(swap_fds),
                         "mmap_bytes_by_caller": mm_by, "mmap_count_by_caller": mm_n}) + "\n")
    print("交换文件 fd", swap_fds, "写入", sum(bytes_by.values()), "字节", flush=True)


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand("command script add -f swaptrace_lldb.sw_run sw_run")
