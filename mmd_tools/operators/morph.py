# -*- coding: utf-8 -*-
# Copyright 2015 MMD Tools authors
# This file is part of MMD Tools.

from typing import Optional, cast

import bpy
from mathutils import Quaternion, Vector

from ..core.model import FnModel
from .. import bpyutils, utils
from ..core.exceptions import MaterialNotFoundError
from ..core.material import FnMaterial
from ..core.morph import FnMorph
from ..utils import ItemMoveOp, ItemOp


# Util functions
def divide_vector_components(vec1, vec2):
    if len(vec1) != len(vec2):
        raise ValueError("Vectors should have the same number of components")
    result = []
    for v1, v2 in zip(vec1, vec2):
        if v2 == 0:
            if v1 == 0:
                v2 = 1  # If we have a 0/0 case we change the divisor to 1
            else:
                raise ZeroDivisionError("Invalid Input: a non-zero value can't be divided by zero")
        result.append(v1 / v2)
    return result


def multiply_vector_components(vec1, vec2):
    if len(vec1) != len(vec2):
        raise ValueError("Vectors should have the same number of components")
    result = []
    for v1, v2 in zip(vec1, vec2):
        result.append(v1 * v2)
    return result


def special_division(n1, n2):
    """This function returns 0 in case of 0/0. If non-zero divided by zero case is found, an Exception is raised"""
    if n2 == 0:
        if n1 == 0:
            n2 = 1
        else:
            raise ZeroDivisionError("Invalid Input: a non-zero value can't be divided by zero")
    return n1 / n2


class AddMorph(bpy.types.Operator):
    bl_idname = "mmd_tools.morph_add"
    bl_label = "Add Morph"
    bl_description = "Add a morph item to active morph list"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        mmd_root = root.mmd_root
        morph_type = mmd_root.active_morph_type
        morphs = getattr(mmd_root, morph_type)
        morph, mmd_root.active_morph = ItemOp.add_after(morphs, mmd_root.active_morph)
        morph.name = "New Morph"
        if morph_type.startswith("uv"):
            morph.data_type = "VERTEX_GROUP"
        return {"FINISHED"}


class RemoveMorph(bpy.types.Operator):
    bl_idname = "mmd_tools.morph_remove"
    bl_label = "Remove Morph"
    bl_description = "Remove morph item(s) from the list"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    all: bpy.props.BoolProperty(
        name="All",
        description="Delete all morph items",
        default=False,
        options={"SKIP_SAVE"},
    )

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        mmd_root = root.mmd_root

        morph_type = mmd_root.active_morph_type
        if morph_type.startswith("material"):
            bpy.ops.mmd_tools.clear_temp_materials()
        elif morph_type.startswith("uv"):
            bpy.ops.mmd_tools.clear_uv_morph_view()

        morphs = getattr(mmd_root, morph_type)
        if self.all:
            morphs.clear()
            mmd_root.active_morph = 0
        else:
            morphs.remove(mmd_root.active_morph)
            mmd_root.active_morph = max(0, mmd_root.active_morph - 1)
        return {"FINISHED"}


class MoveMorph(bpy.types.Operator, ItemMoveOp):
    bl_idname = "mmd_tools.morph_move"
    bl_label = "Move Morph"
    bl_description = "Move active morph item up/down in the list"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        mmd_root = root.mmd_root
        mmd_root.active_morph = self.move(
            getattr(mmd_root, mmd_root.active_morph_type),
            mmd_root.active_morph,
            self.type,
        )
        return {"FINISHED"}


