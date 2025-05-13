# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

import bpy
from bpy.types import Operator

from ..core.bone import FnBone
from ..core.model import FnModel, Model
from ..utils import ItemMoveOp, ItemOp, selectSingleBone


class AddDisplayItemFrame(Operator):
    bl_idname = "mmd_tools.display_item_frame_add"
    bl_label = "Add Display Item Frame"
    bl_description = "Add a display item frame to the list"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        mmd_root = root.mmd_root

        frames = mmd_root.display_item_frames
        item, index = ItemOp.add_after(frames, max(1, mmd_root.active_display_item_frame))
        item.name = "Display Frame"
        mmd_root.active_display_item_frame = index
        return {"FINISHED"}


class RemoveDisplayItemFrame(Operator):
    bl_idname = "mmd_tools.display_item_frame_remove"
    bl_label = "Remove Display Item Frame"
    bl_description = "Remove active display item frame from the list"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        mmd_root = root.mmd_root

        index = mmd_root.active_display_item_frame
        frames = mmd_root.display_item_frames
        frame = ItemOp.get_by_index(frames, index)
        if frame and frame.is_special:
            frame.data.clear()
            frame.active_item = 0
        else:
            frames.remove(index)
            mmd_root.active_display_item_frame = min(len(frames) - 1, max(2, index - 1))
        return {"FINISHED"}


class MoveDisplayItemFrame(Operator, ItemMoveOp):
    bl_idname = "mmd_tools.display_item_frame_move"
    bl_label = "Move Display Item Frame"
    bl_description = "Move active display item frame up/down in the list"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        mmd_root = root.mmd_root

        index = mmd_root.active_display_item_frame
        frames = mmd_root.display_item_frames
        frame = ItemOp.get_by_index(frames, index)
        if frame and frame.is_special:
            pass
        else:
            mmd_root.active_display_item_frame = self.move(frames, index, self.type, index_min=2)
        return {"FINISHED"}


class AddDisplayItem(Operator):
    bl_idname = "mmd_tools.display_item_add"
    bl_label = "Add Display Item"
    bl_description = "Add a display item to the list"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        mmd_root = root.mmd_root
        frame = ItemOp.get_by_index(mmd_root.display_item_frames, mmd_root.active_display_item_frame)
        if frame is None:
            return {"CANCELLED"}

        if frame.name == "表情":
            morph = ItemOp.get_by_index(getattr(mmd_root, mmd_root.active_morph_type), mmd_root.active_morph)
            morph_name = morph.name if morph else "Morph Item"
            self._add_item(frame, "MORPH", morph_name, mmd_root.active_morph_type)
        else:
            if context.active_bone:
                bone_names = [context.active_bone.name]
                if context.selected_bones:
                    bone_names += [b.name for b in context.selected_bones]
                if context.selected_editable_bones:
                    bone_names += [b.name for b in context.selected_editable_bones]
                if context.selected_pose_bones:
                    bone_names += [b.name for b in context.selected_pose_bones]
                bone_names = sorted(list(set(bone_names)))
                for bone_name in bone_names:
                    self._add_item(frame, "BONE", bone_name)
            else:
                self._add_item(frame, "BONE", "Bone Item")
        return {"FINISHED"}

    def _add_item(self, frame, item_type, item_name, morph_type=None):
        items = frame.data
        item, index = ItemOp.add_after(items, frame.active_item)
        item.type = item_type
        item.name = item_name
        if morph_type:
            item.morph_type = morph_type
        frame.active_item = index


class RemoveDisplayItem(Operator):
    bl_idname = "mmd_tools.display_item_remove"
    bl_label = "Remove Display Item"
    bl_description = "Remove display item(s) from the list"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    all: bpy.props.BoolProperty(
        name="All",
        description="Delete all display items",
        default=False,
        options={"SKIP_SAVE"},
    )

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        mmd_root = root.mmd_root
        frame = ItemOp.get_by_index(mmd_root.display_item_frames, mmd_root.active_display_item_frame)
        if frame is None:
            return {"CANCELLED"}
        if self.all:
            frame.data.clear()
            frame.active_item = 0
        else:
            frame.data.remove(frame.active_item)
            frame.active_item = max(0, frame.active_item - 1)
        return {"FINISHED"}


class MoveDisplayItem(Operator, ItemMoveOp):
    bl_idname = "mmd_tools.display_item_move"
    bl_label = "Move Display Item"
    bl_description = "Move active display item up/dowm in the list"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        mmd_root = root.mmd_root
        frame = ItemOp.get_by_index(mmd_root.display_item_frames, mmd_root.active_display_item_frame)
        if frame is None:
            return {"CANCELLED"}
        frame.active_item = self.move(frame.data, frame.active_item, self.type)
        return {"FINISHED"}


