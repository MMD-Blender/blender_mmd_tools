# Copyright 2023 MMD Tools authors
# This file is part of MMD Tools.

import bpy


class MMDShadingPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_mmd_shading"
    bl_label = "MMD UuuNyaa"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

    def draw(self, _context):
        pass

    @staticmethod
    def draw_panel(this: bpy.types.Panel, context):
        if context.space_data.shading.type != "SOLID":
            return

        col = this.layout.column(align=True)
        col.label(text="MMD Shading Presets")
        row = col.row(align=True)
        row.operator("mmd_tools.set_glsl_shading", text="GLSL")
        row.operator("mmd_tools.set_shadeless_glsl_shading", text="Shadeless")
        row = col.row(align=True)
        row.operator("mmd_tools.reset_shading", text="Reset")

    @staticmethod
    def register():
        bpy.types.VIEW3D_PT_shading.append(MMDShadingPanel.draw_panel)

    @staticmethod
    def unregister():
        bpy.types.VIEW3D_PT_shading.remove(MMDShadingPanel.draw_panel)
