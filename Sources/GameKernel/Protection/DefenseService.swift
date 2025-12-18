import Foundation

/// 护道阵法/道具：在 S3/S2 触发时提供额外保护资源。
public actor DefenseService {
    public struct DefenseCharge: Sendable {
        public var count: Int
        public init(count: Int) {
            self.count = max(0, count)
        }
    }

    private var charges: DefenseCharge

    public init(initialCharges: Int = 0) {
        self.charges = DefenseCharge(count: initialCharges)
    }

    /// 消耗护道充能；返回是否抵挡成功。
    public func consume() -> Bool {
        guard charges.count > 0 else { return false }
        charges.count -= 1
        return true
    }

    public func addCharges(_ delta: Int) {
        guard delta > 0 else { return }
        charges.count += delta
    }
}
