# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import logging
import os
import shutil
import unittest

import bpy

# Import the light system components
from bl_ext.blender_org.mmd_tools.core.light import MMDLight
from bl_ext.blender_org.mmd_tools.operators.light import ConvertToMMDLight
from bl_ext.blender_org.mmd_tools.panels.prop_light import MMDLightPanel
from mathutils import Vector

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


class TestLightSystem(unittest.TestCase):
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
        """Set up testing environment"""
        logger = logging.getLogger()
        logger.setLevel("ERROR")

        # Clear all mesh objects
        bpy.ops.wm.read_homefile(use_empty=True)
        self.__enable_mmd_tools()

    def tearDown(self):
        """Clean up after each test"""
        # Clear scene objects
        bpy.ops.wm.read_homefile(use_empty=True)

    # ********************************************
    # Utils
    # ********************************************

    def __vector_error(self, vec0, vec1):
        return (Vector(vec0) - Vector(vec1)).length

    def __enable_mmd_tools(self):
        """Enable MMD tools addon"""
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.blender_org.mmd_tools")

    def __create_light_object(self, name="TestLight", light_type="SUN", location=(0, 0, 0)):
        """Create a light object for testing"""
        light_data = bpy.data.lights.new(name=name + "_Data", type=light_type)
        light_obj = bpy.data.objects.new(name=name, object_data=light_data)
        bpy.context.collection.objects.link(light_obj)
        light_obj.location = location
        return light_obj

    # ********************************************
    # MMDLight Static Methods Tests
    # ********************************************

    def test_isLight_valid_light(self):
        """Test MMDLight.isLight() with valid light object"""
        light_obj = self.__create_light_object()
        self.assertTrue(MMDLight.isLight(light_obj))

    def test_isLight_invalid_object(self):
        """Test MMDLight.isLight() with invalid object types"""
        # Test with empty object
        empty_obj = bpy.data.objects.new(name="TestEmpty", object_data=None)
        bpy.context.collection.objects.link(empty_obj)
        self.assertFalse(MMDLight.isLight(empty_obj))

        # Test with mesh object
        mesh_data = bpy.data.meshes.new(name="TestMesh")
        mesh_obj = bpy.data.objects.new(name="TestMeshObj", object_data=mesh_data)
        bpy.context.collection.objects.link(mesh_obj)
        self.assertFalse(MMDLight.isLight(mesh_obj))

        # Test with None
        self.assertFalse(MMDLight.isLight(None))

    def test_isMMDLight_non_mmd_light(self):
        """Test MMDLight.isMMDLight() with regular light"""
        light_obj = self.__create_light_object()
        self.assertFalse(MMDLight.isMMDLight(light_obj))

    def test_isMMDLight_invalid_object(self):
        """Test MMDLight.isMMDLight() with invalid objects"""
        # Test with regular empty object
        empty_obj = bpy.data.objects.new(name="TestEmpty", object_data=None)
        bpy.context.collection.objects.link(empty_obj)
        self.assertFalse(MMDLight.isMMDLight(empty_obj))

        # Test with None
        self.assertFalse(MMDLight.isMMDLight(None))

    # ********************************************
    # MMDLight Conversion Tests
    # ********************************************

    def test_convertToMMDLight_basic_conversion(self):
        """Test basic conversion of light to MMD light"""
        # Create a regular light
        light_obj = self.__create_light_object(location=(1, 2, 3))
        original_color = (1.0, 1.0, 1.0)
        light_obj.data.color = original_color

        # Convert to MMD light
        scale = 0.5
        mmd_light = MMDLight.convertToMMDLight(light_obj, scale=scale)

        # Verify conversion
        self.assertIsInstance(mmd_light, MMDLight)
        self.assertTrue(MMDLight.isMMDLight(mmd_light.object()))

        # Check empty object properties
        empty_obj = mmd_light.object()
        self.assertEqual(empty_obj.type, "EMPTY")
        self.assertEqual(empty_obj.mmd_type, "LIGHT")
        self.assertEqual(empty_obj.name, "MMD_Light")
        self.assertEqual(empty_obj.rotation_mode, "XYZ")

        # Fix: Convert bpy_prop_array to list for comparison
        self.assertEqual(list(empty_obj.lock_rotation), [True, True, True])

        # Check scale
        expected_scale = [10 * scale] * 3
        for i in range(3):
            self.assertAlmostEqual(empty_obj.scale[i], expected_scale[i], places=6)

        # Check location
        expected_location = (0, 0, 11 * scale)
        self.assertLess(self.__vector_error(empty_obj.location, expected_location), 1e-6)

        # Check light object properties
        converted_light = mmd_light.light()
        self.assertEqual(converted_light, light_obj)
        self.assertEqual(converted_light.parent, empty_obj)
        expected_color = (0.602, 0.602, 0.602)
        actual_color = tuple(converted_light.data.color)
        self.assertLess(self.__vector_error(actual_color, expected_color), 1e-6)
        self.assertEqual(converted_light.rotation_mode, "XYZ")

        # Fix: Convert bpy_prop_array to list for comparison
        self.assertEqual(list(converted_light.lock_rotation), [True, True, True])

        # Check light location relative to parent
        expected_light_location = (0.5, -0.5, 1.0)
        self.assertLess(self.__vector_error(converted_light.location, expected_light_location), 1e-6)

        # Check light rotation
        expected_rotation = (0, 0, 0)
        self.assertLess(self.__vector_error(converted_light.rotation_euler, expected_rotation), 1e-6)

        # Check constraint
        constraints = [c for c in converted_light.constraints if c.name == "mmd_light_track"]
        self.assertEqual(len(constraints), 1)

        constraint = constraints[0]
        self.assertEqual(constraint.type, "TRACK_TO")
        self.assertEqual(constraint.target, empty_obj)
        self.assertEqual(constraint.track_axis, "TRACK_NEGATIVE_Z")
        self.assertEqual(constraint.up_axis, "UP_Y")

    def test_convertToMMDLight_already_mmd_light(self):
        """Test conversion when object is already MMD light"""
        # Create and convert a light
        light_obj = self.__create_light_object()
        mmd_light1 = MMDLight.convertToMMDLight(light_obj, scale=0.5)

        # Try to convert again
        mmd_light2 = MMDLight.convertToMMDLight(light_obj, scale=1.0)

        # Should return the same MMD light instance
        self.assertEqual(mmd_light1.object(), mmd_light2.object())

    def test_convertToMMDLight_different_scales(self):
        """Test conversion with different scale values"""
        scales = [0.01, 0.1, 0.5, 1.0, 2.0, 10.0]

        for scale in scales:
            with self.subTest(scale=scale):
                # Clear scene
                bpy.ops.wm.read_homefile(use_empty=True)

                # Create light and convert
                light_obj = self.__create_light_object(name=f"TestLight_{scale}")
                mmd_light = MMDLight.convertToMMDLight(light_obj, scale=scale)

                # Check scale
                empty_obj = mmd_light.object()
                expected_scale = [10 * scale] * 3
                for i in range(3):
                    self.assertAlmostEqual(empty_obj.scale[i], expected_scale[i], places=6)

                # Check location
                expected_location = (0, 0, 11 * scale)
                self.assertLess(self.__vector_error(empty_obj.location, expected_location), 1e-6)

    # ********************************************
    # MMDLight Instance Tests
    # ********************************************

    def test_mmd_light_init_valid(self):
        """Test MMDLight initialization with valid objects"""
        # Create MMD light
        light_obj = self.__create_light_object()
        mmd_light_converted = MMDLight.convertToMMDLight(light_obj)
        empty_obj = mmd_light_converted.object()

        # Test initialization with empty object
        mmd_light1 = MMDLight(empty_obj)
        self.assertEqual(mmd_light1.object(), empty_obj)

        # Test initialization with light object (should use parent)
        mmd_light2 = MMDLight(light_obj)
        self.assertEqual(mmd_light2.object(), empty_obj)

    def test_mmd_light_init_invalid(self):
        """Test MMDLight initialization with invalid objects"""
        # Test with regular empty object
        empty_obj = bpy.data.objects.new(name="TestEmpty", object_data=None)
        bpy.context.collection.objects.link(empty_obj)

        with self.assertRaises(ValueError):
            MMDLight(empty_obj)

        # Test with regular light object without MMD parent
        light_obj = self.__create_light_object()

        with self.assertRaises(ValueError):
            MMDLight(light_obj)

        # Test with None
        with self.assertRaises(ValueError):
            MMDLight(None)

        # Test with mesh object
        mesh_data = bpy.data.meshes.new(name="TestMesh")
        mesh_obj = bpy.data.objects.new(name="TestMeshObj", object_data=mesh_data)
        bpy.context.collection.objects.link(mesh_obj)

        with self.assertRaises(ValueError):
            MMDLight(mesh_obj)

    def test_mmd_light_methods(self):
        """Test MMDLight instance methods"""
        # Create MMD light
        light_obj = self.__create_light_object()
        mmd_light = MMDLight.convertToMMDLight(light_obj)

        # Test object() method
        empty_obj = mmd_light.object()
        self.assertEqual(empty_obj.type, "EMPTY")
        self.assertEqual(empty_obj.mmd_type, "LIGHT")

        # Test light() method
        retrieved_light = mmd_light.light()
        self.assertEqual(retrieved_light, light_obj)
        self.assertTrue(MMDLight.isLight(retrieved_light))

    def test_mmd_light_no_child_light(self):
        """Test MMDLight.light() when no child light exists"""
        # Create MMD light structure manually without light child
        empty_obj = bpy.data.objects.new(name="MMD_Light", object_data=None)
        bpy.context.collection.objects.link(empty_obj)
        empty_obj.mmd_type = "LIGHT"

        mmd_light = MMDLight(empty_obj)

        # Should raise KeyError when no light child exists
        with self.assertRaises(KeyError):
            mmd_light.light()

    # ********************************************
    # Operator Tests
    # ********************************************

    def test_convert_operator_poll(self):
        """Test ConvertToMMDLight operator poll method"""
        # Create light object
        light_obj = self.__create_light_object()

        # Set active object and test poll
        bpy.context.view_layer.objects.active = light_obj
        self.assertTrue(ConvertToMMDLight.poll(bpy.context))

        # Test with non-light object
        empty_obj = bpy.data.objects.new(name="TestEmpty", object_data=None)
        bpy.context.collection.objects.link(empty_obj)
        bpy.context.view_layer.objects.active = empty_obj
        self.assertFalse(ConvertToMMDLight.poll(bpy.context))

        # Test with no active object
        bpy.context.view_layer.objects.active = None
        self.assertFalse(ConvertToMMDLight.poll(bpy.context))

    # ********************************************
    # Panel Tests
    # ********************************************

    def test_light_panel_poll(self):
        """Test MMDLightPanel poll method"""
        # Test with regular light
        light_obj = self.__create_light_object()
        bpy.context.view_layer.objects.active = light_obj
        self.assertTrue(MMDLightPanel.poll(bpy.context))

        # Test with MMD light
        mmd_light = MMDLight.convertToMMDLight(light_obj)
        bpy.context.view_layer.objects.active = mmd_light.object()
        self.assertTrue(MMDLightPanel.poll(bpy.context))

        # Test with MMD light's child light
        bpy.context.view_layer.objects.active = mmd_light.light()
        self.assertTrue(MMDLightPanel.poll(bpy.context))

        # Test with non-light object
        empty_obj = bpy.data.objects.new(name="TestEmpty", object_data=None)
        bpy.context.collection.objects.link(empty_obj)
        bpy.context.view_layer.objects.active = empty_obj
        self.assertFalse(MMDLightPanel.poll(bpy.context))

        # Test with no active object
        bpy.context.view_layer.objects.active = None
        self.assertFalse(MMDLightPanel.poll(bpy.context))

    # ********************************************
    # Integration Tests
    # ********************************************

    def test_light_system_integration(self):
        """Test complete light system integration"""
        # Create multiple lights with different types
        light_types = ["SUN", "POINT", "SPOT", "AREA"]
        created_lights = []

        for light_type in light_types:
            with self.subTest(light_type=light_type):
                # Create light
                light_obj = self.__create_light_object(name=f"TestLight_{light_type}", light_type=light_type, location=(len(created_lights), 0, 0))
                created_lights.append(light_obj)

                # Convert to MMD light
                mmd_light = MMDLight.convertToMMDLight(light_obj, scale=0.1 * (len(created_lights) + 1))

                # Verify all components work together
                self.assertTrue(MMDLight.isMMDLight(mmd_light.object()))
                self.assertTrue(MMDLight.isLight(mmd_light.light()))
                self.assertEqual(mmd_light.light().data.type, light_type)

                # Test panel poll
                bpy.context.view_layer.objects.active = mmd_light.object()
                self.assertTrue(MMDLightPanel.poll(bpy.context))

                # Fix: Remove incorrect assumption about poll result
                # ConvertToMMDLight.poll() only checks if object is a light,
                # not whether it's already converted to MMD light
                bpy.context.view_layer.objects.active = mmd_light.light()
                self.assertTrue(ConvertToMMDLight.poll(bpy.context))  # Should be True since it's still a light

    def test_parameter_validation(self):
        """Test parameter validation for various edge cases"""
        # Test scale parameter validation
        light_obj = self.__create_light_object()

        # Test with zero scale
        mmd_light = MMDLight.convertToMMDLight(light_obj, scale=0.0)
        empty_obj = mmd_light.object()
        self.assertEqual(list(empty_obj.scale), [0.0, 0.0, 0.0])
        self.assertEqual(list(empty_obj.location), [0.0, 0.0, 0.0])

        # Test with negative scale
        bpy.ops.wm.read_homefile(use_empty=True)
        light_obj = self.__create_light_object()
        mmd_light = MMDLight.convertToMMDLight(light_obj, scale=-1.0)
        empty_obj = mmd_light.object()
        expected_scale = [-10.0, -10.0, -10.0]
        expected_location = (0, 0, -11.0)
        self.assertEqual(list(empty_obj.scale), expected_scale)
        self.assertLess(self.__vector_error(empty_obj.location, expected_location), 1e-6)

    def test_object_hierarchy_consistency(self):
        """Test object hierarchy consistency after conversion"""
        # Create light and convert
        light_obj = self.__create_light_object(name="HierarchyTest")
        original_name = light_obj.name

        mmd_light = MMDLight.convertToMMDLight(light_obj, scale=1.0)

        # Verify hierarchy
        empty_obj = mmd_light.object()
        light_child = mmd_light.light()

        self.assertEqual(light_child.parent, empty_obj)
        self.assertIn(light_child, empty_obj.children)
        self.assertEqual(light_child.name, original_name)

        # Verify no other children
        light_children = [child for child in empty_obj.children if MMDLight.isLight(child)]
        self.assertEqual(len(light_children), 1)
        self.assertEqual(light_children[0], light_child)


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main(verbosity=1, exit=True)
