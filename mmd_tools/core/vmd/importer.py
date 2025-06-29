# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

import logging
import math
import os
from typing import Union

import bpy
from mathutils import Quaternion, Vector

from ... import utils
from .. import vmd
from ..camera import MMDCamera
from ..lamp import MMDLamp


class _MirrorMapper:
    def __init__(self, data_map=None):
        from ...operators.view import FlipPose

        self.__data_map = data_map
        self.__flip_name = FlipPose.flip_name

    def get(self, name, default=None):
        return self.__data_map.get(self.__flip_name(name), None) or self.__data_map.get(name, default)

    @staticmethod
    def get_location(location):
        return (-location[0], location[1], location[2])

    @staticmethod
    def get_rotation(rotation_xyzw):
        return (rotation_xyzw[0], -rotation_xyzw[1], -rotation_xyzw[2], rotation_xyzw[3])

    @staticmethod
    def get_rotation3(rotation_xyz):
        return (rotation_xyz[0], -rotation_xyz[1], -rotation_xyz[2])


class RenamedBoneMapper:
    def __init__(self, armObj=None, rename_LR_bones=True, use_underscore=False, translator=None):
        self.__pose_bones = armObj.pose.bones if armObj else None
        self.__rename_LR_bones = rename_LR_bones
        self.__use_underscore = use_underscore
        self.__translator = translator

    def init(self, armObj):
        self.__pose_bones = armObj.pose.bones
        return self

    def get(self, bone_name, default=None):
        if self.__pose_bones is None:
            return default
        bl_bone_name = bone_name
        if self.__rename_LR_bones:
            bl_bone_name = utils.convertNameToLR(bl_bone_name, self.__use_underscore)
        if self.__translator:
            bl_bone_name = self.__translator.translate(bl_bone_name)
        return self.__pose_bones.get(bl_bone_name, default)


class _InterpolationHelper:
    def __init__(self, mat):
        self.__indices = indices = [0, 1, 2]
        sorted_list = sorted((-abs(mat[i][j]), i, j) for i in range(3) for j in range(3))
        _, i, j = sorted_list[0]
        if i != j:
            indices[i], indices[j] = indices[j], indices[i]
        _, i, j = next(k for k in sorted_list if k[1] != i and k[2] != j)
        if indices[i] != j:
            idx = indices.index(j)
            indices[i], indices[idx] = indices[idx], indices[i]

    def convert(self, interpolation_xyz):
        return (interpolation_xyz[i] for i in self.__indices)


class BoneConverter:
    """
    Bone transform converter using float64 manual math.
    Avoids mathutils (float32) and numpy (overhead) for precision and speed.
    Enhanced precision for critical transforms.
    """

    # ================ ORIGINAL IMPLEMENTATION (mathutils-based) ================
    # def __init__(self, pose_bone, scale, invert=False):
    #     mat = pose_bone.bone.matrix_local.to_3x3()
    #     mat[1], mat[2] = mat[2].copy(), mat[1].copy()
    #     self.__mat = mat.transposed()
    #     self.__scale = scale
    #     if invert:
    #         self.__mat.invert()
    #     self.convert_interpolation = _InterpolationHelper(self.__mat).convert
    # def convert_location(self, location):
    #     return (self.__mat @ Vector(location)) * self.__scale
    # def convert_rotation(self, rotation_xyzw):
    #     rot = Quaternion()
    #     rot.x, rot.y, rot.z, rot.w = rotation_xyzw
    #     return Quaternion((self.__mat @ rot.axis) * -1, rot.angle).normalized()
    # ===========================================================================

    def __init__(self, pose_bone, scale, invert=False):
        mat = pose_bone.bone.matrix_local.to_3x3()
        mat[1], mat[2] = mat[2].copy(), mat[1].copy()
        self.__mat = mat.transposed()
        self.__scale = scale
        if invert:
            self.__mat.invert()

        # Pre-compute matrix elements for faster access and higher precision
        # Note: mathutils uses float32 internally, manual calculation preserves float64
        m = self.__mat
        self.__m00, self.__m01, self.__m02 = m[0][0], m[0][1], m[0][2]
        self.__m10, self.__m11, self.__m12 = m[1][0], m[1][1], m[1][2]
        self.__m20, self.__m21, self.__m22 = m[2][0], m[2][1], m[2][2]

        self.convert_interpolation = _InterpolationHelper(self.__mat).convert

    def convert_location(self, location):
        x, y, z = location[0], location[1], location[2]

        result_x = (self.__m00 * x + self.__m01 * y + self.__m02 * z) * self.__scale
        result_y = (self.__m10 * x + self.__m11 * y + self.__m12 * z) * self.__scale
        result_z = (self.__m20 * x + self.__m21 * y + self.__m22 * z) * self.__scale

        return Vector((result_x, result_y, result_z))

    def convert_rotation(self, rotation_xyzw):
        rot = Quaternion()
        rot.x, rot.y, rot.z, rot.w = rotation_xyzw

        axis = rot.axis
        angle = rot.angle

        axis_x, axis_y, axis_z = axis[0], axis[1], axis[2]
        new_axis_x = self.__m00 * axis_x + self.__m01 * axis_y + self.__m02 * axis_z
        new_axis_y = self.__m10 * axis_x + self.__m11 * axis_y + self.__m12 * axis_z
        new_axis_z = self.__m20 * axis_x + self.__m21 * axis_y + self.__m22 * axis_z

        return Quaternion(Vector((-new_axis_x, -new_axis_y, -new_axis_z)), angle).normalized()


