# Copyright 2015 MMD Tools authors
# This file is part of MMD Tools.

import bpy

from ...core.model import FnModel
from . import PT_ProductionPanelBase, UL_ObjectsMixIn


class MMDJointSelectorPanel(PT_ProductionPanelBase, bpy.types.Panel):
    bl_idname = "OBJECT_PT_mmd_tools_joint_list"
    bl_label = "Joints"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 8

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
            "MMD_TOOLS_UL_joints",
            "",
            context.scene,
            "objects",
            root.mmd_root,
            "active_joint_index",
        )
        tb = row.column()
        tb1 = tb.column(align=True)
        tb1.operator("mmd_tools.joint_add", text="", icon="ADD")
        tb1.operator("mmd_tools.joint_remove", text="", icon="REMOVE")
        tb1.menu("OBJECT_MT_mmd_tools_joint_menu", text="", icon="DOWNARROW_HLT")
        tb.separator()
        tb1 = tb.column(align=True)
        tb1.enabled = active_obj.mmd_type == "JOINT"
        tb1.operator("mmd_tools.object_move", text="", icon="TRIA_UP").type = "UP"
        tb1.operator("mmd_tools.object_move", text="", icon="TRIA_DOWN").type = "DOWN"


class MMD_TOOLS_UL_joints(bpy.types.UIList, UL_ObjectsMixIn):
    mmd_type = "JOINT"
    icon = "CONSTRAINT"
    prop_name = "mmd_joint"

    def draw_item_special(self, context, layout, item):
        rbc = item.rigid_body_constraint
        if rbc is None:
            layout.label(icon="ERROR")
        elif rbc.object1 is None or rbc.object2 is None:
            layout.label(icon="OBJECT_DATA")
        elif rbc.object1 == rbc.object2:
            layout.label(icon="MESH_CUBE")


class MMDJointMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_mmd_tools_joint_menu"
    bl_label = "Joint Menu"

    def draw(self, context):
        layout = self.layout
        layout.enabled = context.active_object.mmd_type == "JOINT"
        layout.operator("mmd_tools.object_move", icon="TRIA_UP_BAR", text="Move To Top").type = "TOP"
        layout.operator("mmd_tools.object_move", icon="TRIA_DOWN_BAR", text="Move To Bottom").type = "BOTTOM"
