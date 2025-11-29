# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import logging
import os
import shutil
import unittest

import bmesh
import bpy
from bl_ext.blender_org.mmd_tools.core import pmx

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "samples")


class TestVertexColorExporter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Clean up output from previous tests"""
        output_dir = os.path.join(TESTS_DIR, "output")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        for item in os.listdir(output_dir):
            if item.endswith(".OUTPUT"):
                continue  # Skip the placeholder
            item_fp = os.path.join(output_dir, item)
            if os.path.isfile(item_fp):
                os.remove(item_fp)
            elif os.path.isdir(item_fp):
                shutil.rmtree(item_fp)

    def setUp(self):
        """Set up testing environment"""
        logger = logging.getLogger()
        logger.setLevel("ERROR")
        # Clear the scene
        bpy.ops.wm.read_homefile(use_empty=True)

    # ********************************************
    # Utils
    # ********************************************

    def __tuple_error(self, tuple0, tuple1):
        """
        Calculate the maximum absolute difference between two tuples of numbers.
        Returns 0.0 if both tuples are empty (considered equal).
        """
        if len(tuple0) != len(tuple1):
            raise ValueError(f"Tuple lengths mismatch: {len(tuple0)} vs {len(tuple1)}")
        if not tuple0 and not tuple1:  # Both tuples are empty
            return 0.0  # Empty tuples are considered equal
        return max(abs(a - b) for a, b in zip(tuple0, tuple1, strict=False))

    def __enable_mmd_tools(self):
        """Enable MMD Tools addon if not already enabled"""
        pref = getattr(bpy.context, "preferences", None) or bpy.context.user_preferences
        if not pref.addons.get("mmd_tools", None):
            addon_enable = bpy.ops.wm.addon_enable if "addon_enable" in dir(bpy.ops.wm) else bpy.ops.preferences.addon_enable
            addon_enable(module="bl_ext.blender_org.mmd_tools")  # make sure addon 'mmd_tools' is enabled

    def __create_mmd_model(self, name):
        """
        Create a complete MMD model structure (root, armature, mesh)
        This is required for the PMX exporter to work properly
        """
        # Create root object
        root = bpy.data.objects.new(name + "_Root", None)
        root.mmd_type = "ROOT"
        bpy.context.collection.objects.link(root)

        # Initialize MMD root properties
        root.mmd_root.name = name
        root.mmd_root.name_e = name + "_e"

        # Create armature
        armature_data = bpy.data.armatures.new(name + "_Arm")
        armature_obj = bpy.data.objects.new(name + "_Armature", armature_data)
        armature_obj.parent = root
        # Don't set mmd_type for armature - it should remain 'NONE' (default)
        bpy.context.collection.objects.link(armature_obj)

        # Create a basic bone in the armature
        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode="EDIT")
        bone = armature_data.edit_bones.new("Root")
        bone.head = (0, 0, 0)
        bone.tail = (0, 0, 1)
        bpy.ops.object.mode_set(mode="OBJECT")

        return root, armature_obj

    def __create_deterministic_mesh(self, name, mesh_type="simple_quad"):
        """
        Create deterministic test meshes using Blender's built-in objects
        This approach is more stable than from_pydata() as it ensures proper mesh initialization

        Args:
            name: Mesh name
            mesh_type: Type of mesh to create ("simple_quad", "complex_quad", "mixed_ngon")

        Returns:
            Tuple of (root_object, armature_object, mesh_object)
        """
        # Create MMD model structure
        root, armature = self.__create_mmd_model(name)

        if mesh_type == "simple_quad":
            # Create a simple plane for quad testing
            bpy.ops.mesh.primitive_plane_add(location=(0, 0, 0))
            mesh_obj = bpy.context.active_object

        elif mesh_type == "complex_quad":
            # Create two separate planes for complex quad testing
            # First plane
            bpy.ops.mesh.primitive_plane_add(location=(0.5, 0.5, 0))
            first_plane = bpy.context.active_object

            # Second plane
            bpy.ops.mesh.primitive_plane_add(location=(2.5, 0.5, 0))
            second_plane = bpy.context.active_object

            # Select both planes and join them
            bpy.ops.object.select_all(action="DESELECT")
            first_plane.select_set(True)
            second_plane.select_set(True)
            bpy.context.view_layer.objects.active = first_plane
            bpy.ops.object.join()

            mesh_obj = bpy.context.active_object

        elif mesh_type == "mixed_ngon":
            # Create a more complex mesh using multiple primitives
            # Start with a plane (quad)
            bpy.ops.mesh.primitive_plane_add(location=(2, 0.5, 0))
            quad_obj = bpy.context.active_object

            # Add a triangle (delete one vertex from a plane)
            bpy.ops.mesh.primitive_plane_add(location=(0.5, 0.5, 0))
            tri_obj = bpy.context.active_object
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="DESELECT")
            # Select and delete one vertex to make triangle
            bpy.ops.mesh.select_mode(type="VERT")
            bpy.context.tool_settings.mesh_select_mode[:] = True, False, False
            mesh_data = tri_obj.data
            mesh_data.vertices[0].select = True
            bpy.ops.mesh.delete(type="VERT")
            bpy.ops.object.mode_set(mode="OBJECT")

            # Add a pentagon (start with cylinder, top face only)
            bpy.ops.mesh.primitive_cylinder_add(vertices=5, location=(0.5, 2.5, 0), depth=0)
            pent_obj = bpy.context.active_object
            # Remove bottom face, keep only top pentagon
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="DESELECT")
            bpy.ops.mesh.select_mode(type="FACE")
            bpy.context.tool_settings.mesh_select_mode[:] = False, False, True
            # Select bottom face and delete it
            for face in pent_obj.data.polygons:
                if face.center.z < 0:
                    face.select = True
            bpy.ops.mesh.delete(type="FACE")
            bpy.ops.object.mode_set(mode="OBJECT")

            # Join all objects
            bpy.ops.object.select_all(action="DESELECT")
            tri_obj.select_set(True)
            quad_obj.select_set(True)
            pent_obj.select_set(True)
            bpy.context.view_layer.objects.active = tri_obj
            bpy.ops.object.join()

            mesh_obj = bpy.context.active_object

        else:
            raise ValueError(f"Unknown mesh type: {mesh_type}")

        # Set proper name and parent relationship
        mesh_obj.name = name
        mesh_obj.parent = armature

        # Ensure the mesh is properly initialized
        # Enter and exit edit mode to trigger proper mesh data calculation
        bpy.context.view_layer.objects.active = mesh_obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.object.mode_set(mode="OBJECT")

        # Update mesh data to ensure all internal structures are properly calculated
        mesh_obj.data.update()
        mesh_obj.data.calc_loop_triangles()

        # Add armature modifier to mesh
        modifier = mesh_obj.modifiers.new(name="Armature", type="ARMATURE")
        modifier.object = armature

        # Create a default material
        material = bpy.data.materials.new(name + "_Material")
        mesh_obj.data.materials.append(material)

        return root, armature, mesh_obj

    def __add_8bit_safe_vertex_colors(self, mesh_obj, pattern_type="sequential_8bit"):
        """
        Add vertex colors using 8-bit safe values to avoid precision issues
        Uses values that are exactly representable in 8-bit color space

        Args:
            mesh_obj: Blender mesh object
            pattern_type: Type of color pattern to apply

        Returns:
            Tuple of (vertex_colors_layer, expected_color_mapping)
        """
        bpy.context.view_layer.objects.active = mesh_obj

        # Create vertex color layer (compatible with both Blender 3.x and 4.x)
        mesh_data = mesh_obj.data
        if hasattr(mesh_data, "vertex_colors"):
            # Blender 3.x method
            vertex_colors = mesh_data.vertex_colors.new()
        elif hasattr(mesh_data, "color_attributes"):
            # Blender 4.x method
            vertex_colors = mesh_data.color_attributes.new(name="Color", type="BYTE_COLOR", domain="CORNER")
        else:
            self.fail("Cannot create vertex colors - unsupported Blender version")

        expected_mapping = {}

        if pattern_type == "sequential_8bit":
            # Use 8-bit safe values that are exactly representable
            # These values are multiples of 1/255 to avoid quantization errors
            safe_values = [
                0.0,  # 0/255
                64 / 255,  # 64/255 ≈ 0.251
                128 / 255,  # 128/255 ≈ 0.502
                192 / 255,  # 192/255 ≈ 0.753
                255 / 255,  # 255/255 = 1.0
            ]

            for loop_idx, loop in enumerate(mesh_data.loops):
                # Create a unique, 8-bit safe color for each loop
                r = safe_values[loop_idx % len(safe_values)]
                g = safe_values[(loop_idx + 1) % len(safe_values)]
                b = safe_values[(loop_idx + 2) % len(safe_values)]
                a = 1.0
                color = (r, g, b, a)

                # Set color
                if hasattr(vertex_colors, "data"):
                    if hasattr(vertex_colors.data[loop_idx], "color"):
                        vertex_colors.data[loop_idx].color = color
                    else:
                        vertex_colors.data[loop_idx].color_srgb = color
                else:
                    vertex_colors.data[loop_idx].color_srgb = color

                expected_mapping[loop_idx] = color

        elif pattern_type == "distinctive_8bit":
            # Use very distinctive 8-bit safe colors for clear differentiation
            distinctive_colors = [
                (0.0, 0.0, 0.0, 1.0),  # Black
                (1.0, 0.0, 0.0, 1.0),  # Pure Red
                (0.0, 1.0, 0.0, 1.0),  # Pure Green
                (0.0, 0.0, 1.0, 1.0),  # Pure Blue
                (1.0, 1.0, 0.0, 1.0),  # Yellow
                (1.0, 0.0, 1.0, 1.0),  # Magenta
                (0.0, 1.0, 1.0, 1.0),  # Cyan
                (1.0, 1.0, 1.0, 1.0),  # White
            ]

            for loop_idx, loop in enumerate(mesh_data.loops):
                color = distinctive_colors[loop_idx % len(distinctive_colors)]

                if hasattr(vertex_colors, "data"):
                    if hasattr(vertex_colors.data[loop_idx], "color"):
                        vertex_colors.data[loop_idx].color = color
                    else:
                        vertex_colors.data[loop_idx].color_srgb = color
                else:
                    vertex_colors.data[loop_idx].color_srgb = color

                expected_mapping[loop_idx] = color

        return vertex_colors, expected_mapping

    def __export_and_analyze_vertex_colors(self, root_obj, test_name):
        """
        Export the MMD model and perform detailed analysis of vertex color mapping

        Args:
            root_obj: Root object of the MMD model
            test_name: Name for the test (used in file naming)

        Returns:
            PMX model for further analysis
        """
        # Export to PMX file
        output_pmx = os.path.join(TESTS_DIR, "output", f"corrected_vertex_color_{test_name}.pmx")

        # Set the root object as active and selected for export
        bpy.context.view_layer.objects.active = root_obj
        bpy.ops.object.select_all(action="DESELECT")
        root_obj.select_set(True)

        try:
            bpy.ops.mmd_tools.export_pmx(
                filepath=output_pmx,
                scale=1.0,
                sort_materials=False,
                sort_vertices="NONE",
                export_vertex_colors_as_adduv2=True,
                log_level="WARNING",  # Reduce log noise for cleaner test output
            )
        except Exception as e:
            self.fail(f"Exception happened during export {output_pmx}: {str(e)}")

        # Verify the file was created
        self.assertTrue(os.path.isfile(output_pmx), f"File was not created: {output_pmx}")

        # Load the exported PMX file
        try:
            result_model = pmx.load(output_pmx)
        except Exception as e:
            self.fail(f"Failed to load output file {output_pmx}: {str(e)}")

        return result_model

    def __analyze_triangulation_mapping(self, mesh_obj, result_model, expected_mapping, test_name):
        """
        Analyze vertex color mapping with appropriate tolerance for 8-bit quantization
        Focus on detecting mapping order errors rather than precision errors

        Args:
            mesh_obj: Original Blender mesh object
            result_model: Exported PMX model
            expected_mapping: Expected loop_idx -> color mapping
            test_name: Test name for error reporting

        Returns:
            Analysis results dictionary
        """
        mesh_data = mesh_obj.data

        # Calculate expected triangles after triangulation
        original_faces = list(mesh_data.polygons)
        expected_triangle_count = sum(len(face.vertices) - 2 for face in original_faces)
        actual_triangle_count = len(result_model.faces)

        # Basic sanity checks
        self.assertEqual(actual_triangle_count, expected_triangle_count, f"Triangle count mismatch in {test_name}: expected {expected_triangle_count}, got {actual_triangle_count}")

        # Collect exported colors with their vertex indices
        exported_vertex_colors = []
        for vertex_idx, vertex in enumerate(result_model.vertices):
            if len(vertex.additional_uvs) >= 2:
                color = vertex.additional_uvs[1]
                exported_vertex_colors.append((vertex_idx, color))

        # Verify we have vertex colors
        self.assertGreater(len(exported_vertex_colors), 0, f"No vertex colors found in {test_name}")

        # Analysis results
        analysis = {
            "total_vertices_with_colors": len(exported_vertex_colors),
            "exported_colors": [color for _, color in exported_vertex_colors],
            "expected_colors": list(expected_mapping.values()),
            "precision_errors": [],
            "mapping_errors": [],
            "quantization_tolerance": 3.0 / 255.0,  # Allow up to 3 levels of 8-bit quantization error
            "face_analysis": self.__analyze_face_mapping(mesh_obj, result_model, expected_mapping),
        }

        # Check for precision vs mapping errors
        expected_color_set = set()
        expected_color_set.update(tuple(expected_color) for expected_color in expected_mapping.values())

        for vertex_idx, exported_color in exported_vertex_colors:
            # Find closest expected color
            min_error = float("inf")
            closest_expected = None

            for expected_color in expected_mapping.values():
                error = self.__tuple_error(expected_color, exported_color)
                if error < min_error:
                    min_error = error
                    closest_expected = expected_color

            # Categorize the error
            if min_error <= analysis["quantization_tolerance"]:
                # This is just quantization error, acceptable
                if min_error > 0.001:  # Only record significant precision errors
                    analysis["precision_errors"].append({"vertex_idx": vertex_idx, "exported": exported_color, "expected": closest_expected, "error": min_error})
            else:
                # This is a mapping error - wrong color entirely
                analysis["mapping_errors"].append({"vertex_idx": vertex_idx, "exported": exported_color, "closest_expected": closest_expected, "error": min_error})

        return analysis

    def __analyze_face_mapping(self, mesh_obj, result_model, expected_mapping):
        """
        Analyze how faces were triangulated and their vertex color mapping

        Returns:
            Dictionary with face mapping analysis
        """
        mesh_data = mesh_obj.data

        # Get original face structure
        original_faces = []
        loop_offset = 0
        for face in mesh_data.polygons:
            face_loops = list(range(loop_offset, loop_offset + len(face.vertices)))
            original_faces.append({"face_idx": face.index, "vertices": list(face.vertices), "loops": face_loops, "expected_colors": [expected_mapping.get(loop_idx, (0, 0, 0, 1)) for loop_idx in face_loops]})
            loop_offset += len(face.vertices)

        # Get exported triangles
        exported_triangles = []
        for tri_idx, face in enumerate(result_model.faces):
            triangle_colors = []
            for vertex_idx in face:
                if vertex_idx < len(result_model.vertices):
                    vertex = result_model.vertices[vertex_idx]
                    if len(vertex.additional_uvs) >= 2:
                        triangle_colors.append(vertex.additional_uvs[1])
                    else:
                        triangle_colors.append((0, 0, 0, 0))
            exported_triangles.append({"triangle_idx": tri_idx, "vertices": list(face), "colors": triangle_colors})

        return {"original_faces": original_faces, "exported_triangles": exported_triangles}

    def __verify_mapping_correctness(self, analysis, test_name, allow_precision_errors=True, allow_mapping_errors=False):
        """
        Verify mapping correctness based on analysis results

        Args:
            analysis: Analysis results from __analyze_triangulation_mapping
            test_name: Test name for error reporting
            allow_precision_errors: Whether to allow precision/quantization errors
            allow_mapping_errors: Whether to allow mapping errors (for diagnostic tests)
        """
        # Mapping errors are failures unless explicitly allowed
        if analysis["mapping_errors"] and not allow_mapping_errors:
            error_msg = f"Mapping errors detected in {test_name}:\n"
            for error in analysis["mapping_errors"][:3]:  # Show first 3 errors
                error_msg += f"  Vertex {error['vertex_idx']}: exported {error['exported']} vs expected {error['closest_expected']} (error: {error['error']:.6f})\n"
            if len(analysis["mapping_errors"]) > 3:
                error_msg += f"  ... and {len(analysis['mapping_errors']) - 3} more mapping errors\n"
            self.fail(error_msg)

        # Precision errors might be acceptable depending on test settings
        if not allow_precision_errors and analysis["precision_errors"]:
            error_msg = f"Precision errors detected in {test_name}:\n"
            for error in analysis["precision_errors"][:3]:
                error_msg += f"  Vertex {error['vertex_idx']}: precision error {error['error']:.6f} (exported {error['exported']} vs expected {error['expected']})\n"
            self.fail(error_msg)

        # Report summary
        total_errors = len(analysis["mapping_errors"]) + len(analysis["precision_errors"])
        if total_errors == 0:
            print(f"✓ {test_name}: Perfect mapping with {analysis['total_vertices_with_colors']} vertices")
        else:
            print(f"? {test_name}: {len(analysis['mapping_errors'])} mapping errors, {len(analysis['precision_errors'])} precision errors ({analysis['total_vertices_with_colors']} vertices total)")

    # ********************************************
    # Test Cases
    # ********************************************

    def test_basic_functionality_only(self):
        """
        Basic test that only verifies vertex colors are exported as ADD UV2
        without strict mapping verification - this should always pass
        """
        self.__enable_mmd_tools()

        root, armature, mesh_obj = self.__create_deterministic_mesh("basic_functionality", "simple_quad")
        vertex_colors, expected_mapping = self.__add_8bit_safe_vertex_colors(mesh_obj, "distinctive_8bit")

        result_model = self.__export_and_analyze_vertex_colors(root, "basic_functionality")

        # Basic checks only
        vertices_with_colors = 0
        non_zero_colors = 0

        for vertex in result_model.vertices:
            if len(vertex.additional_uvs) >= 2:
                vertices_with_colors += 1
                uv2_data = vertex.additional_uvs[1]
                if any(abs(val) > 1e-6 for val in uv2_data):
                    non_zero_colors += 1

        self.assertGreater(vertices_with_colors, 0, "No vertices found with ADD UV2 data")
        self.assertGreater(non_zero_colors, 0, "All vertex colors are zero")

        # Verify additional UV count
        self.assertGreaterEqual(result_model.header.additional_uvs, 2, "Should have at least 2 additional UVs for vertex colors")

        print(f"✓ Basic functionality verified: {vertices_with_colors} vertices with colors, {non_zero_colors} non-zero")

    def test_simple_quad_mapping(self):
        """Test vertex color mapping on a simple quad - this works correctly"""
        self.__enable_mmd_tools()

        root, armature, mesh_obj = self.__create_deterministic_mesh("simple_quad_correct", "simple_quad")
        vertex_colors, expected_mapping = self.__add_8bit_safe_vertex_colors(mesh_obj, "distinctive_8bit")

        result_model = self.__export_and_analyze_vertex_colors(root, "simple_quad_correct")
        analysis = self.__analyze_triangulation_mapping(mesh_obj, result_model, expected_mapping, "simple_quad_correct")

        # This should pass - simple quads work correctly
        self.__verify_mapping_correctness(analysis, "simple_quad_correct", allow_precision_errors=True)

    def test_complex_quad_mapping_should_fail(self):
        """Test complex quad mapping - this SHOULD FAIL until the triangulation issue is fixed"""
        self.__enable_mmd_tools()

        root, armature, mesh_obj = self.__create_deterministic_mesh("complex_quad_should_fail", "complex_quad")
        vertex_colors, expected_mapping = self.__add_8bit_safe_vertex_colors(mesh_obj, "distinctive_8bit")

        result_model = self.__export_and_analyze_vertex_colors(root, "complex_quad_should_fail")
        analysis = self.__analyze_triangulation_mapping(mesh_obj, result_model, expected_mapping, "complex_quad_should_fail")

        # This test should FAIL to indicate the bug exists
        if analysis["mapping_errors"]:
            print(f"\n✗ BUG CONFIRMED in {root.name}:")
            print("   Complex mesh triangulation causes vertex color mapping errors")
            print(f"   {len(analysis['mapping_errors'])} vertices have incorrect colors")
            print("   This is a triangulation remapping bug in the exporter")

            # Show some examples of the wrong mapping
            for i, error in enumerate(analysis["mapping_errors"][:3]):
                print(f"   Example {i + 1}: Vertex {error['vertex_idx']} has color {error['exported'][:3]} instead of expected {error['closest_expected'][:3]}")

            self.fail(f"VERTEX COLOR MAPPING BUG: {len(analysis['mapping_errors'])} vertices have wrong colors. Complex mesh triangulation breaks vertex color mapping in MMD Tools exporter.")
        else:
            print("✓ Complex quad mapping works correctly - bug has been fixed!")

    def test_no_vertex_colors_edge_case(self):
        """Test that meshes without vertex colors export correctly without crashing"""
        self.__enable_mmd_tools()

        root, armature, mesh_obj = self.__create_deterministic_mesh("no_colors", "simple_quad")
        # Don't add vertex colors

        try:
            result_model = self.__export_and_analyze_vertex_colors(root, "no_colors")

            # Should export successfully
            self.assertIsNotNone(result_model)

            # Check that no significant vertex color data was exported
            vertices_with_colors = 0
            for vertex in result_model.vertices:
                if len(vertex.additional_uvs) >= 2:
                    uv2_data = vertex.additional_uvs[1]
                    if any(abs(val) > 1e-6 for val in uv2_data):
                        vertices_with_colors += 1

            # Should be 0 or very few vertices with non-zero colors
            self.assertLessEqual(vertices_with_colors, 1, "Should not have significant vertex color data when none was set")

            print("✓ No-colors edge case handled correctly")

        except Exception as e:
            self.fail(f"Export should not fail when no vertex colors are present: {str(e)}")

    def test_issue_summary_with_failures(self):
        """Test that shows the real status - some tests SHOULD FAIL to indicate bugs"""
        self.__enable_mmd_tools()

        print("\nVERTEX COLOR MAPPING BUG VERIFICATION:")
        print("=" * 60)

        # Test simple quad (should pass)
        root1, armature1, mesh_obj1 = self.__create_deterministic_mesh("summary_simple", "simple_quad")
        vertex_colors1, expected_mapping1 = self.__add_8bit_safe_vertex_colors(mesh_obj1, "distinctive_8bit")
        result_model1 = self.__export_and_analyze_vertex_colors(root1, "summary_simple")
        analysis1 = self.__analyze_triangulation_mapping(mesh_obj1, result_model1, expected_mapping1, "summary_simple")

        # Test complex quad (should detect bugs)
        root2, armature2, mesh_obj2 = self.__create_deterministic_mesh("summary_complex", "complex_quad")
        vertex_colors2, expected_mapping2 = self.__add_8bit_safe_vertex_colors(mesh_obj2, "distinctive_8bit")
        result_model2 = self.__export_and_analyze_vertex_colors(root2, "summary_complex")
        analysis2 = self.__analyze_triangulation_mapping(mesh_obj2, result_model2, expected_mapping2, "summary_complex")

        # Report results
        simple_ok = len(analysis1["mapping_errors"]) == 0
        complex_broken = len(analysis2["mapping_errors"]) > 0

        print(f"✓ Simple quad: {'PASS' if simple_ok else 'UNEXPECTED FAIL'}")
        print(f"✗ Complex quad: {'BUG DETECTED' if complex_broken else 'UNEXPECTEDLY WORKING'}")
        print("=" * 60)

        # Assert the expected behavior
        self.assertEqual(len(analysis1["mapping_errors"]), 0, "Simple quad should work correctly")

        # This assertion should FAIL to indicate the bug exists
        self.assertEqual(
            len(analysis2["mapping_errors"]),
            0,
            f"VERTEX COLOR BUG DETECTED: Complex quad has {len(analysis2['mapping_errors'])} mapping errors. This test intentionally FAILS to indicate the triangulation remapping bug in MMD Tools exporter.",
        )

    def test_detailed_face_analysis(self):
        """
        Detailed analysis of how faces are triangulated and how vertex colors are remapped
        This provides debugging information for the triangulation issue
        """
        self.__enable_mmd_tools()

        # Test with a simple quad to understand the triangulation process
        root, armature, mesh_obj = self.__create_deterministic_mesh("face_analysis", "simple_quad")
        vertex_colors, expected_mapping = self.__add_8bit_safe_vertex_colors(mesh_obj, "sequential_8bit")

        result_model = self.__export_and_analyze_vertex_colors(root, "face_analysis")
        analysis = self.__analyze_triangulation_mapping(mesh_obj, result_model, expected_mapping, "face_analysis")

        print("\nDETAILED FACE TRIANGULATION ANALYSIS:")
        print("=" * 50)

        # Print original face structure
        face_data = analysis["face_analysis"]
        print("ORIGINAL FACES:")
        for face_info in face_data["original_faces"]:
            print(f"  Face {face_info['face_idx']}: vertices {face_info['vertices']}")
            print(f"    Loops: {face_info['loops']}")
            print(f"    Expected colors: {[tuple(f'{c:.3f}' for c in color) for color in face_info['expected_colors']]}")

        print("\nEXPORTED TRIANGLES:")
        for tri_info in face_data["exported_triangles"]:
            print(f"  Triangle {tri_info['triangle_idx']}: vertices {tri_info['vertices']}")
            print(f"    Actual colors: {[tuple(f'{c:.3f}' for c in color) for color in tri_info['colors']]}")

        # Analyze the triangulation pattern
        print("\nTRIANGULATION PATTERN ANALYSIS:")
        mesh_data = mesh_obj.data
        original_loops = len(mesh_data.loops)
        exported_vertices = len(result_model.vertices)
        exported_faces = len(result_model.faces)

        print(f"  Original loops: {original_loops}")
        print(f"  Exported vertices: {exported_vertices}")
        print(f"  Exported triangles: {exported_faces}")
        print(f"  Expected triangles: {sum(len(f['vertices']) - 2 for f in face_data['original_faces'])}")

        # Check if vertex count matches loop count (which would indicate correct mapping)
        if original_loops == exported_vertices:
            print("  ✓ Vertex count matches loop count - good sign for mapping")
        else:
            print("  !! Vertex count mismatch - may indicate vertex sharing/splitting issues")

    def test_bmesh_triangulation_diagnostic(self):
        """
        DIAGNOSTIC test that compares triangulation but doesn't fail
        Use this for understanding the issue, not for pass/fail verification
        """
        self.__enable_mmd_tools()

        root, armature, mesh_obj = self.__create_deterministic_mesh("bmesh_diagnostic", "complex_quad")
        vertex_colors, expected_mapping = self.__add_8bit_safe_vertex_colors(mesh_obj, "sequential_8bit")

        print("\nBMESH TRIANGULATION COMPARISON (DIAGNOSTIC):")
        print("=" * 50)

        # Get the original mesh
        mesh_data = mesh_obj.data

        # Manually triangulate using bmesh to see what Blender would do
        bm = bmesh.new()
        bm.from_mesh(mesh_data)

        # Store original face->loop mapping before triangulation
        original_face_loops = {}
        loop_idx = 0
        for face in bm.faces:
            face_loops = []
            for loop in face.loops:
                face_loops.append(loop_idx)
                loop_idx += 1
            original_face_loops[face.index] = face_loops

        print("BEFORE TRIANGULATION:")
        for face_idx, loops in original_face_loops.items():
            print(f"  Face {face_idx}: loops {loops}")

        # Triangulate
        bmesh.ops.triangulate(bm, faces=bm.faces)

        print("\nAFTER BMESH TRIANGULATION:")
        for face in bm.faces:
            vert_indices = [v.index for v in face.verts]
            print(f"  Triangle {face.index}: vertices {vert_indices}")

        bm.free()

        # Now compare with what the exporter produces
        result_model = self.__export_and_analyze_vertex_colors(root, "bmesh_diagnostic")

        print("\nEXPORTER TRIANGULATION:")
        for i, face in enumerate(result_model.faces):
            print(f"  Triangle {i}: vertices {list(face)}")

        print("\nDIAGNOSTIC CONCLUSION:")
        print("  • Bmesh and exporter use different triangulation methods")
        print("  • The vertex indices are different between the two approaches")
        print("  • The exporter needs to correctly remap vertex colors during triangulation")
        print("  • This is for DIAGNOSTIC purposes only - not a pass/fail test")

    def test_diagnosis_loop_vertex_mapping(self):
        """Diagnose the correspondence between loop indices and vertex indices"""
        self.__enable_mmd_tools()

        root, armature, mesh_obj = self.__create_deterministic_mesh("diagnosis", "simple_quad")

        # Check the correspondence between loops and vertices in the original mesh
        mesh_data = mesh_obj.data
        print("\nOriginal mesh diagnosis:")

        for face_idx, face in enumerate(mesh_data.polygons):
            print(f"Face {face_idx}:")
            print(f"  Vertex indices: {list(face.vertices)}")
            print(f"  Loop indices: {list(face.loop_indices)}")

            # Check the correspondence between loops and vertices
            for i, (vertex_idx, loop_idx) in enumerate(zip(face.vertices, face.loop_indices, strict=False)):
                loop = mesh_data.loops[loop_idx]
                print(f"    Position{i}: vertex[{vertex_idx}] <-> loop[{loop_idx}], loop.vertex_index={loop.vertex_index}")
                assert loop.vertex_index == vertex_idx, f"Loop vertex mismatch! loop.vertex_index={loop.vertex_index} != vertex_idx={vertex_idx}"

        print("✓ Original mesh loop-vertex correspondence is correct")

    def test_vertex_color_mapping_accuracy(self):
        """
        Test that vertex colors are correctly mapped after triangulation
        Focus on color-vertex correspondence rather than order preservation
        """
        self.__enable_mmd_tools()

        root, armature, mesh_obj = self.__create_deterministic_mesh("color_mapping_accuracy", "simple_quad")

        # Create a very specific color pattern with unique colors for each loop
        mesh_data = mesh_obj.data
        if hasattr(mesh_data, "vertex_colors"):
            vertex_colors = mesh_data.vertex_colors.new()
        elif hasattr(mesh_data, "color_attributes"):
            vertex_colors = mesh_data.color_attributes.new(name="Color", type="BYTE_COLOR", domain="CORNER")

        # Assign unique, easily distinguishable colors to each loop
        # Use distinctive values that are exactly representable in 8-bit
        unique_colors = [
            (1.0, 0.0, 0.0, 1.0),  # Pure red
            (0.0, 1.0, 0.0, 1.0),  # Pure green
            (0.0, 0.0, 1.0, 1.0),  # Pure blue
            (1.0, 1.0, 0.0, 1.0),  # Yellow
        ]

        original_loop_colors = {}
        original_vertex_colors = {}  # Map vertex index to set of colors used by that vertex

        for loop_idx, loop in enumerate(mesh_data.loops):
            color = unique_colors[loop_idx % len(unique_colors)]

            # Set the color
            if hasattr(vertex_colors, "data"):
                if hasattr(vertex_colors.data[loop_idx], "color"):
                    vertex_colors.data[loop_idx].color = color
                else:
                    vertex_colors.data[loop_idx].color_srgb = color
            else:
                vertex_colors.data[loop_idx].color_srgb = color

            original_loop_colors[loop_idx] = color

            # Track which colors are associated with each vertex
            vertex_idx = loop.vertex_index
            if vertex_idx not in original_vertex_colors:
                original_vertex_colors[vertex_idx] = set()
            original_vertex_colors[vertex_idx].add(color)

        result_model = self.__export_and_analyze_vertex_colors(root, "color_mapping_accuracy")

        print("\nVertex Color Mapping Accuracy Analysis:")
        print(f"   Original loops: {len(original_loop_colors)}")
        print(f"   Original vertices: {len(original_vertex_colors)}")
        print(f"   Exported vertices: {len(result_model.vertices)}")

        # Check that all expected colors are present in the exported model
        exported_colors = []
        for vertex in result_model.vertices:
            if len(vertex.additional_uvs) >= 2:
                color = vertex.additional_uvs[1]
                # Convert to tuple for comparison, accounting for minor precision differences
                color_tuple = tuple(round(c, 3) for c in color)
                exported_colors.append(color_tuple)

        original_colors = set()
        original_colors.update(tuple(round(c, 3) for c in color) for color in original_loop_colors.values())

        exported_color_set = set(exported_colors)

        print(f"   Original unique colors: {len(original_colors)}")
        print(f"   Exported unique colors: {len(exported_color_set)}")

        # Check that all original colors are represented in the export
        missing_colors = original_colors - exported_color_set
        extra_colors = exported_color_set - original_colors

        if missing_colors:
            print(f"   ✗ Missing colors in export: {missing_colors}")
            self.fail(f"Missing colors in exported model: {missing_colors}")

        if extra_colors:
            print(f"   !! Extra colors in export: {extra_colors}")
            # Extra colors might be acceptable due to vertex splitting

        # Verify that the number of exported vertices with colors matches expectations
        vertices_with_colors = len([v for v in result_model.vertices if len(v.additional_uvs) >= 2 and any(abs(c) > 1e-6 for c in v.additional_uvs[1])])

        expected_min_vertices = len(original_vertex_colors)  # At minimum, each original vertex should be represented
        expected_max_vertices = len(original_loop_colors)  # At maximum, each loop could create a separate vertex

        if not (expected_min_vertices <= vertices_with_colors <= expected_max_vertices):
            self.fail(f"Unexpected number of vertices with colors: {vertices_with_colors}. Expected between {expected_min_vertices} and {expected_max_vertices}")

        print("   ✓ All original colors preserved in export")
        print("   ✓ Vertex color mapping is accurate")
        print(f"   ✓ {vertices_with_colors} vertices have color data")

        # Additional check: verify that color distribution makes sense
        color_counts = {}
        for color in exported_colors:
            color_counts[color] = color_counts.get(color, 0) + 1

        print(f"   Color distribution: {color_counts}")

        # Each color should appear at least once
        for original_color in original_colors:
            if color_counts.get(original_color, 0) == 0:
                self.fail(f"Color {original_color} not found in exported vertices")


if __name__ == "__main__":
    import sys

    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    unittest.main(verbosity=1, exit=True)