class BoneConverterPoseMode:
    def __init__(self, pose_bone, scale, invert=False):
        mat = pose_bone.matrix.to_3x3()
        mat[1], mat[2] = mat[2].copy(), mat[1].copy()
        self.__mat = mat.transposed()
        self.__scale = scale
        self.__mat_rot = pose_bone.matrix_basis.to_3x3()
        self.__mat_loc = self.__mat_rot @ self.__mat
        self.__offset = pose_bone.location.copy()
        self.convert_location = self._convert_location
        self.convert_rotation = self._convert_rotation
        if invert:
            self.__mat.invert()
            self.__mat_rot.invert()
            self.__mat_loc.invert()
            self.convert_location = self._convert_location_inverted
            self.convert_rotation = self._convert_rotation_inverted
        self.convert_interpolation = _InterpolationHelper(self.__mat_loc).convert

    def _convert_location(self, location):
        return self.__offset + (self.__mat_loc @ Vector(location)) * self.__scale

    def _convert_rotation(self, rotation_xyzw):
        rot = Quaternion()
        rot.x, rot.y, rot.z, rot.w = rotation_xyzw
        rot = Quaternion((self.__mat @ rot.axis) * -1, rot.angle)
        return (self.__mat_rot @ rot.to_matrix()).to_quaternion()

    def _convert_location_inverted(self, location):
        return (self.__mat_loc @ (Vector(location) - self.__offset)) * self.__scale

    def _convert_rotation_inverted(self, rotation_xyzw):
        rot = Quaternion()
        rot.x, rot.y, rot.z, rot.w = rotation_xyzw
        rot = (self.__mat_rot @ rot.to_matrix()).to_quaternion()
        return Quaternion((self.__mat @ rot.axis) * -1, rot.angle).normalized()


