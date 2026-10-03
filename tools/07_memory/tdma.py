"""Tile DMA 输入 / 输出路数。

用法（M6）：
  /opt/miniconda3/envs/mps/bin/python tdma.py build <目录>    生成 mlmodelc，并用 anecc 编成 h18g HWX（<目录>/<名字>/hwx）
  python3 tdma.py td <目录> [过滤]                            每个 TD 用到的 Tile DMA 地址包：Src1(0x1346)、Src2(0x134c)、Dst(0x1444)
模型（输入 / 输出都是 [1, C, H, W] fp16；C = 256，H = W 决定大小：128 → 8 MB、192 → 18 MB、256 → 32 MB（181 的行宽不是 64 的倍数，计时极不稳定，已弃用））：
  第 1 步（结构）：addN_s{H}（N = 2–4 个输入相加）、two_s{H}（o1 = a + b、o2 = a − b）、fan_s{H}（o1 = a + b，o2 = relu(a + b)）
  第 2 步（带宽）：mul_s{H}（x × 1.5，读 1 写 1）、add2_s{H}（读 2 写 1）、self_s{H}（a + a）、mulab_s{H}（a × b）
每个模型另带一个小卷积分支（s：[1, 64, 8, 8] → 1×1 卷积 → 输出 z），使 Core ML 把模型放在 ANE 上。
"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import os
import subprocess
import sys

C = 256
SIZES = (128, 192, 256)


def models():
    for h in SIZES:
        for n in (2, 3, 4):
            yield f"add{n}_s{h}", h
        for k in ("two", "fan", "mul", "self", "mulab"):
            yield f"{k}_s{h}", h


def build(out):
    import torch  # noqa: F401
    import numpy as np
    import coremltools as ct
    from coremltools.converters.mil import Builder as mb
    from coremltools.converters.mil.mil import types
    os.makedirs(out, exist_ok=True)
    wt = (np.random.default_rng(0).standard_normal((64, 64, 1, 1)) * 0.1).astype(np.float16)
    for name, h in models():
        kind = name.split("_")[0]
        d = os.path.join(out, name)
        if os.path.exists(os.path.join(d, "hwx", "model.hwx")):
            continue
        nin = int(kind[3:]) if kind.startswith("add") else (1 if kind in ("mul", "self") else 2)
        spec = [mb.TensorSpec(shape=(1, C, h, h), dtype=types.fp16) for _ in range(nin)]
        spec.append(mb.TensorSpec(shape=(1, 64, 8, 8), dtype=types.fp16))

        def body(*xs):
            *ins, s = xs
            z = mb.conv(x=s, weight=mb.const(val=wt), name="z")
            if kind.startswith("add"):
                y = ins[0]
                for t in ins[1:]:
                    y = mb.add(x=y, y=t)
                return mb.identity(x=y, name="y"), z
            if kind == "two":
                return mb.add(x=ins[0], y=ins[1], name="o1"), mb.sub(x=ins[0], y=ins[1], name="o2"), z
            if kind == "fan":
                y = mb.add(x=ins[0], y=ins[1], name="o1")
                return y, mb.relu(x=y, name="o2"), z
            if kind == "mul":
                return mb.mul(x=ins[0], y=np.float16(1.5), name="y"), z
            if kind == "self":
                return mb.add(x=ins[0], y=ins[0], name="y"), z
            return mb.mul(x=ins[0], y=ins[1], name="y"), z
        # mb.program 按函数签名数输入，可变参数不行：按输入个数生成固定参数的包装
        args = ", ".join(f"x{i}" for i in range(len(spec)))
        ns = {"body": body}
        exec(f"def p({args}): return body({args})", ns)
        p = mb.program(input_specs=spec, opset_version=ct.target.iOS18)(ns["p"])
        m = ct.convert(p, convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
                       compute_units=ct.ComputeUnit.CPU_AND_NE, skip_model_load=True)
        pkg = d + ".mlpackage"
        m.save(pkg)
        subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
        subprocess.run(["rm", "-rf", pkg])
        r = subprocess.run(["./anecc", os.path.join(out, name + ".mlmodelc"), os.path.join(d, "hwx"), "h18g"],
                           capture_output=True)
        print("built", name, r.returncode, flush=True)


def td(out, flt=""):
    sys.path.insert(0, ".")
    import td_widths as tw
    import tdwalk
    names = {0x1346: "Src1", 0x134c: "Src2", 0x1444: "Dst"}
    for name, h in models():
        p = os.path.join(out, name, "hwx", "model.hwx")
        if flt not in name or not os.path.exists(p):
            continue
        nb = next(w for k, w in tw.streams(p).items() if "nonb" in k)
        rows = []
        for _, hd, r, ap in tdwalk.walk(nb):
            used = sorted({names[a] for a, *_ in ap if a in names})
            kind = (hd[8] >> 16) & 7
            rows.append(f"[{'卷积' if kind == 5 else '其他'} ec{hd[1] & 0xffff} {r.get(5, 0) & 0x1ffff}×{r.get(6, 0) & 0x1ffff}×{r.get(7, 0) & 0x1ffff} {'+'.join(used) or '-'}]")
        print(f"{name:12s} TD {len(rows):3d}  " + " ".join(rows[:8]) + (" …" if len(rows) > 8 else ""))


if __name__ == "__main__":
    {"build": build, "td": td}[sys.argv[1]](*sys.argv[2:])
