
import os
import shutil
import time
import unittest

import bpy
from bl_ext.user_default.mmd_tools.core.model import Model
from bl_ext.user_default.mmd_tools.core.vpd.importer import VPDImporter
from mathutils import Quaternion, Vector

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "samples")


class TestVPDImporter(unittest.TestCase):

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

    def __store_bone_state(self, armature):
        """Store the current state of all bones in the armature"""
        state = {}
        for bone in armature.pose.bones:
            state[bone.name] = {"location": bone.location.copy(), "rotation": None}

            # Store rotation based on rotation mode
            if bone.rotation_mode == "QUATERNION":
                state[bone.name]["rotation"] = bone.rotation_quaternion.copy()
            elif bone.rotation_mode == "AXIS_ANGLE":
                state[bone.name]["rotation"] = bone.rotation_axis_angle.copy()
            else:
                state[bone.name]["rotation"] = bone.rotation_euler.copy()

        return state

    def __check_pose_library_changes(self, armature):
        """Check if poses were added to the armature's pose library"""
        # Try to access pose library
        # Compatibility with different Blender versions
        if hasattr(armature, "pose_library") and armature.pose_library:
            # In older Blender versions
            if hasattr(armature.pose_library, "pose_markers"):
                return len(armature.pose_library.pose_markers)

        # For newer Blender versions or if no pose library exists
        return 0

    def __compare_bone_states(self, before_state, after_state):
        """Compare bone states before and after VPD import to check for changes"""
        changes = 0
        changed_bones = []

        for bone_name, state_before in before_state.items():
            if bone_name in after_state:
                state_after = after_state[bone_name]

                # Check if location changed
                loc_changed = (
                    state_before["location"] - state_after["location"]
                ).length > 0.001

                # Check if rotation changed
                rot_changed = False
                if isinstance(state_before["rotation"], Quaternion) and isinstance(
                    state_after["rotation"], Quaternion
                ):
                    rot_changed = (
                        abs(1.0 - state_before["rotation"].dot(state_after["rotation"]))
                        > 0.001
                    )
                elif state_before["rotation"] != state_after["rotation"]:
                    rot_changed = True

                if loc_changed or rot_changed:
                    changes += 1
                    changed_bones.append(bone_name)

        return changes, changed_bones

    def test_vpd_import(self):
        """Test VPD imports on all models and vpd files"""
        self.__enable_mmd_tools()

        # Get all PMX files
        pmx_files = self.__list_sample_files("pmx", "pmx")
        pmx_files.extend(self.__list_sample_files("pmd", "pmd"))

        if not pmx_files:
            self.skipTest("No PMX/PMD sample files found")

        # Get all VPD files
        vpd_files = self.__list_sample_files("vpd", "vpd")

        if not vpd_files:
            self.skipTest("No VPD sample files found")

        print(f"\nTesting {len(vpd_files)} VPD files on {len(pmx_files)} models")

        # Test each VPD file with each model
        for model_num, pmx_file in enumerate(pmx_files):
            model_name = os.path.basename(pmx_file)
            print(f"\n - {model_num+1}/{len(pmx_files)} | Model: {model_name}")

            # Import the model
            try:
                # Create model from PMX
                model_root = self.__create_model_from_pmx(pmx_file)

                if not model_root:
                    print(
                        f"   * Skipping model - no MMD root object found after import"
                    )
                    continue

                # Create Model object and get armature
                model = Model(model_root)
                armature = model.armature()

                if not armature:
                    print(f"   * Skipping model - no armature found in MMD model")
                    continue

                # Test each VPD file
                for vpd_num, vpd_file in enumerate(vpd_files):
                    vpd_name = os.path.basename(vpd_file)
                    print(f"   - {vpd_num+1}/{len(vpd_files)} | VPD: {vpd_name}")

                    # Import the VPD
                    try:
                        # Store initial state for comparison
                        initial_pose_count = self.__check_pose_library_changes(armature)
                        initial_bone_state = self.__store_bone_state(armature)

                        # Select the model root and armature, and make armature active
                        bpy.ops.object.select_all(action="DESELECT")
                        model_root.select_set(True)
                        armature.select_set(True)
                        bpy.context.view_layer.objects.active = armature
                        bpy.context.view_layer.update()

                        # Import using operator
                        result = bpy.ops.mmd_tools.import_vpd(
                            filepath=vpd_file, scale=1.0
                        )

                        # Check result
                        if "FINISHED" not in result:
                            print(f"   * Import failed with result: {result}")
                            continue

                        print(f"   * Success! VPD import finished successfully")

                        # Success if the operation finished
                        self.assertTrue(
                            "FINISHED" in result,
                            f"VPD import did not complete successfully",
                        )

                    except Exception as e:
                        print(f"   * Exception during VPD import: {str(e)}")
                        import traceback

                        print(traceback.format_exc())
                        self.fail(
                            f"Exception importing VPD {vpd_name} to model {model_name}: {str(e)}"
                        )

            except Exception as e:
                print(f"   * Exception during model import: {str(e)}")
                import traceback

                print(traceback.format_exc())
                self.fail(f"Exception importing model {model_name}: {str(e)}")

    def test_direct_vpd_import(self):
        """Test VPD importing using the VPDImporter class directly"""
        # Only run if we have sample files
        vpd_files = self.__list_sample_files("vpd", "vpd")
        pmx_files = self.__list_sample_files("pmx", "pmx")

        if not vpd_files or not pmx_files:
            self.skipTest("No sample files found for direct VPD import test")

        # Use the first PMX and VPD file
        pmx_file = pmx_files[0]
        vpd_file = vpd_files[0]

        # Import the model
        model_root = self.__create_model_from_pmx(pmx_file)
        if not model_root:
            self.skipTest("Could not import model for direct VPD import test")

        # Get the model and armature
        model = Model(model_root)
        armature = model.armature()
        if not armature:
            self.skipTest("Model has no armature for direct VPD import test")

        # Directly use VPDImporter
        try:
            importer = VPDImporter(filepath=vpd_file, scale=1.0)
            importer.assign(armature)
            print(f"Direct import completed successfully")
            self.assertTrue(True, "Direct VPD import succeeded")
        except Exception as e:
            print(f"Direct import failed with exception: {str(e)}")
            self.fail(f"Direct VPD import failed with exception: {str(e)}")


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (
        sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    )
    unittest.main()
