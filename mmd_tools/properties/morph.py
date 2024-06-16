# -*- coding: utf-8 -*-
# Copyright 2015 MMD Tools authors
# This file is part of MMD Tools.

import bpy

from .. import utils
from ..core.bone import FnBone
from ..core.material import FnMaterial
from ..core.model import FnModel, MMDModel
from ..core.morph import FnMorph


def _morph_base_get_name(prop: "_MorphBase") -> str:
    return prop.get("name", "")


def _morph_base_set_name(prop: "_MorphBase", value: str):
    mmd_root = prop.id_data.mmd_root
    # morph_type = mmd_root.active_morph_type
    morph_type = "%s_morphs" % prop.bl_rna.identifier[:-5].lower()
    # assert(prop.bl_rna.identifier.endswith('Morph'))
    # logging.debug('_set_name: %s %s %s', prop, value, morph_type)
    prop_name = prop.get("name", None)
    if prop_name == value:
        return

    used_names = {x.name for x in getattr(mmd_root, morph_type) if x != prop}
    value = utils.unique_name(value, used_names)
    if prop_name is not None:
        if morph_type == "vertex_morphs":
            kb_list = {}
            for mesh in FnModel.iterate_mesh_objects(prop.id_data):
                for kb in getattr(mesh.data.shape_keys, "key_blocks", ()):
                    kb_list.setdefault(kb.name, []).append(kb)

            if prop_name in kb_list:
                value = utils.unique_name(value, used_names | kb_list.keys())
                for kb in kb_list[prop_name]:
                    kb.name = value

        elif morph_type == "uv_morphs":
            vg_list = {}
            for mesh in FnModel.iterate_mesh_objects(prop.id_data):
                for vg, n, x in FnMorph.get_uv_morph_vertex_groups(mesh):
                    vg_list.setdefault(n, []).append(vg)

            if prop_name in vg_list:
                value = utils.unique_name(value, used_names | vg_list.keys())
                for vg in vg_list[prop_name]:
                    vg.name = vg.name.replace(prop_name, value)

        if 1:  # morph_type != 'group_morphs':
            for m in mmd_root.group_morphs:
                for d in m.data:
                    if d.name == prop_name and d.morph_type == morph_type:
                        d.name = value

        frame_facial = mmd_root.display_item_frames.get("表情")
        for item in getattr(frame_facial, "data", []):
            if item.name == prop_name and item.morph_type == morph_type:
                item.name = value
                break

        obj = MMDModel(prop.id_data).morph_slider.placeholder()
        if obj and value not in obj.data.shape_keys.key_blocks:
            kb = obj.data.shape_keys.key_blocks.get(prop_name, None)
            if kb:
                kb.name = value

    prop["name"] = value


class _MorphBase:
    name: bpy.props.StringProperty(
        name="Name",
        description="Japanese Name",
        set=_morph_base_set_name,
        get=_morph_base_get_name,
    )
    name_e: bpy.props.StringProperty(
        name="Name(Eng)",
        description="English Name",
        default="",
    )
    category: bpy.props.EnumProperty(
        name="Category",
        description="Select category",
        items=[
            ("SYSTEM", "Hidden", "", 0),
            ("EYEBROW", "Eye Brow", "", 1),
            ("EYE", "Eye", "", 2),
            ("MOUTH", "Mouth", "", 3),
            ("OTHER", "Other", "", 4),
        ],
        default="OTHER",
    )


def _bone_morph_data_get_bone(prop: "BoneMorphData") -> str:
    bone_id = prop.get("bone_id", -1)
    if bone_id < 0:
        return ""
    root_object = prop.id_data
    armature_object = FnModel.find_armature_object(root_object)
    if armature_object is None:
        return ""
    pose_bone = FnBone.find_pose_bone_by_bone_id(armature_object, bone_id)
    if pose_bone is None:
        return ""
    return pose_bone.name


def _bone_morph_data_set_bone(prop: "BoneMorphData", value: str):
    root = prop.id_data
    arm = FnModel.find_armature_object(root)

    # Load the library_override file. This function is triggered when loading, but the arm obj cannot be found.
    # The arm obj is exist, but the relative relationship has not yet been established.
    if arm is None:
        return

    if value not in arm.pose.bones.keys():
        prop["bone_id"] = -1
        return
    pose_bone = arm.pose.bones[value]
    prop["bone_id"] = FnBone.get_or_assign_bone_id(pose_bone)


def _bone_morph_data_update_location_or_rotation(prop: "BoneMorphData", _context):
    if not prop.name.startswith("mmd_bind"):
        return
    arm = FnModel(prop.id_data).morph_slider.dummy_armature
    if arm:
        bone = arm.pose.bones.get(prop.name, None)
        if bone:
            bone.location = prop.location
            bone.rotation_quaternion = prop.rotation.__class__(*prop.rotation.to_axis_angle())  # Fix for consistency


