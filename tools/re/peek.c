// 读本进程内任意地址（先加载 ANECompiler，偏移按 ASLR slide 修正后的绝对地址）
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <mach/mach.h>
int main(int argc, char **argv) {
  dlopen("/System/Library/PrivateFrameworks/ANECompiler.framework/ANECompiler", RTLD_NOW);
  size_t n = strtoul(argv[1], 0, 0);
  for (int a = 2; a < argc; a++) {
    uint64_t p = strtoull(argv[a], 0, 16); uint32_t buf[1024]; vm_size_t got = 0;
    if (vm_read_overwrite(mach_task_self(), p, n, (vm_address_t)buf, &got) != KERN_SUCCESS) { printf("%llx unreadable\n", p); continue; }
    Dl_info di; printf("%llx", p);
    if (dladdr((void *)p, &di) && di.dli_sname) printf(" [%s+%lld]", di.dli_sname, (long long)(p - (uint64_t)di.dli_saddr));
    printf(":"); for (size_t i = 0; i < n / 4; i++) printf(" %08x", buf[i]); printf("\n");
  }
}
