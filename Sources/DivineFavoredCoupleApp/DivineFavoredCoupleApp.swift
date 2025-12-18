import SwiftUI
import GameKernel

@main
struct DivineFavoredCoupleApp: App {
    @StateObject private var gameState = GameStateManager()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(gameState)
                .frame(minWidth: 1024, minHeight: 768)
        }
        .windowStyle(.hiddenTitleBar)
        .commands {
            CommandGroup(replacing: .newItem) {}
        }
    }
}
