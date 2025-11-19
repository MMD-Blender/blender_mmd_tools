# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

from collections import defaultdict

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator

from .. import cycles_converter
from ..core.exceptions import MaterialNotFoundError
from ..core.material import FnMaterial
from ..core.shader import _NodeGroupUtils


class ConvertMaterialsForCycles(Operator):
    bl_idname = "mmd_tools.convert_materials_for_cycles"
    bl_label = "Convert Materials For Cycles"
    bl_description = "Convert materials of selected objects for Cycles."
    bl_options = {"REGISTER", "UNDO"}

    use_principled: bpy.props.BoolProperty(
        name="Convert to Principled BSDF",
        description="Convert MMD shader nodes to Principled BSDF as well if enabled",
        default=False,
        options={"SKIP_SAVE"},
    )

    clean_nodes: bpy.props.BoolProperty(
        name="Clean Nodes",
        description="Remove redundant nodes as well if enabled. Disable it to keep node data.",
        default=False,
        options={"SKIP_SAVE"},
    )

    @classmethod
    def poll(cls, context):
        return any(x.type == "MESH" for x in context.selected_objects)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "use_principled")
        layout.prop(self, "clean_nodes")

    def execute(self, context):
        try:
            context.scene.render.engine = "CYCLES"
        except Exception:
            self.report({"ERROR"}, " * Failed to change to Cycles render engine.")
            return {"CANCELLED"}
        for obj in (x for x in context.selected_objects if x.type == "MESH"):
            cycles_converter.convertToCyclesShader(obj, use_principled=self.use_principled, clean_nodes=self.clean_nodes)
        return {"FINISHED"}


class ConvertMaterials(Operator):
    bl_idname = "mmd_tools.convert_materials"
    bl_label = "Convert Materials"
    bl_description = "Convert materials of selected objects."
    bl_options = {"REGISTER", "UNDO"}

    use_principled: bpy.props.BoolProperty(
        name="Convert to Principled BSDF",
        description="Convert MMD shader nodes to Principled BSDF as well if enabled",
        default=True,
        options={"SKIP_SAVE"},
    )

    clean_nodes: bpy.props.BoolProperty(
        name="Clean Nodes",
        description="Remove redundant nodes as well if enabled. Disable it to keep node data.",
        default=True,
        options={"SKIP_SAVE"},
    )

    subsurface: bpy.props.FloatProperty(
        name="Subsurface",
        default=0.001,
        soft_min=0.000,
        soft_max=1.000,
        precision=3,
        options={"SKIP_SAVE"},
    )

    @classmethod
    def poll(cls, context):
        return any(x.type == "MESH" for x in context.selected_objects)

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type != "MESH":
                continue
            cycles_converter.convertToBlenderShader(obj, use_principled=self.use_principled, clean_nodes=self.clean_nodes, subsurface=self.subsurface)
        return {"FINISHED"}


class MergeMaterials(Operator):
    bl_idname = "mmd_tools.merge_materials"
    bl_label = "Merge Materials"
    bl_description = "Merge materials with the same texture in selected objects. Only merges materials with exactly one texture node. Materials with no texture or with multiple textures are not merged. Please convert to Blender materials first."
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any(x.type == "MESH" for x in context.selected_objects)

    def execute(self, context):
        # Process all selected mesh objects
        for obj in context.selected_objects:
            if obj.type != "MESH":
                continue

            self.merge_materials_for_object(context, obj)

        return {"FINISHED"}

    def merge_materials_for_object(self, context, obj):
        """Merge materials with same texture for a single object"""
        if not obj.data.materials:
            self.report({"INFO"}, f"Object '{obj.name}' has no materials")
            return

        # Map texture paths to material indices and names
        texture_to_materials = defaultdict(list)

        # Check each material
        for i, material in enumerate(obj.data.materials):
            if not material or not material.use_nodes:
                continue

            # 1. Check texture node count (must be exactly 1)
            texture_nodes = [node for node in material.node_tree.nodes if node.type == "TEX_IMAGE"]
            if len(texture_nodes) != 1:
                continue

            # 2. Record texture path and material info
            texture_node = texture_nodes[0]
            if texture_node.image:
                texture_path = bpy.path.abspath(texture_node.image.filepath)
                texture_to_materials[texture_path].append({"index": i, "name": material.name})

        # Find material groups that need merging
        materials_to_merge = {path: materials for path, materials in texture_to_materials.items() if len(materials) > 1}

        if not materials_to_merge:
            self.report({"INFO"}, f"No materials to merge in object '{obj.name}'")
            return

        # Process each texture group
        context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        merge_details = []
        for texture_path, materials in materials_to_merge.items():
            # Use first material as target
            target_material = materials[0]
            target_index = target_material["index"]
            target_name = target_material["name"]

            source_materials = []

            # Reassign faces from other materials to target material
            for source_material in materials[1:]:
                source_index = source_material["index"]
                source_name = source_material["name"]
                source_materials.append(source_name)

                bpy.ops.mesh.select_all(action="DESELECT")
                obj.active_material_index = source_index
                bpy.ops.object.material_slot_select()
                obj.active_material_index = target_index
                bpy.ops.object.material_slot_assign()

            # Record merge details
            texture_name = bpy.path.basename(texture_path)
            merge_details.append({"texture": texture_name, "target": target_name, "sources": source_materials})
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.material_slot_remove_unused()

        merged_count = sum(len(details["sources"]) for details in merge_details)
        self.report({"INFO"}, f"Object '{obj.name}': Merged {merged_count} materials")

        for details in merge_details:
            sources_text = ", ".join(details["sources"])
            self.report({"INFO"}, f"Same Texture '{details['texture']}': Merged materials [{sources_text}] into '{details['target']}'")


