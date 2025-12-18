import Foundation

/// 处理每日功德发放，结合日历与单调计时的反刷策略。
public actor DailyRewardService {
    public enum GrantStatus: CustomStringConvertible, Equatable, Sendable {
        case granted(days: Int, totalGranted: Double, overflowToY: Double)
        case alreadyClaimed
        case backwardTimeDetected
        case invalidInput

        public var description: String {
            switch self {
            case .granted(let days, let totalGranted, let overflow):
                return "granted(\(days)d, G+\(totalGranted), Y+\(overflow))"
            case .alreadyClaimed:
                return "already-claimed"
            case .backwardTimeDetected:
                return "backward-time-detected"
            case .invalidInput:
                return "invalid-input"
            }
        }
    }

    private let calendar: Calendar
    private let calendarValidator: CalendarValidator
    private var lastGrantDayOrdinal: Int?

    public init(calendar: Calendar) {
        self.calendar = calendar
        self.calendarValidator = CalendarValidator(calendar: calendar)
    }

    /// 尝试发放每日功德。返回发放状态及累积金额（支持跨日补发）。
    @discardableResult
    public func attemptGrant(
        wallDate: Date,
        monotonicInstant: MonotonicInstant,
        merit: inout MeritState
    ) async -> GrantStatus {
        let drift = await calendarValidator.recordTick(wallDate: wallDate, monotonicInstant: monotonicInstant)
        if drift == .backward { return .backwardTimeDetected }

        guard let currentDayOrdinal = calendar.ordinality(of: .day, in: .era, for: wallDate) else {
            return .invalidInput
        }

        // 首次发放
        guard let lastOrdinal = lastGrantDayOrdinal else {
            lastGrantDayOrdinal = currentDayOrdinal
            let result = merit.grantDaily()
            return .granted(days: 1, totalGranted: result.grantedToG, overflowToY: result.overflowToY)
        }

        let delta = currentDayOrdinal - lastOrdinal
        if delta <= 0 {
            return .alreadyClaimed
        }

        var totalGrant: Double = 0
        var totalOverflow: Double = 0
        for _ in 0..<delta {
            let result = merit.grantDaily()
            totalGrant += result.grantedToG
            totalOverflow += result.overflowToY
        }
        lastGrantDayOrdinal = currentDayOrdinal

        return .granted(days: delta, totalGranted: totalGrant, overflowToY: totalOverflow)
    }
}
