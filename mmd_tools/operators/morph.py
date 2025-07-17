# Copyright 2015 MMD Tools authors
# This file is part of MMD Tools.

from collections import namedtuple
from typing import Optional, cast

import bpy
from mathutils import Quaternion, Vector

from .. import bpyutils, utils
from ..core.exceptions import MaterialNotFoundError
from ..core.material import FnMaterial
from ..core.model import FnModel
from ..core.morph import FnMorph
from ..utils import ItemMoveOp, ItemOp


# Util functions
def divide_vector_components(vec1, vec2):
    if len(vec1) != len(vec2):
        raise ValueError("Vectors should have the same number of components")
    result = []
    for v1, v2 in zip(vec1, vec2, strict=False):
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
    for v1, v2 in zip(vec1, vec2, strict=False):
        result.append(v1 * v2)
    return result


def special_division(n1, n2):
    """Return 0 in case of 0/0. If non-zero divided by zero case is found, an Exception is raised"""
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
    bl_description = "Move active morph item up/down in the list. This will not affect the morph order in exported PMX files (use Display Panel order instead)."
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

        name_orig, name_tmp = morph.name, f"_tmp{str(morph.as_pointer())}"

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


class OverwriteBoneMorphsFromActionPose(bpy.types.Operator):
    bl_idname = "mmd_tools.morph_overwrite_from_active_action_pose"
    bl_label = "Overwrite Bone Morphs from active Action Pose"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        root = FnModel.find_root_object(context.active_object)
        return root is not None and root.mmd_root.active_morph_type == "bone_morphs"

    def execute(self, context):
        root = FnModel.find_root_object(context.active_object)
        FnMorph.overwrite_bone_morphs_from_action_pose(FnModel.find_armature_object(root))

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
            if morph_type.startswith("uv"):
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

        if not mat_data.related_mesh:
            self.report({"ERROR"}, "You need to choose a Related Mesh first")
            return {"CANCELLED"}
        meshObj = FnModel.find_mesh_object_by_name(morph.id_data, mat_data.related_mesh)
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

        if not mat_data.related_mesh:
            self.report({"ERROR"}, "You need to choose a Related Mesh first")
            return {"CANCELLED"}
        meshObj = FnModel.find_mesh_object_by_name(morph.id_data, mat_data.related_mesh)
        if meshObj is None:
            self.report({"ERROR"}, "The model mesh can't be found")
            return {"CANCELLED"}

        base_mat = meshObj.data.materials.get(mat_data.material, None)
        if base_mat is None:
            self.report({"ERROR"}, f'Material "{mat_data.material}" not found')
            return {"CANCELLED"}

        work_mat_name = base_mat.name + "_temp"
        if work_mat_name in bpy.data.materials:
            self.report({"ERROR"}, f'Temporary material "{work_mat_name}" is in use')
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

            def __pre_remove(m, meshObj=meshObj):
                if m and "_temp" in m.name:
                    base_mat_name = m.name.split("_temp")[0]
                    try:
                        FnMaterial.swap_materials(meshObj, m.name, base_mat_name)
                        return True
                    except MaterialNotFoundError:
                        self.report({"WARNING"}, f"Base material for {m.name} was not found")
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
            mesh = cast("bpy.types.Mesh", meshObj.data)
            morph = mmd_root.uv_morphs[mmd_root.active_morph]
            uv_textures = mesh.uv_layers

            base_uv_layers = [layer for layer in mesh.uv_layers if not layer.name.startswith("_")]
            if morph.uv_index >= len(base_uv_layers):
                self.report({"ERROR"}, "Invalid uv index: %d" % morph.uv_index)
                return {"CANCELLED"}

            uv_layer_name = base_uv_layers[morph.uv_index].name
            if morph.uv_index == 0 or uv_textures.active.name not in {uv_layer_name, "_" + uv_layer_name}:
                uv_textures.active = uv_textures[uv_layer_name]

            uv_layer_name = uv_textures.active.name
            uv_tex = uv_textures.new(name=f"__uv.{uv_layer_name}")
            if uv_tex is None:
                self.report({"ERROR"}, "Failed to create a temporary uv layer")
                return {"CANCELLED"}

            offsets = FnMorph.get_uv_morph_offset_map(meshObj, morph).items()
            offsets = {k: getattr(Vector(v), "zw" if uv_layer_name.startswith("_") else "xy") for k, v in offsets}
            if len(offsets) > 0:
                base_uv_data = mesh.uv_layers.active.data
                temp_uv_data = mesh.uv_layers[uv_tex.name].data
                for i, loop in enumerate(mesh.loops):
                    select = temp_uv_data[i].select = loop.vertex_index in offsets
                    if select:
                        temp_uv_data[i].uv = base_uv_data[i].uv + offsets[loop.vertex_index]

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
            for t in reversed(uv_textures):
                if t.name.startswith("__uv."):
                    uv_textures.remove(t)
            if len(uv_textures) > 0:
                uv_textures[0].active_render = True
                uv_textures.active_index = 0

            animation_data = mesh.animation_data
            if animation_data:
                nla_tracks = animation_data.nla_tracks
                for t in reversed(nla_tracks):
                    if t.name.startswith("__uv."):
                        nla_tracks.remove(t)
                if animation_data.action and animation_data.action.name.startswith("__uv."):
                    animation_data.action = None
                if animation_data.action is None and len(nla_tracks) == 0:
                    mesh.animation_data_clear()

        for act in reversed(bpy.data.actions):
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
        if obj is None or obj.type != "MESH":
            return False
        active_uv_layer = obj.data.uv_layers.active
        return active_uv_layer is not None and active_uv_layer.name.startswith("__uv.")

    def execute(self, context):
        obj = context.active_object
        meshObj = obj

        selected = meshObj.select_get()
        with bpyutils.select_object(meshObj):
            mesh = cast("bpy.types.Mesh", meshObj.data)
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_mode(type="VERT", action="ENABLE")
            bpy.ops.mesh.reveal()  # unhide all vertices
            bpy.ops.mesh.select_all(action="DESELECT")
            bpy.ops.object.mode_set(mode="OBJECT")

            vertices = mesh.vertices
            for loop, d in zip(mesh.loops, mesh.uv_layers.active.data, strict=False):
                if d.select:
                    vertices[loop.vertex_index].select = True

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
        if obj is None or obj.type != "MESH":
            return False
        active_uv_layer = obj.data.uv_layers.active
        return active_uv_layer is not None and active_uv_layer.name.startswith("__uv.")

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        mmd_root = root.mmd_root
        meshObj = obj

        selected = meshObj.select_get()
        with bpyutils.select_object(meshObj):
            mesh = cast("bpy.types.Mesh", meshObj.data)
            morph = mmd_root.uv_morphs[mmd_root.active_morph]

            base_uv_name = mesh.uv_layers.active.name[5:]
            if base_uv_name not in mesh.uv_layers:
                self.report({"ERROR"}, f' * UV map "{base_uv_name}" not found')
                return {"CANCELLED"}

            base_uv_data = mesh.uv_layers[base_uv_name].data
            temp_uv_data = mesh.uv_layers.active.data
            axis_type = "ZW" if base_uv_name.startswith("_") else "XY"

            __OffsetData = namedtuple("OffsetData", "index, offset")
            offsets = {}
            vertices = mesh.vertices
            for loop, i0, i1 in zip(mesh.loops, base_uv_data, temp_uv_data, strict=False):
                if vertices[loop.vertex_index].select and loop.vertex_index not in offsets:
                    dx, dy = i1.uv - i0.uv
                    if abs(dx) > 0.0001 or abs(dy) > 0.0001:
                        offsets[loop.vertex_index] = __OffsetData(loop.vertex_index, (dx, dy, dx, dy))

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
        root = FnModel.find_root_object(context.active_object)
        return root is not None

    def execute(self, context: bpy.types.Context):
        mmd_root_object = FnModel.find_root_object(context.active_object)
        FnMorph.clean_duplicated_material_morphs(mmd_root_object)

        return {"FINISHED"}


