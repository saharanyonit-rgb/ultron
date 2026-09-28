# Scripts
Developer utilities and launcher scripts - not part of the importable package.
| Script | Purpose |
|---|---|
| `launch_jarvis.py` | Windows Startup folder launcher - auto-starts JARVIS on login |
| `ultron_backend.py` | PyInstaller entry point for headless backend mode |
| `ultron_desktop_entry.py` | PyInstaller entry point for desktop shell mode |
| `generate_icon.py` | Generates `assets/icon.ico` from source SVG |
| `setup_android.sh` | Sets up the Android build environment |
## Auto-Start on Windows Login
1. Press `Win + R`, type `shell:startup`, press Enter
2. Create a shortcut to `scripts\launch_jarvis.py` in that folder
