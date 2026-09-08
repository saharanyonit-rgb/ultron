#!/usr/bin/env python3
"""Add flat properties to Config class"""

with open('D:/jarvis/ultron/config.py', 'r') as f:
    content = f.read()

# Find the return Config( ... ) line and add properties after it
marker = "    return Config(\n        llm=llm,\n        memory=memory,\n        security=security,\n        execution=execution,\n        brain=brain,\n        log_level=\"DEBUG\" if debug else (get(\"LOG_LEVEL\", \"INFO\").strip().upper() or \"INFO\"),\n        debug_mode=debug,\n    )"

new_marker = marker + """


# Flat properties for 100% backward compatibility
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

if marker in content:
    content = content.replace(marker, new_marker)
    with open('D:/jarvis/ultron/config.py', 'w') as f:
        f.write(content)
    print("Successfully added flat properties")
else:
    print("Marker not found!")
    # Try to find return Config
    idx = content.find("return Config(")
    if idx >= 0:
        print(f"Found return Config at index {idx}")
        print(content[idx:idx+200])