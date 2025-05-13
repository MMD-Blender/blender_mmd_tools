import os
import shutil
import unittest

import bpy
from bl_ext.user_default.mmd_tools.core import pmx
from bl_ext.user_default.mmd_tools.core.model import Model

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), 'samples')

class TestFileIoOperators(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Clean up output from previous tests
        """
        output_dir = os.path.join(TESTS_DIR, 'output')
        for item in os.listdir(output_dir):
            if item.endswith('.OUTPUT'):
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

        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=True)
        # Add some useful shortcuts
        self.context = bpy.context
        self.scene = bpy.context.scene

    def test_export_shy_cube(self):
        """
        This test will load the shy_cube.blend sample and check if it exports correctly.
        The following checks will be made:
        - The texture is properly copied to the target directory
        - The material order is kept
        """
        input_blend = os.path.join(SAMPLES_DIR, 'blends', 'shy_cube', 'shy_cube.blend')
        if not os.path.isfile(input_blend):
            self.fail('required sample file %s not found. Please download it' % input_blend)
        output_pmx = os.path.join(TESTS_DIR, 'output', 'shy_cube.pmx')
        bpy.ops.wm.open_mainfile(filepath=input_blend)        
        root = Model.findRoot(self.context.active_object)
        rig = Model(root)
        orig_material_names = [mat.mmd_material.name_j or mat.name for mat in rig.materials()]
        try:
            bpy.ops.mmd_tools.export_pmx(filepath=output_pmx)
        except Exception:
            self.fail("Exception happened during export")
        else:
            self.assertTrue(os.path.isfile(output_pmx), "File was not created")  # Is this a race condition?
            # Check if the texture was properly copied
            tex_path = os.path.join(os.path.dirname(output_pmx), 'textures', 'blush.png')
            self.assertTrue(os.path.isfile(tex_path), f"Texture not copied properly. Expected file at: {tex_path}")
            # Load the resultant pmx file and check the material order is the expected
            result_model = pmx.load(output_pmx)
            result_material_names = [mat.name for mat in result_model.materials]
            same_order = True
            for orig, result in zip(orig_material_names, result_material_names):
                if orig != result:
                    same_order = False
                    break
            self.assertTrue(same_order, "Material order was lost")

if __name__ == '__main__':
    import sys
    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    unittest.main()
