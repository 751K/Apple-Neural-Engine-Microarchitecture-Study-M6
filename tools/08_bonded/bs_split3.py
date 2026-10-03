import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import sys,os; sys.path.insert(0,".")
import td_widths as tw, tdwalk
def ec(w): return [h[1]&0xffff for _,h,_,_ in tdwalk.walk(w)]
for s,hh,ww in [("h%dw32"%h,h,32) for h in (8,9,10,11,12,14,15,16)]:
    row=[]; lo=-1; hi=10**9
    for L in (1,2,3,4,5,6,7,8,10,12,16):
        n="k1x4_c256_%s_L%d"%(s,L)
        if not os.path.exists("bsdec/forced/%s/model.hwx"%n): continue
        a=tw.streams("bsdec/ch/%s/model.hwx"%n); f=tw.streams("bsdec/forced/%s/model.hwx"%n)
        pre=sum(ec(next(w for kk,w in a.items() if "nonb" in kk)))
        dual=any("ane1" in kk for kk in a)
        g=2*pre-sum(sum(ec(w)) for kk,w in f.items() if "nonb" not in kk)
        if not any("ane1" in kk for kk in f): row.append("L%d 强制未切"%L); continue
        if dual: hi=min(hi,g)
        else: lo=max(lo,g)
        row.append("L%d %s %d"%(L,"双" if dual else "单",g))
    print("%-7s 张量 %4d KiB  门槛 (%s, %s]  | %s" % (s, 256*hh*ww*2//1024, lo, hi if hi<10**9 else "—", "  ".join(row)))
