# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

import logging
import os
import re
import time
import traceback

import bpy
from bpy.types import Operator, OperatorFileListElement
from bpy_extras.io_utils import ExportHelper, ImportHelper

from .. import auto_scene_setup
from ..core.camera import MMDCamera
from ..core.lamp import MMDLamp
from ..core.model import FnModel, Model
from ..core.pmd import importer as pmd_importer
from ..core.pmx import exporter as pmx_exporter
from ..core.pmx import importer as pmx_importer
from ..core.vmd import exporter as vmd_exporter
from ..core.vmd import importer as vmd_importer
from ..core.vpd import exporter as vpd_exporter
from ..core.vpd import importer as vpd_importer
from ..translations import DictionaryEnum
from ..utils import makePmxBoneMap

LOG_LEVEL_ITEMS = [
    ("DEBUG", "4. DEBUG", "", 1),
    ("INFO", "3. INFO", "", 2),
    ("WARNING", "2. WARNING", "", 3),
    ("ERROR", "1. ERROR", "", 4),
]


def log_handler(log_level, filepath=None):
    if filepath is None:
        handler = logging.StreamHandler()
    else:
        handler = logging.FileHandler(filepath, mode="w", encoding="utf-8")
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    return handler


def _update_types(cls, prop):
    types = cls.types.copy()

    if "PHYSICS" in types:
        types.add("ARMATURE")
    if "DISPLAY" in types:
        types.add("ARMATURE")
    if "MORPHS" in types:
        types.add("ARMATURE")
        types.add("MESH")

    if types != cls.types:
        cls.types = types  # trigger update


def get_addon_package_name():
    """Get the root package name for addon preferences"""
    current_package = __package__
    parts = current_package.split(".")
    try:
        index = parts.index("mmd_tools")
        return ".".join(parts[: index + 1])
    except ValueError:
        pass
    return current_package


def get_preset_directories(operator_bl_idname):
    """Get preset directories for an operator"""
    preset_dirs = []

    try:
        # Try the official API first
        official_dirs = bpy.utils.preset_paths(operator_bl_idname)
        preset_dirs.extend(official_dirs)

        # Add manual preset paths as fallback
        scripts_dir = bpy.utils.user_resource("SCRIPTS")
        config_dir = bpy.utils.user_resource("CONFIG")

        manual_preset_paths = [
            os.path.join(scripts_dir, "presets", "operator", operator_bl_idname),
            os.path.join(config_dir, "presets", "operator", operator_bl_idname),
        ]

        for path in manual_preset_paths:
            if os.path.exists(path) and path not in preset_dirs:
                preset_dirs.append(path)

    except Exception:
        pass

    return preset_dirs


def apply_operator_preset(operator, preset_name):
    """Apply a saved preset to an operator instance"""
    if not preset_name:
        return False

    try:
        preset_dirs = get_preset_directories(operator.__class__.bl_idname)

        if not preset_dirs:
            return False

        # Look for the preset file
        preset_file = None
        for path in preset_dirs:
            potential_file = os.path.join(path, preset_name + ".py")
            if os.path.exists(potential_file):
                preset_file = potential_file
                break

        if not preset_file:
            return False

        # Execute preset with proper context
        with bpy.context.temp_override(active_operator=operator):
            try:
                with open(preset_file, encoding="utf-8") as f:
                    preset_code = f.read()

                namespace = {"bpy": bpy}
                exec(preset_code, namespace)
                return True

            except Exception:
                return False

    except Exception:
        return False


def get_available_presets(operator_bl_idname):
    """Get list of available presets for an operator"""
    presets = []

    try:
        preset_dirs = get_preset_directories(operator_bl_idname)

        for preset_dir in preset_dirs:
            try:
                for filename in os.listdir(preset_dir):
                    if filename.endswith(".py"):
                        preset_name = filename[:-3]  # Remove .py extension
                        if preset_name not in presets:
                            presets.append(preset_name)
            except Exception:
                continue

        return sorted(presets)

    except Exception:
        return []


def load_default_settings_from_preferences(operator, context, preset_property_name):
    """Load default settings from preferences using preset"""
    try:
        addon_package = get_addon_package_name()
        addon_prefs = context.preferences.addons.get(addon_package)

        if not addon_prefs:
            return False

        prefs = addon_prefs.preferences

        # Check if the preset property exists
        if not hasattr(prefs, preset_property_name):
            return False

        # Apply preset if specified
        preset_name = getattr(prefs, preset_property_name, "")
        if preset_name and apply_operator_preset(operator, preset_name):
            return True

        return False

    except Exception:
        return False


def get_armature_display_items(self, context):
    # https://docs.blender.org/api/current/bpy.props.html#bpy.props.EnumProperty
    # self & context are required, even though they are not used in function
    enum_items = bpy.types.Armature.bl_rna.properties["display_type"].enum_items
    return [(item.identifier, item.name, "") for item in enum_items]


class PreferencesMixin:
    """Mixin for operators that load default settings from preferences"""

    _preferences_applied = False

    def load_preferences_on_invoke(self, context, preset_property_name):
        """Load preferences on first invoke"""
        self._preferences_were_applied = getattr(self.__class__, "_preferences_applied", False)
        if not self._preferences_were_applied:
            if load_default_settings_from_preferences(self, context, preset_property_name):
                self.__class__._preferences_applied = True

    def restore_preferences_on_cancel(self):
        """Restore preferences state on cancel"""
        self.__class__._preferences_applied = self._preferences_were_applied


