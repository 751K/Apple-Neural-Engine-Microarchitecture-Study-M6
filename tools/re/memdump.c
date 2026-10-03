// 在本进程加载 ANECompiler 后，按（含共享缓存滑动的）地址把一段代码/数据写到 stdout（只读）
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
int main(int c,char**v){ dlopen("/System/Library/PrivateFrameworks/ANECompiler.framework/ANECompiler",RTLD_NOW);
 unsigned long a=strtoul(v[1],0,16), n=strtoul(v[2],0,0); fwrite((void*)a,1,n,stdout); return 0;}
