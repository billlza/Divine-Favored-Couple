import Foundation

/// 崩溃上报服务
/// 预留接口，支持后续接入 Sentry/Crashlytics/自建服务
@MainActor
public final class CrashReporter: ObservableObject {
    public static let shared = CrashReporter()

    public enum ReporterBackend: String, CaseIterable {
        case none = "None"
        case sentry = "Sentry"
        case crashlytics = "Crashlytics"
        case custom = "Custom"
    }

    @Published public var isEnabled: Bool = false
    @Published public var backend: ReporterBackend = .none
    @Published public var lastCrashDate: Date?
    @Published public var pendingReports: Int = 0

    private var crashLogPath: URL {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let crashDir = appSupport.appendingPathComponent("DivineFavoredCouple/CrashLogs", isDirectory: true)
        try? FileManager.default.createDirectory(at: crashDir, withIntermediateDirectories: true)
        return crashDir
    }

    private init() {
        setupExceptionHandler()
        setupSignalHandlers()
        loadPendingReports()
    }

    // MARK: - Configuration

    /// 配置崩溃上报后端
    public func configure(backend: ReporterBackend, apiKey: String? = nil, endpoint: URL? = nil) {
        self.backend = backend
        self.isEnabled = backend != .none

        switch backend {
        case .none:
            break
        case .sentry:
            // TODO: 接入 Sentry SDK
            // SentrySDK.start { options in
            //     options.dsn = apiKey
            // }
            print("[CrashReporter] Sentry backend configured (placeholder)")
        case .crashlytics:
            // TODO: 接入 Firebase Crashlytics
            // FirebaseApp.configure()
            print("[CrashReporter] Crashlytics backend configured (placeholder)")
        case .custom:
            // TODO: 接入自建服务
            print("[CrashReporter] Custom backend configured: \(endpoint?.absoluteString ?? "nil")")
        }
    }

    // MARK: - Exception Handling

    private func setupExceptionHandler() {
        NSSetUncaughtExceptionHandler { exception in
            CrashReporter.handleException(exception)
        }
    }

    private static func handleException(_ exception: NSException) {
        let crashInfo = CrashInfo(
            name: exception.name.rawValue,
            reason: exception.reason ?? "Unknown",
            callStack: exception.callStackSymbols,
            timestamp: Date(),
            appVersion: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "Unknown",
            osVersion: ProcessInfo.processInfo.operatingSystemVersionString,
            deviceModel: "Mac"
        )

        // 同步写入崩溃日志
        saveCrashLog(crashInfo)
    }

    private func setupSignalHandlers() {
        // 捕获常见信号
        let signals: [Int32] = [SIGABRT, SIGBUS, SIGFPE, SIGILL, SIGSEGV, SIGTRAP]

        for sig in signals {
            signal(sig) { signalNumber in
                let crashInfo = CrashInfo(
                    name: "Signal \(signalNumber)",
                    reason: CrashReporter.signalName(signalNumber),
                    callStack: Thread.callStackSymbols,
                    timestamp: Date(),
                    appVersion: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "Unknown",
                    osVersion: ProcessInfo.processInfo.operatingSystemVersionString,
                    deviceModel: "Mac"
                )

                CrashReporter.saveCrashLog(crashInfo)

                // 恢复默认处理
                signal(signalNumber, SIG_DFL)
                raise(signalNumber)
            }
        }
    }

    private static func signalName(_ signal: Int32) -> String {
        switch signal {
        case SIGABRT: return "SIGABRT (Abort)"
        case SIGBUS: return "SIGBUS (Bus Error)"
        case SIGFPE: return "SIGFPE (Floating Point Exception)"
        case SIGILL: return "SIGILL (Illegal Instruction)"
        case SIGSEGV: return "SIGSEGV (Segmentation Fault)"
        case SIGTRAP: return "SIGTRAP (Trace Trap)"
        default: return "Unknown Signal"
        }
    }

    // MARK: - Crash Log Management

    private static func saveCrashLog(_ info: CrashInfo) {
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let crashDir = appSupport.appendingPathComponent("DivineFavoredCouple/CrashLogs", isDirectory: true)
        try? FileManager.default.createDirectory(at: crashDir, withIntermediateDirectories: true)

        let filename = "crash_\(ISO8601DateFormatter().string(from: info.timestamp)).json"
        let fileURL = crashDir.appendingPathComponent(filename)

        if let data = try? JSONEncoder().encode(info) {
            try? data.write(to: fileURL, options: .atomic)
        }
    }

    private func loadPendingReports() {
        let fm = FileManager.default
        guard let files = try? fm.contentsOfDirectory(at: crashLogPath, includingPropertiesForKeys: nil) else {
            return
        }

        pendingReports = files.filter { $0.pathExtension == "json" }.count

        if let latestFile = files.sorted(by: { $0.lastPathComponent > $1.lastPathComponent }).first,
           let data = try? Data(contentsOf: latestFile),
           let info = try? JSONDecoder().decode(CrashInfo.self, from: data) {
            lastCrashDate = info.timestamp
        }
    }

    // MARK: - Report Submission

    /// 上传待处理的崩溃报告
    public func submitPendingReports() async {
        guard isEnabled, backend != .none else { return }

        let fm = FileManager.default
        guard let files = try? fm.contentsOfDirectory(at: crashLogPath, includingPropertiesForKeys: nil) else {
            return
        }

        for file in files where file.pathExtension == "json" {
            guard let data = try? Data(contentsOf: file),
                  let info = try? JSONDecoder().decode(CrashInfo.self, from: data) else {
                continue
            }

            let success = await submitReport(info)
            if success {
                try? fm.removeItem(at: file)
                pendingReports = max(0, pendingReports - 1)
            }
        }
    }

    private func submitReport(_ info: CrashInfo) async -> Bool {
        switch backend {
        case .none:
            return false
        case .sentry:
            // TODO: 实际调用 Sentry API
            print("[CrashReporter] Would submit to Sentry: \(info.name)")
            return true
        case .crashlytics:
            // TODO: 实际调用 Crashlytics API
            print("[CrashReporter] Would submit to Crashlytics: \(info.name)")
            return true
        case .custom:
            // TODO: 实际调用自建 API
            print("[CrashReporter] Would submit to custom endpoint: \(info.name)")
            return true
        }
    }

    // MARK: - Manual Reporting

    /// 手动记录非致命错误
    public func recordError(_ error: Error, context: [String: String] = [:]) {
        guard isEnabled else { return }

        let info = CrashInfo(
            name: "Non-Fatal Error",
            reason: error.localizedDescription,
            callStack: Thread.callStackSymbols,
            timestamp: Date(),
            appVersion: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "Unknown",
            osVersion: ProcessInfo.processInfo.operatingSystemVersionString,
            deviceModel: "Mac",
            context: context
        )

        Task {
            _ = await submitReport(info)
        }
    }

    /// 记录用户操作面包屑
    public func leaveBreadcrumb(_ message: String, category: String = "user") {
        guard isEnabled else { return }

        // TODO: 实际记录面包屑
        print("[CrashReporter] Breadcrumb [\(category)]: \(message)")
    }
}

// MARK: - Crash Info Model

struct CrashInfo: Codable {
    let name: String
    let reason: String
    let callStack: [String]
    let timestamp: Date
    let appVersion: String
    let osVersion: String
    let deviceModel: String
    var context: [String: String] = [:]
}
