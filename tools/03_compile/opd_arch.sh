#!/bin/zsh
# 边界模型分别以 h16g（M4）与 h18g（M6）为目标直接调用 ANECCompile（anecc），看 ANE 编译器层面的尺寸上限是否随芯片变化。
# 每个模型一个进程、串行，带看门狗（anecc 的 RSS 超过 LIMIT_MB 杀掉，记 OOM；超时 TMO 秒记 TIMEOUT）。
# 输出 arch.tsv：模型 目标 结果(ok/fail/OOM/TIMEOUT) 秒 峰值MB 产物大小
cd ~/opdispatch
PY=/opt/miniconda3/envs/mps/bin/python
LIMIT_MB=${LIMIT_MB:-8000}; TMO=${TMO:-600}
mkdir -p mlc archout
ls iso | sed 's/.mlpackage//' | grep -E '^sw_(conv_k|maxpool|avgpool_k1[34]|matmul_k)' | grep -v '^sw_conv_k16$' > arch_list.txt
M=(${(f)"$(<arch_list.txt)"})
M+=(conv_k17 max_pool_k15 relu_w65536 relu_w65537 relu_c65536 relu_c65537 conv3x3 lstm cumsum_w reduce_argmax_c add_i32 asin topk_w sdpa layer_norm_c gather_dyn sliding_windows)
M+=(sw_conv_k16)                     # 方核 16×16：Core ML 下编译服务峰值 11.7 GB，放最后
for n in $M; do
  if [[ ! -d mlc/$n.mlmodelc ]]; then
    $PY -c "import coremltools as ct, shutil; p = ct.utils.compile_model('iso/$n.mlpackage'); shutil.move(str(p), 'mlc/$n.mlmodelc')" > /dev/null 2>&1
  fi
done
: > arch.tsv
for n in $M; do
  for a in h16g h18g; do
    o=archout/$n.$a; mkdir -p $o
    ./anecc mlc/$n.mlmodelc $o $a > $o/log.txt 2>&1 &
    pid=$!; t0=$SECONDS; peak=0; why=""
    while kill -0 $pid 2>/dev/null; do
      r=$(ps -o rss= -p $pid 2>/dev/null | tr -d ' '); r=${r:-0}; (( r > peak )) && peak=$r
      (( r / 1024 > LIMIT_MB )) && why=OOM
      (( SECONDS - t0 > TMO )) && why=TIMEOUT
      if [[ -n $why ]]; then kill -9 $pid; break; fi
      sleep 0.5
    done
    wait $pid; rc=$?
    res=${why:-$([[ $rc == 0 && -s $o/model.hwx ]] && echo ok || echo "fail(rc=$rc)")}
    sz=$(stat -f %z $o/model.hwx 2>/dev/null || echo 0)
    echo "$n\t$a\t$res\t$((SECONDS - t0))\t$((peak / 1024))\t$sz" >> arch.tsv
  done
done
echo ARCHDONE >> arch.tsv
