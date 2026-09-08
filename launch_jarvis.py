"""Launch JARVIS using the project's virtual environment.

This script is placed in the Windows Startup folder to enable automatic
launch of JARVIS when the user logs into Windows.

It dynamically finds the project directory and uses the project's existing
virtual environment and entry point.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def find_project_root(script_path: Path) -> Path:
    """Find the project root by walking up from the script's location.

    Looks for pyproject.toml as a marker file.
    """
    current = script_path.resolve().parent
    # Walk up at most 10 directories
    for _ in range(10):
        if (current / "pyproject.toml").is_file():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    # Fallback: return the script's parent (project root assumed)
    return script_path.resolve().parent


def find_venv_python(project_root: Path) -> Path:
    """Find the virtual environment's Python executable."""
    # Try common venv locations relative to project root
    candidates = [
        project_root / ".venv" / "Scripts" / "python.exe",  # Windows
        project_root / ".venv" / "bin" / "python",          # macOS/Linux
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    # If no venv found, fall back to system python
    return sys.executable


def main() -> None:
    script_path = Path(__file__)
    project_root = find_project_root(script_path)
    python_exe = find_venv_python(project_root)

    # Run: python -m ultron --web
    # The -m flag uses the project's installed ultron package
    args = [str(python_exe), "-m", "ultron", "--web"]

    # Set the working directory to the project root so relative paths work
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)

    print(f"JARVIS Starting...")
    print(f"Project root: {project_root}")
    print(f"Using Python: {python_exe}")
    print(f"Command: {' '.join(args)}")

    # Launch JARVIS
    subprocess = __import__("subprocess").Popen(args, env=env)
    print(f"JARVIS launched with PID: {subprocess.pid}")


if __name__ == "__main__":
    main()