"""Core ML 算子分派（opdispatch）用的单算子模型：每个模型只有一个被测算子（外加必要的 const），
用 MLComputePlan（computeplan.swift）读出它支持的设备和首选设备，看哪些算子、数据类型、形状会退回 CPU。

用法：python opdispatch_gen.py [--ctx] <输出目录> [名字 ...]（coremltools，conda 环境 mps；不给名字则生成全部）
--ctx：上下文模式，被测运算的 FP16 输入、输出前后各包两层卷积（见 wrap），看放在大网络里时首选设备是否仍是 ANE。
每个模型存为 <名字>.mlpackage；输入 FP16（除名字带 _f32 / _i32 的变体），最低部署目标 macOS 15。
默认输入 1×64×32×32（4 维）；矩阵类 1×128×256；变体覆盖数据类型（f32 / i32）、秩（5、6 维）、超大维度、广播。
"""
import os
import sys

import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import Function, Program, types

rng = np.random.default_rng(0)
F16, F32 = np.float16, np.float32
fp16, fp32, i32 = types.fp16, types.fp32, types.int32
X4 = (1, 64, 32, 32)
M3 = (1, 128, 256)


def c(a, dt=F16):
    return mb.const(val=np.asarray(a, dt))


def wt(*s):
    return (rng.standard_normal(s) * 0.05).astype(F16)


CASES = {}


def case(name, ins, dt=fp16):
    """ins：输入形状列表；dt：输入数据类型（一个或每个输入一个）。"""
    def deco(fn):
        CASES[name] = (ins, dt if isinstance(dt, list) else [dt] * len(ins), fn)
        return fn
    return deco


def unary(name, f, shape=X4, dt=fp16):
    case(name, [shape], dt)(lambda x: f(x))


def binary(name, f, s1=X4, s2=X4, dt=fp16):
    case(name, [s1, s2], dt)(lambda x, y: f(x, y))


# 逐元素一元
for op in ["relu", "sigmoid", "tanh", "silu", "softplus", "softsign", "erf", "exp", "exp2", "log", "sqrt", "rsqrt",
           "inverse", "abs", "sign", "sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "atanh", "floor",
           "ceil", "round", "square", "logical_not", "relu6"]:
    if op == "logical_not":
        continue
    unary(op, lambda x, op=op: getattr(mb, op)(x=x))
unary("gelu_exact", lambda x: mb.gelu(x=x, mode="EXACT"))
unary("gelu_tanh", lambda x: mb.gelu(x=x, mode="TANH_APPROXIMATION"))
unary("gelu_sigmoid", lambda x: mb.gelu(x=x, mode="SIGMOID_APPROXIMATION"))
unary("leaky_relu", lambda x: mb.leaky_relu(x=x, alpha=0.1))
unary("elu", lambda x: mb.elu(x=x, alpha=1.0))
unary("prelu", lambda x: mb.prelu(x=x, alpha=np.full(64, 0.1, F16)))
unary("clip", lambda x: mb.clip(x=x, alpha=np.float16(-1), beta=np.float16(1)))
unary("thresholded_relu", lambda x: mb.thresholded_relu(x=x, alpha=0.5))
unary("hard_sigmoid", lambda x: mb.sigmoid_hard(x=x, alpha=0.2, beta=0.5))
unary("scaled_tanh", lambda x: mb.scaled_tanh(x=x, alpha=1.0, beta=1.0))
unary("linear_act", lambda x: mb.linear_activation(x=x, alpha=2.0, beta=1.0))
unary("pow_const", lambda x: mb.pow(x=x, y=c(3.0)))
unary("pow_half", lambda x: mb.pow(x=x, y=c(0.5)))

# 逐元素二元（同形状、广播）
for op in ["add", "sub", "mul", "real_div", "maximum", "minimum", "pow", "floor_div", "mod"]:
    binary(op, lambda x, y, op=op: getattr(mb, op)(x=x, y=y))
