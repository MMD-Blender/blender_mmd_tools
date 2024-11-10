# -*- coding: utf-8 -*-
# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

"""Properties for MMD model root object"""

import bpy

from .. import utils
from ..bpyutils import FnContext
from ..core.material import FnMaterial
from ..core.model import FnModel
from ..core.sdef import FnSDEF
from . import patch_library_overridable
from .morph import BoneMorph, GroupMorph, MaterialMorph, UVMorph, VertexMorph
from .translations import MMDTranslation


def __driver_variables(constraint: bpy.types.Constraint, path: str, index=-1):
    d = constraint.driver_add(path, index)
    variables = d.driver.variables
    for x in variables:
        variables.remove(x)
    return d.driver, variables


def __add_single_prop(variables, id_obj, data_path, prefix):
    var = variables.new()
    var.name = prefix + str(len(variables))
    var.type = "SINGLE_PROP"
    target = var.targets[0]
    target.id_type = "OBJECT"
    target.id = id_obj
    target.data_path = data_path
    return var


def _toggleUsePropertyDriver(self: "MMDRoot", _context):
    root_object: bpy.types.Object = self.id_data
    armature_object = FnModel.find_armature_object(root_object)

    if armature_object is None:
        ik_map = {}
    else:
        bones = armature_object.pose.bones
        ik_map = {bones[c.subtarget]: (b, c) for b in bones for c in b.constraints if c.type == "IK" and c.is_valid and c.subtarget in bones}

    if self.use_property_driver:
        for ik, (b, c) in ik_map.items():
            driver, variables = __driver_variables(c, "influence")
            driver.expression = "%s" % __add_single_prop(variables, ik.id_data, ik.path_from_id("mmd_ik_toggle"), "use_ik").name
            b = b if c.use_tail else b.parent
            for b in ([b] + b.parent_recursive)[: c.chain_count]:
                c = next((c for c in b.constraints if c.type == "LIMIT_ROTATION" and not c.mute), None)
                if c:
                    driver, variables = __driver_variables(c, "influence")
                    driver.expression = "%s" % __add_single_prop(variables, ik.id_data, ik.path_from_id("mmd_ik_toggle"), "use_ik").name
        for i in FnModel.iterate_mesh_objects(root_object):
            for prop_hide in ("hide_viewport", "hide_render"):
                driver, variables = __driver_variables(i, prop_hide)
                driver.expression = "not %s" % __add_single_prop(variables, root_object, "mmd_root.show_meshes", "show").name
    else:
        for ik, (b, c) in ik_map.items():
            c.driver_remove("influence")
            b = b if c.use_tail else b.parent
            for b in ([b] + b.parent_recursive)[: c.chain_count]:
                c = next((c for c in b.constraints if c.type == "LIMIT_ROTATION" and not c.mute), None)
                if c:
                    c.driver_remove("influence")
        for i in FnModel.iterate_mesh_objects(root_object):
            for prop_hide in ("hide_viewport", "hide_render"):
                i.driver_remove(prop_hide)


# ===========================================
# Callback functions
# ===========================================


def _toggleUseToonTexture(self: "MMDRoot", _context):
    use_toon = self.use_toon_texture
    for i in FnModel.iterate_mesh_objects(self.id_data):
        for m in i.data.materials:
            if m:
                FnMaterial(m).use_toon_texture(use_toon)


def _toggleUseSphereTexture(self: "MMDRoot", _context):
    use_sphere = self.use_sphere_texture
    for i in FnModel.iterate_mesh_objects(self.id_data):
        for m in i.data.materials:
            if m:
                FnMaterial(m).use_sphere_texture(use_sphere, i)


def _toggleUseSDEF(self: "MMDRoot", _context):
    mute_sdef = not self.use_sdef
    for i in FnModel.iterate_mesh_objects(self.id_data):
        FnSDEF.mute_sdef_set(i, mute_sdef)


