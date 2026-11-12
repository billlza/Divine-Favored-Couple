"""Comb the new editable scalp, bun and hanging locks on the fitted bust."""
import math

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import numpy as np

from refine_portrait import require


def dark_material(name, color):
    material = bpy.data.materials.new(name)
    surface = material.node_tree.nodes["Principled BSDF"]
    surface.inputs["Base Color"].default_value = (*color, 1)
    surface.inputs["Roughness"].default_value = .76
    surface.inputs["Specular IOR Level"].default_value = .11
    return material


def fiber_material(name, color):
    material = bpy.data.materials.new(name)
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.remove(nodes["Principled BSDF"])
    strand = nodes.new("ShaderNodeBsdfHairPrincipled")
    strand.model = "CHIANG"
    strand.parametrization = "COLOR"
    strand.inputs["Color"].default_value = (*color,1)
    strand.inputs["Roughness"].default_value = .53
    strand.inputs["Radial Roughness"].default_value = .62
    strand.inputs["Random Roughness"].default_value = .21
    strand.inputs["Coat"].default_value = .055
    diffuse=nodes.new("ShaderNodeBsdfDiffuse")
    diffuse.inputs["Color"].default_value=(*color,1)
    diffuse.inputs["Roughness"].default_value=.57
    mix=nodes.new("ShaderNodeMixShader")
    mix.inputs[0].default_value=.49
    links.new(diffuse.outputs[0],mix.inputs[1])
    links.new(strand.outputs[0],mix.inputs[2])
    links.new(mix.outputs[0],nodes["Material Output"].inputs["Surface"])
    return material


def mesh(name, points, faces, material, collection):
    data=bpy.data.meshes.new(name)
    data.from_pydata(points,[],faces)
    data.update()
    data.materials.append(material)
    data.polygons.foreach_set("use_smooth",np.ones(len(data.polygons),dtype=bool))
    obj=bpy.data.objects.new(name,data)
    collection.objects.link(obj)
    return obj


def hair(name, points, radii, material, collection):
    require(points.ndim == 3 and points.shape[:2] == radii.shape,"Mismatched groom data")
    require(np.isfinite(points).all() and radii.min() > 0,"Invalid hair control points")
    data=bpy.data.hair_curves.new(name)
    data.add_curves([points.shape[1]]*len(points))
    data.attributes["position"].data.foreach_set("vector",np.ascontiguousarray(points,dtype=np.float32).ravel())
    radius=data.attributes.new("radius","FLOAT","POINT")
    radius.data.foreach_set("value",np.ascontiguousarray(radii,dtype=np.float32).ravel())
    data.materials.append(material)
    obj=bpy.data.objects.new(name,data)
    collection.objects.link(obj)
    return obj


def radii(rng, n, t, low=.00018, high=.00044):
    return rng.uniform(low,high,(n,1))*(.18+.82*(1-t)**.59)*(.57+.43*np.minimum(1,t*12))


def scalp_grid(surface):
    # Ray directions follow the fitted skull, including the original head tilt.
    center=Vector((-.019,-.062,.603))
    azimuth=np.linspace(-math.pi,math.pi,160,endpoint=False)
    points=np.empty((len(azimuth),57,3))
    front=np.deg2rad((0,22,42,59,74,91,108,126,160,180))
    line=np.deg2rad((28,25,8,-13,-15,5,3,-26,-43,-51))
    for i,a in enumerate(azimuth):
        edge=float(np.interp(abs(a),front,line))+.024*math.sin(2.2*a)+.013*math.sin(7*a)
        for j,t in enumerate(np.linspace(0,1,57)):
            latitude=(math.pi/2-.017)*(1-t)+edge*t
            direction=Vector((.207*math.sin(a)*math.cos(latitude),-.242*math.cos(a)*math.cos(latitude),
                              .191*math.sin(latitude))).normalized()
            p,_,_,_=surface.ray_cast(center+direction*.75,-direction,.74)
            require(p is not None,f"Missing scalp surface at {a:.3f} {t:.3f}")
            growth=.004 + .020*(1-t)**.65 + .008*max(0,math.sin(latitude))**2
            growth += .0022*math.sin(a*31+.9*math.sin(latitude*5))*math.sin(math.pi*t)**1.1
            points[i,j]=tuple(p+direction*float(growth))
    # Smooth minor ray-to-face variation while retaining the hairline.
    for _ in range(5):
        across=np.roll(points,1,axis=0)+np.roll(points,-1,axis=0)
        points[:,1:-1]=.57*points[:,1:-1]+.07*across[:,1:-1]+.145*(points[:,2:]+points[:,:-2])
    require(points[...,2].max()<.875 and points[...,2].min()>.38,"Scalp outside fitted skull envelope")
    return center,points


