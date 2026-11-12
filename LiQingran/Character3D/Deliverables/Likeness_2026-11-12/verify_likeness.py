"""Reopen both portraits and compare their geometry at the original camera."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils.bvhtree import BVHTree
import numpy as np

sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from portrait_source import HAIR_COLLECTION, HEAD, PHOTO, SOURCE
from portrait_views import VIEWS
from refine_portrait import PhotoView, require
from build_portrait import shape_positions

LANDMARKS=PHOTO.parents[5]/"Docs/Art/Experiments/2026-09-30-likeness-rebuild/reference-features-manual.json"
CAPTURES={"portrait":"Portrait","matched":"Matched_view","quarter":"Quarter","clay":"Profile_clay"}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def field(collection,name,dtype,components=1):
    data=np.empty((len(collection),components),dtype=dtype)
    collection.foreach_get(name,data.ravel())
    return data


def reopen(path):
    bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
    bpy.context.view_layer.update()
    return bpy.data.objects[HEAD],bpy.data.objects[VIEWS["matched"][0]]


def surface(mesh,matrix):
    mesh.calc_loop_triangles()
    return BVHTree.FromPolygons([matrix@v.co for v in mesh.vertices],
                               [t.vertices[:] for t in mesh.loop_triangles],all_triangles=True)


def evaluate(body):
    bpy.context.view_layer.update()
    return body.evaluated_get(bpy.context.evaluated_depsgraph_get())


def silhouette(body,camera,landmarks):
    """Approximate x positions; neck and rear skin are excluded by ray depth."""
    photo=PhotoView(camera)
    evaluated=evaluate(body)
    mesh=evaluated.to_mesh()
    try:
        tree=surface(mesh,evaluated.matrix_world)
        materials=[mesh.polygons[t.polygon_index].material_index for t in mesh.loop_triangles]
    finally:
        evaluated.to_mesh_clear()

    def hit(x,y,depth,material):
        _,_,i,_=tree.ray_cast(photo.ray(float(x),float(y)),photo.direction,depth)
        return i is not None and materials[i]==material

    jaw={}
    for part in ("left","right"):
        for label in ("upper_turn","to_chin"):
            key=f"image_{part}_jaw_{label}"
            y=landmarks[key]["y_px"]
            xs=[x for x in np.arange(285,575,.5) if hit(x,y,2.887,0)]
            require(bool(xs),f"No visible jaw skin at reference row {y}")
            jaw[key]=float((min if part=="left" else max)(xs))
    eyes={}
    for part,x0,x1,y0,y1 in (("left",343,418,325,372),("right",453,526,304,355)):
        xs=[x for x in np.arange(x0,x1,.5) if any(hit(x,y,2.93,1) for y in np.arange(y0,y1,.5))]
        require(bool(xs) and 43<=max(xs)-min(xs)<=66,f"Unexpected {part} eye aperture")
        require(min(xs)>x0 and max(xs)<x1-1,f"Clipped eye window: {part}")
        low,high=("outer","inner") if part=="left" else ("inner","outer")
        eyes[f"image_{part}_eye_{low}_canthus"]=float(min(xs))
        eyes[f"image_{part}_eye_{high}_canthus"]=float(max(xs))
    return jaw,eyes


def measure(previous,revised,landmarks):
    target={name:landmarks[name]["x_px"] for name in previous}
    def error(points):
        return float(np.mean([abs(x-target[name]) for name,x in points.items()]))
    before,after=error(previous),error(revised)
    require(after<before*.65,f"Projection did not improve: {before:.2f} px → {after:.2f} px")
    return {"manual_x_px":target,"previous_x_px":previous,"revised_x_px":revised,
            "previous_mean_absolute_x_error_px":before,"revised_mean_absolute_x_error_px":after}


def groom(body):
    hair=[o for o in bpy.data.collections[HAIR_COLLECTION].objects if o.type=="CURVES"]
    lashes=bpy.data.objects["Tapered upper and lower eyelash fibers"]
    for obj in (*hair,lashes):
        positions=field(obj.data.attributes["position"].data,"vector",np.float32,3)
        radius=field(obj.data.attributes["radius"].data,"value",np.float32)
        require(np.isfinite(positions).all() and np.isfinite(radius).all() and (radius>0).all(),
                f"Invalid fiber geometry: {obj.name}")
        require(positions[:,2].min()>-.24 and positions[:,2].max()<1.08,f"Fiber outside portrait: {obj.name}")
    hair_count=sum(len(o.data.curves) for o in hair)
    require(hair_count>=20000 and len(lashes.data.curves)>=56,"Incomplete strand geometry")
    cap,base,knot=(bpy.data.objects[name] for name in ("Scalp underlayer • fitted hairline",
                   "Tied hair at the base of the knot","Gathered knot underlayer"))
    a,b,c=(surface(obj.data,obj.matrix_world) for obj in (cap,base,knot))
    contacts=[len(a.overlap(b)),len(b.overlap(c))]
    require(all(contacts),f"Detached topknot: {contacts}")
    require(body.data.materials[0]==body.data.materials[2],"Inconsistent head and neck shader")
    for material in body.data.materials[:2]:
        bsdf=material.node_tree.nodes["Principled BSDF"]
        require(bsdf.inputs["Base Color"].is_linked and not bsdf.inputs["Emission Color"].is_linked
                and bsdf.inputs["Emission Strength"].default_value==0,"Projected color bypasses lighting")
    return {"hair_curves":hair_count,"eyelash_curves":len(lashes.data.curves),"topknot_contact_pairs":contacts}


def main(path,report):
    landmarks=json.loads(LANDMARKS.read_text())
    ref_sha=sha(PHOTO)
    require(landmarks["source_image"]["sha256"]==ref_sha,"Landmarks do not describe this reference")
    points={row["id"]:row for row in landmarks["points"]}
    source,camera=reopen(SOURCE)
    loops=field(source.data.loops,"vertex_index",np.int32)
    source_shape=field(evaluate(source).data.vertices,"co",np.float32,3)
    prior_keys={k.name:shape_positions(k) for k in source.data.shape_keys.key_blocks}
    matrix,scale=np.array(camera.matrix_world),camera.data.ortho_scale
    before_jaw,before_eyes=silhouette(source,camera,points)

    body,camera=reopen(path)
    require(np.array_equal(loops,field(body.data.loops,"vertex_index",np.int32)),"Head topology changed")
    require(camera.data.type=="ORTHO" and camera.data.ortho_scale==scale
            and np.array_equal(matrix,np.array(camera.matrix_world)),"Review camera changed")
    keys=body.data.shape_keys.key_blocks
    require(len(keys)==len(prior_keys)+1 and keys[-1].relative_key==keys[-2] and keys[-1].value==1,
            "Revision is not a separate additive shape")
    require(all(np.array_equal(v,shape_positions(keys[n])) for n,v in prior_keys.items()),"A previous key changed")
    displacement=np.linalg.norm(field(evaluate(body).data.vertices,"co",np.float32,3)-source_shape,axis=1)
    require((displacement>.0001).sum()>500 and float(displacement.max())<.032,"Unexpected sculpt displacement")
    keys[-1].value=0
    require(np.array_equal(source_shape,field(evaluate(body).data.vertices,"co",np.float32,3)),"Previous shape not restorable")
    keys[-1].value=1
    after_jaw,after_eyes=silhouette(body,camera,points)
    images=[i for i in bpy.data.images if i.source=="FILE" and i.users]
    require(not bpy.data.libraries and images and all(i.packed_file for i in images),"Unpacked dependencies")
    require(any(hashlib.sha256(i.packed_file.data).hexdigest()==ref_sha for i in images),"Original reference not packed")
    fibers=groom(body)
    renders={}
    for view,name in CAPTURES.items():
        png=path.parent/"Preview"/f"{name}.png"
        img=bpy.data.images.load(str(png),check_existing=False)
        pixels=np.empty(len(img.pixels),np.float32)
        img.pixels.foreach_get(pixels)
        require(tuple(img.size)==VIEWS[view][1] and np.isfinite(pixels).all() and pixels.std()>.08,f"Invalid render: {png}")
        renders[png.name]={"resolution":list(img.size),"sha256":sha(png)}
        bpy.data.images.remove(img)
    data={"blender":bpy.app.version_string,"blend_sha256":sha(path),"source_sha256":sha(SOURCE),
          "reference_sha256":ref_sha,"reference_camera_preserved":True,"previous_shape_restores_exactly":True,
          "max_revision_displacement_blender_units":float(displacement.max()),
          "approximate_projection":{"jaw":measure(before_jaw,after_jaw,points),
              "eye_corners":measure(before_eyes,after_eyes,points),
              "scope":"Two dimensional x coordinates against manual landmarks; not an identity score."},
          "groom":fibers,"renders":renders}
    report.write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
    print("LIKENESS_REOPEN_CHECKED",data["approximate_projection"],fibers,flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blend",type=Path)
    parser.add_argument("report",type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    main(args.blend.resolve(),args.report.resolve())
