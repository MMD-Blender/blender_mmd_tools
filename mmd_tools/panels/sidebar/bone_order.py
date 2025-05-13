# Copyright 2016 MMD Tools authors
# This file is part of MMD Tools.

import bpy

from ...core.bone import BONE_COLLECTION_NAME_DUMMY, BONE_COLLECTION_NAME_SHADOW, FnBone, MigrationFnBone
from ...core.model import FnModel
from . import PT_ProductionPanelBase


class MMDToolsBoneIdMoveUp(bpy.types.Operator):
    bl_idname = "mmd_tools.bone_id_move_up"
    bl_label = "Move Bone ID Up"
    bl_description = "Move active bone up in bone order"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        root = FnModel.find_root_object(context.object)
        armature = FnModel.find_armature_object(root)

        if not root or not armature:
            return {'CANCELLED'}

        active_bone_index = root.mmd_root.active_bone_index
        if active_bone_index >= len(armature.pose.bones):
            return {'CANCELLED'}

        active_bone = armature.pose.bones[active_bone_index]
        active_id = active_bone.mmd_bone.bone_id

        # Find bone with smaller bone_id
        prev_bone = None
        prev_id = -1

        for bone in armature.pose.bones:
            is_shadow = getattr(bone, 'is_mmd_shadow_bone', False) is True
            if not is_shadow and bone.mmd_bone.bone_id < active_id and bone.mmd_bone.bone_id > prev_id:
                prev_bone = bone
                prev_id = bone.mmd_bone.bone_id

        if prev_bone:
            # safe swap bone IDs
            FnModel.swap_bone_ids(active_bone, prev_bone, root.mmd_root.bone_morphs, armature.pose.bones)

            # Refresh UI
            for area in context.screen.areas:
                area.tag_redraw()

        return {'FINISHED'}


class MMDToolsBoneIdMoveDown(bpy.types.Operator):
    bl_idname = "mmd_tools.bone_id_move_down"
    bl_label = "Move Bone ID Down"
    bl_description = "Move active bone down in bone order"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        root = FnModel.find_root_object(context.object)
        armature = FnModel.find_armature_object(root)

        if not root or not armature:
            return {'CANCELLED'}

        active_bone_index = root.mmd_root.active_bone_index
        if active_bone_index >= len(armature.pose.bones):
            return {'CANCELLED'}

        active_bone = armature.pose.bones[active_bone_index]
        active_id = active_bone.mmd_bone.bone_id

        # Find bone with larger bone_id
        next_bone = None
        next_id = float('inf')

        for bone in armature.pose.bones:
            is_shadow = getattr(bone, 'is_mmd_shadow_bone', False) is True
            if not is_shadow and bone.mmd_bone.bone_id > active_id and bone.mmd_bone.bone_id < next_id:
                next_bone = bone
                next_id = bone.mmd_bone.bone_id

        if next_bone:
            # safe swap bone IDs
            FnModel.swap_bone_ids(active_bone, next_bone, root.mmd_root.bone_morphs, armature.pose.bones)

            # Refresh UI
            for area in context.screen.areas:
                area.tag_redraw()

        return {'FINISHED'}


class MMDToolsBoneIdMoveTop(bpy.types.Operator):
    bl_idname = "mmd_tools.bone_id_move_top"
    bl_label = "Move Bone ID to Top"
    bl_description = "Move active bone to the top of bone order"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        root = FnModel.find_root_object(context.object)
        armature = FnModel.find_armature_object(root)

        if not root or not armature:
            return {'CANCELLED'}

        active_bone_index = root.mmd_root.active_bone_index
        if active_bone_index >= len(armature.pose.bones):
            return {'CANCELLED'}

        active_bone = armature.pose.bones[active_bone_index]

        # Change bone ID to 0 safely
        FnModel.safe_change_bone_id(active_bone, 0, root.mmd_root.bone_morphs, armature.pose.bones)

        # Refresh UI
        for area in context.screen.areas:
            area.tag_redraw()

        return {'FINISHED'}


