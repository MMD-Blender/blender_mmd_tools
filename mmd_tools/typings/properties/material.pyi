# -*- coding: utf-8 -*-
# Copyright 2024 MMD Tools authors
# This file is part of MMD Tools.

from typing import List

class MMDMaterial(bpy.types.PropertyGroup):
    name_j: str
    name_e: str

    material_id: int

    ambient_color: List[float]
    diffuse_color: List[float]

    alpha: float

    specular_color: List[float]

    shininess: float

    is_double_sided: bool

    enabled_drop_shadow: bool

    enabled_self_shadow_map: bool

    enabled_self_shadow: bool

    enabled_toon_edge: bool

    edge_color: List[float]

    edge_weight: float

    sphere_texture_type: str

    is_shared_toon_texture: bool
    toon_texture: str

    shared_toon_texture: int

    comment: int

    def is_id_unique(self) -> bool: ...
