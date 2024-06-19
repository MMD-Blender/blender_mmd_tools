# -*- coding: utf-8 -*-
# Copyright 2018 MMD Tools authors
# This file is part of MMD Tools.

from typing import Set

import bpy
from bpy.types import Operator

from ..core import FnCore
from ..core.sdef import FnSDEF


def _get_target_objects(context):
    root_objects: Set[bpy.types.Object] = set()
    selected_objects: Set[bpy.types.Object] = set()
    for i in context.selected_objects:
        if i.type == "MESH":
            selected_objects.add(i)
            continue

        root_object = FnCore.find_root_object(i)
        if root_object is None:
            continue
        if root_object in root_objects:
            continue

        root_objects.add(root_object)

        selected_objects |= set(FnCore.iterate_mesh_objects(root_object))
    return selected_objects, root_objects


class ResetSDEFCache(Operator):
    bl_idname = "mmd_tools.sdef_cache_reset"
    bl_label = "Reset MMD SDEF cache"
    bl_description = "Reset MMD SDEF cache of selected objects and clean unused cache"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        target_meshes, _ = _get_target_objects(context)
        for i in target_meshes:
            FnSDEF.clear_cache(i)
        FnSDEF.clear_cache(unused_only=True)
        return {"FINISHED"}


class BindSDEF(Operator):
    bl_idname = "mmd_tools.sdef_bind"
    bl_label = "Bind SDEF Driver"
    bl_description = "Bind MMD SDEF data of selected objects"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    mode: bpy.props.EnumProperty(
        name="Mode",
        description="Select mode",
        items=[
            ("2", "Bulk", "Speed up with numpy (may be slower in some cases)", 2),
            ("1", "Normal", "Normal mode", 1),
            ("0", "- Auto -", "Select best mode by benchmark result", 0),
        ],
        default="0",
    )
    use_skip: bpy.props.BoolProperty(
        name="Skip",
        description="Skip when the bones are not moving",
        default=True,
    )
    use_scale: bpy.props.BoolProperty(
        name="Scale",
        description="Support bone scaling (slow)",
        default=False,
    )

    def invoke(self, context, event):
        vm = context.window_manager
        return vm.invoke_props_dialog(self)

    # TODO: Utility Functionalize
    def execute(self, context):
        target_meshes, root_objects = _get_target_objects(context)

        for r in root_objects:
            r.mmd_root.use_sdef = True

        param = ((None, False, True)[int(self.mode)], self.use_skip, self.use_scale)
        count = sum(FnSDEF.bind(i, *param) for i in target_meshes)
        self.report({"INFO"}, f"Binded {count} of {len(target_meshes)} selected mesh(es)")
        return {"FINISHED"}


class UnbindSDEF(Operator):
    bl_idname = "mmd_tools.sdef_unbind"
    bl_label = "Unbind SDEF Driver"
    bl_description = "Unbind MMD SDEF data of selected objects"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    # TODO: Utility Functionalize
    def execute(self, context):
        target_meshes, root_objects = _get_target_objects(context)
        for i in target_meshes:
            FnSDEF.unbind(i)

        for r in root_objects:
            r.mmd_root.use_sdef = False

        return {"FINISHED"}
