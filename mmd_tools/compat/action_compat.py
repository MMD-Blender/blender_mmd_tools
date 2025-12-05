# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

"""
Simplest compatibility layer for Action.

Only the first channelbag of ActionChannelbag is used,
preserving the behavior of the previous version.
Although ActionChannelbag was introduced in Blender 4.4,
since MMD Tools works well in 4.2–4.5, use it only in Blender 5.0+.
"""

import bpy

from .versions import IS_BLENDER_50_UP

if IS_BLENDER_50_UP:
    FCurvesCollection = bpy.types.ActionChannelbagFCurves
else:
    FCurvesCollection = bpy.types.ActionFCurves


class ActionGroupsCompatibility:
    """Compatibility layer: Makes Action.groups work in Blender 5.0+"""

    def __init__(self, action: bpy.types.Action):
        self._action = action

    def _get_channelbag(self):
        """Get the first channelbag"""
        if not hasattr(self._action, "layers"):
            return None

        if len(self._action.layers) == 0:
            return None

        layer = self._action.layers[0]
        if not hasattr(layer, "strips") or len(layer.strips) == 0:
            return None

        strip = layer.strips[0]
        if not hasattr(strip, "channelbags"):
            return None

        channelbags = strip.channelbags
        if len(channelbags) == 0:
            return None

        return channelbags[0]

    def new(self, name: str):
        """Create a new action group"""
        channelbag = self._get_channelbag()
        if channelbag is None:
            # Need to create channelbag structure first
            # Use ActionFCurvesCompatibility logic here
            fcurves_compat = ActionFCurvesCompatibility(self._action)
            channelbag = fcurves_compat._get_channelbag(ensure=True)
            if channelbag is None:
                raise RuntimeError("Cannot create action group: failed to get or create channelbag")

        return channelbag.groups.new(name)

    def remove(self, action_group):
        """Remove action group"""
        channelbag = self._get_channelbag()
        if channelbag is not None:
            channelbag.groups.remove(action_group)

    def __iter__(self):
        """Iterate all groups"""
        channelbag = self._get_channelbag()
        if channelbag is not None:
            return iter(channelbag.groups)
        return iter([])

    def __len__(self):
        """Get the number of groups"""
        channelbag = self._get_channelbag()
        if channelbag is not None:
            return len(channelbag.groups)
        return 0

    def __getitem__(self, key):
        """Access group by index or name"""
        channelbag = self._get_channelbag()
        if channelbag is not None:
            return channelbag.groups[key]
        raise IndexError("No channelbag available")

    def __bool__(self):
        """Check if there are groups"""
        return len(self) > 0


