"""Reversible photo-constrained face shape and visible colour transfer."""

import bpy
import numpy as np

from portrait_source import PHOTO
from refine_portrait import attr, attribute, bell, color_mix, eyes, require, smooth
from build_portrait import shape_positions

PLATE="Original_reference_uv"
SKIN_MASK="Visible_ref_color"
EYE_MASK="Visible_ref_eye"
LID_TONE="Eye_rim_tone_weight"
CHEEK_TONE = "Cheek colour weight"
LIP_SHEEN = "Lip sheen weight"


def oval(x,y,xc,yc,a,b,inner=.51):
    return 1-smooth(inner,1,np.hypot((x-xc)/a,(y-yc)/b))


def face_shape(head,photo):
    keys=head.data.shape_keys.key_blocks
    require(len(keys)==3 and keys[-1].value==1,"Expected the last reviewed head geometry")
    previous=keys[-1]
    before=shape_positions(previous)
    uv=photo.to_pixels(before,head)
    x,y,depth=uv.T
    visible=smooth(-3.00,-2.862,depth)
    inner=smooth(-2.83,-2.73,depth)
    # Shrink the full cross-section gradually. Pinching only its visible sides
    # makes the plane below the mouth fold even when the silhouette gets closer.
    contraction=smooth(420,484,y)*(1-smooth(492,529,y))
    axis=436.3+.095*np.maximum(y-443,0)
    jaw=(axis-x)*.197*contraction-1.5*smooth(421,450,y)*(1-smooth(483,515,y))
    eyel=oval(x,y,378,350,47,32,.59)*inner
    eyer=oval(x,y,488,331,51,31,.62)*inner
    dx=jaw+eyel*(-2.33-.033*(x-378))+4.55*eyer
    dy=eyel*(-1.13-.037*(y-350))+eyer*(-1.48+4.18*smooth(492,515,x)-.063*(y-331))
    nose=bell(uv[:,:2],(451,398),(26,29))*inner
    sides=(bell(uv[:,:2],(428,402),(26,23))+bell(uv[:,:2],(465,400),(23,25)))*inner
    lip=bell(uv[:,:2],(449,445),(39,23))*inner
    chin=oval(x,y,449,486,56,30)*visible
    dy+=-1.3*nose-.77*lip-1.3*chin
    depth_delta=.0021*nose-.0030*sides+.0013*lip-.0019*chin
    camera_delta=np.column_stack((dx/photo.scale,-dy/photo.scale,depth_delta))
    local=camera_delta@np.array((head.matrix_world.inverted()@photo.matrix).to_3x3()).T
    detail=head.shape_key_add(name="Original photo • eye position and tapered jaw",from_mix=False)
    detail.relative_key=previous
    after=np.ascontiguousarray(before+local,dtype=np.float32)
    detail.data.foreach_set("co",after.ravel())
    detail.value=1
    print("FACE_SCULPT",float(np.linalg.norm(local,axis=1).max()),int(np.sum(np.linalg.norm(local,axis=1)>.001)),flush=True)
    return photo.to_pixels(after,head)


