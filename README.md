# PsychAid

Local desktop app for psychometric scale forms and report generation.

## Install

Download the file for your machine from the [latest release](../../releases/latest) and open it.

| Machine | File | What to do |
|---|---|---|
| Windows | `PsychAid-windows-x64.zip` | Download the .zip, extract it, then run `PsychAid.exe`. |
| Mac (Apple Silicon only, M1–M4) | `PsychAid-macos-arm64.dmg` | Open the .dmg and drag PsychAid to Applications, which puts it in Launchpad and Spotlight. |

Windows 10 and Windows 11 are both supported, and Python is **not** required.

### First launch

The app is not code-signed yet, so each OS warns once:

- **Windows** — "Windows protected your PC" → *More info* → *Run anyway*.
- **macOS** — the app is blocked on first open → System Settings → Privacy & Security → *Open Anyway*.

After that it launches normally.

## Setup inside the app

Report generation needs an Anthropic API key: **Settings** → paste key → Save.
It is stored in `~/Library/Application Support/PsychAid/config.json` (macOS) or
`%APPDATA%\PsychAid\config.json` (Windows).

## Cutting a release

Releases are built by GitHub Actions (`.github/workflows/release.yml`) on any `v*` tag:

```
git tag v1.0.0 && git push origin v1.0.0
```

Windows and Apple Silicon builds are attached to a **draft** release —
review it on the Releases page, then publish.

## Running from source (developers)

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```
