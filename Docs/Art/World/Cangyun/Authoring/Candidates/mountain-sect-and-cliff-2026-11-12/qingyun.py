"""Qingyun gate, stepped approach and front courtyard in metre units."""

import math
from pathlib import Path
import random

import bpy
import numpy as np

from landscape import area, axis, ground_at, group, mix, mountains, rock_mass, smooth, surface, terrain, terrain_tree
from architecture import beam, box, flagstone, lantern, roof
from mountain_light import ClearAir, CloudBand, set_views, setup_scene, sky
from mountain_materials import material_set
from vegetation import grasses, grove

VIEWS = {
    "Qingyun_approach": ((-1.32, -29.5, 8.10), (.1, 8.5, 17.0), 32, (1800, 1500)),
    "Qingyun_courtyard": ((11.0, 8.3, 11.56), (-1.0, 32.0, 13.8), 32, (1560, 1040)),
}
BASE = 1.9
RISE = .17
TREAD = .60
STARTS = (-42.0,-28.56,-15.12)
WIDTH = 10.1
COURT = BASE + 45*RISE
GATE_Y = -3.1
TERRACE_EDGE = -3.6
RIDGES = (
    (-98,32,68,73,105,-.33),(110,92,75,100,130,.23),
    (-142,182,106,145,224,-.17),(180,246,105,162,246,.18),
    (-38,252,53,104,170,.23),(72,327,70,111,224,-.19),
    (-300,451,170,238,373,.23),(255,522,167,211,369,-.22),
    (-161,637,137,211,403,-.18),(107,742,159,193,436,.27),
    (-370,889,210,263,482,-.19),(345,1065,227,283,523,.21),
    (-43,1264,251,218,545,.23),
)


def grade(y):
    stations=[(-58.0,BASE)]
    for i,a in enumerate(STARTS):
        stations.extend(((a,BASE+15*i*RISE),(a+15*TREAD,BASE+15*(i+1)*RISE)))
    stations.extend(((60.0,COURT),(103.0,COURT+3.0)))
    xy=np.asarray(stations)
    return np.interp(y,xy[:,0],xy[:,1])


def field(x,y):
    wild=mountains(x,y,RIDGES,-25.0+.042*np.maximum(y,0),110)
    width=10+27*smooth(-11,4,y)
    approach=1-smooth(width,width+27,abs(x))
    approach*=smooth(-96,-60,y)*(1-smooth(67,125,y))
    stair_footprint = (1 - smooth(WIDTH / 2 - .12, WIDTH / 2 + .20, abs(x)))
    stair_footprint *= smooth(STARTS[0] - .72, STARTS[0] + .27, y)
    stair_footprint *= 1 - smooth(TERRACE_EDGE - .54, TERRACE_EDGE + .45, y)
    court_footprint = (1 - smooth(20.48, 21.05, abs(x)))
    court_footprint *= smooth(TERRACE_EDGE - .70, TERRACE_EDGE + .36, y) * (1 - smooth(40.4, 42.0, y))
    bed = grade(y) - .083 * np.maximum(stair_footprint, court_footprint)
    return mix(wild, bed, approach)


