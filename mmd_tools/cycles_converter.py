# -*- coding: utf-8 -*-
# Copyright 2012 MMD Tools authors
# This file is part of MMD Tools.

from typing import Iterable, Optional

import bpy

from .core.shader import _NodeGroupUtils


def __switchToCyclesRenderEngine():
    if bpy.context.scene.render.engine != "CYCLES":
        bpy.context.scene.render.engine = "CYCLES"


def __exposeNodeTreeInput(in_socket, name, default_value, node_input, shader):
    _NodeGroupUtils(shader).new_input_socket(name, in_socket, default_value)


def __exposeNodeTreeOutput(out_socket, name, node_output, shader):
    _NodeGroupUtils(shader).new_output_socket(name, out_socket)


def __getMaterialOutput(nodes, bl_idname):
    o = next((n for n in nodes if n.bl_idname == bl_idname and n.is_active_output), None) or nodes.new(bl_idname)
    o.is_active_output = True
    return o


def create_MMDAlphaShader():
    __switchToCyclesRenderEngine()

    if "MMDAlphaShader" in bpy.data.node_groups:
        return bpy.data.node_groups["MMDAlphaShader"]

    shader = bpy.data.node_groups.new(name="MMDAlphaShader", type="ShaderNodeTree")

    node_input = shader.nodes.new("NodeGroupInput")
    node_output = shader.nodes.new("NodeGroupOutput")
    node_output.location.x += 250
    node_input.location.x -= 500

    trans = shader.nodes.new("ShaderNodeBsdfTransparent")
    trans.location.x -= 250
    trans.location.y += 150
    mix = shader.nodes.new("ShaderNodeMixShader")

    shader.links.new(mix.inputs[1], trans.outputs["BSDF"])

    __exposeNodeTreeInput(mix.inputs[2], "Shader", None, node_input, shader)
    __exposeNodeTreeInput(mix.inputs["Fac"], "Alpha", 1.0, node_input, shader)
    __exposeNodeTreeOutput(mix.outputs["Shader"], "Shader", node_output, shader)

    return shader


def create_MMDBasicShader():
    __switchToCyclesRenderEngine()

    if "MMDBasicShader" in bpy.data.node_groups:
        return bpy.data.node_groups["MMDBasicShader"]

    shader: bpy.types.ShaderNodeTree = bpy.data.node_groups.new(name="MMDBasicShader", type="ShaderNodeTree")

    node_input: bpy.types.NodeGroupInput = shader.nodes.new("NodeGroupInput")
    node_output: bpy.types.NodeGroupOutput = shader.nodes.new("NodeGroupOutput")
    node_output.location.x += 250
    node_input.location.x -= 500

    dif: bpy.types.ShaderNodeBsdfDiffuse = shader.nodes.new("ShaderNodeBsdfDiffuse")
    dif.location.x -= 250
    dif.location.y += 150
    glo: bpy.types.ShaderNodeBsdfAnisotropic = shader.nodes.new("ShaderNodeBsdfAnisotropic")
    glo.location.x -= 250
    glo.location.y -= 150
    mix: bpy.types.ShaderNodeMixShader = shader.nodes.new("ShaderNodeMixShader")
    shader.links.new(mix.inputs[1], dif.outputs["BSDF"])
    shader.links.new(mix.inputs[2], glo.outputs["BSDF"])

    __exposeNodeTreeInput(dif.inputs["Color"], "diffuse", [1.0, 1.0, 1.0, 1.0], node_input, shader)
    __exposeNodeTreeInput(glo.inputs["Color"], "glossy", [1.0, 1.0, 1.0, 1.0], node_input, shader)
    __exposeNodeTreeInput(glo.inputs["Roughness"], "glossy_rough", 0.0, node_input, shader)
    __exposeNodeTreeInput(mix.inputs["Fac"], "reflection", 0.02, node_input, shader)
    __exposeNodeTreeOutput(mix.outputs["Shader"], "shader", node_output, shader)

    return shader


def __enum_linked_nodes(node: bpy.types.Node) -> Iterable[bpy.types.Node]:
    yield node
    if node.parent:
        yield node.parent
    for n in set(l.from_node for i in node.inputs for l in i.links):
        yield from __enum_linked_nodes(n)


def __cleanNodeTree(material: bpy.types.Material):
    nodes = material.node_tree.nodes
    node_names = set(n.name for n in nodes)
    for o in (n for n in nodes if n.bl_idname in {"ShaderNodeOutput", "ShaderNodeOutputMaterial"}):
        if any(i.is_linked for i in o.inputs):
            node_names -= set(linked.name for linked in __enum_linked_nodes(o))
    for name in node_names:
        nodes.remove(nodes[name])


def convertToCyclesShader(obj: bpy.types.Object, use_principled=False, clean_nodes=False, subsurface=0.001):
    __switchToCyclesRenderEngine()
    convertToBlenderShader(obj, use_principled, clean_nodes, subsurface)


def convertToBlenderShader(obj: bpy.types.Object, use_principled=False, clean_nodes=False, subsurface=0.001):
    for i in obj.material_slots:
        if not i.material:
            continue
        if not i.material.use_nodes:
            i.material.use_nodes = True
            __convertToMMDBasicShader(i.material)
        if use_principled:
            __convertToPrincipledBsdf(i.material, subsurface)
        if clean_nodes:
            __cleanNodeTree(i.material)


