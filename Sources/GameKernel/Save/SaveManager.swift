import Foundation

/// 负责存档的原子写入、读取与回滚。
public actor SaveManager {
    public enum SaveError: Error {
        case encodingFailed
        case ioFailed
    }

    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    public init() {
        encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        decoder = JSONDecoder()
    }

    /// 原子写入：写入临时文件后 replaceItemAt。
    public func save(state: SaveState, to url: URL) async throws {
        guard let data = try? encoder.encode(state) else {
            throw SaveError.encodingFailed
        }
        let fm = FileManager.default
        let tempURL = url.appendingPathExtension("tmp")
        do {
            try data.write(to: tempURL, options: .atomic)
            _ = try fm.replaceItemAt(url, withItemAt: tempURL, backupItemName: url.lastPathComponent + ".bak", options: .usingNewMetadataOnly)
        } catch {
            throw SaveError.ioFailed
        }
    }

    /// 读取存档，若失败尝试回滚到 .bak。
    public func load(from url: URL) async throws -> SaveState {
        let fm = FileManager.default
        do {
            let data = try Data(contentsOf: url)
            return try decoder.decode(SaveState.self, from: data)
        } catch {
            let backupURL = url.deletingPathExtension().appendingPathExtension("bak")
            guard fm.fileExists(atPath: backupURL.path) else { throw error }
            let data = try Data(contentsOf: backupURL)
            return try decoder.decode(SaveState.self, from: data)
        }
    }
}