def cap_surface(name, points, material, collection):
    rows,cols=points.shape[:2]
    faces=[(i*cols+j,i*cols+j+1,((i+1)%rows)*cols+j+1,((i+1)%rows)*cols+j)
           for i in range(rows) for j in range(cols-1)]
    faces.append(tuple(i*cols for i in range(rows)))
    return mesh(name,points.reshape(-1,3).tolist(),faces,material,collection)


def sample_grid(grid, azimuth, t):
    i=(azimuth+math.pi)*len(grid)/math.tau
    j=np.clip(t,0,1)*(grid.shape[1]-1)
    a=np.floor(i).astype(int)
    b=np.minimum(np.floor(j).astype(int),grid.shape[1]-2)
    u,v=(i-a)[...,None],(j-b)[...,None]
    a%=len(grid)
    c=(a+1)%len(grid)
    return (1-u)*((1-v)*grid[a,b]+v*grid[a,b+1])+u*((1-v)*grid[c,b]+v*grid[c,b+1])


def swept_scalp(grid, center, collection, shades, rng):
    t=np.linspace(0,1,37)[None,:]
    for group,material in enumerate(shades):
        count=(3400,2100,940)[group]
        start=rng.uniform(-math.pi,math.pi,(count,1))
        inward=rng.uniform(.83,1.008,(count,1))
        end=np.sign(start)*rng.uniform(1.25,2.75,(count,1))
        part=rng.uniform(.075,.24,(count,1))
        bend=.16*np.sin(math.pi*t)*np.sin(start*2.4) + .019*np.sin(t*8+start*6)
        a=start+(end-start)*t**1.63+bend
        s=inward*(1-t)+part*t + .017*np.sin(t*10+start*5)*np.sin(math.pi*t)
        positions=sample_grid(grid,a,s)
        normal=positions-np.asarray(center)
        normal/=np.linalg.norm(normal,axis=-1,keepdims=True)
        lift=(rng.uniform(.00025,.0021,(count,1))+.0035*np.sin(math.pi*t)**2)
        positions+=normal*lift[...,None]
        hair(f"Crown flow {group+1}",positions,radii(rng,count,t,.00014,.00039),material,collection)


def parting_fibers(grid, center, collection, material, rng):
    n=640
    t=np.linspace(0,1,32)[None,:]
    a=rng.uniform(-.98,1.06,(n,1))
    root=rng.uniform(.025,.085,(n,1))
    tip=rng.uniform(.22,.45,(n,1))
    azimuth=a+.33*np.sin(a*2.1)*t**1.5
    points=sample_grid(grid,azimuth,root+(tip-root)*t)
    normal=points-np.asarray(center)
    normal/=np.linalg.norm(normal,axis=-1,keepdims=True)
    points+=normal*(rng.uniform(.0008,.0028,(n,1,1))+.001*np.sin(math.pi*t[...,None]))
    hair("Crown parting fibers",points,radii(rng,n,t,.00014,.00034),material,collection)


# Four points for each tapered lock in the unchanged 780 by 640 photo frame.
FRINGE=(
    ((419,174),(380,202),(355,267),(343,339),13),
    ((419,177),(390,204),(363,263),(362,321),12),
    ((421,176),(404,210),(383,261),(382,318),9),
    ((422,177),(413,216),(407,267),(401,316),10),
    ((423,175),(422,216),(426,268),(418,307),9),
    ((425,174),(437,211),(444,253),(439,303),9),
    ((426,176),(451,208),(465,245),(456,297),8),
    ((427,175),(463,207),(483,243),(475,283),9),
    ((428,176),(477,202),(508,245),(514,315),11),
    ((432,178),(492,208),(517,271),(516,359),9),
    ((430,179),(496,216),(520,276),(505,379),7),
    ((414,182),(360,207),(335,271),(347,361),8),
    ((410,181),(352,209),(320,278),(337,385),9),
    ((403,181),(345,200),(314,260),(319,337),13),
    ((413,180),(364,202),(329,260),(331,351),13),
    ((432,176),(488,192),(534,244),(532,331),12),
    ((435,178),(505,207),(545,259),(534,345),10),
)


