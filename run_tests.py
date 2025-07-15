"""
Test runner script for OneNote Copilot.

Provides commands to run different types of tests with proper configuration.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """
    Run a command and return success status.

    Args:
        cmd: Command to run as list of strings
        description: Description of what the command does

    Returns:
        True if command succeeded, False otherwise
    """
    print(f"\n🧪 {description}")
    print(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, check=True, cwd=Path(__file__).parent)
        print(f"✅ {description} - PASSED")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED (exit code: {e.returncode})")
        return False
    except FileNotFoundError:
        print(f"❌ {description} - FAILED (command not found)")
        return False


def main():
    """Run tests based on command line arguments."""
    if len(sys.argv) < 2:
        print("OneNote Copilot Test Runner")
        print("\nUsage:")
        print("  python run_tests.py unit       # Run unit tests only")
        print("  python run_tests.py integration # Run integration tests only")
        print("  python run_tests.py all        # Run all tests")
        print("  python run_tests.py coverage   # Run tests with coverage")
        print("  python run_tests.py lint       # Run linting only")
        print("  python run_tests.py type       # Run type checking only")
        print("  python run_tests.py check      # Run all checks (lint + type + test)")
        return

    test_type = sys.argv[1].lower()
    success = True

    if test_type == "unit":
        success = run_command([
            sys.executable, "-m", "pytest",
            "tests/",
            "-v",
            "-m", "not integration",
            "--tb=short"
        ], "Unit Tests")

    elif test_type == "integration":
        success = run_command([
            sys.executable, "-m", "pytest",
            "tests/",
            "-v",
            "-m", "integration",
            "--tb=short"
        ], "Integration Tests")

    elif test_type == "all":
        success = run_command([
            sys.executable, "-m", "pytest",
            "tests/",
            "-v",
            "--tb=short"
        ], "All Tests")

    elif test_type == "coverage":
        success = run_command([
            sys.executable, "-m", "pytest",
            "tests/",
            "--cov=src",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-fail-under=80",
            "-v"
        ], "Tests with Coverage")

        if success:
            print("\n📊 Coverage report generated in htmlcov/index.html")

    elif test_type == "lint":
        success = run_command([
            sys.executable, "-m", "ruff",
            "check",
            "src/",
            "tests/"
        ], "Linting")

    elif test_type == "type":
        success = run_command([
            sys.executable, "-m", "mypy",
            "src/"
        ], "Type Checking")

    elif test_type == "check":
        print("🔍 Running comprehensive checks...")

        lint_success = run_command([
            sys.executable, "-m", "ruff",
            "check",
            "src/",
            "tests/"
        ], "Linting")

        type_success = run_command([
            sys.executable, "-m", "mypy",
            "src/"
        ], "Type Checking")

        test_success = run_command([
            sys.executable, "-m", "pytest",
            "tests/",
            "-v",
            "--tb=short"
        ], "All Tests")

        success = lint_success and type_success and test_success

        if success:
            print("\n🎉 All checks passed!")
        else:
            print("\n💥 Some checks failed. See output above.")

    else:
        print(f"❌ Unknown test type: {test_type}")
        print("Use: unit, integration, all, coverage, lint, type, or check")
        success = False

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
