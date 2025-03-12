# -*- coding: utf-8 -*-
# Copyright 2016 MMD Tools authors
# This file is part of MMD Tools.

import bpy

from ...core import FnCore
from . import PT_ProductionPanelBase


class MMDBoneOrder(PT_ProductionPanelBase, bpy.types.Panel):
    bl_idname = "OBJECT_PT_mmd_tools_bone_order"
    bl_label = "Bone Order"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 5

    def draw(self, context):
        layout = self.layout
        active_obj = context.active_object
        root = FnCore.find_root_object(active_obj)
        if root is None:
            layout.label(text="Select a MMD Model")
            return

        armature = FnCore.find_armature_object(root)
        if armature is None:
            layout.label(text="The armature object of active MMD model can't be found", icon="ERROR")
            return

        bone_order_mesh_object = FnCore.find_bone_order_mesh_object(root)
        bone_count = MMD_TOOLS_UL_ModelBones.update_bone_tables(armature, bone_order_mesh_object)

        col = layout.column(align=True)
        row = col.row()
        if bone_order_mesh_object is None:
            row.template_list("MMD_TOOLS_UL_ModelBones", "", armature.pose, "bones", root.vertex_groups, "active_index")
            col.operator("mmd_tools.object_select", text="(%d) %s" % (bone_count, armature.name), icon="OUTLINER_OB_ARMATURE", emboss=False).name = armature.name
            col.label(text='No mesh object with "mmd_bone_order_override" modifier', icon="ERROR")
        else:
            row.template_list("MMD_TOOLS_UL_ModelBones", "", bone_order_mesh_object, "vertex_groups", bone_order_mesh_object.vertex_groups, "active_index")

            tb = row.column()
            tb.enabled = bone_order_mesh_object == active_obj
            tb1 = tb.column(align=True)
            tb1.menu("OBJECT_MT_mmd_tools_bone_order_menu", text="", icon="DOWNARROW_HLT")
            tb.separator()
            tb1 = tb.column(align=True)
            tb1.operator("object.vertex_group_move", text="", icon="TRIA_UP").direction = "UP"
            tb1.operator("object.vertex_group_move", text="", icon="TRIA_DOWN").direction = "DOWN"

            row = col.row()
            row.operator("mmd_tools.object_select", text="(%d) %s" % (bone_count, armature.name), icon="OUTLINER_OB_ARMATURE", emboss=False).name = armature.name
            row.label(icon="BACK")
            row.operator("mmd_tools.object_select", text=bone_order_mesh_object.name, icon="OBJECT_DATA", emboss=False).name = bone_order_mesh_object.name


class _DummyVertexGroup:
    index = None

    def __init__(self, index):
        self.index = index