class CopyMorph(bpy.types.Operator):
    bl_idname = "mmd_tools.morph_copy"
    bl_label = "Copy Morph"
    bl_description = "Make a copy of active morph in the list"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        assert root is not None
        mmd_root = root.mmd_root

        morph_type = mmd_root.active_morph_type
        morphs = getattr(mmd_root, morph_type)
        morph = ItemOp.get_by_index(morphs, mmd_root.active_morph)
        if morph is None:
            return {"CANCELLED"}

        name_orig, name_tmp = morph.name, "_tmp%s" % str(morph.as_pointer())

        if morph_type.startswith("vertex"):
            for obj in FnModel.iterate_mesh_objects(root):
                FnMorph.copy_shape_key(obj, name_orig, name_tmp)

        elif morph_type.startswith("uv"):
            if morph.data_type == "VERTEX_GROUP":
                for obj in FnModel.iterate_mesh_objects(root):
                    FnMorph.copy_uv_morph_vertex_groups(obj, name_orig, name_tmp)

        morph_new, mmd_root.active_morph = ItemOp.add_after(morphs, mmd_root.active_morph)
        for k, v in morph.items():
            morph_new[k] = v if k != "name" else name_tmp
        morph_new.name = name_orig + "_copy"  # trigger name check
        return {"FINISHED"}


class OverwriteBoneMorphsFromPoseLibrary(bpy.types.Operator):
    bl_idname = "mmd_tools.morph_overwrite_from_active_pose_library"
    bl_label = "Overwrite Bone Morphs from active Pose Library"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        root = FnModel.find_root_object(context.active_object)
        if root is None:
            return False

        return root.mmd_root.active_morph_type == "bone_morphs"

    def execute(self, context):
        root = FnModel.find_root_object(context.active_object)
        FnMorph.overwrite_bone_morphs_from_pose_library(FnModel.find_armature_object(root))

        return {"FINISHED"}


class AddMorphOffset(bpy.types.Operator):
    bl_idname = "mmd_tools.morph_offset_add"
    bl_label = "Add Morph Offset"
    bl_description = "Add a morph offset item to the list"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        mmd_root = root.mmd_root
        morph_type = mmd_root.active_morph_type
        morph = ItemOp.get_by_index(getattr(mmd_root, morph_type), mmd_root.active_morph)
        if morph is None:
            return {"CANCELLED"}

        item, morph.active_data = ItemOp.add_after(morph.data, morph.active_data)

        if morph_type.startswith("material"):
            if obj.type == "MESH" and obj.mmd_type == "NONE":
                item.related_mesh = obj.data.name
                active_material = obj.active_material
                if active_material and "_temp" not in active_material.name:
                    item.material = active_material.name

        elif morph_type.startswith("bone"):
            pose_bone = context.active_pose_bone
            if pose_bone:
                item.bone = pose_bone.name
                item.location = pose_bone.location
                item.rotation = pose_bone.rotation_quaternion

        return {"FINISHED"}


class RemoveMorphOffset(bpy.types.Operator):
    bl_idname = "mmd_tools.morph_offset_remove"
    bl_label = "Remove Morph Offset"
    bl_description = "Remove morph offset item(s) from the list"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    all: bpy.props.BoolProperty(
        name="All",
        description="Delete all morph offset items",
        default=False,
        options={"SKIP_SAVE"},
    )

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        assert root is not None
        mmd_root = root.mmd_root
        morph_type = mmd_root.active_morph_type
        morph = ItemOp.get_by_index(getattr(mmd_root, morph_type), mmd_root.active_morph)
        if morph is None:
            return {"CANCELLED"}

        if morph_type.startswith("material"):
            bpy.ops.mmd_tools.clear_temp_materials()

        if self.all:
            if morph_type.startswith("vertex"):
                for obj in FnModel.iterate_mesh_objects(root):
                    FnMorph.remove_shape_key(obj, morph.name)
                return {"FINISHED"}
            elif morph_type.startswith("uv"):
                if morph.data_type == "VERTEX_GROUP":
                    for obj in FnModel.iterate_mesh_objects(root):
                        FnMorph.store_uv_morph_data(obj, morph)
                    return {"FINISHED"}
            morph.data.clear()
            morph.active_data = 0
        else:
            morph.data.remove(morph.active_data)
            morph.active_data = max(0, morph.active_data - 1)
        return {"FINISHED"}


