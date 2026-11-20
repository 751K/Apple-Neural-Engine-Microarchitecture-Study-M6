"""各压缩格式的权重重建误差：对 wfmt_gen 中同一份 FP16 权重解压，与原权重比较（相对 L2 误差、余弦）。纯 numpy，不涉及硬件。"""
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types
import wfmt_gen as g

w = g.base_weight(np.random.default_rng(0), 2048, (1, 1))
w32 = w.astype(np.float32)
for f in ["w8", "p6", "p4", "p3", "p2", "w4c", "w4t", "p4o2", "p4o4"]:
    @mb.program(input_specs=[mb.TensorSpec(shape=(1,), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        return mb.add(x=mb.cast(x=g.weight_op(w, f), dtype="fp32"), y=0.0)
    op = [o for o in p.functions["main"].operations if o.op_type.startswith("constexpr")][0]
    d = op.materialized_val_inference().astype(np.float32)
    e = np.linalg.norm(d - w32) / np.linalg.norm(w32)
    c = (d * w32).sum() / np.linalg.norm(d) / np.linalg.norm(w32)
    print(f"{f:5s} 相对误差 {e:.4f}  cos {c:.5f}", flush=True)
