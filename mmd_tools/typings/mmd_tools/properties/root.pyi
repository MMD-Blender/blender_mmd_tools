# -*- coding: utf-8 -*-
# Copyright 2024 MMD Tools authors
# This file is part of MMD Tools.

from typing import Literal

import bpy
from .morph import BoneMorph, GroupMorph, MaterialMorph, UVMorph, VertexMorph
from .translations import MMDTranslation

class MMDDisplayItem:
    name: str
    type: Literal["BONE"] | Literal["MORPH"]

    morph_type: Literal["material_morphs"] | Literal["uv_morphs"] | Literal["bone_morphs"] | Literal["vertex_morphs"] | Literal["group_morphs"]

class MMDDisplayItemFrame:
    name: str
    name_e: str

    is_special: bool

    data: bpy.types.bpy_prop_collection[MMDDisplayItem]

    active_item: int

class MMDRoot:
    id_data: bpy.types.Object
    name: str
    name_j: str
    name_e: str
    comment_text: str
    comment_e_text: str
    ik_lookup_factor: int
    show_meshes: bool
    show_rigid_bodies: bool
    show_joints: bool
    show_temporary_objects: bool
    show_armature: bool
    show_names_of_rigid_bodies: bool
    show_names_of_joints: bool
    use_toon_texture: bool
    use_sphere_texture: bool
    use_sdef: bool
    use_property_driver: bool
    is_built: bool
    active_rigidbody_index: int
    active_joint_index: int
    display_item_frames: bpy.types.bpy_prop_collection[MMDDisplayItemFrame]
    active_display_item_frame: int
    material_morphs: bpy.types.bpy_prop_collection[MaterialMorph]
    uv_morphs: bpy.types.bpy_prop_collection[UVMorph]
    bone_morphs: bpy.types.bpy_prop_collection[BoneMorph]
    vertex_morphs: bpy.types.bpy_prop_collection[VertexMorph]
    group_morphs: bpy.types.bpy_prop_collection[GroupMorph]

    active_morph_type: str  # TODO: Replace with StrEnum
    active_morph: int
    morph_panel_show_settings: bool
    active_mesh_index: int
    translation: MMDTranslation

    @staticmethod
    def register() -> None: ...
    @staticmethod
    def unregister() -> None: ...