class BoneMorphData(bpy.types.PropertyGroup):
    """ """

    bone: bpy.props.StringProperty(
        name="Bone",
        description="Target bone",
        set=_bone_morph_data_set_bone,
        get=_bone_morph_data_get_bone,
    )

    bone_id: bpy.props.IntProperty(
        name="Bone ID",
    )

    location: bpy.props.FloatVectorProperty(
        name="Location",
        description="Location",
        subtype="TRANSLATION",
        size=3,
        default=[0, 0, 0],
        update=_bone_morph_data_update_location_or_rotation,
    )

    rotation: bpy.props.FloatVectorProperty(
        name="Rotation",
        description="Rotation in quaternions",
        subtype="QUATERNION",
        size=4,
        default=[1, 0, 0, 0],
        update=_bone_morph_data_update_location_or_rotation,
    )


class BoneMorph(_MorphBase, bpy.types.PropertyGroup):
    """Bone Morph"""

    data: bpy.props.CollectionProperty(
        name="Morph Data",
        type=BoneMorphData,
    )
    active_data: bpy.props.IntProperty(
        name="Active Bone Data",
        min=0,
        default=0,
    )


def _material_morph_data_get_material(prop: "MaterialMorphData"):
    mat_p = prop.get("material_data", None)
    if mat_p is not None:
        return mat_p.name
    return ""


def _material_morph_data_set_material(prop: "MaterialMorphData", value: str):
    if value not in bpy.data.materials:
        prop["material_data"] = None
        prop["material_id"] = -1
    else:
        mat = bpy.data.materials[value]
        fnMat = FnMaterial(mat)
        prop["material_data"] = mat
        prop["material_id"] = fnMat.material_id


def _material_morph_data_set_related_mesh(prop: "MaterialMorphData", value: str):
    mesh = FnModel.find_mesh_object_by_name(prop.id_data, value)
    if mesh is not None:
        prop["related_mesh_data"] = mesh.data
    else:
        prop["related_mesh_data"] = None


def _material_morph_data_get_related_mesh(prop):
    mesh_p = prop.get("related_mesh_data", None)
    if mesh_p is not None:
        return mesh_p.name
    return ""


def _material_morph_data_update_modifiable_values(prop: "MaterialMorphData", _context):
    if not prop.name.startswith("mmd_bind"):
        return
    from ..core.shader import _MaterialMorph

    mat = prop["material_data"]
    if mat is not None:
        _MaterialMorph.update_morph_inputs(mat, prop)
    else:
        for mat in FnModel(prop.id_data).materials():
            _MaterialMorph.update_morph_inputs(mat, prop)


class MaterialMorphData(bpy.types.PropertyGroup):
    """ """

    related_mesh: bpy.props.StringProperty(
        name="Related Mesh",
        description="Stores a reference to the mesh where this morph data belongs to",
        set=_material_morph_data_set_related_mesh,
        get=_material_morph_data_get_related_mesh,
    )

    related_mesh_data: bpy.props.PointerProperty(
        name="Related Mesh Data",
        type=bpy.types.Mesh,
    )

    offset_type: bpy.props.EnumProperty(name="Offset Type", description="Select offset type", items=[("MULT", "Multiply", "", 0), ("ADD", "Add", "", 1)], default="ADD")

    material: bpy.props.StringProperty(
        name="Material",
        description="Target material",
        get=_material_morph_data_get_material,
        set=_material_morph_data_set_material,
    )

    material_id: bpy.props.IntProperty(
        name="Material ID",
        default=-1,
    )

    material_data: bpy.props.PointerProperty(
        name="Material Data",
        type=bpy.types.Material,
    )

    diffuse_color: bpy.props.FloatVectorProperty(
        name="Diffuse Color",
        description="Diffuse color",
        subtype="COLOR",
        size=4,
        soft_min=0,
        soft_max=1,
        precision=3,
        step=0.1,
        default=[0, 0, 0, 1],
        update=_material_morph_data_update_modifiable_values,
    )

    specular_color: bpy.props.FloatVectorProperty(
        name="Specular Color",
        description="Specular color",
        subtype="COLOR",
        size=3,
        soft_min=0,
        soft_max=1,
        precision=3,
        step=0.1,
        default=[0, 0, 0],
        update=_material_morph_data_update_modifiable_values,
    )

    shininess: bpy.props.FloatProperty(
        name="Reflect",
        description="Reflect",
        soft_min=0,
        soft_max=500,
        step=100.0,
        default=0.0,
        update=_material_morph_data_update_modifiable_values,
    )

    ambient_color: bpy.props.FloatVectorProperty(
        name="Ambient Color",
        description="Ambient color",
        subtype="COLOR",
        size=3,
        soft_min=0,
        soft_max=1,
        precision=3,
        step=0.1,
        default=[0, 0, 0],
        update=_material_morph_data_update_modifiable_values,
    )

    edge_color: bpy.props.FloatVectorProperty(
        name="Edge Color",
        description="Edge color",
        subtype="COLOR",
        size=4,
        soft_min=0,
        soft_max=1,
        precision=3,
        step=0.1,
        default=[0, 0, 0, 1],
        update=_material_morph_data_update_modifiable_values,
    )

    edge_weight: bpy.props.FloatProperty(
        name="Edge Weight",
        description="Edge weight",
        soft_min=0,
        soft_max=2,
        step=0.1,
        default=0,
        update=_material_morph_data_update_modifiable_values,
    )

    texture_factor: bpy.props.FloatVectorProperty(
        name="Texture factor",
        description="Texture factor",
        subtype="COLOR",
        size=4,
        soft_min=0,
        soft_max=1,
        precision=3,
        step=0.1,
        default=[0, 0, 0, 1],
        update=_material_morph_data_update_modifiable_values,
    )

    sphere_texture_factor: bpy.props.FloatVectorProperty(
        name="Sphere Texture factor",
        description="Sphere texture factor",
        subtype="COLOR",
        size=4,
        soft_min=0,
        soft_max=1,
        precision=3,
        step=0.1,
        default=[0, 0, 0, 1],
        update=_material_morph_data_update_modifiable_values,
    )

    toon_texture_factor: bpy.props.FloatVectorProperty(
        name="Toon Texture factor",
        description="Toon texture factor",
        subtype="COLOR",
        size=4,
        soft_min=0,
        soft_max=1,
        precision=3,
        step=0.1,
        default=[0, 0, 0, 1],
        update=_material_morph_data_update_modifiable_values,
    )