class MMDToolsBoneIdMoveBottom(bpy.types.Operator):
    bl_idname = "mmd_tools.bone_id_move_bottom"
    bl_label = "Move Bone ID to Bottom"
    bl_description = "Move active bone to the bottom of bone order"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        root = FnModel.find_root_object(context.object)
        armature = FnModel.find_armature_object(root)

        if not root or not armature:
            return {'CANCELLED'}

        active_bone_index = root.mmd_root.active_bone_index
        if active_bone_index >= len(armature.pose.bones):
            return {'CANCELLED'}

        active_bone = armature.pose.bones[active_bone_index]

        # Get the maximum bone ID and add 1 to place at the bottom
        max_bone_id = FnModel.get_max_bone_id(armature.pose.bones)
        FnModel.safe_change_bone_id(active_bone, max_bone_id + 1, root.mmd_root.bone_morphs, armature.pose.bones)

        # Refresh UI
        for area in context.screen.areas:
            area.tag_redraw()

        return {'FINISHED'}


class MMDToolsRealignBoneIds(bpy.types.Operator):
    bl_idname = "mmd_tools.fix_bone_order"
    bl_label = "Realign Bone IDs"
    bl_description = "Realign bone IDs to be sequential without gaps and apply additional transforms"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        root = FnModel.find_root_object(context.object)
        armature = FnModel.find_armature_object(root)

        if not root or not armature:
            return {'CANCELLED'}

        # Migrate bone layers from Blender 3.6 and earlier to bone collections in newer versions
        self.check_and_rename_collections(armature)

        # Check if this is an old model with vertex group ordering
        bone_order_mesh_object = self.find_old_bone_order_mesh_object(root)
        if bone_order_mesh_object:
            self.migrate_from_vertex_groups(bone_order_mesh_object, armature, root)
        else:
            # safe realign bone IDs
            FnModel.realign_bone_ids(armature.pose.bones, 0, root.mmd_root.bone_morphs, armature.pose.bones)

        # Apply additional transformation (Assembly -> Bone button) (Very Slow)
        MigrationFnBone.fix_mmd_ik_limit_override(armature)
        FnBone.apply_additional_transformation(armature)

        # Refresh UI
        for area in context.screen.areas:
            area.tag_redraw()

        return {'FINISHED'}

    def check_and_rename_collections(self, armature_object):
        """
        Migrate bone layers from Blender 3.6 and earlier to the MMD Tools bone collection system.

        When opening files from older Blender versions, bone layers are converted to collections
        named 'Layer 1', 'Layer 9', etc. This function checks if these collections exist and if
        the bones within them have the correct is_mmd_shadow_bone property values. If all
        conditions are met, it renames the collections to the special MMD collection names
        required by the plugin.
        """
        bone_collections = armature_object.data.collections

        # Define collections to check and their MMD equivalents
        collection_map = {
            "Layer 1": {"new_name": "mmd_normal", "should_be_shadow": False},
            "Layer 9": {"new_name": BONE_COLLECTION_NAME_SHADOW, "should_be_shadow": True},
            "Layer 10": {"new_name": BONE_COLLECTION_NAME_DUMMY, "should_be_shadow": True}
        }

        # Check if all three collections exist
        if not all(old_name in bone_collections for old_name in collection_map.keys()):
            return

        # Check if bones in each collection have the correct is_mmd_shadow_bone property
        all_conditions_met = True

        for old_name, settings in collection_map.items():
            collection = bone_collections[old_name]
            should_be_shadow = settings["should_be_shadow"]

            # Check all bones in this collection
            for bone in collection.bones:
                pose_bone = armature_object.pose.bones.get(bone.name)
                if pose_bone:
                    is_shadow = getattr(pose_bone, 'is_mmd_shadow_bone', False)
                    if is_shadow != should_be_shadow:
                        all_conditions_met = False
                        break

            if not all_conditions_met:
                break

        # If all conditions are met, rename the collections
        if all_conditions_met:
            self.report({'INFO'}, "Converting layer collections to MMD collections")
            for old_name, settings in collection_map.items():
                new_name = settings["new_name"]
                if old_name in bone_collections and new_name not in bone_collections:
                    bone_collections[old_name].name = new_name

    def find_old_bone_order_mesh_object(self, root_object):
        """Find mesh object with mmd_bone_order_override modifier"""
        if root_object is None:
            return None

        armature = FnModel.find_armature_object(root_object)
        if armature is None:
            return None

        for mesh in armature.children:
            if mesh.type != 'MESH':
                continue
            for mod in mesh.modifiers:
                if mod.type == 'ARMATURE' and mod.name == 'mmd_bone_order_override':
                    return mesh
        return None

    def migrate_from_vertex_groups(self, mesh_object, armature, root):
        """Migrate bone order from vertex groups to bone_id"""
        self.report({'INFO'}, "Migrating from old vertex group ordering to bone_id system")

        # Create mapping from bone name to index in vertex_groups
        vg_index_map = {}
        for i, vg in enumerate(mesh_object.vertex_groups):
            if vg.name in armature.pose.bones:
                vg_index_map[vg.name] = i

        # Assign bone_id based on vertex group index
        next_id = 0
        for bone in sorted(armature.pose.bones, key=lambda b: vg_index_map.get(b.name, float('inf'))):
            is_shadow = getattr(bone, 'is_mmd_shadow_bone', False) is True
            if is_shadow:
                continue

            if bone.name in vg_index_map:
                FnModel.safe_change_bone_id(bone, next_id, root.mmd_root.bone_morphs, armature.pose.bones)
                next_id += 1

        # Rename the mmd_bone_order_override modifier of the mesh
        for modifier in mesh_object.modifiers:
            if modifier.name == 'mmd_bone_order_override':
                modifier.name = 'mmd_armature'
                break

        self.report({'INFO'}, f"Successfully migrated {next_id} bones from vertex groups to bone_id system")


