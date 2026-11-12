"""Materials shared by Qingyun and Jiange."""

from landscape import surface, surface_material


def fractured_stone(material, *, exposed_slopes_only=False):
    """Add irregular mineral joints and moss over the underlying stone grain."""
    nodes, links = material.node_tree.nodes, material.node_tree.links
    shader = nodes["Principled BSDF"]
    base = shader.inputs["Base Color"].links[0].from_socket
    normal = shader.inputs["Normal"].links[0].from_socket
    geometry = nodes.new("ShaderNodeNewGeometry")
    stretch = nodes.new("ShaderNodeVectorMath")
    stretch.operation = "MULTIPLY"
    stretch.inputs[1].default_value = (1, 1, .49)
    links.new(geometry.outputs["Position"], stretch.inputs[0])

    warp = nodes.new("ShaderNodeTexNoise")
    warp.inputs["Scale"].default_value = .62
    warp.inputs["Detail"].default_value = 3.5
    links.new(stretch.outputs[0], warp.inputs["Vector"])
    irregular = nodes.new("ShaderNodeVectorMath")
    irregular.operation = "SCALE"
    irregular.inputs["Scale"].default_value = .84
    links.new(warp.outputs["Color"], irregular.inputs[0])
    coords = nodes.new("ShaderNodeVectorMath")
    coords.operation = "ADD"
    links.new(stretch.outputs[0], coords.inputs[0])
    links.new(irregular.outputs[0], coords.inputs[1])
    joints = nodes.new("ShaderNodeTexVoronoi")
    joints.feature = "DISTANCE_TO_EDGE"
    joints.inputs["Scale"].default_value = .48
    links.new(coords.outputs[0], joints.inputs["Vector"])
    mineral = nodes.new("ShaderNodeValToRGB")
    mineral.color_ramp.elements[0].position = .012
    mineral.color_ramp.elements[0].color = (.48, .49, .48, 1)
    mineral.color_ramp.elements[1].position = .083
    mineral.color_ramp.elements[1].color = (1.09, 1.065, 1.025, 1)
    links.new(joints.outputs["Distance"], mineral.inputs["Fac"])
    multiply = nodes.new("ShaderNodeMixRGB")
    multiply.blend_type = "MULTIPLY"
    breaks = nodes.new("ShaderNodeValToRGB")
    breaks.color_ramp.elements[0].position = .40
    breaks.color_ramp.elements[1].position = .70
    links.new(warp.outputs["Fac"], breaks.inputs["Fac"])
    joint_mask = breaks.outputs[0]
    if exposed_slopes_only:
        normal_axis = nodes.new("ShaderNodeSeparateXYZ")
        links.new(geometry.outputs["Normal"], normal_axis.inputs[0])
        slope = nodes.new("ShaderNodeMapRange")
        slope.interpolation_type = "SMOOTHERSTEP"
        slope.inputs["From Min"].default_value = .41
        slope.inputs["From Max"].default_value = .83
        slope.inputs["To Min"].default_value = .74
        slope.inputs["To Max"].default_value = 0
        links.new(normal_axis.outputs["Z"], slope.inputs["Value"])
        gate = nodes.new("ShaderNodeMath")
        gate.operation = "MULTIPLY"
        links.new(slope.outputs["Result"], gate.inputs[0])
        links.new(joint_mask, gate.inputs[1])
        joint_mask = gate.outputs[0]
    links.new(joint_mask, multiply.inputs[0])
    links.new(base, multiply.inputs[1])
    links.new(mineral.outputs[0], multiply.inputs[2])

    weather = nodes.new("ShaderNodeValToRGB")
    weather.color_ramp.elements[0].position = .52
    weather.color_ramp.elements[0].color = (0, 0, 0, 1)
    weather.color_ramp.elements[1].position = .73
    weather.color_ramp.elements[1].color = (.51, .51, .51, 1)
    links.new(warp.outputs["Fac"], weather.inputs["Fac"])
    lichen = nodes.new("ShaderNodeMixRGB")
    lichen.inputs[2].default_value = (.112, .149, .061, 1)
    links.new(weather.outputs[0], lichen.inputs[0])
    links.new(multiply.outputs[0], lichen.inputs[1])
    links.new(lichen.outputs[0], shader.inputs["Base Color"])

    relief = nodes.new("ShaderNodeBump")
    links.new(joint_mask, relief.inputs["Strength"])
    relief.inputs["Distance"].default_value = .11
    links.new(mineral.outputs[0], relief.inputs["Height"])
    links.new(normal, relief.inputs["Normal"])
    links.new(relief.outputs["Normal"], shader.inputs["Normal"])


def material_set():
    result = {
        "ground":surface_material("Green and stone terrain",(.12,.15,.10),.84,1.9,.19,(1.2,1,2),"TerrainTint"),
        "cliff":surface_material("Weathered rock with mineral stains",(.14,.15,.15),.81,2.1,.24,(.91,.89,2.0),"RockTint"),
        "stone":surface_material("Limestone with tool marks",(.20,.22,.205),.81,6.4,.025,(1.1,.91,1.5)),
        "wood":surface_material("Timber with dark grain",(.175,.060,.031),.58,8.8,.025,(1.9,1.9,.24)),
        "oldwood":surface_material("Weathered pine rails",(.125,.081,.041),.74,5.9,.022,(2,2,.36)),
        "eave":surface_material("Glazed blue grey roof tile",(.041,.074,.098),.41,6.6,.022),
        "roof":surface_material("Hand split shale roof",(.065,.085,.081),.68,6.2,.030,(.86,.86,1.2)),
        "paper":surface("Oiled lantern paper",(.71,.34,.10),.47),
        "earth":surface_material("Damp soil in the beds",(.090,.058,.031),.91,15,.024),
        "bark":surface_material("Cleft pine bark",(.082,.054,.038),.85,8.0,.12,(1.7,1.7,.38)),
    }
    ink = result["paper"].node_tree.nodes["Principled BSDF"]
    ink.inputs["Emission Color"].default_value = (1,.39,.12,1)
    ink.inputs["Emission Strength"].default_value = 2.6
    for i, c in enumerate(((.026,.065,.039),(.052,.113,.060),(.100,.164,.077))):
        result[f"pine{i}"] = surface(f"Pine needles {i+1}",c,.82)
    result["flagstones"] = [surface_material(f"Granite slab {i+1}",c,.74,5.4,.022,(.88,.91,2.1))
                            for i,c in enumerate(((.182,.209,.219),(.243,.253,.244),(.159,.178,.176),(.194,.207,.172)))]
    fractured_stone(result["cliff"])
    fractured_stone(result["ground"], exposed_slopes_only=True)
    return result
