// 列出 IOReport 里名字（组 / 子组 / 通道）含关键字的所有通道，并采样 1 秒给出非零值。
// 用法：./iorlist [关键字=ANE] [采样秒数=1] [组名：只取这个组，可选]
// 编译：clang -O2 iorlist.c -framework CoreFoundation -o iorlist
#include <CoreFoundation/CoreFoundation.h>
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

typedef CFMutableDictionaryRef (*copy_all_fn)(uint64_t, uint64_t);
typedef void *(*create_sub_fn)(void *, CFMutableDictionaryRef, CFMutableDictionaryRef *, uint64_t, CFTypeRef);
typedef CFDictionaryRef (*create_samples_fn)(void *, CFMutableDictionaryRef, CFTypeRef);
typedef CFDictionaryRef (*delta_fn)(CFDictionaryRef, CFDictionaryRef, CFTypeRef);
typedef CFStringRef (*str_fn)(CFDictionaryRef);
typedef int64_t (*int_fn)(CFDictionaryRef, int32_t);
typedef int32_t (*i32_fn)(CFDictionaryRef);
typedef CFStringRef (*sname_fn)(CFDictionaryRef, int32_t);
typedef int64_t (*sres_fn)(CFDictionaryRef, int32_t);

static void cs(CFStringRef s, char *b, size_t n) { b[0] = 0; if (s) CFStringGetCString(s, b, n, kCFStringEncodingUTF8); }

int main(int argc, char **argv) {
  const char *key = argc > 1 ? argv[1] : "ANE";
  double secs = argc > 2 ? atof(argv[2]) : 1;
  void *l = dlopen("/usr/lib/libIOReport.dylib", RTLD_LAZY);
  copy_all_fn copy_all = dlsym(l, "IOReportCopyAllChannels");
  create_sub_fn sub_f = dlsym(l, "IOReportCreateSubscription");
  create_samples_fn samp = dlsym(l, "IOReportCreateSamples");
  delta_fn delta = dlsym(l, "IOReportCreateSamplesDelta");
  str_fn g = dlsym(l, "IOReportChannelGetGroup"), sg = dlsym(l, "IOReportChannelGetSubGroup"),
         nm = dlsym(l, "IOReportChannelGetChannelName"), unit = dlsym(l, "IOReportChannelGetUnitLabel");
  int_fn iv = dlsym(l, "IOReportSimpleGetIntegerValue");
  i32_fn fmt = dlsym(l, "IOReportChannelGetFormat"), sc = dlsym(l, "IOReportStateGetCount");
  sname_fn sn = dlsym(l, "IOReportStateGetNameForIndex");
  sres_fn res = dlsym(l, "IOReportStateGetResidency");
  typedef CFMutableDictionaryRef (*copy_group_fn)(CFStringRef, CFStringRef, uint64_t, uint64_t, uint64_t);
  copy_group_fn copy_group = dlsym(l, "IOReportCopyChannelsInGroup");
  CFMutableDictionaryRef all = NULL;
  if (argc > 3) {
    CFStringRef gs = CFStringCreateWithCString(NULL, argv[3], kCFStringEncodingUTF8);
    all = copy_group(gs, NULL, 0, 0, 0);
  } else {
    all = copy_all(0, 0);
  }
  if (!all) { printf("没有这个组\n"); return 1; }
  CFArrayRef arr = CFDictionaryGetValue(all, CFSTR("IOReportChannels"));
  CFMutableArrayRef keep = CFArrayCreateMutable(NULL, 0, &kCFTypeArrayCallBacks);
  char a[256], b[256], c[256], u[64];
  for (CFIndex i = 0; i < CFArrayGetCount(arr); i++) {
    CFDictionaryRef ch = CFArrayGetValueAtIndex(arr, i);
    cs(g(ch), a, sizeof a); cs(sg(ch), b, sizeof b); cs(nm(ch), c, sizeof c);
    if (strcasestr(a, key) || strcasestr(b, key) || strcasestr(c, key)) CFArrayAppendValue(keep, ch);
  }
  printf("匹配 \"%s\" 的通道 %ld 个\n", key, CFArrayGetCount(keep));
  CFDictionarySetValue(all, CFSTR("IOReportChannels"), keep);
  CFMutableDictionaryRef subbed = NULL;
  void *sub = sub_f(NULL, all, &subbed, 0, NULL);
  if (!sub) { printf("订阅失败\n"); return 1; }
  CFDictionaryRef s0 = samp(sub, subbed, NULL);
  usleep((useconds_t)(secs * 1e6));
  CFDictionaryRef s1 = samp(sub, subbed, NULL);
  CFDictionaryRef d = delta(s0, s1, NULL);
  CFArrayRef da = CFDictionaryGetValue(d, CFSTR("IOReportChannels"));
  for (CFIndex i = 0; da && i < CFArrayGetCount(da); i++) {
    CFDictionaryRef ch = CFArrayGetValueAtIndex(da, i);
    cs(g(ch), a, sizeof a); cs(sg(ch), b, sizeof b); cs(nm(ch), c, sizeof c); cs(unit ? unit(ch) : NULL, u, sizeof u);
    int f = fmt(ch);
    printf("[%s] / [%s] / [%s] fmt=%d unit=%s", a, b, c, f, u);
    if (f == 2) {
      int n = sc(ch);
      printf(" states=%d:", n);
      for (int j = 0; j < n; j++) { char s[64]; cs(sn(ch, j), s, sizeof s); long long r = res(ch, j); printf(" %s=%lld", s, r); }
    } else if (f == 1) {
      printf(" value=%lld", (long long)iv(ch, 0));
    }
    printf("\n");
  }
  return 0;
}