class ConvertBSDFMaterials(Operator):
    bl_idname = "mmd_tools.convert_bsdf_materials"
    bl_label = "Convert Blender Materials"
    bl_description = "Convert materials of selected objects."
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any(x.type == "MESH" for x in context.selected_objects)

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type != "MESH":
                continue
            cycles_converter.convertToMMDShader(obj)
        return {"FINISHED"}


class _OpenTextureBase:
    """Create a texture for mmd model material."""

    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    filepath: StringProperty(
        name="File Path",
        description="Filepath used for importing the file",
        maxlen=1024,
        subtype="FILE_PATH",
    )

    use_filter_image: BoolProperty(
        default=True,
        options={"HIDDEN"},
    )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class OpenTexture(Operator, _OpenTextureBase):
    bl_idname = "mmd_tools.material_open_texture"
    bl_label = "Open Texture"
    bl_description = "Create main texture of active material"

    def execute(self, context):
        mat = context.active_object.active_material
        fnMat = FnMaterial(mat)
        fnMat.create_texture(self.filepath)
        return {"FINISHED"}


class SetupTexture(Operator):
    bl_idname = "mmd_tools.material_setup_texture"
    bl_label = "Setup Texture"
    bl_description = "Add main texture nodes for all materials. Enables copy & pasting texture paths in MMD Texture.\nWarning: Materials will turn pink. Use Texture Cleanup after assigning textures."
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any(x.type == "MESH" for x in context.selected_objects)

    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            for i in obj.material_slots:
                # usual checks
                if not i.material:
                    continue
                if not i.material.use_nodes:
                    i.material.use_nodes = True

                # empty texture if one doesn't exist
                mat = i.material
                fnMat = FnMaterial(mat)
                if fnMat.get_texture() is None:
                    fnMat.create_texture("")
                    count += 1
        if count > 0:
            self.report({"INFO"}, f"Added {count} empty texture nodes.")
        return {"FINISHED"}


class RemoveTexture(Operator):
    """Remove a texture for mmd model material."""

    bl_idname = "mmd_tools.material_remove_texture"
    bl_label = "Remove Texture"
    bl_description = "Remove main texture of active material"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        mat = context.active_object.active_material
        fnMat = FnMaterial(mat)
        fnMat.remove_texture()
        return {"FINISHED"}


class CleanupTexture(Operator):
    bl_idname = "mmd_tools.material_cleanup_texture"
    bl_label = "Cleanup Texture"
    bl_description = "Remove unused texture nodes."
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any(x.type == "MESH" for x in context.selected_objects)

    def execute(self, context):
        count = 0
        for obj in context.selected_objects:
            # usual checks
            for i in obj.material_slots:
                if not i.material:
                    continue
                if not i.material.use_nodes:
                    i.material.use_nodes = True

                # remove texture if it's empty (or newly created)
                mat = i.material
                fnMat = FnMaterial(mat)
                tex = fnMat.get_texture()
                if tex is not None and (not tex.image or tex.image.filepath == ""):
                    fnMat.remove_texture()
                    count += 1

        if count > 0:
            self.report({"INFO"}, f"Removed {count} texture nodes.")
        return {"FINISHED"}


class OpenSphereTextureSlot(Operator, _OpenTextureBase):
    """Create a texture for mmd model material."""

    bl_idname = "mmd_tools.material_open_sphere_texture"
    bl_label = "Open Sphere Texture"
    bl_description = "Create sphere texture of active material"

    def execute(self, context):
        mat = context.active_object.active_material
        fnMat = FnMaterial(mat)
        fnMat.create_sphere_texture(self.filepath, context.active_object)
        return {"FINISHED"}


