import Foundation

/// Captures wall-clock snapshots for anti-time-cheat validation.
public struct CalendarSnapshot: Equatable, Sendable {
    public let date: Date
    public let monotonicInstant: MonotonicInstant
}

public enum CalendarDriftStatus: Equatable, CustomStringConvertible, Sendable {
    case ok
    case sameDay
    case forward(days: Int)
    case backward

    public var description: String {
        switch self {
        case .ok:
            return "ok"
        case .sameDay:
            return "same-day"
        case .forward(let days):
            return "forward+\(days)d"
        case .backward:
            return "backward"
        }
    }
}

/// Validates day progression using both wall-clock and monotonic clock.
public actor CalendarValidator {
    private let calendar: Calendar
    private var lastSnapshot: CalendarSnapshot?

    public init(calendar: Calendar) {
        self.calendar = calendar
    }

    /// Records a tick and returns drift status for reward gating and offline reconciliation.
    @discardableResult
    public func recordTick(wallDate: Date, monotonicInstant: MonotonicInstant) -> CalendarDriftStatus {
        defer { lastSnapshot = CalendarSnapshot(date: wallDate, monotonicInstant: monotonicInstant) }

        guard let previous = lastSnapshot else {
            return .ok
        }

        let previousDay = calendar.ordinality(of: .day, in: .era, for: previous.date) ?? 0
        let currentDay = calendar.ordinality(of: .day, in: .era, for: wallDate) ?? previousDay
        let dayDelta = currentDay - previousDay

        if dayDelta < 0 {
            return .backward
        } else if dayDelta == 0 {
            return .sameDay
        } else {
            return .forward(days: dayDelta)
        }
    }
}
