using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Media;
using Avalonia.Styling;

namespace OpenDrop;

/// <summary>
/// Central theme management. Loads built-in themes, applies them at runtime,
/// persists the choice in config.json, and exposes a simple API for the UI.
/// </summary>
public static class ThemeManager
{
    private const string ConfigKey = "theme";
    private static readonly Dictionary<string, ThemeDefinition> _themes = new(StringComparer.OrdinalIgnoreCase);
    private static string _currentThemeId = "system";

    /// <summary>All registered themes (id -> definition).</summary>
    public static IReadOnlyDictionary<string, ThemeDefinition> Themes => _themes;

    /// <summary>Currently active theme id (never null).</summary>
    public static string CurrentThemeId => _currentThemeId;

    /// <summary>Currently active theme definition.</summary>
    public static ThemeDefinition CurrentTheme => _themes[_currentThemeId];

    /// <summary>Raised after the theme has been applied (UI can react).</summary>
    public static event Action<string>? ThemeChanged;

    /// <summary>
    /// Registers all built-in themes. Called once at startup.
    /// </summary>
    public static void Initialize()
    {
        RegisterBuiltInThemes();
    }

    /// <summary>
    /// Loads the saved theme from config.json and applies it.
    /// </summary>
    public static void LoadAndApply()
    {
        var saved = ReadThemeFromConfig();
        if (!string.IsNullOrEmpty(saved) && _themes.ContainsKey(saved))
        {
            _currentThemeId = saved;
        }
        Apply(_currentThemeId);
    }

    /// <summary>
    /// Switches to a theme by id, persists it, and applies immediately.
    /// </summary>
    public static bool SetTheme(string themeId)
    {
        if (!_themes.ContainsKey(themeId))
            return false;

        _currentThemeId = themeId;
        WriteThemeToConfig(themeId);
        Apply(themeId);
        ThemeChanged?.Invoke(themeId);
        return true;
    }

    /// <summary>
    /// Registers a custom theme (for future extensions/plugins).
    /// </summary>
    public static void RegisterTheme(ThemeDefinition theme)
    {
        _themes[theme.Id] = theme;
    }

    private static void RegisterBuiltInThemes()
    {
        // ── System: follows OS setting ───────────────────────────────
        _themes["system"] = new ThemeDefinition(
            Id: "system",
            NameKey: "Theme.System",
            DescriptionKey: "Theme.SystemDesc",
            IsSystem: true,
            LightResources: null,
            DarkResources: null);

        _themes["light"] = new ThemeDefinition(
            Id: "light",
            NameKey: "Theme.Light",
            DescriptionKey: "Theme.LightDesc",
            Variant: ThemeVariant.Light);

        _themes["dark"] = new ThemeDefinition(
            Id: "dark",
            NameKey: "Theme.Dark",
            DescriptionKey: "Theme.DarkDesc",
            Variant: ThemeVariant.Dark);

        // ── Neon Cyberpunk ───────────────────────────────────────────
        _themes["neon"] = new ThemeDefinition(
            Id: "neon",
            NameKey: "Theme.Neon",
            DescriptionKey: "Theme.NeonDesc",
            Variant: ThemeVariant.Dark,
            Accent: "#00ffff",
            Background: "#0a0a12",
            Surface: "#12121f",
            SurfaceHover: "#1a1a2e",
            Border: "#00ffff44",
            TextPrimary: "#e0ffff",
            TextSecondary: "#88ffcc",
            FontFamily: "Consolas, JetBrains Mono, monospace");

        // ── Midnight (deep blue professional) ────────────────────────
        _themes["midnight"] = new ThemeDefinition(
            Id: "midnight",
            NameKey: "Theme.Midnight",
            DescriptionKey: "Theme.MidnightDesc",
            Variant: ThemeVariant.Dark,
            Accent: "#4da6ff",
            Background: "#050a14",
            Surface: "#0d1b2e",
            SurfaceHover: "#142642",
            Border: "#4da6ff33",
            TextPrimary: "#cce4ff",
            TextSecondary: "#7aa8cc");

        // ── Forest (nature green) ────────────────────────────────────
        _themes["forest"] = new ThemeDefinition(
            Id: "forest",
            NameKey: "Theme.Forest",
            DescriptionKey: "Theme.ForestDesc",
            Variant: ThemeVariant.Dark,
            Accent: "#4ade80",
            Background: "#05140a",
            Surface: "#0a2212",
            SurfaceHover: "#12361c",
            Border: "#4ade8033",
            TextPrimary: "#d1fad1",
            TextSecondary: "#7dd08a");

        // ── Sunset (warm orange/pink) ────────────────────────────────
        _themes["sunset"] = new ThemeDefinition(
            Id: "sunset",
            NameKey: "Theme.Sunset",
            DescriptionKey: "Theme.SunsetDesc",
            Variant: ThemeVariant.Dark,
            Accent: "#ff6b4a",
            Background: "#1a0a08",
            Surface: "#2a120e",
            SurfaceHover: "#3d1a12",
            Border: "#ff6b4a33",
            TextPrimary: "#ffe8e0",
            TextSecondary: "#e8a890");

        // ── Monochrome (minimalist grayscale) ────────────────────────
        _themes["monochrome"] = new ThemeDefinition(
            Id: "monochrome",
            NameKey: "Theme.Monochrome",
            DescriptionKey: "Theme.MonochromeDesc",
            Variant: ThemeVariant.Dark,
            Accent: "#ffffff",
            Background: "#0a0a0a",
            Surface: "#141414",
            SurfaceHover: "#1e1e1e",
            Border: "#ffffff22",
            TextPrimary: "#f0f0f0",
            TextSecondary: "#a0a0a0");

        // ── Rose (elegant pink) ──────────────────────────────────────
        _themes["rose"] = new ThemeDefinition(
            Id: "rose",
            NameKey: "Theme.Rose",
            DescriptionKey: "Theme.RoseDesc",
            Variant: ThemeVariant.Dark,
            Accent: "#f472b6",
            Background: "#1a0814",
            Surface: "#2a0e1c",
            SurfaceHover: "#3d1226",
            Border: "#f472b633",
            TextPrimary: "#ffeef6",
            TextSecondary: "#e8a8c8");

        // ── Amber (retro terminal amber) ─────────────────────────────
        _themes["amber"] = new ThemeDefinition(
            Id: "amber",
            NameKey: "Theme.Amber",
            DescriptionKey: "Theme.AmberDesc",
            Variant: ThemeVariant.Dark,
            Accent: "#ffb000",
            Background: "#1a1200",
            Surface: "#261c00",
            SurfaceHover: "#332600",
            Border: "#ffb00033",
            TextPrimary: "#ffe080",
            TextSecondary: "#ccaa55",
            FontFamily: "VT323, Courier New, monospace");
    }

