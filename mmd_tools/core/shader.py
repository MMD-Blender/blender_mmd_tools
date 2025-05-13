# Copyright 2019 MMD Tools authors
# This file is part of MMD Tools.

from typing import Optional, Tuple, cast

import bpy


class _NodeTreeUtils:
    def __init__(self, shader: bpy.types.ShaderNodeTree):
        self.shader = shader
        self.nodes: bpy.types.bpy_prop_collection[bpy.types.ShaderNode] = shader.nodes  # type: ignore
        self.links = shader.links

    def _find_node(self, node_type: str) -> Optional[bpy.types.ShaderNode]:
        return next((n for n in self.nodes if n.bl_idname == node_type), None)

    def new_node(self, idname: str, pos: Tuple[int, int]) -> bpy.types.ShaderNode:
        node: bpy.types.ShaderNode = self.nodes.new(idname)
        node.location = (pos[0] * 210, pos[1] * 220)
        return node

    def new_math_node(self, operation, pos, value1=None, value2=None):
        node = self.new_node("ShaderNodeMath", pos)
        node.operation = operation
        if value1 is not None:
            node.inputs[0].default_value = value1
        if value2 is not None:
            node.inputs[1].default_value = value2
        return node

    def new_vector_math_node(self, operation, pos, vector1=None, vector2=None):
        node = self.new_node("ShaderNodeVectorMath", pos)
        node.operation = operation
        if vector1 is not None:
            node.inputs[0].default_value = vector1
        if vector2 is not None:
            node.inputs[1].default_value = vector2
        return node

    def new_mix_node(self, blend_type, pos, fac=None, color1=None, color2=None):
        node = self.new_node("ShaderNodeMixRGB", pos)
        node.blend_type = blend_type
        if fac is not None:
            node.inputs["Fac"].default_value = fac
        if color1 is not None:
            node.inputs["Color1"].default_value = color1
        if color2 is not None:
            node.inputs["Color2"].default_value = color2
        return node


SOCKET_TYPE_MAPPING = {"NodeSocketFloatFactor": "NodeSocketFloat"}

SOCKET_SUBTYPE_MAPPING = {"NodeSocketFloatFactor": "FACTOR"}


class _NodeGroupUtils(_NodeTreeUtils):
    def __init__(self, shader: bpy.types.ShaderNodeTree):
        super().__init__(shader)
        self.__node_input: Optional[bpy.types.NodeGroupInput] = None
        self.__node_output: Optional[bpy.types.NodeGroupOutput] = None

    @property
    def node_input(self) -> bpy.types.NodeGroupInput:
        if not self.__node_input:
            self.__node_input = cast(bpy.types.NodeGroupInput, self._find_node("NodeGroupInput") or self.new_node("NodeGroupInput", (-2, 0)))
        return self.__node_input

    @property
    def node_output(self) -> bpy.types.NodeGroupOutput:
        if not self.__node_output:
            self.__node_output = cast(bpy.types.NodeGroupOutput, self._find_node("NodeGroupOutput") or self.new_node("NodeGroupOutput", (2, 0)))
        return self.__node_output

    def hide_nodes(self, hide_sockets=True):
        skip_nodes = {self.__node_input, self.__node_output}
        for n in (x for x in self.nodes if x not in skip_nodes):
            n.hide = True
            if not hide_sockets:
                continue
            for s in n.inputs:
                s.hide = not s.is_linked
            for s in n.outputs:
                s.hide = not s.is_linked

    def new_input_socket(self, io_name, socket, default_val=None, min_max=None, socket_type=None):
        self.__new_io("INPUT", self.node_input.outputs, io_name, socket, default_val, min_max, socket_type)

    def new_output_socket(self, io_name, socket, default_val=None, min_max=None, socket_type=None):
        self.__new_io("OUTPUT", self.node_output.inputs, io_name, socket, default_val, min_max, socket_type)

    def __new_io(self, in_out, io_sockets, io_name, socket, default_val=None, min_max=None, socket_type=None):
        if io_name not in io_sockets:
            idname = socket_type or socket.bl_idname
            interface_socket = self.shader.interface.new_socket(name=io_name, in_out=in_out, socket_type=SOCKET_TYPE_MAPPING.get(idname, idname))
            if idname in SOCKET_SUBTYPE_MAPPING:
                interface_socket.subtype = SOCKET_SUBTYPE_MAPPING.get(idname, "")
            if not min_max:
                if idname.endswith("Factor") or io_name.endswith("Alpha"):
                    interface_socket.min_value, interface_socket.max_value = 0, 1
                elif idname.endswith("Float") or idname.endswith("Vector"):
                    interface_socket.min_value, interface_socket.max_value = -10, 10
        if socket is not None:
            self.links.new(io_sockets[io_name], socket)
        if default_val is not None:
            interface_socket.default_value = default_val
        if min_max is not None:
            interface_socket.min_value, interface_socket.max_value = min_max


