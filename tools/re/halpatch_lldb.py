"""lldb 脚本：以 h18g 编译时，在 ZinIrHal2026BaseLine::GetParams() 第一次返回后，把参数表里指定的 8 字节字
改成另一张表（如 M4 的 hal_H16g.bin）的值，然后在指定的 ZinAneTd<24u> setter 处记录参数 x1。
用来二分"哪个 HAL 字段决定某个编译决策"（例如 DetectZeros 只在 M6 上打开）。

用法：lldb --batch -o "command script import halpatch_lldb.py" -o "hp_run <字偏移列表文件> <替换表.bin> <setter 名> <输出>" \
        -- ./anecc <mlmodelc> <out> h18g
字段列表文件：每行"十六进制偏移 [宽度]"；为空则不改（对照）。不要改指针字段（表名、vector 的起止地址），编译器会卡死。输出：setter 每次调用的 x1，空格分隔。
"""
import lldb


def hp_run(debugger, command, result, internal_dict):
    words_file, repl_bin, setter, outp = command.split()
    words = []                         # 每行："偏移" 或 "偏移 宽度"（宽度默认 8）
    for l in open(words_file):
        if l.strip():
            p = l.split()
            words.append((int(p[0], 16), int(p[1]) if len(p) > 1 else 8))
    repl = open(repl_bin, "rb").read()
    debugger.SetAsync(False)
    target = debugger.GetSelectedTarget()
    gp = target.BreakpointCreateByName("ZinIrHal2026BaseLine::GetParams() const")
    sb = target.BreakpointCreateByRegex(r"^ZinAneTd<24u>::" + setter + r"\(")
    err = lldb.SBError()
    proc = target.Launch(debugger.GetListener(), None, None, None, None, None, None, 0, False, err)
    ret_bp, patched, vals = None, False, []
    while proc.GetState() == lldb.eStateStopped:
        for th in proc:
            if th.GetStopReason() != lldb.eStopReasonBreakpoint:
                continue
            bid = th.GetStopReasonDataAtIndex(0)
            fr = th.GetFrameAtIndex(0)
            if bid == gp.GetID() and not patched and ret_bp is None:
                lr = fr.FindRegister("lr").GetValueAsUnsigned() & 0x0000ffffffffffff
                ret_bp = target.BreakpointCreateByAddress(lr)
            elif ret_bp is not None and bid == ret_bp.GetID() and not patched:
                base = fr.FindRegister("x0").GetValueAsUnsigned()
                for w, n in words:
                    proc.WriteMemory(base + w, repl[w:w + n], err)
                    if not err.Success():
                        print("write failed", hex(w), err, flush=True)
                patched = True
                target.BreakpointDelete(ret_bp.GetID()); gp.SetEnabled(False)
            elif bid == sb.GetID():
                vals.append(fr.FindRegister("x1").GetValueAsUnsigned() & 0xffffffff)
        proc.Continue()
    open(outp, "w").write(" ".join(map(str, vals)) + "\n")
    print("patched", patched, "values", vals[:8], flush=True)


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand("command script add -f halpatch_lldb.hp_run hp_run")
