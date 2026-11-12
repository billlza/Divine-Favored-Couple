"""Build a static likeness candidate with independently combed native hair curves."""
import argparse
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
import numpy as np

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / "HeadShoulders_2026-11-12"
SOURCE = PREVIOUS / "LiQingran_Sculpt.blend"
PHOTO_SOURCE = HERE.parent / "HeadShoulders_2026-09-30/LiQingran_HeadShoulders.blend"
NAME = "LiQingran_Portrait"
sys.path[:0] = [str(HERE),str(PREVIOUS)]
from refine_portrait import (HEAD, HAIR, SCALP, PhotoView, area, attribute, bell, camera,
                             color_mix, evaluated_bvh, require, smooth)
from groom_portrait import make_groom, mesh

VIEWS = {
    "matched": ("Reference_Matched_Approximate", (1170, 960)),
    "portrait": ("Silk studio portrait", (1152, 1392)),
    "profile": ("Portrait profile", (990, 1140)),
    "clay": ("Portrait profile", (990, 1140)),
}


def shape_positions(block):
    output=np.empty((len(block.data),3),dtype=np.float32)
    block.data.foreach_get("co",output.ravel())
    return output


def sculpt_lids(head, photo):
    previous=head.data.shape_keys.key_blocks[1]
    initial=shape_positions(previous)
    uv=photo.to_pixels(initial,head)
    front=smooth(-2.84,-2.73,uv[:,2])
    pixels=uv[:,:2]
    upper=(bell(pixels,(379,338),(37,19))+bell(pixels,(487,320),(37,19)))*front
    lower=(bell(pixels,(379,358),(41,26))+bell(pixels,(486,340),(38,23)))*front
    outer=(bell(pixels,(352,354),(24,25))+bell(pixels,(514,331),(24,25)))*front
    lower_face=bell(pixels,(451,474),(73,43))*front
    deltas=np.column_stack((np.zeros(len(uv)),
        (1.05*lower-.58*upper+.43*outer-.6*lower_face)/photo.scale,
        .0023*upper+.0014*lower-.0029*lower_face))
    to_local=np.array((head.matrix_world.inverted()@photo.matrix).to_3x3())
    detail=head.shape_key_add(name="Eye aperture and chin transition",from_mix=False)
    detail.relative_key=previous
    detail.data.foreach_set("co",np.asarray(initial+deltas@to_local.T,dtype=np.float32).ravel())
    detail.value=1
    print("LID SCULPT",int(np.sum(np.linalg.norm(deltas,axis=1)>.0001)),flush=True)


def restore_eye_detail(head):
    old_name="Candidate_03_Eye_Surface"
    with bpy.data.libraries.load(str(PHOTO_SOURCE),link=False) as (source,target):
        require(old_name in source.materials,"Missing original eye material")
        target.materials=[old_name]
    material=target.materials[0]
    material.name="Eyes • reference color and physically lit cornea"
    head.data.materials[1]=material
    nodes,links=material.node_tree.nodes,material.node_tree.links
    surface=nodes["Principled BSDF"]
    base=surface.inputs["Base Color"].links[0].from_socket
    value=nodes.new("ShaderNodeRGBToBW")
    links.new(base,value.inputs["Color"])
    glare=nodes.new("ShaderNodeMapRange")
    glare.interpolation_type="SMOOTHERSTEP"
    glare.inputs["From Min"].default_value=.24
    glare.inputs["From Max"].default_value=.65
    glare.inputs["To Max"].default_value=.26
    links.new(value.outputs[0],glare.inputs["Value"])
    color=color_mix(nodes,links,base,(.20,.135,.107,1),glare.outputs["Result"])
    links.new(color,surface.inputs["Base Color"])
    surface.inputs["Roughness"].default_value=.27
    surface.inputs["Specular IOR Level"].default_value=.21
    surface.inputs["Coat Weight"].default_value=.10
    surface.inputs["Coat Roughness"].default_value=.20
    surface.inputs["IOR"].default_value=1.382


