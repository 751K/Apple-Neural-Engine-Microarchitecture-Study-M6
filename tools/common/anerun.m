// 直接通过 _ANEClient 编译、加载并反复执行一个 mlmodelc，测每次调用耗时。
// 用法：./anerun <mlmodelc> <bonded|nonbonded> [次数=200] [预热=20] [--attrs]
//   nonbonded：编译/加载选项里设 kANEFDisableBondedNetworksKey = YES
// 输出：中位数 / p10 / p90 耗时（微秒）。输入输出缓冲区按 modelAttributes 里的尺寸分配，内容为随机数。
#import <Foundation/Foundation.h>
#import <IOSurface/IOSurface.h>
#include <dlfcn.h>
#include <mach/mach_time.h>

@interface NSObject (ANEPrivate)
+ (id)sharedConnection;
+ (id)modelAtURL:(NSURL *)url key:(NSString *)key;
- (BOOL)compileModel:(id)m options:(NSDictionary *)o qos:(unsigned)q error:(NSError **)e;
- (BOOL)loadModel:(id)m options:(NSDictionary *)o qos:(unsigned)q error:(NSError **)e;
- (BOOL)unloadModel:(id)m options:(NSDictionary *)o qos:(unsigned)q error:(NSError **)e;
- (BOOL)evaluateWithModel:(id)m options:(NSDictionary *)o request:(id)r qos:(unsigned)q error:(NSError **)e;
- (NSDictionary *)modelAttributes;
+ (id)objectWithIOSurface:(IOSurfaceRef)s;
+ (id)requestWithInputs:(NSArray *)i inputIndices:(NSArray *)ii outputs:(NSArray *)o outputIndices:(NSArray *)oi procedureIndex:(NSNumber *)p;
@end

static IOSurfaceRef make_surface(size_t bytes) {
  NSDictionary *p = @{(id)kIOSurfaceWidth : @(bytes), (id)kIOSurfaceHeight : @1, (id)kIOSurfaceBytesPerElement : @1,
                      (id)kIOSurfaceBytesPerRow : @(bytes), (id)kIO