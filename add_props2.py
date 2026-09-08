#!/usr/bin/env python3
"""Add new flat properties after existing ones"""

with open('D:/jarvis/ultron/config.py', 'r') as f:
    content = f.read()

# Find the line "    @property" after "def max_concurrent_tasks" and add new properties after it
# Look for the pattern after max_concurrent_tasks property
old_text = """    @property
    def max_concurrent_tasks(self) -> int:
        return self.execution.max_concurrent_tasks


"""

new_text = """    @property
    def max_concurrent_tasks(self) -> int:
        return self.execution.max_concurrent_tasks

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

if old_text in content:
    content = content.replace(old_text, new_text)
    with open('D:/jarvis/ultron/config.py', 'w') as f:
        f.write(content)
    print("Successfully added new flat properties")
else:
    print("Pattern not found - showing context...")
    # Try to find max_concurrent_tasks
    idx = content.find("def max_concurrent_tasks")
    if idx >= 0:
        print(f"Found at index {idx}")
        print(content[idx:idx+300])