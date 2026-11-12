"""Shared mountain heightfields and surface sampling."""

from pathlib import Path
import sys

from mathutils import Vector
import numpy as np

HERE = Path(__file__).resolve().parent
AUTHORING = HERE.parents[1]
sys.path[:0] = [str(AUTHORING), str(HERE.parent / "wanqing-valley-2026-11-12")]
from build_wanqing_hut_study import area, camera, surface
from build_wanqing_region_study import group, mesh_object, require, terrain_tree
from build_valley import axis, grid, mix, noise, rock_mass, smooth, surface_material, vertex_tint


def terrain(name, xs, ys, height, path, materials, collection):
    x, y = np.meshgrid(xs, ys)
    z = height(x, y)
    gx = np.gradient(z, xs, axis=1)
    gy = np.gradient(z, ys, axis=0)
    steep = smooth(.43, 1.15, np.hypot(gx, gy) + noise(x,y,8.5,135)*.22)
    dust = .5 + .24*noise(x,y,35,44) + .22*noise(x,y,7.7,54) + .07*noise(x,y,2.2,78)
    soil = mix(np.array((.032,.054,.027)),np.array((.132,.158,.079)),dust[...,None])
    strata = .47+.25*noise(x+y*.33,z*2.7,14,22)+.17*noise(x-y*.19,z*4.7,5.8,22)
    stone = mix(np.array((.046,.062,.072)),np.array((.249,.225,.195)),strata[...,None])
    tint = mix(soil,stone,steep[...,None])
    trail = mix(np.array((.104,.097,.072)),np.array((.238,.193,.131)),dust[...,None])
    tint = mix(tint,trail,path(x,y)[...,None])
    obj = grid(name,x,y,z,collection,materials["ground"],"heightfield")
    vertex_tint(obj,tint.reshape(-1,3),"TerrainTint")
    return obj


def mountains(x, y, ridges, baseline, seed):
    """Taper ridges away from the playable shelf and shape layered silhouettes."""
    wx = x+32*noise(x,y,105,seed)+9*noise(x,y,24,seed+1)
    wy = y+35*noise(x,y,139,seed+2)
    uplift = np.zeros_like(wx)
    for cx, cy, width, length, peak, lean in ridges:
        u=(wx-cx)+(wy-cy)*lean
        r=np.hypot(u/width,(wy-cy)/length)
        candidate=peak*(1-smooth(.02,1.52,r))**1.68
        uplift=np.maximum(uplift,candidate)
    channels = (1 - abs(noise(wx + wy * .51, wy * .58, 36, seed + 7))) ** 3
    sheets = noise(wx + wy * .33, wy * .37, 17, seed + 6)
    fluting = .75 + .22 * channels + .092 * sheets
    exposed = smooth(11, 88, uplift)
    chips = (1.3 + uplift * .068) * noise(x, y, 20, seed + 3)
    chips += (.8 + uplift * .030) * noise(x + y * .19, y, 7.9, seed + 4)
    return baseline + uplift * fluting + exposed * chips


def ground_at(ground, x, y):
    p,_,_,_ = ground.ray_cast(Vector((x,y,2200)),Vector((0,0,-1)),4000)
    require(p is not None,f"Ground is missing at {x},{y}")
    return p.z
