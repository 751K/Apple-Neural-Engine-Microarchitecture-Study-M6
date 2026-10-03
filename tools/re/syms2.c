#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include <mach-o/loader.h>
#include <mach-o/nlist.h>
#include <mach-o/dyld.h>
int main(int argc,char**argv){
  void*h=dlopen("/System/Library/PrivateFrameworks/ANECompiler.framework/ANECompiler",RTLD_NOW); if(getenv("IMG")) h=dlopen(getenv("IMG"),RTLD_NOW);
  void*p=dlsym(h,getenv("SYM")?getenv("SYM"):"ANECCompile"); Dl_info di; dladdr(p,&di);
  const struct mach_header_64*mh=di.dli_fbase;
  intptr_t slide=0; for(uint32_t i=0;i<_dyld_image_count();i++) if(_dyld_get_image_header(i)==(void*)mh) slide=_dyld_get_image_vmaddr_slide(i);
  const struct load_command*lc=(void*)(mh+1); const struct segment_command_64*le=0; const struct symtab_command*st=0;
  for(uint32_t i=0;i<mh->ncmds;i++){ if(lc->cmd==LC_SEGMENT_64&&!strcmp(((struct segment_command_64*)lc)->segname,"__LINKEDIT")) le=(void*)lc; if(lc->cmd==LC_SYMTAB) st=(void*)lc; lc=(void*)((char*)lc+lc->cmdsize);}
  char*base=(char*)(le->vmaddr+slide-le->fileoff);
  struct nlist_64*nl=(void*)(base+st->symoff); char*str=base+st->stroff;
  fprintf(stderr,"nsyms %u slide %lx ANECCompile %p\n",st->nsyms,slide,p);
  for(uint32_t i=0;i<st->nsyms;i++){ const char*n=str+nl[i].n_un.n_strx; if(strstr(n,argv[1])) printf("%016llx %02x %s\n",nl[i].n_value+slide,nl[i].n_type,n);}
}
