import bpy
from bpy.app.handlers import persistent
import time
from mathutils import Matrix, Vector
from . operators.fileio import ExportPmxQuick
from . core.model import FnModel

# Time threshold between auto-exports (in seconds)
MIN_EXPORT_INTERVAL = 0.5
last_export_time = 0

# Track object states
object_states = {}
initial_states = {}  # Track initial states to detect total change

# Track when changes were detected and when to export
last_change_time = 0
STABILITY_THRESHOLD = 0.1  # Reduced for faster response

# Enable/disable auto-export functionality
auto_export_enabled = False

# Store the last known active root
last_active_root = None

# Timer for checking stability
stability_timer = None

# Flag to indicate changes were detected
changes_detected = False

# Root to export after stability is achieved
root_to_export = None

# Add this helper function at the top of the file after imports
def is_valid_object(obj):
    """Check if an object still exists and is valid"""
    try:
        # This will raise an exception if the object has been deleted
        return obj.name in bpy.context.scene.objects
    except (ReferenceError, AttributeError):
        return False

# Function to export model
def export_model(root):
    global last_export_time, auto_export_enabled, last_change_time, changes_detected, initial_states
    
    if not root:
        print("No root to export")
        return
    
    print(f"Exporting model: {root.name}")
    
    # Temporarily disable handler to prevent recursion during export
    auto_export_enabled = False
    
    # Save current selection state and active object
    prev_selected_objects = [obj for obj in bpy.context.selected_objects]
    prev_active_object = bpy.context.active_object
    prev_mode = 'OBJECT'
    if prev_active_object and prev_active_object.mode:
        prev_mode = prev_active_object.mode
    
    try:
        # Properly select the root object
        for obj in bpy.context.selected_objects:
            obj.select_set(False)
        root.select_set(True)
        bpy.context.view_layer.objects.active = root
        
        # Make sure we're in object mode
        if bpy.context.active_object and bpy.context.active_object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        # Run the export
        bpy.ops.mmd_tools.export_pmx_quick()
        print(f"Export complete for {root.name}")
        
        # Update export time and reset change time
        last_export_time = time.time()
        last_change_time = 0  # Reset to detect new changes
        changes_detected = False
        
        # Reset initial states to current states
        initial_states = {}  # Reset initial states after export
    except Exception as e:
        print(f"Error during PMX export: {str(e)}")
    finally:
        # Re-enable handler after export completes or fails
        auto_export_enabled = True
        
        # Restore previous selection state
        for obj in bpy.context.selected_objects:
            obj.select_set(False)
            
        for obj in prev_selected_objects:
            if obj and obj.name in bpy.context.view_layer.objects:
                obj.select_set(True)
                
        # Restore active object
        if prev_active_object and prev_active_object.name in bpy.context.view_layer.objects:
            bpy.context.view_layer.objects.active = prev_active_object
            
            # Restore previous mode if possible
            if prev_mode != 'OBJECT' and prev_active_object.mode == 'OBJECT':
                try:
                    bpy.ops.object.mode_set(mode=prev_mode)
                except Exception as e:
                    print(f"Could not restore previous mode: {str(e)}")

# Stability check timer function
def check_stability_timeout():
    global changes_detected, root_to_export, stability_timer
    
    print("Stability check running")
    
    try:
        # Check if root_to_export still exists
        if changes_detected and root_to_export and is_valid_object(root_to_export):
            print(f"Stability timeout reached, exporting {root_to_export.name}")
            export_model(root_to_export)
        else:
            if root_to_export and not is_valid_object(root_to_export):
                print("Root object was deleted, canceling export")
                root_to_export = None
                changes_detected = False
            else:
                print("Stability timeout reached but no root to export")
    except Exception as e:
        print(f"Error during stability check: {str(e)}")
    finally:
        # Always clean up the timer reference
        stability_timer = None
    
    return None  # Do not repeat

