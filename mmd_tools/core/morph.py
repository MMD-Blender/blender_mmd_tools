# -*- coding: utf-8 -*-
# Copyright 2016 MMD Tools authors
# This file is part of MMD Tools.

import logging
import math
import re
from typing import TYPE_CHECKING, Iterable, List, Optional, Tuple, cast

import bpy

from core.bone import FnBone

from .. import bpyutils
from ..bpyutils import FnContext, FnObject, TransformConstraintOp
from . import FnCore

if TYPE_CHECKING:
    from ..properties.morph import BoneMorph, UVMorph, VertexMorph
    from ..properties.root import MMDRoot


class FnMorph:
    def __init__(self, morph, root_object: bpy.types.Object):
        self.__morph = morph
        self.__root_object = root_object

    @staticmethod
    def storeShapeKeyOrder(obj, shape_key_names):
        if len(shape_key_names) < 1:
            return
        assert FnContext.get_active_object(FnContext.ensure_context()) == obj
        if obj.data.shape_keys is None:
            bpy.ops.object.shape_key_add()

        def __move_to_bottom(key_blocks, name):
            obj.active_shape_key_index = key_blocks.find(name)
            bpy.ops.object.shape_key_move(type="BOTTOM")

        key_blocks = obj.data.shape_keys.key_blocks
        for name in shape_key_names:
            if name not in key_blocks:
                obj.shape_key_add(name=name, from_mix=False)
            elif len(key_blocks) > 1:
                __move_to_bottom(key_blocks, name)

    @staticmethod
    def fixShapeKeyOrder(obj: bpy.types.Object, shape_key_names: List[str]):
        if len(shape_key_names) < 1:
            return
        assert FnContext.get_active_object(FnContext.ensure_context()) == obj
        key_blocks = getattr(obj.data.shape_keys, "key_blocks", None)
        if key_blocks is None:
            return

        for name in shape_key_names:
            idx = key_blocks.find(name)
            if idx < 0:
                continue
            obj.active_shape_key_index = idx
            bpy.ops.object.shape_key_move(type="BOTTOM")

    @staticmethod
    def get_morph_slider(root_object: bpy.types.Object) -> "_MorphSlider":
        return _MorphSlider(root_object)

    @staticmethod
    def get_shape_keys(mesh_object: bpy.types.Object) -> bpy.types.bpy_prop_collection[bpy.types.ShapeKey] | Tuple[bpy.types.ShapeKey]:
        keys = cast(bpy.types.Mesh, mesh_object.data).shape_keys
        if keys is None:
            return tuple()
        return keys.key_blocks

    @staticmethod
    def __load_morphs(root_object: bpy.types.Object):
        mmd_root: "MMDRoot" = root_object.mmd_root
        vertex_morphs = mmd_root.vertex_morphs
        uv_morphs = mmd_root.uv_morphs

        def category_guess_and_set(morph: "VertexMorph | UVMorph"):
            name_lower = morph.name.lower()
            if "mouth" in name_lower:
                morph.category = "MOUTH"
            elif "eye" in name_lower:
                if "brow" in name_lower:
                    morph.category = "EYEBROW"
                else:
                    morph.category = "EYE"

        for mesh_object in FnCore.iterate_mesh_objects(root_object):
            for kb in FnMorph.get_shape_keys(mesh_object)[1:]:
                if kb.name.startswith("mmd_") or kb.name in vertex_morphs:
                    continue

                item = vertex_morphs.add()
                item.name = kb.name
                item.name_e = kb.name
                category_guess_and_set(item)

            for _g, name, _x in FnMorph.iterate_uv_morph_vertex_groups(mesh_object):
                if name in uv_morphs:
                    continue

                item = uv_morphs.add()
                item.name = item.name_e = name
                item.data_type = "VERTEX_GROUP"
                category_guess_and_set(item)

    @staticmethod
    def remove_shape_key_by_name(mesh_object: bpy.types.Object, shape_key_name: str):
        assert isinstance(mesh_object.data, bpy.types.Mesh)

        shape_keys = mesh_object.data.shape_keys
        if shape_keys is None:
            return

        key_blocks = shape_keys.key_blocks
        if key_blocks is None or shape_key_name not in key_blocks:
            return

        FnObject.mesh_remove_shape_key(mesh_object, key_blocks[shape_key_name])

    @staticmethod
    def copy_shape_key(mesh_object: bpy.types.Object, src_name: str, dest_name: str):
        assert isinstance(mesh_object.data, bpy.types.Mesh)

        shape_keys = mesh_object.data.shape_keys
        if shape_keys is None:
            return

        key_blocks = shape_keys.key_blocks

        if src_name not in key_blocks:
            return

        if dest_name in key_blocks:
            FnObject.mesh_remove_shape_key(mesh_object, key_blocks[dest_name])

        mesh_object.active_shape_key_index = key_blocks.find(src_name)
        mesh_object.show_only_shape_key, last = True, mesh_object.show_only_shape_key
        mesh_object.shape_key_add(name=dest_name, from_mix=True)
        mesh_object.show_only_shape_key = last
        mesh_object.active_shape_key_index = key_blocks.find(dest_name)

    @staticmethod
    def iterate_uv_morph_vertex_groups(target_mesh_object: bpy.types.Object, morph_name: Optional[str] = None, offset_axes: str = "XYZW") -> Iterable[Tuple[bpy.types.VertexGroup, str, str]]:
        """
        Iterate over uv morph vertex groups of the object.

        Args:
            obj (bpy.types.Object): The object to iterate over.
            morph_name (Optional[str], optional): The name of the morph to filter by. Defaults to None.
            offset_axes (str, optional): The axes to filter by. Defaults to "XYZW".

        Yields:
            Iterable[Tuple[bpy.types.VertexGroup, str, str]]: The vertex group, morph name, and axis.
        """
        pattern = re.compile(rf"UV_{morph_name or '.{1,}'}[+-][{offset_axes}]$")
        yield from ((g, g.name[3:-2], g.name[-2:]) for g in target_mesh_object.vertex_groups if pattern.match(g.name))

    @staticmethod
    def copy_uv_morph_vertex_groups(context: bpy.types.Context, obj, src_name, dest_name):
        for vg, _n, _x in FnMorph.iterate_uv_morph_vertex_groups(obj, dest_name):
            obj.vertex_groups.remove(vg)

        for vg_name in tuple(i[0].name for i in FnMorph.iterate_uv_morph_vertex_groups(obj, src_name)):
            obj.vertex_groups.active = obj.vertex_groups[vg_name]
            with context.temp_override(object=obj):
                bpy.ops.object.vertex_group_copy()
            obj.vertex_groups.active.name = vg_name.replace(src_name, dest_name)

    @staticmethod
    def overwrite_bone_morphs_from_action_pose(armature_object):
        armature = armature_object.id_data
        
        # Use animation_data and action instead of action_pose
        if armature.animation_data is None or armature.animation_data.action is None:
            logging.warning('[WARNING] armature "%s" has no animation data or action', armature_object.name)
            return

        action = armature.animation_data.action
        pose_markers = action.pose_markers

        if not pose_markers:
            return

        root = armature_object.parent
        mmd_root = root.mmd_root
        bone_morphs = mmd_root.bone_morphs

        FnContext.select_single_object(FnContext.ensure_context(), armature_object)
        original_mode = bpy.context.object.mode
        bpy.ops.object.mode_set(mode="POSE")
        try:
            for index, pose_marker in enumerate(pose_markers):
                bone_morph = next(iter([m for m in bone_morphs if m.name == pose_marker.name]), None)
                if bone_morph is None:
                    bone_morph = bone_morphs.add()
                    bone_morph.name = pose_marker.name

                bpy.ops.pose.select_all(action="SELECT")
                bpy.ops.pose.transforms_clear()
                
                frame = pose_marker.frame
                bpy.context.scene.frame_set(int(frame))

                mmd_root.active_morph = bone_morphs.find(bone_morph.name)
                bpy.ops.mmd_tools.apply_bone_morph()

            bpy.ops.pose.transforms_clear()

        finally:
            bpy.ops.object.mode_set(mode=original_mode)
        FnContext.select_single_object(FnContext.ensure_context(), root)

    @staticmethod
    def clean_uv_morph_vertex_groups(mesh_object: bpy.types.Object):
        # remove empty vertex groups of uv morphs
        vg_indices = {g.index for g, n, x in FnMorph.iterate_uv_morph_vertex_groups(mesh_object)}
        vertex_groups = mesh_object.vertex_groups
        for v in cast(bpy.types.Mesh, mesh_object.data).vertices:
            for x in v.groups:
                if x.group in vg_indices and x.weight > 0:
                    vg_indices.remove(x.group)
        for i in sorted(vg_indices, reverse=True):
            vg = vertex_groups[i]
            m = mesh_object.modifiers.get(f"mmd_bind{hash(vg.name)}", None)
            if m:
                mesh_object.modifiers.remove(m)
            vertex_groups.remove(vg)

    @staticmethod
    def get_uv_morph_offset_map(mesh_object: bpy.types.MeshObject, morph: "UVMorph") -> dict[int, List[float]]:
        offset_map: dict[int, List[float]] = {}  # offset_map[vertex_index] = offset_xyzw
        if morph.data_type == "VERTEX_GROUP":
            scale = morph.vertex_group_scale
            axis_map = {g.index: x for g, n, x in FnMorph.iterate_uv_morph_vertex_groups(mesh_object, morph.name)}
            for v in cast(bpy.types.Mesh, mesh_object.data).vertices:
                i = v.index
                for x in v.groups:
                    if x.group in axis_map and x.weight > 0:
                        axis, weight = axis_map[x.group], x.weight
                        d = offset_map.setdefault(i, [0, 0, 0, 0])
                        d["XYZW".index(axis[1])] += -weight * scale if axis[0] == "-" else weight * scale
        else:
            for val in morph.data:
                i = val.index
                if i in offset_map:
                    offset_map[i] = [a + b for a, b in zip(offset_map[i], val.offset)]
                else:
                    offset_map[i] = val.offset
        return offset_map

    @staticmethod
    def store_uv_morph_data(obj, morph, offsets=None, offset_axes="XYZW"):
        vertex_groups = obj.vertex_groups
        morph_name = getattr(morph, "name", None)
        if offset_axes:
            for vg, n, x in FnMorph.iterate_uv_morph_vertex_groups(obj, morph_name, offset_axes):
                vertex_groups.remove(vg)
        if not morph_name or not offsets:
            return

        axis_indices = tuple("XYZW".index(x) for x in offset_axes) or tuple(range(4))
        offset_map = FnMorph.get_uv_morph_offset_map(obj, morph) if offset_axes else {}
        for data in offsets:
            idx, offset = data.index, data.offset
            for i in axis_indices:
                offset_map.setdefault(idx, [0, 0, 0, 0])[i] += round(offset[i], 5)

        max_value = max(max(abs(x) for x in v) for v in offset_map.values() or ([0],))
        scale = morph.vertex_group_scale = max(abs(morph.vertex_group_scale), max_value)
        for idx, offset in offset_map.items():
            for val, axis in zip(offset, "XYZW"):
                if abs(val) <= 1e-4:
                    continue
                vg_name = "UV_{0}{1}{2}".format(morph_name, "-" if val < 0 else "+", axis)
                vg = vertex_groups.get(vg_name, None) or vertex_groups.new(name=vg_name)
                vg.add(index=[idx], weight=abs(val) / scale, type="REPLACE")

    def update_mat_related_mesh(self, new_mesh=None):
        for offset in self.__morph.data:
            # Use the new_mesh if provided
            mesh_object = new_mesh
            if new_mesh is None:
                # Try to find the mesh by material name
                mesh_object = FnCore.find_mesh_object_by_name(self.__root_object, offset.material)

            if mesh_object is None:
                # Given this point we need to loop through all the meshes
                mesh_object = next((m for m in FnCore.iterate_mesh_objects(self.__root_object) if m.data.materials.find(offset.material) >= 0), None)

            # Finally update the reference
            if mesh_object is not None:
                offset.related_mesh = mesh_object.data.name

    @staticmethod
    def clean_duplicated_material_morphs(mmd_root_object: bpy.types.Object):
        """Clean duplicated material_morphs and data from mmd_root_object.mmd_root.material_morphs[].data[]"""
        mmd_root = mmd_root_object.mmd_root

        def morph_data_equals(l, r) -> bool:
            return (
                l.related_mesh_data == r.related_mesh_data
                and l.offset_type == r.offset_type
                and l.material == r.material
                and all(a == b for a, b in zip(l.diffuse_color, r.diffuse_color))
                and all(a == b for a, b in zip(l.specular_color, r.specular_color))
                and l.shininess == r.shininess
                and all(a == b for a, b in zip(l.ambient_color, r.ambient_color))
                and all(a == b for a, b in zip(l.edge_color, r.edge_color))
                and l.edge_weight == r.edge_weight
                and all(a == b for a, b in zip(l.texture_factor, r.texture_factor))
                and all(a == b for a, b in zip(l.sphere_texture_factor, r.sphere_texture_factor))
                and all(a == b for a, b in zip(l.toon_texture_factor, r.toon_texture_factor))
            )

        def morph_equals(l, r) -> bool:
            return len(l.data) == len(r.data) and all(morph_data_equals(a, b) for a, b in zip(l.data, r.data))

        # Remove duplicated mmd_root.material_morphs.data[]
        for material_morph in mmd_root.material_morphs:
            save_materil_morph_datas = []
            remove_material_morph_data_indices = []
            for index, material_morph_data in enumerate(material_morph.data):
                if any(morph_data_equals(material_morph_data, saved_material_morph_data) for saved_material_morph_data in save_materil_morph_datas):
                    remove_material_morph_data_indices.append(index)
                    continue
                save_materil_morph_datas.append(material_morph_data)

            for index in reversed(remove_material_morph_data_indices):
                material_morph.data.remove(index)

        # Mark duplicated mmd_root.material_morphs[]
        save_material_morphs = []
        remove_material_morph_names = []
        for material_morph in sorted(mmd_root.material_morphs, key=lambda m: m.name):
            if any(morph_equals(material_morph, saved_material_morph) for saved_material_morph in save_material_morphs):
                remove_material_morph_names.append(material_morph.name)
                continue

            save_material_morphs.append(material_morph)

        # Remove marked mmd_root.material_morphs[]
        for material_morph_name in remove_material_morph_names:
            mmd_root.material_morphs.remove(mmd_root.material_morphs.find(material_morph_name))

    @staticmethod
    def ensure_placeholder_mesh_object(context: bpy.types.Context, root_object: bpy.types.Object) -> bpy.types.Object:
        mesh_object = FnCore.find_placeholder_mesh_object(root_object)
        if mesh_object is None:
            mesh_object = FnContext.new_and_link_object(context, name=".placeholder", object_data=bpy.data.meshes.new(".placeholder"))
            mesh_object.mmd_type = "PLACEHOLDER"
            mesh_object.parent = root_object

        if cast(bpy.types.Mesh, mesh_object.data).shape_keys is None:
            key = mesh_object.shape_key_add(name="--- morph sliders ---")
            key.mute = True
            mesh_object.active_shape_key_index = 0

        return mesh_object

    @staticmethod
    def ensure_placeholder_armature_object(context: bpy.types.Object, root_object: bpy.types.Object) -> bpy.types.Object:
        mesh_object = FnCore.find_placeholder_mesh_object(root_object)
        assert mesh_object is not None

        armature_object = FnCore.find_placeholder_armature_object(mesh_object)
        if armature_object is None:
            armature_object = FnContext.new_and_link_object(context, name=".dummy_armature", object_data=bpy.data.armatures.new(".dummy_armature"))
            armature_object.mmd_type = "PLACEHOLDER"
            armature_object.parent = mesh_object

            FnBone.setup_special_bone_collections(armature_object)

        return armature_object

    @staticmethod
    def get_shapekey(root_object: bpy.types.Object, morph_name: str) -> Optional[bpy.types.ShapeKey]:
        mesh_object = FnCore.find_placeholder_mesh_object(root_object)
        if mesh_object is None:
            return None

        key_blocks = cast(bpy.types.Mesh, mesh_object.data).shape_keys.key_blocks
        if key_blocks[0].mute:
            return None

        return key_blocks.get(morph_name, None)

    @staticmethod
    def __sync_shape_keys_from_mmd_root(root_object: bpy.types.Object):
        FnMorph.__load_morphs(root_object)
        placeholder_mesh_object = FnCore.find_placeholder_mesh_object(root_object)
        assert placeholder_mesh_object is not None

        mmd_root: "MMDRoot" = root_object.mmd_root
        shape_keys = cast(bpy.types.Mesh, placeholder_mesh_object.data).shape_keys.key_blocks
        for name in (x.name for attr in ("group", "vertex", "bone", "uv", "material") for x in getattr(mmd_root, f"{attr}_morphs", ())):
            if name and name not in shape_keys:
                placeholder_mesh_object.shape_key_add(name=name, from_mix=False)

    @staticmethod
    def __driver_variables(id_data, path, index=-1):
        d = id_data.driver_add(path, index)
        variables = d.driver.variables
        for x in variables:
            variables.remove(x)
        return d.driver, variables

    @staticmethod
    def __add_single_prop(variables, id_obj, data_path, prefix):
        var = variables.new()
        var.name = f"{prefix}{len(variables)}"
        var.type = "SINGLE_PROP"
        target = var.targets[0]
        target.id_type = "OBJECT"
        target.id = id_obj
        target.data_path = data_path
        return var

    @staticmethod
    def __shape_key_driver_check(key_block: bpy.types.ShapeKey, resolve_path: bool = False) -> bool:
        mesh_object = cast(bpy.types.Object, key_block.id_data)

        if resolve_path:
            try:
                mesh_object.path_resolve(key_block.path_from_id())
            except ValueError:
                return False

        if not mesh_object.animation_data:
            return True

        d = mesh_object.animation_data.drivers.find(key_block.path_from_id("value"))

        return not d or d.driver.expression == "".join(("*w", "+g", "v")[-1 if i < 1 else i % 2] + str(i + 1) for i in range(len(d.driver.variables)))

    @staticmethod
    def __cleanup(root_object: bpy.types.Object, names_in_use=None):
        names_in_use = names_in_use or {}
        morph_sliders = FnCore.find_placeholder_mesh_object(root_object)
        morph_sliders = cast(bpy.types.Mesh, morph_sliders.data).shape_keys.key_blocks if morph_sliders else cast(dict[str, bpy.types.ShapeKey], {})
        for mesh_object in FnCore.iterate_mesh_objects(root_object):
            for kb in FnMorph.get_shape_keys(mesh_object):
                if kb.name in names_in_use:
                    continue

                if kb.name.startswith("mmd_bind"):
                    kb.driver_remove("value")
                    ms = morph_sliders[kb.relative_key.name]
                    kb.relative_key.slider_min, kb.relative_key.slider_max = min(ms.slider_min, math.floor(ms.value)), max(ms.slider_max, math.ceil(ms.value))
                    kb.relative_key.value = ms.value
                    kb.relative_key.mute = False
                    FnObject.mesh_remove_shape_key(mesh_object, kb)

                elif kb.name in morph_sliders and FnMorph.__shape_key_driver_check(kb):
                    ms = morph_sliders[kb.name]
                    kb.driver_remove("value")
                    kb.slider_min, kb.slider_max = min(ms.slider_min, math.floor(kb.value)), max(ms.slider_max, math.ceil(kb.value))

            for m in mesh_object.modifiers:  # uv morph
                if m.name.startswith("mmd_bind") and m.name not in names_in_use:
                    mesh_object.modifiers.remove(m)

        from .shader import _MaterialMorph

        for m in FnCore.iterate_materials(root_object):
            if m is None or m.node_tree is None:
                continue

            for n in sorted((x for x in m.node_tree.nodes if x.name.startswith("mmd_bind")), key=lambda x: -x.location[0]):
                _MaterialMorph.reset_morph_links(n)
                m.node_tree.nodes.remove(n)

        attributes = set(TransformConstraintOp.min_max_attributes("LOCATION", "to")) | set(TransformConstraintOp.min_max_attributes("ROTATION", "to"))

        for b in FnCore.find_armature_object(root_object).pose.bones:
            for c in b.constraints:
                if not c.name.startswith("mmd_bind") or c.name[:-4] in names_in_use:
                    continue

                for attr in attributes:
                    c.driver_remove(attr)

                b.constraints.remove(c)

    @staticmethod
    def unbind(root_object: bpy.types.Object):
        mmd_root: "MMDRoot" = root_object.mmd_root

        # after unbind, the weird lag problem will disappear.
        mmd_root.morph_panel_show_settings = True

        for m in mmd_root.bone_morphs:
            for d in m.data:
                d.name = ""

        for m in mmd_root.material_morphs:
            for d in m.data:
                d.name = ""

        placeholder_mesh_object = FnCore.find_placeholder_mesh_object(root_object)
        if placeholder_mesh_object:
            cast(bpy.types.Mesh, placeholder_mesh_object.data).shape_keys.key_blocks[0].mute = True
            placeholder_armature_object = FnCore.find_placeholder_armature_object(placeholder_mesh_object)
            if placeholder_armature_object:
                for b in placeholder_armature_object.pose.bones:
                    if not b.name.startswith("mmd_bind"):
                        continue
                    b.driver_remove("location")
                    b.driver_remove("rotation_quaternion")

        FnMorph.__cleanup(root_object)

    @staticmethod
    def bind(context: bpy.types.Context, root_object: bpy.types.Object):
        armature_object = FnCore.find_armature_object(root_object)
        assert armature_object is not None

        mmd_root: "MMDRoot" = root_object.mmd_root

        # hide detail to avoid weird lag problem
        mmd_root.morph_panel_show_settings = False

        FnMorph.__load_morphs(root_object)
        placeholder_mesh_object = FnMorph.ensure_placeholder_mesh_object(context, root_object)
        FnMorph.__sync_shape_keys_from_mmd_root(root_object)

        placeholder_armature_object = FnMorph.ensure_placeholder_armature_object(context, placeholder_mesh_object)
        morph_sliders = cast(bpy.types.Mesh, placeholder_mesh_object.data).shape_keys.key_blocks

        # data gathering
        group_map: dict[Tuple[str, str], list[list[str]]] = {}

        shape_key_map: dict[str, list[Tuple[bpy.types.ShapeKey, str, list[str]]]] = {}
        uv_morph_map: dict[str, list[Tuple[str, str, str, list[str]]]] = {}
        for mesh_object in FnCore.iterate_mesh_objects(root_object):
            mesh_object.show_only_shape_key = False
            key_blocks = FnMorph.get_shape_keys(mesh_object)
            for kb in key_blocks:
                kb_name = kb.name
                if kb_name not in morph_sliders:
                    continue

                if FnMorph.__shape_key_driver_check(kb, resolve_path=True):
                    name_bind, kb_bind = kb_name, kb
                else:
                    name_bind = "mmd_bind%s" % hash(morph_sliders[kb_name])
                    if name_bind not in key_blocks:
                        mesh_object.shape_key_add(name=name_bind, from_mix=False)
                    kb_bind = key_blocks[name_bind]
                    kb_bind.relative_key = kb
                kb_bind.slider_min = -10
                kb_bind.slider_max = 10

                data_path = 'data.shape_keys.key_blocks["%s"].value' % kb_name.replace('"', '\\"')
                groups: list[str] = []
                shape_key_map.setdefault(name_bind, []).append((kb_bind, data_path, groups))
                group_map.setdefault(("vertex_morphs", kb_name), []).append(groups)

            mesh = cast(bpy.types.Mesh, mesh_object.data)
            uv_layers = [l.name for l in mesh.uv_layers if not l.name.startswith("_")]
            uv_layers += [""] * (5 - len(uv_layers))
            for vg, morph_name, axis in FnMorph.iterate_uv_morph_vertex_groups(mesh_object):
                morph = mmd_root.uv_morphs.get(morph_name, None)
                if morph is None or morph.data_type != "VERTEX_GROUP":
                    continue

                uv_layer = "_" + uv_layers[morph.uv_index] if axis[1] in "ZW" else uv_layers[morph.uv_index]
                if uv_layer not in mesh.uv_layers:
                    continue

                name_bind = f"mmd_bind{hash(vg.name)}"
                uv_morph_map.setdefault(name_bind, [])
                mod = cast(bpy.types.UVWarpModifier, mesh_object.modifiers.get(name_bind, None) or mesh_object.modifiers.new(name=name_bind, type="UV_WARP"))
                mod.show_expanded = False
                mod.vertex_group = vg.name
                mod.axis_u, mod.axis_v = ("Y", "X") if axis[1] in "YW" else ("X", "Y")
                mod.uv_layer = uv_layer
                name_bind = f"mmd_bind{hash(morph_name)}"
                mod.object_from = mod.object_to = placeholder_armature_object
                if axis[0] == "-":
                    mod.bone_from, mod.bone_to = "mmd_bind_ctrl_base", name_bind
                else:
                    mod.bone_from, mod.bone_to = name_bind, "mmd_bind_ctrl_base"

        bone_offset_map: dict[str, Tuple[str, str, str, list[str]]] = {}
        placeholder_armature = cast(bpy.types.Armature, placeholder_armature_object.data)
        with bpyutils.edit_object(placeholder_armature_object) as data:
            from .bone import FnBone

            edit_bones = placeholder_armature.edit_bones

            def __get_bone(name, parent):
                b = edit_bones.get(name, None) or edit_bones.new(name=name)
                b.head = (0, 0, 0)
                b.tail = (0, 0, 1)
                b.use_deform = False
                b.parent = parent
                return b

            m: "BoneMorph"
            for m in mmd_root.bone_morphs:
                morph_name = m.name.replace('"', '\\"')
                data_path = f'data.shape_keys.key_blocks["{morph_name}"].value'
                for d in m.data:
                    if not d.bone:
                        d.name = ""
                        continue
                    d.name = name_bind = f"mmd_bind{hash(d)}"
                    b = FnBone.set_edit_bone_to_shadow(__get_bone(name_bind, None))
                    groups: list[str] = []
                    bone_offset_map[name_bind] = (m.name, d, b.name, data_path, groups)
                    group_map.setdefault(("bone_morphs", m.name), []).append(groups)

            ctrl_base = FnBone.set_edit_bone_to_dummy(__get_bone("mmd_bind_ctrl_base", None))
            for m in mmd_root.uv_morphs:
                morph_name = m.name.replace('"', '\\"')
                data_path = f'data.shape_keys.key_blocks["{morph_name}"].value'
                scale_path = f'mmd_root.uv_morphs["{morph_name}"].vertex_group_scale'
                name_bind = f"mmd_bind{hash(m.name)}"
                b = FnBone.set_edit_bone_to_dummy(__get_bone(name_bind, ctrl_base))
                groups = []
                uv_morph_map.setdefault(name_bind, []).append((b.name, data_path, scale_path, groups))
                group_map.setdefault(("uv_morphs", m.name), []).append(groups)

            used_bone_names = bone_offset_map.keys() | uv_morph_map.keys()
            used_bone_names.add(ctrl_base.name)
            for b in edit_bones:  # cleanup
                if b.name.startswith("mmd_bind") and b.name not in used_bone_names:
                    edit_bones.remove(b)

        material_offset_map = {}
        for m in mmd_root.material_morphs:
            morph_name = m.name.replace('"', '\\"')
            data_path = f'data.shape_keys.key_blocks["{morph_name}"].value'
            groups = []
            group_map.setdefault(("material_morphs", m.name), []).append(groups)
            material_offset_map.setdefault("group_dict", {})[m.name] = (data_path, groups)
            for d in m.data:
                d.name = name_bind = f"mmd_bind{hash(d)}"
                # add '#' before material name to avoid conflict with group_dict
                table = material_offset_map.setdefault("#" + d.material, ([], []))
                table[1 if d.offset_type == "ADD" else 0].append((m.name, d, name_bind))

        for m in mmd_root.group_morphs:
            if len(m.data) != len(set(m.data.keys())):
                logging.warning(' * Found duplicated morph data in Group Morph "%s"', m.name)
            morph_name = m.name.replace('"', '\\"')
            morph_path = f'data.shape_keys.key_blocks["{morph_name}"].value'
            for d in m.data:
                data_name = d.name.replace('"', '\\"')
                factor_path = f'mmd_root.group_morphs["{morph_name}"].data["{data_name}"].factor'
                for groups in group_map.get((d.morph_type, d.name), ()):
                    groups.append((m.name, morph_path, factor_path))

        self.__cleanup(shape_key_map.keys() | bone_offset_map.keys() | uv_morph_map.keys())

        def __config_groups(variables, expression, groups):
            for g_name, morph_path, factor_path in groups:
                var = self.__add_single_prop(variables, placeholder_mesh_object, morph_path, "g")
                fvar = self.__add_single_prop(variables, root_object, factor_path, "w")
                expression = f"{expression}+{var.name}*{fvar.name}"
            return expression

        # vertex morphs
        for kb_bind, morph_data_path, groups in (i for l in shape_key_map.values() for i in l):
            driver, variables = self.__driver_variables(kb_bind, "value")
            var = self.__add_single_prop(variables, placeholder_mesh_object, morph_data_path, "v")
            if kb_bind.name.startswith("mmd_bind"):
                driver.expression = f"-({__config_groups(variables, var.name, groups)})"
                kb_bind.relative_key.mute = True
            else:
                driver.expression = __config_groups(variables, var.name, groups)
            kb_bind.mute = False

        # bone morphs
        def __config_bone_morph(constraints, map_type, attributes, val, val_str):
            c_name = f"mmd_bind{hash(data)}.{map_type[:3]}"
            c = TransformConstraintOp.create(constraints, c_name, map_type)
            TransformConstraintOp.update_min_max(c, val, None)
            c.show_expanded = False
            c.target = placeholder_armature_object
            c.subtarget = bname
            for attr in attributes:
                driver, variables = self.__driver_variables(armature_object, c.path_from_id(attr))
                var = self.__add_single_prop(variables, placeholder_mesh_object, morph_data_path, "b")
                expression = __config_groups(variables, var.name, groups)
                sign = "-" if attr.startswith("to_min") else ""
                driver.expression = f"{sign}{val_str}*({expression})"

        attributes_rot = TransformConstraintOp.min_max_attributes("ROTATION", "to")
        attributes_loc = TransformConstraintOp.min_max_attributes("LOCATION", "to")
        for morph_name, data, bname, morph_data_path, groups in bone_offset_map.values():
            b = placeholder_armature_object.pose.bones[bname]
            b.location = data.location
            b.rotation_quaternion = data.rotation.__class__(*data.rotation.to_axis_angle())  # Fix for consistency
            b.is_mmd_shadow_bone = True
            b.mmd_shadow_bone_type = "BIND"
            pb = armature_object.pose.bones[data.bone]
            __config_bone_morph(pb.constraints, "ROTATION", attributes_rot, math.pi, "pi")
            __config_bone_morph(pb.constraints, "LOCATION", attributes_loc, 100, "100")

        # uv morphs
        # HACK: workaround for Blender 2.80+, data_path can't be properly detected (Save & Reopen file also works)
        root_object.parent, root_object.parent, root_object.matrix_parent_inverse = placeholder_armature_object, root_object.parent, root_object.matrix_parent_inverse.copy()
        b = placeholder_armature_object.pose.bones["mmd_bind_ctrl_base"]
        b.is_mmd_shadow_bone = True
        b.mmd_shadow_bone_type = "BIND"
        for bname, data_path, scale_path, groups in (i for l in uv_morph_map.values() for i in l):
            b = placeholder_armature_object.pose.bones[bname]
            b.is_mmd_shadow_bone = True
            b.mmd_shadow_bone_type = "BIND"
            driver, variables = self.__driver_variables(b, "location", index=0)
            var = self.__add_single_prop(variables, placeholder_mesh_object, data_path, "u")
            fvar = self.__add_single_prop(variables, root_object, scale_path, "s")
            driver.expression = f"({__config_groups(variables, var.name, groups)})*{fvar.name}"

        # material morphs
        from .shader import _MaterialMorph

        group_dict = material_offset_map.get("group_dict", {})

        def __config_material_morph(mat, morph_list):
            nodes = _MaterialMorph.setup_morph_nodes(mat, tuple(x[1] for x in morph_list))
            for (morph_name, data, name_bind), node in zip(morph_list, nodes):
                node.label, node.name = morph_name, name_bind
                data_path, groups = group_dict[morph_name]
                driver, variables = self.__driver_variables(mat.node_tree, node.inputs[0].path_from_id("default_value"))
                var = self.__add_single_prop(variables, placeholder_mesh_object, data_path, "m")
                driver.expression = "%s" % __config_groups(variables, var.name, groups)

        for mat in (m for m in rig.materials() if m and m.use_nodes and not m.name.startswith("mmd_")):
            mul_all, add_all = material_offset_map.get("#", ([], []))
            if mat.name == "":
                logging.warning("Oh no. The material name should never empty.")
                mul_list, add_list = [], []
            else:
                mat_name = "#" + mat.name
                mul_list, add_list = material_offset_map.get(mat_name, ([], []))
            morph_list = tuple(mul_all + mul_list + add_all + add_list)
            __config_material_morph(mat, morph_list)
            mat_edge = bpy.data.materials.get("mmd_edge." + mat.name, None)
            if mat_edge:
                __config_material_morph(mat_edge, morph_list)

        morph_sliders[0].mute = False


