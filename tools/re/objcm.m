#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#include <dlfcn.h>
static void dump(const char *cn) {
  Class c = objc_getClass(cn); if (!c) { printf("## %s missing\n", cn); return; }
  printf("## %s\n", cn); unsigned n;
  Method *m = class_copyMethodList(object_getClass(c), &n);
  for (unsigned i = 0; i < n; i++) printf("  + %s\n", sel_getName(method_getName(m[i])));
  m = class_copyMethodList(c, &n);
  for (unsigned i = 0; i < n; i++) printf("  - %s\n", sel_getName(method_getName(m[i])));
}
int main(int argc, char **argv) {
  dlopen("/System/Library/PrivateFrameworks/AppleNeuralEngine.framework/AppleNeuralEngine", RTLD_NOW);
  for (int i = 1; i < argc; i++) dump(argv[i]);
}
