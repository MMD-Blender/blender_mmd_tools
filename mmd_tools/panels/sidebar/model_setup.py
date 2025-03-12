# -*- coding: utf-8 -*-
# Copyright 2021 MMD Tools authors
# This file is part of MMD Tools.

import time

import bpy

from ...core import FnCore
from ...core.sdef import FnSDEF
from . import PT_PanelBase


class MMDToolsModelSetupPanel(PT_PanelBase, bpy.types.Panel):
    bl_idname = "OBJECT_PT_mmd_tools_model_setup"
    bl_label = "Model Setup"
    bl_order = 2

    def draw(self, context: bpy.types.Context):
        active_object: bpy.types.Object = context.active_object
        mmd_root_object = FnCore.find_root_object(active_object)

        if mmd_root_object is None:
            self.layout.label(text="Select a MMD Model")
            return

        col = self.layout.column(align=True)
        col.label(text=mmd_root_object.mmd_root.name, icon="OUTLINER_OB_ARMATURE")

        self.draw_visibility(context, mmd_root_object)
        self.draw_assembly(context, mmd_root_object)
        self.draw_ik_toggle(context, mmd_root_object)
        self.draw_mesh(context, mmd_root_object)
        self.draw_material(context, mmd_root_object)
        self.draw_misc(context, mmd_root_object)

    def draw_visibility(self, context, mmd_root_object):
        col = self.layout.column(align=True)
        row = col.row(align=False)
        row.label(text="Visibility:", icon="HIDE_OFF")
        row.operator("mmd_tools.reset_object_visibility", text="Reset")

        mmd_root = mmd_root_object.mmd_root
        row = col.row(align=False)
        cell = row.row(align=True)
        cell.prop(mmd_root, "show_meshes", toggle=True, text="Mesh", icon="MESH_DATA")
        cell.prop(mmd_root, "show_armature", toggle=True, text="Armature", icon="ARMATURE_DATA")
        cell.prop(mmd_root, "show_temporary_objects", toggle=True, text="Temporary Object", icon="EMPTY_AXIS")
        cell = row.row(align=True)
        cell.prop(mmd_root, "show_rigid_bodies", toggle=True, text="Rigid Body", icon="RIGID_BODY")
        cell.prop(mmd_root, "show_names_of_rigid_bodies", toggle=True, icon_only=True, icon="SHORTDISPLAY")
        cell = row.row(align=True)
        cell.prop(mmd_root, "show_joints", toggle=True, text="Joint", icon="RIGID_BODY_CONSTRAINT")
        cell.prop(mmd_root, "show_names_of_joints", toggle=True, icon_only=True, icon="SHORTDISPLAY")

    def draw_assembly(self, context, mmd_root_object):
        col = self.layout.column(align=False)
        row = col.row(align=True)
        row.label(text="Assembly:", icon="MODIFIER_ON")

        grid = col.grid_flow(row_major=True)

        row = grid.row(align=True)
        row.operator("mmd_tools.assemble_all", text="All", icon="SETTINGS")
        row.operator("mmd_tools.disassemble_all", text="", icon="TRASH")

        row = grid.row(align=True)
        row.operator("mmd_tools.sdef_bind", text="SDEF", icon="MOD_SIMPLEDEFORM")
        if len(FnSDEF.g_verts) > 0:
            row.operator("mmd_tools.sdef_cache_reset", text="", icon="FILE_REFRESH")
        row.operator("mmd_tools.sdef_unbind", text="", icon="TRASH")

        row = grid.row(align=True)
        row.operator("mmd_tools.apply_additional_transform", text="Bone", icon="CONSTRAINT_BONE")
        row.operator("mmd_tools.clean_additional_transform", text="", icon="TRASH")

        row = grid.row(align=True)
        row.operator("mmd_tools.morph_slider_setup", text="Morph", icon="SHAPEKEY_DATA").type = "BIND"
        row.operator("mmd_tools.morph_slider_setup", text="", icon="TRASH").type = "UNBIND"

        row = grid.row(align=True)
        row.active = getattr(context.scene.rigidbody_world, "enabled", False)

        mmd_root = mmd_root_object.mmd_root
        if not mmd_root.is_built:
            row.operator("mmd_tools.build_rig", text="Physics", icon="PHYSICS", depress=False)
        else:
            row.operator("mmd_tools.clean_rig", text="Physics", icon="PHYSICS", depress=True)

        row = grid.row(align=True)
        row.prop(mmd_root, "use_property_driver", text="Property", toggle=True, icon="DRIVER")

    __toggle_items_ttl = 0.0
    __toggle_items_cache = None

    def __get_toggle_items(self, mmd_root_object: bpy.types.Object):
        if self.__toggle_items_ttl > time.time():
            return self.__toggle_items_cache

        self.__toggle_items_ttl = time.time() + 10
        self.__toggle_items_cache = []
        armature_object = FnCore.find_armature_object(mmd_root_object)
        pose_bones = armature_object.pose.bones
        ik_map = {pose_bones[c.subtarget]: (b.bone, c.chain_count, not c.is_valid) for b in pose_bones for c in b.constraints if c.type == "IK" and c.subtarget in pose_bones}

        if not ik_map:
            return self.__toggle_items_cache

        base = sum(b.bone.length for b in ik_map.keys()) / len(ik_map) * 0.8

        groups = {}
        for ik, (b, cnt, err) in ik_map.items():
            if any(c.is_visible for c in ik.bone.collections):
                px, py, pz = -ik.bone.head_local / base
                bx, by, bz = -b.head_local / base * 0.15
                groups.setdefault((int(pz), int(bz), int(px**2), -cnt), set()).add(((px, -py, bx), ik))  # (px, pz, -py, bx, bz, -by)

        for _, group in sorted(groups.items()):
            for _, ik in sorted(group, key=lambda x: x[0]):
                ic = "ERROR" if ik_map[ik][-1] else "NONE"
                self.__toggle_items_cache.append((ik, ic))

        return self.__toggle_items_cache

    def draw_ik_toggle(self, _context, mmd_root_object):
        col = self.layout.column(align=True)
        row = col.row(align=False)
        row.label(text="IK Toggle:", icon="CON_KINEMATIC")
        grid = col.grid_flow(row_major=True, align=True)

        for ik, ic in self.__get_toggle_items(mmd_root_object):
            grid.row(align=True).prop(ik, "mmd_ik_toggle", text=ik.name, toggle=True, icon=ic)

    def draw_mesh(self, context, mmd_root_object):
        col = self.layout.column(align=True)
        col.label(text="Mesh:", icon="MESH_DATA")
        grid = col.grid_flow(row_major=True, align=True)
        grid.row(align=True).operator("mmd_tools.separate_by_materials", text="Separate by Materials", icon="MOD_EXPLODE")
        grid.row(align=True).operator("mmd_tools.join_meshes", text="Join", icon="MESH_CUBE")

    def draw_material(self, context, mmd_root_object):
        col = self.layout.column(align=True)
        col.label(text="Material:", icon="MATERIAL")

        grid = col.grid_flow(row_major=True, align=False)
        row = grid.row(align=True)
        row.prop(mmd_root_object.mmd_root, "use_toon_texture", text="Toon Texture", toggle=True, icon="SHADING_RENDERED")
        row.prop(mmd_root_object.mmd_root, "use_sphere_texture", text="Sphere Texture", toggle=True, icon="MATSPHERE")
        row = grid.row(align=True)
        row.operator("mmd_tools.edge_preview_setup", text="Edge Preview", icon="ANTIALIASED").action = "CREATE"
        row.operator("mmd_tools.edge_preview_setup", text="", icon="TRASH").action = "CLEAN"
        row = grid.row(align=True)
        row.operator("mmd_tools.convert_materials", text="Convert to Blender", icon="BLENDER")
        row.operator('mmd_tools.convert_bsdf_materials', text='Convert to MMD', icon='MATSPHERE')

    def draw_misc(self, context, mmd_root_object):
        col = self.layout.column(align=True)
        col.label(text="Misc:", icon="TOOL_SETTINGS")
        grid = col.grid_flow(row_major=True)
        grid.row(align=True).operator("mmd_tools.global_translation_popup", text="(Experimental) Global Translation")
        grid.row(align=True).operator("mmd_tools.change_mmd_ik_loop_factor", text="Change MMD IK Loop Factor")
        grid.row(align=True).operator("mmd_tools.clean_duplicated_material_morphs")
