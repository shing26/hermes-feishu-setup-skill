# Changelog

All notable changes to this skill will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-08-17

### Added

- Optional `scripts/guardian.py` for multi-profile gateway monitoring and auto-repair.
- Cross-platform gateway startup instructions (Linux/macOS systemd/launchd).

### Changed

- Leading word changed from `connected-but-silent` to `feishu-gateway-setup` to cover setup and diagnosis under one neutral trigger.
- Pitfalls pruned from 12 to 10 verified-only entries.
- SKILL.md description shrunk to a single leading word to reduce context load.

### Fixed

- Step 4 now provides explicit non-Windows paths instead of Windows-only instructions.

## [1.2.0] - 2026-07-24

### Changed

- SKILL.md refactored to leading-word format with fixed diagnosis order.
- Pitfalls consolidated; references tightened.

## [1.1.0] - 2026-07-16

### Added

- Initial public release with per-profile isolation, Windows startup registration,
  and event-subscription pitfalls.
- `references/feishu-events.md` and `references/feishu-diagnosis.md`.
