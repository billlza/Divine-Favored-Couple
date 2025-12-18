import Foundation

/// Core economy state for功德（G）与相关上限。
public struct MeritState: Sendable, Codable, Equatable {
    public private(set) var gongde: Double
    public var cap: Double
    public var daily: Double
    public var reserve: Double
    public var yBuffer: Double

    /// 透支下限（负数），遵循设计：DebtLimit = -Daily。
    public var debtLimit: Double {
        -daily
    }

    public init(
        gongde: Double = 0,
        cap: Double = 1000,
        daily: Double = 120,
        reserve: Double = 0,
        yBuffer: Double = 0
    ) {
        self.gongde = gongde
        self.cap = cap
        self.daily = daily
        self.reserve = reserve
        self.yBuffer = yBuffer
    }

    /// 发放每日功德，超出上限的部分进入余庆缓冲。
    @discardableResult
    public mutating func grantDaily() -> DailyGrantResult {
        let availableHeadroom = max(0, cap - gongde)
        let grantToG = min(daily, availableHeadroom)
        let overflow = max(0, daily - availableHeadroom)

        gongde += grantToG
        yBuffer += overflow

        return DailyGrantResult(grantedToG: grantToG, overflowToY: overflow)
    }

    /// 功德支付，遵循 DebtLimit 约束。
    @discardableResult
    public mutating func spend(amount: Double) -> SpendOutcome {
        guard amount >= 0 else { return .invalidAmount }

        let projected = gongde - amount
        if projected < debtLimit {
            return .debtLimitReached(current: gongde, limit: debtLimit)
        }

        gongde = projected
        return .success(remaining: gongde)
    }
}

public struct DailyGrantResult: Sendable {
    public let grantedToG: Double
    public let overflowToY: Double
}

public enum SpendOutcome: CustomStringConvertible, Equatable, Sendable {
    case success(remaining: Double)
    case debtLimitReached(current: Double, limit: Double)
    case invalidAmount

    public var description: String {
        switch self {
        case .success(let remaining):
            return "success (G=\(remaining))"
        case .debtLimitReached(let current, let limit):
            return "debt-limit-reached (G=\(current), limit=\(limit))"
        case .invalidAmount:
            return "invalid-amount"
        }
    }
}
