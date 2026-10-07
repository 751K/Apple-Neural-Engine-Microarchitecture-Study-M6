// 打印本机 ANE 的身份：私有类 _ANEDeviceInfo（AppleNeuralEngine.framework）报告的架构名、子类型、变体、核数等。
// 例：M4 报 aneArchitectureType = h16g，即 aneSubType = h16 加 aneSubTypeVariant = g。
// iPhone / iPad 上用同一组调用的 App 在 aneinfo-ios/（需真机，模拟器没有 ANE）。
// 编译：clang -fobjc-arc -framework Foundation anedevinfo.m -o anedevinfo
// 用法：./anedevinfo
#import <Foundation/Foundation.h>
#import <objc/message.h>
#include <dlfcn.h>

int main(void) {
  @autoreleasepool {
    dlopen("/System/Library/PrivateFrameworks/AppleNeuralEngine.framework/AppleNeuralEngine", RTLD_NOW);
    Class c = NSClassFromString(@"_ANEDeviceInfo");
    if (!c) { puts("没有 _ANEDeviceInfo"); return 1; }
    for (NSString *s in @[ @"aneArchitectureType", @"aneSubType", @"aneSubTypeVariant", @"numANECores", @"numANEs",
                           @"hasANE", @"aneBoardType", @"productName", @"buildVersion" ]) {
      SEL sel = NSSelectorFromString(s);
      if (![c respondsToSelector:sel]) { printf("%-20s （无此方法）\n", s.UTF8String); continue; }
      const char *t = [c methodSignatureForSelector:sel].methodReturnType;
      if (t[0] == '@') {
        id v = ((id(*)(id, SEL))objc_msgSend)(c, sel);
        printf("%-20s %s\n", s.UTF8String, [[v description] UTF8String]);
      } else if (t[0] == 'B') {
        printf("%-20s %d\n", s.UTF8String, ((BOOL(*)(id, SEL))objc_msgSend)(c, sel));
      } else {
        printf("%-20s %ld\n", s.UTF8String, ((long(*)(id, SEL))objc_msgSend)(c, sel));
      }
    }
  }
  return 0;
}
