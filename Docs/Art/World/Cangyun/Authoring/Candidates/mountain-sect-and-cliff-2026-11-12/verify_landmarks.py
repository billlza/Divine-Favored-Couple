"""Reopen a saved landmark and check the authored openings and walking surfaces."""

import argparse
import hashlib
import importlib
import json
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector
import numpy as np

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
sys.dont_write_bytecode=True
from landscape import require, terrain_tree


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle,"sha256").hexdigest()


def solid(collection):
    return [obj for obj in collection.objects if obj.type=="MESH"]


def floor_z(tree,x,y,start=60):
    hit,_,_,_=tree.ray_cast(Vector((x,y,start)),Vector((0,0,-1)),3700)
    require(hit is not None,f"Missing walking surface at {x:.2f},{y:.2f}")
    return hit.z


def clear(tree,start,end):
    a,b=Vector(start),Vector(end)
    p,_,_,_=tree.ray_cast(a,(b-a).normalized(),(b-a).length)
    require(p is None,f"Route meets solid geometry at {p}")


def qingyun(module):
    objects=solid(bpy.data.collections["Stair, gate and forecourt"])
    foothold = [obj for obj in objects if obj.name.startswith(("Flight ", "Stair landing", "Landing granite",
               "Gate and courtyard terrace", "Courtyard paving", "Hall porch stair"))]
    terrain = bpy.data.objects["Qingyun ridges and temple shelf"]
    walked = terrain_tree([*foothold, terrain]).tree
    errors=[]
    for j,start in enumerate(module.STARTS):
        for k in range(15):
            y=start+(k+.5)*module.TREAD
            target=module.BASE+(15*j+k+1)*module.RISE
            for x in (-2.37,0,2.37):
                errors.append(abs(floor_z(walked,x,y)-target))
    require(len(errors)==135 and max(errors)<.04,f"Stair tread off grade: {max(errors):.3f} m")
    stone = terrain_tree(foothold).tree
    ground = terrain_tree([terrain]).tree
    landings = 0
    for a, b in zip(module.STARTS, (*module.STARTS[1:], module.TERRACE_EDGE), strict=True):
        for y in np.linspace(a + 15 * module.TREAD + .19, b - .19, 8):
            for x in (-2.37, 0, 2.37):
                target = float(module.grade(y))
                level = floor_z(stone, x, y)
                require(abs(level - target) < .065 and level > floor_z(ground, x, y) + .010,
                        f"Stair landing has exposed terrain at {x:.2f},{y:.2f}")
                landings += 1
    for y in np.linspace(-5.3,23.6,90):
        require(abs(floor_z(walked,0,y)-module.COURT)<.08,"Courtyard path changes level abruptly")
    building=terrain_tree(objects).tree
    for x in (-1.2,0,1.2):
        for h in (.35,1.15,1.8,2.4):
            clear(building,(x,-6.04,module.COURT+h),(x,12,module.COURT+h))
    require(bpy.data.objects.get("青云宗牌匾") is not None,"Missing Qingyun plaque")
    return {"stair_treads":45,"stair_surface_probes":len(errors),"maximum_tread_height_error_m":max(errors),
            "exposed_stone_landing_probes":landings,
            "passage_rays_clear":12,"gate_to_courtyard_checked":True}


