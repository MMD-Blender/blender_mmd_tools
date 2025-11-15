# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import logging
import os
import unittest

import bpy
from bl_ext.blender_org.mmd_tools import auto_scene_setup

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "samples")


class TestSceneSetup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Clean up output from previous tests"""
        output_dir = os.path.join(TESTS_DIR, "output")
        if os.path.exists(output_dir):
            for item in os.listdir(output_dir):
                if item.endswith(".OUTPUT"):
                    continue
                item_fp = os.path.join(output_dir, item)
                if os.path.isfile(item_fp):
                    os.remove(item_fp)

    def setUp(self):
        """Set up testing environment"""
        logger = logging.getLogger()
        logger.setLevel("ERROR")

        # Reset Blender scene to default state
        bpy.ops.wm.read_homefile(use_empty=True)

        # Enable MMD tools addon
        self.__enable_mmd_tools()

    # ********************************************
    # Utils
    # ********************************************

    def __enable_mmd_tools(self):
        """Enable MMD Tools addon for testing"""
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.blender_org.mmd_tools")

    def __create_test_actions(self):
        """Create test actions with frame ranges for testing setupFrameRanges"""
        # Create first action with frame range 1-100
        action1 = bpy.data.actions.new(name="TestAction1")
        action1.frame_range = (1.0, 100.0)
        action1.use_frame_range = True

        # Create second action with frame range 50-150
        action2 = bpy.data.actions.new(name="TestAction2")
        action2.frame_range = (50.0, 150.0)
        action2.use_frame_range = True

        # Create third action with frame range 75-200
        action3 = bpy.data.actions.new(name="TestAction3")
        action3.frame_range = (75.0, 200.0)
        action3.use_frame_range = False

        return action1, action2, action3

    def __create_rigidbody_world(self):
        """Create a rigid body world for testing - using direct scene property"""
        scene = bpy.context.scene

        if scene.rigidbody_world:
            bpy.ops.rigidbody.world_remove()

        # Create a dummy object to establish proper context
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object

        # Set proper context and add rigidbody world
        bpy.ops.rigidbody.world_add()

        # Clean up dummy object
        bpy.data.objects.remove(cube, do_unlink=True)

        rigidbody_world = scene.rigidbody_world
        self.assertIsNotNone(rigidbody_world, "Failed to create rigid body world")
        return rigidbody_world

    # ********************************************
    # Frame Range Tests
    # ********************************************

    def test_setupFrameRanges_empty_scene(self):
        """Test setupFrameRanges with no actions in the scene"""
        # Set initial scene frame values
        initial_current = 10
        initial_start = 5

        bpy.context.scene.frame_current = initial_current
        bpy.context.scene.frame_start = initial_start

        # Call setupFrameRanges
        auto_scene_setup.setupFrameRanges()

        # Verify that function completes without error
        current_start = bpy.context.scene.frame_start
        current_end = bpy.context.scene.frame_end

        # Basic sanity checks
        self.assertIsInstance(current_start, int)
        self.assertIsInstance(current_end, int)
        self.assertLessEqual(current_start, current_end)

    def test_setupFrameRanges_single_action(self):
        """Test setupFrameRanges with a single action"""
        # Set initial scene frame values
        bpy.context.scene.frame_current = 10
        bpy.context.scene.frame_start = 5

        # Create single test action
        action = bpy.data.actions.new(name="SingleTestAction")
        action.frame_range = (20.0, 80.0)
        action.use_frame_range = True

        # Call setupFrameRanges
        auto_scene_setup.setupFrameRanges()

        # Verify function execution and basic constraints
        final_start = bpy.context.scene.frame_start
        final_end = bpy.context.scene.frame_end

        self.assertIsInstance(final_start, int)
        self.assertIsInstance(final_end, int)
        self.assertLessEqual(final_start, final_end)

    def test_action_use_frame_range_behavior(self):
        """Test that we understand action.frame_range behavior correctly"""
        # Test use_frame_range = True behavior
        action_true = bpy.data.actions.new(name="ActionTrue")
        action_true.use_frame_range = True
        action_true.frame_range = (10.0, 90.0)

        self.assertAlmostEqual(action_true.frame_range[0], 10.0)
        self.assertAlmostEqual(action_true.frame_range[1], 90.0)

        # Test use_frame_range = False behavior (empty action)
        action_false = bpy.data.actions.new(name="ActionFalse")
        action_false.use_frame_range = False

        # Empty action with use_frame_range=False should return (0,0)
        self.assertAlmostEqual(action_false.frame_range[0], 0.0)
        self.assertAlmostEqual(action_false.frame_range[1], 0.0)

        # Setting frame_range while use_frame_range=False should work
        action_false.frame_range = (20.0, 80.0)
        self.assertAlmostEqual(action_false.frame_range[0], 20.0)
        self.assertAlmostEqual(action_false.frame_range[1], 80.0)

    def test_setupFrameRanges_preserves_use_frame_range_states(self):
        """Test that setupFrameRanges preserves original use_frame_range states"""
        bpy.context.scene.frame_current = 25
        bpy.context.scene.frame_start = 10
        bpy.context.scene.frame_end = 50

        print(f"BEFORE: frame_start={bpy.context.scene.frame_start}, frame_end={bpy.context.scene.frame_end}")

        def create_action(name, frame_range, use_frame_range):
            """Create non-orphaned action"""
            action = bpy.data.actions.new(name=name)
            if frame_range:
                action.frame_range = frame_range
            action.use_frame_range = use_frame_range

            bpy.ops.mesh.primitive_cube_add()
            obj = bpy.context.active_object
            if not obj.animation_data:
                obj.animation_data_create()
            obj.animation_data.action = action
            return action

        # Create non-orphaned actions
        action1 = create_action("Action1", (1.0, 100.0), True)
        action2 = create_action("Action2", (75.0, 200.0), True)
        action3 = create_action("Action3", None, False)

        # Verify actions have users
        self.assertGreater(action1.users, 0)
        self.assertGreater(action2.users, 0)
        self.assertGreater(action3.users, 0)

        # Record states before
        before = [a.use_frame_range for a in (action1, action2, action3)]

        # Call setupFrameRanges
        auto_scene_setup.setupFrameRanges()

        # Record states after
        after = [a.use_frame_range for a in (action1, action2, action3)]

        # Verify states restored
        self.assertEqual(before, after, "use_frame_range states should be restored")

        print(f"AFTER: frame_start={bpy.context.scene.frame_start}, frame_end={bpy.context.scene.frame_end}")

        # Verify frame range calculation
        self.assertIn(bpy.context.scene.frame_start, (0, 1))
        self.assertEqual(bpy.context.scene.frame_end, 200)

    def test_setupFrameRanges_toggle_mechanism_detailed(self):
        """Test the detailed toggle mechanism of setupFrameRanges"""
        bpy.context.scene.frame_current = 50
        bpy.context.scene.frame_start = 30

        # Create an action with specific initial state
        action = bpy.data.actions.new(name="ToggleTestAction")
        action.use_frame_range = True
        action.frame_range = (10.0, 90.0)

        # Add some keyframes to test False state behavior
        fcurve = action.fcurves.new(data_path="location", index=0)
        fcurve.keyframe_points.add(2)
        fcurve.keyframe_points[0].co = (5.0, 0.0)  # keyframe at frame 5
        fcurve.keyframe_points[1].co = (95.0, 1.0)  # keyframe at frame 95

        # Record initial state
        initial_use_frame_range = action.use_frame_range
        initial_frame_range = tuple(action.frame_range)

        print(f"Initial: use_frame_range={initial_use_frame_range}, frame_range={initial_frame_range}")

        # Manually test the toggle behavior that setupFrameRanges does
        # First read (current state)
        first_range = tuple(action.frame_range)
        print(f"First read (use_frame_range={action.use_frame_range}): {first_range}")

        # Toggle
        action.use_frame_range = not action.use_frame_range

        # Second read (toggled state)
        second_range = tuple(action.frame_range)
        print(f"Second read (use_frame_range={action.use_frame_range}): {second_range}")

        # Restore
        action.use_frame_range = not action.use_frame_range

        # Final state
        final_use_frame_range = action.use_frame_range
        final_frame_range = tuple(action.frame_range)

        print(f"Final: use_frame_range={final_use_frame_range}, frame_range={final_frame_range}")

        # Verify restoration worked
        self.assertEqual(final_use_frame_range, initial_use_frame_range)
        self.assertEqual(final_frame_range, initial_frame_range)

        # Now test setupFrameRanges does the same thing
        auto_scene_setup.setupFrameRanges()

        # Verify setupFrameRanges restored the state correctly
        self.assertEqual(action.use_frame_range, initial_use_frame_range)
        # Note: frame_range might change due to the internal logic, but use_frame_range should be restored

    def test_setupFrameRanges_with_empty_and_keyed_actions(self):
        """Test setupFrameRanges with mix of empty and keyed actions"""
        bpy.context.scene.frame_current = 20
        bpy.context.scene.frame_start = 15

        # Empty action with use_frame_range = True
        empty_action_true = bpy.data.actions.new(name="EmptyTrue")
        empty_action_true.use_frame_range = True
        empty_action_true.frame_range = (40.0, 80.0)

        # Empty action with use_frame_range = False
        empty_action_false = bpy.data.actions.new(name="EmptyFalse")
        empty_action_false.use_frame_range = False
        # Don't set frame_range to keep it truly empty

        # Action with keyframes
        keyed_action = bpy.data.actions.new(name="KeyedAction")
        fcurve = keyed_action.fcurves.new(data_path="location", index=0)
        fcurve.keyframe_points.add(2)
        fcurve.keyframe_points[0].co = (60.0, 0.0)
        fcurve.keyframe_points[1].co = (120.0, 1.0)
        keyed_action.use_frame_range = False  # Use keyframe-based range

        # Record before states
        before_states = {"empty_true": empty_action_true.use_frame_range, "empty_false": empty_action_false.use_frame_range, "keyed": keyed_action.use_frame_range}

        print("=== Action states BEFORE ===")
        for name, state in before_states.items():
            print(f"{name}: {state}")

        print("=== Frame ranges BEFORE ===")
        print(f"empty_true: {empty_action_true.frame_range}")
        print(f"empty_false: {empty_action_false.frame_range}")
        print(f"keyed: {keyed_action.frame_range}")

        # Call setupFrameRanges
        auto_scene_setup.setupFrameRanges()

        # Record after states
        after_states = {"empty_true": empty_action_true.use_frame_range, "empty_false": empty_action_false.use_frame_range, "keyed": keyed_action.use_frame_range}

        print("=== Action states AFTER ===")
        for name, state in after_states.items():
            print(f"{name}: {state}")

        print("=== Frame ranges AFTER ===")
        print(f"empty_true: {empty_action_true.frame_range}")
        print(f"empty_false: {empty_action_false.frame_range}")
        print(f"keyed: {keyed_action.frame_range}")

        # Verify all states were restored
        for action_name in before_states:
            self.assertEqual(after_states[action_name], before_states[action_name], f"{action_name} use_frame_range state should be restored")

        # Verify scene frame range was calculated
        scene_start = bpy.context.scene.frame_start
        scene_end = bpy.context.scene.frame_end

        print(f"Final scene range: {scene_start} - {scene_end}")

        self.assertIsInstance(scene_start, int)
        self.assertIsInstance(scene_end, int)
        self.assertLessEqual(scene_start, scene_end)

    def test_setupFrameRanges_with_rigidbody_world(self):
        """Test setupFrameRanges updates rigid body world point cache when present"""
        # Create rigid body world
        rigidbody_world = self.__create_rigidbody_world()
        point_cache = rigidbody_world.point_cache

        # Set initial values
        bpy.context.scene.frame_current = 15
        bpy.context.scene.frame_start = 8

        # Create test action
        action = bpy.data.actions.new(name="RigidBodyTestAction")
        action.frame_range = (5.0, 120.0)
        action.use_frame_range = True

        # Call setupFrameRanges
        auto_scene_setup.setupFrameRanges()

        # Verify point cache frame range was updated to match scene
        scene_start = bpy.context.scene.frame_start
        scene_end = bpy.context.scene.frame_end

        self.assertEqual(point_cache.frame_start, scene_start)
        self.assertEqual(point_cache.frame_end, scene_end)

    def test_setupFrameRanges_toggle_behavior(self):
        """Test that setupFrameRanges properly toggles use_frame_range to capture both VMD ranges"""
        # Create action that will be toggled
        action = bpy.data.actions.new(name="ToggleTestAction")
        action.frame_range = (30.0, 90.0)
        initial_use_frame_range = True
        action.use_frame_range = initial_use_frame_range

        # Set scene values
        bpy.context.scene.frame_current = 20
        bpy.context.scene.frame_start = 15

        # Call setupFrameRanges
        auto_scene_setup.setupFrameRanges()

        # Verify use_frame_range was restored to original state
        self.assertEqual(action.use_frame_range, initial_use_frame_range)

    # ********************************************
    # FPS Tests
    # ********************************************

    def test_setupFps_sets_correct_values(self):
        """Test that setupFps sets the correct FPS values"""
        # Set different initial values
        render = bpy.context.scene.render
        render.fps = 24
        render.fps_base = 1.001

        # Call setupFps
        auto_scene_setup.setupFps()

        # Verify correct values are set
        self.assertEqual(render.fps, 30, "FPS should be set to 30")
        self.assertEqual(render.fps_base, 1, "FPS base should be set to 1")

    def test_setupFps_idempotent(self):
        """Test that setupFps can be called multiple times without issues"""
        # Call setupFps multiple times
        auto_scene_setup.setupFps()
        auto_scene_setup.setupFps()
        auto_scene_setup.setupFps()

        # Verify values remain correct
        render = bpy.context.scene.render
        self.assertEqual(render.fps, 30)
        self.assertEqual(render.fps_base, 1)

    # ********************************************
    # Integration Tests
    # ********************************************

    def test_complete_scene_setup(self):
        """Test remaining setup functions work together correctly"""
        # Create test actions
        action1, action2, action3 = self.__create_test_actions()

        # Set initial scene state
        bpy.context.scene.frame_current = 35
        bpy.context.scene.frame_start = 20
        bpy.context.scene.render.fps = 25
        bpy.context.scene.render.fps_base = 1.001

        # Apply available setup functions
        auto_scene_setup.setupFrameRanges()
        auto_scene_setup.setupFps()

        # Verify frame ranges were processed
        final_start = bpy.context.scene.frame_start
        final_end = bpy.context.scene.frame_end
        self.assertIsInstance(final_start, int)
        self.assertIsInstance(final_end, int)
        self.assertLessEqual(final_start, final_end)

        # Verify FPS settings
        render = bpy.context.scene.render
        self.assertEqual(render.fps, 30)
        self.assertEqual(render.fps_base, 1)

    def test_edge_case_negative_frames(self):
        """Test setupFrameRanges handles negative frame numbers correctly"""
        # Set scene with negative frame values
        bpy.context.scene.frame_current = -10
        bpy.context.scene.frame_start = -5

        # Create action with negative frames
        action = bpy.data.actions.new(name="NegativeFrameAction")
        action.frame_range = (-20.0, 50.0)
        action.use_frame_range = True

        # Call setupFrameRanges
        auto_scene_setup.setupFrameRanges()

        # Verify function executes without error
        final_start = bpy.context.scene.frame_start
        final_end = bpy.context.scene.frame_end

        self.assertIsInstance(final_start, int)
        self.assertIsInstance(final_end, int)
        self.assertLessEqual(final_start, final_end)

        # Document the actual behavior for future reference
        print(f"Negative frame test: start={final_start}, end={final_end}")

    def test_fractional_frame_rounding(self):
        """Test that setupFrameRanges properly handles fractional frame values in actions"""
        # Set integer frame values (scene properties require integers)
        bpy.context.scene.frame_current = 10
        bpy.context.scene.frame_start = 5

        # Create action with fractional frames (actions can have float frame ranges)
        action = bpy.data.actions.new(name="FractionalFrameAction")
        action.frame_range = (1.2, 99.8)
        action.use_frame_range = True

        # Call setupFrameRanges
        auto_scene_setup.setupFrameRanges()

        # Verify values are properly rounded/converted to integers
        final_start = bpy.context.scene.frame_start
        final_end = bpy.context.scene.frame_end

        self.assertIsInstance(final_start, int)
        self.assertIsInstance(final_end, int)
        self.assertLessEqual(final_start, final_end)

    # ********************************************
    # Removed Functions Tests
    # ********************************************

    def test_setupLighting_function_removed(self):
        """Test that setupLighting function has been properly removed"""
        # Verify function no longer exists in the module
        self.assertFalse(hasattr(auto_scene_setup, "setupLighting"), "setupLighting function should be removed for Blender 4.x compatibility")

    def test_action_frame_range_behavior(self):
        """Test the actual behavior of action.frame_range with use_frame_range toggle"""
        # Create action
        action = bpy.data.actions.new(name="TestAction")

        # Test with use_frame_range = True
        action.use_frame_range = True
        action.frame_range = (75.0, 200.0)

        print(f"use_frame_range=True: {action.frame_range}")

        # Test with use_frame_range = False
        action.use_frame_range = False
        print(f"use_frame_range=False: {action.frame_range}")

        # Test after setting frame_range while False
        action.frame_range = (75.0, 200.0)
        print(f"After setting range while False: {action.frame_range}")


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main(verbosity=1, exit=True)