def front_fibers(photo, skull, cap, collection, materials, rng):
    t=np.linspace(0,1,44)
    basis=np.column_stack(((1-t)**3,3*(1-t)**2*t,3*(1-t)*t*t,t**3))
    for index,guide in enumerate(FRINGE):
        width=guide[4]
        controls=np.asarray(guide[:4],dtype=float)
        count=round(width*13)
        points=np.empty((count,len(t),3))
        for i in range(count):
            wiggle=controls.copy()
            offset=rng.normal(0,width*.44)
            offset=float(np.clip(offset,-width,width))
            wiggle[:,0]+=offset*np.array((.48,.78,1.0,.83))
            wiggle[:,0]+=rng.uniform(-2.4,2.4,4)
            wiggle[0,0]+=rng.uniform(-4.3,4.3)
            wiggle[0,1]+=rng.uniform(-2.2,2.8)
            wiggle[-1,1]+=rng.normal(0,8.5)
            pixel=basis@wiggle
            d_prev=2.71
            lift=rng.uniform(.0024,.011)
            for k,((x,y),u) in enumerate(zip(pixel,t)):
                ray=photo.ray(x,y)
                _,_,_,under=skull.ray_cast(ray,photo.direction,2.92)
                _,_,_,shell=cap.ray_cast(ray,photo.direction,2.93)
                d_skin=(under-lift*(.55+.55*math.sin(math.pi*u))) if under is not None else d_prev
                d_cap=shell-.0015-lift*.39 if shell is not None else d_skin
                dist=min(d_skin,d_cap)
                # Root is embedded in the cap. The rest of the lock sits above the skin.
                dist+=.0038*(1-u)**14
                d_prev=dist
                points[i,k]=tuple(ray+photo.direction*dist)
        for _ in range(5):
            points[:,1:-1]=.23*(points[:,:-2]+points[:,2:])+.54*points[:,1:-1]
        hair(f"Fringe lock {index+1:02d}",points,radii(rng,count,t,.00014,.00041),
             materials[index%len(materials)],collection)


def knot_point(center, angle, latitude, offset=0):
    c=np.cos(latitude)
    ripple=1+.030*np.sin(3*angle+5*latitude)+.018*np.cos(7*angle-3*latitude)
    return np.stack((center[0]+(.080+offset)*c*np.cos(angle)*ripple+.022*np.sin(latitude),
                     center[1]+(.086+offset)*c*np.sin(angle)*ripple-.017*np.sin(latitude),
                     center[2]+(.074+offset)*np.sin(latitude)*ripple),axis=-1)


def bun(photo, grid, collection, underlayer, materials, rng):
    center=photo.ray(393,89)+photo.direction*3.012
    angles,latitude=np.meshgrid(np.linspace(0,math.tau,96,endpoint=False),np.linspace(-1.545,1.545,45),indexing="ij")
    under=knot_point(center,angles,latitude)
    cap_surface("Gathered knot underlayer",under,underlayer,collection)
    base_center=np.asarray(center)+np.array((.009,.011,-.063))
    base=knot_point(base_center,angles,latitude)
    base=base_center+(base-base_center)*np.array((.67,.69,.89))
    cap_surface("Tied hair at the base of the knot",base,underlayer,collection)
    t=np.linspace(0,1,64)[None,:]
    for group,material in enumerate(materials):
        n=(1250,775,440)[group]
        phase=rng.uniform(0,math.tau,(n,1))
        lat=rng.uniform(-1.53,1.53,(n,1))
        angle=phase+(1.04+.14*np.cos(lat))*math.tau*t
        tilt=lat+.15*np.sin(angle+lat)*np.cos(lat)
        offset=rng.uniform(.0005,.003,(n,1))
        points=knot_point(center,angle,tilt,offset)
        hair(f"Knot wrap {group+1}",points,radii(rng,n,t,.00015,.00036),material,collection)
    # Gather a compact bundle from the crown into the lower part of the knot.
    n=1050
    a=rng.uniform(-math.pi,math.pi,(n,1))
    root=sample_grid(grid,a[:,0],rng.uniform(.035,.27,n))[:,None,:]
    end=knot_point(center,a[:,0],rng.uniform(-1.51,-.82,n),.0018)[:,None,:]
    t=np.linspace(0,1,34)[None,:]
    arch=root*(1-t[...,None])+end*t[...,None]
    arch[:,:,2]+=.011*np.sin(t*math.pi)
    arch[:,:,1]-=.006*np.sin(t*math.pi)
    hair("Gathered strands joining scalp and knot",arch,radii(rng,n,t,.00018,.00039),materials[0],collection)


