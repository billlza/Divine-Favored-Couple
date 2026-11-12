"""Instanced mountain pines and small ground plants."""

import math
import random

import bpy
from mathutils import Vector

from landscape import mesh_object, require
from build_valley import prism, tree_template
from build_wanqing_region_study import scatter_object


def needle_spray(vertices, faces, colors, tip, direction, scale, rng):
    up = Vector((0, 0, 1))
    cross = direction.cross(up).normalized()
    for _ in range(54):
        along = rng.uniform(-.46, .54) * scale
        side = rng.uniform(-.57, .57) * scale
        center = tip + direction * along + cross * side + up * rng.uniform(-.10, .17) * scale
        stem = center - direction * (.074 * scale)
        needle = (direction * rng.uniform(.14, .29) + cross * rng.uniform(-.20, .20)
                  + up * rng.uniform(-.14, .25)) * scale
        width = cross * rng.uniform(.011, .026) * scale
        idx = len(vertices)
        vertices.extend((tuple(stem - width), tuple(stem + width), tuple(center + needle)))
        faces.append((idx, idx + 1, idx + 2))
        colors.append(rng.choices((1, 2, 3), (5, 8, 3))[0])


def ledge_pine(name, library, materials, seed):
    rng = random.Random(seed)
    vertices, faces, colors = [], [], []
    up = Vector((0, 0, 1))
    height = rng.uniform(8.0, 11.3)
    lean = Vector((rng.uniform(1.05, 2.3), rng.uniform(-.74, .74), 0))
    stations = [i / 11 for i in range(12)]
    trunk = [
        up * (height * t - .17) + lean * t ** 1.5
        + Vector((.38 * math.sin(7 * t), .25 * math.sin(9 * t), 0)) * t
        for t in stations
    ]
    radii = [.35 * (1 - t) ** 1.26 + .011 for t in stations]
    prism(vertices, faces, colors, trunk, radii, 11, 0, seed)
    for root in range(5):
        a = math.tau * root / 5 + rng.uniform(-.24, .24)
        point = Vector((math.cos(a), math.sin(a), 0)) * rng.uniform(.60, 1.48)
        prism(vertices, faces, colors, [trunk[1], .6 * point + .1 * up, point - .23 * up],
              [.19, .105, .019], 7, 0, a)
    for branch in range(13):
        t = .30 + .67 * branch / 13
        index = t * (len(trunk) - 1)
        low = int(index)
        origin = trunk[low].lerp(trunk[low + 1], index - low)
        azimuth = branch * 2.399963 + rng.uniform(-.28, .28)
        direction = Vector((math.cos(azimuth), math.sin(azimuth), 0))
        cross = direction.cross(up)
        reach = rng.uniform(2.1, 3.45) * (1.18 - .57 * t)
        elbow = origin + .47 * reach * direction - .21 * up
        tip = origin + reach * direction + rng.uniform(.30, .69) * up
        prism(vertices, faces, colors, [origin, elbow, tip],
              [.145 * (1 - .58 * t), .070, .008], 8, 0, azimuth)
        for number, fraction in enumerate((.20, .37, .51, .66, .84, 1.0)):
            start = elbow.lerp(tip, fraction)
            sign = -1 if number % 2 else 1
            heading = (direction + sign * .72 * cross).normalized()
            end = start + heading * rng.uniform(.44, .86) + up * rng.uniform(.14, .32)
            prism(vertices, faces, colors, [start, end], [.027, .0038], 5, 0)
            for offset in (.39, .70, 1.0):
                needle_spray(vertices, faces, colors, start.lerp(end, offset), heading,
                             rng.uniform(.66, 1.12), rng)
    tree = mesh_object(name, vertices, faces, library, materials[0], "near_pine")
    for material in materials[1:]:
        tree.data.materials.append(material)
    tree.data.polygons.foreach_set("material_index", colors)
    tree.data.polygons.foreach_set("use_smooth", [color == 0 for color in colors])


def grove(ground, collection, materials, hero, distant, seed):
    rng = random.Random(seed)
    palette = [materials[f"pine{i}"] for i in range(3)]
    near_library = bpy.data.collections.new("Near pine prototypes")
    far_library = bpy.data.collections.new("Distant pine prototypes")
    for i in range(4):
        ledge_pine(f"Near pine {i + 1}", near_library, [materials["bark"], *palette], 522 + i * 39)
        tree_template(f"Distant pine {i + 1}", far_library, materials["bark"], palette, 522 + i * 39, detail=False)

    count = 0
    for name, source, library in (("Near pines", hero, near_library), ("Distant pine stands", distant, far_library)):
        records = []
        for x, y, scale, variant in source:
            p, normal, _, _ = ground.ray_cast(Vector((x, y, 2200)), Vector((0, 0, -1)), 4000)
            if p is None or normal.z < .45:
                continue
            records.append({"position": (x, y, p.z - .11), "scale": scale,
                            "variant": variant, "rotation": rng.uniform(0, math.tau)})
        require(bool(records), f"No trees rooted for {name}")
        scatter_object(name, records, library, collection)
        count += len(records)
    return count


def grasses(name, points, collection, mats, seed):
    rng=random.Random(seed)
    vertices,faces,indices=[],[],[]
    for x,y,z,scale in points:
        for j in range(rng.randint(8,16)):
            a=rng.uniform(0,math.tau)
            dx,dy=math.cos(a),math.sin(a)
            reach=scale*rng.uniform(.17,.61)
            h=scale*rng.uniform(.25,.82)
            w=scale*rng.uniform(.018,.047)
            k=len(vertices)
            vertices.extend(((x-dy*w,y+dx*w,z),(x+dy*w,y-dx*w,z),
                             (x+dx*reach*.5+dy*w*.75,y+dy*reach*.5-dx*w*.75,z+h*.62),
                             (x+dx*reach*.5-dy*w*.75,y+dy*reach*.5+dx*w*.75,z+h*.62),
                             (x+dx*reach,y+dy*reach,z+h)))
            faces.extend(((k,k+1,k+2,k+3),(k+3,k+2,k+4)))
            indices.extend([rng.randrange(len(mats))]*2)
    if faces:
        obj=mesh_object(name,vertices,faces,collection,mats[0],"grass_tufts")
        for mat in mats[1:]:
            obj.data.materials.append(mat)
        obj.data.polygons.foreach_set("material_index",indices)
