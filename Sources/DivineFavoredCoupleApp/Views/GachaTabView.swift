import SwiftUI
import GameKernel

struct GachaTabView: View {
    @EnvironmentObject var gameState: GameStateManager
    @State private var showResults = false

    var body: some View {
        ZStack {
            ScrollView {
                VStack(spacing: 32) {
                    // 锦鲤池标题
                    VStack(spacing: 8) {
                        Text("锦鲤池")
                            .font(.largeTitle)
                            .fontWeight(.bold)
                            .foregroundColor(.yellow)

                        Text("「天机不可泄露，唯有缘者得之」")
                            .font(.subheadline)
                            .foregroundColor(.gray)
                            .italic()
                    }
                    .padding(.top, 20)

                    // 池子展示
                    PoolDisplay()

                    // 抽卡按钮
                    HStack(spacing: 24) {
                        Button(action: {
                            Task {
                                await gameState.singlePull()
                                showResults = true
                            }
                        }) {
                            VStack(spacing: 4) {
                                Text("单抽")
                                    .font(.headline)
                                Text("10 功德")
                                    .font(.caption)
                                    .opacity(0.8)
                            }
                        }
                        .buttonStyle(GoldenButtonStyle())
                        .disabled(gameState.showingGachaAnimation)

                        Button(action: {
                            Task {
                                await gameState.tenPull()
                                showResults = true
                            }
                        }) {
                            VStack(spacing: 4) {
                                Text("十连")
                                    .font(.headline)
                                Text("90 功德")
                                    .font(.caption)
                                    .opacity(0.8)
                            }
                        }
                        .buttonStyle(GoldenButtonStyle())
                        .disabled(gameState.showingGachaAnimation)
                    }

                    // 保底信息
                    PityInfo()

                    // 抽卡结果
                    if showResults && !gameState.lastGachaResults.isEmpty {
                        GachaResultsView(results: gameState.lastGachaResults)
                    }
                }
                .padding()
            }

            // 抽卡动画遮罩
            if gameState.showingGachaAnimation {
                GachaAnimationOverlay()
            }
        }
    }
}

struct PoolDisplay: View {
    var body: some View {
        ZStack {
            // 背景光效
            Circle()
                .fill(
                    RadialGradient(
                        colors: [Color.cyan.opacity(0.4), Color.purple.opacity(0.2), Color.clear],
                        center: .center,
                        startRadius: 0,
                        endRadius: 150
                    )
                )
                .frame(width: 300, height: 300)

            // 锦鲤图标
            Image(systemName: "fish.fill")
                .resizable()
                .aspectRatio(contentMode: .fit)
                .frame(width: 100, height: 100)
                .foregroundStyle(
                    LinearGradient(
                        colors: [.orange, .red, .pink],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .shadow(color: .orange.opacity(0.5), radius: 20)
        }
    }
}

struct PityInfo: View {
    var body: some View {
        VStack(spacing: 12) {
            Text("概率说明")
                .font(.headline)
                .foregroundColor(.white)

            HStack(spacing: 20) {
                RarityBadge(name: "普通", color: .gray, rate: "82%")
                RarityBadge(name: "稀有", color: .blue, rate: "15%")
                RarityBadge(name: "史诗", color: .purple, rate: "2.7%")
                RarityBadge(name: "传说", color: .orange, rate: "0.3%")
            }

            Text("10抽保底史诗 · 90抽保底传说 · 75抽起软保底")
                .font(.caption)
                .foregroundColor(.gray)
        }
        .padding()
        .background(Color.white.opacity(0.05))
        .cornerRadius(12)
    }
}

struct RarityBadge: View {
    let name: String
    let color: Color
    let rate: String

    var body: some View {
        VStack(spacing: 4) {
            Circle()
                .fill(color)
                .frame(width: 12, height: 12)
            Text(name)
                .font(.caption)
                .foregroundColor(.white)
            Text(rate)
                .font(.caption2)
                .foregroundColor(.gray)
        }
    }
}

struct GachaResultsView: View {
    let results: [GachaOutcome]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("抽卡结果")
                .font(.headline)
                .foregroundColor(.white)

            LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 5), spacing: 12) {
                ForEach(Array(results.enumerated()), id: \.offset) { index, outcome in
                    GachaResultCard(outcome: outcome, index: index)
                }
            }
        }
        .padding()
        .background(Color.white.opacity(0.05))
        .cornerRadius(12)
    }
}

struct GachaResultCard: View {
    let outcome: GachaOutcome
    let index: Int

    var body: some View {
        VStack(spacing: 4) {
            ZStack {
                RoundedRectangle(cornerRadius: 8)
                    .fill(rarityGradient)
                    .frame(width: 60, height: 60)

                Image(systemName: rarityIcon)
                    .font(.title2)
                    .foregroundColor(.white)
            }

            Text(rarityName)
                .font(.caption2)
                .foregroundColor(rarityColor)
        }
        .scaleEffect(isHighRarity ? 1.1 : 1.0)
        .animation(.spring(response: 0.3, dampingFraction: 0.6).delay(Double(index) * 0.05), value: outcome.rarity)
    }

    var rarityGradient: LinearGradient {
        switch outcome.rarity {
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
        switch outcome.rarity {
        case "legendary": return "star.fill"
        case "epic": return "diamond.fill"
        case "rare": return "seal.fill"
        default: return "circle.fill"
        }
    }

    var rarityName: String {
        switch outcome.rarity {
        case "legendary": return "传说"
        case "epic": return "史诗"
        case "rare": return "稀有"
        default: return "普通"
        }
    }

    var rarityColor: Color {
        switch outcome.rarity {
        case "legendary": return .orange
        case "epic": return .purple
        case "rare": return .blue
        default: return .gray
        }
    }

    var isHighRarity: Bool {
        outcome.rarity == "legendary" || outcome.rarity == "epic"
    }
}

struct GachaAnimationOverlay: View {
    @State private var rotation: Double = 0
    @State private var scale: CGFloat = 0.5
    @State private var opacity: Double = 0

    var body: some View {
        ZStack {
            Color.black.opacity(0.8)
                .ignoresSafeArea()

            VStack(spacing: 20) {
                Image(systemName: "fish.fill")
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .frame(width: 100, height: 100)
                    .foregroundStyle(
                        LinearGradient(
                            colors: [.orange, .red, .pink],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .rotationEffect(.degrees(rotation))
                    .scaleEffect(scale)

                Text("天机运转中...")
                    .font(.headline)
                    .foregroundColor(.white)
            }
            .opacity(opacity)
        }
        .onAppear {
            withAnimation(.easeOut(duration: 0.3)) {
                opacity = 1
                scale = 1.2
            }
            withAnimation(.linear(duration: 1).repeatForever(autoreverses: false)) {
                rotation = 360
            }
        }
    }
}
