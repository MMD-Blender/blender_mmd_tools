# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

from bpy.types import Operator

from .. import auto_scene_setup


class SetFrameRange(Operator):
    bl_idname = "mmd_tools.set_frame_range"
    bl_label = "Set Frame Range"
    bl_description = "Set the frame range to best values to play the animation from start to finish. And set the frame rate to 30.0."
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        auto_scene_setup.setupFrameRanges()
        auto_scene_setup.setupFps()
        return {"FINISHED"}
