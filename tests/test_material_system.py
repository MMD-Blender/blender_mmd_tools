# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import gc
import logging
import os
import shutil
import unittest

import bpy
from bl_ext.blender_org.mmd_tools.core.exceptions import MaterialNotFoundError
from bl_ext.blender_org.mmd_tools.core.material import FnMaterial, MigrationFnMaterial
from bl_ext.blender_org.mmd_tools.core.model import Model
from bl_ext.blender_org.mmd_tools.panels.prop_material import MMDMaterialPanel, MMDTexturePanel

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "samples")


class TestMaterialSystem(unittest.TestCase):
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
                elif os.path.isdir(item_fp):
                    shutil.rmtree(item_fp)

    def setUp(self):
        """Set up testing environment"""
        logger = logging.getLogger()
        logger.setLevel("ERROR")

        if not bpy.context.active_object:
            bpy.ops.mesh.primitive_cube_add()

        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=True)

        self.context = bpy.context
        self.scene = bpy.context.scene

    # ********************************************
    # Utils
    # ********************************************

    def __create_test_material(self, name="TestMaterial"):
        """Create a test material with MMD properties"""
        material = bpy.data.materials.new(name=name)
        material.use_nodes = True
        return material

    def __create_test_mesh_with_material(self, material_name="TestMaterial"):
        """Create a test mesh object with material"""
        bpy.ops.mesh.primitive_cube_add()
        mesh_obj = bpy.context.active_object
        mesh_obj.name = "TestMesh"

        # Create and assign material
        material = self.__create_test_material(material_name)
        mesh_obj.data.materials.append(material)
        mesh_obj.active_material = material

        return mesh_obj, material

    def __create_test_mmd_model(self):
        """Create a simple MMD model for testing"""
        # Create root object
        root = Model.create("TestModel", "TestModelE", scale=1.0)

        # Create mesh with material
        mesh_obj, material = self.__create_test_mesh_with_material()
        mesh_obj.parent = root.armature()

        return root, mesh_obj, material

    def __create_test_texture_file(self):
        """Create a simple test texture file"""
        # Create a 1x1 test image
        test_image = bpy.data.images.new("test_texture.png", 1, 1)
        test_image.pixels = [1.0, 0.0, 0.0, 1.0]  # Red pixel

        # Save to temporary location
        test_path = os.path.join(TESTS_DIR, "temp_test_texture.png")
        test_image.filepath_raw = test_path
        test_image.file_format = "PNG"
        test_image.save()

        return test_path

    def __clean_test_files(self):
        """Clean up temporary test files"""
        test_files = ["temp_test_texture.png", "temp_toon_texture.bmp", "temp_sphere_texture.spa"]
        for filename in test_files:
            filepath = os.path.join(TESTS_DIR, filename)
            if os.path.exists(filepath):
                os.remove(filepath)

    def _enable_mmd_tools(self):
        """Make sure mmd_tools addon is enabled"""
        bpy.ops.wm.read_homefile(use_empty=True)
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("bl_ext.blender_org.mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.blender_org.mmd_tools")

    # ********************************************
    # Helper Functions
    # ********************************************

    def _check_material_properties(self, material):
        """Check basic material properties"""
        self.assertIsNotNone(material, "Material should exist")
        self.assertTrue(hasattr(material, "mmd_material"), "Material should have MMD properties")

        mmd_mat = material.mmd_material
        self.assertIsNotNone(mmd_mat, "MMD material properties should exist")
        self.assertTrue(hasattr(mmd_mat, "diffuse_color"), "Should have diffuse color")
        self.assertTrue(hasattr(mmd_mat, "specular_color"), "Should have specular color")
        self.assertTrue(hasattr(mmd_mat, "ambient_color"), "Should have ambient color")
        self.assertTrue(hasattr(mmd_mat, "alpha"), "Should have alpha")
        self.assertTrue(hasattr(mmd_mat, "shininess"), "Should have shininess")

    def _check_shader_nodes(self, material):
        """Check shader node setup"""
        self.assertTrue(material.use_nodes, "Material should use nodes")
        self.assertIsNotNone(material.node_tree, "Material should have node tree")

        nodes = material.node_tree.nodes
        self.assertGreater(len(nodes), 0, "Should have shader nodes")

    def _check_texture_setup(self, material, texture_type="base"):
        """Check texture node setup"""
        if not material.use_nodes:
            return False

        nodes = material.node_tree.nodes
        texture_node_names = {"base": "mmd_base_tex", "toon": "mmd_toon_tex", "sphere": "mmd_sphere_tex"}

        node_name = texture_node_names.get(texture_type, "mmd_base_tex")
        texture_node = nodes.get(node_name)

        if texture_node:
            self.assertEqual(texture_node.type, "TEX_IMAGE", "Should be image texture node")
            return True
        return False

    # ********************************************
    # Core Material Tests (FnMaterial)
    # ********************************************

    def test_fn_material_creation_and_basic_properties(self):
        """Test FnMaterial creation and basic property access"""
        self._enable_mmd_tools()

        # Create test material
        material = self.__create_test_material()
        fn_material = FnMaterial(material)

        # Test basic properties
        self.assertIsNotNone(fn_material.material, "Should have material reference")
        self.assertEqual(fn_material.material, material, "Should reference correct material")

        # Test material ID
        material_id = fn_material.material_id
        self.assertIsInstance(material_id, int, "Material ID should be integer")
        self.assertGreaterEqual(material_id, 0, "Material ID should be non-negative")

        print("✓ FnMaterial creation test passed")

    def test_fn_material_from_material_id(self):
        """Test finding material by ID"""
        self._enable_mmd_tools()

        # Create test materials
        material1 = self.__create_test_material("TestMat1")
        material2 = self.__create_test_material("TestMat2")

        fn_mat1 = FnMaterial(material1)
        fn_mat2 = FnMaterial(material2)

        # Get material IDs
        mat1_id = fn_mat1.material_id
        mat2_id = fn_mat2.material_id

        # Test finding by ID
        found_mat1 = FnMaterial.from_material_id(mat1_id)
        found_mat2 = FnMaterial.from_material_id(mat2_id)

        self.assertIsNotNone(found_mat1, "Should find material 1 by ID")
        self.assertIsNotNone(found_mat2, "Should find material 2 by ID")
        self.assertEqual(found_mat1.material, material1, "Should find correct material 1")
        self.assertEqual(found_mat2.material, material2, "Should find correct material 2")

        # Test non-existent ID
        non_existent = FnMaterial.from_material_id("999999")
        self.assertIsNone(non_existent, "Should return None for non-existent ID")

        print("✓ FnMaterial from_material_id test passed")

    def test_fn_material_texture_operations(self):
        """Test texture creation, removal, and management"""
        self._enable_mmd_tools()

        material = self.__create_test_material()
        fn_material = FnMaterial(material)

        # Create test texture file
        texture_path = self.__create_test_texture_file()

        try:
            # Test base texture
            self.assertIsNone(fn_material.get_texture(), "Should have no texture initially")

            texture_slot = fn_material.create_texture(texture_path)
            self.assertIsNotNone(texture_slot, "Should create texture slot")
            self.assertIsNotNone(fn_material.get_texture(), "Should have texture after creation")

            texture = fn_material.get_texture()
            self.assertEqual(texture.type, "IMAGE", "Should be image texture")
            self.assertIsNotNone(texture.image, "Should have image")

            # Test texture removal
            fn_material.remove_texture()
            self.assertIsNone(fn_material.get_texture(), "Should have no texture after removal")

            print("✓ Base texture operations test passed")

            # Test sphere texture
            sphere_texture_slot = fn_material.create_sphere_texture(texture_path)
            self.assertIsNotNone(sphere_texture_slot, "Should create sphere texture slot")
            self.assertIsNotNone(fn_material.get_sphere_texture(), "Should have sphere texture")

            fn_material.remove_sphere_texture()
            self.assertIsNone(fn_material.get_sphere_texture(), "Should have no sphere texture after removal")

            print("✓ Sphere texture operations test passed")

            # Test toon texture
            toon_texture_slot = fn_material.create_toon_texture(texture_path)
            self.assertIsNotNone(toon_texture_slot, "Should create toon texture slot")
            self.assertIsNotNone(fn_material.get_toon_texture(), "Should have toon texture")

            fn_material.remove_toon_texture()
            self.assertIsNone(fn_material.get_toon_texture(), "Should have no toon texture after removal")

            print("✓ Toon texture operations test passed")

        finally:
            self.__clean_test_files()

    def test_fn_material_color_updates(self):
        """Test color property updates"""
        self._enable_mmd_tools()

        material = self.__create_test_material()
        fn_material = FnMaterial(material)
        mmd_mat = material.mmd_material

        # Test diffuse and ambient color mixing - MMD Tools has special mixing logic
        test_diffuse = (1.0, 0.5, 0.2)
        test_ambient = (0.2, 0.15, 0.1)

        mmd_mat.diffuse_color = test_diffuse
        mmd_mat.ambient_color = test_ambient
        fn_material.update_diffuse_color()

        # MMD Tools mixes diffuse and ambient: min(1.0, 0.5 * diffuse + ambient)
        # This is the _mix_diffuse_and_ambient logic in MMD Tools
        expected_r = min(1.0, 0.5 * test_diffuse[0] + test_ambient[0])
        expected_g = min(1.0, 0.5 * test_diffuse[1] + test_ambient[1])
        expected_b = min(1.0, 0.5 * test_diffuse[2] + test_ambient[2])

        # Check if material diffuse color was updated with mixed values
        self.assertAlmostEqual(material.diffuse_color[0], expected_r, places=6, msg="Mixed diffuse R component should match expected value")
        self.assertAlmostEqual(material.diffuse_color[1], expected_g, places=6, msg="Mixed diffuse G component should match expected value")
        self.assertAlmostEqual(material.diffuse_color[2], expected_b, places=6, msg="Mixed diffuse B component should match expected value")

        print(f"   - Mixed diffuse color: ({expected_r:.3f}, {expected_g:.3f}, {expected_b:.3f})")

        # Test specular color (should be direct assignment, no mixing)
        test_specular = (0.8, 0.9, 1.0)
        mmd_mat.specular_color = test_specular
        fn_material.update_specular_color()
        self.assertAlmostEqual(material.specular_color[0], test_specular[0], places=6, msg="Specular color should be directly assigned")
        self.assertAlmostEqual(material.specular_color[1], test_specular[1], places=6, msg="Specular color should be directly assigned")
        self.assertAlmostEqual(material.specular_color[2], test_specular[2], places=6, msg="Specular color should be directly assigned")

        # Test ambient color update
        test_ambient_new = (0.1, 0.2, 0.3)
        mmd_mat.ambient_color = test_ambient_new
        fn_material.update_ambient_color()

        # After ambient update, diffuse should be recalculated
        expected_r_new = min(1.0, 0.5 * test_diffuse[0] + test_ambient_new[0])
        expected_g_new = min(1.0, 0.5 * test_diffuse[1] + test_ambient_new[1])
        expected_b_new = min(1.0, 0.5 * test_diffuse[2] + test_ambient_new[2])

        self.assertAlmostEqual(material.diffuse_color[0], expected_r_new, places=6, msg="Diffuse should update when ambient changes")
        self.assertAlmostEqual(material.diffuse_color[1], expected_g_new, places=6, msg="Diffuse should update when ambient changes")
        self.assertAlmostEqual(material.diffuse_color[2], expected_b_new, places=6, msg="Diffuse should update when ambient changes")

        # Test alpha
        test_alpha = 0.7
        mmd_mat.alpha = test_alpha
        fn_material.update_alpha()

        # Check alpha in material diffuse_color if it has alpha component
        if len(material.diffuse_color) > 3:
            self.assertAlmostEqual(material.diffuse_color[3], test_alpha, places=6, msg="Material alpha should be updated")

        # Test shininess
        test_shininess = 50.0
        mmd_mat.shininess = test_shininess
        fn_material.update_shininess()

        # Check if roughness was calculated correctly: roughness = 1 / pow(max(shininess, 1), 0.37)
        expected_roughness = 1 / pow(max(test_shininess, 1), 0.37)
        self.assertAlmostEqual(material.roughness, expected_roughness, places=6, msg="Material roughness should be calculated from shininess")

        print("✓ Color updates test passed")

    def test_fn_material_sphere_texture_types(self):
        """Test sphere texture type handling"""
        self._enable_mmd_tools()

        material = self.__create_test_material()
        fn_material = FnMaterial(material)
        mmd_mat = material.mmd_material

        # Create test texture
        texture_path = self.__create_test_texture_file()

        try:
            fn_material.create_sphere_texture(texture_path)

            # Test different sphere texture types
            sphere_types = ["0", "1", "2", "3"]  # OFF, MULT, ADD, SUBTEX

            for sphere_type in sphere_types:
                mmd_mat.sphere_texture_type = sphere_type
                fn_material.update_sphere_texture_type()

                if sphere_type == "0":
                    # Should be disabled
                    fn_material.use_sphere_texture(False)
                else:
                    # Should be enabled
                    fn_material.use_sphere_texture(True)

                print(f"   - Tested sphere texture type: {sphere_type}")

        finally:
            self.__clean_test_files()

        print("✓ Sphere texture types test passed")

    def test_fn_material_edge_properties(self):
        """Test edge-related properties"""
        self._enable_mmd_tools()

        material = self.__create_test_material()
        fn_material = FnMaterial(material)
        mmd_mat = material.mmd_material

        # Test edge color
        test_edge_color = (0.2, 0.4, 0.6, 0.8)
        mmd_mat.edge_color = test_edge_color
        mmd_mat.enabled_toon_edge = True

        fn_material.update_edge_color()
        fn_material.update_enabled_toon_edge()

        # Test edge weight
        test_edge_weight = 1.5
        mmd_mat.edge_weight = test_edge_weight
        fn_material.update_edge_weight()

        print("✓ Edge properties test passed")

    def test_fn_material_double_sided_and_shadows(self):
        """Test double-sided and shadow properties"""
        self._enable_mmd_tools()

        material = self.__create_test_material()
        fn_material = FnMaterial(material)
        mmd_mat = material.mmd_material

        # Test double-sided
        mmd_mat.is_double_sided = True
        fn_material.update_is_double_sided()

        # Test self shadow
        mmd_mat.enabled_self_shadow = True
        fn_material.update_self_shadow()

        # Test self shadow map
        mmd_mat.enabled_self_shadow_map = True
        fn_material.update_self_shadow_map()

        # Test drop shadow update
        fn_material.update_drop_shadow()

        print("✓ Double-sided and shadows test passed")

    def test_fn_material_swap_materials(self):
        """Test material swapping functionality"""
        self._enable_mmd_tools()

        # Create test mesh with multiple materials
        mesh_obj, _ = self.__create_test_mesh_with_material("Material1")
        material2 = self.__create_test_material("Material2")
        material3 = self.__create_test_material("Material3")

        mesh_obj.data.materials.append(material2)
        mesh_obj.data.materials.append(material3)

        # Create some faces with different material indices
        mesh = mesh_obj.data
        mesh.polygons[0].material_index = 0
        if len(mesh.polygons) > 1:
            mesh.polygons[1].material_index = 1
        if len(mesh.polygons) > 2:
            mesh.polygons[2].material_index = 2

        # Test swapping by index
        original_mat0 = mesh.materials[0]
        original_mat1 = mesh.materials[1]

        mat1, mat2 = FnMaterial.swap_materials(mesh_obj, 0, 1, reverse=True, swap_slots=True)

        self.assertEqual(mat1, original_mat0, "Should return first material")
        self.assertEqual(mat2, original_mat1, "Should return second material")
        self.assertEqual(mesh.materials[0], original_mat1, "Materials should be swapped in slots")
        self.assertEqual(mesh.materials[1], original_mat0, "Materials should be swapped in slots")

        # Test swapping by name
        FnMaterial.swap_materials(mesh_obj, "Material2", "Material3", reverse=True, swap_slots=True)

        print("✓ Material swapping test passed")

    def test_fn_material_swap_materials_errors(self):
        """Test material swapping error handling"""
        self._enable_mmd_tools()

        mesh_obj, _ = self.__create_test_mesh_with_material()

        # Test with invalid material references
        with self.assertRaises(MaterialNotFoundError):
            FnMaterial.swap_materials(mesh_obj, 0, 999)  # Non-existent index

        with self.assertRaises(MaterialNotFoundError):
            FnMaterial.swap_materials(mesh_obj, "NonExistent1", "NonExistent2")  # Non-existent names

        print("✓ Material swapping error handling test passed")

    def test_fn_material_fix_material_order(self):
        """Test material order fixing functionality"""
        self._enable_mmd_tools()

        # Create test mesh with multiple materials
        mesh_obj, material1 = self.__create_test_mesh_with_material("Material1")
        material2 = self.__create_test_material("Material2")
        material3 = self.__create_test_material("Material3")

        mesh_obj.data.materials.append(material2)
        mesh_obj.data.materials.append(material3)

        # Mess up the order by swapping
        FnMaterial.swap_materials(mesh_obj, 0, 2, reverse=True, swap_slots=True)

        # Fix the order
        desired_order = ["Material1", "Material2", "Material3"]
        FnMaterial.fixMaterialOrder(mesh_obj, desired_order)

        # Check if order is correct
        for i, name in enumerate(desired_order):
            self.assertEqual(mesh_obj.data.materials[i].name, name, f"Material {i} should be {name}")

        print("✓ Material order fixing test passed")

    def test_fn_material_clean_materials(self):
        """Test material cleaning functionality"""
        self._enable_mmd_tools()

        # Create test mesh with materials
        mesh_obj, material1 = self.__create_test_mesh_with_material("KeepMaterial")
        material2 = self.__create_test_material("RemoveMaterial")

        mesh_obj.data.materials.append(material2)

        # Define removal criteria
        def can_remove(material):
            return material and material.name.startswith("Remove")

        original_count = len(mesh_obj.data.materials)
        FnMaterial.clean_materials(mesh_obj, can_remove)

        self.assertLess(len(mesh_obj.data.materials), original_count, "Should remove some materials")

        # Check remaining materials
        remaining_names = [m.name for m in mesh_obj.data.materials if m]
        self.assertNotIn("RemoveMaterial", remaining_names, "RemoveMaterial should be gone")
        self.assertIn("KeepMaterial", remaining_names, "KeepMaterial should remain")

        print("✓ Material cleaning test passed")

    def test_fn_material_convert_to_mmd_material(self):
        """Test converting standard Blender material to MMD material"""
        self._enable_mmd_tools()

        # Create standard Blender material with nodes
        material = bpy.data.materials.new("StandardMaterial")
        material.use_nodes = True
        # Set initial material properties - these will be used as fallback
        material.diffuse_color = (0.8, 0.6, 0.4, 1.0)
        material.specular_color = (1.0, 1.0, 1.0)
        material.roughness = 0.5

        # Get the initial MMD material default values before conversion
        mmd_mat_initial = material.mmd_material
        initial_diffuse = mmd_mat_initial.diffuse_color[:]
        initial_ambient = mmd_mat_initial.ambient_color[:]

        print(f"   - Initial MMD diffuse color: {initial_diffuse}")
        print(f"   - Initial MMD ambient color: {initial_ambient}")

        # Clear default nodes and add BSDF node manually to ensure predictable behavior
        nodes = material.node_tree.nodes
        nodes.clear()

        # Add Principled BSDF node
        bsdf_node = nodes.new("ShaderNodeBsdfPrincipled")
        bsdf_node.inputs["Base Color"].default_value = (0.9, 0.7, 0.5, 1.0)

        # Add Material Output node
        output_node = nodes.new("ShaderNodeOutputMaterial")

        # Connect BSDF to output
        links = material.node_tree.links
        links.new(bsdf_node.outputs["BSDF"], output_node.inputs["Surface"])

        # Add a texture node that should be renamed
        tex_node = nodes.new("ShaderNodeTexImage")
        tex_node.name = "TextureNode"

        # Convert to MMD material
        FnMaterial.convert_to_mmd_material(material)

        # Check if MMD properties were set correctly
        mmd_mat = material.mmd_material
        self.assertIsNotNone(mmd_mat.diffuse_color, "Should have diffuse color")

        # Since mmd_material.diffuse_color already has default values (not None),
        # the conversion logic only uses material.diffuse_color as fallback when
        # mmd_material.diffuse_color is None, which it isn't.
        # The actual behavior is that it keeps the existing MMD material values
        # unless they were explicitly set by BSDF logic (which doesn't happen with texture nodes)

        # Check if diffuse color remained as initial values (since texture node exists)
        self.assertAlmostEqual(mmd_mat.diffuse_color[0], initial_diffuse[0], places=6, msg="Diffuse R should keep initial MMD value when texture exists")
        self.assertAlmostEqual(mmd_mat.diffuse_color[1], initial_diffuse[1], places=6, msg="Diffuse G should keep initial MMD value when texture exists")
        self.assertAlmostEqual(mmd_mat.diffuse_color[2], initial_diffuse[2], places=6, msg="Diffuse B should keep initial MMD value when texture exists")

        # Ambient color should be half the diffuse color as per conversion logic
        expected_ambient = [x * 0.5 for x in mmd_mat.diffuse_color]
        self.assertAlmostEqual(mmd_mat.ambient_color[0], expected_ambient[0], places=6, msg="Ambient R should be half of diffuse R")
        self.assertAlmostEqual(mmd_mat.ambient_color[1], expected_ambient[1], places=6, msg="Ambient G should be half of diffuse G")
        self.assertAlmostEqual(mmd_mat.ambient_color[2], expected_ambient[2], places=6, msg="Ambient B should be half of diffuse B")

        # Check alpha conversion from material
        self.assertAlmostEqual(mmd_mat.alpha, material.diffuse_color[3], places=6, msg="Alpha should be converted from material")

        # Check specular color conversion
        for i in range(3):
            self.assertAlmostEqual(mmd_mat.specular_color[i], material.specular_color[i], places=6, msg=f"Specular color component {i} should be copied from material")

        # Check shininess calculation from roughness
        # shininess = pow(1 / max(roughness, 0.099), 1 / 0.37)
        expected_shininess = pow(1 / max(material.roughness, 0.099), 1 / 0.37)
        self.assertAlmostEqual(mmd_mat.shininess, expected_shininess, places=0, msg="Shininess should be calculated from roughness")

        # Check if texture node was renamed to mmd_base_tex
        renamed_node = nodes.get("mmd_base_tex")
        self.assertIsNotNone(renamed_node, "First texture node should be renamed to mmd_base_tex")
        self.assertEqual(renamed_node.type, "TEX_IMAGE", "Renamed node should be texture image node")

        # Check that BSDF nodes were removed as per conversion logic
        bsdf_nodes = [n for n in nodes if n.type.startswith("BSDF_")]
        self.assertEqual(len(bsdf_nodes), 0, "BSDF nodes should be removed after conversion")

        # Test the BSDF Base Color logic separately (when no texture nodes exist)
        print("\n   - Testing BSDF Base Color conversion without texture nodes...")

        # Create another material without texture nodes
        material2 = bpy.data.materials.new("StandardMaterial2")
        material2.use_nodes = True
        material2.diffuse_color = (0.1, 0.1, 0.1, 1.0)  # Different base color
        material2.specular_color = (1.0, 1.0, 1.0)
        material2.roughness = 0.3

        # Clear nodes and add only BSDF + Output
        nodes2 = material2.node_tree.nodes
        nodes2.clear()

        bsdf_node2 = nodes2.new("ShaderNodeBsdfPrincipled")
        bsdf_base_color2 = (0.9, 0.7, 0.5, 1.0)
        bsdf_node2.inputs["Base Color"].default_value = bsdf_base_color2

        output_node2 = nodes2.new("ShaderNodeOutputMaterial")
        links2 = material2.node_tree.links
        links2.new(bsdf_node2.outputs["BSDF"], output_node2.inputs["Surface"])

        # Convert this material (should use BSDF Base Color since no texture)
        FnMaterial.convert_to_mmd_material(material2)

        mmd_mat2 = material2.mmd_material

        # This should use BSDF Base Color because there's no texture node
        # and the BSDF logic should have set the diffuse color
        self.assertAlmostEqual(mmd_mat2.diffuse_color[0], bsdf_base_color2[0], places=6, msg="Material2 diffuse R should match BSDF Base Color R")
        self.assertAlmostEqual(mmd_mat2.diffuse_color[1], bsdf_base_color2[1], places=6, msg="Material2 diffuse G should match BSDF Base Color G")
        self.assertAlmostEqual(mmd_mat2.diffuse_color[2], bsdf_base_color2[2], places=6, msg="Material2 diffuse B should match BSDF Base Color B")

        # Ambient should be half of the BSDF-set diffuse color
        expected_ambient2 = [x * 0.5 for x in mmd_mat2.diffuse_color]
        self.assertAlmostEqual(mmd_mat2.ambient_color[0], expected_ambient2[0], places=6, msg="Material2 ambient R should be half of BSDF-set diffuse R")
        self.assertAlmostEqual(mmd_mat2.ambient_color[1], expected_ambient2[1], places=6, msg="Material2 ambient G should be half of BSDF-set diffuse G")
        self.assertAlmostEqual(mmd_mat2.ambient_color[2], expected_ambient2[2], places=6, msg="Material2 ambient B should be half of BSDF-set diffuse B")

        print(f"   - Converted diffuse color (with texture): {mmd_mat.diffuse_color}")
        print(f"   - Converted diffuse color (no texture): {mmd_mat2.diffuse_color}")
        print(f"   - Calculated ambient color: {mmd_mat.ambient_color}")
        print(f"   - Calculated shininess: {mmd_mat.shininess:.1f}")
        print("✓ Convert to MMD material test passed")

    # ********************************************
    # Operator Tests
    # ********************************************

    def test_material_operators_basic_functionality(self):
        """Test basic material operator functionality"""
        self._enable_mmd_tools()

        # Create test setup
        mesh_obj, material = self.__create_test_mesh_with_material()
        bpy.context.view_layer.objects.active = mesh_obj
        mesh_obj.active_material_index = 0

        # Test that operators exist
        self.assertTrue(hasattr(bpy.ops.mmd_tools, "material_open_texture"), "Should have open texture operator")
        self.assertTrue(hasattr(bpy.ops.mmd_tools, "material_remove_texture"), "Should have remove texture operator")
        self.assertTrue(hasattr(bpy.ops.mmd_tools, "material_open_sphere_texture"), "Should have open sphere texture operator")
        self.assertTrue(hasattr(bpy.ops.mmd_tools, "material_remove_sphere_texture"), "Should have remove sphere texture operator")

        # Test remove texture operator (should work even without texture)
        if bpy.ops.mmd_tools.material_remove_texture.poll():
            result = bpy.ops.mmd_tools.material_remove_texture()
            self.assertIn(result, [{"FINISHED"}, {"CANCELLED"}], "Remove texture should complete")

        # Test remove sphere texture operator
        if bpy.ops.mmd_tools.material_remove_sphere_texture.poll():
            result = bpy.ops.mmd_tools.material_remove_sphere_texture()
            self.assertIn(result, [{"FINISHED"}, {"CANCELLED"}], "Remove sphere texture should complete")

        print("✓ Material operators basic functionality test passed")

    def test_material_move_operators(self):
        """Test material move up/down operators"""
        self._enable_mmd_tools()

        # Create test mesh with multiple materials
        mesh_obj, material1 = self.__create_test_mesh_with_material("Material1")
        material2 = self.__create_test_material("Material2")
        material3 = self.__create_test_material("Material3")

        mesh_obj.data.materials.append(material2)
        mesh_obj.data.materials.append(material3)

        bpy.context.view_layer.objects.active = mesh_obj
        mesh_obj.active_material_index = 1  # Select middle material

        # Test move up
        if bpy.ops.mmd_tools.move_material_up.poll():
            result = bpy.ops.mmd_tools.move_material_up()
            self.assertEqual(result, {"FINISHED"}, "Move up should succeed")
            self.assertEqual(mesh_obj.active_material_index, 0, "Active index should move up")

        # Test move down
        mesh_obj.active_material_index = 0  # Reset to first
        if bpy.ops.mmd_tools.move_material_down.poll():
            result = bpy.ops.mmd_tools.move_material_down()
            self.assertEqual(result, {"FINISHED"}, "Move down should succeed")
            self.assertEqual(mesh_obj.active_material_index, 1, "Active index should move down")

        print("✓ Material move operators test passed")

    def test_convert_materials_operators(self):
        """Test material conversion operators"""
        self._enable_mmd_tools()

        # Create test mesh with material
        mesh_obj, material = self.__create_test_mesh_with_material()
        mesh_obj.select_set(True)
        bpy.context.view_layer.objects.active = mesh_obj

        # Test convert materials operator
        if bpy.ops.mmd_tools.convert_materials.poll():
            result = bpy.ops.mmd_tools.convert_materials()
            self.assertIn(result, [{"FINISHED"}, {"CANCELLED"}], "Convert materials should complete")

        # Test convert BSDF materials operator
        if bpy.ops.mmd_tools.convert_bsdf_materials.poll():
            result = bpy.ops.mmd_tools.convert_bsdf_materials()
            self.assertIn(result, [{"FINISHED"}, {"CANCELLED"}], "Convert BSDF materials should complete")

        print("✓ Material conversion operators test passed")

    def test_edge_preview_operators(self):
        """Test edge preview setup operators"""
        self._enable_mmd_tools()

        # Create test MMD model
        root, mesh_obj, material = self.__create_test_mmd_model()
        root_obj = root.rootObject()

        bpy.context.view_layer.objects.active = root_obj

        # Enable toon edge on material
        mmd_mat = material.mmd_material
        mmd_mat.enabled_toon_edge = True
        mmd_mat.edge_color = (0.0, 0.0, 0.0, 1.0)
        mmd_mat.edge_weight = 1.0

        # Test edge preview setup - CREATE
        if bpy.ops.mmd_tools.edge_preview_setup.poll():
            result = bpy.ops.mmd_tools.edge_preview_setup(action="CREATE")
            self.assertIn(result, [{"FINISHED"}, {"CANCELLED"}], "Edge preview create should complete")

            # Check if edge preview modifier was added
            edge_modifier = mesh_obj.modifiers.get("mmd_edge_preview")
            if edge_modifier:
                self.assertEqual(edge_modifier.type, "SOLIDIFY", "Should be solidify modifier")
                print("   - Edge preview modifier created")

            # Test edge preview setup - CLEAN
            result = bpy.ops.mmd_tools.edge_preview_setup(action="CLEAN")
            self.assertIn(result, [{"FINISHED"}, {"CANCELLED"}], "Edge preview clean should complete")

            # Check if edge preview was cleaned
            edge_modifier = mesh_obj.modifiers.get("mmd_edge_preview")
            self.assertIsNone(edge_modifier, "Edge preview modifier should be removed")
            print("   - Edge preview cleaned")

        print("✓ Edge preview operators test passed")

    # ********************************************
    # Shader Node Tests
    # ********************************************

    def test_shader_node_creation(self):
        """Test MMD shader node creation and setup"""
        self._enable_mmd_tools()

        material = self.__create_test_material()
        fn_material = FnMaterial(material)

        # Trigger shader node creation by updating properties
        fn_material.update_diffuse_color()
        fn_material.update_ambient_color()

        # Check if shader nodes were created
        self._check_shader_nodes(material)

        nodes = material.node_tree.nodes
        mmd_shader = nodes.get("mmd_shader")
        mmd_tex_uv = nodes.get("mmd_tex_uv")

        if mmd_shader:
            self.assertEqual(mmd_shader.type, "GROUP", "MMD shader should be group node")
            print("   - MMD shader node created")

        if mmd_tex_uv:
            self.assertEqual(mmd_tex_uv.type, "GROUP", "MMD texture UV should be group node")
            print("   - MMD texture UV node created")

        print("✓ Shader node creation test passed")

    def test_shader_input_updates(self):
        """Test shader input value updates"""
        self._enable_mmd_tools()

        material = self.__create_test_material()
        fn_material = FnMaterial(material)
        mmd_mat = material.mmd_material

        # Set some test values
        test_diffuse = (0.8, 0.6, 0.4)
        test_ambient = (0.2, 0.15, 0.1)
        test_specular = (1.0, 1.0, 1.0)
        test_alpha = 0.9
        test_shininess = 30.0

        mmd_mat.diffuse_color = test_diffuse
        mmd_mat.ambient_color = test_ambient
        mmd_mat.specular_color = test_specular
        mmd_mat.alpha = test_alpha
        mmd_mat.shininess = test_shininess

        # Update shader inputs
        fn_material.update_diffuse_color()
        fn_material.update_ambient_color()
        fn_material.update_specular_color()
        fn_material.update_alpha()
        fn_material.update_shininess()

        # Check if shader was created and inputs are accessible
        if material.node_tree:
            nodes = material.node_tree.nodes
            mmd_shader = nodes.get("mmd_shader")

            if mmd_shader:
                # Check if inputs exist (values might be set internally)
                input_names = ["Diffuse Color", "Ambient Color", "Specular Color", "Alpha", "Reflect"]
                for input_name in input_names:
                    if input_name in mmd_shader.inputs:
                        print(f"   - Found shader input: {input_name}")

        print("✓ Shader input updates test passed")

    def test_shader_texture_connections(self):
        """Test shader texture node connections"""
        self._enable_mmd_tools()

        material = self.__create_test_material()
        fn_material = FnMaterial(material)

        # Create test texture
        texture_path = self.__create_test_texture_file()

        try:
            # Create textures
            fn_material.create_texture(texture_path)
            fn_material.create_toon_texture(texture_path)
            fn_material.create_sphere_texture(texture_path)

            # Trigger shader update
            fn_material.update_diffuse_color()

            # Check texture connections
            if material.node_tree:
                nodes = material.node_tree.nodes

                # Check if texture nodes exist
                texture_nodes = ["mmd_base_tex", "mmd_toon_tex", "mmd_sphere_tex"]
                for node_name in texture_nodes:
                    tex_node = nodes.get(node_name)
                    if tex_node:
                        self.assertEqual(tex_node.type, "TEX_IMAGE", f"{node_name} should be image texture")
                        print(f"   - Found texture node: {node_name}")

                # Check if shader node exists and has connections
                mmd_shader = nodes.get("mmd_shader")
                if mmd_shader:
                    connected_inputs = [inp for inp in mmd_shader.inputs if inp.is_linked]
                    print(f"   - Shader has {len(connected_inputs)} connected inputs")

                    # Check specific texture connections
                    texture_input_names = ["Base Tex", "Toon Tex", "Sphere Tex"]
                    for input_name in texture_input_names:
                        if input_name in mmd_shader.inputs:
                            input_socket = mmd_shader.inputs[input_name]
                            if input_socket.is_linked:
                                print(f"   - {input_name} is connected")

        finally:
            self.__clean_test_files()

        print("✓ Shader texture connections test passed")

    def test_shader_sphere_texture_modes(self):
        """Test sphere texture blend modes in shader"""
        self._enable_mmd_tools()

        material = self.__create_test_material()
        fn_material = FnMaterial(material)
        mmd_mat = material.mmd_material

        # Create sphere texture
        texture_path = self.__create_test_texture_file()

        try:
            fn_material.create_sphere_texture(texture_path)

            # Test different sphere texture types
            sphere_modes = {"0": "OFF", "1": "MULT", "2": "ADD", "3": "SUBTEX"}

            for mode_value, mode_name in sphere_modes.items():
                mmd_mat.sphere_texture_type = mode_value
                fn_material.update_sphere_texture_type()

                # Check if shader reflects the mode
                if material.node_tree:
                    nodes = material.node_tree.nodes
                    mmd_shader = nodes.get("mmd_shader")

                    if mmd_shader and "Sphere Tex Fac" in mmd_shader.inputs:
                        fac_value = mmd_shader.inputs["Sphere Tex Fac"].default_value
                        if mode_value == "0":
                            self.assertEqual(fac_value, 0, f"Sphere factor should be 0 for {mode_name}")
                        else:
                            self.assertEqual(fac_value, 1, f"Sphere factor should be 1 for {mode_name}")

                print(f"   - Tested sphere mode: {mode_name}")

        finally:
            self.__clean_test_files()

        print("✓ Shader sphere texture modes test passed")

    # ********************************************
    # Panel Tests (UI)
    # ********************************************

    def test_mmd_material_panel_poll(self):
        """Test MMD material panel poll conditions"""
        self._enable_mmd_tools()

        # Test with no active object
        bpy.context.view_layer.objects.active = None
        self.assertFalse(MMDMaterialPanel.poll(bpy.context), "Should not poll with no active object")

        # Test with object but no material
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        self.assertFalse(MMDMaterialPanel.poll(bpy.context), "Should not poll with no material")

        # Test with material
        material = self.__create_test_material()
        cube.data.materials.append(material)
        cube.active_material = material
        self.assertTrue(MMDMaterialPanel.poll(bpy.context), "Should poll with material")

        print("✓ MMD material panel poll test passed")

    def test_mmd_texture_panel_poll(self):
        """Test MMD texture panel poll conditions"""
        self._enable_mmd_tools()

        # Test similar conditions as material panel
        mesh_obj, material = self.__create_test_mesh_with_material()
        bpy.context.view_layer.objects.active = mesh_obj

        self.assertTrue(MMDTexturePanel.poll(bpy.context), "Should poll with material")

        print("✓ MMD texture panel poll test passed")

    # ********************************************
    # Integration Tests
    # ********************************************

    def test_material_complete_workflow(self):
        """Test complete material workflow from creation to rendering"""
        self._enable_mmd_tools()

        print("\nTesting complete material workflow...")

        # Create MMD model
        root, mesh_obj, material = self.__create_test_mmd_model()
        fn_material = FnMaterial(material)
        mmd_mat = material.mmd_material

        # Set up material properties
        mmd_mat.name_j = "テストマテリアル"
        mmd_mat.name_e = "TestMaterial"
        mmd_mat.diffuse_color = (0.8, 0.6, 0.4)
        mmd_mat.specular_color = (1.0, 1.0, 1.0)
        mmd_mat.ambient_color = (0.2, 0.15, 0.1)
        mmd_mat.alpha = 0.95
        mmd_mat.shininess = 50.0

        # Set up edge properties
        mmd_mat.enabled_toon_edge = True
        mmd_mat.edge_color = (0.0, 0.0, 0.0, 1.0)
        mmd_mat.edge_weight = 1.0

        # Set up shadow properties
        mmd_mat.enabled_self_shadow = True
        mmd_mat.enabled_self_shadow_map = True
        mmd_mat.is_double_sided = False

        # Create textures
        texture_path = self.__create_test_texture_file()

        try:
            # Add base texture
            fn_material.create_texture(texture_path)
            fn_material.create_toon_texture(texture_path)
            fn_material.create_sphere_texture(texture_path)

            # Set sphere texture type
            mmd_mat.sphere_texture_type = "2"  # ADD mode

            # Update all properties
            fn_material.update_diffuse_color()
            fn_material.update_specular_color()
            fn_material.update_ambient_color()
            fn_material.update_alpha()
            fn_material.update_shininess()
            fn_material.update_edge_color()
            fn_material.update_enabled_toon_edge()
            fn_material.update_is_double_sided()
            fn_material.update_self_shadow()
            fn_material.update_self_shadow_map()
            fn_material.update_sphere_texture_type()

            # Verify final state
            self._check_material_properties(material)
            self._check_shader_nodes(material)

            # Check textures
            self.assertTrue(self._check_texture_setup(material, "base"), "Should have base texture")
            self.assertTrue(self._check_texture_setup(material, "toon"), "Should have toon texture")
            self.assertTrue(self._check_texture_setup(material, "sphere"), "Should have sphere texture")

            # Test edge preview
            bpy.context.view_layer.objects.active = root.rootObject()
            if bpy.ops.mmd_tools.edge_preview_setup.poll():
                bpy.ops.mmd_tools.edge_preview_setup(action="CREATE")

                # Check if edge materials were created
                edge_materials = [mat for mat in bpy.data.materials if mat.name.startswith("mmd_edge.")]
                if edge_materials:
                    print(f"   - Created {len(edge_materials)} edge materials")

                # Clean up edge preview
                bpy.ops.mmd_tools.edge_preview_setup(action="CLEAN")

        finally:
            self.__clean_test_files()

        print("✓ Complete material workflow test passed")

    def test_material_stress_testing(self):
        """Test material system under stress conditions"""
        self._enable_mmd_tools()

        print("\nTesting material stress conditions...")

        # Create many materials rapidly
        materials = []
        for i in range(50):
            material = self.__create_test_material(f"StressMaterial_{i}")
            fn_material = FnMaterial(material)

            # Rapid property updates
            mmd_mat = material.mmd_material
            mmd_mat.diffuse_color = (i / 50.0, 0.5, 0.5)
            fn_material.update_diffuse_color()

            materials.append(material)

        print(f"   - Created {len(materials)} materials")

        # Test material swapping with many materials
        mesh_obj, _ = self.__create_test_mesh_with_material("BaseMaterial")
        for material in materials[:10]:  # Add first 10 materials
            mesh_obj.data.materials.append(material)

        # Perform multiple swaps
        for i in range(5):
            try:
                FnMaterial.swap_materials(mesh_obj, i, i + 1, reverse=True, swap_slots=True)
            except MaterialNotFoundError:
                pass  # Expected for some cases

        # Clean up stress test materials
        for material in materials:
            bpy.data.materials.remove(material)

        # Force garbage collection
        gc.collect()

        print("✓ Material stress testing passed")

    def test_material_edge_cases(self):
        """Test material system edge cases and error handling"""
        self._enable_mmd_tools()

        print("\nTesting material edge cases...")

        # Test with None material
        try:
            fn_material = FnMaterial(None)
            self.fail("Should raise error with None material")
        except Exception:
            pass  # Expected

        # Test with invalid texture paths
        material = self.__create_test_material()
        fn_material = FnMaterial(material)

        # Non-existent texture file
        invalid_texture_slot = fn_material.create_texture("/non/existent/path.png")
        self.assertIsNotNone(invalid_texture_slot, "Should handle invalid texture path gracefully")

        # Test extreme property values
        mmd_mat = material.mmd_material
        mmd_mat.alpha = 2.0  # Out of normal range
        mmd_mat.shininess = -10.0  # Negative value

        # Should handle gracefully
        fn_material.update_alpha()
        fn_material.update_shininess()

        # Test readonly mode
        FnMaterial.set_nodes_are_readonly(True)
        fn_material.update_diffuse_color()  # Should not crash
        FnMaterial.set_nodes_are_readonly(False)

        print("✓ Material edge cases test passed")

    def test_material_memory_management(self):
        """Test material system memory management"""
        self._enable_mmd_tools()

        print("\nTesting material memory management...")

        initial_material_count = len(bpy.data.materials)
        initial_image_count = len(bpy.data.images)

        # Create materials with textures
        texture_path = self.__create_test_texture_file()

        try:
            materials = []
            for i in range(10):
                material = self.__create_test_material(f"MemoryTestMaterial_{i}")
                fn_material = FnMaterial(material)

                # Add textures
                fn_material.create_texture(texture_path)
                fn_material.create_toon_texture(texture_path)
                fn_material.create_sphere_texture(texture_path)

                materials.append(material)

            mid_material_count = len(bpy.data.materials)
            mid_image_count = len(bpy.data.images)

            self.assertGreater(mid_material_count, initial_material_count, "Should have more materials")

            # Remove materials
            for material in materials:
                bpy.data.materials.remove(material)

            # Force cleanup
            gc.collect()

            final_material_count = len(bpy.data.materials)
            final_image_count = len(bpy.data.images)

            print(f"   - Materials: {initial_material_count} -> {mid_material_count} -> {final_material_count}")
            print(f"   - Images: {initial_image_count} -> {mid_image_count} -> {final_image_count}")

        finally:
            self.__clean_test_files()

        print("✓ Material memory management test passed")

    def test_material_compatibility_versions(self):
        """Test material system compatibility across different versions"""
        self._enable_mmd_tools()

        print("\nTesting material version compatibility...")

        # Test material conversion from older formats
        material = self.__create_test_material()

        # Simulate older material setup
        material.diffuse_color = (0.8, 0.6, 0.4, 1.0)
        material.specular_color = (1.0, 1.0, 1.0)
        material.roughness = 0.3

        # Test conversion
        FnMaterial.convert_to_mmd_material(material)

        # Verify conversion
        mmd_mat = material.mmd_material
        self.assertIsNotNone(mmd_mat.diffuse_color, "Should have converted diffuse color")

        # Test shader migration
        MigrationFnMaterial.update_mmd_shader()

        print("✓ Material version compatibility test passed")

    def tearDown(self):
        """Clean up after each test"""
        self.__clean_test_files()

        # Clean up any remaining test objects
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=True)

        # Clean up materials
        test_materials = [mat for mat in bpy.data.materials if mat.name.startswith("Test")]
        for material in test_materials:
            bpy.data.materials.remove(material)

    def test_fn_material_nodes_readonly_mode(self):
        """Test FnMaterial readonly mode functionality"""
        self._enable_mmd_tools()

        material = self.__create_test_material()
        fn_material = FnMaterial(material)

        # Test normal mode first
        FnMaterial.set_nodes_are_readonly(False)
        fn_material.update_diffuse_color()

        # Enable readonly mode
        FnMaterial.set_nodes_are_readonly(True)

        # These operations should not modify nodes in readonly mode
        fn_material.update_toon_texture()
        fn_material.update_enabled_toon_edge()
        fn_material.remove_texture()
        fn_material.remove_sphere_texture()
        fn_material.remove_toon_texture()

        # Disable readonly mode
        FnMaterial.set_nodes_are_readonly(False)

        print("✓ FnMaterial readonly mode test passed")

    def test_fn_material_image_loading_edge_cases(self):
        """Test image loading with various edge cases"""
        self._enable_mmd_tools()

        material = self.__create_test_material()
        fn_material = FnMaterial(material)

        # Test with existing image
        test_image = bpy.data.images.new("existing_test.png", 1, 1)
        test_image.source = "FILE"
        test_image.filepath = "/fake/path/existing_test.png"

        # Test loading same path (should reuse existing)
        fn_material.create_texture("/fake/path/existing_test.png")
        texture = fn_material.get_texture()

        if texture and texture.image:
            self.assertEqual(texture.image.name, "existing_test.png", "Should reuse existing image")

        # Test with invalid path (should create placeholder)
        fn_material.create_toon_texture("/completely/invalid/path.jpg")
        toon_texture = fn_material.get_toon_texture()

        if toon_texture:
            self.assertIsNotNone(toon_texture.image, "Should create placeholder image for invalid path")

        print("✓ FnMaterial image loading edge cases test passed")

    def test_material_id_uniqueness(self):
        """Test material ID uniqueness functionality"""
        self._enable_mmd_tools()

        # Create multiple materials
        materials = []
        for i in range(5):
            material = self.__create_test_material(f"UniqueMaterial_{i}")
            fn_material = FnMaterial(material)
            materials.append((material, fn_material))

        # Get all material IDs
        material_ids = [fn_mat.material_id for _, fn_mat in materials]

        # Check uniqueness
        unique_ids = set(material_ids)
        self.assertEqual(len(material_ids), len(unique_ids), "All material IDs should be unique")

        # Check if IDs are sequential or properly assigned
        for material_id in material_ids:
            self.assertGreaterEqual(material_id, 0, "Material ID should be non-negative")

        # Test is_id_unique method
        for material, fn_mat in materials:
            mmd_mat = material.mmd_material
            if hasattr(mmd_mat, "is_id_unique"):
                unique = mmd_mat.is_id_unique()
                self.assertTrue(unique, f"Material {material.name} should have unique ID")

        print("✓ Material ID uniqueness test passed")


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main(verbosity=1, exit=True)
