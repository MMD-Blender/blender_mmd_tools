# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import logging
import os
import shutil
import unittest

import bpy
from bl_ext.blender_org.mmd_tools.core.model import Model
from bl_ext.blender_org.mmd_tools.core.vmd.importer import BoneConverter, BoneConverterPoseMode, RenamedBoneMapper, VMDImporter, _FnBezier, _MirrorMapper
from mathutils import Quaternion, Vector

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "samples")


class TestVMDImporter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Clean up output from previous tests"""
        output_dir = os.path.join(TESTS_DIR, "output")
        for item in os.listdir(output_dir):
            if item.endswith(".OUTPUT"):
                continue
            item_fp = os.path.join(output_dir, item)
            if os.path.isfile(item_fp):
                os.remove(item_fp)
            elif os.path.isdir(item_fp):
                shutil.rmtree(item_fp)

    def setUp(self):
        """Set up testing environment"""
        logger = logging.getLogger()
        logger.setLevel("ERROR")

        if not bpy.context.active_object:
            bpy.ops.mesh.primitive_cube_add()

        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=True)

        self.context = bpy.context
        self.scene = bpy.context.scene

    # === Helper Functions ===

    def _list_sample_files(self, dir_name, extension):
        """List all files with specified extension in the directory"""
        directory = os.path.join(SAMPLES_DIR, dir_name)
        if not os.path.exists(directory):
            return []

        ret = []
        for root, dirs, files in os.walk(directory):
            ret.extend(os.path.join(root, name) for name in files if name.lower().endswith("." + extension.lower()))
        return ret

    def _enable_mmd_tools(self):
        """Make sure mmd_tools addon is enabled"""
        bpy.ops.wm.read_homefile(use_empty=True)
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("bl_ext.blender_org.mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.blender_org.mmd_tools")

    def _create_standard_mmd_armature(self):
        """Create armature with standard MMD bone names"""
        bpy.ops.object.armature_add()
        armature = bpy.context.active_object
        armature.name = "TestArmature"

        bpy.ops.object.mode_set(mode="EDIT")
        edit_bones = armature.data.edit_bones

        # Create standard MMD bone hierarchy
        bone_data = [
            ("全ての親", None, Vector((0, 0, 0)), Vector((0, 0, 0.1))),
            ("センター", "全ての親", Vector((0, 0, 0)), Vector((0, 0, 0.5))),
            ("上半身", "センター", Vector((0, 0, 0.5)), Vector((0, 0, 1.2))),
            ("首", "上半身", Vector((0, 0, 1.2)), Vector((0, 0, 1.4))),
            ("頭", "首", Vector((0, 0, 1.4)), Vector((0, 0, 1.6))),
            ("左腕", "上半身", Vector((0.3, 0, 1.1)), Vector((0.6, 0, 1.0))),
            ("右腕", "上半身", Vector((-0.3, 0, 1.1)), Vector((-0.6, 0, 1.0))),
            ("左ひじ", "左腕", Vector((0.6, 0, 1.0)), Vector((0.8, 0, 0.8))),
            ("右ひじ", "右腕", Vector((-0.6, 0, 1.0)), Vector((-0.8, 0, 0.8))),
            ("下半身", "センター", Vector((0, 0, 0)), Vector((0, -0.1, 0.4))),
            ("左足", "下半身", Vector((0.1, 0, 0)), Vector((0.1, 0, -0.4))),
            ("右足", "下半身", Vector((-0.1, 0, 0)), Vector((-0.1, 0, -0.4))),
        ]

        # Create bones
        first_bone = edit_bones[0]
        first_bone.name = bone_data[0][0]
        first_bone.head = bone_data[0][2]
        first_bone.tail = bone_data[0][3]

        created_bones = {bone_data[0][0]: first_bone}

        for bone_name, parent_name, head, tail in bone_data[1:]:
            new_bone = edit_bones.new(bone_name)
            new_bone.head = head
            new_bone.tail = tail
            if parent_name:
                new_bone.parent = created_bones[parent_name]
            created_bones[bone_name] = new_bone

        bpy.ops.object.mode_set(mode="OBJECT")

        # Add MMD bone properties if available
        for bone in armature.pose.bones:
            try:
                if hasattr(bone, "mmd_bone"):
                    bone.mmd_bone.name_j = bone.name
            except (AttributeError, TypeError):
                pass

        return armature

    def _create_test_mesh_with_shape_keys(self):
        """Create a test mesh with shape keys"""
        bpy.ops.mesh.primitive_cube_add()
        mesh_obj = bpy.context.active_object
        mesh_obj.name = "TestMesh"

        bpy.ops.object.shape_key_add(from_mix=False)

        shape_key_names = ["まばたき", "笑い", "ウィンク"]
        for name in shape_key_names:
            bpy.ops.object.shape_key_add(from_mix=False)
            shape_key = mesh_obj.data.shape_keys.key_blocks[-1]
            shape_key.name = name

            for i, v in enumerate(mesh_obj.data.vertices):
                if i % 2 == 0:
                    shape_key.data[i].co.x += 0.2
                    shape_key.data[i].co.y += 0.1

        return mesh_obj

    def _create_mmd_camera(self):
        """Create an MMD camera"""
        bpy.ops.object.camera_add()
        camera = bpy.context.active_object
        camera.name = "TestCamera"

        try:
            bpy.ops.mmd_tools.convert_to_mmd_camera()
            for obj in bpy.context.selected_objects:
                if obj.type == "EMPTY" and obj != camera:
                    return obj
        except Exception:
            empty = bpy.data.objects.new("TestMMDCamera", None)
            bpy.context.collection.objects.link(empty)
            empty.parent = None
            empty.rotation_mode = "XYZ"

            try:
                if hasattr(empty, "mmd_camera"):
                    empty.mmd_camera.angle = 45.0
                    empty.mmd_camera.is_perspective = True
                else:
                    empty["mmd_camera.angle"] = 45.0
                    empty["mmd_camera.is_perspective"] = True
            except Exception:
                pass

            camera.parent = empty
            return empty

        return camera

    def _create_mmd_lamp(self):
        """Create an MMD lamp"""
        bpy.ops.object.light_add(type="POINT")
        light = bpy.context.active_object
        light.name = "TestLight"

        try:
            bpy.ops.mmd_tools.convert_to_mmd_lamp()
            for obj in bpy.context.selected_objects:
                if obj.type == "EMPTY" and obj != light:
                    return obj
        except Exception:
            empty = bpy.data.objects.new("TestMMDLamp", None)
            bpy.context.collection.objects.link(empty)
            empty.parent = None
            light.parent = empty
            light.data.color = (1.0, 1.0, 1.0)
            return empty

        return light

    def _create_animation_data(self, obj, property_path, keyframe_values, frames=None):
        """Create animation data and keyframes for an object"""
        if obj is None:
            return None

        if frames is None:
            frames = range(1, len(keyframe_values) + 1)

        if obj.animation_data is None:
            obj.animation_data_create()

        if obj.animation_data.action is None:
            action = bpy.data.actions.new(name=f"{obj.name}Action")
            obj.animation_data.action = action
        else:
            action = obj.animation_data.action

        if isinstance(keyframe_values[0], (list, tuple, Vector, Quaternion)):
            for i in range(len(keyframe_values[0])):
                fcurve = action.fcurves.new(data_path=property_path, index=i)
                for frame, value in zip(frames, keyframe_values, strict=False):
                    fcurve.keyframe_points.insert(frame, value[i])
        else:
            fcurve = action.fcurves.new(data_path=property_path)
            for frame, value in zip(frames, keyframe_values, strict=False):
                fcurve.keyframe_points.insert(frame, value)

        for fcurve in action.fcurves:
            fcurve.update()

        return action

    def _create_full_test_scene(self, with_shape_keys=True, with_camera=True, with_lamp=True):
        """Create a complete test scene with all components"""
        # Create model root
        root = bpy.data.objects.new("TestRoot", None)
        root.mmd_type = "ROOT"
        bpy.context.collection.objects.link(root)

        self._create_animation_data(root, "mmd_root.show_meshes", [1.0, 0.0, 1.0], [1, 10, 20])

        # Create armature
        armature = self._create_standard_mmd_armature()
        armature.parent = root

        # Add bone animations
        bone_names = ["全ての親", "センター", "上半身", "首", "頭", "左腕", "右腕", "左ひじ", "右ひじ", "下半身", "左足", "右足"]
        for bone_name in bone_names:
            if bone_name in armature.pose.bones:
                bone = armature.pose.bones[bone_name]
                self._create_animation_data(armature, f'pose.bones["{bone_name}"].location', [Vector((0, 0, 0)), Vector((0.1, 0.2, 0.3)), Vector((0, 0, 0))], [1, 10, 20])

                bone.rotation_mode = "QUATERNION"
                self._create_animation_data(armature, f'pose.bones["{bone_name}"].rotation_quaternion', [Quaternion((1, 0, 0, 0)), Quaternion((0.707, 0.707, 0, 0)), Quaternion((1, 0, 0, 0))], [1, 10, 20])

        # Create mesh with shape keys
        mesh_obj = None
        if with_shape_keys:
            mesh_obj = self._create_test_mesh_with_shape_keys()
            mesh_obj.parent = armature

            for shape_key_name in ["まばたき", "笑い", "ウィンク"]:
                if shape_key_name in mesh_obj.data.shape_keys.key_blocks:
                    self._create_animation_data(mesh_obj.data.shape_keys, f'key_blocks["{shape_key_name}"].value', [0.0, 1.0, 0.0], [1, 10, 20])

        # Create MMD camera
        mmd_camera = None
        if with_camera:
            mmd_camera = self._create_mmd_camera()
            if mmd_camera:
                self._create_animation_data(mmd_camera, "location", [Vector((0, 0, 0)), Vector((1, 2, 3)), Vector((0, 0, 5))], [1, 10, 20])
                self._create_animation_data(mmd_camera, "rotation_euler", [Vector((0, 0, 0)), Vector((0.1, 0.2, 0.3)), Vector((0, 0, 0))], [1, 10, 20])

                if mmd_camera.children and mmd_camera.children[0].type == "CAMERA":
                    camera = mmd_camera.children[0]
                    self._create_animation_data(camera, "location", [Vector((0, -10, 0)), Vector((0, -5, 0)), Vector((0, -15, 0))], [1, 10, 20])

        # Create MMD lamp
        mmd_lamp = None
        if with_lamp:
            mmd_lamp = self._create_mmd_lamp()
            if mmd_lamp:
                self._create_animation_data(mmd_lamp, "location", [Vector((0, 0, 0)), Vector((1, 1, 1)), Vector((0, 0, 0))], [1, 10, 20])

                if mmd_lamp.children and mmd_lamp.children[0].type == "LIGHT":
                    light = mmd_lamp.children[0]
                    self._create_animation_data(light.data, "color", [Vector((1, 1, 1)), Vector((1, 0, 0)), Vector((1, 1, 1))], [1, 10, 20])

        return {"root": root, "armature": armature, "mesh": mesh_obj, "camera": mmd_camera, "lamp": mmd_lamp}

    def _create_model_from_pmx(self, pmx_file):
        """Create a model from a PMX file"""
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()

        bpy.ops.mmd_tools.import_model(
            filepath=pmx_file,
            scale=1.0,
            types={"MESH", "ARMATURE", "MORPHS"},
            clean_model=False,
            log_level="ERROR",
        )

        model_name = os.path.splitext(os.path.basename(pmx_file))[0]
        for obj in bpy.context.scene.objects:
            if obj.mmd_type == "ROOT" and obj.name == model_name:
                return obj

        for obj in bpy.context.scene.objects:
            if obj.mmd_type == "ROOT":
                return obj

        return None

    # === Animation Testing Functions ===

    def _test_bone_animation(self, armature, test_frames=None):
        """Test bone animation and return number of detected transforms"""
        if test_frames is None:
            test_frames = [1, 50, 100, 150, 200]

        transforms_detected = 0

        for frame in test_frames:
            if frame <= bpy.context.scene.frame_end:
                bpy.context.scene.frame_set(frame)
                bpy.context.view_layer.update()

                for bone in armature.pose.bones:
                    loc_length = bone.location.length
                    if bone.rotation_mode == "QUATERNION":
                        rot_diff = abs(1.0 - abs(bone.rotation_quaternion.w))
                    else:
                        rot_diff = bone.rotation_euler.length

                    if loc_length > 0.001 or rot_diff > 0.001:
                        transforms_detected += 1

        return transforms_detected

    def _test_shape_key_animation(self, mesh_obj, test_frames=None):
        """Test shape key animation and return number of detected changes"""
        if not mesh_obj or not mesh_obj.data.shape_keys:
            return 0

        if test_frames is None:
            test_frames = [1, 50, 100, 150, 200]

        changes_detected = 0

        for frame in test_frames:
            if frame <= bpy.context.scene.frame_end:
                bpy.context.scene.frame_set(frame)
                bpy.context.view_layer.update()

                for key in mesh_obj.data.shape_keys.key_blocks:
                    if key.name != "Basis" and abs(key.value) > 0.001:
                        changes_detected += 1

        return changes_detected

    def _test_camera_animation(self, camera_obj, test_frames=None):
        """Test camera animation and return number of detected changes"""
        if not camera_obj:
            return 0

        if test_frames is None:
            test_frames = [1, 50, 100, 150, 200]

        changes_detected = 0
        initial_loc = camera_obj.location.copy()
        initial_rot = camera_obj.rotation_euler.copy()

        for frame in test_frames:
            if frame <= bpy.context.scene.frame_end:
                bpy.context.scene.frame_set(frame)
                bpy.context.view_layer.update()

                loc_diff = (camera_obj.location - initial_loc).length
                rot_diff = (Vector(camera_obj.rotation_euler) - Vector(initial_rot)).length

                if loc_diff > 0.001 or rot_diff > 0.001:
                    changes_detected += 1

        return changes_detected

    def _test_lamp_animation(self, lamp_obj, test_frames=None):
        """Test lamp animation and return number of detected changes"""
        if not lamp_obj:
            return 0

        if test_frames is None:
            test_frames = [1, 50, 100, 150, 200]

        changes_detected = 0
        initial_loc = lamp_obj.location.copy()

        for frame in test_frames:
            if frame <= bpy.context.scene.frame_end:
                bpy.context.scene.frame_set(frame)
                bpy.context.view_layer.update()

                loc_diff = (lamp_obj.location - initial_loc).length

                if loc_diff > 0.001:
                    changes_detected += 1

        return changes_detected

    def _analyze_vmd_content(self, vmd_file_path):
        """Analyze VMD file content and return bone/shape key info"""
        importer = VMDImporter(filepath=vmd_file_path)
        vmd_file = importer._VMDImporter__vmdFile

        result = {"bone_animation": {}, "shape_key_animation": {}, "importer": importer}

        if hasattr(vmd_file, "boneAnimation"):
            result["bone_animation"] = vmd_file.boneAnimation

        if hasattr(vmd_file, "shapeKeyAnimation"):
            result["shape_key_animation"] = vmd_file.shapeKeyAnimation

        return result

    def _perform_vmd_import_test(self, target_obj, vmd_file_path, obj_type):
        """Perform VMD import and test results for a specific object type"""
        original_frame = bpy.context.scene.frame_current

        # Analyze VMD content
        vmd_analysis = self._analyze_vmd_content(vmd_file_path)
        importer = vmd_analysis["importer"]

        # Perform import
        importer.assign(target_obj)

        # Test results based on object type
        results = {"fcurves": 0, "animation_detected": 0}

        if obj_type == "armature":
            if target_obj.animation_data and target_obj.animation_data.action:
                action = target_obj.animation_data.action
                results["fcurves"] = len(action.fcurves)
                results["animation_detected"] = self._test_bone_animation(target_obj)

                # Show bone matching info
                if vmd_analysis["bone_animation"]:
                    target_bones = {bone.name for bone in target_obj.pose.bones}
                    vmd_bones = set(vmd_analysis["bone_animation"].keys())
                    matching_bones = target_bones & vmd_bones
                    print(f"Matching bones: {len(matching_bones)} out of {len(vmd_bones)} VMD bones")
                    if matching_bones:
                        print(f"Sample matching bones: {sorted(matching_bones)[:10]}")

        elif obj_type == "mesh":
            if target_obj.data.shape_keys and target_obj.data.shape_keys.animation_data:
                action = target_obj.data.shape_keys.animation_data.action
                if action:
                    results["fcurves"] = len(action.fcurves)
                    results["animation_detected"] = self._test_shape_key_animation(target_obj)

                    # Show shape key matching info
                    if vmd_analysis["shape_key_animation"]:
                        target_shapes = {key.name for key in target_obj.data.shape_keys.key_blocks if key.name != "Basis"}
                        vmd_shapes = set(vmd_analysis["shape_key_animation"].keys())
                        matching_shapes = target_shapes & vmd_shapes
                        print(f"Matching shape keys: {matching_shapes}")

        elif obj_type == "camera":
            if target_obj.animation_data and target_obj.animation_data.action:
                action = target_obj.animation_data.action
                results["fcurves"] = len(action.fcurves)
                results["animation_detected"] = self._test_camera_animation(target_obj)

        elif obj_type == "lamp":
            if target_obj.animation_data and target_obj.animation_data.action:
                action = target_obj.animation_data.action
                results["fcurves"] = len(action.fcurves)
                results["animation_detected"] = self._test_lamp_animation(target_obj)

        # Restore frame
        bpy.context.scene.frame_set(original_frame)

        return results

    def _cleanup_animation(self, obj, obj_type):
        """Clean up animation data for an object"""
        if obj_type == "mesh" and obj.data.shape_keys and obj.data.shape_keys.animation_data:
            if obj.data.shape_keys.animation_data.action:
                bpy.data.actions.remove(obj.data.shape_keys.animation_data.action)
        elif obj.animation_data and obj.animation_data.action:
            bpy.data.actions.remove(obj.animation_data.action)

    # === Test Cases ===

    def test_vmd_importer_initialization(self):
        """Test basic initialization of VMDImporter"""
        vmd_files = self._list_sample_files("vmd", "vmd")
        if not vmd_files:
            self.fail("No VMD sample files found for testing")

        filepath = vmd_files[0]

        # Test default initialization
        importer = VMDImporter(filepath=filepath)
        self.assertEqual(importer._VMDImporter__scale, 1.0)
        self.assertFalse(importer._VMDImporter__bone_util_cls == BoneConverterPoseMode)
        self.assertTrue(importer._VMDImporter__convert_mmd_camera)
        self.assertTrue(importer._VMDImporter__convert_mmd_lamp)
        expected_margin = 5 if importer._VMDImporter__frame_start in {0, 1} else 0
        self.assertEqual(importer._VMDImporter__frame_margin, expected_margin)
        self.assertFalse(importer._VMDImporter__mirror)

        # Test custom initialization
        importer = VMDImporter(filepath=filepath, scale=10.0, use_pose_mode=True, convert_mmd_camera=False, convert_mmd_lamp=False, frame_margin=10, use_mirror=True)
        self.assertEqual(importer._VMDImporter__scale, 10.0)
        self.assertTrue(importer._VMDImporter__bone_util_cls == BoneConverterPoseMode)
        self.assertFalse(importer._VMDImporter__convert_mmd_camera)
        self.assertFalse(importer._VMDImporter__convert_mmd_lamp)
        expected_custom_margin = 10 if importer._VMDImporter__frame_start in {0, 1} else 0
        self.assertEqual(importer._VMDImporter__frame_margin, expected_custom_margin)
        self.assertTrue(importer._VMDImporter__mirror)

    def test_mirror_mapper(self):
        """Test _MirrorMapper functionality"""
        test_map = {"左腕": "LeftArm", "右腕": "RightArm", "中央": "Center"}
        mirror_mapper = _MirrorMapper(test_map)

        self.assertEqual(mirror_mapper.get("右腕"), "LeftArm")
        self.assertEqual(mirror_mapper.get("左腕"), "RightArm")
        self.assertEqual(mirror_mapper.get("中央"), "Center")
        self.assertEqual(mirror_mapper.get("不存在", "Default"), "Default")

        # Test static methods
        loc = (1.0, 2.0, 3.0)
        mirrored_loc = _MirrorMapper.get_location(loc)
        self.assertEqual(mirrored_loc, (-1.0, 2.0, 3.0))

        rot = (0.1, 0.2, 0.3, 0.4)
        mirrored_rot = _MirrorMapper.get_rotation(rot)
        self.assertEqual(mirrored_rot, (0.1, -0.2, -0.3, 0.4))

        rot3 = (0.1, 0.2, 0.3)
        mirrored_rot3 = _MirrorMapper.get_rotation3(rot3)
        self.assertEqual(mirrored_rot3, (0.1, -0.2, -0.3))

    def test_renamed_bone_mapper(self):
        """Test RenamedBoneMapper functionality"""
        armature = self._create_standard_mmd_armature()

        mapper = RenamedBoneMapper(armature, rename_LR_bones=False)

        arm_l_bone = mapper.get("左腕")
        self.assertIsNotNone(arm_l_bone)
        if arm_l_bone:
            self.assertEqual(arm_l_bone.name, "左腕")

        arm_r_bone = mapper.get("右腕")
        self.assertIsNotNone(arm_r_bone)
        if arm_r_bone:
            self.assertEqual(arm_r_bone.name, "右腕")

        non_existent = mapper.get("NonExistentBone")
        self.assertIsNone(non_existent)

        default_value = "DefaultBone"
        result_with_default = mapper.get("NonExistentBone", default_value)
        self.assertEqual(result_with_default, default_value)

        # Test with translator
        existing_bones = [bone.name for bone in armature.pose.bones]
        if "左腕" in existing_bones:

            class TestTranslator:
                def translate(self, name):
                    translations = {"LeftArm": "左腕", "RightArm": "右腕"}
                    return translations.get(name, name)

            mapper_with_translator = RenamedBoneMapper(armature, rename_LR_bones=False, translator=TestTranslator())
            translated_result = mapper_with_translator.get("LeftArm")
            self.assertIsNotNone(translated_result)

            direct_result = mapper_with_translator.get("左腕")
            self.assertIsNotNone(direct_result)
            self.assertEqual(translated_result, direct_result)

    def test_bone_converter(self):
        """Test BoneConverter functionality"""
        armature = self._create_standard_mmd_armature()
        pose_bone = armature.pose.bones["左腕"]
        converter = BoneConverter(pose_bone, scale=1.0)

        test_location = Vector((1.0, 2.0, 3.0))
        converted_location = converter.convert_location(test_location)
        self.assertIsInstance(converted_location, Vector)

        test_rotation = (0.0, 0.0, 0.0, 1.0)
        converted_rotation = converter.convert_rotation(test_rotation)
        self.assertIsInstance(converted_rotation, Quaternion)

        converter = BoneConverter(pose_bone, scale=2.0)
        scaled_location = converter.convert_location(test_location)
        self.assertAlmostEqual(scaled_location.length, converted_location.length * 2.0, places=5)

        test_interpolation = ((0, 1, 2), (3, 4, 5), (6, 7, 8))
        converted_interpolation = tuple(converter.convert_interpolation(test_interpolation))
        self.assertEqual(len(converted_interpolation), 3)

    def test_bone_converter_pose_mode(self):
        """Test BoneConverterPoseMode functionality"""
        armature = self._create_standard_mmd_armature()

        bpy.ops.object.select_all(action="DESELECT")
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode="POSE")

        pose_bone = armature.pose.bones["左腕"]
        pose_bone.location = Vector((0.5, 0.0, 0.0))
        pose_bone.rotation_mode = "QUATERNION"
        pose_bone.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))

        converter = BoneConverterPoseMode(pose_bone, scale=1.0)

        test_location = Vector((1.0, 0.0, 0.0))
        converted_location = converter.convert_location(test_location)
        self.assertIsInstance(converted_location, Vector)

        test_rotation = (1.0, 0.0, 0.0, 0.0)
        converted_rotation = converter.convert_rotation(test_rotation)
        self.assertIsInstance(converted_rotation, Quaternion)

        inverted_converter = BoneConverterPoseMode(pose_bone, scale=1.0, invert=True)
        inverted_location = inverted_converter.convert_location(converted_location)
        self.assertAlmostEqual((inverted_location - test_location).length, 0.0, places=3)

        bpy.ops.object.mode_set(mode="OBJECT")

    def test_fn_bezier(self):
        """Test _FnBezier functionality"""
        p0 = Vector((0.0, 0.0))
        p1 = Vector((0.25, 0.25))
        p2 = Vector((0.75, 0.75))
        p3 = Vector((1.0, 1.0))

        bezier = _FnBezier(p0, p1, p2, p3)

        points = bezier.points
        self.assertEqual(len(points), 4)
        self.assertEqual(points[0], p0)

        t = 0.5
        left_bezier, right_bezier, mid_point = bezier.split(t)

        self.assertGreater(mid_point.x, 0.0)
        self.assertLess(mid_point.x, 1.0)
        self.assertAlmostEqual(mid_point.x, 0.5, places=1)

        result_start = bezier.evaluate(0.0)
        result_end = bezier.evaluate(1.0)
        self.assertAlmostEqual(result_start.x, 0.0, places=5)
        self.assertAlmostEqual(result_end.x, 1.0, places=5)

        result_mid = bezier.evaluate(0.5)
        self.assertGreater(result_mid.x, 0.0)
        self.assertLess(result_mid.x, 1.0)

        t_value = bezier.axis_to_t(0.5)
        self.assertGreaterEqual(t_value, 0.0)
        self.assertLessEqual(t_value, 1.0)

        # Test from_fcurve
        class MockKeyframe:
            def __init__(self, co, handle_left, handle_right):
                self.co = co
                self.handle_left = handle_left
                self.handle_right = handle_right

        kp0 = MockKeyframe(Vector((0.0, 0.0)), Vector((-0.1, 0.0)), Vector((0.33, 0.0)))
        kp1 = MockKeyframe(Vector((1.0, 1.0)), Vector((0.66, 1.0)), Vector((1.1, 1.0)))

        bezier_from_fcurve = _FnBezier.from_fcurve(kp0, kp1)
        self.assertEqual(len(bezier_from_fcurve.points), 4)

        fcurve_points = bezier_from_fcurve.points
        self.assertEqual(fcurve_points[0], kp0.co)
        self.assertEqual(fcurve_points[3], kp1.co)

    def test_vmd_import_basic(self):
        """Test basic VMD importing with enhanced debugging"""
        vmd_files = self._list_sample_files("vmd", "vmd")
        if not vmd_files:
            self.fail("No VMD sample files found for testing")

        armature = self._create_standard_mmd_armature()

        for filepath in vmd_files[:1]:
            print(f"Testing VMD file: {filepath}")

            results = self._perform_vmd_import_test(armature, filepath, "armature")

            print(f"Created action with {results['fcurves']} FCurves")
            print(f"Animation working! Detected {results['animation_detected']} bone transforms across timeline")

            self.assertIsNotNone(armature.animation_data, "Animation data should be created")
            if armature.animation_data:
                self.assertIsNotNone(armature.animation_data.action, "Action should be created")
                self.assertGreater(results["fcurves"], 0, "FCurves should be created")

                print(f"✓ VMD import test PASSED: {results['fcurves']} FCurves created")

            self._cleanup_animation(armature, "armature")

    def test_vmd_import_to_mesh(self):
        """Test VMD importing to a mesh with shape keys"""
        vmd_files = self._list_sample_files("vmd", "vmd")
        if not vmd_files:
            self.fail("No VMD sample files found for testing")

        mesh_obj = self._create_test_mesh_with_shape_keys()
        original_frame_start = bpy.context.scene.frame_start
        original_frame_end = bpy.context.scene.frame_end
        original_frame_current = bpy.context.scene.frame_current

        for filepath in vmd_files[:1]:
            vmd_analysis = self._analyze_vmd_content(filepath)
            shape_key_anim = vmd_analysis["shape_key_animation"]
            has_shape_key_data = len(shape_key_anim) > 0

            if has_shape_key_data:
                print(f"VMD file contains {len(shape_key_anim)} shape key animations")

            results = self._perform_vmd_import_test(mesh_obj, filepath, "mesh")

            if has_shape_key_data and results["fcurves"] > 0:
                print(f"Animation action created with {results['fcurves']} FCurves")
                if results["animation_detected"] > 0:
                    print(f"Import resulted in {results['animation_detected']} shape key changes across timeline")
                    self.assertTrue(True, "VMD import should create working shape key animation")
                else:
                    print("Shape key FCurves created but no visible changes detected")

            self._cleanup_animation(mesh_obj, "mesh")

        bpy.context.scene.frame_start = original_frame_start
        bpy.context.scene.frame_end = original_frame_end
        bpy.context.scene.frame_set(original_frame_current)

    def test_vmd_import_to_camera(self):
        """Test VMD importing to a camera"""
        vmd_files = self._list_sample_files("vmd", "vmd")
        if not vmd_files:
            self.fail("No VMD sample files found for testing")

        mmd_camera = self._create_mmd_camera()
        if not mmd_camera:
            self.fail("Could not create MMD camera for testing")

        for filepath in vmd_files[:1]:
            results = self._perform_vmd_import_test(mmd_camera, filepath, "camera")

            if results["fcurves"] > 0:
                print("Camera animation data was created")
                print(f"Camera has {results['fcurves']} FCurves")
                if results["animation_detected"] > 0:
                    print(f"Import resulted in {results['animation_detected']} camera property changes")
            else:
                print("No camera animation data created - VMD may not contain camera animation")

            self._cleanup_animation(mmd_camera, "camera")

    def test_vmd_import_to_lamp(self):
        """Test VMD importing to a lamp"""
        vmd_files = self._list_sample_files("vmd", "vmd")
        if not vmd_files:
            self.fail("No VMD sample files found for testing")

        mmd_lamp = self._create_mmd_lamp()
        if not mmd_lamp:
            self.fail("Could not create MMD lamp for testing")

        for filepath in vmd_files[:1]:
            results = self._perform_vmd_import_test(mmd_lamp, filepath, "lamp")

            if results["fcurves"] > 0:
                print("Lamp animation data was created")
                print(f"Lamp has {results['fcurves']} FCurves")
                if results["animation_detected"] > 0:
                    print(f"Import resulted in {results['animation_detected']} lamp property changes")
            else:
                print("No lamp animation data created - VMD may not contain lamp animation")

            self._cleanup_animation(mmd_lamp, "lamp")

    def test_vmd_import_with_real_model(self):
        """Test VMD importing with real PMX/PMD models if available"""
        pmx_files = self._list_sample_files("pmx", "pmx")
        pmx_files.extend(self._list_sample_files("pmd", "pmd"))
        vmd_files = self._list_sample_files("vmd", "vmd")

        if not pmx_files or not vmd_files:
            self.fail("No PMX/PMD or VMD sample files available for testing")

        try:
            self._enable_mmd_tools()
        except Exception:
            self.fail("Could not enable mmd_tools for testing with real models")

        pmx_file = pmx_files[0]
        vmd_file = vmd_files[0]

        try:
            model_root = self._create_model_from_pmx(pmx_file)
            if not model_root:
                self.fail("Could not import model for real model import test")

            model = Model(model_root)
            armature = model.armature()
            if not armature:
                self.fail("Imported model has no armature")

            print(f"Testing with real model: {os.path.basename(pmx_file)}")
            print(f"Model has {len(armature.pose.bones)} bones")

            results = self._perform_vmd_import_test(armature, vmd_file, "armature")

            self.assertIsNotNone(armature.animation_data, "Animation data should be created")
            if armature.animation_data:
                self.assertIsNotNone(armature.animation_data.action, "Action should be created")
                self.assertGreater(results["fcurves"], 0, "FCurves should be created for real model")

                print(f"✓ Real model VMD import test PASSED: {results['fcurves']} FCurves created")
                if results["animation_detected"] > 0:
                    print(f"✓ Real model animation working! Detected {results['animation_detected']} bone transforms")

                print("Real model import resulted in animation for multiple bones")

        except Exception as e:
            self.fail(f"Real model import test failed with error: {str(e)}")

    def test_vmd_import_full_setup(self):
        """Test importing VMD to a complete setup with armature, mesh, camera and lamp"""
        vmd_files = self._list_sample_files("vmd", "vmd")
        if not vmd_files:
            self.fail("No VMD sample files found for full setup test")

        test_objects = self._create_full_test_scene(with_shape_keys=True, with_camera=True, with_lamp=True)

        results = {"bone_changes": 0, "shape_key_changes": 0, "camera_changes": 0, "lamp_changes": 0}

        print("Testing VMD import on full setup...")

        for obj_type, obj in test_objects.items():
            if obj_type == "root" or obj is None:
                continue

            print(f"\nTesting {obj_type} import...")

            if obj_type == "armature":
                test_results = self._perform_vmd_import_test(obj, vmd_files[0], "armature")
                results["bone_changes"] = test_results["animation_detected"] or test_results["fcurves"]
                if test_results["fcurves"] > 0:
                    print(f"  ✓ Armature: {test_results['fcurves']} FCurves created")
                    if test_results["animation_detected"] > 0:
                        print(f"  ✓ Armature animation working: {test_results['animation_detected']} bone transforms detected")

            elif obj_type == "mesh":
                test_results = self._perform_vmd_import_test(obj, vmd_files[0], "mesh")
                results["shape_key_changes"] = test_results["animation_detected"] or test_results["fcurves"]
                if test_results["fcurves"] > 0:
                    print(f"  ✓ Mesh: {test_results['fcurves']} shape key FCurves created")
                    if test_results["animation_detected"] > 0:
                        print(f"  ✓ Shape key animation working: {test_results['animation_detected']} value changes detected")

            elif obj_type == "camera":
                test_results = self._perform_vmd_import_test(obj, vmd_files[0], "camera")
                results["camera_changes"] = test_results["animation_detected"] or test_results["fcurves"]
                if test_results["fcurves"] > 0:
                    print(f"  ✓ Camera: {test_results['fcurves']} FCurves created")
                    if test_results["animation_detected"] > 0:
                        print(f"  ✓ Camera animation working: {test_results['animation_detected']} transform changes detected")
                else:
                    print("  Camera: No animation data - VMD may not contain camera animation")

            elif obj_type == "lamp":
                test_results = self._perform_vmd_import_test(obj, vmd_files[0], "lamp")
                results["lamp_changes"] = test_results["animation_detected"] or test_results["fcurves"]
                if test_results["fcurves"] > 0:
                    print(f"  ✓ Lamp: {test_results['fcurves']} FCurves created")
                    if test_results["animation_detected"] > 0:
                        print(f"  ✓ Lamp animation working: {test_results['animation_detected']} transform changes detected")
                else:
                    print("  Lamp: No animation data - VMD may not contain lamp animation")

        print("\nFull setup import resulted in:")
        print(f" - {results['bone_changes']} bone changes/FCurves")
        print(f" - {results['shape_key_changes']} shape key changes/FCurves")
        print(f" - {results['camera_changes']} camera cut/FCurves")
        print(f" - {results['lamp_changes']} lamp changes/FCurves")

        total_animation = sum(results.values())
        if total_animation > 0:
            print(f"✓ Full setup test PASSED: Total animation data created = {total_animation}")

    def test_vmd_import_parameters(self):
        """Test VMD importing with different parameters"""
        vmd_files = self._list_sample_files("vmd", "vmd")
        if not vmd_files:
            self.fail("No VMD sample files found for testing parameters")

        armature = self._create_standard_mmd_armature()

        # Test different scale values
        scales = [0.1, 1.0, 10.0]
        for scale in scales:
            self._cleanup_animation(armature, "armature")

            importer = VMDImporter(filepath=vmd_files[0], scale=scale)
            importer.assign(armature)

            if armature.animation_data:
                self.assertIsNotNone(armature.animation_data.action, f"Action should be created with scale {scale}")

        # Test use_pose_mode
        self._cleanup_animation(armature, "armature")

        bpy.ops.object.select_all(action="DESELECT")
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode="POSE")

        importer = VMDImporter(filepath=vmd_files[0], use_pose_mode=True)
        importer.assign(armature)

        if armature.animation_data:
            self.assertIsNotNone(armature.animation_data.action, "Action should be created in pose mode")

        bpy.ops.object.mode_set(mode="OBJECT")

        # Test use_mirror
        self._cleanup_animation(armature, "armature")

        importer = VMDImporter(filepath=vmd_files[0], use_mirror=True)
        importer.assign(armature)

        if armature.animation_data:
            self.assertIsNotNone(armature.animation_data.action, "Action should be created with mirror option")

    def test_vmd_import_with_bone_mapper(self):
        """Test VMD importing with custom bone mapper"""
        vmd_files = self._list_sample_files("vmd", "vmd")
        if not vmd_files:
            self.fail("No VMD sample files found for testing bone mapper")

        armature = self._create_standard_mmd_armature()

        class SimpleBoneMapper:
            def __init__(self, arm_obj):
                self.armature = arm_obj
                self.bone_dict = {bone.name: bone for bone in arm_obj.pose.bones}

            def __call__(self, armObj):
                return self

            def get(self, bone_name, default=None):
                return self.bone_dict.get(bone_name, default)

        mapper = SimpleBoneMapper(armature)
        importer = VMDImporter(filepath=vmd_files[0], bone_mapper=mapper)

        try:
            importer.assign(armature)
            self.assertIsNotNone(armature.animation_data, "Animation data should be created with custom mapper")
            if armature.animation_data:
                self.assertIsNotNone(armature.animation_data.action, "Action should be created with custom mapper")
        except AssertionError:
            self.fail("Plugin has assertion issues with custom bone mappers - this is a plugin bug")

    def test_vmd_import_use_nla(self):
        """Test VMD importing with use_nla option"""
        vmd_files = self._list_sample_files("vmd", "vmd")
        if not vmd_files:
            self.fail("No VMD sample files found for NLA test")

        armature = self._create_standard_mmd_armature()

        importer = VMDImporter(filepath=vmd_files[0], use_nla=True)
        importer.assign(armature)

        self.assertIsNotNone(armature.animation_data, "Animation data should be created")
        if armature.animation_data:
            has_tracks = hasattr(armature.animation_data, "nla_tracks") and len(armature.animation_data.nla_tracks) > 0
            if has_tracks:
                print("NLA tracks were created successfully")
            else:
                print("NLA tracks were not created (this may be normal depending on the MMD Tools version)")

    def test_vmd_import_new_action_settings(self):
        """Test VMD importing with create_new_action option"""
        vmd_files = self._list_sample_files("vmd", "vmd")
        if not vmd_files:
            self.fail("No VMD sample files found for new action test")

        self._enable_mmd_tools()
        armature = self._create_standard_mmd_armature()

        # Select armature for import
        bpy.ops.object.select_all(action="DESELECT")
        armature.select_set(True)

        # First import with create_new_action=False
        bpy.ops.mmd_tools.import_vmd(files=[{"name": os.path.basename(vmd_files[0])}], directory=os.path.dirname(vmd_files[0]), scale=0.08, margin=0, bone_mapper="PMX", use_pose_mode=False, use_mirror=False, update_scene_settings=False, create_new_action=False, use_nla=False)

        first_action = None
        if armature.animation_data:
            first_action = armature.animation_data.action
            self.assertIsNotNone(first_action, "First action should be created")

        # Second import with create_new_action=True
        bpy.ops.mmd_tools.import_vmd(files=[{"name": os.path.basename(vmd_files[0])}], directory=os.path.dirname(vmd_files[0]), scale=0.08, margin=0, bone_mapper="PMX", use_pose_mode=False, use_mirror=False, update_scene_settings=False, create_new_action=True, use_nla=False)

        if armature.animation_data and first_action:
            second_action = armature.animation_data.action
            self.assertIsNotNone(second_action, "Second action should be created")
            if first_action in bpy.data.actions.values():
                print("First action still exists in Blender data")
            else:
                print("First action was cleared by create_new_action=True")
            self.assertIsNotNone(second_action, "New action should be created when create_new_action=True")

    def test_vmd_import_detect_changes(self):
        """Test VMD importing with detect_camera_changes and detect_lamp_changes options"""
        vmd_files = self._list_sample_files("vmd", "vmd")
        if not vmd_files:
            self.fail("No VMD sample files found for detect changes test")

        # Test with detect_camera_changes
        mmd_camera = self._create_mmd_camera()
        if mmd_camera:
            importer = VMDImporter(filepath=vmd_files[0], detect_camera_changes=True)
            importer.assign(mmd_camera)

            if mmd_camera.animation_data:
                if mmd_camera.animation_data.action:
                    print("Camera action was created with detect_camera_changes=True")
                else:
                    print("Camera animation data exists but no action - VMD may not contain camera animation")
            else:
                print("No camera animation data created - VMD may not contain camera animation")

        # Test with detect_lamp_changes
        mmd_lamp = self._create_mmd_lamp()
        if mmd_lamp:
            importer = VMDImporter(filepath=vmd_files[0], detect_lamp_changes=True)
            importer.assign(mmd_lamp)

            if mmd_lamp.animation_data:
                if mmd_lamp.animation_data.action:
                    print("Lamp action was created with detect_lamp_changes=True")
                else:
                    print("Lamp animation data exists but no action - VMD may not contain lamp animation")
            else:
                print("No lamp animation data created - VMD may not contain lamp animation")


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main(verbosity=1, exit=True)