binary("add_bc_ch", lambda x, y: mb.add(x=x, y=y), s2=(1, 64, 1, 1))
binary("add_bc_hw", lambda x, y: mb.add(x=x, y=y), s2=(1, 1, 32, 32))
binary("add_bc_w", lambda x, y: mb.add(x=x, y=y), s2=(1, 1, 1, 32))
binary("add_bc_both", lambda x, y: mb.add(x=x, y=y), s1=(1, 64, 1, 32), s2=(1, 1, 32, 1))
binary("add_bc_batch", lambda x, y: mb.add(x=x, y=y), s1=(4, 64, 32, 32), s2=(1, 64, 32, 32))
for op in ["equal", "not_equal", "less", "less_equal", "greater", "greater_equal"]:
    binary(op, lambda x, y, op=op: mb.cast(x=getattr(mb, op)(x=x, y=y), dtype="fp16"))
case("select", [X4, X4, X4])(lambda m, x, y: mb.select(cond=mb.greater(x=m, y=c(0.0)), a=x, b=y))
binary("logical_and", lambda x, y: mb.cast(x=mb.logical_and(x=mb.greater(x=x, y=c(0.0)), y=mb.greater(x=y, y=c(0.0))),
                                            dtype="fp16"))

# 数据类型变体
unary("relu_f32", lambda x: mb.relu(x=x), dt=fp32)
binary("add_f32", lambda x, y: mb.add(x=x, y=y), dt=fp32)
binary("add_i32", lambda x, y: mb.add(x=x, y=y), dt=i32)
binary("mul_i32", lambda x, y: mb.mul(x=x, y=y), dt=i32)
unary("cast_f16_i32", lambda x: mb.cast(x=x, dtype="int32"))
unary("cast_i32_f16", lambda x: mb.cast(x=x, dtype="fp16"), dt=i32)
unary("cast_f16_f32", lambda x: mb.cast(x=x, dtype="fp32"))
unary("cast_f16_i8", lambda x: mb.cast(x=x, dtype="int8"))
unary("quantize_i8", lambda x: mb.quantize(input=x, scale=np.float16(0.1), output_dtype="int8"))
unary("q_dq_i8", lambda x: mb.dequantize(input=mb.quantize(input=x, scale=np.float16(0.1), output_dtype="int8"),
                                         scale=np.float16(0.1)))

# 秩 / 尺寸变体
unary("relu_r1", lambda x: mb.relu(x=x), shape=(65536,))
unary("relu_r2", lambda x: mb.relu(x=x), shape=(256, 256))
unary("relu_r3", lambda x: mb.relu(x=x), shape=M3)
unary("relu_r5", lambda x: mb.relu(x=x), shape=(1, 4, 16, 32, 32))
unary("relu_w16384", lambda x: mb.relu(x=x), shape=(1, 1, 1, 16384))
unary("relu_w16385", lambda x: mb.relu(x=x), shape=(1, 1, 1, 16385))
unary("relu_w65536", lambda x: mb.relu(x=x), shape=(1, 1, 1, 65536))
unary("relu_w65537", lambda x: mb.relu(x=x), shape=(1, 1, 1, 65537))
unary("relu_c65536", lambda x: mb.relu(x=x), shape=(1, 65536, 1, 1))
unary("relu_c65537", lambda x: mb.relu(x=x), shape=(1, 65537, 1, 1))
unary("relu_h65536", lambda x: mb.relu(x=x), shape=(1, 1, 65536, 1))
unary("relu_h65537", lambda x: mb.relu(x=x), shape=(1, 1, 65537, 1))
unary("relu_n64", lambda x: mb.relu(x=x), shape=(64, 64, 8, 8))

