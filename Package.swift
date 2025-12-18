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
            path: "Sources/GameKernel"
        ),
        .executableTarget(
            name: "DivineFavoredCoupleApp",
            dependencies: ["GameKernel"],
            path: "Sources/DivineFavoredCoupleApp"
        ),
        .testTarget(
            name: "DivineFavoredCoupleTests",
            dependencies: ["GameKernel"],
            path: "Tests/DivineFavoredCoupleTests"
        )
    ]
)
