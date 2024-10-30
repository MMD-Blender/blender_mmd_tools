# -*- coding: utf-8 -*-
# Copyright 2017 MMD Tools authors
# This file is part of MMD Tools.

import logging

import bpy
from mathutils import Matrix

from ..vmd import importer
from .. import vpd
from ...bpyutils import FnContext


class VPDImporter:
    def __init__(self, filepath, scale=1.0, bone_mapper=None, use_pose_mode=False):
        self.__pose_name = bpy.path.display_name_from_filepath(filepath)
        self.__vpd_file = vpd.File()
        self.__vpd_file.load(filepath=filepath)
        self.__scale = scale
        self.__bone_mapper = bone_mapper
        if use_pose_mode:
            self.__bone_util_cls = importer.BoneConverter
            #self.__bone_util_cls = importer.BoneConverterPoseMode
            self.__assignToArmature = self.__assignToArmaturePoseMode
        else:
            self.__bone_util_cls = importer.BoneConverter
            self.__assignToArmature = self.__assignToArmatureSimple
        logging.info("Loaded %s", self.__vpd_file)

    def __assignToArmaturePoseMode(self, armObj):
        self.__assignToArmatureSimple(armObj, reset_transform=False)
        #pose_orig = {b: b.matrix_basis.copy() for b in armObj.pose.bones}
        #try:
        #    self.__assignToArmatureSimple(armObj, reset_transform=False)
        #finally:
        #    for bone, matrix_basis in pose_orig.items():
        #        bone.matrix_basis = matrix_basis

    def __assignToArmatureSimple(self, armObj: bpy.types.Object, reset_transform=True):
        logging.info('  - assigning to armature "%s"', armObj.name)

        pose_bones = armObj.pose.bones
        if self.__bone_mapper:
            pose_bones = self.__bone_mapper(armObj)

        pose_data = {}
        for b in self.__vpd_file.bones:
            bone = pose_bones.get(b.bone_name, None)
            if bone is None:
                logging.warning(" * Bone not found: %s", b.bone_name)
                continue
            converter = self.__bone_util_cls(bone, self.__scale)
            loc = converter.convert_location(b.location)
            rot = converter.convert_rotation(b.rotation)
            assert bone not in pose_data
            pose_data[bone] = Matrix.Translation(loc) @ rot.to_matrix().to_4x4()

        # Check if animation data exists
        if armObj.animation_data is None:
            armObj.animation_data_create()

        # Check if an action exists
        if armObj.animation_data.action is None:
            action = bpy.data.actions.new(name="PoseLib")
            armObj.animation_data.action = action
        else:
            action = armObj.animation_data.action

        # Get the current frame
        current_frame = bpy.context.scene.frame_current

        # Update and keyframe only the bones affected by the current VPD file
        for bone in armObj.pose.bones:
            vpd_pose = pose_data.get(bone, None)
            if vpd_pose:
                bone.matrix_basis = vpd_pose
                bone.keyframe_insert(data_path="location", frame=current_frame)
                bone.keyframe_insert(data_path="rotation_quaternion", frame=current_frame)
            elif reset_transform:
                bone.matrix_basis.identity()
                bone.keyframe_insert(data_path="location", frame=current_frame)
                bone.keyframe_insert(data_path="rotation_quaternion", frame=current_frame)

        # Add or update a pose marker
        if self.__pose_name not in action.pose_markers:
            marker = action.pose_markers.new(self.__pose_name)
        else:
            marker = action.pose_markers[self.__pose_name]
        marker.frame = current_frame

        # Ensure the timeline is updated
        bpy.context.view_layer.update()

    def __assignToMesh(self, meshObj):
        if meshObj.data.shape_keys is None:
            return

        logging.info('  - assigning to mesh "%s"', meshObj.name)

        key_blocks = meshObj.data.shape_keys.key_blocks
        for i in key_blocks.values():
            i.value = 0

        for m in self.__vpd_file.morphs:
            shape_key = key_blocks.get(m.morph_name, None)
            if shape_key is None:
                logging.warning(" * Shape key not found: %s", m.morph_name)
                continue
            shape_key.value = m.weight

    def assign(self, obj):
        if obj is None:
            return
        if obj.type == "ARMATURE":
            self.__assignToArmature(obj)
        elif obj.type == "MESH":
            self.__assignToMesh(obj)
        else:
            pass
