"""Compose a bounded hut core from the saved region, with measured authoring guides."""

import argparse
import html
import json
import math
import random
import sys
from array import array
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_wanqing_hut_study as hut
import build_wanqing_region_study as region

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "Candidates/wanqing-region-study-2026-09-06-05/wanqing-region-study-2026-09-06-05.blend"
NAME = "wanqing-core-study-2026-09-07-01"
ROUTES = {
    "wanqing_hut.retreat": [(0, -.8), (0, -6.5), (-2.5, -11), (-6, -18), (-5, -26)],
    "wanqing_hut.washing_approach": [(0, -1.3), (1.4, -1.55)],
    "wanqing_hut.short_return": [(-6, -18), (3, -23), (12, -16), (10, -8), (5, -3), (1.4, -1.55)],
}
MARKERS = {"DoorRetreat": "wanqing_hut.door", "WashingInteraction": "wanqing_hut.washing",
           "ForestApproach": "wanqing_hut.forest_edge", "IndoorSafetyPoint": "wanqing_hut.indoor_safety"}
VIEWS = {"hut_ground": ((9.5, -15.5), (0, 1.1, 1.35)),
         "forest_return": ((-8.0, -17.0), (0, 1.0, 1.45))}
TREE_SITES = [(-10, 5), (-14, 9), (-20, 7), (-24, 14), (-14, 18), (-7, 16),
              (9, 7), (14, 11), (20, 7), (24, 17), (13, 19), (5, 21),
              (-12, -6), (-16, -11), (-23, -8), (-24, -19), (-17, -24),
              (12, -3), (18, -6), (22, -13), (23, -23), (15, -29),
              (-32, 3), (-30, 23), (30, 5), (31, 26), (-3, 31), (20, 33)]
require = region.require