class InitMaterialOffset(bpy.types.Operator):
    bl_idname = "mmd_tools.material_morph_offset_init"
    bl_label = "Init Material Offset"
    bl_description = "Set all offset values to target value"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    target_value: bpy.props.FloatProperty(
        name="Target Value",
        description="Target value",
        default=0,
    )

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        mmd_root = root.mmd_root
        morph = mmd_root.material_morphs[mmd_root.active_morph]
        mat_data = morph.data[morph.active_data]

        val = self.target_value
        mat_data.diffuse_color = mat_data.edge_color = (val,) * 4
        mat_data.specular_color = mat_data.ambient_color = (val,) * 3
        mat_data.shininess = mat_data.edge_weight = val
        mat_data.texture_factor = mat_data.toon_texture_factor = mat_data.sphere_texture_factor = (val,) * 4
        return {"FINISHED"}


class ApplyMaterialOffset(bpy.types.Operator):
    bl_idname = "mmd_tools.apply_material_morph_offset"
    bl_label = "Apply Material Offset"
    bl_description = "Calculates the offsets and apply them, then the temporary material is removed"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        mmd_root = root.mmd_root
        morph = mmd_root.material_morphs[mmd_root.active_morph]
        mat_data = morph.data[morph.active_data]

        meshObj = FnModel.find_mesh_object_by_name(mat_data.related_mesh)
        if meshObj is None:
            self.report({"ERROR"}, "The model mesh can't be found")
            return {"CANCELLED"}
        try:
            work_mat_name = mat_data.material + "_temp"
            work_mat, base_mat = FnMaterial.swap_materials(meshObj, work_mat_name, mat_data.material)
        except MaterialNotFoundError:
            self.report({"ERROR"}, "Material not found")
            return {"CANCELLED"}

        base_mmd_mat = base_mat.mmd_material
        work_mmd_mat = work_mat.mmd_material

        if mat_data.offset_type == "MULT":
            try:
                diffuse_offset = divide_vector_components(work_mmd_mat.diffuse_color, base_mmd_mat.diffuse_color) + [special_division(work_mmd_mat.alpha, base_mmd_mat.alpha)]
                specular_offset = divide_vector_components(work_mmd_mat.specular_color, base_mmd_mat.specular_color)
                edge_offset = divide_vector_components(work_mmd_mat.edge_color, base_mmd_mat.edge_color)
                mat_data.diffuse_color = diffuse_offset
                mat_data.specular_color = specular_offset
                mat_data.shininess = special_division(work_mmd_mat.shininess, base_mmd_mat.shininess)
                mat_data.ambient_color = divide_vector_components(work_mmd_mat.ambient_color, base_mmd_mat.ambient_color)
                mat_data.edge_color = edge_offset
                mat_data.edge_weight = special_division(work_mmd_mat.edge_weight, base_mmd_mat.edge_weight)

            except ZeroDivisionError:
                mat_data.offset_type = "ADD"  # If there is any 0 division we automatically switch it to type ADD
            except ValueError:
                self.report({"ERROR"}, "An unexpected error happened")
                # We should stop on our tracks and re-raise the exception
                raise

        if mat_data.offset_type == "ADD":
            diffuse_offset = list(work_mmd_mat.diffuse_color - base_mmd_mat.diffuse_color) + [work_mmd_mat.alpha - base_mmd_mat.alpha]
            specular_offset = list(work_mmd_mat.specular_color - base_mmd_mat.specular_color)
            edge_offset = Vector(work_mmd_mat.edge_color) - Vector(base_mmd_mat.edge_color)
            mat_data.diffuse_color = diffuse_offset
            mat_data.specular_color = specular_offset
            mat_data.shininess = work_mmd_mat.shininess - base_mmd_mat.shininess
            mat_data.ambient_color = work_mmd_mat.ambient_color - base_mmd_mat.ambient_color
            mat_data.edge_color = list(edge_offset)
            mat_data.edge_weight = work_mmd_mat.edge_weight - base_mmd_mat.edge_weight

        FnMaterial.clean_materials(meshObj, can_remove=lambda m: m == work_mat)
        return {"FINISHED"}


