# -*- coding: utf-8 -*-
# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

import bpy

from ..bpyutils import FnContext
from ..core import FnCore
from ..core.bone import FnBone, MigrationFnBone
from ..core.model import FnModel, MMDModel


class MorphSliderSetup(bpy.types.Operator):
    bl_idname = "mmd_tools.morph_slider_setup"
    bl_label = "Morph Slider Setup"
    bl_description = "Translate MMD morphs of selected object into format usable by Blender"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    type: bpy.props.EnumProperty(
        name="Type",
        description="Select type",
        items=[
            ("CREATE", "Create", "Create placeholder object for morph sliders", "SHAPEKEY_DATA", 0),
            ("BIND", "Bind", "Bind morph sliders", "DRIVER", 1),
            ("UNBIND", "Unbind", "Unbind morph sliders", "X", 2),
        ],
        default="CREATE",
    )

    def execute(self, context: bpy.types.Context):
        active_object = context.active_object
        root_object = FnCore.find_root_object(active_object)
        assert root_object is not None

        with FnContext.temp_override_active_layer_collection(context, root_object):
            rig = MMDModel(root_object)
            if self.type == "BIND":
                rig.morph_slider.bind()
            elif self.type == "UNBIND":
                rig.morph_slider.unbind()
            else:
                rig.morph_slider.create()
            FnContext.set_active_object(context, active_object)

        return {"FINISHED"}


class CleanRiggingObjects(bpy.types.Operator):
    bl_idname = "mmd_tools.clean_rig"
    bl_label = "Clean Rig"
    bl_description = "Delete temporary physics objects of selected object and revert physics to default MMD state"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        root_object = FnCore.find_root_object(context.active_object)
        assert root_object is not None

        rig = MMDModel(root_object)
        rig.clean()
        FnContext.set_active_object(context, root_object)
        return {"FINISHED"}


class BuildRig(bpy.types.Operator):
    bl_idname = "mmd_tools.build_rig"
    bl_label = "Build Rig"
    bl_description = "Translate physics of selected object into format usable by Blender"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    non_collision_distance_scale: bpy.props.FloatProperty(
        name="Non-Collision Distance Scale",
        description="The distance scale for creating extra non-collision constraints while building physics",
        min=0,
        soft_max=10,
        default=1.5,
    )

    collision_margin: bpy.props.FloatProperty(
        name="Collision Margin",
        description="The collision margin between rigid bodies. If 0, the default value for each shape is adopted.",
        unit="LENGTH",
        min=0,
        soft_max=10,
        default=1e-06,
    )

    def execute(self, context):
        root_object = FnCore.find_root_object(context.active_object)

        with FnContext.temp_override_active_layer_collection(context, root_object):
            rig = MMDModel(root_object)
            rig.build(self.non_collision_distance_scale, self.collision_margin)
            FnContext.set_active_object(context, root_object)

        return {"FINISHED"}


class CleanAdditionalTransformConstraints(bpy.types.Operator):
    bl_idname = "mmd_tools.clean_additional_transform"
    bl_label = "Clean Additional Transform"
    bl_description = "Delete shadow bones of selected object and revert bones to default MMD state"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        active_object = context.active_object
        root_object = FnCore.find_root_object(active_object)
        assert root_object is not None
        FnBone.clean_additional_transformation(FnCore.find_armature_object(root_object))
        FnContext.set_active_object(context, active_object)
        return {"FINISHED"}


class ApplyAdditionalTransformConstraints(bpy.types.Operator):
    bl_idname = "mmd_tools.apply_additional_transform"
    bl_label = "Apply Additional Transform"
    bl_description = "Translate appended bones of selected object for Blender"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        active_object = context.active_object
        root_object = FnCore.find_root_object(active_object)
        assert root_object is not None

        armature_object = FnCore.find_armature_object(root_object)
        assert armature_object is not None

        MigrationFnBone.fix_mmd_ik_limit_override(armature_object)
        FnBone.apply_additional_transformation(armature_object)
        FnContext.set_active_object(context, active_object)
        return {"FINISHED"}


