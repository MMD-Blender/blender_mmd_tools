# -*- coding: utf-8 -*-
# Copyright 2015 MMD Tools authors
# This file is part of MMD Tools.

import bpy

from ...core.model import FnModel
from . import PT_ProductionPanelBase, UL_ObjectsMixIn


class MMDRigidbodySelectorPanel(PT_ProductionPanelBase, bpy.types.Panel):
    bl_idname = "OBJECT_PT_mmd_tools_rigidbody_list"
    bl_label = "Rigid Bodies"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 6

    def draw(self, context):
        active_obj = context.active_object
        root = FnModel.find_root_object(active_obj)
        if root is None:
            self.layout.label(text="Select a MMD Model")
            return

        col = self.layout.column()
        c = col.column(align=True)
        row = c.row()
        row.template_list(
            "MMD_TOOLS_UL_rigidbodies",
            "",
            context.scene,
            "objects",
            root.mmd_root,
            "active_rigidbody_index",
        )
        tb = row.column()
        tb1 = tb.column(align=True)
        tb1.operator("mmd_tools.rigid_body_add", text="", icon="ADD")
        tb1.operator("mmd_tools.rigid_body_remove", text="", icon="REMOVE")
        tb1.menu("OBJECT_MT_mmd_tools_rigidbody_menu", text="", icon="DOWNARROW_HLT")
        tb.separator()
        tb1 = tb.column(align=True)
        tb1.enabled = active_obj.mmd_type == "RIGID_BODY"
        tb1.operator("mmd_tools.object_move", text="", icon="TRIA_UP").type = "UP"
        tb1.operator("mmd_tools.object_move", text="", icon="TRIA_DOWN").type = "DOWN"


class MMD_TOOLS_UL_rigidbodies(bpy.types.UIList, UL_ObjectsMixIn):
    mmd_type = "RIGID_BODY"
    icon = "MESH_ICOSPHERE"
    prop_name = "mmd_rigid"

    def draw_item_special(self, context, layout, item):
        rb = item.rigid_body
        if rb is None:
            layout.label(icon="ERROR")
        elif not item.mmd_rigid.bone:
            layout.label(icon="BONE_DATA")


class MMDRigidbodySelectMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_mmd_tools_rigidbody_select_menu"
    bl_label = "Rigidbody Select Menu"

    def draw(self, context):
        layout = self.layout
        layout.operator_context = "INVOKE_DEFAULT"
        layout.operator("mmd_tools.rigid_body_select", text="Select Similar...")
        layout.separator()
        layout.operator_context = "EXEC_DEFAULT"
        layout.operator_enum("mmd_tools.rigid_body_select", "properties")


class MMDRigidbodyMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_mmd_tools_rigidbody_menu"
    bl_label = "Rigidbody Menu"

    def draw(self, context):
        layout = self.layout
        layout.enabled = context.active_object.mmd_type == "RIGID_BODY"
        layout.menu("OBJECT_MT_mmd_tools_rigidbody_select_menu", text="Select Similar")
        layout.separator()
        layout.operator("mmd_tools.object_move", icon="TRIA_UP_BAR", text="Move To Top").type = "TOP"
        layout.operator("mmd_tools.object_move", icon="TRIA_DOWN_BAR", text="Move To Bottom").type = "BOTTOM"