def tune_skin(head):
    material=head.data.materials[0]
    material.name="Skin • continuous face and neck"
    head.data.materials[2]=material
    nodes,links=material.node_tree.nodes,material.node_tree.links
    shader=nodes["Principled BSDF"]
    base=shader.inputs["Base Color"]
    original=base.links[0].from_socket
    warmed=color_mix(nodes,links,original,(.455,.237,.171,1),.095)
    # The sculpt is continuous, so the neck and shoulders use the same shader.
    # Fade the single-view facial color smoothly below the lower jaw.
    surface=nodes.new("ShaderNodeNewGeometry")
    position=nodes.new("ShaderNodeSeparateXYZ")
    links.new(surface.outputs["Position"],position.inputs["Vector"])
    mask=nodes.new("ShaderNodeMapRange")
    mask.interpolation_type="SMOOTHERSTEP"
    mask.inputs["From Min"].default_value=.265
    mask.inputs["From Max"].default_value=.340
    links.new(position.outputs["Z"],mask.inputs["Value"])
    continuous=color_mix(nodes,links,(.454,.251,.192,1),warmed,mask.outputs["Result"])
    links.new(continuous,base)
    shader.inputs["Roughness"].default_value=.51
    shader.inputs["Subsurface Weight"].default_value=.072
    shader.inputs["Subsurface Scale"].default_value=.011
    shader.inputs["Specular IOR Level"].default_value=.27


def simple(name,color,rough,metal=0):
    m=bpy.data.materials.new(name)
    shader=m.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value=(*color,1)
    shader.inputs["Roughness"].default_value=rough
    shader.inputs["Metallic"].default_value=metal
    return m


def tubes(name,paths,width,material,collection):
    curve=bpy.data.curves.new(name,"CURVE")
    curve.dimensions="3D"
    curve.bevel_depth=width
    curve.bevel_resolution=3
    curve.use_fill_caps=True
    curve.materials.append(material)
    for points in paths:
        spline=curve.splines.new("POLY")
        spline.points.add(len(points)-1)
        for item,point in zip(spline.points,points):
            item.co=(*point,1)
    obj=bpy.data.objects.new(name,curve)
    collection.objects.link(obj)
    return obj