def platform_cladding(m, collection):
    rng=random.Random(3271)
    wear = random.Random(1106)
    for i,start in enumerate(STARTS):
        bottom=BASE+15*i*RISE
        for s in range(15):
            top=bottom+(s+1)*RISE
            yy=start+(s+.5)*TREAD
            key=f"Flight {i+1} tread {s+1:02}"
            # Every row has a continuous solid tread beneath the individual slabs.
            box(key,(0,yy,top-.28),(WIDTH,TREAD+.015,.56),collection,m["stone"],.015)
            edges=np.linspace(-WIDTH/2,WIDTH/2,9)
            edges[1:-1]+=[rng.uniform(-.16,.16) for _ in edges[1:-1]]
            for j,(a,b) in enumerate(zip(edges,edges[1:])):
                flagstone(f"{key} · slab {j+1}", ((a+b)*.5, yy, top-.024),
                          (b-a-.018, TREAD-.017, .063), collection, rng.choice(m["flagstones"]), wear)
        end=start+15*TREAD
        stop=STARTS[i+1] if i+1<len(STARTS) else TERRACE_EDGE
        landing = bottom + 15 * RISE
        box(f"Stair landing {i+1}",(0,(end+stop)*.5,landing-.166),(WIDTH,stop-end,.37),
            collection,m["stone"],.035)
        for y in np.linspace(end + .28, stop - .28, math.ceil((stop-end) / .91)):
            for x in np.arange(-4.55, 4.6, 1.30):
                flagstone("Landing granite flagstone", (x, y, landing + .008), (1.28, .86, .054),
                          collection, rng.choice(m["flagstones"]), wear)
    for x in (-5.34,5.34):
        samples=np.linspace(-44,-6,20)
        for j,y in enumerate(samples):
            z=float(grade(y))
            box(f"Stone balustrade pier {j+1}",(x,y,z+.41),(.48,.48,.97),collection,m["stone"],.05)
            box("Balustrade coping",(x,y,z+.96),(.64,.64,.18),collection,m["flagstones"][1],.065)
        for a,b in zip(samples,samples[1:]):
            beam("Carved stair balustrade",(x,a,float(grade(a))+.58),(x,b,float(grade(b))+.58),.137,
                 collection,m["stone"],vertices=4)
    box("Gate and courtyard terrace",(0,19.0,COURT-.33),(42.0,46.0,.60),collection,m["stone"],.045)
    for row,y in enumerate(np.arange(-3.68,42,1.34)):
        edges=np.arange(-21.0,22,1.72)+(.86 if row%2 else 0)
        for j,(a,b) in enumerate(zip(edges,edges[1:])):
            a,b=max(a,-20.96),min(b,20.96)
            if b-a>.15:
                box("Courtyard paving",((a+b)*.5,y,COURT-.051),(b-a-.022,1.315,.12),
                    collection,rng.choice(m["flagstones"]),.021)


def column(name,x,y,z,h,r,collection,m):
    box(f"{name} · foot",(x,y,z+.16),(r*2.75,r*2.75,.32),collection,m["stone"],.055)
    beam(f"{name} · post",(x,y,z+.27),(x,y,z+h),r,collection,m["wood"],vertices=22)
    box(f"{name} · capital",(x,y,z+h-.18),(r*2.67,r*2.67,.35),collection,m["oldwood"],.035)
    for j in range(3):
        h0=z+h+.18*j
        box(f"{name} · bracket {j+1}",(x,y,h0),(.52+j*.24,1.31+j*.28,.21),
            collection,m["wood"],.030)
        box(f"{name} · bracket tie {j+1}",(x,y,h0+.09),(1.28+j*.31,.51+j*.19,.19),
            collection,m["oldwood"],.030)


def gate_wings(collection, materials):
    for x in (-7.68, 7.68):
        front = GATE_Y - 1.43
        z = COURT
        box("Wing masonry infill", (x, front + .40, z + 1.69), (3.37, .47, 3.37),
            collection, materials["stone"], .039)
        for offset in np.linspace(-1.54, 1.54, 11):
            box("Gate wing timber panel", (x + offset, front + .065, z + 2.04), (.274, .23, 3.52),
                collection, materials["wood"], .012)
        for offset in (-1.64, 0, 1.64):
            box("Framed wing door stile", (x + offset, front - .085, z + 2.07), (.17, .15, 3.65),
                collection, materials["oldwood"], .016)
        for height in (.40, 1.31, 3.03, 3.86):
            box("Framed wing door rail", (x, front - .09, z + height), (3.50, .15, .16),
                collection, materials["oldwood"], .016)


