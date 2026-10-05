// 注入到自己的进程（DYLD_INSERT_LIBRARIES），拦截 _os_log_impl，把格式串含 OSLOGTAP_MATCH（默认 "[CostModelFeature]"）的日志
// 在打码（<private>）之前按格式串展开，写到 stderr。只支持 %s、%d/%u/%ld/%lu/%lld/%llu、%f、%p，够展开 Espresso 的代价日志。
// 编译：clang -dynamiclib -O2 oslogtap.c -o oslogtap.dylib
// 用法：DYLD_INSERT_LIBRARIES=./oslogtap.dylib ./aotdrv ...（需先 defaults write -g espresso.e5compiler.log_cost_model -bool YES）
#include <os/log.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern void _os_log_impl(void *dso, os_log_t log, os_log_type_t type, const char *format, uint8_t *buf, uint32_t size);

static void tap(void *dso, os_log_t log, os_log_type_t type, const char *format, uint8_t *buf, uint32_t size) {
  static const char *match;
  if (!match) { match = getenv("OSLOGTAP_MATCH"); if (!match) match = "[CostModelFeature]"; }
  if (format && strstr(format, match) && buf && size >= 2) {
    // 缓冲区：[摘要字节][参数个数]，之后每个参数 [描述字节][长度][数据]
    int n = buf[1]; uint32_t off = 2;
    uint8_t *arg[64]; uint8_t len[64]; int k = 0;
    for (int i = 0; i < n && i < 64 && off + 2 <= size; i++) {
      len[k] = buf[off + 1]; arg[k] = buf + off + 2; off += 2 + buf[off + 1]; k++;
    }
    char out[16384]; size_t o = 0; int ai = 0;
    for (const char *p = format; *p && o < sizeof(out) - 4096; p++) {
      if (*p != '%') { out[o++] = *p; continue; }
      const char *q = p + 1;
      while (*q && strchr("{}publicprivate.-0123456789lhzj", *q)) q++;   // 跳过 {public}、宽度、长度修饰
      if (*q == '%') { out[o++] = '%'; p = q; continue; }
      if (ai >= k) break;
      uint64_t v = 0; memcpy(&v, arg[ai], len[ai] < 8 ? len[ai] : 8);
      switch (*q) {
        case 's': o += snprintf(out + o, 4096, "%s", v ? (const char *)v : "(null)"); break;
        case 'f': { double d; memcpy(&d, &v, 8); o += snprintf(out + o, 256, "%f", d); break; }
        case 'p': o += snprintf(out + o, 256, "%p", (void *)v); break;
        case 'u': o += snprintf(out + o, 256, "%llu", (unsigned long long)v); break;
        default: o += snprintf(out + o, 256, "%lld", len[ai] == 4 ? (long long)(int32_t)v : (long long)v); break;
      }
      ai++; p = q;
    }
    out[o] = 0;
    fprintf(stderr, "OSLOGTAP\t%s\n", out);
  }
  _os_log_impl(dso, log, type, format, buf, size);
}

__attribute__((used, section("__DATA,__interpose"))) static struct { void *repl, *orig; } interp[] = {
  {(void *)tap, (void *)_os_log_impl},
};
