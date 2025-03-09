import unittest
import os
import re
from unittest.mock import patch, MagicMock

import bpy

from bl_ext.user_default.mmd_tools.utils import (
    selectAObject, enterEditMode, setParentToBone, selectSingleBone,
    convertNameToLR, convertLRToName, mergeVertexGroup, separateByMaterials,
    clearUnusedMeshes, makePmxBoneMap, unique_name, int2base, saferelpath,
    ItemOp, ItemMoveOp, deprecated, warn_deprecation
)


class TestUtilsUnit(unittest.TestCase):

    def setUp(self):
        """
        We should start each test with a clean state
        """
        # Ensure active object exists (user may have deleted the default cube)
        if not bpy.context.active_object:
            bpy.ops.mesh.primitive_cube_add()

        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=True)
        # Add some useful shortcuts
        self.context = bpy.context
        self.scene = bpy.context.scene

    def test_selectAObject(self):
        """
        Test if selectAObject correctly selects and activates an object
        """
        # Create test objects
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        cube.name = 'TestCube'
        
        bpy.ops.mesh.primitive_plane_add()
        plane = bpy.context.active_object
        plane.name = 'TestPlane'
        
        # Deselect all objects first
        bpy.ops.object.select_all(action='DESELECT')
        self.assertFalse(cube.select_get(), "Cube should be deselected initially")
        self.assertFalse(plane.select_get(), "Plane should be deselected initially")
        
        # Test selecting the cube
        selectAObject(cube)
        self.assertTrue(cube.select_get(), "Cube should be selected after selectAObject")
        self.assertFalse(plane.select_get(), "Plane should remain deselected")
        self.assertEqual(bpy.context.active_object, cube, "Cube should be the active object")
        
        # Test selecting the plane
        selectAObject(plane)
        self.assertFalse(cube.select_get(), "Cube should be deselected")
        self.assertTrue(plane.select_get(), "Plane should be selected after selectAObject")
        self.assertEqual(bpy.context.active_object, plane, "Plane should be the active object")

    def test_enterEditMode(self):
        """
        Test if enterEditMode correctly enters edit mode for an object
        """
        # Create a test object
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        cube.name = 'TestCube'
        
        # Start in object mode
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # Test entering edit mode
        enterEditMode(cube)
        self.assertEqual(cube.mode, 'EDIT', "Object should be in EDIT mode")
        self.assertEqual(bpy.context.active_object, cube, "Cube should be the active object")
        
        # Test that it works when already in edit mode
        enterEditMode(cube)
        self.assertEqual(cube.mode, 'EDIT', "Object should remain in EDIT mode")

    def test_setParentToBone(self):
        """
        Test if setParentToBone correctly sets an object's parent to a bone
        """
        # Create an armature
        bpy.ops.object.armature_add()
        armature = bpy.context.active_object
        armature.name = 'TestArmature'
        
        # Create a mesh object to parent
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        cube.name = 'TestCube'
        
        # Test parenting
        bone_name = armature.data.bones[0].name
        setParentToBone(cube, armature, bone_name)
        
        # Check if parenting was successful
        self.assertEqual(cube.parent, armature, "Armature should be the parent of the cube")
        self.assertEqual(cube.parent_bone, bone_name, "Cube should be parented to the bone")
        self.assertEqual(cube.parent_type, 'BONE', "Parent type should be BONE")

    def test_selectSingleBone(self):
        """
        Test if selectSingleBone correctly selects a single bone
        """
        # Create an armature with multiple bones
        bpy.ops.object.armature_add()
        armature = bpy.context.active_object
        armature.name = 'TestArmature'
        
        # Enter edit mode to add more bones
        bpy.ops.object.mode_set(mode='EDIT')
        # Add a second bone
        bpy.ops.armature.bone_primitive_add()
        bone_names = [bone.name for bone in armature.data.bones]
        
        # Back to object mode
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # Test bone selection
        target_bone = bone_names[0]
        selectSingleBone(self.context, armature, target_bone)
        
        # Check if the bone is selected and active
        bpy.ops.object.mode_set(mode='POSE')
        self.assertTrue(armature.data.bones[target_bone].select, "Target bone should be selected")
        self.assertEqual(armature.data.bones.active, armature.data.bones[target_bone], "Target bone should be active")
        
        # Check if other bones are not selected
        for bone_name in bone_names:
            if bone_name != target_bone:
                self.assertFalse(armature.data.bones[bone_name].select, f"Bone {bone_name} should not be selected")

    def test_convertNameToLR(self):
        """
        Test if convertNameToLR correctly converts Japanese left/right naming to Blender's L/R convention
        """
        # Test cases
        test_cases = [
            ('左腕', '腕.L'),  # Left arm
            ('右腕', '腕.R'),  # Right arm
            ('左足首', '足首.L'),  # Left ankle
            ('右足首', '足首.R'),  # Right ankle
            ('胴体', '胴体'),  # Torso (no conversion needed)
            ('頭', '頭')       # Head (no conversion needed)
        ]
        
        # Test with default delimiter (dot)
        for input_name, expected_output in test_cases:
            self.assertEqual(convertNameToLR(input_name), expected_output, f"Failed to convert {input_name}")
        
        # Test with underscore delimiter
        self.assertEqual(convertNameToLR('左腕', True), '腕_L', "Failed to convert with underscore")
        self.assertEqual(convertNameToLR('右腕', True), '腕_R', "Failed to convert with underscore")

    def test_convertLRToName(self):
        """
        Test if convertLRToName correctly converts Blender's L/R convention to Japanese left/right naming
        """
        # Test cases
        test_cases = [
            ('腕.L', '左腕'),  # Left arm
            ('腕.R', '右腕'),  # Right arm
            ('足首.L', '左足首'),  # Left ankle
            ('足首.R', '右足首'),  # Right ankle
            ('腕_L', '左腕'),  # Left arm with underscore
            ('腕_R', '右腕'),  # Right arm with underscore
            ('胴体', '胴体'),  # Torso (no conversion needed)
            ('頭', '頭')       # Head (no conversion needed)
        ]
        
        for input_name, expected_output in test_cases:
            self.assertEqual(convertLRToName(input_name), expected_output, f"Failed to convert {input_name}")

    def test_mergeVertexGroup(self):
        """
        Test if mergeVertexGroup correctly merges two vertex groups
        """
        # Create a mesh object with vertex groups
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        
        # Add vertex groups
        vg1 = cube.vertex_groups.new(name="SourceGroup")
        vg2 = cube.vertex_groups.new(name="DestGroup")
        
        # Assign vertices to groups
        vg1.add([0, 1, 2], 1.0, 'REPLACE')
        vg2.add([3, 4], 0.5, 'REPLACE')
        
        # Merge vertex groups
        mergeVertexGroup(cube, "SourceGroup", "DestGroup")
        
        # Check if vertices from source group were added to destination group
        for v_idx in [0, 1, 2]:
            weight = 0
            for g in cube.data.vertices[v_idx].groups:
                if g.group == vg2.index:
                    weight = g.weight
                    break
            self.assertAlmostEqual(weight, 1.0, places=4, msg=f"Vertex {v_idx} should have weight 1.0 in DestGroup")

    def test_separateByMaterials(self):
        """
        Test if separateByMaterials correctly separates a mesh by materials
        """
        # Create a mesh object with multiple materials
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        
        # Add materials
        mat1 = bpy.data.materials.new(name="Material1")
        mat2 = bpy.data.materials.new(name="Material2")
        cube.data.materials.append(mat1)
        cube.data.materials.append(mat2)
        
        # Assign materials to different faces
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # Assign first half of faces to material 0, second half to material 1
        for i, polygon in enumerate(cube.data.polygons):
            polygon.material_index = 0 if i < len(cube.data.polygons) // 2 else 1
        
        # Separate by materials
        num_objects_before = len(bpy.data.objects)
        separateByMaterials(cube)
        num_objects_after = len(bpy.data.objects)
        
        # Check if separation occurred
        self.assertGreater(num_objects_after, num_objects_before, "Object should have been separated")
        
        # Check if objects have the expected materials
        material_names = {"Material1", "Material2"}
        separated_objects = [obj for obj in bpy.data.objects if obj.type == 'MESH' and obj != cube]
        
        self.assertGreaterEqual(len(separated_objects), 1, "Should have at least one separated object")
        
        # Check each object has exactly one material
        for obj in separated_objects:
            self.assertEqual(len(obj.data.materials), 1, "Separated object should have exactly one material")
            self.assertIn(obj.data.materials[0].name, material_names, f"Unexpected material: {obj.data.materials[0].name}")

    def test_clearUnusedMeshes(self):
        """
        Test if clearUnusedMeshes correctly removes unused meshes
        """
        # Create mesh with no users
        mesh1 = bpy.data.meshes.new(name="UnusedMesh")
        mesh_name = mesh1.name
        
        # Create mesh with a user
        bpy.ops.mesh.primitive_cube_add()
        cube = bpy.context.active_object
        mesh2 = cube.data
        mesh2.name = "UsedMesh"
        
        # Clear unused meshes
        clearUnusedMeshes()
        
        # Check if unused mesh was removed
        self.assertNotIn(mesh_name, bpy.data.meshes, "Unused mesh should have been removed")
        self.assertIn(mesh2.name, bpy.data.meshes, "Used mesh should still exist")

    def test_makePmxBoneMap(self):
        """
        Test if makePmxBoneMap correctly creates a mapping from Japanese bone names to pose bones
        """
        # Create an armature
        bpy.ops.object.armature_add()
        armature = bpy.context.active_object
        
        # Set up bone properties
        bpy.ops.object.mode_set(mode='POSE')
        bone = armature.pose.bones[0]
        bone.name = "Bone"
        
        # Create a bone with name_j property
        try:
            bone.mmd_bone.name_j = "骨"  # Japanese for "bone"
        except AttributeError:
            # If mmd_bone is not available, set custom property
            bone["name_j"] = "骨"
        
        # Create bone map
        bone_map = makePmxBoneMap(armature)
        
        # Check if mapping was correctly created
        if hasattr(bone, 'mmd_bone'):
            self.assertIn("骨", bone_map, "Japanese bone name should be in the map")
            self.assertEqual(bone_map["骨"], bone, "Mapped bone should be the original bone")
        else:
            # Test with custom property
            self.assertIn("骨", bone_map, "Japanese bone name should be in the map")
            self.assertEqual(bone_map["骨"], bone, "Mapped bone should be the original bone")

    def test_unique_name(self):
        """
        Test if unique_name correctly generates unique names
        """
        used_names = {"test", "test.001", "other"}
        
        # Test with a name that doesn't exist yet
        unique = unique_name("new", used_names)
        self.assertEqual(unique, "new", "Should return the original name if not used")
        
        # Test with a name that already exists
        unique = unique_name("test", used_names)
        self.assertEqual(unique, "test.002", "Should find the next available numeric suffix")
        
        # Test with a name that exists with a suffix
        unique = unique_name("test.001", used_names)
        self.assertEqual(unique, "test.002", "Should increment the suffix")

    def test_int2base(self):
        """
        Test if int2base correctly converts integers to different bases
        """
        # Test cases
        test_cases = [
            (10, 2, "1010"),      # Decimal to binary
            (10, 16, "A"),        # Decimal to hex
            (255, 16, "FF"),      # Decimal to hex
            (9, 3, "100"),        # Decimal to base 3
            (-10, 16, "-A"),      # Negative number
            (0, 10, "0"),         # Zero
        ]
        
        for input_int, base, expected_output in test_cases:
            self.assertEqual(int2base(input_int, base), expected_output, f"Failed to convert {input_int} to base {base}")
        
        # Test with width parameter
        self.assertEqual(int2base(10, 16, 4), "000A", "Failed to pad with zeros")

    def test_saferelpath(self):
        """
        Test if saferelpath correctly handles relative paths across drives
        """
        # Test normal relative path (same drive)
        if os.name == 'posix':  # Unix-like system
            self.assertEqual(saferelpath("/a/b/c/file.txt", "/a/b"), "c/file.txt", "Failed to get relative path")
        
        # Test with different strategies
        base_path = os.path.basename("path/to/file.txt")
        self.assertEqual(saferelpath("path/to/file.txt", "different/path", "inside"), base_path, 
                        "Inside strategy should return basename")
        
        # Use os.path.relpath for the expected result of "outside" strategy
        # This is what the implementation actually returns when drives are the same
        expected_outside = os.path.relpath("path/to/file.txt", "different/path") if os.name != 'nt' or not os.path.splitdrive("path/to/file.txt")[0] else ".." + os.sep + base_path
        self.assertEqual(saferelpath("path/to/file.txt", "different/path", "outside"), 
                        expected_outside, "Outside strategy should return proper relative path")
        
        # Test absolute strategy
        if os.name == 'posix':  # Unix-like system
            full_path = os.path.abspath("path/to/file.txt")
            self.assertEqual(saferelpath("path/to/file.txt", "different/path", "absolute"), full_path, 
                            "Absolute strategy should return absolute path")

    def test_ItemOp_get_by_index(self):
        """
        Test if ItemOp.get_by_index correctly retrieves items by index
        """
        items = ["item1", "item2", "item3"]
        
        # Test valid indices
        self.assertEqual(ItemOp.get_by_index(items, 0), "item1", "Failed to get first item")
        self.assertEqual(ItemOp.get_by_index(items, 2), "item3", "Failed to get last item")
        
        # Test invalid indices
        self.assertIsNone(ItemOp.get_by_index(items, -1), "Should return None for negative index")
        self.assertIsNone(ItemOp.get_by_index(items, 3), "Should return None for out of range index")

    def test_deprecated_decorator(self):
        """
        Test if the deprecated decorator correctly marks functions as deprecated
        """
        # Create a test function with the deprecated decorator
        @deprecated(deprecated_in="1.0.0", details="Use new_function instead")
        def old_function():
            return "result"
        
        # Mock the logging module to capture warnings
        with patch('logging.warning') as mock_warning:
            # Call the deprecated function
            result = old_function()
            
            # Check if function still works
            self.assertEqual(result, "result", "Deprecated function should still return its result")
            
            # Check if warning was logged
            mock_warning.assert_called_once()
            args = mock_warning.call_args[0]
            self.assertEqual(args[0], "%s is deprecated%s%s", "Warning format string should match")
            self.assertEqual(args[1], "old_function", "Function name should be passed as argument")
            self.assertIn("1.0.0", args[2], "Warning should mention version")
            self.assertIn("Use new_function instead", args[3], "Warning should include details")


if __name__ == '__main__':
    import sys
    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    unittest.main()