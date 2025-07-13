# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import glob
import multiprocessing
import os
import subprocess
import sys
import time
from datetime import datetime

# ANSI color codes for terminal output
GREEN = "\033[1;32m"  # Green color for passed tests (bright green)
RED = "\033[1;31m"  # Red color for failed tests (bright red)
RESET = "\033[0m"  # Reset to default terminal color

# Directory where test scripts are located
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))

# Global variables for progress tracking
current_test = ""
test_start_time = None

# Shared value to control progress animation
stop_progress = None


def animate_progress_smooth(stop_flag, test_name, start_time, current_test_num, total_tests, shared_progress):
    """Animate the progress bar while a test is running with smooth progression"""
    chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"  # Braille spinner characters
    idx = 0

    while not stop_flag.value:
        idx = (idx + 1) % len(chars)
        spinner = chars[idx]

        # Calculate elapsed time
        elapsed = datetime.now() - start_time
        elapsed_str = f"{elapsed.seconds}s"

        # Calculate progress smoothly
        # Start from the previous progress value
        start_progress = shared_progress.value
        end_progress = current_test_num / total_tests

        # Estimate progress within this test based on time
        test_duration_estimate = 30  # seconds
        elapsed_seconds = elapsed.total_seconds()

        # Progressive increase from start to end, capped by time estimate
        if elapsed_seconds < test_duration_estimate:
            time_progress = elapsed_seconds / test_duration_estimate
        else:
            time_progress = 1.0

        # Interpolate between start and end progress
        current_progress = start_progress + (end_progress - start_progress) * time_progress

        # Update shared progress
        shared_progress.value = current_progress

        # Calculate how much of the bar to fill
        length = 30
        filled_length = int(length * current_progress)
        bar = "█" * filled_length + "-" * (length - filled_length)

        # Print the progress with spinner and elapsed time
        sys.stdout.write(f"\r{test_name:<44} |{bar}| {spinner} [{elapsed_str}]")
        sys.stdout.flush()

        time.sleep(0.1)


def get_blender_path():
    """
    Get the path to the Blender executable based on the three supported launch methods:
    1. When launched from Blender: blender.exe --background -noaudio --python tests/all_test_runner.py -- --verbose
    2. When launched with Python: python all_test_runner.py (uses 'blender' from PATH)
    3. When launched with Python and explicit path: python all_test_runner.py <blender.exe path>
    """
    # Method 1: Check if we're running inside Blender
    try:
        import bpy

        # If we can import bpy, we're running inside Blender
        # Get the Blender executable path
        blender_path = bpy.app.binary_path
        if blender_path and os.path.exists(blender_path):
            return blender_path
    except ImportError:
        # Not running inside Blender
        pass

    # Method 3: Check if Blender path is provided as command-line argument
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) and (os.path.basename(sys.argv[1]).startswith("blender") or "blender" in os.path.basename(sys.argv[1]).lower()):
        return sys.argv[1]

    # Method 2: Use 'blender' from PATH
    return "blender"


def run_test(blender_path, test_script, current_test_num, total_tests, previous_progress):
    """Run a single test script using Blender in background mode"""
    global test_start_time

    try:
        # Set the start time for this test
        test_start_time = datetime.now()

        # Prepare shared flag for process control
        stop_flag = multiprocessing.Value("b", False)
        # Share the previous progress to avoid regression
        shared_progress = multiprocessing.Value("d", previous_progress)

        # Get test name for display
        test_name = f"Testing {os.path.basename(test_script)}"

        # Start the progress animation in a separate process
        progress_process = multiprocessing.Process(target=animate_progress_smooth, args=(stop_flag, test_name, test_start_time, current_test_num, total_tests, shared_progress))
        progress_process.daemon = True
        progress_process.start()

        # Run the test script with Blender in background mode
        cmd = [blender_path, "--background", "-noaudio", "--python", test_script, "--", "--verbose"]

        # Run the test
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )

        # Calculate total execution time
        elapsed = datetime.now() - test_start_time
        elapsed_str = f"{elapsed.seconds}.{str(elapsed.microseconds)[:3]}s"

        # Stop the progress animation
        stop_flag.value = True
        progress_process.join(timeout=0.5)
        if progress_process.is_alive():
            progress_process.terminate()

        # Return the final progress for this test
        final_progress = current_test_num / total_tests

        # Check if the test passed - specifically for unittest output
        output = result.stdout + result.stderr
        success_indicators = {"OK"}
        failure_indicators = {"FAIL\n", "FAIL:", "ERROR\n", "ERROR:", "skipped", "FAILED", "failures=", "errors=", "skipped="}

        has_success = any(indicator in output for indicator in success_indicators)
        has_failure = any(indicator in output for indicator in failure_indicators)

        if result.returncode == 0 and has_success and not has_failure:
            return True, "", elapsed_str, final_progress
        return False, "Test failed", elapsed_str, final_progress

    except Exception:
        # Calculate elapsed time in case of exception
        elapsed = datetime.now() - test_start_time
        elapsed_str = f"{elapsed.seconds}.{str(elapsed.microseconds)[:3]}s"

        # Stop the progress animation if it's running
        if "stop_flag" in locals() and "progress_process" in locals():
            stop_flag.value = True
            progress_process.join(timeout=0.5)
            if progress_process.is_alive():
                progress_process.terminate()

        final_progress = current_test_num / total_tests
        return False, "Exception occurred", elapsed_str, final_progress


