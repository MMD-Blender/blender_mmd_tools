# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import logging
import os
import unittest

import bpy
from bl_ext.blender_org.mmd_tools import utils
from bl_ext.blender_org.mmd_tools.core.model import Model
from bl_ext.blender_org.mmd_tools.operators import misc

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


class TestMiscOperators(unittest.TestCase):
    def setUp(self):
        """Set up testing environment"""
        logger = logging.getLogger()
        logger.setLevel("ERROR")

        # Clean scene
        bpy.ops.wm.read_homefile(use_empty=True)

        # Enable MMD Tools addon
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.blender_org.mmd_tools")

    # ********************************************
    # Helper Methods
    # ********************************************

    def __create_test_armature(self, name="TestArmature"):
        """Create a test armature with some bones"""
        bpy.ops.object.armature_add()
        arm_obj = bpy.context.active_object
        arm_obj.name = name

        # Enter edit mode and add some bones
        bpy.ops.object.mode_set(mode="EDIT")
        edit_bones = arm_obj.data.edit_bones

        # Add a few test bones
        bone1 = edit_bones.new("Bone1")
        bone1.head = (0, 0, 0)
        bone1.tail = (0, 1, 0)

        bone2 = edit_bones.new("Bone2")
        bone2.head = (0, 1, 0)
        bone2.tail = (0, 2, 0)
        bone2.parent = bone1

        bpy.ops.object.mode_set(mode="OBJECT")
        return arm_obj

    def __create_test_mesh(self, name="TestMesh"):
        """Create a test mesh object"""
        bpy.ops.mesh.primitive_cube_add()
        mesh_obj = bpy.context.active_object
        mesh_obj.name = name
        return mesh_obj

    def __create_mmd_model(self):
        """Create a basic MMD model structure"""
        # Create root object
        root = bpy.data.objects.new(name="MMDModel", object_data=None)
        root.mmd_type = "ROOT"
        bpy.context.scene.collection.objects.link(root)

        # Create armature (mmd_type should be NONE for armatures)
        arm_obj = self.__create_test_armature("MMDModel_arm")
        arm_obj.parent = root
        arm_obj.mmd_type = "NONE"

        # Create mesh - IMPORTANT: mesh must be child of armature, not root
        mesh_obj = self.__create_test_mesh("MMDModel_mesh")
        mesh_obj.parent = arm_obj  # Mesh is child of armature
        mesh_obj.mmd_type = "NONE"

        # Add armature modifier
        mod = mesh_obj.modifiers.new(name="Armature", type="ARMATURE")
        mod.object = arm_obj

        return root, arm_obj, mesh_obj

    # ********************************************
    # Test SelectObject Operator
    # ********************************************

    def test_select_object(self):
        """Test SelectObject operator"""
        # Create test objects
        mesh1 = self.__create_test_mesh("Mesh1")
        mesh2 = self.__create_test_mesh("Mesh2")

        # Deselect all
        bpy.ops.object.select_all(action="DESELECT")

        # Test selecting mesh1
        bpy.ops.mmd_tools.object_select(name="Mesh1")

        # Verify mesh1 is selected and active
        self.assertTrue(mesh1.select_get())
        self.assertEqual(bpy.context.active_object, mesh1)
        self.assertFalse(mesh2.select_get())

    # ********************************************
    # Test MoveObject Operator
    # ********************************************

    def test_move_object_set_index(self):
        """Test MoveObject.set_index method"""
        mesh = self.__create_test_mesh("TestMesh")

        # Test setting index
        misc.MoveObject.set_index(mesh, 5)
        self.assertTrue(mesh.name.startswith("005_"))

        # Test setting another index (42 in base-36 with width 3 is "016")
        misc.MoveObject.set_index(mesh, 42)
        self.assertTrue(mesh.name.startswith("016_"))

    def test_move_object_get_name(self):
        """Test MoveObject.get_name method"""
        mesh = self.__create_test_mesh("TestMesh")

        # Set index first
        misc.MoveObject.set_index(mesh, 5)

        # Test getting name without prefix
        name = misc.MoveObject.get_name(mesh)
        self.assertEqual(name, "TestMesh")

        # Test with prefix
        mesh.name = "005_prefix_something"
        name = misc.MoveObject.get_name(mesh, "prefix_")
        self.assertEqual(name, "something")

    def test_move_object_normalize_indices(self):
        """Test MoveObject.normalize_indices method"""
        # Create multiple meshes
        meshes = [self.__create_test_mesh(f"Mesh{i}") for i in range(3)]

        # Set random indices
        misc.MoveObject.set_index(meshes[0], 10)
        misc.MoveObject.set_index(meshes[1], 5)
        misc.MoveObject.set_index(meshes[2], 20)

        # Normalize
        misc.MoveObject.normalize_indices(meshes)

        # Verify indices are normalized to 0, 1, 2
        self.assertTrue(meshes[0].name.startswith("000_"))
        self.assertTrue(meshes[1].name.startswith("001_"))
        self.assertTrue(meshes[2].name.startswith("002_"))

    def test_move_object_execute(self):
        """Test MoveObject operator execution"""
        root, arm_obj, mesh1 = self.__create_mmd_model()

        # Create additional meshes as children of armature
        mesh2 = self.__create_test_mesh("MMDModel_mesh2")
        mesh2.parent = arm_obj  # Must be child of armature
        mesh2.mmd_type = "NONE"

        mesh3 = self.__create_test_mesh("MMDModel_mesh3")
        mesh3.parent = arm_obj  # Must be child of armature
        mesh3.mmd_type = "NONE"

        # Normalize indices
        meshes = [mesh1, mesh2, mesh3]
        misc.MoveObject.normalize_indices(meshes)

        # Select mesh2 (middle mesh)
        utils.selectAObject(mesh2)

        # Move up
        bpy.ops.mmd_tools.object_move(type="UP")

        # Verify mesh2 moved up (should have index 0 now)
        self.assertTrue(mesh2.name.startswith("000_"))

    # ********************************************
    # Test CleanShapeKeys Operator
    # ********************************************

    def test_clean_shape_keys(self):
        """Test CleanShapeKeys operator"""
        mesh = self.__create_test_mesh("MeshWithShapeKeys")

        # Add shape keys
        mesh.shape_key_add(name="Basis")
        sk1 = mesh.shape_key_add(name="Key1")
        sk2 = mesh.shape_key_add(name="Key2")

        # Modify Key1 to make it different from Basis
        sk1.data[0].co.z += 1.0

        # Key2 is identical to Basis (should be removed)
        # Verify sk2 exists before cleaning
        self.assertIsNotNone(sk2)

        # Select mesh
        utils.selectAObject(mesh)

        # Run clean shape keys
        bpy.ops.mmd_tools.clean_shape_keys()

        # Verify only Basis and Key1 remain
        self.assertIsNotNone(mesh.data.shape_keys)
        key_names = [kb.name for kb in mesh.data.shape_keys.key_blocks]
        self.assertIn("Basis", key_names)
        self.assertIn("Key1", key_names)
        self.assertNotIn("Key2", key_names)

    def test_clean_shape_keys_remove_all_if_only_basis(self):
        """Test CleanShapeKeys removes all shape keys if only Basis remains"""
        mesh = self.__create_test_mesh("MeshWithOnlyBasis")

        # Add only Basis and an identical key
        mesh.shape_key_add(name="Basis")
        mesh.shape_key_add(name="IdenticalKey")

        # Select mesh
        utils.selectAObject(mesh)

        # Run clean shape keys
        bpy.ops.mmd_tools.clean_shape_keys()

        # Verify all shape keys are removed
        self.assertIsNone(mesh.data.shape_keys)

    # ********************************************
    # Test SeparateByMaterials Operator
    # ********************************************

    def test_separate_by_materials(self):
        """Test SeparateByMaterials operator"""
        # Create MMD model structure to avoid ValueError
        root, arm_obj, mesh = self.__create_mmd_model()

        # Add multiple materials
        mat1 = bpy.data.materials.new(name="Material1")
        mat2 = bpy.data.materials.new(name="Material2")

        mesh.data.materials.clear()
        mesh.data.materials.append(mat1)
        mesh.data.materials.append(mat2)

        # Assign different materials to different faces
        if len(mesh.data.polygons) >= 2:
            mesh.data.polygons[0].material_index = 0
            mesh.data.polygons[1].material_index = 1

        # Select mesh
        utils.selectAObject(mesh)

        # Count objects before separation
        obj_count_before = len([obj for obj in bpy.data.objects if obj.type == "MESH"])

        # Run separate by materials
        bpy.ops.mmd_tools.separate_by_materials(clean_shape_keys=False, keep_normals=False)

        # Verify objects were created
        obj_count_after = len([obj for obj in bpy.data.objects if obj.type == "MESH"])
        self.assertGreater(obj_count_after, obj_count_before)

        # Verify material names are used for objects with index prefix
        # SeparateByMaterials adds index prefix via MoveObject.set_index()
        material_names = {obj.name for obj in bpy.data.objects if obj.type == "MESH"}

        # Check for objects with material names (with index prefix)
        # The naming format is: "{index:03d}_{material_name}"
        has_material1 = any("Material1" in name for name in material_names)
        has_material2 = any("Material2" in name for name in material_names)

        self.assertTrue(has_material1, f"Material1 not found in {material_names}")
        self.assertTrue(has_material2, f"Material2 not found in {material_names}")

    def test_separate_by_materials_with_mmd_model(self):
        """Test SeparateByMaterials with MMD model"""
        root, arm_obj, mesh = self.__create_mmd_model()

        # Add multiple materials
        mat1 = bpy.data.materials.new(name="MMDMat1")
        mat2 = bpy.data.materials.new(name="MMDMat2")

        mesh.data.materials.clear()
        mesh.data.materials.append(mat1)
        mesh.data.materials.append(mat2)

        # Assign different materials to different faces
        if len(mesh.data.polygons) >= 2:
            mesh.data.polygons[0].material_index = 0
            mesh.data.polygons[1].material_index = 1

        # Select mesh
        utils.selectAObject(mesh)

        # Run separate by materials
        bpy.ops.mmd_tools.separate_by_materials(clean_shape_keys=False, keep_normals=False)

        # Verify meshes were created with proper indices
        rig = Model(root)
        meshes = list(rig.meshes())
        self.assertGreater(len(meshes), 1)

    # ********************************************
    # Test JoinMeshes Operator
    # ********************************************

    def test_join_meshes(self):
        """Test JoinMeshes operator"""
        root, arm_obj, mesh1 = self.__create_mmd_model()

        # Create additional meshes as children of armature
        mesh2 = self.__create_test_mesh("MMDModel_mesh2")
        mesh2.parent = arm_obj  # Must be child of armature
        mesh2.mmd_type = "NONE"

        mesh3 = self.__create_test_mesh("MMDModel_mesh3")
        mesh3.parent = arm_obj  # Must be child of armature
        mesh3.mmd_type = "NONE"

        # Add materials to meshes
        mat1 = bpy.data.materials.new(name="JoinMat1")
        mat2 = bpy.data.materials.new(name="JoinMat2")
        mesh1.data.materials.append(mat1)
        mesh2.data.materials.append(mat2)

        # Count meshes before join
        rig = Model(root)
        mesh_count_before = len(list(rig.meshes()))

        # Verify we have multiple meshes
        self.assertGreaterEqual(mesh_count_before, 3)

        # Select root
        utils.selectAObject(root)

        # Run join meshes
        bpy.ops.mmd_tools.join_meshes(sort_shape_keys=True)

        # Verify only one mesh remains
        mesh_count_after = len(list(rig.meshes()))
        self.assertEqual(mesh_count_after, 1)

        # Verify materials are combined
        remaining_mesh = list(rig.meshes())[0]
        material_names = {mat.name for mat in remaining_mesh.data.materials if mat}
        self.assertIn("JoinMat1", material_names)
        self.assertIn("JoinMat2", material_names)

    # ********************************************
    # Test AttachMeshesToMMD Operator
    # ********************************************

    def test_attach_meshes_to_mmd(self):
        """Test AttachMeshesToMMD operator"""
        root, arm_obj, mesh1 = self.__create_mmd_model()

        # Create a standalone mesh (not attached to model)
        standalone_mesh = self.__create_test_mesh("StandaloneMesh")
        standalone_mesh.parent = None

        # Select root
        utils.selectAObject(root)

        # Count meshes before attach
        rig = Model(root)
        mesh_count_before = len(list(rig.meshes()))

        # Run attach meshes
        bpy.ops.mmd_tools.attach_meshes(add_armature_modifier=True)

        # Verify mesh was attached
        mesh_count_after = len(list(rig.meshes()))
        self.assertGreater(mesh_count_after, mesh_count_before)

        # Verify standalone mesh now has armature as parent (not root)
        # attach_mesh_objects sets mesh parent to armature, not root
        self.assertEqual(standalone_mesh.parent, arm_obj)

    # ********************************************
    # Test ChangeMMDIKLoopFactor Operator
    # ********************************************

    def test_change_mmd_ik_loop_factor(self):
        """Test ChangeMMDIKLoopFactor operator"""
        root, arm_obj, mesh = self.__create_mmd_model()

        # Set initial IK loop factor
        root.mmd_root.ik_loop_factor = 1

        # Select root
        utils.selectAObject(root)

        # Change IK loop factor
        bpy.ops.mmd_tools.change_mmd_ik_loop_factor(mmd_ik_loop_factor=5)

        # Verify IK loop factor changed
        self.assertEqual(root.mmd_root.ik_loop_factor, 5)

    # ********************************************
    # Test RecalculateBoneRoll Operator
    # ********************************************

    def test_recalculate_bone_roll(self):
        """Test RecalculateBoneRoll operator"""
        arm_obj = self.__create_test_armature("TestArmRecalc")

        # Select armature
        utils.selectAObject(arm_obj)

        # Run recalculate bone roll (should not crash)
        try:
            bpy.ops.mmd_tools.recalculate_bone_roll()
            success = True
        except Exception:
            success = False

        self.assertTrue(success)

        # Verify armature is still valid
        self.assertIsNotNone(arm_obj.data)
        self.assertGreater(len(arm_obj.data.bones), 0)


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main(verbosity=1, exit=True)
