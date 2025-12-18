import Foundation

/// 反噬状态：每次付费推演累积 R 点，影响 LS_effective。
public struct BacklashState: Sendable, Codable, Equatable {
    public private(set) var points: Int

    public init(points: Int = 0) {
        self.points = max(0, points)
    }

    /// 累积反噬点。
    public mutating func addPoints(_ delta: Int) {
        guard delta > 0 else { return }
        points += delta
    }

    /// 消耗道具/道法以清除反噬，最少为 0。
    @discardableResult
    public mutating func cleanse(by amount: Int) -> Int {
        guard amount > 0 else { return points }
        points = max(0, points - amount)
        return points
    }

    /// 反噬对应的 LS 惩罚：min(30, 5*R)。
    public var luckPenalty: Double {
        let penalty = Double(points) * 5.0
        return min(30.0, penalty)
    }

    /// 计算生效的运势（LS_effective）。
    public func effectiveLuck(baseLuck: LuckScore) -> LuckScore {
        LuckScore(clamped: baseLuck.value - luckPenalty)
    }
}

public struct AuguryPricing: Sendable {
    public let baseCost: Double
    public let increment: Double

    public init(baseCost: Double = 50, increment: Double = 25) {
        self.baseCost = baseCost
        self.increment = increment
    }

    /// 已付费次数 -> 当次价格。
    public func cost(forPaidCount paidCount: Int) -> Double {
        guard paidCount > 0 else { return 0 }
        return baseCost + increment * Double(paidCount - 1)
    }
}

public enum AuguryOutcome: CustomStringConvertible, Sendable {
    case free
    case paid(cost: Double, backlashAdded: Int)

    public var description: String {
        switch self {
        case .free:
            return "augury-free"
        case .paid(let cost, let backlash):
            return "augury-paid cost=\(cost) backlash+\(backlash)"
        }
    }
}

/// 推演服务：管理每日免费、递增定价和反噬累积。
public actor AuguryService {
    private var paidCountToday: Int = 0
    private let pricing: AuguryPricing

    public init(pricing: AuguryPricing = AuguryPricing()) {
        self.pricing = pricing
    }

    public func resetDaily() {
        paidCountToday = 0
    }

    /// 执行一次推演，返回费用与反噬累积情况。
    public func performAugury(backlash: inout BacklashState) -> AuguryOutcome {
        if paidCountToday == 0 {
            paidCountToday += 1 // 首免计入次数以便后续递增
            return .free
        }

        let cost = pricing.cost(forPaidCount: paidCountToday)
        paidCountToday += 1
        backlash.addPoints(1)
        return .paid(cost: cost, backlashAdded: 1)
    }
}