# 卷积 / 矩阵
case("conv1x1", [X4])(lambda x: mb.conv(x=x, weight=c(wt(64, 64, 1, 1))))
case("conv3x3", [X4])(lambda x: mb.conv(x=x, weight=c(wt(64, 64, 3, 3)), pad_type="same"))
case("conv3x3_dw", [X4])(lambda x: mb.conv(x=x, weight=c(wt(64, 1, 3, 3)), pad_type="same", groups=64))
case("conv7x7_s2", [X4])(lambda x: mb.conv(x=x, weight=c(wt(64, 64, 7, 7)), pad_type="same", strides=[2, 2]))
case("conv3x3_d2", [X4])(lambda x: mb.conv(x=x, weight=c(wt(64, 64, 3, 3)), pad_type="same", dilations=[2, 2]))
case("conv_k17", [X4])(lambda x: mb.conv(x=x, weight=c(wt(64, 64, 17, 17)), pad_type="same"))
case("conv_k1x31", [X4])(lambda x: mb.conv(x=x, weight=c(wt(64, 64, 1, 31)), pad_type="same"))
case("conv_s5", [X4])(lambda x: mb.conv(x=x, weight=c(wt(64, 64, 5, 5)), strides=[5, 5]))
case("conv1d", [(1, 64, 1024)])(lambda x: mb.conv(x=x, weight=c(wt(64, 64, 3)), pad_type="same"))
case("conv3d", [(1, 16, 8, 16, 16)])(lambda x: mb.conv(x=x, weight=c(wt(16, 16, 3, 3, 3)), pad_type="same"))
case("conv_dynw", [X4, (64, 64, 1, 1)])(lambda x, k: mb.conv(x=x, weight=k))
case("conv_transpose", [X4])(lambda x: mb.conv_transpose(x=x, weight=c(wt(64, 64, 2, 2)), strides=[2, 2]))
case("conv_transpose_k3s2", [X4])(lambda x: mb.conv_transpose(x=x, weight=c(wt(64, 64, 3, 3)), strides=[2, 2],
                                                            pad_type="same"))
case("conv_transpose_1d", [(1, 64, 256)])(lambda x: mb.conv_transpose(x=x, weight=c(wt(64, 64, 4)), strides=[2]))
case("conv_transpose_3d", [(1, 16, 4, 8, 8)])(lambda x: mb.conv_transpose(x=x, weight=c(wt(16, 16, 2, 2, 2)),
                                                                        strides=[2, 2, 2]))
case("linear", [M3])(lambda x: mb.linear(x=x, weight=c(wt(512, 256)), bias=c(np.zeros(512))))
case("matmul_const", [M3])(lambda x: mb.matmul(x=x, y=c(wt(256, 512))))
case("matmul_dyn", [M3, (1, 256, 128)])(lambda x, y: mb.matmul(x=x, y=y))
case("matmul_dyn_tr", [M3, (1, 128, 256)])(lambda x, y: mb.matmul(x=x, y=y, transpose_y=True))
case("matmul_batched4d", [(1, 8, 128, 64), (1, 8, 64, 128)])(lambda x, y: mb.matmul(x=x, y=y))
case("matmul_bc", [(1, 8, 128, 64), (1, 1, 64, 128)])(lambda x, y: mb.matmul(x=x, y=y))
case("matmul_f32", [M3, (1, 256, 128)], fp32)(lambda x, y: mb.matmul(x=x, y=y))
case("matmul_i32", [M3, (1, 256, 128)], i32)(lambda x, y: mb.matmul(x=x, y=y))
case("sdpa", [(1, 8, 128, 64)] * 3)(lambda q, k, v: mb.scaled_dot_product_attention(query=q, key=k, value=v))
case("sdpa_mask", [(1, 8, 128, 64)] * 3 + [(1, 1, 128, 128)])(
    lambda q, k, v, m: mb.scaled_dot_product_attention(query=q, key=k, value=v, attn_mask=m))
case("lstm", [(16, 1, 64)])(lambda x: mb.lstm(x=x, initial_h=c(np.zeros((1, 64))), initial_c=c(np.zeros((1, 64))), weight_ih=c(wt(256, 64)), weight_hh=c(wt(256, 64)),
                                              output_sequence=True)[0])
case("gru", [(16, 1, 64)])(lambda x: mb.gru(x=x, initial_h=c(np.zeros((1, 64))), weight_ih=c(wt(192, 64)), weight_hh=c(wt(192, 64)),
                                            output_sequence=True)[0])
