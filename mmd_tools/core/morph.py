# -*- coding: utf-8 -*-
# Copyright 2016 MMD Tools authors
# This file is part of MMD Tools.

import logging
import re
from typing import TYPE_CHECKING, Tuple, cast

import bpy

from .. import bpyutils
from ..bpyutils import FnContext, FnObject, TransformConstraintOp

if TYPE_CHECKING:
    from .model import Model


class FnMorph:
    def __init__(self, morph, model: "Model"):
        self.__morph = morph
        self.__rig = model

    @classmethod
    def storeShapeKeyOrder(cls, obj, shape_key_names):
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

    @classmethod
    def fixShapeKeyOrder(cls, obj, shape_key_names):
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
    def get_morph_slider(rig):
        return _MorphSlider(rig)

    @staticmethod
    def category_guess(morph):
        name_lower = morph.name.lower()
        if "mouth" in name_lower:
            morph.category = "MOUTH"
        elif "eye" in name_lower:
            if "brow" in name_lower:
                morph.category = "EYEBROW"
            else:
                morph.category = "EYE"

    @classmethod
    def load_morphs(cls, rig):
        mmd_root = rig.rootObject().mmd_root
        vertex_morphs = mmd_root.vertex_morphs
        uv_morphs = mmd_root.uv_morphs
        for obj in rig.meshes():
            for kb in getattr(obj.data.shape_keys, "key_blocks", ())[1:]:
                if not kb.name.startswith("mmd_") and kb.name not in vertex_morphs:
                    item = vertex_morphs.add()
                    item.name = kb.name
                    item.name_e = kb.name
                    cls.category_guess(item)
            for g, name, x in FnMorph.get_uv_morph_vertex_groups(obj):
                if name not in uv_morphs:
                    item = uv_morphs.add()
                    item.name = item.name_e = name
                    item.data_type = "VERTEX_GROUP"
                    cls.category_guess(item)

    @staticmethod
    def remove_shape_key(mesh_object: bpy.types.Object, shape_key_name: str):
        assert isinstance(mesh_object.data, bpy.types.Mesh)

        shape_keys = mesh_object.data.shape_keys
        if shape_keys is None:
            return

        key_blocks = shape_keys.key_blocks
        if key_blocks and shape_key_name in key_blocks:
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
    def get_uv_morph_vertex_groups(obj, morph_name=None, offset_axes="XYZW"):
        pattern = "UV_%s[+-][%s]$" % (morph_name or ".{1,}", offset_axes or "XYZW")
        # yield (vertex_group, morph_name, axis),...
        return ((g, g.name[3:-2], g.name[-2:]) for g in obj.vertex_groups if re.match(pattern, g.name))

    @staticmethod
    def copy_uv_morph_vertex_groups(obj, src_name, dest_name):
        for vg, n, x in FnMorph.get_uv_morph_vertex_groups(obj, dest_name):
            obj.vertex_groups.remove(vg)

        for vg_name in tuple(i[0].name for i in FnMorph.get_uv_morph_vertex_groups(obj, src_name)):
            obj.vertex_groups.active = obj.vertex_groups[vg_name]
            with bpy.context.temp_override(object=obj, window=bpy.context.window, region=bpy.context.region):
                bpy.ops.object.vertex_group_copy()
            obj.vertex_groups.active.name = vg_name.replace(src_name, dest_name)

    @staticmethod
    def overwrite_bone_morphs_from_pose_library(armature_object):
        armature = armature_object.id_data
        pose_library = armature.pose_library

        if pose_library is None:
            return

        root = armature_object.parent
        mmd_root = root.mmd_root
        bone_morphs = mmd_root.bone_morphs

        original_mode = bpy.context.object.mode
        bpy.ops.object.mode_set(mode="POSE")
        try:
            for index, pose_maker in enumerate(pose_library.pose_markers):
                bone_morph = next(iter([m for m in bone_morphs if m.name == pose_maker.name]), None)
                if bone_morph is None:
                    bone_morph = bone_morphs.add()
                    bone_morph.name = pose_maker.name

                bpy.ops.pose.select_all(action="SELECT")
                bpy.ops.pose.transforms_clear()
                bpy.ops.poselib.apply_pose(pose_index=index)

                mmd_root.active_morph = bone_morphs.find(bone_morph.name)
                bpy.ops.mmd_tools.apply_bone_morph()

            bpy.ops.pose.transforms_clear()

        finally:
            bpy.ops.object.mode_set(mode=original_mode)

    @staticmethod
    def clean_uv_morph_vertex_groups(obj):
        # remove empty vertex groups of uv morphs
        vg_indices = {g.index for g, n, x in FnMorph.get_uv_morph_vertex_groups(obj)}
        vertex_groups = obj.vertex_groups
        for v in obj.data.vertices:
            for x in v.groups:
                if x.group in vg_indices and x.weight > 0:
                    vg_indices.remove(x.group)
        for i in sorted(vg_indices, reverse=True):
            vg = vertex_groups[i]
            m = obj.modifiers.get("mmd_bind%s" % hash(vg.name), None)
            if m:
                obj.modifiers.remove(m)
            vertex_groups.remove(vg)

    @staticmethod
    def get_uv_morph_offset_map(obj, morph):
        offset_map = {}  # offset_map[vertex_index] = offset_xyzw
        if morph.data_type == "VERTEX_GROUP":
            scale = morph.vertex_group_scale
            axis_map = {g.index: x for g, n, x in FnMorph.get_uv_morph_vertex_groups(obj, morph.name)}
            for v in obj.data.vertices:
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
            for vg, n, x in FnMorph.get_uv_morph_vertex_groups(obj, morph_name, offset_axes):
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
                if abs(val) > 1e-4:
                    vg_name = "UV_{0}{1}{2}".format(morph_name, "-" if val < 0 else "+", axis)
                    vg = vertex_groups.get(vg_name, None) or vertex_groups.new(name=vg_name)
                    vg.add(index=[idx], weight=abs(val) / scale, type="REPLACE")

    def update_mat_related_mesh(self, new_mesh=None):
        for offset in self.__morph.data:
            # Use the new_mesh if provided
            meshObj = new_mesh
            if new_mesh is None:
                # Try to find the mesh by material name
                meshObj = self.__rig.findMesh(offset.material)

            if meshObj is None:
                # Given this point we need to loop through all the meshes
                for mesh in self.__rig.meshes():
                    if mesh.data.materials.find(offset.material) >= 0:
                        meshObj = mesh
                        break

            # Finally update the reference
            if meshObj is not None:
                offset.related_mesh = meshObj.data.name

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


