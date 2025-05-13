
import logging
import os
import shutil
import sys
import unittest

import bpy
from bl_ext.user_default.mmd_tools.core import pmx
from bl_ext.user_default.mmd_tools.core.model import FnModel
from bl_ext.user_default.mmd_tools.core.pmx.importer import PMXImporter

context = bpy.context

# sys.path.append(os.getcwd())
# from tests.test_pmx_exporter import TestPmxExporter

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "samples")


class TestModelEdit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Clean up output from previous tests
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
        # Set up logging and clear the Blender scene
        logger = logging.getLogger()
        logger.setLevel("ERROR")

        # Clear the scene
        bpy.ops.wm.read_homefile()

    # ********************************************
    # Utils
    # ********************************************

    def __create_test_collection(self, name="MMD_Test_Collection"):
        """Create a dedicated collection for testing"""
        # Remove collection if it already exists
        if name in bpy.data.collections:
            collection = bpy.data.collections[name]
            bpy.data.collections.remove(collection)

        # Create new collection
        collection = bpy.data.collections.new(name)
        context.scene.collection.children.link(collection)
        return collection

    def __list_sample_files(self, file_types):
        ret = []
        for file_type in file_types:
            file_ext = "." + file_type
            for root, dirs, files in os.walk(os.path.join(SAMPLES_DIR, file_type)):
                for name in files:
                    if name.lower().endswith(file_ext):
                        ret.append(os.path.join(root, name))
        return ret

    def __enable_mmd_tools(self):
        bpy.ops.wm.read_homefile()  # reload blender startup file
        pref = getattr(context, "preferences", None) or context.user_preferences
        if not pref.addons.get("mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.user_default.mmd_tools")  # make sure addon 'mmd_tools' is enabled

    def __is_object_in_collection(self, obj, collection):
        """Safely check if an object is in a collection"""
        for o in collection.objects:
            if o == obj:
                return True
        return False

    def __import_pmx_models(self, filepaths, collection, scale=1.0):
        """Import PMX models into the specified collection"""
        imported_models = []

        # Set the active collection
        layer_collection = context.view_layer.layer_collection
        for child in layer_collection.children:
            if child.collection == collection:
                layer_collection = child
                break
        context.view_layer.active_layer_collection = layer_collection

        for filepath in filepaths:
            # Import the PMX model
            model = pmx.load(filepath)
            importer = PMXImporter()
            importer.execute(
                pmx=model,
                types={"MESH", "ARMATURE", "PHYSICS", "DISPLAY", "MORPHS"},
                scale=scale,
                clean_model=False,
            )

        # Find all root objects and ensure they're in our collection
        for obj in context.scene.objects:
            if obj.mmd_type == "ROOT":
                if not self.__is_object_in_collection(obj, collection):
                    # Move the root to our collection
                    scene_collection = context.scene.collection
                    if obj.name in scene_collection.objects:
                        scene_collection.objects.unlink(obj)
                    collection.objects.link(obj)

                # Also move all children recursively
                self.__move_children_to_collection(obj, collection)

                # Add to our imported models list
                imported_models.append(obj)

        return imported_models

    def __move_children_to_collection(self, parent_obj, collection):
        """Recursively move all children of an object to the specified collection"""
        for child in parent_obj.children:
            # Check if the child is not already in our collection
            if not self.__is_object_in_collection(child, collection):
                # Unlink from other collections
                for col in bpy.data.collections:
                    if child.name in col.objects:
                        col.objects.unlink(child)
                # Link to our collection
                collection.objects.link(child)

            # Process children recursively
            self.__move_children_to_collection(child, collection)

    def __test_joined_model(self, joined_model_path, model_order_str):
        """Test the exported joined model for validity"""

        # Clear the scene
        bpy.ops.wm.read_homefile()

        # Enable mmd_tools addon
        self.__enable_mmd_tools()

        # Import the joined model
        print(f"\nTesting joined model: {joined_model_path}")
        try:
            # Load the PMX model
            joined_model = pmx.load(joined_model_path)

            # Import the model into Blender
            PMXImporter().execute(
                pmx=joined_model,
                types={"MESH", "ARMATURE", "PHYSICS", "DISPLAY", "MORPHS"},
                scale=1,
                clean_model=False,
            )

            # Update scene
            context.view_layer.update()

            # Basic validation - check if we have bones, vertices, and materials
            self.assertTrue(len(joined_model.bones) > 0, "Joined model has no bones")
            self.assertTrue(len(joined_model.vertices) > 0, "Joined model has no vertices")
            self.assertTrue(len(joined_model.materials) > 0, "Joined model has no materials")

            # Check for key bones from both models
            has_head_bone = False
            has_neck_bone = False
            for bone in joined_model.bones:
                if bone.name == "頭":
                    has_head_bone = True
                elif bone.name == "首":
                    has_neck_bone = True

            print(f"    Total bones: {len(joined_model.bones)}")

            self.assertTrue(has_head_bone, "Joined model is missing the '頭' (head) bone")
            self.assertTrue(has_neck_bone, "Joined model is missing the '首' (neck) bone")

            # Check if the model was correctly imported into Blender
            armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
            self.assertTrue(len(armatures) > 0, "No armatures were imported into Blender")

            # Now re-export the model to test roundtrip conversion
            export_path = os.path.join(TESTS_DIR, "output", f"joined_model_{model_order_str}_test.pmx")
            bpy.ops.mmd_tools.export_pmx(
                filepath=export_path,
                scale=1,
                copy_textures=False,
                sort_materials=False,
                log_level="ERROR",
            )
            print("Joined model passed all validation tests!")
            return True

        except Exception as e:
            import traceback

            traceback.print_exc()
            self.fail(f"Joined model testing failed with error: {e}")
            return False

    def test_model_separation_and_join(self):
        # Run the test twice with models in different orders
        self.__run_separation_and_join_test(reverse_models=False)
        self.__run_separation_and_join_test(reverse_models=True)

    def __run_separation_and_join_test(self, reverse_models=False):
        # Test the model separation and joining functionality
        # Enable mmd_tools
        self.__enable_mmd_tools()

        # Create a dedicated collection for our test
        test_collection = self.__create_test_collection("MMD_Models")

        # Get sample PMX files
        pmx_files = self.__list_sample_files(["pmx"])
        if len(pmx_files) < 2:
            self.skipTest("Need at least 2 PMX sample files for this test")

        # If there are 3 or more models, select the two largest ones
        if len(pmx_files) >= 3:
            # Get file sizes
            file_sizes = [(filepath, os.path.getsize(filepath)) for filepath in pmx_files]
            # Sort by size in descending order
            file_sizes.sort(key=lambda x: x[1], reverse=True)
            # Select the two largest files
            test_files = [file_info[0] for file_info in file_sizes[:2]]
        else:
            # Use the first two PMX files if there are only two
            test_files = pmx_files[:2]

        # Reverse the order if needed for the second test run
        if reverse_models:
            test_files.reverse()
            print(f"\nTesting with REVERSED PMX files:\n - {test_files[0]}\n - {test_files[1]}")
        else:
            print(f"\nTesting with PMX files:\n - {test_files[0]}\n - {test_files[1]}")

        try:
            # Rest of the function remains unchanged
            # Import the models into our collection
            pmx_models = self.__import_pmx_models(test_files, test_collection)
            self.assertEqual(len(pmx_models), 2, "Failed to import two models")

            # Keep track of all model roots in our collection before separation
            existing_roots = []
            for obj in test_collection.objects:
                if obj.mmd_type == "ROOT":
                    existing_roots.append(obj)

            print(f"\nBefore separation - Model roots: {[root.name for root in existing_roots]}")

            # For each model, directly find the '頭' bone and use it for separation
            for model_root in existing_roots:
                # Get the armature object
                armature = None
                for child in model_root.children:
                    if child.type == "ARMATURE":
                        armature = child
                        break

                if not armature:
                    self.fail(f"No armature found in model {model_root.name}")

                # Enter pose mode
                context.view_layer.objects.active = armature
                bpy.ops.object.mode_set(mode="POSE")

                # Deselect all bones
                for bone in armature.pose.bones:
                    bone.bone.select = False

                # Directly find and use the '頭' bone
                head_bone = None
                for bone in armature.pose.bones:
                    if bone.name == "頭":
                        head_bone = bone
                        break

                if not head_bone:
                    self.fail(f"Could not find '頭' bone in model {model_root.name}")

                print(f"Using bone '{head_bone.name}' for model separation in {model_root.name}")
                head_bone.bone.select = True
                armature.data.bones.active = head_bone.bone

                # Execute separation
                bpy.ops.mmd_tools.model_separate_by_bones(separate_armature=True, include_descendant_bones=True, boundary_joint_owner="DESTINATION")

                # Return to object mode
                bpy.ops.object.mode_set(mode="OBJECT")

                # Make sure new objects are in our collection
                for obj in context.scene.objects:
                    if obj.mmd_type == "ROOT" and not self.__is_object_in_collection(obj, test_collection):
                        # Add to collection
                        test_collection.objects.link(obj)
                        # Also move all children
                        self.__move_children_to_collection(obj, test_collection)

            # After separation, find all the armatures and roots in our collection
            all_roots = []
            for obj in test_collection.objects:
                if obj.mmd_type == "ROOT":
                    all_roots.append(obj)

            all_armatures = []
            for obj in bpy.data.objects:
                if obj.type == "ARMATURE":
                    # Check if this armature is in our test collection
                    if self.__is_object_in_collection(obj, test_collection):
                        all_armatures.append(obj)

            print(f"\nAfter separation - All model roots: {[root.name for root in all_roots]}")
            print(f"After separation - All armatures: {[arm.name for arm in all_armatures]}")

            # Get bone information for each armature
            armatures_with_bone_info = []
            for arm in all_armatures:
                # Count bones with specific names
                head_bones = [b for b in arm.pose.bones if b.name in ["頭", "head", "Head"]]
                neck_bones = [b for b in arm.pose.bones if b.name in ["首", "neck", "Neck"]]

                print(f"Armature: {arm.name}")
                print(f"    Total bones: {len(arm.pose.bones)}")
                print(f"    Has head bones: {[b.name for b in head_bones]}")
                print(f"    Has neck bones: {[b.name for b in neck_bones]}")

                armatures_with_bone_info.append({"armature": arm, "bone_count": len(arm.pose.bones), "head_bones": head_bones, "neck_bones": neck_bones})

            # Get the original model names from before separation
            original_model_names = [root.name for root in existing_roots]

            # Find armatures based on the naming pattern from the original models
            first_model_arm = None
            second_model_arm_with_head = None

            # First model's primary armature with '首' bone
            for arm_info in armatures_with_bone_info:
                arm_name = arm_info["armature"].name
                if arm_name == original_model_names[0] + "_arm" and arm_info["neck_bones"]:
                    first_model_arm = arm_info["armature"]
                    break

            # Second model's separated armature with '頭' bone
            for arm_info in armatures_with_bone_info:
                arm_name = arm_info["armature"].name
                if original_model_names[1] + "_arm" in arm_name and ".001" in arm_name and arm_info["head_bones"]:
                    second_model_arm_with_head = arm_info["armature"]
                    break

            if not first_model_arm:
                self.fail("Could not find the first model's armature with '首' bone")

            if not second_model_arm_with_head:
                self.fail("Could not find the second model's armature with '頭' bone")

            print("\nSelected armatures for joining:")
            print(f"    First model armature: {first_model_arm.name}")
            print(f"    Second model armature: {second_model_arm_with_head.name}")

            # Find the roots of the armatures
            first_model_root = first_model_arm.parent
            second_model_root = second_model_arm_with_head.parent

            if not first_model_root or not second_model_root:
                self.fail("Could not find the root objects for the selected armatures")

            # First, ensure we're in object mode
            bpy.ops.object.mode_set(mode="OBJECT")

            # Deselect all objects
            bpy.ops.object.select_all(action="DESELECT")

            # Select both root objects and make the first one active
            first_model_root.select_set(True)
            second_model_root.select_set(True)
            context.view_layer.objects.active = first_model_root

            # Now, select and make active the first armature
            bpy.ops.object.select_all(action="DESELECT")
            first_model_arm.select_set(True)
            context.view_layer.objects.active = first_model_arm

            # Enter pose mode
            bpy.ops.object.mode_set(mode="POSE")

            # Deselect all bones
            for bone in first_model_arm.pose.bones:
                bone.bone.select = False

            # Find and select the '首' bone in the first model
            neck_bone = None
            for bone in first_model_arm.pose.bones:
                if bone.name == "首":
                    neck_bone = bone
                    break

            if not neck_bone:
                self.fail("Could not find '首' bone in the first model's armature")

            # Select the neck bone and make it active
            neck_bone.bone.select = True
            first_model_arm.data.bones.active = neck_bone.bone

            # Return to object mode
            bpy.ops.object.mode_set(mode="OBJECT")

            # Now, select the second armature and make it active
            bpy.ops.object.select_all(action="DESELECT")
            second_model_arm_with_head.select_set(True)
            context.view_layer.objects.active = second_model_arm_with_head

            # Enter pose mode
            bpy.ops.object.mode_set(mode="POSE")

            # Deselect all bones
            for bone in second_model_arm_with_head.pose.bones:
                bone.bone.select = False

            # Find and select the '頭' bone in the second model
            head_bone = None
            for bone in second_model_arm_with_head.pose.bones:
                if bone.name == "頭":
                    head_bone = bone
                    break

            if not head_bone:
                self.fail("Could not find '頭' bone in the second model's armature")

            # Select the head bone
            head_bone.bone.select = True
            second_model_arm_with_head.data.bones.active = head_bone.bone

            # Return to object mode
            bpy.ops.object.mode_set(mode="OBJECT")

            # Select both model roots again for the join operation
            bpy.ops.object.select_all(action="DESELECT")
            first_model_root.select_set(True)
            second_model_root.select_set(True)

            # Set the active object to the first model root
            context.view_layer.objects.active = first_model_root

            print(f"Joining using bones: '{neck_bone.name}' from '{first_model_arm.name}' and '{head_bone.name}' from '{second_model_arm_with_head.name}'")

            # First, collect the objects to be removed
            objects_to_remove = []
            for obj in bpy.data.objects:
                if obj.type == "ARMATURE" and obj != first_model_arm and obj != second_model_arm_with_head:
                    objects_to_remove.append(obj)
                elif obj.mmd_type == "ROOT" and obj != first_model_root and obj != second_model_root:
                    objects_to_remove.append(obj)
            # Then remove them in a separate loop
            for obj in objects_to_remove:
                if obj.name in bpy.data.objects:
                    print(f"Removing unnecessary object: {obj.name} ({obj.type})")
                    bpy.data.objects.remove(obj)

            # Select the specific armatures again and enter pose mode on the first armature
            bpy.ops.object.select_all(action="DESELECT")
            first_model_arm.select_set(True)
            second_model_arm_with_head.select_set(True)
            context.view_layer.objects.active = first_model_arm

            for arm in [first_model_arm, second_model_arm_with_head]:
                head_bones = [b for b in arm.pose.bones if b.name in ["頭", "head", "Head"]]
                neck_bones = [b for b in arm.pose.bones if b.name in ["首", "neck", "Neck"]]
                print(f"Armature: {arm.name}")
                print(f"    Total bones: {len(arm.pose.bones)}")
                print(f"    Has head bones: {[b.name for b in head_bones]}")
                print(f"    Has neck bones: {[b.name for b in neck_bones]}")

            context.view_layer.objects.active = first_model_arm

            # Enter pose mode on the active armature
            bpy.ops.object.mode_set(mode="POSE")

            # Select the bones in the armatures
            for bone in first_model_arm.pose.bones:
                bone.bone.select = False
            neck_bone.bone.select = True
            for bone in second_model_arm_with_head.pose.bones:
                bone.bone.select = False
            head_bone.bone.select = True

            selected_bones = context.selected_pose_bones
            print(f"Selected {len(selected_bones)} bones:")
            for i, bone in enumerate(selected_bones, 1):
                print(f"{i}. {bone.name}")

            # context.view_layer.update()

            # Execute join
            bpy.ops.mmd_tools.model_join_by_bones(join_type="OFFSET")

            # Return to object mode
            bpy.ops.object.mode_set(mode="OBJECT")

            # Check the result - get all roots in our collection
            final_roots = []
            for obj in test_collection.objects:
                if obj.mmd_type == "ROOT":
                    final_roots.append(obj)

            print(f"\nAfter joining - Model roots: {[root.name for root in final_roots]}")

            # Find the joined model's root (should be the first model's root)
            joined_model_root = first_model_root
            print(f"Joined model root: {joined_model_root.name}")

            # Identify the main armature of the joined model
            joined_model_armature = FnModel.find_armature_object(joined_model_root)

            arm = joined_model_armature
            head_bones = [b for b in arm.pose.bones if b.name in ["頭", "head", "Head"]]
            neck_bones = [b for b in arm.pose.bones if b.name in ["首", "neck", "Neck"]]
            print(f"Armature: {arm.name}")
            print(f"    Total bones: {len(arm.pose.bones)}")
            print(f"    Has head bones: {[b.name for b in head_bones]}")
            print(f"    Has neck bones: {[b.name for b in neck_bones]}")

            # Ensure we're in object mode
            bpy.ops.object.mode_set(mode="OBJECT")

            # Deselect all objects and select the joined model root
            bpy.ops.object.select_all(action="DESELECT")
            joined_model_root.select_set(True)
            context.view_layer.objects.active = joined_model_root

            # Export the joined model
            # Modify the output filename to indicate model order
            model_order_str = "2_1" if reverse_models else "1_2"
            output_pmx = os.path.join(TESTS_DIR, "output", f"joined_model_{model_order_str}.pmx")

            bpy.ops.mmd_tools.export_pmx(
                filepath=output_pmx,
                scale=1,
                copy_textures=False,
                sort_materials=False,
                log_level="ERROR",
            )

            # Verify the file was created
            self.assertTrue(os.path.isfile(output_pmx), f"Exported PMX file ({model_order_str} order) was not created")

            # Now test the joined model properly (include a standard import/export cycle test)
            self.__test_joined_model(output_pmx, model_order_str)

            # Verify both exported files exist
            self.assertTrue(os.path.isfile(output_pmx), f"Exported PMX file ({model_order_str} order) was not created")

        except Exception as e:
            import traceback

            traceback.print_exc()
            self.fail(f"Test failed with error: {e}")


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main()
