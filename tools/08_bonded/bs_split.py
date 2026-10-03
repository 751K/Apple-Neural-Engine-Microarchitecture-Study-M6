import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import sys,os,re; sys.path.insert(0,".")
import td_widths as tw, tdwalk
def ec(w): return [h[1]&0xffff for _,h,_,_ in tdwalk.walk(w)]
for c in (256,512):
    for L in (1,2,3,4,5,6,7,8,10,12,16):
        n="k1x4_c%d_h8w32_L%d"%(c,L)
        a=tw.streams("bsdec/ch/%s/model.hwx"%n); f=tw.streams("bsdec/forced/%s/model.hwx"%n)
        pre=sum(ec(next(w for k,w in a.items() if "nonb" in k)))
        dec="双" if any("ane1" in k for k in a) else "单"
        f0=ec(next(w for k,w in f.items() if "ane0" in k and "nonb" not in k)); f1=ec(next((w for k,w in f.items() if "ane1" in k),[]))
        print("c%d L%-2d 决策 %s  切前Σ %4d  强制切分后 ANE0 Σ %4d (%d TD)  ANE1 Σ %4d (%d TD)  2·切前−(ANE0+ANE1) = %d" % (c,L,dec,pre,sum(f0),len(f0),sum(f1),len(f1),2*pre-sum(f0)-sum(f1)))
