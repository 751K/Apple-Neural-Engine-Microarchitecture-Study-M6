// 用公开接口 MLModel compileModelAtURL 把 .mlpackage 编译成 .mlmodelc（替代需要 Xcode 的 coremlcompiler）
// 用法：./mlcompile <x.mlpackage> <输出目录>   编译：clang -fobjc-arc -O2 mlcompile.m -framework Foundation -framework CoreML -o mlcompile
#import <CoreML/CoreML.h>
int main(int argc, char **argv) { @autoreleasepool {
  if (argc < 3) return 2;
  NSURL *src = [NSURL fileURLWithPath:[NSString stringWithUTF8String:argv[1]]];
  NSError *e = nil; NSURL *tmp = [MLModel compileModelAtURL:src error:&e];
  if (!tmp) { fprintf(stderr, "%s\n", e.description.UTF8String); return 1; }
  NSString *name = [[src.lastPathComponent stringByDeletingPathExtension] stringByAppendingString:@".mlmodelc"];
  NSString *dst = [[NSString stringWithUTF8String:argv[2]] stringByAppendingPathComponent:name];
  NSFileManager *fm = NSFileManager.defaultManager; [fm removeItemAtPath:dst error:nil];
  if (![fm moveItemAtURL:tmp toURL:[NSURL fileURLWithPath:dst] error:&e]) { fprintf(stderr, "%s\n", e.description.UTF8String); return 1; }
  return 0; } }
