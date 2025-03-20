# -*- coding: utf-8 -*-
# Copyright 2013 MMD Tools authors
# This file is part of MMD Tools.

import contextlib
from typing import Generator, List, Optional, TypeVar

import bpy


class Props:  # For API changes of only name changed properties
    show_in_front = "show_in_front"
    display_type = "display_type"
    display_size = "display_size"
    empty_display_type = "empty_display_type"
    empty_display_size = "empty_display_size"


class __EditMode:
    def __init__(self, obj):
        if not isinstance(obj, bpy.types.Object):
            raise ValueError
        self.__prevMode = obj.mode
        self.__obj = obj
        self.__obj_select = obj.select_get()
        with select_object(obj):
            if obj.mode != "EDIT":
                bpy.ops.object.mode_set(mode="EDIT")

    def __enter__(self):
        return self.__obj.data

    def __exit__(self, type, value, traceback):
        if self.__prevMode == "EDIT":
            bpy.ops.object.mode_set(mode="OBJECT")  # update edited data
        bpy.ops.object.mode_set(mode=self.__prevMode)
        self.__obj.select_set(self.__obj_select)


class __SelectObjects:
    def __init__(self, active_object: bpy.types.Object, selected_objects: Optional[List[bpy.types.Object]] = None):
        if not isinstance(active_object, bpy.types.Object):
            raise ValueError
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass

        contenxt = FnContext.ensure_context()

        for i in contenxt.selected_objects:
            i.select_set(False)

        self.__active_object = active_object
        self.__selected_objects = tuple(set(selected_objects) | set([active_object])) if selected_objects else (active_object,)

        self.__hides: List[bool] = []
        for i in self.__selected_objects:
            self.__hides.append(i.hide_get())
            FnContext.select_object(contenxt, i)
        FnContext.set_active_object(contenxt, active_object)

    def __enter__(self) -> bpy.types.Object:
        return self.__active_object

    def __exit__(self, type, value, traceback):
        for i, j in zip(self.__selected_objects, self.__hides):
            i.hide_set(j)


def setParent(obj, parent):
    with select_object(parent, objects=[parent, obj]):
        bpy.ops.object.parent_set(type="OBJECT", xmirror=False, keep_transform=False)


def setParentToBone(obj, parent, bone_name):
    with select_object(parent, objects=[parent, obj]):
        bpy.ops.object.mode_set(mode="POSE")
        parent.data.bones.active = parent.data.bones[bone_name]
        bpy.ops.object.parent_set(type="BONE", xmirror=False, keep_transform=False)
        bpy.ops.object.mode_set(mode="OBJECT")


def edit_object(obj):
    """Set the object interaction mode to 'EDIT'

    It is recommended to use 'edit_object' with 'with' statement like the following code.

       with edit_object:
           some functions...
    """
    return __EditMode(obj)


def select_object(obj: bpy.types.Object, objects: Optional[List[bpy.types.Object]] = None):
    """Select objects.

    It is recommended to use 'select_object' with 'with' statement like the following code.
    This function can select "hidden" objects safely.

       with select_object(obj):
           some functions...
    """
    # TODO: Reimplement with bpy.context.temp_override (If it ain't broke, don't fix it.)
    return __SelectObjects(obj, objects)


def duplicateObject(obj, total_len):
    return FnContext.duplicate_object(FnContext.ensure_context(), obj, total_len)


def createObject(name="Object", object_data=None, target_scene=None):
    context = FnContext.ensure_context(target_scene)
    return FnContext.set_active_object(context, FnContext.new_and_link_object(context, name, object_data))


def makeSphere(segment=8, ring_count=5, radius=1.0, target_object=None):
    import bmesh

    if target_object is None:
        target_object = createObject(name="Sphere")

    mesh = target_object.data
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(
        bm,
        u_segments=segment,
        v_segments=ring_count,
        radius=radius,
    )
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(mesh)
    bm.free()
    return target_object


