# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

import math
from typing import Optional

import bpy

from ..bpyutils import FnContext, Props


class FnCamera:
    @staticmethod
    def find_root(obj: bpy.types.Object) -> Optional[bpy.types.Object]:
        if obj is None:
            return None
        if FnCamera.is_mmd_camera_root(obj):
            return obj
        if obj.parent is not None and FnCamera.is_mmd_camera_root(obj.parent):
            return obj.parent
        return None

    @staticmethod
    def is_mmd_camera(obj: bpy.types.Object) -> bool:
        return obj.type == "CAMERA" and FnCamera.find_root(obj.parent) is not None

    @staticmethod
    def is_mmd_camera_root(obj: bpy.types.Object) -> bool:
        return obj.type == "EMPTY" and obj.mmd_type == "CAMERA"

    @staticmethod
    def add_drivers(camera_object: bpy.types.Object):
        def __add_driver(id_data: bpy.types.ID, data_path: str, expression: str, index: int = -1):
            d = id_data.driver_add(data_path, index).driver
            d.type = "SCRIPTED"
            if "$empty_distance" in expression:
                v = d.variables.new()
                v.name = "empty_distance"
                v.type = "TRANSFORMS"
                v.targets[0].id = camera_object
                v.targets[0].transform_type = "LOC_Y"
                v.targets[0].transform_space = "LOCAL_SPACE"
                expression = expression.replace("$empty_distance", v.name)
            if "$is_perspective" in expression:
                v = d.variables.new()
                v.name = "is_perspective"
                v.type = "SINGLE_PROP"
                v.targets[0].id_type = "OBJECT"
                v.targets[0].id = camera_object.parent
                v.targets[0].data_path = "mmd_camera.is_perspective"
                expression = expression.replace("$is_perspective", v.name)
            if "$angle" in expression:
                v = d.variables.new()
                v.name = "angle"
                v.type = "SINGLE_PROP"
                v.targets[0].id_type = "OBJECT"
                v.targets[0].id = camera_object.parent
                v.targets[0].data_path = "mmd_camera.angle"
                expression = expression.replace("$angle", v.name)
            if "$sensor_height" in expression:
                v = d.variables.new()
                v.name = "sensor_height"
                v.type = "SINGLE_PROP"
                v.targets[0].id_type = "CAMERA"
                v.targets[0].id = camera_object.data
                v.targets[0].data_path = "sensor_height"
                expression = expression.replace("$sensor_height", v.name)

            d.expression = expression

        __add_driver(camera_object.data, "ortho_scale", "25*abs($empty_distance)/45")
        __add_driver(camera_object, "rotation_euler", "pi if $is_perspective == False and $empty_distance > 1e-5 else 0", index=1)
        __add_driver(camera_object.data, "type", "not $is_perspective")
        __add_driver(camera_object.data, "lens", "$sensor_height/tan($angle/2)/2")

    @staticmethod
    def remove_drivers(camera_object: bpy.types.Object):
        camera_object.data.driver_remove("ortho_scale")
        camera_object.driver_remove("rotation_euler")
        camera_object.data.driver_remove("ortho_scale")
        camera_object.data.driver_remove("lens")


class MigrationFnCamera:
    @staticmethod
    def update_mmd_camera():
        for camera_object in bpy.data.objects:
            if camera_object.type != "CAMERA":
                continue

            root_object = FnCamera.find_root(camera_object)
            if root_object is None:
                # It's not a MMD Camera
                continue

            FnCamera.remove_drivers(camera_object)
            FnCamera.add_drivers(camera_object)


