"""effA_ktrace.sh 的结果：每次调用在 ANE 任务结束后的各阶段耗时（中位数，µs）。

用法：python3 effA_stages.py <effA_kt 目录>
阶段（同 memory.md C2j）：
  任务结束(0126) → 固件发消息(00b8) → 中断处理(0020) → 完成标记(00a0, arg1=1) → 驱动完成(0170) → 用户返回(0024) → 下次提交(01a9)
双 ANE 时取两个引擎中较晚结束的 0126。
"""
import glob
import os
import sys

import numpy as np

d = sys.argv[1]
names = ["结束→发消息", "消息→中断", "中断→完成标记", "驱动完成处理", "用户线程返回", "返回→下次提交", "合计(结束→下次提交)"]
print(f"{'层数':>4} " + " ".join(f"{n:>10}" for n in names) + "   n")
for f in sorted(glob.glob(os.path.join(d, "*.txt")), key=lambda p: int(os.path.basename(p)[:-4]) if os.path.basename(p)[:-4].isdigit() else 0):
    name = os.path.basename(f)[:-4]
    if not name.isdigit():
        continue
    ev = []
    for l in open(f):
        p = l.split()
        if len(p) >= 3:
            ev.append((int(p[0]) / 24.0, p[1], p[2]))
    ev.sort()
    stages = []
    i = 0
    # 以提交事件 01a9 切分每次调用
    subs = [k for k, e in enumerate(ev) if e[1] == "61b01a9"]
    for a, b in zip(subs[:-1], subs[1:]):
        seg = ev[a:b + 1]
        ends = [t for t, i_, _ in seg if i_ == "61b0126"]
        if not ends:
            continue
        te = max(ends)
        after = [(t, i_, x) for t, i_, x in seg if t >= te]

        def first(idd, cond=lambda x: True, t0=te):
            for t, i_, x in after:
                if i_ == idd and t >= t0 and cond(x):
                    return t
            return None
        t1 = first("61b00b8")
        t2 = first("61b0020", t0=t1 or te)
        t3 = first("61b00a0", lambda x: x == "1", t0=t2 or te)
        t4 = first("61b0170", t0=t3 or te)
        t5 = first("61b0024", t0=t4 or te)
        t6 = seg[-1][0]
        if None in (t1, t2, t3, t4, t5):
            continue
        stages.append([t1 - te, t2 - t1, t3 - t2, t4 - t3, t5 - t4, t6 - t5, t6 - te])
    if not stages:
        continue
    m = np.median(np.array(stages), axis=0)
    print(f"{name:>4} " + " ".join(f"{x:10.1f}" for x in m) + f"   {len(stages)}")