class _MorphSlider:
    def __init__(self, model: "Model"):
        self.__rig = model

    def placeholder(self, create=False, binded=False):
        rig = self.__rig
        root = rig.rootObject()
        obj = next((x for x in root.children if x.mmd_type == "PLACEHOLDER" and x.type == "MESH"), None)
        if create and obj is None:
            obj = bpy.data.objects.new(name=".placeholder", object_data=bpy.data.meshes.new(".placeholder"))
            obj.mmd_type = "PLACEHOLDER"
            obj.parent = root
            FnContext.link_object(FnContext.ensure_context(), obj)
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

    def __dummy_armature(self, obj, create=False):
        arm = next((x for x in obj.children if x.mmd_type == "PLACEHOLDER" and x.type == "ARMATURE"), None)
        if create and arm is None:
            arm = bpy.data.objects.new(name=".dummy_armature", object_data=bpy.data.armatures.new(name=".dummy_armature"))
            arm.mmd_type = "PLACEHOLDER"
            arm.parent = obj
            FnContext.link_object(FnContext.ensure_context(), arm)

            from .bone import FnBone

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

    def create(self):
        self.__rig.loadMorphs()
        obj = self.placeholder(create=True)
        self.__load(obj, self.__rig.rootObject().mmd_root)
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
        from math import ceil, floor

        names_in_use = names_in_use or {}
        rig = self.__rig
        morph_sliders = self.placeholder()
        morph_sliders = morph_sliders.data.shape_keys.key_blocks if morph_sliders else {}
        for mesh_object in rig.meshes():
            for kb in getattr(mesh_object.data.shape_keys, "key_blocks", cast(Tuple[bpy.types.ShapeKey], ())):
                if kb.name in names_in_use:
                    continue

                if kb.name.startswith("mmd_bind"):
                    kb.driver_remove("value")
                    ms = morph_sliders[kb.relative_key.name]
                    kb.relative_key.slider_min, kb.relative_key.slider_max = min(ms.slider_min, floor(ms.value)), max(ms.slider_max, ceil(ms.value))
                    kb.relative_key.value = ms.value
                    kb.relative_key.mute = False
                    FnObject.mesh_remove_shape_key(mesh_object, kb)

                elif kb.name in morph_sliders and self.__shape_key_driver_check(kb):
                    ms = morph_sliders[kb.name]
                    kb.driver_remove("value")
                    kb.slider_min, kb.slider_max = min(ms.slider_min, floor(kb.value)), max(ms.slider_max, ceil(kb.value))

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
        mmd_root = self.__rig.rootObject().mmd_root

        # after unbind, the weird lag problem will disappear.
        mmd_root.morph_panel_show_settings = True

        for m in mmd_root.bone_morphs:
            for d in m.data:
                d.name = ""
        for m in mmd_root.material_morphs:
            for d in m.data:
                d.name = ""
        obj = self.placeholder()
        if obj:
            obj.data.shape_keys.key_blocks[0].mute = True
            arm = self.__dummy_armature(obj)
            if arm:
                for b in arm.pose.bones:
                    if b.name.startswith("mmd_bind"):
                        b.driver_remove("location")
                        b.driver_remove("rotation_quaternion")
        self.__cleanup()

    def bind(self):
        rig = self.__rig
        root = rig.rootObject()
        armObj = rig.armature()
        mmd_root = root.mmd_root

        # hide detail to avoid weird lag problem
        mmd_root.morph_panel_show_settings = False

        obj = self.create()
        arm = self.__dummy_armature(obj, create=True)
        morph_sliders = obj.data.shape_keys.key_blocks

        # data gathering
        group_map = {}

        shape_key_map = {}
        uv_morph_map = {}
        for mesh_object in rig.meshes():
            mesh_object.show_only_shape_key = False
            key_blocks = getattr(mesh_object.data.shape_keys, "key_blocks", ())
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
            for vg, morph_name, axis in FnMorph.get_uv_morph_vertex_groups(mesh_object):
                morph = mmd_root.uv_morphs.get(morph_name, None)
                if morph is None or morph.data_type != "VERTEX_GROUP":
                    continue

                uv_layer = "_" + uv_layers[morph.uv_index] if axis[1] in "ZW" else uv_layers[morph.uv_index]
                if uv_layer not in mesh_object.data.uv_layers:
                    continue

                name_bind = "mmd_bind%s" % hash(vg.name)
                uv_morph_map.setdefault(name_bind, ())
                mod = mesh_object.modifiers.get(name_bind, None) or mesh_object.modifiers.new(name=name_bind, type="UV_WARP")
                mod.show_expanded = False
                mod.vertex_group = vg.name
                mod.axis_u, mod.axis_v = ("Y", "X") if axis[1] in "YW" else ("X", "Y")
                mod.uv_layer = uv_layer
                name_bind = "mmd_bind%s" % hash(morph_name)
                mod.object_from = mod.object_to = arm
                if axis[0] == "-":
                    mod.bone_from, mod.bone_to = "mmd_bind_ctrl_base", name_bind
                else:
                    mod.bone_from, mod.bone_to = name_bind, "mmd_bind_ctrl_base"

        bone_offset_map = {}
        with bpyutils.edit_object(arm) as data:
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
                var = self.__add_single_prop(variables, obj, morph_path, "g")
                fvar = self.__add_single_prop(variables, root, factor_path, "w")
                expression = f"{expression}+{var.name}*{fvar.name}"
            return expression

        # vertex morphs
        for kb_bind, morph_data_path, groups in (i for l in shape_key_map.values() for i in l):
            driver, variables = self.__driver_variables(kb_bind, "value")
            var = self.__add_single_prop(variables, obj, morph_data_path, "v")
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
            c.target = arm
            c.subtarget = bname
            for attr in attributes:
                driver, variables = self.__driver_variables(armObj, c.path_from_id(attr))
                var = self.__add_single_prop(variables, obj, morph_data_path, "b")
                expression = __config_groups(variables, var.name, groups)
                sign = "-" if attr.startswith("to_min") else ""
                driver.expression = f"{sign}{val_str}*({expression})"

        from math import pi

        attributes_rot = TransformConstraintOp.min_max_attributes("ROTATION", "to")
        attributes_loc = TransformConstraintOp.min_max_attributes("LOCATION", "to")
        for morph_name, data, bname, morph_data_path, groups in bone_offset_map.values():
            b = arm.pose.bones[bname]
            b.location = data.location
            b.rotation_quaternion = data.rotation.__class__(*data.rotation.to_axis_angle())  # Fix for consistency
            b.is_mmd_shadow_bone = True
            b.mmd_shadow_bone_type = "BIND"
            pb = armObj.pose.bones[data.bone]
            __config_bone_morph(pb.constraints, "ROTATION", attributes_rot, pi, "pi")
            __config_bone_morph(pb.constraints, "LOCATION", attributes_loc, 100, "100")

        # uv morphs
        # HACK: workaround for Blender 2.80+, data_path can't be properly detected (Save & Reopen file also works)
        root.parent, root.parent, root.matrix_parent_inverse = arm, root.parent, root.matrix_parent_inverse.copy()
        b = arm.pose.bones["mmd_bind_ctrl_base"]
        b.is_mmd_shadow_bone = True
        b.mmd_shadow_bone_type = "BIND"
        for bname, data_path, scale_path, groups in (i for l in uv_morph_map.values() for i in l):
            b = arm.pose.bones[bname]
            b.is_mmd_shadow_bone = True
            b.mmd_shadow_bone_type = "BIND"
            driver, variables = self.__driver_variables(b, "location", index=0)
            var = self.__add_single_prop(variables, obj, data_path, "u")
            fvar = self.__add_single_prop(variables, root, scale_path, "s")
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
                var = self.__add_single_prop(variables, obj, data_path, "m")
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
