# Microarchitecture of the Apple M6 Neural Engine

English | [中文](README.zh.md)

This repository accompanies the technical report *Microarchitecture of the Apple M6 Neural Engine: An Empirical Study Based on Compiled Artifacts, Execution Traces, and Power Measurements*. It holds the report text and the raw data, experiment tools, analysis scripts and figures behind its conclusions.

The report studies the Neural Engine (ANE) of the Apple M6 (T8152, ANE compile target h18g). It covers the program format and compiler, scheduling, the compute array, numerical behavior, the memory hierarchy, dual-engine cooperation, clocks, frequency scaling and power, and uses the M4 as a point of comparison. All models were executed only through public interfaces. The compiler, driver and firmware were analyzed read-only.

The report is currently written in Chinese. An English version is planned.

## What this repository is

- **The report is the single source of conclusions.** Every conclusion in the report carries an evidence tag and links directly to the data files and tools behind it, so any number can be traced back from the report.
- **`data/` and `tools/` are the evidence for the report.** Raw data is kept as recorded. The analysis and plotting scripts read it directly and reproduce the numbers and figures in the report.
- **`notes/` is a lab notebook, not a set of conclusions.** It keeps refuted hypotheses and intermediate estimates. Where it disagrees with the report, the report is authoritative; Appendix C of the report records how each correction was made.

## Contents

| Directory                        | Contents                                                                                                          |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| [`final_report/`](final_report/) | The report, [`zh.md`](final_report/zh.md) (Chinese)                                                               |
| [`figs/`](figs/)                 | Report figures (`fig<chapter>-<n>_*`, SVG and PNG) in `figs/<language>/<theme>/`: `zh` or `en`, `light` or `dark` (dark for dark-mode web pages). `legacy/` holds early overview diagrams not used in the report |
| [`data/`](data/)                 | Raw data, one subdirectory per topic. `_obsolete/` holds superseded data kept for reference                       |
| [`tools/`](tools/)               | Experiment tools and analysis scripts, organized like `data/`                                                     |
| [`notes/`](notes/)               | Lab notes and summaries of prior work                                                                             |

The subdirectory numbers in `data/` and `tools/` differ from the report's chapter numbers:

| Subdirectory  | Report chapter                           |
| ------------- | ---------------------------------------- |
| `02_overview` | Ch. 4 Architecture overview              |
| `03_compile`  | Ch. 5 Compiler and program format        |
| `04_schedule` | Ch. 6 Scheduling and execution           |
| `05_compute`  | Ch. 7 Compute array                      |
| `06_numerics` | Ch. 8 Numerical behavior                 |
| `07_memory`   | Ch. 9 Memory hierarchy and data movement |
| `08_bonded`   | Ch. 10 Dual-engine cooperation           |
| `09_clock`    | Ch. 11 Clock domains                     |
| `10_clpc`     | Ch. 12 Dynamic frequency scaling         |
| `11_power`    | Ch. 13 Power and energy efficiency       |

`tools/` also has a few directories shared across chapters:

- `common/`: runners and samplers, e.g. `bondrun.m`, `anecc.m`, `smcpower.c`, `pclus.c`;
- `lib/`: parsers for compiled artifacts;
- `re/`: read-only reverse-engineering tools;
- `figs/`: scripts that generate the report figures, in the NPG palette from ggsci. `build_all.sh` regenerates every figure: the scripts produce the Chinese light versions, `translate.py` builds the English versions from the tables in `i18n/`, `darken.py` derives the dark versions, and `render.sh` exports SVGs to PNG.

Appendix A of the report lists the tools, data and root requirement of every experiment, chapter by chapter. Appendix B is the data index.

## Not in this repository

- **ANE firmware, the kernelcache, compiler disassembly and raw dumps of the hardware parameter tables.** These are derived from Apple binaries. They were analyzed locally, read-only, and are not redistributed. The report provides the tools to regenerate them on your own machine.
- **Raw records of the real-application tests in Chapter 14.** This data has not yet been organized into the repository, as noted in Appendix B of the report.

## Reproducing the results

Requirements:

- **Hardware and OS**: most experiments need an M6. The Core ML operator-dispatch, zero-activation power and compiler-debugger experiments were done on an M4. The OS was macOS 27.0.1 (26A434). Other OS versions ship a different ANE compiler, so results may differ.
- **Software**:
  - the Xcode command-line tools (`clang`);
  - a Python environment with coremltools 9.0 and PyTorch 2.7 to generate models;
  - numpy for the analysis scripts, plus scipy and matplotlib for plotting.

Steps:

1. **Set up a working directory.** Copy the tools and generator scripts you need into a single working directory. The scripts call each other through relative paths such as `./bondrun`, so they expect all tools to sit flat in one directory. `tools/deploy_m6.sh` can sync all of `tools/`, flattened, to another machine; usage is at the top of the script.
2. **Build the tools.** The build command for each C or Objective-C tool is at the top of its file, for example:
   
   ```bash
   clang -fobjc-arc -O2 bondrun.m -framework Foundation -framework CoreML -o bondrun
   ```
3. **Generate models and run the experiments.** Only the kdebug capture scripts (`*_ktrace.sh`, `d1_trace.sh`, `gov_step.sh`, `gov_target*.sh`) need root; run them with `sudo`. They run the workload as the regular user and hand the result files back to that user when done.
4. **Re-run the analysis.** The analysis scripts read the raw data in `data/` and run on any Mac; no M6 is needed. The figures in the report are generated from the same data by the scripts in `tools/figs/`.

Appendix A.3 of the report walks through three complete examples, from model generation to conclusion. Sections 1.4 and 3.2 of the report describe the constraints the study followed and their exceptions. In short: execution only through public interfaces, read-only observation, no redistribution of firmware or disassembly, and no changes to system security settings.

## Acknowledgments and license

Anthropic's Claude Opus 5.5 played an important role in this work; see the acknowledgments in the report.

This repository is released under the [MIT License](LICENSE).
