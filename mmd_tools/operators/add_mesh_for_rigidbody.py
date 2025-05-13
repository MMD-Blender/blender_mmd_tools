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
                (-size.x, -size.y, -size.z),
                ( size.x, -size.y, -size.z),
                ( size.x,  size.y, -size.z),
                (-size.x,  size.y, -size.z),
                (-size.x, -size.y,  size.z),
                ( size.x, -size.y,  size.z),
                ( size.x,  size.y,  size.z),
                (-size.x,  size.y,  size.z),
            ], [], [
                (0,1,2,3), (4,5,6,7), (0,1,5,4), (2,3,7,6), (1,2,6,5), (0,3,7,4)
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
            bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=height, location=obj.location)
            mesh_obj = context.active_object
            mesh_obj.name = name

            # Top half sphere
            top_loc = obj.location.copy()
            top_loc.z += height / 2
            bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=top_loc)
            top_sphere = context.active_object
            top_sphere.name = name + "_top"
            # Delete lower half
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
            # Select vertices in lower half
            for v in top_sphere.data.vertices:
                if v.co.z < 0:
                    v.select = True
            # Delete selected vertices
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.delete(type='VERT')
            bpy.ops.object.mode_set(mode='OBJECT')

            # Bottom half sphere
            bottom_loc = obj.location.copy()
            bottom_loc.z -= height / 2
            bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=bottom_loc)
            bottom_sphere = context.active_object
            bottom_sphere.name = name + "_bottom"
            # Delete upper half
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
            # Select vertices in upper half
            for v in bottom_sphere.data.vertices:
                if v.co.z > 0:
                    v.select = True
            # Delete selected vertices
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.delete(type='VERT')
            bpy.ops.object.mode_set(mode='OBJECT')

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
            mesh_obj.select_set(True)
            context.view_layer.objects.active = mesh_obj

        return {'FINISHED'}

def register():
    bpy.utils.register_class(AddMeshForRigidbodyOperator)

def unregister():
    bpy.utils.unregister_class(AddMeshForRigidbodyOperator)
