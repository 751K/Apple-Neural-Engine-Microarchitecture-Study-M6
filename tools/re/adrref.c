// 在 ANECompiler 的 __TEXT,__text 里找用 ADRP + ADD / LDR 计算出某个符号地址（含其后 0x40 字节内）的指令，
// 用于找内联了构造函数的代码对 vtable 的引用（只读）。
// 用法：./adrref <符号名> [<符号名> ...]
// 编译：clang -O2 adrref.c -o adrref
#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <mach-o/nlist.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { uint64_t addr; const char *name; } Sym;
static int cmp(const void *a, const void *b) {
  uint64_t x = ((Sym *)a)->addr, y = ((Sym *)b)->addr;
  return x < y ? -1 : x > y;
}

int main(int argc, char **argv) {
  void *h = dlopen("/System/Library/PrivateFrameworks/ANECompiler.framework/ANECompiler", RTLD_NOW);
  Dl_info di;
  dladdr(dlsym(h, "ANECCompile"), &di);
  const struct mach_header_64 *mh = di.dli_fbase;
  intptr_t slide = 0;
  for (uint32_t i = 0; i < _dyld_image_count(); i++)
    if (_dyld_get_image_header(i) == (void *)mh) slide = _dyld_get_image_vmaddr_slide(i);
  const struct load_command *lc = (void *)(mh + 1);
  const struct segment_command_64 *le = 0;
  const struct symtab_command *st = 0;
  uint64_t text = 0, text_size = 0;
  for (uint32_t i = 0; i < mh->ncmds; i++) {
    if (lc->cmd == LC_SEGMENT_64) {
      const struct segment_command_64 *sg = (void *)lc;
      if (!strcmp(sg->segname, "__LINKEDIT")) le = sg;
      const struct section_64 *s = (void *)(sg + 1);
      for (uint32_t j = 0; j < sg->nsects; j++)
        if (!strcmp(s[j].segname, "__TEXT") && !strcmp(s[j].sectname, "__text")) { text = s[j].addr + slide; text_size = s[j].size; }
    }
    if (lc->cmd == LC_SYMTAB) st = (void *)lc;
    lc = (void *)((char *)lc + lc->cmdsize);
  }
  char *base = (char *)(le->vmaddr + slide - le->fileoff);
  struct nlist_64 *nl = (void *)(base + st->symoff);
  char *str = base + st->stroff;
  Sym *syms = malloc(sizeof(Sym) * st->nsyms);
  int n = 0;
  for (uint32_t i = 0; i < st->nsyms; i++)
    if ((nl[i].n_type & N_TYPE) == N_SECT && nl[i].n_value) syms[n++] = (Sym){nl[i].n_value + slide, str + nl[i].n_un.n_strx};
  qsort(syms, n, sizeof(Sym), cmp);
  for (int a = 1; a < argc; a++) {
    uint64_t target = 0;
    for (int i = 0; i < n; i++) if (!strcmp(syms[i].name, argv[a])) { target = syms[i].addr; break; }
    if (!target) { printf("%s：找不到\n", argv[a]); continue; }
    printf("== %s\n", argv[a]);
    const uint32_t *ins = (const uint32_t *)text;
    uint64_t page[32] = {0};
    for (uint64_t k = 0; k < text_size / 4; k++) {
      uint32_t w = ins[k];
      uint64_t pc = text + k * 4;
      if ((w & 0x9f000000) == 0x90000000) {  // ADRP
        int rd = w & 31;
        int64_t imm = ((int64_t)(((w >> 5) & 0x7ffff) << 2 | ((w >> 29) & 3)) << 43) >> 31;
        page[rd] = (pc & ~0xfffULL) + imm;
        continue;
      }
      uint64_t t = 0; int rn = (w >> 5) & 31;
      if ((w & 0xffc00000) == 0x91000000) t = page[rn] + ((w >> 10) & 0xfff);             // ADD x, x, #imm
      else if ((w & 0xffc00000) == 0xf9400000) t = page[rn] + ((w >> 10) & 0xfff) * 8;   // LDR x, [x, #imm]
      else continue;
      if (!page[rn] || t < target || t >= target + 0x40) continue;
      int lo = 0, hi = n - 1, best = -1;
      while (lo <= hi) { int mid = (lo + hi) / 2; if (syms[mid].addr <= pc) { best = mid; lo = mid + 1; } else hi = mid - 1; }
      printf("  +%#llx 于 %s +%#llx\n", (unsigned long long)(t - target), best >= 0 ? syms[best].name : "?",
             best >= 0 ? (unsigned long long)(pc - syms[best].addr) : 0ULL);
    }
  }
  return 0;
}
