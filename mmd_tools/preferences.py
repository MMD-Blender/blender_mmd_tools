# -*- coding: utf-8 -*-
# Copyright 2022 MMD Tools authors
# This file is part of MMD Tools.

import os

import bpy


class MMDToolsAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    enable_mmd_model_production_features: bpy.props.BoolProperty(
        name="Enable MMD Model Production Features",
        default=True,
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

    def draw(self, _context):
        layout: bpy.types.UILayout = self.layout  # pylint: disable=no-member
        layout.prop(self, "enable_mmd_model_production_features")
        layout.prop(self, "shared_toon_folder")
        layout.prop(self, "base_texture_folder")
        layout.prop(self, "dictionary_folder")
