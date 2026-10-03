// 读出 ANECompiler 中某函数 +偏移 处 ADRP + ADD（下一条）计算出的地址，并按 C 字符串打印（只读）。
// 用法：./adrstr <符号名> <偏移（十六进制，指向 ADRP）>
#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>
#include <mach-o/nlist.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
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
  uint64_t f = 0;
  for (uint32_t i = 0; i < st->nsyms; i++) if (!strcmp(str + nl[i].n_un.n_strx, argv[1]) && nl[i].n_value) { f = nl[i].n_value + slide; break; }
  if (!f) { printf("找不到 %s\n", argv[1]); return 1; }
  uint64_t pc = f + strtoull(argv[2], 0, 16);
  uint32_t w = *(uint32_t *)pc, w2 = *(uint32_t *)(pc + 4);
  int64_t imm = ((int64_t)(((w >> 5) & 0x7ffff) << 2 | ((w >> 29) & 3)) << 43) >> 31;
  uint64_t t = (pc & ~0xfffULL) + imm + ((w2 >> 10) & 0xfff);
  printf("%#llx: \"%s\"\n", (unsigned long long)t, (char *)t);
  return 0;
}
