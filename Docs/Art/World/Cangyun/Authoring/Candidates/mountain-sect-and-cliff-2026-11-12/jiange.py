"""Sword Pavilion cave dwellings, stone house and planted terraces."""

import math
import random

import bpy
from mathutils import Vector
import numpy as np

from landscape import area, axis, ground_at, group, mesh_object, mix, mountains, noise, rock_mass, smooth, surface, terrain, terrain_tree
from architecture import beam, box, flagstone, rail
from dwellings import cave_front, cave_wall, stone_house
from mountain_light import ClearAir, CloudBand, set_views, setup_scene, sky
from mountain_materials import material_set
from vegetation import grasses, grove

VIEWS={
    "Jiange_cliff_path": ((-13.8, -17.9, 6.0), (-1.3, 23.0, 5.4), 28, (1800, 1440)),
    "Jiange_overlook": ((-55, -66, 24.7), (3.4, 30.0, 7.6), 31, (1560, 1040)),
}
CAVES=((16.4,2.58,3.95,31.1),(43.5,2.33,3.48,29.8))
RIDGES=(
    (-85,104,33,51,114,-.19),(-187,175,58,79,193,.23),
    (-97,219,32,67,169,.15),(-280,269,87,113,234,-.33),
    (-159,343,53,101,251,-.15),(-356,392,95,127,315,.18),
    (-249,515,90,139,327,.21),(-499,644,126,178,392,-.14),
    (-112,724,115,169,380,.26),(-579,886,155,191,452,-.27),
    (-314,968,134,209,456,.23),(-688,1121,194,211,511,-.24),
    (-184,1195,174,217,507,.18),(251,893,124,181,411,-.18),
)


def shelf(y):
    return .025*(np.asarray(y)+43)+.18+.15*np.sin((y+37)*.045)


def approach_x(y):
    return -1.9+2.6*np.sin((y-8)*.044)+.8*np.sin(y*.083)


def footpaths(x, y):
    main = (1 - smooth(.70, 1.82, abs(x - approach_x(y)))) * (1 - smooth(66, 86, y))
    for cave_y, radius, _, _ in CAVES:
        court = (1 - smooth(1.45, radius + 1.35, abs(y - cave_y))) * smooth(1.8, 5.0, x)
        main = np.maximum(main, court * .71)
    return main


def field(x,y):
    wild=mountains(x,y,RIDGES,-133+.032*np.maximum(y,0),430)
    rim = -11.9 + .92 * np.sin(y * .083) + .56 * noise(x, y, 18, 114)
    plateau = smooth(rim - 7.4, rim + .68, x) * (1 - smooth(109, 169, y)) * smooth(-108, -65, y)
    high=shelf(y)+.14*noise(x,y,4.2,168)
    high=mix(high,shelf(y),(1-smooth(.7,2.2,abs(x-approach_x(y))))*.94)
    # The stone house and front of both caves share the same mountain shelf.
    for cy in (CAVES[0][0],CAVES[1][0]):
        mask=(1-smooth(2.9,6.3,abs(y-cy)))*smooth(5,9,x)*(1-smooth(34,40,x))
        high=mix(high,float(shelf(cy))-.075,mask)
    return mix(wild,high,plateau)


def cliff_face(y,z):
    band=.94*np.sin(z*.18+.38*np.sin(y*.106))+.33*np.sin(z*.52+y*.026)
    veins=3.8*noise(y+z*.21,z*.47,16.0,721)+1.55*noise(y-z*.27,z*.7,6.4,732)
    fracture = .94 * noise(y + z * .26, z * .52, 2.4, 745)
    fracture += .27 * noise(y + z * .47, z * .73, .94, 763)
    warp = noise(y, z, 10.3, 815)
    seam = np.abs(np.sin((y + 1.52 * warp + .19 * z) * .85))
    cleft = -.92 * (1 - smooth(.08, .52, seam))
    fracture += cleft + .34 * np.sin(z * 1.27 + y * .37 + warp * 2.1)
    column=(.88+1.28*noise(y,z,14,752))*(1.24*np.sin(y*.94+z*.021)+.47*np.sin(y*1.97+z*.016))
    buttress=5.1*np.sin(y*.081+.13)+3.0*np.sin(y*.168-z*.010)
    wall=13.6+buttress+band+veins+fracture+column+.055*np.maximum(z-35,0)
    for cy,_,h,_ in CAVES:
        center=13.0+1.67*np.sin(cy*.13)
        seat=(1-smooth(2.0,8.9,abs(y-cy)))*(1-smooth(h*.55,h*1.96,abs(z-shelf(cy)-h*.37)))
        wall=mix(wall,center+.55*noise(y,z,3.0,17),seat*.82)
    return wall


