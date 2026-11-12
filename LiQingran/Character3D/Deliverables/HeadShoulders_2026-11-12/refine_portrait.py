"""Refine the photo-fit head in the existing reference-camera coordinates."""

import argparse
import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import numpy as np

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "HeadShoulders_2026-09-30/LiQingran_HeadShoulders.blend"
NAME = "LiQingran_Sculpt"
HEAD = "PhotoFit_Head_and_Clean_Shoulders"
HAIR = "Retained_Hair_and_Accessories"
SCALP = "Scalp_Density_Underlayer"
VIEWS = {
    "matched": ("Reference_Matched_Approximate", (1170, 960)),
    "portrait": ("Portrait", (1092, 1248)),
    "clay": ("Sculpt / three quarter", (1000, 1100)),
    "profile": ("Sculpt / profile", (900, 1000)),
}
PIXELS = (780, 640)

# Guide endpoints are drawn in the original review frame. Every guide is laid
# against the three-dimensional scalp, starting inside the retained hair mass.
FRINGE_GUIDES = (
    (((421,184),(387,211),(370,262),(348,316)), 13, 4.5),
    (((421,185),(387,220),(378,269),(366,319)), 19, 5.2),
    (((423,186),(396,225),(386,266),(381,309)), 19, 6.0),
    (((423,187),(399,218),(399,272),(393,311)), 20, 5.3),
    (((424,185),(414,224),(415,273),(408,313)), 22, 5.6),
    (((425,182),(428,227),(429,266),(426,299)), 18, 6.4),
    (((426,184),(438,221),(446,265),(441,297)), 20, 5.9),
    (((427,185),(449,222),(466,258),(458,301)), 21, 6.1),
    (((428,185),(459,218),(475,250),(479,286)), 17, 5.4),
    (((423,188),(370,201),(344,255),(334,349)), 24, 5.5),
    (((394,207),(340,238),(334,284),(352,378)), 18, 5.1),
    (((428,183),(487,211),(514,248),(525,333)), 25, 6.1),
    (((434,185),(483,214),(523,252),(513,384)), 27, 5.0),
    (((437,190),(488,213),(542,266),(525,358)), 15, 4.7),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def smooth(low, high, value):
    t = np.clip((value-low)/(high-low),0,1)
    return t*t*(3-2*t)


def bell(pixels, center, radii):
    r = np.linalg.norm((pixels - center)/radii,axis=1)
    t = np.maximum(1-r,0)
    return t**4*(4*r+1)


def coords(mesh):
    values = np.empty((len(mesh.vertices),3),dtype=np.float32)
    mesh.vertices.foreach_get("co",values.ravel())
    return values


def transform(values, matrix):
    m = np.array(matrix)
    return values @ m[:3,:3].T + m[:3,3]


class PhotoView:
    def __init__(self, camera):
        self.matrix = camera.matrix_world.copy()
        self.inverse = self.matrix.inverted()
        self.scale = PIXELS[0]/camera.data.ortho_scale
        self.direction = self.matrix.to_3x3()@Vector((0,0,-1))

    def to_pixels(self, values, obj):
        q = transform(values,self.inverse@obj.matrix_world)
        return np.column_stack((q[:,0]*self.scale+PIXELS[0]/2,PIXELS[1]/2-q[:,1]*self.scale,q[:,2]))

    def ray(self,x,y):
        return self.matrix @ Vector(((x-PIXELS[0]/2)/self.scale,(PIXELS[1]/2-y)/self.scale,0))


def attr(mesh, name, data_type, values, field):
    attribute = mesh.attributes.new(name, data_type, "POINT")
    attribute.data.foreach_set(field, np.ascontiguousarray(values,dtype=np.float32).ravel())


def facial_sculpt(head, photo):
    initial = coords(head.data)
    pixels = photo.to_pixels(initial,head)
    uv, depth = pixels[:,:2],pixels[:,2]
    # These masks limit changes to the visible front surface. No symmetry is imposed.
    front = smooth(-2.84,-2.73,depth)
    nose = bell(uv,(452,394),(47,57))*front
    bridge = bell(uv,(440,366),(35,47))*front
    chin = bell(uv,(449,486),(86,66))*smooth(-2.9,-2.78,depth)
    left_jaw = bell(uv,(380,445),(64,92))*smooth(-2.9,-2.77,depth)
    right_jaw = bell(uv,(495,446),(60,86))*smooth(-2.91,-2.78,depth)
    lower_lid = (bell(uv,(379,358),(35,20))+bell(uv,(486,337),(37,20)))*front
    cheek = (bell(uv,(379,393),(49,47))+bell(uv,(503,378),(51,56)))*front

    shift = np.column_stack((
        (3.1*chin + 2.0*left_jaw - 1.7*right_jaw + .8*nose)/photo.scale,
        (6.8*chin + 1.7*lower_lid + .7*left_jaw)/photo.scale,
        -.015*nose - .0055*bridge - .023*chin - .0082*left_jaw - .0052*right_jaw + .0046*cheek + .0036*lower_lid,
    ))
    # Preserve existing globe geometry while reshaping the surrounding eyelid.
    eye_faces = [poly for poly in head.data.polygons if poly.material_index == 1]
    eye_ids = np.array(sorted({i for poly in eye_faces for i in poly.vertices}), dtype=int)
    require(500 < len(eye_ids) < 3000, "Fitted eye geometry changed upstream")
    shift[eye_ids] = 0
    delta = shift @ np.array((head.matrix_world.inverted() @ photo.matrix).to_3x3()).T
    shape = head.shape_key_add(name="Source • September photo fit",from_mix=False)
    require(len(shape.data)==len(initial),"Invalid base shape")
    sculpt = head.shape_key_add(name="November • cheeks, eyelids, nose and jaw",from_mix=False)
    sculpt.data.foreach_set("co",np.asarray(initial+delta,dtype=np.float32).ravel())
    sculpt.value = 1
    strongest = np.linalg.norm(delta,axis=1)
    require(40 < (strongest > .003).sum() and strongest.max() < .032,"Sculpt mask outside the review range")

    iris_coords = np.zeros_like(initial)
    right = uv[eye_ids,0]>432
    iris_coords[eye_ids,0] = (uv[eye_ids,0] - np.where(right,484.8,380.5))/14.4
    iris_coords[eye_ids,1] = (uv[eye_ids,1] - np.where(right,327.5,346.5))/15.8
    attr(head.data,"Iris_Plane","FLOAT_VECTOR",iris_coords,"vector")
    grade = .15 + .58*bell(uv,(455,384),(53,59)) + .20*bell(uv,(526,388),(29,53))
    grade += .22*bell(uv,(380,316),(47,22)) + .25*bell(uv,(489,299),(43,20))
    grade *= 1-.77*bell(uv,(450,439),(55,30))
    grade = np.clip(grade,0,.72)
    attr(head.data,"Photo_Highlight_Reduction","FLOAT",grade,"value")
    print(f"SCULPT changed={int(np.sum(strongest > .0001))} max_displacement={strongest.max():.5f}",flush=True)


def math_node(nodes, links, op, left, right=None):
    n = nodes.new("ShaderNodeMath")
    n.operation = op
    for index, value in enumerate((left,right)):
        if isinstance(value,bpy.types.NodeSocket):
            links.new(value,n.inputs[index])
        elif value is not None:
            n.inputs[index].default_value=value
    return n.outputs[0]


def color_mix(nodes, links, a, b, factor):
    node = nodes.new("ShaderNodeMixRGB")
    for index,value in enumerate((factor,a,b)):
        if isinstance(value,bpy.types.NodeSocket):
            links.new(value,node.inputs[index])
        else:
            node.inputs[index].default_value=value
    return node.outputs[0]


def attribute(nodes, name):
    n = nodes.new("ShaderNodeAttribute")
    n.attribute_name = name
    return n.outputs


def skin(head):
    for idx in (0,2):
        material = head.data.materials[idx]
        nodes,links=material.node_tree.nodes,material.node_tree.links
        bsdf=nodes.get("Principled BSDF")
        base=bsdf.inputs["Base Color"]
        if idx==0:
            source=base.links[0].from_socket
            mask=attribute(nodes,"Photo_Highlight_Reduction")["Fac"]
            toned=color_mix(nodes,links,source,(.448,.246,.189,1),mask)
            links.new(toned,base)
        else:
            base.default_value=(.445,.251,.198,1)
        bsdf.inputs["Roughness"].default_value=.53
        bsdf.inputs["Specular IOR Level"].default_value=.30
        bsdf.inputs["Subsurface Weight"].default_value=.115
        bsdf.inputs["Subsurface Radius"].default_value=(1,.43,.24)
        bsdf.inputs["Subsurface Scale"].default_value=.016
        geom=nodes.new("ShaderNodeTexCoord")
        pore=nodes.new("ShaderNodeTexNoise")
        pore.inputs["Scale"].default_value=1540
        pore.inputs["Detail"].default_value=2.0
        links.new(geom.outputs["Object"],pore.inputs["Vector"])
        bump=nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value=.16
        bump.inputs["Distance"].default_value=.00037
        links.new(pore.outputs["Fac"],bump.inputs["Height"])
        links.new(bump.outputs["Normal"],bsdf.inputs["Normal"])


def eyes(head):
    material=bpy.data.materials.new("Eyes • walnut iris and clear tear film")
    head.data.materials[1]=material
    nodes,links=material.node_tree.nodes,material.node_tree.links
    bsdf=nodes.get("Principled BSDF")
    eye=attribute(nodes,"Iris_Plane")["Vector"]
    v=nodes.new("ShaderNodeVectorMath"); v.operation="LENGTH"
    links.new(eye,v.inputs[0])
    radius=v.outputs["Value"]
    sep=nodes.new("ShaderNodeSeparateXYZ")
    links.new(eye,sep.inputs[0])
    angle=math_node(nodes,links,"ARCTAN2",sep.outputs["Y"],sep.outputs["X"])
    fiber=math_node(nodes,links,"SINE",math_node(nodes,links,"ADD",
        math_node(nodes,links,"MULTIPLY",angle,53), math_node(nodes,links,"MULTIPLY",radius,5.2)))
    subfiber=math_node(nodes,links,"SINE",math_node(nodes,links,"MULTIPLY",angle,83))
    variation=math_node(nodes,links,"ADD",math_node(nodes,links,"MULTIPLY",fiber,.30),
                        math_node(nodes,links,"ADD",.48,math_node(nodes,links,"MULTIPLY",subfiber,.18)))
    iris=color_mix(nodes,links,(.014,.0062,.0035,1),(.062,.026,.012,1),variation)
    ramp=nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position=.44
    ramp.color_ramp.elements[0].color=(0,0,0,1)
    ramp.color_ramp.elements[1].position=.575
    ramp.color_ramp.elements[1].color=(1,1,1,1)
    links.new(radius,ramp.inputs["Fac"])
    iris=color_mix(nodes,links,(.0026,.0016,.0013,1),iris,ramp.outputs[0])
    ramp2=nodes.new("ShaderNodeValToRGB")
    ramp2.color_ramp.elements[0].position=.81
    ramp2.color_ramp.elements[1].position=1
    links.new(radius,ramp2.inputs["Fac"])
    iris=color_mix(nodes,links,iris,(.010,.0058,.0044,1),ramp2.outputs[0])
    rim=nodes.new("ShaderNodeMapRange")
    rim.inputs["From Min"].default_value=.94
    rim.inputs["From Max"].default_value=1.045
    links.new(radius,rim.inputs["Value"])
    whites=nodes.new("ShaderNodeMapRange")
    whites.inputs["From Min"].default_value=1.2
    whites.inputs["From Max"].default_value=2.25
    links.new(radius,whites.inputs["Value"])
    sclera=color_mix(nodes,links,(.294,.247,.220,1),(.162,.091,.077,1),whites.outputs[0])
    links.new(color_mix(nodes,links,iris,sclera,rim.outputs[0]),bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value=.166
    bsdf.inputs["Specular IOR Level"].default_value=.39
    bsdf.inputs["Coat Weight"].default_value=.19
    bsdf.inputs["Coat Roughness"].default_value=.10
    bsdf.inputs["IOR"].default_value=1.385


def fringe_mesh(obj, photo, protected_material=False):
    co=coords(obj.data)
    pixels=photo.to_pixels(co,obj)
    x,y,depth=pixels.T
    brow_gap=smooth(317,356,x)*(1-smooth(488,521,x))
    front=smooth(-2.822,-2.727,depth)
    ends=smooth(223,317,y)*(1-smooth(340,368,y))
    irregular=38+5.2*np.sin(x*.081)+4.8*np.sin(x*.152+1.4)
    w=brow_gap*front*ends
    if protected_material:
        ornament_vertices=np.fromiter(
            {i for p in obj.data.polygons if p.material_index==0 for i in p.vertices},dtype=np.int32
        )
        w[ornament_vertices]=0
    local_delta=np.column_stack((np.zeros_like(w),w*irregular/photo.scale,-.0034*w))
    co+=np.asarray(local_delta@np.array((obj.matrix_world.inverted()@photo.matrix).to_3x3()).T,dtype=np.float32)
    obj.data.vertices.foreach_set("co",co.ravel())
    obj.data.update()


def evaluated_bvh(obj):
    depsgraph=bpy.context.evaluated_depsgraph_get()
    evaluated=obj.evaluated_get(depsgraph)
    mesh=evaluated.to_mesh()
    try:
        points=[evaluated.matrix_world@vertex.co for vertex in mesh.vertices]
        mesh.calc_loop_triangles()
        return BVHTree.FromPolygons(points,[t.vertices[:] for t in mesh.loop_triangles],all_triangles=True)
    finally:
        evaluated.to_mesh_clear()


def groom(head, hair, photo, collection):
    head_bvh=evaluated_bvh(head)
    hair_bvh=evaluated_bvh(hair)
    shades=((.009,.0049,.0032),(.015,.0081,.0049),(.024,.013,.0073))
    materials=[]
    for i,color in enumerate(shades):
        material=bpy.data.materials.new(f"Fringe • dark silk {i+1}")
        b=material.node_tree.nodes.get("Principled BSDF")
        b.inputs["Base Color"].default_value=(*color,1)
        b.inputs["Roughness"].default_value=.53+i*.024
        b.inputs["Specular IOR Level"].default_value=.23
        b.inputs["Anisotropic"].default_value=.39
        materials.append(material)
    rng=random.Random(184)
    t=np.linspace(0,1,34)
    basis=np.column_stack(((1-t)**3,3*(1-t)**2*t,3*(1-t)*t*t,t**3))
    for index,(guide,count,width) in enumerate(FRINGE_GUIDES):
        data=bpy.data.curves.new(f"Fringe guide {index+1:02d}","CURVE")
        data.dimensions="3D"
        data.bevel_depth=.00115 if index<9 else .00082
        data.bevel_resolution=1
        for material in materials:
            data.materials.append(material)
        count = int(count*1.62) if index<9 else count
        for j in range(count):
            control=np.asarray(guide,dtype=float).copy()
            offset=(2*j/(count-1)-1)*width
            control[:,0]+=np.array([.31,.72,1.04,.76])*offset
            control[-1,1]+=rng.uniform(-8,7)
            xy=basis@control
            points=[]
            previous_distance=2.72
            for k,((x,y),u) in enumerate(zip(xy,t)):
                origin=photo.ray(x,y)
                _,_,_,scalp=head_bvh.ray_cast(origin,photo.direction,2.89)
                _,_,_,strand=hair_bvh.ray_cast(origin,photo.direction,2.88)
                h=(scalp-.0048-.007*math.sin(math.pi*u)) if scalp is not None else previous_distance
                if strand is not None:
                    target=min(strand+.0018,h)
                    # Roots lie under the existing strand shell. Tips emerge with clearance.
                    h=target + (.0022*(1-u)**5-.0020*u)
                elif k==0:
                    h-=.002
                previous_distance=h
                points.append(np.array(origin + photo.direction*h))
            points=np.asarray(points)
            for _ in range(4):
                points[1:-1]=.24*points[:-2]+.52*points[1:-1]+.24*points[2:]
            spline=data.splines.new("POLY")
            spline.points.add(len(points)-1)
            spline.material_index=rng.choices((0,1,2),weights=(7,2.6,.4))[0]
            thickness=rng.uniform(.57,1.38)
            for point,p,u in zip(spline.points,points,t):
                point.co=(*p,1)
                point.radius=thickness*(.075+.925*(1-u)**.62)*(.55+.45*min(1,u*15))
        obj=bpy.data.objects.new(data.name,data)
        collection.objects.link(obj)
        obj["reference_guides_px"]=str(guide)



def lashes(head, photo, collection):
    evaluated = head.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        tris = [tuple(t.vertices) for t in mesh.loop_triangles]
        is_eye = [mesh.polygons[t.polygon_index].material_index == 1 for t in mesh.loop_triangles]
        tree = BVHTree.FromPolygons([evaluated.matrix_world @ v.co for v in mesh.vertices],tris,all_triangles=True)
    finally:
        evaluated.to_mesh_clear()
    data = bpy.data.curves.new("Upper eyelash curves","CURVE")
    data.dimensions="3D"
    data.bevel_depth=.00057
    data.bevel_resolution=2
    data.materials.append(bpy.data.materials["Fringe • dark silk 1"])
    rng = random.Random(729)
    for start,end,top,sign in ((350,403,326,-1),(465,514,305,1)):
        for i,x in enumerate(np.linspace(start,end,25)):
            previous = None
            for y in np.linspace(top,top+34,87):
                origin = photo.ray(x,y)
                _, _, index, distance = tree.ray_cast(origin,photo.direction,3.0)
                if index is not None and is_eye[index]:
                    if previous is None:
                        break
                    base_x,base_y,base_depth = x,y-.38,previous
                    length = rng.uniform(2.8,6.8) * (.63+.37*math.sin(math.pi*i/25))
                    spline=data.splines.new("POLY")
                    spline.points.add(7)
                    for n,point in enumerate(spline.points):
                        t=n/7
                        origin=photo.ray(base_x+sign*length*.55*t,base_y-length*(.18*t+.62*t*t))
                        point.co=(*(origin + photo.direction*(base_depth-.0003-.0047*t)),1)
                        point.radius=.95*(1-t)**.73+.03
                    break
                previous=distance
    require(len(data.splines)>=24,"Could not attach lashes to both visible upper lids")
    obj=bpy.data.objects.new(data.name,data)
    collection.objects.link(obj)
    print(f"LASHES count={len(data.splines)}",flush=True)



def eyebrows(head, photo, collection):
    surface=evaluated_bvh(head)
    data=bpy.data.curves.new("Eyebrow fibers","CURVE")
    data.dimensions="3D"
    data.bevel_depth=.00035
    data.bevel_resolution=1
    data.materials.append(bpy.data.materials["Fringe • dark silk 1"])
    rng=random.Random(5492)
    for xs,ys,sign in (((348,366,384,404),(323,315,312,316),-1),
                       ((458,479,498,519),(308,301,296,304),1)):
        for _ in range(218):
            x=rng.uniform(xs[0],xs[-1])
            t=(x-xs[0])/(xs[-1]-xs[0])
            density=math.sin(math.pi*t)**.48
            y=float(np.interp(x,xs,ys))+rng.gauss(0,1.52)*density
            length=rng.uniform(1.8,5.0)*(.55+.45*density)
            points=[]
            for a in np.linspace(0,1,6):
                origin=photo.ray(x+sign*a*length*.74,y-length*(.82*a-.27*a*a))
                _,_,_,depth=surface.ray_cast(origin,photo.direction,2.86)
                if depth is None:
                    break
                points.append(origin+photo.direction*(depth-.00047-.00043*a))
            if len(points)<6:
                continue
            spline=data.splines.new("POLY")
            spline.points.add(len(points)-1)
            for i,(point,position) in enumerate(zip(spline.points,points)):
                point.co=(*position,1)
                point.radius=(.11+.82*(1-i/5)**.73)*rng.uniform(.83,1.15)
    require(len(data.splines)>=230,"Could not seat brow fibers on the front surface")
    collection.objects.link(bpy.data.objects.new(data.name,data))

def backdrop(scene, camera):
    basis = camera.rotation_euler.to_matrix()
    center = camera.location + basis @ Vector((0,0,-4.7))
    mesh = bpy.data.meshes.new("Portrait backdrop")
    mesh.from_pydata([center + basis @ Vector((x,y,0)) for x,y in ((-1,-1),(1,-1),(1,1),(-1,1))],[],[(0,1,2,3)])
    uv=mesh.uv_layers.new()
    for item,coord in zip(uv.uv,((0,0),(1,0),(1,1),(0,1))):
        item.vector=coord
    obj=bpy.data.objects.new(mesh.name,mesh)
    scene.collection.objects.link(obj)
    obj.visible_shadow=False
    obj.visible_diffuse=False
    obj.visible_glossy=False
    obj.visible_transmission=False
    obj.hide_set(True)
    mat=bpy.data.materials.new("Portrait backdrop • blue-green")
    mesh.materials.append(mat)
    nodes,links=mat.node_tree.nodes,mat.node_tree.links
    nodes.clear()
    coord=nodes.new("ShaderNodeTexCoord")
    distance=nodes.new("ShaderNodeVectorMath")
    distance.operation="DISTANCE"
    distance.inputs[1].default_value=(.61,.63,0)
    links.new(coord.outputs["UV"],distance.inputs[0])
    ramp=nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation="EASE"
    ramp.color_ramp.elements[0].color=(.080,.156,.153,1)
    ramp.color_ramp.elements[1].position=.52
    ramp.color_ramp.elements[1].color=(.009,.025,.028,1)
    links.new(distance.outputs["Value"],ramp.inputs["Fac"])
    emission=nodes.new("ShaderNodeEmission")
    links.new(ramp.outputs["Color"],emission.inputs["Color"])
    output=nodes.new("ShaderNodeOutputMaterial")
    links.new(emission.outputs["Emission"],output.inputs["Surface"])

def camera(scene, name, location, target, size):
    data=bpy.data.cameras.new(name)
    data.type="ORTHO"
    data.ortho_scale=size
    obj=bpy.data.objects.new(name,data)
    scene.collection.objects.link(obj)
    obj.location=location
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()
    return obj


def area(light, loc, target, watts, color, size):
    light.location=loc
    light.rotation_euler=(Vector(target)-light.location).to_track_quat("-Z","Y").to_euler()
    light.data.energy,light.data.color,light.data.size=watts,color,size


def studio(scene, mode):
    world=scene.world
    nodes,links=world.node_tree.nodes,world.node_tree.links
    nodes.clear()
    background=nodes.new("ShaderNodeBackground")
    background.inputs["Color"].default_value=(.54,.61,.66,1)
    background.inputs["Strength"].default_value=.26 if mode=="portrait" else .45
    screen=nodes.new("ShaderNodeBackground")
    screen.inputs["Color"].default_value=(.033,.076,.076,1) if mode=="portrait" else (.122,.122,.122,1)
    screen.inputs["Strength"].default_value=.65
    lp=nodes.new("ShaderNodeLightPath")
    mix=nodes.new("ShaderNodeMixShader")
    links.new(lp.outputs["Is Camera Ray"],mix.inputs[0])
    links.new(background.outputs[0],mix.inputs[1])
    links.new(screen.outputs[0],mix.inputs[2])
    output=nodes.new("ShaderNodeOutputWorld")
    links.new(mix.outputs[0],output.inputs[0])
    key=bpy.data.objects["Studio_Key"]
    fill=bpy.data.objects["Studio_Fill"]
    rim=bpy.data.objects["Studio_Rim"]
    rim.data.specular_factor=.40
    fill.data.specular_factor=.55
    if mode=="portrait":
        area(key,(.80,-1.16,1.54),(.02,-.13,.58),106,(1,.90,.80),1.03)
        area(fill,(-1.35,-.98,.81),(.03,0,.52),43,(.73,.89,1),1.16)
        area(rim,(-.52,.97,1.32),(0,0,.59),58,(.74,.87,1),1.18)
    else:
        area(key,(.74,-1.12,1.45),(.02,-.12,.56),101,(1,.97,.95),1.11)
        area(fill,(-1.23,-1.0,1.04),(.03,0,.55),55,(.92,.97,1),1.23)
        area(rim,(.12,1.04,1.39),(0,0,.60),33,(.96,.98,1),1.25)


def build(path):
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE),load_ui=False,use_scripts=False)
    scene=bpy.context.scene
    scene.name="Li Qingran / portrait sculpt"
    bpy.context.view_layer.update()
    photo=PhotoView(bpy.data.objects[VIEWS["matched"][0]])
    head=bpy.data.objects[HEAD]
    hair=bpy.data.objects[HAIR]
    scalp=bpy.data.objects[SCALP]
    facial_sculpt(head,photo)
    skin(head)
    eyes(head)
    fringe_mesh(hair,photo,protected_material=True)
    fringe_mesh(scalp,photo)
    hair_bsdf=hair.data.materials[1].node_tree.nodes.get("Principled BSDF")
    hair_bsdf.inputs["Base Color"].default_value=(.0090,.0056,.0037,1)
    hair_bsdf.inputs["Roughness"].default_value=.54
    hair_bsdf.inputs["Specular IOR Level"].default_value=.18
    hair_bsdf.inputs["Anisotropic"].default_value=.24
    hair_bsdf.inputs["IOR"].default_value=1.37
    hair_nodes=hair.data.materials[1].node_tree.nodes
    hair_links=hair.data.materials[1].node_tree.links
    diffuse=hair_nodes.new("ShaderNodeBsdfDiffuse")
    diffuse.inputs["Color"].default_value=(.0108,.0064,.0042,1)
    diffuse.inputs["Roughness"].default_value=.43
    lobes=hair_nodes.new("ShaderNodeMixShader")
    lobes.inputs[0].default_value=.43
    hair_links.new(diffuse.outputs[0],lobes.inputs[1])
    hair_links.new(hair_bsdf.outputs[0],lobes.inputs[2])
    hair_links.new(lobes.outputs[0],hair_nodes.get("Material Output").inputs["Surface"])
    bpy.context.view_layer.update()
    fringe=bpy.data.collections.new("Editable fringe and temple strands")
    scene.collection.children.link(fringe)
    groom(head,hair,photo,fringe)
    lashes(head,photo,fringe)
    eyebrows(head,photo,fringe)
    hero=camera(scene,VIEWS["portrait"][0],(.82,-2.76,.73),(.013,-.02,.578),1.02)
    camera(scene,VIEWS["clay"][0],(1.8,-2.65,.71),(.015,0,.562),1.11)
    camera(scene,VIEWS["profile"][0],(3.2,-.085,.574),(.014,-.03,.565),1.10)
    scene.camera=hero
    backdrop(scene,hero)
    scene.render.engine="CYCLES"
    scene.cycles.device="CPU"
    scene.cycles.samples=64
    scene.cycles.use_denoising=True
    scene.render.resolution_x,scene.render.resolution_y=VIEWS["portrait"][1]
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"
    scene.render.filepath="//Preview/Portrait.png"
    scene.view_settings.view_transform="AgX"
    scene.view_settings.look="AgX - Medium High Contrast"
    scene.view_settings.exposure=.03
    scene["candidate_status"]="Static portrait candidate for likeness review"
    scene["source"]="2026-09-30 photo-fitted and assembled head"
    studio(scene,"portrait")
    for screen in bpy.data.screens:
        for ui in screen.areas:
            if ui.type=="VIEW_3D":
                ui.spaces.active.region_3d.view_perspective="CAMERA"
                ui.spaces.active.shading.type="SOLID"
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True,relative_remap=False)


