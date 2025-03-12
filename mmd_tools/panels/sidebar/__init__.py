# -*- coding: utf-8 -*-
# Copyright 2024 MMD Tools authors
# This file is part of MMD Tools.

from typing import Optional

import bpy

from ...bpyutils import FnContext
from ...core import FnCore


class FnDraw:
    @staticmethod
    def draw_bone_special(layout: bpy.types.UILayout, armature: bpy.types.Object, bone_name: str, mmd_name: Optional[str] = None):
        if armature is None:
            return
        row = layout.row(align=True)
        p_bone: bpy.types.PoseBone = armature.pose.bones.get(bone_name, None)
        if p_bone:
            bone = p_bone.bone
            if mmd_name:
                row.prop(p_bone.mmd_bone, mmd_name, text="", emboss=True)
            ic = "RESTRICT_VIEW_ON" if bone.hide else "RESTRICT_VIEW_OFF"
            row.prop(bone, "hide", text="", emboss=p_bone.mmd_bone.is_tip, icon=ic)
            row.active = armature.mode != "EDIT"
        else:
            row.label()  # for alignment only
            row.label(icon="ERROR")


class PT_PanelBase:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MMD"


class PT_ProductionPanelBase(PT_PanelBase):
    @classmethod
    def poll(cls, context):
        return FnContext.get_addon_preferences_attribute(context, "enable_mmd_model_production_features", True)


class UL_ObjectsMixIn:
    model_filter: bpy.props.EnumProperty(
        name="Model Filter",
        description="Show items of active model or all models",
        items=[
            ("ACTIVE", "Active Model", "", 0),
            ("ALL", "All Models", "", 1),
        ],
        default="ACTIVE",
    )
    visible_only: bpy.props.BoolProperty(
        name="Visible Only",
        description="Only show visible items",
        default=False,
    )

    def draw_item(self, context, layout, _data, item, _icon, _active_data, _active_propname, _index):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.split(factor=0.5, align=True)
            item_prop = getattr(item, self.prop_name)
            row.prop(item_prop, "name_j", text="", emboss=False, icon=self.icon)
            row = row.row(align=True)
            row.prop(item_prop, "name_e", text="", emboss=True)
            self.draw_item_special(context, row, item)
        elif self.layout_type in {"GRID"}:
            layout.alignment = "CENTER"
            layout.label(text="", icon=self.icon)

    def draw_filter(self, context, layout):
        row = layout.row(align=True)
        row.prop(self, "model_filter", expand=True)
        row.prop(self, "visible_only", text="", toggle=True, icon="RESTRICT_VIEW_OFF")

    def filter_items(self, context, data, propname):
        objects = getattr(data, propname)
        flt_flags = [~self.bitflag_filter_item] * len(objects)
        flt_neworder = list(range(len(objects)))

        if self.model_filter == "ACTIVE":
            active_root = FnCore.find_root_object(context.active_object)
            for i, obj in enumerate(objects):
                if obj.mmd_type == self.mmd_type and FnCore.find_root_object(obj) == active_root:
                    flt_flags[i] = self.bitflag_filter_item
        else:
            for i, obj in enumerate(objects):
                if obj.mmd_type == self.mmd_type:
                    flt_flags[i] = self.bitflag_filter_item

        if self.visible_only:
            for i, obj in enumerate(objects):
                if obj.hide_get() and flt_flags[i] == self.bitflag_filter_item:
                    flt_flags[i] = ~self.bitflag_filter_item

        indices = (i for i, x in enumerate(flt_flags) if x == self.bitflag_filter_item)
        for i_new, i_orig in enumerate(sorted(indices, key=lambda k: objects[k].name)):
            flt_neworder[i_orig] = i_new
        return flt_flags, flt_neworder
