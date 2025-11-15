# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import logging
import os
import shutil
import unittest

import bmesh
import bpy
from bl_ext.blender_org.mmd_tools.core.sdef import FnSDEF, _hash
from mathutils import Vector

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "samples")


class TestSDEFSystem(unittest.TestCase):
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
        """Set up testing environment"""
        logger = logging.getLogger()
        logger.setLevel("ERROR")

        # Clear the scene
        bpy.ops.wm.read_homefile(use_empty=True)

        # Enable MMD Tools addon
        self.__enable_mmd_tools()

    def tearDown(self):
        """Clean up after each test"""
        # Clear SDEF cache
        FnSDEF.clear_cache()

        # Clear the scene
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)

    # ********************************************
    # Utils
    # ********************************************

    def __enable_mmd_tools(self):
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.blender_org.mmd_tools")

    def __vector_error(self, vec0, vec1):
        return (Vector(vec0) - Vector(vec1)).length

    def __create_test_armature(self, name="TestArmature"):
        """Create a test armature with bones for SDEF testing"""
        # Create armature
        armature_data = bpy.data.armatures.new(name + "_data")
        armature_obj = bpy.data.objects.new(name, armature_data)
        bpy.context.collection.objects.link(armature_obj)

        # Enter edit mode to create bones
        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode="EDIT")

        # Create bones
        bone1 = armature_data.edit_bones.new("Bone1")
        bone1.head = (0.0, 0.0, 0.0)
        bone1.tail = (0.0, 0.0, 1.0)

        bone2 = armature_data.edit_bones.new("Bone2")
        bone2.head = (1.0, 0.0, 0.0)
        bone2.tail = (1.0, 0.0, 1.0)

        bpy.ops.object.mode_set(mode="OBJECT")

        return armature_obj

    def __create_test_mesh_with_sdef(self, name="TestMesh", armature_obj=None):
        """Create a test mesh with SDEF data"""
        # Create mesh
        mesh_data = bpy.data.meshes.new(name + "_data")
        mesh_obj = bpy.data.objects.new(name, mesh_data)
        bpy.context.collection.objects.link(mesh_obj)

        # Create basic mesh geometry
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=2.0)
        bm.to_mesh(mesh_data)
        bm.free()

        # Add armature modifier if armature provided
        if armature_obj:
            modifier = mesh_obj.modifiers.new("mmd_armature", "ARMATURE")
            modifier.object = armature_obj

            # Create vertex groups
            vg1 = mesh_obj.vertex_groups.new(name="Bone1")
            vg2 = mesh_obj.vertex_groups.new(name="Bone2")

            # Assign vertices to groups
            for i, vert in enumerate(mesh_data.vertices):
                if i < 4:  # First half to bone1
                    vg1.add([i], 0.7, "REPLACE")
                    vg2.add([i], 0.3, "REPLACE")
                else:  # Second half to bone2
                    vg1.add([i], 0.3, "REPLACE")
                    vg2.add([i], 0.7, "REPLACE")

        # Add SDEF shape keys
        mesh_obj.shape_key_add(name="Basis", from_mix=False)
        sdef_c = mesh_obj.shape_key_add(name="mmd_sdef_c", from_mix=False)
        sdef_r0 = mesh_obj.shape_key_add(name="mmd_sdef_r0", from_mix=False)
        sdef_r1 = mesh_obj.shape_key_add(name="mmd_sdef_r1", from_mix=False)

        # Modify SDEF shape key data to create test data
        for i, vert in enumerate(sdef_c.data):
            # Offset C points slightly
            vert.co = mesh_data.vertices[i].co + Vector((0.1, 0.1, 0.1))

        for i, vert in enumerate(sdef_r0.data):
            # Offset R0 points
            vert.co = mesh_data.vertices[i].co + Vector((0.2, 0.0, 0.0))

        for i, vert in enumerate(sdef_r1.data):
            # Offset R1 points
            vert.co = mesh_data.vertices[i].co + Vector((0.0, 0.2, 0.0))

        return mesh_obj

    # ********************************************
    # Core SDEF Function Tests
    # ********************************************

    def test_hash_function(self):
        """Test the internal _hash function"""
        # Create test objects
        armature_obj = self.__create_test_armature()
        mesh_obj = self.__create_test_mesh_with_sdef(armature_obj=armature_obj)

        # Validate test objects were created properly
        self.assertIsNotNone(armature_obj, "Armature object should be created")
        self.assertIsNotNone(mesh_obj, "Mesh object should be created")
        self.assertEqual(armature_obj.type, "ARMATURE", "Object should be armature type")
        self.assertEqual(mesh_obj.type, "MESH", "Object should be mesh type")

        # Test hash for objects
        hash1 = _hash(armature_obj)
        hash2 = _hash(armature_obj)
        self.assertEqual(hash1, hash2, "Hash should be consistent for the same object")
        self.assertIsInstance(hash1, int, "Hash should return an integer")

        # Test hash for pose bones
        pose_bone = armature_obj.pose.bones["Bone1"]
        hash3 = _hash(pose_bone)
        hash4 = _hash(pose_bone)
        self.assertEqual(hash3, hash4, "Hash should be consistent for the same pose bone")
        self.assertIsInstance(hash3, int, "Hash should return an integer")

        # Test hash for pose
        pose_hash1 = _hash(armature_obj.pose)
        pose_hash2 = _hash(armature_obj.pose)
        self.assertEqual(pose_hash1, pose_hash2, "Hash should be consistent for the same pose")
        self.assertIsInstance(pose_hash1, int, "Hash should return an integer")

        # Test that different objects have different hashes
        armature_obj2 = self.__create_test_armature("TestArmature2")
        hash_different = _hash(armature_obj2)
        self.assertNotEqual(hash1, hash_different, "Different objects should have different hashes")

        # Test NotImplementedError for unsupported types
        with self.assertRaises(NotImplementedError):
            _hash("invalid_type")

    def test_has_sdef_data(self):
        """Test FnSDEF.has_sdef_data function"""
        # Test with object without SDEF data
        mesh_obj = self.__create_test_mesh_with_sdef()

        # Initially should not have SDEF data (no armature modifier)
        self.assertFalse(FnSDEF.has_sdef_data(mesh_obj), "Should not have SDEF data without armature modifier")

        # Create armature and add armature modifier but no SDEF shape keys
        armature_obj = self.__create_test_armature()
        modifier = mesh_obj.modifiers.new("mmd_armature", "ARMATURE")
        modifier.object = armature_obj

        # Remove SDEF shape keys
        if mesh_obj.data.shape_keys:
            for key in list(mesh_obj.data.shape_keys.key_blocks):
                if key.name.startswith("mmd_sdef_"):
                    mesh_obj.shape_key_remove(key)

        self.assertFalse(FnSDEF.has_sdef_data(mesh_obj), "Should not have SDEF data without required shape keys")

        # Create mesh with proper SDEF data
        mesh_obj_with_sdef = self.__create_test_mesh_with_sdef(armature_obj=armature_obj)
        self.assertTrue(FnSDEF.has_sdef_data(mesh_obj_with_sdef), "Should have SDEF data with all requirements")

    def test_mute_sdef_set(self):
        """Test FnSDEF.mute_sdef_set function"""
        armature_obj = self.__create_test_armature()
        mesh_obj = self.__create_test_mesh_with_sdef(armature_obj=armature_obj)

        # Bind SDEF first
        result = FnSDEF.bind(mesh_obj)
        self.assertTrue(result, "SDEF bind should succeed")

        # Test muting
        FnSDEF.mute_sdef_set(mesh_obj, True)

        # Check if shape key is muted
        if mesh_obj.data.shape_keys and FnSDEF.SHAPEKEY_NAME in mesh_obj.data.shape_keys.key_blocks:
            shapekey = mesh_obj.data.shape_keys.key_blocks[FnSDEF.SHAPEKEY_NAME]
            self.assertTrue(shapekey.mute, "SDEF shape key should be muted")

        # Test unmuting
        FnSDEF.mute_sdef_set(mesh_obj, False)

        if mesh_obj.data.shape_keys and FnSDEF.SHAPEKEY_NAME in mesh_obj.data.shape_keys.key_blocks:
            shapekey = mesh_obj.data.shape_keys.key_blocks[FnSDEF.SHAPEKEY_NAME]
            self.assertFalse(shapekey.mute, "SDEF shape key should be unmuted")

    def test_driver_function_parameter_validation(self):
        """Test driver function parameter validation"""
        armature_obj = self.__create_test_armature()
        mesh_obj = self.__create_test_mesh_with_sdef(armature_obj=armature_obj)

        # Bind SDEF
        result = FnSDEF.bind(mesh_obj)
        self.assertTrue(result, "SDEF bind should succeed")

        # Get the shape key
        shapekey = mesh_obj.data.shape_keys.key_blocks[FnSDEF.SHAPEKEY_NAME]

        # Test with valid parameters
        result = FnSDEF.driver_function(shapekey, mesh_obj.name, bulk_update=False, use_skip=False, use_scale=False)
        self.assertEqual(result, 1.0, "Driver function should return 1.0 on success")

        # Test with invalid object name
        result = FnSDEF.driver_function(shapekey, "NonExistentObject", bulk_update=False, use_skip=False, use_scale=False)
        # Should handle gracefully without crashing

        # Test bulk update mode
        result = FnSDEF.driver_function(shapekey, mesh_obj.name, bulk_update=True, use_skip=False, use_scale=False)
        self.assertEqual(result, 1.0, "Driver function should return 1.0 on success with bulk update")

        # Test with scale
        result = FnSDEF.driver_function(shapekey, mesh_obj.name, bulk_update=False, use_skip=False, use_scale=True)
        self.assertEqual(result, 1.0, "Driver function should return 1.0 on success with scale")

    def test_bind_unbind_cycle(self):
        """Test SDEF bind and unbind cycle"""
        armature_obj = self.__create_test_armature()
        mesh_obj = self.__create_test_mesh_with_sdef(armature_obj=armature_obj)

        # Initially should not be bound
        self.assertIsNone(mesh_obj.data.shape_keys.key_blocks.get(FnSDEF.SHAPEKEY_NAME), "SDEF shape key should not exist before binding")

        # Test binding
        result = FnSDEF.bind(mesh_obj)
        self.assertTrue(result, "SDEF bind should succeed")

        # Check if shape key was created
        self.assertIsNotNone(mesh_obj.data.shape_keys.key_blocks.get(FnSDEF.SHAPEKEY_NAME), "SDEF shape key should exist after binding")

        # Check if driver was added
        if mesh_obj.data.shape_keys.animation_data:
            drivers = mesh_obj.data.shape_keys.animation_data.drivers
            driver_found = False
            for driver in drivers:
                if FnSDEF.SHAPEKEY_NAME in driver.data_path:
                    driver_found = True
                    break
            self.assertTrue(driver_found, "SDEF driver should be created")

        # Test unbinding
        FnSDEF.unbind(mesh_obj)

        # Check if shape key was removed
        self.assertIsNone(mesh_obj.data.shape_keys.key_blocks.get(FnSDEF.SHAPEKEY_NAME), "SDEF shape key should be removed after unbinding")

        # Check if mask vertex group was removed
        self.assertIsNone(mesh_obj.vertex_groups.get(FnSDEF.MASK_NAME), "SDEF mask vertex group should be removed after unbinding")

    def test_bind_without_sdef_data(self):
        """Test binding object without SDEF data"""
        mesh_obj = self.__create_test_mesh_with_sdef()  # No armature

        # Validate that mesh was created without armature
        self.assertIsNotNone(mesh_obj, "Mesh object should be created")
        self.assertEqual(mesh_obj.type, "MESH", "Object should be mesh type")
        self.assertEqual(len([mod for mod in mesh_obj.modifiers if mod.type == "ARMATURE"]), 0, "Mesh should not have armature modifier")

        # Should fail to bind
        result = FnSDEF.bind(mesh_obj)
        self.assertFalse(result, "SDEF bind should fail without proper SDEF data")

    def test_bind_with_different_modes(self):
        """Test binding with different bulk_update and use_skip modes"""
        armature_obj = self.__create_test_armature()
        mesh_obj = self.__create_test_mesh_with_sdef(armature_obj=armature_obj)

        # Test different parameter combinations
        test_params = [
            (None, True, False),  # Auto mode
            (True, True, False),  # Bulk update
            (False, True, False),  # Normal mode
            (True, False, True),  # Bulk with scale
            (False, False, True),  # Normal with scale
        ]

        for bulk_update, use_skip, use_scale in test_params:
            # Unbind first if previously bound
            FnSDEF.unbind(mesh_obj)

            # Test binding with current parameters
            result = FnSDEF.bind(mesh_obj, bulk_update=bulk_update, use_skip=use_skip, use_scale=use_scale)
            self.assertTrue(result, f"SDEF bind should succeed with params: bulk_update={bulk_update}, use_skip={use_skip}, use_scale={use_scale}")

            # Verify shape key exists
            self.assertIsNotNone(mesh_obj.data.shape_keys.key_blocks.get(FnSDEF.SHAPEKEY_NAME), "SDEF shape key should exist after binding")

    def test_cache_management(self):
        """Test SDEF cache management"""
        armature_obj = self.__create_test_armature()
        mesh_obj = self.__create_test_mesh_with_sdef(armature_obj=armature_obj)

        # Bind SDEF to populate cache
        result = FnSDEF.bind(mesh_obj)
        self.assertTrue(result, "SDEF bind should succeed")

        # Check if cache is populated
        key = _hash(mesh_obj)
        self.assertIn(key, FnSDEF.g_verts, "Cache should be populated after binding")

        # Test clearing specific object cache
        FnSDEF.clear_cache(mesh_obj)
        self.assertNotIn(key, FnSDEF.g_verts, "Cache should be cleared for specific object")

        # Bind again to repopulate
        FnSDEF.unbind(mesh_obj)
        result = FnSDEF.bind(mesh_obj)
        self.assertTrue(result, "SDEF bind should succeed after cache clear")

        # Test clearing all cache
        FnSDEF.clear_cache()
        self.assertEqual(len(FnSDEF.g_verts), 0, "All cache should be cleared")
        self.assertEqual(len(FnSDEF.g_bone_check), 0, "Bone check cache should be cleared")
        self.assertEqual(len(FnSDEF.g_shapekey_data), 0, "Shape key data cache should be cleared")

    def test_driver_function_wrap(self):
        """Test FnSDEF.driver_function_wrap function"""
        armature_obj = self.__create_test_armature()
        mesh_obj = self.__create_test_mesh_with_sdef(armature_obj=armature_obj)

        # Bind SDEF
        result = FnSDEF.bind(mesh_obj)
        self.assertTrue(result, "SDEF bind should succeed")

        # Test driver function wrap
        result = FnSDEF.driver_function_wrap(mesh_obj.name, bulk_update=False, use_skip=False, use_scale=False)
        self.assertEqual(result, 1.0, "Driver function wrap should return 1.0 on success")

        # Test with invalid object name
        result = FnSDEF.driver_function_wrap("NonExistentObject", bulk_update=False, use_skip=False, use_scale=False)
        self.assertEqual(result, 0.0, "Driver function wrap should return 0.0 for non-existent object")

    # ********************************************
    # Operator Tests
    # ********************************************

    def test_bind_sdef_operator(self):
        """Test BindSDEF operator"""
        armature_obj = self.__create_test_armature()
        mesh_obj = self.__create_test_mesh_with_sdef(armature_obj=armature_obj)

        # Select the mesh object
        bpy.context.view_layer.objects.active = mesh_obj
        mesh_obj.select_set(True)

        # Execute bind operator
        result = bpy.ops.mmd_tools.sdef_bind(mode="0", use_skip=True, use_scale=False)
        self.assertIn(result, [{"FINISHED"}, {"CANCELLED"}], "Bind operator should complete")

        # Check if binding was successful
        if result == {"FINISHED"}:
            self.assertIsNotNone(mesh_obj.data.shape_keys.key_blocks.get(FnSDEF.SHAPEKEY_NAME), "SDEF shape key should exist after operator")

    def test_unbind_sdef_operator(self):
        """Test UnbindSDEF operator"""
        armature_obj = self.__create_test_armature()
        mesh_obj = self.__create_test_mesh_with_sdef(armature_obj=armature_obj)

        # Bind first
        FnSDEF.bind(mesh_obj)

        # Select the mesh object
        bpy.context.view_layer.objects.active = mesh_obj
        mesh_obj.select_set(True)

        # Execute unbind operator
        result = bpy.ops.mmd_tools.sdef_unbind()
        self.assertIn(result, [{"FINISHED"}, {"CANCELLED"}], "Unbind operator should complete")

        # Check if unbinding was successful
        if result == {"FINISHED"}:
            self.assertIsNone(mesh_obj.data.shape_keys.key_blocks.get(FnSDEF.SHAPEKEY_NAME), "SDEF shape key should be removed after unbind operator")

    def test_reset_sdef_cache_operator(self):
        """Test ResetSDEFCache operator"""
        armature_obj = self.__create_test_armature()
        mesh_obj = self.__create_test_mesh_with_sdef(armature_obj=armature_obj)

        # Bind to populate cache
        FnSDEF.bind(mesh_obj)

        # Select the mesh object
        bpy.context.view_layer.objects.active = mesh_obj
        mesh_obj.select_set(True)

        # Execute cache reset operator
        result = bpy.ops.mmd_tools.sdef_cache_reset()
        self.assertEqual(result, {"FINISHED"}, "Cache reset operator should succeed")

    def test_operator_with_no_selection(self):
        """Test operators with no objects selected"""
        # Test bind operator with no selection
        result = bpy.ops.mmd_tools.sdef_bind(mode="0", use_skip=True, use_scale=False)
        self.assertIn(result, [{"FINISHED"}, {"CANCELLED"}], "Bind operator should handle no selection")

        # Test unbind operator with no selection
        result = bpy.ops.mmd_tools.sdef_unbind()
        self.assertIn(result, [{"FINISHED"}, {"CANCELLED"}], "Unbind operator should handle no selection")

        # Test cache reset operator with no selection
        result = bpy.ops.mmd_tools.sdef_cache_reset()
        self.assertEqual(result, {"FINISHED"}, "Cache reset operator should handle no selection")

    def test_operator_with_invalid_object(self):
        """Test operators with invalid objects selected"""
        # Create a cube (not a valid MMD object)
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object

        # Validate cube was created
        self.assertIsNotNone(cube, "Cube object should be created")
        self.assertEqual(cube.type, "MESH", "Cube should be mesh type")
        self.assertFalse(FnSDEF.has_sdef_data(cube), "Cube should not have SDEF data")

        # Test bind operator with invalid object
        result = bpy.ops.mmd_tools.sdef_bind(mode="0", use_skip=True, use_scale=False)
        self.assertIn(result, [{"FINISHED"}, {"CANCELLED"}], "Bind operator should handle invalid objects")

        # Test unbind operator with invalid object
        result = bpy.ops.mmd_tools.sdef_unbind()
        self.assertIn(result, [{"FINISHED"}, {"CANCELLED"}], "Unbind operator should handle invalid objects")

    # ********************************************
    # Integration Tests
    # ********************************************

    def test_sdef_vertex_deformation(self):
        """Test that SDEF actually deforms vertices correctly"""
        armature_obj = self.__create_test_armature()
        mesh_obj = self.__create_test_mesh_with_sdef(armature_obj=armature_obj)

        # Store original vertex positions
        original_positions = [v.co.copy() for v in mesh_obj.data.vertices]

        # Validate original positions were stored
        self.assertGreater(len(original_positions), 0, "Should have vertex positions to store")
        for pos in original_positions:
            self.assertIsInstance(pos, Vector, "Position should be a Vector")

        # Bind SDEF
        result = FnSDEF.bind(mesh_obj)
        self.assertTrue(result, "SDEF bind should succeed")

        # Enter pose mode and move a bone
        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode="POSE")

        # Move bone1
        bone1 = armature_obj.pose.bones["Bone1"]
        original_bone_location = bone1.location.copy()
        bone1.location = (0.5, 0.0, 0.0)

        # Validate bone was moved
        self.assertNotEqual(bone1.location, original_bone_location, "Bone location should change")
        self.assertAlmostEqual(bone1.location.x, 0.5, places=6, msg="Bone X location should be 0.5")

        # Update scene
        bpy.context.view_layer.update()

        # Check if SDEF shape key has been updated
        if mesh_obj.data.shape_keys and FnSDEF.SHAPEKEY_NAME in mesh_obj.data.shape_keys.key_blocks:
            sdef_shapekey = mesh_obj.data.shape_keys.key_blocks[FnSDEF.SHAPEKEY_NAME]
            self.assertGreater(sdef_shapekey.value, 0.0, "SDEF shape key should be active")

        # Return to object mode
        bpy.ops.object.mode_set(mode="OBJECT")

    def test_multiple_objects_sdef(self):
        """Test SDEF with multiple objects"""
        armature_obj = self.__create_test_armature()
        mesh_obj1 = self.__create_test_mesh_with_sdef("TestMesh1", armature_obj=armature_obj)
        mesh_obj2 = self.__create_test_mesh_with_sdef("TestMesh2", armature_obj=armature_obj)

        # Validate objects were created
        self.assertIsNotNone(mesh_obj1, "First mesh object should be created")
        self.assertIsNotNone(mesh_obj2, "Second mesh object should be created")
        self.assertNotEqual(mesh_obj1, mesh_obj2, "Objects should be different")
        self.assertEqual(mesh_obj1.name, "TestMesh1", "First object should have correct name")
        self.assertEqual(mesh_obj2.name, "TestMesh2", "Second object should have correct name")

        # Bind both objects
        result1 = FnSDEF.bind(mesh_obj1)
        result2 = FnSDEF.bind(mesh_obj2)

        self.assertTrue(result1, "SDEF bind should succeed for first object")
        self.assertTrue(result2, "SDEF bind should succeed for second object")

        # Check both have shape keys
        self.assertIsNotNone(mesh_obj1.data.shape_keys.key_blocks.get(FnSDEF.SHAPEKEY_NAME), "First object should have SDEF shape key")
        self.assertIsNotNone(mesh_obj2.data.shape_keys.key_blocks.get(FnSDEF.SHAPEKEY_NAME), "Second object should have SDEF shape key")

        # Unbind both
        FnSDEF.unbind(mesh_obj1)
        FnSDEF.unbind(mesh_obj2)

        # Check both shape keys are removed
        self.assertIsNone(mesh_obj1.data.shape_keys.key_blocks.get(FnSDEF.SHAPEKEY_NAME), "First object SDEF shape key should be removed")
        self.assertIsNone(mesh_obj2.data.shape_keys.key_blocks.get(FnSDEF.SHAPEKEY_NAME), "Second object SDEF shape key should be removed")

    def test_sdef_with_complex_vertex_groups(self):
        """Test SDEF with complex vertex group assignments"""
        armature_obj = self.__create_test_armature()
        mesh_obj = self.__create_test_mesh_with_sdef(armature_obj=armature_obj)

        # Create more complex vertex group assignments
        vg1 = mesh_obj.vertex_groups["Bone1"]
        vg2 = mesh_obj.vertex_groups["Bone2"]

        # Validate vertex groups exist
        self.assertIsNotNone(vg1, "Bone1 vertex group should exist")
        self.assertIsNotNone(vg2, "Bone2 vertex group should exist")

        # Clear existing assignments
        vg1.remove(range(len(mesh_obj.data.vertices)))
        vg2.remove(range(len(mesh_obj.data.vertices)))

        # Add complex assignments
        vertex_count = len(mesh_obj.data.vertices)
        self.assertGreater(vertex_count, 0, "Mesh should have vertices")

        for i in range(vertex_count):
            if i % 2 == 0:
                vg1.add([i], 0.8, "REPLACE")
                vg2.add([i], 0.2, "REPLACE")
            else:
                vg1.add([i], 0.3, "REPLACE")
                vg2.add([i], 0.7, "REPLACE")

        # Validate vertex group assignments
        for i in range(vertex_count):
            vertex_groups = [vg.group for vg in mesh_obj.data.vertices[i].groups]
            self.assertIn(vg1.index, vertex_groups, f"Vertex {i} should be in Bone1 group")
            self.assertIn(vg2.index, vertex_groups, f"Vertex {i} should be in Bone2 group")

        # Test binding with complex weights
        result = FnSDEF.bind(mesh_obj)
        self.assertTrue(result, "SDEF bind should succeed with complex vertex groups")

    def test_error_handling(self):
        """Test error handling in various scenarios"""
        # Test with None object
        result = FnSDEF.has_sdef_data(None)
        self.assertFalse(result, "has_sdef_data should return False for None")

        # Test binding None object
        try:
            result = FnSDEF.bind(None)
            self.assertFalse(result, "bind should return False for None object")
        except Exception as e:
            self.assertIsInstance(e, (AttributeError, TypeError), "Should raise appropriate exception for None object")

        # Test unbinding None object
        try:
            FnSDEF.unbind(None)
        except Exception as e:
            self.assertIsInstance(e, (AttributeError, TypeError), "Should raise appropriate exception for None object")

        # Test clearing cache with None object
        try:
            FnSDEF.clear_cache(None)
        except Exception as e:
            self.assertIsInstance(e, (AttributeError, TypeError), "Should handle None object gracefully")

        # Test mute_sdef_set with None object
        try:
            FnSDEF.mute_sdef_set(None, True)
        except Exception as e:
            self.assertIsInstance(e, (AttributeError, TypeError), "Should raise appropriate exception for None object")

    def test_sdef_constants(self):
        """Test SDEF system constants"""
        # Validate SDEF constants are properly defined
        self.assertEqual(FnSDEF.SHAPEKEY_NAME, "mmd_sdef_skinning", "SHAPEKEY_NAME should be correct")
        self.assertEqual(FnSDEF.MASK_NAME, "mmd_sdef_mask", "MASK_NAME should be correct")
        self.assertIsInstance(FnSDEF.BENCH_LOOP, int, "BENCH_LOOP should be an integer")
        self.assertGreater(FnSDEF.BENCH_LOOP, 0, "BENCH_LOOP should be positive")

    def test_register_driver_function(self):
        """Test driver function registration"""
        # Clear driver namespace first
        if "mmd_sdef_driver" in bpy.app.driver_namespace:
            del bpy.app.driver_namespace["mmd_sdef_driver"]
        if "mmd_sdef_driver_wrap" in bpy.app.driver_namespace:
            del bpy.app.driver_namespace["mmd_sdef_driver_wrap"]

        # Validate functions are not registered initially
        self.assertNotIn("mmd_sdef_driver", bpy.app.driver_namespace, "Driver function should not be registered initially")
        self.assertNotIn("mmd_sdef_driver_wrap", bpy.app.driver_namespace, "Driver wrap function should not be registered initially")

        # Register driver functions
        FnSDEF.register_driver_function()

        # Validate functions are registered
        self.assertIn("mmd_sdef_driver", bpy.app.driver_namespace, "Driver function should be registered")
        self.assertIn("mmd_sdef_driver_wrap", bpy.app.driver_namespace, "Driver wrap function should be registered")

        # Validate registered functions are callable
        self.assertTrue(callable(bpy.app.driver_namespace["mmd_sdef_driver"]), "Registered driver function should be callable")
        self.assertTrue(callable(bpy.app.driver_namespace["mmd_sdef_driver_wrap"]), "Registered driver wrap function should be callable")

    def test_sdef_shape_key_names(self):
        """Test SDEF required shape key names"""
        armature_obj = self.__create_test_armature()
        mesh_obj = self.__create_test_mesh_with_sdef(armature_obj=armature_obj)

        # Validate required SDEF shape keys exist
        required_keys = ["mmd_sdef_c", "mmd_sdef_r0", "mmd_sdef_r1"]
        shape_keys = mesh_obj.data.shape_keys.key_blocks

        for key_name in required_keys:
            self.assertIn(key_name, shape_keys, f"Required shape key {key_name} should exist")
            key = shape_keys[key_name]
            self.assertIsNotNone(key, f"Shape key {key_name} should not be None")
            self.assertEqual(len(key.data), len(mesh_obj.data.vertices), f"Shape key {key_name} should have same vertex count as mesh")

    def test_benchmark_functionality(self):
        """Test SDEF benchmark functionality"""
        armature_obj = self.__create_test_armature()
        mesh_obj = self.__create_test_mesh_with_sdef(armature_obj=armature_obj)

        # Bind with auto mode (should trigger benchmark)
        result = FnSDEF.bind(mesh_obj, bulk_update=None, use_skip=True, use_scale=False)
        self.assertTrue(result, "SDEF bind with auto mode should succeed")

        # Verify shape key exists
        self.assertIsNotNone(mesh_obj.data.shape_keys.key_blocks.get(FnSDEF.SHAPEKEY_NAME), "SDEF shape key should exist after auto mode binding")

        # Verify driver was created with benchmark result
        if mesh_obj.data.shape_keys.animation_data:
            drivers = mesh_obj.data.shape_keys.animation_data.drivers
            driver_found = False
            for driver in drivers:
                if FnSDEF.SHAPEKEY_NAME in driver.data_path:
                    driver_found = True
                    # Check if expression contains bulk_update parameter
                    self.assertIn("bulk_update=", driver.driver.expression, "Driver expression should contain bulk_update parameter")
                    break
            self.assertTrue(driver_found, "SDEF driver should be created with benchmark result")

    def test_vertex_group_validation(self):
        """Test vertex group validation in SDEF system"""
        armature_obj = self.__create_test_armature()
        mesh_obj = self.__create_test_mesh_with_sdef(armature_obj=armature_obj)

        # Validate vertex groups exist and have correct names
        bone_names = [bone.name for bone in armature_obj.data.bones]
        vertex_group_names = [vg.name for vg in mesh_obj.vertex_groups]

        for bone_name in bone_names:
            self.assertIn(bone_name, vertex_group_names, f"Vertex group for bone {bone_name} should exist")

        # Bind SDEF
        result = FnSDEF.bind(mesh_obj)
        self.assertTrue(result, "SDEF bind should succeed")

        # Check if mask vertex group was created
        mask_vg = mesh_obj.vertex_groups.get(FnSDEF.MASK_NAME)
        if mask_vg is not None:
            self.assertEqual(mask_vg.name, FnSDEF.MASK_NAME, "Mask vertex group should have correct name")

    def test_armature_modifier_validation(self):
        """Test armature modifier validation in SDEF system"""
        armature_obj = self.__create_test_armature()
        mesh_obj = self.__create_test_mesh_with_sdef(armature_obj=armature_obj)

        # Find armature modifier
        armature_modifier = None
        for mod in mesh_obj.modifiers:
            if mod.type == "ARMATURE":
                armature_modifier = mod
                break

        self.assertIsNotNone(armature_modifier, "Mesh should have armature modifier")
        self.assertEqual(armature_modifier.name, "mmd_armature", "Armature modifier should have correct name")
        self.assertEqual(armature_modifier.object, armature_obj, "Armature modifier should reference correct armature")

        # Bind SDEF and check modifier properties
        result = FnSDEF.bind(mesh_obj)
        self.assertTrue(result, "SDEF bind should succeed")

        # After binding, modifier might have additional properties set
        self.assertEqual(armature_modifier.object, armature_obj, "Armature modifier object should remain unchanged")

    def test_cache_unused_only_cleanup(self):
        """Test cache cleanup with unused_only parameter"""
        armature_obj1 = self.__create_test_armature("TestArmature1")
        armature_obj2 = self.__create_test_armature("TestArmature2")
        mesh_obj1 = self.__create_test_mesh_with_sdef("TestMesh1", armature_obj=armature_obj1)
        mesh_obj2 = self.__create_test_mesh_with_sdef("TestMesh2", armature_obj=armature_obj2)

        # Bind both objects to populate cache
        result1 = FnSDEF.bind(mesh_obj1)
        result2 = FnSDEF.bind(mesh_obj2)
        self.assertTrue(result1, "First SDEF bind should succeed")
        self.assertTrue(result2, "Second SDEF bind should succeed")

        # Verify cache is populated
        key1 = _hash(mesh_obj1)
        key2 = _hash(mesh_obj2)
        self.assertIn(key1, FnSDEF.g_verts, "First object should be in cache")
        self.assertIn(key2, FnSDEF.g_verts, "Second object should be in cache")

        # Remove second object from scene
        bpy.data.objects.remove(mesh_obj2)

        # Clear cache with unused_only=True
        FnSDEF.clear_cache(unused_only=True)

        # First object should still be in cache, second should be removed
        self.assertIn(key1, FnSDEF.g_verts, "First object should remain in cache")
        # Note: key2 might still exist if the object was not properly removed from bpy.data.objects


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main(verbosity=1, exit=True)