case("rnn", [(16, 1, 64)])(lambda x: mb.rnn(x=x, initial_h=c(np.zeros((1, 64))), weight_ih=c(wt(64, 64)), weight_hh=c(wt(64, 64)),
                                            output_sequence=True)[0])

# 池化 / 归一化 / softmax
case("avg_pool", [X4])(lambda x: mb.avg_pool(x=x, kernel_sizes=[2, 2], strides=[2, 2], pad_type="valid"))
case("max_pool", [X4])(lambda x: mb.max_pool(x=x, kernel_sizes=[3, 3], strides=[1, 1], pad_type="same"))
case("max_pool_k15", [X4])(lambda x: mb.max_pool(x=x, kernel_sizes=[15, 15], strides=[1, 1], pad_type="same"))
case("l2_pool", [X4])(lambda x: mb.l2_pool(x=x, kernel_sizes=[2, 2], strides=[2, 2], pad_type="valid"))
case("avg_pool3d", [(1, 16, 8, 16, 16)])(lambda x: mb.avg_pool(x=x, kernel_sizes=[2, 2, 2], strides=[2, 2, 2],
                                                               pad_type="valid"))
case("global_avg", [X4])(lambda x: mb.reduce_mean(x=x, axes=[2, 3], keep_dims=True))
case("softmax_c", [X4])(lambda x: mb.softmax(x=x, axis=1))
case("softmax_w", [X4])(lambda x: mb.softmax(x=x, axis=3))
case("softmax_h", [X4])(lambda x: mb.softmax(x=x, axis=2))
case("softmax_n", [(8, 64, 16, 16)])(lambda x: mb.softmax(x=x, axis=0))
case("log_softmax", [X4])(lambda x: mb.sub(x=x, y=mb.reduce_log_sum_exp(x=x, axes=[1], keep_dims=True)))
case("layer_norm_c", [X4])(lambda x: mb.layer_norm(x=x, axes=[1], epsilon=1e-5))
case("layer_norm_w", [M3])(lambda x: mb.layer_norm(x=x, axes=[2], gamma=c(np.ones(256)), beta=c(np.zeros(256))))
case("layer_norm_hw", [X4])(lambda x: mb.layer_norm(x=x, axes=[2, 3]))
case("layer_norm_chw", [X4])(lambda x: mb.layer_norm(x=x, axes=[1, 2, 3]))
case("instance_norm", [X4])(lambda x: mb.instance_norm(x=x, gamma=c(np.ones(64)), beta=c(np.zeros(64))))
case("batch_norm", [X4])(lambda x: mb.batch_norm(x=x, mean=c(np.zeros(64)), variance=c(np.ones(64))))
case("l2_norm", [X4])(lambda x: mb.l2_norm(x=x))
case("lrn", [X4])(lambda x: mb.local_response_norm(x=x, size=5))

# 归约
for op in ["reduce_sum", "reduce_mean", "reduce_max", "reduce_min", "reduce_prod", "reduce_l1_norm", "reduce_l2_norm",
           "reduce_sum_square", "reduce_log_sum", "reduce_log_sum_exp"]:
    case(op + "_c", [X4])(lambda x, op=op: getattr(mb, op)(x=x, axes=[1], keep_dims=True))
case("reduce_sum_w", [X4])(lambda x: mb.reduce_sum(x=x, axes=[3], keep_dims=True))
case("reduce_sum_all", [X4])(lambda x: mb.reduce_sum(x=x, axes=[0, 1, 2, 3], keep_dims=True))
case("reduce_argmax_c", [X4])(lambda x: mb.cast(x=mb.reduce_argmax(x=x, axis=1, keep_dims=True), dtype="fp16"))
case("reduce_argmax_w", [X4])(lambda x: mb.cast(x=mb.reduce_argmax(x=x, axis=3, keep_dims=True), dtype="fp16"))
case("cumsum_w", [X4])(lambda x: mb.cumsum(x=x, axis=3))
case("cumsum_c", [X4])(lambda x: mb.cumsum(x=x, axis=1))

