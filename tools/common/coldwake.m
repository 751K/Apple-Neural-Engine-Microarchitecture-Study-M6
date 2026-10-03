// 冷唤醒与空闲电源状态：空闲 t 秒后，第一次调用和随后几次调用各要多久；空闲期间 ANE 处于哪种电源状态。
// 状态来自 IOReport：
//   - "ANE" / "ANE1" 组的 IOP State（Off / Sleep / Running 等驻留）；
//   - PMGR Counters 的 ANE0_DPE_CLK_ON、ANE0_CPU_POWER_ON、ANE1_CPU_POWER_ON（24 MHz tick）。
// "SoC Stats / Device States" 里的 ANE0_SYS 在满载时也显示 PWROFF 100%，不反映实际状态，所以不用。
//
// 用法：./coldwake <mlmodelc> [重复次数=3]
//       COLDWAKE_IDLES=5,6,8 ./coldwake ...：自定义空闲时长（秒）
//       COLDWAKE_TRACE=1 ./coldwake <mlmodelc> [重复次数]：稳态后空闲 12 s，每 100 ms 记录一次两个 IOP 的主要状态，
//       找出断电（Off）开始的时刻（H16）
// 编译：clang -fobjc-arc -O2 coldwake.m -framework Foundation -framework CoreML -o coldwake
#import <CoreML/CoreML.h>
#import <Foundation/Foundation.h>
#include <dlfcn.h>
#include <mach/mach_time.h>

typedef CFMutableDictionaryRef (*copy_group_fn)(CFStringRef, CFStringRef, uint64_t, uint64_t, uint64_t);
typedef void *(*create_sub_fn)(void *, CFMutableDictionaryRef, CFMutableDictionaryRef *, uint64_t, CFTypeRef);
typedef CFDictionaryRef (*create_samples_fn)(void *, CFMutableDictionaryRef, CFTypeRef);
typedef CFDictionaryRef (*delta_fn)(CFDictionaryRef, CFDictionaryRef, CFTypeRef);
typedef CFStringRef (*str_fn)(CFDictionaryRef);
typedef int32_t (*i32_fn)(CFDictionaryRef);
typedef int64_t (*int_fn)(CFDictionaryRef, int32_t);
typedef void (*merge_fn)(CFMutableDictionaryRef, CFMutableDictionaryRef, CFTypeRef);
typedef CFStringRef (*sname_fn)(CFDictionaryRef, int32_t);
typedef int64_t (*sres_fn)(CFDictionaryRef, int32_t);

static create_samples_fn samp;
static delta_fn delta;
static str_fn ch_name, ch_group;
static i32_fn ch_format;
static int_fn int_value;
static i32_fn state_count;
static sname_fn state_name;
static sres_fn residency;
static void *sub;
static CFMutableDictionaryRef subbed;

static void cs(CFStringRef s, char *b, size_t n) { b[0] = 0; if (s) CFStringGetCString(s, b, n, kCFStringEncodingUTF8); }

static void ior_open(void) {
  void *l = dlopen("/usr/lib/libIOReport.dylib", RTLD_LAZY);
  copy_group_fn cg = dlsym(l, "IOReportCopyChannelsInGroup");
  create_sub_fn csub = dlsym(l, "IOReportCreateSubscription");
  samp = dlsym(l, "IOReportCreateSamples");
  delta = dlsym(l, "IOReportCreateSamplesDelta");
  ch_name = dlsym(l, "IOReportChannelGetChannelName");
  state_count = dlsym(l, "IOReportStateGetCount");
  state_name = dlsym(l, "IOReportStateGetNameForIndex");
  residency = dlsym(l, "IOReportStateGetResidency");
  merge_fn merge = dlsym(l, "IOReportMergeChannels");
  ch_group = dlsym(l, "IOReportChannelGetGroup");
  ch_format = dlsym(l, "IOReportChannelGetFormat");
  int_value = dlsym(l, "IOReportSimpleGetIntegerValue");
  CFMutableDictionaryRef ch = cg(CFSTR("SoC Stats"), CFSTR("PMGR Counters"), 0, 0, 0);
  merge(ch, cg(CFSTR("ANE"), CFSTR("IOP State"), 0, 0, 0), NULL);
  merge(ch, cg(CFSTR("ANE1"), CFSTR("IOP State"), 0, 0, 0), NULL);
  sub = csub(NULL, ch, &subbed, 0, NULL);
}

