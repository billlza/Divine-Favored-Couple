# 天道眷侣 3A（macOS 单机版）开发计划 v1.1

## 目标与范围
- **版本目标**：在 macOS（Apple Silicon）上交付可玩的 Vertical Slice（v1），覆盖核心循环：功德/运势、事件（含离线保护）、推演与反噬、遮掩、护道、锦鲤池抽卡、商店与本地存档。
- **非目标**：Web/多人联机、PVP、开放世界大规模探索、真实世界影响承诺。
- **平台基线**：macOS 15+，ARM64 Only；构建与测试以 Apple Silicon 为主。Xcode 26+，Swift 6+，Clang/LLVM；`ARCHS=arm64`、`EXCLUDED_ARCHS=x86_64`、`SUPPORTED_PLATFORMS=macosx` 固定。

## 技术架构基线
- **壳层**：Swift 6.2+ + SwiftUI（UI/菜单/存档管理，严格并发）；AppKit/MTKView 承载渲染。
- **渲染层**：Objective-C++ + Metal（Frame Graph，Forward+/Deferred 按场景取舍，KTX2 纹理容器）。
- **核心逻辑**：C++20（ECS/任务系统/资源系统/事件与数值系统）。
- **数据**：SQLite + WAL 存档（schemaVersion + migration），DataTable/DataAsset + JSON 策划表。
- **工具链**：Xcode 26+（ARM64），CMake 驱动引擎库；Git LFS 管理大资源。

## 核心系统落地要求（抽象层级）
- **时间/离线**：单调计时 + 自然日发放 Daily；离线 Tick 与战报，S3 事件离线保护（24h 内仅一次，救援窗口 12h）。
- **功德/运势**：G/Cap/Daily/DebtLimit/Reserve/Y；LS ∈ [-100,100]，GoodMult/BadMult 统一调制。
- **推演与反噬**：每日首免，递增定价；反噬 R 影响 LS_effective 与围观概率；需有至少 1 种清除/缓解入口。
- **遮掩与护道**：遮掩降低围观/抢夺；护道阵法/道具优先消耗 Reserve/余庆，失败才进入濒死判定。
- **抽卡（锦鲤池）**：概率表 + 史诗/传说保底 + 软保底 + 十连保障；产物堆叠整理；背包可扩展但默认可玩。
- **商店/货币**：功德 + 天机券（不可兑换回功德）；VIP 汇率抵扣；天机券支付不触发负债但有轻微代价。
- **演出最低标准**：UI/镜头动效 + 音效；抽卡出金、遮掩成功、护道救援需有强反馈。
- **性能保障**：目标场景 60fps；渲染资源池化、Ring/Triple Buffer；KTX2 + BasisU 压缩流程；ASan/UBSan、clang-tidy、Metal GPU Capture 基线。

## 里程碑与交付物
- **M0：工程骨架 & 存档**
  - SwiftUI 壳 + MTKView 桥接；C++/Objective-C++ 架构搭建。
  - SQLite 存档（原子写入 + 回滚点）；计时服务（单调计时 + 本地日历校验）。
  - 构建脚本：Xcode（App）+ CMake（引擎库）通路，ARM64-only 配置；GitHub Actions/macOS（arm64）runner 基础 CI。
- **M1：功德/运势/事件**
  - 数值模块：G/Cap/Daily/DebtLimit/Reserve/Y 与 LS 映射；概率调制接口。
  - 事件系统：S0-S3 分级，在线/离线 Tick，离线保护与战报生成。
  - 日常循环：7 天连续 Daily 验证、负债拦截逻辑。
- **M2：商店 + 抽卡**
  - 货币结算：功德/天机券/VIP 抵扣；天机券代价钩子。
  - 锦鲤池：概率表/保底/软保底/十连；可重复测试的固定随机种子模式。
  - 背包堆叠/整理策略；基础 UI 演出（光效/音效 stub）。
- **M3：推演/反噬/遮掩/护道闭环**
  - 推演定价与反噬累积；LS_effective 应用到事件权重。
  - 遮掩与护道阵法效果；反噬清除/缓解入口；围观/抢夺概率调制。
  - 战报与救援窗口完整流程。
- **M4：演出与打磨**
  - 关键交互动效、音效、镜头演出；UI 文字风格统一（卦象语气）。
  - 性能与稳定性：>=60fps 目标场景；启动/首帧埋点；崩溃/异常上报选型预留；Apple Silicon 机型覆盖 M1/M2/M3/M4 取样。

## 迭代策略与验收
- **验收用例**：7 日 Daily 不重复；DebtLimit 后功德支付被拒且天机券可用；离线 24h 无“直接死亡”；抽卡保底可复现。
- **测试模式**：固定随机种子、时间加速、调试支付开关；ASan/UBSan 与 clang-tidy 接入。
- **资源与 LFS**：大纹理/音频/动画资产必须走 Git LFS；建立 KTX2/BasisU 压缩与导入管线。

## 近期优先事项（下一个迭代）
1. 建立基础仓库结构与 CMake/Xcode 双通道编译（ARM64-only）。
2. 实现单调计时 + 日历校验服务与 SQLite 存档骨架。
3. 编写数值核心（功德/运势映射）与事件权重接口，铺设离线 Tick stub。
4. 搭建锦鲤池概率/保底数据结构与测试种子模式。
5. 定义演出资产接口（音效/特效占位），便于后续替换为正式资产。
