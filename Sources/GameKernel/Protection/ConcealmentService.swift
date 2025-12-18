import Foundation

/// 遮掩天机：降低围观/抢夺概率，在本简化实现中直接调节事件抽样。
public actor ConcealmentService {
    public enum ConcealmentState: Sendable, Equatable {
        case inactive
        case active(evasionMultiplier: Double, expiresAt: Date?)
    }

    private var state: ConcealmentState = .inactive

    public init() {}

    public func activate(evasionMultiplier: Double = 0.5, duration: TimeInterval? = 3600) {
        let expiry = duration.map { Date().addingTimeInterval($0) }
        state = .active(evasionMultiplier: evasionMultiplier, expiresAt: expiry)
    }

    public func deactivate() {
        state = .inactive
    }

    public func currentMultiplier(now: Date = Date()) -> Double {
        switch state {
        case .inactive:
            return 1.0
        case .active(let mult, let expiresAt):
            if let exp = expiresAt, now >= exp {
                state = .inactive
                return 1.0
            }
            return mult
        }
    }
}