// 打印两个样本之间：两个 ANE 的 IOP 状态驻留比例，以及时钟 / 电源开启时间占比
static void print_states(CFDictionaryRef a, CFDictionaryRef b, double secs) {
  CFDictionaryRef d = delta(a, b, NULL);
  CFArrayRef arr = CFDictionaryGetValue(d, CFSTR("IOReportChannels"));
  char n[128], g[64], s[64];
  for (CFIndex i = 0; arr && i < CFArrayGetCount(arr); i++) {
    CFDictionaryRef c = CFArrayGetValueAtIndex(arr, i);
    cs(ch_name(c), n, sizeof n);
    cs(ch_group(c), g, sizeof g);
    if (ch_format(c) == 2 && (!strcmp(g, "ANE") || !strcmp(g, "ANE1"))) {
      int k = state_count(c);
      double tot = 0;
      for (int j = 0; j < k; j++) tot += residency(c, j);
      printf("  %s IOP:", g);
      for (int j = 0; j < k; j++) {
        if (residency(c, j) <= 0) continue;
        cs(state_name(c, j), s, sizeof s);
        printf(" %s %.0f%%", s, 100.0 * residency(c, j) / tot);
      }
    } else if (!strcmp(n, "ANE0_DPE_CLK_ON") || !strcmp(n, "ANE0_CPU_POWER_ON") || !strcmp(n, "ANE1_CPU_POWER_ON")) {
      printf("  %s %.0f%%", n, 100.0 * int_value(c, 0) / (secs * 24e6));
    }
  }
  printf("\n");
  CFRelease(d);
}

