# Copyright 2021 MMD Tools authors
# This file is part of MMD Tools.

import bpy

from . import PT_PanelBase


class MMDToolsSceneSetupPanel(PT_PanelBase, bpy.types.Panel):
    bl_idname = "OBJECT_PT_mmd_tools_scene_setup"
    bl_label = "Scene Setup"
    bl_order = 1

    __LANGUAGE_MANUAL_URL = {
        "ja_JP": "https://mmd-blender.fandom.com/ja/wiki/MMD_Tools/%E3%83%9E%E3%83%8B%E3%83%A5%E3%82%A2%E3%83%AB",
    }

    def draw(self, context: bpy.types.Context):
        self.layout.row(align=True).operator("wm.url_open", text="MMD Tools/Manual", icon="URL").url = self.__LANGUAGE_MANUAL_URL.get(context.preferences.view.language, "https://mmd-blender.fandom.com/wiki/MMD_Tools/Manual")

        self.draw_io()
        self.draw_timeline(context)
        self.draw_rigid_body(context)

    def draw_io(self):
        row = self.layout.row()
        col = row.column(align=True)
        col.label(text="Model:", icon="OUTLINER_OB_ARMATURE")
        col.operator("mmd_tools.import_model", text="Import")
        col.operator("mmd_tools.export_pmx", text="Export")

        col = row.column(align=True)
        col.label(text="Motion:", icon="ANIM")
        col.operator("mmd_tools.import_vmd", text="Import")
        col.operator("mmd_tools.export_vmd", text="Export")

        col = row.column(align=True)
        col.label(text="Pose:", icon="POSE_HLT")
        col.operator("mmd_tools.import_vpd", text="Import")
        col.operator("mmd_tools.export_vpd", text="Export")

    def draw_timeline(self, context):
        col = self.layout.column(align=True)
        row = col.row(align=False)
        row.label(text="Timeline:", icon="TIME")
        row.prop(context.scene, "frame_current")
        row = col.row(align=True)
        row.prop(context.scene, "frame_start", text="Start")
        row.prop(context.scene, "frame_end", text="End")

    def draw_rigid_body(self, context):
        rigidbody_world = context.scene.rigidbody_world

        layout = self.layout
        col = layout.column(align=True)
        row = col.row(align=False)
        row.label(text="Rigid Body Physics:", icon="PHYSICS")
        row.row().operator("mmd_tools.rigid_body_world_update", text="Update World", icon="NONE" if getattr(rigidbody_world, "substeps_per_frame", 0) == 6 else "ERROR")

        if rigidbody_world:
            row = col.row(align=True)
            row.prop(rigidbody_world, "substeps_per_frame", text="Substeps")
            row.prop(rigidbody_world, "solver_iterations", text="Iterations")

            point_cache = rigidbody_world.point_cache

            col = layout.column(align=True)
            row = col.row(align=True)
            row.enabled = not point_cache.is_baked
            row.prop(point_cache, "frame_start")
            row.prop(point_cache, "frame_end")

            row = col.row(align=True)
            if point_cache.is_baked is True:
                row.operator("mmd_tools.ptcache_rigid_body_delete_bake", text="Delete Bake")
            else:
                row.operator("mmd_tools.ptcache_rigid_body_bake", text="Bake")
