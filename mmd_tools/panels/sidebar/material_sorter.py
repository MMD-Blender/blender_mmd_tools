# Copyright 2016 MMD Tools authors
# This file is part of MMD Tools.

import bpy

from . import PT_ProductionPanelBase


class MMDMaterialSorter(PT_ProductionPanelBase, bpy.types.Panel):
    bl_idname = "OBJECT_PT_mmd_tools_material_sorter"
    bl_label = "Material Sorter"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 10

    def draw(self, context):
        layout = self.layout
        active_obj = context.active_object
        if active_obj is None or active_obj.type != "MESH" or active_obj.mmd_type != "NONE":
            layout.label(text="Select a mesh object")
            return

        col = layout.column(align=True)
        row = col.row()
        row.template_list("MMD_TOOLS_UL_Materials", "", active_obj.data, "materials", active_obj, "active_material_index")
        tb = row.column()
        tb1 = tb.column(align=True)
        tb1.operator("mmd_tools.move_material_up", text="", icon="TRIA_UP")
        tb1.operator("mmd_tools.move_material_down", text="", icon="TRIA_DOWN")


class MMD_TOOLS_UL_Materials(bpy.types.UIList):
    def draw_item(self, _context, layout, _data, item, icon, _active_data, _active_propname, _index):
        if self.layout_type in {"DEFAULT"}:
            if item:
                row = layout.row(align=True)
                item_prop = getattr(item, "mmd_material")
                row.prop(item_prop, "name_j", text="", emboss=False, icon="MATERIAL")
                row.prop(item_prop, "name_e", text="", emboss=True)
            else:
                layout.label(text="UNSET", translate=False, icon="ERROR")
        elif self.layout_type in {"COMPACT"}:
            pass
        elif self.layout_type in {"GRID"}:
            layout.alignment = "CENTER"
            layout.label(text="", icon_value=icon)

    def draw_filter(self, context, layout):
        layout.label(text="Use the arrows to sort", icon="INFO")
