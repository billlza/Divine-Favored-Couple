# TECH_STACK_2025.md (Apple Silicon Only)

> 项目目标：先做 **macOS 可玩的“3A质感”单机版本**（不做 Web），性能优先、资产管线清晰、后续可扩到 Windows / 主机（可选）或 iOS（更难，另开分支）。
> 支持范围：**仅 Apple Silicon（arm64，M1+）**，不支持 Intel（x86_64）。

---

## 0. 结论（推荐栈，一句话）

**“Swift 壳 + Objective-C++ Metal 渲染层 + C++20 引擎核心（ECS/任务系统/资源系统） + 数据驱动剧情/经济系统 + 本地存档”**
这是 macOS（Apple Silicon）上追求 **极致性能 + 深度 Apple 平台能力 + 可控工程复杂度** 的最稳解。

---

## 1. 平台与工具链（2025 标准，Apple Silicon only）

* **目标平台**：macOS **Apple Silicon（arm64）Only**

  * **最低硬件**：M1 / M1 Pro / M1 Max 及以上（M2/M3/M4 全部覆盖）
  * **不支持**：Intel Mac（x86_64）——不构建、不测试、不做兼容兜底
* **最低系统**：建议 **macOS 15+**（更“2025味”的基线；若你要覆盖少量旧机可降到 14，但仍只支持 arm64）
* **IDE/编译器**：Xcode 16+（或你当下最新 Xcode），Swift 6+，Clang/LLVM（随 Xcode）
* **构建**：

  * App 层：Xcode 工程（Swift/SwiftUI + AppKit/MetalKit）
  * 引擎层：CMake（C++20 + Objective-C++），产出静态库/动态库给 App 链接
* **CI**：GitHub Actions（macOS runners，arm64 构建优先；必要时用 self-hosted Apple Silicon runner）

### Xcode 架构设置（必须）

* `ARCHS = arm64`
* `EXCLUDED_ARCHS = x86_64`
* `SUPPORTED_PLATFORMS = macosx`
* 若有第三方库：要求提供 arm64 产物；不接受“仅 x86_64”的依赖

---

## 2. 语言与分层（性能 + 可维护的关键）

### 2.1 App Shell（外层壳）

* **Swift 6 + SwiftUI**：菜单、设置、存档管理、商店 UI、辅助功能
* **窗口/输入**：AppKit（必要时），GameController 框架
* **渲染承载**：MTKView（MetalKit）嵌入 SwiftUI（NSViewRepresentable）

### 2.2 渲染与底层（热路径）

* **Objective-C++（.mm）**：直连 Metal API（最少桥接开销）
* **MSL**：Shader 全家桶
* **SIMD**：CPU 侧矩阵/向量走 `simd`

### 2.3 引擎核心（中层逻辑）

* **C++20**：

  * ECS、任务系统、资源系统、事件系统（Tick/离线结算/战报）
  * 数值系统（功德/运势/天机券/VIP）

---

## 3. 渲染栈（3A质感靠这个）

### 3.1 渲染架构

* **Render Graph / Frame Graph**（推荐）
* **Forward+ 或 Deferred**（按场景取舍）

### 3.2 性能关键点

* 资源池化、Ring Buffer / Triple Buffer
* GPU Residency 管理（贴图/网格分级加载）
* 纹理容器：KTX2 + BasisU（更现代、更规范）

---

## 4. 存档与版本迁移（别炸档）

* **SQLite（推荐）**：schemaVersion + migration
* WAL 模式、断电保护、可恢复性优先

---

## 5. 可选中间件（按阶段引入）

* 物理：Jolt（可选）
* 动画：Ozz（可选）
* 音频：MVP 用 AVAudioEngine；做大再接 FMOD/Wwise

---

## 6. 性能与质量保障（必须）

* Instruments + Metal GPU Capture + Metal System Trace
* ASan/UBSan（开发期）、clang-tidy（静态分析）
* Crash：Sentry/Bugsnag（可选但建议）