    private static void Apply(string themeId)
    {
        if (Application.Current == null)
            return;

        var theme = _themes[themeId];
        var dict = Application.Current.Resources;

        // Remove previous custom theme resources
        var keysToRemove = dict.Keys
            .Where(k => k is string s && s.StartsWith("Theme.", StringComparison.Ordinal))
            .ToList();
        foreach (var k in keysToRemove)
            dict.Remove(k);

        if (theme.IsSystem)
        {
            Application.Current.RequestedThemeVariant = null; // follow OS
            return;
        }

        Application.Current.RequestedThemeVariant = theme.EffectiveVariant;

        try
        {
            // Inject CSS-like variables as DynamicResources for use in XAML
            dict["Theme.Accent"] = theme.Accent;
            dict["Theme.Background"] = theme.Background;
            dict["Theme.Surface"] = theme.Surface;
            dict["Theme.SurfaceHover"] = theme.SurfaceHover;
            dict["Theme.Border"] = theme.Border;
            dict["Theme.TextPrimary"] = theme.TextPrimary;
            dict["Theme.TextSecondary"] = theme.TextSecondary;
            dict["Theme.FontFamily"] = theme.FontFamily ?? "Segoe UI, system-ui, sans-serif";

            // FluentTheme respects RequestedThemeVariant; we also push a few
            // commonly used overrides so custom controls pick them up.
            dict["SystemControlBackgroundBaseHighBrush"] = theme.Surface;
            dict["SystemControlBackgroundChromeMediumBrush"] = theme.SurfaceHover;
            dict["SystemControlForegroundBaseHighBrush"] = theme.TextPrimary;
            dict["SystemControlForegroundBaseMediumBrush"] = theme.TextSecondary;
            dict["SystemControlHighlightAccentBrush"] = theme.Accent;
            dict["SystemControlHighlightAltAccentBrush"] = theme.Accent;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[ThemeManager] Apply failed: {ex.Message}");
            // Revert to system theme on error
            Application.Current.RequestedThemeVariant = null;
            throw;
        }
    }

    private static string GetConfigPath()
    {
        var baseDir = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        return Path.Combine(baseDir, "OpenDrop", "config.json");
    }

    private static string? ReadThemeFromConfig()
    {
        try
        {
            var path = GetConfigPath();
            if (!File.Exists(path)) return null;
            var json = File.ReadAllText(path);
            var doc = JsonDocument.Parse(json);
            if (doc.RootElement.TryGetProperty(ConfigKey, out var val))
                return val.GetString();
        }
        catch { }
        return null;
    }

    private static void WriteThemeToConfig(string themeId)
    {
        try
        {
            var path = GetConfigPath();
            var dir = Path.GetDirectoryName(path);
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);

            JsonElement root;
            if (File.Exists(path))
            {
                var json = File.ReadAllText(path);
                root = JsonDocument.Parse(json).RootElement.Clone();
            }
            else
            {
                root = JsonDocument.Parse("{}").RootElement.Clone();
            }

            // JsonElement is immutable → build a new dictionary
            var dict = new Dictionary<string, object>();
            foreach (var prop in root.EnumerateObject())
                dict[prop.Name] = prop.Value.Clone();

            dict[ConfigKey] = themeId;

            var options = new JsonSerializerOptions { WriteIndented = true };
            File.WriteAllText(path, JsonSerializer.Serialize(dict, options));
        }
        catch { }
    }
}

/// <summary>
/// Immutable theme definition. All colours are hex strings (#RRGGBB or #RRGGBBAA).
/// </summary>
public sealed record ThemeDefinition(
    string Id,
    string NameKey,
    string DescriptionKey,
    ThemeVariant? Variant = null,
    bool IsSystem = false,
    string? Accent = null,
    string? Background = null,
    string? Surface = null,
    string? SurfaceHover = null,
    string? Border = null,
    string? TextPrimary = null,
    string? TextSecondary = null,
    string? FontFamily = null,
    ResourceDictionary? LightResources = null,
    ResourceDictionary? DarkResources = null)
{
    public ThemeVariant EffectiveVariant => Variant ?? ThemeVariant.Dark;
    public string DisplayName => Lang.T(NameKey);
    public string Description => Lang.T(DescriptionKey);
}