# 形状 / 数据搬运
case("reshape", [X4])(lambda x: mb.reshape(x=x, shape=[1, 64, 1024]))
case("reshape_split_c", [X4])(lambda x: mb.reshape(x=x, shape=[1, 8, 8, 32, 32]))
case("transpose_hw", [X4])(lambda x: mb.transpose(x=x, perm=[0, 1, 3, 2]))
case("transpose_cw", [X4])(lambda x: mb.transpose(x=x, perm=[0, 3, 2, 1]))
case("transpose_nc", [(8, 64, 16, 16)])(lambda x: mb.transpose(x=x, perm=[1, 0, 2, 3]))
case("transpose_r5", [(1, 4, 16, 16, 16)])(lambda x: mb.transpose(x=x, perm=[0, 2, 1, 4, 3]))
case("concat_c", [X4, X4])(lambda x, y: mb.concat(values=(x, y), axis=1))
case("concat_w", [X4, X4])(lambda x, y: mb.concat(values=(x, y), axis=3))
case("concat_n", [X4, X4])(lambda x, y: mb.concat(values=(x, y), axis=0))
case("concat_interleave", [X4, X4])(lambda x, y: mb.concat(values=(x, y), axis=1, interleave=True))
case("split_c", [X4])(lambda x: mb.split(x=x, num_splits=2, axis=1)[0])
case("stack", [X4, X4])(lambda x, y: mb.stack(values=(x, y), axis=1))
case("slice_c", [X4])(lambda x: mb.slice_by_index(x=x, begin=[0, 8, 0, 0], end=[1, 40, 32, 32]))
case("slice_w_stride2", [X4])(lambda x: mb.slice_by_index(x=x, begin=[0, 0, 0, 0], end=[1, 64, 32, 32],
                                                          stride=[1, 1, 1, 2]))
case("slice_by_size", [X4])(lambda x: mb.slice_by_size(x=x, begin=[0, 0, 4, 4], size=[1, 64, 16, 16]))
case("slice_dyn", [X4, (4,)], [fp16, i32])(lambda x, b: mb.slice_by_size(x=x, begin=b, size=[1, 32, 16, 16]))
case("reverse_w", [X4])(lambda x: mb.reverse(x=x, axes=[3]))
case("tile", [X4])(lambda x: mb.tile(x=x, reps=[1, 2, 1, 2]))
case("pad_const", [X4])(lambda x: mb.pad(x=x, pad=[1, 1, 1, 1], mode="constant", constant_val=np.float16(0)))
case("pad_reflect", [X4])(lambda x: mb.pad(x=x, pad=[2, 2, 2, 2], mode="reflect"))
case("pad_replicate", [X4])(lambda x: mb.pad(x=x, pad=[2, 2, 2, 2], mode="replicate"))
case("pad_c", [X4])(lambda x: mb.pad(x=x, pad=[0, 0, 4, 4, 0, 0, 0, 0], mode="constant"))
case("space_to_depth", [X4])(lambda x: mb.space_to_depth(x=x, block_size=2))
case("depth_to_space", [X4])(lambda x: mb.depth_to_space(x=x, block_size=2))
case("pixel_shuffle", [X4])(lambda x: mb.pixel_shuffle(x=x, upscale_factor=2))
case("pixel_unshuffle", [X4])(lambda x: mb.pixel_unshuffle(x=x, downscale_factor=np.uint32(2)))
case("space_to_batch", [X4])(lambda x: mb.space_to_batch(x=x, block_shape=[2, 2], paddings=[[0, 0], [0, 0]]))
case("batch_to_space", [(4, 64, 16, 16)])(lambda x: mb.batch_to_space(x=x, block_shape=[2, 2],
                                                                      crops=[[0, 0], [0, 0]]))
case("sliding_windows", [(1, 64, 256)])(lambda x: mb.sliding_windows(x=x, axis=2, size=8, stride=4))
case("band_part", [(1, 128, 128)])(lambda x: mb.band_part(x=x, lower=-1, upper=0))
case("squeeze_expand", [(1, 64, 1, 32)])(lambda x: mb.expand_dims(x=mb.squeeze(x=x, axes=[2]), axes=[3]))

