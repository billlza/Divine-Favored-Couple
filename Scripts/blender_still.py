"""Render an explicitly configured Cycles still on the local Metal device."""

from pathlib import Path

import bpy


def open_scene(path: Path):
    bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False, use_scripts=False)
    return bpy.context.scene


def render_still(scene, output: Path, *, scale: int, samples: int, threshold: float):
    if scale < 1 or samples < 1:
        raise ValueError("Render scale and sample count must be positive")
    if scene.render.engine != "CYCLES" or scene.camera is None:
        raise ValueError("Still rendering requires a Cycles scene with a camera")
    preferences = bpy.context.preferences.addons["cycles"].preferences
    preferences.compute_device_type = "METAL"
    preferences.refresh_devices()
    for device in preferences.devices:
        device.use = device.type == "METAL"
    if not any(device.use for device in preferences.devices):
        raise RuntimeError("Cycles Metal device is unavailable")

    scene.cycles.device = "GPU"
    scene.cycles.samples = samples
    scene.cycles.adaptive_threshold = threshold
    scene.render.resolution_percentage = scale
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)
