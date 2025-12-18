// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "DivineFavoredCouple",
    platforms: [
        .macOS(.v15)
    ],
    products: [
        .executable(
            name: "DivineFavoredCoupleApp",
            targets: ["DivineFavoredCoupleApp"]
        ),
        .library(
            name: "GameKernel",
            targets: ["GameKernel"]
        )
    ],
    targets: [
        .target(
            name: "GameKernel",
            path: "Sources/GameKernel",
            resources: [
                .process("Config")
            ],
            swiftSettings: [
                .swiftLanguageMode(.v6)
            ]
        ),
        .executableTarget(
            name: "DivineFavoredCoupleApp",
            dependencies: ["GameKernel"],
            path: "Sources/DivineFavoredCoupleApp",
            resources: [
                .process("Rendering/Shaders.metal")
            ],
            swiftSettings: [
                .swiftLanguageMode(.v6)
            ]
        ),
        .testTarget(
            name: "DivineFavoredCoupleTests",
            dependencies: ["GameKernel"],
            path: "Tests/DivineFavoredCoupleTests",
            swiftSettings: [
                .swiftLanguageMode(.v6)
            ]
        )
    ]
)
