# Copyright 2013 MMD Tools authors
# This file is part of MMD Tools.

import contextlib
import math
from typing import Any, Dict, Generator, Iterable, List, Optional, TypeVar

import bmesh
import bpy
from mathutils import Matrix


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

    def __exit__(self, exc_type, exc_value, traceback):
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
        self.__selected_objects = tuple(set(selected_objects) | {active_object}) if selected_objects else (active_object,)

        self.__hides: List[bool] = []
        for i in self.__selected_objects:
            self.__hides.append(i.hide_get())
            FnContext.select_object(contenxt, i)
        FnContext.set_active_object(contenxt, active_object)

    def __enter__(self) -> bpy.types.Object:
        return self.__active_object

    def __exit__(self, exc_type, exc_value, traceback):
        for i, j in zip(self.__selected_objects, self.__hides, strict=False):
            try:
                i.hide_set(j)
            except ReferenceError:
                # Object may no longer exist, so skip restoring hidden state.
                pass


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
    # TODO: Consider reimplementing with bpy.context.temp_override,
    #       but note that Blender's new API has stability issues.
    #       temp_override is prone to crashes, making the current approach safer.
    #       If it ain't broke, don't fix it.
    return __SelectObjects(obj, objects)


def duplicateObject(obj, total_len):
    return FnContext.duplicate_object(FnContext.ensure_context(), obj, total_len)


def createObject(name="Object", object_data=None, target_scene=None):
    context = FnContext.ensure_context(target_scene)
    return FnContext.set_active_object(context, FnContext.new_and_link_object(context, name, object_data))


