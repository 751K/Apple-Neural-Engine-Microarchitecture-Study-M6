// 同时采 P 核簇功耗（IOReport PMP / Energy 的 "PACC<n>"、"PACC<n> SRAM" 瓦数直方图，按驻留加权平均后求和；方法同 anemon）
// 和 SMC 电源轨（PP0b 等）。M6 上 PP0b 同时供 P 核和 ANE（1 个 P 核空转即 +7.5 W），ANE 净功耗 ≈ PP0b − P 核簇 − 空闲差值。
// 用法：./pclus <秒> <间隔毫秒> [SMC 键...]   每行：相对时间(s) P核簇W 各键W
// 编译：clang -O2 pclus.c -framework IOKit -framework CoreFoundation -o pclus
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/IOKitLib.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

typedef struct { char major, minor, build, reserved; uint16_t release; } smc_vers;
typedef struct { uint16_t version, length; uint32_t cpu, gpu, mem; } smc_plimit;
typedef struct { uint32_t size, type; uint8_t attr; } smc_info;
typedef struct {
  uint32_t key;
  smc_vers vers;
  smc_plimit plimit;
  smc_info info;
  uint8_t result, status, cmd;
  uint32_t data32;
  uint8_t bytes[32];
} smc_msg;

enum { SMC_READ_BYTES = 5, SMC_READ_INDEX = 8, SMC_READ_INFO = 9, SMC_SELECTOR = 2 };
static io_connect_t conn;

static int call(smc_msg *in, smc_msg *out) {
  size_t sz = sizeof *out;
  memset(out, 0, sizeof *out);
  return IOConnectCallStructMethod(conn, SMC_SELECTOR, in, sizeof *in, out, &sz) == KERN_SUCCESS && out->result == 0 ? 0 : -1;
}
static uint32_t k4(const char *k) { return (uint32_t)k[0] << 24 | (uint32_t)k[1] << 16 | (uint32_t)k[2] << 8 | (uint32_t)k[3]; }

static int read_float(uint32_t key, float *v) {
  smc_msg in = {0}, out;
  in.key = key;
  in.cmd = SMC_READ_INFO;
  if (call(&in, &out) || out.info.size != 4 || out.info.type != k4("flt ")) return -1;
  in.info.size = 4;
  in.cmd = SMC_READ_BYTES;
  if (call(&in, &out)) return -1;
  memcpy(v, out.bytes, 4);
  return 0;
}


typedef CFMutableDictionaryRef (*copy_group_fn)(CFStringRef, CFStringRef, uint64_t, uint64_t, uint64_t);
typedef void *(*create_sub_fn)(void *, CFMutableDictionaryRef, CFMutableDictionaryRef *, uint64_t, CFTypeRef);
typedef CFDictionaryRef (*create_samples_fn)(void *, CFMutableDictionaryRef, CFTypeRef);
typedef CFDictionaryRef (*delta_fn)(CFDictionaryRef, CFDictionaryRef, CFTypeRef);
typedef CFStringRef (*str_fn)(CFDictionaryRef);
typedef int32_t (*i32_fn)(CFDictionaryRef);
typedef CFStringRef (*sname_fn)(CFDictionaryRef, int32_t);
typedef int64_t (*sres_fn)(CFDictionaryRef, int32_t);

static int is_pcluster(const char *s) {
  if (strncmp(s, "PACC", 4)) return 0;
  s += 4;
  if (*s < '0' || *s > '9') return 0;
  while (*s >= '0' && *s <= '9') s++;
  return *s == 0 || !strcmp(s, " SRAM");
}
static void cs(CFStringRef s, char *b, size_t n) { b[0] = 0; if (s) CFStringGetCString(s, b, n, kCFStringEncodingUTF8); }

int main(int argc, char **argv) {
  if (argc < 3) { fprintf(stderr, "usage: %s <秒> <间隔毫秒> [SMC 键...]\n", argv[0]); return 2; }
  double secs = atof(argv[1]);
  int period = atoi(argv[2]), nk = argc - 3;
  io_service_t svc = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("AppleSMC"));
  if (nk && (!svc || IOServiceOpen(svc, mach_task_self(), 0, &conn) != KERN_SUCCESS)) { fprintf(stderr, "无法打开 AppleSMC\n"); return 1; }
  void *l = dlopen("/usr/lib/libIOReport.dylib", RTLD_LAZY);
  copy_group_fn cg = dlsym(l, "IOReportCopyChannelsInGroup");
  create_sub_fn sub_f = dlsym(l, "IOReportCreateSubscription");
  create_samples_fn samp = dlsym(l, "IOReportCreateSamples");
  delta_fn delta = dlsym(l, "IOReportCreateSamplesDelta");
  str_fn sg = dlsym(l, "IOReportChannelGetSubGroup"), nm = dlsym(l, "IOReportChannelGetChannelName");
  i32_fn sc = dlsym(l, "IOReportStateGetCount");
  sname_fn sn = dlsym(l, "IOReportStateGetNameForIndex");
  sres_fn res = dlsym(l, "IOReportStateGetResidency");
  CFMutableDictionaryRef ch = cg(CFSTR("PMP"), CFSTR("Energy"), 0, 0, 0);
  CFMutableDictionaryRef subbed = NULL;
  void *sub = sub_f(NULL, ch, &subbed, 0, NULL);
  if (!sub) { fprintf(stderr, "订阅失败\n"); return 1; }
  CFDictionaryRef prev = samp(sub, subbed, NULL);
  struct timespec t0, t;
  clock_gettime(CLOCK_MONOTONIC, &t0);
  char b[256], c[256], s[64];
  for (;;) {
    usleep(period * 1000);
    clock_gettime(CLOCK_MONOTONIC, &t);
    double el = (t.tv_sec - t0.tv_sec) + (t.tv_nsec - t0.tv_nsec) / 1e9;
    if (el >= secs) break;
    CFDictionaryRef cur = samp(sub, subbed, NULL), d = delta(prev, cur, NULL);
    double pw = 0;
    CFArrayRef da = CFDictionaryGetValue(d, CFSTR("IOReportChannels"));
    for (CFIndex i = 0; da && i < CFArrayGetCount(da); i++) {
      CFDictionaryRef x = CFArrayGetValueAtIndex(da, i);
      cs(sg(x), b, sizeof b); cs(nm(x), c, sizeof c);
      if (strcmp(b, "Energy") || !is_pcluster(c)) continue;
      double sum = 0, cnt = 0;
      for (int j = 0; j < sc(x); j++) {
        int64_t r = res(x, j);
        if (r <= 0) continue;
        cs(sn(x, j), s, sizeof s);
        sum += atof(s) * (double)r;  // 状态名以瓦数开头，如 "3W"
        cnt += (double)r;
      }
      if (cnt > 0) pw += sum / cnt;
    }
    printf("%.3f %.3f", el, pw);
    for (int k = 0; k < nk; k++) { float v = 0; read_float(k4(argv[3 + k]), &v); printf(" %.3f", v); }
    printf("\n");
    fflush(stdout);
    CFRelease(d); CFRelease(prev);
    prev = cur;
  }
  return 0;
}