def beds(collection,m,ground):
    rng=random.Random(9165)
    stems=surface("Chrysanthemum stems and leaves",(.072,.145,.031),.75)
    petals=[surface("Yellow chrysanthemum",(.63,.315,.026),.68),
            surface("Russet chrysanthemum",(.57,.142,.031),.73)]
    cactus=surface("Matte wax on cactus",(.079,.231,.101),.51)
    layouts=((-5.9,1.3,4.25,5.8,"flowers"),(-5.65,19.6,4.3,5.3,"cacti"),(3.9,29.2,4.0,7.1,"green"))
    for px,py,w,d,kind in layouts:
        z=ground_at(ground,px,py)
        box(f"Raised {kind} soil",(px,py,z+.08),(w,d,.21),collection,m["earth"],.055)
        for side in (-1,1):
            for n,t in enumerate(np.linspace(-d*.5,d*.5,9)):
                box("Garden retaining stone",(px+side*w*.5,py+t,z+.09),(.34,.63,.28),
                    collection,m["flagstones"][n%4],.052)
            for n,t in enumerate(np.linspace(-w*.5+.38,w*.5-.38,7)):
                box("Garden retaining stone",(px+t,py+side*d*.5,z+.09),(.53,.32,.29),
                    collection,m["flagstones"][n%4],.046)
        if kind=="cacti":
            for j in range(14):
                x=px+rng.uniform(-w*.41,w*.41)
                y=py+rng.uniform(-d*.40,d*.40)
                height=rng.uniform(.62,1.55)
                zz=z+.14
                beam("Ribbed cactus stem",(x,y,zz),(x+.09,y+.1,zz+height),rng.uniform(.15,.26),
                    collection,cactus,vertices=11)
                for v in range(rng.randrange(1,4)):
                    a=rng.uniform(0,math.tau)
                    side=Vector((math.cos(a),math.sin(a),0))
                    root=Vector((x,y,zz+height*rng.uniform(.31,.72)))
                    elbow=root+side*rng.uniform(.19,.37)+Vector((0,0,.10))
                    end=elbow+side*.045+Vector((0,0,rng.uniform(.24,.54)))
                    beam("Cactus arm",root,elbow,.107,collection,cactus,vertices=9)
                    beam("Cactus arm tip",elbow,end,.098,collection,cactus,vertices=9)
        else:
            greens=[]
            vertices,faces,inds=[],[],[]
            for j in range(138):
                x=px+rng.uniform(-w*.45,w*.45)
                y=py+rng.uniform(-d*.45,d*.45)
                h=rng.uniform(.22,.55)
                greens.append((x,y,z+.18,rng.uniform(.22,.46)))
                if kind=="green":
                    continue
                p=Vector((x,y,z+.18+h))
                for ring in (0,1):
                    for k in range(12):
                        a=math.tau*k/12+.26*ring
                        direction=Vector((math.cos(a),math.sin(a),0))
                        across=Vector((-direction.y,direction.x,0))
                        length=rng.uniform(.065,.105)*(1+.27*ring)
                        outer=p+direction*length+Vector((0,0,.021+ring*.010))
                        offset=len(vertices)
                        vertices.extend((tuple(p+direction*.009),tuple(p+direction*length*.61+across*.019),
                                         tuple(outer),tuple(p+direction*length*.61-across*.019)))
                        faces.append((offset,offset+1,offset+2,offset+3))
                        inds.append(0 if j%8 else 1)
                beam("Chrysanthemum stem",(x,y,z+.18),p,.010,collection,stems,vertices=5)
            grasses(f"Foliage in {kind} garden",greens,collection,[m["pine2"],stems],52)
            if faces:
                obj=mesh_object("Chrysanthemum heads",vertices,faces,collection,petals[0],"chrysanthemum")
                obj.data.materials.append(petals[1])
                obj.data.polygons.foreach_set("material_index",inds)



