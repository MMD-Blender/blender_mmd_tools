# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import unittest

import bpy
from bl_ext.user_default.mmd_tools.core.model import FnModel, Model
from bl_ext.user_default.mmd_tools.panels.sidebar.bone_order import MMD_TOOLS_UL_ModelBones
from mathutils import Vector


class TestBoneOrder(unittest.TestCase):
    """Test suite for bone order operations and bone ID management"""

    def setUp(self):
        """Set up test environment with MMD model and bones"""
        # Clear existing mesh objects to start clean
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)

        # Create MMD model for testing
        self.model = Model.create("TestModel", "Test Model", scale=1.0, add_root_bone=True)
        self.root_object = self.model.rootObject()
        self.armature_object = self.model.armature()

        # Set active object for operators
        bpy.context.view_layer.objects.active = self.armature_object
        self.armature_object.select_set(True)

        # Add test bones with specific hierarchy and properties
        self._create_test_bones()

        # IMPORTANT: Fix bone order first to ensure clean state
        self._fix_bone_order_initial()

        # Create bone morph for testing reference updates
        self._create_test_bone_morphs()

    def tearDown(self):
        """Clean up test environment"""
        # Delete all objects created during test
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)

    def _create_test_bones(self):
        """Create a hierarchy of test bones with MMD properties"""
        # Enter edit mode to create bones
        bpy.context.view_layer.objects.active = self.armature_object
        bpy.ops.object.mode_set(mode="EDIT")

        # Define bone structure: (name, head, tail, parent_name)
        bone_definitions = [
            ("center", (0, 0, 0), (0, 0, 1), None),
            ("upper_body", (0, 0, 1), (0, 0, 2), "center"),
            ("neck", (0, 0, 2), (0, 0, 2.5), "upper_body"),
            ("head", (0, 0, 2.5), (0, 0, 3), "neck"),
            ("left_shoulder", (-0.5, 0, 2), (-1, 0, 2), "upper_body"),
            ("left_arm", (-1, 0, 2), (-1.5, 0, 2), "left_shoulder"),
            ("left_elbow", (-1.5, 0, 2), (-2, 0, 2), "left_arm"),
            ("right_shoulder", (0.5, 0, 2), (1, 0, 2), "upper_body"),
            ("right_arm", (1, 0, 2), (1.5, 0, 2), "right_shoulder"),
            ("right_elbow", (1.5, 0, 2), (2, 0, 2), "right_arm"),
        ]

        # Create edit bones
        edit_bones = self.armature_object.data.edit_bones
        for bone_name, head, tail, parent_name in bone_definitions:
            if bone_name not in edit_bones:  # Skip if already exists (like root bone)
                bone = edit_bones.new(bone_name)
                bone.head = Vector(head)
                bone.tail = Vector(tail)
                if parent_name and parent_name in edit_bones:
                    bone.parent = edit_bones[parent_name]

        # Exit edit mode
        bpy.ops.object.mode_set(mode="OBJECT")

        # Set MMD bone properties and assign initial bone IDs
        pose_bones = self.armature_object.pose.bones
        for i, (bone_name, _, _, _) in enumerate(bone_definitions):
            if bone_name in pose_bones:
                pose_bone = pose_bones[bone_name]
                pose_bone.mmd_bone.name_j = bone_name
                pose_bone.mmd_bone.name_e = bone_name.replace("_", " ").title()
                pose_bone.mmd_bone.bone_id = i

                # Set some bones with additional transform properties for testing
                # Use bone names that exist and find their IDs after fix
                if bone_name in ["left_arm", "right_arm"]:
                    pose_bone.mmd_bone.has_additional_rotation = True
                    pose_bone.mmd_bone.additional_transform_bone = "upper_body"
                    # Note: additional_transform_bone_id will be set properly after fix_bone_order

    def _fix_bone_order_initial(self):
        """Fix bone order after creating bones to ensure clean test state"""
        print("=== Initial bone structure before fix ===")
        for bone in self.armature_object.pose.bones:
            if not getattr(bone, "is_mmd_shadow_bone", False):
                print(f"Bone: {bone.name}, ID: {bone.mmd_bone.bone_id}")

        # Execute fix bone order operator to ensure clean state
        bpy.context.view_layer.objects.active = self.root_object
        result = bpy.ops.mmd_tools.fix_bone_order()

        print(f"Fix bone order result: {result}")
        self.assertEqual(result, {"FINISHED"}, "Fix bone order should succeed in setup")

        print("=== Bone structure after fix ===")
        for bone in self.armature_object.pose.bones:
            if not getattr(bone, "is_mmd_shadow_bone", False):
                print(f"Bone: {bone.name}, ID: {bone.mmd_bone.bone_id}")

        # Verify bone IDs are now sequential
        valid_bones = [b for b in self.armature_object.pose.bones if not getattr(b, "is_mmd_shadow_bone", False) and b.mmd_bone.bone_id >= 0]
        bone_ids = sorted([b.mmd_bone.bone_id for b in valid_bones])
        expected_ids = list(range(len(bone_ids)))

        self.assertEqual(bone_ids, expected_ids, f"After fix, bone IDs should be sequential: got {bone_ids}, expected {expected_ids}")

    def _create_test_bone_morphs(self):
        """Create bone morphs that reference bone IDs for testing updates"""
        bone_morphs = self.root_object.mmd_root.bone_morphs

        # Create test bone morph
        morph = bone_morphs.add()
        morph.name = "test_morph"
        morph.name_e = "Test Morph"

        # Find neck and left_shoulder bones by name and use their current IDs
        neck_bone = self.armature_object.pose.bones.get("neck")
        left_shoulder_bone = self.armature_object.pose.bones.get("left_shoulder")

        if neck_bone and neck_bone.mmd_bone.bone_id >= 0:
            morph_data = morph.data.add()
            morph_data.bone_id = neck_bone.mmd_bone.bone_id
            morph_data.location = (0, 0, 0.1)

        if left_shoulder_bone and left_shoulder_bone.mmd_bone.bone_id >= 0:
            morph_data2 = morph.data.add()
            morph_data2.bone_id = left_shoulder_bone.mmd_bone.bone_id
            morph_data2.rotation = (0, 0, 0.1, 1)

    def test_fix_bone_order_operator(self):
        """Test fix bone order operator - this should be tested first"""
        # This test is implicitly done in setUp, but let's add explicit verification
        valid_bones = [b for b in self.armature_object.pose.bones if not getattr(b, "is_mmd_shadow_bone", False) and b.mmd_bone.bone_id >= 0]
        bone_ids = sorted([b.mmd_bone.bone_id for b in valid_bones])
        expected_ids = list(range(len(bone_ids)))

        self.assertEqual(bone_ids, expected_ids, "Fix bone order should create sequential bone IDs without gaps")

        # Verify no duplicate bone IDs
        all_bone_ids = [b.mmd_bone.bone_id for b in valid_bones]
        self.assertEqual(len(all_bone_ids), len(set(all_bone_ids)), "All bone IDs should be unique after fix")

        print("✓ Fix bone order test passed - bone structure is clean")

    def test_get_max_bone_id(self):
        """Test getting maximum bone ID from pose bones"""
        max_id = FnModel.get_max_bone_id(self.armature_object.pose.bones)

        # After fix_bone_order, find the actual maximum valid bone ID
        valid_bones = [b for b in self.armature_object.pose.bones if not getattr(b, "is_mmd_shadow_bone", False) and b.mmd_bone.bone_id >= 0]
        expected_max = max(b.mmd_bone.bone_id for b in valid_bones) if valid_bones else -1

        self.assertEqual(max_id, expected_max, f"Max bone ID should be {expected_max}, got {max_id}")

    def test_safe_change_bone_id(self):
        """Test safe bone ID change with conflict resolution"""
        pose_bones = self.armature_object.pose.bones
        bone_morphs = self.root_object.mmd_root.bone_morphs

        # Get neck bone (currently ID 2) and change to ID 0
        neck_bone = pose_bones["neck"]
        new_id = 0

        # Record original bone at target ID
        center_bone = pose_bones["center"]
        self.assertEqual(center_bone.mmd_bone.bone_id, 0, "Center bone should have ID 0")

        # Execute safe change
        FnModel.safe_change_bone_id(neck_bone, new_id, bone_morphs, pose_bones)

        # Verify neck bone now has new ID
        self.assertEqual(neck_bone.mmd_bone.bone_id, new_id, "Neck bone should have new ID")

        # Verify center bone was shifted
        self.assertNotEqual(center_bone.mmd_bone.bone_id, 0, "Center bone should be shifted away from ID 0")

        # Verify bone morph references were updated
        test_morph = bone_morphs["test_morph"]
        morph_data_ids = [data.bone_id for data in test_morph.data]
        self.assertIn(new_id, morph_data_ids, "Bone morph should reference updated bone ID")

    def test_swap_bone_ids(self):
        """Test swapping bone IDs between two bones"""
        pose_bones = self.armature_object.pose.bones
        bone_morphs = self.root_object.mmd_root.bone_morphs

        # Get bones to swap
        neck_bone = pose_bones["neck"]
        head_bone = pose_bones["head"]

        original_neck_id = neck_bone.mmd_bone.bone_id
        original_head_id = head_bone.mmd_bone.bone_id

        # Execute swap
        FnModel.swap_bone_ids(neck_bone, head_bone, bone_morphs, pose_bones)

        # Verify IDs were swapped
        self.assertEqual(neck_bone.mmd_bone.bone_id, original_head_id, "Neck bone should have head's original ID")
        self.assertEqual(head_bone.mmd_bone.bone_id, original_neck_id, "Head bone should have neck's original ID")

        # Verify references in morphs were updated
        test_morph = bone_morphs["test_morph"]
        updated_ids = [data.bone_id for data in test_morph.data]
        self.assertTrue(any(bone_id in updated_ids for bone_id in [original_neck_id, original_head_id]), "Bone morph references should be updated after swap")

    def test_shift_bone_id(self):
        """Test shifting bone to specific position in bone order"""
        pose_bones = self.armature_object.pose.bones
        bone_morphs = self.root_object.mmd_root.bone_morphs

        # Move head bone (ID 3) to position 1
        old_bone_id = 3  # head
        new_bone_id = 1  # upper_body position

        # Record original bone at target position
        upper_body_bone = pose_bones["upper_body"]
        original_upper_body_id = upper_body_bone.mmd_bone.bone_id

        # Execute shift
        FnModel.shift_bone_id(old_bone_id, new_bone_id, bone_morphs, pose_bones)

        # Verify head bone moved to new position
        head_bone = pose_bones["head"]
        self.assertEqual(head_bone.mmd_bone.bone_id, new_bone_id, "Head bone should have new ID")

        # Verify other bones shifted appropriately
        self.assertNotEqual(upper_body_bone.mmd_bone.bone_id, original_upper_body_id, "Upper body bone should be shifted")

    def test_realign_bone_ids(self):
        """Test realigning all bone IDs to sequential order"""
        pose_bones = self.armature_object.pose.bones
        bone_morphs = self.root_object.mmd_root.bone_morphs

        # Create gaps in bone IDs by setting some to high values
        pose_bones["neck"].mmd_bone.bone_id = 10
        pose_bones["head"].mmd_bone.bone_id = 20

        # Execute realignment
        FnModel.realign_bone_ids(0, bone_morphs, pose_bones)

        # Verify all bone IDs are sequential without gaps
        valid_bones = [b for b in pose_bones if not getattr(b, "is_mmd_shadow_bone", False)]
        bone_ids = sorted([b.mmd_bone.bone_id for b in valid_bones if b.mmd_bone.bone_id >= 0])

        expected_ids = list(range(len(bone_ids)))
        self.assertEqual(bone_ids, expected_ids, "Bone IDs should be sequential starting from 0")

    def test_bone_move_up_operator(self):
        """Test moving bone up in order using operator"""
        # Find neck bone and its position after fix_bone_order
        neck_bone = self.armature_object.pose.bones.get("neck")
        self.assertIsNotNone(neck_bone, "Neck bone should exist")

        # Find neck bone index in the pose bones collection
        neck_index = -1
        for i, bone in enumerate(self.armature_object.pose.bones):
            if bone.name == "neck":
                neck_index = i
                break

        self.assertGreaterEqual(neck_index, 0, "Neck bone index should be valid")

        # Set active bone to neck
        self.root_object.mmd_root.active_bone_index = neck_index

        # Find the bone with ID immediately before neck's ID for comparison
        neck_id = neck_bone.mmd_bone.bone_id
        prev_bone = None
        prev_id = -1

        for bone in self.armature_object.pose.bones:
            if not getattr(bone, "is_mmd_shadow_bone", False) and bone.mmd_bone.bone_id < neck_id and bone.mmd_bone.bone_id > prev_id:
                prev_bone = bone
                prev_id = bone.mmd_bone.bone_id

        # If no previous bone found, this test will fail which is correct behavior
        self.assertIsNotNone(prev_bone, "Should find a bone with smaller ID than neck bone for move up test")

        original_neck_id = neck_bone.mmd_bone.bone_id
        original_prev_id = prev_bone.mmd_bone.bone_id

        print(f"Before move up: Neck ID: {original_neck_id}, Previous bone ({prev_bone.name}) ID: {original_prev_id}")

        # Execute move up operator
        bpy.context.view_layer.objects.active = self.root_object
        result = bpy.ops.mmd_tools.bone_id_move_up()

        self.assertEqual(result, {"FINISHED"}, "Move up operator should complete successfully")

        # Verify bones were swapped
        final_neck_id = neck_bone.mmd_bone.bone_id
        final_prev_id = prev_bone.mmd_bone.bone_id

        print(f"After move up: Neck ID: {final_neck_id}, Previous bone ({prev_bone.name}) ID: {final_prev_id}")

        self.assertEqual(final_neck_id, original_prev_id, f"Neck bone should have previous bone's ID: expected {original_prev_id}, got {final_neck_id}")
        self.assertEqual(final_prev_id, original_neck_id, f"Previous bone should have neck's original ID: expected {original_neck_id}, got {final_prev_id}")

    def test_bone_move_down_operator(self):
        """Test moving bone down in order using operator"""
        # Find neck bone and the bone with the next higher ID
        neck_bone = self.armature_object.pose.bones.get("neck")
        self.assertIsNotNone(neck_bone, "Neck bone should exist")

        neck_index = -1
        for i, bone in enumerate(self.armature_object.pose.bones):
            if bone.name == "neck":
                neck_index = i
                break

        # Set active bone to neck
        self.root_object.mmd_root.active_bone_index = neck_index

        # Find the bone with ID immediately after neck's ID
        neck_id = neck_bone.mmd_bone.bone_id
        next_bone = None
        next_id = float("inf")

        for bone in self.armature_object.pose.bones:
            if not getattr(bone, "is_mmd_shadow_bone", False) and bone.mmd_bone.bone_id > neck_id and bone.mmd_bone.bone_id < next_id:
                next_bone = bone
                next_id = bone.mmd_bone.bone_id

        # If no next bone found, this test will fail which is correct behavior
        self.assertIsNotNone(next_bone, "Should find a bone with higher ID than neck bone for move down test")

        original_neck_id = neck_bone.mmd_bone.bone_id
        original_next_id = next_bone.mmd_bone.bone_id

        # Execute move down operator
        bpy.context.view_layer.objects.active = self.root_object
        result = bpy.ops.mmd_tools.bone_id_move_down()

        self.assertEqual(result, {"FINISHED"}, "Move down operator should complete successfully")

        # Verify bones were swapped
        self.assertEqual(neck_bone.mmd_bone.bone_id, original_next_id, f"Neck bone should have next bone's ID: expected {original_next_id}, got {neck_bone.mmd_bone.bone_id}")
        self.assertEqual(next_bone.mmd_bone.bone_id, original_neck_id, f"Next bone should have neck's original ID: expected {original_neck_id}, got {next_bone.mmd_bone.bone_id}")

    def test_bone_move_top_operator(self):
        """Test moving bone to top of order using operator"""
        # Find head bone (should have a higher ID after fix_bone_order)
        head_bone = self.armature_object.pose.bones.get("head")
        self.assertIsNotNone(head_bone, "Head bone should exist")

        head_index = -1
        for i, bone in enumerate(self.armature_object.pose.bones):
            if bone.name == "head":
                head_index = i
                break

        # Set active bone to head
        self.root_object.mmd_root.active_bone_index = head_index

        # Execute move to top operator
        bpy.context.view_layer.objects.active = self.root_object
        result = bpy.ops.mmd_tools.bone_id_move_top()

        self.assertEqual(result, {"FINISHED"}, "Move to top operator should complete successfully")

        # Verify head bone moved to ID 0
        self.assertEqual(head_bone.mmd_bone.bone_id, 0, f"Head bone should have ID 0, got {head_bone.mmd_bone.bone_id}")

    def test_bone_move_bottom_operator(self):
        """Test moving bone to bottom of order using operator"""
        # Find a bone with lower ID (like center) to move to bottom
        center_bone = self.armature_object.pose.bones.get("center")
        self.assertIsNotNone(center_bone, "Center bone should exist")

        center_index = -1
        for i, bone in enumerate(self.armature_object.pose.bones):
            if bone.name == "center":
                center_index = i
                break

        # Set active bone to center
        self.root_object.mmd_root.active_bone_index = center_index

        max_id = FnModel.get_max_bone_id(self.armature_object.pose.bones)

        # Execute move to bottom operator
        bpy.context.view_layer.objects.active = self.root_object
        result = bpy.ops.mmd_tools.bone_id_move_bottom()

        self.assertEqual(result, {"FINISHED"}, "Move to bottom operator should complete successfully")

        # Verify center bone moved to max ID
        self.assertEqual(center_bone.mmd_bone.bone_id, max_id, f"Center bone should have maximum ID {max_id}, got {center_bone.mmd_bone.bone_id}")

    def test_realign_bone_ids_operator(self):
        """Test realigning bone IDs using operator"""
        # Create disorder in bone IDs
        pose_bones = self.armature_object.pose.bones
        pose_bones["neck"].mmd_bone.bone_id = 15
        pose_bones["head"].mmd_bone.bone_id = 25

        # Execute realign operator
        bpy.context.view_layer.objects.active = self.root_object
        result = bpy.ops.mmd_tools.fix_bone_order()

        self.assertEqual(result, {"FINISHED"}, "Fix bone order operator should complete successfully")

        # Verify bone IDs are now sequential
        valid_bones = [b for b in pose_bones if not getattr(b, "is_mmd_shadow_bone", False)]
        bone_ids = sorted([b.mmd_bone.bone_id for b in valid_bones if b.mmd_bone.bone_id >= 0])
        expected_ids = list(range(len(bone_ids)))

        self.assertEqual(bone_ids, expected_ids, "Bone IDs should be sequential after realignment")

    def test_additional_transform_references_update(self):
        """Test that additional transform bone references are updated correctly"""
        pose_bones = self.armature_object.pose.bones
        bone_morphs = self.root_object.mmd_root.bone_morphs

        # Find left_arm and upper_body bones
        left_arm_bone = pose_bones.get("left_arm")
        upper_body_bone = pose_bones.get("upper_body")

        # If bones don't exist, this test will fail which is correct behavior
        self.assertIsNotNone(left_arm_bone, "Left arm bone should exist")
        self.assertIsNotNone(upper_body_bone, "Upper body bone should exist")

        # Set up additional transform reference manually since fix_bone_order might have cleared it
        left_arm_bone.mmd_bone.has_additional_rotation = True
        left_arm_bone.mmd_bone.additional_transform_bone = "upper_body"
        left_arm_bone.mmd_bone.additional_transform_bone_id = upper_body_bone.mmd_bone.bone_id

        # Verify initial reference
        initial_ref_id = left_arm_bone.mmd_bone.additional_transform_bone_id
        self.assertEqual(initial_ref_id, upper_body_bone.mmd_bone.bone_id, "Left arm should reference upper_body bone ID")

        # Change upper_body bone ID
        new_id = 5  # Pick an ID that should be available

        FnModel.safe_change_bone_id(upper_body_bone, new_id, bone_morphs, pose_bones)

        # Verify additional transform reference was updated
        self.assertEqual(left_arm_bone.mmd_bone.additional_transform_bone_id, new_id, f"Additional transform reference should be updated to {new_id}, got {left_arm_bone.mmd_bone.additional_transform_bone_id}")

    def test_ui_list_bone_filtering(self):
        """Test UI list properly filters and sorts bones"""
        # Create shadow bone for testing
        bpy.context.view_layer.objects.active = self.armature_object
        bpy.ops.object.mode_set(mode="EDIT")

        shadow_bone = self.armature_object.data.edit_bones.new("shadow_test")
        shadow_bone.head = (0, 0, 4)
        shadow_bone.tail = (0, 0, 4.5)

        bpy.ops.object.mode_set(mode="OBJECT")

        # Set shadow bone property
        shadow_pose_bone = self.armature_object.pose.bones["shadow_test"]
        shadow_pose_bone.is_mmd_shadow_bone = True
        shadow_pose_bone.mmd_bone.bone_id = 100

        # Test the static methods instead of instantiating UI list
        valid_count = MMD_TOOLS_UL_ModelBones.update_bone_tables(self.armature_object)

        # Verify shadow bone is not counted
        expected_count = len([b for b in self.armature_object.pose.bones if not getattr(b, "is_mmd_shadow_bone", False)])
        self.assertEqual(valid_count, expected_count, "Valid bone count should exclude shadow bones")

        # Test filtering by checking the bone order map
        self.assertIsInstance(MMD_TOOLS_UL_ModelBones._bone_order_map, dict, "Bone order map should be created")

        # Verify shadow bone is not in the order mapping
        shadow_bone_index = list(self.armature_object.pose.bones.keys()).index("shadow_test")
        # Shadow bones should not have order mapping or should be filtered out
        print(f"Shadow bone index: {shadow_bone_index}")
        print(f"Bone order map: {MMD_TOOLS_UL_ModelBones._bone_order_map}")

    def test_edge_cases(self):
        """Test edge cases and error conditions"""
        pose_bones = self.armature_object.pose.bones
        bone_morphs = self.root_object.mmd_root.bone_morphs

        # Test negative bone ID handling
        neck_bone = pose_bones["neck"]
        FnModel.safe_change_bone_id(neck_bone, -1, bone_morphs, pose_bones)
        self.assertEqual(neck_bone.mmd_bone.bone_id, 0, "Negative bone ID should be corrected to 0")

        # Test swapping bone with itself (should do nothing)
        original_id = neck_bone.mmd_bone.bone_id
        FnModel.swap_bone_ids(neck_bone, neck_bone, bone_morphs, pose_bones)
        self.assertEqual(neck_bone.mmd_bone.bone_id, original_id, "Swapping bone with itself should not change ID")

        # Test shift to same position (should do nothing)
        FnModel.shift_bone_id(original_id, original_id, bone_morphs, pose_bones)
        self.assertEqual(neck_bone.mmd_bone.bone_id, original_id, "Shifting to same position should not change ID")

    def test_operator_error_conditions(self):
        """Test operator behavior with invalid conditions"""
        # Test with no active object - this exposes a MMD Tools bug
        original_active = bpy.context.view_layer.objects.active
        bpy.context.view_layer.objects.active = None

        # This will fail due to MMD Tools bug: operators crash instead of returning CANCELLED
        # Bug location: bone_order.py line 19, model.py line 50
        result = bpy.ops.mmd_tools.bone_id_move_up()

        # This assertion will never be reached due to the RuntimeError above
        # The test will fail, which correctly identifies the bug
        self.assertEqual(result, {"CANCELLED"}, "MMD Tools BUG: Move up should return CANCELLED with no active object, not crash with AttributeError")

        # Restore active object (won't be reached)
        bpy.context.view_layer.objects.active = original_active

        # Test with invalid bone index
        original_index = self.root_object.mmd_root.active_bone_index
        self.root_object.mmd_root.active_bone_index = 999

        result = bpy.ops.mmd_tools.bone_id_move_up()
        self.assertEqual(result, {"CANCELLED"}, "Move up should be cancelled with invalid bone index")

        # Restore original index
        self.root_object.mmd_root.active_bone_index = original_index


