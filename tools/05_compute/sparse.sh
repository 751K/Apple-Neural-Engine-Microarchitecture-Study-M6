#!/bin/zsh
# 稀疏能否在 ANE 上带来收益（模型由 sparse_gen.py 生成在 sparse/；M6 上生成，拷到 M4 上用同一批 mlmodelc）。
# 1. 每个模型用 anecc 编译成 HWX，记录所有 __KERN_<n>（权重）段的大小之和（hwx_kern.py），确认剪枝后是否压缩存储。
#    目标按机型自动选（M6 h18g，M4 h16g；可用 ARCH= 覆盖）。anecc 编译失败的版本，Core ML 会把整个模型放到 CPU 上执行。
# 2. 每次运行连续调用 T 秒，root 时用 kdebug 记录固件任务起止（61b0125 / 61b0126，带 cpu 列）和驱动提交（61b01a9）。
#    bondrun 打印计时窗口的 mach 时间（与 kdebug 同一时基），分析时只取窗口内的任务，窗口内没有任务即在 CPU 上执行。
#    运行中段用 iorlist 采样 SOC-NI 和 DCS BW 读带宽直方图（M6 上截断，只是下限）。
# 3. 运行清单：每个模型用默认随机输入跑一次；c1x1 / c3x3 的 fp16（ReLU）和 lin（无激活）两种稠密模型
#    再用 BONDRUN_FILL=zero（全 0）、half（随机一半为 0）、chan（一半通道为 0）各跑一次。
#    偏置为 0，所以全 0 输入每一层都是 0；half、chan 只影响第 1 层（之后被卷积混合），用来对照。
# 环境变量 KERN=0 跳过第 1 步（各模型的权重段大小已知时省掉 anecc 编译，大模型每个要几分钟）；
#   FILLS=0 不跑第 3 步的三种输入填充。
# 4. ROUNDS=N 时整个清单跑 N 轮，偶数轮倒序（先后顺序带来的状态漂移在两轮间方向相反），运行名后缀 #<轮>。
# 用法（M6 / M4）：cd ~/anehal/hwx && sudo [OUT=目录] [ROUNDS=N] [T=秒] ./sparse.sh [模型名通配 ...]
#   例：sudo OUT=sparse_out2 ROUNDS=2 ./sparse.sh 'c1x1_*' 'c3x3_*'
# 输出：$OUT（默认 sparse_out）/kern_all.txt（模型 字节数 段数）、run.txt（bondrun 输出）、ior_<运行>.txt、
#       marks.txt（运行 起 止，mach）、trace.txt
cd "$(dirname "$0")"
out=${OUT:-sparse_out}
mkdir -p $out
U=${SUDO_USER:-$USER}
if [[ -z $ARCH ]]; then
  case $(sysctl -n hw.model) in Mac16,*) ARCH=h16g ;; *) ARCH=h18g ;; esac
fi
if (( $# )); then MODELS=(); for g in "$@"; do MODELS+=(sparse/${~g}.mlmodelc(N)); done; else MODELS=(sparse/*.mlmodelc); fi
T=${T:-6}
ROUNDS=${ROUNDS:-1}
: > $out/kern_all.txt
[[ ${KERN:-1} == 0 ]] || for M in $MODELS; do
  n=${M:t:r}
  rm -rf /tmp/sparse_hwx; sudo -u "$U" ./anecc $M /tmp/sparse_hwx $ARCH > /dev/null 2>&1
  if [[ -f /tmp/sparse_hwx/model.hwx ]]; then
    echo "$n $(python3 hwx_kern.py /tmp/sparse_hwx/model.hwx)" >> $out/kern_all.txt
  else
    echo "$n failed 0" >> $out/kern_all.txt
  fi
done
echo "# $ARCH $(sysctl -n hw.model)" >> $out/kern_all.txt
ONE=()                              # 运行名：<模型>@<输入>
for M in $MODELS; do ONE+=(${M:t:r}@rand); done
for M in $MODELS; do
  [[ ${FILLS:-1} != 0 && ${M:t:r} == c(1x1|3x3)_(fp16|lin)_L* ]] && for f in zero half chan; do ONE+=(${M:t:r}@$f); done
done
RUNS=()
for (( k = 1; k <= ROUNDS; k++ )); do
  if (( k % 2 )); then for R in $ONE; do RUNS+=($R#$k); done
  else for R in ${(Oa)ONE}; do RUNS+=($R#$k); done; fi
done
typeset -A ITER                     # 预热一次（编译缓存就绪），按每次调用耗时算出跑 T 秒的调用次数
for M in $MODELS; do
  med=$(sudo -u "$U" ./bondrun $M 30 2>&1 | awk '/耗时 中位数/ {print $3}')
  ITER[${M:t:r}]=$(( T * 1000000 / ${med%.*} ))
done
KT=
if (( EUID == 0 )); then
  ktrace trace -t -N -f S0x061b -T $(( ${#RUNS} * (T + 8) + 120 )) |
    awk '$3 ~ /^61b01(25|26|a9)$/ {print $1, $3, $(NF-1)}' > $out/trace.txt &
  KT=$!
  sleep 1
fi
: > $out/run.txt; : > $out/marks.txt
for R in $RUNS; do
  n=${R%@*}; f=${R#*@}; f=${f%#*}
  sleep 3
  echo "== $R" >> $out/run.txt
  sudo -u "$U" env BONDRUN_FILL=$f ./bondrun sparse/$n.mlmodelc ${ITER[$n]} > $out/cur.txt 2>&1 &
  B=$!
  sleep 2
  ./iorlist "SOC-NI" 1 > $out/ior_$R.txt 2>&1
  ./iorlist "DCS BW" 1 >> $out/ior_$R.txt 2>&1
  wait $B
  cat $out/cur.txt >> $out/run.txt
  echo "$R $(awk '/计时窗口 mach/ {print $3, $4}' $out/cur.txt)" >> $out/marks.txt
done
rm -f $out/cur.txt
[[ -n $KT ]] && { pkill -INT -x ktrace; wait $KT; }
chown -R "$U" $out
echo "完成，结果在 $(pwd)/$out"
