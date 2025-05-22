# Copyright 2015 MMD Tools authors
# This file is part of MMD Tools.

import math
from typing import Dict, Optional, Tuple, cast

import bpy
from mathutils import Euler, Vector

from .. import utils
from ..bpyutils import FnContext, Props
from ..core import rigid_body
from ..core.model import FnModel, Model
from ..core.rigid_body import FnRigidBody


class SelectRigidBody(bpy.types.Operator):
    bl_idname = "mmd_tools.rigid_body_select"
    bl_label = "Select Rigid Body"
    bl_description = "Select similar rigidbody objects which have the same property values with active rigidbody object"
    bl_options = {"REGISTER", "UNDO"}

    properties: bpy.props.EnumProperty(
        name="Properties",
        description="Select the properties to be compared",
        options={"ENUM_FLAG"},
        items=[
            ("collision_group_number", "Collision Group", "Collision group", 1),
            ("collision_group_mask", "Collision Group Mask", "Collision group mask", 2),
            ("type", "Rigid Type", "Rigid type", 4),
            ("shape", "Shape", "Collision shape", 8),
            ("bone", "Bone", "Target bone", 16),
        ],
        default=set(),
    )
    hide_others: bpy.props.BoolProperty(
        name="Hide Others",
        description="Hide the rigidbody object which does not have the same property values with active rigidbody object",
        default=False,
    )

    def invoke(self, context, event):
        vm = context.window_manager
        return vm.invoke_props_dialog(self)

    @classmethod
    def poll(cls, context):
        return FnModel.is_rigid_body_object(context.active_object)

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        if root is None:
            self.report({"ERROR"}, "The model root can't be found")
            return {"CANCELLED"}

        selection = set(FnModel.iterate_rigid_body_objects(root))

        for prop_name in self.properties:
            prop_value = getattr(obj.mmd_rigid, prop_name)
            if prop_name == "collision_group_mask":
                prop_value = tuple(prop_value)
                for i in selection.copy():
                    if tuple(i.mmd_rigid.collision_group_mask) != prop_value:
                        selection.remove(i)
                        if self.hide_others:
                            i.select_set(False)
                            i.hide_set(True)
            else:
                for i in selection.copy():
                    if getattr(i.mmd_rigid, prop_name) != prop_value:
                        selection.remove(i)
                        if self.hide_others:
                            i.select_set(False)
                            i.hide_set(True)

        for i in selection:
            i.hide_set(False)
            i.select_set(True)

        return {"FINISHED"}


