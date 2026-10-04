# Whisper large-v3-turbo 编码器的 ANE 编译代价（2026-10-04，macOS 27.0.1，ANECompiler 10.26.6）

模型：WhisperKit 的 Core ML 包 `openai_whisper-large-v3-v20240930_turbo`（AudioEncoder 1.2 GB、TextDecoder 328 MB、
TextDecoderContextPrefill 12 MB、MelSpectrogram 392 KB）。工具：`tools/03_compile/whisper_load.sh`、`whisper_tmp.sh`
（cmload 经 Core ML 加载，ANECompilerService 编译）；`whisper_compile.sh` 用 anecc 直接编译这些包会失败（返回 1），
Core ML 包要先经 Core ML 自己的转换。

| 子模型，首次加载（新进程名，强制编译） | M6（h18g） | M4（h16g） |
|---|---:|---:|
| MelSpectrogram | 0.39 s | |
| TextDecoderContextPrefill | 0.04 s | |
| TextDecoder | 2.29 s，0.5 GB | |
| AudioEncoder | 438 s 时中止（44 GB）；第二次 240 s 时中止（17.7 GB） | **80 s 完成，1.3 GB** |

- 同一进程名再次加载（编译结果复用）：0.01–0.08 s。
- M6 编码器编译时，ANECompilerService（root）写 `/Library/Caches/com.apple.aned/<build>/ModelAssetsCache/<进程>_unsigned/…/anecompiler.swap.*`，
  240 s 时 18.0 GB；前约 70 s 不增长，之后约 3.5 GB/min，CPU 约 200%。另有一份 1.24 GB 的权重副本（e5rt 缓存 `weights1.bin`）。
  M4 上没有出现交换文件。两台都是 16 GB 内存。
- 结束加载进程不会停止 ANECompilerService；要 `killall -9 ANECompilerService`（root），交换文件随之释放。

文件：`wload_M6/`（各子模型两次加载）、`wtmp_Mac18_5/`（M6，每秒可用空间与编译服务 CPU、每 30 s 的大文件与 lsof）、`wtmp_Mac16_10/`（M4）。
路径中的用户主目录已替换为 `~`。

## 不经 Core ML 复现（whisper_capture.sh、whisper_anecc.sh）

编译开始后 17 s，从 e5rt 缓存抓出 Core ML 交给 ANE 编译器的模型 `H18G.bundle/main/main_ane/ane_mil_model/`：
`model.mil`（3.9 MB，15,854 行：5,120 个 einsum、2,560 个 softmax、4,480 个 slice_by_index，WhisperKit 把注意力按头和按块拆开）、
`weights1.bin`（1.27 GB）、`options.plist`（只有 `h18g.EnableLowEffortCPAllocation = true`）。model.mil 放在 `private/whisper_ane_mil/`。

用 anecc 在本进程里编译这份模型（`anecc/`）：

| 编译目标 | 结果 | 用时 | 内存峰值 | 磁盘峰值 |
|---|---|---:|---:|---:|
| h16g（M4） | 成功，HWX 1.29 GB | 41 s | 2.4 GB | 3.8 GB |
| h18（M6 单引擎，不生成双 ANE 程序） | 成功，HWX 1.29 GB | 41 s | 2.5 GB | 3.8 GB |
| h18g + EnableLowEffortCPAllocation | 可用空间低于 15 GB 时结束 | 219 s | 5.9 GB | 44.2 GB |
| h18g | 同上 | 225 s | 6.1 GB | 44.3 GB |

h18g 时 anecc 在输出目录写 `anecompiler.swap.*`，约 15 GB/min，内存只到约 6 GB；进程结束后交换文件被删除。
只有双 ANE 目标失控，选项无影响：编译器（ANECompiler 10.26.6，macOS 27.0.1）在 h18g 的双 ANE 规划上的缺陷。
