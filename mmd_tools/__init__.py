# Copyright 2012 MMD Tools authors
# This file is part of MMD Tools.

# MMD Tools is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# MMD Tools is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import os

PACKAGE_NAME = __package__
PACKAGE_PATH = os.path.dirname(__file__)

with open(os.path.join(PACKAGE_PATH, "blender_manifest.toml"), "rb") as f:
    import tomllib

    manifest = tomllib.load(f)
    MMD_TOOLS_VERSION = manifest["version"]


from . import auto_load
from . import auto_export
 

auto_load.init(PACKAGE_NAME)

# Store keymap items to remove them when unregistering
addon_keymaps = []

import bpy

class MMD_PMX_FileHandler(bpy.types.FileHandler):
    bl_idname = "mmd_tools.pmx_file_handler"
    bl_label = "MMD PMX Model"
    bl_import_operator = "mmd_tools.import_model"  # Change to your actual import operator id
    bl_file_extensions = ".pmx"
    bl_file_filter = "*.pmx"
    bl_description = "Import MMD PMX Model by dropping into Blender"

    @classmethod
    def poll_drop(cls, context):
        # Allow drop in 3D View and File Browser
        print(f" poll_drop")
        return context.area and context.area.type in {"VIEW_3D", "FILE_BROWSER"}

    def import_drop(self, context, filepath=None, files=None, **kwargs):
        print("[MMD_PMX_FileHandler] import_drop called")
        print(f"  filepath: {filepath}")
        print(f"  files: {files}")
        # Call the import operator for each dropped file
        if files:
            for f in files:
                print(f"  Importing file: {f['name']}")
                bpy.ops.mmd_tools.import_model(filepath=f["name"])
        elif filepath:
            print(f"  Importing file: {filepath}")
            bpy.ops.mmd_tools.import_model(filepath=filepath)
        return {'FINISHED'}

def register():
    import bpy

    from . import handlers
    bpy.utils.register_class(MMD_PMX_FileHandler)
    auto_load.register()

    # pylint: disable=import-outside-toplevel
    from .m17n import translations_dict

    bpy.app.translations.register(PACKAGE_NAME, translations_dict)

    handlers.MMDHanders.register()
    
    auto_export.register()
   
    
    # Register keymap
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='Object Mode', space_type='EMPTY')
        kmi = km.keymap_items.new("mmd_tools.export_pmx_quick", 'E', 'PRESS', ctrl=True, alt=False)
        addon_keymaps.append((km, kmi))
        km1 = kc.keymaps.new(name='Curve', space_type='EMPTY')
        kmi1 = km1.keymap_items.new("mmd_tools.export_pmx_quick", 'E', 'PRESS', ctrl=True, alt=False)
        addon_keymaps.append((km1, kmi1))



def unregister():
    import bpy

    from . import handlers
    
    auto_export.unregister()
     
    
    # Unregister keymap
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

    handlers.MMDHanders.unregister()

    bpy.app.translations.unregister(PACKAGE_NAME)

    auto_load.unregister()

    bpy.utils.unregister_class(MMD_PMX_FileHandler)


if __name__ == "__main__":
    register()
