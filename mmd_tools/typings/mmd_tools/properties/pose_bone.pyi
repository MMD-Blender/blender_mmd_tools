# Copyright 2024 MMD Tools authors
# This file is part of MMD Tools.

from mathutils import Vector

class MMDBone:
    name_j: str
    name_e: str
    bone_id: int
    transform_order: int
    is_controllable: bool
    transform_after_dynamics: bool
    enabled_fixed_axis: bool
    fixed_axis: Vector
    enabled_local_axes: bool
    local_axis_x: Vector
    local_axis_z: Vector
    is_tip: bool
    ik_rotation_constraint: float
    has_additional_rotation: bool
    has_additional_location: bool
    additional_transform_bone: str
    additional_transform_bone_id: int
    additional_transform_influence: float
    is_additional_transform_dirty: bool
    display_connection_bone: str
    display_connection_bone_id: int
    display_connection_type: str  # 'BONE', 'OFFSET'
