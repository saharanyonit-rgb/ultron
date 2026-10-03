# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for JARVIS Desktop Application.

This spec builds two executables:
1. JARVIS.exe - The desktop application (tray + WebView2 window + backend)
2. ultron_backend.exe - The ULTRON backend server (optional, can also use Python directly)
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Project root
ROOT = os.path.dirname(os.path.abspath(SPEC))


def discovered_tool_modules():
    """Every `ultron.tools.*` module, derived from the filesystem.

    Tools are discovered at runtime by `ultron.tools.catalog.discover_tools()`,
    which walks the package with pkgutil + importlib. Neither is visible to
    PyInstaller's static analysis, so a frozen build ships *zero* tools unless
    each module is listed as a hidden import. That list used to be maintained
    by hand, which is how `ultron.tools.catalog` itself came to be missing and
    silently broke discovery in packaged builds.

    Scanning the directory (rather than importing the package) keeps this
    working in the build environment, where the app's dependencies may not be
    installed yet.
    """
    tools_dir = os.path.join(ROOT, "ultron", "tools")
    if not os.path.isdir(tools_dir):
        return ["ultron.tools", "ultron.tools.catalog", "ultron.tools.execution"]

    modules = ["ultron.tools", "ultron.tools.catalog", "ultron.tools.execution"]
    for entry in sorted(os.listdir(tools_dir)):
        if not entry.endswith(".py") or entry == "__init__.py":
            continue
        modules.append("ultron.tools." + entry[:-3])
    return modules


TOOL_HIDDENIMPORTS = discovered_tool_modules()

# ============================================================
# JARVIS Desktop Application
# ============================================================

jarvis_a = Analysis(
    [os.path.join(ROOT, "desktop", "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[
        # Include the frontend files
        (os.path.join(ROOT, "frontend"), "frontend"),
        # Include .env.example as template
        (os.path.join(ROOT, ".env.example"), "."),
        # Include the README
        (os.path.join(ROOT, "README.md"), "."),
    ],
    hiddenimports=[
        # Desktop modules
        "desktop",
        "desktop.config",
        "desktop.process",
        "desktop.server",
        "desktop.tray",
        "desktop.notifications",
        "desktop.window",
        "desktop.main",
        # ULTRON core
        "ultron",
        "ultron.cli",
        "ultron.config",
        "ultron.errors",
        "ultron.models",
        "ultron.pipeline",
        "ultron.planner",
        "ultron.risk",
        "ultron.policy",
        "ultron.sandbox",
        "ultron.browser",
        "ultron.audit",
        "ultron.status",
        "ultron.verification",
        "ultron.logging_setup",
        "ultron.platform",
        "ultron.web",
        "ultron.web_api",
        "ultron.web_broadcaster",
        "ultron.web_static",
        "ultron.permission_manager",
        "ultron.network_security",

        # Phase 5
        "ultron.goal",
        "ultron.task",
        "ultron.context",
        "ultron.response",
        "ultron.agent_manager",
        "ultron.autonomous",
        "ultron.orchestrator",
        "ultron.verification_v5",
        "ultron.execution_state",
        "ultron.recovery",
        # Phase 7 brains
        "ultron.brains",
        "ultron.brains.orchestrator",
        "ultron.brains.router",
        "ultron.brains.capability_router",
        "ultron.brains.provider",
        "ultron.brains.planning",
        "ultron.brains.research",
        "ultron.brains.coding",
        "ultron.brains.computer",
        "ultron.brains.verification",
        # LLM providers
        "ultron.llm",
        "ultron.llm.base",
        "ultron.llm.gemini",
        "ultron.llm.nvidia",
        "ultron.llm.openrouter",
        "ultron.llm.grok",
        "ultron.llm.openai_",
        "ultron.llm.azure_openai",
        "ultron.llm.anthropic",
        "ultron.llm.cohere",
        "ultron.llm.mistral",
        "ultron.llm.perplexity",
        "ultron.llm.bedrock",
        "ultron.llm.router",
        # Memory
        "ultron.memory",
        "ultron.memory.persistent",
        "ultron.memory.semantic",
        # Tools: auto-generated from ultron/tools/*.py. Do not hand-edit; add
        # the module to that directory and it is picked up automatically.
        *TOOL_HIDDENIMPORTS,
        "ultron.tool_selection",
        # Services
        "ultron.services",
        "ultron.services.base",
        "ultron.services.calendar",
        "ultron.services.notes",
        "ultron.services.reminders",
        "ultron.services.memory",
        # Agents
        "ultron.agents",
        "ultron.agents.research",
        "ultron.agents.coding",
        "ultron.agents.task",
        "ultron.agents.vision",
        "ultron.agents.llm_agent",
        "ultron.agents.setup",
        # Actions
        "ultron.actions",
        "ultron.actions.permissions",
        "ultron.actions.audit_log",
        # Windows
        "ultron.windows",
        "ultron.windows.utils",
        # Core
        "ultron.core",
        "ultron.core.agent",
        "ultron.core.brain",
        "ultron.core.router",
        # Desktop dependencies
        "pystray",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        # Native UI host (WebView2 on Windows)
        "webview",
        "webview.guilib",
        "webview.util",
        "webview.http",
        "webview.platforms.winforms",
        "webview.platforms.edgechromium",
        "clr_loader",
        # Python stdlib modules used by ULTRON
        "http.server",
        "socketserver",
        "json",
        "threading",
        "subprocess",
        "ctypes",

    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary GUI frameworks
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        # Exclude test frameworks
        "pytest",
        "unittest.mock",
        # Exclude unnecessary modules
        "IPython",
        "jupyter",
        "notebook",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

jarvis_pyz = PYZ(jarvis_a.pure, jarvis_a.zipped_data, cipher=block_cipher)

jarvis_exe = EXE(
    jarvis_pyz,
    jarvis_a.scripts,
    [],
    exclude_binaries=True,
    name="JARVIS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, "assets", "icons", "jarvis.ico") if os.path.exists(os.path.join(ROOT, "assets", "icons", "jarvis.ico")) else None,
)

jarvis_coll = COLLECT(
    jarvis_exe,
    jarvis_a.binaries,
    jarvis_a.zipfiles,
    jarvis_a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="JARVIS",
)