class AddRigidBody(bpy.types.Operator):
    bl_idname = "mmd_tools.rigid_body_add"
    bl_label = "Add Rigid Body"
    bl_description = "Add Rigid Bodies to selected bones"
    bl_options = {"REGISTER", "UNDO", "PRESET", "INTERNAL"}

    name_j: bpy.props.StringProperty(
        name="Name",
        description="The name of rigid body ($name_j means use the japanese name of target bone)",
        default="$name_j",
    )
    name_e: bpy.props.StringProperty(
        name="Name(Eng)",
        description="The english name of rigid body ($name_e means use the english name of target bone)",
        default="$name_e",
    )
    collision_group_number: bpy.props.IntProperty(
        name="Collision Group",
        description="The collision group of the object",
        min=0,
        max=15,
    )
    collision_group_mask: bpy.props.BoolVectorProperty(
        name="Collision Group Mask",
        description="The groups the object can not collide with",
        size=16,
        subtype="LAYER",
    )
    rigid_type: bpy.props.EnumProperty(
        name="Rigid Type",
        description="Select rigid type",
        items=[
            (str(rigid_body.MODE_STATIC), "Bone", "Rigid body's orientation completely determined by attached bone", 1),
            (str(rigid_body.MODE_DYNAMIC), "Physics", "Attached bone's orientation completely determined by rigid body", 2),
            (str(rigid_body.MODE_DYNAMIC_BONE), "Physics + Bone", "Bone determined by combination of parent and attached rigid body", 3),
        ],
    )
    rigid_shape: bpy.props.EnumProperty(
        name="Shape",
        description="Select the collision shape",
        items=[
            ("SPHERE", "Sphere", "", 1),
            ("BOX", "Box", "", 2),
            ("CAPSULE", "Capsule", "", 3),
        ],
    )
    size: bpy.props.FloatVectorProperty(
        name="Size",
        description="Size of the object, the values will multiply the length of target bone",
        subtype="XYZ",
        size=3,
        min=0,
        default=[0.6, 0.6, 0.6],
    )
    mass: bpy.props.FloatProperty(
        name="Mass",
        description="How much the object 'weights' irrespective of gravity",
        min=0.001,
        default=1,
    )
    friction: bpy.props.FloatProperty(
        name="Friction",
        description="Resistance of object to movement",
        min=0,
        soft_max=1,
        default=0.5,
    )
    bounce: bpy.props.FloatProperty(
        name="Restitution",
        description="Tendency of object to bounce after colliding with another (0 = stays still, 1 = perfectly elastic)",
        min=0,
        soft_max=1,
    )
    linear_damping: bpy.props.FloatProperty(
        name="Linear Damping",
        description="Amount of linear velocity that is lost over time",
        min=0,
        max=1,
        default=0.04,
    )
    angular_damping: bpy.props.FloatProperty(
        name="Angular Damping",
        description="Amount of angular velocity that is lost over time",
        min=0,
        max=1,
        default=0.1,
    )

    def __add_rigid_body(self, context: bpy.types.Context, root_object: bpy.types.Object, pose_bone: Optional[bpy.types.PoseBone] = None):
        name_j: str = self.name_j
        name_e: str = self.name_e
        size = self.size.copy()
        loc = Vector((0.0, 0.0, 0.0))
        rot = Euler((0.0, 0.0, 0.0))
        bone_name: Optional[str] = None

        if pose_bone is None:
            size *= getattr(root_object, Props.empty_display_size)
        else:
            bone_name = pose_bone.name
            mmd_bone = pose_bone.mmd_bone
            name_j = name_j.replace("$name_j", mmd_bone.name_j or bone_name)
            name_e = name_e.replace("$name_e", mmd_bone.name_e or bone_name)

            target_bone = pose_bone.bone
            loc = (target_bone.head_local + target_bone.tail_local) / 2
            rot = target_bone.matrix_local.to_euler("YXZ")
            rot.rotate_axis("X", math.pi / 2)

            size *= target_bone.length
            if 1:
                pass  # bypass resizing
            elif self.rigid_shape == "SPHERE":
                size.x *= 0.8
            elif self.rigid_shape == "BOX":
                size.x /= 3
                size.y /= 3
                size.z *= 0.8
            elif self.rigid_shape == "CAPSULE":
                size.x /= 3

        return FnRigidBody.setup_rigid_body_object(
            obj=FnRigidBody.new_rigid_body_object(context, FnModel.ensure_rigid_group_object(context, root_object)),
            shape_type=rigid_body.shapeType(self.rigid_shape),
            location=loc,
            rotation=rot,
            size=size,
            dynamics_type=int(self.rigid_type),
            name=name_j,
            name_e=name_e,
            collision_group_number=self.collision_group_number,
            collision_group_mask=self.collision_group_mask,
            mass=self.mass,
            friction=self.friction,
            bounce=self.bounce,
            linear_damping=self.linear_damping,
            angular_damping=self.angular_damping,
            bone=bone_name,
        )

    @classmethod
    def poll(cls, context):
        root_object = FnModel.find_root_object(context.active_object)
        if root_object is None:
            return False

        armature_object = FnModel.find_armature_object(root_object)
        if armature_object is None:
            return False

        return True

    def execute(self, context):
        active_object = context.active_object

        root_object = cast(bpy.types.Object, FnModel.find_root_object(active_object))
        armature_object = cast(bpy.types.Object, FnModel.find_armature_object(root_object))

        if active_object != armature_object:
            FnContext.select_single_object(context, root_object).select_set(False)
        elif armature_object.mode != "POSE":
            bpy.ops.object.mode_set(mode="POSE")

        selected_pose_bones = []
        if context.selected_pose_bones:
            selected_pose_bones = context.selected_pose_bones

        armature_object.select_set(False)
        if len(selected_pose_bones) > 0:
            for pose_bone in selected_pose_bones:
                rigid = self.__add_rigid_body(context, root_object, pose_bone)
                rigid.select_set(True)
        else:
            rigid = self.__add_rigid_body(context, root_object)
            rigid.select_set(True)
        return {"FINISHED"}

    def invoke(self, context, event):
        no_bone = True
        if context.selected_bones and len(context.selected_bones) > 0:
            no_bone = False
        elif context.selected_pose_bones and len(context.selected_pose_bones) > 0:
            no_bone = False

        if no_bone:
            self.name_j = "Rigid"
            self.name_e = "Rigid_e"
        else:
            if self.name_j == "Rigid":
                self.name_j = "$name_j"
            if self.name_e == "Rigid_e":
                self.name_e = "$name_e"
        vm = context.window_manager
        return vm.invoke_props_dialog(self)


