"""Sculpt and dress the Wanqing valley around the preserved hut assembly."""

import argparse
import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Vector
import numpy as np

HERE = Path(__file__).resolve().parent
AUTHORING = HERE.parents[1]
sys.path.insert(0, str(AUTHORING))
import build_wanqing_core_study as core
import build_wanqing_hut_study as hut
import build_wanqing_region_study as region

SOURCE = AUTHORING / "Candidates/wanqing-core-study-2026-09-07-01/wanqing-core-study-2026-09-07-01.blend"
NAME = "Cangyun_Wanqing"
RIVER_X = np.array([
    (-655, 173), (-455, 118), (-330, 28), (-218, -21), (-142, 2),
    (-74, 53), (-26, 63), (18, 55), (65, 39), (120, 32), (167, 53),
    (237, 113), (300, 104), (375, 86), (448, 113), (505, 156),
    (582, 133), (689, 81), (820, 174), (1020, 232), (1380, 326), (2245, 402),
], dtype=float)
# Basal ranges shaped separately so the skyline has saddles and offset summits.
MASSIFS = (
    (-247, -119, 171, 213, 152, -.28), (227, -50, 150, 219, 132, .34),
    (-291, 282, 215, 329, 330, -.52), (320, 372, 186, 335, 281, .51),
    (-168, 559, 128, 223, 243, -.35), (335, 715, 240, 310, 410, .63),
    (-540, 640, 227, 325, 501, -.23), (-395, 924, 265, 380, 605, .54),
    (577, 1104, 296, 426, 565, .27), (76, 1249, 219, 353, 556, -.38),
    (-730, 1320, 350, 425, 570, -.34), (849, 1492, 351, 456, 692, -.51),
    (-198, 1650, 285, 414, 664, .24), (-758, 1960, 377, 405, 705, .30),
    (425, 1850, 380, 431, 734, -.37), (902, 2130, 357, 412, 681, .29),
)
# Sculpted rock masses in metres: x, y, width, depth, rise, lean.
CRAGS = (
    (-118, 219, 49, 64, 91, -13), (-178, 319, 70, 74, 136, 17),
    (192, 327, 38, 59, 81, -12), (232, 373, 54, 79, 139, 11),
    (20, 444, 50, 63, 116, -19), (-48, 484, 57, 78, 191, 18),
    (-105, 532, 73, 98, 242, -15), (237, 509, 55, 81, 157, -14),
    (255, 598, 60, 83, 216, 24), (317, 698, 81, 102, 185, -20),
    (-258, 701, 76, 101, 209, -19), (-196, 823, 66, 110, 240, 8),
    (20, 931, 73, 82, 227, -18), (325, 984, 70, 95, 189, 31),
    (485, 1172, 110, 118, 249, -22),
)
LOOKOUT_PATH = ((-5, -26), (4, -35), (24, -42), (42, -38), (76, -38), (91, -27), (99, -15), (105, -12))
BRIDGE_Y = -38.0
PAVILION_XY = (105.0,-12.0)
CAMERAS = {
    "valley": ("Valley overlook", (-79, -405, 147), (41, 548, 155), 24.0, (2160, 1280)),
    "hut": ("Hut at eye height", (10.0, -12.6, 1.65), (-.65, 3.5, 2.45), 32, (1650, 1100)),
    "ford": ("Waterfall approach", (116, 325, 7.0), (93, 444, 38), 33, (1650, 1100)),
}


def smooth(low, high, value):
    t = np.clip((value - low) / (high - low), 0, 1)
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    return a + (b - a) * t


def noise(x, y, scale, seed):
    """Continuous value noise, with an integer lattice independent of array shape."""
    x, y = x / scale, y / scale
    ix, iy = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = smooth(0, 1, x - ix), smooth(0, 1, y - iy)

    def corner(i, j):
        n = (i * 374761393 + j * 668265263 + seed * 1274126177) & 0xffffffff
        n = ((n ^ (n >> 13)) * 1274126177) & 0xffffffff
        return (n ^ (n >> 16)) / 2147483648.0 - 1

    return mix(mix(corner(ix, iy), corner(ix+1, iy), fx),
               mix(corner(ix, iy+1), corner(ix+1, iy+1), fx), fy)


def river_center(y):
    ys, xs = RIVER_X.T
    slopes = np.gradient(xs, ys)
    index = np.clip(np.searchsorted(ys, y) - 1, 0, len(ys) - 2)
    span = ys[index + 1] - ys[index]
    t = np.clip((y - ys[index]) / span, 0, 1)
    return ((2*t**3 - 3*t*t + 1)*xs[index] + (t**3-2*t*t+t)*span*slopes[index]
            + (-2*t**3+3*t*t)*xs[index+1] + (t**3-t*t)*span*slopes[index+1])


def river_level(y):
    # y increases upstream. The primary cascade has an exposed ledge and a pool.
    return -4.25 + .023*y + 56*smooth(427, 451, y) + 91*smooth(706, 820, y) + 44*smooth(1150, 1320, y)


def river_width(y):
    return (6.8 + 2.3*np.sin(y*.019 + .6)**2 + 1.1*np.sin(y*.043)
            + 9*np.exp(-((y-386)/35)**2) + 6*np.exp(-((y-117)/34)**2)
            - 3.0*smooth(419, 435, y)*(1-smooth(455, 481, y)))


def path_distance(x, y, routes):
    distance = np.full(np.broadcast_shapes(np.shape(x), np.shape(y)), np.inf)
    for points in routes:
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            dx, dy = bx - ax, by - ay
            t = np.clip(((x - ax)*dx + (y - ay)*dy)/(dx*dx+dy*dy), 0, 1)
            distance = np.minimum(distance, np.hypot(x - ax - t*dx, y - ay - t*dy))
    return distance


