#!/usr/bin/env python
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
progress_percent = 0
test_start_time = None

# Shared value to control progress animation
stop_progress = None


def animate_progress(stop_flag, test_name, start_time):
    """
    Animate the progress bar while a test is running
    """
    chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"  # Braille spinner characters
    idx = 0

    while not stop_flag.value:
        idx = (idx + 1) % len(chars)
        spinner = chars[idx]

        # Calculate elapsed time
        elapsed = datetime.now() - start_time
        elapsed_str = f"{elapsed.seconds}s"

        # Calculate how much of the bar to fill
        length = 30
        filled_length = int(length * progress_percent)
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
    # Method 3: Check if Blender path is provided as command-line argument
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) and (os.path.basename(sys.argv[1]).startswith("blender") or "blender" in os.path.basename(sys.argv[1]).lower()):
        return sys.argv[1]

    # Method 1 & 2: Use 'blender' from PATH
    return "blender"


def run_test(blender_path, test_script):
    """
    Run a single test script using Blender in background mode
    """
    global progress_percent, test_start_time

    try:
        # Set the start time for this test
        test_start_time = datetime.now()

        # Prepare shared flag for process control
        stop_flag = multiprocessing.Value("b", False)

        # Get test name for display
        test_name = f"Testing {os.path.basename(test_script)}"

        # Start the progress animation in a separate process
        progress_process = multiprocessing.Process(target=animate_progress, args=(stop_flag, test_name, test_start_time))
        progress_process.daemon = True
        progress_process.start()

        # Run the test script with Blender in background mode
        cmd = [blender_path, "--background", "-noaudio", "--python", test_script, "--", "--verbose"]

        # Run the test
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",  # Handle Unicode decode errors gracefully
        )

        # Calculate total execution time
        elapsed = datetime.now() - test_start_time
        elapsed_str = f"{elapsed.seconds}.{str(elapsed.microseconds)[:3]}s"

        # Stop the progress animation
        stop_flag.value = True
        progress_process.join(timeout=0.5)
        if progress_process.is_alive():
            progress_process.terminate()

        # Check if the test passed
        # Look for "OK" indicating all tests passed, or check for absence of FAILED/ERROR
        if "OK" in result.stdout or (result.returncode == 0 and "FAILED" not in result.stdout and "ERROR" not in result.stdout):
            return True, "", elapsed_str
        else:
            # We no longer extract the detailed error message
            # Just indicate that the test failed
            return False, "Test failed", elapsed_str

    except Exception as e:
        # Calculate elapsed time in case of exception
        elapsed = datetime.now() - test_start_time
        elapsed_str = f"{elapsed.seconds}.{str(elapsed.microseconds)[:3]}s"

        # Stop the progress animation if it's running
        if "stop_flag" in locals() and "progress_process" in locals():
            stop_flag.value = True
            progress_process.join(timeout=0.5)
            if progress_process.is_alive():
                progress_process.terminate()

        return False, "Exception occurred", elapsed_str


def print_summary_progress(iteration, total):
    """Print a simple progress bar for the overall progress"""
    global progress_percent
    progress_percent = iteration / float(total)

    percent = ("{0:.1f}").format(100 * progress_percent)
    length = 30
    filled_length = int(length * progress_percent)
    bar = "█" * filled_length + "-" * (length - filled_length)

    print(f"\rProgress: |{bar}| {percent}% ({iteration}/{total} tests)", end="")
    if iteration == total:
        print()


def run_all_tests():
    """
    Run all test scripts in the directory
    """
    global current_test

    # Get the path to the Blender executable
    blender_path = get_blender_path()

    # If blender_path is just "blender", check if it's in PATH by running a simple command
    if blender_path == "blender":
        try:
            subprocess.run([blender_path, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
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

    # Run each test script
    for i, script in enumerate(test_scripts, 1):
        script_name = os.path.basename(script)
        current_test = f"Testing {script_name}"

        # Update the overall progress
        print_summary_progress(i - 1, len(test_scripts))

        passed, error, elapsed = run_test(blender_path, script)

        # Convert elapsed time to seconds for total
        try:
            elapsed_secs = float(elapsed.replace("s", ""))
            total_time_seconds += elapsed_secs
        except:
            pass

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

    # Print passed tests with green color
    if passed_tests:
        print("\nPASSED TESTS:")
        for test, elapsed in passed_tests:
            print(f"  {GREEN}✓ {test} ({elapsed}){RESET}")

    # Print failed tests with red color
    if failed_tests:
        print("\nFAILED TESTS:")
        for test, elapsed in failed_tests:
            print(f"  {RED}✗ {test} ({elapsed}){RESET}")

    # print("\nTest run completed at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
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
