#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <mach-o/loader.h>
#include <mach-o/nlist.h>
#include <mach-o/dyld.h>
static struct nlist_64*nl; static char*str; static uint32_t ns; static intptr_t slide;
static void* sym(const char*want){ for(uint32_t i=0;i<ns;i++) if(!strcmp(str+nl[i].n_un.n_strx,want)) return (void*)(nl[i].n_value+slide); return 0;}
int main(int argc,char**argv){
  void*h=dlopen("/System/Library/PrivateFrameworks/ANECompiler.framework/ANECompiler",RTLD_NOW);
  Dl_info di; dladdr(dlsym(h,"ANECCompile"),&di); const struct mach_header_64*mh=di.dli_fbase;
  for(uint32_t i=0;i<_dyld_image_count();i++) if(_dyld_get_image_header(i)==(void*)mh) slide=_dyld_get_image_vmaddr_slide(i);
  const struct load_command*lc=(void*)(mh+1); const struct segment_command_64*le=0; const struct symtab_command*st=0;
  for(uint32_t i=0;i<mh->ncmds;i++){ if(lc->cmd==LC_SEGMENT_64&&!strcmp(((struct segment_command_64*)lc)->segname,"__LINKEDIT")) le=(void*)lc; if(lc->cmd==LC_SYMTAB) st=(void*)lc; lc=(void*)((char*)lc+lc->cmdsize);}
  char*base=(char*)(le->vmaddr+slide-le->fileoff); nl=(void*)(base+st->symoff); str=base+st->stroff; ns=st->nsyms;
  for(int a=1;a<argc;a++){ char fn[256],ps[256]; const char*c=argv[a];
    snprintf(fn,256,"__ZNK%zuZinIrHal%s9GetParamsEv",strlen(c)+8,c); snprintf(ps,256,"__ZZNK%zuZinIrHal%s9GetParamsEvE1p",strlen(c)+8,c);
    void*f=sym(fn); void*p=sym(ps); if(!f){fprintf(stderr,"%s: no fn\n",c);continue;}
    void*dummy=calloc(1,4096); void*(*g)(void*)= (void*(*)(void*))f; void*r=g(dummy);
    fprintf(stderr,"%-14s ret=%p static=%p %s\n",c,r,p,r==p?"same":"DIFF");
    char out[256]; snprintf(out,256,"hal_%s.bin",c); FILE*o=fopen(out,"wb"); fwrite(r,1,0xa10,o); fclose(o);}
}
