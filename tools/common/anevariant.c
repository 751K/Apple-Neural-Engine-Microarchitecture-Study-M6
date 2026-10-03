// 只在我们自己的 anecc 进程里替换 os_variant_has_internal_content：参数为 "com.apple.ane" 时返回 true，其余照常调用原函数。
// 目的：打开 ANECompiler 的调试开关 DebugMask（ANECGetCompilerOptions 只在该函数为真时读取），以导出编译器性能模型的逐层 CSV。
// 不修改系统文件或设置，不影响其他进程；编出的 HWX 只用来读 CSV，不执行。
// 编译：clang -O2 -dynamiclib anevariant.c -o anevariant.dylib
// 用法：DYLD_INSERT_LIBRARIES=./anevariant.dylib ./anecc <mlmodelc> <输出目录> h18g DebugMask=0x800
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

extern bool os_variant_has_internal_content(const char *subsystem);

static bool my_has_internal_content(const char *subsystem) {
  bool hit = subsystem && !strcmp(subsystem, "com.apple.ane");
  fprintf(stderr, "[anevariant] os_variant_has_internal_content(\"%s\") -> %s\n", subsystem ? subsystem : "(null)",
          hit ? "true（替换）" : "原函数");
  return hit ? true : os_variant_has_internal_content(subsystem);
}

__attribute__((used)) static const struct {
  const void *replacement;
  const void *original;
} interposers[] __attribute__((section("__DATA,__interpose"))) = {
    {(const void *)my_has_internal_content, (const void *)os_variant_has_internal_content},
};
