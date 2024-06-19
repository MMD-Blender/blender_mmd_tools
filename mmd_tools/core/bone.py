# -*- coding: utf-8 -*-
# Copyright 2015 MMD Tools authors
# This file is part of MMD Tools.

import math
from typing import TYPE_CHECKING, Iterable, Optional, Set, cast

import bpy
from mathutils import Vector

from .. import bpyutils
from ..bpyutils import TransformConstraintOp
from ..utils import ItemOp

if TYPE_CHECKING:
    from ..properties.pose_bone import MMDBone
    from ..properties.root import MMDDisplayItemFrame, MMDRoot


def remove_constraint(constraints, name):
    c = constraints.get(name, None)
    if c:
        constraints.remove(c)
        return True
    return False


def remove_edit_bones(edit_bones, bone_names):
    for name in bone_names:
        b = edit_bones.get(name, None)
        if b:
            edit_bones.remove(b)


BONE_COLLECTION_CUSTOM_PROPERTY_NAME = "mmd_tools"
BONE_COLLECTION_CUSTOM_PROPERTY_VALUE_SPECIAL = "special collection"
BONE_COLLECTION_CUSTOM_PROPERTY_VALUE_NORMAL = "normal collection"
BONE_COLLECTION_NAME_SHADOW = "mmd_shadow"
BONE_COLLECTION_NAME_DUMMY = "mmd_dummy"

SPECIAL_BONE_COLLECTION_NAMES = [BONE_COLLECTION_NAME_SHADOW, BONE_COLLECTION_NAME_DUMMY]


