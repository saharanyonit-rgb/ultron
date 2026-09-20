"""Tool registry — the single place V1 capabilities are collected.

Includes:
  - Original V1 tools (filesystem, apps, browser, screenshot, sysinfo, clipboard)
  - Phase 4 tools (command execution, file ops)
  - Full PC control tools (mouse, keyboard, voice)
  - Unrestricted tools (command execution, filesystem)
  - Android phone control tools (calls, SMS, contacts, touch, settings, etc.)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ultron.tools.apps import CloseApp, OpenApp
from ultron.tools.base import (
    InvalidParametersError,
    InvalidToolError,
    PermissionDeniedError,
    Tool,
    ToolAlreadyExistsError,
    ToolError,
    ToolNotFoundError,
    ToolSpec,
)
from ultron.tools.browser_tools import (
    ClickElement,
    FillFormField,
    NavigateUrl,
    ReadPage,
    TakeBrowserScreenshot,
    ScrollPage,
    PressKey as BrowserPressKey,
    TypeText as BrowserTypeText,
    HoverElement,
    WaitForElement,
    GetPageLinks,
    PlaySongTool,
    get_browser_tools,
)
from ultron.tools.clipboard import GetClipboard, SetClipboard
from ultron.tools.execution import ToolExecutionResult, ToolExecutionStatus, ToolExecutor
from ultron.tools.file_ops import CreateFile, ReadFile, SearchFiles
from ultron.tools.screenshot import TakeScreenshot
from ultron.tools.shutdown import ShutdownTool
from ultron.tools.sysinfo import GetSystemInfo
from ultron.tools.urls import OpenUrl
from ultron.tools.database import QueryDatabase, ListTables, CreateTable
from ultron.tools.git_tool import GitStatus, GitLog, GitDiff, GitBranch, GitCommit
from ultron.tools.web_api import HttpRequest, FetchJson

# Full PC control tools
from ultron.tools.automation import (
    MouseMove,
    MouseClick,
    MouseScroll,
    MouseDrag,
    TypeText,
    PressKey,
    GetScreenInfo,
)

# Unrestricted tools
from ultron.tools.execute import ExecuteCommand, ExecutePowerShell
from ultron.tools.file_ops_unrestricted import (
    ReadFileUnrestricted,
    WriteFileUnrestricted,
    ListDirectoryUnrestricted,
    DeleteFileUnrestricted,
    CopyFileUnrestricted,
    MoveFileUnrestricted,
    SearchFilesUnrestricted,
)

# Voice tools
from ultron.tools.voice import Speak, Listen, GetVoiceState
from ultron.tools.vision import VisionTool
from ultron.tools.time_tool import GetCurrentTime

# Calendar, Notes, Reminder tools
from ultron.tools.calendar_tool import CalendarTool, ListCalendarEventsTool
from ultron.tools.notes_tool import CreateNoteTool, ListNotesTool, SearchNotesTool
from ultron.tools.reminder_tool import CreateReminderTool, ListRemindersTool, CancelReminderTool

# Long-term memory tools
from ultron.tools.memory_tool import (
    ForgetTool,
    ListMemoriesTool,
    RecallTool,
    RememberTool,
)

# UI/UX design generator
from ultron.tools.ui_tool import GenerateUI

# UI/UX Pro Max design intelligence search (installed skill wrapper)
from ultron.tools.uiux_pro_max_tool import SearchUIDesignTool

# Vane Perplexity-style search engine + AgenticSeek autonomous agent backend
from ultron.tools.vane_tool import VaneSearchTool
from ultron.tools.agenticseek_tool import AgenticSeekTaskTool

# GitHub repository tools
from ultron.tools.github_tool import (
    GitHubCloneTool,
    GitHubCreateRepoTool,
    GitHubPullTool,
    GitHubPushTool,
    GitHubSearchTool,
)

# Android phone control tools (only loaded on Android/Termux)
_ANDROID_TOOLS_AVAILABLE = False
try:
    from ultron.platform import is_android as _is_android
    _ANDROID_TOOLS_AVAILABLE = _is_android()
except Exception:
    pass

if _ANDROID_TOOLS_AVAILABLE:
    from ultron.tools.phone_control import MakeCall, AnswerCall, HangUp, RejectCall, GetCallLog
    from ultron.tools.sms_tools import SendSms, ReadSms, ListSms
    from ultron.tools.contacts_tools import ListContacts, SearchContact, AddContact, DeleteContact
    from ultron.tools.alarm_tools import SetAlarm, ListAlarms, CancelAlarm, SetTimer
    from ultron.tools.notification_tools import (
        SendNotification, ListNotifications, RemoveNotification,
        RemoveAllNotifications, GetNotificationSettings,
    )
    from ultron.tools.battery_tools import (
        GetBatteryInfo, ToggleWifi, ToggleBluetooth, ToggleAirplane,
        ToggleData, ToggleDoNotDisturb, SetBrightness, SetVolume,
        GetVolume, ScreenOn, ScreenOff, UnlockScreen,
    )
    from ultron.tools.device_info import (
        GetDeviceInfo, GetNetworkInfo, GetLocation, ScanWifi,
        GetRunningApps, GetInstalledApps, GetStorageInfo, GetMemoryInfo,
    )
    from ultron.tools.media_tools import (
        PlayMedia, PauseMedia, StopMedia, SkipNext, SkipPrevious,
        PlayPause, GetMediaInfo, VibrateDevice, ShowToast,
    )
    from ultron.tools.touch import (
        TapScreen, SwipeScreen, LongPress, DoubleTap,
        InputText, PressBack, PressHome, PressRecent,
        PressKey as AndroidPressKey, DragAndDrop,
    )
    from ultron.tools.screen_reader import (
        GetUiDump, ClickUiElement, ReadScreen,
        GetScreenResolution, GetScreenDensity,
    )

# Re-export error hierarchy from central module
from ultron.errors import (  # noqa: F401
    JarvisError,
    ToolExecutionError,
    VerificationError,
)

ALL_TOOLS: List[Tool] = [
    # ── Original V1 Tools ──────────────────────────────────────
    ReadFile(),
    CreateFile(),
    SearchFiles(),
    OpenApp(),
    CloseApp(),
    OpenUrl(),
    GetClipboard(),
    SetClipboard(),
    TakeScreenshot(),
    GetSystemInfo(),
    # Browser tools
    NavigateUrl(),
    ReadPage(),
    ClickElement(),
    FillFormField(),
    TakeBrowserScreenshot(),
    ScrollPage(),
    BrowserPressKey(),
    BrowserTypeText(),
    HoverElement(),
    WaitForElement(),
    GetPageLinks(),
    PlaySongTool(),
    # ── Mouse/Keyboard Control ─────────────────────────────────
    MouseMove(),
    MouseClick(),
    MouseScroll(),
    MouseDrag(),
    TypeText(),
    PressKey(),
    GetScreenInfo(),
    # ── Unrestricted Command Execution ─────────────────────────
    ExecuteCommand(),
    ExecutePowerShell(),
    # ── Windows Shutdown ───────────────────────────────────────
    ShutdownTool(),
    # ── Unrestricted Filesystem ────────────────────────────────
    ReadFileUnrestricted(),
    WriteFileUnrestricted(),
    ListDirectoryUnrestricted(),
    DeleteFileUnrestricted(),
    CopyFileUnrestricted(),
    MoveFileUnrestricted(),
    SearchFilesUnrestricted(),
    # ── Voice Engine ───────────────────────────────────────────
    Speak(),
    Listen(),
    GetVoiceState(),
    # ── Vision ────────────────────────────────────────────────
    VisionTool(),
    # ── Time & Date ──────────────────────────────────────────
    GetCurrentTime(),
    # ── Calendar ─────────────────────────────────────────────
    CalendarTool(),
    ListCalendarEventsTool(),
    # ── Notes ────────────────────────────────────────────────
    CreateNoteTool(),
    ListNotesTool(),
    SearchNotesTool(),
    # ── Reminders ────────────────────────────────────────────
    CreateReminderTool(),
    ListRemindersTool(),
    CancelReminderTool(),
    # ── Long-Term Memory ─────────────────────────────────────
    RememberTool(),
    RecallTool(),
    ListMemoriesTool(),
    ForgetTool(),
    # ── Database ────────────────────────────────────────────
    QueryDatabase(),
    ListTables(),
    CreateTable(),
    # ── Git Operations ──────────────────────────────────────
    GitStatus(),
    GitLog(),
    GitDiff(),
    GitBranch(),
    GitCommit(),
    # ── GitHub Integration ─────────────────────────────────
    GitHubSearchTool(),
    GitHubCloneTool(),
    GitHubCreateRepoTool(),
    GitHubPushTool(),
    GitHubPullTool(),
    # ── UI/UX Design Generator ─────────────────────────────
    GenerateUI(),
    # ── UI/UX Design Intelligence Search ──────────────────
    SearchUIDesignTool(),
    # ── Vane Cited-Source Search Engine ─────────────────────
    VaneSearchTool(),
    # ── AgenticSeek Autonomous Agent Backend ────────────────
    AgenticSeekTaskTool(),
    # ── Web API ─────────────────────────────────────────────
    HttpRequest(),
    FetchJson(),
]

# ── Android Phone Control Tools (conditionally loaded) ───────────────
if _ANDROID_TOOLS_AVAILABLE:
    ALL_TOOLS.extend([
        # Calls
        MakeCall(),
        AnswerCall(),
        HangUp(),
        RejectCall(),
        GetCallLog(),
        # SMS
        SendSms(),
        ReadSms(),
        ListSms(),
        # Contacts
        ListContacts(),
        SearchContact(),
        AddContact(),
        DeleteContact(),
        # Alarms & Timers
        SetAlarm(),
        ListAlarms(),
        CancelAlarm(),
        SetTimer(),
        # Notifications
        SendNotification(),
        ListNotifications(),
        RemoveNotification(),
        RemoveAllNotifications(),
        GetNotificationSettings(),
        # Battery & Settings
        GetBatteryInfo(),
        ToggleWifi(),
        ToggleBluetooth(),
        ToggleAirplane(),
        ToggleData(),
        ToggleDoNotDisturb(),
        SetBrightness(),
        SetVolume(),
        GetVolume(),
        ScreenOn(),
        ScreenOff(),
        UnlockScreen(),
        # Device Info
        GetDeviceInfo(),
        GetNetworkInfo(),
        GetLocation(),
        ScanWifi(),
        GetRunningApps(),
        GetInstalledApps(),
        GetStorageInfo(),
        GetMemoryInfo(),
        # Media Control
        PlayMedia(),
        PauseMedia(),
        StopMedia(),
        SkipNext(),
        SkipPrevious(),
        PlayPause(),
        GetMediaInfo(),
        VibrateDevice(),
        ShowToast(),
        # Touch Input
        TapScreen(),
        SwipeScreen(),
        LongPress(),
        DoubleTap(),
        InputText(),
        PressBack(),
        PressHome(),
        PressRecent(),
        AndroidPressKey(),
        DragAndDrop(),
        # Screen Reader / Vision
        GetUiDump(),
        ClickUiElement(),
        ReadScreen(),
        GetScreenResolution(),
        GetScreenDensity(),
    ])


class ToolRegistry:
    """Authoritative registry for discovering, registering, and retrieving tools."""

    def __init__(self, tools: Optional[List[Tool]] = None) -> None:
        self._tools: Dict[str, Tool] = {}
        for t in (tools if tools is not None else ALL_TOOLS):
            self.register(t)

    def register(self, tool: Tool, allow_overwrite: bool = False) -> None:
        """Register a new tool instance in the registry."""
        if not hasattr(tool, "name") or not str(getattr(tool, "name", "")).strip() or not callable(getattr(tool, "run", None)):
            raise InvalidToolError("Cannot register invalid tool: must have a non-empty name and a callable run method.")
        name = str(tool.name).strip()
        if name in self._tools and not allow_overwrite:
            raise ToolAlreadyExistsError(f"Tool '{name}' is already registered.")
        self._tools[name] = tool

    def unregister(self, name: str) -> Optional[Tool]:
        """Remove a tool from the registry by name."""
        return self._tools.pop(name, None)

    def exists(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def get(self, name: str) -> Optional[Tool]:
        """Retrieve a registered tool by name."""
        return self._tools.get(name)

    def all(self) -> List[Tool]:
        """Return a list of all registered tools."""
        return list(self._tools.values())

    def specs(self) -> List[ToolSpec]:
        """Return specs for all registered tools."""
        return [t.spec for t in self._tools.values()]


__all__ = [
    "Tool",
    "ToolSpec",
    "ToolRegistry",
    "ToolExecutor",
    "ToolExecutionResult",
    "ToolExecutionStatus",
    "ALL_TOOLS",
    "ToolError",
    "ToolNotFoundError",
    "ToolAlreadyExistsError",
    "InvalidToolError",
    "InvalidParametersError",
    "PermissionDeniedError",
]
