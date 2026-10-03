// 在 ANECompiler 的 __TEXT,__text 中找装入 16 位立即数（左移 16）的 MOVZ/MOVK（32 位寄存器），并用符号表标出所在函数（只读）。
#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <mach-o/nlist.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { uint64_t a; const char *n; } S;
static int cmp(const void *x, const void *y) { uint64_t p = ((S *)x)->a, q = ((S *)y)->a; return p < q ? -1 : p > q; }
int main(int argc, char **argv) {
  void *h = dlopen("/System/Library/PrivateFrameworks/ANECompiler.framework/ANECompiler", RTLD_NOW);
  Dl_info di; dladdr(dlsym(h, "ANECCompile"), &di);
  const struct mach_header_64 *mh = di.dli_fbase; intptr_t sl = 0;
  for (uint32_t i = 0; i < _dyld_image_count(); i++) if (_dyld_get_image_header(i) == (void *)mh) sl = _dyld_get_image_vmaddr_slide(i);
  const struct load_command *lc = (void *)(mh + 1); const struct segment_command_64 *le = 0; const struct symtab_command *st = 0;
  uint64_t tx = 0, tn = 0;
  for (uint32_t i = 0; i < mh->ncmds; i++, lc = (void *)((char *)lc + lc->cmdsize)) {
    if (lc->cmd == LC_SEGMENT_64) { const struct segment_command_64 *g = (void *)lc; if (!strcmp(g->segname, "__LINKEDIT")) le = g;
      const struct section_64 *s = (void *)(g + 1); for (uint32_t j = 0; j < g->nsects; j++) if (!strcmp(s[j].sectname, "__text") && !strcmp(s[j].segname, "__TEXT")) { tx = s[j].addr + sl; tn = s[j].size; } }
    if (lc->cmd == LC_SYMTAB) st = (void *)lc; }
  char *b = (char *)(le->vmaddr + sl - le->fileoff); struct nlist_64 *nl = (void *)(b + st->symoff); char *str = b + st->stroff;
  S *sy = malloc(sizeof(S) * st->nsyms); int n = 0;
  for (uint32_t i = 0; i < st->nsyms; i++) if ((nl[i].n_type & N_TYPE) == N_SECT && nl[i].n_value) sy[n++] = (S){nl[i].n_value + sl, str + nl[i].n_un.n_strx};
  qsort(sy, n, sizeof(S), cmp);
  for (int a = 1; a < argc; a++) {
    uint32_t imm = strtoul(argv[a], 0, 16);
    const uint32_t *w = (const uint32_t *)tx;
    for (uint64_t k = 0; k < tn / 4; k++) {
      uint32_t x = w[k], hi = (x >> 21) & 3, op = x & 0xff800000;
      if ((op == 0x52800000 || op == 0x72800000) && hi == 1 && ((x >> 5) & 0xffff) == imm) {
        uint64_t pc = tx + 4 * k; int lo = 0, h2 = n - 1, best = -1;
        while (lo <= h2) { int m = (lo + h2) / 2; if (sy[m].a <= pc) { best = m; lo = m + 1; } else h2 = m - 1; }
        printf("%#06x %s  %s +%#llx\n", imm, op == 0x52800000 ? "MOVZ" : "MOVK", best >= 0 ? sy[best].n : "?", best >= 0 ? (unsigned long long)(pc - sy[best].a) : 0ULL);
      }
    }
  }
}
