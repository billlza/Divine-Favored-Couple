#include "GameEngine.h"

namespace DFC {

EngineVersion getEngineVersion() {
    return {1, 0, 0};
}

bool initializeEngine(const EngineConfig& config) {
    // TODO: 实现 Metal 渲染初始化
    // TODO: 实现 ECS 系统初始化
    // TODO: 实现资源管理器初始化
    (void)config;
    return true;
}

void shutdownEngine() {
    // TODO: 清理资源
}

void tickEngine(float deltaTime) {
    // TODO: 实现帧更新逻辑
    (void)deltaTime;
}

} // namespace DFC
