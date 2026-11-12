"""Dimensioned Wanqing Mountain hut study with explicit narrative stages."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parent
STEM = "wanqing-hut-study-2026-09-05-01"
FLOOR_Z = 0.28
EAVE_Z = 2.58
RIDGE_Z = 3.43


def group(name):
    result = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(result)
    return result


def surface(name, color, roughness=.65, metal=0., texture=False):
    result = bpy.data.materials.new(name)
    result.diffuse_color = (*color, 1.)
    nodes, links = result.node_tree.nodes, result.node_tree.links
    shader = nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metal
    if texture:
        coordinates = nodes.new("ShaderNodeTexCoord")
        scale = nodes.new("ShaderNodeVectorMath")
        scale.operation = "MULTIPLY"
        scale.inputs[1].default_value = (32, 4, 3)
        links.new(coordinates.outputs["Generated"], scale.inputs[0])
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 3.0
        noise.inputs["Detail"].default_value = 3.0
        links.new(scale.outputs[0], noise.inputs["Vector"])
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = .20
        ramp.color_ramp.elements[0].color = (*(c*.48 for c in color), 1.)
        ramp.color_ramp.elements[1].position = .80
        ramp.color_ramp.elements[1].color = (*(c*1.12 for c in color), 1.)
        links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], shader.inputs["Base Color"])
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = .22
        bump.inputs["Distance"].default_value = .003
        links.new(noise.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return result


def mesh_object(name, vertices, faces, target, material, obstacle=False):
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    target.objects.link(obj)
    data.materials.append(material)
    obj["walk_obstacle"] = obstacle
    return obj


def finish(obj, name, target, material, obstacle=False):
    obj.name = name
    for previous in tuple(obj.users_collection):
        previous.objects.unlink(obj)
    target.objects.link(obj)
    obj.data.materials.append(material)
    obj["walk_obstacle"] = obstacle
    return obj


def box(name, position, dimensions, target, material, bevel=.003, obstacle=False):
    if min(dimensions) <= 0:
        raise ValueError(f"Nonpositive dimensions: {name}")
    bpy.ops.mesh.primitive_cube_add(size=1, location=position)
    obj = finish(bpy.context.object, name, target, material, obstacle)
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        modifier = obj.modifiers.new("EdgeWearRadius", "BEVEL")
        modifier.width = min(bevel, min(dimensions)*.35)
        modifier.segments = 2
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    return obj


def beam(name, start, end, radius, target, material, obstacle=False, vertices=12):
    start, end = Vector(start), Vector(end)
    delta = end-start
    if delta.length <= 0 or radius <= 0:
        raise ValueError(f"Invalid beam: {name}")
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius,
                                      depth=delta.length, location=(start+end)/2)
    obj = finish(bpy.context.object, name, target, material, obstacle)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = delta.to_track_quat("Z", "Y")
    return obj


def soft_shape(name, position, dimensions, target, material, obstacle=False):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, location=position)
    obj = finish(bpy.context.object, name, target, material, obstacle)
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def leaf_cluster(name, position, dimensions, target, material):
    vertices, faces = [], []
    center = Vector(position)
    count = 250
    for i in range(count):
        phi = i*2.399963229728653
        z = 1-2*(i+.5)/count
        radial = math.sqrt(1-z*z)
        shell_depth = .63+.37*(.5+.5*math.sin(i*13.79))
        offset = Vector((dimensions[0]*.5*radial*math.cos(phi),
                         dimensions[1]*.5*radial*math.sin(phi), dimensions[2]*.5*z))*shell_depth
        point = center+offset
        length = .15+.055*(.5+.5*math.sin(i*4.31))
        axis = Vector((math.cos(phi), math.sin(phi), .45*math.sin(phi*1.7))).normalized()
        width_axis = axis.cross(Vector((.13,.06,1.))).normalized()
        start = len(vertices)
        vertices.extend([tuple(point-axis*length*.5), tuple(point+width_axis*.052),
                         tuple(point+axis*length*.5), tuple(point-width_axis*.052),
                         tuple(point+Vector((0,0,.012)))])
        faces.extend([(start,start+1,start+4),(start+1,start+2,start+4),
                      (start+2,start+3,start+4),(start+3,start,start+4)])
    return mesh_object(name, vertices, faces, target, material)


def vessel(name, center, radius, height, target, material, obstacle=True):
    cx, cy, base = center
    segments = 40
    rings = [(radius*.65, base), (radius, base+height),
             (radius-.012, base+height), (radius*.65-.012, base+.014)]
    vertices, faces = [], []
    for r, z in rings:
        for i in range(segments):
            angle = 2*math.pi*i/segments
            vertices.append((cx+r*math.cos(angle), cy+r*math.sin(angle), z))
    for ring in range(3):
        for i in range(segments):
            n = (i+1) % segments
            faces.append((ring*segments+i, ring*segments+n,
                          (ring+1)*segments+n, (ring+1)*segments+i))
    faces.extend([tuple(reversed(range(segments))), tuple(range(3*segments, 4*segments))])
    return mesh_object(name, vertices, faces, target, material, obstacle)


def aim(obj, point):
    obj.rotation_euler = (Vector(point)-obj.location).to_track_quat("-Z", "Y").to_euler()


def area(name, position, point, power, color, size, target):
    data = bpy.data.lights.new(name, "AREA")
    data.energy, data.color, data.size = power, color, size
    data.shape = "DISK"
    obj = bpy.data.objects.new(name, data)
    target.objects.link(obj)
    obj.location = position
    aim(obj, point)
    return obj


def camera(name, position, point, lens, target, ortho=None):
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    target.objects.link(obj)
    obj.location = position
    data.lens, data.clip_start, data.clip_end = lens, .05, 160
    if ortho is not None:
        data.type, data.ortho_scale = "ORTHO", ortho
    aim(obj, point)
    return obj


def blanket(target, material):
    vertices, faces = [], []
    nx, ny = 30, 38
    for j in range(ny+1):
        y = 1.30+1.40*j/ny
        for i in range(nx+1):
            x = -1.39-.55+1.10*i/nx
            sag = max(0, abs(x+1.39)-.435)*1.9 + max(0, 1.40-y)*1.9
            z = .895-sag+.008*math.sin(29*x+11*y)+.006*math.sin(18*y-5*x)
            vertices.append((x, y, z))
    for j in range(ny):
        for i in range(nx):
            a = j*(nx+1)+i
            faces.append((a, a+1, a+nx+2, a+nx+1))
    obj = mesh_object("Bed.WornCover", vertices, faces, target, material, True)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    bpy.context.view_layer.objects.active = obj
    modifier = obj.modifiers.new("FabricThickness", "SOLIDIFY")
    modifier.thickness = .010
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def construct():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.unit_settings.system, scene.unit_settings.scale_length = "METRIC", 1.0
    scene.unit_settings.length_unit = "METERS"
    scene["study_status"] = "dimensioned_geometry_study_not_game_asset_acceptance"
    scene["narrative_stage"] = "initial_damaged_hut"
    scene["dimensions_basis"] = "art_direction_estimates_not_novel_measurements"
    scene["clear_room_dimensions_m"] = [4.2, 4.8, 2.30]
    scene["exterior_context"] = "local_fictional_coordinates_no_geographic_survey"
    scene["later_events"] = "washing_retreat_and_approach_are_layout_studies_for_later_upgraded_shelter"
    shell, roof = group("01.HutShell"), group("02.DamagedRoof")
    furnishings, porch = group("03.Furnishings"), group("04.PorchAndWashing")
    ground, forest = group("05.GroundAndApproach"), group("06.ForestContext")
    effects, lighting = group("07.OptionalProtectionStudy"), group("08.Lighting")
    cameras, guides = group("09.Cameras"), group("10.LayoutMarkers")
    wood = surface("WeatheredTimber", (.19, .115, .061), .78, texture=True)
    pale_wood = surface("DryTimberInterior", (.29, .19, .105), .80, texture=True)
    dark_wood = surface("WetRoofTimber", (.115, .071, .041), .50, texture=True)
    wood_variation = surface("WeatheredTimberLight", (.255, .17, .10), .77, texture=True)
    earth = surface("DampEarth", (.055, .049, .035), .62, texture=True)
    stone = surface("RoughFoundationStone", (.13, .15, .145), .85, texture=True)
    cloth = surface("WornFlaxCloth", (.25, .25, .16), .93, texture=True)
    straw = surface("StrawMat", (.31, .26, .13), .94, texture=True)
    pottery = surface("PlainEarthenware", (.25, .17, .095), .52)
    water = surface("StillBasinWater", (.035, .060, .069), .18, .18)
    iron = surface("DullIron", (.09, .10, .11), .54, .68)
    tree_mat = surface("ForestBark", (.065, .053, .039), .90, texture=True)
    foliage = surface("ForestFoliage", (.020, .044, .029), .93)

    # Floor boards, joists and actual structural supports.
    for i in range(14):
        x = -1.95+i*.30
        box(f"Floor.Board.{i:02}", (x, 2.4, .25), (.296, 4.8, .06), shell, pale_wood)
    for y in [.10, 1.60, 3.20, 4.70]:
        box("Floor.Joist", (0, y, .14), (4.26, .13, .15), shell, wood)
    for x in [-1.9, 1.9]:
        for y in [.1, 2.4, 4.7]:
            soft_shape("Foundation.Stone", (x, y, .065), (.40, .40, .13), shell, stone)
    for x in [-2.05, 2.05]:
        for y in [.06, 4.74]:
            box("Frame.CornerPost", (x, y, 1.43), (.12, .12, 2.30), shell, wood, obstacle=True)
    for y in [.04, 4.76]:
        box("Frame.CrossBeam", (0, y, 2.51), (4.28, .15, .15), shell, wood, obstacle=True)
    for x in [-2.10, 2.10]:
        box("Frame.SideTopPlate", (x, 2.4, 2.585), (.13, 4.92, .15), shell, wood, obstacle=True)

    # Openings are built by leaving geometry out, not by placing dark rectangles.
    for side in [-1, 1]:
        for i in range(16):
            y = .15+i*.30
            spans = [(FLOOR_Z, EAVE_Z)]
            if side == 1 and 10 <= i <= 13:
                spans = [(FLOOR_Z, 1.30), (2.13, EAVE_Z)]
            for piece, (z0, z1) in enumerate(spans):
                box(f"Wall.Side.{side}.{i:02}.{piece}", (side*2.14, y, (z0+z1)/2),
                    (.08, .296, z1-z0), shell, wood if i % 4 else wood_variation, obstacle=True)
    for i in range(14):
        x = -1.95+i*.30
        spans = [(FLOOR_Z, EAVE_Z)] if abs(x) > .6 else [(2.36, EAVE_Z)]
        for piece, (z0, z1) in enumerate(spans):
            box(f"Wall.Front.{i:02}.{piece}", (x, -.04, (z0+z1)/2),
                (.296, .08, z1-z0), shell, wood if i % 3 else wood_variation, obstacle=True)
        box(f"Wall.Back.{i:02}", (x, 4.84, 1.43), (.296, .08, 2.30), shell, wood, obstacle=True)
    for x in [-.58, .58]:
        box("Door.Jamb", (x, -.06, 1.30), (.04, .14, 2.04), shell, pale_wood, obstacle=True)
    box("Door.Lintel", (0, -.06, 2.335), (1.20, .14, .05), shell, pale_wood, obstacle=True)
    box("Door.OpenLeaf", (-.66, -.58, 1.295), (.045, 1.13, 2.03), shell, wood, obstacle=True)
    for y in [-.15, -.94]:
        box("Door.LeafBrace", (-.626, y, 1.25), (.027, .08, 1.86), shell, pale_wood, obstacle=True)
    beam("Door.Handle", (-.650, -.85, 1.19), (-.60, -.85, 1.19), .017, shell, iron)
    for y in [3.015, 4.185]:
        box("Window.Jamb", (2.125, y, 1.715), (.15, .03, .83), shell, pale_wood, obstacle=True)
    for z in [1.315, 2.115]:
        box("Window.Rail", (2.125, 3.6, z), (.15, 1.20, .03), shell, pale_wood, obstacle=True)
    box("Window.Mullion", (2.13, 3.6, 1.715), (.065, .045, .78), shell, wood, obstacle=True)
    box("Window.Sill", (2.095, 3.6, 1.285), (.22, 1.28, .035), shell, pale_wood, obstacle=True)
    # Front and rear gable infill uses narrow planks with a triangular profile.
    for end_y in [-.04, 4.84]:
        for i in range(14):
            x0, x1 = -2.1+i*.30, -2.1+(i+1)*.30-.004
            z0 = RIDGE_Z-abs(x0)/2.40*(RIDGE_Z-EAVE_Z)
            z1 = RIDGE_Z-abs(x1)/2.40*(RIDGE_Z-EAVE_Z)
            vertices = [(x0,end_y-.04,EAVE_Z),(x1,end_y-.04,EAVE_Z),(x1,end_y-.04,z1),(x0,end_y-.04,z0),
                        (x0,end_y+.04,EAVE_Z),(x1,end_y+.04,EAVE_Z),(x1,end_y+.04,z1),(x0,end_y+.04,z0)]
            faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
            mesh_object("Gable.Plank", vertices, faces, shell, wood)

    slope = (RIDGE_Z-EAVE_Z)/2.40
    angle = math.atan(slope)
    for y in [-.15, 1.05, 2.45, 3.85, 4.95]:
        for side in [-1, 1]:
            beam("Roof.Rafter", (0, y, RIDGE_Z-.07), (side*2.42, y, EAVE_Z-.08), .062, roof, pale_wood)
    beam("Roof.Ridge", (0,-.34,RIDGE_Z-.045), (0,5.14,RIDGE_Z-.045), .075, roof, wood)
    omitted = []
    for side in [-1, 1]:
        for i in range(7):
            for j in range(18):
                if (side == 1 and i in [3,4] and j in [6,7]) or (side == -1 and i == 2 and j == 12):
                    omitted.append([side,i,j])
                    continue
                x = side*(i+.5)*2.40/7
                y = -.15+j*.30
                z = RIDGE_Z-abs(x)*slope+.022
                obj = box(f"Roof.Plank.{side}.{i:02}.{j:02}", (x,y,z),
                          (2.40/7/math.cos(angle)+.012,.311,.035), roof, dark_wood if (i+j)%5 else wood,
                          bevel=.005)
                obj.rotation_euler.y = side*angle
    # Short split boards expose a measurable hole while retaining a weathered edge.
    edge = box("Roof.BrokenEdge", (1.025,1.65,3.09), (.12,.55,.034), roof, wood, bevel=.002)
    edge.rotation_euler.y = angle
    scene["omitted_roof_plank_indices"] = json.dumps(omitted)

    for x in [-1.81, -.98]:
        for y in [1.43, 3.18]:
            box("Bed.Leg", (x,y,.505), (.07,.07,.45), furnishings, pale_wood, obstacle=True)
    box("Bed.Frame", (-1.39,2.30,.745), (1.06,2.04,.12), furnishings, pale_wood, obstacle=True)
    box("Bed.StrawMat", (-1.39,2.30,.842), (.97,1.98,.08), furnishings, straw, bevel=.025, obstacle=True)
    box("Bed.Headboard", (-1.39,3.32,.94), (1.08,.06,.45), furnishings, wood, obstacle=True)
    blanket(furnishings, cloth)
    soft_shape("Bed.Pillow", (-1.39,3.035,.925), (.60,.32,.12), furnishings, cloth, True)
    box("Table.Top", (1.39,3.72,.98), (.92,.75,.045), furnishings, pale_wood, bevel=.012, obstacle=True)
    for x in [1.01,1.77]:
        for y in [3.42,4.02]:
            box("Table.Leg", (x,y,.61875), (.07,.07,.6775), furnishings, wood, obstacle=True)
    box("Table.CrossApron", (1.39,4.02,.90), (.78,.035,.11), furnishings, wood, obstacle=True)
    box("Stool.Seat", (1.35,2.91,.72), (.38,.36,.045), furnishings, wood, obstacle=True)
    for x in [1.21,1.49]:
        for y in [2.79,3.03]:
            beam("Stool.Leg", (x,y,.28), (x,y,.6975), .025, furnishings, pale_wood, True)
    vessel("Table.EmptyBowl", (1.36,3.62,1.003), .105, .060, furnishings, pottery)
    beam("Table.Chopstick.1", (1.08,3.55,1.011), (1.09,3.78,1.011), .003, furnishings, pale_wood)
    beam("Table.Chopstick.2", (1.10,3.55,1.011), (1.11,3.78,1.011), .003, furnishings, pale_wood)
    # A small oil lamp is a lighting proposal, not a claim about a named novel prop.
    vessel("Table.OilLamp", (1.57,3.94,1.005), .060, .037, furnishings, iron)
    flame = surface("SmallWarmFlame", (1.,.48,.12), .4)
    flame_shader = flame.node_tree.nodes.get("Principled BSDF")
    flame_shader.inputs["Emission Color"].default_value = (1.,.36,.065,1)
    flame_shader.inputs["Emission Strength"].default_value = 5.
    soft_shape("Table.LampFlame", (1.57,3.94,1.073), (.016,.016,.055), furnishings, flame)

    for i in range(15):
        box(f"Porch.Board.{i:02}", (-2.10+i*.30,-.46,.245), (.295,.94,.055), porch, wood)
    box("Porch.Step", (0,-1.105,.07), (1.30,.40,.14), porch, wood, bevel=.012)
    for x in [-2.10,2.10]:
        box("Porch.Support", (x,-.72,.11), (.13,.13,.22), porch, wood)
    for x in [1.63,2.01]:
        for y in [-1.35,-1.03]:
            box("Washing.StandLeg", (x,y,.22), (.055,.055,.44), porch, wood, obstacle=True)
    box("Washing.StandTop", (1.82,-1.19,.452), (.53,.47,.025), porch, wood, obstacle=True)
    vessel("Washing.WoodBasin", (1.82,-1.19,.465), .245, .16, porch, wood)
    beam("Washing.BasinWater", (1.82,-1.19,.595), (1.82,-1.19,.599), .217, porch, water, False, 48)
    vessel("Washing.SecondBowl", (1.97,-1.05,.598), .073, .045, porch, pottery)
    box("Washing.LowStool", (1.71,-1.97,.23), (.36,.32,.045), porch, wood, obstacle=True)
    for x in [1.59,1.83]:
        for y in [-2.08,-1.86]:
            beam("Washing.StoolLeg", (x,y,.015), (x,y,.21), .023, porch, wood, True)

    # Terrain has low-amplitude relief and a clear central approach corridor.
    verts, faces = [], []
    nx, ny = 32, 38
    for j in range(ny+1):
        y = -10+20*j/ny
        for i in range(nx+1):
            x = -10+20*i/nx
            flat = abs(x)<2.5 and -7.5<y<5.3
            z = -.012 if flat else -.015+.065*math.sin(.7*x)*math.cos(.6*y)
            verts.append((x,y,z))
    for j in range(ny):
        for i in range(nx):
            a=j*(nx+1)+i
            faces.append((a,a+1,a+nx+2,a+nx+1))
    mesh_object("Terrain.EarthSurface", verts, faces, ground, earth)
    puddle = surface("ThinRainPuddles", (.024,.038,.047), .16, .28)
    for i,(x,y,sx,sy) in enumerate([(-1.55,-2.0,.55,.90),(.88,-3.5,.60,.38),(-.6,-4.8,.75,.34),(2.85,1.6,.75,.44)]):
        soft_shape(f"Terrain.Puddle.{i}", (x,y,-.004), (sx,sy,.004), ground, puddle)
    positions = [(-4.0,-3.0),(-3.5,1.0),(-4.3,4.0),(-2.8,7.0),(-.7,7.8),(1.7,7.4),(4.0,6.0),(4.5,2.6),
                 (5.0,-.8),(-6.5,4.5),(6.8,6.0),(-5.8,-5.5),(8.5,-5.5)]
    for i,(x,y) in enumerate(positions):
        height=5.2+(i%4)*.5
        beam(f"Forest.Tree.{i:02}.Trunk", (x,y,-.02), (x+.18,y,height*.72), .12+(i%3)*.025,
             forest, tree_mat, True)
        for j,(dx,dy,dz) in enumerate([(-.60,.10,.0),(.5,-.15,.30),(.0,.4,.75)]):
            beam(f"Forest.Tree.{i:02}.Branch.{j}", (x,y,height*.45), (x+dx,y+dy,height*.7+dz),
                 .055, forest, tree_mat, True)
            leaf_cluster(f"Forest.Tree.{i:02}.Crown.{j}", (x+dx,y+dy,height*.77+dz),
                         (1.9,1.6,2.7), forest, foliage)
    for i,(x,y) in enumerate([(-3.2,-1.4),(-3.0,3.5),(3.1,4.1),(3.4,-2.9),(-2.3,-5.0)]):
        soft_shape(f"Forest.Rock.{i}", (x,y,.12), (.60,.48,.31), forest, stone, True)
    # Hairline geometry suggests a roof leak without simulating weather.
    rain = surface("RoofLeakWater", (.24,.35,.47), .12, .1)
    for i in range(10):
        x=1.18+.035*math.sin(i*2)
        z=2.84-i*.19
        beam(f"Leak.Droplet.{i:02}", (x,1.66,z), (x+.007,1.66,z-.06), .0017, roof, rain, False, 6)

    glow = surface("OptionalProtectionAmber", (1.,.36,.055), .4)
    shader = glow.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Emission Color"].default_value=(1.,.30,.025,1)
    shader.inputs["Emission Strength"].default_value=3.0
    for side in [-1,1]:
        beam("ProtectionStudy.EaveLine", (side*2.43,-.30,2.59), (side*2.43,5.10,2.59), .012, effects, glow)
    beam("ProtectionStudy.RidgeLine", (0,-.30,3.48), (0,5.10,3.48), .012, effects, glow)
    effects.hide_render, effects.hide_viewport = True, True
    scene["optional_protection_layer"] = "disabled; speculative look study, not initial shelter capability"
    for name, point in [("WashingInteraction",(1.4,-1.55,0)),("DoorRetreat",(0,-.55,.28)),
                        ("IndoorSafetyPoint",(0,2.7,.28)),("ForestApproach",(0,-6.1,0))]:
        obj=bpy.data.objects.new(name,None)
        guides.objects.link(obj)
        obj.location=point
        obj.empty_display_type="PLAIN_AXES"
        obj.empty_display_size=.20
    guides.hide_render=True
    scene.world=bpy.data.worlds.new("RainNightWorld")
    bg=scene.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value=(.24,.35,.56,1)
    bg.inputs["Strength"].default_value=.25
    area("Light.CloudedSky", (4,-2,9), (0,1,.5), 1350, (.48,.64,1.), 9, lighting)
    area("Light.ForestSeparation", (-3,6,7), (0,2,1), 800, (.38,.50,.79), 6, lighting)
    area("Light.InteriorBounce", (0,2.3,2.34), (0,2.2,.5), 12, (.54,.64,.85), 2, lighting)
    data=bpy.data.lights.new("Light.TableLamp", "POINT")
    data.energy, data.color, data.shadow_soft_size=12,(1.,.49,.18),.12
    obj=bpy.data.objects.new("Light.TableLamp",data)
    lighting.objects.link(obj)
    obj.location=(1.57,3.94,1.15)
    main=camera("HutExterior", (7.2,-9.2,4.15), (.0,1.7,1.25), 35, cameras)
    camera("HutInterior", (.05,.22,1.78), (.0,3.05,1.14), 23, cameras)
    camera("HutLayout", (.0,.70,11), (.0,.70,0), 35, cameras, ortho=13.4)
    scene.camera=main
    scene.render.engine="CYCLES"
    scene.cycles.device="CPU"
    scene.cycles.samples=48
    scene.cycles.use_denoising=True
    scene.cycles.max_bounces=8
    scene.render.resolution_x,scene.render.resolution_y=1500,1000
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"
    scene.render.image_settings.color_mode="RGB"
    scene.render.film_transparent=False
    scene.render.threads_mode,scene.render.threads="FIXED",6
    scene.view_settings.view_transform="AgX"
    scene.view_settings.look="AgX - Medium High Contrast"
    scene.view_settings.exposure=.65
    scene.render.filepath=str(ROOT/f"{STEM}.render.png")
    bpy.context.view_layer.update()


def world_bounds(obj):
    points=[obj.matrix_world@Vector(corner) for corner in obj.bound_box]
    return ([min(p[i] for p in points) for i in range(3)], [max(p[i] for p in points) for i in range(3)])


def inspect():
    scene=bpy.context.scene
    if scene.unit_settings.system!="METRIC" or scene.unit_settings.scale_length!=1:
        raise ValueError("Scene is not in metres")
    if scene.camera is None or scene.camera.name!="HutExterior":
        raise ValueError("Exterior camera is not active")
    required=["Bed.StrawMat","Table.Top","Table.EmptyBowl","Washing.WoodBasin","Door.OpenLeaf","Window.Mullion"]
    for name in required:
        obj=bpy.data.objects.get(name)
        if obj is None or obj.type!="MESH" or not obj.data.polygons:
            raise ValueError(f"Missing actual mesh {name}")
    meshes=[obj for obj in scene.objects if obj.type=="MESH"]
    if len(meshes)<200:
        raise ValueError(f"Too few mesh objects: {len(meshes)}")
    for obj in meshes:
        if not obj.data.vertices or not obj.data.polygons:
            raise ValueError(f"Empty mesh {obj.name}")
        if any(not math.isfinite(c) for vertex in obj.data.vertices for c in vertex.co):
            raise ValueError(f"Nonfinite geometry {obj.name}")
    support_checks=0
    for prefix,top_name in [("Table.Leg","Table.Top"),("Stool.Leg","Stool.Seat")]:
        top_bottom=world_bounds(bpy.data.objects[top_name])[0][2]
        legs=[obj for obj in meshes if obj.name.startswith(prefix)]
        if len(legs)!=4:
            raise ValueError(f"Expected four support legs for {top_name}")
        for leg in legs:
            lo,hi=world_bounds(leg)
            if abs(lo[2]-FLOOR_Z)>0.0001 or abs(hi[2]-top_bottom)>0.0001:
                raise ValueError(f"Furniture support does not contact floor and top: {leg.name}")
            support_checks+=2
    corridor={"x":[-.55,.55],"y":[-.90,3.95],"z":[.33,2.0]}
    approach={"x":[-1.2,1.2],"y":[-6.5,-1.35],"z":[.05,1.4]}
    for label,region in [("retreat",corridor),("forest approach",approach)]:
        blocked=[]
        for obj in meshes:
            if not obj.get("walk_obstacle",False):
                continue
            lo,hi=world_bounds(obj)
            if all(hi[i]>region[axis][0] and lo[i]<region[axis][1] for i,axis in enumerate(["x","y","z"])):
                blocked.append(obj.name)
        if blocked:
            raise ValueError(f"{label} bounds obstructed: {blocked}")
    graph=bpy.context.evaluated_depsgraph_get()
    for z in [.48,1.25,2.25]:
        hit,_,_,_,obj,_=scene.ray_cast(graph,Vector((0,-.2,z)),Vector((0,1,0)),distance=.4)
        if hit:
            raise ValueError(f"Door opening blocked at z={z}: {obj.name}")
    hit,_,_,_,obj,_=scene.ray_cast(graph,Vector((2.35,3.25,1.72)),Vector((-1,0,0)),distance=.45)
    if hit:
        raise ValueError(f"Window opening blocked: {obj.name}")
    hit,_,_,_,obj,_=scene.ray_cast(graph,Vector((1.29,1.66,4.5)),Vector((0,0,-1)),distance=2.0)
    if hit:
        raise ValueError(f"Roof defect is covered: {obj.name}")
    view_targets={"door":(0,-.05,1.3),"washing":(1.82,-1.19,.6),"roof":(1.29,1.66,3.0)}
    for label,point in view_targets.items():
        direction=Vector(point)-scene.camera.location
        hit,_,_,_,obj,_=scene.ray_cast(graph,scene.camera.location,direction.normalized(),distance=direction.length)
        if hit and obj.name.startswith("Forest."):
            raise ValueError(f"Exterior camera {label} view blocked by {obj.name}")
    external=[image.filepath for image in bpy.data.images if image.source=="FILE" and image.packed_file is None]
    if external or bpy.data.libraries:
        raise ValueError(f"External resources present: {external}")
    effects=bpy.data.collections["07.OptionalProtectionStudy"]
    if not effects.hide_render or not effects.hide_viewport:
        raise ValueError("Optional protection must remain disabled for the initial hut")
    furniture_bounds={name:world_bounds(bpy.data.objects[name]) for name in required}
    return {
        "status":"dimensioned_study_checks_passed",
        "not_game_asset_acceptance":True,
        "application_version":bpy.app.version_string,
        "scene_stage":scene["narrative_stage"],
        "dimensions_basis":scene["dimensions_basis"],
        "room_clear_dimensions_m":list(scene["clear_room_dimensions_m"]),
        "floor_elevation_m":FLOOR_Z,
        "ridge_elevation_m":RIDGE_Z,
        "retreat_corridor_m":corridor,
        "forest_approach_m":approach,
        "door_clear_width_m":1.12,
        "opening_ray_checks":{"door":3,"window":1,"roof_defect":1},
        "exterior_camera_forest_occlusion_rays":3,
        "furniture_support_contact_checks":support_checks,
        "mesh_objects":len(meshes),
        "vertices":sum(len(obj.data.vertices) for obj in meshes),
        "polygons":sum(len(obj.data.polygons) for obj in meshes),
        "materials":len(bpy.data.materials),
        "cameras":[obj.name for obj in scene.objects if obj.type=="CAMERA"],
        "lights":[obj.name for obj in scene.objects if obj.type=="LIGHT"],
        "selected_object_bounds_m":furniture_bounds,
        "unpacked_external_images":external,
        "linked_libraries":[],
        "optional_protection_visible":False,
        "check_scope":"actual world-space obstacle bounds for two corridors and five opening rays; not full surface intersection, character collision or runtime navigation",
    }


def renders():
    scene=bpy.context.scene
    scene.render.filepath=str(ROOT/f"{STEM}.render.png")
    bpy.ops.render.render(write_still=True)
    scene.camera=bpy.data.objects["HutInterior"]
    scene.render.resolution_x,scene.render.resolution_y=1400,950
    scene.render.filepath=str(ROOT/f"{STEM}.interior.png")
    bpy.ops.render.render(write_still=True)
    roof=bpy.data.collections["02.DamagedRoof"]
    forest=bpy.data.collections["06.ForestContext"]
    roof.hide_render,forest.hide_render=True,True
    scene.camera=bpy.data.objects["HutLayout"]
    scene.render.resolution_x,scene.render.resolution_y=1100,1100
    scene.cycles.samples=24
    scene.render.filepath=str(ROOT/f"{STEM}.layout.png")
    bpy.ops.render.render(write_still=True)
    roof.hide_render,forest.hide_render=False,False
    scene.camera=bpy.data.objects["HutExterior"]
    scene.render.resolution_x,scene.render.resolution_y=1500,1000
    scene.cycles.samples=48
    scene.render.filepath=str(ROOT/f"{STEM}.render.png")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=["build","verify","render"],default="build")
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    if args.mode=="build":
        construct()
        report=inspect()
        bpy.context.preferences.filepaths.save_version=0
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/f"{STEM}.blend"))
        report["verification_context"]="constructed_before_save"
        output=ROOT/f"{STEM}.build-checks.json"
    else:
        expected=ROOT/f"{STEM}.blend"
        if Path(bpy.data.filepath).resolve()!=expected:
            raise ValueError(f"Wrong opened file: {bpy.data.filepath}")
        report=inspect()
        report["verification_context"]="fresh_background_process_after_reopen"
        output=ROOT/f"{STEM}.reopen-checks.json"
        if args.mode=="render":
            renders()
            inspect()
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))


if __name__=="__main__":
    main()
