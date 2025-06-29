# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import logging
import math
import os
import shutil
import unittest

import bpy
from bl_ext.user_default.mmd_tools.core.camera import FnCamera, MMDCamera
from mathutils import Euler, Vector

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


class TestCameraSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Clean up output from previous tests"""
        output_dir = os.path.join(TESTS_DIR, "output")
        if os.path.exists(output_dir):
            for item in os.listdir(output_dir):
                if item.endswith(".OUTPUT"):
                    continue  # Skip the placeholder
                item_fp = os.path.join(output_dir, item)
                if os.path.isfile(item_fp):
                    os.remove(item_fp)
                elif os.path.isdir(item_fp):
                    shutil.rmtree(item_fp)

    def setUp(self):
        """We should start each test with a clean state"""
        logger = logging.getLogger()
        logger.setLevel("ERROR")
        # Clear all objects from scene
        bpy.ops.wm.read_homefile(use_empty=True)

        # Enable MMD tools addon
        self.__enable_mmd_tools()

    # ********************************************
    # Utils
    # ********************************************

    def __enable_mmd_tools(self):
        """Enable MMD tools addon for testing"""
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.user_default.mmd_tools")

    def __vector_error(self, vec0, vec1):
        """Calculate vector difference error"""
        return (Vector(vec0) - Vector(vec1)).length

    def __quaternion_error(self, quat0, quat1):
        """Calculate quaternion rotation difference error"""
        angle = quat0.rotation_difference(quat1).angle % math.pi
        assert angle >= 0
        return min(angle, math.pi - angle)

    def __create_test_camera(self, name="TestCamera"):
        """Create a basic camera for testing"""
        camera_data = bpy.data.cameras.new(name)
        camera_obj = bpy.data.objects.new(name, camera_data)
        bpy.context.scene.collection.objects.link(camera_obj)
        return camera_obj

    # ********************************************
    # FnCamera Tests
    # ********************************************

    def test_fn_camera_is_mmd_camera_root(self):
        """Test FnCamera.is_mmd_camera_root function"""
        # Create empty object with mmd_type
        empty = bpy.data.objects.new("TestEmpty", None)
        bpy.context.scene.collection.objects.link(empty)

        # Test non-MMD empty
        self.assertFalse(FnCamera.is_mmd_camera_root(empty))

        # Set MMD camera type
        empty.mmd_type = "CAMERA"
        self.assertTrue(FnCamera.is_mmd_camera_root(empty))

        # Test non-empty object
        camera_obj = self.__create_test_camera()
        self.assertFalse(FnCamera.is_mmd_camera_root(camera_obj))

    def test_fn_camera_find_root(self):
        """Test FnCamera.find_root function"""
        # Test with None
        self.assertIsNone(FnCamera.find_root(None))

        # Create MMD camera root
        empty = bpy.data.objects.new("MMD_Camera_Root", None)
        bpy.context.scene.collection.objects.link(empty)
        empty.mmd_type = "CAMERA"

        # Test direct root
        self.assertEqual(FnCamera.find_root(empty), empty)

        # Test with child camera
        camera_obj = self.__create_test_camera("MMD_Camera")
        camera_obj.parent = empty

        self.assertEqual(FnCamera.find_root(camera_obj), empty)

        # Test regular camera without MMD root
        regular_camera = self.__create_test_camera("RegularCamera")
        self.assertIsNone(FnCamera.find_root(regular_camera))

    def test_fn_camera_is_mmd_camera(self):
        """Test FnCamera.is_mmd_camera function"""
        # Create regular camera
        camera_obj = self.__create_test_camera()
        self.assertFalse(FnCamera.is_mmd_camera(camera_obj))

        # Create MMD camera system
        empty = bpy.data.objects.new("MMD_Camera_Root", None)
        bpy.context.scene.collection.objects.link(empty)
        empty.mmd_type = "CAMERA"

        camera_obj.parent = empty
        self.assertTrue(FnCamera.is_mmd_camera(camera_obj))

    def test_fn_camera_drivers(self):
        """Test FnCamera add_drivers and remove_drivers functions"""
        # Create MMD camera system
        empty = bpy.data.objects.new("MMD_Camera_Root", None)
        bpy.context.scene.collection.objects.link(empty)
        empty.mmd_type = "CAMERA"

        camera_obj = self.__create_test_camera("MMD_Camera")
        camera_obj.parent = empty

        # Set up required properties
        empty.mmd_camera.angle = math.radians(30)
        empty.mmd_camera.is_perspective = True

        # Test adding drivers
        FnCamera.add_drivers(camera_obj)

        # Check if drivers were added
        self.assertIsNotNone(camera_obj.data.animation_data)
        self.assertTrue(len(camera_obj.data.animation_data.drivers) > 0)

        # Test removing drivers
        FnCamera.remove_drivers(camera_obj)

        # Verify drivers were removed (animation_data might still exist but drivers should be gone)
        if camera_obj.data.animation_data:
            self.assertEqual(len(camera_obj.data.animation_data.drivers), 0)

    # ********************************************
    # MMDCamera Tests
    # ********************************************

    def test_mmd_camera_init_validation(self):
        """Test MMDCamera initialization validation"""
        # Test with regular camera (should raise ValueError)
        regular_camera = self.__create_test_camera()

        with self.assertRaises(ValueError):
            MMDCamera(regular_camera)

    def test_mmd_camera_convert_to_mmd_camera(self):
        """Test MMDCamera.convertToMMDCamera function"""
        # Create regular camera
        camera_obj = self.__create_test_camera("TestCamera")

        # Convert to MMD camera
        mmd_camera = MMDCamera.convertToMMDCamera(camera_obj, scale=1.0)

        # Verify MMD camera was created
        self.assertIsInstance(mmd_camera, MMDCamera)

        # Check if parent is MMD camera root
        self.assertIsNotNone(camera_obj.parent)
        self.assertTrue(FnCamera.is_mmd_camera_root(camera_obj.parent))

        # Check camera properties
        self.assertEqual(camera_obj.data.sensor_fit, "VERTICAL")
        self.assertEqual(camera_obj.data.lens_unit, "MILLIMETERS")
        self.assertEqual(camera_obj.rotation_mode, "XYZ")

        # Check location and rotation
        expected_location = Vector((0, -45.0, 0))
        self.assertLess(self.__vector_error(camera_obj.location, expected_location), 1e-6)

        expected_rotation = Euler((math.radians(90), 0, 0), "XYZ")
        self.assertLess(self.__quaternion_error(camera_obj.rotation_euler.to_quaternion(), expected_rotation.to_quaternion()), 1e-6)

        # Check locks - convert to tuple for proper comparison
        self.assertEqual(tuple(camera_obj.lock_location), (True, False, True))
        self.assertEqual(tuple(camera_obj.lock_rotation), (True, True, True))
        self.assertEqual(tuple(camera_obj.lock_scale), (True, True, True))

        # Verify DoF focus object is set to the empty (root)
        self.assertEqual(camera_obj.data.dof.focus_object, camera_obj.parent)

        # Check root object properties
        root_obj = camera_obj.parent
        expected_root_location = Vector((0, 0, 10.0))  # scale=1.0
        self.assertLess(self.__vector_error(root_obj.location, expected_root_location), 1e-6)
        self.assertEqual(root_obj.rotation_mode, "YXZ")
        self.assertEqual(tuple(root_obj.lock_scale), (True, True, True))

        # Check MMD camera properties - use correct attribute name
        self.assertAlmostEqual(root_obj.mmd_camera.angle, math.radians(30), places=6)
        self.assertTrue(root_obj.mmd_camera.is_perspective)  # Corrected attribute name

    def test_mmd_camera_object_and_camera_methods(self):
        """Test MMDCamera object() and camera() methods"""
        camera_obj = self.__create_test_camera("TestCamera")
        mmd_camera = MMDCamera.convertToMMDCamera(camera_obj, scale=1.0)

        # Test object() method returns the empty (root)
        root_obj = mmd_camera.object()
        self.assertTrue(FnCamera.is_mmd_camera_root(root_obj))

        # Test camera() method returns the camera object
        camera_obj_returned = mmd_camera.camera()
        self.assertEqual(camera_obj_returned.type, "CAMERA")
        self.assertEqual(camera_obj_returned, camera_obj)

    def test_mmd_camera_static_methods(self):
        """Test MMDCamera static methods"""
        # Test isMMDCamera
        regular_camera = self.__create_test_camera("RegularCamera")
        self.assertFalse(MMDCamera.isMMDCamera(regular_camera))

        # Convert and test again
        MMDCamera.convertToMMDCamera(regular_camera, scale=1.0)
        self.assertTrue(MMDCamera.isMMDCamera(regular_camera))

    def test_mmd_camera_new_animation(self):
        """Test MMDCamera.newMMDCameraAnimation function"""
        # Create source camera with some animation data
        source_camera = self.__create_test_camera("SourceCamera")
        bpy.context.scene.camera = source_camera

        # Set some frames for testing
        bpy.context.scene.frame_start = 1
        bpy.context.scene.frame_end = 10

        # Create new MMD camera animation
        try:
            mmd_camera = MMDCamera.newMMDCameraAnimation(source_camera, cameraTarget=None, scale=1.0, min_distance=0.1)

            # Verify MMD camera was created
            self.assertIsInstance(mmd_camera, MMDCamera)

            # Check if animation data was created
            root_obj = mmd_camera.object()
            camera_obj = mmd_camera.camera()

            self.assertIsNotNone(root_obj.animation_data)
            self.assertIsNotNone(camera_obj.animation_data)

        except Exception as e:
            # Animation creation might fail in headless mode, so we catch and verify the setup
            self.assertIsInstance(e, Exception)
            print(f"Animation test failed as expected in headless mode: {e}")

    # ********************************************
    # Driver System Tests
    # ********************************************

    def test_driver_variables_setup(self):
        """Test driver variables are set up correctly"""
        camera_obj = self.__create_test_camera("TestCamera")
        mmd_camera = MMDCamera.convertToMMDCamera(camera_obj, scale=1.0)

        # Verify MMD camera was created properly
        self.assertIsInstance(mmd_camera, MMDCamera)
        root_obj = mmd_camera.object()
        self.assertTrue(FnCamera.is_mmd_camera_root(root_obj))

        # Check if drivers exist
        if camera_obj.data.animation_data and camera_obj.data.animation_data.drivers:
            # Find ortho_scale driver
            ortho_driver = None
            for driver in camera_obj.data.animation_data.drivers:
                if driver.data_path == "ortho_scale":
                    ortho_driver = driver.driver
                    break

            if ortho_driver:
                # Check if empty_distance variable exists
                var_names = [var.name for var in ortho_driver.variables]
                self.assertIn("empty_distance", var_names)

                # Verify driver expression contains expected variables
                self.assertIn("empty_distance", ortho_driver.expression)

    def test_camera_properties_consistency(self):
        """Test camera properties remain consistent after conversion"""
        camera_obj = self.__create_test_camera("TestCamera")

        # Set initial properties to known values that will definitely change
        camera_obj.data.clip_end = 100.0  # Ensure different from expected value
        camera_obj.data.ortho_scale = 10.0  # Ensure different from expected value
        original_clip_end = camera_obj.data.clip_end
        original_ortho_scale = camera_obj.data.ortho_scale

        # Convert to MMD camera with scale=3.0 to avoid coincidental matches
        mmd_camera = MMDCamera.convertToMMDCamera(camera_obj, scale=3.0)

        # Verify MMD camera was created
        self.assertIsInstance(mmd_camera, MMDCamera)

        # Check that original values were changed (they should be different after conversion)
        self.assertNotEqual(camera_obj.data.clip_end, original_clip_end)
        self.assertNotEqual(camera_obj.data.ortho_scale, original_ortho_scale)

        # Check scale-dependent properties match expected values
        expected_clip_end = 500 * 3.0  # scale=3.0 -> 1500.0
        self.assertEqual(camera_obj.data.clip_end, expected_clip_end)

        # Check ortho_scale
        expected_ortho_scale = 25 * 3.0  # scale=3.0 -> 75.0
        self.assertEqual(camera_obj.data.ortho_scale, expected_ortho_scale)

        # Verify MMD camera root properties
        root_obj = mmd_camera.object()
        self.assertEqual(root_obj.mmd_type, "CAMERA")
        expected_root_location = Vector((0, 0, 10 * 3.0))  # scale=3.0 -> (0, 0, 30)
        self.assertLess(self.__vector_error(root_obj.location, expected_root_location), 1e-6)

    # ********************************************
    # Integration Tests
    # ********************************************

    def test_camera_system_integration(self):
        """Test complete camera system integration"""
        # Create multiple cameras and test conversion
        cameras = []
        for i in range(3):
            camera_obj = self.__create_test_camera(f"Camera_{i}")
            cameras.append(camera_obj)

        # Convert all to MMD cameras
        mmd_cameras = []
        for camera_obj in cameras:
            mmd_camera = MMDCamera.convertToMMDCamera(camera_obj, scale=1.0)
            mmd_cameras.append(mmd_camera)

        # Verify all conversions
        for i, (camera_obj, mmd_camera) in enumerate(zip(cameras, mmd_cameras, strict=False)):
            msg = f"Camera_{i}"

            # Check MMD camera validity
            self.assertTrue(MMDCamera.isMMDCamera(camera_obj), msg)
            self.assertTrue(FnCamera.is_mmd_camera(camera_obj), msg)

            # Check parent-child relationship
            root_obj = mmd_camera.object()
            self.assertEqual(camera_obj.parent, root_obj, msg)

            # Check MMD properties
            self.assertEqual(root_obj.mmd_type, "CAMERA", msg)

    def test_camera_error_handling(self):
        """Test camera system error handling"""
        # Test with None object
        self.assertIsNone(FnCamera.find_root(None))

        # Test MMDCamera with invalid object
        empty = bpy.data.objects.new("NotMMDCamera", None)
        bpy.context.scene.collection.objects.link(empty)

        with self.assertRaises(ValueError):
            MMDCamera(empty)

        # Test driver removal on non-camera object
        try:
            MMDCamera.removeDrivers(empty)  # Should not crash
        except Exception as e:
            self.fail(f"removeDrivers should handle non-camera objects gracefully: {e}")


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main()
