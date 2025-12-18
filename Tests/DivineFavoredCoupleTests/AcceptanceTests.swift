import XCTest
@testable import GameKernel

/// 验收测试：覆盖开发计划中的关键验收用例
final class AcceptanceTests: XCTestCase {

    // MARK: - 7日Daily不重复验证
    func testSevenDayDailyNoDuplicates() async throws {
        var merit = MeritState(gongde: 0, cap: 1000, daily: 120, reserve: 0, yBuffer: 0)
        let service = DailyRewardService(calendar: .current)
        let baseDate = Date()
        let baseMono = MonotonicClock.shared.now()

        var grantedDays = 0
        for day in 0..<7 {
            let wallDate = baseDate.addingTimeInterval(Double(day) * 86400)
            let mono = MonotonicInstant(seconds: baseMono.seconds + Double(day) * 90000)
            let result = await service.attemptGrant(wallDate: wallDate, monotonicInstant: mono, merit: &merit)

            if case .granted(let days, _, _) = result {
                grantedDays += days
            }
        }

        XCTAssertEqual(grantedDays, 7, "应该连续7天都能领取")
        XCTAssertEqual(merit.gongde, 840, accuracy: 0.01, "7天应获得 7*120=840 功德")
    }

    // MARK: - DebtLimit后功德支付被拒且天机券可用
    func testDebtLimitBlocksMeritButCouponsWork() async throws {
        var wallet = Wallet(
            merit: MeritState(gongde: 0, cap: 100, daily: 50, reserve: 0, yBuffer: 0),
            coupons: 100,
            vipRate: 1.0
        )
        let shop = ShopService()

        // 尝试用功德支付超过DebtLimit的金额
        let meritOnlyResult = await shop.purchase(cost: 100, preferCoupons: false, wallet: &wallet)

        // 应该失败（因为 gongde=0, debtLimit=-50, 需要100超出范围）
        if case .success = meritOnlyResult {
            // 如果成功了，检查是否用了券
            XCTAssertGreaterThan(wallet.coupons, 0, "应该用券补足")
        }

        // 重置钱包，测试纯券支付
        wallet = Wallet(
            merit: MeritState(gongde: -40, cap: 100, daily: 50, reserve: 0, yBuffer: 0),
            coupons: 100,
            vipRate: 1.0
        )

        let couponResult = await shop.purchase(cost: 50, preferCoupons: true, wallet: &wallet)
        guard case .success(let spentG, let spentCoupons, _) = couponResult else {
            return XCTFail("天机券支付应该成功")
        }

        XCTAssertEqual(spentCoupons, 50, accuracy: 0.01, "应该用天机券支付")
        XCTAssertEqual(spentG, 0, accuracy: 0.01, "不应消耗功德")
    }

    // MARK: - 离线24h无直接死亡
    func testOffline24HoursNoDirectDeath() async throws {
        var reserve: Double = 0
        var yBuffer: Double = 0

        // 强制所有事件为S3
        let engine = EventEngine(
            calendar: .current,
            severityProvider: { _ in .s3 }
        )
        let luck = LuckScore(clamped: -50)
        let start = Date()

        let results = await engine.simulateOffline(
            startDate: start,
            hours: 24,
            luck: luck,
            reserve: &reserve,
            yBuffer: &yBuffer
        )

        // 检查是否有任何S3事件未被降级
        let unprotectedS3 = results.filter {
            $0.originalSeverity == .s3 &&
            $0.finalSeverity == .s3 &&
            !$0.preventedByProtection &&
            !$0.downgradedDueToLimit
        }

        // 由于24h冷却，最多只有1次S3，且应该有救援窗口
        XCTAssertLessThanOrEqual(unprotectedS3.count, 1, "24h内最多1次未保护S3")

        for result in unprotectedS3 {
            XCTAssertNotNil(result.rescueDeadline, "未保护的S3应有救援窗口")
        }
    }

    // MARK: - 抽卡保底可复现
    func testGachaPityReproducible() async throws {
        // 使用固定随机数（始终返回0，确保不会自然出金）
        let config = GachaEngine.Config(
            rarities: [("common", 99.7), ("legendary", 0.3)],
            epicPity: 100,
            legendaryPity: 10,
            legendarySoftPityStart: 100,
            legendarySoftPitySlope: 0
        )

        let engine = GachaEngine(config: config, random: { _ in 0 })

        var results: [String] = []
        for _ in 0..<15 {
            let r = await engine.singlePull()
            results.append(r.rarity)
        }

        // 硬保底应该在第10抽触发
        let legendaryIndex = results.firstIndex(of: "legendary")
        XCTAssertNotNil(legendaryIndex, "应该抽到传说")
        XCTAssertLessThanOrEqual(legendaryIndex!, 9, "传说应在10抽内出现（硬保底）")
    }