int main(int argc, char **argv) {
  @autoreleasepool {
    if (argc < 2) { fprintf(stderr, "usage: %s <mlmodelc> [reps=3]\n", argv[0]); return 2; }
    int reps = argc > 2 ? atoi(argv[2]) : 3;
    ior_open();
    MLModelConfiguration *cfg = [MLModelConfiguration new];
    cfg.computeUnits = MLComputeUnitsCPUAndNeuralEngine;
    NSError *err = nil;
    MLModel *model = [MLModel modelWithContentsOfURL:[NSURL fileURLWithPath:@(argv[1])] configuration:cfg error:&err];
    if (!model) { fprintf(stderr, "load: %s\n", err.description.UTF8String); return 1; }
    NSMutableDictionary *feats = [NSMutableDictionary dictionary];
    for (NSString *k in model.modelDescription.inputDescriptionsByName) {
      MLMultiArrayConstraint *c = model.modelDescription.inputDescriptionsByName[k].multiArrayConstraint;
      MLMultiArray *a = [[MLMultiArray alloc] initWithShape:c.shape dataType:MLMultiArrayDataTypeFloat16 error:&err];
      memset(a.dataPointer, 0, a.count * 2);
      feats[k] = [MLFeatureValue featureValueWithMultiArray:a];
    }
    MLDictionaryFeatureProvider *in = [[MLDictionaryFeatureProvider alloc] initWithDictionary:feats error:&err];
    mach_timebase_info_data_t tb;
    mach_timebase_info(&tb);
    double (^call_us)(void) = ^double {
      uint64_t t = mach_absolute_time();
      @autoreleasepool { [model predictionFromFeatures:in error:nil]; }
      return (mach_absolute_time() - t) * tb.numer / tb.denom / 1e3;
    };
    // 稳态：连续调用 2 秒，取最后 200 次的中位数
    double steady[200];
    uint64_t w0 = mach_absolute_time();
    while ((mach_absolute_time() - w0) * tb.numer / tb.denom < 2e9) call_us();
    for (int i = 0; i < 200; i++) steady[i] = call_us();
    qsort_b(steady, 200, sizeof(double), ^int(const void *a, const void *b) {
      double x = *(const double *)a, y = *(const double *)b; return (x > y) - (x < y); });
    printf("%s\n稳态中位数 %.1f us\n", argv[1], steady[100]);
    if (getenv("COLDWAKE_TRACE")) {
      for (int r = 0; r < reps; r++) {
        for (int i = 0; i < 20; i++) call_us();  // 最后一次调用的结束时刻 = 空闲起点
        uint64_t t0 = mach_absolute_time();
        CFDictionaryRef prev = samp(sub, subbed, NULL);
        char last[2][64] = {"", ""};
        printf("第 %d 轮：\n", r + 1);
        int nk = getenv("COLDWAKE_SECS") ? atoi(getenv("COLDWAKE_SECS")) * 10 : 120;
        for (int k = 1; k <= nk; k++) {
          uint64_t target = t0 + (uint64_t)(k * 0.1e9 * tb.denom / tb.numer);
          while (mach_absolute_time() < target) usleep(1000);
          CFDictionaryRef cur = samp(sub, subbed, NULL);
          CFDictionaryRef d = delta(prev, cur, NULL);
          CFArrayRef arr = CFDictionaryGetValue(d, CFSTR("IOReportChannels"));
          char g[64], s[64];
          for (CFIndex i = 0; arr && i < CFArrayGetCount(arr); i++) {
            CFDictionaryRef c = CFArrayGetValueAtIndex(arr, i);
            cs(ch_group(c), g, sizeof g);
            if (ch_format(c) != 2) continue;
            int which = !strcmp(g, "ANE") ? 0 : !strcmp(g, "ANE1") ? 1 : -1;
            if (which < 0) continue;
            // 本 100 ms 内驻留不为 0 的状态，按顺序拼起来
            char buf[64] = "";
            for (int j = 0; j < state_count(c); j++)
              if (residency(c, j) > 0) {
                cs(state_name(c, j), s, sizeof s);
                if (buf[0]) strlcat(buf, "+", sizeof buf);
                strlcat(buf, s, sizeof buf);
              }
            if (strcmp(buf, last[which])) {
              printf("  %5.2f s  %s → %s\n", k * 0.1, which ? "ANE1" : "ANE ", buf);
              strlcpy(last[which], buf, sizeof last[which]);
            }
          }
          CFRelease(d);
          CFRelease(prev);
          prev = cur;
        }
        CFRelease(prev);
        double first = call_us();
        printf("  %.0f s 后第 1 次调用 %.1f us\n", nk / 10.0, first);
        w0 = mach_absolute_time();
        while ((mach_absolute_time() - w0) * tb.numer / tb.denom < 2e9) call_us();
      }
      return 0;
    }
    double idles[32] = {0.002, 0.01, 0.03, 0.1, 0.3, 1, 3, 10};
    size_t nidle = 8;
    if (getenv("COLDWAKE_IDLES")) {  // 逗号分隔的空闲秒数，例如 5,5.5,6,8,12,20
      nidle = 0;
      for (char *p = getenv("COLDWAKE_IDLES"); *p && nidle < 32; p++) {
        idles[nidle++] = strtod(p, &p);
        if (!*p) break;
      }
    }
    for (int r = 0; r < reps; r++) {
      for (size_t k = 0; k < nidle; k++) {
        CFDictionaryRef s0 = samp(sub, subbed, NULL);
        usleep((useconds_t)(idles[k] * 1e6));
        CFDictionaryRef s1 = samp(sub, subbed, NULL);
        double t[8];
        for (int i = 0; i < 8; i++) t[i] = call_us();
        printf("空闲 %6.3f s → 第 1 次 %8.1f us，第 2 次 %7.1f，第 8 次 %7.1f（稳态的 %.2f×）", idles[k], t[0], t[1], t[7],
               t[0] / steady[100]);
        print_states(s0, s1, idles[k]);
        CFRelease(s0);
        CFRelease(s1);
        // 每个点之间先恢复到稳态
        w0 = mach_absolute_time();
        while ((mach_absolute_time() - w0) * tb.numer / tb.denom < 1e9) call_us();
      }
    }
    return 0;
  }
}
