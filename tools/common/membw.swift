// 用 GPU（Metal）测 DRAM 总带宽：只读（每线程读 float4 累加，写回极少）和拷贝（读 + 写）。
// 用法：./membw [每个缓冲区 MiB = 1024] [重复次数 = 20]（输出最高值和中位数；设环境变量 MEMBW_DUMP=1 时逐次输出 GB/s）
// 编译：swiftc -O membw.swift -o membw
import Metal
import Foundation

let mib = CommandLine.arguments.count > 1 ? Int(CommandLine.arguments[1])! : 1024
let reps = CommandLine.arguments.count > 2 ? Int(CommandLine.arguments[2])! : 20
let src = """
#include <metal_stdlib>
using namespace metal;
kernel void rd(device const float4 *a [[buffer(0)]], device float *out [[buffer(1)]], constant uint &n [[buffer(2)]],
               uint i [[thread_position_in_grid]], uint g [[threads_per_grid]]) {
  float4 s = 0;
  for (uint k = i; k < n; k += g) s += a[k];
  if (s.x == 12345.0f) out[i & 1023] = s.y;  // 防止被优化掉
}
kernel void cp(device const float4 *a [[buffer(0)]], device float4 *b [[buffer(1)]], constant uint &n [[buffer(2)]],
               uint i [[thread_position_in_grid]], uint g [[threads_per_grid]]) {
  for (uint k = i; k < n; k += g) b[k] = a[k];
}
"""
let dev = MTLCreateSystemDefaultDevice()!
let lib = try! dev.makeLibrary(source: src, options: nil)
let q = dev.makeCommandQueue()!
let bytes = mib << 20
let a = dev.makeBuffer(length: bytes, options: .storageModePrivate)!
let b = dev.makeBuffer(length: bytes, options: .storageModePrivate)!
let out = dev.makeBuffer(length: 4096, options: .storageModeShared)!
var n = UInt32(bytes / 16)
let threads = 1 << 20
func run(_ name: String, _ bufs: [MTLBuffer], _ factor: Double) {
  let p = try! dev.makeComputePipelineState(function: lib.makeFunction(name: name)!)
  var v: [Double] = []
  for r in 0..<(reps + 2) {
    let cb = q.makeCommandBuffer()!
    let e = cb.makeComputeCommandEncoder()!
    e.setComputePipelineState(p)
    for (k, x) in bufs.enumerated() { e.setBuffer(x, offset: 0, index: k) }
    e.setBytes(&n, length: 4, index: 2)
    e.dispatchThreads(MTLSize(width: threads, height: 1, depth: 1), threadsPerThreadgroup: MTLSize(width: 256, height: 1, depth: 1))
    e.endEncoding(); cb.commit(); cb.waitUntilCompleted()
    let t = cb.gpuEndTime - cb.gpuStartTime
    if r >= 2 { v.append(Double(bytes) * factor / t / 1e9) }
  }
  if ProcessInfo.processInfo.environment["MEMBW_DUMP"] != nil { for x in v { print(String(format: "%@ %.2f", name, x)) } }
  v.sort()
  print(String(format: "%@ %d MiB：最高 %.1f GB/s，中位数 %.1f GB/s（%d 次）", name, mib, v.last!, v[v.count / 2], v.count))
}
print(dev.name)
run("rd", [a, out], 1)
run("cp", [a, b], 2)
