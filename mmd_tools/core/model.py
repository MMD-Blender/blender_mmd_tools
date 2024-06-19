# -*- coding: utf-8 -*-
# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

import itertools
import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Iterator, Optional, Set, TypeGuard, Union, cast

import bpy
import idprop

from .. import MMD_TOOLS_VERSION, bpyutils
from ..bpyutils import FnContext, Props
from . import FnCore
from .bone import FnBone
from .morph import FnMorph
from .rigid_body import RigidBodyPhysicsBuilder, RigidBodyPhysicsCleaner

if TYPE_CHECKING:
    from ..properties.morph import MaterialMorphData
    from ..properties.root import MMDRoot


class FnModel(FnCore):
    @staticmethod
    def copy_mmd_root(destination_root_object: bpy.types.Object, source_root_object: bpy.types.Object, overwrite: bool = True, replace_name2values: Dict[str, Dict[Any, Any]] = None):
        FnModel.__copy_property(destination_root_object.mmd_root, source_root_object.mmd_root, overwrite=overwrite, replace_name2values=replace_name2values or {})

    @staticmethod
    def join_models(parent_root_object: bpy.types.Object, child_root_objects: Iterable[bpy.types.Object], context: bpy.types.Context):
        parent_armature_object = FnCore.find_armature_object(parent_root_object)
        with context.temp_override(
            active_object=parent_armature_object,
            selected_editable_objects=[parent_armature_object],
        ):
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        def _change_bone_id(bone: bpy.types.PoseBone, new_bone_id: int, bone_morphs, pose_bones):
            """This function will also update the references of bone morphs and rotate+/move+."""
            bone_id = bone.mmd_bone.bone_id

            # Change Bone ID
            bone.mmd_bone.bone_id = new_bone_id

            # Update Relative Bone Morph # Update the reference of bone morph # 更新骨骼表情
            for bone_morph in bone_morphs:
                for data in bone_morph.data:
                    if data.bone_id != bone_id:
                        continue
                    data.bone_id = new_bone_id

            # Update Relative Additional Transform # Update the reference of rotate+/move+ # 更新付与親
            for pose_bone in pose_bones:
                if pose_bone.is_mmd_shadow_bone:
                    continue
                mmd_bone = pose_bone.mmd_bone
                if mmd_bone.additional_transform_bone_id != bone_id:
                    continue
                mmd_bone.additional_transform_bone_id = new_bone_id

        max_bone_id = max(
            (
                b.mmd_bone.bone_id
                for o in itertools.chain(
                    child_root_objects,
                    [parent_root_object],
                )
                for b in FnCore.find_armature_object(o).pose.bones
                if not b.is_mmd_shadow_bone
            ),
            default=-1,
        )

        child_root_object: bpy.types.Object
        for child_root_object in child_root_objects:
            child_armature_object = FnCore.find_armature_object(child_root_object)
            child_pose_bones = child_armature_object.pose.bones
            child_bone_morphs = child_root_object.mmd_root.bone_morphs

            for pose_bone in child_pose_bones:
                if pose_bone.is_mmd_shadow_bone:
                    continue
                if pose_bone.mmd_bone.bone_id != -1:
                    max_bone_id += 1
                    _change_bone_id(pose_bone, max_bone_id, child_bone_morphs, child_pose_bones)

            child_armature_matrix = child_armature_object.matrix_parent_inverse.copy()

            with context.temp_override(
                active_object=child_armature_object,
                selected_editable_objects=[child_armature_object],
            ):
                bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

            # Disconnect mesh dependencies because transform_apply fails when mesh data are multiple used.
            related_meshes: Dict[MaterialMorphData, bpy.types.Mesh] = {}
            for material_morph in child_root_object.mmd_root.material_morphs:
                for material_morph_data in material_morph.data:
                    if material_morph_data.related_mesh_data is not None:
                        related_meshes[material_morph_data] = material_morph_data.related_mesh_data
                        material_morph_data.related_mesh_data = None
            try:
                # replace mesh armature modifier.object
                mesh: bpy.types.Object
                for mesh in FnModel.__iterate_child_mesh_objects(child_armature_object):
                    with context.temp_override(
                        active_object=mesh,
                        selected_editable_objects=[mesh],
                    ):
                        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            finally:
                # Restore mesh dependencies
                for material_morph in child_root_object.mmd_root.material_morphs:
                    for material_morph_data in material_morph.data:
                        material_morph_data.related_mesh_data = related_meshes.get(material_morph_data, None)

            # join armatures
            with context.temp_override(
                active_object=parent_armature_object,
                selected_editable_objects=[parent_armature_object, child_armature_object],
            ):
                bpy.ops.object.join()

            for mesh in FnModel.__iterate_child_mesh_objects(parent_armature_object):
                armature_modifier: bpy.types.ArmatureModifier = mesh.modifiers["mmd_bone_order_override"] if "mmd_bone_order_override" in mesh.modifiers else mesh.modifiers.new("mmd_bone_order_override", "ARMATURE")
                if armature_modifier.object is None:
                    armature_modifier.object = parent_armature_object
                    mesh.matrix_parent_inverse = child_armature_matrix

            child_rigid_group_object = FnCore.find_rigid_group_object(child_root_object)
            if child_rigid_group_object is not None:
                parent_rigid_group_object = FnCore.find_rigid_group_object(parent_root_object)

                with context.temp_override(
                    object=parent_rigid_group_object,
                    selected_editable_objects=[parent_rigid_group_object, *FnCore.iterate_rigid_body_objects(child_root_object)],
                ):
                    bpy.ops.object.parent_set(type="OBJECT", keep_transform=True)
                bpy.data.objects.remove(child_rigid_group_object)

            child_joint_group_object = FnCore.find_joint_group_object(child_root_object)
            if child_joint_group_object is not None:
                parent_joint_group_object = FnCore.find_joint_group_object(parent_root_object)
                with context.temp_override(
                    object=parent_joint_group_object,
                    selected_editable_objects=[parent_joint_group_object, *FnCore.iterate_joint_objects(child_root_object)],
                ):
                    bpy.ops.object.parent_set(type="OBJECT", keep_transform=True)
                bpy.data.objects.remove(child_joint_group_object)

            child_temporary_group_object = FnCore.find_temporary_group_object(child_root_object)
            if child_temporary_group_object is not None:
                parent_temporary_group_object = FnCore.find_temporary_group_object(parent_root_object)
                with context.temp_override(
                    object=parent_temporary_group_object,
                    selected_editable_objects=[parent_temporary_group_object, *FnCore.iterate_temporary_objects(child_root_object)],
                ):
                    bpy.ops.object.parent_set(type="OBJECT", keep_transform=True)

                for obj in list(FnCore.iterate_child_objects(child_temporary_group_object)):
                    bpy.data.objects.remove(obj)
                bpy.data.objects.remove(child_temporary_group_object)

            FnModel.copy_mmd_root(parent_root_object, child_root_object, overwrite=False)

            # Remove unused objects from child models
            if len(child_root_object.children) == 0:
                bpy.data.objects.remove(child_root_object)

    @staticmethod
    def _add_armature_modifier(mesh_object: bpy.types.Object, armature_object: bpy.types.Object) -> bpy.types.ArmatureModifier:
        for m in mesh_object.modifiers:
            if m.type != "ARMATURE":
                continue
            # already has armature modifier.
            return cast(bpy.types.ArmatureModifier, m)

        modifier = cast(bpy.types.ArmatureModifier, mesh_object.modifiers.new(name="Armature", type="ARMATURE"))
        modifier.object = armature_object
        modifier.use_vertex_groups = True
        modifier.name = "mmd_bone_order_override"

        return modifier

    @staticmethod
    def attach_mesh_objects(parent_root_object: bpy.types.Object, mesh_objects: Iterable[bpy.types.Object], add_armature_modifier: bool):
        armature_object = FnCore.find_armature_object(parent_root_object)
        if armature_object is None:
            raise ValueError(f"Armature object not found in {parent_root_object}")

        def __get_root_object(obj: bpy.types.Object) -> bpy.types.Object:
            if obj.parent is None:
                return obj
            return __get_root_object(obj.parent)

        for mesh_object in mesh_objects:
            if not FnCore.is_mesh_object(mesh_object):
                continue

            if FnCore.find_root_object(mesh_object) is not None:
                continue

            mesh_root_object = __get_root_object(mesh_object)
            original_matrix_world = mesh_root_object.matrix_world
            mesh_root_object.parent_type = "OBJECT"
            mesh_root_object.parent = armature_object
            mesh_root_object.matrix_world = original_matrix_world

            if add_armature_modifier:
                FnModel._add_armature_modifier(mesh_object, armature_object)

    @staticmethod
    def add_missing_vertex_groups_from_bones(root_object: bpy.types.Object, mesh_object: bpy.types.Object, search_in_all_meshes: bool):
        armature_object = FnCore.find_armature_object(root_object)
        if armature_object is None:
            raise ValueError(f"Armature object not found in {root_object}")

        vertex_group_names: Set[str] = set()

        search_meshes = FnCore.iterate_mesh_objects(root_object) if search_in_all_meshes else [mesh_object]

        for search_mesh in search_meshes:
            vertex_group_names.update(search_mesh.vertex_groups.keys())

        pose_bone: bpy.types.PoseBone
        for pose_bone in armature_object.pose.bones:
            pose_bone_name = pose_bone.name

            if pose_bone_name in vertex_group_names:
                continue

            if pose_bone_name.startswith("_"):
                continue

            mesh_object.vertex_groups.new(name=pose_bone_name)

    @staticmethod
    def change_mmd_ik_loop_factor(root_object: bpy.types.Object, new_ik_loop_factor: int):
        mmd_root = root_object.mmd_root
        old_ik_loop_factor = mmd_root.ik_loop_factor

        if new_ik_loop_factor == old_ik_loop_factor:
            return

        armature_object = FnCore.find_armature_object(root_object)
        for pose_bone in armature_object.pose.bones:
            for constraint in (cast(bpy.types.KinematicConstraint, c) for c in pose_bone.constraints if c.type == "IK"):
                iterations = int(constraint.iterations * new_ik_loop_factor / old_ik_loop_factor)
                logging.info("Update %s of %s: %d -> %d", constraint.name, pose_bone.name, constraint.iterations, iterations)
                constraint.iterations = iterations

        mmd_root.ik_loop_factor = new_ik_loop_factor

        return

    @staticmethod
    def __copy_property_group(destination: bpy.types.PropertyGroup, source: bpy.types.PropertyGroup, overwrite: bool, replace_name2values: Dict[str, Dict[Any, Any]]):
        destination_rna_properties = destination.bl_rna.properties
        for name in source.keys():
            is_attr = hasattr(source, name)
            value = getattr(source, name) if is_attr else source[name]
            if isinstance(value, bpy.types.PropertyGroup):
                FnModel.__copy_property_group(getattr(destination, name) if is_attr else destination[name], value, overwrite=overwrite, replace_name2values=replace_name2values)
            elif isinstance(value, bpy.types.bpy_prop_collection):
                FnModel.__copy_collection_property(getattr(destination, name) if is_attr else destination[name], value, overwrite=overwrite, replace_name2values=replace_name2values)
            elif isinstance(value, idprop.types.IDPropertyArray):
                pass
                # _copy_collection_property(getattr(destination, name) if is_attr else destination[name], value, overwrite=overwrite, replace_name2values=replace_name2values)
            else:
                value2values = replace_name2values.get(name)
                if value2values is not None:
                    replace_value = value2values.get(value)
                    if replace_value is not None:
                        value = replace_value

                if overwrite or destination_rna_properties[name].default == getattr(destination, name) if is_attr else destination[name]:
                    if is_attr:
                        setattr(destination, name, value)
                    else:
                        destination[name] = value

    @staticmethod
    def __copy_collection_property(destination: bpy.types.bpy_prop_collection, source: bpy.types.bpy_prop_collection, overwrite: bool, replace_name2values: Dict[str, Dict[Any, Any]]):
        if overwrite:
            destination.clear()

        len_source = len(source)
        if len_source == 0:
            return

        source_names: Set[str] = set(source.keys())
        if len(source_names) == len_source and source[0].name != "":
            # names work
            destination_names: Set[str] = set(destination.keys())

            missing_names = source_names - destination_names

            destination_index = 0
            for name, value in source.items():
                if name in missing_names:
                    new_element = destination.add()
                    new_element["name"] = name

                FnModel.__copy_property(destination[name], value, overwrite=overwrite, replace_name2values=replace_name2values)
                destination.move(destination.find(name), destination_index)
                destination_index += 1
        else:
            # names not work
            while len_source > len(destination):
                destination.add()

            for index, name in enumerate(source.keys()):
                FnModel.__copy_property(destination[index], source[index], overwrite=True, replace_name2values=replace_name2values)

    @staticmethod
    def __copy_property(destination: Union[bpy.types.PropertyGroup, bpy.types.bpy_prop_collection], source: Union[bpy.types.PropertyGroup, bpy.types.bpy_prop_collection], overwrite: bool, replace_name2values: Dict[str, Dict[Any, Any]]):
        if isinstance(destination, bpy.types.PropertyGroup):
            FnModel.__copy_property_group(destination, source, overwrite=overwrite, replace_name2values=replace_name2values)
        elif isinstance(destination, bpy.types.bpy_prop_collection):
            FnModel.__copy_collection_property(destination, source, overwrite=overwrite, replace_name2values=replace_name2values)
        else:
            raise ValueError(f"Unsupported destination: {destination}")

    @staticmethod
    def initalize_display_item_frames(root_object: bpy.types.Object, reset: bool = True):
        frames = root_object.mmd_root.display_item_frames
        if reset and len(frames) > 0:
            root_object.mmd_root.active_display_item_frame = 0
            frames.clear()

        frame_names = {"Root": "Root", "表情": "Facial"}

        for frame_name, frame_name_e in frame_names.items():
            frame = frames.get(frame_name, None) or frames.add()
            frame.name = frame_name
            frame.name_e = frame_name_e
            frame.is_special = True

        armature_object = FnCore.find_armature_object(root_object)
        if armature_object is not None and len(armature_object.data.bones) > 0 and len(frames[0].data) < 1:
            item = frames[0].data.add()
            item.type = "BONE"
            item.name = armature_object.data.bones[0].name

        if not reset:
            frames.move(frames.find("Root"), 0)
            frames.move(frames.find("表情"), 1)

    @staticmethod
    def sync_to_bone_collections(root_object: bpy.types.Object):
        armature_object = FnCore.find_armature_object(root_object)
        assert armature_object is not None
        FnBone.sync_bone_collections_from_mmd_root(armature_object, root_object.mmd_root)

    @staticmethod
    def sync_from_bone_collections(root_object: bpy.types.Object):
        armature_object = FnCore.find_armature_object(root_object)
        assert armature_object is not None
        FnBone.sync_mmd_root_from_bone_collections(root_object.mmd_root, armature_object)

    @staticmethod
    def get_empty_display_size(root_object: bpy.types.Object) -> float:
        return getattr(root_object, Props.empty_display_size)

    @staticmethod
    def new_model(name: str, name_e: str = "", scale: float = 1.0, obj_name: Optional[str] = None, armature_object: Optional[bpy.types.Object] = None, add_root_bone: bool = False, context: Optional[bpy.types.Context] = None) -> bpy.types.Object:
        context = FnContext.ensure_context(context)
        obj_name = obj_name or name

        root_object: bpy.types.Object = bpy.data.objects.new(name=obj_name, object_data=None)
        root_object.mmd_type = "ROOT"
        root_object.mmd_root.name = name
        root_object.mmd_root.name_e = name_e
        root_object["mmd_tools_version"] = MMD_TOOLS_VERSION
        setattr(root_object, Props.empty_display_size, scale / 0.2)
        FnContext.link_object(context, root_object)

        if armature_object:
            m = armature_object.matrix_world
            armature_object.parent_type = "OBJECT"
            armature_object.parent = root_object
            # armature_object.matrix_world = m
            root_object.matrix_world = m
            armature_object.matrix_local.identity()
        else:
            armature_object = bpy.data.objects.new(name=obj_name + "_arm", object_data=bpy.data.armatures.new(name=obj_name))
            armature_object.parent = root_object
            FnContext.link_object(context, armature_object)
        armature_object.lock_rotation = armature_object.lock_location = armature_object.lock_scale = [True, True, True]
        setattr(armature_object, Props.show_in_front, True)
        setattr(armature_object, Props.display_type, "WIRE")

        FnBone.setup_special_bone_collections(armature_object)

        if add_root_bone:
            bone_name = "全ての親"
            with bpyutils.edit_object(armature_object) as data:
                bone = data.edit_bones.new(name=bone_name)
                bone.head = [0.0, 0.0, 0.0]
                bone.tail = [0.0, 0.0, getattr(root_object, Props.empty_display_size)]
            armature_object.pose.bones[bone_name].mmd_bone.name_j = bone_name
            armature_object.pose.bones[bone_name].mmd_bone.name_e = "Root"

        FnContext.set_active_and_select_single_object(context, root_object)

        return root_object

    @staticmethod
    def rename_bone(root_object: bpy.types.Object, old_bone_name: str, new_bone_name: str):
        if old_bone_name == new_bone_name:
            return

        armature_object = FnCore.find_armature_object(root_object)
        assert armature_object is not None
        pose_bone = armature_object.pose.bones.get(old_bone_name)
        assert pose_bone is not None

        FnBone.rename(pose_bone, new_bone_name)

        mmd_root: "MMDRoot" = root_object.mmd_root

        for frame in mmd_root.display_item_frames:
            for item in frame.data:
                if item.type == "BONE" and item.name == old_bone_name:
                    item.name = new_bone_name

        for mesh_object in FnCore.iterate_mesh_objects(root_object):
            if old_bone_name not in mesh_object.vertex_groups:
                continue
            mesh_object.vertex_groups[old_bone_name].name = new_bone_name