def portal(collection,m):
    z=COURT
    for x in (-9.4,-6.8,-3.15,3.15,6.8,9.4):
        h=6.62 if abs(x)<4 else 4.75
        for y in (GATE_Y-1.84,GATE_Y+1.85):
            column("Main gate",x,y,z,h,.31 if abs(x)<4 else .235,collection,m)
    for y in (GATE_Y-1.86,GATE_Y+1.87):
        for h,d in ((5.21,.42),(5.93,.39),(6.77,.43)):
            box("Open bay lintel",(0,y,z+h),(7.75,.59,d),collection,m["wood"],.041)
        for x in (-7.1,7.1):
            for h in (3.94,4.70,5.0):
                box("Wing lintel",(x,y,z+h),(5.96,.51,.27),collection,m["wood"],.036)
    gate_wings(collection, m)
    roof("Central lifted roof",(0,GATE_Y,z+7.22),(10.4,5.95),2.20,.83,collection,m["eave"],m["oldwood"])
    for x in (-7.1,7.1):
        roof("Wing lifted roof",(x,GATE_Y,z+5.33),(6.62,5.08),1.56,.61,collection,m["eave"],m["oldwood"])
    for x in (-3.16,3.16):
        box("Central connecting beam",(x,GATE_Y,z+6.68),(.66,4.51,.52),collection,m["wood"],.042)
    # The timber plaque is readable in the render. Convert text to local geometry.
    plaque=surface("Near black blue lacquer",(.016,.029,.033),.37)
    gilding=surface("Aged gilt plaque lettering",(.59,.389,.101),.40,.44)
    box("Gate plaque",(0,GATE_Y-2.24,z+6.02),(3.4,.23,.75),collection,plaque,.055)
    font_path=Path("/System/Library/Fonts/Hiragino Sans GB.ttc")
    if font_path.is_file():
        data=bpy.data.curves.new("青云宗","FONT")
        data.font=bpy.data.fonts.load(str(font_path))
        data.body="青 云 宗"
        data.align_x="CENTER"
        data.align_y="CENTER"
        data.size=.49
        data.extrude=.016
        data.materials.append(gilding)
        label=bpy.data.objects.new("青云宗牌匾",data)
        collection.objects.link(label)
        label.location=(0,GATE_Y-2.38,z+6.02)
        label.rotation_euler=(math.pi/2,0,0)
        bpy.context.view_layer.objects.active=label
        label.select_set(True)
        bpy.ops.object.convert(target="MESH")
        bpy.context.object.select_set(False)


def hall(collection,m):
    z,y=COURT,31.1
    box("Hall masonry plinth",(0,y,z+.47),(16.3,10.4,.94),collection,m["stone"],.058)
    for s in range(5):
        box(f"Hall porch stair {s+1}",(0,y-7.2+s*.42,z+(s+1)*.175-.18),(6.15,.44,.36),
            collection,m["flagstones"][s%4],.026)
    for x in (-7.0,-4.0,-1.88,1.88,4.0,7.0):
        for v in (-4.21,4.1):
            column("Courtyard hall",x,y+v,z+.94,4.55,.215,collection,m)
    for x in (-5.44,5.44):
        box("Hall front screen frame",(x,y-3.73,z+2.62),(3.0,.28,3.35),
            collection,m["wood"],.036)
        for d in np.linspace(-1.33,1.33,9):
            box("Hall screen slat",(x+d,y-3.91,z+2.66),(.11,.095,3.26),collection,m["oldwood"],.014)
    for x in (-6.87,6.87):
        box("Hall side masonry",(x,y+.2,z+2.47),(.35,8.25,3.0),collection,m["stone"],.031)
    box("Hall back masonry",(0,y+3.98,z+2.47),(13.7,.39,3.0),collection,m["stone"],.031)
    roof("Hall tiled roof",(0,y,z+5.99),(17.6,11.02),2.31,.84,collection,m["eave"],m["oldwood"])
    for side in (-1,1):
        for y0 in (5.0,18.4,24.2):
            lantern("Court stone light",side*9.4,y0,z,.82,collection,m)


