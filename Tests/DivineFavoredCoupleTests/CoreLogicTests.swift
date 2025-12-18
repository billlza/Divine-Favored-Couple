import XCTest
@testable import GameKernel

final class CoreLogicTests: XCTestCase {
    func testShopUsesCouponsWhenPreferred() async throws {
        var wallet = Wallet(merit: MeritState(gongde: 0, cap: 50, daily: 100, reserve: 0, yBuffer: 0), coupons: 100, vipRate: 1.0)
        let shop = ShopService()

        let result = await shop.purchase(cost: 30, preferCoupons: true, wallet: &wallet)

        guard case .success(let spentG, let spentCoupons, _) = result else {
            return XCTFail("Expected success, got \(result)")
        }
        XCTAssertEqual(spentG, 0, accuracy: 0.0001)
        XCTAssertEqual(spentCoupons, 30, accuracy: 0.0001)
        XCTAssertEqual(wallet.merit.gongde, 0, accuracy: 0.0001)
    }

    func testAuguryBacklashClamp() {
        var backlash = BacklashState(points: 10)
        XCTAssertEqual(backlash.luckPenalty, 30, accuracy: 0.0001)

        let baseLuck = LuckScore(clamped: 20)
        let effective = backlash.effectiveLuck(baseLuck: baseLuck)
        XCTAssertEqual(effective.value, -10, accuracy: 0.0001)

        backlash.cleanse(by: 5)
        XCTAssertEqual(backlash.points, 5)
        XCTAssertLessThan(backlash.luckPenalty, 30)
    }

    func testDailyGrantBackwardDetection() async throws {
        let service = DailyRewardService(calendar: .current)
        var merit = MeritState()
        let now = Date()
        let mono = MonotonicClock.shared.now()

        _ = await service.attemptGrant(wallDate: now, monotonicInstant: mono, merit: &merit)
        let backward = await service.attemptGrant(wallDate: now.addingTimeInterval(-86_400), monotonicInstant: mono, merit: &merit)
        XCTAssertEqual(backward, .backwardTimeDetected)
    }

    func testGachaLegendaryHardPity() async throws {
        let config = GachaEngine.Config(
            rarities: [("common", 1.0), ("legendary", 0.0)],
            epicPity: 5,
            legendaryPity: 10,
            legendarySoftPityStart: 100,
            legendarySoftPitySlope: 0
        )
        let engine = GachaEngine(config: config, random: { _ in 0 })

        var legendaryFound = false
        for i in 1...10 {
            let result = await engine.singlePull()
            if result.rarity == "legendary" {
                legendaryFound = true
                XCTAssertGreaterThanOrEqual(i, 9)
                break
            }
        }
        XCTAssertTrue(legendaryFound, "Legendary should appear due to hard pity by the 10th pull.")
    }

    func testEventEngineS3LimitAndProtection() async throws {
        var reserve: Double = 200
        var y: Double = 150
        let engine = EventEngine(calendar: .current, severityProvider: { _ in .s3 })
        let luck = LuckScore(clamped: 0)
        let start = Date()

        // First S3 should consume reserve
        let first = await engine.rollEvent(wallDate: start, luck: luck, reserve: &reserve, yBuffer: &y)
        XCTAssertEqual(first.originalSeverity, .s3)
        XCTAssertTrue(first.preventedByProtection)
        XCTAssertLessThan(reserve, 200)

        // Next hour still within 24h -> downgraded to S2
        let second = await engine.rollEvent(
            wallDate: start.addingTimeInterval(3600),
            luck: luck,
            reserve: &reserve,
            yBuffer: &y
        )
        XCTAssertEqual(second.originalSeverity, .s3)
        XCTAssertEqual(second.finalSeverity, .s2)
    }
}