class ImportPmx(Operator, ImportHelper, PreferencesMixin):
    bl_idname = "mmd_tools.import_model"
    bl_label = "Import Model File (.pmd, .pmx)"
    bl_description = "Import model file(s) (.pmd, .pmx)"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    files: bpy.props.CollectionProperty(type=OperatorFileListElement, options={"HIDDEN", "SKIP_SAVE"})
    directory: bpy.props.StringProperty(maxlen=1024, subtype="DIR_PATH", options={"HIDDEN", "SKIP_SAVE"})

    filename_ext = ".pmx"
    filter_glob: bpy.props.StringProperty(default="*.pmx;*.pmd", options={"HIDDEN"})

    types: bpy.props.EnumProperty(
        name="Types",
        description="Select which parts will be imported",
        options={"ENUM_FLAG"},
        items=[
            ("MESH", "Mesh", "Mesh", 1),
            ("ARMATURE", "Armature", "Armature", 2),
            ("PHYSICS", "Physics", "Rigidbodies and joints (include Armature)", 4),
            ("DISPLAY", "Display", "Display frames (include Armature)", 8),
            ("MORPHS", "Morphs", "Morphs (include Armature and Mesh)", 16),
        ],
        default={
            "MESH",
            "ARMATURE",
            "PHYSICS",
            "DISPLAY",
            "MORPHS",
        },
        update=_update_types,
    )
    scale: bpy.props.FloatProperty(
        name="Scale",
        description="Scaling factor for importing the model",
        default=0.08,
    )
    clean_model: bpy.props.BoolProperty(
        name="Clean Model",
        description="Remove unused vertices and duplicated/invalid faces",
        default=True,
    )
    remove_doubles: bpy.props.BoolProperty(
        name="Remove Doubles",
        description="Merge duplicated vertices and faces.\nWarning: This will perform global vertex merging instead of per-material vertex merging which may break mesh geometry, material boundaries, and distort the UV map. Use with caution.",
        default=False,
    )
    import_adduv2_as_vertex_colors: bpy.props.BoolProperty(
        name="Import Vertex Colors",
        description="Import ADD UV2 data as vertex colors. When enabled, the UV2 layer will still be created.",
        default=False,
    )
    fix_bone_order: bpy.props.BoolProperty(
        name="Fix Bone Order",
        description="Automatically fix bone order after import. This ensures bones are ordered correctly for MMD compatibility.",
        default=True,
    )
    fix_ik_links: bpy.props.BoolProperty(
        name="Fix IK Links",
        description="Fix IK links to be blender suitable",
        default=False,
    )
    ik_loop_factor: bpy.props.IntProperty(
        name="IK Loop Factor",
        description="Scaling factor of MMD IK loop",
        min=1,
        soft_max=10,
        max=100,
        default=5,
    )
    apply_bone_fixed_axis: bpy.props.BoolProperty(
        name="Apply Bone Fixed Axis",
        description="Apply bone's fixed axis to be blender suitable",
        default=False,
    )
    rename_bones: bpy.props.BoolProperty(
        name="Rename Bones - L / R Suffix",
        description="Use Blender naming conventions for Left / Right paired bones. Required for features like mirror editing and pose mirroring to function properly.",
        default=True,
    )
    use_underscore: bpy.props.BoolProperty(
        name="Rename Bones - Use Underscore",
        description="Will not use dot, e.g. if renaming bones, will use _R instead of .R",
        default=False,
    )
    dictionary: bpy.props.EnumProperty(
        name="Rename Bones To English",
        items=DictionaryEnum.get_dictionary_items,
        description="Translate bone names from Japanese to English using selected dictionary",
    )
    bone_disp_mode: bpy.props.EnumProperty(
        name="Bone Display Mode",
        items=get_armature_display_items,
        description="Change how bones look in viewport.",
    )
    use_mipmap: bpy.props.BoolProperty(
        name="use MIP maps for UV textures",
        description="Specify if mipmaps will be generated",
        default=True,
    )
    sph_blend_factor: bpy.props.FloatProperty(
        name="influence of .sph textures",
        description="The diffuse color factor of texture slot for .sph textures",
        default=1.0,
    )
    spa_blend_factor: bpy.props.FloatProperty(
        name="influence of .spa textures",
        description="The diffuse color factor of texture slot for .spa textures",
        default=1.0,
    )
    enable_rigid_body_world: bpy.props.BoolProperty(
        name="Enable Rigid Body World",
        description="Automatically enable Rigid Body World to the scene when importing physics.",
        default=False,
    )
    log_level: bpy.props.EnumProperty(
        name="Log level",
        description="Select log level",
        items=LOG_LEVEL_ITEMS,
        default="INFO",
    )
    save_log: bpy.props.BoolProperty(
        name="Create a log file",
        description="Create a log file",
        default=False,
    )

    def invoke(self, context, event):
        self.load_preferences_on_invoke(context, "default_pmx_import_preset")
        return super().invoke(context, event)

    def cancel(self, context):
        self.restore_preferences_on_cancel()
        return super().cancel(context) if hasattr(super(), "cancel") else None

    def execute(self, context):
        try:
            self.__translator = DictionaryEnum.get_translator(self.dictionary)
            if self.directory:
                for f in self.files:
                    self.filepath = os.path.join(self.directory, f.name)
                    self._do_execute(context)
            elif self.filepath:
                self._do_execute(context)
        except Exception:
            logging.exception("Error occurred")
            err_msg = traceback.format_exc()
            self.report({"ERROR"}, err_msg)
        return {"FINISHED"}

    def _do_execute(self, context):
        logger = logging.getLogger()
        logger.setLevel(self.log_level)
        handler = None
        if self.save_log:
            handler = log_handler(self.log_level, filepath=self.filepath + ".mmd_tools.import.log")
            logger.addHandler(handler)

        try:
            importer_cls = pmx_importer.PMXImporter
            if re.search(r"\.pmd$", self.filepath, flags=re.IGNORECASE):
                importer_cls = pmd_importer.PMDImporter

            importer_cls().execute(
                filepath=self.filepath,
                types=self.types,
                scale=self.scale,
                clean_model=self.clean_model,
                remove_doubles=self.remove_doubles,
                import_adduv2_as_vertex_colors=self.import_adduv2_as_vertex_colors,
                fix_bone_order=self.fix_bone_order,
                fix_ik_links=self.fix_ik_links,
                ik_loop_factor=self.ik_loop_factor,
                apply_bone_fixed_axis=self.apply_bone_fixed_axis,
                rename_LR_bones=self.rename_bones,
                use_underscore=self.use_underscore,
                bone_disp_mode=self.bone_disp_mode,
                translator=self.__translator,
                use_mipmap=self.use_mipmap,
                sph_blend_factor=self.sph_blend_factor,
                spa_blend_factor=self.spa_blend_factor,
                enable_rigid_body_world=self.enable_rigid_body_world,
            )
            self.report({"INFO"}, f'Imported MMD model from "{self.filepath}"')
        except Exception:
            logging.exception("Error occurred")
            raise
        finally:
            if handler:
                logger.removeHandler(handler)

        return {"FINISHED"}


