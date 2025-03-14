#!/usr/bin/env python3
"""
Script to run all code quality tools to fix formatting and style issues.
"""
import subprocess
import sys
from typing import List, Tuple


def run_command(cmd: List[str]) -> Tuple[bool, str]:
    """Run a command and return success status and output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def main() -> int:
    """Run all code quality tools to fix issues."""
    tools = [
        ("black", ["black", "."]),
        ("isort", ["isort", "."]),
        ("ruff", ["ruff", "check", "--fix", "."]),
    ]

    print("\nRunning code quality tools to fix issues...\n")

    for name, cmd in tools:
        print(f"Running {name}...")
        success, output = run_command(cmd)
        if not success:
            print(f"❌ {name} encountered an error:")
            print(output)
        else:
            print(f"✅ {name} completed")
            if output:
                print("Changes made:")
                print(output)
        print("-" * 50)

    # Run mypy last as it only checks types and doesn't fix anything
    print("\nRunning mypy type checker...")
    success, output = run_command(["mypy", "src/vp_analysis_api"])
    if not success:
        print("❌ mypy found type issues:")
        print(output)
    else:
        print("✅ mypy passed")
    print("-" * 50)

    print("\n✨ All tools completed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
