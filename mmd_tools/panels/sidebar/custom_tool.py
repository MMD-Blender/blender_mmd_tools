# -*- coding: utf-8 -*-
# Copyright 2024 MMD Tools authors
# This file is part of MMD Tools.

import bpy

from . import PT_PanelBase
from ...bpyutils import FnContext
from ...core.model import FnModel


class MMDToolsCustomToolPanel(PT_PanelBase, bpy.types.Panel):
    bl_idname = "OBJECT_PT_mmd_tools_custom_tool"
    bl_label = "Custom Tool"
    bl_order = 2  # This will position it after Scene Setup

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        
        # Find the active MMD model's root object
        root = FnModel.find_root_object(context.active_object)
        
        if root is None:
            layout.label(text="No MMD model selected", icon="INFO")
            return
            
        # Get the mmd_root property
        mmd_root = root.mmd_root
        
 
        # Add auto-export checkbox
        auto_export_box = layout.box()
        auto_export_box.label(text="Export Settings:", icon="EXPORT")
        auto_export_box.prop(mmd_root, "auto_export_enabled", text="Enable Auto-Export")





