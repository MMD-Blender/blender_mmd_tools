# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import logging
import os
import shutil
import unittest

import bpy
from bl_ext.user_default.mmd_tools.core.model import Model
from bl_ext.user_default.mmd_tools.utils import ItemOp

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


class TestDisplaySystem(unittest.TestCase):
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

        # Clear existing scene
        bpy.ops.wm.read_homefile(use_empty=True)

        # Enable MMD Tools addon
        self.__enable_mmd_tools()

        # Create test model
        self.__create_test_model()

    def tearDown(self):
        """Clean up after each test"""
        # Clear scene
        bpy.ops.wm.read_homefile(use_empty=True)

    # ********************************************
    # Utils
    # ********************************************

    def __enable_mmd_tools(self):
        """Enable MMD Tools addon"""
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.user_default.mmd_tools")

    def __create_test_model(self):
        """Create a test MMD model with basic structure"""
        # Create model
        self.model = Model.create("TestModel", "Test Model", scale=1.0, add_root_bone=True)
        self.root_object = self.model.rootObject()
        self.armature_object = self.model.armature()

        # Create test bones
        bpy.context.view_layer.objects.active = self.armature_object
        bpy.ops.object.mode_set(mode="EDIT")

        # Add test bones
        armature_data = self.armature_object.data
        test_bone_1 = armature_data.edit_bones.new("TestBone1")
        test_bone_1.head = (0.0, 0.0, 1.0)
        test_bone_1.tail = (0.0, 0.0, 2.0)

        test_bone_2 = armature_data.edit_bones.new("TestBone2")
        test_bone_2.head = (1.0, 0.0, 1.0)
        test_bone_2.tail = (1.0, 0.0, 2.0)

        bpy.ops.object.mode_set(mode="OBJECT")

        # Set bone properties
        pose_bones = self.armature_object.pose.bones
        pose_bones["TestBone1"].mmd_bone.name_j = "テストボーン1"
        pose_bones["TestBone1"].mmd_bone.name_e = "TestBone1"
        pose_bones["TestBone2"].mmd_bone.name_j = "テストボーン2"
        pose_bones["TestBone2"].mmd_bone.name_e = "TestBone2"

        # Create test morphs
        mmd_root = self.root_object.mmd_root

        # Add vertex morph
        vertex_morph = mmd_root.vertex_morphs.add()
        vertex_morph.name = "TestVertexMorph"
        vertex_morph.name_e = "Test Vertex Morph"
        vertex_morph.category = "EYE"

        # Add bone morph
        bone_morph = mmd_root.bone_morphs.add()
        bone_morph.name = "TestBoneMorph"
        bone_morph.name_e = "Test Bone Morph"
        bone_morph.category = "OTHER"

        # Add material morph
        material_morph = mmd_root.material_morphs.add()
        material_morph.name = "TestMaterialMorph"
        material_morph.name_e = "Test Material Morph"
        material_morph.category = "OTHER"

        # Add UV morph
        uv_morph = mmd_root.uv_morphs.add()
        uv_morph.name = "TestUVMorph"
        uv_morph.name_e = "Test UV Morph"
        uv_morph.category = "OTHER"

        # Add group morph
        group_morph = mmd_root.group_morphs.add()
        group_morph.name = "TestGroupMorph"
        group_morph.name_e = "Test Group Morph"
        group_morph.category = "OTHER"

        # Initialize display frames
        self.model.initialDisplayFrames(reset=True)

        # Set active object for operations
        bpy.context.view_layer.objects.active = self.root_object

    def __get_display_frames(self):
        """Get display frames collection from model"""
        return self.root_object.mmd_root.display_item_frames

    def __get_current_frame(self):
        """Get currently active display frame"""
        mmd_root = self.root_object.mmd_root
        frames = mmd_root.display_item_frames
        active_index = mmd_root.active_display_item_frame
        return ItemOp.get_by_index(frames, active_index)

    def __set_active_frame(self, frame_index):
        """Set active display frame by index"""
        self.root_object.mmd_root.active_display_item_frame = frame_index

    def __set_active_item_in_frame(self, frame, item_index):
        """Set active item in a frame"""
        frame.active_item = item_index

    def __set_active_morph(self, morph_type, morph_index):
        """Set active morph for testing"""
        mmd_root = self.root_object.mmd_root
        mmd_root.active_morph_type = morph_type
        mmd_root.active_morph = morph_index

    def __set_active_bone_keep_armature_active(self, bone_name):
        """Set active bone and keep armature active for operation (Method 2)"""
        # Set up bone selection in pose mode
        bpy.context.view_layer.objects.active = self.armature_object
        bpy.ops.object.mode_set(mode="POSE")

        if bone_name in self.armature_object.data.bones:
            bone = self.armature_object.data.bones[bone_name]
            bone.select = True
            self.armature_object.data.bones.active = bone

        # Keep armature active and stay in pose mode for operation
        # Don't switch back to root object

    def __ensure_root_active(self):
        """Ensure root object is active for display operations"""
        bpy.context.view_layer.objects.active = self.root_object

    # ********************************************
    # Display Frame Tests
    # ********************************************

    def test_display_frame_initialization(self):
        """Test that display frames are properly initialized"""
        frames = self.__get_display_frames()

        # Should have at least 2 default frames: Root and 表情
        self.assertGreaterEqual(len(frames), 2)

        # Check default frames exist
        root_frame = frames.get("Root")
        self.assertIsNotNone(root_frame, "Root frame should exist")
        self.assertEqual(root_frame.name, "Root")
        self.assertEqual(root_frame.name_e, "Root")
        self.assertTrue(root_frame.is_special, "Root frame should be special")

        facial_frame = frames.get("表情")
        self.assertIsNotNone(facial_frame, "Facial frame should exist")
        self.assertEqual(facial_frame.name, "表情")
        self.assertEqual(facial_frame.name_e, "Facial")
        self.assertTrue(facial_frame.is_special, "Facial frame should be special")

    def test_add_display_frame(self):
        """Test adding new display frames"""
        frames = self.__get_display_frames()
        initial_count = len(frames)

        self.__ensure_root_active()

        # Add new frame using operator
        result = bpy.ops.mmd_tools.display_item_frame_add()

        self.assertEqual(result, {"FINISHED"})
        self.assertEqual(len(frames), initial_count + 1)

        # Check new frame properties
        new_frame = frames[-1]
        self.assertEqual(new_frame.name, "Display Frame")
        self.assertFalse(new_frame.is_special, "New frame should not be special")

    def test_remove_display_frame(self):
        """Test removing display frames"""
        frames = self.__get_display_frames()

        # Add a frame to remove
        test_frame = frames.add()
        test_frame.name = "TestFrame"
        test_frame.is_special = False
        frame_count = len(frames)

        # Set it as active
        self.__set_active_frame(len(frames) - 1)
        self.__ensure_root_active()

        # Remove the frame
        result = bpy.ops.mmd_tools.display_item_frame_remove()

        self.assertEqual(result, {"FINISHED"})
        self.assertEqual(len(frames), frame_count - 1)

    def test_remove_special_frame_clears_data(self):
        """Test that removing special frames only clears their data"""
        frames = self.__get_display_frames()
        facial_frame = frames.get("表情")

        # Add some data to facial frame
        item = facial_frame.data.add()
        item.type = "MORPH"
        item.name = "TestMorph"

        initial_count = len(frames)
        facial_index = frames.find("表情")
        self.__set_active_frame(facial_index)
        self.__ensure_root_active()

        # Try to remove special frame
        result = bpy.ops.mmd_tools.display_item_frame_remove()

        self.assertEqual(result, {"FINISHED"})
        # Frame count should remain the same
        self.assertEqual(len(frames), initial_count)
        # But data should be cleared
        self.assertEqual(len(facial_frame.data), 0)
        self.assertEqual(facial_frame.active_item, 0)

    def test_move_display_frame(self):
        """Test moving display frames"""
        frames = self.__get_display_frames()

        # Add test frames
        frame1 = frames.add()
        frame1.name = "Frame1"
        frame1.is_special = False

        frame2 = frames.add()
        frame2.name = "Frame2"
        frame2.is_special = False

        frame1_index = len(frames) - 2
        frame2_index = len(frames) - 1

        # Set active to frame1
        self.__set_active_frame(frame1_index)
        self.__ensure_root_active()

        # Move frame down
        result = bpy.ops.mmd_tools.display_item_frame_move(type="DOWN")

        self.assertEqual(result, {"FINISHED"})

        # Verify the frame moved
        moved_frame = frames[frame2_index]
        self.assertEqual(moved_frame.name, "Frame1")

    def test_move_special_frame_no_effect(self):
        """Test that special frames cannot be moved"""
        frames = self.__get_display_frames()
        root_index = frames.find("Root")
        original_index = root_index

        self.__set_active_frame(root_index)
        self.__ensure_root_active()

        # Try to move special frame
        result = bpy.ops.mmd_tools.display_item_frame_move(type="DOWN")

        self.assertEqual(result, {"FINISHED"})

        # Special frame should not have moved
        current_index = frames.find("Root")
        self.assertEqual(current_index, original_index)

    # ********************************************
    # Display Item Tests
    # ********************************************

    def test_add_bone_display_item(self):
        """Test adding bone display items"""
        frames = self.__get_display_frames()
        root_frame = frames.get("Root")
        initial_item_count = len(root_frame.data)

        # Set active bone and keep armature active
        self.__set_active_bone_keep_armature_active("TestBone1")

        # Set active frame to Root
        self.__set_active_frame(frames.find("Root"))

        # Add bone item (armature is still active)
        result = bpy.ops.mmd_tools.display_item_add()

        self.assertEqual(result, {"FINISHED"})
        self.assertEqual(len(root_frame.data), initial_item_count + 1)

        # Check new item - should now have correct bone name
        new_item = root_frame.data[-1]
        self.assertEqual(new_item.type, "BONE")
        self.assertEqual(new_item.name, "TestBone1")

    def test_add_morph_display_item(self):
        """Test adding morph display items"""
        frames = self.__get_display_frames()
        facial_frame = frames.get("表情")
        initial_item_count = len(facial_frame.data)

        # Set active morph
        self.__set_active_morph("vertex_morphs", 0)

        # Set active frame to 表情
        self.__set_active_frame(frames.find("表情"))
        self.__ensure_root_active()

        # Add morph item
        result = bpy.ops.mmd_tools.display_item_add()

        self.assertEqual(result, {"FINISHED"})
        self.assertEqual(len(facial_frame.data), initial_item_count + 1)

        # Check new item
        new_item = facial_frame.data[-1]
        self.assertEqual(new_item.type, "MORPH")
        self.assertEqual(new_item.name, "TestVertexMorph")
        self.assertEqual(new_item.morph_type, "vertex_morphs")

    def test_remove_display_item(self):
        """Test removing display items"""
        frames = self.__get_display_frames()
        root_frame = frames.get("Root")

        # Add test item
        item = root_frame.data.add()
        item.type = "BONE"
        item.name = "TestBone1"
        item_count = len(root_frame.data)

        # Set active frame and item
        self.__set_active_frame(frames.find("Root"))
        self.__set_active_item_in_frame(root_frame, len(root_frame.data) - 1)
        self.__ensure_root_active()

        # Remove item
        result = bpy.ops.mmd_tools.display_item_remove(all=False)

        self.assertEqual(result, {"FINISHED"})
        self.assertEqual(len(root_frame.data), item_count - 1)

    def test_remove_all_display_items(self):
        """Test removing all display items"""
        frames = self.__get_display_frames()
        root_frame = frames.get("Root")

        # Add test items
        for i in range(3):
            item = root_frame.data.add()
            item.type = "BONE"
            item.name = f"TestBone{i}"

        # Set active frame
        self.__set_active_frame(frames.find("Root"))
        self.__ensure_root_active()

        # Remove all items
        result = bpy.ops.mmd_tools.display_item_remove(all=True)

        self.assertEqual(result, {"FINISHED"})
        self.assertEqual(len(root_frame.data), 0)
        self.assertEqual(root_frame.active_item, 0)

    def test_move_display_item(self):
        """Test moving display items"""
        frames = self.__get_display_frames()
        root_frame = frames.get("Root")

        # Clear existing items first
        root_frame.data.clear()

        # Add test items
        item1 = root_frame.data.add()
        item1.type = "BONE"
        item1.name = "TestBone1"

        item2 = root_frame.data.add()
        item2.type = "BONE"
        item2.name = "TestBone2"

        # Set active frame and first item
        self.__set_active_frame(frames.find("Root"))
        self.__set_active_item_in_frame(root_frame, 0)
        self.__ensure_root_active()

        # Move item down
        result = bpy.ops.mmd_tools.display_item_move(type="DOWN")

        self.assertEqual(result, {"FINISHED"})

        # Verify items moved
        self.assertEqual(root_frame.data[0].name, "TestBone2")
        self.assertEqual(root_frame.data[1].name, "TestBone1")

    # ********************************************
    # Find and Select Tests
    # ********************************************

    def test_find_bone_display_item(self):
        """Test finding bone display items"""
        frames = self.__get_display_frames()
        root_frame = frames.get("Root")

        # Add test bone item
        item = root_frame.data.add()
        item.type = "BONE"
        item.name = "TestBone1"
        test_item_index = len(root_frame.data) - 1

        # Set active bone and keep armature active
        self.__set_active_bone_keep_armature_active("TestBone1")

        # Find bone item
        result = bpy.ops.mmd_tools.display_item_find(type="BONE")

        self.assertEqual(result, {"FINISHED"})

        # Check that correct frame and item are active
        mmd_root = self.root_object.mmd_root
        self.assertEqual(mmd_root.active_display_item_frame, frames.find("Root"))
        self.assertEqual(root_frame.active_item, test_item_index)

    def test_find_morph_display_item(self):
        """Test finding morph display items"""
        frames = self.__get_display_frames()
        facial_frame = frames.get("表情")

        # Add test morph item
        item = facial_frame.data.add()
        item.type = "MORPH"
        item.name = "TestVertexMorph"
        item.morph_type = "vertex_morphs"
        test_item_index = len(facial_frame.data) - 1

        # Set active morph
        self.__set_active_morph("vertex_morphs", 0)
        self.__ensure_root_active()

        # Find morph item
        result = bpy.ops.mmd_tools.display_item_find(type="MORPH")

        self.assertEqual(result, {"FINISHED"})

        # Check that correct frame and item are active
        mmd_root = self.root_object.mmd_root
        self.assertEqual(mmd_root.active_display_item_frame, frames.find("表情"))
        self.assertEqual(facial_frame.active_item, test_item_index)

    def test_find_nonexistent_item(self):
        """Test finding nonexistent display items"""
        # Set active bone that doesn't have display item
        self.__set_active_bone_keep_armature_active("TestBone2")

        # Try to find bone item
        result = bpy.ops.mmd_tools.display_item_find(type="BONE")

        # Should return FINISHED even if item not found
        self.assertEqual(result, {"FINISHED"})

    def test_select_current_bone_item(self):
        """Test selecting current bone display item"""
        frames = self.__get_display_frames()
        root_frame = frames.get("Root")

        # Add test bone item
        item = root_frame.data.add()
        item.type = "BONE"
        item.name = "TestBone1"

        # Set active frame and item
        self.__set_active_frame(frames.find("Root"))
        self.__set_active_item_in_frame(root_frame, len(root_frame.data) - 1)
        self.__ensure_root_active()

        # Select current item
        result = bpy.ops.mmd_tools.display_item_select_current()

        self.assertEqual(result, {"FINISHED"})

    def test_select_current_morph_item(self):
        """Test selecting current morph display item"""
        frames = self.__get_display_frames()
        facial_frame = frames.get("表情")

        # Add test morph item
        item = facial_frame.data.add()
        item.type = "MORPH"
        item.name = "TestVertexMorph"
        item.morph_type = "vertex_morphs"

        # Set active frame and item
        self.__set_active_frame(frames.find("表情"))
        self.__set_active_item_in_frame(facial_frame, len(facial_frame.data) - 1)
        self.__ensure_root_active()

        # Select current item
        result = bpy.ops.mmd_tools.display_item_select_current()

        self.assertEqual(result, {"FINISHED"})

        # Check that morph is selected
        mmd_root = self.root_object.mmd_root
        self.assertEqual(mmd_root.active_morph_type, "vertex_morphs")

    # ********************************************
    # Quick Setup Tests
    # ********************************************

    def test_quick_setup_reset(self):
        """Test quick setup reset functionality"""
        frames = self.__get_display_frames()

        # Add some custom frames
        custom_frame = frames.add()
        custom_frame.name = "CustomFrame"
        custom_frame.is_special = False

        initial_frame_count = len(frames)
        self.__ensure_root_active()

        # Reset display frames
        result = bpy.ops.mmd_tools.display_item_quick_setup(type="RESET")

        self.assertEqual(result, {"FINISHED"})

        # Should have only default frames now
        self.assertLessEqual(len(frames), initial_frame_count)

        # Default frames should still exist
        self.assertIsNotNone(frames.get("Root"))
        self.assertIsNotNone(frames.get("表情"))

    def test_quick_setup_facial(self):
        """Test quick setup facial functionality"""
        frames = self.__get_display_frames()
        facial_frame = frames.get("表情")
        initial_item_count = len(facial_frame.data)

        self.__ensure_root_active()

        # Load facial items
        result = bpy.ops.mmd_tools.display_item_quick_setup(type="FACIAL")

        self.assertEqual(result, {"FINISHED"})

        # Should have more items in facial frame
        self.assertGreater(len(facial_frame.data), initial_item_count)

        # Check that morph items were added
        morph_items = [item for item in facial_frame.data if item.type == "MORPH"]
        self.assertGreater(len(morph_items), 0)

        # Verify specific test morphs are included
        morph_names = [item.name for item in morph_items]
        self.assertIn("TestVertexMorph", morph_names)
        self.assertIn("TestBoneMorph", morph_names)
        self.assertIn("TestMaterialMorph", morph_names)

    def test_invalid_frame_operations(self):
        """Test operations with invalid frame indices"""
        mmd_root = self.root_object.mmd_root

        # Set invalid frame index
        mmd_root.active_display_item_frame = 999
        self.__ensure_root_active()

        # Try to add item to invalid frame
        result = bpy.ops.mmd_tools.display_item_add()

        # Should return CANCELLED for invalid frame
        self.assertEqual(result, {"CANCELLED"})

    def test_invalid_item_operations(self):
        """Test operations with invalid item indices"""
        frames = self.__get_display_frames()
        root_frame = frames.get("Root")

        # Set active frame
        self.__set_active_frame(frames.find("Root"))

        # Set invalid item index
        root_frame.active_item = 999
        self.__ensure_root_active()

        # Try to select invalid item
        result = bpy.ops.mmd_tools.display_item_select_current()

        # Should return CANCELLED for invalid item
        self.assertEqual(result, {"CANCELLED"})

    def test_morph_type_consistency(self):
        """Test that morph types are handled consistently"""
        frames = self.__get_display_frames()
        facial_frame = frames.get("表情")

        # Test each morph type
        morph_types = ["vertex_morphs", "bone_morphs", "material_morphs", "uv_morphs", "group_morphs"]

        for i, morph_type in enumerate(morph_types):
            # Set active morph
            self.__set_active_morph(morph_type, 0)

            # Set active frame to facial
            self.__set_active_frame(frames.find("表情"))
            self.__ensure_root_active()

            # Add morph item
            result = bpy.ops.mmd_tools.display_item_add()

            self.assertEqual(result, {"FINISHED"})

            # Check the added item has correct morph type
            added_item = facial_frame.data[-1]
            self.assertEqual(added_item.type, "MORPH")
            self.assertEqual(added_item.morph_type, morph_type)

    def test_bone_selection_integration(self):
        """Test integration with bone selection"""
        frames = self.__get_display_frames()
        root_frame = frames.get("Root")

        # Set active bone and keep armature active
        self.__set_active_bone_keep_armature_active("TestBone1")

        # Set active frame to Root
        self.__set_active_frame(frames.find("Root"))

        # Add bone items
        result = bpy.ops.mmd_tools.display_item_add()

        self.assertEqual(result, {"FINISHED"})

        # Verify bone item was added with correct name
        bone_items = [item for item in root_frame.data if item.type == "BONE"]
        bone_names = [item.name for item in bone_items]
        self.assertIn("TestBone1", bone_names)


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main()
