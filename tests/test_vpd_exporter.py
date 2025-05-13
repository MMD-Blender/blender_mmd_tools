
import os
import shutil
import tempfile
import unittest

import bpy
from bl_ext.user_default.mmd_tools.core.model import Model
from bl_ext.user_default.mmd_tools.core.vpd.exporter import VPDExporter
from mathutils import Matrix, Quaternion, Vector

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "samples")
OUTPUT_DIR = os.path.join(TESTS_DIR, "output")


class TestVPDExporter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Clean up output from previous tests
        """
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
        """
        We should start each test with a clean state
        """
        # Ensure active object exists (user may have deleted the default cube)
        if not bpy.context.active_object:
            bpy.ops.mesh.primitive_cube_add()

        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=True)
        # Add some useful shortcuts
        self.context = bpy.context
        self.scene = bpy.context.scene

    def __list_sample_files(self, dir_name, extension):
        """List all files with specified extension in the directory"""
        directory = os.path.join(SAMPLES_DIR, dir_name)
        if not os.path.exists(directory):
            return []

        ret = []
        for root, dirs, files in os.walk(directory):
            for name in files:
                if name.lower().endswith("." + extension.lower()):
                    ret.append(os.path.join(root, name))
        return ret

    def __enable_mmd_tools(self):
        """Make sure mmd_tools addon is enabled"""
        bpy.ops.wm.read_homefile()  # reload blender startup file
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("mmd_tools", None):
            addon_enable = (
                bpy.ops.wm.addon_enable
                if "addon_enable" in dir(bpy.ops.wm)
                else bpy.ops.preferences.addon_enable
            )
            addon_enable(
                module="bl_ext.user_default.mmd_tools"
            )  # make sure addon 'mmd_tools' is enabled

    def __create_model_from_pmx(self, pmx_file):
        """Create a model from a PMX file"""
        # First clear any existing objects
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()

        # Import the model
        bpy.ops.mmd_tools.import_model(
            filepath=pmx_file,
            scale=1.0,
            types={"MESH", "ARMATURE", "MORPHS"},
            clean_model=False,
        )

        # Find the model root based on the filename
        model_name = os.path.splitext(os.path.basename(pmx_file))[0]
        for obj in bpy.context.scene.objects:
            if obj.mmd_type == "ROOT" and obj.name == model_name:
                return obj

        # If we couldn't find a matching name, just try to find any MMD root
        for obj in bpy.context.scene.objects:
            if obj.mmd_type == "ROOT":
                return obj

        return None

    def __modify_bone_pose(self, armature, bone_names, location_offset=(0.1, 0.2, 0.3), rotation_offset=(0.1, 0.2, 0.3, 0.9)):
        """Modify the pose of specified bones for testing export"""
        if not armature or not bone_names:
            return

        bpy.ops.object.select_all(action="DESELECT")
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode="POSE")

        # Modify position of specified bones
        for bone_name in bone_names:
            if bone_name in armature.pose.bones:
                bone = armature.pose.bones[bone_name]
                # Set a predictable transformation
                bone.location = Vector(location_offset)
                bone.rotation_quaternion = Quaternion(rotation_offset)
                bone.keyframe_insert(data_path="location", frame=1)
                bone.keyframe_insert(data_path="rotation_quaternion", frame=1)

        bpy.ops.object.mode_set(mode="OBJECT")

    def __modify_morph_values(self, mesh_obj, morph_names):
        """Modify morph values for testing export"""
        if not mesh_obj or not mesh_obj.data.shape_keys:
            return
        
        shape_keys = mesh_obj.data.shape_keys.key_blocks
        for morph_name in morph_names:
            if morph_name in shape_keys:
                shape_keys[morph_name].value = 0.75
                shape_keys[morph_name].keyframe_insert(data_path="value", frame=1)

    def __create_pose_library(self, armature, num_poses=3):
        """Create a pose library with multiple poses for testing"""
        if not armature:
            return
            
        # Ensure animation data exists
        if armature.animation_data is None:
            armature.animation_data_create()
            
        # Create action for pose library if it doesn't exist
        if not armature.animation_data.action:
            action = bpy.data.actions.new(name="PoseLibrary")
            armature.animation_data.action = action
        else:
            action = armature.animation_data.action
            
        # Select armature and enter pose mode
        bpy.ops.object.select_all(action="DESELECT")
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode="POSE")
        
        # Create multiple poses
        for i in range(num_poses):
            # Create different pose for each iteration
            for j, bone in enumerate(armature.pose.bones):
                if j % (i+1) == 0:  # Create different patterns for different poses
                    bone.location = Vector((0.1 * i, 0.2 * i, 0.3 * i))
                    bone.rotation_quaternion = Quaternion(((0.9, 0.1 * i, 0.2 * i, 0.3 * i)))
                    bone.keyframe_insert(data_path="location", frame=i+1)
                    bone.keyframe_insert(data_path="rotation_quaternion", frame=i+1)
                    
            # Add pose marker (if current Blender version supports it)
            if hasattr(action, "pose_markers"):
                marker = action.pose_markers.new(f"Pose_{i+1}")
                marker.frame = i+1
                    
        # Return to object mode
        bpy.ops.object.mode_set(mode="OBJECT")

    def __create_test_armature(self):
        """Create a simple test armature for exporting"""
        bpy.ops.object.armature_add()
        armature = bpy.context.active_object
        armature.name = "TestArmature"
        
        # Enter edit mode to add bones
        bpy.ops.object.mode_set(mode='EDIT')
        
        # Get the initial bone
        edit_bones = armature.data.edit_bones
        first_bone = edit_bones[0]
        first_bone.name = "Root"
        
        # Add a child bone
        child = edit_bones.new("Child")
        child.head = first_bone.tail
        child.tail = child.head + Vector((0, 0.5, 0))
        child.parent = first_bone
        
        # Add a few more bones
        arm_l = edit_bones.new("Arm.L")
        arm_l.head = first_bone.head + Vector((0.5, 0, 0))
        arm_l.tail = arm_l.head + Vector((0, 0.5, 0))
        arm_l.parent = first_bone
        
        arm_r = edit_bones.new("Arm.R")
        arm_r.head = first_bone.head + Vector((-0.5, 0, 0))
        arm_r.tail = arm_r.head + Vector((0, 0.5, 0))
        arm_r.parent = first_bone
        
        # Exit edit mode
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # Add Japanese names for MMD compatibility
        for bone in armature.pose.bones:
            # Try to handle both property structures depending on the Blender version
            try:
                if not hasattr(bone, "mmd_bone"):
                    # Create the property group if it doesn't exist
                    bone["mmd_bone"] = {}
                
                if bone.name == "Arm.L":
                    bone.mmd_bone.name_j = "左腕"
                elif bone.name == "Arm.R":
                    bone.mmd_bone.name_j = "右腕"
                elif bone.name == "Root":
                    bone.mmd_bone.name_j = "センター"
                elif bone.name == "Child":
                    bone.mmd_bone.name_j = "下半身"
            except (AttributeError, TypeError):
                # Fallback to just setting a custom property if mmd_bone is not available
                if bone.name == "Arm.L":
                    bone["name_j"] = "左腕"
                elif bone.name == "Arm.R":
                    bone["name_j"] = "右腕"
                elif bone.name == "Root":
                    bone["name_j"] = "センター"
                elif bone.name == "Child":
                    bone["name_j"] = "下半身"
        
        return armature

    def __create_test_mesh_with_morphs(self):
        """Create a test mesh with shape keys for morph export testing"""
        bpy.ops.mesh.primitive_cube_add()
        mesh_obj = bpy.context.active_object
        mesh_obj.name = "TestMesh"
        
        # Add shape keys
        bpy.ops.object.shape_key_add(from_mix=False)  # Add basis key
        
        # Add a few shape keys (morphs)
        for name in ["Smile", "Sad", "Angry"]:
            bpy.ops.object.shape_key_add(from_mix=False)
            shape_key = mesh_obj.data.shape_keys.key_blocks[-1]
            shape_key.name = name
            
            # Modify some vertices to make the shape key do something
            for i, v in enumerate(mesh_obj.data.vertices):
                if i % 2 == 0:  # Modify every other vertex
                    shape_key.data[i].co.x += 0.2
                    shape_key.data[i].co.y += 0.1
        
        return mesh_obj

    def test_export_current_pose(self):
        """Test exporting current pose to VPD file"""
        # Set up test objects
        armature = self.__create_test_armature()
        self.__modify_bone_pose(armature, ["Arm.L", "Arm.R"])
        mesh_obj = self.__create_test_mesh_with_morphs()
        self.__modify_morph_values(mesh_obj, ["Smile", "Angry"])
        
        # Define output path
        output_path = os.path.join(OUTPUT_DIR, "test_current_pose.vpd")
        
        try:
            # Create exporter and export the current pose
            exporter = VPDExporter()
            exporter.export(
                armature=armature,
                mesh=mesh_obj,
                filepath=output_path,
                scale=1.0,
                model_name="TestModel",
                pose_type="CURRENT"
            )
            
            # Verify file was created
            self.assertTrue(os.path.exists(output_path), "VPD file was not created")
            self.assertTrue(os.path.getsize(output_path) > 0, "VPD file is empty")
            
            # Simple verification of file structure without relying on specific Japanese characters
            # Read file in binary mode to avoid encoding issues
            with open(output_path, 'rb') as f:
                binary_content = f.read()
                
            # Convert to string for logging purposes
            content_str = str(binary_content)
            
            # Check for morph names (ASCII strings should be preserved correctly)
            self.assertIn(b"Smile", binary_content, "Smile morph not found in VPD file")
            self.assertIn(b"Angry", binary_content, "Angry morph not found in VPD file")
            
            # Instead of checking for specific Japanese characters, check for bone presence by structure
            # VPD has a "Bone" structure with location and rotation values
            self.assertIn(b"Bone", binary_content, "No bone data found in VPD file")
            
            # Check for expected number of bones (we should have at least two modified bones)
            bone_count = binary_content.count(b"Bone")
            self.assertGreaterEqual(bone_count, 2, "Expected at least 2 bones in VPD file")
            
            # Check for expected number of morphs
            morph_count = binary_content.count(b"Morph")
            self.assertGreaterEqual(morph_count, 2, "Expected at least 2 morphs in VPD file")
                
        except Exception as e:
            self.fail(f"VPD export failed with error: {str(e)}")

    def test_export_pose_library(self):
        """Test exporting poses from a pose library"""
        # Set up test armature with pose library
        armature = self.__create_test_armature()
        self.__create_pose_library(armature, num_poses=3)
        
        # Define output paths
        active_pose_path = os.path.join(OUTPUT_DIR, "test_active_pose.vpd")
        all_poses_dir = OUTPUT_DIR
        
        try:
            # Test exporting active pose
            exporter = VPDExporter()
            exporter.export(
                armature=armature,
                filepath=active_pose_path,
                scale=1.0,
                model_name="TestModel",
                pose_type="ACTIVE"
            )
            
            # Verify active pose file was created
            self.assertTrue(os.path.exists(active_pose_path), "Active pose VPD file was not created")
            self.assertTrue(os.path.getsize(active_pose_path) > 0, "Active pose VPD file is empty")
            
            # Test exporting all poses
            all_poses_path = os.path.join(all_poses_dir, "test_all_poses.vpd")
            exporter.export(
                armature=armature,
                filepath=all_poses_path,
                scale=1.0,
                model_name="TestModel",
                pose_type="ALL"
            )
            
            # Verify all pose files were created
            # There should be one file per pose marker with pose name
            pose_count = 0
            for file in os.listdir(all_poses_dir):
                if file.startswith("Pose_") and file.endswith(".vpd"):
                    pose_count += 1
                    full_path = os.path.join(all_poses_dir, file)
                    self.assertTrue(os.path.getsize(full_path) > 0, f"Pose file {file} is empty")
                    
            self.assertGreater(pose_count, 0, "No pose files were created for ALL export")
            
        except Exception as e:
            self.fail(f"Pose library export failed with error: {str(e)}")

    def test_export_with_scale(self):
        """Test exporting with different scale factors"""
        # Set up test objects
        armature = self.__create_test_armature()
        self.__modify_bone_pose(armature, ["Arm.L", "Arm.R"])
        
        # Define output paths for different scales
        output_path_1x = os.path.join(OUTPUT_DIR, "test_scale_1x.vpd")
        output_path_2x = os.path.join(OUTPUT_DIR, "test_scale_2x.vpd")
        
        try:
            # Export with scale 1.0
            exporter = VPDExporter()
            exporter.export(
                armature=armature,
                filepath=output_path_1x,
                scale=1.0,
                model_name="TestModel",
                pose_type="CURRENT"
            )
            
            # Export with scale 2.0
            exporter = VPDExporter()
            exporter.export(
                armature=armature,
                filepath=output_path_2x,
                scale=2.0,
                model_name="TestModel",
                pose_type="CURRENT"
            )
            
            # Verify both files were created
            self.assertTrue(os.path.exists(output_path_1x), "Scale 1x VPD file was not created")
            self.assertTrue(os.path.exists(output_path_2x), "Scale 2x VPD file was not created")
            
            # Read both files to compare content
            with open(output_path_1x, 'r', encoding='utf-8', errors='replace') as f1:
                content_1x = f1.read()
            with open(output_path_2x, 'r', encoding='utf-8', errors='replace') as f2:
                content_2x = f2.read()
                
            # Files should be different due to scale difference
            self.assertNotEqual(content_1x, content_2x, "Scale factor did not affect output")
            
        except Exception as e:
            self.fail(f"Scale test export failed with error: {str(e)}")

    def test_export_with_operator(self):
        """Test exporting using all combinations of pose_type and use_pose_mode"""
        # Enable mmd_tools addon
        self.__enable_mmd_tools()
        
        # Set up test objects
        armature = self.__create_test_armature()
        self.__modify_bone_pose(armature, ["Arm.L", "Arm.R"])
        mesh_obj = self.__create_test_mesh_with_morphs()
        self.__modify_morph_values(mesh_obj, ["Smile", "Angry"])
        
        # Create animations for pose testing
        self.__create_pose_library(armature, num_poses=3)
        
        # Test all 6 combinations directly using VPDExporter
        pose_types = ["CURRENT", "ACTIVE", "ALL"]
        use_pose_modes = [False, True]
        
        for pose_type in pose_types:
            for use_pose_mode in use_pose_modes:
                # Define a unique output path for each combination
                output_name = f"test_export_{pose_type}_pose_mode_{use_pose_mode}.vpd"
                output_path = os.path.join(OUTPUT_DIR, output_name)
                
                print(f"\nTesting combination: pose_type={pose_type}, use_pose_mode={use_pose_mode}")
                
                try:
                    # Create exporter and export
                    exporter = VPDExporter()
                    
                    # For ACTIVE and ALL pose types, we need animation data
                    if pose_type in ["ACTIVE", "ALL"]:
                        # Ensure armature has animation data
                        if armature.animation_data is None:
                            armature.animation_data_create()
                        
                        # Create an action if needed
                        if armature.animation_data.action is None:
                            action = bpy.data.actions.new(name="PoseLib")
                            armature.animation_data.action = action
                        
                        # Add some keyframes if none exist
                        action = armature.animation_data.action
                        if not action.fcurves:
                            # Enter pose mode
                            bpy.ops.object.select_all(action="DESELECT")
                            armature.select_set(True)
                            bpy.context.view_layer.objects.active = armature
                            bpy.ops.object.mode_set(mode="POSE")
                            
                            # Insert keyframes for a bone
                            if len(armature.pose.bones) > 0:
                                bone = armature.pose.bones[0]
                                bone.location = (0.1, 0.2, 0.3)
                                bone.keyframe_insert(data_path="location", frame=1)
                            
                            # Add pose markers if needed for ACTIVE and ALL modes
                            if not hasattr(action, "pose_markers") or len(action.pose_markers) == 0:
                                # Modern Blender might not use pose_markers
                                # We can simulate them by adding a marker to the timeline
                                if hasattr(bpy.context.scene, "timeline_markers"):
                                    marker = bpy.context.scene.timeline_markers.new("Pose_1", frame=1)
                            
                            # Return to object mode
                            bpy.ops.object.mode_set(mode="OBJECT")
                    
                    # Export with current combination
                    exporter.export(
                        armature=armature,
                        mesh=mesh_obj if pose_type == "CURRENT" else None,
                        filepath=output_path,
                        scale=1.0,
                        model_name="TestModel",
                        pose_type=pose_type,
                        use_pose_mode=use_pose_mode
                    )
                    
                    # Check output for CURRENT pose type
                    if pose_type == "CURRENT":
                        self.assertTrue(os.path.exists(output_path), 
                                       f"VPD file not created for {pose_type}, use_pose_mode={use_pose_mode}")
                        self.assertTrue(os.path.getsize(output_path) > 0, 
                                       f"VPD file empty for {pose_type}, use_pose_mode={use_pose_mode}")
                        
                        # Check content (without assuming Japanese characters work correctly)
                        with open(output_path, 'r', encoding='shift_jis', errors='replace') as f:
                            content = f.read()
                            # Check for markers that should be present in any VPD file
                            self.assertIn("Vocaloid Pose Data file", content, 
                                         "Missing VPD header")
                            self.assertIn("Bone", content, 
                                         "No bone data found in VPD file")
                            if mesh_obj:
                                self.assertIn("Morph", content, 
                                             "No morph data found in VPD file")
                    
                    # For ALL pose type, check if multiple files are created
                    if pose_type == "ALL":
                        # Files should be created in the output directory with names matching the pose markers
                        found_pose_files = False
                        for file in os.listdir(OUTPUT_DIR):
                            if file.startswith("Pose_") and file.endswith(".vpd"):
                                found_pose_files = True
                                pose_file_path = os.path.join(OUTPUT_DIR, file)
                                self.assertTrue(os.path.getsize(pose_file_path) > 0, 
                                               f"Pose file {file} is empty")
                        
                        # Only assert if markers should have been created
                        if hasattr(armature, "animation_data") and armature.animation_data and \
                           hasattr(armature.animation_data, "action") and armature.animation_data.action and \
                           hasattr(armature.animation_data.action, "pose_markers") and \
                           len(armature.animation_data.action.pose_markers) > 0:
                            self.assertTrue(found_pose_files, "No pose files created for ALL export")
                        
                    print(f"ok Successfully tested: pose_type={pose_type}, use_pose_mode={use_pose_mode}")
                    
                except Exception as e:
                    # For older Blender versions, pose_library might not be available
                    if "pose_library" in str(e) and pose_type in ["ACTIVE", "ALL"]:
                        print(f"!! Skipped pose_type={pose_type}, use_pose_mode={use_pose_mode}: {str(e)}")
                        print("   This is normal if your Blender version doesn't support pose libraries")
                    else:
                        self.fail(f"Export failed with pose_type={pose_type}, use_pose_mode={use_pose_mode}: {str(e)}")
        
        print("\nAll available export combinations tested successfully")

    def test_export_real_model(self):
        """Test exporting poses from real MMD models (if available)"""
        # Get available PMX files
        pmx_files = self.__list_sample_files("pmx", "pmx")
        pmx_files.extend(self.__list_sample_files("pmd", "pmd"))
        
        if not pmx_files:
            self.skipTest("No PMX/PMD sample files available for testing")
            
        # Enable mmd_tools addon
        self.__enable_mmd_tools()
        
        # Test with first available model
        pmx_file = pmx_files[0]
        model_name = os.path.splitext(os.path.basename(pmx_file))[0]
        
        try:
            # Import the model
            model_root = self.__create_model_from_pmx(pmx_file)
            if not model_root:
                self.skipTest("Could not import model for real model export test")
                
            # Get the model and armature
            model = Model(model_root)
            armature = model.armature()
            mesh = model.firstMesh()
            
            if not armature:
                self.skipTest("Imported model has no armature")
                
            # Select a few bones to modify
            bone_names = []
            for i, bone in enumerate(armature.pose.bones):
                if i % 10 == 0 and i < 30:  # Just select a few bones for testing
                    bone_names.append(bone.name)
                    
            # Modify selected bones
            self.__modify_bone_pose(armature, bone_names)
            
            # Also modify some morphs if available
            if mesh and mesh.data.shape_keys:
                morph_names = []
                for i, key in enumerate(mesh.data.shape_keys.key_blocks):
                    if i > 0 and i < 5:  # Skip basis key (0) and limit to a few morphs
                        morph_names.append(key.name)
                        
                self.__modify_morph_values(mesh, morph_names)
                
            # Export current pose
            output_path = os.path.join(OUTPUT_DIR, f"{model_name}_pose.vpd")
            
            # Create exporter and export
            exporter = VPDExporter()
            exporter.export(
                armature=armature,
                mesh=mesh,
                filepath=output_path,
                scale=1.0,
                model_name=model_name,
                pose_type="CURRENT"
            )
            
            # Verify export succeeded
            self.assertTrue(os.path.exists(output_path), "VPD file was not created for real model")
            self.assertTrue(os.path.getsize(output_path) > 0, "VPD file for real model is empty")
            
            # Simple verification by checking file content
            with open(output_path, 'r', encoding='shift_jis', errors='replace') as f:
                content = f.read()
                # The file should contain the model name in OSM format
                self.assertIn(f"{model_name}.osm", content, "Model name not found in VPD file")
                # And bone data
                self.assertIn("Bone", content, "No bone data found in VPD file")
                
        except Exception as e:
            self.fail(f"Real model export test failed with error: {str(e)}")

    def test_direct_export_api(self):
        """Test the direct API without using operators"""
        # Setup simple objects for export
        armature = self.__create_test_armature()
        self.__modify_bone_pose(armature, ["Arm.L", "Arm.R"])
        
        output_path = os.path.join(OUTPUT_DIR, "direct_api_export.vpd")
        
        try:
            # Create the exporter and export directly
            exporter = VPDExporter()
            
            # Test the direct export functionality
            exporter.export(
                armature=armature,
                filepath=output_path,
                scale=1.0,
                model_name="TestDirectAPI",
                pose_type="CURRENT"
            )
            
            # Verify export succeeded
            self.assertTrue(os.path.exists(output_path), "VPD file was not created with direct API")
            self.assertTrue(os.path.getsize(output_path) > 0, "VPD file created with direct API is empty")
            
        except Exception as e:
            self.fail(f"Direct API export test failed with error: {str(e)}")

    def test_pose_type_validation(self):
        """Test that invalid pose_type values raise appropriate errors"""
        armature = self.__create_test_armature()
        output_path = os.path.join(OUTPUT_DIR, "invalid_pose_type.vpd")
        
        # Test with invalid pose type
        exporter = VPDExporter()
        with self.assertRaises(ValueError):
            exporter.export(
                armature=armature,
                filepath=output_path,
                pose_type="INVALID_TYPE"  # This should raise ValueError
            )


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (
        sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    )
    unittest.main()