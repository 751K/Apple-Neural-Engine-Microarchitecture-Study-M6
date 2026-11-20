// 用系统端侧模型（FoundationModels）生成一段文本，打印首词元延迟、生成速度和时间戳，供与 anemon 的记录对齐。
// 编译：swiftc -O -parse-as-library fmprobe.swift -o fmprobe；运行：anemon --json --interval 1 > a.jsonl & ./fmprobe 4
import Foundation
import FoundationModels

@main struct FMProbe {
    static func main() async throws {
        let model = SystemLanguageModel.default
        print("availability:", model.availability)
        guard case .available = model.availability else { return }
        let rounds = Int(CommandLine.arguments.dropFirst().first ?? "3") ?? 3
        let prompt = "Write a detailed, 400-word essay about the history of the printing press."
        for r in 0..<rounds {
            let session = LanguageModelSession()
            let t0 = Date()
            var first: Date? = nil
            var text = ""
            for try await part in session.streamResponse(to: prompt, options: GenerationOptions(sampling: .greedy, maximumResponseTokens: 600)) {
                if first == nil { first = Date() }
                text = part.content
            }
            let t1 = Date()
            let words = text.split(whereSeparator: { $0.isWhitespace }).count
            let toks = try await model.tokenCount(for: text)
            let ttft = first!.timeIntervalSince(t0), gen = t1.timeIntervalSince(first!)
            print(String(format: "round %d start %.3f ttft %.3f s gen %.2f s chars %d words %d tokens %d tok/s %.1f",
                         r, t0.timeIntervalSince1970, ttft, gen, text.count, words, toks, Double(toks) / gen))
        }
    }
}
