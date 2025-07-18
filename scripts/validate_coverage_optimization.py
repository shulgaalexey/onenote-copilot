#!/usr/bin/env python3
"""
Test coverage optimization validation script.
Demonstrates Python 3.12 sys.monitoring for faster coverage.
"""
import os
import subprocess
import sys
import time


def run_coverage_test(coverage_mode="default"):
    """Run tests with different coverage modes."""
    print(f"\n{'='*60}")
    print(f"Testing coverage mode: {coverage_mode}")
    print(f"{'='*60}")

    if coverage_mode == "sysmon":
        # Use Python 3.12 sys.monitoring for faster coverage
        env = os.environ.copy()
        env["COVERAGE_CORE"] = "sysmon"
        cmd = ["python", "-m", "pytest", "tests/test_config.py", "--cov=src", "--cov-report=term-missing", "-q"]
    else:
        # Use default coverage
        cmd = ["python", "-m", "pytest", "tests/test_config.py", "--cov=src", "--cov-report=term-missing", "-q"]
        env = os.environ.copy()

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=120
        )
        end_time = time.time()
        execution_time = end_time - start_time

        print(f"Execution time: {execution_time:.2f} seconds")
        print(f"Exit code: {result.returncode}")

        if result.stdout:
            # Extract coverage information
            lines = result.stdout.split('\n')
            for line in lines:
                if 'TOTAL' in line or 'coverage' in line.lower():
                    print(f"Coverage: {line.strip()}")

        return execution_time, result.returncode
    except subprocess.TimeoutExpired:
        print("Test timed out")
        return 120, -1
    except Exception as e:
        print(f"Error: {e}")
        return -1, -1

def main():
    """Run coverage optimization tests."""
    print("OneNote Copilot Coverage Optimization Test")
    print("=" * 60)

    # Check Python version
    python_version = sys.version_info
    print(f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")

    if python_version >= (3, 12):
        print("✅ Python 3.12+ detected - sys.monitoring available")

        # Test both modes
        print("\nTesting default coverage mode...")
        default_time, default_code = run_coverage_test("default")

        print("\nTesting sys.monitoring coverage mode...")
        sysmon_time, sysmon_code = run_coverage_test("sysmon")

        if default_time > 0 and sysmon_time > 0:
            improvement = ((default_time - sysmon_time) / default_time) * 100
            print(f"\n{'='*60}")
            print("Coverage Optimization Results:")
            print(f"{'='*60}")
            print(f"Default coverage: {default_time:.2f}s")
            print(f"sys.monitoring:   {sysmon_time:.2f}s")
            print(f"Improvement:      {improvement:.1f}%")

            if improvement > 0:
                print("✅ sys.monitoring shows improvement!")
            else:
                print("⚠️  No significant improvement detected")
        else:
            print("❌ Could not measure improvement - tests failed")
    else:
        print("⚠️  Python 3.12+ required for sys.monitoring optimization")
        print("Running default coverage test...")
        default_time, default_code = run_coverage_test("default")

        print(f"\n{'='*60}")
        print("Coverage Test Results:")
        print(f"{'='*60}")
        print(f"Default coverage: {default_time:.2f}s")
        print("Recommendation: Upgrade to Python 3.12+ for faster coverage")

if __name__ == "__main__":
    main()
