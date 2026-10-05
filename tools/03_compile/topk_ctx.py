# topk 夹在大网络中间（ctrl_*：同形状对照，topk 换成 slice / relu）（前后各 4 层 256 通道 3×3 卷积，64×64），看 M4 上 Core ML 是否真把 topk 放 ANE 并编译成功
import sys, numpy as np, coremltools as ct
sys.path.insert(0, ".")
from opdispatch_gen import mb, c, wt, Function, Program, fp16
def heavy(x, tag):
    for i in range(4):
        x = mb.relu(x=mb.conv(x=x, weight=c(wt(256, 256, 3, 3)), pad_type="same", name=f"wrap_{tag}{i}_conv"), name=f"wrap_{tag}{i}_relu")
    return x
import os
for name, axis in (("topk_big_w", 3), ("topk_big_c", 1), ("ctrl_big_w", 3), ("ctrl_big_c", 1)):
    if os.path.exists(f"iso/{name}.mlpackage"):
        continue
    with Function({"x0": mb.placeholder(shape=(1, 256, 64, 64), dtype=fp16)}, opset_version=ct.target.macOS15) as f:
        x = heavy(f.inputs["x0"], "in")
        if name.startswith("topk"):
            x = mb.topk(x=x, k=4 if axis == 3 else 256, axis=axis)[0]
        elif axis == 3:     # 对照：同样的输出形状，不做 topk
            x = mb.slice_by_index(x=x, begin=[0, 0, 0, 0], end=[1, 256, 64, 4])
        else:
            x = mb.relu(x=x)
        x = heavy(x, "out")
        f.set_outputs([x])
    p = Program(); p.add_function("main", f)
    ct.convert(p, convert_to="mlprogram", minimum_deployment_target=ct.target.macOS15,
               compute_units=ct.ComputeUnit.CPU_AND_NE).save(f"iso/{name}.mlpackage")
