import Foundation
import SQLite3

/// SQLite + WAL 存档管理器
/// 遵循开发计划要求：原子写入 + 回滚点 + schemaVersion + migration
public actor SQLiteSaveManager {
    public static let schemaVersion = 1

    public enum SaveError: Error, CustomStringConvertible {
        case databaseOpenFailed(String)
        case migrationFailed(String)
        case saveFailed(String)
        case loadFailed(String)
        case rollbackFailed(String)

        public var description: String {
            switch self {
            case .databaseOpenFailed(let msg): return "Database open failed: \(msg)"
            case .migrationFailed(let msg): return "Migration failed: \(msg)"
            case .saveFailed(let msg): return "Save failed: \(msg)"
            case .loadFailed(let msg): return "Load failed: \(msg)"
            case .rollbackFailed(let msg): return "Rollback failed: \(msg)"
            }
        }
    }

    private var db: OpaquePointer?
    private let dbPath: String

    public init(dbPath: String) {
        self.dbPath = dbPath
    }

    deinit {
        if let db = db {
            sqlite3_close(db)
        }
    }

    /// 打开数据库并启用 WAL 模式
    public func open() throws {
        var dbPointer: OpaquePointer?
        let result = sqlite3_open(dbPath, &dbPointer)

        guard result == SQLITE_OK, let dbPointer else {
            let errorMsg = String(cString: sqlite3_errmsg(dbPointer))
            throw SaveError.databaseOpenFailed(errorMsg)
        }

        db = dbPointer

        // 启用 WAL 模式
        try execute("PRAGMA journal_mode=WAL;")
        try execute("PRAGMA synchronous=NORMAL;")

        // 创建表结构
        try createTables()

        // 执行迁移
        try migrate()
    }

    /// 创建表结构
    private func createTables() throws {
        let createSQL = """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS player_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            gongde REAL NOT NULL DEFAULT 0,
            cap REAL NOT NULL DEFAULT 1000,
            daily REAL NOT NULL DEFAULT 120,
            reserve REAL NOT NULL DEFAULT 0,
            y_buffer REAL NOT NULL DEFAULT 0,
            luck_value REAL NOT NULL DEFAULT 0,
            backlash_points INTEGER NOT NULL DEFAULT 0,
            gacha_pity INTEGER NOT NULL DEFAULT 0,
            legendary_pity INTEGER NOT NULL DEFAULT 0,
            character_name TEXT NOT NULL DEFAULT '李清然',
            character_mood REAL NOT NULL DEFAULT 1.0,
            character_hp REAL NOT NULL DEFAULT 1.0,
            equipment_slots INTEGER NOT NULL DEFAULT 4,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS world_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_s3_date TEXT,
            rescue_deadline TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS shop_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            coupons REAL NOT NULL DEFAULT 0,
            vip_rate REAL NOT NULL DEFAULT 0.8,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS event_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            original_severity TEXT NOT NULL,
            final_severity TEXT NOT NULL,
            rescue_deadline TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT NOT NULL,
            rarity TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 1,
            stack_limit INTEGER NOT NULL DEFAULT 99,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_inventory_item_id ON inventory(item_id);
        CREATE INDEX IF NOT EXISTS idx_event_reports_timestamp ON event_reports(timestamp);
        """

        try execute(createSQL)
    }

    /// 数据库迁移
    private func migrate() throws {
        let currentVersion = try getSchemaVersion()

        if currentVersion < Self.schemaVersion {
            // 执行迁移
            for version in (currentVersion + 1)...Self.schemaVersion {
                try applyMigration(version: version)
            }
            try setSchemaVersion(Self.schemaVersion)
        }
    }

    private func getSchemaVersion() throws -> Int {
        let sql = "SELECT value FROM meta WHERE key = 'schema_version';"
        var stmt: OpaquePointer?

        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            // 表可能不存在，返回 0
            return 0
        }

        defer { sqlite3_finalize(stmt) }

        if sqlite3_step(stmt) == SQLITE_ROW {
            let value = String(cString: sqlite3_column_text(stmt, 0))
            return Int(value) ?? 0
        }

        return 0
    }

    private func setSchemaVersion(_ version: Int) throws {
        let sql = "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', '\(version)');"
        try execute(sql)
    }

    private func applyMigration(version: Int) throws {
        switch version {
        case 1:
            // 初始版本，无需迁移
            break
        default:
            throw SaveError.migrationFailed("Unknown migration version: \(version)")
        }
    }

    /// 保存游戏状态（带事务和回滚点）
    public func save(state: SaveState) throws {
        guard let db else {
            throw SaveError.saveFailed("Database not opened")
        }

        // 开始事务
        try execute("BEGIN TRANSACTION;")

        // 创建回滚点
        try execute("SAVEPOINT save_checkpoint;")

        do {
            // 保存玩家状态
            try savePlayerState(state.player)

            // 保存世界状态
            try saveWorldState(state.world)

            // 保存商店状态
            try saveShopState(state.shop)

            // 保存事件报告
            try saveEventReports(state.world.reports)

            // 提交事务
            try execute("COMMIT;")
        } catch {
            // 回滚到检查点
            try? execute("ROLLBACK TO SAVEPOINT save_checkpoint;")
            try? execute("ROLLBACK;")
            throw SaveError.saveFailed(error.localizedDescription)
        }
    }

    private func savePlayerState(_ player: PlayerState) throws {
        let sql = """
        INSERT OR REPLACE INTO player_state (
            id, gongde, cap, daily, reserve, y_buffer, luck_value,
            backlash_points, gacha_pity, legendary_pity,
            character_name, character_mood, character_hp, equipment_slots, updated_at
        ) VALUES (
            1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now')
        );
        """

        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw SaveError.saveFailed("Failed to prepare player state")
        }
        defer { sqlite3_finalize(stmt) }

        sqlite3_bind_double(stmt, 1, player.merit.gongde)
        sqlite3_bind_double(stmt, 2, player.merit.cap)
        sqlite3_bind_double(stmt, 3, player.merit.daily)
        sqlite3_bind_double(stmt, 4, player.reserve)
        sqlite3_bind_double(stmt, 5, player.yBuffer)
        sqlite3_bind_double(stmt, 6, player.luck.value)
        sqlite3_bind_int(stmt, 7, Int32(player.backlash.points))
        sqlite3_bind_int(stmt, 8, Int32(player.gachaPity))
        sqlite3_bind_int(stmt, 9, Int32(player.legendaryPity))
        sqlite3_bind_text(stmt, 10, player.character.name, -1, nil)
        sqlite3_bind_double(stmt, 11, player.character.mood)
        sqlite3_bind_double(stmt, 12, player.character.hp)
        sqlite3_bind_int(stmt, 13, Int32(player.character.equipmentSlots))

        guard sqlite3_step(stmt) == SQLITE_DONE else {
            throw SaveError.saveFailed("Failed to save player state")
        }
    }

    private func saveWorldState(_ world: WorldState) throws {
        let sql = """
        INSERT OR REPLACE INTO world_state (id, last_s3_date, rescue_deadline, updated_at)
        VALUES (1, ?, ?, datetime('now'));
        """

        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw SaveError.saveFailed("Failed to prepare world state")
        }
        defer { sqlite3_finalize(stmt) }

        if let date = world.lastS3Date {
            sqlite3_bind_text(stmt, 1, ISO8601DateFormatter().string(from: date), -1, nil)
        } else {
            sqlite3_bind_null(stmt, 1)
        }

        if let deadline = world.rescueDeadline {
            sqlite3_bind_text(stmt, 2, ISO8601DateFormatter().string(from: deadline), -1, nil)
        } else {
            sqlite3_bind_null(stmt, 2)
        }

        guard sqlite3_step(stmt) == SQLITE_DONE else {
            throw SaveError.saveFailed("Failed to save world state")
        }
    }

    private func saveShopState(_ shop: ShopState) throws {
        let sql = """
        INSERT OR REPLACE INTO shop_state (id, coupons, vip_rate, updated_at)
        VALUES (1, ?, ?, datetime('now'));
        """

        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw SaveError.saveFailed("Failed to prepare shop state")
        }
        defer { sqlite3_finalize(stmt) }

        sqlite3_bind_double(stmt, 1, shop.coupons)
        sqlite3_bind_double(stmt, 2, shop.vipRate)

        guard sqlite3_step(stmt) == SQLITE_DONE else {
            throw SaveError.saveFailed("Failed to save shop state")
        }
    }

    private func saveEventReports(_ reports: [EventReport]) throws {
        // 清除旧报告，保留最近 100 条
        try execute("DELETE FROM event_reports WHERE id NOT IN (SELECT id FROM event_reports ORDER BY timestamp DESC LIMIT 100);")

        let sql = """
        INSERT INTO event_reports (timestamp, original_severity, final_severity, rescue_deadline)
        VALUES (?, ?, ?, ?);
        """

        for report in reports.suffix(100) {
            var stmt: OpaquePointer?
            guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
                continue
            }
            defer { sqlite3_finalize(stmt) }

            sqlite3_bind_text(stmt, 1, ISO8601DateFormatter().string(from: report.timestamp), -1, nil)
            sqlite3_bind_text(stmt, 2, report.original.rawValue, -1, nil)
            sqlite3_bind_text(stmt, 3, report.final.rawValue, -1, nil)

            if let deadline = report.rescueDeadline {
                sqlite3_bind_text(stmt, 4, ISO8601DateFormatter().string(from: deadline), -1, nil)
            } else {
                sqlite3_bind_null(stmt, 4)
            }

            _ = sqlite3_step(stmt)
        }
    }

    /// 加载游戏状态
    public func load() throws -> SaveState {
        guard db != nil else {
            throw SaveError.loadFailed("Database not opened")
        }

        let player = try loadPlayerState()
        let world = try loadWorldState()
        let shop = try loadShopState()

        return SaveState(
            schemaVersion: Self.schemaVersion,
            player: player,
            world: world,
            shop: shop
        )
    }

    private func loadPlayerState() throws -> PlayerState {
        let sql = "SELECT * FROM player_state WHERE id = 1;"
        var stmt: OpaquePointer?

        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            return PlayerState()
        }
        defer { sqlite3_finalize(stmt) }

        guard sqlite3_step(stmt) == SQLITE_ROW else {
            return PlayerState()
        }

        let merit = MeritState(
            gongde: sqlite3_column_double(stmt, 1),
            cap: sqlite3_column_double(stmt, 2),
            daily: sqlite3_column_double(stmt, 3),
            reserve: sqlite3_column_double(stmt, 4),
            yBuffer: sqlite3_column_double(stmt, 5)
        )

        let luck = LuckScore(clamped: sqlite3_column_double(stmt, 6))
        let backlash = BacklashState(points: Int(sqlite3_column_int(stmt, 7)))

        let character = CharacterState(
            name: String(cString: sqlite3_column_text(stmt, 10)),
            mood: sqlite3_column_double(stmt, 11),
            hp: sqlite3_column_double(stmt, 12),
            equipmentSlots: Int(sqlite3_column_int(stmt, 13))
        )

        return PlayerState(
            merit: merit,
            luck: luck,
            backlash: backlash,
            reserve: sqlite3_column_double(stmt, 4),
            yBuffer: sqlite3_column_double(stmt, 5),
            gachaPity: Int(sqlite3_column_int(stmt, 8)),
            legendaryPity: Int(sqlite3_column_int(stmt, 9)),
            character: character
        )
    }

    private func loadWorldState() throws -> WorldState {
        let sql = "SELECT * FROM world_state WHERE id = 1;"
        var stmt: OpaquePointer?

        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            return WorldState()
        }
        defer { sqlite3_finalize(stmt) }

        guard sqlite3_step(stmt) == SQLITE_ROW else {
            return WorldState()
        }

        let formatter = ISO8601DateFormatter()
        var lastS3Date: Date?
        var rescueDeadline: Date?

        if sqlite3_column_type(stmt, 1) != SQLITE_NULL {
            lastS3Date = formatter.date(from: String(cString: sqlite3_column_text(stmt, 1)))
        }

        if sqlite3_column_type(stmt, 2) != SQLITE_NULL {
            rescueDeadline = formatter.date(from: String(cString: sqlite3_column_text(stmt, 2)))
        }

        let reports = try loadEventReports()

        return WorldState(
            lastS3Date: lastS3Date,
            rescueDeadline: rescueDeadline,
            reports: reports
        )
    }

    private func loadShopState() throws -> ShopState {
        let sql = "SELECT * FROM shop_state WHERE id = 1;"
        var stmt: OpaquePointer?

        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            return ShopState()
        }
        defer { sqlite3_finalize(stmt) }

        guard sqlite3_step(stmt) == SQLITE_ROW else {
            return ShopState()
        }

        return ShopState(
            coupons: sqlite3_column_double(stmt, 1),
            vipRate: sqlite3_column_double(stmt, 2)
        )
    }

    private func loadEventReports() throws -> [EventReport] {
        let sql = "SELECT timestamp, original_severity, final_severity, rescue_deadline FROM event_reports ORDER BY timestamp DESC LIMIT 100;"
        var stmt: OpaquePointer?

        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else {
            return []
        }
        defer { sqlite3_finalize(stmt) }

        var reports: [EventReport] = []
        let formatter = ISO8601DateFormatter()

        while sqlite3_step(stmt) == SQLITE_ROW {
            guard let timestamp = formatter.date(from: String(cString: sqlite3_column_text(stmt, 0))),
                  let original = EventSeverity(rawValue: String(cString: sqlite3_column_text(stmt, 1))),
                  let final = EventSeverity(rawValue: String(cString: sqlite3_column_text(stmt, 2))) else {
                continue
            }

            var rescueDeadline: Date?
            if sqlite3_column_type(stmt, 3) != SQLITE_NULL {
                rescueDeadline = formatter.date(from: String(cString: sqlite3_column_text(stmt, 3)))
            }

            reports.append(EventReport(
                timestamp: timestamp,
                original: original,
                final: final,
                rescueDeadline: rescueDeadline
            ))
        }

        return reports.reversed()
    }

    /// 执行 SQL
    private func execute(_ sql: String) throws {
        var errorMsg: UnsafeMutablePointer<CChar>?
        let result = sqlite3_exec(db, sql, nil, nil, &errorMsg)

        if result != SQLITE_OK {
            let msg = errorMsg.map { String(cString: $0) } ?? "Unknown error"
            sqlite3_free(errorMsg)
            throw SaveError.saveFailed(msg)
        }
    }

    /// 创建备份
    public func backup(to backupPath: String) throws {
        guard let db else {
            throw SaveError.saveFailed("Database not opened")
        }

        var backupDb: OpaquePointer?
        guard sqlite3_open(backupPath, &backupDb) == SQLITE_OK else {
            throw SaveError.saveFailed("Failed to open backup database")
        }
        defer { sqlite3_close(backupDb) }

        guard let backup = sqlite3_backup_init(backupDb, "main", db, "main") else {
            throw SaveError.saveFailed("Failed to initialize backup")
        }

        sqlite3_backup_step(backup, -1)
        sqlite3_backup_finish(backup)
    }
}
