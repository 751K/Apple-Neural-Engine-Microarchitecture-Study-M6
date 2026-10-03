import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import sys,os; sys.path.insert(0,".")
import td_widths as tw, tdwalk
def ec(w): return [h[1]&0xffff for _,h,_,_ in tdwalk.walk(w)]
for c in (128,160,192,224,256,288,320,384,512):
    row=[]; lo=-1; hi=None; tdl=0
    for L in (1,2,3,4,5,6,7,8,10,12,16,24,32):
        n="k1x4_c%d_h8w32_L%d"%(c,L)
        if not os.path.exists("bsdec/forced/%s/model.hwx"%n) or not os.path.exists("bsdec/ch/%s/model.hwx"%n): continue
        a=tw.streams("bsdec/ch/%s/model.hwx"%n); f=tw.streams("bsdec/forced/%s/model.hwx"%n)
        nb=next(w for k,w in a.items() if "nonb" in k)
        pre=sum(ec(nb)); dual=any("ane1" in k for k in a); tdl=len(ec(nb))//L
        fs=[(k,ec(w)) for k,w in f.items() if "nonb" not in k]
        g=2*pre-sum(sum(e) for _,e in fs)
        if not any("ane1" in k for k,_ in fs): row.append("L%d 强制未切"%L); continue
        if dual: hi=g if hi is None else min(hi,g)
        else: lo=max(lo,g)
        row.append("L%d%s%d"%(L,"双" if dual else "单",g))
    print("C%-3d 激活 %3d KiB 每NE权重 %3d KiB 每层TD %d 开销 (%s, %s] | %s"%(c,c*8*32*2//1024,c*c*4*2//16//1024,tdl,lo,hi," ".join(row)))
