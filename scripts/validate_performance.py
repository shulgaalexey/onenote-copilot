#!/usr/bin/env python3
"""
Test performance validation script.
Runs different test configurations to validate optimization improvements.
"""
import subprocess
import sys
import time


def run_command(cmd, description):
    """Run a command and measure execution time."""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Command: {cmd}")
    print(f"{'='*60}")

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        end_time = time.time()
        execution_time = end_time - start_time

        print(f"Execution time: {execution_time:.2f} seconds")
        print(f"Exit code: {result.returncode}")

        if result.stdout:
            print(f"Output: {result.stdout[-500:]}")  # Last 500 chars
        if result.stderr:
            print(f"Error: {result.stderr[-500:]}")  # Last 500 chars

        return execution_time, result.returncode
    except subprocess.TimeoutExpired:
        print(f"Test timed out after 5 minutes")
        return 300, -1
    except Exception as e:
        print(f"Error running test: {e}")
        return -1, -1

def main():
    """Run performance validation tests."""
    print("OneNote Copilot Test Performance Validation")
    print("=" * 60)

    # Test configurations
    tests = [
        ("python -m pytest tests/test_config.py -q", "Config tests (baseline)"),
        ("python -m pytest tests/test_config.py -m 'not slow' -q", "Config tests (no slow)"),
        ("python -m pytest tests/test_config.py -m 'fast' -q", "Config tests (fast only)"),
        ("python -m pytest tests/test_tools_search.py::TestOneNoteSearchTool::test_search_pages_network_timeout -q", "Network timeout test (fast)"),
        ("python -m pytest tests/test_semantic_search_fixes.py::TestEmbeddingGeneratorFixes::test_generate_embedding_with_no_client -q", "Embedding test (fast)"),
    ]

    results = []

    for cmd, description in tests:
        execution_time, exit_code = run_command(cmd, description)
        results.append((description, execution_time, exit_code))

    # Summary
    print(f"\n{'='*60}")
    print("Performance Test Results Summary")
    print(f"{'='*60}")

    for description, execution_time, exit_code in results:
        status = "✅ PASS" if exit_code == 0 else "❌ FAIL"
        print(f"{status} {description}: {execution_time:.2f}s")

    print(f"\n{'='*60}")
    print("Optimization validation complete!")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