class RemoveSphereTexture(Operator):
    """Create a texture for mmd model material."""

    bl_idname = "mmd_tools.material_remove_sphere_texture"
    bl_label = "Remove Sphere Texture"
    bl_description = "Remove sphere texture of active material"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        mat = context.active_object.active_material
        fnMat = FnMaterial(mat)
        fnMat.remove_sphere_texture()
        return {"FINISHED"}


class MoveMaterialUp(Operator):
    bl_idname = "mmd_tools.move_material_up"
    bl_label = "Move Material Up"
    bl_description = "Moves selected material one slot up"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "MESH" and obj.mmd_type == "NONE" and obj.active_material_index > 0

    def execute(self, context):
        obj = context.active_object
        current_idx = obj.active_material_index
        prev_index = current_idx - 1
        try:
            FnMaterial.swap_materials(obj, current_idx, prev_index, reverse=True, swap_slots=True)
        except MaterialNotFoundError:
            self.report({"ERROR"}, "Materials not found")
            return {"CANCELLED"}
        obj.active_material_index = prev_index

        return {"FINISHED"}


class MoveMaterialDown(Operator):
    bl_idname = "mmd_tools.move_material_down"
    bl_label = "Move Material Down"
    bl_description = "Moves the selected material one slot down"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "MESH" and obj.mmd_type == "NONE" and obj.active_material_index < len(obj.material_slots) - 1

    def execute(self, context):
        obj = context.active_object
        current_idx = obj.active_material_index
        next_index = current_idx + 1
        try:
            FnMaterial.swap_materials(obj, current_idx, next_index, reverse=True, swap_slots=True)
        except MaterialNotFoundError:
            self.report({"ERROR"}, "Materials not found")
            return {"CANCELLED"}
        obj.active_material_index = next_index
        return {"FINISHED"}


