# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

import copy
import logging
import math
import os
import shutil
import time
from collections import OrderedDict

import bmesh
import bpy
import mathutils

from ...bpyutils import FnContext
from ...operators.misc import MoveObject
from ...utils import saferelpath
from .. import pmx
from ..material import FnMaterial
from ..morph import FnMorph
from ..sdef import FnSDEF
from ..translations import FnTranslations
from ..vmd.importer import BoneConverter, BoneConverterPoseMode


class _Vertex:
    def __init__(self, co, groups, offsets, edge_scale, vertex_order, uv_offsets):
        self.co = co
        self.groups = groups  # [(group_number, weight), ...]
        self.offsets = offsets
        self.edge_scale = edge_scale
        self.vertex_order = vertex_order  # used for controlling vertex order
        self.uv_offsets = uv_offsets
        self.index = None
        self.uv = None
        self.normal = None
        self.sdef_data = []  # (C, R0, R1)
        self.add_uvs = [None] * 4  # UV1~UV4


class _Face:
    def __init__(self, vertices, index=-1):
        """Temporary Face Class"""
        self.vertices = vertices
        self.index = index


class _Mesh:
    def __init__(self, material_faces, shape_key_names, material_names):
        self.material_faces = material_faces  # dict of {material_index => [face1, face2, ....]}
        self.shape_key_names = shape_key_names
        self.material_names = material_names


class _DefaultMaterial:
    def __init__(self):
        mat = bpy.data.materials.new("")
        # mat.mmd_material.diffuse_color = (0, 0, 0)
        # mat.mmd_material.specular_color = (0, 0, 0)
        # mat.mmd_material.ambient_color = (0, 0, 0)
        self.material = mat
        logging.debug("create default material: %s", str(self.material))

    def __del__(self):
        if self.material:
            logging.debug("remove default material: %s", str(self.material))
            bpy.data.materials.remove(self.material)


