# -*- coding: utf-8 -*-
# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

import logging
import time
from typing import List, Optional, cast

import bpy
from mathutils import Euler, Vector

from ..bpyutils import FnContext, Props

SHAPE_SPHERE = 0
SHAPE_BOX = 1
SHAPE_CAPSULE = 2

MODE_STATIC = 0
MODE_DYNAMIC = 1
MODE_DYNAMIC_BONE = 2


def shapeType(collision_shape):
    return ("SPHERE", "BOX", "CAPSULE").index(collision_shape)


def collisionShape(shape_type):
    return ("SPHERE", "BOX", "CAPSULE")[shape_type]


class RigidBodyMaterial:
    COLORS = [
        0x7FDDD4,
        0xF0E68C,
        0xEE82EE,
        0xFFE4E1,
        0x8FEEEE,
        0xADFF2F,
        0xFA8072,
        0x9370DB,
        0x40E0D0,
        0x96514D,
        0x5A964E,
        0xE6BFAB,
        0xD3381C,
        0x165E83,
        0x701682,
        0x828216,
    ]

    @classmethod
    def get_material(cls, number):
        number = int(number)
        material_name = f"mmd_tools_rigid_{number}"
        if material_name in bpy.data.materials:
            return bpy.data.materials[material_name]

        mat = bpy.data.materials.new(material_name)
        color = cls.COLORS[number]
        mat.diffuse_color[:3] = [((0xFF0000 & color) >> 16) / float(255), ((0x00FF00 & color) >> 8) / float(255), (0x0000FF & color) / float(255)]
        mat.specular_intensity = 0
        if len(mat.diffuse_color) > 3:
            mat.diffuse_color[3] = 0.5
        mat.blend_method = "BLEND"
        mat.shadow_method = "NONE"
        mat.use_backface_culling = True
        mat.use_backface_culling_shadow = False
        mat.use_backface_culling_lightprobe_volume = True
        mat.show_transparent_back = False
        mat.use_nodes = True
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        nodes.clear()
        node_color = nodes.new("ShaderNodeBackground")
        node_color.inputs["Color"].default_value = mat.diffuse_color
        node_output = nodes.new("ShaderNodeOutputMaterial")
        links.new(node_color.outputs[0], node_output.inputs["Surface"])
        return mat


