# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for JARVIS Desktop Application.

This spec builds two executables:
1. JARVIS.exe - The desktop application (tray + browser launcher + process manager)
2. ultron_backend.exe - The ULTRON backend server (optional, can also use Python directly)
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Project root
ROOT = os.path.dirname(os.path.abspath(SPEC))

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
        # Tools
        "ultron.tools",
        "ultron.tools.execution",
        "ultron.tools.filesystem",
        "ultron.tools.command",
        "ultron.tools.base",
        "ultron.tools.file_ops",
        "ultron.tools.file_ops_unrestricted",
        "ultron.tools.apps",
        "ultron.tools.urls",
        "ultron.tools.clipboard",
        "ultron.tools.screenshot",
        "ultron.tools.sysinfo",
        "ultron.tools.voice",
        "ultron.tools.vision",
        "ultron.tools.time_tool",
        "ultron.tools.shutdown",
        "ultron.tools.automation",
        "ultron.tools.browser_tools",
        "ultron.tools.calendar_tool",
        "ultron.tools.notes_tool",
        "ultron.tools.reminder_tool",
        "ultron.tools.memory_tool",
        "ultron.tools.database",
        "ultron.tools.git_tool",
        "ultron.tools.github_tool",
        "ultron.tools.web_api",
        "ultron.tools.ui_tool",
        "ultron.tools.uiux_pro_max_tool",
        "ultron.tools.notification_tools",
        "ultron.tools.device_info",
        "ultron.tools.media_tools",
        "ultron.tools.battery_tools",
        "ultron.tools.contacts_tools",
        "ultron.tools.sms_tools",
        "ultron.tools.alarm_tools",
        "ultron.tools.execute",
        "ultron.tools.touch",
        "ultron.tools.screen_reader",
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