class CreateWorkMaterial(bpy.types.Operator):
    bl_idname = "mmd_tools.create_work_material"
    bl_label = "Create Work Material"
    bl_description = "Creates a temporary material to edit this offset"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        mmd_root = root.mmd_root
        morph = mmd_root.material_morphs[mmd_root.active_morph]
        mat_data = morph.data[morph.active_data]

        meshObj = FnModel.find_mesh_object_by_name(mat_data.related_mesh)
        if meshObj is None:
            self.report({"ERROR"}, "The model mesh can't be found")
            return {"CANCELLED"}

        base_mat = meshObj.data.materials.get(mat_data.material, None)
        if base_mat is None:
            self.report({"ERROR"}, 'Material "%s" not found' % mat_data.material)
            return {"CANCELLED"}

        work_mat_name = base_mat.name + "_temp"
        if work_mat_name in bpy.data.materials:
            self.report({"ERROR"}, 'Temporary material "%s" is in use' % work_mat_name)
            return {"CANCELLED"}

        work_mat = base_mat.copy()
        work_mat.name = work_mat_name
        meshObj.data.materials.append(work_mat)
        FnMaterial.swap_materials(meshObj, base_mat.name, work_mat.name)
        base_mmd_mat = base_mat.mmd_material
        work_mmd_mat = work_mat.mmd_material
        work_mmd_mat.material_id = -1

        # Apply the offsets
        if mat_data.offset_type == "MULT":
            diffuse_offset = multiply_vector_components(base_mmd_mat.diffuse_color, mat_data.diffuse_color[0:3])
            specular_offset = multiply_vector_components(base_mmd_mat.specular_color, mat_data.specular_color)
            edge_offset = multiply_vector_components(base_mmd_mat.edge_color, mat_data.edge_color)
            ambient_offset = multiply_vector_components(base_mmd_mat.ambient_color, mat_data.ambient_color)
            work_mmd_mat.diffuse_color = diffuse_offset
            work_mmd_mat.alpha *= mat_data.diffuse_color[3]
            work_mmd_mat.specular_color = specular_offset
            work_mmd_mat.shininess *= mat_data.shininess
            work_mmd_mat.ambient_color = ambient_offset
            work_mmd_mat.edge_color = edge_offset
            work_mmd_mat.edge_weight *= mat_data.edge_weight
        elif mat_data.offset_type == "ADD":
            diffuse_offset = Vector(base_mmd_mat.diffuse_color) + Vector(mat_data.diffuse_color[0:3])
            specular_offset = Vector(base_mmd_mat.specular_color) + Vector(mat_data.specular_color)
            edge_offset = Vector(base_mmd_mat.edge_color) + Vector(mat_data.edge_color)
            ambient_offset = Vector(base_mmd_mat.ambient_color) + Vector(mat_data.ambient_color)
            work_mmd_mat.diffuse_color = list(diffuse_offset)
            work_mmd_mat.alpha += mat_data.diffuse_color[3]
            work_mmd_mat.specular_color = list(specular_offset)
            work_mmd_mat.shininess += mat_data.shininess
            work_mmd_mat.ambient_color = list(ambient_offset)
            work_mmd_mat.edge_color = list(edge_offset)
            work_mmd_mat.edge_weight += mat_data.edge_weight

        return {"FINISHED"}


class ClearTempMaterials(bpy.types.Operator):
    bl_idname = "mmd_tools.clear_temp_materials"
    bl_label = "Clear Temp Materials"
    bl_description = "Clears all the temporary materials"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        assert root is not None
        for meshObj in FnModel.iterate_mesh_objects(root):

            def __pre_remove(m):
                if m and "_temp" in m.name:
                    base_mat_name = m.name.split("_temp")[0]
                    try:
                        FnMaterial.swap_materials(meshObj, m.name, base_mat_name)
                        return True
                    except MaterialNotFoundError:
                        self.report({"WARNING"}, "Base material for %s was not found" % m.name)
                return False

            FnMaterial.clean_materials(meshObj, can_remove=__pre_remove)
        return {"FINISHED"}


