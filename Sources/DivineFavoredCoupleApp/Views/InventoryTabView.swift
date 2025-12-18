import SwiftUI
import GameKernel

struct InventoryTabView: View {
    @EnvironmentObject var gameState: GameStateManager
    @State private var selectedRarity: String? = nil

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // 背包标题
                VStack(spacing: 8) {
                    Text("乾坤袋")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                        .foregroundColor(.green)

                    Text("「纳须弥于芥子，藏天地于方寸」")
                        .font(.subheadline)
                        .foregroundColor(.gray)
                        .italic()
                }
                .padding(.top, 20)

                // 筛选器
                RarityFilter(selectedRarity: $selectedRarity)

                // 背包统计
                InventoryStats()

                // 物品网格
                InventoryGrid(selectedRarity: selectedRarity)
            }
            .padding()
        }
    }
}

struct RarityFilter: View {
    @Binding var selectedRarity: String?

    let rarities: [(name: String, label: String, color: Color)] = [
        ("all", "全部", .white),
        ("legendary", "传说", .orange),
        ("epic", "史诗", .purple),
        ("rare", "稀有", .blue),
        ("common", "普通", .gray)
    ]

    var body: some View {
        HStack(spacing: 12) {
            ForEach(rarities, id: \.name) { rarity in
                Button(action: {
                    selectedRarity = rarity.name == "all" ? nil : rarity.name
                }) {
                    Text(rarity.label)
                        .font(.subheadline)
                        .foregroundColor(isSelected(rarity.name) ? .black : rarity.color)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                        .background(
                            isSelected(rarity.name)
                                ? rarity.color
                                : rarity.color.opacity(0.2)
                        )
                        .cornerRadius(20)
                }
                .buttonStyle(.plain)
            }
        }
    }

    func isSelected(_ name: String) -> Bool {
        if name == "all" { return selectedRarity == nil }
        return selectedRarity == name
    }
}

struct InventoryStats: View {
    @EnvironmentObject var gameState: GameStateManager

    var body: some View {
        HStack(spacing: 24) {
            StatBox(label: "总数", value: "\(gameState.inventory.count)", color: .white)
            StatBox(label: "传说", value: "\(countByRarity("legendary"))", color: .orange)
            StatBox(label: "史诗", value: "\(countByRarity("epic"))", color: .purple)
            StatBox(label: "稀有", value: "\(countByRarity("rare"))", color: .blue)
            StatBox(label: "普通", value: "\(countByRarity("common"))", color: .gray)
        }
        .padding()
        .background(Color.white.opacity(0.05))
        .cornerRadius(12)
    }

    func countByRarity(_ rarity: String) -> Int {
        gameState.inventory.filter { $0.rarity == rarity }.count
    }
}

struct StatBox: View {
    let label: String
    let value: String
    let color: Color

    var body: some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.title2)
                .fontWeight(.bold)
                .foregroundColor(color)
            Text(label)
                .font(.caption)
                .foregroundColor(.gray)
        }
    }
}

struct InventoryGrid: View {
    @EnvironmentObject var gameState: GameStateManager
    let selectedRarity: String?

    var filteredItems: [InventoryItem] {
        if let rarity = selectedRarity {
            return gameState.inventory.filter { $0.rarity == rarity }
        }
        return gameState.inventory
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("物品列表")
                .font(.headline)
                .foregroundColor(.white)

            if filteredItems.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "shippingbox")
                        .font(.system(size: 48))
                        .foregroundColor(.gray.opacity(0.5))
                    Text("背包空空如也")
                        .font(.subheadline)
                        .foregroundColor(.gray)
                    Text("去锦鲤池抽取道具吧")
                        .font(.caption)
                        .foregroundColor(.gray.opacity(0.7))
                }
                .frame(maxWidth: .infinity)
                .padding(40)
            } else {
                LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 6), spacing: 12) {
                    ForEach(filteredItems, id: \.id) { item in
                        InventoryItemCard(item: item)
                    }
                }
            }
        }
        .padding()
        .background(Color.white.opacity(0.05))
        .cornerRadius(16)
    }
}

struct InventoryItemCard: View {
    let item: InventoryItem

    var body: some View {
        VStack(spacing: 6) {
            ZStack {
                RoundedRectangle(cornerRadius: 8)
                    .fill(rarityGradient)
                    .frame(width: 50, height: 50)

                Image(systemName: rarityIcon)
                    .font(.title3)
                    .foregroundColor(.white)

                if item.count > 1 {
                    Text("x\(item.count)")
                        .font(.caption2)
                        .fontWeight(.bold)
                        .foregroundColor(.white)
                        .padding(2)
                        .background(Color.black.opacity(0.6))
                        .cornerRadius(4)
                        .offset(x: 15, y: 15)
                }
            }

            Text(rarityName)
                .font(.caption2)
                .foregroundColor(rarityColor)
                .lineLimit(1)
        }
    }

    var rarityGradient: LinearGradient {
        switch item.rarity {
        case "legendary":
            return LinearGradient(colors: [.orange, .yellow], startPoint: .top, endPoint: .bottom)
        case "epic":
            return LinearGradient(colors: [.purple, .pink], startPoint: .top, endPoint: .bottom)
        case "rare":
            return LinearGradient(colors: [.blue, .cyan], startPoint: .top, endPoint: .bottom)
        default:
            return LinearGradient(colors: [.gray, .gray.opacity(0.7)], startPoint: .top, endPoint: .bottom)
        }
    }

    var rarityIcon: String {
        switch item.rarity {
        case "legendary": return "star.fill"
        case "epic": return "diamond.fill"
        case "rare": return "seal.fill"
        default: return "circle.fill"
        }
    }

    var rarityName: String {
        switch item.rarity {
        case "legendary": return "传说"
        case "epic": return "史诗"
        case "rare": return "稀有"
        default: return "普通"
        }
    }

    var rarityColor: Color {
        switch item.rarity {
        case "legendary": return .orange
        case "epic": return .purple
        case "rare": return .blue
        default: return .gray
        }
    }
}
