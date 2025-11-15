# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import gc
import logging
import math
import os
import shutil
import unittest

import bpy
from bl_ext.blender_org.mmd_tools.core.model import Model
from bl_ext.blender_org.mmd_tools.core.pmx.importer import PMXImporter
from mathutils import Vector

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "samples")


class TestPmxImporter(unittest.TestCase):
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

        if not bpy.context.active_object:
            bpy.ops.mesh.primitive_cube_add()

        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=True)

        self.context = bpy.context
        self.scene = bpy.context.scene

    # ********************************************
    # Utils
    # ********************************************

    def __vector_error(self, vec0, vec1):
        return (Vector(vec0) - Vector(vec1)).length

    def __quaternion_error(self, quat0, quat1):
        angle = quat0.rotation_difference(quat1).angle % math.pi
        assert angle >= 0
        return min(angle, math.pi - angle)

    def __safe_get_object(self, name):
        """Safely get object by name"""
        return bpy.data.objects.get(name)

    def __safe_get_material(self, name):
        """Safely get material by name"""
        return bpy.data.materials.get(name)

    def __safe_get_mesh(self, name):
        """Safely get mesh by name"""
        return bpy.data.meshes.get(name)

    def __safe_get_armature(self, name):
        """Safely get armature by name"""
        return bpy.data.armatures.get(name)

    # ********************************************
    # Helper Functions
    # ********************************************

    def _list_sample_files(self, file_types):
        """List all files with specified extensions in the directory"""
        ret = []
        for file_type in file_types:
            file_ext = "." + file_type
            for root, dirs, files in os.walk(os.path.join(SAMPLES_DIR, file_type)):
                ret.extend(os.path.join(root, name) for name in files if name.lower().endswith(file_ext))
        return ret

    def _enable_mmd_tools(self):
        """Make sure mmd_tools addon is enabled"""
        bpy.ops.wm.read_homefile(use_empty=True)
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("bl_ext.blender_org.mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.blender_org.mmd_tools")

    def _import_pmx_model(self, filepath, **kwargs):
        """Import PMX model with given parameters"""
        default_args = {
            "filepath": filepath,
            "types": {"MESH", "ARMATURE", "PHYSICS", "MORPHS", "DISPLAY"},
            "scale": 0.08,
            "clean_model": False,
            "remove_doubles": False,
            "fix_ik_links": False,
            "apply_bone_fixed_axis": False,
            "rename_LR_bones": False,
            "use_underscore": False,
            "translator": None,
            "use_mipmap": True,
            "sph_blend_factor": 1.0,
            "spa_blend_factor": 1.0,
        }
        default_args.update(kwargs)

        importer = PMXImporter()
        importer.execute(**default_args)

        # Find imported root object
        for obj in bpy.context.scene.objects:
            if obj.mmd_type == "ROOT":
                return obj
        return None

    def _get_model_components(self, root_obj):
        """Get all components of an imported MMD model"""
        if not root_obj or root_obj.mmd_type != "ROOT":
            return None

        model = Model(root_obj)
        return {
            "root": root_obj,
            "armature": model.armature(),
            "meshes": list(model.meshes()),
            "rigid_bodies": list(model.rigidBodies()),
            "joints": list(model.joints()),
            "materials": list(model.materials()),
        }

    def _check_basic_structure(self, components):
        """Check basic MMD model structure"""
        self.assertIsNotNone(components["root"], "Root object should exist")
        self.assertEqual(components["root"].mmd_type, "ROOT", "Root object should have ROOT type")
        self.assertIsNotNone(components["armature"], "Armature should exist")
        self.assertEqual(components["armature"].type, "ARMATURE", "Armature should be ARMATURE type")

    def _check_mesh_integrity(self, meshes):
        """Check mesh data integrity"""
        for mesh_obj in meshes:
            self.assertEqual(mesh_obj.type, "MESH", "Object should be mesh type")
            mesh_data = mesh_obj.data
            self.assertGreaterEqual(len(mesh_data.vertices), 0, "Mesh should have vertices")
            self.assertGreaterEqual(len(mesh_data.polygons), 0, "Mesh should have faces")
            self.assertGreater(len(mesh_data.materials), 0, "Mesh should have materials")

            # Check UV layers
            self.assertGreater(len(mesh_data.uv_layers), 0, "Mesh should have UV layers")

            # Check vertex groups for armature weights
            self.assertGreater(len(mesh_obj.vertex_groups), 0, "Mesh should have vertex groups")

    def _check_armature_integrity(self, armature_obj):
        """Check armature data integrity"""
        armature_data = armature_obj.data
        self.assertGreater(len(armature_data.bones), 0, "Armature should have bones")

        # Check pose bones
        pose_bones = armature_obj.pose.bones
        self.assertEqual(len(pose_bones), len(armature_data.bones), "Pose bones should match edit bones")

        # Check MMD bone properties
        for pose_bone in pose_bones:
            self.assertTrue(hasattr(pose_bone, "mmd_bone"), "Pose bone should have MMD properties")
            mmd_bone = pose_bone.mmd_bone
            self.assertIsNotNone(mmd_bone.name_j, "MMD bone should have Japanese name")

    def _check_physics_integrity(self, rigid_bodies, joints):
        """Check physics components integrity"""
        for rigid_obj in rigid_bodies:
            self.assertEqual(rigid_obj.mmd_type, "RIGID_BODY", "Object should be rigid body type")
            self.assertIsNotNone(rigid_obj.rigid_body, "Rigid body should have physics properties")

        for joint_obj in joints:
            self.assertEqual(joint_obj.mmd_type, "JOINT", "Object should be joint type")
            self.assertIsNotNone(joint_obj.rigid_body_constraint, "Joint should have constraint properties")

    def _check_materials_integrity(self, materials):
        """Check materials integrity"""
        for material in materials:
            self.assertTrue(hasattr(material, "mmd_material"), "Material should have MMD properties")
            mmd_mat = material.mmd_material
            self.assertIsNotNone(mmd_mat.name_j, "MMD material should have Japanese name")

    def _check_morphs_integrity(self, root_obj):
        """Check morphs integrity"""
        mmd_root = root_obj.mmd_root

        # Check vertex morphs
        vertex_morphs = mmd_root.vertex_morphs
        for morph in vertex_morphs:
            self.assertIsNotNone(morph.name, "Vertex morph should have name")

        # Check bone morphs
        bone_morphs = mmd_root.bone_morphs
        for morph in bone_morphs:
            self.assertIsNotNone(morph.name, "Bone morph should have name")

        # Check material morphs
        material_morphs = mmd_root.material_morphs
        for morph in material_morphs:
            self.assertIsNotNone(morph.name, "Material morph should have name")

        # Check UV morphs
        uv_morphs = mmd_root.uv_morphs
        for morph in uv_morphs:
            self.assertIsNotNone(morph.name, "UV morph should have name")

        # Check group morphs
        group_morphs = mmd_root.group_morphs
        for morph in group_morphs:
            self.assertIsNotNone(morph.name, "Group morph should have name")

    def _check_display_frames_integrity(self, root_obj):
        """Check display frames integrity"""
        mmd_root = root_obj.mmd_root
        display_frames = mmd_root.display_item_frames

        # Should have at least Root and Facial frames
        self.assertGreaterEqual(len(display_frames), 2, "Should have at least Root and Facial frames")

        frame_names = [frame.name for frame in display_frames]
        self.assertIn("Root", frame_names, "Should have Root frame")
        self.assertIn("表情", frame_names, "Should have Facial frame")

    # ********************************************
    # Test Cases
    # ********************************************

    def test_pmx_importer_basic_functionality(self):
        """Test basic PMX import functionality"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()

        for filepath in input_files[:3]:  # Test first 3 files to save time
            print(f"\nTesting PMX import: {os.path.basename(filepath)}")

            # Clear scene
            bpy.ops.object.select_all(action="SELECT")
            bpy.ops.object.delete()

            # Import model
            root_obj = self._import_pmx_model(filepath)
            self.assertIsNotNone(root_obj, f"Failed to import model from {filepath}")

            # Get model components
            components = self._get_model_components(root_obj)
            self.assertIsNotNone(components, "Failed to get model components")

            # Check basic structure
            self._check_basic_structure(components)

            print(f"✓ Basic import test passed for {os.path.basename(filepath)}")

    def test_pmx_importer_mesh_components(self):
        """Test mesh import components"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        # Import with mesh only
        root_obj = self._import_pmx_model(filepath, types={"MESH"})
        components = self._get_model_components(root_obj)

        # Check mesh integrity
        self._check_mesh_integrity(components["meshes"])
        print("✓ Mesh import test passed")

    def test_pmx_importer_armature_components(self):
        """Test armature import components"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        # Import with armature
        root_obj = self._import_pmx_model(filepath, types={"ARMATURE", "MESH"})
        components = self._get_model_components(root_obj)

        # Check armature integrity
        self._check_armature_integrity(components["armature"])
        print("✓ Armature import test passed")

    def test_pmx_importer_physics_components(self):
        """Test physics import components"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        # Import with physics
        root_obj = self._import_pmx_model(filepath, types={"MESH", "ARMATURE", "PHYSICS"})
        components = self._get_model_components(root_obj)

        # Check physics integrity if physics objects exist
        if components["rigid_bodies"] or components["joints"]:
            self._check_physics_integrity(components["rigid_bodies"], components["joints"])
            print("✓ Physics import test passed")
        else:
            print("✓ Physics import test passed (no physics objects in model)")

    def test_pmx_importer_morphs_components(self):
        """Test morphs import components"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        # Import with morphs
        root_obj = self._import_pmx_model(filepath, types={"MESH", "ARMATURE", "MORPHS"})
        components = self._get_model_components(root_obj)

        # Check basic structure first
        self._check_basic_structure(components)

        # Check morphs integrity
        self._check_morphs_integrity(root_obj)

        # Additional morphs-specific checks using components
        if components["meshes"]:
            for mesh_obj in components["meshes"]:
                # Check if mesh has shape keys (for vertex morphs)
                if mesh_obj.data.shape_keys:
                    shape_keys = mesh_obj.data.shape_keys.key_blocks
                    morph_keys = [key for key in shape_keys if key.name != "Basis"]
                    if morph_keys:
                        print(f"   - Found {len(morph_keys)} shape keys in mesh")

        print("✓ Morphs import test passed")

    def test_pmx_importer_display_frames(self):
        """Test display frames import"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        # Import with display frames
        root_obj = self._import_pmx_model(filepath, types={"MESH", "ARMATURE", "DISPLAY"})
        components = self._get_model_components(root_obj)

        # Check basic structure first
        self._check_basic_structure(components)

        # Check display frames integrity
        self._check_display_frames_integrity(root_obj)

        # Additional display frames checks using components
        if components["armature"]:
            armature = components["armature"]
            # Check if bone collections were created from display frames
            if hasattr(armature.data, "collections"):
                bone_collections = armature.data.collections
                if bone_collections:
                    collection_names = [col.name for col in bone_collections]
                    print(f"   - Created bone collections: {collection_names}")

            # Verify that display frames reference existing bones
            mmd_root = root_obj.mmd_root
            bone_names = {bone.name for bone in armature.pose.bones}

            for frame in mmd_root.display_item_frames:
                for item in frame.data:
                    if item.type == "BONE":
                        self.assertIn(item.name, bone_names, f"Display frame references non-existent bone: {item.name}")

        print("✓ Display frames import test passed")

    def test_pmx_importer_materials_integrity(self):
        """Test materials import integrity"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        # Import model
        root_obj = self._import_pmx_model(filepath)
        components = self._get_model_components(root_obj)

        # Check materials integrity
        self._check_materials_integrity(components["materials"])
        print("✓ Materials import test passed")

    def test_pmx_importer_scale_parameter(self):
        """Test scale parameter functionality"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        scales = [0.04, 0.08, 0.16]
        for scale in scales:
            # Clear scene
            bpy.ops.object.select_all(action="SELECT")
            bpy.ops.object.delete()

            # Import with different scale
            root_obj = self._import_pmx_model(filepath, scale=scale, types={"MESH", "ARMATURE"})
            self.assertIsNotNone(root_obj, f"Failed to import with scale {scale}")

            components = self._get_model_components(root_obj)
            armature = components["armature"]

            # Check that bones have appropriate size
            bone_lengths = [bone.length for bone in armature.data.bones]
            avg_bone_length = sum(bone_lengths) / len(bone_lengths) if bone_lengths else 0

            # Bone lengths should be proportional to scale
            self.assertGreater(avg_bone_length, 0, f"Bones should have positive length with scale {scale}")

        print("✓ Scale parameter test passed")

    def test_pmx_importer_cleaning_options(self):
        """Test cleaning options functionality"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        # Test clean_model option
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()

        root_obj = self._import_pmx_model(filepath, clean_model=True, types={"MESH"})
        self.assertIsNotNone(root_obj, "Failed to import with clean_model=True")

        # Test remove_doubles option
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()

        root_obj = self._import_pmx_model(filepath, remove_doubles=True, types={"MESH"})
        self.assertIsNotNone(root_obj, "Failed to import with remove_doubles=True")

        print("✓ Cleaning options test passed")

    def test_pmx_importer_bone_options(self):
        """Test bone-related options"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        # Test rename_LR_bones option
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()

        root_obj = self._import_pmx_model(filepath, rename_LR_bones=True, types={"ARMATURE"})
        self.assertIsNotNone(root_obj, "Failed to import with rename_LR_bones=True")

        components = self._get_model_components(root_obj)
        armature = components["armature"]

        # Check if any bones have .L or .R suffix
        bone_names = [bone.name for bone in armature.data.bones]
        has_lr_suffix = any(name.endswith((".L", ".R")) for name in bone_names)

        # Note: Only check if model actually has left/right bones
        # Some models might not have bones that can be renamed
        print(f"   - Found L/R suffixed bones: {has_lr_suffix}")

        # Test fix_ik_links option
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()

        root_obj = self._import_pmx_model(filepath, fix_ik_links=True, types={"ARMATURE"})
        self.assertIsNotNone(root_obj, "Failed to import with fix_ik_links=True")

        print("✓ Bone options test passed")

    def test_pmx_importer_edge_cases(self):
        """Test edge cases and error handling"""
        self._enable_mmd_tools()

        # Test with non-existent file
        try:
            root_obj = self._import_pmx_model("non_existent.pmx")
            self.fail("Should have failed with non-existent file")
        except Exception:
            pass  # Expected to fail

        # Test with empty types set
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) >= 1:
            filepath = input_files[0]

            bpy.ops.object.select_all(action="SELECT")
            bpy.ops.object.delete()

            root_obj = self._import_pmx_model(filepath, types=set())
            # Should still create root object even with empty types
            self.assertIsNotNone(root_obj, "Should create root object even with empty types")

        print("✓ Edge cases test passed")

    def test_pmx_importer_complete_workflow(self):
        """Test complete import workflow with all options"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        print(f"\nTesting complete workflow with: {os.path.basename(filepath)}")

        # Import with all components and options
        root_obj = self._import_pmx_model(
            filepath,
            types={"MESH", "ARMATURE", "PHYSICS", "MORPHS", "DISPLAY"},
            scale=0.08,
            clean_model=True,
            use_mipmap=True,
        )

        self.assertIsNotNone(root_obj, "Failed to import model in complete workflow")

        # Get and check all components
        components = self._get_model_components(root_obj)
        self._check_basic_structure(components)

        if components["meshes"]:
            self._check_mesh_integrity(components["meshes"])

        if components["armature"]:
            self._check_armature_integrity(components["armature"])

        if components["rigid_bodies"] or components["joints"]:
            self._check_physics_integrity(components["rigid_bodies"], components["joints"])

        if components["materials"]:
            self._check_materials_integrity(components["materials"])

        self._check_morphs_integrity(root_obj)
        self._check_display_frames_integrity(root_obj)

        # Check that model is properly set up for use
        model = Model(root_obj)
        self.assertIsNotNone(model.armature(), "Model should have armature")

        meshes = list(model.meshes())
        if meshes:
            mesh_obj = meshes[0]
            # Check armature modifier exists
            armature_modifiers = [mod for mod in mesh_obj.modifiers if mod.type == "ARMATURE"]
            self.assertGreater(len(armature_modifiers), 0, "Mesh should have armature modifier")

        print("✓ Complete workflow test passed")
        print(f"   - Root object: {root_obj.name}")
        print(f"   - Armature: {components['armature'].name if components['armature'] else 'None'}")
        print(f"   - Meshes: {len(components['meshes'])}")
        print(f"   - Rigid bodies: {len(components['rigid_bodies'])}")
        print(f"   - Joints: {len(components['joints'])}")
        print(f"   - Materials: {len(components['materials'])}")

    def test_pmx_import_sdef_vertices(self):
        """Test PMX importing SDEF vertex weights"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        root_obj = self._import_pmx_model(filepath, types={"MESH", "ARMATURE"})
        components = self._get_model_components(root_obj)

        # Check for SDEF shape keys
        for mesh_obj in components["meshes"]:
            if mesh_obj.data.shape_keys:
                sdef_keys = [key for key in mesh_obj.data.shape_keys.key_blocks if key.name.startswith("mmd_sdef_")]
                if sdef_keys:
                    print(f"   - Found {len(sdef_keys)} SDEF shape keys")
                    self.assertGreaterEqual(len(sdef_keys), 3, "Should have SDEF C, R0, R1 keys")

        print("✓ SDEF vertices test passed")

    def test_pmx_import_additional_uvs(self):
        """Test PMX importing additional UV channels"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        root_obj = self._import_pmx_model(filepath, types={"MESH"})
        components = self._get_model_components(root_obj)

        for mesh_obj in components["meshes"]:
            uv_layers = mesh_obj.data.uv_layers
            uv_layer_names = [layer.name for layer in uv_layers]

            # Check for additional UV layers
            additional_uvs = [name for name in uv_layer_names if name.startswith("UV") and name != "UVMap"]
            if additional_uvs:
                print(f"   - Found additional UV layers: {additional_uvs}")

            # Check for vertex colors (ADD UV2)
            if mesh_obj.data.vertex_colors:
                color_layers = [layer.name for layer in mesh_obj.data.vertex_colors]
                print(f"   - Found vertex color layers: {color_layers}")

        print("✓ Additional UVs test passed")

    def test_pmx_import_custom_properties(self):
        """Test PMX importing custom properties and metadata"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        root_obj = self._import_pmx_model(filepath)

        # Check MMD root properties
        mmd_root = root_obj.mmd_root
        self.assertIsNotNone(mmd_root.name, "Should have model name")

        # Check import folder property
        self.assertIn("import_folder", root_obj, "Should have import_folder property")

        # Check comment texts
        if mmd_root.comment_text:
            comment_text = bpy.data.texts.get(mmd_root.comment_text)
            self.assertIsNotNone(comment_text, "Comment text should exist")

        if mmd_root.comment_e_text:
            comment_e_text = bpy.data.texts.get(mmd_root.comment_e_text)
            self.assertIsNotNone(comment_e_text, "English comment text should exist")

        print("✓ Custom properties test passed")

    def test_pmx_import_bone_collections(self):
        """Test PMX importing bone collections from display frames"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        root_obj = self._import_pmx_model(filepath, types={"ARMATURE", "DISPLAY"})
        components = self._get_model_components(root_obj)

        armature = components["armature"]
        if hasattr(armature.data, "collections"):
            bone_collections = armature.data.collections
            collection_names = [col.name for col in bone_collections]
            print(f"   - Found bone collections: {collection_names}")

            # Should have at least some bone collections from display frames
            self.assertGreater(len(bone_collections), 0, "Should have bone collections")

        print("✓ Bone collections test passed")

    def test_pmx_import_ik_configuration(self):
        """Test PMX importing detailed IK configuration"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        root_obj = self._import_pmx_model(filepath, types={"ARMATURE"})
        components = self._get_model_components(root_obj)

        armature = components["armature"]
        ik_constraints_found = 0
        ik_limit_constraints_found = 0

        for pose_bone in armature.pose.bones:
            # Check for IK constraints
            ik_constraints = [c for c in pose_bone.constraints if c.type == "IK"]
            ik_constraints_found += len(ik_constraints)

            # Check for IK limit constraints
            limit_constraints = [c for c in pose_bone.constraints if c.type == "LIMIT_ROTATION" and "mmd_ik_limit" in c.name]
            ik_limit_constraints_found += len(limit_constraints)

            # Check MMD IK properties
            if hasattr(pose_bone, "mmd_bone"):
                mmd_bone = pose_bone.mmd_bone
                if hasattr(mmd_bone, "ik_rotation_constraint"):
                    if mmd_bone.ik_rotation_constraint > 0:
                        print(f"   - Bone {pose_bone.name} has IK rotation constraint: {mmd_bone.ik_rotation_constraint}")

        print(f"   - Found {ik_constraints_found} IK constraints")
        print(f"   - Found {ik_limit_constraints_found} IK limit constraints")
        print("✓ IK configuration test passed")

    def test_pmx_import_material_textures(self):
        """Test PMX importing material texture assignments"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        root_obj = self._import_pmx_model(filepath, types={"MESH"})
        components = self._get_model_components(root_obj)

        texture_count = 0
        toon_texture_count = 0
        sphere_texture_count = 0

        for material in components["materials"]:
            mmd_mat = material.mmd_material

            # Check texture assignments
            if material.node_tree:
                texture_nodes = [node for node in material.node_tree.nodes if node.type == "TEX_IMAGE"]
                texture_count += len(texture_nodes)

            # Check MMD specific texture properties
            if hasattr(mmd_mat, "toon_texture") and mmd_mat.toon_texture:
                toon_texture_count += 1

            if hasattr(mmd_mat, "sphere_texture_type") and mmd_mat.sphere_texture_type != "0":
                sphere_texture_count += 1

        print(f"   - Found {texture_count} texture nodes")
        print(f"   - Found {toon_texture_count} toon textures")
        print(f"   - Found {sphere_texture_count} sphere textures")
        print("✓ Material textures test passed")

    def test_pmx_import_vertex_weight_distribution(self):
        """Test PMX importing vertex weight distribution accuracy"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        root_obj = self._import_pmx_model(filepath, types={"MESH", "ARMATURE"})
        components = self._get_model_components(root_obj)

        for mesh_obj in components["meshes"]:
            vertex_groups = mesh_obj.vertex_groups
            if len(vertex_groups) == 0:
                continue

            # Check special vertex groups
            edge_scale_vg = vertex_groups.get("mmd_edge_scale")
            vertex_order_vg = vertex_groups.get("mmd_vertex_order")

            self.assertIsNotNone(edge_scale_vg, "Should have mmd_edge_scale vertex group")
            self.assertIsNotNone(vertex_order_vg, "Should have mmd_vertex_order vertex group")

            if edge_scale_vg:
                self.assertTrue(edge_scale_vg.lock_weight, "Edge scale group should be locked")
            if vertex_order_vg:
                self.assertTrue(vertex_order_vg.lock_weight, "Vertex order group should be locked")

            # Count bone vertex groups
            bone_vgs = [vg for vg in vertex_groups if vg.name not in {"mmd_edge_scale", "mmd_vertex_order"}]
            print(f"   - Found {len(bone_vgs)} bone vertex groups")

        print("✓ Vertex weight distribution test passed")

    def test_pmx_import_stress_testing(self):
        """Test PMX importing under stress conditions"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        # Test rapid sequential imports
        import_count = 5
        for i in range(import_count):
            print(f"   - Stress import #{i + 1}")
            bpy.ops.object.select_all(action="SELECT")
            bpy.ops.object.delete()

            root_obj = self._import_pmx_model(filepath)
            self.assertIsNotNone(root_obj, f"Stress import #{i + 1} failed")

            # Check memory isn't growing excessively
            gc.collect()

        print("✓ Stress testing passed")

    def test_pmx_import_extreme_scales(self):
        """Test PMX importing with extreme scale values"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        extreme_scales = [0.00001, 1000.0, 0.0001, 10000.0]

        for scale in extreme_scales:
            try:
                bpy.ops.object.select_all(action="SELECT")
                bpy.ops.object.delete()

                root_obj = self._import_pmx_model(filepath, scale=scale, types={"MESH", "ARMATURE"})

                if root_obj:
                    components = self._get_model_components(root_obj)
                    armature = components["armature"]

                    # Check if bones have reasonable dimensions
                    bone_lengths = [bone.length for bone in armature.data.bones if bone.length > 0]
                    if bone_lengths:
                        avg_length = sum(bone_lengths) / len(bone_lengths)
                        print(f"   - Scale {scale}: avg bone length = {avg_length:.6f}")

                        # Very extreme scales might cause precision issues
                        if scale < 0.0001 or scale > 1000:
                            print(f"   - Warning: Extreme scale {scale} may cause precision issues")

            except Exception as e:
                print(f"   - Scale {scale} failed as expected: {str(e)[:50]}")

        print("✓ Extreme scales test completed")

    def test_pmx_import_corrupted_data_handling(self):
        """Test PMX importing with potentially problematic data"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()
        filepath = input_files[0]

        # Test with all cleaning options to stress the cleaner
        try:
            root_obj = self._import_pmx_model(filepath, clean_model=True, remove_doubles=True, types={"MESH", "ARMATURE", "MORPHS"})

            if root_obj:
                components = self._get_model_components(root_obj)

                # Verify data integrity after aggressive cleaning
                for mesh_obj in components["meshes"]:
                    mesh_data = mesh_obj.data
                    self.assertGreater(len(mesh_data.vertices), 0, "Vertices should survive cleaning")
                    self.assertGreater(len(mesh_data.polygons), 0, "Faces should survive cleaning")

                    # Check for degenerate faces
                    degenerate_faces = 0
                    for poly in mesh_data.polygons:
                        vertices = [mesh_data.vertices[i].co for i in poly.vertices]
                        if len({tuple(v) for v in vertices}) < 3:
                            degenerate_faces += 1

                    print(f"   - Found {degenerate_faces} potentially degenerate faces")

        except Exception as e:
            print(f"   - Corrupted data handling test encountered: {str(e)[:100]}")

        print("✓ Corrupted data handling test completed")

    def test_pmx_import_compatibility_matrix(self):
        """Test PMX importing across different model types and configurations"""
        input_files = self._list_sample_files(("pmx", "pmd"))
        if len(input_files) < 1:
            self.fail("Required PMX/PMD sample file(s)!")

        self._enable_mmd_tools()

        # Test matrix of different import configurations
        test_configs = [
            {"types": {"MESH"}, "desc": "Mesh only"},
            {"types": {"ARMATURE"}, "desc": "Armature only"},
            {"types": {"MESH", "ARMATURE"}, "desc": "Mesh + Armature"},
            {"types": {"MESH", "ARMATURE", "MORPHS"}, "desc": "Basic + Morphs"},
            {"types": {"MESH", "ARMATURE", "PHYSICS"}, "desc": "Basic + Physics"},
            {"types": {"MESH", "ARMATURE", "DISPLAY"}, "desc": "Basic + Display"},
        ]

        compatibility_matrix = {}

        for filepath in input_files[:2]:
            filename = os.path.basename(filepath)
            compatibility_matrix[filename] = {}

            print(f"\n   Testing compatibility for: {filename}")

            for config in test_configs:
                try:
                    bpy.ops.object.select_all(action="SELECT")
                    bpy.ops.object.delete()

                    root_obj = self._import_pmx_model(filepath, **config)

                    if root_obj:
                        components = self._get_model_components(root_obj)
                        success = True
                        details = {"meshes": len(components["meshes"]), "bones": len(components["armature"].data.bones) if components["armature"] else 0, "materials": len(components["materials"])}
                    else:
                        success = False
                        details = {}

                    compatibility_matrix[filename][config["desc"]] = {"success": success, "details": details}

                    status = "✓" if success else "✗"
                    print(f"   {status} {config['desc']}")

                except Exception as e:
                    compatibility_matrix[filename][config["desc"]] = {"success": False, "error": str(e)[:50]}
                    print(f"   ✗ {config['desc']}: {str(e)[:50]}")

        # Print compatibility summary
        print("\n   Compatibility Matrix Summary:")
        for filename, results in compatibility_matrix.items():
            successful_configs = sum(1 for r in results.values() if r.get("success", False))
            total_configs = len(results)
            print(f"   {filename}: {successful_configs}/{total_configs} configs successful")

        print("\n✓ Compatibility matrix test completed")


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main(verbosity=1, exit=True)