class ConvertBoneMorphToVertexMorph(bpy.types.Operator):
    bl_idname = "mmd_tools.convert_bone_morph_to_vertex_morph"
    bl_label = "Convert To Vertex Morph"
    bl_description = "Convert a bone morph into a single vertex morph by applying the bone transformations.\nIf a corresponding vertex morph already exists, it will be updated."
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        root = FnModel.find_root_object(context.active_object)
        if root is None:
            return False
        mmd_root = root.mmd_root
        if mmd_root.active_morph_type != "bone_morphs":
            return False
        morph = ItemOp.get_by_index(mmd_root.bone_morphs, mmd_root.active_morph)
        return morph is not None and len(morph.data) > 0

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        mmd_root = root.mmd_root

        # Get the active bone morph
        bone_morph = ItemOp.get_by_index(mmd_root.bone_morphs, mmd_root.active_morph)
        if bone_morph is None:
            self.report({"ERROR"}, "No active bone morph")
            return {"CANCELLED"}

        original_name = bone_morph.name
        target_name = original_name

        # Add 'B' suffix if necessary
        if not original_name.endswith("B"):
            bone_morph.name = original_name + "B"
            target_name = original_name
        else:
            # If already has B suffix, use name without B
            target_name = original_name[:-1]

        try:
            # Step 1: import
            from ..core.model import Model

            rig = Model(root)

            # Ensure morph slider is bound
            bpy.ops.mmd_tools.morph_slider_setup(type="BIND")

            # Re-obtain placeholder object
            placeholder_obj = rig.morph_slider.placeholder()
            if placeholder_obj is None or placeholder_obj.data.shape_keys is None:
                self.report({"ERROR"}, "Failed to create morph slider system")
                return {"CANCELLED"}

            shape_keys = placeholder_obj.data.shape_keys
            key_blocks = shape_keys.key_blocks

            # Step 2: Check if target bone morph exists
            current_morph_name = bone_morph.name
            if current_morph_name not in key_blocks:
                self.report({"ERROR"}, f"Bone morph '{current_morph_name}' not found in morph sliders")
                return {"CANCELLED"}

            # Step 3: Save all current morph values
            original_values = {}
            for key_block in key_blocks:
                if key_block.name != "--- morph sliders ---":
                    original_values[key_block.name] = key_block.value

            # Step 4: Set all morphs to 0
            for key_block in key_blocks:
                if key_block.name != "--- morph sliders ---":
                    key_block.value = 0

            # Step 5: Set target bone morph to 1.0
            key_blocks[current_morph_name].value = 1.0

            # Step 6: Use Armature Modifier's "Apply as Shape Key" functionality
            created_shape_keys = []
            for mesh_obj in FnModel.iterate_mesh_objects(root):
                # Switch to this mesh object
                context.view_layer.objects.active = mesh_obj

                # Ensure mesh object has shape keys
                if mesh_obj.data.shape_keys is None:
                    mesh_obj.shape_key_add(name="Basis", from_mix=False)

                # Delete existing shape key with same name
                if target_name in mesh_obj.data.shape_keys.key_blocks:
                    idx = mesh_obj.data.shape_keys.key_blocks.find(target_name)
                    if idx >= 0:
                        mesh_obj.active_shape_key_index = idx
                        bpy.ops.object.shape_key_remove()

                # Find armature modifier
                armature_modifier = None
                for modifier in mesh_obj.modifiers:
                    if modifier.type == "ARMATURE":
                        armature_modifier = modifier
                        break

                if armature_modifier is None:
                    self.report({"WARNING"}, f"No armature modifier found on mesh '{mesh_obj.name}'")
                    continue

                # Use Apply as Shape Key functionality, keeping the modifier
                bpy.ops.object.modifier_apply_as_shapekey(modifier=armature_modifier.name, keep_modifier=True)

                # Rename the newly created shape key to target name
                shape_key_blocks = mesh_obj.data.shape_keys.key_blocks
                new_shape_key = shape_key_blocks[-1]  # Latest created shape key
                new_shape_key.name = target_name
                new_shape_key.value = 0.0  # Set to 0 to avoid double effect

                created_shape_keys.append((mesh_obj.name, target_name))
                self.report({"INFO"}, f"Created shape key '{target_name}' on mesh '{mesh_obj.name}'")

            # Step 7: Restore all original morph values
            for key_name, original_value in original_values.items():
                if key_name in key_blocks:
                    key_blocks[key_name].value = original_value

            # Step 8: Create or update vertex morph entry
            vertex_morph_exists = False
            for i, morph in enumerate(mmd_root.vertex_morphs):
                if morph.name == target_name:
                    vertex_morph_exists = True
                    mmd_root.active_morph_type = "vertex_morphs"
                    mmd_root.active_morph = i
                    break

            if not vertex_morph_exists:
                mmd_root.active_morph_type = "vertex_morphs"
                morph, mmd_root.active_morph = ItemOp.add_after(mmd_root.vertex_morphs, mmd_root.active_morph)
                morph.name = target_name

            # Step 9: Add to facial expression display frame
            facial_frame = None
            for frame in mmd_root.display_item_frames:
                if frame.name == "表情":
                    facial_frame = frame
                    break

            if facial_frame:
                morph_exists_in_frame = False
                for item in facial_frame.data:
                    if item.type == "MORPH" and item.name == target_name and item.morph_type == "vertex_morphs":
                        morph_exists_in_frame = True
                        break

                if not morph_exists_in_frame:
                    new_item = facial_frame.data.add()
                    new_item.type = "MORPH"
                    new_item.morph_type = "vertex_morphs"
                    new_item.name = target_name

                    facial_frame.active_item = len(facial_frame.data) - 1

                    for i, frame in enumerate(mmd_root.display_item_frames):
                        if frame.name == "表情":
                            mmd_root.active_display_item_frame = i
                            break

            # UNBIND
            bpy.ops.mmd_tools.morph_slider_setup(type="UNBIND")

            # Success message
            shape_key_info = ", ".join([f"{mesh}:{key}" for mesh, key in created_shape_keys])
            self.report({"INFO"}, f"Successfully converted bone morph '{original_name}' to vertex morph '{target_name}'. Created shape keys: {shape_key_info}")

        except Exception as e:
            self.report({"ERROR"}, f"Error during conversion: {str(e)}")
            return {"CANCELLED"}

        return {"FINISHED"}