def landform(x, y):
    wx = x + 38*noise(x, y, 141, 5) + 10*noise(x, y, 49, 3)
    wy = y + 43*noise(x, y, 161, 7) + 14*noise(x, y, 51, 11)
    relief = np.zeros_like(wx)
    for cx, cy, sx, sy, height, angle in MASSIFS:
        dx, dy = wx - cx, wy - cy
        u = (dx*math.cos(angle) + dy*math.sin(angle))/sx
        v = (dy*math.cos(angle) - dx*math.sin(angle))/sy
        r = (abs(u)**1.7 + abs(v)**1.7)**(1/1.7)
        spur = 1 - smooth(.04, 1.62, r)
        ridge = np.clip(1 - r*.69, 0, 1)
        relief = np.maximum(relief, height*(.68*spur**1.14 + .32*ridge**2.1))
    folds = 1-abs(noise(wx*.96 + wy*.27, wy*.58, 63, 29))
    scours = 1-abs(noise(wx*1.52-wy*.32, wy*.68, 25, 31))
    height = (1 + .019*y + relief*(.86 + .14*folds**2 + .062*scours**3)
              + (2 + relief*.075)*noise(x, y, 38, 73)
              + (1.6+relief*.028)*noise(x, y, 12, 89)
              + (.27+relief*.009)*noise(x, y, 4.9, 91))
    distance = abs(x - river_center(y))
    width = river_width(y)
    floodplain = river_level(y) + 2.1 + .108*np.maximum(0, distance-width)
    terrace = smooth(width+6, 109+24*noise(x, y, 75, 37), distance)
    height = mix(floodplain + noise(x, y, 16, 21)*.72, height, terrace)
    # The hanging valley drops over irregular rock shoulders, while the central
    # channel retains the precisely sampled water/riverbed profile.
    lateral = distance - width
    ledge_y = 425 + 5.5*noise(x,y,16,106) + 3*noise(x,y,7,107)
    ledge = -4.25+.023*y+56*smooth(ledge_y,ledge_y+12,y)
    ledge += 4.4*noise(x,y,15,108)+2.1*noise(x,y,5,112)
    face = (smooth(3,8,lateral)*(1-smooth(26,80,lateral))
            * smooth(399,425,y)*(1-smooth(455,490,y)))
    height = mix(height, ledge+.165*lateral+4, face*.93)
    # Preserve the visible crossing and low path grade across the floodplain.
    trail = path_distance(x, y, (LOOKOUT_PATH,))
    low_path = mix(.02, river_level(y)+1.3, smooth(4, 38, abs(x-5)))
    px,py = PAVILION_XY
    shelf = float(river_level(py)) + 12.2
    low_path = mix(low_path,shelf,smooth(78,px-1,x))
    height = mix(height, low_path, (1-smooth(.55, 3.7, trail))*(1-smooth(18, 33, abs(y+34))))
    pad = np.maximum(abs(x-px)*.84,abs(y-py))
    height = mix(height,shelf,1-smooth(4.7,12.5,pad))
    offset = distance - width
    banks = river_level(y) + np.where(offset < 0, np.maximum(offset*.41, -2.8), offset*.25)
    return mix(banks, height, smooth(1.0, 11.5, offset))


def axis(knots):
    return np.concatenate([np.linspace(a, b, math.ceil((b-a)/step)+1)[:-1]
                           for (a, step), (b, _) in zip(knots, knots[1:])] + [[knots[-1][0]]])


def sample_old_ground(obj, x, y):
    # Core.Ground is a 0.5 m lattice. Index by the authored XY to avoid mesh ordering.
    coords = np.empty((len(obj.data.vertices), 3), dtype=np.float32)
    obj.data.vertices.foreach_get("co", coords.ravel())
    origin = coords[:, :2].min(axis=0)
    ij = np.rint((coords[:, :2] - origin)/.5).astype(int)
    shape = tuple(ij.max(axis=0) + 1)
    require = region.require
    require(len(ij) == math.prod(shape), "Source core is no longer a complete heightfield")
    ground = np.empty(shape, dtype=np.float32)
    ground[ij[:, 0], ij[:, 1]] = coords[:, 2]
    i, j = np.moveaxis(np.clip(np.stack(((x-origin[0])/.5, (y-origin[1])/.5), axis=-1), 0, np.array(shape)-1.001), -1, 0)
    a, b = i.astype(int), j.astype(int)
    return mix(mix(ground[a,b], ground[a+1,b], i-a), mix(ground[a,b+1], ground[a+1,b+1], i-a), j-b)