class ViewBoneMorph(bpy.types.Operator):
    bl_idname = "mmd_tools.view_bone_morph"
    bl_label = "View Bone Morph"
    bl_description = "View the result of active bone morph"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        assert root is not None
        mmd_root = root.mmd_root
        armature = FnModel.find_armature_object(root)
        utils.selectSingleBone(context, armature, None, True)
        morph = mmd_root.bone_morphs[mmd_root.active_morph]
        for morph_data in morph.data:
            p_bone: Optional[bpy.types.PoseBone] = armature.pose.bones.get(morph_data.bone, None)
            if p_bone:
                p_bone.bone.select = True
                mtx = (p_bone.matrix_basis.to_3x3() @ Quaternion(*morph_data.rotation.to_axis_angle()).to_matrix()).to_4x4()
                mtx.translation = p_bone.location + morph_data.location
                p_bone.matrix_basis = mtx
        return {"FINISHED"}


class ClearBoneMorphView(bpy.types.Operator):
    bl_idname = "mmd_tools.clear_bone_morph_view"
    bl_label = "Clear Bone Morph View"
    bl_description = "Reset transforms of all bones to their default values"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        assert root is not None
        armature = FnModel.find_armature_object(root)
        for p_bone in armature.pose.bones:
            p_bone.matrix_basis.identity()
        return {"FINISHED"}


class ApplyBoneMorph(bpy.types.Operator):
    bl_idname = "mmd_tools.apply_bone_morph"
    bl_label = "Apply Bone Morph"
    bl_description = "Apply current pose to active bone morph"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        assert root is not None
        armature = FnModel.find_armature_object(root)
        mmd_root = root.mmd_root
        morph = mmd_root.bone_morphs[mmd_root.active_morph]
        morph.data.clear()
        morph.active_data = 0
        for p_bone in armature.pose.bones:
            if p_bone.location.length > 0 or p_bone.matrix_basis.decompose()[1].angle > 0:
                item = morph.data.add()
                item.bone = p_bone.name
                item.location = p_bone.location
                item.rotation = p_bone.rotation_quaternion if p_bone.rotation_mode == "QUATERNION" else p_bone.matrix_basis.to_quaternion()
                p_bone.bone.select = True
            else:
                p_bone.bone.select = False
        return {"FINISHED"}


class SelectRelatedBone(bpy.types.Operator):
    bl_idname = "mmd_tools.select_bone_morph_offset_bone"
    bl_label = "Select Related Bone"
    bl_description = "Select the bone assigned to this offset in the armature"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        assert root is not None
        mmd_root = root.mmd_root
        armature = FnModel.find_armature_object(root)
        morph = mmd_root.bone_morphs[mmd_root.active_morph]
        morph_data = morph.data[morph.active_data]
        utils.selectSingleBone(context, armature, morph_data.bone)
        return {"FINISHED"}


class EditBoneOffset(bpy.types.Operator):
    bl_idname = "mmd_tools.edit_bone_morph_offset"
    bl_label = "Edit Related Bone"
    bl_description = "Applies the location and rotation of this offset to the bone"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        assert root is not None
        mmd_root = root.mmd_root
        armature = FnModel.find_armature_object(root)
        morph = mmd_root.bone_morphs[mmd_root.active_morph]
        morph_data = morph.data[morph.active_data]
        p_bone = armature.pose.bones[morph_data.bone]
        mtx = Quaternion(*morph_data.rotation.to_axis_angle()).to_matrix().to_4x4()
        mtx.translation = morph_data.location
        p_bone.matrix_basis = mtx
        utils.selectSingleBone(context, armature, p_bone.name)
        return {"FINISHED"}


