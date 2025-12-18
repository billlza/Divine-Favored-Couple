#pragma once

/**
 * @file GameEngine.h
 * @brief 天道眷侣游戏引擎 C++ 接口
 *
 * 此头文件定义了游戏引擎的核心 C++ 接口，用于：
 * - Metal 渲染层集成
 * - ECS 实体组件系统
 * - 资源管理系统
 * - 任务调度系统
 */

#include <cstdint>

namespace DFC {

/// 引擎版本信息
struct EngineVersion {
    uint32_t major;
    uint32_t minor;
    uint32_t patch;
};

/// 获取引擎版本
EngineVersion getEngineVersion();

/// 引擎初始化配置
struct EngineConfig {
    bool enableValidation;
    bool enableProfiling;
    uint32_t maxEntities;
    uint32_t maxComponents;
};

/// 引擎初始化
bool initializeEngine(const EngineConfig& config);

/// 引擎关闭
void shutdownEngine();

/// 帧更新
void tickEngine(float deltaTime);

} // namespace DFC
