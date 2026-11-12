"""Build or render Li Qingran's editable, photo-constrained head and shoulders."""

import argparse
from pathlib import Path
import sys

import bpy

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from portrait_source import HEAD, ROOT, SOURCE
from blender_still import open_scene, render_still
from refine_portrait import PhotoView
from face_fit import face_shape, reference_color
from portrait_groom import hairline, lashes
from portrait_views import VIEWS, configure, create_review_cameras

NAME = "LiQingran_Likeness.blend"


def build(path):
    if path.exists():
        raise FileExistsError(path)
    scene = open_scene(SOURCE)
    head = bpy.data.objects[HEAD]
    bpy.context.view_layer.update()
    photo = PhotoView(bpy.data.objects[VIEWS["matched"][0]])

    pixels = face_shape(head, photo)
    reference_color(head, pixels)
    hairline(head, photo)
    lashes(head, photo, scene)

    create_review_cameras(scene)
    configure(scene, "portrait")
    scene.render.filepath = "//Preview/Portrait.png"
    scene["likeness_scope"] = "Photo-matched frontal proportions; side and back depth inferred."
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.use_denoising = True
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True, relative_remap=False)


def render(path, view, output, scale, samples):
    scene = open_scene(path)
    configure(scene, view)
    render_still(scene, output, scale=scale, samples=samples,
                 threshold=.038 if scale < 100 else .024)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "render"))
    parser.add_argument("--blend", type=Path, default=ROOT / NAME)
    parser.add_argument("--view", choices=VIEWS, default="portrait")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--scale", type=int, default=100)
    parser.add_argument("--samples", type=int, default=64)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if args.action == "build":
        build(args.blend.resolve())
    else:
        if args.image is None:
            parser.error("render requires --image")
        render(args.blend.resolve(), args.view, args.image.resolve(), args.scale, args.samples)


if __name__ == "__main__":
    main()