class MigrationFnMorph:
    @staticmethod
    def update_mmd_morph():
        from .material import FnMaterial

        for root in bpy.data.objects:
            if root.mmd_type != "ROOT":
                continue

            for mat_morph in root.mmd_root.material_morphs:
                for morph_data in mat_morph.data:
                    if morph_data.material_data is not None:
                        # SUPPORT_UNTIL: 5 LTS
                        # The material_id is also no longer used, but for compatibility with older version mmd_tools, keep it.
                        if "material_id" not in morph_data.material_data.mmd_material or "material_id" not in morph_data or morph_data.material_data.mmd_material["material_id"] == morph_data["material_id"]:
                            # In the new version, the related_mesh property is no longer used.
                            # Explicitly remove this property to avoid misuse.
                            if "related_mesh" in morph_data:
                                del morph_data["related_mesh"]
                            continue

                        else:
                            # Compat case. The new version mmd_tools saved. And old version mmd_tools edit. Then new version mmd_tools load again.
                            # Go update path.
                            pass

                    morph_data.material_data = None
                    if "material_id" in morph_data:
                        mat_id = morph_data["material_id"]
                        if mat_id != -1:
                            fnMat = FnMaterial.from_material_id(mat_id)
                            if fnMat:
                                morph_data.material_data = fnMat.material
                            else:
                                morph_data["material_id"] = -1

                    morph_data.related_mesh_data = None
                    if "related_mesh" in morph_data:
                        related_mesh = morph_data["related_mesh"]
                        del morph_data["related_mesh"]
                        if related_mesh != "" and related_mesh in bpy.data.meshes:
                            morph_data.related_mesh_data = bpy.data.meshes[related_mesh]

    @staticmethod
    def ensure_material_id_not_conflict():
        mat_ids_set = set()

        # The reference library properties cannot be modified and bypassed in advance.
        need_update_mat = []
        for mat in bpy.data.materials:
            if mat.mmd_material.material_id < 0:
                continue
            if mat.library is not None:
                mat_ids_set.add(mat.mmd_material.material_id)
            else:
                need_update_mat.append(mat)

        for mat in need_update_mat:
            if mat.mmd_material.material_id in mat_ids_set:
                mat.mmd_material.material_id = max(mat_ids_set) + 1
            mat_ids_set.add(mat.mmd_material.material_id)

    @staticmethod
    def compatible_with_old_version_mmd_tools():
        MigrationFnMorph.ensure_material_id_not_conflict()

        for root in bpy.data.objects:
            if root.mmd_type != "ROOT":
                continue

            for mat_morph in root.mmd_root.material_morphs:
                for morph_data in mat_morph.data:
                    morph_data["related_mesh"] = morph_data.related_mesh

                    if morph_data.material_data is None:
                        morph_data.material_id = -1
                    else:
                        morph_data.material_id = morph_data.material_data.mmd_material.material_id


