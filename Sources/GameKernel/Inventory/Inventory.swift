import Foundation

public struct InventoryItem: Hashable, Sendable {
    public let id: String
    public let rarity: String
    public var count: Int
    public let stackLimit: Int

    public init(id: String, rarity: String, count: Int = 1, stackLimit: Int = 99) {
        self.id = id
        self.rarity = rarity
        self.count = max(0, count)
        self.stackLimit = max(1, stackLimit)
    }
}

public enum InventoryAddResult: CustomStringConvertible, Sendable {
    case added(newStacks: Int, overflow: [InventoryItem])
    case nothingToAdd

    public var description: String {
        switch self {
        case .added(let stacks, let overflow):
            let overflowDesc = overflow.isEmpty ? "none" : overflow.map { "\($0.id)x\($0.count)" }.joined(separator: ",")
            return "added stacks=\(stacks) overflow=[\(overflowDesc)]"
        case .nothingToAdd:
            return "nothing-to-add"
        }
    }
}

/// 简单可堆叠背包，按 item id 分堆。
public actor Inventory {
    private var items: [String: [InventoryItem]] = [:]

    public init() {}

    public func snapshot() -> [InventoryItem] {
        items.values.flatMap { $0 }
    }

    @discardableResult
    public func add(_ newItem: InventoryItem) -> InventoryAddResult {
        guard newItem.count > 0 else { return .nothingToAdd }

        var remaining = newItem.count
        var stacks = items[newItem.id] ?? []

        // 先填充已有未满堆
        for index in stacks.indices {
            if stacks[index].count < stacks[index].stackLimit && remaining > 0 {
                let canFill = stacks[index].stackLimit - stacks[index].count
                let filled = min(canFill, remaining)
                stacks[index].count += filled
                remaining -= filled
            }
        }

        // 新建堆
        while remaining > 0 {
            let toPlace = min(newItem.stackLimit, remaining)
            stacks.append(InventoryItem(id: newItem.id, rarity: newItem.rarity, count: toPlace, stackLimit: newItem.stackLimit))
            remaining -= toPlace
        }

        items[newItem.id] = stacks
        return .added(newStacks: stacks.count, overflow: [])
    }
}
