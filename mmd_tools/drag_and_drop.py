# -*- coding: utf-8 -*-
# Copyright 2023 MMD Tools authors
# This file is part of MMD Tools.


import bpy


class FH_ImportPmx(bpy.types.FileHandler):
    bl_idname = "FH_IportPmx"
    bl_label = "PMX Import File Handler"
    bl_import_operator = "mmd_tools.import_model"
    bl_file_extensions = ".pmx;.pmd"

    @classmethod
    def poll_drop(cls, context):
        return context.area.type == "VIEW_3D"


class FH_ImportVmd(bpy.types.FileHandler):
    bl_idname = "FH_ImportVmd"
    bl_label = "VMD Import File Handler"
    bl_import_operator = "mmd_tools.import_vmd"
    bl_file_extensions = ".vmd"

    @classmethod
    def poll_drop(cls, context):
        return context.area.type == "VIEW_3D"


class FH_ImportVpd(bpy.types.FileHandler):
    bl_idname = "FH_ImportVpd"
    bl_label = "VPD Import File Handler"
    bl_import_operator = "mmd_tools.import_vpd"
    bl_file_extensions = ".vpd"

    @classmethod
    def poll_drop(cls, context):
        return context.area.type == "VIEW_3D"