def trailing_locks(grid, skull, collection, underlayer, materials, rng):
    angle=np.linspace(1.65,math.tau-1.65,147)
    top=sample_grid(grid,angle,np.full_like(angle,.74))
    inward=top-np.array((-.019,-.062,.603))
    inward/=np.linalg.norm(inward,axis=1,keepdims=True)
    top-=.011*inward

    t=np.linspace(0,1,49)
    field=np.empty((len(top),len(t),3))
    for i,(a,root) in enumerate(zip(angle,top)):
        lateral=math.sin(a)
        rear=-math.cos(a)
        for j,s in enumerate(t):
            x=float(root[0]*(1-.30*s)+lateral*(.08*s+.23*s*s)-.095*s*s)
            z=float(root[2]*(1-s)+(-.081+.047*math.sin(a*2.7)+.04*math.sin(a*5))*s)
            y=float(root[1]*(1-s)+(.19+.14*max(0,rear))*s+.062*math.sin(math.pi*s)+.026*math.sin(8*s+a)+.019*math.sin(a*9.0+4*s)*math.sin(math.pi*s)**2)
            tuck=min(1,s/.19)
            tuck=tuck*tuck*(3-2*tuck)
            y+=max(.041-y,0)*tuck
            if s>.23:
                p,_,_,_=skull.ray_cast(Vector((x,.85,z)),Vector((0,-1,0)),1.30)
                if p is not None:
                    y=max(y,p.y+.024)
            field[i,j]=(x,y,z)
    for _ in range(4):
        field[1:-1,1:-1]=.51*field[1:-1,1:-1]+.13*(field[1:-1,2:]+field[1:-1,:-2])+.115*(field[2:,1:-1]+field[:-2,1:-1])
    rows,cols=field.shape[:2]
    faces=[(i*cols+j,(i+1)*cols+j,(i+1)*cols+j+1,i*cols+j+1) for i in range(rows-1) for j in range(cols-1)]
    support=mesh("Hanging hair interior",field.reshape(-1,3).tolist(),faces,underlayer,collection)
    # Individual curves are offset towards the outward face of the curtain.
    normal=np.cross(np.gradient(field,axis=1),np.gradient(field,axis=0))
    normal/=np.maximum(np.linalg.norm(normal,axis=-1,keepdims=True),1e-7)
    # Back at the centre of the curtain faces +Y.
    if normal[rows//2,cols//2,1]<0:
        normal*=-1
    for group,material in enumerate(materials):
        n=(3300,2150,970)[group]
        track=rng.uniform(0,rows-1.001,n)
        k=np.floor(track).astype(int)
        f=(track-k)[:,None,None]
        points=(1-f)*field[k]+f*field[k+1]
        normals=(1-f)*normal[k]+f*normal[k+1]
        offset=rng.uniform(.0008,.010,(n,1,1))+.005*np.sin(t[None,:,None]*4)**2
        side_sign=rng.choice((-1,1),n,p=(.46,.54))
        points+=offset*normals*side_sign[:,None,None]
        sway=rng.uniform(-.016,.016,(n,1))*t*t + .004*np.sin(t*12+track[:,None]*.79)*t
        points[:,:,0]+=sway + .008*np.sin(t*14+track[:,None]*.39)*t**1.65
        points[:,:,2]+=rng.uniform(-.035,.044,(n,1))*t**2
        hair(f"Length fibers {group+1}",points,radii(rng,n,t[None,:],.00017,.00049),material,collection)
    return support


def make_groom(head_bvh, photo, scene):
    collection=bpy.data.collections.new("Hair • scalp, fringe, knot and long strands")
    scene.collection.children.link(collection)
    underlayer=dark_material("Hair underlayer • charcoal",(.0061,.0044,.0038))
    materials=[fiber_material(f"Natural black fiber {i+1}",color) for i,color in enumerate((
        (.0074,.0049,.0043),(.0115,.0077,.0065),(.0175,.012,.0105)))]
    rng=np.random.default_rng(512)
    center,grid=scalp_grid(head_bvh)
    obj=cap_surface("Scalp underlayer • fitted hairline",grid,underlayer,collection)
    obj.data.calc_loop_triangles()
    cap=BVHTree.FromPolygons([v.co for v in obj.data.vertices],
                            [tri.vertices[:] for tri in obj.data.loop_triangles],all_triangles=True)
    swept_scalp(grid,center,collection,materials,rng)
    parting_fibers(grid,center,collection,materials[0],rng)
    front_fibers(photo,head_bvh,cap,collection,materials,rng)
    bun(photo,grid,collection,underlayer,materials,rng)
    trailing_locks(grid,head_bvh,collection,underlayer,materials,rng)
    print("GROOM",sum(len(o.data.curves) for o in collection.objects if o.type=="CURVES"),flush=True)
    return collection
