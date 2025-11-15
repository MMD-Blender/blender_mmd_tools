# Copyright 2021 MMD Tools authors
# This file is part of MMD Tools.

import csv
import os
from typing import TYPE_CHECKING, cast

import bpy

from ..core.model import FnModel, Model
from ..core.translations import MMD_DATA_TYPE_TO_HANDLERS, FnTranslations
from ..translations import DictionaryEnum

if TYPE_CHECKING:
    from ..properties.translations import (
        MMDTranslation,
        MMDTranslationElement,
        MMDTranslationElementIndex,
    )


class TranslateMMDModel(bpy.types.Operator):
    bl_idname = "mmd_tools.translate_mmd_model"
    bl_label = "Translate a MMD Model"
    bl_description = "Translate Japanese names of a MMD model"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    dictionary: bpy.props.EnumProperty(
        name="Dictionary",
        items=DictionaryEnum.get_dictionary_items,
        description="Translate names from Japanese to English using selected dictionary",
    )
    types: bpy.props.EnumProperty(
        name="Types",
        description="Select which parts will be translated",
        options={"ENUM_FLAG"},
        items=[
            ("BONE", "Bones", "Bones", 1),
            ("MORPH", "Morphs", "Morphs", 2),
            ("MATERIAL", "Materials", "Materials", 4),
            ("DISPLAY", "Display", "Display frames", 8),
            ("PHYSICS", "Physics", "Rigidbodies and joints", 16),
            ("INFO", "Information", "Model name and comments", 32),
        ],
        default={
            "BONE",
            "MORPH",
            "MATERIAL",
            "DISPLAY",
            "PHYSICS",
        },
    )
    modes: bpy.props.EnumProperty(
        name="Modes",
        description="Select translation mode",
        options={"ENUM_FLAG"},
        items=[
            ("MMD", "MMD Names", "Fill MMD English names", 1),
            ("BLENDER", "Blender Names", "Translate blender names (experimental)", 2),
        ],
        default={"MMD"},
    )
    use_morph_prefix: bpy.props.BoolProperty(
        name="Use Morph Prefix",
        description="Add/remove prefix to English name of morph",
        default=False,
    )
    overwrite: bpy.props.BoolProperty(
        name="Overwrite",
        description="Overwrite a translated English name",
        default=False,
    )
    allow_fails: bpy.props.BoolProperty(
        name="Allow Fails",
        description="Allow incompletely translated names",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        root = FnModel.find_root_object(obj)
        return obj is not None and obj in context.selected_objects and root is not None

    def invoke(self, context, event):
        vm = context.window_manager
        return vm.invoke_props_dialog(self)

    def execute(self, context):
        try:
            self.__translator = DictionaryEnum.get_translator(self.dictionary)
        except Exception as e:
            self.report({"ERROR"}, f"Failed to load dictionary: {e}")
            return {"CANCELLED"}

        obj = context.active_object
        root = FnModel.find_root_object(obj)
        rig = Model(root)

        if "MMD" in self.modes:
            for i in self.types:
                getattr(self, f"translate_{i.lower()}")(rig)

        if "BLENDER" in self.modes:
            self.translate_blender_names(rig)

        translator = self.__translator
        txt = translator.save_fails()
        if translator.fails:
            self.report({"WARNING"}, f"Failed to translate {len(translator.fails)} names, see '{txt.name}' in text editor")
        return {"FINISHED"}

    def translate(self, name_j, name_e):
        if not self.overwrite and name_e and self.__translator.is_translated(name_e):
            return name_e
        if self.allow_fails:
            name_e = None
        return self.__translator.translate(name_j, name_e)

    def translate_blender_names(self, rig: Model):
        if "BONE" in self.types:
            for b in rig.armature().pose.bones:
                rig.renameBone(b.name, self.translate(b.name, b.name))

        if "MORPH" in self.types:
            for i in (x for x in rig.meshes() if x.data.shape_keys):
                for kb in i.data.shape_keys.key_blocks:
                    kb.name = self.translate(kb.name, kb.name)

        if "MATERIAL" in self.types:
            for m in (x for x in rig.materials() if x):
                m.name = self.translate(m.name, m.name)

        if "DISPLAY" in self.types:
            g: bpy.types.BoneCollection
            for g in cast("bpy.types.Armature", rig.armature().data).collections:
                g.name = self.translate(g.name, g.name)

        if "PHYSICS" in self.types:
            for i in rig.rigidBodies():
                i.name = self.translate(i.name, i.name)

            for i in rig.joints():
                i.name = self.translate(i.name, i.name)

        if "INFO" in self.types:
            objects = [rig.rootObject(), rig.armature()]
            objects.extend(rig.meshes())
            for i in objects:
                i.name = self.translate(i.name, i.name)

    def translate_info(self, rig):
        mmd_root = rig.rootObject().mmd_root
        mmd_root.name_e = self.translate(mmd_root.name, mmd_root.name_e)

        comment_text = bpy.data.texts.get(mmd_root.comment_text, None)
        comment_e_text = bpy.data.texts.get(mmd_root.comment_e_text, None)
        if comment_text and comment_e_text:
            comment_e = self.translate(
                comment_text.as_string(), comment_e_text.as_string(),
            )
            comment_e_text.from_string(comment_e)

    def translate_bone(self, rig):
        bones = rig.armature().pose.bones
        for b in bones:
            if b.is_mmd_shadow_bone:
                continue
            b.mmd_bone.name_e = self.translate(b.mmd_bone.name_j, b.mmd_bone.name_e)

    def translate_morph(self, rig):
        mmd_root = rig.rootObject().mmd_root
        attr_list = ("group", "vertex", "bone", "uv", "material")
        prefix_list = ("G_", "", "B_", "UV_", "M_")
        for attr, prefix in zip(attr_list, prefix_list, strict=False):
            for m in getattr(mmd_root, attr + "_morphs", []):
                m.name_e = self.translate(m.name, m.name_e)
                if not prefix:
                    continue
                if self.use_morph_prefix:
                    if not m.name_e.startswith(prefix):
                        m.name_e = prefix + m.name_e
                elif m.name_e.startswith(prefix):
                    m.name_e = m.name_e[len(prefix) :]

    def translate_material(self, rig):
        for m in rig.materials():
            if m is None:
                continue
            m.mmd_material.name_e = self.translate(
                m.mmd_material.name_j, m.mmd_material.name_e,
            )

    def translate_display(self, rig):
        mmd_root = rig.rootObject().mmd_root
        for f in mmd_root.display_item_frames:
            f.name_e = self.translate(f.name, f.name_e)

    def translate_physics(self, rig):
        for i in rig.rigidBodies():
            i.mmd_rigid.name_e = self.translate(i.mmd_rigid.name_j, i.mmd_rigid.name_e)

        for i in rig.joints():
            i.mmd_joint.name_e = self.translate(i.mmd_joint.name_j, i.mmd_joint.name_e)


DEFAULT_SHOW_ROW_COUNT = 20


class MMD_TOOLS_UL_MMDTranslationElementIndex(bpy.types.UIList):
    def draw_item(
        self,
        context,
        layout: bpy.types.UILayout,
        data,
        mmd_translation_element_index: "MMDTranslationElementIndex",
        icon,
        active_data,
        active_propname,
        index: int,
    ):
        mmd_translation_element: MMDTranslationElement = data.translation_elements[
            mmd_translation_element_index.value
        ]
        MMD_DATA_TYPE_TO_HANDLERS[mmd_translation_element.type].draw_item(
            layout, mmd_translation_element, index,
        )


class RestoreMMDDataReferenceOperator(bpy.types.Operator):
    bl_idname = "mmd_tools.restore_mmd_translation_element_name"
    bl_label = "Restore this Name"
    bl_options = {"INTERNAL"}

    index: bpy.props.IntProperty()
    prop_name: bpy.props.StringProperty()
    restore_value: bpy.props.StringProperty()

    def execute(self, context: bpy.types.Context):
        root_object = FnModel.find_root_object(context.active_object)
        mmd_translation_element_index = (
            root_object.mmd_root.translation.filtered_translation_element_indices[
                self.index
            ].value
        )
        mmd_translation_element = root_object.mmd_root.translation.translation_elements[
            mmd_translation_element_index
        ]
        setattr(mmd_translation_element, self.prop_name, self.restore_value)

        return {"FINISHED"}


class GlobalTranslationPopup(bpy.types.Operator):
    bl_idname = "mmd_tools.global_translation_popup"
    bl_label = "Global Translation Popup"
    bl_options = {"INTERNAL", "UNDO"}

    @classmethod
    def poll(cls, context):
        root = FnModel.find_root_object(context.active_object)
        return root is not None

    def draw(self, _context):
        layout = self.layout
        mmd_translation = self._mmd_translation

        col = layout.column(align=True)
        col.label(text="Filter", icon="FILTER")
        row = col.row()
        row.prop(mmd_translation, "filter_types")

        group = row.row(align=True, heading="is Blank:")
        group.alignment = "RIGHT"
        group.prop(
            mmd_translation, "filter_japanese_blank", toggle=True, text="Japanese",
        )
        group.prop(mmd_translation, "filter_english_blank", toggle=True, text="English")

        group = row.row(align=True)
        group.prop(
            mmd_translation,
            "filter_restorable",
            toggle=True,
            icon="FILE_REFRESH",
            icon_only=True,
        )
        group.prop(
            mmd_translation,
            "filter_selected",
            toggle=True,
            icon="RESTRICT_SELECT_OFF",
            icon_only=True,
        )
        group.prop(
            mmd_translation,
            "filter_visible",
            toggle=True,
            icon="HIDE_OFF",
            icon_only=True,
        )

        col = layout.column(align=True)
        box = col.box().column(align=True)
        row = box.row(align=True)
        row.label(text="Select the target column for Batch Operations:", icon="TRACKER")
        row = box.row(align=True)
        row.label(text="", icon="BLANK1")
        row.prop(mmd_translation, "batch_operation_target", expand=True)
        row.label(text="", icon="RESTRICT_SELECT_OFF")
        row.label(text="", icon="HIDE_OFF")

        if (
            len(mmd_translation.filtered_translation_element_indices)
            > DEFAULT_SHOW_ROW_COUNT
        ):
            row.label(text="", icon="BLANK1")

        col.template_list(
            "MMD_TOOLS_UL_MMDTranslationElementIndex",
            "",
            mmd_translation,
            "filtered_translation_element_indices",
            mmd_translation,
            "filtered_translation_element_indices_active_index",
            rows=DEFAULT_SHOW_ROW_COUNT,
        )

        box = layout.box().column(align=True)
        box.label(text="Batch Operation:", icon="MODIFIER")
        box.prop(mmd_translation, "batch_operation_script", text="", icon="SCRIPT")

        box.separator()
        row = box.row()
        row.prop(
            mmd_translation,
            "batch_operation_script_preset",
            text="Preset",
            icon="CON_TRANSFORM_CACHE",
        )
        row.operator(ExecuteTranslationBatchOperator.bl_idname, text="Execute")

        box.separator()
        translation_box = box.box().column(align=True)
        translation_box.label(text="Dictionaries:", icon="HELP")
        row = translation_box.row()
        row.prop(mmd_translation, "dictionary", text="to_english")

        translation_box.separator()
        row = translation_box.row()
        row.prop(mmd_translation, "dictionary", text="replace")

        # CSV import/export
        box.separator()
        translation_box = box.box().column(align=True)
        translation_box.label(text="CSV:", icon="FILE_TEXT")
        row = translation_box.row()
        row.operator(ImportTranslationCSVOperator.bl_idname, text="Import CSV")
        row.operator(ExportTranslationCSVOperator.bl_idname, text="Export CSV")

    def invoke(self, context: bpy.types.Context, _event):
        root_object = FnModel.find_root_object(context.active_object)
        if root_object is None:
            return {"CANCELLED"}

        mmd_translation: MMDTranslation = root_object.mmd_root.translation
        self._mmd_translation = mmd_translation
        FnTranslations.clear_data(mmd_translation)
        FnTranslations.collect_data(mmd_translation)
        FnTranslations.update_query(mmd_translation)

        return context.window_manager.invoke_props_dialog(self, width=800)

    def execute(self, context):
        root_object = FnModel.find_root_object(context.active_object)
        if root_object is None:
            return {"CANCELLED"}

        FnTranslations.apply_translations(root_object)
        FnTranslations.clear_data(root_object.mmd_root.translation)

        return {"FINISHED"}


class ExecuteTranslationBatchOperator(bpy.types.Operator):
    bl_idname = "mmd_tools.execute_translation_batch"
    bl_label = "Execute Translation Batch"
    bl_options = {"INTERNAL"}

    def execute(self, context: bpy.types.Context):
        root = FnModel.find_root_object(context.active_object)
        if root is None:
            return {"CANCELLED"}

        fails, text = FnTranslations.execute_translation_batch(root)
        if fails:
            self.report({"WARNING"}, f"Failed to translate {len(fails)} names, see '{text.name}' in text editor")
        return {"FINISHED"}


class ExportTranslationCSVOperator(bpy.types.Operator):
    bl_idname = "mmd_tools.export_translation_csv"
    bl_description = "Export CSV for external translation."
    bl_label = "Export Translation CSV"

    filter_glob: bpy.props.StringProperty(default="*.csv", options={"HIDDEN"})
    filename_ext = ".csv"
    filepath: bpy.props.StringProperty(
        name="File Path",
        description="Path to save the translation CSV",
        subtype="FILE_PATH",
        default="mmd_translation.csv",
    )

    def _ensure_csv_extension(self):
        """Ensure the file path ends with a .csv extension (case-insensitive)."""
        if not self.filepath.lower().endswith(".csv"):
            self.filepath = bpy.path.ensure_ext(self.filepath, ".csv")

    def invoke(self, context, event):
        self._ensure_csv_extension()
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        self._ensure_csv_extension()
        root_object = FnModel.find_root_object(context.active_object)
        if root_object is None:
            self.report({"ERROR"}, "Root object not found")
            return {"CANCELLED"}

        mmd_translation = root_object.mmd_root.translation

        try:
            with open(self.filepath, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["type", "blender", "japanese", "english"])
                for idx in mmd_translation.filtered_translation_element_indices:
                    element = mmd_translation.translation_elements[idx.value]
                    writer.writerow(
                        [element.type, element.name, element.name_j, element.name_e],
                    )
        except Exception as e:
            self.report({"ERROR"}, f"Failed to write CSV: {e}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Exported to {os.path.basename(self.filepath)}")
        return {"FINISHED"}


class ImportTranslationCSVOperator(bpy.types.Operator):
    bl_idname = "mmd_tools.import_translation_csv"
    bl_description = "Import translated CSV."
    bl_label = "Import Translation CSV"

    only_update_english_name: bpy.props.BoolProperty(
        name="Only Update English Name",
        description="(Enabled by default) Only update English name (name_e). otherwise, update all names when different",
        default=True,
    )

    filter_glob: bpy.props.StringProperty(default="*.csv", options={"HIDDEN"})
    filepath: bpy.props.StringProperty(
        name="File Path",
        description="Path to import the translation CSV",
        subtype="FILE_PATH",
        default="*.csv",
    )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        root_object = FnModel.find_root_object(context.active_object)
        if root_object is None:
            self.report({"ERROR"}, "Root object not found")
            return {"CANCELLED"}

        mmd_translation = root_object.mmd_root.translation
        updated_count = 0
        warnings = []

        try:
            with open(self.filepath, encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                required_headers = {"blender", "japanese", "english"}
                if not required_headers.issubset(set(reader.fieldnames or [])):
                    missing = required_headers - set(reader.fieldnames or [])
                    self.report(
                        {"ERROR"},
                        f"Missing required headers in CSV: {', '.join(missing)}",
                    )
                    return {"CANCELLED"}

                visible_indices = [
                    i.value
                    for i in mmd_translation.filtered_translation_element_indices
                ]
                translation_elements_list = list(mmd_translation.translation_elements)
                row_count = 0

                for row in reader:
                    if row_count >= len(visible_indices):
                        row_count += 1
                        continue

                    element = translation_elements_list[visible_indices[row_count]]

                    b_name = row.get("blender", "").strip()
                    j_name = row.get("japanese", "").strip()
                    e_name = row.get("english", "").strip()

                    updated = False
                    if self.only_update_english_name:
                        if element.name_e != e_name:
                            element.name_e = e_name
                            updated = True
                    else:
                        if element.name != b_name:
                            element.name = b_name
                            updated = True
                        if element.name_j != j_name:
                            element.name_j = j_name
                            updated = True
                        if element.name_e != e_name:
                            element.name_e = e_name
                            updated = True

                    if updated:
                        updated_count += 1

                    row_count += 1

                # Output warnings
                if row_count > len(visible_indices):
                    warnings.append(
                        f"{row_count - len(visible_indices)} extra lines in CSV! (ignored)",
                    )
                elif row_count < len(visible_indices):
                    warnings.append(
                        f"{len(visible_indices) - row_count} missing lines in CSV! (aborted translation)",
                    )
        except Exception as e:
            self.report({"ERROR"}, f"Failed to read CSV: {e}")
            return {"CANCELLED"}

        FnTranslations.update_query(mmd_translation)

        msg = f"Imported {updated_count} entries from CSV"
        if warnings:
            for w in warnings:
                self.report({"WARNING"}, w)
            msg += " with warnings"

        self.report({"INFO"}, msg)
        return {"FINISHED"}
