# PsychAid — release hardening runlist

Ordered so large changes land first and verification happens after them.

| # | Task | Status |
|---|------|--------|
| 0 | Recon: identify AI provider, locate Gemini demo key, inventory tests | done |
| 1 | Provider interface + Anthropic and Gemini implementations | pending |
| 2 | Settings UI: pick provider, API key **or** subscription/env auth | pending |
| 3 | Packaging: Start Menu / Applications entry, Win10 + Win11, no preinstalled Python | pending |
| 4 | Test suite: unit + integration + live provider smoke | pending |
| 5 | Security review incl. proof no API key is baked into any release artifact | pending |
| 6 | End-to-end verification: CI, Windows 11 VM, Windows 10 VM, macOS arm64 | pending |
| 7 | Final release + report | pending |

## Recon findings (task 0)

- **Provider in use:** Anthropic only. `report_generator.py:generate_report` constructs
  `anthropic.Anthropic(api_key=...)` and hardcodes `model='claude-opus-4-5'`.
  No abstraction, no model config, no second provider.
- **Gemini key:** found in `~/cyberglass/smart_import/.env` as `GEMINI_API_KEY`.
  Verified live against `generativelanguage.googleapis.com`. `gemini-2.0-flash` is
  retired; `gemini-flash-latest` is the stable alias to target.
  The key stays outside the repo (scratchpad, chmod 600) and must never be committed.
- **Tests:** none in the repository. `main.py --selftest` is the only check and it is
  not a test suite.
- **Intel Mac CI:** `macos-13` jobs have sat queued for >1h while `windows-latest` and
  `macos-14` finish in minutes. Per instruction to skip the slow Mac variant, the Intel
  job is dropped; Apple Silicon is kept.

## Decisions

- Config gains `provider`, `model`, and per-provider auth. Existing `api_key` values are
  migrated to the Anthropic provider so current installs keep working.
- "Subscription" = auth that is not a user-pasted key: an environment variable or an
  ambient credential the machine already has. Selecting it means the app sends no key of
  its own.
- Windows ships an installer (Start Menu + Add/Remove Programs) rather than a bare exe,
  because a loose exe in Downloads never appears in the app selector.
