#!/bin/zsh
# root 下的 anemon 记录 FoundationModels 生成：空闲 15 s → 生成 7 轮 → 空闲 15 s
cd "$(dirname "$0")"
sudo -v || exit 1
sudo anemon --json --interval 1 > anemon_root.jsonl 2> anemon_root.err &
sleep 15
./fmprobe 7 | tee fmprobe_root.txt
sleep 15
sudo pkill -INT -f "anemon --json"
sleep 1
echo "done: $(grep -c . anemon_root.jsonl) samples"
