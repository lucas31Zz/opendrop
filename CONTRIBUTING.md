# Contributing to OpenDrop

Thanks for your interest in the project. This document explains how to
submit a fix or a feature.

## Prerequisites

- Python **3.10+** (developed and tested on 3.12)
- **.NET 8 SDK** if you touch the desktop app (Avalonia, Windows or Linux)
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
python -m tests.test_security     # 36
python -m tests.test_routes       # 44
python -m tests.test_paths        # 43
python -m tests.test_quota        # 40
python -m tests.test_sessions     # 34
python -m tests.test_tls          # 15
python -m tests.test_server       # 11
python -m tests.test_beta         # 64
```

- Every suite exits with a non-zero status when it fails.
- `python -m tests.test_beta --large` (76) is slower: run it before merging
  changes that touch the protocol or the multipart handling.
- Tests **always** work in a temporary folder created by
  `tests/conftest.py`: no user file is read, written, or deleted. Never
  break that isolation.

## Conventions

- **Code and comments in French, without accents** (keeps encoding simple
  everywhere). Markdown (README, docs) may use accents.
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
- The CI suites (tests + desktop build) must pass.

## Issues

- **Bug**: OS, Python version, steps to reproduce, expected vs. observed
  behavior.
- **Feature**: describe the real-world use before the proposed solution.

## Security

Don't report a vulnerability in a public issue: see
[SECURITY.md](SECURITY.md) (GitHub private form or e-mail).
