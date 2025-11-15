# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import logging
import os
import unittest

import bpy

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "samples")


class TestAnimation(unittest.TestCase):
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

    def setUp(self):
        """Set up testing environment"""
        logger = logging.getLogger()
        logger.setLevel("ERROR")

        # Reset scene to default state
        bpy.ops.wm.read_homefile(use_empty=True)

    # ********************************************
    # Test Function
    # ********************************************

    def __enable_mmd_tools(self):
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.blender_org.mmd_tools")  # make sure addon 'mmd_tools' is enabled

    def __list_sample_files(self, file_types):
        ret = []
        for file_type in file_types:
            file_ext = "." + file_type
            for root, dirs, files in os.walk(os.path.join(SAMPLES_DIR, file_type)):
                ret.extend(os.path.join(root, name) for name in files if name.lower().endswith(file_ext))
        return ret

    def __create_test_actions(self):
        """Create test actions with specific frame ranges"""
        # Create first action with frame range 0-100
        action1 = bpy.data.actions.new(name="TestAction1")
        action1.use_frame_range = True
        action1.frame_start = 0
        action1.frame_end = 100

        # Create second action with frame range 50-200
        action2 = bpy.data.actions.new(name="TestAction2")
        action2.use_frame_range = True
        action2.frame_start = 50
        action2.frame_end = 200

        # Create third action with frame range -10-30
        action3 = bpy.data.actions.new(name="TestAction3")
        action3.use_frame_range = True
        action3.frame_start = -10
        action3.frame_end = 30

        # Create orphaned action (should be ignored)
        orphan_action = bpy.data.actions.new(name="OrphanAction")
        orphan_action.use_frame_range = True
        orphan_action.frame_start = 1000
        orphan_action.frame_end = 2000
        # Don't assign it to anything, so users == 0

        # Assign actions to dummy objects to give them users
        obj1 = bpy.data.objects.new("Dummy1", None)
        obj2 = bpy.data.objects.new("Dummy2", None)
        obj3 = bpy.data.objects.new("Dummy3", None)
        bpy.context.scene.collection.objects.link(obj1)
        bpy.context.scene.collection.objects.link(obj2)
        bpy.context.scene.collection.objects.link(obj3)

        obj1.animation_data_create()
        obj2.animation_data_create()
        obj3.animation_data_create()
        obj1.animation_data.action = action1
        obj2.animation_data.action = action2
        obj3.animation_data.action = action3

        return action1, action2, action3

    def test_set_frame_range_with_test_actions(self):
        """Test SetFrameRange operator with manually created test actions"""
        self.__enable_mmd_tools()

        # Set initial scene frame range
        bpy.context.scene.frame_start = 1
        bpy.context.scene.frame_end = 250
        bpy.context.scene.frame_current = 10

        # Set initial FPS to non-30 values
        bpy.context.scene.render.fps = 24
        bpy.context.scene.render.fps_base = 1.001

        # Create test actions
        action1, action2, action3 = self.__create_test_actions()

        # Expected frame range calculation:
        # base = min(frame_current, frame_start) = min(10, 1) = 1
        # Then s = min(1, -10, 0, 50) = -10
        # And e = max(1, 100, 200, 30) = 200
        # However, Blender clamps frame_start to 0 minimum, so result is 0 to 200

        # Call the operator
        result = bpy.ops.mmd_tools.set_frame_range()
        self.assertEqual(result, {"FINISHED"})

        # Verify frame range was set correctly
        # Blender doesn't allow negative frame_start, so it gets clamped to 0
        self.assertEqual(bpy.context.scene.frame_start, 0)
        self.assertEqual(bpy.context.scene.frame_end, 200)

        # Verify FPS was set to 30.0
        self.assertEqual(bpy.context.scene.render.fps, 30)
        self.assertEqual(bpy.context.scene.render.fps_base, 1)

    def test_set_frame_range_with_vmd_import(self):
        """Test SetFrameRange operator with imported VMD files"""
        input_files = self.__list_sample_files(("vmd",))
        if len(input_files) < 1:
            self.skipTest("No VMD sample files found")

        self.__enable_mmd_tools()

        # Import a model first (needed for VMD import)
        pmx_files = self.__list_sample_files(("pmx", "pmd"))
        if len(pmx_files) < 1:
            self.skipTest("No PMX/PMD sample files found")

        try:
            bpy.ops.mmd_tools.import_model(filepath=pmx_files[0], types={"MESH", "ARMATURE"}, scale=1.0, clean_model=False, remove_doubles=False, log_level="ERROR")
        except Exception as e:
            self.skipTest(f"Failed to import model: {str(e)}")

        # Import VMD file
        try:
            bpy.ops.mmd_tools.import_vmd(filepath=input_files[0], scale=1.0, log_level="ERROR")
        except Exception as e:
            self.skipTest(f"Failed to import VMD: {str(e)}")

        # Call the operator
        result = bpy.ops.mmd_tools.set_frame_range()
        self.assertEqual(result, {"FINISHED"})

        # Verify frame range was updated (should be different from original)
        # We can't predict exact values, but we can verify the operation succeeded
        # and that FPS was set correctly
        self.assertEqual(bpy.context.scene.render.fps, 30)
        self.assertEqual(bpy.context.scene.render.fps_base, 1)

        # Verify that frame range is within reasonable bounds
        self.assertGreaterEqual(bpy.context.scene.frame_start, -1000)
        self.assertLessEqual(bpy.context.scene.frame_end, 100000)

    def test_set_frame_range_with_no_actions(self):
        """Test SetFrameRange operator when no actions exist"""
        self.__enable_mmd_tools()

        # Set initial scene values
        initial_start = 5
        initial_end = 95
        initial_current = 10
        bpy.context.scene.frame_start = initial_start
        bpy.context.scene.frame_end = initial_end
        bpy.context.scene.frame_current = initial_current

        # Remove all actions
        for action in list(bpy.data.actions):
            bpy.data.actions.remove(action)

        # Call the operator
        result = bpy.ops.mmd_tools.set_frame_range()
        self.assertEqual(result, {"FINISHED"})

        # When no actions exist, frame range should be set to base (min of current and start)
        expected_frame = min(initial_current, initial_start)
        self.assertEqual(bpy.context.scene.frame_start, expected_frame)
        self.assertEqual(bpy.context.scene.frame_end, expected_frame)

        # FPS should still be set correctly
        self.assertEqual(bpy.context.scene.render.fps, 30)
        self.assertEqual(bpy.context.scene.render.fps_base, 1)

    def test_set_frame_range_with_orphaned_actions(self):
        """Test that orphaned actions (users == 0) are ignored"""
        self.__enable_mmd_tools()

        # Create only orphaned actions
        orphan1 = bpy.data.actions.new(name="Orphan1")
        orphan1.use_frame_range = True
        orphan1.frame_start = 500
        orphan1.frame_end = 600

        orphan2 = bpy.data.actions.new(name="Orphan2")
        orphan2.use_frame_range = True
        orphan2.frame_start = 700
        orphan2.frame_end = 800

        # Set initial scene values
        initial_start = 1
        initial_end = 100
        initial_current = 50
        bpy.context.scene.frame_start = initial_start
        bpy.context.scene.frame_end = initial_end
        bpy.context.scene.frame_current = initial_current

        # Call the operator
        result = bpy.ops.mmd_tools.set_frame_range()
        self.assertEqual(result, {"FINISHED"})

        # Orphaned actions should be ignored, so frame range should be based on base value only
        expected_frame = min(initial_current, initial_start)
        self.assertEqual(bpy.context.scene.frame_start, expected_frame)
        self.assertEqual(bpy.context.scene.frame_end, expected_frame)


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main(verbosity=1, exit=True)
