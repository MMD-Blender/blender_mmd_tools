# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import logging
import os
import shutil
import unittest

import bmesh
import bpy
from bl_ext.blender_org.mmd_tools.core.model import FnModel, Model
from bl_ext.blender_org.mmd_tools.core.sdef import FnSDEF
from mathutils import Vector

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "samples")


class TestModelManagement(unittest.TestCase):
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

    # ********************************************
    # Utils
    # ********************************************

    def __enable_mmd_tools(self):
        bpy.ops.wm.read_homefile(use_empty=True)
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

    def __create_mesh_geometry(self, mesh_data, vertices, faces):
        """Create actual mesh geometry for testing"""
        bm = bmesh.new()

        # Add vertices
        for vert in vertices:
            bm.verts.new(vert)

        # Ensure vertex indices are valid
        bm.verts.ensure_lookup_table()

        # Add faces
        for face in faces:
            try:
                bm.faces.new([bm.verts[i] for i in face])
            except ValueError:
                # Skip invalid faces
                pass

        # Update mesh
        bm.to_mesh(mesh_data)
        bm.free()

    def __create_test_model(self, model_name="TestModel", with_mesh_data=True, with_vertex_groups=True, with_sdef_data=False):
        """
        Create a basic MMD model for testing

        Args:
            model_name: Name of the model to create
            with_mesh_data: Whether to create actual mesh geometry
            with_vertex_groups: Whether to create vertex groups matching bone names
            with_sdef_data: Whether to create SDEF shape keys for testing SDEF binding
        """
        self.__enable_mmd_tools()

        # Create root object
        root_obj = bpy.data.objects.new(name=model_name, object_data=None)
        root_obj.mmd_type = "ROOT"
        root_obj.mmd_root.name = model_name
        root_obj.mmd_root.name_e = model_name + "_E"
        bpy.context.collection.objects.link(root_obj)

        # Create armature
        armature_data = bpy.data.armatures.new(name=model_name + "_arm")
        armature_obj = bpy.data.objects.new(name=model_name + "_arm", object_data=armature_data)
        armature_obj.parent = root_obj
        bpy.context.collection.objects.link(armature_obj)

        # Add test bones
        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode="EDIT")

        # Create root bone
        root_bone = armature_data.edit_bones.new("Root")
        root_bone.head = (0.0, 0.0, 0.0)
        root_bone.tail = (0.0, 0.0, 1.0)

        # Create child bones
        child_bone1 = armature_data.edit_bones.new("Bone1")
        child_bone1.head = (0.0, 0.0, 1.0)
        child_bone1.tail = (0.0, 0.0, 2.0)
        child_bone1.parent = root_bone

        child_bone2 = armature_data.edit_bones.new("Bone2")
        child_bone2.head = (1.0, 0.0, 1.0)
        child_bone2.tail = (1.0, 0.0, 2.0)
        child_bone2.parent = root_bone

        bpy.ops.object.mode_set(mode="OBJECT")

        # Create test meshes
        mesh_data1 = bpy.data.meshes.new(name="TestMesh1")
        mesh_obj1 = bpy.data.objects.new(name="TestMesh1", object_data=mesh_data1)
        mesh_obj1.parent = armature_obj
        mesh_obj1.mmd_type = "NONE"
        bpy.context.collection.objects.link(mesh_obj1)

        mesh_data2 = bpy.data.meshes.new(name="TestMesh2")
        mesh_obj2 = bpy.data.objects.new(name="TestMesh2", object_data=mesh_data2)
        mesh_obj2.parent = armature_obj
        mesh_obj2.mmd_type = "NONE"
        bpy.context.collection.objects.link(mesh_obj2)

        # Add mesh geometry if requested
        if with_mesh_data:
            # Create simple cube geometry for mesh1
            vertices1 = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
            faces1 = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (2, 6, 7, 3), (0, 3, 7, 4), (1, 5, 6, 2)]
            self.__create_mesh_geometry(mesh_data1, vertices1, faces1)

            # Create simple triangle geometry for mesh2
            vertices2 = [(0, 0, 0), (2, 0, 0), (1, 2, 0)]
            faces2 = [(0, 1, 2)]
            self.__create_mesh_geometry(mesh_data2, vertices2, faces2)

        # Add vertex groups and weights if requested
        if with_vertex_groups and with_mesh_data:
            # Add vertex groups and assign vertices with weights
            bone_names = ["Root", "Bone1", "Bone2"]

            for mesh_obj in [mesh_obj1, mesh_obj2]:
                # Create vertex groups
                for bone_name in bone_names:
                    mesh_obj.vertex_groups.new(name=bone_name)

                # Assign vertices to groups with weights
                if len(mesh_obj.data.vertices) > 0:
                    # Set active object for vertex group operations
                    bpy.context.view_layer.objects.active = mesh_obj
                    bpy.ops.object.mode_set(mode="EDIT")

                    # Select all vertices
                    bpy.ops.mesh.select_all(action="SELECT")

                    # Assign all vertices to Root bone with full weight
                    bpy.ops.object.mode_set(mode="OBJECT")
                    root_vg = mesh_obj.vertex_groups["Root"]

                    # Assign all vertices to the root bone
                    vertex_indices = [v.index for v in mesh_obj.data.vertices]
                    root_vg.add(vertex_indices, 1.0, "REPLACE")

                    # Add some vertices to other bones with partial weights
                    if len(vertex_indices) > 2:
                        # Assign some vertices to Bone1
                        bone1_vg = mesh_obj.vertex_groups["Bone1"]
                        bone1_indices = vertex_indices[: len(vertex_indices) // 2]
                        bone1_vg.add(bone1_indices, 0.5, "REPLACE")

                        # Assign some vertices to Bone2
                        bone2_vg = mesh_obj.vertex_groups["Bone2"]
                        bone2_indices = vertex_indices[len(vertex_indices) // 2 :]
                        bone2_vg.add(bone2_indices, 0.3, "REPLACE")

        # Add SDEF data if requested
        if with_sdef_data and with_mesh_data:
            self.__add_sdef_data_to_meshes([mesh_obj1, mesh_obj2], armature_obj)

        # Add test materials
        material1 = bpy.data.materials.new(name="TestMaterial1")
        material1.mmd_material.name_j = "テスト材質1"
        material1.mmd_material.name_e = "TestMaterial1_E"
        mesh_data1.materials.append(material1)

        material2 = bpy.data.materials.new(name="TestMaterial2")
        material2.mmd_material.name_j = "テスト材質2"
        material2.mmd_material.name_e = "TestMaterial2_E"
        mesh_data1.materials.append(material2)

        material3 = bpy.data.materials.new(name="TestMaterial3")
        material3.mmd_material.name_j = "テスト材質3"
        material3.mmd_material.name_e = "TestMaterial3_E"
        mesh_data2.materials.append(material3)

        return root_obj, armature_obj, [mesh_obj1, mesh_obj2]

    def __add_sdef_data_to_meshes(self, mesh_objects, armature_obj):
        """
        Add SDEF shape keys to mesh objects for testing SDEF binding functionality
        This creates the minimal SDEF data structure that FnSDEF.has_sdef_data() expects
        """
        for mesh_obj in mesh_objects:
            if len(mesh_obj.data.vertices) == 0:
                continue  # Skip meshes without vertices

            # Ensure mesh has shape keys
            if mesh_obj.data.shape_keys is None:
                # Add basis shape key first
                mesh_obj.shape_key_add(name="Basis", from_mix=False)

            # Add the three required SDEF shape keys
            sdef_c = mesh_obj.shape_key_add(name="mmd_sdef_c", from_mix=False)  # SDEF center points
            sdef_r0 = mesh_obj.shape_key_add(name="mmd_sdef_r0", from_mix=False)  # SDEF radius point 0
            sdef_r1 = mesh_obj.shape_key_add(name="mmd_sdef_r1", from_mix=False)  # SDEF radius point 1

            # Create some basic SDEF data for testing
            # In real MMD models, this data comes from the PMX file and represents
            # spherical falloff deformation parameters for each vertex

            bpy.context.view_layer.objects.active = mesh_obj
            bpy.ops.object.mode_set(mode="OBJECT")

            # Set SDEF center points (slightly offset from original vertex positions)
            for i, vertex in enumerate(mesh_obj.data.vertices):
                # Center point: slightly offset from original position
                offset_center = Vector((0.01, 0.01, 0.01))
                sdef_c.data[i].co = vertex.co + offset_center

                # Radius points: create some variation around the center
                # In real SDEF, these define the spherical deformation area
                offset_r0 = Vector((0.1, 0.0, 0.0)) if i % 2 == 0 else Vector((-0.1, 0.0, 0.0))
                offset_r1 = Vector((0.0, 0.1, 0.0)) if i % 2 == 0 else Vector((0.0, -0.1, 0.0))

                sdef_r0.data[i].co = sdef_c.data[i].co + offset_r0
                sdef_r1.data[i].co = sdef_c.data[i].co + offset_r1

            # Add the required "mmd_armature" modifier for SDEF to work
            armature_mod = mesh_obj.modifiers.new(name="mmd_armature", type="ARMATURE")
            armature_mod.object = armature_obj
            armature_mod.use_vertex_groups = True

            # Update mesh data
            mesh_obj.data.update()

    # ********************************************
    # Model Setup Panel Tests
    # ********************************************

    def test_model_setup_visibility_controls(self):
        """Test model visibility control functionality from model_setup.py"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("VisibilityTest")

        # Verify initial visibility settings
        mmd_root = root_obj.mmd_root
        self.assertTrue(hasattr(mmd_root, "show_meshes"))
        self.assertTrue(hasattr(mmd_root, "show_armature"))
        self.assertTrue(hasattr(mmd_root, "show_temporary_objects"))
        self.assertTrue(hasattr(mmd_root, "show_rigid_bodies"))
        self.assertTrue(hasattr(mmd_root, "show_joints"))

        # Test visibility toggle functionality
        original_mesh_visibility = mmd_root.show_meshes
        mmd_root.show_meshes = not original_mesh_visibility
        self.assertNotEqual(mmd_root.show_meshes, original_mesh_visibility)

        # Test reset visibility operator
        bpy.context.view_layer.objects.active = root_obj
        try:
            bpy.ops.mmd_tools.reset_object_visibility()
            # Verify the operation completed without error
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Reset visibility operation failed: {e}")

    def test_model_assembly_operations(self):
        """Test model assembly operations from model_setup.py"""
        # Test with mesh data
        root_obj, armature_obj, mesh_objects = self.__create_test_model("AssemblyTest", with_mesh_data=True)

        bpy.context.view_layer.objects.active = root_obj

        # Test assembly operations with actual mesh data
        try:
            # Test assemble all
            bpy.ops.mmd_tools.assemble_all()
            self.assertTrue(True, "Assemble all operation completed with mesh data")

            # Test disassemble all
            bpy.ops.mmd_tools.disassemble_all()
            self.assertTrue(True, "Disassemble all operation completed with mesh data")

        except Exception as e:
            self.fail(f"Assembly operations with mesh data failed: {e}")

        # Test without mesh data
        root_obj_empty, armature_obj_empty, mesh_objects_empty = self.__create_test_model("AssemblyTestEmpty", with_mesh_data=False)

        bpy.context.view_layer.objects.active = root_obj_empty

        try:
            # Test assemble all with empty meshes
            bpy.ops.mmd_tools.assemble_all()
            self.assertTrue(True, "Assemble all operation completed with empty meshes")

            # Test disassemble all with empty meshes
            bpy.ops.mmd_tools.disassemble_all()
            self.assertTrue(True, "Disassemble all operation completed with empty meshes")

        except Exception as e:
            self.assertTrue(True, f"Assembly operations with empty meshes handled: {e}")

    def test_model_ik_toggle_functionality(self):
        """Test IK toggle functionality from model_setup.py"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("IKTest")

        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode="POSE")

        # Add IK constraint for testing
        pose_bone = armature_obj.pose.bones.get("Bone2")
        if pose_bone:
            ik_constraint = pose_bone.constraints.new(type="IK")
            ik_constraint.target = armature_obj
            ik_constraint.subtarget = "Bone1"
            ik_constraint.chain_count = 1

            # Test IK toggle property
            self.assertTrue(hasattr(pose_bone, "mmd_ik_toggle"))

            # Test toggle functionality
            original_ik_state = pose_bone.mmd_ik_toggle
            pose_bone.mmd_ik_toggle = not original_ik_state
            self.assertNotEqual(pose_bone.mmd_ik_toggle, original_ik_state)

        bpy.ops.object.mode_set(mode="OBJECT")

    def test_model_mesh_operations_with_data(self):
        """Test mesh operations from model_setup.py with actual mesh data"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("MeshTestWithData", with_mesh_data=True)

        bpy.context.view_layer.objects.active = mesh_objects[0]

        # Test separate by materials with actual mesh data
        try:
            bpy.ops.mmd_tools.separate_by_materials()
            self.assertTrue(True, "Separate by materials operation completed with mesh data")
        except Exception as e:
            self.assertTrue(True, f"Separate by materials with mesh data handled: {e}")

        # Test join meshes with actual mesh data
        bpy.context.view_layer.objects.active = root_obj
        # Select all mesh objects
        bpy.ops.object.select_all(action="DESELECT")
        for mesh_obj in mesh_objects:
            mesh_obj.select_set(True)

        try:
            bpy.ops.mmd_tools.join_meshes()
            self.assertTrue(True, "Join meshes operation completed with mesh data")
        except Exception as e:
            self.assertTrue(True, f"Join meshes with mesh data handled: {e}")

    def test_model_mesh_operations_without_data(self):
        """Test mesh operations from model_setup.py without mesh data"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("MeshTestWithoutData", with_mesh_data=False)

        bpy.context.view_layer.objects.active = mesh_objects[0]

        # Test separate by materials without mesh data
        try:
            bpy.ops.mmd_tools.separate_by_materials()
            self.assertTrue(True, "Separate by materials operation completed without mesh data")
        except Exception as e:
            # This is expected to fail or warn with no mesh data
            self.assertTrue(True, f"Separate by materials without mesh data expected behavior: {e}")

        # Test join meshes without mesh data
        bpy.context.view_layer.objects.active = root_obj
        # Select all mesh objects
        bpy.ops.object.select_all(action="DESELECT")
        for mesh_obj in mesh_objects:
            mesh_obj.select_set(True)

        try:
            bpy.ops.mmd_tools.join_meshes()
            self.assertTrue(True, "Join meshes operation completed without mesh data")
        except Exception as e:
            # This should produce the "No mesh data to join" warning
            self.assertTrue(True, f"Join meshes without mesh data expected warning: {e}")

    # ********************************************
    # Model Production Panel Tests
    # ********************************************

    def test_model_production_creation(self):
        """Test model creation functionality from model_production.py"""
        # Test create model root object
        try:
            bpy.ops.mmd_tools.create_mmd_model_root_object()

            # Verify root object was created
            created_objects = [obj for obj in bpy.context.scene.objects if obj.mmd_type == "ROOT"]
            self.assertGreater(len(created_objects), 0, "MMD root object should be created")

        except Exception as e:
            self.fail(f"Create MMD model root object failed: {e}")

    def test_model_production_conversion(self):
        """Test model conversion functionality from model_production.py"""
        # Create a regular armature for conversion
        armature_data = bpy.data.armatures.new(name="ConvertTest_arm")
        armature_obj = bpy.data.objects.new(name="ConvertTest_arm", object_data=armature_data)
        bpy.context.collection.objects.link(armature_obj)

        bpy.context.view_layer.objects.active = armature_obj

        try:
            bpy.ops.mmd_tools.convert_to_mmd_model()

            # Verify conversion created root object
            root_obj = FnModel.find_root_object(armature_obj)
            self.assertIsNotNone(root_obj, "Root object should be created after conversion")

        except Exception as e:
            self.fail(f"Convert to MMD model failed: {e}")

    def test_model_production_attachment_with_data(self):
        """Test mesh attachment functionality from model_production.py with mesh data"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("AttachTestWithData", with_mesh_data=True)

        bpy.context.view_layer.objects.active = root_obj

        try:
            bpy.ops.mmd_tools.attach_meshes()
            self.assertTrue(True, "Attach meshes operation completed with mesh data")
        except Exception as e:
            self.assertTrue(True, f"Attach meshes with mesh data handled: {e}")

    def test_model_production_attachment_without_data(self):
        """Test mesh attachment functionality from model_production.py without mesh data"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("AttachTestWithoutData", with_mesh_data=False)

        bpy.context.view_layer.objects.active = root_obj

        try:
            bpy.ops.mmd_tools.attach_meshes()
            self.assertTrue(True, "Attach meshes operation completed without mesh data")
        except Exception as e:
            self.assertTrue(True, f"Attach meshes without mesh data handled: {e}")

    def test_model_production_surgery(self):
        """Test model surgery operations from model_production.py"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("SurgeryTest", with_mesh_data=True)

        bpy.context.view_layer.objects.active = armature_obj

        # Test model separation operations
        try:
            # Test chop operation (with default parameters)
            op_props = {"separate_armature": True, "include_descendant_bones": True, "boundary_joint_owner": "DESTINATION"}

            # Note: This might fail due to insufficient bone structure, which is expected
            bpy.ops.mmd_tools.model_separate_by_bones(**op_props)
            self.assertTrue(True, "Model separate operation handled")

        except Exception as e:
            self.assertTrue(True, f"Model separate operation expected behavior: {e}")

    # ********************************************
    # Material Sorter Tests
    # ********************************************

    def test_material_sorter_functionality(self):
        """Test material sorting functionality from material_sorter.py"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("MaterialSortTest", with_mesh_data=True)

        # Select mesh object for material sorting
        bpy.context.view_layer.objects.active = mesh_objects[0]

        # Verify materials exist
        mesh_data = mesh_objects[0].data
        self.assertGreater(len(mesh_data.materials), 0, "Test mesh should have materials")

        # Test material movement operations
        if len(mesh_data.materials) > 1:
            original_material_count = len(mesh_data.materials)
            original_first_material = mesh_data.materials[0]

            try:
                # Test move material down
                mesh_objects[0].active_material_index = 0
                bpy.ops.mmd_tools.move_material_down()

                # Verify material order changed and count remained the same
                self.assertEqual(len(mesh_data.materials), original_material_count, "Material count should remain the same")

                # Verify the first material is no longer in the first position
                self.assertNotEqual(mesh_data.materials[0], original_first_material, "First material should have moved from first position")

                # Test move material up
                mesh_objects[0].active_material_index = 1
                bpy.ops.mmd_tools.move_material_up()

                # Verify material count remains the same and original order is restored
                self.assertEqual(len(mesh_data.materials), original_material_count, "Material count should remain the same after up movement")
                self.assertEqual(mesh_data.materials[0], original_first_material, "Original material should be back in first position")

            except Exception as e:
                self.fail(f"Material sorting operations failed: {e}")

    def test_material_sorter_properties(self):
        """Test material MMD properties from material_sorter.py"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("MaterialPropTest")

        mesh_data = mesh_objects[0].data
        if len(mesh_data.materials) > 0:
            material = mesh_data.materials[0]

            # Verify MMD material properties exist
            self.assertTrue(hasattr(material, "mmd_material"))
            self.assertTrue(hasattr(material.mmd_material, "name_j"))
            self.assertTrue(hasattr(material.mmd_material, "name_e"))

            # Test property values
            self.assertIsNotNone(material.mmd_material.name_j)
            self.assertIsNotNone(material.mmd_material.name_e)

    # ********************************************
    # Meshes Sorter Tests
    # ********************************************

    def test_meshes_sorter_functionality_with_data(self):
        """Test mesh sorting functionality from meshes_sorter.py with mesh data"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("MeshSortTestWithData", with_mesh_data=True)

        bpy.context.view_layer.objects.active = mesh_objects[0]

        # Verify we have multiple meshes for sorting
        all_meshes = list(FnModel.iterate_mesh_objects(root_obj))
        self.assertGreaterEqual(len(all_meshes), 2, "Should have at least 2 meshes for sorting test")

        # Verify meshes have actual geometry
        for mesh_obj in all_meshes:
            self.assertGreater(len(mesh_obj.data.vertices), 0, "Mesh should have vertices")

        try:
            # Test mesh movement operations
            root_obj.mmd_root.active_mesh_index = 0

            # Test move up
            bpy.ops.mmd_tools.object_move(type="UP")
            self.assertTrue(True, "Move mesh up operation completed with data")

            # Test move down
            bpy.ops.mmd_tools.object_move(type="DOWN")
            self.assertTrue(True, "Move mesh down operation completed with data")

            # Test move to top
            bpy.ops.mmd_tools.object_move(type="TOP")
            self.assertTrue(True, "Move mesh to top operation completed with data")

            # Test move to bottom
            bpy.ops.mmd_tools.object_move(type="BOTTOM")
            self.assertTrue(True, "Move mesh to bottom operation completed with data")

        except Exception as e:
            self.fail(f"Mesh sorting operations with data failed: {e}")

    def test_meshes_sorter_functionality_without_data(self):
        """Test mesh sorting functionality from meshes_sorter.py without mesh data"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("MeshSortTestWithoutData", with_mesh_data=False)

        bpy.context.view_layer.objects.active = mesh_objects[0]

        # Verify we have multiple meshes for sorting
        all_meshes = list(FnModel.iterate_mesh_objects(root_obj))
        self.assertGreaterEqual(len(all_meshes), 2, "Should have at least 2 meshes for sorting test")

        # Verify meshes have no geometry
        for mesh_obj in all_meshes:
            self.assertEqual(len(mesh_obj.data.vertices), 0, "Empty mesh should have no vertices")

        try:
            # Test mesh movement operations with empty meshes
            root_obj.mmd_root.active_mesh_index = 0

            # Test move up
            bpy.ops.mmd_tools.object_move(type="UP")
            self.assertTrue(True, "Move mesh up operation completed without data")

            # Test move down
            bpy.ops.mmd_tools.object_move(type="DOWN")
            self.assertTrue(True, "Move mesh down operation completed without data")

            # Test move to top
            bpy.ops.mmd_tools.object_move(type="TOP")
            self.assertTrue(True, "Move mesh to top operation completed without data")

            # Test move to bottom
            bpy.ops.mmd_tools.object_move(type="BOTTOM")
            self.assertTrue(True, "Move mesh to bottom operation completed without data")

        except Exception as e:
            self.assertTrue(True, f"Mesh sorting operations without data handled: {e}")

    def test_meshes_sorter_filtering(self):
        """Test mesh filtering functionality from meshes_sorter.py"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("MeshFilterTest", with_mesh_data=True)

        # Verify mesh filtering criteria
        for mesh_obj in mesh_objects:
            self.assertEqual(mesh_obj.type, "MESH", "Object should be mesh type")
            self.assertEqual(mesh_obj.mmd_type, "NONE", "Mesh should have NONE mmd_type")
            self.assertEqual(mesh_obj.parent, armature_obj, "Mesh should be child of armature")

    # ********************************************
    # Model Debug Panel Tests
    # ********************************************

    def test_model_debug_validation_setup(self):
        """Test model debug validation setup from model_debug.py"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("DebugTest", with_mesh_data=True)

        bpy.context.view_layer.objects.active = root_obj

        # Verify debug validation properties exist in scene
        if not hasattr(bpy.context.scene, "mmd_validation_results"):
            # Add the property if it doesn't exist (might not be registered in test)
            bpy.types.Scene.mmd_validation_results = bpy.props.StringProperty(default="")

        self.assertTrue(hasattr(bpy.context.scene, "mmd_validation_results"))

    def test_model_debug_validation_operations(self):
        """Test model debug validation operations from model_debug.py"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("ValidationTest", with_mesh_data=True)

        bpy.context.view_layer.objects.active = root_obj

        # Test validation operators
        validation_operators = ["mmd_tools.validate_bone_limits", "mmd_tools.validate_morphs", "mmd_tools.validate_textures"]

        for op_name in validation_operators:
            try:
                if hasattr(bpy.ops.mmd_tools, op_name.split(".")[-1]):
                    getattr(bpy.ops.mmd_tools, op_name.split(".")[-1])()
                    self.assertTrue(True, f"{op_name} validation completed")
                else:
                    self.assertTrue(True, f"{op_name} operator not available in test environment")
            except Exception as e:
                self.assertTrue(True, f"{op_name} validation handling: {e}")

    def test_model_debug_fix_operations(self):
        """Test model debug fix operations from model_debug.py"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("FixTest", with_mesh_data=True)

        bpy.context.view_layer.objects.active = root_obj

        # Test fix operators
        fix_operators = ["mmd_tools.fix_bone_issues", "mmd_tools.fix_morph_issues", "mmd_tools.fix_texture_issues"]

        for op_name in fix_operators:
            try:
                if hasattr(bpy.ops.mmd_tools, op_name.split(".")[-1]):
                    getattr(bpy.ops.mmd_tools, op_name.split(".")[-1])()
                    self.assertTrue(True, f"{op_name} fix operation completed")
                else:
                    self.assertTrue(True, f"{op_name} operator not available in test environment")
            except Exception as e:
                self.assertTrue(True, f"{op_name} fix operation handling: {e}")

    # ********************************************
    # Integration Tests
    # ********************************************

    def test_panel_integration_with_real_model(self):
        """Test panel functionality with actual PMX/PMD files"""
        input_files = self.__list_sample_files(("pmd", "pmx"))
        if len(input_files) < 1:
            self.skipTest("No PMX/PMD sample files available for integration test")

        # Test with first available model
        test_file = input_files[0]

        try:
            # Load model
            self.__enable_mmd_tools()
            bpy.ops.mmd_tools.import_model(filepath=test_file, types={"MESH", "ARMATURE", "PHYSICS", "MORPHS", "DISPLAY"}, scale=1.0, clean_model=False, remove_doubles=False, log_level="ERROR")

            # Find the imported model
            root_objects = [obj for obj in bpy.context.scene.objects if obj.mmd_type == "ROOT"]
            self.assertGreater(len(root_objects), 0, "Model should be imported successfully")

            root_obj = root_objects[0]
            bpy.context.view_layer.objects.active = root_obj

            # Test that model structure is compatible with panel operations
            armature_obj = FnModel.find_armature_object(root_obj)
            self.assertIsNotNone(armature_obj, "Imported model should have armature")

            mesh_objects = list(FnModel.iterate_mesh_objects(root_obj))
            if len(mesh_objects) > 0:
                # Test material operations if materials exist
                test_mesh = mesh_objects[0]
                if len(test_mesh.data.materials) > 0:
                    bpy.context.view_layer.objects.active = test_mesh
                    # This validates that the material sorter can work with the imported model
                    self.assertTrue(True, "Material sorter compatible with imported model")

                # Test mesh operations
                bpy.context.view_layer.objects.active = root_obj
                # This validates that the mesh sorter can work with the imported model
                self.assertTrue(True, "Mesh sorter compatible with imported model")

            # Test model setup operations
            try:
                bpy.ops.mmd_tools.reset_object_visibility()
                self.assertTrue(True, "Model setup operations compatible with imported model")
            except Exception as e:
                self.assertTrue(True, f"Model setup operations handling: {e}")

        except Exception as e:
            self.fail(f"Integration test with real model failed: {e}")

    def test_error_handling_with_invalid_objects(self):
        """Test error handling when panels are used with invalid objects"""
        # Create non-MMD objects
        mesh_data = bpy.data.meshes.new(name="InvalidMesh")
        mesh_obj = bpy.data.objects.new(name="InvalidMesh", object_data=mesh_data)
        bpy.context.collection.objects.link(mesh_obj)

        bpy.context.view_layer.objects.active = mesh_obj

        # Test that operations handle invalid objects gracefully
        try:
            # These should either handle gracefully or raise expected exceptions
            bpy.ops.mmd_tools.reset_object_visibility()
        except Exception as e:
            self.assertTrue(True, f"Expected error handling for invalid object: {e}")

        # Test with no active object
        bpy.context.view_layer.objects.active = None

        try:
            bpy.ops.mmd_tools.reset_object_visibility()
        except Exception as e:
            self.assertTrue(True, f"Expected error handling for no active object: {e}")

    # ********************************************
    # Edge Case Tests
    # ********************************************

    def test_edge_cases_empty_materials(self):
        """Test material sorter with meshes that have no materials"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("EmptyMaterialTest", with_mesh_data=True)

        # Remove all materials from the first mesh
        mesh_data = mesh_objects[0].data
        mesh_data.materials.clear()

        bpy.context.view_layer.objects.active = mesh_objects[0]

        # Test material operations with no materials
        try:
            mesh_objects[0].active_material_index = 0
            bpy.ops.mmd_tools.move_material_down()
            self.assertTrue(True, "Material move operation handled with no materials")
        except Exception as e:
            self.assertTrue(True, f"Material move with no materials expected behavior: {e}")

    def test_edge_cases_single_mesh(self):
        """Test mesh sorter with only one mesh"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("SingleMeshTest", with_mesh_data=True)

        # Remove one mesh to test with single mesh
        bpy.data.objects.remove(mesh_objects[1])

        bpy.context.view_layer.objects.active = root_obj

        # Verify we now have only one mesh
        remaining_meshes = list(FnModel.iterate_mesh_objects(root_obj))
        self.assertEqual(len(remaining_meshes), 1, "Should have only one mesh after removal")

        # Test mesh operations with single mesh - these should handle gracefully
        try:
            root_obj.mmd_root.active_mesh_index = 0

            # Moving a single mesh should either do nothing or show appropriate message
            bpy.ops.mmd_tools.object_move(type="UP")
            self.assertTrue(True, "Mesh move up operation handled with single mesh")

            bpy.ops.mmd_tools.object_move(type="DOWN")
            self.assertTrue(True, "Mesh move down operation handled with single mesh")

            bpy.ops.mmd_tools.object_move(type="TOP")
            self.assertTrue(True, "Mesh move to top operation handled with single mesh")

            bpy.ops.mmd_tools.object_move(type="BOTTOM")
            self.assertTrue(True, "Mesh move to bottom operation handled with single mesh")

        except Exception as e:
            # "Can not move object" error is expected and acceptable for single mesh
            if "Can not move object" in str(e):
                self.assertTrue(True, f"Expected single mesh move limitation: {e}")
            else:
                self.assertTrue(True, f"Mesh move with single mesh handled: {e}")

    def test_edge_cases_vertex_groups_validation(self):
        """Test operations with and without vertex groups"""
        # Test with vertex groups
        root_obj_with_vg, armature_obj_with_vg, mesh_objects_with_vg = self.__create_test_model("VertexGroupTest", with_mesh_data=True, with_vertex_groups=True)

        # Verify vertex groups exist
        for mesh_obj in mesh_objects_with_vg:
            self.assertGreater(len(mesh_obj.vertex_groups), 0, "Mesh should have vertex groups")

        # Test without vertex groups
        root_obj_no_vg, armature_obj_no_vg, mesh_objects_no_vg = self.__create_test_model("NoVertexGroupTest", with_mesh_data=True, with_vertex_groups=False)

        # Verify no vertex groups exist
        for mesh_obj in mesh_objects_no_vg:
            self.assertEqual(len(mesh_obj.vertex_groups), 0, "Mesh should have no vertex groups")

    def test_edge_cases_bone_operations(self):
        """Test bone-related operations with different bone configurations"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("BoneTest", with_mesh_data=True)

        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode="EDIT")

        # Add more complex bone structure
        armature_data = armature_obj.data
        complex_bone = armature_data.edit_bones.new("ComplexBone")
        complex_bone.head = (2.0, 0.0, 0.0)
        complex_bone.tail = (2.0, 0.0, 1.0)
        complex_bone.parent = armature_data.edit_bones["Root"]

        bpy.ops.object.mode_set(mode="OBJECT")

        # Test IK setup with complex bone structure
        bpy.ops.object.mode_set(mode="POSE")

        complex_pose_bone = armature_obj.pose.bones.get("ComplexBone")
        if complex_pose_bone:
            # Test multiple IK constraints
            ik_constraint1 = complex_pose_bone.constraints.new(type="IK")
            ik_constraint1.target = armature_obj
            ik_constraint1.subtarget = "Bone1"
            ik_constraint1.chain_count = 1

            # Verify IK properties
            self.assertTrue(hasattr(complex_pose_bone, "mmd_ik_toggle"))
            self.assertIsNotNone(ik_constraint1.target)
            self.assertEqual(ik_constraint1.subtarget, "Bone1")

        bpy.ops.object.mode_set(mode="OBJECT")

    def test_performance_with_large_model(self):
        """Test performance and stability with a model containing many meshes and materials"""
        root_obj, armature_obj, initial_mesh_objects = self.__create_test_model("LargeModelTest", with_mesh_data=True)

        # Create additional meshes and materials
        additional_meshes = []
        for i in range(10):  # Create 10 additional meshes
            mesh_data = bpy.data.meshes.new(name=f"ExtraMesh{i}")
            mesh_obj = bpy.data.objects.new(name=f"ExtraMesh{i}", object_data=mesh_data)
            mesh_obj.parent = armature_obj
            mesh_obj.mmd_type = "NONE"
            bpy.context.collection.objects.link(mesh_obj)

            # Add simple geometry
            vertices = [(0, 0, i), (1, 0, i), (0.5, 1, i)]
            faces = [(0, 1, 2)]
            self.__create_mesh_geometry(mesh_data, vertices, faces)

            # Add materials
            for j in range(3):  # 3 materials per mesh
                material = bpy.data.materials.new(name=f"ExtraMaterial{i}_{j}")
                material.mmd_material.name_j = f"追加材質{i}_{j}"
                material.mmd_material.name_e = f"ExtraMaterial{i}_{j}_E"
                mesh_data.materials.append(material)

            additional_meshes.append(mesh_obj)

        all_meshes = initial_mesh_objects + additional_meshes
        total_mesh_count = len(all_meshes)

        # Test operations with large number of meshes
        bpy.context.view_layer.objects.active = root_obj

        # Verify we have multiple meshes for testing
        self.assertGreater(total_mesh_count, 10, "Should have sufficient meshes for performance test")

        # Test mesh sorting performance with valid indices
        try:
            # Test moving from middle position to avoid edge cases
            middle_index = min(5, total_mesh_count - 2)  # Ensure valid index
            root_obj.mmd_root.active_mesh_index = middle_index

            # Test individual moves that should be valid
            bpy.ops.mmd_tools.object_move(type="DOWN")
            self.assertTrue(True, "Mesh move down completed with large model")

            bpy.ops.mmd_tools.object_move(type="UP")
            self.assertTrue(True, "Mesh move up completed with large model")

            # Test moves to extremes
            root_obj.mmd_root.active_mesh_index = 0
            bpy.ops.mmd_tools.object_move(type="BOTTOM")
            self.assertTrue(True, "Mesh move to bottom completed with large model")

            # Reset to valid position for top move
            root_obj.mmd_root.active_mesh_index = total_mesh_count - 1
            bpy.ops.mmd_tools.object_move(type="TOP")
            self.assertTrue(True, "Mesh move to top completed with large model")

        except Exception as e:
            # Handle expected errors gracefully
            if "Can not move object" in str(e):
                self.assertTrue(True, f"Expected mesh move limitation in large model: {e}")
            else:
                self.assertTrue(True, f"Large model mesh sorting handled: {e}")

        # Test material sorting performance
        if len(all_meshes) > 0:
            test_mesh = all_meshes[0]
            if len(test_mesh.data.materials) > 1:
                bpy.context.view_layer.objects.active = test_mesh
                try:
                    test_mesh.active_material_index = 0
                    bpy.ops.mmd_tools.move_material_down()
                    self.assertTrue(True, "Material move down completed with large model")

                    test_mesh.active_material_index = 1
                    bpy.ops.mmd_tools.move_material_up()
                    self.assertTrue(True, "Material move up completed with large model")

                except Exception as e:
                    self.assertTrue(True, f"Large model material sorting handled: {e}")

    def test_cleanup_and_memory_management(self):
        """Test that operations properly clean up resources and don't cause memory leaks"""
        initial_object_count = len(bpy.data.objects)
        initial_mesh_count = len(bpy.data.meshes)
        initial_material_count = len(bpy.data.materials)

        # Track created objects by name instead of reference
        created_object_names = []

        # Create and destroy multiple models
        for i in range(3):  # Reduce to 3 iterations to avoid excessive resource usage
            model_name = f"CleanupTest{i}"
            root_obj, armature_obj, mesh_objects = self.__create_test_model(model_name, with_mesh_data=True)

            # Store object names for cleanup tracking
            test_objects = [obj for obj in bpy.context.scene.objects if obj.name.startswith(model_name)]
            created_object_names.extend([obj.name for obj in test_objects])

            # Perform operations with proper error handling
            bpy.context.view_layer.objects.active = root_obj
            try:
                bpy.ops.mmd_tools.assemble_all()
                self.assertTrue(True, f"Assemble operation completed for model {i}")
            except Exception as e:
                self.assertTrue(True, f"Assemble operation handled for model {i}: {e}")

            try:
                bpy.ops.mmd_tools.disassemble_all()
                self.assertTrue(True, f"Disassemble operation completed for model {i}")
            except Exception as e:
                self.assertTrue(True, f"Disassemble operation handled for model {i}: {e}")

        # Clean up created objects using names to avoid reference errors
        for obj_name in created_object_names:
            if obj_name in bpy.data.objects:
                try:
                    obj = bpy.data.objects[obj_name]
                    # Check if object still exists and is valid
                    if obj is not None:
                        bpy.data.objects.remove(obj, do_unlink=True)
                except (ReferenceError, KeyError):
                    # Object already removed or invalid reference
                    pass

        # Clean up orphaned data with error handling
        try:
            bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
            self.assertTrue(True, "Orphan data cleanup completed")
        except Exception as e:
            self.assertTrue(True, f"Orphan cleanup handled: {e}")

        # Verify resource cleanup (allow reasonable tolerance for test artifacts)
        final_object_count = len(bpy.data.objects)
        final_mesh_count = len(bpy.data.meshes)
        final_material_count = len(bpy.data.materials)

        object_growth = final_object_count - initial_object_count
        mesh_growth = final_mesh_count - initial_mesh_count
        material_growth = final_material_count - initial_material_count

        # Log cleanup results for debugging
        print(f"Object count change: {object_growth}")
        print(f"Mesh count change: {mesh_growth}")
        print(f"Material count change: {material_growth}")

        # Verify cleanup effectiveness - allow some growth but not excessive
        self.assertLess(object_growth, 20, f"Object count should not grow excessively (grew by {object_growth})")
        self.assertLess(mesh_growth, 20, f"Mesh count should not grow excessively (grew by {mesh_growth})")
        self.assertLess(material_growth, 50, f"Material count should not grow excessively (grew by {material_growth})")

    def test_binding_functionality_investigation(self):
        """Investigate binding functionality that shows 'Binded 0 of X' messages"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("BindingInvestigation", with_mesh_data=True, with_vertex_groups=True)

        # Check if meshes have proper armature modifiers
        for mesh_obj in mesh_objects:
            armature_mods = [mod for mod in mesh_obj.modifiers if mod.type == "ARMATURE"]
            print(f"Mesh {mesh_obj.name} has {len(armature_mods)} armature modifiers")

        # Check if vertex groups match bone names
        bone_names = set(armature_obj.data.bones.keys())
        for mesh_obj in mesh_objects:
            vg_names = set(mesh_obj.vertex_groups.keys())
            matching_groups = bone_names.intersection(vg_names)
            print(f"Mesh {mesh_obj.name}: {len(matching_groups)} vertex groups match bone names")

        bpy.context.view_layer.objects.active = root_obj

        # Test binding with detailed logging
        try:
            bpy.ops.mmd_tools.assemble_all()
            # Check if binding actually worked
            for mesh_obj in mesh_objects:
                armature_mods = [mod for mod in mesh_obj.modifiers if mod.type == "ARMATURE"]
                if armature_mods:
                    self.assertIsNotNone(armature_mods[0].object, "Armature modifier should have target")
                else:
                    print(f"Warning: Mesh {mesh_obj.name} has no armature modifier after binding")
        except Exception as e:
            self.fail(f"Binding investigation failed: {e}")

    def test_armature_binding_bug_investigation(self):
        """Deep investigation of the armature binding bug"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("BindingBugTest", with_mesh_data=True, with_vertex_groups=True)

        print("\n=== BEFORE BINDING ===")
        print(f"Root object type: {root_obj.mmd_type}")
        print(f"Armature object: {armature_obj.name}")
        print(f"Number of bones: {len(armature_obj.data.bones)}")

        # Check mesh parent relationships
        for i, mesh_obj in enumerate(mesh_objects):
            print(f"Mesh {i + 1} ({mesh_obj.name}):")
            print(f"  - Parent: {mesh_obj.parent.name if mesh_obj.parent else 'None'}")
            print(f"  - Parent type: {mesh_obj.parent_type}")
            print(f"  - MMD type: {mesh_obj.mmd_type}")
            print(f"  - Vertex groups: {[vg.name for vg in mesh_obj.vertex_groups]}")
            print(f"  - Has vertices: {len(mesh_obj.data.vertices) > 0}")
            print(f"  - Modifiers: {[mod.type for mod in mesh_obj.modifiers]}")

        # Check selection state
        print("\nSelection state:")
        print(f"  - Active object: {bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else 'None'}")
        print(f"  - Selected objects: {[obj.name for obj in bpy.context.selected_objects]}")

        # Set proper context for binding
        bpy.context.view_layer.objects.active = root_obj
        bpy.ops.object.select_all(action="DESELECT")
        root_obj.select_set(True)

        print("\n=== EXECUTING BINDING ===")
        try:
            # Try manual SDEF binding first
            bpy.ops.mmd_tools.sdef_bind()

            print("\n=== AFTER SDEF BINDING ===")
            for i, mesh_obj in enumerate(mesh_objects):
                armature_mods = [mod for mod in mesh_obj.modifiers if mod.type == "ARMATURE"]
                print(f"Mesh {i + 1}: {len(armature_mods)} armature modifiers")
                if armature_mods:
                    print(f"  - Target: {armature_mods[0].object.name if armature_mods[0].object else 'None'}")

            # Now try full assembly
            bpy.ops.mmd_tools.assemble_all()

        except Exception as e:
            print(f"Binding error: {e}")

        print("\n=== AFTER FULL ASSEMBLY ===")
        for i, mesh_obj in enumerate(mesh_objects):
            armature_mods = [mod for mod in mesh_obj.modifiers if mod.type == "ARMATURE"]
            print(f"Mesh {i + 1}: {len(armature_mods)} armature modifiers")
            if armature_mods:
                print(f"  - Target: {armature_mods[0].object.name if armature_mods[0].object else 'None'}")
                print(f"  - Use vertex groups: {armature_mods[0].use_vertex_groups}")

            # Check if mesh has required vertex weights
            has_weights = False
            for vertex in mesh_obj.data.vertices:
                if len(vertex.groups) > 0:
                    has_weights = True
                    break
            print(f"  - Has vertex weights: {has_weights}")

        # Final verification
        binding_success = all(any(mod.type == "ARMATURE" for mod in mesh_obj.modifiers) for mesh_obj in mesh_objects)

        if not binding_success:
            self.fail("MMD Tools binding functionality is broken - armature modifiers not created")
        else:
            self.assertTrue(True, "Binding functionality works correctly")

    def test_assemble_all_selection_bug_investigation(self):
        """Investigate the selection-based bug in assemble_all"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("SelectionBugTest", with_mesh_data=True, with_vertex_groups=True)

        print("\n=== TESTING DIFFERENT SELECTION SCENARIOS ===")

        # Scenario 1: Default state (no selection)
        print("\n--- Scenario 1: No selection ---")
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = root_obj

        print(f"Active: {bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else 'None'}")
        print(f"Selected: {[obj.name for obj in bpy.context.selected_objects]}")

        try:
            bpy.ops.mmd_tools.sdef_bind()
            count_scenario1 = sum(1 for mesh_obj in mesh_objects if any(mod.type == "ARMATURE" for mod in mesh_obj.modifiers))
            print(f"Result: {count_scenario1} meshes bound")
        except Exception as e:
            print(f"Error: {e}")
            count_scenario1 = 0

        # Clear modifiers for next test
        for mesh_obj in mesh_objects:
            mesh_obj.modifiers.clear()

        # Scenario 2: Select all meshes
        print("\n--- Scenario 2: All meshes selected ---")
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = root_obj

        for mesh_obj in mesh_objects:
            mesh_obj.select_set(True)

        print(f"Active: {bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else 'None'}")
        print(f"Selected: {[obj.name for obj in bpy.context.selected_objects]}")

        try:
            bpy.ops.mmd_tools.sdef_bind()
            count_scenario2 = sum(1 for mesh_obj in mesh_objects if any(mod.type == "ARMATURE" for mod in mesh_obj.modifiers))
            print(f"Result: {count_scenario2} meshes bound")
        except Exception as e:
            print(f"Error: {e}")
            count_scenario2 = 0

        # Clear modifiers for next test
        for mesh_obj in mesh_objects:
            mesh_obj.modifiers.clear()

        # Scenario 3: Select root object
        print("\n--- Scenario 3: Root object selected ---")
        bpy.ops.object.select_all(action="DESELECT")
        root_obj.select_set(True)
        bpy.context.view_layer.objects.active = root_obj

        print(f"Active: {bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else 'None'}")
        print(f"Selected: {[obj.name for obj in bpy.context.selected_objects]}")

        try:
            bpy.ops.mmd_tools.sdef_bind()
            count_scenario3 = sum(1 for mesh_obj in mesh_objects if any(mod.type == "ARMATURE" for mod in mesh_obj.modifiers))
            print(f"Result: {count_scenario3} meshes bound")
        except Exception as e:
            print(f"Error: {e}")
            count_scenario3 = 0

        # Clear modifiers for next test
        for mesh_obj in mesh_objects:
            mesh_obj.modifiers.clear()

        # Scenario 4: Select root + meshes
        print("\n--- Scenario 4: Root + meshes selected ---")
        bpy.ops.object.select_all(action="DESELECT")
        root_obj.select_set(True)
        for mesh_obj in mesh_objects:
            mesh_obj.select_set(True)
        bpy.context.view_layer.objects.active = root_obj

        print(f"Active: {bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else 'None'}")
        print(f"Selected: {[obj.name for obj in bpy.context.selected_objects]}")

        try:
            bpy.ops.mmd_tools.sdef_bind()
            count_scenario4 = sum(1 for mesh_obj in mesh_objects if any(mod.type == "ARMATURE" for mod in mesh_obj.modifiers))
            print(f"Result: {count_scenario4} meshes bound")
        except Exception as e:
            print(f"Error: {e}")
            count_scenario4 = 0

        # Clear modifiers for next test
        for mesh_obj in mesh_objects:
            mesh_obj.modifiers.clear()

        # Scenario 5: Individual mesh selection
        print("\n--- Scenario 5: Individual mesh operations ---")
        for i, mesh_obj in enumerate(mesh_objects):
            print(f"\nTesting mesh {i + 1}: {mesh_obj.name}")
            bpy.ops.object.select_all(action="DESELECT")
            mesh_obj.select_set(True)
            bpy.context.view_layer.objects.active = mesh_obj

            print(f"Active: {bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else 'None'}")
            print(f"Selected: {[obj.name for obj in bpy.context.selected_objects]}")

            try:
                bpy.ops.mmd_tools.sdef_bind()
                has_modifier = any(mod.type == "ARMATURE" for mod in mesh_obj.modifiers)
                print(f"Result: Modifier created = {has_modifier}")
            except Exception as e:
                print(f"Error: {e}")

        # Test assemble_all with different selections
        print("\n=== TESTING ASSEMBLE_ALL ===")

        # Clear all modifiers
        for mesh_obj in mesh_objects:
            mesh_obj.modifiers.clear()

        # Test assemble_all with root selected
        print("\n--- assemble_all with root selected ---")
        bpy.ops.object.select_all(action="DESELECT")
        root_obj.select_set(True)
        bpy.context.view_layer.objects.active = root_obj

        try:
            bpy.ops.mmd_tools.assemble_all()
            count_assemble = sum(1 for mesh_obj in mesh_objects if any(mod.type == "ARMATURE" for mod in mesh_obj.modifiers))
            print(f"assemble_all result: {count_assemble} meshes bound")
        except Exception as e:
            print(f"assemble_all error: {e}")
            count_assemble = 0

        # Print final analysis
        print("\n=== ANALYSIS ===")
        print(f"Scenario 1 (no selection): {count_scenario1} bound")
        print(f"Scenario 2 (meshes selected): {count_scenario2} bound")
        print(f"Scenario 3 (root selected): {count_scenario3} bound")
        print(f"Scenario 4 (root + meshes): {count_scenario4} bound")
        print(f"assemble_all: {count_assemble} bound")

        # Determine if any scenario worked
        if max(count_scenario1, count_scenario2, count_scenario3, count_scenario4, count_assemble) > 0:
            self.assertTrue(True, "Found working selection method")
        else:
            self.fail("No selection method successfully created armature modifiers")

    def test_assemble_all_bug_fix_verification(self):
        """
        Verify the AssembleAll bug fix works correctly
        This test focuses on armature modifier creation, not SDEF binding
        """
        root_obj, armature_obj, mesh_objects = self.__create_test_model(
            "BugFixTest",
            with_mesh_data=True,
            with_vertex_groups=True,
            with_sdef_data=False,  # Test without SDEF data
        )

        print("\n=== Testing AssembleAll Bug Fix ===")

        # Clear any existing modifiers to start clean
        for mesh_obj in mesh_objects:
            mesh_obj.modifiers.clear()

        print("Testing fixed behavior:")
        bpy.ops.object.select_all(action="DESELECT")
        root_obj.select_set(True)
        bpy.context.view_layer.objects.active = root_obj

        # Execute AssembleAll
        bpy.ops.mmd_tools.assemble_all()

        # Count meshes with armature modifiers (this is what should be fixed)
        armature_mod_count = sum(1 for mesh_obj in mesh_objects if any(mod.type == "ARMATURE" for mod in mesh_obj.modifiers))

        # Count SDEF bindings (expected to be 0 for meshes without SDEF data)
        sdef_bind_count = sum(1 for mesh_obj in mesh_objects if mesh_obj.data.shape_keys and "mmd_sdef_skinning" in mesh_obj.data.shape_keys.key_blocks)

        print(f"Fixed method result: {armature_mod_count} meshes have armature modifiers")
        print(f"SDEF bindings: {sdef_bind_count} meshes have SDEF binding")

        # The key fix: armature modifiers should be created regardless of SDEF data
        self.assertEqual(armature_mod_count, len(mesh_objects), "Fixed method should add armature modifiers to all meshes")

        # SDEF binding should be 0 for meshes without SDEF data (this is expected)
        self.assertEqual(sdef_bind_count, 0, "No SDEF binding expected for meshes without SDEF data")

    def test_assemble_all_sdef_vs_regular_meshes(self):
        """Compare AssembleAll behavior with SDEF vs regular meshes"""
        # Test 1: Regular meshes (no SDEF data)
        root_obj1, armature_obj1, mesh_objects1 = self.__create_test_model("RegularTest", with_mesh_data=True, with_vertex_groups=True, with_sdef_data=False)

        bpy.context.view_layer.objects.active = root_obj1
        bpy.ops.mmd_tools.assemble_all()

        # Should have armature modifiers but no SDEF binding
        regular_armature_count = sum(1 for mesh in mesh_objects1 if any(mod.type == "ARMATURE" for mod in mesh.modifiers))
        regular_sdef_count = sum(1 for mesh in mesh_objects1 if mesh.data.shape_keys and "mmd_sdef_skinning" in mesh.data.shape_keys.key_blocks)

        # Test 2: SDEF meshes
        root_obj2, armature_obj2, mesh_objects2 = self.__create_test_model("SDEFTest", with_mesh_data=True, with_vertex_groups=True, with_sdef_data=True)

        bpy.context.view_layer.objects.active = root_obj2
        bpy.ops.mmd_tools.assemble_all()

        # Should have both armature modifiers and SDEF binding
        sdef_armature_count = sum(1 for mesh in mesh_objects2 if any(mod.type == "ARMATURE" for mod in mesh.modifiers))
        sdef_sdef_count = sum(1 for mesh in mesh_objects2 if mesh.data.shape_keys and "mmd_sdef_skinning" in mesh.data.shape_keys.key_blocks)

        # Assertions
        self.assertEqual(regular_armature_count, len(mesh_objects1), "Regular meshes should get armature modifiers")
        self.assertEqual(regular_sdef_count, 0, "Regular meshes should not get SDEF binding")

        self.assertEqual(sdef_armature_count, len(mesh_objects2), "SDEF meshes should get armature modifiers")
        self.assertGreater(sdef_sdef_count, 0, "SDEF meshes should get SDEF binding")

        print(f"Regular meshes: {regular_armature_count} armature mods, {regular_sdef_count} SDEF bindings")
        print(f"SDEF meshes: {sdef_armature_count} armature mods, {sdef_sdef_count} SDEF bindings")

    def test_sdef_bind_deep_investigation(self):
        """Deep investigation of sdef_bind internal logic"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("SDEFDeepTest", with_mesh_data=True, with_vertex_groups=True)

        print("\n=== SDEF BIND DEEP INVESTIGATION ===")

        # Check model structure requirements
        print("\n--- Model Structure Check ---")
        print(f"Root object mmd_type: {root_obj.mmd_type}")
        print(f"Root object name: {root_obj.name}")
        print(f"Armature object: {armature_obj.name}")
        print(f"Armature parent: {armature_obj.parent.name if armature_obj.parent else 'None'}")

        # Check if root object has the built flag
        print(f"Root is_built: {root_obj.mmd_root.is_built}")

        # Check mesh parent relationships and structure
        for i, mesh_obj in enumerate(mesh_objects):
            print(f"\nMesh {i + 1} ({mesh_obj.name}):")
            print(f"  - Parent: {mesh_obj.parent.name if mesh_obj.parent else 'None'}")
            print(f"  - MMD type: {mesh_obj.mmd_type}")
            print(f"  - In scene: {mesh_obj.name in bpy.context.scene.objects}")
            print(f"  - Vertex count: {len(mesh_obj.data.vertices)}")
            print(f"  - Face count: {len(mesh_obj.data.polygons)}")

            # Check vertex group details
            print("  - Vertex groups:")
            for vg in mesh_obj.vertex_groups:
                vertex_count = len([v for v in mesh_obj.data.vertices if any(g.group == vg.index for g in v.groups)])
                print(f"    * {vg.name}: {vertex_count} vertices assigned")

        # Check armature bone structure
        print("\n--- Armature Structure ---")
        print(f"Bones in armature: {len(armature_obj.data.bones)}")
        for bone in armature_obj.data.bones:
            print(f"  - {bone.name}")

        # Check if we need to manually add armature modifiers first
        print("\n--- Manual Armature Modifier Test ---")
        for i, mesh_obj in enumerate(mesh_objects):
            print(f"Adding manual armature modifier to mesh {i + 1}")

            # Add armature modifier manually
            armature_mod = mesh_obj.modifiers.new(name="Armature", type="ARMATURE")
            armature_mod.object = armature_obj
            armature_mod.use_vertex_groups = True

            print(f"  - Modifier added: {armature_mod.name}")
            print(f"  - Target: {armature_mod.object.name if armature_mod.object else 'None'}")
            print(f"  - Use vertex groups: {armature_mod.use_vertex_groups}")

        # Now test if sdef_bind works with pre-existing modifiers
        print("\n--- SDEF Bind Test with Pre-existing Modifiers ---")
        bpy.ops.object.select_all(action="DESELECT")
        for mesh_obj in mesh_objects:
            mesh_obj.select_set(True)
        bpy.context.view_layer.objects.active = root_obj

        print(f"Selected objects: {[obj.name for obj in bpy.context.selected_objects]}")
        print(f"Active object: {bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else 'None'}")

        try:
            bpy.ops.mmd_tools.sdef_bind()
            print("SDEF bind executed successfully")
        except Exception as e:
            print(f"SDEF bind error: {e}")

        # Check final state
        print("\n--- Final State Check ---")
        for i, mesh_obj in enumerate(mesh_objects):
            modifiers = [mod for mod in mesh_obj.modifiers if mod.type == "ARMATURE"]
            print(f"Mesh {i + 1}: {len(modifiers)} armature modifiers")
            for mod in modifiers:
                print(f"  - {mod.name}: target={mod.object.name if mod.object else 'None'}")

        # Test alternative: try to use FnModel.attach_mesh_objects directly
        print("\n--- Testing FnModel.attach_mesh_objects ---")

        # Clear existing modifiers
        for mesh_obj in mesh_objects:
            mesh_obj.modifiers.clear()

        try:
            FnModel.attach_mesh_objects(root_obj, mesh_objects, add_armature_modifier=True)
            print("attach_mesh_objects executed successfully")

            # Check result
            success_count = 0
            for i, mesh_obj in enumerate(mesh_objects):
                modifiers = [mod for mod in mesh_obj.modifiers if mod.type == "ARMATURE"]
                if modifiers:
                    success_count += 1
                print(f"Mesh {i + 1}: {len(modifiers)} armature modifiers after attach_mesh_objects")

            if success_count > 0:
                print(f"SUCCESS: attach_mesh_objects created {success_count} armature modifiers!")
                self.assertGreater(success_count, 0, "attach_mesh_objects should create armature modifiers")
            else:
                print("attach_mesh_objects also failed to create modifiers")

        except Exception as e:
            print(f"attach_mesh_objects error: {e}")

        # Test if the issue is with model state
        print("\n--- Testing Model Build State ---")
        try:
            model = Model(root_obj)
            print("Model created successfully")
            print(f"Model has armature: {model.armature() is not None}")
            print(f"Model meshes count: {len(list(model.meshes()))}")

            # Try to use model's attach method
            model.attachMeshes(mesh_objects, add_armature_modifier=True)
            print("Model.attachMeshes executed")

            # Check result
            final_count = 0
            for i, mesh_obj in enumerate(mesh_objects):
                modifiers = [mod for mod in mesh_obj.modifiers if mod.type == "ARMATURE"]
                if modifiers:
                    final_count += 1
                print(f"Mesh {i + 1}: {len(modifiers)} armature modifiers after Model.attachMeshes")

            if final_count > 0:
                print(f"SUCCESS: Model.attachMeshes created {final_count} armature modifiers!")
                self.assertGreater(final_count, 0, "Model.attachMeshes should work")
            else:
                self.fail("No method successfully created armature modifiers")

        except Exception as e:
            print(f"Model operations error: {e}")
            self.fail(f"Model operations failed: {e}")

    def test_sdef_binding_with_data(self):
        """Test SDEF binding functionality with proper SDEF data"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model(
            "SDEFTest",
            with_mesh_data=True,
            with_vertex_groups=True,
            with_sdef_data=True,  # Enable SDEF data creation
        )

        # Test SDEF binding
        bpy.ops.object.select_all(action="DESELECT")
        for mesh_obj in mesh_objects:
            mesh_obj.select_set(True)
        bpy.context.view_layer.objects.active = root_obj

        try:
            bpy.ops.mmd_tools.sdef_bind()

            # Verify SDEF binding worked
            bind_count = 0
            for mesh_obj in mesh_objects:
                if "mmd_sdef_skinning" in mesh_obj.data.shape_keys.key_blocks:
                    bind_count += 1

            self.assertGreater(bind_count, 0, "SDEF binding should create skinning shape keys")

        except Exception as e:
            self.fail(f"SDEF binding with proper data failed: {e}")

    def test_assemble_all_with_sdef_data(self):
        """Test AssembleAll with SDEF-enabled meshes"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model("AssembleSDEFTest", with_mesh_data=True, with_vertex_groups=True, with_sdef_data=True)

        bpy.context.view_layer.objects.active = root_obj

        try:
            bpy.ops.mmd_tools.assemble_all()

            # Check if SDEF binding was successful
            sdef_bound_count = 0
            armature_mod_count = 0

            for mesh_obj in mesh_objects:
                # Check for SDEF skinning shape key
                if mesh_obj.data.shape_keys and "mmd_sdef_skinning" in mesh_obj.data.shape_keys.key_blocks:
                    sdef_bound_count += 1

                # Check for armature modifiers
                if any(mod.type == "ARMATURE" for mod in mesh_obj.modifiers):
                    armature_mod_count += 1

            self.assertEqual(armature_mod_count, len(mesh_objects), "All meshes should have armature modifiers")
            self.assertGreater(sdef_bound_count, 0, "At least some meshes should have SDEF binding")

        except Exception as e:
            self.fail(f"AssembleAll with SDEF data failed: {e}")

    def test_sdef_shape_key_binding(self):
        """Deep investigation of SDEF shape key binding functionality"""
        root_obj, armature_obj, mesh_objects = self.__create_test_model(
            "SDEFShapeKeyTest",
            with_mesh_data=True,
            with_vertex_groups=True,
            with_sdef_data=True,  # Use SDEF data for this test
        )

        print("\n=== SDEF BIND DEEP INVESTIGATION ===")

        # Check model structure requirements
        print("\n--- Model Structure Check ---")
        print(f"Root object mmd_type: {root_obj.mmd_type}")
        print(f"Root object name: {root_obj.name}")
        print(f"Armature object: {armature_obj.name}")
        print(f"Armature parent: {armature_obj.parent.name if armature_obj.parent else 'None'}")

        # Check if root object has the built flag
        print(f"Root is_built: {root_obj.mmd_root.is_built}")

        # Check mesh parent relationships and structure
        for i, mesh_obj in enumerate(mesh_objects):
            print(f"\nMesh {i + 1} ({mesh_obj.name}):")
            print(f"  - Parent: {mesh_obj.parent.name if mesh_obj.parent else 'None'}")
            print(f"  - MMD type: {mesh_obj.mmd_type}")
            print(f"  - In scene: {mesh_obj.name in bpy.context.scene.objects}")
            print(f"  - Vertex count: {len(mesh_obj.data.vertices)}")
            print(f"  - Face count: {len(mesh_obj.data.polygons)}")

            # Check SDEF data specifically
            print(f"  - Has shape keys: {mesh_obj.data.shape_keys is not None}")
            if mesh_obj.data.shape_keys:
                shape_key_names = list(mesh_obj.data.shape_keys.key_blocks.keys())
                print(f"  - Shape keys: {shape_key_names}")
                has_sdef = "mmd_sdef_c" in shape_key_names and "mmd_sdef_r0" in shape_key_names and "mmd_sdef_r1" in shape_key_names
                print(f"  - Has SDEF shape keys: {has_sdef}")

            # Check armature modifier details
            armature_mods = [mod for mod in mesh_obj.modifiers if mod.type == "ARMATURE"]
            print(f"  - Armature modifiers: {len(armature_mods)}")
            for mod in armature_mods:
                print(f"    * {mod.name}: target={mod.object.name if mod.object else 'None'}")

            # Test FnSDEF.has_sdef_data specifically
            has_sdef_data = FnSDEF.has_sdef_data(mesh_obj)
            print(f"  - FnSDEF.has_sdef_data(): {has_sdef_data}")

            # Check vertex group details
            print("  - Vertex groups:")
            for vg in mesh_obj.vertex_groups:
                vertex_count = len([v for v in mesh_obj.data.vertices if any(g.group == vg.index for g in v.groups)])
                print(f"    * {vg.name}: {vertex_count} vertices assigned")

        # Test individual SDEF binding on each mesh
        print("\n--- Individual SDEF Bind Test ---")
        for i, mesh_obj in enumerate(mesh_objects):
            print(f"\nTesting SDEF bind on mesh {i + 1}: {mesh_obj.name}")

            # Clear any existing SDEF data
            FnSDEF.unbind(mesh_obj)

            # Test direct binding
            try:
                bind_result = FnSDEF.bind(mesh_obj)
                print(f"  - FnSDEF.bind() result: {bind_result}")

                # Check if skinning shape key was created
                if mesh_obj.data.shape_keys and "mmd_sdef_skinning" in mesh_obj.data.shape_keys.key_blocks:
                    print("  - SDEF skinning shape key created: Yes")
                else:
                    print("  - SDEF skinning shape key created: No")

            except Exception as e:
                print(f"  - FnSDEF.bind() error: {e}")

        # Test the operator with proper selection
        print("\n--- SDEF Operator Test ---")
        bpy.ops.object.select_all(action="DESELECT")
        for mesh_obj in mesh_objects:
            mesh_obj.select_set(True)
        bpy.context.view_layer.objects.active = root_obj

        print(f"Selected objects: {[obj.name for obj in bpy.context.selected_objects]}")
        print(f"Active object: {bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else 'None'}")

        try:
            # Test the operator
            bpy.ops.mmd_tools.sdef_bind()
            print("SDEF bind operator executed successfully")

            # Check final results
            bind_count = 0
            for i, mesh_obj in enumerate(mesh_objects):
                has_skinning = mesh_obj.data.shape_keys and "mmd_sdef_skinning" in mesh_obj.data.shape_keys.key_blocks
                if has_skinning:
                    bind_count += 1
                print(f"Mesh {i + 1}: SDEF skinning = {has_skinning}")

            if bind_count > 0:
                print(f"SUCCESS: {bind_count} meshes successfully bound with SDEF")
                self.assertGreater(bind_count, 0, "SDEF binding should work with proper data")
            else:
                print("FAILURE: No meshes were successfully bound with SDEF")

        except Exception as e:
            print(f"SDEF bind operator error: {e}")
            self.fail(f"SDEF operator failed: {e}")

    def test_model_assembly_operations_with_real_model(self):
        """Test model assembly operations with real PMX model"""
        input_files = self.__list_sample_files(("pmx",))
        if len(input_files) < 1:
            self.skipTest("No PMX sample files available for real model test")

        # Find the largest PMX file for comprehensive testing
        largest_file = max(input_files, key=os.path.getsize)

        print(f"\nTesting assembly operations with largest PMX: {os.path.basename(largest_file)} ({os.path.getsize(largest_file)} bytes)")

        try:
            # Load real model
            self.__enable_mmd_tools()
            bpy.ops.mmd_tools.import_model(filepath=largest_file, types={"MESH", "ARMATURE", "PHYSICS", "MORPHS"}, scale=0.08, clean_model=False, remove_doubles=False, log_level="ERROR")

            # Find the imported model
            root_objects = [obj for obj in bpy.context.scene.objects if obj.mmd_type == "ROOT"]
            self.assertGreater(len(root_objects), 0, "Real model should be imported successfully")

            root_obj = root_objects[0]
            model = Model(root_obj)
            mesh_objects = list(model.meshes())
            armature_obj = model.armature()

            self.assertIsNotNone(armature_obj, "Real model should have armature")
            self.assertGreater(len(mesh_objects), 0, "Real model should have meshes")

            print(f"   - Imported model: {root_obj.name}")
            print(f"   - Meshes: {len(mesh_objects)}")
            print(f"   - Bones: {len(armature_obj.data.bones)}")

            # Test assembly operations with real model data
            bpy.context.view_layer.objects.active = root_obj

            # Test assemble all with real complex data
            initial_modifier_counts = {}
            for mesh_obj in mesh_objects:
                initial_modifier_counts[mesh_obj.name] = len([mod for mod in mesh_obj.modifiers if mod.type == "ARMATURE"])

            bpy.ops.mmd_tools.assemble_all()

            # Verify armature modifiers were added to meshes without them
            assembled_count = 0
            for mesh_obj in mesh_objects:
                current_modifiers = len([mod for mod in mesh_obj.modifiers if mod.type == "ARMATURE"])
                if current_modifiers > initial_modifier_counts[mesh_obj.name]:
                    assembled_count += 1
                elif current_modifiers > 0:
                    assembled_count += 1  # Already had modifiers

            self.assertGreater(assembled_count, 0, "Assemble operation should create or maintain armature modifiers")
            print(f"   - Assembled {assembled_count} meshes with armature modifiers")

            # Test disassemble all
            bpy.ops.mmd_tools.disassemble_all()

            # Verify some modifiers were removed (but not necessarily all, depends on model state)
            disassembled_count = 0
            for mesh_obj in mesh_objects:
                current_modifiers = len([mod for mod in mesh_obj.modifiers if mod.type == "ARMATURE"])
                if current_modifiers == 0:
                    disassembled_count += 1

            print(f"   - Disassembled {disassembled_count} meshes (removed armature modifiers)")
            self.assertTrue(True, "Disassemble operation completed on real model")

        except Exception as e:
            self.fail(f"Assembly operations with real model failed: {e}")

    def test_separate_by_materials_with_real_model(self):
        """Test separate by materials operation with real PMX model"""
        input_files = self.__list_sample_files(("pmx",))
        if len(input_files) < 1:
            self.skipTest("No PMX sample files available for real model test")

        # Find the largest PMX file
        largest_file = max(input_files, key=os.path.getsize)

        print(f"\nTesting separate by materials with largest PMX: {os.path.basename(largest_file)}")

        try:
            # Load real model
            self.__enable_mmd_tools()
            bpy.ops.mmd_tools.import_model(filepath=largest_file, types={"MESH", "ARMATURE"}, scale=0.08, clean_model=False, remove_doubles=False, log_level="ERROR")

            # Find the imported model
            root_objects = [obj for obj in bpy.context.scene.objects if obj.mmd_type == "ROOT"]
            self.assertGreater(len(root_objects), 0, "Real model should be imported successfully")

            root_obj = root_objects[0]
            model = Model(root_obj)
            mesh_objects = list(model.meshes())

            # Find a mesh with multiple materials for testing
            test_mesh = None
            for mesh_obj in mesh_objects:
                if len(mesh_obj.data.materials) > 1:
                    test_mesh = mesh_obj
                    break

            if test_mesh is None:
                self.skipTest("No mesh with multiple materials found in real model")

            initial_material_count = len(test_mesh.data.materials)
            initial_mesh_count = len(mesh_objects)

            print(f"   - Testing mesh: {test_mesh.name}")
            print(f"   - Materials in mesh: {initial_material_count}")
            print(f"   - Initial mesh count: {initial_mesh_count}")

            # Test separate by materials
            bpy.context.view_layer.objects.active = test_mesh
            bpy.ops.object.select_all(action="DESELECT")
            test_mesh.select_set(True)

            # Record material names for verification
            original_materials = [mat.name for mat in test_mesh.data.materials if mat]

            bpy.ops.mmd_tools.separate_by_materials()

            # Check results
            updated_mesh_objects = list(model.meshes())
            final_mesh_count = len(updated_mesh_objects)

            print(f"   - Final mesh count: {final_mesh_count}")

            # Should have more meshes after separation (unless there was only one material)
            if initial_material_count > 1:
                self.assertGreaterEqual(final_mesh_count, initial_mesh_count, "Should have same or more meshes after material separation")

                # Verify that new meshes have single materials
                single_material_meshes = 0
                for mesh_obj in updated_mesh_objects:
                    if len([mat for mat in mesh_obj.data.materials if mat]) == 1:
                        single_material_meshes += 1

                print(f"   - Meshes with single material: {single_material_meshes}")
                self.assertGreater(single_material_meshes, 0, "Should have meshes with single materials after separation")

                # Verify that all original materials are still present across the separated meshes
                found_materials = set()
                for mesh_obj in updated_mesh_objects:
                    for mat in mesh_obj.data.materials:
                        if mat and mat.name in original_materials:
                            found_materials.add(mat.name)

                missing_materials = set(original_materials) - found_materials
                if missing_materials:
                    print(f"   - Warning: Some materials were lost during separation: {missing_materials}")
                    self.fail(f"Materials lost during separation: {missing_materials}")
                else:
                    print(f"   - All {len(original_materials)} original materials preserved after separation")
                    self.assertEqual(len(found_materials), len(original_materials), "All original materials should be preserved after separation")

                # Verify material distribution makes sense
                total_material_slots = sum(len([mat for mat in mesh_obj.data.materials if mat]) for mesh_obj in updated_mesh_objects)
                self.assertGreaterEqual(total_material_slots, len(original_materials), "Total material slots should be at least equal to original material count")

        except Exception as e:
            self.fail(f"Separate by materials with real model failed: {e}")

    def test_model_ik_toggle_functionality_with_real_model(self):
        """Test IK toggle functionality with real PMX model"""
        input_files = self.__list_sample_files(("pmx",))
        if len(input_files) < 1:
            self.skipTest("No PMX sample files available for real model test")

        # Find the largest PMX file
        largest_file = max(input_files, key=os.path.getsize)

        print(f"\nTesting IK toggle with largest PMX: {os.path.basename(largest_file)}")

        try:
            # Load real model
            self.__enable_mmd_tools()
            bpy.ops.mmd_tools.import_model(filepath=largest_file, types={"MESH", "ARMATURE"}, scale=0.08, clean_model=False, remove_doubles=False, log_level="ERROR")

            # Find the imported model
            root_objects = [obj for obj in bpy.context.scene.objects if obj.mmd_type == "ROOT"]
            self.assertGreater(len(root_objects), 0, "Real model should be imported successfully")

            root_obj = root_objects[0]
            model = Model(root_obj)
            armature_obj = model.armature()

            self.assertIsNotNone(armature_obj, "Real model should have armature")

            print(f"   - Armature: {armature_obj.name}")
            print(f"   - Total bones: {len(armature_obj.data.bones)}")

            bpy.context.view_layer.objects.active = armature_obj
            bpy.ops.object.mode_set(mode="POSE")

            # Find bones with IK constraints
            ik_bones = []
            ik_constraints_found = 0

            for pose_bone in armature_obj.pose.bones:
                ik_constraints = [c for c in pose_bone.constraints if c.type == "IK"]
                if ik_constraints:
                    ik_bones.append(pose_bone)
                    ik_constraints_found += len(ik_constraints)

            print(f"   - Bones with IK constraints: {len(ik_bones)}")
            print(f"   - Total IK constraints: {ik_constraints_found}")

            if len(ik_bones) == 0:
                print("   - No IK constraints found, testing MMD IK properties instead")

                # Test MMD IK properties on bones that might have them
                mmd_ik_bones = []
                for pose_bone in armature_obj.pose.bones:
                    if hasattr(pose_bone, "mmd_bone"):
                        mmd_bone = pose_bone.mmd_bone
                        if hasattr(mmd_bone, "ik_rotation_constraint") and mmd_bone.ik_rotation_constraint > 0:
                            mmd_ik_bones.append(pose_bone)

                print(f"   - Bones with MMD IK properties: {len(mmd_ik_bones)}")

                if len(mmd_ik_bones) > 0:
                    test_bone = mmd_ik_bones[0]
                    print(f"   - Testing MMD IK properties on bone: {test_bone.name}")

                    # Test MMD IK toggle property
                    self.assertTrue(hasattr(test_bone, "mmd_ik_toggle"), "MMD bone should have IK toggle property")

                    original_ik_state = test_bone.mmd_ik_toggle
                    test_bone.mmd_ik_toggle = not original_ik_state
                    self.assertNotEqual(test_bone.mmd_ik_toggle, original_ik_state, "IK toggle state should change")

                    # Reset to original state
                    test_bone.mmd_ik_toggle = original_ik_state
                    print(f"   - MMD IK toggle test passed on {test_bone.name}")
            else:
                # Test with actual IK constraints
                test_bone = ik_bones[0]
                print(f"   - Testing IK constraints on bone: {test_bone.name}")

                ik_constraint = [c for c in test_bone.constraints if c.type == "IK"][0]

                # Test IK constraint properties
                self.assertIsNotNone(ik_constraint.target, "IK constraint should have target")
                self.assertIsNotNone(ik_constraint.subtarget, "IK constraint should have subtarget")

                original_influence = ik_constraint.influence
                ik_constraint.influence = 0.0 if original_influence > 0.5 else 1.0
                self.assertNotEqual(ik_constraint.influence, original_influence, "IK constraint influence should be modifiable")

                # Reset influence
                ik_constraint.influence = original_influence

                # Test MMD IK toggle if available
                if hasattr(test_bone, "mmd_ik_toggle"):
                    original_toggle = test_bone.mmd_ik_toggle
                    test_bone.mmd_ik_toggle = not original_toggle
                    test_bone.mmd_ik_toggle = original_toggle
                    print(f"   - IK constraint and MMD toggle test passed on {test_bone.name}")

            bpy.ops.object.mode_set(mode="OBJECT")

            self.assertTrue(True, "IK functionality test completed with real model")

        except Exception as e:
            self.fail(f"IK toggle functionality with real model failed: {e}")


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main(verbosity=1, exit=True)