def path_distance(x, y):
    distance = math.inf
    for route in ROUTES.values():
        for a, b in zip(route, route[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            t = min(1, max(0, ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy)))
            distance = min(distance, math.hypot(x - a[0] - t * dx, y - a[1] - t * dy))
    return distance


def sight_distance(x, y):
    distances = []
    for start, _ in VIEWS.values():
        dx, dy = -start[0], -.1 - start[1]
        t = min(1, max(0, ((x - start[0]) * dx + (y - start[1]) * dy) / (dx * dx + dy * dy)))
        distances.append(math.hypot(x - start[0] - t * dx, y - start[1] - t * dy))
    return min(distances)


class CoreGround:
    def __init__(self):
        self.base = region.TerrainField(region.RegionSettings())

    def height(self, x, y):
        base = self.base.height(x, y)
        border = 1 - region.smoothstep((max(abs(x), abs(y)) - 32) / 8)
        house = region.smoothstep((max(abs(x) - 3.2, abs(y - 1.0) - 4.8)) / 3)
        path = region.smoothstep((path_distance(x, y) - .65) / 1.8)
        berms = .34 * math.exp(-((x + 13) / 8) ** 2 - ((y - 5) / 9) ** 2)
        berms += .28 * math.exp(-((x - 15) / 7) ** 2 - ((y - 8) / 10) ** 2)
        small = .019 * math.sin(x * 2.1 + y * .8) * math.cos(y * 1.9 - x * .3)
        return base + border * house * path * (berms + small)

    def color(self, x, y):
        distance = path_distance(x, y)
        noise = .5 + .25 * math.sin(x * .67 + y * .34) + .25 * math.sin(y * .91 - x * .22)
        clearing = 1 - region.smoothstep((math.hypot(x, y - .2) - 4.6) / 7)
        wear = 1 - region.smoothstep((distance - .62 - noise * .16) / 1.45)
        wear = max(wear, clearing * .9)
        turf = Vector((.105 + noise * .034, .15 + noise * .04, .065 + noise * .019))
        earth = Vector((.205 + noise * .035, .139 + noise * .03, .078 + noise * .02))
        result = turf.lerp(earth, wear)
        wet = math.exp(-((x - 1.55) / 1.45) ** 2 - ((y + 2.25) / 1.8) ** 2)
        drip = math.exp(-((y + .6) / .35) ** 2) * (1 - region.smoothstep((abs(x) - 2.1) / .8))
        result *= 1 - max(wet * .37, drip * .20)
        return (*result, 1)


def ground_mesh(name, half, field, destination, material, exclude_core=False):
    step = .5
    cells = round(half * 2 / step)
    vertices, faces, positions = [], [], {}
    def corner(column, row):
        key = (column, row)
        if key not in positions:
            x, y = -half + column * step, -half + row * step
            positions[key] = len(vertices)
            vertices.append((x, y, field.height(x, y)))
        return positions[key]
    for row in range(cells):
        y = -half + (row + .5) * step
        for column in range(cells):
            x = -half + (column + .5) * step
            if exclude_core and abs(x) < 40 and abs(y) < 40:
                continue
            faces.append((corner(column, row), corner(column + 1, row),
                          corner(column + 1, row + 1), corner(column, row + 1)))
    obj = region.mesh_object(name, vertices, faces, destination, material, "core_ground" if not exclude_core else "background_ground")
    colors = obj.data.color_attributes.new(name="TerrainTint", type="FLOAT_COLOR", domain="POINT")
    colors.data.foreach_set("color", array("f", (value for x, y, _ in vertices for value in field.color(x, y))))
    uv = obj.data.uv_layers.new(name="StudyUV")
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
        for loop in polygon.loop_indices:
            point = obj.data.vertices[obj.data.loops[loop].vertex_index].co
            uv.uv[loop].vector = ((point.x + 40) / 80, (point.y + 40) / 80)
    obj["authoring_only"] = True
    return obj


def append_source(destination, templates):
    names = [f"TreeTemplate.Detailed.{index}" for index in range(3)]
    with bpy.data.libraries.load(str(SOURCE), link=False) as (available, selected):
        require(set(region.HUT_COLLECTIONS).issubset(available.collections), "Source hut collections changed")
        require(set(names).issubset(available.objects), "Source tree templates missing")
        selected.collections = list(region.HUT_COLLECTIONS)
        selected.objects = names
    for collection in selected.collections:
        destination.children.link(collection)
    for obj in selected.objects:
        require(obj.parent is None and not obj.modifiers and not obj.constraints, "Unsupported source tree transform")
        templates.objects.link(obj)
    bpy.context.view_layer.update()
    protected = {obj.name: region.protected_object_state(obj, obj.matrix_world) for obj in destination.all_objects}
    for library in tuple(bpy.data.libraries):
        users = bpy.data.user_map()
        require(not users.get(library) and not any(item.library == library for item in users), "Source append retained a linked dependency")
        bpy.data.libraries.remove(library)
    return selected.objects, protected


def plantable(x, y, radius=.8):
    return (math.hypot(x, y - 1.5) > 5.4 + radius and path_distance(x, y) > 1.3 + radius
            and sight_distance(x, y) > .75 + radius and not (-3.2 < x < 3.2 and -7 < y < 7))


def add_vegetation(surface, tree_sources, trees, shrubs, details, materials):
    rng = random.Random(2026090701)
    tree_records, shrub_records = [], []
    for index, (x, y) in enumerate(TREE_SITES):
        require(plantable(x, y, .35), f"Tree site enters a protected route: {index}")
        source = tree_sources[index % 3]
        obj = bpy.data.objects.new(f"Core.Tree.{index:02}", source.data)
        trees.objects.link(obj)
        scale = rng.uniform(1.35, 1.95)
        lowest = min(vertex.co.z for vertex in source.data.vertices)
        ground = region.ground_height(surface, x, y)
        obj.location = (x, y, ground - lowest * scale - .035)
        obj.scale = (scale, scale, scale)
        obj.rotation_euler.z = rng.uniform(0, math.tau)
        obj["asset_role"] = "core_tree_instance"
        bark = {vertex for polygon in source.data.polygons if polygon.material_index == 0 for vertex in polygon.vertices}
        trunk = [source.data.vertices[i].co for i in bark]
        lower = [point for point in trunk if point.z < lowest + .25]
        radius = max(math.hypot(point.x, point.y) for point in lower) * scale
        top = max(point.z for point in trunk) * scale + obj.location.z
        tree_records.append({"object": obj.name, "ground_m": ground, "root_burial_m": .035,
                             "capsule_radius_m": radius, "capsule_bottom_m": ground,
                             "capsule_top_m": top, "xy_m": [x, y]})
        if math.hypot(x, y) < 21:
            for root in range(4):
                angle = root * math.pi / 2 + index * 1.17
                length = rng.uniform(.48, .85)
                end = Vector((x + math.cos(angle) * length, y + math.sin(angle) * length, 0))
                end.z = region.ground_height(surface, end.x, end.y) - .025
                start = Vector((x, y, ground + .22))
                root_obj = hut.beam(f"Core.Root.{index:02}.{root}", start, end, .055, details, materials["root"], vertices=8)
                root_obj["asset_role"] = "decorative_root"
        for bush in range(3 if index % 3 else 4):
            angle, distance = rng.uniform(0, math.tau), rng.uniform(1.1, 3.4)
            bx, by = x + math.cos(angle) * distance, y + math.sin(angle) * distance
            if not plantable(bx, by, .65):
                continue
            z = region.ground_height(surface, bx, by)
            height, width = rng.uniform(.50, 1.0), rng.uniform(.8, 1.45)
            leaf = hut.leaf_cluster(f"Core.Understory.{index:02}.{bush}", (bx, by, z + height * .54),
                                    (width, width * .78, height), shrubs, materials["shrub"])
            leaf["asset_role"] = "decorative_shrub"
            hut.beam(f"Core.UnderstoryStem.{index:02}.{bush}", (bx, by, z - .025),
                     (bx, by, z + height * .75), .035, shrubs, materials["root"], vertices=6)
            shrub_records.append({"object": leaf.name, "xy_m": [bx, by], "ground_m": z})
    grass_vertices, grass_faces = [], []
    leaf_vertices, leaf_faces = [], []
    grass_clumps = leaf_count = 0
    for _ in range(1500):
        x, y = rng.uniform(-32, 32), rng.uniform(-32, 32)
        distance = path_distance(x, y)
        if not plantable(x, y, .05) or distance < 1.2:
            continue
        nearest_tree = min(math.hypot(x - a, y - b) for a, b in TREE_SITES)
        probability = .44 if nearest_tree < 5 else .08
        if rng.random() > probability:
            continue
        grass_clumps += 1
        for _ in range(rng.randrange(10, 21)):
            bx, by = x + rng.uniform(-.34, .34), y + rng.uniform(-.34, .34)
            z = region.ground_height(surface, bx, by) - .008
            angle, height = rng.uniform(0, math.tau), rng.uniform(.13, .36)
            side = Vector((math.cos(angle), math.sin(angle), 0)) * rng.uniform(.015, .027)
            root = Vector((bx, by, z))
            bend = Vector((math.sin(angle), -math.cos(angle), 0)) * height * .20
            n = len(grass_vertices)
            grass_vertices.extend(tuple(p) for p in (root - side, root + side,
                                  root + side * .45 + bend + Vector((0, 0, height * .58)),
                                  root + bend * 1.5 + Vector((0, 0, height)),
                                  root - side * .45 + bend + Vector((0, 0, height * .58))))
            grass_faces.extend(((n, n + 1, n + 2), (n, n + 2, n + 4), (n + 4, n + 2, n + 3)))
    for _ in range(850):
        x, y = rng.uniform(-24, 24), rng.uniform(-25, 24)
        if math.hypot(x, y - 1.5) < 4 or min(math.hypot(x - a, y - b) for a, b in TREE_SITES) > 5.5:
            continue
        z = region.ground_height(surface, x, y) + .004
        angle, length = rng.uniform(0, math.tau), rng.uniform(.08, .18)
        axis = Vector((math.cos(angle), math.sin(angle), 0)) * length
        side = Vector((-math.sin(angle), math.cos(angle), 0)) * length * .3
        p = Vector((x, y, z))
        n = len(leaf_vertices)
        leaf_vertices.extend(tuple(v) for v in (p - axis / 2, p + side, p + axis / 2, p - side, p + Vector((0, 0, .006))))
        leaf_faces.extend(((n, n + 1, n + 4), (n + 1, n + 2, n + 4), (n + 2, n + 3, n + 4), (n + 3, n, n + 4)))
        leaf_count += 1
    region.mesh_object("Core.GrassClumps", grass_vertices, grass_faces, details, materials["grass"], "decorative_ground_cover")
    region.mesh_object("Core.LeafLitter", leaf_vertices, leaf_faces, details, materials["litter"], "decorative_litter")
    for index, (x, y) in enumerate(((-4.8, -3.8), (7, -1), (-9, 3), (7, 6), (-12, -13), (17, -5), (15, -20))):
        require(path_distance(x, y) > 1.4, "Rock site obstructs a route")
        z = region.ground_height(surface, x, y)
        height = rng.uniform(.12, .25)
        obj = hut.soft_shape(f"Core.EmbeddedStone.{index:02}", (x, y, z + height * .32),
                             (height * 3.3, height * 2.1, height), details, materials["stone"])
        obj["asset_role"] = "embedded_ground_stone"
    return {"trees": tree_records, "shrubs": shrub_records, "grass_clumps": grass_clumps, "fallen_leaves": leaf_count}


def make_colliders(hut_collection, tree_records, destination, material):
    records = []
    for source in hut_collection.all_objects:
        if source.type == "MESH" and source.get("walk_obstacle", False):
            low, high = hut.world_bounds(source)
            center, size = [(a + b) / 2 for a, b in zip(low, high)], [b - a for a, b in zip(low, high)]
            obj = hut.box("Collision." + source.name, center, size, destination, material, bevel=0)
            obj.display_type = "WIRE"
            obj["collision_shape"] = "world_aabb"
            obj["source_object"] = source.name
            records.append({"object": obj.name, "source_object": source.name, "shape": "world_aabb", "minimum_m": low, "maximum_m": high})
    for index, tree in enumerate(tree_records):
        x, y = tree["xy_m"]
        radius = tree["capsule_radius_m"]
        low, high = tree["capsule_bottom_m"], tree["capsule_top_m"]
        obj = hut.beam(f"Collision.TreeTrunk.{index:02}", (x, y, low), (x, y, high), radius, destination, material, vertices=8)
        obj.display_type = "WIRE"
        obj["collision_shape"] = "vertical_cylinder"
        obj["source_object"] = tree["object"]
        records.append({"object": obj.name, "source_object": tree["object"], "shape": "vertical_cylinder",
                        "center_xy_m": [x, y], "radius_m": radius, "bottom_m": low, "top_m": high})
    return records


def layout_svg(output, manifest):
    def xy(x, y):
        return (40 + (x + 40) * 8, 40 + (40 - y) * 8)
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="760" viewBox="0 0 900 760">',
           '<rect width="900" height="760" fill="#ece8dc"/>',
           '<rect x="40" y="40" width="640" height="640" fill="#d0d6b7" stroke="#5b664c"/>']
    for tree in manifest["vegetation"]["trees"]:
        x, y = xy(*tree["xy_m"])
        svg.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{tree["capsule_radius_m"] * 8:.2f}" fill="#5c4934"/>')
        svg.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="13" fill="none" stroke="#6b8058" stroke-width="1"/>')
    for collider in manifest["collision_guides"]:
        if collider["shape"] != "world_aabb":
            continue
        low, high = collider["minimum_m"], collider["maximum_m"]
        x, y = xy(low[0], high[1])
        svg.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{(high[0]-low[0])*8:.2f}" height="{(high[1]-low[1])*8:.2f}" fill="#815f45" fill-opacity=".72"/>')
    for key, route in manifest["routes_m"].items():
        points = " ".join(f"{xy(p[0],p[1])[0]:.2f},{xy(p[0],p[1])[1]:.2f}" for p in route)
        svg.append(f'<polyline points="{points}" fill="none" stroke="#b76632" stroke-width="9" stroke-opacity=".55" stroke-linejoin="round"/>')
        svg.append(f'<polyline points="{points}" fill="none" stroke="#713d20" stroke-width="1.5" stroke-dasharray="4 3"/>')
    for index, marker in enumerate(manifest["interaction_markers"]):
        x, y = xy(*marker["world_m"][:2])
        svg.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="#234a62"/>')
        svg.append(f'<text x="710" y="{220+index*42}" font-size="12" fill="#263b43">{html.escape(marker["stable_id"])}</text>')
    svg.extend(['<g font-family="sans-serif" fill="#263b43"><text x="40" y="24" font-size="18">Wanqing hut core — 80 × 80 m</text>',
                '<text x="705" y="65" font-size="14">Authoring layout</text>',
                '<text x="705" y="93" font-size="12">+Y upward; metres; Z-up</text>',
                '<text x="705" y="125" font-size="12">Brown: simplified obstacles</text>',
                '<text x="705" y="151" font-size="12">Ochre: proposed walking route</text>',
                '<text x="705" y="177" font-size="12">Circles: trunk / canopy context</text>',
                '<text x="40" y="711" font-size="13">Existing hut origin preserved. Geometry guides only; runtime collision and walking are not verified.</text>',
                '<text x="40" y="736" font-size="13">Coordinates and routes are art estimates, not canonical geography. Background is outside the playable proposal.</text></g></svg>'])
    (output / "core_walk_layout.svg").write_text("\n".join(svg), encoding="utf-8")