# 缩放 / 采样
case("upsample_nearest", [X4])(lambda x: mb.upsample_nearest_neighbor(x=x, scale_factor_height=2,
                                                                      scale_factor_width=2))
case("upsample_nearest_x3", [X4])(lambda x: mb.upsample_nearest_neighbor(x=x, scale_factor_height=3,
                                                                         scale_factor_width=3))
case("upsample_nearest_frac", [X4])(lambda x: mb.upsample_nearest_neighbor(x=x, scale_factor_height=1.5,
                                                                           scale_factor_width=1.5))
case("upsample_bilinear", [X4])(lambda x: mb.upsample_bilinear(x=x, scale_factor_height=2, scale_factor_width=2))
case("upsample_bilinear_ac", [X4])(lambda x: mb.upsample_bilinear(x=x, scale_factor_height=2, scale_factor_width=2,
                                                                  align_corners=True))
case("resize_bilinear", [X4])(lambda x: mb.resize_bilinear(x=x, target_size_height=48, target_size_width=48))
case("resize_nearest", [X4])(lambda x: mb.resize_nearest_neighbor(x=x, target_size_height=48, target_size_width=48))
case("resize_down", [X4])(lambda x: mb.resize(x=x, shape=c([20, 20], np.int32), resized_dims=np.uint32(2),
                                              interpolation_mode="LINEAR"))
case("crop_resize", [X4])(lambda x: mb.crop_resize(x=x, boxes=c(np.array([[0, 0, 16, 16]] * 4)), box_indices=c(
    np.zeros(4), np.int32), target_height=8, target_width=8, box_coordinate_mode="CORNERS_HEIGHT_FIRST",
    normalized_coordinates=False))
case("affine", [X4])(lambda x: mb.affine(x=x, transform_matrix=c(np.array([[1, 0, 0, 0, 1, 0]], F16)),
                                         output_height=32, output_width=32, sampling_mode="bilinear",
                                         padding_mode="constant", padding_value=np.float16(0), coordinates_mode="normalized_minus_one_to_one",
                                         align_corners=True))
case("resample", [X4, (1, 32, 32, 2)])(lambda x, g: mb.resample(x=x, coordinates=g, sampling_mode="bilinear",
                                                                padding_mode="constant", padding_value=np.float16(0),
                                                                coordinates_mode="normalized_minus_one_to_one",
                                                                align_corners=True))

# 索引 / 排序
I64 = rng.integers(0, 64, 32).astype(np.int32)
case("gather_c", [X4])(lambda x: mb.gather(x=x, indices=c(I64, np.int32), axis=1))
case("gather_w", [X4])(lambda x: mb.gather(x=x, indices=c(rng.integers(0, 32, 16), np.int32), axis=3))
case("gather_dyn", [(1000, 256), (1, 64)], [fp16, i32])(lambda t, i: mb.gather(x=t, indices=i, axis=0))
case("embedding", [(1, 64)], i32)(lambda i: mb.gather(x=c(wt(32000, 256)), indices=i, axis=0))
case("gather_along_axis", [X4, X4], [fp16, i32])(lambda x, i: mb.gather_along_axis(x=x, indices=i, axis=3))
case("gather_nd", [X4, (8, 2)], [fp16, i32])(lambda x, i: mb.gather_nd(x=x, indices=i))
case("scatter", [X4, (4,), (1, 64, 32, 4)], [fp16, i32, fp16])(lambda x, i, u: mb.scatter(data=x, indices=i,
                                                                                         updates=u, axis=3))
case("scatter_along_axis", [X4, X4, X4], [fp16, i32, fp16])(lambda x, i, u: mb.scatter_along_axis(
    data=x, indices=i, updates=u, axis=3))