def _toggleVisibilityOfMeshes(self: "MMDRoot", context: bpy.types.Context):
    root = self.id_data
    hide = not self.show_meshes
    for i in FnModel.iterate_mesh_objects(self.id_data):
        i.hide_set(hide)
        i.hide_render = hide
    if hide and context.active_object is None:
        FnContext.set_active_object(context, root)


def _toggleVisibilityOfRigidBodies(self: "MMDRoot", context: bpy.types.Context):
    root = self.id_data
    hide = not self.show_rigid_bodies
    for i in FnModel.iterate_rigid_body_objects(root):
        i.hide_set(hide)
    if hide and context.active_object is None:
        FnContext.set_active_object(context, root)


def _toggleVisibilityOfJoints(self: "MMDRoot", context):
    root_object = self.id_data
    hide = not self.show_joints
    for i in FnModel.iterate_joint_objects(root_object):
        i.hide_set(hide)
    if hide and context.active_object is None:
        FnContext.set_active_object(context, root_object)


def _toggleVisibilityOfTemporaryObjects(self: "MMDRoot", context: bpy.types.Context):
    root_object: bpy.types.Object = self.id_data
    hide = not self.show_temporary_objects
    with FnContext.temp_override_active_layer_collection(context, root_object):
        for i in FnModel.iterate_temporary_objects(root_object):
            i.hide_set(hide)
    if hide and context.active_object is None:
        FnContext.set_active_object(context, root_object)


def _toggleShowNamesOfRigidBodies(self: "MMDRoot", _context):
    root = self.id_data
    show_names = root.mmd_root.show_names_of_rigid_bodies
    for i in FnModel.iterate_rigid_body_objects(root):
        i.show_name = show_names


def _toggleShowNamesOfJoints(self: "MMDRoot", _context):
    root = self.id_data
    show_names = root.mmd_root.show_names_of_joints
    for i in FnModel.iterate_joint_objects(root):
        i.show_name = show_names


def _setVisibilityOfMMDRigArmature(prop: "MMDRoot", v: bool):
    root = prop.id_data
    arm = FnModel.find_armature_object(root)
    if arm is None:
        return
    if not v and bpy.context.active_object == arm:
        FnContext.set_active_object(bpy.context, root)
    arm.hide_set(not v)


def _getVisibilityOfMMDRigArmature(prop: "MMDRoot"):
    if prop.id_data.mmd_type != "ROOT":
        return False
    arm = FnModel.find_armature_object(prop.id_data)
    return arm and not arm.hide_get()


def _setActiveRigidbodyObject(prop: "MMDRoot", v: int):
    obj = FnContext.get_scene_objects(bpy.context)[v]
    if FnModel.is_rigid_body_object(obj):
        FnContext.set_active_and_select_single_object(bpy.context, obj)
    prop["active_rigidbody_object_index"] = v


def _getActiveRigidbodyObject(prop: "MMDRoot"):
    context = bpy.context
    active_obj = FnContext.get_active_object(context)
    if FnModel.is_rigid_body_object(active_obj):
        prop["active_rigidbody_object_index"] = FnContext.get_scene_objects(context).find(active_obj.name)
    return prop.get("active_rigidbody_object_index", 0)


def _setActiveJointObject(prop: "MMDRoot", v: int):
    obj = FnContext.get_scene_objects(bpy.context)[v]
    if FnModel.is_joint_object(obj):
        FnContext.set_active_and_select_single_object(bpy.context, obj)
    prop["active_joint_object_index"] = v


def _getActiveJointObject(prop: "MMDRoot"):
    context = bpy.context
    active_obj = FnContext.get_active_object(context)
    if FnModel.is_joint_object(active_obj):
        prop["active_joint_object_index"] = FnContext.get_scene_objects(context).find(active_obj.name)
    return prop.get("active_joint_object_index", 0)