class RemoveRigidBody(bpy.types.Operator):
    bl_idname = "mmd_tools.rigid_body_remove"
    bl_label = "Remove Rigid Body"
    bl_description = "Deletes the currently selected Rigid Body"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return FnModel.is_rigid_body_object(context.active_object)

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        utils.selectAObject(obj)  # ensure this is the only one object select
        bpy.ops.object.delete(use_global=True)
        if root:
            utils.selectAObject(root)
        return {"FINISHED"}


class RigidBodyBake(bpy.types.Operator):
    bl_idname = "mmd_tools.ptcache_rigid_body_bake"
    bl_label = "Bake"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context: bpy.types.Context):
        with context.temp_override(scene=context.scene, point_cache=context.scene.rigidbody_world.point_cache):
            bpy.ops.ptcache.bake("INVOKE_DEFAULT", bake=True)

        return {"FINISHED"}


class RigidBodyDeleteBake(bpy.types.Operator):
    bl_idname = "mmd_tools.ptcache_rigid_body_delete_bake"
    bl_label = "Delete Bake"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context: bpy.types.Context):
        with context.temp_override(scene=context.scene, point_cache=context.scene.rigidbody_world.point_cache):
            bpy.ops.ptcache.free_bake("INVOKE_DEFAULT")

        return {"FINISHED"}


