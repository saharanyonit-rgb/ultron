"""Allow running desktop module directly: python -m desktop"""

from desktop.main import main

if __name__ == "__main__":
    raise SystemExit(main())