class ConvertGroupMorphToVertexMorph(bpy.types.Operator):
    bl_idname = "mmd_tools.convert_group_morph_to_vertex_morph"
    bl_label = "Convert To Vertex Morph"
    bl_description = "Convert a group morph into a single vertex morph by merging only the vertex morphs within the group.\nIf a corresponding vertex morph already exists, it will be updated."
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        root = FnModel.find_root_object(context.active_object)
        if root is None:
            return False
        mmd_root = root.mmd_root
        if mmd_root.active_morph_type != "group_morphs":
            return False
        morph = ItemOp.get_by_index(mmd_root.group_morphs, mmd_root.active_morph)
        return morph is not None and len(morph.data) > 0

    def execute(self, context):
        bpy.ops.mmd_tools.morph_slider_setup(type="UNBIND")

        obj = context.active_object
        root = FnModel.find_root_object(obj)
        mmd_root = root.mmd_root

        # Get the active group morph
        group_morph = ItemOp.get_by_index(mmd_root.group_morphs, mmd_root.active_morph)
        if group_morph is None:
            self.report({"ERROR"}, "No active group morph")
            return {"CANCELLED"}

        # Check if the group morph contains any vertex morphs to convert
        has_vertex_morphs = False
        for offset in group_morph.data:
            if offset.morph_type == "vertex_morphs":
                has_vertex_morphs = True
                break

        if not has_vertex_morphs:
            self.report({"ERROR"}, "The group morph does not contain any vertex morphs to convert")
            return {"CANCELLED"}

        original_name = group_morph.name
        target_name = original_name

        # Add 'G' suffix if necessary
        if not original_name.endswith("G"):
            group_morph.name = original_name + "G"
            target_name = original_name
        else:
            # If already has G suffix, use name without G
            target_name = original_name[:-1]

        # First, reset all shape keys to zero
        for obj in FnModel.iterate_mesh_objects(root):
            if obj.data.shape_keys:
                for kb in obj.data.shape_keys.key_blocks:
                    kb.value = 0

        # Apply only the vertex morphs from the group morph
        for offset in group_morph.data:
            if offset.morph_type == "vertex_morphs":
                # Find the vertex morph by name
                vertex_morph = getattr(root.mmd_root, offset.morph_type).get(offset.name)
                if vertex_morph:
                    # Apply this morph at the specified factor
                    for obj in FnModel.iterate_mesh_objects(root):
                        if obj.data.shape_keys:
                            kb = obj.data.shape_keys.key_blocks.get(offset.name)
                            if kb:
                                kb.value = offset.factor

        # Now add a new shape key from mix for each mesh
        for obj in FnModel.iterate_mesh_objects(root):
            if obj.data.shape_keys:
                # Make this the active object
                context.view_layer.objects.active = obj

                # Remove existing shape key if it exists
                if target_name in obj.data.shape_keys.key_blocks:
                    idx = obj.data.shape_keys.key_blocks.find(target_name)
                    if idx >= 0:
                        obj.active_shape_key_index = idx
                        bpy.ops.object.shape_key_remove()

                # Add shape key from mix
                bpy.ops.object.shape_key_add(from_mix=True)

                # Rename the newly created shape key
                new_key = obj.data.shape_keys.key_blocks[-1]
                new_key.name = target_name

        # Check if a vertex morph with the target name already exists
        vertex_morph_exists = False
        for i, morph in enumerate(mmd_root.vertex_morphs):
            if morph.name == target_name:
                vertex_morph_exists = True
                mmd_root.active_morph_type = "vertex_morphs"
                mmd_root.active_morph = i
                break

        # If not, create a new vertex morph
        if not vertex_morph_exists:
            # Switch to vertex morphs panel
            mmd_root.active_morph_type = "vertex_morphs"

            # Add new vertex morph
            morph, mmd_root.active_morph = ItemOp.add_after(mmd_root.vertex_morphs, mmd_root.active_morph)
            morph.name = target_name

        # Add the new vertex morph to the facial display frame
        facial_frame = None
        for frame in mmd_root.display_item_frames:
            if frame.name == "表情":  # This is the facial display frame
                facial_frame = frame
                break

        if facial_frame:
            # Check if this morph is already in the facial frame
            morph_exists_in_frame = False
            for item in facial_frame.data:
                if item.type == "MORPH" and item.name == target_name and item.morph_type == "vertex_morphs":
                    morph_exists_in_frame = True
                    break

            # If not, add it
            if not morph_exists_in_frame:
                new_item = facial_frame.data.add()
                new_item.type = "MORPH"
                new_item.morph_type = "vertex_morphs"
                new_item.name = target_name

                # Make this the active item in the facial frame
                facial_frame.active_item = len(facial_frame.data) - 1

                # Set the facial frame as active
                for i, frame in enumerate(mmd_root.display_item_frames):
                    if frame.name == "表情":
                        mmd_root.active_display_item_frame = i
                        break

        # Reset all shape keys
        for obj in FnModel.iterate_mesh_objects(root):
            if obj.data.shape_keys:
                for kb in obj.data.shape_keys.key_blocks:
                    kb.value = 0

        self.report({"INFO"}, f"Successfully converted vertex morphs in group to vertex morph '{target_name}' and added to facial display frame")
        return {"FINISHED"}
