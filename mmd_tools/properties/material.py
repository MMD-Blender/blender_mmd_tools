# -*- coding: utf-8 -*-
# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

import bpy

from .. import utils
from ..core import material
from ..core.material import FnMaterial
from ..core.model import FnModel
from . import patch_library_overridable


def _mmd_material_update_ambient_color(prop: "MMDMaterial", _context):
    FnMaterial(prop.id_data).update_ambient_color()


def _mmd_material_update_diffuse_color(prop: "MMDMaterial", _context):
    FnMaterial(prop.id_data).update_diffuse_color()


def _mmd_material_update_alpha(prop: "MMDMaterial", _context):
    FnMaterial(prop.id_data).update_alpha()


def _mmd_material_update_specular_color(prop: "MMDMaterial", _context):
    FnMaterial(prop.id_data).update_specular_color()


def _mmd_material_update_shininess(prop: "MMDMaterial", _context):
    FnMaterial(prop.id_data).update_shininess()


def _mmd_material_update_is_double_sided(prop: "MMDMaterial", _context):
    FnMaterial(prop.id_data).update_is_double_sided()


def _mmd_material_update_sphere_texture_type(prop: "MMDMaterial", context):
    FnMaterial(prop.id_data).update_sphere_texture_type(context.active_object)


def _mmd_material_update_toon_texture(prop: "MMDMaterial", _context):
    FnMaterial(prop.id_data).update_toon_texture()


def _mmd_material_update_enabled_drop_shadow(prop: "MMDMaterial", _context):
    FnMaterial(prop.id_data).update_drop_shadow()


def _mmd_material_update_enabled_self_shadow_map(prop: "MMDMaterial", _context):
    FnMaterial(prop.id_data).update_self_shadow_map()


def _mmd_material_update_enabled_self_shadow(prop: "MMDMaterial", _context):
    FnMaterial(prop.id_data).update_self_shadow()


def _mmd_material_update_enabled_toon_edge(prop: "MMDMaterial", _context):
    FnMaterial(prop.id_data).update_enabled_toon_edge()


def _mmd_material_update_edge_color(prop: "MMDMaterial", _context):
    FnMaterial(prop.id_data).update_edge_color()


def _mmd_material_update_edge_weight(prop: "MMDMaterial", _context):
    FnMaterial(prop.id_data).update_edge_weight()


def _mmd_material_get_name_j(prop: "MMDMaterial"):
    return prop.get("name_j", "")


def _mmd_material_set_name_j(prop: "MMDMaterial", value: str):
    prop_value = value
    if prop_value and prop_value != prop.get("name_j"):
        root = FnModel.find_root_object(bpy.context.active_object)
        if root is None:
            prop_value = utils.unique_name(value, {mat.mmd_material.name_j for mat in bpy.data.materials})
        else:
            prop_value = utils.unique_name(value, {mat.mmd_material.name_j for mat in FnModel.iterate_materials(root)})

    prop["name_j"] = prop_value


# ===========================================
# Property classes
# ===========================================


