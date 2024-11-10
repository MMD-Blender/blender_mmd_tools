# -*- coding: utf-8 -*-
# Copyright 2015 MMD Tools authors
# This file is part of MMD Tools.

import bpy

from ...core.model import FnModel, Model
from . import FnDraw, PT_ProductionPanelBase
from ...properties.morph import MaterialMorph
from ...utils import ItemOp
from ...operators import morph as operators_morph


class MMDMorphToolsPanel(PT_ProductionPanelBase, bpy.types.Panel):
    bl_idname = "OBJECT_PT_mmd_tools_morph_tools"
    bl_label = "Morph Tools"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 4

    def draw(self, context):
        active_obj = context.active_object
        root = FnModel.find_root_object(active_obj)
        if root is None:
            self.layout.label(text="Select a MMD Model")
            return

        rig = Model(root)
        mmd_root = root.mmd_root
        col = self.layout.column()
        row = col.row()
        row.prop(mmd_root, "active_morph_type", expand=True)
        morph_type = mmd_root.active_morph_type

        c = col.column(align=True)
        row = c.row()
        row.template_list("MMD_TOOLS_UL_Morphs", "", mmd_root, morph_type, mmd_root, "active_morph")
        tb = row.column()
        tb1 = tb.column(align=True)
        tb1.operator("mmd_tools.morph_add", text="", icon="ADD")
        tb1.operator("mmd_tools.morph_remove", text="", icon="REMOVE")
        tb1.menu("OBJECT_MT_mmd_tools_morph_menu", text="", icon="DOWNARROW_HLT")
        tb.separator()
        tb1 = tb.column(align=True)
        tb1.operator("mmd_tools.morph_move", text="", icon="TRIA_UP").type = "UP"
        tb1.operator("mmd_tools.morph_move", text="", icon="TRIA_DOWN").type = "DOWN"

        morph = ItemOp.get_by_index(getattr(mmd_root, morph_type), mmd_root.active_morph)
        if morph:
            slider = rig.morph_slider.get(morph.name)
            if slider:
                col.row().prop(slider, "value")

            row = col.row(align=True)
            row.prop(
                mmd_root,
                "morph_panel_show_settings",
                icon="TRIA_DOWN" if mmd_root.morph_panel_show_settings else "TRIA_RIGHT",
                icon_only=True,
                emboss=False,
            )
            row.label(text="Morph Settings")
            if mmd_root.morph_panel_show_settings:
                draw_func = getattr(self, "_draw_%s_data" % morph_type[:-7], None)
                if draw_func:
                    draw_func(context, rig, col, morph)

    def _template_morph_offset_list(self, layout, morph, list_type_name):
        row = layout.row()
        row.template_list(
            list_type_name,
            "",
            morph,
            "data",
            morph,
            "active_data",
        )
        tb = row.column()
        tb1 = tb.column(align=True)
        tb1.operator("mmd_tools.morph_offset_add", text="", icon="ADD")
        tb1.operator("mmd_tools.morph_offset_remove", text="", icon="REMOVE")
        tb.operator("mmd_tools.morph_offset_remove", text="", icon="X").all = True
        return ItemOp.get_by_index(morph.data, morph.active_data)

    def _draw_vertex_data(self, context, rig, col, morph):
        r = col.row()
        col = r.column(align=True)
        for i in rig.meshes():
            shape_keys = i.data.shape_keys
            if shape_keys is None:
                continue
            kb = shape_keys.key_blocks.get(morph.name, None)
            if kb:
                found = row = col.row(align=True)
                row.active = not (i.show_only_shape_key or kb.mute)
                row.operator("mmd_tools.object_select", text=i.name, icon="OBJECT_DATA").name = i.name
                row.prop(kb, "value", text=kb.name)
        if "found" not in locals():
            col.label(text="Not found", icon="INFO")
        else:
            r.operator("mmd_tools.morph_offset_remove", text="", icon="X").all = True

    def _draw_material_data(self, context, rig, col, morph):
        col.label(text=bpy.app.translations.pgettext_iface("Material Offsets (%d)") % len(morph.data))
        data = self._template_morph_offset_list(col, morph, "MMD_TOOLS_UL_MaterialMorphOffsets")
        if data is None:
            return

        c_mat = col.column(align=True)
        c_mat.prop_search(data, "related_mesh", bpy.data, "meshes")

        related_mesh = bpy.data.meshes.get(data.related_mesh, None)
        c_mat.prop_search(data, "material", related_mesh or bpy.data, "materials")

        base_mat_name = data.material
        if "_temp" in base_mat_name:
            col.label(text="This is not a valid base material", icon="ERROR")
            return

        work_mat = bpy.data.materials.get(base_mat_name + "_temp", None)
        use_work_mat = work_mat and related_mesh and work_mat.name in related_mesh.materials
        if not use_work_mat:
            c = col.column()
            row = c.row(align=True)
            if base_mat_name == "":
                row.label(text="This offset affects all materials", icon="INFO")
            else:
                row.operator(operators_morph.CreateWorkMaterial.bl_idname)
                row.operator(operators_morph.ClearTempMaterials.bl_idname, text="Clear")

            row = c.row()
            row.prop(data, "offset_type", expand=True)
            r1 = row.row(align=True)
            r1.operator(operators_morph.InitMaterialOffset.bl_idname, text="", icon="TRIA_LEFT").target_value = 0
            r1.operator(operators_morph.InitMaterialOffset.bl_idname, text="", icon="TRIA_RIGHT").target_value = 1
            row = c.row()
            row.column(align=True).prop(data, "diffuse_color", expand=True, slider=True)
            c1 = row.column(align=True)
            c1.prop(data, "specular_color", expand=True, slider=True)
            c1.prop(data, "shininess", slider=True)
            row.column(align=True).prop(data, "ambient_color", expand=True, slider=True)
            row = c.row()
            row.column(align=True).prop(data, "edge_color", expand=True, slider=True)
            row = c.row()
            row.prop(data, "edge_weight", slider=True)
            row = c.row()
            row.column(align=True).prop(data, "texture_factor", expand=True, slider=True)
            row.column(align=True).prop(data, "sphere_texture_factor", expand=True, slider=True)
            row.column(align=True).prop(data, "toon_texture_factor", expand=True, slider=True)
        else:
            c_mat.enabled = False
            c = col.column()
            row = c.row(align=True)
            row.operator(operators_morph.ApplyMaterialOffset.bl_idname, text="Apply")
            row.operator(operators_morph.ClearTempMaterials.bl_idname, text="Clear")

            row = c.row()
            row.prop(data, "offset_type")
            row = c.row()
            row.prop(work_mat.mmd_material, "diffuse_color")
            row.prop(work_mat.mmd_material, "alpha", slider=True)
            row = c.row()
            row.prop(work_mat.mmd_material, "specular_color")
            row.prop(work_mat.mmd_material, "shininess", slider=True)
            row = c.row()
            row.prop(work_mat.mmd_material, "ambient_color")
            row.label()  # for alignment only
            row = c.row()
            row.prop(work_mat.mmd_material, "edge_color")
            row.prop(work_mat.mmd_material, "edge_weight", slider=True)
            row = c.row()
            row.column(align=True).prop(data, "texture_factor", expand=True, slider=True)
            row.column(align=True).prop(data, "sphere_texture_factor", expand=True, slider=True)
            row.column(align=True).prop(data, "toon_texture_factor", expand=True, slider=True)

    def _draw_bone_data(self, context, rig, col, morph):
        armature = rig.armature()
        if armature is None:
            col.label(text="Armature not found", icon="ERROR")
            return

        row = col.row(align=True)
        row.operator(operators_morph.ViewBoneMorph.bl_idname, text="View")
        row.operator(operators_morph.ApplyBoneMorph.bl_idname, text="Apply")
        row.operator(operators_morph.ClearBoneMorphView.bl_idname, text="Clear")

        col.label(text=bpy.app.translations.pgettext_iface("Bone Offsets (%d)") % len(morph.data))
        data = self._template_morph_offset_list(col, morph, "MMD_TOOLS_UL_BoneMorphOffsets")
        if data is None:
            return

        row = col.row(align=True)
        row.prop_search(data, "bone", armature.pose, "bones")
        if data.bone:
            row = col.row(align=True)
            row.operator(operators_morph.SelectRelatedBone.bl_idname, text="Select")
            row.operator(operators_morph.EditBoneOffset.bl_idname, text="Edit")
            row.operator(operators_morph.ApplyBoneOffset.bl_idname, text="Update")

        row = col.row()
        row.column(align=True).prop(data, "location")
        row.column(align=True).prop(data, "rotation")

    def _draw_uv_data(self, context, rig, col, morph):
        c = col.column(align=True)
        row = c.row(align=True)
        row.operator(operators_morph.ViewUVMorph.bl_idname, text="View")
        row.operator(operators_morph.ClearUVMorphView.bl_idname, text="Clear")
        row = c.row(align=True)
        row.operator(operators_morph.EditUVMorph.bl_idname, text="Edit")
        row.operator(operators_morph.ApplyUVMorph.bl_idname, text="Apply")

        c = col.column()
        if len(morph.data):
            row = c.row()
            row.prop(morph, "data_type", expand=True)
        row = c.row()
        if morph.data_type == "VERTEX_GROUP":
            row.prop(morph, "vertex_group_scale", text="Scale")
        else:
            row.label(text=bpy.app.translations.pgettext_iface("UV Offsets (%d)") % len(morph.data))
            # self._template_morph_offset_list(c, morph, 'MMD_TOOLS_UL_UVMorphOffsets')
        row.prop(morph, "uv_index")
        row.operator("mmd_tools.morph_offset_remove", text="", icon="X").all = True

    def _draw_group_data(self, context, rig, col, morph):
        col.label(text=bpy.app.translations.pgettext_iface("Group Offsets (%d)") % len(morph.data))
        item = self._template_morph_offset_list(col, morph, "MMD_TOOLS_UL_GroupMorphOffsets")
        if item is None:
            return

        c = col.column(align=True)
        row = c.split(factor=0.67, align=True)
        row.prop_search(item, "name", morph.id_data.mmd_root, item.morph_type, icon="SHAPEKEY_DATA", text="")
        row.prop(item, "morph_type", text="")