class __MorphSlider:
    def __init__(self, root_object: bpy.types.Object):
        self.__root_object = root_object

    def placeholder(self, create: bool = False, binded: bool = False) -> Optional[bpy.types.Object]:
        obj = FnCore.find_placeholder_mesh_object(self.__root_object)
        if create and obj is None:
            obj = FnContext.new_and_link_object(FnContext.ensure_context(), name=".placeholder", object_data=bpy.data.meshes.new(".placeholder"))
            obj.mmd_type = "PLACEHOLDER"
            obj.parent = self.__root_object
        if obj and obj.data.shape_keys is None:
            key = obj.shape_key_add(name="--- morph sliders ---")
            key.mute = True
            obj.active_shape_key_index = 0
        if binded and obj and obj.data.shape_keys.key_blocks[0].mute:
            return None
        return obj

    @property
    def dummy_armature(self):
        obj = self.placeholder()
        return self.__dummy_armature(obj) if obj else None

    def __dummy_armature(self, obj: bpy.types.Object, create: bool = False) -> Optional[bpy.types.Object]:
        arm = FnCore.find_placeholder_armature_object(obj)
        if create and arm is None:
            arm = FnContext.new_and_link_object(FnContext.ensure_context(), name=".dummy_armature", object_data=bpy.data.armatures.new(".dummy_armature"))
            arm.mmd_type = "PLACEHOLDER"
            arm.parent = obj

            FnBone.setup_special_bone_collections(arm)
        return arm

    def get(self, morph_name):
        obj = self.placeholder()
        if obj is None:
            return None
        key_blocks = obj.data.shape_keys.key_blocks
        if key_blocks[0].mute:
            return None
        return key_blocks.get(morph_name, None)

    def new_placeholder_mesh_object(self) -> bpy.types.Object:
        FnMorph.__load_morphs(self.__root_object)
        obj = self.placeholder(create=True)
        self.__load(obj, self.__root_object.mmd_root)
        return obj

    def __load(self, obj, mmd_root):
        attr_list = ("group", "vertex", "bone", "uv", "material")
        morph_sliders = obj.data.shape_keys.key_blocks
        for m in (x for attr in attr_list for x in getattr(mmd_root, attr + "_morphs", ())):
            name = m.name
            # if name[-1] == '\\': # fix driver's bug???
            #    m.name = name = name + ' '
            if name and name not in morph_sliders:
                obj.shape_key_add(name=name, from_mix=False)

    @staticmethod
    def __driver_variables(id_data, path, index=-1):
        d = id_data.driver_add(path, index)
        variables = d.driver.variables
        for x in variables:
            variables.remove(x)
        return d.driver, variables

    @staticmethod
    def __add_single_prop(variables, id_obj, data_path, prefix):
        var = variables.new()
        var.name = f"{prefix}{len(variables)}"
        var.type = "SINGLE_PROP"
        target = var.targets[0]
        target.id_type = "OBJECT"
        target.id = id_obj
        target.data_path = data_path
        return var

    @staticmethod
    def __shape_key_driver_check(key_block, resolve_path=False):
        if resolve_path:
            try:
                key_block.id_data.path_resolve(key_block.path_from_id())
            except ValueError:
                return False
        if not key_block.id_data.animation_data:
            return True
        d = key_block.id_data.animation_data.drivers.find(key_block.path_from_id("value"))
        if isinstance(d, int):  # for Blender 2.76 or older
            data_path = key_block.path_from_id("value")
            d = next((i for i in key_block.id_data.animation_data.drivers if i.data_path == data_path), None)
        return not d or d.driver.expression == "".join(("*w", "+g", "v")[-1 if i < 1 else i % 2] + str(i + 1) for i in range(len(d.driver.variables)))

    def __cleanup(self, names_in_use=None):
        names_in_use = names_in_use or {}
        morph_sliders = self.placeholder()
        morph_sliders = morph_sliders.data.shape_keys.key_blocks if morph_sliders else {}
        for mesh_object in FnCore.iterate_mesh_objects(self.__root_object):
            for kb in FnMorph.get_shape_keys(mesh_object):
                if kb.name in names_in_use:
                    continue

                if kb.name.startswith("mmd_bind"):
                    kb.driver_remove("value")
                    ms = morph_sliders[kb.relative_key.name]
                    kb.relative_key.slider_min, kb.relative_key.slider_max = min(ms.slider_min, math.floor(ms.value)), max(ms.slider_max, math.ceil(ms.value))
                    kb.relative_key.value = ms.value
                    kb.relative_key.mute = False
                    FnObject.mesh_remove_shape_key(mesh_object, kb)

                elif kb.name in morph_sliders and self.__shape_key_driver_check(kb):
                    ms = morph_sliders[kb.name]
                    kb.driver_remove("value")
                    kb.slider_min, kb.slider_max = min(ms.slider_min, math.floor(kb.value)), max(ms.slider_max, math.ceil(kb.value))

            for m in mesh_object.modifiers:  # uv morph
                if m.name.startswith("mmd_bind") and m.name not in names_in_use:
                    mesh_object.modifiers.remove(m)

        from .shader import _MaterialMorph

        for m in rig.materials():
            if m and m.node_tree:
                for n in sorted((x for x in m.node_tree.nodes if x.name.startswith("mmd_bind")), key=lambda x: -x.location[0]):
                    _MaterialMorph.reset_morph_links(n)
                    m.node_tree.nodes.remove(n)

        attributes = set(TransformConstraintOp.min_max_attributes("LOCATION", "to"))
        attributes |= set(TransformConstraintOp.min_max_attributes("ROTATION", "to"))
        for b in rig.armature().pose.bones:
            for c in b.constraints:
                if c.name.startswith("mmd_bind") and c.name[:-4] not in names_in_use:
                    for attr in attributes:
                        c.driver_remove(attr)
                    b.constraints.remove(c)

    def unbind(self):
        mmd_root = self.__root_object.mmd_root

        # after unbind, the weird lag problem will disappear.
        mmd_root.morph_panel_show_settings = True

        for m in mmd_root.bone_morphs:
            for d in m.data:
                d.name = ""

        for m in mmd_root.material_morphs:
            for d in m.data:
                d.name = ""

        placeholder_mesh_object = self.placeholder()
        if placeholder_mesh_object:
            placeholder_mesh_object.data.shape_keys.key_blocks[0].mute = True
            placeholder_armature_object = self.__dummy_armature(placeholder_mesh_object)
            if placeholder_armature_object:
                for b in placeholder_armature_object.pose.bones:
                    if not b.name.startswith("mmd_bind"):
                        continue
                    b.driver_remove("location")
                    b.driver_remove("rotation_quaternion")

        self.__cleanup()

    def bind(self):
        root_object = self.__root_object
        armature_object = FnCore.find_armature_object(root_object)
        mmd_root: "MMDRoot" = root_object.mmd_root

        # hide detail to avoid weird lag problem
        mmd_root.morph_panel_show_settings = False

        placeholder_mesh_object = self.new_placeholder_mesh_object()
        placeholder_armature_object = self.__dummy_armature(placeholder_mesh_object, create=True)
        morph_sliders = placeholder_mesh_object.data.shape_keys.key_blocks

        # data gathering
        group_map = {}

        shape_key_map = {}
        uv_morph_map = {}
        for mesh_object in FnCore.iterate_mesh_objects(root_object):
            mesh_object.show_only_shape_key = False
            key_blocks = FnMorph.get_shape_keys(mesh_object)
            for kb in key_blocks:
                kb_name = kb.name
                if kb_name not in morph_sliders:
                    continue

                if self.__shape_key_driver_check(kb, resolve_path=True):
                    name_bind, kb_bind = kb_name, kb
                else:
                    name_bind = "mmd_bind%s" % hash(morph_sliders[kb_name])
                    if name_bind not in key_blocks:
                        mesh_object.shape_key_add(name=name_bind, from_mix=False)
                    kb_bind = key_blocks[name_bind]
                    kb_bind.relative_key = kb
                kb_bind.slider_min = -10
                kb_bind.slider_max = 10

                data_path = 'data.shape_keys.key_blocks["%s"].value' % kb_name.replace('"', '\\"')
                groups = []
                shape_key_map.setdefault(name_bind, []).append((kb_bind, data_path, groups))
                group_map.setdefault(("vertex_morphs", kb_name), []).append(groups)

            uv_layers = [l.name for l in mesh_object.data.uv_layers if not l.name.startswith("_")]
            uv_layers += [""] * (5 - len(uv_layers))
            for vg, morph_name, axis in FnMorph.iterate_uv_morph_vertex_groups(mesh_object):
                morph = mmd_root.uv_morphs.get(morph_name, None)
                if morph is None or morph.data_type != "VERTEX_GROUP":
                    continue

                uv_layer = "_" + uv_layers[morph.uv_index] if axis[1] in "ZW" else uv_layers[morph.uv_index]
                if uv_layer not in mesh_object.data.uv_layers:
                    continue

                name_bind = f"mmd_bind{hash(vg.name)}"
                uv_morph_map.setdefault(name_bind, ())
                mod = cast(bpy.types.UVWarpModifier, mesh_object.modifiers.get(name_bind, None) or mesh_object.modifiers.new(name=name_bind, type="UV_WARP"))
                mod.show_expanded = False
                mod.vertex_group = vg.name
                mod.axis_u, mod.axis_v = ("Y", "X") if axis[1] in "YW" else ("X", "Y")
                mod.uv_layer = uv_layer
                name_bind = f"mmd_bind{hash(morph_name)}"
                mod.object_from = mod.object_to = placeholder_armature_object
                if axis[0] == "-":
                    mod.bone_from, mod.bone_to = "mmd_bind_ctrl_base", name_bind
                else:
                    mod.bone_from, mod.bone_to = name_bind, "mmd_bind_ctrl_base"

        bone_offset_map = {}
        with bpyutils.edit_object(placeholder_armature_object) as data:
            from .bone import FnBone

            edit_bones = data.edit_bones

            def __get_bone(name, parent):
                b = edit_bones.get(name, None) or edit_bones.new(name=name)
                b.head = (0, 0, 0)
                b.tail = (0, 0, 1)
                b.use_deform = False
                b.parent = parent
                return b

            for m in mmd_root.bone_morphs:
                morph_name = m.name.replace('"', '\\"')
                data_path = f'data.shape_keys.key_blocks["{morph_name}"].value'
                for d in m.data:
                    if not d.bone:
                        d.name = ""
                        continue
                    d.name = name_bind = f"mmd_bind{hash(d)}"
                    b = FnBone.set_edit_bone_to_shadow(__get_bone(name_bind, None))
                    groups = []
                    bone_offset_map[name_bind] = (m.name, d, b.name, data_path, groups)
                    group_map.setdefault(("bone_morphs", m.name), []).append(groups)

            ctrl_base = FnBone.set_edit_bone_to_dummy(__get_bone("mmd_bind_ctrl_base", None))
            for m in mmd_root.uv_morphs:
                morph_name = m.name.replace('"', '\\"')
                data_path = f'data.shape_keys.key_blocks["{morph_name}"].value'
                scale_path = f'mmd_root.uv_morphs["{morph_name}"].vertex_group_scale'
                name_bind = f"mmd_bind{hash(m.name)}"
                b = FnBone.set_edit_bone_to_dummy(__get_bone(name_bind, ctrl_base))
                groups = []
                uv_morph_map.setdefault(name_bind, []).append((b.name, data_path, scale_path, groups))
                group_map.setdefault(("uv_morphs", m.name), []).append(groups)

            used_bone_names = bone_offset_map.keys() | uv_morph_map.keys()
            used_bone_names.add(ctrl_base.name)
            for b in edit_bones:  # cleanup
                if b.name.startswith("mmd_bind") and b.name not in used_bone_names:
                    edit_bones.remove(b)

        material_offset_map = {}
        for m in mmd_root.material_morphs:
            morph_name = m.name.replace('"', '\\"')
            data_path = f'data.shape_keys.key_blocks["{morph_name}"].value'
            groups = []
            group_map.setdefault(("material_morphs", m.name), []).append(groups)
            material_offset_map.setdefault("group_dict", {})[m.name] = (data_path, groups)
            for d in m.data:
                d.name = name_bind = f"mmd_bind{hash(d)}"
                # add '#' before material name to avoid conflict with group_dict
                table = material_offset_map.setdefault("#" + d.material, ([], []))
                table[1 if d.offset_type == "ADD" else 0].append((m.name, d, name_bind))

        for m in mmd_root.group_morphs:
            if len(m.data) != len(set(m.data.keys())):
                logging.warning(' * Found duplicated morph data in Group Morph "%s"', m.name)
            morph_name = m.name.replace('"', '\\"')
            morph_path = f'data.shape_keys.key_blocks["{morph_name}"].value'
            for d in m.data:
                data_name = d.name.replace('"', '\\"')
                factor_path = f'mmd_root.group_morphs["{morph_name}"].data["{data_name}"].factor'
                for groups in group_map.get((d.morph_type, d.name), ()):
                    groups.append((m.name, morph_path, factor_path))

        self.__cleanup(shape_key_map.keys() | bone_offset_map.keys() | uv_morph_map.keys())

        def __config_groups(variables, expression, groups):
            for g_name, morph_path, factor_path in groups:
                var = self.__add_single_prop(variables, placeholder_mesh_object, morph_path, "g")
                fvar = self.__add_single_prop(variables, root_object, factor_path, "w")
                expression = f"{expression}+{var.name}*{fvar.name}"
            return expression

        # vertex morphs
        for kb_bind, morph_data_path, groups in (i for l in shape_key_map.values() for i in l):
            driver, variables = self.__driver_variables(kb_bind, "value")
            var = self.__add_single_prop(variables, placeholder_mesh_object, morph_data_path, "v")
            if kb_bind.name.startswith("mmd_bind"):
                driver.expression = f"-({__config_groups(variables, var.name, groups)})"
                kb_bind.relative_key.mute = True
            else:
                driver.expression = __config_groups(variables, var.name, groups)
            kb_bind.mute = False

        # bone morphs
        def __config_bone_morph(constraints, map_type, attributes, val, val_str):
            c_name = f"mmd_bind{hash(data)}.{map_type[:3]}"
            c = TransformConstraintOp.create(constraints, c_name, map_type)
            TransformConstraintOp.update_min_max(c, val, None)
            c.show_expanded = False
            c.target = placeholder_armature_object
            c.subtarget = bname
            for attr in attributes:
                driver, variables = self.__driver_variables(armature_object, c.path_from_id(attr))
                var = self.__add_single_prop(variables, placeholder_mesh_object, morph_data_path, "b")
                expression = __config_groups(variables, var.name, groups)
                sign = "-" if attr.startswith("to_min") else ""
                driver.expression = f"{sign}{val_str}*({expression})"

        attributes_rot = TransformConstraintOp.min_max_attributes("ROTATION", "to")
        attributes_loc = TransformConstraintOp.min_max_attributes("LOCATION", "to")
        for morph_name, data, bname, morph_data_path, groups in bone_offset_map.values():
            b = placeholder_armature_object.pose.bones[bname]
            b.location = data.location
            b.rotation_quaternion = data.rotation.__class__(*data.rotation.to_axis_angle())  # Fix for consistency
            b.is_mmd_shadow_bone = True
            b.mmd_shadow_bone_type = "BIND"
            pb = armature_object.pose.bones[data.bone]
            __config_bone_morph(pb.constraints, "ROTATION", attributes_rot, math.pi, "pi")
            __config_bone_morph(pb.constraints, "LOCATION", attributes_loc, 100, "100")

        # uv morphs
        # HACK: workaround for Blender 2.80+, data_path can't be properly detected (Save & Reopen file also works)
        root_object.parent, root_object.parent, root_object.matrix_parent_inverse = placeholder_armature_object, root_object.parent, root_object.matrix_parent_inverse.copy()
        b = placeholder_armature_object.pose.bones["mmd_bind_ctrl_base"]
        b.is_mmd_shadow_bone = True
        b.mmd_shadow_bone_type = "BIND"
        for bname, data_path, scale_path, groups in (i for l in uv_morph_map.values() for i in l):
            b = placeholder_armature_object.pose.bones[bname]
            b.is_mmd_shadow_bone = True
            b.mmd_shadow_bone_type = "BIND"
            driver, variables = self.__driver_variables(b, "location", index=0)
            var = self.__add_single_prop(variables, placeholder_mesh_object, data_path, "u")
            fvar = self.__add_single_prop(variables, root_object, scale_path, "s")
            driver.expression = f"({__config_groups(variables, var.name, groups)})*{fvar.name}"

        # material morphs
        from .shader import _MaterialMorph

        group_dict = material_offset_map.get("group_dict", {})

        def __config_material_morph(mat, morph_list):
            nodes = _MaterialMorph.setup_morph_nodes(mat, tuple(x[1] for x in morph_list))
            for (morph_name, data, name_bind), node in zip(morph_list, nodes):
                node.label, node.name = morph_name, name_bind
                data_path, groups = group_dict[morph_name]
                driver, variables = self.__driver_variables(mat.node_tree, node.inputs[0].path_from_id("default_value"))
                var = self.__add_single_prop(variables, placeholder_mesh_object, data_path, "m")
                driver.expression = "%s" % __config_groups(variables, var.name, groups)

        for mat in (m for m in rig.materials() if m and m.use_nodes and not m.name.startswith("mmd_")):
            mul_all, add_all = material_offset_map.get("#", ([], []))
            if mat.name == "":
                logging.warning("Oh no. The material name should never empty.")
                mul_list, add_list = [], []
            else:
                mat_name = "#" + mat.name
                mul_list, add_list = material_offset_map.get(mat_name, ([], []))
            morph_list = tuple(mul_all + mul_list + add_all + add_list)
            __config_material_morph(mat, morph_list)
            mat_edge = bpy.data.materials.get("mmd_edge." + mat.name, None)
            if mat_edge:
                __config_material_morph(mat_edge, morph_list)

        morph_sliders[0].mute = False
