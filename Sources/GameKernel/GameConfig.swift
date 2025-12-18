import Foundation

public struct EventConfig: Codable, Sendable {
    public struct Weights: Codable, Sendable {
        public let s0: Double
        public let s1: Double
        public let s2: Double
        public let s3: Double
    }

    public let weights: Weights
    public let rescueHours: Int
    public let s3CooldownHours: Int
}

public struct ShopConfig: Codable, Sendable {
    public let vipRate: Double
    public let ledgerPenaltyRate: Double
}

public enum ConfigLoader {
    public static func load<T: Decodable>(_ type: T.Type, named name: String) -> T? {
        let fm = FileManager.default
        // Resource is processed into bundle for GameKernel.
        let url = Bundle.module.url(forResource: name, withExtension: "json")
        guard let url, let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(T.self, from: data)
    }
}