class SetupBoneFixedAxes(bpy.types.Operator):
    bl_idname = "mmd_tools.bone_fixed_axis_setup"
    bl_label = "Setup Bone Fixed Axis"
    bl_description = "Setup fixed axis of selected bones"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    type: bpy.props.EnumProperty(
        name="Type",
        description="Select type",
        items=[
            ("DISABLE", "Disable", "Disable MMD fixed axis of selected bones", 0),
            ("LOAD", "Load", "Load/Enable MMD fixed axis of selected bones from their Y-axis or the only rotatable axis", 1),
            ("APPLY", "Apply", "Align bone axes to MMD fixed axis of each bone", 2),
        ],
        default="LOAD",
    )

    def execute(self, context):
        armature_object = context.active_object
        if not armature_object or armature_object.type != "ARMATURE":
            self.report({"ERROR"}, "Active object is not an armature object")
            return {"CANCELLED"}

        if self.type == "APPLY":
            FnBone.apply_bone_fixed_axis(armature_object)
            FnBone.apply_additional_transformation(armature_object)
        else:
            FnBone.load_bone_fixed_axis(armature_object, enable=(self.type == "LOAD"))
        return {"FINISHED"}


class SetupBoneLocalAxes(bpy.types.Operator):
    bl_idname = "mmd_tools.bone_local_axes_setup"
    bl_label = "Setup Bone Local Axes"
    bl_description = "Setup local axes of each bone"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    type: bpy.props.EnumProperty(
        name="Type",
        description="Select type",
        items=[
            ("DISABLE", "Disable", "Disable MMD local axes of selected bones", 0),
            ("LOAD", "Load", "Load/Enable MMD local axes of selected bones from their bone axes", 1),
            ("APPLY", "Apply", "Align bone axes to MMD local axes of each bone", 2),
        ],
        default="LOAD",
    )

    def execute(self, context):
        armature_object = context.active_object
        if not armature_object or armature_object.type != "ARMATURE":
            self.report({"ERROR"}, "Active object is not an armature object")
            return {"CANCELLED"}

        if self.type == "APPLY":
            FnBone.apply_bone_local_axes(armature_object)
            FnBone.apply_additional_transformation(armature_object)
        else:
            FnBone.load_bone_local_axes(armature_object, enable=(self.type == "LOAD"))
        return {"FINISHED"}


