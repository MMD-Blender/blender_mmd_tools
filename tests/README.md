# Test Runner

## Running All Tests

The test runner supports three launch methods:

```
# Method 1: From Blender
blender --background -noaudio --python tests/all_test_runner.py -- --verbose

# Method 2: With Python (using PATH)
python all_test_runner.py

# Method 3: With Python (explicit path)
python all_test_runner.py "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
```

If any tests FAIL, run the individual test file to see detailed error information.

## Running Individual Tests

Run individual test scripts directly:
```
blender --background -noaudio --python tests/test_fileio_operators.py -- --verbose
blender --background -noaudio --python tests/test_model_operators.py -- --verbose
blender --background -noaudio --python tests/test_pmx_exporter.py -- --verbose
blender --background -noaudio --python tests/test_utils_unit.py -- --verbose
blender --background -noaudio --python tests/test_vpd_exporter.py -- --verbose
blender --background -noaudio --python tests/test_vpd_importer.py -- --verbose
blender --background -noaudio --python tests/test_model_edit.py -- --verbose
blender --background -noaudio --python tests/test_model_debug.py -- --verbose
```

## Available Test Scripts

Check the tests folder in the repo.
