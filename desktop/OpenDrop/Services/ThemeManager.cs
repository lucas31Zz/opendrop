using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Avalonia;
using Avalonia.Styling;

namespace OpenDrop;

/// <summary>
/// One entry of the theme catalogue: the id stored in config.json (and
/// mirrored by the server on /api/info) plus the translation key of the
/// name shown in the UI. Adding a theme means adding a line here, a
/// palette in App.axaml and the same id in src/opendrop/themes.py.
/// </summary>
public sealed class ThemeDefinition
{
    public string Id { get; }
    public string Key { get; }

    public ThemeDefinition(string id, string key)
    {
        Id = id;
        Key = key;
    }
}

/// <summary>
/// Light / dark appearance. The palette itself lives in App.axaml
/// (ResourceDictionary.ThemeDictionaries): this class only picks the variant
/// and remembers the choice in config.json, so no brush is ever rewritten at
/// runtime.
/// </summary>
public static class ThemeManager
{
    public const string Light = "light";
    public const string Dark = "dark";
    public const string Default = Dark;

    private const string ConfigKey = "theme";

    private static string _current = Default;

    /// <summary>Every theme the app knows, in display order.</summary>
    public static readonly IReadOnlyList<ThemeDefinition> Themes = new[]
    {
        new ThemeDefinition(Light, "Theme.Light"),
        new ThemeDefinition(Dark, "Theme.Dark"),
    };

    /// <summary>Current theme id, always one of <see cref="Themes"/>.</summary>
    public static string Current => _current;

    /// <summary>The ids offered by the UI, in display order.</summary>
    public static readonly string[] Ids = Themes.Select(t => t.Id).ToArray();

    /// <summary>Display name of a theme id (already localised).</summary>
    public static string NameOf(string id)
    {
        foreach (var theme in Themes)
            if (theme.Id == id)
                return Lang.T(theme.Key);
        return id;
    }

    /// <summary>True when the id is part of <see cref="Themes"/>.</summary>
    public static bool IsValid(string? id) =>
        id != null && Themes.Any(t => t.Id == id);

    /// <summary>Applies the theme saved in config.json (default: dark).</summary>
    public static void LoadAndApply()
    {
        Set(ReadThemeFromConfig());
    }

    /// <summary>Switches to a theme id and persists the choice.</summary>
    public static void Set(string? themeId)
    {
        _current = IsValid(themeId) ? themeId! : Default;
        Apply();
        WriteThemeToConfig(_current);
    }

    private static void Apply()
    {
        if (Application.Current == null)
            return;
        Application.Current.RequestedThemeVariant =
            _current == Light ? ThemeVariant.Light : ThemeVariant.Dark;
    }

    private static string GetConfigPath()
    {
        // Same path as every other component: the shell folder and the
        // LOCALAPPDATA environment variable are not always the same
        // directory (tests and sandboxed runs redirect the variable), and
        // the theme writer must follow that redirection like Lang,
        // SettingsWindow, ServerManager and MoveRegistry already do.
        return QuotaUsage.ConfigPath;
    }

    private static string? ReadThemeFromConfig()
    {
        try
        {
            var path = GetConfigPath();
            if (!File.Exists(path)) return null;
            using var doc = JsonDocument.Parse(File.ReadAllText(path));
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

            var dict = new Dictionary<string, object>();
            if (File.Exists(path))
            {
                try
                {
                    using var doc = JsonDocument.Parse(File.ReadAllText(path));
                    foreach (var prop in doc.RootElement.EnumerateObject())
                        dict[prop.Name] = prop.Value.Clone();
                }
                catch { }
            }

            dict[ConfigKey] = themeId;
            File.WriteAllText(path, JsonSerializer.Serialize(
                dict, new JsonSerializerOptions { WriteIndented = true }));
        }
        catch { }
    }
}
