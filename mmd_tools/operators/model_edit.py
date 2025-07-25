# Copyright 2022 MMD Tools authors
# This file is part of MMD Tools.

import itertools
from operator import itemgetter
from typing import Dict, List, Optional, Set

import bmesh
import bpy

from ..bpyutils import FnContext, select_object
from ..core.model import FnModel, Model


class NoModelSelectedError(Exception):
    """Raised when no MMD model is selected."""


class ModelJoinByBonesOperator(bpy.types.Operator):
    bl_idname = "mmd_tools.model_join_by_bones"
    bl_label = "Model Join by Bones"
    bl_options = {"REGISTER", "UNDO"}

    join_type: bpy.props.EnumProperty(
        name="Join Type",
        items=[
            ("CONNECTED", "Connected", ""),
            ("OFFSET", "Keep Offset", ""),
        ],
        default="OFFSET",
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        active_object: Optional[bpy.types.Object] = context.active_object

        if context.mode != "POSE":
            return False

        if active_object is None:
            return False

        if active_object.type != "ARMATURE":
            return False

        if len(list(filter(lambda o: o.type == "ARMATURE", context.selected_objects))) < 2:
            return False

        return len(context.selected_pose_bones) > 0

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context):
        try:
            self.join(context)
        except NoModelSelectedError as ex:
            self.report(type={"ERROR"}, message=str(ex))
            return {"CANCELLED"}

        return {"FINISHED"}

    def join(self, context: bpy.types.Context):
        bpy.ops.object.mode_set(mode="OBJECT")

        parent_root_object = FnModel.find_root_object(context.active_object)
        child_root_objects = {FnModel.find_root_object(o) for o in context.selected_objects}
        child_root_objects.remove(parent_root_object)

        if parent_root_object is None or len(child_root_objects) == 0:
            raise NoModelSelectedError("No MMD Models selected")

        # Save original active_layer_collection
        orig_active_layer_collection = context.view_layer.active_layer_collection

        # Find layer collection containing parent_root_object and set it as active
        layer_collection = FnContext.find_user_layer_collection_by_object(context, parent_root_object)
        if layer_collection:
            context.view_layer.active_layer_collection = layer_collection

        # Execute the join operation
        FnModel.join_models(parent_root_object, child_root_objects)

        # Restore original active_layer_collection
        context.view_layer.active_layer_collection = orig_active_layer_collection

        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.armature.parent_set(type="OFFSET")

        # Connect child bones
        if self.join_type == "CONNECTED":
            parent_edit_bone: bpy.types.EditBone = context.active_bone
            child_edit_bones: Set[bpy.types.EditBone] = set(context.selected_bones)
            child_edit_bones.remove(parent_edit_bone)

            child_edit_bone: bpy.types.EditBone
            for child_edit_bone in child_edit_bones:
                child_edit_bone.use_connect = True

        bpy.ops.object.mode_set(mode="POSE")