class ImportVmd(Operator, ImportHelper, PreferencesMixin):
    bl_idname = "mmd_tools.import_vmd"
    bl_label = "Import VMD File (.vmd)"
    bl_description = "Import a VMD file to selected objects (.vmd)\nBehavior varies depending on the selected object:\n- Select the root (cross under the model): imports both armature and morph animations\n- Select the model: imports only morph animation\n- Select the armature: imports only armature animation"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    files: bpy.props.CollectionProperty(type=OperatorFileListElement, options={"HIDDEN", "SKIP_SAVE"})
    directory: bpy.props.StringProperty(maxlen=1024, subtype="DIR_PATH", options={"HIDDEN", "SKIP_SAVE"})

    filename_ext = ".vmd"
    filter_glob: bpy.props.StringProperty(default="*.vmd", options={"HIDDEN"})

    scale: bpy.props.FloatProperty(
        name="Scale",
        description="Scaling factor for importing the motion",
        default=0.08,
    )
    margin: bpy.props.IntProperty(
        name="Margin",
        description="Number of frames to add before the motion starts (only applies if current frame is 0 or 1)",
        min=0,
        default=0,
    )
    bone_mapper: bpy.props.EnumProperty(
        name="Bone Mapper",
        description="Select bone mapper",
        items=[
            ("BLENDER", "Blender", "Use blender bone name", 0),
            ("PMX", "PMX", "Use japanese name of MMD bone", 1),
            ("RENAMED_BONES", "Renamed bones", "Rename the bone of motion data to be blender suitable", 2),
        ],
        default="PMX",
    )
    rename_bones: bpy.props.BoolProperty(
        name="Rename Bones - L / R Suffix",
        description="Use Blender naming conventions for Left / Right paired bones. Required for features like mirror editing and pose mirroring to function properly.",
        default=True,
    )
    use_underscore: bpy.props.BoolProperty(
        name="Rename Bones - Use Underscore",
        description="Will not use dot, e.g. if renaming bones, will use _R instead of .R",
        default=False,
    )
    dictionary: bpy.props.EnumProperty(
        name="Rename Bones To English",
        items=DictionaryEnum.get_dictionary_items,
        description="Translate bone names from Japanese to English using selected dictionary",
    )
    use_pose_mode: bpy.props.BoolProperty(
        name="Treat Current Pose as Rest Pose",
        description="You can pose the model to fit the original pose of a motion data, such as T-Pose or A-Pose",
        default=False,
        options={"SKIP_SAVE"},
    )
    use_mirror: bpy.props.BoolProperty(
        name="Mirror Motion",
        description="Import the motion by using X-Axis mirror",
        default=False,
    )
    update_scene_settings: bpy.props.BoolProperty(
        name="Update scene settings",
        description="Update frame range and frame rate (30 fps)",
        default=True,
    )
    create_new_action: bpy.props.BoolProperty(
        name="Create New Action",
        description="Create a new action when importing VMD, otherwise add keyframes to existing actions if available. Note: This option is ignored when 'Use NLA' is enabled.",
        default=False,
    )
    use_nla: bpy.props.BoolProperty(
        name="Use NLA",
        description="Import the motion as NLA strips",
        default=False,
    )
    detect_camera_changes: bpy.props.BoolProperty(
        name="Detect Camera Cut",
        description="When the interval between camera keyframes is 1 frame, change the interpolation to CONSTANT. This is useful when making a 60fps video, as it helps prevent unwanted smoothing between rapid camera cuts.",
        default=True,
    )
    detect_lamp_changes: bpy.props.BoolProperty(
        # TODO: Update all instances of "lamp" to "light" throughout the repository to align with Blender 2.80+ API changes.
        # This includes:
        #   - Variable names and references
        #   - Class/type checks (LAMP -> LIGHT)
        #   - Documentation and comments
        #   - Function parameters and return values
        # This change is necessary since Blender 2.80 renamed the "Lamp" type to "Light".
        name="Detect Light Cut",
        description="When the interval between light keyframes is 1 frame, change the interpolation to CONSTANT. This is useful when making a 60fps video, as it helps prevent unwanted smoothing during sudden lighting changes.",
        default=True,
    )
    log_level: bpy.props.EnumProperty(
        name="Log level",
        description="Select log level",
        items=LOG_LEVEL_ITEMS,
        default="INFO",
    )
    save_log: bpy.props.BoolProperty(
        name="Create a log file",
        description="Create a log file",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 0

    def invoke(self, context, event):
        self.load_preferences_on_invoke(context, "default_vmd_import_preset")
        return super().invoke(context, event)

    def cancel(self, context):
        self.restore_preferences_on_cancel()
        return super().cancel(context) if hasattr(super(), "cancel") else None

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "scale")
        layout.prop(self, "margin")
        layout.prop(self, "create_new_action")
        layout.prop(self, "use_nla")

        layout.prop(self, "bone_mapper")
        if self.bone_mapper == "RENAMED_BONES":
            layout.prop(self, "rename_bones")
            layout.prop(self, "use_underscore")
            layout.prop(self, "dictionary")
        layout.prop(self, "use_pose_mode")
        layout.prop(self, "use_mirror")
        layout.prop(self, "detect_camera_changes")
        layout.prop(self, "detect_lamp_changes")

        layout.prop(self, "update_scene_settings")

        layout.prop(self, "log_level")
        layout.prop(self, "save_log")

    def execute(self, context):
        logger = logging.getLogger()
        logger.setLevel(self.log_level)
        handler = None
        if self.save_log:
            handler = log_handler(self.log_level, filepath=self.filepath + ".mmd_tools.import.log")
            logger.addHandler(handler)

        try:
            selected_objects = set(context.selected_objects)
            for i in frozenset(selected_objects):
                root = FnModel.find_root_object(i)
                if root == i:
                    rig = Model(root)
                    armature = rig.armature()
                    if armature is not None:
                        selected_objects.add(armature)
                    placeholder = rig.morph_slider.placeholder()
                    if placeholder is not None:
                        selected_objects.add(placeholder)
                    selected_objects |= set(rig.meshes())

            bone_mapper = None
            if self.bone_mapper == "PMX":
                bone_mapper = makePmxBoneMap
            elif self.bone_mapper == "RENAMED_BONES":
                bone_mapper = vmd_importer.RenamedBoneMapper(
                    rename_LR_bones=self.rename_bones,
                    use_underscore=self.use_underscore,
                    translator=DictionaryEnum.get_translator(self.dictionary),
                ).init

            if self.files:
                if self.create_new_action:
                    for obj in selected_objects:
                        self.__reset_all_animations(obj)

            for file in self.files:
                start_time = time.time()
                importer = vmd_importer.VMDImporter(
                    filepath=os.path.join(self.directory, file.name),
                    scale=self.scale,
                    bone_mapper=bone_mapper,
                    use_pose_mode=self.use_pose_mode,
                    frame_margin=self.margin,
                    use_mirror=self.use_mirror,
                    use_nla=self.use_nla,
                    detect_camera_changes=self.detect_camera_changes,
                    detect_lamp_changes=self.detect_lamp_changes,
                )

                for i in selected_objects:
                    importer.assign(i)
                logging.info(" Finished importing motion in %f seconds.", time.time() - start_time)

            if self.update_scene_settings:
                auto_scene_setup.setupFrameRanges()
                auto_scene_setup.setupFps()
            context.scene.frame_set(context.scene.frame_current)

        except Exception:
            logging.exception("Error occurred")
            err_msg = traceback.format_exc()
            self.report({"ERROR"}, err_msg)
        finally:
            if handler:
                logger.removeHandler(handler)

        return {"FINISHED"}

    def __reset_all_animations(self, target_obj):
        """Reset all animation states for the target object and related MMD model objects"""
        root_object = FnModel.find_root_object(target_obj)
        objects_to_process = set()

        if root_object:
            objects_to_process.add(root_object)
            objects_to_process.add(target_obj)
            # Add armature object
            armature_object = FnModel.find_armature_object(root_object)
            if armature_object:
                objects_to_process.add(armature_object)
            # Add all mesh objects
            objects_to_process.update(FnModel.iterate_mesh_objects(root_object))
            # Add other group objects if they exist
            rigid_group = FnModel.find_rigid_group_object(root_object)
            if rigid_group:
                objects_to_process.add(rigid_group)
            joint_group = FnModel.find_joint_group_object(root_object)
            if joint_group:
                objects_to_process.add(joint_group)
            temporary_group = FnModel.find_temporary_group_object(root_object)
            if temporary_group:
                objects_to_process.add(temporary_group)
        else:
            objects_to_process.add(target_obj)

        # STEP 1: Clear all existing actions first
        for obj in objects_to_process:
            # Clear object's own actions
            if obj.animation_data:
                obj.animation_data.action = None

            # Clear Shape Keys actions
            if hasattr(obj, "data") and hasattr(obj.data, "shape_keys") and obj.data.shape_keys:
                if obj.data.shape_keys.animation_data:
                    obj.data.shape_keys.animation_data.action = None

            # Clear light data actions
            if obj.type == "LIGHT" and obj.data.animation_data:
                obj.data.animation_data.action = None

        # STEP 2: Reset all properties to default states
        for obj in objects_to_process:
            if obj.type == "ARMATURE":
                # Reset armature pose
                for bone in obj.pose.bones:
                    bone.location = (0.0, 0.0, 0.0)
                    bone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
                    bone.rotation_euler = (0.0, 0.0, 0.0)
                    bone.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
                    bone.scale = (1.0, 1.0, 1.0)

                    # Reset IK settings to default
                    if hasattr(bone, "mmd_ik_toggle"):
                        bone.mmd_ik_toggle = True

            elif obj.type == "MESH" and getattr(obj.data, "shape_keys", None):
                # Reset mesh morphs
                for shape_key in obj.data.shape_keys.key_blocks:
                    if shape_key.name != "Basis":  # Don't reset basis shape key
                        shape_key.value = 0.0

            # NOTE: Unnecessary for animation import; users expect only bones/morphs reset
            # elif hasattr(obj, "mmd_type") and obj.mmd_type == "ROOT":
            #     # Reset root display state
            #     if hasattr(obj, "mmd_root") and hasattr(obj.mmd_root, "show_meshes"):
            #         obj.mmd_root.show_meshes = True  # Default to show meshes


