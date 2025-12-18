import Foundation

public enum PaymentResult: CustomStringConvertible, Sendable {
    case success
    case blocked(reason: String)

    public var description: String {
        switch self {
        case .success:
            return "success"
        case .blocked(let reason):
            return "blocked(\(reason))"
        }
    }
}

/// 调试支付服务：可开关本地支付逻辑，占位后续 StoreKit/Steam 接入。
public actor PaymentDebugService {
    private var enabled: Bool

    public init(enabled: Bool = true) {
        self.enabled = enabled
    }

    public func setEnabled(_ flag: Bool) {
        enabled = flag
    }

    public func process(amount: Double) -> PaymentResult {
        guard enabled else { return .blocked(reason: "debug-payment-disabled") }
        guard amount >= 0 else { return .blocked(reason: "invalid-amount") }
        return .success
    }
}