def makeSphere(segment=8, ring_count=5, radius=1.0, target_object=None):
    if target_object is None:
        mesh_data = bpy.data.meshes.new("Sphere")
        target_object = createObject(name="Sphere", object_data=mesh_data)

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
    if target_object is None:
        mesh_data = bpy.data.meshes.new("Box")
        target_object = createObject(name="Box", object_data=mesh_data)

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
    if target_object is None:
        mesh_data = bpy.data.meshes.new("Capsule")
        target_object = createObject(name="Capsule", object_data=mesh_data)
    height = max(height, 1e-3)

    mesh = target_object.data
    bm = bmesh.new()
    verts = bm.verts
    top = (0, 0, height / 2 + radius)
    verts.new(top)

    # def f(i):
    #     return radius * i / ring_count
    def f(i):
        return radius * math.sin(0.5 * math.pi * i / ring_count)

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
    def mesh_add_shape_key(mesh_object: bpy.types.Object, name: str, from_mix: bool = True) -> bpy.types.ShapeKey:
        """Add a shape key to the mesh object.
        Note:
            Blender 5.0+ changed the default shape key value from 0.0 to 1.0.
            This function explicitly sets value to 0.0 for consistent behavior.
        """
        assert isinstance(mesh_object.data, bpy.types.Mesh)
        shape_key = mesh_object.shape_key_add(name=name, from_mix=from_mix)
        shape_key.value = 0.0
        return shape_key

    @staticmethod
    def mesh_ensure_basis_shape_key(mesh_object: bpy.types.Object) -> bpy.types.ShapeKey:
        """Ensure the mesh has a basis shape key, create if not exists."""
        assert isinstance(mesh_object.data, bpy.types.Mesh)
        if mesh_object.data.shape_keys is None:
            return mesh_object.shape_key_add(name="Basis", from_mix=False)
        return mesh_object.data.shape_keys.key_blocks[0]

    @staticmethod
    def mesh_remove_shape_key(mesh_object: bpy.types.Object, shape_key: bpy.types.ShapeKey):
        assert isinstance(mesh_object.data, bpy.types.Mesh)

        key: bpy.types.Key = shape_key.id_data
        assert key == mesh_object.data.shape_keys

        if mesh_object.animation_data is not None:
            fc_curve: bpy.types.FCurve
            for fc_curve in mesh_object.animation_data.drivers:
                if not fc_curve.data_path.startswith(shape_key.path_from_id()):
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
        if context is None or not hasattr(context, "active_object"):
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
        if context is None or not hasattr(context, "scene") or not hasattr(context.scene, "objects"):
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
    def copy_object(object_to_copy: bpy.types.Object, target_count: int) -> List[bpy.types.Object]:
        """
        Copy object without operators.

        Much faster than duplicate_object() for thousands of copies. Copies are linked to the same collections as the original.

        Returns:
            List[bpy.types.Object]: The original object followed by target_count - 1 copies.
        """
        # Blender adds copies to the rigid body world collections by itself when they are linked to a scene collection
        rigid_body_collections = set()
        for scene in bpy.data.scenes:
            rigidbody_world = scene.rigidbody_world
            if rigidbody_world is not None:
                rigid_body_collections.update(c for c in (rigidbody_world.collection, rigidbody_world.constraints) if c is not None)
        collections = [c for c in object_to_copy.users_collection if c not in rigid_body_collections]

        result_objects = [object_to_copy]
        for _ in range(target_count - 1):
            obj = object_to_copy.copy()
            for collection in collections:
                collection.objects.link(obj)
            result_objects.append(obj)
        return result_objects

    @staticmethod
    def __find_view3d_override(context: bpy.types.Context) -> Optional[Dict[str, Any]]:
        window = context.window or next(iter(context.window_manager.windows), None)
        area = next((a for a in window.screen.areas if a.type == "VIEW_3D"), None) if window else None
        if area is None:
            return None
        return {"window": window, "area": area, "region": next(r for r in area.regions if r.type == "WINDOW")}

    @staticmethod
    def set_objects_hidden(context: bpy.types.Context, objects: Iterable[bpy.types.Object], hide: bool):
        """
        Hide or unhide objects in the viewport, like calling Object.hide_set(hide) on each of them.

        Object.hide_set() resyncs the whole view layer on every call, which is O(N^2) for thousands of objects.
        When a 3D view is available, use one hide/unhide operator call instead:
        - hide: select the objects and hide the selection.
        - unhide: unhide everything, then hide the objects that were hidden before and are not targets.
        Falls back to Object.hide_set() without a 3D view.
        """
        objects = [obj for obj in objects if obj.hide_get() != hide]
        if not objects:
            return

        override = FnContext.__find_view3d_override(context)
        # unhiding re-hides every other hidden object, which costs more than a few hide_set() calls
        if not hide and len(objects) < 64:
            override = None
        if override is not None:
            if hide:
                FnContext.__hide_by_selection(context, override, objects)
            else:
                targets = set(objects)
                others = [obj for obj in context.view_layer.objects if obj.hide_get() and obj not in targets]
                with context.temp_override(**override):
                    bpy.ops.object.hide_view_clear(select=False)
                if others:
                    FnContext.__hide_by_selection(context, override, others)
                    # hide_view_set can skip objects that were unselectable before hide_view_clear, so hide those one by one
                    for obj in others:
                        if not obj.hide_get():
                            obj.hide_set(True)

        # Fallback for no 3D view, and for objects the operators skipped (e.g. in a hidden collection)
        for obj in objects:
            if obj.hide_get() != hide:
                obj.hide_set(hide)

    @staticmethod
    def __hide_by_selection(context: bpy.types.Context, override: Dict[str, Any], objects: List[bpy.types.Object]):
        # hide_view_set only hides selected objects, so make unselectable ones selectable for the moment
        unselectable_objects = [obj for obj in objects if obj.hide_select]
        if unselectable_objects:
            FnContext.set_hide_select(unselectable_objects, False)
        # restore selection and selectability even if select_set() fails (e.g. an object not in the view layer)
        try:
            with context.temp_override(**override):
                selected_objects = context.selected_objects
                try:
                    for obj in selected_objects:
                        obj.select_set(False)
                    for obj in objects:
                        obj.select_set(True)
                    bpy.ops.object.hide_view_set(unselected=False)
                finally:
                    for obj in objects:
                        if obj.visible_get():
                            obj.select_set(False)
                    for obj in selected_objects:
                        if obj.visible_get():
                            obj.select_set(True)
        finally:
            if unselectable_objects:
                FnContext.set_hide_select(unselectable_objects, True)

    @staticmethod
    def hide_objects(context: bpy.types.Context, objects: List[bpy.types.Object]):
        """Hide objects in the viewport. See set_objects_hidden()."""
        FnContext.set_objects_hidden(context, objects, True)

    @staticmethod
    def set_hide_select(objects: List[bpy.types.Object], hide_select: bool = True):
        """
        Set Object.hide_select on many objects at once.

        Setting it per object resyncs the view layer on every call (O(N^2) for thousands of objects).
        foreach_set() skips the per-object update, so resync once at the end instead.
        Objects linked from a library are left unchanged, because foreach_set() skips them.
        """
        if not objects:
            return
        targets = {obj.as_pointer() for obj in objects}
        all_objects = bpy.data.objects
        values = [False] * len(all_objects)
        all_objects.foreach_get("hide_select", values)
        for i, obj in enumerate(all_objects):
            if obj.as_pointer() in targets:
                values[i] = hide_select
        all_objects.foreach_set("hide_select", values)
        # foreach_set() skips the update callback, so tag the objects and evaluate once to refresh base selectability
        for obj in objects:
            obj.update_tag()
        bpy.context.view_layer.update()

    @staticmethod
    def find_user_layer_collection_by_object(context: bpy.types.Context, target_object: bpy.types.Object) -> Optional[bpy.types.LayerCollection]:
        """
        Find the layer collection that contains the given target_object in the user's collections.

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
