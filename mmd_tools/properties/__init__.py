# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

import bpy


def patch_library_overridable(prop: "bpy.props._PropertyDeferred") -> "bpy.props._PropertyDeferred":
    """Apply recursively for each mmd_tools property class annotations.
    Args:
        prop: The property to be patched.

    Returns:
        The patched property.
    """
    prop.keywords.setdefault("override", set()).add("LIBRARY_OVERRIDABLE")

    if prop.function.__name__ not in {"PointerProperty", "CollectionProperty"}:
        return prop

    property_type = prop.keywords["type"]
    # The __annotations__ cannot be inherited. Manually search for base classes.
    for inherited_type in (property_type, *property_type.__bases__):
        if not inherited_type.__module__.startswith("mmd_tools.properties"):
            continue
        for annotation in inherited_type.__annotations__.values():
            if not isinstance(annotation, bpy.props._PropertyDeferred):
                continue
            patch_library_overridable(annotation)

    return prop
