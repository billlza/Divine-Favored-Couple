import Foundation

/// Monotonic timestamp wrapper to avoid wall-clock manipulation.
public struct MonotonicInstant: Equatable, Comparable, Sendable {
    public let seconds: TimeInterval

    public init(seconds: TimeInterval) {
        self.seconds = seconds
    }

    public static func < (lhs: MonotonicInstant, rhs: MonotonicInstant) -> Bool {
        lhs.seconds < rhs.seconds
    }
}

/// Provides monotonic time readings with a thin abstraction layer.
public actor MonotonicClock {
    public static let shared = MonotonicClock()
    public init() {}

    /// Returns the current monotonic instant (seconds since boot).
    public nonisolated func now() -> MonotonicInstant {
        MonotonicInstant(seconds: ProcessInfo.processInfo.systemUptime)
    }

    /// Computes the elapsed time between two instants.
    public nonisolated func elapsed(from start: MonotonicInstant, to end: MonotonicInstant? = nil) -> TimeInterval {
        let endInstant = end ?? now()
        return max(0, endInstant.seconds - start.seconds)
    }
}
