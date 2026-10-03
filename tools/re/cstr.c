// 在已加载镜像的 __TEXT,__cstring 中搜索子串（不区分大小写）
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <stdlib.h>
#include <mach-o/loader.h>
#include <mach-o/dyld.h>
int main(int argc, char **argv) {
  void *h = dlopen(argv[1], RTLD_NOW);
  Dl_info di; dladdr(dlsym(h, argv[2]), &di);
  const struct mach_header_64 *mh = di.dli_fbase; intptr_t slide = 0;
  for (uint32_t i = 0; i < _dyld_image_count(); i++)
    if (_dyld_get_image_header(i) == (void *)mh) slide = _dyld_get_image_vmaddr_slide(i);
  const struct load_command *lc = (void *)(mh + 1);
  for (uint32_t i = 0; i < mh->ncmds; i++, lc = (void *)((char *)lc + lc->cmdsize)) {
    if (lc->cmd != LC_SEGMENT_64) continue;
    const struct segment_command_64 *sg = (void *)lc; const struct section_64 *s = (void *)(sg + 1);
    for (uint32_t j = 0; j < sg->nsects; j++) {
      if (strcmp(s[j].sectname, "__cstring")) continue;
      const char *p = (char *)(s[j].addr + slide), *e = p + s[j].size;
      while (p < e) { size_t n = strlen(p);
        for (int a = 3; a < argc; a++) if (strcasestr(p, argv[a])) { printf("%s\n", p); break; }
        p += n + 1; }
    }
  }
}
