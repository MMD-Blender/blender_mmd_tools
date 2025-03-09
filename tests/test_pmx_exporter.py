# -*- coding: utf-8 -*-

import os
import shutil
import unittest

import bpy

from math import pi
from mathutils import Euler
from mathutils import Vector
from bl_ext.user_default.mmd_tools.core import pmx
from bl_ext.user_default.mmd_tools.core.model import Model
from bl_ext.user_default.mmd_tools.core.pmd.importer import import_pmd_to_pmx
from bl_ext.user_default.mmd_tools.core.pmx.importer import PMXImporter

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), 'samples')

class TestPmxExporter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        '''
        Clean up output from previous tests
        '''
        output_dir = os.path.join(TESTS_DIR, 'output')
        for item in os.listdir(output_dir):
            if item.endswith('.OUTPUT'):
                continue  # Skip the placeholder
            item_fp = os.path.join(output_dir, item)
            if os.path.isfile(item_fp):
                os.remove(item_fp)
            elif os.path.isdir(item_fp):
                shutil.rmtree(item_fp)

    def setUp(self):
        '''
        '''
        import logging
        logger = logging.getLogger()
        logger.setLevel('ERROR')

    #********************************************
    # Utils
    #********************************************

    def __axis_error(self, axis0, axis1):
        return (Vector(axis0).normalized() - Vector(axis1).normalized()).length

    def __vector_error(self, vec0, vec1):
        return (Vector(vec0) - Vector(vec1)).length

    def __quaternion_error(self, quat0, quat1):
        angle = quat0.rotation_difference(quat1).angle % pi
        assert(angle >= 0)
        return min(angle, pi-angle)

    #********************************************
    # Header & Informations
    #********************************************

    def __check_pmx_header_info(self, source_model, result_model, import_types):
        '''
        Test pmx model info, header
        '''
        # Informations ================

        self.assertEqual(source_model.name, result_model.name)
        self.assertEqual(source_model.name_e, result_model.name_e)
        self.assertEqual(source_model.comment.replace('\r', ''), result_model.comment.replace('\r', ''))
        self.assertEqual(source_model.comment_e.replace('\r', ''), result_model.comment_e.replace('\r', ''))

        # Header ======================

        if source_model.header:
            source_header = source_model.header
            result_header = result_model.header
            self.assertEqual(source_header.sign, result_header.sign)
            self.assertEqual(source_header.version, result_header.version)
            self.assertEqual(source_header.encoding.index, result_header.encoding.index)
            self.assertEqual(source_header.encoding.charset, result_header.encoding.charset)
            if 'MESH' in import_types:
                self.assertEqual(source_header.additional_uvs, result_header.additional_uvs)
                self.assertEqual(source_header.vertex_index_size, result_header.vertex_index_size)
                self.assertEqual(source_header.texture_index_size, result_header.texture_index_size)
                self.assertEqual(source_header.material_index_size, result_header.material_index_size)
            if 'ARMATURE' in import_types:
                self.assertEqual(source_header.bone_index_size, result_header.bone_index_size)
            if 'MORPHS' in import_types:
                self.assertEqual(source_header.morph_index_size, result_header.morph_index_size)
            if 'PHYSICS' in import_types:
                self.assertEqual(source_header.rigid_index_size, result_header.rigid_index_size)

    #********************************************
    # Mesh
    #********************************************

    def __get_pmx_textures(self, textures):
        ret = []
        for t in textures:
            path = t.path
            path = os.path.basename(path)
            ret.append(path)
        return ret

    def __get_texture(self, tex_id, textures):
        if 0 <= tex_id < len(textures):
            return textures[tex_id]
        return tex_id

    def __get_toon_texture(self, tex_id, textures, is_shared):
        return tex_id if is_shared else self.__get_texture(tex_id, textures)

    def __check_pmx_mesh(self, source_model, result_model):
        '''
        Test pmx textures, materials, vertices, faces
        '''
        # textures ====================
        # TODO

        source_textures = self.__get_pmx_textures(source_model.textures)
        result_textures = self.__get_pmx_textures(result_model.textures)
        self.assertEqual(len(source_textures), len(result_textures))
        for tex0, tex1 in zip(sorted(source_textures), sorted(result_textures)):
            self.assertEqual(tex0, tex1)

        # materials ===================

        source_materials = source_model.materials
        result_materials = result_model.materials
        self.assertEqual(len(source_materials), len(result_materials))

        for mat0, mat1 in zip(source_materials, result_materials):
            msg = mat0.name
            self.assertEqual(mat0.name, mat1.name, msg)
            self.assertEqual(mat0.name_e, mat1.name_e, msg)
            self.assertEqual(mat0.diffuse, mat1.diffuse, msg)
            self.assertEqual(mat0.specular, mat1.specular, msg)
            self.assertEqual(mat0.shininess, mat1.shininess, msg)
            self.assertEqual(mat0.ambient, mat1.ambient, msg)
            self.assertEqual(mat0.is_double_sided, mat1.is_double_sided, msg)
            self.assertEqual(mat0.enabled_drop_shadow, mat1.enabled_drop_shadow, msg)
            self.assertEqual(mat0.enabled_self_shadow_map, mat1.enabled_self_shadow_map, msg)
            self.assertEqual(mat0.enabled_self_shadow, mat1.enabled_self_shadow, msg)
            self.assertEqual(mat0.enabled_toon_edge, mat1.enabled_toon_edge, msg)
            self.assertEqual(mat0.edge_color, mat1.edge_color, msg)
            self.assertEqual(mat0.edge_size, mat1.edge_size, msg)
            self.assertEqual(mat0.comment, mat1.comment, msg)
            self.assertEqual(mat0.vertex_count, mat1.vertex_count, msg)

            tex0 = self.__get_texture(mat0.texture, source_textures)
            tex1 = self.__get_texture(mat1.texture, result_textures)
            self.assertEqual(tex0, tex1, msg)

            self.assertEqual(mat0.sphere_texture_mode, mat1.sphere_texture_mode, msg)
            sph0 = self.__get_texture(mat0.sphere_texture, source_textures)
            sph1 = self.__get_texture(mat1.sphere_texture, result_textures)
            self.assertEqual(sph0, sph1, msg)

            self.assertEqual(mat0.is_shared_toon_texture, mat1.is_shared_toon_texture, msg)
            toon0 = self.__get_toon_texture(mat0.toon_texture, source_textures, mat0.is_shared_toon_texture)
            toon1 = self.__get_toon_texture(mat1.toon_texture, result_textures, mat1.is_shared_toon_texture)
            self.assertEqual(toon0, toon1, msg)

        # vertices & faces ============
        # TODO

        source_vertices = source_model.vertices
        result_vertices = result_model.vertices
        #self.assertEqual(len(source_vertices), len(result_vertices))

        source_faces = source_model.faces
        result_faces = result_model.faces
        self.assertEqual(len(source_faces), len(result_faces))

        for f0, f1 in zip(source_faces, result_faces):
            seq0 = [source_vertices[i] for i in f0]
            seq1 = [result_vertices[i] for i in f1]
            for v0, v1 in zip(seq0, seq1):
                self.assertLess(self.__vector_error(v0.co, v1.co), 1e-6)
                self.assertLess(self.__vector_error(v0.uv, v1.uv), 1e-6)
                #self.assertLess(self.__vector_error(v0.normal, v1.normal), 1e-3)

                self.assertEqual(v0.additional_uvs, v1.additional_uvs)
                self.assertEqual(v0.edge_scale, v1.edge_scale)
                #self.assertEqual(v0.weight.weights, v1.weight.weights)
                #self.assertEqual(v0.weight.bones, v1.weight.bones)

    #********************************************
    # Armature
    #********************************************

    def __get_bone(self, bone_id, bones):
        if bone_id is not None and 0 <= bone_id < len(bones):
            return bones[bone_id]
        return bone_id

    def __get_bone_name(self, bone_id, bones):
        if bone_id is not None and 0 <= bone_id < len(bones):
            return bones[bone_id].name
        return bone_id

    def __get_bone_display_connection(self, bone, bones):
        displayConnection = bone.displayConnection
        if isinstance(displayConnection, int):
            if displayConnection == -1:
                return (0.0, 0.0, 0.0)
            tail_bone = self.__get_bone(displayConnection, bones)
            if self.__get_bone_name(tail_bone.parent, bones) == bone.name and not tail_bone.isMovable:
                return tail_bone.name
            return tuple(Vector(tail_bone.location) - Vector(bone.location))
        return displayConnection

    def __check_pmx_bones(self, source_model, result_model):
        '''
        Test pmx bones
        '''
        source_bones = source_model.bones
        result_bones = result_model.bones
        self.assertEqual(len(source_bones), len(result_bones))

        # check bone order
        bone_order0 = [x.name for x in source_bones]
        bone_order1 = [x.name for x in result_bones]
        self.assertEqual(bone_order0, bone_order1)

        for bone0, bone1 in zip(source_bones, result_bones):
            msg = bone0.name
            self.assertEqual(bone0.name, bone1.name, msg)
            self.assertEqual(bone0.name_e, bone1.name_e, msg)
            self.assertLess(self.__vector_error(bone0.location, bone1.location), 1e-6, msg)

            parent0 = self.__get_bone_name(bone0.parent, source_bones)
            parent1 = self.__get_bone_name(bone1.parent, result_bones)
            self.assertEqual(parent0, parent1, msg)

            self.assertEqual(bone0.transform_order, bone1.transform_order, msg)
            self.assertEqual(bone0.isRotatable, bone1.isRotatable, msg)
            self.assertEqual(bone0.isMovable and not bone0.axis, bone1.isMovable, msg)
            self.assertEqual(bone0.visible, bone1.visible, msg)
            self.assertEqual(bone0.isControllable, bone1.isControllable, msg)
            self.assertEqual(bone0.isIK, bone1.isIK, msg)
            self.assertEqual(bone0.transAfterPhis, bone1.transAfterPhis, msg)
            self.assertEqual(bone0.externalTransKey, bone1.externalTransKey, msg)

            if bone0.axis and bone1.axis:
                self.assertLess(self.__axis_error(bone0.axis, bone1.axis), 1e-6, msg)
            else:
                self.assertEqual(bone0.axis, bone1.axis, msg)

            if bone0.localCoordinate and bone1.localCoordinate:
                self.assertLess(self.__axis_error(bone0.localCoordinate.x_axis, bone1.localCoordinate.x_axis), 1e-6, msg)
                self.assertLess(self.__axis_error(bone0.localCoordinate.z_axis, bone1.localCoordinate.z_axis), 1e-6, msg)
            else:
                self.assertEqual(bone0.localCoordinate, bone1.localCoordinate, msg)

            self.assertEqual(bone0.hasAdditionalRotate, bone1.hasAdditionalRotate, msg)
            self.assertEqual(bone0.hasAdditionalLocation, bone1.hasAdditionalLocation, msg)
            if bone0.additionalTransform and bone1.additionalTransform:
                at_target0, at_infl0 = bone0.additionalTransform
                at_target1, at_infl1 = bone1.additionalTransform
                at_target0 = self.__get_bone_name(at_target0, source_bones)
                at_target1 = self.__get_bone_name(at_target1, result_bones)
                self.assertEqual(at_target0, at_target1, msg)
                self.assertLess(abs(at_infl0 - at_infl1), 1e-4, msg)
            else:
                self.assertEqual(bone0.additionalTransform, bone1.additionalTransform, msg)

            target0 = self.__get_bone_name(bone0.target, source_bones)
            target1 = self.__get_bone_name(bone1.target, result_bones)
            self.assertEqual(target0, target1, msg)
            self.assertEqual(bone0.loopCount, bone1.loopCount, msg)
            self.assertEqual(bone0.rotationConstraint, bone1.rotationConstraint, msg)
            self.assertEqual(len(bone0.ik_links), len(bone1.ik_links), msg)
            for link0, link1 in zip(bone0.ik_links, bone1.ik_links):
                target0 = self.__get_bone_name(link0.target, source_bones)
                target1 = self.__get_bone_name(link1.target, result_bones)
                self.assertEqual(target0, target1, msg)

                maximumAngle0 = link0.maximumAngle
                maximumAngle1 = link1.maximumAngle
                if maximumAngle0 and maximumAngle1:
                    self.assertLess(self.__vector_error(maximumAngle0, maximumAngle1), 1e-6, msg)
                else:
                    self.assertEqual(maximumAngle0, maximumAngle1, msg)

                minimumAngle0 = link0.minimumAngle
                minimumAngle1 = link1.minimumAngle
                if minimumAngle0 and minimumAngle1:
                    self.assertLess(self.__vector_error(minimumAngle0, minimumAngle1), 1e-6, msg)
                else:
                    self.assertEqual(minimumAngle0, minimumAngle1, msg)

        for bone0, bone1 in zip(source_bones, result_bones):
            msg = bone0.name
            displayConnection0 = self.__get_bone_display_connection(bone0, source_bones)
            displayConnection1 = self.__get_bone_display_connection(bone1, result_bones)
            if not isinstance(displayConnection0, str) and not isinstance(displayConnection1, str):
                self.assertLess(self.__vector_error(displayConnection0, displayConnection1), 1e-4, msg)
            else:
                self.assertEqual(displayConnection0, displayConnection1, msg)

    #********************************************
    # Physics
    #********************************************

    def __get_rigid_name(self, rigid_id, rigids):
        if rigid_id is not None and 0 <= rigid_id < len(rigids):
            return rigids[rigid_id].name
        return rigid_id

    def __check_pmx_physics(self, source_model, result_model):
        '''
        Test pmx rigids, joints
        '''
        # rigids ======================

        source_rigids = source_model.rigids
        result_rigids = result_model.rigids
        self.assertEqual(len(source_rigids), len(result_rigids))

        source_bones = source_model.bones
        result_bones = result_model.bones

        for rigid0, rigid1 in zip(source_rigids, result_rigids):
            msg = rigid0.name
            self.assertEqual(rigid0.name, rigid1.name, msg)
            self.assertEqual(rigid0.name_e, rigid1.name_e, msg)

            bone0 = self.__get_bone_name(rigid0.bone, source_bones)
            bone1 = self.__get_bone_name(rigid0.bone, source_bones)
            self.assertEqual(bone0, bone1, msg)

            self.assertEqual(rigid0.collision_group_number, rigid1.collision_group_number, msg)
            self.assertEqual(rigid0.collision_group_mask, rigid1.collision_group_mask, msg)

            self.assertEqual(rigid0.type, rigid1.type, msg)
            if rigid0.type == 0: # SHAPE_SPHERE
                self.assertLess(abs(rigid0.size[0]-rigid1.size[0]), 1e-6, msg)
            elif rigid0.type == 1: # SHAPE_BOX
                self.assertLess(self.__vector_error(rigid0.size, rigid1.size), 1e-6, msg)
            elif rigid0.type == 2: # SHAPE_CAPSULE
                self.assertLess(self.__vector_error(rigid0.size[0:2], rigid1.size[0:2]), 1e-6, msg)

            self.assertLess(self.__vector_error(rigid0.location, rigid1.location), 1e-6, msg)
            rigid0_rotation = Euler(rigid0.rotation,'YXZ').to_quaternion()
            rigid1_rotation = Euler(rigid1.rotation,'YXZ').to_quaternion()
            self.assertLess(self.__quaternion_error(rigid0_rotation, rigid1_rotation), 1e-6, msg)
            self.assertEqual(rigid0.mass, rigid1.mass, msg)
            self.assertEqual(rigid0.velocity_attenuation, rigid1.velocity_attenuation, msg)
            self.assertEqual(rigid0.rotation_attenuation, rigid1.rotation_attenuation, msg)
            self.assertEqual(rigid0.bounce, rigid1.bounce, msg)
            self.assertEqual(rigid0.friction, rigid1.friction, msg)
            self.assertEqual(rigid0.mode, rigid1.mode, msg)

        # joints ======================

        source_joints = source_model.joints
        result_joints = result_model.joints
        self.assertEqual(len(source_joints), len(result_joints))

        for joint0, joint1 in zip(source_joints, result_joints):
            msg = joint0.name
            self.assertEqual(joint0.name, joint1.name, msg)
            self.assertEqual(joint0.name_e, joint1.name_e, msg)
            self.assertEqual(joint0.mode, joint1.mode, msg)

            src_rigid0 = self.__get_rigid_name(joint0.src_rigid, source_rigids)
            src_rigid1 = self.__get_rigid_name(joint1.src_rigid, result_rigids)
            self.assertEqual(src_rigid0, src_rigid1, msg)

            dest_rigid0 = self.__get_rigid_name(joint0.dest_rigid, source_rigids)
            dest_rigid1 = self.__get_rigid_name(joint1.dest_rigid, result_rigids)
            self.assertEqual(dest_rigid0, dest_rigid1, msg)

            self.assertEqual(joint0.location, joint1.location, msg)
            joint0_rotation = Euler(joint0.rotation,'YXZ').to_quaternion()
            joint1_rotation = Euler(joint1.rotation,'YXZ').to_quaternion()
            self.assertLess(self.__quaternion_error(joint0_rotation, joint1_rotation), 1e-6, msg)
            self.assertLess(self.__vector_error(joint0.maximum_location, joint1.maximum_location), 1e-6, msg)
            self.assertLess(self.__vector_error(joint0.minimum_location, joint1.minimum_location), 1e-6, msg)
            self.assertEqual(joint0.maximum_rotation, joint1.maximum_rotation, msg)
            self.assertEqual(joint0.minimum_rotation, joint1.minimum_rotation, msg)
            self.assertEqual(joint0.spring_constant, joint1.spring_constant, msg)
            self.assertEqual(joint0.spring_rotation_constant, joint1.spring_rotation_constant, msg)

    #********************************************
    # Morphs
    #********************************************
    def __get_material(self, index, materials):
        if 0 <= index < len(materials):
            return materials[index]
        class _dummy:
            name = None
        return _dummy

    def __check_pmx_morphs(self, source_model, result_model):
        '''
        Test pmx morphs
        '''
        source_morphs = source_model.morphs
        result_morphs = result_model.morphs
        self.assertEqual(len(source_morphs), len(result_morphs))

        source_table = {}
        for m in source_morphs:
            source_table.setdefault(type(m), []).append(m)
        result_table = {}
        for m in result_morphs:
            result_table.setdefault(type(m), []).append(m)

        self.assertEqual(source_table.keys(), result_table.keys(), 'types mismatch')

        #source_vertices = source_model.vertices
        #result_vertices = result_model.vertices

        # VertexMorph =================
        # TODO

        source = source_table.get(pmx.VertexMorph, [])
        result = result_table.get(pmx.VertexMorph, [])
        self.assertEqual(len(source), len(result))
        for m0, m1 in zip(source, result):
            msg = 'VertexMorph %s'%m0.name
            self.assertEqual(m0.name, m1.name, msg)
            self.assertEqual(m0.name_e, m1.name_e, msg)
            self.assertEqual(m0.category, m1.category, msg)
            #self.assertEqual(len(m0.offsets), len(m1.offsets), msg)

        # UVMorph =====================
        # TODO

        source = source_table.get(pmx.UVMorph, [])
        result = result_table.get(pmx.UVMorph, [])
        self.assertEqual(len(source), len(result))
        for m0, m1 in zip(source, result):
            msg = 'UVMorph %s'%m0.name
            self.assertEqual(m0.name, m1.name, msg)
            self.assertEqual(m0.name_e, m1.name_e, msg)
            self.assertEqual(m0.category, m1.category, msg)
            self.assertEqual(len(m0.offsets), len(m1.offsets), msg)
            #for s0, s1 in zip(m0.offsets, m1.offsets):
            #    self.assertEqual(s0.index, s1.index, msg)
            #    self.assertEqual(s0.offset, s1.offset, msg)

        # BoneMorph ===================

        source_bones = source_model.bones
        result_bones = result_model.bones

        source = source_table.get(pmx.BoneMorph, [])
        result = result_table.get(pmx.BoneMorph, [])
        self.assertEqual(len(source), len(result))
        for m0, m1 in zip(source, result):
            msg = 'BoneMorph %s'%m0.name
            self.assertEqual(m0.name, m1.name, msg)
            self.assertEqual(m0.name_e, m1.name_e, msg)
            self.assertEqual(m0.category, m1.category, msg)
            # the source may contains invalid data
            source_offsets = [m for m in m0.offsets if 0 <= m.index < len(source_bones)]
            result_offsets = m1.offsets
            self.assertEqual(len(source_offsets), len(result_offsets), msg)
            for s0, s1 in zip(source_offsets, result_offsets):
                bone0 = source_bones[s0.index]
                bone1 = result_bones[s1.index]
                self.assertEqual(bone0.name, bone1.name, msg)
                self.assertLess(self.__vector_error(s0.location_offset, s1.location_offset), 1e-5, msg)
                self.assertLess(self.__vector_error(s0.rotation_offset, s1.rotation_offset), 1e-5, msg)

        # MaterialMorph ===============

        source_materials = source_model.materials
        result_materials = result_model.materials

        source = source_table.get(pmx.MaterialMorph, [])
        result = result_table.get(pmx.MaterialMorph, [])
        self.assertEqual(len(source), len(result))
        for m0, m1 in zip(source, result):
            msg = 'MaterialMorph %s'%m0.name
            self.assertEqual(m0.name, m1.name, msg)
            self.assertEqual(m0.name_e, m1.name_e, msg)
            self.assertEqual(m0.category, m1.category, msg)
            source_offsets = m0.offsets
            result_offsets = m1.offsets
            self.assertEqual(len(source_offsets), len(result_offsets), msg)
            for s0, s1 in zip(source_offsets, result_offsets):
                mat0 = self.__get_material(s0.index, source_materials)
                mat1 = self.__get_material(s1.index, result_materials)
                self.assertEqual(mat0.name, mat1.name, msg)
                self.assertEqual(s0.offset_type, s1.offset_type, msg)
                self.assertEqual(s0.diffuse_offset, s1.diffuse_offset, msg)
                self.assertEqual(s0.specular_offset, s1.specular_offset, msg)
                self.assertEqual(s0.shininess_offset, s1.shininess_offset, msg)
                self.assertEqual(s0.ambient_offset, s1.ambient_offset, msg)
                self.assertEqual(s0.edge_color_offset, s1.edge_color_offset, msg)
                self.assertEqual(s0.edge_size_offset, s1.edge_size_offset, msg)
                self.assertEqual(s0.texture_factor, s1.texture_factor, msg)
                self.assertEqual(s0.sphere_texture_factor, s1.sphere_texture_factor, msg)
                self.assertEqual(s0.toon_texture_factor, s1.toon_texture_factor, msg)

        # GroupMorph ==================

        source = source_table.get(pmx.GroupMorph, [])
        result = result_table.get(pmx.GroupMorph, [])
        self.assertEqual(len(source), len(result))
        for m0, m1 in zip(source, result):
            msg = 'GroupMorph %s'%m0.name
            self.assertEqual(m0.name, m1.name, msg)
            self.assertEqual(m0.name_e, m1.name_e, msg)
            self.assertEqual(m0.category, m1.category, msg)
            # the source may contains invalid data
            source_offsets = [m for m in m0.offsets if 0 <= m.morph < len(source_morphs)]
            result_offsets = m1.offsets
            self.assertEqual(len(source_offsets), len(result_offsets), msg)
            for s0, s1 in zip(source_offsets, result_offsets):
                morph0 = source_morphs[s0.morph]
                morph1 = result_morphs[s1.morph]
                self.assertEqual(morph0.name, morph1.name, msg)
                self.assertEqual(morph0.category, morph1.category, msg)
                self.assertEqual(s0.factor, s1.factor, msg)

    #********************************************
    # Display
    #********************************************

    def __check_pmx_display_data(self, source_model, result_model, check_morphs):
        '''
        Test pmx display
        '''
        source_display = source_model.display
        result_display = result_model.display
        self.assertEqual(len(source_display), len(result_display))

        for source, result in zip(source_display, result_display):
            self.assertEqual(source.name, result.name)
            self.assertEqual(source.name_e, result.name_e)
            self.assertEqual(source.isSpecial, result.isSpecial)

            source_items = source.data
            if not check_morphs:
                source_items = [i for i in source_items if i[0] == 0]
            result_items = result.data

            self.assertEqual(len(source_items), len(result_items))
            for item0, item1 in zip(source_items, result_items):
                disp_type0, index0 = item0
                disp_type1, index1 = item1
                self.assertEqual(disp_type0, disp_type1)
                if disp_type0 == 0:
                    bone_name0 = source_model.bones[index0].name
                    bone_name1 = result_model.bones[index1].name
                    self.assertEqual(bone_name0, bone_name1)
                elif disp_type0 == 1:
                    morph0 = source_model.morphs[index0]
                    morph1 = result_model.morphs[index1]
                    self.assertEqual(morph0.name, morph1.name)
                    self.assertEqual(morph0.category, morph1.category)

    #********************************************
    # Test Function
    #********************************************

    def __get_import_types(self, types):
        types = types.copy()
        if 'PHYSICS' in types:
            types.add('ARMATURE')
        if 'DISPLAY' in types:
            types.add('ARMATURE')
        if 'MORPHS' in types:
            types.add('ARMATURE')
            types.add('MESH')
        return types

    def __list_sample_files(self, file_types):
        ret = []
        for file_type in file_types:
            file_ext ='.' + file_type
            for root, dirs, files in os.walk(os.path.join(SAMPLES_DIR, file_type)):
                for name in files:
                    if name.lower().endswith(file_ext):
                        ret.append(os.path.join(root, name))
        return ret

    def __enable_mmd_tools(self):
        bpy.ops.wm.read_homefile() # reload blender startup file
        pref = getattr(bpy.context, 'preferences', None) or bpy.context.user_preferences
        if not pref.addons.get('mmd_tools', None):
            addon_enable = bpy.ops.wm.addon_enable if 'addon_enable' in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module='bl_ext.user_default.mmd_tools') # make sure addon 'mmd_tools' is enabled

    def test_pmx_exporter(self):
        '''
        '''
        input_files = self.__list_sample_files(('pmd', 'pmx'))
        if len(input_files) < 1:
            self.fail('required pmd/pmx sample file(s)!')

        check_types = set()
        check_types.add('MESH')
        check_types.add('ARMATURE')
        check_types.add('PHYSICS')
        check_types.add('MORPHS')
        check_types.add('DISPLAY')

        import_types = self.__get_import_types(check_types)

        print('\n    Check: %s | Import: %s'%(str(check_types), str(import_types)))

        for test_num, filepath in enumerate(input_files):
            print('\n     - %2d/%d | filepath: %s'%(test_num+1, len(input_files), filepath))
            try:
                self.__enable_mmd_tools()
                file_loader = pmx.load
                if filepath.lower().endswith('.pmd'):
                    file_loader = import_pmd_to_pmx
                source_model = file_loader(filepath)
                PMXImporter().execute(
                    pmx=source_model,
                    types=import_types,
                    scale=1,
                    clean_model=False,
                    )
                #bpy.context.scene.update()
                bpy.context.scene.frame_set(bpy.context.scene.frame_current)
            except Exception:
                self.fail('Exception happened during import %s'%filepath)
            else:
                try:
                    output_pmx = os.path.join(TESTS_DIR, 'output', '%d.pmx'%test_num)
                    bpy.ops.mmd_tools.export_pmx(
                        filepath=output_pmx,
                        scale=1,
                        copy_textures=False,
                        sort_materials=False,
                        log_level='ERROR',
                        )
                except Exception:
                    self.fail('Exception happened during export %s'%output_pmx)
                else:
                    self.assertTrue(os.path.isfile(output_pmx), 'File was not created')  # Is this a race condition?

                    try:
                        result_model = pmx.load(output_pmx)
                    except:
                        self.fail('Failed to load output file %s'%output_pmx)

                    self.__check_pmx_header_info(source_model, result_model, import_types)

                    if 'MESH' in check_types:
                        self.__check_pmx_mesh(source_model, result_model)

                    if 'ARMATURE' in check_types:
                        self.__check_pmx_bones(source_model, result_model)

                    if 'PHYSICS' in check_types:
                        self.__check_pmx_physics(source_model, result_model)

                    if 'MORPHS' in check_types:
                        self.__check_pmx_morphs(source_model, result_model)

                    if 'DISPLAY' in check_types:
                        self.__check_pmx_display_data(source_model, result_model, 'MORPHS' in check_types)

if __name__ == '__main__':
    import sys
    sys.argv = [__file__] + (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    unittest.main()
