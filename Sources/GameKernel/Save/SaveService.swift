import Foundation

/// 高层保存/加载接口，集成核心状态到 SaveState。
public actor SaveService {
    private let manager = SaveManager()

    public init() {}

    /// 聚合当前关键状态，返回编码后的 SaveState。
    public func buildSave(
        player: PlayerState,
        world: WorldState,
        shop: ShopState
    ) -> SaveState {
        SaveState(player: player, world: world, shop: shop)
    }

    public func save(state: SaveState, to url: URL) async throws {
        try await manager.save(state: state, to: url)
    }

    public func load(from url: URL) async throws -> SaveState {
        try await manager.load(from: url)
    }
}
