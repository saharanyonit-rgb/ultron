#!/usr/bin/env python3
"""Fix indentation in config.py"""

with open('D:/jarvis/ultron/config.py', 'r') as f:
    content = f.read()

# The flat properties have 4-space indent but should have none (they're class-level properties)
# Replace the incorrectly indented properties with correct ones
old_props = """# Flat properties for 100% backward compatibility
@property
    def auto_start(self) -> bool:
        return self._auto_start

    @property
    def auto_open_ui(self) -> bool:
        return self._auto_open_ui

    @property
    def fullscreen(self) -> bool:
        return self._fullscreen

    @property
    def display(self) -> str:
        return self._display

    @property
    def ui_url(self) -> str:
        return self._ui_url

    @property
    def wake_word_enabled(self) -> bool:
        return self._wake_word_enabled

    @property
    def wake_word(self) -> str:
        return self._wake_word

    @property
    def double_clap_enabled(self) -> bool:
        return self._double_clap_enabled

    @property
    def double_clap_min_interval_ms(self) -> int:
        return self._double_clap_min_interval_ms

    @property
    def double_clap_max_interval_ms(self) -> int:
        return self._double_clap_max_interval_ms

    @property
    def double_clap_cooldown_ms(self) -> int:
        return self._double_clap_cooldown_ms

    @property
    def microphone_enabled(self) -> bool:
        return self._microphone_enabled"""

new_props = """# Flat properties for 100% backward compatibility
@property
def auto_start(self) -> bool:
    return self._auto_start

@property
def auto_open_ui(self) -> bool:
    return self._auto_open_ui

@property
def fullscreen(self) -> bool:
    return self._fullscreen

@property
def display(self) -> str:
    return self._display

@property
def ui_url(self) -> str:
    return self._ui_url

@property
def wake_word_enabled(self) -> bool:
    return self._wake_word_enabled

@property
def wake_word(self) -> str:
    return self._wake_word

@property
def double_clap_enabled(self) -> bool:
    return self._double_clap_enabled

@property
def double_clap_min_interval_ms(self) -> int:
    return self._double_clap_min_interval_ms

@property
def double_clap_max_interval_ms(self) -> int:
    return self._double_clap_max_interval_ms

@property
def double_clap_cooldown_ms(self) -> int:
    return self._double_clap_cooldown_ms

@property
def microphone_enabled(self) -> bool:
    return self._microphone_enabled"""

if old_props in content:
    content = content.replace(old_props, new_props)
    with open('D:/jarvis/ultron/config.py', 'w') as f:
        f.write(content)
    print("Fixed indentation")
else:
    print("Pattern not found")