case("topk_w", [X4])(lambda x: mb.topk(x=x, k=4, axis=3)[0])
case("topk_c", [X4])(lambda x: mb.topk(x=x, k=4, axis=1)[0])
case("topk_large", [(1, 32000)])(lambda x: mb.topk(x=x, k=40, axis=1)[0])
case("argsort_w", [X4])(lambda x: mb.cast(x=mb.argsort(x=x, axis=3), dtype="fp16"))
case("nms", [(1, 100, 4), (1, 100, 4)])(lambda b, s: mb.non_maximum_suppression(boxes=b, scores=s, iou_threshold=np.float16(0.5),
                                                                                max_boxes=10)[0])
case("one_hot", [(1, 64)], i32)(lambda i: mb.one_hot(indices=i, one_hot_vector_size=128))
case("shape", [X4])(lambda x: mb.cast(x=mb.shape(x=x), dtype="fp16"))
case("fill_like", [X4])(lambda x: mb.fill_like(ref_tensor=x, value=1.0))
case("range_1d", [(1,)], i32)(lambda e: mb.cast(x=mb.range_1d(start=0, end=mb.squeeze(x=e), step=1), dtype="fp16"))
case("random_normal", [X4])(lambda x: mb.add(x=x, y=mb.cast(x=mb.random_normal(shape=np.array(X4, np.int32)), dtype="fp16")))
case("nonzero", [(1, 256)])(lambda x: mb.cast(x=mb.non_zero(x=x), dtype="fp16"))
case("argmax_flat", [(1, 32000)])(lambda x: mb.cast(x=mb.reduce_argmax(x=x, axis=1), dtype="fp16"))


# 边界扫描（名字以 sw_ 开头）：卷积核、池化核、矩阵维度、张量维度上限
for k in (13, 14, 15, 16):
    case(f"sw_conv_k{k}", [X4])(lambda x, k=k: mb.conv(x=x, weight=c(wt(64, 64, k, k)), pad_type="same"))
for k in (16, 17, 24, 32, 64):
    case(f"sw_conv_k1x{k}", [X4])(lambda x, k=k: mb.conv(x=x, weight=c(wt(64, 64, 1, k)), pad_type="same"))
    case(f"sw_conv_k{k}x1", [X4])(lambda x, k=k: mb.conv(x=x, weight=c(wt(64, 64, k, 1)), pad_type="same"))
for k in (4, 5, 7, 8, 9, 13, 14):
    case(f"sw_maxpool_k{k}", [X4])(lambda x, k=k: mb.max_pool(x=x, kernel_sizes=[k, k], strides=[1, 1], pad_type="same"))
    case(f"sw_avgpool_k{k}", [X4])(lambda x, k=k: mb.avg_pool(x=x, kernel_sizes=[k, k], strides=[1, 1], pad_type="same"))
for s in (2, 3, 4, 6, 8):
    case(f"sw_conv_s{s}", [X4])(lambda x, s=s: mb.conv(x=x, weight=c(wt(64, 64, s, s)), strides=[s, s]))
for d in (16384, 16385, 32768, 65536):
    case(f"sw_matmul_k{d}", [(1, 16, d), (1, d, 16)])(lambda x, y: mb.matmul(x=x, y=y))