class ActionFCurvesCompatibility:
    """Compatibility layer: Makes Action.fcurves work in Blender 5.0+"""

    def __init__(self, action: bpy.types.Action):
        self._action = action

    def _ensure_layer_and_strip(self):
        """Ensure Action has at least one layer and strip"""
        action = self._action

        # Ensure there is a layer
        if not hasattr(action, "layers") or len(action.layers) == 0:
            if hasattr(action, "layers") and hasattr(action.layers, "new"):
                layer = action.layers.new(name="Layer")
            else:
                return None, None
        else:
            layer = action.layers[0]

        # Ensure there is a strip
        if not hasattr(layer, "strips") or len(layer.strips) == 0:
            if hasattr(layer, "strips") and hasattr(layer.strips, "new"):
                strip = layer.strips.new(type="KEYFRAME")
            else:
                return layer, None
        else:
            strip = layer.strips[0]

        return layer, strip

    def _ensure_slot(self, id_type: str = "OBJECT"):
        """Ensure Action has at least one slot"""
        action = self._action

        if not hasattr(action, "slots") or len(action.slots) == 0:
            if hasattr(action, "slots") and hasattr(action.slots, "new"):
                # Create a default slot
                slot_name = action.name if action.name else "Slot"
                return action.slots.new(name=slot_name, id_type=id_type)
            return None
        return action.slots[0]

    def _get_channelbag(self, ensure=False, id_type: str = "OBJECT"):
        """Get the first channelbag"""
        if not hasattr(self._action, "layers"):
            return None

        if ensure:
            layer, strip = self._ensure_layer_and_strip()
        else:
            if len(self._action.layers) == 0:
                return None
            layer = self._action.layers[0]
            if not hasattr(layer, "strips") or len(layer.strips) == 0:
                return None
            strip = layer.strips[0]

        if layer is None or strip is None:
            return None

        # Get or create channelbag
        if not hasattr(strip, "channelbags"):
            return None

        channelbags = strip.channelbags
        if len(channelbags) == 0:
            if ensure:
                # Ensure there is a slot
                slot = self._ensure_slot(id_type=id_type)
                if slot is None:
                    return None
                return channelbags.new(slot)
            return None

        return channelbags[0]

    def new(self, data_path: str, index: int = 0, group_name: str = "", action_group: str = "", id_type: str = "OBJECT"):
        """Create a new F-Curve (returns existing one if already exists)

        Note: For compatibility with legacy code, when an F-Curve already exists,
        this method returns the existing F-Curve instead of throwing an error.
        This differs from the native behavior in Blender 5.0+, but matches the
        expectations of the old version.

        Args:
            data_path: Data path for the F-Curve
            index: Array index
            group_name: Group name (used in Blender 5.0+)
            action_group: Action group (legacy compatibility parameter, converts to group_name)
            id_type: The ID type for the action slot, e.g. "OBJECT" or "KEY".
        """
        channelbag = self._get_channelbag(ensure=True, id_type=id_type)
        if channelbag is None:
            raise RuntimeError("Cannot create F-Curve: failed to get or create channelbag")

        # Legacy compatibility: If action_group is provided, use it as group_name
        if action_group and not group_name:
            group_name = action_group

        # Check if it already exists first (legacy version behavior)
        existing = channelbag.fcurves.find(data_path, index=index)
        if existing is not None:
            # If group_name is specified, try to update the group
            if group_name and hasattr(existing, "group"):
                # Could try to set the group here, but may need additional logic
                pass
            return existing

        # Create new if it doesn't exist
        try:
            return channelbag.fcurves.new(data_path, index=index, group_name=group_name)
        except RuntimeError as e:
            # If it still reports that it already exists, try to find and return it again
            if "already exists" in str(e):
                existing = channelbag.fcurves.find(data_path, index=index)
                if existing is not None:
                    return existing
            raise

    def ensure(self, data_path: str, index: int = 0, group_name: str = "", action_group: str = "", id_type: str = "OBJECT"):
        """Ensure F-Curve exists

        Args:
            data_path: Data path for the F-Curve
            index: Array index
            group_name: Group name (used in Blender 5.0+)
            action_group: Action group (legacy compatibility parameter, converts to group_name)
            id_type: The ID type for the action slot, e.g. "OBJECT" or "KEY".
        """
        channelbag = self._get_channelbag(ensure=True, id_type=id_type)
        if channelbag is None:
            raise RuntimeError("Cannot ensure F-Curve: failed to get or create channelbag")

        # Legacy compatibility: If action_group is provided, use it as group_name
        if action_group and not group_name:
            group_name = action_group

        return channelbag.fcurves.ensure(data_path, index=index, group_name=group_name)

    def find(self, data_path: str, index: int = 0):
        """Find F-Curve"""
        channelbag = self._get_channelbag(ensure=False)
        if channelbag is None:
            return None
        return channelbag.fcurves.find(data_path, index=index)

    def remove(self, fcurve):
        """Remove F-Curve"""
        channelbag = self._get_channelbag(ensure=False)
        if channelbag is not None:
            channelbag.fcurves.remove(fcurve)

    def clear(self):
        """Clear all F-Curves"""
        channelbag = self._get_channelbag(ensure=False)
        if channelbag is not None:
            channelbag.fcurves.clear()

    def __iter__(self):
        """Iterate all F-Curves"""
        channelbag = self._get_channelbag(ensure=False)
        if channelbag is not None:
            return iter(channelbag.fcurves)
        return iter([])

    def __len__(self):
        """Get the number of F-Curves"""
        channelbag = self._get_channelbag(ensure=False)
        if channelbag is not None:
            return len(channelbag.fcurves)
        return 0

    def __getitem__(self, key):
        """Access F-Curve by index or name"""
        channelbag = self._get_channelbag(ensure=False)
        if channelbag is not None:
            return channelbag.fcurves[key]
        raise IndexError("No channelbag available")

    def __bool__(self):
        """Check if there are F-Curves"""
        return len(self) > 0


