# -*- coding: utf-8 -*-
# Copyright 2015 MMD Tools authors
# This file is part of MMD Tools.


import bpy

from ...core.model import FnModel
from . import FnDraw, PT_ProductionPanelBase
from ...utils import ItemOp


class MMDDisplayItemsPanel(PT_ProductionPanelBase, bpy.types.Panel):
    bl_idname = "OBJECT_PT_mmd_tools_display_items"
    bl_label = "Display Panel"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 10

    def draw(self, context):
        active_obj = context.active_object
        root = FnModel.find_root_object(active_obj)
        if root is None:
            self.layout.label(text="Select a MMD Model")
            return

        mmd_root = root.mmd_root
        col = self.layout.column()
        row = col.row()
        row.template_list(
            "MMD_ROOT_UL_display_item_frames",
            "",
            mmd_root,
            "display_item_frames",
            mmd_root,
            "active_display_item_frame",
        )
        tb = row.column()
        tb1 = tb.column(align=True)
        tb1.operator("mmd_tools.display_item_frame_add", text="", icon="ADD")
        tb1.operator("mmd_tools.display_item_frame_remove", text="", icon="REMOVE")
        tb1.menu("OBJECT_MT_mmd_tools_display_item_frame_menu", text="", icon="DOWNARROW_HLT")
        tb.separator()
        tb1 = tb.column(align=True)
        tb1.operator("mmd_tools.display_item_frame_move", text="", icon="TRIA_UP").type = "UP"
        tb1.operator("mmd_tools.display_item_frame_move", text="", icon="TRIA_DOWN").type = "DOWN"

        frame = ItemOp.get_by_index(mmd_root.display_item_frames, mmd_root.active_display_item_frame)
        if frame is None:
            return

        c = col.column(align=True)
        row = c.row()
        row.template_list(
            "MMD_ROOT_UL_display_items",
            "",
            frame,
            "data",
            frame,
            "active_item",
        )
        tb = row.column()
        tb1 = tb.column(align=True)
        tb1.operator("mmd_tools.display_item_add", text="", icon="ADD")
        tb1.operator("mmd_tools.display_item_remove", text="", icon="REMOVE")
        tb1.menu("OBJECT_MT_mmd_tools_display_item_menu", text="", icon="DOWNARROW_HLT")
        tb.separator()
        tb1 = tb.column(align=True)
        tb1.operator("mmd_tools.display_item_move", text="", icon="TRIA_UP").type = "UP"
        tb1.operator("mmd_tools.display_item_move", text="", icon="TRIA_DOWN").type = "DOWN"

        row = col.row()
        r = row.row(align=True)
        r.operator("mmd_tools.display_item_find", text="Bone", icon="VIEWZOOM").type = "BONE"
        r.operator("mmd_tools.display_item_find", text="Morph", icon="VIEWZOOM").type = "MORPH"
        row.operator("mmd_tools.display_item_select_current", text="Select")


class MMD_ROOT_UL_display_item_frames(bpy.types.UIList):
    def draw_item(self, _context, layout, _data, item, icon, _active_data, _active_propname, _index):
        frame = item
        if self.layout_type in {"DEFAULT"}:
            row = layout.split(factor=0.5, align=True)
            if frame.is_special:
                row.label(text=frame.name, translate=False)
                row = row.row(align=True)
                row.label(text=frame.name_e, translate=False)
                row.label(text="", icon="LOCKED")
            else:
                row.prop(frame, "name", text="", emboss=False)
                row.prop(frame, "name_e", text="", emboss=True)
        elif self.layout_type in {"COMPACT"}:
            pass
        elif self.layout_type in {"GRID"}:
            layout.alignment = "CENTER"
            layout.label(text="", icon_value=icon)


class MMD_ROOT_UL_display_items(bpy.types.UIList):
    morph_filter: bpy.props.EnumProperty(
        name="Morph Filter",
        description="Only show items matching this category",
        options={"ENUM_FLAG"},
        items=[
            ("SYSTEM", "Hidden", "", 1),
            ("EYEBROW", "Eye Brow", "", 2),
            ("EYE", "Eye", "", 4),
            ("MOUTH", "Mouth", "", 8),
            ("OTHER", "Other", "", 16),
        ],
        default={
            "SYSTEM",
            "EYEBROW",
            "EYE",
            "MOUTH",
            "OTHER",
        },
    )
    mmd_name: bpy.props.EnumProperty(
        name="MMD Name",
        description="Show JP or EN name of MMD bone",
        items=[
            ("name_j", "JP", "", 1),
            ("name_e", "EN", "", 2),
        ],
        default="name_e",
    )

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {"DEFAULT"}:
            if item.type == "BONE":
                row = layout.split(factor=0.5, align=True)
                row.prop(item, "name", text="", emboss=False, icon="BONE_DATA")
                FnDraw.draw_bone_special(row, FnModel.find_armature_object(item.id_data), item.name, self.mmd_name)
            else:
                row = layout.split(factor=0.6, align=True)
                row.prop(item, "name", text="", emboss=False, icon="SHAPEKEY_DATA")
                row = row.row(align=True)
                row.prop(item, "morph_type", text="", emboss=False)
                if item.name not in getattr(item.id_data.mmd_root, item.morph_type):
                    row.label(icon="ERROR")
        elif self.layout_type in {"COMPACT"}:
            pass
        elif self.layout_type in {"GRID"}:
            layout.alignment = "CENTER"
            layout.label(text="", icon_value=icon)

    def filter_items(self, context, data, propname):
        if len(self.morph_filter) == 5 or data.name != "表情":
            return [], []

        objects = getattr(data, propname)
        flt_flags = [~self.bitflag_filter_item] * len(objects)
        flt_neworder = []

        for i, item in enumerate(objects):
            morph = getattr(item.id_data.mmd_root, item.morph_type).get(item.name, None)
            if morph and morph.category in self.morph_filter:
                flt_flags[i] = self.bitflag_filter_item

        return flt_flags, flt_neworder

    def draw_filter(self, context, layout):
        row = layout.row()
        row.prop(self, "morph_filter", expand=True)
        row.prop(self, "mmd_name", expand=True)


class MMDDisplayItemFrameMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_mmd_tools_display_item_frame_menu"
    bl_label = "Display Item Frame Menu"

    def draw(self, context):
        layout = self.layout
        layout.operator_enum("mmd_tools.display_item_quick_setup", "type")
        layout.separator()
        layout.operator("mmd_tools.display_item_frame_move", icon="TRIA_UP_BAR", text="Move To Top").type = "TOP"
        layout.operator("mmd_tools.display_item_frame_move", icon="TRIA_DOWN_BAR", text="Move To Bottom").type = "BOTTOM"


class MMDDisplayItemMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_mmd_tools_display_item_menu"
    bl_label = "Display Item Menu"

    def draw(self, context):
        layout = self.layout
        layout.operator("mmd_tools.display_item_remove", text="Delete All", icon="X").all = True
        layout.separator()
        layout.operator("mmd_tools.display_item_move", icon="TRIA_UP_BAR", text="Move To Top").type = "TOP"
        layout.operator("mmd_tools.display_item_move", icon="TRIA_DOWN_BAR", text="Move To Bottom").type = "BOTTOM"