# Forced check handler that runs less frequently but catches any missed movements
def forced_check_handler():
    global object_states, initial_states, last_export_time, changes_detected, root_to_export, last_active_root
    
    # Clean up references to deleted objects
    if root_to_export and not is_valid_object(root_to_export):
        root_to_export = None
        
    if last_active_root and not is_valid_object(last_active_root):
        last_active_root = None
    
    current_time = time.time()
    
    # Skip if too soon after last export
    if current_time - last_export_time < MIN_EXPORT_INTERVAL:
        return 5.0  # Check again in 5 seconds
        
    # Skip if we're already tracking changes
    if changes_detected:
        return 5.0
        
    try:
        # Find all MMD model roots
        mmd_roots = [obj for obj in bpy.context.scene.objects if hasattr(obj, 'mmd_type') and obj.mmd_type == "ROOT"]
        
        # Get active root
        active_root = None
        if bpy.context.active_object:
            try:
                active_root = FnModel.find_root_object(bpy.context.active_object)
            except:
                pass
                
        relevant_root = active_root if active_root else last_active_root
        
        if relevant_root:
            significant_change = False
            
            # Check for significant changes that might have been missed
            try:
                meshes = list(FnModel.iterate_mesh_objects(relevant_root))
                
                for mesh_obj in meshes:
                    if not mesh_obj or not hasattr(mesh_obj, 'matrix_world'):
                        continue
                        
                    # Get current state
                    loc = mesh_obj.matrix_world.to_translation()
                    rot = mesh_obj.matrix_world.to_euler()
                    scale = mesh_obj.matrix_world.to_scale()
                    
                    # Create state string
                    current_state = f"{loc.x:.2f},{loc.y:.2f},{loc.z:.2f}|{rot.x:.2f},{rot.y:.2f},{rot.z:.2f}|{scale.x:.2f},{scale.y:.2f},{scale.z:.2f}"
                    
                    # Check if we have an initial state
                    if mesh_obj.name in initial_states:
                        # Compare with initial state to detect cumulative changes
                        if initial_states[mesh_obj.name] != current_state:
                            print(f"Detected significant change in {mesh_obj.name} during forced check")
                            significant_change = True
                            break
                    else:
                        # Store initial state
                        initial_states[mesh_obj.name] = current_state
            except:
                pass
                
            # If significant changes detected, trigger export
            if significant_change:
                print(f"Significant change detected in forced check for {relevant_root.name}")
                changes_detected = True
                root_to_export = relevant_root
                
                # Set timer to export after stability
                if stability_timer and stability_timer in bpy.app.timers.registered:
                    bpy.app.timers.unregister(stability_timer)
                
                stability_timer = bpy.app.timers.register(
                    check_stability_timeout,
                    first_interval=STABILITY_THRESHOLD
                )
    except Exception as e:
        print(f"Error in forced check: {str(e)}")
        
    return 5.0  # Run again in 5 seconds

