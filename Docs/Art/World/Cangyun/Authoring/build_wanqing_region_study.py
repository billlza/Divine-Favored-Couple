"""Build, render and reopen-check a bounded Wanqing Mountain region study."""

import argparse
import copy
import json
import math
import random
import runpy
import sys
import time
from array import array
from dataclasses import asdict, dataclass
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector, noise
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree


ROOT = Path(__file__).resolve().parent
HUT_SOURCE = ROOT / "wanqing-hut-study-2026-09-05-01.blend"
HUT_SCRIPT = ROOT / "build_wanqing_hut_study.py"
HUT_COLLECTIONS = ("01.HutShell", "02.DamagedRoof", "03.Furnishings", "04.PorchAndWashing", "07.OptionalProtectionStudy", "10.LayoutMarkers")
ROUTE_CONTROLS = ((0, -6.5, 0), (0, -45, 0), (26, -95, 1), (85, -140, 3), (160, -200, 8), (210, -280, 6), (160, -330, -2), (60, -310, -6), (-50, -275, -2), (-180, -255, 6), (-320, -280, 11))
REGION_VIEWS = {"overview": ("RegionOverview", "overview.png"), "hut_ground": ("HutGroundContext", "hut_ground.png"), "forest_return": ("ForestReturn", "forest_return.png")}
TREE_TEMPLATES = tuple(f"TreeTemplate.{detail}.{index}" for detail in ("Detailed", "Distant") for index in range(3))
SCATTER_OBJECTS = ("Forest.NearInstances.ArtEstimate", "Forest.DistantInstances.ArtEstimate")


@dataclass(frozen=True)
class RegionSettings:
    seed: int = 20260906
    tile_count: int = 4
    tile_width_m: float = 500.0
    tile_intervals: int = 128
    route_width_m: float = 3.6
    stream_level_m: float = -35.0
    stream_boundary_inset_m: float = 0.5
    stream_mesh_half_width_m: float = 9.5
    maximum_tree_instances: int = 2400
    detailed_tree_radius_m: float = 300.0
    render_samples: int = 40
    haze_density_per_m: float = 0.000075


