// 同一进程内多线程并发调用 Core ML（H15）：每组 = 一个 mlmodelc + 线程数 + 是否各自加载一份 MLModel。
// 所有线程先各自预热，然后在同一时刻开始，连续调用 <秒数>；输出每组的调用次数、吞吐、中位耗时，
// 以及这段时间里两个 ANE 各自的中断次数（IOReport，不需要 root）。
//
// 用法：./mtrun <秒数> <mlmodelc>:<线程数>[:own] [<mlmodelc>:<线程数>[:own] ...]
//   own：每个线程各自加载一个 MLModel 对象；不写则该组线程共用一个对象。
// 编译：clang -fobjc-arc -O2 mtrun.m -framework Foundation -framework CoreML -o mtrun
#import <CoreML/CoreML.h>
#import <Foundation/Foundation.h>
#include <dlfcn.h>
#include <mach/mach_time.h>
#include <pthread.h>
#include <stdatomic.h>

typedef CFMutableDictionaryRef (*copy_group_fn)(CFStringRef, CFStringRef, uint64_t, uint64_t, uint64_t);
typedef void *(*create_sub_fn)(void *, CFMutableDictionaryRef, CFMutableDictionaryRef *, uint64_t, CFTypeRef);
typedef CFDictionaryRef (*create_samples_fn)(void *, CFMutableDictionaryRef, CFTypeRef);
typedef CFDictionaryRef (*samples_delta_fn)(CFDictionaryRef, CFDictionaryRef, CFTypeRef);
typedef CFStringRef (*get_str_fn)(CFDictionaryRef);
typedef int64_t (*get_int_fn)(CFDictionaryRef, int32_t);

static create_samples_fn create_samples;
static samples_delta_fn samples_delta;
static get_str_fn ch_group, ch_subgroup, ch_name;
static get_int_fn int_value;
static void *sub;
static CFMutableDictionaryRef subbed;

static void cfstr(CFStringRef s, char *buf, size_t n) {
  buf[0] = 0;
  if (s) CFStringGetCString(s, buf, (CFIndex)n, kCFStringEncodingUTF8);
}

static void ior_open(void) {
  void *lib = dlopen("/usr/lib/libIOReport.dylib", RTLD_LAZY);
  copy_group_fn copy_group = dlsym(lib, "IOReportCopyChannelsInGroup");
  create_sub_fn create_sub = dlsym(lib, "IOReportCreateSubscription");
  create_samples = dlsym(lib, "IOReportCreateSamples");
  samples_delta = dlsym(lib, "IOReportCreateSamplesDelta");
  ch_group = dlsym(lib, "IOReportChannelGetGroup");
  ch_subgroup = dlsym(lib, "IOReportChannelGetSubGroup");
  ch_name = dlsym(lib, "IOReportChannelGetChannelName");
  int_value = dlsym(lib, "IOReportSimpleGetIntegerValue");
  CFMutableDictionaryRef irq = copy_group(CFSTR("Interrupt Statistics (by index)"), NULL, 0, 0, 0);
  sub = create_sub(NULL, irq, &subbed, 0, NULL);
}

// "ane 2" → 0，"ane1 2" → 1；不是 ANE 的返回 -1。
static int irq_engine(const char *s) {
  if (strncasecmp(s, "ane", 3) != 0) return -1;
  s += 3;
  int e = 0, digits = 0;
  while (*s >= '0' && *s <= '9') e = e * 10 + (*s++ - '0'), digits++;
  return *s == ' ' ? (digits ? e : 0) : -1;
}

static void irq_delta(CFDictionaryRef a, CFDictionaryRef b, uint64_t irq[2]) {
  irq[0] = irq[1] = 0;
  CFDictionaryRef d = samples_delta(a, b, NULL);
  CFArrayRef arr = CFDictionaryGetValue(d, CFSTR("IOReportChannels"));
  char grp[128], sg[128], name[128];
  for (CFIndex i = 0; arr && i < CFArrayGetCount(arr); i++) {
    CFDictionaryRef ch = CFArrayGetValueAtIndex(arr, i);
    cfstr(ch_group(ch), grp, sizeof grp);
    cfstr(ch_subgroup(ch), sg, sizeof sg);
    cfstr(ch_name(ch), name, sizeof name);
    int e = irq_engine(sg);
    if (e >= 0 && e < 2 && strstr(name, "First Level Interrupt Handler Count")) {
      int64_t x = int_value(ch, 0);
      if (x > 0) irq[e] += (uint64_t)x;
    }
  }
  CFRelease(d);
}

static MLModel *load(const char *path) {
  MLModelConfiguration *cfg = [MLModelConfiguration new];
  cfg.computeUnits = MLComputeUnitsCPUAndNeuralEngine;
  NSError *err = nil;
  MLModel *m = [MLModel modelWithContentsOfURL:[NSURL fileURLWithPath:@(path)] configuration:cfg error:&err];
  if (!m) { fprintf(stderr, "load %s: %s\n", path, err.description.UTF8String); exit(1); }
  return m;
}

