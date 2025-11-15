# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

from bpy.types import Operator


class _SetShadingBase:
    bl_options = {"REGISTER", "UNDO"}

    @staticmethod
    def _get_view3d_spaces(context):
        if getattr(context.area, "type", None) == "VIEW_3D":
            return (context.area.spaces[0],)
        return (area.spaces[0] for area in getattr(context.screen, "areas", ()) if area.type == "VIEW_3D")

    def execute(self, context):
        try:
            context.scene.render.engine = "BLENDER_EEVEE"  # Blender 5.0+
        except TypeError:
            context.scene.render.engine = "BLENDER_EEVEE_NEXT"  # Blender 4.2-4.5

        shading_mode = getattr(self, "_shading_mode", None)
        for space in self._get_view3d_spaces(context):
            shading = space.shading
            shading.type = "SOLID"
            shading.light = "FLAT" if shading_mode == "SHADELESS" else "STUDIO"
            shading.color_type = "TEXTURE" if shading_mode else "MATERIAL"
            shading.show_object_outline = False
            shading.show_backface_culling = False
        return {"FINISHED"}


class SetGLSLShading(Operator, _SetShadingBase):
    bl_idname = "mmd_tools.set_glsl_shading"
    bl_label = "GLSL View"
    bl_description = "Use GLSL shading with additional lighting"

    _shading_mode = "GLSL"


class SetShadelessGLSLShading(Operator, _SetShadingBase):
    bl_idname = "mmd_tools.set_shadeless_glsl_shading"
    bl_label = "Shadeless GLSL View"
    bl_description = "Use only toon shading"

    _shading_mode = "SHADELESS"


class ResetShading(Operator, _SetShadingBase):
    bl_idname = "mmd_tools.reset_shading"
    bl_label = "Reset View"
    bl_description = "Reset to default Blender shading"
