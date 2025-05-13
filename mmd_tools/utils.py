# Copyright 2012 MMD Tools authors
# This file is part of MMD Tools.

import logging
import os
import re
from typing import Callable, Optional, Set

import bpy

from .bpyutils import FnContext


## 指定したオブジェクトのみを選択状態かつアクティブにする
def selectAObject(obj):
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass
    bpy.ops.object.select_all(action="DESELECT")
    FnContext.select_object(FnContext.ensure_context(), obj)
    FnContext.set_active_object(FnContext.ensure_context(), obj)


## 現在のモードを指定したオブジェクトのEdit Modeに変更する
def enterEditMode(obj):
    selectAObject(obj)
    if obj.mode != "EDIT":
        bpy.ops.object.mode_set(mode="EDIT")


def setParentToBone(obj, parent, bone_name):
    selectAObject(obj)
    FnContext.set_active_object(FnContext.ensure_context(), parent)
    bpy.ops.object.mode_set(mode="POSE")
    parent.data.bones.active = parent.data.bones[bone_name]
    bpy.ops.object.parent_set(type="BONE", xmirror=False, keep_transform=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def selectSingleBone(context, armature, bone_name, reset_pose=False):
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
    except:
        pass
    for i in context.selected_objects:
        i.select_set(False)
    FnContext.set_active_object(context, armature)
    bpy.ops.object.mode_set(mode="POSE")
    if reset_pose:
        for p_bone in armature.pose.bones:
            p_bone.matrix_basis.identity()
    armature_bones: bpy.types.ArmatureBones = armature.data.bones
    i: bpy.types.Bone
    for i in armature_bones:
        i.select = i.name == bone_name
        i.select_head = i.select_tail = i.select
        if i.select:
            armature_bones.active = i
            i.hide = False


__CONVERT_NAME_TO_L_REGEXP = re.compile("^(.*)左(.*)$")
__CONVERT_NAME_TO_R_REGEXP = re.compile("^(.*)右(.*)$")


## 日本語で左右を命名されている名前をblender方式のL(R)に変更する
def convertNameToLR(name, use_underscore=False):
    m = __CONVERT_NAME_TO_L_REGEXP.match(name)
    delimiter = "_" if use_underscore else "."
    if m:
        name = m.group(1) + m.group(2) + delimiter + "L"
    m = __CONVERT_NAME_TO_R_REGEXP.match(name)
    if m:
        name = m.group(1) + m.group(2) + delimiter + "R"
    return name


__CONVERT_L_TO_NAME_REGEXP = re.compile(r"(?P<lr>(?P<separator>[._])[lL])(?P<after>($|(?P=separator)))")
__CONVERT_R_TO_NAME_REGEXP = re.compile(r"(?P<lr>(?P<separator>[._])[rR])(?P<after>($|(?P=separator)))")


def convertLRToName(name):
    match = __CONVERT_L_TO_NAME_REGEXP.search(name)
    if match:
        return f"左{name[0:match.start()]}{match['after']}{name[match.end():]}"

    match = __CONVERT_R_TO_NAME_REGEXP.search(name)
    if match:
        return f"右{name[0:match.start()]}{match['after']}{name[match.end():]}"

    return name


## src_vertex_groupのWeightをdest_vertex_groupにaddする
def mergeVertexGroup(meshObj, src_vertex_group_name, dest_vertex_group_name):
    mesh = meshObj.data
    src_vertex_group = meshObj.vertex_groups[src_vertex_group_name]
    dest_vertex_group = meshObj.vertex_groups[dest_vertex_group_name]

    vtxIndex = src_vertex_group.index
    for v in mesh.vertices:
        try:
            gi = [i.group for i in v.groups].index(vtxIndex)
            dest_vertex_group.add([v.index], v.groups[gi].weight, "ADD")
        except ValueError:
            pass


def separateByMaterials(meshObj: bpy.types.Object):
    if len(meshObj.data.materials) < 2:
        selectAObject(meshObj)
        return
    matrix_parent_inverse = meshObj.matrix_parent_inverse.copy()
    prev_parent = meshObj.parent
    dummy_parent = bpy.data.objects.new(name="tmp", object_data=None)
    meshObj.parent = dummy_parent
    meshObj.active_shape_key_index = 0
    try:
        enterEditMode(meshObj)
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.separate(type="MATERIAL")
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    for i in dummy_parent.children:
        materials = i.data.materials
        i.name = getattr(materials[0], "name", "None") if len(materials) else "None"
        i.parent = prev_parent
        i.matrix_parent_inverse = matrix_parent_inverse
    bpy.data.objects.remove(dummy_parent)


def clearUnusedMeshes():
    meshes_to_delete = []
    for mesh in bpy.data.meshes:
        if mesh.users == 0:
            meshes_to_delete.append(mesh)

    for mesh in meshes_to_delete:
        bpy.data.meshes.remove(mesh)


## Boneのカスタムプロパティにname_jが存在する場合、name_jの値を
# それ以外の場合は通常のbone名をキーとしたpose_boneへの辞書を作成
def makePmxBoneMap(armObj):
    # Maintain backward compatibility with mmd_tools v0.4.x or older.
    return {(i.mmd_bone.name_j or i.get("mmd_bone_name_j", i.get("name_j", i.name))): i for i in armObj.pose.bones}


__REMOVE_PREFIX_DIGITS_REGEXP = re.compile(r"\.\d{1,}$")


def unique_name(name: str, used_names: Set[str]) -> str:
    """Helper function for storing unique names.
    This function is a limited and simplified version of bpy_extras.io_utils.unique_name.

    Args:
        name (str): The name to make unique.
        used_names (Set[str]): A set of names that are already used.

    Returns:
        str: The unique name, formatted as "{name}.{number:03d}".
    """
    if name not in used_names:
        return name
    count = 1
    new_name = orig_name = __REMOVE_PREFIX_DIGITS_REGEXP.sub("", name)
    while new_name in used_names:
        new_name = f"{orig_name}.{count:03d}"
        count += 1
    return new_name


def int2base(x, base, width=0):
    """
    Method to convert an int to a base
    Source: http://stackoverflow.com/questions/2267362
    """
    import string

    digs = string.digits + string.ascii_uppercase
    assert 2 <= base <= len(digs)
    digits, negtive = "", False
    if x <= 0:
        if x == 0:
            return "0" * max(1, width)
        x, negtive, width = -x, True, width - 1
    while x:
        digits = digs[x % base] + digits
        x //= base
    digits = "0" * (width - len(digits)) + digits
    if negtive:
        digits = "-" + digits
    return digits


def saferelpath(path, start, strategy="inside"):
    """
    On Windows relpath will raise a ValueError
    when trying to calculate the relative path to a
    different drive.
    This method will behave different depending on the strategy
    choosen to handle the different drive issue.
    Strategies:
    - inside: this will just return the basename of the path given
    - outside: this will prepend '..' to the basename
    - absolute: this will return the absolute path instead of a relative.
    See http://bugs.python.org/issue7195
    """
    if strategy == "inside":
        return os.path.basename(path)

    if strategy == "absolute":
        return os.path.abspath(path)

    if strategy == "outside" and os.name == "nt":
        d1, _ = os.path.splitdrive(path)
        d2, _ = os.path.splitdrive(start)
        if d1 != d2:
            return ".." + os.sep + os.path.basename(path)

    return os.path.relpath(path, start)

class ItemOp:
    @staticmethod
    def get_by_index(items, index):
        if 0 <= index < len(items):
            return items[index]
        return None

    @staticmethod
    def resize(items: bpy.types.bpy_prop_collection, length: int):
        count = length - len(items)
        if count > 0:
            for i in range(count):
                items.add()
        elif count < 0:
            for i in range(-count):
                items.remove(length)

    @staticmethod
    def add_after(items, index):
        index_end = len(items)
        index = max(0, min(index_end, index + 1))
        items.add()
        items.move(index_end, index)
        return items[index], index


class ItemMoveOp:
    type: bpy.props.EnumProperty(
        name="Type",
        description="Move type",
        items=[
            ("UP", "Up", "", 0),
            ("DOWN", "Down", "", 1),
            ("TOP", "Top", "", 2),
            ("BOTTOM", "Bottom", "", 3),
        ],
        default="UP",
    )

    @staticmethod
    def move(items, index, move_type, index_min=0, index_max=None):
        if index_max is None:
            index_max = len(items) - 1
        else:
            index_max = min(index_max, len(items) - 1)
        index_min = min(index_min, index_max)

        if index < index_min:
            items.move(index, index_min)
            return index_min
        elif index > index_max:
            items.move(index, index_max)
            return index_max

        index_new = index
        if move_type == "UP":
            index_new = max(index_min, index - 1)
        elif move_type == "DOWN":
            index_new = min(index + 1, index_max)
        elif move_type == "TOP":
            index_new = index_min
        elif move_type == "BOTTOM":
            index_new = index_max

        if index_new != index:
            items.move(index, index_new)
        return index_new


def deprecated(deprecated_in: Optional[str] = None, details: Optional[str] = None):
    """Decorator to mark a function as deprecated.
    Args:
        deprecated_in (Optional[str]): Version in which the function was deprecated.
        details (Optional[str]): Additional details about the deprecation.
    Returns:
        Callable: The decorated function.
    """

    def _function_wrapper(function: Callable):
        def _inner_wrapper(*args, **kwargs):
            warn_deprecation(function.__name__, deprecated_in, details)
            return function(*args, **kwargs)

        return _inner_wrapper

    return _function_wrapper


def warn_deprecation(function_name: str, deprecated_in: Optional[str] = None, details: Optional[str] = None) -> None:
    """Reports a deprecation warning.
    Args:
        function_name (str): Name of the deprecated function.
        deprecated_in (Optional[str]): Version in which the function was deprecated.
        details (Optional[str]): Additional details about the deprecation.
    """
    logging.warning(
        "%s is deprecated%s%s",
        function_name,
        f" since {deprecated_in}" if deprecated_in else "",
        f": {details}" if details else "",
        stack_info=True,
        stacklevel=4,
    )

    # import warnings  # pylint: disable=import-outside-toplevel

    # warnings.warn(f"""{function_name}is deprecated{f" since {deprecated_in}" if deprecated_in else ""}{f": {details}" if details else ""}""", category=DeprecationWarning, stacklevel=2)
