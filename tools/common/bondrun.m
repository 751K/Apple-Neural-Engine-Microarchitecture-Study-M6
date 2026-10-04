// 用公开的 Core ML 接口反复运行一个 mlmodelc，测每次调用耗时；同时用 IOReport（不需要 root）
// 记录这段时间里两个 ANE 各自的中断次数和 DRAM 链路带宽，判断实际用了哪个 ANE。
//
// 用法：./bondrun <mlmodelc> [次数=300] [每次的 GFLOP，用于算吞吐]
// 编译：clang -fobjc-arc -O2 bondrun.m -framework Foundation -framework CoreML -o bondrun
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

int main(int argc, char **argv) {
  @autoreleasepool {
    if (argc < 2) {
      fprintf(stderr, "usage: %s <mlmodelc> [iters=300] [gflop]\n", argv[0]);
      return 2;
    }
    int iters = argc > 2 ? atoi(argv[2]) : 300;
    double gflop = argc > 3 ? atof(argv[3]) : 0;
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
    for (NSString *k in model.modelDescription.inputDescriptionsByName) {
      MLMultiArrayConstraint *c = model.modelDescription.inputDescriptionsByName[k].multiArrayConstraint;
      MLMultiArray *a = [[MLMultiArray alloc] initWithShape:c.shape dataType:MLMultiArrayDataTypeFloat16 error:&err];
      __fp16 *p = a.dataPointer;
      // BONDRUN_FILL：默认 [-1, 1) 随机；zero 全为 0（看数据翻转对功耗的影响）；
      //   half 随机一半元素为 0；chan 前一半通道（轴 1）整体为 0（按 strides 定位，不假设连续存放）；
      //   chconst 每个通道一个随机常数（空间上处处相同；复现偏置非 0 的模型在全 0 输入下第 2 层起的激活）；
      //   negzero 全为 −0（0x8000：数值等于 0，位模式不是全 0）
      const char *fill = getenv("BONDRUN_FILL") ? getenv("BONDRUN_FILL") : "";
      int zero = !strcmp(fill, "zero"), half = !strcmp(fill, "half"), chan = !strcmp(fill, "chan");
      int chconst = !strcmp(fill, "chconst"), negzero = !strcmp(fill, "negzero");
      NSInteger nch = c.shape.count > 1 ? c.shape[1].integerValue : 1, cs = a.strides.count > 1 ? a.strides[1].integerValue : 1;
      for (NSInteger i = 0; i < a.count; i++) p[i] = (__fp16)((arc4random_uniform(2000) - 1000) / 1000.0f);
      if (zero) memset(p, 0, a.count * sizeof(__fp16));
      if (negzero)
        for (NSInteger i = 0; i < a.count; i++) ((uint16_t *)p)[i] = 0x8000;
      if (half)
        for (NSInteger i = 0; i < a.count; i++)
          if (arc4random_uniform(2)) p[i] = 0;
      if (chan)
        for (NSInteger ch = 0; ch < nch / 2; ch++)
          for (NSInteger j = 0; j < cs; j++) p[ch * cs + j] = 0;
      if (chconst)
        for (NSInteger ch = 0; ch < nch; ch++) {
          __fp16 v = (__fp16)((arc4random_uniform(2000) - 1000) / 1000.0f);
          for (NSInteger j = 0; j < cs; j++) p[ch * cs + j] = v;
        }
      feats[k] = [MLFeatureValue featureValueWithMultiArray:a];
    }
    MLDictionaryFeatureProvider *in = [[MLDictionaryFeatureProvider alloc] initWithDictionary:feats error:&err];

    // 空闲基线：不调用模型，等 0.5 秒，看两个 ANE 本身的中断背景
    if (sub) {
      CFDictionaryRef i0 = create_samples(sub, subbed, NULL);
      usleep(500000);
      CFDictionaryRef i1 = create_samples(sub, subbed, NULL);
      engine_stats st;
      ior_delta(i0, i1, &st);
      printf("  空闲 0.5 s：ANE0 中断 %llu，ANE1 中断 %llu\n", st.irq[0], st.irq[1]);
    }
    // 预热：连续调用至少 1 秒。从空闲开始约 0.3 s 内调用明显偏慢（实测 2.8 倍），推测是 ANE 时钟在爬升。
    // 空闲基线必须放在预热之前，否则空闲的 0.5 s 会让时钟又降下来。
    mach_timebase_info_data_t tb0;
    mach_timebase_info(&tb0);
    double warm_s = getenv("BONDRUN_WARM") ? atof(getenv("BONDRUN_WARM")) : 1.0;
    uint64_t w0 = mach_absolute_time();
    for (int i = 0; i < 20 || (mach_absolute_time() - w0) * tb0.numer / tb0.denom < warm_s * 1e9; i++)
      @autoreleasepool {
        [model predictionFromFeatures:in error:&err];
      }
    if (err) {
      fprintf(stderr, "predict: %s\n", err.description.UTF8String);
      return 1;
    }

    mach_timebase_info_data_t tb;
    mach_timebase_info(&tb);
    double *us = calloc(iters, sizeof(double));
    CFDictionaryRef s0 = sub ? create_samples(sub, subbed, NULL) : NULL;
    uint64_t t_all = mach_absolute_time();
    // BONDRUN_GAP=flush|spin，BONDRUN_GAP_MB=N：每次计时调用前插入一段间隔（不计入耗时）。
    //   flush：CPU 往 N MB 内存写一遍，冲掉系统级缓存（SLC）；
    //   spin：CPU 空转同样长的时间、不碰内存（对照：同样长的空闲间隔）。
    const char *gap = getenv("BONDRUN_GAP");
    size_t gap_bytes = (size_t)(getenv("BONDRUN_GAP_MB") ? atof(getenv("BONDRUN_GAP_MB")) : 128) << 20;
    char *gap_buf = gap ? malloc(gap_bytes) : NULL;
    double gap_us = 0;
    if (gap) {
      uint64_t g0 = mach_absolute_time();
      memset(gap_buf, 1, gap_bytes);
      gap_us = (mach_absolute_time() - g0) * tb.numer / tb.denom / 1e3;
      fprintf(stderr, "间隔模式 %s，%zu MB，每次约 %.0f us\n", gap, gap_bytes >> 20, gap_us);
    }
    // BONDRUN_SLEEP_US=N：每次计时调用前 usleep(N)（调占空比，不计入耗时）
    int sleep_us = getenv("BONDRUN_SLEEP_US") ? atoi(getenv("BONDRUN_SLEEP_US")) : 0;
    // BONDRUN_SLEEP_SEQ="间隔us:次数,间隔us:次数,..."：按段循环切换间隔（阶跃实验）；
    // BONDRUN_PHASES=文件：每次切换段时写一行 "mach_absolute_time 新间隔us"（与 kdebug 同一时基）
    int seq_us[64], seq_n[64], nseq = 0, seg = 0, left = 0;
    if (getenv("BONDRUN_SLEEP_SEQ")) {
      char *buf = strdup(getenv("BONDRUN_SLEEP_SEQ")), *tok, *save;
      for (tok = strtok_r(buf, ",", &save); tok && nseq < 64; tok = strtok_r(NULL, ",", &save))
        if (sscanf(tok, "%d:%d", &seq_us[nseq], &seq_n[nseq]) == 2) nseq++;
    }
    FILE *phf = getenv("BONDRUN_PHASES") ? fopen(getenv("BONDRUN_PHASES"), "w") : NULL;
    for (int i = 0; i < iters; i++) {
      if (nseq) {
        if (left == 0) {
          if (i) seg = (seg + 1) % nseq;
          left = seq_n[seg];
          sleep_us = seq_us[seg];
          if (phf) fprintf(phf, "%llu %d\n", (unsigned long long)mach_absolute_time(), sleep_us);
        }
        left--;
      }
      if (sleep_us) usleep(sleep_us);
      if (gap && !strcmp(gap, "flush")) {
        memset(gap_buf, i & 0xff, gap_bytes);
      } else if (gap) {
        uint64_t g0 = mach_absolute_time();
        volatile uint64_t x = 0;
        while ((mach_absolute_time() - g0) * tb.numer / tb.denom < gap_us * 1e3) x++;
      }
      @autoreleasepool {
        uint64_t t = mach_absolute_time();
        [model predictionFromFeatures:in error:&err];
        us[i] = (mach_absolute_time() - t) * tb.numer / tb.denom / 1e3;
      }
    }
    if (phf) fclose(phf);
    uint64_t t_end = mach_absolute_time();
    double wall_s = (mach_absolute_time() - t_all) * tb.numer / tb.denom / 1e9;
    CFDictionaryRef s1 = sub ? create_samples(sub, subbed, NULL) : NULL;

    if (getenv("BONDRUN_SERIES")) {  // 按调用顺序写出每次耗时（微秒），每行一个
      FILE *f = fopen(getenv("BONDRUN_SERIES"), "w");
      for (int i = 0; f && i < iters; i++) fprintf(f, "%.1f\n", us[i]);
      if (f) fclose(f);
    }
    qsort(us, iters, sizeof(double), cmp_double);
    double med = us[iters / 2];
    printf("%s\n  耗时 中位数 %.1f us  p10 %.1f  p90 %.1f", argv[1], med, us[iters / 10], us[iters * 9 / 10]);
    if (gflop > 0) printf("  吞吐 %.2f TFLOPS", gflop / med * 1e3);
    printf("\n  计时窗口 mach %llu %llu\n", (unsigned long long)t_all, (unsigned long long)t_end);  // 与 kdebug 同一时基
    if (s0 && s1) {
      engine_stats st;
      ior_delta(s0, s1, &st);
      for (int e = 0; e < 2; e++) {
        printf("  ANE%d: 中断 %6llu（%.2f 次/调用）", e, st.irq[e], (double)st.irq[e] / iters);
        for (int dir = 1; dir <= 2; dir++) {
          double avg = st.bw_n[e][dir] ? st.bw_sum[e][dir] / st.bw_n[e][dir] : 0;
          printf("  %s 活跃采样 %5llu 平均 %6.1f GB/s", dir == 1 ? "读" : "写", st.bw_n[e][dir], avg);
        }
        printf("\n");
      }
      printf("  总时长 %.2f s；ANE0 计算时钟开启 %.1f us/调用（占 %.0f%%）\n", wall_s,
             st.dpe_ticks / 24.0 / iters, 100.0 * st.dpe_ticks / 24e6 / wall_s);
    }
    return 0;
  }
}
