// 调用 Espresso 内置的 AOT 编译驱动：aotdrv <参数...>（等价于该驱动的命令行；argv[0] 作为程序名传入）
#include <dlfcn.h>
#include <iostream>
#include <cstdlib>
typedef void (*Ctor)(void *);
typedef int (*Run)(const void *, int, char **, std::ostream &);
typedef std::vector<std::string> (*Names)(const void *);
int main(int argc, char **argv) {
  void *h = dlopen("/System/Library/PrivateFrameworks/Espresso.framework/Espresso", RTLD_NOW);
  auto ctor = (Ctor)dlsym(h, "_ZN8Espresso3AOT17AOTCompilerDriverC1Ev");
  auto run = (Run)dlsym(h, "_ZNK8Espresso3AOT17AOTCompilerDriver3RunEiPPcRNSt3__113basic_ostreamIcNS4_11char_traitsIcEEEE");
  auto names = (Names)dlsym(h, "_ZNK8Espresso3AOT17AOTCompilerDriver25GetRegisteredBackendNamesEv");
  if (!ctor || !run) { std::cerr << "symbols missing\n"; return 1; }
  void *drv = calloc(1, 1 << 16);          // 布局未知，给足空间
  ctor(drv);
  if (getenv("AOT_BACKENDS") && names) { for (auto &n : names(drv)) std::cout << "backend: " << n << "\n"; }
  int rc = run(drv, argc, argv, std::cout);
  std::cout << "\n[rc=" << rc << "]\n";
  return rc;
}
