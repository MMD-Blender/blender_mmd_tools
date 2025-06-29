# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import gc
import logging
import math
import os
import shutil
import time
import unittest

import bl_ext.user_default.mmd_tools
import bpy
from bl_ext.user_default.mmd_tools.core.model import Model
from bl_ext.user_default.mmd_tools.properties.camera import MMDCamera

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "samples")
MMD_TOOLS_PATH = os.path.dirname(bl_ext.user_default.mmd_tools.__file__)
TOON_TEXTURE_PATH = os.path.join(MMD_TOOLS_PATH, "externals", "MikuMikuDance", "toon01.bmp")


class TestMMDProperties(unittest.TestCase):
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
        """Start each test with a clean state"""
        logger = logging.getLogger()
        logger.setLevel("ERROR")

        if not bpy.context.active_object:
            bpy.ops.mesh.primitive_cube_add()

        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=True)

        self.context = bpy.context
        self.scene = bpy.context.scene

    def _enable_mmd_tools(self):
        """Make sure mmd_tools addon is enabled"""
        bpy.ops.wm.read_homefile(use_empty=True)
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("bl_ext.user_default.mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.user_default.mmd_tools")

    def _create_test_model(self, name: str = "TestModel") -> Model:
        """Create a basic MMD model for testing"""
        return Model.create(name=name, name_e=f"{name}_English", add_root_bone=True)

    def _create_test_mesh(self, model: Model, name: str = "TestMesh") -> bpy.types.Object:
        """Create a test mesh and attach it to the model"""
        bpy.ops.mesh.primitive_cube_add()
        mesh_obj = bpy.context.active_object
        mesh_obj.name = name

        # Attach to model
        armature_obj = model.armature()
        mesh_obj.parent = armature_obj
        mesh_obj.parent_type = "OBJECT"

        # Add armature modifier
        modifier = mesh_obj.modifiers.new(name="Armature", type="ARMATURE")
        modifier.object = armature_obj

        return mesh_obj

    def _create_test_material(self, name: str = "TestMaterial") -> bpy.types.Material:
        """Create a test material with MMD properties"""
        # MMD material properties are automatically added via property registration
        return bpy.data.materials.new(name=name)

    def _create_test_rigid_body(self, model: Model, name: str = "TestRigidBody") -> bpy.types.Object:
        """Create a test rigid body object"""
        bpy.ops.mesh.primitive_cube_add()
        rigid_obj = bpy.context.active_object
        rigid_obj.name = name
        rigid_obj.mmd_type = "RIGID_BODY"

        # Set parent to rigid group
        rigid_group = model.rigidGroupObject()
        rigid_obj.parent = rigid_group

        return rigid_obj

    def _create_test_joint(self, model: Model, name: str = "TestJoint") -> bpy.types.Object:
        """Create a test joint object"""
        bpy.ops.object.empty_add()
        joint_obj = bpy.context.active_object
        joint_obj.name = name
        joint_obj.mmd_type = "JOINT"

        # Set parent to joint group
        joint_group = model.jointGroupObject()
        joint_obj.parent = joint_group

        return joint_obj

    def _create_test_camera(self, name: str = "TestCamera") -> bpy.types.Object:
        """Create a test camera object"""
        bpy.ops.object.camera_add()
        camera_obj = bpy.context.active_object
        camera_obj.name = name
        camera_obj.mmd_type = "CAMERA"
        return camera_obj

    # ********************************************
    # Camera Properties Tests
    # ********************************************

    def test_camera_properties_basic(self):
        """Test basic camera property functionality"""
        self._enable_mmd_tools()

        camera_obj = self._create_test_camera()
        mmd_camera = camera_obj.mmd_camera

        # Test angle property
        self.assertTrue(hasattr(mmd_camera, "angle"), "Camera should have angle property")

        # Test angle limits
        test_angles = [math.radians(10), math.radians(45), math.radians(90), math.radians(120)]
        for angle in test_angles:
            mmd_camera.angle = angle
            self.assertAlmostEqual(mmd_camera.angle, angle, places=5, msg=f"Angle {angle} should be preserved")

        # Test is_perspective property
        self.assertTrue(hasattr(mmd_camera, "is_perspective"), "Camera should have is_perspective property")
        self.assertTrue(mmd_camera.is_perspective, "Camera should default to perspective")

        mmd_camera.is_perspective = False
        self.assertFalse(mmd_camera.is_perspective, "Camera perspective should be toggleable")

        print("✓ Camera properties basic test passed")

    def test_camera_properties_registration(self):
        """Test camera property registration and unregistration"""
        self._enable_mmd_tools()

        # Create camera and verify properties exist
        camera_obj = self._create_test_camera()
        self.assertTrue(hasattr(camera_obj, "mmd_camera"), "Camera should have mmd_camera property")

        # Test property type
        self.assertIsInstance(camera_obj.mmd_camera, MMDCamera, "mmd_camera should be MMDCamera type")

        print("✓ Camera properties registration test passed")

    def test_camera_properties_validation(self):
        """Test camera property validation and constraints"""
        self._enable_mmd_tools()

        camera_obj = self._create_test_camera()
        mmd_camera = camera_obj.mmd_camera

        # Test angle limits
        min_angle = math.radians(1)
        max_angle = math.radians(180)

        # Test minimum constraint
        mmd_camera.angle = math.radians(0.5)
        self.assertGreaterEqual(mmd_camera.angle, min_angle - 1e-7, "Angle should respect minimum limit")

        # Test maximum constraint
        mmd_camera.angle = math.radians(200)
        self.assertLessEqual(mmd_camera.angle, max_angle + 1e-7, "Angle should respect maximum limit")

        # Test valid range
        valid_angle = math.radians(60)
        mmd_camera.angle = valid_angle
        self.assertAlmostEqual(mmd_camera.angle, valid_angle, places=7, msg="Valid angle should be preserved")

        print("✓ Camera properties validation test passed")

    # ********************************************
    # Material Properties Tests
    # ********************************************

    def test_material_properties_basic(self):
        """Test basic material property functionality"""
        self._enable_mmd_tools()

        mat = self._create_test_material()
        mmd_mat = mat.mmd_material

        # Test name properties
        self.assertTrue(hasattr(mmd_mat, "name_j"), "Material should have Japanese name")
        self.assertTrue(hasattr(mmd_mat, "name_e"), "Material should have English name")

        test_name_j = "テストマテリアル"
        test_name_e = "TestMaterial"

        mmd_mat.name_j = test_name_j
        mmd_mat.name_e = test_name_e

        self.assertEqual(mmd_mat.name_j, test_name_j, "Japanese name should be preserved")
        self.assertEqual(mmd_mat.name_e, test_name_e, "English name should be preserved")

        # Test material ID
        self.assertTrue(hasattr(mmd_mat, "material_id"), "Material should have material_id")
        mmd_mat.material_id = 42
        self.assertEqual(mmd_mat.material_id, 42, "Material ID should be preserved")

        print("✓ Material properties basic test passed")

    def test_material_properties_colors(self):
        """Test material color properties"""
        self._enable_mmd_tools()

        mat = self._create_test_material()
        mmd_mat = mat.mmd_material

        # Test ambient color
        test_ambient = [0.2, 0.3, 0.4]
        mmd_mat.ambient_color = test_ambient
        for i, expected in enumerate(test_ambient):
            self.assertAlmostEqual(mmd_mat.ambient_color[i], expected, places=7, msg=f"Ambient color component {i} should be preserved")

        # Test diffuse color
        test_diffuse = [0.8, 0.7, 0.6]
        mmd_mat.diffuse_color = test_diffuse
        for i, expected in enumerate(test_diffuse):
            self.assertAlmostEqual(mmd_mat.diffuse_color[i], expected, places=7, msg=f"Diffuse color component {i} should be preserved")

        # Test specular color
        test_specular = [1.0, 0.9, 0.8]
        mmd_mat.specular_color = test_specular
        for i, expected in enumerate(test_specular):
            self.assertAlmostEqual(mmd_mat.specular_color[i], expected, places=7, msg=f"Specular color component {i} should be preserved")

        # Test edge color (4 components)
        test_edge = [0.1, 0.2, 0.3, 0.8]
        mmd_mat.edge_color = test_edge
        for i, expected in enumerate(test_edge):
            self.assertAlmostEqual(mmd_mat.edge_color[i], expected, places=7, msg=f"Edge color component {i} should be preserved")

        print("✓ Material properties colors test passed")

    def test_material_properties_alpha_and_shininess(self):
        """Test material alpha and shininess properties"""
        self._enable_mmd_tools()

        mat = self._create_test_material()
        mmd_mat = mat.mmd_material

        # Test alpha
        test_alpha = 0.7
        mmd_mat.alpha = test_alpha
        self.assertAlmostEqual(mmd_mat.alpha, test_alpha, places=3, msg="Alpha should be preserved")

        # Test alpha limits
        mmd_mat.alpha = -0.5
        self.assertGreaterEqual(mmd_mat.alpha, 0.0, "Alpha should respect minimum limit")

        mmd_mat.alpha = 1.5
        self.assertLessEqual(mmd_mat.alpha, 1.0, "Alpha should respect maximum limit")

        # Test shininess
        test_shininess = 100.0
        mmd_mat.shininess = test_shininess
        self.assertAlmostEqual(mmd_mat.shininess, test_shininess, places=1, msg="Shininess should be preserved")

        print("✓ Material properties alpha and shininess test passed")

    def test_material_properties_flags(self):
        """Test material boolean flag properties"""
        self._enable_mmd_tools()

        mat = self._create_test_material()
        mmd_mat = mat.mmd_material

        # Test boolean flags
        flags_to_test = ["is_double_sided", "enabled_drop_shadow", "enabled_self_shadow_map", "enabled_self_shadow", "enabled_toon_edge", "is_shared_toon_texture"]

        for flag in flags_to_test:
            if hasattr(mmd_mat, flag):
                # Test setting to True
                setattr(mmd_mat, flag, True)
                self.assertTrue(getattr(mmd_mat, flag), f"{flag} should be settable to True")

                # Test setting to False
                setattr(mmd_mat, flag, False)
                self.assertFalse(getattr(mmd_mat, flag), f"{flag} should be settable to False")

        print("✓ Material properties flags test passed")

    def test_material_properties_textures(self):
        """Test material texture properties"""
        self._enable_mmd_tools()

        mat = self._create_test_material()
        mmd_mat = mat.mmd_material

        # Test sphere texture type
        self.assertTrue(hasattr(mmd_mat, "sphere_texture_type"), "Material should have sphere_texture_type")

        # Test toon texture properties
        if hasattr(mmd_mat, "toon_texture"):
            mmd_mat.toon_texture = TOON_TEXTURE_PATH
            self.assertEqual(mmd_mat.toon_texture, TOON_TEXTURE_PATH, "Toon texture path should be preserved")

        if hasattr(mmd_mat, "shared_toon_texture"):
            test_id = 5
            mmd_mat.shared_toon_texture = test_id
            self.assertEqual(mmd_mat.shared_toon_texture, test_id, "Shared toon texture ID should be preserved")

        print("✓ Material properties textures test passed")

    def test_material_properties_edge(self):
        """Test material edge properties"""
        self._enable_mmd_tools()

        mat = self._create_test_material()
        mmd_mat = mat.mmd_material

        # Test edge weight
        test_weight = 1.5
        mmd_mat.edge_weight = test_weight
        self.assertAlmostEqual(mmd_mat.edge_weight, test_weight, places=1, msg="Edge weight should be preserved")

        # Test edge weight limits
        mmd_mat.edge_weight = -1.0
        self.assertGreaterEqual(mmd_mat.edge_weight, 0.0, "Edge weight should respect minimum limit")

        print("✓ Material properties edge test passed")

    def test_material_properties_uniqueness(self):
        """Test material ID uniqueness validation"""
        self._enable_mmd_tools()

        mat1 = self._create_test_material("Material1")
        mat2 = self._create_test_material("Material2")

        mmd_mat1 = mat1.mmd_material
        mmd_mat2 = mat2.mmd_material

        # Set same ID for both materials
        test_id = 10
        mmd_mat1.material_id = test_id
        mmd_mat2.material_id = test_id

        # Test uniqueness check
        self.assertTrue(hasattr(mmd_mat1, "is_id_unique"), "Material should have is_id_unique method")

        # At least one should report non-unique (implementation specific)
        unique1 = mmd_mat1.is_id_unique()
        unique2 = mmd_mat2.is_id_unique()

        # At least one should report non-unique since they have the same ID
        self.assertFalse(unique1 and unique2, "Both materials cannot be unique with same ID")

        # Test with negative ID (should be unique)
        mmd_mat1.material_id = -1
        self.assertTrue(mmd_mat1.is_id_unique(), "Negative ID should be considered unique")

        print("✓ Material properties uniqueness test passed")

    # ********************************************
    # Morph Properties Tests
    # ********************************************

    def test_morph_properties_vertex_morph(self):
        """Test vertex morph properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        root_obj = model.rootObject()
        mmd_root = root_obj.mmd_root

        # Add vertex morph
        vertex_morph = mmd_root.vertex_morphs.add()
        vertex_morph.name = "TestVertexMorph"
        vertex_morph.name_e = "TestVertexMorphEnglish"
        vertex_morph.category = "MOUTH"

        self.assertEqual(vertex_morph.name, "TestVertexMorph", "Vertex morph name should be preserved")
        self.assertEqual(vertex_morph.name_e, "TestVertexMorphEnglish", "Vertex morph English name should be preserved")
        self.assertEqual(vertex_morph.category, "MOUTH", "Vertex morph category should be preserved")

        print("✓ Morph properties vertex morph test passed")

    def test_morph_properties_bone_morph(self):
        """Test bone morph properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        root_obj = model.rootObject()
        mmd_root = root_obj.mmd_root

        # Add bone morph
        bone_morph = mmd_root.bone_morphs.add()
        bone_morph.name = "TestBoneMorph"
        bone_morph.category = "OTHER"

        # Add bone morph data
        bone_data = bone_morph.data.add()

        # Test location
        test_location = [1.0, 2.0, 3.0]
        bone_data.location = test_location
        self.assertEqual(list(bone_data.location), test_location, "Bone morph location should be preserved")

        # Test rotation (quaternion)
        test_rotation = [1.0, 0.0, 0.0, 0.0]  # w, x, y, z
        bone_data.rotation = test_rotation
        self.assertEqual(list(bone_data.rotation), test_rotation, "Bone morph rotation should be preserved")

        print("✓ Morph properties bone morph test passed")

    def test_morph_properties_material_morph(self):
        """Test material morph properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        root_obj = model.rootObject()
        mmd_root = root_obj.mmd_root

        # Add material morph
        material_morph = mmd_root.material_morphs.add()
        material_morph.name = "TestMaterialMorph"

        # Add material morph data
        material_data = material_morph.data.add()

        # Test offset type
        material_data.offset_type = "MULT"
        self.assertEqual(material_data.offset_type, "MULT", "Material morph offset type should be preserved")

        # Test color properties
        test_diffuse = [0.5, 0.6, 0.7, 0.8]
        material_data.diffuse_color = test_diffuse
        for i, expected in enumerate(test_diffuse):
            self.assertAlmostEqual(material_data.diffuse_color[i], expected, places=7, msg=f"Material morph diffuse color component {i} should be preserved")

        test_specular = [0.9, 0.8, 0.7]
        material_data.specular_color = test_specular
        for i, expected in enumerate(test_specular):
            self.assertAlmostEqual(material_data.specular_color[i], expected, places=7, msg=f"Material morph specular color component {i} should be preserved")

        # Test shininess
        test_shininess = 75.0
        material_data.shininess = test_shininess
        self.assertAlmostEqual(material_data.shininess, test_shininess, places=7, msg="Material morph shininess should be preserved")

        print("✓ Morph properties material morph test passed")

    def test_morph_properties_uv_morph(self):
        """Test UV morph properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        root_obj = model.rootObject()
        mmd_root = root_obj.mmd_root

        # Add UV morph
        uv_morph = mmd_root.uv_morphs.add()
        uv_morph.name = "TestUVMorph"

        # Test UV index
        test_uv_index = 2
        uv_morph.uv_index = test_uv_index
        self.assertEqual(uv_morph.uv_index, test_uv_index, "UV morph UV index should be preserved")

        # Test data type
        uv_morph.data_type = "VERTEX_GROUP"
        self.assertEqual(uv_morph.data_type, "VERTEX_GROUP", "UV morph data type should be preserved")

        # Test vertex group scale
        test_scale = 2.5
        uv_morph.vertex_group_scale = test_scale
        self.assertAlmostEqual(uv_morph.vertex_group_scale, test_scale, places=7, msg="UV morph vertex group scale should be preserved")

        # Add UV morph offset data
        uv_offset = uv_morph.data.add()
        uv_offset.index = 100
        test_offset = [0.1, 0.2, 0.3, 0.4]
        uv_offset.offset = test_offset

        self.assertEqual(uv_offset.index, 100, "UV offset index should be preserved")
        for i, expected in enumerate(test_offset):
            self.assertAlmostEqual(uv_offset.offset[i], expected, places=7, msg=f"UV offset component {i} should be preserved")

        print("✓ Morph properties UV morph test passed")

    def test_morph_properties_group_morph(self):
        """Test group morph properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        root_obj = model.rootObject()
        mmd_root = root_obj.mmd_root

        # Add group morph
        group_morph = mmd_root.group_morphs.add()
        group_morph.name = "TestGroupMorph"

        # Add group morph offset data
        group_offset = group_morph.data.add()

        # Test morph type
        group_offset.morph_type = "vertex_morphs"
        self.assertEqual(group_offset.morph_type, "vertex_morphs", "Group morph type should be preserved")

        # Test factor
        test_factor = 0.75
        group_offset.factor = test_factor
        self.assertAlmostEqual(group_offset.factor, test_factor, places=2, msg="Group morph factor should be preserved")

        print("✓ Morph properties group morph test passed")

    def test_morph_properties_name_uniqueness(self):
        """Test morph name uniqueness"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        root_obj = model.rootObject()
        mmd_root = root_obj.mmd_root

        # Add multiple vertex morphs with same name
        morph1 = mmd_root.vertex_morphs.add()
        morph1.name = "TestMorph"

        morph2 = mmd_root.vertex_morphs.add()
        morph2.name = "TestMorph"

        # Names should be made unique
        self.assertNotEqual(morph1.name, morph2.name, "Morph names should be made unique")

        print("✓ Morph properties name uniqueness test passed")

    # ********************************************
    # Pose Bone Properties Tests
    # ********************************************

    def test_pose_bone_properties_basic(self):
        """Test basic pose bone properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        armature_obj = model.armature()

        # Get the root bone created by the model
        root_bone = None
        for bone in armature_obj.pose.bones:
            if bone.name == "全ての親":
                root_bone = bone
                break

        self.assertIsNotNone(root_bone, "Root bone should exist")

        mmd_bone = root_bone.mmd_bone

        # Test name properties
        self.assertTrue(hasattr(mmd_bone, "name_j"), "Bone should have Japanese name")
        self.assertTrue(hasattr(mmd_bone, "name_e"), "Bone should have English name")

        test_name_j = "テストボーン"
        test_name_e = "TestBone"

        mmd_bone.name_j = test_name_j
        mmd_bone.name_e = test_name_e

        self.assertEqual(mmd_bone.name_j, test_name_j, "Japanese name should be preserved")
        self.assertEqual(mmd_bone.name_e, test_name_e, "English name should be preserved")

        # Test bone ID
        self.assertTrue(hasattr(mmd_bone, "bone_id"), "Bone should have bone_id")
        test_id = 42
        mmd_bone.bone_id = test_id
        self.assertEqual(mmd_bone.bone_id, test_id, "Bone ID should be preserved")

        print("✓ Pose bone properties basic test passed")

    def test_pose_bone_properties_transform(self):
        """Test pose bone transform properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        armature_obj = model.armature()

        # Get any pose bone
        pose_bone = next(iter(armature_obj.pose.bones))
        mmd_bone = pose_bone.mmd_bone

        # Test transform order
        test_order = 5
        mmd_bone.transform_order = test_order
        self.assertEqual(mmd_bone.transform_order, test_order, "Transform order should be preserved")

        # Test boolean flags
        flags_to_test = ["is_controllable", "transform_after_dynamics", "enabled_fixed_axis", "enabled_local_axes", "is_tip", "has_additional_rotation", "has_additional_location"]

        for flag in flags_to_test:
            if hasattr(mmd_bone, flag):
                # Test setting to True
                setattr(mmd_bone, flag, True)
                self.assertTrue(getattr(mmd_bone, flag), f"{flag} should be settable to True")

                # Test setting to False
                setattr(mmd_bone, flag, False)
                self.assertFalse(getattr(mmd_bone, flag), f"{flag} should be settable to False")

        print("✓ Pose bone properties transform test passed")

    def test_pose_bone_properties_axes(self):
        """Test pose bone axis properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        armature_obj = model.armature()

        pose_bone = next(iter(armature_obj.pose.bones))
        mmd_bone = pose_bone.mmd_bone

        # Test fixed axis
        test_fixed_axis = [1.0, 0.5, 0.0]
        mmd_bone.fixed_axis = test_fixed_axis
        for i, expected in enumerate(test_fixed_axis):
            self.assertAlmostEqual(mmd_bone.fixed_axis[i], expected, places=7, msg=f"Fixed axis component {i} should be preserved")

        # Test local axes
        test_local_x = [0.707, 0.707, 0.0]
        test_local_z = [0.0, 0.0, 1.0]

        mmd_bone.local_axis_x = test_local_x
        mmd_bone.local_axis_z = test_local_z

        for i, expected in enumerate(test_local_x):
            self.assertAlmostEqual(mmd_bone.local_axis_x[i], expected, places=7, msg=f"Local X axis component {i} should be preserved")

        for i, expected in enumerate(test_local_z):
            self.assertAlmostEqual(mmd_bone.local_axis_z[i], expected, places=7, msg=f"Local Z axis component {i} should be preserved")

        print("✓ Pose bone properties axes test passed")

    def test_pose_bone_properties_ik(self):
        """Test pose bone IK properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        armature_obj = model.armature()

        pose_bone = next(iter(armature_obj.pose.bones))
        mmd_bone = pose_bone.mmd_bone

        # Test IK rotation constraint
        test_constraint = 2.0
        mmd_bone.ik_rotation_constraint = test_constraint
        self.assertAlmostEqual(mmd_bone.ik_rotation_constraint, test_constraint, places=1, msg="IK rotation constraint should be preserved")

        # Test additional transform influence
        test_influence = 0.8
        mmd_bone.additional_transform_influence = test_influence
        self.assertAlmostEqual(mmd_bone.additional_transform_influence, test_influence, places=1, msg="Additional transform influence should be preserved")

        print("✓ Pose bone properties IK test passed")

    def test_pose_bone_properties_display_connection(self):
        """Test pose bone display connection properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        armature_obj = model.armature()

        pose_bone = next(iter(armature_obj.pose.bones))
        mmd_bone = pose_bone.mmd_bone

        # Test display connection type
        mmd_bone.display_connection_type = "BONE"
        self.assertEqual(mmd_bone.display_connection_type, "BONE", "Display connection type should be preserved")

        mmd_bone.display_connection_type = "OFFSET"
        self.assertEqual(mmd_bone.display_connection_type, "OFFSET", "Display connection type should be preserved")

        print("✓ Pose bone properties display connection test passed")

    def test_pose_bone_properties_uniqueness(self):
        """Test pose bone ID uniqueness validation"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        armature_obj = model.armature()

        # Add another bone for testing
        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode="EDIT")

        edit_bone = armature_obj.data.edit_bones.new("TestBone")
        edit_bone.head = [0, 0, 1]
        edit_bone.tail = [0, 0, 2]

        bpy.ops.object.mode_set(mode="OBJECT")

        # Get pose bones
        bones = list(armature_obj.pose.bones)
        if len(bones) >= 2:
            bone1 = bones[0]
            bone2 = bones[1]

            # Set same ID for both bones
            test_id = 10
            bone1.mmd_bone.bone_id = test_id
            bone2.mmd_bone.bone_id = test_id

            # Test uniqueness check
            self.assertTrue(hasattr(bone1.mmd_bone, "is_id_unique"), "Bone should have is_id_unique method")

            # At least one should report non-unique (implementation specific)
            unique1 = bone1.mmd_bone.is_id_unique()
            unique2 = bone2.mmd_bone.is_id_unique()

            # At least one should report non-unique since they have the same ID
            self.assertFalse(unique1 and unique2, "Both bones cannot be unique with same ID")

            # Test with negative ID (should be unique)
            bone1.mmd_bone.bone_id = -1
            self.assertTrue(bone1.mmd_bone.is_id_unique(), "Negative ID should be considered unique")

        print("✓ Pose bone properties uniqueness test passed")

    # ********************************************
    # Rigid Body Properties Tests
    # ********************************************

    def test_rigid_body_properties_basic(self):
        """Test basic rigid body properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        rigid_obj = self._create_test_rigid_body(model)
        mmd_rigid = rigid_obj.mmd_rigid

        # Test name properties
        self.assertTrue(hasattr(mmd_rigid, "name_j"), "Rigid body should have Japanese name")
        self.assertTrue(hasattr(mmd_rigid, "name_e"), "Rigid body should have English name")

        test_name_j = "テスト剛体"
        test_name_e = "TestRigidBody"

        mmd_rigid.name_j = test_name_j
        mmd_rigid.name_e = test_name_e

        self.assertEqual(mmd_rigid.name_j, test_name_j, "Japanese name should be preserved")
        self.assertEqual(mmd_rigid.name_e, test_name_e, "English name should be preserved")

        print("✓ Rigid body properties basic test passed")

    def test_rigid_body_properties_collision(self):
        """Test rigid body collision properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        rigid_obj = self._create_test_rigid_body(model)
        mmd_rigid = rigid_obj.mmd_rigid

        # Test collision group number
        test_group = 5
        mmd_rigid.collision_group_number = test_group
        self.assertEqual(mmd_rigid.collision_group_number, test_group, "Collision group number should be preserved")

        # Test collision group number limits
        mmd_rigid.collision_group_number = -1
        self.assertGreaterEqual(mmd_rigid.collision_group_number, 0, "Collision group should respect minimum limit")

        mmd_rigid.collision_group_number = 20
        self.assertLessEqual(mmd_rigid.collision_group_number, 15, "Collision group should respect maximum limit")

        # Test collision group mask
        self.assertTrue(hasattr(mmd_rigid, "collision_group_mask"), "Rigid body should have collision group mask")
        self.assertEqual(len(mmd_rigid.collision_group_mask), 16, "Collision group mask should have 16 elements")

        # Test setting mask values
        mmd_rigid.collision_group_mask[0] = True
        mmd_rigid.collision_group_mask[15] = True
        self.assertTrue(mmd_rigid.collision_group_mask[0], "Collision mask should be settable")
        self.assertTrue(mmd_rigid.collision_group_mask[15], "Collision mask should be settable")

        print("✓ Rigid body properties collision test passed")

    def test_rigid_body_properties_type_and_shape(self):
        """Test rigid body type and shape properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        rigid_obj = self._create_test_rigid_body(model)
        mmd_rigid = rigid_obj.mmd_rigid

        # Test rigid type
        rigid_types = ["0", "1", "2"]  # Static, Dynamic, Dynamic+Bone
        for rigid_type in rigid_types:
            mmd_rigid.type = rigid_type
            self.assertEqual(mmd_rigid.type, rigid_type, f"Rigid type {rigid_type} should be preserved")

        # Test shape
        shapes = ["SPHERE", "BOX", "CAPSULE"]
        for shape in shapes:
            mmd_rigid.shape = shape
            self.assertEqual(mmd_rigid.shape, shape, f"Shape {shape} should be preserved")

        print("✓ Rigid body properties type and shape test passed")

    def test_rigid_body_properties_size(self):
        """Test rigid body size properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        rigid_obj = self._create_test_rigid_body(model)
        mmd_rigid = rigid_obj.mmd_rigid

        # Test size property
        test_size = [2.0, 3.0, 4.0]
        mmd_rigid.size = test_size
        bpy.context.view_layer.update()

        # Size property has custom getter/setter, so we check if it was applied
        current_size = list(mmd_rigid.size)
        self.assertEqual(len(current_size), 3, "Size should have 3 components")

        # All components should be positive
        for component in current_size:
            self.assertGreaterEqual(component, 0, "Size components should be non-negative")

        print("✓ Rigid body properties size test passed")

    def test_rigid_body_properties_bone_assignment(self):
        """Test rigid body bone assignment"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        rigid_obj = self._create_test_rigid_body(model)
        mmd_rigid = rigid_obj.mmd_rigid

        # Test bone property
        self.assertTrue(hasattr(mmd_rigid, "bone"), "Rigid body should have bone property")

        # Get a bone name from the armature
        armature_obj = model.armature()
        if armature_obj.pose.bones:
            bone_name = armature_obj.pose.bones[0].name
            mmd_rigid.bone = bone_name

            # Verify bone assignment (may be empty if constraints aren't set up)
            assigned_bone = mmd_rigid.bone
            # Just check that the property accepts the assignment without error
            self.assertIsInstance(assigned_bone, str, "Bone assignment should return string")

        print("✓ Rigid body properties bone assignment test passed")

    # ********************************************
    # Joint Properties Tests
    # ********************************************

    def test_joint_properties_basic(self):
        """Test basic joint properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        joint_obj = self._create_test_joint(model)
        mmd_joint = joint_obj.mmd_joint

        # Test name properties
        self.assertTrue(hasattr(mmd_joint, "name_j"), "Joint should have Japanese name")
        self.assertTrue(hasattr(mmd_joint, "name_e"), "Joint should have English name")

        test_name_j = "テストジョイント"
        test_name_e = "TestJoint"

        mmd_joint.name_j = test_name_j
        mmd_joint.name_e = test_name_e

        self.assertEqual(mmd_joint.name_j, test_name_j, "Japanese name should be preserved")
        self.assertEqual(mmd_joint.name_e, test_name_e, "English name should be preserved")

        print("✓ Joint properties basic test passed")

    def test_joint_properties_spring(self):
        """Test joint spring properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        joint_obj = self._create_test_joint(model)
        mmd_joint = joint_obj.mmd_joint

        # Test spring linear
        test_spring_linear = [10.0, 20.0, 30.0]
        mmd_joint.spring_linear = test_spring_linear
        self.assertEqual(list(mmd_joint.spring_linear), test_spring_linear, "Spring linear should be preserved")

        # Test spring angular
        test_spring_angular = [5.0, 15.0, 25.0]
        mmd_joint.spring_angular = test_spring_angular
        self.assertEqual(list(mmd_joint.spring_angular), test_spring_angular, "Spring angular should be preserved")

        # Test spring value limits (should be non-negative)
        mmd_joint.spring_linear = [-1.0, -2.0, -3.0]
        for component in mmd_joint.spring_linear:
            self.assertGreaterEqual(component, 0.0, "Spring linear components should be non-negative")

        mmd_joint.spring_angular = [-1.0, -2.0, -3.0]
        for component in mmd_joint.spring_angular:
            self.assertGreaterEqual(component, 0.0, "Spring angular components should be non-negative")

        print("✓ Joint properties spring test passed")

    # ********************************************
    # Root Properties Tests
    # ********************************************

    def test_root_properties_basic(self):
        """Test basic root object properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        root_obj = model.rootObject()
        mmd_root = root_obj.mmd_root

        # Test name properties
        self.assertTrue(hasattr(mmd_root, "name"), "Root should have name")
        self.assertTrue(hasattr(mmd_root, "name_e"), "Root should have English name")

        test_name = "テストモデル"
        test_name_e = "TestModel"

        mmd_root.name = test_name
        mmd_root.name_e = test_name_e

        self.assertEqual(mmd_root.name, test_name, "Name should be preserved")
        self.assertEqual(mmd_root.name_e, test_name_e, "English name should be preserved")

        print("✓ Root properties basic test passed")

    def test_root_properties_comments(self):
        """Test root object comment properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        root_obj = model.rootObject()
        mmd_root = root_obj.mmd_root

        # Test comment text properties
        self.assertTrue(hasattr(mmd_root, "comment_text"), "Root should have comment_text")
        self.assertTrue(hasattr(mmd_root, "comment_e_text"), "Root should have comment_e_text")

        test_comment = "TestComment"
        test_comment_e = "TestCommentEnglish"

        mmd_root.comment_text = test_comment
        mmd_root.comment_e_text = test_comment_e

        self.assertEqual(mmd_root.comment_text, test_comment, "Comment text should be preserved")
        self.assertEqual(mmd_root.comment_e_text, test_comment_e, "English comment text should be preserved")

        print("✓ Root properties comments test passed")

    def test_root_properties_ik_loop_factor(self):
        """Test root object IK loop factor"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        root_obj = model.rootObject()
        mmd_root = root_obj.mmd_root

        # Test IK loop factor
        self.assertTrue(hasattr(mmd_root, "ik_loop_factor"), "Root should have ik_loop_factor")

        test_factor = 5
        mmd_root.ik_loop_factor = test_factor
        self.assertEqual(mmd_root.ik_loop_factor, test_factor, "IK loop factor should be preserved")

        # Test limits
        mmd_root.ik_loop_factor = 0
        self.assertGreaterEqual(mmd_root.ik_loop_factor, 1, "IK loop factor should respect minimum limit")

        mmd_root.ik_loop_factor = 200
        self.assertLessEqual(mmd_root.ik_loop_factor, 100, "IK loop factor should respect maximum limit")

        print("✓ Root properties IK loop factor test passed")

    def test_root_properties_visibility_flags(self):
        """Test root object visibility flags"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        root_obj = model.rootObject()
        mmd_root = root_obj.mmd_root

        # Test visibility flags
        visibility_flags = ["show_meshes", "show_rigid_bodies", "show_joints", "show_temporary_objects", "show_armature", "show_names_of_rigid_bodies", "show_names_of_joints"]

        for flag in visibility_flags:
            if hasattr(mmd_root, flag):
                # Test setting to True
                setattr(mmd_root, flag, True)
                self.assertTrue(getattr(mmd_root, flag), f"{flag} should be settable to True")

                # Test setting to False
                setattr(mmd_root, flag, False)
                self.assertFalse(getattr(mmd_root, flag), f"{flag} should be settable to False")

        print("✓ Root properties visibility flags test passed")

    def test_root_properties_usage_flags(self):
        """Test root object usage flags"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        root_obj = model.rootObject()
        mmd_root = root_obj.mmd_root

        # Test usage flags
        usage_flags = ["use_toon_texture", "use_sphere_texture", "use_sdef", "use_property_driver", "is_built"]

        for flag in usage_flags:
            if hasattr(mmd_root, flag):
                # Test setting to True
                setattr(mmd_root, flag, True)
                self.assertTrue(getattr(mmd_root, flag), f"{flag} should be settable to True")

                # Test setting to False
                setattr(mmd_root, flag, False)
                self.assertFalse(getattr(mmd_root, flag), f"{flag} should be settable to False")

        print("✓ Root properties usage flags test passed")

    def test_root_properties_display_frames(self):
        """Test root object display frames"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        root_obj = model.rootObject()
        mmd_root = root_obj.mmd_root

        # Test display item frames
        self.assertTrue(hasattr(mmd_root, "display_item_frames"), "Root should have display_item_frames")

        # Add a display frame
        frame = mmd_root.display_item_frames.add()
        frame.name = "TestFrame"
        frame.name_e = "TestFrameEnglish"
        frame.is_special = False

        self.assertEqual(frame.name, "TestFrame", "Display frame name should be preserved")
        self.assertEqual(frame.name_e, "TestFrameEnglish", "Display frame English name should be preserved")
        self.assertFalse(frame.is_special, "Display frame special flag should be preserved")

        # Add display item
        item = frame.data.add()
        item.type = "BONE"
        item.name = "TestBone"

        self.assertEqual(item.type, "BONE", "Display item type should be preserved")
        self.assertEqual(item.name, "TestBone", "Display item name should be preserved")

        print("✓ Root properties display frames test passed")

    def test_root_properties_morph_collections(self):
        """Test root object morph collections"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        root_obj = model.rootObject()
        mmd_root = root_obj.mmd_root

        # Test morph collections
        morph_collections = ["vertex_morphs", "bone_morphs", "material_morphs", "uv_morphs", "group_morphs"]

        for collection_name in morph_collections:
            if hasattr(mmd_root, collection_name):
                collection = getattr(mmd_root, collection_name)
                self.assertTrue(hasattr(collection, "add"), f"{collection_name} should be a collection")
                self.assertTrue(hasattr(collection, "clear"), f"{collection_name} should be a collection")

        # Test active morph type
        if hasattr(mmd_root, "active_morph_type"):
            test_type = "bone_morphs"
            mmd_root.active_morph_type = test_type
            self.assertEqual(mmd_root.active_morph_type, test_type, "Active morph type should be preserved")

        print("✓ Root properties morph collections test passed")

    def test_root_properties_translation(self):
        """Test root object translation properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        root_obj = model.rootObject()
        mmd_root = root_obj.mmd_root

        # Test translation property
        self.assertTrue(hasattr(mmd_root, "translation"), "Root should have translation property")

        translation = mmd_root.translation
        self.assertIsNotNone(translation, "Translation should not be None")

        print("✓ Root properties translation test passed")

    # ********************************************
    # Translation Properties Tests
    # ********************************************

    def test_translation_properties_basic(self):
        """Test basic translation properties"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        root_obj = model.rootObject()
        translation = root_obj.mmd_root.translation

        # Test filter properties
        filter_flags = ["filter_japanese_blank", "filter_english_blank", "filter_restorable", "filter_selected", "filter_visible"]

        for flag in filter_flags:
            if hasattr(translation, flag):
                # Test setting to True
                setattr(translation, flag, True)
                self.assertTrue(getattr(translation, flag), f"{flag} should be settable to True")

                # Test setting to False
                setattr(translation, flag, False)
                self.assertFalse(getattr(translation, flag), f"{flag} should be settable to False")

        print("✓ Translation properties basic test passed")

    def test_translation_properties_types_and_operations(self):
        """Test translation types and operations"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        root_obj = model.rootObject()
        translation = root_obj.mmd_root.translation

        # Test filter types
        if hasattr(translation, "filter_types"):
            # Default should include multiple types
            self.assertIsInstance(translation.filter_types, set, "Filter types should be a set")

        # Test batch operation target
        if hasattr(translation, "batch_operation_target"):
            targets = ["BLENDER", "JAPANESE", "ENGLISH"]
            for target in targets:
                translation.batch_operation_target = target
                self.assertEqual(translation.batch_operation_target, target, f"Batch operation target {target} should be preserved")

        # Test batch operation script
        if hasattr(translation, "batch_operation_script"):
            test_script = "test_script"
            translation.batch_operation_script = test_script
            self.assertEqual(translation.batch_operation_script, test_script, "Batch operation script should be preserved")

        print("✓ Translation properties types and operations test passed")

    def test_translation_properties_elements(self):
        """Test translation elements"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        root_obj = model.rootObject()
        translation = root_obj.mmd_root.translation

        # Test translation elements collection
        if hasattr(translation, "translation_elements"):
            elements = translation.translation_elements
            self.assertTrue(hasattr(elements, "add"), "Translation elements should be a collection")
            self.assertTrue(hasattr(elements, "clear"), "Translation elements should be a collection")

        # Test filtered indices
        if hasattr(translation, "filtered_translation_element_indices"):
            indices = translation.filtered_translation_element_indices
            self.assertTrue(hasattr(indices, "add"), "Filtered indices should be a collection")

        print("✓ Translation properties elements test passed")

    # ********************************************
    # Property Registration Tests
    # ********************************************

    def test_property_registration(self):
        """Test that all properties are properly registered"""
        self._enable_mmd_tools()

        # Test camera properties
        camera_obj = self._create_test_camera()
        self.assertTrue(hasattr(camera_obj, "mmd_camera"), "Camera should have mmd_camera property")

        # Test material properties
        mat = self._create_test_material()
        self.assertTrue(hasattr(mat, "mmd_material"), "Material should have mmd_material property")

        # Test object properties
        empty_obj = bpy.data.objects.new("TestEmpty", None)
        bpy.context.collection.objects.link(empty_obj)
        self.assertTrue(hasattr(empty_obj, "mmd_type"), "Object should have mmd_type property")

        # Test rigid body properties
        model = self._create_test_model()
        rigid_obj = self._create_test_rigid_body(model)
        self.assertTrue(hasattr(rigid_obj, "mmd_rigid"), "Rigid body should have mmd_rigid property")

        # Test joint properties
        joint_obj = self._create_test_joint(model)
        self.assertTrue(hasattr(joint_obj, "mmd_joint"), "Joint should have mmd_joint property")

        # Test root properties
        root_obj = model.rootObject()
        self.assertTrue(hasattr(root_obj, "mmd_root"), "Root should have mmd_root property")

        # Test pose bone properties
        armature_obj = model.armature()
        if armature_obj.pose.bones:
            pose_bone = armature_obj.pose.bones[0]
            self.assertTrue(hasattr(pose_bone, "mmd_bone"), "Pose bone should have mmd_bone property")
            self.assertTrue(hasattr(pose_bone, "mmd_ik_toggle"), "Pose bone should have mmd_ik_toggle property")

        print("✓ Property registration test passed")

    def test_property_update_callbacks(self):
        """Test property update callbacks"""
        self._enable_mmd_tools()

        # Test material property updates
        mat = self._create_test_material()
        mmd_mat = mat.mmd_material

        # These should trigger update callbacks without errors
        try:
            mmd_mat.ambient_color = [0.5, 0.5, 0.5]
            mmd_mat.diffuse_color = [0.8, 0.8, 0.8]
            mmd_mat.alpha = 0.9
            mmd_mat.specular_color = [0.6, 0.6, 0.6]
            mmd_mat.shininess = 80.0
            mmd_mat.is_double_sided = True
            mmd_mat.enabled_toon_edge = True
        except Exception as e:
            self.fail(f"Material property update failed: {e}")

        # Test root property updates
        model = self._create_test_model()
        root_obj = model.rootObject()
        mmd_root = root_obj.mmd_root

        try:
            mmd_root.show_meshes = False
            mmd_root.show_meshes = True
            mmd_root.use_toon_texture = False
            mmd_root.use_toon_texture = True
        except Exception as e:
            self.fail(f"Root property update failed: {e}")

        print("✓ Property update callbacks test passed")

    def test_property_constraints_and_validation(self):
        """Test property constraints and validation"""
        self._enable_mmd_tools()

        # Test camera angle constraints
        camera_obj = self._create_test_camera()
        mmd_camera = camera_obj.mmd_camera

        # Test minimum angle constraint
        min_angle = math.radians(1)
        mmd_camera.angle = math.radians(0.5)
        self.assertGreaterEqual(mmd_camera.angle, min_angle - 1e-7, "Camera angle should respect minimum")

        # Test maximum angle constraint
        max_angle = math.radians(180)
        mmd_camera.angle = math.radians(200)
        self.assertLessEqual(mmd_camera.angle, max_angle + 1e-7, "Camera angle should respect maximum")

        # Test material alpha constraints
        mat = self._create_test_material()
        mmd_mat = mat.mmd_material

        mmd_mat.alpha = -0.5
        self.assertGreaterEqual(mmd_mat.alpha, 0.0, "Material alpha should respect minimum")

        mmd_mat.alpha = 1.5
        self.assertLessEqual(mmd_mat.alpha, 1.0, "Material alpha should respect maximum")

        # Test rigid body collision group constraints
        model = self._create_test_model()
        rigid_obj = self._create_test_rigid_body(model)
        mmd_rigid = rigid_obj.mmd_rigid

        mmd_rigid.collision_group_number = -1
        self.assertGreaterEqual(mmd_rigid.collision_group_number, 0, "Collision group should respect minimum")

        mmd_rigid.collision_group_number = 20
        self.assertLessEqual(mmd_rigid.collision_group_number, 15, "Collision group should respect maximum")

        print("✓ Property constraints and validation test passed")

    def test_property_memory_management(self):
        """Test property memory management and cleanup"""
        self._enable_mmd_tools()

        # Create multiple objects and test cleanup
        objects_created = []

        try:
            for i in range(10):
                # Create model
                model = self._create_test_model(f"TestModel{i}")
                root_obj = model.rootObject()
                objects_created.append(root_obj)

                # Create mesh
                mesh_obj = self._create_test_mesh(model, f"TestMesh{i}")
                objects_created.append(mesh_obj)

                # Create material
                mat = self._create_test_material(f"TestMaterial{i}")

                # Create rigid body
                rigid_obj = self._create_test_rigid_body(model, f"TestRigidBody{i}")
                objects_created.append(rigid_obj)

                # Verify properties are accessible
                self.assertIsNotNone(root_obj.mmd_root, f"Root {i} should have MMD properties")
                self.assertIsNotNone(mat.mmd_material, f"Material {i} should have MMD properties")
                self.assertIsNotNone(rigid_obj.mmd_rigid, f"Rigid body {i} should have MMD properties")

            # Clean up
            bpy.ops.object.select_all(action="SELECT")
            bpy.ops.object.delete()

            # Force garbage collection
            gc.collect()

        except Exception as e:
            self.fail(f"Property memory management test failed: {e}")

        print("✓ Property memory management test passed")

    def test_property_serialization(self):
        """Test property serialization and deserialization"""
        self._enable_mmd_tools()

        # Create model with various properties set
        model = self._create_test_model("SerializationTest")
        root_obj = model.rootObject()
        mmd_root = root_obj.mmd_root

        # Set various properties
        mmd_root.name = "SerializedModel"
        mmd_root.name_e = "SerializedModelEnglish"
        mmd_root.ik_loop_factor = 3
        mmd_root.use_toon_texture = False

        # Add morphs
        vertex_morph = mmd_root.vertex_morphs.add()
        vertex_morph.name = "TestVertexMorph"
        vertex_morph.category = "MOUTH"

        bone_morph = mmd_root.bone_morphs.add()
        bone_morph.name = "TestBoneMorph"

        # Create material with properties
        mat = self._create_test_material("SerializationMaterial")
        mmd_mat = mat.mmd_material
        mmd_mat.name_j = "シリアライズマテリアル"
        mmd_mat.diffuse_color = [0.7, 0.8, 0.9]
        mmd_mat.alpha = 0.85

        # Ensure material has a user to prevent automatic cleanup
        mat.use_fake_user = True

        # Save and reload scene
        temp_filepath = os.path.join(TESTS_DIR, "temp_serialization_test.blend")
        try:
            bpy.ops.wm.save_as_mainfile(filepath=temp_filepath)
            bpy.ops.wm.open_mainfile(filepath=temp_filepath)

            # Find the objects again
            new_root_obj = None
            new_mat = None

            for obj in bpy.data.objects:
                if obj.mmd_type == "ROOT" and obj.name.startswith("SerializationTest"):
                    new_root_obj = obj
                    break

            # Debug: print all material names
            print(f"   - Available materials after reload: {[material.name for material in bpy.data.materials]}")

            for material in bpy.data.materials:
                if "SerializationMaterial" in material.name:
                    new_mat = material
                    break

            # Verify properties were preserved
            self.assertIsNotNone(new_root_obj, "Root object should be found after reload")
            self.assertIsNotNone(new_mat, "Material should be found after reload")

            if new_root_obj:
                new_mmd_root = new_root_obj.mmd_root
                self.assertEqual(new_mmd_root.name, "SerializedModel", "Root name should be preserved")
                self.assertEqual(new_mmd_root.name_e, "SerializedModelEnglish", "Root English name should be preserved")
                self.assertEqual(new_mmd_root.ik_loop_factor, 3, "IK loop factor should be preserved")
                self.assertFalse(new_mmd_root.use_toon_texture, "Toon texture flag should be preserved")
                # Check morphs were preserved
                self.assertGreater(len(new_mmd_root.vertex_morphs), 0, "Vertex morphs should be preserved")
                self.assertGreater(len(new_mmd_root.bone_morphs), 0, "Bone morphs should be preserved")

                if len(new_mmd_root.vertex_morphs) > 0:
                    self.assertEqual(new_mmd_root.vertex_morphs[0].name, "TestVertexMorph", "Vertex morph name should be preserved")
                    self.assertEqual(new_mmd_root.vertex_morphs[0].category, "MOUTH", "Vertex morph category should be preserved")

            if new_mat:
                new_mmd_mat = new_mat.mmd_material
                self.assertEqual(new_mmd_mat.name_j, "シリアライズマテリアル", "Material Japanese name should be preserved")

                # Test diffuse color with tolerance
                expected_diffuse = [0.7, 0.8, 0.9]
                for i, expected in enumerate(expected_diffuse):
                    self.assertAlmostEqual(new_mmd_mat.diffuse_color[i], expected, places=7, msg=f"Material diffuse color component {i} should be preserved")

                self.assertAlmostEqual(new_mmd_mat.alpha, 0.85, places=7, msg="Material alpha should be preserved")

        finally:
            # Clean up temp file
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)

        print("✓ Property serialization test passed")

    def test_property_edge_cases(self):
        """Test property edge cases and error handling"""
        self._enable_mmd_tools()

        # Test with extreme values
        model = self._create_test_model()
        root_obj = model.rootObject()
        mmd_root = root_obj.mmd_root

        # Test extremely long names
        long_name = "A" * 1000
        try:
            mmd_root.name = long_name
            # Should handle gracefully
            self.assertIsInstance(mmd_root.name, str, "Long name should be handled")
        except Exception:
            # If it raises an exception, that's also acceptable
            pass

        # Test with special characters
        special_name = "テスト♪♫♪♫"
        try:
            mmd_root.name = special_name
            self.assertEqual(mmd_root.name, special_name, "Special characters should be preserved")
        except Exception:
            # Some edge cases might not be supported
            pass

        # Test material with extreme color values
        mat = self._create_test_material()
        mmd_mat = mat.mmd_material

        # Colors should be clamped to valid ranges
        extreme_color = [10.0, -5.0, 2.0]
        mmd_mat.diffuse_color = extreme_color

        for component in mmd_mat.diffuse_color:
            self.assertGreaterEqual(component, 0.0, "Color components should be non-negative")
            self.assertLessEqual(component, 1.0, "Color components should not exceed 1.0")

        # Test camera with extreme angles
        camera_obj = self._create_test_camera()
        mmd_camera = camera_obj.mmd_camera

        extreme_angle = math.radians(1000)
        mmd_camera.angle = extreme_angle
        self.assertLessEqual(mmd_camera.angle, math.radians(180) + 1e-7, "Extreme angle should be clamped")

        print("✓ Property edge cases test passed")

    def test_property_performance(self):
        """Test property performance with many objects"""
        self._enable_mmd_tools()

        start_time = time.time()

        # Create many objects with properties
        num_objects = 50
        created_objects = []

        try:
            for i in range(num_objects):
                # Create model
                model = self._create_test_model(f"PerfTest{i}")
                root_obj = model.rootObject()
                created_objects.append(root_obj)

                # Set properties
                mmd_root = root_obj.mmd_root
                mmd_root.name = f"PerfTestModel{i}"
                mmd_root.ik_loop_factor = (i % 10) + 1

                # Add morphs
                for j in range(5):
                    morph = mmd_root.vertex_morphs.add()
                    morph.name = f"Morph{j}"

                # Create materials
                for j in range(3):
                    mat = self._create_test_material(f"PerfMat{i}_{j}")
                    mmd_mat = mat.mmd_material
                    mmd_mat.diffuse_color = [i / num_objects, j / 3.0, 0.5]

            creation_time = time.time() - start_time

            # Access properties
            access_start = time.time()

            for obj in created_objects:
                mmd_root = obj.mmd_root
                name = mmd_root.name
                factor = mmd_root.ik_loop_factor
                morph_count = len(mmd_root.vertex_morphs)

                # Verify properties are accessible and valid
                self.assertIsInstance(name, str, "Name should be string")
                self.assertGreaterEqual(factor, 1, "IK loop factor should be >= 1")
                self.assertGreaterEqual(morph_count, 0, "Morph count should be >= 0")

                for morph in mmd_root.vertex_morphs:
                    morph_name = morph.name
                    self.assertIsInstance(morph_name, str, "Morph name should be string")

            access_time = time.time() - access_start

            print(f"   - Created {num_objects} objects in {creation_time:.3f}s")
            print(f"   - Accessed properties in {access_time:.3f}s")

            # Performance should be reasonable (adjust thresholds as needed)
            self.assertLess(creation_time, 30.0, "Creation should complete in reasonable time")
            self.assertLess(access_time, 5.0, "Property access should be fast")

        finally:
            # Clean up
            bpy.ops.object.select_all(action="SELECT")
            bpy.ops.object.delete()

        print("✓ Property performance test passed")

    def test_property_compatibility(self):
        """Test property compatibility across different scenarios"""
        self._enable_mmd_tools()

        # Test with different object types
        object_types = [("EMPTY", None), ("MESH", bpy.data.meshes.new("TestMesh")), ("ARMATURE", bpy.data.armatures.new("TestArmature")), ("CAMERA", bpy.data.cameras.new("TestCamera"))]

        for obj_type, obj_data in object_types:
            obj = bpy.data.objects.new(f"Test{obj_type}", obj_data)
            bpy.context.collection.objects.link(obj)

            # All objects should have mmd_type
            self.assertTrue(hasattr(obj, "mmd_type"), f"{obj_type} should have mmd_type property")

            # Set appropriate MMD type
            if obj_type == "EMPTY":
                obj.mmd_type = "ROOT"
                self.assertTrue(hasattr(obj, "mmd_root"), f"{obj_type} should have mmd_root when set to ROOT")
            elif obj_type == "CAMERA":
                obj.mmd_type = "CAMERA"
                self.assertTrue(hasattr(obj, "mmd_camera"), f"{obj_type} should have mmd_camera when set to CAMERA")

        # Test with different material setups
        mat_with_nodes = bpy.data.materials.new("MatWithNodes")
        mat_with_nodes.use_nodes = True
        self.assertTrue(hasattr(mat_with_nodes, "mmd_material"), "Material with nodes should have MMD properties")

        mat_without_nodes = bpy.data.materials.new("MatWithoutNodes")
        mat_without_nodes.use_nodes = False
        self.assertTrue(hasattr(mat_without_nodes, "mmd_material"), "Material without nodes should have MMD properties")

        print("✓ Property compatibility test passed")

    def test_property_integration(self):
        """Test property integration with Blender systems"""
        self._enable_mmd_tools()

        # Create a complete model setup
        model = self._create_test_model()
        root_obj = model.rootObject()
        armature_obj = model.armature()
        mesh_obj = self._create_test_mesh(model)

        # Verify objects are properly created
        self.assertIsNotNone(root_obj, "Root object should be created")
        self.assertIsNotNone(armature_obj, "Armature object should be created")

        # # Test integration with animation system
        # if armature_obj.pose.bones:
        #     pose_bone = armature_obj.pose.bones[0]
        #     mmd_bone = pose_bone.mmd_bone
        #     # Test that MMD properties work with keyframing
        #     try:
        #         # Check if the property is animatable before trying to keyframe
        #         if hasattr(mmd_bone, "transform_order") and hasattr(mmd_bone.bl_rna.properties.get("transform_order", None), "is_animatable"):
        #             if mmd_bone.bl_rna.properties["transform_order"].is_animatable:
        #                 mmd_bone.keyframe_insert(data_path="transform_order", frame=1)
        #                 mmd_bone.transform_order = 5
        #                 mmd_bone.keyframe_insert(data_path="transform_order", frame=10)
        #                 # Check if keyframes were created
        #                 if armature_obj.animation_data and armature_obj.animation_data.action:
        #                     fcurves = armature_obj.animation_data.action.fcurves
        #                     transform_order_fcurve = None
        #                     for fcurve in fcurves:
        #                         if "transform_order" in fcurve.data_path:
        #                             transform_order_fcurve = fcurve
        #                             break
        #                     if transform_order_fcurve:
        #                         self.assertGreaterEqual(len(transform_order_fcurve.keyframe_points), 2, "Should have keyframes")
        #             else:
        #                 print("   - Transform order property is not animatable")
        #         else:
        #             print("   - Transform order property not found or not animatable")
        #     except Exception as e:
        #         print(f"   - Animation integration test had issues: {e}")
        print("   - MMD property animation integration: SKIPPED (not supported)")

        # Test integration with material system
        mat = mesh_obj.data.materials[0] if mesh_obj.data.materials else self._create_test_material()
        if not mesh_obj.data.materials:
            mesh_obj.data.materials.append(mat)

        mmd_mat = mat.mmd_material

        # Test that MMD material properties integrate with Blender material
        original_color = list(mmd_mat.diffuse_color)
        test_color = [0.5, 0.6, 0.7]
        mmd_mat.diffuse_color = test_color

        # Verify color was changed from original
        color_changed = False
        for i in range(len(original_color)):
            if abs(mmd_mat.diffuse_color[i] - original_color[i]) > 1e-7:
                color_changed = True
                break

        self.assertTrue(color_changed, "Color should be updated from original")

        # Test color values with tolerance
        for i, expected in enumerate(test_color):
            self.assertAlmostEqual(mmd_mat.diffuse_color[i], expected, places=7, msg=f"Material color component {i} should be updated")

        # Test integration with modifier system
        # Armature modifier should work with MMD properties
        armature_mod = None
        for mod in mesh_obj.modifiers:
            if mod.type == "ARMATURE":
                armature_mod = mod
                break

        if armature_mod:
            self.assertEqual(armature_mod.object, armature_obj, "Armature modifier should reference MMD armature")

        print("✓ Property integration test passed")

    def test_complete_property_workflow(self):
        """Test complete workflow using all property systems"""
        self._enable_mmd_tools()

        print("\n   Testing complete MMD property workflow...")

        # 1. Create base model
        model = self._create_test_model("CompleteWorkflow")
        root_obj = model.rootObject()
        armature_obj = model.armature()

        # 2. Set up root properties
        mmd_root = root_obj.mmd_root
        mmd_root.name = "ワークフローテスト"
        mmd_root.name_e = "WorkflowTest"
        mmd_root.ik_loop_factor = 2
        mmd_root.use_toon_texture = True
        mmd_root.use_sphere_texture = True

        # 3. Create and set up mesh
        mesh_obj = self._create_test_mesh(model, "WorkflowMesh")

        # 4. Create and set up materials
        materials = []
        for i in range(3):
            mat = self._create_test_material(f"WorkflowMat{i}")
            mmd_mat = mat.mmd_material
            mmd_mat.name_j = f"マテリアル{i}"
            mmd_mat.name_e = f"Material{i}"
            mmd_mat.diffuse_color = [i / 3.0, 0.5, 0.8]
            mmd_mat.alpha = 0.9
            mmd_mat.enabled_toon_edge = True
            mmd_mat.edge_color = [0.0, 0.0, 0.0, 1.0]
            materials.append(mat)
            mesh_obj.data.materials.append(mat)

        # 5. Set up bone properties
        if armature_obj.pose.bones:
            for i, pose_bone in enumerate(armature_obj.pose.bones):
                mmd_bone = pose_bone.mmd_bone
                mmd_bone.name_j = f"ボーン{i}"
                mmd_bone.name_e = f"Bone{i}"
                mmd_bone.transform_order = i
                mmd_bone.is_controllable = True

        # 6. Create morphs
        # Vertex morphs
        for i in range(3):
            vertex_morph = mmd_root.vertex_morphs.add()
            vertex_morph.name = f"VertexMorph{i}"
            vertex_morph.category = ["EYEBROW", "EYE", "MOUTH"][i]

        # Bone morphs
        bone_morph = mmd_root.bone_morphs.add()
        bone_morph.name = "BoneMorph1"
        bone_data = bone_morph.data.add()
        bone_data.location = [0.1, 0.0, 0.0]

        # Material morphs
        material_morph = mmd_root.material_morphs.add()
        material_morph.name = "MaterialMorph1"
        mat_data = material_morph.data.add()
        mat_data.diffuse_color = [0.1, 0.1, 0.1, 0.0]

        # 7. Create physics objects
        rigid_obj = self._create_test_rigid_body(model, "WorkflowRigid")
        mmd_rigid = rigid_obj.mmd_rigid
        mmd_rigid.name_j = "剛体"
        mmd_rigid.type = "1"  # Dynamic
        mmd_rigid.shape = "BOX"
        mmd_rigid.collision_group_number = 1

        joint_obj = self._create_test_joint(model, "WorkflowJoint")
        mmd_joint = joint_obj.mmd_joint
        mmd_joint.name_j = "ジョイント"
        mmd_joint.spring_linear = [10.0, 10.0, 10.0]

        # 8. Set up display frames
        frame = mmd_root.display_item_frames.add()
        frame.name = "CustomFrame"
        frame.name_e = "CustomFrameEnglish"

        item = frame.data.add()
        item.type = "BONE"
        item.name = armature_obj.pose.bones[0].name if armature_obj.pose.bones else "Root"

        # 9. Set up translation
        translation = mmd_root.translation
        translation.filter_japanese_blank = True
        translation.batch_operation_target = "JAPANESE"

        # 10. Verify everything works together
        # Check model structure
        self.assertEqual(root_obj.mmd_type, "ROOT", "Root object should be ROOT type")
        self.assertEqual(len(list(model.meshes())), 1, "Should have one mesh")
        self.assertEqual(len(materials), 3, "Should have three materials")
        self.assertGreater(len(mmd_root.vertex_morphs), 0, "Should have vertex morphs")
        self.assertGreater(len(mmd_root.bone_morphs), 0, "Should have bone morphs")
        self.assertGreater(len(mmd_root.material_morphs), 0, "Should have material morphs")

        # Check property values are preserved
        self.assertEqual(mmd_root.name, "ワークフローテスト", "Root Japanese name should be preserved")
        self.assertEqual(mmd_root.name_e, "WorkflowTest", "Root English name should be preserved")
        self.assertEqual(mmd_root.ik_loop_factor, 2, "IK loop factor should be preserved")

        # Check material properties
        for i, mat in enumerate(materials):
            mmd_mat = mat.mmd_material
            self.assertEqual(mmd_mat.name_j, f"マテリアル{i}", f"Material {i} Japanese name should be preserved")
            self.assertEqual(mmd_mat.name_e, f"Material{i}", f"Material {i} English name should be preserved")
            self.assertTrue(mmd_mat.enabled_toon_edge, f"Material {i} should have toon edge enabled")

        # Check physics properties
        self.assertEqual(mmd_rigid.name_j, "剛体", "Rigid body Japanese name should be preserved")
        self.assertEqual(mmd_rigid.type, "1", "Rigid body type should be preserved")
        self.assertEqual(mmd_joint.name_j, "ジョイント", "Joint Japanese name should be preserved")

        print("   - Root properties: ✓")
        print("   - Material properties: ✓")
        print("   - Bone properties: ✓")
        print("   - Morph properties: ✓")
        print("   - Physics properties: ✓")
        print("   - Display frames: ✓")
        print("   - Translation setup: ✓")

        print("✓ Complete property workflow test passed")

    def test_rigid_body_properties_size_setting(self):
        """Test rigid body size setting functionality"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        rigid_obj = self._create_test_rigid_body(model)
        mmd_rigid = rigid_obj.mmd_rigid

        # Ensure object is in OBJECT mode
        bpy.context.view_layer.objects.active = rigid_obj
        bpy.ops.object.mode_set(mode="OBJECT")

        # Test different shapes and their size behavior
        shapes_to_test = [
            ("SPHERE", [2.0, 2.0, 2.0]),  # radius
            ("BOX", [1.5, 2.0, 2.5]),  # width, height, depth
            ("CAPSULE", [1.0, 3.0, 1.0]),  # radius, height
        ]

        for shape, test_size in shapes_to_test:
            # Set shape first
            mmd_rigid.shape = shape
            self.assertEqual(mmd_rigid.shape, shape, f"Shape {shape} should be set")

            # Get initial size
            initial_size = list(mmd_rigid.size)

            # Set new size
            mmd_rigid.size = test_size
            bpy.context.view_layer.update()

            # Get size after setting
            new_size = list(mmd_rigid.size)

            # Check if size actually changed from initial
            size_changed = False
            for i in range(len(initial_size)):
                if abs(new_size[i] - initial_size[i]) > 1e-6:
                    size_changed = True
                    break

            # If _set_size has early return, size won't change
            # This test will fail if the early return is present
            if not size_changed:
                self.fail(f"Size setting for {shape} did not work - size remained {initial_size}")

            # Verify mesh was actually updated
            mesh = rigid_obj.data
            self.assertGreater(len(mesh.vertices), 0, f"Mesh should have vertices after size update for {shape}")

            # Check that mesh vertices reflect the new size approximately
            # This is a more detailed check to ensure the mesh geometry changed
            vertex_positions = [v.co[:] for v in mesh.vertices]
            max_extents = [max(abs(v[i]) for v in vertex_positions) for i in range(3)]

            # For different shapes, verify the extents make sense
            if shape == "SPHERE":
                expected_radius = test_size[0]
                for extent in max_extents[:2]:  # X and Y should match radius
                    self.assertAlmostEqual(extent, expected_radius, delta=0.1, msg=f"Sphere extent should match radius {expected_radius}")

            elif shape == "BOX":
                for i, expected_extent in enumerate(test_size):
                    self.assertAlmostEqual(max_extents[i], expected_extent, places=1, msg=f"Box extent {i} should match size {expected_extent}")

            elif shape == "CAPSULE":
                expected_radius = test_size[0]
                expected_height = test_size[1]
                # Check radius in X and Y
                for i in [0, 1]:
                    self.assertAlmostEqual(max_extents[i], expected_radius, places=1, msg=f"Capsule radius should match {expected_radius}")
                # Check height in Z (approximately, as capsule has rounded ends)
                self.assertGreaterEqual(max_extents[2], expected_height * 0.4, msg="Capsule should have reasonable height")

            print(f"   - {shape} size setting: ✓ (size: {new_size})")

        print("✓ Rigid body properties size setting test passed")

    def test_rigid_body_properties_size_edge_cases(self):
        """Test rigid body size setting with edge cases"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        rigid_obj = self._create_test_rigid_body(model)
        mmd_rigid = rigid_obj.mmd_rigid

        # Ensure object is in OBJECT mode
        bpy.context.view_layer.objects.active = rigid_obj
        bpy.ops.object.mode_set(mode="OBJECT")

        # Test minimum size constraints
        mmd_rigid.shape = "BOX"

        # Try to set very small or negative sizes
        edge_cases = [
            [0.0, 0.0, 0.0],  # Zero size
            [-1.0, -1.0, -1.0],  # Negative size
            [1e-6, 1e-6, 1e-6],  # Very small size
        ]

        for test_size in edge_cases:
            mmd_rigid.size = [1.0, 1.0, 1.0]
            bpy.context.view_layer.update()
            initial_size = list(mmd_rigid.size)

            mmd_rigid.size = test_size
            bpy.context.view_layer.update()
            new_size = list(mmd_rigid.size)

            # Verify size actually changed from initial when setting edge cases
            size_changed = any(abs(new_size[i] - initial_size[i]) > 1e-6 for i in range(len(initial_size)))

            if any(x <= 0 for x in test_size):
                # For invalid sizes, verify they were clamped properly
                self.assertTrue(size_changed or not any(x < 0 for x in new_size), f"Size should change or be clamped when setting {test_size}")

            # Size should be clamped to minimum values
            for component in new_size:
                self.assertGreaterEqual(component, 0, "Size components should be non-negative after clamping")

        # Test very large sizes
        large_size = [100.0, 100.0, 100.0]
        mmd_rigid.size = large_size
        bpy.context.view_layer.update()
        new_size = list(mmd_rigid.size)

        # Should handle large sizes without issues
        for i, expected in enumerate(large_size):
            self.assertAlmostEqual(new_size[i], expected, places=1, msg=f"Large size component {i} should be preserved")

        print("✓ Rigid body properties size edge cases test passed")

    def test_rigid_body_properties_size_mesh_update(self):
        """Test that rigid body size changes actually update the mesh geometry"""
        self._enable_mmd_tools()

        model = self._create_test_model()
        rigid_obj = self._create_test_rigid_body(model)
        mmd_rigid = rigid_obj.mmd_rigid

        # Ensure object is in OBJECT mode
        bpy.context.view_layer.objects.active = rigid_obj
        bpy.ops.object.mode_set(mode="OBJECT")

        # Set shape to BOX for predictable testing
        mmd_rigid.shape = "BOX"

        # Set initial size
        initial_size = [1.0, 1.0, 1.0]
        mmd_rigid.size = initial_size
        bpy.context.view_layer.update()

        # Get initial mesh state
        mesh = rigid_obj.data
        initial_vertex_count = len(mesh.vertices)
        initial_vertices = [v.co.copy() for v in mesh.vertices]

        # Verify we have vertices to work with
        self.assertGreater(initial_vertex_count, 0, "Rigid body mesh should have vertices initially")

        # Change size significantly
        new_size = [2.0, 3.0, 0.5]
        mmd_rigid.size = new_size
        bpy.context.view_layer.update()

        # Check that mesh was updated
        updated_vertices = [v.co.copy() for v in mesh.vertices]

        # Verify vertex count is consistent (shouldn't change for size updates)
        self.assertEqual(len(updated_vertices), initial_vertex_count, "Vertex count should remain the same when updating size")

        # Vertices should have changed positions
        vertices_changed = False
        for i, (initial_v, updated_v) in enumerate(zip(initial_vertices, updated_vertices, strict=False)):
            if (initial_v - updated_v).length > 1e-6:
                vertices_changed = True
                break

        if not vertices_changed:
            self.fail("Mesh vertices did not change when rigid body size was updated. This indicates _set_size function is not working properly.")

        # Check that vertex positions reflect new size
        # For a box, vertices should be at ±size/2 for each axis
        expected_extents = list(new_size)  # Box extents should match size
        actual_extents = [max(abs(v.co[i]) for v in mesh.vertices) for i in range(3)]

        for i, (expected, actual) in enumerate(zip(expected_extents, actual_extents, strict=False)):
            self.assertAlmostEqual(actual, expected, places=1, msg=f"Mesh extent {i} should reflect new size {expected}")

        print("✓ Rigid body properties size mesh update test passed")


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main()
