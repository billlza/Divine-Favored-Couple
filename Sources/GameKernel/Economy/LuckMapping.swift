import Foundation

/// Luck score [-100, 100] derived from功德。
public struct LuckScore: Equatable, Sendable {
    public let value: Double

    public init(clamped value: Double) {
        self.value = max(-100, min(100, value))
    }

    public var goodMultiplier: Double {
        pow(2.0, value / 50.0)
    }

    public var badMultiplier: Double {
        pow(2.0, -value / 50.0)
    }
}

public struct LuckMapping: Sendable {
    private let positiveScale: Double
    private let negativeScale: Double

    /// `positiveScale` 通常与 Cap 关联，`negativeScale` 与 DebtLimit 关联（用绝对值）。
    public init(positiveScale: Double, negativeScale: Double) {
        self.positiveScale = max(1, positiveScale)
        self.negativeScale = max(1, negativeScale)
    }

    /// 使用平滑双曲正切曲线映射功德余额到 LS。
    public func map(gongde: Double) -> LuckScore {
        if gongde >= 0 {
            let ratio = gongde / positiveScale
            let ls = 100 * tanh(ratio)
            return LuckScore(clamped: ls)
        } else {
            let ratio = abs(gongde) / negativeScale
            let ls = -100 * tanh(ratio)
            return LuckScore(clamped: ls)
        }
    }
}
