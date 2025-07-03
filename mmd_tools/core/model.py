# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

import itertools
import logging
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Iterator, Optional, Set, TypeGuard, Union, cast

import bpy
import idprop
import rna_prop_ui
from mathutils import Vector

from .. import MMD_TOOLS_VERSION, bpyutils
from ..bpyutils import FnContext, Props
from . import rigid_body
from .morph import FnMorph
from .rigid_body import MODE_DYNAMIC, MODE_DYNAMIC_BONE, MODE_STATIC

if TYPE_CHECKING:
    from ..properties.rigid_body import MMDRigidBody


class FnModel:
    @staticmethod
    def copy_mmd_root(destination_root_object: bpy.types.Object, source_root_object: bpy.types.Object, overwrite: bool = True, replace_name2values: Dict[str, Dict[Any, Any]] = None):
        FnModel.__copy_property(destination_root_object.mmd_root, source_root_object.mmd_root, overwrite=overwrite, replace_name2values=replace_name2values or {})

    @staticmethod
    def find_root_object(obj: Optional[bpy.types.Object]) -> Optional[bpy.types.Object]:
        """Find the root object of the model.
        Args:
            obj (bpy.types.Object): The object to start searching from.
        Returns:
            Optional[bpy.types.Object]: The root object of the model. If the object is not a part of a model, None is returned.
            Generally, the root object is a object with type == "EMPTY" and mmd_type == "ROOT".
        """
        while obj is not None and obj.mmd_type != "ROOT":
            obj = obj.parent
        return obj

    @staticmethod
    def find_armature_object(root_object: Optional[bpy.types.Object]) -> Optional[bpy.types.Object]:
        """Find the armature object of the model.
        Args:
            root_object (Optional[bpy.types.Object]): The root object of the model.
        Returns:
            Optional[bpy.types.Object]: The armature object of the model. If the model does not have an armature, None is returned.
        """
        if root_object is None:
            return None
        for o in root_object.children:
            if o.type == "ARMATURE":
                return o
        return None

    @staticmethod
    def find_rigid_group_object(root_object: Optional[bpy.types.Object]) -> Optional[bpy.types.Object]:
        if root_object is None:
            return None
        for o in root_object.children:
            if o.type == "EMPTY" and o.mmd_type == "RIGID_GRP_OBJ":
                return o
        return None

    @staticmethod
    def __new_group_object(context: bpy.types.Context, name: str, mmd_type: str, parent: bpy.types.Object) -> bpy.types.Object:
        group_object = FnContext.new_and_link_object(context, name=name, object_data=None)
        group_object.mmd_type = mmd_type
        group_object.parent = parent
        group_object.hide_set(True)
        group_object.hide_select = True
        group_object.lock_rotation = group_object.lock_location = group_object.lock_scale = [True, True, True]
        return group_object

    @staticmethod
    def ensure_rigid_group_object(context: bpy.types.Context, root_object: bpy.types.Object) -> bpy.types.Object:
        if root_object is None:
            raise ValueError("root_object cannot be None")
        rigid_group_object = FnModel.find_rigid_group_object(root_object)
        if rigid_group_object is not None:
            return rigid_group_object
        return FnModel.__new_group_object(context, name="rigidbodies", mmd_type="RIGID_GRP_OBJ", parent=root_object)

    @staticmethod
    def find_joint_group_object(root_object: Optional[bpy.types.Object]) -> Optional[bpy.types.Object]:
        if root_object is None:
            return None
        for o in root_object.children:
            if o.type == "EMPTY" and o.mmd_type == "JOINT_GRP_OBJ":
                return o
        return None

    @staticmethod
    def ensure_joint_group_object(context: bpy.types.Context, root_object: bpy.types.Object) -> bpy.types.Object:
        if root_object is None:
            raise ValueError("root_object cannot be None")
        joint_group_object = FnModel.find_joint_group_object(root_object)
        if joint_group_object is not None:
            return joint_group_object
        return FnModel.__new_group_object(context, name="joints", mmd_type="JOINT_GRP_OBJ", parent=root_object)

    @staticmethod
    def find_temporary_group_object(root_object: Optional[bpy.types.Object]) -> Optional[bpy.types.Object]:
        if root_object is None:
            return None
        for o in root_object.children:
            if o.type == "EMPTY" and o.mmd_type == "TEMPORARY_GRP_OBJ":
                return o
        return None

    @staticmethod
    def ensure_temporary_group_object(context: bpy.types.Context, root_object: bpy.types.Object) -> bpy.types.Object:
        if root_object is None:
            raise ValueError("root_object cannot be None")
        temporary_group_object = FnModel.find_temporary_group_object(root_object)
        if temporary_group_object is not None:
            return temporary_group_object
        return FnModel.__new_group_object(context, name="temporary", mmd_type="TEMPORARY_GRP_OBJ", parent=root_object)

    @staticmethod
    def find_bone_order_mesh_object(root_object: Optional[bpy.types.Object]) -> Optional[bpy.types.Object]:
        if root_object is None:
            return None
        armature_object = FnModel.find_armature_object(root_object)
        if armature_object is None:
            return None

        for o in armature_object.children:
            if o.type == "MESH" and "mmd_armature" in o.modifiers:
                return o
        return None

    @staticmethod
    def find_mesh_object_by_name(root_object: Optional[bpy.types.Object], name: str) -> Optional[bpy.types.Object]:
        if root_object is None:
            return None
        if not name:
            return None

        for o in FnModel.iterate_mesh_objects(root_object):
            if o.name == name or (hasattr(o.data, "name") and o.data.name == name):
                return o
        return None

    @staticmethod
    def iterate_child_objects(obj: Optional[bpy.types.Object]) -> Iterator[bpy.types.Object]:
        if obj is None:
            return iter(())
        for child in obj.children:
            yield child
            yield from FnModel.iterate_child_objects(child)

    @staticmethod
    def iterate_filtered_child_objects(condition_function: Callable[[bpy.types.Object], bool], obj: Optional[bpy.types.Object]) -> Iterator[bpy.types.Object]:
        if obj is None:
            return iter(())
        return FnModel.__iterate_filtered_child_objects_internal(condition_function, obj)

    @staticmethod
    def __iterate_filtered_child_objects_internal(condition_function: Callable[[bpy.types.Object], bool], obj: bpy.types.Object) -> Iterator[bpy.types.Object]:
        for child in obj.children:
            if condition_function(child):
                yield child
            yield from FnModel.__iterate_filtered_child_objects_internal(condition_function, child)

    @staticmethod
    def __iterate_child_mesh_objects(obj: Optional[bpy.types.Object]) -> Iterator[bpy.types.Object]:
        return FnModel.iterate_filtered_child_objects(FnModel.is_mesh_object, obj)

    @staticmethod
    def iterate_mesh_objects(root_object: Optional[bpy.types.Object]) -> Iterator[bpy.types.Object]:
        if root_object is None:
            return iter(())
        return FnModel.__iterate_child_mesh_objects(FnModel.find_armature_object(root_object))

    @staticmethod
    def iterate_rigid_body_objects(root_object: Optional[bpy.types.Object]) -> Iterator[bpy.types.Object]:
        if root_object is None:
            return iter(())
        if root_object.mmd_root.is_built:
            return itertools.chain(
                FnModel.iterate_filtered_child_objects(FnModel.is_rigid_body_object, FnModel.find_armature_object(root_object)),
                FnModel.iterate_filtered_child_objects(FnModel.is_rigid_body_object, FnModel.find_rigid_group_object(root_object)),
            )
        return FnModel.iterate_filtered_child_objects(FnModel.is_rigid_body_object, FnModel.find_rigid_group_object(root_object))

    @staticmethod
    def iterate_joint_objects(root_object: Optional[bpy.types.Object]) -> Iterator[bpy.types.Object]:
        if root_object is None:
            return iter(())
        return FnModel.iterate_filtered_child_objects(FnModel.is_joint_object, FnModel.find_joint_group_object(root_object))

    @staticmethod
    def iterate_temporary_objects(root_object: Optional[bpy.types.Object], rigid_track_only: bool = False) -> Iterator[bpy.types.Object]:
        if root_object is None:
            return iter(())

        rigid_body_objects = FnModel.iterate_filtered_child_objects(FnModel.is_temporary_object, FnModel.find_rigid_group_object(root_object))
        if rigid_track_only:
            return rigid_body_objects

        temporary_group_object = FnModel.find_temporary_group_object(root_object)
        if temporary_group_object is None:
            return rigid_body_objects
        return itertools.chain(rigid_body_objects, FnModel.__iterate_filtered_child_objects_internal(FnModel.is_temporary_object, temporary_group_object))

    @staticmethod
    def iterate_materials(root_object: Optional[bpy.types.Object]) -> Iterator[bpy.types.Material]:
        if root_object is None:
            return iter(())
        return (material for mesh_object in FnModel.iterate_mesh_objects(root_object) for material in cast("bpy.types.Mesh", mesh_object.data).materials if material is not None)

    @staticmethod
    def iterate_unique_materials(root_object: Optional[bpy.types.Object]) -> Iterator[bpy.types.Material]:
        if root_object is None:
            return iter(())
        materials: Dict[bpy.types.Material, None] = {}  # use dict because set does not guarantee the order
        materials.update((material, None) for material in FnModel.iterate_materials(root_object))
        return iter(materials.keys())

    @staticmethod
    def is_root_object(obj: Optional[bpy.types.Object]) -> TypeGuard[bpy.types.Object]:
        return obj is not None and obj.mmd_type == "ROOT"

    @staticmethod
    def is_rigid_body_object(obj: Optional[bpy.types.Object]) -> TypeGuard[bpy.types.Object]:
        return obj is not None and obj.mmd_type == "RIGID_BODY"

    @staticmethod
    def is_joint_object(obj: Optional[bpy.types.Object]) -> TypeGuard[bpy.types.Object]:
        return obj is not None and obj.mmd_type == "JOINT"

    @staticmethod
    def is_temporary_object(obj: Optional[bpy.types.Object]) -> TypeGuard[bpy.types.Object]:
        return obj is not None and obj.mmd_type in {"TRACK_TARGET", "NON_COLLISION_CONSTRAINT", "SPRING_CONSTRAINT", "SPRING_GOAL"}

    @staticmethod
    def is_mesh_object(obj: Optional[bpy.types.Object]) -> TypeGuard[bpy.types.Object]:
        return obj is not None and obj.type == "MESH" and obj.mmd_type == "NONE"

    @staticmethod
    def get_max_bone_id(pose_bones):
        """Find maximum bone ID from pose bones, return -1 if no valid IDs found"""
        max_bone_id = -1
        for bone in pose_bones:
            if not hasattr(bone, "is_mmd_shadow_bone") or not bone.is_mmd_shadow_bone:
                max_bone_id = max(max_bone_id, bone.mmd_bone.bone_id)
        return max_bone_id

    @staticmethod
    def unsafe_change_bone_id(bone: bpy.types.PoseBone, new_bone_id: int, bone_morphs, pose_bones):
        """
        Change bone ID and updates all references without validating if new_bone_id is already in use.
        If new_bone_id is already in use, it may cause conflicts and corrupt existing bone references.
        """
        # Store the original bone_id and change it
        bone_id = bone.mmd_bone.bone_id
        bone.mmd_bone.bone_id = new_bone_id

        # Update all bone_id references in bone morphs
        for bone_morph in bone_morphs:
            for data in bone_morph.data:
                if data.bone_id == bone_id:
                    data.bone_id = new_bone_id

        # Update all additional_transform_bone_id references in pose bones
        for pose_bone in pose_bones:
            if not hasattr(pose_bone, "is_mmd_shadow_bone") or not pose_bone.is_mmd_shadow_bone:
                mmd_bone = pose_bone.mmd_bone
                if mmd_bone.additional_transform_bone_id == bone_id:
                    mmd_bone.additional_transform_bone_id = new_bone_id

        # Update all display_connection_bone_id references in pose bones
        for pose_bone in pose_bones:
            if not hasattr(pose_bone, "is_mmd_shadow_bone") or not pose_bone.is_mmd_shadow_bone:
                mmd_bone = pose_bone.mmd_bone
                if mmd_bone.display_connection_bone_id == bone_id:
                    mmd_bone.display_connection_bone_id = new_bone_id

    @staticmethod
    def safe_change_bone_id(bone: bpy.types.PoseBone, new_bone_id: int, bone_morphs, pose_bones):
        """
        Change bone ID and updates all references safely by detecting and resolving conflicts automatically.
        If new_bone_id is already in use, shifts all conflicting bone IDs sequentially until a gap is found.
        """
        # Validate new_bone_id is non-negative
        if new_bone_id < 0:
            logging.warning(f"Attempted to set negative bone_id ({new_bone_id}) for bone '{bone.name}'. Using 0 instead.")
            new_bone_id = 0

        # Check if new_bone_id is already in use
        bones_using_id = [pb for pb in pose_bones if pb.mmd_bone.bone_id == new_bone_id]

        if bones_using_id:
            # Find all bones that need to be shifted (those with consecutive IDs starting from new_bone_id)
            bones_to_shift = []
            current_id = new_bone_id

            # Sort all pose bones by bone ID
            sorted_bones = sorted([pb for pb in pose_bones if pb.mmd_bone.bone_id >= new_bone_id],
                                key=lambda pb: pb.mmd_bone.bone_id)

            # Add bones to shift until we find a gap
            for pb in sorted_bones:
                if pb.mmd_bone.bone_id == current_id:
                    bones_to_shift.append(pb)
                    current_id += 1
                else:
                    # Found a gap, stop adding bones
                    break

            # Sort by bone ID in descending order to avoid conflicts during shifting
            bones_to_shift.sort(key=lambda pb: pb.mmd_bone.bone_id, reverse=True)

            # Shift bone IDs upward
            for shift_bone in bones_to_shift:
                FnModel.unsafe_change_bone_id(shift_bone, shift_bone.mmd_bone.bone_id + 1, bone_morphs, pose_bones)

        # Now change our target bone's ID
        FnModel.unsafe_change_bone_id(bone, new_bone_id, bone_morphs, pose_bones)

    @staticmethod
    def swap_bone_ids(bone_a, bone_b, bone_morphs, pose_bones):
        """Safely swap bone IDs between two bones and update all references"""
        # Store original IDs
        id_a = bone_a.mmd_bone.bone_id
        id_b = bone_b.mmd_bone.bone_id

        # Check for invalid bone IDs
        if id_a < 0:
            logging.warning(f"Cannot swap bone '{bone_a.name}' with invalid bone_id ({id_a})")
            return
        if id_b < 0:
            logging.warning(f"Cannot swap bone '{bone_b.name}' with invalid bone_id ({id_b})")
            return

        # If both bones have the same ID, no swap needed
        if id_a == id_b:
            return

        # Use temporary ID for three-step swap
        temp_id = FnModel.get_max_bone_id(pose_bones) + 1
        FnModel.unsafe_change_bone_id(bone_a, temp_id, bone_morphs, pose_bones)
        FnModel.unsafe_change_bone_id(bone_b, id_a, bone_morphs, pose_bones)
        FnModel.unsafe_change_bone_id(bone_a, id_b, bone_morphs, pose_bones)

    @staticmethod
    def shift_bone_id(old_bone_id: int, new_bone_id: int, bone_morphs, pose_bones):
        """
        Shifts a bone to a specified ID position within a fixed bone ID order structure.
        Maintains the gap structure of bone IDs unchanged, only changes which bone corresponds to which ID.
        Other bones shift positions to accommodate the change while preserving relative order.
        """
        # Check for invalid bone IDs
        if old_bone_id < 0:
            logging.warning(f"Cannot shift bone with invalid old_bone_id ({old_bone_id})")
            return
        if new_bone_id < 0:
            logging.warning(f"Cannot shift bone to invalid new_bone_id ({new_bone_id})")
            return

        # If source and target IDs are the same, no operation needed
        if old_bone_id == new_bone_id:
            return

        # Get all valid pose bones (exclude shadow bones)
        valid_bones = [pb for pb in pose_bones if not (hasattr(pb, "is_mmd_shadow_bone") and pb.is_mmd_shadow_bone) and pb.mmd_bone.bone_id >= 0]

        # Sort by bone_id
        valid_bones.sort(key=lambda pb: pb.mmd_bone.bone_id)

        # Extract current bone IDs (this order structure must remain unchanged)
        fixed_bone_ids = [pb.mmd_bone.bone_id for pb in valid_bones]

        # Find the bone to move and target position
        old_pos = None
        new_pos = None
        moving_bone = None

        for i, bone in enumerate(valid_bones):
            if bone.mmd_bone.bone_id == old_bone_id:
                old_pos = i
                moving_bone = bone
            if bone.mmd_bone.bone_id == new_bone_id:
                new_pos = i

        # If old_bone_id doesn't exist, return directly
        if old_pos is None or moving_bone is None:
            logging.warning(f"Could not find bone with ID {old_bone_id}")
            return

        # If new_bone_id doesn't exist, use safe_change_bone_id instead
        if new_pos is None:
            FnModel.safe_change_bone_id(moving_bone, new_bone_id, bone_morphs, pose_bones)
            return

        # Create new bone order array
        new_bone_order = valid_bones.copy()

        if old_pos < new_pos:
            # Move right: shift left bones to the right by one position
            for i in range(old_pos, new_pos):
                new_bone_order[i] = valid_bones[i + 1]
            new_bone_order[new_pos] = moving_bone
        else:
            # Move left: shift right bones to the left by one position
            for i in range(old_pos, new_pos, -1):
                new_bone_order[i] = valid_bones[i - 1]
            new_bone_order[new_pos] = moving_bone

        # Reassign bone IDs (using fixed ID order) with conflict resolution
        # Use one temporary ID to perform circular shift, similar to swap_bone_ids approach
        temp_id = FnModel.get_max_bone_id(pose_bones) + 1

        # Perform circular shift using temporary ID
        if old_pos < new_pos:
            # Move right: shift sequence [old_pos+1, new_pos] leftward
            # moving_bone -> temp_id, then shift others left, finally temp_id -> target
            FnModel.unsafe_change_bone_id(moving_bone, temp_id, bone_morphs, pose_bones)
            for i in range(old_pos, new_pos):
                target_id = fixed_bone_ids[i]
                source_bone = valid_bones[i + 1]
                FnModel.unsafe_change_bone_id(source_bone, target_id, bone_morphs, pose_bones)
            FnModel.unsafe_change_bone_id(moving_bone, fixed_bone_ids[new_pos], bone_morphs, pose_bones)
        else:
            # Move left: shift sequence [new_pos, old_pos-1] rightward
            # moving_bone -> temp_id, then shift others right, finally temp_id -> target
            FnModel.unsafe_change_bone_id(moving_bone, temp_id, bone_morphs, pose_bones)
            for i in range(old_pos, new_pos, -1):
                target_id = fixed_bone_ids[i]
                source_bone = valid_bones[i - 1]
                FnModel.unsafe_change_bone_id(source_bone, target_id, bone_morphs, pose_bones)
            FnModel.unsafe_change_bone_id(moving_bone, fixed_bone_ids[new_pos], bone_morphs, pose_bones)

    @staticmethod
    def realign_bone_ids(bone_id_offset: int, bone_morphs, pose_bones, sorting_method: str = "FIX-MOVE-CHILDREN"):
        """Realigns all bone IDs sequentially without gaps for bones displayed in Bone Order Panel."""

        def get_hierarchy_depth(bone):
            """Get the depth of bone in the hierarchy (root bones have depth 0)"""
            depth = 0
            while bone.parent:
                depth += 1
                bone = bone.parent
            return depth

        def bone_hierarchy_path(bone):
            """Build path from root to bone for parent-child hierarchy sorting"""
            path = []
            while bone:
                path.append(bone.name)
                bone = bone.parent
            return tuple(reversed(path))

        def get_fix_key_move_children(bone):
            """Fix mode: move children after their parents (preserve parent positions)"""
            # Find the maximum ID among ALL ancestors in the hierarchy chain
            max_ancestor_id = -1
            temp_parent = bone.parent

            while temp_parent:
                if hasattr(temp_parent, "is_mmd_shadow_bone") and temp_parent.is_mmd_shadow_bone:
                    temp_parent = temp_parent.parent
                    continue

                if temp_parent.mmd_bone.bone_id >= 0:
                    max_ancestor_id = max(max_ancestor_id, temp_parent.mmd_bone.bone_id)
                temp_parent = temp_parent.parent

            current_id = bone.mmd_bone.bone_id

            if max_ancestor_id >= 0 and current_id >= 0 and max_ancestor_id >= current_id:
                # This bone needs to be moved after ALL ancestors
                # Use max ancestor ID + small offset + hierarchy depth for stable sorting
                return (1, max_ancestor_id + 0.1, get_hierarchy_depth(bone), bone.name)
            # Keep original position
            return (0, current_id if current_id >= 0 else float("inf"), bone.name)

        # Get valid bones (non-shadow bones)
        valid_bones = [pb for pb in pose_bones if not (hasattr(pb, "is_mmd_shadow_bone") and pb.is_mmd_shadow_bone)]

        # Choose sorting method
        if sorting_method == "REBUILD-DEPTH":
            # Sort by hierarchy depth, then name (allows chain mixing)
            valid_bones.sort(key=lambda pb: (get_hierarchy_depth(pb), pb.name))
        elif sorting_method == "REBUILD-PATH":
            # Sort by hierarchy path (keeps bone chains together)
            valid_bones.sort(key=bone_hierarchy_path)
        else:  # Default to "FIX-MOVE-CHILDREN"
            # Fix mode: move children after parents (preserve parent positions)
            valid_bones.sort(key=get_fix_key_move_children)

        # Reassign IDs sequentially
        for i, bone in enumerate(valid_bones):
            new_id = bone_id_offset + i
            if bone.mmd_bone.bone_id != new_id:
                FnModel.safe_change_bone_id(bone, new_id, bone_morphs, pose_bones)

    @staticmethod
    def join_models(parent_root_object: bpy.types.Object, child_root_objects: Iterable[bpy.types.Object]):
        # Ensure we are in object mode
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        parent_armature_object = FnModel.find_armature_object(parent_root_object)

        # Deselect all objects to ensure a clean selection state before operations
        bpy.ops.object.select_all(action="DESELECT")

        # Get the maximum bone ID of parent model's armature to avoid ID conflicts during merging
        max_bone_id = FnModel.get_max_bone_id(parent_armature_object.pose.bones)

        # Process each child model
        for child_root_object in child_root_objects:
            if child_root_object is None:
                continue

            child_armature_object = FnModel.find_armature_object(child_root_object)
            if child_armature_object is None:
                continue

            # Ensure we're in the correct mode
            if bpy.context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            # Update bone IDs
            child_pose_bones = child_armature_object.pose.bones
            child_bone_morphs = child_root_object.mmd_root.bone_morphs

            # Reassign bone IDs to avoid conflicts
            FnModel.realign_bone_ids(max_bone_id + 1, child_bone_morphs, child_pose_bones)
            max_bone_id = FnModel.get_max_bone_id(child_pose_bones)

            # Save material morph references
            related_meshes = {}
            for material_morph in child_root_object.mmd_root.material_morphs:
                for material_morph_data in material_morph.data:
                    if material_morph_data.related_mesh_data is not None:
                        related_meshes[material_morph_data] = material_morph_data.related_mesh_data
                        material_morph_data.related_mesh_data = None

            # Store world coordinate positions of child mesh objects
            child_mesh_transforms = {}
            try:
                for mesh in FnModel.__iterate_child_mesh_objects(child_armature_object):
                    if mesh.name in bpy.context.view_layer.objects.keys():
                        # Store the original world coordinate matrix
                        child_mesh_transforms[mesh.name] = mesh.matrix_world.copy()
            finally:
                # Restore material references
                for material_morph_data, mesh_data in related_meshes.items():
                    material_morph_data.related_mesh_data = mesh_data

            # Merge armatures - using a safer method
            if parent_armature_object and child_armature_object:
                if (parent_armature_object.name in bpy.context.view_layer.objects.keys() and
                    child_armature_object.name in bpy.context.view_layer.objects.keys()):
                    try:
                        # Ensure we're in object mode
                        if bpy.context.mode != "OBJECT":
                            bpy.ops.object.mode_set(mode="OBJECT")

                        # Clear all selections
                        bpy.ops.object.select_all(action="DESELECT")

                        # Select and activate the parent armature
                        parent_armature_object.select_set(True)
                        bpy.context.view_layer.objects.active = parent_armature_object

                        # Select the child armature
                        child_armature_object.select_set(True)

                        # Execute the join - after merging, objects will remain at the parent armature's position
                        bpy.ops.object.join()

                    except Exception:
                        logging.exception("Error joining armatures")
                        # Ensure we exit special modes regardless of what happened
                        if bpy.context.mode != "OBJECT":
                            bpy.ops.object.mode_set(mode="OBJECT")

            # Update mesh armature modifiers and restore positions
            mesh_objects = list(FnModel.__iterate_child_mesh_objects(parent_armature_object))
            for mesh in mesh_objects:
                if mesh.name not in bpy.context.view_layer.objects.keys():
                    continue

                # Handle armature modifiers
                armature_modifier = None
                for mod in mesh.modifiers:
                    if mod.type == "ARMATURE":
                        if mod.name == "mmd_armature" or mod.object is None:
                            armature_modifier = mod
                            break

                if armature_modifier is None:
                    armature_modifier = mesh.modifiers.new("mmd_armature", "ARMATURE")

                armature_modifier.object = parent_armature_object

                # If this mesh was originally part of the child model, restore its world coordinate position
                if mesh.name in child_mesh_transforms:
                    mesh.matrix_world = child_mesh_transforms[mesh.name]

            # Handle rigid bodies
            child_rigid_group_object = FnModel.find_rigid_group_object(child_root_object)
            if child_rigid_group_object and child_rigid_group_object.name in bpy.context.view_layer.objects.keys():
                parent_rigid_group_object = FnModel.find_rigid_group_object(parent_root_object)
                if parent_rigid_group_object and parent_rigid_group_object.name in bpy.context.view_layer.objects.keys():
                    # Safely handle each rigid body
                    rigid_objects = [obj for obj in FnModel.iterate_rigid_body_objects(child_root_object) if obj.name in bpy.context.view_layer.objects.keys()]

                    if rigid_objects:
                        # Ensure we're in object mode
                        if bpy.context.mode != "OBJECT":
                            bpy.ops.object.mode_set(mode="OBJECT")

                        for rigid_obj in rigid_objects:
                            # Save world coordinate position
                            original_matrix_world = rigid_obj.matrix_world.copy()

                            # Set parent object
                            rigid_obj.parent = parent_rigid_group_object
                            rigid_obj.parent_type = "OBJECT"

                            # Restore world coordinate position
                            rigid_obj.matrix_world = original_matrix_world

                    # Safely remove the original group
                    try:
                        if child_rigid_group_object.name in bpy.data.objects:
                            bpy.data.objects.remove(child_rigid_group_object)
                    except Exception:
                        logging.exception("Error removing rigid group")

            # Handle joints - similar to the rigid body approach
            child_joint_group_object = FnModel.find_joint_group_object(child_root_object)
            if child_joint_group_object and child_joint_group_object.name in bpy.context.view_layer.objects.keys():
                parent_joint_group_object = FnModel.find_joint_group_object(parent_root_object)
                if parent_joint_group_object and parent_joint_group_object.name in bpy.context.view_layer.objects.keys():
                    joint_objects = [obj for obj in FnModel.iterate_joint_objects(child_root_object) if obj.name in bpy.context.view_layer.objects.keys()]

                    if joint_objects:
                        # Ensure we're in object mode
                        if bpy.context.mode != "OBJECT":
                            bpy.ops.object.mode_set(mode="OBJECT")

                        for joint_obj in joint_objects:
                            # Save world coordinate position
                            original_matrix_world = joint_obj.matrix_world.copy()

                            # Set parent object
                            joint_obj.parent = parent_joint_group_object
                            joint_obj.parent_type = "OBJECT"

                            # Restore world coordinate position
                            joint_obj.matrix_world = original_matrix_world

                    # Safely remove the original group
                    try:
                        if child_joint_group_object.name in bpy.data.objects:
                            bpy.data.objects.remove(child_joint_group_object)
                    except Exception:
                        logging.exception("Error removing joint group")

            # Handle temporary objects - similar approach
            child_temporary_group_object = FnModel.find_temporary_group_object(child_root_object)
            if child_temporary_group_object and child_temporary_group_object.name in bpy.context.view_layer.objects.keys():
                parent_temporary_group_object = FnModel.find_temporary_group_object(parent_root_object)
                if parent_temporary_group_object and parent_temporary_group_object.name in bpy.context.view_layer.objects.keys():
                    temp_objects = [obj for obj in FnModel.iterate_temporary_objects(child_root_object) if obj.name in bpy.context.view_layer.objects.keys()]

                    if temp_objects:
                        # Ensure we're in object mode
                        if bpy.context.mode != "OBJECT":
                            bpy.ops.object.mode_set(mode="OBJECT")

                        for temp_obj in temp_objects:
                            # Save world coordinate position
                            original_matrix_world = temp_obj.matrix_world.copy()

                            # Set parent object
                            temp_obj.parent = parent_temporary_group_object
                            temp_obj.parent_type = "OBJECT"

                            # Restore world coordinate position
                            temp_obj.matrix_world = original_matrix_world

                    # Safely remove child objects and groups
                    try:
                        child_objects = [obj for obj in FnModel.iterate_child_objects(child_temporary_group_object) if obj.name in bpy.data.objects]
                        for obj in child_objects:
                            bpy.data.objects.remove(obj)

                        if child_temporary_group_object.name in bpy.data.objects:
                            bpy.data.objects.remove(child_temporary_group_object)
                    except Exception:
                        logging.exception("Error removing temporary objects")

            # Copy MMD root properties
            try:
                FnModel.copy_mmd_root(parent_root_object, child_root_object, overwrite=False)
            except Exception:
                logging.exception("Error copying MMD root")

            # Safely remove empty child root objects
            try:
                if child_root_object and len(child_root_object.children) == 0:
                    if child_root_object.name in bpy.data.objects:
                        bpy.data.objects.remove(child_root_object)
            except Exception:
                logging.exception("Error removing child root object")

        # Clean and reapply additional transformations to properly set up all bones and constraints
        bpy.ops.mmd_tools.clean_additional_transform()
        bpy.ops.mmd_tools.apply_additional_transform()

    @staticmethod
    def _add_armature_modifier(mesh_object: bpy.types.Object, armature_object: bpy.types.Object) -> bpy.types.ArmatureModifier:
        for m in mesh_object.modifiers:
            if m.type != "ARMATURE":
                continue
            # already has armature modifier.
            return cast("bpy.types.ArmatureModifier", m)

        modifier = cast("bpy.types.ArmatureModifier", mesh_object.modifiers.new(name="Armature", type="ARMATURE"))
        modifier.object = armature_object
        modifier.use_vertex_groups = True
        modifier.name = "mmd_armature"

        return modifier

    @staticmethod
    def attach_mesh_objects(parent_root_object: bpy.types.Object, mesh_objects: Iterable[bpy.types.Object], add_armature_modifier: bool):
        armature_object = FnModel.find_armature_object(parent_root_object)
        if armature_object is None:
            raise ValueError(f"Armature object not found in {parent_root_object}")

        def __get_root_object(obj: bpy.types.Object) -> bpy.types.Object:
            if obj.parent is None:
                return obj
            return __get_root_object(obj.parent)

        for mesh_object in mesh_objects:
            if not FnModel.is_mesh_object(mesh_object):
                continue

            mesh_root_object = __get_root_object(mesh_object)
            original_matrix_world = mesh_root_object.matrix_world
            mesh_root_object.parent_type = "OBJECT"
            mesh_root_object.parent = armature_object
            mesh_root_object.matrix_world = original_matrix_world

            if add_armature_modifier:
                FnModel._add_armature_modifier(mesh_object, armature_object)

    @staticmethod
    def add_missing_vertex_groups_from_bones(root_object: bpy.types.Object, mesh_object: bpy.types.Object, search_in_all_meshes: bool):
        armature_object = FnModel.find_armature_object(root_object)
        if armature_object is None:
            raise ValueError(f"Armature object not found in {root_object}")

        vertex_group_names: Set[str] = set()

        search_meshes = FnModel.iterate_mesh_objects(root_object) if search_in_all_meshes else [mesh_object]

        for search_mesh in search_meshes:
            vertex_group_names.update(search_mesh.vertex_groups.keys())

        pose_bone: bpy.types.PoseBone
        for pose_bone in armature_object.pose.bones:
            pose_bone_name = pose_bone.name

            if pose_bone_name in vertex_group_names:
                continue

            if pose_bone_name.startswith("_"):
                continue

            mesh_object.vertex_groups.new(name=pose_bone_name)

    @staticmethod
    def change_mmd_ik_loop_factor(root_object: bpy.types.Object, new_ik_loop_factor: int):
        mmd_root = root_object.mmd_root
        old_ik_loop_factor = mmd_root.ik_loop_factor

        if new_ik_loop_factor == old_ik_loop_factor:
            return

        armature_object = FnModel.find_armature_object(root_object)
        for pose_bone in armature_object.pose.bones:
            for constraint in (cast("bpy.types.KinematicConstraint", c) for c in pose_bone.constraints if c.type == "IK"):
                iterations = int(constraint.iterations * new_ik_loop_factor / old_ik_loop_factor)
                logging.info("Update %s of %s: %d -> %d", constraint.name, pose_bone.name, constraint.iterations, iterations)
                constraint.iterations = iterations

        mmd_root.ik_loop_factor = new_ik_loop_factor

        return

    @staticmethod
    def __copy_property_group(destination: bpy.types.PropertyGroup, source: bpy.types.PropertyGroup, overwrite: bool, replace_name2values: Dict[str, Dict[Any, Any]]):
        destination_rna_properties = destination.bl_rna.properties
        for name in source.keys():
            is_attr = hasattr(source, name)
            value = getattr(source, name) if is_attr else source[name]
            if isinstance(value, bpy.types.PropertyGroup):
                FnModel.__copy_property_group(getattr(destination, name) if is_attr else destination[name], value, overwrite=overwrite, replace_name2values=replace_name2values)
            elif isinstance(value, bpy.types.bpy_prop_collection):
                FnModel.__copy_collection_property(getattr(destination, name) if is_attr else destination[name], value, overwrite=overwrite, replace_name2values=replace_name2values)
            elif isinstance(value, idprop.types.IDPropertyArray):
                pass
                # _copy_collection_property(getattr(destination, name) if is_attr else destination[name], value, overwrite=overwrite, replace_name2values=replace_name2values)
            else:
                value2values = replace_name2values.get(name)
                if value2values is not None:
                    replace_value = value2values.get(value)
                    if replace_value is not None:
                        value = replace_value

                if overwrite or destination_rna_properties[name].default == getattr(destination, name) if is_attr else destination[name]:
                    if is_attr:
                        setattr(destination, name, value)
                    else:
                        destination[name] = value

    @staticmethod
    def __copy_collection_property(destination: bpy.types.bpy_prop_collection, source: bpy.types.bpy_prop_collection, overwrite: bool, replace_name2values: Dict[str, Dict[Any, Any]]):
        if overwrite:
            destination.clear()

        len_source = len(source)
        if len_source == 0:
            return

        source_names: Set[str] = set(source.keys())
        if len(source_names) == len_source and source[0].name != "":
            # names work
            destination_names: Set[str] = set(destination.keys())

            missing_names = source_names - destination_names

            destination_index = 0
            for name, value in source.items():
                if name in missing_names:
                    new_element = destination.add()
                    new_element["name"] = name

                FnModel.__copy_property(destination[name], value, overwrite=overwrite, replace_name2values=replace_name2values)
                destination.move(destination.find(name), destination_index)
                destination_index += 1
        else:
            # names not work
            while len_source > len(destination):
                destination.add()

            for index, name in enumerate(source.keys()):
                FnModel.__copy_property(destination[index], source[index], overwrite=True, replace_name2values=replace_name2values)

    @staticmethod
    def __copy_property(destination: Union[bpy.types.PropertyGroup, bpy.types.bpy_prop_collection], source: Union[bpy.types.PropertyGroup, bpy.types.bpy_prop_collection], overwrite: bool, replace_name2values: Dict[str, Dict[Any, Any]]):
        if isinstance(destination, bpy.types.PropertyGroup):
            FnModel.__copy_property_group(destination, source, overwrite=overwrite, replace_name2values=replace_name2values)
        elif isinstance(destination, bpy.types.bpy_prop_collection):
            FnModel.__copy_collection_property(destination, source, overwrite=overwrite, replace_name2values=replace_name2values)
        else:
            raise ValueError(f"Unsupported destination: {destination}")

    @staticmethod
    def initalize_display_item_frames(root_object: bpy.types.Object, reset: bool = True):
        frames = root_object.mmd_root.display_item_frames
        if reset and len(frames) > 0:
            root_object.mmd_root.active_display_item_frame = 0
            frames.clear()

        frame_names = {"Root": "Root", "表情": "Facial"}

        for frame_name, frame_name_e in frame_names.items():
            frame = frames.get(frame_name, None) or frames.add()
            frame.name = frame_name
            frame.name_e = frame_name_e
            frame.is_special = True

        arm = FnModel.find_armature_object(root_object)
        if arm is not None and len(arm.data.bones) > 0 and len(frames[0].data) < 1:
            item = frames[0].data.add()
            item.type = "BONE"
            item.name = arm.data.bones[0].name

        if not reset:
            frames.move(frames.find("Root"), 0)
            frames.move(frames.find("表情"), 1)

    @staticmethod
    def get_empty_display_size(root_object: bpy.types.Object) -> float:
        return getattr(root_object, Props.empty_display_size)


