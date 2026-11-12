"""Excavated cliff solid and small stone and timber dwellings."""

import math
import random

import bmesh
import bpy
import numpy as np

from landscape import axis, mesh_object, mix, noise, require, smooth, vertex_tint
from architecture import beam, box, lantern, roof

def recalc(obj):
    bm=bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        require(not any(e.is_boundary for e in bm.edges),f"Open wall shell: {obj.name}")
        bm.to_mesh(obj.data)
    finally:
        bm.free()
    obj.data.update()


def arch_points(center, radius, height, floor):
    spring=floor+.59*height
    return [(center-radius,floor),(center+radius,floor)]+[
        (center+radius*math.cos(a),spring+.41*height*math.sin(a)) for a in np.linspace(0,math.pi,36)
    ]


def cave_wall(collection, m, caves, shelf, cliff_face):
    ys = axis(((-74, 2.2), (-16, .64), (63, .39), (103, 1.03), (162, 3.2)))
    zs = axis(((-168, 4.1), (-20, 1.35), (-5, .62), (15, .37), (34, .98), (165, 3.4)))
    y,z=np.meshgrid(ys,zs)
    x=cliff_face(y,z)
    rows,cols=x.shape
    n=rows*cols
    front=np.stack((x,y,z),axis=-1).reshape(-1,3)
    rear=np.stack((np.full_like(x,93)+.014*z,y,z),axis=-1).reshape(-1,3)
    faces=[]
    for j in range(rows-1):
        for i in range(cols-1):
            a=j*cols+i
            faces.extend(((a,a+cols,a+cols+1,a+1),(n+a,n+a+1,n+a+cols+1,n+a+cols)))
    perimeter=([i for i in range(cols)]+[j*cols+cols-1 for j in range(1,rows)]
               +[(rows-1)*cols+i for i in range(cols-2,-1,-1)]+[j*cols for j in range(rows-2,0,-1)])
    faces.extend((a,b,n+b,n+a) for a,b in zip(perimeter,perimeter[1:]+perimeter[:1]))
    wall=mesh_object("Fractured cliff with excavated rooms",np.concatenate((front,rear)).tolist(),faces,
                     collection,m["cliff"],"solid_cliff")
    wall.data.materials.append(m["stone"])
    s=.41+.28*noise(y+z*.18,z*3.0,10.0,53)+.18*noise(y+z*.15,z*6,5.5,55)
    colors=mix(np.array((.044,.052,.060)),np.array((.247,.211,.169)),s[...,None])
    moss=smooth(.48,.72,.52+.36*noise(y,z,12.7,96))*smooth(-45,3,z)
    colors=mix(colors,np.array((.066,.102,.045)),moss[...,None]*.32)
    vertex_tint(wall,np.tile(colors.reshape(-1,3),(2,1)),"RockTint")
    recalc(wall)
    for i,(cy,r,h,back) in enumerate(caves):
        shape=arch_points(cy, r, h, float(shelf(cy)))
        count=len(shape)
        points=[(x0,a,b) for x0 in (2.2,back) for a,b in shape]
        cutter_faces=[tuple(reversed(range(count))),tuple(range(count,2*count))]
        cutter_faces.extend((a,(a+1)%count,count+(a+1)%count,count+a) for a in range(count))
        cutter=mesh_object(f"Excavation {i+1}",points,cutter_faces,collection,m["cliff"],"cutter")
        cutter.data.materials.append(m["stone"])
        for p in cutter.data.polygons:
            p.material_index=1
        recalc(cutter)
        before=len(wall.data.polygons)
        mod=wall.modifiers.new(f"Excavated cavity {i+1}","BOOLEAN")
        mod.operation="DIFFERENCE"
        mod.solver="EXACT"
        mod.object=cutter
        bpy.context.view_layer.objects.active=wall
        bpy.ops.object.modifier_apply(modifier=mod.name)
        require(len(wall.data.polygons)!=before,"Cave Boolean left cliff unchanged")
        bpy.data.objects.remove(cutter,do_unlink=True)
    for p in wall.data.polygons:
        p.use_smooth=p.material_index==0
    return wall


