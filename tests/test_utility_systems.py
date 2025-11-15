# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bpy
from bl_ext.blender_org.mmd_tools import auto_load, bpyutils, cycles_converter, handlers
from bl_ext.blender_org.mmd_tools.core.exceptions import MaterialNotFoundError


class TestUtilitySystems(unittest.TestCase):
    """
    Test suite for utility systems and helper functions including:
    - bpyutils.py: Blender utility functions and context management
    - cycles_converter.py: Material/shader conversion utilities
    - handlers.py: Blender event handlers
    - auto_load.py: Module auto-loading system
    - exceptions.py: Custom exception classes
    """

    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        # Enable MMD Tools addon
        cls.__enable_mmd_tools()
        # Enable Cycles rendering engine
        cls.__enable_cycles()

    def setUp(self):
        """Set up testing environment"""
        logger = logging.getLogger()
        logger.setLevel("ERROR")
        # Start with clean scene
        bpy.ops.wm.read_homefile(use_empty=True)

    @classmethod
    def __enable_mmd_tools(cls):
        """Enable MMD Tools addon"""
        bpy.ops.wm.read_homefile(use_empty=True)
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.blender_org.mmd_tools")

    @classmethod
    def __enable_cycles(cls):
        """Enable Cycles rendering engine"""
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("cycles", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="cycles")

    # ********************************************
    # Exception Tests
    # ********************************************

    def test_material_not_found_error(self):
        """Test MaterialNotFoundError exception class"""
        # Test basic instantiation
        error = MaterialNotFoundError()
        self.assertIsInstance(error, KeyError)
        self.assertIsInstance(error, MaterialNotFoundError)

        # Test with message
        message = "Test material not found"
        error_with_msg = MaterialNotFoundError(message)
        self.assertEqual(str(error_with_msg), f"'{message}'")

        # Test with multiple arguments
        error_multi = MaterialNotFoundError("arg1", "arg2", 123)
        self.assertIn("arg1", str(error_multi))

        # Test exception raising
        with self.assertRaises(MaterialNotFoundError):
            raise MaterialNotFoundError("Test material not found")

    # ********************************************
    # Auto Load Tests
    # ********************************************

    def test_auto_load_module_discovery(self):
        """Test auto_load module discovery functions"""
        # Test iter_submodule_names with a mock directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create mock module files
            (temp_path / "module1.py").touch()
            (temp_path / "module2.py").touch()
            (temp_path / "subdir").mkdir()
            (temp_path / "subdir" / "__init__.py").touch()
            (temp_path / "subdir" / "submodule.py").touch()

            # Test iter_submodule_names
            names = list(auto_load.iter_submodule_names(temp_path))

            # Verify expected modules are found
            self.assertIn("module1", names)
            self.assertIn("module2", names)
            self.assertIn("subdir.submodule", names)

            # Verify names are sorted
            self.assertEqual(names, sorted(names))

    def test_auto_load_class_registration_detection(self):
        """Test auto_load class registration detection"""

        # Create mock classes that should be registered
        class MockPanel:
            """Mock Blender panel class"""

            bl_idname = "TEST_PT_mock"
            is_registered = False

        class MockOperator:
            """Mock Blender operator class"""

            bl_idname = "test.mock_operator"
            is_registered = False

        class MockPropertyGroup:
            """Mock Blender property group class"""

            pass

        # Mock the base types
        mock_panel_base = type("Panel", (), {})
        mock_operator_base = type("Operator", (), {})
        mock_prop_group_base = type("PropertyGroup", (), {})

        # Create test classes with proper inheritance
        test_panel = type("TestPanel", (mock_panel_base,), {"bl_idname": "TEST_PT_mock", "is_registered": False})
        test_operator = type("TestOperator", (mock_operator_base,), {"bl_idname": "test.mock_operator", "is_registered": False})
        test_prop_group = type("TestPropGroup", (mock_prop_group_base,), {})

        # Mock module with these classes
        mock_module = type(
            "MockModule",
            (),
            {
                "__dict__": {
                    "TestPanel": test_panel,
                    "TestOperator": test_operator,
                    "TestPropGroup": test_prop_group,
                    "NotAClass": "string value",
                    "MockPanel": MockPanel,
                },
            },
        )()

        # Test iter_classes_in_module
        classes = list(auto_load.iter_classes_in_module(mock_module))

        # Verify classes are detected
        class_names = [cls.__name__ for cls in classes]
        self.assertIn("TestPanel", class_names)
        self.assertIn("TestOperator", class_names)
        self.assertIn("TestPropGroup", class_names)
        self.assertIn("MockPanel", class_names)
        self.assertNotIn("NotAClass", class_names)

    def test_auto_load_topological_sort(self):
        """Test topological sorting for dependency resolution"""
        # Create dependency graph: A -> B -> C, D -> B
        deps_dict = {"A": set(), "B": {"A"}, "C": {"B"}, "D": set(), "E": {"B", "D"}}

        sorted_list = auto_load.toposort(deps_dict)

        # Verify all items are included
        self.assertEqual(set(sorted_list), {"A", "B", "C", "D", "E"})

        # Verify dependencies are respected
        a_idx = sorted_list.index("A")
        b_idx = sorted_list.index("B")
        c_idx = sorted_list.index("C")
        d_idx = sorted_list.index("D")
        e_idx = sorted_list.index("E")

        self.assertLess(a_idx, b_idx)  # A before B
        self.assertLess(b_idx, c_idx)  # B before C
        self.assertLess(d_idx, e_idx)  # D before E
        self.assertLess(b_idx, e_idx)  # B before E

    # ********************************************
    # BPY Utils Tests
    # ********************************************

    def test_bpyutils_props_constants(self):
        """Test bpyutils Props class constants"""
        # Verify all expected properties exist
        self.assertEqual(bpyutils.Props.show_in_front, "show_in_front")
        self.assertEqual(bpyutils.Props.display_type, "display_type")
        self.assertEqual(bpyutils.Props.display_size, "display_size")
        self.assertEqual(bpyutils.Props.empty_display_type, "empty_display_type")
        self.assertEqual(bpyutils.Props.empty_display_size, "empty_display_size")

    def test_bpyutils_create_object(self):
        """Test object creation utilities"""
        # Test basic object creation
        obj = bpyutils.createObject(name="TestObject")
        self.assertIsNotNone(obj)
        self.assertEqual(obj.name, "TestObject")
        self.assertIsNone(obj.data)

        # Test object creation with mesh data
        mesh_data = bpy.data.meshes.new("TestMesh")
        mesh_obj = bpyutils.createObject(name="TestMeshObject", object_data=mesh_data)
        self.assertIsNotNone(mesh_obj)
        self.assertEqual(mesh_obj.data, mesh_data)

        # Verify objects are in scene
        self.assertIn(obj.name, bpy.context.scene.objects)
        self.assertIn(mesh_obj.name, bpy.context.scene.objects)

    def test_bpyutils_make_sphere(self):
        """Test sphere creation utility"""
        # Test default sphere
        sphere = bpyutils.makeSphere()
        self.assertIsNotNone(sphere)
        self.assertEqual(sphere.type, "MESH")
        self.assertIsInstance(sphere.data, bpy.types.Mesh)

        # Test sphere with custom parameters
        custom_sphere = bpyutils.makeSphere(segment=16, ring_count=10, radius=2.0)
        self.assertIsNotNone(custom_sphere)
        self.assertEqual(custom_sphere.type, "MESH")

        # Test sphere with target object
        target_obj = bpyutils.createObject(name="TargetSphere", object_data=bpy.data.meshes.new("TargetMesh"))
        result_sphere = bpyutils.makeSphere(target_object=target_obj)
        self.assertEqual(result_sphere, target_obj)
        self.assertGreater(len(target_obj.data.vertices), 0)

    def test_bpyutils_make_box(self):
        """Test box creation utility"""
        # Test default box
        box = bpyutils.makeBox()
        self.assertIsNotNone(box)
        self.assertEqual(box.type, "MESH")
        self.assertIsInstance(box.data, bpy.types.Mesh)

        # Test box with custom size
        custom_box = bpyutils.makeBox(size=(2, 3, 4))
        self.assertIsNotNone(custom_box)
        self.assertEqual(custom_box.type, "MESH")

        # Test box with target object
        target_obj = bpyutils.createObject(name="TargetBox", object_data=bpy.data.meshes.new("TargetMesh"))
        result_box = bpyutils.makeBox(target_object=target_obj)
        self.assertEqual(result_box, target_obj)
        self.assertGreater(len(target_obj.data.vertices), 0)

    def test_bpyutils_make_capsule(self):
        """Test capsule creation utility"""
        # Test default capsule
        capsule = bpyutils.makeCapsule()
        self.assertIsNotNone(capsule)
        self.assertEqual(capsule.type, "MESH")
        self.assertIsInstance(capsule.data, bpy.types.Mesh)

        # Test capsule with custom parameters
        custom_capsule = bpyutils.makeCapsule(segment=12, ring_count=3, radius=1.5, height=2.0)
        self.assertIsNotNone(custom_capsule)
        self.assertEqual(custom_capsule.type, "MESH")

        # Test capsule with minimum height
        min_capsule = bpyutils.makeCapsule(height=0.0001)
        self.assertIsNotNone(min_capsule)
        self.assertEqual(min_capsule.type, "MESH")

        # Test capsule with target object
        target_obj = bpyutils.createObject(name="TargetCapsule", object_data=bpy.data.meshes.new("TargetMesh"))
        result_capsule = bpyutils.makeCapsule(target_object=target_obj)
        self.assertEqual(result_capsule, target_obj)
        self.assertGreater(len(target_obj.data.vertices), 0)

    def test_bpyutils_select_object_context_manager(self):
        """Test select_object context manager"""
        # Create test objects
        obj1 = bpyutils.createObject(name="TestObj1")
        obj2 = bpyutils.createObject(name="TestObj2")
        obj3 = bpyutils.createObject(name="TestObj3")

        # Test single object selection
        with bpyutils.select_object(obj1) as active_obj:
            self.assertEqual(active_obj, obj1)
            self.assertTrue(obj1.select_get())
            self.assertEqual(bpy.context.active_object, obj1)

        # Test multiple object selection
        with bpyutils.select_object(obj2, objects=[obj1, obj2, obj3]) as active_obj:
            self.assertEqual(active_obj, obj2)
            self.assertTrue(obj1.select_get())
            self.assertTrue(obj2.select_get())
            self.assertTrue(obj3.select_get())
            self.assertEqual(bpy.context.active_object, obj2)

        # Test context restoration after exiting
        # Selection state should be restored
        # Note: exact restoration depends on initial state

    def test_bpyutils_edit_object_context_manager(self):
        """Test edit_object context manager"""
        # Create mesh object
        mesh_data = bpy.data.meshes.new("TestMesh")
        mesh_obj = bpyutils.createObject(name="TestMeshObj", object_data=mesh_data)

        # Test edit mode context
        with bpyutils.edit_object(mesh_obj) as edit_data:
            self.assertEqual(edit_data, mesh_obj.data)
            # In edit mode, we should be able to access edit_bones for armatures
            # or modify mesh data for meshes

        # Should return to object mode after exiting context
        self.assertEqual(mesh_obj.mode, "OBJECT")

    def test_bpyutils_transform_constraint_op(self):
        """Test TransformConstraintOp utility class"""
        # Create test object with bone
        armature_data = bpy.data.armatures.new("TestArmature")
        armature_obj = bpyutils.createObject(name="TestArmature", object_data=armature_data)

        # Add bone in edit mode
        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode="EDIT")

        bone = armature_data.edit_bones.new("TestBone")
        bone.head = (0, 0, 0)
        bone.tail = (0, 1, 0)

        bpy.ops.object.mode_set(mode="POSE")

        pose_bone = armature_obj.pose.bones["TestBone"]

        # Test constraint creation
        constraint = bpyutils.TransformConstraintOp.create(pose_bone.constraints, "test_transform", "ROTATION")

        self.assertIsNotNone(constraint)
        self.assertEqual(constraint.name, "test_transform")
        self.assertEqual(constraint.type, "TRANSFORM")
        self.assertEqual(constraint.map_from, "ROTATION")
        self.assertEqual(constraint.map_to, "ROTATION")

        # Test min/max attribute handling
        attrs = bpyutils.TransformConstraintOp.min_max_attributes("ROTATION")
        self.assertIsInstance(attrs, tuple)
        self.assertGreater(len(attrs), 0)

        # Test update min/max
        bpyutils.TransformConstraintOp.update_min_max(constraint, 1.5, 0.8)
        # Verify constraint was updated (specific values depend on implementation)

        bpy.ops.object.mode_set(mode="OBJECT")

    def test_bpyutils_fn_object_utilities(self):
        """Test FnObject utility functions"""
        # Create mesh with shape keys for testing
        mesh_data = bpy.data.meshes.new("TestMesh")
        mesh_obj = bpyutils.createObject(name="TestMeshObj", object_data=mesh_data)

        # Add some vertices to mesh
        bpy.context.view_layer.objects.active = mesh_obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.primitive_cube_add()
        bpy.ops.object.mode_set(mode="OBJECT")

        # Add shape key
        mesh_obj.shape_key_add(name="Basis")
        shape_key = mesh_obj.shape_key_add(name="TestKey")

        # Test shape key removal
        initial_key_count = len(mesh_obj.data.shape_keys.key_blocks)
        bpyutils.FnObject.mesh_remove_shape_key(mesh_obj, shape_key)
        final_key_count = len(mesh_obj.data.shape_keys.key_blocks)

        self.assertEqual(final_key_count, initial_key_count - 1)

    def test_bpyutils_fn_context_utilities(self):
        """Test FnContext utility functions"""
        context = bpy.context

        # Test ensure_context
        ensured_context = bpyutils.FnContext.ensure_context()
        self.assertIsNotNone(ensured_context)

        ensured_with_param = bpyutils.FnContext.ensure_context(context)
        self.assertEqual(ensured_with_param, context)

        # Test object creation and linking
        test_obj = bpyutils.FnContext.new_and_link_object(context, "TestObject", None)
        self.assertIsNotNone(test_obj)
        self.assertEqual(test_obj.name, "TestObject")
        self.assertIn(test_obj.name, context.collection.objects)

        # Test active object management
        bpyutils.FnContext.set_active_object(context, test_obj)
        self.assertEqual(bpy.context.active_object, test_obj)

        active_obj = bpyutils.FnContext.get_active_object(context)
        self.assertEqual(active_obj, test_obj)

        # Test object selection
        selected_obj = bpyutils.FnContext.select_object(context, test_obj)
        self.assertEqual(selected_obj, test_obj)
        self.assertTrue(test_obj.select_get())

        # Test single object selection
        bpyutils.FnContext.select_single_object(context, test_obj)
        self.assertTrue(test_obj.select_get())

    def test_bpyutils_duplicate_object(self):
        """Test object duplication utility"""
        # Create test object
        original_obj = bpyutils.createObject(name="OriginalObject")

        # Test duplication
        duplicated_objects = bpyutils.duplicateObject(original_obj, 3)

        self.assertEqual(len(duplicated_objects), 3)
        self.assertIn(original_obj, duplicated_objects)

        # Verify all objects exist in scene
        for obj in duplicated_objects:
            self.assertIn(obj.name, bpy.context.scene.objects)

    # ********************************************
    # Cycles Converter Tests
    # ********************************************

    def test_cycles_converter_shader_creation(self):
        """Test shader node group creation"""
        # Test MMDAlphaShader creation
        alpha_shader = cycles_converter.create_MMDAlphaShader()
        self.assertIsNotNone(alpha_shader)
        self.assertEqual(alpha_shader.name, "MMDAlphaShader")
        self.assertEqual(alpha_shader.type, "SHADER")

        # Verify it's reusable (returns existing if called again)
        alpha_shader2 = cycles_converter.create_MMDAlphaShader()
        self.assertEqual(alpha_shader, alpha_shader2)

        # Test MMDBasicShader creation
        basic_shader = cycles_converter.create_MMDBasicShader()
        self.assertIsNotNone(basic_shader)
        self.assertEqual(basic_shader.name, "MMDBasicShader")
        self.assertEqual(basic_shader.type, "SHADER")

        # Verify it's reusable
        basic_shader2 = cycles_converter.create_MMDBasicShader()
        self.assertEqual(basic_shader, basic_shader2)

    def test_cycles_converter_material_conversion(self):
        """Test material conversion functions"""
        # Create test object with materials
        mesh_data = bpy.data.meshes.new("TestMesh")
        test_obj = bpyutils.createObject(name="TestObject", object_data=mesh_data)

        # Add material
        material = bpy.data.materials.new("TestMaterial")
        test_obj.data.materials.append(material)

        # Test conversion to Cycles shader
        cycles_converter.convertToCyclesShader(test_obj)

        # Verify material uses nodes
        self.assertTrue(material.use_nodes)

        # Test conversion to Blender shader
        cycles_converter.convertToBlenderShader(test_obj)
        self.assertTrue(material.use_nodes)

        # Test conversion with principled BSDF
        cycles_converter.convertToBlenderShader(test_obj, use_principled=True)
        self.assertTrue(material.use_nodes)

        # Test conversion to MMD shader
        cycles_converter.convertToMMDShader(test_obj)
        self.assertTrue(material.use_nodes)

    # ********************************************
    # Handlers Tests
    # ********************************************

    def test_handlers_registration(self):
        """Test handlers registration and unregistration"""
        # Clean up any existing handlers first
        handlers.MMDHanders.unregister()

        # Test registration
        handlers.MMDHanders.register()

        # Verify handlers are registered
        self.assertIn(handlers.MMDHanders.load_hander, bpy.app.handlers.load_post)
        self.assertIn(handlers.MMDHanders.save_pre_handler, bpy.app.handlers.save_pre)

        # Test unregistration
        handlers.MMDHanders.unregister()

        # Verify handlers are unregistered
        self.assertNotIn(handlers.MMDHanders.load_hander, bpy.app.handlers.load_post)
        self.assertNotIn(handlers.MMDHanders.save_pre_handler, bpy.app.handlers.save_pre)

        # Restore
        handlers.MMDHanders.register()

    @patch("bl_ext.blender_org.mmd_tools.core.sdef.FnSDEF")
    @patch("bl_ext.blender_org.mmd_tools.core.material.MigrationFnMaterial")
    @patch("bl_ext.blender_org.mmd_tools.core.morph.MigrationFnMorph")
    @patch("bl_ext.blender_org.mmd_tools.core.camera.MigrationFnCamera")
    @patch("bl_ext.blender_org.mmd_tools.core.model.MigrationFnModel")
    def test_handlers_load_handler(self, mock_model, mock_camera, mock_morph, mock_material, mock_sdef):
        """Test load handler functionality"""
        # Call load handler
        handlers.MMDHanders.load_hander(None)

        # Verify all migration functions are called
        mock_sdef.clear_cache.assert_called_once()
        mock_sdef.register_driver_function.assert_called_once()
        mock_material.update_mmd_shader.assert_called_once()
        mock_morph.update_mmd_morph.assert_called_once()
        mock_camera.update_mmd_camera.assert_called_once()
        mock_model.update_mmd_ik_loop_factor.assert_called_once()
        mock_model.update_mmd_tools_version.assert_called_once()

    @patch("bl_ext.blender_org.mmd_tools.core.morph.MigrationFnMorph")
    def test_handlers_save_pre_handler(self, mock_morph):
        """Test save pre handler functionality"""
        # Call save pre handler
        handlers.MMDHanders.save_pre_handler(None)

        # Verify migration function is called
        mock_morph.compatible_with_old_version_mmd_tools.assert_called_once()

    # ********************************************
    # Integration Tests
    # ********************************************

    def test_utility_systems_integration(self):
        """Test integration between utility systems"""
        # Clean up any existing handlers first
        handlers.MMDHanders.unregister()

        # Test auto_load integration with handlers
        # This simulates addon loading process
        try:
            # Test that handlers can be registered without conflicts
            handlers.MMDHanders.register()

            # Verify handlers are properly registered
            self.assertIn(handlers.MMDHanders.load_hander, bpy.app.handlers.load_post)
            self.assertIn(handlers.MMDHanders.save_pre_handler, bpy.app.handlers.save_pre)

            # Test object creation and cycles conversion integration
            test_obj = bpyutils.createObject(name="IntegrationTestObj", object_data=bpy.data.meshes.new("IntegrationMesh"))

            # Validate created object parameters
            self.assertIsNotNone(test_obj)
            self.assertEqual(test_obj.name, "IntegrationTestObj")
            self.assertIsNotNone(test_obj.data)
            self.assertEqual(test_obj.data.name, "IntegrationMesh")
            self.assertEqual(test_obj.type, "MESH")

            # Add material for conversion test
            material = bpy.data.materials.new("IntegrationMaterial")
            test_obj.data.materials.append(material)

            # Validate material parameters
            self.assertIsNotNone(material)
            self.assertEqual(material.name, "IntegrationMaterial")
            self.assertEqual(len(test_obj.data.materials), 1)
            self.assertEqual(test_obj.data.materials[0], material)

            # Test cycles conversion with parameter validation
            initial_node_state = material.use_nodes
            cycles_converter.convertToBlenderShader(test_obj)

            # Verify integration worked and validate results
            self.assertTrue(material.use_nodes)
            # Validate that the conversion actually changed the node state if it was initially False
            if not initial_node_state:
                self.assertTrue(material.use_nodes)  # Should now be True after conversion
            self.assertIsNotNone(test_obj)

            # Verify integration worked and validate results
            self.assertTrue(material.use_nodes)
            self.assertIsNotNone(test_obj)

            # Test auto_load module functions integration
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Create test module structure
                (temp_path / "test_module.py").touch()
                test_modules = list(auto_load.iter_submodule_names(temp_path))

                # Validate auto_load results
                self.assertIsInstance(test_modules, list)
                self.assertIn("test_module", test_modules)

                # Test topological sort with integration data
                test_deps = {"A": set(), "B": {"A"}}
                sorted_result = auto_load.toposort(test_deps)

                # Validate topological sort results
                self.assertIsInstance(sorted_result, list)
                self.assertEqual(len(sorted_result), 2)
                self.assertEqual(sorted_result, ["A", "B"])

        finally:
            # Clean up handlers
            try:
                handlers.MMDHanders.unregister()

                # Verify handlers are properly unregistered
                self.assertNotIn(handlers.MMDHanders.load_hander, bpy.app.handlers.load_post)
                self.assertNotIn(handlers.MMDHanders.save_pre_handler, bpy.app.handlers.save_pre)
            except ValueError:
                # Handler might not be in list if already removed
                pass

            # Restore
            handlers.MMDHanders.register()

    def test_error_handling_and_edge_cases(self):
        """Test error handling and edge cases across utility systems"""
        # Test exception handling with parameter validation
        test_error_message = "Test error message"
        try:
            raise MaterialNotFoundError(test_error_message)
        except MaterialNotFoundError as caught_exception:
            # Validate exception parameters
            self.assertIsInstance(caught_exception, MaterialNotFoundError)
            self.assertIsInstance(caught_exception, KeyError)
            self.assertIn(test_error_message, str(caught_exception))

            # Test exception with multiple parameters
            multi_arg_error = MaterialNotFoundError("arg1", "arg2", 123)
            self.assertIn("arg1", str(multi_arg_error))

        # Test bpyutils with invalid objects and parameter validation
        invalid_inputs = ["not_an_object", None, 123, []]

        for invalid_input in invalid_inputs:
            with self.assertRaises(ValueError) as context_manager:
                with bpyutils.edit_object(invalid_input):
                    pass

            # Validate exception was raised correctly
            self.assertIsInstance(context_manager.exception, ValueError)

        # Test cycles converter with object without materials
        empty_obj = bpyutils.createObject(name="EmptyTestObj")

        # Validate empty object parameters - Empty objects have no data
        self.assertIsNotNone(empty_obj)
        self.assertEqual(empty_obj.name, "EmptyTestObj")
        self.assertIsNone(empty_obj.data)  # Empty objects have no data block

        # Should not raise exception with empty objects (no materials to convert)
        try:
            cycles_converter.convertToBlenderShader(empty_obj)
            cycles_converter.convertToCyclesShader(empty_obj)
            cycles_converter.convertToMMDShader(empty_obj)
        except Exception as conversion_error:
            self.fail(f"Conversion should handle empty objects gracefully: {conversion_error}")

        # Test FnContext with None parameters and validate handling
        context_none = bpyutils.FnContext.ensure_context(None)
        self.assertIsNotNone(context_none)
        self.assertEqual(context_none, bpy.context)

        active_obj_none = bpyutils.FnContext.get_active_object(None)
        # Should handle None gracefully
        self.assertIsNone(active_obj_none)

        # Test scene objects with None context
        scene_objects_none = bpyutils.FnContext.get_scene_objects(None)
        self.assertEqual(scene_objects_none, [])

        # Test auto_load edge cases with parameter validation
        empty_deps = {}
        empty_sort_result = auto_load.toposort(empty_deps)
        self.assertIsInstance(empty_sort_result, list)
        self.assertEqual(len(empty_sort_result), 0)

        # Test circular dependency detection
        circular_deps = {"A": {"B"}, "B": {"A"}}
        with self.assertRaises((ValueError, RuntimeError)) as context:
            auto_load.toposort(circular_deps)
        self.assertIn("Circular dependency", str(context.exception))

        # Test bpyutils geometry creation with edge case parameters
        edge_case_tests = [
            {"func": bpyutils.makeSphere, "params": {"segment": 3, "ring_count": 2, "radius": 0.001}},
            {"func": bpyutils.makeBox, "params": {"size": (0.001, 0.001, 0.001)}},
            {"func": bpyutils.makeCapsule, "params": {"height": 0.0, "radius": 0.001}},
        ]

        for test_case in edge_case_tests:
            func = test_case["func"]
            params = test_case["params"]

            try:
                result_obj = func(**params)

                # Validate edge case results
                self.assertIsNotNone(result_obj)
                self.assertEqual(result_obj.type, "MESH")
                self.assertIsInstance(result_obj.data, bpy.types.Mesh)

            except Exception as edge_error:
                self.fail(f"Edge case test failed for {func.__name__} with params {params}: {edge_error}")

        # Test TransformConstraintOp edge cases
        test_obj_armature = bpyutils.createObject(name="TestArmature", object_data=bpy.data.armatures.new("TestArmatureData"))

        # Validate armature object
        self.assertIsNotNone(test_obj_armature)
        self.assertEqual(test_obj_armature.type, "ARMATURE")

        bpy.context.view_layer.objects.active = test_obj_armature
        bpy.ops.object.mode_set(mode="EDIT")

        bone = test_obj_armature.data.edit_bones.new("TestBone")
        bone.head = (0, 0, 0)
        bone.tail = (0, 1, 0)

        # Validate bone parameters
        self.assertIsNotNone(bone)
        self.assertEqual(bone.name, "TestBone")

        bpy.ops.object.mode_set(mode="POSE")

        pose_bone = test_obj_armature.pose.bones["TestBone"]

        # Test constraint operations with edge case parameters
        constraint_tests = [
            {"map_type": "ROTATION", "name": "test_rot"},
            {"map_type": "SCALE", "name": "test_scale"},
        ]

        for constraint_test in constraint_tests:
            constraint = bpyutils.TransformConstraintOp.create(pose_bone.constraints, constraint_test["name"], constraint_test["map_type"])

            # Validate constraint parameters
            self.assertIsNotNone(constraint)
            self.assertEqual(constraint.name, constraint_test["name"])
            self.assertEqual(constraint.map_from, constraint_test["map_type"])

            # Test min/max updates with edge values
            bpyutils.TransformConstraintOp.update_min_max(constraint, 0.0, 1.0)
            bpyutils.TransformConstraintOp.update_min_max(constraint, 999.0, None)

        bpy.ops.object.mode_set(mode="OBJECT")


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main(verbosity=1, exit=True)
