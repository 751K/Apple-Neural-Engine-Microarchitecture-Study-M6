"""ANE weight-streaming speed for decode-shaped matmuls, per weight format.

Each model chains k MLP-shaped pairs (2560 -> 9216 -> 2560 1x1 convs over T
positions). Times are fitted over k, so the slope is the cost per pair
(stored weight bytes / slope = streaming GB/s) and the intercept is the fixed
per-call cost. Inputs are random: all-zero inputs run faster on the ANE.

  python -m tools.ane_bw --out /tmp/ane_bw --formats fp16 lut4_g8 --tokens 1 4
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

HIDDEN, INTER = 2560, 9216
FORMATS = ("fp16", "lut4_g8", "lut4_g32", "lut4_tensor", "lut6_g8", "lut2_g8", "int8", "int4")


def stored_bytes(fmt):
    params = 2*HIDDEN*INTER
    bits = {"fp16": 16, "int8": 8, "int4": 4}.get(fmt) or int(fmt[3])
    return params*bits/8


def build(path, fmt, pairs, tokens):
    import coremltools as ct
    import coremltools.optimize.coreml as cto
    from coremltools.converters.mil import Builder as mb
    rng = np.random.default_rng(0)
    weights = [(rng.standard_normal((INTER, HIDDEN, 1, 1), dtype=np.float32)*0.02).astype(np.float16) for _ in range(pairs)]
    downs = [(rng.standard_normal((HIDDEN, INTER, 1, 1), dtype=np.float32)*0.02).astype(np.float16) for _ in range(pairs)]

    @mb.program(input_specs=[mb.TensorSpec((1, HIDDEN, 1, tokens), dtype=ct.converters.mil.mil.types.fp16)],
                opset_version=ct.target.macOS15)
    def prog(x):
        for i in range(pairs):
            h = mb.conv(x=x, weight=mb.const(val=weights[i], name="up%d" % i), pad_type="valid", name="cu%d" % i)
            h = mb.mul(x=h, y=np.float16(0.5))
            x = mb.conv(x=h, weight=mb.const(val=downs[i], name="down%d" % i), pad_type="valid", name="cd%d" % i)
        return x

    model = ct.convert(prog, minimum_deployment_target=ct.target.macOS15, compute_precision=ct.precision.FLOAT16,
                       compute_units=ct.ComputeUnit.CPU_AND_NE, skip_model_load=True)
    if fmt.startswith("lut"):
        bits, granularity = int(fmt[3]), fmt.split("_")[1]
        op = cto.OpPalettizerConfig(mode="uniform", nbits=bits, weight_threshold=1024,
                                    granularity="per_tensor" if granularity == "tensor" else "per_grouped_channel",
                                    group_size=0 if granularity == "tensor" else int(granularity[1:]))
        model = cto.palettize_weights(model, cto.OptimizationConfig(global_config=op))
    elif fmt in ("int8", "int4"):
        op = cto.OpLinearQuantizerConfig(mode="linear_symmetric", dtype=fmt, granularity="per_channel",
                                         weight_threshold=1024)
        model = cto.linear_quantize_weights(model, cto.OptimizationConfig(global_config=op))
    model.save(str(path))


def time_model(path, tokens, seconds):
    import coremltools as ct
    t0 = time.perf_counter()
    model = ct.models.MLModel(str(path), compute_units=ct.ComputeUnit.CPU_AND_NE)
    load = time.perf_counter()-t0
    rng = np.random.default_rng(1)
    inputs = [{"x": rng.standard_normal((1, HIDDEN, 1, tokens)).astype(np.float16)} for _ in range(4)]
    for i in range(5):
        model.predict(inputs[i % 4])
    times = []
    end = time.perf_counter()+seconds
    while time.perf_counter() < end or len(times) < 20:
        t = time.perf_counter()
        model.predict(inputs[len(times) % 4])
        times.append(time.perf_counter()-t)
    return float(np.median(times))*1e3, load


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--formats", nargs="+", default=list(FORMATS), choices=FORMATS)
    p.add_argument("--pairs", nargs="+", type=int, default=[1, 2, 4])
    p.add_argument("--tokens", nargs="+", type=int, default=[1])
    p.add_argument("--seconds", type=float, default=4)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    results_path = a.out/"results.json"
    results = json.loads(results_path.read_text()) if results_path.exists() else {}
    for fmt in a.formats:
        for tokens in a.tokens:
            key = "%s_t%d" % (fmt, tokens)
            rows = []
            for pairs in a.pairs:
                path = a.out/("%s_k%d_t%d.mlpackage" % (fmt, pairs, tokens))
                if not path.exists():
                    build(path, fmt, pairs, tokens)
                ms, load = time_model(path, tokens, a.seconds)
                rows.append({"pairs": pairs, "ms": ms, "load_s": load})
                print("%-12s t=%-2d k=%d  %8.3f ms  (%.1f GB/s incl. overhead, load %.1fs)" % (
                    fmt, tokens, pairs, ms, pairs*stored_bytes(fmt)/ms/1e6, load), flush=True)
            k = np.array([r["pairs"] for r in rows], float)
            ms = np.array([r["ms"] for r in rows])
            slope, intercept = np.polyfit(k, ms, 1) if len(rows) > 1 else (ms[0]/k[0], 0.0)
            results[key] = {"format": fmt, "tokens": tokens, "rows": rows, "ms_per_pair": slope,
                            "fixed_ms": intercept, "stored_mb_per_pair": stored_bytes(fmt)/1e6,
                            "stream_gbs": stored_bytes(fmt)/slope/1e6}
            print("%-12s t=%-2d  %.3f ms/pair  fixed %.3f ms  -> %.1f GB/s streaming" % (
                fmt, tokens, slope, intercept, stored_bytes(fmt)/slope/1e6), flush=True)
            results_path.write_text(json.dumps(results, indent=2)+"\n")


if __name__ == "__main__":
    main()
