"""lldb 脚本：以 h18g 编译时，在 ZinIrHal2026BaseLine::GetParams() 第一次返回后，对参数表的指定偏移设读观察点
（arm64 一次最多 4 个），记录每次读取它们的函数（名字 + 偏移），用来给静态扫描找不到读取者的 HAL 字段命名。

用法：lldb --batch -o "command script import halwatch_lldb.py" -o "hw_run <偏移,偏移,...> <输出>" -- ./anecc <mlmodelc> <out> h18g
输出：每行"偏移<TAB>读取函数<TAB>次数"。每个偏移最多记录 200 次命中后删除其观察点，避免拖慢编译。
"""
import collections
import lldb


def hw_run(debugger, command, result, internal_dict):
    offs_s, outp = command.split()
    offs = [int(x, 16) for x in offs_s.split(",")]
    debugger.SetAsync(False)
    target = debugger.GetSelectedTarget()
    gp = target.BreakpointCreateByName("ZinIrHal2026BaseLine::GetParams() const")
    err = lldb.SBError()
    proc = target.Launch(debugger.GetListener(), None, None, None, None, None, None, 0, False, err)
    ret_bp, base, wps = None, None, {}
    hits = collections.Counter()
    per = collections.Counter()
    while proc.GetState() == lldb.eStateStopped:
        for th in proc:
            r = th.GetStopReason()
            fr = th.GetFrameAtIndex(0)
            if r == lldb.eStopReasonBreakpoint:
                bid = th.GetStopReasonDataAtIndex(0)
                if bid == gp.GetID() and ret_bp is None and base is None:
                    lr = fr.FindRegister("lr").GetValueAsUnsigned() & 0x0000ffffffffffff
                    ret_bp = target.BreakpointCreateByAddress(lr)
                elif ret_bp is not None and bid == ret_bp.GetID() and base is None:
                    base = fr.FindRegister("x0").GetValueAsUnsigned()
                    for o in offs:
                        wp = target.WatchAddress(base + o, 1, True, False, err)
                        if err.Success():
                            wps[wp.GetID()] = o
                        else:
                            print("watch failed", hex(o), err, flush=True)
                    target.BreakpointDelete(ret_bp.GetID()); gp.SetEnabled(False)
            elif r == lldb.eStopReasonWatchpoint:
                wid = th.GetStopReasonDataAtIndex(0)
                o = wps.get(wid)
                sym = fr.GetSymbol()
                name = (fr.GetFunctionName() or "?").split("(")[0]
                off = fr.GetPC() - sym.GetStartAddress().GetLoadAddress(target) if sym else 0
                if o is not None:
                    hits[(o, f"{name}+{off}")] += 1
                    per[o] += 1
                    if per[o] >= 200:
                        target.DeleteWatchpoint(wid)
        proc.Continue()
    with open(outp, "w") as f:
        for (o, fn), n in sorted(hits.items()):
            f.write(f"{o:#06x}\t{fn}\t{n}\n")
    print("watch", [hex(o) for o in offs], "命中", sum(hits.values()), flush=True)


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand("command script add -f halwatch_lldb.hw_run hw_run")