class FindDisplayItem(Operator):
    bl_idname = "mmd_tools.display_item_find"
    bl_label = "Find Display Item"
    bl_description = "Find the display item of active bone or morph"
    bl_options = {"INTERNAL"}

    type: bpy.props.EnumProperty(
        name="Type",
        description="Find type",
        items=[
            ("BONE", "Find Bone Item", "Find active bone in Display Panel", 0),
            ("MORPH", "Find Morph Item", "Find active morph of Morph Tools Panel in Display Panel", 1),
        ],
        default="BONE",
    )

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        mmd_root = root.mmd_root
        if self.type == "MORPH":
            morph_type = mmd_root.active_morph_type
            morph = ItemOp.get_by_index(getattr(mmd_root, morph_type), mmd_root.active_morph)
            if morph is None:
                return {"CANCELLED"}

            morph_name = morph.name

            def __check(item):
                return item.type == "MORPH" and item.name == morph_name and item.morph_type == morph_type

            self._find_display_item(mmd_root, __check)
        else:
            if context.active_bone is None:
                return {"CANCELLED"}

            bone_name = context.active_bone.name

            def __check(item):
                return item.type == "BONE" and item.name == bone_name

            self._find_display_item(mmd_root, __check)
        return {"FINISHED"}

    def _find_display_item(self, mmd_root, check_func=None):
        for i, frame in enumerate(mmd_root.display_item_frames):
            for j, item in enumerate(frame.data):
                if check_func(item):
                    mmd_root.active_display_item_frame = i
                    frame.active_item = j
                    return


class SelectCurrentDisplayItem(Operator):
    bl_idname = "mmd_tools.display_item_select_current"
    bl_label = "Select Current Display Item"
    bl_description = "Select the bone or morph assigned to the display item"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        mmd_root = root.mmd_root
        frame = ItemOp.get_by_index(mmd_root.display_item_frames, mmd_root.active_display_item_frame)
        if frame is None:
            return {"CANCELLED"}
        item = ItemOp.get_by_index(frame.data, frame.active_item)
        if item is None:
            return {"CANCELLED"}

        if item.type == "MORPH":
            morphs = getattr(mmd_root, item.morph_type)
            index = morphs.find(item.name)
            if index >= 0:
                mmd_root.active_morph_type = item.morph_type
                mmd_root.active_morph = index
        else:
            selectSingleBone(context, FnModel.find_armature_object(root), item.name)
        return {"FINISHED"}


class DisplayItemQuickSetup(Operator):
    bl_idname = "mmd_tools.display_item_quick_setup"
    bl_label = "Display Item Quick Setup"
    bl_description = "Quick setup display items"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    type: bpy.props.EnumProperty(
        name="Type",
        description="Select type",
        items=[
            ("RESET", "Reset", "Clear all items and frames, reset to default", "X", 0),
            ("FACIAL", "Load Facial Items", "Load all morphs to faical frame", "SHAPEKEY_DATA", 1),
            ("GROUP_LOAD", "Sync from Bone Collections", "Sync armature's bone collections to display item frames", "GROUP_BONE", 2),
            ("GROUP_APPLY", "Sync to Bone Collections", "Sync display item frames to armature's bone collections", "GROUP_BONE", 3),
        ],
        default="FACIAL",
    )

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        rig = Model(root)
        if self.type == "RESET":
            rig.initialDisplayFrames()
        elif self.type == "FACIAL":
            rig.initialDisplayFrames(reset=False)  # ensure default frames
            self.load_facial_items(root.mmd_root)
        elif self.type == "GROUP_LOAD":
            FnBone.sync_display_item_frames_from_bone_collections(rig.armature())
            rig.initialDisplayFrames(reset=False)  # ensure default frames
        elif self.type == "GROUP_APPLY":
            FnBone.sync_bone_collections_from_display_item_frames(rig.armature())
        return {"FINISHED"}

    @staticmethod
    def load_facial_items(mmd_root):
        item_list = []
        item_list.extend(("vertex_morphs", i.name) for i in mmd_root.vertex_morphs)
        item_list.extend(("bone_morphs", i.name) for i in mmd_root.bone_morphs)
        item_list.extend(("material_morphs", i.name) for i in mmd_root.material_morphs)
        item_list.extend(("uv_morphs", i.name) for i in mmd_root.uv_morphs)
        item_list.extend(("group_morphs", i.name) for i in mmd_root.group_morphs)

        frames = mmd_root.display_item_frames
        frame = frames["表情"]
        facial_items = frame.data
        mmd_root.active_display_item_frame = frames.find(frame.name)

        # keep original item order
        old = tuple((i.morph_type, i.name) for i in facial_items)
        item_list.sort(key=lambda x: old.index(x) if x in old else len(old))

        ItemOp.resize(facial_items, len(item_list))
        for item, data in zip(facial_items, item_list):
            item.type = "MORPH"
            item.morph_type, item.name = data
        frame.active_item = 0
