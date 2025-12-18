import Foundation

public struct PlayerState: Codable, Sendable, Equatable {
    public var merit: MeritState
    public var luck: LuckScore
    public var backlash: BacklashState
    public var reserve: Double
    public var yBuffer: Double
    public var gachaPity: Int
    public var legendaryPity: Int
    public var character: CharacterState

    public init(
        merit: MeritState = MeritState(),
        luck: LuckScore = LuckScore(clamped: 0),
        backlash: BacklashState = BacklashState(),
        reserve: Double = 0,
        yBuffer: Double = 0,
        gachaPity: Int = 0,
        legendaryPity: Int = 0,
        character: CharacterState = CharacterState()
    ) {
        self.merit = merit
        self.luck = luck
        self.backlash = backlash
        self.reserve = reserve
        self.yBuffer = yBuffer
        self.gachaPity = gachaPity
        self.legendaryPity = legendaryPity
        self.character = character
    }
}

public struct WorldState: Codable, Sendable, Equatable {
    public var lastS3Date: Date?
    public var rescueDeadline: Date?
    public var eventCooldowns: [String: Int]
    public var reports: [EventReport]

    public init(lastS3Date: Date? = nil, rescueDeadline: Date? = nil, eventCooldowns: [String: Int] = [:], reports: [EventReport] = []) {
        self.lastS3Date = lastS3Date
        self.rescueDeadline = rescueDeadline
        self.eventCooldowns = eventCooldowns
        self.reports = reports
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

public struct CharacterState: Codable, Sendable, Equatable {
    public var name: String
    public var mood: Double
    public var hp: Double
    public var equipmentSlots: Int

    public init(name: String = "李清然", mood: Double = 1.0, hp: Double = 1.0, equipmentSlots: Int = 4) {
        self.name = name
        self.mood = mood
        self.hp = hp
        self.equipmentSlots = equipmentSlots
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
