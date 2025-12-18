import SwiftUI
import GameKernel
import Combine

@MainActor
final class GameStateManager: ObservableObject {
    // MARK: - Published State
    @Published var merit: MeritState
    @Published var luck: LuckScore
    @Published var backlash: BacklashState
    @Published var wallet: Wallet
    @Published var inventory: [InventoryItem] = []
    @Published var eventReports: [EventReport] = []
    @Published var lastGachaResults: [GachaOutcome] = []
    @Published var concealmentActive: Bool = false
    @Published var defenseCharges: Int = 0
    @Published var showingGachaAnimation: Bool = false
    @Published var lastPurchaseResult: String = ""

    // MARK: - Services
    private let shopService = ShopService()
    private let gachaEngine = GachaEngine()
    private let auguryService = AuguryService()
    private let dailyService: DailyRewardService
    private let eventEngine: EventEngine
    private let concealmentService = ConcealmentService()
    private let defenseService: DefenseService
    private let reportLog = EventReportLog()
    private let saveService = SaveService()
    private let luckMapping: LuckMapping

    private var saveURL: URL {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let gameDir = appSupport.appendingPathComponent("DivineFavoredCouple", isDirectory: true)
        try? FileManager.default.createDirectory(at: gameDir, withIntermediateDirectories: true)
        return gameDir.appendingPathComponent("save.json")
    }

    init() {
        let initialMerit = MeritState(gongde: 100, cap: 1000, daily: 120, reserve: 50, yBuffer: 0)
        self.merit = initialMerit
        self.luckMapping = LuckMapping(positiveScale: initialMerit.cap, negativeScale: abs(initialMerit.debtLimit))
        self.luck = luckMapping.map(gongde: initialMerit.gongde)
        self.backlash = BacklashState()
        self.wallet = Wallet(merit: initialMerit, coupons: 50, vipRate: 0.8)
        self.dailyService = DailyRewardService(calendar: .current)
        self.defenseService = DefenseService(initialCharges: 1)
        self.defenseCharges = 1
        self.eventEngine = EventEngine(
            calendar: .current,
            concealment: concealmentService,
            defense: defenseService,
            reportLog: reportLog
        )

        Task { await loadGame() }
    }

    // MARK: - Daily
    func claimDaily() async {
        let now = Date()
        let mono = MonotonicClock.shared.now()
        var localMerit = merit
        let result = await dailyService.attemptGrant(wallDate: now, monotonicInstant: mono, merit: &localMerit)
        merit = localMerit
        wallet.merit = merit
        updateLuck()
        await saveGame()
        print("Daily claim: \(result)")
    }

    // MARK: - Shop
    func purchase(cost: Double, preferCoupons: Bool) async {
        var localWallet = wallet
        let result = await shopService.purchase(cost: cost, preferCoupons: preferCoupons, wallet: &localWallet)
        wallet = localWallet
        merit = wallet.merit
        updateLuck()
        lastPurchaseResult = result.description
        await saveGame()
    }

    // MARK: - Gacha
    func singlePull() async {
        let cost = 10.0
        var localWallet = wallet
        let purchaseResult = await shopService.purchase(cost: cost, preferCoupons: false, wallet: &localWallet)
        wallet = localWallet
        guard case .success = purchaseResult else {
            lastPurchaseResult = "抽卡失败: \(purchaseResult)"
            return
        }
        merit = wallet.merit
        updateLuck()

        showingGachaAnimation = true
        try? await Task.sleep(for: .milliseconds(500))

        let outcome = await gachaEngine.singlePull()
        lastGachaResults = [outcome]
        let item = InventoryItem(id: "item-\(outcome.rarity)-\(UUID().uuidString.prefix(4))", rarity: outcome.rarity, count: 1)
        inventory.append(item)

        showingGachaAnimation = false
        await saveGame()
    }

    func tenPull() async {
        let cost = 90.0
        var localWallet = wallet
        let purchaseResult = await shopService.purchase(cost: cost, preferCoupons: false, wallet: &localWallet)
        wallet = localWallet
        guard case .success = purchaseResult else {
            lastPurchaseResult = "十连失败: \(purchaseResult)"
            return
        }
        merit = wallet.merit
        updateLuck()

        showingGachaAnimation = true
        try? await Task.sleep(for: .milliseconds(800))

        let outcomes = await gachaEngine.tenPull()
        lastGachaResults = outcomes
        for outcome in outcomes {
            let item = InventoryItem(id: "item-\(outcome.rarity)-\(UUID().uuidString.prefix(4))", rarity: outcome.rarity, count: 1)
            inventory.append(item)
        }

        showingGachaAnimation = false
        await saveGame()
    }

    // MARK: - Augury
    func performAugury() async -> AuguryOutcome {
        var localBacklash = backlash
        let outcome = await auguryService.performAugury(backlash: &localBacklash)
        backlash = localBacklash
        updateLuck()
        await saveGame()
        return outcome
    }

    func cleanseBacklash(amount: Int) {
        backlash.cleanse(by: amount)
        updateLuck()
        Task { await saveGame() }
    }

    // MARK: - Protection
    func activateConcealment(duration: TimeInterval = 3600) async {
        await concealmentService.activate(evasionMultiplier: 0.5, duration: duration)
        concealmentActive = true
    }

    func deactivateConcealment() async {
        await concealmentService.deactivate()
        concealmentActive = false
    }

    // MARK: - Events
    func simulateEvent() async {
        var reserve = merit.reserve
        var yBuffer = merit.yBuffer
        let result = await eventEngine.rollEvent(
            wallDate: Date(),
            luck: luck,
            reserve: &reserve,
            yBuffer: &yBuffer
        )
        merit = MeritState(
            gongde: merit.gongde,
            cap: merit.cap,
            daily: merit.daily,
            reserve: reserve,
            yBuffer: yBuffer
        )
        wallet.merit = merit

        eventReports = await reportLog.snapshot()
        await saveGame()
        print("Event: \(result)")
    }

    // MARK: - Save/Load
    func saveGame() async {
        let player = PlayerState(
            merit: merit,
            luck: luck,
            backlash: backlash,
            reserve: merit.reserve,
            yBuffer: merit.yBuffer
        )
        let shop = ShopState(coupons: wallet.coupons, vipRate: wallet.vipRate)
        let world = WorldState(reports: eventReports)
        let state = SaveState(player: player, world: world, shop: shop)

        do {
            try await saveService.save(state: state, to: saveURL)
        } catch {
            print("Save failed: \(error)")
        }
    }

    func loadGame() async {
        do {
            let state = try await saveService.load(from: saveURL)
            merit = state.player.merit
            luck = state.player.luck
            backlash = state.player.backlash
            wallet = Wallet(merit: merit, coupons: state.shop.coupons, vipRate: state.shop.vipRate)
            eventReports = state.world.reports
        } catch {
            print("Load failed (new game): \(error)")
        }
    }

    private func updateLuck() {
        let baseLuck = luckMapping.map(gongde: merit.gongde)
        luck = backlash.effectiveLuck(baseLuck: baseLuck)
    }
}
