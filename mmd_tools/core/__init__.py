# -*- coding: utf-8 -*-
# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.


import itertools
from typing import Callable, Dict, Iterator, Optional, TypeGuard, cast

import bpy

from ..bpyutils import FnContext


class FnCore:
    """
    A collection of utility functions for working with MMD models in Blender.

    This class provides various utility functions to work with MMD models in Blender.
    It has knowledge of the MMD model structure and provides functions to work with the model's hierarchy.
    The functions in this class are read-only and do not modify the model in any way.


    Object Hierarchy:
    -----------------
    The MMD model hierarchy consists of the following objects:

    - Root Object: The root object of the model.
        - Armature Object: The armature object of the model.
            - Mesh Objects: The mesh objects of the model.
        - Rigid Group Object: The rigid group object of the model.
            - Rigid Body Objects: The rigid body objects of the model.
        - Joint Group Object: The joint group object of the model.
            - Joint Objects: The joint objects of the model.
        - Temporary Group Object: The temporary group object of the model.
            - Temporary Objects: The temporary objects of the model.
        - Placeholder Object: The placeholder object of the model.

    Object Types:
    -------------
    The table of object types and their corresponding type and mmd_type values is as follows:

    +------------------------+----------+---------------------+
    | Object Type            | type     | mmd_type            |
    +------------------------+----------+---------------------+
    | Root Object            | EMPTY    | ROOT                |
    | Armature Object        | ARMATURE | NONE                |
    | Mesh Objects           | MESH     | NONE                |
    | Rigid Group Object     | EMPTY    | RIGID_GRP_OBJ       |
    | Rigid Body Objects     | EMPTY    | RIGID_BODY          |
    | Joint Group Object     | EMPTY    | JOINT_GRP_OBJ       |
    | Joint Objects          | EMPTY    | JOINT               |
    | Temporary Group Object | EMPTY    | TEMPORARY_GRP_OBJ   |
    | Temporary Objects      | EMPTY    | TRACK_TARGET, ...   |
    | Placeholder Object     | MESH     | PLACEHOLDER         |
    +------------------------+----------+---------------------+
    """

    @staticmethod
    def find_root_object(target_object: Optional[bpy.types.Object]) -> Optional[bpy.types.Object]:
        """
        Find the root object of the model.

        Args:
            target_object (bpy.types.Object): The object to start searching from.

        Returns:
            Optional[bpy.types.Object]: The root object of the model. If the object is not a part of a model, None is returned.
            Generally, the root object is an object with type == "EMPTY" and mmd_type == "ROOT".
        """
        while target_object is not None and target_object.mmd_type != "ROOT":
            target_object = target_object.parent
        return target_object

    @staticmethod
    def find_armature_object(root_object: bpy.types.Object) -> Optional[bpy.types.Object]:
        """
        Find the armature object of the model.

        Args:
            root_object (bpy.types.Object): The root object of the model.

        Returns:
            Optional[bpy.types.Object]: The armature object of the model. If the model does not have an armature, None is returned.
        """
        for o in root_object.children:
            if o.type == "ARMATURE":
                return o
        return None

    @staticmethod
    def find_rigid_group_object(root_object: bpy.types.Object) -> Optional[bpy.types.Object]:
        """
        Find the rigid group object of the model.

        This function searches for the rigid group object within the model's hierarchy.

        Args:
            root_object (bpy.types.Object): The root object of the model.

        Returns:
            Optional[bpy.types.Object]: The rigid group object of the model. If the model does not have a rigid group object, None is returned.
        """
        for o in root_object.children:
            if o.type == "EMPTY" and o.mmd_type == "RIGID_GRP_OBJ":
                return o
        return None

    @staticmethod
    def ensure_rigid_group_object(context: bpy.types.Context, root_object: bpy.types.Object) -> bpy.types.Object:
        """
        Ensures that the model has a rigid group object.

        Args:
            context (bpy.types.Context): The Blender context.
            root_object (bpy.types.Object): The root object to search for a rigid group object.

        Returns:
            bpy.types.Object: The existing or newly created rigid group object.
        """
        rigid_group_object = FnCore.find_rigid_group_object(root_object)
        if rigid_group_object is not None:
            return rigid_group_object
        return FnCore.__new_group_object(context, name="rigidbodies", mmd_type="RIGID_GRP_OBJ", parent=root_object)

    @staticmethod
    def find_joint_group_object(root_object: bpy.types.Object) -> Optional[bpy.types.Object]:
        """
        Find the joint group object of the model.

        Args:
            root_object (bpy.types.Object): The root object to search for a joint group object.

        Returns:
            Optional[bpy.types.Object]: The joint group object if found, otherwise None.

        """
        for o in root_object.children:
            if o.type == "EMPTY" and o.mmd_type == "JOINT_GRP_OBJ":
                return o
        return None

    @staticmethod
    def ensure_joint_group_object(context: bpy.types.Context, root_object: bpy.types.Object) -> bpy.types.Object:
        """
        Ensures that the model has a joint group object.

        Args:
            context (bpy.types.Context): The Blender context.
            root_object (bpy.types.Object): The root object to search for a joint group object.

        Returns:
            bpy.types.Object: The existing or newly created joint group object.
        """
        joint_group_object = FnCore.find_joint_group_object(root_object)
        if joint_group_object is not None:
            return joint_group_object
        return FnCore.__new_group_object(context, name="joints", mmd_type="JOINT_GRP_OBJ", parent=root_object)

    @staticmethod
    def find_temporary_group_object(root_object: bpy.types.Object) -> Optional[bpy.types.Object]:
        """
        Find the temporary group object of the model.

        Args:
            root_object (bpy.types.Object): The root object to search for a temporary group object.

        Returns:
            Optional[bpy.types.Object]: The temporary group object if found, otherwise None.
        """
        for o in root_object.children:
            if o.type == "EMPTY" and o.mmd_type == "TEMPORARY_GRP_OBJ":
                return o
        return None

    @staticmethod
    def ensure_temporary_group_object(context: bpy.types.Context, root_object: bpy.types.Object) -> bpy.types.Object:
        """
        Ensures that the model has a temporary group object.

        Args:
            context (bpy.types.Context): The Blender context.
            root_object (bpy.types.Object): The root object to search for a temporary group object.

        Returns:
            bpy.types.Object: The existing or newly created temporary group object.
        """
        temporary_group_object = FnCore.find_temporary_group_object(root_object)
        if temporary_group_object is not None:
            return temporary_group_object
        return FnCore.__new_group_object(context, name="temporary", mmd_type="TEMPORARY_GRP_OBJ", parent=root_object)

    @staticmethod
    def find_bone_order_mesh_object(root_object: bpy.types.Object) -> Optional[bpy.types.Object]:
        """
        Find the mesh object that stores the bone order override data.

        Args:
            root_object (bpy.types.Object): The root object to search for the mesh object.

        Returns:
            Optional[bpy.types.Object]: The mesh object if found, otherwise None.
        """
        armature_object = FnCore.find_armature_object(root_object)
        if armature_object is None:
            return None

        # TODO: consistency issue
        return next(filter(lambda o: o.type == "MESH" and "mmd_bone_order_override" in o.modifiers, armature_object.children), None)

    @staticmethod
    def find_mesh_object_by_name(root_object: bpy.types.Object, name: str) -> Optional[bpy.types.Object]:
        """
        Find a mesh object by name.

        Args:
            root_object (bpy.types.Object): The root object to search for the mesh object.
            name (str): The name of the mesh object to find.

        Returns:
            Optional[bpy.types.Object]: The mesh object if found, otherwise None.
        """
        for o in FnCore.iterate_mesh_objects(root_object):
            # TODO: consider o.data.name
            if o.name != name:
                continue
            return o
        return None

    @staticmethod
    def find_mesh_object_by_index(root_object: bpy.types.Object, index: int) -> Optional[bpy.types.Object]:
        """
        Find a mesh object by index.

        Args:
            root_object (bpy.types.Object): The root object to search for the mesh object.
            index (int): The index of the mesh object to find.

        Returns:
            Optional[bpy.types.Object]: The mesh object if found, otherwise None.
        """
        for i, o in enumerate(FnCore.iterate_mesh_objects(root_object)):
            if i == index:
                return o
        return None

    @staticmethod
    def find_mesh_object_index_by_name(root_object: bpy.types.Object, name: str) -> int:
        """
        Get the index of a mesh object by name.

        Args:
            root_object (bpy.types.Object): The root object to search for the mesh object.
            name (str): The name of the mesh object to find.

        Returns:
            int: The index of the mesh object if found, otherwise -1.
        """
        for i, o in enumerate(FnCore.iterate_mesh_objects(root_object)):
            # TODO: consider o.data.name
            if o.name == name:
                return i
        return -1

    @staticmethod
    def iterate_child_objects(target_object: bpy.types.Object) -> Iterator[bpy.types.Object]:
        """
        Iterate over the child objects of the given object.

        Args:
            target_object (bpy.types.Object): The object to iterate over.

        Yields:
            Iterator[bpy.types.Object]: The child objects of the given object.
        """
        for child in target_object.children:
            yield child
            yield from FnCore.iterate_child_objects(child)

    @staticmethod
    def iterate_filtered_child_objects(condition_function: Callable[[bpy.types.Object], bool], target_object: Optional[bpy.types.Object]) -> Iterator[bpy.types.Object]:
        """
        Iterate over the child objects of the given object that satisfy the given condition.

        Args:
            condition_function (Callable[[bpy.types.Object], bool]): The condition function to filter the child objects.
            target_object (Optional[bpy.types.Object]): The object to iterate over.

        Yields:
            Iterator[bpy.types.Object]: The child objects of the given object that satisfy the given condition.
        """
        if target_object is None:
            return iter(())
        return FnCore.__iterate_filtered_child_objects_internal(condition_function, target_object)

    @staticmethod
    def iterate_mesh_objects(root_object: bpy.types.Object) -> Iterator[bpy.types.Object]:
        """
        Iterate over the mesh objects of the model.

        Args:
            root_object (bpy.types.Object): The root object of the model.

        Yields:
            Iterator[bpy.types.Object]: The mesh objects of the model.
        """
        return FnCore.iterate_filtered_child_objects(FnCore.is_mesh_object, FnCore.find_armature_object(root_object))

    @staticmethod
    def iterate_rigid_body_objects(root_object: bpy.types.Object) -> Iterator[bpy.types.Object]:
        """
        Iterate over the rigid body objects of the model.

        Args:
            root_object (bpy.types.Object): The root object of the model.

        Yields:
            Iterator[bpy.types.Object]: The rigid body objects of the model.
        """
        if root_object.mmd_root.is_built:
            return itertools.chain(
                FnCore.iterate_filtered_child_objects(FnCore.is_rigid_body_object, FnCore.find_armature_object(root_object)),
                FnCore.iterate_filtered_child_objects(FnCore.is_rigid_body_object, FnCore.find_rigid_group_object(root_object)),
            )
        return FnCore.iterate_filtered_child_objects(FnCore.is_rigid_body_object, FnCore.find_rigid_group_object(root_object))

    @staticmethod
    def iterate_joint_objects(root_object: bpy.types.Object) -> Iterator[bpy.types.Object]:
        """
        Iterate over the joint objects of the model.

        Args:
            root_object (bpy.types.Object): The root object of the model.

        Yields:
            Iterator[bpy.types.Object]: The joint objects of the model.
        """
        return FnCore.iterate_filtered_child_objects(FnCore.is_joint_object, FnCore.find_joint_group_object(root_object))

    @staticmethod
    def iterate_temporary_objects(root_object: bpy.types.Object, rigid_track_only: bool = False) -> Iterator[bpy.types.Object]:
        """
        Iterate over the temporary objects of the model.

        Args:
            root_object (bpy.types.Object): The root object of the model.
            rigid_track_only (bool): Whether to return only the temporary objects that are related to rigid bodies.

        Yields:
            Iterator[bpy.types.Object]: The temporary objects of the model.
        """
        rigid_body_objects = FnCore.iterate_filtered_child_objects(FnCore.is_temporary_object, FnCore.find_rigid_group_object(root_object))

        if rigid_track_only:
            return rigid_body_objects

        temporary_group_object = FnCore.find_temporary_group_object(root_object)
        if temporary_group_object is None:
            return rigid_body_objects
        return itertools.chain(rigid_body_objects, FnCore.__iterate_filtered_child_objects_internal(FnCore.is_temporary_object, temporary_group_object))

    @staticmethod
    def iterate_materials(root_object: bpy.types.Object) -> Iterator[bpy.types.Material]:
        """
        Iterate over the materials of the model.
        If a material is shared across multiple mesh objects, it will be yielded multiple times.
        If you need to iterate over unique materials, use the `iterate_unique_materials` function instead.

        Args:
            root_object (bpy.types.Object): The root object of the model.

        Yields:
            Iterator[bpy.types.Material]: The materials of the model, including duplicates.
        """
        return (material for mesh_object in FnCore.iterate_mesh_objects(root_object) for material in cast(bpy.types.Mesh, mesh_object.data).materials if material is not None)

    @staticmethod
    def iterate_unique_materials(root_object: bpy.types.Object) -> Iterator[bpy.types.Material]:
        """
        Iterate over the unique materials of the model.

        Args:
            root_object (bpy.types.Object): The root object of the model.

        Yields:
            Iterator[bpy.types.Material]: The unique materials of the model.
        """
        materials: Dict[bpy.types.Material, None] = {}  # use dict because set does not guarantee the order
        materials.update((material, None) for material in FnCore.iterate_materials(root_object))
        return iter(materials.keys())

    @staticmethod
    def is_root_object(target_object: Optional[bpy.types.Object]) -> TypeGuard[bpy.types.Object]:
        """
        Check if the object is a root object.

        Args:
            target_object (Optional[bpy.types.Object]): The object to check.

        Returns:
            TypeGuard[bpy.types.Object]: True if the object is a root object, otherwise False.
        """
        return target_object is not None and target_object.mmd_type == "ROOT"

    @staticmethod
    def is_rigid_body_object(target_object: Optional[bpy.types.Object]) -> TypeGuard[bpy.types.Object]:
        """
        Check if the object is a rigid body object.

        Args:
            target_object (Optional[bpy.types.Object]): The object to check.

        Returns:
            TypeGuard[bpy.types.Object]: True if the object is a rigid body object, otherwise False.
        """
        return target_object is not None and target_object.mmd_type == "RIGID_BODY"

    @staticmethod
    def is_joint_object(target_object: Optional[bpy.types.Object]) -> TypeGuard[bpy.types.Object]:
        """
        Check if the object is a joint object.

        Args:
            target_object (Optional[bpy.types.Object]): The object to check.

        Returns:
            TypeGuard[bpy.types.Object]: True if the object is a joint object, otherwise False.
        """
        return target_object is not None and target_object.mmd_type == "JOINT"

    @staticmethod
    def is_temporary_object(target_object: Optional[bpy.types.Object]) -> TypeGuard[bpy.types.Object]:
        """
        Check if the object is a temporary object.

        Args:
            target_object (Optional[bpy.types.Object]): The object to check.

        Returns:
            TypeGuard[bpy.types.Object]: True if the object is a temporary object, otherwise False.
        """
        return target_object is not None and target_object.mmd_type in ("TRACK_TARGET", "NON_COLLISION_CONSTRAINT", "SPRING_CONSTRAINT", "SPRING_GOAL")

    @staticmethod
    def is_mesh_object(target_object: Optional[bpy.types.Object]) -> TypeGuard[bpy.types.Object]:
        """
        Check if the object is a mesh object.

        Args:
            target_object (Optional[bpy.types.Object]): The object to check.

        Returns:
            TypeGuard[bpy.types.Object]: True if the object is a mesh object, otherwise False.
        """
        return target_object is not None and target_object.type == "MESH" and target_object.mmd_type == "NONE"

    @staticmethod
    def __new_group_object(context: bpy.types.Context, name: str, mmd_type: str, parent: bpy.types.Object) -> bpy.types.Object:
        group_object = FnContext.new_and_link_object(context, name=name, object_data=None)
        group_object.mmd_type = mmd_type
        group_object.parent = parent
        group_object.hide_set(True)
        group_object.hide_select = True
        group_object.lock_rotation = group_object.lock_location = group_object.lock_scale = [True, True, True]
        return group_object

    @staticmethod
    def __iterate_filtered_child_objects_internal(condition_function: Callable[[bpy.types.Object], bool], target_object: bpy.types.Object) -> Iterator[bpy.types.Object]:
        for child in target_object.children:
            if condition_function(child):
                yield child
            yield from FnCore.__iterate_filtered_child_objects_internal(condition_function, child)
