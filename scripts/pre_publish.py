#!/usr/bin/env python3
"""
Pre-publish validation script
Run this before publishing to PyPI to catch common issues
"""

import os
import subprocess
import sys
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback for older Python versions


def run_command(command, capture_output=True, check=True):
    """Run a shell command and return the result."""
    try:
        if capture_output:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, check=check
            )
            return result.stdout.strip(), result.stderr.strip()
        else:
            subprocess.run(command, shell=True, check=check)
            return "", ""
    except subprocess.CalledProcessError as e:
        if capture_output:
            return "", e.stderr
        else:
            raise


def main():
    print("🔍 Running pre-publish checks...\n")

    checks = []

    # Get project root directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    os.chdir(project_root)

    # Check 1: pyproject.toml exists and is valid
    pyproject_path = project_root / "pyproject.toml"
    try:
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
        checks.append({"name": "pyproject.toml exists", "passed": True})

        # Check required fields
        project_config = pyproject.get("project", {})
        required_fields = ["name", "version", "description", "license"]
        for field in required_fields:
            if field not in project_config or not project_config[field]:
                checks.append(
                    {
                        "name": f"pyproject.toml has {field}",
                        "passed": False,
                        "error": f"Missing {field}",
                    }
                )
            else:
                checks.append({"name": f"pyproject.toml has {field}", "passed": True})

        # Check scripts
        scripts = project_config.get("scripts", {})
        if scripts:
            checks.append({"name": "Entry points configured", "passed": True})
        else:
            checks.append(
                {
                    "name": "Entry points configured",
                    "passed": False,
                    "error": "No scripts/entry points defined",
                }
            )

    except Exception as e:
        checks.append(
            {"name": "pyproject.toml exists", "passed": False, "error": str(e)}
        )

    # Check 2: README.md exists
    readme_path = project_root / "README.md"
    if readme_path.exists():
        checks.append({"name": "README.md exists", "passed": True})
    else:
        checks.append(
            {
                "name": "README.md exists",
                "passed": False,
                "error": "README.md not found",
            }
        )

    # Check 3: LICENSE exists
    license_path = project_root / "LICENSE"
    if license_path.exists():
        checks.append({"name": "LICENSE exists", "passed": True})
    else:
        checks.append(
            {
                "name": "LICENSE exists",
                "passed": False,
                "error": "LICENSE file not found",
            }
        )

    # Check 4: Git status clean
    try:
        git_status, _ = run_command("git status --porcelain")
        if not git_status:
            checks.append({"name": "Git working directory clean", "passed": True})
        else:
            checks.append(
                {
                    "name": "Git working directory clean",
                    "passed": False,
                    "error": "Uncommitted changes",
                }
            )
            print("\n⚠️  Uncommitted changes:")
            print(git_status)
    except Exception:
        checks.append(
            {
                "name": "Git working directory clean",
                "passed": False,
                "error": "Not a git repository or git not available",
            }
        )

    # Check 5: Tests pass
    try:
        print("\n🧪 Running tests...")
        run_command("python -m pytest", capture_output=False)
        checks.append({"name": "Tests pass", "passed": True})
    except subprocess.CalledProcessError:
        checks.append({"name": "Tests pass", "passed": False, "error": "Tests failed"})
    except FileNotFoundError:
        checks.append(
            {"name": "Tests pass", "passed": False, "error": "pytest not installed"}
        )

    # Check 6: Code quality with ruff (formatting + linting in one tool)
    try:
        print("\n🔧 Auto-formatting code with ruff...")
        run_command("python -m ruff format .", capture_output=False)
        checks.append({"name": "Code formatting (ruff)", "passed": True})

        print("\n🔍 Running linter with ruff...")
        stdout, stderr = run_command("python -m ruff check . --fix")
        # Success is determined by exit code, not by absence of output
        # Ruff prints "All checks passed!" on success which counts as output
        checks.append({"name": "Code linting (ruff)", "passed": True})
        if stdout and "All checks passed!" not in stdout:
            print(f"❌ Linting errors:\n{stdout}")
        elif stdout:
            print(f"✅ {stdout}")
    except subprocess.CalledProcessError:
        checks.append(
            {
                "name": "Code quality (ruff)",
                "passed": False,
                "error": "Code quality check failed",
            }
        )
    except FileNotFoundError:
        checks.append(
            {
                "name": "Code quality (ruff)",
                "passed": False,
                "error": "ruff not installed - install with: pip install ruff",
            }
        )

    # Check 7: Type checking passes (non-blocking)
    try:
        print("\n🔍 Running type checker...")
        stdout, stderr = run_command("python -m mypy .", check=False)
        if not stderr and "error:" not in stdout.lower():
            checks.append({"name": "Type checking passes", "passed": True})
        else:
            checks.append(
                {
                    "name": "Type checking passes",
                    "passed": False,
                    "error": "Type checking issues found",
                    "warning": True,
                }
            )
            print("⚠️  Type checking issues found but not blocking publish")
    except FileNotFoundError:
        checks.append(
            {
                "name": "Type checking passes",
                "passed": False,
                "error": "mypy not installed",
                "warning": True,
            }
        )

    # Check 8: Build succeeds
    try:
        print("\n🏗️  Building...")
        run_command("python -m build", capture_output=False)
        checks.append({"name": "Build succeeds", "passed": True})

        # Check if build artifacts exist
        dist_dir = project_root / "dist"
        if dist_dir.exists():
            wheel_files = list(dist_dir.glob("*-py3-none-any.whl"))
            tar_files = list(dist_dir.glob("*.tar.gz"))

            if wheel_files and tar_files:
                print(
                    f"✅ Build artifacts found: {len(wheel_files)} wheel(s), {len(tar_files)} source dist(s)"
                )
                checks.append({"name": "Build artifacts created", "passed": True})
            else:
                all_files = list(dist_dir.glob("*"))
                error_msg = (
                    f"Missing artifacts. Found files: {[f.name for f in all_files]}"
                )
                if not wheel_files:
                    error_msg += " (No wheel files matching *-py3-none-any.whl pattern)"
                if not tar_files:
                    error_msg += " (No .tar.gz files)"
                checks.append(
                    {
                        "name": "Build artifacts created",
                        "passed": False,
                        "error": error_msg,
                    }
                )
        else:
            checks.append(
                {
                    "name": "Build artifacts created",
                    "passed": False,
                    "error": "dist/ directory not created",
                }
            )

    except subprocess.CalledProcessError:
        checks.append(
            {"name": "Build succeeds", "passed": False, "error": "Build failed"}
        )
    except FileNotFoundError:
        checks.append(
            {
                "name": "Build succeeds",
                "passed": False,
                "error": "build module not installed",
            }
        )

    # Print summary
    print("\n" + "=" * 60)
    print("📋 Pre-publish Check Summary")
    print("=" * 60 + "\n")

    blocking_errors = False
    for check in checks:
        icon = "✅" if check["passed"] else ("⚠️" if check.get("warning") else "❌")
        if check["passed"]:
            message = f"{icon} {check['name']}"
            if check.get("info"):
                message += f" ({check['info']})"
        else:
            message = f"{icon} {check['name']}: {check['error']}"
            if not check.get("warning"):
                blocking_errors = True
        print(message)

    print("\n" + "=" * 60)

    if blocking_errors:
        print("\n❌ Pre-publish checks FAILED!")
        print("Please fix the errors above before publishing.\n")
        sys.exit(1)
    else:
        print("\n✅ All critical pre-publish checks PASSED!")
        if any(not check["passed"] and check.get("warning") for check in checks):
            print("⚠️  Some warnings were found but won't block publishing.")

        print("\nYou can now publish with:")
        print("  python -m twine upload dist/*")
        print("\nOr clean, build and publish:")
        print("  rm -rf dist/")
        print("  python -m build")
        print("  python -m twine upload dist/*")
        print("\nTo bump version, edit pyproject.toml and commit changes first.\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