# Then modify the track_mmd_changes function to handle deleted objects
@persistent
def track_mmd_changes(scene):
    global last_export_time, object_states, initial_states, last_change_time, auto_export_enabled
    global last_active_root, stability_timer, changes_detected, root_to_export
    
    # Clean up references to deleted objects
    if root_to_export and not is_valid_object(root_to_export):
        root_to_export = None
        
    if last_active_root and not is_valid_object(last_active_root):
        last_active_root = None
    
    # Clean up object_states and initial_states
    deleted_keys = []
    for obj_name in object_states.keys():
        if obj_name not in scene.objects:
            deleted_keys.append(obj_name)
    
    for key in deleted_keys:
        if key in object_states:
            del object_states[key]
        if key in initial_states:
            del initial_states[key]
    
    # Update auto_export_enabled based on active root's setting
    active_obj_root = None
    if bpy.context.active_object:
        try:
            active_obj_root = FnModel.find_root_object(bpy.context.active_object)
            if active_obj_root and hasattr(active_obj_root, 'mmd_root'):
                auto_export_enabled = active_obj_root.mmd_root.auto_export_enabled
        except:
            pass
    
    # Skip if auto-export is disabled
    if not auto_export_enabled:
        return
    
    try:
        current_time = time.time()
        
        # Don't process too frequently if no changes
        if current_time - last_export_time < MIN_EXPORT_INTERVAL and not changes_detected:
            return
            
        # Find all MMD model roots in the scene
        mmd_roots = []
        try:
            mmd_roots = [obj for obj in scene.objects if hasattr(obj, 'mmd_type') and obj.mmd_type == "ROOT"]
        except:
            return  # Skip if we can't get roots
        
        if not mmd_roots:
            return  # No MMD models to process

        # Try to find the active root from current active object
        active_obj_root = None
        if bpy.context.active_object:
            try:
                active_obj_root = FnModel.find_root_object(bpy.context.active_object)
            except:
                pass  # Continue even if we can't find active root
            
            # Update last active root if we found one
            if active_obj_root:
                last_active_root = active_obj_root
        
        # Track if any object is still moving
        any_moving = False
        
        for root in mmd_roots:
            # Check if model has been exported before - REMOVED THIS RESTRICTION
            # if not scene.get("mmd_tools_export_pmx_last_filepath"):
            #     continue
                
            changed = False
            
            try:
                meshes = list(FnModel.iterate_mesh_objects(root))
            except:
                continue  # Skip this root if there's an error
            
            # Check each mesh for changes in transformation
            for mesh_obj in meshes:
                # Create a hash of the object's transformation
                if mesh_obj and hasattr(mesh_obj, 'matrix_world'):
                    try:
                        # Get transformation components with reduced precision to avoid noise
                        loc = mesh_obj.matrix_world.to_translation()
                        rot = mesh_obj.matrix_world.to_euler()
                        scale = mesh_obj.matrix_world.to_scale()
                        
                        # Create state string with lower precision to catch meaningful changes
                        current_state = f"{loc.x:.3f},{loc.y:.3f},{loc.z:.3f}|{rot.x:.3f},{rot.y:.3f},{rot.z:.3f}|{scale.x:.3f},{scale.y:.3f},{scale.z:.3f}"
                        
                        # Store initial state if not already stored
                        if mesh_obj.name not in initial_states:
                            initial_states[mesh_obj.name] = current_state
                        
                        # Check if state changed from the previous frame
                        if mesh_obj.name in object_states:
                            if object_states[mesh_obj.name] != current_state:
                                any_moving = True
                                changed = True
                                # Debug
                                # print(f"Movement detected in {mesh_obj.name}: {object_states[mesh_obj.name]} -> {current_state}")
                        
                        # Update state
                        object_states[mesh_obj.name] = current_state
                    except Exception as e:
                        print(f"Error tracking object {mesh_obj.name}: {str(e)}")
                        continue
                        
            # If active object is in edit mode and is part of this model, consider it changed
            if bpy.context.active_object and bpy.context.active_object.mode == 'EDIT':
                active_obj = bpy.context.active_object
                if active_obj in meshes:
                    changed = True
                    any_moving = True
            
            # If this is the first detection of changes, record the time and root
            if changed:
                last_change_time = current_time
                
                if not changes_detected:
                    changes_detected = True
                    # Remember which root had changes
                    if root == active_obj_root or not root_to_export:
                        root_to_export = root
                    print(f"Movement detected for {root.name}")
                
                # Cancel any existing timer since movement is still happening
                if stability_timer and stability_timer in bpy.app.timers.registered:
                    # print("Canceling previous stability timer - movement continuing")
                    bpy.app.timers.unregister(stability_timer)
                    stability_timer = None
        
        # If nothing is moving and we've detected changes, start a timer
        if changes_detected and not any_moving and not stability_timer:
            # The active root or the last known active root or the root that had changes
            relevant_root = root_to_export
            if not relevant_root:
                relevant_root = active_obj_root if active_obj_root else last_active_root
            
            if relevant_root:
                print(f"Movement stopped for {relevant_root.name}, starting stability timer")
                root_to_export = relevant_root
                
                # Set a timer to check for stability after the threshold
                try:
                    stability_timer = bpy.app.timers.register(
                        check_stability_timeout,
                        first_interval=STABILITY_THRESHOLD
                    )
                    print("Stability timer registered successfully")
                except Exception as e:
                    print(f"Failed to register stability timer: {str(e)}")
            else:
                print("Movement stopped but no relevant root found to export")
            
    except Exception as e:
        print(f"Error in track_mmd_changes: {str(e)}")

def register():
    global last_export_time, last_change_time, changes_detected, root_to_export
    last_export_time = time.time()  # Initialize last export time
    last_change_time = 0  # Initialize to 0 to indicate no changes detected yet
    changes_detected = False
    root_to_export = None
    
    if track_mmd_changes not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(track_mmd_changes)
        print("Auto-export handler registered")
    
    # Register the forced check handler
    if not bpy.app.timers.is_registered(forced_check_handler):
        bpy.app.timers.register(forced_check_handler, first_interval=5.0)
        print("Forced check timer registered")

def unregister():
    global stability_timer
    
    # Clean up timers
    if stability_timer and stability_timer in bpy.app.timers.registered:
        bpy.app.timers.unregister(stability_timer)
        stability_timer = None
    
    if bpy.app.timers.is_registered(forced_check_handler):
        bpy.app.timers.unregister(forced_check_handler)
    
    if track_mmd_changes in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(track_mmd_changes)
        print("Auto-export handler unregistered")