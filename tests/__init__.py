import os
import sys

# Bare runs (`python -m tests.test_X` from the repo root): put this
# repo's src/ first on sys.path before ANY test module imports
# `opendrop`, so a stale editable install (.pth) in site-packages can
# never shadow the working tree. Same insert as conftest.py, but
# earlier: the `tests` package is imported before any test module, and
# several suites import `opendrop` before they reach conftest.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