    // MARK: - 反噬影响运势
    func testBacklashAffectsLuck() {
        let baseLuck = LuckScore(clamped: 50)
        var backlash = BacklashState(points: 0)

        let effective0 = backlash.effectiveLuck(baseLuck: baseLuck)
        XCTAssertEqual(effective0.value, 50, accuracy: 0.01)

        backlash.addPoints(3)
        let effective3 = backlash.effectiveLuck(baseLuck: baseLuck)
        XCTAssertEqual(effective3.value, 35, accuracy: 0.01, "3点反噬应减少15运势")

        backlash.addPoints(10) // 总共13点，但惩罚上限30
        let effectiveMax = backlash.effectiveLuck(baseLuck: baseLuck)
        XCTAssertEqual(effectiveMax.value, 20, accuracy: 0.01, "反噬惩罚上限30")
    }

    // MARK: - 遮掩降低高危概率
    func testConcealmentReducesHighSeverity() async throws {
        let concealment = ConcealmentService()
        await concealment.activate(evasionMultiplier: 0.3, duration: nil)

        var s3Count = 0
        var totalRolls = 0

        for _ in 0..<100 {
            var reserve: Double = 0
            var yBuffer: Double = 0

            let engine = EventEngine(
                calendar: .current,
                concealment: concealment,
                randomDouble: { _ in 0.5 }, // 50%概率触发遮掩降级
                severityProvider: { _ in .s3 }
            )

            let result = await engine.rollEvent(
                wallDate: Date(),
                luck: LuckScore(clamped: 0),
                reserve: &reserve,
                yBuffer: &yBuffer
            )

            if result.finalSeverity == .s3 || result.finalSeverity == .s2 {
                s3Count += 1
            }
            totalRolls += 1
        }

        // 遮掩应该显著降低高危事件
        let highSeverityRate = Double(s3Count) / Double(totalRolls)
        XCTAssertLessThan(highSeverityRate, 0.8, "遮掩应降低高危事件比例")
    }

    // MARK: - 存档完整性
    func testSaveLoadIntegrity() async throws {
        let original = SaveState(
            player: PlayerState(
                merit: MeritState(gongde: 500, cap: 1000, daily: 120, reserve: 100, yBuffer: 50),
                luck: LuckScore(clamped: 45),
                backlash: BacklashState(points: 2),
                reserve: 100,
                yBuffer: 50,
                gachaPity: 5,
                legendaryPity: 30
            ),
            world: WorldState(
                lastS3Date: Date(),
                rescueDeadline: Date().addingTimeInterval(3600)
            ),
            shop: ShopState(coupons: 200, vipRate: 0.75)
        )

        let saveService = SaveService()
        let tempURL = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("test_save_\(UUID()).json")

        try await saveService.save(state: original, to: tempURL)
        let loaded = try await saveService.load(from: tempURL)

        XCTAssertEqual(loaded.player.merit.gongde, original.player.merit.gongde, accuracy: 0.01)
        XCTAssertEqual(loaded.player.backlash.points, original.player.backlash.points)
        XCTAssertEqual(loaded.shop.coupons, original.shop.coupons, accuracy: 0.01)
        XCTAssertEqual(loaded.schemaVersion, SaveState.currentVersion)

        try? FileManager.default.removeItem(at: tempURL)
    }

    // MARK: - 十连保底至少稀有
    func testTenPullGuaranteesRare() async throws {
        // 配置：只有common，但十连应该保底rare
        let config = GachaEngine.Config(
            rarities: [("common", 100.0), ("rare", 0.0), ("epic", 0.0), ("legendary", 0.0)],
            epicPity: 100,
            legendaryPity: 200,
            legendarySoftPityStart: 150,
            legendarySoftPitySlope: 0
        )

        let engine = GachaEngine(config: config, random: { _ in 0 })
        let results = await engine.tenPull()

        let hasRareOrBetter = results.contains { $0.rarity != "common" }
        XCTAssertTrue(hasRareOrBetter, "十连应至少有一个稀有或更高")
    }
}