class FnRigidBody:
    @staticmethod
    def get_and_set_rigid_body_world_enabled(enable: bool, context: Optional[bpy.types.Context] = None) -> bool:
        if bpy.ops.rigidbody.world_add.poll():
            bpy.ops.rigidbody.world_add()
        rigidbody_world = FnContext.ensure_context(context).scene.rigidbody_world
        previous_enabled = rigidbody_world.enabled
        rigidbody_world.enabled = enable
        return previous_enabled

    @staticmethod
    def new_rigid_body_objects(context: bpy.types.Context, parent_object: bpy.types.Object, count: int) -> List[bpy.types.Object]:
        if count < 1:
            return []

        obj = FnRigidBody.new_rigid_body_object(context, parent_object)

        if count == 1:
            return [obj]

        return FnContext.duplicate_object(context, obj, count)

    @staticmethod
    def new_rigid_body_object(context: bpy.types.Context, parent_object: bpy.types.Object) -> bpy.types.Object:
        obj = FnContext.new_and_link_object(context, name="Rigidbody", object_data=bpy.data.meshes.new(name="Rigidbody"))
        obj.parent = parent_object
        obj.mmd_type = "RIGID_BODY"
        obj.rotation_mode = "YXZ"
        setattr(obj, Props.display_type, "SOLID")
        obj.show_transparent = True
        obj.hide_render = True
        obj.display.show_shadows = False

        with context.temp_override(object=obj):
            bpy.ops.rigidbody.object_add(type="ACTIVE")

        return obj

    @staticmethod
    def setup_rigid_body_object(
        obj: bpy.types.Object,
        shape_type: str,
        location: Vector,
        rotation: Euler,
        size: Vector,
        dynamics_type: str,
        collision_group_number: Optional[int] = None,
        collision_group_mask: Optional[List[bool]] = None,
        name: Optional[str] = None,
        name_e: Optional[str] = None,
        bone: Optional[str] = None,
        friction: Optional[float] = None,
        mass: Optional[float] = None,
        angular_damping: Optional[float] = None,
        linear_damping: Optional[float] = None,
        bounce: Optional[float] = None,
    ) -> bpy.types.Object:
        obj.location = location
        obj.rotation_euler = rotation

        obj.mmd_rigid.shape = collisionShape(shape_type)
        obj.mmd_rigid.size = size
        obj.mmd_rigid.type = str(dynamics_type) if dynamics_type in range(3) else "1"

        if collision_group_number is not None:
            obj.mmd_rigid.collision_group_number = collision_group_number

        if collision_group_mask is not None:
            obj.mmd_rigid.collision_group_mask = collision_group_mask

        if name is not None:
            obj.name = name
            obj.mmd_rigid.name_j = name
            obj.data.name = name

        if name_e is not None:
            obj.mmd_rigid.name_e = name_e

        if bone is not None:
            obj.mmd_rigid.bone = bone
        else:
            obj.mmd_rigid.bone = ""

        rb = obj.rigid_body
        if friction is not None:
            rb.friction = friction
        if mass is not None:
            rb.mass = mass
        if angular_damping is not None:
            rb.angular_damping = angular_damping
        if linear_damping is not None:
            rb.linear_damping = linear_damping
        if bounce is not None:
            rb.restitution = bounce

        return obj

    @staticmethod
    def get_rigid_body_size(obj: bpy.types.Object):
        assert obj.mmd_type == "RIGID_BODY"

        x0, y0, z0 = obj.bound_box[0]
        x1, y1, z1 = obj.bound_box[6]
        assert x1 >= x0 and y1 >= y0 and z1 >= z0

        shape = obj.mmd_rigid.shape
        if shape == "SPHERE":
            radius = (z1 - z0) / 2
            return (radius, 0.0, 0.0)
        elif shape == "BOX":
            x, y, z = (x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2
            return (x, y, z)
        elif shape == "CAPSULE":
            diameter = x1 - x0
            radius = diameter / 2
            height = abs((z1 - z0) - diameter)
            return (radius, height, 0.0)
        else:
            raise ValueError(f"Invalid shape type: {shape}")

    @staticmethod
    def new_joint_object(context: bpy.types.Context, parent_object: bpy.types.Object, empty_display_size: float) -> bpy.types.Object:
        obj = FnContext.new_and_link_object(context, name="Joint", object_data=None)
        obj.parent = parent_object
        obj.mmd_type = "JOINT"
        obj.rotation_mode = "YXZ"
        setattr(obj, Props.empty_display_type, "ARROWS")
        setattr(obj, Props.empty_display_size, 0.1 * empty_display_size)
        obj.hide_render = True

        with context.temp_override():
            context.view_layer.objects.active = obj
            bpy.ops.rigidbody.constraint_add(type="GENERIC_SPRING")

        rigid_body_constraint = obj.rigid_body_constraint
        rigid_body_constraint.disable_collisions = False
        rigid_body_constraint.use_limit_ang_x = True
        rigid_body_constraint.use_limit_ang_y = True
        rigid_body_constraint.use_limit_ang_z = True
        rigid_body_constraint.use_limit_lin_x = True
        rigid_body_constraint.use_limit_lin_y = True
        rigid_body_constraint.use_limit_lin_z = True
        rigid_body_constraint.use_spring_x = True
        rigid_body_constraint.use_spring_y = True
        rigid_body_constraint.use_spring_z = True
        rigid_body_constraint.use_spring_ang_x = True
        rigid_body_constraint.use_spring_ang_y = True
        rigid_body_constraint.use_spring_ang_z = True

        return obj

    @staticmethod
    def new_joint_objects(context: bpy.types.Context, parent_object: bpy.types.Object, count: int, empty_display_size: float) -> List[bpy.types.Object]:
        if count < 1:
            return []

        obj = FnRigidBody.new_joint_object(context, parent_object, empty_display_size)

        if count == 1:
            return [obj]

        return FnContext.duplicate_object(context, obj, count)

    @staticmethod
    def setup_joint_object(
        obj: bpy.types.Object,
        location: Vector,
        rotation: Euler,
        rigid_a: bpy.types.Object,
        rigid_b: bpy.types.Object,
        maximum_location: Vector,
        minimum_location: Vector,
        maximum_rotation: Euler,
        minimum_rotation: Euler,
        spring_angular: Vector,
        spring_linear: Vector,
        name: str,
        name_e: Optional[str] = None,
    ) -> bpy.types.Object:
        obj.name = f"J.{name}"

        obj.location = location
        obj.rotation_euler = rotation

        rigid_body_constraint = obj.rigid_body_constraint
        rigid_body_constraint.object1 = rigid_a
        rigid_body_constraint.object2 = rigid_b
        rigid_body_constraint.limit_lin_x_upper = maximum_location.x
        rigid_body_constraint.limit_lin_y_upper = maximum_location.y
        rigid_body_constraint.limit_lin_z_upper = maximum_location.z

        rigid_body_constraint.limit_lin_x_lower = minimum_location.x
        rigid_body_constraint.limit_lin_y_lower = minimum_location.y
        rigid_body_constraint.limit_lin_z_lower = minimum_location.z

        rigid_body_constraint.limit_ang_x_upper = maximum_rotation.x
        rigid_body_constraint.limit_ang_y_upper = maximum_rotation.y
        rigid_body_constraint.limit_ang_z_upper = maximum_rotation.z

        rigid_body_constraint.limit_ang_x_lower = minimum_rotation.x
        rigid_body_constraint.limit_ang_y_lower = minimum_rotation.y
        rigid_body_constraint.limit_ang_z_lower = minimum_rotation.z

        obj.mmd_joint.name_j = name
        if name_e is not None:
            obj.mmd_joint.name_e = name_e

        obj.mmd_joint.spring_linear = spring_linear
        obj.mmd_joint.spring_angular = spring_angular

        return obj

    __LOCATION_ATTRIBUTE_NAME = "location"
    __LOCATION_BACKUP_ATTRIBUTE_NAME = "__backup_location__"
    __ROTATION_EULER_ATTRIBUTE_NAME = "rotation_euler"
    __ROTATION_EULER_BACKUP_ATTRIBUTE_NAME = "__backup_rotation_euler__"

    @staticmethod
    def backup_transforms(obj: bpy.types.Object):
        if FnRigidBody.__LOCATION_BACKUP_ATTRIBUTE_NAME not in obj:
            obj[FnRigidBody.__LOCATION_BACKUP_ATTRIBUTE_NAME] = getattr(obj, FnRigidBody.__LOCATION_ATTRIBUTE_NAME, None)

        if FnRigidBody.__ROTATION_EULER_BACKUP_ATTRIBUTE_NAME not in obj:
            obj[FnRigidBody.__ROTATION_EULER_BACKUP_ATTRIBUTE_NAME] = getattr(obj, FnRigidBody.__ROTATION_EULER_ATTRIBUTE_NAME, None)

    @staticmethod
    def restore_transforms(obj: bpy.types.Object):
        val = obj.get(FnRigidBody.__LOCATION_BACKUP_ATTRIBUTE_NAME, None)
        if val is not None:
            setattr(obj, FnRigidBody.__LOCATION_ATTRIBUTE_NAME, val)
            del obj[FnRigidBody.__LOCATION_BACKUP_ATTRIBUTE_NAME]

        val = obj.get(FnRigidBody.__ROTATION_EULER_BACKUP_ATTRIBUTE_NAME, None)
        if val is not None:
            setattr(obj, FnRigidBody.__ROTATION_EULER_ATTRIBUTE_NAME, val)
            del obj[FnRigidBody.__ROTATION_EULER_BACKUP_ATTRIBUTE_NAME]


class RigidBodyPhysicsCleaner:
    @staticmethod
    def clean(
        context: bpy.types.Context,
        root_object: bpy.types.Object,
        armature_object: Optional[bpy.types.Object],
        rigid_group_object: bpy.types.Object,
        rigid_body_objects: List[bpy.types.Object],
        joint_objects: List[bpy.types.Object],
        temporary_objects: List[bpy.types.Object],
    ):
        rigidbody_world_enabled = FnRigidBody.get_and_set_rigid_body_world_enabled(False, context=context)
        try:
            logging.info("****************************************")
            logging.info(" Clean Rigid Body Physics")
            logging.info("****************************************")
            start_time = time.time()

            RigidBodyPhysicsCleaner._clean_pose_bones(armature_object)
            RigidBodyPhysicsCleaner._clean_rigid_body_objects(rigid_group_object, rigid_body_objects)
            RigidBodyPhysicsCleaner._clean_joint_objects(joint_objects)
            RigidBodyPhysicsCleaner._clean_temorary_objects(context, root_object, temporary_objects)

            if armature_object is not None:  # update armature
                armature_object.update_tag()
                FnContext.viewlayer_update(context)

            RigidBodyPhysicsCleaner._clean_root_object(root_object)

            logging.info(" Finished cleaning in %f seconds.", time.time() - start_time)

        finally:
            FnRigidBody.get_and_set_rigid_body_world_enabled(rigidbody_world_enabled, context=context)

    @staticmethod
    def _clean_root_object(root_object):
        mmd_root = root_object.mmd_root
        if mmd_root.show_temporary_objects:
            mmd_root.show_temporary_objects = False
        mmd_root.is_built = False

    @staticmethod
    def _clean_temorary_objects(context, root_object, temporary_objects):
        with FnContext.temp_override_objects(context, selected_objects=temporary_objects, active_object=root_object):
            bpy.ops.object.delete()

    @staticmethod
    def _clean_joint_objects(joint_objects):
        for joint_body_object in joint_objects:
            FnRigidBody.restore_transforms(joint_body_object)

    @staticmethod
    def _clean_rigid_body_objects(rigid_group_object, rigid_body_objects):
        rigid_track_counts = 0
        for rigid_body_object in rigid_body_objects:
            rigid_type = int(rigid_body_object.mmd_rigid.type)
            if "mmd_tools_rigid_parent" not in rigid_body_object.constraints:
                rigid_track_counts += 1
                logging.info('%3d# Create a "CHILD_OF" constraint for %s', rigid_track_counts, rigid_body_object.name)
                rigid_body_object.mmd_rigid.bone = rigid_body_object.mmd_rigid.bone
            relation_constraint = cast(bpy.types.ChildOfConstraint, rigid_body_object.constraints["mmd_tools_rigid_parent"])
            relation_constraint.mute = True
            if rigid_type == MODE_STATIC:
                rigid_body_object.parent_type = "OBJECT"
                rigid_body_object.parent = rigid_group_object
            elif rigid_type in (MODE_DYNAMIC, MODE_DYNAMIC_BONE):
                arm = relation_constraint.target
                bone_name = relation_constraint.subtarget
                if arm is not None and bone_name != "":
                    for c in arm.pose.bones[bone_name].constraints:
                        if c.type == "IK":
                            c.mute = False
            FnRigidBody.restore_transforms(rigid_body_object)

    @staticmethod
    def _clean_pose_bones(armature_object: Optional[bpy.types.Object]):
        if armature_object is None:
            return

        for pose_bone in armature_object.pose.bones:
            if "mmd_tools_rigid_track" not in pose_bone.constraints:
                continue
            pose_bone.constraints.remove(pose_bone.constraints["mmd_tools_rigid_track"])


class RigidBodyPhysicsBuilder:
    """
    A class that builds and cleans the rigidity physics for a given set of objects in Blender.
    """

    def __init__(
        self,
        context: bpy.types.Context,
        root_object: bpy.types.Object,
        armature_object: bpy.types.Object,
        rigid_group_object: bpy.types.Object,
        rigid_body_objects: List[bpy.types.Object],
        joint_objects: List[bpy.types.Object],
        temporary_group_object: bpy.types.Object,
    ):
        self.context = context
        self.root_object = root_object
        self.armature_object = armature_object
        self.rigid_body_objects = rigid_body_objects
        self.joint_objects = joint_objects
        self.rigid_group_object = rigid_group_object
        self.temporary_group_object = temporary_group_object
        self.__fake_parent_map = {}
        self.__rigid_body_matrix_map = {}
        self.__empty_parent_map: dict[bpy.types.Object, bpy.types.Object] = {}

    def build(self, non_collision_distance_scale=1.5, collision_margin=1e-06):
        rigidbody_world_enabled = FnRigidBody.get_and_set_rigid_body_world_enabled(False, context=self.context)
        if self.root_object.mmd_root.is_built:
            RigidBodyPhysicsCleaner.clean(
                self.context,
                self.root_object,
                self.armature_object,
                self.rigid_group_object,
                self.rigid_body_objects,
                self.joint_objects,
                self.temporary_objects,
            )
        self.root_object.mmd_root.is_built = True
        logging.info("****************************************")
        logging.info(" Build Rigidity Physics")
        logging.info("****************************************")
        start_time = time.time()
        self.__pre_build()
        self.__build_rigids(non_collision_distance_scale, collision_margin)
        self.__build_joints()
        self.__post_build()
        logging.info(" Finished building in %f seconds.", time.time() - start_time)
        FnRigidBody.get_and_set_rigid_body_world_enabled(rigidbody_world_enabled, context=self.context)

    def __get_rigid_range(self, obj):
        return (Vector(obj.bound_box[0]) - Vector(obj.bound_box[6])).length

    def __pre_build(self):
        no_parents = []
        for i in self.rigid_body_objects:
            FnRigidBody.backup_transforms(i)
            # mute relation
            relation = cast(bpy.types.ChildOfConstraint, i.constraints["mmd_tools_rigid_parent"])
            relation.mute = True
            # mute IK
            if int(i.mmd_rigid.type) in [MODE_DYNAMIC, MODE_DYNAMIC_BONE]:
                arm = relation.target
                bone_name = relation.subtarget
                if arm is not None and bone_name != "":
                    for c in arm.pose.bones[bone_name].constraints:
                        if c.type == "IK":
                            c.mute = True
                            c.influence = c.influence  # trigger update
                else:
                    no_parents.append(i)

        FnContext.viewlayer_update(self.context)

        parented = []
        for i in self.joint_objects:
            FnRigidBody.backup_transforms(i)
            rbc = i.rigid_body_constraint
            if rbc is None:
                continue
            obj1, obj2 = rbc.object1, rbc.object2
            if obj2 in no_parents:
                if obj1 not in no_parents and obj2 not in parented:
                    self.__fake_parent_map.setdefault(obj1, []).append(obj2)
                    parented.append(obj2)
            elif obj1 in no_parents:
                if obj1 not in parented:
                    self.__fake_parent_map.setdefault(obj2, []).append(obj1)
                    parented.append(obj1)

        # assert(len(no_parents) == len(parented))

    def __post_build(self):
        FnContext.viewlayer_update(self.context)

        # parenting empty to rigid object at once for speeding up
        for empty, rigid_obj in self.__empty_parent_map.items():
            matrix_world = empty.matrix_world
            empty.parent = rigid_obj
            empty.matrix_world = matrix_world

        arm = self.armature_object
        if arm:
            for p_bone in arm.pose.bones:
                c = p_bone.constraints.get("mmd_tools_rigid_track", None)
                if c:
                    c.mute = False

    def __create_non_collision_constraint(self, non_collision_joint_table):
        total_len = len(non_collision_joint_table)
        if total_len < 1:
            return

        start_time = time.time()
        logging.debug("-" * 60)
        logging.debug(" creating ncc, counts: %d", total_len)

        context = self.context
        ncc_obj = FnContext.new_and_link_object(context, name="ncc", object_data=None)
        ncc_obj.location = [0, 0, 0]
        setattr(ncc_obj, Props.empty_display_type, "ARROWS")
        setattr(ncc_obj, Props.empty_display_size, 0.5 * getattr(self.root_object, Props.empty_display_size))
        ncc_obj.mmd_type = "NON_COLLISION_CONSTRAINT"
        ncc_obj.hide_render = True
        ncc_obj.parent = self.temporary_group_object

        FnContext.set_active_object(context, ncc_obj)
        bpy.ops.rigidbody.constraint_add(type="GENERIC")

        rb = ncc_obj.rigid_body_constraint
        rb.disable_collisions = True

        ncc_objs = FnContext.duplicate_object(context, ncc_obj, total_len)
        logging.debug(" created %d ncc.", len(ncc_objs))

        for ncc_obj, pair in zip(ncc_objs, non_collision_joint_table):
            rbc = ncc_obj.rigid_body_constraint
            rbc.object1, rbc.object2 = pair
            ncc_obj.hide_set(True)
            ncc_obj.hide_select = True
        logging.debug(" finish in %f seconds.", time.time() - start_time)
        logging.debug("-" * 60)

    def __build_rigids(self, non_collision_distance_scale, collision_margin):
        logging.debug("--------------------------------")
        logging.debug(" Build riggings of rigid bodies")
        logging.debug("--------------------------------")
        rigid_objects = list(self.rigid_body_objects)
        rigid_object_groups = [[] for i in range(16)]
        for i in rigid_objects:
            rigid_object_groups[i.mmd_rigid.collision_group_number].append(i)

        joint_map: dict[frozenset[bpy.types.Object], bpy.types.Object] = {}
        for joint in self.joint_objects:
            rbc = joint.rigid_body_constraint
            if rbc is None:
                continue
            rbc.disable_collisions = False
            joint_map[frozenset((rbc.object1, rbc.object2))] = joint

        logging.info("Creating non collision constraints")
        # create non collision constraints
        non_collision_joint_table = []
        non_collision_pairs = set()
        rigid_object_cnt = len(rigid_objects)
        for obj_a in rigid_objects:
            for n, ignore in enumerate(obj_a.mmd_rigid.collision_group_mask):
                if not ignore:
                    continue
                for obj_b in rigid_object_groups[n]:
                    if obj_a == obj_b:
                        continue
                    pair = frozenset((obj_a, obj_b))
                    if pair in non_collision_pairs:
                        continue
                    if pair in joint_map:
                        joint = joint_map[pair]
                        joint.rigid_body_constraint.disable_collisions = True
                    else:
                        distance = (obj_a.location - obj_b.location).length
                        if distance < non_collision_distance_scale * (self.__get_rigid_range(obj_a) + self.__get_rigid_range(obj_b)) * 0.5:
                            non_collision_joint_table.append((obj_a, obj_b))
                    non_collision_pairs.add(pair)
        for cnt, i in enumerate(rigid_objects):
            logging.info("%3d/%3d: Updating rigid body %s", cnt + 1, rigid_object_cnt, i.name)
            self.__update_rigid(i, collision_margin)
        self.__create_non_collision_constraint(non_collision_joint_table)
        return rigid_objects

    def __build_joints(self):
        for i in self.joint_objects:
            rbc = i.rigid_body_constraint
            if rbc is None:
                continue
            m = self.__rigid_body_matrix_map.get(rbc.object1, None) or self.__rigid_body_matrix_map.get(rbc.object2, None)
            if m is None:
                continue
            t, r, _s = (m @ i.matrix_local).decompose()
            i.location = t
            i.rotation_euler = r.to_euler(i.rotation_mode)

    def __update_rigid(self, rigid_body_object: bpy.types.Object, collision_margin: float):
        assert rigid_body_object.mmd_type == "RIGID_BODY"
        rigid_body = rigid_body_object.rigid_body
        if rigid_body is None:
            return

        mmd_rigid = rigid_body_object.mmd_rigid
        mmd_rigid_type = int(mmd_rigid.type)
        relation_constraint = cast(bpy.types.ChildOfConstraint, rigid_body_object.constraints["mmd_tools_rigid_parent"])

        if relation_constraint.target is None:
            relation_constraint.target = self.armature_object

        arm = relation_constraint.target
        if relation_constraint.subtarget not in arm.pose.bones:
            bone_name = ""
        else:
            bone_name = relation_constraint.subtarget

        if mmd_rigid_type == MODE_STATIC:
            rigid_body.kinematic = True
        else:
            rigid_body.kinematic = False

        if collision_margin == 0.0:
            rigid_body.use_margin = False
        else:
            rigid_body.use_margin = True
            rigid_body.collision_margin = collision_margin

        if arm is not None and bone_name != "":
            target_bone = arm.pose.bones[bone_name]

            if mmd_rigid_type == MODE_STATIC:
                m = target_bone.matrix @ target_bone.bone.matrix_local.inverted()
                self.__rigid_body_matrix_map[rigid_body_object] = m
                orig_scale = rigid_body_object.scale.copy()
                to_matrix_world = rigid_body_object.matrix_world @ rigid_body_object.matrix_local.inverted()
                matrix_world = to_matrix_world @ (m @ rigid_body_object.matrix_local)
                rigid_body_object.parent = arm
                rigid_body_object.parent_type = "BONE"
                rigid_body_object.parent_bone = bone_name
                rigid_body_object.matrix_world = matrix_world
                rigid_body_object.scale = orig_scale
                fake_children = self.__fake_parent_map.get(rigid_body_object, None)
                if fake_children:
                    for fake_child in fake_children:
                        logging.debug("          - fake_child: %s", fake_child.name)
                        t, r, s = (m @ fake_child.matrix_local).decompose()
                        fake_child.location = t
                        fake_child.rotation_euler = r.to_euler(fake_child.rotation_mode)

            elif mmd_rigid_type in (MODE_DYNAMIC, MODE_DYNAMIC_BONE):
                m = target_bone.matrix @ target_bone.bone.matrix_local.inverted()
                self.__rigid_body_matrix_map[rigid_body_object] = m
                t, r, s = (m @ rigid_body_object.matrix_local).decompose()
                rigid_body_object.location = t
                rigid_body_object.rotation_euler = r.to_euler(rigid_body_object.rotation_mode)
                fake_children = self.__fake_parent_map.get(rigid_body_object, None)
                if fake_children:
                    for fake_child in fake_children:
                        logging.debug("          - fake_child: %s", fake_child.name)
                        t, r, s = (m @ fake_child.matrix_local).decompose()
                        fake_child.location = t
                        fake_child.rotation_euler = r.to_euler(fake_child.rotation_mode)

                if "mmd_tools_rigid_track" not in target_bone.constraints:
                    empty = FnContext.new_and_link_object(self.context, name="mmd_bonetrack", object_data=None)
                    empty.matrix_world = target_bone.matrix
                    setattr(empty, Props.empty_display_type, "ARROWS")
                    setattr(empty, Props.empty_display_size, 0.1 * getattr(self.root_object, Props.empty_display_size))
                    empty.mmd_type = "TRACK_TARGET"
                    empty.hide_set(True)
                    empty.parent = self.temporary_group_object

                    rigid_body_object.mmd_rigid.bone = bone_name
                    rigid_body_object.constraints.remove(relation_constraint)

                    self.__empty_parent_map[empty] = rigid_body_object

                    constraint_type = ("COPY_TRANSFORMS", "COPY_ROTATION")[mmd_rigid_type - 1]
                    constraint: bpy.types.CopyTransformsConstraint | bpy.types.CopyRotationConstraint = target_bone.constraints.new(constraint_type)
                    constraint.mute = True
                    constraint.name = "mmd_tools_rigid_track"
                    constraint.target = empty
                else:
                    empty = target_bone.constraints["mmd_tools_rigid_track"].target
                    original_rigid_body_object = self.__empty_parent_map[empty]
                    original_rigid_body = original_rigid_body_object.rigid_body
                    if original_rigid_body and rigid_body.mass > original_rigid_body.mass:
                        logging.debug("        * Bone (%s): change target from [%s] to [%s]", target_bone.name, original_rigid_body_object.name, rigid_body_object.name)
                        # re-parenting
                        rigid_body_object.mmd_rigid.bone = bone_name
                        rigid_body_object.constraints.remove(relation_constraint)
                        self.__empty_parent_map[empty] = rigid_body_object
                        # revert change
                        original_rigid_body_object.mmd_rigid.bone = bone_name
                    else:
                        logging.debug("        * Bone (%s): track target [%s]", target_bone.name, original_rigid_body_object.name)

        rigid_body.collision_shape = mmd_rigid.shape