def cliff_greenery(collection,m):
    rng=random.Random(6271)
    vertices,faces,tints=[],[],[]
    for _ in range(104):
        cy=rng.uniform(-19,87)
        cz=rng.uniform(5.7,52)
        if rng.random()>.63+.24*float(noise(cy,cz,11,294)):
            continue
        spread=rng.uniform(.31,1.27)
        for j in range(rng.randrange(14,29)):
            y=cy+rng.uniform(-spread,spread)
            z=cz+rng.uniform(-spread*.58,spread*.59)
            p=Vector((float(cliff_face(y,z))-.13,y,z))
            if j%3==0:
                branch=Vector((float(cliff_face(y+.17,z-.42))-.098,y+.17,z-.42))
                beam("Roots on the rock face",p,branch,.021,collection,m["oldwood"],vertices=6)
            for k in range(rng.randrange(2,5)):
                a=rng.uniform(0,math.tau)
                length=rng.uniform(.12,.31)
                forward=Vector((-.10,math.cos(a),math.sin(a)))*length
                across=Vector((-.14,-math.sin(a),math.cos(a)))*length*.29
                idx=len(vertices)
                vertices.extend((tuple(p),tuple(p+forward*.50+across),
                                 tuple(p+forward+Vector((-.08,0,0))),tuple(p+forward*.49-across)))
                faces.append((idx,idx+1,idx+2,idx+3))
                tints.append(rng.randrange(3))
    obj=mesh_object("Fern and moss colonies clinging to cliff joints",vertices,faces,collection,m["pine0"],"cliff_vegetation")
    obj.data.materials.append(m["pine1"])
    obj.data.materials.append(m["pine2"])
    obj.data.polygons.foreach_set("material_index",tints)

def ledge_outcrops(collection, material):
    rng = random.Random(467)
    for index, (y, width, depth, height) in enumerate(((-24, 3.3, 6.2, 46), (-6, 3.2, 5.4, 34),
            (10, 3.7, 6.8, 45), (30, 3.6, 6.3, 48), (52, 3.8, 6.0, 37))):
        x = -13.6 + .48 * math.sin(y * .08)
        rock_mass(f"Exposed strata beneath the ledge {index + 1}", collection, material,
                  (x, y, float(shelf(y)) - height * .98), (width, depth, height),
                  rng.uniform(-1.1, .45), rng, layers=25, sides=20)
    for index, (y, width, depth, height) in enumerate(((-12, 2.6, 4.0, 27), (4.8, 2.3, 3.5, 19),
            (28.6, 3.2, 4.2, 30), (57.8, 3.8, 4.8, 37))):
        bottom = float(shelf(y)) - 1.4
        x = max(float(cliff_face(y, bottom + 3)) - .52, 8.8)
        rock_mass(f"Broken cliff buttress {index + 1}", collection, material,
                  (x, y, bottom), (width, depth, height), rng.uniform(1.0, 3.0),
                  rng, layers=28, sides=22)