class ModelSeparateByBonesOperator(bpy.types.Operator):
    bl_idname = "mmd_tools.model_separate_by_bones"
    bl_label = "Model Separate by Bones"
    bl_options = {"REGISTER", "UNDO"}

    separate_armature: bpy.props.BoolProperty(name="Separate Armature", default=True)
    include_descendant_bones: bpy.props.BoolProperty(name="Include Descendant Bones", default=True)
    weight_threshold: bpy.props.FloatProperty(name="Weight Threshold", default=0.001, min=0.0, max=1.0, precision=4, subtype="FACTOR")
    boundary_joint_owner: bpy.props.EnumProperty(
        name="Boundary Joint Owner",
        items=[
            ("SOURCE", "Source Model", ""),
            ("DESTINATION", "Destination Model", ""),
        ],
        default="DESTINATION",
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        active_object: Optional[bpy.types.Object] = context.active_object

        if context.mode != "POSE":
            return False

        if active_object is None:
            return False

        if active_object.type != "ARMATURE":
            return False

        if FnModel.find_root_object(active_object) is None:
            return False

        return len(context.selected_pose_bones) > 0

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context):
        try:
            self.separate(context)
        except NoModelSelectedError as ex:
            self.report(type={"ERROR"}, message=str(ex))
            return {"CANCELLED"}

        return {"FINISHED"}

    def separate(self, context: bpy.types.Context):
        weight_threshold: float = self.weight_threshold
        mmd_scale = 0.08

        target_armature_object: bpy.types.Object = context.active_object

        bpy.ops.object.mode_set(mode="EDIT")
        root_bones: Set[bpy.types.EditBone] = set(context.selected_bones)

        if self.include_descendant_bones:
            original_active_bone = context.active_bone
            for edit_bone in root_bones:
                context.active_object.data.edit_bones.active = edit_bone
                bpy.ops.armature.select_similar(type="CHILDREN", threshold=0.1)
            if original_active_bone:
                context.active_object.data.edit_bones.active = original_active_bone

        separate_bones: Dict[str, bpy.types.EditBone] = {b.name: b for b in context.selected_bones}
        deform_bones: Dict[str, bpy.types.EditBone] = {b.name: b for b in target_armature_object.data.edit_bones if b.use_deform}

        mmd_root_object: bpy.types.Object = FnModel.find_root_object(context.active_object)
        mmd_model = Model(mmd_root_object)
        mmd_model_mesh_objects: List[bpy.types.Object] = list(mmd_model.meshes())

        mmd_model_mesh_objects = list(self.select_weighted_vertices(mmd_model_mesh_objects, separate_bones, deform_bones, weight_threshold).keys())

        # separate armature bones
        separate_armature_object: Optional[bpy.types.Object]
        if self.separate_armature:
            target_armature_object.select_set(True)
            bpy.ops.armature.separate()
            separate_armature_object = next(iter([a for a in context.selected_objects if a != target_armature_object]), None)
        bpy.ops.object.mode_set(mode="OBJECT")

        # collect separate rigid bodies
        separate_rigid_bodies: Set[bpy.types.Object] = {rigid_body_object for rigid_body_object in mmd_model.rigidBodies() if rigid_body_object.mmd_rigid.bone in separate_bones}

        boundary_joint_owner_condition = any if self.boundary_joint_owner == "DESTINATION" else all

        # collect separate joints
        separate_joints: Set[bpy.types.Object] = {
            joint_object
            for joint_object in mmd_model.joints()
            if boundary_joint_owner_condition(
                [
                    joint_object.rigid_body_constraint.object1 in separate_rigid_bodies,
                    joint_object.rigid_body_constraint.object2 in separate_rigid_bodies,
                ],
            )
        }

        separate_mesh_objects: Set[bpy.types.Object]
        model2separate_mesh_objects: Dict[bpy.types.Object, bpy.types.Object]
        if len(mmd_model_mesh_objects) == 0:
            separate_mesh_objects = set()
            model2separate_mesh_objects = {}
        else:
            # select meshes
            obj: bpy.types.Object
            for obj in context.view_layer.objects:
                obj.select_set(obj in mmd_model_mesh_objects)
            context.view_layer.objects.active = mmd_model_mesh_objects[0]

            # separate mesh by selected vertices
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.separate(type="SELECTED")
            separate_mesh_objects: List[bpy.types.Object] = [m for m in context.selected_objects if m.type == "MESH" and m not in mmd_model_mesh_objects]
            bpy.ops.object.mode_set(mode="OBJECT")

            model2separate_mesh_objects = dict(zip(mmd_model_mesh_objects, separate_mesh_objects, strict=False))

        separate_model: Model = Model.create(mmd_root_object.mmd_root.name, mmd_root_object.mmd_root.name_e, mmd_scale, add_root_bone=False)

        separate_model.initialDisplayFrames()
        separate_root_object = separate_model.rootObject()
        separate_root_object.matrix_world = mmd_root_object.matrix_world
        separate_model_armature_object = separate_model.armature()

        if self.separate_armature:
            with select_object(separate_model_armature_object, objects=[separate_model_armature_object, separate_armature_object]):
                bpy.ops.object.join()

        with select_object(separate_model_armature_object, objects=[separate_model_armature_object] + list(separate_mesh_objects)):
            bpy.ops.object.parent_set(type="OBJECT", keep_transform=True)

        # replace mesh armature modifier.object
        for separate_mesh in separate_mesh_objects:
            armature_modifier: Optional[bpy.types.ArmatureModifier] = next(iter([m for m in separate_mesh.modifiers if m.type == "ARMATURE"]), None)
            if armature_modifier is None:
                armature_modifier: bpy.types.ArmatureModifier = separate_mesh.modifiers.new("mmd_armature", "ARMATURE")

            armature_modifier.object = separate_model_armature_object

        with select_object(separate_model.rigidGroupObject(), objects=[separate_model.rigidGroupObject()] + list(separate_rigid_bodies)):
            bpy.ops.object.parent_set(type="OBJECT", keep_transform=True)

        with select_object(separate_model.jointGroupObject(), objects=[separate_model.jointGroupObject()] + list(separate_joints)):
            bpy.ops.object.parent_set(type="OBJECT", keep_transform=True)

        # move separate objects to new collection
        mmd_layer_collection = FnContext.find_user_layer_collection_by_object(context, mmd_root_object)
        assert mmd_layer_collection is not None

        separate_layer_collection = FnContext.find_user_layer_collection_by_object(context, separate_root_object)
        assert separate_layer_collection is not None

        if mmd_layer_collection.name != separate_layer_collection.name:
            for separate_object in itertools.chain(separate_mesh_objects, separate_rigid_bodies, separate_joints):
                separate_layer_collection.collection.objects.link(separate_object)
                mmd_layer_collection.collection.objects.unlink(separate_object)

        FnModel.copy_mmd_root(
            separate_root_object,
            mmd_root_object,
            overwrite=True,
            replace_name2values={
                # replace related_mesh property values
                "related_mesh": {m.data.name: s.data.name for m, s in model2separate_mesh_objects.items()},
            },
        )

        FnContext.set_active_and_select_single_object(context, separate_root_object)

    def select_weighted_vertices(self, mmd_model_mesh_objects: List[bpy.types.Object], separate_bones: Dict[str, bpy.types.EditBone], deform_bones: Dict[str, bpy.types.EditBone], weight_threshold: float) -> Dict[bpy.types.Object, int]:
        mesh2selected_vertex_count: Dict[bpy.types.Object, int] = {}
        target_bmesh: bmesh.types.BMesh = bmesh.new()
        for mesh_object in mmd_model_mesh_objects:
            vertex_groups: bpy.types.VertexGroups = mesh_object.vertex_groups

            mesh: bpy.types.Mesh = mesh_object.data
            target_bmesh.from_mesh(mesh, face_normals=False)
            target_bmesh.select_mode |= {"VERT"}
            deform_layer = target_bmesh.verts.layers.deform.verify()

            selected_vertex_count = 0
            vert: bmesh.types.BMVert
            for vert in target_bmesh.verts:
                vert.select_set(False)

                # Find the largest weight vertex group
                weights = [(group_index, weight) for group_index, weight in vert[deform_layer].items() if vertex_groups[group_index].name in deform_bones]

                weights.sort(key=lambda i: vertex_groups[i[0]].name in separate_bones, reverse=True)
                weights.sort(key=itemgetter(1), reverse=True)
                group_index, weight = next(iter(weights), (0, -1))

                if weight < weight_threshold:
                    continue

                if vertex_groups[group_index].name not in separate_bones:
                    continue

                selected_vertex_count += 1
                vert.select_set(True)

            if selected_vertex_count > 0:
                mesh2selected_vertex_count[mesh_object] = selected_vertex_count
                target_bmesh.select_flush_mode()
                target_bmesh.to_mesh(mesh)

            target_bmesh.clear()

        return mesh2selected_vertex_count
