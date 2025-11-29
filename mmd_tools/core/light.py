# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

import bpy

from ..bpyutils import FnContext, Props


class MMDLight:
    def __init__(self, obj):
        if MMDLight.isLight(obj):
            obj = obj.parent
        if obj and obj.type == "EMPTY" and obj.mmd_type == "LIGHT":
            self.__emptyObj = obj
        else:
            raise ValueError(f"{str(obj)} is not MMDLight")

    @staticmethod
    def isLight(obj):
        return obj and obj.type == "LIGHT"

    @staticmethod
    def isMMDLight(obj):
        if MMDLight.isLight(obj):
            obj = obj.parent
        return obj and obj.type == "EMPTY" and obj.mmd_type == "LIGHT"

    @staticmethod
    def convertToMMDLight(lightObj, scale=1.0):
        if MMDLight.isMMDLight(lightObj):
            return MMDLight(lightObj)

        empty = bpy.data.objects.new(name="MMD_Light", object_data=None)
        FnContext.link_object(FnContext.ensure_context(), empty)

        empty.rotation_mode = "XYZ"
        empty.lock_rotation = (True, True, True)
        setattr(empty, Props.empty_display_size, 0.4)
        empty.scale = [10 * scale] * 3
        empty.mmd_type = "LIGHT"
        empty.location = (0, 0, 11 * scale)

        lightObj.parent = empty
        lightObj.data.color = (0.602, 0.602, 0.602)
        lightObj.location = (0.5, -0.5, 1.0)
        lightObj.rotation_mode = "XYZ"
        lightObj.rotation_euler = (0, 0, 0)
        lightObj.lock_rotation = (True, True, True)

        constraint = lightObj.constraints.new(type="TRACK_TO")
        constraint.name = "mmd_light_track"
        constraint.target = empty
        constraint.track_axis = "TRACK_NEGATIVE_Z"
        constraint.up_axis = "UP_Y"

        return MMDLight(empty)

    def object(self):
        return self.__emptyObj

    def light(self):
        for i in self.__emptyObj.children:
            if MMDLight.isLight(i):
                return i
        raise KeyError