class MMDCamera:
    def __init__(self, obj):
        root_object = FnCamera.find_root(obj)
        if root_object is None:
            raise ValueError("%s is not MMDCamera" % str(obj))

        self.__emptyObj = getattr(root_object, "original", obj)

    @staticmethod
    def isMMDCamera(obj: bpy.types.Object) -> bool:
        return FnCamera.find_root(obj) is not None

    @staticmethod
    def addDrivers(cameraObj: bpy.types.Object):
        FnCamera.add_drivers(cameraObj)

    @staticmethod
    def removeDrivers(cameraObj: bpy.types.Object):
        if cameraObj.type != "CAMERA":
            return
        FnCamera.remove_drivers(cameraObj)

    @staticmethod
    def convertToMMDCamera(cameraObj: bpy.types.Object, scale=1.0):
        if FnCamera.is_mmd_camera(cameraObj):
            return MMDCamera(cameraObj)

        empty = bpy.data.objects.new(name="MMD_Camera", object_data=None)
        FnContext.link_object(FnContext.ensure_context(), empty)

        cameraObj.parent = empty
        cameraObj.data.sensor_fit = "VERTICAL"
        cameraObj.data.lens_unit = "MILLIMETERS"  # MILLIMETERS, FOV
        cameraObj.data.ortho_scale = 25 * scale
        cameraObj.data.clip_end = 500 * scale
        setattr(cameraObj.data, Props.display_size, 5 * scale)
        cameraObj.location = (0, -45 * scale, 0)
        cameraObj.rotation_mode = "XYZ"
        cameraObj.rotation_euler = (math.radians(90), 0, 0)
        cameraObj.lock_location = (True, False, True)
        cameraObj.lock_rotation = (True, True, True)
        cameraObj.lock_scale = (True, True, True)
        cameraObj.data.dof.focus_object = empty
        FnCamera.add_drivers(cameraObj)

        empty.location = (0, 0, 10 * scale)
        empty.rotation_mode = "YXZ"
        setattr(empty, Props.empty_display_size, 5 * scale)
        empty.lock_scale = (True, True, True)
        empty.mmd_type = "CAMERA"
        empty.mmd_camera.angle = math.radians(30)
        empty.mmd_camera.persp = True
        return MMDCamera(empty)

    @staticmethod
    def newMMDCameraAnimation(cameraObj, cameraTarget=None, scale=1.0, min_distance=0.1):
        scene = bpy.context.scene
        mmd_cam = bpy.data.objects.new(name="Camera", object_data=bpy.data.cameras.new("Camera"))
        FnContext.link_object(FnContext.ensure_context(), mmd_cam)
        MMDCamera.convertToMMDCamera(mmd_cam, scale=scale)
        mmd_cam_root = mmd_cam.parent

        _camera_override_func = None
        if cameraObj is None:
            if scene.camera is None:
                scene.camera = mmd_cam
                return MMDCamera(mmd_cam_root)
            _camera_override_func = lambda: scene.camera

        _target_override_func = None
        if cameraTarget is None:
            _target_override_func = lambda camObj: camObj.data.dof.focus_object or camObj

        action_name = mmd_cam_root.name
        parent_action = bpy.data.actions.new(name=action_name)
        distance_action = bpy.data.actions.new(name=action_name + "_dis")
        FnCamera.remove_drivers(mmd_cam)

        from math import atan

        from mathutils import Matrix, Vector

        render = scene.render
        factor = (render.resolution_y * render.pixel_aspect_y) / (render.resolution_x * render.pixel_aspect_x)
        matrix_rotation = Matrix(([1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]))
        neg_z_vector = Vector((0, 0, -1))
        frame_start, frame_end, frame_current = scene.frame_start, scene.frame_end + 1, scene.frame_current
        frame_count = frame_end - frame_start
        frames = range(frame_start, frame_end)

        fcurves = []
        for i in range(3):
            fcurves.append(parent_action.fcurves.new(data_path="location", index=i))  # x, y, z
        for i in range(3):
            fcurves.append(parent_action.fcurves.new(data_path="rotation_euler", index=i))  # rx, ry, rz
        fcurves.append(parent_action.fcurves.new(data_path="mmd_camera.angle"))  # fov
        fcurves.append(parent_action.fcurves.new(data_path="mmd_camera.is_perspective"))  # persp
        fcurves.append(distance_action.fcurves.new(data_path="location", index=1))  # dis
        for c in fcurves:
            c.keyframe_points.add(frame_count)

        for f, x, y, z, rx, ry, rz, fov, persp, dis in zip(frames, *(c.keyframe_points for c in fcurves)):
            scene.frame_set(f)
            if _camera_override_func:
                cameraObj = _camera_override_func()
            if _target_override_func:
                cameraTarget = _target_override_func(cameraObj)
            cam_matrix_world = cameraObj.matrix_world
            cam_target_loc = cameraTarget.matrix_world.translation
            cam_rotation = (cam_matrix_world @ matrix_rotation).to_euler(mmd_cam_root.rotation_mode)
            cam_vec = cam_matrix_world.to_3x3() @ neg_z_vector
            if cameraObj.data.type == "ORTHO":
                cam_dis = -(9 / 5) * cameraObj.data.ortho_scale
                if cameraObj.data.sensor_fit != "VERTICAL":
                    if cameraObj.data.sensor_fit == "HORIZONTAL":
                        cam_dis *= factor
                    else:
                        cam_dis *= min(1, factor)
            else:
                target_vec = cam_target_loc - cam_matrix_world.translation
                cam_dis = -max(target_vec.length * cam_vec.dot(target_vec.normalized()), min_distance)
            cam_target_loc = cam_matrix_world.translation - cam_vec * cam_dis

            tan_val = cameraObj.data.sensor_height / cameraObj.data.lens / 2
            if cameraObj.data.sensor_fit != "VERTICAL":
                ratio = cameraObj.data.sensor_width / cameraObj.data.sensor_height
                if cameraObj.data.sensor_fit == "HORIZONTAL":
                    tan_val *= factor * ratio
                else:  # cameraObj.data.sensor_fit == 'AUTO'
                    tan_val *= min(ratio, factor * ratio)

            x.co, y.co, z.co = ((f, i) for i in cam_target_loc)
            rx.co, ry.co, rz.co = ((f, i) for i in cam_rotation)
            dis.co = (f, cam_dis)
            fov.co = (f, 2 * atan(tan_val))
            persp.co = (f, cameraObj.data.type != "ORTHO")
            persp.interpolation = "CONSTANT"
            for kp in (x, y, z, rx, ry, rz, fov, dis):
                kp.interpolation = "LINEAR"

        FnCamera.add_drivers(mmd_cam)
        mmd_cam_root.animation_data_create().action = parent_action
        mmd_cam.animation_data_create().action = distance_action
        scene.frame_set(frame_current)
        return MMDCamera(mmd_cam_root)

    def object(self):
        return self.__emptyObj

    def camera(self):
        for i in self.__emptyObj.children:
            if i.type == "CAMERA":
                return i
        raise KeyError
