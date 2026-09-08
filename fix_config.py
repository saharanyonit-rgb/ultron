#!/usr/bin/env python3
"""Fix the syntax error in ultron/config.py"""

with open('D:/jarvis/ultron/config.py', 'r') as f:
    lines = f.readlines()

# Find the problematic line and fix it
new_lines = []
skip_next = False
for i, line in enumerate(lines):
    if i > 390 and i < 410:
        # Check if this is the problematic section
        if 'microphone_enabled: bool = True,)' in line:
            # Skip this line and the next few lines until we hit the right place
            skip_next = True
            # Print what we're skipping for debugging
            print(f"Skipping line {i}: {line.strip()}")
            continue
        elif skip_next and line.strip().startswith(') -> None:'):
            # This is the line we want to keep or modify
            skip_next = False
            # Keep this line but maybe adjust it
            new_lines.append(line)
            continue
        elif skip_next:
            continue
    
    new_lines.append(line)

with open('D:/jarvis/ultron/config.py', 'w') as f:
    f.writelines(new_lines)
print("Fixed the config file")