static id<MLFeatureProvider> inputs_for(MLModel *m) {
  NSError *err = nil;
  NSMutableDictionary *feats = [NSMutableDictionary dictionary];
  for (NSString *k in m.modelDescription.inputDescriptionsByName) {
    MLMultiArrayConstraint *c = m.modelDescription.inputDescriptionsByName[k].multiArrayConstraint;
    MLMultiArray *a = [[MLMultiArray alloc] initWithShape:c.shape dataType:MLMultiArrayDataTypeFloat16 error:&err];
    memset(a.dataPointer, 0, a.count * 2);
    feats[k] = [MLFeatureValue featureValueWithMultiArray:a];
  }
  return [[MLDictionaryFeatureProvider alloc] initWithDictionary:feats error:&err];
}

typedef struct {
  MLModel *__unsafe_unretained model;
  int group;
  double *lat;  // 每次调用耗时（微秒）
  int cap, n;
} worker;

static mach_timebase_info_data_t tb;
static atomic_int ready;  // 预热完成的线程数（macOS 没有 pthread_barrier）
static volatile uint64_t t_start, t_stop;

static double now_s(void) { return (double)mach_absolute_time() * tb.numer / tb.denom / 1e9; }

static void *run(void *arg) {
  worker *w = arg;
  @autoreleasepool {
    id<MLFeatureProvider> in = inputs_for(w->model);
    double w0 = now_s();
    while (now_s() - w0 < 1.0) @autoreleasepool { [w->model predictionFromFeatures:in error:nil]; }  // 预热 1 s
    atomic_fetch_add(&ready, 1);
    while (!t_start || mach_absolute_time() < t_start) ;
    while (mach_absolute_time() < t_stop && w->n < w->cap) {
      uint64_t t = mach_absolute_time();
      @autoreleasepool { [w->model predictionFromFeatures:in error:nil]; }
      w->lat[w->n++] = (double)(mach_absolute_time() - t) * tb.numer / tb.denom / 1e3;
    }
  }
  return NULL;
}

static int cmp_double(const void *a, const void *b) {
  double x = *(const double *)a, y = *(const double *)b;
  return (x > y) - (x < y);
}

int main(int argc, char **argv) {
  @autoreleasepool {
    if (argc < 3) { fprintf(stderr, "usage: %s <secs> <mlmodelc>:<threads>[:own] ...\n", argv[0]); return 2; }
    mach_timebase_info(&tb);
    double secs = atof(argv[1]);
    ior_open();
    int ngroups = argc - 2, nw = 0;
    worker ws[64];
    NSMutableArray *keep = [NSMutableArray array];
    char *names[16];
    for (int g = 0; g < ngroups; g++) {
      char *spec = strdup(argv[g + 2]);
      char *path = strsep(&spec, ":");
      int threads = atoi(strsep(&spec, ":") ?: "1");
      int own = spec && !strcmp(spec, "own");
      names[g] = path;
      MLModel *shared = own ? nil : load(path);
      if (shared) [keep addObject:shared];
      for (int t = 0; t < threads; t++) {
        MLModel *m = shared ?: load(path);
        if (!shared) [keep addObject:m];
        ws[nw] = (worker){m, g, malloc(sizeof(double) * 200000), 200000, 0};
        nw++;
      }
      printf("组 %d：%s  %d 线程  %s\n", g, path, threads, own ? "各自一个 MLModel" : "共用一个 MLModel");
    }
    pthread_t th[64];
    for (int i = 0; i < nw; i++) pthread_create(&th[i], NULL, run, &ws[i]);
    while (atomic_load(&ready) < nw) usleep(1000);
    uint64_t now = mach_absolute_time();
    t_stop = now + (uint64_t)((0.05 + secs) * 1e9 * tb.denom / tb.numer);
    t_start = now + (uint64_t)(0.05e9 * tb.denom / tb.numer);
    while (mach_absolute_time() < t_start) ;
    CFDictionaryRef s0 = create_samples(sub, subbed, NULL);
    while (mach_absolute_time() < t_stop) usleep(1000);
    CFDictionaryRef s1 = create_samples(sub, subbed, NULL);
    for (int i = 0; i < nw; i++) pthread_join(th[i], NULL);
    uint64_t irq[2];
    irq_delta(s0, s1, irq);
    int total_calls = 0;
    for (int g = 0; g < ngroups; g++) {
      int calls = 0, k = 0;
      for (int i = 0; i < nw; i++) if (ws[i].group == g) calls += ws[i].n;
      double *all = malloc(sizeof(double) * (calls + 1));
      for (int i = 0; i < nw; i++)
        if (ws[i].group == g) { memcpy(all + k, ws[i].lat, sizeof(double) * ws[i].n); k += ws[i].n; }
      qsort(all, calls, sizeof(double), cmp_double);
      printf("  组 %d：%d 次（%.1f 次/s）  每次中位数 %.1f us  p10 %.1f  p90 %.1f  各线程:", g, calls, calls / secs,
             calls ? all[calls / 2] : 0, calls ? all[calls / 10] : 0, calls ? all[calls * 9 / 10] : 0);
      for (int i = 0; i < nw; i++) if (ws[i].group == g) printf(" %d", ws[i].n);
      printf("\n");
      total_calls += calls;
      free(all);
    }
    printf("  合计 %.1f 次/s  ANE0 中断 %llu（%.2f 次/调用）  ANE1 中断 %llu（%.2f 次/调用）\n", total_calls / secs, irq[0],
           (double)irq[0] / total_calls, irq[1], (double)irq[1] / total_calls);
    return 0;
  }
}
