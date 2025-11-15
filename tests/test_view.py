# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import logging
import unittest

import bpy


class TestView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Enable the mmd_tools addon"""
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("mmd_tools", None):
            print("Enabling mmd_tools addon for testing...")
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.blender_org.mmd_tools")
        else:
            print("mmd_tools addon already enabled.")

    def setUp(self):
        """Set up a clean testing environment for each test"""
        # Start with a clean file
        bpy.ops.wm.read_homefile(use_empty=True)
        self.context = bpy.context

        # Set logger level (matches style)
        logger = logging.getLogger()
        logger.setLevel("ERROR")

        # --- Setup for Shading Tests ---

        # Create a mesh object
        bpy.ops.mesh.primitive_plane_add()
        self.mesh_obj = self.context.active_object
        self.mesh_obj.name = "TestMesh"

        # Find a 3D view area to test on
        self.area_3d = None
        self.space_3d = None
        for area in self.context.screen.areas:
            if area.type == "VIEW_3D":
                self.area_3d = area
                self.space_3d = area.spaces[0]
                break
        self.assertIsNotNone(self.area_3d, "Could not find a 3D View area for testing")

    # ********************************************
    # Shading Operators
    # ********************************************

    def test_set_glsl_shading(self):
        """Test the SetGLSLShading operator."""
        # Run the operator
        bpy.ops.mmd_tools.set_glsl_shading()

        # Check engine
        self.assertIn(self.context.scene.render.engine, ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"])

        # Check viewport shading settings
        shading = self.space_3d.shading
        self.assertEqual(shading.type, "SOLID")
        self.assertEqual(shading.light, "STUDIO")
        self.assertEqual(shading.color_type, "TEXTURE")
        self.assertEqual(shading.show_object_outline, False)
        self.assertEqual(shading.show_backface_culling, False)

    def test_set_shadeless_glsl_shading(self):
        """Test the SetShadelessGLSLShading operator."""
        # Run the operator
        bpy.ops.mmd_tools.set_shadeless_glsl_shading()

        # Check engine
        self.assertIn(self.context.scene.render.engine, ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"])

        # Check viewport shading settings
        shading = self.space_3d.shading
        self.assertEqual(shading.type, "SOLID")
        self.assertEqual(shading.light, "FLAT")
        self.assertEqual(shading.color_type, "TEXTURE")
        self.assertEqual(shading.show_object_outline, False)
        self.assertEqual(shading.show_backface_culling, False)

    def test_reset_shading(self):
        """Test the ResetShading operator."""
        # Run the operator
        bpy.ops.mmd_tools.reset_shading()

        # Check engine
        self.assertIn(self.context.scene.render.engine, ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"])

        # Check viewport shading settings
        shading = self.space_3d.shading
        self.assertEqual(shading.type, "SOLID")
        self.assertEqual(shading.light, "STUDIO")
        self.assertEqual(shading.color_type, "MATERIAL")
        self.assertEqual(shading.show_object_outline, False)
        self.assertEqual(shading.show_backface_culling, False)


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main(verbosity=1, exit=True)
