#include <metal_stdlib>
using namespace metal;

/// 顶点输入结构
struct VertexIn {
    float3 position [[attribute(0)]];
    float2 texCoord [[attribute(1)]];
    float4 color [[attribute(2)]];
};

/// 顶点输出/片段输入结构
struct VertexOut {
    float4 position [[position]];
    float2 texCoord;
    float4 color;
};

/// 统一变量
struct Uniforms {
    float4x4 modelViewProjection;
    float time;
    float2 resolution;
};

/// 顶点着色器
vertex VertexOut vertexShader(
    VertexIn in [[stage_in]],
    constant Uniforms& uniforms [[buffer(1)]]
) {
    VertexOut out;
    out.position = uniforms.modelViewProjection * float4(in.position, 1.0);
    out.texCoord = in.texCoord;
    out.color = in.color;
    return out;
}

/// 片段着色器
fragment float4 fragmentShader(
    VertexOut in [[stage_in]],
    texture2d<float> texture [[texture(0)]],
    sampler textureSampler [[sampler(0)]]
) {
    float4 texColor = texture.sample(textureSampler, in.texCoord);
    return texColor * in.color;
}

/// 简单的全屏四边形顶点着色器（用于后处理）
vertex VertexOut fullscreenQuadVertex(uint vertexID [[vertex_id]]) {
    VertexOut out;

    // 生成全屏四边形的顶点
    float2 positions[4] = {
        float2(-1.0, -1.0),
        float2( 1.0, -1.0),
        float2(-1.0,  1.0),
        float2( 1.0,  1.0)
    };

    float2 texCoords[4] = {
        float2(0.0, 1.0),
        float2(1.0, 1.0),
        float2(0.0, 0.0),
        float2(1.0, 0.0)
    };

    out.position = float4(positions[vertexID], 0.0, 1.0);
    out.texCoord = texCoords[vertexID];
    out.color = float4(1.0);

    return out;
}

/// 发光效果片段着色器（用于抽卡出金演出）
fragment float4 glowFragmentShader(
    VertexOut in [[stage_in]],
    constant Uniforms& uniforms [[buffer(0)]]
) {
    float2 uv = in.texCoord;
    float2 center = float2(0.5, 0.5);
    float dist = distance(uv, center);

    // 脉冲发光效果
    float pulse = sin(uniforms.time * 3.0) * 0.5 + 0.5;
    float glow = smoothstep(0.5, 0.0, dist) * pulse;

    // 金色渐变
    float3 goldColor = mix(
        float3(1.0, 0.8, 0.2),
        float3(1.0, 0.6, 0.0),
        dist
    );

    return float4(goldColor * glow, glow);
}

/// 遮掩效果片段着色器
fragment float4 concealmentFragmentShader(
    VertexOut in [[stage_in]],
    constant Uniforms& uniforms [[buffer(0)]]
) {
    float2 uv = in.texCoord;

    // 波纹效果
    float wave = sin(uv.x * 20.0 + uniforms.time * 2.0) * 0.02;
    wave += sin(uv.y * 15.0 + uniforms.time * 1.5) * 0.02;

    // 紫色迷雾
    float3 mistColor = float3(0.4, 0.2, 0.6);
    float alpha = 0.3 + wave;

    return float4(mistColor, alpha);
}