class _MaterialMorph:
    @classmethod
    def update_morph_inputs(cls, material, morph):
        if material and material.node_tree and morph.name in material.node_tree.nodes:
            cls.__update_node_inputs(material.node_tree.nodes[morph.name], morph)
            cls.update_morph_inputs(bpy.data.materials.get("mmd_edge." + material.name, None), morph)

    @classmethod
    def setup_morph_nodes(cls, material, morphs):
        node, nodes = None, []
        for m in morphs:
            node = cls.__morph_node_add(material, m, node)
            nodes.append(node)
        if node:
            node = cls.__morph_node_add(material, None, node) or node
            for n in reversed(nodes):
                n.location += node.location
                if n.node_tree.name != node.node_tree.name:
                    n.location.x -= 100
                if node.name.startswith("mmd_"):
                    n.location.y += 1500
                node = n
        return nodes

    @classmethod
    def reset_morph_links(cls, node):
        cls.__update_morph_links(node, reset=True)

    @classmethod
    def __update_morph_links(cls, node, reset=False):
        nodes, links = node.id_data.nodes, node.id_data.links
        if reset:
            if any(l.from_node.name.startswith("mmd_bind") for i in node.inputs for l in i.links):
                return

            def __init_link(socket_morph, socket_shader):
                if socket_shader and socket_morph.is_linked:
                    links.new(socket_morph.links[0].from_socket, socket_shader)

        else:

            def __init_link(socket_morph, socket_shader):
                if socket_shader:
                    if socket_shader.is_linked:
                        links.new(socket_shader.links[0].from_socket, socket_morph)
                    if socket_morph.type == "VALUE":
                        socket_morph.default_value = socket_shader.default_value
                    else:
                        socket_morph.default_value[:3] = socket_shader.default_value[:3]

        shader = nodes.get("mmd_shader", None)
        if shader:
            __init_link(node.inputs["Ambient1"], shader.inputs.get("Ambient Color"))
            __init_link(node.inputs["Diffuse1"], shader.inputs.get("Diffuse Color"))
            __init_link(node.inputs["Specular1"], shader.inputs.get("Specular Color"))
            __init_link(node.inputs["Reflect1"], shader.inputs.get("Reflect"))
            __init_link(node.inputs["Alpha1"], shader.inputs.get("Alpha"))
            __init_link(node.inputs["Base1 RGB"], shader.inputs.get("Base Tex"))
            __init_link(node.inputs["Toon1 RGB"], shader.inputs.get("Toon Tex"))  # FIXME toon only affect shadow color
            __init_link(node.inputs["Sphere1 RGB"], shader.inputs.get("Sphere Tex"))
        elif "mmd_edge_preview" in nodes:
            shader = nodes["mmd_edge_preview"]
            __init_link(node.inputs["Edge1 RGB"], shader.inputs["Color"])
            __init_link(node.inputs["Edge1 A"], shader.inputs["Alpha"])

    @classmethod
    def __update_node_inputs(cls, node, morph):
        node.inputs["Ambient2"].default_value[:3] = morph.ambient_color[:3]
        node.inputs["Diffuse2"].default_value[:3] = morph.diffuse_color[:3]
        node.inputs["Specular2"].default_value[:3] = morph.specular_color[:3]
        node.inputs["Reflect2"].default_value = morph.shininess
        node.inputs["Alpha2"].default_value = morph.diffuse_color[3]

        node.inputs["Edge2 RGB"].default_value[:3] = morph.edge_color[:3]
        node.inputs["Edge2 A"].default_value = morph.edge_color[3]

        node.inputs["Base2 RGB"].default_value[:3] = morph.texture_factor[:3]
        node.inputs["Base2 A"].default_value = morph.texture_factor[3]
        node.inputs["Toon2 RGB"].default_value[:3] = morph.toon_texture_factor[:3]
        node.inputs["Toon2 A"].default_value = morph.toon_texture_factor[3]
        node.inputs["Sphere2 RGB"].default_value[:3] = morph.sphere_texture_factor[:3]
        node.inputs["Sphere2 A"].default_value = morph.sphere_texture_factor[3]

    @classmethod
    def __morph_node_add(cls, material, morph, prev_node):
        nodes, links = material.node_tree.nodes, material.node_tree.links

        shader = nodes.get("mmd_shader", None)
        if morph:
            node = nodes.new("ShaderNodeGroup")
            node.parent = getattr(shader, "parent", None)
            node.location = (-250, 0)
            node.node_tree = cls.__get_shader("Add" if morph.offset_type == "ADD" else "Mul")
            cls.__update_node_inputs(node, morph)
            if prev_node:
                for id_name in ("Ambient", "Diffuse", "Specular", "Reflect", "Alpha"):
                    links.new(prev_node.outputs[id_name], node.inputs[id_name + "1"])
                for id_name in ("Edge", "Base", "Toon", "Sphere"):
                    links.new(prev_node.outputs[id_name + " RGB"], node.inputs[id_name + "1 RGB"])
                    links.new(prev_node.outputs[id_name + " A"], node.inputs[id_name + "1 A"])
            else:  # initial first node
                if node.node_tree.name.endswith("Add"):
                    node.inputs["Base1 A"].default_value = 1
                    node.inputs["Toon1 A"].default_value = 1
                    node.inputs["Sphere1 A"].default_value = 1
                cls.__update_morph_links(node)
            return node
        # connect last node to shader
        if shader:

            def __soft_link(socket_out, socket_in):
                if socket_out and socket_in:
                    links.new(socket_out, socket_in)

            __soft_link(prev_node.outputs["Ambient"], shader.inputs.get("Ambient Color"))
            __soft_link(prev_node.outputs["Diffuse"], shader.inputs.get("Diffuse Color"))
            __soft_link(prev_node.outputs["Specular"], shader.inputs.get("Specular Color"))
            __soft_link(prev_node.outputs["Reflect"], shader.inputs.get("Reflect"))
            __soft_link(prev_node.outputs["Alpha"], shader.inputs.get("Alpha"))
            __soft_link(prev_node.outputs["Base Tex"], shader.inputs.get("Base Tex"))
            __soft_link(prev_node.outputs["Toon Tex"], shader.inputs.get("Toon Tex"))
            if int(material.mmd_material.sphere_texture_type) != 2:  # shader.inputs['Sphere Mul/Add'].default_value < 0.5
                __soft_link(prev_node.outputs["Sphere Tex"], shader.inputs.get("Sphere Tex"))
            else:
                __soft_link(prev_node.outputs["Sphere Tex Add"], shader.inputs.get("Sphere Tex"))
        elif "mmd_edge_preview" in nodes:
            shader = nodes["mmd_edge_preview"]
            links.new(prev_node.outputs["Edge RGB"], shader.inputs["Color"])
            links.new(prev_node.outputs["Edge A"], shader.inputs["Alpha"])
        return shader

    @classmethod
    def __get_shader(cls, morph_type):
        group_name = "MMDMorph" + morph_type
        shader = bpy.data.node_groups.get(group_name, None) or bpy.data.node_groups.new(name=group_name, type="ShaderNodeTree")
        if len(shader.nodes):
            return shader

        ng = _NodeGroupUtils(shader)
        links = ng.links

        use_mul = morph_type == "Mul"

        ############################################################################
        node_input = ng.new_node("NodeGroupInput", (-3, 0))
        ng.new_input_socket("Fac", None, 0, socket_type="NodeSocketFloat")
        ng.new_node("NodeGroupOutput", (3, 0))

        def __blend_color_add(id_name, pos, tag=""):
            # MA_RAMP_MULT: ColorMul = Color1 * (Fac * Color2 + (1 - Fac))
            # MA_RAMP_ADD:  ColorAdd = Color1 + Fac * Color2
            # https://github.com/blender/blender/blob/594f47ecd2d5367ca936cf6fc6ec8168c2b360d0/source/blender/blenkernel/intern/material.c#L1400
            node_mix = ng.new_mix_node("MULTIPLY" if use_mul else "ADD", (pos[0] + 1, pos[1]))
            links.new(node_input.outputs["Fac"], node_mix.inputs["Fac"])
            ng.new_input_socket("%s1" % id_name + tag, node_mix.inputs["Color1"])
            ng.new_input_socket("%s2" % id_name + tag, node_mix.inputs["Color2"], socket_type="NodeSocketVector")
            ng.new_output_socket(id_name + tag, node_mix.outputs["Color"])
            return node_mix

        def __blend_tex_color(id_name, pos, node_tex_rgb, node_tex_a_output):
            # Tex Color = tex_rgb * tex_a + (1 - tex_a)
            # : tex_rgb = TexRGB * ColorMul + ColorAdd
            # : tex_a = TexA * ValueMul + ValueAdd
            if id_name != "Sphere":
                node_mix = ng.new_mix_node("MULTIPLY", pos, color1=(1, 1, 1, 1))
                links.new(node_tex_a_output, node_mix.inputs[0])
                links.new(node_tex_rgb.outputs["Color"], node_mix.inputs[2])
                ng.new_output_socket(id_name + " Tex", node_mix.outputs[0])
            else:
                node_inv = ng.new_math_node("SUBTRACT", (pos[0], pos[1] - 0.25), value1=1.0)
                node_scale = ng.new_vector_math_node("SCALE", (pos[0], pos[1]))
                node_add = ng.new_vector_math_node("ADD", (pos[0] + 1, pos[1]))

                links.new(node_tex_a_output, node_inv.inputs[1])
                links.new(node_tex_rgb.outputs["Color"], node_scale.inputs[0])
                links.new(node_tex_a_output, node_scale.inputs["Scale"])
                links.new(node_scale.outputs[0], node_add.inputs[0])
                links.new(node_inv.outputs[0], node_add.inputs[1])

                ng.new_output_socket(id_name + " Tex", node_add.outputs[0], socket_type="NodeSocketColor")
                ng.new_output_socket(id_name + " Tex Add", node_scale.outputs[0], socket_type="NodeSocketColor")

        def __add_sockets(id_name, input1, input2, output, tag=""):
            ng.new_input_socket(f"{id_name}1{tag}", input1, use_mul)
            ng.new_input_socket(f"{id_name}2{tag}", input2, use_mul)
            ng.new_output_socket(f"{id_name}{tag}", output)

        pos_x = -2
        __blend_color_add("Ambient", (pos_x, +0.5))
        __blend_color_add("Diffuse", (pos_x, +0.0))
        __blend_color_add("Specular", (pos_x, -0.5))

        combine_reflect1_alpha1_edge1 = ng.new_node("ShaderNodeCombineRGB", (-2, -1.5))
        combine_reflect2_alpha2_edge2 = ng.new_node("ShaderNodeCombineRGB", (-2, -1.75))
        separate_reflect_alpha_edge = ng.new_node("ShaderNodeSeparateRGB", (pos_x + 2, -1.5))

        __add_sockets("Reflect", combine_reflect1_alpha1_edge1.inputs[0], combine_reflect2_alpha2_edge2.inputs[0], separate_reflect_alpha_edge.outputs[0])
        __add_sockets("Alpha", combine_reflect1_alpha1_edge1.inputs[1], combine_reflect2_alpha2_edge2.inputs[1], separate_reflect_alpha_edge.outputs[1])

        __blend_color_add("Edge", (pos_x, -1.0), " RGB")
        __add_sockets("Edge", combine_reflect1_alpha1_edge1.inputs[2], combine_reflect2_alpha2_edge2.inputs[2], separate_reflect_alpha_edge.outputs[2], tag=" A")

        node_mix = ng.new_mix_node("MULTIPLY" if use_mul else "ADD", (pos_x + 1, -1.5))
        links.new(node_input.outputs["Fac"], node_mix.inputs[0])
        links.new(combine_reflect1_alpha1_edge1.outputs[0], node_mix.inputs[1])
        links.new(combine_reflect2_alpha2_edge2.outputs[0], node_mix.inputs[2])
        links.new(node_mix.outputs[0], separate_reflect_alpha_edge.inputs[0])

        combine_base1a_toon1a_sphere1a = ng.new_node("ShaderNodeCombineRGB", (-2, -2.0))
        combine_base2a_toon2a_sphere2a = ng.new_node("ShaderNodeCombineRGB", (-2, -2.25))
        separate_basea_toona_spherea = ng.new_node("ShaderNodeSeparateRGB", (pos_x + 2, -2.0))

        node_mix = ng.new_mix_node("MULTIPLY" if use_mul else "ADD", (pos_x + 1, -2.0))
        links.new(node_input.outputs["Fac"], node_mix.inputs[0])
        links.new(combine_base1a_toon1a_sphere1a.outputs[0], node_mix.inputs[1])
        links.new(combine_base2a_toon2a_sphere2a.outputs[0], node_mix.inputs[2])
        links.new(node_mix.outputs[0], separate_basea_toona_spherea.inputs[0])

        base_rgb = __blend_color_add("Base", (pos_x, -2.5), " RGB")
        __add_sockets("Base", combine_base1a_toon1a_sphere1a.inputs[0], combine_base2a_toon2a_sphere2a.inputs[0], separate_basea_toona_spherea.outputs[0], tag=" A")
        __blend_tex_color("Base", (pos_x + 3, -2.5), base_rgb, separate_basea_toona_spherea.outputs[0])

        toon_rgb = __blend_color_add("Toon", (pos_x, -3.0), " RGB")
        __add_sockets("Toon", combine_base1a_toon1a_sphere1a.inputs[1], combine_base2a_toon2a_sphere2a.inputs[1], separate_basea_toona_spherea.outputs[1], tag=" A")
        __blend_tex_color("Toon", (pos_x + 3, -3.0), toon_rgb, separate_basea_toona_spherea.outputs[1])

        sphere_rgb = __blend_color_add("Sphere", (pos_x, -3.5), " RGB")
        __add_sockets("Sphere", combine_base1a_toon1a_sphere1a.inputs[2], combine_base2a_toon2a_sphere2a.inputs[2], separate_basea_toona_spherea.outputs[2], tag=" A")
        __blend_tex_color("Sphere", (pos_x + 3, -3.5), sphere_rgb, separate_basea_toona_spherea.outputs[2])

        ng.hide_nodes()
        return ng.shader
