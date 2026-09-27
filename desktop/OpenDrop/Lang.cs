using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Markup.Xaml;
using Avalonia.Styling;

namespace OpenDrop;

// Two-language UI (English/French). The choice lives in config.json
// ("language": "en" | "fr"). The active string table is injected into
// Application.Resources (a single dictionary) so every DynamicResource
// text resolves in the chosen language and updates live on switch.
internal static class Lang
{
    public static string Current { get; private set; } = "en";

    private static readonly Dictionary<string, string> _en =
        Load("avares://OpenDrop/Strings.en.axaml");
    private static readonly Dictionary<string, string> _fr =
        Load("avares://OpenDrop/Strings.fr.axaml");

    // Called once at startup, before any window is built.
    public static void Init() => Set(ReadConfigLanguage());

    // Reads the language from config.json; English on first start or when
    // the file is missing/corrupt.
    public static string ReadConfigLanguage()
    {
        try
        {
            var path = QuotaUsage.ConfigPath;
            if (File.Exists(path))
            {
                using var doc = JsonDocument.Parse(File.ReadAllText(path));
                if (doc.RootElement.TryGetProperty("language", out var value))
                {
                    var s = value.GetString();
                    if (s != null && s.StartsWith("fr", StringComparison.OrdinalIgnoreCase))
                        return "fr";
                }
            }
        }
        catch { }
        return "en";
    }

    // Replaces the contents of Application.Resources with the active
    // language table. DynamicResource references re-resolve immediately.
    public static void Set(string lang)
    {
        Current = lang != null && lang.StartsWith("fr", StringComparison.OrdinalIgnoreCase)
            ? "fr"
            : "en";

        var app = Application.Current;
        if (app == null) return;

        var res = app.Resources;
        res.Clear();
        var table = Current == "fr" ? _fr : _en;
        foreach (var kv in table)
            res[kv.Key] = kv.Value;
    }

    // Localized string for code-behind (labels in XAML use DynamicResource).
    public static string T(string key)
    {
        var table = Current == "fr" ? _fr : _en;
        return table.TryGetValue(key, out var value) ? value : key;
    }

    public static string Format(string key, params object?[] args)
    {
        try
        {
            return string.Format(T(key), args);
        }
        catch (FormatException)
        {
            return T(key);
        }
    }

    // Loads a compiled string table (Strings.*.axaml) into memory.
    private static Dictionary<string, string> Load(string uri)
    {
        var dict = new Dictionary<string, string>();
        try
        {
            if (AvaloniaXamlLoader.Load(new Uri(uri)) is ResourceDictionary table)
            {
                foreach (var kv in table)
                {
                    var key = kv.Key?.ToString();
                    var val = kv.Value?.ToString();
                    if (key != null && val != null)
                        dict[key] = val;
                }
            }
        }
        catch { }
        return dict;
    }
}