def pin(photo,scene):
    collection=bpy.data.collections.new("Hairpin • cut silver and silk")
    scene.collection.children.link(collection)
    silver=simple("Pin • polished silver",(.59,.66,.70),.25,.88)
    recess=simple("Pin • oxidized silver",(.145,.179,.195),.38,.82)
    silk=simple("Pin • dark cyan silk",(.018,.184,.214),.48)
    jade=simple("Pin • glazed teal bead",(.027,.21,.23),.30,.08)
    turn=lambda x,y,d: photo.ray(float(x),float(y))+photo.direction*d
    axis_left=(235,119)
    axis_right=(545,96)
    shaft=[turn(*p,d) for p,d in zip((axis_left,axis_right),(2.923,2.896))]
    tubes("Silver pin shaft",[shaft],.00415,silver,collection)
    loops=[]
    for cx,cy,d,sign,start in ((218,123,2.923,-1,shaft[0]),(562,94,2.896,1,shaft[1])):
        points=[start]
        for t in np.linspace(0,1,78):
            a=-math.pi/2+t*math.tau*1.10
            r=(14.4-8.1*t)*(.96+.04*math.sin(t*math.pi))
            points.append(turn(cx+sign*r*math.sin(a),cy+r*math.cos(a),d+.003*math.sin(t*math.tau)))
        loops.append(points)
    tubes("Chased silver scroll ends",loops,.00365,silver,collection)
    links=[]
    for x in (249,255,528,534,541):
        t=(x-axis_left[0])/(axis_right[0]-axis_left[0])
        p=shaft[0].lerp(shaft[1],t)
        tangent=(shaft[1]-shaft[0]).normalized()
        back=Vector((0,1,0))
        up=tangent.cross(back).normalized()
        links.append([p+(.008 if x in (249,534) else .0064)*(back*math.cos(a)+up*math.sin(a))
                      for a in np.linspace(0,math.tau,38)])
    tubes("Pin shaft collars",links,.00185,recess,collection)
    # Curves share the actual pin depth; the relief is supported by a rear arch.
    crest_depth=2.899
    def crest_path(points,depth=crest_depth):
        return [turn(*p,depth) for p in points]
    x=np.linspace(328,449,101)
    t=(x-328)/121
    bottom=116-.070*(x-328)
    arch=bottom-35*np.sin(math.pi*t)**1.58
    crest=[crest_path(list(zip(x,bottom))),crest_path(list(zip(x,arch)))]
    for cx,cy,rx,ry,sgn in ((353,104,14,8,1),(426,98,14,9,-1),(386,97,11,15,1),(400,98,9,10,-1)):
        a=np.linspace(-.25,math.tau+.24,54)
        weight=np.linspace(1,.52,len(a))
        crest.append(crest_path(list(zip(cx+rx*np.cos(a)*weight*sgn,cy+ry*np.sin(a)*weight))))
    tubes("Openwork silver crest",crest,.0030,silver,collection)
    tubes("Crest mounting clips",[crest_path(((336,115),(338,108),(339,102)),2.916),
                                  crest_path(((438,108),(435,101),(431,96)),2.914)],.0037,recess,collection)
    support_x,support_y=386,106
    tubes("Hidden shaft into the tied knot",
          [[turn(support_x,support_y,2.904),turn(support_x,support_y+3,2.970),
            turn(support_x+3,support_y+4,3.037)]],.0041,recess,collection)

    chain=[]
    for k in range(3):
        y=108+6.2*k
        chain.append([turn(562+2.9*math.cos(a),y+4.7*math.sin(a),2.891+.0021*math.cos(a)*(-1)**k)
                      for a in np.linspace(0,math.tau,36)])
    tubes("Tassel silver chain",chain,.00125,silver,collection)
    point=turn(563,127,2.893)
    ring_rows=[]
    for v in np.linspace(-math.pi/2+.012,math.pi/2-.012,18):
        ring_rows.append([tuple(point+Vector((.009*math.cos(v)*math.cos(a),.008*math.cos(v)*math.sin(a),.010*math.sin(v))))
                          for a in np.linspace(0,math.tau,32,endpoint=False)])
    faces=[(j*32+i,j*32+(i+1)%32,(j+1)*32+(i+1)%32,(j+1)*32+i) for j in range(17) for i in range(32)]
    faces.extend((tuple(reversed(range(32))),tuple(range(17*32,18*32))))
    mesh("Tassel polished jade bead",[p for row in ring_rows for p in row],faces,jade,collection)
    threads=[]
    rng=np.random.default_rng(739)
    for _ in range(75):
        a=rng.uniform(0,math.tau)
        r=rng.uniform(.7,4.7)
        length=rng.uniform(47,57)
        threads.append([turn(563+r*(.5+.65*t)*math.cos(a)+2.2*t*t,131+length*t,
                             2.892+.0019*r*math.sin(a)*(1+.16*t)) for t in np.linspace(0,1,19)])
    tubes("Loose silk tassel fibers",threads,.00058,silk,collection)



