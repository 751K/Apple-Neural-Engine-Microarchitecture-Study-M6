import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import sys,os; sys.path.insert(0,".")
import td_widths as tw, tdwalk
def ec(w): return [h[1]&0xffff for _,h,_,_ in tdwalk.walk(w)]
for ci,co in ((256,256),(128,256),(256,128),(128,128),(64,64)):
    row=[]; lo=-1; hi=None
    for L in (2,3,4,6,8,12):
        n="io_ci%d_co%d_h9w32_L%d"%(ci,co,L)
        a=tw.streams("bsdec/io/%s/model.hwx"%n); f=tw.streams("bsdec/iof/%s/model.hwx"%n)
        pre=sum(ec(next(w for k,w in a.items() if "nonb" in k))); dual=any("ane1" in k for k in a)
        g=2*pre-sum(sum(ec(w)) for k,w in f.items() if "nonb" not in k)
        if dual: hi=g if hi is None else min(hi,g)
        else: lo=max(lo,g)
        row.append("L%d %s %d"%(L,"双" if dual else "单",g))
    print("输入 %3d 通道 + 输出 %3d 通道 = %3d KiB  开销区间 (%s, %s]  | %s"%(ci,co,(ci+co)*9*32*2//1024,lo,hi,"  ".join(row)))
