// 在 ANECompiler 的 __TEXT,__text 里找调用某些函数的 BL / B 指令，并用符号表标出调用者（只读）。
// 用法：./xref <符号名> [<符号名> ...]        找调用这些函数的地方
//       ./xref -callees <符号名> [...]        列出这些函数内部（前 400 条指令）BL / B 的目标
// 编译：clang -O2 xref.c -o xref
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
        if (!strcmp(s[j].segname, "__TEXT") && !strcmp(s[j].sectname, "__text")) {
          text = s[j].addr + slide;
          text_size = s[j].size;
        }
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

  if (argc > 2 && !strcmp(argv[1], "-callees")) {
    for (int a = 2; a < argc; a++) {
      uint64_t f = 0;
      for (int i = 0; i < n; i++)
        if (!strcmp(syms[i].name, argv[a])) { f = syms[i].addr; break; }
      if (!f) { printf("%s：找不到\n", argv[a]); continue; }
      printf("== %s 调用：\n", argv[a]);
      const uint32_t *ins = (const uint32_t *)f;
      for (int k = 0; k < (getenv("XN") ? atoi(getenv("XN")) : 1200); k++) {
        uint32_t w = ins[k];
        uint32_t op = w & 0xfc000000;
        if (k > 0 && (w == 0xd65f03c0 || w == 0xd65f0fff || w == 0xd65f0bff)) break;  // ret / retab / retaa
        if (op != 0x94000000 && op != 0x14000000) continue;
        int32_t imm = (int32_t)(w << 6) >> 6;
        uint64_t t = f + k * 4 + (int64_t)imm * 4;
        int lo = 0, hi = n - 1, best = -1;
        while (lo <= hi) {
          int mid = (lo + hi) / 2;
          if (syms[mid].addr <= t) { best = mid; lo = mid + 1; } else hi = mid - 1;
        }
        printf("  +%#05x %s %s%s\n", k * 4, op == 0x94000000 ? "BL" : "B ", best >= 0 ? syms[best].name : "?",
               best >= 0 && syms[best].addr != t ? " (+偏移)" : "");
      }
    }
    return 0;
  }
  for (int a = 1; a < argc; a++) {
    uint64_t target = 0;
    for (int i = 0; i < n; i++)
      if (!strcmp(syms[i].name, argv[a])) { target = syms[i].addr; break; }
    if (!target) { printf("%s：找不到\n", argv[a]); continue; }
    printf("== %s @ +%#llx\n", argv[a], (unsigned long long)(target - (uint64_t)mh));
    const uint32_t *ins = (const uint32_t *)text;
    for (uint64_t k = 0; k < text_size / 4; k++) {
      uint32_t w = ins[k];
      uint32_t op = w & 0xfc000000;
      if (op != 0x94000000 && op != 0x14000000) continue;  // BL / B
      int32_t imm = (int32_t)(w << 6) >> 6;
      uint64_t pc = text + k * 4;
      if (pc + (int64_t)imm * 4 != target) continue;
      // 找所在函数：地址 <= pc 的最后一个符号
      int lo = 0, hi = n - 1, best = -1;
      while (lo <= hi) {
        int mid = (lo + hi) / 2;
        if (syms[mid].addr <= pc) { best = mid; lo = mid + 1; } else hi = mid - 1;
      }
      printf("  %s 于 %s +%#llx\n", op == 0x94000000 ? "BL" : "B ", best >= 0 ? syms[best].name : "?",
             best >= 0 ? (unsigned long long)(pc - syms[best].addr) : 0ULL);
    }
  }
  return 0;
}
