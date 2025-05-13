# Copyright 2023 MMD Tools authors
# This file is part of MMD Tools.


import bpy


class MMDHanders:
    @staticmethod
    @bpy.app.handlers.persistent
    def load_hander(_):
        # pylint: disable=import-outside-toplevel
        from .core.sdef import FnSDEF

        FnSDEF.clear_cache()
        FnSDEF.register_driver_function()

        from .core.material import MigrationFnMaterial

        MigrationFnMaterial.update_mmd_shader()

        from .core.morph import MigrationFnMorph

        MigrationFnMorph.update_mmd_morph()

        from .core.camera import MigrationFnCamera

        MigrationFnCamera.update_mmd_camera()

        from .core.model import MigrationFnModel

        MigrationFnModel.update_mmd_ik_loop_factor()
        MigrationFnModel.update_mmd_tools_version()

    @staticmethod
    @bpy.app.handlers.persistent
    def save_pre_handler(_):
        # pylint: disable=import-outside-toplevel
        from .core.morph import MigrationFnMorph

        MigrationFnMorph.compatible_with_old_version_mmd_tools()

    @staticmethod
    def register():
        bpy.app.handlers.load_post.append(MMDHanders.load_hander)
        bpy.app.handlers.save_pre.append(MMDHanders.save_pre_handler)

    @staticmethod
    def unregister():
        bpy.app.handlers.save_pre.remove(MMDHanders.save_pre_handler)
        bpy.app.handlers.load_post.remove(MMDHanders.load_hander)
