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


class TestPmxExportAfterModifier(unittest.TestCase):
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

    def __import_and_setup_model(self):
        """Import model and return root object and target mesh"""
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

        # Find a mesh with sufficient vertices
        target_mesh = None
        for mesh_obj in meshes:
            if len(mesh_obj.data.vertices) > 50:
                target_mesh = mesh_obj
                break

        assert target_mesh is not None, "No mesh with sufficient vertices found"
        return root_obj, target_mesh

    def __export_model(self, root_obj, filename):
        """Export the model to PMX format"""
        # Setup export context
        bpy.ops.object.select_all(action="DESELECT")
        root_obj.select_set(True)
        bpy.context.view_layer.objects.active = root_obj
        bpy.context.view_layer.update()

        # Export model
        output_pmx = os.path.join(TESTS_DIR, "output", filename)
        bpy.ops.mmd_tools.export_pmx(filepath=output_pmx, scale=12.5, sort_materials=False, sort_vertices="NONE", log_level="ERROR")

    def test_array_modifier_export(self):
        """Test PMX export after applying Array modifier"""
        root_obj, target_mesh = self.__import_and_setup_model()

        # Add Array modifier
        bpy.context.view_layer.objects.active = target_mesh
        array_mod = target_mesh.modifiers.new(name="Array", type="ARRAY")
        array_mod.count = 2
        array_mod.relative_offset_displace[0] = 1.0

        # Export model
        self.__export_model(root_obj, "array_modifier_test.pmx")

    def test_decimate_modifier_export(self):
        """Test PMX export after applying Decimate modifier"""
        root_obj, target_mesh = self.__import_and_setup_model()

        # Add Decimate modifier
        bpy.context.view_layer.objects.active = target_mesh
        decimate_mod = target_mesh.modifiers.new(name="Decimate", type="DECIMATE")
        decimate_mod.ratio = 0.5

        # Export model
        self.__export_model(root_obj, "decimate_modifier_test.pmx")

    def test_edge_split_modifier_export(self):
        """Test PMX export after applying Edge Split modifier"""
        root_obj, target_mesh = self.__import_and_setup_model()

        # Add Edge Split modifier
        bpy.context.view_layer.objects.active = target_mesh
        edge_split_mod = target_mesh.modifiers.new(name="EdgeSplit", type="EDGE_SPLIT")
        edge_split_mod.split_angle = 0.523599  # 30 degrees in radians

        # Export model
        self.__export_model(root_obj, "edge_split_modifier_test.pmx")

    def test_mirror_modifier_export(self):
        """Test PMX export after applying Mirror modifier"""
        root_obj, target_mesh = self.__import_and_setup_model()

        # Add Mirror modifier
        bpy.context.view_layer.objects.active = target_mesh
        mirror_mod = target_mesh.modifiers.new(name="Mirror", type="MIRROR")
        mirror_mod.use_axis[0] = True  # Mirror on X-axis
        mirror_mod.use_clip = True

        # Export model
        self.__export_model(root_obj, "mirror_modifier_test.pmx")

    def test_solidify_modifier_export(self):
        """Test PMX export after applying Solidify modifier"""
        root_obj, target_mesh = self.__import_and_setup_model()

        # Add Solidify modifier
        bpy.context.view_layer.objects.active = target_mesh
        solidify_mod = target_mesh.modifiers.new(name="Solidify", type="SOLIDIFY")
        solidify_mod.thickness = 0.1

        # Export model
        self.__export_model(root_obj, "solidify_modifier_test.pmx")

    def test_weld_modifier_export(self):
        """Test PMX export after applying Weld modifier"""
        root_obj, target_mesh = self.__import_and_setup_model()

        # Add Weld modifier
        bpy.context.view_layer.objects.active = target_mesh
        weld_mod = target_mesh.modifiers.new(name="Weld", type="WELD")
        weld_mod.merge_threshold = 0.001

        # Export model
        self.__export_model(root_obj, "weld_modifier_test.pmx")


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main(verbosity=1, exit=True)
