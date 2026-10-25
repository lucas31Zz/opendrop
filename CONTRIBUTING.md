# Contributing to OpenDrop

Thanks for your interest in the project. This document explains how to
submit a fix or a feature.

## Prerequisites

- Python **3.10+** (developed and tested on 3.12)
- **Node 20+** and **Rust** (via [rustup](https://rustup.rs)) if you touch
  the desktop app (Tauri 2 + React, Windows or Linux); on Linux the
  runtime packages too: `libwebkit2gtk-4.1-0 libayatana-appindicator3-1`
  (and the `-dev` variants to build)
- `git`

## Setup

```powershell
git clone https://github.com/lucas31Zz/opendrop.git
cd opendrop
pip install -e .
```

## Tests

The suites are homegrown (no external framework), run from the repo root.
**Everything must pass before a PR**:

```powershell
python -m tests.test_security     # 35
python -m tests.test_routes       # 50
python -m tests.test_paths        # 41
python -m tests.test_quota        # 40
python -m tests.test_sessions     # 34
python -m tests.test_tls          # 15
python -m tests.test_server       # 42
python -m tests.test_beta         # 63
python -m tests.test_devices      # 62
python -m tests.test_zip_web      # 47
python -m tests.test_e2e          # 16
```

Eleven suites, 445 checks in total.

- Every suite exits with a non-zero status when it fails.
- `python -m tests.test_beta --large` (75) is slower: run it before merging
  changes that touch the protocol or the multipart handling.
- Tests **always** work in a temporary folder created by
  `tests/conftest.py`: no user file is read, written, or deleted. Never
  break that isolation.

## Conventions

- **Code and comments in English**: the server, the desktop app and the
  documentation are all written in English. French only exists as an
  *interface* language (`"language": "fr"`), never as a source language.
  Same for commit messages.
- **No out-of-scope refactoring**: if a fix is 3 lines long, it stays 3
  lines.
- No new dependency without discussing it first (issues).
- No secrets, keys, certificates, or personal paths in the repo
  (`config.json`, `session.json`, `certs/` stay out of it).
- If a suite gains or loses checks, update the counts in the README (the
  *Tests* section) and `CHANGELOG.md`.

## Commits and pull requests

- Short first line in the imperative ("Add the quota...", "Fix ..."), body
  if the why isn't obvious.
- Describe the **why** of the change, not just the what.
- List the suites you ran in the PR description.
- UI (web/desktop): attach a before/after screenshot.
- The CI suites (tests + desktop build) must pass; the desktop build is
  `cd desktop && npm ci && npx tsc --noEmit && npm run build && npm run tauri build`.

## Community

Questions, setup help, and design discussion happen on the
[OpenDrop Discord](https://discord.gg/vREBPZuvhV). Issues stay reserved for
bugs and features.

## Issues

- **Bug**: OS, Python version, steps to reproduce, expected vs. observed
  behavior.
- **Feature**: describe the real-world use before the proposed solution.

## Security

Don't report a vulnerability in a public issue: see
[SECURITY.md](SECURITY.md) (GitHub private form or e-mail).