class _FnBezier:
    @classmethod
    def from_fcurve(cls, kp0, kp1):
        p0, p1, p2, p3 = kp0.co, kp0.handle_right, kp1.handle_left, kp1.co
        # Clamp for using Cardano's cubic formula
        if p1.x > p3.x:
            t = (p3.x - p0.x) / (p1.x - p0.x)
            p1 = (1 - t) * p0 + p1 * t
        if p0.x > p2.x:
            t = (p3.x - p0.x) / (p3.x - p2.x)
            p2 = (1 - t) * p3 + p2 * t
        return cls(p0, p1, p2, p3)

    def __init__(self, p0, p1, p2, p3):  # assuming VMD's bezier or F-Curve's bezier
        # assert(p0.x <= p1.x <= p3.x and p0.x <= p2.x <= p3.x)
        self._p0, self._p1, self._p2, self._p3 = p0, p1, p2, p3

    @property
    def points(self):
        return self._p0, self._p1, self._p2, self._p3

    def split(self, t):
        p0, p1, p2, p3 = self._p0, self._p1, self._p2, self._p3
        p01t = (1 - t) * p0 + t * p1
        p12t = (1 - t) * p1 + t * p2
        p23t = (1 - t) * p2 + t * p3
        p012t = (1 - t) * p01t + t * p12t
        p123t = (1 - t) * p12t + t * p23t
        pt = (1 - t) * p012t + t * p123t
        return _FnBezier(p0, p01t, p012t, pt), _FnBezier(pt, p123t, p23t, p3), pt

    def evaluate(self, t):
        p0, p1, p2, p3 = self._p0, self._p1, self._p2, self._p3
        p01t = (1 - t) * p0 + t * p1
        p12t = (1 - t) * p1 + t * p2
        p23t = (1 - t) * p2 + t * p3
        p012t = (1 - t) * p01t + t * p12t
        p123t = (1 - t) * p12t + t * p23t
        return (1 - t) * p012t + t * p123t

    def split_by_x(self, x):
        return self.split(self.axis_to_t(x))

    def evaluate_by_x(self, x):
        return self.evaluate(self.axis_to_t(x))

    def axis_to_t(self, val, axis=0):
        """Find parameter t using Cardano's cubic formula"""
        p0, p1, p2, p3 = self._p0[axis], self._p1[axis], self._p2[axis], self._p3[axis]
        a = p3 - p0 + 3 * (p1 - p2)
        b = 3 * (p0 - 2 * p1 + p2)
        c = 3 * (p1 - p0)
        d = p0 - val
        return next(self.__find_roots(a, b, c, d))

    def find_critical(self):
        p0, p1, p2, p3 = self._p0.y, self._p1.y, self._p2.y, self._p3.y
        p_min, p_max = (p0, p3) if p0 < p3 else (p3, p0)
        if p1 > p_max or p1 < p_min or p2 > p_max or p2 < p_min:
            a = 3 * (p3 - p0 + 3 * (p1 - p2))
            b = 6 * (p0 - 2 * p1 + p2)
            c = 3 * (p1 - p0)
            yield from self.__find_roots(0, a, b, c)

    @staticmethod
    def __find_roots(a, b, c, d):  # a*t*t*t + b*t*t + c*t + d = 0
        # TODO fix precision errors (ex: t=0 and t=1) and improve performance
        if a == 0:
            if b == 0:
                t = -d / c
                if 0 <= t <= 1:
                    yield t
            else:
                D = c * c - 4 * b * d
                if D < 0:
                    return
                D = D**0.5
                b2 = 2 * b
                t = (-c + D) / b2
                if 0 <= t <= 1:
                    yield t
                t = (-c - D) / b2
                if 0 <= t <= 1:
                    yield t
            return

        def _sqrt3(v):
            return -((-v) ** (1 / 3)) if v < 0 else v ** (1 / 3)

        A = ((b * c / 6 - b * b * b / (27 * a)) / a - d / 2) / a
        B = (c - b * b / (3 * a)) / (3 * a)
        b_3a = -b / (3 * a)
        D = A * A + B * B * B

        if D > 0:
            D = D**0.5
            t = b_3a + _sqrt3(A + D) + _sqrt3(A - D)
            if 0 <= t <= 1:
                yield t
        elif D == 0:
            t = b_3a + _sqrt3(A) * 2
            if 0 <= t <= 1:
                yield t
            t = b_3a - _sqrt3(A)
            if 0 <= t <= 1:
                yield t
        else:
            R = A / (-B * B * B) ** 0.5
            t = b_3a + 2 * (-B) ** 0.5 * math.cos(math.acos(R) / 3)
            if 0 <= t <= 1:
                yield t
            t = b_3a + 2 * (-B) ** 0.5 * math.cos((math.acos(R) + 2 * math.pi) / 3)
            if 0 <= t <= 1:
                yield t
            t = b_3a + 2 * (-B) ** 0.5 * math.cos((math.acos(R) - 2 * math.pi) / 3)
            if 0 <= t <= 1:
                yield t


class HasAnimationData:
    animation_data: bpy.types.AnimData