def inspect(manifest):
    scene = bpy.context.scene
    require(scene.unit_settings.system == "METRIC" and scene.unit_settings.scale_length == 1, "Core units changed")
    terrain = [scene.objects["Core.Ground"], scene.objects["Background.Ground"]]
    surface = region.terrain_tree(terrain)
    count = 0
    for obj in scene.objects:
        if obj.type == "MESH":
            require(obj.data.vertices and obj.data.polygons, f"Empty mesh: {obj.name}")
            require(all(math.isfinite(v) for p in obj.data.vertices for v in p.co), f"Nonfinite mesh: {obj.name}")
            count += len(obj.data.vertices)
    for name in MARKERS:
        require(name in scene.objects and scene.objects[name].get("gameplay_id") == MARKERS[name], f"Missing stable marker: {name}")
    for stone in (obj for obj in scene.objects if obj.name.startswith("Foundation.Stone")):
        low, high = hut.world_bounds(stone)
        ground = region.ground_height(surface, (low[0] + high[0]) / 2, (low[1] + high[1]) / 2)
        require(abs(low[2] - ground) < .0001, f"Detached hut foundation: {stone.name}")
    require(bpy.data.collections["07.OptionalProtectionStudy"].hide_render, "Initial state shows protection effect")
    graph = bpy.context.evaluated_depsgraph_get()
    for name, (start, _) in VIEWS.items():
        camera = scene.objects["CoreCamera." + name]
        endpoint = Vector((0, -.12, 1.25))
        direction = endpoint - camera.location
        hit, _, _, _, obj, _ = scene.ray_cast(graph, camera.location, direction.normalized(), distance=direction.length - .02)
        require(not hit, f"Door sight line blocked in {name}: {obj.name if obj else ''}")
    require(not bpy.data.libraries, "Core has a linked Blender dependency")
    require(not any(i.source == "FILE" and i.packed_file is None for i in bpy.data.images), "Unpacked core image dependency")
    require(region.file_state(SOURCE) == manifest["source_file_state"], "Source region05 changed")
    return {"status": "passed", "mesh_object_vertex_total": count, "core_grid_vertices": len(scene.objects["Core.Ground"].data.vertices),
            "tree_instances": len(manifest["vegetation"]["trees"]), "stable_markers": len(MARKERS),
            "source05_unchanged": True, "door_sight_lines_clear": list(VIEWS),
            "runtime_collision_verified": False, "runtime_walk_verified": False}


