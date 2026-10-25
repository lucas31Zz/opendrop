"""Theme ids known by OpenDrop, in one place.

The desktop app and the web page both read the id through
``/api/info`` (the pre-1.0 Avalonia app used to keep its own copy of
this catalogue in ``desktop/OpenDrop/Services/ThemeManager.cs``).
Adding a theme means adding it here *and* there - no component writes
the tuple by hand any more.
"""

# Display order, also the order offered by the settings UI.
THEMES = ("light", "dark")

# Used for a missing, unknown or hand-edited value.
DEFAULT_THEME = "dark"


def normalize_theme(value) -> str:
    """Return a known theme id; anything unknown becomes the default."""
    return value if value in THEMES else DEFAULT_THEME