def render(path, view, output, scale, samples):
    bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
    scene=bpy.context.scene
    name, size=VIEWS[view]
    scene.camera=bpy.data.objects[name]
    scene.render.resolution_x,scene.render.resolution_y=size
    scene.render.resolution_percentage=scale
    scene.render.filepath=str(output)
    studio(scene,view)
    bpy.data.objects["Portrait backdrop"].hide_render = view != "portrait"
    if view in ("clay","profile"):
        clay=bpy.data.materials.new("Neutral sculpt inspection")
        bsdf=clay.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value=(.46,.44,.41,1)
        bsdf.inputs["Roughness"].default_value=.58
        for slot in bpy.data.objects[HEAD].material_slots:
            slot.material=clay
    prefs=bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type="METAL"
    prefs.refresh_devices()
    for dev in prefs.devices:
        dev.use=dev.type=="METAL"
    require(any(d.use for d in prefs.devices),"Cycles Metal device unavailable")
    scene.cycles.device="GPU"
    scene.cycles.samples=samples
    scene.cycles.adaptive_threshold=.045 if scale<100 else .020
    print(f"RENDER {view} {[d.name for d in prefs.devices if d.use]} {samples} samples",flush=True)
    bpy.ops.render.render(write_still=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=("build","render"))
    parser.add_argument("--blend",type=Path,default=HERE/f"{NAME}.blend")
    parser.add_argument("--view",choices=VIEWS,default="portrait")
    parser.add_argument("--image",type=Path)
    parser.add_argument("--scale",type=int,default=100)
    parser.add_argument("--samples",type=int,default=56)
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    if args.mode=="build":
        require(args.blend.resolve()!=SOURCE.resolve(),"Preserve the source blend")
        build(args.blend.resolve())
    else:
        render(args.blend.resolve(),args.view,args.image.resolve(),args.scale,args.samples)
