"""解析 Core ML（E5 编译器）分段器写出的 analytics.mil，并用"常数切换代价 + 逐运算估计耗时"的最短路径模型复现它的后端选择。

analytics.mil 由 opd_ana 流程收集（每个模型一个，见 notes/coreml_dispatch.md §2）：每个运算带
  BackendSupport（可用后端）、EstimatedRuntime（各后端估计耗时，ms）、SelectedBackend（选中的后端）；
函数头带图级常数：Launch_<后端>_ms、Src_<a>_Dest_<b>_ms。

用法：
  python opdispatch_fit.py ops <analytics.mil> ...   逐运算打印：模型 运算 输出名 选中后端 可用后端 各后端估计
  python opdispatch_fit.py fit <analytics.mil> ...   用模型复现选择，统计完全一致 / 代价相同（平局）/ 不一致
模型（拟合结果）：一段 ANE 计启动 0.125 ms；相邻两段后端不同时计切换 0.125 ms；图的最后一段在 ANE 上再计 0.125 ms
（输出回到 CPU 缓冲）；图的输入不计。CPU 类后端（bnns / classic_cpu）之间的切换按同样的 0.125 ms 计。
运算按文件中的顺序当作一条链（多输入的图是近似）。
"""
import glob
import re
import sys

OPRE = re.compile(r"^\s*(\S.*?) (\w+) = ([\w:]+)\((.*)\)\[(BackendSupport.*)\];\s*$")
LAUNCH_ANE = 0.125
SWITCH = 0.125
END_ANE = 0.125


def parse(f):
    ops = []
    for line in open(f):
        m = OPRE.match(line)
        if not m:
            continue
        typ, out, op, _args, meta = m.groups()
        sup = re.search(r'BackendSupport = list<string, \d+>\(\[(.*?)\]\)', meta).group(1)
        sup = [x.strip('" ') for x in sup.split(",") if "unsupported" not in x]
        est = re.search(r'EstimatedRuntime = dict<string, fp64>\(\{(.*?)\}\)', meta)
        est = {k: float(v) for k, v in re.findall(r'\{"(\w+)", ([0-9.e+-]+)\}', est.group(1) + "}")} if est else {}
        sel = re.search(r'SelectedBackend = string\("(\w+)"\)', meta).group(1)
        ops.append(dict(out=out, op=op, type=typ, sup=sup, est=est, sel=sel))
    return ops


def step(prev, b):
    if b == prev:
        return 0.0
    return (LAUNCH_ANE if b == "ane" else 0.0) + (SWITCH if prev is not None else 0.0)


def path_cost(ops, path):
    c, prev = 0.0, None
    for o, b in zip(ops, path):
        c += o["est"].get(b, 0.0) + step(prev, b)
        prev = b
    return c + (END_ANE if prev == "ane" else 0.0)


def best_path(ops):
    st = {None: (0.0, [])}
    for o in ops:
        ns = {}
        for b in o["sup"]:
            for pb, (pc, pp) in st.items():
                v = pc + o["est"].get(b, 0.0) + step(pb, b)
                if b not in ns or v < ns[b][0]:
                    ns[b] = (v, pp + [b])
        st = ns
    return min((c + (END_ANE if b == "ane" else 0.0), p) for b, (c, p) in st.items())


def main():
    mode, files = sys.argv[1], [f for a in sys.argv[2:] for f in sorted(glob.glob(a))]
    if mode == "ops":
        for f in files:
            n = f.split("/")[-1][:-4]
            for o in parse(f):
                print(n, o["op"], o["out"], o["sel"], ",".join(o["sup"]),
                      " ".join(f"{k}={v:.4f}" for k, v in o["est"].items()), sep="\t")
        return
    exact = tie = 0
    bad = []
    for f in files:
        ops = parse(f)
        if not ops:
            continue
        c, p = best_path(ops)
        act = [o["sel"] for o in ops]
        A = "".join("a" if x == "ane" else "c" for x in act)
        P = "".join("a" if x == "ane" else "c" for x in p)
        if A == P:
            exact += 1
        elif abs(path_cost(ops, act) - c) < 1e-6:
            tie += 1
        else:
            bad.append((f, round(path_cost(ops, act), 4), round(c, 4), A, P))
    print(f"完全一致 {exact}，平局 {tie}，不一致 {len(bad)}（共 {exact + tie + len(bad)}）")
    for b in bad:
        print("  ", *b)


if __name__ == "__main__":
    main()