class ApplyBoneOffset(bpy.types.Operator):
    bl_idname = "mmd_tools.apply_bone_morph_offset"
    bl_label = "Apply Bone Morph Offset"
    bl_description = "Stores the current bone location and rotation into this offset"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        assert root is not None
        mmd_root = root.mmd_root
        armature = FnModel.find_armature_object(root)
        assert armature is not None
        morph = mmd_root.bone_morphs[mmd_root.active_morph]
        morph_data = morph.data[morph.active_data]
        p_bone = armature.pose.bones[morph_data.bone]
        morph_data.location = p_bone.location
        morph_data.rotation = p_bone.rotation_quaternion if p_bone.rotation_mode == "QUATERNION" else p_bone.matrix_basis.to_quaternion()
        return {"FINISHED"}


class ViewUVMorph(bpy.types.Operator):
    bl_idname = "mmd_tools.view_uv_morph"
    bl_label = "View UV Morph"
    bl_description = "View the result of active UV morph on current mesh object"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        assert root is not None
        mmd_root = root.mmd_root

        meshes = tuple(FnModel.iterate_mesh_objects(root))
        if len(meshes) == 1:
            obj = meshes[0]
        elif obj not in meshes:
            self.report({"ERROR"}, "Please select a mesh object")
            return {"CANCELLED"}
        meshObj = obj

        bpy.ops.mmd_tools.clear_uv_morph_view()

        selected = meshObj.select_get()
        with bpyutils.select_object(meshObj):
            mesh = cast(bpy.types.Mesh, meshObj.data)
            morph = mmd_root.uv_morphs[mmd_root.active_morph]
            uv_textures = mesh.uv_layers

            base_uv_layers = [l for l in mesh.uv_layers if not l.name.startswith("_")]
            if morph.uv_index >= len(base_uv_layers):
                self.report({"ERROR"}, "Invalid uv index: %d" % morph.uv_index)
                return {"CANCELLED"}

            uv_layer_name = base_uv_layers[morph.uv_index].name
            if morph.uv_index == 0 or uv_textures.active.name not in {uv_layer_name, "_" + uv_layer_name}:
                uv_textures.active = uv_textures[uv_layer_name]

            uv_layer_name = uv_textures.active.name
            uv_tex = uv_textures.new(name="__uv.%s" % uv_layer_name)
            if uv_tex is None:
                self.report({"ERROR"}, "Failed to create a temporary uv layer")
                return {"CANCELLED"}

            offsets = FnMorph.get_uv_morph_offset_map(meshObj, morph).items()
            offsets = {k: getattr(Vector(v), "zw" if uv_layer_name.startswith("_") else "xy") for k, v in offsets}
            if len(offsets) > 0:
                base_uv_data = mesh.uv_layers.active.data
                temp_uv_data = mesh.uv_layers[uv_tex.name].data
                for i, l in enumerate(mesh.loops):
                    select = temp_uv_data[i].select = l.vertex_index in offsets
                    if select:
                        temp_uv_data[i].uv = base_uv_data[i].uv + offsets[l.vertex_index]

            uv_textures.active = uv_tex
            uv_tex.active_render = True
        meshObj.hide_set(False)
        meshObj.select_set(selected)
        return {"FINISHED"}


class ClearUVMorphView(bpy.types.Operator):
    bl_idname = "mmd_tools.clear_uv_morph_view"
    bl_label = "Clear UV Morph View"
    bl_description = "Clear all temporary data of UV morphs"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        assert root is not None
        for m in FnModel.iterate_mesh_objects(root):
            mesh = m.data
            uv_textures = getattr(mesh, "uv_textures", mesh.uv_layers)
            for t in uv_textures:
                if t.name.startswith("__uv."):
                    uv_textures.remove(t)
            if len(uv_textures) > 0:
                uv_textures[0].active_render = True
                uv_textures.active_index = 0

            animation_data = mesh.animation_data
            if animation_data:
                nla_tracks = animation_data.nla_tracks
                for t in nla_tracks:
                    if t.name.startswith("__uv."):
                        nla_tracks.remove(t)
                if animation_data.action and animation_data.action.name.startswith("__uv."):
                    animation_data.action = None
                if animation_data.action is None and len(nla_tracks) == 0:
                    mesh.animation_data_clear()

        for act in bpy.data.actions:
            if act.name.startswith("__uv.") and act.users < 1:
                bpy.data.actions.remove(act)
        return {"FINISHED"}


