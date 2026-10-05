// 用 Core ML 的公开 API MLComputePlan（macOS 14.4+）读出 ML Program 每个运算的支持设备、首选设备和估计代价。
// 用法：computeplan <all|cpune> <模型.mlpackage 或 .mlmodelc> ...
//   all   = MLComputeUnits.all；cpune = cpuAndNeuralEngine
// 输出（制表符分隔）：模型名  运算序号  运算类型  第一个输出名  首选设备  支持设备（逗号分隔）  估计代价权重
// 编译：swiftc -O computeplan.swift -o computeplan
import CoreML
import Foundation

func dev(_ d: MLComputeDevice) -> String {
  switch d {
  case .cpu: return "CPU"
  case .gpu: return "GPU"
  case .neuralEngine: return "ANE"
  @unknown default: return "?"
  }
}

func walk(_ block: MLModelStructure.Program.Block, _ plan: MLComputePlan, _ name: String, _ idx: inout Int) {
  for op in block.operations {
    for b in op.blocks { walk(b, plan, name, &idx) }
    if op.operatorName == "const" { continue }
    let u = plan.deviceUsage(for: op)
    let pref = u.map { dev($0.preferred) } ?? "-"
    let sup = u.map { $0.supported.map(dev).joined(separator: ",") } ?? "-"
    let cost = plan.estimatedCost(of: op).map { String(format: "%.4f", $0.weight) } ?? "-"
    let out = op.outputs.first?.name ?? "-"
    print("\(name)\t\(idx)\t\(op.operatorName)\t\(out)\t\(pref)\t\(sup)\t\(cost)")
    idx += 1
  }
}

let args = CommandLine.arguments
let cfg = MLModelConfiguration()
cfg.computeUnits = args[1] == "all" ? .all : .cpuAndNeuralEngine
let sem = DispatchSemaphore(value: 0)
Task {
  for path in args.dropFirst(2) {
    let url = URL(fileURLWithPath: path)
    let name = url.deletingPathExtension().lastPathComponent
    do {
      let compiled = url.pathExtension == "mlmodelc" ? url : try await MLModel.compileModel(at: url)
      let plan = try await MLComputePlan.load(contentsOf: compiled, configuration: cfg)
      guard case let .program(prog) = plan.modelStructure, let main = prog.functions["main"] else {
        print("\(name)\t-\tNOT_PROGRAM\t-\t-\t-\t-"); continue
      }
      var i = 0
      walk(main.block, plan, name, &i)
      if compiled != url { try? FileManager.default.removeItem(at: compiled) }
    } catch {
      print("\(name)\t-\tERROR\t-\t-\t-\t\(String(describing: error).replacingOccurrences(of: "\n", with: " ").prefix(200))")
    }
    fflush(stdout)
  }
  sem.signal()
}
sem.wait()
