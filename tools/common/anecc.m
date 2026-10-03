// 在本进程内调用 ANECompiler 的 ANECCompile，把 MIL 编译成 HWX，输出到指定目录
// 用法：./anecc <mlmodelc 目录> <输出目录> [目标架构，默认 h18] [额外选项 key=value ...]
// 选项键是 flags 字典的驼峰式键名（如 DumpParallelScore、DisableNetworkImbalanceAnalysis），不是命令行参数名；目标选项（DebugMask 等）写成 all.键=值
#import <Foundation/Foundation.h>
#include <dlfcn.h>

typedef int (*ANECCompileFn)(CFDictionaryRef options, CFDictionaryRef flags, unsigned long reserved);

int main(int argc, char **argv) {
  @autoreleasepool {
    if (argc < 3) { fprintf(stderr, "usage: %s mlmodelc outdir [arch] [k=v ...]\n", argv[0]); return 2; }
    void *h = dlopen("/System/Library/PrivateFrameworks/ANECompiler.framework/ANECompiler", RTLD_NOW);
    ANECCompileFn compile = (ANECCompileFn)dlsym(h, "ANECCompile");
    if (!compile) { fprintf(stderr, "no ANECCompile\n"); return 1; }

    NSString *src = [[NSString stringWithUTF8String:argv[1]] stringByStandardizingPath];
    NSString *out = [[NSString stringWithUTF8String:argv[2]] stringByStandardizingPath];
    NSString *arch = argc > 3 ? [NSString stringWithUTF8String:argv[3]] : @"h18";
    [[NSFileManager defaultManager] createDirectoryAtPath:out withIntermediateDirectories:YES attributes:nil error:nil];

    NSMutableDictionary *options = [@{
      @"InputNetworks" : @[ @{
        @"NetworkSourceFileName" : @"model.mil",
        @"NetworkSourcePath" : [src stringByAppendingString:@"/"],
      } ],
      @"OutputFileName" : @"model.hwx",
      @"OutputFilePath" : [out stringByAppendingString:@"/"],
    } mutableCopy];
    NSMutableDictionary *flags = [@{ @"TargetArchitecture" : arch } mutableCopy];
    for (int i = 4; i < argc; i++) {
      NSArray *kv = [[NSString stringWithUTF8String:argv[i]] componentsSeparatedByString:@"="];
      if (kv.count != 2) continue;
      // true / false → 布尔值，十进制或 0x 开头的数 → 整数，其余保持字符串（编译器对类型敏感）
      NSString *v = kv[1];
      // "子字典.键=值"：放进 flags[子字典]（如 all.DebugMask=0x800 → flags["all"]["DebugMask"]）；目标选项（ANECGetTargetOptions）只从
      // flags["all"] 和 flags[目标架构名] 这两个子字典里读
      // 前缀 "O:" 表示放进 options 字典（ANECCompile 的第一个参数）而不是 flags
      NSMutableDictionary *base = flags; NSString *key = kv[0];
      if ([key hasPrefix:@"O:"]) { base = options; key = [key substringFromIndex:2]; }
      NSMutableDictionary *dst = base;
      NSRange dot = [key rangeOfString:@"."];
      if (dot.location != NSNotFound) {
        NSString *sub = [key substringToIndex:dot.location];
        key = [key substringFromIndex:dot.location + 1];
        if (![base[sub] isKindOfClass:[NSMutableDictionary class]]) base[sub] = [NSMutableDictionary dictionary];
        dst = base[sub];
      }
      if ([v isEqualToString:@"true"] || [v isEqualToString:@"false"]) dst[key] = @([v isEqualToString:@"true"]);
      else if ([v hasPrefix:@"0x"]) dst[key] = @(strtoull(v.UTF8String, NULL, 16));
      else if (v.length && [v rangeOfCharacterFromSet:[[NSCharacterSet characterSetWithCharactersInString:@"-0123456789"] invertedSet]].location == NSNotFound) dst[key] = @(v.longLongValue);
      else dst[key] = v;
    }
    fprintf(stderr, "options %s\nflags %s\n", options.description.UTF8String, flags.description.UTF8String);
    int ret = compile((__bridge CFDictionaryRef)options, (__bridge CFDictionaryRef)flags, 0);
    fprintf(stderr, "ANECCompile returned %d\n", ret);
    return ret;
  }
}