def dress_bust(head,scene):
    """Cut a real collar opening into a drape offset from the fitted shoulders."""
    collection=bpy.data.collections.new("White robe • portrait shoulder drape")
    scene.collection.children.link(collection)
    obj=head.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data=obj.to_mesh()
    try:
        positions=np.asarray([tuple(obj.matrix_world @ v.co) for v in data.vertices])
        normals=np.asarray([tuple((obj.matrix_world.to_3x3()@v.normal).normalized()) for v in data.vertices])
        data.calc_loop_triangles()
        triangles=[list(t.vertices) for t in data.loop_triangles if data.polygons[t.polygon_index].material_index==2]
    finally:
        obj.to_mesh_clear()
    x,y,z=positions.T
    v=np.abs(x-.041+.19*(y+.145))
    front=.072+.188*np.clip((v-.012)/.167,0,1)
    top=front+( .245-front )*smooth(-.13,.055,y)
    depth=top-z
    offset=.011 + .017*smooth(.09,.32,abs(x-.045))
    offset+=.0058*np.exp(-((depth-.012)/.009)**2)
    offset+=.0052*np.sin(43*x+52*z+6*np.sin(y*16))*smooth(.025,.11,depth)
    offset+=.003*np.cos(77*x-28*y+36*z)*smooth(.025,.16,depth)
    outer=positions+normals*offset[:,None]
    verts,faces,seam_depth,ids=[],[],[],{}

    def vertex(a,b=None):
        key=(a,) if b is None else tuple(sorted((a,b)))
        if key not in ids:
            ids[key]=len(verts)
            if b is None:
                verts.append(outer[a])
                seam_depth.append(depth[a])
            else:
                t=depth[a]/(depth[a]-depth[b])
                verts.append(outer[a]+t*(outer[b]-outer[a]))
                seam_depth.append(0)
        return ids[key]

    for triangle in triangles:
        face=[]
        for a,b in zip(triangle,triangle[1:]+triangle[:1]):
            if depth[a]>=0:
                face.append(vertex(a))
            if (depth[a]>=0)!=(depth[b]>=0):
                face.append(vertex(a,b))
        if len(face)>2:
            faces.append(face)
    require(len(faces)>1800,"White shoulder drape has no usable surface")
    silk=simple("Robe • ivory silk with celadon lapel",(.72,.72,.67),.53)
    nodes,links=silk.node_tree.nodes,silk.node_tree.links
    bsdf=nodes["Principled BSDF"]
    bsdf.inputs["Sheen Weight"].default_value=.23
    bsdf.inputs["Sheen Roughness"].default_value=.60
    edge=attribute(nodes,"Distance from collar edge")["Fac"]
    ramp=nodes.new("ShaderNodeValToRGB")
    elements=ramp.color_ramp.elements
    elements[0].position=0
    elements[0].color=(.048,.151,.163,1)
    elements[1].position=.029
    elements[1].color=(.68,.68,.637,1)
    elements.new(.004).color=(.093,.25,.253,1)
    elements.new(.0125).color=(.33,.460,.481,1)
    elements.new(.025).color=(.51,.573,.567,1)
    links.new(edge,ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"],bsdf.inputs["Base Color"])
    coord=nodes.new("ShaderNodeTexCoord")
    thread=nodes.new("ShaderNodeTexNoise")
    thread.inputs["Scale"].default_value=750
    thread.inputs["Detail"].default_value=2.1
    links.new(coord.outputs["Object"],thread.inputs["Vector"])
    bump=nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value=.24
    bump.inputs["Distance"].default_value=.00095
    links.new(thread.outputs["Fac"],bump.inputs["Height"])
    links.new(bump.outputs["Normal"],bsdf.inputs["Normal"])
    cloth=mesh("Robe shoulder panels and V collar",verts,faces,silk,collection)
    attr=cloth.data.attributes.new("Distance from collar edge","FLOAT","POINT")
    attr.data.foreach_set("value",np.asarray(seam_depth,dtype=np.float32))
    thickness=cloth.modifiers.new("Folded fabric edge","SOLIDIFY")
    thickness.thickness=.0028
    thickness.offset=-.6
    print("ROBE",len(verts),len(faces),flush=True)

def studio(scene,view):
    nodes,links=scene.world.node_tree.nodes,scene.world.node_tree.links
    nodes.clear()
    env=nodes.new("ShaderNodeBackground")
    env.inputs["Color"].default_value=(.66,.72,.77,1)
    env.inputs["Strength"].default_value=.31
    screen=nodes.new("ShaderNodeBackground")
    screen.inputs["Color"].default_value=(.169,.151,.132,1) if view=="portrait" else (.135,.135,.135,1)
    screen.inputs["Strength"].default_value=.68
    ray=nodes.new("ShaderNodeLightPath")
    mix=nodes.new("ShaderNodeMixShader")
    links.new(ray.outputs["Is Camera Ray"],mix.inputs[0])
    links.new(env.outputs[0],mix.inputs[1])
    links.new(screen.outputs[0],mix.inputs[2])
    output=nodes.new("ShaderNodeOutputWorld")
    links.new(mix.outputs[0],output.inputs["Surface"])
    key,fill,rim=(bpy.data.objects[name] for name in ("Studio_Key","Studio_Fill","Studio_Rim"))
    area(key,(.94,-1.48,1.65),(.03,-.15,.57),131,(1,.90,.81),1.28)
    area(fill,(-1.12,-1.1,.93),(0,-.08,.52),46,(.86,.93,1),1.24)
    area(rim,(-.36,1.01,1.36),(0,0,.56),31,(.88,.94,1),1.15)
    fill.data.specular_factor=.34
    rim.data.specular_factor=.32
    scene.view_settings.view_transform="AgX"
    scene.view_settings.look="AgX - Medium High Contrast"
    scene.view_settings.exposure=.06


def build(path):
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE),load_ui=False,use_scripts=False)
    scene=bpy.context.scene
    bpy.context.view_layer.update()
    photo=PhotoView(bpy.data.objects["Reference_Matched_Approximate"])
    obj=bpy.data.objects[HEAD]
    sculpt_lids(obj,photo)
    restore_eye_detail(obj)
    tune_skin(obj)
    for name in (HAIR,SCALP,"Portrait backdrop"):
        bpy.data.objects.remove(bpy.data.objects[name],do_unlink=True)
    old=bpy.data.collections["Editable fringe and temple strands"]
    for item in list(old.objects):
        # Lashes are rebuilt to the reshaped lid after the groom is seated.
        bpy.data.objects.remove(item,do_unlink=True)
    bpy.data.collections.remove(old)
    bpy.context.view_layer.update()
    make_groom(evaluated_bvh(obj),photo,scene)
    pin(photo,scene)
    dress_bust(obj,scene)
    hero=camera(scene,VIEWS["portrait"][0],(.46,-2.85,.665),(.016,-.035,.553),1.03)
    camera(scene,VIEWS["profile"][0],(3.1,-.49,.590),(-.008,0,.52),1.16)
    scene.name="Li Qingran / Photo-based portrait"
    scene["status"]="Likeness review candidate; static head and shoulder assembly."
    scene.camera=hero
    for item in scene.objects:
        if item.name.startswith("Shoulder_Cord_"):
            item.hide_render=True
    scene.render.engine="CYCLES"
    scene.cycles.device="CPU"
    scene.cycles.samples=64
    scene.cycles.use_denoising=True
    scene.render.image_settings.file_format="PNG"
    scene.render.resolution_x,scene.render.resolution_y=VIEWS["portrait"][1]
    scene.render.resolution_percentage=100
    scene.render.filepath="//Preview/Portrait.png"
    studio(scene,"portrait")
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True,relative_remap=False)


