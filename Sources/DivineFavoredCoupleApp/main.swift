import Foundation
import GameKernel

@main
struct DivineFavoredCoupleApp {
    static func main() async {
        let banner = """
        === 天道眷侣（Vertical Slice Bootstrap） ===
        架构：SwiftUI 壳 + Metal 渲染 + C++20 内核（待接入）
        平台：macOS Apple Silicon（ARM64）
        """
        print(banner)

        await demoClocks()
        demoEconomy()
        await demoDailyGrant()
        await demoEvents()
        await demoAugury()
        await demoShop()
        await demoGacha()
        await demoInventoryGachaIntegration()
    }

    private static func demoClocks() async {
        let now = MonotonicClock.shared.now()
        let wallDate = Date()
        let calendar = Calendar.current
        let calendarValidator = CalendarValidator(calendar: calendar)

        let tickResult = await calendarValidator.recordTick(wallDate: wallDate, monotonicInstant: now)
        print("Monotonic tick (s):", String(format: "%.3f", now.seconds))
        print("Wall date:", wallDate)
        print("Tick status:", tickResult.description)
    }

    private static func demoEconomy() {
        var economy = MeritState()
        let luckMapping = LuckMapping(positiveScale: economy.cap, negativeScale: abs(economy.debtLimit))

        let grant = economy.grantDaily()
        let luckAfterGrant = luckMapping.map(gongde: economy.gongde)

        print("Daily grant -> G +\(grant.grantedToG), Y +\(grant.overflowToY)")
        print("G after grant:", economy.gongde)
        print("Luck after grant:", String(format: "%.2f", luckAfterGrant.value))
        print("GoodMult:", String(format: "%.2f", luckAfterGrant.goodMultiplier), "BadMult:", String(format: "%.2f", luckAfterGrant.badMultiplier))

        let spendResult = economy.spend(amount: 150)
        let luckAfterSpend = luckMapping.map(gongde: economy.gongde)
        print("Spend 150 result:", spendResult.description)
        print("G after spend:", economy.gongde)
        print("Luck after spend:", String(format: "%.2f", luckAfterSpend.value))
    }

    private static func demoDailyGrant() async {
        print("=== Daily Grant Demo ===")
        var economy = MeritState()
        let service = DailyRewardService(calendar: Calendar.current)

        let now = Date()
        let mono = MonotonicClock.shared.now()

        let first = await service.attemptGrant(wallDate: now, monotonicInstant: mono, merit: &economy)
        print("Day0 grant:", first.description, "G:", economy.gongde, "Y:", economy.yBuffer)

        // 同日重复领取，应该被拦截
        let repeatAttempt = await service.attemptGrant(wallDate: now, monotonicInstant: MonotonicInstant(seconds: mono.seconds + 60), merit: &economy)
        print("Day0 repeat:", repeatAttempt.description, "G:", economy.gongde, "Y:", economy.yBuffer)

        // 模拟+1天（离线补发）
        let nextDay = now.addingTimeInterval(86_400)
        let nextMono = MonotonicInstant(seconds: mono.seconds + 90_000)
        let next = await service.attemptGrant(wallDate: nextDay, monotonicInstant: nextMono, merit: &economy)
        print("Day1 grant:", next.description, "G:", economy.gongde, "Y:", economy.yBuffer)
    }

    private static func demoEvents() async {
        print("=== Event System Demo (Offline 6h) ===")
        var economy = MeritState()
        economy.reserve = 180
        economy.yBuffer = 120

        let luckMapping = LuckMapping(positiveScale: economy.cap, negativeScale: abs(economy.debtLimit))
        let luck = luckMapping.map(gongde: economy.gongde)

        let engine = EventEngine(calendar: Calendar.current)
        let start = Date()
        let results = await engine.simulateOffline(
            startDate: start,
            hours: 6,
            luck: luck,
            reserve: &economy.reserve,
            yBuffer: &economy.yBuffer
        )

        for (index, result) in results.enumerated() {
            print("Hour+\(index+1):", result.description)
        }
        print("Reserve remaining:", economy.reserve, "Y buffer remaining:", economy.yBuffer)
    }