for g in (2, 4, 8, 16, 32):
    case(f"sw_conv_g{g}", [X4])(lambda x, g=g: mb.conv(x=x, weight=c(wt(64, 64 // g, 3, 3)), pad_type="same", groups=g))
for k in (9, 10, 11, 12, 13, 14, 15):
    case(f"sw_conv_k1x{k}", [X4])(lambda x, k=k: mb.conv(x=x, weight=c(wt(64, 64, 1, k)), pad_type="same"))
for k in (25, 28, 31):
    case(f"sw_conv_k{k}x1", [X4])(lambda x, k=k: mb.conv(x=x, weight=c(wt(64, 64, k, 1)), pad_type="same"))
case("sw_conv_k1x16_valid", [X4])(lambda x: mb.conv(x=x, weight=c(wt(64, 64, 1, 16))))
case("sw_conv_k15x15_valid", [X4])(lambda x: mb.conv(x=x, weight=c(wt(64, 64, 15, 15))))
case("sw_maxpool_k9_valid", [X4])(lambda x: mb.max_pool(x=x, kernel_sizes=[9, 9], strides=[1, 1], pad_type="valid"))
case("sw_maxpool_k1x9", [X4])(lambda x: mb.max_pool(x=x, kernel_sizes=[1, 9], strides=[1, 1], pad_type="same"))
case("sw_maxpool_k9x1", [X4])(lambda x: mb.max_pool(x=x, kernel_sizes=[9, 1], strides=[1, 1], pad_type="same"))
for d in (40000, 49152, 65535):
    case(f"sw_matmul_k{d}", [(1, 16, d), (1, d, 16)])(lambda x, y: mb.matmul(x=x, y=y))
for b in (2, 4, 8, 16):
    case(f"sw_relu_n{b}", [(b, 64, 32, 32)])(lambda x: mb.relu(x=x))

def wrap(x, tag):
    """上下文模式：FP16 的 4 维张量前后各加两层 3×3 卷积 + ReLU（通道 > 512 时用逐通道卷积），
    3 维张量（最后一维 ≤ 2048）加两层 linear + ReLU，
    让被测运算处在一段够大的 ANE 网络中间。包裹运算一律以 wrap_ 命名，便于分析时排除。"""
    if x.dtype != fp16 or x.rank not in (3, 4) or any(not isinstance(d, int) for d in x.shape):
        return x
    for i in range(2):
        n = f"wrap_{tag}{i}"
        if x.rank == 4:
            C = x.shape[1]
            if C <= 512:
                x = mb.conv(x=x, weight=c(wt(C, C, 3, 3)), pad_type="same", name=n + "_conv")
            else:                   # 通道多时用逐通道卷积，避免 C×C 权重（C=65536 时为 77 GB，曾把机器内存撑爆）
                x = mb.conv(x=x, weight=c(wt(C, 1, 3, 3)), pad_type="same", groups=C, name=n + "_conv")
        else:
            D = x.shape[2]
            if D > 2048:
                return x
            x = mb.linear(x=x, weight=c(wt(D, D)), name=n + "_lin")
        x = mb.relu(x=x, name=n + "_relu")
    return x


def build(name, ctx=False):
    shapes, dts, fn = CASES[name]
    # mb.program 按函数签名取输入名，不接受 *args：直接构造 Function
    ins = {f"x{i}": mb.placeholder(shape=s, dtype=d) for i, (s, d) in enumerate(zip(shapes, dts))}
    with Function(ins, opset_version=ct.target.macOS15) as f:
        xs = list(f.inputs.values())
        if ctx:
            xs = [wrap(x, f"in{i}_") for i, x in enumerate(xs)]
        out = fn(*xs)
        if ctx:
            out = wrap(out, "out_")
        f.set_outputs([out])
    prog = Program()
    prog.add_function("main", f)
    return ct.convert(prog, convert_to="mlprogram", minimum_deployment_target=ct.target.macOS15,
                      compute_precision=ct.precision.FLOAT16, compute_units=ct.ComputeUnit.CPU_AND_NE)


def main():
    a = sys.argv[1:]
    ctx = "--ctx" in a
    a = [x for x in a if x != "--ctx"]
    out = a[0]
    names = a[1:] or list(CASES)
    os.makedirs(out, exist_ok=True)
    bad = []
    for n in names:
        p = os.path.join(out, n + ".mlpackage")
        if os.path.exists(p):
            continue
        try:
            build(n, ctx).save(p)
        except Exception as e:  # 某些算子在这一版 coremltools / 部署目标下无法构造：记下来，不中断
            bad.append((n, repr(e)[:200]))
            print("FAIL", n, repr(e)[:200], flush=True)
    with open(os.path.join(out, "gen_failures.txt"), "w") as f:
        for n, e in bad:
            f.write(f"{n}\t{e}\n")
    print(len(names) - len(bad), "ok,", len(bad), "failed")


if __name__ == "__main__":
    main()
