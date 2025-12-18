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
    /// 是否触发离线战报（仅当有保护或降级）—占位。
    public let battleReportGenerated: Bool
    /// 是否应用了遮掩（降低高危概率的影响）。
    public let concealmentApplied: Bool

    public var description: String {
        var parts: [String] = []
        parts.append("orig=\(originalSeverity.rawValue)")
        parts.append("final=\(finalSeverity.rawValue)")
        if downgradedDueToLimit { parts.append("downgraded-limit") }
        if preventedByProtection { parts.append("protected") }
        if consumedReserve > 0 { parts.append("reserve-\(consumedReserve)") }
        if consumedY > 0 { parts.append("y-\(consumedY)") }
        if let rescueDeadline { parts.append("rescue-deadline=\(rescueDeadline)") }
        if battleReportGenerated { parts.append("report") }
        if concealmentApplied { parts.append("concealed") }
        return parts.joined(separator: " ")
    }
}

/// 事件引擎（离线安全）：S3 事件 24h 至多一次，优先消耗 Reserve/余庆。
public actor EventEngine {
    private let calendar: Calendar
    private var lastS3Date: Date?
    private var rescueDeadline: Date?
    private let severityProvider: @Sendable (LuckScore) -> EventSeverity
    private let concealment: ConcealmentService?
    private let defense: DefenseService?
    private let reportLog: EventReportLog?
    private let randomDouble: @Sendable (ClosedRange<Double>) -> Double
    private let rescueHours: Int
    private let s3CooldownHours: Int

    public init(
        calendar: Calendar,
        concealment: ConcealmentService? = nil,
        defense: DefenseService? = nil,
        reportLog: EventReportLog? = nil,
        randomDouble: @escaping @Sendable (ClosedRange<Double>) -> Double = { Double.random(in: $0) },
        rescueHours: Int = 12,
        s3CooldownHours: Int = 24,
        severityProvider: @escaping @Sendable (LuckScore) -> EventSeverity = defaultSeverityProvider
    ) {
        self.calendar = calendar
        self.severityProvider = severityProvider
        self.concealment = concealment
        self.defense = defense
        self.reportLog = reportLog
        self.randomDouble = randomDouble
        self.rescueHours = rescueHours
        self.s3CooldownHours = s3CooldownHours
    }

    /// 离线或在线单次事件判定。
    public func rollEvent(
        wallDate: Date,
        luck: LuckScore,
        reserve: inout Double,
        yBuffer: inout Double
    ) async -> EventRollResult {
        let base = sampleSeverity(luck: luck)
        var final = base
        var downgraded = false
        var concealmentApplied = false

        if let concealment {
            let mult = await concealment.currentMultiplier(now: wallDate)
            if mult < 1.0, (base == .s3 || base == .s2), randomDouble(0...1) > mult {
                final = .s1
                concealmentApplied = true
            }
        }

        if base == .s3, let last = lastS3Date, let hours = hoursBetween(last, wallDate), hours < s3CooldownHours {
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

        if let defense, !protected, (final == .s3 || final == .s2), await defense.consume() {
            protected = true
        }

        let report = protected || final == .s2

        if !protected && base == .s3 {
            rescueDeadline = wallDate.addingTimeInterval(TimeInterval(rescueHours * 3600))
        } else if protected {
            rescueDeadline = nil
        }

        if report, let reportLog {
            await reportLog.append(EventReport(timestamp: wallDate, original: base, final: final, rescueDeadline: rescueDeadline))
        }

        return EventRollResult(
            originalSeverity: base,
            finalSeverity: final,
            consumedReserve: consumedReserve,
            consumedY: consumedY,
            downgradedDueToLimit: downgraded,
            preventedByProtection: protected,
            rescueDeadline: rescueDeadline,
            battleReportGenerated: report,
            concealmentApplied: concealmentApplied
        )
    }

    /// 以小时为粒度的离线模拟，应用离线保护规则。
    public func simulateOffline(
        startDate: Date,
        hours: Int,
        luck: LuckScore,
        reserve: inout Double,
        yBuffer: inout Double
    ) async -> [EventRollResult] {
        var results: [EventRollResult] = []
        var cursor = startDate

        for _ in 0..<hours {
            cursor = cursor.addingTimeInterval(3600)
            let result = await rollEvent(
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

    public static func defaultSeverityProvider(luck: LuckScore) -> EventSeverity {
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