class VMDImporter:
    def __init__(self, filepath, scale=1.0, bone_mapper=None, use_pose_mode=False, convert_mmd_camera=True, convert_mmd_lamp=True, frame_margin=5, use_mirror=False, always_create_new_action=False, use_NLA=False, detect_camera_changes=True, detect_lamp_changes=True):
        self.__vmdFile = vmd.File()
        self.__vmdFile.load(filepath=filepath)
        logging.debug(str(self.__vmdFile.header))
        self.__scale = scale
        self.__convert_mmd_camera = convert_mmd_camera
        self.__convert_mmd_lamp = convert_mmd_lamp
        self.__bone_mapper = bone_mapper
        self.__bone_util_cls = BoneConverterPoseMode if use_pose_mode else BoneConverter
        self.__frame_start = bpy.context.scene.frame_current
        self.__frame_margin = frame_margin if self.__frame_start == 1 else 0  # Ignore margin if current frame is not 1
        self.__mirror = use_mirror
        self.__always_create_new_action = always_create_new_action
        self.__use_NLA = use_NLA
        self.__detect_camera_changes = detect_camera_changes
        self.__detect_lamp_changes = detect_lamp_changes

    @staticmethod
    def __minRotationDiff(prev_q, curr_q):
        t1 = (prev_q.w - curr_q.w) ** 2 + (prev_q.x - curr_q.x) ** 2 + (prev_q.y - curr_q.y) ** 2 + (prev_q.z - curr_q.z) ** 2
        t2 = (prev_q.w + curr_q.w) ** 2 + (prev_q.x + curr_q.x) ** 2 + (prev_q.y + curr_q.y) ** 2 + (prev_q.z + curr_q.z) ** 2
        # t1 = prev_q.rotation_difference(curr_q).angle
        # t2 = prev_q.rotation_difference(-curr_q).angle
        return -curr_q if t2 < t1 else curr_q

    @staticmethod
    def __setInterpolation(bezier, kp0, kp1):
        # Always use BEZIER to match Blender's default behavior
        kp0.interpolation = "BEZIER"
        kp0.handle_right_type = "FREE"
        kp1.handle_left_type = "FREE"

        d = (kp1.co - kp0.co)
        dy = d.y

        # Reset handles if the value doesn't change much (dy is small enough) or the bezier is linear
        # When dy is small enough, the curve is meaningless and will lose data during import; there's no difference in resetting it
        # When the bezier is linear, the resulting curve is equivalent to the original
        if abs(dy) < 1e-4 or (bezier[0] == bezier[1] and bezier[2] == bezier[3]):
            bezier = [20, 20, 107, 107]

        # Always multiply before dividing to reduce precision errors
        kp0.handle_right = kp0.co + Vector((d.x * bezier[0] / 127.0, d.y * bezier[1] / 127.0))
        kp1.handle_left = kp0.co + Vector((d.x * bezier[2] / 127.0, d.y * bezier[3] / 127.0))

    @staticmethod
    def __fixFcurveHandles(fcurve):
        kp0 = fcurve.keyframe_points[0]
        kp0.handle_left_type = "FREE"
        kp0.handle_left = kp0.co + Vector((-1, 0))
        kp = fcurve.keyframe_points[-1]
        kp.handle_right_type = "FREE"
        kp.handle_right = kp.co + Vector((1, 0))

    @staticmethod
    def __keyframe_insert_inner(fcurves: bpy.types.ActionFCurves, path: str, index: int, frame: float, value: float):
        fcurve = fcurves.find(path, index=index)
        if fcurve is None:
            fcurve = fcurves.new(path, index=index)
        fcurve.keyframe_points.insert(frame, value, options={"FAST"})

    @staticmethod
    def __keyframe_insert(fcurves: bpy.types.ActionFCurves, path: str, frame: float, value: Union[int, float, Vector]):
        if isinstance(value, (int, float)):
            VMDImporter.__keyframe_insert_inner(fcurves, path, 0, frame, value)

        elif isinstance(value, Vector):
            VMDImporter.__keyframe_insert_inner(fcurves, path, 0, frame, value[0])
            VMDImporter.__keyframe_insert_inner(fcurves, path, 1, frame, value[1])
            VMDImporter.__keyframe_insert_inner(fcurves, path, 2, frame, value[2])

        else:
            raise TypeError("Unsupported type: {0}".format(type(value)))

    def __getBoneConverter(self, bone):
        converter = self.__bone_util_cls(bone, self.__scale)
        mode = bone.rotation_mode
        compatible_quaternion = self.__minRotationDiff

        class _ConverterWrap:
            convert_location = converter.convert_location
            convert_interpolation = converter.convert_interpolation
            if mode == "QUATERNION":
                convert_rotation = converter.convert_rotation
                compatible_rotation = compatible_quaternion
            elif mode == "AXIS_ANGLE":

                @staticmethod
                def convert_rotation(rot):
                    (x, y, z), angle = converter.convert_rotation(rot).to_axis_angle()
                    return (angle, x, y, z)

                @staticmethod
                def compatible_rotation(prev, curr):
                    angle, x, y, z = curr
                    if prev[1] * x + prev[2] * y + prev[3] * z < 0:
                        angle, x, y, z = -angle, -x, -y, -z
                    angle_diff = prev[0] - angle
                    if abs(angle_diff) > math.pi:
                        pi_2 = math.pi * 2
                        bias = -0.5 if angle_diff < 0 else 0.5
                        angle += int(bias + angle_diff / pi_2) * pi_2
                    return (angle, x, y, z)

            else:
                @staticmethod
                def convert_rotation(rot):
                    return converter.convert_rotation(rot).to_euler(mode)

                @staticmethod
                def compatible_rotation(prev, curr):
                    return curr.make_compatible(prev) or curr

        return _ConverterWrap

    def __assign_action(self, target: Union[bpy.types.ID, HasAnimationData], action: bpy.types.Action):
        if target.animation_data is None:
            target.animation_data_create()

        if not self.__use_NLA:
            if not self.__always_create_new_action and target.animation_data.action:
                return target.animation_data.action
            target.animation_data.action = action
        else:
            frame_current = bpy.context.scene.frame_current
            target_track: bpy.types.NlaTrack = target.animation_data.nla_tracks.new()
            target_track.name = action.name
            target_strip = target_track.strips.new(action.name, frame_current, action)
            target_strip.blend_type = "COMBINE"

        return action

    def __get_or_create_action(self, target, action_name):
        """Get existing action or create a new one depending on settings."""
        # Handle different target types to find the correct animation_data
        if hasattr(target, "data") and hasattr(target.data, "shape_keys") and target.data.shape_keys:
            animation_data = target.data.shape_keys.animation_data
        else:
            animation_data = getattr(target, "animation_data", None)

        if not self.__always_create_new_action and animation_data and animation_data.action:
            return animation_data.action

        return bpy.data.actions.new(name=action_name)

    def __get_or_create_fcurve(self, action, data_path, index, action_group_name=""):
        """Get existing F-Curve or create a new one."""
        fcurve = action.fcurves.find(data_path, index=index)

        if fcurve is None:
            fcurve = action.fcurves.new(data_path=data_path, index=index, action_group=action_group_name)
        # Ensure F-Curve belongs to the correct action group
        elif action_group_name and (fcurve.group is None or fcurve.group.name != action_group_name):
            # Find or create the action group
            group = None
            for g in action.groups:
                if g.name == action_group_name:
                    group = g
                    break
            if group is None:
                group = action.groups.new(action_group_name)
            fcurve.group = group

        return fcurve

    def __assignToArmature(self, armObj, action_name=None):
        boneAnim = self.__vmdFile.boneAnimation
        logging.info("---- bone animations:%5d  target: %s", len(boneAnim), armObj.name)
        if len(boneAnim) < 1:
            return

        action_name = action_name or armObj.name
        action = self.__get_or_create_action(armObj, action_name)

        extra_frame = 1 if self.__frame_margin > 0 else 0

        pose_bones = armObj.pose.bones
        if self.__bone_mapper:
            pose_bones = self.__bone_mapper(armObj)

        def _identity(i):
            return i

        _loc = _rot = _identity
        if self.__mirror:
            pose_bones = _MirrorMapper(pose_bones)
            _loc, _rot = _MirrorMapper.get_location, _MirrorMapper.get_rotation

        class _Dummy:
            pass

        dummy_keyframe_points = iter(lambda: _Dummy, None)
        prop_rot_map = {"QUATERNION": "rotation_quaternion", "AXIS_ANGLE": "rotation_axis_angle"}

        bone_name_table = {}
        for name, keyFrames in boneAnim.items():
            num_frame = len(keyFrames)
            if num_frame < 1:
                continue
            bone = pose_bones.get(name, None)
            if bone is None:
                logging.warning("WARNING: not found bone %s (%d frames)", name, len(keyFrames))
                continue
            logging.info("(bone) frames:%5d  name: %s", len(keyFrames), name)
            assert bone_name_table.get(bone.name, name) == name
            bone_name_table[bone.name] = name

            fcurves = [dummy_keyframe_points] * 7  # x, y, z, r0, r1, r2, (r3)
            data_path_rot = prop_rot_map.get(bone.rotation_mode, "rotation_euler")
            bone_rotation = getattr(bone, data_path_rot)
            default_values = tuple(bone.location) + tuple(bone_rotation)
            data_path = 'pose.bones["%s"].location' % bone.name
            for axis_i in range(3):
                fcurves[axis_i] = self.__get_or_create_fcurve(action, data_path, axis_i, bone.name)
            data_path = 'pose.bones["%s"].%s' % (bone.name, data_path_rot)
            for axis_i in range(len(bone_rotation)):
                fcurves[3 + axis_i] = self.__get_or_create_fcurve(action, data_path, axis_i, bone.name)

            for i in range(len(default_values)):
                c = fcurves[i]
                original_count = len(c.keyframe_points)
                c.keyframe_points.add(extra_frame + num_frame)
                new_keyframes = c.keyframe_points[original_count:]
                kp_iter = iter(new_keyframes)
                if extra_frame:
                    kp = next(kp_iter)
                    kp.co = (1, default_values[i])
                    kp.interpolation = "LINEAR"
                fcurves[i] = kp_iter

            converter = self.__getBoneConverter(bone)
            prev_rot = bone_rotation if extra_frame else None
            prev_kps, indices = None, tuple(converter.convert_interpolation((0, 16, 32))) + (48,) * len(bone_rotation)
            keyFrames.sort(key=lambda x: x.frame_number)
            for k, x, y, z, r0, r1, r2, r3 in zip(keyFrames, *fcurves, strict=False):
                frame = k.frame_number + self.__frame_start + self.__frame_margin
                loc = converter.convert_location(_loc(k.location))
                curr_rot = converter.convert_rotation(_rot(k.rotation))
                if prev_rot is not None:
                    curr_rot = converter.compatible_rotation(prev_rot, curr_rot)
                    # FIXME the rotation interpolation has slightly different result
                    #   Blender: rot(x) = prev_rot*(1 - bezier(t)) + curr_rot*bezier(t)
                    #       MMD: rot(x) = prev_rot.slerp(curr_rot, factor=bezier(t))
                prev_rot = curr_rot

                x.co = (frame, loc[0])
                y.co = (frame, loc[1])
                z.co = (frame, loc[2])
                r0.co = (frame, curr_rot[0])
                r1.co = (frame, curr_rot[1])
                r2.co = (frame, curr_rot[2])
                r3.co = (frame, curr_rot[-1])

                curr_kps = (x, y, z, r0, r1, r2, r3)
                if prev_kps is not None:
                    interp = k.interp
                    for idx, prev_kp, kp in zip(indices, prev_kps, curr_kps, strict=False):
                        self.__setInterpolation(interp[idx : idx + 16 : 4], prev_kp, kp)
                prev_kps = curr_kps

        for c in action.fcurves:
            self.__fixFcurveHandles(c)

        # property animation
        propertyAnim = self.__vmdFile.propertyAnimation
        if len(propertyAnim) > 0:
            logging.info("---- IK animations:%5d  target: %s", len(propertyAnim), armObj.name)
            for keyFrame in propertyAnim:
                logging.debug("(IK) frame:%5d  list: %s", keyFrame.frame_number, keyFrame.ik_states)
                frame = keyFrame.frame_number + self.__frame_start + self.__frame_margin
                for ikName, enable in keyFrame.ik_states:
                    bone = pose_bones.get(ikName, None)
                    if not bone:
                        continue

                    self.__keyframe_insert(action.fcurves, f'pose.bones["{bone.name}"].mmd_ik_toggle', frame, enable)

        self.__assign_action(armObj, action)

        # Ensure IK toggle state is set based on the first frame of VMD animation
        if len(propertyAnim) > 0:
            # Collect IK states from the first frame
            first_frame_ik_states = {}
            first_frame = float("inf")
            for keyFrame in propertyAnim:
                frame_num = keyFrame.frame_number
                if frame_num <= first_frame:
                    first_frame = frame_num
                    for ikName, enable in keyFrame.ik_states:
                        first_frame_ik_states[ikName] = enable
            # Set the mmd_ik_toggle property for each bone based on the collected first frame IK states
            for ikName, enable in first_frame_ik_states.items():
                bone = pose_bones.get(ikName, None)
                if bone and bone.mmd_ik_toggle != enable:
                    bone.mmd_ik_toggle = enable  # This will trigger the _pose_bone_update_mmd_ik_toggle method

    def __assignToMesh(self, meshObj, action_name=None):
        shapeKeyAnim = self.__vmdFile.shapeKeyAnimation
        logging.info("---- morph animations:%5d  target: %s", len(shapeKeyAnim), meshObj.name)
        if len(shapeKeyAnim) < 1:
            return

        action_name = action_name or meshObj.name
        action = self.__get_or_create_action(meshObj.data.shape_keys, action_name)

        mirror_map = _MirrorMapper(meshObj.data.shape_keys.key_blocks) if self.__mirror else {}
        shapeKeyDict = {k: mirror_map.get(k, v) for k, v in meshObj.data.shape_keys.key_blocks.items()}

        from ...core.model import FnModel

        # Get all available morph names from the model
        root_object = FnModel.find_root_object(meshObj)
        model_morph_names = set()
        if root_object:
            mmd_root = root_object.mmd_root
            # Check all types of morphs in the model
            for morph_type in ["vertex_morphs", "uv_morphs", "bone_morphs", "material_morphs", "group_morphs"]:
                model_morph_names.update(morph.name for morph in getattr(mmd_root, morph_type, []))

        for name, keyFrames in shapeKeyAnim.items():
            if name not in shapeKeyDict:
                # Check if model has this morph registered but not set up
                if name in model_morph_names:
                    # Model has the morph but it's not assembled
                    logging.warning("WARNING: not found shape key %s (%d frames) - model has this morph but needs assembly", name, len(keyFrames))
                else:
                    # Model doesn't have this morph at all
                    logging.warning("WARNING: not found shape key %s (%d frames) - model doesn't have this morph", name, len(keyFrames))
                continue
            logging.info("(mesh) frames:%5d  name: %s", len(keyFrames), name)
            shapeKey = shapeKeyDict[name]
            data_path = 'key_blocks["%s"].value' % shapeKey.name
            fcurve = self.__get_or_create_fcurve(action, data_path, 0)

            original_count = len(fcurve.keyframe_points)
            fcurve.keyframe_points.add(len(keyFrames))
            new_keyframes = fcurve.keyframe_points[original_count:]

            keyFrames.sort(key=lambda x: x.frame_number)
            for k, v in zip(keyFrames, new_keyframes, strict=False):
                v.co = (k.frame_number + self.__frame_start + self.__frame_margin, k.weight)
                v.interpolation = "LINEAR"
            weights = tuple(i.weight for i in keyFrames)
            shapeKey.slider_min = min(shapeKey.slider_min, math.floor(min(weights)))
            shapeKey.slider_max = max(shapeKey.slider_max, math.ceil(max(weights)))

        self.__assign_action(meshObj.data.shape_keys, action)

    def __assignToRoot(self, rootObj, action_name=None):
        propertyAnim = self.__vmdFile.propertyAnimation
        logging.info("---- display animations:%5d  target: %s", len(propertyAnim), rootObj.name)
        if len(propertyAnim) < 1:
            return

        action_name = action_name or rootObj.name
        action = self.__get_or_create_action(rootObj, action_name)

        logging.debug("(Display) list(frame, show): %s", [(keyFrame.frame_number, bool(keyFrame.visible)) for keyFrame in propertyAnim])
        for keyFrame in propertyAnim:
            self.__keyframe_insert(action.fcurves, "mmd_root.show_meshes", keyFrame.frame_number + self.__frame_start + self.__frame_margin, float(keyFrame.visible))

        self.__assign_action(rootObj, action)

    @staticmethod
    def detectCameraChange(fcurve):
        frames = list(fcurve.keyframe_points)
        frameCount = len(frames)
        frames.sort(key=lambda x: x.co[0])
        for i, f in enumerate(frames):
            if i + 1 < frameCount:
                n = frames[i + 1]
                if n.co[0] - f.co[0] <= 1.0:
                    f.interpolation = "CONSTANT"

    def __assignToCamera(self, cameraObj, action_name=None):
        mmdCameraInstance = MMDCamera.convertToMMDCamera(cameraObj, self.__scale)
        mmdCamera = mmdCameraInstance.object()
        cameraObj = mmdCameraInstance.camera()

        cameraAnim = self.__vmdFile.cameraAnimation
        logging.info("(camera) frames:%5d  name: %s", len(cameraAnim), mmdCamera.name)
        if len(cameraAnim) < 1:
            return

        action_name = action_name or mmdCamera.name
        parent_action = self.__get_or_create_action(mmdCamera, action_name)
        distance_action = self.__get_or_create_action(cameraObj, action_name + "_dis")

        def _identity(i):
            return i

        _loc = _rot = _identity
        if self.__mirror:
            _loc, _rot = _MirrorMapper.get_location, _MirrorMapper.get_rotation3

        fcurves = []
        for i in range(3):
            fcurves.append(self.__get_or_create_fcurve(parent_action, "location", i))  # x, y, z
        for i in range(3):
            fcurves.append(self.__get_or_create_fcurve(parent_action, "rotation_euler", i))  # rx, ry, rz
        fcurves.append(self.__get_or_create_fcurve(parent_action, "mmd_camera.angle", 0))  # fov
        fcurves.append(self.__get_or_create_fcurve(parent_action, "mmd_camera.is_perspective", 0))  # persp
        fcurves.append(self.__get_or_create_fcurve(distance_action, "location", 1))  # dis

        new_keyframe_iterators = []
        for c in fcurves:
            original_count = len(c.keyframe_points)
            c.keyframe_points.add(len(cameraAnim))
            new_keyframes = c.keyframe_points[original_count:]
            new_keyframe_iterators.append(iter(new_keyframes))

        prev_kps, indices = None, (0, 8, 4, 12, 12, 12, 16, 20)  # x, z, y, rx, ry, rz, dis, fov
        cameraAnim.sort(key=lambda x: x.frame_number)
        for k, x, y, z, rx, ry, rz, fov, persp, dis in zip(cameraAnim, *new_keyframe_iterators, strict=False):
            frame = k.frame_number + self.__frame_start + self.__frame_margin
            x.co, z.co, y.co = ((frame, val * self.__scale) for val in _loc(k.location))
            rx.co, rz.co, ry.co = ((frame, val) for val in _rot(k.rotation))
            fov.co = (frame, math.radians(k.angle))
            dis.co = (frame, k.distance * self.__scale)
            persp.co = (frame, k.persp)

            persp.interpolation = "CONSTANT"
            curr_kps = (x, y, z, rx, ry, rz, dis, fov)
            if prev_kps is not None:
                interp = k.interp
                for idx, prev_kp, kp in zip(indices, prev_kps, curr_kps, strict=False):
                    # TODO: Optimize this bottleneck: __setInterpolation is called per keypoint; should batch set interpolation instead
                    self.__setInterpolation(interp[idx : idx + 4 : 2] + interp[idx + 1 : idx + 4 : 2], prev_kp, kp)
            prev_kps = curr_kps

        for fcurve in fcurves:
            self.__fixFcurveHandles(fcurve)
            if self.__detect_camera_changes:
                self.detectCameraChange(fcurve)

        self.__assign_action(mmdCamera, parent_action)
        self.__assign_action(cameraObj, distance_action)

    @staticmethod
    def detectLampChange(fcurve):
        frames = list(fcurve.keyframe_points)
        frameCount = len(frames)
        frames.sort(key=lambda x: x.co[0])
        for i, f in enumerate(frames):
            f.interpolation = "LINEAR"
            if i + 1 < frameCount:
                n = frames[i + 1]
                if n.co[0] - f.co[0] <= 1.0:
                    f.interpolation = "CONSTANT"

    def __assignToLamp(self, lampObj, action_name=None):
        mmdLampInstance = MMDLamp.convertToMMDLamp(lampObj, self.__scale)
        mmdLamp = mmdLampInstance.object()
        lampObj = mmdLampInstance.lamp()

        lampAnim = self.__vmdFile.lampAnimation
        logging.info("(lamp) frames:%5d  name: %s", len(lampAnim), mmdLamp.name)
        if len(lampAnim) < 1:
            return

        action_name = action_name or mmdLamp.name
        color_action = self.__get_or_create_action(lampObj.data, action_name + "_color")
        location_action = self.__get_or_create_action(lampObj, action_name + "_loc")

        def _identity(i):
            return i

        _loc = _MirrorMapper.get_location if self.__mirror else _identity
        for keyFrame in lampAnim:
            frame = keyFrame.frame_number + self.__frame_start + self.__frame_margin
            self.__keyframe_insert(color_action.fcurves, "color", frame, Vector(keyFrame.color))
            self.__keyframe_insert(location_action.fcurves, "location", frame, Vector(_loc(keyFrame.direction)).xzy * -1)

        if self.__detect_lamp_changes:
            for fcurve in location_action.fcurves:
                self.detectLampChange(fcurve)

        self.__assign_action(lampObj.data, color_action)
        self.__assign_action(lampObj, location_action)

    def assign(self, obj, action_name=None):
        if obj is None:
            return
        if action_name is None:
            action_name = os.path.splitext(os.path.basename(self.__vmdFile.filepath))[0]

        if MMDCamera.isMMDCamera(obj):
            self.__assignToCamera(obj, action_name + "_camera")
        elif MMDLamp.isMMDLamp(obj):
            self.__assignToLamp(obj, action_name + "_lamp")
        elif getattr(obj.data, "shape_keys", None):
            self.__assignToMesh(obj, action_name + "_facial")
        elif obj.type == "ARMATURE":
            self.__assignToArmature(obj, action_name + "_bone")
        elif obj.type == "CAMERA" and self.__convert_mmd_camera:
            self.__assignToCamera(obj, action_name + "_camera")
        elif obj.type == "LIGHT" and self.__convert_mmd_lamp:
            self.__assignToLamp(obj, action_name + "_lamp")
        elif obj.mmd_type == "ROOT":
            self.__assignToRoot(obj, action_name + "_display")
        else:
            pass
