# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import logging
import os
import shutil
import unittest

import bpy

# Import the lamp system components
from bl_ext.blender_org.mmd_tools.core.lamp import MMDLamp
from bl_ext.blender_org.mmd_tools.operators.lamp import ConvertToMMDLamp
from bl_ext.blender_org.mmd_tools.panels.prop_lamp import MMDLampPanel
from mathutils import Vector

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


class TestLampSystem(unittest.TestCase):
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

    def __create_lamp_object(self, name="TestLamp", lamp_type="SUN", location=(0, 0, 0)):
        """Create a lamp object for testing"""
        lamp_data = bpy.data.lights.new(name=name + "_Data", type=lamp_type)
        lamp_obj = bpy.data.objects.new(name=name, object_data=lamp_data)
        bpy.context.collection.objects.link(lamp_obj)
        lamp_obj.location = location
        return lamp_obj

    # ********************************************
    # MMDLamp Static Methods Tests
    # ********************************************

    def test_isLamp_valid_lamp(self):
        """Test MMDLamp.isLamp() with valid lamp object"""
        lamp_obj = self.__create_lamp_object()
        self.assertTrue(MMDLamp.isLamp(lamp_obj))

    def test_isLamp_invalid_object(self):
        """Test MMDLamp.isLamp() with invalid object types"""
        # Test with empty object
        empty_obj = bpy.data.objects.new(name="TestEmpty", object_data=None)
        bpy.context.collection.objects.link(empty_obj)
        self.assertFalse(MMDLamp.isLamp(empty_obj))

        # Test with mesh object
        mesh_data = bpy.data.meshes.new(name="TestMesh")
        mesh_obj = bpy.data.objects.new(name="TestMeshObj", object_data=mesh_data)
        bpy.context.collection.objects.link(mesh_obj)
        self.assertFalse(MMDLamp.isLamp(mesh_obj))

        # Test with None
        self.assertFalse(MMDLamp.isLamp(None))

    def test_isMMDLamp_non_mmd_lamp(self):
        """Test MMDLamp.isMMDLamp() with regular lamp"""
        lamp_obj = self.__create_lamp_object()
        self.assertFalse(MMDLamp.isMMDLamp(lamp_obj))

    def test_isMMDLamp_invalid_object(self):
        """Test MMDLamp.isMMDLamp() with invalid objects"""
        # Test with regular empty object
        empty_obj = bpy.data.objects.new(name="TestEmpty", object_data=None)
        bpy.context.collection.objects.link(empty_obj)
        self.assertFalse(MMDLamp.isMMDLamp(empty_obj))

        # Test with None
        self.assertFalse(MMDLamp.isMMDLamp(None))

    # ********************************************
    # MMDLamp Conversion Tests
    # ********************************************

    def test_convertToMMDLamp_basic_conversion(self):
        """Test basic conversion of lamp to MMD lamp"""
        # Create a regular lamp
        lamp_obj = self.__create_lamp_object(location=(1, 2, 3))
        original_color = (1.0, 1.0, 1.0)
        lamp_obj.data.color = original_color

        # Convert to MMD lamp
        scale = 0.5
        mmd_lamp = MMDLamp.convertToMMDLamp(lamp_obj, scale=scale)

        # Verify conversion
        self.assertIsInstance(mmd_lamp, MMDLamp)
        self.assertTrue(MMDLamp.isMMDLamp(mmd_lamp.object()))

        # Check empty object properties
        empty_obj = mmd_lamp.object()
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

        # Check lamp object properties
        converted_lamp = mmd_lamp.lamp()
        self.assertEqual(converted_lamp, lamp_obj)
        self.assertEqual(converted_lamp.parent, empty_obj)
        expected_color = (0.602, 0.602, 0.602)
        actual_color = tuple(converted_lamp.data.color)
        self.assertLess(self.__vector_error(actual_color, expected_color), 1e-6)
        self.assertEqual(converted_lamp.rotation_mode, "XYZ")

        # Fix: Convert bpy_prop_array to list for comparison
        self.assertEqual(list(converted_lamp.lock_rotation), [True, True, True])

        # Check lamp location relative to parent
        expected_lamp_location = (0.5, -0.5, 1.0)
        self.assertLess(self.__vector_error(converted_lamp.location, expected_lamp_location), 1e-6)

        # Check lamp rotation
        expected_rotation = (0, 0, 0)
        self.assertLess(self.__vector_error(converted_lamp.rotation_euler, expected_rotation), 1e-6)

        # Check constraint
        constraints = [c for c in converted_lamp.constraints if c.name == "mmd_lamp_track"]
        self.assertEqual(len(constraints), 1)

        constraint = constraints[0]
        self.assertEqual(constraint.type, "TRACK_TO")
        self.assertEqual(constraint.target, empty_obj)
        self.assertEqual(constraint.track_axis, "TRACK_NEGATIVE_Z")
        self.assertEqual(constraint.up_axis, "UP_Y")

    def test_convertToMMDLamp_already_mmd_lamp(self):
        """Test conversion when object is already MMD lamp"""
        # Create and convert a lamp
        lamp_obj = self.__create_lamp_object()
        mmd_lamp1 = MMDLamp.convertToMMDLamp(lamp_obj, scale=0.5)

        # Try to convert again
        mmd_lamp2 = MMDLamp.convertToMMDLamp(lamp_obj, scale=1.0)

        # Should return the same MMD lamp instance
        self.assertEqual(mmd_lamp1.object(), mmd_lamp2.object())

    def test_convertToMMDLamp_different_scales(self):
        """Test conversion with different scale values"""
        scales = [0.01, 0.1, 0.5, 1.0, 2.0, 10.0]

        for scale in scales:
            with self.subTest(scale=scale):
                # Clear scene
                bpy.ops.wm.read_homefile(use_empty=True)

                # Create lamp and convert
                lamp_obj = self.__create_lamp_object(name=f"TestLamp_{scale}")
                mmd_lamp = MMDLamp.convertToMMDLamp(lamp_obj, scale=scale)

                # Check scale
                empty_obj = mmd_lamp.object()
                expected_scale = [10 * scale] * 3
                for i in range(3):
                    self.assertAlmostEqual(empty_obj.scale[i], expected_scale[i], places=6)

                # Check location
                expected_location = (0, 0, 11 * scale)
                self.assertLess(self.__vector_error(empty_obj.location, expected_location), 1e-6)

    # ********************************************
    # MMDLamp Instance Tests
    # ********************************************

    def test_mmd_lamp_init_valid(self):
        """Test MMDLamp initialization with valid objects"""
        # Create MMD lamp
        lamp_obj = self.__create_lamp_object()
        mmd_lamp_converted = MMDLamp.convertToMMDLamp(lamp_obj)
        empty_obj = mmd_lamp_converted.object()

        # Test initialization with empty object
        mmd_lamp1 = MMDLamp(empty_obj)
        self.assertEqual(mmd_lamp1.object(), empty_obj)

        # Test initialization with lamp object (should use parent)
        mmd_lamp2 = MMDLamp(lamp_obj)
        self.assertEqual(mmd_lamp2.object(), empty_obj)

    def test_mmd_lamp_init_invalid(self):
        """Test MMDLamp initialization with invalid objects"""
        # Test with regular empty object
        empty_obj = bpy.data.objects.new(name="TestEmpty", object_data=None)
        bpy.context.collection.objects.link(empty_obj)

        with self.assertRaises(ValueError):
            MMDLamp(empty_obj)

        # Test with regular lamp object without MMD parent
        lamp_obj = self.__create_lamp_object()

        with self.assertRaises(ValueError):
            MMDLamp(lamp_obj)

        # Test with None
        with self.assertRaises(ValueError):
            MMDLamp(None)

        # Test with mesh object
        mesh_data = bpy.data.meshes.new(name="TestMesh")
        mesh_obj = bpy.data.objects.new(name="TestMeshObj", object_data=mesh_data)
        bpy.context.collection.objects.link(mesh_obj)

        with self.assertRaises(ValueError):
            MMDLamp(mesh_obj)

    def test_mmd_lamp_methods(self):
        """Test MMDLamp instance methods"""
        # Create MMD lamp
        lamp_obj = self.__create_lamp_object()
        mmd_lamp = MMDLamp.convertToMMDLamp(lamp_obj)

        # Test object() method
        empty_obj = mmd_lamp.object()
        self.assertEqual(empty_obj.type, "EMPTY")
        self.assertEqual(empty_obj.mmd_type, "LIGHT")

        # Test lamp() method
        retrieved_lamp = mmd_lamp.lamp()
        self.assertEqual(retrieved_lamp, lamp_obj)
        self.assertTrue(MMDLamp.isLamp(retrieved_lamp))

    def test_mmd_lamp_no_child_lamp(self):
        """Test MMDLamp.lamp() when no child lamp exists"""
        # Create MMD lamp structure manually without lamp child
        empty_obj = bpy.data.objects.new(name="MMD_Light", object_data=None)
        bpy.context.collection.objects.link(empty_obj)
        empty_obj.mmd_type = "LIGHT"

        mmd_lamp = MMDLamp(empty_obj)

        # Should raise KeyError when no lamp child exists
        with self.assertRaises(KeyError):
            mmd_lamp.lamp()

    # ********************************************
    # Operator Tests
    # ********************************************

    def test_convert_operator_poll(self):
        """Test ConvertToMMDLamp operator poll method"""
        # Create lamp object
        lamp_obj = self.__create_lamp_object()

        # Set active object and test poll
        bpy.context.view_layer.objects.active = lamp_obj
        self.assertTrue(ConvertToMMDLamp.poll(bpy.context))

        # Test with non-lamp object
        empty_obj = bpy.data.objects.new(name="TestEmpty", object_data=None)
        bpy.context.collection.objects.link(empty_obj)
        bpy.context.view_layer.objects.active = empty_obj
        self.assertFalse(ConvertToMMDLamp.poll(bpy.context))

        # Test with no active object
        bpy.context.view_layer.objects.active = None
        self.assertFalse(ConvertToMMDLamp.poll(bpy.context))

    # ********************************************
    # Panel Tests
    # ********************************************

    def test_lamp_panel_poll(self):
        """Test MMDLampPanel poll method"""
        # Test with regular lamp
        lamp_obj = self.__create_lamp_object()
        bpy.context.view_layer.objects.active = lamp_obj
        self.assertTrue(MMDLampPanel.poll(bpy.context))

        # Test with MMD lamp
        mmd_lamp = MMDLamp.convertToMMDLamp(lamp_obj)
        bpy.context.view_layer.objects.active = mmd_lamp.object()
        self.assertTrue(MMDLampPanel.poll(bpy.context))

        # Test with MMD lamp's child lamp
        bpy.context.view_layer.objects.active = mmd_lamp.lamp()
        self.assertTrue(MMDLampPanel.poll(bpy.context))

        # Test with non-lamp object
        empty_obj = bpy.data.objects.new(name="TestEmpty", object_data=None)
        bpy.context.collection.objects.link(empty_obj)
        bpy.context.view_layer.objects.active = empty_obj
        self.assertFalse(MMDLampPanel.poll(bpy.context))

        # Test with no active object
        bpy.context.view_layer.objects.active = None
        self.assertFalse(MMDLampPanel.poll(bpy.context))

    # ********************************************
    # Integration Tests
    # ********************************************

    def test_lamp_system_integration(self):
        """Test complete lamp system integration"""
        # Create multiple lamps with different types
        lamp_types = ["SUN", "POINT", "SPOT", "AREA"]
        created_lamps = []

        for lamp_type in lamp_types:
            with self.subTest(lamp_type=lamp_type):
                # Create lamp
                lamp_obj = self.__create_lamp_object(name=f"TestLamp_{lamp_type}", lamp_type=lamp_type, location=(len(created_lamps), 0, 0))
                created_lamps.append(lamp_obj)

                # Convert to MMD lamp
                mmd_lamp = MMDLamp.convertToMMDLamp(lamp_obj, scale=0.1 * (len(created_lamps) + 1))

                # Verify all components work together
                self.assertTrue(MMDLamp.isMMDLamp(mmd_lamp.object()))
                self.assertTrue(MMDLamp.isLamp(mmd_lamp.lamp()))
                self.assertEqual(mmd_lamp.lamp().data.type, lamp_type)

                # Test panel poll
                bpy.context.view_layer.objects.active = mmd_lamp.object()
                self.assertTrue(MMDLampPanel.poll(bpy.context))

                # Fix: Remove incorrect assumption about poll result
                # ConvertToMMDLamp.poll() only checks if object is a lamp,
                # not whether it's already converted to MMD lamp
                bpy.context.view_layer.objects.active = mmd_lamp.lamp()
                self.assertTrue(ConvertToMMDLamp.poll(bpy.context))  # Should be True since it's still a lamp

    def test_parameter_validation(self):
        """Test parameter validation for various edge cases"""
        # Test scale parameter validation
        lamp_obj = self.__create_lamp_object()

        # Test with zero scale
        mmd_lamp = MMDLamp.convertToMMDLamp(lamp_obj, scale=0.0)
        empty_obj = mmd_lamp.object()
        self.assertEqual(list(empty_obj.scale), [0.0, 0.0, 0.0])
        self.assertEqual(list(empty_obj.location), [0.0, 0.0, 0.0])

        # Test with negative scale
        bpy.ops.wm.read_homefile(use_empty=True)
        lamp_obj = self.__create_lamp_object()
        mmd_lamp = MMDLamp.convertToMMDLamp(lamp_obj, scale=-1.0)
        empty_obj = mmd_lamp.object()
        expected_scale = [-10.0, -10.0, -10.0]
        expected_location = (0, 0, -11.0)
        self.assertEqual(list(empty_obj.scale), expected_scale)
        self.assertLess(self.__vector_error(empty_obj.location, expected_location), 1e-6)

    def test_object_hierarchy_consistency(self):
        """Test object hierarchy consistency after conversion"""
        # Create lamp and convert
        lamp_obj = self.__create_lamp_object(name="HierarchyTest")
        original_name = lamp_obj.name

        mmd_lamp = MMDLamp.convertToMMDLamp(lamp_obj, scale=1.0)

        # Verify hierarchy
        empty_obj = mmd_lamp.object()
        lamp_child = mmd_lamp.lamp()

        self.assertEqual(lamp_child.parent, empty_obj)
        self.assertIn(lamp_child, empty_obj.children)
        self.assertEqual(lamp_child.name, original_name)

        # Verify no other children
        lamp_children = [child for child in empty_obj.children if MMDLamp.isLamp(child)]
        self.assertEqual(len(lamp_children), 1)
        self.assertEqual(lamp_children[0], lamp_child)


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main(verbosity=1, exit=True)
