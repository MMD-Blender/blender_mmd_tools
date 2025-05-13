# Copyright 2017 MMD Tools authors
# This file is part of MMD Tools.

from bpy.props import FloatProperty
from bpy.types import Operator

from ..core.lamp import MMDLamp


class ConvertToMMDLamp(Operator):
    bl_idname = "mmd_tools.convert_to_mmd_lamp"
    bl_label = "Convert to MMD Light"
    bl_description = "Create a light rig for MMD"
    bl_options = {"REGISTER", "UNDO"}

    scale: FloatProperty(
        name="Scale",
        description="Scaling factor for initializing the light",
        default=0.08,
    )

    @classmethod
    def poll(cls, context):
        return MMDLamp.isLamp(context.active_object)

    def invoke(self, context, event):
        vm = context.window_manager
        return vm.invoke_props_dialog(self)

    def execute(self, context):
        MMDLamp.convertToMMDLamp(context.active_object, self.scale)
        return {"FINISHED"}