class __PmxExporter:
    CATEGORIES = {
        "SYSTEM": pmx.Morph.CATEGORY_SYSTEM,
        "EYEBROW": pmx.Morph.CATEGORY_EYEBROW,
        "EYE": pmx.Morph.CATEGORY_EYE,
        "MOUTH": pmx.Morph.CATEGORY_MOUTH,
    }

    MORPH_TYPES = {
        pmx.GroupMorph: "group_morphs",
        pmx.VertexMorph: "vertex_morphs",
        pmx.BoneMorph: "bone_morphs",
        pmx.UVMorph: "uv_morphs",
        pmx.MaterialMorph: "material_morphs",
    }

    def __init__(self):
        self.__model = None
        self.__bone_name_table = []
        self.__material_name_table = []
        self.__exported_vertices = []
        self.__default_material = None
        self.__vertex_order_map = None  # used for controlling vertex order
        self.__overwrite_bone_morphs_from_action_pose = False
        self.__translate_in_presets = False
        self.__disable_specular = False
        self.__add_uv_count = 0

    @staticmethod
    def flipUV_V(uv):
        u, v = uv
        return u, 1.0 - v

    def __getDefaultMaterial(self):
        if self.__default_material is None:
            self.__default_material = _DefaultMaterial()
        return self.__default_material.material

    def __sortVertices(self):
        logging.info(" - Sorting vertices ...")
        weight_items = self.__vertex_order_map.items()
        sorted_indices = [i[0] for i in sorted(weight_items, key=lambda x: x[1].vertex_order)]
        vertices = self.__model.vertices
        self.__model.vertices = [vertices[i] for i in sorted_indices]

        # update indices
        index_map = {x: i for i, x in enumerate(sorted_indices)}
        for v in self.__vertex_order_map.values():
            v.index = index_map[v.index]
        for f in self.__model.faces:
            f[:] = [index_map[i] for i in f]
        logging.debug("   - Done (count:%d)", len(self.__vertex_order_map))

    def __exportMeshes(self, meshes, bone_map):
        mat_map = OrderedDict()
        for mesh in meshes:
            for index, mat_faces in sorted(mesh.material_faces.items(), key=lambda x: x[0]):
                name = mesh.material_names[index]
                if name not in mat_map:
                    mat_map[name] = []
                mat_map[name].append(mat_faces)

        sort_vertices = self.__vertex_order_map is not None
        if sort_vertices:
            self.__vertex_order_map.clear()

        # export vertices
        for mat_name, mat_meshes in mat_map.items():
            face_count = 0
            for mat_faces in mat_meshes:
                mesh_vertices = []
                for face in mat_faces:
                    mesh_vertices.extend(face.vertices)

                for v in mesh_vertices:
                    if v.index is not None:
                        continue

                    v.index = len(self.__model.vertices)
                    if sort_vertices:
                        self.__vertex_order_map[v.index] = v

                    pv = pmx.Vertex()
                    pv.co = v.co
                    pv.normal = v.normal
                    pv.uv = self.flipUV_V(v.uv)
                    pv.edge_scale = v.edge_scale

                    # Handle additional UVs
                    max_uv_index = max((i for i, uvzw in enumerate(v.add_uvs) if uvzw), default=-1)  # Find the highest index with valid data
                    if max_uv_index >= 0:
                        # Ensure additional_uvs list is long enough to include all required indices
                        for uv_index in range(max_uv_index + 1):
                            _uvzw = v.add_uvs[uv_index]
                            if _uvzw:
                                if uv_index == 1:  # ADD UV2 (vertex color data)
                                    # Vertex color data doesn't need V-axis flipping
                                    additional_uv_data = _uvzw[0] + _uvzw[1]
                                else:
                                    # Other UV data requires V-axis flipping
                                    additional_uv_data = self.flipUV_V(_uvzw[0]) + self.flipUV_V(_uvzw[1])
                                pv.additional_uvs.append(additional_uv_data)
                            else:
                                # If this index has no data but higher indices do, insert zero data to keep indices aligned
                                pv.additional_uvs.append((0.0, 0.0, 0.0, 0.0))

                    t = len(v.groups)
                    if t == 0:
                        weight = pmx.BoneWeight()
                        weight.type = pmx.BoneWeight.BDEF1
                        weight.bones = [0]
                        pv.weight = weight
                    elif t == 1:
                        weight = pmx.BoneWeight()
                        weight.type = pmx.BoneWeight.BDEF1
                        weight.bones = [v.groups[0][0]]
                        pv.weight = weight
                    elif t == 2:
                        vg1, vg2 = v.groups
                        weight = pmx.BoneWeight()
                        weight.type = pmx.BoneWeight.BDEF2
                        weight.bones = [vg1[0], vg2[0]]
                        w1, w2 = vg1[1], vg2[1]
                        weight.weights = [w1 / (w1 + w2)]
                        if v.sdef_data:
                            weight.type = pmx.BoneWeight.SDEF
                            sdef_weights = pmx.BoneWeightSDEF()
                            sdef_weights.weight = weight.weights[0]
                            sdef_weights.c, sdef_weights.r0, sdef_weights.r1 = v.sdef_data
                            if weight.bones[0] > weight.bones[1]:
                                weight.bones.reverse()
                                sdef_weights.weight = 1.0 - sdef_weights.weight
                            weight.weights = sdef_weights
                        pv.weight = weight
                    else:
                        weight = pmx.BoneWeight()
                        weight.type = pmx.BoneWeight.BDEF4
                        weight.bones = [0, 0, 0, 0]
                        weight.weights = [0.0, 0.0, 0.0, 0.0]
                        w_all = 0.0
                        if t > 4:
                            v.groups.sort(key=lambda x: -x[1])
                        for i in range(min(t, 4)):
                            gn, w = v.groups[i]
                            weight.bones[i] = gn
                            weight.weights[i] = w
                            w_all += w
                        for i in range(4):
                            weight.weights[i] /= w_all
                        pv.weight = weight
                    self.__model.vertices.append(pv)
                    self.__exported_vertices.append(v)

                for face in mat_faces:
                    self.__model.faces.append([x.index for x in face.vertices])
                face_count += len(mat_faces)
            self.__exportMaterial(bpy.data.materials[mat_name], face_count)

        if sort_vertices:
            self.__sortVertices()

    def __exportTexture(self, filepath):
        if filepath.strip() == "":
            return -1
        # Use bpy.path to resolve '//' in .blend relative filepaths
        filepath = bpy.path.abspath(filepath)
        filepath = os.path.abspath(filepath)
        for i, tex in enumerate(self.__model.textures):
            if os.path.normcase(tex.path) == os.path.normcase(filepath):
                return i
        t = pmx.Texture()
        t.path = filepath
        self.__model.textures.append(t)
        if not os.path.isfile(t.path):
            logging.warning("  The texture file does not exist: %s", t.path)
        return len(self.__model.textures) - 1

    def __copy_textures(self, output_dir, base_folder=""):
        tex_dir_fallback = os.path.join(output_dir, "textures")
        tex_dir_preference = FnContext.get_addon_preferences_attribute(FnContext.ensure_context(), "base_texture_folder", "")

        path_set = set()  # to prevent overwriting
        tex_copy_list = []
        for texture in self.__model.textures:
            path = texture.path
            tex_dir = output_dir  # restart to the default directory at each loop
            if not os.path.isfile(path):
                logging.warning("*** skipping texture file which does not exist: %s", path)
                path_set.add(os.path.normcase(path))
                continue
            dst_name = os.path.basename(path)
            if base_folder:
                dst_name = saferelpath(path, base_folder, strategy="outside")
                if dst_name.startswith(".."):
                    # Check if the texture comes from the preferred folder
                    if tex_dir_preference:
                        dst_name = saferelpath(path, tex_dir_preference, strategy="outside")
                    if dst_name.startswith(".."):
                        # If the code reaches here the texture is somewhere else
                        logging.warning("The texture %s is not inside the base texture folder", path)
                        # Fall back to basename and textures folder
                        dst_name = os.path.basename(path)
                        tex_dir = tex_dir_fallback
            else:
                tex_dir = tex_dir_fallback
            dest_path = os.path.join(tex_dir, dst_name)
            if os.path.normcase(path) != os.path.normcase(dest_path):  # Only copy if the paths are different
                tex_copy_list.append((texture, path, dest_path))
            else:
                path_set.add(os.path.normcase(path))

        for texture, path, dest_path in tex_copy_list:
            counter = 1
            base, ext = os.path.splitext(dest_path)
            while os.path.normcase(dest_path) in path_set:
                dest_path = "%s_%d%s" % (base, counter, ext)
                counter += 1
            path_set.add(os.path.normcase(dest_path))
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copyfile(path, dest_path)
            logging.info("Copy file %s --> %s", path, dest_path)
            texture.path = dest_path

    def __exportMaterial(self, material, num_faces):
        p_mat = pmx.Material()
        mmd_mat = material.mmd_material

        p_mat.name = mmd_mat.name_j or material.name
        p_mat.name_e = mmd_mat.name_e
        p_mat.diffuse = list(mmd_mat.diffuse_color) + [mmd_mat.alpha]
        p_mat.ambient = mmd_mat.ambient_color
        p_mat.specular = mmd_mat.specular_color
        p_mat.shininess = mmd_mat.shininess
        p_mat.is_double_sided = mmd_mat.is_double_sided
        p_mat.enabled_drop_shadow = mmd_mat.enabled_drop_shadow
        p_mat.enabled_self_shadow_map = mmd_mat.enabled_self_shadow_map
        p_mat.enabled_self_shadow = mmd_mat.enabled_self_shadow
        p_mat.enabled_toon_edge = mmd_mat.enabled_toon_edge
        p_mat.edge_color = mmd_mat.edge_color
        p_mat.edge_size = mmd_mat.edge_weight
        p_mat.sphere_texture_mode = int(mmd_mat.sphere_texture_type)
        if self.__disable_specular:
            p_mat.sphere_texture_mode = pmx.Material.SPHERE_MODE_OFF
        p_mat.comment = mmd_mat.comment

        p_mat.vertex_count = num_faces * 3
        fnMat = FnMaterial(material)
        tex = fnMat.get_texture()
        if tex and tex.type == "IMAGE" and tex.image:  # Ensure the texture is an image
            index = self.__exportTexture(tex.image.filepath)
            p_mat.texture = index
        tex = fnMat.get_sphere_texture()
        if tex and tex.type == "IMAGE" and tex.image:  # Ensure the texture is an image
            index = self.__exportTexture(tex.image.filepath)
            p_mat.sphere_texture = index

        if mmd_mat.is_shared_toon_texture:
            p_mat.toon_texture = mmd_mat.shared_toon_texture
            p_mat.is_shared_toon_texture = True
        else:
            p_mat.toon_texture = self.__exportTexture(mmd_mat.toon_texture)
            p_mat.is_shared_toon_texture = False

        self.__material_name_table.append(material.name)
        self.__model.materials.append(p_mat)

    @classmethod
    def __countBoneDepth(cls, bone):
        if bone.parent is None:
            return 0
        return cls.__countBoneDepth(bone.parent) + 1

    def __exportBones(self, root, meshes):
        """Export bones.
        Returns:
            A dictionary to map Blender bone names to bone indices of the pmx.model instance.
        """
        arm = self.__armature
        if hasattr(arm, "evaluated_get"):
            bpy.context.view_layer.update()
            arm = arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
        boneMap = {}
        pmx_bones = []
        pose_bones = arm.pose.bones
        world_mat = arm.matrix_world
        r = {}

        sorted_bones = sorted(pose_bones, key=lambda x: x.mmd_bone.bone_id if x.mmd_bone.bone_id >= 0 else float("inf"))

        Vector = mathutils.Vector
        pmx_matrix = world_mat * self.__scale
        pmx_matrix[1], pmx_matrix[2] = pmx_matrix[2].copy(), pmx_matrix[1].copy()

        def __to_pmx_location(loc):
            return pmx_matrix @ Vector(loc)

        pmx_matrix_rot = pmx_matrix.to_3x3()

        def __to_pmx_axis(axis, pose_bone):
            m = (pose_bone.matrix @ pose_bone.bone.matrix_local.inverted()).to_3x3()
            return ((pmx_matrix_rot @ m) @ Vector(axis).xzy).normalized()

        if True:  # no need to enter edit mode
            for p_bone in sorted_bones:
                if p_bone.is_mmd_shadow_bone:
                    continue
                bone = p_bone.bone
                mmd_bone = p_bone.mmd_bone
                pmx_bone = pmx.Bone()
                pmx_bone.name = mmd_bone.name_j or bone.name
                pmx_bone.name_e = mmd_bone.name_e

                pmx_bone.hasAdditionalRotate = mmd_bone.has_additional_rotation
                pmx_bone.hasAdditionalLocation = mmd_bone.has_additional_location
                pmx_bone.additionalTransform = [mmd_bone.additional_transform_bone, mmd_bone.additional_transform_influence]

                pmx_bone.location = __to_pmx_location(p_bone.head)
                pmx_bone.parent = bone.parent
                # Determine bone visibility: visible if not hidden and either has no collections or belongs to at least one visible collection
                # This logic is the same as Blender's
                pmx_bone.visible = not bone.hide and (not bone.collections or any(collection.is_visible for collection in bone.collections))
                pmx_bone.isControllable = mmd_bone.is_controllable
                pmx_bone.isMovable = not all(p_bone.lock_location)
                pmx_bone.isRotatable = not all(p_bone.lock_rotation)
                pmx_bone.transform_order = mmd_bone.transform_order
                pmx_bone.transAfterPhis = mmd_bone.transform_after_dynamics
                pmx_bones.append(pmx_bone)
                self.__bone_name_table.append(p_bone.name)
                boneMap[bone] = pmx_bone
                r[bone.name] = len(pmx_bones) - 1

                # fmt: off
                if (
                    pmx_bone.parent is not None
                    and (
                        bone.use_connect
                        or (
                            not pmx_bone.isMovable
                            and math.isclose(0.0, (bone.head - pmx_bone.parent.tail).length)
                        )
                    )
                    and p_bone.parent.mmd_bone.is_tip
                ):
                    logging.debug(" * fix location of bone %s, parent %s is tip", bone.name, pmx_bone.parent.name)
                    pmx_bone.location = boneMap[pmx_bone.parent].location
                # fmt: on

                if mmd_bone.display_connection_type == "BONE":
                    if mmd_bone.is_tip:
                        pmx_bone.displayConnection = -1
                    else:
                        pmx_bone.displayConnection = mmd_bone.display_connection_bone_id
                elif mmd_bone.display_connection_type == "OFFSET":
                    if mmd_bone.is_tip:
                        pmx_bone.displayConnection = (0.0, 0.0, 0.0)
                    else:
                        tail_loc = __to_pmx_location(p_bone.tail)
                        pmx_bone.displayConnection = tail_loc - pmx_bone.location

                if mmd_bone.enabled_fixed_axis:
                    pmx_bone.axis = __to_pmx_axis(mmd_bone.fixed_axis, p_bone)

                if mmd_bone.enabled_local_axes:
                    pmx_bone.localCoordinate = pmx.Coordinate(__to_pmx_axis(mmd_bone.local_axis_x, p_bone), __to_pmx_axis(mmd_bone.local_axis_z, p_bone))

            for idx, i in enumerate(pmx_bones):
                if i.parent is not None:
                    i.parent = pmx_bones.index(boneMap[i.parent])
                    logging.debug("the parent of %s:%s: %s", idx, i.name, i.parent)
                if isinstance(i.displayConnection, pmx.Bone):
                    i.displayConnection = pmx_bones.index(i.displayConnection)
                elif isinstance(i.displayConnection, bpy.types.Bone):
                    i.displayConnection = pmx_bones.index(boneMap[i.displayConnection])
                i.additionalTransform[0] = r.get(i.additionalTransform[0], -1)

            if len(pmx_bones) == 0:
                # avoid crashing MMD
                pmx_bone = pmx.Bone()
                pmx_bone.name = "全ての親"
                pmx_bone.name_e = "Root"
                pmx_bone.location = __to_pmx_location([0, 0, 0])
                tail_loc = __to_pmx_location([0, 0, 1])
                pmx_bone.displayConnection = tail_loc - pmx_bone.location
                pmx_bones.append(pmx_bone)

            self.__model.bones = pmx_bones
        self.__exportIK(root, r)
        return r

    def __exportIKLinks(self, pose_bone, count, bone_map, ik_links, custom_bone, ik_export_option):
        if count <= 0 or pose_bone is None or pose_bone.name not in bone_map:
            return ik_links

        logging.debug("    Create IK Link for %s", pose_bone.name)
        ik_link = pmx.IKLink()
        ik_link.target = bone_map[pose_bone.name]

        from math import pi

        minimum, maximum = [-pi] * 3, [pi] * 3
        unused_counts = 0

        if ik_export_option == "IGNORE_ALL":
            unused_counts = 3
        else:
            ik_limit_custom = next((c for c in custom_bone.constraints if c.type == "LIMIT_ROTATION" and c.name == "mmd_ik_limit_custom%d" % len(ik_links)), None)
            ik_limit_override = next((c for c in pose_bone.constraints if c.type == "LIMIT_ROTATION" and not c.mute), None)

            for i, axis in enumerate("xyz"):
                if ik_limit_custom:  # custom ik limits for MMD only
                    if getattr(ik_limit_custom, "use_limit_" + axis):
                        minimum[i] = getattr(ik_limit_custom, "min_" + axis)
                        maximum[i] = getattr(ik_limit_custom, "max_" + axis)
                    else:
                        unused_counts += 1
                    continue

                if getattr(pose_bone, "lock_ik_" + axis):
                    minimum[i] = maximum[i] = 0
                elif ik_limit_override is not None and getattr(ik_limit_override, "use_limit_" + axis):
                    minimum[i] = getattr(ik_limit_override, "min_" + axis)
                    maximum[i] = getattr(ik_limit_override, "max_" + axis)
                elif ik_limit_override is not None and ik_export_option == "OVERRIDE_CONTROLLED":
                    # mmd_ik_limit_override exists but axis disabled, don't check other sources
                    unused_counts += 1
                elif getattr(pose_bone, "use_ik_limit_" + axis):
                    minimum[i] = getattr(pose_bone, "ik_min_" + axis)
                    maximum[i] = getattr(pose_bone, "ik_max_" + axis)
                else:
                    unused_counts += 1

        if unused_counts < 3:
            convertIKLimitAngles = pmx.importer.PMXImporter.convertIKLimitAngles
            bone_matrix = pose_bone.id_data.matrix_world @ pose_bone.matrix
            minimum, maximum = convertIKLimitAngles(minimum, maximum, bone_matrix, invert=True)
            ik_link.minimumAngle = list(minimum)
            ik_link.maximumAngle = list(maximum)

        return self.__exportIKLinks(pose_bone.parent, count - 1, bone_map, ik_links + [ik_link], custom_bone, ik_export_option)

    def __exportIK(self, root, bone_map):
        """Export IK constraints
        @param bone_map the dictionary to map Blender bone names to bone indices of the pmx.model instance.
        """
        pmx_bones = self.__model.bones
        arm = self.__armature
        ik_loop_factor = root.mmd_root.ik_loop_factor
        pose_bones = arm.pose.bones

        logging.info("IK angle limits handling: %s", self.__ik_angle_limits)

        ik_target_custom_map = {getattr(b.constraints.get("mmd_ik_target_custom", None), "subtarget", None): b for b in pose_bones if not b.is_mmd_shadow_bone}

        def __ik_target_bone_get(ik_constraint_bone, ik_bone):
            if ik_bone.name in ik_target_custom_map:
                logging.debug('  (use "mmd_ik_target_custom")')
                return ik_target_custom_map[ik_bone.name]  # for supporting the ik target which is not a child of ik_constraint_bone
            return self.__get_ik_target_bone(ik_constraint_bone)  # this only search the children of ik_constraint_bone

        for bone in pose_bones:
            if bone.is_mmd_shadow_bone:
                continue
            for c in bone.constraints:
                if c.type == "IK" and not c.mute:
                    logging.debug("  Found IK constraint on %s", bone.name)
                    ik_pose_bone = self.__get_ik_control_bone(c)
                    if ik_pose_bone is None:
                        logging.warning('  * Invalid IK constraint "%s" on bone %s', c.name, bone.name)
                        continue

                    ik_bone_index = bone_map.get(ik_pose_bone.name, -1)
                    if ik_bone_index < 0:
                        logging.warning('  * IK bone "%s" not found !!!', ik_pose_bone.name)
                        continue

                    pmx_ik_bone = pmx_bones[ik_bone_index]
                    if pmx_ik_bone.isIK:
                        logging.warning('  * IK bone "%s" is used by another IK setting !!!', ik_pose_bone.name)
                        continue

                    ik_chain0 = bone if c.use_tail else bone.parent
                    ik_target_bone = __ik_target_bone_get(bone, ik_pose_bone) if c.use_tail else bone
                    if ik_target_bone is None:
                        logging.warning("  * IK bone: %s, IK Target not found !!!", ik_pose_bone.name)
                        continue
                    logging.debug("  - IK bone: %s, IK Target: %s", ik_pose_bone.name, ik_target_bone.name)
                    pmx_ik_bone.isIK = True
                    pmx_ik_bone.loopCount = max(int(c.iterations / ik_loop_factor), 1)
                    if ik_pose_bone.name in ik_target_custom_map:
                        pmx_ik_bone.rotationConstraint = ik_pose_bone.mmd_bone.ik_rotation_constraint
                    else:
                        pmx_ik_bone.rotationConstraint = bone.mmd_bone.ik_rotation_constraint
                    pmx_ik_bone.target = bone_map[ik_target_bone.name]
                    pmx_ik_bone.ik_links = self.__exportIKLinks(ik_chain0, c.chain_count, bone_map, [], ik_pose_bone, self.__ik_angle_limits)

    def __get_ik_control_bone(self, ik_constraint):
        arm = ik_constraint.target
        if arm != ik_constraint.id_data:
            return None
        bone = arm.pose.bones.get(ik_constraint.subtarget, None)
        if bone is None:
            return None
        if bone.mmd_shadow_bone_type == "IK_TARGET":
            logging.debug("  Found IK proxy bone: %s -> %s", bone.name, getattr(bone.parent, "name", None))
            return bone.parent
        return bone

    def __get_ik_target_bone(self, target_bone):
        """Get mmd ik target bone.

        Args:
            target_bone: A blender PoseBone

        Returns:
            A bpy.types.PoseBone object which is the closest bone from the tail position of target_bone.
            Return None if target_bone has no child bones.
        """
        valid_children = [c for c in target_bone.children if not c.is_mmd_shadow_bone]

        # search 'mmd_ik_target_override' first
        for c in valid_children:
            ik_target_override = c.constraints.get("mmd_ik_target_override", None)
            if ik_target_override and ik_target_override.subtarget == target_bone.name:
                logging.debug('  (use "mmd_ik_target_override")')
                return c

        r = None
        min_length = None
        for c in valid_children:
            if c.bone.use_connect:
                return c
            length = (c.head - target_bone.tail).length
            if min_length is None or length < min_length:
                min_length = length
                r = c
        return r

    def __exportVertexMorphs(self, meshes, root):
        shape_key_names = []
        for mesh in meshes:
            for i in mesh.shape_key_names:
                if i not in shape_key_names:
                    shape_key_names.append(i)

        morph_categories = {}
        morph_english_names = {}
        if root:
            categories = self.CATEGORIES
            for vtx_morph in root.mmd_root.vertex_morphs:
                morph_english_names[vtx_morph.name] = vtx_morph.name_e
                morph_categories[vtx_morph.name] = categories.get(vtx_morph.category, pmx.Morph.CATEGORY_OHTER)
            shape_key_names.sort(key=lambda x: root.mmd_root.vertex_morphs.find(x))

        for i in shape_key_names:
            morph = pmx.VertexMorph(name=i, name_e=morph_english_names.get(i, ""), category=morph_categories.get(i, pmx.Morph.CATEGORY_OHTER))
            self.__model.morphs.append(morph)

        append_table = dict(zip(shape_key_names, [m.offsets.append for m in self.__model.morphs], strict=False))
        for v in self.__exported_vertices:
            for i, offset in v.offsets.items():
                mo = pmx.VertexMorphOffset()
                mo.index = v.index
                mo.offset = offset
                append_table[i](mo)

    def __export_material_morphs(self, root):
        mmd_root = root.mmd_root
        categories = self.CATEGORIES
        for morph in mmd_root.material_morphs:
            mat_morph = pmx.MaterialMorph(name=morph.name, name_e=morph.name_e, category=categories.get(morph.category, pmx.Morph.CATEGORY_OHTER))
            for data in morph.data:
                morph_data = pmx.MaterialMorphOffset()
                try:
                    if data.material != "":
                        morph_data.index = self.__material_name_table.index(data.material)
                    else:
                        morph_data.index = -1
                except ValueError:
                    logging.warning('Material Morph (%s): Material "%s" was not found.', morph.name, data.material)
                    continue
                morph_data.offset_type = ["MULT", "ADD"].index(data.offset_type)
                morph_data.diffuse_offset = data.diffuse_color
                morph_data.specular_offset = data.specular_color
                morph_data.shininess_offset = data.shininess
                morph_data.ambient_offset = data.ambient_color
                morph_data.edge_color_offset = data.edge_color
                morph_data.edge_size_offset = data.edge_weight
                morph_data.texture_factor = data.texture_factor
                morph_data.sphere_texture_factor = data.sphere_texture_factor
                morph_data.toon_texture_factor = data.toon_texture_factor
                mat_morph.offsets.append(morph_data)
            self.__model.morphs.append(mat_morph)

    def __sortMaterials(self):
        """Sort materials for alpha blending

        モデル内全頂点の平均座標をモデルの中心と考えて、
        モデル中心座標とマテリアルがアサインされている全ての面の構成頂点との平均距離を算出。
        この値が小さい順にソートしてみる。
        モデル中心座標から離れている位置で使用されているマテリアルほどリストの後ろ側にくるように。
        かなりいいかげんな実装
        """
        center = mathutils.Vector([0, 0, 0])
        vertices = self.__model.vertices
        vert_num = len(vertices)
        for v in self.__model.vertices:
            center += mathutils.Vector(v.co) / vert_num

        faces = self.__model.faces
        offset = 0
        distances = []
        for mat, bl_mat_name in zip(self.__model.materials, self.__material_name_table, strict=False):
            d = 0
            face_num = int(mat.vertex_count / 3)
            for i in range(offset, offset + face_num):
                face = faces[i]
                d += (mathutils.Vector(vertices[face[0]].co) - center).length
                d += (mathutils.Vector(vertices[face[1]].co) - center).length
                d += (mathutils.Vector(vertices[face[2]].co) - center).length
            distances.append((d / mat.vertex_count, mat, offset, face_num, bl_mat_name))
            offset += face_num
        sorted_faces = []
        sorted_mat = []
        self.__material_name_table.clear()
        for d, mat, offset, vert_count, bl_mat_name in sorted(distances, key=lambda x: x[0]):
            sorted_faces.extend(faces[offset : offset + vert_count])
            sorted_mat.append(mat)
            self.__material_name_table.append(bl_mat_name)
        self.__model.materials = sorted_mat
        self.__model.faces = sorted_faces

    def __export_bone_morphs(self, root):
        if self.__overwrite_bone_morphs_from_action_pose:
            FnMorph.overwrite_bone_morphs_from_action_pose(self.__armature)

        mmd_root = root.mmd_root
        if len(mmd_root.bone_morphs) == 0:
            return
        categories = self.CATEGORIES
        pose_bones = self.__armature.pose.bones
        matrix_world = self.__armature.matrix_world
        bone_util_cls = BoneConverterPoseMode if self.__armature.data.pose_position != "REST" else BoneConverter

        class _RestBone:
            def __init__(self, b):
                self.matrix_local = matrix_world @ b.bone.matrix_local

        class _PoseBone:  # world space
            def __init__(self, b):
                self.bone = _RestBone(b)
                self.matrix = matrix_world @ b.matrix
                self.matrix_basis = b.matrix_basis
                self.location = b.location

        converter_cache = {}

        def _get_converter(b):
            if b not in converter_cache:
                converter_cache[b] = bone_util_cls(_PoseBone(blender_bone), self.__scale, invert=True)
            return converter_cache[b]

        for morph in mmd_root.bone_morphs:
            bone_morph = pmx.BoneMorph(name=morph.name, name_e=morph.name_e, category=categories.get(morph.category, pmx.Morph.CATEGORY_OHTER))
            for data in morph.data:
                morph_data = pmx.BoneMorphOffset()
                try:
                    morph_data.index = self.__bone_name_table.index(data.bone)
                except ValueError:
                    continue
                blender_bone = pose_bones.get(data.bone, None)
                if blender_bone is None:
                    logging.warning('Bone Morph (%s): Bone "%s" was not found.', morph.name, data.bone)
                    continue
                converter = _get_converter(blender_bone)
                morph_data.location_offset = converter.convert_location(data.location)
                rw, rx, ry, rz = data.rotation
                rw, rx, ry, rz = converter.convert_rotation([rx, ry, rz, rw])
                morph_data.rotation_offset = (rx, ry, rz, rw)
                bone_morph.offsets.append(morph_data)
            self.__model.morphs.append(bone_morph)

    def __export_uv_morphs(self, root):
        mmd_root = root.mmd_root
        if len(mmd_root.uv_morphs) == 0:
            return
        categories = self.CATEGORIES
        append_table_vg = {}
        for morph in mmd_root.uv_morphs:
            uv_morph = pmx.UVMorph(name=morph.name, name_e=morph.name_e, category=categories.get(morph.category, pmx.Morph.CATEGORY_OHTER))
            uv_morph.uv_index = morph.uv_index
            self.__model.morphs.append(uv_morph)
            if morph.data_type == "VERTEX_GROUP":
                append_table_vg[morph.name] = uv_morph.offsets.append
                continue
            logging.warning(' * Deprecated UV morph "%s", please convert it to vertex groups', morph.name)

        if append_table_vg:
            incompleted = set()
            uv_morphs = mmd_root.uv_morphs
            for v in self.__exported_vertices:
                for name, offset in v.uv_offsets.items():
                    if name not in append_table_vg:
                        incompleted.add(name)
                        continue
                    scale = uv_morphs[name].vertex_group_scale
                    morph_data = pmx.UVMorphOffset()
                    morph_data.index = v.index
                    morph_data.offset = (offset[0] * scale, -offset[1] * scale, offset[2] * scale, -offset[3] * scale)
                    append_table_vg[name](morph_data)

            if incompleted:
                logging.warning(" * Incompleted UV morphs %s with vertex groups", incompleted)

    def __export_group_morphs(self, root):
        mmd_root = root.mmd_root
        if len(mmd_root.group_morphs) == 0:
            return
        categories = self.CATEGORIES
        start_index = len(self.__model.morphs)
        for morph in mmd_root.group_morphs:
            group_morph = pmx.GroupMorph(name=morph.name, name_e=morph.name_e, category=categories.get(morph.category, pmx.Morph.CATEGORY_OHTER))
            self.__model.morphs.append(group_morph)

        morph_map = self.__get_pmx_morph_map(root)
        for morph, group_morph in zip(mmd_root.group_morphs, self.__model.morphs[start_index:], strict=False):
            for data in morph.data:
                morph_index = morph_map.get((data.morph_type, data.name), -1)
                if morph_index < 0:
                    logging.warning('Group Morph (%s): Morph "%s" was not found.', morph.name, data.name)
                    continue
                morph_data = pmx.GroupMorphOffset()
                morph_data.morph = morph_index
                morph_data.factor = data.factor
                group_morph.offsets.append(morph_data)

    def __exportDisplayItems(self, root, bone_map):
        res = []
        morph_map = self.__get_pmx_morph_map(root)
        for i in root.mmd_root.display_item_frames:
            d = pmx.Display()
            d.name = i.name
            d.name_e = i.name_e
            d.isSpecial = i.is_special
            items = []
            for j in i.data:
                if j.type == "BONE" and j.name in bone_map:
                    items.append((0, bone_map[j.name]))
                elif j.type == "MORPH" and (j.morph_type, j.name) in morph_map:
                    items.append((1, morph_map[(j.morph_type, j.name)]))
                else:
                    logging.warning("Display item (%s, %s) was not found.", j.type, j.name)
            d.data = items
            res.append(d)
        self.__model.display = res

    def __get_facial_frame(self, root):
        for frame in root.mmd_root.display_item_frames:
            if frame.name == "表情":
                return frame
        return None

    def __get_pmx_morph_map(self, root):
        assert root is not None, "root should not be None when this method is called"

        morph_map = {}
        index = 0

        # Priority: Display Panel order
        facial_frame = self.__get_facial_frame(root)
        if facial_frame:
            for item in facial_frame.data:
                if item.type == "MORPH":
                    key = (item.morph_type, item.name)
                    if key not in morph_map:
                        morph_map[key] = index
                        index += 1

        # Fallback: remaining morphs in original order
        for m in self.__model.morphs:
            key = (self.MORPH_TYPES[type(m)], m.name)
            if key not in morph_map:
                morph_map[key] = index
                index += 1

        return morph_map

    def __exportRigidBodies(self, rigid_bodies, bone_map):
        rigid_map = {}
        rigid_cnt = 0
        Vector = mathutils.Vector
        for obj in rigid_bodies:
            t, r, s = obj.matrix_world.decompose()
            if any(math.isnan(val) for val in t):
                logging.warning(f"Rigid body '{obj.name}' has invalid position coordinates, using default position")
                t = mathutils.Vector((0.0, 0.0, 0.0))
            if any(math.isnan(val) for val in r):
                logging.warning(f"Rigid body '{obj.name}' has invalid rotation coordinates, using default rotation")
                r = mathutils.Euler((0.0, 0.0, 0.0), "YXZ")
            if any(math.isnan(val) for val in s):
                logging.warning(f"Rigid body '{obj.name}' has invalid scale coordinates, using default scale")
                s = mathutils.Vector((1.0, 1.0, 1.0))
            r = r.to_euler("YXZ")
            rb = obj.rigid_body
            if rb is None:
                logging.warning(' * Settings of rigid body "%s" not found, skipped!', obj.name)
                continue
            p_rigid = pmx.Rigid()
            mmd_rigid = obj.mmd_rigid
            p_rigid.name = mmd_rigid.name_j or MoveObject.get_name(obj)
            p_rigid.name_e = mmd_rigid.name_e
            p_rigid.location = Vector(t).xzy * self.__scale
            p_rigid.rotation = Vector(r).xzy * -1
            p_rigid.mode = int(mmd_rigid.type)

            rigid_shape = mmd_rigid.shape
            shape_size = Vector(mmd_rigid.size) * (sum(s) / 3)
            if rigid_shape == "SPHERE":
                p_rigid.type = 0
                p_rigid.size = shape_size * self.__scale
            elif rigid_shape == "BOX":
                p_rigid.type = 1
                p_rigid.size = shape_size.xzy * self.__scale
            elif rigid_shape == "CAPSULE":
                p_rigid.type = 2
                p_rigid.size = shape_size * self.__scale
            else:
                raise Exception("Invalid rigid body type: %s %s", obj.name, rigid_shape)

            p_rigid.bone = bone_map.get(mmd_rigid.bone, -1)
            p_rigid.collision_group_number = mmd_rigid.collision_group_number
            mask = 0
            for i, v in enumerate(mmd_rigid.collision_group_mask):
                if not v:
                    mask += 1 << i
            p_rigid.collision_group_mask = mask

            p_rigid.mass = rb.mass
            p_rigid.friction = rb.friction
            p_rigid.bounce = rb.restitution
            p_rigid.velocity_attenuation = rb.linear_damping
            p_rigid.rotation_attenuation = rb.angular_damping

            self.__model.rigids.append(p_rigid)
            rigid_map[obj] = rigid_cnt
            rigid_cnt += 1
        return rigid_map

    def __exportJoints(self, joints, rigid_map):
        Vector = mathutils.Vector
        for joint in joints:
            t, r, s = joint.matrix_world.decompose()
            r = r.to_euler("YXZ")
            rbc = joint.rigid_body_constraint
            if rbc is None:
                logging.warning(' * Settings of joint "%s" not found, skipped!', joint.name)
                continue
            p_joint = pmx.Joint()
            mmd_joint = joint.mmd_joint
            p_joint.name = mmd_joint.name_j or MoveObject.get_name(joint, "J.")
            p_joint.name_e = mmd_joint.name_e
            p_joint.location = Vector(t).xzy * self.__scale
            p_joint.rotation = Vector(r).xzy * -1
            p_joint.src_rigid = rigid_map.get(rbc.object1, -1)
            p_joint.dest_rigid = rigid_map.get(rbc.object2, -1)
            scale = self.__scale * sum(s) / 3
            p_joint.maximum_location = Vector((rbc.limit_lin_x_upper, rbc.limit_lin_z_upper, rbc.limit_lin_y_upper)) * scale
            p_joint.minimum_location = Vector((rbc.limit_lin_x_lower, rbc.limit_lin_z_lower, rbc.limit_lin_y_lower)) * scale
            p_joint.maximum_rotation = Vector((rbc.limit_ang_x_lower, rbc.limit_ang_z_lower, rbc.limit_ang_y_lower)) * -1
            p_joint.minimum_rotation = Vector((rbc.limit_ang_x_upper, rbc.limit_ang_z_upper, rbc.limit_ang_y_upper)) * -1
            p_joint.spring_constant = Vector(mmd_joint.spring_linear).xzy
            p_joint.spring_rotation_constant = Vector(mmd_joint.spring_angular).xzy
            self.__model.joints.append(p_joint)

    def __convertFaceUVToVertexUV(self, vert_index, uv, normal, vertices_map, face_area, loop_angle, vertex_color):
        vertices = vertices_map[vert_index]
        assert vertices, f"Empty vertices list for vertex index {vert_index}"

        # Normalize vertex_color to always be a Vector (None becomes zero vector)
        color_vec = mathutils.Vector(vertex_color) if vertex_color else mathutils.Vector((0, 0, 0, 0))

        def _ensure_add_uvs(vertex):
            """Ensure vertex has add_uvs list with at least 2 elements"""
            if not hasattr(vertex, "add_uvs"):
                vertex.add_uvs = [None] * 4
            elif len(vertex.add_uvs) < 2:
                vertex.add_uvs.extend([None] * (2 - len(vertex.add_uvs)))

        def _color_to_uv(color_vector):
            """Convert color vector to ADD UV2 format"""
            if color_vector.length > 0:
                return ((color_vector[0], color_vector[1]), (color_vector[2], color_vector[3]))
            return None

        def _color_diff(vertex, current_color_uv):
            """Calculate difference between vertex's existing color and current color"""
            # Return 0.0 if no color data exists (compatible)
            if not hasattr(vertex, "add_uvs") or len(vertex.add_uvs) < 2:
                return 0.0

            existing_color_uv = vertex.add_uvs[1]

            # Both None - perfectly compatible
            if existing_color_uv is None and current_color_uv is None:
                return 0.0

            # One None, one not - incompatible
            if existing_color_uv is None or current_color_uv is None:
                return 1.0  # Large difference to force splitting

            # Calculate maximum component difference
            max_diff = 0.0
            for j in range(2):
                for k in range(2):
                    diff = abs(existing_color_uv[j][k] - current_color_uv[j][k])
                    max_diff = max(max_diff, diff)

            return max_diff

        # Convert current vertex color to ADD UV2 format for comparison
        current_color_uv = _color_to_uv(color_vec)

        if self.__vertex_splitting:  # Vertex splitting mode
            for i in vertices:
                if i.uv is None:
                    # Initialize new vertex with all attributes
                    _ensure_add_uvs(i)
                    i.uv = uv
                    i.normal = normal
                    i.add_uvs[1] = current_color_uv
                    return i
                if (i.uv - uv).length < 0.001 and (normal - i.normal).length < 0.01 and _color_diff(i, current_color_uv) < 0.01:
                    # UV, normal, and vertex color are all compatible within thresholds
                    return i

            # Create new vertex for different UV, normal, or vertex color
            n = copy.copy(vertices[0])  # Shallow copy should be fine
            _ensure_add_uvs(n)
            n.uv = uv
            n.normal = normal
            n.add_uvs[1] = current_color_uv
            vertices.append(n)
            return n

        # Non-splitting mode: UV splits, normals and colors use weighted averaging
        # Find or create vertex based on UV compatibility only
        v = None
        for i in vertices:
            if i.uv is None:
                i.uv = uv
                v = i
                break
            if (i.uv - uv).length < 0.001:  # UV requires exact matching
                v = i
                break

        if v is None:
            # Create new vertex for different UV
            v = copy.copy(vertices[0])
            v.uv = uv
            vertices.append(v)

        # Initialize averaging lists if needed
        for attr_name in ["_normal_list", "_color_list", "_area_list", "_angle_list"]:
            if not hasattr(v, attr_name):
                setattr(v, attr_name, [])

        # Append current values to averaging lists
        v._normal_list.append(normal)
        v._color_list.append(color_vec)
        v._area_list.append(face_area)
        v._angle_list.append(loop_angle)

        # Calculate angle * area weighted averages
        weights = [angle * area for angle, area in zip(v._angle_list, v._area_list, strict=False)]
        total_weight = sum(weights) or 1.0  # Avoid division by zero

        # Average normals
        if len(set(tuple(n) for n in v._normal_list)) == 1:  # All normals identical
            v.normal = normal
        else:
            weighted_normal_sum = sum((n * w for n, w in zip(v._normal_list, weights, strict=False)), mathutils.Vector((0, 0, 0)))
            v.normal = (weighted_normal_sum / total_weight).normalized()

        # Average vertex colors and convert to ADD UV2 format
        if len(set(tuple(c) for c in v._color_list)) == 1:  # All colors identical
            final_color = color_vec
        else:
            weighted_color_sum = sum((c * w for c, w in zip(v._color_list, weights, strict=False)), mathutils.Vector((0, 0, 0, 0)))
            final_color = weighted_color_sum / total_weight

        # Set averaged vertex color as ADD UV2
        _ensure_add_uvs(v)
        v.add_uvs[1] = _color_to_uv(final_color)
        return v

    def __convertAddUV(self, vert, adduv, addzw, uv_index, vertices, rip_vertices):
        assert vertices, "Empty vertices list for additional UV processing"

        if vert.add_uvs[uv_index] is None:
            vert.add_uvs[uv_index] = (adduv, addzw)
            return vert
        for i in rip_vertices:
            uvzw = i.add_uvs[uv_index]
            if (uvzw[0] - adduv).length < 0.001 and (uvzw[1] - addzw).length < 0.001:
                return i
        n = copy.copy(vert)
        add_uvs = n.add_uvs.copy()
        add_uvs[uv_index] = (adduv, addzw)
        n.add_uvs = add_uvs
        vertices.append(n)
        rip_vertices.append(n)
        return n

    @staticmethod
    def __get_normals(mesh, matrix):
        logging.debug(" - Get normals...")
        custom_normals = [(matrix @ cn.vector).normalized() for cn in mesh.corner_normals]
        logging.debug("   - Done (polygons:%d)", len(mesh.polygons))
        return custom_normals

    def __doLoadMeshData(self, meshObj, bone_map):
        def _to_mesh(obj):
            bpy.context.view_layer.update()
            depsgraph = bpy.context.evaluated_depsgraph_get()
            return obj.evaluated_get(depsgraph).to_mesh(depsgraph=depsgraph, preserve_all_data_layers=True)

        def _to_mesh_clear(obj, mesh):
            return obj.to_mesh_clear()

        # Triangulate immediately before processing any loop-based data
        base_mesh = _to_mesh(meshObj)
        needs_triangulation = any(len(poly.vertices) > 3 for poly in base_mesh.polygons)
        if needs_triangulation:
            face_count_before = len(base_mesh.polygons)
            logging.debug(" - Triangulating mesh using Blender standard method...")
            bm = bmesh.new()
            bm.from_mesh(base_mesh)
            bmesh.ops.triangulate(bm, faces=bm.faces, quad_method="BEAUTY", ngon_method="BEAUTY")
            bm.to_mesh(base_mesh)
            bm.free()
            face_count_after = len(base_mesh.polygons)
            logging.debug("   - Triangulation completed (%d -> %d faces)", face_count_before, face_count_after)
        else:
            logging.debug(" - Mesh already triangulated (%d triangular faces)", len(base_mesh.polygons))

        # Process vertex groups after triangulation
        vg_to_bone = {i: bone_map[x.name] for i, x in enumerate(meshObj.vertex_groups) if x.name in bone_map}
        vg_edge_scale = meshObj.vertex_groups.get("mmd_edge_scale", None)
        vg_vertex_order = meshObj.vertex_groups.get("mmd_vertex_order", None)

        # Setup transformation matrices
        pmx_matrix = meshObj.matrix_world * self.__scale
        pmx_matrix[1], pmx_matrix[2] = pmx_matrix[2].copy(), pmx_matrix[1].copy()
        sx, sy, sz = meshObj.matrix_world.to_scale()
        normal_matrix = pmx_matrix.to_3x3()
        if not (sx == sy == sz):
            invert_scale_matrix = mathutils.Matrix([[1.0 / sx, 0, 0], [0, 1.0 / sy, 0], [0, 0, 1.0 / sz]])
            normal_matrix = normal_matrix @ invert_scale_matrix  # reset the scale of meshObj.matrix_world
            normal_matrix = normal_matrix @ invert_scale_matrix  # the scale transform of normals

        # Extract normals and angles from triangulated mesh
        loop_normals = self.__get_normals(base_mesh, normal_matrix)
        bm_temp = bmesh.new()
        bm_temp.from_mesh(base_mesh)
        loop_angles = []
        for face in bm_temp.faces:
            for loop in face.loops:
                loop_angles.append(loop.calc_angle())
        bm_temp.free()

        # Extract vertex colors from triangulated mesh
        vertex_colors = base_mesh.vertex_colors.active
        vertex_color_data = None
        if vertex_colors:
            color_data = [c.color for c in vertex_colors.data]
            # Check if all vertex colors are white (1.0, 1.0, 1.0, 1.0)
            if all(color[0] == 1.0 and color[1] == 1.0 and color[2] == 1.0 and color[3] == 1.0 for color in color_data):
                logging.info("All vertex colors are white - treating as no vertex colors")
            else:
                vertex_color_data = color_data

        # Apply transformation to triangulated mesh
        base_mesh.transform(pmx_matrix)
        remapped_vertex_colors = vertex_color_data

        def _get_weight(vertex_group_index, vertex, default_weight):
            for i in vertex.groups:
                if i.group == vertex_group_index:
                    return i.weight
            return default_weight

        get_edge_scale = None
        if vg_edge_scale:
            def get_edge_scale(x):
                return _get_weight(vg_edge_scale.index, x, 1)
        else:
            def get_edge_scale(x):
                return 1

        get_vertex_order = None
        if self.__vertex_order_map:  # sort vertices
            mesh_id = self.__vertex_order_map.setdefault("mesh_id", 0)
            self.__vertex_order_map["mesh_id"] += 1
            if vg_vertex_order and self.__vertex_order_map["method"] == "CUSTOM":
                def get_vertex_order(x):
                    return (mesh_id, _get_weight(vg_vertex_order.index, x, 2), x.index)
            else:
                def get_vertex_order(x):
                    return (mesh_id, x.index)
        else:
            def get_vertex_order(x):
                return None

        uv_morph_names = {g.index: (n, x) for g, n, x in FnMorph.get_uv_morph_vertex_groups(meshObj)}

        def get_uv_offsets(v):
            uv_offsets = {}
            for x in v.groups:
                if x.group in uv_morph_names and x.weight > 0:
                    name, axis = uv_morph_names[x.group]
                    d = uv_offsets.setdefault(name, [0, 0, 0, 0])
                    d["XYZW".index(axis[1])] += -x.weight if axis[0] == "-" else x.weight
            return uv_offsets

        # Create base vertices from triangulated mesh
        base_vertices = {}
        for v in base_mesh.vertices:
            base_vertices[v.index] = [
                _Vertex(
                    v.co.copy(),
                    [(vg_to_bone[x.group], x.weight) for x in v.groups if x.weight > 0 and x.group in vg_to_bone],
                    {},
                    get_edge_scale(v),
                    get_vertex_order(v),
                    get_uv_offsets(v),
                )
            ]

        # Process UV layers (skip UV2 if vertex colors present)
        bl_add_uvs = [i for i in base_mesh.uv_layers[1:] if not i.name.startswith("_")]

        # Handle UV2 layer based on vertex color presence
        if vertex_colors:
            # When vertex colors exist, UV2 is likely converted from vertex colors - skip it
            if any(uv.name == "UV2" for uv in bl_add_uvs):
                logging.info("Vertex colors detected - UV2 layer treated as vertex color data and skipped.")
                bl_add_uvs = [uv for uv in bl_add_uvs if uv.name != "UV2"]
        else:
            # When no vertex colors, UV2 is treated as normal additional UV layer
            logging.info("No vertex colors detected - all UV layers exported normally.")

        # Check total UV count limit (PMX supports maximum 4 additional UVs)
        total_uv_needed = len(bl_add_uvs)
        if vertex_colors:
            total_uv_needed += 1  # Vertex colors need one UV slot

        if total_uv_needed > 4:
            logging.warning(f"Too many UV channels: {total_uv_needed} needed, but maximum is 4.")
            logging.warning("Some UV data will be lost.")

            if vertex_colors:
                # Prioritize vertex colors, limit other UV layers
                max_other_uvs = 3
                if len(bl_add_uvs) > max_other_uvs:
                    logging.warning(f"Keeping vertex colors and first {max_other_uvs} UV layers.")
                    logging.warning(f"Discarding UV layers: {[uv.name for uv in bl_add_uvs[max_other_uvs:]]}")
                    bl_add_uvs = bl_add_uvs[:max_other_uvs]
            else:
                # No vertex colors, limit to 4 UV layers maximum
                if len(bl_add_uvs) > 4:
                    logging.warning(f"Keeping first 4 UV layers out of {len(bl_add_uvs)}.")
                    logging.warning(f"Discarding UV layers: {[uv.name for uv in bl_add_uvs[4:]]}")
                    bl_add_uvs = bl_add_uvs[:4]

        # Update additional UV count
        self.__add_uv_count = max(self.__add_uv_count, len(bl_add_uvs))
        if vertex_colors:
            self.__add_uv_count = max(self.__add_uv_count, len(bl_add_uvs) + 1, 2)  # Ensure at least 2 for ADD UV2

        # Process faces from triangulated mesh
        class _DummyUV:
            uv1 = uv2 = uv3 = mathutils.Vector((0, 1))

            def __init__(self, uvs):
                self.uv1, self.uv2, self.uv3 = (v.uv.copy() for v in uvs)

        def _UVWrapper(x):
            return (_DummyUV(x[i : i + 3]) for i in range(0, len(x), 3))

        material_faces = {}
        uv_data = base_mesh.uv_layers.active
        if uv_data:
            uv_data = _UVWrapper(uv_data.data)
        else:
            uv_data = iter(lambda: _DummyUV, None)

        face_seq = []
        for face, uv in zip(base_mesh.polygons, uv_data, strict=False):
            if len(face.vertices) != 3:
                raise ValueError(f"Face should be triangulated. Face index: {face.index}, Mesh name: {base_mesh.name}")
            loop_indices = list(face.loop_indices)
            n1, n2, n3 = [loop_normals[idx] for idx in loop_indices]
            a1, a2, a3 = [loop_angles[idx] for idx in loop_indices]
            if remapped_vertex_colors:
                c1, c2, c3 = [remapped_vertex_colors[idx] for idx in loop_indices]
            else:
                c1 = c2 = c3 = None
            face_area = face.area
            v1 = self.__convertFaceUVToVertexUV(face.vertices[0], uv.uv1, n1, base_vertices, face_area, a1, c1)
            v2 = self.__convertFaceUVToVertexUV(face.vertices[1], uv.uv2, n2, base_vertices, face_area, a2, c2)
            v3 = self.__convertFaceUVToVertexUV(face.vertices[2], uv.uv3, n3, base_vertices, face_area, a3, c3)

            t = _Face([v1, v2, v3], face.index)
            face_seq.append(t)
            if face.material_index not in material_faces:
                material_faces[face.material_index] = []
            material_faces[face.material_index].append(t)

        def _mat_name(x):
            return x.name if x else self.__getDefaultMaterial().name
        material_names = {i: _mat_name(m) for i, m in enumerate(base_mesh.materials)}
        material_names = {i: material_names.get(i) or _mat_name(None) for i in material_faces.keys()}

        # Vertex colors are handled directly in __convertFaceUVToVertexUV
        if vertex_colors:
            logging.info("Exported vertex colors as ADD UV2")

        # Export additional UV layers
        for uv_n, uv_tex in enumerate(bl_add_uvs):
            if uv_n > 3:
                logging.warning(" * extra addUV%d+ are not supported", uv_n + 1)
                break
            uv_data = _UVWrapper(uv_tex.data)
            zw_data = base_mesh.uv_layers.get("_" + uv_tex.name, None)
            logging.info(" # exporting addUV%d: %s [zw: %s]", uv_n + 1, uv_tex.name, zw_data)
            if zw_data:
                zw_data = _UVWrapper(zw_data.data)
            else:
                zw_data = iter(lambda: _DummyUV, None)
            rip_vertices_map = {}

            # Adjust UV index if vertex colors are being used for ADD UV2
            actual_uv_index = uv_n
            if vertex_colors:
                # If vertex colors use index 1, shift other UVs accordingly
                if uv_n >= 1:
                    actual_uv_index = uv_n + 1
                elif uv_n == 0:
                    actual_uv_index = 0  # UV1 stays at index 0

            for f, face, uv, zw in zip(face_seq, base_mesh.polygons, uv_data, zw_data, strict=False):
                vertices = [base_vertices[x] for x in face.vertices]
                rip_vertices = [rip_vertices_map.setdefault(x, [x]) for x in f.vertices]
                f.vertices[0] = self.__convertAddUV(f.vertices[0], uv.uv1, zw.uv1, actual_uv_index, vertices[0], rip_vertices[0])
                f.vertices[1] = self.__convertAddUV(f.vertices[1], uv.uv2, zw.uv2, actual_uv_index, vertices[1], rip_vertices[1])
                f.vertices[2] = self.__convertAddUV(f.vertices[2], uv.uv3, zw.uv3, actual_uv_index, vertices[2], rip_vertices[2])

        _to_mesh_clear(meshObj, base_mesh)

        # Calculate shape key offsets
        shape_key_list = []
        if meshObj.data.shape_keys:
            for i, kb in enumerate(meshObj.data.shape_keys.key_blocks):
                if i == 0:  # Basis
                    continue
                if kb.name.startswith("mmd_bind") or kb.name == FnSDEF.SHAPEKEY_NAME:
                    continue
                if kb.name == "mmd_sdef_c":  # make sure 'mmd_sdef_c' is at first
                    shape_key_list = [(i, kb)] + shape_key_list
                else:
                    shape_key_list.append((i, kb))

        shape_key_names = []
        sdef_counts = 0
        for i, kb in shape_key_list:
            shape_key_name = kb.name
            logging.info(" - processing shape key: %s", shape_key_name)
            kb_mute, kb.mute = kb.mute, False
            kb_value, kb.value = kb.value, 1.0
            meshObj.active_shape_key_index = i
            mesh = _to_mesh(meshObj)
            mesh.transform(pmx_matrix)
            kb.mute = kb_mute
            kb.value = kb_value
            if len(mesh.vertices) != len(base_vertices):
                logging.warning("   * Error! vertex count mismatch!")
                continue
            if shape_key_name in {"mmd_sdef_c", "mmd_sdef_r0", "mmd_sdef_r1"}:
                if shape_key_name == "mmd_sdef_c":
                    for v in mesh.vertices:
                        base = base_vertices[v.index][0]
                        if len(base.groups) != 2:
                            continue
                        base_co = base.co
                        c_co = v.co
                        if (c_co - base_co).length < 0.001:
                            continue
                        base.sdef_data[:] = tuple(c_co), base_co, base_co
                        sdef_counts += 1
                    logging.info("   - Restored %d SDEF vertices", sdef_counts)
                elif sdef_counts > 0:
                    ri = 1 if shape_key_name == "mmd_sdef_r0" else 2
                    for v in mesh.vertices:
                        sdef_data = base_vertices[v.index][0].sdef_data
                        if sdef_data:
                            sdef_data[ri] = tuple(v.co)
                    logging.info("   - Updated SDEF data")
            else:
                shape_key_names.append(shape_key_name)
                for v in mesh.vertices:
                    base = base_vertices[v.index][0]
                    offset = v.co - base.co
                    if offset.length < 0.001:
                        continue
                    base.offsets[shape_key_name] = offset
            _to_mesh_clear(meshObj, mesh)

        if not pmx_matrix.is_negative:  # pmx.load/pmx.save reverse face vertices by default
            for f in face_seq:
                f.vertices.reverse()

        return _Mesh(material_faces, shape_key_names, material_names)

    def __loadMeshData(self, meshObj, bone_map):
        show_only_shape_key = meshObj.show_only_shape_key
        active_shape_key_index = meshObj.active_shape_key_index
        meshObj.active_shape_key_index = 0
        uv_textures = getattr(meshObj.data, "uv_textures", meshObj.data.uv_layers)
        active_uv_texture_index = uv_textures.active_index
        uv_textures.active_index = 0

        muted_modifiers = []
        for m in meshObj.modifiers:
            if m.type != "ARMATURE" or m.object is None:
                continue
            if m.object.data.pose_position == "REST":
                muted_modifiers.append((m, m.show_viewport))
                m.show_viewport = False

        try:
            logging.info("Loading mesh: %s", meshObj.name)
            meshObj.show_only_shape_key = bool(muted_modifiers)
            return self.__doLoadMeshData(meshObj, bone_map)
        finally:
            meshObj.show_only_shape_key = show_only_shape_key
            meshObj.active_shape_key_index = active_shape_key_index
            uv_textures.active_index = active_uv_texture_index
            for m, show in muted_modifiers:
                m.show_viewport = show

    def __translate_armature(self, root_object: bpy.types.Object):
        FnTranslations.clear_data(root_object.mmd_root.translation)
        FnTranslations.collect_data(root_object.mmd_root.translation)
        FnTranslations.update_query(root_object.mmd_root.translation)
        FnTranslations.execute_translation_batch(root_object)
        FnTranslations.apply_translations(root_object)
        FnTranslations.clear_data(root_object.mmd_root.translation)

    def execute(self, filepath, **args):
        root = args.get("root")
        self.__model = pmx.Model()
        self.__model.name = "test"
        self.__model.name_e = "test eng"
        self.__model.comment = "exported by mmd_tools"
        self.__model.comment_e = "exported by mmd_tools"

        if root is not None:
            if root.mmd_root.name:
                self.__model.name = root.mmd_root.name
            else:
                logging.warning(f"Model name is empty, using root object name '{root.name}' instead")
                self.__model.name = root.name
            self.__model.name_e = root.mmd_root.name_e
            txt = bpy.data.texts.get(root.mmd_root.comment_text, None)
            if txt:
                self.__model.comment = txt.as_string().replace("\n", "\r\n")
            txt = bpy.data.texts.get(root.mmd_root.comment_e_text, None)
            if txt:
                self.__model.comment_e = txt.as_string().replace("\n", "\r\n")

        self.__armature = args.get("armature")
        meshes = sorted(args.get("meshes", []), key=lambda x: x.name)
        rigids = sorted(args.get("rigid_bodies", []), key=lambda x: x.name)
        joints = sorted(args.get("joints", []), key=lambda x: x.name)

        bpy.ops.mmd_tools.fix_bone_order()

        self.__scale = args.get("scale", 1.0)
        self.__disable_specular = args.get("disable_specular", False)
        self.__vertex_splitting = args.get("vertex_splitting", False)
        self.__ik_angle_limits = args.get("ik_angle_limits", "EXPORT_ALL")
        sort_vertices = args.get("sort_vertices", "NONE")
        if sort_vertices != "NONE":
            self.__vertex_order_map = {"method": sort_vertices}

        self.__overwrite_bone_morphs_from_action_pose = args.get("overwrite_bone_morphs_from_action_pose", False)
        self.__translate_in_presets = args.get("translate_in_presets", False)

        if self.__translate_in_presets:
            self.__translate_armature(root)

        nameMap = self.__exportBones(root, meshes)

        mesh_data = [self.__loadMeshData(i, nameMap) for i in meshes]
        self.__exportMeshes(mesh_data, nameMap)
        if args.get("sort_materials", False):
            self.__sortMaterials()

        self.__exportVertexMorphs(mesh_data, root)
        if root is not None:
            self.__export_bone_morphs(root)
            self.__export_material_morphs(root)
            self.__export_uv_morphs(root)
            self.__export_group_morphs(root)

            # Sort morphs by Display Panel facial frame order for PMX export
            # Reference: https://github.com/MMD-Blender/blender_mmd_tools/issues/77
            morph_map = self.__get_pmx_morph_map(root)
            self.__model.morphs.sort(key=lambda m: morph_map.get((self.MORPH_TYPES[type(m)], m.name), float("inf")))

            self.__exportDisplayItems(root, nameMap)

        rigid_map = self.__exportRigidBodies(rigids, nameMap)
        self.__exportJoints(joints, rigid_map)

        if args.get("copy_textures", False):
            output_dir = os.path.dirname(filepath)
            import_folder = root.get("import_folder", "") if root else ""
            base_folder = FnContext.get_addon_preferences_attribute(FnContext.ensure_context(), "base_texture_folder", "")
            self.__copy_textures(output_dir, import_folder or base_folder)

        # Output Changes in Vertex and Face Count
        original_vertex_count = 0
        original_face_count = 0
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for mesh_obj in meshes:
            obj_eval = mesh_obj.evaluated_get(depsgraph)
            mesh_eval = obj_eval.data
            original_vertex_count += len(mesh_eval.vertices)
            original_face_count += len(mesh_eval.polygons)
        final_vertex_count = len(self.__model.vertices)
        final_face_count = len(self.__model.faces)
        vertex_diff = final_vertex_count - original_vertex_count
        face_diff = final_face_count - original_face_count
        triangulation_ratio = final_face_count / original_face_count if original_face_count > 0 else 0
        logging.info("Changes in Vertex and Face Count:")
        logging.info("  Vertex Splitting for Normals: %s", "Enabled" if self.__vertex_splitting else "Disabled")
        logging.info("  Vertices: Original %d -> Output %d (%+d)", original_vertex_count, final_vertex_count, vertex_diff)
        logging.info("  Faces: Original %d -> Output %d (%+d)", original_face_count, final_face_count, face_diff)
        logging.info("  Face Triangulation Ratio: %.2fx (Output / Original)", triangulation_ratio)

        pmx.save(filepath, self.__model, add_uv_count=self.__add_uv_count)


def export(filepath, **kwargs):
    logging.info("****************************************")
    logging.info(" %s module" % __name__)
    logging.info("----------------------------------------")
    start_time = time.time()
    exporter = __PmxExporter()
    exporter.execute(filepath, **kwargs)
    logging.info(" Finished exporting the model in %f seconds.", time.time() - start_time)
    logging.info("----------------------------------------")
    logging.info(" %s module" % __name__)
    logging.info("****************************************")
