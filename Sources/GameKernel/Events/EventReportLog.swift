import Foundation

public struct EventReport: Sendable, Equatable, Codable {
    public let timestamp: Date
    public let original: EventSeverity
    public let final: EventSeverity
    public let rescueDeadline: Date?
}

/// 简易战报记录（可扩展为离线日志/持久化）。
public actor EventReportLog {
    private var reports: [EventReport] = []
    private let capacity: Int

    public init(capacity: Int = 100) {
        self.capacity = max(10, capacity)
    }

    public func append(_ report: EventReport) {
        reports.append(report)
        if reports.count > capacity {
            reports.removeFirst(reports.count - capacity)
        }
    }

    public func snapshot() -> [EventReport] {
        reports
    }
}