def get_action_fcurves(action: bpy.types.Action):
    """Get Action's fcurves (compatible with Blender 5.0+)

    Returns native action.fcurves in Blender 4.x
    Returns compatibility layer object in Blender 5.0+
    """
    if IS_BLENDER_50_UP:
        return ActionFCurvesCompatibility(action)
    return action.fcurves


def get_action_groups(action: bpy.types.Action):
    """Get Action's groups (compatible with Blender 5.0+)

    Returns native action.groups in Blender 4.x
    Returns compatibility layer object in Blender 5.0+
    """
    if IS_BLENDER_50_UP:
        return ActionGroupsCompatibility(action)
    return action.groups


def new_fcurve(action_obj: bpy.types.Action, data_path: str, index: int = 0, group_name: str = "", id_type: str = "OBJECT"):
    """
    Create an F-Curve in a version-independent way.
    Handles the `id_type` argument, available only in Blender 5.0+.
    """
    fcurves = get_action_fcurves(action_obj)

    if IS_BLENDER_50_UP:
        return fcurves.new(data_path, index=index, group_name=group_name, id_type=id_type)
    return fcurves.new(data_path, index=index, action_group=group_name)


def assign_action_to_datablock(datablock, action):
    """Assign Action to datablock and ensure slot is properly set in Blender 5.0+"""
    if not datablock.animation_data:
        datablock.animation_data_create()

    datablock.animation_data.action = action

    if IS_BLENDER_50_UP and action is not None:
        # Auto-create slot if missing
        if not hasattr(action, "slots") or len(action.slots) == 0:
            id_type = "OBJECT"
            if isinstance(datablock, bpy.types.Key):
                id_type = "KEY"
            elif hasattr(datablock, "node_tree"):
                id_type = "NODETREE"

            slot_name = action.name if action.name else "Slot"
            action.slots.new(name=slot_name, id_type=id_type)

        datablock.animation_data.action_slot = action.slots[0]


# Monkey patch to Action objects
def patch_action_fcurves():
    """Patch fcurves and groups properties onto Action objects

    This patch allows Action objects in Blender 5.0+ to be accessed
    directly via action.fcurves and action.groups like the old version,
    without going through the layers -> strips -> channelbags hierarchy.
    """
    if not IS_BLENDER_50_UP:
        return

    # Save the original __getattribute__
    if not hasattr(bpy.types.Action, "_original_getattribute"):
        bpy.types.Action._original_getattribute = bpy.types.Action.__getattribute__

    original_getattr = bpy.types.Action._original_getattribute

    def custom_getattr(self, name):
        if name == "fcurves":
            return ActionFCurvesCompatibility(self)
        if name == "groups":
            return ActionGroupsCompatibility(self)
        return original_getattr(self, name)

    bpy.types.Action.__getattribute__ = custom_getattr


def unpatch_action_fcurves():
    """Remove the fcurves and groups patch"""
    if IS_BLENDER_50_UP and hasattr(bpy.types.Action, "_original_getattribute"):
        bpy.types.Action.__getattribute__ = bpy.types.Action._original_getattribute
        delattr(bpy.types.Action, "_original_getattribute")


def register():
    """Register compatibility layer

    Register fcurves and groups property patch in Blender 5.0+
    """
    if IS_BLENDER_50_UP:
        patch_action_fcurves()


def unregister():
    """Unregister compatibility layer

    Remove fcurves and groups property patch
    """
    if IS_BLENDER_50_UP:
        unpatch_action_fcurves()
