"""Editable scalp, fringe, temple flow, and eyelashes for the fitted portrait."""

import math

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import numpy as np

from portrait_source import HAIR_COLLECTION
from refine_portrait import evaluated_bvh, require, smooth
import groom_portrait as groom

SCALP_SHAPE = (160, 57)
FRINGE=(
    ((416,169),(369,194),(344,265),(335,366),11),
    ((416,170),(371,197),(352,258),(346,349),13),
    ((417,171),(376,204),(366,257),(363,337),14),
    ((418,171),(386,213),(383,262),(377,326),12),
    ((419,170),(397,211),(392,266),(390,318),11),
    ((420,170),(407,218),(405,267),(405,319),12),
    ((421,170),(418,216),(421,270),(417,318),13),
    ((423,168),(430,215),(438,267),(433,315),13),
    ((424,167),(445,210),(451,257),(449,310),10),
    ((425,168),(453,200),(468,242),(472,284),9),
    ((426,170),(440,202),(460,255),(461,313),5),
    ((426,169),(473,194),(498,253),(513,323),11),
    ((426,170),(476,200),(505,260),(523,350),13),
    ((428,172),(491,210),(530,266),(528,381),13),
    ((429,173),(503,215),(542,284),(512,401),10),
    ((416,172),(359,201),(323,258),(320,353),13),
    ((419,172),(388,218),(339,273),(347,380),8),
    ((410,166),(366,165),(326,190),(302,313),15),
    ((400,172),(353,171),(312,216),(304,333),14),
    ((416,168),(368,183),(330,228),(322,327),12),
    ((425,167),(464,163),(514,191),(546,284),15),
    ((442,166),(485,168),(524,219),(543,311),14),
    ((428,170),(480,182),(521,229),(535,326),12),
    ((403,168),(331,168),(255,228),(287,358),16),
    ((407,169),(343,175),(271,232),(300,367),15),
    ((422,163),(489,159),(568,209),(558,314),14),
    ((430,167),(502,173),(578,220),(548,332),13),
)


def groom_warp(obj,photo):
    crown=obj.name.startswith(("Scalp underlayer","Crown flow","Crown parting","Gathered strands"))
    length=obj.name.startswith(("Length fibers","Hanging hair"))
    bun=obj.name.startswith(("Gathered knot","Knot wrap","Tied hair at the base"))
    if not (crown or length or bun):
        return
    if obj.type=="MESH":
        field=obj.data.vertices
        key="co"
    else:
        field=obj.data.attributes["position"].data
        key="vector"
    local=np.empty((len(field),3),dtype=np.float32)
    field.foreach_get(key,local.ravel())
    pix=photo.to_pixels(local,obj)
    x,y,_=pix.T
    if crown:
        mask=smooth(124,175,y)*(1-smooth(211,314,y))
        dx=(x-416)*(.173*mask+.023*smooth(155,197,y)*(1-smooth(283,342,y)))
        shoulder=smooth(150,220,y)*(1-smooth(257,349,y))
        dx+=((x-416)*(.069+.037*(1-smooth(258,390,x)))-2.9)*shoulder
        lift=(1-smooth(152,235,y))*smooth(119,151,y)
        dy=-12.0*lift
        if obj.name.startswith("Gathered strands"):
            knot_shift=1-smooth(101,139,y)
            dx+=((x-391)*.14-8)*knot_shift
            dy-=4*knot_shift
    elif bun:
        knot_shift=1-smooth(102,145,y)
        dx=((x-391)*.14-8)*knot_shift
        dy=-4*knot_shift
    else:
        mask=smooth(322,470,y)
        dx=(x-428)*(.147*mask)-8.2*smooth(404,586,y)
        dy=np.zeros_like(dx)
    delta=np.column_stack((dx/photo.scale,-dy/photo.scale,np.zeros_like(dx)))
    basis=np.array((obj.matrix_world.inverted()@photo.matrix).to_3x3())
    local+=np.asarray(delta@basis.T,dtype=np.float32)
    field.foreach_set(key,local.ravel())
    if obj.type=="MESH":
        obj.data.update()


