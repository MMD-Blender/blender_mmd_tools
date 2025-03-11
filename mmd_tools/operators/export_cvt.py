# -*- coding: utf-8 -*-
# Copyright MMD Tools authors
# This file is part of MMD Tools.

import bpy
import logging
from ..core.model import FnModel

def convert_curves_to_meshes(context, root_object):
    """
    Converts all curve objects in the model to temporary meshes for export.
    Creates new temporary mesh objects without modifying the original curves.
    
    Args:
        context: The current Blender context
        root_object: The root object of the MMD model
        
    Returns:
        tuple: (list of created mesh objects, list of original curve objects)
    """
    temp_meshes = []
    curve_objects = []
    
    # Find all curve objects that are part of the model's hierarchy
    for obj in FnModel.iterate_child_objects(root_object):
        if obj.type == 'CURVE' and obj.data is not None:
            curve_objects.append(obj)
    
    if not curve_objects:
        return [], []
    
    logging.info(f"Found {len(curve_objects)} curve objects to convert")
    armature_object = FnModel.find_armature_object(root_object)
    
    # Convert each curve to a temporary mesh
    for curve_obj in curve_objects:
        # Create evaluated version of the curve
        depsgraph = context.evaluated_depsgraph_get()
        curve_evaluated = curve_obj.evaluated_get(depsgraph)
        
        # Convert to mesh (non-destructive)
        mesh = bpy.data.meshes.new_from_object(
            curve_evaluated,
            preserve_all_data_layers=True,
            depsgraph=depsgraph
        )
        
        # Create a new mesh object with the converted data
        duplicate_name = f"temp_mesh_{curve_obj.name}"
        duplicate = bpy.data.objects.new(duplicate_name, mesh)
        context.collection.objects.link(duplicate)
        
        # Keep track of original parent and constraints
        orig_parent = curve_obj.parent
        orig_parent_type = curve_obj.parent_type
        orig_parent_bone = curve_obj.parent_bone
        
        # Handle parenting
        if orig_parent:
            # Use the same parent as the original curve
            duplicate.parent = orig_parent
            duplicate.parent_type = orig_parent_type
            duplicate.parent_bone = orig_parent_bone
            
            # If it's parented to a bone, make sure we set it up correctly
            if orig_parent_type == 'BONE' and orig_parent_bone:
                duplicate.parent_bone = orig_parent_bone
        
        # Copy the transformation matrices
        duplicate.matrix_world = curve_obj.matrix_world.copy()
        
        # Apply materials from the curve to the mesh
        for mat_slot in curve_obj.material_slots:
            if mat_slot.material:
                duplicate.data.materials.append(mat_slot.material)
        
        # Add armature modifier if needed (for deformation)
        if armature_object:
            # Check if the original curve has an armature modifier
            has_armature_mod = False
            for mod in curve_obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object == armature_object:
                    has_armature_mod = True
                    # Add the same modifier to the duplicate
                    modifier = duplicate.modifiers.new(name="Armature", type="ARMATURE")
                    modifier.object = armature_object
                    modifier.use_vertex_groups = True
                    modifier.use_deform_preserve_volume = mod.use_deform_preserve_volume
            
            # If the curve is parented to the armature or a bone but has no armature modifier,
            # we may still need one for weight deformation
            if not has_armature_mod and orig_parent == armature_object:
                modifier = duplicate.modifiers.new(name="Armature", type="ARMATURE")
                modifier.object = armature_object
                modifier.use_vertex_groups = True
        
        # Copy vertex groups from curve to mesh for weight support
        for vgroup in curve_obj.vertex_groups:
            if vgroup.name not in duplicate.vertex_groups:
                duplicate.vertex_groups.new(name=vgroup.name)
        
        # Copy the original object's visibility state
        duplicate.hide_viewport = curve_obj.hide_viewport
        duplicate.hide_render = curve_obj.hide_render
        
        # Add to our list of temporary objects
        temp_meshes.append(duplicate)
        logging.info(f"Converted curve '{curve_obj.name}' to temporary mesh '{duplicate.name}'")
    
    return temp_meshes, curve_objects


def transfer_weights_from_curve_to_mesh(curve_obj, mesh_obj):
    """
    Attempts to transfer vertex weights from a curve object to a mesh object.
    This is a more complex operation that requires sampling along the curve.
    
    Note: This is a placeholder for future implementation.
    
    Args:
        curve_obj: The source curve object
        mesh_obj: The target mesh object
    """
    # This would require more complex implementation to map curve points to mesh vertices
    # For now, this is left as a placeholder for future implementation
    pass