def build():
    scene=setup_scene("Cangyun • Jiange cliff dwellings")
    geol=group("Cliff face and drop")
    dwellings=group("Dwellings and cliff path")
    plants=group("Pines and cultivation beds")
    lights=group("Daylight, valley cloud and lanterns")
    m=material_set()
    xs=axis(((-860,7),(-146,3.2),(-27,.82),(46,.62),(146,3.2),(380,7)))
    ys=axis(((-180,5.6),(-59,.78),(85,.78),(163,2.6),(1330,7.5)))
    ground = terrain("Jiange ledge and mountain drop", xs, ys, field, footpaths, m, geol)
    bpy.context.view_layer.update()
    tree=terrain_tree([ground]).tree
    wall=cave_wall(geol, m, CAVES, shelf, cliff_face)
    ledge_outcrops(geol, m["cliff"])
    rng=random.Random(588)
    for i,(x,y,w,d,h) in enumerate((
            (-60,34,13,26,75),(-71,85,20,29,90),(-121,122,26,33,137),
            (-155,206,29,39,171),(-91,252,25,46,162),(-214,301,41,49,192),
            (-289,335,36,52,177),(-121,355,38,45,172),(-385,473,55,57,222))):
        rock_mass(f"Distant cliff fin {i+1:02}",geol,m["cliff"],(x,y,ground_at(tree,x,y)-h*.44),
                  (w,d,h),rng.uniform(-14,12),rng,layers=39,sides=24,ground=tree)
    for i in range(65):
        y=rng.uniform(-51,60)
        x=rng.choice((rng.uniform(-10,-8),rng.uniform(5.7,10.7)))
        if any(abs(y-cy)<3.5 and x>0 for cy,_,_,_ in CAVES):
            continue
        a=rng.uniform(.18,1.05)
        rock_mass(f"Shelf boulder {i+1}",geol,m["cliff"],(x,y,ground_at(tree,x,y)-a*.40),
                  (a,a*.86,a*.93),a*.19,rng,layers=8,sides=11)
    for a,b in ((-50,-9),(-8,31),(31.2,65)):
        y=np.linspace(a,b,math.ceil((b-a)/2.32)+1)
        coords=[]
        for t in y:
            x=-9.45+1.14*math.sin(t*.085)
            coords.append((x,float(t),ground_at(tree,x,t)))
        rail("Cliff edge railing",coords,dwellings,m["oldwood"])
    # A dry flagstone ribbon makes the climb and the two side entrances readable.
    wear = random.Random(3277)
    for j,y in enumerate(np.arange(-47,60,.95)):
        x=float(approach_x(y))
        z=ground_at(tree,x,y)
        for side in (-1,1):
            slab = flagstone("Path flagstone", (x+side*rng.uniform(.47,.56), y+rng.uniform(-.072,.072), z+.012),
                             (rng.uniform(.92,1.12), rng.uniform(.74,.89), .14), dwellings,
                             rng.choice(m["flagstones"]), wear)
            slab.rotation_euler.z=rng.uniform(-.084,.084)
    for cy,r,h,_ in CAVES:
        stop=float(cliff_face(cy,shelf(cy)+h*.49))-3.5
        for x in np.arange(float(approach_x(cy))+.74,stop+.35,.79):
            z=ground_at(tree,x,cy)
            box("Cave side path slab",(x,cy+rng.uniform(-.15,.15),z+.021),(.74,1.61,.17),
                dwellings,rng.choice(m["flagstones"]),.040)
    cave_front(dwellings, m, lights, CAVES, shelf, cliff_face)
    cliff_greenery(plants,m)
    house_x, house_y = -5.15, 29.2
    house_z = ground_at(tree, house_x, house_y)
    stone_house(house_x, house_y, house_z, dwellings, m)
    for x, y in zip(np.linspace(approach_x(24.3) - 1, house_x, 9), np.linspace(24.3, 26.31, 9), strict=True):
        flagstone("Stone house approach slab", (x, y, ground_at(tree, x, y) + .025),
                  (.64, .95, .13), dwellings, m["flagstones"][2], wear)
    beds(plants,m,tree)
    hero=((-9.4,-17.8,.83,2),(-9.2,14.7,.77,0),(-8.8,38.0,1.05,3),(-8.7,46.2,.84,2),
          (-8.8,61.8,1.11,1),(7.9,57.8,.89,0),(7.3,-13.8,.63,1),(6.9,-24.5,.69,3))
    trees=[]
    for _ in range(1450):
        x,y=rng.uniform(-637,-31),rng.uniform(-65,1110)
        trees.append((x,y,rng.uniform(.51,1.12),rng.randrange(4)))
    tree_count=grove(tree,plants,m,hero,trees,1588)
    tufts=[]
    for _ in range(570):
        y=rng.uniform(-50,68)
        x=rng.uniform(-9.3,9)
        if abs(x-approach_x(y))<1.38 or any(abs(y-cy)<3.8 and x>3 for cy,_,_,_ in CAVES):
            continue
        tufts.append((x,y,ground_at(tree,x,y)-.023,rng.uniform(.25,.68)))
    grasses("Ledge grasses and small ferns",tufts,plants,[m["pine1"],m["pine2"]],155)
    sky(scene, lights, (1, .78, .55), (-.73, -.31, .48), (-330, 385, 100), (
        CloudBand(-53, 41, .028), CloudBand(61, 28, .005), CloudBand(166, 35, .005),
    ), ClearAir((5, 14), 24, 68))
    area("Soft cliff bounce", (-13, -13, 17), (15, 24, 5), 1900, (.91, .94, 1), 19, lights)
    set_views(scene,VIEWS)
    scene["entry_marker"]="jiange.cliff_path"
    scene["route_type"]="Authored ledge with two excavated chambers and planted terraces"
    scene["tree_instances"]=tree_count
    scene["cliff_object"]=wall.name
    return scene
