import SwiftUI
import UIKit

// 在 iPhone / iPad 上读 ANE 的身份，调用与 Mac 上的 anedevinfo.m 相同（私有类 _ANEDeviceInfo）。
// 需真机（模拟器没有 ANE）。用 Xcode 打开 ANEInfo.xcodeproj，在 Signing 里选自己的 Team 后运行；
// 结果显示在屏幕上（右上角 Copy 复制），也打印到标准输出：
//   xcrun devicectl device process launch --device <UDID> --console local.aneinfo.q7k3
enum ANEInfo {
  static let keys = ["aneArchitectureType", "aneSubType", "aneSubTypeVariant", "numANECores", "numANEs",
                     "hasANE", "aneBoardType", "productName", "buildVersion"]

  static func read() -> [(String, String)] {
    _ = dlopen("/System/Library/PrivateFrameworks/AppleNeuralEngine.framework/AppleNeuralEngine", RTLD_NOW)
    guard let cls: AnyClass = NSClassFromString("_ANEDeviceInfo") else { return [("error", "no _ANEDeviceInfo")] }
    var model = utsname()
    uname(&model)
    let hw = withUnsafeBytes(of: &model.machine) { String(decoding: $0.prefix { $0 != 0 }, as: UTF8.self) }
    var out: [(String, String)] = [("hw.machine", hw)]
    for key in keys {
      let sel = NSSelectorFromString(key)
      guard let m = class_getClassMethod(cls, sel) else { out.append((key, "(none)")); continue }
      let ret = method_copyReturnType(m)
      let enc = String(cString: ret)
      free(ret)
      let imp = method_getImplementation(m)
      switch enc.first {
      case "@":
        typealias F = @convention(c) (AnyClass, Selector) -> Unmanaged<AnyObject>?
        let v = unsafeBitCast(imp, to: F.self)(cls, sel)
        out.append((key, v.map { "\($0.takeUnretainedValue())" } ?? "nil"))
      case "B":
        typealias F = @convention(c) (AnyClass, Selector) -> Bool
        out.append((key, "\(unsafeBitCast(imp, to: F.self)(cls, sel))"))
      default:
        typealias F = @convention(c) (AnyClass, Selector) -> Int
        out.append((key, "\(unsafeBitCast(imp, to: F.self)(cls, sel))"))
      }
    }
    return out
  }
}

@main
struct ANEInfoApp: App {
  init() {   // 同时打印到标准输出，供 devicectl --console 读取
    for (k, v) in ANEInfo.read() { print("\(k) = \(v)") }
  }

  var body: some Scene { WindowGroup { ContentView() } }
}

struct ContentView: View {
  let rows = ANEInfo.read()
  var text: String { rows.map { "\($0.0) = \($0.1)" }.joined(separator: "\n") }

  var body: some View {
    NavigationStack {
      List(rows, id: \.0) { row in
        HStack {
          Text(row.0).font(.system(.body, design: .monospaced))
          Spacer()
          Text(row.1).font(.system(.body, design: .monospaced)).bold()
        }
      }
      .navigationTitle("ANE Info")
      .toolbar { Button("Copy") { UIPasteboard.general.string = text } }
    }
  }
}