def render(path,view,output,scale,samples):
    bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
    scene=bpy.context.scene
    camera_name,size=VIEWS[view]
    scene.camera=bpy.data.objects[camera_name]
    scene.render.resolution_x,scene.render.resolution_y=size
    scene.render.resolution_percentage=scale
    scene.render.filepath=str(output)
    studio(scene,view)
    bpy.data.collections["White robe • portrait shoulder drape"].hide_render = view != "portrait"
    for obj in scene.objects:
        if obj.name.startswith("Shoulder_Cord_"):
            obj.hide_render=view=="portrait"
    if view=="clay":
        clay=simple("Neutral face inspection",(.45,.42,.38),.62)
        for slot in bpy.data.objects[HEAD].material_slots:
            slot.material=clay
    prefs=bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type="METAL"
    prefs.refresh_devices()
    for dev in prefs.devices:
        dev.use=dev.type=="METAL"
    require(any(d.use for d in prefs.devices),"No Cycles Metal device")
    scene.cycles.device="GPU"
    scene.cycles.samples=samples
    scene.cycles.adaptive_threshold=.039 if scale<100 else .024
    print(f"RENDER {view}",flush=True)
    bpy.ops.render.render(write_still=True)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=("build","render"))
    p.add_argument("--blend",type=Path,default=HERE/f"{NAME}.blend")
    p.add_argument("--view",choices=VIEWS,default="portrait")
    p.add_argument("--image",type=Path)
    p.add_argument("--scale",type=int,default=100)
    p.add_argument("--samples",type=int,default=64)
    a=p.parse_args(sys.argv[sys.argv.index("--")+1:])
    path=a.blend.resolve()
    if a.mode=="build":
        require(path not in (SOURCE.resolve(),PHOTO_SOURCE.resolve()),"Preserve upstream source assets")
        build(path)
    else:
        if not a.image:
            p.error("render requires --image")
        render(path,a.view,a.image.resolve(),a.scale,a.samples)
