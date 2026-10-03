import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import sys,os; sys.path.insert(0,".")
import td_widths as tw, tdwalk
def ec(w): return [h[1]&0xffff for _,h,_,_ in tdwalk.walk(w)]
for k in ["1x1","1x2","1x3","1x5","1x6","1x7","1x8","3x1","9x1","3x3"]:
    row=[]
    for L in (2,3,4,8,16,24):
        n="k%s_c256_h8w32_L%d"%(k,L)
        if not os.path.exists("bsdec/forced/%s/model.hwx"%n): continue
        a=tw.streams("bsdec/all/%s/model.hwx"%n); f=tw.streams("bsdec/forced/%s/model.hwx"%n)
        pre=sum(ec(next(w for kk,w in a.items() if "nonb" in kk)))
        dec="双" if any("ane1" in kk for kk in a) else "单"
        fs=sum(sum(ec(w)) for kk,w in f.items() if "nonb" not in kk)
        f1=any("ane1" in kk for kk in f)
        row.append("L%d %s %d" % (L,dec,2*pre-fs) + ("" if f1 else "(强制也未切)"))
    print("%-4s " % k + "  ".join(row))
