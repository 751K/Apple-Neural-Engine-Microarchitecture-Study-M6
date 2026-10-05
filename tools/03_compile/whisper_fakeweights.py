"""按 model.mil 里的 BLOBFILE 引用生成一份格式正确的假权重文件（MIL blob v2），用来在没有真实权重时复现编译行为。

用法：python3 whisper_fakeweights.py <model.mil> <输出 weights1.bin>
格式：文件头 64 字节（张量个数 u32、版本 2 u32）；每个张量在 MIL 给出的偏移处放 64 字节元数据
（0xDEADBEEF、数据类型 fp16 = 1、字节数、数据偏移 = 元数据偏移 + 64），数据紧随其后。
数据填标准差 0.02 的正态随机数：不能用随机字节（约 3% 解读为 FP16 NaN / Inf，编译器直接返回失败），
也不宜用全 0（编译器按内容去重 / 判断稀疏，会和真实情况不同）。编译结果（HWX 大小、用时、交换文件）与真实权重一致。
"""
import re
import struct
import sys

import numpy as np

mil, out = sys.argv[1], sys.argv[2]
s = open(mil).read()
refs = re.findall(r'tensor<(fp16), \[([0-9, ]*)\]>\(BLOBFILE\(path = string\("@model_path/weights1\.bin"\), offset = uint64\((\d+)\)\)', s)
blobs = {}
for _, shape, off in refs:
    blobs[int(off)] = int(np.prod([int(x) for x in shape.split(",")])) if shape.strip() else 1
end = max(o + 64 + 2 * n for o, n in blobs.items())
rng = np.random.default_rng(0)
with open(out, "wb") as f:
    f.truncate(end)
    f.write(struct.pack("<II", len(blobs), 2) + b"\0" * 56)
    for o, n in sorted(blobs.items()):
        f.seek(o)
        f.write(struct.pack("<IIQQQ", 0xDEADBEEF, 1, 2 * n, o + 64, 0) + b"\0" * 32)
        for i in range(0, n, 1 << 24):
            m = min(1 << 24, n - i)
            f.write((rng.standard_normal(m, dtype=np.float32) * 0.02).astype(np.float16).tobytes())
print(f"{len(blobs)} 个张量，{end} 字节")