def comb_fringe(photo, skull, cap, group, materials):
    """Follow the cap and skin without inheriting a ray miss from the prior sample."""
    rng=np.random.default_rng(511)
    t=np.linspace(0,1,51)
    for index,guide in enumerate(FRINGE):
        controls=np.asarray(guide[:4],dtype=float)
        width=guide[4]
        side_sweep=index>=len(FRINGE)-10
        count=round(width*(10 if side_sweep else 11))
        points=np.empty((count,len(t),3))
        for i in range(count):
            anchors=controls.copy()
            offset=np.clip(rng.normal(0,width*.49),-width*1.1,width*1.1)
            anchors[:,0]+=offset*np.array((.58,.81,1,.94))+rng.uniform(-2.8,2.8,4)
            anchors[0,1]+=rng.uniform(-3.0,4.2)
            central = 1 - smooth(28, 84, abs(controls[-1, 0] - 406))
            anchors[-1, 1] += rng.normal(0, 11.6) - 6.0 * central
            u=t+rng.uniform(.01,.19 if side_sweep else .115)*(1-t)
            basis=np.column_stack(((1-u)**3,3*(1-u)**2*u,3*(1-u)*u*u,u**3))
            px=basis@anchors
            roots=[photo.ray(x,y) for x,y in px]
            cap_dist=np.array([cap.ray_cast(ray,photo.direction,2.98)[3] for ray in roots],dtype=float)
            skin_dist=np.array([skull.ray_cast(ray,photo.direction,2.95)[3] for ray in roots],dtype=float)
            lift=rng.uniform(.0017,.0070)*(.59+.41*np.sin(t*np.pi))
            envelope=np.fmin(cap_dist-.0009-lift*.66,skin_dist-lift)
            hit=np.isfinite(envelope)
            require(hit.sum()>=9,f"Fringe guide {index+1} does not follow the head")
            d=np.interp(t,t[hit],envelope[hit])
            # Relax sharp changes at the cap edge across neighboring samples.
            # The one-sided constraint keeps the fiber from tunneling into skin.
            bound=np.where(hit,envelope+.001,np.inf)
            for _ in range(24):
                d[1:-1]=np.minimum(d[1:-1]*.42+.29*(d[:-2]+d[2:]),bound[1:-1])
            # Bury roots gradually and leave the last few millimetres free.
            d+=.0028*(1-t)**15-.0017*t**7
            points[i]=np.array(roots)+d[:,None]*np.array(photo.direction)
        groom.hair(f"Fringe lock {index+1:02d}",points,groom.radii(rng,count,t,.00011,.00034),
                   materials[index%len(materials)],group)


def relax_hairline(cap,skull):
    """Keep crown volume and taper its lower section to the forehead and temples."""
    grid=np.empty((len(cap.data.vertices),3),dtype=np.float32)
    cap.data.vertices.foreach_get("co",grid.ravel())
    grid = grid.reshape(*SCALP_SHAPE, 3)
    center=np.array((-.019,-.062,.603))
    a=np.abs(np.linspace(-np.pi,np.pi,len(grid),endpoint=False))[:,None]
    s=np.linspace(0,1,grid.shape[1])[None,:]
    blend=smooth(.43,.94,s)*(.83+.17*smooth(.40,1.17,a))*(1-smooth(1.87,2.63,a))
    for _ in range(3):
        across=(np.roll(grid,4,axis=0)+np.roll(grid,-4,axis=0))*.5
        grid+=.29*blend[...,None]*(across-grid)
    for i,j in zip(*np.where(blend>.002)):
        d=grid[i,j]-center
        d/=np.linalg.norm(d)
        direction=Vector(d)
        p,_,_,_=skull.ray_cast(Vector(center)+direction*.73,-direction,.729)
        require(p is not None,"Temporal scalp is detached from the fitted skull")
        desired=np.array(p)+d*(.0028+.0054*(1-s[0,j]))
        grid[i,j]+=(desired-grid[i,j])*(.97*blend[i,j])
    cap.data.vertices.foreach_set("co",grid.ravel())
    cap.data.update()
    return center,grid


def comb_scalp(grid, center, group, materials):
    """One continuous comb field connects the crown to the temples and nape."""
    rng = np.random.default_rng(521)
    steps = np.linspace(0, 1, 56)[None, :]
    bend = np.sin(np.pi * steps)
    for index, (count, material) in enumerate(zip((7150, 3440, 1550), materials, strict=True)):
        angle_end = rng.uniform(-np.pi, np.pi, (count, 1))
        front = 1 - smooth(1.13, 2.10, abs(angle_end))
        # Spread the parting at the forehead and blend into the rearward sweep.
        angle_root = angle_end * (.81 - .47 * front)
        angle_root += rng.normal(-.036, .101, (count, 1))
        angle = angle_root + (angle_end - angle_root) * steps ** .87
        angle += (.095 * np.sin(2 * angle_end) + rng.normal(0, .025, (count, 1))) * bend
        root = rng.uniform(.012, .225, (count, 1))
        end = rng.uniform(.79, .999, (count, 1))
        track = root + (end - root) * steps ** 1.12
        points = groom.sample_grid(grid, angle, track)
        normal = points - center
        normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
        lift = rng.uniform(.0004, .0027, (count, 1)) + rng.uniform(.0006, .0023, (count, 1)) * bend
        points += normal * lift[..., None]
        radius = groom.radii(rng, count, steps, .00013, .00034)
        groom.hair(f"Continuous scalp comb {index + 1}", points, radius, material, group)


def hairline(head,photo):
    group=bpy.data.collections[HAIR_COLLECTION]
    for obj in list(group.objects):
        if obj.name.startswith(("Fringe lock","Crown flow","Crown parting")):
            bpy.data.objects.remove(obj,do_unlink=True)
        else:
            groom_warp(obj,photo)
    bpy.context.view_layer.update()
    cap=bpy.data.objects["Scalp underlayer • fitted hairline"]
    skull=evaluated_bvh(head)
    center,grid=relax_hairline(cap,skull)
    cap.data.calc_loop_triangles()
    cap_surface=BVHTree.FromPolygons([cap.matrix_world@v.co for v in cap.data.vertices],
        [tri.vertices[:] for tri in cap.data.loop_triangles],all_triangles=True)
    materials=[bpy.data.materials[f"Natural black fiber {i}"] for i in (1,2,3)]
    comb_scalp(grid, center, group, materials)
    comb_fringe(photo, skull, cap_surface, group, materials)
    tune_black_fibers(group)
    feather_scalp_support(cap)
    print("GROOM",sum(len(o.data.curves) for o in group.objects if o.type=="CURVES"),flush=True)


