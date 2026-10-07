"""Theme ids known by OpenDrop, in one place.

The desktop app keeps the same catalogue in
``desktop/OpenDrop/Services/ThemeManager.cs`` (palettes in App.axaml) and
the web page gets the id through ``/api/info``. Adding a theme means
adding it here *and* there - no component writes the tuple by hand any
more.
"""

# Display order, also the order offered by the settings UI.
THEMES = ("light", "dark")

# Used for a missing, unknown or hand-edited value.
DEFAULT_THEME = "dark"


def normalize_theme(value) -> str:
    """Return a known theme id; anything unknown becomes the default."""
    return value if value in THEMES else DEFAULT_THEME