def __convertToMMDBasicShader(material: bpy.types.Material):
    # TODO: test me
    mmd_basic_shader_grp = create_MMDBasicShader()
    mmd_alpha_shader_grp = create_MMDAlphaShader()

    if not any(filter(lambda x: isinstance(x, bpy.types.ShaderNodeGroup) and x.node_tree.name in {"MMDBasicShader", "MMDAlphaShader"}, material.node_tree.nodes)):
        # Add nodes for Cycles Render
        shader: bpy.types.ShaderNodeGroup = material.node_tree.nodes.new("ShaderNodeGroup")
        shader.node_tree = mmd_basic_shader_grp
        shader.inputs[0].default_value[:3] = material.diffuse_color[:3]
        shader.inputs[1].default_value[:3] = material.specular_color[:3]
        shader.inputs["glossy_rough"].default_value = 1.0 / getattr(material, "specular_hardness", 50)
        outplug = shader.outputs[0]

        location = shader.location.copy()
        location.x -= 1000

        alpha_value = 1.0
        if len(material.diffuse_color) > 3:
            alpha_value = material.diffuse_color[3]

        if alpha_value < 1.0:
            alpha_shader: bpy.types.ShaderNodeGroup = material.node_tree.nodes.new("ShaderNodeGroup")
            alpha_shader.location.x = shader.location.x + 250
            alpha_shader.location.y = shader.location.y - 150
            alpha_shader.node_tree = mmd_alpha_shader_grp
            alpha_shader.inputs[1].default_value = alpha_value
            material.node_tree.links.new(alpha_shader.inputs[0], outplug)
            outplug = alpha_shader.outputs[0]

        material_output: bpy.types.ShaderNodeOutputMaterial = __getMaterialOutput(material.node_tree.nodes, "ShaderNodeOutputMaterial")
        material.node_tree.links.new(material_output.inputs["Surface"], outplug)
        material_output.location.x = shader.location.x + 500
        material_output.location.y = shader.location.y - 150


def __convertToPrincipledBsdf(material: bpy.types.Material, subsurface: float):
    node_names = set()
    for s in (n for n in material.node_tree.nodes if isinstance(n, bpy.types.ShaderNodeGroup)):
        if s.node_tree.name == "MMDBasicShader":
            l: bpy.types.NodeLink
            for l in s.outputs[0].links:
                to_node = l.to_node
                # assuming there is no bpy.types.NodeReroute between MMDBasicShader and MMDAlphaShader
                if isinstance(to_node, bpy.types.ShaderNodeGroup) and to_node.node_tree.name == "MMDAlphaShader":
                    __switchToPrincipledBsdf(material.node_tree, s, subsurface, node_alpha=to_node)
                    node_names.add(to_node.name)
                else:
                    __switchToPrincipledBsdf(material.node_tree, s, subsurface)
            node_names.add(s.name)
        elif s.node_tree.name == "MMDShaderDev":
            __switchToPrincipledBsdf(material.node_tree, s, subsurface)
            node_names.add(s.name)
    # remove MMD shader nodes
    nodes = material.node_tree.nodes
    for name in node_names:
        nodes.remove(nodes[name])


def __switchToPrincipledBsdf(node_tree: bpy.types.NodeTree, node_basic: bpy.types.ShaderNodeGroup, subsurface: float, node_alpha: Optional[bpy.types.ShaderNodeGroup] = None):
    shader: bpy.types.ShaderNodeBsdfPrincipled = node_tree.nodes.new("ShaderNodeBsdfPrincipled")
    shader.parent = node_basic.parent
    shader.location.x = node_basic.location.x
    shader.location.y = node_basic.location.y

    alpha_socket_name = "Alpha"
    if node_basic.node_tree.name == "MMDShaderDev":
        node_alpha, alpha_socket_name = node_basic, "Base Alpha"
        if "Base Tex" in node_basic.inputs and node_basic.inputs["Base Tex"].is_linked:
            node_tree.links.new(node_basic.inputs["Base Tex"].links[0].from_socket, shader.inputs["Base Color"])
        elif "Diffuse Color" in node_basic.inputs:
            shader.inputs["Base Color"].default_value[:3] = node_basic.inputs["Diffuse Color"].default_value[:3]
    elif "diffuse" in node_basic.inputs:
        shader.inputs["Base Color"].default_value[:3] = node_basic.inputs["diffuse"].default_value[:3]
        if node_basic.inputs["diffuse"].is_linked:
            node_tree.links.new(node_basic.inputs["diffuse"].links[0].from_socket, shader.inputs["Base Color"])

    shader.inputs["IOR"].default_value = 1.0
    shader.inputs["Subsurface Weight"].default_value = subsurface

    output_links = node_basic.outputs[0].links
    if node_alpha:
        output_links = node_alpha.outputs[0].links
        shader.parent = node_alpha.parent or shader.parent
        shader.location.x = node_alpha.location.x

        if alpha_socket_name in node_alpha.inputs:
            if "Alpha" in shader.inputs:
                shader.inputs["Alpha"].default_value = node_alpha.inputs[alpha_socket_name].default_value
                if node_alpha.inputs[alpha_socket_name].is_linked:
                    node_tree.links.new(node_alpha.inputs[alpha_socket_name].links[0].from_socket, shader.inputs["Alpha"])
            else:
                shader.inputs["Transmission"].default_value = 1 - node_alpha.inputs[alpha_socket_name].default_value
                if node_alpha.inputs[alpha_socket_name].is_linked:
                    node_invert = node_tree.nodes.new("ShaderNodeMath")
                    node_invert.parent = shader.parent
                    node_invert.location.x = node_alpha.location.x - 250
                    node_invert.location.y = node_alpha.location.y - 300
                    node_invert.operation = "SUBTRACT"
                    node_invert.use_clamp = True
                    node_invert.inputs[0].default_value = 1
                    node_tree.links.new(node_alpha.inputs[alpha_socket_name].links[0].from_socket, node_invert.inputs[1])
                    node_tree.links.new(node_invert.outputs[0], shader.inputs["Transmission"])

    for l in output_links:
        node_tree.links.new(shader.outputs[0], l.to_socket)
