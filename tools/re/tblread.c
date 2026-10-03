// 读出 ANECompiler 中某函数开头 ADRP + ADD 指向的 32 位整数表（如 ArchCompareValue 的查表）（只读）
// 函数开头形如：sub w16,w0,#1; cmp w16,#N; ...; adrp x17; add x17; ldrsw x16,[x17,x16,lsl#2]; adr x17,#0; add x16,x17,x16; br x16
// 用法：./tblread <符号名> <个数> [第几个同名符号，默认 0]
// 编译：clang -O2 tblread.c -o tblread
#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <mach-o/nlist.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { uint64_t addr; const char *name; } Sym;
static int cmp(const void *a, const void *b) { uint64_t x = ((Sym *)a)->addr, y = ((Sym *)b)->addr; return x < y ? -1 : x > y; }
static Sym *syms; static int n;
static const char *at(uint64_t t) {
  int lo = 0, hi = n - 1, best = -1;
  while (lo <= hi) { int mid = (lo + hi) / 2; if (syms[mid].addr <= t) { best = mid; lo = mid + 1; } else hi = mid - 1; }
  return best >= 0 && syms[best].addr == t ? syms[best].name : "?";
}
int main(int argc, char **argv) {
  void *h = dlopen("/System/Library/PrivateFrameworks/ANECompiler.framework/ANECompiler", RTLD_NOW);
  Dl_info di; dladdr(dlsym(h, "ANECCompile"), &di);
  const struct mach_header_64 *mh = di.dli_fbase; intptr_t slide = 0;
  for (uint32_t i = 0; i < _dyld_image_count(); i++) if (_dyld_get_image_header(i) == (void *)mh) slide = _dyld_get_image_vmaddr_slide(i);
  const struct load_command *lc = (void *)(mh + 1); const struct segment_command_64 *le = 0; const struct symtab_command *st = 0;
  for (uint32_t i = 0; i < mh->ncmds; i++) {
    if (lc->cmd == LC_SEGMENT_64 && !strcmp(((struct segment_command_64 *)lc)->segname, "__LINKEDIT")) le = (void *)lc;
    if (lc->cmd == LC_SYMTAB) st = (void *)lc;
    lc = (void *)((char *)lc + lc->cmdsize);
  }
  char *base = (char *)(le->vmaddr + slide - le->fileoff);
  struct nlist_64 *nl = (void *)(base + st->symoff); char *str = base + st->stroff;
  syms = malloc(sizeof(Sym) * st->nsyms);
  for (uint32_t i = 0; i < st->nsyms; i++) if ((nl[i].n_type & N_TYPE) == N_SECT && nl[i].n_value) syms[n++] = (Sym){nl[i].n_value + slide, str + nl[i].n_un.n_strx};
  qsort(syms, n, sizeof(Sym), cmp);
  uint64_t f = 0; int want = argc > 3 ? atoi(argv[3]) : 0, seen = 0;
  for (int i = 0; i < n; i++) if (!strcmp(syms[i].name, argv[1]) && seen++ == want) { f = syms[i].addr; break; }
  if (!f) { printf("找不到\n"); return 1; }
  const uint32_t *ins = (const uint32_t *)f; uint64_t page = 0, tab = 0;
  for (int k = 0; k < 16 && !tab; k++) {
    uint32_t w = ins[k]; uint64_t pc = f + 4 * k;
    if ((w & 0x9f000000) == 0x90000000) page = (pc & ~0xfffULL) + (((int64_t)(((w >> 5) & 0x7ffff) << 2 | ((w >> 29) & 3)) << 43) >> 31);
    else if ((w & 0xffc00000) == 0x91000000 && page) tab = page + ((w >> 10) & 0xfff);
  }
  int cnt = atoi(argv[2]);
  for (int c = 0; c < cnt; c++) printf("%d %d\n", c, ((const int32_t *)tab)[c]);
}
