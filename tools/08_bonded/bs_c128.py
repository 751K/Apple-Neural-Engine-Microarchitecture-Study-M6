import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import sys,os; sys.path.insert(0,".")
import td_widths as tw, tdwalk
def ec(w): return [h[1]&0xffff for _,h,_,_ in tdwalk.walk(w)]
for s,hh in (("h8w64",8),("h9w64",9)):
    row=[]; lo=-1; hi=None
    for L in (2,4,8,12,16,20,24,32):
        n="k1x4_c128_%s_L%d"%(s,L)
        a=tw.streams("bsdec/ch/%s/model.hwx"%n); f=tw.streams("bsdec/forced/%s/model.hwx"%n)
        pre=sum(ec(next(w for k,w in a.items() if "nonb" in k))); dual=any("ane1" in k for k in a)
        fs=[(k,ec(w)) for k,w in f.items() if "nonb" not in k]
        g=2*pre-sum(sum(e) for _,e in fs)
        if not any("ane1" in k for k,_ in fs): row.append("L%d 强制未切"%L); continue
        if dual: hi=g if hi is None else min(hi,g)
        else: lo=max(lo,g)
        row.append("L%d %s 切前%d 增益%d"%(L,"双" if dual else "单",pre,g))
    print("128 通道 %s 激活 %d KiB 每 NE 权重 8 KiB  开销 (%s, %s] | %s"%(s,128*hh*64*2//1024,lo,hi,"  ".join(row)))
