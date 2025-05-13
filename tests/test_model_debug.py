
import logging
import os
import unittest

import bpy
from bl_ext.user_default.mmd_tools.core.model import FnModel, Model

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "samples")


class TestModelDebug(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Clean up output from previous tests"""
        output_dir = os.path.join(TESTS_DIR, "output")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def setUp(self):
        """Set up testing environment"""
        # Set logging level
        logger = logging.getLogger()
        logger.setLevel("INFO")  # Set to INFO to see validation messages

        # Clean scene and create a new MMD model
        bpy.ops.wm.read_homefile()
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.user_default.mmd_tools")  # make sure addon 'mmd_tools' is enabled

        # Create test model
        self.model_name = "Test Model"
        self.rig = Model.create(self.model_name, self.model_name, 0.08, add_root_bone=True)
        self.root_object = self.rig.rootObject()

        # Set as active object
        bpy.context.view_layer.objects.active = self.root_object

    def tearDown(self):
        """Clean up after test"""
        # Don't actually clean up to help with troubleshooting
        pass

    # ********************************************
    # Utility Methods
    # ********************************************

    def __create_test_bone_with_invalid_name(self):
        """Create a test bone with invalid name"""
        armature = FnModel.find_armature_object(self.root_object)
        bpy.context.view_layer.objects.active = armature

        # Switch to edit mode
        bpy.ops.object.mode_set(mode="EDIT")

        # Create a new bone with a long name
        long_bone = armature.data.edit_bones.new("TestBoneWithVeryLongName")
        long_bone.head = (0, 0, 0)
        long_bone.tail = (0, 1, 0)

        # Create a non-Japanese test bone with Chinese characters
        non_japanese_bone = armature.data.edit_bones.new("NonJapaneseTestBone1")
        non_japanese_bone.head = (0, 0, 0)
        non_japanese_bone.tail = (0, 1, 0)

        non_japanese_bone = armature.data.edit_bones.new("NonJapaneseTestBone2")
        non_japanese_bone.head = (0, 0, 0)
        non_japanese_bone.tail = (0, 1, 0)

        # Create a duplicate bone with the same name
        bone1 = armature.data.edit_bones.new("DuplicateNameBone1")
        bone1.head = (0, 0, 0)
        bone1.tail = (0, 1, 0)

        # Create another bone with the same name to create a duplicate
        bone2 = armature.data.edit_bones.new("DuplicateNameBone2")
        bone2.head = (0, 0, 0)
        bone2.tail = (0, 1, 0)

        # Switch back to object mode to update the bones
        bpy.ops.object.mode_set(mode="OBJECT")

        # Set Japanese names
        armature.pose.bones["TestBoneWithVeryLongName"].mmd_bone.name_j = "非常に長い名前のボーン"
        armature.pose.bones["NonJapaneseTestBone1"].mmd_bone.name_j = "测试"
        armature.pose.bones["NonJapaneseTestBone2"].mmd_bone.name_j = "測試测试"
        armature.pose.bones["DuplicateNameBone1"].mmd_bone.name_j = "重複した名前"
        armature.pose.bones["DuplicateNameBone2"].mmd_bone.name_j = "重複した名前"

        # Make sure active object is back to the root
        bpy.context.view_layer.objects.active = self.root_object

    def __create_test_morph_with_invalid_name(self):
        """Create test morphs with invalid/duplicate names"""
        # Add long name test
        test_morph = self.root_object.mmd_root.vertex_morphs.add()
        test_morph.name = "非常に長い名前のモーフ"

        # Add non-Japanese name test
        test_morph = self.root_object.mmd_root.vertex_morphs.add()
        test_morph.name = "测试"
        test_morph = self.root_object.mmd_root.group_morphs.add()
        test_morph.name = "测试"
        test_morph = self.root_object.mmd_root.group_morphs.add()
        test_morph.name = "測試测试"
        test_morph = self.root_object.mmd_root.group_morphs.add()
        test_morph.name = "口横缩げ"

        # Add duplicate name test
        test_morph = self.root_object.mmd_root.vertex_morphs.add()
        test_morph.name = "重複した名前"
        test_morph = self.root_object.mmd_root.group_morphs.add()
        test_morph.name = "重複した名前"  # Same name to create duplicate

    def __create_test_texture_issues(self):
        """Create test texture issues"""
        # Create a test mesh with material
        mesh_data = bpy.data.meshes.new("TestMesh")
        mesh_obj = bpy.data.objects.new("TestMeshObject", mesh_data)
        bpy.context.collection.objects.link(mesh_obj)

        # Create vertices and faces
        verts = [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)]
        faces = [(0, 1, 2, 3)]
        mesh_data.from_pydata(verts, [], faces)
        mesh_data.update()

        # Set parent to mmd armature
        mesh_obj.parent = FnModel.find_armature_object(self.root_object)

        # Create materials with texture problems
        mat1 = bpy.data.materials.new(name="Material1")
        mat1.use_nodes = True

        mat2 = bpy.data.materials.new(name="Material2")
        mat2.use_nodes = True

        # Assign materials to mesh
        mesh_data.materials.append(mat1)
        mesh_data.materials.append(mat2)

        # Create test textures with issues
        # 1. Same filename in different paths
        img1 = bpy.data.images.new("texture.png", 4, 4)
        img1.filepath = "/path1/texture.png"

        img2 = bpy.data.images.new("texture.png", 4, 4)  # Same filename
        img2.filepath = "/path2/texture.png"  # Different path

        # 2. Missing file reference
        img3 = bpy.data.images.new("missing.png", 4, 4)
        img3.filepath = "/path/missing.png"

        # Add texture nodes
        for mat, img in zip([mat1, mat2], [img1, img2]):
            nodes = mat.node_tree.nodes
            tex_node = nodes.new("ShaderNodeTexImage")
            tex_node.image = img

            # Add missing texture node to mat2
            if mat == mat2:
                tex_node2 = nodes.new("ShaderNodeTexImage")
                tex_node2.image = img3

    # ********************************************
    # Test Methods
    # ********************************************

    def test_1_validate_bone_limits(self):
        """Test if bone validation runs without errors"""
        print()
        self.__create_test_bone_with_invalid_name()

        # Set active object back to root
        bpy.context.view_layer.objects.active = self.root_object

        # Run validation using operator
        result = bpy.ops.mmd_tools.validate_bone_limits()

        # Check if the operation completed
        self.assertEqual(set(result), {"FINISHED"})

        # Print validation results
        print("Bone validation results:")
        print(bpy.context.scene.mmd_validation_results)
        print()

        # Just verify it runs without errors, don't verify specific messages
        self.assertIsNotNone(bpy.context.scene.mmd_validation_results)

    def test_2_validate_morphs(self):
        """Test if morph validation runs without errors"""
        print()
        self.__create_test_morph_with_invalid_name()

        # Set active object back to root
        bpy.context.view_layer.objects.active = self.root_object

        # Run validation using operator
        result = bpy.ops.mmd_tools.validate_morphs()

        # Check if the operation completed
        self.assertEqual(set(result), {"FINISHED"})

        # Print validation results
        print("Morph validation results:")
        print(bpy.context.scene.mmd_validation_results)
        print()

        # Just verify it runs without errors, don't verify specific messages
        self.assertIsNotNone(bpy.context.scene.mmd_validation_results)

    def test_3_validate_textures(self):
        """Test if texture validation runs without errors"""
        print()
        self.__create_test_texture_issues()

        # Set active object back to root
        bpy.context.view_layer.objects.active = self.root_object

        # Run validation using operator
        result = bpy.ops.mmd_tools.validate_textures()

        # Check if the operation completed
        self.assertEqual(set(result), {"FINISHED"})

        # Print validation results
        print("Texture validation results:")
        print(bpy.context.scene.mmd_validation_results)
        print()

        # Just verify it runs without errors, don't verify specific messages
        self.assertIsNotNone(bpy.context.scene.mmd_validation_results)

    def test_4_fix_bone_issues(self):
        """Test if bone issues fix function works"""
        print()
        self.__create_test_bone_with_invalid_name()

        # Set active object back to root
        bpy.context.view_layer.objects.active = self.root_object

        # First validate to get initial state
        bpy.ops.mmd_tools.validate_bone_limits()
        before_fix = bpy.context.scene.mmd_validation_results
        print("Before fix:")
        print(before_fix)
        print()

        # Run fix operation using operator
        result = bpy.ops.mmd_tools.fix_bone_issues()

        # Check if the operation completed
        self.assertEqual(set(result), {"FINISHED"})

        # Check the fix results
        fix_results = bpy.context.scene.mmd_validation_results
        print("Fix results:")
        print(fix_results)
        print()

        # Run validation again to see if issues were fixed
        bpy.ops.mmd_tools.validate_bone_limits()
        after_fix = bpy.context.scene.mmd_validation_results
        print("After fix:")
        print(after_fix)
        print()

        # Success if validation result is empty or says no issues found
        self.assertTrue("No bone issues found" in after_fix or not after_fix, f"Fix failed. After fix: {after_fix}")

    def test_5_fix_morph_issues(self):
        """Test if morph issues fix function works"""
        print()
        self.__create_test_morph_with_invalid_name()

        # Set active object back to root
        bpy.context.view_layer.objects.active = self.root_object

        # First validate to get initial state
        bpy.ops.mmd_tools.validate_morphs()
        before_fix = bpy.context.scene.mmd_validation_results
        print("Before fix:")
        print(before_fix)
        print()

        # Run fix operation using operator
        result = bpy.ops.mmd_tools.fix_morph_issues()

        # Check if the operation completed
        self.assertEqual(set(result), {"FINISHED"})

        # Check the fix results
        fix_results = bpy.context.scene.mmd_validation_results
        print("Fix results:")
        print(fix_results)
        print()

        # Run validation again to see if issues were fixed
        bpy.ops.mmd_tools.validate_morphs()
        after_fix = bpy.context.scene.mmd_validation_results
        print("After fix:")
        print(after_fix)
        print()

        # Success if validation result is empty or says no issues found
        self.assertTrue("No morph issues found" in after_fix or not after_fix, f"Fix failed. After fix: {after_fix}")

    def test_6_fix_texture_issues(self):
        """Test if texture issues fix function works"""
        print()
        self.__create_test_texture_issues()

        # Set active object back to root
        bpy.context.view_layer.objects.active = self.root_object

        # First validate to get initial state
        bpy.ops.mmd_tools.validate_textures()
        before_fix = bpy.context.scene.mmd_validation_results
        print("Before fix:")
        print(before_fix)
        print()

        # Run fix operation using operator
        result = bpy.ops.mmd_tools.fix_texture_issues()

        # Check if the operation completed
        self.assertEqual(set(result), {"FINISHED"})

        # Check the fix results
        fix_results = bpy.context.scene.mmd_validation_results
        print("Fix results:")
        print(fix_results)
        print()

        # Success if fix results contains expected message
        self.assertNotIn("No texture issues to fix", fix_results)
        self.assertIn("Fix texture filename conflict", fix_results)


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main()
