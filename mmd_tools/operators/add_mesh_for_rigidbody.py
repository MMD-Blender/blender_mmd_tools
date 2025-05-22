import bpy
from mathutils import Vector
from ..core.rigid_body import FnRigidBody
from ..core.model import FnModel

class AddMeshForRigidbodyOperator(bpy.types.Operator):
    bl_idname = "mmd_tools.add_mesh_for_rigidbody"
    bl_label = "Add Mesh for Selected Rigid Body"
    bl_description = "Create a mesh with the same size and transform as the selected rigid body"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.mmd_type != "RIGID_BODY":
            self.report({'ERROR'}, "Select a rigid body object.")
            return {'CANCELLED'}

        shape = obj.mmd_rigid.shape
        size = Vector(obj.mmd_rigid.size)
        mesh_obj = None
        mesh = None
        name = obj.name + "_mesh"
        if shape == "BOX":
            mesh = bpy.data.meshes.new(name)
            mesh.from_pydata([
                (-size.x, -size.y, -size.z),  # 0: bottom front left
                ( size.x, -size.y, -size.z),  # 1: bottom front right
                ( size.x,  size.y, -size.z),  # 2: bottom back right
                (-size.x,  size.y, -size.z),  # 3: bottom back left
                (-size.x, -size.y,  size.z),  # 4: top front left
                ( size.x, -size.y,  size.z),  # 5: top front right
                ( size.x,  size.y,  size.z),  # 6: top back right
                (-size.x,  size.y,  size.z),  # 7: top back left
            ], [], [
                (0,3,2,1),  # bottom face (-Z) - corrected winding
                (4,5,6,7),  # top face (+Z)
                (0,1,5,4),  # front face (-Y)
                (3,7,6,2),  # back face (+Y)
                (1,2,6,5),  # right face (+X)
                (0,4,7,3)   # left face (-X) - corrected winding
            ])
            mesh_obj = bpy.data.objects.new(name, mesh)
            # FIX: Link to current collection
            bpy.context.collection.objects.link(mesh_obj)
        elif shape == "SPHERE":
            bpy.ops.mesh.primitive_uv_sphere_add(radius=size.x, location=obj.location)
            mesh_obj = context.active_object
            mesh_obj.name = name
        elif shape == "CAPSULE":
            radius = size.x
            height = max(size.z, size.y)
            # Cylinder
            bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=height , location=obj.location)
            mesh_obj = context.active_object
            mesh_obj.name = name

            # Top sphere
            top_loc = obj.location.copy()
            top_loc.z += (height ) / 2
            bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=top_loc)
            top_sphere = context.active_object
            top_sphere.name = name + "_top"

            # Bottom sphere
            bottom_loc = obj.location.copy()
            bottom_loc.z -= (height ) / 2
            bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=bottom_loc)
            bottom_sphere = context.active_object
            bottom_sphere.name = name + "_bottom"

            # Join all parts into one mesh
            bpy.ops.object.select_all(action='DESELECT')
            mesh_obj.select_set(True)
            top_sphere.select_set(True)
            bottom_sphere.select_set(True)
            context.view_layer.objects.active = mesh_obj
            bpy.ops.object.join()
        else:
            self.report({'ERROR'}, f"Unsupported shape: {shape}")
            return {'CANCELLED'}

        if mesh_obj:
            mesh_obj.matrix_world = obj.matrix_world.copy()
            mesh_obj.display_type = 'SOLID'
            mesh_obj.show_transparent = True
            mesh_obj.hide_render = False
            
            # Bind mesh to the bone of the rigid body
            bone_name = obj.mmd_rigid.bone
            root = FnModel.find_root_object(obj)
            if bone_name:
                # Find the armature that has this bone
                
                if root:
                    armature_obj = FnModel.find_armature_object(root)
                    if armature_obj and bone_name in armature_obj.data.bones:
                        # Create vertex group with bone name
                        vertex_group = mesh_obj.vertex_groups.new(name=bone_name)
                        # Add all vertices to the vertex group with full weight
                        vertex_indices = [v.index for v in mesh_obj.data.vertices]
                        if vertex_indices:
                            vertex_group.add(vertex_indices, 1.0, 'REPLACE')
                        
                        # Create armature modifier if it doesn't exist
                        arm_mod = None
                        for mod in mesh_obj.modifiers:
                            if mod.type == 'ARMATURE' and mod.object == armature_obj:
                                arm_mod = mod
                                break
                                
                        if not arm_mod:
                            arm_mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
                            arm_mod.object = armature_obj
                            arm_mod.use_vertex_groups = True
                            
            mesh_obj.select_set(True)
            context.view_layer.objects.active = mesh_obj
            
            # Automatically attach the mesh to the MMD model
            if root:
                # Use the FnModel.attach_mesh_objects function to connect the mesh to the model
                # This is the same function used by the "Attach Meshes to Model" operator
                FnModel.attach_mesh_objects(root, [mesh_obj], True)

        return {'FINISHED'}

def register():
    pass  # Registration handled by auto_load

def unregister():
    pass  # Unregistration handled by auto_load
