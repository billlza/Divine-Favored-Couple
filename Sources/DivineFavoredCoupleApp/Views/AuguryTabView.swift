import SwiftUI
import GameKernel

struct AuguryTabView: View {
    @EnvironmentObject var gameState: GameStateManager
    @State private var lastAuguryResult: String = ""
    @State private var isPerforming = false
    @State private var showHexagram = false

    var body: some View {
        ScrollView {
            VStack(spacing: 32) {
                // 推演标题
                VStack(spacing: 8) {
                    Text("天机推演")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                        .foregroundColor(.purple)

                    Text("「窥探天机，必有代价」")
                        .font(.subheadline)
                        .foregroundColor(.gray)
                        .italic()
                }
                .padding(.top, 20)

                // 卦象展示
                HexagramDisplay(showHexagram: showHexagram)

                // 反噬状态
                BacklashPanel()

                // 推演按钮
                Button(action: performAugury) {
                    HStack(spacing: 8) {
                        Image(systemName: "sparkle.magnifyingglass")
                        Text("推演天机")
                    }
                    .font(.headline)
                }
                .buttonStyle(GoldenButtonStyle())
                .disabled(isPerforming)

                // 推演结果
                if !lastAuguryResult.isEmpty {
                    AuguryResultCard(result: lastAuguryResult)
                }

                // 清除反噬
                CleansePanel()

                // 遮掩控制
                ConcealmentPanel()
            }
            .padding()
        }
    }

    func performAugury() {
        Task {
            isPerforming = true
            showHexagram = true

            try? await Task.sleep(for: .milliseconds(800))

            let outcome = await gameState.performAugury()
            lastAuguryResult = formatOutcome(outcome)

            isPerforming = false
        }
    }

    func formatOutcome(_ outcome: AuguryOutcome) -> String {
        switch outcome {
        case .free:
            return "今日首卦，天机免费示之"
        case .paid(let cost, let backlash):
            return "消耗 \(Int(cost)) 功德，反噬 +\(backlash)"
        }
    }
}

struct HexagramDisplay: View {
    let showHexagram: Bool
    @State private var rotation: Double = 0

    var body: some View {
        ZStack {
            // 背景光环
            Circle()
                .stroke(
                    AngularGradient(
                        colors: [.purple, .blue, .cyan, .purple],
                        center: .center
                    ),
                    lineWidth: 3
                )
                .frame(width: 200, height: 200)
                .rotationEffect(.degrees(rotation))
                .opacity(showHexagram ? 1 : 0.3)

            // 八卦图案
            VStack(spacing: 8) {
                ForEach(0..<6, id: \.self) { index in
                    HexagramLine(isBroken: index % 2 == 0)
                }
            }
            .opacity(showHexagram ? 1 : 0.5)
        }
        .onAppear {
            withAnimation(.linear(duration: 10).repeatForever(autoreverses: false)) {
                rotation = 360
            }
        }
    }
}

struct HexagramLine: View {
    let isBroken: Bool

    var body: some View {
        HStack(spacing: isBroken ? 8 : 0) {
            if isBroken {
                Rectangle()
                    .fill(Color.purple)
                    .frame(width: 40, height: 8)
                Rectangle()
                    .fill(Color.purple)
                    .frame(width: 40, height: 8)
            } else {
                Rectangle()
                    .fill(Color.cyan)
                    .frame(width: 88, height: 8)
            }
        }
    }
}

struct BacklashPanel: View {
    @EnvironmentObject var gameState: GameStateManager

    var body: some View {
        VStack(spacing: 12) {
            Text("反噬状态")
                .font(.headline)
                .foregroundColor(.white)

            HStack(spacing: 32) {
                VStack(spacing: 4) {
                    Text("\(gameState.backlash.points)")
                        .font(.title)
                        .fontWeight(.bold)
                        .foregroundColor(backlashColor)
                    Text("反噬点数")
                        .font(.caption)
                        .foregroundColor(.gray)
                }

                VStack(spacing: 4) {
                    Text(String(format: "%.1f", gameState.backlash.luckPenalty))
                        .font(.title)
                        .fontWeight(.bold)
                        .foregroundColor(.red)
                    Text("运势惩罚")
                        .font(.caption)
                        .foregroundColor(.gray)
                }

                VStack(spacing: 4) {
                    Text(String(format: "%.1f", gameState.luck.value))
                        .font(.title)
                        .fontWeight(.bold)
                        .foregroundColor(luckColor)
                    Text("当前运势")
                        .font(.caption)
                        .foregroundColor(.gray)
                }
            }

            // 反噬进度条
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    Rectangle()
                        .fill(Color.white.opacity(0.1))
                        .frame(height: 8)
                        .cornerRadius(4)

                    Rectangle()
                        .fill(backlashGradient)
                        .frame(width: geometry.size.width * backlashProgress, height: 8)
                        .cornerRadius(4)
                }
            }
            .frame(height: 8)

