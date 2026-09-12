"""Tests for Android phone control tools.

These tests validate tool definitions, schemas, and behavior
using mocked Termux commands (no real Android device needed).
"""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


# ── Mock _termux module for all tests ──────────────────────────────

class MockTermuxResult:
    def __init__(self, stdout="", stderr="", returncode=0, data=None):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.data = data

    @property
    def ok(self):
        return self.returncode == 0


def _mock_run_termux(subcommand, args=None, stdin_text=None, timeout=15, parse_json=False):
    return MockTermuxResult(stdout="ok", returncode=0, data={})

def _mock_run_cmd(args, timeout=15):
    return MockTermuxResult(stdout="ok", returncode=0)

def _mock_run_am(args):
    return MockTermuxResult(stdout="ok", returncode=0)

def _mock_run_settings(args):
    return MockTermuxResult(stdout="ok", returncode=0)


# ── Phone Control Tests ───────────────────────────────────────────

class TestPhoneControl:
    @patch("ultron.tools.phone_control.run_am", side_effect=_mock_run_am)
    def test_make_call(self, mock_am):
        from ultron.tools.phone_control import MakeCall
        tool = MakeCall()
        result = tool.run(number="+1234567890")
        assert result["success"] is True
        assert result["number"] == "+1234567890"

    def test_make_call_no_number(self):
        from ultron.tools.phone_control import MakeCall
        tool = MakeCall()
        result = tool.run()
        assert result["success"] is False
        assert "error" in result

    @patch("ultron.tools.phone_control.run_cmd", side_effect=_mock_run_cmd)
    def test_answer_call(self, mock_cmd):
        from ultron.tools.phone_control import AnswerCall
        tool = AnswerCall()
        result = tool.run()
        assert result["success"] is True

    @patch("ultron.tools.phone_control.run_cmd", side_effect=_mock_run_cmd)
    def test_hang_up(self, mock_cmd):
        from ultron.tools.phone_control import HangUp
        tool = HangUp()
        result = tool.run()
        assert result["success"] is True

    @patch("ultron.tools.phone_control.run_termux", side_effect=_mock_run_termux)
    def test_get_call_log(self, mock_termux):
        from ultron.tools.phone_control import GetCallLog
        tool = GetCallLog()
        result = tool.run()
        assert "calls" in result
        assert "count" in result


# ── SMS Tests ──────────────────────────────────────────────────────

class TestSMS:
    @patch("ultron.tools.sms_tools.run_termux", side_effect=_mock_run_termux)
    def test_send_sms(self, mock_termux):
        from ultron.tools.sms_tools import SendSms
        tool = SendSms()
        result = tool.run(to="+1234567890", message="Hello")
        assert result["success"] is True
        assert result["to"] == "+1234567890"

    def test_send_sms_no_recipient(self):
        from ultron.tools.sms_tools import SendSms
        tool = SendSms()
        result = tool.run()
        assert result["success"] is False

    @patch("ultron.tools.sms_tools.run_termux", side_effect=_mock_run_termux)
    def test_read_sms(self, mock_termux):
        from ultron.tools.sms_tools import ReadSms
        tool = ReadSms()
        result = tool.run()
        assert "messages" in result


# ── Contacts Tests ─────────────────────────────────────────────────

class TestContacts:
    @patch("ultron.tools.contacts_tools.run_termux", side_effect=_mock_run_termux)
    def test_list_contacts(self, mock_termux):
        from ultron.tools.contacts_tools import ListContacts
        tool = ListContacts()
        result = tool.run()
        assert "contacts" in result

    @patch("ultron.tools.contacts_tools.run_termux", side_effect=_mock_run_termux)
    def test_add_contact(self, mock_termux):
        from ultron.tools.contacts_tools import AddContact
        tool = AddContact()
        result = tool.run(name="Test User", number="1234567890")
        assert result["success"] is True
        assert result["name"] == "Test User"

    def test_add_contact_missing(self):
        from ultron.tools.contacts_tools import AddContact
        tool = AddContact()
        result = tool.run()
        assert result["success"] is False


# ── Battery & Settings Tests ──────────────────────────────────────

