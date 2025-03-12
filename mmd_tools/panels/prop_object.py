# -*- coding: utf-8 -*-
# Copyright 2015 MMD Tools authors
# This file is part of MMD Tools.

import bpy

from ..core import FnCore


class MMDModelObjectPanel(bpy.types.Panel):
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_idname = "OBJECT_PT_mmd_tools_root_object"
    bl_label = "MMD Model Information"

    @classmethod
    def poll(cls, context):
        return FnCore.find_root_object(context.active_object)

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        root = FnCore.find_root_object(obj)

        c = layout.column()
        c.prop(root.mmd_root, "name")
        c.prop(root.mmd_root, "name_e")
        c = layout.column()
        c.prop_search(root.mmd_root, "comment_text", search_data=bpy.data, search_property="texts")
        c.prop_search(root.mmd_root, "comment_e_text", search_data=bpy.data, search_property="texts")
        c = layout.column()
        c.operator("mmd_tools.change_mmd_ik_loop_factor", text="Change MMD IK Loop Factor")
        c.operator("mmd_tools.recalculate_bone_roll", text="Recalculate bone roll")
