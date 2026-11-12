"""Cameras, wardrobe visibility, and studio lighting for portrait review."""

import bpy

from portrait_source import HEAD
from refine_portrait import area, camera
from build_portrait import simple

VIEWS = {
    "matched": ("Reference_Matched_Approximate", (1170, 960)),
    "portrait": ("Likeness portrait", (1440, 1740)),
    "clay": ("Profile clay review", (1024, 1160)),
    "quarter": ("Quarter material review", (1200, 1334)),
}
ROBE = "White robe • portrait shoulder drape"


def create_review_cameras(scene):
    camera(scene, VIEWS["portrait"][0], (.43, -2.84, .719), (.018, -.033, .548), 1.021)
    camera(scene, VIEWS["quarter"][0], (-1.10, -2.79, .686), (.020, -.017, .566), 1.04)
    camera(scene, VIEWS["clay"][0], (3.18, -.44, .658), (.005, 0, .616), 1.005)


def softbox(light, position, focus, energy, color, size, *, specular=1, diffuse=1):
    light.data.shape = "RECTANGLE"
    area(light, position, focus, energy, color, size[0])
    light.data.size_y = size[1]
    light.data.specular_factor = specular
    light.data.diffuse_factor = diffuse


def studio(scene, view):
    clay = view == "clay"
    nodes, links = scene.world.node_tree.nodes, scene.world.node_tree.links
    nodes.clear()
    ambient = nodes.new("ShaderNodeBackground")
    ambient.inputs["Color"].default_value = (.67, .73, .85, 1)
    ambient.inputs["Strength"].default_value = .28 if clay else .18
    backdrop = nodes.new("ShaderNodeBackground")
    backdrop.inputs["Color"].default_value = (.11, .11, .11, 1) if clay else (.032, .042, .042, 1)
    backdrop.inputs["Strength"].default_value = .60
    ray = nodes.new("ShaderNodeLightPath")
    background = nodes.new("ShaderNodeMixShader")
    links.new(ray.outputs["Is Camera Ray"], background.inputs[0])
    links.new(ambient.outputs[0], background.inputs[1])
    links.new(backdrop.outputs[0], background.inputs[2])
    output = nodes.new("ShaderNodeOutputWorld")
    links.new(background.outputs[0], output.inputs["Surface"])

    key, fill, rim = (bpy.data.objects[name] for name in ("Studio_Key", "Studio_Fill", "Studio_Rim"))
    softbox(key, (.90, -1.16, 1.19), (.02, -.16, .57), 115,
            (1, .94, .89) if not clay else (1, .99, .97), (.55, .88), specular=.74)
    softbox(fill, (-1.14, -1.06, .89), (.01, -.15, .55), 43 if clay else 34,
            (.85, .92, 1), (1.45, 1.08), specular=.24)
    softbox(rim, (.73, .32, 1.17), (.012, -.02, .63), 52 if not clay else 27,
            (.90, .96, 1), (.23, .79), diffuse=.31, specular=.75)
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -.22 if not clay else .08


def configure(scene, view):
    camera_name, size = VIEWS[view]
    scene.camera = bpy.data.objects[camera_name]
    scene.render.resolution_x, scene.render.resolution_y = size
    bpy.data.collections[ROBE].hide_render = view == "matched"
    for obj in scene.objects:
        if obj.name.startswith("Shoulder_Cord_"):
            obj.hide_render = view != "matched"
    studio(scene, view)
    if view == "clay":
        matte = simple("Neutral clay", (.47, .45, .42), .60)
        for slot in bpy.data.objects[HEAD].material_slots:
            slot.material = matte
