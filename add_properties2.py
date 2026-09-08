#!/usr/bin/env python3
"""Add flat properties to Config class in ultron/config.py"""

# Read the file
with open('D:/jarvis/ultron/config.py', 'r') as f:
    content = f.read()

# Find the location of "# Flat properties for 100% backward compatibility"
idx = content.find("# Flat properties for 100% backward compatibility")
if idx < 0:
    print("ERROR: Could not find the marker")
    sys.exit(1)

# The new properties to insert after the marker
new_properties = """

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

# Insert the new properties before the "# Flat properties" line
new_content = content[:idx] + new_properties + content[idx:]

with open('D:/jarvis/ultron/config.py', 'w') as f:
    f.write(new_content)
print("Successfully added flat properties")