class TestBatteryAndSettings:
    @patch("ultron.tools.battery_tools.run_termux", side_effect=_mock_run_termux)
    def test_get_battery(self, mock_termux):
        from ultron.tools.battery_tools import GetBatteryInfo
        tool = GetBatteryInfo()
        result = tool.run()
        assert "level" in result

    @patch("ultron.tools.battery_tools.run_termux", side_effect=_mock_run_termux)
    def test_toggle_wifi(self, mock_termux):
        from ultron.tools.battery_tools import ToggleWifi
        tool = ToggleWifi()
        result = tool.run(enabled=True)
        assert result["success"] is True
        assert result["enabled"] is True

    @patch("ultron.tools.battery_tools.run_am", side_effect=_mock_run_am)
    def test_toggle_bluetooth(self, mock_am):
        from ultron.tools.battery_tools import ToggleBluetooth
        tool = ToggleBluetooth()
        result = tool.run(enabled=False)
        assert result["success"] is True

    @patch("ultron.tools.battery_tools.run_settings", side_effect=_mock_run_settings)
    def test_toggle_airplane(self, mock_settings):
        from ultron.tools.battery_tools import ToggleAirplane
        tool = ToggleAirplane()
        result = tool.run(enabled=True)
        assert result["success"] is True

    @patch("ultron.tools.battery_tools.run_termux", side_effect=_mock_run_termux)
    def test_set_brightness(self, mock_termux):
        from ultron.tools.battery_tools import SetBrightness
        tool = SetBrightness()
        result = tool.run(level=200)
        assert result["success"] is True
        assert result["level"] == 200

    @patch("ultron.tools.battery_tools.run_termux", side_effect=_mock_run_termux)
    def test_set_volume(self, mock_termux):
        from ultron.tools.battery_tools import SetVolume
        tool = SetVolume()
        result = tool.run(stream="music", level=12)
        assert result["success"] is True

    @patch("ultron.tools.battery_tools.run_cmd", side_effect=_mock_run_cmd)
    def test_screen_on(self, mock_cmd):
        from ultron.tools.battery_tools import ScreenOn
        tool = ScreenOn()
        result = tool.run()
        assert result["success"] is True

    @patch("ultron.tools.battery_tools.run_cmd", side_effect=_mock_run_cmd)
    def test_unlock_screen(self, mock_cmd):
        from ultron.tools.battery_tools import UnlockScreen
        tool = UnlockScreen()
        result = tool.run()
        assert result["success"] is True


# ── Device Info Tests ─────────────────────────────────────────────

class TestDeviceInfo:
    @patch("ultron.tools.device_info.run_cmd", side_effect=_mock_run_cmd)
    def test_get_device_info(self, mock_cmd):
        from ultron.tools.device_info import GetDeviceInfo
        tool = GetDeviceInfo()
        result = tool.run()
        assert "model" in result
        assert "android_version" in result

    @patch("ultron.tools.device_info.run_termux", side_effect=_mock_run_termux)
    def test_get_network_info(self, mock_termux):
        from ultron.tools.device_info import GetNetworkInfo
        tool = GetNetworkInfo()
        result = tool.run()
        assert "ssid" in result

    @patch("ultron.tools.device_info.run_termux", side_effect=_mock_run_termux)
    def test_get_location(self, mock_termux):
        from ultron.tools.device_info import GetLocation
        tool = GetLocation()
        result = tool.run()
        assert "latitude" in result
        assert "longitude" in result

    @patch("ultron.tools.device_info.run_cmd", side_effect=_mock_run_cmd)
    def test_get_installed_apps(self, mock_cmd):
        from ultron.tools.device_info import GetInstalledApps
        tool = GetInstalledApps()
        result = tool.run()
        assert "apps" in result


# ── Media Tests ────────────────────────────────────────────────────

class TestMedia:
    @patch("ultron.tools.media_tools.run_termux", side_effect=_mock_run_termux)
    def test_play_media(self, mock_termux):
        from ultron.tools.media_tools import PlayMedia
        tool = PlayMedia()
        result = tool.run(source="/sdcard/music.mp3")
        assert result["success"] is True

    @patch("ultron.tools.media_tools.run_cmd", side_effect=_mock_run_cmd)
    def test_play_pause(self, mock_cmd):
        from ultron.tools.media_tools import PlayPause
        tool = PlayPause()
        result = tool.run()
        assert result["success"] is True

    @patch("ultron.tools.media_tools.run_termux", side_effect=_mock_run_termux)
    def test_vibrate(self, mock_termux):
        from ultron.tools.media_tools import VibrateDevice
        tool = VibrateDevice()
        result = tool.run(duration_ms=500)
        assert result["success"] is True

    @patch("ultron.tools.media_tools.run_termux", side_effect=_mock_run_termux)
    def test_show_toast(self, mock_termux):
        from ultron.tools.media_tools import ShowToast
        tool = ShowToast()
        result = tool.run(message="Hello from Ultron!")
        assert result["success"] is True


