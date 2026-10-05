// 加载模型并预测：第 2 个参数为 cpu 时只用 CPU，否则 cpuAndNeuralEngine；预热 1 次后跑 20 次，打印中位数
import CoreML
import Foundation
let url = URL(fileURLWithPath: CommandLine.arguments[1])
let cfg = MLModelConfiguration(); cfg.computeUnits = CommandLine.arguments.count > 2 && CommandLine.arguments[2] == "cpu" ? .cpuOnly : .cpuAndNeuralEngine
do {
  let c = try MLModel.compileModel(at: url)
  let m = try MLModel(contentsOf: c, configuration: cfg)
  let d = m.modelDescription.inputDescriptionsByName.first!
  let a = try MLMultiArray(shape: d.value.multiArrayConstraint!.shape, dataType: .float16)
  let inp = try MLDictionaryFeatureProvider(dictionary: [d.key: a])
  _ = try m.prediction(from: inp)
  var ts: [Double] = []
  for _ in 0..<20 { let t0 = Date(); _ = try m.prediction(from: inp); ts.append(Date().timeIntervalSince(t0) * 1000) }
  ts.sort(); print(String(format: "predict ok, median %.2f ms", ts[10]))
} catch { print("ERROR", error) }