class AddJoint(bpy.types.Operator):
    bl_idname = "mmd_tools.joint_add"
    bl_label = "Add Joint"
    bl_description = "Add Joint(s) to selected rigidbody objects"
    bl_options = {"REGISTER", "UNDO", "PRESET", "INTERNAL"}

    use_bone_rotation: bpy.props.BoolProperty(
        name="Use Bone Rotation",
        description="Match joint orientation to bone orientation if enabled",
        default=True,
    )
    limit_linear_lower: bpy.props.FloatVectorProperty(
        name="Limit Linear Lower",
        description="Lower limit of translation",
        subtype="XYZ",
        size=3,
    )
    limit_linear_upper: bpy.props.FloatVectorProperty(
        name="Limit Linear Upper",
        description="Upper limit of translation",
        subtype="XYZ",
        size=3,
    )
    limit_angular_lower: bpy.props.FloatVectorProperty(
        name="Limit Angular Lower",
        description="Lower limit of rotation",
        subtype="EULER",
        size=3,
        min=-math.pi * 2,
        max=math.pi * 2,
        default=[-math.pi / 4] * 3,
    )
    limit_angular_upper: bpy.props.FloatVectorProperty(
        name="Limit Angular Upper",
        description="Upper limit of rotation",
        subtype="EULER",
        size=3,
        min=-math.pi * 2,
        max=math.pi * 2,
        default=[math.pi / 4] * 3,
    )
    spring_linear: bpy.props.FloatVectorProperty(
        name="Spring(Linear)",
        description="Spring constant of movement",
        subtype="XYZ",
        size=3,
        min=0,
    )
    spring_angular: bpy.props.FloatVectorProperty(
        name="Spring(Angular)",
        description="Spring constant of rotation",
        subtype="XYZ",
        size=3,
        min=0,
    )

    def __enumerate_rigid_pair(self, bone_map: Dict[bpy.types.Object, Optional[bpy.types.Bone]]):
        obj_seq = tuple(bone_map.keys())
        for rigid_a, bone_a in bone_map.items():
            for rigid_b, bone_b in bone_map.items():
                if bone_a and bone_b and bone_b.parent == bone_a:
                    obj_seq = ()
                    yield (rigid_a, rigid_b)
        if len(obj_seq) == 2:
            if obj_seq[1].mmd_rigid.type == str(rigid_body.MODE_STATIC):
                yield (obj_seq[1], obj_seq[0])
            else:
                yield obj_seq

    def __add_joint(self, context: bpy.types.Context, root_object: bpy.types.Object, rigid_pair: Tuple[bpy.types.Object, bpy.types.Object], bone_map):
        loc: Optional[Vector] = None
        rot = Euler((0.0, 0.0, 0.0))
        rigid_a, rigid_b = rigid_pair
        bone_a = bone_map[rigid_a]
        bone_b = bone_map[rigid_b]
        if bone_a and bone_b:
            if bone_a.parent == bone_b:
                rigid_b, rigid_a = rigid_a, rigid_b
                bone_b, bone_a = bone_a, bone_b
            if bone_b.parent == bone_a:
                loc = bone_b.head_local
                if self.use_bone_rotation:
                    rot = bone_b.matrix_local.to_euler("YXZ")
                    rot.rotate_axis("X", math.pi / 2)
        if loc is None:
            loc = (rigid_a.location + rigid_b.location) / 2

        name_j = rigid_b.mmd_rigid.name_j or rigid_b.name
        name_e = rigid_b.mmd_rigid.name_e or rigid_b.name

        return FnRigidBody.setup_joint_object(
            obj=FnRigidBody.new_joint_object(context, FnModel.ensure_joint_group_object(context, root_object), FnModel.get_empty_display_size(root_object)),
            name=name_j,
            name_e=name_e,
            location=loc,
            rotation=rot,
            rigid_a=rigid_a,
            rigid_b=rigid_b,
            maximum_location=self.limit_linear_upper,
            minimum_location=self.limit_linear_lower,
            maximum_rotation=self.limit_angular_upper,
            minimum_rotation=self.limit_angular_lower,
            spring_linear=self.spring_linear,
            spring_angular=self.spring_angular,
        )

    @classmethod
    def poll(cls, context):
        root_object = FnModel.find_root_object(context.active_object)
        if root_object is None:
            return False

        armature_object = FnModel.find_armature_object(root_object)
        if armature_object is None:
            return False

        return True

    def execute(self, context):
        active_object = context.active_object
        root_object = cast(bpy.types.Object, FnModel.find_root_object(active_object))
        armature_object = cast(bpy.types.Object, FnModel.find_armature_object(root_object))
        bones = cast(bpy.types.Armature, armature_object.data).bones
        bone_map: Dict[bpy.types.Object, Optional[bpy.types.Bone]] = {r: bones.get(r.mmd_rigid.bone, None) for r in FnModel.iterate_rigid_body_objects(root_object) if r.select_get()}

        # If only one rigid body is selected, create a joint at its location
        if len(bone_map) == 1:
            rigid = next(iter(bone_map.keys()))
            joint_object = FnRigidBody.new_joint_object(context, FnModel.ensure_joint_group_object(context, root_object), FnModel.get_empty_display_size(root_object))
            
            # Use the rigid body's name for the joint
            name_j = rigid.mmd_rigid.name_j or rigid.name
            name_e = rigid.mmd_rigid.name_e or rigid.name
            
            # Use the location and rotation of the rigid body for the joint
            loc = rigid.location
            rot = rigid.rotation_euler
            
            # Set up the joint with itself as both objects (user will need to set second object manually)
            joint = FnRigidBody.setup_joint_object(
                obj=joint_object,
                name=name_j + "_joint",
                name_e=name_e + "_joint",
                location=loc,
                rotation=rot,
                rigid_a=rigid,
                rigid_b=rigid,  # Temporarily set same object, user needs to change
                maximum_location=self.limit_linear_upper,
                minimum_location=self.limit_linear_lower,
                maximum_rotation=self.limit_angular_upper,
                minimum_rotation=self.limit_angular_lower,
                spring_linear=self.spring_linear,
                spring_angular=self.spring_angular,
            )
            joint.select_set(True)
            self.report({"INFO"}, "Created joint at rigid body location. Please set the second rigid body manually.")
            return {"FINISHED"}
        elif len(bone_map) < 2:
            self.report({"ERROR"}, "Please select one or more mmd rigid objects")
            return {"CANCELLED"}
        
        

        FnContext.select_single_object(context, root_object).select_set(False)
        if context.scene.rigidbody_world is None:
            bpy.ops.rigidbody.world_add()

        for pair in self.__enumerate_rigid_pair(bone_map):
            joint = self.__add_joint(context, root_object, pair, bone_map)
            joint.select_set(True)

        return {"FINISHED"}

    def invoke(self, context, event):
        vm = context.window_manager
        return vm.invoke_props_dialog(self)