@dataclass(frozen=True)
class TerrainSurface:
    tree: BVHTree
    vertices: list[Vector]
    triangles: list[tuple[int, int, int]]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_state(path):
    stat = path.stat()
    return {"size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def group(name, parent=None):
    require(name not in bpy.data.collections, f"Collection already exists: {name}")
    value = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(value)
    return value


def mesh_object(name, vertices, faces, destination, material, role):
    mesh = bpy.data.meshes.new(name + ".Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    destination.objects.link(obj)
    if material is not None:
        mesh.materials.append(material)
    obj["asset_role"] = role
    obj["artEstimate"] = True
    return obj


def smoothstep(value):
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def route_samples():
    result = []
    controls = [Vector(point) for point in ROUTE_CONTROLS]
    for index in range(len(controls) - 1):
        p0, p1 = controls[max(0, index - 1)], controls[index]
        p2, p3 = controls[index + 1], controls[min(len(controls) - 1, index + 2)]
        steps = max(4, math.ceil((p2 - p1).length / 4.0))
        for step in range(steps):
            t = step / steps
            result.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    result.append(controls[-1])
    return result


class TerrainField:
    def __init__(self, settings):
        self.settings = settings
        self.route = route_samples()
        self.route_tree = KDTree(len(self.route))
        for index, point in enumerate(self.route):
            self.route_tree.insert(Vector((point.x, point.y, 0)), index)
        self.route_tree.balance()

    def route_distance(self, x, y):
        query = Vector((x, y, 0))
        segments = set()
        for _, index, _ in self.route_tree.find_n(query, 4):
            if index > 0:
                segments.add(index - 1)
            if index < len(self.route) - 1:
                segments.add(index)
        best_distance, best_z = math.inf, 0.0
        for index in segments:
            a, b = self.route[index], self.route[index + 1]
            dx, dy = b.x - a.x, b.y - a.y
            t = min(1.0, max(0.0, ((x - a.x) * dx + (y - a.y) * dy) / (dx * dx + dy * dy)))
            distance = math.hypot(x - a.x - t * dx, y - a.y - t * dy)
            if distance < best_distance:
                best_distance, best_z = distance, a.z + t * (b.z - a.z)
        require(math.isfinite(best_distance), "Could not locate regional trail")
        return best_distance, best_z

    @staticmethod
    def stream_y(x):
        return -455.0 + 72.0 * math.sin(x / 230.0) + 22.0 * math.sin(x / 83.0)

    def height(self, x, y):
        hills = ((-610, 530, 330, 410, 460), (410, 660, 300, 360, 610), (-820, -240, 300, 510, 310), (850, -80, 310, 540, 390))
        height = -5.0 + 0.000012 * (x * x + y * y)
        for cx, cy, sx, sy, amplitude in hills:
            height += amplitude * math.exp(-((x - cx) / sx) ** 2 - ((y - cy) / sy) ** 2)
        seed = self.settings.seed * 0.00017
        detail = (22.0 * noise.noise(Vector((x * 0.004, y * 0.004, seed))) + 8.0 * noise.noise(Vector((x * 0.013, y * 0.013, seed + 8))) + 2.0 * noise.noise(Vector((x * 0.040, y * 0.040, seed + 17))))
        height += detail * (0.5 + min(max(height, 0) / 180, 1.5))
        channel_distance = abs(y - self.stream_y(x))
        if channel_distance < 62:
            channel = self.settings.stream_level_m - 1.2 + max(0, channel_distance - 4.5) * 0.42
            weight = 1.0 - smoothstep((channel_distance - 12) / 50)
            height = height * (1.0 - weight) + channel * weight
        distance, trail_z = self.route_distance(x, y)
        if distance < 20:
            weight = 1.0 - smoothstep((distance - 5.0) / 15.0)
            height = height * (1.0 - weight) + trail_z * weight
        clearing = smoothstep((math.hypot(x, y - 1.5) - 23.0) / 36.0)
        return height * clearing


def append_hut(destination):
    names = [*HUT_COLLECTIONS, "06.ForestContext"]
    with bpy.data.libraries.load(str(HUT_SOURCE), link=False) as (available, selected):
        require(all(name in available.collections for name in names), "Hut library does not contain its documented collections")
        selected.collections = names
    loaded = {collection.name: collection for collection in selected.collections}
    for name in HUT_COLLECTIONS:
        destination.children.link(loaded[name])
    protection = loaded["07.OptionalProtectionStudy"]
    require(protection.hide_viewport and protection.hide_render, "Initial hut must not show the optional protection study")
    require("Terrain.EarthSurface" not in bpy.data.objects, "The old 20m ground patch must not overlap regional terrain")
    require(not any(obj.type in {"CAMERA", "LIGHT"} for obj in destination.all_objects), "Hut import brought its old presentation rig")
    # Appending in 5.2 retains a Library ID with an extra bookkeeping user even
    # after every asset is local. Remove only that unreferenced record.
    users = bpy.data.user_map()
    for library in tuple(bpy.data.libraries):
        require(not any(asset.library == library for asset in users) and not users.get(library), "Hut append retained a linked data dependency")
        require(library.users == 1 and library.use_extra_user and not library.use_fake_user, "Unexpected imported library ownership")
        bpy.data.libraries.remove(library)
    return loaded["06.ForestContext"]


def terrain_material(helpers):
    material = helpers["surface"]("RegionTerrain.ArtEstimate", (0.11, 0.15, 0.08), 0.92)
    nodes, links = material.node_tree.nodes, material.node_tree.links
    shader = nodes["Principled BSDF"]
    color = nodes.new("ShaderNodeVertexColor")
    color.layer_name = "TerrainTint"
    geometry = nodes.new("ShaderNodeNewGeometry")
    texture = nodes.new("ShaderNodeTexNoise")
    texture.inputs["Scale"].default_value = 0.28
    texture.inputs["Detail"].default_value = 4
    links.new(geometry.outputs["Position"], texture.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.53, 0.56, 0.51, 1)
    ramp.color_ramp.elements[1].color = (1.0, 1.0, 0.91, 1)
    links.new(texture.outputs["Fac"], ramp.inputs["Fac"])
    multiply = nodes.new("ShaderNodeMixRGB")
    multiply.blend_type = "MULTIPLY"
    multiply.inputs[0].default_value = 1.0
    links.new(color.outputs["Color"], multiply.inputs[1])
    links.new(ramp.outputs["Color"], multiply.inputs[2])
    links.new(multiply.outputs["Color"], shader.inputs["Base Color"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.18
    bump.inputs["Distance"].default_value = 0.09
    links.new(texture.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return material


def build_terrain(field, destination, material):
    settings = field.settings
    half = settings.tile_count * settings.tile_width_m / 2
    stride = settings.tile_intervals + 1
    faces = [(j * stride + i, j * stride + i + 1, (j + 1) * stride + i + 1, (j + 1) * stride + i) for j in range(settings.tile_intervals) for i in range(settings.tile_intervals)]
    objects = []
    for row in range(settings.tile_count):
        for column in range(settings.tile_count):
            vertices, colors = [], []
            for j in range(stride):
                y = -half + row * settings.tile_width_m + j * settings.tile_width_m / settings.tile_intervals
                for i in range(stride):
                    x = -half + column * settings.tile_width_m + i * settings.tile_width_m / settings.tile_intervals
                    z = field.height(x, y)
                    vertices.append((x, y, z))
                    rock = smoothstep((z - 120) / 220)
                    variation = 0.8 + 0.3 * noise.noise(Vector((x * .017, y * .017, 31)))
                    low, high = Vector((0.10, 0.155, 0.065)), Vector((0.24, 0.27, 0.24))
                    tint = low.lerp(high, rock) * variation
                    if math.hypot(x, y - 1.5) < 13:
                        tint = Vector((0.17, 0.125, 0.075))
                    path_distance, _ = field.route_distance(x, y)
                    path_weight = 1.0 - smoothstep((path_distance - 1.3) / 3.5)
                    tint = tint.lerp(Vector((.23, .185, .11)) * variation, path_weight)
                    colors.extend((*tint, 1.0))
            obj = mesh_object(f"Terrain.Tile.{row:02}.{column:02}", vertices, faces, destination, material, "terrain_tile")
            obj["tile_row"], obj["tile_column"] = row, column
            tint = obj.data.color_attributes.new(name="TerrainTint", type="FLOAT_COLOR", domain="POINT")
            tint.data.foreach_set("color", colors)
            uv = obj.data.uv_layers.new(name="StudyUV")
            for polygon in obj.data.polygons:
                polygon.use_smooth = True
                for loop_index in polygon.loop_indices:
                    point = obj.data.vertices[obj.data.loops[loop_index].vertex_index].co
                    uv.uv[loop_index].vector = ((point.x + half) / (2 * half), (point.y + half) / (2 * half))
            objects.append(obj)
    return objects


def terrain_tree(objects):
    vertices, triangles = [], []
    for obj in objects:
        offset = len(vertices)
        obj.data.calc_loop_triangles()
        vertices.extend(obj.matrix_world @ vertex.co for vertex in obj.data.vertices)
        triangles.extend(tuple(offset + index for index in face.vertices) for face in obj.data.loop_triangles)
    return TerrainSurface(BVHTree.FromPolygons(vertices, triangles, all_triangles=True), vertices, triangles)


def ground_height(surface, x, y):
    hit, _, triangle, _ = surface.tree.ray_cast(Vector((x, y, 1200)), Vector((0, 0, -1)), 1600)
    require(hit is not None, f"Missing regional terrain under {x:.3f},{y:.3f}")
    # A long float32 ray loses submillimetre precision in the returned hit Z.
    # Locate with the BVH, then interpolate the actual triangle in double precision.
    a, b, c = (surface.vertices[index] for index in surface.triangles[triangle])
    bx, by, cx, cy = b.x - a.x, b.y - a.y, c.x - a.x, c.y - a.y
    determinant = bx * cy - cx * by
    require(abs(determinant) > .00000001, "Terrain triangle has no finite XY height")
    u = ((x - a.x) * cy - (y - a.y) * cx) / determinant
    v = (bx * (y - a.y) - by * (x - a.x)) / determinant
    height = a.z + u * (b.z - a.z) + v * (c.z - a.z)
    require(math.isfinite(height), "Terrain triangle produced a nonfinite height")
    return height


def build_trail(field, tree, destination, material):
    vertices, faces, route = [], [], []
    for index, point in enumerate(field.route):
        tangent = field.route[min(index + 1, len(field.route) - 1)] - field.route[max(0, index - 1)]
        side = Vector((-tangent.y, tangent.x, 0)).normalized()
        ground = ground_height(tree, point.x, point.y)
        route.append([point.x, point.y, ground])
        for column in range(5):
            offset = (column / 4 - .5) * field.settings.route_width_m
            p = point + side * offset
            vertices.append((p.x, p.y, ground_height(tree, p.x, p.y)))
    for row in range(len(route) - 1):
        for column in range(4):
            first = row * 5 + column
            faces.append((first, first + 1, first + 6, first + 5))
    guide = mesh_object("Trail.Valley.ArtEstimate", vertices, faces, destination, material, "route_layout_guide")
    guide.hide_render, guide.display_type = True, "WIRE"
    guide["surface_representation"] = "graded_terrain_vertex_color"
    return route


def build_stream(field, tree, destination, material):
    vertices, faces = [], []
    for index in range(501):
        inset = field.settings.stream_boundary_inset_m
        x = -1000 + inset + index * (2000 - 2 * inset) / 500
        y = field.stream_y(x)
        require(ground_height(tree, x, y) < field.settings.stream_level_m - .15, "Estimated stream has no submerged central bed")
        for offset in (-field.settings.stream_mesh_half_width_m, field.settings.stream_mesh_half_width_m):
            vertices.append((x, y + offset, field.settings.stream_level_m))
            require(ground_height(tree, x, y + offset) > field.settings.stream_level_m + .15, "Water mesh ends before meeting its terrain bank")
        if index:
            first = (index - 1) * 2
            faces.append((first, first + 2, first + 3, first + 1))
    obj = mesh_object("Stream.Unnamed.ArtEstimate", vertices, faces, destination, material, "water_surface")
    obj["narrative_basis"] = "landscape_design_only_not_inferred_from_basin_washing"


def tree_templates(source_forest, helpers):
    detailed = bpy.data.collections.new("TreeLibrary.Detailed")
    distant = bpy.data.collections.new("TreeLibrary.Distant")
    for index in range(3):
        prefix = f"Forest.Tree.{index:02}."
        objects = [obj for obj in source_forest.objects if obj.name.startswith(prefix)]
        require(len(objects) == 7, f"Expected one documented tree template: {prefix}")
        trunk = next(obj for obj in objects if obj.name.endswith(".Trunk"))
        anchor = Vector((trunk.location.x - .09, trunk.location.y, 0))
        vertices, faces, material_indices, materials = [], [], [], []
        for obj in objects:
            require(obj.parent is None and not obj.constraints and not obj.modifiers, f"Tree template needs evaluated geometry: {obj.name}")
            offset = len(vertices)
            # Unlinked appended objects have no evaluated matrix_world. These
            # static, unparented source meshes have their full transform in basis.
            vertices.extend(tuple(obj.matrix_basis @ vertex.co - anchor) for vertex in obj.data.vertices)
            for polygon in obj.data.polygons:
                faces.append(tuple(offset + value for value in polygon.vertices))
                material = obj.data.materials[polygon.material_index]
                if material not in materials:
                    materials.append(material)
                material_indices.append(materials.index(material))
        template = mesh_object(f"TreeTemplate.Detailed.{index}", vertices, faces, detailed, None, "tree_template")
        for material in materials:
            template.data.materials.append(material)
        for polygon, material_index in zip(template.data.polygons, material_indices, strict=True):
            polygon.material_index, polygon.use_smooth = material_index, True
        low = Vector(tuple(min(point[axis] for point in vertices) for axis in range(3)))
        high = Vector(tuple(max(point[axis] for point in vertices) for axis in range(3)))
        require(-.3 < low.z < .2 and 4 < high.z - low.z < 12, f"Tree template lost its ground anchor: {prefix}")
        require(abs((low.x + high.x) / 2) < 2.5 and abs((low.y + high.y) / 2) < 2.5, f"Tree template crown is displaced: {prefix}")
        # Low-detail distant crowns are separate real meshes, not image cards.
        verts, polys, indices = [], [], []
        tree_height = 6.2 + index * .5
        for ring in (0, 1):
            for segment in range(8):
                angle = segment * math.tau / 8
                verts.append((math.cos(angle) * (.16 if ring == 0 else .10), math.sin(angle) * (.16 if ring == 0 else .10), -.04 if ring == 0 else tree_height * .7))
        for segment in range(8):
            polys.append((segment, (segment + 1) % 8, (segment + 1) % 8 + 8, segment + 8))
            indices.append(0)
        for cx, cy, cz, rx, ry, rz in ((-.6, .1, tree_height * .72, 1.3, 1.2, 1.8), (.6, -.1, tree_height * .8, 1.5, 1.1, 1.6), (0, .4, tree_height * .94, 1.1, 1.1, 1.5)):
            start = len(verts)
            for ring in range(7):
                theta = math.pi * (ring + .05) / 6.1
                for segment in range(10):
                    phi = segment * math.tau / 10
                    verts.append((cx + rx * math.sin(theta) * math.cos(phi), cy + ry * math.sin(theta) * math.sin(phi), cz + rz * math.cos(theta)))
            for ring in range(6):
                for segment in range(10):
                    first = start + ring * 10 + segment
                    polys.append((first, start + ring * 10 + (segment + 1) % 10, start + (ring + 1) * 10 + (segment + 1) % 10, first + 10))
                    indices.append(1)
        far = mesh_object(f"TreeTemplate.Distant.{index}", verts, polys, distant, None, "tree_template")
        far.data.materials.append(bpy.data.materials["ForestBark"])
        leaf = helpers["surface"](f"DistantLeaves.{index}.ArtEstimate", ((.035, .075, .025), (.045, .09, .035), (.06, .105, .035))[index], .90)
        far.data.materials.append(leaf)
        for polygon, material_index in zip(far.data.polygons, indices, strict=True):
            polygon.material_index, polygon.use_smooth = material_index, True
    return detailed, distant


def leaf_components(mesh, expected_count=750):
    """Read the source's disconnected five-vertex, four-triangle leaves."""
    require([material.name for material in mesh.materials] == ["ForestBark", "ForestFoliage"], "Unexpected source tree material slots")
    leaves = [polygon for polygon in mesh.polygons if polygon.material_index == 1]
    adjacency = {}
    for polygon in leaves:
        require(len(polygon.vertices) == 3, "Source foliage contains a non-triangle face")
        for index in polygon.vertices:
            adjacency.setdefault(index, set()).update(polygon.vertices)
    remaining, groups = set(adjacency), []
    while remaining:
        queue, component = [min(remaining)], set()
        while queue:
            index = queue.pop()
            if index not in component:
                component.add(index)
                queue.extend(adjacency[index] - component)
        remaining.difference_update(component)
        groups.append(tuple(sorted(component)))
    require(len(groups) == expected_count and all(len(group) == 5 for group in groups), f"Expected exactly {expected_count} independent leaves")
    by_vertex = {index: group for group in groups for index in group}
    faces = {group: [] for group in groups}
    for polygon in leaves:
        group = by_vertex[polygon.vertices[0]]
        faces[group].append(tuple(polygon.vertices))
    require(all(len(value) == 4 for value in faces.values()), "Source leaf face structure changed")
    require(all(not any(index in by_vertex for index in polygon.vertices) for polygon in mesh.polygons if polygon.material_index == 0), "Bark and leaf vertices are unexpectedly shared")
    return [(group, faces[group]) for group in groups]


def denser_canopy_mesh(source, variant):
    components = leaf_components(source)
    vertices = [tuple(vertex.co) for vertex in source.vertices]
    faces = [tuple(polygon.vertices) for polygon in source.polygons]
    material_indices = [polygon.material_index for polygon in source.polygons]
    foliage = [Vector(vertices[index]) for group, _ in components for index in group]
    low = Vector(tuple(min(point[axis] for point in foliage) for axis in range(3)))
    high = Vector(tuple(max(point[axis] for point in foliage) for axis in range(3)))
    for leaf_index, (group, leaf_faces) in enumerate(components):
        center = sum((Vector(vertices[index]) for index in group), Vector()) / len(group)
        for copy_index in range(1, 4):
            phase = math.tau * (leaf_index * .61803398875 + copy_index * .754877666 + variant * .13)
            rotation = Euler((.35 * math.sin(phase), .30 * math.cos(phase), phase)).to_matrix()
            offset = Vector((.13 * math.cos(phase), .13 * math.sin(phase), .11 * math.sin(phase * 1.7)))
            points = [center + rotation @ (Vector(vertices[index]) - center) for index in group]
            # Keep every new leaf within the source canopy's total extents.
            for axis in range(3):
                lower = low[axis] - min(point[axis] for point in points)
                upper = high[axis] - max(point[axis] for point in points)
                require(lower <= upper, "A copied leaf cannot fit the source canopy")
                offset[axis] = min(upper, max(lower, offset[axis]))
            remap = {old: len(vertices) + index for index, old in enumerate(group)}
            vertices.extend(tuple(point + offset) for point in points)
            faces.extend(tuple(remap[index] for index in face) for face in leaf_faces)
            material_indices.extend([1] * len(leaf_faces))
    mesh = bpy.data.meshes.new(f"TreeCanopy.Shared.{variant}")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    for material in source.materials:
        mesh.materials.append(material)
    for polygon, material_index in zip(mesh.polygons, material_indices, strict=True):
        polygon.material_index, polygon.use_smooth = material_index, True
    require(all(math.isfinite(value) for vertex in mesh.vertices for value in vertex.co), "Nonfinite canopy vertex")
    require(all(polygon.area > .0000000001 for polygon in mesh.polygons), "Canopy contains a zero-area face")
    require(all(low[axis] - .000001 <= vertex.co[axis] <= high[axis] + .000001 for vertex in mesh.vertices[len(source.vertices):] for axis in range(3)), "New leaves expanded the source canopy bounds")
    for old, new in zip(source.vertices, mesh.vertices, strict=False):
        require(old.co == new.co, "Canopy refinement changed an original vertex")
    for old, new in zip(source.polygons, mesh.polygons, strict=False):
        require(tuple(old.vertices) == tuple(new.vertices) and old.material_index == new.material_index, "Canopy refinement changed an original face")
    return mesh


def data_values(items, field, count, typecode):
    values = array(typecode, [0]) * (len(items) * count)
    items.foreach_get(field, values)
    return values


def protected_mesh_state(mesh):
    formats = {"FLOAT": ("value", 1, "f"), "FLOAT2": ("vector", 2, "f"), "FLOAT_VECTOR": ("vector", 3, "f"), "FLOAT_COLOR": ("color", 4, "f"), "INT": ("value", 1, "i"), "INT32_2D": ("value", 2, "i"), "BOOLEAN": ("value", 1, "b")}
    attributes = []
    for attribute in sorted(mesh.attributes, key=lambda value: value.name):
        require(attribute.data_type in formats, f"Unsupported protected mesh attribute: {attribute.data_type}")
        field, count, typecode = formats[attribute.data_type]
        attributes.append((attribute.name, attribute.data_type, attribute.domain, data_values(attribute.data, field, count, typecode)))
    return (data_values(mesh.vertices, "co", 3, "f"), data_values(mesh.edges, "vertices", 2, "i"), data_values(mesh.loops, "vertex_index", 1, "i"), data_values(mesh.polygons, "loop_start", 1, "i"), data_values(mesh.polygons, "loop_total", 1, "i"), data_values(mesh.polygons, "material_index", 1, "i"), tuple(attributes), tuple(layer.name for layer in mesh.uv_layers))


def matrix_values(matrix):
    return tuple(value for row in matrix for value in row)


def protected_object_state(obj, matrix):
    require(obj.parent is None and not obj.constraints, f"Protected region object has an unsupported parent or constraint: {obj.name}")
    common = (obj.type, matrix_values(matrix), obj.hide_render, obj.hide_viewport)
    if obj.type == "MESH":
        return common + (protected_mesh_state(obj.data),)
    if obj.type == "CAMERA":
        data = obj.data
        return common + (data.type, data.lens, data.sensor_width, data.sensor_height, data.sensor_fit, data.ortho_scale, data.clip_start, data.clip_end, data.shift_x, data.shift_y)
    if obj.type == "LIGHT":
        data = obj.data
        light = common + (data.type, data.energy, tuple(data.color))
        if data.type == "SUN":
            return light + (data.angle,)
        require(data.type == "AREA", f"Unsupported protected region light type: {data.type}")
        return light + (data.shape, data.size, data.size_y)
    require(obj.type == "EMPTY", f"Unsupported protected region object type: {obj.type}")
    return common


def instance_state(parents, aliases):
    result = []
    for instance in bpy.context.evaluated_depsgraph_get().object_instances:
        if instance.is_instance and instance.parent is not None and instance.parent.original in parents:
            require(instance.object.original in aliases, "Instance template has no source identity")
            result.append((aliases[instance.parent.original], aliases[instance.object.original], matrix_values(instance.matrix_world)))
    require(len(result) == 2400, "Protected source must have exactly 2400 actual tree instances")
    return sorted(result)


def protected_scene_state():
    scene = bpy.context.scene
    objects = {obj.name: protected_object_state(obj, obj.matrix_world) for obj in scene.objects}
    aliases = {obj: obj.name for obj in bpy.data.objects if obj.name in TREE_TEMPLATES + SCATTER_OBJECTS}
    parents = {bpy.data.objects[name] for name in SCATTER_OBJECTS}
    return objects, instance_state(parents, aliases), {name: matrix_values(bpy.data.objects[name].matrix_world) for name in TREE_TEMPLATES}


def compare_canopy_source(source_path: Path):
    """Compare the saved source's actual data, without saving imported IDs."""
    require(Path(bpy.data.filepath).resolve() != source_path, "Saved-source comparison requires reopening the new candidate")
    current = protected_scene_state()
    candidates = {name: bpy.data.objects[name] for name in TREE_TEMPLATES}
    before_ids = set(bpy.data.user_map())
    before_file = file_state(source_path)
    try:
        # Collection Info orders separate children by object name. Numeric-suffix
        # collision renaming during append would reorder the source's variants.
        for index, obj in enumerate(candidates.values()):
            temporary_name = f"CanopyComparisonTemplate_{index}"
            require(temporary_name not in bpy.data.objects, "Temporary canopy comparison name is occupied")
            obj.name = temporary_name
        with bpy.data.libraries.load(str(source_path), link=False) as (available, selected):
            names = tuple(available.objects)
            require(set(current[0]).union(TREE_TEMPLATES).issubset(names) and source_path.stem in available.scenes, "Protected source object or scene inventory differs")
            selected.objects = list(names)
            selected.scenes = [source_path.stem]
        loaded = dict(zip(names, selected.objects, strict=True))
        require(all(loaded[name].name == name for name in TREE_TEMPLATES), "Source canopy names changed during append")
        source_scene = selected.scenes[0]
        aliases = {obj: name for name, obj in loaded.items()}
        require({aliases[obj] for obj in source_scene.objects} == set(current[0]), "Protected source scene membership changed")
        with bpy.context.temp_override(scene=source_scene, view_layer=source_scene.view_layers[0]):
            bpy.context.view_layer.update()
            for name in current[0]:
                require(current[0][name] == protected_object_state(loaded[name], loaded[name].matrix_world), f"Protected source object changed: {name}")
            source_instances = instance_state({loaded[name] for name in SCATTER_OBJECTS}, aliases)
        require(current[1] == source_instances, "Actual tree instance matrices differ from the saved source")
        for name in TREE_TEMPLATES:
            require(current[2][name] == matrix_values(loaded[name].matrix_basis), f"Tree template object transform changed: {name}")
        for variant in range(3):
            old = loaded[f"TreeTemplate.Detailed.{variant}"].data
            new = candidates[f"TreeTemplate.Detailed.{variant}"].data
            require(len(new.vertices) >= len(old.vertices) and len(new.polygons) >= len(old.polygons), "Canopy lost source geometry")
            require(all(a.co == b.co for a, b in zip(old.vertices, new.vertices)), "Original canopy vertices changed")
            require(all(tuple(a.vertices) == tuple(b.vertices) and a.material_index == b.material_index for a, b in zip(old.polygons, new.polygons)), "Original canopy faces changed")
            leaf_indices = {index for polygon in old.polygons if polygon.material_index == 1 for index in polygon.vertices}
            low = tuple(min(old.vertices[index].co[axis] for index in leaf_indices) for axis in range(3))
            high = tuple(max(old.vertices[index].co[axis] for index in leaf_indices) for axis in range(3))
            require(all(low[axis] - .000001 <= vertex.co[axis] <= high[axis] + .000001 for vertex in new.vertices[len(old.vertices):] for axis in range(3)), "New foliage expands outside the original canopy bounds")
    finally:
        bpy.data.batch_remove(ids=set(bpy.data.user_map()) - before_ids)
        for name, obj in candidates.items():
            obj.name = name
        bpy.context.view_layer.update()
        require(protected_scene_state() == current, "Saved-source comparison failed to restore the candidate's in-memory state")
    require(file_state(source_path) == before_file, "Source comparison modified the input file")
    return {"protected_objects": len(current[0]), "protected_meshes": sum(obj.type == "MESH" for obj in bpy.context.scene.objects), "unchanged_actual_instance_matrices": 2400, "original_detailed_vertices_and_faces_preserved": True, "new_leaves_within_original_canopy_bounds": True, "source_file_unchanged": True}


def inspect_refined_canopies():
    meshes = set()
    for variant in range(3):
        near = bpy.data.objects[f"TreeTemplate.Detailed.{variant}"]
        far = bpy.data.objects[f"TreeTemplate.Distant.{variant}"]
        require(near.data == far.data, "Near and distant spatial groups no longer share the same canopy mesh")
        require(len(near.data.vertices) == 15096 and len(near.data.polygons) == 12056, "Refined canopy geometry inventory changed")
        leaf_components(near.data, expected_count=3000)
        require(all(polygon.area > .0000000001 for polygon in near.data.polygons), "Refined canopy contains a zero-area face")
        meshes.add(near.data)
    require(len(meshes) == 3, "Expected three independent shared canopy variants")
    return {"template_objects": 6, "shared_meshes": 3, "leaves_per_mesh": 3000}


def scatter_object(name, records, library, destination):
    obj = mesh_object(name, [record["position"] for record in records], [], destination, None, "vegetation_scatter_points")
    for attribute_name, data_type in (("tree_scale", "FLOAT_VECTOR"), ("tree_rotation", "FLOAT_VECTOR"), ("tree_variant", "INT")):
        attribute = obj.data.attributes.new(name=attribute_name, type=data_type, domain="POINT")
        for item, record in zip(attribute.data, records, strict=True):
            if data_type == "INT":
                item.value = record["variant"]
            else:
                item.vector = (record["scale"],) * 3 if attribute_name == "tree_scale" else (0, 0, record["rotation"])
    nodes_group = bpy.data.node_groups.new(name + ".Instances", "GeometryNodeTree")
    nodes_group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    nodes_group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nodes, links = nodes_group.nodes, nodes_group.links
    source, output = nodes.new("NodeGroupInput"), nodes.new("NodeGroupOutput")
    info = nodes.new("GeometryNodeCollectionInfo")
    info.inputs["Collection"].default_value = library
    info.inputs["Separate Children"].default_value = True
    info.inputs["Reset Children"].default_value = True
    instances = nodes.new("GeometryNodeInstanceOnPoints")
    instances.inputs["Pick Instance"].default_value = True
    links.new(source.outputs["Geometry"], instances.inputs["Points"])
    links.new(info.outputs["Instances"], instances.inputs["Instance"])
    for attribute_name, data_type, socket in (("tree_scale", "FLOAT_VECTOR", "Scale"), ("tree_rotation", "FLOAT_VECTOR", "Rotation"), ("tree_variant", "INT", "Instance Index")):
        attribute = nodes.new("GeometryNodeInputNamedAttribute")
        attribute.data_type = data_type
        attribute.inputs["Name"].default_value = attribute_name
        if socket == "Rotation":
            rotation = nodes.new("FunctionNodeEulerToRotation")
            links.new(attribute.outputs["Attribute"], rotation.inputs["Euler"])
            links.new(rotation.outputs["Rotation"], instances.inputs[socket])
        else:
            links.new(attribute.outputs["Attribute"], instances.inputs[socket])
    links.new(instances.outputs["Instances"], output.inputs["Geometry"])
    modifier = obj.modifiers.new("SharedTreeInstances", "NODES")
    modifier.node_group = nodes_group
    return obj


def populate_forest(field, tree, libraries, destination):
    randomizer = random.Random(field.settings.seed)
    near, far = [], []
    cells = {}
    for attempt in range(30000):
        if len(near) + len(far) >= field.settings.maximum_tree_instances:
            break
        if attempt % 3:
            x, y = randomizer.uniform(-330, 330), randomizer.uniform(-380, 300)
        else:
            x, y = randomizer.uniform(-940, 940), randomizer.uniform(-940, 940)
        radius = math.hypot(x, y)
        distance, _ = field.route_distance(x, y)
        if radius < 13 or distance < 4.8 or abs(y - field.stream_y(x)) < 12:
            continue
        # Reserve a sight corridor from the two close inspection cameras.
        if -23 < y < 8 and -1.2 < x < 13:
            continue
        z = ground_height(tree, x, y)
        if z > 280 or randomizer.random() > (.9 if radius < 350 else .7):
            continue
        slope = max(abs(ground_height(tree, x + 1, y) - z), abs(ground_height(tree, x, y + 1) - z))
        if slope > .70:
            continue
        spacing = 5.5 if radius < 150 else 8.0
        cell = (math.floor(x / 8), math.floor(y / 8))
        neighbors = (position for dx in (-1, 0, 1) for dy in (-1, 0, 1) for position in cells.get((cell[0] + dx, cell[1] + dy), ()))
        if any(math.hypot(x - px, y - py) < spacing for px, py in neighbors):
            continue
        cells.setdefault(cell, []).append((x, y))
        scale = randomizer.uniform(.9, 1.55) if radius < 80 else randomizer.uniform(1.35, 2.6)
        record = {"position": [x, y, z - .06 * scale], "scale": scale, "rotation": randomizer.uniform(0, math.tau), "variant": (len(near) + len(far)) % 3, "ground_m": z, "trail_clearance_m": distance}
        (near if radius < field.settings.detailed_tree_radius_m else far).append(record)
    require(len(near) > 10 and len(far) > 1000, "Forest population did not form the intended near and distant layers")
    scatter_object("Forest.NearInstances.ArtEstimate", near, libraries[0], destination)
    scatter_object("Forest.DistantInstances.ArtEstimate", far, libraries[1], destination)
    return {"near": near, "distant": far}


def detail_ground(field, tree, destination, helpers):
    randomizer = random.Random(field.settings.seed + 10)
    rock = helpers["surface"]("RegionStone.ArtEstimate", (.19, .21, .18), .88, texture=True)
    grass = helpers["surface"]("GroundGrass.ArtEstimate", (.13, .19, .07), .95)
    vertices, faces = [], []
    for index in range(700):
        x, y = randomizer.uniform(-42, 42), randomizer.uniform(-44, 40)
        distance, _ = field.route_distance(x, y)
        if math.hypot(x, y - 1.5) < 7 or distance < 2.4:
            continue
        z = ground_height(tree, x, y)
        for blade in range(9):
            angle = randomizer.uniform(0, math.tau)
            point = Vector((x + randomizer.uniform(-.25, .25), y + randomizer.uniform(-.25, .25), z - .025))
            width, height = randomizer.uniform(.014, .028), randomizer.uniform(.12, .33)
            side = Vector((math.cos(angle) * width, math.sin(angle) * width, 0))
            start = len(vertices)
            vertices.extend((tuple(point - side), tuple(point + side), tuple(point + Vector((side.x * 3, side.y * 3, height)))))
            faces.append((start, start + 1, start + 2))
        if index < 65:
            size = randomizer.uniform(.30, 1.1)
            obj = helpers["soft_shape"](f"Outcrop.ArtEstimate.{index:03}", (x, y, z + size * .16), (size, size * .7, size * .48), destination, rock, True)
            obj["artEstimate"] = True
    mesh_object("Clearing.Grass.ArtEstimate", vertices, faces, destination, grass, "ground_vegetation")


def presentation(settings, tree, lighting, cameras, helpers):
    scene = bpy.context.scene
    scene.world = bpy.data.worlds.new("Cangyun.OvercastStudy")
    world_nodes = scene.world.node_tree.nodes
    background = world_nodes["Background"]
    sky = world_nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_elevation, sky.sun_rotation = .55, 2.5
    sky.sun_disc = False
    background.inputs["Strength"].default_value = .35
    scene.world.node_tree.links.new(sky.outputs["Color"], background.inputs["Color"])
    sunlight = bpy.data.lights.new("Region.SoftSun.ArtEstimate", "SUN")
    sunlight.energy, sunlight.angle = 2.0, .20
    sun = bpy.data.objects.new(sunlight.name, sunlight)
    lighting.objects.link(sun)
    sun.rotation_euler = (.55, -.45, -.7)
    helpers["area"]("Hut.InteriorFill.ArtEstimate", (0, 2.4, 2.3), (0, 2.1, .4), 16, (1.0, .75, .46), 1.7, lighting)
    fog = bpy.data.materials.new("Region.DistanceHaze.ArtEstimate")
    fog.node_tree.nodes.remove(fog.node_tree.nodes["Principled BSDF"])
    volume = fog.node_tree.nodes.new("ShaderNodeVolumeScatter")
    volume.inputs["Color"].default_value = (.58, .69, .72, 1)
    volume.inputs["Density"].default_value = settings.haze_density_per_m
    volume.inputs["Anisotropy"].default_value = .25
    fog.node_tree.links.new(volume.outputs["Volume"], fog.node_tree.nodes["Material Output"].inputs["Volume"])
    helpers["box"]("Region.HazeVolume.ArtEstimate", (0, 0, 660), (4000, 4000, 1520), lighting, fog, bevel=0)
    views = {
        "overview": helpers["camera"]("RegionOverview", (720, -1040, 800), (0, -160, 65), 40, cameras),
        "hut_ground": helpers["camera"]("HutGroundContext", (9.8, -14.0, ground_height(tree, 9.8, -14) + 2.1), (0, 1.9, 1.7), 37, cameras),
        "forest_return": helpers["camera"]("ForestReturn", (-11.0, -31.0, ground_height(tree, -11, -31) + 1.75), (0, 1.6, 2.1), 48, cameras),
    }
    for camera in views.values():
        camera.data.clip_end = 5000
    scene.camera = views["overview"]
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples, scene.cycles.use_denoising = settings.render_samples, True
    scene.cycles.max_bounces = 6
    scene.render.resolution_x, scene.render.resolution_y = 1800, 1200
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.threads_mode, scene.render.threads = "FIXED", 6
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = .2
    return views


def validate_manifest(output, manifest):
    require(isinstance(manifest, dict), "Region manifest must be an object")
    require(manifest.get("name") == output.name and manifest.get("status") == "regional_world_modeling_study", "Region manifest identity does not match the candidate")
    require(manifest.get("render_resolution") == [1800, 1200], "Region render resolution differs from the study contract")
    views = manifest.get("render_views")
    require(isinstance(views, dict) and set(views) == set(REGION_VIEWS), "Region manifest must declare all three fixed views")
    for key, (camera, filename) in REGION_VIEWS.items():
        view = views[key]
        require(isinstance(view, dict) and view.get("camera") == camera and view.get("file") == filename, f"Unexpected region camera or output basename: {key}")


def inspect_region(manifest):
    scene = bpy.context.scene
    require(scene.unit_settings.system == "METRIC" and scene.unit_settings.scale_length == 1, "Region units changed")
    tiles = sorted((obj for obj in scene.objects if obj.get("asset_role") == "terrain_tile"), key=lambda obj: (obj["tile_row"], obj["tile_column"]))
    require(len(tiles) == 16 and sum(len(obj.data.vertices) for obj in tiles) == 266256, "Terrain tile inventory changed")
    for obj in scene.objects:
        require(all(math.isfinite(value) for row in obj.matrix_world for value in row) and abs(obj.matrix_world.to_3x3().determinant()) > .00000001, f"Nonfinite or singular object transform: {obj.name}")
    seam_checks = 0
    for row in range(4):
        for column in range(4):
            current = tiles[row * 4 + column]
            if column < 3:
                right = tiles[row * 4 + column + 1]
                for index in range(129):
                    require((current.matrix_world @ current.data.vertices[index * 129 + 128].co - right.matrix_world @ right.data.vertices[index * 129].co).length < .000001, "Terrain has an X tile seam")
                    seam_checks += 1
            if row < 3:
                upper = tiles[(row + 1) * 4 + column]
                for index in range(129):
                    require((current.matrix_world @ current.data.vertices[128 * 129 + index].co - upper.matrix_world @ upper.data.vertices[index].co).length < .000001, "Terrain has a Y tile seam")
                    seam_checks += 1
    for obj in scene.objects:
        if obj.type == "MESH":
            require(len(obj.data.vertices) > 0, f"Empty region mesh: {obj.name}")
            if obj.get("asset_role") != "vegetation_scatter_points":
                require(len(obj.data.polygons) > 0, f"Region mesh has no faces: {obj.name}")
            values = array("f", [0]) * (len(obj.data.vertices) * 3)
            obj.data.vertices.foreach_get("co", values)
            require(all(math.isfinite(value) for value in values), f"Nonfinite region mesh: {obj.name}")
    tree = terrain_tree(tiles)
    for x, y in ((0, 0), (-1.9, .1), (1.9, 4.7), (0, -1), (1.82, -1.19), (0, -6.1)):
        require(abs(ground_height(tree, x, y)) < .0001, "Regional terrain does not meet the hut's original ground datum")
    world_bounds = runpy.run_path(str(HUT_SCRIPT))["world_bounds"]
    foundation = [obj for obj in scene.objects if obj.name.startswith("Foundation.Stone")]
    require(len(foundation) == 6, "Original hut foundation inventory changed")
    for stone in foundation:
        low, high = world_bounds(stone)
        terrain_z = ground_height(tree, (low[0] + high[0]) / 2, (low[1] + high[1]) / 2)
        require(abs(low[2] - terrain_z) < .0001, f"Hut foundation is detached from terrain: {stone.name}")
    corridors = {"retreat": {"x": [-.55, .55], "y": [-.90, 3.95], "z": [.33, 2.0]}, "forest_approach": {"x": [-1.2, 1.2], "y": [-6.5, -1.35], "z": [.05, 1.4]}}
    for label, bounds in corridors.items():
        for obj in scene.objects:
            if obj.type == "MESH" and obj.get("walk_obstacle", False):
                low, high = world_bounds(obj)
                require(not all(high[index] > bounds[axis][0] and low[index] < bounds[axis][1] for index, axis in enumerate(("x", "y", "z"))), f"Original {label} corridor obstructed: {obj.name}")
    water = scene.objects["Stream.Unnamed.ArtEstimate"]
    require(len(water.data.vertices) == 1002, "Stream geometry inventory changed")
    bank_clearances, bed_depths = [], []
    for index in range(501):
        left, right = (water.matrix_world @ water.data.vertices[index * 2 + side].co for side in (0, 1))
        for point in (left, right):
            clearance = ground_height(tree, point.x, point.y) - point.z
            require(clearance > .15, "Water mesh ends above an exposed riverbed")
            bank_clearances.append(clearance)
        middle = (left + right) / 2
        depth = middle.z - ground_height(tree, middle.x, middle.y)
        require(depth > .15, "Water has no submerged central bed")
        bed_depths.append(depth)
    protection = bpy.data.collections["07.OptionalProtectionStudy"]
    require(protection.hide_render and protection.hide_viewport, "Initial hut protection became visible")
    require("Terrain.EarthSurface" not in bpy.data.objects, "Old ground overlaps the regional surface")
    path = scene.objects["Trail.Valley.ArtEstimate"]
    require(path.hide_render and path.display_type == "WIRE" and path["surface_representation"] == "graded_terrain_vertex_color", "Trail guide must not create a second rendered ground surface")
    expected_route = manifest["route_centerline_m"]
    require(len(path.data.vertices) == len(expected_route) * 5, "Trail surface inventory changed")
    route = []
    for index, expected in enumerate(expected_route):
        actual = path.matrix_world @ path.data.vertices[index * 5 + 2].co
        require((actual - Vector(expected)).length < .0001, "Trail surface moved from its recorded centerline")
        require(abs(actual.z - ground_height(tree, actual.x, actual.y)) < .0001, "Trail floats above or intersects terrain")
        route.append(actual)
    grades = [abs(b.z - a.z) / math.hypot(b.x - a.x, b.y - a.y) for a, b in zip(route, route[1:])]
    require(max(grades) < .30, f"Regional trail slope is too steep: {max(grades)}")
    records = [record for layer in manifest["vegetation"].values() for record in layer]
    require(manifest["settings"]["maximum_tree_instances"] == 2400 and 1000 < len(records) <= 2400, "Vegetation instance budget changed")
    field = TerrainField(RegionSettings(**manifest["settings"]))
    clearances = []
    for layer, name in (("near", "Forest.NearInstances.ArtEstimate"), ("distant", "Forest.DistantInstances.ArtEstimate")):
        scatter = scene.objects[name]
        layer_records = manifest["vegetation"][layer]
        require(len(scatter.data.vertices) == len(layer_records), "Scatter point inventory changed")
        for vertex, record, scale, rotation, variant in zip(scatter.data.vertices, layer_records, scatter.data.attributes["tree_scale"].data, scatter.data.attributes["tree_rotation"].data, scatter.data.attributes["tree_variant"].data, strict=True):
            point = scatter.matrix_world @ vertex.co
            require((point - Vector(record["position"])).length < .0001, "Tree scatter point differs from its recorded position")
            require((scale.vector - Vector((record["scale"],) * 3)).length < .000001 and (rotation.vector - Vector((0, 0, record["rotation"]))).length < .000001 and variant.value == record["variant"], "Tree instance transform attributes changed")
            require(abs(point.z + .06 * record["scale"] - ground_height(tree, point.x, point.y)) < .0002, "Tree root is detached from its terrain anchor")
            distance, _ = field.route_distance(point.x, point.y)
            require(distance >= 4.8, "Tree roots enter the regional trail")
            clearances.append(distance)
    graph = bpy.context.evaluated_depsgraph_get()
    layers = {}
    for layer, parent, detail in (("near", "Forest.NearInstances.ArtEstimate", "Detailed"), ("distant", "Forest.DistantInstances.ArtEstimate", "Distant")):
        points = KDTree(len(manifest["vegetation"][layer]))
        for index, record in enumerate(manifest["vegetation"][layer]):
            points.insert(Vector(record["position"]), index)
        points.balance()
        layers[parent] = (layer, detail, points)
    seen, checked_templates, checked_meshes = set(), set(), set()
    actual_instances = 0
    for instance in graph.object_instances:
        if not instance.is_instance or not instance.object.original.name.startswith("TreeTemplate."):
            continue
        require(instance.parent is not None and instance.parent.original.name in layers, "Tree instance has an unexpected parent")
        layer, detail, points = layers[instance.parent.original.name]
        _, index, distance = points.find(instance.matrix_world.translation)
        identity = (layer, index)
        require(distance < .0001 and identity not in seen, "Tree instance is misplaced or duplicated")
        seen.add(identity)
        record = manifest["vegetation"][layer][index]
        expected = Matrix.LocRotScale(Vector(record["position"]), Euler((0, 0, record["rotation"])).to_quaternion(), Vector((record["scale"],) * 3))
        require(max(abs(instance.matrix_world[row][column] - expected[row][column]) for row in range(4) for column in range(4)) < .0001, "Evaluated tree instance does not apply its recorded transform")
        template = instance.object.original
        require(template.name == f"TreeTemplate.{detail}.{record['variant']}", "Evaluated tree instance uses the wrong template")
        if template.name not in checked_templates:
            require(template.type == "MESH" and template.data.vertices and template.data.polygons, "Tree template has no actual mesh")
            checked_templates.add(template.name)
        if template.data not in checked_meshes:
            require(all(math.isfinite(value) for vertex in template.data.vertices for value in vertex.co), "Tree template mesh is nonfinite")
            checked_meshes.add(template.data)
        actual_instances += 1
    require(actual_instances == len(records), f"Tree geometry instance count differs: actual={actual_instances}, expected={len(records)}")
    for z in (.48, 1.25, 2.25):
        hit, _, _, _, obj, _ = scene.ray_cast(graph, Vector((0, -.2, z)), Vector((0, 1, 0)), distance=.4)
        require(not hit, f"Imported door opening is blocked: {obj.name if obj else 'unknown'}")
    for key in ("WashingInteraction", "DoorRetreat", "IndoorSafetyPoint", "ForestApproach"):
        require(key in scene.objects and scene.objects[key].type == "EMPTY", f"Missing original interaction marker: {key}")
    require(not bpy.data.libraries, "Region depends on linked Blender libraries")
    require(not any(image.source == "FILE" and image.packed_file is None for image in bpy.data.images), "Region has an unpacked image dependency")
    require(file_state(HUT_SOURCE) == manifest["hut_source_file_state"], "Original hut file changed")
    return {"status": "passed", "scope": "region_geometry_layout_and_resources", "terrain_tiles": len(tiles), "terrain_vertices": 266256, "matching_tile_edge_vertices": seam_checks, "hut_foundation_contact_checks": len(foundation), "original_static_corridors_clear": list(corridors), "door_opening_rays": 3, "route_surface_samples": len(route), "route_length_m": sum((b - a).length for a, b in zip(route, route[1:])), "maximum_route_grade": max(grades), "vegetation_instances": actual_instances, "evaluated_instance_transform_checks": len(seen), "tree_template_object_checks": len(checked_templates), "unique_tree_template_mesh_checks": len(checked_meshes), "tree_ground_and_transform_checks": len(records), "minimum_tree_trail_centerline_distance_m": min(clearances), "submerged_water_edge_checks": len(bank_clearances), "minimum_water_edge_burial_m": min(bank_clearances), "stream_center_depth_checks": len(bed_depths), "minimum_stream_depth_m": min(bed_depths), "source_hut_file_unchanged": True, "runtime_navigation_verified": False, "complete_world_map": False}


def save_candidate(output, manifest, checks):
    require(not output.exists(), "Refusing to replace a region candidate")
    output.mkdir(parents=True)
    with (output / "scene_manifest.json").open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    with (output / "build_checks.json").open("x", encoding="utf-8") as handle:
        json.dump(checks, handle, ensure_ascii=False, indent=2)
    bpy.context.scene.render.filepath = ""
    bpy.ops.wm.save_as_mainfile(filepath=str(output / (output.name + ".blend")))


def region_source_path(value):
    path = Path(value).resolve(strict=True)
    require(path.is_file() and path.parent.parent == ROOT / "Candidates" and path.name == path.parent.name + ".blend", "Source must be an existing regional candidate blend")
    return path


def refine_canopy(output, source_value):
    source_path = region_source_path(source_value)
    require(Path(bpy.data.filepath).resolve() == source_path, "Canopy refinement must open its declared source in a separate background process")
    require(not output.exists(), "Refusing to replace a region candidate")
    source_file = file_state(source_path)
    original = json.loads((source_path.parent / "scene_manifest.json").read_text(encoding="utf-8"))
    validate_manifest(source_path.parent, original)
    require("canopy_refinement" not in original, "Canopy refinement requires the original sparse-leaf baseline")
    inspect_region(original)
    protected = protected_scene_state()
    template_records = []
    for variant in range(3):
        near = bpy.data.objects[f"TreeTemplate.Detailed.{variant}"]
        far = bpy.data.objects[f"TreeTemplate.Distant.{variant}"]
        mesh = denser_canopy_mesh(near.data, variant)
        near.data = far.data = mesh
        template_records.append({"variant": variant, "objects": [near.name, far.name], "mesh": mesh.name, "vertices": len(mesh.vertices), "faces": len(mesh.polygons), "source_leaves": 750, "total_leaves": 3000})
    bpy.context.view_layer.update()
    require(protected == protected_scene_state(), "Canopy refinement changed protected regional geometry, presentation or tree transforms")
    manifest = copy.deepcopy(original)
    manifest["name"] = output.name
    manifest["vegetation_detail_policy"] = "same_dense_leaf_geometry_in_both_existing_spatial_groups_no_geometry_LOD"
    manifest["tree_template_scope"] = "six_template_objects_share_three_dense_tree_meshes"
    manifest["canopy_refinement"] = {"source_blend": str(source_path), "source_file_state": source_file, "method": "local_leaf_copies_inside_original_canopy_bounds_shared_across_spatial_groups", "template_meshes": template_records, "protected_scene_verified": True}
    bpy.context.scene.name = output.name
    validate_manifest(output, manifest)
    checks = inspect_region(manifest)
    checks["protected_in_memory_comparison"] = {"objects": len(protected[0]), "unchanged_actual_instance_matrices": len(protected[1]), "source_scene_loaded_before_refinement": True}
    checks["shared_canopies"] = inspect_refined_canopies()
    require(file_state(source_path) == source_file, "Canopy refinement changed the source file")
    save_candidate(output, manifest, checks)
    print("REGION_CANOPY_REFINED", json.dumps(checks), flush=True)


def build(output, settings):
    require(not bpy.data.filepath and "--factory-startup" in sys.argv, "Build in a new independent factory process")
    require(not output.exists(), "Refusing to replace a region candidate")
    require(HUT_SOURCE.is_file() and HUT_SCRIPT.is_file(), "Existing hut source and helpers are required")
    hut_source_state = file_state(HUT_SOURCE)
    helpers = runpy.run_path(str(HUT_SCRIPT))
    for obj in tuple(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene = bpy.context.scene
    scene.name = output.name
    scene.unit_settings.system, scene.unit_settings.scale_length = "METRIC", 1.0
    scene.unit_settings.length_unit = "METERS"
    scene["world"] = "Cangyun"
    scene["study_region"] = "Wanqing Mountain starting-area study"
    scene["artEstimate"] = True
    hut = group("00.WanqingHut")
    terrain = group("10.RegionalTerrain")
    water = group("20.Water.ArtEstimate")
    vegetation = group("30.Vegetation.ArtEstimate")
    detail = group("31.GroundDetail.ArtEstimate")
    routes = group("40.Trail.ArtEstimate")
    lighting = group("60.RegionLighting")
    cameras = group("70.RegionCameras")
    forest_source = append_hut(hut)
    field = TerrainField(settings)
    print("BUILD_TERRAIN", flush=True)
    tiles = build_terrain(field, terrain, terrain_material(helpers))
    bpy.context.view_layer.update()
    tree = terrain_tree(tiles)
    path_material = helpers["surface"]("TrailEarth.ArtEstimate", (.23, .18, .105), .88, texture=True)
    route = build_trail(field, tree, routes, path_material)
    water_material = helpers["surface"]("StreamWater.ArtEstimate", (.045, .12, .105), .15, .1)
    build_stream(field, tree, water, water_material)
    libraries = tree_templates(forest_source, helpers)
    print("BUILD_FOREST", flush=True)
    population = populate_forest(field, tree, libraries, vegetation)
    detail_ground(field, tree, detail, helpers)
    views = presentation(settings, tree, lighting, cameras, helpers)
    bpy.context.view_layer.update()
    manifest = {
        "name": output.name, "status": "regional_world_modeling_study", "world": "Cangyun", "canonical_anchor": "Wanqing Mountain hut",
        "settings": asdict(settings), "main_terrain_extent_m": [-1000, 1000, -1000, 1000], "dimensions_basis": "artEstimate_not_novel_geography", "coordinate_orientation": "local_XY_not_canonical_cardinal_directions",
        "hut_source": str(HUT_SOURCE), "hut_source_file_state": hut_source_state, "hut_collections": list(HUT_COLLECTIONS), "hut_stage": "initial_damaged_hut", "later_encounter_markers_only": True,
        "ground_join": "old_20m_patch_excluded_new_terrain_at_hut_ground_zero", "protection_visible": False,
        "route_centerline_m": route, "route_width_m": settings.route_width_m, "vegetation": population,
        "route_surface_representation": "graded_terrain_vertex_color_with_nonrendering_layout_mesh", "path_tint_falloff_distance_m": [1.3, 4.8],
        "tree_template_scope": "one_tree_per_instance_three_detailed_and_three_distant_variants", "terrain_facts": "all_heights_rocks_trees_path_and_stream_layout_are_artEstimate",
        "vegetation_detail_policy": "individual_leaf_meshes_within_detailed_tree_radius_coarse_crowns_only_beyond",
        "render_views": {key: {"camera": camera.name, "position": list(camera.location), "rotation_euler": list(camera.rotation_euler), "lens_mm": camera.data.lens, "file": f"{key}.png"} for key, camera in views.items()},
        "render_resolution": [1800, 1200], "weather_study": "overcast_day_for_spatial_inspection_not_a_chapter_timestamp",
        "not_included": ["Qingyun Sect geography", "Sword Pavilion geography", "Moon Shadow Sect geography", "Extreme North gate", "Tianjin", "upgraded shelter", "wolves or combat", "runtime navigation, collision, LOD or streaming"],
    }
    validate_manifest(output, manifest)
    checks = inspect_region(manifest)
    save_candidate(output, manifest, checks)
    print("REGION_BUILD_PASSED", json.dumps(checks), flush=True)


def render(output, manifest, view_name=None, metal=False):
    views = manifest["render_views"] if view_name is None else {view_name: manifest["render_views"][view_name]}
    scene = bpy.context.scene
    device_names = ["CPU"]
    if metal:
        preferences = bpy.context.preferences.addons["cycles"].preferences
        preferences.compute_device_type = "METAL"
        devices = preferences.get_devices_for_type("METAL")
        device_names = [device.name for device in devices if device.type == "METAL"]
        require(device_names, "No Cycles Metal device is available")
        for device in devices:
            device.use = device.type == "METAL"
        scene.cycles.device = "GPU"
    else:
        scene.cycles.device = "CPU"
    for view in views.values():
        require(not (output / view["file"]).exists(), "Refusing to render over a prior candidate image")
    print("REGION_RENDER_DEVICE", json.dumps({"backend": "METAL" if metal else "CPU", "devices": device_names, "samples": scene.cycles.samples}), flush=True)
    for key, view in views.items():
        path = output / view["file"]
        require(not path.exists(), f"Refusing to replace a prior render: {path}")
        camera = bpy.data.objects.get(view["camera"])
        require(camera is not None and camera.type == "CAMERA", f"Missing region camera: {key}")
        bpy.context.scene.camera = camera
        bpy.context.scene.render.filepath = str(path)
        started = time.perf_counter()
        status = bpy.ops.render.render(write_still=True)
        require(status == {"FINISHED"} and path.is_file() and path.stat().st_size > 0, f"Region render did not finish: {key}")
        if metal:
            receipt = {"view": key, "image": path.name, "backend": "METAL", "devices": device_names, "samples": scene.cycles.samples, "elapsed_seconds": time.perf_counter() - started, "source_blend_saved": False}
            with (output / f"{key}.render_receipt.json").open("x", encoding="utf-8") as handle:
                json.dump(receipt, handle, indent=2)
        print("REGION_VIEW_RENDERED", key, flush=True)


def verify(output, manifest):
    blend = output / (output.name + ".blend")
    before = file_state(blend)
    report = inspect_region(manifest)
    decoded = []
    for view in manifest["render_views"].values():
        path = output / view["file"]
        require(path.is_file() and path.stat().st_size > 0, f"Missing actual region render: {path}")
        image = bpy.data.images.load(str(path), check_existing=False)
        try:
            require(tuple(image.size) == tuple(manifest["render_resolution"]), f"Unexpected region render dimensions: {path}")
            require(image.has_data and len(image.pixels) == image.size[0] * image.size[1] * 4, f"Region PNG failed to decode: {path}")
            pixels = array("f", [0]) * len(image.pixels)
            image.pixels.foreach_get(pixels)
            require(all(math.isfinite(value) for value in pixels), f"Nonfinite decoded render: {path}")
            require(max(pixels[0::4]) - min(pixels[0::4]) > .02, f"Region render appears empty: {path}")
            decoded.append({"file": path.name, "size": list(image.size), "bytes": path.stat().st_size})
        finally:
            bpy.data.images.remove(image)
    require(file_state(blend) == before, "Verification changed the region blend file")
    report["decoded_renders"] = decoded
    report["reopened_blend"] = str(blend)
    if "canopy_refinement" in manifest:
        refinement = manifest["canopy_refinement"]
        source_path = region_source_path(refinement["source_blend"])
        require(file_state(source_path) == refinement["source_file_state"], "Canopy source file changed since refinement")
        report["shared_canopies"] = inspect_refined_canopies()
        report["canopy_source_comparison"] = compare_canopy_source(source_path)
        require(file_state(blend) == before, "Source comparison changed the candidate blend file")
    with (output / "reopen_checks.json").open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    print("REGION_REOPEN_PASSED", json.dumps(report), flush=True)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("build", "render", "verify", "refine-canopy"), required=True)
    parser.add_argument("--name", default="wanqing-region-study-2026-09-06-04")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--view", choices=tuple(REGION_VIEWS))
    parser.add_argument("--metal", action="store_true")
    args = parser.parse_args(argv)
    require(bpy.app.background, "Region authoring runs only in an independent background process")
    require(args.name.replace("-", "").replace("_", "").isalnum(), "Invalid region candidate name")
    output = ROOT / "Candidates" / args.name
    require(args.mode == "render" or (args.view is None and not args.metal), "--view and --metal apply only to rendering")
    if args.mode == "refine-canopy":
        require(args.source is not None, "Canopy refinement requires --source")
        refine_canopy(output, args.source)
    elif args.mode == "build":
        require(args.source is None, "--source applies only to canopy refinement")
        build(output, RegionSettings())
    else:
        require(args.source is None, "--source applies only to canopy refinement")
        blend = output / (output.name + ".blend")
        require(Path(bpy.data.filepath).resolve() == blend, "Opened file does not match the requested region candidate")
        manifest = json.loads((output / "scene_manifest.json").read_text(encoding="utf-8"))
        validate_manifest(output, manifest)
        if args.mode == "render":
            render(output, manifest, args.view, args.metal)
        else:
            verify(output, manifest)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
