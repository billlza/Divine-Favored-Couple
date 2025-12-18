import SwiftUI
import GameKernel

struct ShopTabView: View {
    @EnvironmentObject var gameState: GameStateManager

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // 商店标题
                VStack(spacing: 8) {
                    Text("天机阁")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                        .foregroundColor(.cyan)

                    Text("「功德换天机，天机券抵扣」")
                        .font(.subheadline)
                        .foregroundColor(.gray)
                        .italic()
                }
                .padding(.top, 20)

                // 钱包信息
                WalletCard()

                // 商品列表
                ShopItemsGrid()

                // 购买提示
                if !gameState.lastPurchaseResult.isEmpty {
                    Text(gameState.lastPurchaseResult)
                        .font(.subheadline)
                        .foregroundColor(.yellow)
                        .padding()
                        .background(Color.yellow.opacity(0.1))
                        .cornerRadius(8)
                }
            }
            .padding()
        }
    }
}

struct WalletCard: View {
    @EnvironmentObject var gameState: GameStateManager

    var body: some View {
        HStack(spacing: 32) {
            VStack(spacing: 4) {
                Image(systemName: "sparkles")
                    .font(.title2)
                    .foregroundColor(.yellow)
                Text(String(format: "%.0f", gameState.merit.gongde))
                    .font(.title)
                    .fontWeight(.bold)
                    .foregroundColor(.white)
                Text("功德")
                    .font(.caption)
                    .foregroundColor(.gray)
            }

            Divider()
                .frame(height: 60)
                .background(Color.white.opacity(0.3))

            VStack(spacing: 4) {
                Image(systemName: "ticket")
                    .font(.title2)
                    .foregroundColor(.cyan)
                Text(String(format: "%.0f", gameState.wallet.coupons))
                    .font(.title)
                    .fontWeight(.bold)
                    .foregroundColor(.white)
                Text("天机券")
                    .font(.caption)
                    .foregroundColor(.gray)
            }

            Divider()
                .frame(height: 60)
                .background(Color.white.opacity(0.3))

            VStack(spacing: 4) {
                Image(systemName: "percent")
                    .font(.title2)
                    .foregroundColor(.green)
                Text(String(format: "%.0f%%", gameState.wallet.vipRate * 100))
                    .font(.title)
                    .fontWeight(.bold)
                    .foregroundColor(.white)
                Text("VIP汇率")
                    .font(.caption)
                    .foregroundColor(.gray)
            }
        }
        .padding(24)
        .background(Color.white.opacity(0.05))
        .cornerRadius(16)
    }
}

struct ShopItemsGrid: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("道具商店")
                .font(.headline)
                .foregroundColor(.white)

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 16) {
                ShopItemCard(
                    name: "护道符",
                    description: "抵挡一次大凶事件",
                    icon: "shield.fill",
                    cost: 200,
                    iconColor: .blue
                )

                ShopItemCard(
                    name: "遮掩术",
                    description: "降低围观概率1小时",
                    icon: "eye.slash.fill",
                    cost: 100,
                    iconColor: .purple
                )

                ShopItemCard(
                    name: "净化丹",
                    description: "清除1点反噬",
                    icon: "leaf.fill",
                    cost: 80,
                    iconColor: .green
                )

                ShopItemCard(
                    name: "余庆珠",
                    description: "增加50点余庆",
                    icon: "circle.hexagongrid.fill",
                    cost: 150,
                    iconColor: .orange
                )

                ShopItemCard(
                    name: "锦鲤单抽券",
                    description: "免费单抽一次",
                    icon: "fish.fill",
                    cost: 15,
                    iconColor: .pink
                )

                ShopItemCard(
                    name: "天机券礼包",
                    description: "获得100天机券",
                    icon: "gift.fill",
                    cost: 500,
                    iconColor: .cyan
                )
            }
        }
        .padding()
        .background(Color.white.opacity(0.05))
        .cornerRadius(16)
    }
}

struct ShopItemCard: View {
    @EnvironmentObject var gameState: GameStateManager

    let name: String
    let description: String
    let icon: String
    let cost: Double
    let iconColor: Color

    @State private var isPurchasing = false

    var body: some View {
        VStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(iconColor.opacity(0.2))
                    .frame(width: 60, height: 60)

                Image(systemName: icon)
                    .font(.title)
                    .foregroundColor(iconColor)
            }

            Text(name)
                .font(.headline)
                .foregroundColor(.white)

            Text(description)
                .font(.caption)
                .foregroundColor(.gray)
                .multilineTextAlignment(.center)
                .lineLimit(2)

            Button(action: {
                Task {
                    isPurchasing = true
                    await gameState.purchase(cost: cost, preferCoupons: false)
                    isPurchasing = false
                }
            }) {
                HStack(spacing: 4) {
                    Image(systemName: "sparkles")
                        .font(.caption)
                    Text("\(Int(cost))")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                }
                .foregroundColor(.black)
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(Color.yellow)
                .cornerRadius(6)
            }
            .buttonStyle(.plain)
            .disabled(isPurchasing)
        }
        .padding()
        .background(Color.white.opacity(0.03))
        .cornerRadius(12)
    }
}
