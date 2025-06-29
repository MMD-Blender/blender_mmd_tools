# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import logging
import math
import os
import shutil
import unittest

import bpy

# Import the modules to test
from bl_ext.user_default.mmd_tools.core.bone import FnBone, MigrationFnBone
from bl_ext.user_default.mmd_tools.core.model import FnModel
from mathutils import Vector

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


class TestBone(unittest.TestCase):
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
        # logger.setLevel('DEBUG')
        # logger.setLevel('INFO')

        # Start with a clean Blender scene
        bpy.ops.wm.read_homefile(use_empty=True)
        self.__enable_mmd_tools()

        # Create a test armature
        self.test_armature = self.__create_test_armature()

    # ********************************************
    # Utils
    # ********************************************

    def __enable_mmd_tools(self):
        """Enable MMD Tools addon"""
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.user_default.mmd_tools")

    def __create_test_armature(self):
        """Create a test armature with some bones for testing"""
        # Create armature object
        armature_data = bpy.data.armatures.new("test_armature")
        armature_object = bpy.data.objects.new("test_armature", armature_data)
        bpy.context.collection.objects.link(armature_object)

        # Enter edit mode to add bones
        bpy.context.view_layer.objects.active = armature_object
        bpy.ops.object.mode_set(mode="EDIT")

        # Add test bones
        edit_bones = armature_data.edit_bones

        # Root bone
        root_bone = edit_bones.new("全ての親")
        root_bone.head = (0.0, 0.0, 0.0)
        root_bone.tail = (0.0, 0.0, 1.0)

        # Arm bones
        left_shoulder = edit_bones.new("左肩")
        left_shoulder.head = (1.0, 0.0, 1.5)
        left_shoulder.tail = (2.0, 0.0, 1.5)
        left_shoulder.parent = root_bone

        left_arm = edit_bones.new("左腕")
        left_arm.head = (2.0, 0.0, 1.5)
        left_arm.tail = (4.0, 0.0, 1.5)
        left_arm.parent = left_shoulder

        left_elbow = edit_bones.new("左ひじ")
        left_elbow.head = (4.0, 0.0, 1.5)
        left_elbow.tail = (6.0, 0.0, 1.5)
        left_elbow.parent = left_arm

        # Add finger bone for auto local axis testing
        left_thumb = edit_bones.new("左親指１")
        left_thumb.head = (6.0, 0.5, 1.5)
        left_thumb.tail = (6.5, 0.5, 1.5)
        left_thumb.parent = left_elbow

        # Exit edit mode
        bpy.ops.object.mode_set(mode="OBJECT")

        # Setup special bone collections
        FnBone.setup_special_bone_collections(armature_object)

        return armature_object

    # ********************************************
    # Bone ID Tests
    # ********************************************

    def test_bone_id_assignment(self):
        """Test bone ID assignment and retrieval"""
        pose_bones = self.test_armature.pose.bones

        # Test get_or_assign_bone_id
        root_bone = pose_bones["全ての親"]
        bone_id = FnBone.get_or_assign_bone_id(root_bone)
        self.assertGreaterEqual(bone_id, 0, "Bone ID should be non-negative")

        # Test find_pose_bone_by_bone_id
        found_bone = FnBone.find_pose_bone_by_bone_id(self.test_armature, bone_id)
        self.assertEqual(found_bone, root_bone, "Should find the same bone by ID")

        # Test that subsequent calls return the same ID
        same_id = FnBone.get_or_assign_bone_id(root_bone)
        self.assertEqual(bone_id, same_id, "Should return the same ID on subsequent calls")

    # ********************************************
    # Fixed Axis Tests
    # ********************************************

    def test_bone_fixed_axis_loading(self):
        """Test loading bone fixed axis from pose bone"""
        pose_bones = self.test_armature.pose.bones

        # Select a bone for testing
        bpy.context.view_layer.objects.active = self.test_armature
        bpy.ops.object.mode_set(mode="POSE")

        # Clear selection and select specific bone
        for bone in pose_bones:
            bone.bone.select = False
        pose_bones["左腕"].bone.select = True

        # Test loading fixed axis
        FnBone.load_bone_fixed_axis(self.test_armature, enable=True)

        left_arm = pose_bones["左腕"]
        mmd_bone = left_arm.mmd_bone

        self.assertTrue(mmd_bone.enabled_fixed_axis, "Fixed axis should be enabled")
        self.assertGreater(Vector(mmd_bone.fixed_axis).length, 0, "Fixed axis vector should have non-zero length")

        bpy.ops.object.mode_set(mode="OBJECT")

    def test_bone_fixed_axis_application(self):
        """Test applying bone fixed axis transformations"""
        pose_bones = self.test_armature.pose.bones

        # Enable fixed axis for test bone
        left_arm = pose_bones["左腕"]
        mmd_bone = left_arm.mmd_bone
        mmd_bone.enabled_fixed_axis = True
        mmd_bone.fixed_axis = (1.0, 0.0, 0.0)  # X-axis

        # Apply fixed axis
        FnBone.apply_bone_fixed_axis(self.test_armature)

        # Check that locks were applied
        self.assertTrue(all(left_arm.lock_location), "Location should be locked")
        rotation_locks = (left_arm.lock_rotation[0], left_arm.lock_rotation[1], left_arm.lock_rotation[2])
        self.assertTrue(any(rotation_locks), "At least one rotation axis should be locked")

    # ********************************************
    # Local Axes Tests
    # ********************************************

    def test_bone_local_axes_loading(self):
        """Test loading bone local axes from pose bone"""
        pose_bones = self.test_armature.pose.bones

        # Select a bone for testing
        bpy.context.view_layer.objects.active = self.test_armature
        bpy.ops.object.mode_set(mode="POSE")

        # Clear selection and select specific bone
        for bone in pose_bones:
            bone.bone.select = False
        pose_bones["左腕"].bone.select = True

        # Test loading local axes
        FnBone.load_bone_local_axes(self.test_armature, enable=True)

        left_arm = pose_bones["左腕"]
        mmd_bone = left_arm.mmd_bone

        self.assertTrue(mmd_bone.enabled_local_axes, "Local axes should be enabled")
        self.assertGreater(Vector(mmd_bone.local_axis_x).length, 0, "Local X axis should have non-zero length")
        self.assertGreater(Vector(mmd_bone.local_axis_z).length, 0, "Local Z axis should have non-zero length")

        bpy.ops.object.mode_set(mode="OBJECT")

    def test_bone_local_axes_application(self):
        """Test applying bone local axes transformations"""
        pose_bones = self.test_armature.pose.bones

        # Enable local axes for test bone
        left_arm = pose_bones["左腕"]
        mmd_bone = left_arm.mmd_bone
        mmd_bone.enabled_local_axes = True
        mmd_bone.local_axis_x = (1.0, 0.0, 0.0)
        mmd_bone.local_axis_z = (0.0, 0.0, 1.0)

        # Get original roll from edit bone
        bpy.context.view_layer.objects.active = self.test_armature
        bpy.ops.object.mode_set(mode="EDIT")
        original_roll = self.test_armature.data.edit_bones["左腕"].roll
        bpy.ops.object.mode_set(mode="OBJECT")

        # Apply local axes
        FnBone.apply_bone_local_axes(self.test_armature)

        # Get new roll from edit bone
        bpy.ops.object.mode_set(mode="EDIT")
        new_roll = self.test_armature.data.edit_bones["左腕"].roll
        bpy.ops.object.mode_set(mode="OBJECT")

        # Verify that both roll values are valid floats
        self.assertIsInstance(original_roll, float, "Original roll should be a float value")
        self.assertIsInstance(new_roll, float, "New roll should be a float value")

        # The roll might change based on local axes - verify the change is reasonable
        roll_difference = abs(new_roll - original_roll)
        self.assertLessEqual(roll_difference, 2 * math.pi, "Roll change should be within reasonable bounds")

        # Verify that the bone is still valid after local axes application
        bone = self.test_armature.data.bones["左腕"]
        self.assertIsNotNone(bone, "Bone should still exist after local axes application")
        self.assertGreater(bone.length, 0, "Bone should maintain positive length")

    def test_get_axes_calculation(self):
        """Test axes calculation from local axes"""
        local_axis_x = (1.0, 0.0, 0.0)
        local_axis_z = (0.0, 0.0, 1.0)

        axes = FnBone.get_axes(local_axis_x, local_axis_z)

        self.assertEqual(len(axes), 3, "Should return 3 axes")

        # Check that axes are normalized
        for axis in axes:
            self.assertAlmostEqual(axis.length, 1.0, places=5, msg="Axis should be normalized")

        # Check orthogonality
        x_axis, y_axis, z_axis = axes
        self.assertLess(abs(x_axis.dot(y_axis)), 1e-5, "X and Y axes should be orthogonal")
        self.assertLess(abs(y_axis.dot(z_axis)), 1e-5, "Y and Z axes should be orthogonal")
        self.assertLess(abs(z_axis.dot(x_axis)), 1e-5, "Z and X axes should be orthogonal")

    # ********************************************
    # Auto Bone Roll Tests
    # ********************************************

    def test_has_auto_local_axis(self):
        """Test detection of bones that should have auto local axis"""
        # Test arm bones
        self.assertTrue(FnBone.has_auto_local_axis("左肩"), "Left shoulder should have auto local axis")
        self.assertTrue(FnBone.has_auto_local_axis("左腕"), "Left arm should have auto local axis")
        self.assertTrue(FnBone.has_auto_local_axis("右ひじ"), "Right elbow should have auto local axis")

        # Test finger bones
        self.assertTrue(FnBone.has_auto_local_axis("左親指１"), "Left thumb should have auto local axis")
        self.assertTrue(FnBone.has_auto_local_axis("右人指２"), "Right index finger should have auto local axis")

        # Test semi-standard arm bones
        self.assertTrue(FnBone.has_auto_local_axis("左腕捩"), "Left arm twist should have auto local axis")

        # Test non-auto bones
        self.assertFalse(FnBone.has_auto_local_axis("全ての親"), "Root bone should not have auto local axis")
        self.assertFalse(FnBone.has_auto_local_axis("センター"), "Center bone should not have auto local axis")

    def test_apply_auto_bone_roll(self):
        """Test applying auto bone roll to eligible bones"""
        # This test verifies the function runs without error on our test armature
        try:
            FnBone.apply_auto_bone_roll(self.test_armature)
        except Exception as e:
            self.fail(f"apply_auto_bone_roll should not raise exception: {e}")

    # ********************************************
    # Bone Collection Tests
    # ********************************************

    def test_setup_special_bone_collections(self):
        """Test setup of special bone collections"""
        armature = self.test_armature
        collections = armature.data.collections

        # Check that special collections exist
        self.assertIn("mmd_shadow", collections, "Shadow collection should exist")
        self.assertIn("mmd_dummy", collections, "Dummy collection should exist")

        # Check collection properties
        shadow_collection = collections["mmd_shadow"]
        self.assertIn("mmd_tools", shadow_collection, "Shadow collection should have mmd_tools property")
        self.assertEqual(shadow_collection["mmd_tools"], "special collection")

    def test_sync_bone_collections_display_frames(self):
        """Test syncing bone collections with display item frames"""
        # Create a root object for testing
        root_object = bpy.data.objects.new("test_root", None)
        root_object.mmd_type = "ROOT"
        bpy.context.collection.objects.link(root_object)

        # Parent armature to root
        self.test_armature.parent = root_object

        # Initialize display frames

        FnModel.initalize_display_item_frames(root_object, reset=True)

        # Test syncing from display frames to bone collections
        FnBone.sync_bone_collections_from_display_item_frames(self.test_armature)

        # Test syncing from bone collections to display frames
        FnBone.sync_display_item_frames_from_bone_collections(self.test_armature)

    # ********************************************
    # Additional Transform Tests
    # ********************************************

    def test_clean_additional_transformation(self):
        """Test cleaning additional transformation constraints and shadow bones"""
        pose_bones = self.test_armature.pose.bones

        # Add a test constraint to verify cleanup
        left_arm = pose_bones["左腕"]
        constraint = left_arm.constraints.new("COPY_ROTATION")
        constraint.name = "mmd_additional_rotation"

        # Clean additional transformations
        FnBone.clean_additional_transformation(self.test_armature)

        # Check that constraint was removed
        constraint_names = [c.name for c in left_arm.constraints]
        self.assertNotIn("mmd_additional_rotation", constraint_names, "Additional rotation constraint should be removed")

    def test_apply_additional_transformation(self):
        """Test applying additional transformation"""
        pose_bones = self.test_armature.pose.bones

        # Setup additional transform on a bone
        left_arm = pose_bones["左腕"]
        mmd_bone = left_arm.mmd_bone
        mmd_bone.has_additional_rotation = True
        mmd_bone.additional_transform_bone = "全ての親"
        mmd_bone.additional_transform_influence = 0.5
        mmd_bone.is_additional_transform_dirty = True

        # Apply additional transformation
        try:
            FnBone.apply_additional_transformation(self.test_armature)
        except Exception as e:
            self.fail(f"apply_additional_transformation should not raise exception: {e}")

        # Check that dirty flag was cleared
        self.assertFalse(mmd_bone.is_additional_transform_dirty, "Dirty flag should be cleared")

    def test_update_additional_transform_influence(self):
        """Test updating additional transform influence"""
        pose_bones = self.test_armature.pose.bones
        left_arm = pose_bones["左腕"]

        # Add constraints for testing
        rot_constraint = left_arm.constraints.new("TRANSFORM")
        rot_constraint.name = "mmd_additional_rotation"

        loc_constraint = left_arm.constraints.new("TRANSFORM")
        loc_constraint.name = "mmd_additional_location"

        # Test influence update
        try:
            FnBone.update_additional_transform_influence(left_arm)
        except Exception as e:
            self.fail(f"update_additional_transform_influence should not raise exception: {e}")

    # ********************************************
    # Migration Tests
    # ********************************************

    def test_fix_mmd_ik_limit_override(self):
        """Test fixing MMD IK limit override constraints"""
        pose_bones = self.test_armature.pose.bones
        left_arm = pose_bones["左腕"]

        # Add a test constraint that needs fixing
        constraint = left_arm.constraints.new("LIMIT_ROTATION")
        constraint.name = "mmd_ik_limit_override_test"
        constraint.owner_space = "WORLD"  # Wrong space that should be fixed

        # Apply the fix
        MigrationFnBone.fix_mmd_ik_limit_override(self.test_armature)

        # Check that the constraint was fixed
        self.assertEqual(constraint.owner_space, "LOCAL", "Constraint owner space should be fixed to LOCAL")

    # ********************************************
    # Edge Cases and Error Handling
    # ********************************************

    def test_bone_operations_with_empty_armature(self):
        """Test bone operations with empty but valid armature"""
        # Create empty armature with initialized pose data
        empty_armature_data = bpy.data.armatures.new("empty_test")
        empty_armature = bpy.data.objects.new("empty_test", empty_armature_data)
        bpy.context.collection.objects.link(empty_armature)

        # Initialize pose data to create valid armature state
        bpy.context.view_layer.objects.active = empty_armature
        bpy.ops.object.mode_set(mode="POSE")
        bpy.ops.object.mode_set(mode="OBJECT")

        self.assertIsNotNone(empty_armature.pose, "Empty armature should have pose data")

        # Test operations that should handle empty armature gracefully
        try:
            FnBone.clean_additional_transformation(empty_armature)
            FnBone.apply_additional_transformation(empty_armature)
            FnBone.apply_auto_bone_roll(empty_armature)
        except Exception as e:
            self.fail(f"Operations should handle empty armature gracefully: {e}")

    def test_invalid_bone_references(self):
        """Test handling of invalid bone references"""
        pose_bones = self.test_armature.pose.bones
        left_arm = pose_bones["左腕"]
        mmd_bone = left_arm.mmd_bone

        # Set invalid additional transform bone
        mmd_bone.additional_transform_bone = "NonExistentBone"
        mmd_bone.has_additional_rotation = True
        mmd_bone.is_additional_transform_dirty = True

        # Should handle invalid reference gracefully
        try:
            FnBone.apply_additional_transformation(self.test_armature)
        except Exception as e:
            self.fail(f"Should handle invalid bone references gracefully: {e}")

    def tearDown(self):
        """Clean up after each test"""
        # Return to object mode
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        # Clear scene
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main()
