"""lldb 脚本：跟踪 anecc 编译时 ZinAneTd<24u> 的每个方法调用，记录参数、调用者、调用层级，
以及该调用前后 TD 对象中按寄存器地址换算的每个字的变化。

用法：lldb --batch -o "command script import tdtrace_lldb.py" -o "dt_run <输出.jsonl>" -- ./anecc <mlmodelc> <out> h18g
不用 lldb 的断点回调：编译器是多线程的，几个线程同时停下时回调偶尔不执行，进程会停住。
改为脚本自己循环：继续运行 -> 停下 -> 逐个处理停在断点上的线程（入口 / 返回 / ANECCompile）-> 继续。
寄存器地址 -> setter 对象偏移（ZinAneTdHw_v24::GetRegisterValueFromAddress 反汇编，+8 为 ZinAneTd 中硬件对象的位置）。
"""
import json
import lldb

BLOCKS = [(0x0000, 0x0016, 0x238), (0x1040, 0x106a, 0x400), (0x1140, 0x114f, 0x4b4), (0x1240, 0x124d, 0x4fc),
          (0x1340, 0x1396, 0x29c), (0x1440, 0x145c, 0x53c), (0x1540, 0x1594, 0x3c), (0x1640, 0x164d, 0x5b8)]
SPAN = 0x600
OUT = None
stack = {}      # 线程 -> [(记录, 入口快照, 返回地址)]
exit_bps = {}   # 返回地址 -> 断点（永久、不限线程；编译器是多线程的，一次性 / 限线程的断点会让进程停住）
seq = [0]


def snap(proc, obj):
    err = lldb.SBError()
    b = proc.ReadMemory(obj, SPAN, err)
    if not err.Success() or b is None:
        return None
    words = {}
    for lo, hi, off in BLOCKS:
        for r in range(lo, hi + 1):
            o = off + 4 * (r - lo)
            words[r] = int.from_bytes(b[o:o + 4], "little")
    return words


def on_entry(frame, bp_loc, extra, internal_dict):
    try:
        _entry(frame)
    except Exception as e:  # 任何异常都继续运行，否则 lldb 会停住
        print("entry error", e, flush=True)
    return False


def _entry(frame):
    thread = frame.GetThread()
    proc = thread.GetProcess()
    target = proc.GetTarget()
    reg = lambda n: frame.FindRegister(n).GetValueAsUnsigned()
    obj = reg("x0")
    caller = thread.GetFrameAtIndex(1)
    cname = caller.GetFunctionName() or "?"
    coff = caller.GetPC() - caller.GetSymbol().GetStartAddress().GetLoadAddress(target) if caller.GetSymbol() else 0
    seq[0] += 1
    rec = {"i": seq[0], "fn": frame.GetFunctionName(), "caller": f"{cname}+{coff}",
           "args": [reg("x1"), reg("x2"), reg("x3")], "d0": frame.FindRegister("d0").GetValue(),
           "obj": obj, "depth": len(stack.get(thread.GetThreadID(), []))}
    s0 = snap(proc, obj)
    lr = reg("lr") & 0x0000ffffffffffff       # 去掉指针认证位
    stack.setdefault(thread.GetThreadID(), []).append((rec, s0, lr))
    if lr not in exit_bps:
        exit_bps[lr] = target.BreakpointCreateByAddress(lr)


def on_exit(frame, bp_loc, extra, internal_dict):
    try:
        _exit(frame)
    except Exception as e:
        print("exit error", e, flush=True)
    return False


def _exit(frame):
    thread = frame.GetThread()
    st = stack.get(thread.GetThreadID())
    if not st or st[-1][2] != frame.GetPC():  # 不是本线程栈顶那次调用的返回点（别的线程或别的调用经过这里）
        return
    rec, s0, _ = st.pop()
    s1 = snap(thread.GetProcess(), rec["obj"])
    if s0 and s1:
        rec["diff"] = [[r, s0[r], s1[r]] for r in s0 if s0[r] != s1[r]]
    rec["ret"] = frame.FindRegister("x0").GetValueAsUnsigned()
    rec["tid"] = thread.GetIndexID()
    OUT.write(json.dumps(rec) + "\n")


MAIN_BP = [None]


def on_compile(frame, bp_loc, extra, internal_dict):
    try:
        _compile()
    except Exception as e:
        print("compile error", e, flush=True)
    return False


def _compile():
    """ANECCompile 入口：ANECompiler 已加载。禁用"地址实际属于别的函数"的断点位置（相同代码合并），
    只留 ZinAneTd<24u> 自己的函数。"""
    bp = MAIN_BP[0]
    keep = off = 0
    for i in range(bp.GetNumLocations()):
        loc = bp.GetLocationAtIndex(i)
        name = loc.GetAddress().GetSymbol().GetName() or ""
        if name.startswith("ZinAneTd<24u>::"):
            keep += 1
        else:
            loc.SetEnabled(False); off += 1
    print(f"断点：保留 {keep}，禁用 {off}（与其他函数共用地址）", flush=True)


def dt_run(debugger, command, result, internal_dict):
    global OUT
    OUT = open(command.strip() or "trace.jsonl", "w", buffering=1)
    debugger.SetAsync(False)
    target = debugger.GetSelectedTarget()
    bp = target.BreakpointCreateByRegex(r"^ZinAneTd<24u>::")
    MAIN_BP[0] = bp
    cb = target.BreakpointCreateByName("ANECCompile")
    err = lldb.SBError()
    proc = target.Launch(debugger.GetListener(), None, None, None, None, None, None, 0, False, err)
    if not err.Success():
        print("launch failed", err); return
    while proc.GetState() == lldb.eStateStopped:
        for th in proc:
            if th.GetStopReason() != lldb.eStopReasonBreakpoint:
                continue
            bid = th.GetStopReasonDataAtIndex(0)
            fr = th.GetFrameAtIndex(0)
            try:
                if bid == cb.GetID():
                    _compile(); cb.SetEnabled(False)
                elif bid == bp.GetID():
                    _entry(fr)
                else:
                    _exit(fr)
            except Exception as e:
                print("handler error", e, flush=True)
        proc.Continue()
    print("进程结束，状态", proc.GetState(), "退出码", proc.GetExitStatus(), flush=True)


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand("command script add -f tdtrace_lldb.dt_run dt_run")