def tune_black_fibers(group):
    materials = {obj.data.materials[0] for obj in group.objects if obj.type == "CURVES"}
    for material in sorted(materials, key=lambda item: item.name):
        nodes = material.node_tree.nodes
        fiber = next(node for node in nodes if node.type == "BSDF_HAIR_PRINCIPLED")
        diffuse = next(node for node in nodes if node.type == "BSDF_DIFFUSE")
        mix = next(node for node in nodes if node.type == "MIX_SHADER")
        color = tuple(fiber.inputs["Color"].default_value)
        darker = (color[0] * .60, color[1] * .65, color[2] * .71, 1)
        fiber.inputs["Color"].default_value = darker
        diffuse.inputs["Color"].default_value = darker
        fiber.inputs["Roughness"].default_value = .40
        fiber.inputs["Radial Roughness"].default_value = .52
        mix.inputs[0].default_value = .57


def feather_scalp_support(cap):
    """Let the visible strand tips define the hairline at the temple."""
    azimuths = np.abs(np.linspace(-np.pi, np.pi, SCALP_SHAPE[0], endpoint=False))[:, None]
    rows = np.linspace(0, 1, SCALP_SHAPE[1])[None, :]
    front = 1 - smooth(1.55, 2.19, azimuths)
    feather = np.asarray(front * smooth(.82, .998, rows), dtype=np.float32)
    attribute = cap.data.attributes.new("Scalp edge fade", "FLOAT", "POINT")
    attribute.data.foreach_set("value", feather.ravel())

    material = cap.data.materials[0].copy()
    material.name = "Scalp backing with a soft edge"
    cap.data.materials[0] = material
    nodes, links = material.node_tree.nodes, material.node_tree.links
    output = nodes["Material Output"]
    fade = nodes.new("ShaderNodeAttribute")
    fade.attribute_name = attribute.name
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    links.new(fade.outputs["Fac"], mix.inputs[0])
    links.new(nodes["Principled BSDF"].outputs[0], mix.inputs[1])
    links.new(transparent.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs["Surface"])



def lashes(head,photo,scene):
    group=bpy.data.collections.new("Eyelashes seated along both fitted eyes")
    scene.collection.children.link(group)
    surface=head.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data=surface.to_mesh()
    try:
        data.calc_loop_triangles()
        ocular=[data.polygons[t.polygon_index].material_index==1 for t in data.loop_triangles]
        bvh=BVHTree.FromPolygons([surface.matrix_world@v.co for v in data.vertices],
             [t.vertices[:] for t in data.loop_triangles],all_triangles=True)
    finally:
        surface.to_mesh_clear()
    rng=np.random.default_rng(91)
    points=[]
    lengths=[]
    ts=np.linspace(0,1,14)
    for xmin,xmax,ymin,ymax,side in ((351.5,402.9,330,366,-1),(466,515.8,307,346,1)):
        for upper in (True,False):
            density=30 if upper else 11
            for idx,x in enumerate(np.linspace(xmin,xmax,density)):
                x+=float(rng.uniform(-.37,.37))
                found=[]
                for y in np.arange(ymin,ymax,.50):
                    _,_,i,d=bvh.ray_cast(photo.ray(float(x),float(y)),photo.direction,2.945)
                    if i is not None and ocular[i]:
                        found.append((float(y),d))
                if len(found)<4:
                    continue
                y,_=(found[0] if upper else found[-1])
                y+=-.57 if upper else .55
                point,_,_,d=bvh.ray_cast(photo.ray(float(x),y),photo.direction,2.945)
                if point is None:
                    continue
                outer=(1-idx/(density-1)) if side<0 else idx/(density-1)
                length=float(rng.uniform(2.45,4.20))*(.68+.54*outer) if upper else float(rng.uniform(1.02,2.52))
                positions=[]
                for t in ts:
                    v=float(t)
                    xx=float(x+side*length*.70*v**1.55)
                    yy=float(y+(-1 if upper else 1)*length*(.52*v+.48*v*v))
                    p=photo.ray(xx,yy)+photo.direction*(d-.00031-.0032*v-.0013*math.sin(v*math.pi*.88))
                    positions.append(tuple(p))
                points.append(positions)
                lengths.append(length)
    require(len(points)>=56,"Too few eyelash roots seated on the geometry")
    material=groom.fiber_material("Short lash fibers",(.009,.0047,.0041))
    radii=np.asarray(lengths)[:,None]*.000077*(.16+.84*(1-ts)**.67)
    groom.hair("Tapered upper and lower eyelash fibers",np.array(points),radii,material,group)
