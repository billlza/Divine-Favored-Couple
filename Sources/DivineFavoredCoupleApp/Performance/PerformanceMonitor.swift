import Foundation
import QuartzCore

/// 性能监控服务
@MainActor
final class PerformanceMonitor: ObservableObject {
    static let shared = PerformanceMonitor()

    @Published var currentFPS: Double = 0
    @Published var averageFPS: Double = 0
    @Published var frameTime: Double = 0
    @Published var memoryUsage: UInt64 = 0

    private var frameCount: Int = 0
    private var lastFrameTime: CFTimeInterval = 0
    private var fpsHistory: [Double] = []
    private let historySize = 60

    private var displayLink: CVDisplayLink?
    private var isMonitoring = false

    private init() {}

    /// 开始监控
    func startMonitoring() {
        guard !isMonitoring else { return }
        isMonitoring = true

        // 启动帧率监控
        Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.updateMetrics()
            }
        }

        lastFrameTime = CACurrentMediaTime()
    }

    /// 停止监控
    func stopMonitoring() {
        isMonitoring = false
    }

    /// 记录帧
    func recordFrame() {
        let currentTime = CACurrentMediaTime()
        let delta = currentTime - lastFrameTime

        if delta > 0 {
            frameTime = delta * 1000 // 转换为毫秒
            currentFPS = 1.0 / delta
        }

        lastFrameTime = currentTime
        frameCount += 1
    }

    /// 更新指标
    private func updateMetrics() {
        // 更新 FPS 历史
        fpsHistory.append(currentFPS)
        if fpsHistory.count > historySize {
            fpsHistory.removeFirst()
        }

        // 计算平均 FPS
        if !fpsHistory.isEmpty {
            averageFPS = fpsHistory.reduce(0, +) / Double(fpsHistory.count)
        }

        // 更新内存使用
        memoryUsage = getMemoryUsage()

        frameCount = 0
    }

    /// 获取内存使用量
    private func getMemoryUsage() -> UInt64 {
        var info = mach_task_basic_info()
        var count = mach_msg_type_number_t(MemoryLayout<mach_task_basic_info>.size) / 4

        let result = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: 1) {
                task_info(mach_task_self_, task_flavor_t(MACH_TASK_BASIC_INFO), $0, &count)
            }
        }

        return result == KERN_SUCCESS ? info.resident_size : 0
    }

    /// 记录启动时间点
    func recordLaunchMilestone(_ name: String) {
        let timestamp = CACurrentMediaTime()
        print("[\(String(format: "%.3f", timestamp))s] \(name)")
    }

    /// 格式化内存大小
    func formattedMemory() -> String {
        let mb = Double(memoryUsage) / 1024 / 1024
        return String(format: "%.1f MB", mb)
    }
}

/// 性能指标视图（调试用）
import SwiftUI

struct PerformanceOverlay: View {
    @ObservedObject var monitor = PerformanceMonitor.shared

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("FPS: \(String(format: "%.1f", monitor.currentFPS))")
            Text("Avg: \(String(format: "%.1f", monitor.averageFPS))")
            Text("Frame: \(String(format: "%.2f", monitor.frameTime))ms")
            Text("Mem: \(monitor.formattedMemory())")
        }
        .font(.system(size: 10, weight: .medium, design: .monospaced))
        .foregroundColor(.green)
        .padding(8)
        .background(Color.black.opacity(0.7))
        .cornerRadius(8)
    }
}
