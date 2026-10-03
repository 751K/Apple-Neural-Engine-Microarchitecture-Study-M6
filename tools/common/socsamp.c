// 高频采样 SOC 调压域的档位（只读，不需要 root）：每 period 毫秒读一次 IOReport，输出该时间窗内各档的驻留，
// 时间戳为 mach_absolute_time（24 MHz，与 kdebug 事件同一时基）。
// 通道：[SoC Stats]/[Events]/SOC_VMIN、SOC_VNOM、SOC_VMAX、SOC_VOVD、SOC_VOVD2（ACT 驻留）；
//       [PMP]/[PMC SOC Floor]/[PMP]（汇总后的 SOC 下限，5 档）；[PMP]/[SOC Floor]/[ANE0-AF-BW]（ANE0 与互连之间的带宽投票，5 档）。
// 用法：./socsamp <总秒数> [period 毫秒 = 20] > 输出
// 每行：t_end（mach tick） 窗口长（tick） SOC实际[VMIN VNOM VMAX VOVD VOVD2] PMP下限[5] ANE0-AF-BW投票[5]（均为该窗口内的驻留 tick）
// 编译：clang -O2 socsamp.c -framework CoreFoundation -o socsamp
#include <CoreFoundation/CoreFoundation.h>
#include <dlfcn.h>
#include <mach/mach_time.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

typedef CFMutableDictionaryRef (*copy_all_fn)(uint64_t, uint64_t);
typedef void *(*create_sub_fn)(void *, CFMutableDictionaryRef, CFMutableDictionaryRef *, uint64_t, CFTypeRef);
typedef CFDictionaryRef (*create_samples_fn)(void *, CFMutableDictionaryRef, CFTypeRef);
typedef CFDictionaryRef (*delta_fn)(CFDictionaryRef, CFDictionaryRef, CFTypeRef);
typedef CFStringRef (*str_fn)(CFDictionaryRef);
typedef int32_t (*i32_fn)(CFDictionaryRef);
typedef CFStringRef (*sname_fn)(CFDictionaryRef, int32_t);
typedef int64_t (*sres_fn)(CFDictionaryRef, int32_t);

static void cs(CFStringRef s, char *b, size_t n) { b[0] = 0; if (s) CFStringGetCString(s, b, n, kCFStringEncodingUTF8); }
static const char *SOC[5] = {"SOC_VMIN", "SOC_VNOM", "SOC_VMAX", "SOC_VOVD", "SOC_VOVD2"};

int main(int argc, char **argv) {
  double total = argc > 1 ? atof(argv[1]) : 10;
  int period = argc > 2 ? atoi(argv[2]) : 20;
  void *l = dlopen("/usr/lib/libIOReport.dylib", RTLD_LAZY);
  copy_all_fn copy_all = dlsym(l, "IOReportCopyAllChannels");
  create_sub_fn sub_f = dlsym(l, "IOReportCreateSubscription");
  create_samples_fn samp = dlsym(l, "IOReportCreateSamples");
  delta_fn delta = dlsym(l, "IOReportCreateSamplesDelta");
  str_fn g = dlsym(l, "IOReportChannelGetGroup"), sg = dlsym(l, "IOReportChannelGetSubGroup"),
         nm = dlsym(l, "IOReportChannelGetChannelName");
  i32_fn sc = dlsym(l, "IOReportStateGetCount");
  sname_fn sn = dlsym(l, "IOReportStateGetNameForIndex");
  sres_fn res = dlsym(l, "IOReportStateGetResidency");
  CFMutableDictionaryRef all = copy_all(0, 0);
  CFArrayRef arr = CFDictionaryGetValue(all, CFSTR("IOReportChannels"));
  CFMutableArrayRef keep = CFArrayCreateMutable(NULL, 0, &kCFTypeArrayCallBacks);
  char a[256], b[256], c[256];
  for (CFIndex i = 0; i < CFArrayGetCount(arr); i++) {
    CFDictionaryRef ch = CFArrayGetValueAtIndex(arr, i);
    cs(g(ch), a, sizeof a); cs(sg(ch), b, sizeof b); cs(nm(ch), c, sizeof c);
    int want = 0;
    if (!strcmp(a, "SoC Stats") && !strcmp(b, "Events")) for (int k = 0; k < 5; k++) if (!strcmp(c, SOC[k])) want = 1;
    if (!strcmp(a, "PMP") && !strcmp(b, "PMC SOC Floor") && !strcmp(c, "PMP")) want = 1;
    if (!strcmp(a, "PMP") && !strcmp(b, "SOC Floor") && !strcmp(c, "ANE0-AF-BW")) want = 1;
    if (want) CFArrayAppendValue(keep, ch);
  }
  fprintf(stderr, "通道 %ld 个\n", CFArrayGetCount(keep));
  CFDictionarySetValue(all, CFSTR("IOReportChannels"), keep);
  CFMutableDictionaryRef subbed = NULL;
  void *sub = sub_f(NULL, all, &subbed, 0, NULL);
  if (!sub) { fprintf(stderr, "订阅失败\n"); return 1; }
  CFDictionaryRef prev = samp(sub, subbed, NULL);
  uint64_t tprev = mach_absolute_time(), t0 = tprev;
  while ((mach_absolute_time() - t0) / 24e6 < total) {
    usleep(period * 1000);
    CFDictionaryRef cur = samp(sub, subbed, NULL);
    uint64_t t = mach_absolute_time();
    CFDictionaryRef d = delta(prev, cur, NULL);
    long long soc[5] = {0}, fl[5] = {0}, bw[5] = {0};
    CFArrayRef da = CFDictionaryGetValue(d, CFSTR("IOReportChannels"));
    for (CFIndex i = 0; da && i < CFArrayGetCount(da); i++) {
      CFDictionaryRef ch = CFArrayGetValueAtIndex(da, i);
      cs(sg(ch), b, sizeof b); cs(nm(ch), c, sizeof c);
      int n = sc(ch);
      if (!strcmp(b, "Events")) {
        for (int k = 0; k < 5; k++) if (!strcmp(c, SOC[k]))
          for (int j = 0; j < n; j++) { char s[32]; cs(sn(ch, j), s, sizeof s); if (!strcmp(s, "ACT")) soc[k] = res(ch, j); }
      } else {
        long long *dst = !strcmp(b, "PMC SOC Floor") ? fl : bw;
        for (int j = 0; j < n && j < 5; j++) dst[j] = res(ch, j);
      }
    }
    printf("%llu %llu", (unsigned long long)t, (unsigned long long)(t - tprev));
    for (int k = 0; k < 5; k++) printf(" %lld", soc[k]);
    printf(" |");
    for (int k = 0; k < 5; k++) printf(" %lld", fl[k]);
    printf(" |");
    for (int k = 0; k < 5; k++) printf(" %lld", bw[k]);
    printf("\n");
    fflush(stdout);
    CFRelease(d); CFRelease(prev);
    prev = cur; tprev = t;
  }
  return 0;
}