def build(output):
    require(bpy.app.background and not bpy.data.filepath and "--factory-startup" in sys.argv, "Build only in a separate factory background process")
    require(not output.exists(), "Refusing to replace a core candidate")
    require(SOURCE.is_file(), "Saved source05 is missing")
    source_state = region.file_state(SOURCE)
    for obj in tuple(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene = bpy.context.scene
    scene.name = NAME
    scene.unit_settings.system, scene.unit_settings.scale_length = "METRIC", 1
    shell, ground = region.group("00.Hut"), region.group("10.CoreGround")
    trees, shrubs, details = region.group("20.CoreTrees"), region.group("21.Understory"), region.group("22.GroundDetails")
    background, guides, templates = region.group("30.BackgroundOnly"), region.group("80.CollisionGuides"), region.group("90.SourceTemplates")
    sources, protected = append_source(shell, templates)
    templates.hide_render = templates.hide_viewport = True
    guides.hide_render = guides.hide_viewport = True
    material = region.terrain_material({"surface": hut.surface})
    material.name = "Core.GroundMaterial"
    material.node_tree.nodes["Bump"].inputs["Distance"].default_value = .025
    field = CoreGround()
    core = ground_mesh("Core.Ground", 40, field, ground, material)
    ring = ground_mesh("Background.Ground", 70, field, background, material, exclude_core=True)
    bpy.context.view_layer.update()
    surface = region.terrain_tree((core, ring))
    materials = {name: hut.surface("Core." + name, color, roughness, texture=texture)
                 for name, color, roughness, texture in (
                     ("root", (.105, .07, .039), .94, True), ("shrub", (.072, .14, .037), .9, False),
                     ("grass", (.15, .215, .065), .92, False), ("litter", (.23, .145, .051), .98, False),
                     ("stone", (.28, .29, .245), .94, True), ("collision", (.6, .2, .07), .9, False))}
    vegetation = add_vegetation(surface, sources, trees, shrubs, details, materials)
    bpy.context.view_layer.update()
    colliders = make_colliders(shell, vegetation["trees"], guides, materials["collision"])
    for name, stable_id in MARKERS.items():
        bpy.data.objects[name]["gameplay_id"] = stable_id
    lighting, cameras = region.group("60.CoreLighting"), region.group("70.CoreCameras")
    scene.world = bpy.data.worlds.new("Core.NeutralDaylight")
    require(scene.world.node_tree is not None, "Blender world node tree is unavailable")
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (.50, .57, .66, 1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = .48
    sun_data = bpy.data.lights.new("Core.Sun", "SUN")
    sun_data.energy, sun_data.angle, sun_data.color = 2.3, math.radians(12), (1.0, .90, .76)
    sun = bpy.data.objects.new("Core.Sun", sun_data)
    lighting.objects.link(sun)
    sun.rotation_euler = (math.radians(28), math.radians(-24), math.radians(-32))
    for name, (xy, target) in VIEWS.items():
        camera_data = bpy.data.cameras.new("CoreCamera." + name)
        camera_data.lens = 42
        camera = bpy.data.objects.new(camera_data.name, camera_data)
        cameras.objects.link(camera)
        camera.location = (*xy, region.ground_height(surface, *xy) + 1.65)
        camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()
        camera_data.clip_start, camera_data.clip_end = .05, 300
    scene.camera = scene.objects["CoreCamera.hut_ground"]
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 960, 640, 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.threads_mode, scene.render.threads = "FIXED", 2
    scene.render.use_file_extension = True
    scene.eevee.taa_render_samples = 16
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = .35
    bpy.context.view_layer.update()
    require(protected == {obj.name: region.protected_object_state(obj, obj.matrix_world) for obj in shell.all_objects}, "Core composition changed source hut geometry")
    routes = {key: [[x, y, region.ground_height(surface, x, y)] for x, y in points] for key, points in ROUTES.items()}
    manifest = {"name": NAME, "status": "bounded_authoring_core_study", "source_blend": str(SOURCE), "source_file_state": source_state,
                "units": "metres", "up_axis": "Z", "origin": "unchanged_source_hut_origin", "core_xy_bounds_m": [-40, 40, -40, 40],
                "background_xy_bounds_m": [-70, 70, -70, 70], "background_playable": False,
                "hut_state": "initial_damaged", "geometry_source_hut_unchanged": True,
                "dimensions_and_vegetation_basis": "art_estimate_not_novel_geography", "vegetation": vegetation,
                "routes_m": routes, "route_width_design_m": 2.0, "collision_guides": colliders,
                "collision_scope": "measured simplified hut obstacle AABBs and trunk cylinders; ground mesh is the terrain source; no runtime solver or navigation acceptance",
                "interaction_markers": [{"object": name, "stable_id": stable_id, "world_m": list(bpy.data.objects[name].matrix_world.translation)} for name, stable_id in MARKERS.items()],
                "render_views": {name: {"camera": "CoreCamera." + name, "file": name + ".png", "eye_height_m": 1.65} for name in VIEWS},
                "render_settings": {"engine": "BLENDER_EEVEE", "resolution": [960, 640], "samples": 16, "threads": 2},
                "runtime_integrated": False, "production_ready": False}
    checks = inspect(manifest)
    output.mkdir(parents=True)
    for name, data in (("scene_manifest.json", manifest), ("build_checks.json", checks)):
        with (output / name).open("x", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
    layout_svg(output, manifest)
    scene.render.filepath = ""
    bpy.ops.wm.save_as_mainfile(filepath=str(output / (NAME + ".blend")))
    print("CORE_BUILD_PASSED", json.dumps(checks), flush=True)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("build", "render", "verify"), required=True)
    parser.add_argument("--view", choices=tuple(VIEWS))
    args = parser.parse_args(argv)
    require(bpy.app.background, "Never run the core entry against the foreground GUI")
    output = ROOT / "Candidates" / NAME
    if args.mode == "build":
        build(output)
        return
    path = output / (NAME + ".blend")
    require(Path(bpy.data.filepath).resolve() == path, "Opened file does not match this candidate")
    manifest = json.loads((output / "scene_manifest.json").read_text())
    require(manifest["name"] == NAME, "Core manifest identity mismatch")
    if args.mode == "render":
        require(args.view is not None, "Render exactly one declared view")
        destination = output / (args.view + ".png")
        require(not destination.exists(), "Refusing to overwrite a prior core image")
        bpy.context.scene.camera = bpy.data.objects["CoreCamera." + args.view]
        bpy.context.scene.render.filepath = str(destination)
        result = bpy.ops.render.render(write_still=True)
        require(result == {"FINISHED"} and destination.is_file() and destination.stat().st_size > 0, "Core render did not finish")
        print("CORE_RENDER_PASSED", args.view, flush=True)
    else:
        before = region.file_state(path)
        checks = inspect(manifest)
        decoded = []
        for view in VIEWS:
            image_path = output / (view + ".png")
            require(image_path.is_file(), f"Missing actual core image: {view}")
            image = bpy.data.images.load(str(image_path), check_existing=False)
            try:
                require(tuple(image.size) == (960, 640) and image.has_data, "Core PNG did not decode at the declared size")
                decoded.append(view)
            finally:
                bpy.data.images.remove(image)
        require(region.file_state(path) == before, "Verification changed the saved core")
        checks["decoded_views"] = decoded
        with (output / "reopen_checks.json").open("x", encoding="utf-8") as handle:
            json.dump(checks, handle, ensure_ascii=False, indent=2, allow_nan=False)
        print("CORE_REOPEN_PASSED", json.dumps(checks), flush=True)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