def jiange(module):
    cliff=bpy.data.objects["Fractured cliff with excavated rooms"]
    bm=bmesh.new()
    try:
        bm.from_mesh(cliff.data)
        require(all(e.is_manifold for e in bm.edges),"Excavated cliff is not a closed solid")
    finally:
        bm.free()
    shell=terrain_tree([cliff]).tree
    exterior=solid(bpy.data.collections["Dwellings and cliff path"])
    landscape=bpy.data.objects["Jiange ledge and mountain drop"]
    walkable=[o for o in exterior if o.name.startswith(("Path flagstone","Cave side path slab"))
              or "threshold to interior" in o.name]
    floor=terrain_tree([landscape,*walkable]).tree
    ground=terrain_tree([landscape]).tree
    buttresses = [obj for obj in solid(bpy.data.collections["Cliff face and drop"])
                  if obj.name.startswith("Broken cliff buttress")]
    require(len(buttresses) == 4, "Missing authored cliff buttresses")
    structure=terrain_tree([*exterior, *buttresses]).tree
    rooms=[]
    for i,(y,r,h,back) in enumerate(module.CAVES,1):
        level=float(module.shelf(y))
        for offset in (-.55,0,.55):
            for dz in (.37,1.1,1.73):
                p,_,_,_=shell.ray_cast(Vector((1.4,y+offset,level+dz)),Vector((1,0,0)),60)
                require(p is not None and abs(p.x-back)<.025,f"Cave {i} lacks the planned cavity at {p}")
                clear(structure,(1.4,y+offset,level+dz),(back-.45,y+offset,level+dz))
        for check_y,check_z in ((y+r+1.0,level+1.3),(y,level+h+.85)):
            p,_,_,_=shell.ray_cast(Vector((1.4,check_y,check_z)),Vector((1,0,0)),50)
            require(p is not None and p.x<back-2,"Cave side or top has no surrounding rock")
        marker=bpy.data.objects[f"jiange.cave_{i}.threshold"]
        samples=[floor_z(floor,float(x),y,start=level+1.04) for x in np.linspace(float(module.approach_x(y)),marker.location.x,22)]
        require(max(abs(a-b) for a,b in zip(samples,samples[1:]))<.25,"Abrupt step on cave approach")
        floor_inside=floor_z(floor,back-1.2,y,start=level+.90)
        require(abs(floor_inside-level)<.13,"Missing interior floor")
        rooms.append({"id":marker.name,"opening_width_m":2*r,"opening_height_m":h,
                      "depth_from_threshold_marker_m":back-marker.location.x,"clear_passage_rays":9})
    for y in np.linspace(-42,57,100):
        x=float(module.approach_x(y))
        require(abs(floor_z(ground,x,y)-module.shelf(y))<.18,"Main trail leaves the ledge")
    for name in ("Raised flowers soil","Raised cacti soil","Chrysanthemum heads","Stone house open door lintel"):
        require(bpy.data.objects.get(name) is not None,f"Missing authored prop {name}")
    return {"cavities":rooms,"cliff_closed_solid":True,"ledge_probes":100,"gardens_checked":["chrysanthemums","cacti"]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("location",choices=("qingyun","jiange"))
    parser.add_argument("blend",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    path=args.blend.resolve()
    bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
    bpy.context.view_layer.update()
    require(bpy.context.scene.unit_settings.system=="METRIC","Scene units are not metres")
    require(not bpy.data.libraries,"Linked scene asset")
    require(not any(i.users and i.source=="FILE" and not i.packed_file for i in bpy.data.images),
            "External texture dependency")
    module=importlib.import_module(args.location)
    checks=(qingyun if args.location=="qingyun" else jiange)(module)
    renders={}
    for name,info in module.VIEWS.items():
        png=path.parent/"Preview"/f"{name}.png"
        img=bpy.data.images.load(str(png),check_existing=False)
        pixels=np.empty(len(img.pixels),dtype=np.float32)
        img.pixels.foreach_get(pixels)
        require(tuple(img.size)==info[3] and np.isfinite(pixels).all() and pixels.std()>.07,f"Invalid render {name}")
        renders[name]={"size":list(img.size),"sha256":sha(png)}
        bpy.data.images.remove(img)
    args.output.write_text(json.dumps({"blender":bpy.app.version_string,"location":args.location,
        "blend_sha256":sha(path),"geometry":checks,"renders":renders},indent=2,ensure_ascii=False)+"\n")
    print(f"REOPEN_CHECKED {args.location} {checks}",flush=True)


if __name__=="__main__":
    main()
