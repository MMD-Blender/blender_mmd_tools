# -*- coding: utf-8 -*-
# Copyright 2015 MMD Tools authors
# This file is part of MMD Tools.

import bpy

from ...core import FnCore
from . import PT_ProductionPanelBase


class MMDModelProductionPanel(PT_ProductionPanelBase, bpy.types.Panel):
    bl_idname = "OBJECT_PT_mmd_tools_model_production"
    bl_label = "Model Production"
    bl_order = 3

    def draw(self, context):
        active_obj = context.active_object

        layout = self.layout
        col = layout.column(align=True)
        grid = col.grid_flow(row_major=True)
        row = grid.row(align=True)
        row.operator("mmd_tools.create_mmd_model_root_object", text="Create Model", icon="OUTLINER_OB_ARMATURE")
        row.operator("mmd_tools.convert_to_mmd_model", text="Convert Model", icon="ARMATURE_DATA")

        root = FnCore.find_root_object(active_obj)
        row = grid.row(align=True)
        row.enabled = root is not None
        row.operator("mmd_tools.attach_meshes", text="Attach Meshes", icon="OUTLINER_OB_MESH")

        row = grid.row(align=True)
        row.operator("mmd_tools.translate_mmd_model", text="Translate", icon="HELP")
        row.operator("mmd_tools.global_translation_popup", text="", icon="WINDOW")

        self.draw_edit(context)

    def draw_edit(self, _context):
        col = self.layout.column(align=True)
        col.label(text="Model Surgery:", icon="MOD_ARMATURE")
        grid = col.grid_flow(row_major=True, align=True)

        separate_row = grid.row(align=True)
        row = separate_row.row(align=True)
        row.operator_context = "EXEC_DEFAULT"
        op = row.operator("mmd_tools.model_separate_by_bones", text="Chop", icon="BONE_DATA")
        op.separate_armature = True
        op.include_descendant_bones = True
        op.boundary_joint_owner = "DESTINATION"

        row = row.row(align=True)
        row.operator_context = "INVOKE_DEFAULT"
        op = row.operator("mmd_tools.model_separate_by_bones", text="", icon="WINDOW")

        row = separate_row.row(align=True)
        row.operator_context = "EXEC_DEFAULT"
        op = row.operator("mmd_tools.model_separate_by_bones", text="Peel", icon="MOD_EXPLODE")
        op.separate_armature = False
        op.include_descendant_bones = False
        op.boundary_joint_owner = "DESTINATION"

        row = grid.row(align=True)
        row.operator_context = "INVOKE_DEFAULT"
        row.operator("mmd_tools.model_join_by_bones", text="Join", icon="GROUP_BONE")
