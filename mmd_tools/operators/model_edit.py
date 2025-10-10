# Copyright 2022 MMD Tools authors
# This file is part of MMD Tools.

import itertools
from operator import itemgetter
from typing import Dict, List, Optional, Set

import bmesh
import bpy
import numpy as np
from mathutils import Matrix

from ..bpyutils import FnContext, select_object
from ..core.model import FnModel, Model


class NoModelSelectedError(Exception):
    """Raised when no MMD model is selected."""


class ModelJoinByBonesOperator(bpy.types.Operator):
    bl_idname = "mmd_tools.model_join_by_bones"
    bl_label = "Model Join by Bones"
    bl_description = "Join multiple MMD models into one.\n\nWARNING: To align models before joining, only adjust the root (cross under the model) transformation. Do not move armatures, meshes, rigid bodies, or joints directly as they will not move together.\n\nIMPORTANT: Don't use any of the 'Assembly' functions before using this function. This function requires the models to be in a clean state."
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

        bpy.ops.object.mode_set(mode="OBJECT")
        parent_armature_object = FnModel.find_armature_object(parent_root_object)
        FnContext.set_active_and_select_single_object(context, parent_armature_object)
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
    bl_description = "Separate MMD model into multiple models based on selected bones.\n\nWARNING: This operation will split meshes, armatures, rigid bodies and joints. To move models before separating, only adjust the root (cross under the model) transformation. Do not move armatures, meshes, rigid bodies, or joints directly before separating as they will not move together.\n\nIMPORTANT: Don't use any of the 'Assembly' functions before using this function. This function requires the model to be in a clean state."
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
            self._select_related_ik_bones(target_armature_object)
            if original_active_bone:
                context.active_object.data.edit_bones.active = original_active_bone

        separate_bones: Dict[str, bpy.types.EditBone] = {b.name: b for b in context.selected_bones}
        deform_bones: Dict[str, bpy.types.EditBone] = {b.name: b for b in target_armature_object.data.edit_bones if b.use_deform}
        mmd_root_object: bpy.types.Object = FnModel.find_root_object(context.active_object)
        mmd_model = Model(mmd_root_object)
        mmd_model_mesh_objects: List[bpy.types.Object] = list(mmd_model.meshes())
        mmd_model_mesh_objects = list(self._select_weighted_vertices(mmd_model_mesh_objects, separate_bones, deform_bones, weight_threshold).keys())
        bpy.ops.object.mode_set(mode="OBJECT")

        # Store original transform matrix for root object
        original_matrix_world = mmd_root_object.matrix_world.copy()
        mmd_root_object.matrix_world = Matrix.Identity(4)

        # Reset object visibility
        FnContext.set_active_and_select_single_object(context, mmd_root_object)
        bpy.ops.mmd_tools.reset_object_visibility()

        # Clean additional transform
        FnContext.set_active_and_select_single_object(context, mmd_root_object)
        bpy.ops.mmd_tools.clean_additional_transform()

        # Create new separate model first
        separate_model: Model = Model.create(mmd_root_object.mmd_root.name, mmd_root_object.mmd_root.name_e, mmd_scale, obj_name=mmd_root_object.name, add_root_bone=False)
        separate_model.initialDisplayFrames()
        separate_root_object = separate_model.rootObject()
        separate_root_object.matrix_world = mmd_root_object.matrix_world
        separate_model_armature_object = separate_model.armature()

        # Now separate armature bones from original model
        separate_armature_object: Optional[bpy.types.Object] = None
        if self.separate_armature:
            FnContext.set_active_and_select_single_object(context, target_armature_object)
            bpy.ops.object.mode_set(mode="EDIT")

            # Re-select the bones that should be separated (they might have been deselected)
            for bone_name in separate_bones.keys():
                if bone_name in target_armature_object.data.edit_bones:
                    target_armature_object.data.edit_bones[bone_name].select = True

            bpy.ops.armature.separate()
            separate_armature_object = next(iter([a for a in context.selected_objects if a != target_armature_object and a.type == "ARMATURE"]), None)
        bpy.ops.object.mode_set(mode="OBJECT")

        # Collect separate rigid bodies
        separate_rigid_bodies: Set[bpy.types.Object] = {rigid_body_object for rigid_body_object in mmd_model.rigidBodies() if rigid_body_object.mmd_rigid.bone in separate_bones}

        boundary_joint_owner_condition = any if self.boundary_joint_owner == "DESTINATION" else all

        # Collect separate joints
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

        separate_mesh_objects: List[bpy.types.Object] = []
        model2separate_mesh_objects: Dict[bpy.types.Object, bpy.types.Object] = {}
        if len(mmd_model_mesh_objects) > 0:
            # Find a single unique attribute name that doesn't conflict with any existing attributes.
            all_attribute_names = {attr.name for obj in mmd_model_mesh_objects for attr in obj.data.attributes}
            temp_normal_name = "mmd_temp_normal"
            i = 0
            while temp_normal_name in all_attribute_names:
                temp_normal_name = f"mmd_temp_normal.{i:03d}"
                i += 1

            # Backup custom normals to the unique temporary attribute.
            for mesh_obj in mmd_model_mesh_objects:
                mesh_data = mesh_obj.data
                existing_custom_normal = mesh_data.attributes.get("custom_normal")
                if not existing_custom_normal:
                    continue

                if existing_custom_normal.data_type == "INT16_2D":
                    normals_data = np.empty(len(mesh_data.loops) * 2, dtype=np.int16)
                    existing_custom_normal.data.foreach_get("value", normals_data)
                    temp_normal_attr = mesh_data.attributes.new(temp_normal_name, "INT16_2D", "CORNER")
                    temp_normal_attr.data.foreach_set("value", normals_data)
                else:
                    raise TypeError(f"Unsupported custom_normal data type: '{existing_custom_normal.data_type}'. Supported types: 'INT16_2D'")

            # Select meshes
            obj: bpy.types.Object
            for obj in context.view_layer.objects:
                obj.select_set(obj in mmd_model_mesh_objects)
            context.view_layer.objects.active = mmd_model_mesh_objects[0]

            # Separate mesh by selected vertices
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.separate(type="SELECTED")
            separate_mesh_objects = [m for m in context.selected_objects if m.type == "MESH" and m not in mmd_model_mesh_objects]
            bpy.ops.object.mode_set(mode="OBJECT")

            model2separate_mesh_objects = dict(zip(mmd_model_mesh_objects, separate_mesh_objects, strict=False))

            # Restore normal data for all meshes (original and separated)
            all_mesh_objects = list(mmd_model_mesh_objects) + list(separate_mesh_objects)
            for mesh_obj in all_mesh_objects:
                mesh_data = mesh_obj.data
                temp_normal_attr = mesh_data.attributes.get(temp_normal_name)
                if not temp_normal_attr:
                    continue

                try:
                    if temp_normal_attr.data_type == "INT16_2D":
                        normals_data = np.empty(len(mesh_data.loops) * 2, dtype=np.int16)
                        temp_normal_attr.data.foreach_get("value", normals_data)
                        custom_normal_attr = mesh_data.attributes.get("custom_normal")
                        if not custom_normal_attr:
                            custom_normal_attr = mesh_data.attributes.new("custom_normal", "INT16_2D", "CORNER")
                        custom_normal_attr.data.foreach_set("value", normals_data)
                    else:
                        raise TypeError(f"Unsupported custom_normal data type: '{temp_normal_attr.data_type}'. Supported types: 'INT16_2D'")
                finally:
                    mesh_data.attributes.remove(temp_normal_attr)

        if self.separate_armature and separate_armature_object:
            separate_armature_data = separate_armature_object.data
            with select_object(separate_model_armature_object, objects=[separate_model_armature_object, separate_armature_object]):
                bpy.ops.object.join()
            if separate_armature_data.users == 0:
                bpy.data.armatures.remove(separate_armature_data)

        if separate_mesh_objects:
            with select_object(separate_model_armature_object, objects=[separate_model_armature_object] + separate_mesh_objects):
                bpy.ops.object.parent_set(type="OBJECT", keep_transform=True)

        # Replace mesh armature modifier.object
        for separate_mesh in separate_mesh_objects:
            armature_modifier: Optional[bpy.types.ArmatureModifier] = next(iter([m for m in separate_mesh.modifiers if m.type == "ARMATURE"]), None)
            if armature_modifier is None:
                armature_modifier: bpy.types.ArmatureModifier = separate_mesh.modifiers.new("mmd_armature", "ARMATURE")

            armature_modifier.object = separate_model_armature_object

        if separate_rigid_bodies:
            with select_object(separate_model.rigidGroupObject(), objects=[separate_model.rigidGroupObject()] + list(separate_rigid_bodies)):
                bpy.ops.object.parent_set(type="OBJECT", keep_transform=True)

        if separate_joints:
            with select_object(separate_model.jointGroupObject(), objects=[separate_model.jointGroupObject()] + list(separate_joints)):
                bpy.ops.object.parent_set(type="OBJECT", keep_transform=True)

        # Move separate objects to new collection
        mmd_layer_collection = FnContext.find_user_layer_collection_by_object(context, mmd_root_object)
        assert mmd_layer_collection is not None

        separate_layer_collection = FnContext.find_user_layer_collection_by_object(context, separate_root_object)
        assert separate_layer_collection is not None

        if mmd_layer_collection.name != separate_layer_collection.name:
            for separate_object in itertools.chain(separate_mesh_objects, separate_rigid_bodies, separate_joints):
                if separate_object.name not in separate_layer_collection.collection.objects:
                    separate_layer_collection.collection.objects.link(separate_object)
                if separate_object.name in mmd_layer_collection.collection.objects:
                    mmd_layer_collection.collection.objects.unlink(separate_object)

        FnModel.copy_mmd_root(
            separate_root_object,
            mmd_root_object,
            overwrite=True,
            replace_name2values={
                # Replace related_mesh property values
                "related_mesh": {m.data.name: s.data.name for m, s in model2separate_mesh_objects.items()},
            },
        )

        # Apply additional transform
        FnContext.set_active_and_select_single_object(context, mmd_root_object)
        bpy.ops.mmd_tools.apply_additional_transform()
        FnContext.set_active_and_select_single_object(context, separate_root_object)
        bpy.ops.mmd_tools.apply_additional_transform()

        # Restore original transform matrix for root object
        mmd_root_object.matrix_world = original_matrix_world
        separate_root_object.matrix_world = original_matrix_world

        # End state
        FnContext.set_active_and_select_single_object(context, separate_root_object)

    def _select_weighted_vertices(self, mmd_model_mesh_objects: List[bpy.types.Object], separate_bones: Dict[str, bpy.types.EditBone], deform_bones: Dict[str, bpy.types.EditBone], weight_threshold: float) -> Dict[bpy.types.Object, int]:
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

    def _select_related_ik_bones(self, armature_object: bpy.types.Object) -> None:
        """
        Expand the current selection to include any full IK systems that are
        partially selected. An IK system includes the chain bones, the IK
        target bone, and the pole target bone.

        NOTE: This method operates entirely in EDIT mode and avoids mode switching
        to prevent segmentation faults.
        """
        edit_bones = armature_object.data.edit_bones
        initial_selection_names = {b.name for b in edit_bones if b.select}

        # Access pose bones constraints directly without mode switching
        pose_bones = armature_object.pose.bones

        # Find all complete IK systems
        ik_systems = []

        for pose_bone in pose_bones:
            for constraint in pose_bone.constraints:
                if constraint.type == "IK":
                    # Build the set of bones in this IK system
                    system_bones = {pose_bone.name}

                    # Add the main IK Target bone
                    if constraint.target and constraint.subtarget:
                        system_bones.add(constraint.subtarget)

                    # Add the Pole Target bone
                    if constraint.pole_target and constraint.pole_subtarget:
                        system_bones.add(constraint.pole_subtarget)

                    # Add all other bones in the IK chain
                    current_bone_name = pose_bone.name
                    chain_count = constraint.chain_count

                    # Walk up the parent chain
                    for _ in range(chain_count - 1):
                        if current_bone_name not in edit_bones:
                            break
                        current_bone = edit_bones[current_bone_name]
                        if not current_bone.parent:
                            break
                        current_bone_name = current_bone.parent.name
                        system_bones.add(current_bone_name)

                    ik_systems.append(system_bones)

        # Expand selection to include any related, full IK systems
        final_selection_names = set(initial_selection_names)
        for system in ik_systems:
            if not system.isdisjoint(initial_selection_names):
                final_selection_names.update(system)

        # Apply the final selection
        for bone in edit_bones:
            bone.select = bone.name in final_selection_names
