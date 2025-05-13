# Copyright 2023 MMD Tools authors
# This file is part of MMD Tools.

import bpy

from .operators import fileio, misc, model, rigid_body, view


class MMDFileImportMenu(bpy.types.Menu):
    bl_idname = "TOPBAR_MT_mmd_file_import"
    bl_label = "MMD UuuNyaa"

    def draw(self, _):
        pass

    @staticmethod
    def draw_menu(this: bpy.types.Menu, _):
        this.layout.operator(fileio.ImportPmx.bl_idname, text="MikuMikuDance Model (.pmd, .pmx)", icon="OUTLINER_OB_ARMATURE")
        this.layout.operator(fileio.ImportVmd.bl_idname, text="MikuMikuDance Motion (.vmd)", icon="ANIM")
        this.layout.operator(fileio.ImportVpd.bl_idname, text="Vocaloid Pose Data (.vpd)", icon="POSE_HLT")

    @staticmethod
    def register():
        bpy.types.TOPBAR_MT_file_import.append(MMDFileImportMenu.draw_menu)

    @staticmethod
    def unregister():
        bpy.types.TOPBAR_MT_file_import.remove(MMDFileImportMenu.draw_menu)


class MMDFileExportMenu(bpy.types.Menu):
    bl_idname = "TOPBAR_MT_mmd_file_export"
    bl_label = "MMD UuuNyaa"

    def draw(self, _):
        pass

    @staticmethod
    def draw_menu(this: bpy.types.Menu, _):
        this.layout.operator(fileio.ExportPmx.bl_idname, text="MikuMikuDance Model (.pmx)", icon="OUTLINER_OB_ARMATURE")
        this.layout.operator(fileio.ExportVmd.bl_idname, text="MikuMikuDance Motion (.vmd)", icon="ANIM")
        this.layout.operator(fileio.ExportVpd.bl_idname, text="Vocaloid Pose Data (.vpd)", icon="POSE_HLT")

    @staticmethod
    def register():
        bpy.types.TOPBAR_MT_file_export.append(MMDFileExportMenu.draw_menu)

    @staticmethod
    def unregister():
        bpy.types.TOPBAR_MT_file_export.remove(MMDFileExportMenu.draw_menu)


class MMDArmatureAddMenu(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_mmd_armature_add"
    bl_label = "MMD UuuNyaa"

    def draw(self, _):
        pass

    @staticmethod
    def draw_menu(this: bpy.types.Menu, _):
        this.layout.operator(model.CreateMMDModelRoot.bl_idname, text="Create MMD Model", icon="OUTLINER_OB_ARMATURE")

    @staticmethod
    def register():
        bpy.types.VIEW3D_MT_armature_add.append(MMDArmatureAddMenu.draw_menu)

    @staticmethod
    def unregister():
        bpy.types.VIEW3D_MT_armature_add.remove(MMDArmatureAddMenu.draw_menu)


class MMDObjectMenu(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_mmd_object"
    bl_label = "MMD UuuNyaa"

    def draw(self, _):
        pass

    @staticmethod
    def draw_menu(this: bpy.types.Menu, _):
        this.layout.separator()
        this.layout.operator(misc.CleanShapeKeys.bl_idname, text="Clean Shape Keys", icon="SHAPEKEY_DATA")

    @staticmethod
    def register():
        bpy.types.VIEW3D_MT_object.append(MMDObjectMenu.draw_menu)

    @staticmethod
    def unregister():
        bpy.types.VIEW3D_MT_object.remove(MMDObjectMenu.draw_menu)


class MMDSelectObjectMenu(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_mmd_select_object"
    bl_label = "MMD UuuNyaa"

    def draw(self, _):
        pass

    @staticmethod
    def draw_menu(this: bpy.types.Menu, _):
        this.layout.separator()
        this.layout.operator_context = "EXEC_DEFAULT"
        this.layout.operator(rigid_body.SelectRigidBody.bl_idname, text="Select MMD Rigid Body").properties = {"collision_group_number", "shape"}

    @staticmethod
    def register():
        bpy.types.VIEW3D_MT_select_object.append(MMDSelectObjectMenu.draw_menu)

    @staticmethod
    def unregister():
        bpy.types.VIEW3D_MT_select_object.remove(MMDSelectObjectMenu.draw_menu)


class MMDPoseMenu(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_mmd_pose"
    bl_label = "MMD UuuNyaa"

    def draw(self, _):
        pass

    @staticmethod
    def draw_menu(this: bpy.types.Menu, _):
        this.layout.operator(view.FlipPose.bl_idname, text="MMD Flip Pose", icon="ARROW_LEFTRIGHT")

    @staticmethod
    def register():
        bpy.types.VIEW3D_MT_pose.append(MMDPoseMenu.draw_menu)
        bpy.types.VIEW3D_MT_pose_context_menu.append(MMDPoseMenu.draw_menu)

    @staticmethod
    def unregister():
        bpy.types.VIEW3D_MT_pose_context_menu.remove(MMDPoseMenu.draw_menu)
        bpy.types.VIEW3D_MT_pose.remove(MMDPoseMenu.draw_menu)
