// 导出 ANECompiler 中名字含指定子串的函数机器码，生成可汇编的 .s（每个函数一个标签，.byte 形式）
// 用法：./fnbytes 18ZinIrHalParameters > funcs.s
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdint.h>
#include <mach-o/loader.h>
#include <mach-o/nlist.h>
#include <mach-o/dyld.h>

typedef struct { uint64_t addr; const char *name; } Sym;
static int cmp(const void *a, const void *b) {
  uint64_t x = ((Sym *)a)->addr, y = ((Sym *)b)->addr; return x < y ? -1 : x > y;
}

int main(int argc, char **argv) {
  void *h = dlopen("/System/Library/PrivateFrameworks/ANECompiler.framework/ANECompiler", RTLD_NOW);
  Dl_info di; dladdr(dlsym(h, "ANECCompile"), &di);
  const struct mach_header_64 *mh = di.dli_fbase; intptr_t slide = 0;
  for (uint32_t i = 0; i < _dyld_image_count(); i++)
    if (_dyld_get_image_header(i) == (void *)mh) slide = _dyld_get_image_vmaddr_slide(i);
  const struct load_command *lc = (void *)(mh + 1);
  const struct segment_command_64 *le = 0, *tx = 0; const struct symtab_command *st = 0;
  for (uint32_t i = 0; i < mh->ncmds; i++, lc = (void *)((char *)lc + lc->cmdsize)) {
    if (lc->cmd == LC_SEGMENT_64) {
      const struct segment_command_64 *s = (void *)lc;
      if (!strcmp(s->segname, "__LINKEDIT")) le = s;
      if (!strcmp(s->segname, "__TEXT")) tx = s;
    }
    if (lc->cmd == LC_SYMTAB) st = (void *)lc;
  }
  char *base = (char *)(le->vmaddr + slide - le->fileoff);
  struct nlist_64 *nl = (void *)(base + st->symoff); char *str = base + st->stroff;
  uint64_t tlo = tx->vmaddr + slide, thi = tlo + tx->vmsize;

  // 收集 __TEXT 内全部符号（用于求函数长度）
  Sym *all = malloc(sizeof(Sym) * st->nsyms); size_t n = 0;
  for (uint32_t i = 0; i < st->nsyms; i++) {
    if ((nl[i].n_type & N_TYPE) != N_SECT) continue;
    uint64_t a = nl[i].n_value + slide;
    if (a < tlo || a >= thi) continue;
    all[n].addr = a; all[n].name = str + nl[i].n_un.n_strx; n++;
  }
  qsort(all, n, sizeof(Sym), cmp);

  int k = 0;
  for (size_t i = 0; i + 1 < n; i++) {
    if (!strstr(all[i].name, argv[1])) continue;
    if (!strncmp(all[i].name, "__ZZ", 4) || !strncmp(all[i].name, "__ZGV", 5)) continue;
    size_t j = i + 1; while (j < n && all[j].addr == all[i].addr) j++;
    if (j >= n) break;
    uint64_t sz = all[j].addr - all[i].addr;
    if (sz == 0 || sz > 65536 || (sz & 3)) continue;
    printf("; FUNC %d %s\n.p2align 2\nf%d:\n", k, all[i].name, k);
    const uint32_t *w = (const uint32_t *)all[i].addr;
    for (uint64_t q = 0; q < sz / 4; q++) printf(".long 0x%08x\n", w[q]);
    k++;
  }
  fprintf(stderr, "%d functions\n", k);
  return 0;
}
