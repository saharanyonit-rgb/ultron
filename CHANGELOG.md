# Changelog
All notable changes are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
Versioning: [Semantic Versioning](https://semver.org/)
---
## [Unreleased]
### Added
- GitHub Actions CI/CD (test, lint, build, release workflows)
- CodeQL weekly security scanning
- CONTRIBUTING.md - guide for adding tools, providers, brains
- SECURITY.md - vulnerability reporting and security design
- CHANGELOG.md - this file
- Structured GitHub issue templates (bug report, feature request)
- Pull request template with tool/provider/brain checklist
- scripts/ directory - all dev/launcher utilities organized here
### Changed
- Removed dev one-off scripts from root
- Removed binary blobs from git (distributed via GitHub Releases)
- Expanded .gitignore to cover binaries, IDEs, Windows files
- Upgraded pyproject.toml with full metadata, ruff, mypy config
- Rewrote README with badges, tables, and clean Quick Start
---
## [0.1.0] - 2026-09-01
### Added
- Phase 1-7 complete: 11 LLM providers, 60+ tools, 6 specialized brains
- 3-tier memory: in-session, persistent (JSONL), semantic (vector)
- Windows desktop shell (pystray), Web UI (SSE), Android companion
- 1001-test pytest suite (1000 passing)
- PyInstaller packaging - single .exe and portable .zip
- Permission gates, audit logging, secret-redacting log formatter
---
[Unreleased]: https://github.com/saharanyonit-rgb/ultron/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/saharanyonit-rgb/ultron/releases/tag/v0.1.0
