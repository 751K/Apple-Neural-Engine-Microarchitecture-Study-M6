// 同一进程内不同的提交方式（10.7 节）：同步逐个调用、异步保持 K 个请求在途、一次提交 B 个的批量调用。
// 连续运行 <秒数>，输出每秒推理次数（吞吐）、单次延迟，以及这段时间里两个 ANE 各自的中断次数和
// DCS BW 读带宽直方图（IOReport，不需要 root；与 bondrun 相同）。
//
// 用法：./asyncrun <mlmodelc> <秒数> sync
//       ./asyncrun <mlmodelc> <秒数> async <K>     -[MLModel predictionFromFeatures:completionHandler:]（macOS 14+），信号量保持 K 个在途
//       ./asyncrun <mlmodelc> <秒数> batch <B>     -[MLModel predictionsFromBatch:error:]，每次 B 个输入
// 计时前先用同步调用预热 1 s（ANE 时钟升到稳态）。
// 编译：clang -fobjc-arc -O2 asyncrun.m -framework Foundation -framework CoreML -o asyncrun
#import <CoreML/CoreML.h>
#import <Foundation/Foundation.h>
#include <dlfcn.h>
#include <mach/mach_time.h>

typedef CFMutableDictionaryRef (*copy_group_fn)(CFStringRef, CFStringRef, uint64_t, uint64_t, uint64_t);
typedef void (*merge_fn)(CFMutableDictionaryRef, CFMutableDictionaryRef, CFTypeRef);
typedef void *(*create_sub_fn)(void *, CFMutableDictionaryRef, CFMutableDictionaryRef *, uint64_t, CFTypeRef);
typedef CFDictionaryRef (*create_samples_fn)(void *, CFMutableDictionaryRef, CFTypeRef);
typedef CFDictionaryRef (*samples_delta_fn)(CFDictionaryRef, CFDictionaryRef, CFTypeRef);
typedef CFStringRef (*get_str_fn)(CFDictionaryRef);
typedef int64_t (*get_int_fn)(CFDictionaryRef, int32_t);
typedef int32_t (*get_i32_fn)(CFDictionaryRef);
typedef CFStringRef (*state_name_fn)(CFDictionaryRef, int32_t);
typedef int64_t (*state_res_fn)(CFDictionaryRef, int32_t);

static copy_group_fn copy_group;
static merge_fn merge;
static create_sub_fn create_sub;
static create_samples_fn create_samples;
static samples_delta_fn samples_delta;
static get_str_fn ch_group, ch_subgroup, ch_name;
static get_int_fn int_value;
static get_i32_fn ch_format, state_count;
static state_name_fn state_name;
static state_res_fn residency;
static void *sub;
static CFMutableDictionaryRef subbed;

static void cfstr(CFStringRef s, char *buf, size_t n) {
  buf[0] = 0;
  if (s) CFStringGetCString(s, buf, (CFIndex)n, kCFStringEncodingUTF8);
}

static int ior_open(void) {
  void *lib = dlopen("/usr/lib/libIOReport.dylib", RTLD_LAZY);
  if (!lib) return -1;
  copy_group = dlsym(lib, "IOReportCopyChannelsInGroup");
  merge = dlsym(lib, "IOReportMergeChannels");
  create_sub = dlsym(lib, "IOReportCreateSubscription");
  create_samples = dlsym(lib, "IOReportCreateSamples");
  samples_delta = dlsym(lib, "IOReportCreateSamplesDelta");
  ch_group = dlsym(lib, "IOReportChannelGetGroup");
  ch_subgroup = dlsym(lib, "IOReportChannelGetSubGroup");
  ch_name = dlsym(lib, "IOReportChannelGetChannelName");
  int_value = dlsym(lib, "IOReportSimpleGetIntegerValue");
  ch_format = dlsym(lib, "IOReportChannelGetFormat");
  state_count = dlsym(lib, "IOReportStateGetCount");
  state_name = dlsym(lib, "IOReportStateGetNameForIndex");
  residency = dlsym(lib, "IOReportStateGetResidency");
  CFMutableDictionaryRef bw = copy_group(CFSTR("PMP"), CFSTR("DCS BW"), 0, 0, 0);
  CFMutableDictionaryRef irq = copy_group(CFSTR("Interrupt Statistics (by index)"), NULL, 0, 0, 0);
  CFMutableDictionaryRef pmgr = copy_group(CFSTR("SoC Stats"), CFSTR("PMGR Counters"), 0, 0, 0);
  if (!bw || !irq) return -1;
  merge(bw, irq, NULL);
  if (pmgr) merge(bw, pmgr, NULL);
  sub = create_sub(NULL, bw, &subbed, 0, NULL);
  return sub && subbed ? 0 : -1;
}

