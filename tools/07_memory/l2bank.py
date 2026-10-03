"""L2 bank 冲突（H53 第 3 步，只编译）：同一个卷积链分别用默认选项和 DisableL2BankConflictOpt=true 编译，
比较编译器估计的 exe_cycles 与 L2 相关寄存器，看关掉优化后哪些宽度（行步长）会被估计变慢。

用法（M6）：
  /opt/miniconda3/envs/mps/bin/python l2bank.py build <目录>
  python3 l2bank.py table <目录>
模型：k3_c{C}_h16w{W}_L4（共享权重），C = 64 / 128，W = 8–136 步长 8。
"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import os
import subprocess
import sys

CS = (64, 128)
WS = range(8, 137, 8)


def build(out):
    import coremltools as ct
    from chain import program
    os.makedirs(out, exist_ok=True)
    for C in CS:
        for W in WS:
            name = f"k3_c{C}_h16w{W}_L4"
            mc = os.path.join(out, name + ".mlmodelc")
            if not os.path.isdir(mc):
                m = ct.convert(program("3", C, 16, W, 4, False), convert_to="mlprogram",
                               minimum_deployment_target=ct.target.iOS18, compute_units=ct.ComputeUnit.CPU_ONLY)
                pkg = os.path.join(out, name + ".mlpackage")
                m.save(pkg)
                subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
                subprocess.run(["rm", "-rf", pkg])
            for tag, extra in (("def", []), ("off", ["DisableL2BankConflictOpt=true"])):
                d = os.path.join(out, "hwx", f"{name}_{tag}")
                if not os.path.exists(os.path.join(d, "model.hwx")):
                    subprocess.run(["./anecc", mc, d, "h18g"] + extra, capture_output=True)
            print("built", name, flush=True)


def table(out):
    sys.path.insert(0, ".")
    import td_widths as tw
    import tdwalk

    def info(p):
        nb = next(w for k, w in tw.streams(p).items() if "nonb" in k)
        st, ec, regs = {}, 0, []
        for _, h, r, _ in tdwalk.walk(nb):
            st.update(r)
            ec += h[1] & 0xffff
            regs.append(dict(st))
        return ec, regs
    print(f"{'模型':20s} 行字节 ec默认 ec关闭  差异寄存器（默认→关闭，取第 2 个 TD）")
    for C in CS:
        for W in WS:
            name = f"k3_c{C}_h16w{W}_L4"
            a = os.path.join(out, "hwx", f"{name}_def", "model.hwx")
            b = os.path.join(out, "hwx", f"{name}_off", "model.hwx")
            if not (os.path.exists(a) and os.path.exists(b)):
                continue
            ea, ra = info(a)
            eb, rb = info(b)
            k = min(1, len(ra) - 1, len(rb) - 1)
            diff = [f"{x:#x}:{ra[k].get(x, 0):x}→{rb[k].get(x, 0):x}" for x in sorted(set(ra[k]) | set(rb[k])) if ra[k].get(x) != rb[k].get(x)]
            print(f"{name:20s} {W * 2:6d} {ea:5d} {eb:5d}  {' '.join(diff[:6])}")


if __name__ == "__main__":
    {"build": build, "table": table}[sys.argv[1]](sys.argv[2])