class EditUVMorph(bpy.types.Operator):
    bl_idname = "mmd_tools.edit_uv_morph"
    bl_label = "Edit UV Morph"
    bl_description = "Edit UV morph on a temporary UV layer (use UV Editor to edit the result)"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj.type != "MESH":
            return False
        active_uv_layer = obj.data.uv_layers.active
        return active_uv_layer and active_uv_layer.name.startswith("__uv.")

    def execute(self, context):
        obj = context.active_object
        meshObj = obj

        selected = meshObj.select_get()
        with bpyutils.select_object(meshObj):
            mesh = cast(bpy.types.Mesh, meshObj.data)
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_mode(type="VERT", action="ENABLE")
            bpy.ops.mesh.reveal()  # unhide all vertices
            bpy.ops.mesh.select_all(action="DESELECT")
            bpy.ops.object.mode_set(mode="OBJECT")

            vertices = mesh.vertices
            for l, d in zip(mesh.loops, mesh.uv_layers.active.data):
                if d.select:
                    vertices[l.vertex_index].select = True

            polygons = mesh.polygons
            polygons.active = getattr(next((p for p in polygons if all(vertices[i].select for i in p.vertices)), None), "index", polygons.active)

            bpy.ops.object.mode_set(mode="EDIT")
        meshObj.select_set(selected)
        return {"FINISHED"}


class ApplyUVMorph(bpy.types.Operator):
    bl_idname = "mmd_tools.apply_uv_morph"
    bl_label = "Apply UV Morph"
    bl_description = "Calculate the UV offsets of selected vertices and apply to active UV morph"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj.type != "MESH":
            return False
        active_uv_layer = obj.data.uv_layers.active
        return active_uv_layer and active_uv_layer.name.startswith("__uv.")

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        mmd_root = root.mmd_root
        meshObj = obj

        selected = meshObj.select_get()
        with bpyutils.select_object(meshObj):
            mesh = cast(bpy.types.Mesh, meshObj.data)
            morph = mmd_root.uv_morphs[mmd_root.active_morph]

            base_uv_name = mesh.uv_layers.active.name[5:]
            if base_uv_name not in mesh.uv_layers:
                self.report({"ERROR"}, ' * UV map "%s" not found' % base_uv_name)
                return {"CANCELLED"}

            base_uv_data = mesh.uv_layers[base_uv_name].data
            temp_uv_data = mesh.uv_layers.active.data
            axis_type = "ZW" if base_uv_name.startswith("_") else "XY"

            from collections import namedtuple

            __OffsetData = namedtuple("OffsetData", "index, offset")
            offsets = {}
            vertices = mesh.vertices
            for l, i0, i1 in zip(mesh.loops, base_uv_data, temp_uv_data):
                if vertices[l.vertex_index].select and l.vertex_index not in offsets:
                    dx, dy = i1.uv - i0.uv
                    if abs(dx) > 0.0001 or abs(dy) > 0.0001:
                        offsets[l.vertex_index] = __OffsetData(l.vertex_index, (dx, dy, dx, dy))

            FnMorph.store_uv_morph_data(meshObj, morph, offsets.values(), axis_type)
            morph.data_type = "VERTEX_GROUP"

        meshObj.select_set(selected)
        return {"FINISHED"}


class CleanDuplicatedMaterialMorphs(bpy.types.Operator):
    bl_idname = "mmd_tools.clean_duplicated_material_morphs"
    bl_label = "Clean Duplicated Material Morphs"
    bl_description = "Clean duplicated material morphs"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return FnModel.find_root_object(context.active_object) is not None

    def execute(self, context: bpy.types.Context):
        mmd_root_object = FnModel.find_root_object(context.active_object)
        FnMorph.clean_duplicated_material_morphs(mmd_root_object)

        return {"FINISHED"}