class FnBone:
    AUTO_LOCAL_AXIS_ARMS = ("左肩", "左腕", "左ひじ", "左手首", "右腕", "右肩", "右ひじ", "右手首")
    AUTO_LOCAL_AXIS_FINGERS = ("親指", "人指", "中指", "薬指", "小指")
    AUTO_LOCAL_AXIS_SEMI_STANDARD_ARMS = ("左腕捩", "左手捩", "左肩P", "左ダミー", "右腕捩", "右手捩", "右肩P", "右ダミー")

    def __init__(self):
        raise NotImplementedError("This class cannot be instantiated.")

    @staticmethod
    def find_pose_bone_by_bone_id(armature_object: bpy.types.Object, bone_id: int) -> Optional[bpy.types.PoseBone]:
        for bone in armature_object.pose.bones:
            if bone.mmd_bone.bone_id != bone_id:
                continue
            return bone
        return None

    @staticmethod
    def __new_bone_id(armature_object: bpy.types.Object) -> int:
        return max(b.mmd_bone.bone_id for b in armature_object.pose.bones) + 1

    @staticmethod
    def get_or_assign_bone_id(pose_bone: bpy.types.PoseBone) -> int:
        if pose_bone.mmd_bone.bone_id < 0:
            pose_bone.mmd_bone.bone_id = FnBone.__new_bone_id(pose_bone.id_data)
        return pose_bone.mmd_bone.bone_id

    @staticmethod
    def __get_selected_pose_bones(armature_object: bpy.types.Object) -> Iterable[bpy.types.PoseBone]:
        if armature_object.mode == "EDIT":
            bpy.ops.object.mode_set(mode="OBJECT")  # update selected bones
            bpy.ops.object.mode_set(mode="EDIT")  # back to edit mode
        context_selected_bones = bpy.context.selected_pose_bones or bpy.context.selected_bones or []
        bones = armature_object.pose.bones
        return (bones[b.name] for b in context_selected_bones if not bones[b.name].is_mmd_shadow_bone)

    @staticmethod
    def load_bone_fixed_axis(armature_object: bpy.types.Object, enable=True):
        for b in FnBone.__get_selected_pose_bones(armature_object):
            mmd_bone: MMDBone = b.mmd_bone
            mmd_bone.enabled_fixed_axis = enable
            lock_rotation = b.lock_rotation[:]
            if enable:
                axes = b.bone.matrix_local.to_3x3().transposed()
                if lock_rotation.count(False) == 1:
                    mmd_bone.fixed_axis = axes[lock_rotation.index(False)].xzy
                else:
                    mmd_bone.fixed_axis = axes[1].xzy  # Y-axis
            elif all(b.lock_location) and lock_rotation.count(True) > 1 and lock_rotation == (b.lock_ik_x, b.lock_ik_y, b.lock_ik_z):
                # unlock transform locks if fixed axis was applied
                b.lock_ik_x, b.lock_ik_y, b.lock_ik_z = b.lock_rotation = (False, False, False)
                b.lock_location = b.lock_scale = (False, False, False)

    @staticmethod
    def setup_special_bone_collections(armature_object: bpy.types.Object) -> bpy.types.Object:
        armature = cast(bpy.types.Armature, armature_object.data)
        bone_collections = armature.collections
        for bone_collection_name in SPECIAL_BONE_COLLECTION_NAMES:
            if bone_collection_name in bone_collections:
                continue
            bone_collection = bone_collections.new(bone_collection_name)
            FnBone.__set_bone_collection_to_special(bone_collection, is_visible=False)
        return armature_object

    @staticmethod
    def __is_mmd_tools_bone_collection(bone_collection: bpy.types.BoneCollection) -> bool:
        return BONE_COLLECTION_CUSTOM_PROPERTY_NAME in bone_collection

    @staticmethod
    def __is_special_bone_collection(bone_collection: bpy.types.BoneCollection) -> bool:
        return BONE_COLLECTION_CUSTOM_PROPERTY_VALUE_SPECIAL == bone_collection.get(BONE_COLLECTION_CUSTOM_PROPERTY_NAME)

    @staticmethod
    def __set_bone_collection_to_special(bone_collection: bpy.types.BoneCollection, is_visible: bool):
        bone_collection[BONE_COLLECTION_CUSTOM_PROPERTY_NAME] = BONE_COLLECTION_CUSTOM_PROPERTY_VALUE_SPECIAL
        bone_collection.is_visible = is_visible

    @staticmethod
    def __is_normal_bone_collection(bone_collection: bpy.types.BoneCollection) -> bool:
        return BONE_COLLECTION_CUSTOM_PROPERTY_VALUE_NORMAL == bone_collection.get(BONE_COLLECTION_CUSTOM_PROPERTY_NAME)

    @staticmethod
    def __set_bone_collection_to_normal(bone_collection: bpy.types.BoneCollection):
        bone_collection[BONE_COLLECTION_CUSTOM_PROPERTY_NAME] = BONE_COLLECTION_CUSTOM_PROPERTY_VALUE_NORMAL

    @staticmethod
    def __set_edit_bone_to_special(edit_bone: bpy.types.EditBone, bone_collection_name: str) -> bpy.types.EditBone:
        edit_bone.id_data.collections[bone_collection_name].assign(edit_bone)
        edit_bone.use_deform = False
        return edit_bone

    @staticmethod
    def set_edit_bone_to_dummy(edit_bone: bpy.types.EditBone) -> bpy.types.EditBone:
        return FnBone.__set_edit_bone_to_special(edit_bone, BONE_COLLECTION_NAME_DUMMY)

    @staticmethod
    def set_edit_bone_to_shadow(edit_bone: bpy.types.EditBone) -> bpy.types.EditBone:
        return FnBone.__set_edit_bone_to_special(edit_bone, BONE_COLLECTION_NAME_SHADOW)

    @staticmethod
    def __unassign_mmd_tools_bone_collections(edit_bone: bpy.types.EditBone) -> bpy.types.EditBone:
        for bone_collection in edit_bone.collections:
            if not FnBone.__is_mmd_tools_bone_collection(bone_collection):
                continue
            bone_collection.unassign(edit_bone)
        return edit_bone

    @staticmethod
    def sync_bone_collections_from_mmd_root(armature_object: bpy.types.Object, mmd_root: "MMDRoot"):
        armature = cast(bpy.types.Armature, armature_object.data)
        bone_collections = armature.collections
        bones = armature.bones
        used_groups = set()
        unassigned_bone_names = {b.name for b in bones}

        for frame in mmd_root.display_item_frames:
            for item in frame.data:
                if item.type == "BONE" and item.name in unassigned_bone_names:
                    unassigned_bone_names.remove(item.name)
                    group_name = frame.name
                    used_groups.add(group_name)
                    bone_collection = bone_collections.get(group_name)
                    if bone_collection is None:
                        bone_collection = bone_collections.new(name=group_name)
                        FnBone.__set_bone_collection_to_normal(bone_collection)
                    bone_collection.assign(bones[item.name])

        for name in unassigned_bone_names:
            for bc in bones[name].collections:
                if not FnBone.__is_mmd_tools_bone_collection(bc):
                    continue
                if not FnBone.__is_normal_bone_collection(bc):
                    continue
                bc.unassign(bones[name])

        # remove unused bone groups
        for bone_collection in bone_collections.values():
            if bone_collection.name in used_groups:
                continue
            if not FnBone.__is_mmd_tools_bone_collection(bone_collection):
                continue
            if not FnBone.__is_normal_bone_collection(bone_collection):
                continue
            bone_collections.remove(bone_collection)

    @staticmethod
    def sync_mmd_root_from_bone_collections(mmd_root: "MMDRoot", armature_object: bpy.types.Object):
        armature = cast(bpy.types.Armature, armature_object.data)
        bone_collections: bpy.types.BoneCollections = armature.collections

        display_item_frames = mmd_root.display_item_frames

        used_frame_index: Set[int] = set()

        bone_collection: bpy.types.BoneCollection
        for bone_collection in bone_collections:
            if len(bone_collection.bones) == 0 or FnBone.__is_special_bone_collection(bone_collection):
                continue

            bone_collection_name = bone_collection.name
            display_item_frame: Optional[MMDDisplayItemFrame] = display_item_frames.get(bone_collection_name)
            if display_item_frame is None:
                display_item_frame = display_item_frames.add()
                display_item_frame.name = bone_collection_name
                display_item_frame.name_e = bone_collection_name
            used_frame_index.add(display_item_frames.find(bone_collection_name))

            ItemOp.resize(display_item_frame.data, len(bone_collection.bones))
            for display_item, bone in zip(display_item_frame.data, bone_collection.bones):
                display_item.type = "BONE"
                display_item.name = bone.name

        for i in reversed(range(len(display_item_frames))):
            if i in used_frame_index:
                continue
            display_item_frame = display_item_frames[i]
            if display_item_frame.is_special:
                if display_item_frame.name != "表情":
                    display_item_frame.data.clear()
            else:
                display_item_frames.remove(i)
        mmd_root.active_display_item_frame = 0

    @staticmethod
    def apply_bone_fixed_axis(armature_object: bpy.types.Object):
        bone_map = {}
        for b in armature_object.pose.bones:
            if b.is_mmd_shadow_bone or not b.mmd_bone.enabled_fixed_axis:
                continue
            mmd_bone: MMDBone = b.mmd_bone
            parent_tip = b.parent and not b.parent.is_mmd_shadow_bone and b.parent.mmd_bone.is_tip
            bone_map[b.name] = (mmd_bone.fixed_axis.normalized(), mmd_bone.is_tip, parent_tip)

        force_align = True
        with bpyutils.edit_object(armature_object) as data:
            bone: bpy.types.EditBone
            for bone in data.edit_bones:
                if bone.name not in bone_map:
                    bone.select = False
                    continue
                fixed_axis, is_tip, parent_tip = bone_map[bone.name]
                if fixed_axis.length:
                    axes = [bone.x_axis, bone.y_axis, bone.z_axis]
                    direction = fixed_axis.normalized().xzy
                    idx, val = max([(i, direction.dot(v)) for i, v in enumerate(axes)], key=lambda x: abs(x[1]))
                    idx_1, idx_2 = (idx + 1) % 3, (idx + 2) % 3
                    axes[idx] = -direction if val < 0 else direction
                    axes[idx_2] = axes[idx].cross(axes[idx_1])
                    axes[idx_1] = axes[idx_2].cross(axes[idx])
                    if parent_tip and bone.use_connect:
                        bone.use_connect = False
                        bone.head = bone.parent.head
                    if force_align:
                        tail = bone.head + axes[1].normalized() * bone.length
                        if is_tip or (tail - bone.tail).length > 1e-4:
                            for c in bone.children:
                                if c.use_connect:
                                    c.use_connect = False
                                    if is_tip:
                                        c.head = bone.head
                        bone.tail = tail
                    bone.align_roll(axes[2])
                    bone_map[bone.name] = tuple(i != idx for i in range(3))
                else:
                    bone_map[bone.name] = (True, True, True)
                bone.select = True

        for bone_name, locks in bone_map.items():
            b = armature_object.pose.bones[bone_name]
            b.lock_location = (True, True, True)
            b.lock_ik_x, b.lock_ik_y, b.lock_ik_z = b.lock_rotation = locks

    @staticmethod
    def load_bone_local_axes(armature_object: bpy.types.Object, enable=True):
        for b in FnBone.__get_selected_pose_bones(armature_object):
            mmd_bone: MMDBone = b.mmd_bone
            mmd_bone.enabled_local_axes = enable
            if enable:
                axes = b.bone.matrix_local.to_3x3().transposed()
                mmd_bone.local_axis_x = axes[0].xzy
                mmd_bone.local_axis_z = axes[2].xzy

    @staticmethod
    def apply_bone_local_axes(armature_object: bpy.types.Object):
        bone_map = {}
        for b in armature_object.pose.bones:
            if b.is_mmd_shadow_bone or not b.mmd_bone.enabled_local_axes:
                continue
            mmd_bone: MMDBone = b.mmd_bone
            bone_map[b.name] = (mmd_bone.local_axis_x, mmd_bone.local_axis_z)

        with bpyutils.edit_object(armature_object) as data:
            bone: bpy.types.EditBone
            for bone in data.edit_bones:
                if bone.name not in bone_map:
                    bone.select = False
                    continue
                local_axis_x, local_axis_z = bone_map[bone.name]
                FnBone.update_bone_roll(bone, local_axis_x, local_axis_z)
                bone.select = True

    @staticmethod
    def update_bone_roll(edit_bone: bpy.types.EditBone, mmd_local_axis_x, mmd_local_axis_z):
        axes = FnBone.get_axes(mmd_local_axis_x, mmd_local_axis_z)
        idx, val = max([(i, edit_bone.vector.dot(v)) for i, v in enumerate(axes)], key=lambda x: abs(x[1]))
        edit_bone.align_roll(axes[(idx - 1) % 3 if val < 0 else (idx + 1) % 3])

    @staticmethod
    def get_axes(mmd_local_axis_x, mmd_local_axis_z):
        x_axis = Vector(mmd_local_axis_x).normalized().xzy
        z_axis = Vector(mmd_local_axis_z).normalized().xzy
        y_axis = z_axis.cross(x_axis).normalized()
        z_axis = x_axis.cross(y_axis).normalized()  # correction
        return (x_axis, y_axis, z_axis)

    @staticmethod
    def apply_auto_bone_roll(armature):
        bone_names = []
        for b in armature.pose.bones:
            if not b.is_mmd_shadow_bone and not b.mmd_bone.enabled_local_axes and FnBone.has_auto_local_axis(b.mmd_bone.name_j):
                bone_names.append(b.name)
        with bpyutils.edit_object(armature) as data:
            bone: bpy.types.EditBone
            for bone in data.edit_bones:
                if bone.name not in bone_names:
                    continue
                FnBone.update_auto_bone_roll(bone)
                bone.select = True

    @staticmethod
    def update_auto_bone_roll(edit_bone):
        # make a triangle face (p1,p2,p3)
        p1 = edit_bone.head.copy()
        p2 = edit_bone.tail.copy()
        p3 = p2.copy()
        # translate p3 in xz plane
        # the normal vector of the face tracks -Y direction
        xz = Vector((p2.x - p1.x, p2.z - p1.z))
        xz.normalize()
        theta = math.atan2(xz.y, xz.x)
        norm = edit_bone.vector.length
        p3.z += norm * math.cos(theta)
        p3.x -= norm * math.sin(theta)
        # calculate the normal vector of the face
        y = (p2 - p1).normalized()
        z_tmp = (p3 - p1).normalized()
        x = y.cross(z_tmp)  # normal vector
        # z = x.cross(y)
        FnBone.update_bone_roll(edit_bone, y.xzy, x.xzy)

    @staticmethod
    def has_auto_local_axis(name_j):
        if name_j:
            if name_j in FnBone.AUTO_LOCAL_AXIS_ARMS or name_j in FnBone.AUTO_LOCAL_AXIS_SEMI_STANDARD_ARMS:
                return True
            for finger_name in FnBone.AUTO_LOCAL_AXIS_FINGERS:
                if finger_name in name_j:
                    return True
        return False

    @staticmethod
    def clean_additional_transformation(armature_object: bpy.types.Object):
        # clean constraints
        p_bone: bpy.types.PoseBone
        for p_bone in armature_object.pose.bones:
            p_bone.mmd_bone.is_additional_transform_dirty = True
            constraints = p_bone.constraints
            remove_constraint(constraints, "mmd_additional_rotation")
            remove_constraint(constraints, "mmd_additional_location")
            if remove_constraint(constraints, "mmd_additional_parent"):
                p_bone.bone.use_inherit_rotation = True
        # clean shadow bones
        shadow_bone_types = {
            "DUMMY",
            "SHADOW",
            "ADDITIONAL_TRANSFORM",
            "ADDITIONAL_TRANSFORM_INVERT",
        }

        def __is_at_shadow_bone(b):
            return b.is_mmd_shadow_bone and b.mmd_shadow_bone_type in shadow_bone_types

        shadow_bone_names = [b.name for b in armature_object.pose.bones if __is_at_shadow_bone(b)]
        if len(shadow_bone_names) > 0:
            with bpyutils.edit_object(armature_object) as data:
                remove_edit_bones(data.edit_bones, shadow_bone_names)

    @staticmethod
    def apply_additional_transformation(armature_object: bpy.types.Object):
        def __is_dirty_bone(b):
            if b.is_mmd_shadow_bone:
                return False
            mmd_bone = b.mmd_bone
            if mmd_bone.has_additional_rotation or mmd_bone.has_additional_location:
                return True
            return mmd_bone.is_additional_transform_dirty

        dirty_bones = [b for b in armature_object.pose.bones if __is_dirty_bone(b)]

        # setup constraints
        shadow_bone_pool = []
        for p_bone in dirty_bones:
            sb = FnBone.__setup_constraints(p_bone)
            if sb:
                shadow_bone_pool.append(sb)

        # setup shadow bones
        with bpyutils.edit_object(armature_object) as data:
            edit_bones = data.edit_bones
            for sb in shadow_bone_pool:
                sb.update_edit_bones(edit_bones)

        pose_bones = armature_object.pose.bones
        for sb in shadow_bone_pool:
            sb.update_pose_bones(pose_bones)

        # finish
        for p_bone in dirty_bones:
            p_bone.mmd_bone.is_additional_transform_dirty = False

    @staticmethod
    def __setup_constraints(p_bone):
        bone_name = p_bone.name
        mmd_bone = p_bone.mmd_bone
        influence = mmd_bone.additional_transform_influence
        target_bone = mmd_bone.additional_transform_bone
        mute_rotation = not mmd_bone.has_additional_rotation  # or p_bone.is_in_ik_chain
        mute_location = not mmd_bone.has_additional_location

        constraints = p_bone.constraints
        if not target_bone or (mute_rotation and mute_location) or influence == 0:
            rot = remove_constraint(constraints, "mmd_additional_rotation")
            loc = remove_constraint(constraints, "mmd_additional_location")
            if rot or loc:
                return _AT_ShadowBoneRemove(bone_name)
            return None

        shadow_bone = _AT_ShadowBoneCreate(bone_name, target_bone)

        def __config(name, mute, map_type, value):
            if mute:
                remove_constraint(constraints, name)
                return
            c = TransformConstraintOp.create(constraints, name, map_type)
            c.target = p_bone.id_data
            shadow_bone.add_constraint(c)
            TransformConstraintOp.update_min_max(c, value, influence)

        __config("mmd_additional_rotation", mute_rotation, "ROTATION", math.pi)
        __config("mmd_additional_location", mute_location, "LOCATION", 100)

        return shadow_bone

    @staticmethod
    def update_additional_transform_influence(pose_bone: bpy.types.PoseBone):
        influence = pose_bone.mmd_bone.additional_transform_influence
        constraints = pose_bone.constraints
        c = constraints.get("mmd_additional_rotation", None)
        TransformConstraintOp.update_min_max(c, math.pi, influence)
        c = constraints.get("mmd_additional_location", None)
        TransformConstraintOp.update_min_max(c, 100, influence)

    @staticmethod
    def rename(pose_bone: bpy.types.PoseBone, new_bone_name: str) -> bpy.types.PoseBone:
        pose_bone.name = new_bone_name
        pose_bone.bone.name = new_bone_name
        return pose_bone