def makeBox(size=(1, 1, 1), target_object=None):
    import bmesh
    from mathutils import Matrix

    if target_object is None:
        target_object = createObject(name="Box")

    mesh = target_object.data
    bm = bmesh.new()
    bmesh.ops.create_cube(
        bm,
        size=2,
        matrix=Matrix([[size[0], 0, 0, 0], [0, size[1], 0, 0], [0, 0, size[2], 0], [0, 0, 0, 1]]),
    )
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(mesh)
    bm.free()
    return target_object


def makeCapsule(segment=8, ring_count=2, radius=1.0, height=1.0, target_object=None):
    import math

    import bmesh

    if target_object is None:
        target_object = createObject(name="Capsule")
    height = max(height, 1e-3)

    mesh = target_object.data
    bm = bmesh.new()
    verts = bm.verts
    top = (0, 0, height / 2 + radius)
    verts.new(top)

    # f = lambda i: radius*i/ring_count
    f = lambda i: radius * math.sin(0.5 * math.pi * i / ring_count)
    for i in range(ring_count, 0, -1):
        z = f(i - 1)
        t = math.sqrt(radius**2 - z**2)
        for j in range(segment):
            theta = 2 * math.pi / segment * j
            x = t * math.sin(-theta)
            y = t * math.cos(-theta)
            verts.new((x, y, z + height / 2))

    for i in range(ring_count):
        z = -f(i)
        t = math.sqrt(radius**2 - z**2)
        for j in range(segment):
            theta = 2 * math.pi / segment * j
            x = t * math.sin(-theta)
            y = t * math.cos(-theta)
            verts.new((x, y, z - height / 2))

    bottom = (0, 0, -(height / 2 + radius))
    verts.new(bottom)
    if hasattr(verts, "ensure_lookup_table"):
        verts.ensure_lookup_table()

    faces = bm.faces
    for i in range(1, segment):
        faces.new([verts[x] for x in (0, i, i + 1)])
    faces.new([verts[x] for x in (0, segment, 1)])
    offset = segment + 1
    for i in range(ring_count * 2 - 1):
        for j in range(segment - 1):
            t = offset + j
            faces.new([verts[x] for x in (t - segment, t, t + 1, t - segment + 1)])
        faces.new([verts[x] for x in (offset - 1, offset + segment - 1, offset, offset - segment)])
        offset += segment
    for i in range(segment - 1):
        t = offset + i
        faces.new([verts[x] for x in (t - segment, offset, t - segment + 1)])
    faces.new([verts[x] for x in (offset - 1, offset, offset - segment)])

    for f in bm.faces:
        f.smooth = True
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    return target_object


class TransformConstraintOp:
    __MIN_MAX_MAP = {"ROTATION": "_rot", "SCALE": "_scale"}

    @staticmethod
    def create(constraints, name, map_type):
        c = constraints.get(name, None)
        if c and c.type != "TRANSFORM":
            constraints.remove(c)
            c = None
        if c is None:
            c = constraints.new("TRANSFORM")
            c.name = name
        c.use_motion_extrapolate = True
        c.target_space = c.owner_space = "LOCAL"
        c.map_from = c.map_to = map_type
        c.map_to_x_from = "X"
        c.map_to_y_from = "Y"
        c.map_to_z_from = "Z"
        c.influence = 1
        return c

    @classmethod
    def min_max_attributes(cls, map_type, name_id=""):
        key = (map_type, name_id)
        ret = cls.__MIN_MAX_MAP.get(key, None)
        if ret is None:
            defaults = (i + j + k for i in ("from_", "to_") for j in ("min_", "max_") for k in "xyz")
            extension = cls.__MIN_MAX_MAP.get(map_type, "")
            ret = cls.__MIN_MAX_MAP[key] = tuple(n + extension for n in defaults if name_id in n)
        return ret

    @classmethod
    def update_min_max(cls, constraint, value, influence=1):
        c = constraint
        if not c or c.type != "TRANSFORM":
            return

        for attr in cls.min_max_attributes(c.map_from, "from_min"):
            setattr(c, attr, -value)
        for attr in cls.min_max_attributes(c.map_from, "from_max"):
            setattr(c, attr, value)

        if influence is None:
            return

        for attr in cls.min_max_attributes(c.map_to, "to_min"):
            setattr(c, attr, -value * influence)
        for attr in cls.min_max_attributes(c.map_to, "to_max"):
            setattr(c, attr, value * influence)


