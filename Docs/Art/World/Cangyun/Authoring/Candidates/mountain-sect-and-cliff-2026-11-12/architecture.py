"""Shared solids, railings, pantile roofs, and stone lanterns."""

import math

import bpy
from mathutils import Vector
import numpy as np

from landscape import grid, mesh_object, require


def box(name, position, dimensions, target, material, bevel=.003):
    """Build local solid geometry without re-evaluating the full scene for each slab."""
    require(min(dimensions)>0,f"Nonpositive box dimensions: {name}")
    x,y,z=np.asarray(dimensions)*.5
    corners=((-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),
             (-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z))
    faces=((3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7))
    obj=mesh_object(name,corners,faces,target,material,"architectural_solid")
    obj.location=position
    if bevel:
        edge=obj.modifiers.new("Bevel on worn edges","BEVEL")
        edge.width=min(bevel,min(dimensions)*.35)
        edge.segments=2
    return obj


def beam(name, start, end, radius, target, material, vertices=12):
    a,b=Vector(start),Vector(end)
    span=b-a
    require(span.length>0 and radius>0,f"Nonpositive beam dimensions: {name}")
    profile=[(radius*math.cos(t),radius*math.sin(t)) for t in np.linspace(0,math.tau,vertices,endpoint=False)]
    coords=[(x,y,z) for z in (-span.length*.5,span.length*.5) for x,y in profile]
    faces=[(i,(i+1)%vertices,vertices+(i+1)%vertices,vertices+i) for i in range(vertices)]
    faces.extend((tuple(reversed(range(vertices))),tuple(range(vertices,vertices*2))))
    obj=mesh_object(name,coords,faces,target,material,"beam")
    obj.location=(a+b)*.5
    obj.rotation_mode="QUATERNION"
    obj.rotation_quaternion=span.to_track_quat("Z","Y")
    if vertices>8:
        for p in obj.data.polygons:
            p.use_smooth=p.index<vertices
    return obj


def flagstone(name, position, dimensions, target, material, rng):
    """Cut small irregular corners into a traversable slab."""
    require(min(dimensions) > 0, f"Nonpositive slab dimensions: {name}")
    x, y, half_height = np.asarray(dimensions) * .5
    chip = [min(x, y) * rng.uniform(.08, .27) for _ in range(4)]
    outline = ((-x + chip[0], -y), (x - chip[1], -y), (x, -y + chip[1]), (x, y - chip[2]),
               (x - chip[2], y), (-x + chip[3], y), (-x, y - chip[3]), (-x, -y + chip[0]))
    vertices = [(u, v, -half_height) for u, v in outline]
    vertices.extend((u, v, half_height + rng.uniform(-.006, .004)) for u, v in outline)
    count = len(outline)
    faces = [tuple(reversed(range(count))), tuple(range(count, 2 * count))]
    faces.extend((i, (i + 1) % count, count + (i + 1) % count, count + i) for i in range(count))
    slab = mesh_object(name, vertices, faces, target, material, "worn_flagstone")
    slab.location = position
    bevel = slab.modifiers.new("Soft stone edges", "BEVEL")
    bevel.width = min(.021, half_height * .48)
    bevel.segments = 2
    return slab


def lantern(name, x, y, z, scale, collection, m):
    stone, metal = m["stone"], m["oldwood"]
    for h,w,d in ((.14,.95,.28),(.39,.60,.23),(.73,.34,.49),(1.04,.58,.15)):
        box(name,(x,y,z+h*scale),(w*scale,w*scale,d*scale),collection,stone,.035*scale)
    box(f"{name} • paper", (x,y,z+1.34*scale),(.48*scale,.48*scale,.43*scale),collection,m["paper"],.036*scale)
    for a in (-.25,.25):
        for b in (-.25,.25):
            box(f"{name} • lattice", (x+a*scale,y+b*scale,z+1.33*scale),(.073*scale,.073*scale,.53*scale),
                collection,metal,.010*scale)
    for h,w in ((1.62,.72),(1.72,.61),(1.81,.46),(1.89,.29),(1.99,.15)):
        box(f"{name} • carved canopy",(x,y,z+h*scale),(w*scale,w*scale,.11*scale),collection,stone,.044*scale)
    lamp=bpy.data.lights.new(f"{name} • amber glow","POINT")
    lamp.color=(1,.48,.21)
    lamp.energy=40*scale*scale
    lamp.shadow_soft_size=.27*scale
    obj=bpy.data.objects.new(lamp.name,lamp)
    collection.objects.link(obj)
    obj.location=(x,y-.30*scale,z+1.42*scale)


def roof(name, center, size, rise, flare, collection, tile, ridge):
    """Continuous pantile surface with dressed eaves, rafters and ridge caps."""
    x,y,z=center
    half_x,half_y=size[0]*.5,size[1]*.5
    def top(a,b):
        u=np.abs(b)/half_y
        return z+rise*(1-u)**1.46 + flare*(np.abs(a)/half_x)**6*(.46+.54*u*u) + .25*u**6
    a=np.linspace(-half_x,half_x,math.ceil(size[0]/.068)+1)
    b=np.linspace(-half_y,half_y,math.ceil(size[1]/.11)+1)
    u,v=np.meshgrid(a,b)
    tilebed=top(u,v)+.077*np.cos(u*math.tau/.25)+.023*np.sin(v*math.tau/.44)
    obj=grid(name,u+x,v+y,tilebed,collection,tile,"tiled_roof")
    mod=obj.modifiers.new("Tile edge thickness","SOLIDIFY")
    mod.thickness=.15
    # The front tiles sit on separate fascia and rafter ends.
    for b0 in (-half_y,0,half_y):
        samples=np.linspace(-half_x,half_x,31)
        guide=[(x+a0,y+b0,float(top(a0,b0)+.10)) for a0 in samples]
        for p,q in zip(guide,guide[1:]):
            beam(f"{name} • curved cap",p,q,.095 if b0 else .18,collection,ridge,vertices=8)
    for a0 in np.linspace(-half_x+.14,half_x-.14,max(8,round(size[0]/.43))):
        for side in (-1,1):
            b0=side*half_y
            height=float(top(a0,b0)-.19)
            beam(f"{name} • exposed rafters",(x+a0,y+b0-side*.54,height-.11),
                 (x+a0,y+b0+side*.22,height),.073,collection,ridge,vertices=8)
    return obj


def rail(name, points, collection, material, height=1.07, thickness=.088):
    for i, point in enumerate(points):
        x,y,z=point
        box(f"{name} • post {(i+1):02}",(x,y,z+height*.49),(.19,.19,height*1.14),
            collection,material,.022)
    for a,b in zip(points,points[1:]):
        for h in (.49,.98):
            beam(f"{name} • horizontal rail",(a[0],a[1],a[2]+height*h),(b[0],b[1],b[2]+height*h),
                 thickness,collection,material,vertices=10)
