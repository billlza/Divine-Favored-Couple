"""Daylight, volumetric cloud bands, and review cameras."""

from dataclasses import dataclass
import math

import bpy
from mathutils import Vector

from architecture import box
from landscape import camera, group


@dataclass(frozen=True)
class CloudBand:
    elevation: float
    half_depth: float
    density: float


@dataclass(frozen=True)
class ClearAir:
    center: tuple[float, float]
    inner_radius: float
    outer_radius: float


def range_node(nodes, links, value, start, stop, low=0, high=1):
    node = nodes.new("ShaderNodeMapRange")
    node.interpolation_type = "SMOOTHERSTEP"
    for name, setting in (("From Min", start), ("From Max", stop),
                          ("To Min", low), ("To Max", high)):
        node.inputs[name].default_value = setting
    links.new(value, node.inputs["Value"])
    return node.outputs["Result"]


def math_output(nodes, links, operation, left, right=None):
    node = nodes.new("ShaderNodeMath")
    node.operation = operation
    for socket, value in zip(node.inputs, (left, right)):
        if isinstance(value, (float, int)):
            socket.default_value = value
        elif value is not None:
            links.new(value, socket)
    return node.outputs[0]


def daylight(scene, direction):
    scene.world = bpy.data.worlds.new("Mountain daylight and sky")
    nodes, links = scene.world.node_tree.nodes, scene.world.node_tree.links
    nodes.clear()
    ambient = nodes.new("ShaderNodeBackground")
    ambient.inputs["Color"].default_value = (.57, .70, .90, 1)
    ambient.inputs["Strength"].default_value = .54

    sky = nodes.new("ShaderNodeTexSky")
    sky.sky_type = "HOSEK_WILKIE"
    sky.sun_direction = direction
    sky.turbidity = 3.0
    sky_coords = nodes.new("ShaderNodeTexCoord")
    stretch = nodes.new("ShaderNodeVectorMath")
    stretch.operation = "MULTIPLY"
    stretch.inputs[1].default_value = (2.0, 2.0, 7.9)
    links.new(sky_coords.outputs["Normal"], stretch.inputs[0])
    wisps = nodes.new("ShaderNodeTexNoise")
    wisps.inputs["Scale"].default_value = 2.8
    wisps.inputs["Detail"].default_value = 3.0
    links.new(stretch.outputs[0], wisps.inputs["Vector"])
    cover = range_node(nodes, links, wisps.outputs["Fac"], .49, .74, 0, .69)
    atmosphere = nodes.new("ShaderNodeMixRGB")
    atmosphere.inputs[2].default_value = (.84, .76, .69, 1)
    links.new(cover, atmosphere.inputs[0])
    links.new(sky.outputs["Color"], atmosphere.inputs[1])
    visible = nodes.new("ShaderNodeBackground")
    visible.inputs["Strength"].default_value = .78
    links.new(atmosphere.outputs[0], visible.inputs["Color"])

    path = nodes.new("ShaderNodeLightPath")
    background = nodes.new("ShaderNodeMixShader")
    links.new(path.outputs["Is Camera Ray"], background.inputs[0])
    links.new(ambient.outputs[0], background.inputs[1])
    links.new(visible.outputs[0], background.inputs[2])
    output = nodes.new("ShaderNodeOutputWorld")
    links.new(background.outputs[0], output.inputs["Surface"])


def cloud_volume(lights, center, bands, clearing):
    material = bpy.data.materials.new("Cloud banks and distance haze")
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    world = nodes.new("ShaderNodeNewGeometry").outputs["Position"]
    xyz = nodes.new("ShaderNodeSeparateXYZ")
    links.new(world, xyz.inputs[0])
    coordinates = nodes.new("ShaderNodeVectorMath")
    coordinates.operation = "MULTIPLY"
    coordinates.inputs[1].default_value = (.008, .010, .045)
    links.new(world, coordinates.inputs[0])
    turbulence = nodes.new("ShaderNodeTexNoise")
    turbulence.inputs["Scale"].default_value = 1.0
    turbulence.inputs["Detail"].default_value = 3.5
    turbulence.inputs["Roughness"].default_value = .63
    links.new(coordinates.outputs[0], turbulence.inputs["Vector"])
    clumps = range_node(nodes, links, turbulence.outputs["Fac"], .36, .68)
    horizontal = nodes.new("ShaderNodeVectorMath")
    horizontal.operation = "MULTIPLY"
    horizontal.inputs[1].default_value = (1, 1, 0)
    links.new(world, horizontal.inputs[0])
    distance = nodes.new("ShaderNodeVectorMath")
    distance.operation = "DISTANCE"
    distance.inputs[1].default_value = (*clearing.center, 0)
    links.new(horizontal.outputs[0], distance.inputs[0])
    outside = range_node(nodes, links, distance.outputs["Value"], clearing.inner_radius, clearing.outer_radius)
    clumps = math_output(nodes, links, "MULTIPLY", clumps, outside)
    drift = range_node(nodes, links, turbulence.outputs["Fac"], .27, .78, -18, 18)
    height = math_output(nodes, links, "ADD", xyz.outputs["Z"], drift)

    density = .00016
    for band in bands:
        relative = math_output(nodes, links, "SUBTRACT", height, band.elevation)
        offset = math_output(nodes, links, "ABSOLUTE", relative)
        envelope = range_node(nodes, links, offset, 0, band.half_depth, band.density, 0)
        layer = math_output(nodes, links, "MULTIPLY", envelope, clumps)
        density = math_output(nodes, links, "ADD", density, layer)
    mist = nodes.new("ShaderNodeVolumeScatter")
    mist.inputs["Color"].default_value = (.81, .87, .94, 1)
    mist.inputs["Anisotropy"].default_value = .16
    links.new(density, mist.inputs["Density"])
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(mist.outputs[0], output.inputs["Volume"])
    volume = box("Cloud and mist volume", center, (2240, 2490, 910), lights, material, bevel=0)
    volume.display_type = "WIRE"


def sky(scene, lights, warmth, sun_direction, center, bands, clearing):
    direction = Vector(sun_direction).normalized()
    daylight(scene, direction)
    sun = bpy.data.lights.new("Raking mountain sunlight", "SUN")
    sun.energy = 4.1
    sun.angle = math.radians(2.6)
    sun.color = warmth
    key = bpy.data.objects.new(sun.name, sun)
    lights.objects.link(key)
    key.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    cloud_volume(lights, center, bands, clearing)


def setup_scene(name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = name
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 56
    scene.cycles.use_denoising = True
    scene.cycles.volume_bounces = 1
    scene.cycles.volume_step_rate = 2.8
    scene.cycles.volume_max_steps = 512
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = .37
    scene.render.image_settings.file_format = "PNG"
    return scene


def set_views(scene, views):
    cameras = group("Review cameras")
    for name, (origin, target, lens, _) in views.items():
        obj = camera(name, origin, target, lens, cameras)
        obj.data.clip_end = 4200
    first = next(iter(views))
    scene.camera = bpy.data.objects[first]
    scene.render.resolution_x, scene.render.resolution_y = views[first][3]
    scene.render.filepath = f"//Preview/{first}.png"
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.clip_end = 4200
                area.spaces.active.region_3d.view_perspective = "CAMERA"
