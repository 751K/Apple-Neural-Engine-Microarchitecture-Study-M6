// 读 SMC 里的功率键（不需要 root）。
//   ./smcpower list                列出所有以 P 开头、类型为 flt 的键及当前值（瓦）
//   ./smcpower sample S K1 K2 ...  每 100 ms 采一次给定的键，持续 S 秒，打印各键的平均值和最大值
// 编译：clang -O2 smcpower.c -framework IOKit -o smcpower
// SMC 消息结构和 anemon 的 smc.c 相同。
#include <IOKit/IOKitLib.h>
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

static uint32_t read_u32(uint32_t key) {
  smc_msg in = {0}, out;
  in.key = key;
  in.cmd = SMC_READ_INFO;
  if (call(&in, &out)) return 0;
  in.info.size = out.info.size;
  in.cmd = SMC_READ_BYTES;
  if (call(&in, &out)) return 0;
  return (uint32_t)out.bytes[0] << 24 | (uint32_t)out.bytes[1] << 16 | (uint32_t)out.bytes[2] << 8 | out.bytes[3];
}

int main(int argc, char **argv) {
  io_service_t svc = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("AppleSMC"));
  if (!svc || IOServiceOpen(svc, mach_task_self(), 0, &conn) != KERN_SUCCESS) { fprintf(stderr, "无法打开 AppleSMC\n"); return 1; }
  if (argc > 1 && !strcmp(argv[1], "list")) {
    uint32_t n = read_u32(k4("#KEY"));
    for (uint32_t i = 0; i < n; i++) {
      smc_msg in = {0}, out;
      in.cmd = SMC_READ_INDEX;
      in.data32 = i;
      if (call(&in, &out)) continue;
      uint32_t key = out.key;
      char name[5] = {(char)(key >> 24), (char)(key >> 16), (char)(key >> 8), (char)key, 0};
      float v;
      if (name[0] == 'P' && read_float(key, &v) == 0) printf("%s %.3f\n", name, v);
    }
    return 0;
  }
  if (argc > 3 && !strcmp(argv[1], "sample")) {
    double secs = atof(argv[2]);
    int nk = argc - 3, ns = 0;
    double *sum = calloc(nk, sizeof(double)), *mx = calloc(nk, sizeof(double));
    for (double t = 0; t < secs; t += 0.1, ns++) {
      for (int j = 0; j < nk; j++) {
        float v = 0;
        read_float(k4(argv[3 + j]), &v);
        sum[j] += v;
        if (v > mx[j]) mx[j] = v;
      }
      usleep(100000);
    }
    for (int j = 0; j < nk; j++) printf("%s 平均 %.3f W  最大 %.3f W\n", argv[3 + j], sum[j] / ns, mx[j]);
    return 0;
  }
  if (argc > 4 && !strcmp(argv[1], "trace")) {  // trace <秒> <间隔毫秒> <键>...：逐点输出 "相对时间(s) 值..."
    double secs = atof(argv[2]);
    int period = atoi(argv[3]), nk = argc - 4;
    struct timespec t0, t;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (;;) {
      clock_gettime(CLOCK_MONOTONIC, &t);
      double el = (t.tv_sec - t0.tv_sec) + (t.tv_nsec - t0.tv_nsec) / 1e9;
      if (el >= secs) break;
      printf("%.3f", el);
      for (int j = 0; j < nk; j++) {
        float v = 0;
        read_float(k4(argv[4 + j]), &v);
        printf(" %.3f", v);
      }
      printf("\n");
      fflush(stdout);
      usleep(period * 1000);
    }
    return 0;
  }
  fprintf(stderr, "usage: %s list | sample <秒> <键>... | trace <秒> <间隔毫秒> <键>...\n", argv[0]);
  return 2;
}