class MigrationFnBone:
    """Migration Functions for old MMD models broken by bugs or issues"""

    @staticmethod
    def fix_mmd_ik_limit_override(armature_object: bpy.types.Object):
        pose_bone: bpy.types.PoseBone
        for pose_bone in armature_object.pose.bones:
            constraint: bpy.types.Constraint
            for constraint in pose_bone.constraints:
                if constraint.type == "LIMIT_ROTATION" and "mmd_ik_limit_override" in constraint.name:
                    constraint.owner_space = "LOCAL"


class _AT_ShadowBoneRemove:
    def __init__(self, bone_name):
        self.__shadow_bone_names = ("_dummy_" + bone_name, "_shadow_" + bone_name)

    def update_edit_bones(self, edit_bones):
        remove_edit_bones(edit_bones, self.__shadow_bone_names)

    def update_pose_bones(self, pose_bones):
        pass


class _AT_ShadowBoneCreate:
    def __init__(self, bone_name, target_bone_name):
        self.__dummy_bone_name = "_dummy_" + bone_name
        self.__shadow_bone_name = "_shadow_" + bone_name
        self.__bone_name = bone_name
        self.__target_bone_name = target_bone_name
        self.__constraint_pool = []

    def __is_well_aligned(self, bone0, bone1):
        return bone0.x_axis.dot(bone1.x_axis) > 0.99 and bone0.y_axis.dot(bone1.y_axis) > 0.99

    def __update_constraints(self, use_shadow=True):
        subtarget = self.__shadow_bone_name if use_shadow else self.__target_bone_name
        for c in self.__constraint_pool:
            c.subtarget = subtarget

    def add_constraint(self, constraint):
        self.__constraint_pool.append(constraint)

    def update_edit_bones(self, edit_bones):
        bone = edit_bones[self.__bone_name]
        target_bone = edit_bones[self.__target_bone_name]
        if bone != target_bone and self.__is_well_aligned(bone, target_bone):
            _AT_ShadowBoneRemove(self.__bone_name).update_edit_bones(edit_bones)
            return

        dummy_bone_name = self.__dummy_bone_name
        dummy = edit_bones.get(dummy_bone_name, None) or FnBone.set_edit_bone_to_dummy(edit_bones.new(name=dummy_bone_name))
        dummy.parent = target_bone
        dummy.head = target_bone.head
        dummy.tail = dummy.head + bone.tail - bone.head
        dummy.roll = bone.roll

        shadow_bone_name = self.__shadow_bone_name
        shadow = edit_bones.get(shadow_bone_name, None) or FnBone.set_edit_bone_to_shadow(edit_bones.new(name=shadow_bone_name))
        shadow.parent = target_bone.parent
        shadow.head = dummy.head
        shadow.tail = dummy.tail
        shadow.roll = bone.roll

    def update_pose_bones(self, pose_bones):
        if self.__shadow_bone_name not in pose_bones:
            self.__update_constraints(use_shadow=False)
            return

        dummy_p_bone = pose_bones[self.__dummy_bone_name]
        dummy_p_bone.is_mmd_shadow_bone = True
        dummy_p_bone.mmd_shadow_bone_type = "DUMMY"

        shadow_p_bone = pose_bones[self.__shadow_bone_name]
        shadow_p_bone.is_mmd_shadow_bone = True
        shadow_p_bone.mmd_shadow_bone_type = "SHADOW"

        if "mmd_tools_at_dummy" not in shadow_p_bone.constraints:
            c = shadow_p_bone.constraints.new("COPY_TRANSFORMS")
            c.name = "mmd_tools_at_dummy"
            c.target = dummy_p_bone.id_data
            c.subtarget = dummy_p_bone.name
            c.target_space = "POSE"
            c.owner_space = "POSE"

        self.__update_constraints()
