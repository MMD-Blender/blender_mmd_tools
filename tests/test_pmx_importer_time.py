# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import os
import time
import unittest

import bpy
from bl_ext.blender_org.mmd_tools.core import pmx
from bl_ext.blender_org.mmd_tools.core.pmd.importer import import_pmd_to_pmx
from bl_ext.blender_org.mmd_tools.core.pmx.importer import PMXImporter

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "samples")


class TestPmxImportTime(unittest.TestCase):
    def __list_sample_files(self, file_types):
        """List sample files"""
        ret = []
        for file_type in file_types:
            file_ext = "." + file_type
            for root, dirs, files in os.walk(os.path.join(SAMPLES_DIR, file_type)):
                ret.extend(os.path.join(root, name) for name in files if name.lower().endswith(file_ext))
        return ret

    def __enable_mmd_tools(self):
        """Enable MMD Tools addon"""
        bpy.ops.wm.read_homefile(use_empty=True)
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.blender_org.mmd_tools")

    def test_pmx_import_time(self):
        """Test PMX import time performance"""
        input_files = self.__list_sample_files(("pmd", "pmx"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample files!")

        # Set import types
        import_types = {"MESH", "ARMATURE", "PHYSICS", "MORPHS", "DISPLAY"}

        print("\n=== PMX Import Time Test ===")
        print(f"Import types: {str(import_types)}")

        total_time = 0
        successful_imports = 0

        for test_num, filepath in enumerate(input_files):
            filename = os.path.basename(filepath)
            print(f"\n{test_num + 1:2d}/{len(input_files)} | File: {filename}")

            try:
                # Reset Blender environment
                self.__enable_mmd_tools()

                # Select file loader
                file_loader = pmx.load
                if filepath.lower().endswith(".pmd"):
                    file_loader = import_pmd_to_pmx

                # Start timing
                start_time = time.time()

                # Load model
                source_model = file_loader(filepath)

                # Execute import
                PMXImporter().execute(
                    pmx=source_model,
                    types=import_types,
                    scale=1,
                    clean_model=False,
                )

                # Update scene
                bpy.context.scene.frame_set(bpy.context.scene.frame_current)

                # End timing
                end_time = time.time()
                import_time = end_time - start_time

                print(f"     Import time: {import_time:.3f} seconds")

                total_time += import_time
                successful_imports += 1

            except Exception as e:
                print(f"     Import failed: {str(e)}")
                continue

        # Output statistics
        print("\n=== Statistics ===")
        print(f"Successful imports: {successful_imports}/{len(input_files)} files")
        if successful_imports > 0:
            print(f"Total time: {total_time:.3f} seconds")
            print(f"Average time: {total_time / successful_imports:.3f} seconds")
            print("Fastest import: Please check individual results above")


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main(verbosity=1, exit=True)
