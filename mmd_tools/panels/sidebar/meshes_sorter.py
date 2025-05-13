# Copyright 2016 MMD Tools authors
# This file is part of MMD Tools.

import bpy

from ...core.model import FnModel
from . import PT_ProductionPanelBase


class MMDMeshSorter(PT_ProductionPanelBase, bpy.types.Panel):
    bl_idname = "OBJECT_PT_mmd_tools_meshes_sorter"
    bl_label = "Meshes Sorter"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 9

    def draw(self, context):
        layout = self.layout
        active_obj = context.active_object
        root = FnModel.find_root_object(active_obj)
        if root is None:
            layout.label(text="Select a MMD Model")
            return

        col = layout.column(align=True)
        row = col.row()
        row.template_list("MMD_TOOLS_UL_ModelMeshes", "", context.scene, "objects", root.mmd_root, "active_mesh_index")
        tb = row.column()
        tb1 = tb.column(align=True)
        tb1.enabled = active_obj.type == "MESH" and active_obj.mmd_type == "NONE"
        tb1.operator("mmd_tools.object_move", text="", icon="TRIA_UP_BAR").type = "TOP"
        tb1.operator("mmd_tools.object_move", text="", icon="TRIA_UP").type = "UP"
        tb1.operator("mmd_tools.object_move", text="", icon="TRIA_DOWN").type = "DOWN"
        tb1.operator("mmd_tools.object_move", text="", icon="TRIA_DOWN_BAR").type = "BOTTOM"


class MMD_TOOLS_UL_ModelMeshes(bpy.types.UIList):
    def draw_item(self, _context, layout, _data, item, icon, _active_data, _active_propname, _index):
        if self.layout_type in {"DEFAULT"}:
            layout.label(text=item.name, translate=False, icon="OBJECT_DATA")
        elif self.layout_type in {"COMPACT"}:
            pass
        elif self.layout_type in {"GRID"}:
            layout.alignment = "CENTER"
            layout.label(text="", icon_value=icon)

    def draw_filter(self, context, layout):
        layout.label(text="Use the arrows to sort", icon="INFO")

    def filter_items(self, context, data, propname):
        # We will use the filtering to sort the mesh objects to match the rig order
        objects = getattr(data, propname)
        flt_flags = [~self.bitflag_filter_item] * len(objects)
        flt_neworder = list(range(len(objects)))

        armature = FnModel.find_armature_object(FnModel.find_root_object(context.active_object))
        __is_child_of_armature = lambda x: x.parent and (x.parent == armature or __is_child_of_armature(x.parent))

        name_dict = {}
        for i, obj in enumerate(objects):
            if obj.type == "MESH" and obj.mmd_type == "NONE" and __is_child_of_armature(obj):
                flt_flags[i] = self.bitflag_filter_item
                name_dict[obj.name] = i

        for new_index, name in enumerate(sorted(name_dict.keys())):
            i = name_dict[name]
            flt_neworder[i] = new_index

        return flt_flags, flt_neworder
