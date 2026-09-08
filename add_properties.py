#!/usr/bin/env python3
"""Add flat properties to Config class in ultron/config.py"""

import sys

# Read the file
with open('D:/jarvis/ultron/config.py', 'r') as f:
    content = f.read()

# Find the location after execution_state_enabled property and add the new properties
old_text = """    @property
    def execution_state_enabled(self) -> bool:
        return self.execution.execution_state_enabled

# Flat properties for 100% backward compatibility"""

new_text = """    @property
    def execution_state_enabled(self) -> bool:
        return self.execution.execution_state_enabled

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
        return self._microphone_enabled

# Flat properties for 100% backward compatibility"""

if old_text in content:
    content = content.replace(old_text, new_text)
    with open('D:/jarvis/ultron/config.py', 'w') as f:
        f.write(content)
    print("Successfully added flat properties")
else:
    print("Old text not found!")
    # Try to find the location
    idx = content.find("# Flat properties for 100% backward compatibility")
    if idx >= 0:
        print(f"Found at index: {idx}")
        print(content[idx-200:idx+200])