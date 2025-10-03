# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import logging
import os
import shutil
import unittest

import bpy
from bl_ext.blender_org.mmd_tools.core.model import Model

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "samples")


class TestPmxExportViewLayerExclusion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Clean up output from previous tests"""
        output_dir = os.path.join(TESTS_DIR, "output")
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

    def __enable_mmd_tools(self):
        bpy.ops.wm.read_homefile(use_empty=True)
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.blender_org.mmd_tools")

    def __list_sample_files(self, file_types):
        ret = []
        for file_type in file_types:
            file_ext = "." + file_type
            for root, dirs, files in os.walk(os.path.join(SAMPLES_DIR, file_type)):
                ret.extend(os.path.join(root, name) for name in files if name.lower().endswith(file_ext))
        return ret

    def __get_model_meshes(self, root_obj):
        """Get all mesh objects belonging to the model"""
        model = Model(root_obj)
        return list(model.meshes())

    def test_export_with_excluded_view_layer_parts(self):
        """Test PMX export failure when some model parts are excluded from View Layer"""
        input_files = self.__list_sample_files(("pmx",))
        assert len(input_files) >= 1, "No PMX sample files available"

        test_file = input_files[0]

        # Import model
        self.__enable_mmd_tools()
        bpy.ops.mmd_tools.import_model(filepath=test_file, types={"MESH", "ARMATURE", "PHYSICS", "MORPHS", "DISPLAY"}, scale=0.08, clean_model=False, remove_doubles=False, log_level="ERROR")

        # Find the imported model
        root_objects = [obj for obj in bpy.context.scene.objects if obj.mmd_type == "ROOT"]
        assert len(root_objects) > 0, "PMX model should be imported successfully"

        root_obj = root_objects[0]
        meshes = self.__get_model_meshes(root_obj)

        # Find a mesh to exclude from view layer
        target_mesh = None
        for mesh_obj in meshes:
            if mesh_obj.data and len(mesh_obj.data.vertices) > 10:
                target_mesh = mesh_obj
                break

        assert target_mesh is not None, "No suitable mesh found for exclusion test"

        # Create a new collection and move the mesh to it
        excluded_collection = bpy.data.collections.new("ExcludedCollection")
        bpy.context.scene.collection.children.link(excluded_collection)

        # Remove mesh from current collections and add to new collection
        for collection in target_mesh.users_collection:
            collection.objects.unlink(target_mesh)
        excluded_collection.objects.link(target_mesh)

        # Exclude the collection from view layer (this removes the checkmark)
        layer_collection = bpy.context.view_layer.layer_collection.children["ExcludedCollection"]
        layer_collection.exclude = True

        bpy.context.view_layer.update()

        # Setup export context
        bpy.ops.object.select_all(action="DESELECT")
        root_obj.select_set(True)
        bpy.context.view_layer.objects.active = root_obj
        bpy.context.view_layer.update()

        # Export should fail with ReferenceError - let it crash
        output_pmx = os.path.join(TESTS_DIR, "output", "view_layer_exclusion_test.pmx")
        bpy.ops.mmd_tools.export_pmx(filepath=output_pmx, scale=12.5, sort_materials=False, sort_vertices="NONE", log_level="ERROR")


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main(verbosity=1, exit=True)
