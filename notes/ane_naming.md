# ANE 架构名与芯片的对应

- 日期：2026-10-07
- 数据：`data/03_compile/ane_names.txt`（各设备自报的名字）、`data/03_compile/tdv/*.log`（各编译目标能否编译）
- 工具：`tools/common/anedevinfo.m`（Mac）、`tools/common/aneinfo-ios/`（iPhone / iPad，真机）

## 1. 怎么读

设备的 ANE 名字有两个来源，结果一致：

- IORegistry 里 ANE 驱动服务 `H11ANEIn` 的设备属性 `ANEDevicePropertyTypeANEArchitectureTypeStr`（anemon 用的就是这个，Mac 上 `ioreg` 可见）。
- 私有类 `_ANEDeviceInfo`（AppleNeuralEngine.framework）的类方法：`aneArchitectureType`、`aneSubType`、`aneSubTypeVariant`、`numANECores`、`numANEs`、`aneBoardType`。iPhone 上没有 `ioreg`，用这条路：Xcode 装一个调用它的小 App 到真机（不需要越狱，免费 Apple ID 即可签名）。

Apple 自己把名字拆成两部分：**`aneArchitectureType` = `aneSubType` + `aneSubTypeVariant`**，例如 M4 的 `h16g` = `h16` + `g`。

## 2. 实测

| 设备 | 发布 | aneArchitectureType | aneSubType | aneSubTypeVariant | 核数 | 引擎数 | aneBoardType |
|---|---|---|---|---|---|---|---|
| M4（Mac） | 2024 | h16g | h16 | g | 16 | 1 | 256 |
| A18 Pro（iPhone 16 Pro，iPhone17,1） | 2024 | **h17** | h17 | （空） | 16 | 1 | 512 |
| M5（Mac17,x） | 2025 | **h17** | – | – | 16 | – | – |
| M6（Mac18,5） | 2026 | h18g | – | – | 16 | 2 | – |

- M5 只有 IORegistry 读数（anemon diagnose，2026-10-03），M6 只有 ioreg 读数，`–` 为未读。
- A20 = h19 是用户提供的，未在设备上读过。

## 3. 编译器里的目标

ANECompiler 10.26.6 认识 36 个目标名，逐个编译同一模型（`data/03_compile/tdv/`）：

| 结果 | 目标 |
|---|---|
| 能编译（26 个） | h13、h13g、h14、h14g、h15、h15g、h16、h16c、h16g、h16s、h17、h17a、h17c、h17d、h17g、h17s、h18、h18g、h19、m11、m12、t1、u1–u4 |
| 返回 22（10 个，有名字但无 HAL） | h18c、h18d、h18s、h19c、h19g、h19s、h20、h20c、h20g、h21 |
| 返回 1 | m9、t0 |

H18 以后能编译的只有 h18（subtype 10，TD v20）、h18g 与 h19（都是 subtype 11、TD v24，HAL 内容逐字节相同，见 hwx_h18g.md §11.3）。

## 4. 能确定的

1. 同一年的 A 系列和 M 系列不是同一个编号：2024 年 A18 Pro 是 h17、M4 是 h16g；2026 年 A20 是 h19、M6 是 h18g。
2. A18 Pro 与 M5 的名字完全相同（h17，无变体，16 核）。
3. 变体字母不表示核数：M4（g）与 A18 Pro（无变体）都是 16 核。Bryngelson 书中"后缀决定 num_nes：无 = 4，g = 8，s = 16，c = 32，d = 64"与此不符（bryngelson_summary.md 第 32 行）。
4. h17s 不是任何已知设备的名字。之前用 h17s 代表"H17 一代"做编译对比（compile_cost.md、hwx_h18g.md §1），真实设备 A18 Pro 和 M5 用的都是 h17。

## 5. 推测（未证实）

- **数字是 ANE 设计的编号，新设计先用在 A 系列上**；M 系列或直接沿用手机的设计（M5 = A18 Pro 的 h17），或出一个 `g` 变体（M4 = h16g）。M6 名义上是 h18 的 g 变体，但参数表 `2026BaseLine` 与 h19 相同，即实际是 A20 一代的 ANE。
- `g` 可能表示 Mac 专用配置：h16g 有 8 个 DRAM 通道（单引擎 h18 为 4 个），h18g 有双引擎。证据只有这两条。
- `c`、`d`、`s`、`a` 可能是同一设计的其他芯片规格（如 Pro/Max），没有设备读数。
- `aneBoardType`：M4 为 256，A18 Pro 为 512，含义不明。
- `m`、`t`、`u` 开头的目标（M12 = subtype 17，U1–U4 = 15、18–20，都比 h19 新）与 Apple 的 M 系列协处理器、T2、U1 超宽带芯片同名，是否有关无证据。

## 6. 被推翻的说法

- ~~A18 Pro 与 M4 同代，应报 h16~~：实测 h17（2026-10-07）。
- ~~A20 = h18~~：A20 = h19（用户指出，2026-10-07；已改 hwx_h18g.md、power.md、repro_plan.md、bryngelson_summary.md）。
- ~~M5 = h17s~~（Bryngelson）：M5 = h17。

## 7. 待查

- M5 的 `aneSubTypeVariant`、`aneBoardType`；M6 的 `_ANEDeviceInfo` 全部字段（`anedevinfo` 一次即可）。
- Pro/Max（M4 Pro、M5 Pro 等）的名字，用来检验 `c` / `d` 是否对应它们。ANEForge #295 的维护者有 M5 Pro。
- M1–M3 是否为 h13g–h15g。
