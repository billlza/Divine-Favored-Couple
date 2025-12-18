import SwiftUI
import GameKernel

struct HomeTabView: View {
    @EnvironmentObject var gameState: GameStateManager

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // 角色卡片
                CharacterCard()

                // 状态面板
                StatusPanel()

                // 事件日志
                EventLogPanel()
            }
            .padding()
        }
    }
}

struct CharacterCard: View {
    @EnvironmentObject var gameState: GameStateManager

    var body: some View {
        VStack(spacing: 16) {
            ZStack {
                Circle()
                    .fill(
                        RadialGradient(
                            colors: [Color.purple.opacity(0.6), Color.clear],
                            center: .center,
                            startRadius: 0,
                            endRadius: 100
                        )
                    )
                    .frame(width: 200, height: 200)

                Image(systemName: "person.circle.fill")
                    .resizable()
                    .frame(width: 120, height: 120)
                    .foregroundColor(.white.opacity(0.8))
            }

            Text("李清然")
                .font(.title)
                .foregroundColor(.white)

            Text(luckDescription)
                .font(.subheadline)
                .foregroundColor(luckColor)
                .italic()
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(Color.white.opacity(0.05))
        .cornerRadius(16)
    }

    var luckDescription: String {
        let value = gameState.luck.value
        if value > 60 { return "「天命所归，万事顺遂」" }
        if value > 30 { return "「气运亨通，福星高照」" }
        if value > 0 { return "「运势平稳，小有机缘」" }
        if value > -30 { return "「时运不济，宜静待时」" }
        if value > -60 { return "「霉运缠身，诸事不顺」" }
        return "「天道示警，大凶之兆」"
    }

    var luckColor: Color {
        let value = gameState.luck.value
        if value > 30 { return .green }
        if value > 0 { return .yellow }
        if value > -30 { return .orange }
        return .red
    }
}

struct StatusPanel: View {
    @EnvironmentObject var gameState: GameStateManager

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("状态总览")
                .font(.headline)
                .foregroundColor(.white)

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                StatusItem(title: "功德上限", value: String(format: "%.0f", gameState.merit.cap))
                StatusItem(title: "每日发放", value: String(format: "%.0f", gameState.merit.daily))
                StatusItem(title: "透支下限", value: String(format: "%.0f", gameState.merit.debtLimit))
                StatusItem(title: "余庆缓冲", value: String(format: "%.0f", gameState.merit.yBuffer))
                StatusItem(title: "反噬点数", value: "\(gameState.backlash.points)")
                StatusItem(title: "运势惩罚", value: String(format: "%.1f", gameState.backlash.luckPenalty))
                StatusItem(title: "遮掩状态", value: gameState.concealmentActive ? "激活" : "未激活")
                StatusItem(title: "护道充能", value: "\(gameState.defenseCharges)")
            }
        }
        .padding()
        .background(Color.white.opacity(0.05))
        .cornerRadius(16)
    }
}

struct StatusItem: View {
    let title: String
    let value: String

    var body: some View {
        HStack {
            Text(title)
                .font(.subheadline)
                .foregroundColor(.gray)
            Spacer()
            Text(value)
                .font(.subheadline)
                .foregroundColor(.white)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Color.white.opacity(0.05))
        .cornerRadius(8)
    }
}

struct EventLogPanel: View {
    @EnvironmentObject var gameState: GameStateManager

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("事件日志")
                    .font(.headline)
                    .foregroundColor(.white)

                Spacer()

                Button("模拟事件") {
                    Task { await gameState.simulateEvent() }
                }
                .buttonStyle(SecondaryButtonStyle())
            }

            if gameState.eventReports.isEmpty {
                Text("暂无事件记录")
                    .font(.subheadline)
                    .foregroundColor(.gray)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding()
            } else {
                ForEach(gameState.eventReports.suffix(5).reversed(), id: \.timestamp) { report in
                    EventReportRow(report: report)
                }
            }
        }
        .padding()
        .background(Color.white.opacity(0.05))
        .cornerRadius(16)
    }
}

struct EventReportRow: View {
    let report: EventReport

    var body: some View {
        HStack {
            Circle()
                .fill(severityColor(report.final))
                .frame(width: 10, height: 10)

            Text(severityText(report.original))
                .font(.subheadline)
                .foregroundColor(.white)

            if report.original != report.final {
                Image(systemName: "arrow.right")
                    .foregroundColor(.gray)
                Text(severityText(report.final))
                    .font(.subheadline)
                    .foregroundColor(.green)
            }

            Spacer()

            Text(report.timestamp, style: .time)
                .font(.caption)
                .foregroundColor(.gray)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Color.white.opacity(0.03))
        .cornerRadius(6)
    }

    func severityColor(_ severity: EventSeverity) -> Color {
        switch severity {
        case .s0: return .green
        case .s1: return .yellow
        case .s2: return .orange
        case .s3: return .red
        }
    }

    func severityText(_ severity: EventSeverity) -> String {
        switch severity {
        case .s0: return "吉"
        case .s1: return "小凶"
        case .s2: return "中凶"
        case .s3: return "大凶"
        }
    }
}