class ImportVpd(Operator, ImportHelper, PreferencesMixin):
    bl_idname = "mmd_tools.import_vpd"
    bl_label = "Import VPD File (.vpd)"
    bl_description = "Import VPD file(s) to selected rig's Action Pose (.vpd)\nBehavior varies depending on the selected object:\n- Select the root (cross under the model): applies both armature pose and morphs\n- Select the model: applies only morphs\n- Select the armature: applies only armature pose"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    files: bpy.props.CollectionProperty(type=OperatorFileListElement, options={"HIDDEN", "SKIP_SAVE"})
    directory: bpy.props.StringProperty(maxlen=1024, subtype="DIR_PATH", options={"HIDDEN", "SKIP_SAVE"})

    filename_ext = ".vpd"
    filter_glob: bpy.props.StringProperty(default="*.vpd", options={"HIDDEN"})

    scale: bpy.props.FloatProperty(
        name="Scale",
        description="Scaling factor for importing the pose",
        default=0.08,
    )
    bone_mapper: bpy.props.EnumProperty(
        name="Bone Mapper",
        description="Select bone mapper",
        items=[
            ("BLENDER", "Blender", "Use blender bone name", 0),
            ("PMX", "PMX", "Use japanese name of MMD bone", 1),
            ("RENAMED_BONES", "Renamed bones", "Rename the bone of pose data to be blender suitable", 2),
        ],
        default="PMX",
    )
    rename_bones: bpy.props.BoolProperty(
        name="Rename Bones - L / R Suffix",
        description="Use Blender naming conventions for Left / Right paired bones. Required for features like mirror editing and pose mirroring to function properly.",
        default=True,
    )
    use_underscore: bpy.props.BoolProperty(
        name="Rename Bones - Use Underscore",
        description="Will not use dot, e.g. if renaming bones, will use _R instead of .R",
        default=False,
    )
    dictionary: bpy.props.EnumProperty(
        name="Rename Bones To English",
        items=DictionaryEnum.get_dictionary_items,
        description="Translate bone names from Japanese to English using selected dictionary",
    )
    use_pose_mode: bpy.props.BoolProperty(
        name="Treat Current Pose as Rest Pose",
        description="You can pose the model to fit the original pose of a pose data, such as T-Pose or A-Pose",
        default=False,
        options={"SKIP_SAVE"},
    )

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 0

    def invoke(self, context, event):
        self.load_preferences_on_invoke(context, "default_vpd_import_preset")
        return super().invoke(context, event)

    def cancel(self, context):
        self.restore_preferences_on_cancel()
        return super().cancel(context) if hasattr(super(), "cancel") else None

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "scale")

        layout.prop(self, "bone_mapper")
        if self.bone_mapper == "RENAMED_BONES":
            layout.prop(self, "rename_bones")
            layout.prop(self, "use_underscore")
            layout.prop(self, "dictionary")
        layout.prop(self, "use_pose_mode")

    def execute(self, context):
        selected_objects = set(context.selected_objects)
        for i in frozenset(selected_objects):
            root = FnModel.find_root_object(i)
            if root == i:
                rig = Model(root)
                armature = rig.armature()
                if armature is not None:
                    selected_objects.add(armature)
                placeholder = rig.morph_slider.placeholder()
                if placeholder is not None:
                    selected_objects.add(placeholder)
                selected_objects |= set(rig.meshes())

        bone_mapper = None
        if self.bone_mapper == "PMX":
            bone_mapper = makePmxBoneMap
        elif self.bone_mapper == "RENAMED_BONES":
            bone_mapper = vmd_importer.RenamedBoneMapper(
                rename_LR_bones=self.rename_bones,
                use_underscore=self.use_underscore,
                translator=DictionaryEnum.get_translator(self.dictionary),
            ).init

        for f in self.files:
            importer = vpd_importer.VPDImporter(
                filepath=os.path.join(self.directory, f.name),
                scale=self.scale,
                bone_mapper=bone_mapper,
                use_pose_mode=self.use_pose_mode,
            )
            for i in selected_objects:
                importer.assign(i)
        return {"FINISHED"}


