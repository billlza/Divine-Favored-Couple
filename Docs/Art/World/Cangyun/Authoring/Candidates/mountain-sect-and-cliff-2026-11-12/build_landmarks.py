"""Build or render one of the two editable Cangyun location files."""

import argparse
import importlib
from pathlib import Path
import sys

import bpy

ROOT=Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT.parents[6] / "Scripts")]
sys.dont_write_bytecode=True
from blender_still import open_scene, render_still

FILES={"qingyun":"Cangyun_Qingyun.blend","jiange":"Cangyun_Jiange.blend"}


def render(path, module, view, image, scale, samples):
    scene = open_scene(path)
    scene.camera=bpy.data.objects[view]
    scene.render.resolution_x,scene.render.resolution_y=module.VIEWS[view][3]
    render_still(scene, image, scale=scale, samples=samples, threshold=.056 if scale<100 else .032)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("build","render"))
    parser.add_argument("location",choices=FILES)
    parser.add_argument("--blend",type=Path)
    parser.add_argument("--view")
    parser.add_argument("--image",type=Path)
    parser.add_argument("--scale",type=int,default=100)
    parser.add_argument("--samples",type=int,default=54)
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    path=(args.blend or ROOT/FILES[args.location]).resolve()
    module=importlib.import_module(args.location)
    if args.action=="build":
        if path.exists():
            raise FileExistsError(path)
        module.build()
        bpy.ops.outliner.orphans_purge(do_recursive=True)
        bpy.context.preferences.filepaths.save_version=0
        bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True,relative_remap=False)
    else:
        view=args.view or next(iter(module.VIEWS))
        if view not in module.VIEWS or not args.image:
            parser.error("render requires a valid view and --image")
        render(path,module,view,args.image.resolve(),args.scale,args.samples)


if __name__=="__main__":
    main()
