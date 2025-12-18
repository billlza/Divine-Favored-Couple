import Foundation

public enum EventSeverity: String, Codable, Sendable {
    case s0, s1, s2, s3
}

public struct EventRollResult: CustomStringConvertible, Sendable {
    public let originalSeverity: EventSeverity
    public let finalSeverity: EventSeverity
    public let consumedReserve: Double
    public let consumedY: Double
    public let downgradedDueToLimit: Bool
    public let preventedByProtection: Bool
    /// S3 无保护时的救援截止时间（12h 窗口）。
    public let rescueDeadline: Date?

    public var description: String {
        var parts: [String] = []
        parts.append("orig=\(originalSeverity.rawValue)")
        parts.append("final=\(finalSeverity.rawValue)")
        if downgradedDueToLimit { parts.append("downgraded-limit") }
        if preventedByProtection { parts.append("protected") }
        if consumedReserve > 0 { parts.append("reserve-\(consumedReserve)") }
        if consumedY > 0 { parts.append("y-\(consumedY)") }
        if let rescueDeadline { parts.append("rescue-deadline=\(rescueDeadline)") }
        return parts.joined(separator: " ")
    }
}

/// 事件引擎（离线安全）：S3 事件 24h 至多一次，优先消耗 Reserve/余庆。
public actor EventEngine {
    private let calendar: Calendar
    private var lastS3Date: Date?
    private var rescueDeadline: Date?
    private let severityProvider: @Sendable (LuckScore) -> EventSeverity

    public init(
        calendar: Calendar,
        severityProvider: @escaping @Sendable (LuckScore) -> EventSeverity = { luck in
            // 默认权重采样
            let weights: [EventSeverity: Double] = [
                .s0: 0.6 * luck.goodMultiplier,
                .s1: 0.25,
                .s2: 0.12,
                .s3: 0.03 * luck.badMultiplier
            ]

            let total = weights.values.reduce(0, +)
            guard total > 0 else { return .s0 }

            let roll = Double.random(in: 0...total)
            var accumulator: Double = 0

            for (severity, weight) in weights {
                accumulator += weight
                if roll <= accumulator {
                    return severity
                }
            }

            return .s0
        }
    ) {
        self.calendar = calendar
        self.severityProvider = severityProvider
    }

    /// 离线或在线单次事件判定。
    public func rollEvent(
        wallDate: Date,
        luck: LuckScore,
        reserve: inout Double,
        yBuffer: inout Double
    ) -> EventRollResult {
        let base = sampleSeverity(luck: luck)
        var final = base
        var downgraded = false

        if base == .s3, let last = lastS3Date, let hours = hoursBetween(last, wallDate), hours < 24 {
            final = .s2
            downgraded = true
        }

        if base == .s3 && !downgraded {
            lastS3Date = wallDate
        }

        var consumedReserve: Double = 0
        var consumedY: Double = 0
        var protected = false

        if final == .s3 || final == .s2 {
            (protected, consumedReserve, consumedY, final) = protectIfPossible(
                severity: final,
                reserve: &reserve,
                yBuffer: &yBuffer
            )
        }

        if !protected && base == .s3 {
            rescueDeadline = wallDate.addingTimeInterval(43_200) // 12h
        } else if protected {
            rescueDeadline = nil
        }

        return EventRollResult(
            originalSeverity: base,
            finalSeverity: final,
            consumedReserve: consumedReserve,
            consumedY: consumedY,
            downgradedDueToLimit: downgraded,
            preventedByProtection: protected,
            rescueDeadline: rescueDeadline
        )
    }

    /// 以小时为粒度的离线模拟，应用离线保护规则。
    public func simulateOffline(
        startDate: Date,
        hours: Int,
        luck: LuckScore,
        reserve: inout Double,
        yBuffer: inout Double
    ) -> [EventRollResult] {
        var results: [EventRollResult] = []
        var cursor = startDate

        for _ in 0..<hours {
            cursor = cursor.addingTimeInterval(3600)
            let result = rollEvent(
                wallDate: cursor,
                luck: luck,
                reserve: &reserve,
                yBuffer: &yBuffer
            )
            results.append(result)
        }

        return results
    }

    private func sampleSeverity(luck: LuckScore) -> EventSeverity {
        severityProvider(luck)
    }

    private func protectIfPossible(
        severity: EventSeverity,
        reserve: inout Double,
        yBuffer: inout Double
    ) -> (Bool, Double, Double, EventSeverity) {
        let reserveCost = severity == .s3 ? 120.0 : 60.0
        let yCost = severity == .s3 ? 80.0 : 40.0

        var consumedReserve: Double = 0
        var consumedY: Double = 0

        if reserve >= reserveCost {
            reserve -= reserveCost
            consumedReserve = reserveCost
            return (true, consumedReserve, consumedY, severity)
        }

        if yBuffer >= yCost {
            yBuffer -= yCost
            consumedY = yCost
            return (true, consumedReserve, consumedY, severity)
        }

        // 无保护资源，S3 降级为濒死 S2，S2 保持。
        if severity == .s3 {
            return (false, consumedReserve, consumedY, .s2)
        }

        return (false, consumedReserve, consumedY, severity)
    }

    private func hoursBetween(_ from: Date, _ to: Date) -> Int? {
        let components = calendar.dateComponents([.hour], from: from, to: to)
        return components.hour
    }
}