class MMD_TOOLS_UL_ModelBones(bpy.types.UIList):
    # Static data for bone relationships
    _IK_MAP = {}
    _IK_BONES = {}
    _bone_order_map = {}

    @classmethod
    def update_bone_tables(cls, armature):
        """Update bone relationship tables"""
        cls._IK_MAP.clear()
        cls._IK_BONES.clear()
        cls._bone_order_map.clear()

        # Process IK relationships
        valid_bone_count = 0

        for bone in armature.pose.bones:
            is_shadow = getattr(bone, 'is_mmd_shadow_bone', False) is True
            if is_shadow:
                continue

            valid_bone_count += 1

            # Process IK constraints
            for constraint in bone.constraints:
                if constraint.type == "IK" and constraint.subtarget in armature.pose.bones:
                    if not constraint.use_tail:
                        cls._IK_MAP.setdefault(hash(bone), []).append(constraint.subtarget)
                        cls._IK_BONES[constraint.subtarget] = hash(bone)
                        bone_chain = bone.parent_recursive
                    else:
                        cls._IK_BONES[constraint.subtarget] = bone.name
                        bone_chain = [bone] + bone.parent_recursive

                    # Add all bones in IK chain
                    for linked_bone in bone_chain[:constraint.chain_count]:
                        cls._IK_MAP.setdefault(hash(linked_bone), []).append(constraint.subtarget)

        # Process special IK connections
        for subtarget, value in tuple(cls._IK_BONES.items()):
            if isinstance(value, str):
                target_bone = cls.__get_ik_target_bone(armature.pose.bones[value])
                if target_bone:
                    cls._IK_BONES[subtarget] = hash(target_bone)
                    cls._IK_MAP.setdefault(hash(target_bone), []).append(subtarget)
                else:
                    del cls._IK_BONES[subtarget]

        # Update bone sorting
        cls.update_sorted_bones(armature)

        return valid_bone_count

    @classmethod
    def update_sorted_bones(cls, armature):
        """Update bone order mapping"""
        cls._bone_order_map.clear()

        # Create index to bone_id mapping
        bone_id_list = []
        for i, bone in enumerate(armature.pose.bones):
            is_shadow = getattr(bone, 'is_mmd_shadow_bone', False) is True
            if not is_shadow:
                bone_id = bone.mmd_bone.bone_id if hasattr(bone.mmd_bone, 'bone_id') else -1
                bone_id_list.append((i, bone_id))

        # Sort by bone_id
        bone_id_list.sort(key=lambda x: x[1] if x[1] >= 0 else float('inf'))

        # Create order mapping
        for new_idx, (orig_idx, _) in enumerate(bone_id_list):
            cls._bone_order_map[orig_idx] = new_idx

    @staticmethod
    def __get_ik_target_bone(target_bone):
        """Find the IK target bone from a parent bone"""
        r = None
        min_length = None
        for child in target_bone.children:
            is_shadow = getattr(child, 'is_mmd_shadow_bone', False) is True
            if is_shadow:
                continue
            if child.bone.use_connect:
                return child
            length = (child.head - target_bone.tail).length
            if min_length is None or length < min_length:
                min_length = length
                r = child
        return r

    def filter_items(self, context, data, propname):
        """Filter and sort items"""
        bones = getattr(data, propname)
        bone_count = len(bones)

        # Filter out shadow bones
        filtered_flags = []
        for bone in bones:
            is_shadow = getattr(bone, 'is_mmd_shadow_bone', False) is True
            if is_shadow:
                filtered_flags.append(0)  # Filter out shadow bones
            else:
                filtered_flags.append(self.bitflag_filter_item)  # Show non-shadow bones

        # Use defined sort order
        if not self._bone_order_map:
            # If no sort mapping yet, update once
            self.update_sorted_bones(data)

        ordered_indices = []
        for i in range(bone_count):
            if filtered_flags[i]:  # Only sort displayed bones
                ordered_indices.append(self._bone_order_map.get(i, i))
            else:
                ordered_indices.append(i)  # Keep filtered items in original position

        return filtered_flags, ordered_indices

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {"DEFAULT"}:
            self._draw_bone_item(layout, item)
        elif self.layout_type in {"GRID"}:
            layout.alignment = "CENTER"
            layout.label(text="", icon_value=icon)

    @classmethod
    def _draw_bone_item(cls, layout, bone):
        """Draw a single bone item in the UI list"""
        is_shadow = False
        if bone:
            is_shadow = getattr(bone, 'is_mmd_shadow_bone', False) is True

        if not bone or is_shadow:
            layout.active = False
            layout.label(text=bone.name if bone else "", translate=False, icon="GROUP_BONE" if bone else "MESH_DATA")
            return

        bone_id = bone.mmd_bone.bone_id if bone.mmd_bone.bone_id >= 0 else -1

        # Check for duplicate bone_id
        has_duplicate = False
        if bone_id >= 0:
            for other_bone in bone.id_data.pose.bones:
                if other_bone != bone and not getattr(other_bone, 'is_mmd_shadow_bone', False) and other_bone.mmd_bone.bone_id == bone_id:
                    has_duplicate = True
                    break

        count = len(bone.id_data.pose.bones)
        bone_transform_rank = bone_id + bone.mmd_bone.transform_order * count

        row = layout.split(factor=0.45, align=False)
        r0 = row.row()
        r0.label(text=bone.name, translate=False, icon="POSE_HLT" if bone.name in cls._IK_BONES else "BONE_DATA")
        r = r0.row()
        r.alignment = "RIGHT"

        # Show warning icon for duplicate bone_id
        if has_duplicate:
            r.label(text=str(bone_id), icon="ERROR")
        else:
            r.label(text=str(bone_id))

        row_sub = row.split(factor=0.67, align=False)

        # Display bone relationships
        r = row_sub.row()

        # Display parent bone
        bone_parent = bone.parent
        if bone_parent:
            parent_bone_id = bone_parent.mmd_bone.bone_id if bone_parent.mmd_bone.bone_id >= 0 else -1
            parent_icon = "ERROR"
            if parent_bone_id >= 0:
                if bone_transform_rank >= (parent_bone_id + bone_parent.mmd_bone.transform_order * count):
                    parent_icon = "INFO" if bone_id < parent_bone_id else "FILE_PARENT"
            r.label(text=str(parent_bone_id), icon=parent_icon)
        else:
            r.label()

        # Display additional transforms
        r = r.row()
        mmd_bone = bone.mmd_bone
        if mmd_bone.has_additional_rotation or mmd_bone.has_additional_location:
            append_bone_name = mmd_bone.additional_transform_bone
            if append_bone_name in bone.id_data.pose.bones:
                append_bone = bone.id_data.pose.bones[append_bone_name]
                append_bone_id = append_bone.mmd_bone.bone_id if append_bone.mmd_bone.bone_id >= 0 else -1

                icon = "ERROR"
                if append_bone_id >= 0 and bone_transform_rank >= (append_bone_id + append_bone.mmd_bone.transform_order * count):
                    if mmd_bone.has_additional_rotation and mmd_bone.has_additional_location:
                        icon = "IPO_QUAD"
                    elif mmd_bone.has_additional_rotation:
                        icon = "IPO_EXPO"
                    else:
                        icon = "IPO_LINEAR"

                if append_bone_name:
                    r.label(text=str(append_bone_id), icon=icon)

        # Display IK connections with index-based sorting (like the old version)
        ik_bones_data = []
        for ik_bone_name in cls._IK_MAP.get(hash(bone), []):
            ik_bone = bone.id_data.pose.bones[ik_bone_name]
            ik_bone_id = ik_bone.mmd_bone.bone_id if ik_bone.mmd_bone.bone_id >= 0 else -1
            is_ik_chain = hash(bone) != cls._IK_BONES.get(ik_bone_name)

            icon = "LINKED" if is_ik_chain else "HOOK"
            if ik_bone_id < 0:
                icon = "ERROR"
            elif is_ik_chain and bone_transform_rank > (ik_bone_id + ik_bone.mmd_bone.transform_order * count):
                icon = "ERROR"

            # Store for sorting
            ik_bones_data.append((ik_bone_id, ik_bone, icon))

        # Sort by bone_id (similar to the old version's vertex_group index sorting)
        for bone_id, ik_bone, icon in sorted(ik_bones_data, key=lambda x: x[0] if x[0] >= 0 else float('inf')):
            r.prop(ik_bone, "mmd_ik_toggle", text=str(bone_id), toggle=True, icon=icon)

        # Display transform order and post-dynamics transform
        row = row_sub.row(align=True)
        # Use a specific icon name instead of None
        if mmd_bone.transform_after_dynamics:
            row.prop(mmd_bone, "transform_after_dynamics", text="", toggle=True, icon="PHYSICS")
        else:
            row.prop(mmd_bone, "transform_after_dynamics", text="", toggle=True, icon="BLANK1")
        row.prop(mmd_bone, "transform_order", text="", slider=bool(mmd_bone.transform_order))


class MMDBoneOrderMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_mmd_tools_bone_order_menu"
    bl_label = "Bone Order Menu"

    def draw(self, _context):
        layout = self.layout
        layout.operator("mmd_tools.fix_bone_order", text="Fix Bone Order", icon="LINENUMBERS_ON")


class MMDBoneOrder(PT_ProductionPanelBase, bpy.types.Panel):
    bl_idname = "OBJECT_PT_mmd_tools_bone_order"
    bl_label = "Bone Order"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 6

    def draw(self, context):
        layout = self.layout
        active_obj = context.active_object
        root = FnModel.find_root_object(active_obj)
        if root is None:
            layout.label(text="Select a MMD Model")
            return

        armature = FnModel.find_armature_object(root)
        if armature is None:
            layout.label(text="The armature object of active MMD model can't be found", icon="ERROR")
            return

        # Update bone tables
        valid_bone_count = MMD_TOOLS_UL_ModelBones.update_bone_tables(armature)

        # UI
        col = layout.column(align=True)
        row = col.row()

        # Bone list sorted by bone_id
        row.template_list("MMD_TOOLS_UL_ModelBones", "", armature.pose, "bones", root.mmd_root, "active_bone_index")

        # Bone order controls
        tb = row.column()
        tb1 = tb.column(align=True)
        # a hard-to-notice small triangle button
        # tb1.menu("OBJECT_MT_mmd_tools_bone_order_menu", text="", icon="DOWNARROW_HLT")
        # tb.separator()
        tb1 = tb.column(align=True)
        tb1.operator("mmd_tools.bone_id_move_top", text="", icon="TRIA_UP_BAR")
        tb1.operator("mmd_tools.bone_id_move_up", text="", icon="TRIA_UP")
        tb1.operator("mmd_tools.bone_id_move_down", text="", icon="TRIA_DOWN")
        tb1.operator("mmd_tools.bone_id_move_bottom", text="", icon="TRIA_DOWN_BAR")

        # Display total bone count with action buttons
        row = col.row(align=True)
        row.label(text=bpy.app.translations.pgettext_iface("Total Bones: %d") % valid_bone_count)
        row.operator("mmd_tools.fix_bone_order", text="Fix Bone Order", icon="LINENUMBERS_ON")