class MMD_TOOLS_UL_ModelBones(bpy.types.UIList):
    _IK_MAP = {}
    _IK_BONES = {}
    _DUMMY_VERTEX_GROUPS = {}

    @classmethod
    def __wrap_pose_bones(cls, pose_bones):
        for i, b in enumerate(pose_bones):
            cls._DUMMY_VERTEX_GROUPS[b.name] = _DummyVertexGroup(i)
            yield b

    @classmethod
    def update_bone_tables(cls, armature, bone_order_object):
        cls._IK_MAP.clear()
        cls._IK_BONES.clear()
        cls._DUMMY_VERTEX_GROUPS.clear()

        ik_target_override = {}
        ik_target_custom = {}
        ik_target_fin = {}
        pose_bones = armature.pose.bones
        bone_count = len(pose_bones)
        pose_bone_list = pose_bones if bone_order_object else cls.__wrap_pose_bones(pose_bones)

        for b in pose_bone_list:
            if b.is_mmd_shadow_bone:
                bone_count -= 1
                continue
            for c in b.constraints:
                if c.type == "IK" and c.subtarget in pose_bones and c.subtarget not in cls._IK_BONES:
                    if not c.use_tail:
                        cls._IK_MAP.setdefault(hash(b), []).append(c.subtarget)
                        cls._IK_BONES[c.subtarget] = ik_target_fin[c.subtarget] = hash(b)
                        bone_chain = b.parent_recursive
                    else:
                        cls._IK_BONES[c.subtarget] = b.name
                        bone_chain = [b] + b.parent_recursive
                    for l in bone_chain[: c.chain_count]:
                        cls._IK_MAP.setdefault(hash(l), []).append(c.subtarget)
                if "mmd_ik_target_custom" == c.name:
                    ik_target_custom[getattr(c, "subtarget", "")] = hash(b)
                elif "mmd_ik_target_override" == c.name and b.parent:
                    if b.parent.name == getattr(c, "subtarget", ""):
                        for c in b.parent.constraints:
                            if c.type == "IK" and c.subtarget in pose_bones and c.subtarget not in ik_target_override and c.subtarget not in ik_target_custom:
                                ik_target_override[c.subtarget] = hash(b)

        for k, v in ik_target_custom.items():
            if k not in ik_target_fin and k in cls._IK_BONES:
                cls._IK_BONES[k] = v
                cls._IK_MAP.setdefault(v, []).append(k)
                if k in ik_target_override:
                    del ik_target_override[k]

        for k, v in ik_target_override.items():
            if k not in ik_target_fin and k in cls._IK_BONES:
                cls._IK_BONES[k] = v
                cls._IK_MAP.setdefault(v, []).append(k)

        for k, v in tuple(cls._IK_BONES.items()):
            if isinstance(v, str):
                b = cls.__get_ik_target_bone(pose_bones[v])
                if b:
                    cls._IK_BONES[k] = hash(b)
                    cls._IK_MAP.setdefault(hash(b), []).append(k)
                else:
                    del cls._IK_BONES[k]
        return bone_count

    @staticmethod
    def __get_ik_target_bone(target_bone):
        r = None
        min_length = None
        for c in (c for c in target_bone.children if not c.is_mmd_shadow_bone):
            if c.bone.use_connect:
                return c
            length = (c.head - target_bone.tail).length
            if min_length is None or length < min_length:
                min_length = length
                r = c
        return r

    @classmethod
    def _draw_bone_item(cls, layout, bone_name, pose_bones, vertex_groups, index):
        bone = pose_bones.get(bone_name, None)
        if not bone or bone.is_mmd_shadow_bone:
            layout.active = False
            layout.label(text=bone_name, translate=False, icon="GROUP_BONE" if bone else "MESH_DATA")
            r = layout.row()
            r.alignment = "RIGHT"
            r.label(text=str(index))
        else:
            row = layout.split(factor=0.45, align=False)
            r0 = row.row()
            r0.label(text=bone_name, translate=False, icon="POSE_HLT" if bone_name in cls._IK_BONES else "BONE_DATA")
            r = r0.row()
            r.alignment = "RIGHT"
            r.label(text=str(index))

            row_sub = row.split(factor=0.67, align=False)

            mmd_bone = bone.mmd_bone
            count = len(pose_bones)
            bone_transform_rank = index + mmd_bone.transform_order * count

            r = row_sub.row()
            bone_parent = bone.parent
            if bone_parent:
                bone_parent = bone_parent.name
                idx = vertex_groups.get(bone_parent, _DummyVertexGroup).index
                if idx is None or bone_transform_rank < (idx + pose_bones[bone_parent].mmd_bone.transform_order * count):
                    r.label(text=str(idx), icon="ERROR")
                else:
                    r.label(text=str(idx), icon="INFO" if index < idx else "FILE_PARENT")
            else:
                r.label()

            r = r.row()
            if mmd_bone.has_additional_rotation:
                append_bone = mmd_bone.additional_transform_bone
                idx = vertex_groups.get(append_bone, _DummyVertexGroup).index
                if idx is None or bone_transform_rank < (idx + pose_bones[append_bone].mmd_bone.transform_order * count):
                    if append_bone:
                        r.label(text=str(idx), icon="ERROR")
                else:
                    r.label(text=str(idx), icon="IPO_QUAD" if mmd_bone.has_additional_location else "IPO_EXPO")
            elif mmd_bone.has_additional_location:
                append_bone = mmd_bone.additional_transform_bone
                idx = vertex_groups.get(append_bone, _DummyVertexGroup).index
                if idx is None or bone_transform_rank < (idx + pose_bones[append_bone].mmd_bone.transform_order * count):
                    if append_bone:
                        r.label(text=str(idx), icon="ERROR")
                else:
                    r.label(text=str(idx), icon="IPO_LINEAR")

            for idx, b in sorted(((vertex_groups.get(b, _DummyVertexGroup).index, b) for b in cls._IK_MAP.get(hash(bone), ())), key=lambda i: i[0] or 0):
                ik_bone = pose_bones[b]
                is_ik_chain = hash(bone) != cls._IK_BONES.get(b)
                if idx is None or (is_ik_chain and bone_transform_rank > (idx + ik_bone.mmd_bone.transform_order * count)):
                    r.prop(ik_bone, "mmd_ik_toggle", text=str(idx), toggle=True, icon="ERROR")
                elif b not in cls._IK_BONES:
                    r.prop(ik_bone, "mmd_ik_toggle", text=str(idx), toggle=True, icon="QUESTION")
                else:
                    r.prop(ik_bone, "mmd_ik_toggle", text=str(idx), toggle=True, icon="LINKED" if is_ik_chain else "HOOK")

            row = row_sub.row(align=True)
            if mmd_bone.transform_after_dynamics:
                row.prop(mmd_bone, "transform_after_dynamics", text="", toggle=True, icon="PHYSICS")
            else:
                row.prop(mmd_bone, "transform_after_dynamics", text="", toggle=True)
            row.prop(mmd_bone, "transform_order", text="", slider=bool(mmd_bone.transform_order))

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {"DEFAULT"}:
            if self._DUMMY_VERTEX_GROUPS:
                self._draw_bone_item(layout, item.name, data.bones, self._DUMMY_VERTEX_GROUPS, index)
            else:
                self._draw_bone_item(layout, item.name, data.parent.pose.bones, data.vertex_groups, index)
        elif self.layout_type in {"COMPACT"}:
            pass
        elif self.layout_type in {"GRID"}:
            layout.alignment = "CENTER"
            layout.label(text="", icon_value=icon)


class MMDBoneOrderMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_mmd_tools_bone_order_menu"
    bl_label = "Bone Order Menu"

    def draw(self, _context):
        layout = self.layout
        layout.operator("object.vertex_group_sort", text="Sort by Bone Hierarchy", icon="BONE_DATA").sort_type = "BONE_HIERARCHY"
        layout.separator()
        layout.operator("mmd_tools.add_missing_vertex_groups_from_bones", icon="PRESET_NEW")