def _setActiveMorph(prop: "MMDRoot", v: bool):
    if "active_morph_indices" not in prop:
        prop["active_morph_indices"] = [0] * 5
    prop["active_morph_indices"][prop.get("active_morph_type", 3)] = v


def _getActiveMorph(prop: "MMDRoot"):
    if "active_morph_indices" in prop:
        return prop["active_morph_indices"][prop.get("active_morph_type", 3)]
    return 0


def _setActiveMeshObject(prop: "MMDRoot", v: int):
    obj = FnContext.get_scene_objects(bpy.context)[v]
    if FnModel.is_mesh_object(obj):
        FnContext.set_active_and_select_single_object(bpy.context, obj)
    prop["active_mesh_index"] = v


def _getActiveMeshObject(prop: "MMDRoot"):
    context = bpy.context
    active_obj = FnContext.get_active_object(context)
    if FnModel.is_mesh_object(active_obj):
        prop["active_mesh_index"] = FnContext.get_scene_objects(context).find(active_obj.name)
    return prop.get("active_mesh_index", -1)


# ===========================================
# Property classes
# ===========================================


class MMDDisplayItem(bpy.types.PropertyGroup):
    """PMX 表示項目(表示枠内の1項目)"""

    type: bpy.props.EnumProperty(
        name="Type",
        description="Select item type",
        items=[
            ("BONE", "Bone", "", 1),
            ("MORPH", "Morph", "", 2),
        ],
    )

    morph_type: bpy.props.EnumProperty(
        name="Morph Type",
        description="Select morph type",
        items=[
            ("material_morphs", "Material", "Material Morphs", 0),
            ("uv_morphs", "UV", "UV Morphs", 1),
            ("bone_morphs", "Bone", "Bone Morphs", 2),
            ("vertex_morphs", "Vertex", "Vertex Morphs", 3),
            ("group_morphs", "Group", "Group Morphs", 4),
        ],
        default="vertex_morphs",
    )


class MMDDisplayItemFrame(bpy.types.PropertyGroup):
    """PMX 表示枠

    PMXファイル内では表示枠がリストで格納されています。
    """

    name_e: bpy.props.StringProperty(
        name="Name(Eng)",
        description="English Name",
        default="",
    )

    # 特殊枠フラグ
    # 特殊枠はファイル仕様上の固定枠(削除、リネーム不可)
    is_special: bpy.props.BoolProperty(
        name="Special",
        description="Is special",
        default=False,
    )

    # 表示項目のリスト
    data: bpy.props.CollectionProperty(
        name="Display Items",
        type=MMDDisplayItem,
    )

    # 現在アクティブな項目のインデックス
    active_item: bpy.props.IntProperty(
        name="Active Display Item",
        min=0,
        default=0,
    )