def reference_color(head, pixels):
    image=bpy.data.images.load(str(PHOTO),check_existing=False)
    image.name="Original identity crop • 780 × 640"
    require(tuple(image.size)==(780,640),"Reference dimensions changed")
    image.pack()
    x,y,depth=pixels.T
    fit_iris(head, x, y)
    uv=np.column_stack(((x+.35)/780,1-(y+.35)/640,np.zeros(len(x))))
    attr(head.data,PLATE,"FLOAT_VECTOR",uv,"vector")
    visible=smooth(-2.95,-2.728,depth)
    oval_face=oval(x,y,436,404,105,106,.56)*smooth(302,349,y)*(1-smooth(472,501,y))
    eye_left=oval(x,y,378,349,34,25,.43)
    eye_right=oval(x,y,484,329,34,24,.43)
    lip=oval(x,y,449,439,48,21,.63)
    nostril=oval(x,y,452,400,33,25,.5)
    left=np.interp(y,(315,359,420,442,475,499),(335,340,346,354,388,446))
    right=np.interp(y,(315,359,420,445,479,499),(521,530,524,515,486,455))
    margin=smooth(left+3,left+15,x)*(1-smooth(right-13,right-3,x))
    patch=(.47*oval_face*margin+.38*np.maximum(eye_left,eye_right)+.37*lip)*(1-.46*nostril)
    attr(head.data,SKIN_MASK,"FLOAT",np.clip(patch*visible,.0,.87),"value")
    attr(head.data,EYE_MASK,"FLOAT",.40*smooth(-2.86,-2.74,depth),"value")
    lid_tone=np.maximum(oval(x,y,379,352,39,17),oval(x,y,484,333,38,17))*visible
    attr(head.data,LID_TONE,"FLOAT",lid_tone,"value")
    cheeks = np.maximum(oval(x, y, 381, 391, 44, 35), oval(x, y, 502, 373, 36, 33))
    attr(head.data, CHEEK_TONE, "FLOAT", .18 * cheeks * visible, "value")
    attr(head.data, LIP_SHEEN, "FLOAT", .68 * oval(x, y, 449, 442, 37, 13) * visible, "value")
    for index,mask_attr in ((0,SKIN_MASK),(1,EYE_MASK)):
        material=head.data.materials[index]
        nodes,links=material.node_tree.nodes,material.node_tree.links
        bsdf=nodes.get("Principled BSDF")
        socket=bsdf.inputs["Base Color"]
        previous=socket.links[0].from_socket
        coordinates=attribute(nodes,PLATE)["Vector"]
        photo_node=nodes.new("ShaderNodeTexImage")
        photo_node.image=image
        photo_node.interpolation="Cubic"
        photo_node.extension="CLIP"
        links.new(coordinates,photo_node.inputs["Vector"])
        color=photo_node.outputs["Color"]
        luma=nodes.new("ShaderNodeRGBToBW")
        links.new(color,luma.inputs[0])
        gain=nodes.new("ShaderNodeMapRange")
        gain.interpolation_type="SMOOTHERSTEP"
        gain.inputs["From Min"].default_value=.14
        gain.inputs["From Max"].default_value=.68
        gain.inputs["To Min"].default_value=1.14 if index==0 else 1.07
        gain.inputs["To Max"].default_value=.78 if index==0 else .76
        links.new(luma.outputs[0],gain.inputs["Value"])
        toned=nodes.new("ShaderNodeVectorMath")
        toned.operation="SCALE"
        links.new(color,toned.inputs[0])
        links.new(gain.outputs["Result"],toned.inputs["Scale"])
        weight=attribute(nodes,mask_attr)["Fac"]
        mixed=color_mix(nodes,links,previous,toned.outputs[0],weight)
        if index==0:
            neutral=nodes.new("ShaderNodeHueSaturation")
            neutral.inputs["Saturation"].default_value=.53
            links.new(attribute(nodes,LID_TONE)["Fac"],neutral.inputs["Fac"])
            links.new(mixed,neutral.inputs["Color"])
            mixed = color_mix(nodes, links, neutral.outputs[0], (.43, .217, .177, 1),
                              attribute(nodes, CHEEK_TONE)["Fac"])
        links.new(mixed,socket)
        if index==1:
            bsdf.inputs["Roughness"].default_value = .20
            bsdf.inputs["Specular IOR Level"].default_value = .31
            bsdf.inputs["Coat Weight"].default_value = .15
            bsdf.inputs["Coat Roughness"].default_value = .135
        else:
            skin_response(nodes, links, bsdf)
    return image


def fit_iris(head, x, y):
    """Recenter the existing radial iris shader on the observed pupils."""
    right_eye = x > 432
    iris = np.zeros((len(x), 3), dtype=np.float32)
    iris[:, 0] = (x - np.where(right_eye, 484, 380)) / 14.8
    iris[:, 1] = (y - np.where(right_eye, 328, 346)) / 15.4
    head.data.attributes["Iris_Plane"].data.foreach_set("vector", iris.ravel())
    eyes(head)


def skin_response(nodes, links, shader):
    """Keep pores, surface oil, and lip sheen in the lit material."""
    shader.inputs["Subsurface Weight"].default_value = .092
    shader.inputs["Subsurface Scale"].default_value = .011
    shader.inputs["Specular IOR Level"].default_value = .32
    coordinates = nodes.new("ShaderNodeTexCoord")
    pores = nodes.new("ShaderNodeTexNoise")
    pores.label = "Fine skin relief"
    pores.inputs["Scale"].default_value = 395
    pores.inputs["Detail"].default_value = 2.2
    links.new(coordinates.outputs["Object"], pores.inputs["Vector"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value = .00047
    bump.inputs["Strength"].default_value = .27
    links.new(pores.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])

    oil = nodes.new("ShaderNodeTexNoise")
    oil.label = "Broad roughness variation"
    oil.inputs["Scale"].default_value = 27
    links.new(coordinates.outputs["Object"], oil.inputs["Vector"])
    roughness = nodes.new("ShaderNodeMapRange")
    roughness.inputs["To Min"].default_value = .44
    roughness.inputs["To Max"].default_value = .59
    links.new(oil.outputs["Fac"], roughness.inputs["Value"])
    lips = nodes.new("ShaderNodeMix")
    lips.data_type = "FLOAT"
    links.new(attribute(nodes, LIP_SHEEN)["Fac"], lips.inputs[0])
    links.new(roughness.outputs["Result"], lips.inputs[2])
    lips.inputs[3].default_value = .31
    links.new(lips.outputs[0], shader.inputs["Roughness"])
