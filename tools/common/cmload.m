// 只计时 Core ML 的首次加载（含 ANE 编译）。每次运行前把可执行文件复制成新名字，
// Core ML 和 aned 的缓存按进程名区分，这样每次都会重新编译。
// 用法：./cmload <mlmodelc> [computeUnits: ane|cpu|all] [QoS: ui|init|default|utility|bg]
// 编译：clang -fobjc-arc -O2 cmload.m -framework Foundation -framework CoreML -o cmload
#import <CoreML/CoreML.h>
#import <Foundation/Foundation.h>
#include <mach/mach_time.h>
#include <pthread/qos.h>

int main(int argc, char **argv) {
  @autoreleasepool {
    MLModelConfiguration *cfg = [MLModelConfiguration new];
    cfg.computeUnits = MLComputeUnitsCPUAndNeuralEngine;
    if (argc > 2 && !strcmp(argv[2], "cpu")) cfg.computeUnits = MLComputeUnitsCPUOnly;
    if (argc > 2 && !strcmp(argv[2], "all")) cfg.computeUnits = MLComputeUnitsAll;
    if (argc > 3) {  // 发起加载的线程 QoS，会经 aned 传给编译服务（日志里的 clientQos）
      qos_class_t q = QOS_CLASS_DEFAULT;
      if (!strcmp(argv[3], "ui")) q = QOS_CLASS_USER_INTERACTIVE;
      if (!strcmp(argv[3], "init")) q = QOS_CLASS_USER_INITIATED;
      if (!strcmp(argv[3], "utility")) q = QOS_CLASS_UTILITY;
      if (!strcmp(argv[3], "bg")) q = QOS_CLASS_BACKGROUND;
      pthread_set_qos_class_self_np(q, 0);
    }
    mach_timebase_info_data_t tb;
    mach_timebase_info(&tb);
    uint64_t t = mach_absolute_time();
    NSError *err = nil;
    MLModel *m = [MLModel modelWithContentsOfURL:[NSURL fileURLWithPath:@(argv[1])] configuration:cfg error:&err];
    double s = (mach_absolute_time() - t) * tb.numer / tb.denom / 1e9;
    printf("%s 加载 %.2f s %s\n", argv[1], s, m ? "成功" : err.description.UTF8String);
    return 0;
  }
}