            Text(backlashWarning)
                .font(.caption)
                .foregroundColor(backlashColor)
        }
        .padding()
        .background(Color.white.opacity(0.05))
        .cornerRadius(12)
    }

    var backlashProgress: CGFloat {
        min(1.0, CGFloat(gameState.backlash.points) / 6.0)
    }

    var backlashColor: Color {
        if gameState.backlash.points >= 5 { return .red }
        if gameState.backlash.points >= 3 { return .orange }
        return .yellow
    }

    var backlashGradient: LinearGradient {
        LinearGradient(colors: [.yellow, .orange, .red], startPoint: .leading, endPoint: .trailing)
    }

    var backlashWarning: String {
        if gameState.backlash.points >= 5 { return "⚠️ 反噬深重，速速清除" }
        if gameState.backlash.points >= 3 { return "反噬渐深，宜早清除" }
        if gameState.backlash.points >= 1 { return "略有反噬，尚可承受" }
        return "身心清净，无有反噬"
    }

    var luckColor: Color {
        if gameState.luck.value > 30 { return .green }
        if gameState.luck.value > 0 { return .yellow }
        if gameState.luck.value > -30 { return .orange }
        return .red
    }
}

struct AuguryResultCard: View {
    let result: String

    var body: some View {
        Text(result)
            .font(.subheadline)
            .foregroundColor(.cyan)
            .padding()
            .frame(maxWidth: .infinity)
            .background(Color.cyan.opacity(0.1))
            .cornerRadius(8)
    }
}

struct CleansePanel: View {
    @EnvironmentObject var gameState: GameStateManager

    var body: some View {
        VStack(spacing: 12) {
            Text("清除反噬")
                .font(.headline)
                .foregroundColor(.white)

            Text("消耗净化丹可清除反噬点数")
                .font(.caption)
                .foregroundColor(.gray)

            Button(action: {
                gameState.cleanseBacklash(amount: 1)
            }) {
                HStack(spacing: 8) {
                    Image(systemName: "leaf.fill")
                    Text("净化 (-1 反噬)")
                }
            }
            .buttonStyle(SecondaryButtonStyle())
            .disabled(gameState.backlash.points == 0)
        }
        .padding()
        .background(Color.white.opacity(0.05))
        .cornerRadius(12)
    }
}

struct ConcealmentPanel: View {
    @EnvironmentObject var gameState: GameStateManager

    var body: some View {
        VStack(spacing: 12) {
            Text("遮掩天机")
                .font(.headline)
                .foregroundColor(.white)

            Text("激活遮掩可降低围观/抢夺概率")
                .font(.caption)
                .foregroundColor(.gray)

            HStack(spacing: 16) {
                Button(action: {
                    Task { await gameState.activateConcealment() }
                }) {
                    HStack(spacing: 8) {
                        Image(systemName: "eye.slash.fill")
                        Text("激活遮掩")
                    }
                }
                .buttonStyle(SecondaryButtonStyle())
                .disabled(gameState.concealmentActive)

                Button(action: {
                    Task { await gameState.deactivateConcealment() }
                }) {
                    HStack(spacing: 8) {
                        Image(systemName: "eye.fill")
                        Text("解除遮掩")
                    }
                }
                .buttonStyle(SecondaryButtonStyle())
                .disabled(!gameState.concealmentActive)
            }

            if gameState.concealmentActive {
                Text("✓ 遮掩已激活")
                    .font(.caption)
                    .foregroundColor(.green)
            }
        }
        .padding()
        .background(Color.white.opacity(0.05))
        .cornerRadius(12)
    }
}