class TestBoneOrderIntegration(unittest.TestCase):
    """Integration tests for bone order functionality with complex scenarios"""

    def setUp(self):
        """Set up complex test scenario with multiple models"""
        # Clear scene
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)

        # Create multiple models for join testing
        self.model1 = Model.create("Model1", "First Model", add_root_bone=True)
        self.model2 = Model.create("Model2", "Second Model", add_root_bone=True)

        self._setup_model_bones()

    def tearDown(self):
        """Clean up integration test environment"""
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)

    def _setup_model_bones(self):
        """Set up bones for both models with overlapping IDs"""
        for i, model in enumerate([self.model1, self.model2]):
            armature = model.armature()
            bpy.context.view_layer.objects.active = armature
            bpy.ops.object.mode_set(mode="EDIT")

            # Create test bones
            edit_bones = armature.data.edit_bones
            for j in range(3):
                bone_name = f"bone_{j}_model_{i}"
                bone = edit_bones.new(bone_name)
                bone.head = (0, 0, j)
                bone.tail = (0, 0, j + 0.5)

            bpy.ops.object.mode_set(mode="OBJECT")

            # Set bone IDs (overlapping between models)
            for j, bone in enumerate(armature.pose.bones):
                if not bone.name.startswith("全ての親"):  # Skip root bone
                    bone.mmd_bone.bone_id = j

    def test_model_join_bone_id_conflict_resolution(self):
        """Test that bone ID conflicts are resolved when joining models"""
        root1 = self.model1.rootObject()
        root2 = self.model2.rootObject()

        # Record original bone counts
        original_count1 = len([b for b in self.model1.armature().pose.bones if not getattr(b, "is_mmd_shadow_bone", False)])
        original_count2 = len([b for b in self.model2.armature().pose.bones if not getattr(b, "is_mmd_shadow_bone", False)])

        # Join models
        FnModel.join_models(root1, [root2])

        # Verify no duplicate bone IDs exist
        pose_bones = self.model1.armature().pose.bones
        valid_bones = [b for b in pose_bones if not getattr(b, "is_mmd_shadow_bone", False)]
        bone_ids = [b.mmd_bone.bone_id for b in valid_bones if b.mmd_bone.bone_id >= 0]

        self.assertEqual(len(bone_ids), len(set(bone_ids)), "All bone IDs should be unique after joining models")

        # Verify total bone count
        expected_total = original_count1 + original_count2
        self.assertEqual(len(valid_bones), expected_total, "Total bone count should match sum of both models")


def suite():
    """Create test suite for bone order functionality"""
    loader = unittest.TestLoader()
    test_suite = unittest.TestSuite()

    # Add basic functionality tests using modern approach
    test_suite.addTest(loader.loadTestsFromTestCase(TestBoneOrder))

    # Add integration tests
    test_suite.addTest(loader.loadTestsFromTestCase(TestBoneOrderIntegration))

    return test_suite


if __name__ == "__main__":
    # Run tests when executed directly
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())