class MigrationFnModel:
    """Migration Functions for old MMD models broken by bugs or issues"""

    @classmethod
    def update_mmd_ik_loop_factor(cls):
        for armature_object in bpy.data.objects:
            if armature_object.type != "ARMATURE":
                continue

            if "mmd_ik_loop_factor" not in armature_object:
                return

            FnModel.find_root_object(armature_object).mmd_root.ik_loop_factor = max(armature_object["mmd_ik_loop_factor"], 1)
            del armature_object["mmd_ik_loop_factor"]

    @staticmethod
    def update_mmd_tools_version():
        for root_object in bpy.data.objects:
            if root_object.type != "EMPTY":
                continue

            if not FnModel.is_root_object(root_object):
                continue

            if "mmd_tools_version" in root_object:
                continue

            root_object["mmd_tools_version"] = "2.8.0"


class Model:
    def __init__(self, root_obj):
        if root_obj is None:
            raise ValueError("must be MMD ROOT type object")
        if root_obj.mmd_type != "ROOT":
            raise ValueError("must be MMD ROOT type object")
        self.__root: bpy.types.Object = getattr(root_obj, "original", root_obj)
        self.__arm: Optional[bpy.types.Object] = None
        self.__rigid_grp: Optional[bpy.types.Object] = None
        self.__joint_grp: Optional[bpy.types.Object] = None
        self.__temporary_grp: Optional[bpy.types.Object] = None

    @staticmethod
    def create(name: str, name_e: str = "", scale: float = 1, obj_name: Optional[str] = None, armature_object: Optional[bpy.types.Object] = None, add_root_bone: bool = False):
        if obj_name is None:
            obj_name = name

        context = FnContext.ensure_context()

        root: bpy.types.Object = bpy.data.objects.new(name=obj_name, object_data=None)
        root.mmd_type = "ROOT"
        root.mmd_root.name = name
        root.mmd_root.name_e = name_e
        root["mmd_tools_version"] = MMD_TOOLS_VERSION
        setattr(root, Props.empty_display_size, scale / 0.2)
        FnContext.link_object(context, root)

        if armature_object:
            m = armature_object.matrix_world
            armature_object.parent_type = "OBJECT"
            armature_object.parent = root
            # armature_object.matrix_world = m
            root.matrix_world = m
            armature_object.matrix_local.identity()
        else:
            armature_object = bpy.data.objects.new(name=obj_name + "_arm", object_data=bpy.data.armatures.new(name=obj_name))
            armature_object.parent = root
            FnContext.link_object(context, armature_object)
        armature_object.lock_rotation = armature_object.lock_location = armature_object.lock_scale = [True, True, True]
        setattr(armature_object, Props.show_in_front, True)
        setattr(armature_object, Props.display_type, "WIRE")

        from .bone import FnBone

        FnBone.setup_special_bone_collections(armature_object)

        if add_root_bone:
            bone_name = "全ての親"
            bone_name_english = "Root"

            # Create the root bone
            with bpyutils.edit_object(armature_object) as data:
                bone = data.edit_bones.new(name=bone_name)
                bone.head = (0.0, 0.0, 0.0)
                bone.tail = (0.0, 0.0, getattr(root, Props.empty_display_size))

            # Set MMD bone properties
            pose_bone = armature_object.pose.bones[bone_name]
            pose_bone.mmd_bone.name_j = bone_name
            pose_bone.mmd_bone.name_e = bone_name_english

            # Create a bone collection named "Root"
            bone_collection_name = bone_name_english
            bone_collection = armature_object.data.collections.new(name=bone_collection_name)

            # Assign the new bone to the bone collection
            data_bone = armature_object.data.bones[bone_name]
            bone_collection.assign(data_bone)

        FnContext.set_active_and_select_single_object(context, root)
        return Model(root)

    @staticmethod
    def findRoot(obj: bpy.types.Object) -> Optional[bpy.types.Object]:
        return FnModel.find_root_object(obj)

    def initialDisplayFrames(self, reset=True):
        FnModel.initalize_display_item_frames(self.__root, reset=reset)

    @property
    def morph_slider(self):
        return FnMorph.get_morph_slider(self)

    def loadMorphs(self):
        FnMorph.load_morphs(self)

    def create_ik_constraint(self, bone, ik_target):
        """Create IK constraint

        Args:
            bone: A pose bone to add a IK constraint
            ik_target: A pose bone for IK target

        Returns:
            The bpy.types.KinematicConstraint object created. It is set target
            and subtarget options.

        """
        ik_target_name = ik_target.name
        ik_const = bone.constraints.new("IK")
        ik_const.target = self.__arm
        ik_const.subtarget = ik_target_name
        return ik_const

    def allObjects(self, obj: Optional[bpy.types.Object] = None) -> Iterator[bpy.types.Object]:
        if obj is None:
            obj: bpy.types.Object = self.__root
        yield obj
        yield from FnModel.iterate_child_objects(obj)

    def rootObject(self) -> bpy.types.Object:
        return self.__root

    def armature(self) -> bpy.types.Object:
        if self.__arm is None:
            self.__arm = FnModel.find_armature_object(self.__root)
            assert self.__arm is not None
        return self.__arm

    def hasRigidGroupObject(self) -> bool:
        return FnModel.find_rigid_group_object(self.__root) is not None

    def rigidGroupObject(self) -> bpy.types.Object:
        if self.__rigid_grp is None:
            self.__rigid_grp = FnModel.find_rigid_group_object(self.__root)
            if self.__rigid_grp is None:
                rigids = bpy.data.objects.new(name="rigidbodies", object_data=None)
                FnContext.link_object(FnContext.ensure_context(), rigids)
                rigids.mmd_type = "RIGID_GRP_OBJ"
                rigids.parent = self.__root
                rigids.hide_set(True)
                rigids.hide_select = True
                rigids.lock_rotation = rigids.lock_location = rigids.lock_scale = [True, True, True]
                self.__rigid_grp = rigids
        return self.__rigid_grp

    def hasJointGroupObject(self) -> bool:
        return FnModel.find_joint_group_object(self.__root) is not None

    def jointGroupObject(self) -> bpy.types.Object:
        if self.__joint_grp is None:
            self.__joint_grp = FnModel.find_joint_group_object(self.__root)
            if self.__joint_grp is None:
                joints = bpy.data.objects.new(name="joints", object_data=None)
                FnContext.link_object(FnContext.ensure_context(), joints)
                joints.mmd_type = "JOINT_GRP_OBJ"
                joints.parent = self.__root
                joints.hide_set(True)
                joints.hide_select = True
                joints.lock_rotation = joints.lock_location = joints.lock_scale = [True, True, True]
                self.__joint_grp = joints
        return self.__joint_grp

    def hasTemporaryGroupObject(self) -> bool:
        return FnModel.find_temporary_group_object(self.__root) is not None

    def temporaryGroupObject(self) -> bpy.types.Object:
        if self.__temporary_grp is None:
            self.__temporary_grp = FnModel.find_temporary_group_object(self.__root)
            if self.__temporary_grp is None:
                temporarys = bpy.data.objects.new(name="temporary", object_data=None)
                FnContext.link_object(FnContext.ensure_context(), temporarys)
                temporarys.mmd_type = "TEMPORARY_GRP_OBJ"
                temporarys.parent = self.__root
                temporarys.hide_set(True)
                temporarys.hide_select = True
                temporarys.lock_rotation = temporarys.lock_location = temporarys.lock_scale = [True, True, True]
                self.__temporary_grp = temporarys
        return self.__temporary_grp

    def meshes(self) -> Iterator[bpy.types.Object]:
        return FnModel.iterate_mesh_objects(self.__root)

    def attachMeshes(self, meshes: Iterator[bpy.types.Object], add_armature_modifier: bool = True):
        FnModel.attach_mesh_objects(self.rootObject(), meshes, add_armature_modifier)

    def firstMesh(self) -> Optional[bpy.types.Object]:
        for i in self.meshes():
            return i
        return None

    def findMesh(self, mesh_name) -> Optional[bpy.types.Object]:
        """Find the mesh by name"""
        if mesh_name == "":
            return None
        for mesh in self.meshes():
            if mesh_name in {mesh.name, mesh.data.name}:
                return mesh
        return None

    def findMeshByIndex(self, index: int) -> Optional[bpy.types.Object]:
        """Find the mesh by index"""
        if index < 0:
            return None
        for i, mesh in enumerate(self.meshes()):
            if i == index:
                return mesh
        return None

    def getMeshIndex(self, mesh_name: str) -> int:
        """Get the index of a mesh. Returns -1 if not found"""
        if mesh_name == "":
            return -1
        for i, mesh in enumerate(self.meshes()):
            if mesh_name in {mesh.name, mesh.data.name}:
                return i
        return -1

    def rigidBodies(self) -> Iterator[bpy.types.Object]:
        return FnModel.iterate_rigid_body_objects(self.__root)

    def joints(self) -> Iterator[bpy.types.Object]:
        return FnModel.iterate_joint_objects(self.__root)

    def temporaryObjects(self, rigid_track_only=False) -> Iterator[bpy.types.Object]:
        return FnModel.iterate_temporary_objects(self.__root, rigid_track_only)

    def materials(self) -> Iterator[bpy.types.Material]:
        """List all materials in all meshes"""
        materials = {}  # Use dict instead of set to guarantee preserve order
        for mesh in self.meshes():
            materials.update((slot.material, 0) for slot in mesh.material_slots if slot.material is not None)
        return iter(materials.keys())

    def renameBone(self, old_bone_name, new_bone_name):
        if old_bone_name == new_bone_name:
            return
        armature = self.armature()
        bone = armature.pose.bones[old_bone_name]
        bone.name = new_bone_name
        new_bone_name = bone.name

        mmd_root = self.rootObject().mmd_root
        for frame in mmd_root.display_item_frames:
            for item in frame.data:
                if item.type == "BONE" and item.name == old_bone_name:
                    item.name = new_bone_name
        for mesh in self.meshes():
            if old_bone_name in mesh.vertex_groups:
                mesh.vertex_groups[old_bone_name].name = new_bone_name

    def build(self, non_collision_distance_scale=1.5, collision_margin=1e-06):
        rigidbody_world_enabled = rigid_body.setRigidBodyWorldEnabled(False)
        if self.__root.mmd_root.is_built:
            self.clean()
        self.__root.mmd_root.is_built = True
        logging.info("****************************************")
        logging.info(" Build rig")
        logging.info("****************************************")
        start_time = time.time()
        self.__preBuild()
        self.disconnectPhysicsBones()
        self.buildRigids(non_collision_distance_scale, collision_margin)
        self.buildJoints()
        self.__postBuild()
        logging.info(" Finished building in %f seconds.", time.time() - start_time)
        rigid_body.setRigidBodyWorldEnabled(rigidbody_world_enabled)

    def clean(self):
        rigidbody_world_enabled = rigid_body.setRigidBodyWorldEnabled(False)
        logging.info("****************************************")
        logging.info(" Clean rig")
        logging.info("****************************************")
        start_time = time.time()

        pose_bones = []
        arm = self.armature()
        if arm is not None:
            pose_bones = arm.pose.bones
        for i in pose_bones:
            if "mmd_tools_rigid_track" in i.constraints:
                const = i.constraints["mmd_tools_rigid_track"]
                i.constraints.remove(const)

        rigid_track_counts = 0
        for i in self.rigidBodies():
            rigid_type = int(i.mmd_rigid.type)
            if "mmd_tools_rigid_parent" not in i.constraints:
                rigid_track_counts += 1
                logging.info('%3d# Create a "CHILD_OF" constraint for %s', rigid_track_counts, i.name)
                i.mmd_rigid.bone = i.mmd_rigid.bone
            relation = i.constraints["mmd_tools_rigid_parent"]
            relation.mute = True
            if rigid_type == rigid_body.MODE_STATIC:
                i.parent_type = "OBJECT"
                i.parent = self.rigidGroupObject()
            elif rigid_type in {rigid_body.MODE_DYNAMIC, rigid_body.MODE_DYNAMIC_BONE}:
                arm = relation.target
                bone_name = relation.subtarget
                if arm is not None and bone_name != "":
                    for c in arm.pose.bones[bone_name].constraints:
                        if c.type == "IK":
                            c.mute = False
            self.__restoreTransforms(i)

        for i in self.joints():
            self.__restoreTransforms(i)

        self.__removeTemporaryObjects()
        self.connectPhysicsBones()

        arm = self.armature()
        if arm is not None:  # update armature
            arm.update_tag()
            bpy.context.scene.frame_set(bpy.context.scene.frame_current)

        mmd_root = self.rootObject().mmd_root
        if mmd_root.show_temporary_objects:
            mmd_root.show_temporary_objects = False
        logging.info(" Finished cleaning in %f seconds.", time.time() - start_time)
        mmd_root.is_built = False
        rigid_body.setRigidBodyWorldEnabled(rigidbody_world_enabled)

    def __removeTemporaryObjects(self):
        with bpy.context.temp_override(selected_objects=tuple(self.temporaryObjects()), active_object=self.rootObject()):
            bpy.ops.object.delete()

    def __restoreTransforms(self, obj):
        for attr in ("location", "rotation_euler"):
            attr_name = f"__backup_{attr}__"
            val = obj.get(attr_name, None)
            if val is not None:
                setattr(obj, attr, val)
                del obj[attr_name]

    def __backupTransforms(self, obj):
        for attr in ("location", "rotation_euler"):
            attr_name = f"__backup_{attr}__"
            if attr_name in obj:  # should not happen in normal build/clean cycle
                continue
            obj[attr_name] = getattr(obj, attr, None)

    def __preBuild(self):
        self.__fake_parent_map = {}
        self.__rigid_body_matrix_map = {}
        self.__empty_parent_map = {}

        no_parents = []
        for i in self.rigidBodies():
            self.__backupTransforms(i)
            # mute relation
            relation = i.constraints["mmd_tools_rigid_parent"]
            relation.mute = True
            # mute IK
            if int(i.mmd_rigid.type) in {rigid_body.MODE_DYNAMIC, rigid_body.MODE_DYNAMIC_BONE}:
                arm = relation.target
                bone_name = relation.subtarget
                if arm is not None and bone_name != "":
                    for c in arm.pose.bones[bone_name].constraints:
                        if c.type == "IK":
                            c.mute = True
                            c.influence = c.influence  # trigger update
                else:
                    no_parents.append(i)
        # update changes of armature constraints
        bpy.context.scene.frame_set(bpy.context.scene.frame_current)

        parented = []
        for i in self.joints():
            self.__backupTransforms(i)
            rbc = i.rigid_body_constraint
            if rbc is None:
                continue
            obj1, obj2 = rbc.object1, rbc.object2
            if obj2 in no_parents:
                if obj1 not in no_parents and obj2 not in parented:
                    self.__fake_parent_map.setdefault(obj1, []).append(obj2)
                    parented.append(obj2)
            elif obj1 in no_parents:
                if obj1 not in parented:
                    self.__fake_parent_map.setdefault(obj2, []).append(obj1)
                    parented.append(obj1)

        # assert(len(no_parents) == len(parented))

    def __postBuild(self):
        self.__fake_parent_map = None
        self.__rigid_body_matrix_map = None

        # update changes
        bpy.context.scene.frame_set(bpy.context.scene.frame_current)

        # parenting empty to rigid object at once for speeding up
        for empty, rigid_obj in self.__empty_parent_map.items():
            matrix_world = empty.matrix_world
            empty.parent = rigid_obj
            empty.matrix_world = matrix_world
        self.__empty_parent_map = None

        arm = self.armature()
        if arm:
            for p_bone in arm.pose.bones:
                c = p_bone.constraints.get("mmd_tools_rigid_track", None)
                if c:
                    c.mute = False

    def updateRigid(self, rigid_obj: bpy.types.Object, collision_margin: float):
        assert rigid_obj.mmd_type == "RIGID_BODY"
        rb = rigid_obj.rigid_body
        if rb is None:
            return

        rigid = rigid_obj.mmd_rigid
        rigid_type = int(rigid.type)
        relation = rigid_obj.constraints["mmd_tools_rigid_parent"]

        if relation.target is None:
            relation.target = self.armature()

        arm = relation.target
        if relation.subtarget not in arm.pose.bones:
            bone_name = ""
        else:
            bone_name = relation.subtarget

        if rigid_type == rigid_body.MODE_STATIC:
            rb.kinematic = True
        else:
            rb.kinematic = False

        if collision_margin == 0.0:
            rb.use_margin = False
        else:
            rb.use_margin = True
            rb.collision_margin = collision_margin

        if arm is not None and bone_name != "":
            target_bone = arm.pose.bones[bone_name]

            if rigid_type == rigid_body.MODE_STATIC:
                m = target_bone.matrix @ target_bone.bone.matrix_local.inverted()
                self.__rigid_body_matrix_map[rigid_obj] = m
                orig_scale = rigid_obj.scale.copy()
                to_matrix_world = rigid_obj.matrix_world @ rigid_obj.matrix_local.inverted()
                matrix_world = to_matrix_world @ (m @ rigid_obj.matrix_local)
                rigid_obj.parent = arm
                rigid_obj.parent_type = "BONE"
                rigid_obj.parent_bone = bone_name
                rigid_obj.matrix_world = matrix_world
                rigid_obj.scale = orig_scale
                fake_children = self.__fake_parent_map.get(rigid_obj, None)
                if fake_children:
                    for fake_child in fake_children:
                        logging.debug("          - fake_child: %s", fake_child.name)
                        t, r, s = (m @ fake_child.matrix_local).decompose()
                        fake_child.location = t
                        fake_child.rotation_euler = r.to_euler(fake_child.rotation_mode)

            elif rigid_type in {rigid_body.MODE_DYNAMIC, rigid_body.MODE_DYNAMIC_BONE}:
                m = target_bone.matrix @ target_bone.bone.matrix_local.inverted()
                self.__rigid_body_matrix_map[rigid_obj] = m
                t, r, s = (m @ rigid_obj.matrix_local).decompose()
                rigid_obj.location = t
                rigid_obj.rotation_euler = r.to_euler(rigid_obj.rotation_mode)
                fake_children = self.__fake_parent_map.get(rigid_obj, None)
                if fake_children:
                    for fake_child in fake_children:
                        logging.debug("          - fake_child: %s", fake_child.name)
                        t, r, s = (m @ fake_child.matrix_local).decompose()
                        fake_child.location = t
                        fake_child.rotation_euler = r.to_euler(fake_child.rotation_mode)

                if "mmd_tools_rigid_track" not in target_bone.constraints:
                    empty = bpy.data.objects.new(name="mmd_bonetrack", object_data=None)
                    FnContext.link_object(FnContext.ensure_context(), empty)
                    empty.matrix_world = target_bone.matrix
                    setattr(empty, Props.empty_display_type, "ARROWS")
                    setattr(empty, Props.empty_display_size, 0.1 * getattr(self.__root, Props.empty_display_size))
                    empty.mmd_type = "TRACK_TARGET"
                    empty.hide_set(True)
                    empty.parent = self.temporaryGroupObject()

                    rigid_obj.mmd_rigid.bone = bone_name
                    rigid_obj.constraints.remove(relation)

                    self.__empty_parent_map[empty] = rigid_obj

                    const_type = ("COPY_TRANSFORMS", "COPY_ROTATION")[rigid_type - 1]
                    const = target_bone.constraints.new(const_type)
                    const.mute = True
                    const.name = "mmd_tools_rigid_track"
                    const.target = empty
                else:
                    empty = target_bone.constraints["mmd_tools_rigid_track"].target
                    ori_rigid_obj = self.__empty_parent_map[empty]
                    ori_rb = ori_rigid_obj.rigid_body
                    if ori_rb and rb.mass > ori_rb.mass:
                        logging.debug("        * Bone (%s): change target from [%s] to [%s]", target_bone.name, ori_rigid_obj.name, rigid_obj.name)
                        # re-parenting
                        rigid_obj.mmd_rigid.bone = bone_name
                        rigid_obj.constraints.remove(relation)
                        self.__empty_parent_map[empty] = rigid_obj
                        # revert change
                        ori_rigid_obj.mmd_rigid.bone = bone_name
                    else:
                        logging.debug("        * Bone (%s): track target [%s]", target_bone.name, ori_rigid_obj.name)

        rb.collision_shape = rigid.shape

    @staticmethod
    def __getRigidRange(obj):
        return (Vector(obj.bound_box[0]) - Vector(obj.bound_box[6])).length

    def __createNonCollisionConstraint(self, nonCollisionJointTable):
        total_len = len(nonCollisionJointTable)
        if total_len < 1:
            return

        start_time = time.time()
        logging.debug("-" * 60)
        logging.debug(" creating ncc, counts: %d", total_len)

        ncc_obj = bpyutils.createObject(name="ncc", object_data=None)
        ncc_obj.location = [0, 0, 0]
        setattr(ncc_obj, Props.empty_display_type, "ARROWS")
        setattr(ncc_obj, Props.empty_display_size, 0.5 * getattr(self.__root, Props.empty_display_size))
        ncc_obj.mmd_type = "NON_COLLISION_CONSTRAINT"
        ncc_obj.hide_render = True
        ncc_obj.parent = self.temporaryGroupObject()

        bpy.ops.rigidbody.constraint_add(type="GENERIC")
        rb = ncc_obj.rigid_body_constraint
        rb.disable_collisions = True

        ncc_objs = bpyutils.duplicateObject(ncc_obj, total_len)
        logging.debug(" created %d ncc.", len(ncc_objs))

        for ncc_obj, pair in zip(ncc_objs, nonCollisionJointTable, strict=False):
            rbc = ncc_obj.rigid_body_constraint
            rbc.object1, rbc.object2 = pair
            ncc_obj.hide_set(True)
            ncc_obj.hide_select = True
        logging.debug(" finish in %f seconds.", time.time() - start_time)
        logging.debug("-" * 60)

    def buildRigids(self, non_collision_distance_scale, collision_margin):
        logging.debug("--------------------------------")
        logging.debug(" Build riggings of rigid bodies")
        logging.debug("--------------------------------")
        rigid_objects = list(self.rigidBodies())
        rigid_object_groups = [[] for i in range(16)]
        for i in rigid_objects:
            rigid_object_groups[i.mmd_rigid.collision_group_number].append(i)

        jointMap = {}
        for joint in self.joints():
            rbc = joint.rigid_body_constraint
            if rbc is None:
                continue
            rbc.disable_collisions = False
            jointMap[frozenset((rbc.object1, rbc.object2))] = joint

        logging.info("Creating non collision constraints")
        # create non collision constraints
        nonCollisionJointTable = []
        non_collision_pairs = set()
        rigid_object_cnt = len(rigid_objects)
        for obj_a in rigid_objects:
            for n, ignore in enumerate(obj_a.mmd_rigid.collision_group_mask):
                if not ignore:
                    continue
                for obj_b in rigid_object_groups[n]:
                    if obj_a == obj_b:
                        continue
                    pair = frozenset((obj_a, obj_b))
                    if pair in non_collision_pairs:
                        continue
                    if pair in jointMap:
                        joint = jointMap[pair]
                        joint.rigid_body_constraint.disable_collisions = True
                    else:
                        distance = (obj_a.location - obj_b.location).length
                        if distance < non_collision_distance_scale * (self.__getRigidRange(obj_a) + self.__getRigidRange(obj_b)) * 0.5:
                            nonCollisionJointTable.append((obj_a, obj_b))
                    non_collision_pairs.add(pair)
        for cnt, i in enumerate(rigid_objects):
            logging.info("%3d/%3d: Updating rigid body %s", cnt + 1, rigid_object_cnt, i.name)
            self.updateRigid(i, collision_margin)
        self.__createNonCollisionConstraint(nonCollisionJointTable)
        return rigid_objects

    def buildJoints(self):
        for i in self.joints():
            rbc = i.rigid_body_constraint
            if rbc is None:
                continue
            m = self.__rigid_body_matrix_map.get(rbc.object1, None)
            if m is None:
                m = self.__rigid_body_matrix_map.get(rbc.object2, None)
                if m is None:
                    continue
            t, r, s = (m @ i.matrix_local).decompose()
            i.location = t
            i.rotation_euler = r.to_euler(i.rotation_mode)

    def __editPhysicsBones(self, editor: Callable[[bpy.types.EditBone], None], target_modes: Set[str]):
        armature_object = self.armature()

        armature: bpy.types.Armature
        with bpyutils.edit_object(armature_object) as armature:
            edit_bones = armature.edit_bones
            rigid_body_object: bpy.types.Object
            for rigid_body_object in self.rigidBodies():
                mmd_rigid: MMDRigidBody = rigid_body_object.mmd_rigid
                if mmd_rigid.type not in target_modes:
                    continue

                bone_name: str = mmd_rigid.bone
                edit_bone = edit_bones.get(bone_name)
                if edit_bone is None:
                    continue

                editor(edit_bone)

    def disconnectPhysicsBones(self):
        def editor(edit_bone: bpy.types.EditBone):
            rna_prop_ui.rna_idprop_ui_create(edit_bone, "mmd_bone_use_connect", default=edit_bone.use_connect)
            edit_bone.use_connect = False

        self.__editPhysicsBones(editor, {str(MODE_DYNAMIC)})

    def connectPhysicsBones(self):
        def editor(edit_bone: bpy.types.EditBone):
            mmd_bone_use_connect_str: Optional[str] = edit_bone.get("mmd_bone_use_connect")
            if mmd_bone_use_connect_str is None:
                return

            if not edit_bone.use_connect:  # wasn't it overwritten?
                edit_bone.use_connect = bool(mmd_bone_use_connect_str)
            del edit_bone["mmd_bone_use_connect"]

        self.__editPhysicsBones(editor, {str(MODE_STATIC), str(MODE_DYNAMIC), str(MODE_DYNAMIC_BONE)})
