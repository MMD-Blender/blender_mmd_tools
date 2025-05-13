import unittest

import bpy
from bl_ext.user_default.mmd_tools.core.model import Model

# Usage: blender --background -noaudio --python tests/test_model_operators.py -- --verbose

# Due to the limitations of Windows this file can't contain characters
# outside the cp1252 range. Because Blender parses the file with that character set.
# http://stackoverflow.com/questions/3284827
# https://developer.blender.org/T35176

# A workaround is to use unicode literals
# Root bone
ROOT_BONE = '\u5168\u3066\u306e\u89aa'
# Facial Frame
EXP_FRAME = '\u8868\u60c5'

class ModelOperatorsTest(unittest.TestCase):
    
    def setUp(self):
        """
        We should start each test with a clean state
        """
        # Ensure active object exists (user may have deleted the default cube)
        if not bpy.context.active_object:
            bpy.ops.mesh.primitive_cube_add()

        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=True)
        # Add some useful shortcuts
        self.context = bpy.context
        self.scene = bpy.context.scene

    def test_create_model(self):
        bpy.ops.mmd_tools.create_mmd_model_root_object(name_j='Test', name_e='Test_e')
        self.assertIn('Test', self.scene.objects.keys(), 'Model not found')
        # Check the object has the expected data
        obj = self.scene.objects['Test']
        root = Model.findRoot(obj)
        self.assertIsNotNone(root, 'Model not created properly')
        frames = root.mmd_root.display_item_frames
        self.assertIn('Root', frames.keys())
        self.assertIn(EXP_FRAME, frames.keys())
        # Check the rig has an armature
        rig = Model(root)
        self.assertIsNotNone(rig.armature(), 'Armature not found')
        armObj = rig.armature()
        self.assertIn(ROOT_BONE, armObj.data.bones.keys(), 'Root bone not found')
        # Check the root frame has the root bone
        root_frame = frames['Root']
        try:
            item = getattr(root_frame, 'data', root_frame.items)[0]
            self.assertEqual(item.name, armObj.data.bones.keys()[0], 'Incorrect Item name')
            self.assertEqual(item.type, 'BONE', 'Incorrect Item type')
        except IndexError:
            self.fail('Root bone not found in root frame')

if __name__ == '__main__':
    import sys
    sys.argv = [__file__] + (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    unittest.main()