class MMDRoot(bpy.types.PropertyGroup):
    """MMDモデルデータ

    モデルルート用に作成されたEmtpyオブジェクトで使用します
    """

    name: bpy.props.StringProperty(
        name="Name",
        description="The name of the MMD model",
        default="",
    )

    name_e: bpy.props.StringProperty(
        name="Name (English)",
        description="The english name of the MMD model",
        default="",
    )

    comment_text: bpy.props.StringProperty(
        name="Comment",
        description="The text datablock of the comment",
        default="",
    )

    comment_e_text: bpy.props.StringProperty(
        name="Comment (English)",
        description="The text datablock of the english comment",
        default="",
    )

    ik_loop_factor: bpy.props.IntProperty(
        name="MMD IK Loop Factor",
        description="Scaling factor of MMD IK loop",
        min=1,
        soft_max=10,
        max=100,
        default=1,
    )

    # TODO: Replace to driver for NLA
    show_meshes: bpy.props.BoolProperty(
        name="Show Meshes",
        description="Show all meshes of the MMD model",
        # get=_show_meshes_get,
        # set=_show_meshes_set,
        update=_toggleVisibilityOfMeshes,
        default=True,
    )

    show_rigid_bodies: bpy.props.BoolProperty(
        name="Show Rigid Bodies",
        description="Show all rigid bodies of the MMD model",
        update=_toggleVisibilityOfRigidBodies,
    )

    show_joints: bpy.props.BoolProperty(
        name="Show Joints",
        description="Show all joints of the MMD model",
        update=_toggleVisibilityOfJoints,
    )

    show_temporary_objects: bpy.props.BoolProperty(
        name="Show Temps",
        description="Show all temporary objects of the MMD model",
        update=_toggleVisibilityOfTemporaryObjects,
    )

    show_armature: bpy.props.BoolProperty(
        name="Show Armature",
        description="Show the armature object of the MMD model",
        get=_getVisibilityOfMMDRigArmature,
        set=_setVisibilityOfMMDRigArmature,
    )

    show_names_of_rigid_bodies: bpy.props.BoolProperty(
        name="Show Rigid Body Names",
        description="Show rigid body names",
        update=_toggleShowNamesOfRigidBodies,
    )

    show_names_of_joints: bpy.props.BoolProperty(
        name="Show Joint Names",
        description="Show joint names",
        update=_toggleShowNamesOfJoints,
    )

    use_toon_texture: bpy.props.BoolProperty(
        name="Use Toon Texture",
        description="Use toon texture",
        update=_toggleUseToonTexture,
        default=True,
    )

    use_sphere_texture: bpy.props.BoolProperty(
        name="Use Sphere Texture",
        description="Use sphere texture",
        update=_toggleUseSphereTexture,
        default=True,
    )

    use_sdef: bpy.props.BoolProperty(
        name="Use SDEF",
        description="Use SDEF",
        update=_toggleUseSDEF,
        default=True,
    )

    use_property_driver: bpy.props.BoolProperty(
        name="Use Property Driver",
        description="Setup drivers for MMD property animation (Visibility and IK toggles)",
        update=_toggleUsePropertyDriver,
        default=False,
    )

    is_built: bpy.props.BoolProperty(
        name="Is Built",
    )

    active_rigidbody_index: bpy.props.IntProperty(
        name="Active Rigidbody Index",
        min=0,
        get=_getActiveRigidbodyObject,
        set=_setActiveRigidbodyObject,
    )

    active_joint_index: bpy.props.IntProperty(
        name="Active Joint Index",
        min=0,
        get=_getActiveJointObject,
        set=_setActiveJointObject,
    )

    # *************************
    # Display Items
    # *************************
    display_item_frames: bpy.props.CollectionProperty(
        name="Display Frames",
        type=MMDDisplayItemFrame,
    )

    active_display_item_frame: bpy.props.IntProperty(
        name="Active Display Item Frame",
        min=0,
        default=0,
    )

    # *************************
    # Morph
    # *************************
    material_morphs: bpy.props.CollectionProperty(
        name="Material Morphs",
        type=MaterialMorph,
    )
    uv_morphs: bpy.props.CollectionProperty(
        name="UV Morphs",
        type=UVMorph,
    )
    bone_morphs: bpy.props.CollectionProperty(
        name="Bone Morphs",
        type=BoneMorph,
    )
    vertex_morphs: bpy.props.CollectionProperty(name="Vertex Morphs", type=VertexMorph)
    group_morphs: bpy.props.CollectionProperty(
        name="Group Morphs",
        type=GroupMorph,
    )
    active_morph_type: bpy.props.EnumProperty(
        name="Active Morph Type",
        description="Select current morph type",
        items=[
            ("material_morphs", "Material", "Material Morphs", 0),
            ("uv_morphs", "UV", "UV Morphs", 1),
            ("bone_morphs", "Bone", "Bone Morphs", 2),
            ("vertex_morphs", "Vertex", "Vertex Morphs", 3),
            ("group_morphs", "Group", "Group Morphs", 4),
        ],
        default="vertex_morphs",
    )
    active_morph: bpy.props.IntProperty(
        name="Active Morph",
        min=0,
        set=_setActiveMorph,
        get=_getActiveMorph,
    )
    morph_panel_show_settings: bpy.props.BoolProperty(
        name="Morph Panel Show Settings",
        description="Show Morph Settings",
        default=True,
    )
    active_mesh_index: bpy.props.IntProperty(
        name="Active Mesh",
        min=0,
        set=_setActiveMeshObject,
        get=_getActiveMeshObject,
    )

    # *************************
    # Translation
    # *************************
    translation: bpy.props.PointerProperty(
        name="Translation",
        type=MMDTranslation,
    )

    @staticmethod
    def __get_select(prop: bpy.types.Object) -> bool:
        utils.warn_deprecation("Object.select", "v4.0.0", "Use Object.select_get() method instead")
        return prop.select_get()

    @staticmethod
    def __set_select(prop: bpy.types.Object, value: bool) -> None:
        utils.warn_deprecation("Object.select", "v4.0.0", "Use Object.select_set() method instead")
        prop.select_set(value)

    @staticmethod
    def __get_hide(prop: bpy.types.Object) -> bool:
        utils.warn_deprecation("Object.hide", "v4.0.0", "Use Object.hide_get() method instead")
        return prop.hide_get()

    @staticmethod
    def __set_hide(prop: bpy.types.Object, value: bool) -> None:
        utils.warn_deprecation("Object.hide", "v4.0.0", "Use Object.hide_set() method instead")
        prop.hide_set(value)
        if prop.hide_viewport != value:
            prop.hide_viewport = value

    @staticmethod
    def register():
        bpy.types.Object.mmd_type = patch_library_overridable(
            bpy.props.EnumProperty(
                name="Type",
                description="Internal MMD type of this object (DO NOT CHANGE IT DIRECTLY)",
                default="NONE",
                items=[
                    ("NONE", "None", "", 1),
                    ("ROOT", "Root", "", 2),
                    ("RIGID_GRP_OBJ", "Rigid Body Grp Empty", "", 3),
                    ("JOINT_GRP_OBJ", "Joint Grp Empty", "", 4),
                    ("TEMPORARY_GRP_OBJ", "Temporary Grp Empty", "", 5),
                    ("PLACEHOLDER", "Place Holder", "", 6),
                    ("CAMERA", "Camera", "", 21),
                    ("JOINT", "Joint", "", 22),
                    ("RIGID_BODY", "Rigid body", "", 23),
                    ("LIGHT", "Light", "", 24),
                    ("TRACK_TARGET", "Track Target", "", 51),
                    ("NON_COLLISION_CONSTRAINT", "Non Collision Constraint", "", 52),
                    ("SPRING_CONSTRAINT", "Spring Constraint", "", 53),
                    ("SPRING_GOAL", "Spring Goal", "", 54),
                ],
            )
        )
        bpy.types.Object.mmd_root = patch_library_overridable(bpy.props.PointerProperty(type=MMDRoot))

        bpy.types.Object.select = patch_library_overridable(
            bpy.props.BoolProperty(
                get=MMDRoot.__get_select,
                set=MMDRoot.__set_select,
                options={
                    "SKIP_SAVE",
                    "ANIMATABLE",
                    "LIBRARY_EDITABLE",
                },
            )
        )
        bpy.types.Object.hide = patch_library_overridable(
            bpy.props.BoolProperty(
                get=MMDRoot.__get_hide,
                set=MMDRoot.__set_hide,
                options={
                    "SKIP_SAVE",
                    "ANIMATABLE",
                    "LIBRARY_EDITABLE",
                },
            )
        )

    @staticmethod
    def unregister():
        del bpy.types.Object.hide
        del bpy.types.Object.select
        del bpy.types.Object.mmd_root
        del bpy.types.Object.mmd_type
