# Copyright 2022 MMD Tools authors
# This file is part of MMD Tools.

import os

import bpy


def get_preset_items_for_operator(operator_bl_idname):
    """Get preset items for EnumProperty"""
    items = [("__DEFAULT__", "Default", "Use built-in defaults")]
    try:
        from .operators import fileio

        presets = fileio.get_available_presets(operator_bl_idname)
        items.extend((preset, preset, f"Use preset: {preset}") for preset in presets)
    except Exception:
        pass
    return items


def get_pmx_import_preset_items(self, context):
    return get_preset_items_for_operator("mmd_tools.import_model")


def get_vmd_import_preset_items(self, context):
    return get_preset_items_for_operator("mmd_tools.import_vmd")


def get_vpd_import_preset_items(self, context):
    return get_preset_items_for_operator("mmd_tools.import_vpd")


def get_pmx_export_preset_items(self, context):
    return get_preset_items_for_operator("mmd_tools.export_pmx")


def get_vmd_export_preset_items(self, context):
    return get_preset_items_for_operator("mmd_tools.export_vmd")


def get_vpd_export_preset_items(self, context):
    return get_preset_items_for_operator("mmd_tools.export_vpd")


def get_additional_unallowed_chars(prop_name: str) -> str:
    """Get the additional unallowed characters string from addon preferences.

    Args:
        prop_name: One of 'model', 'texture', 'bone', 'morph'.

    Returns:
        The unallowed characters string, or empty string if not set.
    """
    try:
        prefs = bpy.context.preferences.addons[__package__].preferences
        return getattr(prefs, f"additional_unallowed_chars_{prop_name}", "")
    except Exception:
        return ""


def get_replacement_char() -> str:
    """Get the replacement character from addon preferences."""
    try:
        prefs = bpy.context.preferences.addons[__package__].preferences
        return prefs.replacement_char
    except Exception:
        return "_"


class MMDToolsAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    enable_mmd_model_production_features: bpy.props.BoolProperty(
        name="Enable MMD Model Production Features",
        default=True,
    )
    use_collision_collections: bpy.props.BoolProperty(
        name="Use Collision Collections for New Models",
        description="Default Collision Collections setting for newly imported or created models. See the setting next to Assembly -> Physics",
        default=False,
    )
    shared_toon_folder: bpy.props.StringProperty(
        name="Shared Toon Texture Folder",
        description=('Directory path to toon textures. This is normally the "Data" directory within of your MikuMikuDance directory'),
        subtype="DIR_PATH",
        default=os.path.join(os.path.dirname(__file__), "externals", "MikuMikuDance"),
    )
    base_texture_folder: bpy.props.StringProperty(
        name="Base Texture Folder",
        description="Path for textures shared between models",
        subtype="DIR_PATH",
    )
    dictionary_folder: bpy.props.StringProperty(
        name="Dictionary Folder",
        description="Path for searching csv dictionaries",
        subtype="DIR_PATH",
        default=os.path.dirname(__file__),
    )

    # Preset selection properties
    default_pmx_import_preset: bpy.props.EnumProperty(
        name="Default PMX Import Operator Preset",
        description="Default preset to use for PMX import operations",
        items=get_pmx_import_preset_items,
        default=0,
    )
    default_vmd_import_preset: bpy.props.EnumProperty(
        name="Default VMD Import Operator Preset",
        description="Default preset to use for VMD import operations",
        items=get_vmd_import_preset_items,
        default=0,
    )
    default_vpd_import_preset: bpy.props.EnumProperty(
        name="Default VPD Import Operator Preset",
        description="Default preset to use for VPD import operations",
        items=get_vpd_import_preset_items,
        default=0,
    )
    default_pmx_export_preset: bpy.props.EnumProperty(
        name="Default PMX Export Operator Preset",
        description="Default preset to use for PMX export operations",
        items=get_pmx_export_preset_items,
        default=0,
    )
    default_vmd_export_preset: bpy.props.EnumProperty(
        name="Default VMD Export Operator Preset",
        description="Default preset to use for VMD export operations",
        items=get_vmd_export_preset_items,
        default=0,
    )
    default_vpd_export_preset: bpy.props.EnumProperty(
        name="Default VPD Export Operator Preset",
        description="Default preset to use for VPD export operations",
        items=get_vpd_export_preset_items,
        default=0,
    )

    # Additional unallowed character settings
    additional_unallowed_chars_model: bpy.props.StringProperty(
        name="Additional Unallowed Characters in Model Name",
        description="Characters that are not allowed in model names. Each character in this string will be treated as unallowed",
        default="",
    )
    additional_unallowed_chars_texture: bpy.props.StringProperty(
        name="Additional Unallowed Characters in Texture Name",
        description="Characters that are not allowed in texture names. Each character in this string will be treated as unallowed",
        default="",
    )
    additional_unallowed_chars_bone: bpy.props.StringProperty(
        name="Additional Unallowed Characters in Bone Name",
        description="Characters that are not allowed in bone names. Each character in this string will be treated as unallowed",
        default="",
    )
    additional_unallowed_chars_morph: bpy.props.StringProperty(
        name="Additional Unallowed Characters in Morph Name",
        description="Characters that are not allowed in morph names. Each character in this string will be treated as unallowed",
        default="",
    )
    replacement_char: bpy.props.StringProperty(
        name="Replacement Character",
        description="Character used to replace unallowed characters. Leave empty to remove them instead",
        default="_",
        maxlen=1,
    )

    def initialize_defaults(self):
        """Initialize default preset values, converting empty strings to default preset"""
        preset_configs = [
            ("default_pmx_import_preset", "mmd_tools.import_model"),
            ("default_pmx_export_preset", "mmd_tools.export_pmx"),
            ("default_vmd_import_preset", "mmd_tools.import_vmd"),
            ("default_vmd_export_preset", "mmd_tools.export_vmd"),
            ("default_vpd_import_preset", "mmd_tools.import_vpd"),
            ("default_vpd_export_preset", "mmd_tools.export_vpd"),
        ]

        for prop_name, operator_name in preset_configs:
            current_value = getattr(self, prop_name, "")
            if current_value == "":  # Uninitialized
                setattr(self, prop_name, "__DEFAULT__")

    def draw(self, _context):
        layout: bpy.types.UILayout = self.layout  # pylint: disable=no-member

        self.initialize_defaults()

        layout.prop(self, "enable_mmd_model_production_features")
        layout.prop(self, "use_collision_collections")
        layout.prop(self, "shared_toon_folder")
        layout.prop(self, "base_texture_folder")
        layout.prop(self, "dictionary_folder")

        layout.separator()
        layout.label(text="Default Operator Presets:")
        layout.prop(self, "default_pmx_import_preset", text="PMX Import")
        layout.prop(self, "default_pmx_export_preset", text="PMX Export")
        layout.prop(self, "default_vmd_import_preset", text="VMD Import")
        layout.prop(self, "default_vmd_export_preset", text="VMD Export")
        layout.prop(self, "default_vpd_import_preset", text="VPD Import")
        layout.prop(self, "default_vpd_export_preset", text="VPD Export")

        layout.separator()
        layout.label(text="Additional Unallowed Characters (Model Debug):", icon="TOOL_SETTINGS")
        layout.prop(self, "additional_unallowed_chars_model", text="Model Name")
        layout.prop(self, "additional_unallowed_chars_texture", text="Texture Filename")
        layout.prop(self, "additional_unallowed_chars_bone", text="Bone Name")
        layout.prop(self, "additional_unallowed_chars_morph", text="Morph Name")
        layout.prop(self, "replacement_char", text="-> Replaced With")
