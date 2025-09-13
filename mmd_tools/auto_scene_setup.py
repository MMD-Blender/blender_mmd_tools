# Copyright 2013 MMD Tools authors
# This file is part of MMD Tools.

import bpy


def setupFrameRanges():
    base = min(bpy.context.scene.frame_current, bpy.context.scene.frame_start)
    s = base
    e = base

    for action in bpy.data.actions:
        # When create_new_action=False, multiple VMDs share the same action
        # Need to toggle use_frame_range to access frame ranges from both VMDs:
        # use_frame_range = True: gets range from the first imported VMD
        # use_frame_range = False: gets range from the newly imported VMD
        # By toggling twice, we ensure both ranges are captured regardless of initial state
        ts, te = action.frame_range
        s, e = min(s, ts), max(e, te)
        action.use_frame_range = not action.use_frame_range  # Toggle to access the other VMD's range
        ts, te = action.frame_range
        s, e = min(s, ts), max(e, te)
        action.use_frame_range = not action.use_frame_range  # Restore to original state

    bpy.context.scene.frame_start = round(s)
    bpy.context.scene.frame_end = round(e)
    if bpy.context.scene.rigidbody_world is not None:
        bpy.context.scene.rigidbody_world.point_cache.frame_start = round(s)
        bpy.context.scene.rigidbody_world.point_cache.frame_end = round(e)


def setupFps():
    bpy.context.scene.render.fps = 30
    bpy.context.scene.render.fps_base = 1
