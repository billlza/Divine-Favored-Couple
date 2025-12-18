import Foundation

public struct GachaOutcome: CustomStringConvertible, Sendable {
    public let rarity: String
    public let pityCounter: Int
    public let legendaryPityCounter: Int

    public var description: String {
        "rarity=\(rarity) pity=\(pityCounter) legendaryPity=\(legendaryPityCounter)"
    }
}

public actor GachaEngine {
    public struct Config: Sendable {
        public let rarities: [(name: String, weight: Double)]
        public let epicPity: Int
        public let legendaryPity: Int
        public let legendarySoftPityStart: Int
        public let legendarySoftPitySlope: Double

        public init(
            rarities: [(name: String, weight: Double)] = [
                ("common", 82.0),
                ("rare", 15.0),
                ("epic", 2.7),
                ("legendary", 0.3)
            ],
            epicPity: Int = 10,
            legendaryPity: Int = 90,
            legendarySoftPityStart: Int = 75,
            legendarySoftPitySlope: Double = 0.25
        ) {
            self.rarities = rarities
            self.epicPity = epicPity
            self.legendaryPity = legendaryPity
            self.legendarySoftPityStart = legendarySoftPityStart
            self.legendarySoftPitySlope = legendarySoftPitySlope
        }
    }

    private let config: Config
    private let random: @Sendable (ClosedRange<Double>) -> Double
    private var pityCounter: Int = 0
    private var legendaryPityCounter: Int = 0

    public init(
        config: Config = Config(),
        random: @escaping @Sendable (ClosedRange<Double>) -> Double = { Double.random(in: $0) }
    ) {
        self.config = config
        self.random = random
    }

    /// 单抽，返回稀有度与保底计数。
    public func singlePull() -> GachaOutcome {
        pityCounter += 1
        legendaryPityCounter += 1

        let rarity = rollRarity()
        if rarity == "epic" || rarity == "legendary" {
            pityCounter = 0
        }
        if rarity == "legendary" {
            legendaryPityCounter = 0
        }

        return GachaOutcome(rarity: rarity, pityCounter: pityCounter, legendaryPityCounter: legendaryPityCounter)
    }

    /// 十连规则：至少稀有。
    public func tenPull() -> [GachaOutcome] {
        var results: [GachaOutcome] = []
        for i in 0..<10 {
            var outcome = singlePull()
            // 十连兜底：若最后一次仍低于 rare，则提升为 rare
            if i == 9 && (outcome.rarity == "common") {
                outcome = GachaOutcome(
                    rarity: "rare",
                    pityCounter: max(0, outcome.pityCounter - 1),
                    legendaryPityCounter: outcome.legendaryPityCounter
                )
                pityCounter = outcome.pityCounter
            }
            results.append(outcome)
        }
        return results
    }

    private func rollRarity() -> String {
        // 强制保底判定
        if pityCounter >= config.epicPity - 1 {
            return "epic"
        }
        if legendaryPityCounter >= config.legendaryPity - 1 {
            return "legendary"
        }

        let adjustedWeights = adjustedLegendaryWeights()
        let total = adjustedWeights.reduce(0.0) { $0 + $1.weight }
        let roll = random(0...total)
        var accumulator: Double = 0

        for entry in adjustedWeights {
            accumulator += entry.weight
            if roll <= accumulator {
                return entry.name
            }
        }

        return adjustedWeights.last?.name ?? "common"
    }

    private func adjustedLegendaryWeights() -> [(name: String, weight: Double)] {
        var weights = config.rarities
        if let index = weights.firstIndex(where: { $0.name == "legendary" }) {
            if legendaryPityCounter >= config.legendarySoftPityStart {
                let extra = Double(legendaryPityCounter - config.legendarySoftPityStart) * config.legendarySoftPitySlope
                weights[index].weight += max(0, extra)
            }
        }
        return weights
    }
}