# ── Touch Tests ────────────────────────────────────────────────────

class TestTouch:
    @patch("ultron.tools.touch.run_cmd", side_effect=_mock_run_cmd)
    def test_tap_screen(self, mock_cmd):
        from ultron.tools.touch import TapScreen
        tool = TapScreen()
        result = tool.run(x=500, y=1000)
        assert result["x"] == 500
        assert result["y"] == 1000

    @patch("ultron.tools.touch.run_cmd", side_effect=_mock_run_cmd)
    def test_swipe_screen(self, mock_cmd):
        from ultron.tools.touch import SwipeScreen
        tool = SwipeScreen()
        result = tool.run(x1=100, y1=500, x2=100, y2=200)
        assert result["from"] == [100, 500]
        assert result["to"] == [100, 200]

    @patch("ultron.tools.touch.run_cmd", side_effect=_mock_run_cmd)
    def test_long_press(self, mock_cmd):
        from ultron.tools.touch import LongPress
        tool = LongPress()
        result = tool.run(x=300, y=600, duration_ms=1500)
        assert result["duration_ms"] == 1500

    @patch("ultron.tools.touch.run_cmd", side_effect=_mock_run_cmd)
    def test_input_text(self, mock_cmd):
        from ultron.tools.touch import InputText
        tool = InputText()
        result = tool.run(text="Hello World")
        assert result["typed"] == "Hello World"
        assert result["length"] == 11

    @patch("ultron.tools.touch.run_cmd", side_effect=_mock_run_cmd)
    def test_press_back(self, mock_cmd):
        from ultron.tools.touch import PressBack
        tool = PressBack()
        result = tool.run()
        assert result["success"] is True

    @patch("ultron.tools.touch.run_cmd", side_effect=_mock_run_cmd)
    def test_press_home(self, mock_cmd):
        from ultron.tools.touch import PressHome
        tool = PressHome()
        result = tool.run()
        assert result["success"] is True

    @patch("ultron.tools.touch.run_cmd", side_effect=_mock_run_cmd)
    def test_press_key(self, mock_cmd):
        from ultron.tools.touch import PressKey
        tool = PressKey()
        result = tool.run(key="enter")
        assert result["success"] is True

    @patch("ultron.tools.touch.run_cmd", side_effect=_mock_run_cmd)
    def test_double_tap(self, mock_cmd):
        from ultron.tools.touch import DoubleTap
        tool = DoubleTap()
        result = tool.run(x=500, y=1000)
        assert result["success"] is True


# ── Alarm Tests ────────────────────────────────────────────────────

class TestAlarms:
    @patch("ultron.tools.alarm_tools.run_termux", side_effect=_mock_run_termux)
    def test_set_alarm(self, mock_termux):
        from ultron.tools.alarm_tools import SetAlarm
        tool = SetAlarm()
        result = tool.run(time="07:30", label="Wake up")
        assert result["success"] is True

    @patch("ultron.tools.alarm_tools.run_termux", side_effect=_mock_run_termux)
    def test_list_alarms(self, mock_termux):
        from ultron.tools.alarm_tools import ListAlarms
        tool = ListAlarms()
        result = tool.run()
        assert "alarms" in result

    @patch("ultron.tools.alarm_tools.run_termux", side_effect=_mock_run_termux)
    def test_set_timer(self, mock_termux):
        from ultron.tools.alarm_tools import SetTimer
        tool = SetTimer()
        result = tool.run(seconds=60)
        assert result["success"] is True
        assert result["seconds"] == 60


# ── Notification Tests ────────────────────────────────────────────