class MMDMaterial(bpy.types.PropertyGroup):
    """マテリアル"""

    name_j: bpy.props.StringProperty(
        name="Name",
        description="Japanese Name",
        default="",
        set=_mmd_material_set_name_j,
        get=_mmd_material_get_name_j,
    )

    name_e: bpy.props.StringProperty(
        name="Name(Eng)",
        description="English Name",
        default="",
    )

    material_id: bpy.props.IntProperty(
        name="Material ID",
        description="Unique ID for the reference of material morph",
        default=-1,
        min=-1,
    )

    ambient_color: bpy.props.FloatVectorProperty(
        name="Ambient Color",
        description="Ambient color",
        subtype="COLOR",
        size=3,
        min=0,
        max=1,
        precision=3,
        step=0.1,
        default=[0.4, 0.4, 0.4],
        update=_mmd_material_update_ambient_color,
    )

    diffuse_color: bpy.props.FloatVectorProperty(
        name="Diffuse Color",
        description="Diffuse color",
        subtype="COLOR",
        size=3,
        min=0,
        max=1,
        precision=3,
        step=0.1,
        default=[0.8, 0.8, 0.8],
        update=_mmd_material_update_diffuse_color,
    )

    alpha: bpy.props.FloatProperty(
        name="Alpha",
        description="Alpha transparency",
        min=0,
        max=1,
        precision=3,
        step=0.1,
        default=1.0,
        update=_mmd_material_update_alpha,
    )

    specular_color: bpy.props.FloatVectorProperty(
        name="Specular Color",
        description="Specular color",
        subtype="COLOR",
        size=3,
        min=0,
        max=1,
        precision=3,
        step=0.1,
        default=[0.625, 0.625, 0.625],
        update=_mmd_material_update_specular_color,
    )

    shininess: bpy.props.FloatProperty(
        name="Reflect",
        description="Sharpness of reflected highlights",
        min=0,
        soft_max=512,
        step=100.0,
        default=50.0,
        update=_mmd_material_update_shininess,
    )

    is_double_sided: bpy.props.BoolProperty(
        name="Double Sided",
        description="Both sides of mesh should be rendered",
        default=False,
        update=_mmd_material_update_is_double_sided,
    )

    enabled_drop_shadow: bpy.props.BoolProperty(
        name="Ground Shadow",
        description="Display ground shadow",
        default=True,
        update=_mmd_material_update_enabled_drop_shadow,
    )

    enabled_self_shadow_map: bpy.props.BoolProperty(
        name="Self Shadow Map",
        description="Object can become shadowed by other objects",
        default=True,
        update=_mmd_material_update_enabled_self_shadow_map,
    )

    enabled_self_shadow: bpy.props.BoolProperty(
        name="Self Shadow",
        description="Object can cast shadows",
        default=True,
        update=_mmd_material_update_enabled_self_shadow,
    )

    enabled_toon_edge: bpy.props.BoolProperty(
        name="Toon Edge",
        description="Use toon edge",
        default=False,
        update=_mmd_material_update_enabled_toon_edge,
    )

    edge_color: bpy.props.FloatVectorProperty(
        name="Edge Color",
        description="Toon edge color",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        precision=3,
        step=0.1,
        default=[0, 0, 0, 1],
        update=_mmd_material_update_edge_color,
    )

    edge_weight: bpy.props.FloatProperty(
        name="Edge Weight",
        description="Toon edge size",
        min=0,
        max=100,
        soft_max=2,
        step=1.0,
        default=1.0,
        update=_mmd_material_update_edge_weight,
    )

    sphere_texture_type: bpy.props.EnumProperty(
        name="Sphere Map Type",
        description="Choose sphere texture blend type",
        items=[
            (str(material.SPHERE_MODE_OFF), "Off", "", 1),
            (str(material.SPHERE_MODE_MULT), "Multiply", "", 2),
            (str(material.SPHERE_MODE_ADD), "Add", "", 3),
            (str(material.SPHERE_MODE_SUBTEX), "SubTexture", "", 4),
        ],
        update=_mmd_material_update_sphere_texture_type,
    )

    is_shared_toon_texture: bpy.props.BoolProperty(
        name="Use Shared Toon Texture",
        description="Use shared toon texture or custom toon texture",
        default=False,
        update=_mmd_material_update_toon_texture,
    )

    toon_texture: bpy.props.StringProperty(
        name="Toon Texture",
        subtype="FILE_PATH",
        description="The file path of custom toon texture",
        default="",
        update=_mmd_material_update_toon_texture,
    )

    shared_toon_texture: bpy.props.IntProperty(
        name="Shared Toon Texture",
        description="Shared toon texture id (toon01.bmp ~ toon10.bmp)",
        default=0,
        min=0,
        max=9,
        update=_mmd_material_update_toon_texture,
    )

    comment: bpy.props.StringProperty(
        name="Comment",
        description="Comment",
    )

    def is_id_unique(self):
        return self.material_id < 0 or not next((m for m in bpy.data.materials if m.mmd_material != self and m.mmd_material.material_id == self.material_id), None)

    @staticmethod
    def register():
        bpy.types.Material.mmd_material = patch_library_overridable(bpy.props.PointerProperty(type=MMDMaterial))

    @staticmethod
    def unregister():
        del bpy.types.Material.mmd_material