class FnObject:
    def __init__(self):
        raise NotImplementedError("This class is not expected to be instantiated.")

    @staticmethod
    def mesh_remove_shape_key(mesh_object: bpy.types.Object, shape_key: bpy.types.ShapeKey):
        assert isinstance(mesh_object.data, bpy.types.Mesh)

        key: bpy.types.Key = shape_key.id_data
        assert key == mesh_object.data.shape_keys

        shape_key_path = shape_key.path_from_id()

        if mesh_object.animation_data is not None:
            fc_curve: bpy.types.FCurve
            for fc_curve in mesh_object.animation_data.drivers:
                if not fc_curve.data_path.startswith(shape_key_path):
                    continue
                mesh_object.driver_remove(fc_curve.data_path)

        key_blocks = key.key_blocks

        last_index = mesh_object.active_shape_key_index or 0
        if last_index >= key_blocks.find(shape_key.name):
            last_index = max(0, last_index - 1)

        mesh_object.shape_key_remove(shape_key)
        mesh_object.active_shape_key_index = min(last_index, len(key_blocks) - 1)


ADDON_PREFERENCE_ATTRIBUTE_VALUE_TYPE = TypeVar("ADDON_PREFERENCE_ATTRIBUTE_VALUE_TYPE")


class FnContext:
    def __init__(self):
        raise NotImplementedError("This class is not expected to be instantiated.")

    @staticmethod
    def ensure_context(context: Optional[bpy.types.Context] = None) -> bpy.types.Context:
        return context or bpy.context

    @staticmethod
    def get_active_object(context: bpy.types.Context) -> Optional[bpy.types.Object]:
        # Added defensive programming for get methods
        # Related to: https://github.com/MMD-Blender/blender_mmd_tools/issues/176
        if context is None or not hasattr(context, 'active_object'):
            return None
        return context.active_object

    @staticmethod
    def set_active_object(context: bpy.types.Context, obj: bpy.types.Object) -> bpy.types.Object:
        context.view_layer.objects.active = obj
        return obj

    @staticmethod
    def set_active_and_select_single_object(context: bpy.types.Context, obj: bpy.types.Object) -> bpy.types.Object:
        return FnContext.set_active_object(context, FnContext.select_single_object(context, obj))

    @staticmethod
    def get_scene_objects(context: bpy.types.Context) -> bpy.types.SceneObjects:
        # Added defensive programming for get methods
        # Added for consistency with get_active_object
        if context is None or not hasattr(context, 'scene') or not hasattr(context.scene, 'objects'):
            return []
        return context.scene.objects

    @staticmethod
    def ensure_selectable(context: bpy.types.Context, obj: bpy.types.Object) -> bpy.types.Object:
        obj.hide_viewport = False
        obj.hide_select = False
        obj.hide_set(False)

        if obj not in context.selectable_objects:

            def __layer_check(layer_collection: bpy.types.LayerCollection) -> bool:
                for lc in layer_collection.children:
                    if __layer_check(lc):
                        lc.hide_viewport = False
                        lc.collection.hide_viewport = False
                        lc.collection.hide_select = False
                        return True
                if obj in layer_collection.collection.objects.values():
                    if layer_collection.exclude:
                        layer_collection.exclude = False
                    return True
                return False

            selected_objects = set(context.selected_objects)
            __layer_check(context.view_layer.layer_collection)
            if len(context.selected_objects) != len(selected_objects):
                for i in context.selected_objects:
                    if i not in selected_objects:
                        i.select_set(False)
        return obj

    @staticmethod
    def select_object(context: bpy.types.Context, obj: bpy.types.Object) -> bpy.types.Object:
        FnContext.ensure_selectable(context, obj).select_set(True)
        return obj

    @staticmethod
    def select_objects(context: bpy.types.Context, *objects: bpy.types.Object) -> List[bpy.types.Object]:
        return [FnContext.select_object(context, obj) for obj in objects]

    @staticmethod
    def select_single_object(context: bpy.types.Context, obj: bpy.types.Object) -> bpy.types.Object:
        for i in context.selected_objects:
            if i != obj:
                i.select_set(False)
        return FnContext.select_object(context, obj)

    @staticmethod
    def link_object(context: bpy.types.Context, obj: bpy.types.Object) -> bpy.types.Object:
        context.collection.objects.link(obj)
        return obj

    @staticmethod
    def new_and_link_object(context: bpy.types.Context, name: str, object_data: Optional[bpy.types.ID]) -> bpy.types.Object:
        return FnContext.link_object(context, bpy.data.objects.new(name=name, object_data=object_data))

    @staticmethod
    def duplicate_object(context: bpy.types.Context, object_to_duplicate: bpy.types.Object, target_count: int) -> List[bpy.types.Object]:
        """
        Duplicate object.

        This function duplicates the given object and returns a list of duplicated objects.

        Args:
            context (bpy.types.Context): The context in which the duplication is performed.
            object_to_duplicate (bpy.types.Object): The object to be duplicated.
            target_count (int): The desired count of duplicated objects.

        Returns:
            List[bpy.types.Object]: A list of duplicated objects.

        Raises:
            AssertionError: If the number of selected objects in the context is not equal to 1 or if the selected object is not the same as the object to be duplicated.
        """
        for o in context.selected_objects:
            o.select_set(False)
        object_to_duplicate.select_set(True)
        assert len(context.selected_objects) == 1
        assert context.selected_objects[0] == object_to_duplicate
        last_selected_objects = result_objects = [object_to_duplicate]
        while len(result_objects) < target_count:
            bpy.ops.object.duplicate()
            result_objects.extend(context.selected_objects)
            remain = target_count - len(result_objects) - len(context.selected_objects)
            if remain < 0:
                last_selected_objects = context.selected_objects
                for i in range(-remain):
                    last_selected_objects[i].select_set(False)
            else:
                for i in range(min(remain, len(last_selected_objects))):
                    last_selected_objects[i].select_set(True)
                last_selected_objects = context.selected_objects
        assert len(result_objects) == target_count
        return result_objects

    @staticmethod
    def find_user_layer_collection_by_object(context: bpy.types.Context, target_object: bpy.types.Object) -> Optional[bpy.types.LayerCollection]:
        """
        Finds the layer collection that contains the given target_object in the user's collections.

        Args:
            context (bpy.types.Context): The Blender context.
            target_object (bpy.types.Object): The target object to find the layer collection for.

        Returns:
            Optional[bpy.types.LayerCollection]: The layer collection that contains the target_object, or None if not found.
        """
        scene_layer_collection: bpy.types.LayerCollection = context.view_layer.layer_collection

        def find_layer_collection_by_name(layer_collection: bpy.types.LayerCollection, name: str) -> Optional[bpy.types.LayerCollection]:
            if layer_collection.name == name:
                return layer_collection

            child_layer_collection: bpy.types.LayerCollection
            for child_layer_collection in layer_collection.children:
                found = find_layer_collection_by_name(child_layer_collection, name)
                if found is not None:
                    return found

            return None

        user_collection: bpy.types.Collection
        for user_collection in target_object.users_collection:
            found = find_layer_collection_by_name(scene_layer_collection, user_collection.name)
            if found is not None:
                return found

        return None

    @staticmethod
    @contextlib.contextmanager
    def temp_override_active_layer_collection(context: bpy.types.Context, target_object: bpy.types.Object) -> Generator[bpy.types.Context, None, None]:
        """
        Context manager to temporarily override the active_layer_collection that contains the target object.

        This context manager allows you to temporarily change the active_layer_collection in the given context to the one that contains the target object.
        It ensures that the original active_layer_collection is restored after the context is exited.

        Args:
            context (bpy.types.Context): The context in which the active_layer_collection will be overridden.
            target_object (bpy.types.Object): The target object whose layer collection will be set as the active_layer_collection.

        Yields:
            bpy.types.Context: The modified context with the active_layer_collection overridden.

        Example:
            with FnContext.temp_override_active_layer_collection(context, target_object):
                # Perform operations with the modified context
                bpy.ops.object.select_all(action='DESELECT')
                target_object.select_set(True)
                bpy.ops.object.delete()

        """
        original_layer_collection = context.view_layer.active_layer_collection
        target_layer_collection = FnContext.find_user_layer_collection_by_object(context, target_object)
        if target_layer_collection is not None:
            context.view_layer.active_layer_collection = target_layer_collection
        try:
            yield context
        finally:
            if context.view_layer.active_layer_collection.name != original_layer_collection.name:
                context.view_layer.active_layer_collection = original_layer_collection

    @staticmethod
    def __get_addon_preferences(context: bpy.types.Context) -> Optional[bpy.types.AddonPreferences]:
        addon: bpy.types.Addon = context.preferences.addons.get(__package__, None)
        return addon.preferences if addon else None

    @staticmethod
    def get_addon_preferences_attribute(context: bpy.types.Context, attribute_name: str, default_value: ADDON_PREFERENCE_ATTRIBUTE_VALUE_TYPE = None) -> ADDON_PREFERENCE_ATTRIBUTE_VALUE_TYPE:
        return getattr(FnContext.__get_addon_preferences(context), attribute_name, default_value)

    @staticmethod
    def temp_override_objects(
        context: bpy.types.Context,
        window: Optional[bpy.types.Window] = None,
        area: Optional[bpy.types.Area] = None,
        region: Optional[bpy.types.Region] = None,
        active_object: Optional[bpy.types.Object] = None,
        selected_objects: Optional[List[bpy.types.Object]] = None,
        **keywords,
    ) -> Generator[bpy.types.Context, None, None]:
        if active_object is not None:
            keywords["active_object"] = active_object
            keywords["object"] = active_object

        if selected_objects is not None:
            keywords["selected_objects"] = selected_objects
            keywords["selected_editable_objects"] = selected_objects

        return context.temp_override(window=window, area=area, region=region, **keywords)

    @staticmethod
    def viewlayer_update(context: bpy.types.Context):
        """
        Update the view layer.

        Sometimes you want to modify values from Python and immediately access the updated values, e.g: Once changing the objects `bpy.types.Object.location` you may want to access its transformation right after from `bpy.types.Object.matrix_world`, but this doesn’t work as you might expect.
        There are similar issues with changes to the UI, that are covered in the next section.

        Consider the calculations that might contribute to the object’s final transformation, this includes:
        - Animation function curves.
        - Drivers and their Python expressions.
        - Constraints
        - Parent objects and all of their F-Curves, constraints, etc.

        To avoid expensive recalculations every time a property is modified, Blender defers the evaluation until the results are needed.
        However, while the script runs you may want to access the updated values.
        In this case you need to call `bpy.types.ViewLayer.update` after modifying values, for example:

        ```python
        bpy.context.object.location = 1, 2, 3
        bpy.context.view_layer.update()
        ```

        Now all dependent data (child objects, modifiers, drivers, etc.) have been recalculated and are available to the script within the active view layer.
        """
        context.view_layer.update()