class AddMissingVertexGroupsFromBones(bpy.types.Operator):
    bl_idname = "mmd_tools.add_missing_vertex_groups_from_bones"
    bl_label = "Add Missing Vertex Groups from Bones"
    bl_description = "Add the missing vertex groups to the selected mesh"
    bl_options = {"REGISTER", "UNDO"}

    search_in_all_meshes: bpy.props.BoolProperty(
        name="Search in all meshes",
        description="Search for vertex groups in all meshes",
        default=False,
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return FnCore.find_root_object(context.active_object) is not None

    def execute(self, context: bpy.types.Context):
        active_object: bpy.types.Object = context.active_object
        root_object = FnCore.find_root_object(active_object)
        assert root_object is not None

        bone_order_mesh_object = FnCore.find_bone_order_mesh_object(root_object)
        if bone_order_mesh_object is None:
            return {"CANCELLED"}

        FnModel.add_missing_vertex_groups_from_bones(root_object, bone_order_mesh_object, self.search_in_all_meshes)

        return {"FINISHED"}


class CreateMMDModelRoot(bpy.types.Operator):
    bl_idname = "mmd_tools.create_mmd_model_root_object"
    bl_label = "Create a MMD Model Root Object"
    bl_description = "Create a MMD model root object with a basic armature"
    bl_options = {"REGISTER", "UNDO"}

    name_j: bpy.props.StringProperty(
        name="Name",
        description="The name of the MMD model",
        default="New MMD Model",
    )
    name_e: bpy.props.StringProperty(
        name="Name(Eng)",
        description="The english name of the MMD model",
        default="New MMD Model",
    )
    scale: bpy.props.FloatProperty(
        name="Scale",
        description="Scale",
        default=0.08,
    )

    def execute(self, context):
        rig = MMDModel.create(self.name_j, self.name_e, self.scale, add_root_bone=True)
        FnModel.initalize_display_item_frames(rig.rootObject())
        return {"FINISHED"}

    def invoke(self, context, event):
        vm = context.window_manager
        return vm.invoke_props_dialog(self)


class ConvertToMMDModel(bpy.types.Operator):
    bl_idname = "mmd_tools.convert_to_mmd_model"
    bl_label = "Convert to a MMD Model"
    bl_description = "Convert active armature with its meshes to a MMD model (experimental)"
    bl_options = {"REGISTER", "UNDO"}

    ambient_color_source: bpy.props.EnumProperty(
        name="Ambient Color Source",
        description="Select ambient color source",
        items=[
            ("DIFFUSE", "Diffuse", "Diffuse color", 0),
            ("MIRROR", "Mirror", 'Mirror color (if property "mirror_color" is available)', 1),
        ],
        default="DIFFUSE",
    )
    edge_threshold: bpy.props.FloatProperty(
        name="Edge Threshold",
        description="MMD toon edge will not be enabled if freestyle line color alpha less than this value",
        min=0,
        max=1.001,
        precision=3,
        step=0.1,
        default=0.1,
    )
    edge_alpha_min: bpy.props.FloatProperty(
        name="Minimum Edge Alpha",
        description="Minimum alpha of MMD toon edge color",
        min=0,
        max=1,
        precision=3,
        step=0.1,
        default=0.5,
    )
    scale: bpy.props.FloatProperty(
        name="Scale",
        description="Scaling factor for converting the model",
        default=0.08,
    )
    convert_material_nodes: bpy.props.BoolProperty(
        name="Convert Material Nodes",
        default=True,
    )
    middle_joint_bones_lock: bpy.props.BoolProperty(
        name="Middle Joint Bones Lock",
        description="Lock specific bones for backward compatibility.",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == "ARMATURE" and obj.mode != "EDIT"

    def invoke(self, context, event):
        vm = context.window_manager
        return vm.invoke_props_dialog(self)

    def execute(self, context):
        # TODO convert some basic MMD properties
        armature_object = context.active_object
        scale = self.scale
        model_name = "New MMD Model"

        root_object = FnCore.find_root_object(armature_object)
        if root_object is None or root_object != armature_object.parent:
            MMDModel.create(model_name, model_name, scale, armature_object=armature_object)

        self.__attach_meshes_to(armature_object, FnContext.get_scene_objects(context))
        self.__configure_rig(context, MMDModel(armature_object.parent))
        return {"FINISHED"}

    def __attach_meshes_to(self, armature_object: bpy.types.Object, objects: bpy.types.SceneObjects):
        def __is_child_of_armature(mesh):
            if mesh.parent is None:
                return False
            return mesh.parent == armature_object or __is_child_of_armature(mesh.parent)

        def __is_using_armature(mesh):
            for m in mesh.modifiers:
                if m.type == "ARMATURE" and m.object == armature_object:
                    return True
            return False

        def __get_root(mesh):
            if mesh.parent is None:
                return mesh
            return __get_root(mesh.parent)

        for x in objects:
            if __is_using_armature(x) and not __is_child_of_armature(x):
                x_root = __get_root(x)
                m = x_root.matrix_world
                x_root.parent_type = "OBJECT"
                x_root.parent = armature_object
                x_root.matrix_world = m

    def __configure_rig(self, context: bpy.types.Context, mmd_model: MMDModel):
        root_object = mmd_model.rootObject()
        armature_object = mmd_model.armature()
        mesh_objects = tuple(mmd_model.meshes())

        mmd_model.loadMorphs()

        if self.middle_joint_bones_lock:
            vertex_groups = {g.name for mesh in mesh_objects for g in mesh.vertex_groups}
            for pose_bone in armature_object.pose.bones:
                if not pose_bone.parent:
                    continue
                if not pose_bone.bone.use_connect and pose_bone.name not in vertex_groups:
                    continue
                pose_bone.lock_location = (True, True, True)

        from ..core.material import FnMaterial

        FnMaterial.set_nodes_are_readonly(not self.convert_material_nodes)
        try:
            for m in (x for mesh in mesh_objects for x in mesh.data.materials if x):
                FnMaterial.convert_to_mmd_material(m, context)
                mmd_material = m.mmd_material
                if self.ambient_color_source == "MIRROR" and hasattr(m, "mirror_color"):
                    mmd_material.ambient_color = m.mirror_color
                else:
                    mmd_material.ambient_color = [0.5 * c for c in mmd_material.diffuse_color]

                if hasattr(m, "line_color"):  # freestyle line color
                    line_color = list(m.line_color)
                    mmd_material.enabled_toon_edge = line_color[3] >= self.edge_threshold
                    mmd_material.edge_color = line_color[:3] + [max(line_color[3], self.edge_alpha_min)]
        finally:
            FnMaterial.set_nodes_are_readonly(False)
        from .display_item import DisplayItemQuickSetup

        FnModel.sync_from_bone_collections(root_object)
        FnModel.initalize_display_item_frames(root_object, reset=False)  # ensure default frames
        DisplayItemQuickSetup.load_facial_items(root_object.mmd_root)
        root_object.mmd_root.active_display_item_frame = 0


class ResetObjectVisibility(bpy.types.Operator):
    bl_idname = "mmd_tools.reset_object_visibility"
    bl_label = "Reset Object Visivility"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        active_object: bpy.types.Object = context.active_object
        return FnCore.find_root_object(active_object) is not None

    def execute(self, context: bpy.types.Context):
        active_object: bpy.types.Object = context.active_object
        mmd_root_object = FnCore.find_root_object(active_object)
        assert mmd_root_object is not None
        mmd_root = mmd_root_object.mmd_root

        mmd_root_object.hide_set(False)

        rigid_group_object = FnCore.find_rigid_group_object(mmd_root_object)
        if rigid_group_object:
            rigid_group_object.hide_set(True)

        joint_group_object = FnCore.find_joint_group_object(mmd_root_object)
        if joint_group_object:
            joint_group_object.hide_set(True)

        temporary_group_object = FnCore.find_temporary_group_object(mmd_root_object)
        if temporary_group_object:
            temporary_group_object.hide_set(True)

        mmd_root.show_meshes = True
        mmd_root.show_armature = True
        mmd_root.show_temporary_objects = False
        mmd_root.show_rigid_bodies = False
        mmd_root.show_names_of_rigid_bodies = False
        mmd_root.show_joints = False
        mmd_root.show_names_of_joints = False

        return {"FINISHED"}


class AssembleAll(bpy.types.Operator):
    bl_idname = "mmd_tools.assemble_all"
    bl_label = "Assemble All"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        active_object = context.active_object
        root_object = FnCore.find_root_object(active_object)
        assert root_object is not None

        with FnContext.temp_override_active_layer_collection(context, root_object) as context:
            rig = MMDModel(root_object)
            MigrationFnBone.fix_mmd_ik_limit_override(rig.armature())
            FnBone.apply_additional_transformation(rig.armature())
            rig.build()
            rig.morph_slider.bind()

            with context.temp_override(selected_objects=[active_object]):
                bpy.ops.mmd_tools.sdef_bind()
            root_object.mmd_root.use_property_driver = True

            FnContext.set_active_object(context, active_object)

        return {"FINISHED"}


class DisassembleAll(bpy.types.Operator):
    bl_idname = "mmd_tools.disassemble_all"
    bl_label = "Disassemble All"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        active_object = context.active_object
        root_object = FnCore.find_root_object(active_object)
        assert root_object is not None

        with FnContext.temp_override_active_layer_collection(context, root_object) as context:
            root_object.mmd_root.use_property_driver = False
            with context.temp_override(selected_objects=[active_object]):
                bpy.ops.mmd_tools.sdef_unbind()

            rig = MMDModel(root_object)
            rig.morph_slider.unbind()
            rig.clean()
            FnBone.clean_additional_transformation(rig.armature())

            FnContext.set_active_object(context, active_object)

        return {"FINISHED"}
