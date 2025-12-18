import Foundation

public struct Wallet: Sendable {
    public var merit: MeritState
    public var coupons: Double
    /// VIP 汇率（天机券抵扣倍数，0.8 表示 1 成本需要 0.8 券）。
    public var vipRate: Double

    public init(merit: MeritState, coupons: Double = 0, vipRate: Double = 0.8) {
        self.merit = merit
        self.coupons = coupons
        self.vipRate = max(0, vipRate)
    }

    /// 最大可用功德额度（含透支）。
    public var meritCapacity: Double {
        max(0, merit.gongde - merit.debtLimit)
    }
}

public enum PurchaseOutcome: CustomStringConvertible, Sendable {
    case success(spentG: Double, spentCoupons: Double, ledgerPenalty: Double)
    case debtLimitReached(currentG: Double, limit: Double)
    case insufficientCoupons
    case invalidAmount

    public var description: String {
        switch self {
        case .success(let g, let coupons, let penalty):
            return "success G=\(g) coupons=\(coupons) penalty=\(penalty)"
        case .debtLimitReached(let current, let limit):
            return "debt-limit (G=\(current), limit=\(limit))"
        case .insufficientCoupons:
            return "insufficient-coupons"
        case .invalidAmount:
            return "invalid-amount"
        }
    }
}

/// 商店结算服务：支持功德 + 天机券，天机券不触发负债，包含轻微记账代价。
public actor ShopService {
    public init(config: ShopConfig? = nil) {
        if let config {
            defaultVipRate = config.vipRate
            ledgerPenaltyRate = config.ledgerPenaltyRate
        } else if let loaded: ShopConfig = ConfigLoader.load(ShopConfig.self, named: "shop_config") {
            defaultVipRate = loaded.vipRate
            ledgerPenaltyRate = loaded.ledgerPenaltyRate
        } else {
            defaultVipRate = 0.8
            ledgerPenaltyRate = 0.02
        }
    }

    private let defaultVipRate: Double
    private let ledgerPenaltyRate: Double

    /// 购买。preferCoupons 表示优先使用天机券（按 VIP 汇率），否则优先功德并用券兜底避免越过 DebtLimit。
    public func purchase(
        cost: Double,
        preferCoupons: Bool,
        wallet: inout Wallet
    ) -> PurchaseOutcome {
        guard cost >= 0 else { return .invalidAmount }

        var meritAmount: Double
        var couponAmount: Double

        let capacity = wallet.meritCapacity

        if preferCoupons {
            if wallet.vipRate == 0 { wallet.vipRate = defaultVipRate }
            couponAmount = min(wallet.coupons, cost * wallet.vipRate)
            meritAmount = cost - couponAmount
            // 如果仍超出功德可用额度，尝试用剩余券补足
            if meritAmount > capacity {
                let shortfall = meritAmount - capacity
                let extraCoupon = min(wallet.coupons - couponAmount, shortfall * wallet.vipRate)
                couponAmount += extraCoupon
                meritAmount = cost - couponAmount
            }
        } else {
            couponAmount = 0
            meritAmount = cost
            if meritAmount > capacity {
                let shortfall = meritAmount - capacity
                if wallet.vipRate == 0 { wallet.vipRate = defaultVipRate }
                let couponNeeded = shortfall * wallet.vipRate
                if couponNeeded > wallet.coupons {
                    return .insufficientCoupons
                }
                couponAmount = couponNeeded
                meritAmount = cost - couponAmount
            }
        }

        // 最终检查功德容量
        if meritAmount > capacity {
            return .debtLimitReached(currentG: wallet.merit.gongde, limit: wallet.merit.debtLimit)
        }

        // 扣券
        wallet.coupons -= couponAmount

        // 扣功德
        if meritAmount > 0 {
            let spendResult = wallet.merit.spend(amount: meritAmount)
            if case .debtLimitReached(let current, let limit) = spendResult {
                return .debtLimitReached(currentG: current, limit: limit)
            }
            if case .invalidAmount = spendResult {
                return .invalidAmount
            }
        }

        let ledgerPenalty = couponAmount > 0 ? couponAmount * ledgerPenaltyRate : 0
        return .success(spentG: meritAmount, spentCoupons: couponAmount, ledgerPenalty: ledgerPenalty)
    }
}
