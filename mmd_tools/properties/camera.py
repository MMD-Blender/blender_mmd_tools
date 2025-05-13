# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

import math

import bpy

from . import patch_library_overridable


class MMDCamera(bpy.types.PropertyGroup):
    angle: bpy.props.FloatProperty(
        name="Angle",
        description="Camera lens field of view",
        subtype="ANGLE",
        min=math.radians(1),
        max=math.radians(180),
        soft_max=math.radians(125),
        step=100.0,
    )

    is_perspective: bpy.props.BoolProperty(
        name="Perspective",
        description="Is perspective",
        default=True,
    )

    @staticmethod
    def register():
        bpy.types.Object.mmd_camera = patch_library_overridable(bpy.props.PointerProperty(type=MMDCamera))

    @staticmethod
    def unregister():
        del bpy.types.Object.mmd_camera
