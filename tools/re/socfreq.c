// 读编译器内置的各代 SoC 频率参数：ZinIrSocVariantParams::<架构>() 返回静态对象，
// 对象第一个字段指向数据块，数据块里有若干 std::vector<double>（NE、L2、DMA、DRAM 频率等）。
// 只读：调用工厂函数（构造静态对象）后，用 vm_read 读内存，不调用编译器的其他功能。
// 用法：./socfreq H16g H17s H18 H19 ...
// 编译：clang -O2 socfreq.c -o socfreq
#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <mach-o/nlist.h>
#include <mach/mach.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int rd(uint64_t a, void *buf, size_t n) {
  vm_size_t got = 0;
  return vm_read_overwrite(mach_task_self(), a, n, (vm_address_t)buf, &got) == KERN_SUCCESS && got == n;
}

static struct nlist_64 *nl;
static char *str;
static uint32_t ns;
static intptr_t slide;

static void *sym(const char *want) {
  for (uint32_t i = 0; i < ns; i++)
    if (!strcmp(str + nl[i].n_un.n_strx, want)) return (void *)(nl[i].n_value + slide);
  return 0;
}

int main(int argc, char **argv) {
  void *h = dlopen("/System/Library/PrivateFrameworks/ANECompiler.framework/ANECompiler", RTLD_NOW);
  Dl_info di;
  dladdr(dlsym(h, "ANECCompile"), &di);
  const struct mach_header_64 *mh = di.dli_fbase;
  for (uint32_t i = 0; i < _dyld_image_count(); i++)
    if (_dyld_get_image_header(i) == (void *)mh) slide = _dyld_get_image_vmaddr_slide(i);
  const struct load_command *lc = (void *)(mh + 1);
  const struct segment_command_64 *le = 0;
  const struct symtab_command *st = 0;
  for (uint32_t i = 0; i < mh->ncmds; i++) {
    if (lc->cmd == LC_SEGMENT_64 && !strcmp(((struct segment_command_64 *)lc)->segname, "__LINKEDIT")) le = (void *)lc;
    if (lc->cmd == LC_SYMTAB) st = (void *)lc;
    lc = (void *)((char *)lc + lc->cmdsize);
  }
  char *base = (char *)(le->vmaddr + slide - le->fileoff);
  nl = (void *)(base + st->symoff);
  str = base + st->stroff;
  ns = st->nsyms;

  for (int a = 1; a < argc; a++) {
    char fn[128];
    snprintf(fn, sizeof fn, "__ZN21ZinIrSocVariantParams%zu%sEv", strlen(argv[a]), argv[a]);
    void *f = sym(fn);
    if (!f) { printf("%s: 没有工厂函数 %s\n", argv[a], fn); continue; }
    uint64_t obj = (uint64_t)((void *(*)(void))f)();
    uint64_t data = 0;
    rd(obj, &data, 8);
    printf("== %s  对象 %#llx  数据块 %#llx\n", argv[a], obj, data);
    // 反汇编确认：GetMCacheSize 读数据块 +0x0，GetDRAMChannels 读 +0x8，GetDRAMPoolLimit 读 +0x70
    uint64_t mc = 0, ch = 0, pool = 0;
    rd(data, &mc, 8);
    rd(data + 0x8, &ch, 8);
    rd(data + 0x70, &pool, 8);
    printf("  MCache %llu B（%.1f MiB）  DRAM 通道 %llu  DRAM 池上限 %llu B（%.1f MiB）\n", mc, mc / 1048576.0, ch, pool,
           pool / 1048576.0);
    // 扫描数据块前 0x200 字节里的 vector<double>（begin <= end <= cap，长度合理）
    for (int off = 0; off + 24 <= 0x200; off += 8) {
      uint64_t q[3];
      if (!rd(data + off, q, sizeof q)) break;
      uint64_t b = q[0], e = q[1], c = q[2];
      if (b > 0x100000000ULL && e >= b && c >= e && e - b <= 8 * 64 && (e - b) % 8 == 0 && e > b) {
        double v[64];
        if (!rd(b, v, e - b)) continue;
        int n = (int)((e - b) / 8);
        int ok = 1;
        for (int i = 0; i < n; i++) if (!(v[i] > -1e12 && v[i] < 1e12)) ok = 0;
        if (!ok) continue;
        printf("  +%#04x 共 %2d 项:", off, n);
        for (int i = 0; i < n; i++) printf(" %g", v[i]);
        printf("\n");
        off += 16;
      }
    }
  }
  return 0;
}