class MMD_TOOLS_UL_Morphs(bpy.types.UIList):
    def draw_item(self, _context, layout, data, item, icon, _active_data, _active_propname, _index):
        mmd_root = data
        if self.layout_type in {"DEFAULT"}:
            row = layout.split(factor=0.4, align=True)
            row.prop(item, "name", text="", emboss=False, icon="SHAPEKEY_DATA")
            row = row.split(factor=0.6, align=True)
            row.prop(item, "name_e", text="", emboss=True)
            row = row.row(align=True)
            row.prop(item, "category", text="", emboss=False)
            frame_facial = mmd_root.display_item_frames.get("表情")
            morph_item = frame_facial.data.get(item.name) if frame_facial else None
            if morph_item is None:
                row.label(icon="INFO")
            elif morph_item.morph_type != mmd_root.active_morph_type:
                row.label(icon="SHAPEKEY_DATA")
            else:
                row.label(icon="BLANK1")
            if isinstance(item, MaterialMorph) and any(not d.material for d in item.data):
                row.label(icon="TEMP")
        elif self.layout_type in {"COMPACT"}:
            pass
        elif self.layout_type in {"GRID"}:
            layout.alignment = "CENTER"
            layout.label(text="", icon_value=icon)


class MMD_TOOLS_UL_MaterialMorphOffsets(bpy.types.UIList):
    def draw_item(self, _context, layout, _data, item, icon, _active_data, _active_propname, _index):
        if self.layout_type in {"DEFAULT"}:
            material = item.material
            layout.label(text=material or "All Materials", translate=False, icon="MATERIAL")
        elif self.layout_type in {"COMPACT"}:
            pass
        elif self.layout_type in {"GRID"}:
            layout.alignment = "CENTER"
            layout.label(text="", icon_value=icon)