class MigrationFnModel:
    """Migration Functions for old MMD models broken by bugs or issues"""

    @classmethod
    def update_mmd_ik_loop_factor(cls):
        for armature_object in bpy.data.objects:
            if armature_object.type != "ARMATURE":
                continue

            if "mmd_ik_loop_factor" not in armature_object:
                return

            FnCore.find_root_object(armature_object).mmd_root.ik_loop_factor = max(armature_object["mmd_ik_loop_factor"], 1)
            del armature_object["mmd_ik_loop_factor"]

    @staticmethod
    def update_mmd_tools_version():
        for root_object in bpy.data.objects:
            if root_object.type != "EMPTY":
                continue

            if not FnCore.is_root_object(root_object):
                continue

            if "mmd_tools_version" in root_object:
                continue

            root_object["mmd_tools_version"] = "2.8.0"


class MMDModel:
    """
    MMD Model class
    """

    def __init__(self, root_object):
        if root_object is None or root_object.mmd_type != "ROOT":
            raise ValueError("must be MMD ROOT type object")
        self.__root: bpy.types.Object = getattr(root_object, "original", root_object)

    @staticmethod
    def create(name: str, name_e: str = "", scale: float = 1, obj_name: Optional[str] = None, armature_object: Optional[bpy.types.Object] = None, add_root_bone: bool = False):
        return MMDModel(FnModel.new_model(name, name_e, scale, obj_name, armature_object, add_root_bone, FnContext.ensure_context()))

    @property
    def morph_slider(self):
        return FnMorph.get_morph_slider(self)

    def loadMorphs(self):
        FnMorph.load_morphs(self)

    def allObjects(self, obj: Optional[bpy.types.Object] = None) -> Iterator[bpy.types.Object]:
        if obj is None:
            obj: bpy.types.Object = self.__root
        yield obj
        yield from FnCore.iterate_child_objects(obj)

    def rootObject(self) -> bpy.types.Object:
        return self.__root

    def armature(self) -> bpy.types.Object:
        armature_object = FnCore.find_armature_object(self.__root)
        assert armature_object is not None
        return armature_object

    def hasRigidGroupObject(self) -> bool:
        return FnCore.find_rigid_group_object(self.__root) is not None

    def rigidGroupObject(self) -> bpy.types.Object:
        return FnCore.ensure_rigid_group_object(FnContext.ensure_context(), self.__root)

    def hasJointGroupObject(self) -> bool:
        return FnCore.find_joint_group_object(self.__root) is not None

    def jointGroupObject(self) -> bpy.types.Object:
        return FnCore.ensure_joint_group_object(FnContext.ensure_context(), self.__root)

    def hasTemporaryGroupObject(self) -> bool:
        return FnCore.find_temporary_group_object(self.__root) is not None

    def temporaryGroupObject(self) -> bpy.types.Object:
        return FnCore.ensure_temporary_group_object(FnContext.ensure_context(), self.__root)

    def meshes(self) -> Iterator[bpy.types.Object]:
        return FnCore.iterate_mesh_objects(self.__root)

    def attachMeshes(self, meshes: Iterator[bpy.types.Object], add_armature_modifier: bool = True):
        FnModel.attach_mesh_objects(self.rootObject(), meshes, add_armature_modifier)

    def firstMesh(self) -> Optional[bpy.types.Object]:
        return next(FnCore.iterate_mesh_objects(self.__root), None)

    def findMesh(self, mesh_name) -> Optional[bpy.types.Object]:
        return FnCore.find_mesh_object_by_name(self.__root, mesh_name)

    def findMeshByIndex(self, index: int) -> Optional[bpy.types.Object]:
        return FnCore.find_mesh_object_by_index(self.__root, index)

    def getMeshIndex(self, mesh_name: str) -> int:
        return FnCore.find_mesh_object_index_by_name(self.__root, mesh_name)

    def rigidBodies(self) -> Iterator[bpy.types.Object]:
        return FnCore.iterate_rigid_body_objects(self.__root)

    def joints(self) -> Iterator[bpy.types.Object]:
        return FnCore.iterate_joint_objects(self.__root)

    def temporaryObjects(self, rigid_track_only=False) -> Iterator[bpy.types.Object]:
        return FnCore.iterate_temporary_objects(self.__root, rigid_track_only)

    def materials(self) -> Iterator[bpy.types.Material]:
        return FnCore.iterate_unique_materials(self.__root)

    def renameBone(self, old_bone_name: str, new_bone_name: str):
        FnModel.rename_bone(self.__root, old_bone_name, new_bone_name)

    def build(self, non_collision_distance_scale=1.5, collision_margin=1e-06):
        context = FnContext.ensure_context()

        root_object = FnCore.find_root_object(self.__root)
        assert root_object is not None
        RigidBodyPhysicsBuilder(
            context,
            root_object,
            FnCore.find_armature_object(root_object),
            FnCore.ensure_rigid_group_object(context, root_object),
            list(FnCore.iterate_rigid_body_objects(root_object)),
            list(FnCore.iterate_joint_objects(root_object)),
            FnCore.ensure_temporary_group_object(context, root_object),
        ).build(non_collision_distance_scale, collision_margin)

    def clean(self):
        context = FnContext.ensure_context()

        root_object = FnCore.find_root_object(self.__root)
        assert root_object is not None
        RigidBodyPhysicsCleaner.clean(
            context,
            root_object,
            FnCore.find_armature_object(root_object),
            FnCore.ensure_rigid_group_object(context, root_object),
            list(FnCore.iterate_rigid_body_objects(root_object)),
            list(FnCore.iterate_joint_objects(root_object)),
            list(FnCore.iterate_temporary_objects(root_object, rigid_track_only=False)),
        )