class RemoveJoint(bpy.types.Operator):
    bl_idname = "mmd_tools.joint_remove"
    bl_label = "Remove Joint"
    bl_description = "Deletes the currently selected Joint"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return FnModel.is_joint_object(context.active_object)

    def execute(self, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        utils.selectAObject(obj)  # ensure this is the only one object select
        bpy.ops.object.delete(use_global=True)
        if root:
            utils.selectAObject(root)
        return {"FINISHED"}


class UpdateRigidBodyWorld(bpy.types.Operator):
    bl_idname = "mmd_tools.rigid_body_world_update"
    bl_label = "Update Rigid Body World"
    bl_description = "Update rigid body world and references of rigid body constraint according to current scene objects (experimental)"
    bl_options = {"REGISTER", "UNDO"}

    @staticmethod
    def __get_rigid_body_world_objects():
        rigid_body.setRigidBodyWorldEnabled(True)
        rbw = bpy.context.scene.rigidbody_world
        if not rbw.collection:
            rbw.collection = bpy.data.collections.new("RigidBodyWorld")
            rbw.collection.use_fake_user = True
        if not rbw.constraints:
            rbw.constraints = bpy.data.collections.new("RigidBodyConstraints")
            rbw.constraints.use_fake_user = True

        bpy.context.scene.rigidbody_world.substeps_per_frame = 6
        bpy.context.scene.rigidbody_world.solver_iterations = 10

        return rbw.collection.objects, rbw.constraints.objects

    def execute(self, context):
        scene = context.scene
        scene_objs = set(scene.objects)
        scene_objs.union(o for x in scene.objects if x.instance_type == "COLLECTION" and x.instance_collection for o in x.instance_collection.objects)

        def _update_group(obj, group):
            if obj in scene_objs:
                if obj not in group.values():
                    group.link(obj)
                return True
            elif obj in group.values():
                group.unlink(obj)
            return False

        def _references(obj):
            yield obj
            if getattr(obj, "proxy", None):
                yield from _references(obj.proxy)
            if getattr(obj, "override_library", None):
                yield from _references(obj.override_library.reference)

        need_rebuild_physics = scene.rigidbody_world is None or scene.rigidbody_world.collection is None or scene.rigidbody_world.constraints is None
        rb_objs, rbc_objs = self.__get_rigid_body_world_objects()
        objects = bpy.data.objects
        table = {}

        # Perhaps due to a bug in Blender,
        # when bpy.ops.rigidbody.world_remove(),
        # Object.rigid_body are removed,
        # but Object.rigid_body_constraint are retained.
        # Therefore, it must be checked with Object.mmd_type.
        for i in (x for x in objects if x.mmd_type == "RIGID_BODY"):
            if not _update_group(i, rb_objs):
                continue

            rb_map = table.setdefault(FnModel.find_root_object(i), {})
            if i in rb_map:  # means rb_map[i] will replace i
                rb_objs.unlink(i)
                continue
            for r in _references(i):
                rb_map[r] = i

            # TODO Modify mmd_rigid to allow recovery of the remaining rigidbody parameters.
            # mass, friction, restitution, linear_dumping, angular_dumping

        for i in (x for x in objects if x.rigid_body_constraint):
            if not _update_group(i, rbc_objs):
                continue

            rbc, root_object = i.rigid_body_constraint, FnModel.find_root_object(i)
            rb_map = table.get(root_object, {})
            rbc.object1 = rb_map.get(rbc.object1, rbc.object1)
            rbc.object2 = rb_map.get(rbc.object2, rbc.object2)

        if need_rebuild_physics:
            for root_object in scene.objects:
                if root_object.mmd_type != "ROOT":
                    continue
                if not root_object.mmd_root.is_built:
                    continue
                with FnContext.temp_override_active_layer_collection(context, root_object):
                    Model(root_object).build()
                    # After rebuild. First play. Will be crash!
                    # But saved it before. Reload after crash. The play can be work.

        return {"FINISHED"}