class MMD_TOOLS_UL_UVMorphOffsets(bpy.types.UIList):
    def draw_item(self, _context, layout, _data, item, icon, _active_data, _active_propname, _index):
        if self.layout_type in {"DEFAULT"}:
            layout.label(text=str(item.index), translate=False, icon="MESH_DATA")
            layout.prop(item, "offset", text="", emboss=False, slider=True)
        elif self.layout_type in {"COMPACT"}:
            pass
        elif self.layout_type in {"GRID"}:
            layout.alignment = "CENTER"
            layout.label(text="", icon_value=icon)


class MMD_TOOLS_UL_BoneMorphOffsets(bpy.types.UIList):
    def draw_item(self, _context, layout, _data, item, icon, _active_data, _active_propname, _index):
        if self.layout_type in {"DEFAULT"}:
            layout.prop(item, "bone", text="", emboss=False, icon="BONE_DATA")
            FnDraw.draw_bone_special(layout, FnModel.find_armature_object(item.id_data), item.bone)
        elif self.layout_type in {"COMPACT"}:
            pass
        elif self.layout_type in {"GRID"}:
            layout.alignment = "CENTER"
            layout.label(text="", icon_value=icon)


class MMD_TOOLS_UL_GroupMorphOffsets(bpy.types.UIList):
    def draw_item(self, _context, layout, _data, item, icon, _active_data, _active_propname, _index):
        if self.layout_type in {"DEFAULT"}:
            row = layout.split(factor=0.5, align=True)
            row.prop(item, "name", text="", emboss=False, icon="SHAPEKEY_DATA")
            row = row.row(align=True)
            row.prop(item, "morph_type", text="", emboss=False)
            if item.name in getattr(item.id_data.mmd_root, item.morph_type):
                row.prop(item, "factor", text="", emboss=False, slider=True)
            else:
                row.label(icon="ERROR")
        elif self.layout_type in {"COMPACT"}:
            pass
        elif self.layout_type in {"GRID"}:
            layout.alignment = "CENTER"
            layout.label(text="", icon_value=icon)


class MMDMorphMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_mmd_tools_morph_menu"
    bl_label = "Morph Menu"

    def draw(self, context):
        layout = self.layout
        layout.operator("mmd_tools.morph_remove", text="Delete All", icon="X").all = True
        layout.separator()
        layout.operator("mmd_tools.morph_slider_setup", text="Bind morphs to .placeholder", icon="DRIVER").type = "BIND"
        layout.operator("mmd_tools.morph_slider_setup", text="Unbind morphs from .placeholder", icon="UNLINKED").type = "UNBIND"
        layout.separator()
        layout.operator("mmd_tools.morph_copy", icon="COPY_ID")
        layout.operator("mmd_tools.morph_overwrite_from_active_pose_library", icon="PRESET_NEW")
        layout.operator("mmd_tools.clean_duplicated_material_morphs", icon="TRASH")
        layout.separator()
        layout.operator("mmd_tools.morph_move", icon="TRIA_UP_BAR", text="Move To Top").type = "TOP"
        layout.operator("mmd_tools.morph_move", icon="TRIA_DOWN_BAR", text="Move To Bottom").type = "BOTTOM"
