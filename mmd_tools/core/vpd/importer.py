# Copyright 2017 MMD Tools authors
# This file is part of MMD Tools.

import logging

import bpy
from mathutils import Matrix

from ...bpyutils import FnContext
from .. import vpd
from ..vmd import importer


class VPDImporter:
    def __init__(self, filepath, scale=1.0, bone_mapper=None, use_pose_mode=False):
        self.__pose_name = bpy.path.display_name_from_filepath(filepath)
        self.__vpd_file = vpd.File()
        self.__vpd_file.load(filepath=filepath)
        self.__scale = scale
        self.__bone_mapper = bone_mapper
        self.__bone_util_cls = importer.BoneConverter
        logging.info("Loaded %s", self.__vpd_file)

    def __assignToArmature(self, armObj: bpy.types.Object):
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

        prop_rot_map = {"QUATERNION": "rotation_quaternion", "AXIS_ANGLE": "rotation_axis_angle"}

        # Update and keyframe only the bones affected by the current VPD file
        for bone in armObj.pose.bones:
            vpd_pose = pose_data.get(bone, None)
            if vpd_pose:
                bone.matrix_basis = vpd_pose
                
                data_path_rot = prop_rot_map.get(bone.rotation_mode, "rotation_euler")
                bone_rotation = getattr(bone, data_path_rot)
                fcurves = [None] * (3 + len(bone_rotation))  # x, y, z, r0, r1, r2, (r3)
                
                data_path = 'pose.bones["%s"].location' % bone.name
                for axis_i in range(3):
                    fcurves[axis_i] = action.fcurves.find(data_path, index=axis_i)
                    if fcurves[axis_i] is None:
                        fcurves[axis_i] = action.fcurves.new(data_path=data_path, index=axis_i, action_group=bone.name)
                
                data_path = 'pose.bones["%s"].%s' % (bone.name, data_path_rot)
                for axis_i in range(len(bone_rotation)):
                    fcurves[3 + axis_i] = action.fcurves.find(data_path, index=axis_i) 
                    if fcurves[3 + axis_i] is None:
                        fcurves[3 + axis_i] = action.fcurves.new(data_path=data_path, index=axis_i, action_group=bone.name)
                
                for axis_i in range(3):
                    fcurves[axis_i].keyframe_points.insert(current_frame, bone.location[axis_i])
                
                for axis_i in range(len(bone_rotation)):
                    fcurves[3 + axis_i].keyframe_points.insert(current_frame, bone_rotation[axis_i])

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

        # Check if animation data exists
        if meshObj.data.shape_keys.animation_data is None:
            meshObj.data.shape_keys.animation_data_create()

        # Check if an action exists or create new one
        if meshObj.data.shape_keys.animation_data.action is None:
            action = bpy.data.actions.new(name=meshObj.name+"_ShapeKeys")
            meshObj.data.shape_keys.animation_data.action = action
        else:
            action = meshObj.data.shape_keys.animation_data.action

        # Get current frame
        current_frame = bpy.context.scene.frame_current

        # Set and keyframe shape keys from VPD file
        key_blocks = meshObj.data.shape_keys.key_blocks
        for m in self.__vpd_file.morphs:
            shape_key = key_blocks.get(m.morph_name, None)
            if shape_key is None:
                logging.warning(" * Shape key not found: %s", m.morph_name)
                continue
            
            # Set the value
            shape_key.value = m.weight
            
            # Create or get FCurve
            data_path = 'key_blocks["%s"].value' % shape_key.name
            fcurve = action.fcurves.find(data_path)
            if fcurve is None:
                fcurve = action.fcurves.new(data_path=data_path)
            
            # Add keyframe
            fcurve.keyframe_points.insert(current_frame, m.weight)

    def assign(self, obj):
        if obj is None:
            return
        if obj.type == "ARMATURE":
            self.__assignToArmature(obj)
        elif obj.type == "MESH":
            self.__assignToMesh(obj)
        else:
            pass