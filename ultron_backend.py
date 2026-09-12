"""Backend entry point for PyInstaller bundling.

This script starts the ULTRON backend server in headless mode
when bundled as a standalone executable.
"""

from __future__ import annotations

import sys
import os

# Ensure the project root is in the path
if getattr(sys, "frozen", False):
    # Running as PyInstaller bundle
    bundle_dir = os.path.dirname(sys.executable)
    sys.path.insert(0, bundle_dir)
else:
    # Running in development
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)

from ultron.cli import main

if __name__ == "__main__":
    # Override sys.argv for headless mode
    if "--headless" not in sys.argv:
        sys.argv.append("--headless")
    if "--web" not in sys.argv:
        sys.argv.append("--web")

    raise SystemExit(main())