class ExportPmx(Operator, ExportHelper, PreferencesMixin):
    bl_idname = "mmd_tools.export_pmx"
    bl_label = "Export PMX File (.pmx)"
    bl_description = "Export selected MMD model(s) to PMX file(s) (.pmx)"
    bl_options = {"PRESET"}

    filename_ext = ".pmx"
    filter_glob: bpy.props.StringProperty(default="*.pmx", options={"HIDDEN"})

    scale: bpy.props.FloatProperty(
        name="Scale",
        description="Scaling factor for exporting the model",
        default=12.5,
    )
    copy_textures_mode: bpy.props.EnumProperty(
        name="Copy Textures",
        description="Choose how to handle texture files during export",
        items=[
            ("NONE", "Don't Copy", "Don't copy texture files", 0),
            ("SKIP_EXISTING", "Copy (Skip Existing)", "Copy textures but skip files that already exist", 1),
            ("OVERWRITE", "Copy (Overwrite)", "Copy textures and overwrite existing files", 2),
        ],
        default="SKIP_EXISTING",
    )
    sort_materials: bpy.props.BoolProperty(
        name="Sort Materials",
        description="Sort materials for alpha blending. WARNING: Will not work if you have transparent meshes inside the model. E.g. blush meshes",
        default=False,
    )
    disable_specular: bpy.props.BoolProperty(
        name="Disable SPH/SPA",
        description="Disables all the Specular Map textures. It is required for some MME Shaders.",
        default=False,
    )
    visible_meshes_only: bpy.props.BoolProperty(
        name="Visible Meshes Only",
        description="Export visible meshes only",
        default=False,
    )
    export_vertex_colors_as_adduv2: bpy.props.BoolProperty(
        name="Export Vertex Colors",
        description="Export vertex colors as ADD UV2 data. This allows vertex color data to be preserved in the PMX file format. When enabled, existing ADD UV2 data on the model will be skipped during export.",
        default=False,
    )
    fix_bone_order: bpy.props.BoolProperty(
        name="Fix Bone Order",
        description="Automatically fix bone order before export. This ensures bones are ordered correctly for MMD compatibility.",
        default=True,
    )
    overwrite_bone_morphs_from_action_pose: bpy.props.BoolProperty(
        name="Overwrite Bone Morphs",
        description="Overwrite the bone morphs from active Action Pose before exporting.",
        default=False,
    )
    translate_in_presets: bpy.props.BoolProperty(
        name="(Experimental) Translate in Presets",
        description="Translate in presets before exporting.",
        default=False,
    )
    normal_handling: bpy.props.EnumProperty(
        name="Normal Handling",
        description="Choose how to handle normals during export. This affects vertex count, edge count, and mesh topology by splitting vertices and edges to preserve split normals.",
        items=[
            ("PRESERVE_ALL_NORMALS", "Preserve All Normals", "Export existing normals without any changes. This option performs NO automatic smoothing; only use it if you have already manually smoothed and perfected your normals. When using this option, please verify if the vertex count of the exported model has significantly increased or is within a reasonable range to prevent excessive geometry destruction and an overly fragmented model.", 0),
            ("SMOOTH_KEEP_SHARP", "Smooth (Keep Sharp)", "Shade smooth, keep sharp edges. Balances vertex count and normal preservation.", 1),
            ("SMOOTH_ALL_NORMALS", "Smooth All Normals", "Force smooths all normals, ignoring any sharp edges. This will result in a completely smooth-shaded model and minimum vertex count.", 2),
        ],
        default="SMOOTH_KEEP_SHARP",
    )
    sort_vertices: bpy.props.EnumProperty(
        name="Sort Vertices",
        description="Choose the method to sort vertices",
        items=[
            ("NONE", "None", "No sorting", 0),
            ("BLENDER", "Blender", "Use blender's internal vertex order", 1),
            ("CUSTOM", "Custom", 'Use custom vertex weight of vertex group "mmd_vertex_order"', 2),
        ],
        default="NONE",
    )
    ik_angle_limits: bpy.props.EnumProperty(
        name="IK Angle Limits",
        description="Choose how to handle IK angle limits during export",
        items=[
            (
                "EXPORT_ALL",
                "Export All Limits",
                "Export all existing IK angle limits using current priority system: "
                "mmd_ik_limit_override -> Blender IK limits -> other sources. "
                "If mmd_ik_limit_override disables an axis but Blender IK limits exist for that axis, "
                "the Blender limits will still be exported. This maintains backward compatibility "
                "with existing workflows",
                0,
            ),
            (
                "IGNORE_ALL",
                "Ignore All Limits",
                "Completely ignore all IK angle limits from any source during export. "
                "No angle restrictions will be written to the PMX file, regardless of "
                "mmd_ik_limit_override, Blender IK limits, or other constraint settings. "
                "Useful when you want to rely entirely on MMD v9.19+ fixed axis feature instead",
                1,
            ),
            (
                "OVERRIDE_CONTROLLED",
                "Override Controlled",
                "Use mmd_ik_limit_override constraints as the sole authority for IK limits. "
                "When mmd_ik_limit_override exists: only its enabled axes export limits, "
                "disabled axes export no limits (ignoring Blender IK limits). "
                "When mmd_ik_limit_override doesn't exist: fall back to Blender IK limits. "
                "This makes mmd_ik_limit_override act as a true 'override' that completely "
                "controls whether limits are exported, enabling fine-grained per-bone control",
                2,
            ),
        ],
        default="EXPORT_ALL",
    )
    log_level: bpy.props.EnumProperty(
        name="Log level",
        description="Select log level",
        items=LOG_LEVEL_ITEMS,
        default="DEBUG",
    )
    save_log: bpy.props.BoolProperty(
        name="Create a log file",
        description="Create a log file",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj in context.selected_objects and FnModel.find_root_object(obj)

    def invoke(self, context, event):
        self.load_preferences_on_invoke(context, "default_pmx_export_preset")
        return super().invoke(context, event)

    def cancel(self, context):
        self.restore_preferences_on_cancel()
        return super().cancel(context) if hasattr(super(), "cancel") else None

    def execute(self, context):
        try:
            folder = os.path.dirname(self.filepath)
            models = {FnModel.find_root_object(i) for i in context.selected_objects}
            for root in models:
                if root is None:
                    continue
                # use original self.filepath when export only one model
                # otherwise, use root object's name as file name
                if len(models) > 1:
                    model_name = bpy.path.clean_name(root.name)
                    model_folder = os.path.join(folder, model_name)
                    os.makedirs(model_folder, exist_ok=True)
                    self.filepath = os.path.join(model_folder, model_name + ".pmx")
                self._do_execute(context, root)
        except Exception:
            logging.exception("Error occurred")
            err_msg = traceback.format_exc()
            self.report({"ERROR"}, err_msg)
        return {"FINISHED"}

    def _do_execute(self, context, root):
        logger = logging.getLogger()
        logger.setLevel(self.log_level)
        handler = None
        if self.save_log:
            handler = log_handler(self.log_level, filepath=self.filepath + ".mmd_tools.export.log")
            logger.addHandler(handler)

        arm = FnModel.find_armature_object(root)
        if arm is None:
            self.report({"ERROR"}, f'[Skipped] The armature object of MMD model "{root.name}" can\'t be found')
            return {"CANCELLED"}
        orig_pose_position = None
        if not root.mmd_root.is_built:  # use 'REST' pose when the model is not built
            orig_pose_position = arm.data.pose_position
            arm.data.pose_position = "REST"
            arm.update_tag()
            context.scene.frame_set(context.scene.frame_current)

        try:
            meshes = FnModel.iterate_mesh_objects(root)
            if self.visible_meshes_only:
                meshes = (x for x in meshes if x in context.visible_objects)
            pmx_exporter.export(
                filepath=self.filepath,
                scale=self.scale,
                root=root,
                armature=FnModel.find_armature_object(root),
                meshes=meshes,
                rigid_bodies=FnModel.iterate_rigid_body_objects(root),
                joints=FnModel.iterate_joint_objects(root),
                copy_textures_mode=self.copy_textures_mode,
                fix_bone_order=self.fix_bone_order,
                overwrite_bone_morphs_from_action_pose=self.overwrite_bone_morphs_from_action_pose,
                translate_in_presets=self.translate_in_presets,
                sort_materials=self.sort_materials,
                sort_vertices=self.sort_vertices,
                disable_specular=self.disable_specular,
                export_vertex_colors_as_adduv2=self.export_vertex_colors_as_adduv2,
                normal_handling=self.normal_handling,
                ik_angle_limits=self.ik_angle_limits,
            )
            self.report({"INFO"}, f'Exported MMD model "{root.name}" to "{self.filepath}"')
        except Exception:
            logging.exception("Error occurred")
            raise
        finally:
            if orig_pose_position:
                arm.data.pose_position = orig_pose_position
            if handler:
                logger.removeHandler(handler)

        return {"FINISHED"}


class ExportVmd(Operator, ExportHelper, PreferencesMixin):
    bl_idname = "mmd_tools.export_vmd"
    bl_label = "Export VMD File (.vmd)"
    bl_description = "Export motion data of active object to a VMD file (.vmd)\nBehavior varies depending on the active object:\n- Active object is the root (cross under the model): exports both armature and morph animations\n- Active object is the model: exports only morph animation\n- Active object is the armature: exports only armature animation"
    bl_options = {"PRESET"}

    filename_ext = ".vmd"
    filter_glob: bpy.props.StringProperty(default="*.vmd", options={"HIDDEN"})

    scale: bpy.props.FloatProperty(
        name="Scale",
        description="Scaling factor for exporting the motion",
        default=12.5,
    )
    use_pose_mode: bpy.props.BoolProperty(
        name="Treat Current Pose as Rest Pose",
        description="You can pose the model to export a motion data to different pose base, such as T-Pose or A-Pose",
        default=False,
        options={"SKIP_SAVE"},
    )
    use_frame_range: bpy.props.BoolProperty(
        name="Use Frame Range",
        description="Export frames only in the frame range of context scene",
        default=False,
    )
    preserve_curves: bpy.props.BoolProperty(
        name="Preserve Animation Curves",
        description="Add additional keyframes to accurately preserve animation curves. Blender's bezier handles are more flexible than the VMD format. Complex handle settings will be lost during export unless additional keyframes are added to approximate the original curves.",
        default=False,
    )
    log_level: bpy.props.EnumProperty(
        name="Log level",
        description="Select log level",
        items=LOG_LEVEL_ITEMS,
        default="INFO",
    )
    save_log: bpy.props.BoolProperty(
        name="Create a log file",
        description="Create a log file",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None:
            return False

        if obj.mmd_type == "ROOT":
            return True
        if obj.mmd_type == "NONE" and (obj.type == "ARMATURE" or getattr(obj.data, "shape_keys", None)):
            return True
        if MMDCamera.isMMDCamera(obj) or MMDLamp.isMMDLamp(obj):
            return True

        return False

    def invoke(self, context, event):
        self.load_preferences_on_invoke(context, "default_vmd_export_preset")
        return super().invoke(context, event)

    def cancel(self, context):
        self.restore_preferences_on_cancel()
        return super().cancel(context) if hasattr(super(), "cancel") else None

    def execute(self, context):
        logger = logging.getLogger()
        logger.setLevel(self.log_level)
        handler = None
        if self.save_log:
            handler = log_handler(self.log_level, filepath=self.filepath + ".mmd_tools.export.log")
            logger.addHandler(handler)

        try:
            params = {
                "filepath": self.filepath,
                "scale": self.scale,
                "use_pose_mode": self.use_pose_mode,
                "use_frame_range": self.use_frame_range,
                "preserve_curves": self.preserve_curves,
            }

            obj = context.active_object
            if obj.mmd_type == "ROOT":
                rig = Model(obj)
                params["mesh"] = rig.morph_slider.placeholder(binded=True) or rig.firstMesh()
                params["armature"] = rig.armature()
                params["model_name"] = obj.mmd_root.name or obj.name
            elif getattr(obj.data, "shape_keys", None):
                params["mesh"] = obj
                params["model_name"] = obj.name
            elif obj.type == "ARMATURE":
                params["armature"] = obj
                params["model_name"] = obj.name
            else:
                for i in context.selected_objects:
                    if MMDCamera.isMMDCamera(i):
                        params["camera"] = i
                    elif MMDLamp.isMMDLamp(i):
                        params["lamp"] = i

            start_time = time.time()
            vmd_exporter.VMDExporter().export(**params)
            logging.info(" Finished exporting motion in %f seconds.", time.time() - start_time)
        except Exception:
            logging.exception("Error occurred")
            err_msg = traceback.format_exc()
            self.report({"ERROR"}, err_msg)
        finally:
            if handler:
                logger.removeHandler(handler)
        return {"FINISHED"}


class ExportVpd(Operator, ExportHelper, PreferencesMixin):
    bl_idname = "mmd_tools.export_vpd"
    bl_label = "Export VPD File (.vpd)"
    bl_description = "Export active rig's Action Pose to VPD file(s) (.vpd)\nBehavior varies depending on the active object:\n- Active object is the root (cross under the model): exports both armature pose and morphs\n- Active object is the model: exports only morphs\n- Active object is the armature: exports only armature pose"
    bl_options = {"PRESET"}

    filename_ext = ".vpd"
    filter_glob: bpy.props.StringProperty(default="*.vpd", options={"HIDDEN"})

    scale: bpy.props.FloatProperty(
        name="Scale",
        description="Scaling factor for exporting the pose",
        default=12.5,
    )
    pose_type: bpy.props.EnumProperty(
        name="Pose Type",
        description="Choose the pose type to export",
        items=[
            ("CURRENT", "Current Pose", "Current pose of the rig", 0),
            ("ACTIVE", "Active Pose", "Active pose of the rig's Action Pose", 1),
            ("ALL", "All Poses", "All poses of the rig's Action Pose (the pose name will be the file name)", 2),
        ],
        default="CURRENT",
    )
    use_pose_mode: bpy.props.BoolProperty(
        name="Treat Current Pose as Rest Pose",
        description="You can pose the model to export a pose data to different pose base, such as T-Pose or A-Pose",
        default=False,
        options={"SKIP_SAVE"},
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None:
            return False

        if obj.mmd_type == "ROOT":
            return True
        if obj.mmd_type == "NONE" and (obj.type == "ARMATURE" or getattr(obj.data, "shape_keys", None)):
            return True

        return False

    def invoke(self, context, event):
        self.load_preferences_on_invoke(context, "default_vpd_export_preset")
        return super().invoke(context, event)

    def cancel(self, context):
        self.restore_preferences_on_cancel()
        return super().cancel(context) if hasattr(super(), "cancel") else None

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "scale")
        layout.prop(self, "pose_type", expand=True)
        if self.pose_type != "CURRENT":
            layout.prop(self, "use_pose_mode")

    def execute(self, context):
        params = {
            "filepath": self.filepath,
            "scale": self.scale,
            "pose_type": self.pose_type,
            "use_pose_mode": self.use_pose_mode,
        }

        obj = context.active_object
        if obj.mmd_type == "ROOT":
            rig = Model(obj)
            params["mesh"] = rig.morph_slider.placeholder(binded=True) or rig.firstMesh()
            params["armature"] = rig.armature()
            params["model_name"] = obj.mmd_root.name or obj.name
        elif getattr(obj.data, "shape_keys", None):
            params["mesh"] = obj
            params["model_name"] = obj.name
        elif obj.type == "ARMATURE":
            params["armature"] = obj
            params["model_name"] = obj.name

        try:
            vpd_exporter.VPDExporter().export(**params)
        except Exception:
            logging.exception("Error occurred")
            err_msg = traceback.format_exc()
            self.report({"ERROR"}, err_msg)
        return {"FINISHED"}
