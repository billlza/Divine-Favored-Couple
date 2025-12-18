import AVFoundation

/// 音效服务：管理游戏音效播放
@MainActor
final class AudioService: ObservableObject {
    static let shared = AudioService()

    @Published var isMuted: Bool = false
    @Published var volume: Float = 0.8

    private var audioPlayers: [String: AVAudioPlayer] = [:]

    private init() {}

    /// 预加载音效
    func preload(soundName: String, fileExtension: String = "wav") {
        guard let url = Bundle.main.url(forResource: soundName, withExtension: fileExtension) else {
            print("Audio file not found: \(soundName).\(fileExtension)")
            return
        }

        do {
            let player = try AVAudioPlayer(contentsOf: url)
            player.prepareToPlay()
            player.volume = volume
            audioPlayers[soundName] = player
        } catch {
            print("Failed to load audio: \(error)")
        }
    }

    /// 播放音效
    func play(_ soundName: String) {
        guard !isMuted else { return }

        if let player = audioPlayers[soundName] {
            player.volume = volume
            player.currentTime = 0
            player.play()
        } else {
            // 尝试即时加载
            preload(soundName: soundName)
            audioPlayers[soundName]?.play()
        }
    }

    /// 播放抽卡音效
    func playGachaSound(rarity: String) {
        switch rarity {
        case "legendary":
            play("gacha_legendary")
        case "epic":
            play("gacha_epic")
        case "rare":
            play("gacha_rare")
        default:
            play("gacha_common")
        }
    }

    /// 播放UI音效
    func playUISound(_ type: UISoundType) {
        play(type.rawValue)
    }

    /// 停止所有音效
    func stopAll() {
        audioPlayers.values.forEach { $0.stop() }
    }

    /// 设置音量
    func setVolume(_ newVolume: Float) {
        volume = max(0, min(1, newVolume))
        audioPlayers.values.forEach { $0.volume = volume }
    }
}

/// UI 音效类型
enum UISoundType: String {
    case buttonClick = "ui_click"
    case tabSwitch = "ui_tab"
    case purchase = "ui_purchase"
    case dailyClaim = "ui_daily"
    case eventAlert = "ui_alert"
    case success = "ui_success"
    case failure = "ui_failure"
}