def print_summary_progress(iteration, total):
    """Print a simple progress bar for the overall progress"""
    progress_percent = iteration / float(total)

    percent = (f"{100 * progress_percent:.1f}")
    length = 30
    filled_length = int(length * progress_percent)
    bar = "█" * filled_length + "-" * (length - filled_length)

    print(f"\rProgress: |{bar}| {percent}% ({iteration}/{total} tests)", end="")
    if iteration == total:
        print()


def run_all_tests():
    """Run all test scripts in the directory"""
    global current_test

    # Get the path to the Blender executable
    blender_path = get_blender_path()

    # If blender_path is just "blender", check if it's in PATH by running a simple command
    if blender_path == "blender":
        try:
            subprocess.run([blender_path, "--version"], capture_output=True, check=False)
        except FileNotFoundError:
            print("Error: 'blender' executable not found in PATH.")
            print("Please either:")
            print("1. Add Blender to your system PATH, or")
            print("2. Provide the Blender path as an argument: python all_test_runner.py <blender_path>")
            return

    print(f"Using Blender: {blender_path}")

    # Find all Python test scripts in the directory
    test_scripts = glob.glob(os.path.join(TESTS_DIR, "test_*.py"))

    if not test_scripts:
        print("No test scripts found in directory:", TESTS_DIR)
        return

    print(f"Found {len(test_scripts)} test scripts")
    print(f"Starting tests at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 85)

    passed_tests = []
    failed_tests = []
    total_time_seconds = 0
    current_progress = 0.0  # Track overall progress

    # Run each test script
    for i, script in enumerate(test_scripts, 1):
        script_name = os.path.basename(script)
        current_test = f"Testing {script_name}"

        # Update the overall progress
        print_summary_progress(i - 1, len(test_scripts))

        # Pass the current progress to avoid regression
        passed, error, elapsed, new_progress = run_test(blender_path, script, i, len(test_scripts), current_progress)
        current_progress = new_progress  # Update for next iteration

        # Convert elapsed time to seconds for total
        try:
            elapsed_secs = float(elapsed.replace("s", ""))
            total_time_seconds += elapsed_secs
        except Exception as e:
            print(f"Failed to parse elapsed time '{elapsed}': {e}")

        # Clear the line
        sys.stdout.write("\r" + " " * 100 + "\r")
        sys.stdout.flush()

        # Print the result for this test with color
        status = "✓" if passed else "✗"
        color = GREEN if passed else RED
        print(f"{color}{status} {script_name} ({elapsed}){RESET}")

        if passed:
            passed_tests.append((script_name, elapsed))
        else:
            failed_tests.append((script_name, elapsed))

    # Complete the progress
    print_summary_progress(len(test_scripts), len(test_scripts))

    # Print results
    print("\n" + "=" * 80)
    print(f"RESULTS: {len(passed_tests)} passed, {len(failed_tests)} failed")
    total_time_str = time.strftime("%H:%M:%S", time.gmtime(total_time_seconds))
    print(f"Total execution time: {total_time_str}")
    print("=" * 80)

    print("\nPASSED TESTS:")
    if passed_tests:
        for test, elapsed in passed_tests:
            print(f"  {GREEN}✓ {test} ({elapsed}){RESET}")
    else:
        print("    No tests passed!")

    print("\nFAILED TESTS:")
    if failed_tests:
        for test, elapsed in failed_tests:
            print(f"  {RED}✗ {test} ({elapsed}){RESET}")
    else:
        print("    All tests passed!")

    print("\nTest run completed at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"({total_time_seconds:.3f}s)")


# When run directly
if __name__ == "__main__":
    # Remove the Blender path from sys.argv if it was provided
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) and (os.path.basename(sys.argv[1]).startswith("blender") or "blender" in os.path.basename(sys.argv[1]).lower()):
        blender_path = sys.argv[1]
        sys.argv = [sys.argv[0]] + sys.argv[2:]

    # If run as a Blender Python script, sys.argv might contain Blender's arguments
    # The Python script gets all arguments after the '--' separator
    argv = sys.argv

    # Get all args after "--" to use for unittest
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]  # Get all args after "--"
    else:
        argv = []

    # Set up the unittest args
    sys.argv = [__file__] + argv

    try:
        # Required for Windows
        multiprocessing.freeze_support()
        run_all_tests()
    except KeyboardInterrupt:
        print("\nTest run interrupted by user")