def surface_material(name, color, roughness, texture_scale, relief, stretch=(1,1,1), attr=None):
    mat = hut.surface(name, color, roughness)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    source = nodes.new("ShaderNodeNewGeometry")
    stretch_node = nodes.new("ShaderNodeVectorMath")
    stretch_node.operation = "MULTIPLY"
    stretch_node.inputs[1].default_value = stretch
    links.new(source.outputs["Position"], stretch_node.inputs[0])
    detail = nodes.new("ShaderNodeTexNoise")
    detail.inputs["Scale"].default_value = texture_scale
    detail.inputs["Detail"].default_value = 4
    detail.inputs["Roughness"].default_value = .68
    links.new(stretch_node.outputs["Vector"], detail.inputs["Vector"])
    patina = nodes.new("ShaderNodeValToRGB")
    patina.color_ramp.elements[0].position = .18
    patina.color_ramp.elements[0].color = (.31, .40, .38, 1)
    patina.color_ramp.elements[1].position = .84
    patina.color_ramp.elements[1].color = (1.27, 1.19, 1.01, 1)
    links.new(detail.outputs["Fac"], patina.inputs["Fac"])
    mult = nodes.new("ShaderNodeMixRGB")
    mult.blend_type = "MULTIPLY"
    mult.inputs[0].default_value = 1
    mult.inputs[1].default_value = (*color[:3], 1)
    if attr:
        tint = nodes.new("ShaderNodeAttribute")
        tint.attribute_name = attr
        links.new(tint.outputs["Color"], mult.inputs[1])
    links.new(patina.outputs["Color"], mult.inputs[2])
    links.new(mult.outputs["Color"], bsdf.inputs["Base Color"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = .38
    bump.inputs["Distance"].default_value = relief
    links.new(detail.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def vertex_tint(obj, values, name):
    rgba = np.ones((len(values), 4), dtype=np.float32)
    rgba[:, :3] = np.reshape(values, (-1, 3))
    attr = obj.data.color_attributes.new(name=name, type="FLOAT_COLOR", domain="POINT")
    attr.data.foreach_set("color", rgba.ravel())


def grid(name, x, y, z, group, material, role):
    rows, cols = z.shape
    vertices = np.stack((x,y,z), axis=-1).reshape(-1,3)
    a = (np.arange(rows-1)[:, None]*cols + np.arange(cols-1)).ravel()
    faces = np.column_stack((a, a+1, a+1+cols, a+cols))
    obj = region.mesh_object(name, vertices.tolist(), faces.tolist(), group, material, role)
    obj.data.polygons.foreach_set("use_smooth", np.ones(len(faces), dtype=bool))
    return obj


def terrain(old, destination, material):
    bx = axis(((-1250, 7), (-315, 2.5), (-95, .72), (105, 2.5), (315, 6), (1250, 6)))
    by = axis(((-650, 7), (-226, 2.5), (-64, .54), (64, 1.6), (365, 1.5), (421, .75), (458, 1.5), (484, 2.9), (760, 6.4), (2240, 6)))
    bx, y = np.meshgrid(bx, by)
    # Align terrain rows with the river centre to resolve the narrow banks at any distance.
    x = bx + (river_center(y)-55)*(1-smooth(105, 680, abs(bx-55)))
    original = sample_old_ground(old, x, y)
    blend = smooth(31, 40, np.maximum(abs(x), abs(y)))
    z = mix(original, landform(x, y), blend)
    dy = np.gradient(z, axis=0)/np.gradient(y, axis=0)
    dx = np.gradient(z, axis=1)/np.gradient(x, axis=1)
    dy -= dx*np.gradient(x, axis=0)/np.gradient(y, axis=0)
    slope = np.hypot(dx, dy)
    detail = (noise(x, y, 47, 53)*.26 + noise(x, y, 10, 55)*.19 + noise(x,y,2.6,61)*.08)
    base = mix(np.array([.015,.050,.034]), np.array([.133,.225,.077]), (.41+detail)[...,None])
    forest = smooth(.1,.54, noise(x,y,37,109)*.55 + noise(x,y,12,113)*.19 + .27)
    base = mix(base, np.array([.025,.090,.043]), (.62*forest)[...,None])
    rock = smooth(.77, 1.65, slope + noise(x,y,31,92)*.39 + detail) * smooth(18,77,z)
    falls = smooth(408,428,y)*(1-smooth(449,471,y))*(1-smooth(15,91,abs(x-river_center(y))))
    rock = np.maximum(rock,falls*(.54+.42*smooth(.4,1.55,slope+noise(x,y,11,95)*.35)))
    strata = .42+.27*noise(x+y*.28,z*2.6,24,99)+.18*noise(x-y*.17,z*3.7,8,100)
    shale = mix(np.array([.053,.071,.077]), np.array([.227,.210,.166]), strata[...,None])
    base = mix(base, shale, rock[...,None])
    routes = (*core.ROUTES.values(), LOOKOUT_PATH)
    path = (1-smooth(.34, 1.55, path_distance(x,y,routes)-.5*detail))
    clearing = (1-smooth(2.9, 9.5, np.hypot(x,y+1.2)+2*detail))*.94
    silt = (1-smooth(.25, 4.7, abs(x-river_center(y))-river_width(y)-2*detail))*.88
    earth = mix(np.array([.101,.073,.041]), np.array([.31,.224,.121]), (.55+detail)[...,None])
    base = mix(base, earth, np.maximum(path,clearing)[...,None])
    base = mix(base, np.array([.167,.146,.097]), silt[...,None])
    # Tiles share the same border coordinates and gradient-derived normals.
    result = []
    xcuts = [0, int(np.searchsorted(bx[0],-155)), int(np.searchsorted(bx[0],155)), bx.shape[1]-1]
    ycuts = [0, int(np.searchsorted(y[:,0],-62)), int(np.searchsorted(y[:,0],67)),
             int(np.searchsorted(y[:,0],486)), int(np.searchsorted(y[:,0],970)), y.shape[0]-1]
    for row, (j,k) in enumerate(zip(ycuts,ycuts[1:])):
        for col, (i,l) in enumerate(zip(xcuts,xcuts[1:])):
            s = np.s_[j:k+1,i:l+1]
            obj = grid(f"Terrain.{row:02}.{col:02}", x[s], y[s], z[s], destination, material, "sculpted_heightfield")
            vertex_tint(obj, base[s].reshape(-1,3), "TerrainTint")
            normals = np.stack((-dx[s], -dy[s], np.ones_like(z[s])), axis=-1).reshape(-1,3)
            normals /= np.linalg.norm(normals, axis=1, keepdims=True)
            obj.data.normals_split_custom_set_from_vertices(normals.tolist())
            result.append(obj)
    return result


def rock_mass(name, destination, material, pos, sizes, lean, rng, layers=42, sides=30, ground=None):
    """Irregular ledges and vertical joints on the same solid."""
    center_x, center_y, bottom = pos
    width, depth, height = sizes
    phases = [rng.uniform(0,math.tau) for _ in range(6)]
    ridges = [1 + .19*math.cos(3*a+phases[0]) + .115*math.sin(5*a+phases[1])
              - .27*(.5+.5*math.cos(7*a+phases[2]))**6 + rng.uniform(-.06,.06)
              for a in np.linspace(0, math.tau, sides, endpoint=False)]
    shoulder = rng.uniform(.62,.80)
    upper = rng.uniform(.27,.54)
    verts, colors, faces = [], [], []
    for j in range(layers+1):
        t = j/layers
        profile = np.interp(t, (0,.14,.24,.51,.71,.85,.95,1), (1.13,.99,.86,shoulder,shoulder*.93,upper,upper*.87,.045))
        for i, a in enumerate(np.linspace(0,math.tau,sides,endpoint=False)):
            fracture = (.079*math.sin(4*a+t*5+phases[0])-.097*(.5+.5*math.sin(9*a-t*3+phases[1]))**5)
            ledge = .019*math.sin(t*71+2*math.sin(a*2+phases[3])) + .009*math.sin(t*146+a*3+phases[4])
            split = .069*math.exp(-((t-.53-.09*math.sin(a*2+phases[0]))/.045)**2)
            radius = max(.032, profile*(ridges[i] + fracture) + (ledge-split)*(1-t)**.45)
            px = center_x + math.cos(a)*width*radius + t*t*lean
            py = center_y + math.sin(a)*depth*radius + math.sin(t*3)*lean*.46
            pz = bottom + height*(t + .052*math.sin(a*2+phases[3])*math.sin(math.pi*t*.84) + .021*math.cos(a*5+phases[2])*t)
            if ground is not None and t < .37:
                rooted = ground_z(ground,px,py) - max(1.7, height*.024)
                pz += (min(bottom,rooted)-bottom)*(1-float(smooth(.025,.37,t)))
            verts.append((px,py,pz))
            moss = max(0, math.sin(a*3+phases[0])*.25+math.sin(t*35+phases[3])*.26+t*.36)
            tint = mix(np.array((.051,.071,.079)), np.array((.245,.209,.153)), .33+.12*math.sin(t*28+math.sin(a*3+phases[2]))+.27*math.sin(a*7+phases[1]))
            tint = mix(tint, np.array((.083,.130,.061)), moss*.82)
            colors.append(tint)
    for j in range(layers):
        for i in range(sides):
            n = (i+1)%sides
            faces.append((j*sides+i,j*sides+n,(j+1)*sides+n,(j+1)*sides+i))
    faces.append(tuple(range(sides-1,-1,-1)))
    faces.append(tuple(range(layers*sides,(layers+1)*sides)))
    obj = region.mesh_object(name, verts, faces, destination, material, "stratified_rock")
    obj.data.polygons.foreach_set("use_smooth", np.ones(len(faces),dtype=bool))
    vertex_tint(obj, colors, "RockTint")
    return obj


def ground_z(tree, x, y):
    hit, _, _, _ = tree.ray_cast(Vector((x,y,1500)), Vector((0,0,-1)), 2000)
    region.require(hit is not None, f"Terrain ray missed ({x:.3f}, {y:.3f})")
    return hit.z


def prism(vertices, faces, colors, path, radii, side_count, color, phase=0):
    """Tapered trunk or branch with shared rings and a continuous axis."""
    offset = len(vertices)
    for index, (p, radius) in enumerate(zip(path,radii)):
        tangent = (path[min(index+1,len(path)-1)]-path[max(0,index-1)]).normalized()
        right = tangent.cross(Vector((0,1,0))).normalized()
        up = tangent.cross(right)
        for n in range(side_count):
            angle = n*math.tau/side_count
            r = radius*(1+.13*math.sin(n*3+phase))
            vertices.append(tuple(p + r*(math.cos(angle)*right + math.sin(angle)*up)))
    for j in range(len(path)-1):
        for n in range(side_count):
            a, b = n, (n+1)%side_count
            faces.append((offset+j*side_count+a,offset+j*side_count+b,
                          offset+(j+1)*side_count+b,offset+(j+1)*side_count+a))
            colors.append(color)
    faces.append(tuple(offset+n for n in reversed(range(side_count))))
    faces.append(tuple(offset+(len(path)-1)*side_count+n for n in range(side_count)))
    colors.extend((color,color))


def foliage(vertices, faces, colors, center, span, depth, lift, angle, rng, palette, count):
    """Angled twig sprays and three-dimensional flattened needle clusters."""
    side = Vector((math.cos(angle), math.sin(angle), 0))
    forward = Vector((-side.y, side.x, 0))
    for _ in range(count):
        a = rng.uniform(0,math.tau)
        d = rng.random()**.65
        tip = center + side*(math.cos(a)*d*span) + forward*(math.sin(a)*d*depth)
        tip.z += lift*(1-d*d)*rng.uniform(.25,1.2)
        direction = (side*math.cos(a)+forward*math.sin(a)+Vector((0,0,rng.uniform(-.12,.65)))).normalized()
        long = rng.uniform(.23,.52)*span
        lat = Vector((-direction.y,direction.x,0)).normalized()*rng.uniform(.11,.23)*span
        j = len(vertices)
        vertices.extend(tuple(v) for v in (
            tip-direction*long*.65,tip+lat,tip+direction*long,tip-lat,
            tip+Vector((0,0,long*.22)),tip-Vector((0,0,long*.16)),
        ))
        faces.extend(((j,j+1,j+4),(j+1,j+2,j+4),(j+2,j+3,j+4),(j+3,j,j+4),
                      (j+1,j,j+5),(j+2,j+1,j+5),(j+3,j+2,j+5),(j,j+3,j+5)))
        color = rng.choice(palette)
        colors.extend((color,)*8)


def tree_template(name, destination, bark, palettes, seed, detail=True, broadleaf=False):
    rng = random.Random(seed)
    verts, faces, colors = [], [], []
    tall = rng.uniform(7.5,12.5) if not broadleaf else rng.uniform(6.5,9.5)
    crown = rng.uniform(2.4,3.8)
    lean = Vector((rng.uniform(-1.4,1.4),rng.uniform(-.9,.9),0))
    trunk = [Vector((0,0,-.20)) + Vector((0,0,t*tall)) + lean*(t*t) +
             Vector((math.sin(t*6)*.43, math.sin(t*8+.1)*.19,0))*t for t in np.linspace(0,1,8)]
    prism(verts,faces,colors,trunk,[.36,.28,.205,.161,.124,.085,.042,.005],9 if detail else 6,0,seed)
    if detail:
        for n in range(5):
            a = n*math.tau/5+rng.uniform(-.24,.24)
            tip = Vector((math.cos(a),math.sin(a),0))*rng.uniform(.65,1.46)
            prism(verts,faces,colors,[trunk[0]+Vector((0,0,.54)),tip*.47+Vector((0,0,.09)),tip-Vector((0,0,.19))],[.20,.098,.022],6,0)
    count = rng.randrange(12,17) if detail else rng.randrange(9,12)
    for j in range(count):
        t = .35 + .64*j/count
        if broadleaf:
            t = .51 + .47*j/count
        az = j*2.399963+rng.uniform(-.36,.36)+seed
        radial = Vector((math.cos(az),math.sin(az),0))
        base = trunk[min(6,int(t*7))].lerp(trunk[min(7,int(t*7)+1)], t*7%1)
        reach = 1.18*crown*math.sin(math.pi*(.18+.76*(t-.35)/.65))*(1.15 if broadleaf else 1)*rng.uniform(.73,1.15)
        branch = [base,base+radial*(reach*.43)+Vector((0,0,-.18)),
                  base+radial*(reach*.77)+Vector((0,0,.30)),base+radial*reach+Vector((0,0,.76))]
        prism(verts,faces,colors,branch,[.103*(1.2-t),.067,.039,.007],6,0,az)
        for k in range(4 if detail else 3):
            f = (k+1)/(4 if detail else 3)
            location = branch[1].lerp(branch[-1],f)
            location += Vector((-radial.y,radial.x,0))*rng.uniform(-.35,.35)
            breadth = rng.uniform(.97,1.39)*(1.07 if broadleaf else 1.19-.32*f)
            foliage(verts,faces,colors,location,breadth,breadth*.69,.85 if broadleaf else .38,az,rng,(1,2,2,3),rng.randint(31,43) if detail else 19)
    obj = region.mesh_object(name, verts, faces, destination, bark, "tree_template")
    for mat in palettes:
        obj.data.materials.append(mat)
    obj.data.polygons.foreach_set("material_index",np.asarray(colors,dtype=np.int32))
    return obj


def scatter_forest(ground, destination, bark, greens, ochres):
    rng = random.Random(4371)
    near_library = bpy.data.collections.new("Tree library / close pine and maple")
    far_library = bpy.data.collections.new("Tree library / ridge pine and maple")
    for lib, detail in ((near_library, True),(far_library,False)):
        for n in range(6):
            tree_template(f"{n:02} {'Maple' if n >= 4 else 'Pine'}",lib,bark,ochres if n>=4 else greens,
                          457+n*27,detail,n>=4)
    def record(x,y,z,scale,variant):
        return {"position": (x,y,z-.085), "scale": scale, "variant": variant, "rotation": rng.uniform(0,math.tau)}
    near, far = [], []
    hero_sites = ((-7.7,3,1.08,0),(-9.2,-5.3,.91,2),(-10.1,1.0,1.09,1),
                  (5.4,4.9,.94,1),(6.8,7.5,.89,4),(-3.8,11,1.1,3),(14.8,-8.5,1.18,0),
                  (16.8,-14.6,.76,5),(-13.8,-17.3,.94,1),(7.6,15.3,1.05,2),(-15.7,16.2,1.15,3),
                  (21.0,1.2,1.14,2),(-2.5,22.2,.91,0),(11.2,23.8,.98,5))
    occupied = [(x,y) for x,y,_,_ in hero_sites]
    for x,y,scale,kind in hero_sites:
        near.append(record(x,y,ground_z(ground,x,y),scale,kind))
    for _ in range(6960):
        x,y = rng.uniform(-104,139),rng.uniform(-205,234)
        if not core.plantable(x,y,.55) or float(path_distance(x,y,(LOOKOUT_PATH,))) < 2.15:
            continue
        if abs(x-float(river_center(y))) < float(river_width(y))+2.55:
            continue
        if y > 14 and 3 < x < 9 and y < 39:
            continue
        if math.hypot(x-PAVILION_XY[0],y-PAVILION_XY[1])<9.5:
            continue
        if any((x-a)**2+(y-b)**2 < 16 for a,b in occupied):
            continue
        cover = float(noise(x,y,32,25))*.34 + float(noise(x,y,12,27))*.20
        if rng.random() > .43+cover:
            continue
        hit, normal, _, _ = ground.ray_cast(Vector((x,y,1200)),Vector((0,0,-1)))
        if hit is None or normal.z < .64:
            continue
        occupied.append((x,y))
        kind = rng.randrange(4) if rng.random() > .16 else rng.randrange(4,6)
        near.append(record(x,y,hit.z,rng.uniform(.49,1.12),kind))
    # Cluster points by relief and canopy suitability. Geometry nodes share each template mesh.
    count = 76200
    x = np.array([rng.uniform(-1040,1050) for _ in range(count)])
    y = np.array([rng.uniform(-505,1700) for _ in range(count)])
    cover = .47+.52*noise(x,y,120,41)+.23*noise(x,y,37,43)
    selected = ((abs(x-river_center(y))>river_width(y)+4)
                & ((x < -105)|(x > 140)|(y < -205)|(y > 234)))
    for px,py,p in zip(x[selected],y[selected],cover[selected]):
        if rng.random() > p:
            continue
        hit, normal, _, _ = ground.ray_cast(Vector((px,py,1500)),Vector((0,0,-1)))
        if hit is None or normal.z < rng.uniform(.56,.88):
            continue
        if hit.z > rng.uniform(415,620):
            continue
        kind = rng.randrange(4) if rng.random() > .064 else rng.randrange(4,6)
        far.append(record(px,py,hit.z,rng.uniform(.61,1.34),kind))
    for x,y,scale,kind in ((-175,-215,1.48,0),(-167,-228,1.25,3),(-188,-202,1.43,2),
                            (-173,-242,1.24,1),(138,-251,1.31,3),(145,-226,1.38,1)):
        far.append(record(x,y,ground_z(ground,x,y),scale,kind))
    region.scatter_object("Canopy / hut and lowland",near,near_library,destination)
    region.scatter_object("Canopy / valley and foothills",far,far_library,destination)
    print(f"CANOPY placements near={len(near)} regional={len(far)}",flush=True)


def stream(destination):
    material = hut.surface("Creek / reflective green water",(.019,.107,.094),.25)
    nodes, links = material.node_tree.nodes, material.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["IOR"].default_value = 1.333
    bsdf.inputs["Transmission Weight"].default_value = .26
    bsdf.inputs["Coat Weight"].default_value = .3
    bsdf.inputs["Coat Roughness"].default_value = .12
    tex = nodes.new("ShaderNodeNewGeometry")
    stretch = nodes.new("ShaderNodeVectorMath"); stretch.operation = "MULTIPLY"
    stretch.inputs[1].default_value = (1.1,2.75,1)
    links.new(tex.outputs["Position"],stretch.inputs[0])
    ripple = nodes.new("ShaderNodeTexNoise")
    ripple.inputs["Scale"].default_value = 1.7
    ripple.inputs["Detail"].default_value = 2.4
    links.new(stretch.outputs["Vector"],ripple.inputs["Vector"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = .33
    bump.inputs["Distance"].default_value = .077
    links.new(ripple.outputs["Fac"],bump.inputs["Height"])
    links.new(bump.outputs["Normal"],bsdf.inputs["Normal"])
    tint = nodes.new("ShaderNodeAttribute"); tint.attribute_name = "WaterTint"
    lacing = nodes.new("ShaderNodeMixRGB")
    lacing.blend_type = "MULTIPLY"
    lacing.inputs[0].default_value = .33
    links.new(tint.outputs["Color"],lacing.inputs[1])
    links.new(ripple.outputs["Fac"],lacing.inputs[2])
    links.new(lacing.outputs["Color"],bsdf.inputs["Base Color"])
    y = axis(((-650,2.2),(370,1.1),(421,.44),(463,.7),(525,1.3),(2240,2.5)))[:,None] + np.zeros((1,19))
    s = np.linspace(-1.07,1.07,19)[None,:]
    x = river_center(y) + river_width(y)*s
    z = river_level(y) + .018*np.sin(y*2.6+x*.49)
    river = grid("Wanqing creek / pool, run and cascade",x,y,z,destination,material,"continuous_water_surface")
    shoal = smooth(.26,1,abs(s)) + np.zeros_like(z)
    rapids = smooth(.28,1.25,np.gradient(z,axis=0)/np.gradient(y,axis=0))
    color = mix(np.array([.012,.108,.101]),np.array([.041,.249,.177]),shoal[...,None]*.87)
    color = mix(color,np.array([.45,.62,.56]),rapids[...,None]*.61)
    vertex_tint(river,color.reshape(-1,3),"WaterTint")
    foam = hut.surface("Breaking current / translucent foam",(.52,.68,.60),.28)
    foam.node_tree.nodes.get("Principled BSDF").inputs["Transmission Weight"].default_value = .14
    rng = random.Random(508)
    verts, faces = [], []
    for a,b,n in ((-64,103,125),(369,425,165),(422,466,260),(466,493,60),(708,820,130)):
        for _ in range(n):
            py = rng.uniform(a,b)
            offset = rng.uniform(-.94,.94)
            length = rng.uniform(.6,4.5)*(1.3 if 419<py<469 else .65)
            width = rng.uniform(.018,.23)
            index = len(verts)
            for j in range(7):
                t = j/6
                dy = py + (t-.5)*length
                dx = float(river_center(dy)+river_width(dy)*offset)+.14*math.sin(5*t+py)
                radius = width*math.sin(math.pi*t)**.7
                pz = float(river_level(dy))+.032 + .018*math.sin(dy*2.6+dx*.49)
                verts.extend(((dx-radius,dy,pz),(dx+radius,dy,pz)))
                if j:
                    k=index+2*j
                    faces.append((k-2,k-1,k+1,k))
    region.mesh_object("White water / current filaments",verts,faces,destination,foam,"surface_foam")
    return river


def hut_detail(destination, ground, rock):
    wood = surface_material("Porch / weathered cedar",(.128,.070,.035),.68,3.8,.028,(2.3,.33,2.4))
    bronze = hut.surface("Lantern / dark bronze",(.051,.032,.015),.39,.58)
    paper = hut.surface("Lantern / warm oiled paper",(.84,.44,.15),.57)
    bsdf = paper.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Emission Color"].default_value = (1,.31,.065,1)
    bsdf.inputs["Emission Strength"].default_value = 1.25
    for x,y,z in ((1.73,-.35,1.78),):
        hut.beam("Lantern hook", (x,y,z+.15),(x,y+.33,z+.21),.012,destination,bronze)
        hut.beam("Lantern suspension",(x,y,z+.13),(x,y,z-.015),.006,destination,bronze)
        hut.box("Porch lantern / paper", (x,y,z-.145),(.163,.163,.26),destination,paper,.023)
        for k in (-.29,-.03):
            hut.box("Porch lantern / frame",(x,y,z+k),(.19,.19,.035),destination,bronze,.008)
        light = bpy.data.lights.new("Porch lantern / warm pool","POINT")
        light.color=(1,.43,.16); light.energy=9; light.shadow_soft_size=.11
        lamp=bpy.data.objects.new(light.name,light); destination.objects.link(lamp); lamp.location=(x,y-.15,z-.15)
    rng = random.Random(516)
    for j in range(29):
        py = rng.uniform(-20,-2.4)
        px = rng.uniform(-4.5,7.0)
        d = float(path_distance(px,py,core.ROUTES.values()))
        if not .48 < d < 1.9:
            continue
        z = ground_z(ground,px,py)
        a=rng.uniform(.10,.28)
        rock_mass(f"Track shale {j:02}",destination,rock,(px,py,z-.045),(a,a*.61,rng.uniform(.08,.15)),.034,rng,6,10)
    y = BRIDGE_Y
    mid = float(river_center(y))
    half = float(river_width(y)) + 2.55
    west = ground_z(ground,mid-half,y)+.13
    east = ground_z(ground,mid+half,y)+.13
    level = max(west,east,float(river_level(y))+1.46)
    def deck(t):
        return mix(west,east,t)+(level-min(west,east))*math.sin(math.pi*t)**1.35
    span = 2*half
    for j in range(45):
        t = j/44
        x = mid-half+span*t
        z = deck(t)
        board = hut.box(f"Footbridge / deck {j:02}",(x,y,z),(span/44+.006,2.14,.11),destination,wood,.012)
        board.rotation_euler.z = rng.uniform(-.009,.009)
    for j in range(7):
        t = j/6
        x = mid-half+span*t
        z = deck(t)
        for v in (-.96,.96):
            hut.box(f"Footbridge / post {j}.{v}",(x,y+v,z+.43),(.12,.12,.99),destination,wood,.018)
            if j:
                prev = (j-1)/6
                hut.beam("Footbridge / rail", (mid-half+span*prev,y+v,deck(prev)+.81),
                         (x,y+v,z+.81),.048,destination,wood,vertices=8)
            if j in (0,2,4,6):
                g = ground_z(ground,x,y+v)
                hut.beam("Footbridge / pile",(x,y+v,g-.18),(x,y+v,z-.03),.145,destination,wood,vertices=9)
    return {"bridge_deck_z": deck(.5), "bridge_x_limits": (mid-half,mid+half)}



def stream_pavilion(destination, ground):
    """A small open shelter placed above the footbridge on the east bank."""
    x,y = PAVILION_XY
    platform = max(ground_z(ground,x+a,y+b) for a in (-4.7,0,4.7) for b in (-2.9,0,2.9))+.18
    stone=surface_material("Pavilion / cut granite",(.149,.177,.175),.8,2.4,.061,(1,1,1.7))
    frame=surface_material("Pavilion / oxblood lacquer",(.224,.060,.024),.53,4.6,.039,(1.8,1.8,.29))
    tile=surface_material("Pavilion / ink glazed tile",(.039,.064,.071),.45,3.7,.024)
    ridge=hut.surface("Pavilion / cap tile",(.062,.094,.09),.46,.14)
    foot=hut.surface("Pavilion / dark steps",(.104,.130,.122),.82)
    bottom=min(ground_z(ground,x+a,y+b) for a in (-4.7,0,4.7) for b in (-2.9,0,2.9))-.12
    region.require(.15 < platform-bottom < .75,"Pavilion terrace does not match its plinth")
    hut.box("Stream pavilion / plinth",(x,y,(bottom+platform)/2),(10.0,6.3,platform-bottom),destination,stone,.10)
    hut.box("Stream pavilion / flagstone deck",(x,y,platform),(9.85,6.11,.25),destination,foot,.065)
    for a in (-4.15,0,4.15):
        for b in (-2.42,2.42):
            hut.box("Pavilion column foot",(x+a,y+b,platform+.16),(.71,.71,.33),destination,stone,.09)
            hut.beam("Pavilion lacquer column",(x+a,y+b,platform+.23),(x+a,y+b,platform+3.42),.203,destination,frame,vertices=16)
            for sign in ((-1,1) if a==0 else (-math.copysign(1,a),)):
                hut.beam("Pavilion bracket",(x+a,y+b,platform+2.54),(x+a+sign*.86,y+b,platform+3.37),
                         .107,destination,frame,vertices=8)
    for b in (-2.42,2.42):
        hut.box("Pavilion eave beam",(x,y+b,platform+3.26),(9.4,.42,.36),destination,frame,.05)
    for a in (-4.15,4.15):
        hut.box("Pavilion tie beam",(x+a,y,platform+3.22),(.37,5.14,.38),destination,frame,.06)
    def roof_z(a,b):
        v = abs(b)/3.65
        return platform+5.18-2.25*(1-(1-v)**1.65)+.55*v**3+.49*(abs(a)/5.62)**4*v**2
    ax,by=np.meshgrid(np.linspace(-5.62,5.62,67),np.linspace(-3.65,3.65,39))
    roof=np.asarray([[roof_z(a,b) for a,b in zip(row_a,row_b)] for row_a,row_b in zip(ax,by)])
    roof += .058*np.cos(ax*math.tau/.285)
    roof_obj=grid("Stream pavilion / curved pan tiles",ax+x,by+y,roof,destination,tile,"pavilion_roof")
    thickness=roof_obj.modifiers.new("Roof tile depth","SOLIDIFY")
    thickness.thickness=.14
    for b in (-3.65,0,3.65):
        points=[(x+a,y+b,roof_z(a,b)+.13) for a in np.linspace(-5.73,5.73,23)]
        for a,d in zip(points,points[1:]):
            hut.beam("Pavilion glazed ridge",a,d,.112,destination,ridge,vertices=8)
    approach_x=x-5.13
    approach_z=ground_z(ground,approach_x-2.25,y)
    for i in range(7):
        t=i/6
        rise=mix(approach_z,platform,t)
        ht=max(.20,rise-ground_z(ground,approach_x-2.2+2.2*t,y)+.14)
        hut.box("Pavilion west steps",(approach_x-2.2+2.2*t,y,rise-ht/2),(.45,2.34,ht),destination,stone,.032)
    lamp=hut.surface("Pavilion / amber paper",(.82,.34,.092),.63)
    shader=lamp.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Emission Color"].default_value=(1,.34,.075,1)
    shader.inputs["Emission Strength"].default_value=1.55
    for a in (-3.06,3.06):
        hut.beam("Pavilion / lantern drop",(x+a,y-2.25,platform+3.32),(x+a,y-2.25,platform+2.99),.019,destination,frame,vertices=8)
        hut.box("Pavilion / lantern",(x+a,y-2.25,platform+2.78),(.31,.31,.42),destination,lamp,.054)

def understory(destination, ground, slate, mats):
    rng = random.Random(2243)
    for i in range(175):
        y = rng.uniform(-132,207)
        width = float(river_width(y))
        x = float(river_center(y)) + rng.choice((-1,1))*(width+rng.uniform(-1.4,8.2))
        if abs(y-BRIDGE_Y)<2.4:
            continue
        z = ground_z(ground,x,y)
        size = rng.uniform(.27,1.55)*(1 if i<130 else 2.4)
        rock_mass(f"Alluvial stone {i:03}",destination,slate,(x,y,z-.30*size),
                  (size,size*rng.uniform(.53,1.20),size*rng.uniform(.63,1.39)),.17*size,rng,8,12)
    for i in range(47):
        y = rng.uniform(390,427)
        side = rng.choice((-1,1))
        x = float(river_center(y)) + side*(float(river_width(y))+rng.uniform(-1.7,14))
        z = ground_z(ground,x,y)
        size = rng.uniform(.66,3.8)
        rock_mass(f"Cascade talus {i+1:02}",destination,slate,(x,y,z-size*.57),
                  (size*1.25,size*.85,size*rng.uniform(.94,1.82)),size*.13,rng,10,16)
    verts, faces, colors = [], [], []
    sites = []
    for _ in range(5900):
        x,y = rng.uniform(-19,21),rng.uniform(-29,26)
        path = float(path_distance(x,y,core.ROUTES.values()))
        if math.hypot(x,y-1)<4.4 or path < .67 or (-2.5<x<2.5 and -4<y<5.5):
            continue
        if rng.random() > (.39 if path < 3.3 else .16+.13*float(noise(x,y,4,19))):
            continue
        sites.append((x,y,.21,.68,False))
    for _ in range(680):
        y=rng.uniform(-91,188)
        x=float(river_center(y))+rng.choice((-1,1))*(float(river_width(y))+rng.uniform(1.1,5.8))
        if abs(y-BRIDGE_Y)>3.3:
            sites.append((x,y,.34,.94,True))
    for x,y,lo,hi,reed in sites:
        center = Vector((x,y,ground_z(ground,x,y)-.017))
        for _ in range(rng.randint(7,13)):
            a=rng.uniform(0,math.tau)
            direction=Vector((math.cos(a),math.sin(a),0))
            side=Vector((-direction.y,direction.x,0))*rng.uniform(.007,.023)
            height=rng.uniform(lo,hi)
            start=center+direction*rng.uniform(.025,.17)
            knee=start+direction*height*.19+Vector((0,0,height*.64))
            tip=start+direction*height*rng.uniform(.31,.60)+Vector((0,0,height))
            i=len(verts)
            verts.extend(tuple(v) for v in (start-side,start+side,knee+side*.75,knee-side*.75,tip))
            faces.extend(((i,i+1,i+2,i+3),(i+3,i+2,i+4)))
            shade = rng.choice((0,0,1,1,2,2,3)) if not reed else rng.choice((0,1,1,2,3,3))
            colors.extend((shade,shade))
    for x,y in ((5.6,-7.7),(7.3,-7.2),(-4.9,-4.8),(-5.8,-5.4),(4.4,-1.2),(-4.6,1.5),
                (7.9,-9.5),(2.6,-11.8),(-8.5,-8.9),(11.4,-11.2)):
        z=ground_z(ground,x,y)
        for _ in range(rng.randrange(7,11)):
            az=rng.uniform(0,math.tau)
            d=Vector((math.cos(az),math.sin(az),0))
            side=Vector((-d.y,d.x,0))
            root=Vector((x,y,z))
            reach=rng.uniform(.51,.94); lift=rng.uniform(.29,.58)
            def fern(t):
                return root+d*t*reach+Vector((0,0,lift*math.sin(t*2.22)))
            prism(verts,faces,colors,[fern(t) for t in np.linspace(0,1,8)],[.010,.009,.008,.006,.005,.004,.003,.0005],4,2)
            for t in np.linspace(.14,.92,11):
                for sign in (-1,1):
                    start=fern(t)
                    out=side*sign*reach*.24*(1-t)**.64
                    tip=start+out+d*.11*(1-t)+Vector((0,0,.025))
                    center=start.lerp(tip,.53)
                    i=len(verts)
                    verts.extend(tuple(p) for p in (start,center-d*.029*(1-t),tip,center+d*.035*(1-t)))
                    faces.append((i,i+1,i+2,i+3))
                    colors.append(rng.choice((0,1,2)))
    grass = region.mesh_object("Understory / sedges, grasses and ferns",verts,faces,destination,mats[0],"understory")
    for mat in mats[1:]:
        grass.data.materials.append(mat)
    grass.data.polygons.foreach_set("material_index",np.asarray(colors,dtype=np.int32))


def atmosphere(lighting):
    world = bpy.data.worlds.new("Cool high sky / warm horizon")
    bpy.context.scene.world = world
    nodes, links = world.node_tree.nodes, world.node_tree.links
    nodes.clear()
    background = nodes.new("ShaderNodeBackground")
    background.inputs["Color"].default_value=(.49,.66,.87,1)
    background.inputs["Strength"].default_value=.63
    sky = nodes.new("ShaderNodeTexSky")
    sky.sky_type="HOSEK_WILKIE"
    sky.sun_direction = (-.78,-.32,.54)
    sky.turbidity=3.2
    visible=nodes.new("ShaderNodeBackground")
    visible.inputs["Strength"].default_value=.80
    direction=nodes.new("ShaderNodeTexCoord")
    elongation=nodes.new("ShaderNodeVectorMath")
    elongation.operation="MULTIPLY"
    elongation.inputs[1].default_value=(3.6,3.9,19.0)
    links.new(direction.outputs["Normal"],elongation.inputs[0])
    wisps=nodes.new("ShaderNodeTexNoise")
    wisps.inputs["Scale"].default_value=1.6
    wisps.inputs["Detail"].default_value=2.6
    links.new(elongation.outputs["Vector"],wisps.inputs["Vector"])
    mask=nodes.new("ShaderNodeMapRange")
    mask.interpolation_type="SMOOTHERSTEP"
    for key,value in (("From Min",.49),("From Max",.72),("To Max",.57)):
        mask.inputs[key].default_value=value
    links.new(wisps.outputs["Fac"],mask.inputs["Value"])
    cirrus=nodes.new("ShaderNodeMixRGB")
    cirrus.inputs[2].default_value=(.78,.62,.45,1)
    links.new(mask.outputs["Result"],cirrus.inputs[0])
    links.new(sky.outputs["Color"],cirrus.inputs[1])
    links.new(cirrus.outputs["Color"],visible.inputs["Color"])
    paths=nodes.new("ShaderNodeLightPath")
    mix_sky=nodes.new("ShaderNodeMixShader")
    links.new(paths.outputs["Is Camera Ray"],mix_sky.inputs[0])
    links.new(background.outputs[0],mix_sky.inputs[1])
    links.new(visible.outputs[0],mix_sky.inputs[2])
    output=nodes.new("ShaderNodeOutputWorld")
    links.new(mix_sky.outputs[0],output.inputs["Surface"])
    sun_data=bpy.data.lights.new("Sun across the valley","SUN")
    sun_data.energy=3.55
    sun_data.angle=math.radians(4.8)
    sun_data.color=(1,.83,.59)
    sun=bpy.data.objects.new(sun_data.name,sun_data)
    lighting.objects.link(sun)
    sun.rotation_euler=Vector((.78,.32,-.63)).to_track_quat("-Z","Y").to_euler()

    fog=bpy.data.materials.new("Valley air / height falloff and broken inversion")
    nodes,links=fog.node_tree.nodes,fog.node_tree.links
    nodes.clear()
    output=nodes.new("ShaderNodeOutputMaterial")
    scatter=nodes.new("ShaderNodeVolumeScatter")
    scatter.inputs["Color"].default_value=(.67,.79,.93,1)
    scatter.inputs["Anisotropy"].default_value=.18
    links.new(scatter.outputs["Volume"],output.inputs["Volume"])
    position=nodes.new("ShaderNodeNewGeometry")
    xyz=nodes.new("ShaderNodeSeparateXYZ")
    links.new(position.outputs["Position"],xyz.inputs["Vector"])
    height=nodes.new("ShaderNodeMapRange")
    height.interpolation_type="SMOOTHERSTEP"
    for key,value in (("From Min", -12),("From Max",532),("To Min",.00033),("To Max",.000075)):
        height.inputs[key].default_value=value
    links.new(xyz.outputs["Z"],height.inputs["Value"])
    stretch=nodes.new("ShaderNodeVectorMath")
    stretch.operation="MULTIPLY"; stretch.inputs[1].default_value=(.0045,.006,.071)
    links.new(position.outputs["Position"],stretch.inputs[0])
    clouds=nodes.new("ShaderNodeTexNoise")
    clouds.inputs["Scale"].default_value=1
    clouds.inputs["Detail"].default_value=2.1
    links.new(stretch.outputs["Vector"],clouds.inputs["Vector"])
    edge=nodes.new("ShaderNodeMapRange")
    edge.interpolation_type="SMOOTHERSTEP"
    for key,value in (("From Min",.43),("From Max",.76),("To Min",0),("To Max",.0015)):
        edge.inputs[key].default_value=value
    links.new(clouds.outputs["Fac"],edge.inputs["Value"])
    layer=nodes.new("ShaderNodeMapRange")
    layer.interpolation_type="SMOOTHERSTEP"
    for key,value in (("From Min",32),("From Max",123),("To Min",.70),("To Max",0)):
        layer.inputs[key].default_value=value
    links.new(xyz.outputs["Z"],layer.inputs["Value"])
    mist=nodes.new("ShaderNodeMath"); mist.operation="MULTIPLY"
    links.new(edge.outputs["Result"],mist.inputs[0]); links.new(layer.outputs["Result"],mist.inputs[1])
    add=nodes.new("ShaderNodeMath"); add.operation="ADD"
    links.new(height.outputs["Result"],add.inputs[0]); links.new(mist.outputs[0],add.inputs[1])
    links.new(add.outputs[0],scatter.inputs["Density"])
    obj=hut.box("Valley atmosphere",(0,792,407),(2720,3350,980),lighting,fog,0)
    obj.display_type="WIRE"


def add_cameras(scene, collection, ground):
    for key,(name,loc,target,lens,_) in CAMERAS.items():
        x,y,z=loc
        if key != "valley":
            z += ground_z(ground,x,y)
        cam=hut.camera(name,(x,y,z),target,lens,collection)
        cam.data.clip_end=5500
    scene.camera=bpy.data.objects[CAMERAS["valley"][0]]


def build(output):
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE),load_ui=False,use_scripts=False)
    scene=bpy.context.scene
    scene.name="Cangyun / Wanqing valley"
    scene["scope"]="Regional environment art; geographic placement is an authoring decision."
    scene["hut_source"]=SOURCE.name
    house=bpy.data.collections["00.Hut"]
    source_ground=bpy.data.objects["Core.Ground"]
    preserved={o.name:region.protected_object_state(o,o.matrix_world) for o in house.all_objects}
    ground_group=region.group("11.Sculpted terrain")
    slate_group=region.group("12.Crags and deposits")
    water_group=region.group("20.Stream and cascades")
    forest=region.group("30.Forest")
    low=region.group("31.Forest floor")
    dress=region.group("40.Trail and hut dressing")
    lighting=region.group("60.Atmosphere and sun")
    camera_group=region.group("70.Review cameras")
    loam=surface_material("Valley / soil, granite and moss",(.11,.15,.08),.86,1.55,.13,(1.1,1,1.85),"TerrainTint")
    slate=surface_material("Crags / weathered slate",(.14,.15,.13),.76,.56,.27,(.64,.76,3.25),"RockTint")
    bark=surface_material("Pine / fissured bark",(.083,.051,.032),.84,9,.10,(2.1,2.1,.39))
    greens=[hut.surface(f"Pine needles / {i+1}",v,.78) for i,v in enumerate(((.022,.082,.039),(.041,.135,.051),(.086,.207,.078)))]
    ochres=[hut.surface(f"Maple / {i+1}",v,.77) for i,v in enumerate(((.22,.061,.015),(.39,.132,.026),(.53,.241,.056)))]
    plants=[hut.surface(f"Sedge and fern / {i+1}",v,.83) for i,v in enumerate(((.067,.158,.059),(.10,.207,.073),(.177,.265,.091),(.32,.261,.092)))]
    terrain_objects=terrain(source_ground,ground_group,loam)
    keep={c.name for c in (house,ground_group,slate_group,water_group,forest,low,dress,lighting,camera_group)}
    for collection in list(scene.collection.children):
        if collection.name not in keep:
            for obj in list(collection.all_objects):
                bpy.data.objects.remove(obj,do_unlink=True)
            bpy.data.collections.remove(collection)
    bpy.context.view_layer.update()
    bare=region.terrain_tree(terrain_objects).tree
    print("TERRAIN",sum(len(obj.data.vertices) for obj in terrain_objects),flush=True)
    rng=random.Random(535)
    crags=[]
    for i,(x,y,w,d,h,lean) in enumerate(CRAGS):
        z=ground_z(bare,x,y) - h*.30
        crags.append(rock_mass(f"Valley cliff {i+1:02}",slate_group,slate,(x,y,z),(w,d,h),lean,rng,ground=bare))
    bpy.context.view_layer.update()
    forest_floor=region.terrain_tree(terrain_objects+crags).tree
    scatter_forest(forest_floor,forest,bark,greens,ochres)
    stream(water_group)
    crossing=hut_detail(dress,bare,slate)
    stream_pavilion(dress,bare)
    understory(low,bare,slate,plants)
    atmosphere(lighting)
    hut.area("Clearing / warm bounce", (8,-9,9.5),(-.65,1.2,1.1),2200,(1,.81,.61),8,lighting)
    hut.area("Clearing / cool sky bounce", (-6,-5,5.5),(1,0,1.5),380,(.55,.75,1),6,lighting)
    add_cameras(scene,camera_group,bare)
    scene.render.engine="CYCLES"
    scene.cycles.device="CPU"
    scene.cycles.samples=48
    scene.cycles.use_denoising=True
    scene.cycles.volume_step_rate=2.4
    scene.cycles.volume_max_steps=480
    scene.cycles.volume_bounces=1
    scene.view_settings.view_transform="AgX"
    scene.view_settings.look="AgX - Medium High Contrast"
    scene.view_settings.exposure=.48
    scene.render.resolution_x,scene.render.resolution_y=CAMERAS["valley"][4]
    scene.render.resolution_percentage=100
    scene.render.filepath="//Preview/Wanqing_valley.png"
    bpy.context.view_layer.update()
    region.require(preserved=={o.name:region.protected_object_state(o,o.matrix_world) for o in house.all_objects},"Hut transform or mesh changed")
    for marker,gameplay_id in core.MARKERS.items():
        region.require(bpy.data.objects[marker].get("gameplay_id")==gameplay_id, f"Missing interaction ID {marker}")
    region.require(crossing["bridge_deck_z"] > float(river_level(BRIDGE_Y))+1.0,"Bridge clearance failed")
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=="VIEW_3D":
                area.spaces.active.clip_end=5500
                area.spaces.active.region_3d.view_perspective="CAMERA"
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(output),compress=True,relative_remap=False)


def render(path, name, output, scale, samples):
    bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
    scene=bpy.context.scene
    prefs=bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type="METAL"
    prefs.refresh_devices()
    for dev in prefs.devices:
        dev.use=dev.type=="METAL"
    region.require(any(d.use for d in prefs.devices),"Cycles Metal device unavailable")
    scene.cycles.device="GPU"
    scene.cycles.samples=samples
    scene.cycles.adaptive_threshold=.043 if scale<100 else .025
    scene.camera=bpy.data.objects[CAMERAS[name][0]]
    scene.render.resolution_x,scene.render.resolution_y=CAMERAS[name][4]
    scene.render.resolution_percentage=scale
    scene.render.image_settings.file_format="PNG"
    scene.render.filepath=str(output)
    print(f"RENDER {name} {[d.name for d in prefs.devices if d.use]} {samples} samples",flush=True)
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=("build","render"))
    p.add_argument("--blend",type=Path,default=HERE/f"{NAME}.blend")
    p.add_argument("--view",choices=CAMERAS,default="valley")
    p.add_argument("--image",type=Path)
    p.add_argument("--scale",type=int,default=100)
    p.add_argument("--samples",type=int,default=48)
    args=p.parse_args(sys.argv[sys.argv.index("--")+1:])
    if args.mode=="build":
        region.require(args.blend.resolve()!=SOURCE.resolve(),"Preserve the source blend")
        build(args.blend.resolve())
    else:
        render(args.blend.resolve(),args.view,args.image.resolve(),args.scale,args.samples)
