import Foundation

public struct PlayerState: Codable, Sendable, Equatable {
    public var merit: MeritState
    public var luck: LuckScore
    public var backlash: BacklashState
    public var reserve: Double
    public var yBuffer: Double
    public var gachaPity: Int
    public var legendaryPity: Int

    public init(
        merit: MeritState = MeritState(),
        luck: LuckScore = LuckScore(clamped: 0),
        backlash: BacklashState = BacklashState(),
        reserve: Double = 0,
        yBuffer: Double = 0,
        gachaPity: Int = 0,
        legendaryPity: Int = 0
    ) {
        self.merit = merit
        self.luck = luck
        self.backlash = backlash
        self.reserve = reserve
        self.yBuffer = yBuffer
        self.gachaPity = gachaPity
        self.legendaryPity = legendaryPity
    }
}

public struct WorldState: Codable, Sendable, Equatable {
    public var lastS3Date: Date?
    public var rescueDeadline: Date?
    public init(lastS3Date: Date? = nil, rescueDeadline: Date? = nil) {
        self.lastS3Date = lastS3Date
        self.rescueDeadline = rescueDeadline
    }
}

public struct ShopState: Codable, Sendable, Equatable {
    public var coupons: Double
    public var vipRate: Double
    public init(coupons: Double = 0, vipRate: Double = 0.8) {
        self.coupons = coupons
        self.vipRate = vipRate
    }
}

public struct SaveState: Codable, Sendable, Equatable {
    public static let currentVersion = 1

    public var schemaVersion: Int
    public var player: PlayerState
    public var world: WorldState
    public var shop: ShopState

    public init(
        schemaVersion: Int = SaveState.currentVersion,
        player: PlayerState = PlayerState(),
        world: WorldState = WorldState(),
        shop: ShopState = ShopState()
    ) {
        self.schemaVersion = schemaVersion
        self.player = player
        self.world = world
        self.shop = shop
    }
}
