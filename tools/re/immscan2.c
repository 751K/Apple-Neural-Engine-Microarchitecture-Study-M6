// 在 ANECompiler 的 __TEXT 里找所有以"基址寄存器 + 立即数"读取指定偏移的 LDRB / LDRH / LDR(w) / LDR(x) 指令，
// 按符号表标出所在函数（只读）。用于给静态寄存器跟踪漏掉的 HAL 字段找读取者：结果里会混入别的结构体在同一偏移的读取，
// 要看函数名筛选。
// 用法：./immscan2 <偏移，十六进制> [宽度 1/2/4/8，默认 1]
// 编译：clang -O2 immscan2.c -o immscan2
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
  uint64_t x = ((const Sym *)a)->addr, y = ((const Sym *)b)->addr; return x < y ? -1 : x > y;
}

int main(int argc, char **argv) {
  if (argc < 2) { fprintf(stderr, "usage: %s <off> [width]\n", argv[0]); return 2; }
  uint32_t off = (uint32_t)strtoul(argv[1], 0, 16);
  int width = argc > 2 ? atoi(argv[2]) : 1;
  int sz = width == 1 ? 0 : width == 2 ? 1 : width == 4 ? 2 : 3;
  if (off % width) { fprintf(stderr, "offset not aligned to width\n"); return 2; }
  uint32_t imm = off / width;
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
  Sym *all = malloc(sizeof(Sym) * st->nsyms); size_t n = 0;
  for (uint32_t i = 0; i < st->nsyms; i++) {
    if ((nl[i].n_type & N_TYPE) != N_SECT) continue;
    uint64_t a = nl[i].n_value + slide;
    if (a < tlo || a >= thi) continue;
    all[n].addr = a; all[n].name = str + nl[i].n_un.n_strx; n++;
  }
  qsort(all, n, sizeof(Sym), cmp);
  // __text 节
  const struct section_64 *sec = (void *)(tx + 1);
  for (uint32_t k = 0; k < tx->nsects; k++, sec++) {
    if (strcmp(sec->sectname, "__text")) continue;
    const uint32_t *w = (const uint32_t *)(sec->addr + slide);
    size_t cnt = sec->size / 4;
    for (size_t q = 0; q < cnt; q++) {
      uint32_t x = w[q];
      // LDR (immediate, unsigned offset)：size[31:30] 111 0 01 opc[23:22]=01（加载） imm12 Rn Rt
      if ((x & 0x3fc00000) != 0x39400000 || (x >> 30) != (uint32_t)sz) continue;
      if (((x >> 10) & 0xfff) != imm) continue;
      uint64_t a = (uint64_t)&w[q];
      size_t lo = 0, hi = n;
      while (hi - lo > 1) { size_t m = (lo + hi) / 2; if (all[m].addr <= a) lo = m; else hi = m; }
      printf("%s+%llu\tx%u\n", all[lo].name, (unsigned long long)(a - all[lo].addr), (x >> 5) & 31);
    }
  }
  return 0;
}
