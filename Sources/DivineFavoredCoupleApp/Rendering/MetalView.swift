import SwiftUI
import MetalKit

/// Metal 渲染视图的 SwiftUI 包装
struct MetalView: NSViewRepresentable {
    @Binding var isRendering: Bool

    func makeNSView(context: Context) -> MTKView {
        let mtkView = MTKView()
        mtkView.device = MTLCreateSystemDefaultDevice()
        mtkView.delegate = context.coordinator
        mtkView.clearColor = MTLClearColor(red: 0.1, green: 0.1, blue: 0.15, alpha: 1.0)
        mtkView.colorPixelFormat = .bgra8Unorm
        mtkView.depthStencilPixelFormat = .depth32Float
        mtkView.preferredFramesPerSecond = 60
        mtkView.enableSetNeedsDisplay = false
        mtkView.isPaused = !isRendering
        return mtkView
    }

    func updateNSView(_ nsView: MTKView, context: Context) {
        nsView.isPaused = !isRendering
    }

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    class Coordinator: NSObject, MTKViewDelegate {
        private var renderer: MetalRenderer?

        override init() {
            super.init()
        }

        func mtkView(_ view: MTKView, drawableSizeWillChange size: CGSize) {
            if renderer == nil, let device = view.device {
                renderer = MetalRenderer(device: device, pixelFormat: view.colorPixelFormat)
            }
            renderer?.resize(to: size)
        }

        func draw(in view: MTKView) {
            guard let renderer = renderer,
                  let drawable = view.currentDrawable,
                  let descriptor = view.currentRenderPassDescriptor else {
                return
            }
            renderer.render(drawable: drawable, descriptor: descriptor)
        }
    }
}

/// Metal 渲染器
final class MetalRenderer {
    private let device: MTLDevice
    private let commandQueue: MTLCommandQueue
    private let pipelineState: MTLRenderPipelineState?
    private var viewportSize: CGSize = .zero

    init(device: MTLDevice, pixelFormat: MTLPixelFormat) {
        self.device = device
        self.commandQueue = device.makeCommandQueue()!

        // 创建渲染管线
        let library = device.makeDefaultLibrary()
        let pipelineDescriptor = MTLRenderPipelineDescriptor()
        pipelineDescriptor.vertexFunction = library?.makeFunction(name: "vertexShader")
        pipelineDescriptor.fragmentFunction = library?.makeFunction(name: "fragmentShader")
        pipelineDescriptor.colorAttachments[0].pixelFormat = pixelFormat
        pipelineDescriptor.depthAttachmentPixelFormat = .depth32Float

        self.pipelineState = try? device.makeRenderPipelineState(descriptor: pipelineDescriptor)
    }

    func resize(to size: CGSize) {
        viewportSize = size
    }

    func render(drawable: CAMetalDrawable, descriptor: MTLRenderPassDescriptor) {
        guard let commandBuffer = commandQueue.makeCommandBuffer(),
              let encoder = commandBuffer.makeRenderCommandEncoder(descriptor: descriptor) else {
            return
        }

        // 设置视口
        encoder.setViewport(MTLViewport(
            originX: 0, originY: 0,
            width: viewportSize.width, height: viewportSize.height,
            znear: 0, zfar: 1
        ))

        // TODO: 绘制场景
        // 当前仅清屏，后续添加实际渲染逻辑

        encoder.endEncoding()
        commandBuffer.present(drawable)
        commandBuffer.commit()
    }
}