def build():
    scene=setup_scene("Cangyun • Qingyun sect gate")
    ground_group=group("Mountain shelf and distant ridges")
    structure=group("Stair, gate and forecourt")
    gardens=group("Pines, cliff toes and grasses")
    illumination=group("Mountain daylight and lanterns")
    m=material_set()
    xs=axis(((-880,8),(-180,3.2),(-40,.71),(40,.71),(190,3.2),(880,8)))
    ys=axis(((-180,5),(-66,.68),(61,.68),(163,3.1),(1390,8.0)))
    ground=terrain("Qingyun ridges and temple shelf",xs,ys,field,
                   lambda x,y:(1-smooth(4,6.4,abs(x)))*(1-smooth(-47,-41,y)),m,ground_group)
    bpy.context.view_layer.update()
    surface_tree=terrain_tree([ground]).tree
    rng=random.Random(71)
    for i,(x,y,w,d,h) in enumerate((
            (-31,-17,9,11,17),(23,-26,10,13,16),(-48,13,25,18,41),(47,14,20,18,34),
            (-67,48,33,32,61),(51,89,27,31,69),(-83,132,31,38,116),(115,168,36,35,139),
            (-110,196,36,46,147),(45,236,21,37,98),(196,296,45,61,192))):
        rock_mass(f"Limestone fin {i+1:02}",gardens,m["cliff"],(x,y,ground_at(surface_tree,x,y)-h*.43),
                  (w,d,h),rng.uniform(-9,8),rng,layers=40,sides=24,ground=surface_tree)
    for i in range(60):
        x=rng.choice((-1,1))*rng.uniform(6.1,22.0)
        y=rng.uniform(-54,-6)
        a=rng.uniform(.15,.95)
        rock_mass(f"Stair side rock {i+1}",gardens,m["cliff"],(x,y,ground_at(surface_tree,x,y)-a*.38),
                  (a,a*.77,a*.85),a*.18,rng,layers=7,sides=10)
    hero=((-10.3,-40.5,1.15,1),(8.4,-34.7,.95,2),(-8.4,-18.3,.97,0),
          (10.4,-12.7,.91,3),(-14.5,7.7,1.17,1),(14.9,9.4,.98,2),
          (-12.8,22.7,.74,2),(13.6,26.2,.81,0))
    trees=[]
    for _ in range(2400):
        y=rng.uniform(-91,1000)
        x=rng.uniform(-540,565)
        if abs(x)<24 and y<70 or abs(x)<44 and -60<y<-8:
            continue
        trees.append((x,y,rng.uniform(.62,1.21),rng.randrange(4)))
    tree_count=grove(surface_tree,gardens,m,hero,trees,816)
    tufts=[]
    for _ in range(480):
        x=rng.choice((-1,1))*rng.uniform(5.64,18)
        y=rng.uniform(-57,-5)
        tufts.append((x,y,ground_at(surface_tree,x,y)-.015,rng.uniform(.25,.76)))
    grasses("Moss and grasses beside the steps",tufts,gardens,[m["pine1"],m["pine2"]],81)
    platform_cladding(m,structure)
    portal(structure,m)
    hall(structure,m)
    for side in (-1,1):
        for x in (11.65,16.9):
            box("Outer courtyard wall",(side*x,GATE_Y+.7,COURT+1.25),(5.3,.65,2.5),
                structure,m["stone"],.042)
            box("Wall cap",(side*x,GATE_Y+.7,COURT+2.55),(5.41,.83,.18),
                structure,m["eave"],.03)
        lantern("Gate light",side*5.84,-5.1,COURT,1.13,structure,m)
    sky(scene, illumination, (1, .84, .66), (.57, -.57, .59), (0, 425, 140), (
        CloudBand(49, 20, .013), CloudBand(127, 33, .009), CloudBand(229, 31, .005),
    ), ClearAir((0, -14), 82, 199))
    area("Soft bounce at the gate", (-8, -22, 21), (0, -2, 13), 1600, (.87, .92, 1), 15, illumination)
    set_views(scene,VIEWS)
    scene["entry_marker"]="qingyun.gate_approach"
    scene["route_type"]="Authored stair, gate, courtyard and hall threshold"
    scene["tree_instances"]=tree_count
    return scene
