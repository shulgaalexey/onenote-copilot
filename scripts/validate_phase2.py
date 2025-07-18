#!/usr/bin/env python3
"""
Phase 2 validation test script.
Tests the new fixtures and markers implemented in Phase 2.
"""
import subprocess
import sys
import time


def run_command(cmd, description):
    """Run a command and measure execution time."""
    print(f"\n{'='*50}")
    print(f"Testing: {description}")
    print(f"Command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    print(f"{'='*50}")

    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            shell=True if isinstance(cmd, str) else False,
            capture_output=True,
            text=True,
            timeout=60
        )
        end_time = time.time()
        execution_time = end_time - start_time

        print(f"Execution time: {execution_time:.2f} seconds")
        print(f"Exit code: {result.returncode}")

        if result.stdout:
            lines = result.stdout.split('\n')
            # Show last few lines for results
            for line in lines[-10:]:
                if line.strip() and ('passed' in line or 'failed' in line or 'error' in line):
                    print(f"Result: {line.strip()}")

        return execution_time, result.returncode
    except subprocess.TimeoutExpired:
        print("Test timed out")
        return 60, -1
    except Exception as e:
        print(f"Error: {e}")
        return -1, -1

def main():
    """Run Phase 2 validation tests."""
    print("OneNote Copilot Phase 2 Optimization Validation")
    print("=" * 60)

    # Test the new categorization markers
    tests = [
        ("python -m pytest --collect-only -q", "Test collection with new markers"),
        ("python -m pytest tests/test_config.py -q", "Basic config tests"),
        ("python -m pytest tests/test_config.py -m 'not slow' -q", "Config tests excluding slow"),
        ("python -m pytest tests/test_auth.py -m 'auth' -q", "Auth marker tests"),
        ("python -m pytest tests/test_tools_search.py -m 'search' -q", "Search marker tests"),
        ("python -m pytest tests/test_semantic_search_fixes.py -m 'embedding' -q", "Embedding marker tests"),
        ("python -m pytest tests/test_onenote_agent.py -m 'agent' -q", "Agent marker tests"),
    ]

    results = []

    for cmd, description in tests:
        execution_time, exit_code = run_command(cmd, description)
        results.append((description, execution_time, exit_code))

    # Summary
    print(f"\n{'='*60}")
    print("Phase 2 Validation Results Summary")
    print(f"{'='*60}")

    for description, execution_time, exit_code in results:
        status = "✅ PASS" if exit_code == 0 else "❌ FAIL"
        print(f"{status} {description}: {execution_time:.2f}s")

    print(f"\n{'='*60}")
    print("Phase 2 validation complete!")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