def cave_front(collection, m, lights, caves, shelf, cliff_face):
    for i,(cy,r,h,back) in enumerate(caves):
        floor=float(shelf(cy))
        entrance=float(cliff_face(cy,floor+h*.49))
        prefix=f"Cave {i+1}"
        box(f"{prefix} • threshold to interior",((entrance-3.8+back)*.5,cy,floor-.13),
            (back-entrance+3.8,r*1.87,.32),collection,m["flagstones"][i],.035)
        spring=floor+.59*h
        for sign in (-1,1):
            for j in range(5):
                z=floor+.23+j*(spring-floor)/5
                y=cy+sign*(r+.10)
                x=float(cliff_face(y,z))-.14
                box(f"{prefix} • jamb stone",(x,y,z),(.48,.46,.45),collection,m["flagstones"][(i+j)%4],.045)
        for j,a in enumerate(np.linspace(.04,math.pi-.04,16)):
            y=cy+(r+.12)*math.cos(a)
            z=spring+(.41*h+.16)*math.sin(a)
            x=float(cliff_face(y,z))-.17
            obj=box(f"{prefix} • arch stone",(x,y,z),(.48,.40,.44),
                    collection,m["flagstones"][(j+i)%4],.044)
            obj.rotation_euler.x=(a-math.pi/2)*.63
        for d in (-r*.76,r*.76):
            box(f"{prefix} • support post",(entrance+.76,cy+d,floor+.96),(.22,.24,1.94),
                collection,m["oldwood"],.024)
        box(f"{prefix} • inside lintel",(entrance+.78,cy,floor+2.03),(.27,r*1.68,.29),
            collection,m["oldwood"],.034)
        lantern(f"{prefix} lamp",entrance-.48,cy-r-1.03,floor,.67,collection,m)
        lamp=bpy.data.lights.new(f"{prefix} interior light","POINT")
        lamp.energy=93
        lamp.color=(1,.52,.22)
        lamp.shadow_soft_size=.51
        o=bpy.data.objects.new(lamp.name,lamp)
        lights.objects.link(o)
        o.location=(entrance+3.8,cy+.45,floor+1.74)
        box(f"{prefix} bench",(entrance+5.9,cy+r*.63,floor+.45),(1.67,.54,.17),
            collection,m["oldwood"],.035)
        for d in (-.63,.63):
            box(f"{prefix} bench foot",(entrance+5.9+d,cy+r*.63,floor+.21),(.14,.43,.43),
                collection,m["oldwood"],.024)
        marker=bpy.data.objects.new(f"jiange.cave_{i+1}.threshold",None)
        collection.objects.link(marker)
        marker.location=(entrance-2.0,cy,floor+.03)
        marker.empty_display_size=.35


def stone_house(x,y,z,collection,m):
    width,depth=7.85,5.45
    rng=random.Random(336)
    box("Stone house floor",(x,y,z-.13),(width,depth,.30),collection,m["stone"],.041)
    for j in range(8):
        zz=z+.22+.37*j
        for side in (-1,1):
            for k in range(8):
                dy=-depth*.5+(k+.5)*depth/8
                box("Stone house side masonry",(x+side*(width*.5-.18),y+dy,zz),
                    (.37,depth/8-.015,.365),collection,rng.choice(m["flagstones"]),.037)
        for side in (-1,1):
            edges=np.linspace(-width*.5,width*.5,12)
            for k,(a,b) in enumerate(zip(edges,edges[1:])):
                if side==-1 and j<6 and a<.92 and b>-.92:
                    continue
                box("Stone house end masonry",(x+(a+b)*.5,y+side*(depth*.5-.18),zz),
                    (b-a-.012,.37,.365),collection,rng.choice(m["flagstones"]),.041)
    for a in (-1.10,1.10):
        box("Stone house open door jamb",(x+a,y-depth*.5-.02,z+1.19),(.20,.34,2.38),
            collection,m["oldwood"],.026)
    box("Stone house open door lintel",(x,y-depth*.5-.02,z+2.42),(2.46,.36,.26),
        collection,m["oldwood"],.023)
    for x0 in (-3.42,3.42):
        box("Stone house end gable",(x+x0,y,z+3.03),(.32,depth*.93,.38),
            collection,m["stone"],.039)
    roof("Stone house slate",(x,y,z+3.09),(width+.66,depth+.84),1.21,.051,
         collection,m["roof"],m["oldwood"])
    lantern("House approach lantern",x+2.05,y-depth*.5-.43,z,.64,collection,m)
