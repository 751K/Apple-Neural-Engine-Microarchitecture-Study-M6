// 运行一个命令，报告运行期间两个 ANE 各自的中断次数和 DPE 时钟开启时间，用来确认命令真的用了哪个 ANE。
// 用法：./anewho <命令> [参数 ...]
// 编译：clang -O2 anewho.c -framework CoreFoundation -o anewho
#include <CoreFoundation/CoreFoundation.h>
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

typedef CFMutableDictionaryRef (*copy_group_fn)(CFStringRef, CFStringRef, uint64_t, uint64_t, uint64_t);
typedef void (*merge_fn)(CFMutableDictionaryRef, CFMutableDictionaryRef, CFTypeRef);
typedef void *(*create_sub_fn)(void *, CFMutableDictionaryRef, CFMutableDictionaryRef *, uint64_t, CFTypeRef);
typedef CFDictionaryRef (*create_samples_fn)(void *, CFMutableDictionaryRef, CFTypeRef);
typedef CFDictionaryRef (*delta_fn)(CFDictionaryRef, CFDictionaryRef, CFTypeRef);
typedef CFStringRef (*str_fn)(CFDictionaryRef);
typedef int64_t (*int_fn)(CFDictionaryRef, int32_t);

static void cs(CFStringRef s, char *b, size_t n) { b[0] = 0; if (s) CFStringGetCString(s, b, n, kCFStringEncodingUTF8); }

int main(int argc, char **argv) {
  if (argc < 2) { fprintf(stderr, "usage: %s cmd [args...]\n", argv[0]); return 2; }
  void *l = dlopen("/usr/lib/libIOReport.dylib", RTLD_LAZY);
  copy_group_fn cg = dlsym(l, "IOReportCopyChannelsInGroup");
  merge_fn merge = dlsym(l, "IOReportMergeChannels");
  create_sub_fn csub = dlsym(l, "IOReportCreateSubscription");
  create_samples_fn samp = dlsym(l, "IOReportCreateSamples");
  delta_fn delta = dlsym(l, "IOReportCreateSamplesDelta");
  str_fn g = dlsym(l, "IOReportChannelGetGroup"), sg = dlsym(l, "IOReportChannelGetSubGroup"),
         nm = dlsym(l, "IOReportChannelGetChannelName");
  int_fn iv = dlsym(l, "IOReportSimpleGetIntegerValue");
  CFMutableDictionaryRef ch = cg(CFSTR("Interrupt Statistics (by index)"), NULL, 0, 0, 0);
  merge(ch, cg(CFSTR("SoC Stats"), CFSTR("PMGR Counters"), 0, 0, 0), NULL);
  CFMutableDictionaryRef subbed = NULL;
  void *sub = csub(NULL, ch, &subbed, 0, NULL);
  CFDictionaryRef s0 = samp(sub, subbed, NULL);
  pid_t pid = fork();
  if (pid == 0) { execvp(argv[1], argv + 1); perror("exec"); _exit(127); }
  int st = 0;
  waitpid(pid, &st, 0);
  CFDictionaryRef s1 = samp(sub, subbed, NULL);
  CFDictionaryRef d = delta(s0, s1, NULL);
  CFArrayRef a = CFDictionaryGetValue(d, CFSTR("IOReportChannels"));
  long long irq[2] = {0, 0}, dpe = 0;
  char gr[128], sgr[128], n[128];
  for (CFIndex i = 0; a && i < CFArrayGetCount(a); i++) {
    CFDictionaryRef c = CFArrayGetValueAtIndex(a, i);
    cs(g(c), gr, sizeof gr); cs(sg(c), sgr, sizeof sgr); cs(nm(c), n, sizeof n);
    if (!strncmp(gr, "Interrupt Statistics", 20) && !strncasecmp(sgr, "ane", 3) && strstr(n, "First Level Interrupt Handler Count")) {
      const char *p = sgr + 3;
      int e = (*p >= '0' && *p <= '9') ? atoi(p) : 0;
      if (e < 2 && iv(c, 0) > 0) irq[e] += iv(c, 0);
    } else if (!strcmp(n, "ANE0_DPE_CLK_ON")) {
      dpe = iv(c, 0);
    }
  }
  fprintf(stderr, "[anewho] ANE0 中断 %lld，ANE1 中断 %lld，ANE0 DPE 时钟开启 %.1f ms\n", irq[0], irq[1], dpe / 24e3);
  return WIFEXITED(st) ? WEXITSTATUS(st) : 1;
}
