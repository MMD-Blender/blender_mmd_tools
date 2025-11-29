# Copyright 2017 MMD Tools authors
# This file is part of MMD Tools.

from bpy.types import Panel

from ..core.light import MMDLight


class MMDLightPanel(Panel):
    bl_idname = "OBJECT_PT_mmd_tools_light"
    bl_label = "MMD Light Tools"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and (MMDLight.isLight(obj) or MMDLight.isMMDLight(obj))

    def draw(self, context):
        obj = context.active_object

        layout = self.layout

        if MMDLight.isMMDLight(obj):
            mmd_light = MMDLight(obj)
            # empty = mmd_light.object()
            light = mmd_light.light()

            c = layout.column()
            c.prop(light.data, "color")
            c.prop(light, "location", text="Light Source")
        else:
            layout.operator("mmd_tools.convert_to_mmd_light", text="Convert")