class EdgePreviewSetup(Operator):
    bl_idname = "mmd_tools.edge_preview_setup"
    bl_label = "Edge Preview Setup"
    bl_description = 'Preview toon edge settings of active model using "Solidify" modifier'
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    action: bpy.props.EnumProperty(
        name="Action",
        description="Select action",
        items=[
            ("CREATE", "Create", "Create toon edge", 0),
            ("CLEAN", "Clean", "Clear toon edge", 1),
        ],
        default="CREATE",
    )

    def execute(self, context):
        from ..core.model import FnModel

        root = FnModel.find_root_object(context.active_object)
        if root is None:
            self.report({"ERROR"}, "Select a MMD model")
            return {"CANCELLED"}

        if self.action == "CLEAN":
            for obj in FnModel.iterate_mesh_objects(root):
                self.__clean_toon_edge(obj)
        else:
            from ..bpyutils import Props

            scale = 0.2 * getattr(root, Props.empty_display_size)
            counts = sum(self.__create_toon_edge(obj, scale) for obj in FnModel.iterate_mesh_objects(root))
            self.report({"INFO"}, f"Created {counts} toon edge(s)")
        return {"FINISHED"}

    def __clean_toon_edge(self, obj):
        if "mmd_edge_preview" in obj.modifiers:
            obj.modifiers.remove(obj.modifiers["mmd_edge_preview"])

        if "mmd_edge_preview" in obj.vertex_groups:
            obj.vertex_groups.remove(obj.vertex_groups["mmd_edge_preview"])

        FnMaterial.clean_materials(obj, can_remove=lambda m: m and m.name.startswith("mmd_edge."))

    def __create_toon_edge(self, obj, scale=1.0):
        self.__clean_toon_edge(obj)
        materials = obj.data.materials
        material_offset = len(materials)
        for m in tuple(materials):
            if m and m.mmd_material.enabled_toon_edge:
                mat_edge = self.__get_edge_material("mmd_edge." + m.name, m.mmd_material.edge_color, materials)
                materials.append(mat_edge)
            elif material_offset > 1:
                mat_edge = self.__get_edge_material("mmd_edge.disabled", (0, 0, 0, 0), materials)
                materials.append(mat_edge)
        if len(materials) > material_offset:
            mod = obj.modifiers.get("mmd_edge_preview", None)
            if mod is None:
                mod = obj.modifiers.new("mmd_edge_preview", "SOLIDIFY")
            mod.material_offset = material_offset
            mod.thickness_vertex_group = 1e-3  # avoid overlapped faces
            mod.use_flip_normals = True
            mod.use_rim = False
            mod.offset = 1
            self.__create_edge_preview_group(obj)
            mod.thickness = scale
            mod.vertex_group = "mmd_edge_preview"
        return len(materials) - material_offset

    def __create_edge_preview_group(self, obj):
        vertices, materials = obj.data.vertices, obj.data.materials
        weight_map = {i: m.mmd_material.edge_weight for i, m in enumerate(materials) if m}
        scale_map = {}
        vg_scale_index = obj.vertex_groups.find("mmd_edge_scale")
        if vg_scale_index >= 0:
            scale_map = {v.index: g.weight for v in vertices for g in v.groups if g.group == vg_scale_index}
        vg_edge_preview = obj.vertex_groups.new(name="mmd_edge_preview")
        for i, mi in {v: f.material_index for f in reversed(obj.data.polygons) for v in f.vertices}.items():
            weight = scale_map.get(i, 1.0) * weight_map.get(mi, 1.0) * 0.02
            vg_edge_preview.add(index=[i], weight=weight, type="REPLACE")

    def __get_edge_material(self, mat_name, edge_color, materials):
        if mat_name in materials:
            return materials[mat_name]
        mat = bpy.data.materials.get(mat_name, None)
        if mat is None:
            mat = bpy.data.materials.new(mat_name)
        mmd_mat = mat.mmd_material
        # note: edge affects ground shadow
        mmd_mat.is_double_sided = mmd_mat.enabled_drop_shadow = False
        mmd_mat.enabled_self_shadow_map = mmd_mat.enabled_self_shadow = False
        # mmd_mat.enabled_self_shadow_map = True # for blender 2.78+ BI viewport only
        mmd_mat.diffuse_color = mmd_mat.specular_color = (0, 0, 0)
        mmd_mat.ambient_color = edge_color[:3]
        mmd_mat.alpha = edge_color[3]
        mmd_mat.edge_color = edge_color
        self.__make_shader(mat)
        return mat

    def __make_shader(self, m):
        m.use_nodes = True
        nodes, links = m.node_tree.nodes, m.node_tree.links

        node_shader = nodes.get("mmd_edge_preview", None)
        if node_shader is None or not any(s.is_linked for s in node_shader.outputs):
            XPOS, YPOS = 210, 110
            nodes.clear()
            node_shader = nodes.new("ShaderNodeGroup")
            node_shader.name = "mmd_edge_preview"
            node_shader.location = (0, 0)
            node_shader.width = 200
            node_shader.node_tree = self.__get_edge_preview_shader()

            node_out = nodes.new("ShaderNodeOutputMaterial")
            node_out.location = (XPOS * 2, YPOS * 0)
            links.new(node_shader.outputs["Shader"], node_out.inputs["Surface"])

        node_shader.inputs["Color"].default_value = m.mmd_material.edge_color
        node_shader.inputs["Alpha"].default_value = m.mmd_material.edge_color[3]

    def __get_edge_preview_shader(self):
        group_name = "MMDEdgePreview"
        shader = bpy.data.node_groups.get(group_name, None) or bpy.data.node_groups.new(name=group_name, type="ShaderNodeTree")
        if len(shader.nodes):
            return shader

        ng = _NodeGroupUtils(shader)

        ng.new_node("NodeGroupInput", (-5, 0))
        ng.new_node("NodeGroupOutput", (3, 0))

        ############################################################################
        node_color = ng.new_node("ShaderNodeMixRGB", (-1, -1.5))
        node_color.mute = True

        ng.new_input_socket("Color", node_color.inputs["Color1"])

        ############################################################################
        node_ray = ng.new_node("ShaderNodeLightPath", (-3, 1.5))
        node_geo = ng.new_node("ShaderNodeNewGeometry", (-3, 0))
        node_max = ng.new_math_node("MAXIMUM", (-2, 1.5))
        node_max.mute = True
        node_gt = ng.new_math_node("GREATER_THAN", (-1, 1))
        node_alpha = ng.new_math_node("MULTIPLY", (0, 1))
        node_trans = ng.new_node("ShaderNodeBsdfTransparent", (0, 0))
        node_rgb = ng.new_node("ShaderNodeBackground", (0, -0.5))
        node_mix = ng.new_node("ShaderNodeMixShader", (1, 0.5))

        links = ng.links
        links.new(node_ray.outputs["Is Camera Ray"], node_max.inputs[0])
        links.new(node_ray.outputs["Is Glossy Ray"], node_max.inputs[1])
        links.new(node_max.outputs["Value"], node_gt.inputs[0])
        links.new(node_geo.outputs["Backfacing"], node_gt.inputs[1])
        links.new(node_gt.outputs["Value"], node_alpha.inputs[0])
        links.new(node_alpha.outputs["Value"], node_mix.inputs["Fac"])
        links.new(node_trans.outputs["BSDF"], node_mix.inputs[1])
        links.new(node_rgb.outputs[0], node_mix.inputs[2])
        links.new(node_color.outputs["Color"], node_rgb.inputs["Color"])

        ng.new_input_socket("Alpha", node_alpha.inputs[1])
        ng.new_output_socket("Shader", node_mix.outputs["Shader"])

        return shader
