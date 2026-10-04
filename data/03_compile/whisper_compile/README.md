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
