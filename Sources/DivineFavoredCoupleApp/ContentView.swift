import SwiftUI
import GameKernel

struct ContentView: View {
    @EnvironmentObject var gameState: GameStateManager
    @State private var selectedTab: Tab = .home

    enum Tab: String, CaseIterable {
        case home = "主界面"
        case gacha = "锦鲤池"
        case shop = "商店"
        case inventory = "背包"
        case augury = "推演"
    }

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color(hex: "1a1a2e"), Color(hex: "16213e")],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            VStack(spacing: 0) {
                HeaderView()
                    .padding()

                TabBarView(selectedTab: $selectedTab)

                TabContent(selectedTab: selectedTab)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
    }
}

struct HeaderView: View {
    @EnvironmentObject var gameState: GameStateManager

    var body: some View {
        HStack(spacing: 24) {
            StatBadge(
                icon: "sparkles",
                label: "功德",
                value: String(format: "%.0f", gameState.merit.gongde),
                color: .yellow
            )

            StatBadge(
                icon: "moon.stars",
                label: "运势",
                value: String(format: "%.1f", gameState.luck.value),
                color: luckColor
            )

            StatBadge(
                icon: "ticket",
                label: "天机券",
                value: String(format: "%.0f", gameState.wallet.coupons),
                color: .cyan
            )

            StatBadge(
                icon: "shield",
                label: "余庆",
                value: String(format: "%.0f", gameState.merit.reserve),
                color: .green
            )

            Spacer()

            Button("领取每日") {
                Task { await gameState.claimDaily() }
            }
            .buttonStyle(GoldenButtonStyle())
        }
    }

    var luckColor: Color {
        if gameState.luck.value > 30 { return .green }
        if gameState.luck.value < -30 { return .red }
        return .orange
    }
}

struct StatBadge: View {
    let icon: String
    let label: String
    let value: String
    let color: Color

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .foregroundColor(color)
            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(.caption)
                    .foregroundColor(.gray)
                Text(value)
                    .font(.headline)
                    .foregroundColor(.white)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Color.white.opacity(0.1))
        .cornerRadius(8)
    }
}

struct TabBarView: View {
    @Binding var selectedTab: ContentView.Tab

    var body: some View {
        HStack(spacing: 0) {
            ForEach(ContentView.Tab.allCases, id: \.self) { tab in
                Button(action: { selectedTab = tab }) {
                    Text(tab.rawValue)
                        .font(.headline)
                        .foregroundColor(selectedTab == tab ? .yellow : .gray)
                        .padding(.vertical, 12)
                        .frame(maxWidth: .infinity)
                        .background(
                            selectedTab == tab
                                ? Color.yellow.opacity(0.2)
                                : Color.clear
                        )
                }
                .buttonStyle(.plain)
            }
        }
        .background(Color.black.opacity(0.3))
    }
}

struct TabContent: View {
    let selectedTab: ContentView.Tab

    var body: some View {
        switch selectedTab {
        case .home:
            HomeTabView()
        case .gacha:
            GachaTabView()
        case .shop:
            ShopTabView()
        case .inventory:
            InventoryTabView()
        case .augury:
            AuguryTabView()
        }
    }
}

// MARK: - Color Extension
extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 6:
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8:
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

// MARK: - Button Styles
struct GoldenButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundColor(.black)
            .padding(.horizontal, 20)
            .padding(.vertical, 10)
            .background(
                LinearGradient(
                    colors: [Color.yellow, Color.orange],
                    startPoint: .top,
                    endPoint: .bottom
                )
            )
            .cornerRadius(8)
            .scaleEffect(configuration.isPressed ? 0.95 : 1.0)
            .animation(.easeInOut(duration: 0.1), value: configuration.isPressed)
    }
}

struct SecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundColor(.white)
            .padding(.horizontal, 20)
            .padding(.vertical, 10)
            .background(Color.white.opacity(0.2))
            .cornerRadius(8)
            .scaleEffect(configuration.isPressed ? 0.95 : 1.0)
    }
}
