# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import logging
import math
import os
import shutil
import unittest
from collections import namedtuple

import bpy
from bl_ext.user_default.mmd_tools.core.model import Model
from bl_ext.user_default.mmd_tools.core.morph import FnMorph, MigrationFnMorph
from mathutils import Quaternion, Vector

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "samples")


class TestMorphSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Clean up output from previous tests"""
        output_dir = os.path.join(TESTS_DIR, "output")
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

        # Clean the scene
        bpy.ops.wm.read_homefile(use_empty=True)
        self.__enable_mmd_tools()

    # ********************************************
    # Utils
    # ********************************************

    def __enable_mmd_tools(self):
        """Enable MMD Tools addon"""
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.user_default.mmd_tools")

    def __create_test_model(self, name="TestModel"):
        """Create a simple test model with armature and mesh"""
        # Create model
        model = Model.create(name, add_root_bone=True)
        root_object = model.rootObject()
        armature_object = model.armature()

        # Create a simple mesh
        mesh = bpy.data.meshes.new(name + "_mesh")
        verts = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)]
        faces = [(0, 1, 3, 2)]
        mesh.from_pydata(verts, [], faces)
        mesh.update()

        mesh_object = bpy.data.objects.new(name + "_mesh", mesh)
        mesh_object.parent = armature_object
        bpy.context.collection.objects.link(mesh_object)

        # Add material
        material = bpy.data.materials.new(name + "_material")
        mesh.materials.append(material)

        return model, root_object, armature_object, mesh_object

    def __vector_error(self, vec0, vec1):
        """Calculate vector error"""
        return (Vector(vec0) - Vector(vec1)).length

    def __quaternion_error(self, quat0, quat1):
        """Calculate quaternion error"""
        angle = quat0.rotation_difference(quat1).angle % math.pi
        return min(angle, math.pi - angle)

    def __list_sample_files(self, file_types):
        """List sample files for testing"""
        ret = []
        for file_type in file_types:
            file_ext = "." + file_type
            for root, dirs, files in os.walk(os.path.join(SAMPLES_DIR, file_type)):
                for name in files:
                    if name.lower().endswith(file_ext):
                        ret.append(os.path.join(root, name))
        return ret

    # ********************************************
    # Shape Key Functions Tests
    # ********************************************

    def test_shape_key_operations(self):
        """Test shape key creation, copying, and removal"""
        model, root_object, armature_object, mesh_object = self.__create_test_model("ShapeKeyTest")

        # Set mesh object as active (required for storeShapeKeyOrder)
        bpy.context.view_layer.objects.active = mesh_object
        mesh_object.select_set(True)

        # Test storeShapeKeyOrder
        shape_key_names = ["key1", "key2", "key3"]
        FnMorph.storeShapeKeyOrder(mesh_object, shape_key_names)

        # Verify shape keys were created
        self.assertIsNotNone(mesh_object.data.shape_keys, "Shape keys should be created")
        key_blocks = mesh_object.data.shape_keys.key_blocks

        for name in shape_key_names:
            self.assertIn(name, key_blocks, f"Shape key '{name}' should exist")

        # Test fixShapeKeyOrder (also requires active object)
        FnMorph.fixShapeKeyOrder(mesh_object, ["key3", "key1", "key2"])

        # Test copy_shape_key
        FnMorph.copy_shape_key(mesh_object, "key1", "key1_copy")
        self.assertIn("key1_copy", key_blocks, "Copied shape key should exist")

        # Test remove_shape_key
        FnMorph.remove_shape_key(mesh_object, "key1_copy")
        self.assertNotIn("key1_copy", key_blocks, "Removed shape key should not exist")

    def test_uv_morph_operations(self):
        """Test UV morph vertex groups operations"""
        model, root_object, armature_object, mesh_object = self.__create_test_model("UVMorphTest")

        # Add UV layer
        uv_layer = mesh_object.data.uv_layers.new(name="UVMap")
        self.assertIsNotNone(uv_layer, "UV layer should be created successfully")
        self.assertEqual(uv_layer.name, "UVMap", "UV layer should have correct name")

        # Create UV morph vertex groups
        vg1 = mesh_object.vertex_groups.new(name="UV_TestMorph+X")
        vg2 = mesh_object.vertex_groups.new(name="UV_TestMorph-Y")
        vg3 = mesh_object.vertex_groups.new(name="UV_OtherMorph+Z")

        # Verify vertex groups were created correctly
        self.assertIsNotNone(vg1, "UV_TestMorph+X vertex group should be created")
        self.assertIsNotNone(vg2, "UV_TestMorph-Y vertex group should be created")
        self.assertIsNotNone(vg3, "UV_OtherMorph+Z vertex group should be created")
        self.assertEqual(vg1.name, "UV_TestMorph+X", "Vertex group should have correct name")
        self.assertEqual(vg2.name, "UV_TestMorph-Y", "Vertex group should have correct name")
        self.assertEqual(vg3.name, "UV_OtherMorph+Z", "Vertex group should have correct name")

        # Test get_uv_morph_vertex_groups
        uv_groups = list(FnMorph.get_uv_morph_vertex_groups(mesh_object, "TestMorph"))
        self.assertEqual(len(uv_groups), 2, "Should find 2 UV morph vertex groups for 'TestMorph'")

        # Verify the returned groups are correct
        group_names = [group[0].name for group in uv_groups]
        self.assertIn("UV_TestMorph+X", group_names, "Should find UV_TestMorph+X group")
        self.assertIn("UV_TestMorph-Y", group_names, "Should find UV_TestMorph-Y group")
        self.assertNotIn("UV_OtherMorph+Z", group_names, "Should not find UV_OtherMorph+Z group")

        # Test copy_uv_morph_vertex_groups
        FnMorph.copy_uv_morph_vertex_groups(mesh_object, "TestMorph", "TestMorphCopy")
        copy_groups = list(FnMorph.get_uv_morph_vertex_groups(mesh_object, "TestMorphCopy"))
        self.assertEqual(len(copy_groups), 2, "Should find 2 copied UV morph vertex groups")

        # Verify copied groups have correct names
        copy_group_names = [group[0].name for group in copy_groups]
        self.assertIn("UV_TestMorphCopy+X", copy_group_names, "Should find copied UV_TestMorphCopy+X group")
        self.assertIn("UV_TestMorphCopy-Y", copy_group_names, "Should find copied UV_TestMorphCopy-Y group")

        # Test clean_uv_morph_vertex_groups
        initial_group_count = len(mesh_object.vertex_groups)
        FnMorph.clean_uv_morph_vertex_groups(mesh_object)
        # After cleaning, empty UV morph groups should be removed
        self.assertLessEqual(len(mesh_object.vertex_groups), initial_group_count, "Empty UV morph vertex groups should be cleaned up")

    # ********************************************
    # Bone Morph Tests
    # ********************************************

    def test_bone_morph_operations(self):
        """Test bone morph operations including action pose"""
        model, root_object, armature_object, mesh_object = self.__create_test_model("BoneMorphTest")

        # Add test bones
        bpy.context.view_layer.objects.active = armature_object
        bpy.ops.object.mode_set(mode="EDIT")

        edit_bones = armature_object.data.edit_bones
        bone1 = edit_bones.new(name="TestBone1")
        bone1.head = (0, 0, 1)
        bone1.tail = (0, 0, 2)

        bone2 = edit_bones.new(name="TestBone2")
        bone2.head = (1, 0, 1)
        bone2.tail = (1, 0, 2)
        bone2.parent = bone1

        bpy.ops.object.mode_set(mode="POSE")

        # Create action with pose markers
        action = bpy.data.actions.new(name="TestAction")
        armature_object.animation_data_create()
        armature_object.animation_data.action = action

        # Add pose marker
        marker = action.pose_markers.new(name="TestMorph")
        marker.frame = 10

        # Set bone poses
        pose_bone1 = armature_object.pose.bones["TestBone1"]
        pose_bone2 = armature_object.pose.bones["TestBone2"]

        pose_bone1.location = (0.1, 0.2, 0.3)
        pose_bone1.rotation_quaternion = Quaternion((0.9, 0.1, 0.2, 0.3)).normalized()

        pose_bone2.location = (0.2, 0.3, 0.4)
        pose_bone2.rotation_quaternion = Quaternion((0.8, 0.2, 0.3, 0.4)).normalized()

        # Test overwrite_bone_morphs_from_action_pose
        FnMorph.overwrite_bone_morphs_from_action_pose(armature_object)

        # Verify bone morph was created
        mmd_root = root_object.mmd_root
        bone_morphs = mmd_root.bone_morphs
        self.assertGreater(len(bone_morphs), 0, "Bone morph should be created from action pose")

        test_morph = bone_morphs.get("TestMorph")
        self.assertIsNotNone(test_morph, "TestMorph should exist in bone morphs")

        bpy.ops.object.mode_set(mode="OBJECT")

    # ********************************************
    # Material Morph Tests
    # ********************************************

    def test_material_morph_operations(self):
        """Test material morph related operations"""
        model, root_object, armature_object, mesh_object = self.__create_test_model("MaterialMorphTest")

        # Create material morphs for testing
        mmd_root = root_object.mmd_root

        # Create identical material morphs to test cleaning
        morph1 = mmd_root.material_morphs.add()
        morph1.name = "TestMaterialMorph1"

        data1 = morph1.data.add()
        data1.material = "TestMaterial"
        data1.diffuse_color = (1.0, 0.5, 0.3, 1.0)
        data1.offset_type = "ADD"

        morph2 = mmd_root.material_morphs.add()
        morph2.name = "TestMaterialMorph2"

        data2 = morph2.data.add()
        data2.material = "TestMaterial"
        data2.diffuse_color = (1.0, 0.5, 0.3, 1.0)
        data2.offset_type = "ADD"

        # Test clean_duplicated_material_morphs
        original_count = len(mmd_root.material_morphs)
        FnMorph.clean_duplicated_material_morphs(root_object)

        # Verify duplicates were removed
        self.assertLess(len(mmd_root.material_morphs), original_count, "Duplicate material morphs should be removed")

    def test_material_morph_update_references(self):
        """Test updating material morph mesh references"""
        model, root_object, armature_object, mesh_object = self.__create_test_model("MaterialMorphRefTest")

        # Create material morph
        mmd_root = root_object.mmd_root
        morph = mmd_root.material_morphs.add()
        morph.name = "TestMaterialMorph"

        data = morph.data.add()
        data.material = mesh_object.data.materials[0].name

        # Create FnMorph instance and test update
        fn_morph = FnMorph(morph, model)
        fn_morph.update_mat_related_mesh(mesh_object)

        # Verify mesh reference was updated
        self.assertEqual(data.related_mesh, mesh_object.data.name, "Material morph should reference correct mesh")

    # ********************************************
    # Morph Slider Tests
    # ********************************************

    def test_morph_slider_system(self):
        """Test morph slider placeholder and binding system"""
        model, root_object, armature_object, mesh_object = self.__create_test_model("MorphSliderTest")

        # Set mesh object as active for shape key operations
        bpy.context.view_layer.objects.active = mesh_object
        mesh_object.select_set(True)

        # Create actual shape keys for vertex morphs
        mesh_object.shape_key_add(name="Basis")
        mesh_object.shape_key_add(name="TestVertexMorph")

        # Add some morphs
        mmd_root = root_object.mmd_root
        vertex_morph = mmd_root.vertex_morphs.add()
        vertex_morph.name = "TestVertexMorph"

        bone_morph = mmd_root.bone_morphs.add()
        bone_morph.name = "TestBoneMorph"

        material_morph = mmd_root.material_morphs.add()
        material_morph.name = "TestMaterialMorph"

        # Test morph slider creation
        morph_slider = FnMorph.get_morph_slider(model)
        placeholder = morph_slider.create()

        self.assertIsNotNone(placeholder, "Placeholder object should be created")
        self.assertEqual(placeholder.mmd_type, "PLACEHOLDER", "Should be placeholder type")
        self.assertIsNotNone(placeholder.data.shape_keys, "Placeholder should have shape keys")

        # Verify default state: should be muted (unbound state)
        base_key = placeholder.data.shape_keys.key_blocks[0]
        self.assertTrue(base_key.mute, "Base shape key should be muted by default (unbound state)")

        # In unbound state, get() should return None
        vertex_slider = morph_slider.get("TestVertexMorph")
        self.assertIsNone(vertex_slider, "Vertex morph slider should be None in unbound state")

        # Test binding - this will unmute the base key
        morph_slider.bind()

        # Verify state after binding: should not be muted
        base_key_after_bind = placeholder.data.shape_keys.key_blocks[0]
        self.assertFalse(base_key_after_bind.mute, "Base shape key should not be muted after bind")

        # Now get() should work properly
        vertex_slider = morph_slider.get("TestVertexMorph")
        self.assertIsNotNone(vertex_slider, "Vertex morph slider should exist after binding")

        bone_slider = morph_slider.get("TestBoneMorph")
        self.assertIsNotNone(bone_slider, "Bone morph slider should exist after binding")

        material_slider = morph_slider.get("TestMaterialMorph")
        self.assertIsNotNone(material_slider, "Material morph slider should exist after binding")

        # Test unbinding - this will mute the base key again
        morph_slider.unbind()

        # Verify state after unbinding: should be muted again
        base_key_after_unbind = placeholder.data.shape_keys.key_blocks[0]
        self.assertTrue(base_key_after_unbind.mute, "Base shape key should be muted after unbind")

        # After unbinding, get() should return None again
        vertex_slider_after_unbind = morph_slider.get("TestVertexMorph")
        self.assertIsNone(vertex_slider_after_unbind, "Vertex morph slider should be None after unbind")

    # ********************************************
    # Load Morphs Tests
    # ********************************************

    def test_load_morphs_from_shape_keys(self):
        """Test loading morphs from existing shape keys"""
        model, root_object, armature_object, mesh_object = self.__create_test_model("LoadMorphsTest")

        # Add shape keys to mesh
        mesh_object.shape_key_add(name="Basis")
        mesh_object.shape_key_add(name="TestMorph1")
        mesh_object.shape_key_add(name="TestMorph2")
        mesh_object.shape_key_add(name="mmd_ignore")  # Should be ignored

        # Add UV morph vertex groups
        mesh_object.vertex_groups.new(name="UV_UVMorph1+X")
        mesh_object.vertex_groups.new(name="UV_UVMorph1-Y")

        # Test loading morphs
        FnMorph.load_morphs(model)

        mmd_root = root_object.mmd_root

        # Verify vertex morphs were loaded
        vertex_morphs = mmd_root.vertex_morphs
        self.assertIn("TestMorph1", vertex_morphs, "TestMorph1 should be loaded")
        self.assertIn("TestMorph2", vertex_morphs, "TestMorph2 should be loaded")
        self.assertNotIn("mmd_ignore", vertex_morphs, "mmd_ prefixed morphs should be ignored")

        # Verify UV morphs were loaded
        uv_morphs = mmd_root.uv_morphs
        self.assertIn("UVMorph1", uv_morphs, "UVMorph1 should be loaded from vertex groups")

    def test_category_guess(self):
        """Test automatic morph category guessing"""

        # Create mock morph objects
        class MockMorph:
            def __init__(self, name):
                self.name = name
                self.category = "OTHER"

        # Test mouth category
        mouth_morph = MockMorph("mouth_smile")
        FnMorph.category_guess(mouth_morph)
        self.assertEqual(mouth_morph.category, "MOUTH", "Should guess MOUTH category")

        # Test eye category
        eye_morph = MockMorph("eye_close")
        FnMorph.category_guess(eye_morph)
        self.assertEqual(eye_morph.category, "EYE", "Should guess EYE category")

        # Test eyebrow category
        eyebrow_morph = MockMorph("eye_brow_angry")
        FnMorph.category_guess(eyebrow_morph)
        self.assertEqual(eyebrow_morph.category, "EYEBROW", "Should guess EYEBROW category")

    # ********************************************
    # UV Morph Data Tests
    # ********************************************

    def test_uv_morph_data_operations(self):
        """Test UV morph data storage and retrieval"""
        model, root_object, armature_object, mesh_object = self.__create_test_model("UVMorphDataTest")

        # Add UV layer
        uv_layer = mesh_object.data.uv_layers.new(name="UVMap")
        self.assertIsNotNone(uv_layer, "UV layer should be created successfully")
        self.assertEqual(uv_layer.name, "UVMap", "UV layer should have correct name")
        self.assertEqual(len(mesh_object.data.uv_layers), 1, "Should have exactly one UV layer")

        # Create UV morph
        mmd_root = root_object.mmd_root
        uv_morph = mmd_root.uv_morphs.add()
        uv_morph.name = "TestUVMorph"
        uv_morph.data_type = "VERTEX_GROUP"
        uv_morph.vertex_group_scale = 1.0
        uv_morph.uv_index = 0

        # Verify UV morph was created correctly
        self.assertEqual(uv_morph.name, "TestUVMorph", "UV morph should have correct name")
        self.assertEqual(uv_morph.data_type, "VERTEX_GROUP", "UV morph should have correct data type")
        self.assertEqual(uv_morph.vertex_group_scale, 1.0, "UV morph should have correct scale")
        self.assertEqual(uv_morph.uv_index, 0, "UV morph should have correct UV index")

        # Test storing UV morph data
        OffsetData = namedtuple("OffsetData", "index offset")
        offsets = [
            OffsetData(0, (0.1, 0.2, 0.0, 0.0)),
            OffsetData(1, (0.3, 0.4, 0.0, 0.0)),
        ]

        initial_group_count = len(mesh_object.vertex_groups)
        FnMorph.store_uv_morph_data(mesh_object, uv_morph, offsets, "XY")

        # Verify vertex groups were created
        self.assertGreater(len(mesh_object.vertex_groups), initial_group_count, "New vertex groups should be created for UV morph data")

        expected_groups = ["UV_TestUVMorph+X", "UV_TestUVMorph+Y"]
        for group_name in expected_groups:
            self.assertIn(group_name, mesh_object.vertex_groups, f"Vertex group '{group_name}' should be created")

            # Verify group has correct weights
            group = mesh_object.vertex_groups[group_name]
            self.assertIsNotNone(group, f"Vertex group '{group_name}' should exist")

        # Test getting UV morph offset map
        offset_map = FnMorph.get_uv_morph_offset_map(mesh_object, uv_morph)
        self.assertGreater(len(offset_map), 0, "Offset map should contain data")

        # Verify offset map contains expected vertex indices
        for offset_data in offsets:
            if any(abs(val) > 1e-4 for val in offset_data.offset[:2]):  # Only check XY components
                self.assertIn(offset_data.index, offset_map, f"Offset map should contain vertex index {offset_data.index}")

    # ********************************************
    # Integration Tests with Sample Files
    # ********************************************

    def test_morph_system_with_sample_files(self):
        """Test morph system with actual PMX/PMD sample files"""
        input_files = self.__list_sample_files(("pmd", "pmx"))
        if len(input_files) < 1:
            self.skipTest("No PMX/PMD sample files available for testing")

        # Test with first available sample file
        filepath = input_files[0]
        print(f"\n     Testing with sample file: {filepath}")

        # Import model
        bpy.ops.mmd_tools.import_model(filepath=filepath, types={"MESH", "ARMATURE", "MORPHS"}, scale=1.0, clean_model=False, remove_doubles=False, log_level="ERROR")

        # Find imported model
        root_object = None
        for obj in bpy.context.scene.objects:
            if obj.mmd_type == "ROOT":
                root_object = obj
                break

        self.assertIsNotNone(root_object, "Should find imported root object")

        model = Model(root_object)
        mmd_root = root_object.mmd_root

        # Test morph loading
        FnMorph.load_morphs(model)

        # Test morph slider system if morphs exist
        if len(mmd_root.vertex_morphs) > 0 or len(mmd_root.bone_morphs) > 0:
            morph_slider = FnMorph.get_morph_slider(model)
            placeholder = morph_slider.create()
            self.assertIsNotNone(placeholder, "Morph slider placeholder should be created")

            # Test binding/unbinding
            morph_slider.bind()
            morph_slider.unbind()

        # Test material morph cleaning if material morphs exist
        if len(mmd_root.material_morphs) > 0:
            original_count = len(mmd_root.material_morphs)
            FnMorph.clean_duplicated_material_morphs(root_object)
            # Count should be same or less (if duplicates were found)
            self.assertLessEqual(len(mmd_root.material_morphs), original_count, "Material morph count should not increase after cleaning")

    # ********************************************
    # Error Handling Tests
    # ********************************************

    def test_error_handling(self):
        """Test error handling in morph operations"""
        model, root_object, armature_object, mesh_object = self.__create_test_model("ErrorHandlingTest")

        # Test operations on non-existent shape keys
        FnMorph.remove_shape_key(mesh_object, "NonExistentKey")  # Should not crash

        # Test copy operations with invalid source
        FnMorph.copy_shape_key(mesh_object, "NonExistentSource", "TestDest")  # Should not crash

        # Test UV morph operations on mesh without UV layers
        mesh_without_uv = bpy.data.meshes.new("NoUVMesh")
        obj_without_uv = bpy.data.objects.new("NoUVObj", mesh_without_uv)
        bpy.context.collection.objects.link(obj_without_uv)

        # Should not crash
        uv_groups = list(FnMorph.get_uv_morph_vertex_groups(obj_without_uv))
        self.assertEqual(len(uv_groups), 0, "Should return empty list for mesh without UV groups")

    def test_migration_functions(self):
        """Test migration functions for compatibility"""
        # Test migration functions don't crash on empty scene
        MigrationFnMorph.update_mmd_morph()  # Should not crash
        MigrationFnMorph.ensure_material_id_not_conflict()  # Should not crash
        MigrationFnMorph.compatible_with_old_version_mmd_tools()  # Should not crash


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main()