// "ane 2" → 0，"ane1 2" → 1；不是 ANE 的返回 -1。
static int irq_engine(const char *s) {
  if (strncasecmp(s, "ane", 3) != 0) return -1;
  s += 3;
  int e = 0, digits = 0;
  while (*s >= '0' && *s <= '9') e = e * 10 + (*s++ - '0'), digits++;
  return *s == ' ' ? (digits ? e : 0) : -1;
}

// "ANE1 L0 RD" → 引擎 1、方向 1（读）；WR 为 2。
static int link_engine(const char *s, int *dir) {
  if (strncmp(s, "ANE", 3) != 0 || s[3] < '0' || s[3] > '9') return -1;
  int e = atoi(s + 3);
  size_t n = strlen(s);
  if (n > 3 && strcmp(s + n - 3, " RD") == 0) *dir = 1;
  else if (n > 3 && strcmp(s + n - 3, " WR") == 0 && !strstr(s, "RD+WR")) *dir = 2;
  else return -1;
  return e;
}

typedef struct {
  uint64_t irq[2];
  double bw_sum[2][3];  // [引擎][方向]：Σ(档位中值 GB/s × 采样数)
  uint64_t bw_n[2][3];  // 链路活跃的采样数
  int64_t dpe_ticks;    // ANE0_DPE_CLK_ON：ANE0 计算单元时钟开启时间（24 MHz tick）
} engine_stats;

static void ior_delta(CFDictionaryRef a, CFDictionaryRef b, engine_stats *st) {
  memset(st, 0, sizeof *st);
  CFDictionaryRef d = samples_delta(a, b, NULL);
  CFArrayRef arr = CFDictionaryGetValue(d, CFSTR("IOReportChannels"));
  char grp[128], sg[128], name[128], st_name[64];
  for (CFIndex i = 0; arr && i < CFArrayGetCount(arr); i++) {
    CFDictionaryRef ch = CFArrayGetValueAtIndex(arr, i);
    cfstr(ch_group(ch), grp, sizeof grp);
    cfstr(ch_subgroup(ch), sg, sizeof sg);
    cfstr(ch_name(ch), name, sizeof name);
    if (!strcmp(name, "ANE0_DPE_CLK_ON")) {
      st->dpe_ticks = int_value(ch, 0);
      continue;
    }
    if (strncmp(grp, "Interrupt Statistics", 20) == 0) {
      int e = irq_engine(sg);
      if (e >= 0 && e < 2 && strstr(name, "First Level Interrupt Handler Count")) {
        int64_t x = int_value(ch, 0);
        if (x > 0) st->irq[e] += (uint64_t)x;
      }
    } else if (strcmp(grp, "PMP") == 0 && ch_format(ch) == 2) {
      int dir = 0, e = link_engine(name, &dir);
      if (e < 0 || e > 1) continue;
      double lower = 0;
      int32_t c = state_count(ch);
      for (int32_t j = 0; j < c; j++) {
        cfstr(state_name(ch, j), st_name, sizeof st_name);
        double upper = atof(st_name), mid = j == c - 1 ? upper : (lower + upper) / 2;
        lower = upper;
        int64_t r = residency(ch, j);
        if (r <= 0) continue;
        st->bw_sum[e][dir] += mid * (double)r;
        st->bw_n[e][dir] += (uint64_t)r;
      }
    }
  }
  CFRelease(d);
}

static int cmp_double(const void *a, const void *b) {
  double x = *(const double *)a, y = *(const double *)b;
  return (x > y) - (x < y);
}

static double now_us(void) {
  static mach_timebase_info_data_t tb;
  if (!tb.denom) mach_timebase_info(&tb);
  return mach_absolute_time() * (double)tb.numer / tb.denom / 1e3;
}

