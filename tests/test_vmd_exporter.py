# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import logging
import math
import os
import shutil
import traceback
import unittest

import bpy
from bl_ext.blender_org.mmd_tools.core import vmd
from bl_ext.blender_org.mmd_tools.core.model import Model
from mathutils import Quaternion, Vector

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "samples")


class TestVmdExporter(unittest.TestCase):
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

    # ********************************************
    # Utils
    # ********************************************

    def __vector_error(self, vec0, vec1):
        return (Vector(vec0) - Vector(vec1)).length

    def __quaternion_error(self, quat0, quat1):
        # Convert lists to quaternions if needed
        if isinstance(quat0, (list, tuple)):
            q0 = Quaternion((quat0[3], quat0[0], quat0[1], quat0[2]))  # (x,y,z,w) to (w,x,y,z)
        else:
            q0 = quat0

        if isinstance(quat1, (list, tuple)):
            q1 = Quaternion((quat1[3], quat1[0], quat1[1], quat1[2]))  # (x,y,z,w) to (w,x,y,z)
        else:
            q1 = quat1

        angle = q0.rotation_difference(q1).angle % math.pi
        assert angle >= 0
        return min(angle, math.pi - angle)

    def __list_sample_files(self, file_types):
        ret = []
        for file_type in file_types:
            file_ext = "." + file_type
            for root, dirs, files in os.walk(os.path.join(SAMPLES_DIR, file_type)):
                ret.extend(os.path.join(root, name) for name in files if name.lower().endswith(file_ext))
        return ret

    def __enable_mmd_tools(self):
        bpy.ops.wm.read_homefile(use_empty=True)
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.blender_org.mmd_tools")  # make sure addon 'mmd_tools' is enabled

    def __get_largest_pmx_file(self):
        """Get the largest PMX file from samples"""
        pmx_files = self.__list_sample_files(["pmx", "pmd"])
        if not pmx_files:
            return None

        # Get file sizes and find the largest
        file_sizes = [(filepath, os.path.getsize(filepath)) for filepath in pmx_files]
        file_sizes.sort(key=lambda x: x[1], reverse=True)

        return file_sizes[0][0]  # Return the largest file path

    def __import_largest_pmx_model(self):
        """Import the largest PMX model and return the root object"""
        largest_pmx = self.__get_largest_pmx_file()
        if not largest_pmx:
            self.fail("No PMX sample files found")

        print(f"\nImporting largest PMX model: {largest_pmx}")

        # Clear the scene
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)

        try:
            # Use MMD Tools importer to import PMX
            bpy.ops.mmd_tools.import_model(filepath=largest_pmx, types={"MESH", "ARMATURE", "PHYSICS", "DISPLAY", "MORPHS"}, scale=0.08, clean_model=False, remove_doubles=False, log_level="ERROR")

            # Update scene
            bpy.context.view_layer.update()

            # Find the root object
            root_obj = None
            for obj in bpy.context.scene.objects:
                if obj.mmd_type == "ROOT":
                    root_obj = obj
                    break

            if not root_obj:
                self.fail("Failed to find root object after PMX import")

            # Use Model class to wrap the root object
            model = Model(root_obj)

            # Get correct object information
            armature_obj = model.armature()
            mesh_objs = list(model.meshes())

            print(f"Successfully imported PMX model with root: {root_obj.name}")
            print(f"Model has armature: {armature_obj.name}")
            print(f"Model has {len(mesh_objs)} mesh objects")

            # List all mesh objects
            for i, mesh in enumerate(mesh_objs):
                print(f"  Mesh {i + 1}: {mesh.name}")

            return root_obj

        except Exception as e:
            self.fail(f"Failed to import PMX model {largest_pmx}: {e}")

    # ********************************************
    # VMD Check Functions
    # ********************************************

    def __check_vmd_header(self, source_vmd, result_vmd):
        """Test VMD header information"""
        self.assertEqual(source_vmd.header.signature, result_vmd.header.signature)
        # Note: model_name might change during export, so we don't check it strictly

    def __get_vmd_keyframe_dy_by_axis(self, src_frame, prev_src_frame):
        """
        Calculate dy from VMD keyframe data for each axis separately
        Returns dict with 'x', 'y', 'z', 'r' keys
        """
        if prev_src_frame is None:
            return {"x": None, "y": None, "z": None, "r": None}

        # Calculate dy for each axis
        dy_values = {}

        # Location dy for x, y, z
        dy_values["x"] = abs(src_frame.location[0] - prev_src_frame.location[0])
        dy_values["y"] = abs(src_frame.location[1] - prev_src_frame.location[1])
        dy_values["z"] = abs(src_frame.location[2] - prev_src_frame.location[2])

        # Rotation dy (maximum change across all rotation components)
        rotation_dy = 0
        for i in range(4):  # x, y, z, w
            dy = abs(src_frame.rotation[i] - prev_src_frame.rotation[i])
            rotation_dy = max(rotation_dy, dy)
        dy_values["r"] = rotation_dy

        return dy_values

    def __check_interpolation_with_dy_info(self, src_interp, res_interp, dy_values, msg):
        """Check interpolation with dy information for each axis"""
        # fmt: off
        param_names = [
            "x_x1", "y_x1",    "0",    "0", "x_y1", "y_y1", "z_y1", "r_y1", "x_x2", "y_x2", "z_x2", "r_x2", "x_y2", "y_y2", "z_y2", "r_y2",
            "y_x1", "z_x1", "r_x1", "x_y1", "y_y1", "z_y1", "r_y1", "x_x2", "y_x2", "z_x2", "r_x2", "x_y2", "y_y2", "z_y2", "r_y2",    "0",
            "z_x1", "r_x1", "x_y1", "y_y1", "z_y1", "r_y1", "x_x2", "y_x2", "z_x2", "r_x2", "x_y2", "y_y2", "z_y2", "r_y2",    "0",    "0",
            "r_x1", "x_y1", "y_y1", "z_y1", "r_y1", "x_x2", "y_x2", "z_x2", "r_x2", "x_y2", "y_y2", "z_y2", "r_y2",    "0",    "0",    "0",
        ]
        # fmt: on

        # indices in [2, 3, 31, 46, 47, 61, 62, 63] are unclear
        skip_indices = {2, 3, 31, 46, 47, 61, 62, 63}
        error_count = 0
        max_error = 0

        # Check if it's linear interpolation for each axis
        def is_axis_linear(axis):
            """Check if specific axis has linear interpolation (x1 == y1 and x2 == y2)"""
            axis_indices = {
                "x": [0, 4, 8, 12],  # x_x1, x_y1, x_x2, x_y2
                "y": [1, 5, 9, 13],  # y_x1, y_y1, y_x2, y_y2
                "z": [17, 21, 25, 29],  # z_x1, z_y1, z_x2, z_y2
                "r": [18, 22, 26, 30],  # r_x1, r_y1, r_x2, r_y2
            }

            if axis not in axis_indices:
                return False

            indices = axis_indices[axis]
            if any(i >= len(src_interp) for i in indices):
                return False

            x1, y1, x2, y2 = [src_interp[i] for i in indices]
            return x1 == y1 and x2 == y2

        for j, (s, r) in enumerate(zip(src_interp, res_interp, strict=False)):
            if j in skip_indices:
                continue

            param_name = param_names[j]

            # Skip parameters marked as "0"
            if param_name == "0":
                continue

            # Extract axis and parameter type from parameter name
            parts = param_name.split("_")
            if len(parts) != 2:
                continue

            axis = parts[0]  # x, y, z, r
            param_type = parts[1]  # x1, y1, x2, y2

            # Check if this axis has dy ≈ 0 (currently allow large tolerance, may refine later)
            if axis in dy_values and dy_values[axis] is not None and abs(dy_values[axis]) < 1e-2:
                # For axis with dy ≈ 0, allow specific cases based on parameter type:
                # x1, y1 parameters allow == 20
                # x2, y2 parameters allow == 107
                is_valid = s == r  # Always allow source == result

                if param_type in {"x1", "y1"}:
                    is_valid = is_valid or (r == 20)
                elif param_type in {"x2", "y2"}:
                    is_valid = is_valid or (r == 107)

                if not is_valid:
                    expected_values = ["same as source"]
                    if param_type in {"x1", "y1"}:
                        expected_values.append("20")
                    elif param_type in {"x2", "y2"}:
                        expected_values.append("107")

                    error_count += 1
                    print(f"        Invalid for zero-dy axis {axis} at index {j:2d} ({param_name:>4}): {s:4d} -> {r:4d} (expected: {' or '.join(expected_values)}, dy={dy_values[axis]:.2e}), {msg}")
                    max_error = max(max_error, abs(s - r))
            # Check if current axis has linear interpolation
            elif is_axis_linear(axis):
                # For linear interpolation, allow result to be 20, 107 for corresponding positions
                is_valid = s == r  # Always allow source == result

                if param_type in {"x1", "y1"}:
                    is_valid = is_valid or (r == 20)
                elif param_type in {"x2", "y2"}:
                    is_valid = is_valid or (r == 107)

                if not is_valid:
                    error_count += 1
                    expected_values = ["same as source"]
                    if param_type in {"x1", "y1"}:
                        expected_values.append("20")
                    elif param_type in {"x2", "y2"}:
                        expected_values.append("107")
                    print(f"        Invalid for linear interp at index {j:2d} ({param_name:>4}): {s:4d} -> {r:4d} (expected: {' or '.join(expected_values)}), {msg}")
                    max_error = max(max_error, abs(s - r))
            # Normal case: require exact match
            elif abs(s - r) > 0:
                error_count += 1
                print(f"        Difference at index {j:2d} ({param_name:>4}): {s:4d} -> {r:4d}, diff {abs(s - r):4d}, {msg}")
                max_error = max(max_error, abs(s - r))

        return max_error, error_count

    def __check_vmd_bone_animation(self, source_vmd, result_vmd):
        """Test VMD bone animation data - compare all keyframes"""
        source_bone_anim = source_vmd.boneAnimation
        result_bone_anim = result_vmd.boneAnimation

        # We allow some bones to be filtered out during export
        # So we only check bones that exist in both
        common_bones = set(source_bone_anim.keys()) & set(result_bone_anim.keys())

        print(f"    Checking {len(common_bones)} common bones out of {len(source_bone_anim)} source bones")

        # Used to record the maximum interpolation error for each bone
        bone_interpolation_errors = {}

        # Flag to track if we've already printed detailed interpolation differences

        interp_error_count = 0
        for bone_name in common_bones:
            source_frames = source_bone_anim[bone_name]
            result_frames = result_bone_anim[bone_name]

            # Sort frames by frame number for consistent comparison
            source_frames.sort(key=lambda x: x.frame_number)
            result_frames.sort(key=lambda x: x.frame_number)

            # Strictly require frame count to be identical
            self.assertEqual(len(source_frames), len(result_frames), f"Bone {bone_name}: Frame count mismatch - source has {len(source_frames)} frames, exported has {len(result_frames)} frames")

            # Record the maximum interpolation error for this bone
            max_interpolation_error = 0

            # Track previous frame for dy calculation
            prev_src_frame = None

            # Compare all frames
            for i in range(len(source_frames)):
                src_frame = source_frames[i]
                res_frame = result_frames[i]

                msg = f"Bone {bone_name}, frame {src_frame.frame_number}"

                # Check frame number consistency
                self.assertEqual(src_frame.frame_number, res_frame.frame_number, f"{msg} - frame number mismatch")

                # Check location (allow tolerance due to scale conversion)
                self.assertLess(self.__vector_error(src_frame.location, res_frame.location), 1e-5, f"{msg} - location error")

                # Check rotation (currently allow large tolerance, may refine later)
                self.assertLess(self.__quaternion_error(src_frame.rotation, res_frame.rotation), 1e-2, f"{msg} - rotation error")

                # Check interpolation - skip first keyframe
                # Blender uses right handle of previous keyframe and left handle of current keyframe
                # to calculate interpolation curve, so VMD first frame interpolation cannot be preserved
                if i > 0:  # Skip first keyframe (index 0)
                    if hasattr(src_frame, "interp") and hasattr(res_frame, "interp"):
                        if src_frame.interp and res_frame.interp:
                            # Get dy values for each axis from VMD data
                            dy_values = self.__get_vmd_keyframe_dy_by_axis(src_frame, prev_src_frame)

                            # Check interpolation with dy information
                            interp_error, frame_error_count = self.__check_interpolation_with_dy_info(src_frame.interp, res_frame.interp, dy_values, msg)

                            interp_error_count += frame_error_count
                            max_interpolation_error = max(max_interpolation_error, interp_error)
                        else:
                            # Report if no interpolation data available
                            has_src_interp = hasattr(src_frame, "interp") and bool(src_frame.interp)
                            has_res_interp = hasattr(res_frame, "interp") and bool(res_frame.interp)
                            print(f"    No interpolation check for {msg} (src_has_interp: {has_src_interp}, res_has_interp: {has_res_interp})")
                    else:
                        print(f"    Skipping interpolation check for first frame: {msg} (VMD first frame interpolation not preserved in Blender)")

                # Update previous frame for next iteration
                prev_src_frame = src_frame

            # Record the maximum interpolation error for this bone
            if max_interpolation_error > 0:
                bone_interpolation_errors[bone_name] = max_interpolation_error

        if bone_interpolation_errors:
            print(f"        Total {interp_error_count} errors")
            print("\n    === Bone Interpolation Error Ranking ===")
            # Sort by error size
            sorted_errors = sorted(bone_interpolation_errors.items(), key=lambda x: x[1], reverse=True)

            for rank, (bone_name, error) in enumerate(sorted_errors, 1):
                print(f"    {rank:2d}. {bone_name}: Maximum interpolation error = {error:.2f}")

            print(f"    Total {len(bone_interpolation_errors)} bones have interpolation errors")
            self.assertEqual(len(bone_interpolation_errors), 0, f"Expected no bones with interpolation errors, but found {len(bone_interpolation_errors)} bones with errors")
        else:
            print("    No interpolation errors found")

    def __check_vmd_shape_key_animation(self, source_vmd, result_vmd):
        """Test VMD shape key animation data - compare all keyframes"""
        source_shape_anim = source_vmd.shapeKeyAnimation
        result_shape_anim = result_vmd.shapeKeyAnimation

        common_shapes = set(source_shape_anim.keys()) & set(result_shape_anim.keys())
        print(f"    Checking {len(common_shapes)} common shape keys out of {len(source_shape_anim)} source shapes")

        for shape_name in common_shapes:
            source_frames = source_shape_anim[shape_name]
            result_frames = result_shape_anim[shape_name]

            # Sort frames by frame number for consistent comparison
            source_frames.sort(key=lambda x: x.frame_number)
            result_frames.sort(key=lambda x: x.frame_number)

            # Strictly require frame count to be identical
            self.assertEqual(len(source_frames), len(result_frames), f"Shape key {shape_name}: Frame count mismatch - source has {len(source_frames)} frames, exported has {len(result_frames)} frames")

            # Compare all frames (not just first one)
            for i in range(len(source_frames)):  # Now safe to use len(source_frames)
                src_frame = source_frames[i]
                res_frame = result_frames[i]
                msg = f"Shape key {shape_name}, frame {src_frame.frame_number}"

                # Check frame number consistency
                self.assertEqual(src_frame.frame_number, res_frame.frame_number, f"{msg} - frame number mismatch")

                # Check weight value
                self.assertAlmostEqual(src_frame.weight, res_frame.weight, places=3, msg=f"{msg} - weight error")

    # ********************************************
    # Main Test Functions
    # ********************************************

    def test_vmd_exporter_with_pmx_model(self):
        """Test VMD export by importing the largest PMX model and testing different VMD files"""
        # Get VMD sample files
        vmd_files = self.__list_sample_files(["vmd"])
        if len(vmd_files) < 1:
            self.fail("No VMD sample files found")

        print(f"\nFound {len(vmd_files)} VMD files to test")

        # Enable MMD tools
        self.__enable_mmd_tools()

        # Import the largest PMX model
        root_obj = self.__import_largest_pmx_model()

        # Use Model class to get correct objects
        model = Model(root_obj)
        armature_obj = model.armature()
        mesh_objs = list(model.meshes())

        if not armature_obj:
            self.fail("No armature found in imported PMX model")

        print(f"Model has armature: {armature_obj.name}")
        print(f"Model has {len(mesh_objs)} mesh objects")

        # Check if model has shape keys
        shape_key_meshes = []
        for mesh_obj in mesh_objs:
            if mesh_obj.data.shape_keys:
                shape_key_meshes.append(mesh_obj)
                print(f"  Mesh {mesh_obj.name} has {len(mesh_obj.data.shape_keys.key_blocks)} shape keys")

        # Test each VMD file
        success_count = 0
        for test_num, vmd_file in enumerate(vmd_files):
            print(f"\n--- Testing VMD {test_num + 1}/{len(vmd_files)}: {os.path.basename(vmd_file)} ---")

            try:
                # Clear existing animation data
                if armature_obj.animation_data:
                    armature_obj.animation_data_clear()
                for mesh_obj in shape_key_meshes:
                    if mesh_obj.data.shape_keys and mesh_obj.data.shape_keys.animation_data:
                        mesh_obj.data.shape_keys.animation_data_clear()

                # Load original VMD
                source_vmd = vmd.File()
                source_vmd.load(filepath=vmd_file)
                print(f"    Loaded VMD with {len(source_vmd.boneAnimation)} bone animations, {len(source_vmd.shapeKeyAnimation)} shape animations")

                # Select all related objects for VMD import
                bpy.ops.object.select_all(action="DESELECT")
                root_obj.select_set(True)
                armature_obj.select_set(True)
                for mesh_obj in mesh_objs:
                    mesh_obj.select_set(True)

                # Import VMD motion
                bpy.ops.mmd_tools.import_vmd(
                    files=[{"name": os.path.basename(vmd_file)}],
                    directory=os.path.dirname(vmd_file),
                    scale=0.08,
                    margin=0,
                    bone_mapper="PMX",
                    use_pose_mode=False,
                    use_mirror=False,
                    update_scene_settings=True,
                    create_new_action=True,
                    use_nla=False,
                )
                print("    VMD imported successfully")

                # Export VMD motion
                output_vmd = os.path.join(TESTS_DIR, "output", f"test_export_{test_num}.vmd")

                # Set active object to root for export
                bpy.context.view_layer.objects.active = root_obj
                bpy.ops.mmd_tools.export_vmd(filepath=output_vmd, scale=12.5, use_pose_mode=False, use_frame_range=False, preserve_curves=True)
                print("    VMD exported successfully")

                # Load exported VMD for comparison
                result_vmd = vmd.File()
                result_vmd.load(filepath=output_vmd)
                print(f"    Exported VMD has {len(result_vmd.boneAnimation)} bone animations, {len(result_vmd.shapeKeyAnimation)} shape animations")

                # Compare VMD files
                self.__check_vmd_header(source_vmd, result_vmd)

                if len(source_vmd.boneAnimation) > 0:
                    self.__check_vmd_bone_animation(source_vmd, result_vmd)

                if len(source_vmd.shapeKeyAnimation) > 0:
                    self.__check_vmd_shape_key_animation(source_vmd, result_vmd)

                print("    ✓ VMD test passed")
                success_count += 1

            except Exception as e:
                print(f"    ✗ VMD test failed: {e}")
                # Don't fail the entire test, just log the error
                traceback.print_exc()

        print("\n=== VMD Export Test Results ===")
        print(f"Successfully tested: {success_count}/{len(vmd_files)} VMD files")

        # Require all tests to pass
        success_rate = success_count / len(vmd_files)
        self.assertEqual(success_count, len(vmd_files), f"All direct VMD tests must pass. Success rate: {success_rate:.1%} ({success_count}/{len(vmd_files)})")

    def test_vmd_direct_file_operations(self):
        """Direct test of VMD file loading/saving without Blender integration"""
        vmd_files = self.__list_sample_files(["vmd"])
        if len(vmd_files) < 1:
            self.fail("No VMD sample files found")

        print(f"\nTesting direct VMD file operations on {len(vmd_files)} files")

        success_count = 0
        for test_num, vmd_file in enumerate(vmd_files):
            print(f"\n--- Direct test {test_num + 1}/{len(vmd_files)}: {os.path.basename(vmd_file)} ---")

            try:
                # Load original VMD
                source_vmd = vmd.File()
                source_vmd.load(filepath=vmd_file)

                # Save to new file
                output_vmd = os.path.join(TESTS_DIR, "output", f"direct_test_{test_num}.vmd")
                source_vmd.save(filepath=output_vmd)

                # Load saved file
                result_vmd = vmd.File()
                result_vmd.load(filepath=output_vmd)

                # Basic comparisons
                self.__check_vmd_header(source_vmd, result_vmd)
                self.assertEqual(len(source_vmd.boneAnimation), len(result_vmd.boneAnimation))
                self.assertEqual(len(source_vmd.shapeKeyAnimation), len(result_vmd.shapeKeyAnimation))

                print("    ✓ Direct VMD test passed")
                success_count += 1

            except Exception as e:
                print(f"    ✗ Direct VMD test failed: {e}")

        print("\n=== Direct VMD Test Results ===")
        print(f"Successfully tested: {success_count}/{len(vmd_files)} VMD files")

        # Require all tests to pass
        success_rate = success_count / len(vmd_files)
        self.assertEqual(success_count, len(vmd_files), f"All direct VMD tests must pass. Success rate: {success_rate:.1%} ({success_count}/{len(vmd_files)})")


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main(verbosity=1, exit=True)
