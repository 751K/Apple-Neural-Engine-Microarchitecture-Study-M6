// 导出各代 ANE 编译器 HAL 表（ZinIrHal*::GetParams 的静态表）及其引用的 vector 内容
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdint.h>
#include <mach-o/loader.h>
#include <mach-o/nlist.h>
#include <mach-o/dyld.h>
#include <mach/mach.h>

// 安全读内存：不可读时返回 0
static int rd(uint64_t a, void *buf, size_t n) {
  vm_size_t got = 0;
  return vm_read_overwrite(mach_task_self(), a, n, (vm_address_t)buf, &got) == KERN_SUCCESS && got == n;
}

static struct nlist_64 *nl; static char *str; static uint32_t ns; static intptr_t slide;

static void *sym(const char *want) {
  for (uint32_t i = 0; i < ns; i++)
    if (!strcmp(str + nl[i].n_un.n_strx, want)) return (void *)(nl[i].n_value + slide);
  return 0;
}

int main(int argc, char **argv) {
  void *h = dlopen("/System/Library/PrivateFrameworks/ANECompiler.framework/ANECompiler", RTLD_NOW);
  Dl_info di; dladdr(dlsym(h, "ANECCompile"), &di);
  const struct mach_header_64 *mh = di.dli_fbase;
  for (uint32_t i = 0; i < _dyld_image_count(); i++)
    if (_dyld_get_image_header(i) == (void *)mh) slide = _dyld_get_image_vmaddr_slide(i);
  const struct load_command *lc = (void *)(mh + 1);
  const struct segment_command_64 *le = 0; const struct symtab_command *st = 0;
  for (uint32_t i = 0; i < mh->ncmds; i++) {
    if (lc->cmd == LC_SEGMENT_64 && !strcmp(((struct segment_command_64 *)lc)->segname, "__LINKEDIT")) le = (void *)lc;
    if (lc->cmd == LC_SYMTAB) st = (void *)lc;
    lc = (void *)((char *)lc + lc->cmdsize);
  }
  char *base = (char *)(le->vmaddr + slide - le->fileoff);
  nl = (void *)(base + st->symoff); str = base + st->stroff; ns = st->nsyms;

  for (int a = 1; a < argc; a++) {
    const char *c = argv[a]; char fn[256];
    snprintf(fn, 256, "__ZNK%zuZinIrHal%s9GetParamsEv", strlen(c) + 8, c);
    void *f = sym(fn);
    if (!f) { fprintf(stderr, "%s: no fn\n", c); continue; }
    void *dummy = calloc(1, 4096);
    char *r = ((void *(*)(void *))f)(dummy);
    char out[256]; snprintf(out, 256, "vec_%s.txt", c);
    FILE *o = fopen(out, "w");
    char nm[64] = {0}; rd(*(uint64_t *)r, nm, 63);
    fprintf(o, "name=%s\n", nm);
    fprintf(stderr, "%s ok\n", c);
    for (int off = 0x10; off + 24 <= 0xa10; off += 8) {
      uint64_t *q = (uint64_t *)(r + off);
      uint64_t b = q[0], e = q[1], cp = q[2];
      // libc++ vector：begin <= end <= cap，指向堆（与静态表不在同一 4 GB 段）
      if (b > 0x100000000ULL && e >= b && cp >= e && e - b <= 4096 &&
          (b >> 32) == (e >> 32) && (b >> 32) != ((uint64_t)r >> 32)) {
        uint32_t buf[1024];
        if (!rd(b, buf, e - b)) continue;
        fprintf(o, "vec 0x%x len %llu:", off, (unsigned long long)(e - b));
        for (uint64_t i = 0; i < (e - b) / 4; i++) fprintf(o, " %x", buf[i]);
        fprintf(o, "\n");
        off += 16;
      }
    }
    // 头指针指向的对象：导出 0x100 字节
    { uint64_t hp = *(uint64_t *)r; uint8_t hb[0x100];
      if (rd(hp, hb, sizeof hb)) { fprintf(o, "head %llx:", (unsigned long long)hp);
        for (int i = 0; i < 0x100; i += 4) fprintf(o, " %08x", *(uint32_t *)(hb + i)); fprintf(o, "\n"); }
      Dl_info hi; if (dladdr((void *)hp, &hi) && hi.dli_sname) fprintf(o, "head sym %s +%lld\n", hi.dli_sname, (long long)(hp - (uint64_t)hi.dli_saddr)); }
    fclose(o);
  }
  return 0;
}
