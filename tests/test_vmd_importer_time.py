# Copyright 2025 MMD Tools authors
# Simplified VMD import time test script (including mesh tests) - unittest version

import os
import time
import unittest

import bpy
from bl_ext.blender_org.mmd_tools.core.vmd.importer import VMDImporter

# Test file path configuration
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "samples")


class TestVmdImportTime(unittest.TestCase):
    def setUp(self):
        """Set up testing environment"""
        self.enable_mmd_tools()

    def list_sample_files(self, dir_name, extension):
        """List all files with specified extension in the specified directory"""
        directory = os.path.join(SAMPLES_DIR, dir_name)
        if not os.path.exists(directory):
            return []

        ret = []
        for root, dirs, files in os.walk(directory):
            ret.extend(os.path.join(root, name) for name in files if name.lower().endswith("." + extension.lower()))
        return ret

    def clear_scene(self):
        """Clear scene"""
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=True)

    def enable_mmd_tools(self):
        """Enable mmd_tools addon"""
        bpy.ops.wm.read_homefile(use_empty=True)
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("bl_ext.blender_org.mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.blender_org.mmd_tools")

    def import_pmx_model(self, pmx_file):
        """Import PMX model"""
        self.clear_scene()

        bpy.ops.mmd_tools.import_model(filepath=pmx_file, scale=1.0, types={"MESH", "ARMATURE", "MORPHS"}, clean_model=False, log_level="ERROR")

        # Find imported model root object
        for obj in bpy.context.scene.objects:
            if obj.mmd_type == "ROOT":
                return obj
        return None

    def find_model_components(self, model_root):
        """Find model components"""
        components = {"armature": None, "meshes": []}

        # Iterate through all objects to find armature and meshes
        for obj in bpy.context.scene.objects:
            if obj.type == "ARMATURE":
                # Check if it belongs to this model
                if model_root in {obj.parent, obj} or (hasattr(obj, "mmd_type") and obj.mmd_type != "NONE"):
                    components["armature"] = obj

            elif obj.type == "MESH":
                # Check if it belongs to this model and has shape keys
                if (obj.parent and obj.parent.parent == model_root) or obj.parent == model_root:
                    components["meshes"].append(obj)

        return components

    def clean_animation_data(self, obj, obj_type):
        """Clean animation data from object"""
        if obj_type == "mesh" and obj.data.shape_keys and obj.data.shape_keys.animation_data:
            if obj.data.shape_keys.animation_data.action:
                bpy.data.actions.remove(obj.data.shape_keys.animation_data.action)
        elif obj.animation_data and obj.animation_data.action:
            bpy.data.actions.remove(obj.animation_data.action)

    def count_fcurves(self, obj, obj_type):
        """Count animation fcurves of object"""
        if obj_type == "mesh" and obj.data.shape_keys and obj.data.shape_keys.animation_data:
            action = obj.data.shape_keys.animation_data.action
            return len(action.fcurves) if action else 0
        if obj.animation_data and obj.animation_data.action:
            return len(obj.animation_data.action.fcurves)
        return 0

    def assign_vmd_to_object(self, importer, target_obj, obj_type, obj_name):
        """Use the existing VMD importer to assign to specified object"""
        # Clean previous animation data
        self.clean_animation_data(target_obj, obj_type)

        # Start timing assign operation
        start_time = time.time()

        # Use existing importer to execute assign
        importer.assign(target_obj)

        assign_time = time.time() - start_time

        # Check number of created animation fcurves
        fcurves_count = self.count_fcurves(target_obj, obj_type)

        return {"success": True, "time": assign_time, "fcurves": fcurves_count}

    def test_vmd_import_performance(self):
        """Test VMD import performance"""
        print("=== VMD Import Time Test ===")

        # Get test files
        pmx_files = self.list_sample_files("pmx", "pmx")
        pmx_files.extend(self.list_sample_files("pmd", "pmd"))
        vmd_files = self.list_sample_files("vmd", "vmd")

        # Check test conditions
        self.assertGreater(len(pmx_files), 0, "No PMX/PMD model files found")
        self.assertGreater(len(vmd_files), 0, "No VMD animation files found")

        print(f"Found {len(pmx_files)} model files")
        print(f"Found {len(vmd_files)} VMD files")

        # Import PMX model
        pmx_file = pmx_files[0]
        model_name = os.path.splitext(os.path.basename(pmx_file))[0]
        print(f"\nImporting model: {model_name}")

        model_start_time = time.time()
        model_root = self.import_pmx_model(pmx_file)
        model_import_time = time.time() - model_start_time

        self.assertIsNotNone(model_root, "Model import failed")
        print(f"✓ Model import completed, time: {model_import_time:.2f} seconds")

        # Find model components
        components = self.find_model_components(model_root)
        armature = components["armature"]
        meshes = components["meshes"]

        self.assertIsNotNone(armature, "Armature object not found")
        print(f"✓ Found armature object, contains {len(armature.pose.bones)} bones")
        print(f"✓ Found {len(meshes)} mesh objects")

        # Display meshes with shape keys
        shape_key_meshes = []
        for mesh in meshes:
            if mesh.data.shape_keys and len(mesh.data.shape_keys.key_blocks) > 1:
                shape_key_count = len(mesh.data.shape_keys.key_blocks) - 1  # Subtract Basis
                shape_key_meshes.append((mesh, shape_key_count))
                print(f"  - {mesh.name}: {shape_key_count} shape keys")

        if not shape_key_meshes:
            print("  ⚠ No mesh objects with shape keys found")

        # Test import time for each VMD file
        print(f"\nStarting test for {len(vmd_files)} VMD files import time:")
        print("=" * 80)

        all_results = []
        successful_tests = 0
        total_tests = 0

        for i, vmd_file in enumerate(vmd_files, 1):
            vmd_name = os.path.splitext(os.path.basename(vmd_file))[0]
            print(f"\n[{i}/{len(vmd_files)}] Testing VMD: {vmd_name}")
            print("-" * 60)

            vmd_results = {"vmd_name": vmd_name, "load_time": 0, "armature": None, "meshes": []}

            # Read VMD file
            print("Reading VMD file...")
            load_start_time = time.time()
            try:
                importer = VMDImporter(filepath=vmd_file)
                load_time = time.time() - load_start_time
                vmd_results["load_time"] = load_time
                print(f"✓ VMD file read completed, time: {load_time:.3f} seconds")
            except Exception as e:
                print(f"✗ VMD file read failed: {e}")
                continue

            # Test armature import
            print("Testing armature animation assign...")
            try:
                armature_result = self.assign_vmd_to_object(importer, armature, "armature", armature.name)
                vmd_results["armature"] = armature_result
                total_tests += 1

                if armature_result["success"]:
                    print(f"  ✓ Armature assign completed, time: {armature_result['time']:.3f} seconds, created {armature_result['fcurves']} animation fcurves")
                    successful_tests += 1
                else:
                    print(f"  ✗ Armature assign failed: {armature_result.get('error', 'Unknown error')}")
            except Exception as e:
                print(f"  ✗ Armature assign failed: {e}")
                vmd_results["armature"] = {"success": False, "error": str(e), "time": 0, "fcurves": 0}
                total_tests += 1

            # Test each mesh with shape keys import
            if shape_key_meshes:
                print("Testing shape key animation assign...")
                for mesh, shape_count in shape_key_meshes:
                    print(f"  Testing mesh: {mesh.name} ({shape_count} shape keys)")
                    try:
                        mesh_result = self.assign_vmd_to_object(importer, mesh, "mesh", mesh.name)
                        mesh_result["mesh_name"] = mesh.name
                        mesh_result["shape_count"] = shape_count
                        vmd_results["meshes"].append(mesh_result)
                        total_tests += 1

                        if mesh_result["success"]:
                            print(f"    ✓ Mesh assign completed, time: {mesh_result['time']:.3f} seconds, created {mesh_result['fcurves']} animation fcurves")
                            successful_tests += 1
                        else:
                            print(f"    ✗ Mesh assign failed: {mesh_result.get('error', 'Unknown error')}")
                    except Exception as e:
                        print(f"    ✗ Mesh assign failed: {e}")
                        mesh_result = {"success": False, "error": str(e), "time": 0, "fcurves": 0, "mesh_name": mesh.name, "shape_count": shape_count}
                        vmd_results["meshes"].append(mesh_result)
                        total_tests += 1
            else:
                print("  ⚠ Skipping shape key test (no available shape key meshes)")

            all_results.append(vmd_results)

        # Output summary report
        self.print_summary_report(all_results)

        # Calculate success rate
        success_rate = successful_tests / total_tests if total_tests > 0 else 0
        print(f"\nTest success rate: {success_rate:.1%} ({successful_tests}/{total_tests})")

        # Assert all tests passed
        self.assertEqual(successful_tests, total_tests, "Some tests failed")

    def print_summary_report(self, all_results):
        """Print summary report"""
        print("\n" + "=" * 80)
        print("VMD Import Time Test Results Summary (Optimized Version)")
        print("=" * 80)

        # VMD loading time statistics
        load_results = [r for r in all_results if r["load_time"] > 0]
        if load_results:
            print("\nVMD File Loading Time Statistics")
            print("-" * 50)
            for result in load_results:
                print(f"{result['vmd_name']:<30} {result['load_time']:>8.3f} seconds")

            load_times = [r["load_time"] for r in load_results]
            print("-" * 50)
            print(f"Average loading time: {sum(load_times) / len(load_times):.3f} seconds")
            print(f"Fastest loading time: {min(load_times):.3f} seconds")
            print(f"Slowest loading time: {max(load_times):.3f} seconds")

        # Armature animation statistics
        armature_results = [r["armature"] for r in all_results if r["armature"] and r["armature"]["success"]]
        if armature_results:
            print(f"\nArmature Animation Assign Results (Success: {len(armature_results)}/{len(all_results)})")
            print("-" * 50)

            for result in all_results:
                vmd_name = result["vmd_name"]
                arm_result = result["armature"]
                if arm_result and arm_result["success"]:
                    print(f"{vmd_name:<30} {arm_result['time']:>8.3f}s {arm_result['fcurves']:>6} fcurves")
                else:
                    print(f"{vmd_name:<30} {'Failed':>15}")

            # Armature statistics
            arm_times = [r["time"] for r in armature_results]
            arm_fcurves = [r["fcurves"] for r in armature_results]
            print("-" * 50)
            print(f"Average armature assign time: {sum(arm_times) / len(arm_times):.3f} seconds")
            print(f"Fastest armature assign time: {min(arm_times):.3f} seconds")
            print(f"Slowest armature assign time: {max(arm_times):.3f} seconds")
            print(f"Average animation fcurves: {sum(arm_fcurves) / len(arm_fcurves):.1f}")

        # Shape key animation statistics
        all_mesh_results = []
        for result in all_results:
            all_mesh_results.extend([m for m in result["meshes"] if m["success"]])

        if all_mesh_results:
            print(f"\nShape Key Animation Assign Results (Success: {len(all_mesh_results)} tests)")
            print("-" * 50)

            for result in all_results:
                vmd_name = result["vmd_name"]
                if result["meshes"]:
                    for mesh_result in result["meshes"]:
                        if mesh_result["success"]:
                            print(f"{vmd_name:<20} {mesh_result['mesh_name']:<15} {mesh_result['time']:>8.3f}s {mesh_result['fcurves']:>6} fcurves")
                        else:
                            print(f"{vmd_name:<20} {mesh_result['mesh_name']:<15} {'Failed':>15}")

            # Shape key statistics
            mesh_times = [r["time"] for r in all_mesh_results]
            mesh_fcurves = [r["fcurves"] for r in all_mesh_results]
            print("-" * 50)
            print(f"Average shape key assign time: {sum(mesh_times) / len(mesh_times):.3f} seconds")
            print(f"Fastest shape key assign time: {min(mesh_times):.3f} seconds")
            print(f"Slowest shape key assign time: {max(mesh_times):.3f} seconds")
            print(f"Average animation fcurves: {sum(mesh_fcurves) / len(mesh_fcurves):.1f}")
        else:
            print("\n⚠ No successful shape key animation assign tests")

        # Overall statistics
        total_successful = len(armature_results) + len(all_mesh_results)
        total_tests = len([r for r in all_results if r["armature"]]) + sum(len(r["meshes"]) for r in all_results)

        print("\nOverall Statistics:")
        print(f"Total tests: {total_tests}")
        print(f"Successful tests: {total_successful}")
        if total_tests > 0:
            print(f"Success rate: {total_successful / total_tests * 100:.1f}%")

        # Performance improvement summary
        if load_results and (armature_results or all_mesh_results):
            print("\nPerformance Improvement Summary:")
            avg_load_time = sum(r["load_time"] for r in load_results) / len(load_results)

            if armature_results:
                avg_arm_assign = sum(r["time"] for r in armature_results) / len(armature_results)
                print(f"Average VMD loading time: {avg_load_time:.3f} seconds")
                print(f"Average armature assign time: {avg_arm_assign:.3f} seconds")

            if all_mesh_results:
                avg_mesh_assign = sum(r["time"] for r in all_mesh_results) / len(all_mesh_results)
                print(f"Average shape key assign time: {avg_mesh_assign:.3f} seconds")


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main(verbosity=1, exit=True)