class TestNotifications:
    @patch("ultron.tools.notification_tools.run_termux", side_effect=_mock_run_termux)
    def test_send_notification(self, mock_termux):
        from ultron.tools.notification_tools import SendNotification
        tool = SendNotification()
        result = tool.run(title="Test", message="Hello")
        assert result["success"] is True

    @patch("ultron.tools.notification_tools.run_termux", side_effect=_mock_run_termux)
    def test_list_notifications(self, mock_termux):
        from ultron.tools.notification_tools import ListNotifications
        tool = ListNotifications()
        result = tool.run()
        assert "notifications" in result

    @patch("ultron.tools.notification_tools.run_termux", side_effect=_mock_run_termux)
    def test_remove_notification(self, mock_termux):
        from ultron.tools.notification_tools import RemoveNotification
        tool = RemoveNotification()
        result = tool.run(id="123")
        assert result["success"] is True


# ── Screen Reader Tests ───────────────────────────────────────────

class TestScreenReader:
    @patch("ultron.tools.screen_reader.run_cmd")
    def test_get_screen_resolution(self, mock_cmd):
        mock_cmd.return_value = MockTermuxResult(stdout="Physical size: 1080x2400", returncode=0)
        from ultron.tools.screen_reader import GetScreenResolution
        tool = GetScreenResolution()
        result = tool.run()
        assert result["width"] == 1080
        assert result["height"] == 2400

    @patch("ultron.tools.screen_reader.run_cmd")
    def test_get_screen_density(self, mock_cmd):
        mock_cmd.return_value = MockTermuxResult(stdout="Physical density: 420", returncode=0)
        from ultron.tools.screen_reader import GetScreenDensity
        tool = GetScreenDensity()
        result = tool.run()
        assert result["density"] == 420


# ── Tool Schema Tests ─────────────────────────────────────────────

class TestToolSchemas:
    """Verify all Android tools have valid schema definitions."""

    def _import_all_android_tools(self):
        tools = []
        modules = [
            "ultron.tools.phone_control",
            "ultron.tools.sms_tools",
            "ultron.tools.contacts_tools",
            "ultron.tools.alarm_tools",
            "ultron.tools.notification_tools",
            "ultron.tools.battery_tools",
            "ultron.tools.device_info",
            "ultron.tools.media_tools",
            "ultron.tools.touch",
            "ultron.tools.screen_reader",
        ]
        import importlib
        import inspect
        for mod_name in modules:
            mod = importlib.import_module(mod_name)
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (inspect.isclass(attr)
                        and hasattr(attr, "name")
                        and hasattr(attr, "run")
                        and attr_name != "Tool"
                        and not inspect.isabstract(attr)):
                    try:
                        tools.append(attr())
                    except Exception:
                        pass
        return tools

    def test_all_tools_have_name_and_description(self):
        tools = self._import_all_android_tools()
        assert len(tools) > 0, "No Android tools found"
        for tool in tools:
            assert tool.name, f"{tool.__class__.__name__} has no name"
            assert tool.description, f"{tool.name} has no description"

    def test_all_tools_have_parameters_schema(self):
        tools = self._import_all_android_tools()
        for tool in tools:
            assert "type" in tool.parameters, f"{tool.name} parameters missing 'type'"
            assert "properties" in tool.parameters, f"{tool.name} parameters missing 'properties'"

    def test_all_tools_have_output_schema(self):
        tools = self._import_all_android_tools()
        for tool in tools:
            assert "type" in tool.output_schema, f"{tool.name} output_schema missing 'type'"
            assert "properties" in tool.output_schema, f"{tool.name} output_schema missing 'properties'"

    def test_tool_names_are_unique(self):
        tools = self._import_all_android_tools()
        names = [t.name for t in tools]
        assert len(names) == len(set(names)), f"Duplicate tool names: {[n for n in names if names.count(n) > 1]}"


# ── Termux Wrapper Tests ──────────────────────────────────────────

class TestTermuxWrapper:
    def test_termux_result_ok(self):
        from ultron.tools._termux import TermuxResult
        result = TermuxResult(command="test", returncode=0)
        assert result.ok is True

    def test_termux_result_error(self):
        from ultron.tools._termux import TermuxResult
        result = TermuxResult(command="test", returncode=1, stderr="error")
        assert result.ok is False

    def test_termux_result_to_dict(self):
        from ultron.tools._termux import TermuxResult
        result = TermuxResult(command="test", returncode=0, data={"key": "value"})
        d = result.to_dict()
        assert d["success"] is True
        assert d["data"] == {"key": "value"}
