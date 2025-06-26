# Copyright 2017 MMD Tools authors
# This file is part of MMD Tools.

import logging
import os

import bpy
from mathutils import Matrix

from ...bpyutils import FnContext
from .. import vpd
from ..vmd import importer


class VPDExporter:
    def __init__(self):
        self.__osm_name = None
        self.__scale = 1
        self.__bone_util_cls = importer.BoneConverter

    def __exportVPDFile(self, filepath, bones=None, morphs=None):
        vpd_file = vpd.File()
        vpd_file.osm_name = self.__osm_name
        if bones:
            vpd_file.bones = bones
        if morphs:
            vpd_file.morphs = morphs
        vpd_file.save(filepath=filepath)
        logging.info("Exported %s", vpd_file)

    def __getConverters(self, pose_bones):
        return {b: self.__bone_util_cls(b, self.__scale, invert=True) for b in pose_bones}

    def __exportBones(self, armObj, converters=None, matrix_basis_map=None):
        if armObj is None:
            return None

        pose_bones = armObj.pose.bones
        if converters is None:
            converters = self.__getConverters(pose_bones)

        if matrix_basis_map is None:
            matrix_basis_map = {}

        matrix_identity = Matrix.Identity(4)
        vpd_bones = []
        for b in pose_bones:
            if b.is_mmd_shadow_bone:
                continue
            if b.matrix_basis == matrix_basis_map.get(b, matrix_identity):
                continue
            bone_name = b.mmd_bone.name_j or b.name
            converter = converters[b]
            location = converter.convert_location(b.location)
            w, x, y, z = b.matrix_basis.to_quaternion()
            w, x, y, z = converter.convert_rotation([x, y, z, w])
            vpd_bones.append(vpd.VpdBone(bone_name, location, [x, y, z, w]))
        return vpd_bones

    def __exportPoseLib(self, armObj: bpy.types.Object, pose_type, filepath, use_pose_mode=False):
        if armObj is None:
            return

        # Use animation_data and action, checking if they are available
        if armObj.animation_data is None or armObj.animation_data.action is None:
            logging.warning('[WARNING] armature "%s" has no animation data or action', armObj.name)
            return

        pose_bones = armObj.pose.bones
        converters = self.__getConverters(pose_bones)

        backup = {b: (b.matrix_basis.copy(), b.bone.select) for b in pose_bones}
        for b in pose_bones:
            b.bone.select = False

        matrix_basis_map = {}
        if use_pose_mode:
            matrix_basis_map = {b: bak[0] for b, bak in backup.items()}

        def __export_index(index, filepath):
            for b in pose_bones:
                b.matrix_basis = matrix_basis_map.get(b, None) or Matrix.Identity(4)
            pose_markers = armObj.animation_data.action.pose_markers
            frame = pose_markers[index].frame if index < len(pose_markers) else 1
            bpy.context.scene.frame_set(frame)
            vpd_bones = self.__exportBones(armObj, converters, matrix_basis_map)
            self.__exportVPDFile(filepath, vpd_bones)

        try:
            pose_markers = armObj.animation_data.action.pose_markers
            with FnContext.temp_override_objects(FnContext.ensure_context(), active_object=armObj, selected_objects=[armObj]):
                bpy.ops.object.mode_set(mode="POSE")
                if pose_type == "ACTIVE":
                    if 0 <= pose_markers.active_index < len(pose_markers):
                        __export_index(pose_markers.active_index, filepath)
                else:
                    folder = os.path.dirname(filepath)
                    for i, m in enumerate(pose_markers):
                        __export_index(i, os.path.join(folder, m.name + ".vpd"))
        finally:
            for b, bak in backup.items():
                b.matrix_basis, b.bone.select = bak

    def __exportMorphs(self, meshObj):
        if meshObj is None:
            return None
        if meshObj.data.shape_keys is None:
            return None

        vpd_morphs = []
        key_blocks = meshObj.data.shape_keys.key_blocks
        for i in key_blocks.values():
            if i.value == 0:
                continue
            vpd_morphs.append(vpd.VpdMorph(i.name, i.value))
        return vpd_morphs

    def export(self, **args):
        armature = args.get("armature")
        mesh = args.get("mesh")
        filepath = args.get("filepath", "")
        self.__scale = args.get("scale", 1.0)
        self.__osm_name = "%s.osm" % args.get("model_name")

        pose_type = args.get("pose_type", "CURRENT")
        if pose_type == "CURRENT":
            vpd_bones = self.__exportBones(armature)
            vpd_morphs = self.__exportMorphs(mesh)
            self.__exportVPDFile(filepath, vpd_bones, vpd_morphs)
        elif pose_type in {"ACTIVE", "ALL"}:
            use_pose_mode = args.get("use_pose_mode", False)
            if use_pose_mode:
                self.__bone_util_cls = importer.BoneConverterPoseMode
            self.__exportPoseLib(armature, pose_type, filepath, use_pose_mode)
        else:
            raise ValueError(f'Unknown pose type "{pose_type}"')