    private static func demoAugury() async {
        print("=== Augury & Backlash Demo ===")
        let economy = MeritState()
        let mapping = LuckMapping(positiveScale: economy.cap, negativeScale: abs(economy.debtLimit))
        var backlash = BacklashState()
        let augury = AuguryService()

        func logLuck(_ label: String) {
            let baseLuck = mapping.map(gongde: economy.gongde)
            let effective = backlash.effectiveLuck(baseLuck: baseLuck)
            print(label, "base:", String(format: "%.2f", baseLuck.value), "effective:", String(format: "%.2f", effective.value), "penalty:", String(format: "%.2f", backlash.luckPenalty))
        }

        logLuck("Initial luck")

        let first = await augury.performAugury(backlash: &backlash)
        print("First augury:", first.description)
        logLuck("After free augury")

        let second = await augury.performAugury(backlash: &backlash)
        print("Second augury:", second.description)
        logLuck("After paid augury")

        // Cleanse反噬
        backlash.cleanse(by: 1)
        logLuck("After cleanse")
    }

    private static func demoShop() async {
        print("=== Shop Demo (Coupons + DebtLimit) ===")
        var wallet = Wallet(merit: MeritState(gongde: 50, cap: 200, daily: 120, reserve: 0, yBuffer: 0), coupons: 80, vipRate: 0.8)
        let shop = ShopService()

        let cost1 = 100.0
        let first = await shop.purchase(cost: cost1, preferCoupons: false, wallet: &wallet)
        print("Purchase #1 cost \(cost1):", first.description, "G:", wallet.merit.gongde, "Coupons:", wallet.coupons)

        let cost2 = 120.0
        let second = await shop.purchase(cost: cost2, preferCoupons: true, wallet: &wallet)
        print("Purchase #2 cost \(cost2) prefer coupons:", second.description, "G:", wallet.merit.gongde, "Coupons:", wallet.coupons)
    }

    private static func demoGacha() async {
        print("=== Gacha Demo (10-pull with soft/hard pity) ===")
        let engine = GachaEngine()
        var singles: [GachaOutcome] = []
        for _ in 1...12 {
            let outcome = await engine.singlePull()
            singles.append(outcome)
        }
        for (index, outcome) in singles.enumerated() {
            print("Single #\(index + 1):", outcome.description)
        }

        let ten = await engine.tenPull()
        print("Ten-pull:")
        for (index, outcome) in ten.enumerated() {
            print("  \(index + 1):", outcome.description)
        }
    }

    private static func demoInventoryGachaIntegration() async {
        print("=== Inventory + Gacha Integration ===")
        let engine = GachaEngine()
        let inventory = Inventory()

        let pullResults = await engine.tenPull()
        for outcome in pullResults {
            let item = InventoryItem(id: "item-\(outcome.rarity)", rarity: outcome.rarity, count: 1, stackLimit: 20)
            _ = await inventory.add(item)
        }

        let snapshot = await inventory.snapshot()
        for entry in snapshot {
            print("Inventory:", entry.id, "rarity:", entry.rarity, "count:", entry.count, "stackLimit:", entry.stackLimit)
        }

        // 存档示例
        let player = PlayerState(
            merit: MeritState(gongde: 200, cap: 500, daily: 120, reserve: 150, yBuffer: 30),
            luck: LuckMapping(positiveScale: 500, negativeScale: 120).map(gongde: 200),
            backlash: BacklashState(points: 2),
            reserve: 150,
            yBuffer: 30,
            gachaPity: 0,
            legendaryPity: 0
        )
        let save = SaveState(player: player, world: WorldState(), shop: ShopState(coupons: 20, vipRate: 0.8))
        let url = URL(fileURLWithPath: "/tmp/dfc_save.json")
        let manager = SaveManager()
        do {
            try await manager.save(state: save, to: url)
            let loaded = try await manager.load(from: url)
            print("Save/Load OK:", loaded.player.merit.gongde, "coupons:", loaded.shop.coupons)
        } catch {
            print("Save/Load failed:", error)
        }
    }
}