int main(int argc, char **argv) {
  @autoreleasepool {
    if (argc < 4) {
      fprintf(stderr, "usage: %s <mlmodelc> <seconds> sync | async <K> | batch <B>\n", argv[0]);
      return 2;
    }
    double secs = atof(argv[2]);
    const char *mode = argv[3];
    int k = argc > 4 ? atoi(argv[4]) : 1;
    if (ior_open() != 0) fprintf(stderr, "IOReport 不可用，只测时间\n");

    MLModelConfiguration *cfg = [MLModelConfiguration new];
    cfg.computeUnits = MLComputeUnitsCPUAndNeuralEngine;
    NSError *err = nil;
    MLModel *model = [MLModel modelWithContentsOfURL:[NSURL fileURLWithPath:@(argv[1])] configuration:cfg error:&err];
    if (!model) {
      fprintf(stderr, "load: %s\n", err.description.UTF8String);
      return 1;
    }
    NSMutableDictionary *feats = [NSMutableDictionary dictionary];
    for (NSString *key in model.modelDescription.inputDescriptionsByName) {
      MLMultiArrayConstraint *c = model.modelDescription.inputDescriptionsByName[key].multiArrayConstraint;
      MLMultiArray *a = [[MLMultiArray alloc] initWithShape:c.shape dataType:MLMultiArrayDataTypeFloat16 error:&err];
      __fp16 *p = a.dataPointer;
      for (NSInteger i = 0; i < a.count; i++) p[i] = (__fp16)((arc4random_uniform(2000) - 1000) / 1000.0f);
      feats[key] = [MLFeatureValue featureValueWithMultiArray:a];
    }
    MLDictionaryFeatureProvider *in = [[MLDictionaryFeatureProvider alloc] initWithDictionary:feats error:&err];

    double w0 = now_us();
    while (now_us() - w0 < 1e6)
      @autoreleasepool { [model predictionFromFeatures:in error:&err]; }
    if (err) {
      fprintf(stderr, "predict: %s\n", err.description.UTF8String);
      return 1;
    }

    size_t cap = 1 << 22, n = 0;
    double *lat = calloc(cap, sizeof(double));
    __block long done = 0;
    CFDictionaryRef s0 = sub ? create_samples(sub, subbed, NULL) : NULL;
    double t0 = now_us(), t1 = t0;
    if (!strcmp(mode, "sync")) {
      while ((t1 = now_us()) - t0 < secs * 1e6) {
        @autoreleasepool { [model predictionFromFeatures:in error:&err]; }
        double t = now_us();
        if (n < cap) lat[n++] = t - t1;
        done++;
      }
    } else if (!strcmp(mode, "async")) {
      dispatch_semaphore_t slots = dispatch_semaphore_create(k);
      dispatch_group_t g = dispatch_group_create();
      __block double *latp = lat;
      __block size_t *np = &n;
      NSLock *lock = [NSLock new];
      while ((t1 = now_us()) - t0 < secs * 1e6) {
        dispatch_semaphore_wait(slots, DISPATCH_TIME_FOREVER);
        double ts = now_us();
        dispatch_group_enter(g);
        [model predictionFromFeatures:in completionHandler:^(id<MLFeatureProvider> out, NSError *e) {
          double t = now_us();
          [lock lock];
          if (*np < cap) latp[(*np)++] = t - ts;
          done++;
          [lock unlock];
          dispatch_semaphore_signal(slots);
          dispatch_group_leave(g);
        }];
      }
      dispatch_group_wait(g, DISPATCH_TIME_FOREVER);
      t1 = now_us();
    } else if (!strcmp(mode, "batch")) {
      NSMutableArray *arr = [NSMutableArray arrayWithCapacity:k];
      for (int i = 0; i < k; i++) [arr addObject:in];
      MLArrayBatchProvider *batch = [[MLArrayBatchProvider alloc] initWithFeatureProviderArray:arr];
      while ((t1 = now_us()) - t0 < secs * 1e6) {
        @autoreleasepool { [model predictionsFromBatch:batch error:&err]; }
        double t = now_us();
        if (n < cap) lat[n++] = t - t1;
        done += k;
      }
    } else {
      fprintf(stderr, "unknown mode %s\n", mode);
      return 2;
    }
    double wall_s = (t1 - t0) / 1e6;
    CFDictionaryRef s1 = sub ? create_samples(sub, subbed, NULL) : NULL;
    if (err) fprintf(stderr, "predict: %s\n", err.description.UTF8String);

    qsort(lat, n, sizeof(double), cmp_double);
    printf("%s %s %d\n", argv[1], mode, k);
    printf("  推理 %ld 次 / %.2f s = %.1f 次/s；每次%s耗时 中位数 %.1f us  p10 %.1f  p90 %.1f\n", done, wall_s,
           done / wall_s, !strcmp(mode, "batch") ? "批量调用" : "请求", lat[n / 2], lat[n / 10], lat[n * 9 / 10]);
    if (s0 && s1) {
      engine_stats st;
      ior_delta(s0, s1, &st);
      for (int e = 0; e < 2; e++) {
        printf("  ANE%d: 中断 %6llu（%.2f 次/推理）", e, st.irq[e], (double)st.irq[e] / done);
        for (int dir = 1; dir <= 2; dir++) {
          double avg = st.bw_n[e][dir] ? st.bw_sum[e][dir] / st.bw_n[e][dir] : 0;
          printf("  %s 活跃采样 %5llu 平均 %6.1f GB/s", dir == 1 ? "读" : "写", st.bw_n[e][dir], avg);
        }
        printf("\n");
      }
      printf("  总时长 %.2f s\n", wall_s);
    }
  }
  return 0;
}