class MaterialMorph(_MorphBase, bpy.types.PropertyGroup):
    """Material Morph"""

    data: bpy.props.CollectionProperty(
        name="Morph Data",
        type=MaterialMorphData,
    )
    active_data: bpy.props.IntProperty(
        name="Active Material Data",
        min=0,
        default=0,
    )


class UVMorphOffset(bpy.types.PropertyGroup):
    """UV Morph Offset"""

    index: bpy.props.IntProperty(
        name="Vertex Index",
        description="Vertex index",
        min=0,
        default=0,
    )
    offset: bpy.props.FloatVectorProperty(
        name="UV Offset",
        description="UV offset",
        size=4,
        # min=-1,
        # max=1,
        # precision=3,
        step=0.1,
        default=[0, 0, 0, 0],
    )


class UVMorph(_MorphBase, bpy.types.PropertyGroup):
    """UV Morph"""

    uv_index: bpy.props.IntProperty(
        name="UV Index",
        description="UV index (UV, UV1 ~ UV4)",
        min=0,
        max=4,
        default=0,
    )
    data_type: bpy.props.EnumProperty(
        name="Data Type",
        description="Select data type",
        items=[
            ("DATA", "Data", "Store offset data in root object (deprecated)", 0),
            ("VERTEX_GROUP", "Vertex Group", "Store offset data in vertex groups", 1),
        ],
        default="DATA",
    )
    data: bpy.props.CollectionProperty(
        name="Morph Data",
        type=UVMorphOffset,
    )
    active_data: bpy.props.IntProperty(
        name="Active UV Data",
        min=0,
        default=0,
    )
    vertex_group_scale: bpy.props.FloatProperty(
        name="Vertex Group Scale",
        description='The value scale of "Vertex Group" data type',
        precision=3,
        step=0.1,
        default=1,
    )


class GroupMorphOffset(bpy.types.PropertyGroup):
    """Group Morph Offset"""

    morph_type: bpy.props.EnumProperty(
        name="Morph Type",
        description="Select morph type",
        items=[
            ("material_morphs", "Material", "Material Morphs", 0),
            ("uv_morphs", "UV", "UV Morphs", 1),
            ("bone_morphs", "Bone", "Bone Morphs", 2),
            ("vertex_morphs", "Vertex", "Vertex Morphs", 3),
            ("group_morphs", "Group", "Group Morphs", 4),
        ],
        default="vertex_morphs",
    )
    factor: bpy.props.FloatProperty(name="Factor", description="Factor", soft_min=0, soft_max=1, precision=3, step=0.1, default=0)


class GroupMorph(_MorphBase, bpy.types.PropertyGroup):
    """Group Morph"""

    data: bpy.props.CollectionProperty(
        name="Morph Data",
        type=GroupMorphOffset,
    )
    active_data: bpy.props.IntProperty(
        name="Active Group Data",
        min=0,
        default=0,
    )


class VertexMorph(_MorphBase, bpy.types.PropertyGroup):
    """Vertex Morph"""
